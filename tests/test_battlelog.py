# -*- coding: utf-8 -*-
"""Testes do BattleLogCog (FIX-14: erros honestos, fuso horário e db_ready)."""
import asyncio
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytz
import pytest
from geniuslib import NotFound

from cogs import battlelog_cog
from cogs.battlelog_cog import BattleLogCog

FUSO = pytz.timezone("America/Sao_Paulo")


class _DataSemFuso(datetime.date):
    @classmethod
    def today(cls):
        raise AssertionError("date.today() sem fuso horário foi usado")


def _datetime_com_data_proibida():
    return SimpleNamespace(
        date=_DataSemFuso,
        datetime=datetime.datetime,
        timedelta=datetime.timedelta,
        time=datetime.time,
    )


def _http_response():
    return SimpleNamespace(status=404, reason="Not Found")


def _make_bot():
    return SimpleNamespace(
        db=SimpleNamespace(battle_logs=SimpleNamespace()),
        clan_tag="#TAGCLAN",
        channel_id=1,
        maintenance_mode=True,
        timezone=FUSO,
        bot_version="test",
        user=SimpleNamespace(name="Bot"),
        db_ready=asyncio.Event(),
        coc_client_ready=asyncio.Event(),
        api_client=SimpleNamespace(
            get_clan=AsyncMock(return_value=None),
            get_player=AsyncMock(return_value=None),
            get_player_battlelog=AsyncMock(return_value=[]),
            get_player_league_history=AsyncMock(return_value=[]),
        ),
        get_channel=AsyncMock(return_value=None),
        fetch_channel=AsyncMock(return_value=None),
        wait_until_ready=AsyncMock(),
    )


def fake_interaction():
    return SimpleNamespace(
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )


def sent_messages(interaction):
    return [call.args[0] for call in interaction.followup.send.call_args_list if call.args]


@pytest.fixture
async def cog():
    bot = _make_bot()
    bot.db_ready.set()
    bot.coc_client_ready.set()
    instance = BattleLogCog(bot)
    yield instance
    instance.cog_unload()


async def test_legend_erro_na_consulta_nao_vira_nao_encontrado(cog):
    interaction = fake_interaction()
    cog.bot.api_client.get_player = AsyncMock(return_value=SimpleNamespace(tag="#TAG", name="Jogador"))
    cog.bot.api_client.get_player_battlelog = AsyncMock(side_effect=RuntimeError("503 da API"))

    await cog.cmd_legend.callback(cog, interaction, "#TAG")

    mensagens = sent_messages(interaction)
    assert mensagens, "o comando precisa responder o usuário"
    assert all("Nenhum battle log" not in msg for msg in mensagens)
    assert all("não encontrado" not in msg for msg in mensagens)
    assert any("Erro ao consultar" in msg for msg in mensagens)


async def test_legend_erro_no_jogador_nao_diz_nao_encontrado(cog):
    interaction = fake_interaction()
    cog.bot.api_client.get_player = AsyncMock(side_effect=RuntimeError("timeout na API"))

    await cog.cmd_legend.callback(cog, interaction, "#TAG")

    mensagens = sent_messages(interaction)
    assert mensagens
    assert all("não encontrado" not in msg for msg in mensagens)
    assert any("Erro ao consultar" in msg for msg in mensagens)


async def test_legend_jogador_desconhecido_diz_nao_encontrado(cog):
    interaction = fake_interaction()
    cog.bot.api_client.get_player = AsyncMock(side_effect=NotFound(_http_response(), "Not Found"))

    await cog.cmd_legend.callback(cog, interaction, "#TAG")

    mensagens = sent_messages(interaction)
    assert any("não encontrado" in msg for msg in mensagens)


async def test_legend_historico_erro_consulta_honesto(cog):
    interaction = fake_interaction()
    cog.bot.api_client.get_player = AsyncMock(return_value=SimpleNamespace(tag="#TAG", name="Jogador"))
    cog.bot.api_client.get_player_league_history = AsyncMock(side_effect=RuntimeError("503 da API"))

    await cog.cmd_legend_historico.callback(cog, interaction, "#TAG")

    mensagens = sent_messages(interaction)
    assert mensagens
    assert all("Nenhum histórico" not in msg for msg in mensagens)
    assert any("Erro ao consultar" in msg for msg in mensagens)


async def test_legend_exercitos_erro_consulta_honesto(cog):
    interaction = fake_interaction()
    cog.bot.api_client.get_player = AsyncMock(return_value=SimpleNamespace(tag="#TAG", name="Jogador"))
    cog.bot.api_client.get_player_battlelog = AsyncMock(side_effect=RuntimeError("503 da API"))

    await cog.cmd_legend_exercitos.callback(cog, interaction, "#TAG")

    mensagens = sent_messages(interaction)
    assert mensagens
    assert all("Nenhum battle log" not in msg for msg in mensagens)
    assert any("Erro ao consultar" in msg for msg in mensagens)


async def test_legend_resumo_erro_consulta_honesto(cog):
    interaction = fake_interaction()
    lendario = SimpleNamespace(tag="#L", name="Lendario", league=SimpleNamespace(name="Legend League"))
    cog.bot.api_client.get_clan = AsyncMock(return_value=SimpleNamespace(members=[lendario]))
    cog.bot.api_client.get_player_battlelog = AsyncMock(side_effect=RuntimeError("503 da API"))

    await cog.cmd_legend_resumo.callback(cog, interaction, 1)

    mensagens = sent_messages(interaction)
    assert mensagens
    assert all("Nenhum battle log" not in msg for msg in mensagens)
    assert any("Erro ao consultar" in msg for msg in mensagens)


async def test_legend_resumo_usa_fuso_horario(cog, monkeypatch):
    interaction = fake_interaction()
    lendario = SimpleNamespace(tag="#L", name="Lendario", league=SimpleNamespace(name="Legend League"))
    cog.bot.api_client.get_clan = AsyncMock(return_value=SimpleNamespace(members=[lendario]))
    cog.bot.api_client.get_player_battlelog = AsyncMock(return_value=[object()])

    capturado = {}

    def _resumo(entries, start_date, end_date):
        capturado["start"] = start_date
        capturado["end"] = end_date
        return {
            "attacks": {"total_attacks": 1, "avg_stars": 1.0},
            "win_rate": 50.0,
            "defenses": {"total_defenses": 0, "wins": 0, "losses": 0},
            "loot": {"total_gold": 0, "total_elixir": 0, "total_dark": 0},
        }

    monkeypatch.setattr(battlelog_cog, "battle_period_summary", _resumo)
    monkeypatch.setattr(battlelog_cog, "datetime", _datetime_com_data_proibida())

    await cog.cmd_legend_resumo.callback(cog, interaction, 1)

    assert capturado, "o resumo do período deve ser calculado"
    hoje = datetime.datetime.now(FUSO).date()
    assert capturado["end"] == hoje
    assert capturado["start"] == hoje - datetime.timedelta(days=1)


async def test_on_ready_sem_db_nao_inicia_tasks():
    bot = _make_bot()
    bot.db = None
    bot.db_ready.set()
    bot.coc_client_ready.set()
    instance = BattleLogCog(bot)
    try:
        await instance.on_ready()

        assert instance.tasks_started is False, "sem banco de dados as tasks não podem ser iniciadas"
        assert not instance.snapshot_battle_logs_task.is_running()
        assert not instance.daily_legend_report_task.is_running()
    finally:
        instance.cog_unload()
