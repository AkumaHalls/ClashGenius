# -*- coding: utf-8 -*-
# Versão 20.2.12-Startup-Hotfix

import os
import logging
import asyncio
import datetime
from typing import Dict, Any, Optional, List

import discord
from discord.ext import commands
import coc
import pytz
from dotenv import load_dotenv
import motor.motor_asyncio
from pymongo.uri_parser import parse_uri
from aiohttp import web
from aiohttp_session import setup as setup_session, get_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
import base64
from cryptography.fernet import Fernet
import json

from war_predictor import WarPredictionSystemV3

class MemoryLogHandler(logging.Handler):
    """Guarda os registos de log mais recentes em memória."""
    def __init__(self, capacity=50):
        super().__init__()
        self.capacity = capacity
        self.buffer = []

    def emit(self, record):
        self.buffer.append(self.format(record))
        if len(self.buffer) > self.capacity:
            self.buffer.pop(0)

log_handler = MemoryLogHandler()
log_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log_handler.setFormatter(formatter)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logging.getLogger().addHandler(log_handler)
logger = logging.getLogger("clash_genius_bot")

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COC_EMAIL = os.getenv("COC_EMAIL")
COC_PASSWORD = os.getenv("COC_PASSWORD")
CLAN_TAG = os.getenv("CLAN_TAG")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
AI_LOG_CHANNEL_ID = int(os.getenv("AI_LOG_CHANNEL_ID", 0))
POST_WAR_ANALYSIS_CHANNEL_ID = int(os.getenv("POST_WAR_ANALYSIS_CHANNEL_ID", 0))
CLAN_GAMES_CHANNEL_ID = int(os.getenv("CLAN_GAMES_CHANNEL_ID", 0))
CWL_PLANNER_CHANNEL_ID = int(os.getenv("CWL_PLANNER_CHANNEL_ID", 0))
DONATIONS_CHANNEL_ID = int(os.getenv("DONATIONS_CHANNEL_ID", 0))
MONGO_DB_URL = os.getenv("MONGO_DB_URL")
ROLE_ID_1STAR_ALERT = int(os.getenv("ROLE_ID_1STAR_ALERT", 0))
ROLE_ID_MISSED_ATTACK = int(os.getenv("ROLE_ID_MISSED_ATTACK", 0))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
FERNET_KEY = os.getenv("FERNET_KEY")
BASE_URL = os.getenv("BASE_URL")

BOT_VERSION = "20.2.15-Watchlist" # Atualiza a versão
TIMEZONE = pytz.timezone('America/Sao_Paulo')

class ClashGeniusBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coc_email = COC_EMAIL
        self.coc_password = COC_PASSWORD
        self.clan_tag = CLAN_TAG
        self.channel_id = CHANNEL_ID
        self.ai_log_channel_id = AI_LOG_CHANNEL_ID
        self.post_war_analysis_channel_id = POST_WAR_ANALYSIS_CHANNEL_ID
        self.clan_games_channel_id = CLAN_GAMES_CHANNEL_ID
        self.cwl_planner_channel_id = CWL_PLANNER_CHANNEL_ID
        self.donations_channel_id = DONATIONS_CHANNEL_ID
        self.role_id_1star_alert = ROLE_ID_1STAR_ALERT
        self.role_id_missed_attack = ROLE_ID_MISSED_ATTACK
        self.bot_version = BOT_VERSION
        self.timezone = TIMEZONE
        self.base_url = BASE_URL
        self.maintenance_mode = False
        self.maintenance_message = "O painel está em manutenção. Voltaremos em breve!"
        self.api_client: Optional[coc.Client] = None
        self.war_prediction_system: Optional[WarPredictionSystemV3] = None
        self.db = None
        self.mongo_client = None
        self.clan_cache: Dict[str, Dict[str, Any]] = {}
        self.CACHE_DURATION_SECONDS = 300
        self.web_api_cache: Dict[str, Dict[str, Any]] = {}
        self.WEB_API_CACHE_DURATION_SECONDS = 45
        self.db_ready = asyncio.Event()
        self.coc_client_ready = asyncio.Event()
        self.processed_war_ids = set()
        self.last_api_status = "ok" # Para monitorar mudanças no status da API
        self.log_handler = log_handler

    async def setup_hook(self) -> None:
        logger.info("A executar setup_hook...")
        if MONGO_DB_URL:
            try:
                db_name = parse_uri(MONGO_DB_URL).get('database', 'genius_db')
                self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)
                self.db = self.mongo_client[db_name]
                logger.info(f"Ligado ao MongoDB: {db_name}")
                await self.load_initial_state_from_db()
                self.db_ready.set()
            except Exception as e:
                logger.error(f"Falha ao ligar ao MongoDB: {e}", exc_info=True)
        else:
            logger.warning("URL do MongoDB não fornecida. Recursos de persistência desativados.")
            self.db_ready.set()

        self.war_prediction_system = WarPredictionSystemV3(db_connection=self.db)
        await self.war_prediction_system.initialize_system()

        logger.info("A carregar cogs...")
        cog_files = [
            'events_cog', 'tasks_cog', 'database_cog', 'general_cog',
            'cwl_planner_cog', 'clan_games_cog', 'war_advisor_cog', 'profile_cog',
            'maintenance_cog', 'web_api_cog', 'admin_cog', 'donation_cog',
            'slash_cog', 'watchlist_cog' # Adiciona a nova Cog
        ]
        for cog_name in cog_files:
            try:
                await self.load_extension(f'cogs.{cog_name}')
                logger.info(f"Cog '{cog_name}' carregado com sucesso.")
            except Exception as e:
                # ADICIONADO: Log de erro detalhado para diagnóstico
                logger.error(f"FALHA CRÍTICA AO CARREGAR O COG '{cog_name}'. Erro: {e}", exc_info=True)

        self.loop.create_task(self.coc_login_task())
        self.loop.create_task(setup_web_server(self))

    async def load_initial_state_from_db(self):
        if self.db is None: return
        maint_config = await self.db.system_config.find_one({"_id": "maintenance_mode"})
        if maint_config:
            self.maintenance_mode = maint_config.get("enabled", False)
            logger.info(f"Modo de manutenção carregado da BD. Estado: {'ATIVADO' if self.maintenance_mode else 'DESATIVADO'}")

        bot_settings = await self.db.system_config.find_one({"_id": "bot_settings"})
        if bot_settings:
            self.channel_id = bot_settings.get("channel_id", self.channel_id)
            self.post_war_analysis_channel_id = bot_settings.get("post_war_analysis_channel_id", self.post_war_analysis_channel_id)
            self.clan_games_channel_id = bot_settings.get("clan_games_channel_id", self.clan_games_channel_id)
            self.cwl_planner_channel_id = bot_settings.get("cwl_planner_channel_id", self.cwl_planner_channel_id)
            self.donations_channel_id = bot_settings.get("donations_channel_id", self.donations_channel_id)
            self.role_id_1star_alert = bot_settings.get("role_id_1star_alert", self.role_id_1star_alert)
            self.role_id_missed_attack = bot_settings.get("role_id_missed_attack", self.role_id_missed_attack)
            self.maintenance_message = bot_settings.get("maintenance_message", self.maintenance_message)
            logger.info("Configurações de IDs e mensagens carregadas da base de dados.")

        processed_wars_cursor = self.db.war_history.find({}, {"_id": 1})
        self.processed_war_ids = {doc["_id"] async for doc in processed_wars_cursor}
        logger.info(f"Carregados {len(self.processed_war_ids)} IDs de guerras já processadas do histórico.")

    async def coc_login_task(self):
        try:
            self.api_client = coc.Client()
            await self.api_client.login(self.coc_email, self.coc_password)
            logger.info("Login no coc.Client (api_client) bem-sucedido.")
            self.coc_client_ready.set()
        except Exception as e:
            logger.critical(f"Falha CRÍTICA no login do coc.Client: {e}", exc_info=True)

    async def on_ready(self):
        logger.info(f'Bot {self.user.name} está online e pronto!')
        # Adicionado: Tenta sincronizar os comandos no arranque para garantir que estão registados
        try:
            synced = await self.tree.sync()
            logger.info(f"Sincronizados {len(synced)} comandos de barra no arranque.")
        except Exception as e:
            logger.error(f"Falha ao sincronizar comandos no arranque: {e}", exc_info=True)


    async def close(self):
        logger.info("A fechar ligações...")
        if self.api_client: await self.api_client.close()
        if self.mongo_client: self.mongo_client.close()
        await super().close()

    async def get_clan_data_with_cache(self, tag: str) -> Optional[coc.Clan]:
        await self.coc_client_ready.wait()
        normalized_tag = coc.utils.correct_tag(tag)
        now = datetime.datetime.now()
        if normalized_tag in self.clan_cache and (now - self.clan_cache[normalized_tag]["timestamp"]).total_seconds() < self.CACHE_DURATION_SECONDS:
            return self.clan_cache[normalized_tag]["data"]
        try:
            clan_data = await self.api_client.get_clan(normalized_tag)
            self.clan_cache[normalized_tag] = {"data": clan_data, "timestamp": now}
            return clan_data
        except Exception as e:
            logger.error(f"Erro ao obter dados do clã {tag}: {e}")
            return None

async def setup_web_server(bot_instance: ClashGeniusBot):
    app = web.Application()

    await bot_instance.wait_until_ready()
    # Adiciona a referência à nova Cog
    web_api_cog = bot_instance.get_cog("Web API")
    db_cog = bot_instance.get_cog("Banco de Dados")
    profile_cog = bot_instance.get_cog("Perfis de Membros")
    cwl_cog = bot_instance.get_cog("Planeador de CWL")
    maintenance_cog = bot_instance.get_cog("Manutenção do Sistema")
    war_advisor_cog = bot_instance.get_cog("Conselheiro de Guerra IA")
    admin_cog = bot_instance.get_cog("Painel de Administração Avançado")
    watchlist_cog = bot_instance.get_cog("Lista de Observação") # Referência à nova Cog

    # Verifica se todas as Cogs necessárias foram carregadas
    required_cogs = [
        web_api_cog, db_cog, profile_cog, cwl_cog, maintenance_cog,
        war_advisor_cog, admin_cog, watchlist_cog # Adiciona watchlist_cog à verificação
    ]
    if not all(required_cogs):
        missing = [cog.__class__.__name__ for cog in required_cogs if cog is None]
        logger.critical(f"Cogs essenciais para o servidor web não carregados: {', '.join(missing)}. O servidor não pode iniciar.")
        return

    async def handle_web_response(request, key, func, *args, **kwargs):
        now = datetime.datetime.now()
        if not kwargs.get('force_api_call', False) and key in bot_instance.web_api_cache and (now - bot_instance.web_api_cache[key]["timestamp"]).total_seconds() < bot_instance.WEB_API_CACHE_DURATION_SECONDS:
            return web.json_response(bot_instance.web_api_cache[key]["data"])
        if not bot_instance.coc_client_ready.is_set():
            return web.json_response({"error": "O bot ainda está a iniciar... Por favor, aguarde."}, status=503)
        data = await func(*args, **kwargs)
        if 'error' not in data and not kwargs.get('force_api_call', False):
             bot_instance.web_api_cache[key] = {"data": data, "timestamp": now}
        return web.json_response(data)

    async def api_clan_handler(r): return await handle_web_response(r, 'clan', web_api_cog.fetch_clan_info_for_web)
    async def api_members_handler(r): return await handle_web_response(r, 'members', web_api_cog.fetch_clan_members_for_web)
    async def api_current_war_details_handler(r): return await handle_web_response(r, 'war_details', web_api_cog.fetch_current_war_details_for_web)
    async def api_missed_attacks_history_handler(r): return await handle_web_response(r, 'missed_attacks', web_api_cog.fetch_missed_attacks_history_for_web)
    async def api_war_log_handler(r): return await handle_web_response(r, 'war_log', web_api_cog.fetch_war_log_for_web)
    async def api_cwl_info_handler(r): return await handle_web_response(r, 'cwl', web_api_cog.fetch_cwl_info_for_web)
    async def api_highlights_handler(r): return await handle_web_response(r, 'highlights', web_api_cog.fetch_highlights_for_web)
    async def api_save_player_note_handler(request):
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        data = await request.json()
        await db_cog.save_player_note_to_db(player_tag, data.get('text', ''), data.get('priority', 'none'))
        bot_instance.web_api_cache.pop('members', None)
        return web.Response(status=204)
    async def api_historic_war_handler(request):
        war_id = request.match_info['war_id']
        war_doc = await bot_instance.db.war_history.find_one({"_id": war_id})
        return web.json_response(war_doc, dumps=lambda v: json.dumps(v, default=str)) if war_doc else web.json_response({"error": "Guerra não encontrada."}, status=404)
    async def api_member_profile_handler(request):
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        profile_data = await profile_cog.fetch_player_profile_data(player_tag)
        return web.json_response(profile_data, status=404 if "error" in profile_data else 200)
    async def api_cwl_generate_plan_handler(request):
        bot_instance.web_api_cache.pop('cwl_plan', None)
        plan = await cwl_cog.generate_rotation_plan()
        return web.json_response(plan)
    async def api_war_advisor_plan_handler(request):
        try:
            war = await bot_instance.api_client.get_current_war(bot_instance.clan_tag)
            prediction_data = await bot_instance.war_prediction_system.predict_war_outcome(war, bot_instance.clan_tag)
            plan = war_advisor_cog.war_advisor.create_war_plan(war, bot_instance.clan_tag, prediction_data)
            return web.json_response(plan)
        except (coc.NotFound, coc.PrivateWarLog):
            return web.json_response({"success": False, "error": "Nenhuma guerra ativa."}, status=404)
        except Exception as e:
            logger.error(f"Erro no endpoint do war_advisor: {e}", exc_info=True)
            return web.json_response({"success": False, "error": "Erro interno."}, status=500)

    async def api_coc_status_handler(r):
        """Handler to get the current status of the CoC API."""
        if not admin_cog:
            return web.json_response({"status": "error", "message": "Admin cog not loaded."}, status=500)

        if not bot_instance.coc_client_ready.is_set():
            return web.json_response({"status": "maintenance", "message": "O bot ainda está a iniciar... Por favor, aguarde."}, status=200)

        status_data = await admin_cog.get_api_status()
        return web.json_response(status_data)

    app.router.add_get("/api/clan", api_clan_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/current_war_details", api_current_war_details_handler)
    app.router.add_get("/api/missed_attacks_history", api_missed_attacks_history_handler)
    app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler)
    app.router.add_get("/api/highlights", api_highlights_handler)
    app.router.add_post("/api/notes/{player_tag:.*}", api_save_player_note_handler)
    app.router.add_get("/api/war_history/{war_id:.*}", api_historic_war_handler)
    app.router.add_get("/api/player_profile/{player_tag:.*}", api_member_profile_handler)
    app.router.add_post("/api/cwl/generate_plan", api_cwl_generate_plan_handler)
    app.router.add_get("/api/war_advisor_plan", api_war_advisor_plan_handler)
    app.router.add_get("/api/coc_status", api_coc_status_handler) # Rota adicionada

    @web.middleware
    async def admin_auth_middleware(request, handler):
        session = await get_session(request)
        if not session.get('admin'):
            # Permite acesso ao GET /api/admin/watchlist sem autenticação se necessário
            # (Ajustar se a leitura da watchlist precisar ser protegida)
            # if request.method == 'GET' and request.path == '/api/admin/watchlist':
            #     pass # Permite leitura pública da watchlist
            # else:
            return web.json_response({"status": "unauthorized"}, status=403)
        response = await handler(request)
        return response

    async def api_admin_diagnostics(r): return web.json_response(await admin_cog.get_diagnostics())
    async def api_admin_get_settings(r): return web.json_response(await admin_cog.get_settings())
    async def api_admin_update_settings(r): return web.json_response(await admin_cog.update_settings(await r.json()))
    async def api_admin_db_viewer(r): return web.json_response(await admin_cog.get_db_viewer_data(), dumps=lambda v: json.dumps(v, default=str))

    # --- Novas Rotas Admin para Watchlist ---
    async def api_admin_get_watchlist(r):
        data = await watchlist_cog.get_full_watchlist()
        # Converte ObjectId e datetime para string para serialização JSON
        for item in data:
            item['_id'] = str(item['_id'])
            if isinstance(item.get('date_added'), datetime.datetime):
                item['date_added'] = item['date_added'].isoformat()
        return web.json_response(data)

    async def api_admin_add_watchlist(r):
        data = await r.json()
        tag = data.get('player_tag')
        name = data.get('player_name') # Opcional, pode buscar se não fornecido
        reason = data.get('reason')
        details = data.get('details')
        if not tag or not reason:
            return web.json_response({"status": "error", "message": "Tag do jogador e motivo são obrigatórios."}, status=400)
        # Opcional: buscar nome se não fornecido
        if not name:
             try:
                 player = await bot_instance.api_client.get_player(tag)
                 name = player.name
             except:
                 name = tag # Usa a tag como nome se não conseguir buscar
        success = await watchlist_cog.add_to_watchlist(tag, name, reason, details)
        if success:
            bot_instance.web_api_cache.pop('members', None) # Limpa cache de membros
            return web.json_response({"status": "success", "message": "Jogador adicionado à watchlist."})
        else:
            return web.json_response({"status": "error", "message": "Erro ao adicionar jogador."}, status=500)

    async def api_admin_remove_watchlist(r):
        data = await r.json()
        tag = data.get('player_tag')
        if not tag:
            return web.json_response({"status": "error", "message": "Tag do jogador é obrigatória."}, status=400)
        success = await watchlist_cog.remove_from_watchlist(tag)
        if success:
            bot_instance.web_api_cache.pop('members', None) # Limpa cache de membros
            return web.json_response({"status": "success", "message": "Jogador removido da watchlist."})
        else:
            # Pode ser erro ou jogador não encontrado, tratamos como sucesso parcial para UI
            return web.json_response({"status": "success", "message": "Jogador não encontrado ou erro ao remover."}, status=200)
    # --- Fim das Novas Rotas Admin ---

    async def api_admin_actions(r):
        data = await r.json()
        session = await get_session(r)
        action = data.get("action")
        payload = data.get("payload", {})

        if action == "send_announcement":
            return web.json_response(await admin_cog.send_announcement(payload.get("channel_id"), payload.get("message")))
        elif action == "clear_cache":
            return web.json_response(await admin_cog.clear_web_cache(payload.get("cache_key")))
        elif action == "force_sync_war":
            tasks_cog = bot_instance.get_cog("Tarefas em Segundo Plano")
            asyncio.create_task(tasks_cog.check_war_end_task.coro(tasks_cog))
            return web.json_response({"status": "success", "message": "Sincronização de guerra forçada."})
        elif action == "sync_commands":
            guild_id = session.get('guild_id')
            if not guild_id and payload.get("scope") == "guild":
                return web.json_response({"status": "error", "message": "ID do servidor não encontrado na sessão. Faça login novamente usando o link do bot."})

            guild = bot_instance.get_guild(int(guild_id)) if guild_id else None
            return web.json_response(await admin_cog.sync_commands(payload.get("scope", "guild"), guild))
        return web.json_response({"status": "error", "message": "Ação desconhecida."}, status=400)

    admin_api_app = web.Application(middlewares=[admin_auth_middleware])
    admin_api_app.router.add_get("/diagnostics", api_admin_diagnostics)
    admin_api_app.router.add_get("/settings", api_admin_get_settings)
    admin_api_app.router.add_post("/settings", api_admin_update_settings)
    admin_api_app.router.add_get("/db_viewer", api_admin_db_viewer)
    admin_api_app.router.add_post("/actions", api_admin_actions)
    # Adiciona rotas da watchlist ao subapp admin
    admin_api_app.router.add_get("/watchlist", api_admin_get_watchlist)
    admin_api_app.router.add_post("/watchlist/add", api_admin_add_watchlist)
    admin_api_app.router.add_post("/watchlist/remove", api_admin_remove_watchlist)


    app.add_subapp("/api/admin/", admin_api_app)

    static_dir = os.path.join(os.path.dirname(__file__), "static")

    async def admin_login_page(r): return web.FileResponse(os.path.join(static_dir, "admin_login.html"))
    async def admin_panel_page(r):
        session = await get_session(r)
        if not session.get('admin'):
            return web.HTTPFound('/admin')
        return web.FileResponse(os.path.join(static_dir, "admin_panel.html"))
    async def admin_login_handler(r):
        data = await r.post()
        if data.get('password') == ADMIN_PASSWORD:
            session = await get_session(r)
            session['admin'] = True
            guild_id = data.get('guild_id')
            if guild_id:
                session['guild_id'] = guild_id
            return web.HTTPFound('/admin/panel')
        return web.HTTPFound(f"/admin?error=1&guild_id={data.get('guild_id', '')}")

    async def admin_logout_handler(r):
        session = await get_session(r)
        session.pop('admin', None)
        session.pop('guild_id', None)
        return web.HTTPFound('/admin')

    async def admin_toggle_maintenance_handler(request):
        session = await get_session(request)
        if not session.get('admin'): return web.json_response({"status": "unauthorized"}, status=403)
        return await maintenance_cog.toggle_maintenance_mode_web()

    async def admin_send_test_embed_handler(request):
        session = await get_session(request)
        if not session.get('admin'): return web.json_response({"status": "unauthorized"}, status=403)
        return await maintenance_cog.send_test_embed_web()

    async def admin_get_status_handler(request):
        session = await get_session(request)
        is_admin = session.get('admin', False)
        return web.json_response({
            "status": "ok",
            "maintenance_mode": bot_instance.maintenance_mode,
            "version": BOT_VERSION,
            "is_admin": is_admin
        })

    async def api_maintenance_message(r):
        return web.json_response({"message": bot_instance.maintenance_message})

    app.router.add_get("/api/maintenance_message", api_maintenance_message)
    app.router.add_get("/admin", admin_login_page)
    app.router.add_post("/admin/login", admin_login_handler)
    app.router.add_get("/admin/logout", admin_logout_handler)
    app.router.add_get("/admin/panel", admin_panel_page)
    app.router.add_post("/admin/toggle_maintenance", admin_toggle_maintenance_handler)
    app.router.add_post("/admin/send_test_embed", admin_send_test_embed_handler)
    app.router.add_get("/api/status", admin_get_status_handler)

    async def painel_handler(request):
        session = await get_session(request)
        is_admin = session.get('admin', False)
        if bot_instance.maintenance_mode and not is_admin:
            return web.FileResponse(os.path.join(static_dir, "maintenance.html"))
        return web.FileResponse(os.path.join(static_dir, "painel.html"))

    app.router.add_static('/static/', path=static_dir, name='static')
    app.router.add_get("/painel", painel_handler)
    app.router.add_get("/", lambda r: web.Response(text=f"Bot running! v{BOT_VERSION}"))

    secret_key = base64.urlsafe_b64decode(Fernet.generate_key() if not FERNET_KEY else FERNET_KEY.encode())
    setup_session(app, EncryptedCookieStorage(secret_key))

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Servidor web iniciado em http://0.0.0.0:{port}")

async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    bot = ClashGeniusBot(command_prefix="!", intents=intents)
    try:
        await bot.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot desligado manualmente.")
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
