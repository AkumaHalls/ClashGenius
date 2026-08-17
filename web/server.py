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

from web.middleware import security_headers_middleware, admin_auth_middleware, admin_csrf_middleware, rate_limit_middleware
from web.routes import register_public_routes
from web.admin_routes import register_admin_routes
from web.auth_routes import register_auth_routes

logger = logging.getLogger("web.server")


async def start_early_health_check(bot_instance):
    """Inicia um servidor mínimo de health check imediatamente no setup_hook,
    antes do carregamento dos cogs. Render precisa ver a porta aberta rápido."""
    early_app = web.Application()

    async def health(r):
        return web.json_response({"status": "starting", "version": bot_instance.bot_version})

    async def root(r):
        return web.json_response({"status": "starting", "version": bot_instance.bot_version})

    early_app.router.add_get("/health", health)
    early_app.router.add_get("/", root)

    runner = web.AppRunner(early_app)
    await runner.setup()
    try:
        port = int(os.environ.get("PORT", 10000))
    except (ValueError, TypeError):
        port = 10000
    site = web.TCPSite(runner, '0.0.0.0', port)
    try:
        await site.start()
        bot_instance._early_web_runner = runner
        logger.info(f">>> Health check antecipado iniciado em :{port} <<<")
    except Exception as e:
        logger.warning(f"Health check antecipado não pôde iniciar (porta pode já estar em uso): {e}")
        bot_instance._early_web_runner = None


async def stop_early_health_check(bot_instance):
    """Para o health check antecipado quando o servidor web completo inicia."""
    runner = getattr(bot_instance, '_early_web_runner', None)
    if runner:
        try:
            await runner.cleanup()
            logger.info("Health check antecipado encerrado.")
        except Exception:
            pass
        bot_instance._early_web_runner = None


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
        if not os.path.isdir(geniuslib_assets_dir) or not os.listdir(geniuslib_assets_dir):
            logger.info("Assets da GeniusLib não encontrados. Baixando do GitHub Releases...")
            try:
                import subprocess, sys
                script = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "download_assets.py")
                subprocess.run([sys.executable, script], check=True, timeout=120)
            except Exception as dl_err:
                logger.warning(f"Falha ao baixar assets: {dl_err}")
        if os.path.isdir(geniuslib_assets_dir) and os.listdir(geniuslib_assets_dir):
            app.router.add_static('/assets/', path=geniuslib_assets_dir, name='assets')
            logger.info(f"Assets da GeniusLib servidos de: {geniuslib_assets_dir}")
        else:
            raise FileNotFoundError(f"Assets dir not found: {geniuslib_assets_dir}")
    except Exception as e:
        logger.warning(f"Assets da GeniusLib NÃO encontrados: {e}")

    # Security headers (inclui CSP) + rate limiting
    app.middlewares.append(security_headers_middleware)
    app.middlewares.append(rate_limit_middleware)

    # Registrar rotas públicas
    register_public_routes(app, bot_instance)

    # Health check
    async def health_check(r):
        return web.json_response({"status": "ok", "version": bot_instance.bot_version})
    app.router.add_get("/health", health_check)

    # Rotas de páginas
    app.router.add_static('/static/', path=static_dir, name='static')
    app.router.add_get("/", lambda r: web.json_response({"status": "ok", "version": bot_instance.bot_version}))

    # PWA: manifest com MIME correto + service worker com escopo raiz
    async def manifest_handler(r):
        return web.FileResponse(
            os.path.join(static_dir, "site.webmanifest"),
            headers={"Content-Type": "application/manifest+json", "Cache-Control": "public, max-age=3600"}
        )

    async def sw_handler(r):
        return web.FileResponse(
            os.path.join(static_dir, "sw.js"),
            headers={
                "Content-Type": "application/javascript; charset=utf-8",
                "Service-Worker-Allowed": "/",
                "Cache-Control": "no-cache"
            }
        )

    async def offline_handler(r):
        return web.FileResponse(os.path.join(static_dir, "offline.html"))

    app.router.add_get("/site.webmanifest", manifest_handler)
    app.router.add_get("/sw.js", sw_handler)
    app.router.add_get("/offline", offline_handler)
    app.router.add_get("/offline.html", offline_handler)

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
    if not FERNET_KEY:
        logger.critical("### ERRO FATAL: FERNET_KEY não definido nas variáveis de ambiente. "
                        "Sessões criptografadas não podem funcionar sem uma chave. ###")
        return
    try:
        secret_key_bytes = FERNET_KEY.encode()
        secret_key_decoded = base64.urlsafe_b64decode(secret_key_bytes)
    except (AttributeError, ValueError, TypeError):
        logger.critical("### ERRO FATAL: FERNET_KEY inválida (não é base64 válido). ###")
        return
    is_secure = os.environ.get("RENDER", "") == "true" or (BASE_URL and BASE_URL.startswith("https"))
    setup_session(app, EncryptedCookieStorage(
        secret_key_decoded,
        max_age=86400,
        secure=is_secure,
        httponly=True,
        samesite='Lax'
    ))

    # Parar health check antecipado antes de iniciar o servidor completo
    await stop_early_health_check(bot_instance)

    # Iniciar
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        port = int(os.environ.get("PORT", 10000))
    except (ValueError, TypeError):
        port = 10000
    site = web.TCPSite(runner, '0.0.0.0', port)
    try:
        await site.start()
        bot_instance._web_runner = runner
        logger.info(f">>> SERVIDOR WEB INICIADO EM :{port} <<<")
    except Exception as e:
        logger.critical(f"### ERRO FATAL WEB SERVER ###: {e}", exc_info=True)
