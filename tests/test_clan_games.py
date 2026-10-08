# -*- coding: utf-8 -*-
"""Testes do ClanGamesCog (FIX-16a, FIX-16b, FIX-16c e resiliência de task loop)."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytz
import pytest

from cogs.clan_games_cog import ClanGamesCog


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    async def to_list(self, length=None):
        return list(self._docs)


class FakeSnapshotCollection:
    """Substituto assíncrono da coleção Mongo do snapshot dos Jogos."""

    def __init__(self, docs=None):
        self.docs = dict(docs or {})
        self.calls = []

    @staticmethod
    def _match(doc, flt):
        return all(doc.get(key) == value for key, value in flt.items())

    async def find_one(self, flt):
        self.calls.append(("find_one", flt))
        for doc in self.docs.values():
            if self._match(doc, flt):
                return doc
        return None

    def find(self, flt):
        self.calls.append(("find", flt))
        return _Cursor([doc for doc in self.docs.values() if self._match(doc, flt)])

    async def insert_many(self, docs):
        self.calls.append(("insert_many", list(docs)))
        for doc in docs:
            self.docs[doc["_id"]] = doc

    async def delete_many(self, flt):
        self.calls.append(("delete_many", flt))
        removed = len(self.docs)
        self.docs.clear()
        return SimpleNamespace(deleted_count=removed)


def _make_bot(collection):
    return SimpleNamespace(
        db=SimpleNamespace(clan_games_snapshot=collection),
        clan_tag="#TAGCLAN",
        clan_games_channel_id=None,
        maintenance_mode=True,
        timezone=pytz.utc,
        api_client=SimpleNamespace(
            get_clan=AsyncMock(return_value=None),
            get_player=AsyncMock(return_value=None),
        ),
        get_channel=AsyncMock(return_value=None),
        fetch_channel=AsyncMock(return_value=None),
        wait_until_ready=AsyncMock(),
        coc_client_ready=asyncio.Event(),
    )


def member(tag, name="Membro"):
    return SimpleNamespace(tag=tag, name=name, role=SimpleNamespace(name="Membro"))


def player(tag, points, name="Jogador"):
    def get_achievement(achievement_name, default_value=None):
        if achievement_name == "Games Champion":
            return SimpleNamespace(value=points)
        return default_value

    return SimpleNamespace(tag=tag, name=name, get_achievement=get_achievement)


def clan_of(members):
    by_tag = {m.tag: m for m in members}
    return SimpleNamespace(members=members, get_member=lambda tag: by_tag.get(tag))


def fake_interaction():
    return SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )


def sent_messages(interaction):
    return [call.args[0] for call in interaction.followup.send.call_args_list if call.args]


@pytest.fixture
def collection():
    return FakeSnapshotCollection()


@pytest.fixture
async def cog(collection):
    bot = _make_bot(collection)
    bot.coc_client_ready.set()
    instance = ClanGamesCog(bot)
    yield instance
    await instance.cog_unload()


async def test_pontos_do_novo_membro_sao_calculados(cog, collection):
    collection.docs = {"#VETERANO": {"_id": "#VETERANO", "initial_points": 1000, "name": "Veterano"}}
    veterano = member("#VETERANO", "Veterano")
    novato = member("#NOVATO", "Novato")
    cog.bot.api_client.get_clan = AsyncMock(return_value=clan_of([veterano, novato]))
    pontos = {"#VETERANO": 1400, "#NOVATO": 1500}
    cog.bot.api_client.get_player = AsyncMock(side_effect=lambda tag: player(tag, pontos[tag]))

    data = await cog.fetch_clan_games_data_for_web()

    assert "error" not in data, data
    scores = {m["tag"]: m["score"] for m in data["members"]}
    assert scores["#VETERANO"] == 400
    assert scores["#NOVATO"] == 1500, "ponto do membro novo deve ser calculado, não ignorado"
    assert data["total_points"] == 1900


async def test_snapshot_preservado_quando_coleta_falha(cog, collection):
    collection.docs = {"#VETERANO": {"_id": "#VETERANO", "initial_points": 1000, "name": "Veterano"}}
    cog.bot.api_client.get_clan = AsyncMock(side_effect=RuntimeError("API da Supercell fora do ar"))

    await cog.take_snapshot(automated=True)

    assert "#VETERANO" in collection.docs, "snapshot anterior não pode ser apagado antes da nova coleta"
    assert not any(call[0] == "delete_many" for call in collection.calls)


async def test_snapshot_renovado_quando_coleta_da_certo(cog, collection):
    collection.docs = {"#VETERANO": {"_id": "#VETERANO", "initial_points": 1000, "name": "Veterano"}}
    novo = member("#NOVO", "Novo")
    cog.bot.api_client.get_clan = AsyncMock(return_value=clan_of([novo]))
    cog.bot.api_client.get_player = AsyncMock(return_value=player("#NOVO", 300))

    await cog.take_snapshot(automated=True)

    assert any(call[0] == "delete_many" for call in collection.calls), "snapshot velho deve ser limpo após sucesso"
    assert set(collection.docs) == {"#NOVO"}
    assert collection.docs["#NOVO"]["initial_points"] == 300


async def test_snapshot_preservado_quando_nenhum_jogador_coletado(cog, collection):
    collection.docs = {"#VETERANO": {"_id": "#VETERANO", "initial_points": 1000, "name": "Veterano"}}
    cog.bot.api_client.get_clan = AsyncMock(return_value=clan_of([member("#VETERANO", "Veterano")]))
    cog.bot.api_client.get_player = AsyncMock(side_effect=RuntimeError("API da Supercell fora do ar"))

    await cog.take_snapshot(automated=True)

    assert "#VETERANO" in collection.docs, "coleta vazia não pode apagar o snapshot anterior"


async def test_cgs_iniciar_nao_envia_sucesso_em_falha(cog):
    interaction = fake_interaction()
    cog.bot.api_client.get_clan = AsyncMock(side_effect=RuntimeError("falha de rede"))

    await cog.cmd_cgs_start.callback(cog, interaction)

    mensagens = sent_messages(interaction)
    assert mensagens, "o comando precisa responder o usuário"
    assert all("✅" not in msg for msg in mensagens), "não pode reportar sucesso quando a coleta falhou"
    assert any(msg.startswith("❌") for msg in mensagens)


async def test_cgs_iniciar_envia_sucesso_quando_grava(cog, collection):
    interaction = fake_interaction()
    novo = member("#NOVO", "Novo")
    cog.bot.api_client.get_clan = AsyncMock(return_value=clan_of([novo]))
    cog.bot.api_client.get_player = AsyncMock(return_value=player("#NOVO", 300))

    await cog.cmd_cgs_start.callback(cog, interaction)

    mensagens = sent_messages(interaction)
    assert any("✅" in msg for msg in mensagens)
    assert set(collection.docs) == {"#NOVO"}


async def test_periodic_status_update_nao_morre_na_primeira_excecao(cog):
    cog.bot.maintenance_mode = False
    cog._is_snapshot_active = AsyncMock(side_effect=RuntimeError("Mongo indisponível"))

    await cog.periodic_status_update()

    assert cog.periodic_status_update.is_running()
