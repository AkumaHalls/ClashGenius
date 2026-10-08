"""Testes da LANE 4a: robustez dos loops, marcador semanal, semana ISO,
normalizacao de timestamps do relatorio de atividade e dedupe do war_history."""
import asyncio
import datetime
import inspect
from types import SimpleNamespace

import pytz
import pytest

from cogs import tournament_cog
from cogs.activity_report_cog import ActivityReportCog
from cogs.donation_cog import DonationsCog
from cogs.maintenance_cog import MaintenanceCog
from cogs.performance_cog import PerformanceCog
from cogs.tournament_cog import TournamentCog


def _bson_rank(value):
    if value is None:
        return 0
    if isinstance(value, bool):
        return 5
    if isinstance(value, (int, float)):
        return 1
    if isinstance(value, str):
        return 2
    if isinstance(value, datetime.datetime):
        return 3
    if isinstance(value, (dict, list)):
        return 4
    return 6


def _get_path(doc, path):
    current = doc
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _to_comparable(value):
    if isinstance(value, datetime.datetime) and value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value


def _matches_condition(value, operand, operator):
    if operator in ("$gt", "$gte", "$lt", "$lte"):
        if _bson_rank(value) != _bson_rank(operand):
            return False
        left, right = _to_comparable(value), _to_comparable(operand)
        try:
            if operator == "$gt":
                return left > right
            if operator == "$gte":
                return left >= right
            if operator == "$lt":
                return left < right
            return left <= right
        except TypeError:
            return False
    if operator == "$ne":
        if operand is None:
            return value is not None
        return value != operand
    if operator == "$eq":
        if operand is None:
            return value is None
        return _bson_rank(value) == _bson_rank(operand) and _to_comparable(value) == _to_comparable(operand)
    if operator == "$in":
        return value in operand
    raise AssertionError(f"operador nao suportado no fake: {operator}")


def _match_query(doc, query):
    for key, condition in query.items():
        if key == "$or":
            if not any(_match_query(doc, sub) for sub in condition):
                return False
            continue
        value = _get_path(doc, key)
        if isinstance(condition, dict) and condition and all(str(k).startswith("$") for k in condition):
            for operator, operand in condition.items():
                if not _matches_condition(value, operand, operator):
                    return False
        elif value != condition:
            return False
    return True


def _apply_projection(doc, projection):
    if not projection:
        return doc
    included = [path for path, flag in projection.items() if flag and path != "_id"]
    if not included:
        return doc
    result = {}
    for path in included:
        value = _get_path(doc, path)
        if value is None:
            continue
        target = result
        parts = path.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    if projection.get("_id", 1) and "_id" in doc:
        result["_id"] = doc["_id"]
    return result


def _sort_key(doc, path):
    value = _get_path(doc, path)
    rank = _bson_rank(value)
    if rank in (1, 2, 3):
        return (rank, _to_comparable(value))
    return (rank, 0)


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, path, direction=1):
        self._docs.sort(key=lambda doc: _sort_key(doc, path), reverse=direction == -1)
        return self

    def limit(self, count):
        self._docs = self._docs[:count]
        return self

    async def to_list(self, length=None):
        if length is None:
            return list(self._docs)
        return list(self._docs[:length])

    def __aiter__(self):
        self._iterator = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration


class _Result:
    def __init__(self, matched=0, modified=0, deleted=0):
        self.matched_count = matched
        self.modified_count = modified
        self.deleted_count = deleted


def _apply_set(doc, fields):
    for path, value in fields.items():
        parts = path.split(".")
        target = doc
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value


def _group_key(doc, expression):
    if isinstance(expression, str) and expression.startswith("$"):
        return _get_path(doc, expression[1:])
    if isinstance(expression, dict):
        return tuple(
            sorted(
                (field, _get_path(doc, path[1:]) if str(path).startswith("$") else path)
                for field, path in expression.items()
            )
        )
    return expression


def _accumulate(members, accumulator):
    if "$addToSet" in accumulator:
        expression = accumulator["$addToSet"]
        values = {_get_path(doc, expression[1:]) if str(expression).startswith("$") else expression for doc in members}
        return sorted(values, key=str)
    if "$sum" in accumulator:
        expression = accumulator["$sum"]
        if expression == 1:
            return len(members)
        if str(expression).startswith("$"):
            return sum(_get_path(doc, expression[1:]) or 0 for doc in members)
        return expression
    raise AssertionError(f"acumulador nao suportado no fake: {accumulator}")


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = [dict(doc) for doc in (docs or [])]

    def find(self, query=None, projection=None):
        query = query or {}
        docs = [doc for doc in self.docs if _match_query(doc, query)]
        if projection:
            docs = [_apply_projection(doc, projection) for doc in docs]
        return FakeCursor(docs)

    async def find_one(self, query, sort=None):
        cursor = self.find(query)
        if sort:
            for path, direction in reversed(sort):
                cursor.sort(path, direction)
        found = await cursor.to_list(length=1)
        return found[0] if found else None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return _Result(matched=1, modified=1)

    async def update_one(self, query, update, upsert=False):
        found = await self.find(query).to_list(length=1)
        if found:
            _apply_set(found[0], update.get("$set", {}))
            return _Result(matched=1, modified=1)
        if upsert:
            new_doc = {key: value for key, value in query.items() if not str(key).startswith("$")}
            _apply_set(new_doc, update.get("$set", {}))
            self.docs.append(new_doc)
        return _Result()

    async def delete_many(self, query):
        remaining = []
        deleted = []
        for doc in self.docs:
            (deleted if _match_query(doc, query) else remaining).append(doc)
        self.docs = remaining
        return _Result(deleted=len(deleted))

    def aggregate(self, pipeline):
        docs = [dict(doc) for doc in self.docs]
        for stage in pipeline:
            if "$match" in stage:
                docs = [doc for doc in docs if _match_query(doc, stage["$match"])]
            elif "$group" in stage:
                docs = self._group(docs, stage["$group"])
            else:
                raise AssertionError(f"estagio nao suportado no fake: {list(stage)}")
        return FakeCursor(docs)

    @staticmethod
    def _group(docs, spec):
        buckets = {}
        for doc in docs:
            buckets.setdefault(_group_key(doc, spec["_id"]), []).append(doc)
        results = []
        for key, members in buckets.items():
            grouped = {"_id": key}
            for field, accumulator in spec.items():
                if field != "_id":
                    grouped[field] = _accumulate(members, accumulator)
            results.append(grouped)
        return results


class RecordingCollection(FakeCollection):
    """Guarda as queries/projeções recebidas para provar filtro no servidor."""

    def __init__(self, docs=None):
        super().__init__(docs)
        self.queries = []
        self.projections = []

    def find(self, query=None, projection=None):
        self.queries.append(query)
        self.projections.append(projection)
        return super().find(query, projection)


class FakeDB:
    def __init__(self, **collections):
        self._collections = {name: FakeCollection(docs) for name, docs in collections.items()}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._collections.setdefault(name, FakeCollection())


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, content=None, embed=None):
        self.sent.append(SimpleNamespace(content=content, embed=embed))


class FakeBot:
    def __init__(self, db=None, clan=None, maintenance_mode=False):
        self.db = db
        self.clan = clan
        self._maintenance_mode = maintenance_mode
        self.clan_tag = "#TESTCLAN"
        self.timezone = pytz.timezone("America/Sao_Paulo")
        self.donations_channel_id = 111
        self.low_performance_channel_id = 222
        self.activity_report_channel_id = 333
        self.tournament_summary_channel_id = 444
        self.user = SimpleNamespace(id=999)
        self._ready = asyncio.Event()
        self._channels = {}

    @property
    def maintenance_mode(self):
        return self._maintenance_mode

    def get_channel(self, channel_id):
        return self._channels.setdefault(channel_id, FakeChannel())

    async def fetch_channel(self, channel_id):
        return self.get_channel(channel_id)

    async def wait_until_ready(self):
        await self._ready.wait()

    async def get_clan_data_with_cache(self, tag):
        return self.clan


class BrokenMaintenanceBot(FakeBot):
    @property
    def maintenance_mode(self):
        raise RuntimeError("falha simulada ao ler maintenance_mode")


class FakeMessage:
    def __init__(self):
        self.added = []
        self.removed = []

    async def add_reaction(self, emoji):
        self.added.append(emoji)

    async def remove_reaction(self, emoji, user):
        self.removed.append((emoji, user))


class FakeContext:
    def __init__(self, author_id=1):
        self.author = SimpleNamespace(id=author_id)
        self.message = FakeMessage()
        self.sent = []

    async def send(self, content=None, embed=None):
        self.sent.append(SimpleNamespace(content=content, embed=embed))


def _member(tag, name, th=15, trophies=5000):
    return SimpleNamespace(tag=tag, name=name, town_hall=th, trophies=trophies, league=None)


def _clan(*members):
    return SimpleNamespace(tag="#TESTCLAN", members=list(members))


def _war_doc(war_id, end_time, opponent="Los Galacticos", members=None):
    return {
        "_id": war_id,
        "war_data": {
            "end_time_iso": end_time,
            "opponent_name": opponent,
            "attacks_per_member": 2,
        },
        "our_clan_members_in_war": members or [],
    }


def _performance_clan():
    leech = SimpleNamespace(tag="#SANG", name="Sanguessuga", town_hall=16, received=5000, donations=10)
    return SimpleNamespace(members=[leech])


def _activity_setup():
    now = datetime.datetime.now(pytz.utc)
    clan = _clan(
        _member("#TAGA", "Alfa Ativa", th=15, trophies=5200),
        _member("#TAGP", "Poldro Parcial", th=14, trophies=4800),
        _member("#TAGI", "Vagabundo Inativo", th=13, trophies=4100),
    )
    wars = [
        _war_doc(
            "guerra-legado",
            int((now - datetime.timedelta(hours=2)).timestamp() * 1000),
            members=[
                {"tag": "#TAGA", "name": "Alfa Ativa", "attacks_made": [{"stars": 3}, {"stars": 2}]},
            ],
        ),
        _war_doc(
            "guerra-recente",
            (now - datetime.timedelta(hours=6)).isoformat(),
            members=[
                {"tag": "#TAGP", "name": "Poldro Parcial", "attacks_made": [{"stars": 1}]},
            ],
        ),
        _war_doc(
            "guerra-antiga",
            (now - datetime.timedelta(days=10)).isoformat(),
            members=[
                {"tag": "#TAGI", "name": "Vagabundo Inativo", "attacks_made": [{"stars": 2}, {"stars": 1}]},
            ],
        ),
    ]
    snapshots = [
        {
            "_id": "snapshot-antigo",
            "timestamp": int((now - datetime.timedelta(days=2)).timestamp() * 1000),
            "members": [
                {"tag": "#TAGA", "name": "Alfa Ativa", "donations": 40, "received": 10},
                {"tag": "#TAGP", "name": "Poldro Parcial", "donations": 50, "received": 10},
                {"tag": "#TAGI", "name": "Vagabundo Inativo", "donations": 30, "received": 5},
            ],
        },
        {
            "_id": "snapshot-atual",
            "timestamp": now,
            "members": [
                {"tag": "#TAGA", "name": "Alfa Ativa", "donations": 100, "received": 50},
                {"tag": "#TAGP", "name": "Poldro Parcial", "donations": 70, "received": 10},
                {"tag": "#TAGI", "name": "Vagabundo Inativo", "donations": 30, "received": 5},
            ],
        },
    ]
    db = FakeDB(war_history=wars, donation_snapshots=snapshots, clan_watchlist=[])
    return FakeBot(db=db, clan=clan), db


def _duplicate_war_history():
    return [
        _war_doc("guerra-antiga-id", "2026-10-04T12:00:00+00:00"),
        _war_doc("guerra-novo-id", "2026-10-04T12:00:00+00:00"),
        _war_doc("guerra-unica-id", "2026-09-20T15:00:00+00:00", opponent="Outro Clan"),
        _war_doc("guerra-sem-data", None, opponent="SemData"),
    ]


@pytest.fixture()
async def make_cog():
    created = []

    def _make(cog_cls, bot):
        cog = cog_cls(bot)
        created.append(cog)
        return cog

    yield _make

    for cog in created:
        result = cog.cog_unload()
        if inspect.isawaitable(result):
            await result
    await asyncio.sleep(0)


async def test_donation_post_reports_task_nao_propaga_erro(make_cog, caplog):
    cog = make_cog(DonationsCog, FakeBot())
    calls = []

    async def _explode(days, force=False, interaction=None):
        calls.append(days)
        raise RuntimeError("falha simulada ao gerar relatorio")

    cog.generate_and_send_report = _explode
    await cog.post_reports_task.coro(cog)

    assert calls == [1]
    assert "relatório de doações agendado" in caplog.text


async def test_tournament_snapshot_task_nao_propaga_erro(make_cog, caplog):
    cog = make_cog(TournamentCog, FakeBot(db=FakeDB()))
    calls = []

    async def _boom():
        calls.append(True)
        raise RuntimeError("falha simulada ao tirar snapshot")

    cog.take_snapshot = _boom
    await cog.snapshot_task.coro(cog)

    assert calls == [True]
    assert "Erro ao verificar snapshot do torneio" in caplog.text


async def test_tournament_end_check_task_nao_propaga_erro_de_guarda(make_cog, caplog):
    cog = make_cog(TournamentCog, BrokenMaintenanceBot(db=FakeDB()))

    await cog.end_check_task.coro(cog)

    assert "Erro ao gerar resumo do torneio" in caplog.text


async def test_performance_weekly_task_nao_propaga_erro_de_guarda(make_cog, caplog):
    cog = make_cog(PerformanceCog, BrokenMaintenanceBot(db=FakeDB()))

    await cog.weekly_report_task.coro(cog)

    assert "Erro no Relatório Semanal" in caplog.text


async def test_activity_daily_task_nao_propaga_erro_de_guarda(make_cog, caplog):
    cog = make_cog(ActivityReportCog, BrokenMaintenanceBot(db=FakeDB()))

    await cog.daily_report_task.coro(cog)

    assert "Erro no relatório diário" in caplog.text


async def test_performance_semanal_registra_marcador_apos_envio(make_cog):
    db = FakeDB()
    bot = FakeBot(db=db, clan=_performance_clan())
    cog = make_cog(PerformanceCog, bot)

    await cog.weekly_report_task.coro(cog)

    channel = bot.get_channel(bot.low_performance_channel_id)
    assert len(channel.sent) == 1
    marker = await db.system_config.find_one({"_id": "weekly_performance_report"})
    assert marker is not None
    assert isinstance(marker.get("last_run"), datetime.datetime)


async def test_performance_semanal_nao_repete_apos_restart(make_cog):
    db = FakeDB()
    bot = FakeBot(db=db, clan=_performance_clan())
    first = make_cog(PerformanceCog, bot)
    await first.weekly_report_task.coro(first)
    channel = bot.get_channel(bot.low_performance_channel_id)
    assert len(channel.sent) == 1

    restarted = make_cog(PerformanceCog, bot)
    await restarted.weekly_report_task.coro(restarted)

    assert len(channel.sent) == 1


async def test_performance_semanal_reativa_apos_sete_dias(make_cog):
    db = FakeDB()
    bot = FakeBot(db=db, clan=_performance_clan())
    await db.system_config.insert_one(
        {
            "_id": "weekly_performance_report",
            "last_run": datetime.datetime.now(pytz.utc) - datetime.timedelta(days=8),
        }
    )
    cog = make_cog(PerformanceCog, bot)

    await cog.weekly_report_task.coro(cog)

    assert len(bot.get_channel(bot.low_performance_channel_id).sent) == 1


async def test_performance_semanal_funciona_sem_banco(make_cog):
    bot = FakeBot(db=None, clan=_performance_clan())
    cog = make_cog(PerformanceCog, bot)

    await cog.weekly_report_task.coro(cog)

    assert len(bot.get_channel(bot.low_performance_channel_id).sent) == 1


async def test_membro_com_guerra_recente_nao_vira_inativo(make_cog):
    bot, _db = _activity_setup()
    cog = make_cog(ActivityReportCog, bot)

    embed = await cog.generate_activity_report(days=1)

    active = next(f for f in embed.fields if f.name.startswith("🟢"))
    partial = next(f for f in embed.fields if f.name.startswith("🟡"))
    inactive = next(f for f in embed.fields if f.name.startswith("🔴"))
    assert "Alfa Ativa" in active.value
    assert "Poldro Parcial" in partial.value
    assert "Vagabundo Inativo" in inactive.value
    assert "Alfa Ativa" not in inactive.value


async def test_activity_report_filtra_periodo_e_projeta_no_servidor(make_cog):
    now = datetime.datetime.now(pytz.utc)
    wars = RecordingCollection([
        _war_doc(
            "guerra-recente",
            (now - datetime.timedelta(hours=2)).isoformat(),
            members=[{"tag": "#TAGA", "name": "Alfa", "attacks_made": [{"stars": 3}]}],
        )
    ])
    snapshots = RecordingCollection([
        {
            "_id": "snap-atual",
            "timestamp": now,
            "members": [{"tag": "#TAGA", "name": "Alfa", "donations": 10, "received": 1}],
        }
    ])
    db = FakeDB()
    db._collections["war_history"] = wars
    db._collections["donation_snapshots"] = snapshots
    bot = FakeBot(db=db, clan=_clan(_member("#TAGA", "Alfa")))
    cog = make_cog(ActivityReportCog, bot)

    await cog.get_war_activity(days=1)
    await cog.get_donation_activity(days=1)

    assert wars.queries and "$or" in wars.queries[0]
    assert wars.projections and wars.projections[0]
    assert wars.projections[0].get("our_clan_members_in_war") == 1
    assert snapshots.projections and snapshots.projections[0]
    assert snapshots.projections[0].get("timestamp") == 1
    assert snapshots.projections[0].get("members") == 1


async def test_doacoes_com_snapshot_legado_sao_contabilizadas(make_cog):
    bot, _db = _activity_setup()
    cog = make_cog(ActivityReportCog, bot)

    activity = await cog.get_donation_activity(days=1)

    assert activity["#TAGA"]["donated"] == 60
    assert activity["#TAGA"]["received"] == 40
    assert activity["#TAGP"]["donated"] == 20
    assert activity["#TAGI"]["donated"] == 0


def test_tournament_id_usa_ano_iso():
    from cogs.tournament_cog import _tournament_id

    assert _tournament_id(datetime.datetime(2021, 1, 1, 12, 0)) == "2020-W53"
    assert _tournament_id(datetime.datetime(2020, 12, 31, 12, 0)) == "2020-W53"
    assert _tournament_id(datetime.datetime(2021, 1, 4, 12, 0)) == "2021-W01"


def test_tournament_cog_usa_semana_iso_em_todos_os_lugares():
    source = inspect.getsource(tournament_cog)

    assert "%G-W%V" in source
    assert "%Y-W%V" not in source


async def test_tournament_snapshot_usa_id_de_semana_iso(make_cog):
    from cogs.tournament_cog import _tournament_id

    clan = _clan(_member("#TAGA", "Alfa"), _member("#TAGP", "Poldro"))
    bot = FakeBot(db=FakeDB(), clan=clan)
    cog = make_cog(TournamentCog, bot)
    before = _tournament_id(datetime.datetime.now(pytz.utc))

    assert await cog.take_snapshot() is True

    after = _tournament_id(datetime.datetime.now(pytz.utc))
    stored = bot.db.tournament_snapshots.docs[0]["_id"]
    assert stored in {before, after}


async def test_dbcleanup_encontra_duplicatas_por_guerra(make_cog):
    bot = FakeBot(db=FakeDB(war_history=_duplicate_war_history()))
    cog = make_cog(MaintenanceCog, bot)
    ctx = FakeContext()

    await cog.db_cleanup.callback(cog, ctx)

    groups = cog.cleanup_confirmation_data.get(ctx.author.id)
    assert groups is not None
    assert len(groups) == 1
    assert groups[0]["count"] == 2


async def test_dbcleanup_confirmar_remove_apenas_excedentes(make_cog):
    db = FakeDB(war_history=_duplicate_war_history())
    bot = FakeBot(db=db)
    cog = make_cog(MaintenanceCog, bot)
    ctx = FakeContext()

    await cog.db_cleanup.callback(cog, ctx)
    await cog.db_cleanup_confirm.callback(cog, ctx)

    duplicated = [
        doc for doc in db.war_history.docs
        if doc["war_data"]["end_time_iso"] == "2026-10-04T12:00:00+00:00"
    ]
    assert len(duplicated) == 1
    assert any(doc["_id"] == "guerra-unica-id" for doc in db.war_history.docs)
    assert any(doc["_id"] == "guerra-sem-data" for doc in db.war_history.docs)
