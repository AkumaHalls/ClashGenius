# -*- coding: utf-8 -*-
"""Testes da LANE 1 (Segurança Web): rate limit por IP real, papel viewer,
logout com sessão server-side e rotação de sessão na senha mestre."""
import base64
import os
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from aiohttp_session import get_session
from aiohttp_session import setup as setup_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage

from config import redact_mongo_uri
from web.admin_routes import register_admin_routes
from web.auth import hash_password
from web.auth_routes import register_auth_routes
from web.middleware import (
    RateLimiter,
    admin_auth_middleware,
    admin_csrf_middleware,
    rate_limit_middleware,
)

STATIC_DIR = str(Path(__file__).resolve().parents[1] / "static")


def _setup_sessions(app):
    fernet_key = base64.urlsafe_b64decode(os.environ["FERNET_KEY"].encode())
    setup_session(app, EncryptedCookieStorage(fernet_key, max_age=86400))


# ---------------------------------------------------------------------------
# FIX-07a: rate limit usa X-Forwarded-For como chave (proxy Render)
# ---------------------------------------------------------------------------

@pytest.fixture
def sem_proxy_confiavel(monkeypatch):
    monkeypatch.delenv("TRUST_PROXY_HEADERS", raising=False)
    monkeypatch.delenv("RENDER", raising=False)


@pytest.fixture
def proxy_confiavel(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")


@web.middleware
async def _stub_api_middleware(request, handler):
    return await handler(request)


def _rate_limit_app():
    app = web.Application()
    app.middlewares.append(rate_limit_middleware)

    async def ok(request):
        return web.json_response({"status": "ok"})

    app.router.add_post("/api/admin/auth/login", ok)
    return app


@pytest.fixture
def rate_limiter_limpo(monkeypatch):
    limiter = RateLimiter()
    monkeypatch.setattr("web.middleware._rate_limiter", limiter)
    return limiter


async def test_xff_forjado_sem_proxy_confiavel_eh_ignorado(rate_limiter_limpo, sem_proxy_confiavel):
    # Sem proxy confiável, o X-Forwarded-For é ignorado: todos compartilham o
    # bucket do IP remoto, mesmo que o header seja forjado com IPs diferentes.
    async with TestClient(TestServer(_rate_limit_app())) as client:
        for i in range(10):
            resp = await client.post("/api/admin/auth/login", headers={"X-Forwarded-For": f"203.0.113.{i + 1}"})
            assert resp.status == 200
        resp = await client.post("/api/admin/auth/login", headers={"X-Forwarded-For": "198.51.100.9"})
        assert resp.status == 429


async def test_xff_ultimo_hop_com_proxy_confiavel_manda_no_bucket(rate_limiter_limpo, proxy_confiavel):
    # Com proxy confiável, o ÚLTIMO hop do XFF é o IP do cliente: forjar o
    # PRIMEIRO elemento não cria bucket novo.
    async with TestClient(TestServer(_rate_limit_app())) as client:
        for _ in range(10):
            resp = await client.post("/api/admin/auth/login", headers={"X-Forwarded-For": "203.0.113.7, 10.0.0.1"})
            assert resp.status == 200
        resp = await client.post("/api/admin/auth/login", headers={"X-Forwarded-For": "198.51.100.9, 10.0.0.1"})
        assert resp.status == 429
        resp = await client.post("/api/admin/auth/login", headers={"X-Forwarded-For": "198.51.100.9, 10.0.0.2"})
        assert resp.status == 200


async def test_xff_com_proxy_confiavel_remove_porta_do_ultimo_hop(rate_limiter_limpo, proxy_confiavel):
    async with TestClient(TestServer(_rate_limit_app())) as client:
        for _ in range(5):
            resp = await client.post("/api/admin/auth/login", headers={"X-Forwarded-For": "10.0.0.5:4444"})
            assert resp.status == 200
        for _ in range(5):
            resp = await client.post("/api/admin/auth/login", headers={"X-Forwarded-For": "10.0.0.5:5555"})
            assert resp.status == 200
        resp = await client.post("/api/admin/auth/login", headers={"X-Forwarded-For": "10.0.0.5"})
        assert resp.status == 429


async def test_xff_com_proxy_confiavel_normaliza_ipv6(rate_limiter_limpo, proxy_confiavel):
    async with TestClient(TestServer(_rate_limit_app())) as client:
        for _ in range(5):
            resp = await client.post("/api/admin/auth/login", headers={"X-Forwarded-For": "[2001:db8::1]:8080"})
            assert resp.status == 200
        for _ in range(5):
            resp = await client.post("/api/admin/auth/login", headers={"X-Forwarded-For": "[2001:db8::1]:9090"})
            assert resp.status == 200
        resp = await client.post("/api/admin/auth/login", headers={"X-Forwarded-For": "2001:db8::1"})
        assert resp.status == 429


async def test_sem_xff_usa_ip_remoto(rate_limiter_limpo, sem_proxy_confiavel):
    async with TestClient(TestServer(_rate_limit_app())) as client:
        for _ in range(10):
            resp = await client.post("/api/admin/auth/login")
            assert resp.status == 200
        resp = await client.post("/api/admin/auth/login")
        assert resp.status == 429


# ---------------------------------------------------------------------------
# FIX-07b: viewer bloqueado em TODOS os métodos nos endpoints admin
# ---------------------------------------------------------------------------

def _viewer_app():
    app = web.Application()
    _setup_sessions(app)

    async def seed(request):
        session = await get_session(request)
        session["role"] = "viewer"
        session["csrf_token"] = "token-de-teste"
        return web.json_response({"status": "ok"})

    async def status_publico(request):
        return web.json_response({"status": "ok"})

    app.router.add_get("/_seed_viewer", seed)
    app.router.add_get("/api/status", status_publico)

    admin_app = web.Application(middlewares=[admin_auth_middleware, admin_csrf_middleware])

    async def ok(request):
        return web.json_response({"status": "ok"})

    admin_app.router.add_get("/diagnostics", ok)
    admin_app.router.add_get("/auth/me", ok)
    admin_app.router.add_post("/actions", ok)
    app.add_subapp("/api/admin/", admin_app)
    return app


async def test_viewer_get_endpoint_admin_recebe_403():
    async with TestClient(TestServer(_viewer_app())) as client:
        await client.get("/_seed_viewer")
        resp = await client.get("/api/admin/diagnostics")
        assert resp.status == 403
        dados = await resp.json()
        assert dados["status"] == "forbidden"


async def test_viewer_post_endpoint_admin_recebe_403():
    async with TestClient(TestServer(_viewer_app())) as client:
        await client.get("/_seed_viewer")
        resp = await client.post("/api/admin/actions", json={"action": "clear_cache"})
        assert resp.status == 403


async def test_visitante_sem_sessao_recebe_403():
    async with TestClient(TestServer(_viewer_app())) as client:
        resp = await client.get("/api/admin/diagnostics")
        assert resp.status == 403


async def test_viewer_rotas_permitidas_continuam_ok():
    async with TestClient(TestServer(_viewer_app())) as client:
        await client.get("/_seed_viewer")
        resp = await client.get("/api/admin/auth/me")
        assert resp.status == 200
        resp = await client.get("/api/status")
        assert resp.status == 200


# ---------------------------------------------------------------------------
# FIX-07c: /admin/toggle_maintenance e /admin/send_test_embed bloqueiam viewer
# ---------------------------------------------------------------------------

class _FakeMaintenanceCog:
    async def toggle_maintenance_mode_web(self):
        return web.json_response({"status": "success"})

    async def send_test_embed_web(self):
        return web.json_response({"status": "success"})


def _maintenance_app():
    app = web.Application()
    _setup_sessions(app)

    class BotComManutencao(_FakeBot):
        def get_cog(self, name):
            if name == "Manutenção do Sistema":
                return _FakeMaintenanceCog()
            return None

    async def seed(request):
        session = await get_session(request)
        session["role"] = request.query.get("role", "admin")
        session["username"] = "alguem"
        session["csrf_token"] = "token-de-teste"
        return web.json_response({"status": "ok"})

    app.router.add_get("/_seed", seed)
    app.router.add_get("/_csrf", lambda r: web.json_response({"csrf_token": "token-de-teste"}))
    register_admin_routes(app, app, BotComManutencao(), STATIC_DIR)
    return app


async def test_viewer_nao_alterna_manutencao():
    async with TestClient(TestServer(_maintenance_app())) as client:
        await client.get("/_seed?role=viewer")
        resp = await client.post("/admin/toggle_maintenance", headers={"X-CSRF-Token": "token-de-teste"})
        assert resp.status == 403


async def test_viewer_nao_envia_test_embed():
    async with TestClient(TestServer(_maintenance_app())) as client:
        await client.get("/_seed?role=viewer")
        resp = await client.post("/admin/send_test_embed", headers={"X-CSRF-Token": "token-de-teste"})
        assert resp.status == 403


async def test_admin_alterna_manutencao_com_csrf():
    async with TestClient(TestServer(_maintenance_app())) as client:
        await client.get("/_seed?role=admin")
        resp = await client.post("/admin/toggle_maintenance", headers={"X-CSRF-Token": "token-de-teste"})
        assert resp.status == 200
        assert (await resp.json())["status"] == "success"


async def test_admin_envia_test_embed_sem_csrf_recebe_403():
    async with TestClient(TestServer(_maintenance_app())) as client:
        await client.get("/_seed?role=admin")
        resp = await client.post("/admin/send_test_embed")
        assert resp.status == 403


# ---------------------------------------------------------------------------
# FIX-07d: forgot-password está na allowlist (o login chama o endpoint sem sessão)
# ---------------------------------------------------------------------------

def _forgot_password_app():
    app = web.Application()
    _setup_sessions(app)
    admin_app = web.Application(middlewares=[admin_auth_middleware, admin_csrf_middleware])

    async def ok(request):
        return web.json_response({"status": "success"})

    admin_app.router.add_post("/auth/forgot-password", ok)
    app.add_subapp("/api/admin/", admin_app)
    return app


async def test_forgot_password_sem_sessao_nao_recebe_403():
    async with TestClient(TestServer(_forgot_password_app())) as client:
        resp = await client.post("/api/admin/auth/forgot-password", json={"username": "alguem"})
        assert resp.status == 200
        assert (await resp.json())["status"] == "success"


# ---------------------------------------------------------------------------
# Helpers para FIX-08a / FIX-08b (rotas admin reais de web/admin_routes.py)
# ---------------------------------------------------------------------------

class _FakePanelUsers:
    def __init__(self, total):
        self._total = total

    async def count_documents(self, query):
        return self._total


class _FakeDB:
    def __init__(self):
        self.panel_users = _FakePanelUsers(total=1)


class _FakeBot:
    def __init__(self):
        self.db = _FakeDB()
        self.web_api_cache = {}
        self.maintenance_mode = False
        self.maintenance_message = "Manutencao de teste"
        self.bot_version = "0.0.0-test"

    def get_cog(self, name):
        return None


def _admin_app():
    app = web.Application()
    _setup_sessions(app)

    async def seed(request):
        session = await get_session(request)
        session["sid"] = "sessao-antiga-fixa"
        session["role"] = "viewer"
        session["username"] = "alguem"
        session["csrf_token"] = "token-antigo"
        return web.json_response({"status": "ok"})

    async def whoami(request):
        session = await get_session(request)
        return web.json_response({
            "sid": session.get("sid"),
            "role": session.get("role"),
            "username": session.get("username"),
        })

    app.router.add_get("/_seed", seed)
    app.router.add_get("/_whoami", whoami)

    admin_app = web.Application(middlewares=[admin_auth_middleware, admin_csrf_middleware])

    async def me(request):
        return web.json_response({"status": "ok"})

    admin_app.router.add_get("/auth/me", me)
    register_admin_routes(admin_app, app, _FakeBot(), STATIC_DIR)
    app.add_subapp("/api/admin/", admin_app)
    return app


# ---------------------------------------------------------------------------
# FIX-08b: login com senha mestre rotaciona a sessão e reatribui identidade
# ---------------------------------------------------------------------------

async def test_login_senha_mestre_rotaciona_sessao_e_reatribui_identidade():
    async with TestClient(TestServer(_admin_app())) as client:
        await client.get("/_seed")
        resp = await client.post("/admin/login", data={"password": os.environ["ADMIN_PASSWORD"]}, allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin/panel"
        dados = await (await client.get("/_whoami")).json()
        assert dados["role"] == "admin"
        assert dados["username"] == "root"
        assert dados["sid"]
        assert dados["sid"] != "sessao-antiga-fixa"


async def test_login_senha_mestre_em_sessao_nova_cria_session_id():
    async with TestClient(TestServer(_admin_app())) as client:
        resp = await client.post("/admin/login", data={"password": os.environ["ADMIN_PASSWORD"]}, allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin/panel"
        dados = await (await client.get("/_whoami")).json()
        assert dados["role"] == "admin"
        assert dados["sid"]


async def test_login_senha_incorreta_nao_altera_sessao():
    async with TestClient(TestServer(_admin_app())) as client:
        await client.get("/_seed")
        resp = await client.post("/admin/login", data={"password": "senha-errada"}, allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin?error=1"
        dados = await (await client.get("/_whoami")).json()
        assert dados["role"] == "viewer"
        assert dados["sid"] == "sessao-antiga-fixa"


# ---------------------------------------------------------------------------
# FIX-08a: logout apaga a sessão server-side e expira o cookie
# ---------------------------------------------------------------------------

async def test_logout_expira_cookie_da_sessao():
    async with TestClient(TestServer(_admin_app())) as client:
        resp = await client.post("/admin/login", data={"password": os.environ["ADMIN_PASSWORD"]}, allow_redirects=False)
        assert resp.status == 302
        assert resp.cookies["AIOHTTP_SESSION"].value

        resp = await client.get("/admin/logout", allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin"
        assert resp.cookies["AIOHTTP_SESSION"].value == ""


async def test_cookie_anterior_ao_logout_eh_rejeitado():
    async with TestClient(TestServer(_admin_app())) as client:
        resp = await client.post("/admin/login", data={"password": os.environ["ADMIN_PASSWORD"]}, allow_redirects=False)
        cookie_antigo = resp.cookies["AIOHTTP_SESSION"].value
        assert cookie_antigo

        resp = await client.get("/admin/logout", allow_redirects=False)
        assert resp.status == 302
        client.session.cookie_jar.clear()
        header = {"Cookie": f'AIOHTTP_SESSION="{cookie_antigo}"'}

        resp = await client.get("/admin/panel", headers=header, allow_redirects=False)
        assert resp.status == 302
        assert resp.headers["Location"] == "/admin"

        resp = await client.get("/api/admin/auth/me", headers=header)
        assert resp.status == 401


# ---------------------------------------------------------------------------
# FIX-08c: login COMUM (usuário do painel) também rotaciona sessão e seta 'sid'
# ---------------------------------------------------------------------------

class _PanelUsersStore:
    def __init__(self, users):
        self._users = users

    async def find_one(self, filter_, projection=None):
        user = self._users.get(filter_.get("_id"))
        if user is None:
            return None
        if not projection:
            return dict(user)
        out = {}
        for key in projection:
            if key in user:
                out[key] = user[key]
        return out

    async def update_one(self, filter_, update):
        uid = filter_.get("_id")
        if uid in self._users:
            self._users[uid].update(update.get("$set", {}))
        return None

    async def count_documents(self, query):
        return 1


class _FakeBotComLogin:
    def __init__(self):
        self.web_api_cache = {}
        self.maintenance_mode = False
        self.maintenance_message = "Manutencao de teste"
        self.bot_version = "0.0.0-test"
        self.db = type("_DB", (), {
            "panel_users": _PanelUsersStore({
                "alguem": {
                    "_id": "alguem",
                    "password_hash": hash_password("senha-legal"),
                    "role": "admin",
                    "status": "active",
                },
            }),
        })()

    def get_cog(self, name):
        return None


def _login_comum_app():
    app = web.Application()
    _setup_sessions(app)

    async def whoami(request):
        session = await get_session(request)
        return web.json_response({
            "sid": session.get("sid"),
            "role": session.get("role"),
            "username": session.get("username"),
        })

    app.router.add_get("/_whoami", whoami)
    admin_app = web.Application(middlewares=[admin_auth_middleware, admin_csrf_middleware])
    bot = _FakeBotComLogin()
    register_auth_routes(admin_app, bot)
    register_admin_routes(admin_app, app, bot, STATIC_DIR)
    app.add_subapp("/api/admin/", admin_app)
    return app


async def test_login_comum_cria_session_id():
    async with TestClient(TestServer(_login_comum_app())) as client:
        resp = await client.post("/api/admin/auth/login", json={"username": "alguem", "password": "senha-legal"})
        assert resp.status == 200
        dados = await resp.json()
        assert dados["status"] == "success"
        whoami = await (await client.get("/_whoami")).json()
        assert whoami["role"] == "admin"
        assert whoami["sid"]


async def test_logout_apos_login_comum_rejeita_cookie_antigo():
    async with TestClient(TestServer(_login_comum_app())) as client:
        resp = await client.post("/api/admin/auth/login", json={"username": "alguem", "password": "senha-legal"})
        assert resp.status == 200
        cookie_antigo = resp.cookies["AIOHTTP_SESSION"].value
        assert cookie_antigo

        resp = await client.get("/admin/logout", allow_redirects=False)
        assert resp.status == 302
        client.session.cookie_jar.clear()
        header = {"Cookie": f'AIOHTTP_SESSION="{cookie_antigo}"'}

        resp = await client.get("/api/admin/auth/me", headers=header)
        assert resp.status == 401


# ---------------------------------------------------------------------------
# FIX-L1: redact_mongo_uri não vaza credenciais com @ ou / na senha
# ---------------------------------------------------------------------------

async def test_redact_mongo_uri_arroba_na_senha_mongodb_srv():
    assert redact_mongo_uri("mongodb+srv://user:p@ss@host/db") == "mongodb+srv://***:***@host/db"


async def test_redact_mongo_uri_barra_na_senha():
    assert redact_mongo_uri("mongodb://user:pa/ss@host/db") == "mongodb://***:***@host/db"


async def test_redact_mongo_uri_sem_credenciais_nao_altera():
    assert redact_mongo_uri("mongodb://host:27017/db") == "mongodb://host:27017/db"


async def test_redact_mongo_uri_simples():
    assert redact_mongo_uri("mongodb://user:pass@host") == "mongodb://***:***@host"

