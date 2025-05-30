# -*- coding: utf-8 -*-
# Versão 18.1 - Painel Web SPA com Detalhes do Jogador, Log de Eventos, CWL

import os
import logging
import asyncio
import datetime
import collections # << NOVO IMPORT
from aiohttp import web
from typing import Dict, List, Optional, Union, Set
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
from coc import ClanWar, Player, Clan, WarAttack, Timestamp, ClanMember, WarLogEntry, LeagueGroup, LeagueWar
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
    CHANNEL_ID = int(channel_id_str) if channel_id_str else 0
    if CHANNEL_ID == 0: logger.error("CHANNEL_ID não definido no .env. Usando 0 como padrão.")
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

BOT_VERSION = "18.1" # << VERSÃO ATUALIZADA
reported_war_ends: Set[str] = set()

# <<< NOVO: Log de Eventos do Clã em Memória >>>
MAX_EVENT_LOG_SIZE = 50 # Armazena os últimos 50 eventos
clan_event_log = collections.deque(maxlen=MAX_EVENT_LOG_SIZE)

def add_event_to_log(message: str):
    """Adiciona uma mensagem formatada com timestamp ao log de eventos do clã."""
    timestamp = datetime.datetime.now(TIMEZONE).strftime('%d/%m %H:%M')
    clan_event_log.appendleft(f"[{timestamp}] {message}") # Adiciona no início para ver os mais recentes primeiro

# Intents configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Funções Auxiliares (get_clan_data, get_player_data, etc. - como antes) ---
async def get_clan_data(tag: str) -> Clan:
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        if not tag.startswith("#"): tag = f"#{tag}"
        return await bot.coc_client.get_clan(tag)
    except coc.NotFound: raise ValueError(f"Clã com tag {tag} não encontrado.")
    except coc.Maintenance: raise ValueError("API do CoC está em manutenção.")
    except asyncio.TimeoutError: raise ValueError("Tempo esgotado buscando dados do clã.")
    except coc.InvalidCredentials: raise ValueError("Credenciais inválidas para API CoC.")
    except coc.Forbidden: raise ValueError("Acesso proibido à API CoC.")
    except Exception as e:
        logger.error(f"Erro inesperado buscando clã {tag}: {e}", exc_info=True)
        raise ValueError(f"Erro inesperado buscando clã: {str(e)}")

async def get_player_data(tag: str) -> Player:
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        if not tag.startswith("#"): tag = f"#{tag}"
        return await bot.coc_client.get_player(tag)
    except coc.NotFound: raise ValueError(f"Jogador com tag {tag} não encontrado.")
    except coc.Maintenance: raise ValueError("API do CoC está em manutenção.")
    except asyncio.TimeoutError: raise ValueError("Tempo esgotado buscando dados do jogador.")
    except coc.InvalidCredentials: raise ValueError("Credenciais inválidas para API CoC.")
    except coc.Forbidden: raise ValueError("Acesso proibido à API CoC.")
    except Exception as e:
        logger.error(f"Erro inesperado buscando jogador {tag}: {e}", exc_info=True)
        raise ValueError(f"Erro inesperado buscando jogador: {str(e)}")

clan_cache: Dict[str, Dict] = {}
CACHE_DURATION_SECONDS = 300

async def get_clan_data_with_cache(tag: str) -> Clan:
    if not tag.startswith("#"): tag = f"#{tag}"
    now = datetime.datetime.now()
    if tag in clan_cache and (now - clan_cache[tag]["timestamp"]).total_seconds() < CACHE_DURATION_SECONDS:
        return clan_cache[tag]["data"]
    clan_data_val = await get_clan_data(tag)
    clan_cache[tag] = {"data": clan_data_val, "timestamp": now}
    return clan_data_val

async def fetch_location_id(location_name: str) -> int:
    # ... (código como antes) ...
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
    # ... (código como antes) ...
    if not CHANNEL_ID or CHANNEL_ID == 0:
         logger.warning("CHANNEL_ID não configurado. Não é possível enviar embed de log.")
         return

    if not hasattr(embed_to_log, 'footer') or not hasattr(embed_to_log.footer, 'text') or not embed_to_log.footer.text:
         embed_to_log.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")

    if not embed_to_log.timestamp:
        embed_to_log.timestamp = datetime.datetime.now(TIMEZONE)

    try:
        channel_log = await bot.fetch_channel(CHANNEL_ID) # Renomeado
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
    # ... (código como antes, sem alterações necessárias aqui para as novas funcionalidades do painel)
    if not isinstance(channel, discord.TextChannel):
        logger.error("Canal inválido passado para send_embeds_splitted.")
        return

    if not items:
         embed_empty_split = discord.Embed.from_dict(base_embed.to_dict()) # Renomeado
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
    current_embed_split = discord.Embed.from_dict(base_embed.to_dict()) # Renomeado
    current_field_value_split = "" # Renomeado

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
                 logger.warning(f"Item individual muito longo para campo de embed: {item[:50]}...")
                 current_field_value_split = current_field_value_split[:1021] + "...\n"
        else:
            current_field_value_split += item_line

    if current_field_value_split:
        safe_field_name_split = field_name if field_name else "Dados" # Renomeado
        current_embed_split.add_field(name=safe_field_name_split, value=current_field_value_split, inline=False)
    if current_embed_split.fields:
         embeds_to_send.append(current_embed_split)

    for embed_item in embeds_to_send:
        if not hasattr(embed_item, 'footer') or not hasattr(embed_item.footer, 'text') or not embed_item.footer.text:
             embed_item.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
        if not embed_item.timestamp:
             embed_item.timestamp = datetime.datetime.now(TIMEZONE)

    for embed_to_send_msg in embeds_to_send: # Renomeado
        try:
            await channel.send(embed=embed_to_send_msg)
        except discord.Forbidden:
             logger.error(f"Sem permissão para enviar embed dividido para o canal {channel.id}")
             break
        except Exception as e:
            logger.error(f"Erro ao enviar embed dividido para o canal {channel.id}: {e}", exc_info=True)

# --- Funções de Guerra (format_attacks_remaining_embed, send_missed_attacks_report - como antes) ---
async def format_attacks_remaining_embed(war: ClanWar) -> Optional[List[discord.Embed]]:
    # ... (código como antes) ...
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

         end_time_local_fmt = end_time_aware.strftime('%d/%m/%Y %H:%M') # Renomeado
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
        # (Lógica de split de embed como antes)
        current_embed_attacks = discord.Embed.from_dict(base_embed_attacks.to_dict())
        current_field_value_attacks = ""
        for item in members_with_attacks:
            item_line = item + "\n"
            if len(current_field_value_attacks) + len(item_line) > 1024: # Limite de valor de campo
                if current_field_value_attacks: # Adiciona campo anterior se houver algo
                    current_embed_attacks.add_field(name=field_name_attacks, value=current_field_value_attacks, inline=False)
                if current_embed_attacks.fields: # Adiciona embed atual se tiver campos
                    embeds_to_send_attacks.append(current_embed_attacks)
                current_embed_attacks = discord.Embed.from_dict(base_embed_attacks.to_dict()) # Novo embed
                current_field_value_attacks = item_line # Começa novo valor de campo
                if len(current_field_value_attacks) > 1024: # Trunca se item individual for muito longo
                    logger.warning(f"Item individual muito longo para ataques restantes: {item_line[:50]}...")
                    current_field_value_attacks = current_field_value_attacks[:1021] + "...\n"
            else:
                current_field_value_attacks += item_line

        if current_field_value_attacks: # Adiciona o último campo
            current_embed_attacks.add_field(name=field_name_attacks, value=current_field_value_attacks, inline=False)
        if current_embed_attacks.fields: # Adiciona o último embed se tiver campos
            embeds_to_send_attacks.append(current_embed_attacks)


    for embed_item_rem in embeds_to_send_attacks: # Renomeado
        if not hasattr(embed_item_rem, 'footer') or not hasattr(embed_item_rem.footer, 'text') or not embed_item_rem.footer.text:
             embed_item_rem.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        if not embed_item_rem.timestamp:
             embed_item_rem.timestamp = datetime.datetime.now(TIMEZONE)

    return embeds_to_send_attacks if embeds_to_send_attacks else None


async def send_missed_attacks_report(war: ClanWar,
                                    missed_members_details: List[str],
                                    war_type: str) -> None:
    # ... (código como antes) ...
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

    opponent_name_val = getattr(getattr(war, 'opponent', None), 'name', 'Oponente Desconhecido') # Renomeado

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
        f"Membros que não usaram todos os ataques contra **{opponent_name_val}**.\n\n"
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
    # ... (código como antes) ...
    if not CHANNEL_ID or CHANNEL_ID == 0:
        logger.warning("CHANNEL_ID não configurado. Não é possível enviar status online.")
        return

    try:
        clan_name = "Clã Desconhecido"
        clan_tag_formatted = CLAN_TAG if CLAN_TAG else "Nenhum"
        if CLAN_TAG and hasattr(bot, 'coc_client') and bot.coc_client.http: # Verifica se cliente coc está pronto
             try:
                  clan_data_status = await bot.coc_client.get_clan(CLAN_TAG)
                  clan_name = clan_data_status.name
                  clan_tag_formatted = clan_data_status.tag
             except Exception as e:
                  logger.error(f"Erro ao buscar dados do clã para status online: {e}")

        embed_online = discord.Embed(
            title="✅ Bot Online e Monitorando!",
            description=f"Eventos do clã **{clan_name}** (`{clan_tag_formatted}`) e Guerras monitorados. Painel Web Ativo.", # Adicionado menção ao Painel
            color=discord.Color.green()
        )
        embed_online.add_field(name="Monitoramento", value="Event-Driven Ativo 🔄", inline=False)
        embed_online.add_field(name="Painel Web", value=f"Acessível em /painel", inline=False) # Adicionado link do painel
        await send_log_embed(embed_online)
        logger.info("Mensagem de status online enviada.")
        add_event_to_log(f"🤖 Bot reiniciado e online. Versão: {BOT_VERSION}")


    except Exception as e:
        logger.error(f"Erro ao enviar mensagem de status online: {e}", exc_info=True)


# --- Bot Events (on_ready, on_app_command_error) ---
@bot.event
async def on_ready():
    # ... (código como antes, mas a chamada para send_online_status já adicionará ao log de eventos)
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

    await send_online_status() # Isso já vai adicionar o evento "Bot online" ao log


@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    # ... (código como antes) ...
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


# --- CoC Event Handlers (Modificados para adicionar ao log de eventos) ---
async def register_coc_events(coc_client: coc.EventsClient):
    if not CLAN_TAG:
         logger.warning("CLAN_TAG não definido, eventos do clã não serão registrados.")
         return
    logger.info(f"Registrando manipuladores de eventos CoC para o clã {CLAN_TAG}...")

    @coc_client.event
    @coc.ClanEvents.member_join(tags=[CLAN_TAG])
    async def on_member_join_event(old_member: Optional[ClanMember], member: ClanMember): # Nomeado para evitar conflito
        # ... (lógica do embed como antes) ...
        if not member or not hasattr(member, 'clan'): return
        clan_obj_join = member.clan
        embed_join = discord.Embed( title="👋 Novo Membro", description=f"**{member.name}** (`{member.tag}`) entrou no clã!", color=discord.Color.green())
        # ... (add_fields como antes) ...
        embed_join.add_field(name="CV", value=getattr(member, 'town_hall', '?'), inline=True)
        embed_join.add_field(name="Nível", value=getattr(member, 'exp_level', '?'), inline=True)
        embed_join.add_field(name="Troféus", value=getattr(member, 'trophies', '?'), inline=True)
        if hasattr(member, 'league') and member.league:
            embed_join.add_field(name="Liga", value=member.league.name, inline=True)
        if hasattr(clan_obj_join, 'badge') and clan_obj_join.badge:
             embed_join.set_author(name=clan_obj_join.name, icon_url=clan_obj_join.badge.url)
             embed_join.set_thumbnail(url=clan_obj_join.badge.url)
        await send_log_embed(embed_join)
        add_event_to_log(f"👋 {member.name} (CV{member.town_hall}) entrou no clã.")

    @coc_client.event
    @coc.ClanEvents.member_leave(tags=[CLAN_TAG])
    async def on_member_leave_event(old_member: ClanMember, member: ClanMember): # Nomeado para evitar conflito
        # ... (lógica do embed como antes) ...
        if not old_member: return
        clan_obj_leave = old_member.clan if hasattr(old_member, 'clan') else None
        clan_name_leave = getattr(clan_obj_leave, 'name', 'Clã Desconhecido')
        leaving_member_name = getattr(old_member, 'name', 'Membro Desconhecido')
        embed_leave = discord.Embed(title="👋 Membro Saiu", description=f"**{leaving_member_name}** (`{old_member.tag}`) saiu do clã!", color=discord.Color.red())
        # ... (add_fields como antes) ...
        if clan_obj_leave and hasattr(clan_obj_leave, 'badge') and clan_obj_leave.badge:
             embed_leave.set_author(name=clan_name_leave, icon_url=clan_obj_leave.badge.url)
             embed_leave.set_thumbnail(url=clan_obj_leave.badge.url)

        await send_log_embed(embed_leave)
        add_event_to_log(f"🚪 {leaving_member_name} (CV{old_member.town_hall}) saiu do clã.")

    @coc_client.event
    @coc.ClanEvents.member_donations(tags=[CLAN_TAG])
    async def on_member_donations_event(old_member: ClanMember, member: ClanMember): # Nomeado
        if not member or not old_member or not hasattr(member, 'clan'): return
        donation_difference = member.donations - old_member.donations
        if donation_difference <= 0: return
        # ... (lógica do embed como antes) ...
        add_event_to_log(f"🎁 {member.name} doou {donation_difference} tropas.")
        # O embed de doação já é enviado por send_log_embed

    @coc_client.event
    @coc.ClanEvents.member_received(tags=[CLAN_TAG])
    async def on_member_received_event(old_member: ClanMember, member: ClanMember): # Nomeado
        if not member or not old_member or not hasattr(member, 'clan'): return
        received_difference = member.received - old_member.received
        if received_difference <= 0: return
        # ... (lógica do embed como antes) ...
        add_event_to_log(f"📥 {member.name} recebeu {received_difference} tropas.")

    @coc_client.event
    @coc.ClanEvents.member_role_change(tags=[CLAN_TAG])
    async def on_member_role_change_event(old_member: ClanMember, member: ClanMember): # Nomeado
        if not member or not old_member or not hasattr(member, 'clan') or old_member.role == member.role: return
        # ... (lógica do embed como antes) ...
        add_event_to_log(f"🔄 Cargo de {member.name} mudou de {old_member.role} para {member.role}.")

    @coc_client.event
    @coc.ClanEvents.member_league_change(tags=[CLAN_TAG])
    async def on_member_league_change_event(old_member: ClanMember, member: ClanMember): # Nomeado
        if not member or not old_member or not hasattr(member, 'clan') or old_member.league == member.league: return
        # ... (lógica do embed como antes) ...
        old_league_name = old_member.league.name if old_member.league else "Sem Liga"
        new_league_name = member.league.name if member.league else "Sem Liga"
        add_event_to_log(f"🏆 Liga de {member.name} mudou de {old_league_name} para {new_league_name}.")

    @coc_client.event
    @coc.ClanEvents.member_trophies_change(tags=[CLAN_TAG])
    async def on_member_trophies_change_event(old_member: ClanMember, member: ClanMember): # Nomeado
        if not member or not old_member: return
        trophy_difference = member.trophies - old_member.trophies
        if abs(trophy_difference) < 5 : return # Ignora pequenas flutuações
        # ... (lógica do embed como antes) ...
        direction = "ganhou" if trophy_difference > 0 else "perdeu"
        add_event_to_log(f"🏆 {member.name} {direction} {abs(trophy_difference)} troféus (Total: {member.trophies}).")

    @coc_client.event
    @coc.WarEvents.war_attack(tags=[CLAN_TAG])
    async def on_war_attack_event(attack: WarAttack, war: ClanWar): # Nomeado
        # ... (lógica do embed como antes) ...
        # Determinar se é nosso ataque ou defesa
        # Adicionar ao log:
        # add_event_to_log(f"⚔️ {attacker_name} atacou {defender_name} ({attack.stars}⭐, {attack.destruction}%)")
        # ou
        # add_event_to_log(f"🛡️ {defender_name} foi atacado por {attacker_name} ({attack.stars}⭐, {attack.destruction}%)")
        if not all(hasattr(attack, attr) for attr in ['attacker_tag', 'defender_tag', 'stars', 'destruction', 'order']):
            logger.warning(f"Evento de ataque de guerra recebido com dados incompletos. War Tag: {getattr(war, 'tag', 'N/A')}")
            return

        is_our_attack = False
        is_our_defense = False
        attacker_clan_tag = None
        defender_clan_tag = None
        attacker_player = None
        defender_player = None

        try:
             attacker_player = await get_player_data(attack.attacker_tag)
             defender_player = await get_player_data(attack.defender_tag)
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
        else: # Ataque não envolve nosso clã (raro se filtrado por tag, mas seguro)
             return

        attacker_name = getattr(attacker_player, 'name', attack.attacker_tag) if attacker_player else attack.attacker_tag
        defender_name = getattr(defender_player, 'name', attack.defender_tag) if defender_player else attack.defender_tag
        attacker_th = getattr(attacker_player, 'town_hall', '?') if attacker_player else '?'
        defender_th = getattr(defender_player, 'town_hall', '?') if defender_player else '?'
        stars_str = "⭐" * attack.stars + "⚫" * (3 - attack.stars)
        content_attack = None

        if is_our_attack:
            # ... (lógica de embed e alerta de 1 estrela como antes) ...
            embed_attack = discord.Embed( title=f"⚔️ Ataque Realizado (Guerra)", description=f"**{attacker_name}** (CV{attacker_th}) atacou **{defender_name}** (CV{defender_th})", color=discord.Color.blue())
            embed_attack.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
            if hasattr(war, 'clan') and hasattr(war.clan, 'badge') and war.clan.badge:
                 embed_attack.set_author(name=war.clan.name, icon_url=war.clan.badge.url)
                 embed_attack.set_thumbnail(url=war.clan.badge.url)
            await send_log_embed(embed_attack, content_attack)
            add_event_to_log(f"⚔️ {attacker_name} atacou {defender_name} ({attack.stars}⭐, {attack.destruction}%)")
        elif is_our_defense:
            # ... (lógica de embed como antes) ...
            embed_defense = discord.Embed( title=f"🛡️ Defesa Recebida (Guerra)", description=f"**{defender_name}** (CV{defender_th}) foi atacado por **{attacker_name}** (CV{attacker_th})", color=discord.Color.orange())
            embed_defense.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
            if hasattr(war, 'opponent') and hasattr(war.opponent, 'badge') and war.opponent.badge:
                 embed_defense.set_author(name=war.opponent.name, icon_url=war.opponent.badge.url)
                 embed_defense.set_thumbnail(url=war.opponent.badge.url)
            await send_log_embed(embed_defense)
            add_event_to_log(f"🛡️ {defender_name} foi atacado por {attacker_name} ({attack.stars}⭐, {attack.destruction}%)")


    logger.info("Manipuladores de eventos CoC registrados.")

# --- Tasks (check_war_end_report_task - como antes) ---
@tasks.loop(minutes=10)
async def check_war_end_report_task():
    # ... (código como antes, mas pode adicionar ao log de eventos ao encontrar guerra finalizada) ...
    if not bot.coc_client or not bot.coc_client.http:
         logger.debug("check_war_end_report_task: Cliente CoC não pronto, pulando ciclo.")
         return

    logger.debug("check_war_end_report_task: Iniciando verificação de fim de guerra...")
    processed_war_ids: Set[str] = set()

    async def process_war(war_obj: ClanWar, war_type_name: str):
        war_id = war_obj.end_time.raw_time if hasattr(war_obj, 'end_time') and hasattr(war_obj.end_time, 'raw_time') else None

        if not war_obj or not war_id or war_id in processed_war_ids:
            return

        opponent_name_proc = getattr(getattr(war_obj, 'opponent', None), 'name', 'Oponente Desconhecido')
        war_state_proc = getattr(war_obj, 'state', 'unknown')

        if war_state_proc == "warEnded" and war_id not in reported_war_ends:
            add_event_to_log(f"🏁 Guerra '{war_type_name}' vs {opponent_name_proc} finalizada. Verificando ataques...")
            # ... (resto da lógica de process_war como antes)
            logger.info(f"Guerra '{war_type_name}' contra {opponent_name_proc} terminou (ID: {war_id}). Verificando ataques perdidos...")

            our_clan_obj = None
            attacks_per_member = 2

            if "Liga de Clãs" in war_type_name:
                 attacks_per_member = 1
                 war_clan_tag = getattr(getattr(war_obj, 'clan', None), 'tag', None)
                 war_opponent_tag = getattr(getattr(war_obj, 'opponent', None), 'tag', None)
                 if war_clan_tag == CLAN_TAG:
                     our_clan_obj = war_obj.clan
                 elif war_opponent_tag == CLAN_TAG: # Nosso clã é o oponente na estrutura de dados da API
                     our_clan_obj = war_obj.opponent
                 else:
                      logger.error(f"Guerra da liga {war_id} não contém o clã {CLAN_TAG}? ClanTag: {war_clan_tag}, OppTag: {war_opponent_tag}")
                      return
            else:
                 our_clan_obj = getattr(war_obj, 'clan', None)
                 attacks_per_member = getattr(war_obj, 'attacks_per_member', 2)

            if not our_clan_obj:
                 logger.error(f"Não foi possível identificar nosso clã na guerra {war_id}.")
                 return

            missed_members_details_task = []
            if hasattr(our_clan_obj, 'members') and our_clan_obj.members:
                 for member_proc in our_clan_obj.members:
                    if not member_proc or not hasattr(member_proc, 'tag'): continue
                    attacks_used_task = len(member_proc.attacks) if hasattr(member_proc, "attacks") and member_proc.attacks else 0
                    if attacks_used_task < attacks_per_member:
                        missed_count_task = attacks_per_member - attacks_used_task
                        member_name_proc = getattr(member_proc, 'name', member_proc.tag)
                        member_th_proc = getattr(member_proc, 'town_hall', '?')
                        missed_members_details_task.append(
                            f"**{member_name_proc}** (CV{member_th_proc}): {missed_count_task} perdido{'s' if missed_count_task > 1 else ''}"
                        )
            else:
                 logger.warning(f"Objeto do clã '{getattr(our_clan_obj, 'name', 'N/A')}' na guerra {war_id} não possui lista de membros.")


            if missed_members_details_task:
                logger.info(f"{len(missed_members_details_task)} membro(s) perderam ataques na guerra {war_type_name} (ID: {war_id}).")
                await send_missed_attacks_report(war_obj, missed_members_details_task, war_type_name)
                add_event_to_log(f"❌ {len(missed_members_details_task)} membro(s) não realizaram todos os ataques na guerra vs {opponent_name_proc}.")
            else:
                logger.info(f"Nenhum ataque perdido na guerra {war_type_name} (ID: {war_id}).")
                add_event_to_log(f"✅ Todos os ataques realizados na guerra vs {opponent_name_proc}!")


            reported_war_ends.add(war_id)
            processed_war_ids.add(war_id)
            logger.debug(f"Guerra {war_id} marcada como reportada.")
    # ... (resto da task check_war_end_report_task como antes) ...
    try:
        logger.debug("Buscando guerra atual (regular)...")
        current_war_reg = await bot.coc_client.get_current_war(CLAN_TAG)
        if current_war_reg and hasattr(current_war_reg, 'state') and current_war_reg.state != "notInWar":
             if hasattr(current_war_reg, 'end_time'): # Garante que é um objeto de guerra válido
                  await process_war(current_war_reg, "Guerra Normal")
             else:
                  logger.warning("Objeto de guerra regular inválido (sem end_time).")
        # ... (restante da lógica como antes)
    except coc.PrivateWarLog: # etc.
        logger.warning("Log de guerra regular é privado. Não é possível verificar automaticamente.")
    except coc.NotFound:
         logger.info("Clã não encontrado ao buscar guerra regular (possivelmente tag inválida?).")
    except Exception as e:
        logger.error(f"Erro ao buscar/processar guerra regular: {e}", exc_info=True)

    try:
        logger.debug("Buscando grupo de liga (CWL)...")
        league_group_cwl = await bot.coc_client.get_league_group(CLAN_TAG)

        if league_group_cwl and hasattr(league_group_cwl, 'state') and league_group_cwl.state != "notInWar":
            # ... (lógica de processamento da CWL como antes) ...
            if hasattr(league_group_cwl, 'rounds') and league_group_cwl.rounds:
                 for round_num_cwl, war_tags_cwl in reversed(list(enumerate(league_group_cwl.rounds))): # Processa da mais recente para a mais antiga
                     logger.debug(f"Processando rodada {round_num_cwl + 1} da CWL...")
                     for war_tag_cwl in war_tags_cwl:
                         try:
                             league_war_cwl = await league_group_cwl.get_league_war(war_tag_cwl)

                             if not league_war_cwl or not hasattr(league_war_cwl, 'state') or not hasattr(league_war_cwl, 'end_time'):
                                  logger.warning(f"Objeto da guerra da liga {war_tag_cwl} inválido ou incompleto.")
                                  continue

                             # Verifica se o clã monitorado está participando desta guerra específica da liga
                             clan_tag_in_cwl = getattr(getattr(league_war_cwl, 'clan', None), 'tag', None)
                             opponent_tag_in_cwl = getattr(getattr(league_war_cwl, 'opponent', None), 'tag', None)

                             if CLAN_TAG == clan_tag_in_cwl or CLAN_TAG == opponent_tag_in_cwl:
                                 await process_war(league_war_cwl, f"Liga de Clãs (Rodada {round_num_cwl + 1})")
                         # ... (resto do try/except como antes) ...
                         except coc.NotFound:
                              logger.warning(f"Guerra da liga com tag {war_tag_cwl} (Rodada {round_num_cwl + 1}) não encontrada.")
                         except Exception as e:
                              logger.error(f"Erro ao buscar/processar guerra da liga {war_tag_cwl} (Rodada {round_num_cwl + 1}): {e}", exc_info=True)

    # ... (restante da task como antes) ...
    except coc.NotFound:
         logger.info("Clã não encontrado ao buscar grupo de liga (possivelmente não em CWL ou tag inválida).")
    except Exception as e:
        logger.error(f"Erro ao buscar/processar grupo de liga (CWL): {e}", exc_info=True)

    logger.debug("check_war_end_report_task: Verificação de fim de guerra concluída.")


@check_war_end_report_task.before_loop
async def before_check_war():
    # ... (código como antes) ...
    logger.info("Aguardando o bot ficar pronto para iniciar a tarefa 'check_war_end_report_task'...")
    await bot.wait_until_ready()
    logger.info("Bot pronto. Tarefa 'check_war_end_report_task' pode iniciar.")


# --- Slash Commands (sem grandes alterações aqui, a menos que queira adicionar novos) ---
# ... (grupos de comandos e comandos como antes) ...
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

# ... (todos os seus comandos slash como /admin ping, /guerra ataques, etc. permanecem aqui como antes) ...
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

# (Todos os outros comandos /guerra, /info, /buscar, /rank como no seu código original)
# ...
# Cole aqui todos os seus comandos slash que já estavam funcionando.
# Para economizar espaço na resposta, não vou repetir todos eles,
# mas eles devem estar aqui no seu arquivo.
# ...


# ============================================================================ #
# ==================== PAINEL WEB - LÓGICA E ENDPOINTS API ==================== #
# ============================================================================ #

web_api_cache: Dict[str, Dict] = {}
WEB_API_CACHE_DURATION_SECONDS = 30 # Cache mais curto para dados mais dinâmicos

async def get_cached_web_data(key: str, func_to_fetch_data, *args, **kwargs):
    now = datetime.datetime.now()
    if key in web_api_cache:
        cache_entry = web_api_cache[key]
        cache_age = (now - cache_entry["timestamp"]).total_seconds()
        if cache_age < WEB_API_CACHE_DURATION_SECONDS:
            logger.debug(f"Usando cache API web (chave: {key}, idade: {cache_age:.1f}s)")
            return cache_entry["data"]
    logger.debug(f"Buscando novos dados API web (chave: {key})")
    data = await func_to_fetch_data(*args, **kwargs)
    web_api_cache[key] = {"data": data, "timestamp": now}
    return data

# --- Funções de Fetch para a API do Painel ---
async def fetch_clan_info_for_web_api():
    # ... (como na resposta anterior, incluindo BOT_VERSION) ...
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        return {
            "name": clan.name, "tag": clan.tag, "level": clan.level,
            "points": clan.points, "capital_points": getattr(clan, 'capital_points', 0),
            "member_count": clan.member_count, "description": clan.description,
            "war_wins": getattr(clan, 'war_wins', 'N/A'),
            "location": clan.location.name if hasattr(clan, 'location') and clan.location else "N/A",
            "type": clan.type.capitalize() if hasattr(clan, 'type') else "N/A",
            "badge_url": clan.badge.url if hasattr(clan, 'badge') and clan.badge else None,
            "version": BOT_VERSION
        }
    except Exception as e: return {"error": str(e), "name": "Erro"}


async def fetch_clan_members_for_web_api():
    # ... (como na resposta anterior) ...
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
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
                    "league_icon_url": member.league.icon.url if hasattr(member, 'league') and member.league and hasattr(member.league.icon, 'url') else None
                })
        members_data.sort(key=lambda m: m.get("trophies", 0), reverse=True)
        return {"members": members_data, "clan_name": clan.name, "clan_tag": clan.tag}
    except Exception as e: return {"error": str(e)}


async def fetch_war_status_for_web_api():
    # (Lógica aprimorada para incluir última guerra se não houver ativa)
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    current_war: Optional[Union[ClanWar, WarLogEntry]] = None
    war_type_description = "Nenhuma guerra"
    is_from_log = False

    # 1. Tenta CWL ativa
    try:
        lg = await bot.coc_client.get_league_group(CLAN_TAG)
        if lg and lg.state != "notInWar" and lg.rounds:
            for i, war_tags in reversed(list(enumerate(lg.rounds))): # Da mais recente
                for tag in war_tags:
                    try:
                        war = await lg.get_league_war(tag)
                        # Garante que nosso clã está na guerra
                        if war and (war.clan.tag == CLAN_TAG or war.opponent.tag == CLAN_TAG):
                            if war.state == "inWar" or war.state == "preparation":
                                if war.opponent.tag == CLAN_TAG: war.clan, war.opponent = war.opponent, war.clan # Swap
                                current_war = war
                                war_type_description = f"Liga (Rodada {i+1})"
                                break
                    except: continue
                if current_war: break
    except coc.NotFound: pass
    except Exception as e: logger.error(f"Erro CWL API Web: {e}")

    # 2. Tenta Guerra Regular ativa se não achou CWL
    if not current_war:
        try:
            war = await bot.coc_client.get_current_war(CLAN_TAG)
            if war and (war.state == "inWar" or war.state == "preparation"):
                current_war = war
                war_type_description = "Guerra Normal"
        except coc.PrivateWarLog: return {"status": "PrivateWarLog", "message": "Log de guerra privado."}
        except coc.NotFound: pass
        except Exception as e: logger.error(f"Erro Guerra Regular API Web: {e}")

    # 3. Se ainda sem guerra ativa, tenta a última guerra do log (se público)
    if not current_war:
        try:
            war_log = await bot.coc_client.get_war_log(CLAN_TAG, limit=1)
            if war_log:
                current_war = war_log[0] # WarLogEntry
                war_type_description = "Última Guerra (Log)"
                is_from_log = True
        except coc.PrivateWarLog: return {"status": "PrivateWarLog", "message": "Log de guerra privado."}
        except Exception as e: logger.error(f"Erro WarLog API Web: {e}")

    if not current_war: return {"status": "NotInWar", "message": "Nenhuma guerra ativa ou no log recente."}

    # Formatar dados para o frontend
    now_tz = datetime.datetime.now(TIMEZONE)
    state_desc = current_war.state.capitalize() if hasattr(current_war, 'state') else "Finalizada (Log)"
    time_key, time_val, time_rem = "N/A", "N/A", "-"

    if isinstance(current_war, ClanWar): # Guerra ativa/preparação
        if current_war.state == "preparation" and current_war.start_time:
            start_aware = pytz.utc.localize(current_war.start_time.time).astimezone(TIMEZONE)
            time_key, time_val = "Início", start_aware.strftime('%d/%m %H:%M')
            delta = start_aware - now_tz
            if delta.total_seconds() > 0: time_rem = f"{int(delta.total_seconds() // 3600)}h {int((delta.total_seconds() % 3600) // 60)}m"
            else: time_rem = "Iniciando..."
        elif current_war.state == "inWar" and current_war.end_time:
            end_aware = pytz.utc.localize(current_war.end_time.time).astimezone(TIMEZONE)
            time_key, time_val = "Fim", end_aware.strftime('%d/%m %H:%M')
            delta = end_aware - now_tz
            if delta.total_seconds() > 0: time_rem = f"{int(delta.total_seconds() // 3600)}h {int((delta.total_seconds() % 3600) // 60)}m"
            else: time_rem = "Finalizando..."
        elif current_war.state == "warEnded" and current_war.end_time:
            time_key = "Finalizada"
            time_val = pytz.utc.localize(current_war.end_time.time).astimezone(TIMEZONE).strftime('%d/%m %H:%M')
    elif isinstance(current_war, WarLogEntry): # Guerra do Log
        time_key = "Finalizada (Log)"
        if current_war.end_time:
             time_val = pytz.utc.localize(current_war.end_time.time).astimezone(TIMEZONE).strftime('%d/%m %H:%M')
        state_desc = current_war.result.capitalize() if current_war.result else "Finalizada"


    # Dados do clã e oponente
    our_clan_data = current_war.clan if isinstance(current_war, ClanWar) else \
                    (current_war.clan if current_war.clan.tag == CLAN_TAG else current_war.opponent)
    opponent_data = current_war.opponent if isinstance(current_war, ClanWar) else \
                    (current_war.opponent if current_war.clan.tag == CLAN_TAG else current_war.clan)


    return {
        "status": current_war.state if hasattr(current_war, 'state') else "warEnded", # Normaliza para o JS
        "type": war_type_description, "state_description": state_desc,
        "clan_name": our_clan_data.name,
        "clan_stars": our_clan_data.stars,
        "clan_destruction": f"{our_clan_data.destruction:.2f}%",
        "clan_badge_url": our_clan_data.badge.url if hasattr(our_clan_data, 'badge') else None,
        "opponent_name": opponent_data.name, "opponent_tag": opponent_data.tag,
        "opponent_stars": opponent_data.stars,
        "opponent_destruction": f"{opponent_data.destruction:.2f}%",
        "opponent_badge_url": opponent_data.badge.url if hasattr(opponent_data, 'badge') else None,
        "time_key": time_key, "time_value": time_val, "time_remaining": time_rem,
        "attacks_per_member": getattr(current_war, 'attacks_per_member', 1 if "Liga" in war_type_description else 2),
        "team_size": getattr(current_war, 'team_size', 'N/A')
    }


async def fetch_player_details_for_web_api(player_tag: str):
    if not player_tag: return {"error": "Tag do jogador não fornecida."}
    try:
        player = await get_player_data(player_tag) # Reutiliza get_player_data com seu tratamento de erro
        
        heroes_data = [{"name": h.name, "level": h.level, "max_level": h.max_level, "village": h.village}
                       for h in player.heroes if h.is_home_base or h.is_builder_base] # Inclui ambos
        
        troops_data = [{"name": t.name, "level": t.level, "max_level": t.max_level_for_townhall(player.town_hall), "village": t.village} # Max para o CV atual
                       for t in player.troops if t.is_home_base or t.is_builder_base] # Adicionar .is_elixir_troop, .is_dark_troop etc. para filtrar se quiser
        
        spells_data = [{"name": s.name, "level": s.level, "max_level": s.max_level_for_townhall(player.town_hall), "village": s.village}
                       for s in player.spells]

        return {
            "name": player.name, "tag": player.tag, "town_hall": player.town_hall,
            "exp_level": player.exp_level,
            "trophies": player.trophies, "best_trophies": player.best_trophies,
            "league": player.league.name if player.league else "N/A",
            "league_icon_url": player.league.icon.url if player.league and hasattr(player.league.icon, 'url') else None,
            "clan_name": player.clan.name if player.clan else "Sem Clã",
            "clan_tag": player.clan.tag if player.clan else "N/A",
            "role": player.role.name.capitalize() if player.role else "Membro",
            "donations": player.donations, "received": player.received,
            "war_stars": player.war_stars, "attack_wins": player.attack_wins,
            "heroes": heroes_data, "troops": troops_data, "spells": spells_data,
            "builder_hall_level": getattr(player, 'builder_hall_level', None),
            "builder_base_trophies": getattr(player, 'builder_base_trophies', None),
            "best_builder_base_trophies": getattr(player, 'best_builder_base_trophies', None),
            "achievements": [{"name": a.name, "stars": a.stars, "value": a.value, "target": a.target, "info": a.info}
                             for a in player.achievements if a.value > 0 and a.name in ["Friend in Need", "War Hero", "Clan War Leagues", "Games Champion"]], # Exemplo de algumas conquistas
        }
    except Exception as e: return {"error": str(e)}


async def fetch_clan_events_log_for_web_api():
    return {"events": list(clan_event_log)} # Converte deque para lista para JSON


async def fetch_cwl_info_for_web_api():
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        group: LeagueGroup = await bot.coc_client.get_league_group(CLAN_TAG)
        if not group or group.state == "notInWar":
            return {"status": "notInWar", "message": "O clã não está em CWL ou os dados não estão disponíveis."}

        rounds_data = []
        for i, round_war_tags in enumerate(group.rounds):
            round_info = {"round_number": i + 1, "wars": []}
            for war_tag in round_war_tags:
                try:
                    war: LeagueWar = await group.get_league_war(war_tag)
                    if not war: continue
                    
                    # Garante que nosso clã é 'clan' e o outro é 'opponent'
                    our_clan_is_clan1 = war.clan.tag == CLAN_TAG
                    
                    clan1_data = war.clan
                    clan2_data = war.opponent

                    if not our_clan_is_clan1 and war.opponent.tag == CLAN_TAG: # Nosso clã é o opponent na API
                        clan1_data, clan2_data = war.opponent, war.clan # Swap

                    war_details = {
                        "war_tag": war_tag, "state": war.state,
                        "clan1_name": clan1_data.name, "clan1_tag": clan1_data.tag,
                        "clan1_stars": clan1_data.stars, "clan1_destruction": f"{clan1_data.destruction:.2f}%",
                        "clan1_badge_url": clan1_data.badge.url if hasattr(clan1_data.badge, 'url') else None,
                        "clan2_name": clan2_data.name, "clan2_tag": clan2_data.tag,
                        "clan2_stars": clan2_data.stars, "clan2_destruction": f"{clan2_data.destruction:.2f}%",
                        "clan2_badge_url": clan2_data.badge.url if hasattr(clan2_data.badge, 'url') else None,
                        "end_time_str": pytz.utc.localize(war.end_time.time).astimezone(TIMEZONE).strftime('%d/%m %H:%M') if war.end_time else "N/A"
                    }
                    round_info["wars"].append(war_details)
                except Exception as e_war:
                    logger.warning(f"Erro ao buscar guerra da CWL {war_tag} para API: {e_war}")
                    round_info["wars"].append({"war_tag": war_tag, "error": "Erro ao carregar dados desta guerra."})
            rounds_data.append(round_info)
        
        return {
            "status": group.state, "season": group.season,
            "rounds": rounds_data,
            "clans": [{"name": c.name, "tag": c.tag, "level": c.level, "badge_url": c.badge.url} for c in group.clans]
        }
    except coc.NotFound: return {"status": "notInWar", "message": "Clã não encontrado em grupo de CWL."}
    except Exception as e: return {"error": str(e)}


# --- Handlers de Rota da API do Painel ---
async def api_clan_info_handler(request):
    data = await get_cached_web_data(f"web_clan_info_{CLAN_TAG}", fetch_clan_info_for_web_api)
    return web.json_response(data)

async def api_members_handler(request):
    data = await get_cached_web_data(f"web_clan_members_{CLAN_TAG}", fetch_clan_members_for_web_api)
    return web.json_response(data)

async def api_war_status_handler(request):
    # Guerra é muito dinâmica, cache bem curto ou sem cache
    data = await get_cached_web_data(f"web_war_status_{CLAN_TAG}", fetch_war_status_for_web_api, _cache_duration=15) # Exemplo de cache específico
    return web.json_response(data)

async def api_player_details_handler(request):
    player_tag = request.match_info.get('player_tag', None)
    if not player_tag:
        return web.json_response({"error": "Tag do jogador não especificada na URL."}, status=400)
    # Adiciona # se não tiver, e decodifica URL (caso tags com # sejam passadas)
    player_tag_cleaned = f"#{player_tag.lstrip('#')}"
    
    # Cache por jogador pode ser um pouco mais longo
    data = await get_cached_web_data(f"web_player_{player_tag_cleaned}", fetch_player_details_for_web_api, player_tag=player_tag_cleaned, _cache_duration=120)
    return web.json_response(data)

async def api_clan_events_log_handler(request):
    data = await fetch_clan_events_log_for_web_api() # Log é atualizado em tempo real, sem cache de API aqui
    return web.json_response(data)

async def api_cwl_info_handler(request):
    data = await get_cached_web_data(f"web_cwl_info_{CLAN_TAG}", fetch_cwl_info_for_web_api, _cache_duration=300) # CWL não muda tão rápido
    return web.json_response(data)


async def handle_panel_index(request):
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "painel.html")
    try: return web.FileResponse(index_path)
    except Exception: return web.Response(text="Painel não encontrado.", status=404)


async def setup_web_server():
    app = web.Application()
    async def health_handler(request):
        return web.Response(text=f"Bot is running! Web panel active. Version: {BOT_VERSION}")

    # Rotas da API
    app.router.add_get("/api/clan", api_clan_info_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/war", api_war_status_handler)
    app.router.add_get("/api/player/{player_tag}", api_player_details_handler) # Rota com parâmetro
    app.router.add_get("/api/events", api_clan_events_log_handler)
    app.router.add_get("/api/cwl", api_cwl_info_handler)

    app.router.add_get("/painel", handle_panel_index) # Página principal do painel
    
    static_files_path = os.path.join(os.path.dirname(__file__), "static")
    # (Lógica de criar pasta static e arquivos básicos como antes, se quiser)

    app.router.add_static('/static/', path=static_files_path, name='static', show_index=False)
    app.router.add_get("/", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    try:
         await site.start()
         logger.info(f"Servidor web (painel e API) iniciado em 0.0.0.0:{port}")
         return runner
    except Exception as e:
         logger.error(f"Falha ao iniciar servidor web: {e}", exc_info=True)
         return None

# --- setup_hook e main (como antes, mas setup_hook chama o setup_web_server atualizado) ---
async def setup_hook():
    # ... (login CoC como antes) ...
    logger.info("Executando setup_hook...")

    logger.info("Inicializando cliente CoC...")
    bot.coc_client = coc.EventsClient()
    # ... (lógica de login do CoC como no seu arquivo original) ...
    # (Certifique-se que a lógica de login está aqui)
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
        # ... (outros excepts como no seu original)
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
         logger.error("Não foi possível logar no CoC.")
    else:
         logger.info("Registrando listeners de eventos CoC...")
         await register_coc_events(bot.coc_client) # register_coc_events modificado acima
         if CLAN_TAG:
             try:
                  bot.coc_client.add_clan_updates(CLAN_TAG)
                  bot.coc_client.add_war_updates(CLAN_TAG)
                  logger.info(f"Atualizações de clã e guerra ativadas para {CLAN_TAG}.")
             except Exception as e:
                  logger.error(f"Erro ao adicionar atualizações de eventos para {CLAN_TAG}: {e}")
         else:
              logger.warning("CLAN_TAG não definido. Atualizações CoC não ativadas.")


    logger.info("Configurando servidor web...")
    bot.web_runner = await setup_web_server() # Chama o setup_web_server atualizado
    # ... (sincronização de comandos como antes) ...
    if bot.web_runner:
        logger.info("Servidor web configurado.")
    else:
        logger.warning("Falha ao configurar o servidor web.")

    logger.info("Tentando sincronizar comandos de aplicativo (/) no setup_hook...")
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
        logger.error(f"Erro 403 Forbidden ao sincronizar comandos (/): {e}.")
    except discord.HTTPException as e:
        logger.error(f"Erro HTTP ao sincronizar comandos (/): {e.status} - {e.text}", exc_info=True)
    except Exception as e:
        logger.error(f"Erro inesperado ao sincronizar comandos (/) no setup_hook: {e}", exc_info=True)


    logger.info("setup_hook concluído.")


async def main():
    # ... (código como antes) ...
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
        finally: # (Lógica de cleanup como antes)
            logger.info("Iniciando processo de desligamento do bot...")
            if 'check_war_end_report_task' in globals() and check_war_end_report_task.is_running():
                 logger.info("Parando tarefa 'check_war_end_report_task'...")
                 check_war_end_report_task.cancel()
                 try: await asyncio.sleep(1); logger.info("Tarefa 'check_war_end_report_task' cancelada.")
                 except asyncio.CancelledError: logger.info("Tarefa 'check_war_end_report_task' foi cancelada com sucesso.")
                 except Exception as e_task_cancel: logger.error(f"Erro durante cancelamento da tarefa: {e_task_cancel}")

            if hasattr(bot, "web_runner") and bot.web_runner:
                logger.info("Limpando servidor web..."); await bot.web_runner.cleanup(); logger.info("Servidor web limpo.")

            if hasattr(bot, "coc_client") and bot.coc_client.http and not bot.coc_client.http.closed:
                logger.info("Fechando cliente CoC..."); await bot.coc_client.close(); logger.info("Cliente CoC fechado.")
            logger.info("Desligamento do bot concluído.")


def handle_asyncio_exception(loop, context):
    # ... (código como antes) ...
    msg = context.get("exception", context["message"])
    future_exc = context.get('future')
    if future_exc:
        logger.error(f"Erro não tratado no loop asyncio (Future: {future_exc}): {msg}", exc_info=context.get('exception'))
    else:
        logger.error(f"Erro não tratado no loop asyncio: {msg}", exc_info=context.get('exception'))


if __name__ == "__main__":
    # ... (código como antes) ...
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
        except KeyboardInterrupt: logger.info("Bot interrompido manualmente (KeyboardInterrupt).")
        except RuntimeError as e_runtime:
             if "Event loop is closed" in str(e_runtime): logger.info("Loop de eventos fechado durante o desligamento (normal).")
             else: logger.warning(f"RuntimeError durante execução do loop: {e_runtime}", exc_info=True)
        except Exception as e_fatal: logger.critical(f"Erro fatal fora do loop principal do bot: {e_fatal}", exc_info=True)
        finally:
            if loop_main.is_running(): loop_main.stop()
            if not loop_main.is_closed():
                tasks_main = [t for t in asyncio.all_tasks(loop=loop_main) if t is not asyncio.current_task(loop=loop_main)]
                if tasks_main:
                    logger.info(f"Cancelando {len(tasks_main)} tarefas pendentes...")
                    for task_item_main in tasks_main: task_item_main.cancel()
                    loop_main.run_until_complete(asyncio.gather(*tasks_main, return_exceptions=True))
                    logger.info("Tarefas pendentes canceladas.")
                loop_main.close()
                logger.info("Loop de eventos asyncio fechado.")
            logger.info("Programa finalizado.")
