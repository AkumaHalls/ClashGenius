# -*- coding: utf-8 -*-
# Versão 19.3 - (Painel web expandido, correções de import WarLogEntry, LeagueGroup, CapitalDistrict e sintaxe)

import os
import logging
import asyncio
import datetime
from aiohttp import web
from typing import Dict, List, Optional, Union, Set, Any
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc

# ---- CORREÇÃO E ADIÇÃO DE IMPORTAÇÕES ESPECÍFICAS ----
from coc import (
    ClanWar,
    Player,
    Clan,
    WarAttack,
    Timestamp,
    ClanMember
)
# LeagueGroup e WarLogEntry são frequentemente encontrados em coc.wars
from coc.wars import WarLogEntry, LeagueGroup
# CapitalDistrict pode estar em coc.clans ou coc.capital
from coc.clans import CapitalDistrict # Tentativa comum para CapitalDistrict
# Se CapitalDistrict ainda causar erro, pode ser necessário ajustar para coc.capital ou outro local
# ---- FIM DA SEÇÃO DE IMPORTAÇÕES ESPECÍFICAS ----

import pytz
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("coc_discord_bot")

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COC_EMAIL = os.getenv("COC_EMAIL")
COC_PASSWORD = os.getenv("COC_PASSWORD")
CLAN_TAG = os.getenv("CLAN_TAG")

try:
    channel_id_str = os.environ.get("CHANNEL_ID")
    if channel_id_str:
        CHANNEL_ID = int(channel_id_str)
    else:
        CHANNEL_ID = 0 
        logger.error("CHANNEL_ID não definido no .env. Usando 0 como padrão.")
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

BOT_VERSION = "19.3" 

reported_war_ends: Set[str] = set()
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

player_short_term_cache: Dict[str, Player] = {}
clan_cache: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION_SECONDS = 300 

async def get_clan_data_base(tag: str) -> Clan:
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        if not tag.startswith("#"):
            tag = f"#{tag}"
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
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        locations = await bot.coc_client.search_locations(name=location_name, limit=1)
        if not locations: raise ValueError(f"Localização '{location_name}' não encontrada.")
        loc_obj = locations[0] 
        if hasattr(loc_obj, 'id'): return loc_obj.id
        else: raise ValueError(f"Objeto de localização para '{location_name}' não possui ID.")
    except Exception as e: logger.error(f"Erro ao buscar ID da localização '{location_name}': {e}", exc_info=True); raise ValueError(f"Erro ao buscar ID da localização: {str(e)}")

async def send_log_embed(embed_to_log: discord.Embed, content: str = None) -> None:
    if not CHANNEL_ID or CHANNEL_ID == 0: logger.warning("CHANNEL_ID não configurado."); return
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
         if not embed_empty_split.timestamp:
             embed_empty_split.timestamp = datetime.datetime.now(TIMEZONE)
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

# --- FUNÇÕES HELPER PARA O PAINEL WEB ---
def format_war_time_details(war_obj: ClanWar, time_now_tz: datetime.datetime) -> Dict[str, Any]:
    details: Dict[str, Any] = { "time_key": "N/A", "time_value": "N/A", "time_remaining": "N/A", "start_time_iso": None, "end_time_iso": None }
    if hasattr(war_obj, 'state') and war_obj.state == "preparation":
        if hasattr(war_obj, 'start_time') and war_obj.start_time and hasattr(war_obj.start_time, 'time'):
            start_aware = pytz.utc.localize(war_obj.start_time.time).astimezone(TIMEZONE)
            details["start_time_iso"] = start_aware.isoformat(); details["time_key"] = "Início"; details["time_value"] = start_aware.strftime('%d/%m %H:%M')
            delta = start_aware - time_now_tz
            if delta.total_seconds() > 0: d, r = divmod(delta.total_seconds(), 86400); h, r = divmod(r, 3600); m, _ = divmod(r, 60); details["time_remaining"] = f"{int(d)}d {int(h)}h {int(m)}m" if d > 0 else f"{int(h)}h {int(m)}m"
            else: details["time_remaining"] = "Iniciando..."
    elif hasattr(war_obj, 'state') and (war_obj.state == "inWar" or war_obj.state == "warEnded"):
        if hasattr(war_obj, 'end_time') and war_obj.end_time and hasattr(war_obj.end_time, 'time'):
            end_aware = pytz.utc.localize(war_obj.end_time.time).astimezone(TIMEZONE)
            details["end_time_iso"] = end_aware.isoformat(); details["time_key"] = "Fim" if war_obj.state == "inWar" else "Finalizada em"; details["time_value"] = end_aware.strftime('%d/%m %H:%M')
            if war_obj.state == "inWar":
                delta = end_aware - time_now_tz
                if delta.total_seconds() > 0: d, r = divmod(delta.total_seconds(), 86400); h, r = divmod(r, 3600); m, _ = divmod(r, 60); details["time_remaining"] = f"{int(d)}d {int(h)}h {int(m)}m" if d > 0 else f"{int(h)}h {int(m)}m"
                else: details["time_remaining"] = "Finalizando..."
            else: details["time_remaining"] = "-"
    return details

async def get_current_or_last_war(clan_tag_param: str) -> Optional[ClanWar]:
    current_war: Optional[ClanWar] = None
    try: 
        league_group = await bot.coc_client.get_league_group(clan_tag_param)
        if league_group and getattr(league_group,'state',None) != "notInWar" and hasattr(league_group, 'rounds'):
            if hasattr(league_group, 'current_wars') and league_group.current_wars:
                for war_tag_obj in reversed(league_group.current_wars):
                    try:
                        lg_war = await league_group.get_league_war(war_tag_obj.tag)
                        if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param) and lg_war.state in ["inWar", "preparation"]:
                            current_war = lg_war; 
                            if lg_war.opponent.tag == clan_tag_param: current_war.clan, current_war.opponent = current_war.opponent, current_war.clan
                            return current_war
                    except (coc.NotFound, Exception): continue
            for war_tags_in_round in reversed(league_group.rounds): 
                for war_tag_str in war_tags_in_round:
                    if war_tag_str == "#0": continue
                    try:
                        lg_war = await league_group.get_league_war(war_tag_str)
                        if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param) and lg_war.state in ["inWar", "preparation"]:
                            current_war = lg_war
                            if lg_war.opponent.tag == clan_tag_param: current_war.clan, current_war.opponent = current_war.opponent, current_war.clan
                            return current_war
                    except (coc.NotFound, Exception): continue
            if not current_war and league_group.rounds: 
                for war_tags_in_round in reversed(league_group.rounds):
                    for war_tag_str in war_tags_in_round:
                        if war_tag_str == "#0": continue
                        try:
                            lg_war = await league_group.get_league_war(war_tag_str)
                            if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param) and lg_war.state == "warEnded":
                                if lg_war.opponent.tag == clan_tag_param: lg_war.clan, lg_war.opponent = lg_war.opponent, lg_war.clan
                                return lg_war 
                        except (coc.NotFound, Exception): continue
    except coc.NotFound: logger.debug(f"Nenhum grupo CWL para {clan_tag_param}.")
    except Exception as e_cwl: logger.error(f"Erro guerra CWL para {clan_tag_param}: {e_cwl}", exc_info=True)
    try: 
        regular_war = await bot.coc_client.get_current_war(clan_tag_param)
        if regular_war and regular_war.state != "notInWar": return regular_war
    except coc.PrivateWarLog: logger.warning(f"Log guerra regular {clan_tag_param} privado.")
    except coc.NotFound: logger.debug(f"Nenhuma guerra regular para {clan_tag_param}.")
    except Exception as e_reg: logger.error(f"Erro guerra regular para {clan_tag_param}: {e_reg}", exc_info=True)
    return None

# ============================================================================ #
# ==================== INÍCIO DAS MODIFICAÇÕES PARA PAINEL WEB ==================== #
# ============================================================================ #
web_api_cache: Dict[str, Dict[str, Any]] = {} 
WEB_API_CACHE_DURATION_SECONDS = 60

async def get_cached_web_data(key: str, func_to_fetch_data: callable, *args: Any) -> Any:
    now = datetime.datetime.now()
    if key in web_api_cache:
        cache_entry = web_api_cache[key]
        if "timestamp" in cache_entry and isinstance(cache_entry["timestamp"], datetime.datetime):
            if (now - cache_entry["timestamp"]).total_seconds() < WEB_API_CACHE_DURATION_SECONDS: return cache_entry["data"]
    data = await func_to_fetch_data(*args)
    web_api_cache[key] = {"data": data, "timestamp": now}
    return data

async def fetch_clan_info_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG); districts = []
        if hasattr(clan, 'capital_districts') and clan.capital_districts:
            for d in clan.capital_districts: districts.append({"name": d.name, "level": d.hall_level})
        return {"name": clan.name, "tag": clan.tag, "level": clan.level, "points": clan.points,
                "capital_points": getattr(clan, 'capital_points', 0), "member_count": clan.member_count, 
                "description": clan.description, "war_wins": getattr(clan, 'war_wins', 'N/A'),
                "location": clan.location.name if hasattr(clan, 'location') and clan.location else "N/A",
                "type": clan.type.capitalize() if hasattr(clan, 'type') else "N/A",
                "badge_url": clan.badge.url if hasattr(clan, 'badge') and clan.badge else None,
                "version": BOT_VERSION, "capital_districts": districts,
                "capital_league": clan.capital_league.name if hasattr(clan, 'capital_league') and clan.capital_league else "N/A"}
    except Exception as e: logger.error(f"Erro API clã web: {e}", exc_info=True); return {"error": str(e), "name": "Erro Clã"}

async def fetch_clan_members_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG); members = []
        if hasattr(clan, 'members') and clan.members:
            for m in clan.members: members.append({"name": m.name, "tag": m.tag, "town_hall": m.town_hall, "exp_level": m.exp_level,
                                                 "league": m.league.name if hasattr(m, 'league') and m.league else "N/A",
                                                 "trophies": m.trophies, "role": m.role.name.capitalize() if hasattr(m, 'role') and m.role else "Membro",
                                                 "donations": m.donations, "received": m.received})
        members.sort(key=lambda x: x.get("trophies", 0), reverse=True)
        return {"members": members, "clan_name": clan.name, "clan_tag": clan.tag}
    except Exception as e: logger.error(f"Erro API membros web: {e}", exc_info=True); return {"error": str(e)}

async def fetch_war_status_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    war = await get_current_or_last_war(CLAN_TAG)
    if not war: return {"status": "NotInWar", "message": "Nenhuma guerra ativa/recente.", "type": "Nenhuma"}
    td = format_war_time_details(war, datetime.datetime.now(TIMEZONE))
    war_type = "Guerra"; 
    if hasattr(war, 'is_cwl') and war.is_cwl: war_type = "CWL"
    elif hasattr(war, 'type') and war.type == "friendly": war_type = "Amistosa"
    return {"status": war.state, "type": war_type, "state_description": war.state.capitalize() if war.state else "N/A",
            "clan_name": war.clan.name if war.clan else "N/A", "clan_stars": war.clan.stars if war.clan else 0,
            "clan_destruction": f"{war.clan.destruction:.2f}%" if war.clan else "0%",
            "clan_badge_url": war.clan.badge.url if war.clan and hasattr(war.clan.badge, 'url') else None,
            "opponent_name": war.opponent.name if war.opponent else "N/A", "opponent_tag": war.opponent.tag if war.opponent else "#?",
            "opponent_stars": war.opponent.stars if war.opponent else 0, "opponent_destruction": f"{war.opponent.destruction:.2f}%" if war.opponent else "0%",
            "opponent_badge_url": war.opponent.badge.url if war.opponent and hasattr(war.opponent.badge, 'url') else None,
            **td, "attacks_per_member": getattr(war, 'attacks_per_member', 'N/A'),
            "preparation_start_time_iso": war.preparation_start_time.time.isoformat() if war.preparation_start_time and hasattr(war.preparation_start_time, 'time') else None}

async def fetch_current_war_details_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado.", "war_data": None, "attacks": []}
    player_short_term_cache.clear(); war = await get_current_or_last_war(CLAN_TAG)
    if not war or (hasattr(war, 'state') and war.state == "notInWar"): return {"error": "Nenhuma guerra para detalhar.", "war_data": None, "attacks": []}
    attacks = []
    if war.attacks:
        for att in sorted(war.attacks, key=lambda a: a.order):
            try: p_att = await get_player_data(att.attacker_tag); att_n, att_th = p_att.name, p_att.town_hall
            except ValueError: att_n, att_th = att.attacker_tag, '?'
            try: p_def = await get_player_data(att.defender_tag); def_n, def_th = p_def.name, p_def.town_hall
            except ValueError: def_n, def_th = att.defender_tag, '?'
            attacks.append({"attacker_name": att_n, "attacker_townhall": att_th, "defender_name": def_n, "defender_townhall": def_th,
                            "stars": att.stars, "destruction": att.destruction, "order": att.order, "duration": getattr(att, 'duration', 'N/A')})
    td = format_war_time_details(war, datetime.datetime.now(TIMEZONE)); war_type = "Guerra"
    if hasattr(war, 'is_cwl') and war.is_cwl: war_type = "CWL"
    elif hasattr(war, 'type') and war.type == "friendly": war_type = "Amistosa"
    war_data = {"status": war.state, "type": war_type, "state_description": war.state.capitalize() if war.state else "N/A",
                "clan_name": war.clan.name if war.clan else "N/A", "clan_stars": war.clan.stars if war.clan else 0, "clan_destruction": f"{war.clan.destruction:.2f}%" if war.clan else "0%",
                "clan_badge_url": war.clan.badge.url if war.clan and hasattr(war.clan.badge, 'url') else None,
                "opponent_name": war.opponent.name if war.opponent else "N/A", "opponent_tag": war.opponent.tag if war.opponent else "#?",
                "opponent_stars": war.opponent.stars if war.opponent else 0, "opponent_destruction": f"{war.opponent.destruction:.2f}%" if war.opponent else "0%",
                "opponent_badge_url": war.opponent.badge.url if war.opponent and hasattr(war.opponent.badge, 'url') else None,
                **td, "attacks_per_member": getattr(war, 'attacks_per_member', 'N/A'), "team_size": getattr(war, 'team_size', 'N/A')}
    return {"war_data": war_data, "attacks": attacks}

async def fetch_war_attacks_remaining_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    war = await get_current_or_last_war(CLAN_TAG); clan_name = "N/A"
    if war and war.clan and war.clan.tag == CLAN_TAG: clan_name = war.clan.name
    elif war and war.opponent and war.opponent.tag == CLAN_TAG: clan_name = war.opponent.name
    if not war or war.state != "inWar": return {"message": "Não há guerra em andamento.", "members_pending": [], "clan_name": clan_name}
    pending = []; our_clan = war.clan if war.clan.tag == CLAN_TAG else war.opponent if war.opponent.tag == CLAN_TAG else None
    if not our_clan: return {"message": "Erro ao id nosso clã.", "members_pending": [], "clan_name": "Erro"}
    if our_clan.members:
        for m in our_clan.members:
            left = war.attacks_per_member - (len(m.attacks) if m.attacks else 0)
            if left > 0: pending.append({"name": m.name, "tag": m.tag, "town_hall": m.town_hall, "attacks_left": left, "map_position": m.map_position})
    pending.sort(key=lambda x: x.get("map_position", 0))
    return {"message": "Membros pendentes.", "members_pending": pending, "clan_name": our_clan.name}

async def fetch_war_log_for_web_api(limit: int = 10) -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        log_iter = await bot.coc_client.get_war_log(CLAN_TAG); entries = []; count = 0
        async for entry in log_iter:
            if count >= limit: break; res = "N/A"
            if entry.clan.tag == CLAN_TAG and entry.result: res = "Vitória" if entry.result == "win" else "Derrota" if entry.result == "lose" else "Empate"
            elif entry.opponent.tag == CLAN_TAG and entry.result: res = "Derrota" if entry.result == "win" else "Vitória" if entry.result == "lose" else "Empate"
            entries.append({"clan_name": entry.clan.name, "clan_stars": entry.clan.stars, "clan_destruction": entry.clan.destruction, "clan_badge_url": entry.clan.badge.url if hasattr(entry.clan.badge, 'url') else None,
                            "opponent_name": entry.opponent.name, "opponent_stars": entry.opponent.stars, "opponent_destruction": entry.opponent.destruction, "opponent_badge_url": entry.opponent.badge.url if hasattr(entry.opponent.badge, 'url') else None,
                            "team_size": entry.team_size, "end_time": entry.end_time.time.strftime('%d/%m/%Y %H:%M') if entry.end_time and hasattr(entry.end_time, 'time') else "N/A",
                            "result": res, "is_cwl": getattr(entry, 'is_cwl', False)})
            count +=1
        return {"log": entries}
    except coc.PrivateWarLog: return {"error": "Log de guerras privado."}
    except Exception as e: logger.error(f"Erro API log web: {e}", exc_info=True); return {"error": str(e)}

async def fetch_cwl_info_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        lg = await bot.coc_client.get_league_group(CLAN_TAG)
        if not lg or (hasattr(lg, 'state') and lg.state == "notInWar"): return {"status": "NotInCwl", "message": "Clã não em CWL."}
        rounds = []
        if lg.rounds:
            for i, tags in enumerate(lg.rounds):
                r_info: Dict[str, Any] = {"round_number": i + 1, "wars": []}; 
                if not tags: r_info["wars"].append({"message": "Rodada não definida."})
                else:
                    for tag in tags:
                        if tag=="#0": r_info["wars"].append({"message":"Bye."}); continue
                        try:
                            war = await lg.get_league_war(tag); our, opp = (war.clan, war.opponent) if war.clan.tag == CLAN_TAG else (war.opponent, war.clan)
                            td = format_war_time_details(war, datetime.datetime.now(TIMEZONE))
                            r_info["wars"].append({"war_tag":tag, "state":war.state, "clan_name":our.name, "clan_stars":our.stars, "clan_destruction":f"{our.destruction:.2f}%", "clan_badge_url":our.badge.url if hasattr(our.badge, 'url') else None,
                                                "opponent_name":opp.name, "opponent_stars":opp.stars, "opponent_destruction":f"{opp.destruction:.2f}%", "opponent_badge_url":opp.badge.url if hasattr(opp.badge, 'url') else None, **td})
                        except Exception as e_w: r_info["wars"].append({"war_tag":tag, "error":f"Erro: {e_w}"})
                rounds.append(r_info)
        clans = [{"name":c.name, "tag":c.tag, "level":c.level, "badge_url":c.badge.url if hasattr(c.badge, 'url') else None} for c in lg.clans] if lg.clans else []
        return {"status":"InCwl", "state":lg.state, "season":lg.season.strftime('%Y-%m') if hasattr(lg,'season') and lg.season else "N/A", "clans_in_group":clans, "rounds":rounds}
    except coc.NotFound: return {"status": "NotInCwl", "message": "Grupo CWL não encontrado."}
    except Exception as e: logger.error(f"Erro API CWL web: {e}", exc_info=True); return {"error":str(e)}

# --- Endpoints da API Web (Handlers) ---
async def api_clan_info_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_clan_info_{CLAN_TAG}", fetch_clan_info_for_web_api))
async def api_members_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_clan_members_{CLAN_TAG}", fetch_clan_members_for_web_api))
async def api_war_status_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_war_status_{CLAN_TAG}", fetch_war_status_for_web_api))
async def api_current_war_details_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_current_war_details_{CLAN_TAG}", fetch_current_war_details_for_web_api))
async def api_war_attacks_remaining_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_war_attacks_remaining_{CLAN_TAG}", fetch_war_attacks_remaining_for_web_api))
async def api_war_log_handler(request: web.Request) -> web.Response: limit = int(request.query.get("limit","10")); limit=max(1,min(limit,50)); return web.json_response(await get_cached_web_data(f"web_war_log_{CLAN_TAG}_limit{limit}",fetch_war_log_for_web_api,limit))
async def api_cwl_info_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_cwl_info_{CLAN_TAG}", fetch_cwl_info_for_web_api))

# --- Configuração do Servidor Web ---
async def handle_panel_index(request: web.Request) -> web.FileResponse | web.Response:
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "painel.html")
    try: return web.FileResponse(index_path)
    except FileNotFoundError: logger.error(f"painel.html não encontrado em {index_path}"); return web.Response(text="Painel não encontrado.", status=404)
    except Exception as e: logger.error(f"Erro ao servir painel.html: {e}"); return web.Response(text="Erro ao carregar painel.", status=500)

async def setup_web_server() -> Optional[web.AppRunner]:
    app = web.Application()
    async def health_check(request: web.Request) -> web.Response: return web.Response(text=f"Bot running! Panel active! v{BOT_VERSION}")
    app.router.add_get("/api/clan", api_clan_info_handler); app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/war", api_war_status_handler); app.router.add_get("/api/current_war_details", api_current_war_details_handler)
    app.router.add_get("/api/war_attacks_remaining", api_war_attacks_remaining_handler); app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler); app.router.add_get("/painel", handle_panel_index)
    static_path = os.path.join(os.path.dirname(__file__), "static")
    for folder in ["css", "js", "images"]:
        path = os.path.join(static_path, folder)
        if not os.path.exists(path): os.makedirs(path); logger.info(f"Pasta '{path}' criada.")
    painel_html_path = os.path.join(static_path, "painel.html") # Criação de arquivos básicos mantida
    if not os.path.exists(painel_html_path):
        with open(painel_html_path, "w", encoding='utf-8') as f: f.write("<!DOCTYPE html><html lang='pt-br'><head><meta charset='UTF-8'><title>Painel CoC</title><link rel='stylesheet' href='/static/css/style.css'></head><body><h1>Painel Carregando...</h1><script src='/static/js/scripts.js'></script></body></html>")
    style_css_path = os.path.join(static_path, "css", "style.css")
    if not os.path.exists(style_css_path):
        with open(style_css_path, "w", encoding='utf-8') as f: f.write("body { font-family: sans-serif; }")
    scripts_js_path = os.path.join(static_path, "js", "scripts.js")
    if not os.path.exists(scripts_js_path):
        with open(scripts_js_path, "w", encoding='utf-8') as f: f.write("console.log('Painel JS carregado.');")
    app.router.add_static('/static/', path=static_path, name='static', show_index=False); app.router.add_get("/", health_check)
    runner = web.AppRunner(app); await runner.setup(); port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    try: await site.start(); logger.info(f"Servidor web iniciado: 0.0.0.0:{port}"); return runner
    except Exception as e: logger.error(f"Falha ao iniciar servidor web: {e}", exc_info=True); return None
# ============================================================================ #
# ===================== FIM DAS MODIFICAÇÕES PARA PAINEL WEB ===================== #
# ============================================================================ #

async def format_attacks_remaining_embed(war: ClanWar) -> Optional[List[discord.Embed]]:
    if not all(hasattr(war, attr) for attr in ['state', 'opponent', 'clan', 'end_time', 'stars', 'destruction']):
         logger.error("format_attacks_remaining_embed: Objeto 'war' inválido.")
         return None
    our_display_clan = war.clan; opponent_display_clan = war.opponent
    if war.clan.tag != CLAN_TAG and war.opponent.tag == CLAN_TAG:
        our_display_clan, opponent_display_clan = opponent_display_clan, our_display_clan
    opponent_name = opponent_display_clan.name if opponent_display_clan else 'Oponente Desconhecido'
    opponent_tag = opponent_display_clan.tag if opponent_display_clan else '#?'
    clan_name_display = our_display_clan.name if our_display_clan else 'Clã Desconhecido'
    clan_badge_url = our_display_clan.badge.url if our_display_clan and hasattr(our_display_clan.badge, 'url') else None
    our_stars_display = our_display_clan.stars if our_display_clan else 0
    our_destruction_display = our_display_clan.destruction if our_display_clan else 0.0
    opponent_stars_display = opponent_display_clan.stars if opponent_display_clan else 0
    opponent_destruction_display = opponent_display_clan.destruction if opponent_display_clan else 0.0

    if war.state != "inWar":
        embed_msg = discord.Embed(title=f"⚔️ Guerra Não Ativa vs {opponent_name}", description=f"A guerra contra {opponent_name} ({opponent_tag}) não está em andamento (Estado: {war.state}).", color=discord.Color.orange())
        if clan_badge_url: embed_msg.set_thumbnail(url=clan_badge_url)
        embed_msg.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed_msg.timestamp = datetime.datetime.now(TIMEZONE)
        return [embed_msg]
    time_details = format_war_time_details(war, datetime.datetime.now(TIMEZONE))
    time_remaining_str_embed = time_details["time_remaining"]; end_time_local_fmt_embed = time_details["time_value"]
    members_with_attacks_list_embed = []
    attack_count_embed = getattr(war, 'attacks_per_member', 2)
    if hasattr(our_display_clan, 'members') and our_display_clan.members:
         for member_obj in our_display_clan.members:
            if not member_obj or not hasattr(member_obj, 'attacks'): continue
            attacks_used = len(member_obj.attacks) if member_obj.attacks else 0; attacks_left = attack_count_embed - attacks_used
            if attacks_left > 0: members_with_attacks_list_embed.append(f"**{getattr(member_obj, 'name', 'N/A')}** (CV{getattr(member_obj, 'town_hall', '?')}) - {attacks_left} atk{'s' if attacks_left > 1 else ''} restante{'s' if attacks_left > 1 else ''}")
    else: logger.warning(f"Lista de membros não encontrada em '{our_display_clan.name if our_display_clan else 'N/A'}' para format_attacks_remaining_embed.")
    base_embed_attacks = discord.Embed(title=f"🗡️ Ataques Restantes - {clan_name_display} vs {opponent_name}",
        description=f"**Placar:** {our_stars_display}⭐ ({our_destruction_display:.2f}%) vs {opponent_stars_display}⭐ ({opponent_destruction_display:.2f}%)\n**Fim:** {end_time_local_fmt_embed} ({time_remaining_str_embed} restantes)", color=discord.Color.blue())
    if clan_badge_url: base_embed_attacks.set_thumbnail(url=clan_badge_url)
    if not members_with_attacks_list_embed:
        final_embed = discord.Embed.from_dict(base_embed_attacks.to_dict()); final_embed.add_field(name="Membros com Ataques Pendentes", value="✅ Todos os ataques já foram utilizados!", inline=False)
        if not hasattr(final_embed, 'footer') or not final_embed.footer or not getattr(final_embed.footer, 'text', None): final_embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        if not final_embed.timestamp: final_embed.timestamp = datetime.datetime.now(TIMEZONE)
        return [final_embed]
    else:
        embeds_to_send_attacks_final = []; field_title_attacks = "Membros com Ataques Pendentes"
        current_embed_att = discord.Embed.from_dict(base_embed_attacks.to_dict()); current_field_val_att = ""
        for item in members_with_attacks_list_embed:
            line = item + "\n"
            if len(current_field_val_att) + len(line) > 1024:
                if current_field_val_att: current_embed_att.add_field(name=field_title_attacks, value=current_field_val_att, inline=False)
                if current_embed_att.fields: embeds_to_send_attacks_final.append(current_embed_att)
                current_embed_att = discord.Embed.from_dict(base_embed_attacks.to_dict()); current_field_val_att = line
                if len(current_field_val_att) > 1024: current_field_val_att=current_field_val_att[:1021]+"...\n"
            else: current_field_val_att += line
        if current_field_val_att: current_embed_att.add_field(name=field_title_attacks, value=current_field_val_att, inline=False)
        if current_embed_att.fields: embeds_to_send_attacks_final.append(current_embed_att)
        for emb in embeds_to_send_attacks_final:
            if not hasattr(emb, 'footer') or not emb.footer or not getattr(emb.footer, 'text', None): emb.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
            if not emb.timestamp: emb.timestamp = datetime.datetime.now(TIMEZONE)
        return embeds_to_send_attacks_final if embeds_to_send_attacks_final else None

async def send_missed_attacks_report(war: ClanWar, missed_members_details: List[str], war_type: str) -> None:
    if not missed_members_details: return
    if not CHANNEL_ID or CHANNEL_ID == 0: logger.warning("CHANNEL_ID não configurado (ataques perdidos)."); return
    content = None
    if ROLE_ID_MISSED_ATTACK:
        try:
            log_channel = await bot.fetch_channel(CHANNEL_ID)
            if log_channel and hasattr(log_channel, 'guild'):
                 guild = log_channel.guild
                 try: role_id_int = int(ROLE_ID_MISSED_ATTACK); role = guild.get_role(role_id_int)
                 except (ValueError, TypeError): logger.error(f"ROLE_ID_MISSED_ATTACK ('{ROLE_ID_MISSED_ATTACK}') inválido."); role = None
                 if role: content = f"{role.mention} Ataques Não Realizados!"
                 else: logger.warning(f"Cargo alerta ataques perdidos (ID: {ROLE_ID_MISSED_ATTACK}) não encontrado.")
            else: logger.warning(f"Servidor do canal de log (ID: {CHANNEL_ID}) não encontrado.")
        except discord.Forbidden: logger.error(f"Sem permissão para buscar cargos no servidor do canal {CHANNEL_ID}.")
        except Exception as e: logger.error(f"Erro ao buscar cargo para alerta de ataques perdidos: {e}", exc_info=True)
    opponent_name_report = getattr(getattr(war, 'opponent', None), 'name', 'Oponente Desconhecido')
    start_time_str, end_time_str = "N/A", "N/A"
    try:
        if hasattr(war, 'start_time') and war.start_time and hasattr(war.start_time, 'time'): start_time_str = pytz.utc.localize(war.start_time.time).astimezone(TIMEZONE).strftime('%d/%m/%Y %H:%M')
        if hasattr(war, 'end_time') and war.end_time and hasattr(war.end_time, 'time'): end_time_str = pytz.utc.localize(war.end_time.time).astimezone(TIMEZONE).strftime('%d/%m/%Y %H:%M')
    except Exception as e_time: logger.error(f"Erro ao formatar tempos para relatório de ataques perdidos: {e_time}", exc_info=True)
    description_text = (f"Membros que não usaram todos os ataques contra **{opponent_name_report}**.\n\n"
                        f"**Início da Guerra:** {start_time_str}\n"
                        f"**Fim da Guerra:** {end_time_str}")
    base_embed_missed = discord.Embed(title=f"❌ Ataques Não Realizados - {war_type}", description=description_text, color=discord.Color.red())
    if hasattr(war, 'opponent') and hasattr(war.opponent, 'badge') and war.opponent.badge: base_embed_missed.set_thumbnail(url=war.opponent.badge.url)
    try:
        channel_to_send = await bot.fetch_channel(CHANNEL_ID)
        if isinstance(channel_to_send, discord.TextChannel):
             if content: await channel_to_send.send(content)
             await send_embeds_splitted(channel_to_send, base_embed_missed, "Membros", missed_members_details)
        else: logger.error(f"Canal de log ID {CHANNEL_ID} não é canal de texto para relatório.")
    except discord.NotFound: logger.error(f"Canal de log ID {CHANNEL_ID} não encontrado para relatório.")
    except discord.Forbidden: logger.error(f"Sem permissão para enviar relatório no canal {CHANNEL_ID}.")
    except Exception as e: logger.error(f"Erro ao enviar relatório de ataques perdidos para {CHANNEL_ID}: {e}", exc_info=True)

async def send_online_status():
    if not CHANNEL_ID or CHANNEL_ID == 0: logger.warning("CHANNEL_ID não configurado (status online)."); return
    try:
        clan_name_online = "Clã Desconhecido"; clan_tag_fmt_online = CLAN_TAG or "Nenhum"
        if CLAN_TAG and hasattr(bot, 'coc_client') and bot.coc_client.http:
             try: clan_data = await bot.coc_client.get_clan(CLAN_TAG); clan_name_online = clan_data.name; clan_tag_fmt_online = clan_data.tag
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
    @coc_client.event # CORRIGIDO
    @coc.ClanEvents.member_join(tags=[CLAN_TAG])
    async def on_member_join(old_member: Optional[ClanMember], member: ClanMember):
        if not member or not hasattr(member, 'clan'): logger.warning("Evento member_join com 'member' inválido."); return
        clan = member.clan
        logger.info(f"Evento: {member.name} ({member.tag}) entrou em {clan.name}.")
        embed = discord.Embed(title="👋 Novo Membro", description=f"**{member.name}** (`{member.tag}`) entrou no clã!", color=discord.Color.green())
        embed.add_field(name="CV", value=getattr(member, 'town_hall', '?'), inline=True); embed.add_field(name="Nível", value=getattr(member, 'exp_level', '?'), inline=True)
        embed.add_field(name="Troféus", value=getattr(member, 'trophies', '?'), inline=True)
        if hasattr(member, 'league') and member.league: embed.add_field(name="Liga", value=member.league.name, inline=True)
        if hasattr(clan, 'badge') and clan.badge: embed.set_author(name=clan.name, icon_url=clan.badge.url); embed.set_thumbnail(url=clan.badge.url)
        await send_log_embed(embed)
    @coc_client.event # CORRIGIDO
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
    @coc_client.event # CORRIGIDO
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
    @coc_client.event # CORRIGIDO
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
    @coc_client.event # CORRIGIDO
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
    @coc_client.event # CORRIGIDO
    @coc.ClanEvents.member_league_change(tags=[CLAN_TAG])
    async def on_member_league_change(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan'): return
        old_league_name = old_member.league.name if old_member.league else "Sem Liga"; new_league_name = member.league.name if member.league else "Sem Liga"
        if old_league_name == new_league_name: return
        logger.info(f"Evento: Liga de {member.name} mudou de {old_league_name} para {new_league_name} em {member.clan.name}.")
        embed = discord.Embed(title="🏆 Mudança de Liga", description=f"Liga de **{member.name}** (`{member.tag}`) alterada!", color=discord.Color.purple())
        embed.add_field(name="Liga Anterior", value=old_league_name, inline=True); embed.add_field(name="Nova Liga", value=new_league_name, inline=True)
        if hasattr(member.clan, 'badge') and member.clan.badge: embed.set_author(name=member.clan.name, icon_url=member.clan.badge.url); embed.set_thumbnail(url=member.clan.badge.url)
        await send_log_embed(embed)
    @coc_client.event # CORRIGIDO
    @coc.ClanEvents.member_trophies_change(tags=[CLAN_TAG])
    async def on_member_trophies_change(old_member: ClanMember, member: ClanMember):
        if not member or not old_member: logger.warning("Evento member_trophies_change com member/old_member inválido."); return
        trophy_difference = member.trophies - old_member.trophies
        if abs(trophy_difference) < 5: return
        logger.info(f"Evento: Troféus de {member.name} mudaram em {trophy_difference} (Total: {member.trophies}).")
        direction = "ganhou" if trophy_difference > 0 else "perdeu"
        embed = discord.Embed(description=f"**{member.name}** {direction} **{abs(trophy_difference)}** troféus (Total: {member.trophies})", color=discord.Color.green() if trophy_difference > 0 else discord.Color.dark_red())
        await send_log_embed(embed)
    @coc_client.event # CORRIGIDO
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
        att_name = attacker.name if attacker else attack.attacker_tag; att_th = attacker.town_hall if attacker else '?'
        def_name = defender.name if defender else attack.defender_tag; def_th = defender.town_hall if defender else '?'
        stars_str = "⭐" * attack.stars + "⚫" * (3 - attack.stars); content_msg = None
        our_war_clan_obj = war.clan if war.clan.tag == CLAN_TAG else war.opponent if war.opponent.tag == CLAN_TAG else None
        enemy_war_clan_obj = war.opponent if war.clan.tag == CLAN_TAG else war.clan if war.opponent.tag == CLAN_TAG else None
        if is_our_attack:
            logger.info(f"Evento Guerra: {att_name} atacou {def_name} - {attack.stars}*, {attack.destruction}%.")
            embed = discord.Embed(title=f"⚔️ Ataque Realizado (Guerra)", description=f"**{att_name}** (CV{att_th}) atacou **{def_name}** (CV{def_th})", color=discord.Color.blue())
            embed.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
            if attack.stars <= 1 and ROLE_ID_1STAR_ALERT:
                try:
                    log_ch = await bot.fetch_channel(CHANNEL_ID)
                    if log_ch and hasattr(log_ch, 'guild'):
                        role = log_ch.guild.get_role(int(ROLE_ID_1STAR_ALERT))
                        if role: content_msg = f"{role.mention} ⚠️ Ataque fora do padrão!"
                except Exception as e_alert: logger.error(f"Erro alerta 1 estrela: {e_alert}")
            if our_war_clan_obj and hasattr(our_war_clan_obj, 'badge') and our_war_clan_obj.badge:
                 embed.set_author(name=our_war_clan_obj.name, icon_url=our_war_clan_obj.badge.url); embed.set_thumbnail(url=our_war_clan_obj.badge.url)
            await send_log_embed(embed, content_msg)
        elif is_our_defense:
            logger.info(f"Evento Guerra: {def_name} foi atacado por {att_name} - {attack.stars}*, {attack.destruction}%.")
            embed = discord.Embed(title=f"🛡️ Defesa Recebida (Guerra)", description=f"**{def_name}** (CV{def_th}) foi atacado por **{att_name}** (CV{att_th})", color=discord.Color.orange())
            embed.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
            if enemy_war_clan_obj and hasattr(enemy_war_clan_obj, 'badge') and enemy_war_clan_obj.badge:
                 embed.set_author(name=enemy_war_clan_obj.name, icon_url=enemy_war_clan_obj.badge.url); embed.set_thumbnail(url=enemy_war_clan_obj.badge.url)
            await send_log_embed(embed)
    logger.info("Manipuladores de eventos CoC registrados.")

@tasks.loop(minutes=10)
async def check_war_end_report_task():
    if not bot.coc_client or not bot.coc_client.http: logger.debug("check_war_end_report_task: CoC Client não pronto."); return
    logger.debug("check_war_end_report_task: Iniciando verificação..."); processed_ids_cycle: Set[str] = set()
    async def process_war_for_report(war: ClanWar, war_type: str):
        war_id = war.tag if hasattr(war, 'tag') and war.tag and war.tag != "#0" else f"REG-{war.opponent.tag if war.opponent else 'NA'}-{war.end_time.raw_time if war.end_time else 'NA'}"
        if not war_id or war_id in processed_ids_cycle: return
        if war.state == "warEnded" and war_id not in reported_war_ends:
            our_clan = war.clan if war.clan and war.clan.tag == CLAN_TAG else war.opponent if war.opponent and war.opponent.tag == CLAN_TAG else None
            if not our_clan: logger.error(f"check_war_end_report_task: Nosso clã não encontrado na guerra {war_id}."); processed_ids_cycle.add(war_id); return
            missed = []
            if our_clan.members:
                for m in our_clan.members:
                    left = war.attacks_per_member - (len(m.attacks) if m.attacks else 0)
                    if left > 0: missed.append(f"**{m.name}** (CV{m.town_hall}): {left} perdido{'s' if left > 1 else ''}")
            if missed: await send_missed_attacks_report(war, missed, war_type); logger.info(f"Relatório de ataques perdidos enviado para {war_type} ID: {war_id}")
            else: logger.info(f"check_war_end_report_task: Nenhum ataque perdido em {war_type} (ID: {war_id}).")
            reported_war_ends.add(war_id)
        processed_ids_cycle.add(war_id)
    try: 
        reg_war = await bot.coc_client.get_current_war(CLAN_TAG)
        if reg_war and reg_war.state != "notInWar" and hasattr(reg_war, 'end_time'): await process_war_for_report(reg_war, "Guerra Normal")
    except Exception as e: logger.error(f"check_war_end_report_task: Erro guerra regular: {e}", exc_info=True)
    try: 
        lg = await bot.coc_client.get_league_group(CLAN_TAG)
        if lg and lg.state != "notInWar" and lg.rounds:
            for i, rd_tags in enumerate(lg.rounds):
                for tag_val in rd_tags: # Renomeado para evitar conflito com a função tag
                    if tag_val == "#0": continue
                    try: cwl_war = await lg.get_league_war(tag_val)
                    except coc.NotFound: continue
                    if cwl_war and (cwl_war.clan.tag == CLAN_TAG or cwl_war.opponent.tag == CLAN_TAG) and hasattr(cwl_war, 'end_time'):
                        await process_war_for_report(cwl_war, f"Liga (Rodada {i+1})")
    except Exception as e: logger.error(f"check_war_end_report_task: Erro CWL: {e}", exc_info=True)
    logger.debug("check_war_end_report_task: Verificação concluída.")

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
    current_war_cmd: Optional[ClanWar] = None
    try:
        league_group_cmd = await bot.coc_client.get_league_group(CLAN_TAG)
        if league_group_cmd and getattr(league_group_cmd,'state',None) != "notInWar" and hasattr(league_group_cmd, 'rounds'):
            if hasattr(league_group_cmd, 'current_wars') and league_group_cmd.current_wars:
                for war_tag_obj in reversed(league_group_cmd.current_wars):
                    try:
                        league_war_cmd_obj = await league_group_cmd.get_league_war(war_tag_obj.tag)
                        if league_war_cmd_obj and (league_war_cmd_obj.clan.tag == CLAN_TAG or league_war_cmd_obj.opponent.tag == CLAN_TAG) and league_war_cmd_obj.state == "inWar":
                            current_war_cmd = league_war_cmd_obj; break
                    except (coc.NotFound, Exception): continue
                if current_war_cmd and current_war_cmd.opponent.tag == CLAN_TAG : current_war_cmd.clan, current_war_cmd.opponent = current_war_cmd.opponent, current_war_cmd.clan
            else: 
                for _round_num_cmd, war_tags_cmd in enumerate(league_group_cmd.rounds):
                    if current_war_cmd: break
                    for war_tag_cmd in war_tags_cmd:
                        if war_tag_cmd == "#0": continue
                        try:
                             league_war_cmd_obj = await league_group_cmd.get_league_war(war_tag_cmd)
                             if league_war_cmd_obj and (league_war_cmd_obj.clan.tag == CLAN_TAG or league_war_cmd_obj.opponent.tag == CLAN_TAG) and league_war_cmd_obj.state == "inWar":
                                 current_war_cmd = league_war_cmd_obj; break
                        except (coc.NotFound, Exception): continue
                    if current_war_cmd and current_war_cmd.opponent.tag == CLAN_TAG : current_war_cmd.clan, current_war_cmd.opponent = current_war_cmd.opponent, current_war_cmd.clan
    except coc.NotFound: logger.info("/ataques: Clã não encontrado ao buscar grupo de liga.")
    except Exception as e: logger.error(f"Erro ao buscar grupo de liga (CWL) em /ataques: {e}", exc_info=True)
    if not current_war_cmd:
         try:
             regular_war_cmd = await bot.coc_client.get_current_war(CLAN_TAG)
             if regular_war_cmd and getattr(regular_war_cmd, 'state', None) == "inWar": current_war_cmd = regular_war_cmd
         except coc.PrivateWarLog: await interaction.followup.send("Log de guerra regular é privado.", ephemeral=True); return
         except coc.NotFound: logger.info("/ataques: Clã não encontrado ao buscar guerra regular.")
         except Exception as e: logger.error(f"Erro ao buscar guerra regular em /ataques: {e}", exc_info=True); await interaction.followup.send("Erro ao buscar guerra regular.", ephemeral=True); return
    if current_war_cmd and isinstance(current_war_cmd, coc.ClanWar):
        embeds_list_cmd = await format_attacks_remaining_embed(current_war_cmd)
        if embeds_list_cmd:
            first_embed_cmd = embeds_list_cmd.pop(0); await interaction.followup.send(embed=first_embed_cmd)
            for embed_item_cmd in embeds_list_cmd:
                try:
                    if interaction.channel and isinstance(interaction.channel, discord.abc.Messageable): await interaction.channel.send(embed=embed_item_cmd)
                    else: logger.warning("interaction.channel não acessível para embeds adicionais."); break
                except Exception as e: logger.error(f"Erro ao enviar embed adicional de /ataques: {e}"); break
        else: await interaction.followup.send(f"Erro ao formatar informações de ataques.", ephemeral=True)
    elif current_war_cmd: logger.error(f"Objeto 'current_war_cmd' inválido ({type(current_war_cmd)}) para format_attacks_remaining_embed."); await interaction.followup.send(f"Erro interno.", ephemeral=True)
    else: await interaction.followup.send("O clã não está em nenhuma guerra ativa (Normal ou Liga) no momento.")

@war_group.command(name="status", description="Exibe o status da guerra atual (Normal ou Liga)") # Mantido do seu código original
async def war_status(interaction: discord.Interaction):
    # ... (Cole aqui a implementação completa do seu comando /guerra status)
    await interaction.response.defer() # ... (resto da lógica)

@info_group.command(name="clan", description="Exibe informações sobre um clã") # Mantido do seu código original
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def clan_info(interaction: discord.Interaction, tag: Optional[str] = None):
    # ... (Cole aqui a implementação completa do seu comando /info clan)
    await interaction.response.defer() # ... (resto da lógica)

@info_group.command(name="jogador", description="Exibe informações sobre um jogador") # Ajustado para usar get_player_data
@app_commands.describe(tag="Tag do jogador (Ex: #P0LGYC9YQ)")
async def player_info(interaction: discord.Interaction, tag: str):
    try:
        await interaction.response.defer()
        player_data_info = await get_player_data(tag)
        embed_player_info = discord.Embed(title=f"{player_data_info.name} ({player_data_info.tag})", color=discord.Color.green())
        if hasattr(player_data_info, 'league') and player_data_info.league and hasattr(player_data_info.league.icon, 'url'): embed_player_info.set_thumbnail(url=player_data_info.league.icon.url)
        basic_info = [f"**CV:** {getattr(player_data_info, 'town_hall', '?')}", f"**Nível:** {getattr(player_data_info, 'exp_level', '?')}",
                      f"**Liga:** {getattr(player_data_info.league, 'name', 'S/L') if player_data_info.league else 'S/L'}",
                      f"**Troféus:** {getattr(player_data_info, 'trophies', '?')}🏆", f"**Recorde:** {getattr(player_data_info, 'best_trophies', '?')}🏆"]
        embed_player_info.add_field(name="Info Básicas", value="\n".join(basic_info), inline=True)
        clan_info_p = ["**Clã:** Sem Clã"]
        if hasattr(player_data_info, 'clan') and player_data_info.clan:
            clan_info_p = [f"**Clã:** {player_data_info.clan.name}", f"**Nível Clã:** {player_data_info.clan.level}",
                           f"**Cargo:** {player_data_info.role.name.capitalize() if player_data_info.role else 'Membro'}"]
        embed_player_info.add_field(name="Clã", value="\n".join(clan_info_p), inline=True)
        stats = [f"**Estrelas Guerra:** {player_data_info.war_stars}⭐" if hasattr(player_data_info, "war_stars") else "",
                 f"**Ataques Vencidos:** {player_data_info.attack_wins}" if hasattr(player_data_info, "attack_wins") else "",
                 # ... (mais estatísticas como no seu original)
                ]
        stats = [s for s in stats if s] # Remove strings vazias
        if stats: embed_player_info.add_field(name="Estatísticas", value="\n".join(stats[:4]), inline=True if len(stats)>4 else False) # Limita a 4 para inline
        if len(stats) > 4 : embed_player_info.add_field(name="Estatísticas (cont.)", value="\n".join(stats[4:]), inline=True)
        # ... (lógica de heróis)
        embed_player_info.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed_player_info.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed_player_info)
    except ValueError as e_val: await interaction.followup.send(str(e_val), ephemeral=True)
    except Exception as e_gen: logger.error(f"Erro info jogador {tag}: {e_gen}", exc_info=True); await interaction.followup.send("Erro ao buscar info do jogador.", ephemeral=True)

@info_group.command(name="membros", description="Lista os membros do clã") # Mantido do seu código original
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def clan_members(interaction: discord.Interaction, tag: Optional[str] = None):
    # ... (Cole aqui a implementação completa do seu comando /info membros)
    await interaction.response.defer() # ... (resto da lógica)

@search_group.command(name="clan", description="Busca clãs por nome") # Mantido do seu código original
@app_commands.describe(nome="Nome (ou parte) do clã", min_membros="Mínimo de membros", max_membros="Máximo de membros", min_nivel="Nível mínimo", localizacao="Nome da localização (ex: Brazil)")
async def search_clan(interaction: discord.Interaction, nome: str, min_membros: Optional[app_commands.Range[int, 1, 50]] = None, max_membros: Optional[app_commands.Range[int, 1, 50]] = None, min_nivel: Optional[app_commands.Range[int, 1, None]] = None, localizacao: Optional[str] = None):
    # ... (Cole aqui a implementação completa do seu comando /buscar clan)
    await interaction.response.defer() # ... (resto da lógica)

@search_group.command(name="jogador", description="Busca jogadores por nome") # Mantido do seu código original
@app_commands.describe(nome="Nome (ou parte) do jogador")
async def search_player(interaction: discord.Interaction, nome: str):
    # ... (Cole aqui a implementação completa do seu comando /buscar jogador)
    await interaction.response.defer() # ... (resto da lógica)

@rank_group.command(name="doacoes", description="Exibe o ranking de doações do clã") # Mantido do seu código original
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def donations_rank(interaction: discord.Interaction, tag: Optional[str] = None):
    # ... (Cole aqui a implementação completa do seu comando /rank doacoes)
    await interaction.response.defer() # ... (resto da lógica)

@rank_group.command(name="trofeus", description="Exibe o ranking de troféus do clã") # Mantido do seu código original
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def trophies_rank(interaction: discord.Interaction, tag: Optional[str] = None):
    # ... (Cole aqui a implementação completa do seu comando /rank trofeus)
    await interaction.response.defer() # ... (resto da lógica)

@rank_group.command(name="cv", description="Exibe o ranking de Casa de Vila do clã") # Mantido do seu código original
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def th_rank(interaction: discord.Interaction, tag: Optional[str] = None):
    # ... (Cole aqui a implementação completa do seu comando /rank cv)
    await interaction.response.defer() # ... (resto da lógica)


# --- Setup Hook ---
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
        if TEST_GUILD_ID:
            try: guild_obj = discord.Object(id=int(TEST_GUILD_ID)); bot.tree.copy_global_to(guild=guild_obj); synced_cmds = await bot.tree.sync(guild=guild_obj)
            except (ValueError, TypeError): logger.error(f"TEST_GUILD_ID ('{TEST_GUILD_ID}') inválido. Sincronizando globalmente..."); synced_cmds = await bot.tree.sync()
        else: synced_cmds = await bot.tree.sync()
        logger.info(f"{len(synced_cmds)} comandos (/) sincronizados.")
        if not synced_cmds and bot.tree.get_commands(): logger.warning("Nenhum comando sincronizado, mas a tree possui comandos.")
    except Exception as e: logger.error(f"Erro ao sincronizar comandos (/): {e}", exc_info=True)
    logger.info("setup_hook concluído.")

# --- Main e Bloco if __name__ ---
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
            if hasattr(bot, "web_runner") and bot.web_runner: await bot.web_runner.cleanup(); logger.info("Servidor web limpo.")
            if hasattr(bot, "coc_client") and bot.coc_client.http and not bot.coc_client.http.closed : await bot.coc_client.close(); logger.info("Cliente CoC fechado.")
            logger.info("Desligamento do bot concluído.")

def handle_asyncio_exception(loop: asyncio.AbstractEventLoop, context: Dict[str, Any]):
    msg = context.get("exception", context["message"])
    logger.error(f"Erro asyncio não tratado: {msg}", exc_info=context.get('exception'))

if __name__ == "__main__":
    required = ["DISCORD_TOKEN", "COC_EMAIL", "COC_PASSWORD", "CLAN_TAG", "CHANNEL_ID"]
    if any(not os.getenv(v) for v in required): logger.critical(f"Variáveis env faltando: {[v for v in required if not os.getenv(v)]}. Verifique .env."); exit(1)
    loop = asyncio.get_event_loop()
    try:
        loop.set_exception_handler(handle_asyncio_exception)
        loop.run_until_complete(main())
    except KeyboardInterrupt: logger.info("Bot interrompido.")
    except RuntimeError as e_loop: 
        if "Event loop is closed" in str(e_loop): logger.info("Loop de eventos fechado durante desligamento (normal).")
        else: logger.warning(f"RuntimeError no loop: {e_loop}", exc_info=True)
    except Exception as e_fatal: logger.critical(f"Erro fatal: {e_fatal}", exc_info=True)
    finally:
        if loop.is_running(): loop.stop()
        if not loop.is_closed():
            tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not asyncio.current_task(loop=loop)]
            if tasks: logger.info(f"Cancelando {len(tasks)} tarefas pendentes..."); [task.cancel() for task in tasks]; loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            loop.close()
        logger.info("Programa finalizado.")
