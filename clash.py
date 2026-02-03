# -*- coding: utf-8 -*-
# Versão 20.2.21-AntiLoop1

import os
import logging
import asyncio
import datetime
from typing import Dict, Any, Optional, List
import time

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

# --- Configuração de Logging ---
class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity=50):
        super().__init__()
        self.capacity = capacity
        self.buffer = []
    def emit(self, record):
        self.buffer.append(self.format(record))
        if len(self.buffer) > self.capacity: self.buffer.pop(0)

log_handler = MemoryLogHandler()
log_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log_handler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logging.getLogger().addHandler(log_handler)
logger = logging.getLogger("clash_genius_bot")

# --- Carregamento de Variáveis de Ambiente ---
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
WATCHLIST_ALERT_CHANNEL_ID = int(os.getenv("WATCHLIST_ALERT_CHANNEL_ID", 0)) 
LEADER_ROLE_ID = int(os.getenv("LEADER_ROLE_ID", 0))
COLEADER_ROLE_ID = int(os.getenv("COLEADER_ROLE_ID", 0))
AUTO_ADD_WATCHLIST_ENABLED = os.getenv("AUTO_ADD_WATCHLIST_ENABLED", "True").lower() == "true"

BOT_VERSION = "20.2.21-AntiLoop" 
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
        self.watchlist_alert_channel_id = WATCHLIST_ALERT_CHANNEL_ID if WATCHLIST_ALERT_CHANNEL_ID else CHANNEL_ID
        self.leader_role_id = LEADER_ROLE_ID
        self.coleader_role_id = COLEADER_ROLE_ID
        self.auto_add_watchlist_enabled = AUTO_ADD_WATCHLIST_ENABLED
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
        self.last_api_status = "ok"
        self.log_handler = log_handler
        self._setup_hook_done = asyncio.Event()
        logger.info(f"Instância ClashGeniusBot v{self.bot_version} criada.")

    async def setup_hook(self) -> None:
        logger.info("### Iniciando setup_hook ###")
        try:
            if MONGO_DB_URL:
                try:
                    db_name = parse_uri(MONGO_DB_URL).get('database', 'genius_db')
                    self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL, serverSelectionTimeoutMS=10000)
                    await self.mongo_client.admin.command('ping')
                    self.db = self.mongo_client[db_name]
                    logger.info(f"Conectado ao MongoDB: {db_name}")
                    await self.load_initial_state_from_db() 
                    self.db_ready.set()
                    logger.info("Estado inicial carregado do DB e db_ready definido.")
                except Exception as e:
                    logger.error(f"Falha ao conectar/configurar MongoDB: {e}", exc_info=True)
                    self.db_ready.set() 
            else:
                logger.warning("URL MongoDB não fornecida. Persistência desativada.")
                self.db_ready.set()

            logger.info("Criando tarefa coc_login_task...")
            self.loop.create_task(self.coc_login_task())

            logger.info("Inicializando WarPredictionSystemV3...")
            self.war_prediction_system = WarPredictionSystemV3(db_connection=self.db)
            self.loop.create_task(self.war_prediction_system.initialize_system())

            logger.info("--- Iniciando carregamento de Cogs ---")
            cog_files = [ 'events_cog', 'tasks_cog', 'database_cog', 'general_cog', 'cwl_planner_cog', 'clan_games_cog', 'war_advisor_cog', 'profile_cog', 'maintenance_cog', 'web_api_cog', 'admin_cog', 'donation_cog', 'slash_cog', 'watchlist_cog', 'smurf_detection_cog' ]
            loaded_cogs_count = 0
            for cog_name in cog_files:
                try:
                    logger.info(f"==> Tentando carregar Cog: {cog_name}...")
                    await self.load_extension(f'cogs.{cog_name}')
                    logger.info(f"<== Cog '{cog_name}' carregado com SUCESSO.")
                    loaded_cogs_count += 1
                except discord.ext.commands.errors.NoEntryPointError: logger.warning(f"AVISO: Cog '{cog_name}' sem 'setup'. Pulando.")
                except Exception as e: logger.critical(f"### ERRO FATAL AO CARREGAR COG '{cog_name}' ###: {e}", exc_info=True)
            logger.info(f"--- Carregamento de Cogs finalizado ({loaded_cogs_count}/{len(cog_files)} carregados) ---")

            logger.info("Criando tarefa setup_web_server...")
            self.loop.create_task(setup_web_server(self))
            logger.info("Tarefa setup_web_server criada.")

        finally:
            self._setup_hook_done.set()
            logger.info("### Finalizando setup_hook (evento _setup_hook_done definido) ###")


    async def load_initial_state_from_db(self):
        if self.db is None: logger.warning("load_initial_state_from_db sem conexão DB."); return
        logger.info("Carregando estado inicial do DB...")
        try:
            maint_config = await self.db.system_config.find_one({"_id": "maintenance_mode"})
            if maint_config: self.maintenance_mode = maint_config.get("enabled", False); logger.info(f"Modo Manutenção: {'ATIVADO' if self.maintenance_mode else 'DESATIVADO'}")
            else: logger.warning("Doc 'maintenance_mode' não encontrado.")

            bot_settings = await self.db.system_config.find_one({"_id": "bot_settings"})
            if bot_settings:
                self.channel_id = bot_settings.get("channel_id", self.channel_id)
                self.post_war_analysis_channel_id = bot_settings.get("post_war_analysis_channel_id", self.post_war_analysis_channel_id)
                self.clan_games_channel_id = bot_settings.get("clan_games_channel_id", self.clan_games_channel_id)
                self.cwl_planner_channel_id = bot_settings.get("cwl_planner_channel_id", self.cwl_planner_channel_id)
                self.donations_channel_id = bot_settings.get("donations_channel_id", self.donations_channel_id)
                self.watchlist_alert_channel_id = bot_settings.get("watchlist_alert_channel_id", self.watchlist_alert_channel_id)
                self.role_id_1star_alert = bot_settings.get("role_id_1star_alert", self.role_id_1star_alert)
                self.role_id_missed_attack = bot_settings.get("role_id_missed_attack", self.role_id_missed_attack)
                self.leader_role_id = bot_settings.get("leader_role_id", self.leader_role_id)
                self.coleader_role_id = bot_settings.get("coleader_role_id", self.coleader_role_id)
                self.maintenance_message = bot_settings.get("maintenance_message", self.maintenance_message)
                self.auto_add_watchlist_enabled = str(bot_settings.get("auto_add_watchlist_enabled", self.auto_add_watchlist_enabled)).lower() in ['true', 'on', '1', 'yes']
                logger.info("Configurações 'bot_settings' carregadas.")
            else: logger.warning("Doc 'bot_settings' não encontrado. Usando defaults.")

            processed_wars_cursor = self.db.war_history.find({}, {"_id": 1})
            self.processed_war_ids = {doc["_id"] async for doc in processed_wars_cursor}
            logger.info(f"Carregados {len(self.processed_war_ids)} IDs de guerras processadas.")
        except Exception as e: logger.error(f"Erro durante load_initial_state_from_db: {e}", exc_info=True)


    async def coc_login_task(self):
        logger.info("Iniciando tarefa de login coc_login_task...")
        login_attempts = 0; max_attempts = 5; retry_delay = 15
        while login_attempts < max_attempts:
            login_attempts += 1; logger.info(f"Tentativa login CoC ({login_attempts}/{max_attempts})...")
            try:
                self.api_client = coc.Client()
                await asyncio.wait_for(self.api_client.login(self.coc_email, self.coc_password), timeout=45.0)
                logger.info(">>> Login coc.Client BEM-SUCEDIDO. <<<")
                self.coc_client_ready.set(); logger.info("Evento coc_client_ready definido.")
                return
            except coc.LoginError as e: logger.error(f"### ERRO LOGIN CoC (Tentativa {login_attempts}) ###: {e}"); break
            except asyncio.TimeoutError: logger.error(f"### TIMEOUT LOGIN CoC (Tentativa {login_attempts}) ###: API não respondeu em 45s.")
            except Exception as e: logger.error(f"### ERRO INESPERADO login CoC (Tentativa {login_attempts}) ###: {e}", exc_info=True)
            if login_attempts < max_attempts: logger.info(f"Aguardando {retry_delay}s..."); await asyncio.sleep(retry_delay)
        logger.critical(f"### FALHA CRÍTICA: Login CoC falhou após {max_attempts} tentativas. ###")
        self.coc_client_ready.set()
        logger.warning("Evento coc_client_ready definido APESAR de falha no login CoC.")


    async def on_ready(self):
        logger.info("on_ready: Aguardando setup_hook terminar...")
        await self._setup_hook_done.wait()
        logger.info("on_ready: setup_hook terminado.")
        logger.info("="*30)
        logger.info(f'>>> BOT {self.user.name} (ID: {self.user.id}) ONLINE E PRONTO! <<<')
        logger.info(f"Versão: {self.bot_version}")
        logger.info(f"Conectado a {len(self.guilds)} servidor(es).")
        logger.info("="*30)
        try:
            synced = await self.tree.sync()
            logger.info(f"Sincronizados {len(synced)} comandos de barra globalmente no on_ready.")
        except Exception as e: logger.error(f"Falha ao sincronizar comandos no on_ready: {e}", exc_info=True)


    async def close(self):
        logger.info("Iniciando desligamento...")
        if hasattr(self, '_web_runner'):
             logger.info("Parando servidor web...")
             await self._web_runner.cleanup()
             logger.info("Servidor web parado.")
        if self.api_client: logger.info("Fechando coc.py client..."); await self.api_client.close(); logger.info("coc.py fechado.")
        if self.mongo_client: logger.info("Fechando MongoDB client..."); self.mongo_client.close(); logger.info("MongoDB fechado.")
        logger.info("Chamando super().close()...")
        await super().close()
        logger.info("Bot desligado.")

    async def get_clan_data_with_cache(self, tag: str) -> Optional[coc.Clan]:
        try:
            await asyncio.wait_for(self.coc_client_ready.wait(), timeout=45.0)
        except asyncio.TimeoutError:
            logger.error("Timeout esperando coc_client_ready em get_clan_data.")
            return None
        if not self.api_client:
             logger.error("get_clan_data: api_client não está disponível (login CoC pode ter falhado).")
             return None

        normalized_tag = coc.utils.correct_tag(tag); now = datetime.datetime.now()
        cache_entry = self.clan_cache.get(normalized_tag)
        if cache_entry and (now - cache_entry["timestamp"]).total_seconds() < self.CACHE_DURATION_SECONDS: return cache_entry["data"]
        try:
            logger.debug(f"Buscando clã {tag} na API...")
            clan_data = await self.api_client.get_clan(normalized_tag)
            self.clan_cache[normalized_tag] = {"data": clan_data, "timestamp": now}
            logger.debug(f"Clã {tag} obtido e cacheado.")
            return clan_data
        except coc.errors.NotFound: logger.warning(f"Clã {tag} não encontrado."); return None
        except coc.LoginError: logger.error("get_clan_data: Erro de login CoC ao buscar clã."); return None
        except Exception as e: logger.error(f"Erro ao obter clã {tag}: {e}", exc_info=True); return None

# --- Servidor Web ---
async def setup_web_server(bot_instance: ClashGeniusBot):
    logger.info("setup_web_server: Aguardando fim do setup_hook...")
    await bot_instance._setup_hook_done.wait()
    logger.info("setup_web_server: setup_hook terminado. Iniciando configuração do servidor web...")

    app = web.Application()

    web_api_cog = bot_instance.get_cog("Web API")
    db_cog = bot_instance.get_cog("Banco de Dados")
    profile_cog = bot_instance.get_cog("Perfis de Membros")
    
    # ATENÇÃO: NOME CORRIGIDO PARA CWLPlanner
    cwl_cog = bot_instance.get_cog("CWLPlanner")
    
    maintenance_cog = bot_instance.get_cog("Manutenção do Sistema")
    war_advisor_cog = bot_instance.get_cog("Conselheiro de Guerra IA")
    admin_cog = bot_instance.get_cog("Painel de Administração Avançado")
    watchlist_cog = bot_instance.get_cog("Lista de Observação")

    required_cogs = [ web_api_cog, db_cog, profile_cog, cwl_cog, maintenance_cog, war_advisor_cog, admin_cog, watchlist_cog ]
    if not all(required_cogs):
        missing = [name for name, inst in zip(["WebAPI","DB","Profile","CWL","Maint","Advisor","Admin","Watchlist"], required_cogs) if inst is None]
        logger.critical(f"Cogs disponíveis no bot: {list(bot_instance.cogs.keys())}")
        logger.critical(f"### ERRO FATAL: Cogs web essenciais não carregados: {', '.join(missing)}. Servidor web NÃO PODE iniciar. ###")
        return
    logger.info("Todas Cogs web encontradas.")

    async def handle_web_response(request, key, func, *args, **kwargs):
        now = datetime.datetime.now(); cache_entry = bot_instance.web_api_cache.get(key)
        force_call = kwargs.get('force_api_call', False)
        if not bot_instance.coc_client_ready.is_set():
            return web.json_response({"error": "Bot iniciando (Aguardando API CoC)..."}, status=503)
        if not bot_instance.api_client:
            return web.json_response({"error": "Falha na conexão com a API Clash of Clans."}, status=503)
        if not force_call and cache_entry and (now - cache_entry["timestamp"]).total_seconds() < bot_instance.WEB_API_CACHE_DURATION_SECONDS:
            return web.json_response(cache_entry["data"], dumps=lambda v: json.dumps(v, default=str))
        try:
            data = await func(*args, **kwargs)
            if 'error' not in data and not force_call:
                bot_instance.web_api_cache[key] = {"data": data, "timestamp": now}
            elif 'error' in data:
                 status_code = 503 if "API" in data.get('error','') else (404 if "não encontrado" in data.get('error','').lower() else 500)
                 return web.json_response(data, status=status_code, dumps=lambda v: json.dumps(v, default=str))
            return web.json_response(data, dumps=lambda v: json.dumps(v, default=str))
        except coc.LoginError:
            bot_instance.coc_client_ready.clear(); bot_instance.api_client = None; asyncio.create_task(bot_instance.coc_login_task())
            return web.json_response({"error": "Erro de autenticação com a API CoC. Tentando reconectar..."}, status=503)
        except Exception as e:
            return web.json_response({"error": f"Erro interno no servidor ao processar '{key}'."}, status=500)

    async def api_clan_handler(r): return await handle_web_response(r, 'clan', web_api_cog.fetch_clan_info_for_web)
    async def api_members_handler(r): return await handle_web_response(r, 'members', web_api_cog.fetch_clan_members_for_web)
    async def api_current_war_details_handler(r): return await handle_web_response(r, 'war_details', web_api_cog.fetch_current_war_details_for_web)
    async def api_missed_attacks_history_handler(r): return await handle_web_response(r, 'missed_attacks', web_api_cog.fetch_missed_attacks_history_for_web)
    async def api_war_log_handler(r): return await handle_web_response(r, 'war_log', web_api_cog.fetch_war_log_for_web)
    async def api_cwl_info_handler(r): return await handle_web_response(r, 'cwl', web_api_cog.fetch_cwl_info_for_web)
    async def api_highlights_handler(r): return await handle_web_response(r, 'highlights', web_api_cog.fetch_highlights_for_web)
    async def api_save_player_note_handler(request):
        player_tag = coc.utils.correct_tag(request.match_info['player_tag']); data = await request.json()
        try:
            await db_cog.save_player_note_to_db(player_tag, data.get('text', ''), data.get('priority', 'none'))
            bot_instance.web_api_cache.pop('members', None); return web.Response(status=204)
        except ConnectionError as e: return web.json_response({"error": "Erro de conexão com o banco de dados."}, status=500)
        except Exception as e: return web.json_response({"error": "Erro interno ao salvar nota."}, status=500)

    async def api_update_cwl_status_handler(request):
        player_tag = request.match_info.get('player_tag')
        if not player_tag: return web.json_response({"error": "Player tag is required."}, status=400)
        try:
            data = await request.json()
            status = data.get('status')
            if status not in ['active', 'backup']: return web.json_response({"error": "Invalid status. Must be 'active' or 'backup'."}, status=400)
            if not db_cog: return web.json_response({"error": "Internal server error (DB Cog missing)."}, status=500)
            await db_cog.update_player_cwl_status(player_tag, status)
            bot_instance.web_api_cache.pop('members', None)
            return web.json_response({"success": True, "message": f"Status for {player_tag} updated to {status}."})
        except Exception as e: return web.json_response({"error": "Internal server error while updating status."}, status=500)

    async def api_historic_war_handler(request):
        if bot_instance.db is None: return web.json_response({"error": "Banco de dados não configurado."}, status=503)
        war_id = request.match_info['war_id']
        try:
            war_doc = await bot_instance.db.war_history.find_one({"_id": war_id})
            if war_doc:
                def default_serializer(obj):
                    if isinstance(obj, (datetime.datetime, datetime.date)): return obj.isoformat()
                    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
                return web.json_response(war_doc, dumps=lambda v: json.dumps(v, default=default_serializer))
            else: return web.json_response({"error": "Guerra não encontrada."}, status=404)
        except Exception as e: return web.json_response({"error": "Erro interno ao buscar guerra histórica."}, status=500)

    async def api_member_profile_handler(request):
        if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client: return web.json_response({"error": "API CoC temporariamente indisponível."}, status=503)
        player_tag = coc.utils.correct_tag(request.match_info['player_tag']); profile_data = await profile_cog.fetch_player_profile_data(player_tag)
        return web.json_response(profile_data, status=404 if "error" in profile_data else 200)
    async def api_cwl_generate_plan_handler(request):
        if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client: return web.json_response({"error": "API CoC temporariamente indisponível."}, status=503)
        bot_instance.web_api_cache.pop('cwl_plan', None); plan = await cwl_cog.generate_rotation_plan()
        return web.json_response(plan)
    async def api_war_advisor_plan_handler(request):
        if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client: return web.json_response({"success": False, "error": "API CoC temporariamente indisponível."}, status=503)
        try:
            war = await bot_instance.api_client.get_current_war(bot_instance.clan_tag, ignore_cache=True)
            if not bot_instance.war_prediction_system or not bot_instance.war_prediction_system.is_initialized: return web.json_response({"success": False, "error": "Sistema de predição ainda inicializando."}, status=503)
            prediction_data = await bot_instance.war_prediction_system.predict_war_outcome(war, bot_instance.clan_tag)
            plan = war_advisor_cog.war_advisor.create_war_plan(war, bot_instance.clan_tag, prediction_data)
            return web.json_response(plan)
        except (coc.NotFound, coc.PrivateWarLog): return web.json_response({"success": False, "error": "Nenhuma guerra ativa ou log privado."}, status=404)
        except coc.LoginError: return web.json_response({"success": False, "error": "Erro de login com API CoC."}, status=503)
        except Exception as e: return web.json_response({"success": False, "error": "Erro interno ao gerar plano."}, status=500)
    async def api_coc_status_handler(r):
        if not admin_cog: return web.json_response({"status": "error", "message": "Admin cog não carregado."}, status=500)
        if not bot_instance.coc_client_ready.is_set(): return web.json_response({"status": "maintenance", "message": "Bot iniciando (Aguardando API CoC)..."}, status=200)
        if not bot_instance.api_client: return web.json_response({"status": "error", "message": "Falha na conexão com a API CoC."}, status=503)
        return web.json_response(await admin_cog.get_api_status())
    async def api_maintenance_message(r):
         return web.json_response({"message": bot_instance.maintenance_message})
    async def admin_get_status_handler(r):
        session=await get_session(r); is_admin=session.get('admin',False)
        return web.json_response({"status":"ok","maintenance_mode":bot_instance.maintenance_mode,"version":BOT_VERSION,"is_admin":is_admin})

    app.router.add_get("/api/clan", api_clan_handler); app.router.add_get("/api/members", api_members_handler);
    app.router.add_get("/api/current_war_details", api_current_war_details_handler); app.router.add_get("/api/missed_attacks_history", api_missed_attacks_history_handler);
    app.router.add_get("/api/war_log", api_war_log_handler); app.router.add_get("/api/cwl_info", api_cwl_info_handler);
    app.router.add_get("/api/highlights", api_highlights_handler); app.router.add_post("/api/notes/{player_tag:.*}", api_save_player_note_handler);
    app.router.add_post("/api/cwl/player_status/{player_tag:.*}", api_update_cwl_status_handler)
    app.router.add_get("/api/war_history/{war_id:.*}", api_historic_war_handler); app.router.add_get("/api/player_profile/{player_tag:.*}", api_member_profile_handler);
    app.router.add_post("/api/cwl/generate_plan", api_cwl_generate_plan_handler); app.router.add_get("/api/war_advisor_plan", api_war_advisor_plan_handler);
    app.router.add_get("/api/coc_status", api_coc_status_handler); app.router.add_get("/api/status", admin_get_status_handler);
    app.router.add_get("/api/maintenance_message", api_maintenance_message); 

    @web.middleware
    async def admin_auth_middleware(request, handler):
        session=await get_session(request)
        if not session.get('admin'): return web.json_response({"status":"unauthorized", "message": "Acesso negado."}, status=403)
        return await handler(request)
    async def api_admin_diagnostics(r): return web.json_response(await admin_cog.get_diagnostics())
    async def api_admin_get_settings(r): session = await get_session(r); return web.json_response(await admin_cog.get_settings(session))
    async def api_admin_update_settings(r): return web.json_response(await admin_cog.update_settings(await r.json()))
    async def api_admin_db_viewer(r): return web.json_response(await admin_cog.get_db_viewer_data(), dumps=lambda v: json.dumps(v, default=str))
    async def api_admin_get_watchlist(r): return web.json_response(await admin_cog.get_watchlist_admin()) 
    async def api_admin_add_watchlist(r):
        data=await r.json(); tag=data.get('player_tag'); name=data.get('player_name'); reason=data.get('reason'); details=data.get('details')
        if not tag or not reason: return web.json_response({"status":"error","message":"Tag e motivo obrigatórios."}, status=400)
        if not name:
             if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client: name = tag
             else:
                 try: player=await bot_instance.api_client.get_player(tag); name=player.name
                 except coc.NotFound: name = tag
                 except Exception as e: logger.warning(f"Erro ao buscar nome para tag {tag} em add_watchlist: {e}"); name = tag
        result = await admin_cog.add_to_watchlist_admin(tag, name, reason, details)
        if result: bot_instance.web_api_cache.pop('members',None); return web.json_response({"status":"success","message":"Jogador adicionado/atualizado na watchlist."})
        else: return web.json_response({"status":"error","message":"Erro interno ao adicionar à watchlist."},status=500)
    async def api_admin_remove_watchlist(r):
        data=await r.json(); tag=data.get('player_tag')
        if not tag: return web.json_response({"status":"error","message":"Tag obrigatória."}, status=400)
        success = await admin_cog.remove_from_watchlist_admin(tag)
        if success: bot_instance.web_api_cache.pop('members',None); return web.json_response({"status":"success","message":"Jogador removido da watchlist."})
        else:
            w_cog = bot_instance.get_cog("Lista de Observação")
            entry_exists = await w_cog.is_on_watchlist(tag) if w_cog else False
            if not entry_exists: return web.json_response({"status":"not_found","message":"Jogador não encontrado na watchlist."}, status=404)
            else: return web.json_response({"status":"error","message":"Erro interno ao remover da watchlist."}, status=500)
    async def api_admin_actions(r):
        data=await r.json(); session=await get_session(r); action=data.get("action"); payload=data.get("payload",{})
        try:
            if action=="send_announcement": return web.json_response(await admin_cog.send_announcement(payload.get("channel_id"),payload.get("message")))
            elif action=="clear_cache": return web.json_response(await admin_cog.clear_web_cache(payload.get("cache_key")))
            elif action=="force_sync_war":
                tasks_cog=bot_instance.get_cog("Tarefas em Segundo Plano")
                if tasks_cog: asyncio.create_task(tasks_cog.check_war_end_task()); return web.json_response({"status":"success","message":"Sincronização de guerra iniciada."})
                else: return web.json_response({"status":"error","message":"Cog de Tarefas não encontrado."}, status=500)
            elif action=="sync_commands":
                guild_id=session.get('guild_id')
                if not guild_id and payload.get("scope")=="guild": return web.json_response({"status":"error","message":"ID do servidor não encontrado na sessão para sync local."}, status=400)
                guild=bot_instance.get_guild(int(guild_id)) if guild_id else None
                return web.json_response(await admin_cog.sync_commands(payload.get("scope","guild"),guild))
            else: return web.json_response({"status":"error","message":"Ação desconhecida."},status=400)
        except Exception as e: return web.json_response({"status":"error","message": f"Erro interno ao processar '{action}'."}, status=500)

    admin_api_app = web.Application(middlewares=[admin_auth_middleware]);
    admin_api_app.router.add_get("/diagnostics", api_admin_diagnostics); admin_api_app.router.add_get("/settings", api_admin_get_settings);
    admin_api_app.router.add_post("/settings", api_admin_update_settings); admin_api_app.router.add_get("/db_viewer", api_admin_db_viewer);
    admin_api_app.router.add_post("/actions", api_admin_actions); admin_api_app.router.add_get("/watchlist", api_admin_get_watchlist);
    admin_api_app.router.add_post("/watchlist/add", api_admin_add_watchlist); admin_api_app.router.add_post("/watchlist/remove", api_admin_remove_watchlist);
    app.add_subapp("/api/admin/", admin_api_app);

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    async def admin_login_page(r): return web.FileResponse(os.path.join(static_dir, "admin_login.html"))
    async def admin_panel_page(r):
        session=await get_session(r);
        if not session.get('admin'): return web.HTTPFound('/admin')
        return web.FileResponse(os.path.join(static_dir,"admin_panel.html"))
    async def admin_login_handler(r):
        data=await r.post(); guild_id_from_form = data.get('guild_id', '')
        if data.get('password')==ADMIN_PASSWORD:
            session=await get_session(r); session['admin']=True; session['guild_id']= guild_id_from_form if guild_id_from_form else None
            return web.HTTPFound('/admin/panel')
        else: return web.HTTPFound(f"/admin?error=1&guild_id={guild_id_from_form}")
    async def admin_logout_handler(r):
        session=await get_session(r); session.pop('admin',None); session.pop('guild_id',None); 
        return web.HTTPFound('/admin')
    async def admin_toggle_maintenance_handler(r):
        session=await get_session(r);
        if not session.get('admin'): return web.json_response({"status":"unauthorized"}, status=403)
        return await maintenance_cog.toggle_maintenance_mode_web()
    async def admin_send_test_embed_handler(r):
        session=await get_session(r);
        if not session.get('admin'): return web.json_response({"status":"unauthorized"}, status=403)
        return await maintenance_cog.send_test_embed_web()
    async def painel_handler(r):
        api_status_response = await api_coc_status_handler(r)
        api_status = json.loads(api_status_response.text) if api_status_response.text else {"status": "error"}
        session=await get_session(r); is_admin=session.get('admin',False)
        if (bot_instance.maintenance_mode or api_status.get("status") in ["maintenance", "error"]) and not is_admin:
            return web.HTTPFound('/maintenance')
        return web.FileResponse(os.path.join(static_dir,"painel.html"))
    async def maintenance_page_handler(r):
        return web.FileResponse(os.path.join(static_dir, "maintenance.html"))

    app.router.add_static('/static/', path=static_dir, name='static');
    app.router.add_get("/", lambda r: web.HTTPFound('/painel')); app.router.add_get("/painel", painel_handler);
    app.router.add_get("/maintenance", maintenance_page_handler); app.router.add_get("/admin", admin_login_page);
    app.router.add_post("/admin/login", admin_login_handler); app.router.add_get("/admin/logout", admin_logout_handler);
    app.router.add_get("/admin/panel", admin_panel_page); app.router.add_post("/admin/toggle_maintenance", admin_toggle_maintenance_handler);
    app.router.add_post("/admin/send_test_embed", admin_send_test_embed_handler);

    try: secret_key_bytes = FERNET_KEY.encode(); secret_key_decoded = base64.urlsafe_b64decode(secret_key_bytes)
    except (AttributeError, ValueError, TypeError): secret_key_decoded = FERNET_KEY
    if not secret_key_decoded: secret_key_decoded = Fernet.generate_key()
    setup_session(app, EncryptedCookieStorage(secret_key_decoded))

    runner = web.AppRunner(app);
    await runner.setup();
    port = int(os.environ.get("PORT", 10000)); 
    site = web.TCPSite(runner, '0.0.0.0', port)
    try:
        await site.start()
        bot_instance._web_runner = runner
        logger.info(f">>> SERVIDOR WEB INICIADO EM :{port} <<<")
    except Exception as e:
        logger.critical(f"### ERRO FATAL WEB SERVER ###: {e}", exc_info=True)


async def main():
    intents = discord.Intents.default(); intents.message_content = True; intents.members = True; intents.guilds = True
    bot = ClashGeniusBot(command_prefix="!", intents=intents)
    try:
        logger.info("Iniciando bot (bot.start)...")
        await bot.start(DISCORD_TOKEN)
    except discord.errors.LoginFailure: logger.critical("### FALHA LOGIN DISCORD: Token inválido. ###")
    except discord.errors.HTTPException as e:
        # ---> PROTEÇÃO ANTI-LOOP PARA RATE LIMIT 429 <---
        if e.status == 429:
            logger.critical("### ERRO 429 (RATE LIMIT) DETECTADO ###")
            logger.critical("O Discord bloqueou temporariamente este IP/Token devido a muitas tentativas.")
            logger.critical("Entrando em modo de espera (SLEEP) por 1 HORA para evitar reinício automático do Render.")
            logger.critical("NÃO REINICIE MANUALMENTE AGORA. ESPERE.")
            time.sleep(3600) # Dorme por 1 hora antes de deixar o script morrer.
        else:
            logger.critical(f"### ERRO HTTP NÃO TRATADO ###: {e}", exc_info=True)
    except KeyboardInterrupt: logger.info("Bot desligado manualmente.")
    except Exception as e: logger.critical(f"### ERRO FATAL NÃO TRATADO NO LOOP PRINCIPAL ###: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()
        logger.info("Processo finalizado.")

if __name__ == "__main__":
    logger.info("="*10 + f" INICIANDO ClashGeniusBot v{BOT_VERSION} " + "="*10)
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.info("Programa interrompido pelo usuário.")
    except Exception as e: logger.critical(f"### ERRO FATAL (asyncio) ###: {e}", exc_info=True)# -*- coding: utf-8 -*-
# Versão 20.2.21-AntiLoop1

import os
import logging
import asyncio
import datetime
from typing import Dict, Any, Optional, List
import time

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

# --- Configuração de Logging ---
class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity=50):
        super().__init__()
        self.capacity = capacity
        self.buffer = []
    def emit(self, record):
        self.buffer.append(self.format(record))
        if len(self.buffer) > self.capacity: self.buffer.pop(0)

log_handler = MemoryLogHandler()
log_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log_handler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logging.getLogger().addHandler(log_handler)
logger = logging.getLogger("clash_genius_bot")

# --- Carregamento de Variáveis de Ambiente ---
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
WATCHLIST_ALERT_CHANNEL_ID = int(os.getenv("WATCHLIST_ALERT_CHANNEL_ID", 0)) 
LEADER_ROLE_ID = int(os.getenv("LEADER_ROLE_ID", 0))
COLEADER_ROLE_ID = int(os.getenv("COLEADER_ROLE_ID", 0))
AUTO_ADD_WATCHLIST_ENABLED = os.getenv("AUTO_ADD_WATCHLIST_ENABLED", "True").lower() == "true"

BOT_VERSION = "20.2.21-AntiLoop" 
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
        self.watchlist_alert_channel_id = WATCHLIST_ALERT_CHANNEL_ID if WATCHLIST_ALERT_CHANNEL_ID else CHANNEL_ID
        self.leader_role_id = LEADER_ROLE_ID
        self.coleader_role_id = COLEADER_ROLE_ID
        self.auto_add_watchlist_enabled = AUTO_ADD_WATCHLIST_ENABLED
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
        self.last_api_status = "ok"
        self.log_handler = log_handler
        self._setup_hook_done = asyncio.Event()
        logger.info(f"Instância ClashGeniusBot v{self.bot_version} criada.")

    async def setup_hook(self) -> None:
        logger.info("### Iniciando setup_hook ###")
        try:
            if MONGO_DB_URL:
                try:
                    db_name = parse_uri(MONGO_DB_URL).get('database', 'genius_db')
                    self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL, serverSelectionTimeoutMS=10000)
                    await self.mongo_client.admin.command('ping')
                    self.db = self.mongo_client[db_name]
                    logger.info(f"Conectado ao MongoDB: {db_name}")
                    await self.load_initial_state_from_db() 
                    self.db_ready.set()
                    logger.info("Estado inicial carregado do DB e db_ready definido.")
                except Exception as e:
                    logger.error(f"Falha ao conectar/configurar MongoDB: {e}", exc_info=True)
                    self.db_ready.set() 
            else:
                logger.warning("URL MongoDB não fornecida. Persistência desativada.")
                self.db_ready.set()

            logger.info("Criando tarefa coc_login_task...")
            self.loop.create_task(self.coc_login_task())

            logger.info("Inicializando WarPredictionSystemV3...")
            self.war_prediction_system = WarPredictionSystemV3(db_connection=self.db)
            self.loop.create_task(self.war_prediction_system.initialize_system())

            logger.info("--- Iniciando carregamento de Cogs ---")
            cog_files = [ 'events_cog', 'tasks_cog', 'database_cog', 'general_cog', 'cwl_planner_cog', 'clan_games_cog', 'war_advisor_cog', 'profile_cog', 'maintenance_cog', 'web_api_cog', 'admin_cog', 'donation_cog', 'slash_cog', 'watchlist_cog', 'smurf_detection_cog' ]
            loaded_cogs_count = 0
            for cog_name in cog_files:
                try:
                    logger.info(f"==> Tentando carregar Cog: {cog_name}...")
                    await self.load_extension(f'cogs.{cog_name}')
                    logger.info(f"<== Cog '{cog_name}' carregado com SUCESSO.")
                    loaded_cogs_count += 1
                except discord.ext.commands.errors.NoEntryPointError: logger.warning(f"AVISO: Cog '{cog_name}' sem 'setup'. Pulando.")
                except Exception as e: logger.critical(f"### ERRO FATAL AO CARREGAR COG '{cog_name}' ###: {e}", exc_info=True)
            logger.info(f"--- Carregamento de Cogs finalizado ({loaded_cogs_count}/{len(cog_files)} carregados) ---")

            logger.info("Criando tarefa setup_web_server...")
            self.loop.create_task(setup_web_server(self))
            logger.info("Tarefa setup_web_server criada.")

        finally:
            self._setup_hook_done.set()
            logger.info("### Finalizando setup_hook (evento _setup_hook_done definido) ###")


    async def load_initial_state_from_db(self):
        if self.db is None: logger.warning("load_initial_state_from_db sem conexão DB."); return
        logger.info("Carregando estado inicial do DB...")
        try:
            maint_config = await self.db.system_config.find_one({"_id": "maintenance_mode"})
            if maint_config: self.maintenance_mode = maint_config.get("enabled", False); logger.info(f"Modo Manutenção: {'ATIVADO' if self.maintenance_mode else 'DESATIVADO'}")
            else: logger.warning("Doc 'maintenance_mode' não encontrado.")

            bot_settings = await self.db.system_config.find_one({"_id": "bot_settings"})
            if bot_settings:
                self.channel_id = bot_settings.get("channel_id", self.channel_id)
                self.post_war_analysis_channel_id = bot_settings.get("post_war_analysis_channel_id", self.post_war_analysis_channel_id)
                self.clan_games_channel_id = bot_settings.get("clan_games_channel_id", self.clan_games_channel_id)
                self.cwl_planner_channel_id = bot_settings.get("cwl_planner_channel_id", self.cwl_planner_channel_id)
                self.donations_channel_id = bot_settings.get("donations_channel_id", self.donations_channel_id)
                self.watchlist_alert_channel_id = bot_settings.get("watchlist_alert_channel_id", self.watchlist_alert_channel_id)
                self.role_id_1star_alert = bot_settings.get("role_id_1star_alert", self.role_id_1star_alert)
                self.role_id_missed_attack = bot_settings.get("role_id_missed_attack", self.role_id_missed_attack)
                self.leader_role_id = bot_settings.get("leader_role_id", self.leader_role_id)
                self.coleader_role_id = bot_settings.get("coleader_role_id", self.coleader_role_id)
                self.maintenance_message = bot_settings.get("maintenance_message", self.maintenance_message)
                self.auto_add_watchlist_enabled = str(bot_settings.get("auto_add_watchlist_enabled", self.auto_add_watchlist_enabled)).lower() in ['true', 'on', '1', 'yes']
                logger.info("Configurações 'bot_settings' carregadas.")
            else: logger.warning("Doc 'bot_settings' não encontrado. Usando defaults.")

            processed_wars_cursor = self.db.war_history.find({}, {"_id": 1})
            self.processed_war_ids = {doc["_id"] async for doc in processed_wars_cursor}
            logger.info(f"Carregados {len(self.processed_war_ids)} IDs de guerras processadas.")
        except Exception as e: logger.error(f"Erro durante load_initial_state_from_db: {e}", exc_info=True)


    async def coc_login_task(self):
        logger.info("Iniciando tarefa de login coc_login_task...")
        login_attempts = 0; max_attempts = 5; retry_delay = 15
        while login_attempts < max_attempts:
            login_attempts += 1; logger.info(f"Tentativa login CoC ({login_attempts}/{max_attempts})...")
            try:
                self.api_client = coc.Client()
                await asyncio.wait_for(self.api_client.login(self.coc_email, self.coc_password), timeout=45.0)
                logger.info(">>> Login coc.Client BEM-SUCEDIDO. <<<")
                self.coc_client_ready.set(); logger.info("Evento coc_client_ready definido.")
                return
            except coc.LoginError as e: logger.error(f"### ERRO LOGIN CoC (Tentativa {login_attempts}) ###: {e}"); break
            except asyncio.TimeoutError: logger.error(f"### TIMEOUT LOGIN CoC (Tentativa {login_attempts}) ###: API não respondeu em 45s.")
            except Exception as e: logger.error(f"### ERRO INESPERADO login CoC (Tentativa {login_attempts}) ###: {e}", exc_info=True)
            if login_attempts < max_attempts: logger.info(f"Aguardando {retry_delay}s..."); await asyncio.sleep(retry_delay)
        logger.critical(f"### FALHA CRÍTICA: Login CoC falhou após {max_attempts} tentativas. ###")
        self.coc_client_ready.set()
        logger.warning("Evento coc_client_ready definido APESAR de falha no login CoC.")


    async def on_ready(self):
        logger.info("on_ready: Aguardando setup_hook terminar...")
        await self._setup_hook_done.wait()
        logger.info("on_ready: setup_hook terminado.")
        logger.info("="*30)
        logger.info(f'>>> BOT {self.user.name} (ID: {self.user.id}) ONLINE E PRONTO! <<<')
        logger.info(f"Versão: {self.bot_version}")
        logger.info(f"Conectado a {len(self.guilds)} servidor(es).")
        logger.info("="*30)
        try:
            synced = await self.tree.sync()
            logger.info(f"Sincronizados {len(synced)} comandos de barra globalmente no on_ready.")
        except Exception as e: logger.error(f"Falha ao sincronizar comandos no on_ready: {e}", exc_info=True)


    async def close(self):
        logger.info("Iniciando desligamento...")
        if hasattr(self, '_web_runner'):
             logger.info("Parando servidor web...")
             await self._web_runner.cleanup()
             logger.info("Servidor web parado.")
        if self.api_client: logger.info("Fechando coc.py client..."); await self.api_client.close(); logger.info("coc.py fechado.")
        if self.mongo_client: logger.info("Fechando MongoDB client..."); self.mongo_client.close(); logger.info("MongoDB fechado.")
        logger.info("Chamando super().close()...")
        await super().close()
        logger.info("Bot desligado.")

    async def get_clan_data_with_cache(self, tag: str) -> Optional[coc.Clan]:
        try:
            await asyncio.wait_for(self.coc_client_ready.wait(), timeout=45.0)
        except asyncio.TimeoutError:
            logger.error("Timeout esperando coc_client_ready em get_clan_data.")
            return None
        if not self.api_client:
             logger.error("get_clan_data: api_client não está disponível (login CoC pode ter falhado).")
             return None

        normalized_tag = coc.utils.correct_tag(tag); now = datetime.datetime.now()
        cache_entry = self.clan_cache.get(normalized_tag)
        if cache_entry and (now - cache_entry["timestamp"]).total_seconds() < self.CACHE_DURATION_SECONDS: return cache_entry["data"]
        try:
            logger.debug(f"Buscando clã {tag} na API...")
            clan_data = await self.api_client.get_clan(normalized_tag)
            self.clan_cache[normalized_tag] = {"data": clan_data, "timestamp": now}
            logger.debug(f"Clã {tag} obtido e cacheado.")
            return clan_data
        except coc.errors.NotFound: logger.warning(f"Clã {tag} não encontrado."); return None
        except coc.LoginError: logger.error("get_clan_data: Erro de login CoC ao buscar clã."); return None
        except Exception as e: logger.error(f"Erro ao obter clã {tag}: {e}", exc_info=True); return None

# --- Servidor Web ---
async def setup_web_server(bot_instance: ClashGeniusBot):
    logger.info("setup_web_server: Aguardando fim do setup_hook...")
    await bot_instance._setup_hook_done.wait()
    logger.info("setup_web_server: setup_hook terminado. Iniciando configuração do servidor web...")

    app = web.Application()

    web_api_cog = bot_instance.get_cog("Web API")
    db_cog = bot_instance.get_cog("Banco de Dados")
    profile_cog = bot_instance.get_cog("Perfis de Membros")
    
    # ATENÇÃO: NOME CORRIGIDO PARA CWLPlanner
    cwl_cog = bot_instance.get_cog("CWLPlanner")
    
    maintenance_cog = bot_instance.get_cog("Manutenção do Sistema")
    war_advisor_cog = bot_instance.get_cog("Conselheiro de Guerra IA")
    admin_cog = bot_instance.get_cog("Painel de Administração Avançado")
    watchlist_cog = bot_instance.get_cog("Lista de Observação")

    required_cogs = [ web_api_cog, db_cog, profile_cog, cwl_cog, maintenance_cog, war_advisor_cog, admin_cog, watchlist_cog ]
    if not all(required_cogs):
        missing = [name for name, inst in zip(["WebAPI","DB","Profile","CWL","Maint","Advisor","Admin","Watchlist"], required_cogs) if inst is None]
        logger.critical(f"Cogs disponíveis no bot: {list(bot_instance.cogs.keys())}")
        logger.critical(f"### ERRO FATAL: Cogs web essenciais não carregados: {', '.join(missing)}. Servidor web NÃO PODE iniciar. ###")
        return
    logger.info("Todas Cogs web encontradas.")

    async def handle_web_response(request, key, func, *args, **kwargs):
        now = datetime.datetime.now(); cache_entry = bot_instance.web_api_cache.get(key)
        force_call = kwargs.get('force_api_call', False)
        if not bot_instance.coc_client_ready.is_set():
            return web.json_response({"error": "Bot iniciando (Aguardando API CoC)..."}, status=503)
        if not bot_instance.api_client:
            return web.json_response({"error": "Falha na conexão com a API Clash of Clans."}, status=503)
        if not force_call and cache_entry and (now - cache_entry["timestamp"]).total_seconds() < bot_instance.WEB_API_CACHE_DURATION_SECONDS:
            return web.json_response(cache_entry["data"], dumps=lambda v: json.dumps(v, default=str))
        try:
            data = await func(*args, **kwargs)
            if 'error' not in data and not force_call:
                bot_instance.web_api_cache[key] = {"data": data, "timestamp": now}
            elif 'error' in data:
                 status_code = 503 if "API" in data.get('error','') else (404 if "não encontrado" in data.get('error','').lower() else 500)
                 return web.json_response(data, status=status_code, dumps=lambda v: json.dumps(v, default=str))
            return web.json_response(data, dumps=lambda v: json.dumps(v, default=str))
        except coc.LoginError:
            bot_instance.coc_client_ready.clear(); bot_instance.api_client = None; asyncio.create_task(bot_instance.coc_login_task())
            return web.json_response({"error": "Erro de autenticação com a API CoC. Tentando reconectar..."}, status=503)
        except Exception as e:
            return web.json_response({"error": f"Erro interno no servidor ao processar '{key}'."}, status=500)

    async def api_clan_handler(r): return await handle_web_response(r, 'clan', web_api_cog.fetch_clan_info_for_web)
    async def api_members_handler(r): return await handle_web_response(r, 'members', web_api_cog.fetch_clan_members_for_web)
    async def api_current_war_details_handler(r): return await handle_web_response(r, 'war_details', web_api_cog.fetch_current_war_details_for_web)
    async def api_missed_attacks_history_handler(r): return await handle_web_response(r, 'missed_attacks', web_api_cog.fetch_missed_attacks_history_for_web)
    async def api_war_log_handler(r): return await handle_web_response(r, 'war_log', web_api_cog.fetch_war_log_for_web)
    async def api_cwl_info_handler(r): return await handle_web_response(r, 'cwl', web_api_cog.fetch_cwl_info_for_web)
    async def api_highlights_handler(r): return await handle_web_response(r, 'highlights', web_api_cog.fetch_highlights_for_web)
    async def api_save_player_note_handler(request):
        player_tag = coc.utils.correct_tag(request.match_info['player_tag']); data = await request.json()
        try:
            await db_cog.save_player_note_to_db(player_tag, data.get('text', ''), data.get('priority', 'none'))
            bot_instance.web_api_cache.pop('members', None); return web.Response(status=204)
        except ConnectionError as e: return web.json_response({"error": "Erro de conexão com o banco de dados."}, status=500)
        except Exception as e: return web.json_response({"error": "Erro interno ao salvar nota."}, status=500)

    async def api_update_cwl_status_handler(request):
        player_tag = request.match_info.get('player_tag')
        if not player_tag: return web.json_response({"error": "Player tag is required."}, status=400)
        try:
            data = await request.json()
            status = data.get('status')
            if status not in ['active', 'backup']: return web.json_response({"error": "Invalid status. Must be 'active' or 'backup'."}, status=400)
            if not db_cog: return web.json_response({"error": "Internal server error (DB Cog missing)."}, status=500)
            await db_cog.update_player_cwl_status(player_tag, status)
            bot_instance.web_api_cache.pop('members', None)
            return web.json_response({"success": True, "message": f"Status for {player_tag} updated to {status}."})
        except Exception as e: return web.json_response({"error": "Internal server error while updating status."}, status=500)

    async def api_historic_war_handler(request):
        if bot_instance.db is None: return web.json_response({"error": "Banco de dados não configurado."}, status=503)
        war_id = request.match_info['war_id']
        try:
            war_doc = await bot_instance.db.war_history.find_one({"_id": war_id})
            if war_doc:
                def default_serializer(obj):
                    if isinstance(obj, (datetime.datetime, datetime.date)): return obj.isoformat()
                    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
                return web.json_response(war_doc, dumps=lambda v: json.dumps(v, default=default_serializer))
            else: return web.json_response({"error": "Guerra não encontrada."}, status=404)
        except Exception as e: return web.json_response({"error": "Erro interno ao buscar guerra histórica."}, status=500)

    async def api_member_profile_handler(request):
        if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client: return web.json_response({"error": "API CoC temporariamente indisponível."}, status=503)
        player_tag = coc.utils.correct_tag(request.match_info['player_tag']); profile_data = await profile_cog.fetch_player_profile_data(player_tag)
        return web.json_response(profile_data, status=404 if "error" in profile_data else 200)
    async def api_cwl_generate_plan_handler(request):
        if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client: return web.json_response({"error": "API CoC temporariamente indisponível."}, status=503)
        bot_instance.web_api_cache.pop('cwl_plan', None); plan = await cwl_cog.generate_rotation_plan()
        return web.json_response(plan)
    async def api_war_advisor_plan_handler(request):
        if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client: return web.json_response({"success": False, "error": "API CoC temporariamente indisponível."}, status=503)
        try:
            war = await bot_instance.api_client.get_current_war(bot_instance.clan_tag, ignore_cache=True)
            if not bot_instance.war_prediction_system or not bot_instance.war_prediction_system.is_initialized: return web.json_response({"success": False, "error": "Sistema de predição ainda inicializando."}, status=503)
            prediction_data = await bot_instance.war_prediction_system.predict_war_outcome(war, bot_instance.clan_tag)
            plan = war_advisor_cog.war_advisor.create_war_plan(war, bot_instance.clan_tag, prediction_data)
            return web.json_response(plan)
        except (coc.NotFound, coc.PrivateWarLog): return web.json_response({"success": False, "error": "Nenhuma guerra ativa ou log privado."}, status=404)
        except coc.LoginError: return web.json_response({"success": False, "error": "Erro de login com API CoC."}, status=503)
        except Exception as e: return web.json_response({"success": False, "error": "Erro interno ao gerar plano."}, status=500)
    async def api_coc_status_handler(r):
        if not admin_cog: return web.json_response({"status": "error", "message": "Admin cog não carregado."}, status=500)
        if not bot_instance.coc_client_ready.is_set(): return web.json_response({"status": "maintenance", "message": "Bot iniciando (Aguardando API CoC)..."}, status=200)
        if not bot_instance.api_client: return web.json_response({"status": "error", "message": "Falha na conexão com a API CoC."}, status=503)
        return web.json_response(await admin_cog.get_api_status())
    async def api_maintenance_message(r):
         return web.json_response({"message": bot_instance.maintenance_message})
    async def admin_get_status_handler(r):
        session=await get_session(r); is_admin=session.get('admin',False)
        return web.json_response({"status":"ok","maintenance_mode":bot_instance.maintenance_mode,"version":BOT_VERSION,"is_admin":is_admin})

    app.router.add_get("/api/clan", api_clan_handler); app.router.add_get("/api/members", api_members_handler);
    app.router.add_get("/api/current_war_details", api_current_war_details_handler); app.router.add_get("/api/missed_attacks_history", api_missed_attacks_history_handler);
    app.router.add_get("/api/war_log", api_war_log_handler); app.router.add_get("/api/cwl_info", api_cwl_info_handler);
    app.router.add_get("/api/highlights", api_highlights_handler); app.router.add_post("/api/notes/{player_tag:.*}", api_save_player_note_handler);
    app.router.add_post("/api/cwl/player_status/{player_tag:.*}", api_update_cwl_status_handler)
    app.router.add_get("/api/war_history/{war_id:.*}", api_historic_war_handler); app.router.add_get("/api/player_profile/{player_tag:.*}", api_member_profile_handler);
    app.router.add_post("/api/cwl/generate_plan", api_cwl_generate_plan_handler); app.router.add_get("/api/war_advisor_plan", api_war_advisor_plan_handler);
    app.router.add_get("/api/coc_status", api_coc_status_handler); app.router.add_get("/api/status", admin_get_status_handler);
    app.router.add_get("/api/maintenance_message", api_maintenance_message); 

    @web.middleware
    async def admin_auth_middleware(request, handler):
        session=await get_session(request)
        if not session.get('admin'): return web.json_response({"status":"unauthorized", "message": "Acesso negado."}, status=403)
        return await handler(request)
    async def api_admin_diagnostics(r): return web.json_response(await admin_cog.get_diagnostics())
    async def api_admin_get_settings(r): session = await get_session(r); return web.json_response(await admin_cog.get_settings(session))
    async def api_admin_update_settings(r): return web.json_response(await admin_cog.update_settings(await r.json()))
    async def api_admin_db_viewer(r): return web.json_response(await admin_cog.get_db_viewer_data(), dumps=lambda v: json.dumps(v, default=str))
    async def api_admin_get_watchlist(r): return web.json_response(await admin_cog.get_watchlist_admin()) 
    async def api_admin_add_watchlist(r):
        data=await r.json(); tag=data.get('player_tag'); name=data.get('player_name'); reason=data.get('reason'); details=data.get('details')
        if not tag or not reason: return web.json_response({"status":"error","message":"Tag e motivo obrigatórios."}, status=400)
        if not name:
             if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client: name = tag
             else:
                 try: player=await bot_instance.api_client.get_player(tag); name=player.name
                 except coc.NotFound: name = tag
                 except Exception as e: logger.warning(f"Erro ao buscar nome para tag {tag} em add_watchlist: {e}"); name = tag
        result = await admin_cog.add_to_watchlist_admin(tag, name, reason, details)
        if result: bot_instance.web_api_cache.pop('members',None); return web.json_response({"status":"success","message":"Jogador adicionado/atualizado na watchlist."})
        else: return web.json_response({"status":"error","message":"Erro interno ao adicionar à watchlist."},status=500)
    async def api_admin_remove_watchlist(r):
        data=await r.json(); tag=data.get('player_tag')
        if not tag: return web.json_response({"status":"error","message":"Tag obrigatória."}, status=400)
        success = await admin_cog.remove_from_watchlist_admin(tag)
        if success: bot_instance.web_api_cache.pop('members',None); return web.json_response({"status":"success","message":"Jogador removido da watchlist."})
        else:
            w_cog = bot_instance.get_cog("Lista de Observação")
            entry_exists = await w_cog.is_on_watchlist(tag) if w_cog else False
            if not entry_exists: return web.json_response({"status":"not_found","message":"Jogador não encontrado na watchlist."}, status=404)
            else: return web.json_response({"status":"error","message":"Erro interno ao remover da watchlist."}, status=500)
    async def api_admin_actions(r):
        data=await r.json(); session=await get_session(r); action=data.get("action"); payload=data.get("payload",{})
        try:
            if action=="send_announcement": return web.json_response(await admin_cog.send_announcement(payload.get("channel_id"),payload.get("message")))
            elif action=="clear_cache": return web.json_response(await admin_cog.clear_web_cache(payload.get("cache_key")))
            elif action=="force_sync_war":
                tasks_cog=bot_instance.get_cog("Tarefas em Segundo Plano")
                if tasks_cog: asyncio.create_task(tasks_cog.check_war_end_task()); return web.json_response({"status":"success","message":"Sincronização de guerra iniciada."})
                else: return web.json_response({"status":"error","message":"Cog de Tarefas não encontrado."}, status=500)
            elif action=="sync_commands":
                guild_id=session.get('guild_id')
                if not guild_id and payload.get("scope")=="guild": return web.json_response({"status":"error","message":"ID do servidor não encontrado na sessão para sync local."}, status=400)
                guild=bot_instance.get_guild(int(guild_id)) if guild_id else None
                return web.json_response(await admin_cog.sync_commands(payload.get("scope","guild"),guild))
            else: return web.json_response({"status":"error","message":"Ação desconhecida."},status=400)
        except Exception as e: return web.json_response({"status":"error","message": f"Erro interno ao processar '{action}'."}, status=500)

    admin_api_app = web.Application(middlewares=[admin_auth_middleware]);
    admin_api_app.router.add_get("/diagnostics", api_admin_diagnostics); admin_api_app.router.add_get("/settings", api_admin_get_settings);
    admin_api_app.router.add_post("/settings", api_admin_update_settings); admin_api_app.router.add_get("/db_viewer", api_admin_db_viewer);
    admin_api_app.router.add_post("/actions", api_admin_actions); admin_api_app.router.add_get("/watchlist", api_admin_get_watchlist);
    admin_api_app.router.add_post("/watchlist/add", api_admin_add_watchlist); admin_api_app.router.add_post("/watchlist/remove", api_admin_remove_watchlist);
    app.add_subapp("/api/admin/", admin_api_app);

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    async def admin_login_page(r): return web.FileResponse(os.path.join(static_dir, "admin_login.html"))
    async def admin_panel_page(r):
        session=await get_session(r);
        if not session.get('admin'): return web.HTTPFound('/admin')
        return web.FileResponse(os.path.join(static_dir,"admin_panel.html"))
    async def admin_login_handler(r):
        data=await r.post(); guild_id_from_form = data.get('guild_id', '')
        if data.get('password')==ADMIN_PASSWORD:
            session=await get_session(r); session['admin']=True; session['guild_id']= guild_id_from_form if guild_id_from_form else None
            return web.HTTPFound('/admin/panel')
        else: return web.HTTPFound(f"/admin?error=1&guild_id={guild_id_from_form}")
    async def admin_logout_handler(r):
        session=await get_session(r); session.pop('admin',None); session.pop('guild_id',None); 
        return web.HTTPFound('/admin')
    async def admin_toggle_maintenance_handler(r):
        session=await get_session(r);
        if not session.get('admin'): return web.json_response({"status":"unauthorized"}, status=403)
        return await maintenance_cog.toggle_maintenance_mode_web()
    async def admin_send_test_embed_handler(r):
        session=await get_session(r);
        if not session.get('admin'): return web.json_response({"status":"unauthorized"}, status=403)
        return await maintenance_cog.send_test_embed_web()
    async def painel_handler(r):
        api_status_response = await api_coc_status_handler(r)
        api_status = json.loads(api_status_response.text) if api_status_response.text else {"status": "error"}
        session=await get_session(r); is_admin=session.get('admin',False)
        if (bot_instance.maintenance_mode or api_status.get("status") in ["maintenance", "error"]) and not is_admin:
            return web.HTTPFound('/maintenance')
        return web.FileResponse(os.path.join(static_dir,"painel.html"))
    async def maintenance_page_handler(r):
        return web.FileResponse(os.path.join(static_dir, "maintenance.html"))

    app.router.add_static('/static/', path=static_dir, name='static');
    app.router.add_get("/", lambda r: web.HTTPFound('/painel')); app.router.add_get("/painel", painel_handler);
    app.router.add_get("/maintenance", maintenance_page_handler); app.router.add_get("/admin", admin_login_page);
    app.router.add_post("/admin/login", admin_login_handler); app.router.add_get("/admin/logout", admin_logout_handler);
    app.router.add_get("/admin/panel", admin_panel_page); app.router.add_post("/admin/toggle_maintenance", admin_toggle_maintenance_handler);
    app.router.add_post("/admin/send_test_embed", admin_send_test_embed_handler);

    try: secret_key_bytes = FERNET_KEY.encode(); secret_key_decoded = base64.urlsafe_b64decode(secret_key_bytes)
    except (AttributeError, ValueError, TypeError): secret_key_decoded = FERNET_KEY
    if not secret_key_decoded: secret_key_decoded = Fernet.generate_key()
    setup_session(app, EncryptedCookieStorage(secret_key_decoded))

    runner = web.AppRunner(app);
    await runner.setup();
    port = int(os.environ.get("PORT", 10000)); 
    site = web.TCPSite(runner, '0.0.0.0', port)
    try:
        await site.start()
        bot_instance._web_runner = runner
        logger.info(f">>> SERVIDOR WEB INICIADO EM :{port} <<<")
    except Exception as e:
        logger.critical(f"### ERRO FATAL WEB SERVER ###: {e}", exc_info=True)


async def main():
    intents = discord.Intents.default(); intents.message_content = True; intents.members = True; intents.guilds = True
    bot = ClashGeniusBot(command_prefix="!", intents=intents)
    try:
        logger.info("Iniciando bot (bot.start)...")
        await bot.start(DISCORD_TOKEN)
    except discord.errors.LoginFailure: logger.critical("### FALHA LOGIN DISCORD: Token inválido. ###")
    except discord.errors.HTTPException as e:
        # ---> PROTEÇÃO ANTI-LOOP PARA RATE LIMIT 429 <---
        if e.status == 429:
            logger.critical("### ERRO 429 (RATE LIMIT) DETECTADO ###")
            logger.critical("O Discord bloqueou temporariamente este IP/Token devido a muitas tentativas.")
            logger.critical("Entrando em modo de espera (SLEEP) por 1 HORA para evitar reinício automático do Render.")
            logger.critical("NÃO REINICIE MANUALMENTE AGORA. ESPERE.")
            time.sleep(3600) # Dorme por 1 hora antes de deixar o script morrer.
        else:
            logger.critical(f"### ERRO HTTP NÃO TRATADO ###: {e}", exc_info=True)
    except KeyboardInterrupt: logger.info("Bot desligado manualmente.")
    except Exception as e: logger.critical(f"### ERRO FATAL NÃO TRATADO NO LOOP PRINCIPAL ###: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()
        logger.info("Processo finalizado.")

if __name__ == "__main__":
    logger.info("="*10 + f" INICIANDO ClashGeniusBot v{BOT_VERSION} " + "="*10)
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.info("Programa interrompido pelo usuário.")
    except Exception as e: logger.critical(f"### ERRO FATAL (asyncio) ###: {e}", exc_info=True)# -*- coding: utf-8 -*-
# Versão 20.2.21-AntiLoop1

import os
import logging
import asyncio
import datetime
from typing import Dict, Any, Optional, List
import time

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

# --- Configuração de Logging ---
class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity=50):
        super().__init__()
        self.capacity = capacity
        self.buffer = []
    def emit(self, record):
        self.buffer.append(self.format(record))
        if len(self.buffer) > self.capacity: self.buffer.pop(0)

log_handler = MemoryLogHandler()
log_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log_handler.setFormatter(formatter)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logging.getLogger().addHandler(log_handler)
logger = logging.getLogger("clash_genius_bot")

# --- Carregamento de Variáveis de Ambiente ---
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
WATCHLIST_ALERT_CHANNEL_ID = int(os.getenv("WATCHLIST_ALERT_CHANNEL_ID", 0)) 
LEADER_ROLE_ID = int(os.getenv("LEADER_ROLE_ID", 0))
COLEADER_ROLE_ID = int(os.getenv("COLEADER_ROLE_ID", 0))
AUTO_ADD_WATCHLIST_ENABLED = os.getenv("AUTO_ADD_WATCHLIST_ENABLED", "True").lower() == "true"

BOT_VERSION = "20.2.21-AntiLoop" 
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
        self.watchlist_alert_channel_id = WATCHLIST_ALERT_CHANNEL_ID if WATCHLIST_ALERT_CHANNEL_ID else CHANNEL_ID
        self.leader_role_id = LEADER_ROLE_ID
        self.coleader_role_id = COLEADER_ROLE_ID
        self.auto_add_watchlist_enabled = AUTO_ADD_WATCHLIST_ENABLED
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
        self.last_api_status = "ok"
        self.log_handler = log_handler
        self._setup_hook_done = asyncio.Event()
        logger.info(f"Instância ClashGeniusBot v{self.bot_version} criada.")

    async def setup_hook(self) -> None:
        logger.info("### Iniciando setup_hook ###")
        try:
            if MONGO_DB_URL:
                try:
                    db_name = parse_uri(MONGO_DB_URL).get('database', 'genius_db')
                    self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL, serverSelectionTimeoutMS=10000)
                    await self.mongo_client.admin.command('ping')
                    self.db = self.mongo_client[db_name]
                    logger.info(f"Conectado ao MongoDB: {db_name}")
                    await self.load_initial_state_from_db() 
                    self.db_ready.set()
                    logger.info("Estado inicial carregado do DB e db_ready definido.")
                except Exception as e:
                    logger.error(f"Falha ao conectar/configurar MongoDB: {e}", exc_info=True)
                    self.db_ready.set() 
            else:
                logger.warning("URL MongoDB não fornecida. Persistência desativada.")
                self.db_ready.set()

            logger.info("Criando tarefa coc_login_task...")
            self.loop.create_task(self.coc_login_task())

            logger.info("Inicializando WarPredictionSystemV3...")
            self.war_prediction_system = WarPredictionSystemV3(db_connection=self.db)
            self.loop.create_task(self.war_prediction_system.initialize_system())

            logger.info("--- Iniciando carregamento de Cogs ---")
            cog_files = [ 'events_cog', 'tasks_cog', 'database_cog', 'general_cog', 'cwl_planner_cog', 'clan_games_cog', 'war_advisor_cog', 'profile_cog', 'maintenance_cog', 'web_api_cog', 'admin_cog', 'donation_cog', 'slash_cog', 'watchlist_cog', 'smurf_detection_cog' ]
            loaded_cogs_count = 0
            for cog_name in cog_files:
                try:
                    logger.info(f"==> Tentando carregar Cog: {cog_name}...")
                    await self.load_extension(f'cogs.{cog_name}')
                    logger.info(f"<== Cog '{cog_name}' carregado com SUCESSO.")
                    loaded_cogs_count += 1
                except discord.ext.commands.errors.NoEntryPointError: logger.warning(f"AVISO: Cog '{cog_name}' sem 'setup'. Pulando.")
                except Exception as e: logger.critical(f"### ERRO FATAL AO CARREGAR COG '{cog_name}' ###: {e}", exc_info=True)
            logger.info(f"--- Carregamento de Cogs finalizado ({loaded_cogs_count}/{len(cog_files)} carregados) ---")

            logger.info("Criando tarefa setup_web_server...")
            self.loop.create_task(setup_web_server(self))
            logger.info("Tarefa setup_web_server criada.")

        finally:
            self._setup_hook_done.set()
            logger.info("### Finalizando setup_hook (evento _setup_hook_done definido) ###")


    async def load_initial_state_from_db(self):
        if self.db is None: logger.warning("load_initial_state_from_db sem conexão DB."); return
        logger.info("Carregando estado inicial do DB...")
        try:
            maint_config = await self.db.system_config.find_one({"_id": "maintenance_mode"})
            if maint_config: self.maintenance_mode = maint_config.get("enabled", False); logger.info(f"Modo Manutenção: {'ATIVADO' if self.maintenance_mode else 'DESATIVADO'}")
            else: logger.warning("Doc 'maintenance_mode' não encontrado.")

            bot_settings = await self.db.system_config.find_one({"_id": "bot_settings"})
            if bot_settings:
                self.channel_id = bot_settings.get("channel_id", self.channel_id)
                self.post_war_analysis_channel_id = bot_settings.get("post_war_analysis_channel_id", self.post_war_analysis_channel_id)
                self.clan_games_channel_id = bot_settings.get("clan_games_channel_id", self.clan_games_channel_id)
                self.cwl_planner_channel_id = bot_settings.get("cwl_planner_channel_id", self.cwl_planner_channel_id)
                self.donations_channel_id = bot_settings.get("donations_channel_id", self.donations_channel_id)
                self.watchlist_alert_channel_id = bot_settings.get("watchlist_alert_channel_id", self.watchlist_alert_channel_id)
                self.role_id_1star_alert = bot_settings.get("role_id_1star_alert", self.role_id_1star_alert)
                self.role_id_missed_attack = bot_settings.get("role_id_missed_attack", self.role_id_missed_attack)
                self.leader_role_id = bot_settings.get("leader_role_id", self.leader_role_id)
                self.coleader_role_id = bot_settings.get("coleader_role_id", self.coleader_role_id)
                self.maintenance_message = bot_settings.get("maintenance_message", self.maintenance_message)
                self.auto_add_watchlist_enabled = str(bot_settings.get("auto_add_watchlist_enabled", self.auto_add_watchlist_enabled)).lower() in ['true', 'on', '1', 'yes']
                logger.info("Configurações 'bot_settings' carregadas.")
            else: logger.warning("Doc 'bot_settings' não encontrado. Usando defaults.")

            processed_wars_cursor = self.db.war_history.find({}, {"_id": 1})
            self.processed_war_ids = {doc["_id"] async for doc in processed_wars_cursor}
            logger.info(f"Carregados {len(self.processed_war_ids)} IDs de guerras processadas.")
        except Exception as e: logger.error(f"Erro durante load_initial_state_from_db: {e}", exc_info=True)


    async def coc_login_task(self):
        logger.info("Iniciando tarefa de login coc_login_task...")
        login_attempts = 0; max_attempts = 5; retry_delay = 15
        while login_attempts < max_attempts:
            login_attempts += 1; logger.info(f"Tentativa login CoC ({login_attempts}/{max_attempts})...")
            try:
                self.api_client = coc.Client()
                await asyncio.wait_for(self.api_client.login(self.coc_email, self.coc_password), timeout=45.0)
                logger.info(">>> Login coc.Client BEM-SUCEDIDO. <<<")
                self.coc_client_ready.set(); logger.info("Evento coc_client_ready definido.")
                return
            except coc.LoginError as e: logger.error(f"### ERRO LOGIN CoC (Tentativa {login_attempts}) ###: {e}"); break
            except asyncio.TimeoutError: logger.error(f"### TIMEOUT LOGIN CoC (Tentativa {login_attempts}) ###: API não respondeu em 45s.")
            except Exception as e: logger.error(f"### ERRO INESPERADO login CoC (Tentativa {login_attempts}) ###: {e}", exc_info=True)
            if login_attempts < max_attempts: logger.info(f"Aguardando {retry_delay}s..."); await asyncio.sleep(retry_delay)
        logger.critical(f"### FALHA CRÍTICA: Login CoC falhou após {max_attempts} tentativas. ###")
        self.coc_client_ready.set()
        logger.warning("Evento coc_client_ready definido APESAR de falha no login CoC.")


    async def on_ready(self):
        logger.info("on_ready: Aguardando setup_hook terminar...")
        await self._setup_hook_done.wait()
        logger.info("on_ready: setup_hook terminado.")
        logger.info("="*30)
        logger.info(f'>>> BOT {self.user.name} (ID: {self.user.id}) ONLINE E PRONTO! <<<')
        logger.info(f"Versão: {self.bot_version}")
        logger.info(f"Conectado a {len(self.guilds)} servidor(es).")
        logger.info("="*30)
        try:
            synced = await self.tree.sync()
            logger.info(f"Sincronizados {len(synced)} comandos de barra globalmente no on_ready.")
        except Exception as e: logger.error(f"Falha ao sincronizar comandos no on_ready: {e}", exc_info=True)


    async def close(self):
        logger.info("Iniciando desligamento...")
        if hasattr(self, '_web_runner'):
             logger.info("Parando servidor web...")
             await self._web_runner.cleanup()
             logger.info("Servidor web parado.")
        if self.api_client: logger.info("Fechando coc.py client..."); await self.api_client.close(); logger.info("coc.py fechado.")
        if self.mongo_client: logger.info("Fechando MongoDB client..."); self.mongo_client.close(); logger.info("MongoDB fechado.")
        logger.info("Chamando super().close()...")
        await super().close()
        logger.info("Bot desligado.")

    async def get_clan_data_with_cache(self, tag: str) -> Optional[coc.Clan]:
        try:
            await asyncio.wait_for(self.coc_client_ready.wait(), timeout=45.0)
        except asyncio.TimeoutError:
            logger.error("Timeout esperando coc_client_ready em get_clan_data.")
            return None
        if not self.api_client:
             logger.error("get_clan_data: api_client não está disponível (login CoC pode ter falhado).")
             return None

        normalized_tag = coc.utils.correct_tag(tag); now = datetime.datetime.now()
        cache_entry = self.clan_cache.get(normalized_tag)
        if cache_entry and (now - cache_entry["timestamp"]).total_seconds() < self.CACHE_DURATION_SECONDS: return cache_entry["data"]
        try:
            logger.debug(f"Buscando clã {tag} na API...")
            clan_data = await self.api_client.get_clan(normalized_tag)
            self.clan_cache[normalized_tag] = {"data": clan_data, "timestamp": now}
            logger.debug(f"Clã {tag} obtido e cacheado.")
            return clan_data
        except coc.errors.NotFound: logger.warning(f"Clã {tag} não encontrado."); return None
        except coc.LoginError: logger.error("get_clan_data: Erro de login CoC ao buscar clã."); return None
        except Exception as e: logger.error(f"Erro ao obter clã {tag}: {e}", exc_info=True); return None

# --- Servidor Web ---
async def setup_web_server(bot_instance: ClashGeniusBot):
    logger.info("setup_web_server: Aguardando fim do setup_hook...")
    await bot_instance._setup_hook_done.wait()
    logger.info("setup_web_server: setup_hook terminado. Iniciando configuração do servidor web...")

    app = web.Application()

    web_api_cog = bot_instance.get_cog("Web API")
    db_cog = bot_instance.get_cog("Banco de Dados")
    profile_cog = bot_instance.get_cog("Perfis de Membros")
    
    # ATENÇÃO: NOME CORRIGIDO PARA CWLPlanner
    cwl_cog = bot_instance.get_cog("CWLPlanner")
    
    maintenance_cog = bot_instance.get_cog("Manutenção do Sistema")
    war_advisor_cog = bot_instance.get_cog("Conselheiro de Guerra IA")
    admin_cog = bot_instance.get_cog("Painel de Administração Avançado")
    watchlist_cog = bot_instance.get_cog("Lista de Observação")

    required_cogs = [ web_api_cog, db_cog, profile_cog, cwl_cog, maintenance_cog, war_advisor_cog, admin_cog, watchlist_cog ]
    if not all(required_cogs):
        missing = [name for name, inst in zip(["WebAPI","DB","Profile","CWL","Maint","Advisor","Admin","Watchlist"], required_cogs) if inst is None]
        logger.critical(f"Cogs disponíveis no bot: {list(bot_instance.cogs.keys())}")
        logger.critical(f"### ERRO FATAL: Cogs web essenciais não carregados: {', '.join(missing)}. Servidor web NÃO PODE iniciar. ###")
        return
    logger.info("Todas Cogs web encontradas.")

    async def handle_web_response(request, key, func, *args, **kwargs):
        now = datetime.datetime.now(); cache_entry = bot_instance.web_api_cache.get(key)
        force_call = kwargs.get('force_api_call', False)
        if not bot_instance.coc_client_ready.is_set():
            return web.json_response({"error": "Bot iniciando (Aguardando API CoC)..."}, status=503)
        if not bot_instance.api_client:
            return web.json_response({"error": "Falha na conexão com a API Clash of Clans."}, status=503)
        if not force_call and cache_entry and (now - cache_entry["timestamp"]).total_seconds() < bot_instance.WEB_API_CACHE_DURATION_SECONDS:
            return web.json_response(cache_entry["data"], dumps=lambda v: json.dumps(v, default=str))
        try:
            data = await func(*args, **kwargs)
            if 'error' not in data and not force_call:
                bot_instance.web_api_cache[key] = {"data": data, "timestamp": now}
            elif 'error' in data:
                 status_code = 503 if "API" in data.get('error','') else (404 if "não encontrado" in data.get('error','').lower() else 500)
                 return web.json_response(data, status=status_code, dumps=lambda v: json.dumps(v, default=str))
            return web.json_response(data, dumps=lambda v: json.dumps(v, default=str))
        except coc.LoginError:
            bot_instance.coc_client_ready.clear(); bot_instance.api_client = None; asyncio.create_task(bot_instance.coc_login_task())
            return web.json_response({"error": "Erro de autenticação com a API CoC. Tentando reconectar..."}, status=503)
        except Exception as e:
            return web.json_response({"error": f"Erro interno no servidor ao processar '{key}'."}, status=500)

    async def api_clan_handler(r): return await handle_web_response(r, 'clan', web_api_cog.fetch_clan_info_for_web)
    async def api_members_handler(r): return await handle_web_response(r, 'members', web_api_cog.fetch_clan_members_for_web)
    async def api_current_war_details_handler(r): return await handle_web_response(r, 'war_details', web_api_cog.fetch_current_war_details_for_web)
    async def api_missed_attacks_history_handler(r): return await handle_web_response(r, 'missed_attacks', web_api_cog.fetch_missed_attacks_history_for_web)
    async def api_war_log_handler(r): return await handle_web_response(r, 'war_log', web_api_cog.fetch_war_log_for_web)
    async def api_cwl_info_handler(r): return await handle_web_response(r, 'cwl', web_api_cog.fetch_cwl_info_for_web)
    async def api_highlights_handler(r): return await handle_web_response(r, 'highlights', web_api_cog.fetch_highlights_for_web)
    async def api_save_player_note_handler(request):
        player_tag = coc.utils.correct_tag(request.match_info['player_tag']); data = await request.json()
        try:
            await db_cog.save_player_note_to_db(player_tag, data.get('text', ''), data.get('priority', 'none'))
            bot_instance.web_api_cache.pop('members', None); return web.Response(status=204)
        except ConnectionError as e: return web.json_response({"error": "Erro de conexão com o banco de dados."}, status=500)
        except Exception as e: return web.json_response({"error": "Erro interno ao salvar nota."}, status=500)

    async def api_update_cwl_status_handler(request):
        player_tag = request.match_info.get('player_tag')
        if not player_tag: return web.json_response({"error": "Player tag is required."}, status=400)
        try:
            data = await request.json()
            status = data.get('status')
            if status not in ['active', 'backup']: return web.json_response({"error": "Invalid status. Must be 'active' or 'backup'."}, status=400)
            if not db_cog: return web.json_response({"error": "Internal server error (DB Cog missing)."}, status=500)
            await db_cog.update_player_cwl_status(player_tag, status)
            bot_instance.web_api_cache.pop('members', None)
            return web.json_response({"success": True, "message": f"Status for {player_tag} updated to {status}."})
        except Exception as e: return web.json_response({"error": "Internal server error while updating status."}, status=500)

    async def api_historic_war_handler(request):
        if bot_instance.db is None: return web.json_response({"error": "Banco de dados não configurado."}, status=503)
        war_id = request.match_info['war_id']
        try:
            war_doc = await bot_instance.db.war_history.find_one({"_id": war_id})
            if war_doc:
                def default_serializer(obj):
                    if isinstance(obj, (datetime.datetime, datetime.date)): return obj.isoformat()
                    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
                return web.json_response(war_doc, dumps=lambda v: json.dumps(v, default=default_serializer))
            else: return web.json_response({"error": "Guerra não encontrada."}, status=404)
        except Exception as e: return web.json_response({"error": "Erro interno ao buscar guerra histórica."}, status=500)

    async def api_member_profile_handler(request):
        if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client: return web.json_response({"error": "API CoC temporariamente indisponível."}, status=503)
        player_tag = coc.utils.correct_tag(request.match_info['player_tag']); profile_data = await profile_cog.fetch_player_profile_data(player_tag)
        return web.json_response(profile_data, status=404 if "error" in profile_data else 200)
    async def api_cwl_generate_plan_handler(request):
        if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client: return web.json_response({"error": "API CoC temporariamente indisponível."}, status=503)
        bot_instance.web_api_cache.pop('cwl_plan', None); plan = await cwl_cog.generate_rotation_plan()
        return web.json_response(plan)
    async def api_war_advisor_plan_handler(request):
        if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client: return web.json_response({"success": False, "error": "API CoC temporariamente indisponível."}, status=503)
        try:
            war = await bot_instance.api_client.get_current_war(bot_instance.clan_tag, ignore_cache=True)
            if not bot_instance.war_prediction_system or not bot_instance.war_prediction_system.is_initialized: return web.json_response({"success": False, "error": "Sistema de predição ainda inicializando."}, status=503)
            prediction_data = await bot_instance.war_prediction_system.predict_war_outcome(war, bot_instance.clan_tag)
            plan = war_advisor_cog.war_advisor.create_war_plan(war, bot_instance.clan_tag, prediction_data)
            return web.json_response(plan)
        except (coc.NotFound, coc.PrivateWarLog): return web.json_response({"success": False, "error": "Nenhuma guerra ativa ou log privado."}, status=404)
        except coc.LoginError: return web.json_response({"success": False, "error": "Erro de login com API CoC."}, status=503)
        except Exception as e: return web.json_response({"success": False, "error": "Erro interno ao gerar plano."}, status=500)
    async def api_coc_status_handler(r):
        if not admin_cog: return web.json_response({"status": "error", "message": "Admin cog não carregado."}, status=500)
        if not bot_instance.coc_client_ready.is_set(): return web.json_response({"status": "maintenance", "message": "Bot iniciando (Aguardando API CoC)..."}, status=200)
        if not bot_instance.api_client: return web.json_response({"status": "error", "message": "Falha na conexão com a API CoC."}, status=503)
        return web.json_response(await admin_cog.get_api_status())
    async def api_maintenance_message(r):
         return web.json_response({"message": bot_instance.maintenance_message})
    async def admin_get_status_handler(r):
        session=await get_session(r); is_admin=session.get('admin',False)
        return web.json_response({"status":"ok","maintenance_mode":bot_instance.maintenance_mode,"version":BOT_VERSION,"is_admin":is_admin})

    app.router.add_get("/api/clan", api_clan_handler); app.router.add_get("/api/members", api_members_handler);
    app.router.add_get("/api/current_war_details", api_current_war_details_handler); app.router.add_get("/api/missed_attacks_history", api_missed_attacks_history_handler);
    app.router.add_get("/api/war_log", api_war_log_handler); app.router.add_get("/api/cwl_info", api_cwl_info_handler);
    app.router.add_get("/api/highlights", api_highlights_handler); app.router.add_post("/api/notes/{player_tag:.*}", api_save_player_note_handler);
    app.router.add_post("/api/cwl/player_status/{player_tag:.*}", api_update_cwl_status_handler)
    app.router.add_get("/api/war_history/{war_id:.*}", api_historic_war_handler); app.router.add_get("/api/player_profile/{player_tag:.*}", api_member_profile_handler);
    app.router.add_post("/api/cwl/generate_plan", api_cwl_generate_plan_handler); app.router.add_get("/api/war_advisor_plan", api_war_advisor_plan_handler);
    app.router.add_get("/api/coc_status", api_coc_status_handler); app.router.add_get("/api/status", admin_get_status_handler);
    app.router.add_get("/api/maintenance_message", api_maintenance_message); 

    @web.middleware
    async def admin_auth_middleware(request, handler):
        session=await get_session(request)
        if not session.get('admin'): return web.json_response({"status":"unauthorized", "message": "Acesso negado."}, status=403)
        return await handler(request)
    async def api_admin_diagnostics(r): return web.json_response(await admin_cog.get_diagnostics())
    async def api_admin_get_settings(r): session = await get_session(r); return web.json_response(await admin_cog.get_settings(session))
    async def api_admin_update_settings(r): return web.json_response(await admin_cog.update_settings(await r.json()))
    async def api_admin_db_viewer(r): return web.json_response(await admin_cog.get_db_viewer_data(), dumps=lambda v: json.dumps(v, default=str))
    async def api_admin_get_watchlist(r): return web.json_response(await admin_cog.get_watchlist_admin()) 
    async def api_admin_add_watchlist(r):
        data=await r.json(); tag=data.get('player_tag'); name=data.get('player_name'); reason=data.get('reason'); details=data.get('details')
        if not tag or not reason: return web.json_response({"status":"error","message":"Tag e motivo obrigatórios."}, status=400)
        if not name:
             if not bot_instance.coc_client_ready.is_set() or not bot_instance.api_client: name = tag
             else:
                 try: player=await bot_instance.api_client.get_player(tag); name=player.name
                 except coc.NotFound: name = tag
                 except Exception as e: logger.warning(f"Erro ao buscar nome para tag {tag} em add_watchlist: {e}"); name = tag
        result = await admin_cog.add_to_watchlist_admin(tag, name, reason, details)
        if result: bot_instance.web_api_cache.pop('members',None); return web.json_response({"status":"success","message":"Jogador adicionado/atualizado na watchlist."})
        else: return web.json_response({"status":"error","message":"Erro interno ao adicionar à watchlist."},status=500)
    async def api_admin_remove_watchlist(r):
        data=await r.json(); tag=data.get('player_tag')
        if not tag: return web.json_response({"status":"error","message":"Tag obrigatória."}, status=400)
        success = await admin_cog.remove_from_watchlist_admin(tag)
        if success: bot_instance.web_api_cache.pop('members',None); return web.json_response({"status":"success","message":"Jogador removido da watchlist."})
        else:
            w_cog = bot_instance.get_cog("Lista de Observação")
            entry_exists = await w_cog.is_on_watchlist(tag) if w_cog else False
            if not entry_exists: return web.json_response({"status":"not_found","message":"Jogador não encontrado na watchlist."}, status=404)
            else: return web.json_response({"status":"error","message":"Erro interno ao remover da watchlist."}, status=500)
    async def api_admin_actions(r):
        data=await r.json(); session=await get_session(r); action=data.get("action"); payload=data.get("payload",{})
        try:
            if action=="send_announcement": return web.json_response(await admin_cog.send_announcement(payload.get("channel_id"),payload.get("message")))
            elif action=="clear_cache": return web.json_response(await admin_cog.clear_web_cache(payload.get("cache_key")))
            elif action=="force_sync_war":
                tasks_cog=bot_instance.get_cog("Tarefas em Segundo Plano")
                if tasks_cog: asyncio.create_task(tasks_cog.check_war_end_task()); return web.json_response({"status":"success","message":"Sincronização de guerra iniciada."})
                else: return web.json_response({"status":"error","message":"Cog de Tarefas não encontrado."}, status=500)
            elif action=="sync_commands":
                guild_id=session.get('guild_id')
                if not guild_id and payload.get("scope")=="guild": return web.json_response({"status":"error","message":"ID do servidor não encontrado na sessão para sync local."}, status=400)
                guild=bot_instance.get_guild(int(guild_id)) if guild_id else None
                return web.json_response(await admin_cog.sync_commands(payload.get("scope","guild"),guild))
            else: return web.json_response({"status":"error","message":"Ação desconhecida."},status=400)
        except Exception as e: return web.json_response({"status":"error","message": f"Erro interno ao processar '{action}'."}, status=500)

    admin_api_app = web.Application(middlewares=[admin_auth_middleware]);
    admin_api_app.router.add_get("/diagnostics", api_admin_diagnostics); admin_api_app.router.add_get("/settings", api_admin_get_settings);
    admin_api_app.router.add_post("/settings", api_admin_update_settings); admin_api_app.router.add_get("/db_viewer", api_admin_db_viewer);
    admin_api_app.router.add_post("/actions", api_admin_actions); admin_api_app.router.add_get("/watchlist", api_admin_get_watchlist);
    admin_api_app.router.add_post("/watchlist/add", api_admin_add_watchlist); admin_api_app.router.add_post("/watchlist/remove", api_admin_remove_watchlist);
    app.add_subapp("/api/admin/", admin_api_app);

    static_dir = os.path.join(os.path.dirname(__file__), "static")
    async def admin_login_page(r): return web.FileResponse(os.path.join(static_dir, "admin_login.html"))
    async def admin_panel_page(r):
        session=await get_session(r);
        if not session.get('admin'): return web.HTTPFound('/admin')
        return web.FileResponse(os.path.join(static_dir,"admin_panel.html"))
    async def admin_login_handler(r):
        data=await r.post(); guild_id_from_form = data.get('guild_id', '')
        if data.get('password')==ADMIN_PASSWORD:
            session=await get_session(r); session['admin']=True; session['guild_id']= guild_id_from_form if guild_id_from_form else None
            return web.HTTPFound('/admin/panel')
        else: return web.HTTPFound(f"/admin?error=1&guild_id={guild_id_from_form}")
    async def admin_logout_handler(r):
        session=await get_session(r); session.pop('admin',None); session.pop('guild_id',None); 
        return web.HTTPFound('/admin')
    async def admin_toggle_maintenance_handler(r):
        session=await get_session(r);
        if not session.get('admin'): return web.json_response({"status":"unauthorized"}, status=403)
        return await maintenance_cog.toggle_maintenance_mode_web()
    async def admin_send_test_embed_handler(r):
        session=await get_session(r);
        if not session.get('admin'): return web.json_response({"status":"unauthorized"}, status=403)
        return await maintenance_cog.send_test_embed_web()
    async def painel_handler(r):
        api_status_response = await api_coc_status_handler(r)
        api_status = json.loads(api_status_response.text) if api_status_response.text else {"status": "error"}
        session=await get_session(r); is_admin=session.get('admin',False)
        if (bot_instance.maintenance_mode or api_status.get("status") in ["maintenance", "error"]) and not is_admin:
            return web.HTTPFound('/maintenance')
        return web.FileResponse(os.path.join(static_dir,"painel.html"))
    async def maintenance_page_handler(r):
        return web.FileResponse(os.path.join(static_dir, "maintenance.html"))

    app.router.add_static('/static/', path=static_dir, name='static');
    app.router.add_get("/", lambda r: web.HTTPFound('/painel')); app.router.add_get("/painel", painel_handler);
    app.router.add_get("/maintenance", maintenance_page_handler); app.router.add_get("/admin", admin_login_page);
    app.router.add_post("/admin/login", admin_login_handler); app.router.add_get("/admin/logout", admin_logout_handler);
    app.router.add_get("/admin/panel", admin_panel_page); app.router.add_post("/admin/toggle_maintenance", admin_toggle_maintenance_handler);
    app.router.add_post("/admin/send_test_embed", admin_send_test_embed_handler);

    try: secret_key_bytes = FERNET_KEY.encode(); secret_key_decoded = base64.urlsafe_b64decode(secret_key_bytes)
    except (AttributeError, ValueError, TypeError): secret_key_decoded = FERNET_KEY
    if not secret_key_decoded: secret_key_decoded = Fernet.generate_key()
    setup_session(app, EncryptedCookieStorage(secret_key_decoded))

    runner = web.AppRunner(app);
    await runner.setup();
    port = int(os.environ.get("PORT", 10000)); 
    site = web.TCPSite(runner, '0.0.0.0', port)
    try:
        await site.start()
        bot_instance._web_runner = runner
        logger.info(f">>> SERVIDOR WEB INICIADO EM :{port} <<<")
    except Exception as e:
        logger.critical(f"### ERRO FATAL WEB SERVER ###: {e}", exc_info=True)


async def main():
    intents = discord.Intents.default(); intents.message_content = True; intents.members = True; intents.guilds = True
    bot = ClashGeniusBot(command_prefix="!", intents=intents)
    try:
        logger.info("Iniciando bot (bot.start)...")
        await bot.start(DISCORD_TOKEN)
    except discord.errors.LoginFailure: logger.critical("### FALHA LOGIN DISCORD: Token inválido. ###")
    except discord.errors.HTTPException as e:
        # ---> PROTEÇÃO ANTI-LOOP PARA RATE LIMIT 429 <---
        if e.status == 429:
            logger.critical("### ERRO 429 (RATE LIMIT) DETECTADO ###")
            logger.critical("O Discord bloqueou temporariamente este IP/Token devido a muitas tentativas.")
            logger.critical("Entrando em modo de espera (SLEEP) por 1 HORA para evitar reinício automático do Render.")
            logger.critical("NÃO REINICIE MANUALMENTE AGORA. ESPERE.")
            time.sleep(3600) # Dorme por 1 hora antes de deixar o script morrer.
        else:
            logger.critical(f"### ERRO HTTP NÃO TRATADO ###: {e}", exc_info=True)
    except KeyboardInterrupt: logger.info("Bot desligado manualmente.")
    except Exception as e: logger.critical(f"### ERRO FATAL NÃO TRATADO NO LOOP PRINCIPAL ###: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            await bot.close()
        logger.info("Processo finalizado.")

if __name__ == "__main__":
    logger.info("="*10 + f" INICIANDO ClashGeniusBot v{BOT_VERSION} " + "="*10)
    try: asyncio.run(main())
    except KeyboardInterrupt: logger.info("Programa interrompido pelo usuário.")
    except Exception as e: logger.critical(f"### ERRO FATAL (asyncio) ###: {e}", exc_info=True)
