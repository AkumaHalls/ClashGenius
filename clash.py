# -*- coding: utf-8 -*-
# Versão 19.8.15 - Integração com MongoDB Atlas e refatoração dos handlers de notas.

import os
import logging
import asyncio
import datetime
import json
from aiohttp import web
from typing import Dict, List, Optional, Union, Set, Any
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
import pytz
from dotenv import load_dotenv
import motor.motor_asyncio  # +++ Importação do Motor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("coc_discord_bot")

from coc import (
    ClanWar,
    Player,
    Clan,
    WarAttack,
    Timestamp,
    ClanMember
)

# ... (O resto das suas importações e definições iniciais permanecem as mesmas) ...
WarLogEntry = None
LeagueGroup = None
CapitalDistrict = None

try:
    try:
        from coc import ClanWarLogEntry as WarLogEntry_coc
        WarLogEntry = WarLogEntry_coc
        logger.info("ClanWarLogEntry importado com sucesso de 'coc'.")
    except ImportError:
        logger.warning("Falha ao importar 'ClanWarLogEntry' de 'coc'. Tentando 'coc.wars'.")
        try:
            from coc.wars import ClanWarLogEntry as WarLogEntry_coc_wars
            WarLogEntry = WarLogEntry_coc_wars
            logger.info("ClanWarLogEntry importado com sucesso de 'coc.wars'.")
        except ImportError:
            logger.error("Não foi possível importar 'ClanWarLogEntry'. Funcionalidade de Histórico de Guerras afetada.")
            WarLogEntry = None

    try:
        from coc import ClanWarLeagueGroup as LeagueGroup_coc
        LeagueGroup = LeagueGroup_coc
        logger.info("ClanWarLeagueGroup importado com sucesso de 'coc'.")
    except ImportError:
        logger.warning("Falha ao importar 'ClanWarLeagueGroup' de 'coc'. Tentando 'coc.cwl' ou 'coc.wars'.")
        try:
            from coc.cwl import ClanWarLeagueGroup as LeagueGroup_coc_cwl
            LeagueGroup = LeagueGroup_coc_cwl
            logger.info("ClanWarLeagueGroup importado com sucesso de 'coc.cwl'.")
        except ImportError:
            try:
                from coc.wars import ClanWarLeagueGroup as LeagueGroup_coc_wars
                LeagueGroup = LeagueGroup_coc_wars
                logger.info("ClanWarLeagueGroup importado com sucesso de 'coc.wars'.")
            except ImportError:
                logger.error("Não foi possível importar 'ClanWarLeagueGroup'. Funcionalidade de CWL afetada.")
                LeagueGroup = None
    try:
        from coc import CapitalDistrict as CapitalDistrict_coc
        CapitalDistrict = CapitalDistrict_coc
        logger.info("CapitalDistrict importado com sucesso de 'coc'.")
    except ImportError:
        logger.warning("Falha ao importar 'CapitalDistrict' de 'coc'. Tentando 'coc.clans'.")
        try:
            from coc.clans import CapitalDistrict as CapitalDistrict_coc_clans
            CapitalDistrict = CapitalDistrict_coc_clans
            logger.info("CapitalDistrict importado com sucesso de 'coc.clans'.")
        except ImportError:
            logger.error("Não foi possível importar 'CapitalDistrict'. Funcionalidade da Capital afetada.")
            CapitalDistrict = None
except Exception as e_import_general:
    logger.error(f"Erro geral durante importações específicas do CoC: {e_import_general}")
    WarLogEntry = WarLogEntry or None
    LeagueGroup = LeagueGroup or None
    CapitalDistrict = CapitalDistrict or None

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COC_EMAIL = os.getenv("COC_EMAIL")
COC_PASSWORD = os.getenv("COC_PASSWORD")
CLAN_TAG = os.getenv("CLAN_TAG")

try:
    channel_id_str = os.environ.get("CHANNEL_ID")
    if channel_id_str: CHANNEL_ID = int(channel_id_str)
    else: CHANNEL_ID = 0; logger.error("CHANNEL_ID não definido no .env. Usando 0 como padrão.")
except (TypeError, ValueError) as e_channel_id:
    logger.error(f"CHANNEL_ID ('{channel_id_str if 'channel_id_str' in locals() else 'N/A'}') inválido no .env: {e_channel_id}. Usando 0 como padrão.")
    CHANNEL_ID = 0

ROLE_ID_1STAR_ALERT = os.getenv("ROLE_ID_1STAR_ALERT")
ROLE_ID_MISSED_ATTACK = os.getenv("ROLE_ID_MISSED_ATTACK")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

try:
    TIMEZONE = pytz.timezone('America/Sao_Paulo')
except pytz.UnknownTimeZoneError:
    logger.error("Timezone 'America/Sao_Paulo' desconhecida. Usando UTC como padrão.")
    TIMEZONE = pytz.utc

BOT_VERSION = "19.8.15-DB" # Versão atualizada
# --- O arquivo de notas JSON não é mais necessário ---
# PLAYER_NOTES_FILE = "player_notes.json" 
reported_war_ends: Set[str] = set()
intents = discord.Intents.default()
intents.message_content = True; intents.members = True; intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)
player_short_term_cache: Dict[str, Player] = {}
clan_cache: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION_SECONDS = 300

# --- As funções load_player_notes e save_player_notes foram removidas ---
# --- Elas serão substituídas pela lógica direta do DB nos handlers da API ---

# ... (O resto das suas funções helper como get_clan_data_base, get_player_data, etc., permanecem as mesmas ATÉ fetch_clan_members_for_web_api) ...
async def get_clan_data_base(tag: str) -> Clan:
    if not bot.coc_client or not bot.coc_client.http: raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        if not tag.startswith("#"): tag = f"#{tag}"
        return await bot.coc_client.get_clan(tag)
    except coc.NotFound: raise ValueError(f"Clã com tag {tag} não encontrado.")
    except coc.Maintenance: raise ValueError("API CoC em manutenção.")
    except asyncio.TimeoutError: raise ValueError("Timeout buscando dados do clã.")
    except coc.InvalidCredentials: raise ValueError("Credenciais API CoC inválidas.")
    except coc.Forbidden: raise ValueError("Acesso proibido à API CoC.")
    except Exception as e: logger.error(f"Erro ao buscar clã {tag}: {e}", exc_info=True); raise ValueError(f"Erro ao buscar clã: {e}")

async def get_player_data(tag: str) -> Player:
    normalized_tag = tag if tag.startswith("#") else f"#{tag}"
    if normalized_tag in player_short_term_cache: return player_short_term_cache[normalized_tag]
    if not bot.coc_client or not bot.coc_client.http: raise ValueError("Cliente CoC não inicializado.")
    try:
        player = await bot.coc_client.get_player(normalized_tag)
        player_short_term_cache[normalized_tag] = player
        return player
    except coc.NotFound: raise ValueError(f"Jogador {normalized_tag} não encontrado.")
    except coc.Maintenance: raise ValueError("API CoC em manutenção.")
    except asyncio.TimeoutError: raise ValueError("Timeout buscando jogador.")
    except coc.InvalidCredentials: raise ValueError("Credenciais API CoC inválidas.")
    except coc.Forbidden: raise ValueError("Acesso proibido à API CoC.")
    except Exception as e: logger.error(f"Erro ao buscar jogador {normalized_tag}: {e}", exc_info=True); raise ValueError(f"Erro ao buscar jogador: {e}")

async def get_clan_data_with_cache(tag: str) -> Clan:
    normalized_tag = tag if tag.startswith("#") else f"#{tag}"
    now = datetime.datetime.now()
    if normalized_tag in clan_cache:
        cache_entry = clan_cache[normalized_tag]
        if "timestamp" in cache_entry and isinstance(cache_entry["timestamp"], datetime.datetime):
            if (now - cache_entry["timestamp"]).total_seconds() < CACHE_DURATION_SECONDS:
                return cache_entry["data"]
    clan_data_val = await get_clan_data_base(normalized_tag)
    clan_cache[normalized_tag] = {"data": clan_data_val, "timestamp": now}
    return clan_data_val

async def fetch_clan_members_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        members_data = []

        # +++ Lógica de Notas Modificada para usar o DB +++
        player_notes = {}
        if bot.db:
            notes_cursor = bot.db.players.find({"_id": {"$in": [m.tag for m in clan.members]}}, {"_id": 1, "notes": 1})
            async for doc in notes_cursor:
                player_notes[doc["_id"]] = doc.get("notes", {"text": "", "priority": "none"})
        # +++ Fim da modificação +++

        if hasattr(clan, 'members') and clan.members:
            for m in clan.members:
                note_info = player_notes.get(m.tag, {"text": "", "priority": "none"}) # Pega do DB
                members_data.append({
                    "name": m.name, "tag": m.tag, "town_hall": m.town_hall, "exp_level": m.exp_level,
                    "league": m.league.name if hasattr(m, 'league') and m.league else "N/A",
                    "trophies": m.trophies, "role": m.role.name.capitalize() if hasattr(m, 'role') and m.role else "Membro",
                    "donations": m.donations, "received": m.received,
                    "note": note_info.get("text", ""),
                    "note_priority": note_info.get("priority", "none")
                })
        members_data.sort(key=lambda x: x.get("trophies", 0), reverse=True)
        return {"members": members_data, "clan_name": clan.name, "clan_tag": clan.tag}
    except Exception as e:
        logger.error(f"Erro ao buscar membros do clã para API web: {e}", exc_info=True)
        return {"error": str(e)}

# ... (Suas outras funções de fetch permanecem iguais: fetch_current_war_details_for_web_api, fetch_war_attacks_remaining_for_web_api, etc.) ...
async def fetch_current_war_details_for_web_api():
    # ... (esta função não precisa de mudanças por enquanto) ...
    pass
# ... (etc) ...

# --- HANDLERS DA API ---
async def api_clan_info_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_clan_info_{CLAN_TAG}", fetch_clan_info_for_web_api))
async def api_members_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_clan_members_{CLAN_TAG}", fetch_clan_members_for_web_api))
async def api_current_war_details_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_current_war_details_{CLAN_TAG}", fetch_current_war_details_for_web_api))
async def api_war_attacks_remaining_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_war_attacks_remaining_{CLAN_TAG}", fetch_war_attacks_remaining_for_web_api))
async def api_war_log_handler(request: web.Request) -> web.Response: limit = int(request.query.get("limit","10")); limit=max(1,min(limit,50)); return web.json_response(await get_cached_web_data(f"web_war_log_{CLAN_TAG}_limit{limit}",fetch_war_log_for_web_api,limit))
async def api_cwl_info_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_cwl_info_{CLAN_TAG}", fetch_cwl_info_for_web_api))

# +++ HANDLERS DE NOTAS MODIFICADOS +++
async def api_get_player_note_handler(request: web.Request) -> web.Response:
    if not bot.db:
        return web.json_response({"error": "Database not connected"}, status=503)
        
    player_tag = request.match_info.get('player_tag', None)
    if not player_tag: return web.json_response({"error": "Player tag não fornecida"}, status=400)
    
    player_tag_fmt = f"#{player_tag}" if not player_tag.startswith("#") else player_tag
    
    note_doc = await bot.db.players.find_one({"_id": player_tag_fmt})
    if note_doc and "notes" in note_doc:
        note_info = note_doc["notes"]
    else:
        note_info = {"text": "", "priority": "none"}
        
    return web.json_response(note_info)

async def api_save_player_note_handler(request: web.Request) -> web.Response:
    if not bot.db:
        return web.json_response({"error": "Database not connected"}, status=503)

    player_tag = request.match_info.get('player_tag', None)
    if not player_tag: return web.json_response({"error": "Player tag não fornecida"}, status=400)
    
    player_tag_fmt = f"#{player_tag}" if not player_tag.startswith("#") else player_tag
    
    try:
        data = await request.json()
        note_text = data.get("text", "")
        note_priority = data.get("priority", "none")
        if note_priority not in ["none", "green", "yellow", "red"]: 
            return web.json_response({"error": "Prioridade inválida"}, status=400)

        # Busca o nome atual do jogador para manter o DB atualizado
        try:
            player = await get_player_data(player_tag_fmt)
            player_name = player.name
        except Exception:
            # Se não encontrar o jogador, busca no próprio DB para não perder o nome
            existing_doc = await bot.db.players.find_one({"_id": player_tag_fmt})
            player_name = existing_doc.get("name") if existing_doc else "Desconhecido"

        # Usa update_one com upsert=True para criar ou atualizar o documento
        await bot.db.players.update_one(
            {'_id': player_tag_fmt},
            {
                '$set': {
                    'name': player_name,
                    'notes.text': note_text,
                    'notes.priority': note_priority,
                    'last_updated': datetime.datetime.now(pytz.utc)
                }
            },
            upsert=True
        )
        
        logger.info(f"Nota salva no DB para {player_tag_fmt}: Prio: {note_priority}, Texto: '{note_text[:30]}...'")
        
        # Invalida o cache para que a próxima requisição puxe os dados atualizados do DB
        if f"web_clan_members_{CLAN_TAG}" in web_api_cache: 
            del web_api_cache[f"web_clan_members_{CLAN_TAG}"]
            logger.info(f"Cache de membros invalidado para {CLAN_TAG} após salvar nota.")
            
        return web.json_response({"success": True, "message": "Nota salva com sucesso."})
    except json.JSONDecodeError: 
        return web.json_response({"error": "Payload JSON inválido"}, status=400)
    except Exception as e: 
        logger.error(f"Erro ao salvar nota para {player_tag_fmt} no DB: {e}", exc_info=True)
        return web.json_response({"error": "Erro interno ao salvar nota"}, status=500)

# ... (setup_web_server e outras funções permanecem iguais) ...
async def setup_web_server() -> Optional[web.AppRunner]:
    # ...
    pass
# ...

async def setup_hook():
    logger.info("Executando setup_hook...")
    
    # +++ CONEXÃO COM O BANCO DE DADOS +++
    logger.info("Tentando conectar ao MongoDB Atlas...")
    mongo_url = os.getenv("MONGO_DB_URL")
    if not mongo_url:
        logger.error("MONGO_DB_URL não encontrada no .env. Funcionalidades de banco de dados desabilitadas.")
        bot.db_client = None
        bot.db = None
    else:
        try:
            bot.db_client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
            bot.db = bot.db_client.get_default_database() # Pega o DB da URL
            await bot.db.command('ping') # Testa a conexão
            logger.info(f"Conexão com MongoDB estabelecida com sucesso! Database: {bot.db.name}")
        except Exception as e:
            logger.error(f"Falha ao conectar/pingar MongoDB: {e}", exc_info=True)
            bot.db_client = None
            bot.db = None
    # +++ FIM DA SEÇÃO DO DB +++
    
    logger.info("Inicializando cliente CoC...")
    bot.coc_client = coc.EventsClient()
    # ... (O resto do seu setup_hook permanece igual) ...

# ... (main e o resto do arquivo permanecem iguais) ...
async def main():
    # ...
    pass

if __name__ == "__main__":
    # ...
    pass
