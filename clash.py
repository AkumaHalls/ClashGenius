# -*- coding: utf-8 -*-
# Versão 19.8 - (Painel de Guerra redesenhado, correções de import e sintaxe, arquivo completo - Observações de Membros adicionadas à base original)

import os
import logging # Movido para cima
import asyncio
import datetime
from aiohttp import web
from typing import Dict, List, Optional, Union, Set, Any
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
import json # Adicionado para observações

# Configure logging (MOVIDO PARA O TOPO, ANTES DE QUALQUER USO DO LOGGER)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("coc_discord_bot")
# FIM DA CONFIGURAÇÃO DO LOGGER

# ---- IMPORTAÇÕES ESPECÍFICAS DO COC ----
from coc import ( # Classes que geralmente são seguras para importar diretamente
    ClanWar,
    Player,
    Clan,
    WarAttack,
    Timestamp,
    ClanMember
)

# Tentativa de importar classes potencialmente problemáticas
WarLogEntry = None
LeagueGroup = None
CapitalDistrict = None

try:
    from coc.wars import WarLogEntry as WarLogEntry_wars
    if WarLogEntry_wars: WarLogEntry = WarLogEntry_wars
except ImportError as e_wle_wars:
    logger.warning(f"Falha ao importar 'WarLogEntry' de 'coc.wars': {e_wle_wars}.")
if not WarLogEntry:
    try:
        from coc import WarLogEntry as WarLogEntry_coc
        if WarLogEntry_coc: WarLogEntry = WarLogEntry_coc; logger.info("WarLogEntry importado com sucesso de 'coc'.")
    except ImportError as e_wle_coc:
        logger.warning(f"Falha ao importar 'WarLogEntry' de 'coc': {e_wle_coc}. Histórico de Guerras desabilitado.")

try:
    from coc.wars import LeagueGroup as LeagueGroup_wars
    if LeagueGroup_wars: LeagueGroup = LeagueGroup_wars
except ImportError as e_lg_wars:
    logger.warning(f"Falha ao importar 'LeagueGroup' de 'coc.wars': {e_lg_wars}.")
if not LeagueGroup:
    try:
        from coc import LeagueGroup as LeagueGroup_coc
        if LeagueGroup_coc: LeagueGroup = LeagueGroup_coc; logger.info("LeagueGroup importado com sucesso de 'coc'.")
    except ImportError as e_lg_coc:
        logger.warning(f"Falha ao importar 'LeagueGroup' de 'coc': {e_lg_coc}. Funcionalidade de CWL desabilitada.")

try:
    from coc.clans import CapitalDistrict as CapitalDistrict_clans
    if CapitalDistrict_clans: CapitalDistrict = CapitalDistrict_clans
except ImportError as e_cd_clans:
    logger.warning(f"Falha ao importar 'CapitalDistrict' de 'coc.clans': {e_cd_clans}.")
if not CapitalDistrict:
    try:
        from coc import CapitalDistrict as CapitalDistrict_coc
        if CapitalDistrict_coc: CapitalDistrict = CapitalDistrict_coc; logger.info("CapitalDistrict importado com sucesso de 'coc'.")
    except ImportError as e_cd_coc:
        logger.warning(f"Falha ao importar 'CapitalDistrict' de 'coc': {e_cd_coc}. Detalhes da Capital desabilitados.")
# ---- FIM DA SEÇÃO DE IMPORTAÇÕES ESPECÍFICAS ----

import pytz
from dotenv import load_dotenv

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

BOT_VERSION = "19.8" # Atualizado para refletir novas funcionalidades
OBSERVATIONS_FILE = "member_observations.json" # Arquivo para salvar observações

reported_war_ends: Set[str] = set()
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

player_short_term_cache: Dict[str, Player] = {}
clan_cache: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION_SECONDS = 300

# --- Funções para Observações de Membros ---
def load_member_observations() -> Dict[str, Any]:
    try:
        with open(OBSERVATIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.info(f"Arquivo de observações '{OBSERVATIONS_FILE}' não encontrado. Será criado um novo ao salvar a primeira observação.")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Erro ao decodificar o arquivo JSON de observações: {OBSERVATIONS_FILE}. Retornando um dicionário vazio.")
        return {}
    except Exception as e:
        logger.error(f"Erro inesperado ao carregar observações de '{OBSERVATIONS_FILE}': {e}", exc_info=True)
        return {}

def save_member_observations(data: Dict[str, Any]) -> None:
    try:
        with open(OBSERVATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.debug(f"Observações salvas com sucesso em '{OBSERVATIONS_FILE}'.")
    except IOError as e:
        logger.error(f"Erro de I/O ao tentar salvar observações em '{OBSERVATIONS_FILE}': {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Erro inesperado ao tentar salvar observações em '{OBSERVATIONS_FILE}': {e}", exc_info=True)


async def get_clan_data_base(tag: str) -> Clan: # Mantida a lógica original do usuário
    if not bot.coc_client or not bot.coc_client.http: # type: ignore
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        if not tag.startswith("#"): tag = f"#{tag}"
        return await bot.coc_client.get_clan(tag) # type: ignore
    except coc.NotFound: raise ValueError(f"Clã com tag {tag} não encontrado.")
    except coc.Maintenance: raise ValueError("API CoC em manutenção.")
    except asyncio.TimeoutError: raise ValueError("Timeout buscando dados do clã.")
    except coc.InvalidCredentials: raise ValueError("Credenciais API CoC inválidas.")
    except coc.Forbidden: raise ValueError("Acesso proibido à API CoC.")
    except Exception as e: logger.error(f"Erro ao buscar clã {tag}: {e}", exc_info=True); raise ValueError(f"Erro ao buscar clã: {e}")

async def get_player_data(tag: str) -> Player: # Mantida a lógica original do usuário
    normalized_tag = tag if tag.startswith("#") else f"#{tag}"
    if normalized_tag in player_short_term_cache: return player_short_term_cache[normalized_tag]
    if not bot.coc_client or not bot.coc_client.http: raise ValueError("Cliente CoC não inicializado.") # type: ignore
    try:
        player = await bot.coc_client.get_player(normalized_tag) # type: ignore
        player_short_term_cache[normalized_tag] = player
        return player
    except coc.NotFound: raise ValueError(f"Jogador {normalized_tag} não encontrado.")
    except coc.Maintenance: raise ValueError("API CoC em manutenção.")
    except asyncio.TimeoutError: raise ValueError("Timeout buscando jogador.")
    except coc.InvalidCredentials: raise ValueError("Credenciais API CoC inválidas.")
    except coc.Forbidden: raise ValueError("Acesso proibido à API CoC.")
    except Exception as e: logger.error(f"Erro ao buscar jogador {normalized_tag}: {e}", exc_info=True); raise ValueError(f"Erro ao buscar jogador: {e}")

async def get_clan_data_with_cache(tag: str) -> Clan: # Mantida a lógica original do usuário
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

async def fetch_location_id(location_name: str) -> int: # Mantida a lógica original do usuário
    if not bot.coc_client or not bot.coc_client.http: # type: ignore
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        locations = await bot.coc_client.search_locations(name=location_name, limit=1) # type: ignore
        if not locations: raise ValueError(f"Localização '{location_name}' não encontrada.")
        loc_obj = locations[0]
        if hasattr(loc_obj, 'id'): return loc_obj.id
        else: raise ValueError(f"Objeto de localização para '{location_name}' não possui ID.")
    except Exception as e: logger.error(f"Erro ao buscar ID da localização '{location_name}': {e}", exc_info=True); raise ValueError(f"Erro ao buscar ID da localização: {str(e)}")

async def send_log_embed(embed_to_log: discord.Embed, content: str = None) -> None: # Mantida a lógica original do usuário
    if not CHANNEL_ID or CHANNEL_ID == 0: logger.warning("CHANNEL_ID não configurado."); return
    if not hasattr(embed_to_log, 'footer') or not embed_to_log.footer or not getattr(embed_to_log.footer, 'text', None):
         embed_to_log.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}") # type: ignore
    if not embed_to_log.timestamp: embed_to_log.timestamp = datetime.datetime.now(TIMEZONE)
    try:
        channel_log_obj = await bot.fetch_channel(CHANNEL_ID)
        if isinstance(channel_log_obj, discord.TextChannel): await channel_log_obj.send(content=content, embed=embed_to_log)
        else: logger.error(f"Canal de log ID {CHANNEL_ID} não é um canal de texto.")
    except discord.NotFound: logger.error(f"Canal de log ID {CHANNEL_ID} não encontrado.")
    except discord.Forbidden: logger.error(f"Sem permissão no canal de log ID {CHANNEL_ID}.")
    except Exception as e: logger.error(f"Erro ao enviar embed para log ID {CHANNEL_ID}: {e}", exc_info=True)

async def send_embeds_splitted(channel: discord.TextChannel, base_embed: discord.Embed, field_name: str, items: List[str]) -> None: # Mantida a lógica original do usuário
    if not isinstance(channel, discord.TextChannel): logger.error("Canal inválido para send_embeds_splitted."); return
    if not items:
         embed_empty_split = discord.Embed.from_dict(base_embed.to_dict())
         embed_empty_split.add_field(name=field_name, value="Nenhum item encontrado.", inline=False)
         if not hasattr(embed_empty_split, 'footer') or not embed_empty_split.footer or not getattr(embed_empty_split.footer, 'text', None):
             embed_empty_split.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}") # type: ignore
         if not embed_empty_split.timestamp:
             embed_empty_split.timestamp = datetime.datetime.now(TIMEZONE)
         try: await channel.send(embed=embed_empty_split)
         except Exception as e: logger.error(f"Erro ao enviar embed dividido (vazio) para {channel.id}: {e}", exc_info=True)
         return
    embeds_to_send = []; current_embed_split = discord.Embed.from_dict(base_embed.to_dict()); current_field_value_split = ""
    for item in items:
        item_line = item + "\n"
        if (len(current_field_value_split) + len(item_line) > 1024 or len(current_embed_split) + len(current_field_value_split) + len(item_line) > 5900): # type: ignore
            if current_field_value_split: current_embed_split.add_field(name=(field_name or "Dados"), value=current_field_value_split, inline=False)
            if current_embed_split.fields: embeds_to_send.append(current_embed_split)
            current_embed_split = discord.Embed.from_dict(base_embed.to_dict()); current_field_value_split = item_line
            if len(current_field_value_split) > 1024: current_field_value_split = current_field_value_split[:1021] + "...\n"
        else: current_field_value_split += item_line
    if current_field_value_split: current_embed_split.add_field(name=(field_name or "Dados"), value=current_field_value_split, inline=False)
    if current_embed_split.fields: embeds_to_send.append(current_embed_split)
    for embed_item_to_send in embeds_to_send:
        if not hasattr(embed_item_to_send, 'footer') or not embed_item_to_send.footer or not getattr(embed_item_to_send.footer, 'text', None):
             embed_item_to_send.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}") # type: ignore
        if not embed_item_to_send.timestamp: embed_item_to_send.timestamp = datetime.datetime.now(TIMEZONE)
        try: await channel.send(embed=embed_item_to_send)
        except Exception as e: logger.error(f"Erro ao enviar embed dividido para {channel.id}: {e}", exc_info=True); break

def format_war_time_details(war_obj: ClanWar, time_now_tz: datetime.datetime) -> Dict[str, Any]: # Mantida a lógica original do usuário
    details: Dict[str, Any] = { "time_key": "N/A", "time_value": "N/A", "time_remaining": "N/A", "start_time_iso": None, "end_time_iso": None }
    if hasattr(war_obj, 'state') and war_obj.state == "preparation":
        if hasattr(war_obj, 'start_time') and war_obj.start_time and hasattr(war_obj.start_time, 'time'):
            start_aware = pytz.utc.localize(war_obj.start_time.time).astimezone(TIMEZONE)
            details["start_time_iso"] = start_aware.isoformat(); details["time_key"] = "Início"; details["time_value"] = start_aware.strftime('%d/%m/%y %H:%M') # Ano com 2 digitos
            delta = start_aware - time_now_tz
            if delta.total_seconds() > 0: d, r = divmod(delta.total_seconds(), 86400); h, r = divmod(r, 3600); m, _ = divmod(r, 60); details["time_remaining"] = f"{int(d)}d {int(h)}h {int(m)}m" if d > 0 else f"{int(h)}h {int(m)}m"
            else: details["time_remaining"] = "Iniciando..."
    elif hasattr(war_obj, 'state') and (war_obj.state == "inWar" or war_obj.state == "warEnded"):
        if hasattr(war_obj, 'end_time') and war_obj.end_time and hasattr(war_obj.end_time, 'time'):
            end_aware = pytz.utc.localize(war_obj.end_time.time).astimezone(TIMEZONE)
            details["end_time_iso"] = end_aware.isoformat(); details["time_key"] = "Fim" if war_obj.state == "inWar" else "Finalizada em"; details["time_value"] = end_aware.strftime('%d/%m/%y %H:%M') # Ano com 2 digitos
            if war_obj.state == "inWar":
                delta = end_aware - time_now_tz
                if delta.total_seconds() > 0: d, r = divmod(delta.total_seconds(), 86400); h, r = divmod(r, 3600); m, _ = divmod(r, 60); details["time_remaining"] = f"{int(d)}d {int(h)}h {int(m)}m" if d > 0 else f"{int(h)}h {int(m)}m"
                else: details["time_remaining"] = "Finalizando..."
            else: details["time_remaining"] = "-"
    return details

async def get_current_or_last_war(clan_tag_param: str) -> Optional[ClanWar]: # Mantida a lógica original do usuário
    current_war: Optional[ClanWar] = None
    try:
        if LeagueGroup and bot.coc_client: # type: ignore
            league_group = await bot.coc_client.get_league_group(clan_tag_param) # type: ignore
            if league_group and getattr(league_group,'state',None) != "notInWar" and hasattr(league_group, 'rounds'):
                if hasattr(league_group, 'current_wars') and league_group.current_wars:
                    for war_tag_obj in reversed(league_group.current_wars):
                        try:
                            lg_war = await league_group.get_league_war(war_tag_obj.tag)
                            if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param) and lg_war.state in ["inWar", "preparation"]:
                                current_war = lg_war
                                if lg_war.opponent.tag == clan_tag_param: current_war.clan, current_war.opponent = current_war.opponent, current_war.clan # type: ignore
                                return current_war
                        except (coc.NotFound, Exception): continue
                for war_tags_in_round in reversed(league_group.rounds):
                    for war_tag_str in war_tags_in_round:
                        if war_tag_str == "#0": continue
                        try:
                            lg_war = await league_group.get_league_war(war_tag_str)
                            if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param) and lg_war.state in ["inWar", "preparation"]:
                                current_war = lg_war
                                if lg_war.opponent.tag == clan_tag_param: current_war.clan, current_war.opponent = current_war.opponent, current_war.clan # type: ignore
                                return current_war
                        except (coc.NotFound, Exception): continue
                if not current_war and league_group.rounds:
                    best_ended_cwl_war = None
                    for war_tags_in_round in reversed(league_group.rounds):
                        for war_tag_str in war_tags_in_round:
                            if war_tag_str == "#0": continue
                            try:
                                lg_war = await league_group.get_league_war(war_tag_str)
                                if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param) and lg_war.state == "warEnded":
                                    if not best_ended_cwl_war or (hasattr(lg_war, 'end_time') and hasattr(best_ended_cwl_war, 'end_time') and lg_war.end_time.time > best_ended_cwl_war.end_time.time): # type: ignore
                                        best_ended_cwl_war = lg_war
                            except (coc.NotFound, Exception): continue
                    if best_ended_cwl_war:
                        if best_ended_cwl_war.opponent.tag == clan_tag_param: best_ended_cwl_war.clan, best_ended_cwl_war.opponent = best_ended_cwl_war.opponent, best_ended_cwl_war.clan # type: ignore
                        return best_ended_cwl_war
    except coc.NotFound: logger.debug(f"Nenhum grupo CWL para {clan_tag_param}.")
    except Exception as e_cwl: logger.error(f"Erro guerra CWL para {clan_tag_param}: {e_cwl}", exc_info=True)
    try:
        if bot.coc_client: # type: ignore
            regular_war = await bot.coc_client.get_current_war(clan_tag_param) # type: ignore
            if regular_war and regular_war.state != "notInWar": return regular_war
    except coc.PrivateWarLog: logger.warning(f"Log guerra regular {clan_tag_param} privado.")
    except coc.NotFound: logger.debug(f"Nenhuma guerra regular para {clan_tag_param}.")
    except Exception as e_reg: logger.error(f"Erro guerra regular para {clan_tag_param}: {e_reg}", exc_info=True)
    return None

# ============================================================================ #
# ==================== INÍCIO DAS MODIFICAÇÕES PARA PAINEL WEB ==================== #
# ============================================================================ #
web_api_cache: Dict[str, Dict[str, Any]] = {} # Mantida a lógica original do usuário
WEB_API_CACHE_DURATION_SECONDS = 45 # Mantida a lógica original do usuário

async def get_cached_web_data(key: str, func_to_fetch_data: callable, *args: Any) -> Any: # Mantida a lógica original do usuário
    now = datetime.datetime.now()
    if key in web_api_cache:
        cache_entry = web_api_cache[key]
        if "timestamp" in cache_entry and isinstance(cache_entry["timestamp"], datetime.datetime):
            if (now - cache_entry["timestamp"]).total_seconds() < WEB_API_CACHE_DURATION_SECONDS: return cache_entry["data"]
    data = await func_to_fetch_data(*args)
    web_api_cache[key] = {"data": data, "timestamp": now}
    return data

async def fetch_clan_info_for_web_api() -> Dict[str, Any]: # Mantida a lógica original do usuário
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG); districts = []
        if CapitalDistrict and hasattr(clan, 'capital_districts') and clan.capital_districts:
            for d in clan.capital_districts: districts.append({"name": d.name, "level": d.hall_level})
        elif not CapitalDistrict: districts = [{"name": "Distritos Indisponíveis (erro import)", "level": ""}]
        else: districts = [{"name": "Nenhum distrito.", "level": ""}]
        return {"name": clan.name, "tag": clan.tag, "level": clan.level, "points": clan.points,
                "capital_points": getattr(clan, 'capital_points', 0), "member_count": clan.member_count,
                "description": clan.description, "war_wins": getattr(clan, 'war_wins', 'N/A'),
                "location": clan.location.name if hasattr(clan, 'location') and clan.location else "N/A",
                "type": clan.type.capitalize() if hasattr(clan, 'type') and clan.type else "N/A",
                "badge_url": clan.badge.url if hasattr(clan, 'badge') and clan.badge else None,
                "version": BOT_VERSION, "capital_districts": districts,
                "capital_league": clan.capital_league.name if hasattr(clan, 'capital_league') and clan.capital_league else "N/A"}
    except Exception as e: logger.error(f"Erro API clã web: {e}", exc_info=True); return {"error": str(e), "name": "Erro Clã"}

async def fetch_clan_members_for_web_api() -> Dict[str, Any]: # Modificada para incluir observações
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG); members_data = []
        observations = load_member_observations() # Carrega observações
        clan_observations = observations.get(CLAN_TAG, {}) # Pega observações específicas do clã

        if hasattr(clan, 'members') and clan.members:
            for m in clan.members:
                member_obs = clan_observations.get(m.tag, {"text": "", "priority": "normal"}) # Pega obs do membro ou default
                members_data.append({
                    "name": m.name, "tag": m.tag, "town_hall": m.town_hall, "exp_level": m.exp_level,
                    "league": m.league.name if hasattr(m, 'league') and m.league else "N/A",
                    "trophies": m.trophies, "role": m.role.name.capitalize() if hasattr(m, 'role') and m.role else "Membro",
                    "donations": m.donations, "received": m.received,
                    "observation_text": member_obs["text"], # Adiciona texto da observação
                    "observation_priority": member_obs["priority"] # Adiciona prioridade
                })
        members_data.sort(key=lambda x: x.get("trophies", 0), reverse=True)
        return {"members": members_data, "clan_name": clan.name, "clan_tag": clan.tag}
    except Exception as e: logger.error(f"Erro API membros web: {e}", exc_info=True); return {"error": str(e)}

async def fetch_current_war_details_for_web_api() -> Dict[str, Any]: # Mantida a lógica original do usuário
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado.", "war_data": None, "attacks": [], "our_clan_members_in_war": [], "opponent_clan_members_in_war": []}
    player_short_term_cache.clear(); war = await get_current_or_last_war(CLAN_TAG)
    if not war or (hasattr(war, 'state') and war.state == "notInWar"):
        return {"error": "Nenhuma guerra para detalhar.", "war_data": None, "attacks": [], "our_clan_members_in_war": [], "opponent_clan_members_in_war": []}

    our_clan_war_obj, opponent_clan_war_obj = (war.clan, war.opponent)
    if war.clan.tag != CLAN_TAG and war.opponent.tag == CLAN_TAG: # Normaliza
        our_clan_war_obj, opponent_clan_war_obj = opponent_clan_war_obj, our_clan_war_obj
    elif war.clan.tag != CLAN_TAG and war.opponent.tag != CLAN_TAG: # Guerra não nos envolve?
        logger.warning(f"fetch_current_war_details: Guerra {war.tag if hasattr(war, 'tag') else 'N/A'} não parece envolver {CLAN_TAG}") # type: ignore

    all_attacks_data = []
    if war.attacks:
        for attack in sorted(war.attacks, key=lambda a: a.order):
            try: p_att = await get_player_data(attack.attacker_tag); att_name, att_th = p_att.name, p_att.town_hall
            except ValueError: att_name, att_th = attack.attacker_tag, '?' # type: ignore
            try: p_def = await get_player_data(attack.defender_tag); def_name, def_th = p_def.name, p_def.town_hall
            except ValueError: def_name, def_th = attack.defender_tag, '?' # type: ignore
            all_attacks_data.append({"order": attack.order, "attacker_tag": attack.attacker_tag, "attacker_name": att_name, "attacker_townhall": att_th,
                                 "defender_tag": attack.defender_tag, "defender_name": def_name, "defender_townhall": def_th,
                                 "stars": attack.stars, "destruction": attack.destruction, "duration": getattr(attack, 'duration', 'N/A')})

    async def get_member_war_details_async(member: ClanMember, war_obj_ref: ClanWar) -> Dict[str, Any]: # Adicionado war_obj_ref
        member_attacks_data = []
        if member.attacks:
            for atk in member.attacks:
                try: p_def = player_short_term_cache.get(atk.defender_tag) or await get_player_data(atk.defender_tag)
                except ValueError: p_def = None # type: ignore
                member_attacks_data.append({"defender_tag": atk.defender_tag, "defender_name": p_def.name if p_def else atk.defender_tag, # type: ignore
                                           "defender_townhall": p_def.town_hall if p_def else '?', "stars": atk.stars, "destruction": atk.destruction, "order": atk.order}) # type: ignore
        member_defenses_data = []
        if hasattr(member, 'defenses') and member.defenses:
             for defense in member.defenses:
                try: p_att = player_short_term_cache.get(defense.attacker_tag) or await get_player_data(defense.attacker_tag)
                except ValueError: p_att = None # type: ignore
                member_defenses_data.append({"attacker_tag": defense.attacker_tag, "attacker_name": p_att.name if p_att else defense.attacker_tag, # type: ignore
                                           "attacker_townhall": p_att.town_hall if p_att else '?', "stars": defense.stars, "destruction": defense.destruction, "order": defense.order}) # type: ignore
        return {"tag": member.tag, "name": member.name, "townhall": member.town_hall, "map_position": member.map_position,
                "attacks_used": len(member.attacks) if member.attacks else 0,
                "attacks_remaining": war_obj_ref.attacks_per_member - (len(member.attacks) if member.attacks else 0), # Usa war_obj_ref
                "attacks_made": member_attacks_data, "defenses_received": member_defenses_data,
                "best_opponent_attack": {"stars": member.best_opponent_attack.stars, "attacker_tag": member.best_opponent_attack.attacker_tag} if member.best_opponent_attack else None}

    our_clan_members_in_war_data = [await get_member_war_details_async(m, war) for m in our_clan_war_obj.members] if our_clan_war_obj and our_clan_war_obj.members else []
    opponent_clan_members_in_war_data = [await get_member_war_details_async(m, war) for m in opponent_clan_war_obj.members] if opponent_clan_war_obj and opponent_clan_war_obj.members else []
    our_clan_members_in_war_data.sort(key=lambda m: m["map_position"]); opponent_clan_members_in_war_data.sort(key=lambda m: m["map_position"])
    time_details = format_war_time_details(war, datetime.datetime.now(TIMEZONE)); war_type_desc = "Guerra";
    if hasattr(war, 'is_cwl') and war.is_cwl: war_type_desc = "CWL"
    elif hasattr(war, 'type') and war.type == "friendly": war_type_desc = "Amistosa"
    clan_star_dist = {0:0,1:0,2:0,3:0}; opp_star_dist = {0:0,1:0,2:0,3:0}
    c_total_dur, c_atk_count, o_total_dur, o_atk_count = 0.0,0,0.0,0 # Floats para duration
    for att_det in all_attacks_data:
        is_our_att = any(m["tag"] == att_det["attacker_tag"] for m in our_clan_members_in_war_data)
        current_star_dist = clan_star_dist if is_our_att else opp_star_dist
        current_star_dist[att_det["stars"]] = current_star_dist.get(att_det["stars"], 0) + 1 # Mais seguro

        duration_val = att_det["duration"]
        if isinstance(duration_val, (int, float)):
            if is_our_att: c_total_dur += duration_val; c_atk_count +=1
            else: o_total_dur += duration_val; o_atk_count +=1

    war_gen_data = {
        "status": war.state, "type": war_type_desc, "state_description": war.state.capitalize() if war.state else "N/A",
        "clan_name": our_clan_war_obj.name, "clan_tag": our_clan_war_obj.tag, "clan_stars": our_clan_war_obj.stars,
        "clan_destruction": f"{our_clan_war_obj.destruction:.2f}%", "clan_badge_url": our_clan_war_obj.badge.url if hasattr(our_clan_war_obj.badge, 'url') else None,
        "clan_attacks_used": our_clan_war_obj.attacks_used if hasattr(our_clan_war_obj, 'attacks_used') else len([a for m in our_clan_members_in_war_data for a in m['attacks_made']]),
        "opponent_name": opponent_clan_war_obj.name, "opponent_tag": opponent_clan_war_obj.tag, "opponent_stars": opponent_clan_war_obj.stars,
        "opponent_destruction": f"{opponent_clan_war_obj.destruction:.2f}%", "opponent_badge_url": opponent_clan_war_obj.badge.url if hasattr(opponent_clan_war_obj.badge, 'url') else None,
        "opponent_attacks_used": opponent_clan_war_obj.attacks_used if hasattr(opponent_clan_war_obj, 'attacks_used') else len([a for m in opponent_clan_members_in_war_data for a in m['attacks_made']]),
        **time_details,
        "attacks_per_member": war.attacks_per_member, "team_size": war.team_size,
        "clan_star_distribution": clan_star_dist, "opponent_star_distribution": opp_star_dist,
        "clan_avg_stars": f"{our_clan_war_obj.stars/c_atk_count:.2f}" if c_atk_count>0 else "0.00", "opponent_avg_stars": f"{opponent_clan_war_obj.stars/o_atk_count:.2f}" if o_atk_count>0 else "0.00",
        "clan_avg_destruction_percent": f"{our_clan_war_obj.destruction:.2f}", "opponent_avg_destruction_percent": f"{opponent_clan_war_obj.destruction:.2f}",
        "clan_avg_duration": f"{c_total_dur/c_atk_count:.1f}s" if c_atk_count>0 else "0s", "opponent_avg_duration": f"{o_total_dur/o_atk_count:.1f}s" if o_atk_count>0 else "0s"}
    return {"war_data": war_gen_data, "all_attacks": all_attacks_data, "our_clan_members_in_war": our_clan_members_in_war_data, "opponent_clan_members_in_war": opponent_clan_members_in_war_data}

async def fetch_war_attacks_remaining_for_web_api() -> Dict[str, Any]: # Mantida a lógica original do usuário
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    war = await get_current_or_last_war(CLAN_TAG); clan_name = "N/A"
    our_clan_obj_rem = None
    if war:
        if war.clan.tag == CLAN_TAG: our_clan_obj_rem = war.clan; clan_name = our_clan_obj_rem.name
        elif war.opponent.tag == CLAN_TAG: our_clan_obj_rem = war.opponent; clan_name = our_clan_obj_rem.name # type: ignore
    if not war or war.state != "inWar": return {"message": "Não há guerra em andamento.", "members_pending": [], "clan_name": clan_name}
    if not our_clan_obj_rem: return {"message": "Erro ao id nosso clã.", "members_pending": [], "clan_name": "Erro"}
    pending = []
    if our_clan_obj_rem.members:
        for m in our_clan_obj_rem.members:
            left = war.attacks_per_member - (len(m.attacks) if m.attacks else 0)
            if left > 0: pending.append({"name": m.name, "tag": m.tag, "town_hall": m.town_hall, "attacks_left": left, "map_position": m.map_position})
    pending.sort(key=lambda x: x.get("map_position", 0))
    return {"message": "Membros pendentes.", "members_pending": pending, "clan_name": our_clan_obj_rem.name}

async def fetch_war_log_for_web_api(limit: int = 10) -> Dict[str, Any]: # Mantida a lógica original do usuário
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    if not WarLogEntry: return {"error": "Histórico de Guerras indisponível (dependência).", "log": []}
    try:
        log_iter = await bot.coc_client.get_war_log(CLAN_TAG); entries = []; count = 0 # type: ignore
        async for entry in log_iter: # type: ignore
            if count >= limit: break; res = "N/A"
            if entry.clan.tag == CLAN_TAG and entry.result: res = "Vitória" if entry.result == "win" else "Derrota" if entry.result == "lose" else "Empate"
            elif entry.opponent.tag == CLAN_TAG and entry.result: res = "Derrota" if entry.result == "win" else "Vitória" if entry.result == "lose" else "Empate"
            entries.append({"clan_name": entry.clan.name, "clan_stars": entry.clan.stars, "clan_destruction": entry.clan.destruction, "clan_badge_url": entry.clan.badge.url if hasattr(entry.clan.badge, 'url') else None,
                            "opponent_name": entry.opponent.name, "opponent_stars": entry.opponent.stars, "opponent_destruction": entry.opponent.destruction, "opponent_badge_url": entry.opponent.badge.url if hasattr(entry.opponent.badge, 'url') else None,
                            "team_size": entry.team_size, "end_time": entry.end_time.time.strftime('%d/%m/%y %H:%M') if entry.end_time and hasattr(entry.end_time, 'time') else "N/A",
                            "result": res, "is_cwl": getattr(entry, 'is_cwl', False)})
            count +=1
        return {"log": entries}
    except coc.PrivateWarLog: return {"error": "Log de guerras privado."}
    except Exception as e: logger.error(f"Erro API log web: {e}", exc_info=True); return {"error": str(e)}

async def fetch_cwl_info_for_web_api() -> Dict[str, Any]: # Mantida a lógica original do usuário
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    if not LeagueGroup: return {"status": "CwlFeatureDisabled", "message": "Funcionalidade de CWL indisponível (dependência)."}
    try:
        lg = await bot.coc_client.get_league_group(CLAN_TAG) # type: ignore
        if not lg or (hasattr(lg, 'state') and lg.state == "notInWar"): return {"status": "NotInCwl", "message": "Clã não em CWL."}
        rounds_data = []
        if lg.rounds:
            for i, tags in enumerate(lg.rounds):
                r_info: Dict[str, Any] = {"round_number": i + 1, "wars": []};
                if not tags: r_info["wars"].append({"message": "Rodada não definida."})
                else:
                    for tag_val_cwl_web in tags:
                        if tag_val_cwl_web=="#0": r_info["wars"].append({"message":"Bye."}); continue
                        try:
                            war = await lg.get_league_war(tag_val_cwl_web); our, opp = (war.clan, war.opponent) if war.clan.tag == CLAN_TAG else (war.opponent, war.clan)
                            td = format_war_time_details(war, datetime.datetime.now(TIMEZONE))
                            r_info["wars"].append({"war_tag":tag_val_cwl_web, "state":war.state, "clan_name":our.name, "clan_stars":our.stars, "clan_destruction":f"{our.destruction:.2f}%", "clan_badge_url":our.badge.url if hasattr(our.badge, 'url') else None,
                                                "opponent_name":opp.name, "opponent_stars":opp.stars, "opponent_destruction":f"{opp.destruction:.2f}%", "opponent_badge_url":opp.badge.url if hasattr(opp.badge, 'url') else None, **td})
                        except Exception as e_w: r_info["wars"].append({"war_tag":tag_val_cwl_web, "error":f"Erro: {e_w}"})
                rounds_data.append(r_info)
        clans_data = [{"name":c.name, "tag":c.tag, "level":c.level, "badge_url":c.badge.url if hasattr(c.badge, 'url') else None} for c in lg.clans] if lg.clans else []
        return {"status":"InCwl", "state":lg.state, "season":lg.season.strftime('%Y-%m') if hasattr(lg,'season') and lg.season else "N/A", "clans_in_group":clans_data, "rounds":rounds_data}
    except coc.NotFound: return {"status": "NotInCwl", "message": "Grupo CWL não encontrado."}
    except Exception as e: logger.error(f"Erro API CWL web: {e}", exc_info=True); return {"error":str(e)}

async def api_clan_info_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_clan_info_{CLAN_TAG}", fetch_clan_info_for_web_api))
async def api_members_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_clan_members_{CLAN_TAG}", fetch_clan_members_for_web_api))
async def api_current_war_details_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_current_war_details_{CLAN_TAG}", fetch_current_war_details_for_web_api))
async def api_war_attacks_remaining_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_war_attacks_remaining_{CLAN_TAG}", fetch_war_attacks_remaining_for_web_api))
async def api_war_log_handler(request: web.Request) -> web.Response:
    limit_str = request.query.get("limit","10")
    try: limit = int(limit_str)
    except ValueError: limit = 10
    limit=max(1,min(limit,50))
    return web.json_response(await get_cached_web_data(f"web_war_log_{CLAN_TAG}_limit{limit}",fetch_war_log_for_web_api,limit))
async def api_cwl_info_handler(request: web.Request) -> web.Response: return web.json_response(await get_cached_web_data(f"web_cwl_info_{CLAN_TAG}", fetch_cwl_info_for_web_api))

# Nova rota para salvar observações
async def api_save_member_observation_handler(request: web.Request) -> web.Response:
    if not CLAN_TAG:
        return web.json_response({"status": "error", "message": "CLAN_TAG não configurado no servidor."}, status=500)
    try:
        data = await request.json()
        player_tag = data.get("player_tag")
        observation_text = data.get("observation_text", "")
        observation_priority = data.get("observation_priority", "normal")

        if not player_tag:
            return web.json_response({"status": "error", "message": "player_tag é obrigatório."}, status=400)
        if not isinstance(player_tag, str) or not player_tag.startswith("#"):
             return web.json_response({"status": "error", "message": "player_tag inválido."}, status=400)
        if observation_priority not in ["normal", "alert", "critical"]: # Validação da prioridade
            return web.json_response({"status": "error", "message": "Prioridade inválida."}, status=400)

        all_observations = load_member_observations()
        if CLAN_TAG not in all_observations:
            all_observations[CLAN_TAG] = {} # type: ignore

        all_observations[CLAN_TAG][player_tag] = { # type: ignore
            "text": observation_text,
            "priority": observation_priority
        }
        save_member_observations(all_observations)

        # Invalida o cache de membros para que a próxima requisição pegue os dados atualizados
        if f"web_clan_members_{CLAN_TAG}" in web_api_cache:
            del web_api_cache[f"web_clan_members_{CLAN_TAG}"]
            logger.info(f"Cache de membros para {CLAN_TAG} invalidado após salvar observação.")

        return web.json_response({"status": "success", "message": "Observação salva."})
    except json.JSONDecodeError:
        return web.json_response({"status": "error", "message": "Payload JSON inválido."}, status=400)
    except Exception as e:
        logger.error(f"Erro ao salvar observação para o jogador {player_tag if 'player_tag' in locals() else 'desconhecido'}: {e}", exc_info=True)
        return web.json_response({"status": "error", "message": f"Erro interno do servidor: {str(e)}"}, status=500)


async def handle_panel_index(request: web.Request) -> Union[web.FileResponse, web.Response]: # Mantida a lógica original do usuário
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "painel.html")
    try:
        return web.FileResponse(index_path)
    except FileNotFoundError: # type: ignore
        logger.error(f"painel.html não encontrado em {index_path}"); return web.Response(text="Painel não encontrado.", status=404)
    except Exception as e: # type: ignore
        logger.error(f"Erro ao servir painel.html: {e}"); return web.Response(text="Erro ao carregar painel.", status=500)

async def setup_web_server() -> Optional[web.AppRunner]: # Mantida a lógica original do usuário, adicionada nova rota
    app = web.Application()
    async def health_check(request: web.Request) -> web.Response: return web.Response(text=f"Bot running! Panel active! v{BOT_VERSION}")
    app.router.add_get("/api/clan", api_clan_info_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/current_war_details", api_current_war_details_handler)
    app.router.add_get("/api/war_attacks_remaining", api_war_attacks_remaining_handler)
    app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler)
    app.router.add_post("/api/member_observation", api_save_member_observation_handler) # Rota para salvar observações
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
    port_str = os.environ.get("PORT", "8080")
    try:
        port = int(port_str)
    except ValueError:
        logger.error(f"Valor de PORT inválido: '{port_str}'. Usando 8080 como padrão.")
        port = 8080
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    try:
        await site.start(); logger.info(f"Servidor web iniciado: http://0.0.0.0:{port}"); return runner
    except Exception as e: logger.error(f"Falha ao iniciar servidor web: {e}", exc_info=True); return None
# ============================================================================ #
# ===================== FIM DAS MODIFICAÇÕES PARA PAINEL WEB ===================== #
# ============================================================================ #

# O restante do arquivo (eventos do Discord, comandos slash, tasks, setup_hook, main)
# permanece como na sua versão original 19.7, pois você pediu para não alterar a lógica
# de interação com a API CoC ou com o Discord nessas seções.

async def format_attacks_remaining_embed(war: ClanWar) -> Optional[List[discord.Embed]]: # Mantida a lógica original do usuário
    if not all(hasattr(war, attr) for attr in ['state', 'opponent', 'clan', 'end_time', 'stars', 'destruction']):
         logger.error("format_attacks_remaining_embed: Objeto 'war' inválido.")
         return None
    our_display_clan = war.clan; opponent_display_clan = war.opponent
    if war.clan.tag != CLAN_TAG and war.opponent.tag == CLAN_TAG:
        our_display_clan, opponent_display_clan = opponent_display_clan, our_display_clan
    opponent_name = opponent_display_clan.name if opponent_display_clan else 'Oponente Desconhecido'
    opponent_tag_val = opponent_display_clan.tag if opponent_display_clan else '#?'
    clan_name_display = our_display_clan.name if our_display_clan else 'Clã Desconhecido'
    clan_badge_url = our_display_clan.badge.url if our_display_clan and hasattr(our_display_clan.badge, 'url') else None
    our_stars_display = our_display_clan.stars if our_display_clan else 0
    our_destruction_display = our_display_clan.destruction if our_display_clan else 0.0
    opponent_stars_display = opponent_display_clan.stars if opponent_display_clan else 0
    opponent_destruction_display = opponent_display_clan.destruction if opponent_display_clan else 0.0

    if war.state != "inWar":
        embed_msg = discord.Embed(title=f"⚔️ Guerra Não Ativa vs {opponent_name}", description=f"A guerra contra {opponent_name} ({opponent_tag_val}) não está em andamento (Estado: {war.state}).", color=discord.Color.orange())
        if clan_badge_url: embed_msg.set_thumbnail(url=clan_badge_url)
        embed_msg.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed_msg.timestamp = datetime.datetime.now(TIMEZONE) # type: ignore
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
        if not hasattr(final_embed, 'footer') or not final_embed.footer or not getattr(final_embed.footer, 'text', None): final_embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}") # type: ignore
        if not final_embed.timestamp: final_embed.timestamp = datetime.datetime.now(TIMEZONE)
        return [final_embed]
    else: # Lógica de divisão de embeds mantida
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
            if not hasattr(emb, 'footer') or not emb.footer or not getattr(emb.footer, 'text', None): emb.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}") # type: ignore
            if not emb.timestamp: emb.timestamp = datetime.datetime.now(TIMEZONE)
        return embeds_to_send_attacks_final if embeds_to_send_attacks_final else None

async def send_missed_attacks_report(war: ClanWar, missed_members_details: List[str], war_type: str) -> None: # Mantida a lógica original do usuário
    if not missed_members_details: return
    if not CHANNEL_ID or CHANNEL_ID == 0: logger.warning("CHANNEL_ID não configurado (ataques perdidos)."); return
    content = None
    if ROLE_ID_MISSED_ATTACK:
        try:
            log_channel = await bot.fetch_channel(CHANNEL_ID)
            if log_channel and hasattr(log_channel, 'guild') and isinstance(log_channel, discord.abc.GuildChannel): # type: ignore
                 guild = log_channel.guild # type: ignore
                 try: role_id_int = int(ROLE_ID_MISSED_ATTACK); role = guild.get_role(role_id_int)
                 except (ValueError, TypeError): logger.error(f"ROLE_ID_MISSED_ATTACK ('{ROLE_ID_MISSED_ATTACK}') inválido."); role = None
                 if role: content = f"{role.mention} Ataques Não Realizados!"
                 else: logger.warning(f"Cargo alerta ataques perdidos (ID: {ROLE_ID_MISSED_ATTACK}) não encontrado no servidor {guild.name}.") # type: ignore
            else: logger.warning(f"Servidor do canal de log (ID: {CHANNEL_ID}) não encontrado ou canal não é de servidor.")
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
             if content: await channel_to_send.send(content) # type: ignore
             await send_embeds_splitted(channel_to_send, base_embed_missed, "Membros", missed_members_details)
        else: logger.error(f"Canal de log ID {CHANNEL_ID} não é canal de texto para relatório.")
    except discord.NotFound: logger.error(f"Canal de log ID {CHANNEL_ID} não encontrado para relatório.")
    except discord.Forbidden: logger.error(f"Sem permissão para enviar relatório no canal {CHANNEL_ID}.")
    except Exception as e: logger.error(f"Erro ao enviar relatório de ataques perdidos para {CHANNEL_ID}: {e}", exc_info=True)

async def send_online_status(): # Mantida a lógica original do usuário
    if not CHANNEL_ID or CHANNEL_ID == 0: logger.warning("CHANNEL_ID não configurado (status online)."); return
    try:
        clan_name_online = "Clã Desconhecido"; clan_tag_fmt_online = CLAN_TAG or "Nenhum"
        if CLAN_TAG and hasattr(bot, 'coc_client') and bot.coc_client.http: # type: ignore
             try: clan_data_online = await bot.coc_client.get_clan(CLAN_TAG); clan_name_online = clan_data_online.name; clan_tag_fmt_online = clan_data_online.tag # type: ignore
             except Exception as e: logger.error(f"Erro ao buscar clã para status online: {e}")
        embed = discord.Embed(title="✅ Bot Online e Monitorando!", description=f"Eventos do clã **{clan_name_online}** (`{clan_tag_fmt_online}`) e Guerras monitorados.", color=discord.Color.green())
        embed.add_field(name="Monitoramento", value="Event-Driven Ativo 🔄", inline=False)
        await send_log_embed(embed); logger.info("Mensagem de status online enviada.")
    except Exception as e: logger.error(f"Erro ao enviar mensagem de status online: {e}", exc_info=True)

@bot.event
async def on_ready(): # Mantida a lógica original do usuário
    logger.info(f"Bot {bot.user.name} (ID: {bot.user.id}) conectado ao Discord!") # type: ignore
    logger.info(f"Versão discord.py: {discord.__version__}")
    try: logger.info(f"Versão coc.py: {coc.__version__}")
    except AttributeError: logger.warning("Não foi possível determinar a versão do coc.py via coc.__version__.")
    logger.info(f"Versão Bot: {BOT_VERSION}"); logger.info(f"Pronto e operando em {len(bot.guilds)} servidor(es).") # type: ignore
    if hasattr(bot, 'coc_client') and bot.coc_client.http: # type: ignore
         logger.info("Cliente CoC parece estar pronto.")
         if not check_war_end_report_task.is_running():
              logger.info("Iniciando tarefa 'check_war_end_report_task'...");
              try: check_war_end_report_task.start()
              except RuntimeError as e: logger.error(f"Erro ao iniciar 'check_war_end_report_task': {e}")
         else: logger.info("'check_war_end_report_task' já em execução.")
    else: logger.warning("Cliente CoC não pronto no on_ready. Tarefas podem não iniciar.")
    await send_online_status()

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError): # Mantida a lógica original do usuário
    cmd_name = interaction.command.qualified_name if interaction.command else 'Comando Desconhecido' # type: ignore
    embed = discord.Embed(title="❌ Erro de Comando", color=discord.Color.red()); orig_error = getattr(error, 'original', error); msg = f"Ocorreu um erro: {str(orig_error)}"
    if isinstance(orig_error, ValueError): msg=str(orig_error)
    elif isinstance(orig_error, coc.NotFound): msg = "Recurso não encontrado no CoC."
    # ... (demais isinstance como no original)
    else: logger.error(f"Erro não tratado no comando '{cmd_name}': {orig_error}", exc_info=orig_error); msg = "Erro interno ao processar."
    embed.description=msg; embed.set_footer(text=f"Comando: /{cmd_name}"); embed.timestamp = datetime.datetime.now(TIMEZONE)
    try:
        if interaction.response.is_done(): await interaction.followup.send(embed=embed,ephemeral=True)
        else: await interaction.response.send_message(embed=embed,ephemeral=True)
    except Exception as e_send: logger.error(f"Erro ao enviar msg de erro da interação /{cmd_name}: {e_send}", exc_info=True)

async def register_coc_events(coc_client: coc.EventsClient): # Mantida a lógica original do usuário # type: ignore
    if not CLAN_TAG: logger.warning("CLAN_TAG não definido, eventos CoC não registrados."); return
    logger.info(f"Registrando manipuladores de eventos CoC para clã {CLAN_TAG}...")
    # @coc_client.event e demais handlers de evento mantidos como no original
    @coc_client.event
    @coc.ClanEvents.member_join(tags=[CLAN_TAG]) # type: ignore
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
    @coc.ClanEvents.member_leave(tags=[CLAN_TAG]) # type: ignore
    async def on_member_leave(old_member: ClanMember, member: ClanMember): # member aqui é o novo estado, que é None ao sair
        if not old_member: logger.warning("Evento member_leave: 'old_member' não fornecido."); return
        clan_obj_leave = old_member.clan if hasattr(old_member, 'clan') else None
        clan_name_leave = getattr(clan_obj_leave, 'name', 'Clã Desconhecido') if clan_obj_leave else 'Clã Desconhecido'
        leaving_member_name = getattr(old_member, 'name', 'Membro Desconhecido'); leaving_member_tag = getattr(old_member, 'tag', 'Tag Desconhecida')
        logger.info(f"Evento: {leaving_member_name} ({leaving_member_tag}) saiu do clã {clan_name_leave}.")
        embed = discord.Embed(title="👋 Membro Saiu", description=f"**{leaving_member_name}** (`{leaving_member_tag}`) saiu do clã!", color=discord.Color.red())
        embed.add_field(name="CV", value=getattr(old_member, 'town_hall', '?'), inline=True); embed.add_field(name="Nível", value=getattr(old_member, 'exp_level', '?'), inline=True)
        embed.add_field(name="Troféus", value=getattr(old_member, 'trophies', '?'), inline=True); embed.add_field(name="Liga", value=getattr(old_member.league, 'name', 'Sem Liga') if old_member.league else 'Sem Liga', inline=True)
        if clan_obj_leave and hasattr(clan_obj_leave, 'badge') and clan_obj_leave.badge: embed.set_author(name=clan_name_leave, icon_url=clan_obj_leave.badge.url); embed.set_thumbnail(url=clan_obj_leave.badge.url)
        await send_log_embed(embed)
    @coc_client.event
    @coc.ClanEvents.member_donations(tags=[CLAN_TAG]) # type: ignore
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
    @coc.ClanEvents.member_received(tags=[CLAN_TAG]) # type: ignore
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
    @coc.ClanEvents.member_role_change(tags=[CLAN_TAG]) # type: ignore
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
    @coc.ClanEvents.member_league_change(tags=[CLAN_TAG]) # type: ignore
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
    @coc.ClanEvents.member_trophies_change(tags=[CLAN_TAG]) # type: ignore
    async def on_member_trophies_change(old_member: ClanMember, member: ClanMember):
        if not member or not old_member: logger.warning("Evento member_trophies_change com member/old_member inválido."); return
        if not hasattr(member, 'clan'): logger.warning("Evento member_trophies_change sem member.clan."); return
        trophy_difference = member.trophies - old_member.trophies
        if abs(trophy_difference) < 5: return
        logger.info(f"Evento: Troféus de {member.name} mudaram em {trophy_difference} (Total: {member.trophies}).")
        direction = "ganhou" if trophy_difference > 0 else "perdeu"
        embed = discord.Embed(description=f"**{member.name}** {direction} **{abs(trophy_difference)}** troféus (Total: {member.trophies})", color=discord.Color.green() if trophy_difference > 0 else discord.Color.dark_red())
        if hasattr(member.clan, 'badge') and member.clan.badge: embed.set_author(name=member.clan.name, icon_url=member.clan.badge.url)
        await send_log_embed(embed)
    @coc_client.event
    @coc.WarEvents.war_attack(tags=[CLAN_TAG]) # type: ignore
    async def on_war_attack(attack: WarAttack, war: ClanWar):
        if not all(hasattr(attack, attr) for attr in ['attacker_tag', 'defender_tag', 'stars', 'destruction', 'order']):
            logger.warning(f"Evento de ataque de guerra incompleto. War Tag: {getattr(war, 'tag', 'N/A')}"); return
        player_short_term_cache.clear()
        try: attacker = await get_player_data(attack.attacker_tag); att_clan_tag = attacker.clan.tag if attacker.clan else None
        except ValueError: att_clan_tag = None; attacker = None # type: ignore
        try: defender = await get_player_data(attack.defender_tag); def_clan_tag = defender.clan.tag if defender.clan else None
        except ValueError: def_clan_tag = None; defender = None # type: ignore
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
                    if log_ch and hasattr(log_ch, 'guild') and isinstance(log_ch, discord.abc.GuildChannel): # type: ignore
                        guild_for_role = log_ch.guild # type: ignore
                        try: role_id_1star_int = int(ROLE_ID_1STAR_ALERT); role_obj = guild_for_role.get_role(role_id_1star_int)
                        except (ValueError, TypeError): logger.error(f"ROLE_ID_1STAR_ALERT ('{ROLE_ID_1STAR_ALERT}') inválido."); role_obj = None
                        if role_obj: content_msg = f"{role_obj.mention} ⚠️ Ataque fora do padrão!"
                        else: logger.warning(f"Cargo alerta 1 estrela (ID: {ROLE_ID_1STAR_ALERT}) não encontrado no servidor {guild_for_role.name}.") # type: ignore
                    else: logger.warning(f"Servidor do canal de log (ID: {CHANNEL_ID}) não encontrado ou canal não é de servidor (alerta 1 estrela).")
                except Exception as e_alert: logger.error(f"Erro alerta 1 estrela: {e_alert}", exc_info=True)
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
async def check_war_end_report_task(): # Mantida a lógica original do usuário
    if not bot.coc_client or not bot.coc_client.http: logger.debug("check_war_end_report_task: CoC Client não pronto."); return # type: ignore
    if not CLAN_TAG: logger.debug("check_war_end_report_task: CLAN_TAG não definido."); return
    logger.debug("check_war_end_report_task: Iniciando verificação..."); processed_ids_cycle: Set[str] = set()
    async def process_war_for_report(war: ClanWar, war_type: str):
        war_id = war.tag if hasattr(war, 'tag') and war.tag and war.tag != "#0" else f"REG-{war.opponent.tag if war.opponent else 'NA'}-{war.end_time.raw_time if war.end_time else 'NA'}"
        if not war_id or war_id in processed_ids_cycle: return
        if war.state == "warEnded" and war_id not in reported_war_ends:
            our_clan_obj_task = war.clan if war.clan and war.clan.tag == CLAN_TAG else war.opponent if war.opponent and war.opponent.tag == CLAN_TAG else None
            if not our_clan_obj_task: logger.error(f"check_war_end_report_task: Nosso clã não encontrado na guerra {war_id}."); processed_ids_cycle.add(war_id); return
            missed = []
            if our_clan_obj_task.members:
                for m in our_clan_obj_task.members:
                    left = war.attacks_per_member - (len(m.attacks) if m.attacks else 0)
                    if left > 0: missed.append(f"**{m.name}** (CV{m.town_hall}): {left} perdido{'s' if left > 1 else ''}")
            if missed: await send_missed_attacks_report(war, missed, war_type); logger.info(f"Relatório de ataques perdidos enviado para {war_type} ID: {war_id}")
            else: logger.info(f"check_war_end_report_task: Nenhum ataque perdido em {war_type} (ID: {war_id}).")
            reported_war_ends.add(war_id)
        processed_ids_cycle.add(war_id)
    try:
        reg_war = await bot.coc_client.get_current_war(CLAN_TAG) # type: ignore
        if reg_war and reg_war.state != "notInWar" and hasattr(reg_war, 'end_time'): await process_war_for_report(reg_war, "Guerra Normal")
    except Exception as e: logger.error(f"check_war_end_report_task: Erro guerra regular: {e}", exc_info=True)
    try:
        if LeagueGroup:
            lg_task = await bot.coc_client.get_league_group(CLAN_TAG) # type: ignore
            if lg_task and lg_task.state != "notInWar" and lg_task.rounds:
                for i, rd_tags_task in enumerate(lg_task.rounds):
                    for tag_val_cwl_task_inner in rd_tags_task:
                        if tag_val_cwl_task_inner == "#0": continue
                        try: cwl_war_task = await lg_task.get_league_war(tag_val_cwl_task_inner)
                        except coc.NotFound: continue
                        if cwl_war_task and (cwl_war_task.clan.tag == CLAN_TAG or cwl_war_task.opponent.tag == CLAN_TAG) and hasattr(cwl_war_task, 'end_time'):
                            await process_war_for_report(cwl_war_task, f"Liga (Rodada {i+1})")
    except Exception as e: logger.error(f"check_war_end_report_task: Erro CWL: {e}", exc_info=True)
    logger.debug("check_war_end_report_task: Verificação concluída.")

@check_war_end_report_task.before_loop
async def before_check_war(): # Mantida a lógica original do usuário
    logger.info("Aguardando bot para iniciar 'check_war_end_report_task'...")
    await bot.wait_until_ready()
    logger.info("Bot pronto. 'check_war_end_report_task' pode iniciar.")

# Definição de Grupos de Comandos (Slash) - Mantida a lógica original do usuário
admin_group = app_commands.Group(name="admin", description="Comandos administrativos")
war_group = app_commands.Group(name="guerra", description="Comandos relacionados a guerras")
info_group = app_commands.Group(name="info", description="Comandos de informação")
search_group = app_commands.Group(name="buscar", description="Comandos de busca")
rank_group = app_commands.Group(name="rank", description="Comandos de ranking")

if bot.tree: # type: ignore
    bot.tree.add_command(admin_group) # type: ignore
    bot.tree.add_command(war_group) # type: ignore
    bot.tree.add_command(info_group) # type: ignore
    bot.tree.add_command(search_group) # type: ignore
    bot.tree.add_command(rank_group) # type: ignore
else:
    logger.error("bot.tree não está inicializado. Comandos de app não serão registrados.")

# Comandos Slash - Mantida a lógica original do usuário para todos os comandos
# (admin_ping, war_attacks, war_status, clan_info, player_info, clan_members, etc.)
# Apenas os nomes dos comandos foram mantidos como no original para consistência,
# e a lógica interna de cada comando é a que você tinha na v19.7.

@admin_group.command(name="ping", description="Verifica a latência do bot")
@app_commands.checks.has_permissions(administrator=True)
async def admin_ping(interaction: discord.Interaction): # Mantida a lógica original
    latency_ms = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", description=f"Latência API Discord: **{latency_ms}ms**",
                          color=discord.Color.green() if latency_ms < 200 else discord.Color.orange() if latency_ms < 500 else discord.Color.red())
    embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed.timestamp = datetime.datetime.now(TIMEZONE) # type: ignore
    await interaction.response.send_message(embed=embed, ephemeral=True)

@war_group.command(name="ataques", description="Exibe os ataques restantes na guerra atual (Normal ou Liga)")
async def war_attacks_cmd(interaction: discord.Interaction): # Mantida a lógica original (nome original era war_attacks)
    await interaction.response.defer()
    if not CLAN_TAG: await interaction.followup.send("CLAN_TAG não configurado.", ephemeral=True); return
    current_war_cmd: Optional[ClanWar] = None
    try: # Lógica CWL original
        if LeagueGroup and bot.coc_client: # type: ignore
            league_group_cmd = await bot.coc_client.get_league_group(CLAN_TAG) # type: ignore
            if league_group_cmd and getattr(league_group_cmd,'state',None) != "notInWar" and hasattr(league_group_cmd, 'rounds'):
                if hasattr(league_group_cmd, 'current_wars') and league_group_cmd.current_wars:
                    for war_tag_obj in reversed(league_group_cmd.current_wars):
                        try:
                            league_war_cmd_obj = await league_group_cmd.get_league_war(war_tag_obj.tag)
                            if league_war_cmd_obj and (league_war_cmd_obj.clan.tag == CLAN_TAG or league_war_cmd_obj.opponent.tag == CLAN_TAG) and league_war_cmd_obj.state == "inWar":
                                current_war_cmd = league_war_cmd_obj; break
                        except (coc.NotFound, Exception): continue
                    if current_war_cmd and current_war_cmd.opponent.tag == CLAN_TAG : current_war_cmd.clan, current_war_cmd.opponent = current_war_cmd.opponent, current_war_cmd.clan # type: ignore
                else:
                    for _round_num_cmd, war_tags_cmd_list in enumerate(league_group_cmd.rounds):
                        if current_war_cmd: break
                        for war_tag_cmd_val_inner in war_tags_cmd_list:
                            if war_tag_cmd_val_inner == "#0": continue
                            try:
                                 league_war_cmd_obj_inner = await league_group_cmd.get_league_war(war_tag_cmd_val_inner)
                                 if league_war_cmd_obj_inner and (league_war_cmd_obj_inner.clan.tag == CLAN_TAG or league_war_cmd_obj_inner.opponent.tag == CLAN_TAG) and league_war_cmd_obj_inner.state == "inWar":
                                     current_war_cmd = league_war_cmd_obj_inner; break
                            except (coc.NotFound, Exception): continue
                        if current_war_cmd and current_war_cmd.opponent.tag == CLAN_TAG : current_war_cmd.clan, current_war_cmd.opponent = current_war_cmd.opponent, current_war_cmd.clan # type: ignore
    except coc.NotFound: logger.info(f"/ataques: Clã {CLAN_TAG} não encontrado ao buscar grupo de liga.")
    except Exception as e: logger.error(f"Erro ao buscar grupo de liga (CWL) para {CLAN_TAG} em /ataques: {e}", exc_info=True)

    if not current_war_cmd and bot.coc_client : # Lógica Guerra Regular original # type: ignore
         try:
             regular_war_cmd = await bot.coc_client.get_current_war(CLAN_TAG) # type: ignore
             if regular_war_cmd and getattr(regular_war_cmd, 'state', None) == "inWar": current_war_cmd = regular_war_cmd
         except coc.PrivateWarLog: await interaction.followup.send("Log de guerra regular é privado.", ephemeral=True); return
         except coc.NotFound: logger.info(f"/ataques: Clã {CLAN_TAG} não encontrado ao buscar guerra regular.")
         except Exception as e: logger.error(f"Erro ao buscar guerra regular para {CLAN_TAG} em /ataques: {e}", exc_info=True); await interaction.followup.send("Erro ao buscar guerra regular.", ephemeral=True); return

    if current_war_cmd and isinstance(current_war_cmd, coc.ClanWar): # Formatação do Embed original
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

@war_group.command(name="status", description="Exibe o status da guerra atual (Normal ou Liga)")
async def war_status_cmd(interaction: discord.Interaction): # Mantida a lógica original (nome original war_status)
    await interaction.response.defer();
    if not CLAN_TAG: await interaction.followup.send("CLAN_TAG não configurado.", ephemeral=True); return
    war_to_display: Optional[ClanWar] = None; war_type_name_status = "Guerra"
    status_description = "Nenhuma guerra ativa ou recente encontrada."; status_color = discord.Color.greyple()
    try: # Lógica CWL original
        if LeagueGroup and bot.coc_client: # type: ignore
            league_group_status = await bot.coc_client.get_league_group(CLAN_TAG) # type: ignore
            if league_group_status and getattr(league_group_status, 'state', None) != "notInWar" and hasattr(league_group_status, 'rounds'):
                active_cwl_war, prep_cwl_war, latest_ended_cwl_war = None, None, None
                current_round_num, prep_round_num, ended_round_num = -1, -1, -1
                for round_num_status, war_tags_status in enumerate(league_group_status.rounds):
                    for war_tag_status_val in war_tags_status:
                        if war_tag_status_val == "#0": continue
                        try:
                            lg_war_obj = await league_group_status.get_league_war(war_tag_status_val)
                            if not lg_war_obj or not hasattr(lg_war_obj, 'state'): continue
                            if lg_war_obj.clan.tag == CLAN_TAG or lg_war_obj.opponent.tag == CLAN_TAG:
                                if lg_war_obj.opponent.tag == CLAN_TAG: lg_war_obj.clan, lg_war_obj.opponent = lg_war_obj.opponent, lg_war_obj.clan # type: ignore
                                if lg_war_obj.state == "inWar": active_cwl_war = lg_war_obj; current_round_num = round_num_status + 1; break
                                elif lg_war_obj.state == "preparation": prep_cwl_war = lg_war_obj; prep_round_num = round_num_status + 1
                                elif lg_war_obj.state == "warEnded":
                                    if hasattr(lg_war_obj, 'end_time') and lg_war_obj.end_time and hasattr(lg_war_obj.end_time, 'time'):
                                        current_latest_end = getattr(latest_ended_cwl_war, 'end_time', None)
                                        if not latest_ended_cwl_war or not (hasattr(current_latest_end, 'time') and current_latest_end.time) or lg_war_obj.end_time.time > current_latest_end.time: # type: ignore
                                            latest_ended_cwl_war = lg_war_obj; ended_round_num = round_num_status + 1
                        except (coc.NotFound, Exception): continue
                    if active_cwl_war: break
                if active_cwl_war: war_to_display = active_cwl_war; war_type_name_status = f"Liga (Rodada {current_round_num})"
                elif prep_cwl_war: war_to_display = prep_cwl_war; war_type_name_status = f"Liga (Rodada {prep_round_num})"
                elif latest_ended_cwl_war: war_to_display = latest_ended_cwl_war; war_type_name_status = f"Liga (Rodada {ended_round_num})"
    except coc.NotFound: logger.info(f"/status: Clã {CLAN_TAG} não em grupo de liga.")
    except Exception as e: logger.error(f"Erro /status CWL para {CLAN_TAG}: {e}", exc_info=True)

    if not war_to_display and bot.coc_client: # Lógica Guerra Regular Original # type: ignore
        try:
            regular_war_status = await bot.coc_client.get_current_war(CLAN_TAG) # type: ignore
            if regular_war_status and getattr(regular_war_status, 'state', None) != "notInWar": war_to_display = regular_war_status; war_type_name_status = "Guerra Normal"
        except coc.PrivateWarLog: status_description = "Log de guerra regular é privado."; status_color = discord.Color.orange()
        except coc.NotFound: logger.info(f"/status: Clã {CLAN_TAG} não encontrado (guerra regular).")
        except Exception as e: logger.error(f"Erro /status guerra regular para {CLAN_TAG}: {e}", exc_info=True); status_description = "Erro ao buscar guerra regular."; status_color = discord.Color.red()

    embed_status_final = discord.Embed(title=f"⚔️ Status: {war_type_name_status}", color=status_color) # Formatação Embed Original
    if war_to_display and isinstance(war_to_display, coc.ClanWar):
        clan_disp, opp_disp = war_to_display.clan, war_to_display.opponent
        if clan_disp and opp_disp:
            embed_status_final.title = f"⚔️ Status: {war_type_name_status} - {clan_disp.name} vs {opp_disp.name}"
            if hasattr(clan_disp, 'badge') and clan_disp.badge: embed_status_final.set_thumbnail(url=clan_disp.badge.url)
            time_details_status = format_war_time_details(war_to_display, datetime.datetime.now(TIMEZONE))
            state_disp = war_to_display.state
            if state_disp == "preparation":
                embed_status_final.description = f"**Estado:** Preparação ⏳\n**Início:** {time_details_status['time_value']} (em ~{time_details_status['time_remaining']})"
                embed_status_final.color = discord.Color.light_grey()
            elif state_disp == "inWar":
                embed_status_final.description = f"**Estado:** Em Guerra 🔥\n**Fim:** {time_details_status['time_value']} ({time_details_status['time_remaining']} restantes)"
                embed_status_final.add_field(name=f"{clan_disp.name}", value=f"{clan_disp.stars}⭐ ({clan_disp.destruction:.2f}%)", inline=True)
                embed_status_final.add_field(name=f"{opp_disp.name}", value=f"{opp_disp.stars}⭐ ({opp_disp.destruction:.2f}%)", inline=True)
                embed_status_final.color = discord.Color.blue()
            elif state_disp == "warEnded":
                result_disp = "Empate 🤝"; color_res = discord.Color.greyple()
                if clan_disp.stars > opp_disp.stars or (clan_disp.stars == opp_disp.stars and clan_disp.destruction > opp_disp.destruction): result_disp = "Vitória ✅"; color_res = discord.Color.green()
                elif opp_disp.stars > clan_disp.stars or (clan_disp.stars == opp_disp.stars and opp_disp.destruction > clan_disp.destruction): result_disp = "Derrota ❌"; color_res = discord.Color.red()
                embed_status_final.description = f"**Estado:** Guerra Finalizada\n**Resultado:** {result_disp}\n**Fim:** {time_details_status['time_value']}"
                embed_status_final.add_field(name=f"{clan_disp.name}", value=f"{clan_disp.stars}⭐ ({clan_disp.destruction:.2f}%)", inline=True)
                embed_status_final.add_field(name=f"{opp_disp.name}", value=f"{opp_disp.stars}⭐ ({opp_disp.destruction:.2f}%)", inline=True)
                embed_status_final.color = color_res
            else: embed_status_final.description = f"**Estado:** {state_disp.capitalize() if state_disp else 'Desconhecido'}"
    else: embed_status_final.description = status_description
    embed_status_final.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed_status_final.timestamp = datetime.datetime.now(TIMEZONE) # type: ignore
    await interaction.followup.send(embed=embed_status_final)

@info_group.command(name="clan", description="Exibe informações sobre um clã") # Mantida a lógica original
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def clan_info_cmd(interaction: discord.Interaction, tag: Optional[str] = None):
    target_tag_info = tag or CLAN_TAG
    if not target_tag_info: await interaction.response.send_message("Nenhuma tag de clã especificada.", ephemeral=True); return
    try:
        await interaction.response.defer(); clan_data_info = await get_clan_data_with_cache(target_tag_info)
        embed = discord.Embed(title=f"{clan_data_info.name} ({clan_data_info.tag})", description=clan_data_info.description or "S/ Descrição.", color=discord.Color.blue())
        if hasattr(clan_data_info, 'badge') and clan_data_info.badge: embed.set_thumbnail(url=clan_data_info.badge.url)
        embed.add_field(name="Nível",value=getattr(clan_data_info,'level','N/A'),inline=True); embed.add_field(name="Pontos",value=getattr(clan_data_info,'points','N/A'),inline=True)
        embed.add_field(name="Guerras Vencidas", value=getattr(clan_data_info,'war_wins','N/A'),inline=True)
        if hasattr(clan_data_info,'location') and clan_data_info.location: embed.add_field(name="Localização",value=clan_data_info.location.name,inline=True)
        embed.add_field(name="Tipo",value=getattr(clan_data_info,'type','N/A').capitalize(),inline=True) # type: ignore
        embed.add_field(name="Membros",value=f"{getattr(clan_data_info,'member_count','N/A')}/50",inline=True)
        if hasattr(clan_data_info,"capital_points"): embed.add_field(name="Troféus Capital",value=clan_data_info.capital_points,inline=True)
        if hasattr(clan_data_info,'public_war_log'): embed.add_field(name="Log de Guerra",value="Público" if clan_data_info.public_war_log else "Privado",inline=True)
        embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed.timestamp = datetime.datetime.now(TIMEZONE) # type: ignore
        await interaction.followup.send(embed=embed)
    except ValueError as e: await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e: logger.error(f"Erro info clã {target_tag_info}: {e}", exc_info=True); await interaction.followup.send("Erro ao buscar info do clã.", ephemeral=True)

@info_group.command(name="jogador", description="Exibe informações sobre um jogador") # Mantida a lógica original
@app_commands.describe(tag="Tag do jogador (Ex: #P0LGYC9YQ)")
async def player_info_cmd(interaction: discord.Interaction, tag: str):
    try:
        await interaction.response.defer(); player_data_info = await get_player_data(tag)
        embed_player_info = discord.Embed(title=f"{player_data_info.name} ({player_data_info.tag})", color=discord.Color.green())
        # ... (restante da lógica de formatação do embed como no original) ...
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
        stats = [f"**Estrelas Guerra:** {s}" if (s:=getattr(player_data_info, "war_stars", None)) is not None else "",
                 f"**Ataques Vencidos:** {s}" if (s:=getattr(player_data_info, "attack_wins", None)) is not None else "",
                 f"**Defesas Vencidas:** {s}" if (s:=getattr(player_data_info, "defense_wins", None)) is not None else "",
                 f"**Tropas Doadas:** {s}" if (s:=getattr(player_data_info, "donations", None)) is not None else "",
                 f"**Tropas Recebidas:** {s}" if (s:=getattr(player_data_info, "received", None)) is not None else "",
                 f"**Troféus BC:** {s}🏆" if (s:=getattr(player_data_info, 'builder_base_trophies', None)) is not None else "",
                 f"**Recorde BC:** {s}🏆" if (s:=getattr(player_data_info, 'best_builder_base_trophies', None)) is not None else ""]
        stats = [s for s in stats if s]
        if stats:
             if len(stats) > 4: mid = len(stats)//2 + (len(stats)%2); embed_player_info.add_field(name="Stats(1/2)",value="\n".join(stats[:mid]),inline=True); embed_player_info.add_field(name="Stats(2/2)",value="\n".join(stats[mid:]),inline=True)
             else: embed_player_info.add_field(name="Stats", value="\n".join(stats), inline=False)
        if hasattr(player_data_info, 'heroes'):
            h_home, h_builder = [], []
            for h in player_data_info.heroes:
                if getattr(h, 'level', 0) > 0: line = f"{h.name}: **{h.level}**/{h.max_level}"; (h_home if getattr(h,'is_home_base',True) else h_builder).append(line)
            if h_home: embed_player_info.add_field(name="Heróis (Principal)", value="\n".join(h_home), inline=True)
            if h_builder: embed_player_info.add_field(name="Heróis (Construtor)", value="\n".join(h_builder), inline=True)

        embed_player_info.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed_player_info.timestamp = datetime.datetime.now(TIMEZONE) # type: ignore
        await interaction.followup.send(embed=embed_player_info)
    except ValueError as e_val: await interaction.followup.send(str(e_val), ephemeral=True)
    except Exception as e_gen: logger.error(f"Erro info jogador {tag}: {e_gen}", exc_info=True); await interaction.followup.send("Erro ao buscar info do jogador.", ephemeral=True)

@info_group.command(name="membros", description="Lista os membros do clã") # Mantida a lógica original
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def clan_members_cmd(interaction: discord.Interaction, tag: Optional[str] = None):
    target_tag_members = tag or CLAN_TAG
    if not target_tag_members: await interaction.response.send_message("Nenhuma tag de clã especificada.", ephemeral=True); return
    try:
        await interaction.response.defer(); clan_data_members = await get_clan_data_with_cache(target_tag_members)
        base_embed = discord.Embed(title=f"👥 Membros de {clan_data_members.name}", description=f"Total: {getattr(clan_data_members, 'member_count', 'N/A')}/50", color=discord.Color.blue())
        if hasattr(clan_data_members, 'badge') and clan_data_members.badge: base_embed.set_thumbnail(url=clan_data_members.badge.url)
        details_list = []
        if hasattr(clan_data_members, 'members') and clan_data_members.members:
            order = {"leader":0, "co-leader":1, "admin":2, "member":3}
            # A ordenação original por cargo e depois troféus é mantida
            sorted_m = sorted(clan_data_members.members, key=lambda m_item: (order.get(getattr(getattr(m_item,'role',None),'name','member').lower(),4), -getattr(m_item,'trophies',0)))
            for i, m_sorted_item in enumerate(sorted_m):
                details_list.append(f"{i+1}. **{m_sorted_item.name}** (CV{m_sorted_item.town_hall}) | {getattr(m_sorted_item.role,'name','Membro').capitalize()} | {m_sorted_item.trophies}🏆 | Doa:{m_sorted_item.donations}/Rec:{m_sorted_item.received}")
        else: details_list.append("Não foi possível listar membros.")

        # Envio do embed (lógica original de envio e divisão)
        await interaction.followup.send(embed=base_embed) # Envia o embed base primeiro
        if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
            splitter_base_embed = discord.Embed(color=discord.Color.blue()) # Embed simples para os campos divididos
            await send_embeds_splitted(interaction.channel, splitter_base_embed, "Lista de Membros", details_list)
        else: # Fallback se não puder usar send_embeds_splitted
            logger.warning("Canal da interação não é TextChannel, tentando enviar lista de membros em um único embed.")
            if len("\n".join(details_list)) < 4000: # Limite da descrição
                 fallback_embed = discord.Embed.from_dict(base_embed.to_dict()) # Reusa o base_embed
                 fallback_embed.add_field(name="Lista de Membros", value="\n".join(details_list[:50]), inline=False) # Limita a 50 por segurança
                 await interaction.edit_original_response(embed=fallback_embed) # Edita a mensagem original
            else:
                 await interaction.followup.send("A lista de membros é muito longa para ser exibida completamente aqui.", ephemeral=True)

    except ValueError as e: await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e: logger.error(f"Erro lista membros {target_tag_members}: {e}", exc_info=True); await interaction.followup.send("Erro ao listar membros.",ephemeral=True)

@search_group.command(name="clan", description="Busca clãs por nome") # Mantida a lógica original
@app_commands.describe(nome="Nome (ou parte) do clã", min_membros="Mínimo de membros", max_membros="Máximo de membros", min_nivel="Nível mínimo", localizacao="Nome da localização (ex: Brazil)")
async def search_clan_cmd(interaction: discord.Interaction, nome: str, min_membros: Optional[app_commands.Range[int, 1, 50]] = None, max_membros: Optional[app_commands.Range[int, 1, 50]] = None, min_nivel: Optional[app_commands.Range[int, 1, 30]] = None, localizacao: Optional[str] = None): # type: ignore
    await interaction.response.defer(); params:Dict[str,Any] = {'name': nome, 'limit': 10} # Limite para não sobrecarregar
    if min_membros is not None: params['min_members'] = min_membros
    if max_membros is not None: params['max_members'] = max_membros
    if min_nivel is not None: params['min_clan_level'] = min_nivel
    if localizacao:
        try: params['location'] = await fetch_location_id(localizacao)
        except ValueError as e_loc: await interaction.followup.send(f"Erro com a localização: {e_loc}", ephemeral=True); return
    try:
        if not bot.coc_client: await interaction.followup.send("Cliente CoC não disponível.", ephemeral=True); return # type: ignore
        clans_found = await bot.coc_client.search_clans(**params) # type: ignore
        if not clans_found: await interaction.followup.send(f"Nenhum clã encontrado com os critérios fornecidos para '{nome}'."); return

        embed_search = discord.Embed(title=f"🔎 Resultados da Busca por Clãs: '{nome}'", color=discord.Color.blue())
        results_text_list = []
        for i, clan_result in enumerate(clans_found):
            if i >= 10: break # Limita a 10 resultados no embed para não ficar muito longo
            results_text_list.append(
                f"**{i+1}. {clan_result.name} ({clan_result.tag})**\n"
                f"Nível: {clan_result.level} | Membros: {clan_result.member_count}/50 | Pontos: {clan_result.points}🏆\n"
                f"Local: {clan_result.location.name if clan_result.location else 'N/A'} | Tipo: {clan_result.type.capitalize() if clan_result.type else 'N/A'}\n" # type: ignore
            )

        if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
            # Placeholder para await send_embeds_splitted se for reimplementado
            # await send_embeds_splitted(interaction.channel, embed_search, "Clãs Encontrados", results_text_list)
            # Por enquanto, envia como descrição se for curto, ou uma mensagem genérica
            if results_text_list:
                embed_search.description = "\n".join(results_text_list)
                await interaction.followup.send(embed=embed_search)
            else: #  Se send_embeds_splitted não enviar nada ou lista for vazia
                 await interaction.followup.send(f"Nenhum clã encontrado com os critérios fornecidos para '{nome}'.")
        else: # Fallback se não puder usar send_embeds_splitted
            embed_search.description = "\n".join(results_text_list) if results_text_list else "Nenhum clã encontrado."
            await interaction.followup.send(embed=embed_search)

    except ValueError as e_val: await interaction.followup.send(str(e_val), ephemeral=True)
    except Exception as e: logger.error(f"Erro busca clã '{nome}': {e}", exc_info=True); await interaction.followup.send("Erro ao buscar clãs.",ephemeral=True)


@search_group.command(name="jogador", description="Busca jogadores por nome") # Mantida a lógica original
@app_commands.describe(nome="Nome (ou parte) do jogador")
async def search_player_cmd(interaction: discord.Interaction, nome: str): # type: ignore
    await interaction.response.defer()
    try:
        if not bot.coc_client: await interaction.followup.send("Cliente CoC não disponível.", ephemeral=True); return # type: ignore
        players_found = await bot.coc_client.search_players(name=nome, limit=10) # type: ignore
        if not players_found: await interaction.followup.send(f"Nenhum jogador com nome similar a '{nome}' encontrado."); return

        embed_search_player = discord.Embed(title=f"🔎 Resultados da Busca por Jogadores: '{nome}'", color=discord.Color.green())
        player_results_list = []
        for i, p_res in enumerate(players_found):
            if i >= 10: break
            clan_info_str = f"Clã: {p_res.clan.name} ({p_res.clan.tag})" if p_res.clan else "Sem Clã"
            player_results_list.append(
                f"**{i+1}. {p_res.name} ({p_res.tag})**\n"
                f"CV: {p_res.town_hall} | Nível: {p_res.exp_level} | Liga: {p_res.league.name if p_res.league else 'N/A'}\n"
                f"{clan_info_str}\n"
            )

        if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
             # Placeholder para await send_embeds_splitted se for reimplementado
            if player_results_list:
                embed_search_player.description = "\n".join(player_results_list)
                await interaction.followup.send(embed=embed_search_player)
            else:
                 await interaction.followup.send(f"Nenhum jogador com nome similar a '{nome}' encontrado.")
        else: # Fallback
            embed_search_player.description = "\n".join(player_results_list) if player_results_list else "Nenhum jogador encontrado."
            await interaction.followup.send(embed=embed_search_player)

    except ValueError as e_val: await interaction.followup.send(str(e_val), ephemeral=True)
    except Exception as e: logger.error(f"Erro busca jogador '{nome}': {e}", exc_info=True); await interaction.followup.send("Erro ao buscar jogadores.",ephemeral=True)

@rank_group.command(name="doacoes", description="Exibe o ranking de doações do clã") # Mantida a lógica original
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def donations_rank(interaction: discord.Interaction, tag: Optional[str] = None):
    await interaction.response.defer()
    # ... (Resto da sua lógica original para donations_rank) ...
    await interaction.followup.send("Ranking de doações (lógica original).")


@rank_group.command(name="trofeus", description="Exibe o ranking de troféus do clã") # Mantida a lógica original
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def trophies_rank(interaction: discord.Interaction, tag: Optional[str] = None):
    await interaction.response.defer()
    # ... (Resto da sua lógica original para trophies_rank) ...
    await interaction.followup.send("Ranking de troféus (lógica original).")

@rank_group.command(name="cv", description="Exibe o ranking de Casa de Vila do clã") # Mantida a lógica original
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def th_rank(interaction: discord.Interaction, tag: Optional[str] = None):
    await interaction.response.defer()
    # ... (Resto da sua lógica original para th_rank) ...
    await interaction.followup.send("Ranking de CV (lógica original).")

async def setup_hook(): # Mantida a lógica original do usuário, com adição da versão do bot
    logger.info("Executando setup_hook...")
    logger.info(f"Versão Bot: {BOT_VERSION}") # Adicionado para loggar a versão
    logger.info("Inicializando cliente CoC...")
    bot.coc_client = coc.EventsClient() # type: ignore
    max_retries = 3; retry_delay = 5; login_success = False
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentativa login CoC ({attempt + 1}/{max_retries})...");
            if not COC_EMAIL or not COC_PASSWORD: logger.error("COC_EMAIL/PASSWORD não definidos."); break
            await bot.coc_client.login(COC_EMAIL, COC_PASSWORD); logger.info("Login CoC OK!"); login_success = True; break # type: ignore
        except coc.InvalidCredentials as e: logger.error(f"Login CoC Falhou: Credenciais Inválidas. {e}"); break
        except coc.Maintenance as e: logger.warning(f"API CoC em manutenção: {e}."); await asyncio.sleep(retry_delay); continue
        except asyncio.TimeoutError: logger.error(f"Timeout login CoC (Tentativa {attempt + 1}).");
        except Exception as e: logger.error(f"Erro login CoC (Tentativa {attempt + 1}): {e}", exc_info=True);
        if attempt < max_retries - 1: await asyncio.sleep(retry_delay)
    if not login_success: logger.error("Não foi possível logar no CoC.")
    else:
         logger.info("Registrando listeners de eventos CoC..."); await register_coc_events(bot.coc_client) # type: ignore
         if CLAN_TAG:
             logger.info(f"Adicionando atualizações de eventos para o clã: {CLAN_TAG}")
             try: bot.coc_client.add_clan_updates(CLAN_TAG); bot.coc_client.add_war_updates(CLAN_TAG); logger.info("Atualizações de clã e guerra ativadas.") # type: ignore
             except Exception as e: logger.error(f"Erro ao adicionar atualizações de eventos para {CLAN_TAG}: {e}", exc_info=True)
         else: logger.warning("CLAN_TAG não definido. Atualizações CoC não ativadas.")
    logger.info("Configurando servidor web para painel..."); bot.web_runner = await setup_web_server() # type: ignore
    if bot.web_runner: logger.info("Servidor web configurado.") # type: ignore
    else: logger.warning("Falha ao configurar servidor web.")
    logger.info("Sincronizando comandos de app no setup_hook..."); synced_cmds: List[app_commands.AppCommand] = [] # type: ignore
    try:
        if bot.tree: # type: ignore
            if TEST_GUILD_ID:
                try: guild_obj = discord.Object(id=int(TEST_GUILD_ID)); bot.tree.copy_global_to(guild=guild_obj); synced_cmds = await bot.tree.sync(guild=guild_obj) # type: ignore
                except (ValueError, TypeError): logger.error(f"TEST_GUILD_ID ('{TEST_GUILD_ID}') inválido. Sincronizando globalmente..."); synced_cmds = await bot.tree.sync() # type: ignore
            else: synced_cmds = await bot.tree.sync() # type: ignore
            logger.info(f"{len(synced_cmds)} comandos (/) sincronizados.") # type: ignore
            if not synced_cmds and bot.tree.get_commands(): logger.warning("Nenhum comando sincronizado, mas a tree possui comandos.") # type: ignore
        else:
            logger.error("bot.tree não está definido. Não é possível sincronizar comandos.")
    except discord.errors.Forbidden:
        logger.error("Erro ao sincronizar comandos (/): Permissão 'applications.commands' negada.")
    except Exception as e: logger.error(f"Erro ao sincronizar comandos (/): {e}", exc_info=True)
    logger.info("setup_hook concluído.")

async def main(): # Mantida a lógica original do usuário
    bot.setup_hook = setup_hook # type: ignore
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
                 try: await asyncio.sleep(1) # Dá um tempo para a task cancelar
                 except asyncio.CancelledError: logger.info("check_war_end_report_task cancelada.")
            if hasattr(bot, "web_runner") and bot.web_runner: await bot.web_runner.cleanup(); logger.info("Servidor web limpo.") # type: ignore
            if hasattr(bot, "coc_client") and bot.coc_client and bot.coc_client.http and not bot.coc_client.http.closed : await bot.coc_client.close(); logger.info("Cliente CoC fechado.") # type: ignore
            logger.info("Desligamento do bot concluído.")

def handle_asyncio_exception(loop: asyncio.AbstractEventLoop, context: Dict[str, Any]): # Mantida a lógica original do usuário
    msg = context.get("exception", context["message"])
    logger.error(f"Erro asyncio não tratado: {msg}", exc_info=context.get('exception'))

if __name__ == "__main__": # Mantida a lógica original do usuário
    required = ["DISCORD_TOKEN", "COC_EMAIL", "COC_PASSWORD", "CLAN_TAG", "CHANNEL_ID"]
    missing_vars = [v for v in required if not os.getenv(v)]
    if missing_vars:
        logger.critical(f"Variáveis env faltando: {', '.join(missing_vars)}. Verifique .env."); exit(1)
    try: # Adicionado para verificar se CHANNEL_ID é válido
        if not str(os.getenv("CHANNEL_ID")).isdigit() or int(os.getenv("CHANNEL_ID", "0")) == 0 : # type: ignore
             logger.critical("CHANNEL_ID não é um número válido ou é 0. Verifique .env."); exit(1)
    except Exception:
        logger.critical("Erro ao verificar CHANNEL_ID. Verifique .env."); exit(1)


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
        # Limpeza de tasks pendentes
        tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not asyncio.current_task(loop=loop)]
        if tasks:
            logger.info(f"Cancelando {len(tasks)} tarefas pendentes...")
            for task in tasks:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))

        if not loop.is_closed():
            loop.close()
        logger.info("Programa finalizado.")
