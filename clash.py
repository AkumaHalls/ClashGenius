# -*- coding: utf-8 -*-
# Versão 19.0 - (Com painel web expandido)

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
from coc import ClanWar, Player, Clan, WarAttack, Timestamp, ClanMember, WarLogEntry, LeagueGroup, CapitalDistrict
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

BOT_VERSION = "19.0" 

reported_war_ends: Set[str] = set()
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Cache para dados de jogadores (tag: Player) para evitar múltiplas buscas na mesma requisição web
# Este cache é de curta duração, apenas para o contexto de uma requisição ou operação
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

async def get_player_data_with_short_term_cache(tag: str) -> Player:
    """Fetch player data, using a short-term cache first."""
    if not tag.startswith("#"):
        tag = f"#{tag}"
    if tag in player_short_term_cache:
        return player_short_term_cache[tag]
    
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        player = await bot.coc_client.get_player(tag)
        player_short_term_cache[tag] = player # Add to short-term cache
        return player
    except coc.NotFound:
        # Log a warning but don't necessarily raise an error that stops everything,
        # as a player might have left CoC or their tag is mistyped in war data.
        logger.warning(f"Jogador com tag {tag} não encontrado ao buscar para cache de curto prazo.")
        # Return a placeholder or specific error object if needed, for now, re-raise
        raise ValueError(f"Jogador com tag {tag} não encontrado.") 
    except coc.Maintenance:
        raise ValueError("API do CoC está em manutenção. Tente novamente mais tarde.")
    except asyncio.TimeoutError:
        raise ValueError("Tempo limite excedido ao buscar dados do jogador. Tente novamente.")
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar dados do jogador {tag} para cache: {e}", exc_info=True)
        raise ValueError(f"Erro inesperado ao buscar dados do jogador {tag}: {str(e)}")


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
            return cache_entry["data"]
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
            len(current_embed_split) + len(item_line) > 5900):
            if current_field_value_split:
                safe_field_name = field_name if field_name else "Dados"
                current_embed_split.add_field(name=safe_field_name, value=current_field_value_split, inline=False)
            if current_embed_split.fields:
                 embeds_to_send.append(current_embed_split)
            current_embed_split = discord.Embed.from_dict(base_embed.to_dict())
            current_field_value_split = item_line
            if len(current_field_value_split) > 1024:
                 current_field_value_split = current_field_value_split[:1021] + "...\n"
        else:
            current_field_value_split += item_line
    if current_field_value_split:
        safe_field_name_split = field_name if field_name else "Dados"
        current_embed_split.add_field(name=safe_field_name_split, value=current_field_value_split, inline=False)
    if current_embed_split.fields:
         embeds_to_send.append(current_embed_split)
    for embed_item in embeds_to_send:
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
def format_war_time_details(war_obj: ClanWar, time_now_tz: datetime.datetime) -> Dict[str, str]:
    """Formata os tempos de início/fim e o tempo restante para uma guerra."""
    details = {
        "time_key": "N/A",
        "time_value": "N/A",
        "time_remaining": "N/A",
        "start_time_iso": None,
        "end_time_iso": None,
    }
    if war_obj.state == "preparation":
        if war_obj.start_time and hasattr(war_obj.start_time, 'time'):
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
    elif war_obj.state == "inWar" or war_obj.state == "warEnded":
        if war_obj.end_time and hasattr(war_obj.end_time, 'time'):
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
            # Procura por guerra em andamento ou preparação na CWL
            for war_tag_obj in reversed(league_group.current_wars): # coc.py >=2.3 property
                 lg_war = await league_group.get_league_war(war_tag_obj.tag)
                 if lg_war and (lg_war.clan.tag == clan_tag or lg_war.opponent.tag == clan_tag):
                     if lg_war.state in ["inWar", "preparation"]:
                         current_war = lg_war
                         if lg_war.opponent.tag == clan_tag: # Garante que 'clan' seja sempre o nosso
                             lg_war.clan, lg_war.opponent = lg_war.opponent, lg_war.clan
                         return current_war # Retorna a primeira guerra ativa/preparação encontrada

            # Se não achou ativa, procura a última finalizada da CWL atual
            if not current_war and league_group.rounds:
                # Iterar pelas rodadas de trás para frente para pegar a mais recente
                for war_tags_in_round in reversed(league_group.rounds):
                    for war_tag_str in war_tags_in_round:
                        try:
                            lg_war = await league_group.get_league_war(war_tag_str)
                            if lg_war and (lg_war.clan.tag == clan_tag or lg_war.opponent.tag == clan_tag):
                                if lg_war.state == "warEnded":
                                     if lg_war.opponent.tag == clan_tag:
                                         lg_war.clan, lg_war.opponent = lg_war.opponent, lg_war.clan
                                     return lg_war # Retorna a primeira guerra finalizada da CWL
                        except coc.NotFound: continue
    except coc.NotFound:
        logger.debug("Nenhum grupo de liga encontrado para get_current_or_last_war.")
    except Exception as e:
        logger.error(f"Erro ao buscar guerra da CWL em get_current_or_last_war: {e}", exc_info=True)

    # Se não achou guerra de CWL, tenta guerra regular
    try:
        regular_war = await bot.coc_client.get_current_war(clan_tag)
        if regular_war and regular_war.state != "notInWar": # inWar, preparation, warEnded
            return regular_war
    except coc.PrivateWarLog:
        logger.warning("Log de guerra regular privado ao tentar buscar última guerra.")
    except coc.NotFound:
        logger.debug("Nenhuma guerra regular encontrada para get_current_or_last_war.")
    return None # Nenhuma guerra encontrada

# --- Funções de Coleta de Dados para Endpoints Web ---
web_api_cache: Dict[str, Dict] = {}
WEB_API_CACHE_DURATION_SECONDS = 60

async def get_cached_web_data(key: str, func_to_fetch_data, *args):
    now = datetime.datetime.now()
    if key in web_api_cache:
        cache_entry = web_api_cache[key]
        cache_age = (now - cache_entry["timestamp"]).total_seconds()
        if cache_age < WEB_API_CACHE_DURATION_SECONDS:
            return cache_entry["data"]
    data = await func_to_fetch_data(*args)
    web_api_cache[key] = {"data": data, "timestamp": now}
    return data

async def fetch_clan_info_for_web_api():
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        districts_data = []
        if hasattr(clan, 'capital_districts') and clan.capital_districts:
            for district in clan.capital_districts:
                districts_data.append({
                    "name": district.name,
                    "level": district.hall_level # district_hall_level
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
            "capital_league": clan.capital_league.name if hasattr(clan, 'capital_league') else "N/A"
        }
    except Exception as e:
        logger.error(f"Erro ao buscar dados do clã para API web: {e}", exc_info=True)
        return {"error": str(e), "name": "Erro ao carregar Clã"}

async def fetch_clan_members_for_web_api():
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

async def fetch_war_status_for_web_api():
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot."}
    war_to_display = await get_current_or_last_war(CLAN_TAG)

    if not war_to_display:
        return {"status": "NotInWar", "message": "Nenhuma guerra ativa ou recente encontrada.", "type": "Nenhuma"}
    
    time_now_tz = datetime.datetime.now(TIMEZONE)
    time_details = format_war_time_details(war_to_display, time_now_tz)
    
    war_type_description = "Guerra" # Default
    if war_to_display.is_cwl: war_type_description = "Liga de Clãs (CWL)"
    elif war_to_display.type == "friendly": war_type_description = "Guerra Amistosa"
    else: war_type_description = "Guerra Normal"


    return {
        "status": war_to_display.state, "type": war_type_description,
        "state_description": war_to_display.state.capitalize(),
        "clan_name": war_to_display.clan.name, "clan_stars": war_to_display.clan.stars,
        "clan_destruction": f"{war_to_display.clan.destruction:.2f}%",
        "clan_badge_url": war_to_display.clan.badge.url if hasattr(war_to_display.clan.badge, 'url') else None,
        "opponent_name": war_to_display.opponent.name, "opponent_tag": war_to_display.opponent.tag,
        "opponent_stars": war_to_display.opponent.stars,
        "opponent_destruction": f"{war_to_display.opponent.destruction:.2f}%",
        "opponent_badge_url": war_to_display.opponent.badge.url if hasattr(war_to_display.opponent.badge, 'url') else None,
        **time_details,
        "attacks_per_member": war_to_display.attacks_per_member,
        "preparation_start_time_iso": war_to_display.preparation_start_time.time.isoformat() if war_to_display.preparation_start_time else None,
    }

async def fetch_current_war_details_for_web_api():
    """ Retorna detalhes da guerra atual, incluindo lista de ataques. """
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot."}
    
    player_short_term_cache.clear() # Limpa o cache de curto prazo para jogadores
    war = await get_current_or_last_war(CLAN_TAG)

    if not war or war.state == "notInWar":
        return {"error": "Nenhuma guerra ativa ou recente para detalhar.", "war_data": None}

    attacks_data = []
    if war.attacks:
        # Coletar todas as tags de jogadores para buscar em lote (otimização)
        player_tags_to_fetch = set()
        for attack in war.attacks:
            player_tags_to_fetch.add(attack.attacker_tag)
            player_tags_to_fetch.add(attack.defender_tag)
        
        # Buscar dados dos jogadores
        # Nota: get_player_data_with_short_term_cache lida com cada tag individualmente.
        # Para um lote real, asyncio.gather seria usado, mas isso complica o cache de curto prazo.
        # Por simplicidade, manteremos chamadas sequenciais que utilizam o cache.

        for attack in sorted(war.attacks, key=lambda a: a.order): # Ordena por ordem do ataque
            try:
                attacker = await get_player_data_with_short_term_cache(attack.attacker_tag)
                attacker_name = attacker.name
                attacker_townhall = attacker.town_hall
            except ValueError: # Jogador não encontrado ou outro erro
                attacker_name = attack.attacker_tag # Fallback para tag
                attacker_townhall = '?'
            
            try:
                defender = await get_player_data_with_short_term_cache(attack.defender_tag)
                defender_name = defender.name
                defender_townhall = defender.town_hall
            except ValueError:
                defender_name = attack.defender_tag # Fallback para tag
                defender_townhall = '?'

            attacks_data.append({
                "attacker_tag": attack.attacker_tag,
                "attacker_name": attacker_name,
                "attacker_townhall": attacker_townhall,
                "defender_tag": attack.defender_tag,
                "defender_name": defender_name,
                "defender_townhall": defender_townhall,
                "stars": attack.stars,
                "destruction": attack.destruction,
                "order": attack.order,
                "duration": attack.duration # Adicionado
            })
    
    time_now_tz = datetime.datetime.now(TIMEZONE)
    time_details = format_war_time_details(war, time_now_tz)
    
    war_type_description = "Guerra"
    if war.is_cwl: war_type_description = "Liga de Clãs (CWL)"
    elif war.type == "friendly": war_type_description = "Guerra Amistosa"
    else: war_type_description = "Guerra Normal"

    return {
        "war_data": {
            "status": war.state, "type": war_type_description,
            "state_description": war.state.capitalize(),
            "clan_name": war.clan.name, "clan_stars": war.clan.stars,
            "clan_destruction": f"{war.clan.destruction:.2f}%",
            "clan_badge_url": war.clan.badge.url if hasattr(war.clan.badge, 'url') else None,
            "opponent_name": war.opponent.name, "opponent_tag": war.opponent.tag,
            "opponent_stars": war.opponent.stars,
            "opponent_destruction": f"{war.opponent.destruction:.2f}%",
            "opponent_badge_url": war.opponent.badge.url if hasattr(war.opponent.badge, 'url') else None,
            **time_details,
            "attacks_per_member": war.attacks_per_member,
            "team_size": war.team_size, # Adicionado
        },
        "attacks": attacks_data
    }

async def fetch_war_attacks_remaining_for_web_api():
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot."}
    war = await get_current_or_last_war(CLAN_TAG)

    if not war or war.state != "inWar":
        return {"message": "Não há guerra em andamento para verificar ataques restantes.", "members_pending": []}

    members_pending_attack = []
    if war.clan.members: # Assume que war.clan é o nosso clã
        for member in war.clan.members:
            attacks_made = len(member.attacks) if member.attacks else 0
            attacks_left = war.attacks_per_member - attacks_made
            if attacks_left > 0:
                members_pending_attack.append({
                    "name": member.name,
                    "tag": member.tag,
                    "town_hall": member.town_hall,
                    "attacks_left": attacks_left,
                    "map_position": member.map_position
                })
    members_pending_attack.sort(key=lambda m: m.get("map_position", 0))
    return {"message": "Membros com ataques pendentes.", "members_pending": members_pending_attack, "clan_name": war.clan.name}

async def fetch_war_log_for_web_api(limit: int = 10):
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot."}
    try:
        war_log = await bot.coc_client.get_war_log(CLAN_TAG, limit=limit)
        log_entries = []
        for entry in war_log:
            # Determinar se o resultado é vitória, derrota ou empate para o nosso clã
            # A API retorna 'win', 'loss', 'tie' do ponto de vista do 'clan' no log entry.
            # Precisamos garantir que 'clan' é o nosso clã.
            # Normalmente, o primeiro clã listado no log (`entry.clan`) é o clã cujo log estamos vendo,
            # mas é bom verificar se a API sempre se comporta assim ou se precisa de ajuste.
            # Assumindo que entry.clan é o nosso clã:
            
            result_for_us = "N/A"
            if entry.result: # result can be None for very old wars or errors
                if entry.result == "win": result_for_us = "Vitória"
                elif entry.result == "lose": result_for_us = "Derrota" # Note: API usa 'lose'
                elif entry.result == "tie": result_for_us = "Empate"


            log_entries.append({
                "clan_name": entry.clan.name, # Nosso clã
                "clan_tag": entry.clan.tag,
                "clan_stars": entry.clan.stars,
                "clan_destruction": entry.clan.destruction,
                "clan_badge_url": entry.clan.badge.url if hasattr(entry.clan.badge, 'url') else None,
                "opponent_name": entry.opponent.name,
                "opponent_tag": entry.opponent.tag,
                "opponent_stars": entry.opponent.stars,
                "opponent_destruction": entry.opponent.destruction,
                "opponent_badge_url": entry.opponent.badge.url if hasattr(entry.opponent.badge, 'url') else None,
                "team_size": entry.team_size,
                "end_time": entry.end_time.time.strftime('%d/%m/%Y %H:%M') if entry.end_time else "N/A",
                "end_time_iso": entry.end_time.time.isoformat() if entry.end_time else None,
                "result": result_for_us,
                "is_cwl": entry.is_cwl # Adicionado
            })
        return {"log": log_entries}
    except coc.PrivateWarLog:
        return {"error": "O log de guerras deste clã é privado."}
    except Exception as e:
        logger.error(f"Erro ao buscar log de guerras para API web: {e}", exc_info=True)
        return {"error": str(e)}

async def fetch_cwl_info_for_web_api():
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado no bot."}
    try:
        league_group = await bot.coc_client.get_league_group(CLAN_TAG)
        if not league_group or league_group.state == "notInWar":
            return {"status": "NotInCwl", "message": "O clã não está atualmente em uma Liga de Guerras de Clãs."}

        rounds_data = []
        if league_group.rounds:
            for i, war_tags_in_round in enumerate(league_group.rounds):
                round_info = {"round_number": i + 1, "wars": []}
                for war_tag_str in war_tags_in_round:
                    try:
                        war = await league_group.get_league_war(war_tag_str)
                        # Garantir que 'war.clan' seja o nosso clã
                        our_clan_obj = war.clan
                        opponent_obj = war.opponent
                        if war.opponent.tag == CLAN_TAG:
                            our_clan_obj, opponent_obj = opponent_obj, our_clan_obj

                        time_now_tz = datetime.datetime.now(TIMEZONE)
                        time_details = format_war_time_details(war, time_now_tz)

                        round_info["wars"].append({
                            "war_tag": war_tag_str,
                            "state": war.state,
                            "clan_name": our_clan_obj.name,
                            "clan_stars": our_clan_obj.stars,
                            "clan_destruction": f"{our_clan_obj.destruction:.2f}%",
                            "clan_badge_url": our_clan_obj.badge.url if hasattr(our_clan_obj.badge, 'url') else None,
                            "opponent_name": opponent_obj.name,
                            "opponent_tag": opponent_obj.tag,
                            "opponent_stars": opponent_obj.stars,
                            "opponent_destruction": f"{opponent_obj.destruction:.2f}%",
                            "opponent_badge_url": opponent_obj.badge.url if hasattr(opponent_obj.badge, 'url') else None,
                            **time_details
                        })
                    except coc.NotFound:
                        round_info["wars"].append({"war_tag": war_tag_str, "error": "Guerra não encontrada"})
                    except Exception as e_war:
                         round_info["wars"].append({"war_tag": war_tag_str, "error": f"Erro ao buscar guerra: {str(e_war)}"})
                rounds_data.append(round_info)
        
        clans_in_group_data = []
        if league_group.clans:
            for clan_in_group in league_group.clans:
                 clans_in_group_data.append({
                     "name": clan_in_group.name,
                     "tag": clan_in_group.tag,
                     "level": clan_in_group.level,
                     "badge_url": clan_in_group.badge.url if hasattr(clan_in_group.badge, 'url') else None,
                 })


        return {
            "status": "InCwl",
            "state": league_group.state, # "inWar", "preparation", "ended"
            "season": league_group.season.strftime('%Y-%m') if league_group.season else "N/A",
            "clans_in_group": clans_in_group_data,
            "rounds": rounds_data
        }
    except coc.NotFound:
        return {"status": "NotInCwl", "message": "O clã não está em CWL ou não foi encontrado."}
    except Exception as e:
        logger.error(f"Erro ao buscar informações da CWL para API web: {e}", exc_info=True)
        return {"error": str(e)}

# --- Endpoints da API Web ---
async def api_clan_info_handler(request):
    key = f"web_clan_info_{CLAN_TAG}"
    data = await get_cached_web_data(key, fetch_clan_info_for_web_api)
    return web.json_response(data)

async def api_members_handler(request):
    key = f"web_clan_members_{CLAN_TAG}"
    data = await get_cached_web_data(key, fetch_clan_members_for_web_api)
    return web.json_response(data)

async def api_war_status_handler(request): # Visão geral da guerra
    key = f"web_war_status_{CLAN_TAG}"
    data = await get_cached_web_data(key, fetch_war_status_for_web_api)
    return web.json_response(data)

async def api_current_war_details_handler(request): # Detalhes com ataques
    # Dados de guerra mudam rapidamente, cache mais curto ou sem cache para este.
    # Usando o cache padrão de 60s por enquanto.
    key = f"web_current_war_details_{CLAN_TAG}"
    data = await get_cached_web_data(key, fetch_current_war_details_for_web_api)
    return web.json_response(data)

async def api_war_attacks_remaining_handler(request):
    key = f"web_war_attacks_remaining_{CLAN_TAG}"
    data = await get_cached_web_data(key, fetch_war_attacks_remaining_for_web_api)
    return web.json_response(data)

async def api_war_log_handler(request):
    limit = request.query.get("limit", "10")
    try:
        limit = int(limit)
    except ValueError:
        limit = 10
    key = f"web_war_log_{CLAN_TAG}_limit{limit}"
    data = await get_cached_web_data(key, fetch_war_log_for_web_api, limit)
    return web.json_response(data)

async def api_cwl_info_handler(request):
    key = f"web_cwl_info_{CLAN_TAG}"
    data = await get_cached_web_data(key, fetch_cwl_info_for_web_api)
    return web.json_response(data)

# --- Servidor Web ---
async def handle_panel_index(request):
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "painel.html")
    try:
        return web.FileResponse(index_path)
    except FileNotFoundError:
        return web.Response(text="Painel não encontrado.", status=404)
    except Exception as e:
        return web.Response(text="Erro ao carregar o painel.", status=500)

async def setup_web_server():
    app = web.Application()
    async def health_handler(request):
        return web.Response(text=f"Bot is running! Panel active! v{BOT_VERSION}")

    app.router.add_get("/api/clan", api_clan_info_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/war", api_war_status_handler) # Visão geral
    app.router.add_get("/api/current_war_details", api_current_war_details_handler) # Com ataques
    app.router.add_get("/api/war_attacks_remaining", api_war_attacks_remaining_handler)
    app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler)

    app.router.add_get("/painel", handle_panel_index)
    static_files_path = os.path.join(os.path.dirname(__file__), "static")
    if not os.path.exists(static_files_path): os.makedirs(static_files_path)
    if not os.path.exists(os.path.join(static_files_path, "css")): os.makedirs(os.path.join(static_files_path, "css"))
    if not os.path.exists(os.path.join(static_files_path, "js")): os.makedirs(os.path.join(static_files_path, "js"))
    # ... (criação de arquivos HTML, CSS, JS básicos se não existirem - omitido para brevidade, já existe no código original)

    app.router.add_static('/static/', path=static_files_path, name='static', show_index=False)
    app.router.add_get("/", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    try:
         await site.start()
         logger.info(f"Servidor web para painel iniciado em 0.0.0.0:{port}")
         return runner
    except OSError as e:
        logger.error(f"Falha ao iniciar servidor web na porta {port}: {e}")
        return None
    except Exception as e:
         logger.error(f"Erro inesperado ao iniciar servidor web: {e}", exc_info=True)
         return None

# ... (Restante do seu código do bot: format_attacks_remaining_embed, send_missed_attacks_report, 
#      eventos on_ready, on_app_command_error, eventos CoC, task check_war_end_report_task,
#      comandos slash, setup_hook, main, etc. OMITIDOS PARA BREVIDADE, mas devem ser mantidos como estão no seu arquivo original,
#      a menos que necessitem de ajustes específicos por causa das novas funções de fetch, o que não parece ser o caso aqui.)
# --- INÍCIO DO CÓDIGO RESTANTE DO BOT (COPIADO DO ORIGINAL, SEM ALTERAÇÕES SIGNIFICATIVAS AQUI) ---
# Você deve inserir aqui o restante do seu código `clash.py` que foi omitido.
# As funções como `format_attacks_remaining_embed`, `send_missed_attacks_report`,
# os eventos do bot (`on_ready`, `on_app_command_error`), os eventos CoC,
# a task `check_war_end_report_task`, os comandos slash,
# a função `setup_hook` e a função `main` devem ser mantidas.

# Exemplo de como ficaria a estrutura para manter o restante do código:

async def format_attacks_remaining_embed(war: ClanWar) -> Optional[List[discord.Embed]]:
    # ... (seu código existente)
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


    members_with_attacks = []
    attack_count = getattr(war, 'attacks_per_member', 2)

    if hasattr(war.clan, 'members') and war.clan.members:
         for member in war.clan.members:
            if not member or not hasattr(member, 'attacks'): continue
            attacks_used = len(member.attacks) if member.attacks else 0
            attacks_left = attack_count - attacks_used
            if attacks_left > 0:
                member_th = getattr(member, 'town_hall', '?')
                member_name = getattr(member, 'name', 'Membro Desconhecido')
                members_with_attacks.append(f"**{member_name}** (CV{member_th}) - {attacks_left} {'ataques' if attacks_left > 1 else 'ataque'} restante{'s' if attacks_left > 1 else ''}")
    else:
         logger.warning("Lista de membros não encontrada no objeto 'war.clan' para format_attacks_remaining_embed.")


    base_embed_attacks = discord.Embed(
        title=f"🗡️ Ataques Restantes - {clan_name} vs {opponent_name}",
        description=f"**Placar:** {war.clan.stars}⭐ ({war.clan.destruction:.2f}%) vs {opponent_stars}⭐ ({opponent_destruction:.2f}%)\n"
                    f"**Fim:** {end_time_local_fmt} ({time_remaining} restantes)",
        color=discord.Color.blue()
    )
    if clan_badge_url: base_embed_attacks.set_thumbnail(url=clan_badge_url)


    embeds_to_send_attacks = []
    field_name_attacks = "Membros com Ataques Pendentes"
    if not members_with_attacks:
         embed_single = discord.Embed.from_dict(base_embed_attacks.to_dict())
         embed_single.add_field(name=field_name_attacks, value="✅ Todos os ataques já foram utilizados!", inline=False)
         embeds_to_send_attacks.append(embed_single)
    else:
        current_embed_attacks = discord.Embed.from_dict(base_embed_attacks.to_dict())
        current_field_value_attacks = ""
        for item in members_with_attacks:
            item_line = item + "\n"
            if len(current_field_value_attacks) + len(item_line) > 1024:
                if current_field_value_attacks:
                    current_embed_attacks.add_field(name=field_name_attacks, value=current_field_value_attacks, inline=False)
                if current_embed_attacks.fields:
                    embeds_to_send_attacks.append(current_embed_attacks)
                current_embed_attacks = discord.Embed.from_dict(base_embed_attacks.to_dict())
                current_field_value_attacks = item_line
                if len(current_field_value_attacks) > 1024:
                    current_field_value_attacks = current_field_value_attacks[:1021] + "...\n"
            else:
                current_field_value_attacks += item_line

        if current_field_value_attacks:
            current_embed_attacks.add_field(name=field_name_attacks, value=current_field_value_attacks, inline=False)
        if current_embed_attacks.fields:
            embeds_to_send_attacks.append(current_embed_attacks)

    for embed_item_rem in embeds_to_send_attacks: 
        if not hasattr(embed_item_rem, 'footer') or not hasattr(embed_item_rem.footer, 'text') or not embed_item_rem.footer.text:
             embed_item_rem.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        if not embed_item_rem.timestamp:
             embed_item_rem.timestamp = datetime.datetime.now(TIMEZONE)

    return embeds_to_send_attacks if embeds_to_send_attacks else None

async def send_missed_attacks_report(war: ClanWar,
                                    missed_members_details: List[str],
                                    war_type: str) -> None:
    # ... (seu código existente)
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
             if content:
                  await channel_to_send.send(content)
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
    # ... (seu código existente)
    if not CHANNEL_ID or CHANNEL_ID == 0:
        logger.warning("CHANNEL_ID não configurado. Não é possível enviar status online.")
        return

    try:
        clan_name = "Clã Desconhecido"
        clan_tag_formatted = CLAN_TAG if CLAN_TAG else "Nenhum"
        if CLAN_TAG and hasattr(bot, 'coc_client') and bot.coc_client.http: 
             try:
                  clan_data_status = await bot.coc_client.get_clan(CLAN_TAG)
                  clan_name = clan_data_status.name
                  clan_tag_formatted = clan_data_status.tag
             except Exception as e:
                  logger.error(f"Erro ao buscar dados do clã para status online: {e}")

        embed_online = discord.Embed(
            title="✅ Bot Online e Monitorando!",
            description=f"Eventos do clã **{clan_name}** (`{clan_tag_formatted}`) e Guerras monitorados.",
            color=discord.Color.green()
        )
        embed_online.add_field(name="Monitoramento", value="Event-Driven Ativo 🔄", inline=False)
        await send_log_embed(embed_online)
        logger.info("Mensagem de status online enviada.")

    except Exception as e:
        logger.error(f"Erro ao enviar mensagem de status online: {e}", exc_info=True)

@bot.event
async def on_ready():
    # ... (seu código existente, igual ao fornecido)
    logger.info(f"Bot {bot.user.name} (ID: {bot.user.id}) conectado ao Discord!")
    logger.info(f"Versão discord.py: {discord.__version__}")
    logger.info(f"Versão coc.py: {coc.__version__}")
    logger.info(f"Versão Bot: {BOT_VERSION}")
    logger.info(f"Pronto e operando em {len(bot.guilds)} servidor(es).")

    if hasattr(bot, 'coc_client') and bot.coc_client.http:
         logger.info("Cliente CoC parece estar pronto.")
         if not check_war_end_report_task.is_running():
              logger.info("Iniciando tarefa 'check_war_end_report_task'...")
              try:
                   check_war_end_report_task.start()
                   logger.info("Tarefa 'check_war_end_report_task' iniciada com sucesso.")
              except RuntimeError as e:
                   logger.error(f"Erro ao iniciar a tarefa 'check_war_end_report_task' (possivelmente já iniciada ou loop não pronto): {e}")
         else:
              logger.info("Tarefa 'check_war_end_report_task' já estava em execução.")
    else:
         logger.warning("Cliente CoC não parece estar pronto no on_ready. Tarefas em segundo plano podem não iniciar.")

    await send_online_status()

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # ... (seu código existente, igual ao fornecido)
    command_name = interaction.command.qualified_name if interaction.command else 'Comando Desconhecido'
    error_embed_cmd = discord.Embed(
        title="❌ Erro de Comando",
        color=discord.Color.red()
    )
    error_message = f"Ocorreu um erro inesperado: {str(error)}"

    original_error = getattr(error, 'original', error)

    if isinstance(original_error, ValueError):
        error_message = str(original_error)
    elif isinstance(original_error, coc.NotFound):
        error_message = "Não foi possível encontrar o recurso solicitado no Clash of Clans."
    elif isinstance(original_error, coc.Maintenance):
        error_message = "A API do Clash of Clans está em manutenção. Tente novamente mais tarde."
    elif isinstance(original_error, coc.PrivateWarLog):
        error_message = "O registro de guerra deste clã é privado e não pode ser acessado."
    elif isinstance(original_error, asyncio.TimeoutError):
         error_message = "Tempo limite excedido ao buscar dados da API do CoC. Tente novamente."
    elif isinstance(original_error, coc.InvalidCredentials):
         error_message = "Credenciais inválidas para a API do CoC detectadas."
    elif isinstance(original_error, coc.Forbidden):
         error_message = "Acesso proibido (Forbidden) à API do CoC. Verifique as permissões da chave."
    elif isinstance(error, app_commands.CommandSignatureMismatch):
         error_message = "Assinatura do comando desatualizada. Tente novamente em alguns instantes ou peça para sincronizar os comandos."
         logger.warning(f"CommandSignatureMismatch detectado para /{command_name}.")
    elif isinstance(error, app_commands.CheckFailure):
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
    else:
        error_message = f"Ocorreu um erro interno ao processar o comando."
        logger.error(f"Erro não tratado no comando '{command_name}': {original_error}", exc_info=original_error)


    error_embed_cmd.description = error_message
    error_embed_cmd.set_footer(text=f"Comando: /{command_name}")
    error_embed_cmd.timestamp = datetime.datetime.now(TIMEZONE)

    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=error_embed_cmd, ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed_cmd, ephemeral=True)
    except discord.NotFound:
         logger.warning(f"Interação para o comando /{command_name} não encontrada ao tentar enviar mensagem de erro.")
    except discord.Forbidden:
         logger.warning(f"Sem permissão para enviar mensagem de erro na interação /{command_name}.")
    except Exception as e:
         logger.error(f"Erro ao enviar mensagem de erro da interação /{command_name}: {e}", exc_info=True)


async def register_coc_events(coc_client: coc.EventsClient):
    # ... (seu código existente, igual ao fornecido)
    if not CLAN_TAG:
         logger.warning("CLAN_TAG não definido, eventos do clã não serão registrados.")
         return
    logger.info(f"Registrando manipuladores de eventos CoC para o clã {CLAN_TAG}...")

    @coc_client.event
    @coc.ClanEvents.member_join(tags=[CLAN_TAG])
    async def on_member_join(old_member: Optional[ClanMember], member: ClanMember):
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
    async def on_member_leave(old_member: ClanMember, member: ClanMember):
        logger.info(f"EVENTO DETECTADO: on_member_leave para {getattr(old_member, 'tag', 'TAG DESCONHECIDA DO MEMBRO QUE SAIU')}")
        if not old_member:
            logger.warning("Evento member_leave: 'old_member' (estado anterior do membro) não fornecido. Não é possível obter detalhes do membro que saiu.")
            return

        clan_obj_leave = old_member.clan if hasattr(old_member, 'clan') else None
        clan_name_leave = getattr(clan_obj_leave, 'name', 'Clã Desconhecido')

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

        if clan_obj_leave and hasattr(clan_obj_leave, 'badge') and clan_obj_leave.badge:
             embed_leave.set_author(name=clan_name_leave, icon_url=clan_obj_leave.badge.url)
             embed_leave.set_thumbnail(url=clan_obj_leave.badge.url)
        else:
            logger.warning(f"Não foi possível obter o emblema do clã {clan_name_leave} ({getattr(clan_obj_leave, 'tag', 'TAG CLÃ DESCONHECIDA')}) para o evento de saída de {leaving_member_name} ({leaving_member_tag}).")

        await send_log_embed(embed_leave)

    @coc_client.event
    @coc.ClanEvents.member_donations(tags=[CLAN_TAG])
    async def on_member_donations(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan_obj_don = member.clan
        old_donations = getattr(old_member, 'donations', 0)
        new_donations = getattr(member, 'donations', 0)
        donation_difference = new_donations - old_donations
        if donation_difference <= 0: return
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
        logger.info(f"EVENTO DETECTADO: on_member_role_change para {getattr(member, 'tag', 'TAG DESCONHECIDA')}")
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan_obj_role = member.clan
        old_role = getattr(old_member, 'role', None)
        new_role = getattr(member, 'role', None)
        if old_role == new_role: return
        logger.info(f"Evento: Cargo de {member.name} mudou de {old_role} para {new_role} em {clan_obj_role.name}.")
        embed_role = discord.Embed(
            title="🔄 Mudança de Cargo",
            description=f"Cargo de **{member.name}** (`{member.tag}`) foi alterado!",
            color=discord.Color.gold()
        )
        embed_role.add_field(name="Cargo Anterior", value=old_role.name.capitalize() if old_role else 'N/A', inline=True)
        embed_role.add_field(name="Novo Cargo", value=new_role.name.capitalize() if new_role else 'N/A', inline=True)
        if hasattr(clan_obj_role, 'badge') and clan_obj_role.badge:
             embed_role.set_author(name=clan_obj_role.name, icon_url=clan_obj_role.badge.url)
             embed_role.set_thumbnail(url=clan_obj_role.badge.url)
        await send_log_embed(embed_role)

    @coc_client.event
    @coc.ClanEvents.member_league_change(tags=[CLAN_TAG])
    async def on_member_league_change(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan_obj_league = member.clan
        old_league = getattr(old_member, 'league', None)
        new_league = getattr(member, 'league', None)
        if old_league == new_league: return
        logger.info(f"Evento: Liga de {member.name} mudou de {old_league} para {new_league} em {clan_obj_league.name}.")
        old_league_name = old_league.name if old_league else "Sem Liga"
        new_league_name = new_league.name if new_league else "Sem Liga"
        embed_league_evt = discord.Embed( # Renomeado para evitar conflito com variável no escopo global
            title="🏆 Mudança de Liga",
            description=f"Liga de **{member.name}** (`{member.tag}`) foi alterada!",
            color=discord.Color.purple()
        )
        embed_league_evt.add_field(name="Liga Anterior", value=old_league_name, inline=True)
        embed_league_evt.add_field(name="Nova Liga", value=new_league_name, inline=True)
        if hasattr(clan_obj_league, 'badge') and clan_obj_league.badge:
             embed_league_evt.set_author(name=clan_obj_league.name, icon_url=clan_obj_league.badge.url)
             embed_league_evt.set_thumbnail(url=clan_obj_league.badge.url)
        await send_log_embed(embed_league_evt)


    @coc_client.event
    @coc.ClanEvents.member_trophies_change(tags=[CLAN_TAG])
    async def on_member_trophies_change(old_member: ClanMember, member: ClanMember):
        if not member or not old_member:
             logger.warning("Evento member_trophies_change recebido com objeto 'member' ou 'old_member' inválido.")
             return
        old_trophies = getattr(old_member, 'trophies', 0)
        new_trophies = getattr(member, 'trophies', 0)
        trophy_difference = new_trophies - old_trophies

        if abs(trophy_difference) < 5: return 
        logger.info(f"Evento: Troféus de {member.name} mudaram em {trophy_difference} (Total: {new_trophies}).")
        direction = "ganhou" if trophy_difference > 0 else "perdeu"
        embed_trophies = discord.Embed(
            description=f"**{member.name}** {direction} **{abs(trophy_difference)}** troféus (Total: {new_trophies})",
            color=discord.Color.green() if trophy_difference > 0 else discord.Color.dark_red()
        )
        await send_log_embed(embed_trophies)

    @coc_client.event
    @coc.WarEvents.war_attack(tags=[CLAN_TAG])
    async def on_war_attack(attack: WarAttack, war: ClanWar):
        # ... (seu código existente, igual ao fornecido)
        if not all(hasattr(attack, attr) for attr in ['attacker_tag', 'defender_tag', 'stars', 'destruction', 'order']):
            logger.warning(f"Evento de ataque de guerra recebido com dados incompletos. War Tag: {getattr(war, 'tag', 'N/A')}")
            return

        is_our_attack = False
        is_our_defense = False
        attacker_clan_tag = None
        defender_clan_tag = None
        attacker_player = None
        defender_player = None
        player_short_term_cache.clear() # Limpa cache antes de buscar para este evento

        try:
             attacker_player = await get_player_data_with_short_term_cache(attack.attacker_tag)
             defender_player = await get_player_data_with_short_term_cache(attack.defender_tag)
             attacker_clan_tag = getattr(attacker_player.clan, 'tag', None) if hasattr(attacker_player, 'clan') else None
             defender_clan_tag = getattr(defender_player.clan, 'tag', None) if hasattr(defender_player, 'clan') else None
        except ValueError as e:
             logger.warning(f"Não foi possível buscar dados do atacante ({attack.attacker_tag}) ou defensor ({attack.defender_tag}) para ataque de guerra {attack.order}: {e}")
        except Exception as e:
             logger.error(f"Erro inesperado ao buscar dados atacante/defensor para ataque de guerra {attack.order}: {e}", exc_info=True)
             return

        if attacker_clan_tag is not None and attacker_clan_tag == CLAN_TAG:
             is_our_attack = True
        elif defender_clan_tag is not None and defender_clan_tag == CLAN_TAG:
             is_our_defense = True
        elif attacker_clan_tag is None or defender_clan_tag is None:
             logger.warning(f"Não foi possível determinar clãs do atacante/defensor para ataque {attack.order} após tentativa de fetch.")
             return
        else:
             #logger.debug(f"Ataque de guerra ({attack.order}) não envolve o clã {CLAN_TAG}. Attacker: {attacker_clan_tag}, Defender: {defender_clan_tag}")
             return # Ignora ataques que não são do nosso clã

        attacker_name = getattr(attacker_player, 'name', attack.attacker_tag) if attacker_player else attack.attacker_tag
        defender_name = getattr(defender_player, 'name', attack.defender_tag) if defender_player else attack.defender_tag
        attacker_th = getattr(attacker_player, 'town_hall', '?') if attacker_player else '?'
        defender_th = getattr(defender_player, 'town_hall', '?') if defender_player else '?'

        stars_str = "⭐" * attack.stars + "⚫" * (3 - attack.stars)
        content_attack = None

        if is_our_attack:
            logger.info(f"Evento Guerra: {attacker_name} atacou {defender_name} - {attack.stars} estrelas, {attack.destruction}% destruição.")
            embed_attack = discord.Embed(
                title=f"⚔️ Ataque Realizado (Guerra)",
                description=f"**{attacker_name}** (CV{attacker_th}) atacou **{defender_name}** (CV{defender_th})",
                color=discord.Color.blue()
            )
            embed_attack.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)

            if attack.stars <= 1 and ROLE_ID_1STAR_ALERT:
                try:
                    log_channel_attack = await bot.fetch_channel(CHANNEL_ID)
                    if log_channel_attack and hasattr(log_channel_attack, 'guild'):
                         guild_attack = log_channel_attack.guild
                         try:
                              role_id_int_attack = int(ROLE_ID_1STAR_ALERT)
                              role_attack = guild_attack.get_role(role_id_int_attack)
                              if role_attack: content_attack = f"{role_attack.mention} ⚠️ Atenção: ataque fora do padrão detectado!"
                              else: logger.warning(f"Cargo para alerta de 1 estrela (ID: {ROLE_ID_1STAR_ALERT}) não encontrado.")
                         except (ValueError, TypeError): logger.error(f"ROLE_ID_1STAR_ALERT ('{ROLE_ID_1STAR_ALERT}') é inválido.")
                    else: logger.warning("Não foi possível buscar o servidor do canal de log para alerta de 1 estrela.")
                except Exception as e: logger.error(f"Erro ao buscar cargo para alerta de 1 estrela: {e}", exc_info=True)

            if hasattr(war, 'clan') and hasattr(war.clan, 'badge') and war.clan.badge:
                 embed_attack.set_author(name=war.clan.name, icon_url=war.clan.badge.url)
                 embed_attack.set_thumbnail(url=war.clan.badge.url)
            await send_log_embed(embed_attack, content_attack)

        elif is_our_defense:
            logger.info(f"Evento Guerra: {defender_name} foi atacado por {attacker_name} - {attack.stars} estrelas, {attack.destruction}% destruição.")
            embed_defense = discord.Embed(
                title=f"🛡️ Defesa Recebida (Guerra)",
                description=f"**{defender_name}** (CV{defender_th}) foi atacado por **{attacker_name}** (CV{attacker_th})",
                color=discord.Color.orange()
            )
            embed_defense.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
            if hasattr(war, 'opponent') and hasattr(war.opponent, 'badge') and war.opponent.badge:
                 embed_defense.set_author(name=war.opponent.name, icon_url=war.opponent.badge.url)
                 embed_defense.set_thumbnail(url=war.opponent.badge.url)
            await send_log_embed(embed_defense)


    logger.info("Manipuladores de eventos CoC registrados.")


@tasks.loop(minutes=10)
async def check_war_end_report_task():
    # ... (seu código existente, igual ao fornecido)
    if not bot.coc_client or not bot.coc_client.http:
         logger.debug("check_war_end_report_task: Cliente CoC não pronto, pulando ciclo.")
         return

    logger.debug("check_war_end_report_task: Iniciando verificação de fim de guerra...")
    processed_war_ids: Set[str] = set() # Mantém IDs baseados no raw_time da guerra

    async def process_war_for_report(war_obj: ClanWar, war_type_name: str):
        # Usar um ID único para a guerra, como combinação de tag do oponente e tempo de fim
        # O end_time.raw_time é um bom candidato se for estável.
        war_id_str = None
        if hasattr(war_obj, 'opponent') and war_obj.opponent and hasattr(war_obj.opponent, 'tag') and \
           hasattr(war_obj, 'end_time') and war_obj.end_time and hasattr(war_obj.end_time, 'raw_time'):
            war_id_str = f"{war_obj.opponent.tag}-{war_obj.end_time.raw_time}"
        else: # Fallback se não tiver todos os dados, embora improvável para uma guerra processável
            logger.warning(f"Não foi possível gerar ID estável para guerra {war_type_name} contra {getattr(war_obj.opponent, 'name', 'N/A')}. Pulando.")
            return

        if war_id_str in processed_war_ids:
            logger.debug(f"Guerra {war_id_str} ({war_type_name}) já processada neste ciclo de task. Pulando.")
            return
        
        opponent_name_proc = getattr(getattr(war_obj, 'opponent', None), 'name', 'Oponente Desconhecido')
        war_state_proc = getattr(war_obj, 'state', 'unknown')
        logger.debug(f"Processando para relatório: {war_type_name} contra {opponent_name_proc} (ID: {war_id_str}, Estado: {war_state_proc})")

        if war_state_proc == "warEnded" and war_id_str not in reported_war_ends:
            logger.info(f"Guerra '{war_type_name}' contra {opponent_name_proc} terminou (ID: {war_id_str}). Verificando ataques perdidos...")

            our_clan_obj_for_report = war_obj.clan # Assume que war_obj.clan é o nosso
            # Para CWL, war_obj.clan pode ser o oponente se o nosso clã for o 'opponent' na busca inicial.
            # A função get_current_or_last_war já tenta normalizar isso.
            # Aqui, precisamos garantir que 'our_clan_obj_for_report' é de fato o nosso clã.
            if war_obj.clan.tag != CLAN_TAG and war_obj.opponent.tag == CLAN_TAG:
                our_clan_obj_for_report = war_obj.opponent
            elif war_obj.clan.tag != CLAN_TAG and war_obj.opponent.tag != CLAN_TAG:
                 logger.error(f"Não foi possível identificar nosso clã na guerra {war_id_str} para relatório de ataques perdidos.")
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
                 logger.warning(f"Clã '{getattr(our_clan_obj_for_report, 'name', 'N/A')}' na guerra {war_id_str} não possui lista de membros para relatório.")

            if missed_members_details_task:
                logger.info(f"{len(missed_members_details_task)} membro(s) perderam ataques na guerra {war_type_name} (ID: {war_id_str}).")
                await send_missed_attacks_report(war_obj, missed_members_details_task, war_type_name)
            else:
                logger.info(f"Nenhum ataque perdido na guerra {war_type_name} (ID: {war_id_str}).")

            reported_war_ends.add(war_id_str)
            logger.debug(f"Guerra {war_id_str} marcada como reportada para ataques perdidos.")
        
        processed_war_ids.add(war_id_str) # Adiciona ao set de processados neste ciclo da task
    
    # Processar Guerra Regular
    try:
        logger.debug("check_war_end_report_task: Buscando guerra regular...")
        current_war_reg = await bot.coc_client.get_current_war(CLAN_TAG)
        if current_war_reg and hasattr(current_war_reg, 'state') and current_war_reg.state != "notInWar":
             if hasattr(current_war_reg, 'end_time'): # Guerra válida
                  await process_war_for_report(current_war_reg, "Guerra Normal")
             else:
                  logger.warning("check_war_end_report_task: Objeto de guerra regular inválido (sem end_time).")
        # (logs de debug sobre estado omitidos para brevidade)
    except coc.PrivateWarLog:
        logger.warning("check_war_end_report_task: Log de guerra regular é privado.")
    except coc.NotFound:
         logger.info("check_war_end_report_task: Clã não encontrado ao buscar guerra regular.")
    except Exception as e:
        logger.error(f"check_war_end_report_task: Erro ao buscar/processar guerra regular: {e}", exc_info=True)

    # Processar Guerras da CWL
    try:
        logger.debug("check_war_end_report_task: Buscando grupo de liga (CWL)...")
        league_group_cwl = await bot.coc_client.get_league_group(CLAN_TAG)
        if league_group_cwl and hasattr(league_group_cwl, 'state') and league_group_cwl.state != "notInWar":
            if hasattr(league_group_cwl, 'rounds') and league_group_cwl.rounds:
                 for round_num_cwl, war_tags_cwl in enumerate(league_group_cwl.rounds):
                     for war_tag_cwl in war_tags_cwl:
                         try:
                             league_war_obj = await league_group_cwl.get_league_war(war_tag_cwl)
                             if not league_war_obj or not hasattr(league_war_obj, 'state') or not hasattr(league_war_obj, 'end_time'):
                                  logger.warning(f"check_war_end_report_task: Objeto da guerra da liga {war_tag_cwl} inválido.")
                                  continue
                             
                             # Verificar se nosso clã está envolvido nesta guerra da rodada
                             if league_war_obj.clan.tag == CLAN_TAG or league_war_obj.opponent.tag == CLAN_TAG:
                                 # Normalizar para que league_war_obj.clan seja sempre o nosso clã (se possível)
                                 final_war_obj_for_cwl_report = league_war_obj
                                 if league_war_obj.opponent.tag == CLAN_TAG:
                                     # Criar um objeto "espelhado" ou ajustar. A API coc.py não permite modificar clan/opponent diretamente
                                     # Para simplicidade, passamos o objeto como está e a função process_war_for_report deve lidar com isso.
                                     pass # process_war_for_report vai verificar e usar o clã correto

                                 await process_war_for_report(final_war_obj_for_cwl_report, f"Liga de Clãs (Rodada {round_num_cwl + 1})")
                         except coc.NotFound:
                              logger.warning(f"check_war_end_report_task: Guerra da liga {war_tag_cwl} não encontrada.")
                         except Exception as e_cwl_war:
                              logger.error(f"check_war_end_report_task: Erro ao buscar/processar guerra da liga {war_tag_cwl}: {e_cwl_war}", exc_info=True)
            # (logs de debug omitidos)
    except coc.NotFound:
         logger.info("check_war_end_report_task: Clã não encontrado ao buscar grupo de liga (CWL).")
    except Exception as e:
        logger.error(f"check_war_end_report_task: Erro ao buscar/processar grupo de liga (CWL): {e}", exc_info=True)

    logger.debug("check_war_end_report_task: Verificação de fim de guerra concluída.")


@check_war_end_report_task.before_loop
async def before_check_war():
    # ... (seu código existente)
    logger.info("Aguardando o bot ficar pronto para iniciar a tarefa 'check_war_end_report_task'...")
    await bot.wait_until_ready()
    logger.info("Bot pronto. Tarefa 'check_war_end_report_task' pode iniciar.")

# Slash command groups
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

# Slash commands
# ... (Seus comandos slash existentes: admin_ping, war_attacks, war_status, clan_info, player_info, clan_members, search_clan, search_player, rank_donations, rank_trophies, rank_cv)
# Mantenha todos os seus comandos slash como estão. Eles não precisam de alteração para estas novas funcionalidades do painel web.
# Omitidos aqui para não exceder o limite de resposta.

# EXEMPLO DE UM COMANDO SLASH (MANTENHA OS SEUS):
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

# ... COLOQUE AQUI TODOS OS SEUS OUTROS COMANDOS SLASH ...

async def setup_hook():
    # ... (seu código setup_hook existente, garantindo que bot.web_runner = await setup_web_server() seja chamado)
    logger.info("Executando setup_hook...")

    logger.info("Inicializando cliente CoC...")
    bot.coc_client = coc.EventsClient()
    max_retries = 3
    retry_delay = 5
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
        except coc.InvalidCredentials as e:
             logger.error(f"Login CoC Falhou: Credenciais Inválidas. Verifique COC_EMAIL/COC_PASSWORD. {e}")
             break
        except coc.Maintenance as e:
             logger.warning(f"API CoC em manutenção: {e}. Funcionalidades CoC estarão indisponíveis.")
             break
        except asyncio.TimeoutError:
             logger.error(f"Timeout no login CoC (Tentativa {attempt + 1}).")
             if attempt < max_retries - 1: await asyncio.sleep(retry_delay)
        except Exception as e:
             logger.error(f"Erro inesperado no login CoC (Tentativa {attempt + 1}): {e}", exc_info=True)
             if attempt < max_retries - 1: await asyncio.sleep(retry_delay)

    if not login_success:
         logger.error("Não foi possível logar no CoC após todas as tentativas ou devido a erro/manutenção.")
    else:
         logger.info("Registrando listeners de eventos CoC...")
         await register_coc_events(bot.coc_client)
         if CLAN_TAG:
             logger.info(f"Adicionando atualizações de eventos para o clã: {CLAN_TAG}")
             try:
                  bot.coc_client.add_clan_updates(CLAN_TAG)
                  bot.coc_client.add_war_updates(CLAN_TAG)
                  logger.info("Atualizações de clã e guerra ativadas.")
             except Exception as e:
                  logger.error(f"Erro ao adicionar atualizações de eventos para {CLAN_TAG}: {e}", exc_info=True)
         else:
              logger.warning("CLAN_TAG não definido. Atualizações de eventos CoC não ativadas.")

    logger.info("Configurando servidor web para painel...") 
    bot.web_runner = await setup_web_server() # Esta linha é crucial
    if bot.web_runner:
        logger.info("Servidor web configurado.")
    else:
        logger.warning("Falha ao configurar o servidor web.")

    logger.info("Tentando sincronizar comandos de aplicativo (/) no setup_hook...")
    # ... (resto do seu código de sincronização de comandos)
    synced_commands_list_hook = []
    try:
        if TEST_GUILD_ID:
            try:
                guild_id_obj_hook = discord.Object(id=int(TEST_GUILD_ID))
                logger.info(f"Copiando comandos globais para o servidor de teste ID: {TEST_GUILD_ID} e sincronizando...")
                bot.tree.copy_global_to(guild=guild_id_obj_hook)
                synced_commands_list_hook = await bot.tree.sync(guild=guild_id_obj_hook)
                logger.info(f"{len(synced_commands_list_hook)} comandos (/) sincronizados com o servidor de teste (ID: {TEST_GUILD_ID}).")
            except (ValueError, TypeError):
                logger.error(f"TEST_GUILD_ID ('{TEST_GUILD_ID}') é inválido. Tentando sincronizar globalmente...")
                synced_commands_list_hook = await bot.tree.sync()
                logger.info(f"{len(synced_commands_list_hook)} comandos (/) sincronizados globalmente.")
        else:
            logger.info("Nenhum TEST_GUILD_ID definido. Sincronizando comandos globalmente...")
            synced_commands_list_hook = await bot.tree.sync()
            logger.info(f"{len(synced_commands_list_hook)} comandos (/) sincronizados globalmente.")

        if not synced_commands_list_hook:
            logger.warning("Nenhum comando de aplicativo foi sincronizado.")

    except discord.Forbidden as e:
        logger.error(f"Erro 403 Forbidden ao sincronizar comandos (/): {e}. Verifique as permissões do bot (application.commands).")
    except discord.HTTPException as e:
        logger.error(f"Erro HTTP ao sincronizar comandos (/): {e.status} - {e.text}", exc_info=True)
    except Exception as e:
        logger.error(f"Erro inesperado ao sincronizar comandos (/) no setup_hook: {e}", exc_info=True)


    logger.info("setup_hook concluído.")


async def main():
    # ... (seu código main existente)
    bot.setup_hook = setup_hook

    async with bot:
        try:
            if not DISCORD_TOKEN:
                 logger.critical("DISCORD_TOKEN não encontrado. O bot não pode iniciar.")
                 return

            logger.info("Iniciando conexão com o Discord...")
            await bot.start(DISCORD_TOKEN)

        except discord.LoginFailure:
             logger.critical("Login no Discord Falhou: Token inválido. Verifique DISCORD_TOKEN.")
        except discord.PrivilegedIntentsRequired as e:
             shard_info_main = f"(Shard ID: {e.shard_id})" if hasattr(e, 'shard_id') and e.shard_id is not None else ""
             logger.critical(f"Intents Privilegiadas {shard_info_main} não habilitadas no Portal do Desenvolvedor Discord.")
        except Exception as e:
            logger.critical(f"Erro crítico durante a execução do bot: {e}", exc_info=True)
        finally:
            logger.info("Iniciando processo de desligamento do bot...")
            if 'check_war_end_report_task' in globals() and check_war_end_report_task.is_running():
                 logger.info("Parando tarefa 'check_war_end_report_task'...")
                 check_war_end_report_task.cancel()
                 try:
                     await asyncio.sleep(1) # Dar um tempo para cancelar
                 except asyncio.CancelledError:
                     logger.info("Tarefa 'check_war_end_report_task' foi cancelada com sucesso.")
                 except Exception as e_task_cancel: 
                     logger.error(f"Erro durante cancelamento da tarefa 'check_war_end_report_task': {e_task_cancel}")

            if hasattr(bot, "web_runner") and bot.web_runner:
                logger.info("Limpando servidor web...")
                await bot.web_runner.cleanup()
                logger.info("Servidor web limpo.")

            if hasattr(bot, "coc_client") and bot.coc_client.http and hasattr(bot.coc_client.http, 'closed') and not bot.coc_client.http.closed:
                logger.info("Fechando cliente CoC...")
                await bot.coc_client.close()
                logger.info("Cliente CoC fechado.")
            elif hasattr(bot, "coc_client") and not bot.coc_client.http:
                 logger.info("Cliente CoC não foi logado, não há sessão para fechar.")
            else:
                 logger.info("Cliente CoC já estava fechado ou não inicializado.")
            logger.info("Desligamento do bot concluído.")


def handle_asyncio_exception(loop, context):
    # ... (seu código existente)
    msg = context.get("exception", context["message"])
    future_exc = context.get('future')
    if future_exc:
        logger.error(f"Erro não tratado no loop asyncio (Future: {future_exc}): {msg}", exc_info=context.get('exception'))
    else:
        logger.error(f"Erro não tratado no loop asyncio: {msg}", exc_info=context.get('exception'))


if __name__ == "__main__":
    # ... (seu código existente)
    required_vars = ["DISCORD_TOKEN", "COC_EMAIL", "COC_PASSWORD", "CLAN_TAG", "CHANNEL_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
         logger.critical(f"Variáveis de ambiente obrigatórias faltando: {', '.join(missing_vars)}. Verifique .env ou configuração.")
    else:
        loop_main = asyncio.get_event_loop()
        try:
            logger.info("Iniciando loop de eventos asyncio para main()...")
            loop_main.set_exception_handler(handle_asyncio_exception)
            loop_main.run_until_complete(main())

        except KeyboardInterrupt:
            logger.info("Bot interrompido manualmente (KeyboardInterrupt).")
        except RuntimeError as e_runtime: 
             if "Event loop is closed" in str(e_runtime):
                  logger.info("Loop de eventos fechado durante o desligamento (normal).")
             else:
                  logger.warning(f"RuntimeError durante execução do loop: {e_runtime}", exc_info=True)
        except Exception as e_fatal: 
            logger.critical(f"Erro fatal fora do loop principal do bot: {e_fatal}", exc_info=True)
        finally:
            if loop_main.is_running():
                loop_main.stop()
            if not loop_main.is_closed():
                # Cancel all tasks
                tasks_main = [t for t in asyncio.all_tasks(loop=loop_main) if t is not asyncio.current_task(loop=loop_main)]
                if tasks_main:
                    logger.info(f"Cancelando {len(tasks_main)} tarefas pendentes...")
                    for task_item_main in tasks_main:
                        task_item_main.cancel()
                    loop_main.run_until_complete(asyncio.gather(*tasks_main, return_exceptions=True))
                    logger.info("Tarefas pendentes canceladas.")
                loop_main.close()
                logger.info("Loop de eventos asyncio fechado.")
            logger.info("Programa finalizado.")

# --- FIM DO CÓDIGO RESTANTE DO BOT ---
