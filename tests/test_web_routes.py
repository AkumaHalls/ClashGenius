# -*- coding: utf-8 -*-
"""Testes da LANE 1 — FIX-23: validação de player tag e cadeia de middlewares."""
import asyncio
import base64
import os

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from aiohttp_session import get_session
from aiohttp_session import setup as setup_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from web.middleware import rate_limit_middleware, security_headers_middleware
from web.routes import register_public_routes

CORPO_UNIVERSAL = {"text": "nota", "priority": "none", "status": "active", "enabled": True}

TAGS_INVALIDAS = [
    ("get", "/api/player_profile/!!!"),
    ("get", "/api/player_upgrades/!!!"),
    ("post", "/api/notes/!!!"),
    ("post", "/api/cwl/player_status/!!!"),
    ("post", "/api/admin_border/!!!"),
]


class _FakeWebApiCog:
    async def fetch_player_upgrades_for_web(self, player_tag):
        return {"tag": player_tag}


class _FakeProfileCog:
    async def fetch_player_profile_data(self, player_tag):
        if player_tag == "#FAILTHIS":
            raise RuntimeError("falha simulada")
        return {"tag": player_tag}


class _FakeDbCog:
    async def save_player_note_to_db(self, *args, **kwargs):
        return None

    async def update_player_cwl_status(self, *args, **kwargs):
        return None

    async def update_player_admin_border(self, *args, **kwargs):
        return None


class _FakeBot:
    def __init__(self):
        self.web_api_cache = {}
        self.WEB_API_CACHE_DURATION_SECONDS = 60
        self._WEB_API_CACHE_MAXSIZE = 100
        self.maintenance_mode = False
        self.maintenance_message = "Manutencao de teste"
        self.bot_version = "0.0.0-test"
        self.coc_client_ready = asyncio.Event()
        self.coc_client_ready.set()
        self.api_client = object()
        self.db = None
        self._cogs = {
            "Web API": _FakeWebApiCog(),
            "Perfis de Membros": _FakeProfileCog(),
            "Banco de Dados": _FakeDbCog(),
        }

    def get_cog(self, name):
        return self._cogs.get(name)


def _make_app():
    app = web.Application()
    app.middlewares.append(security_headers_middleware)
    app.middlewares.append(rate_limit_middleware)

    async def seed(request):
        session = await get_session(request)
        session["role"] = "admin"
        return web.json_response({"status": "ok"})

    async def seed_viewer(request):
        session = await get_session(request)
        session["role"] = "viewer"
        return web.json_response({"status": "ok"})

    app.router.add_get("/_seed_admin", seed)
    app.router.add_get("/_seed_viewer", seed_viewer)
    register_public_routes(app, _FakeBot())
    fernet_key = base64.urlsafe_b64decode(os.environ["FERNET_KEY"].encode())
    setup_session(app, EncryptedCookieStorage(fernet_key, max_age=86400))
    return app


async def _autenticado(client):
    resp = await client.get("/_seed_admin")
    assert resp.status == 200


@pytest.mark.parametrize("metodo,caminho", TAGS_INVALIDAS)
async def test_tag_malformada_retorna_400(metodo, caminho):
    async with TestClient(TestServer(_make_app())) as client:
        await _autenticado(client)
        if metodo == "get":
            resp = await client.get(caminho)
        else:
            resp = await client.post(caminho, json=CORPO_UNIVERSAL)
        assert resp.status == 400
        dados = await resp.json()
        assert dados["status"] == "error"
        assert dados["message"] == "Tag de jogador inválida."


async def test_tag_valida_e_normalizada_nos_cinco_handlers():
    async with TestClient(TestServer(_make_app())) as client:
        await _autenticado(client)

        resp = await client.get("/api/player_profile/abc-123")
        assert resp.status == 200
        assert (await resp.json())["tag"] == "#ABC123"

        resp = await client.get("/api/player_upgrades/abc-123")
        assert resp.status == 200
        assert (await resp.json())["tag"] == "#ABC123"

        resp = await client.post("/api/notes/abc-123", json=CORPO_UNIVERSAL)
        assert resp.status == 204

        resp = await client.post("/api/cwl/player_status/abc-123", json=CORPO_UNIVERSAL)
        assert resp.status == 200
        dados = await resp.json()
        assert dados["status"] == "success"
        assert "#ABC123" in dados["message"]

        resp = await client.post("/api/admin_border/abc-123", json=CORPO_UNIVERSAL)
        assert resp.status == 200
        dados = await resp.json()
        assert dados["status"] == "success"
        assert "#ABC123" in dados["message"]


async def test_viewer_nao_salva_nota_de_jogador():
    async with TestClient(TestServer(_make_app())) as client:
        resp = await client.get("/_seed_viewer")
        assert resp.status == 200
        resp = await client.post("/api/notes/abc-123", json=CORPO_UNIVERSAL)
        assert resp.status == 403
        dados = await resp.json()
        assert dados["status"] == "error"


async def test_viewer_nao_atualiza_status_cwl():
    async with TestClient(TestServer(_make_app())) as client:
        resp = await client.get("/_seed_viewer")
        assert resp.status == 200
        resp = await client.post("/api/cwl/player_status/abc-123", json=CORPO_UNIVERSAL)
        assert resp.status == 403
        dados = await resp.json()
        assert dados["status"] == "error"


async def test_erro_na_handler_de_player_tag_vira_500_padrao():
    async with TestClient(TestServer(_make_app())) as client:
        resp = await client.get("/api/player_profile/FAILTHIS")
        assert resp.status == 500
        dados = await resp.json()
        assert dados["status"] == "error"
        assert dados["message"] == "Erro interno do servidor."
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["X-Content-Type-Options"] == "nosniff"


async def test_cadeia_de_middlewares_cobre_respostas_de_player_tag():
    async with TestClient(TestServer(_make_app())) as client:
        await _autenticado(client)

        resp = await client.get("/api/player_profile/abc-123")
        assert resp.status == 200
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert "Content-Security-Policy" in resp.headers

        resp = await client.get("/api/player_profile/!!!")
        assert resp.status == 400
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
