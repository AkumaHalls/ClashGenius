# -*- coding: utf-8 -*-
# Versão 19.8.9 - Correções NameError, AttributeError get_league_war, strftime, capitalize

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

BOT_VERSION = "19.8.9"
PLAYER_NOTES_FILE = "player_notes.json"
reported_war_ends: Set[str] = set()
intents = discord.Intents.default()
intents.message_content = True; intents.members = True; intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)
player_short_term_cache: Dict[str, Player] = {}
clan_cache: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION_SECONDS = 300

def load_player_notes() -> Dict[str, Dict[str, str]]:
    if not os.path.exists(PLAYER_NOTES_FILE):
        logger.info(f"Arquivo de notas '{PLAYER_NOTES_FILE}' não encontrado. Criando um novo com {{}}.")
        save_player_notes({})
        return {}
    try:
        if os.path.getsize(PLAYER_NOTES_FILE) == 0:
            logger.warning(f"Arquivo de notas '{PLAYER_NOTES_FILE}' encontrado, mas está vazio. Inicializando com {{}}.")
            save_player_notes({})
            return {}
    except OSError as e:
        logger.error(f"Erro ao verificar o tamanho do arquivo '{PLAYER_NOTES_FILE}': {e}. Tentando carregar mesmo assim.")
    try:
        with open(PLAYER_NOTES_FILE, 'r', encoding='utf-8') as f:
            notes = json.load(f)
            if not isinstance(notes, dict):
                logger.warning(f"Formato inesperado no arquivo de notas '{PLAYER_NOTES_FILE}'. Resetando para {{}}.")
                save_player_notes({})
                return {}
            return notes
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Erro ao carregar notas dos jogadores de {PLAYER_NOTES_FILE}: {e}. Resetando para {{}}.")
        try:
            backup_file = f"{PLAYER_NOTES_FILE}.bak_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            if os.path.exists(PLAYER_NOTES_FILE):
                os.rename(PLAYER_NOTES_FILE, backup_file)
                logger.info(f"Arquivo de notas corrompido movido para {backup_file}")
        except Exception as backup_e:
            logger.error(f"Erro ao tentar fazer backup do arquivo de notas corrompido: {backup_e}")
        save_player_notes({})
        return {}

def save_player_notes(notes_data: Dict[str, Dict[str, str]]) -> None:
    try:
        with open(PLAYER_NOTES_FILE, 'w', encoding='utf-8') as f:
            json.dump(notes_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Erro ao salvar notas dos jogadores em {PLAYER_NOTES_FILE}: {e}")
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar notas dos jogadores: {e}", exc_info=True)

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

async def fetch_location_id(location_name: str) -> int:
    if not bot.coc_client or not bot.coc_client.http: raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        locations = await bot.coc_client.search_locations(name=location_name, limit=1)
        if not locations: raise ValueError(f"Localização '{location_name}' não encontrada.")
        loc_obj = locations[0]
        if hasattr(loc_obj, 'id'): return loc_obj.id
        else: raise ValueError(f"Objeto de localização para '{location_name}' não possui ID.")
    except Exception as e: logger.error(f"Erro ao buscar ID da localização '{location_name}': {e}", exc_info=True); raise ValueError(f"Erro ao buscar ID da localização: {str(e)}")

async def send_log_embed(embed_to_log: discord.Embed, content: str = None) -> None:
    if not CHANNEL_ID or CHANNEL_ID == 0: logger.warning("CHANNEL_ID não configurado para send_log_embed."); return
    if not hasattr(embed_to_log, 'footer') or not embed_to_log.footer or not getattr(embed_to_log.footer, 'text', None):
         embed_to_log.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
    if not embed_to_log.timestamp: embed_to_log.timestamp = datetime.datetime.now(TIMEZONE)
    try:
        channel_log_obj = await bot.fetch_channel(CHANNEL_ID)
        if isinstance(channel_log_obj, discord.TextChannel): await channel_log_obj.send(content=content, embed=embed_to_log)
        else: logger.error(f"Canal de log ID {CHANNEL_ID} não é um canal de texto.")
    except discord.NotFound: logger.error(f"Canal de log ID {CHANNEL_ID} não encontrado.")
    except discord.Forbidden: logger.error(f"Sem permissão no canal de log ID {CHANNEL_ID}.")
    except Exception as e: logger.error(f"Erro ao enviar embed para log ID {CHANNEL_ID}: {e}", exc_info=True)

async def send_embeds_splitted(channel: discord.TextChannel, base_embed: discord.Embed, field_name: str, items: List[str]) -> None:
    if not isinstance(channel, discord.TextChannel): logger.error("Canal inválido para send_embeds_splitted."); return
    if not items:
         embed_empty_split = discord.Embed.from_dict(base_embed.to_dict())
         embed_empty_split.add_field(name=field_name, value="Nenhum item encontrado.", inline=False)
         if not hasattr(embed_empty_split, 'footer') or not embed_empty_split.footer or not getattr(embed_empty_split.footer, 'text', None):
             embed_empty_split.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
         if not embed_empty_split.timestamp: embed_empty_split.timestamp = datetime.datetime.now(TIMEZONE)
         try: await channel.send(embed=embed_empty_split)
         except Exception as e: logger.error(f"Erro ao enviar embed dividido (vazio) para {channel.id}: {e}", exc_info=True)
         return
    embeds_to_send = []; current_embed_split = discord.Embed.from_dict(base_embed.to_dict()); current_field_value_split = ""
    for item in items:
        item_line = item + "\n"
        if (len(current_field_value_split) + len(item_line) > 1024 or len(current_embed_split) + len(current_field_value_split) + len(item_line) > 5900):
            if current_field_value_split: current_embed_split.add_field(name=(field_name or "Dados"), value=current_field_value_split, inline=False)
            if current_embed_split.fields: embeds_to_send.append(current_embed_split)
            current_embed_split = discord.Embed.from_dict(base_embed.to_dict()); current_field_value_split = item_line
            if len(current_field_value_split) > 1024: current_field_value_split = current_field_value_split[:1021] + "...\n"
        else: current_field_value_split += item_line
    if current_field_value_split: current_embed_split.add_field(name=(field_name or "Dados"), value=current_field_value_split, inline=False)
    if current_embed_split.fields: embeds_to_send.append(current_embed_split)
    for embed_item_to_send in embeds_to_send:
        if not hasattr(embed_item_to_send, 'footer') or not embed_item_to_send.footer or not getattr(embed_item_to_send.footer, 'text', None):
             embed_item_to_send.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
        if not embed_item_to_send.timestamp: embed_item_to_send.timestamp = datetime.datetime.now(TIMEZONE)
        try: await channel.send(embed=embed_item_to_send)
        except Exception as e: logger.error(f"Erro ao enviar embed dividido para {channel.id}: {e}", exc_info=True); break

def format_war_time_details(war_obj: ClanWar, time_now_tz: datetime.datetime) -> Dict[str, Any]:
    details: Dict[str, Any] = { "time_key": "N/A", "time_value": "N/A", "time_remaining": "N/A", "start_time_iso": None, "end_time_iso": None }
    if hasattr(war_obj, 'state') and war_obj.state == "preparation":
        if hasattr(war_obj, 'start_time') and war_obj.start_time and hasattr(war_obj.start_time, 'time'):
            start_aware = pytz.utc.localize(war_obj.start_time.time).astimezone(TIMEZONE)
            details["start_time_iso"] = start_aware.isoformat(); details["time_key"] = "Início"; details["time_value"] = start_aware.strftime('%d/%m/%y %H:%M')
            delta = start_aware - time_now_tz
            if delta.total_seconds() > 0: d, r = divmod(delta.total_seconds(), 86400); h, r_h = divmod(r, 3600); m, _ = divmod(r_h, 60); details["time_remaining"] = f"{int(d)}d {int(h)}h {int(m)}m" if d > 0 else f"{int(h)}h {int(m)}m"
            else: details["time_remaining"] = "Iniciando..."
    elif hasattr(war_obj, 'state') and (war_obj.state == "inWar" or war_obj.state == "warEnded"):
        if hasattr(war_obj, 'end_time') and war_obj.end_time and hasattr(war_obj.end_time, 'time'):
            end_aware = pytz.utc.localize(war_obj.end_time.time).astimezone(TIMEZONE)
            details["end_time_iso"] = end_aware.isoformat(); details["time_key"] = "Fim" if war_obj.state == "inWar" else "Finalizada em"; details["time_value"] = end_aware.strftime('%d/%m/%y %H:%M')
            if war_obj.state == "inWar":
                delta = end_aware - time_now_tz
                if delta.total_seconds() > 0: d, r = divmod(delta.total_seconds(), 86400); h, r_h = divmod(r, 3600); m, _ = divmod(r_h, 60); details["time_remaining"] = f"{int(d)}d {int(h)}h {int(m)}m" if d > 0 else f"{int(h)}h {int(m)}m"
                else: details["time_remaining"] = "Finalizando..."
            else: details["time_remaining"] = "-"
    return details

async def get_current_or_last_war(clan_tag_param: str) -> Optional[ClanWar]:
    current_war: Optional[ClanWar] = None
    try:
        if LeagueGroup:
            league_group = await bot.coc_client.get_league_group(clan_tag_param)
            if league_group and getattr(league_group,'state',None) != "notInWar" and hasattr(league_group, 'rounds'):
                if hasattr(league_group, 'current_wars') and league_group.current_wars:
                    for war_tag_obj in reversed(league_group.current_wars):
                        try:
                            lg_war = await bot.coc_client.get_league_war(war_tag_obj.tag) # CORRIGIDO
                            if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param) and lg_war.state in ["inWar", "preparation"]:
                                current_war = lg_war;
                                if lg_war.opponent.tag == clan_tag_param: current_war.clan, current_war.opponent = current_war.opponent, current_war.clan
                                return current_war
                        except (coc.NotFound, AttributeError) as e:
                            logger.debug(f"Erro ao buscar guerra CWL específica {war_tag_obj.tag} em current_wars: {e}")
                            continue
                        except Exception as e:
                            logger.error(f"Erro inesperado ao buscar guerra CWL {war_tag_obj.tag} em current_wars: {e}", exc_info=True)
                            continue
                for war_tags_in_round in reversed(league_group.rounds):
                    for war_tag_str in war_tags_in_round:
                        if war_tag_str == "#0": continue
                        try:
                            lg_war = await bot.coc_client.get_league_war(war_tag_str) # CORRIGIDO
                            if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param) and lg_war.state in ["inWar", "preparation"]:
                                current_war = lg_war
                                if lg_war.opponent.tag == clan_tag_param: current_war.clan, current_war.opponent = current_war.opponent, current_war.clan
                                return current_war
                        except (coc.NotFound, AttributeError) as e:
                            logger.debug(f"Erro ao buscar guerra CWL específica {war_tag_str} em rounds: {e}")
                            continue
                        except Exception as e:
                            logger.error(f"Erro inesperado ao buscar guerra CWL {war_tag_str} em rounds: {e}", exc_info=True)
                            continue
                if not current_war and league_group.rounds:
                    best_ended_cwl_war = None
                    for war_tags_in_round in reversed(league_group.rounds):
                        for war_tag_str in war_tags_in_round:
                            if war_tag_str == "#0": continue
                            try:
                                lg_war = await bot.coc_client.get_league_war(war_tag_str) # CORRIGIDO
                                if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param) and lg_war.state == "warEnded":
                                    if not best_ended_cwl_war or \
                                       (hasattr(lg_war, 'end_time') and hasattr(best_ended_cwl_war, 'end_time') and \
                                        lg_war.end_time and best_ended_cwl_war.end_time and \
                                        lg_war.end_time.time > best_ended_cwl_war.end_time.time):
                                        best_ended_cwl_war = lg_war
                            except (coc.NotFound, AttributeError) as e:
                                logger.debug(f"Erro ao buscar guerra CWL finalizada {war_tag_str}: {e}")
                                continue
                            except Exception as e:
                                logger.error(f"Erro inesperado ao buscar guerra CWL finalizada {war_tag_str}: {e}", exc_info=True)
                                continue
                    if best_ended_cwl_war:
                        if best_ended_cwl_war.opponent.tag == clan_tag_param: best_ended_cwl_war.clan, best_ended_cwl_war.opponent = best_ended_cwl_war.opponent, best_ended_cwl_war.clan
                        return best_ended_cwl_war
    except coc.NotFound:
        logger.debug(f"Nenhum grupo CWL encontrado para o clã {clan_tag_param}.")
    except AttributeError as e_attr_lg:
        logger.error(f"AttributeError em get_current_or_last_war ao acessar ClanWarLeagueGroup para {clan_tag_param}: {e_attr_lg}. Verifique a importação/versão da coc.py.")
    except Exception as e_cwl:
        logger.error(f"Erro ao buscar dados da guerra CWL para {clan_tag_param}: {e_cwl}", exc_info=True)

    try:
        regular_war = await bot.coc_client.get_current_war(clan_tag_param)
        if regular_war and regular_war.state != "notInWar":
            return regular_war
    except coc.PrivateWarLog:
        logger.warning(f"Log de guerra regular do clã {clan_tag_param} é privado.")
    except coc.NotFound:
        logger.debug(f"Nenhuma guerra regular ativa ou em preparação encontrada para {clan_tag_param}.")
    except Exception as e_reg:
        logger.error(f"Erro ao buscar dados da guerra regular para {clan_tag_param}: {e_reg}", exc_info=True)
    
    return None

web_api_cache: Dict[str, Dict[str, Any]] = {}
WEB_API_CACHE_DURATION_SECONDS = 45

async def get_cached_web_data(key: str, func_to_fetch_data: callable, *args: Any) -> Any:
    now = datetime.datetime.now()
    if key in web_api_cache:
        cache_entry = web_api_cache[key]
        if "timestamp" in cache_entry and isinstance(cache_entry["timestamp"], datetime.datetime):
            if (now - cache_entry["timestamp"]).total_seconds() < WEB_API_CACHE_DURATION_SECONDS:
                return cache_entry["data"]
    data = await func_to_fetch_data(*args)
    web_api_cache[key] = {"data": data, "timestamp": now}
    return data

async def fetch_clan_info_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        districts = []
        if CapitalDistrict and hasattr(clan, 'capital_districts') and clan.capital_districts:
            for d in clan.capital_districts: districts.append({"name": d.name, "level": d.hall_level})
        elif not CapitalDistrict: districts = [{"name": "Distritos Indisponíveis (erro import)", "level": ""}]
        else: districts = [{"name": "Nenhum distrito.", "level": ""}]
        
        return {
            "name": clan.name, "tag": clan.tag, "level": clan.level, "points": clan.points,
            "capital_points": getattr(clan, 'capital_points', 0), "member_count": clan.member_count,
            "description": clan.description, "war_wins": getattr(clan, 'war_wins', 'N/A'),
            "location": clan.location.name if hasattr(clan, 'location') and clan.location else "N/A",
            "type": clan.type.capitalize() if hasattr(clan, 'type') else "N/A",
            "badge_url": clan.badge.url if hasattr(clan, 'badge') and clan.badge else None,
            "version": BOT_VERSION, "capital_districts": districts,
            "capital_league": clan.capital_league.name if hasattr(clan, 'capital_league') and clan.capital_league else "N/A"
        }
    except Exception as e:
        logger.error(f"Erro ao buscar informações do clã para API web: {e}", exc_info=True)
        return {"error": str(e), "name": "Erro ao carregar dados do clã"}

async def fetch_clan_members_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        members_data = []
        player_notes = load_player_notes() 

        if hasattr(clan, 'members') and clan.members:
            for m in clan.members:
                note_info = player_notes.get(m.tag, {"text": "", "priority": "none"})
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

async def get_member_war_details_async(member: ClanMember, war_obj_ref: ClanWar) -> Dict[str, Any]:
    member_attacks_data = []
    if member.attacks:
        for atk in member.attacks:
            try: p_def = player_short_term_cache.get(atk.defender_tag) or await get_player_data(atk.defender_tag)
            except ValueError: p_def = None
            member_attacks_data.append({"defender_tag": atk.defender_tag, "defender_name": p_def.name if p_def else atk.defender_tag,
                                        "defender_townhall": p_def.town_hall if p_def else '?', "stars": atk.stars, "destruction": atk.destruction, "order": atk.order})
    member_defenses_data = []
    if hasattr(member, 'defenses') and member.defenses:
            for defense in member.defenses:
                try: p_att = player_short_term_cache.get(defense.attacker_tag) or await get_player_data(defense.attacker_tag)
                except ValueError: p_att = None
                member_defenses_data.append({"attacker_tag": defense.attacker_tag, "attacker_name": p_att.name if p_att else defense.attacker_tag,
                                            "attacker_townhall": p_att.town_hall if p_att else '?', "stars": defense.stars, "destruction": defense.destruction, "order": defense.order})
    return {"tag": member.tag, "name": member.name, "townhall": member.town_hall, "map_position": member.map_position,
            "attacks_used": len(member.attacks) if member.attacks else 0,
            "attacks_remaining": war_obj_ref.attacks_per_member - (len(member.attacks) if member.attacks else 0),
            "attacks_made": member_attacks_data, "defenses_received": member_defenses_data,
            "best_opponent_attack": {"stars": member.best_opponent_attack.stars, "attacker_tag": member.best_opponent_attack.attacker_tag} if member.best_opponent_attack else None}

async def fetch_current_war_details_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG:
        return {"error": "CLAN_TAG não configurado.", "war_data": None, "attacks": [], "our_clan_members_in_war": [], "opponent_clan_members_in_war": []}

    player_short_term_cache.clear()
    final_response: Dict[str, Any] = {
        "war_data": None, "all_attacks": [],
        "our_clan_members_in_war": [], "opponent_clan_members_in_war": []
    }

    try:
        war = await get_current_or_last_war(CLAN_TAG)
        
        if not war or getattr(war, 'state', "notInWar") == "notInWar":
            logger.info("Nenhuma guerra ativa ou recente encontrada na API CoC Oficial para o painel.")
            return {"error": "Nenhuma guerra para detalhar.", "war_data": None, "attacks": [], "our_clan_members_in_war": [], "opponent_clan_members_in_war": []}

        logger.info(f"Guerra encontrada via API CoC Oficial: Estado {war.state}")
        
        our_clan_obj, opp_clan_obj = (war.clan, war.opponent)
        if war.clan.tag != CLAN_TAG and war.opponent.tag == CLAN_TAG:
            our_clan_obj, opp_clan_obj = opp_clan_obj, our_clan_obj
        
        time_details_coc = format_war_time_details(war, datetime.datetime.now(TIMEZONE))
        war_type_coc = "Guerra"
        if hasattr(war, 'is_cwl') and war.is_cwl: war_type_coc = "CWL"
        elif hasattr(war, 'type') and war.type == "friendly": war_type_coc = "Amistosa"

        if our_clan_obj and hasattr(our_clan_obj, 'members') and our_clan_obj.members:
            final_response["our_clan_members_in_war"] = [await get_member_war_details_async(m, war) for m in our_clan_obj.members]
            final_response["our_clan_members_in_war"].sort(key=lambda m: m["map_position"])
        if opp_clan_obj and hasattr(opp_clan_obj, 'members') and opp_clan_obj.members:
            final_response["opponent_clan_members_in_war"] = [await get_member_war_details_async(m, war) for m in opp_clan_obj.members]
            final_response["opponent_clan_members_in_war"].sort(key=lambda m: m["map_position"])
        
        if war.attacks:
            for attack in sorted(war.attacks, key=lambda a: a.order):
                try: p_att = await get_player_data(attack.attacker_tag); att_name, att_th = p_att.name, p_att.town_hall
                except ValueError: att_name, att_th = attack.attacker_tag, '?'
                try: p_def = await get_player_data(attack.defender_tag); def_name, def_th = p_def.name, p_def.town_hall
                except ValueError: def_name, def_th = attack.defender_tag, '?'
                final_response["all_attacks"].append({
                    "order": attack.order, "attacker_tag": attack.attacker_tag, "attacker_name": att_name, "attacker_townhall": att_th,
                    "defender_tag": attack.defender_tag, "defender_name": def_name, "defender_townhall": def_th,
                    "stars": attack.stars, "destruction": attack.destruction, "duration": getattr(attack, 'duration', 'N/A')})
        
        clan_star_dist = {0:0,1:0,2:0,3:0}; opp_star_dist = {0:0,1:0,2:0,3:0}
        c_total_dur, c_atk_count, o_total_dur, o_atk_count = 0.0,0,0.0,0
        for att_det in final_response["all_attacks"]:
            is_our_att = any(m_w["tag"] == att_det["attacker_tag"] for m_w in final_response["our_clan_members_in_war"])
            current_star_dist = clan_star_dist if is_our_att else opp_star_dist
            current_star_dist[att_det["stars"]] = current_star_dist.get(att_det["stars"], 0) + 1
            duration_val = att_det["duration"]
            if isinstance(duration_val, (int, float)):
                if is_our_att: c_total_dur += duration_val; c_atk_count +=1
                else: o_total_dur += duration_val; o_atk_count +=1
        
        state_description = str(war.state).capitalize() if war.state else "N/A" # CORRIGIDO

        final_response["war_data"] = {
            "status": str(war.state),  # Garantir que seja string
            "type": war_type_coc,
            "state_description": state_description,
            "clan_name": our_clan_obj.name if our_clan_obj else "N/A", 
            "clan_tag": our_clan_obj.tag if our_clan_obj else "N/A", 
            "clan_stars": our_clan_obj.stars if our_clan_obj else 0,
            "clan_destruction": f"{our_clan_obj.destruction:.2f}%" if our_clan_obj else "0.00%",
            "clan_badge_url": our_clan_obj.badge.url if our_clan_obj and hasattr(our_clan_obj.badge, 'url') else None,
            "clan_attacks_used": our_clan_obj.attacks_used if our_clan_obj and hasattr(our_clan_obj, 'attacks_used') else len([a for m_w in final_response.get("our_clan_members_in_war", []) for a in m_w['attacks_made']]),
            "opponent_name": opp_clan_obj.name if opp_clan_obj else "N/A", 
            "opponent_tag": opp_clan_obj.tag if opp_clan_obj else "N/A", 
            "opponent_stars": opp_clan_obj.stars if opp_clan_obj else 0,
            "opponent_destruction": f"{opp_clan_obj.destruction:.2f}%" if opp_clan_obj else "0.00%",
            "opponent_badge_url": opp_clan_obj.badge.url if opp_clan_obj and hasattr(opp_clan_obj.badge, 'url') else None,
            "opponent_attacks_used": opp_clan_obj.attacks_used if opp_clan_obj and hasattr(opp_clan_obj, 'attacks_used') else len([a for m_w in final_response.get("opponent_clan_members_in_war", []) for a in m_w['attacks_made']]),
            **time_details_coc,
            "attacks_per_member": war.attacks_per_member, 
            "team_size": war.team_size,
            "clan_star_distribution": clan_star_dist, "opponent_star_distribution": opp_star_dist,
            "clan_avg_stars": f"{our_clan_obj.stars/c_atk_count:.2f}" if our_clan_obj and c_atk_count > 0 else "0.00",
            "opponent_avg_stars": f"{opp_clan_obj.stars/o_atk_count:.2f}" if opp_clan_obj and o_atk_count > 0 else "0.00",
            "clan_avg_destruction_percent": f"{our_clan_obj.destruction:.2f}" if our_clan_obj else "0.00",
            "opponent_avg_destruction_percent": f"{opp_clan_obj.destruction:.2f}" if opp_clan_obj else "0.00",
            "clan_avg_duration": f"{c_total_dur/c_atk_count:.1f}s" if c_atk_count > 0 else "0s",
            "opponent_avg_duration": f"{o_total_dur/o_atk_count:.1f}s" if o_atk_count > 0 else "0s",
            "source": "API CoC Oficial"
        }
    except Exception as e:
        logger.error(f"Erro geral ao processar detalhes da guerra: {e}", exc_info=True)
        return {"error": f"Erro ao buscar detalhes da guerra: {e}", "war_data": None, "attacks": [], "our_clan_members_in_war": [], "opponent_clan_members_in_war": []}

    return final_response

async def fetch_war_attacks_remaining_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    war = await get_current_or_last_war(CLAN_TAG); clan_name_rem = "N/A"
    our_clan_obj_rem = None
    if war:
        if war.clan.tag == CLAN_TAG: our_clan_obj_rem = war.clan; clan_name_rem = our_clan_obj_rem.name
        elif war.opponent.tag == CLAN_TAG: our_clan_obj_rem = war.opponent; clan_name_rem = our_clan_obj_rem.name
    if not war or war.state != "inWar": return {"message": "Não há guerra em andamento.", "members_pending": [], "clan_name": clan_name_rem}
    if not our_clan_obj_rem: return {"message": "Erro ao identificar o clã na guerra.", "members_pending": [], "clan_name": "Erro"}
    pending = []
    if hasattr(our_clan_obj_rem, 'members') and our_clan_obj_rem.members:
        for m in our_clan_obj_rem.members:
            attacks_left = war.attacks_per_member - (len(m.attacks) if m.attacks else 0)
            if attacks_left > 0: pending.append({"name": m.name, "tag": m.tag, "town_hall": m.town_hall, "attacks_left": attacks_left, "map_position": m.map_position})
    pending.sort(key=lambda x: x.get("map_position", 0))
    return {"message": "Membros com ataques pendentes:", "members_pending": pending, "clan_name": clan_name_rem}

async def fetch_war_log_for_web_api(limit: int = 10) -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    if not WarLogEntry: logger.warning("WarLogEntry não está disponível, Histórico de Guerras desabilitado para o painel."); return {"error": "Histórico de Guerras indisponível (dependência não carregada).", "log": []}
    try:
        log_entries = await bot.coc_client.get_war_log(CLAN_TAG, limit=limit)
        entries = []
        for entry in log_entries:
            res = "N/A"
            if entry.clan and entry.clan.tag == CLAN_TAG:
                if entry.result: res = "Vitória" if entry.result == "win" else "Derrota" if entry.result == "lose" else "Empate"
            elif entry.opponent and entry.opponent.tag == CLAN_TAG:
                if entry.result: res = "Derrota" if entry.result == "win" else "Vitória" if entry.result == "lose" else "Empate"
            entries.append({
                "clan_name": entry.clan.name if entry.clan else "N/A", "clan_stars": entry.clan.stars if entry.clan else 0, "clan_destruction": entry.clan.destruction if entry.clan else 0.0,
                "clan_badge_url": entry.clan.badge.url if entry.clan and hasattr(entry.clan.badge, 'url') else None,
                "opponent_name": entry.opponent.name if entry.opponent else "N/A", "opponent_stars": entry.opponent.stars if entry.opponent else 0, "opponent_destruction": entry.opponent.destruction if entry.opponent else 0.0,
                "opponent_badge_url": entry.opponent.badge.url if entry.opponent and hasattr(entry.opponent.badge, 'url') else None,
                "team_size": entry.team_size, "end_time": entry.end_time.time.astimezone(TIMEZONE).strftime('%d/%m/%y %H:%M') if entry.end_time and hasattr(entry.end_time, 'time') else "N/A",
                "result": res, "is_cwl": getattr(entry, 'is_league_entry', False) or getattr(entry, 'is_cwl', False)
            })
        return {"log": entries}
    except coc.PrivateWarLog: return {"error": "Log de guerras do clã é privado."}
    except Exception as e: logger.error(f"Erro ao buscar histórico de guerras para API web: {e}", exc_info=True); return {"error": str(e), "log": []}

async def fetch_cwl_info_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    if not LeagueGroup: logger.warning("LeagueGroup não está disponível, funcionalidade de CWL desabilitada para o painel."); return {"status": "CwlFeatureDisabled", "message": "Funcionalidade de CWL indisponível (dependência não carregada)."}
    try:
        lg = await bot.coc_client.get_league_group(CLAN_TAG)
        if not lg or (hasattr(lg, 'state') and lg.state == "notInWar"): return {"status": "NotInCwl", "message": "Clã não está em CWL no momento."}
        rounds_data = []
        if hasattr(lg, 'rounds') and lg.rounds:
            for i, round_tags in enumerate(lg.rounds):
                r_info: Dict[str, Any] = {"round_number": i + 1, "wars": []}
                if not round_tags: r_info["wars"].append({"message": "Rodada não definida."})
                else:
                    for war_tag_val in round_tags:
                        if war_tag_val == "#0": r_info["wars"].append({"message":"Rodada de descanso (Bye)."}); continue
                        try:
                            # CORREÇÃO: Usar o método correto do objeto league_group (lg)
                            war = await lg.get_league_war(war_tag_val) 
                            our_display_clan, opp_display_clan = (war.clan, war.opponent)
                            if war.clan.tag != CLAN_TAG and war.opponent.tag == CLAN_TAG:
                                our_display_clan, opp_display_clan = opp_display_clan, our_display_clan
                            td = format_war_time_details(war, datetime.datetime.now(TIMEZONE))
                            r_info["wars"].append({
                                "war_tag": war_tag_val, "state": str(war.state), # Garantir que seja string
                                "clan_name": our_display_clan.name, "clan_stars": our_display_clan.stars, "clan_destruction":f"{our_display_clan.destruction:.2f}%", 
                                "clan_badge_url": our_display_clan.badge.url if hasattr(our_display_clan.badge, 'url') else None,
                                "opponent_name": opp_display_clan.name, "opponent_stars": opp_display_clan.stars, "opponent_destruction":f"{opp_display_clan.destruction:.2f}%", 
                                "opponent_badge_url": opp_display_clan.badge.url if hasattr(opp_display_clan.badge, 'url') else None,
                                **td
                            })
                        except AttributeError as e_attr_cwl_war:
                             logger.error(f"AttributeError ao buscar guerra CWL específica ({war_tag_val}) em fetch_cwl_info: {e_attr_cwl_war}")
                             r_info["wars"].append({"war_tag": war_tag_val, "error":f"Erro (AttributeError) ao carregar guerra: {e_attr_cwl_war}"})
                        except Exception as e_w: 
                            logger.error(f"Erro ao buscar guerra CWL específica ({war_tag_val}): {e_w}")
                            r_info["wars"].append({"war_tag": war_tag_val, "error":f"Erro ao carregar guerra: {e_w}"})
                rounds_data.append(r_info)
        clans_data = []
        if hasattr(lg, 'clans') and lg.clans:
            clans_data = [{"name":c.name, "tag":c.tag, "level":c.level, "badge_url":c.badge.url if hasattr(c.badge, 'url') else None} for c in lg.clans]
        
        season_str = "N/A" 
        if hasattr(lg, 'season') and lg.season:
            # CORREÇÃO: lg.season já é uma string
            season_str = lg.season 
        
        return {
            "status":"InCwl", "state": str(lg.state), # Garantir que seja string
            "season": season_str, 
            "clans_in_group":clans_data, "rounds":rounds_data
        }
    except coc.NotFound: return {"status": "NotInCwl", "message": "Grupo CWL não encontrado para o clã."}
    except Exception as e: logger.error(f"Erro ao buscar informações da CWL para API web: {e}", exc_info=True); return {"error":str(e), "status": "Error"}

async def api_clan_info_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_clan_info_{CLAN_TAG}", fetch_clan_info_for_web_api))
async def api_members_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_clan_members_{CLAN_TAG}", fetch_clan_members_for_web_api))
async def api_current_war_details_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_current_war_details_{CLAN_TAG}", fetch_current_war_details_for_web_api))
async def api_war_attacks_remaining_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_war_attacks_remaining_{CLAN_TAG}", fetch_war_attacks_remaining_for_web_api))
async def api_war_log_handler(request: web.Request) -> web.Response: limit = int(request.query.get("limit","10")); limit=max(1,min(limit,50)); return web.json_response(await get_cached_web_data(f"web_war_log_{CLAN_TAG}_limit{limit}",fetch_war_log_for_web_api,limit))
async def api_cwl_info_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_cwl_info_{CLAN_TAG}", fetch_cwl_info_for_web_api))
async def api_get_player_note_handler(request: web.Request) -> web.Response:
    player_tag = request.match_info.get('player_tag', None)
    if not player_tag: return web.json_response({"error": "Player tag não fornecida"}, status=400)
    player_tag_fmt = f"#{player_tag}" if not player_tag.startswith("#") else player_tag
    notes = load_player_notes()
    note_info = notes.get(player_tag_fmt, {"text": "", "priority": "none"})
    return web.json_response(note_info)
async def api_save_player_note_handler(request: web.Request) -> web.Response:
    player_tag = request.match_info.get('player_tag', None)
    if not player_tag: return web.json_response({"error": "Player tag não fornecida"}, status=400)
    player_tag_fmt = f"#{player_tag}" if not player_tag.startswith("#") else player_tag
    try:
        data = await request.json()
        note_text = data.get("text", "")
        note_priority = data.get("priority", "none")
        if note_priority not in ["none", "green", "yellow", "red"]: return web.json_response({"error": "Prioridade inválida"}, status=400)
        notes = load_player_notes()
        notes[player_tag_fmt] = {"text": note_text, "priority": note_priority}
        save_player_notes(notes) 
        logger.info(f"Nota salva localmente para {player_tag_fmt}: Prio: {note_priority}, Texto: '{note_text[:30]}...'")
        if f"web_clan_members_{CLAN_TAG}" in web_api_cache: del web_api_cache[f"web_clan_members_{CLAN_TAG}"]; logger.info(f"Cache de membros invalidado para {CLAN_TAG} após salvar nota local.")
        if f"web_current_war_details_{CLAN_TAG}" in web_api_cache: del web_api_cache[f"web_current_war_details_{CLAN_TAG}"]; logger.info(f"Cache de detalhes da guerra invalidado para {CLAN_TAG} após salvar nota.")
        return web.json_response({"success": True, "message": "Nota salva com sucesso."})
    except json.JSONDecodeError: return web.json_response({"error": "Payload JSON inválido"}, status=400)
    except Exception as e: logger.error(f"Erro ao salvar nota para {player_tag_fmt}: {e}", exc_info=True); return web.json_response({"error": "Erro interno ao salvar nota"}, status=500)

async def handle_panel_index(request: web.Request) -> web.FileResponse | web.Response:
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "painel.html")
    try: return web.FileResponse(index_path)
    except FileNotFoundError: logger.error(f"painel.html não encontrado em {index_path}"); return web.Response(text="Painel não encontrado.", status=404)
    except Exception as e: logger.error(f"Erro ao servir painel.html: {e}"); return web.Response(text="Erro ao carregar painel.", status=500)

async def setup_web_server() -> Optional[web.AppRunner]:
    app = web.Application()
    async def health_check(request: web.Request) -> web.Response: return web.Response(text=f"Bot running! Panel active! v{BOT_VERSION}")
    app.router.add_get("/api/clan", api_clan_info_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/current_war_details", api_current_war_details_handler)
    app.router.add_get("/api/war_attacks_remaining", api_war_attacks_remaining_handler)
    app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler)
    app.router.add_get("/api/notes/{player_tag}", api_get_player_note_handler)
    app.router.add_post("/api/notes/{player_tag}", api_save_player_note_handler)
    app.router.add_get("/painel", handle_panel_index)
    static_path = os.path.join(os.path.dirname(__file__), "static")
    for folder in ["css", "js", "images"]:
        path_to_create = os.path.join(static_path, folder)
        if not os.path.exists(path_to_create): os.makedirs(path_to_create); logger.info(f"Pasta '{path_to_create}' criada.")
    painel_html_path = os.path.join(static_path, "painel.html")
    if not os.path.exists(painel_html_path):
        with open(painel_html_path, "w", encoding='utf-8') as f: f.write("<!DOCTYPE html><html lang='pt-br'><head><meta charset='UTF-8'><title>Painel CoC</title><link rel='stylesheet' href='/static/css/style.css'></head><body><h1>Painel Carregando...</h1><script src='/static/js/scripts.js'></script></body></html>")
    style_css_path = os.path.join(static_path, "css", "style.css")
    if not os.path.exists(style_css_path):
        with open(style_css_path, "w", encoding='utf-8') as f: f.write("body { font-family: sans-serif; }")
    scripts_js_path = os.path.join(static_path, "js", "scripts.js")
    if not os.path.exists(scripts_js_path):
        with open(scripts_js_path, "w", encoding='utf-8') as f: f.write("console.log('Painel JS carregado.');")
    app.router.add_static('/static/', path=static_path, name='static', show_index=False)
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    try: await site.start(); logger.info(f"Servidor web iniciado: http://0.0.0.0:{port}"); return runner
    except Exception as e: logger.error(f"Falha ao iniciar servidor web: {e}", exc_info=True); return None

async def send_online_status(): # DEFINIÇÃO MOVIDA PARA CIMA
    if not CHANNEL_ID or CHANNEL_ID == 0: logger.warning("CHANNEL_ID não configurado (status online)."); return
    try:
        clan_name_online = "Clã Desconhecido"; clan_tag_fmt_online = CLAN_TAG or "Nenhum"
        if CLAN_TAG and hasattr(bot, 'coc_client') and bot.coc_client.http:
             try: clan_data_online = await bot.coc_client.get_clan(CLAN_TAG); clan_name_online = clan_data_online.name; clan_tag_fmt_online = clan_data_online.tag
             except Exception as e: logger.error(f"Erro ao buscar clã para status online: {e}")
        embed = discord.Embed(title="✅ Bot Online e Monitorando!", description=f"Eventos do clã **{clan_name_online}** (`{clan_tag_fmt_online}`) e Guerras monitorados.", color=discord.Color.green())
        embed.add_field(name="Monitoramento", value="Event-Driven Ativo 🔄", inline=False)
        await send_log_embed(embed); logger.info("Mensagem de status online enviada.")
    except Exception as e: logger.error(f"Erro ao enviar mensagem de status online: {e}", exc_info=True)

@bot.event
async def on_ready():
    logger.info(f"Bot {bot.user.name} (ID: {bot.user.id}) conectado ao Discord!")
    logger.info(f"Versão discord.py: {discord.__version__}")
    try: logger.info(f"Versão coc.py: {coc.__version__}")
    except AttributeError: logger.warning("Não foi possível determinar a versão do coc.py via coc.__version__.")
    logger.info(f"Versão Bot: {BOT_VERSION}"); logger.info(f"Pronto e operando em {len(bot.guilds)} servidor(es).")
    if hasattr(bot, 'coc_client') and bot.coc_client.http:
         logger.info("Cliente CoC parece estar pronto.")
         if not check_war_end_report_task.is_running():
              logger.info("Iniciando tarefa 'check_war_end_report_task'...");
              try: check_war_end_report_task.start()
              except RuntimeError as e: logger.error(f"Erro ao iniciar 'check_war_end_report_task': {e}")
         else: logger.info("'check_war_end_report_task' já em execução.")
    else: logger.warning("Cliente CoC não pronto no on_ready. Tarefas podem não iniciar.")
    await send_online_status()

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    cmd_name = interaction.command.qualified_name if interaction.command else 'Comando Desconhecido'
    embed = discord.Embed(title="❌ Erro de Comando", color=discord.Color.red()); orig_error = getattr(error, 'original', error); msg = f"Ocorreu um erro: {str(orig_error)}"
    if isinstance(orig_error, ValueError): msg=str(orig_error)
    elif isinstance(orig_error, coc.NotFound): msg = "Recurso não encontrado no CoC."
    elif isinstance(orig_error, coc.Maintenance): msg = "API CoC em manutenção."
    elif isinstance(orig_error, coc.PrivateWarLog): msg = "Log de guerra deste clã é privado."
    elif isinstance(orig_error, asyncio.TimeoutError): msg = "Tempo limite buscando dados da API CoC."
    elif isinstance(orig_error, coc.InvalidCredentials): msg = "Credenciais inválidas para API CoC."
    elif isinstance(orig_error, coc.Forbidden): msg = "Acesso proibido (Forbidden) à API CoC."
    elif isinstance(error, app_commands.CommandSignatureMismatch): msg = "Comando desatualizado. Tente sincronizar."
    elif isinstance(error, app_commands.CheckFailure): msg = "Você não tem permissão."
    elif isinstance(error, app_commands.CommandNotFound): msg = "Comando não encontrado."
    elif isinstance(error, app_commands.CommandOnCooldown): msg = f"Comando em cooldown. Tente em {error.retry_after:.1f}s."
    elif isinstance(error, app_commands.MissingRequiredArgument): msg = f"Argumento faltando: `{getattr(error.param, 'name', 'N/A')}`."
    elif isinstance(error, (app_commands.BadArgument, app_commands.ArgumentParsingError)): msg = f"Argumento inválido: {str(error)}"
    else: logger.error(f"Erro não tratado no comando '{cmd_name}': {orig_error}", exc_info=orig_error); msg = "Erro interno ao processar."
    embed.description=msg; embed.set_footer(text=f"Comando: /{cmd_name}"); embed.timestamp = datetime.datetime.now(TIMEZONE)
    try:
        if interaction.response.is_done(): await interaction.followup.send(embed=embed,ephemeral=True)
        else: await interaction.response.send_message(embed=embed,ephemeral=True)
    except Exception as e_send: logger.error(f"Erro ao enviar msg de erro da interação /{cmd_name}: {e_send}", exc_info=True)

async def register_coc_events(coc_client: coc.EventsClient):
    if not CLAN_TAG: logger.warning("CLAN_TAG não definido, eventos CoC não registrados."); return
    logger.info(f"Registrando manipuladores de eventos CoC para clã {CLAN_TAG}...")
    @coc_client.event
    @coc.ClanEvents.member_join(tags=[CLAN_TAG])
    async def on_member_join(old_member: Optional[ClanMember], member: ClanMember):
        if not member or not hasattr(member, 'clan'): logger.warning("Evento member_join com 'member' inválido."); return
        clan_obj = member.clan
        logger.info(f"Evento: {member.name} ({member.tag}) entrou em {clan_obj.name}.")
        embed = discord.Embed(title="👋 Novo Membro", description=f"**{member.name}** (`{member.tag}`) entrou no clã!", color=discord.Color.green())
        embed.add_field(name="CV", value=getattr(member, 'town_hall', '?'), inline=True); embed.add_field(name="Nível", value=getattr(member, 'exp_level', '?'), inline=True)
        embed.add_field(name="Troféus", value=getattr(member, 'trophies', '?'), inline=True)
        if hasattr(member, 'league') and member.league: embed.add_field(name="Liga", value=member.league.name, inline=True)
        if hasattr(clan_obj, 'badge') and clan_obj.badge: embed.set_author(name=clan_obj.name, icon_url=clan_obj.badge.url); embed.set_thumbnail(url=clan_obj.badge.url)
        await send_log_embed(embed)
    @coc_client.event
    @coc.ClanEvents.member_leave(tags=[CLAN_TAG])
    async def on_member_leave(old_member: ClanMember, member: ClanMember):
        if not old_member: logger.warning("Evento member_leave: 'old_member' não fornecido."); return
        clan_obj_leave = old_member.clan if hasattr(old_member, 'clan') else None
        clan_name_leave = getattr(clan_obj_leave, 'name', 'Clã Desconhecido')
        leaving_member_name = getattr(old_member, 'name', 'Membro Desconhecido'); leaving_member_tag = getattr(old_member, 'tag', 'Tag Desconhecida')
        logger.info(f"Evento: {leaving_member_name} ({leaving_member_tag}) saiu do clã {clan_name_leave}.")
        embed = discord.Embed(title="👋 Membro Saiu", description=f"**{leaving_member_name}** (`{leaving_member_tag}`) saiu do clã!", color=discord.Color.red())
        embed.add_field(name="CV", value=getattr(old_member, 'town_hall', '?'), inline=True); embed.add_field(name="Nível", value=getattr(old_member, 'exp_level', '?'), inline=True)
        embed.add_field(name="Troféus", value=getattr(old_member, 'trophies', '?'), inline=True); embed.add_field(name="Liga", value=getattr(old_member.league, 'name', 'Sem Liga') if old_member.league else 'Sem Liga', inline=True)
        if clan_obj_leave and hasattr(clan_obj_leave, 'badge') and clan_obj_leave.badge: embed.set_author(name=clan_name_leave, icon_url=clan_obj_leave.badge.url); embed.set_thumbnail(url=clan_obj_leave.badge.url)
        await send_log_embed(embed)
    @coc_client.event
    @coc.ClanEvents.member_donations(tags=[CLAN_TAG])
    async def on_member_donations(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan'): return
        donation_difference = member.donations - old_member.donations
        if donation_difference <= 0: return
        logger.info(f"Evento: {member.name} doou {donation_difference} tropas (Total: {member.donations}).")
        embed = discord.Embed(color=discord.Color.green())
        if hasattr(member.clan, 'badge') and member.clan.badge: embed.set_author(name=member.clan.name, icon_url=member.clan.badge.url); embed.set_thumbnail(url=member.clan.badge.url)
        embed.add_field(name="🎁 Doação", value=f"**{donation_difference}** tropas por `{member.name}` (Total: {member.donations})", inline=False)
        await send_log_embed(embed)
    @coc_client.event
    @coc.ClanEvents.member_received(tags=[CLAN_TAG])
    async def on_member_received(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan'): return
        received_difference = member.received - old_member.received
        if received_difference <= 0: return
        logger.info(f"Evento: {member.name} recebeu {received_difference} tropas (Total: {member.received}).")
        embed = discord.Embed(color=discord.Color.blue())
        if hasattr(member.clan, 'badge') and member.clan.badge: embed.set_author(name=member.clan.name, icon_url=member.clan.badge.url); embed.set_thumbnail(url=member.clan.badge.url)
        embed.add_field(name="📥 Recebimento", value=f"`{member.name}` recebeu **{received_difference}** tropas (Total: {member.received})", inline=False)
        await send_log_embed(embed)
    @coc_client.event
    @coc.ClanEvents.member_role_change(tags=[CLAN_TAG])
    async def on_member_role_change(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan'): return
        old_role_name = old_member.role.name if old_member.role else None; new_role_name = member.role.name if member.role else None
        if old_role_name == new_role_name: return
        logger.info(f"Evento: Cargo de {member.name} mudou de {old_role_name} para {new_role_name} em {member.clan.name}.")
        embed = discord.Embed(title="🔄 Mudança de Cargo", description=f"Cargo de **{member.name}** (`{member.tag}`) alterado!", color=discord.Color.gold())
        embed.add_field(name="Cargo Anterior", value=old_role_name.capitalize() if old_role_name else 'N/A', inline=True)
        embed.add_field(name="Novo Cargo", value=new_role_name.capitalize() if new_role_name else 'N/A', inline=True)
        if hasattr(member.clan, 'badge') and member.clan.badge: embed.set_author(name=member.clan.name, icon_url=member.clan.badge.url); embed.set_thumbnail(url=member.clan.badge.url)
        await send_log_embed(embed)
    @coc_client.event
    @coc.ClanEvents.member_league_change(tags=[CLAN_TAG])
    async def on_member_league_change(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan'): return
        old_league_name_event = old_member.league.name if old_member.league else "Sem Liga"; new_league_name_event = member.league.name if member.league else "Sem Liga"
        if old_league_name_event == new_league_name_event: return
        logger.info(f"Evento: Liga de {member.name} mudou de {old_league_name_event} para {new_league_name_event} em {member.clan.name}.")
        embed_league_evt = discord.Embed(title="🏆 Mudança de Liga", description=f"Liga de **{member.name}** (`{member.tag}`) alterada!", color=discord.Color.purple())
        embed_league_evt.add_field(name="Liga Anterior", value=old_league_name_event, inline=True); embed_league_evt.add_field(name="Nova Liga", value=new_league_name_event, inline=True)
        if hasattr(member.clan, 'badge') and member.clan.badge: embed_league_evt.set_author(name=member.clan.name, icon_url=member.clan.badge.url); embed_league_evt.set_thumbnail(url=member.clan.badge.url)
        await send_log_embed(embed_league_evt)
    @coc_client.event
    @coc.ClanEvents.member_trophies_change(tags=[CLAN_TAG])
    async def on_member_trophies_change(old_member: ClanMember, member: ClanMember):
        if not member or not old_member: logger.warning("Evento member_trophies_change com member/old_member inválido."); return
        trophy_difference = member.trophies - old_member.trophies
        if abs(trophy_difference) < 5: return
        logger.info(f"Evento: Troféus de {member.name} mudaram em {trophy_difference} (Total: {member.trophies}).")
        direction = "ganhou" if trophy_difference > 0 else "perdeu"
        embed = discord.Embed(description=f"**{member.name}** {direction} **{abs(trophy_difference)}** troféus (Total: {member.trophies})", color=discord.Color.green() if trophy_difference > 0 else discord.Color.dark_red())
        await send_log_embed(embed)
    @coc_client.event
    @coc.WarEvents.war_attack(tags=[CLAN_TAG])
    async def on_war_attack(attack: WarAttack, war: ClanWar):
        if not all(hasattr(attack, attr) for attr in ['attacker_tag', 'defender_tag', 'stars', 'destruction', 'order']):
            logger.warning(f"Evento de ataque de guerra incompleto. War Tag: {getattr(war, 'tag', 'N/A')}"); return
        player_short_term_cache.clear()
        try: attacker = await get_player_data(attack.attacker_tag); att_clan_tag = attacker.clan.tag if attacker.clan else None
        except ValueError: att_clan_tag = None; attacker = None
        try: defender = await get_player_data(attack.defender_tag); def_clan_tag = defender.clan.tag if defender.clan else None
        except ValueError: def_clan_tag = None; defender = None
        is_our_attack = att_clan_tag == CLAN_TAG; is_our_defense = def_clan_tag == CLAN_TAG
        if not (is_our_attack or is_our_defense): return
        att_name = attacker.name if attacker else attack.attacker_tag; att_th_val = attacker.town_hall if attacker else '?'
        def_name = defender.name if defender else attack.defender_tag; def_th_val = defender.town_hall if defender else '?'
        stars_str = "⭐" * attack.stars + "⚫" * (3 - attack.stars); content_msg = None
        our_war_clan_obj = war.clan if war.clan and war.clan.tag == CLAN_TAG else war.opponent if war.opponent and war.opponent.tag == CLAN_TAG else None
        enemy_war_clan_obj = war.opponent if war.clan and war.clan.tag == CLAN_TAG else war.clan if war.opponent and war.opponent.tag == CLAN_TAG else None
        if is_our_attack:
            logger.info(f"Evento Guerra: {att_name} atacou {def_name} - {attack.stars}*, {attack.destruction}%.")
            embed = discord.Embed(title=f"⚔️ Ataque Realizado (Guerra)", description=f"**{att_name}** (CV{att_th_val}) atacou **{def_name}** (CV{def_th_val})", color=discord.Color.blue())
            embed.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
            if attack.stars <= 1 and ROLE_ID_1STAR_ALERT:
                try:
                    log_ch = await bot.fetch_channel(CHANNEL_ID)
                    if log_ch and hasattr(log_ch, 'guild'):
                        guild_obj_alert = log_ch.guild
                        role_obj = guild_obj_alert.get_role(int(ROLE_ID_1STAR_ALERT))
                        if role_obj: content_msg = f"{role_obj.mention} ⚠️ Ataque fora do padrão!"
                except Exception as e_alert: logger.error(f"Erro alerta 1 estrela: {e_alert}")
            if our_war_clan_obj and hasattr(our_war_clan_obj, 'badge') and our_war_clan_obj.badge:
                 embed.set_author(name=our_war_clan_obj.name, icon_url=our_war_clan_obj.badge.url); embed.set_thumbnail(url=our_war_clan_obj.badge.url)
            await send_log_embed(embed, content_msg)
        elif is_our_defense:
            logger.info(f"Evento Guerra: {def_name} foi atacado por {att_name} - {attack.stars}*, {attack.destruction}%.")
            embed = discord.Embed(title=f"🛡️ Defesa Recebida (Guerra)", description=f"**{def_name}** (CV{def_th_val}) foi atacado por **{att_name}** (CV{att_th_val})", color=discord.Color.orange())
            embed.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
            if enemy_war_clan_obj and hasattr(enemy_war_clan_obj, 'badge') and enemy_war_clan_obj.badge:
                 embed.set_author(name=enemy_war_clan_obj.name, icon_url=enemy_war_clan_obj.badge.url); embed.set_thumbnail(url=enemy_war_clan_obj.badge.url)
            await send_log_embed(embed)
    logger.info("Manipuladores de eventos CoC registrados.")

@tasks.loop(minutes=10)
async def check_war_end_report_task():
    if not bot.coc_client or not bot.coc_client.http: logger.debug("check_war_end_report_task: CoC Client não pronto."); return
    logger.debug("check_war_end_report_task: Iniciando verificação de fim de guerra..."); 
    processed_ids_cycle: Set[str] = set()

    async def process_war_for_report(war: ClanWar, war_type: str):
        war_id = war.tag if hasattr(war, 'tag') and war.tag and war.tag != "#0" else \
                 f"REG-{war.opponent.tag if war.opponent else 'NA'}-{war.end_time.raw_time if war.end_time else 'NA'}"
        if not war_id or war_id in processed_ids_cycle: return
        if war.state == "warEnded" and war_id not in reported_war_ends:
            our_clan_obj_task = None
            if war.clan and war.clan.tag == CLAN_TAG: our_clan_obj_task = war.clan
            elif war.opponent and war.opponent.tag == CLAN_TAG: our_clan_obj_task = war.opponent
            if not our_clan_obj_task: 
                logger.error(f"check_war_end_report_task: Nosso clã não encontrado na guerra {war_id}.")
                processed_ids_cycle.add(war_id); return
            missed_attacks_details = []
            if hasattr(our_clan_obj_task, 'members') and our_clan_obj_task.members:
                for m in our_clan_obj_task.members:
                    attacks_made = len(m.attacks) if m.attacks else 0
                    attacks_left = war.attacks_per_member - attacks_made
                    if attacks_left > 0: missed_attacks_details.append(f"**{m.name}** (CV{m.town_hall}): {attacks_left} ataque{'s' if attacks_left > 1 else ''} perdido{'s' if attacks_left > 1 else ''}")
            if missed_attacks_details:
                await send_missed_attacks_report(war, missed_attacks_details, war_type)
                logger.info(f"Relatório de ataques perdidos enviado para {war_type} ID: {war_id}")
            else: logger.info(f"check_war_end_report_task: Nenhum ataque perdido em {war_type} (ID: {war_id}).")
            reported_war_ends.add(war_id)
        processed_ids_cycle.add(war_id)

    try: 
        reg_war = await bot.coc_client.get_current_war(CLAN_TAG)
        if reg_war and reg_war.state != "notInWar" and hasattr(reg_war, 'end_time'):
            await process_war_for_report(reg_war, "Guerra Normal")
    except Exception as e: logger.error(f"check_war_end_report_task: Erro ao verificar guerra regular: {e}", exc_info=True)
    
    try: 
        if LeagueGroup:
            lg_task = await bot.coc_client.get_league_group(CLAN_TAG)
            if lg_task and lg_task.state != "notInWar" and hasattr(lg_task, 'rounds') and lg_task.rounds:
                for i, rd_tags_task in enumerate(lg_task.rounds):
                    for tag_val_cwl_task_inner in rd_tags_task:
                        if tag_val_cwl_task_inner == "#0": continue
                        try: 
                            # CORREÇÃO: Usar bot.coc_client.get_league_war() para guerras de CWL
                            cwl_war_task = await bot.coc_client.get_league_war(tag_val_cwl_task_inner)
                            if cwl_war_task and \
                               (cwl_war_task.clan.tag == CLAN_TAG or cwl_war_task.opponent.tag == CLAN_TAG) and \
                               hasattr(cwl_war_task, 'end_time'):
                                await process_war_for_report(cwl_war_task, f"Liga (Rodada {i+1})")
                        except coc.NotFound: 
                            logger.debug(f"Guerra CWL específica {tag_val_cwl_task_inner} não encontrada na task.")
                            continue
                        except AttributeError as e_attr: 
                            logger.error(f"AttributeError ao processar guerra CWL {tag_val_cwl_task_inner} na task: {e_attr}", exc_info=True)
                        except Exception as e_inner_cwl: 
                            logger.error(f"Erro ao processar guerra CWL específica {tag_val_cwl_task_inner} na task: {e_inner_cwl}", exc_info=True)
    except Exception as e: logger.error(f"check_war_end_report_task: Erro ao verificar guerras CWL: {e}", exc_info=True)
    logger.debug("check_war_end_report_task: Verificação de fim de guerra concluída.")

@check_war_end_report_task.before_loop
async def before_check_war():
    logger.info("Aguardando bot para iniciar 'check_war_end_report_task'...")
    await bot.wait_until_ready()
    logger.info("Bot pronto. 'check_war_end_report_task' pode iniciar.")

admin_group = app_commands.Group(name="admin", description="Comandos administrativos")
war_group = app_commands.Group(name="guerra", description="Comandos relacionados a guerras")
info_group = app_commands.Group(name="info", description="Comandos de informação")
search_group = app_commands.Group(name="buscar", description="Comandos de busca")
rank_group = app_commands.Group(name="rank", description="Comandos de ranking")
bot.tree.add_command(admin_group); bot.tree.add_command(war_group); bot.tree.add_command(info_group)
bot.tree.add_command(search_group); bot.tree.add_command(rank_group)

@admin_group.command(name="ping", description="Verifica a latência do bot")
@app_commands.checks.has_permissions(administrator=True)
async def admin_ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", description=f"Latência API Discord: **{latency_ms}ms**",
                          color=discord.Color.green() if latency_ms < 200 else discord.Color.orange() if latency_ms < 500 else discord.Color.red())
    embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed.timestamp = datetime.datetime.now(TIMEZONE)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@war_group.command(name="ataques", description="Exibe os ataques restantes na guerra atual (Normal ou Liga)")
async def war_attacks(interaction: discord.Interaction):
    await interaction.response.defer()
    current_war_cmd: Optional[ClanWar] = await get_current_or_last_war(CLAN_TAG)
    if current_war_cmd and isinstance(current_war_cmd, coc.ClanWar) and current_war_cmd.state == "inWar":
        embeds_list_cmd = await format_attacks_remaining_embed(current_war_cmd)
        if embeds_list_cmd:
            first_embed_cmd = embeds_list_cmd.pop(0); await interaction.followup.send(embed=first_embed_cmd)
            for embed_item_cmd in embeds_list_cmd:
                try:
                    if interaction.channel and isinstance(interaction.channel, discord.abc.Messageable): await interaction.channel.send(embed=embed_item_cmd)
                    else: logger.warning("interaction.channel não acessível para embeds adicionais de /guerra ataques."); break
                except Exception as e: logger.error(f"Erro ao enviar embed adicional de /guerra ataques: {e}"); break
        else: await interaction.followup.send(f"Erro ao formatar informações de ataques.", ephemeral=True)
    elif current_war_cmd:
        await interaction.followup.send(f"O clã está em uma guerra, mas o estado atual é '{current_war_cmd.state}'. Ataques restantes são mostrados apenas para guerras 'inWar'.")
    else: await interaction.followup.send("O clã não está em nenhuma guerra ativa (Normal ou Liga) no momento.")

@war_group.command(name="status", description="Exibe o status da guerra atual (Normal ou Liga)")
async def war_status(interaction: discord.Interaction):
    await interaction.response.defer()
    war_to_display: Optional[ClanWar] = await get_current_or_last_war(CLAN_TAG)
    war_type_name_status = "Guerra"; status_description = "Nenhuma guerra ativa ou recente encontrada."; status_color = discord.Color.greyple()
    if war_to_display and isinstance(war_to_display, coc.ClanWar):
        clan_disp, opp_disp = war_to_display.clan, war_to_display.opponent
        if war_to_display.clan.tag != CLAN_TAG and war_to_display.opponent.tag == CLAN_TAG: clan_disp, opp_disp = opp_disp, clan_disp
        if hasattr(war_to_display, 'is_cwl') and war_to_display.is_cwl: war_type_name_status = "Liga (CWL)"
        elif hasattr(war_to_display, 'type') and war_to_display.type == "friendly": war_type_name_status = "Amistosa"
        else: war_type_name_status = "Guerra Normal"
        embed_status_final = discord.Embed(title=f"⚔️ Status: {war_type_name_status} - {clan_disp.name} vs {opp_disp.name}", color=status_color)
        if hasattr(clan_disp, 'badge') and clan_disp.badge: embed_status_final.set_thumbnail(url=clan_disp.badge.url)
        time_details_status = format_war_time_details(war_to_display, datetime.datetime.now(TIMEZONE))
        state_disp = war_to_display.state
        
        state_desc_str = str(state_disp).capitalize() if state_disp else 'Desconhecido'

        if state_disp == "preparation":
            embed_status_final.description = f"**Estado:** Preparação ⏳\n**{time_details_status['time_key']}:** {time_details_status['time_value']} (em ~{time_details_status['time_remaining']})"
            embed_status_final.color = discord.Color.light_grey()
        elif state_disp == "inWar":
            embed_status_final.description = f"**Estado:** Em Guerra 🔥\n**{time_details_status['time_key']}:** {time_details_status['time_value']} ({time_details_status['time_remaining']} restantes)"
            embed_status_final.add_field(name=f"{clan_disp.name}", value=f"{clan_disp.stars}⭐ ({clan_disp.destruction:.2f}%)", inline=True)
            embed_status_final.add_field(name=f"{opp_disp.name}", value=f"{opp_disp.stars}⭐ ({opp_disp.destruction:.2f}%)", inline=True)
            embed_status_final.color = discord.Color.blue()
        elif state_disp == "warEnded":
            result_disp = "Empate 🤝"; color_res = discord.Color.greyple()
            if clan_disp.stars > opp_disp.stars or (clan_disp.stars == opp_disp.stars and clan_disp.destruction > opp_disp.destruction): result_disp = "Vitória ✅"; color_res = discord.Color.green()
            elif opp_disp.stars > clan_disp.stars or (clan_disp.stars == opp_disp.stars and opp_disp.destruction > clan_disp.destruction): result_disp = "Derrota ❌"; color_res = discord.Color.red()
            embed_status_final.description = f"**Estado:** Guerra Finalizada\n**Resultado:** {result_disp}\n**{time_details_status['time_key']}:** {time_details_status['time_value']}"
            embed_status_final.add_field(name=f"{clan_disp.name}", value=f"{clan_disp.stars}⭐ ({clan_disp.destruction:.2f}%)", inline=True)
            embed_status_final.add_field(name=f"{opp_disp.name}", value=f"{opp_disp.stars}⭐ ({opp_disp.destruction:.2f}%)", inline=True)
            embed_status_final.color = color_res
        else: embed_status_final.description = f"**Estado:** {state_desc_str}\nNenhuma guerra ativa."; embed_status_final.title = f"⚔️ Status Guerra: {clan_disp.name}"
    else: embed_status_final = discord.Embed(title=f"⚔️ Status Guerra", description=status_description, color=status_color)
    embed_status_final.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed_status_final.timestamp = datetime.datetime.now(TIMEZONE)
    await interaction.followup.send(embed=embed_status_final)

async def setup_hook():
    logger.info("Executando setup_hook...")
    logger.info("Inicializando cliente CoC...")
    bot.coc_client = coc.EventsClient()
    max_retries = 3; retry_delay = 5; login_success = False
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentativa login CoC ({attempt + 1}/{max_retries})...");
            if not COC_EMAIL or not COC_PASSWORD: logger.error("COC_EMAIL/PASSWORD não definidos."); break
            await bot.coc_client.login(COC_EMAIL, COC_PASSWORD); logger.info("Login CoC OK!"); login_success = True; break
        except coc.InvalidCredentials as e: logger.error(f"Login CoC Falhou: Credenciais Inválidas. {e}"); break
        except coc.Maintenance as e: logger.warning(f"API CoC em manutenção: {e}."); break
        except asyncio.TimeoutError: logger.error(f"Timeout login CoC (Tentativa {attempt + 1}).");
        except Exception as e: logger.error(f"Erro login CoC (Tentativa {attempt + 1}): {e}", exc_info=True);
        if attempt < max_retries - 1: await asyncio.sleep(retry_delay)
    if not login_success: logger.error("Não foi possível logar no CoC.")
    else:
         logger.info("Registrando listeners de eventos CoC..."); await register_coc_events(bot.coc_client)
         if CLAN_TAG:
             logger.info(f"Adicionando atualizações de eventos para o clã: {CLAN_TAG}")
             try: bot.coc_client.add_clan_updates(CLAN_TAG); bot.coc_client.add_war_updates(CLAN_TAG); logger.info("Atualizações de clã e guerra ativadas.")
             except Exception as e: logger.error(f"Erro ao adicionar atualizações de eventos para {CLAN_TAG}: {e}", exc_info=True)
         else: logger.warning("CLAN_TAG não definido. Atualizações CoC não ativadas.")
    logger.info("Configurando servidor web para painel..."); bot.web_runner = await setup_web_server()
    if bot.web_runner: logger.info("Servidor web configurado.")
    else: logger.warning("Falha ao configurar servidor web.")
    logger.info("Sincronizando comandos de app no setup_hook..."); synced_cmds = []
    try:
        guild_obj_sync = None
        if TEST_GUILD_ID:
            try: guild_obj_sync = discord.Object(id=int(TEST_GUILD_ID))
            except (ValueError, TypeError): logger.error(f"TEST_GUILD_ID ('{TEST_GUILD_ID}') inválido. Sincronizando globalmente...")
        if guild_obj_sync:
            bot.tree.copy_global_to(guild=guild_obj_sync)
            synced_cmds = await bot.tree.sync(guild=guild_obj_sync)
        else: synced_cmds = await bot.tree.sync()
        logger.info(f"{len(synced_cmds)} comandos (/) sincronizados.")
        if not synced_cmds and bot.tree.get_commands(): logger.warning("Nenhum comando sincronizado, mas a tree possui comandos.")
    except Exception as e: logger.error(f"Erro ao sincronizar comandos (/): {e}", exc_info=True)
    logger.info("setup_hook concluído.")

async def main():
    bot.setup_hook = setup_hook
    async with bot:
        try:
            if not DISCORD_TOKEN: logger.critical("DISCORD_TOKEN não encontrado!"); return
            logger.info("Iniciando conexão com o Discord..."); await bot.start(DISCORD_TOKEN)
        except discord.LoginFailure: logger.critical("Login Discord Falhou: Token inválido.")
        except discord.PrivilegedIntentsRequired as e: logger.critical(f"Intents Privilegiadas não habilitadas: {e.shard_id if hasattr(e, 'shard_id') else ''}")
        except Exception as e: logger.critical(f"Erro crítico no bot: {e}", exc_info=True)
        finally:
            logger.info("Desligando o bot...")
            if 'check_war_end_report_task' in globals() and check_war_end_report_task.is_running():
                 check_war_end_report_task.cancel()
                 try: await asyncio.sleep(1)
                 except asyncio.CancelledError: logger.info("check_war_end_report_task cancelada.")
            if hasattr(bot, "web_runner") and bot.web_runner: logger.info("Limpando web runner..."); await bot.web_runner.cleanup(); logger.info("Servidor web limpo.")
            if hasattr(bot, "coc_client") and bot.coc_client.http and not bot.coc_client.http.closed : logger.info("Fechando cliente CoC..."); await bot.coc_client.close(); logger.info("Cliente CoC fechado.")
            logger.info("Desligamento do bot concluído.")

def handle_asyncio_exception(loop: asyncio.AbstractEventLoop, context: Dict[str, Any]):
    msg = context.get("exception", context["message"])
    logger.error(f"Erro asyncio não tratado: {msg}", exc_info=context.get('exception'))

if __name__ == "__main__":
    required_env_vars = ["DISCORD_TOKEN", "COC_EMAIL", "COC_PASSWORD", "CLAN_TAG", "CHANNEL_ID"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars: logger.critical(f"Variáveis de ambiente essenciais faltando: {', '.join(missing_vars)}. Verifique seu arquivo .env."); exit(1)
    loop = asyncio.get_event_loop()
    try:
        loop.set_exception_handler(handle_asyncio_exception)
        loop.run_until_complete(main())
    except KeyboardInterrupt: logger.info("Bot interrompido pelo usuário (KeyboardInterrupt).")
    except RuntimeError as e_loop:
        if "Event loop is closed" in str(e_loop): logger.info("Loop de eventos fechado durante o desligamento (normal).")
        else: logger.warning(f"RuntimeError no loop de eventos: {e_loop}", exc_info=True)
    except Exception as e_fatal: logger.critical(f"Erro fatal não capturado no loop principal: {e_fatal}", exc_info=True)
    finally:
        logger.info("Iniciando processo de finalização do loop de eventos...")
        if loop.is_running(): logger.info("Parando o loop de eventos..."); loop.stop()
        tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not asyncio.current_task(loop=loop)]
        if tasks:
            logger.info(f"Cancelando {len(tasks)} tarefas pendentes...")
            for task in tasks: task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            logger.info("Tarefas pendentes canceladas.")
        if not loop.is_closed(): logger.info("Fechando o loop de eventos..."); loop.close(); logger.info("Loop de eventos fechado.")
        else: logger.info("Loop de eventos já estava fechado.")
        logger.info("Programa finalizado.")
