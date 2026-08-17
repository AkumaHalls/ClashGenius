# -*- coding: utf-8 -*-
"""
Handlers de rotas públicas da API web.
Endpoints /api/* que não requerem autenticação.
"""
import json
import datetime
import logging

from aiohttp import web

import geniuslib as coc

logger = logging.getLogger("web.routes")


def register_public_routes(app, bot_instance):
    """Registra todas as rotas públicas no app principal."""

    # Busca os cogs necessários
    web_api_cog = bot_instance.get_cog("Web API")
    profile_cog = bot_instance.get_cog("Perfis de Membros")
    cwl_cog = bot_instance.get_cog("CWLPlanner")
    capital_cog = bot_instance.get_cog("Monitoramento da Capital")
    admin_cog = bot_instance.get_cog("Painel de Administração Avançado")

    async def handle_web_response(request, key, func, *args, **kwargs):
        now = datetime.datetime.now()
        cache_entry = bot_instance.web_api_cache.get(key)
        force_call = kwargs.get('force_api_call', False)
        if not bot_instance.coc_client_ready.is_set():
            return web.json_response({"status": "error", "message": "Bot iniciando (Aguardando API CoC)..."}, status=503)
        if not bot_instance.api_client:
            return web.json_response({"status": "error", "message": "Falha na conexão com a API Clash of Clans."}, status=503)
        if not force_call and cache_entry and (now - cache_entry["timestamp"]).total_seconds() < bot_instance.WEB_API_CACHE_DURATION_SECONDS:
            return web.json_response(cache_entry["data"], dumps=lambda v: json.dumps(v, default=str))
        try:
            data = await func(*args, **kwargs)
            if 'error' not in data and not force_call:
                if len(bot_instance.web_api_cache) >= bot_instance._WEB_API_CACHE_MAXSIZE:
                    oldest_key = min(bot_instance.web_api_cache, key=lambda k: bot_instance.web_api_cache[k]["timestamp"])
                    del bot_instance.web_api_cache[oldest_key]
                bot_instance.web_api_cache[key] = {"data": data, "timestamp": now}
            elif 'error' in data:
                status_code = 503 if "API" in data.get('error', '') else (404 if "não encontrado" in data.get('error', '').lower() else 500)
                return web.json_response({"status": "error", "message": data.get('error', 'Erro desconhecido')}, status=status_code, dumps=lambda v: json.dumps(v, default=str))
            return web.json_response(data, dumps=lambda v: json.dumps(v, default=str))
        except coc.LoginError:
            bot_instance.coc_client_ready.clear()
            bot_instance.api_client = None
            import asyncio
            if hasattr(bot_instance, '_reconnect_task') and bot_instance._reconnect_task and not bot_instance._reconnect_task.done():
                bot_instance._reconnect_task.cancel()
            bot_instance._reconnect_task = asyncio.create_task(bot_instance.coc_login_task())
            return web.json_response({"status": "error", "message": "Erro de autenticação com a API CoC. Tentando reconectar..."}, status=503)
        except Exception as e:
            return web.json_response({"status": "error", "message": "Erro interno no servidor."}, status=500)

    # --- Handlers simples ---
    async def api_clan_handler(r):
        return await handle_web_response(r, 'clan', web_api_cog.fetch_clan_info_for_web)

    async def api_members_handler(r):
        return await handle_web_response(r, 'members', web_api_cog.fetch_clan_members_for_web)

    async def api_current_war_details_handler(r):
        return await handle_web_response(r, 'war_details', web_api_cog.fetch_current_war_details_for_web)

    async def api_missed_attacks_history_handler(r):
        return await handle_web_response(r, 'missed_attacks', web_api_cog.fetch_missed_attacks_history_for_web)

    async def api_war_log_handler(r):
        return await handle_web_response(r, 'war_log', web_api_cog.fetch_war_log_for_web)

    async def api_cwl_info_handler(r):
        return await handle_web_response(r, 'cwl', web_api_cog.fetch_cwl_info_for_web)

    async def api_highlights_handler(r):
        return await handle_web_response(r, 'highlights', web_api_cog.fetch_highlights_for_web)

    async def api_capital_handler(r):
        return await handle_web_response(r, 'capital', capital_cog.fetch_capital_data_for_web)

    async def api_clan_games_handler(r):
        clan_games_cog = bot_instance.get_cog("Jogos do Clã")
        if clan_games_cog:
            return await handle_web_response(r, 'clan_games', clan_games_cog.fetch_clan_games_data_for_web)
        return web.json_response({"status": "error", "message": "Módulo dos Jogos do Clã não encontrado."}, status=500)

    async def api_save_player_note_handler(request):
        from aiohttp_session import get_session
        from web.auth import get_db
        session = await get_session(request)
        if not session.get('role') and not session.get('admin'):
            return web.json_response({"status": "error", "message": "Autenticação necessária."}, status=401)
        db_cog = bot_instance.get_cog("Banco de Dados")
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        data = await request.json()
        try:
            await db_cog.save_player_note_to_db(player_tag, data.get('text', ''), data.get('priority', 'none'))
            bot_instance.web_api_cache.pop('members', None)
            return web.Response(status=204)
        except ConnectionError:
            return web.json_response({"status": "error", "message": "Erro de conexão com o banco de dados."}, status=500)
        except Exception:
            return web.json_response({"status": "error", "message": "Erro interno ao salvar nota."}, status=500)

    async def api_update_cwl_status_handler(request):
        from aiohttp_session import get_session
        session = await get_session(request)
        if not session.get('role') and not session.get('admin'):
            return web.json_response({"status": "error", "message": "Autenticação necessária."}, status=401)
        db_cog = bot_instance.get_cog("Banco de Dados")
        player_tag = request.match_info.get('player_tag')
        if not player_tag:
            return web.json_response({"status": "error", "message": "Player tag is required."}, status=400)
        try:
            data = await request.json()
            status = data.get('status')
            if status not in ['active', 'backup', 'priority']:
                return web.json_response({"status": "error", "message": "Invalid status."}, status=400)
            if not db_cog:
                return web.json_response({"status": "error", "message": "Internal server error (DB Cog missing)."}, status=500)
            await db_cog.update_player_cwl_status(player_tag, status)
            bot_instance.web_api_cache.pop('members', None)
            return web.json_response({"status": "success", "message": f"Status for {player_tag} updated to {status}."})
        except Exception:
            return web.json_response({"status": "error", "message": "Internal server error while updating status."}, status=500)

    async def api_update_admin_border_handler(request):
        from aiohttp_session import get_session
        session = await get_session(request)
        role = session.get('role', '')
        is_admin_session = session.get('admin', False)
        if not role and not is_admin_session:
            return web.json_response({"status": "error", "message": "Autenticação necessária."}, status=401)
        if role == 'viewer':
            return web.json_response({"status": "error", "message": "Sem permissão para alterar borda admin."}, status=403)
        db_cog = bot_instance.get_cog("Banco de Dados")
        player_tag = request.match_info.get('player_tag')
        if not player_tag:
            return web.json_response({"status": "error", "message": "Player tag is required."}, status=400)
        try:
            data = await request.json()
            enabled = bool(data.get('enabled', False))
            if not db_cog:
                return web.json_response({"status": "error", "message": "Internal server error (DB Cog missing)."}, status=500)
            await db_cog.update_player_admin_border(player_tag, enabled)
            bot_instance.web_api_cache.pop('members', None)
            return web.json_response({"status": "success", "message": f"Admin border for {player_tag} set to {enabled}."})
        except Exception:
            return web.json_response({"status": "error", "message": "Internal server error while updating admin border."}, status=500)

    async def api_historic_war_handler(request):
        if bot_instance.db is None:
            return web.json_response({"status": "error", "message": "Banco de dados não configurado."}, status=503)
        war_id = request.match_info['war_id']
        try:
            war_doc = await bot_instance.db.war_history.find_one({"_id": war_id})
            if war_doc:
                def default_serializer(obj):
                    if isinstance(obj, (datetime.datetime, datetime.date)):
                        return obj.isoformat()
                    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
                return web.json_response(war_doc, dumps=lambda v: json.dumps(v, default=default_serializer))
            else:
                return web.json_response({"status": "error", "message": "Guerra não encontrada."}, status=404)
        except Exception:
            return web.json_response({"status": "error", "message": "Erro interno ao buscar guerra histórica."}, status=500)

    async def api_member_profile_handler(request):
        if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client:
            return web.json_response({"status": "error", "message": "API CoC temporariamente indisponível."}, status=503)
        if not profile_cog:
            return web.json_response({"status": "error", "message": "Profile cog não carregado."}, status=500)
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        profile_data = await profile_cog.fetch_player_profile_data(player_tag)
        return web.json_response(profile_data, status=404 if "error" in profile_data else 200, dumps=lambda v: json.dumps(v, default=str))

    async def api_cwl_generate_plan_handler(request):
        if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client:
            return web.json_response({"status": "error", "message": "API CoC temporariamente indisponível."}, status=503)
        if not cwl_cog:
            return web.json_response({"status": "error", "message": "CWL cog não carregado."}, status=500)
        bot_instance.web_api_cache.pop('cwl_plan', None)
        try:
            data = await request.json()
        except Exception:
            data = {}
        force = data.get("force", False)
        plan = await cwl_cog.generate_rotation_plan(force_recalculate=force)
        return web.json_response(plan)

    async def api_war_advisor_plan_handler(request):
        if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client:
            return web.json_response({"status": "error", "message": "API CoC temporariamente indisponível."}, status=503)
        war_advisor_cog = bot_instance.get_cog("Conselheiro de Guerra IA")
        try:
            war = await bot_instance.api_client.get_current_war(bot_instance.clan_tag, ignore_cache=True)
            if not bot_instance.war_prediction_system or not bot_instance.war_prediction_system.is_initialized:
                return web.json_response({"status": "error", "message": "Sistema de predição ainda inicializando."}, status=503)
            prediction_data = await bot_instance.war_prediction_system.predict_war_outcome(war, bot_instance.clan_tag)
            plan = war_advisor_cog.war_advisor.create_war_plan(war, bot_instance.clan_tag, prediction_data)
            return web.json_response(plan)
        except (coc.NotFound, coc.PrivateWarLog):
            return web.json_response({"status": "error", "message": "Nenhuma guerra ativa ou log privado."}, status=404)
        except coc.LoginError:
            return web.json_response({"status": "error", "message": "Erro de login com API CoC."}, status=503)
        except Exception:
            return web.json_response({"status": "error", "message": "Erro interno ao gerar plano."}, status=500)

    async def api_coc_status_handler(r):
        if not admin_cog:
            return web.json_response({"status": "error", "message": "Admin cog não carregado."}, status=500)
        if not bot_instance.coc_client_ready.is_set():
            return web.json_response({"status": "maintenance", "message": "Bot iniciando (Aguardando API CoC)..."}, status=200)
        if not bot_instance.api_client:
            return web.json_response({"status": "error", "message": "Falha na conexão com a API CoC."}, status=503)
        return web.json_response(await admin_cog.get_api_status())

    async def api_maintenance_message(r):
        return web.json_response({"message": bot_instance.maintenance_message})

    async def admin_get_status_handler(r):
        from aiohttp_session import get_session
        session = await get_session(r)
        is_admin = session.get('admin', False) or bool(session.get('role'))
        return web.json_response({"status": "ok", "maintenance_mode": bot_instance.maintenance_mode, "version": bot_instance.bot_version, "is_admin": is_admin})

    # Legend
    async def api_legend_data_handler(request):
        player_tag = request.query.get('tag', '')
        if not player_tag:
            return web.json_response({"status": "error", "message": "Parâmetro 'tag' é obrigatório."}, status=400)
        return await handle_web_response(request, f'legend_{player_tag}', web_api_cog.fetch_legend_data_for_web, player_tag)

    async def api_legend_history_handler(request):
        player_tag = request.query.get('tag', '')
        if not player_tag:
            return web.json_response({"status": "error", "message": "Parâmetro 'tag' é obrigatório."}, status=400)
        return await handle_web_response(request, f'legend_history_{player_tag}', web_api_cog.fetch_legend_history_for_web, player_tag)

    async def api_legend_clan_summary_handler(request):
        try:
            dias = int(request.query.get('dias', 1))
            if dias < 1 or dias > 90:
                dias = 1
        except (ValueError, TypeError):
            dias = 1
        return await handle_web_response(request, f'legend_clan_{dias}', web_api_cog.fetch_legend_clan_summary_for_web, dias)

    # Upgrades, export, compare
    async def api_player_upgrades_handler(request):
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        return await handle_web_response(request, f'upgrades_{player_tag}', web_api_cog.fetch_player_upgrades_for_web, player_tag)

    async def api_export_clan_handler(request):
        fmt = request.query.get('format', 'json')
        return web.json_response(await web_api_cog.export_clan_data_for_web(fmt))

    async def api_export_players_handler(request):
        fmt = request.query.get('format', 'json')
        return web.json_response(await web_api_cog.export_players_for_web(fmt))

    async def api_compare_players_handler(request):
        tag1 = request.query.get('tag1', '')
        tag2 = request.query.get('tag2', '')
        if not tag1 or not tag2:
            return web.json_response({"status": "error", "message": "Parâmetros tag1 e tag2 são obrigatórios."}, status=400)
        result = await web_api_cog.compare_players_for_web(tag1, tag2)
        return web.json_response(result, dumps=lambda v: json.dumps(v, default=str))

    async def api_compare_clans_handler(request):
        tag1 = request.query.get('tag1', '')
        tag2 = request.query.get('tag2', '')
        if not tag1 or not tag2:
            return web.json_response({"status": "error", "message": "Parâmetros tag1 e tag2 são obrigatórios."}, status=400)
        result = await web_api_cog.compare_clans_for_web(tag1, tag2)
        return web.json_response(result, dumps=lambda v: json.dumps(v, default=str))

    async def api_tournament_handler(request):
        tournament_cog = bot_instance.get_cog("Torneio")
        if tournament_cog:
            data = await tournament_cog.get_tournament_data_for_web()
            if data:
                return web.json_response(data, dumps=lambda v: json.dumps(v, default=str))
        return web.json_response({"status": "no_data"})

    # Registrar todas as rotas
    app.router.add_get("/api/clan", api_clan_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/current_war_details", api_current_war_details_handler)
    app.router.add_get("/api/missed_attacks_history", api_missed_attacks_history_handler)
    app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler)
    app.router.add_get("/api/highlights", api_highlights_handler)
    app.router.add_post("/api/notes/{player_tag:.*}", api_save_player_note_handler)
    app.router.add_post("/api/cwl/player_status/{player_tag:.*}", api_update_cwl_status_handler)
    app.router.add_post("/api/admin_border/{player_tag:.*}", api_update_admin_border_handler)
    app.router.add_get("/api/war_history/{war_id:.*}", api_historic_war_handler)
    app.router.add_get("/api/player_profile/{player_tag:.*}", api_member_profile_handler)
    app.router.add_post("/api/cwl/generate_plan", api_cwl_generate_plan_handler)
    app.router.add_get("/api/war_advisor_plan", api_war_advisor_plan_handler)
    app.router.add_get("/api/coc_status", api_coc_status_handler)
    app.router.add_get("/api/status", admin_get_status_handler)
    app.router.add_get("/api/maintenance_message", api_maintenance_message)
    app.router.add_get("/api/capital", api_capital_handler)
    app.router.add_get("/api/clan_games", api_clan_games_handler)
    app.router.add_get("/api/legend", api_legend_data_handler)
    app.router.add_get("/api/legend/history", api_legend_history_handler)
    app.router.add_get("/api/legend/clan", api_legend_clan_summary_handler)
    app.router.add_get("/api/player_upgrades/{player_tag:.*}", api_player_upgrades_handler)
    app.router.add_get("/api/export/clan", api_export_clan_handler)
    app.router.add_get("/api/export/players", api_export_players_handler)
    app.router.add_get("/api/compare/players", api_compare_players_handler)
    app.router.add_get("/api/compare/clans", api_compare_clans_handler)
    app.router.add_get("/api/tournament", api_tournament_handler)
