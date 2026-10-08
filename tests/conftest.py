"""Fixtures globais dos testes.

Este conftest define um ambiente FALSO ANTES de qualquer import de `config`,
para que `import config` nunca dependa de secrets reais do host.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest

# --- Ambiente fake hermético (sobrescreve qualquer valor real do host) ---
os.environ["DISCORD_TOKEN"] = "test-discord-token"
os.environ["COC_EMAIL"] = "test@example.com"
os.environ["COC_PASSWORD"] = "test-password"
os.environ["CLAN_TAG"] = "#TESTCLAN"
os.environ["MONGO_DB_URL"] = "mongodb://localhost:27017/clashgenius_test"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["BASE_URL"] = "http://localhost:10000"

if "FERNET_KEY" not in os.environ or not os.environ["FERNET_KEY"]:
    from cryptography.fernet import Fernet

    os.environ["FERNET_KEY"] = Fernet.generate_key().decode()

_CHANNEL_VARS = (
    "CHANNEL_ID",
    "AI_LOG_CHANNEL_ID",
    "POST_WAR_ANALYSIS_CHANNEL_ID",
    "POST_WAR_VERDICT_CHANNEL_ID",
    "CLAN_GAMES_CHANNEL_ID",
    "CWL_PLANNER_CHANNEL_ID",
    "DONATIONS_CHANNEL_ID",
    "SMURF_LOG_CHANNEL_ID",
    "WATCHLIST_ALERT_CHANNEL_ID",
    "LOW_PERFORMANCE_CHANNEL_ID",
    "CAPITAL_REPORT_CHANNEL_ID",
    "MAINTENANCE_ALERT_CHANNEL_ID",
    "WAR_PREFERENCE_CHANNEL_ID",
    "CHANGELOG_CHANNEL_ID",
    "ACTIVITY_REPORT_CHANNEL_ID",
    "TOURNAMENT_SUMMARY_CHANNEL_ID",
    "ROLE_ID_1STAR_ALERT",
    "ROLE_ID_MISSED_ATTACK",
    "LEADER_ROLE_ID",
    "COLEADER_ROLE_ID",
    "MAINTENANCE_ROLE_ID",
)
for _name in _CHANNEL_VARS:
    os.environ[_name] = "0"

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture()
def reload_config():
    """Recarrega o módulo `config` após o teste (para env alterada via monkeypatch)."""
    import config

    importlib.reload(config)
    yield config
    importlib.reload(config)
