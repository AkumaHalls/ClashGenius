# -*- coding: utf-8 -*-
"""
Handlers de rotas admin: painel de controle, ações, diagnósticos.
"""
import html as html_module
import json
import logging
import os
import secrets

from aiohttp import web
from aiohttp_session import get_session

from web.auth import get_db
from web.middleware import (
    BLOCKING_STATUSES,
    get_account_state,
    is_session_revoked,
    revoke_session,
)

logger = logging.getLogger("web.admin_routes")

MAX_ADMIN_PASSWORD_LEN = 128


def _same_origin(request) -> bool:
    """Confere Origin/Referer contra o Host em requisições de login por form.

    O login por formulário não tem token CSRF (não existe sessão antes dele),
    então a checagem de origem é a defesa contra login CSRF. Navegadores enviam
    Origin em POST; clientes não-navegador (curl, testes) não enviam nenhum dos
    três headers e são aceitos.
    """
    host = request.headers.get('Host', '')
    if not host:
        return False
    origin = request.headers.get('Origin', '')
    referer = request.headers.get('Referer', '')
    if origin:
        return origin.split('://', 1)[-1].split('/', 1)[0] == host
    if referer:
        return referer.split('://', 1)[-1].split('/', 1)[0] == host
    fetch_site = request.headers.get('Sec-Fetch-Site', '')
    if fetch_site:
        return fetch_site in ('same-origin', 'none')
    return True


def make_troca_senha_page(static_dir):
    """Factory that creates the handler with static_dir captured."""
    async def troca_senha_page(r):
        """Página para definir nova senha (sessão limitada com password_change_required)."""
        session = await get_session(r)
        if not session.get('password_change_required') or not session.get('username'):
            return web.HTTPFound('/admin?error=1')

        username = session.get('username', '')
        csrf_token = session.get('csrf_token') or secrets.token_hex(32)
        session['csrf_token'] = csrf_token

        html_path = os.path.join(static_dir, 'trocar_senha.html')
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                html = f.read()
        except FileNotFoundError:
            return web.Response(text='Página não encontrada', status=404)

        # Inject username and CSRF token into the HTML
        html_content = html.replace('{{USERNAME}}', html_module.escape(username))
        html_content = html_content.replace('</head>', f'<meta name="csrf-token" content="{csrf_token}"></head>')
        return web.Response(text=html_content, content_type='text/html', charset='utf-8')
    return troca_senha_page


def register_admin_routes(admin_api_app, app, bot_instance, static_dir):
    """Registra rotas admin (API + páginas) nos apps correspondentes."""

    admin_cog = bot_instance.get_cog("Painel de Administração Avançado")
    maintenance_cog = bot_instance.get_cog("Manutenção do Sistema")
    _admin_panel_html_cache = None

    # --- Admin API handlers ---
    async def api_admin_diagnostics(r):
        if not admin_cog:
            return web.json_response({"status": "error", "message": "Admin cog não carregado."}, status=500)
        return web.json_response(await admin_cog.get_diagnostics())

    async def api_admin_get_settings(r):
        if not admin_cog:
            return web.json_response({"status": "error", "message": "Admin cog não carregado."}, status=500)
        session = await get_session(r)
        return web.json_response(await admin_cog.get_settings(session))

    async def api_admin_update_settings(r):
        if not admin_cog:
            return web.json_response({"status": "error", "message": "Admin cog não carregado."}, status=500)
        return web.json_response(await admin_cog.update_settings(await r.json()))

    async def api_admin_db_viewer(r):
        if not admin_cog:
            return web.json_response({"status": "error", "message": "Admin cog não carregado."}, status=500)
        return web.json_response(await admin_cog.get_db_viewer_data(), dumps=lambda v: json.dumps(v, default=str))

    async def api_admin_get_watchlist(r):
        if not admin_cog:
            return web.json_response({"status": "error", "message": "Admin cog não carregado."}, status=500)
        return web.json_response(await admin_cog.get_watchlist_admin())

    async def api_admin_add_watchlist(r):
        import geniuslib as coc
        data = await r.json()
        tag = data.get('player_tag')
        name = data.get('player_name')
        reason = data.get('reason')
        details = data.get('details')
        if not tag or not reason:
            return web.json_response({"status": "error", "message": "Tag e motivo obrigatórios."}, status=400)
        if not name:
            if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client:
                name = tag
            else:
                try:
                    player = await bot_instance.api_client.get_player(tag)
                    name = player.name
                except coc.NotFound:
                    name = tag
                except Exception as e:
                    logger.warning(f"Erro ao buscar nome para tag {tag} em add_watchlist: {e}")
                    name = tag
        result = await admin_cog.add_to_watchlist_admin(tag, name, reason, details)
        if result:
            bot_instance.web_api_cache.pop('members', None)
            bot_instance.web_api_cache.pop('missed_attacks', None)
            return web.json_response({"status": "success", "message": "Jogador adicionado/atualizado na watchlist."})
        else:
            return web.json_response({"status": "error", "message": "Erro interno ao adicionar à watchlist."}, status=500)

    async def api_admin_remove_watchlist(r):
        data = await r.json()
        tag = data.get('player_tag')
        if not tag:
            return web.json_response({"status": "error", "message": "Tag obrigatória."}, status=400)
        success = await admin_cog.remove_from_watchlist_admin(tag)
        if success:
            bot_instance.web_api_cache.pop('members', None)
            bot_instance.web_api_cache.pop('missed_attacks', None)
            return web.json_response({"status": "success", "message": "Jogador removido da watchlist."})
        else:
            w_cog = bot_instance.get_cog("Lista de Observação")
            entry_exists = await w_cog.is_on_watchlist(tag) if w_cog else False
            if not entry_exists:
                return web.json_response({"status": "not_found", "message": "Jogador não encontrado na watchlist."}, status=404)
            else:
                return web.json_response({"status": "error", "message": "Erro interno ao remover da watchlist."}, status=500)

    async def api_admin_actions(r):
        import asyncio
        data = await r.json()
        session = await get_session(r)
        action = data.get("action")
        payload = data.get("payload", {})
        try:
            if action == "send_announcement":
                return web.json_response(await admin_cog.send_announcement(payload.get("channel_id"), payload.get("message")))
            elif action == "clear_cache":
                return web.json_response(await admin_cog.clear_web_cache(payload.get("cache_key")))
            elif action == "force_sync_war":
                tasks_cog = bot_instance.get_cog("Tarefas em Segundo Plano")
                if tasks_cog:
                    asyncio.create_task(tasks_cog.check_war_end_task())
                    return web.json_response({"status": "success", "message": "Sincronização de guerra iniciada."})
                else:
                    return web.json_response({"status": "error", "message": "Cog de Tarefas não encontrado."}, status=500)
            elif action == "sync_commands":
                guild_id = session.get('guild_id')
                if not guild_id and payload.get("scope") == "guild":
                    return web.json_response({"status": "error", "message": "ID do servidor não encontrado na sessão para sync local."}, status=400)
                guild = bot_instance.get_guild(int(guild_id)) if guild_id else None
                return web.json_response(await admin_cog.sync_commands(payload.get("scope", "guild"), guild))
            elif action == "absolve_smurf":
                return web.json_response(await admin_cog.absolve_smurf(payload.get("pair_id")), dumps=lambda v: json.dumps(v, default=str))
            elif action == "condemn_smurf":
                return web.json_response(await admin_cog.condemn_smurf(payload.get("pair_id")), dumps=lambda v: json.dumps(v, default=str))
            elif action == "smurf_cleanup":
                return web.json_response(await admin_cog.smurf_cleanup(), dumps=lambda v: json.dumps(v, default=str))
            elif action == "send_changelog":
                return web.json_response(await admin_cog.send_changelog())
            else:
                return web.json_response({"status": "error", "message": "Ação desconhecida."}, status=400)
        except Exception as e:
            logger.error(f"Erro em api_admin_actions (Ação: {action}): {e}", exc_info=True)
            return web.json_response({"status": "error", "message": f"Erro interno ao processar '{action}'."}, status=500)

    async def api_admin_discord_data(r):
        if not admin_cog:
            return web.json_response({"status": "error", "message": "Admin cog não carregado."}, status=500)
        return web.json_response(await admin_cog.get_discord_data())

    async def api_admin_smurf_dossier(r):
        if not admin_cog:
            return web.json_response({"status": "error", "message": "Admin cog não carregado."}, status=500)
        return web.json_response(await admin_cog.get_smurf_dossier(), dumps=lambda v: json.dumps(v, default=str))

    async def api_admin_smurf_training_status(r):
        if not admin_cog:
            return web.json_response({"status": "error", "message": "Admin cog não carregado."}, status=500)
        return web.json_response(await admin_cog.get_smurf_training_status(), dumps=lambda v: json.dumps(v, default=str))

    async def api_get_csrf_token(r):
        session = await get_session(r)
        token = session.get('csrf_token')
        if not token:
            token = secrets.token_hex(32)
            session['csrf_token'] = token
        return web.json_response({"csrf_token": token})

    # --- Páginas HTML ---
    async def admin_login_page(r):
        return web.FileResponse(os.path.join(static_dir, "admin_login.html"))

    async def admin_panel_page(r):
        nonlocal _admin_panel_html_cache
        session = await get_session(r)
        if is_session_revoked(session):
            return web.HTTPFound('/admin')
        role = session.get('role')
        if not role and not session.get('admin'):
            return web.HTTPFound('/admin')
        # Conta banida/desativada perde o painel mesmo com cookie válido.
        username = (session.get('username') or '').lower()
        if username and username != 'root':
            state = await get_account_state(getattr(bot_instance, 'db', None), username)
            if state is not None:
                if (state.get('status') or 'active').lower() in BLOCKING_STATUSES:
                    revoke_session(session)
                    session.invalidate()
                    return web.HTTPFound('/admin')
                db_role = state.get('role')
                if db_role:
                    session['role'] = db_role
        csrf_token = session.get('csrf_token') or secrets.token_hex(32)
        session['csrf_token'] = csrf_token
        if _admin_panel_html_cache is None:
            with open(os.path.join(static_dir, "admin_panel.html"), 'r', encoding='utf-8') as f:
                _admin_panel_html_cache = f.read()
        html = _admin_panel_html_cache.replace('</head>', f'<meta name="csrf-token" content="{csrf_token}"></head>')
        return web.Response(text=html, content_type='text/html', charset='utf-8')

    async def admin_login_handler(r):
        from config import ADMIN_PASSWORD
        if not _same_origin(r):
            return web.HTTPFound('/admin?error=1')
        data = await r.post()
        guild_id_from_form = str(data.get('guild_id', ''))[:32]
        password = str(data.get('password', ''))[:MAX_ADMIN_PASSWORD_LEN]
        db, err = get_db(bot_instance)
        if err:
            return web.HTTPFound('/admin?error=1')
        master_ok = bool(ADMIN_PASSWORD) and secrets.compare_digest(password, ADMIN_PASSWORD)
        if master_ok:
            session = await get_session(r)
            session.invalidate()
            session['sid'] = secrets.token_urlsafe(16)
            session['csrf_token'] = secrets.token_hex(32)
            session['admin'] = True
            session['role'] = 'admin'
            session['username'] = 'root'
            session['guild_id'] = guild_id_from_form if guild_id_from_form else None
            return web.HTTPFound('/admin/panel')
        return web.HTTPFound("/admin?error=1")

    async def admin_logout_handler(r):
        session = await get_session(r)
        revoke_session(session)
        session.invalidate()
        return web.HTTPFound('/admin')

    def _csrf_ok(r, session):
        """Valida o token CSRF enviado no header X-CSRF-Token."""
        provided = r.headers.get('X-CSRF-Token', '')
        expected = session.get('csrf_token', '')
        return bool(expected) and bool(provided) and secrets.compare_digest(provided, expected)

    async def admin_toggle_maintenance_handler(r):
        session = await get_session(r)
        if is_session_revoked(session):
            return web.json_response({"status": "unauthorized", "message": "Sessão encerrada. Entre novamente."}, status=401)
        role = session.get('role')
        if role == 'viewer':
            return web.json_response({"status": "forbidden", "message": "Membro Sênior não tem acesso."}, status=403)
        if not role and not session.get('admin'):
            return web.json_response({"status": "unauthorized"}, status=403)
        if not _csrf_ok(r, session):
            return web.json_response({"status": "error", "message": "CSRF token inválido."}, status=403)
        if not maintenance_cog:
            return web.json_response({"status": "error", "message": "Maintenance cog não carregado."}, status=500)
        return await maintenance_cog.toggle_maintenance_mode_web()

    async def admin_send_test_embed_handler(r):
        session = await get_session(r)
        if is_session_revoked(session):
            return web.json_response({"status": "unauthorized", "message": "Sessão encerrada. Entre novamente."}, status=401)
        role = session.get('role')
        if role == 'viewer':
            return web.json_response({"status": "forbidden", "message": "Membro Sênior não tem acesso."}, status=403)
        if not role and not session.get('admin'):
            return web.json_response({"status": "unauthorized"}, status=403)
        if not _csrf_ok(r, session):
            return web.json_response({"status": "error", "message": "CSRF token inválido."}, status=403)
        if not maintenance_cog:
            return web.json_response({"status": "error", "message": "Maintenance cog não carregado."}, status=500)
        return await maintenance_cog.send_test_embed_web()

    # --- Registrar rotas admin API ---
    admin_api_app.router.add_get("/diagnostics", api_admin_diagnostics)
    admin_api_app.router.add_get("/settings", api_admin_get_settings)
    admin_api_app.router.add_post("/settings", api_admin_update_settings)
    admin_api_app.router.add_get("/db_viewer", api_admin_db_viewer)
    admin_api_app.router.add_post("/actions", api_admin_actions)
    admin_api_app.router.add_get("/watchlist", api_admin_get_watchlist)
    admin_api_app.router.add_post("/watchlist/add", api_admin_add_watchlist)
    admin_api_app.router.add_post("/watchlist/remove", api_admin_remove_watchlist)
    admin_api_app.router.add_get("/discord_data", api_admin_discord_data)
    admin_api_app.router.add_get("/smurf_dossier", api_admin_smurf_dossier)
    admin_api_app.router.add_get("/smurf_training_status", api_admin_smurf_training_status)

    # Export (usa web_api_cog diretamente)
    web_api_cog = bot_instance.get_cog("Web API")

    async def admin_export_clan(r):
        if not web_api_cog:
            return web.json_response({"status": "error", "message": "Web API cog não carregado."}, status=500)
        return web.json_response(await web_api_cog.export_clan_data_for_web('json'))

    async def admin_export_players(r):
        if not web_api_cog:
            return web.json_response({"status": "error", "message": "Web API cog não carregado."}, status=500)
        return web.json_response(await web_api_cog.export_players_for_web('json'))

    admin_api_app.router.add_get("/export/clan", admin_export_clan)
    admin_api_app.router.add_get("/export/players", admin_export_players)
    admin_api_app.router.add_get("/csrf_token", api_get_csrf_token)

    # --- Registrar rotas páginas admin (no app principal) ---
    app.router.add_get("/admin", admin_login_page)
    app.router.add_post("/admin/login", admin_login_handler)
    app.router.add_get("/admin/logout", admin_logout_handler)
    app.router.add_get("/admin/panel", admin_panel_page)
    app.router.add_get("/trocar-senha", make_troca_senha_page(static_dir))
    app.router.add_post("/admin/toggle_maintenance", admin_toggle_maintenance_handler)
    app.router.add_post("/admin/send_test_embed", admin_send_test_embed_handler)
