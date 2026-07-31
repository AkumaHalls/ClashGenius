# -*- coding: utf-8 -*-
"""
Configurações centralizadas do ClashGenius.
Todas as constantes compartilhadas entre módulos ficam aqui.
"""

import os
import logging

import pytz
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("config")

# ================== AMBIENTE ==================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COC_EMAIL = os.getenv("COC_EMAIL")
COC_PASSWORD = os.getenv("COC_PASSWORD")
CLAN_TAG = os.getenv("CLAN_TAG")
MONGO_DB_URL = os.getenv("MONGO_DB_URL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
FERNET_KEY = os.getenv("FERNET_KEY")
BASE_URL = os.getenv("BASE_URL")

if not ADMIN_PASSWORD:
    logger.critical("ADMIN_PASSWORD não definido nas variáveis de ambiente! O bot não poderá funcionar.")
    raise RuntimeError("Variável de ambiente ADMIN_PASSWORD é obrigatória.")

# ================== CANAIS DISCORD ==================
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
AI_LOG_CHANNEL_ID = int(os.getenv("AI_LOG_CHANNEL_ID", 0))
POST_WAR_ANALYSIS_CHANNEL_ID = int(os.getenv("POST_WAR_ANALYSIS_CHANNEL_ID", 0))
POST_WAR_VERDICT_CHANNEL_ID = int(os.getenv("POST_WAR_VERDICT_CHANNEL_ID", 0))
CLAN_GAMES_CHANNEL_ID = int(os.getenv("CLAN_GAMES_CHANNEL_ID", 0))
CWL_PLANNER_CHANNEL_ID = int(os.getenv("CWL_PLANNER_CHANNEL_ID", 0))
DONATIONS_CHANNEL_ID = int(os.getenv("DONATIONS_CHANNEL_ID", 0))
SMURF_LOG_CHANNEL_ID = int(os.getenv("SMURF_LOG_CHANNEL_ID", 0))
WATCHLIST_ALERT_CHANNEL_ID = int(os.getenv("WATCHLIST_ALERT_CHANNEL_ID", 0))
LOW_PERFORMANCE_CHANNEL_ID = int(os.getenv("LOW_PERFORMANCE_CHANNEL_ID", 0))
CAPITAL_REPORT_CHANNEL_ID = int(os.getenv("CAPITAL_REPORT_CHANNEL_ID", 0))
MAINTENANCE_ALERT_CHANNEL_ID = int(os.getenv("MAINTENANCE_ALERT_CHANNEL_ID", 0))
WAR_PREFERENCE_CHANNEL_ID = int(os.getenv("WAR_PREFERENCE_CHANNEL_ID", 0))
CHANGELOG_CHANNEL_ID = int(os.getenv("CHANGELOG_CHANNEL_ID", "0"))
ACTIVITY_REPORT_CHANNEL_ID = int(os.getenv("ACTIVITY_REPORT_CHANNEL_ID", 0))
TOURNAMENT_SUMMARY_CHANNEL_ID = int(os.getenv("TOURNAMENT_SUMMARY_CHANNEL_ID", 0))

# ================== ROLES ==================
ROLE_ID_1STAR_ALERT = int(os.getenv("ROLE_ID_1STAR_ALERT", 0))
ROLE_ID_MISSED_ATTACK = int(os.getenv("ROLE_ID_MISSED_ATTACK", 0))
LEADER_ROLE_ID = int(os.getenv("LEADER_ROLE_ID", 0))
COLEADER_ROLE_ID = int(os.getenv("COLEADER_ROLE_ID", 0))
MAINTENANCE_ROLE_ID = int(os.getenv("MAINTENANCE_ROLE_ID", 0))

# ================== CONFIGURAÇÕES DO BOT ==================
AUTO_ADD_WATCHLIST_ENABLED = os.getenv("AUTO_ADD_WATCHLIST_ENABLED", "True").lower() == "true"
BOT_VERSION = "34.2.1-GeniusLib-v5.3.0"
TIMEZONE = pytz.timezone('America/Sao_Paulo')

# ================== CACHE ==================
CACHE_DURATION_SECONDS = 300
WEB_API_CACHE_DURATION_SECONDS = 45

# ================== RATE LIMIT (futuro) ==================
# WEB_API_RATE_LIMIT = 30  # requests per minute per IP
