# -*- coding: utf-8 -*-
# Versão 33.0.0 - Decomposição do Web Server

import os
import logging
import asyncio
import datetime
from typing import Dict, Any, Optional, List

import discord
from discord.ext import commands
import geniuslib as coc
from geniuslib.middleware import middleware, request_logger as mw_request_logger, response_logger as mw_response_logger
import pytz
import motor.motor_asyncio
from pymongo.uri_parser import parse_uri

from config import (
    DISCORD_TOKEN, COC_EMAIL, COC_PASSWORD, CLAN_TAG, MONGO_DB_URL, BASE_URL,
    CHANNEL_ID, AI_LOG_CHANNEL_ID, POST_WAR_ANALYSIS_CHANNEL_ID, POST_WAR_VERDICT_CHANNEL_ID,
    CLAN_GAMES_CHANNEL_ID, CWL_PLANNER_CHANNEL_ID, DONATIONS_CHANNEL_ID, SMURF_LOG_CHANNEL_ID,
    WATCHLIST_ALERT_CHANNEL_ID, LOW_PERFORMANCE_CHANNEL_ID, CAPITAL_REPORT_CHANNEL_ID,
    MAINTENANCE_ALERT_CHANNEL_ID, WAR_PREFERENCE_CHANNEL_ID, CHANGELOG_CHANNEL_ID,
    ROLE_ID_1STAR_ALERT, ROLE_ID_MISSED_ATTACK, LEADER_ROLE_ID, COLEADER_ROLE_ID,
    AUTO_ADD_WATCHLIST_ENABLED, BOT_VERSION, TIMEZONE,
)

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


class ClashGeniusBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coc_email = COC_EMAIL
        self.coc_password = COC_PASSWORD
        self.clan_tag = CLAN_TAG
        self.channel_id = CHANNEL_ID
        self.ai_log_channel_id = AI_LOG_CHANNEL_ID
        self.post_war_analysis_channel_id = POST_WAR_ANALYSIS_CHANNEL_ID
        self.post_war_verdict_channel_id = POST_WAR_VERDICT_CHANNEL_ID
        self.clan_games_channel_id = CLAN_GAMES_CHANNEL_ID
        self.cwl_planner_channel_id = CWL_PLANNER_CHANNEL_ID
        self.donations_channel_id = DONATIONS_CHANNEL_ID
        self.smurf_log_channel_id = SMURF_LOG_CHANNEL_ID # INJEÇÃO
        self.role_id_1star_alert = ROLE_ID_1STAR_ALERT
        self.role_id_missed_attack = ROLE_ID_MISSED_ATTACK
        self.watchlist_alert_channel_id = WATCHLIST_ALERT_CHANNEL_ID if WATCHLIST_ALERT_CHANNEL_ID else CHANNEL_ID
        self.leader_role_id = LEADER_ROLE_ID
        self.coleader_role_id = COLEADER_ROLE_ID
        self.auto_add_watchlist_enabled = AUTO_ADD_WATCHLIST_ENABLED
        self.low_performance_channel_id = LOW_PERFORMANCE_CHANNEL_ID
        self.capital_report_channel_id = CAPITAL_REPORT_CHANNEL_ID
        self.maintenance_alert_channel_id = MAINTENANCE_ALERT_CHANNEL_ID
        self.war_preference_channel_id = WAR_PREFERENCE_CHANNEL_ID
        self.changelog_channel_id = CHANGELOG_CHANNEL_ID
        self.bot_version = BOT_VERSION
        self.timezone = TIMEZONE
        self.base_url = BASE_URL
        self.maintenance_mode = False
        self.maintenance_message = "O painel está em manutenção. Voltaremos em breve!"
        self.api_client: Optional[coc.Client] = None
        self.war_prediction_system = None
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

            logger.info("--- Iniciando carregamento de Cogs ---")
            cog_files = [ 'events_cog', 'tasks_cog', 'database_cog', 'general_cog', 'cwl_planner_cog', 'clan_games_cog', 'war_advisor_cog', 'profile_cog', 'maintenance_cog', 'web_api_cog', 'admin_cog', 'donation_cog', 'slash_cog', 'watchlist_cog', 'smurf_detection_cog', 'capital_cog', 'performance_cog', 'war_predictor_cog', 'battlelog_cog' ]
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
                self.post_war_verdict_channel_id = bot_settings.get("post_war_verdict_channel_id", self.post_war_verdict_channel_id)
                self.clan_games_channel_id = bot_settings.get("clan_games_channel_id", self.clan_games_channel_id)
                self.cwl_planner_channel_id = bot_settings.get("cwl_planner_channel_id", self.cwl_planner_channel_id)
                self.donations_channel_id = bot_settings.get("donations_channel_id", self.donations_channel_id)
                self.smurf_log_channel_id = bot_settings.get("smurf_log_channel_id", self.smurf_log_channel_id) # INJEÇÃO
                self.watchlist_alert_channel_id = bot_settings.get("watchlist_alert_channel_id", self.watchlist_alert_channel_id)
                self.low_performance_channel_id = bot_settings.get("low_performance_channel_id", self.low_performance_channel_id)
                self.capital_report_channel_id = bot_settings.get("capital_report_channel_id", self.capital_report_channel_id)
                self.maintenance_alert_channel_id = bot_settings.get("maintenance_alert_channel_id", self.maintenance_alert_channel_id)
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
                self.api_client = coc.Client(raw_attribute=True)
                await asyncio.wait_for(self.api_client.login(self.coc_email, self.coc_password), timeout=45.0)
                await self._setup_middleware()
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

    async def _setup_middleware(self):
        """Registra middlewares GeniusLib v4.2.0 no HTTP client."""
        try:
            if hasattr(self.api_client, 'http') and hasattr(self.api_client.http, 'add_middleware'):
                self.api_client.http.add_middleware(mw_request_logger, mw_response_logger)

                @middleware("response")
                async def health_middleware(resp):
                    if resp.status >= 400:
                        logger.warning("Middleware: CoC API retornou status %d em %.1fms", resp.status, resp.elapsed_ms)
                    return resp

                self.api_client.http.add_middleware(health_middleware)
                logger.info(">>> Middleware GeniusLib v4.2.0 registrado no HTTP client. <<<")
        except Exception as e:
            logger.warning("Não foi possível registrar middleware: %s", e)

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

# --- Utilitários de Autenticação ---
# Movidos para web/auth.py — mantidos aqui para compatibilidade com imports existentes
from web.auth import hash_password, check_password

# --- Servidor Web ---
# Decomposto para web/server.py
from web.server import setup_web_server


async def main():
    intents = discord.Intents.default(); intents.message_content = True; intents.members = True; intents.guilds = True
    bot = ClashGeniusBot(command_prefix="!", intents=intents, allowed_mentions=discord.AllowedMentions(roles=True))
    try:
        logger.info("Iniciando bot (bot.start)...")
        await bot.start(DISCORD_TOKEN)
    except discord.errors.LoginFailure: logger.critical("### FALHA LOGIN DISCORD: Token inválido. ###")
    except discord.errors.HTTPException as e:
        if e.status == 429:
            logger.critical("### ERRO 429 (RATE LIMIT) DETECTADO ###")
            logger.critical("O Discord bloqueou temporariamente este IP/Token devido a muitas tentativas.")
            logger.critical("Entrando em modo de espera (SLEEP) por 1 HORA para evitar reinício automático do Render.")
            logger.critical("NÃO REINICIE MANUALMENTE AGORA. ESPERE.")
            await asyncio.sleep(3600) 
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
