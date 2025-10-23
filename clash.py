# -*- coding: utf-8 -*-
# Versão 20.2.16-Watchlist-Final-Debug

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
# --- Fim Configuração de Logging ---

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
WATCHLIST_ALERT_CHANNEL_ID = int(os.getenv("WATCHLIST_ALERT_CHANNEL_ID", "1390479489401753732"))
LEADER_ROLE_ID = int(os.getenv("LEADER_ROLE_ID", "1362076878458065041"))
COLEADER_ROLE_ID = int(os.getenv("COLEADER_ROLE_ID", "1362076878458065040"))
AUTO_ADD_WATCHLIST_ENABLED = os.getenv("AUTO_ADD_WATCHLIST_ENABLED", "True").lower() == "true"
# --- Fim Variáveis de Ambiente ---

BOT_VERSION = "20.2.16-Watchlist-Final-Debug" # Atualiza a versão
TIMEZONE = pytz.timezone('America/Sao_Paulo')

class ClashGeniusBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # --- Atribuição de Configurações ---
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
        self.watchlist_alert_channel_id = WATCHLIST_ALERT_CHANNEL_ID
        self.leader_role_id = LEADER_ROLE_ID
        self.coleader_role_id = COLEADER_ROLE_ID
        self.auto_add_watchlist_enabled = AUTO_ADD_WATCHLIST_ENABLED
        self.bot_version = BOT_VERSION
        self.timezone = TIMEZONE
        self.base_url = BASE_URL
        self.maintenance_mode = False
        self.maintenance_message = "O painel está em manutenção. Voltaremos em breve!"
        # --- Fim Atribuição ---
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
        logger.info(f"Instância ClashGeniusBot v{self.bot_version} criada.") # Log Adicional

    async def setup_hook(self) -> None:
        logger.info("### Iniciando setup_hook ###") # Log Adicional
        # --- Conexão DB ---
        if MONGO_DB_URL:
            try:
                db_name = parse_uri(MONGO_DB_URL).get('database', 'genius_db')
                self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)
                # Teste de conexão rápido
                await self.mongo_client.admin.command('ping')
                self.db = self.mongo_client[db_name]
                logger.info(f"Conectado ao MongoDB: {db_name}")
                await self.load_initial_state_from_db()
                self.db_ready.set()
                logger.info("Estado inicial carregado do DB e db_ready definido.") # Log Adicional
            except Exception as e:
                logger.error(f"Falha ao conectar/configurar MongoDB: {e}", exc_info=True)
                # Não definimos db_ready para sinalizar o problema
        else:
            logger.warning("URL do MongoDB não fornecida. Recursos de persistência desativados.")
            self.db_ready.set() # Define como pronto mesmo sem DB para não bloquear Cogs
        # --- Fim DB ---

        # --- War Predictor ---
        logger.info("Inicializando WarPredictionSystemV3...") # Log Adicional
        self.war_prediction_system = WarPredictionSystemV3(db_connection=self.db)
        await self.war_prediction_system.initialize_system()
        logger.info("WarPredictionSystemV3 inicializado.") # Log Adicional
        # --- Fim War Predictor ---

        # --- Carregamento de Cogs ---
        logger.info("--- Iniciando carregamento de Cogs ---") # Log Adicional
        cog_files = [
            'events_cog', 'tasks_cog', 'database_cog', 'general_cog',
            'cwl_planner_cog', 'clan_games_cog', 'war_advisor_cog', 'profile_cog',
            'maintenance_cog', 'web_api_cog', 'admin_cog', 'donation_cog',
            'slash_cog', 'watchlist_cog'
        ]
        loaded_cogs_count = 0 # Contador
        for cog_name in cog_files:
            try:
                logger.info(f"==> Tentando carregar Cog: {cog_name}...") # Log Adicional
                await self.load_extension(f'cogs.{cog_name}')
                logger.info(f"<== Cog '{cog_name}' carregado com SUCESSO.") # Log Adicional
                loaded_cogs_count += 1
            except discord.ext.commands.errors.NoEntryPointError:
                 logger.warning(f"AVISO: Cog '{cog_name}' não possui função 'setup'. Pulando.") # Apenas aviso
            except Exception as e:
                # Log CRÍTICO para erros inesperados durante o carregamento
                logger.critical(f"### ERRO FATAL AO CARREGAR COG '{cog_name}' ###: {e}", exc_info=True)
                # Poderíamos optar por parar o bot aqui se uma Cog essencial falhar
                # raise e # Descomente para parar o bot se uma Cog falhar
        logger.info(f"--- Carregamento de Cogs finalizado ({loaded_cogs_count}/{len(cog_files)} carregados com sucesso) ---") # Log Adicional
        # --- Fim Cogs ---

        # --- Tarefas Assíncronas ---
        logger.info("Criando tarefas assíncronas (coc_login_task, setup_web_server)...") # Log Adicional
        self.loop.create_task(self.coc_login_task())
        self.loop.create_task(setup_web_server(self))
        logger.info("Tarefas assíncronas criadas.") # Log Adicional
        # --- Fim Tarefas ---
        logger.info("### Finalizando setup_hook ###") # Log Adicional


    async def load_initial_state_from_db(self):
        if self.db is None:
             logger.warning("load_initial_state_from_db chamado sem conexão DB.")
             return
        logger.info("Carregando estado inicial do DB (maintenance, settings)...") # Log Adicional
        try: # Bloco try/except para capturar erros específicos do DB aqui
            maint_config = await self.db.system_config.find_one({"_id": "maintenance_mode"})
            if maint_config:
                self.maintenance_mode = maint_config.get("enabled", False)
                logger.info(f"Modo Manutenção carregado: {'ATIVADO' if self.maintenance_mode else 'DESATIVADO'}")
            else:
                 logger.warning("Documento 'maintenance_mode' não encontrado na DB.")

            bot_settings = await self.db.system_config.find_one({"_id": "bot_settings"})
            if bot_settings:
                # Carrega configurações com get para evitar KeyError e loga cada uma
                self.channel_id = bot_settings.get("channel_id", self.channel_id)
                self.post_war_analysis_channel_id = bot_settings.get("post_war_analysis_channel_id", self.post_war_analysis_channel_id)
                self.clan_games_channel_id = bot_settings.get("clan_games_channel_id", self.clan_games_channel_id)
                self.cwl_planner_channel_id = bot_settings.get("cwl_planner_channel_id", self.cwl_planner_channel_id)
                self.donations_channel_id = bot_settings.get("donations_channel_id", self.donations_channel_id)
                self.role_id_1star_alert = bot_settings.get("role_id_1star_alert", self.role_id_1star_alert)
                self.role_id_missed_attack = bot_settings.get("role_id_missed_attack", self.role_id_missed_attack)
                self.maintenance_message = bot_settings.get("maintenance_message", self.maintenance_message)
                self.watchlist_alert_channel_id = bot_settings.get("watchlist_alert_channel_id", self.watchlist_alert_channel_id)
                self.leader_role_id = bot_settings.get("leader_role_id", self.leader_role_id)
                self.coleader_role_id = bot_settings.get("coleader_role_id", self.coleader_role_id)
                self.auto_add_watchlist_enabled = bot_settings.get("auto_add_watchlist_enabled", self.auto_add_watchlist_enabled)
                logger.info("Configurações do 'bot_settings' carregadas do DB.")
                # Log detalhado das configurações carregadas (opcional, pode ser muito verboso)
                # logger.debug(f"Configurações carregadas: channel_id={self.channel_id}, watchlist_channel={self.watchlist_alert_channel_id}, ...")
            else:
                logger.warning("Documento 'bot_settings' não encontrado na DB. Usando valores padrão do código.")

            processed_wars_cursor = self.db.war_history.find({}, {"_id": 1})
            self.processed_war_ids = {doc["_id"] async for doc in processed_wars_cursor}
            logger.info(f"Carregados {len(self.processed_war_ids)} IDs de guerras processadas.")
        except Exception as e:
            logger.error(f"Erro durante load_initial_state_from_db: {e}", exc_info=True)


    async def coc_login_task(self):
        logger.info("Iniciando tarefa de login coc_login_task...") # Log Adicional
        try:
            self.api_client = coc.Client()
            logger.info("Tentando login no coc.py API Client...") # Log Adicional
            await self.api_client.login(self.coc_email, self.coc_password)
            logger.info(">>> Login no coc.Client (api_client) BEM-SUCEDIDO. <<<") # Log Adicional
            self.coc_client_ready.set()
            logger.info("Evento coc_client_ready definido.") # Log Adicional
        except Exception as e:
            logger.critical(f"### FALHA CRÍTICA no login do coc.Client ###: {e}", exc_info=True)
            # Considerar parar o bot aqui se o login falhar?
            # await self.close()

    async def on_ready(self):
        logger.info("="*30) # Separador
        logger.info(f'>>> BOT {self.user.name} (ID: {self.user.id}) ESTÁ ONLINE E PRONTO! <<<') # Log mais destacado
        logger.info(f"Versão: {self.bot_version}")
        logger.info(f"Conectado a {len(self.guilds)} servidor(es).")
        logger.info("="*30) # Separador
        # Sincronização de comandos
        try:
            # Sincroniza globalmente. Para sincronizar apenas em um servidor, use:
            # synced = await self.tree.sync(guild=discord.Object(id=SEU_GUILD_ID))
            synced = await self.tree.sync()
            logger.info(f"Sincronizados {len(synced)} comandos de barra globalmente no on_ready.")
        except Exception as e:
            logger.error(f"Falha ao sincronizar comandos no on_ready: {e}", exc_info=True)


    async def close(self):
        logger.info("Iniciando processo de desligamento do bot...")
        if self.api_client:
             logger.info("Fechando cliente coc.py...")
             await self.api_client.close()
             logger.info("Cliente coc.py fechado.")
        if self.mongo_client:
             logger.info("Fechando cliente MongoDB...")
             self.mongo_client.close()
             logger.info("Cliente MongoDB fechado.")
        logger.info("Chamando super().close()...")
        await super().close()
        logger.info("Bot desligado.")

    async def get_clan_data_with_cache(self, tag: str) -> Optional[coc.Clan]:
        # Espera o cliente CoC estar pronto
        try:
             await asyncio.wait_for(self.coc_client_ready.wait(), timeout=10.0) # Timeout de 10s
        except asyncio.TimeoutError:
             logger.error("Timeout esperando coc_client_ready em get_clan_data_with_cache.")
             return None

        normalized_tag = coc.utils.correct_tag(tag)
        now = datetime.datetime.now()
        # Verifica cache
        cache_entry = self.clan_cache.get(normalized_tag)
        if cache_entry and (now - cache_entry["timestamp"]).total_seconds() < self.CACHE_DURATION_SECONDS:
            logger.debug(f"Retornando dados do clã {tag} do cache.")
            return cache_entry["data"]
        # Busca na API
        try:
            logger.debug(f"Buscando dados do clã {tag} na API...")
            if not self.api_client: # Verificação extra
                 logger.error("api_client não inicializado em get_clan_data_with_cache.")
                 return None
            clan_data = await self.api_client.get_clan(normalized_tag)
            self.clan_cache[normalized_tag] = {"data": clan_data, "timestamp": now}
            logger.debug(f"Dados do clã {tag} obtidos da API e cacheados.")
            return clan_data
        except coc.errors.NotFound:
             logger.warning(f"Clã {tag} não encontrado na API.")
             return None
        except Exception as e:
            logger.error(f"Erro ao obter dados do clã {tag} da API: {e}", exc_info=True)
            return None

# --- Servidor Web ---
async def setup_web_server(bot_instance: ClashGeniusBot):
    logger.info("Iniciando configuração do servidor web (setup_web_server)...") # Log Adicional
    app = web.Application()

    logger.info("Aguardando bot estar pronto para obter referências das Cogs...") # Log Adicional
    await bot_instance.wait_until_ready()
    logger.info("Bot está pronto. Obtendo referências das Cogs para o servidor web...") # Log Adicional
    web_api_cog = bot_instance.get_cog("Web API")
    db_cog = bot_instance.get_cog("Banco de Dados")
    profile_cog = bot_instance.get_cog("Perfis de Membros")
    cwl_cog = bot_instance.get_cog("Planeador de CWL")
    maintenance_cog = bot_instance.get_cog("Manutenção do Sistema")
    war_advisor_cog = bot_instance.get_cog("Conselheiro de Guerra IA")
    admin_cog = bot_instance.get_cog("Painel de Administração Avançado")
    watchlist_cog = bot_instance.get_cog("Lista de Observação")

    required_cogs = [
        web_api_cog, db_cog, profile_cog, cwl_cog, maintenance_cog,
        war_advisor_cog, admin_cog, watchlist_cog
    ]
    # Verifica se todas as Cogs necessárias foram carregadas
    if not all(required_cogs):
        missing = [cog_name for cog_name, cog_instance in zip([
            "Web API", "Banco de Dados", "Perfis de Membros", "Planeador de CWL",
            "Manutenção do Sistema", "Conselheiro de Guerra IA", "Painel de Administração Avançado",
            "Lista de Observação"
        ], required_cogs) if cog_instance is None]
        logger.critical(f"### ERRO FATAL: Cogs essenciais para o servidor web não carregados: {', '.join(missing)}. O servidor web NÃO PODE iniciar. ###")
        return # Impede o início do servidor web

    logger.info("Todas as Cogs necessárias para o servidor web foram encontradas.") # Log Adicional

    # --- Definição dos Handlers da API --- (código omitido por brevidade, mantido igual)
    async def handle_web_response(request, key, func, *args, **kwargs):
        now = datetime.datetime.now()
        # Verifica cache
        cache_entry = bot_instance.web_api_cache.get(key)
        if not kwargs.get('force_api_call', False) and cache_entry and \
           (now - cache_entry["timestamp"]).total_seconds() < bot_instance.WEB_API_CACHE_DURATION_SECONDS:
            logger.debug(f"Retornando resposta web para '{key}' do cache.")
            return web.json_response(cache_entry["data"])

        # Verifica se o cliente CoC está pronto
        if not bot_instance.coc_client_ready.is_set():
            logger.warning(f"Requisição para '{key}' recebida, mas coc_client não está pronto.")
            return web.json_response({"error": "O bot ainda está a iniciar (API CoC indisponível)... Por favor, aguarde."}, status=503)

        # Chama a função da Cog
        logger.debug(f"Buscando dados para resposta web '{key}' (sem cache ou forçado)...")
        data = await func(*args, **kwargs)

        # Atualiza cache se não for erro
        if 'error' not in data and not kwargs.get('force_api_call', False):
             bot_instance.web_api_cache[key] = {"data": data, "timestamp": now}
             logger.debug(f"Dados para '{key}' cacheados.")

        # Retorna resposta JSON, usando default=str para BSON/datetime
        return web.json_response(data, dumps=lambda v: json.dumps(v, default=str))


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
        bot_instance.web_api_cache.pop('members', None) # Invalida cache
        return web.Response(status=204)
    async def api_historic_war_handler(request):
        war_id = request.match_info['war_id']
        war_doc = await bot_instance.db.war_history.find_one({"_id": war_id})
        # Usa default=str para converter ObjectId e datetime
        return web.json_response(war_doc, dumps=lambda v: json.dumps(v, default=str)) if war_doc else web.json_response({"error": "Guerra não encontrada."}, status=404)
    async def api_member_profile_handler(request):
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        profile_data = await profile_cog.fetch_player_profile_data(player_tag)
        return web.json_response(profile_data, status=404 if "error" in profile_data else 200)
    async def api_cwl_generate_plan_handler(request):
        bot_instance.web_api_cache.pop('cwl_plan', None) # Invalida cache
        plan = await cwl_cog.generate_rotation_plan()
        return web.json_response(plan)
    async def api_war_advisor_plan_handler(request):
        try:
            # Força a busca da guerra atual para ter dados frescos
            war = await bot_instance.api_client.get_current_war(bot_instance.clan_tag, ignore_cache=True)
            prediction_data = await bot_instance.war_prediction_system.predict_war_outcome(war, bot_instance.clan_tag)
            plan = war_advisor_cog.war_advisor.create_war_plan(war, bot_instance.clan_tag, prediction_data)
            return web.json_response(plan)
        except (coc.NotFound, coc.PrivateWarLog):
            return web.json_response({"success": False, "error": "Nenhuma guerra ativa."}, status=404)
        except Exception as e:
            logger.error(f"Erro no endpoint /api/war_advisor_plan: {e}", exc_info=True)
            return web.json_response({"success": False, "error": "Erro interno ao gerar plano."}, status=500)

    async def api_coc_status_handler(r):
        if not admin_cog: return web.json_response({"status": "error", "message": "Admin cog not loaded."}, status=500)
        if not bot_instance.coc_client_ready.is_set(): return web.json_response({"status": "maintenance", "message": "O bot ainda está a iniciar..."}, status=200)
        status_data = await admin_cog.get_api_status()
        return web.json_response(status_data)
    # --- Fim Handlers API ---

    # --- Registro de Rotas API ---
    logger.info("Registrando rotas da API principal...") # Log Adicional
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
    app.router.add_get("/api/coc_status", api_coc_status_handler)
    app.router.add_get("/api/status", admin_get_status_handler) # Status geral do bot
    app.router.add_get("/api/maintenance_message", api_maintenance_message)
    logger.info("Rotas da API principal registradas.") # Log Adicional
    # --- Fim Registro API ---

    # --- Middleware de Autenticação Admin ---
    @web.middleware
    async def admin_auth_middleware(request, handler):
        session = await get_session(request)
        # Permite acesso não autenticado para GET /api/admin/settings para carregar no form
        # Ajuste: A leitura de settings agora é protegida, a escrita também. Watchlist também.
        # if request.method == 'GET' and request.path == '/api/admin/settings':
        #    pass # Permitir leitura
        if not session.get('admin'):
            logger.warning(f"Acesso não autorizado negado para: {request.path}")
            return web.json_response({"status": "unauthorized"}, status=403)
        response = await handler(request)
        return response
    # --- Fim Middleware ---

    # --- Handlers API Admin --- (código omitido, mantido igual)
    async def api_admin_diagnostics(r): return web.json_response(await admin_cog.get_diagnostics())
    async def api_admin_get_settings(r): return web.json_response(await admin_cog.get_settings())
    async def api_admin_update_settings(r): return web.json_response(await admin_cog.update_settings(await r.json()))
    async def api_admin_db_viewer(r): return web.json_response(await admin_cog.get_db_viewer_data(), dumps=lambda v: json.dumps(v, default=str))
    async def api_admin_get_watchlist(r):
        data = await admin_cog.get_watchlist_admin()
        return web.json_response(data) # WatchlistCog já formata a data
    async def api_admin_add_watchlist(r):
        data = await r.json()
        tag=data.get('player_tag'); name=data.get('player_name'); reason=data.get('reason'); details=data.get('details')
        if not tag or not reason: return web.json_response({"status":"error","message":"Tag e motivo obrigatórios."}, status=400)
        if not name:
             try: player=await bot_instance.api_client.get_player(tag); name=player.name
             except: name=tag
        success = await admin_cog.add_to_watchlist_admin(tag, name, reason, details)
        if success: bot_instance.web_api_cache.pop('members',None); return web.json_response({"status":"success","message":"Jogador adicionado."})
        else: return web.json_response({"status":"error","message":"Erro ao adicionar."},status=500)
    async def api_admin_remove_watchlist(r):
        data=await r.json(); tag=data.get('player_tag')
        if not tag: return web.json_response({"status":"error","message":"Tag obrigatória."}, status=400)
        success = await admin_cog.remove_from_watchlist_admin(tag)
        if success: bot_instance.web_api_cache.pop('members',None); return web.json_response({"status":"success","message":"Jogador removido."})
        else: return web.json_response({"status":"not_found","message":"Jogador não encontrado."}, status=404) # 404 se não encontrado
    async def api_admin_actions(r):
        data=await r.json(); session=await get_session(r); action=data.get("action"); payload=data.get("payload",{})
        if action=="send_announcement": return web.json_response(await admin_cog.send_announcement(payload.get("channel_id"),payload.get("message")))
        elif action=="clear_cache": return web.json_response(await admin_cog.clear_web_cache(payload.get("cache_key")))
        elif action=="force_sync_war":
            tasks_cog=bot_instance.get_cog("Tarefas em Segundo Plano"); asyncio.create_task(tasks_cog.check_war_end_task.coro(tasks_cog))
            return web.json_response({"status":"success","message":"Sincronização forçada."})
        elif action=="sync_commands":
            guild_id=session.get('guild_id')
            if not guild_id and payload.get("scope")=="guild": return web.json_response({"status":"error","message":"ID do servidor não encontrado."})
            guild=bot_instance.get_guild(int(guild_id)) if guild_id else None
            return web.json_response(await admin_cog.sync_commands(payload.get("scope","guild"),guild))
        return web.json_response({"status":"error","message":"Ação desconhecida."},status=400)
    # --- Fim Handlers API Admin ---

    # --- Registro Rotas Admin ---
    logger.info("Registrando rotas da API Admin...") # Log Adicional
    admin_api_app = web.Application(middlewares=[admin_auth_middleware])
    admin_api_app.router.add_get("/diagnostics", api_admin_diagnostics)
    admin_api_app.router.add_get("/settings", api_admin_get_settings)
    admin_api_app.router.add_post("/settings", api_admin_update_settings)
    admin_api_app.router.add_get("/db_viewer", api_admin_db_viewer)
    admin_api_app.router.add_post("/actions", api_admin_actions)
    admin_api_app.router.add_get("/watchlist", api_admin_get_watchlist)
    admin_api_app.router.add_post("/watchlist/add", api_admin_add_watchlist)
    admin_api_app.router.add_post("/watchlist/remove", api_admin_remove_watchlist)
    app.add_subapp("/api/admin/", admin_api_app)
    logger.info("Rotas da API Admin registradas.") # Log Adicional
    # --- Fim Registro Admin ---

    # --- Handlers de Páginas e Auth --- (código omitido, mantido igual)
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    async def admin_login_page(r): return web.FileResponse(os.path.join(static_dir, "admin_login.html"))
    async def admin_panel_page(r):
        session=await get_session(r);
        if not session.get('admin'): return web.HTTPFound('/admin')
        return web.FileResponse(os.path.join(static_dir,"admin_panel.html"))
    async def admin_login_handler(r):
        data=await r.post()
        if data.get('password')==ADMIN_PASSWORD:
            session=await get_session(r); session['admin']=True; guild_id=data.get('guild_id'); session['guild_id']=guild_id if guild_id else None
            return web.HTTPFound('/admin/panel')
        return web.HTTPFound(f"/admin?error=1&guild_id={data.get('guild_id','')}")
    async def admin_logout_handler(r):
        session=await get_session(r); session.pop('admin',None); session.pop('guild_id',None)
        return web.HTTPFound('/admin')
    async def admin_toggle_maintenance_handler(r):
        session=await get_session(r);
        if not session.get('admin'): return web.json_response({"status":"unauthorized"}, status=403)
        return await maintenance_cog.toggle_maintenance_mode_web()
    async def admin_send_test_embed_handler(r):
        session=await get_session(r);
        if not session.get('admin'): return web.json_response({"status":"unauthorized"}, status=403)
        return await maintenance_cog.send_test_embed_web()
    async def admin_get_status_handler(r): # Renomeado para evitar conflito com /api/status
        session=await get_session(r); is_admin=session.get('admin',False)
        return web.json_response({"status":"ok","maintenance_mode":bot_instance.maintenance_mode,"version":BOT_VERSION,"is_admin":is_admin})
    async def painel_handler(r):
        session=await get_session(r); is_admin=session.get('admin',False)
        # Verifica manutenção do bot OU status da API CoC
        api_status_data = await admin_cog.get_api_status() if admin_cog else {"status": "error"}
        if (bot_instance.maintenance_mode or api_status_data.get("status") in ["maintenance", "error"]) and not is_admin:
            logger.info(f"Acesso ao painel bloqueado (Manutenção Bot: {bot_instance.maintenance_mode}, Status API: {api_status_data.get('status')}). Redirecionando para maintenance.html")
            return web.FileResponse(os.path.join(static_dir,"maintenance.html"))
        return web.FileResponse(os.path.join(static_dir,"painel.html"))
    # --- Fim Handlers Páginas ---

    # --- Registro Rotas Páginas e Statics ---
    logger.info("Registrando rotas de páginas e arquivos estáticos...") # Log Adicional
    app.router.add_static('/static/', path=static_dir, name='static')
    app.router.add_get("/admin", admin_login_page)
    app.router.add_post("/admin/login", admin_login_handler)
    app.router.add_get("/admin/logout", admin_logout_handler)
    app.router.add_get("/admin/panel", admin_panel_page)
    app.router.add_post("/admin/toggle_maintenance", admin_toggle_maintenance_handler)
    app.router.add_post("/admin/send_test_embed", admin_send_test_embed_handler)
    # app.router.add_get("/api/status", admin_get_status_handler) # Removido para usar o geral
    app.router.add_get("/painel", painel_handler)
    app.router.add_get("/", lambda r: web.HTTPFound('/painel')) # Redireciona raiz para o painel
    logger.info("Rotas de páginas registradas.") # Log Adicional
    # --- Fim Registro Páginas ---

    # --- Configuração de Sessão e Inicialização do Servidor ---
    logger.info("Configurando sessão web...") # Log Adicional
    try:
        secret_key_bytes = Fernet.generate_key() if not FERNET_KEY else FERNET_KEY.encode()
        secret_key = base64.urlsafe_b64decode(secret_key_bytes)
        setup_session(app, EncryptedCookieStorage(secret_key))
        logger.info("Sessão web configurada.") # Log Adicional
    except Exception as e:
         logger.critical(f"### ERRO FATAL ao configurar sessão web (verifique FERNET_KEY) ###: {e}", exc_info=True)
         return # Não inicia o servidor se a sessão falhar

    logger.info("Configurando AppRunner e TCPSite...") # Log Adicional
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    try:
        await site.start()
        logger.info(f">>> SERVIDOR WEB INICIADO com sucesso em http://0.0.0.0:{port} <<<") # Log de Sucesso
    except OSError as e:
         logger.critical(f"### ERRO FATAL ao iniciar servidor web na porta {port} ###: {e}", exc_info=True)
         logger.critical("Verifique se a porta já está em uso ou se há problemas de permissão.")
    except Exception as e:
         logger.critical(f"### ERRO FATAL inesperado ao iniciar servidor web ###: {e}", exc_info=True)
    # --- Fim Servidor ---

async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    bot = ClashGeniusBot(command_prefix="!", intents=intents)
    try:
        logger.info("Iniciando o bot (bot.start)...") # Log Adicional
        await bot.start(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        logger.critical("### FALHA NO LOGIN DO DISCORD: Token inválido. Verifique DISCORD_TOKEN. ###")
    except KeyboardInterrupt:
        logger.info("Bot desligado manualmente (KeyboardInterrupt).")
    except Exception as e:
         logger.critical(f"### ERRO FATAL NÃO TRATADO NO LOOP PRINCIPAL DO BOT ###: {e}", exc_info=True)
    finally:
        if not bot.is_closed():
            logger.info("Garantindo que o bot seja fechado...")
            await bot.close()
        logger.info("Processo principal finalizado.")

if __name__ == "__main__":
    # Garante que o diretório 'logs' exista (se for usar FileHandler)
    # log_dir = "logs"
    # if not os.path.exists(log_dir):
    #     os.makedirs(log_dir)
    # file_handler = logging.FileHandler(filename=os.path.join(log_dir, 'bot.log'), encoding='utf-8', mode='a')
    # file_handler.setFormatter(formatter)
    # logging.getLogger().addHandler(file_handler)

    logger.info("="*10 + f" INICIANDO ClashGeniusBot v{BOT_VERSION} " + "="*10)
    asyncio.run(main())

