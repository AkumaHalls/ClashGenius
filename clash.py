# -*- coding: utf-8 -*-
# Versão 19.8.3 - (Foco na API Oficial CoC para dados de guerra, sem API externa)

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
import coc # Biblioteca oficial para a API do Clash of Clans
import pytz # Para lidar com fusos horários
from dotenv import load_dotenv # Para carregar variáveis de ambiente

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'), # Salva logs em um arquivo
        logging.StreamHandler() # Mostra logs no console
    ]
)
logger = logging.getLogger("coc_discord_bot")

# ---- IMPORTAÇÕES ESPECÍFICAS DO COC ----
# Importa classes principais da biblioteca coc.py
from coc import (
    ClanWar,
    Player,
    Clan,
    WarAttack,
    Timestamp,
    ClanMember
)

# Inicializa variáveis para classes que podem ter problemas de importação (fallback)
WarLogEntry = None
LeagueGroup = None
CapitalDistrict = None

# Tenta importar WarLogEntry de diferentes locais da biblioteca coc.py
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

# Tenta importar LeagueGroup
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

# Tenta importar CapitalDistrict
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

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COC_EMAIL = os.getenv("COC_EMAIL")
COC_PASSWORD = os.getenv("COC_PASSWORD")
CLAN_TAG = os.getenv("CLAN_TAG")

# Configura o ID do canal do Discord para logs
try:
    channel_id_str = os.environ.get("CHANNEL_ID")
    if channel_id_str:
        CHANNEL_ID = int(channel_id_str)
    else:
        CHANNEL_ID = 0 # Padrão se não definido
        logger.error("CHANNEL_ID não definido no .env. Usando 0 como padrão.")
except (TypeError, ValueError) as e_channel_id:
    logger.error(f"CHANNEL_ID ('{channel_id_str if 'channel_id_str' in locals() else 'N/A'}') inválido no .env: {e_channel_id}. Usando 0 como padrão.")
    CHANNEL_ID = 0

# IDs de cargos para menções em alertas (opcional)
ROLE_ID_1STAR_ALERT = os.getenv("ROLE_ID_1STAR_ALERT")
ROLE_ID_MISSED_ATTACK = os.getenv("ROLE_ID_MISSED_ATTACK")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID") # ID do servidor de teste para sincronizar comandos rapidamente

# Configura o fuso horário
try:
    TIMEZONE = pytz.timezone('America/Sao_Paulo')
except pytz.UnknownTimeZoneError:
    logger.error("Timezone 'America/Sao_Paulo' desconhecida. Usando UTC como padrão.")
    TIMEZONE = pytz.utc

BOT_VERSION = "19.8.3"
PLAYER_NOTES_FILE = "player_notes.json" # Arquivo para persistência local das notas dos jogadores

# Conjunto para rastrear guerras já reportadas (evita duplicidade de relatórios de fim de guerra)
reported_war_ends: Set[str] = set()

# Configuração das intents do Discord (permissões que o bot necessita)
intents = discord.Intents.default()
intents.message_content = True # Para ler conteúdo de mensagens (se comandos de prefixo fossem usados)
intents.members = True       # Para acessar informações de membros do servidor
intents.guilds = True        # Para acessar informações do servidor
bot = commands.Bot(command_prefix="!", intents=intents) # Define o prefixo de comando (embora usemos slash commands)

# Caches em memória para dados do CoC, para reduzir chamadas à API
player_short_term_cache: Dict[str, Player] = {}
clan_cache: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION_SECONDS = 300 # 5 minutos de cache

# --- Funções de Persistência de Notas (JSON Local) ---
def load_player_notes() -> Dict[str, Dict[str, str]]:
    """Carrega as notas dos jogadores do arquivo JSON local."""
    if not os.path.exists(PLAYER_NOTES_FILE):
        logger.info(f"Arquivo de notas '{PLAYER_NOTES_FILE}' não encontrado. Criando um novo com {{}}.")
        save_player_notes({}) # Cria um arquivo com um JSON vazio
        return {}
    # Verifica se o arquivo está completamente vazio antes de tentar carregar
    try:
        if os.path.getsize(PLAYER_NOTES_FILE) == 0:
            logger.warning(f"Arquivo de notas '{PLAYER_NOTES_FILE}' encontrado, mas está vazio. Inicializando com {{}}.")
            save_player_notes({}) # Escreve um JSON vazio no arquivo
            return {}
    except OSError as e: # Caso haja erro ao verificar o tamanho (ex: permissão)
        logger.error(f"Erro ao verificar o tamanho do arquivo '{PLAYER_NOTES_FILE}': {e}. Tentando carregar mesmo assim.")

    try:
        with open(PLAYER_NOTES_FILE, 'r', encoding='utf-8') as f:
            notes = json.load(f)
            # Garante que o formato é o esperado (dicionário de dicionários)
            if not isinstance(notes, dict):
                logger.warning(f"Formato inesperado no arquivo de notas '{PLAYER_NOTES_FILE}'. Resetando para {{}}.")
                save_player_notes({})
                return {}
            return notes
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Erro ao carregar notas dos jogadores de {PLAYER_NOTES_FILE}: {e}. Resetando para {{}}.")
        # Em caso de erro, tenta criar um arquivo de backup e retorna um dicionário vazio
        try:
            backup_file = f"{PLAYER_NOTES_FILE}.bak_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            if os.path.exists(PLAYER_NOTES_FILE):
                os.rename(PLAYER_NOTES_FILE, backup_file)
                logger.info(f"Arquivo de notas corrompido movido para {backup_file}")
        except Exception as backup_e:
            logger.error(f"Erro ao tentar fazer backup do arquivo de notas corrompido: {backup_e}")
        save_player_notes({}) # Cria um novo arquivo vazio
        return {}

def save_player_notes(notes_data: Dict[str, Dict[str, str]]) -> None:
    """Salva as notas dos jogadores no arquivo JSON local."""
    try:
        with open(PLAYER_NOTES_FILE, 'w', encoding='utf-8') as f:
            json.dump(notes_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Erro ao salvar notas dos jogadores em {PLAYER_NOTES_FILE}: {e}")
    except Exception as e:
        logger.error(f"Erro inesperado ao salvar notas dos jogadores: {e}", exc_info=True)

# --- Funções de Busca de Dados da API CoC ---
async def get_clan_data_base(tag: str) -> Clan:
    """Busca dados básicos de um clã da API CoC."""
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
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
    """Busca dados de um jogador da API CoC, com cache de curto prazo."""
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
    """Busca dados de um clã, utilizando um cache de maior duração."""
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
    """Busca o ID de uma localização pelo nome."""
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        locations = await bot.coc_client.search_locations(name=location_name, limit=1)
        if not locations: raise ValueError(f"Localização '{location_name}' não encontrada.")
        loc_obj = locations[0]
        if hasattr(loc_obj, 'id'): return loc_obj.id
        else: raise ValueError(f"Objeto de localização para '{location_name}' não possui ID.")
    except Exception as e: logger.error(f"Erro ao buscar ID da localização '{location_name}': {e}", exc_info=True); raise ValueError(f"Erro ao buscar ID da localização: {str(e)}")

# --- Funções de Formatação e Envio de Mensagens no Discord ---
async def send_log_embed(embed_to_log: discord.Embed, content: str = None) -> None:
    """Envia um embed para o canal de log configurado."""
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
    """Envia uma lista de itens em múltiplos embeds se necessário, para evitar limites do Discord."""
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
        if (len(current_field_value_split) + len(item_line) > 1024 or len(current_embed_split) + len(current_field_value_split) + len(item_line) > 5900): # Limites de campo e embed
            if current_field_value_split: current_embed_split.add_field(name=(field_name or "Dados"), value=current_field_value_split, inline=False)
            if current_embed_split.fields: embeds_to_send.append(current_embed_split)
            current_embed_split = discord.Embed.from_dict(base_embed.to_dict()); current_field_value_split = item_line
            if len(current_field_value_split) > 1024: current_field_value_split = current_field_value_split[:1021] + "...\n" # Trunca se um único item for muito grande
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
    """Formata os detalhes de tempo de uma guerra (início, fim, tempo restante)."""
    details: Dict[str, Any] = { "time_key": "N/A", "time_value": "N/A", "time_remaining": "N/A", "start_time_iso": None, "end_time_iso": None }
    if hasattr(war_obj, 'state') and war_obj.state == "preparation":
        if hasattr(war_obj, 'start_time') and war_obj.start_time and hasattr(war_obj.start_time, 'time'):
            start_aware = pytz.utc.localize(war_obj.start_time.time).astimezone(TIMEZONE)
            details["start_time_iso"] = start_aware.isoformat()
            details["time_key"] = "Início"
            details["time_value"] = start_aware.strftime('%d/%m/%y %H:%M')
            delta = start_aware - time_now_tz
            if delta.total_seconds() > 0:
                d, r = divmod(delta.total_seconds(), 86400); h, r_h = divmod(r, 3600); m, _ = divmod(r_h, 60)
                details["time_remaining"] = f"{int(d)}d {int(h)}h {int(m)}m" if d > 0 else f"{int(h)}h {int(m)}m"
            else:
                details["time_remaining"] = "Iniciando..."

    elif hasattr(war_obj, 'state') and (war_obj.state == "inWar" or war_obj.state == "warEnded"):
        if hasattr(war_obj, 'end_time') and war_obj.end_time and hasattr(war_obj.end_time, 'time'):
            end_aware = pytz.utc.localize(war_obj.end_time.time).astimezone(TIMEZONE)
            details["end_time_iso"] = end_aware.isoformat()
            details["time_key"] = "Fim" if war_obj.state == "inWar" else "Finalizada em"
            details["time_value"] = end_aware.strftime('%d/%m/%y %H:%M')
            if war_obj.state == "inWar":
                delta = end_aware - time_now_tz
                if delta.total_seconds() > 0:
                    d, r = divmod(delta.total_seconds(), 86400); h, r_h = divmod(r, 3600); m, _ = divmod(r_h, 60)
                    details["time_remaining"] = f"{int(d)}d {int(h)}h {int(m)}m" if d > 0 else f"{int(h)}h {int(m)}m"
                else:
                    details["time_remaining"] = "Finalizando..."
            else: # warEnded
                details["time_remaining"] = "-"
    return details

async def get_current_or_last_war(clan_tag_param: str) -> Optional[ClanWar]:
    """Busca a guerra atual (regular ou CWL) ou a última guerra CWL finalizada."""
    current_war: Optional[ClanWar] = None
    # Tenta buscar guerra CWL primeiro, pois pode estar em andamento mesmo se a regular não estiver
    try:
        if LeagueGroup: # Verifica se a classe LeagueGroup foi importada com sucesso
            league_group = await bot.coc_client.get_league_group(clan_tag_param)
            if league_group and getattr(league_group,'state',None) != "notInWar" and hasattr(league_group, 'rounds'):
                # Verifica guerras CWL ativas ou em preparação
                if hasattr(league_group, 'current_wars') and league_group.current_wars:
                    for war_tag_obj in reversed(league_group.current_wars): # Itera das mais recentes
                        try:
                            lg_war = await league_group.get_league_war(war_tag_obj.tag)
                            if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param) and lg_war.state in ["inWar", "preparation"]:
                                current_war = lg_war
                                # Normaliza para que 'clan' seja sempre o nosso clã
                                if lg_war.opponent.tag == clan_tag_param: current_war.clan, current_war.opponent = current_war.opponent, current_war.clan
                                return current_war
                        except (coc.NotFound, Exception): continue # Ignora erros ao buscar uma guerra específica da liga
                # Se não encontrou em current_wars, verifica todas as rodadas
                for war_tags_in_round in reversed(league_group.rounds):
                    for war_tag_str in war_tags_in_round:
                        if war_tag_str == "#0": continue # Pula "bye rounds"
                        try:
                            lg_war = await league_group.get_league_war(war_tag_str)
                            if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param) and lg_war.state in ["inWar", "preparation"]:
                                current_war = lg_war
                                if lg_war.opponent.tag == clan_tag_param: current_war.clan, current_war.opponent = current_war.opponent, current_war.clan
                                return current_war
                        except (coc.NotFound, Exception): continue
                # Se nenhuma CWL ativa ou em preparação, pega a última CWL finalizada
                if not current_war and league_group.rounds:
                    best_ended_cwl_war = None
                    for war_tags_in_round in reversed(league_group.rounds):
                        for war_tag_str in war_tags_in_round:
                            if war_tag_str == "#0": continue
                            try:
                                lg_war = await league_group.get_league_war(war_tag_str)
                                if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param) and lg_war.state == "warEnded":
                                    if not best_ended_cwl_war or \
                                       (hasattr(lg_war, 'end_time') and hasattr(best_ended_cwl_war, 'end_time') and \
                                        lg_war.end_time and best_ended_cwl_war.end_time and \
                                        lg_war.end_time.time > best_ended_cwl_war.end_time.time):
                                        best_ended_cwl_war = lg_war
                            except (coc.NotFound, Exception): continue
                    if best_ended_cwl_war:
                        if best_ended_cwl_war.opponent.tag == clan_tag_param: best_ended_cwl_war.clan, best_ended_cwl_war.opponent = best_ended_cwl_war.opponent, best_ended_cwl_war.clan
                        return best_ended_cwl_war
    except coc.NotFound:
        logger.debug(f"Nenhum grupo CWL encontrado para o clã {clan_tag_param}.")
    except Exception as e_cwl:
        logger.error(f"Erro ao buscar dados da guerra CWL para {clan_tag_param}: {e_cwl}", exc_info=True)

    # Se não encontrou guerra CWL ativa/preparação, tenta guerra regular
    try:
        regular_war = await bot.coc_client.get_current_war(clan_tag_param)
        if regular_war and regular_war.state != "notInWar": # notInWar, preparation, inWar, warEnded
            return regular_war
    except coc.PrivateWarLog:
        logger.warning(f"Log de guerra regular do clã {clan_tag_param} é privado.")
    except coc.NotFound:
        logger.debug(f"Nenhuma guerra regular ativa ou em preparação encontrada para {clan_tag_param}.")
    except Exception as e_reg:
        logger.error(f"Erro ao buscar dados da guerra regular para {clan_tag_param}: {e_reg}", exc_info=True)
    
    return None # Retorna None se nenhuma guerra (CWL ou regular) for encontrada

# ============================================================================ #
# ==================== FUNÇÕES PARA O PAINEL WEB (API) ======================= #
# ============================================================================ #
web_api_cache: Dict[str, Dict[str, Any]] = {}
WEB_API_CACHE_DURATION_SECONDS = 45 # Cache para os dados da API do painel

async def get_cached_web_data(key: str, func_to_fetch_data: callable, *args: Any) -> Any:
    """Função genérica para buscar dados com cache para a API do painel."""
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
    """Busca informações do clã para a API do painel."""
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG) # Usa a função de cache
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
    """Busca lista de membros do clã com suas notas para a API do painel."""
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
        members_data.sort(key=lambda x: x.get("trophies", 0), reverse=True) # Ordena por troféus
        return {"members": members_data, "clan_name": clan.name, "clan_tag": clan.tag}
    except Exception as e:
        logger.error(f"Erro ao buscar membros do clã para API web: {e}", exc_info=True)
        return {"error": str(e)}

async def get_member_war_details_async(member: ClanMember, war_obj_ref: ClanWar) -> Dict[str, Any]:
    """Função auxiliar para obter detalhes de um membro em uma guerra específica."""
    member_attacks_data = []
    if member.attacks:
        for atk in member.attacks:
            try: p_def = player_short_term_cache.get(atk.defender_tag) or await get_player_data(atk.defender_tag)
            except ValueError: p_def = None
            member_attacks_data.append({"defender_tag": atk.defender_tag, "defender_name": p_def.name if p_def else atk.defender_tag,
                                        "defender_townhall": p_def.town_hall if p_def else '?', "stars": atk.stars, "destruction": atk.destruction, "order": atk.order})
    member_defenses_data = []
    if hasattr(member, 'defenses') and member.defenses: # Verifica se o atributo 'defenses' existe
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
    """Busca e formata detalhes da guerra atual para a API do painel, usando apenas a API Oficial CoC."""
    if not CLAN_TAG:
        return {"error": "CLAN_TAG não configurado.", "war_data": None, "attacks": [], "our_clan_members_in_war": [], "opponent_clan_members_in_war": []}

    player_short_term_cache.clear() # Limpa cache de jogadores para garantir dados frescos de TH para ataques
    final_response: Dict[str, Any] = {
        "war_data": None, "all_attacks": [],
        "our_clan_members_in_war": [], "opponent_clan_members_in_war": []
    }

    try:
        war_from_coc_api = await get_current_or_last_war(CLAN_TAG) # Usa a API Oficial CoC
        
        if not war_from_coc_api or getattr(war_from_coc_api, 'state', "notInWar") == "notInWar":
            logger.info("Nenhuma guerra ativa ou recente encontrada na API CoC Oficial para o painel.")
            return {"error": "Nenhuma guerra para detalhar.", "war_data": None, "attacks": [], "our_clan_members_in_war": [], "opponent_clan_members_in_war": []}

        logger.info(f"Guerra encontrada via API CoC Oficial: Estado {war_from_coc_api.state}")
        
        # Normaliza clan e opponent
        our_clan_obj, opp_clan_obj = (war_from_coc_api.clan, war_from_coc_api.opponent)
        if war_from_coc_api.clan.tag != CLAN_TAG and war_from_coc_api.opponent.tag == CLAN_TAG:
            our_clan_obj, opp_clan_obj = opp_clan_obj, our_clan_obj
        elif war_from_coc_api.clan.tag != CLAN_TAG and war_from_coc_api.opponent.tag != CLAN_TAG:
             # Isso pode acontecer em CWL se o clã estiver como oponente em uma rodada específica.
             # O frontend deve ser capaz de lidar com isso, mostrando o clã correto como "nosso".
             logger.warning(f"fetch_current_war_details: Guerra {getattr(war_from_coc_api, 'war_tag', 'N/A')} não parece envolver diretamente {CLAN_TAG} como 'clan', mas pode ser 'opponent'.")
        
        time_details_coc = format_war_time_details(war_from_coc_api, datetime.datetime.now(TIMEZONE))
        war_type_coc = "Guerra" # Padrão
        if hasattr(war_from_coc_api, 'is_cwl') and war_from_coc_api.is_cwl: war_type_coc = "CWL"
        elif hasattr(war_from_coc_api, 'type') and war_from_coc_api.type == "friendly": war_type_coc = "Amistosa"

        # Detalhes dos membros na guerra
        if our_clan_obj and hasattr(our_clan_obj, 'members') and our_clan_obj.members:
            final_response["our_clan_members_in_war"] = [await get_member_war_details_async(m, war_from_coc_api) for m in our_clan_obj.members]
            final_response["our_clan_members_in_war"].sort(key=lambda m: m["map_position"])
        if opp_clan_obj and hasattr(opp_clan_obj, 'members') and opp_clan_obj.members:
            final_response["opponent_clan_members_in_war"] = [await get_member_war_details_async(m, war_from_coc_api) for m in opp_clan_obj.members]
            final_response["opponent_clan_members_in_war"].sort(key=lambda m: m["map_position"])
        
        # Detalhes dos ataques
        if war_from_coc_api.attacks:
            for attack in sorted(war_from_coc_api.attacks, key=lambda a: a.order):
                try: p_att = await get_player_data(attack.attacker_tag); att_name, att_th = p_att.name, p_att.town_hall
                except ValueError: att_name, att_th = attack.attacker_tag, '?' # Fallback se jogador não encontrado
                try: p_def = await get_player_data(attack.defender_tag); def_name, def_th = p_def.name, p_def.town_hall
                except ValueError: def_name, def_th = attack.defender_tag, '?' # Fallback
                final_response["all_attacks"].append({
                    "order": attack.order, "attacker_tag": attack.attacker_tag, "attacker_name": att_name, "attacker_townhall": att_th,
                    "defender_tag": attack.defender_tag, "defender_name": def_name, "defender_townhall": def_th,
                    "stars": attack.stars, "destruction": attack.destruction, "duration": getattr(attack, 'duration', 'N/A')})
        
        # Cálculo de estatísticas (distribuição de estrelas, médias)
        clan_star_dist = {0:0,1:0,2:0,3:0}; opp_star_dist = {0:0,1:0,2:0,3:0}
        c_total_dur, c_atk_count, o_total_dur, o_atk_count = 0.0,0,0.0,0
        for att_det in final_response["all_attacks"]:
            # Verifica se o atacante é do nosso clã (considerando que our_clan_obj pode ser o oponente em CWL)
            is_our_att = (our_clan_obj and att_det["attacker_tag"].startswith(our_clan_obj.tag)) or \
                         any(m_w["tag"] == att_det["attacker_tag"] for m_w in final_response["our_clan_members_in_war"])

            current_star_dist = clan_star_dist if is_our_att else opp_star_dist
            current_star_dist[att_det["stars"]] = current_star_dist.get(att_det["stars"], 0) + 1
            
            duration_val = att_det["duration"]
            if isinstance(duration_val, (int, float)): # Duração pode ser int ou float
                if is_our_att: c_total_dur += duration_val; c_atk_count +=1
                else: o_total_dur += duration_val; o_atk_count +=1
        
        # Monta o dicionário final para war_data
        final_response["war_data"] = {
            "status": war_from_coc_api.state, 
            "type": war_type_coc,
            "state_description": war_from_coc_api.state.capitalize() if war_from_coc_api.state else "N/A",
            "clan_name": our_clan_obj.name if our_clan_obj else "N/A", 
            "clan_tag": our_clan_obj.tag if our_clan_obj else "N/A", 
            "clan_stars": our_clan_obj.stars if our_clan_obj else 0,
            "clan_destruction": f"{our_clan_obj.destruction:.2f}%" if our_clan_obj else "0.00%",
            "clan_badge_url": our_clan_obj.badge.url if our_clan_obj and hasattr(our_clan_obj.badge, 'url') else None,
            "clan_attacks_used": our_clan_obj.attacks_used if our_clan_obj and hasattr(our_clan_obj, 'attacks_used') else len([a for m_w in final_response["our_clan_members_in_war"] for a in m_w['attacks_made']]),
            "opponent_name": opp_clan_obj.name if opp_clan_obj else "N/A", 
            "opponent_tag": opp_clan_obj.tag if opp_clan_obj else "N/A", 
            "opponent_stars": opp_clan_obj.stars if opp_clan_obj else 0,
            "opponent_destruction": f"{opp_clan_obj.destruction:.2f}%" if opp_clan_obj else "0.00%",
            "opponent_badge_url": opp_clan_obj.badge.url if opp_clan_obj and hasattr(opp_clan_obj.badge, 'url') else None,
            "opponent_attacks_used": opp_clan_obj.attacks_used if opp_clan_obj and hasattr(opp_clan_obj, 'attacks_used') else len([a for m_w in final_response["opponent_clan_members_in_war"] for a in m_w['attacks_made']]),
            **time_details_coc, # Inclui time_key, time_value, time_remaining
            "attacks_per_member": war_from_coc_api.attacks_per_member, 
            "team_size": war_from_coc_api.team_size,
            "clan_star_distribution": clan_star_dist, 
            "opponent_star_distribution": opp_star_dist,
            "clan_avg_stars": f"{our_clan_obj.stars/c_atk_count:.2f}" if our_clan_obj and c_atk_count > 0 else "0.00",
            "opponent_avg_stars": f"{opp_clan_obj.stars/o_atk_count:.2f}" if opp_clan_obj and o_atk_count > 0 else "0.00",
            "clan_avg_destruction_percent": f"{our_clan_obj.destruction:.2f}" if our_clan_obj else "0.00", # Média já é a destruição total do clã
            "opponent_avg_destruction_percent": f"{opp_clan_obj.destruction:.2f}" if opp_clan_obj else "0.00",
            "clan_avg_duration": f"{c_total_dur/c_atk_count:.1f}s" if c_atk_count > 0 else "0s",
            "opponent_avg_duration": f"{o_total_dur/o_atk_count:.1f}s" if o_atk_count > 0 else "0s",
            "source": "API CoC Oficial" # Indica a fonte dos dados
        }
    except Exception as e:
        logger.error(f"Erro geral ao processar detalhes da guerra: {e}", exc_info=True)
        return {"error": f"Erro ao buscar detalhes da guerra: {e}", "war_data": None, "attacks": [], "our_clan_members_in_war": [], "opponent_clan_members_in_war": []}

    return final_response

async def fetch_war_attacks_remaining_for_web_api() -> Dict[str, Any]:
    """Busca membros com ataques pendentes na guerra atual."""
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    war = await get_current_or_last_war(CLAN_TAG)
    clan_name_rem = "N/A"
    our_clan_obj_rem = None

    if war:
        if war.clan.tag == CLAN_TAG:
            our_clan_obj_rem = war.clan
            clan_name_rem = our_clan_obj_rem.name
        elif war.opponent.tag == CLAN_TAG: # Caso seja uma guerra de liga e nosso clã seja o oponente
            our_clan_obj_rem = war.opponent
            clan_name_rem = our_clan_obj_rem.name
        
    if not war or war.state != "inWar":
        return {"message": "Não há guerra em andamento.", "members_pending": [], "clan_name": clan_name_rem}
    
    if not our_clan_obj_rem: # Se por algum motivo não identificou nosso clã
        return {"message": "Erro ao identificar o clã na guerra.", "members_pending": [], "clan_name": "Erro"}

    pending = []
    if hasattr(our_clan_obj_rem, 'members') and our_clan_obj_rem.members:
        for m in our_clan_obj_rem.members:
            attacks_left = war.attacks_per_member - (len(m.attacks) if m.attacks else 0)
            if attacks_left > 0:
                pending.append({
                    "name": m.name, "tag": m.tag, 
                    "town_hall": m.town_hall, "attacks_left": attacks_left, 
                    "map_position": m.map_position
                })
    pending.sort(key=lambda x: x.get("map_position", 0)) # Ordena pela posição no mapa
    return {"message": "Membros com ataques pendentes:", "members_pending": pending, "clan_name": clan_name_rem}

async def fetch_war_log_for_web_api(limit: int = 10) -> Dict[str, Any]:
    """Busca o histórico de guerras do clã."""
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    if not WarLogEntry: return {"error": "Histórico de Guerras indisponível (dependência não carregada).", "log": []}
    try:
        log_iter = await bot.coc_client.get_war_log(CLAN_TAG, limit=limit) # Usa o limite da API
        entries = []
        # A API coc.py já retorna uma lista, não um iterador assíncrono para get_war_log
        for entry in log_iter: # log_iter aqui é uma lista de WarLogEntry
            res = "N/A"
            # Determina o resultado da perspectiva do nosso clã
            if entry.clan.tag == CLAN_TAG:
                if entry.result: res = "Vitória" if entry.result == "win" else "Derrota" if entry.result == "lose" else "Empate"
            elif entry.opponent.tag == CLAN_TAG: # Se nosso clã foi o oponente
                if entry.result: res = "Derrota" if entry.result == "win" else "Vitória" if entry.result == "lose" else "Empate"
            
            entries.append({
                "clan_name": entry.clan.name if entry.clan else "N/A", 
                "clan_stars": entry.clan.stars if entry.clan else 0, 
                "clan_destruction": entry.clan.destruction if entry.clan else 0.0,
                "clan_badge_url": entry.clan.badge.url if entry.clan and hasattr(entry.clan.badge, 'url') else None,
                "opponent_name": entry.opponent.name if entry.opponent else "N/A", 
                "opponent_stars": entry.opponent.stars if entry.opponent else 0, 
                "opponent_destruction": entry.opponent.destruction if entry.opponent else 0.0,
                "opponent_badge_url": entry.opponent.badge.url if entry.opponent and hasattr(entry.opponent.badge, 'url') else None,
                "team_size": entry.team_size, 
                "end_time": entry.end_time.time.astimezone(TIMEZONE).strftime('%d/%m/%y %H:%M') if entry.end_time and hasattr(entry.end_time, 'time') else "N/A",
                "result": res, 
                "is_cwl": getattr(entry, 'is_cwl', False) # Verifica se é CWL (pode não estar presente em todas as versões de coc.py para WarLogEntry)
            })
        return {"log": entries}
    except coc.PrivateWarLog:
        return {"error": "Log de guerras do clã é privado."}
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de guerras para API web: {e}", exc_info=True)
        return {"error": str(e)}

async def fetch_cwl_info_for_web_api() -> Dict[str, Any]:
    """Busca informações da CWL atual do clã."""
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    if not LeagueGroup: return {"status": "CwlFeatureDisabled", "message": "Funcionalidade de CWL indisponível (dependência não carregada)."}
    try:
        lg = await bot.coc_client.get_league_group(CLAN_TAG)
        if not lg or (hasattr(lg, 'state') and lg.state == "notInWar"):
            return {"status": "NotInCwl", "message": "Clã não está em CWL no momento."}
        
        rounds_data = []
        if hasattr(lg, 'rounds') and lg.rounds:
            for i, round_tags in enumerate(lg.rounds):
                r_info: Dict[str, Any] = {"round_number": i + 1, "wars": []}
                if not round_tags: r_info["wars"].append({"message": "Rodada não definida."})
                else:
                    for war_tag_val in round_tags:
                        if war_tag_val == "#0": r_info["wars"].append({"message":"Rodada de descanso (Bye)."}); continue
                        try:
                            war = await lg.get_league_war(war_tag_val) # Busca cada guerra da rodada
                            # Normaliza para que 'our_display_clan' seja sempre o clã monitorado
                            our_display_clan, opp_display_clan = (war.clan, war.opponent)
                            if war.clan.tag != CLAN_TAG and war.opponent.tag == CLAN_TAG:
                                our_display_clan, opp_display_clan = opp_display_clan, our_display_clan
                            
                            td = format_war_time_details(war, datetime.datetime.now(TIMEZONE))
                            r_info["wars"].append({
                                "war_tag": war_tag_val, "state": war.state,
                                "clan_name": our_display_clan.name, "clan_stars": our_display_clan.stars, 
                                "clan_destruction":f"{our_display_clan.destruction:.2f}%", 
                                "clan_badge_url": our_display_clan.badge.url if hasattr(our_display_clan.badge, 'url') else None,
                                "opponent_name": opp_display_clan.name, "opponent_stars": opp_display_clan.stars, 
                                "opponent_destruction":f"{opp_display_clan.destruction:.2f}%", 
                                "opponent_badge_url": opp_display_clan.badge.url if hasattr(opp_display_clan.badge, 'url') else None,
                                **td
                            })
                        except Exception as e_w:
                            logger.error(f"Erro ao buscar guerra CWL específica ({war_tag_val}): {e_w}")
                            r_info["wars"].append({"war_tag": war_tag_val, "error":f"Erro ao carregar guerra: {e_w}"})
                rounds_data.append(r_info)
        
        clans_data = []
        if hasattr(lg, 'clans') and lg.clans:
            clans_data = [{"name":c.name, "tag":c.tag, "level":c.level, "badge_url":c.badge.url if hasattr(c.badge, 'url') else None} for c in lg.clans]

        return {
            "status":"InCwl", "state":lg.state, 
            "season":lg.season.strftime('%Y-%m') if hasattr(lg,'season') and lg.season else "N/A", 
            "clans_in_group":clans_data, "rounds":rounds_data
        }
    except coc.NotFound:
        return {"status": "NotInCwl", "message": "Grupo CWL não encontrado para o clã."}
    except Exception as e:
        logger.error(f"Erro ao buscar informações da CWL para API web: {e}", exc_info=True)
        return {"error":str(e)}

# --- Handlers da API Web (Endpoints) ---
async def api_clan_info_handler(request: web.Request) -> web.Response:
    return web.json_response(await get_cached_web_data(f"web_clan_info_{CLAN_TAG}", fetch_clan_info_for_web_api))
async def api_members_handler(request: web.Request) -> web.Response:
    return web.json_response(await get_cached_web_data(f"web_clan_members_{CLAN_TAG}", fetch_clan_members_for_web_api))
async def api_current_war_details_handler(request: web.Request) -> web.Response:
    return web.json_response(await get_cached_web_data(f"web_current_war_details_{CLAN_TAG}", fetch_current_war_details_for_web_api))
async def api_war_attacks_remaining_handler(request: web.Request) -> web.Response:
    return web.json_response(await get_cached_web_data(f"web_war_attacks_remaining_{CLAN_TAG}", fetch_war_attacks_remaining_for_web_api))
async def api_war_log_handler(request: web.Request) -> web.Response:
    limit = int(request.query.get("limit","10")); limit=max(1,min(limit,50)) # Limita o número de entradas do log
    return web.json_response(await get_cached_web_data(f"web_war_log_{CLAN_TAG}_limit{limit}",fetch_war_log_for_web_api,limit))
async def api_cwl_info_handler(request: web.Request) -> web.Response:
    return web.json_response(await get_cached_web_data(f"web_cwl_info_{CLAN_TAG}", fetch_cwl_info_for_web_api))

# --- Rotas para Notas dos Jogadores (JSON Local) ---
async def api_get_player_note_handler(request: web.Request) -> web.Response:
    player_tag = request.match_info.get('player_tag', None)
    if not player_tag:
        return web.json_response({"error": "Player tag não fornecida"}, status=400)
    player_tag_fmt = f"#{player_tag}" if not player_tag.startswith("#") else player_tag
    notes = load_player_notes()
    note_info = notes.get(player_tag_fmt, {"text": "", "priority": "none"})
    return web.json_response(note_info)

async def api_save_player_note_handler(request: web.Request) -> web.Response:
    player_tag = request.match_info.get('player_tag', None)
    if not player_tag:
        return web.json_response({"error": "Player tag não fornecida"}, status=400)
    player_tag_fmt = f"#{player_tag}" if not player_tag.startswith("#") else player_tag
    try:
        data = await request.json()
        note_text = data.get("text", "")
        note_priority = data.get("priority", "none")
        if note_priority not in ["none", "green", "yellow", "red"]:
            return web.json_response({"error": "Prioridade inválida"}, status=400)

        notes = load_player_notes()
        notes[player_tag_fmt] = {"text": note_text, "priority": note_priority}
        save_player_notes(notes) 
        logger.info(f"Nota salva localmente para {player_tag_fmt}: Prio: {note_priority}, Texto: '{note_text[:30]}...'")

        # Invalida caches relevantes para que o painel atualize
        if f"web_clan_members_{CLAN_TAG}" in web_api_cache:
            del web_api_cache[f"web_clan_members_{CLAN_TAG}"]
            logger.info(f"Cache de membros invalidado para {CLAN_TAG} após salvar nota local.")
        # Se a nota puder influenciar a exibição da guerra (improvável, mas por segurança)
        if f"web_current_war_details_{CLAN_TAG}" in web_api_cache:
            del web_api_cache[f"web_current_war_details_{CLAN_TAG}"]
            logger.info(f"Cache de detalhes da guerra invalidado para {CLAN_TAG} após salvar nota.")

        return web.json_response({"success": True, "message": "Nota salva com sucesso."})
    except json.JSONDecodeError:
        return web.json_response({"error": "Payload JSON inválido"}, status=400)
    except Exception as e:
        logger.error(f"Erro ao salvar nota para {player_tag_fmt}: {e}", exc_info=True)
        return web.json_response({"error": "Erro interno ao salvar nota"}, status=500)

# --- Configuração do Servidor Web (aiohttp) ---
async def handle_panel_index(request: web.Request) -> web.FileResponse | web.Response:
    """Serve o arquivo principal do painel (painel.html)."""
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "painel.html")
    try: return web.FileResponse(index_path)
    except FileNotFoundError: logger.error(f"painel.html não encontrado em {index_path}"); return web.Response(text="Painel não encontrado.", status=404)
    except Exception as e: logger.error(f"Erro ao servir painel.html: {e}"); return web.Response(text="Erro ao carregar painel.", status=500)

async def setup_web_server() -> Optional[web.AppRunner]:
    """Configura e inicia o servidor web para o painel."""
    app = web.Application()
    async def health_check(request: web.Request) -> web.Response: return web.Response(text=f"Bot running! Panel active! v{BOT_VERSION}")
    
    # Rotas da API
    app.router.add_get("/api/clan", api_clan_info_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/current_war_details", api_current_war_details_handler)
    app.router.add_get("/api/war_attacks_remaining", api_war_attacks_remaining_handler)
    app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler)
    app.router.add_get("/api/notes/{player_tag}", api_get_player_note_handler) # GET para buscar nota específica
    app.router.add_post("/api/notes/{player_tag}", api_save_player_note_handler) # POST para salvar/atualizar nota

    # Rota para o painel e arquivos estáticos
    app.router.add_get("/painel", handle_panel_index)
    static_path = os.path.join(os.path.dirname(__file__), "static")
    # Cria pastas estáticas se não existirem
    for folder in ["css", "js", "images"]:
        path_to_create = os.path.join(static_path, folder)
        if not os.path.exists(path_to_create): os.makedirs(path_to_create); logger.info(f"Pasta '{path_to_create}' criada.")
    # Cria arquivos estáticos padrão se não existirem
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
    app.router.add_get("/", health_check) # Rota raiz para verificação de saúde
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080)) # Porta do Render.com ou padrão 8080
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    try:
        await site.start()
        logger.info(f"Servidor web iniciado: http://0.0.0.0:{port}")
        return runner
    except Exception as e:
        logger.error(f"Falha ao iniciar servidor web: {e}", exc_info=True)
        return None

# --- Lógica do Bot Discord (Eventos, Tarefas, Comandos) ---
# (O restante do seu código, como format_attacks_remaining_embed, send_missed_attacks_report,
# on_ready, on_app_command_error, register_coc_events, check_war_end_report_task,
# grupos de comandos, setup_hook, main, etc., permanece o mesmo da versão 19.8.1)
# ... (COLE O RESTANTE DO SEU CÓDIGO A PARTIR DAQUI) ...
async def format_attacks_remaining_embed(war: ClanWar) -> Optional[List[discord.Embed]]:
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
        reg_war = await bot.coc_client.get_current_war(CLAN_TAG)
        if reg_war and reg_war.state != "notInWar" and hasattr(reg_war, 'end_time'): await process_war_for_report(reg_war, "Guerra Normal")
    except Exception as e: logger.error(f"check_war_end_report_task: Erro guerra regular: {e}", exc_info=True)
    try:
        if LeagueGroup:
            lg_task = await bot.coc_client.get_league_group(CLAN_TAG)
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
        if LeagueGroup:
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
                    for _round_num_cmd, war_tags_cmd_list in enumerate(league_group_cmd.rounds):
                        if current_war_cmd: break
                        for war_tag_cmd_val_inner in war_tags_cmd_list:
                            if war_tag_cmd_val_inner == "#0": continue
                            try:
                                 league_war_cmd_obj_inner = await league_group_cmd.get_league_war(war_tag_cmd_val_inner)
                                 if league_war_cmd_obj_inner and (league_war_cmd_obj_inner.clan.tag == CLAN_TAG or league_war_cmd_obj_inner.opponent.tag == CLAN_TAG) and league_war_cmd_obj_inner.state == "inWar":
                                     current_war_cmd = league_war_cmd_obj_inner; break
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

@war_group.command(name="status", description="Exibe o status da guerra atual (Normal ou Liga)")
async def war_status(interaction: discord.Interaction):
    await interaction.response.defer(); war_to_display: Optional[ClanWar] = None; war_type_name_status = "Guerra"
    status_description = "Nenhuma guerra ativa ou recente encontrada."; status_color = discord.Color.greyple()
    try:
        if LeagueGroup:
            league_group_status = await bot.coc_client.get_league_group(CLAN_TAG)
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
                                if lg_war_obj.opponent.tag == CLAN_TAG: lg_war_obj.clan, lg_war_obj.opponent = lg_war_obj.opponent, lg_war_obj.clan
                                if lg_war_obj.state == "inWar": active_cwl_war = lg_war_obj; current_round_num = round_num_status + 1; break
                                elif lg_war_obj.state == "preparation": prep_cwl_war = lg_war_obj; prep_round_num = round_num_status + 1
                                elif lg_war_obj.state == "warEnded":
                                    if hasattr(lg_war_obj, 'end_time') and lg_war_obj.end_time and hasattr(lg_war_obj.end_time, 'time'):
                                        current_latest_end = getattr(latest_ended_cwl_war, 'end_time', None)
                                        if not latest_ended_cwl_war or not (hasattr(current_latest_end, 'time') and current_latest_end.time) or lg_war_obj.end_time.time > current_latest_end.time:
                                            latest_ended_cwl_war = lg_war_obj; ended_round_num = round_num_status + 1
                        except (coc.NotFound, Exception): continue
                    if active_cwl_war: break
                if active_cwl_war: war_to_display = active_cwl_war; war_type_name_status = f"Liga (Rodada {current_round_num})"
                elif prep_cwl_war: war_to_display = prep_cwl_war; war_type_name_status = f"Liga (Rodada {prep_round_num})"
                elif latest_ended_cwl_war: war_to_display = latest_ended_cwl_war; war_type_name_status = f"Liga (Rodada {ended_round_num})"
    except coc.NotFound: logger.info("/status: Clã não em grupo de liga.")
    except Exception as e: logger.error(f"Erro /status CWL: {e}", exc_info=True)
    if not war_to_display:
        try:
            regular_war_status = await bot.coc_client.get_current_war(CLAN_TAG)
            if regular_war_status and getattr(regular_war_status, 'state', None) != "notInWar": war_to_display = regular_war_status; war_type_name_status = "Guerra Normal"
        except coc.PrivateWarLog: status_description = "Log de guerra regular é privado."; status_color = discord.Color.orange()
        except coc.NotFound: logger.info("/status: Clã não encontrado (guerra regular).")
        except Exception as e: logger.error(f"Erro /status guerra regular: {e}", exc_info=True); status_description = "Erro ao buscar guerra regular."; status_color = discord.Color.red()
    embed_status_final = discord.Embed(title=f"⚔️ Status: {war_type_name_status}", color=status_color)
    if war_to_display and isinstance(war_to_display, coc.ClanWar):
        clan_disp, opp_disp = war_to_display.clan, war_to_display.opponent
        if clan_disp and opp_disp: # Garante que ambos os objetos de clã existem
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
    embed_status_final.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed_status_final.timestamp = datetime.datetime.now(TIMEZONE)
    await interaction.followup.send(embed=embed_status_final)

@info_group.command(name="clan", description="Exibe informações sobre um clã")
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def clan_info(interaction: discord.Interaction, tag: Optional[str] = None):
    target_tag_info = tag or CLAN_TAG
    if not target_tag_info: await interaction.response.send_message("Nenhuma tag de clã especificada.", ephemeral=True); return
    try:
        await interaction.response.defer(); clan_data_info = await get_clan_data_with_cache(target_tag_info)
        embed = discord.Embed(title=f"{clan_data_info.name} ({clan_data_info.tag})", description=clan_data_info.description or "S/ Descrição.", color=discord.Color.blue())
        if hasattr(clan_data_info, 'badge') and clan_data_info.badge: embed.set_thumbnail(url=clan_data_info.badge.url)
        embed.add_field(name="Nível",value=getattr(clan_data_info,'level','N/A'),inline=True); embed.add_field(name="Pontos",value=getattr(clan_data_info,'points','N/A'),inline=True)
        embed.add_field(name="Guerras Vencidas", value=getattr(clan_data_info,'war_wins','N/A'),inline=True)
        if hasattr(clan_data_info,'location') and clan_data_info.location: embed.add_field(name="Localização",value=clan_data_info.location.name,inline=True)
        embed.add_field(name="Tipo",value=getattr(clan_data_info,'type','N/A').capitalize(),inline=True)
        embed.add_field(name="Membros",value=f"{getattr(clan_data_info,'member_count','N/A')}/50",inline=True)
        if hasattr(clan_data_info,"capital_points"): embed.add_field(name="Troféus Capital",value=clan_data_info.capital_points,inline=True)
        if hasattr(clan_data_info,'public_war_log'): embed.add_field(name="Log de Guerra",value="Público" if clan_data_info.public_war_log else "Privado",inline=True)
        embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed)
    except ValueError as e: await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e: logger.error(f"Erro info clã {target_tag_info}: {e}", exc_info=True); await interaction.followup.send("Erro ao buscar info do clã.", ephemeral=True)

@info_group.command(name="jogador", description="Exibe informações sobre um jogador")
@app_commands.describe(tag="Tag do jogador (Ex: #P0LGYC9YQ)")
async def player_info(interaction: discord.Interaction, tag: str):
    try:
        await interaction.response.defer(); player_data_info = await get_player_data(tag)
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
        embed_player_info.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed_player_info.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed_player_info)
    except ValueError as e_val: await interaction.followup.send(str(e_val), ephemeral=True)
    except Exception as e_gen: logger.error(f"Erro info jogador {tag}: {e_gen}", exc_info=True); await interaction.followup.send("Erro ao buscar info do jogador.", ephemeral=True)

@info_group.command(name="membros", description="Lista os membros do clã")
async def clan_members(interaction: discord.Interaction, tag: Optional[str] = None):
    target_tag_members = tag or CLAN_TAG
    if not target_tag_members: await interaction.response.send_message("Nenhuma tag de clã especificada.", ephemeral=True); return
    try:
        await interaction.response.defer(); clan_data_members = await get_clan_data_with_cache(target_tag_members)
        base_embed = discord.Embed(title=f"👥 Membros de {clan_data_members.name}", description=f"Total: {getattr(clan_data_members, 'member_count', 'N/A')}/50", color=discord.Color.blue())
        if hasattr(clan_data_members, 'badge') and clan_data_members.badge: base_embed.set_thumbnail(url=clan_data_members.badge.url)
        details_list = []
        if hasattr(clan_data_members, 'members') and clan_data_members.members:
            order = {"leader":0, "co-leader":1, "admin":2, "member":3}
            sorted_m = sorted(clan_data_members.members, key=lambda m_item: (order.get(getattr(getattr(m_item,'role',None),'name','member').lower(),4), -getattr(m_item,'trophies',0)))
            for i, m_sorted_item in enumerate(sorted_m):
                details_list.append(f"{i+1}. **{m_sorted_item.name}** (CV{m_sorted_item.town_hall}) | {getattr(m_sorted_item.role,'name','Membro').capitalize()} | {m_sorted_item.trophies}🏆 | Doa:{m_sorted_item.donations}/Rec:{m_sorted_item.received}")
        else: details_list.append("Não foi possível listar membros.")
        await interaction.followup.send(embed=base_embed)
        splitter_base_embed = discord.Embed(color=discord.Color.blue())
        if interaction.channel:
            await send_embeds_splitted(interaction.channel, splitter_base_embed, "Lista de Membros", details_list)
        else:
            logger.warning("Comando /info membros: interaction.channel não encontrado para enviar detalhes divididos.")
            await interaction.followup.send("Não foi possível enviar a lista detalhada de membros (canal não encontrado).", ephemeral=True)

    except ValueError as e: await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e: logger.error(f"Erro lista membros {target_tag_members}: {e}", exc_info=True); await interaction.followup.send("Erro ao listar membros.",ephemeral=True)


@search_group.command(name="clan", description="Busca clãs por nome")
@app_commands.describe(nome="Nome (ou parte) do clã", min_membros="Mínimo de membros", max_membros="Máximo de membros", min_nivel="Nível mínimo", localizacao="Nome da localização (ex: Brazil)")
async def search_clan(interaction: discord.Interaction, nome: str, min_membros: Optional[app_commands.Range[int, 1, 50]] = None, max_membros: Optional[app_commands.Range[int, 1, 50]] = None, min_nivel: Optional[app_commands.Range[int, 1, None]] = None, localizacao: Optional[str] = None):
    await interaction.response.defer(); params:Dict[str,Any] = {'name': nome, 'limit': 10}
    if min_membros is not None: params['min_members'] = min_membros
    if max_membros is not None: params['max_members'] = max_membros
    if min_nivel is not None: params['min_clan_level'] = min_nivel
    loc_id = None
    if localizacao:
        try: loc_id = await fetch_location_id(localizacao); params['location'] = loc_id
        except ValueError as e_loc: await interaction.followup.send(f"Erro localização: {e_loc}", ephemeral=True); return
    try:
        clans_found = await bot.coc_client.search_clans(**params)
        if not clans_found: await interaction.followup.send(f"Nenhum clã encontrado com os critérios."); return

        base_embed_search = discord.Embed(title=f"🔎 Resultados da Busca por '{nome}'", color=discord.Color.og_blurple())
        if loc_id: base_embed_search.description = f"Localização: {localizacao}"

        clan_details_list = []
        for i, clan_s_item in enumerate(clans_found):
            clan_details_list.append(
                f"**{i+1}. {clan_s_item.name} ({clan_s_item.tag})**\n"
                f"Nível: {clan_s_item.level} | Membros: {clan_s_item.member_count}/50 | Pontos: {clan_s_item.points}🏆\n"
                f"Local: {clan_s_item.location.name if clan_s_item.location else 'N/A'} | Tipo: {clan_s_item.type.capitalize()}"
            )
        await interaction.followup.send(embed=base_embed_search)
        splitter_embed_search = discord.Embed(color=discord.Color.og_blurple())
        if interaction.channel:
             await send_embeds_splitted(interaction.channel, splitter_embed_search, "Clãs Encontrados", clan_details_list)
        else:
            logger.warning("Comando /buscar clan: interaction.channel não encontrado.")
            await interaction.followup.send("Não foi possível enviar a lista detalhada de clãs (canal não encontrado).", ephemeral=True)

    except Exception as e: logger.error(f"Erro busca clã: {e}", exc_info=True); await interaction.followup.send("Erro ao buscar clãs.",ephemeral=True)


@search_group.command(name="jogador", description="Busca jogadores por nome")
@app_commands.describe(nome="Nome (ou parte) do jogador")
async def search_player(interaction: discord.Interaction, nome: str):
    await interaction.response.defer()
    try:
        players_found = await bot.coc_client.search_players(name=nome, limit=10)
        if not players_found: await interaction.followup.send(f"Nenhum jogador '{nome}' encontrado."); return

        base_embed_psearch = discord.Embed(title=f"🧑‍ Resultados da Busca por Jogador '{nome}'", color=discord.Color.dark_green())
        player_details_s_list = []
        for i, p_s_item in enumerate(players_found):
            clan_name_s = p_s_item.clan.name if p_s_item.clan else "Sem Clã"
            player_details_s_list.append(
                f"**{i+1}. {p_s_item.name} ({p_s_item.tag})**\n"
                f"CV{p_s_item.town_hall} | Nível: {p_s_item.exp_level} | Liga: {p_s_item.league.name if p_s_item.league else 'N/A'}\n"
                f"Troféus: {p_s_item.trophies}🏆 | Clã: {clan_name_s}"
            )
        await interaction.followup.send(embed=base_embed_psearch)
        splitter_embed_psearch = discord.Embed(color=discord.Color.dark_green())
        if interaction.channel:
            await send_embeds_splitted(interaction.channel, splitter_embed_psearch, "Jogadores Encontrados", player_details_s_list)
        else:
            logger.warning("Comando /buscar jogador: interaction.channel não encontrado.")
            await interaction.followup.send("Não foi possível enviar a lista detalhada de jogadores (canal não encontrado).", ephemeral=True)

    except Exception as e: logger.error(f"Erro busca jogador: {e}", exc_info=True); await interaction.followup.send("Erro ao buscar jogadores.",ephemeral=True)


async def rank_command_base(interaction: discord.Interaction, tag: Optional[str], rank_type: str, key_func: callable, title_suffix: str, value_format_func: callable):
    await interaction.response.defer()
    target_tag_rank = tag or CLAN_TAG
    if not target_tag_rank: await interaction.followup.send("Nenhuma tag de clã especificada.", ephemeral=True); return
    try:
        clan_data_rank = await get_clan_data_with_cache(target_tag_rank)
        if not hasattr(clan_data_rank, 'members') or not clan_data_rank.members:
            await interaction.followup.send(f"Não há membros no clã {clan_data_rank.name} para exibir o ranking."); return

        sorted_members_rank = sorted(clan_data_rank.members, key=key_func, reverse=True)
        base_embed_rank = discord.Embed(title=f"🏆 Ranking de {title_suffix} - {clan_data_rank.name}", color=discord.Color.gold())
        if hasattr(clan_data_rank, 'badge') and clan_data_rank.badge: base_embed_rank.set_thumbnail(url=clan_data_rank.badge.url)

        rank_list_details = []
        for i, member_r_item in enumerate(sorted_members_rank[:25]):
            rank_list_details.append(f"**{i+1}. {member_r_item.name}**: {value_format_func(member_r_item)}")

        await interaction.followup.send(embed=base_embed_rank)
        splitter_embed_rank = discord.Embed(color=discord.Color.gold())
        if interaction.channel:
            await send_embeds_splitted(interaction.channel, splitter_embed_rank, f"Top {len(rank_list_details)} - {title_suffix}", rank_list_details)
        else:
            logger.warning(f"Comando /rank {rank_type}: interaction.channel não encontrado.")
            await interaction.followup.send(f"Não foi possível enviar o ranking detalhado de {title_suffix} (canal não encontrado).", ephemeral=True)

    except ValueError as e: await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e: logger.error(f"Erro rank {rank_type} {target_tag_rank}: {e}", exc_info=True); await interaction.followup.send(f"Erro ao buscar ranking de {title_suffix}.",ephemeral=True)

@rank_group.command(name="doacoes", description="Exibe o ranking de doações do clã")
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def donations_rank(interaction: discord.Interaction, tag: Optional[str] = None):
    await rank_command_base(interaction, tag, "doacoes", lambda m: m.donations, "Doações", lambda m: f"{m.donations} tropas")

@rank_group.command(name="trofeus", description="Exibe o ranking de troféus do clã")
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def trophies_rank(interaction: discord.Interaction, tag: Optional[str] = None):
    await rank_command_base(interaction, tag, "trofeus", lambda m: m.trophies, "Troféus", lambda m: f"{m.trophies}🏆")

@rank_group.command(name="cv", description="Exibe o ranking de Casa de Vila do clã")
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def th_rank(interaction: discord.Interaction, tag: Optional[str] = None):
    await rank_command_base(interaction, tag, "cv", lambda m: (m.town_hall, m.exp_level), "Nível de CV", lambda m: f"CV{m.town_hall} (Nível {m.exp_level})")


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
            except (ValueError, TypeError):
                logger.error(f"TEST_GUILD_ID ('{TEST_GUILD_ID}') inválido. Sincronizando globalmente...")
        if guild_obj_sync:
            bot.tree.copy_global_to(guild=guild_obj_sync)
            synced_cmds = await bot.tree.sync(guild=guild_obj_sync)
        else:
            synced_cmds = await bot.tree.sync()

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
            if hasattr(bot, "web_runner") and bot.web_runner:
                logger.info("Limpando web runner...")
                await bot.web_runner.cleanup()
                logger.info("Servidor web limpo.")
            if hasattr(bot, "coc_client") and bot.coc_client.http and not bot.coc_client.http.closed :
                logger.info("Fechando cliente CoC...")
                await bot.coc_client.close()
                logger.info("Cliente CoC fechado.")
            logger.info("Desligamento do bot concluído.")

def handle_asyncio_exception(loop: asyncio.AbstractEventLoop, context: Dict[str, Any]):
    msg = context.get("exception", context["message"])
    logger.error(f"Erro asyncio não tratado: {msg}", exc_info=context.get('exception'))

if __name__ == "__main__":
    required_env_vars = ["DISCORD_TOKEN", "COC_EMAIL", "COC_PASSWORD", "CLAN_TAG", "CHANNEL_ID"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        logger.critical(f"Variáveis de ambiente essenciais faltando: {', '.join(missing_vars)}. Verifique seu arquivo .env.")
        exit(1)

    loop = asyncio.get_event_loop()
    try:
        loop.set_exception_handler(handle_asyncio_exception)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário (KeyboardInterrupt).")
    except RuntimeError as e_loop:
        if "Event loop is closed" in str(e_loop):
            logger.info("Loop de eventos fechado durante o desligamento (normal).")
        else:
            logger.warning(f"RuntimeError no loop de eventos: {e_loop}", exc_info=True)
    except Exception as e_fatal:
        logger.critical(f"Erro fatal não capturado no loop principal: {e_fatal}", exc_info=True)
    finally:
        logger.info("Iniciando processo de finalização do loop de eventos...")
        if loop.is_running():
            logger.info("Parando o loop de eventos...")
            loop.stop()

        tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not asyncio.current_task(loop=loop)]
        if tasks:
            logger.info(f"Cancelando {len(tasks)} tarefas pendentes...")
            for task in tasks:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            logger.info("Tarefas pendentes canceladas.")

        if not loop.is_closed():
            logger.info("Fechando o loop de eventos...")
            loop.close()
            logger.info("Loop de eventos fechado.")
        else:
            logger.info("Loop de eventos já estava fechado.")
        logger.info("Programa finalizado.")

