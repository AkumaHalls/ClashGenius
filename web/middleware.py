# -*- coding: utf-8 -*-
"""
Middleware do servidor web: segurança, auth admin, CSRF, rate limiting.
"""
import time
import secrets
import logging
from collections import defaultdict

from aiohttp import web
from aiohttp_session import get_session

logger = logging.getLogger("web.middleware")


class RateLimiter:
    """Rate limiter simples baseado em janela deslizante."""

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_rate_limited(self, key: str, max_requests: int = 60, window: int = 60) -> bool:
        now = time.time()
        cutoff = now - window
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]
        if len(self._requests[key]) >= max_requests:
            return True
        self._requests[key].append(now)
        return False


_rate_limiter = RateLimiter()


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
    client_ip = request.remote or 'unknown'
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


@web.middleware
async def admin_auth_middleware(request, handler):
    """Verifica autenticação para rotas admin."""
    if request.path in ('/api/admin/auth/login', '/api/admin/auth/register') or request.path.startswith('/api/admin/auth/login/'):
        return await handler(request)
    session = await get_session(request)
    role = session.get('role')
    if not role and not session.get('admin'):
        return web.json_response({"status": "unauthorized", "message": "Acesso negado."}, status=403)
    if role == 'viewer' and request.method == 'POST':
        return web.json_response({"status": "forbidden", "message": "Membro Sênior não pode modificar."}, status=403)
    return await handler(request)


@web.middleware
async def admin_csrf_middleware(request, handler):
    """Valida CSRF token em mutations admin."""
    if request.method in ('GET', 'HEAD', 'OPTIONS', 'TRACE'):
        return await handler(request)
    if request.path in ('/api/admin/auth/login', '/api/admin/auth/register'):
        return await handler(request)
    session = await get_session(request)
    csrf_token = session.get('csrf_token')
    if not csrf_token:
        return web.json_response({"status": "error", "message": "CSRF token não encontrado."}, status=403)
    request_csrf = request.headers.get('X-CSRF-Token', '')
    if not request_csrf or not secrets.compare_digest(request_csrf, csrf_token):
        return web.json_response({"status": "error", "message": "CSRF token inválido."}, status=403)
    return await handler(request)
