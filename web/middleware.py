# -*- coding: utf-8 -*-
"""
Middleware do servidor web: segurança, auth admin, CSRF, rate limiting.
"""
import logging
import os
import secrets
import time
from collections import defaultdict

from aiohttp import web
from aiohttp_session import get_session

logger = logging.getLogger("web.middleware")


class RateLimiter:
    """Rate limiter simples baseado em janela deslizante."""

    _CLEANUP_INTERVAL = 300
    _KEY_MAX_AGE = 600

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup: float = time.time()

    def _cleanup_stale_keys(self):
        now = time.time()
        if now - self._last_cleanup < self._CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        stale_keys = []
        for key, timestamps in self._requests.items():
            if not timestamps or (now - timestamps[-1]) > self._KEY_MAX_AGE:
                stale_keys.append(key)
        for key in stale_keys:
            del self._requests[key]

    def is_rate_limited(self, key: str, max_requests: int = 60, window: int = 60) -> bool:
        self._cleanup_stale_keys()
        now = time.time()
        cutoff = now - window
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]
        if len(self._requests[key]) >= max_requests:
            return True
        self._requests[key].append(now)
        return False


_rate_limiter = RateLimiter()


class RevokedSessionRegistry:
    """Registro server-side de sessões revogadas (invalidação no logout)."""

    _TTL_SECONDS = 86400

    def __init__(self):
        self._revoked: dict[str, float] = {}

    def _cleanup(self):
        now = time.time()
        expired = [sid for sid, expiry in self._revoked.items() if expiry < now]
        for sid in expired:
            del self._revoked[sid]

    def revoke(self, sid: str) -> None:
        self._cleanup()
        self._revoked[sid] = time.time() + self._TTL_SECONDS

    def is_revoked(self, sid: str) -> bool:
        self._cleanup()
        return sid in self._revoked


_revoked_sessions = RevokedSessionRegistry()


def revoke_session(session) -> None:
    """Marca a sessão atual (sid) como revogada server-side."""
    sid = session.get('sid')
    if sid:
        _revoked_sessions.revoke(sid)


def is_session_revoked(session) -> bool:
    """Verifica se a sessão carregada do cookie está revogada."""
    sid = session.get('sid')
    return bool(sid) and _revoked_sessions.is_revoked(sid)


def _trusts_proxy_headers() -> bool:
    """Só honra X-Forwarded-For quando o hop direto é um proxy confiável."""
    return (
        os.environ.get("TRUST_PROXY_HEADERS", "").strip().lower() == "true"
        or os.environ.get("RENDER", "").strip().lower() == "true"
    )


def _normalize_ip(value: str) -> str:
    """Remove portas ([ipv6]:port, ipv4:port) e brackets de IPv6."""
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("["):
        end = value.find("]")
        if end != -1:
            return value[1:end]
    if value.count(":") == 1:
        host, _, port = value.rpartition(":")
        if host and port.isdigit():
            return host
    return value


def _client_ip(request) -> str:
    """IP real do cliente atrás de proxy ou IP remoto.

    X-Forwarded-For só é honrado quando o proxy direto é confiável
    (TRUST_PROXY_HEADERS=true ou RENDER=true); nesses casos usa-se o ÚLTIMO
    hop do header (o mais próximo do cliente final visto pelo proxy confiável),
    jamais o primeiro — que um atacante pode forjar. Sem proxy confiável o
    header é ignorado e o IP usado é o da conexão direta.
    """
    if _trusts_proxy_headers():
        forwarded = request.headers.get('X-Forwarded-For', '')
        if forwarded:
            hops = [h.strip() for h in forwarded.split(',') if h.strip()]
            if hops:
                last_hop = _normalize_ip(hops[-1])
                if last_hop:
                    return last_hop
    return _normalize_ip(request.remote or '') or 'unknown'


@web.middleware
async def security_headers_middleware(request, handler):
    """Headers de segurança em todas as respostas."""
    try:
        resp = await handler(request)
    except web.HTTPException:
        raise
    except Exception:
        logger.error("Unhandled exception in handler: %s %s", request.method, request.path, exc_info=True)
        resp = web.json_response({"status": "error", "message": "Erro interno do servidor."}, status=500)
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['Referrer-Policy'] = 'same-origin'
    resp.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://akuma-labs.duckdns.org; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://akuma-labs.duckdns.org; "
        "frame-ancestors 'none'"
    )
    return resp


@web.middleware
async def rate_limit_middleware(request, handler):
    """Rate limiting global: 60 req/min por IP, 10 req/min para login/registro."""
    client_ip = _client_ip(request)
    path = request.path

    if path in ('/api/admin/auth/login', '/api/admin/auth/register'):
        max_requests, window = 10, 60
    elif path.startswith('/api/'):
        max_requests, window = 120, 60
    else:
        max_requests, window = 200, 60

    key = f"{client_ip}:{path}"
    if _rate_limiter.is_rate_limited(key, max_requests, window):
        logger.warning("Rate limit exceeded: %s from %s", path, client_ip)
        return web.json_response(
            {"status": "error", "message": "Rate limit excedido. Tente novamente mais tarde."},
            status=429
        )
    return await handler(request)


_VIEWER_ALLOWED_PATHS = (
    '/api/admin/auth/me',
    '/api/admin/auth/session-info',
    '/api/admin/csrf_token',
)


@web.middleware
async def admin_auth_middleware(request, handler):
    """Verifica autenticação para rotas admin."""
    if request.path in ('/api/admin/auth/login', '/api/admin/auth/register', '/api/admin/auth/change-password', '/api/admin/auth/forgot-password') or request.path.startswith('/api/admin/auth/login/'):
        return await handler(request)
    session = await get_session(request)
    if is_session_revoked(session):
        return web.json_response({"status": "unauthorized", "message": "Sessão encerrada. Entre novamente."}, status=401)
    role = session.get('role')
    if not role and not session.get('admin'):
        # Allow password change flow with limited session
        if request.path == '/api/admin/auth/change-password' and session.get('password_change_required'):
            return await handler(request)
        return web.json_response({"status": "unauthorized", "message": "Acesso negado."}, status=403)
    if role == 'viewer' and request.path not in _VIEWER_ALLOWED_PATHS:
        return web.json_response({"status": "forbidden", "message": "Membro Sênior não tem acesso."}, status=403)
    return await handler(request)


@web.middleware
async def admin_csrf_middleware(request, handler):
    """Valida CSRF token em mutations admin."""
    if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
        return await handler(request)
    if request.path in ('/api/admin/auth/login', '/api/admin/auth/register', '/api/admin/auth/forgot-password'):
        return await handler(request)
    session = await get_session(request)
    csrf_token = session.get('csrf_token')
    if not csrf_token:
        return web.json_response({"status": "error", "message": "CSRF token não encontrado."}, status=403)
    request_csrf = request.headers.get('X-CSRF-Token', '')
    if not request_csrf or not secrets.compare_digest(request_csrf, csrf_token):
        return web.json_response({"status": "error", "message": "CSRF token inválido."}, status=403)
    return await handler(request)
