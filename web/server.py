# -*- coding: utf-8 -*-
"""
Configuração e inicialização do servidor web.
Ponto central que monta o app aiohttp com todas as rotas e middleware.
"""
import os
import logging
import base64
import json

from aiohttp import web
from aiohttp_session import setup as setup_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography.fernet import Fernet

from web.middleware import security_headers_middleware, admin_auth_middleware, admin_csrf_middleware
from web.routes import register_public_routes
from web.admin_routes import register_admin_routes
from web.auth_routes import register_auth_routes

logger = logging.getLogger("web.server")


async def setup_web_server(bot_instance):
    """Configura e inicia o servidor web aiohttp."""
    logger.info("setup_web_server: Aguardando fim do setup_hook...")
    await bot_instance._setup_hook_done.wait()
    logger.info("setup_web_server: setup_hook terminado. Iniciando configuração do servidor web...")

    app = web.Application()

    # Verificar cogs essenciais
    required_cog_names = ["Web API", "Banco de Dados", "Perfis de Membros", "CWLPlanner",
                          "Manutenção do Sistema", "Conselheiro de Guerra IA",
                          "Painel de Administração Avançado", "Lista de Observação", "Monitoramento da Capital"]
    missing = [name for name in required_cog_names if bot_instance.get_cog(name) is None]
    if missing:
        logger.critical(f"Cogs disponíveis no bot: {list(bot_instance.cogs.keys())}")
        logger.critical(f"### ERRO FATAL: Cogs web essenciais não carregados: {', '.join(missing)}. Servidor web NÃO PODE iniciar. ###")
        return
    logger.info("Todas Cogs web encontradas.")

    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

    # Servir assets da GeniusLib
    try:
        from geniuslib.utils import get_assets_dir as _get_assets_dir
        geniuslib_assets_dir = _get_assets_dir()
        if os.path.isdir(geniuslib_assets_dir):
            app.router.add_static('/assets/', path=geniuslib_assets_dir, name='assets')
            logger.info(f"Assets da GeniusLib servidos de: {geniuslib_assets_dir}")
        else:
            raise FileNotFoundError(f"Assets dir not found: {geniuslib_assets_dir}")
    except Exception as e:
        logger.warning(f"Assets da GeniusLib NÃO encontrados: {e}")

    # Security headers (inclui CSP)
    app.middlewares.append(security_headers_middleware)

    # Registrar rotas públicas
    register_public_routes(app, bot_instance)

    # Rotas de páginas
    app.router.add_static('/static/', path=static_dir, name='static')
    app.router.add_get("/", lambda r: web.HTTPFound('/painel'))

    async def painel_handler(r):
        from aiohttp_session import get_session
        api_cog = bot_instance.get_cog("Painel de Administração Avançado")
        status_data = {"status": "ok"}
        if api_cog:
            try:
                status_data = await api_cog.get_api_status()
            except Exception:
                pass
        session = await get_session(r)
        is_admin = session.get('admin', False) or bool(session.get('role'))
        if (bot_instance.maintenance_mode or status_data.get("status") in ["maintenance", "error"]) and not is_admin:
            return web.HTTPFound('/maintenance')
        return web.FileResponse(os.path.join(static_dir, "painel.html"))

    async def maintenance_page_handler(r):
        return web.FileResponse(os.path.join(static_dir, "maintenance.html"))

    app.router.add_get("/painel", painel_handler)
    app.router.add_get("/maintenance", maintenance_page_handler)

    # Admin sub-app com auth + CSRF
    admin_api_app = web.Application(middlewares=[admin_auth_middleware, admin_csrf_middleware])
    register_auth_routes(admin_api_app, bot_instance)
    register_admin_routes(admin_api_app, app, bot_instance, static_dir)
    app.add_subapp("/api/admin/", admin_api_app)

    # Sessions (Fernet encrypted cookies)
    from config import FERNET_KEY, BASE_URL
    try:
        secret_key_bytes = FERNET_KEY.encode()
        secret_key_decoded = base64.urlsafe_b64decode(secret_key_bytes)
    except (AttributeError, ValueError, TypeError):
        secret_key_decoded = FERNET_KEY
    if not secret_key_decoded:
        secret_key_decoded = Fernet.generate_key()
    is_secure = os.environ.get("RENDER", "") == "true" or (BASE_URL and BASE_URL.startswith("https"))
    setup_session(app, EncryptedCookieStorage(
        secret_key_decoded,
        max_age=86400,
        secure=is_secure,
        httponly=True
    ))

    # Iniciar
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    try:
        await site.start()
        bot_instance._web_runner = runner
        logger.info(f">>> SERVIDOR WEB INICIADO EM :{port} <<<")
    except Exception as e:
        logger.critical(f"### ERRO FATAL WEB SERVER ###: {e}", exc_info=True)
