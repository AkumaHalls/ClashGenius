# -*- coding: utf-8 -*-
# Versão 19.1 - (Painel web expandido, correção de import WarLogEntry e integrações)

import os
import logging
import asyncio
import datetime
from aiohttp import web
from typing import Dict, List, Optional, Union, Set, Any # Adicionado Any
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc # Importa o pacote principal

# ---- CORREÇÃO E ADIÇÃO DE IMPORTAÇÕES ESPECÍFICAS ----
from coc import (
    ClanWar,
    Player,
    Clan,
    WarAttack,
    Timestamp,
    ClanMember,
    LeagueGroup,
    CapitalDistrict # Assegurar que CapitalDistrict também seja importado corretamente
)
from coc.wars import WarLogEntry # Importação específica para WarLogEntry
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
except (TypeError, ValueError):
    logger.error(f"CHANNEL_ID ('{channel_id_str}') inválido no .env. Usando 0 como padrão.")
    CHANNEL_ID = 0

ROLE_ID_1STAR_ALERT = os.getenv("ROLE_ID_1STAR_ALERT")
ROLE_ID_MISSED_ATTACK = os.getenv("ROLE_ID_MISSED_ATTACK")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

try:
    TIMEZONE = pytz.timezone('America/Sao_Paulo')
except pytz.UnknownTimeZoneError:
    logger.error("Timezone 'America/Sao_Paulo' desconhecida. Usando UTC como padrão.")
    TIMEZONE = pytz.utc

BOT_VERSION = "19.1" 

reported_war_ends: Set[str] = set()
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Cache para dados de jogadores (tag: Player) para evitar múltiplas buscas na mesma requisição web
player_short_term_cache: Dict[str, Player] = {}

async def get_clan_data(tag: str) -> Clan:
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        if not tag.startswith("#"):
            tag = f"#{tag}"
        return await bot.coc_client.get_clan(tag)
    except coc.NotFound:
        raise ValueError(f"Clã com tag {tag} não encontrado.")
    except coc.Maintenance:
        raise ValueError("API do CoC está em manutenção. Tente novamente mais tarde.")
    except asyncio.TimeoutError:
        raise ValueError("Tempo limite excedido ao buscar dados do clã. Tente novamente.")
    except coc.InvalidCredentials:
        raise ValueError("Credenciais inválidas para a API do CoC detectadas.")
    except coc.Forbidden:
        raise ValueError("Acesso proibido à API do CoC (Forbidden). Verifique permissões da chave API.")
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar dados do clã {tag}: {e}", exc_info=True)
        raise ValueError(f"Erro inesperado ao buscar dados do clã: {str(e)}")

async def get_player_data_with_short_term_cache(tag: str) -> Player: # Renomeada da original get_player_data para clareza
    """Fetch player data, using a short-term cache first."""
    if not tag.startswith("#"):
        tag = f"#{tag}"
    if tag in player_short_term_cache:
        # logger.debug(f"Usando cache de curto prazo para jogador {tag}")
        return player_short_term_cache[tag]
    
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        # logger.debug(f"Buscando dados do jogador {tag} (sem cache de curto prazo)")
        player = await bot.coc_client.get_player(tag)
        player_short_term_cache[tag] = player 
        return player
    except coc.NotFound:
        logger.warning(f"Jogador com tag {tag} não encontrado ao buscar para cache de curto prazo.")
        raise ValueError(f"Jogador com tag {tag} não encontrado.") 
    except coc.Maintenance:
        raise ValueError("API do CoC está em manutenção. Tente novamente mais tarde.")
    except asyncio.TimeoutError:
        raise ValueError("Tempo limite excedido ao buscar dados do jogador. Tente novamente.")
    except coc.InvalidCredentials: # Adicionado para consistência com get_clan_data
        raise ValueError("Credenciais inválidas para a API do CoC detectadas.")
    except coc.Forbidden: # Adicionado para consistência
        raise ValueError("Acesso proibido à API do CoC (Forbidden). Verifique permissões da chave API.")
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar dados do jogador {tag} para cache: {e}", exc_info=True)
        raise ValueError(f"Erro inesperado ao buscar dados do jogador {tag}: {str(e)}")

# Cache de clã de longa duração
clan_cache: Dict[str, Dict] = {}
CACHE_DURATION_SECONDS = 300 

async def get_clan_data_with_cache(tag: str) -> Clan:
    if not tag.startswith("#"):
        tag = f"#{tag}"
    now = datetime.datetime.now()
    if tag in clan_cache:
        cache_entry = clan_cache[tag]
        cache_age = (now - cache_entry["timestamp"]).total_seconds()
        if cache_age < CACHE_DURATION_SECONDS:
            logger.debug(f"Usando cache para clã {tag} (idade: {cache_age:.1f}s)")
            return cache_entry["data"]
        else:
            logger.debug(f"Cache expirado para clã {tag} (idade: {cache_age:.1f}s)")

    logger.debug(f"Buscando novos dados para clã {tag}")
    clan_data_val = await get_clan_data(tag) 
    clan_cache[tag] = {"data": clan_data_val, "timestamp": now}
    return clan_data_val

async def fetch_location_id(location_name: str) -> int:
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        locations = await bot.coc_client.search_locations(name=location_name, limit=1)
        if not locations:
            raise ValueError(f"Localização '{location_name}' não encontrada.")
        loc_obj = locations[0]
        if hasattr(loc_obj, 'id'):
            return loc_obj.id
        else:
            raise ValueError(f"Objeto de localização para '{location_name}' não possui ID.")
    except Exception as e:
        logger.error(f"Erro ao buscar ID da localização '{location_name}': {e}", exc_info=True)
        raise ValueError(f"Erro ao buscar ID da localização: {str(e)}")

async def send_log_embed(embed_to_log: discord.Embed, content: str = None) -> None:
    if not CHANNEL_ID or CHANNEL_ID == 0:
         logger.warning("CHANNEL_ID não configurado. Não é possível enviar embed de log.")
         return
    if not hasattr(embed_to_log, 'footer') or not hasattr(embed_to_log.footer, 'text') or not embed_to_log.footer.text:
         embed_to_log.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
    if not embed_to_log.timestamp:
        embed_to_log.timestamp = datetime.datetime.now(TIMEZONE)
    try:
        channel_log = await bot.fetch_channel(CHANNEL_ID)
        if isinstance(channel_log, discord.TextChannel):
            await channel_log.send(content=content, embed=embed_to_log)
        else:
             logger.error(f"Canal de log ID {CHANNEL_ID} não é um canal de texto válido.")
    except discord.NotFound:
         logger.error(f"Canal de log ID {CHANNEL_ID} não encontrado.")
    except discord.Forbidden:
         logger.error(f"Sem permissão para enviar mensagens no canal de log ID {CHANNEL_ID}.")
    except Exception as e:
        logger.error(f"Erro ao enviar embed para o canal de log ID {CHANNEL_ID}: {e}", exc_info=True)

async def send_embeds_splitted(channel: discord.TextChannel, base_embed: discord.Embed,
                               field_name: str, items: List[str]) -> None:
    if not isinstance(channel, discord.TextChannel):
        logger.error("Canal inválido passado para send_embeds_splitted.")
        return
    if not items:
         embed_empty_split = discord.Embed.from_dict(base_embed.to_dict())
         embed_empty_split.add_field(name=field_name, value="Nenhum item encontrado.", inline=False)
         if not hasattr(embed_empty_split, 'footer') or not hasattr(embed_empty_split.footer, 'text') or not embed_empty_split.footer.text:
             embed_empty_split.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
         if not embed_empty_split.timestamp:
             embed_empty_split.timestamp = datetime.datetime.now(TIMEZONE)
         try:
              await channel.send(embed=embed_empty_split)
         except discord.Forbidden:
              logger.error(f"Sem permissão para enviar embed dividido (vazio) para o canal {channel.id}")
         except Exception as e:
              logger.error(f"Erro ao enviar embed dividido (vazio) para o canal {channel.id}: {e}", exc_info=True)
         return

    embeds_to_send = []
    current_embed_split = discord.Embed.from_dict(base_embed.to_dict())
    current_field_value_split = ""
    for item in items:
        item_line = item + "\n"
        if (len(current_field_value_split) + len(item_line) > 1024 or
            len(current_embed_split) + len(item_line) > 5900): # Limite aproximado de tamanho de embed
            if current_field_value_split:
                safe_field_name = field_name if field_name else "Dados"
                current_embed_split.add_field(name=safe_field_name, value=current_field_value_split, inline=False)
            if current_embed_split.fields: # Apenas adiciona se tiver campos
                 embeds_to_send.append(current_embed_split)
            current_embed_split = discord.Embed.from_dict(base_embed.to_dict()) # Reinicia para o próximo embed
            current_field_value_split = item_line # Começa o novo campo com o item atual
            if len(current_field_value_split) > 1024: # Se o item sozinho for muito grande
                 logger.warning(f"Item individual muito longo para campo de embed: {item[:50]}...")
                 current_field_value_split = current_field_value_split[:1021] + "...\n" # Trunca
        else:
            current_field_value_split += item_line
    
    # Adiciona o último embed se houver conteúdo pendente
    if current_field_value_split: # Adiciona o valor do campo final
        safe_field_name_split = field_name if field_name else "Dados"
        current_embed_split.add_field(name=safe_field_name_split, value=current_field_value_split, inline=False)
    if current_embed_split.fields: # Adiciona o último embed se tiver campos
         embeds_to_send.append(current_embed_split)

    for embed_item in embeds_to_send: # Define rodapé e timestamp para todos os embeds
        if not hasattr(embed_item, 'footer') or not hasattr(embed_item.footer, 'text') or not embed_item.footer.text:
             embed_item.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
        if not embed_item.timestamp:
             embed_item.timestamp = datetime.datetime.now(TIMEZONE)

    for embed_to_send_msg in embeds_to_send:
        try:
            await channel.send(embed=embed_to_send_msg)
        except discord.Forbidden:
             logger.error(f"Sem permissão para enviar embed dividido para o canal {channel.id}")
             break 
        except Exception as e:
            logger.error(f"Erro ao enviar embed dividido para o canal {channel.id}: {e}", exc_info=True)


# --- FUNÇÕES HELPER PARA O PAINEL WEB ---
def format_war_time_details(war_obj: ClanWar, time_now_tz: datetime.datetime) -> Dict[str, Any]:
    """Formata os tempos de início/fim e o tempo restante para uma guerra."""
    details: Dict[str, Any] = { # Corrigido para Any para aceitar None
        "time_key": "N/A",
        "time_value": "N/A",
        "time_remaining": "N/A",
        "start_time_iso": None,
        "end_time_iso": None,
    }
    if hasattr(war_obj, 'state') and war_obj.state == "preparation":
        if hasattr(war_obj, 'start_time') and war_obj.start_time and hasattr(war_obj.start_time, 'time'):
            start_aware = pytz.utc.localize(war_obj.start_time.time).astimezone(TIMEZONE)
            details["start_time_iso"] = start_aware.isoformat()
            details["time_key"] = "Início"
            details["time_value"] = start_aware.strftime('%d/%m %H:%M')
            delta = start_aware - time_now_tz
            if delta.total_seconds() > 0:
                d, rem_s = divmod(delta.total_seconds(), 86400)
                h, rem_s = divmod(rem_s, 3600)
                m, _ = divmod(rem_s, 60)
                details["time_remaining"] = f"{int(d)}d {int(h)}h {int(m)}m" if d > 0 else f"{int(h)}h {int(m)}m"
            else:
                details["time_remaining"] = "Iniciando..."
    elif hasattr(war_obj, 'state') and (war_obj.state == "inWar" or war_obj.state == "warEnded"):
        if hasattr(war_obj, 'end_time') and war_obj.end_time and hasattr(war_obj.end_time, 'time'):
            end_aware = pytz.utc.localize(war_obj.end_time.time).astimezone(TIMEZONE)
            details["end_time_iso"] = end_aware.isoformat()
            details["time_key"] = "Fim" if war_obj.state == "inWar" else "Finalizada em"
            details["time_value"] = end_aware.strftime('%d/%m %H:%M')
            if war_obj.state == "inWar":
                delta = end_aware - time_now_tz
                if delta.total_seconds() > 0:
                    d, rem_s = divmod(delta.total_seconds(), 86400)
                    h, rem_s = divmod(rem_s, 3600)
                    m, _ = divmod(rem_s, 60)
                    details["time_remaining"] = f"{int(d)}d {int(h)}h {int(m)}m" if d > 0 else f"{int(h)}h {int(m)}m"
                else:
                    details["time_remaining"] = "Finalizando..."
            else: # warEnded
                 details["time_remaining"] = "-"
    return details

async def get_current_or_last_war(clan_tag: str) -> Optional[ClanWar]:
    """Busca a guerra atual (regular ou CWL). Se não houver guerra ativa, busca a última guerra finalizada."""
    current_war: Optional[ClanWar] = None
    # Tenta CWL primeiro
    try:
        league_group = await bot.coc_client.get_league_group(clan_tag)
        if league_group and getattr(league_group,'state',None) != "notInWar" and hasattr(league_group, 'rounds'):
            # Para coc.py >= 2.3, current_wars é uma property
            if hasattr(league_group, 'current_wars'):
                for war_tag_obj in reversed(league_group.current_wars): 
                    try:
                        lg_war = await league_group.get_league_war(war_tag_obj.tag)
                        if lg_war and (lg_war.clan.tag == clan_tag or lg_war.opponent.tag == clan_tag):
                            if lg_war.state in ["inWar", "preparation"]:
                                current_war = lg_war
                                if lg_war.opponent.tag == clan_tag: 
                                    current_war.clan, current_war.opponent = current_war.opponent, current_war.clan
                                return current_war 
                    except coc.NotFound:
                        logger.debug(f"Guerra da CWL {war_tag_obj.tag} não encontrada durante busca de guerra atual.")
                        continue
                    except Exception as e_cwl_curr:
                        logger.error(f"Erro ao buscar guerra atual específica da CWL {war_tag_obj.tag}: {e_cwl_curr}")
                        continue
            else: # Fallback para versões mais antigas ou se current_wars não for útil
                for war_tags_in_round in reversed(league_group.rounds):
                    for war_tag_str in war_tags_in_round:
                        if war_tag_str == "#0": continue # Ignora guerras "bye"
                        try:
                            lg_war = await league_group.get_league_war(war_tag_str)
                            if lg_war and (lg_war.clan.tag == clan_tag or lg_war.opponent.tag == clan_tag):
                                if lg_war.state in ["inWar", "preparation"]:
                                    current_war = lg_war
                                    if lg_war.opponent.tag == clan_tag:
                                        current_war.clan, current_war.opponent = current_war.opponent, current_war.clan
                                    return current_war
                        except coc.NotFound: continue
                        except Exception as e_cwl_fb:
                            logger.error(f"Erro ao buscar guerra da CWL (fallback) {war_tag_str}: {e_cwl_fb}")
                            continue


            if not current_war and league_group.rounds: # Se não achou ativa, procura a última finalizada da CWL
                for war_tags_in_round in reversed(league_group.rounds):
                    for war_tag_str in war_tags_in_round:
                        if war_tag_str == "#0": continue
                        try:
                            lg_war = await league_group.get_league_war(war_tag_str)
                            if lg_war and (lg_war.clan.tag == clan_tag or lg_war.opponent.tag == clan_tag):
                                if lg_war.state == "warEnded":
                                     if lg_war.opponent.tag == clan_tag:
                                         lg_war.clan, lg_war.opponent = lg_war.opponent, lg_war.clan
                                     return lg_war 
                        except coc.NotFound: continue
                        except Exception as e_cwl_ended:
                             logger.error(f"Erro ao buscar guerra finalizada da CWL {war_tag_str}: {e_cwl_ended}")
                             continue
    except coc.NotFound:
        logger.debug(f"Nenhum grupo de liga encontrado para clan {clan_tag} em get_current_or_last_war.")
    except Exception as e:
        logger.error(f"Erro ao buscar guerra da CWL em get_current_or_last_war para {clan_tag}: {e}", exc_info=True)

    try:
        regular_war = await bot.coc_client.get_current_war(clan_tag)
        if regular_war and regular_war.state != "notInWar": 
            return regular_war
    except coc.PrivateWarLog:
        logger.warning(f"Log de guerra regular do clã {clan_tag} é privado.")
    except coc.NotFound:
        logger.debug(f"Nenhuma guerra regular encontrada para {clan_tag} em get_current_or_last_war.")
    except Exception as e_reg_war:
        logger.error(f"Erro ao buscar guerra regular para {clan_tag}: {e_reg_war}", exc_info=True)
        
    return None

# --- Funções de Coleta de Dados para Endpoints Web ---
web_api_cache: Dict[str, Dict[str, Any]] = {} # Tipagem mais específica para o cache
WEB_API_CACHE_DURATION_SECONDS = 60

async def get_cached_web_data(key: str, func_to_fetch_data: callable, *args: Any) -> Any:
    now = datetime.datetime.now()
    if key in web_api_cache:
        cache_entry = web_api_cache[key]
        # Verifica se 'timestamp' existe e é um datetime
        if "timestamp" in cache_entry and isinstance(cache_entry["timestamp"], datetime.datetime):
            cache_age = (now - cache_entry["timestamp"]).total_seconds()
            if cache_age < WEB_API_CACHE_DURATION_SECONDS:
                logger.debug(f"Usando cache web para {key} (idade: {cache_age:.1f}s)")
                return cache_entry["data"]
            else:
                logger.debug(f"Cache web expirado para {key}")
        else: # Timestamp inválido, tratar como cache expirado
            logger.warning(f"Timestamp inválido ou ausente no cache para {key}. Buscando novos dados.")


    logger.debug(f"Buscando novos dados web para {key}")
    data = await func_to_fetch_data(*args)
    web_api_cache[key] = {"data": data, "timestamp": now}
    return data

async def fetch_clan_info_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        districts_data = []
        if hasattr(clan, 'capital_districts') and clan.capital_districts:
            for district in clan.capital_districts:
                districts_data.append({
                    "name": district.name,
                    "level": district.hall_level 
                })
        
        return {
            "name": clan.name, "tag": clan.tag, "level": clan.level, "points": clan.points,
            "capital_points": clan.capital_points if hasattr(clan, 'capital_points') else 0,
            "member_count": clan.member_count, "description": clan.description,
            "war_wins": clan.war_wins if hasattr(clan, 'war_wins') else 'N/A',
            "location": clan.location.name if hasattr(clan, 'location') and clan.location else "N/A",
            "type": clan.type.capitalize() if hasattr(clan, 'type') else "N/A",
            "badge_url": clan.badge.url if hasattr(clan, 'badge') and clan.badge else None,
            "version": BOT_VERSION,
            "capital_districts": districts_data,
            "capital_league": clan.capital_league.name if hasattr(clan, 'capital_league') and clan.capital_league else "N/A"
        }
    except Exception as e:
        logger.error(f"Erro ao buscar dados do clã para API web: {e}", exc_info=True)
        return {"error": str(e), "name": "Erro ao carregar Clã"}

async def fetch_clan_members_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        members_data = []
        if hasattr(clan, 'members') and clan.members:
            for member in clan.members:
                members_data.append({
                    "name": member.name, "tag": member.tag, "town_hall": member.town_hall,
                    "exp_level": member.exp_level,
                    "league": member.league.name if hasattr(member, 'league') and member.league else "N/A",
                    "trophies": member.trophies,
                    "role": member.role.name.capitalize() if hasattr(member, 'role') and member.role else "Membro",
                    "donations": member.donations, "received": member.received,
                })
        members_data.sort(key=lambda m: m.get("trophies", 0), reverse=True)
        return {"members": members_data, "clan_name": clan.name, "clan_tag": clan.tag}
    except Exception as e:
        logger.error(f"Erro ao buscar membros do clã para API web: {e}", exc_info=True)
        return {"error": str(e)}

async def fetch_war_status_for_web_api() -> Dict[str, Any]: # Visão geral da guerra
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot."}
    war_to_display = await get_current_or_last_war(CLAN_TAG)

    if not war_to_display:
        return {"status": "NotInWar", "message": "Nenhuma guerra ativa ou recente encontrada.", "type": "Nenhuma"}
    
    time_now_tz = datetime.datetime.now(TIMEZONE)
    time_details = format_war_time_details(war_to_display, time_now_tz)
    
    war_type_description = "Guerra" 
    if hasattr(war_to_display, 'is_cwl') and war_to_display.is_cwl: war_type_description = "Liga de Clãs (CWL)"
    elif hasattr(war_to_display, 'type') and war_to_display.type == "friendly": war_type_description = "Guerra Amistosa"
    else: war_type_description = "Guerra Normal"


    return {
        "status": war_to_display.state, "type": war_type_description,
        "state_description": war_to_display.state.capitalize() if war_to_display.state else "Desconhecido",
        "clan_name": war_to_display.clan.name if war_to_display.clan else "Clã Desconhecido", 
        "clan_stars": war_to_display.clan.stars if war_to_display.clan else 0,
        "clan_destruction": f"{war_to_display.clan.destruction:.2f}%" if war_to_display.clan else "0.00%",
        "clan_badge_url": war_to_display.clan.badge.url if war_to_display.clan and hasattr(war_to_display.clan.badge, 'url') else None,
        "opponent_name": war_to_display.opponent.name if war_to_display.opponent else "Oponente Desconhecido", 
        "opponent_tag": war_to_display.opponent.tag if war_to_display.opponent else "#?",
        "opponent_stars": war_to_display.opponent.stars if war_to_display.opponent else 0,
        "opponent_destruction": f"{war_to_display.opponent.destruction:.2f}%" if war_to_display.opponent else "0.00%",
        "opponent_badge_url": war_to_display.opponent.badge.url if war_to_display.opponent and hasattr(war_to_display.opponent.badge, 'url') else None,
        **time_details,
        "attacks_per_member": war_to_display.attacks_per_member,
        "preparation_start_time_iso": war_to_display.preparation_start_time.time.isoformat() if war_to_display.preparation_start_time and hasattr(war_to_display.preparation_start_time, 'time') else None,
    }

async def fetch_current_war_details_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot.", "war_data": None, "attacks": []}
    
    player_short_term_cache.clear() 
    war = await get_current_or_last_war(CLAN_TAG)

    if not war or (hasattr(war, 'state') and war.state == "notInWar"): # Adicionado hasattr
        return {"error": "Nenhuma guerra ativa ou recente para detalhar.", "war_data": None, "attacks": []}

    attacks_data = []
    if war.attacks: # war.attacks pode ser None
        for attack in sorted(war.attacks, key=lambda a: a.order): 
            try:
                attacker = await get_player_data_with_short_term_cache(attack.attacker_tag)
                attacker_name = attacker.name
                attacker_townhall = attacker.town_hall
            except ValueError: 
                attacker_name = attack.attacker_tag 
                attacker_townhall = '?'
            
            try:
                defender = await get_player_data_with_short_term_cache(attack.defender_tag)
                defender_name = defender.name
                defender_townhall = defender.town_hall
            except ValueError:
                defender_name = attack.defender_tag 
                defender_townhall = '?'

            attacks_data.append({
                "attacker_tag": attack.attacker_tag, "attacker_name": attacker_name,
                "attacker_townhall": attacker_townhall, "defender_tag": attack.defender_tag,
                "defender_name": defender_name, "defender_townhall": defender_townhall,
                "stars": attack.stars, "destruction": attack.destruction,
                "order": attack.order, "duration": attack.duration 
            })
    
    time_now_tz = datetime.datetime.now(TIMEZONE)
    time_details = format_war_time_details(war, time_now_tz)
    
    war_type_description = "Guerra"
    if hasattr(war, 'is_cwl') and war.is_cwl: war_type_description = "Liga de Clãs (CWL)"
    elif hasattr(war, 'type') and war.type == "friendly": war_type_description = "Guerra Amistosa"
    else: war_type_description = "Guerra Normal"

    return {
        "war_data": {
            "status": war.state, "type": war_type_description,
            "state_description": war.state.capitalize() if war.state else "Desconhecido",
            "clan_name": war.clan.name if war.clan else "Clã Desconhecido", 
            "clan_stars": war.clan.stars if war.clan else 0,
            "clan_destruction": f"{war.clan.destruction:.2f}%" if war.clan else "0.00%",
            "clan_badge_url": war.clan.badge.url if war.clan and hasattr(war.clan.badge, 'url') else None,
            "opponent_name": war.opponent.name if war.opponent else "Oponente Desconhecido", 
            "opponent_tag": war.opponent.tag if war.opponent else "#?",
            "opponent_stars": war.opponent.stars if war.opponent else 0,
            "opponent_destruction": f"{war.opponent.destruction:.2f}%" if war.opponent else "0.00%",
            "opponent_badge_url": war.opponent.badge.url if war.opponent and hasattr(war.opponent.badge, 'url') else None,
            **time_details,
            "attacks_per_member": war.attacks_per_member,
            "team_size": war.team_size if hasattr(war, 'team_size') else 'N/A', 
        },
        "attacks": attacks_data
    }

async def fetch_war_attacks_remaining_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot."}
    war = await get_current_or_last_war(CLAN_TAG)

    clan_name_for_header = "N/A"
    if war and war.clan: clan_name_for_header = war.clan.name

    if not war or war.state != "inWar":
        return {"message": "Não há guerra em andamento para verificar ataques restantes.", "members_pending": [], "clan_name": clan_name_for_header}

    members_pending_attack = []
    
    our_clan_in_war = None
    if war.clan and war.clan.tag == CLAN_TAG:
        our_clan_in_war = war.clan
    elif war.opponent and war.opponent.tag == CLAN_TAG: # Se o nosso clã for o oponente no objeto war
        our_clan_in_war = war.opponent
    else:
        logger.error(f"Ataques restantes: Não foi possível identificar nosso clã ({CLAN_TAG}) na guerra entre {war.clan.tag if war.clan else 'N/A'} e {war.opponent.tag if war.opponent else 'N/A'}.")
        return {"message": "Erro ao identificar nosso clã na guerra.", "members_pending": [], "clan_name": "Erro"}
    
    clan_name_for_header = our_clan_in_war.name # Atualiza com o nome correto

    if our_clan_in_war.members: 
        for member in our_clan_in_war.members:
            # Somente processar membros que realmente participam da guerra (se houver essa info)
            # Por agora, assume que todos os membros listados em war.clan.members estão na guerra
            attacks_made = len(member.attacks) if member.attacks else 0
            attacks_left = war.attacks_per_member - attacks_made
            if attacks_left > 0:
                members_pending_attack.append({
                    "name": member.name, "tag": member.tag,
                    "town_hall": member.town_hall, "attacks_left": attacks_left,
                    "map_position": member.map_position
                })
    members_pending_attack.sort(key=lambda m: m.get("map_position", 0))
    return {"message": "Membros com ataques pendentes.", "members_pending": members_pending_attack, "clan_name": clan_name_for_header}

async def fetch_war_log_for_web_api(limit: int = 10) -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot."}
    try:
        war_log_iterator = await bot.coc_client.get_war_log(CLAN_TAG) # Limit é tratado após
        
        log_entries_data = [] 
        count = 0
        async for entry in war_log_iterator: 
            if count >= limit:
                break
            
            result_for_us = "N/A"
            # Assume que entry.clan é o nosso clã, pois pedimos o log de CLAN_TAG
            if entry.clan.tag == CLAN_TAG:
                if entry.result:
                    if entry.result == "win": result_for_us = "Vitória"
                    elif entry.result == "lose": result_for_us = "Derrota"
                    elif entry.result == "tie": result_for_us = "Empate"
            else: 
                logger.warning(f"WarLogEntry com clã principal {entry.clan.tag} não é o nosso clã {CLAN_TAG}")
                # Se o oponente for o nosso clã, o resultado seria o inverso
                if entry.opponent.tag == CLAN_TAG:
                    if entry.result == "win": result_for_us = "Derrota" # O oponente (nós) perdeu
                    elif entry.result == "lose": result_for_us = "Vitória" # O oponente (nós) ganhou
                    elif entry.result == "tie": result_for_us = "Empate"


            log_entries_data.append({
                "clan_name": entry.clan.name, "clan_tag": entry.clan.tag,
                "clan_stars": entry.clan.stars, "clan_destruction": entry.clan.destruction,
                "clan_badge_url": entry.clan.badge.url if hasattr(entry.clan.badge, 'url') else None,
                "opponent_name": entry.opponent.name, "opponent_tag": entry.opponent.tag,
                "opponent_stars": entry.opponent.stars, "opponent_destruction": entry.opponent.destruction,
                "opponent_badge_url": entry.opponent.badge.url if hasattr(entry.opponent.badge, 'url') else None,
                "team_size": entry.team_size,
                "end_time": entry.end_time.time.strftime('%d/%m/%Y %H:%M') if entry.end_time and hasattr(entry.end_time, 'time') else "N/A",
                "end_time_iso": entry.end_time.time.isoformat() if entry.end_time and hasattr(entry.end_time, 'time') else None,
                "result": result_for_us,
                "is_cwl": True if hasattr(entry, 'is_cwl') and entry.is_cwl else False
            })
            count += 1
        return {"log": log_entries_data}
    except coc.PrivateWarLog:
        return {"error": "O log de guerras deste clã é privado."}
    except Exception as e:
        logger.error(f"Erro ao buscar log de guerras para API web: {e}", exc_info=True)
        return {"error": str(e)}

async def fetch_cwl_info_for_web_api() -> Dict[str, Any]:
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot."}
    try:
        league_group = await bot.coc_client.get_league_group(CLAN_TAG)
        # `state` em LeagueGroup pode ser 'preparation', 'inWar', 'ended', ou 'notInWar' (se não estiver em um grupo)
        if not league_group or (hasattr(league_group, 'state') and league_group.state == "notInWar"):
            return {"status": "NotInCwl", "message": "O clã não está atualmente em uma Liga de Guerras de Clãs."}

        rounds_data = []
        if league_group.rounds:
            for i, war_tags_in_round in enumerate(league_group.rounds):
                round_info: Dict[str, Any] = {"round_number": i + 1, "wars": []}
                if not war_tags_in_round: # Rodada ainda não definida
                     round_info["wars"].append({"message": "Rodada ainda não definida."})
                else:
                    for war_tag_str in war_tags_in_round:
                        if war_tag_str == "#0": 
                            round_info["wars"].append({"message": "Sem guerra (bye)."})
                            continue
                        try:
                            war = await league_group.get_league_war(war_tag_str)
                            our_clan_obj = war.clan
                            opponent_obj = war.opponent
                            if war.opponent.tag == CLAN_TAG: # Normaliza para que nosso clã seja 'our_clan_obj'
                                our_clan_obj, opponent_obj = opponent_obj, our_clan_obj

                            time_now_tz = datetime.datetime.now(TIMEZONE)
                            time_details = format_war_time_details(war, time_now_tz)

                            round_info["wars"].append({
                                "war_tag": war_tag_str, "state": war.state,
                                "clan_name": our_clan_obj.name, "clan_stars": our_clan_obj.stars,
                                "clan_destruction": f"{our_clan_obj.destruction:.2f}%",
                                "clan_badge_url": our_clan_obj.badge.url if hasattr(our_clan_obj.badge, 'url') else None,
                                "opponent_name": opponent_obj.name, "opponent_tag": opponent_obj.tag,
                                "opponent_stars": opponent_obj.stars,
                                "opponent_destruction": f"{opponent_obj.destruction:.2f}%",
                                "opponent_badge_url": opponent_obj.badge.url if hasattr(opponent_obj.badge, 'url') else None,
                                **time_details
                            })
                        except coc.NotFound:
                            round_info["wars"].append({"war_tag": war_tag_str, "error": "Guerra não encontrada (pode não ter iniciado)"})
                        except Exception as e_war:
                             round_info["wars"].append({"war_tag": war_tag_str, "error": f"Erro ao buscar guerra: {str(e_war)}"})
                rounds_data.append(round_info)
        
        clans_in_group_data = []
        if league_group.clans:
            for clan_in_group in league_group.clans:
                 clans_in_group_data.append({
                     "name": clan_in_group.name, "tag": clan_in_group.tag,
                     "level": clan_in_group.level,
                     "badge_url": clan_in_group.badge.url if hasattr(clan_in_group.badge, 'url') else None,
                 })

        return {
            "status": "InCwl", # Indica que está em um grupo de CWL
            "state": league_group.state, # O estado do grupo ('preparation', 'inWar', 'ended')
            "season": league_group.season.strftime('%Y-%m') if hasattr(league_group, 'season') and league_group.season else "N/A",
            "clans_in_group": clans_in_group_data,
            "rounds": rounds_data
        }
    except coc.NotFound: 
        return {"status": "NotInCwl", "message": "O clã não está em CWL (grupo não encontrado)."}
    except Exception as e:
        logger.error(f"Erro ao buscar informações da CWL para API web: {e}", exc_info=True)
        return {"error": str(e)}

# --- Endpoints da API Web ---
async def api_clan_info_handler(request: web.Request) -> web.Response:
    key = f"web_clan_info_{CLAN_TAG}"
    data = await get_cached_web_data(key, fetch_clan_info_for_web_api)
    return web.json_response(data)

async def api_members_handler(request: web.Request) -> web.Response:
    key = f"web_clan_members_{CLAN_TAG}"
    data = await get_cached_web_data(key, fetch_clan_members_for_web_api)
    return web.json_response(data)

async def api_war_status_handler(request: web.Request) -> web.Response: # Visão geral da guerra
    key = f"web_war_status_{CLAN_TAG}"
    data = await get_cached_web_data(key, fetch_war_status_for_web_api)
    return web.json_response(data)

async def api_current_war_details_handler(request: web.Request) -> web.Response: # Detalhes com ataques
    key = f"web_current_war_details_{CLAN_TAG}"
    data = await get_cached_web_data(key, fetch_current_war_details_for_web_api)
    return web.json_response(data)

async def api_war_attacks_remaining_handler(request: web.Request) -> web.Response:
    key = f"web_war_attacks_remaining_{CLAN_TAG}"
    data = await get_cached_web_data(key, fetch_war_attacks_remaining_for_web_api)
    return web.json_response(data)

async def api_war_log_handler(request: web.Request) -> web.Response:
    limit_str = request.query.get("limit", "10")
    try:
        limit = int(limit_str)
        if not 1 <= limit <= 50: 
            limit = 10
    except ValueError:
        limit = 10
    key = f"web_war_log_{CLAN_TAG}_limit{limit}" 
    data = await get_cached_web_data(key, fetch_war_log_for_web_api, limit)
    return web.json_response(data)

async def api_cwl_info_handler(request: web.Request) -> web.Response:
    key = f"web_cwl_info_{CLAN_TAG}"
    data = await get_cached_web_data(key, fetch_cwl_info_for_web_api)
    return web.json_response(data)

# --- Servidor Web ---
async def handle_panel_index(request: web.Request) -> web.FileResponse | web.Response:
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "painel.html")
    try:
        return web.FileResponse(index_path)
    except FileNotFoundError:
        logger.error(f"Arquivo painel.html não encontrado em {index_path}")
        return web.Response(text="Painel não encontrado. Verifique se 'static/painel.html' existe.", status=404)
    except Exception as e:
        logger.error(f"Erro ao servir painel.html: {e}")
        return web.Response(text="Erro ao carregar o painel.", status=500)

async def setup_web_server() -> Optional[web.AppRunner]:
    app = web.Application()
    async def health_check_handler(request: web.Request) -> web.Response: # Nomeado para clareza
        logger.debug("Health check endpoint '/' accessed.")
        return web.Response(text=f"Bot is running and web panel is active! Version: {BOT_VERSION}")

    app.router.add_get("/api/clan", api_clan_info_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/war", api_war_status_handler)
    app.router.add_get("/api/current_war_details", api_current_war_details_handler)
    app.router.add_get("/api/war_attacks_remaining", api_war_attacks_remaining_handler)
    app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler)

    app.router.add_get("/painel", handle_panel_index)
    static_files_path = os.path.join(os.path.dirname(__file__), "static")
    
    # Criação de pastas estáticas se não existirem
    for folder in ["", "css", "js", "images"]: # Adicionada pasta images
        path_to_check = os.path.join(static_files_path, folder)
        if not os.path.exists(path_to_check):
            os.makedirs(path_to_check)
            logger.info(f"Pasta '{path_to_check}' criada.")

    # Criação de arquivos HTML, CSS, JS básicos se não existirem (mantido do código original)
    painel_html_path = os.path.join(static_files_path, "painel.html")
    if not os.path.exists(painel_html_path):
        with open(painel_html_path, "w", encoding='utf-8') as f:
            f.write("<!DOCTYPE html><html lang='pt-br'><head><meta charset='UTF-8'><title>Painel CoC</title><link rel='stylesheet' href='/static/css/style.css'></head><body><h1>Painel do Clã - Carregando...</h1><div id='clanName'></div><script src='/static/js/scripts.js'></script></body></html>")
        logger.info(f"Arquivo 'painel.html' básico criado em {painel_html_path}")

    style_css_path = os.path.join(static_files_path, "css", "style.css")
    if not os.path.exists(style_css_path):
        with open(style_css_path, "w", encoding='utf-8') as f:
            f.write("body { font-family: sans-serif; }")
        logger.info(f"Arquivo 'style.css' básico criado em {style_css_path}")

    scripts_js_path = os.path.join(static_files_path, "js", "scripts.js")
    if not os.path.exists(scripts_js_path):
        with open(scripts_js_path, "w", encoding='utf-8') as f:
            f.write("console.log('Painel JS carregado.');")
        logger.info(f"Arquivo 'scripts.js' básico criado em {scripts_js_path}")


    app.router.add_static('/static/', path=static_files_path, name='static', show_index=False)
    app.router.add_get("/", health_check_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    try:
         await site.start()
         logger.info(f"Servidor web para painel iniciado em 0.0.0.0:{port}")
         return runner
    except OSError as e:
        logger.error(f"Falha ao iniciar servidor web na porta {port}: {e} - Verifique se a porta está em uso.")
        return None
    except Exception as e:
         logger.error(f"Erro inesperado ao iniciar servidor web: {e}", exc_info=True)
         return None

# --- Refactored display_attacks_remaining --- (seu código existente)
async def format_attacks_remaining_embed(war: ClanWar) -> Optional[List[discord.Embed]]:
    if not all(hasattr(war, attr) for attr in ['state', 'opponent', 'clan', 'end_time', 'stars', 'destruction']):
         logger.error("Objeto 'war' inválido recebido por format_attacks_remaining_embed.")
         return None

    opponent_name = getattr(war.opponent, 'name', 'Oponente Desconhecido')
    opponent_tag = getattr(war.opponent, 'tag', 'Tag Desconhecida')
    clan_name = getattr(war.clan, 'name', 'Clã Desconhecido')
    clan_badge_url = getattr(war.clan.badge, 'url', None) if hasattr(war.clan, 'badge') else None
    opponent_stars = getattr(war.opponent, 'stars', 0)
    opponent_destruction = getattr(war.opponent, 'destruction', 0.0)

    if war.state != "inWar":
        embed_msg = discord.Embed(
            title=f"⚔️ Guerra Não Ativa",
            description=f"A guerra contra **{opponent_name}** ({opponent_tag}) não está em andamento (Estado: {war.state}).",
            color=discord.Color.orange()
        )
        if clan_badge_url: embed_msg.set_thumbnail(url=clan_badge_url)
        embed_msg.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        embed_msg.timestamp = datetime.datetime.now(TIMEZONE)
        return [embed_msg]

    try:
         time_now = datetime.datetime.now(TIMEZONE)
         if hasattr(war, 'end_time') and isinstance(war.end_time, Timestamp) and hasattr(war.end_time, 'time'):
            naive_end_dt = war.end_time.time
            aware_utc_end_dt = pytz.utc.localize(naive_end_dt)
            end_time_aware = aware_utc_end_dt.astimezone(TIMEZONE)
         else:
            logger.error(f"war.end_time (ou .time) inválido para format_attacks_remaining_embed: {type(war.end_time)}")
            raise ValueError("Tempo de fim da guerra inválido")


         time_delta = end_time_aware - time_now
         if time_delta.total_seconds() < 0:
              time_remaining = "Finalizada"
         else:
             days = time_delta.days
             secs = time_delta.seconds
             hours, rem = divmod(secs, 3600)
             mins, secs_rem = divmod(rem, 60)
             time_remaining = f"{days}d {hours}h {mins}m" if days > 0 else f"{hours}h {mins}m {int(secs_rem)}s"

         end_time_local_fmt = end_time_aware.strftime('%d/%m/%Y %H:%M') 
    except Exception as e:
         logger.error(f"Erro ao calcular tempo restante da guerra em format_attacks_remaining_embed: {e}", exc_info=True)
         time_remaining = "Erro"
         end_time_local_fmt = "Erro"


    members_with_attacks_list = [] # Renomeado para evitar conflito
    # Garantir que estamos olhando para o nosso clã
    our_war_clan = war.clan
    if war.clan.tag != CLAN_TAG and war.opponent.tag == CLAN_TAG:
        our_war_clan = war.opponent
    
    attack_count = getattr(war, 'attacks_per_member', 2)

    if hasattr(our_war_clan, 'members') and our_war_clan.members:
         for member in our_war_clan.members:
            if not member or not hasattr(member, 'attacks'): continue
            attacks_used = len(member.attacks) if member.attacks else 0
            attacks_left = attack_count - attacks_used
            if attacks_left > 0:
                member_th = getattr(member, 'town_hall', '?')
                member_name_str = getattr(member, 'name', 'Membro Desconhecido') # Renomeado
                members_with_attacks_list.append(f"**{member_name_str}** (CV{member_th}) - {attacks_left} {'ataques' if attacks_left > 1 else 'ataque'} restante{'s' if attacks_left > 1 else ''}")
    else:
         logger.warning(f"Lista de membros não encontrada no objeto '{our_war_clan.name}' para format_attacks_remaining_embed.")


    base_embed_attacks = discord.Embed(
        title=f"🗡️ Ataques Restantes - {clan_name} vs {opponent_name}",
        description=f"**Placar:** {war.clan.stars}⭐ ({war.clan.destruction:.2f}%) vs {opponent_stars}⭐ ({opponent_destruction:.2f}%)\n"
                    f"**Fim:** {end_time_local_fmt} ({time_remaining} restantes)",
        color=discord.Color.blue()
    )
    if clan_badge_url: base_embed_attacks.set_thumbnail(url=clan_badge_url)


    embeds_to_send_attacks = []
    field_name_attacks = "Membros com Ataques Pendentes"
    if not members_with_attacks_list:
         embed_single = discord.Embed.from_dict(base_embed_attacks.to_dict())
         embed_single.add_field(name=field_name_attacks, value="✅ Todos os ataques já foram utilizados!", inline=False)
         embeds_to_send_attacks.append(embed_single)
    else: # Lógica de divisão de embeds (send_embeds_splitted pode ser usada aqui se preferir)
        # Para simplificar, se a lista for muito grande, pode ser truncada ou enviada em várias mensagens.
        # A função send_embeds_splitted é uma boa candidata para reutilização aqui.
        # Por enquanto, manterei a lógica original de divisão inline:
        current_embed_attacks = discord.Embed.from_dict(base_embed_attacks.to_dict())
        current_field_value_attacks = ""
        for item in members_with_attacks_list:
            item_line = item + "\n"
            if len(current_field_value_attacks) + len(item_line) > 1024: # Limite do campo
                if current_field_value_attacks:
                    current_embed_attacks.add_field(name=field_name_attacks, value=current_field_value_attacks, inline=False)
                if current_embed_attacks.fields: # Adiciona se tiver campos
                    embeds_to_send_attacks.append(current_embed_attacks)
                current_embed_attacks = discord.Embed.from_dict(base_embed_attacks.to_dict()) # Novo embed para o próximo campo
                current_field_value_attacks = item_line
                if len(current_field_value_attacks) > 1024: # Trunca item se ele sozinho for > 1024
                    current_field_value_attacks = current_field_value_attacks[:1021] + "...\n"
            else:
                current_field_value_attacks += item_line

        if current_field_value_attacks: # Adiciona o último campo/embed
            current_embed_attacks.add_field(name=field_name_attacks, value=current_field_value_attacks, inline=False)
        if current_embed_attacks.fields:
            embeds_to_send_attacks.append(current_embed_attacks)

    # Assegura que mesmo que a lista de ataques seja vazia, um embed é retornado.
    if not embeds_to_send_attacks and not members_with_attacks_list: # Caso especial: todos atacaram
        # O código acima já lida com isso adicionando embed_single a embeds_to_send_attacks
        pass
    elif not embeds_to_send_attacks and members_with_attacks_list: # Se a lógica de divisão falhar em adicionar algo
        logger.error("Falha ao popular embeds para ataques restantes, apesar de haver membros pendentes.")
        # Adicionar um embed de erro ou fallback
        error_embed = discord.Embed(title="Erro", description="Não foi possível formatar a lista de ataques restantes.", color=discord.Color.red())
        embeds_to_send_attacks.append(error_embed)


    for embed_item_rem in embeds_to_send_attacks: 
        if not hasattr(embed_item_rem, 'footer') or not hasattr(embed_item_rem.footer, 'text') or not embed_item_rem.footer.text:
             embed_item_rem.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        if not embed_item_rem.timestamp:
             embed_item_rem.timestamp = datetime.datetime.now(TIMEZONE)

    return embeds_to_send_attacks if embeds_to_send_attacks else None


async def send_missed_attacks_report(war: ClanWar,
                                    missed_members_details: List[str],
                                    war_type: str) -> None:
    # SEU CÓDIGO ORIGINAL AQUI (send_missed_attacks_report)
    # ...
    if not missed_members_details:
        return

    if not CHANNEL_ID or CHANNEL_ID == 0:
        logger.warning("CHANNEL_ID não configurado. Não é possível enviar relatório de ataques perdidos.")
        return

    content = None
    if ROLE_ID_MISSED_ATTACK:
        try:
            log_channel = await bot.fetch_channel(CHANNEL_ID)
            if log_channel and hasattr(log_channel, 'guild'):
                 guild = log_channel.guild
                 try:
                     role_id_int = int(ROLE_ID_MISSED_ATTACK)
                     role = guild.get_role(role_id_int)
                     if role:
                         content = f"{role.mention} Ataques Não Realizados!"
                     else:
                          logger.warning(f"Cargo para alerta de ataques perdidos (ID: {ROLE_ID_MISSED_ATTACK}) não encontrado no servidor.")
                 except (ValueError, TypeError):
                      logger.error(f"ROLE_ID_MISSED_ATTACK ('{ROLE_ID_MISSED_ATTACK}') é inválido.")
            else:
                 logger.warning(f"Não foi possível encontrar o servidor do canal de log (ID: {CHANNEL_ID}) para buscar o cargo.")

        except discord.Forbidden:
             logger.error(f"Sem permissão para buscar cargos no servidor do canal {CHANNEL_ID}.")
        except Exception as e:
            logger.error(f"Erro ao buscar cargo para alerta de ataques perdidos: {e}", exc_info=True)

    opponent_name = getattr(getattr(war, 'opponent', None), 'name', 'Oponente Desconhecido')

    start_time_local_str = "N/A"
    end_time_local_str = "N/A"

    if hasattr(war, 'start_time') and isinstance(war.start_time, Timestamp) and hasattr(war.start_time, 'time'):
        try:
            naive_start_time = war.start_time.time
            aware_start_time_utc = pytz.utc.localize(naive_start_time)
            aware_start_time_local = aware_start_time_utc.astimezone(TIMEZONE)
            start_time_local_str = aware_start_time_local.strftime('%d/%m/%Y %H:%M')
        except Exception as e:
            logger.error(f"Erro ao formatar start_time para relatório de ataques perdidos: {e}", exc_info=True)
            start_time_local_str = "Erro na data"
    else:
        logger.warning(f"war.start_time (ou .time) inválido para send_missed_attacks_report: Tipo {type(war.start_time)}")


    if hasattr(war, 'end_time') and isinstance(war.end_time, Timestamp) and hasattr(war.end_time, 'time'):
        try:
            naive_end_time = war.end_time.time
            aware_end_time_utc = pytz.utc.localize(naive_end_time)
            aware_end_time_local = aware_end_time_utc.astimezone(TIMEZONE)
            end_time_local_str = aware_end_time_local.strftime('%d/%m/%Y %H:%M')
        except Exception as e:
            logger.error(f"Erro ao formatar end_time para relatório de ataques perdidos: {e}", exc_info=True)
            end_time_local_str = "Erro na data"
    else:
        logger.warning(f"war.end_time (ou .time) inválido para send_missed_attacks_report: Tipo {type(war.end_time)}")


    description_text = (
        f"Membros que não usaram todos os ataques contra **{opponent_name}**.\n\n"
        f"**Data do Início da Guerra:** {start_time_local_str}\n"
        f"**Data do Fim da Guerra:** {end_time_local_str}"
    )

    base_embed_missed = discord.Embed(
        title=f"❌ Ataques Não Realizados - {war_type}",
        description=description_text,
        color=discord.Color.red()
    )
    if hasattr(war, 'opponent') and hasattr(war.opponent, 'badge') and war.opponent.badge:
         base_embed_missed.set_thumbnail(url=war.opponent.badge.url)

    try:
        channel_to_send = await bot.fetch_channel(CHANNEL_ID)
        if isinstance(channel_to_send, discord.TextChannel):
             if content: # Envia a menção do cargo primeiro, se houver
                  await channel_to_send.send(content)
             # Agora envia os embeds divididos
             await send_embeds_splitted(channel_to_send, base_embed_missed, "Membros", missed_members_details)
        else:
             logger.error(f"Canal de log ID {CHANNEL_ID} não é um canal de texto válido para relatório.")

    except discord.NotFound:
         logger.error(f"Canal de log ID {CHANNEL_ID} não encontrado para relatório.")
    except discord.Forbidden:
         logger.error(f"Sem permissão para enviar relatório de ataques perdidos no canal {CHANNEL_ID}.")
    except Exception as e:
        logger.error(f"Erro ao enviar relatório de ataques perdidos para o canal {CHANNEL_ID}: {e}", exc_info=True)


async def send_online_status():
    # SEU CÓDIGO ORIGINAL AQUI (send_online_status)
    # ...
    if not CHANNEL_ID or CHANNEL_ID == 0:
        logger.warning("CHANNEL_ID não configurado. Não é possível enviar status online.")
        return

    try:
        clan_name_status_online = "Clã Desconhecido" # Renomeado para evitar conflito
        clan_tag_formatted_status_online = CLAN_TAG if CLAN_TAG else "Nenhum"
        if CLAN_TAG and hasattr(bot, 'coc_client') and bot.coc_client.http: 
             try:
                  clan_data_status = await bot.coc_client.get_clan(CLAN_TAG) # Não usar cache aqui para status rápido
                  clan_name_status_online = clan_data_status.name
                  clan_tag_formatted_status_online = clan_data_status.tag
             except Exception as e:
                  logger.error(f"Erro ao buscar dados do clã para status online: {e}")

        embed_online = discord.Embed(
            title="✅ Bot Online e Monitorando!",
            description=f"Eventos do clã **{clan_name_status_online}** (`{clan_tag_formatted_status_online}`) e Guerras monitorados.",
            color=discord.Color.green()
        )
        embed_online.add_field(name="Monitoramento", value="Event-Driven Ativo 🔄", inline=False)
        await send_log_embed(embed_online)
        logger.info("Mensagem de status online enviada.")

    except Exception as e:
        logger.error(f"Erro ao enviar mensagem de status online: {e}", exc_info=True)


@bot.event
async def on_ready():
    # SEU CÓDIGO ORIGINAL AQUI (on_ready)
    # ...
    logger.info(f"Bot {bot.user.name} (ID: {bot.user.id}) conectado ao Discord!")
    logger.info(f"Versão discord.py: {discord.__version__}")
    logger.info(f"Versão coc.py: {coc.__version__}") # Assegure que coc.__version__ é acessível
    logger.info(f"Versão Bot: {BOT_VERSION}")
    logger.info(f"Pronto e operando em {len(bot.guilds)} servidor(es).")

    if hasattr(bot, 'coc_client') and bot.coc_client.http:
         logger.info("Cliente CoC parece estar pronto.")
         if not check_war_end_report_task.is_running():
              logger.info("Iniciando tarefa 'check_war_end_report_task'...")
              try:
                   check_war_end_report_task.start()
                   logger.info("Tarefa 'check_war_end_report_task' iniciada com sucesso.")
              except RuntimeError as e: # Captura erro se o loop não estiver pronto ou já iniciado
                   logger.error(f"Erro ao iniciar a tarefa 'check_war_end_report_task' (possivelmente já iniciada ou loop não pronto): {e}")
         else:
              logger.info("Tarefa 'check_war_end_report_task' já estava em execução.")
    else:
         logger.warning("Cliente CoC não parece estar pronto no on_ready. Tarefas em segundo plano podem não iniciar.")

    await send_online_status()


@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # SEU CÓDIGO ORIGINAL AQUI (on_app_command_error)
    # ...
    command_name = interaction.command.qualified_name if interaction.command else 'Comando Desconhecido'
    error_embed_cmd = discord.Embed(
        title="❌ Erro de Comando",
        color=discord.Color.red()
    )
    error_message = f"Ocorreu um erro inesperado: {str(error)}" # Mensagem padrão

    original_error = getattr(error, 'original', error) # Pega o erro original encapsulado

    # Trata erros específicos da API do CoC
    if isinstance(original_error, ValueError): # Erros de ValueError levantados manualmente
        error_message = str(original_error)
    elif isinstance(original_error, coc.NotFound):
        error_message = "Não foi possível encontrar o recurso solicitado no Clash of Clans."
    elif isinstance(original_error, coc.Maintenance):
        error_message = "A API do Clash of Clans está em manutenção. Tente novamente mais tarde."
    elif isinstance(original_error, coc.PrivateWarLog):
        error_message = "O registro de guerra deste clã é privado e não pode ser acessado."
    elif isinstance(original_error, asyncio.TimeoutError): # Erro de Timeout da API
         error_message = "Tempo limite excedido ao buscar dados da API do CoC. Tente novamente."
    elif isinstance(original_error, coc.InvalidCredentials): # Credenciais inválidas
         error_message = "Credenciais inválidas para a API do CoC detectadas."
    elif isinstance(original_error, coc.Forbidden): # Erro de acesso proibido (403)
         error_message = "Acesso proibido (Forbidden) à API do CoC. Verifique as permissões da chave."
    # Trata erros de comandos de aplicativo do Discord
    elif isinstance(error, app_commands.CommandSignatureMismatch):
         error_message = "Assinatura do comando desatualizada. Tente novamente em alguns instantes ou peça para sincronizar os comandos."
         logger.warning(f"CommandSignatureMismatch detectado para /{command_name}.")
    elif isinstance(error, app_commands.CheckFailure): # Falha em checagem de permissão
        error_message = "Você não tem permissão para usar este comando."
    elif isinstance(error, app_commands.CommandNotFound):
         error_message = "Comando não encontrado. Verifique se digitou corretamente."
    elif isinstance(error, app_commands.CommandOnCooldown):
        error_message = f"Este comando está em cooldown. Tente novamente em {error.retry_after:.1f} segundos."
    elif isinstance(error, app_commands.MissingRequiredArgument):
         param_name = getattr(error.param, 'display_name', getattr(error.param, 'name', 'desconhecido'))
         error_message = f"Argumento obrigatório faltando: `{param_name}`."
    elif isinstance(error, app_commands.BadArgument) or isinstance(error, app_commands.ArgumentParsingError):
         error_message = f"Argumento inválido fornecido. Verifique o tipo de dado esperado. ({str(error)})"
    else: # Erro genérico não tratado especificamente
        error_message = f"Ocorreu um erro interno ao processar o comando." # Mensagem mais genérica para o usuário
        logger.error(f"Erro não tratado no comando '{command_name}': {original_error}", exc_info=original_error)


    error_embed_cmd.description = error_message
    error_embed_cmd.set_footer(text=f"Comando: /{command_name}")
    error_embed_cmd.timestamp = datetime.datetime.now(TIMEZONE)

    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=error_embed_cmd, ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed_cmd, ephemeral=True)
    except discord.NotFound: # Se a interação não for mais válida
         logger.warning(f"Interação para o comando /{command_name} não encontrada ao tentar enviar mensagem de erro.")
    except discord.Forbidden: # Se o bot não tiver permissão para responder
         logger.warning(f"Sem permissão para enviar mensagem de erro na interação /{command_name}.")
    except Exception as e_send_error: # Outro erro ao tentar enviar a mensagem de erro
         logger.error(f"Erro ao enviar mensagem de erro da interação /{command_name}: {e_send_error}", exc_info=True)


async def register_coc_events(coc_client: coc.EventsClient): # Note que o tipo de coc_client é coc.EventsClient
    # SEU CÓDIGO ORIGINAL AQUI (register_coc_events e todos os @coc_client.event)
    # Apenas o @coc.WarEvents.war_attack foi modificado para usar o cache de jogador.
    # ...
    if not CLAN_TAG:
         logger.warning("CLAN_TAG não definido, eventos do clã não serão registrados.")
         return
    logger.info(f"Registrando manipuladores de eventos CoC para o clã {CLAN_TAG}...")

    @coc_client.event
    @coc.ClanEvents.member_join(tags=[CLAN_TAG])
    async def on_member_join(old_member: Optional[ClanMember], member: ClanMember):
        # ... (código original)
        logger.info(f"EVENTO DETECTADO: on_member_join para {getattr(member, 'tag', 'TAG DESCONHECIDA')}")
        if not member or not hasattr(member, 'clan'):
             logger.warning("Evento member_join recebido com objeto 'member' inválido ou sem clã.")
             return
        clan_obj_join = member.clan
        logger.info(f"Evento: {member.name} ({member.tag}) entrou no clã {clan_obj_join.name}.")
        embed_join = discord.Embed(
            title="👋 Novo Membro",
            description=f"**{member.name}** (`{member.tag}`) entrou no clã!",
            color=discord.Color.green()
        )
        embed_join.add_field(name="CV", value=getattr(member, 'town_hall', '?'), inline=True)
        embed_join.add_field(name="Nível", value=getattr(member, 'exp_level', '?'), inline=True)
        embed_join.add_field(name="Troféus", value=getattr(member, 'trophies', '?'), inline=True)
        if hasattr(member, 'league') and member.league:
            embed_join.add_field(name="Liga", value=member.league.name, inline=True)
        if hasattr(clan_obj_join, 'badge') and clan_obj_join.badge:
             embed_join.set_author(name=clan_obj_join.name, icon_url=clan_obj_join.badge.url)
             embed_join.set_thumbnail(url=clan_obj_join.badge.url)
        await send_log_embed(embed_join)


    @coc_client.event
    @coc.ClanEvents.member_leave(tags=[CLAN_TAG])
    async def on_member_leave(old_member: ClanMember, member: ClanMember): # 'member' aqui é o estado atual (geralmente vazio ou de outro clã)
        # ... (código original)
        logger.info(f"EVENTO DETECTADO: on_member_leave para {getattr(old_member, 'tag', 'TAG DESCONHECIDA DO MEMBRO QUE SAIU')}")
        # old_member contém o estado do membro ANTES de sair
        if not old_member: # Se old_member não for fornecido (raro, mas possível)
            logger.warning("Evento member_leave: 'old_member' (estado anterior do membro) não fornecido. Não é possível obter detalhes do membro que saiu.")
            # Pode tentar usar 'member' se for o caso, mas geralmente 'member' nesse evento é o novo estado (ex: sem clã)
            # Se 'member' for o objeto do membro que saiu mas com clan=None, podemos usá-lo.
            # if member and not hasattr(member, 'clan'): # Tentativa de usar 'member'
            #    leaving_member_name = getattr(member, 'name', 'Membro Desconhecido')
            #    # ... etc.
            return

        clan_obj_leave = old_member.clan if hasattr(old_member, 'clan') else None
        clan_name_leave = getattr(clan_obj_leave, 'name', 'Clã Desconhecido') # Nome do clã de onde saiu

        leaving_member_name = getattr(old_member, 'name', 'Membro Desconhecido')
        leaving_member_tag = getattr(old_member, 'tag', 'Tag Desconhecida')
        leaving_member_town_hall = getattr(old_member, 'town_hall', '?')
        leaving_member_exp_level = getattr(old_member, 'exp_level', '?')
        leaving_member_trophies = getattr(old_member, 'trophies', '?')
        leaving_member_league = getattr(old_member, 'league', None)
        league_name_leave = getattr(leaving_member_league, 'name', 'Sem Liga') if leaving_member_league else 'Sem Liga'

        logger.info(f"Evento: {leaving_member_name} ({leaving_member_tag}) saiu do clã {clan_name_leave}.")

        embed_leave = discord.Embed(
            title="👋 Membro Saiu",
            description=f"**{leaving_member_name}** (`{leaving_member_tag}`) saiu do clã!",
            color=discord.Color.red()
        )
        embed_leave.add_field(name="CV", value=leaving_member_town_hall, inline=True)
        embed_leave.add_field(name="Nível", value=leaving_member_exp_level, inline=True)
        embed_leave.add_field(name="Troféus", value=leaving_member_trophies, inline=True)
        embed_leave.add_field(name="Liga", value=league_name_leave, inline=True)

        # Tenta pegar o emblema do clã de onde o membro saiu
        if clan_obj_leave and hasattr(clan_obj_leave, 'badge') and clan_obj_leave.badge:
             embed_leave.set_author(name=clan_name_leave, icon_url=clan_obj_leave.badge.url)
             embed_leave.set_thumbnail(url=clan_obj_leave.badge.url)
        else: # Se não conseguir o emblema do clã (ex: clã não encontrado mais, ou old_member.clan é None)
            logger.warning(f"Não foi possível obter o emblema do clã {clan_name_leave} ({getattr(clan_obj_leave, 'tag', 'TAG CLÃ DESCONHECIDA')}) para o evento de saída de {leaving_member_name} ({leaving_member_tag}).")
            # Pode tentar usar o emblema do clã do bot se fizer sentido como fallback
            # current_bot_clan = await get_clan_data_with_cache(CLAN_TAG) # Cuidado com await em eventos síncronos (não é o caso aqui)
            # if current_bot_clan and hasattr(current_bot_clan, 'badge'):
            #     embed_leave.set_author(name=current_bot_clan.name, icon_url=current_bot_clan.badge.url)


        await send_log_embed(embed_leave)

    @coc_client.event
    @coc.ClanEvents.member_donations(tags=[CLAN_TAG])
    async def on_member_donations(old_member: ClanMember, member: ClanMember):
        # ... (código original)
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan_obj_don = member.clan # Clã atual do membro
        old_donations = getattr(old_member, 'donations', 0)
        new_donations = getattr(member, 'donations', 0)
        donation_difference = new_donations - old_donations
        if donation_difference <= 0: return # Apenas notifica se houver aumento
        logger.info(f"Evento: {member.name} doou {donation_difference} tropas (Total: {new_donations}).")
        embed_don = discord.Embed(color=discord.Color.green())
        if hasattr(clan_obj_don, 'badge') and clan_obj_don.badge:
             embed_don.set_author(name=clan_obj_don.name, icon_url=clan_obj_don.badge.url)
             embed_don.set_thumbnail(url=clan_obj_don.badge.url)
        embed_don.add_field(name="🎁 Doação",
                         value=f"**{donation_difference}** tropas por `{member.name}` (Total doado: {new_donations})", inline=False)
        await send_log_embed(embed_don)


    @coc_client.event
    @coc.ClanEvents.member_received(tags=[CLAN_TAG])
    async def on_member_received(old_member: ClanMember, member: ClanMember):
        # ... (código original)
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan_obj_rec = member.clan
        old_received = getattr(old_member, 'received', 0)
        new_received = getattr(member, 'received', 0)
        received_difference = new_received - old_received
        if received_difference <= 0: return
        logger.info(f"Evento: {member.name} recebeu {received_difference} tropas (Total: {new_received}).")
        embed_rec = discord.Embed(color=discord.Color.blue())
        if hasattr(clan_obj_rec, 'badge') and clan_obj_rec.badge:
            embed_rec.set_author(name=clan_obj_rec.name, icon_url=clan_obj_rec.badge.url)
            embed_rec.set_thumbnail(url=clan_obj_rec.badge.url)
        embed_rec.add_field(name="📥 Recebimento",
                         value=f"`{member.name}` recebeu **{received_difference}** tropas (Total recebido: {new_received})", inline=False)
        await send_log_embed(embed_rec)


    @coc_client.event
    @coc.ClanEvents.member_role_change(tags=[CLAN_TAG])
    async def on_member_role_change(old_member: ClanMember, member: ClanMember):
        # ... (código original)
        logger.info(f"EVENTO DETECTADO: on_member_role_change para {getattr(member, 'tag', 'TAG DESCONHECIDA')}")
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan_obj_role = member.clan
        old_role_obj = getattr(old_member, 'role', None) # Renomeado para clareza
        new_role_obj = getattr(member, 'role', None)   # Renomeado para clareza
        
        # Compara os nomes dos cargos, pois os objetos de cargo podem ser diferentes instâncias mesmo se o cargo for o mesmo
        old_role_name = old_role_obj.name if old_role_obj else None
        new_role_name = new_role_obj.name if new_role_obj else None

        if old_role_name == new_role_name: return # Sem mudança real no cargo
        
        logger.info(f"Evento: Cargo de {member.name} mudou de {old_role_name} para {new_role_name} em {clan_obj_role.name}.")
        embed_role_change = discord.Embed( # Renomeado para evitar conflito
            title="🔄 Mudança de Cargo",
            description=f"Cargo de **{member.name}** (`{member.tag}`) foi alterado!",
            color=discord.Color.gold()
        )
        embed_role_change.add_field(name="Cargo Anterior", value=old_role_name.capitalize() if old_role_name else 'N/A', inline=True)
        embed_role_change.add_field(name="Novo Cargo", value=new_role_name.capitalize() if new_role_name else 'N/A', inline=True)
        if hasattr(clan_obj_role, 'badge') and clan_obj_role.badge:
             embed_role_change.set_author(name=clan_obj_role.name, icon_url=clan_obj_role.badge.url)
             embed_role_change.set_thumbnail(url=clan_obj_role.badge.url)
        await send_log_embed(embed_role_change)


    @coc_client.event
    @coc.ClanEvents.member_league_change(tags=[CLAN_TAG])
    async def on_member_league_change(old_member: ClanMember, member: ClanMember):
        # ... (código original)
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan_obj_league_event = member.clan # Renomeado
        old_league_obj = getattr(old_member, 'league', None) # Renomeado
        new_league_obj = getattr(member, 'league', None)   # Renomeado

        old_league_name_event = old_league_obj.name if old_league_obj else "Sem Liga"
        new_league_name_event = new_league_obj.name if new_league_obj else "Sem Liga"

        if old_league_name_event == new_league_name_event: return # Sem mudança real na liga

        logger.info(f"Evento: Liga de {member.name} mudou de {old_league_name_event} para {new_league_name_event} em {clan_obj_league_event.name}.")
        
        embed_league_evt = discord.Embed(
            title="🏆 Mudança de Liga",
            description=f"Liga de **{member.name}** (`{member.tag}`) foi alterada!",
            color=discord.Color.purple()
        )
        embed_league_evt.add_field(name="Liga Anterior", value=old_league_name_event, inline=True)
        embed_league_evt.add_field(name="Nova Liga", value=new_league_name_event, inline=True)
        if hasattr(clan_obj_league_event, 'badge') and clan_obj_league_event.badge:
             embed_league_evt.set_author(name=clan_obj_league_event.name, icon_url=clan_obj_league_event.badge.url)
             embed_league_evt.set_thumbnail(url=clan_obj_league_event.badge.url)
        await send_log_embed(embed_league_evt)


    @coc_client.event
    @coc.ClanEvents.member_trophies_change(tags=[CLAN_TAG])
    async def on_member_trophies_change(old_member: ClanMember, member: ClanMember):
        # ... (código original)
        if not member or not old_member:
             logger.warning("Evento member_trophies_change recebido com objeto 'member' ou 'old_member' inválido.")
             return
        old_trophies = getattr(old_member, 'trophies', 0)
        new_trophies = getattr(member, 'trophies', 0)
        trophy_difference = new_trophies - old_trophies

        if abs(trophy_difference) < 5: return # Ignora pequenas flutuações
        logger.info(f"Evento: Troféus de {member.name} mudaram em {trophy_difference} (Total: {new_trophies}).")
        direction = "ganhou" if trophy_difference > 0 else "perdeu"
        embed_trophies_event = discord.Embed( # Renomeado
            description=f"**{member.name}** {direction} **{abs(trophy_difference)}** troféus (Total: {new_trophies})",
            color=discord.Color.green() if trophy_difference > 0 else discord.Color.dark_red()
        )
        # Adicionar autor/thumbnail do clã se desejado
        # if hasattr(member, 'clan') and member.clan and hasattr(member.clan, 'badge'):
        #    embed_trophies_event.set_author(name=member.clan.name, icon_url=member.clan.badge.url)
        await send_log_embed(embed_trophies_event)

    @coc_client.event
    @coc.WarEvents.war_attack(tags=[CLAN_TAG])
    async def on_war_attack(attack: WarAttack, war: ClanWar):
        if not all(hasattr(attack, attr) for attr in ['attacker_tag', 'defender_tag', 'stars', 'destruction', 'order']):
            logger.warning(f"Evento de ataque de guerra recebido com dados incompletos. War Tag: {getattr(war, 'tag', 'N/A')}")
            return

        is_our_attack = False
        is_our_defense = False
        attacker_clan_tag = None
        defender_clan_tag = None
        attacker_player_obj = None # Renomeado
        defender_player_obj = None # Renomeado
        
        player_short_term_cache.clear() # Limpa cache de curto prazo para este evento

        try:
             attacker_player_obj = await get_player_data_with_short_term_cache(attack.attacker_tag)
             defender_player_obj = await get_player_data_with_short_term_cache(attack.defender_tag)
             attacker_clan_tag = getattr(attacker_player_obj.clan, 'tag', None) if hasattr(attacker_player_obj, 'clan') and attacker_player_obj.clan else None
             defender_clan_tag = getattr(defender_player_obj.clan, 'tag', None) if hasattr(defender_player_obj, 'clan') and defender_player_obj.clan else None
        except ValueError as e: # Erro de get_player_data_with_short_term_cache
             logger.warning(f"Não foi possível buscar dados do atacante ({attack.attacker_tag}) ou defensor ({attack.defender_tag}) para ataque de guerra {attack.order}: {e}")
             # Continuar sem dados do jogador se um não for encontrado, usando tags como fallback
        except Exception as e:
             logger.error(f"Erro inesperado ao buscar dados atacante/defensor para ataque de guerra {attack.order}: {e}", exc_info=True)
             return # Aborta se for um erro inesperado grave

        # Determinar se é nosso ataque ou defesa
        # Normaliza CLAN_TAG para garantir que não tenha '#' para comparação, se necessário
        # (CLAN_TAG já deve estar formatado corretamente)
        
        # Verifica se o atacante pertence ao nosso clã
        if attacker_clan_tag and attacker_clan_tag == CLAN_TAG:
             is_our_attack = True
        # Verifica se o defensor pertence ao nosso clã
        elif defender_clan_tag and defender_clan_tag == CLAN_TAG:
             is_our_defense = True
        # Se não pudermos determinar os clãs (ex: jogadores sem clã no momento da busca), logar e possivelmente ignorar
        elif attacker_clan_tag is None and defender_clan_tag is None:
             logger.warning(f"Clãs do atacante E defensor desconhecidos para o ataque {attack.order}. Atacante: {attack.attacker_tag}, Defensor: {attack.defender_tag}.")
             return # Ignora se ambos os clãs são desconhecidos
        elif attacker_clan_tag is None and defender_clan_tag != CLAN_TAG: # Atacante sem clã, defensor não é nosso
            logger.debug(f"Ataque {attack.order}: Atacante sem clã, defensor ({defender_clan_tag}) não é o nosso. Ignorando.")
            return
        elif defender_clan_tag is None and attacker_clan_tag != CLAN_TAG: # Defensor sem clã, atacante não é nosso
            logger.debug(f"Ataque {attack.order}: Defensor sem clã, atacante ({attacker_clan_tag}) não é o nosso. Ignorando.")
            return
        else: # Nenhum dos clãs envolvidos é o nosso (CLAN_TAG)
             # logger.debug(f"Ataque de guerra ({attack.order}) não envolve o clã {CLAN_TAG}. Attacker: {attacker_clan_tag}, Defender: {defender_clan_tag}")
             return # Ignora se não for do nosso clã

        attacker_name = getattr(attacker_player_obj, 'name', attack.attacker_tag) if attacker_player_obj else attack.attacker_tag
        defender_name = getattr(defender_player_obj, 'name', attack.defender_tag) if defender_player_obj else attack.defender_tag
        attacker_th = getattr(attacker_player_obj, 'town_hall', '?') if attacker_player_obj else '?'
        defender_th = getattr(defender_player_obj, 'town_hall', '?') if defender_player_obj else '?'

        stars_str = "⭐" * attack.stars + "⚫" * (3 - attack.stars)
        content_for_discord_attack = None # Renomeado para clareza

        if is_our_attack:
            logger.info(f"Evento Guerra: {attacker_name} atacou {defender_name} - {attack.stars} estrelas, {attack.destruction}% destruição.")
            embed_discord_attack = discord.Embed( # Renomeado
                title=f"⚔️ Ataque Realizado (Guerra)",
                description=f"**{attacker_name}** (CV{attacker_th}) atacou **{defender_name}** (CV{defender_th})",
                color=discord.Color.blue()
            )
            embed_discord_attack.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)

            if attack.stars <= 1 and ROLE_ID_1STAR_ALERT:
                try:
                    log_channel_attack_alert = await bot.fetch_channel(CHANNEL_ID) # Renomeado
                    if log_channel_attack_alert and hasattr(log_channel_attack_alert, 'guild'):
                         guild_attack_alert = log_channel_attack_alert.guild # Renomeado
                         try:
                              role_id_int_attack_alert = int(ROLE_ID_1STAR_ALERT) # Renomeado
                              role_attack_alert = guild_attack_alert.get_role(role_id_int_attack_alert) # Renomeado
                              if role_attack_alert: content_for_discord_attack = f"{role_attack_alert.mention} ⚠️ Atenção: ataque fora do padrão detectado!"
                              else: logger.warning(f"Cargo para alerta de 1 estrela (ID: {ROLE_ID_1STAR_ALERT}) não encontrado.")
                         except (ValueError, TypeError): logger.error(f"ROLE_ID_1STAR_ALERT ('{ROLE_ID_1STAR_ALERT}') é inválido.")
                    else: logger.warning("Não foi possível buscar o servidor do canal de log para alerta de 1 estrela.")
                except Exception as e_alert: logger.error(f"Erro ao buscar cargo para alerta de 1 estrela: {e_alert}", exc_info=True)

            # Tenta usar war.clan (que deve ser o nosso clã) para o emblema
            our_clan_obj_in_war_event = war.clan
            if hasattr(war, 'clan') and war.clan.tag != CLAN_TAG and hasattr(war, 'opponent') and war.opponent.tag == CLAN_TAG:
                our_clan_obj_in_war_event = war.opponent # Se o nosso clã for o 'opponent'
            
            if hasattr(our_clan_obj_in_war_event, 'badge') and our_clan_obj_in_war_event.badge:
                 embed_discord_attack.set_author(name=our_clan_obj_in_war_event.name, icon_url=our_clan_obj_in_war_event.badge.url)
                 embed_discord_attack.set_thumbnail(url=our_clan_obj_in_war_event.badge.url)
            await send_log_embed(embed_discord_attack, content_for_discord_attack)

        elif is_our_defense:
            logger.info(f"Evento Guerra: {defender_name} foi atacado por {attacker_name} - {attack.stars} estrelas, {attack.destruction}% destruição.")
            embed_discord_defense = discord.Embed( # Renomeado
                title=f"🛡️ Defesa Recebida (Guerra)",
                description=f"**{defender_name}** (CV{defender_th}) foi atacado por **{attacker_name}** (CV{attacker_th})",
                color=discord.Color.orange()
            )
            embed_discord_defense.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
            
            # Para defesa, o emblema do oponente (que nos atacou)
            if hasattr(war, 'opponent') and hasattr(war.opponent, 'badge') and war.opponent.badge:
                 # Se o nosso clã for 'opponent' no objeto war, então war.clan é o inimigo
                 enemy_clan_obj = war.opponent
                 if hasattr(war, 'clan') and war.clan.tag != CLAN_TAG and hasattr(war, 'opponent') and war.opponent.tag == CLAN_TAG:
                     enemy_clan_obj = war.clan # O inimigo é war.clan
                 
                 if hasattr(enemy_clan_obj, 'badge') and enemy_clan_obj.badge:
                    embed_discord_defense.set_author(name=enemy_clan_obj.name, icon_url=enemy_clan_obj.badge.url)
                    embed_discord_defense.set_thumbnail(url=enemy_clan_obj.badge.url)

            await send_log_embed(embed_discord_defense)


    logger.info("Manipuladores de eventos CoC registrados.")


@tasks.loop(minutes=10) # Intervalo da task
async def check_war_end_report_task():
    # SEU CÓDIGO ORIGINAL AQUI (check_war_end_report_task)
    # A lógica interna de process_war_for_report e a busca por guerras CWL/Regular foi mantida
    # Apenas pequenas adaptações de log ou nomenclatura podem ter sido feitas acima.
    # ...
    if not bot.coc_client or not bot.coc_client.http:
         logger.debug("check_war_end_report_task: Cliente CoC não pronto, pulando ciclo.")
         return

    logger.debug("check_war_end_report_task: Iniciando verificação de fim de guerra...")
    processed_war_ids_this_cycle: Set[str] = set() # Renomeado para clareza do escopo

    async def process_war_for_report(war_obj: ClanWar, war_type_name: str):
        war_id_str = None
        # Tenta criar um ID único para a guerra com base no oponente e tempo de fim
        # Se for CWL, war.tag (da guerra específica da liga) pode ser mais único.
        if hasattr(war_obj, 'tag') and war_obj.tag: # Para guerras da liga que têm tag própria
            war_id_str = war_obj.tag
        elif hasattr(war_obj, 'opponent') and war_obj.opponent and hasattr(war_obj.opponent, 'tag') and \
           hasattr(war_obj, 'end_time') and war_obj.end_time and hasattr(war_obj.end_time, 'raw_time'):
            war_id_str = f"REGULAR-{war_obj.opponent.tag}-{war_obj.end_time.raw_time}" # Adiciona prefixo
        else:
            logger.warning(f"check_war_end_report_task: Não foi possível gerar ID estável para guerra {war_type_name}. Pulando.")
            return

        if war_id_str in processed_war_ids_this_cycle: # Evita reprocessar na mesma execução da task
            logger.debug(f"check_war_end_report_task: Guerra {war_id_str} ({war_type_name}) já processada neste ciclo. Pulando.")
            return
        
        opponent_name_proc = getattr(getattr(war_obj, 'opponent', None), 'name', 'Oponente Desconhecido')
        war_state_proc = getattr(war_obj, 'state', 'unknown')
        logger.debug(f"check_war_end_report_task: Processando para relatório: {war_type_name} contra {opponent_name_proc} (ID: {war_id_str}, Estado: {war_state_proc})")

        if war_state_proc == "warEnded" and war_id_str not in reported_war_ends: # reported_war_ends é o cache global
            logger.info(f"check_war_end_report_task: Guerra '{war_type_name}' contra {opponent_name_proc} terminou (ID: {war_id_str}). Verificando ataques perdidos...")

            our_clan_obj_for_report = None
            if war_obj.clan and war_obj.clan.tag == CLAN_TAG:
                our_clan_obj_for_report = war_obj.clan
            elif war_obj.opponent and war_obj.opponent.tag == CLAN_TAG:
                our_clan_obj_for_report = war_obj.opponent
            
            if not our_clan_obj_for_report:
                 logger.error(f"check_war_end_report_task: Não foi possível identificar nosso clã na guerra {war_id_str} para relatório.")
                 processed_war_ids_this_cycle.add(war_id_str) # Marca como processado para este ciclo
                 return

            attacks_per_member_report = war_obj.attacks_per_member

            missed_members_details_task = []
            if hasattr(our_clan_obj_for_report, 'members') and our_clan_obj_for_report.members:
                 for member_proc in our_clan_obj_for_report.members:
                    if not member_proc or not hasattr(member_proc, 'tag'): continue
                    attacks_used_task = len(member_proc.attacks) if hasattr(member_proc, "attacks") and member_proc.attacks else 0
                    if attacks_used_task < attacks_per_member_report:
                        missed_count_task = attacks_per_member_report - attacks_used_task
                        member_name_proc = getattr(member_proc, 'name', member_proc.tag)
                        member_th_proc = getattr(member_proc, 'town_hall', '?')
                        missed_members_details_task.append(
                            f"**{member_name_proc}** (CV{member_th_proc}): {missed_count_task} perdido{'s' if missed_count_task > 1 else ''}"
                        )
            else:
                 logger.warning(f"check_war_end_report_task: Clã '{getattr(our_clan_obj_for_report, 'name', 'N/A')}' na guerra {war_id_str} não possui lista de membros.")

            if missed_members_details_task:
                logger.info(f"check_war_end_report_task: {len(missed_members_details_task)} membro(s) perderam ataques na guerra {war_type_name} (ID: {war_id_str}).")
                await send_missed_attacks_report(war_obj, missed_members_details_task, war_type_name)
            else:
                logger.info(f"check_war_end_report_task: Nenhum ataque perdido na guerra {war_type_name} (ID: {war_id_str}).")

            reported_war_ends.add(war_id_str) # Adiciona ao cache global de guerras reportadas
            logger.debug(f"check_war_end_report_task: Guerra {war_id_str} marcada como reportada para ataques perdidos.")
        
        processed_war_ids_this_cycle.add(war_id_str) 
    
    # Processar Guerra Regular
    try:
        logger.debug("check_war_end_report_task: Buscando guerra regular...")
        current_war_reg = await bot.coc_client.get_current_war(CLAN_TAG)
        if current_war_reg and hasattr(current_war_reg, 'state') and current_war_reg.state != "notInWar":
             if hasattr(current_war_reg, 'end_time'): 
                  await process_war_for_report(current_war_reg, "Guerra Normal")
             else:
                  logger.warning("check_war_end_report_task: Objeto de guerra regular inválido (sem end_time).")
    except coc.PrivateWarLog:
        logger.warning("check_war_end_report_task: Log de guerra regular é privado.")
    except coc.NotFound:
         logger.info("check_war_end_report_task: Clã não encontrado ao buscar guerra regular.")
    except Exception as e:
        logger.error(f"check_war_end_report_task: Erro ao buscar/processar guerra regular: {e}", exc_info=True)

    # Processar Guerras da CWL
    try:
        logger.debug("check_war_end_report_task: Buscando grupo de liga (CWL)...")
        league_group_cwl_task = await bot.coc_client.get_league_group(CLAN_TAG) # Renomeado
        if league_group_cwl_task and hasattr(league_group_cwl_task, 'state') and league_group_cwl_task.state != "notInWar":
            if hasattr(league_group_cwl_task, 'rounds') and league_group_cwl_task.rounds:
                 for round_num_cwl, war_tags_cwl_round in enumerate(league_group_cwl_task.rounds): # Renomeado
                     for war_tag_cwl_item in war_tags_cwl_round: # Renomeado
                         if war_tag_cwl_item == "#0": continue # Ignora "bye" rounds
                         try:
                             league_war_obj_task = await league_group_cwl_task.get_league_war(war_tag_cwl_item) # Renomeado
                             if not league_war_obj_task or not hasattr(league_war_obj_task, 'state') or not hasattr(league_war_obj_task, 'end_time'):
                                  logger.warning(f"check_war_end_report_task: Objeto da guerra da liga {war_tag_cwl_item} inválido.")
                                  continue
                             
                             if league_war_obj_task.clan.tag == CLAN_TAG or league_war_obj_task.opponent.tag == CLAN_TAG:
                                 await process_war_for_report(league_war_obj_task, f"Liga de Clãs (Rodada {round_num_cwl + 1})")
                         except coc.NotFound:
                              logger.warning(f"check_war_end_report_task: Guerra da liga {war_tag_cwl_item} não encontrada.")
                         except Exception as e_cwl_war_task: # Renomeado
                              logger.error(f"check_war_end_report_task: Erro ao buscar/processar guerra da liga {war_tag_cwl_item}: {e_cwl_war_task}", exc_info=True)
    except coc.NotFound:
         logger.info("check_war_end_report_task: Clã não encontrado ao buscar grupo de liga (CWL).")
    except Exception as e:
        logger.error(f"check_war_end_report_task: Erro ao buscar/processar grupo de liga (CWL): {e}", exc_info=True)

    logger.debug("check_war_end_report_task: Verificação de fim de guerra concluída.")


@check_war_end_report_task.before_loop
async def before_check_war():
    # SEU CÓDIGO ORIGINAL AQUI (before_check_war)
    # ...
    logger.info("Aguardando o bot ficar pronto para iniciar a tarefa 'check_war_end_report_task'...")
    await bot.wait_until_ready()
    logger.info("Bot pronto. Tarefa 'check_war_end_report_task' pode iniciar.")

# Slash command groups (SEU CÓDIGO ORIGINAL)
admin_group = app_commands.Group(name="admin", description="Comandos administrativos")
war_group = app_commands.Group(name="guerra", description="Comandos relacionados a guerras")
info_group = app_commands.Group(name="info", description="Comandos de informação")
search_group = app_commands.Group(name="buscar", description="Comandos de busca")
rank_group = app_commands.Group(name="rank", description="Comandos de ranking")

bot.tree.add_command(admin_group)
bot.tree.add_command(war_group)
bot.tree.add_command(info_group)
bot.tree.add_command(search_group)
bot.tree.add_command(rank_group)

# Slash commands (TODOS OS SEUS COMANDOS SLASH ORIGINAIS DEVEM ESTAR AQUI)
# OMITIDOS PARA BREVIDADE, MAS DEVEM SER MANTIDOS NO SEU ARQUIVO.
# Exemplo de um comando (mantenha todos os seus):
@admin_group.command(name="ping", description="Verifica a latência do bot")
@app_commands.checks.has_permissions(administrator=True)
async def admin_ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    embed_ping = discord.Embed(
        title="🏓 Pong!",
        description=f"Latência da API do Discord: **{latency_ms}ms**",
        color=discord.Color.green() if latency_ms < 200 else discord.Color.orange() if latency_ms < 500 else discord.Color.red()
    )
    embed_ping.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
    embed_ping.timestamp = datetime.datetime.now(TIMEZONE)
    await interaction.response.send_message(embed=embed_ping, ephemeral=True)

# ... (COLE AQUI TODOS OS SEUS OUTROS COMANDOS SLASH: war_attacks, war_status, clan_info, player_info, etc.) ...
# O comando /info jogador usava get_player_data. Ele foi renomeado para get_player_data_with_short_term_cache.
# Vamos ajustar o comando /info jogador para usar a nova função.
# Se você tiver um get_player_data separado que não usa cache, pode mantê-lo, ou renomear
# get_player_data_with_short_term_cache para get_player_data se ele for o principal agora.
# Para consistência, vou assumir que a função com cache deve ser usada:

@info_group.command(name="jogador", description="Exibe informações sobre um jogador")
@app_commands.describe(tag="Tag do jogador (Ex: #P0LGYC9YQ)")
async def player_info(interaction: discord.Interaction, tag: str):
    try:
        await interaction.response.defer()
        player_short_term_cache.clear() # Limpa cache antes desta chamada específica se desejar sempre dados frescos para o comando
        player_data_info = await get_player_data_with_short_term_cache(tag) # Usando a função com cache

        embed_player_info = discord.Embed(
            title=f"{player_data_info.name} ({player_data_info.tag})",
            color=discord.Color.green()
        )
        if hasattr(player_data_info, 'league') and player_data_info.league and hasattr(player_data_info.league, 'icon') and hasattr(player_data_info.league.icon, 'url'):
             embed_player_info.set_thumbnail(url=player_data_info.league.icon.url)

        basic_info_player = [
             f"**CV:** {getattr(player_data_info, 'town_hall', '?')}",
             f"**Nível:** {getattr(player_data_info, 'exp_level', '?')}",
             f"**Liga:** {getattr(player_data_info.league, 'name', 'Sem Liga')}" if hasattr(player_data_info, 'league') and player_data_info.league else "Sem Liga",
             f"**Troféus:** {getattr(player_data_info, 'trophies', '?')}🏆",
             f"**Recorde:** {getattr(player_data_info, 'best_trophies', '?')}🏆"
        ]
        embed_player_info.add_field(name="Informações Básicas", value="\n".join(basic_info_player), inline=True)

        clan_info_parts_player = ["**Clã:** Sem Clã"]
        if hasattr(player_data_info, 'clan') and player_data_info.clan:
            clan_name_player = getattr(player_data_info.clan, 'name', 'Nome Desconhecido')
            clan_level_player = getattr(player_data_info.clan, 'level', '?')
            player_role_obj_player = getattr(player_data_info, 'role', None)
            clan_role_player = player_role_obj_player.name.capitalize() if player_role_obj_player and hasattr(player_role_obj_player, 'name') else 'Membro'
            clan_info_parts_player = [
                 f"**Clã:** {clan_name_player}",
                 f"**Nível Clã:** {clan_level_player}",
                 f"**Cargo:** {clan_role_player}"
            ]
        embed_player_info.add_field(name="Clã", value="\n".join(clan_info_parts_player), inline=True)

        stats_player = []
        if hasattr(player_data_info, "war_stars"): stats_player.append(f"**Estrelas Guerra:** {player_data_info.war_stars}⭐")
        if hasattr(player_data_info, "attack_wins"): stats_player.append(f"**Ataques Vencidos:** {player_data_info.attack_wins}")
        if hasattr(player_data_info, "defense_wins"): stats_player.append(f"**Defesas Vencidas:** {player_data_info.defense_wins}")
        if hasattr(player_data_info, "donations"): stats_player.append(f"**Tropas Doadas:** {player_data_info.donations}")
        if hasattr(player_data_info, "received"): stats_player.append(f"**Tropas Recebidas:** {player_data_info.received}")
        if hasattr(player_data_info, 'builder_base_trophies'): stats_player.append(f"**Troféus BC:** {player_data_info.builder_base_trophies}🏆")
        if hasattr(player_data_info, 'best_builder_base_trophies'): stats_player.append(f"**Recorde BC:** {player_data_info.best_builder_base_trophies}🏆")

        if stats_player:
             if len(stats_player) > 4: # Divide em duas colunas se muitas estatísticas
                  mid_player = len(stats_player) // 2 + (len(stats_player) % 2)
                  col1_player = "\n".join(stats_player[:mid_player])
                  col2_player = "\n".join(stats_player[mid_player:])
                  if len(col1_player) <= 1024: embed_player_info.add_field(name="Estatísticas (1/2)", value=col1_player, inline=True)
                  if len(col2_player) <= 1024: embed_player_info.add_field(name="Estatísticas (2/2)", value=col2_player, inline=True)
             elif len("\n".join(stats_player)) <= 1024: # Se couber em uma coluna
                  embed_player_info.add_field(name="Estatísticas", value="\n".join(stats_player), inline=False)
        
        if hasattr(player_data_info, 'heroes'):
            heroes_home_player = []
            heroes_builder_player = []
            for hero_player in player_data_info.heroes:
                hero_name_player = getattr(hero_player, 'name', '?')
                hero_level_player = getattr(hero_player, 'level', '?')
                hero_max_player = getattr(hero_player, 'max_level', '?')
                if hero_level_player == 0 or hero_level_player == '?': continue # Ignora heróis não desbloqueados
                hero_line_player = f"{hero_name_player}: **{hero_level_player}**/{hero_max_player}"
                # Verifica se o herói pertence à base principal ou à do construtor
                # A propriedade is_home_base pode não existir em todas as versões ou para todos os heróis.
                # Uma heurística comum é verificar o nome do herói ou se tem 'is_builder_base'.
                # coc.py geralmente tem `hero.is_home_base`
                if getattr(hero_player, 'is_home_base', True): # Assume base principal por padrão se não especificado
                    heroes_home_player.append(hero_line_player)
                else:
                    heroes_builder_player.append(hero_line_player)

            if heroes_home_player:
                home_text_player = "\n".join(heroes_home_player)
                if len(home_text_player) <= 1024: embed_player_info.add_field(name="Heróis (Base Principal)", value=home_text_player, inline=True)
            if heroes_builder_player:
                 builder_text_player = "\n".join(heroes_builder_player)
                 if len(builder_text_player) <= 1024: embed_player_info.add_field(name="Heróis (Base Construtor)", value=builder_text_player, inline=True)


        embed_player_info.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        embed_player_info.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed_player_info)

    except ValueError as e_val: # Captura ValueError de get_player_data_with_short_term_cache
         await interaction.followup.send(str(e_val), ephemeral=True)
    except Exception as e_gen: # Captura outros erros
        logger.error(f"Erro ao buscar informações do jogador {tag}: {e_gen}", exc_info=True)
        await interaction.followup.send("Ocorreu um erro ao buscar informações do jogador.", ephemeral=True)
# Certifique-se de que TODOS os seus outros comandos slash estão aqui e funcionais.

async def setup_hook():
    # SEU CÓDIGO ORIGINAL AQUI (setup_hook)
    # A parte importante é que `bot.web_runner = await setup_web_server()` seja chamada.
    # ...
    logger.info("Executando setup_hook...")

    logger.info("Inicializando cliente CoC...")
    bot.coc_client = coc.EventsClient() # Assegure que é coc.EventsClient se você usa eventos
    max_retries = 3
    retry_delay = 5 # segundos
    login_success = False
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentativa de login CoC ({attempt + 1}/{max_retries})...")
            if not COC_EMAIL or not COC_PASSWORD:
                 logger.error("COC_EMAIL ou COC_PASSWORD não definidos no ambiente. Login CoC abortado.")
                 break 
            await bot.coc_client.login(COC_EMAIL, COC_PASSWORD)
            logger.info("Login CoC bem-sucedido!")
            login_success = True
            break 
        except coc.InvalidCredentials as e_creds:
             logger.error(f"Login CoC Falhou: Credenciais Inválidas. Verifique COC_EMAIL/COC_PASSWORD. {e_creds}")
             break 
        except coc.Maintenance as e_maint:
             logger.warning(f"API CoC em manutenção: {e_maint}. Funcionalidades CoC estarão indisponíveis.")
             break # Não adianta tentar de novo se estiver em manutenção
        except asyncio.TimeoutError:
             logger.error(f"Timeout no login CoC (Tentativa {attempt + 1}).")
             if attempt < max_retries - 1: await asyncio.sleep(retry_delay)
        except Exception as e_login: # Outros erros de login
             logger.error(f"Erro inesperado no login CoC (Tentativa {attempt + 1}): {e_login}", exc_info=True)
             if attempt < max_retries - 1: await asyncio.sleep(retry_delay)

    if not login_success:
         logger.error("Não foi possível logar no CoC após todas as tentativas ou devido a erro/manutenção.")
         # O bot pode continuar rodando para comandos Discord que não usam CoC, ou você pode optar por pará-lo.
    else:
         logger.info("Registrando listeners de eventos CoC...")
         await register_coc_events(bot.coc_client) # Passa o cliente CoC para o registro
         if CLAN_TAG:
             logger.info(f"Adicionando atualizações de eventos para o clã: {CLAN_TAG}")
             try:
                  bot.coc_client.add_clan_updates(CLAN_TAG)
                  bot.coc_client.add_war_updates(CLAN_TAG) # Se você quer eventos de guerra
                  logger.info("Atualizações de clã e guerra ativadas.")
             except Exception as e_updates:
                  logger.error(f"Erro ao adicionar atualizações de eventos para {CLAN_TAG}: {e_updates}", exc_info=True)
         else:
              logger.warning("CLAN_TAG não definido. Atualizações de eventos CoC não ativadas.")

    logger.info("Configurando servidor web para painel...") 
    bot.web_runner = await setup_web_server() # Esta linha é crucial
    if bot.web_runner:
        logger.info("Servidor web configurado.")
    else:
        logger.warning("Falha ao configurar o servidor web.")

    logger.info("Tentando sincronizar comandos de aplicativo (/) no setup_hook...")
    synced_commands_list_hook = [] # Para armazenar os comandos sincronizados
    try:
        if TEST_GUILD_ID: # Se um ID de servidor de teste for fornecido
            try:
                guild_id_obj_hook = discord.Object(id=int(TEST_GUILD_ID))
                logger.info(f"Copiando comandos globais para o servidor de teste ID: {TEST_GUILD_ID} e sincronizando...")
                bot.tree.copy_global_to(guild=guild_id_obj_hook) # Copia comandos globais para o guild
                synced_commands_list_hook = await bot.tree.sync(guild=guild_id_obj_hook) # Sincroniza para o guild específico
                logger.info(f"{len(synced_commands_list_hook)} comandos (/) sincronizados com o servidor de teste (ID: {TEST_GUILD_ID}).")
                if synced_commands_list_hook: # Log dos nomes dos comandos sincronizados
                    nomes_comandos_sinc_hook = [cmd.name for cmd in synced_commands_list_hook]
                    logger.info(f"Nomes dos comandos sincronizados com o guild: {nomes_comandos_sinc_hook}")
                elif not synced_commands_list_hook and bot.tree.get_commands(guild=guild_id_obj_hook): # Se nada foi sincronizado mas existem comandos
                    nomes_comandos_guild_hook = [cmd.name for cmd in bot.tree.get_commands(guild=guild_id_obj_hook)]
                    logger.warning(f"Nenhum comando sincronizado com o guild, mas a tree do guild possui: {nomes_comandos_guild_hook}")

            except (ValueError, TypeError): # Se TEST_GUILD_ID for inválido
                logger.error(f"TEST_GUILD_ID ('{TEST_GUILD_ID}') é inválido. Tentando sincronizar globalmente...")
                synced_commands_list_hook = await bot.tree.sync() # Tenta sincronizar globalmente
                logger.info(f"{len(synced_commands_list_hook)} comandos (/) sincronizados globalmente.")
        else: # Se nenhum TEST_GUILD_ID for definido, sincroniza globalmente
            logger.info("Nenhum TEST_GUILD_ID definido. Sincronizando comandos globalmente...")
            synced_commands_list_hook = await bot.tree.sync()
            logger.info(f"{len(synced_commands_list_hook)} comandos (/) sincronizados globalmente.")

        if not synced_commands_list_hook: # Se, após tudo, nenhum comando foi sincronizado
            logger.warning("Nenhum comando de aplicativo foi sincronizado. Verifique as definições e se foram adicionados à tree.")

    except discord.Forbidden as e_forbidden_sync: # Erro de permissão
        logger.error(f"Erro 403 Forbidden ao sincronizar comandos (/): {e_forbidden_sync}. Verifique as permissões do bot (application.commands).")
    except discord.HTTPException as e_http_sync: # Outro erro HTTP
        logger.error(f"Erro HTTP ao sincronizar comandos (/): {e_http_sync.status} - {e_http_sync.text}", exc_info=True)
    except Exception as e_sync: # Erro genérico
        logger.error(f"Erro inesperado ao sincronizar comandos (/) no setup_hook: {e_sync}", exc_info=True)

    logger.info("setup_hook concluído.")


async def main():
    # SEU CÓDIGO ORIGINAL AQUI (main)
    # ...
    bot.setup_hook = setup_hook # Atribui o hook ANTES de iniciar o bot

    async with bot: # Context manager para o bot
        try:
            if not DISCORD_TOKEN:
                 logger.critical("DISCORD_TOKEN não encontrado. O bot não pode iniciar.")
                 return # Sai se não houver token

            logger.info("Iniciando conexão com o Discord...")
            await bot.start(DISCORD_TOKEN) # Inicia o bot

        except discord.LoginFailure: # Erro específico de falha de login
             logger.critical("Login no Discord Falhou: Token inválido. Verifique DISCORD_TOKEN.")
        except discord.PrivilegedIntentsRequired as e_intents: # Erro de intents privilegiadas
             shard_info_main = f"(Shard ID: {e_intents.shard_id})" if hasattr(e_intents, 'shard_id') and e_intents.shard_id is not None else ""
             logger.critical(f"Intents Privilegiadas {shard_info_main} não habilitadas no Portal do Desenvolvedor Discord.")
        except Exception as e_main_critical: # Erro crítico durante a execução geral do bot
            logger.critical(f"Erro crítico durante a execução do bot: {e_main_critical}", exc_info=True)
        finally: # Bloco finally para garantir limpeza
            logger.info("Iniciando processo de desligamento do bot...")
            if 'check_war_end_report_task' in globals() and check_war_end_report_task.is_running():
                 logger.info("Parando tarefa 'check_war_end_report_task'...")
                 check_war_end_report_task.cancel()
                 try:
                     await asyncio.sleep(1) # Dá um tempo para a task ser cancelada
                 except asyncio.CancelledError:
                     logger.info("Tarefa 'check_war_end_report_task' foi cancelada com sucesso.")
                 except Exception as e_task_cancel_finally: 
                     logger.error(f"Erro durante cancelamento da tarefa 'check_war_end_report_task': {e_task_cancel_finally}")

            if hasattr(bot, "web_runner") and bot.web_runner:
                logger.info("Limpando servidor web...")
                await bot.web_runner.cleanup()
                logger.info("Servidor web limpo.")

            if hasattr(bot, "coc_client") and bot.coc_client.http and hasattr(bot.coc_client.http, 'closed') and not bot.coc_client.http.closed:
                logger.info("Fechando cliente CoC...")
                await bot.coc_client.close()
                logger.info("Cliente CoC fechado.")
            elif hasattr(bot, "coc_client") and not bot.coc_client.http: # Se o cliente CoC não foi logado
                 logger.info("Cliente CoC não foi logado, não há sessão para fechar.")
            else: # Se o cliente CoC já estava fechado ou não inicializado
                 logger.info("Cliente CoC já estava fechado ou não inicializado.")
            logger.info("Desligamento do bot concluído.")


def handle_asyncio_exception(loop: asyncio.AbstractEventLoop, context: Dict[str, Any]): # Tipagem adicionada
    # SEU CÓDIGO ORIGINAL AQUI (handle_asyncio_exception)
    # ...
    msg = context.get("exception", context["message"])
    future_exc = context.get('future')
    if future_exc:
        logger.error(f"Erro não tratado no loop asyncio (Future: {future_exc}): {msg}", exc_info=context.get('exception'))
    else:
        logger.error(f"Erro não tratado no loop asyncio: {msg}", exc_info=context.get('exception'))


if __name__ == "__main__":
    # SEU CÓDIGO ORIGINAL AQUI (bloco if __name__ == "__main__":)
    # ...
    required_vars = ["DISCORD_TOKEN", "COC_EMAIL", "COC_PASSWORD", "CLAN_TAG", "CHANNEL_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
         logger.critical(f"Variáveis de ambiente obrigatórias faltando: {', '.join(missing_vars)}. Verifique .env ou configuração.")
    else:
        loop_main = asyncio.get_event_loop()
        try:
            logger.info("Iniciando loop de eventos asyncio para main()...")
            loop_main.set_exception_handler(handle_asyncio_exception) # Configura o handler de exceções do loop
            loop_main.run_until_complete(main()) # Roda a função main até completar

        except KeyboardInterrupt: # Captura Ctrl+C
            logger.info("Bot interrompido manualmente (KeyboardInterrupt).")
        except RuntimeError as e_runtime_main: # Captura RuntimeError, ex: loop fechado
             if "Event loop is closed" in str(e_runtime_main):
                  logger.info("Loop de eventos fechado durante o desligamento (normal).")
             else: # Outro RuntimeError
                  logger.warning(f"RuntimeError durante execução do loop: {e_runtime_main}", exc_info=True)
        except Exception as e_fatal_main: # Captura qualquer outra exceção fatal
            logger.critical(f"Erro fatal fora do loop principal do bot: {e_fatal_main}", exc_info=True)
        finally: # Bloco finally para garantir limpeza do loop
            if loop_main.is_running(): # Se o loop ainda estiver rodando
                loop_main.stop() # Para o loop
            if not loop_main.is_closed(): # Se o loop não estiver fechado
                # Cancela todas as tasks pendentes
                tasks_main_loop = [t for t in asyncio.all_tasks(loop=loop_main) if t is not asyncio.current_task(loop=loop_main)]
                if tasks_main_loop:
                    logger.info(f"Cancelando {len(tasks_main_loop)} tarefas pendentes...")
                    for task_item_main_loop in tasks_main_loop:
                        task_item_main_loop.cancel()
                    # Aguarda o cancelamento das tasks
                    loop_main.run_until_complete(asyncio.gather(*tasks_main_loop, return_exceptions=True))
                    logger.info("Tarefas pendentes canceladas.")
                loop_main.close() # Fecha o loop
                logger.info("Loop de eventos asyncio fechado.")
            logger.info("Programa finalizado.")
