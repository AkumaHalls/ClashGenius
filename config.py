# -*- coding: utf-8 -*-
"""
Configurações centralizadas do ClashGenius.
Todas as constantes compartilhadas entre módulos ficam aqui.
"""

import logging
import os
import re

import pytz
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("config")


def _str_env(nome, default=None):
    """Lê uma variável de ambiente string; valor vazio conta como ausente."""
    valor = os.getenv(nome)
    return default if not valor else valor


def _int_env(nome, default=0):
    """Lê uma variável de ambiente inteira; valor vazio cai no default."""
    valor = os.getenv(nome)
    if not valor:
        return default
    return int(valor)


def redact_mongo_uri(texto):
    """Mascara credenciais de URIs Mongo antes de ir para log ou API.

    Redige toda a authority ``://<credenciais>@`` até o ÚLTIMO ``@`` antes do
    host. Funciona com senhas contendo ``@``/``/`` e com ``mongodb+srv``.
    """
    return re.sub(
        r"(mongodb(?:\+srv)?://)[^@\s]*(?:@[^@\s]*)*@",
        r"\1***:***@",
        str(texto),
    )


# ================== AMBIENTE ==================
DISCORD_TOKEN = _str_env("DISCORD_TOKEN")
COC_EMAIL = _str_env("COC_EMAIL")
COC_PASSWORD = _str_env("COC_PASSWORD")
CLAN_TAG = _str_env("CLAN_TAG")
MONGO_DB_URL = _str_env("MONGO_DB_URL")
ADMIN_PASSWORD = _str_env("ADMIN_PASSWORD")
FERNET_KEY = _str_env("FERNET_KEY")
BASE_URL = _str_env("BASE_URL")

_AMBIENTE_OBRIGATORIO = {
    "DISCORD_TOKEN": DISCORD_TOKEN,
    "COC_EMAIL": COC_EMAIL,
    "COC_PASSWORD": COC_PASSWORD,
    "CLAN_TAG": CLAN_TAG,
    "MONGO_DB_URL": MONGO_DB_URL,
    "ADMIN_PASSWORD": ADMIN_PASSWORD,
    "FERNET_KEY": FERNET_KEY,
}
_ausentes = [nome for nome, valor in _AMBIENTE_OBRIGATORIO.items() if not valor]
if _ausentes:
    raise RuntimeError(
        "Variáveis de ambiente obrigatórias ausentes ou vazias: " + ", ".join(_ausentes)
    )

try:
    Fernet(FERNET_KEY.encode())
except Exception as exc:
    raise RuntimeError(
        "FERNET_KEY inválida: use uma chave Fernet válida (Fernet.generate_key())."
    ) from exc

# ================== CANAIS DISCORD ==================
CHANNEL_ID = _int_env("CHANNEL_ID")
AI_LOG_CHANNEL_ID = _int_env("AI_LOG_CHANNEL_ID")
POST_WAR_ANALYSIS_CHANNEL_ID = _int_env("POST_WAR_ANALYSIS_CHANNEL_ID")
POST_WAR_VERDICT_CHANNEL_ID = _int_env("POST_WAR_VERDICT_CHANNEL_ID")
CLAN_GAMES_CHANNEL_ID = _int_env("CLAN_GAMES_CHANNEL_ID")
CWL_PLANNER_CHANNEL_ID = _int_env("CWL_PLANNER_CHANNEL_ID")
DONATIONS_CHANNEL_ID = _int_env("DONATIONS_CHANNEL_ID")
SMURF_LOG_CHANNEL_ID = _int_env("SMURF_LOG_CHANNEL_ID")
WATCHLIST_ALERT_CHANNEL_ID = _int_env("WATCHLIST_ALERT_CHANNEL_ID")
LOW_PERFORMANCE_CHANNEL_ID = _int_env("LOW_PERFORMANCE_CHANNEL_ID")
CAPITAL_REPORT_CHANNEL_ID = _int_env("CAPITAL_REPORT_CHANNEL_ID")
MAINTENANCE_ALERT_CHANNEL_ID = _int_env("MAINTENANCE_ALERT_CHANNEL_ID")
WAR_PREFERENCE_CHANNEL_ID = _int_env("WAR_PREFERENCE_CHANNEL_ID")
CHANGELOG_CHANNEL_ID = _int_env("CHANGELOG_CHANNEL_ID")
ACTIVITY_REPORT_CHANNEL_ID = _int_env("ACTIVITY_REPORT_CHANNEL_ID")
TOURNAMENT_SUMMARY_CHANNEL_ID = _int_env("TOURNAMENT_SUMMARY_CHANNEL_ID")

# ================== ROLES ==================
ROLE_ID_1STAR_ALERT = _int_env("ROLE_ID_1STAR_ALERT")
ROLE_ID_MISSED_ATTACK = _int_env("ROLE_ID_MISSED_ATTACK")
LEADER_ROLE_ID = _int_env("LEADER_ROLE_ID")
COLEADER_ROLE_ID = _int_env("COLEADER_ROLE_ID")
MAINTENANCE_ROLE_ID = _int_env("MAINTENANCE_ROLE_ID")

# ================== CONFIGURAÇÕES DO BOT ==================
AUTO_ADD_WATCHLIST_ENABLED = os.getenv("AUTO_ADD_WATCHLIST_ENABLED", "True").lower() == "true"
BOT_VERSION = "34.8.0-GeniusLib-v5.6.0"
TIMEZONE = pytz.timezone('America/Sao_Paulo')

# ================== CACHE ==================
CACHE_DURATION_SECONDS = 300
WEB_API_CACHE_DURATION_SECONDS = 45

# ================== RATE LIMIT (futuro) ==================
# WEB_API_RATE_LIMIT = 30  # requests per minute per IP
