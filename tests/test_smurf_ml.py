# -*- coding: utf-8 -*-
"""Tests TDD para LANE 3 (ML/Smurf) FIX-09..FIX-12.

FIX-09  Pipeline XGBoost morto + UI mentirosa.
FIX-10  /smurfs O(n²·m²) síncrono no event loop -> to_thread + assinaturas.
FIX-11  hit_count>=1 / $exists:True / sincronia por timestamp de poll.
FIX-12  Caches IsolationForest + debounce TTL do treino analytics.
"""
from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

import pytest

from cogs import smurf_detection_cog as sdc


def make_player(tag, name, th=15, trophies=5000, exp=100):
    return SimpleNamespace(
        tag=tag, name=name, town_hall=th, exp_level=exp, trophies=trophies,
        war_stars=1000, attack_wins=500, defense_wins=200,
        builder_hall_level=10, hero_equipment=[], troops=[], spells=[],
        achievements=[],
    )


@pytest.fixture
def make_cog():
    bot = SimpleNamespace(db=None, api_client=None, clan_tag="#T", get_cog=lambda *a: None)
    cog = sdc.SmurfDetectionCog(bot)
    return cog


# ---------------------------------------------------------------------------
# FIX-09
# ---------------------------------------------------------------------------

class FakeCursor:
    def __init__(self, docs):
        self._docs = iter(docs)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._docs)
        except StopIteration:
            raise StopAsyncIteration from None


class FakeColl:
    def __init__(self, store=None):
        self._store = store if store is not None else []

    async def find_one(self, q):
        for d in self._store:
            if d["_id"] == q.get("_id"):
                return d
        return None

    async def insert_one(self, doc):
        self._store.append(doc)

    async def update_one(self, *a, **k):
        query = a[0] if a else k.get("filter", {})
        update = a[1] if len(a) > 1 else k.get("update", {})
        for d in self._store:
            if d["_id"] == query.get("_id"):
                for key, val in (update.get("$set") or {}).items():
                    d[key] = val

    async def delete_one(self, *a, **k):
        query = a[0] if a else k.get("filter", {})
        for i, d in enumerate(self._store):
            if d["_id"] == query.get("_id"):
                del self._store[i]
                return

    def find(self, q):
        return FakeCursor([d for d in self._store if all(
            v == d.get(k) for k, v in q.items()
        )])

    async def count_documents(self, q):
        return sum(1 for d in self._store if all(v == d.get(k) for k, v in q.items()))


class FakeDB:
    def __init__(self, training=None, evidence=None):
        self.smurf_training = FakeColl(training if training is not None else [])
        self.smurf_evidence = FakeColl(evidence if evidence is not None else [])


def test_fix09_store_includes_26_features(make_cog):
    p1 = make_player("#1", "Alpha")
    p2 = make_player("#2", "betaa")
    cog = make_cog
    stored = []
    cog.db = FakeDB(stored)

    df = cog._extract_pair_features(p1, p2, {"score": 10, "logs": []}, baseline=None)
    feats = df.iloc[0].to_dict()

    assert [k for k in feats] == cog.XGB_FEATURE_NAMES
    assert len(feats) == 26

    asyncio.run(cog._store_training_example_async("a_b", "#1", "#2", feats, pseudo_label=0.7))

    assert stored
    doc = stored[0]
    assert doc["features"] == feats
    assert set(cog.XGB_FEATURE_NAMES) == set(doc["features"].keys())
    assert doc["real_label"] is None
    assert doc["pseudo_label"] == 0.7


def test_fix09_is_valid_real_label_rejects_pseudo(make_cog):
    cog = make_cog
    assert cog._is_valid_real_label(0) is True
    assert cog._is_valid_real_label(1) is True
    assert cog._is_valid_real_label(0.0) is True
    assert cog._is_valid_real_label(1.0) is True
    assert cog._is_valid_real_label(True) is True
    assert cog._is_valid_real_label(0.5) is False
    assert cog._is_valid_real_label(None) is False
    assert cog._is_valid_real_label("x") is False


def test_fix09_fit_data_rejects_pseudo05(make_cog):
    cog = make_cog
    feats = {k: 0.1 for k in cog.XGB_FEATURE_NAMES}
    docs = [
        {"_id": "a", "features": feats, "real_label": 0, "real_weight": 1.0},
        {"_id": "b", "features": feats, "real_label": 1, "real_weight": 1.0},
        {"_id": "p", "features": feats, "real_label": 0.5, "real_weight": 0.3},
        {"_id": "n", "features": feats, "real_label": None, "real_weight": 0.3},
    ]
    rows, labels, weights = cog._build_xgb_fit_data(docs, cog.XGB_FEATURE_NAMES)
    assert len(labels) == 2
    assert labels == [0.0, 1.0]
    assert len(rows) == 2
    assert len(weights) == 2


def test_fix09_train_not_called_below_20_labeled(make_cog, monkeypatch):
    cog = make_cog
    feats = {k: 0.1 for k in cog.XGB_FEATURE_NAMES}
    docs = [
        {"_id": f"d{i}", "features": feats,
         "real_label": i % 2, "real_weight": 1.0}
        for i in range(19)
    ]
    cog.db = FakeDB(docs)
    fit_calls = {"n": 0, "labels": []}

    class FakeModel:
        def fit(self, X, y, sample_weight=None):
            fit_calls["n"] += 1
            fit_calls["labels"] = list(y)

    cog._xgb_model = FakeModel()
    monkeypatch.setattr(cog, "_ensure_xgb_model", lambda: None)

    asyncio.run(cog._train_xgb_from_db())
    assert fit_calls["n"] == 0
    assert cog._xgb_is_trained is False


def test_fix09_train_called_at_20_labeled_and_ignores_05(make_cog, monkeypatch):
    cog = make_cog
    feats = {k: 0.1 for k in cog.XGB_FEATURE_NAMES}
    docs = [
        {"_id": f"d{i}", "features": feats,
         "real_label": i % 2, "real_weight": 1.0}
        for i in range(20)
    ]
    docs.append({"_id": "pseudo", "features": feats, "real_label": 0.5})
    docs.append({"_id": "unlab", "features": feats, "real_label": None})
    cog.db = FakeDB(docs)
    fit_calls = {"n": 0, "labels": []}

    class FakeModel:
        def fit(self, X, y, sample_weight=None):
            fit_calls["n"] += 1
            fit_calls["labels"] = sorted(float(v) for v in y)

    cog._xgb_model = FakeModel()
    monkeypatch.setattr(cog, "_ensure_xgb_model", lambda: None)

    asyncio.run(cog._train_xgb_from_db())
    assert fit_calls["n"] == 1
    assert set(fit_calls["labels"]) == {0.0, 1.0}
    assert cog._xgb_is_trained is True
    assert cog._xgb_real_labels == 20


def test_fix09_ui_honesta_com_0_labels(make_cog):
    cog = make_cog
    cog._xgb_is_trained = False
    cog._xgb_model = None
    cog._xgb_real_labels = 0
    p1 = make_player("#1", "alpha")
    p2 = make_player("#2", "alpha_alt")

    telemetry = {"score": 30, "logs": [
        {"axis": "Sincronia Mutex", "msg": "ataques sincronizados"},
    ]}
    dossier = cog._run_ml_inference(p1, p2, telemetry)

    assert dossier is not None
    assert dossier["model_status"] == "cold_start"
    thoughts = dossier["thoughts"]
    assert any(t["axis"] == "Bayes (cold start)" for t in thoughts)
    assert any("cold start" in t["text"] for t in thoughts)
    assert not any("recalibrou" in t["text"] for t in thoughts)
    assert not any("Modo cold start" in t["text"] for t in thoughts)


def test_fix09_confirmation_sets_real_label(make_cog, monkeypatch):
    cog = make_cog
    stored = []
    evidence = [{"_id": "a_b", "tag1": "#1", "tag2": "#2", "score": 30, "logs": []}]
    cog.db = FakeDB(stored, evidence)
    cog.bot.get_cog = lambda name: None
    monkeypatch.setattr(cog, "_train_xgb_from_db", lambda: asyncio.sleep(0))

    feats = {k: 0.1 for k in cog.XGB_FEATURE_NAMES}
    asyncio.run(cog._store_training_example_async("a_b", "#1", "#2", feats, pseudo_label=0.7))
    assert stored[0]["real_label"] is None

    msg = asyncio.run(cog.absolve_pair("a_b"))
    assert stored[0]["real_label"] == 0
    assert "Absolvido" in msg["message"]
    assert msg["status"] == "success"


# ---------------------------------------------------------------------------
# FIX-10
# ---------------------------------------------------------------------------

def test_fix10_candidate_pairs_correctness(make_cog):
    cog = make_cog
    cog.MIN_FUZZY_RATIO = 78
    pa = make_player("#1", "joaosilva")
    pb = make_player("#2", "joaosilva2")
    pc = make_player("#3", "maria_linda")
    pd = make_player("#4", "carlos_edu")

    players = [pa, pb, pc, pd]
    sigs = cog._build_player_signatures(players)
    judged = {"#3_#4"}

    pairs = cog._candidate_pairs(players, sigs, telemetry_ids={"#1_#4"}, judged=judged)

    pair_ids = {pid for _, _, pid in pairs}
    assert "#1_#2" in pair_ids          # nomes similares (joaosilva ~ joaosilva2)
    assert "#1_#4" in pair_ids          # dissimilar, mas tem telemetria -> incluso
    assert "#2_#3" not in pair_ids      # dissimilar e sem telemetria -> excluído
    assert "#3_#4" not in pair_ids      # julgado -> excluído


def test_fix10_build_player_signatures(make_cog):
    cog = make_cog
    sigs = cog._build_player_signatures([make_player("#1", "Joao.O-Silva")])
    assert sigs["#1"]["name_norm"] == "joaoosilva"


def test_fix10_inference_executes_via_to_thread(make_cog):
    cog = make_cog
    cog._xgb_is_trained = False
    p1 = make_player("#1", "alpha")
    p2 = make_player("#2", "alpha_alt")

    threads = []
    orig = cog._run_ml_inference

    def wrapped(p1_, p2_, telemetry_):
        threads.append(threading.current_thread().name)
        return orig(p1_, p2_, telemetry_)

    cog._run_ml_inference = wrapped

    telemetry = {"score": 30, "logs": [
        {"axis": "Sincronia Mutex", "msg": "ataques sincronizados"},
    ]}
    dossier = asyncio.run(cog._run_ml_inference_in_thread(p1, p2, telemetry))

    assert dossier is not None
    assert threads and threads[0] != "MainThread"


# ---------------------------------------------------------------------------
# FIX-11
# ---------------------------------------------------------------------------

def test_fix11_donation_recurrence_threshold(make_cog):
    cog = make_cog
    assert cog._should_flag_donation_recurrence(0) is False
    assert cog._should_flag_donation_recurrence(1) is False
    assert cog._should_flag_donation_recurrence(2) is True
    assert cog._should_flag_donation_recurrence(3) is True


def test_fix11_real_label_filter_is_eq_only(make_cog):
    cog = make_cog
    assert cog._real_label_filter() == {"real_label": {"$in": [0, 1]}}


def test_fix11_find_donation_transfers_content_marker(make_cog):
    cog = make_cog
    m1 = SimpleNamespace(tag="#A", name="A", donations=100, received=5)
    m2 = SimpleNamespace(tag="#B", name="B", donations=5, received=100)
    m3 = SimpleNamespace(tag="#C", name="C", donations=0, received=0)
    current = {
        "#A": {"donations": 120, "received": 5, "member": m1},
        "#B": {"donations": 5, "received": 120, "member": m2},
        "#C": {"donations": 0, "received": 0, "member": m3},
    }
    last = {
        "#A": {"donations": 100, "received": 5, "member": m1},
        "#B": {"donations": 5, "received": 100, "member": m2},
        "#C": {"donations": 0, "received": 0, "member": m3},
    }
    transfers = cog._find_donation_transfers(current, last)
    assert len(transfers) == 1
    t = transfers[0]
    assert t["pair_id"] == "#A_#B"
    assert t["amount"] == 20
    assert t["marker"] == "don:20"


def test_fix11_attack_content_marker_from_order(make_cog):
    cog = make_cog
    atk1 = SimpleNamespace(order=1, stars=3, attacker_tag="#A", defender_tag="#X")
    atk2 = SimpleNamespace(order=2, stars=3, attacker_tag="#B", defender_tag="#Y")
    atk9 = SimpleNamespace(order=9, stars=3, attacker_tag="#C", defender_tag="#Z")
    assert cog._attack_content_marker(atk1) == 1
    assert cog._attack_content_marker(atk2) == 2
    assert cog._attack_content_marker(atk9) == 9

    pairs = cog._find_synchronized_attacks({"#A": 1, "#B": 2, "#C": 9, "#D": 10}, max_gap=1)
    assert ("#A", "#B") in pairs
    assert ("#C", "#D") in pairs
    assert ("#A", "#C") not in pairs


# ---------------------------------------------------------------------------
# FIX-12
# ---------------------------------------------------------------------------

def test_fix12_clear_isolation_forest_caches(make_cog):
    cog = make_cog
    cog._if_score_cache.update({"#1": 0.9, "#2": 0.3})
    cog._pair_if_score_cache.update({"#1_#2": 0.8})
    cog._if_score_ts.update({"#1": 1.0, "#2": 2.0})
    cog._pair_if_score_ts.update({"#1_#2": 1.0})

    cog._clear_isolation_forest_caches()
    assert cog._if_score_cache == {}
    assert cog._pair_if_score_cache == {}
    assert cog._if_score_ts == {}
    assert cog._pair_if_score_ts == {}


def test_fix12_prepare_baselines_clears_caches_on_retrain(make_cog):
    cog = make_cog
    cog._if_score_cache.update({"#1": 0.9})
    cog._pair_if_score_cache.update({"#1_#2": 0.8})

    cog._prepare_clan_baselines(clan_members=[], players_full=[])
    assert cog._isolation_forest is None
    assert cog._pair_isolation_forest is None
    assert cog._if_score_cache == {}
    assert cog._pair_if_score_cache == {}


def test_fix12_if_cache_size_limited(make_cog):
    cog = make_cog
    cog._if_score_cache_maxsize = 100
    for i in range(250):
        cog._if_score_cache[f"#P{i}"] = 0.5
        cog._if_score_ts[f"#P{i}"] = float(i)
    cog._evict_if_score_cache()
    assert len(cog._if_score_cache) <= 100


class _CursorVazio:
    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class _CollVazia:
    def find(self, *_args, **_kwargs):
        return _CursorVazio()


def test_get_web_dossier_delega_inferencia_para_thread(make_cog):
    """O handler web não pode rodar a inferência pesada no event loop."""
    cog = make_cog
    m1 = SimpleNamespace(tag="#1")
    m2 = SimpleNamespace(tag="#2")

    class _APIFake:
        async def get_clan(self, _tag):
            return SimpleNamespace(members=[m1, m2])

        def get_players(self, _tags):
            async def _gen():
                yield make_player("#1", "Alpha")
                yield make_player("#2", "betaa")

            return _gen()

    cog.bot.api_client = _APIFake()
    cog.bot.clan_tag = "#CLAN"
    cog.db = SimpleNamespace(smurf_evidence=_CollVazia(), smurf_training=_CollVazia())
    cog._prepare_clan_baselines = lambda *a, **k: None
    cog._phonetic_lexical_analysis = lambda a, b: 100.0

    chamadas = []

    async def _thread_falsa(p1, p2, _telemetry):
        chamadas.append((p1.tag, p2.tag))
        return None

    cog._run_ml_inference_in_thread = _thread_falsa

    asyncio.run(cog.get_web_dossier())

    assert chamadas, "get_web_dossier deve delegar à inferência via _run_ml_inference_in_thread"