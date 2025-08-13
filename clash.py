# -*- coding: utf-8 -*-
# Versão 19.8.21-DB-R-FIX2 - Corrige o registo de eventos com decoradores.

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
import motor.motor_asyncio

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

# Bloco de importação para compatibilidade com versões do coc.py
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

# Carrega variáveis de ambiente do arquivo .env
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

# --- CONFIGURAÇÕES GLOBAIS DO BOT ---
BOT_VERSION = "19.8.21-DB-R-FIX2"
reported_war_ends: Set[str] = set()
intents = discord.Intents.default()
intents.message_content = True; intents.members = True; intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)
coc_client = coc.EventsClient() # <<-- MUDANÇA 1: Cliente CoC criado aqui
player_short_term_cache: Dict[str, Player] = {}
clan_cache: Dict[str, Dict[str, Any]] = {}
WEB_API_CACHE_DURATION_SECONDS = 45
CACHE_DURATION_SECONDS = 300
web_api_cache: Dict[str, Dict[str, Any]] = {}

# --- FUNÇÕES DE BUSCA DE DADOS (API CoC) ---
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

# --- FUNÇÃO CENTRAL DE LOGS NO DISCORD ---
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

# --- FUNÇÕES DE LÓGICA DE GUERRA ---
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
    current_war_in_war: Optional[ClanWar] = None
    current_war_preparation: Optional[ClanWar] = None
    best_ended_cwl_war: Optional[ClanWar] = None
    try:
        if LeagueGroup:
            league_group = await bot.coc_client.get_league_group(clan_tag_param)
            if league_group and getattr(league_group, 'state', None) != "notInWar" and hasattr(league_group, 'rounds'):
                all_round_war_tags = [tag for round_tags in league_group.rounds for tag in round_tags if tag != "#0"]
                if hasattr(league_group, 'current_wars') and league_group.current_wars:
                    for war_tag_obj in reversed(league_group.current_wars):
                        try:
                            lg_war = await bot.coc_client.get_league_war(war_tag_obj.tag)
                            if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param):
                                if lg_war.state == "inWar":
                                    current_war_in_war = lg_war
                                    if lg_war.opponent.tag == clan_tag_param: current_war_in_war.clan, current_war_in_war.opponent = current_war_in_war.opponent, current_war_in_war.clan
                                    return current_war_in_war
                                elif lg_war.state == "preparation" and not current_war_preparation:
                                    current_war_preparation = lg_war
                                    if lg_war.opponent.tag == clan_tag_param: current_war_preparation.clan, current_war_preparation.opponent = current_war_preparation.opponent, current_war_preparation.clan
                        except (coc.NotFound, AttributeError) as e: logger.debug(f"Erro ao buscar guerra CWL {war_tag_obj.tag}: {e}")
                if not current_war_in_war:
                    for war_tag_str in reversed(all_round_war_tags):
                        try:
                            lg_war = await bot.coc_client.get_league_war(war_tag_str)
                            if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param):
                                if lg_war.state == "inWar":
                                    current_war_in_war = lg_war
                                    if lg_war.opponent.tag == clan_tag_param: current_war_in_war.clan, current_war_in_war.opponent = current_war_in_war.opponent, current_war_in_war.clan
                                    return current_war_in_war
                                elif lg_war.state == "preparation" and not current_war_preparation:
                                    current_war_preparation = lg_war
                                    if lg_war.opponent.tag == clan_tag_param: current_war_preparation.clan, current_war_preparation.opponent = current_war_preparation.opponent, current_war_preparation.clan
                                elif lg_war.state == "warEnded":
                                    if not best_ended_cwl_war or (hasattr(lg_war, 'end_time') and hasattr(best_ended_cwl_war, 'end_time') and lg_war.end_time and best_ended_cwl_war.end_time and lg_war.end_time.time > best_ended_cwl_war.end_time.time):
                                        best_ended_cwl_war = lg_war
                        except (coc.NotFound, AttributeError) as e: logger.debug(f"Erro ao buscar guerra CWL {war_tag_str}: {e}")
                if current_war_preparation: return current_war_preparation
                if best_ended_cwl_war:
                    if best_ended_cwl_war.opponent.tag == clan_tag_param: best_ended_cwl_war.clan, best_ended_cwl_war.opponent = best_ended_cwl_war.opponent, best_ended_cwl_war.clan
                    return best_ended_cwl_war
    except coc.NotFound:
        logger.debug(f"Nenhum grupo CWL encontrado para o clã {clan_tag_param}.")
    except Exception as e_cwl:
        logger.error(f"Erro ao buscar dados da guerra CWL: {e_cwl}", exc_info=True)
    try:
        regular_war = await bot.coc_client.get_current_war(clan_tag_param)
        if regular_war and regular_war.state != "notInWar":
            return regular_war
    except coc.PrivateWarLog:
        logger.warning(f"Log de guerra regular do clã {clan_tag_param} é privado.")
    except Exception as e_reg:
        logger.error(f"Erro ao buscar dados da guerra regular: {e_reg}", exc_info=True)
    return None

# --- FUNÇÕES PARA O PAINEL WEB (API) ---
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
        elif not CapitalDistrict: districts = [{"name": "Distritos Indisponíveis", "level": ""}]
        else: districts = [{"name": "Nenhum distrito.", "level": ""}]
        
        return {"name": clan.name, "tag": clan.tag, "level": clan.level, "points": clan.points, "capital_points": getattr(clan, 'capital_points', 0), "member_count": clan.member_count,
                "description": clan.description, "war_wins": getattr(clan, 'war_wins', 'N/A'), "location": clan.location.name if hasattr(clan, 'location') and clan.location else "N/A",
                "type": clan.type.capitalize() if hasattr(clan, 'type') else "N/A", "badge_url": clan.badge.url if hasattr(clan, 'badge') and clan.badge else None,
                "version": BOT_VERSION, "capital_districts": districts, "capital_league": clan.capital_league.name if hasattr(clan, 'capital_league') and clan.capital_league else "N/A"}
    except Exception as e:
        logger.error(f"Erro ao buscar informações do clã para API web: {e}", exc_info=True)
        return {"error": str(e), "name": "Erro ao carregar dados do clã"}

async def fetch_clan_members_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        members_data = []
        player_notes = {}
        if bot.db is not None and hasattr(clan, 'members') and clan.members:
            member_tags = [m.tag for m in clan.members]
            notes_cursor = bot.db.players.find({"_id": {"$in": member_tags}}, {"_id": 1, "notes": 1})
            async for doc in notes_cursor:
                player_notes[doc["_id"]] = doc.get("notes", {"text": "", "priority": "none"})
        if hasattr(clan, 'members') and clan.members:
            for m in clan.members:
                note_info = player_notes.get(m.tag, {"text": "", "priority": "none"})
                members_data.append({"name": m.name, "tag": m.tag, "town_hall": m.town_hall, "exp_level": m.exp_level,
                                     "league": m.league.name if hasattr(m, 'league') and m.league else "N/A", "trophies": m.trophies,
                                     "role": m.role.name.capitalize() if hasattr(m, 'role') and m.role else "Membro", "donations": m.donations,
                                     "received": m.received, "note": note_info.get("text", ""), "note_priority": note_info.get("priority", "none")})
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
    return {"tag": member.tag, "name": member.name, "townhall": member.town_hall, "map_position": member.map_position, "attacks_used": len(member.attacks) if member.attacks else 0,
            "attacks_remaining": war_obj_ref.attacks_per_member - (len(member.attacks) if member.attacks else 0), "attacks_made": member_attacks_data,
            "defenses_received": member_defenses_data, "best_opponent_attack": {"stars": member.best_opponent_attack.stars, "attacker_tag": member.best_opponent_attack.attacker_tag} if member.best_opponent_attack else None}

async def fetch_current_war_details_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado.", "war_data": None}
    player_short_term_cache.clear()
    try:
        war = await get_current_or_last_war(CLAN_TAG)
        if not war or getattr(war, 'state', "notInWar") == "notInWar":
            return {"error": "Nenhuma guerra para detalhar.", "war_data": None}
        our_clan_obj, opp_clan_obj = (war.clan, war.opponent) if war.clan.tag == CLAN_TAG else (war.opponent, war.clan)
        time_details_coc = format_war_time_details(war, datetime.datetime.now(TIMEZONE))
        our_clan_members_in_war, opponent_clan_members_in_war, all_attacks = [], [], []
        if our_clan_obj and hasattr(our_clan_obj, 'members') and our_clan_obj.members:
            our_clan_members_in_war = sorted([await get_member_war_details_async(m, war) for m in our_clan_obj.members], key=lambda m: m["map_position"])
        if opp_clan_obj and hasattr(opp_clan_obj, 'members') and opp_clan_obj.members:
            opponent_clan_members_in_war = sorted([await get_member_war_details_async(m, war) for m in opp_clan_obj.members], key=lambda m: m["map_position"])
        if war.attacks:
            for attack in sorted(war.attacks, key=lambda a: a.order):
                try: p_att = await get_player_data(attack.attacker_tag); att_name, att_th = p_att.name, p_att.town_hall
                except ValueError: att_name, att_th = attack.attacker_tag, '?'
                try: p_def = await get_player_data(attack.defender_tag); def_name, def_th = p_def.name, p_def.town_hall
                except ValueError: def_name, def_th = attack.defender_tag, '?'
                all_attacks.append({"order": attack.order, "attacker_tag": attack.attacker_tag, "attacker_name": att_name, "attacker_townhall": att_th, "defender_tag": attack.defender_tag,
                                     "defender_name": def_name, "defender_townhall": def_th, "stars": attack.stars, "destruction": attack.destruction, "duration": getattr(attack, 'duration', 'N/A')})
        clan_star_dist, opp_star_dist = {i: 0 for i in range(4)}, {i: 0 for i in range(4)}
        c_total_dur, c_atk_count, o_total_dur, o_atk_count = 0.0, 0, 0.0, 0
        for att_det in all_attacks:
            if any(m_w["tag"] == att_det["attacker_tag"] for m_w in our_clan_members_in_war):
                clan_star_dist[att_det["stars"]] += 1; c_atk_count += 1
                if isinstance(att_det["duration"], (int, float)): c_total_dur += att_det["duration"]
            else:
                opp_star_dist[att_det["stars"]] += 1; o_atk_count += 1
                if isinstance(att_det["duration"], (int, float)): o_total_dur += att_det["duration"]
        war_data = {"status": str(war.state), "type": "CWL" if hasattr(war, 'is_cwl') and war.is_cwl else "Guerra", "state_description": str(war.state).capitalize(),
                    "clan_name": our_clan_obj.name, "clan_tag": our_clan_obj.tag, "clan_stars": our_clan_obj.stars, "clan_destruction": f"{our_clan_obj.destruction:.2f}%",
                    "clan_badge_url": our_clan_obj.badge.url, "clan_attacks_used": our_clan_obj.attacks_used, "opponent_name": opp_clan_obj.name,
                    "opponent_tag": opp_clan_obj.tag, "opponent_stars": opp_clan_obj.stars, "opponent_destruction": f"{opp_clan_obj.destruction:.2f}%",
                    "opponent_badge_url": opp_clan_obj.badge.url, "opponent_attacks_used": opp_clan_obj.attacks_used, **time_details_coc,
                    "attacks_per_member": war.attacks_per_member, "team_size": war.team_size, "clan_star_distribution": clan_star_dist, "opponent_star_distribution": opp_star_dist,
                    "clan_avg_stars": f"{our_clan_obj.stars/c_atk_count:.2f}" if c_atk_count > 0 else "0.00", "opponent_avg_stars": f"{opp_clan_obj.stars/o_atk_count:.2f}" if o_atk_count > 0 else "0.00",
                    "clan_avg_duration": f"{c_total_dur/c_atk_count:.1f}s" if c_atk_count > 0 else "0s", "opponent_avg_duration": f"{o_total_dur/o_atk_count:.1f}s" if o_atk_count > 0 else "0s"}
        return {"war_data": war_data, "all_attacks": all_attacks, "our_clan_members_in_war": our_clan_members_in_war, "opponent_clan_members_in_war": opponent_clan_members_in_war}
    except Exception as e:
        logger.error(f"Erro ao processar detalhes da guerra: {e}", exc_info=True)
        return {"error": f"Erro ao buscar detalhes da guerra: {e}", "war_data": None}

async def fetch_war_attacks_remaining_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    war = await get_current_or_last_war(CLAN_TAG)
    if not war or war.state not in ["inWar", "preparation"]:
        return {"message": "Não há guerra em andamento ou em preparação.", "members_pending": []}
    our_clan_obj_rem = war.clan if war.clan.tag == CLAN_TAG else war.opponent
    pending = []
    if hasattr(our_clan_obj_rem, 'members') and our_clan_obj_rem.members:
        for m in our_clan_obj_rem.members:
            attacks_left = war.attacks_per_member - (len(m.attacks) if m.attacks and war.state == "inWar" else 0)
            if attacks_left > 0: pending.append({"name": m.name, "tag": m.tag, "town_hall": m.town_hall, "attacks_left": attacks_left, "map_position": m.map_position})
    return {"message": "Membros com ataques pendentes:", "members_pending": sorted(pending, key=lambda x: x.get("map_position", 0)), "clan_name": our_clan_obj_rem.name}

async def fetch_war_log_for_web_api(limit: int = 10) -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    if not WarLogEntry: return {"error": "Histórico de Guerras indisponível.", "log": []}
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
                "clan_name": entry.clan.name if entry.clan else "Clã Desconhecido",
                "clan_stars": entry.clan.stars if entry.clan else 0,
                "clan_destruction": entry.clan.destruction if entry.clan else 0.0,
                "clan_badge_url": entry.clan.badge.url if entry.clan and hasattr(entry.clan.badge, 'url') else None,
                "opponent_name": entry.opponent.name if entry.opponent else "Clã Deletado",
                "opponent_stars": entry.opponent.stars if entry.opponent else 0,
                "opponent_destruction": entry.opponent.destruction if entry.opponent else 0.0,
                "opponent_badge_url": entry.opponent.badge.url if entry.opponent and hasattr(entry.opponent.badge, 'url') else None,
                "team_size": entry.team_size,
                "end_time": entry.end_time.time.astimezone(TIMEZONE).strftime('%d/%m/%y %H:%M') if entry.end_time and hasattr(entry.end_time, 'time') else "N/A",
                "result": res,
                "is_cwl": getattr(entry, 'is_league_entry', False) or getattr(entry, 'is_cwl', False)
            })
        return {"log": entries}
    except coc.PrivateWarLog: return {"error": "Log de guerras do clã é privado."}
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de guerras: {e}", exc_info=True)
        return {"error": str(e), "log": []}

async def fetch_cwl_info_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    if not LeagueGroup: return {"status": "CwlFeatureDisabled", "message": "Funcionalidade de CWL indisponível."}
    try:
        lg = await bot.coc_client.get_league_group(CLAN_TAG)
        if not lg or lg.state == "notInWar": return {"status": "NotInCwl", "message": "Clã não está em CWL."}
        rounds_data = []
        for i, round_tags in enumerate(lg.rounds):
            r_info = {"round_number": i + 1, "wars": []}
            for war_tag_val in round_tags:
                if war_tag_val == "#0": r_info["wars"].append({"message":"Rodada de descanso."}); continue
                try:
                    war = await bot.coc_client.get_league_war(war_tag_val)
                    our, opp = (war.clan, war.opponent) if war.clan.tag == CLAN_TAG else (war.opponent, war.clan)
                    td = format_war_time_details(war, datetime.datetime.now(TIMEZONE))
                    r_info["wars"].append({"war_tag": war_tag_val, "state": str(war.state), "clan_name": our.name, "clan_stars": our.stars, "clan_destruction":f"{our.destruction:.2f}%",
                                           "clan_badge_url": our.badge.url, "opponent_name": opp.name, "opponent_stars": opp.stars, "opponent_destruction":f"{opp.destruction:.2f}%",
                                           "opponent_badge_url": opp.badge.url, **td})
                except Exception as e: r_info["wars"].append({"war_tag": war_tag_val, "error":f"Erro: {e}"})
            rounds_data.append(r_info)
        clans_data = [{"name":c.name, "tag":c.tag, "level":c.level, "badge_url":c.badge.url} for c in lg.clans]
        return {"status":"InCwl", "state": str(lg.state), "season": lg.season, "clans_in_group":clans_data, "rounds":rounds_data}
    except coc.NotFound: return {"status": "NotInCwl", "message": "Grupo CWL não encontrado."}
    except Exception as e: logger.error(f"Erro ao buscar CWL: {e}", exc_info=True); return {"error":str(e), "status": "Error"}

# --- ROTEAMENTO DA API WEB ---
async def api_clan_info_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data("web_clan_info", fetch_clan_info_for_web_api))
async def api_members_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data("web_members", fetch_clan_members_for_web_api))
async def api_current_war_details_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data("web_war_details", fetch_current_war_details_for_web_api))
async def api_war_attacks_remaining_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data("web_attacks_remaining", fetch_war_attacks_remaining_for_web_api))
async def api_war_log_handler(request: web.Request) -> web.Response: limit = int(request.query.get("limit","10")); return web.json_response(await get_cached_web_data(f"web_war_log_{limit}", fetch_war_log_for_web_api, limit))
async def api_cwl_info_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data("web_cwl_info", fetch_cwl_info_for_web_api))

async def api_get_player_note_handler(request: web.Request) -> web.Response:
    if bot.db is None: return web.json_response({"error": "Database not connected"}, status=503)
    player_tag = request.match_info.get('player_tag', None)
    if not player_tag: return web.json_response({"error": "Player tag não fornecida"}, status=400)
    player_tag_fmt = f"#{player_tag}" if not player_tag.startswith("#") else player_tag
    note_doc = await bot.db.players.find_one({"_id": player_tag_fmt})
    return web.json_response(note_doc.get("notes", {"text": "", "priority": "none"}) if note_doc else {"text": "", "priority": "none"})

async def api_save_player_note_handler(request: web.Request) -> web.Response:
    if bot.db is None: return web.json_response({"error": "Database not connected"}, status=503)
    player_tag = request.match_info.get('player_tag', None)
    if not player_tag: return web.json_response({"error": "Player tag não fornecida"}, status=400)
    player_tag_fmt = f"#{player_tag}" if not player_tag.startswith("#") else player_tag
    try:
        data = await request.json()
        note_text = data.get("text", "")
        note_priority = data.get("priority", "none")
        if not isinstance(note_text, str) or note_priority not in ["none", "green", "yellow", "red"]:
            return web.json_response({"error": "Dados inválidos"}, status=400)
        
        if note_text:
            try:
                player = await get_player_data(player_tag_fmt)
                player_name = player.name
            except Exception:
                existing_doc = await bot.db.players.find_one({"_id": player_tag_fmt})
                player_name = existing_doc.get("name", "Desconhecido") if existing_doc else "Desconhecido"
            
            update_op = {'$set': {'name': player_name, 'notes': {'text': note_text, 'priority': note_priority}, 'last_updated': datetime.datetime.now(pytz.utc)}}
            await bot.db.players.update_one({'_id': player_tag_fmt}, update_op, upsert=True)
            logger.info(f"Nota salva/atualizada no DB para {player_tag_fmt}")
        else:
            update_op = {'$unset': {'notes': ""}}
            await bot.db.players.update_one({'_id': player_tag_fmt}, update_op)
            logger.info(f"Nota removida do DB para {player_tag_fmt}")

        if f"web_clan_members_{CLAN_TAG}" in web_api_cache: del web_api_cache[f"web_clan_members_{CLAN_TAG}"]
        return web.json_response({"success": True, "message": "Operação concluída."})
    except Exception as e:
        logger.error(f"Erro em save_player_note para {player_tag_fmt}: {e}", exc_info=True)
        return web.json_response({"error": "Erro interno ao processar a nota"}, status=500)

async def handle_panel_index(request: web.Request) -> web.FileResponse | web.Response:
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "painel.html")
    try: return web.FileResponse(index_path)
    except FileNotFoundError: return web.Response(text="Painel não encontrado.", status=404)

async def setup_web_server() -> Optional[web.AppRunner]:
    app = web.Application()
    app['bot'] = bot
    app.router.add_get("/api/clan", api_clan_info_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/current_war_details", api_current_war_details_handler)
    app.router.add_get("/api/war_attacks_remaining", api_war_attacks_remaining_handler)
    app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler)
    app.router.add_get("/api/notes/{player_tag}", api_get_player_note_handler)
    app.router.add_post("/api/notes/{player_tag}", api_save_player_note_handler)
    app.router.add_get("/painel", handle_panel_index)
    app.router.add_static('/static/', path=os.path.join(os.path.dirname(__file__), "static"), name='static')
    app.router.add_get("/", lambda r: web.Response(text=f"Bot running! v{BOT_VERSION}"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080)))
    await site.start()
    logger.info(f"Servidor web iniciado na porta {site._port}")
    return runner

# --- EVENTOS DO DISCORD E COC (FUNCIONALIDADES REATIVADAS) ---
@bot.event
async def on_ready():
    """
    Executado quando o bot se conecta ao Discord.
    Envia um embed de status para o canal de logs.
    """
    logger.info(f"Bot {bot.user.name} online! Versão: {BOT_VERSION}")
    
    # Aguarda um pouco para garantir que o cliente CoC esteja pronto
    await asyncio.sleep(5) 
    
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        if not clan:
            logger.error("Não foi possível obter dados do clã no on_ready para o embed de status.")
            return

        embed = discord.Embed(
            title=f"✅ ClashGenius Online | {clan.name}",
            description=f"Monitoramento ativado para o clã **{clan.name} ({clan.tag})**.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📊 Status do Clã",
            value=f"**Membros:** {clan.member_count}/50\n**Troféus:** 🏆 {clan.points}",
            inline=True
        )
        embed.add_field(
            name="⚙️ Status do Bot",
            value=f"**Versão:** {BOT_VERSION}\n**API CoC:** ✅ OK",
            inline=True
        )
        if clan.badge and hasattr(clan.badge, 'url'):
            embed.set_thumbnail(url=clan.badge.url)

        await send_log_embed(embed)
        logger.info("Embed de inicialização enviado com sucesso.")

    except Exception as e:
        logger.error(f"Erro ao criar e enviar o embed de inicialização: {e}", exc_info=True)

# --- FUNÇÕES DE EVENTOS DO COC (CORRIGIDO) ---
@coc_client.event # <<-- MUDANÇA 2: Usando decorador no cliente global
async def on_clan_member_join(member, clan):
    """
    Registra a entrada de um novo membro no clã.
    """
    if clan.tag != CLAN_TAG:
        return
    
    embed = discord.Embed(
        title="➡️ Novo Membro no Clã",
        description=f"**{member.name}** ({member.tag}) entrou no clã.",
        color=discord.Color.blue()
    )
    embed.add_field(name="CV", value=member.town_hall, inline=True)
    embed.add_field(name="Liga", value=member.league.name if member.league else "N/A", inline=True)
    embed.add_field(name="Troféus", value=f"🏆 {member.trophies}", inline=True)
    await send_log_embed(embed)
    logger.info(f"Log de entrada enviado para {member.name}.")

@coc_client.event # <<-- MUDANÇA 2: Usando decorador no cliente global
async def on_clan_member_leave(member, clan):
    """
    Registra a saída de um membro do clã.
    """
    if clan.tag != CLAN_TAG:
        return

    embed = discord.Embed(
        title="⬅️ Membro Saiu do Clã",
        description=f"**{member.name}** ({member.tag}) saiu do clã.",
        color=discord.Color.dark_grey()
    )
    embed.add_field(name="CV", value=member.town_hall, inline=True)
    embed.add_field(name="Cargo", value=member.role.name.capitalize() if member.role else "N/A", inline=True)
    await send_log_embed(embed)
    logger.info(f"Log de saída enviado para {member.name}.")

@coc_client.event # <<-- MUDANÇA 2: Usando decorador no cliente global
async def on_war_attack(attack, war):
    """
    Registra um ataque realizado na guerra pelo nosso clã.
    """
    if not hasattr(attack, 'attacker') or not hasattr(attack.attacker, 'clan') or not hasattr(attack.attacker.clan, 'tag'):
        return
        
    if attack.attacker.clan.tag != CLAN_TAG:
        return

    embed = discord.Embed(
        title="⚔️ Ataque na Guerra Realizado!",
        description=f"**{attack.attacker.name}** (CV{attack.attacker.town_hall}) atacou **{attack.defender.name}** (CV{attack.defender.town_hall})",
        color=discord.Color.orange()
    )
    stars = "⭐" * attack.stars + "⚫" * (3 - attack.stars)
    embed.add_field(name="Resultado", value=f"{stars} **{attack.destruction}%**", inline=False)
    
    our_clan = war.clan if war.clan.tag == CLAN_TAG else war.opponent
    opponent_clan = war.opponent if war.clan.tag == CLAN_TAG else war.clan
    embed.add_field(
        name="Placar Atual",
        value=f"**{our_clan.name}:** {our_clan.stars}⭐\n**{opponent_clan.name}:** {opponent_clan.stars}⭐",
        inline=False
    )
    await send_log_embed(embed)
    logger.info(f"Log de ataque na guerra enviado para {attack.attacker.name}.")

# --- INICIALIZAÇÃO DO BOT ---
async def setup_hook():
    logger.info("Executando setup_hook...")
    mongo_url = os.getenv("MONGO_DB_URL")
    if mongo_url:
        try:
            bot.db_client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
            bot.db = bot.db_client.get_default_database()
            await bot.db.command('ping')
            logger.info(f"Conectado ao MongoDB: {bot.db.name}")
        except Exception as e:
            logger.error(f"Falha ao conectar ao MongoDB: {e}", exc_info=True)
            bot.db_client = None; bot.db = None
    else:
        logger.error("MONGO_DB_URL não definida. DB desabilitado.")
        bot.db_client = None; bot.db = None
    
    # Adiciona o cliente CoC (já com eventos) ao bot
    bot.coc_client = coc_client # <<-- MUDANÇA 3: Atribui o cliente global ao bot

    try:
        await bot.coc_client.login(os.getenv("COC_EMAIL"), os.getenv("COC_PASSWORD"))
        logger.info("Login no CoC bem-sucedido.")
        
        # Adiciona a tag do clã para monitoramento
        bot.coc_client.add_clan_updates(CLAN_TAG)
        bot.coc_client.add_war_updates(CLAN_TAG)
        logger.info(f"Monitoramento e eventos ativados para o clã {CLAN_TAG}")

    except Exception as e:
        logger.error(f"Falha no login do CoC: {e}", exc_info=True) # Adicionado exc_info para mais detalhes
        return

    bot.web_runner = await setup_web_server()

async def main():
    bot.setup_hook = setup_hook
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    if not all(os.getenv(var) for var in ["DISCORD_TOKEN", "COC_EMAIL", "COC_PASSWORD", "CLAN_TAG", "MONGO_DB_URL"]):
        logger.critical("Variáveis de ambiente essenciais faltando.")
    else:
        asyncio.run(main())
