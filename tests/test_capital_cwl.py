# -*- coding: utf-8 -*-
"""Testes do CapitalCog (FIX-17b: /gerar_cwl com resposta honesta e sem NotFound)."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytz
import pytest

from cogs.capital_cog import CapitalCog


def _http_response():
    return SimpleNamespace(status=404, reason="Not Found")


def _make_bot():
    canal = SimpleNamespace(send=AsyncMock())
    return SimpleNamespace(
        db=None,
        clan_tag="#TAGCLAN",
        capital_report_channel_id=4242,
        maintenance_mode=True,
        timezone=pytz.utc,
        api_client=SimpleNamespace(
            get_clan=AsyncMock(return_value=None),
            get_raid_log=AsyncMock(return_value=None),
            get_league_group=AsyncMock(return_value=None),
        ),
        get_channel=lambda channel_id: canal,
        fetch_channel=AsyncMock(return_value=canal),
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
    instance = CapitalCog(_make_bot())
    yield instance
    await instance.cog_unload()


async def test_gerar_cwl_nao_propaga_not_found(cog):
    interaction = fake_interaction()
    interaction.followup.send = AsyncMock(side_effect=discord.NotFound(_http_response(), "Unknown Webhook"))
    cog._process_and_send_cwl = AsyncMock(return_value=None)

    await cog.cmd_gerar_cwl.callback(cog, interaction)

    assert interaction.followup.send.await_count == 1


async def test_gerar_cwl_erro_nao_envia_check(cog, monkeypatch):
    interaction = fake_interaction()
    monkeypatch.setattr(cog, "_ensure_font_exists", AsyncMock())
    cog.fetch_cwl_data = AsyncMock(return_value={"error": "Nenhum grupo CWL ativo."})

    await cog.cmd_gerar_cwl.callback(cog, interaction)

    mensagens = sent_messages(interaction)
    assert mensagens, "o comando precisa responder o usuário"
    assert all("✅" not in msg for msg in mensagens), "não pode reportar sucesso quando a geração falhou"
    assert any(msg.startswith("❌") for msg in mensagens)


async def test_process_cwl_reporta_falha_ao_chamador(cog, monkeypatch):
    monkeypatch.setattr(cog, "_ensure_font_exists", AsyncMock())
    cog.fetch_cwl_data = AsyncMock(return_value={"error": "Nenhum grupo CWL ativo."})

    resultado = await cog._process_and_send_cwl(automated=False)

    assert resultado, "a falha deve ser reportada ao chamador (e não silenciada)"


async def test_gerar_cwl_sucesso_envia_check(cog):
    interaction = fake_interaction()
    cog._process_and_send_cwl = AsyncMock(return_value=None)

    await cog.cmd_gerar_cwl.callback(cog, interaction)

    mensagens = sent_messages(interaction)
    assert any("✅" in msg for msg in mensagens)
    assert all(not msg.startswith("❌") for msg in mensagens)
