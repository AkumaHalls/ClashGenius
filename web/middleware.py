# -*- coding: utf-8 -*-
"""
Middleware do servidor web: segurança, auth admin, CSRF.
"""
import secrets
import logging

from aiohttp import web
from aiohttp_session import get_session

logger = logging.getLogger("web.middleware")


@web.middleware
async def security_headers_middleware(request, handler):
    """Headers de segurança em todas as respostas."""
    resp = await handler(request)
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['X-Frame-Options'] = 'DENY'
    resp.headers['Referrer-Policy'] = 'same-origin'
    resp.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    return resp


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
    if not request_csrf or request_csrf != csrf_token:
        return web.json_response({"status": "error", "message": "CSRF token inválido."}, status=403)
    return await handler(request)
