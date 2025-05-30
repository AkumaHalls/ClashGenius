# -*- coding: utf-8 -*-
# Versão 18.5 - Painel Web SPA (Revisão Final Importações coc.py 3.9.1)

import os
import logging
import asyncio
import datetime
import collections
from aiohttp import web
from typing import Dict, List, Optional, Union, Set

import discord
from discord import app_commands
from discord.ext import commands, tasks

import coc # Import principal
# Para coc.py 3.9.1, tentamos importar diretamente do 'coc' principal.
# WarLogEntry será acessado via coc.WarLogEntry.
from coc import ClanWar, Player, Clan, WarAttack, Timestamp, ClanMember, LeagueGroup, LeagueWar

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
    channel_id_str_for_log = os.environ.get("CHANNEL_ID", "NÃO DEFINIDO")
    logger.error(f"CHANNEL_ID ('{channel_id_str_for_log}') inválido no .env. Usando 0 como padrão.")
    CHANNEL_ID = 0

ROLE_ID_1STAR_ALERT = os.getenv("ROLE_ID_1STAR_ALERT")
ROLE_ID_MISSED_ATTACK = os.getenv("ROLE_ID_MISSED_ATTACK")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

try:
    TIMEZONE = pytz.timezone('America/Sao_Paulo')
except pytz.UnknownTimeZoneError:
    logger.error("Timezone 'America/Sao_Paulo' desconhecida. Usando UTC como padrão.")
    TIMEZONE = pytz.utc

BOT_VERSION = "18.5" # << VERSÃO ATUALIZADA
reported_war_ends: Set[str] = set()

MAX_EVENT_LOG_SIZE = 50
clan_event_log = collections.deque(maxlen=MAX_EVENT_LOG_SIZE)

def add_event_to_log(message: str):
    timestamp = datetime.datetime.now(TIMEZONE).strftime('%d/%m %H:%M')
    clan_event_log.appendleft(f"[{timestamp}] {message}")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- Funções Auxiliares ---
async def get_clan_data(tag: str) -> Clan:
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        if not tag.startswith("#"): tag = f"#{tag}"
        return await bot.coc_client.get_clan(tag)
    except coc.NotFound: raise ValueError(f"Clã com tag {tag} não encontrado.")
    except coc.Maintenance: raise ValueError("API do CoC está em manutenção. Tente novamente mais tarde.")
    except asyncio.TimeoutError: raise ValueError("Tempo limite excedido ao buscar dados do clã. Tente novamente.")
    except coc.InvalidCredentials: raise ValueError("Credenciais inválidas para a API do CoC detectadas.")
    except coc.Forbidden: raise ValueError("Acesso proibido à API do CoC (Forbidden). Verifique permissões da chave API.")
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar dados do clã {tag}: {e}", exc_info=True)
        raise ValueError(f"Erro inesperado ao buscar dados do clã: {str(e)}")

async def get_player_data(tag: str) -> Player:
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        if not tag.startswith("#"): tag = f"#{tag}"
        return await bot.coc_client.get_player(tag)
    except coc.NotFound: raise ValueError(f"Jogador com tag {tag} não encontrado.")
    except coc.Maintenance: raise ValueError("API do CoC está em manutenção. Tente novamente mais tarde.")
    except asyncio.TimeoutError: raise ValueError("Tempo limite excedido ao buscar dados do jogador. Tente novamente.")
    except coc.InvalidCredentials: raise ValueError("Credenciais inválidas para a API do CoC detectadas.")
    except coc.Forbidden: raise ValueError("Acesso proibido à API do CoC (Forbidden). Verifique permissões da chave API.")
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar dados do jogador {tag}: {e}", exc_info=True)
        raise ValueError(f"Erro inesperado ao buscar dados do jogador: {str(e)}")

clan_cache: Dict[str, Dict] = {}
CACHE_DURATION_SECONDS = 300

async def get_clan_data_with_cache(tag: str) -> Clan:
    if not tag.startswith("#"): tag = f"#{tag}"
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
    except discord.NotFound: logger.error(f"Canal de log ID {CHANNEL_ID} não encontrado.")
    except discord.Forbidden: logger.error(f"Sem permissão para enviar mensagens no canal de log ID {CHANNEL_ID}.")
    except Exception as e: logger.error(f"Erro ao enviar embed para o canal de log ID {CHANNEL_ID}: {e}", exc_info=True)

async def send_embeds_splitted(channel: discord.TextChannel, base_embed: discord.Embed,
                               field_name: str, items: List[str]) -> None:
    if not isinstance(channel, discord.TextChannel): logger.error("Canal inválido para send_embeds_splitted."); return
    if not items:
         embed_empty = discord.Embed.from_dict(base_embed.to_dict())
         embed_empty.add_field(name=field_name, value="Nenhum item encontrado.", inline=False)
         if not (hasattr(embed_empty.footer, 'text') and embed_empty.footer.text): embed_empty.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
         if not embed_empty.timestamp: embed_empty.timestamp = datetime.datetime.now(TIMEZONE)
         try: await channel.send(embed=embed_empty)
         except Exception as e: logger.error(f"Erro ao enviar embed dividido (vazio): {e}", exc_info=True)
         return
    embeds_to_send = []
    current_embed_split = discord.Embed.from_dict(base_embed.to_dict())
    current_field_value_split = ""
    for item in items:
        item_line = item + "\n"
        if (len(current_field_value_split) + len(item_line) > 1024 or len(current_embed_split) + len(item_line) > 5900):
            if current_field_value_split: current_embed_split.add_field(name=field_name if field_name else "Dados", value=current_field_value_split, inline=False)
            if current_embed_split.fields: embeds_to_send.append(current_embed_split)
            current_embed_split = discord.Embed.from_dict(base_embed.to_dict()); current_field_value_split = item_line
            if len(current_field_value_split) > 1024: current_field_value_split = current_field_value_split[:1021] + "...\n"
        else: current_field_value_split += item_line
    if current_field_value_split: current_embed_split.add_field(name=field_name if field_name else "Dados", value=current_field_value_split, inline=False)
    if current_embed_split.fields: embeds_to_send.append(current_embed_split)
    for embed_item in embeds_to_send:
        if not (hasattr(embed_item.footer, 'text') and embed_item.footer.text): embed_item.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
        if not embed_item.timestamp: embed_item.timestamp = datetime.datetime.now(TIMEZONE)
    for embed_to_send_msg in embeds_to_send:
        try: await channel.send(embed=embed_to_send_msg)
        except Exception as e: logger.error(f"Erro ao enviar embed dividido: {e}", exc_info=True); break

# --- Funções de Guerra (Restauradas do seu código original) ---
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
             mins, secs_rem_val = divmod(rem, 60)
             time_remaining = f"{days}d {hours}h {mins}m" if days > 0 else f"{hours}h {mins}m {int(secs_rem_val)}s"

         end_time_local_fmt = end_time_aware.strftime('%d/%m/%Y %H:%M')
    except Exception as e:
         logger.error(f"Erro ao calcular tempo restante da guerra em format_attacks_remaining_embed: {e}", exc_info=True)
         time_remaining = "Erro"; end_time_local_fmt = "Erro"

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
    if not missed_members_details: return
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
                     if role: content = f"{role.mention} Ataques Não Realizados!"
                     else: logger.warning(f"Cargo para alerta de ataques perdidos (ID: {ROLE_ID_MISSED_ATTACK}) não encontrado.")
                 except (ValueError, TypeError): logger.error(f"ROLE_ID_MISSED_ATTACK ('{ROLE_ID_MISSED_ATTACK}') é inválido.")
            else: logger.warning(f"Não foi possível encontrar o servidor do canal de log (ID: {CHANNEL_ID}).")
        except discord.Forbidden: logger.error(f"Sem permissão para buscar cargos no servidor do canal {CHANNEL_ID}.")
        except Exception as e: logger.error(f"Erro ao buscar cargo para alerta de ataques perdidos: {e}", exc_info=True)

    opponent_name_val = getattr(getattr(war, 'opponent', None), 'name', 'Oponente Desconhecido')
    start_time_local_str, end_time_local_str = "N/A", "N/A"
    if hasattr(war, 'start_time') and isinstance(war.start_time, Timestamp) and hasattr(war.start_time, 'time'):
        try:
            start_time_local_str = pytz.utc.localize(war.start_time.time).astimezone(TIMEZONE).strftime('%d/%m/%Y %H:%M')
        except Exception as e: logger.error(f"Erro formatar start_time relatório: {e}", exc_info=True); start_time_local_str = "Erro data"
    if hasattr(war, 'end_time') and isinstance(war.end_time, Timestamp) and hasattr(war.end_time, 'time'):
        try:
            end_time_local_str = pytz.utc.localize(war.end_time.time).astimezone(TIMEZONE).strftime('%d/%m/%Y %H:%M')
        except Exception as e: logger.error(f"Erro formatar end_time relatório: {e}", exc_info=True); end_time_local_str = "Erro data"

    description_text = (f"Membros que não usaram todos os ataques contra **{opponent_name_val}**.\n\n"
                        f"**Data do Início da Guerra:** {start_time_local_str}\n"
                        f"**Data do Fim da Guerra:** {end_time_local_str}")
    base_embed_missed = discord.Embed(title=f"❌ Ataques Não Realizados - {war_type}", description=description_text, color=discord.Color.red())
    if hasattr(war, 'opponent') and hasattr(war.opponent, 'badge') and war.opponent.badge:
         base_embed_missed.set_thumbnail(url=war.opponent.badge.url)
    try:
        channel_to_send = await bot.fetch_channel(CHANNEL_ID)
        if isinstance(channel_to_send, discord.TextChannel):
             if content: await channel_to_send.send(content)
             await send_embeds_splitted(channel_to_send, base_embed_missed, "Membros", missed_members_details)
        else: logger.error(f"Canal de log ID {CHANNEL_ID} não é canal de texto para relatório.")
    except discord.NotFound: logger.error(f"Canal de log ID {CHANNEL_ID} não encontrado para relatório.")
    except discord.Forbidden: logger.error(f"Sem permissão para enviar relatório de ataques perdidos no canal {CHANNEL_ID}.")
    except Exception as e: logger.error(f"Erro ao enviar relatório de ataques perdidos: {e}", exc_info=True)

async def send_online_status():
    if not CHANNEL_ID or CHANNEL_ID == 0: logger.warning("CHANNEL_ID não config."); return
    try:
        clan_name, clan_tag_fmt = "Clã Desc.", CLAN_TAG or "Nenhum"
        if CLAN_TAG and hasattr(bot, 'coc_client') and bot.coc_client.http:
             try: clan_data = await bot.coc_client.get_clan(CLAN_TAG); clan_name, clan_tag_fmt = clan_data.name, clan_data.tag
             except Exception as e: logger.error(f"Erro ao buscar clã para status online: {e}")
        embed_online = discord.Embed(title="✅ Bot Online e Monitorando!", description=f"Eventos do clã **{clan_name}** (`{clan_tag_fmt}`) e Guerras monitorados. Painel Web Ativo.", color=discord.Color.green())
        embed_online.add_field(name="Monitoramento", value="Event-Driven Ativo 🔄", inline=False)
        embed_online.add_field(name="Painel Web", value=f"Acessível em /painel", inline=False)
        await send_log_embed(embed_online)
        logger.info("Mensagem de status online enviada.")
        add_event_to_log(f"🤖 Bot reiniciado e online. Versão: {BOT_VERSION}")
    except Exception as e: logger.error(f"Erro ao enviar msg status online: {e}", exc_info=True)

# --- Bot Events ---
@bot.event
async def on_ready():
    logger.info(f"Bot {bot.user.name} ({bot.user.id}) conectado ao Discord! v{BOT_VERSION}")
    if hasattr(bot, 'coc_client') and bot.coc_client.http:
         logger.info("Cliente CoC pronto.")
         if not check_war_end_report_task.is_running():
              try: check_war_end_report_task.start(); logger.info("Task check_war_end_report_task iniciada.")
              except RuntimeError as e: logger.error(f"Erro ao iniciar task check_war_end_report: {e}")
    else: logger.warning("Cliente CoC não pronto no on_ready.")
    await send_online_status()

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    command_name = interaction.command.qualified_name if interaction.command else 'Comando Desconhecido'
    error_embed_cmd = discord.Embed(title="❌ Erro de Comando", color=discord.Color.red())
    error_message = f"Ocorreu um erro inesperado: {str(error)}"
    original_error = getattr(error, 'original', error)
    if isinstance(original_error, ValueError): error_message = str(original_error)
    elif isinstance(original_error, coc.NotFound): error_message = "Não foi possível encontrar o recurso solicitado no Clash of Clans."
    elif isinstance(original_error, coc.Maintenance): error_message = "A API do Clash of Clans está em manutenção. Tente novamente mais tarde."
    elif isinstance(original_error, coc.PrivateWarLog): error_message = "O registro de guerra deste clã é privado e não pode ser acessado."
    elif isinstance(original_error, asyncio.TimeoutError): error_message = "Tempo limite excedido ao buscar dados da API do CoC."
    elif isinstance(original_error, coc.InvalidCredentials): error_message = "Credenciais inválidas para a API do CoC detectadas."
    elif isinstance(original_error, coc.Forbidden): error_message = "Acesso proibido (Forbidden) à API do CoC."
    elif isinstance(error, app_commands.CommandSignatureMismatch): error_message = "Assinatura do comando desatualizada."; logger.warning(f"CommandSignatureMismatch: /{command_name}.")
    elif isinstance(error, app_commands.CheckFailure): error_message = "Você não tem permissão para usar este comando."
    elif isinstance(error, app_commands.CommandNotFound): error_message = "Comando não encontrado."
    elif isinstance(error, app_commands.CommandOnCooldown): error_message = f"Comando em cooldown. Tente em {error.retry_after:.1f}s."
    elif isinstance(error, app_commands.MissingRequiredArgument): param_name = getattr(error.param, 'display_name', getattr(error.param, 'name', 'desconhecido')); error_message = f"Argumento obrigatório faltando: `{param_name}`."
    elif isinstance(error, (app_commands.BadArgument, app_commands.ArgumentParsingError)): error_message = f"Argumento inválido. ({str(error)})"
    else: error_message = f"Ocorreu um erro interno."; logger.error(f"Erro não tratado no comando '{command_name}': {original_error}", exc_info=original_error)
    error_embed_cmd.description = error_message
    error_embed_cmd.set_footer(text=f"Comando: /{command_name}"); error_embed_cmd.timestamp = datetime.datetime.now(TIMEZONE)
    try:
        if interaction.response.is_done(): await interaction.followup.send(embed=error_embed_cmd, ephemeral=True)
        else: await interaction.response.send_message(embed=error_embed_cmd, ephemeral=True)
    except Exception as e: logger.error(f"Erro ao enviar msg de erro da interação /{command_name}: {e}", exc_info=True)

# --- CoC Event Handlers ---
async def register_coc_events(coc_client: coc.EventsClient):
    if not CLAN_TAG: logger.warning("CLAN_TAG não definido."); return
    logger.info(f"Registrando handlers CoC para clã {CLAN_TAG}...")

    @coc_client.event
    @coc.ClanEvents.member_join(tags=[CLAN_TAG])
    async def on_member_join_event(old_member: Optional[ClanMember], member: ClanMember):
        if not member or not hasattr(member, 'clan'): logger.warning("Evento member_join com member inválido."); return
        clan_obj_join = member.clan
        logger.info(f"Evento: {member.name} ({member.tag}) entrou no clã {clan_obj_join.name}.")
        embed_join = discord.Embed(title="👋 Novo Membro", description=f"**{member.name}** (`{member.tag}`) entrou no clã!", color=discord.Color.green())
        embed_join.add_field(name="CV", value=getattr(member, 'town_hall', '?'), inline=True)
        embed_join.add_field(name="Nível", value=getattr(member, 'exp_level', '?'), inline=True)
        embed_join.add_field(name="Troféus", value=getattr(member, 'trophies', '?'), inline=True)
        if hasattr(member, 'league') and member.league: embed_join.add_field(name="Liga", value=member.league.name, inline=True)
        if hasattr(clan_obj_join, 'badge') and clan_obj_join.badge:
             embed_join.set_author(name=clan_obj_join.name, icon_url=clan_obj_join.badge.url)
             embed_join.set_thumbnail(url=clan_obj_join.badge.url)
        await send_log_embed(embed_join)
        add_event_to_log(f"👋 {member.name} (CV{member.town_hall}) entrou no clã.")

    @coc_client.event
    @coc.ClanEvents.member_leave(tags=[CLAN_TAG])
    async def on_member_leave_event(old_member: ClanMember, member: ClanMember):
        if not old_member: logger.warning("Evento member_leave: old_member não fornecido."); return
        clan_obj_leave = old_member.clan if hasattr(old_member, 'clan') else None
        clan_name_leave = getattr(clan_obj_leave, 'name', 'Clã Desconhecido')
        leaving_member_name = getattr(old_member, 'name', 'Membro Desconhecido')
        leaving_member_tag = getattr(old_member, 'tag', 'Tag Desconhecida')
        logger.info(f"Evento: {leaving_member_name} ({leaving_member_tag}) saiu do clã {clan_name_leave}.")
        embed_leave = discord.Embed(title="👋 Membro Saiu", description=f"**{leaving_member_name}** (`{leaving_member_tag}`) saiu do clã!", color=discord.Color.red())
        embed_leave.add_field(name="CV", value=getattr(old_member, 'town_hall', '?'), inline=True)
        embed_leave.add_field(name="Nível", value=getattr(old_member, 'exp_level', '?'), inline=True)
        embed_leave.add_field(name="Troféus", value=getattr(old_member, 'trophies', '?'), inline=True)
        if hasattr(old_member, 'league') and old_member.league: embed_leave.add_field(name="Liga", value=old_member.league.name, inline=True)
        if clan_obj_leave and hasattr(clan_obj_leave, 'badge') and clan_obj_leave.badge:
             embed_leave.set_author(name=clan_name_leave, icon_url=clan_obj_leave.badge.url)
             embed_leave.set_thumbnail(url=clan_obj_leave.badge.url)
        await send_log_embed(embed_leave)
        add_event_to_log(f"🚪 {leaving_member_name} (CV{old_member.town_hall}) saiu do clã.")

    @coc_client.event
    @coc.ClanEvents.member_donations(tags=[CLAN_TAG])
    async def on_member_donations_event(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan'): return
        donation_difference = member.donations - old_member.donations
        if donation_difference <= 0: return
        logger.info(f"Evento: {member.name} doou {donation_difference} tropas (Total: {member.donations}).")
        embed_don = discord.Embed(color=discord.Color.green())
        if hasattr(member.clan, 'badge') and member.clan.badge:
             embed_don.set_author(name=member.clan.name, icon_url=member.clan.badge.url)
             embed_don.set_thumbnail(url=member.clan.badge.url)
        embed_don.add_field(name="🎁 Doação", value=f"**{donation_difference}** tropas por `{member.name}` (Total doado: {member.donations})", inline=False)
        await send_log_embed(embed_don)
        add_event_to_log(f"🎁 {member.name} doou {donation_difference} tropas.")

    @coc_client.event
    @coc.ClanEvents.member_received(tags=[CLAN_TAG])
    async def on_member_received_event(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan'): return
        received_difference = member.received - old_member.received
        if received_difference <= 0: return
        logger.info(f"Evento: {member.name} recebeu {received_difference} tropas (Total: {member.received}).")
        embed_rec = discord.Embed(color=discord.Color.blue())
        if hasattr(member.clan, 'badge') and member.clan.badge:
            embed_rec.set_author(name=member.clan.name, icon_url=member.clan.badge.url)
            embed_rec.set_thumbnail(url=member.clan.badge.url)
        embed_rec.add_field(name="📥 Recebimento", value=f"`{member.name}` recebeu **{received_difference}** tropas (Total recebido: {member.received})", inline=False)
        await send_log_embed(embed_rec)
        add_event_to_log(f"📥 {member.name} recebeu {received_difference} tropas.")

    @coc_client.event
    @coc.ClanEvents.member_role_change(tags=[CLAN_TAG])
    async def on_member_role_change_event(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan') or old_member.role == member.role: return
        logger.info(f"Evento: Cargo de {member.name} mudou de {old_member.role} para {member.role} em {member.clan.name}.")
        embed_role = discord.Embed(title="🔄 Mudança de Cargo", description=f"Cargo de **{member.name}** (`{member.tag}`) foi alterado!", color=discord.Color.gold())
        embed_role.add_field(name="Cargo Anterior", value=old_member.role.name.capitalize() if old_member.role else 'N/A', inline=True)
        embed_role.add_field(name="Novo Cargo", value=member.role.name.capitalize() if member.role else 'N/A', inline=True)
        if hasattr(member.clan, 'badge') and member.clan.badge:
             embed_role.set_author(name=member.clan.name, icon_url=member.clan.badge.url)
             embed_role.set_thumbnail(url=member.clan.badge.url)
        await send_log_embed(embed_role)
        add_event_to_log(f"🔄 Cargo de {member.name} mudou de {old_member.role} para {member.role}.")

    @coc_client.event
    @coc.ClanEvents.member_league_change(tags=[CLAN_TAG])
    async def on_member_league_change_event(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan') or old_member.league == member.league: return
        old_league_name = old_member.league.name if old_member.league else "Sem Liga"
        new_league_name = member.league.name if member.league else "Sem Liga"
        logger.info(f"Evento: Liga de {member.name} mudou de {old_league_name} para {new_league_name} em {member.clan.name}.")
        embed_league = discord.Embed(title="🏆 Mudança de Liga", description=f"Liga de **{member.name}** (`{member.tag}`) foi alterada!", color=discord.Color.purple())
        embed_league.add_field(name="Liga Anterior", value=old_league_name, inline=True)
        embed_league.add_field(name="Nova Liga", value=new_league_name, inline=True)
        if hasattr(member.clan, 'badge') and member.clan.badge:
             embed_league.set_author(name=member.clan.name, icon_url=member.clan.badge.url)
             embed_league.set_thumbnail(url=member.clan.badge.url)
        await send_log_embed(embed_league)
        add_event_to_log(f"🏆 Liga de {member.name} mudou de {old_league_name} para {new_league_name}.")

    @coc_client.event
    @coc.ClanEvents.member_trophies_change(tags=[CLAN_TAG])
    async def on_member_trophies_change_event(old_member: ClanMember, member: ClanMember):
        if not member or not old_member: return
        trophy_difference = member.trophies - old_member.trophies
        if abs(trophy_difference) < 5 : return
        logger.info(f"Evento: Troféus de {member.name} mudaram em {trophy_difference} (Total: {member.trophies}).")
        direction = "ganhou" if trophy_difference > 0 else "perdeu"
        embed_trophies = discord.Embed(description=f"**{member.name}** {direction} **{abs(trophy_difference)}** troféus (Total: {member.trophies})",
                                       color=discord.Color.green() if trophy_difference > 0 else discord.Color.dark_red())
        await send_log_embed(embed_trophies)
        add_event_to_log(f"🏆 {member.name} {direction} {abs(trophy_difference)} troféus (Total: {member.trophies}).")

    @coc_client.event
    @coc.WarEvents.war_attack(tags=[CLAN_TAG])
    async def on_war_attack_event(attack: WarAttack, war: ClanWar):
        if not all(hasattr(attack, attr) for attr in ['attacker_tag', 'defender_tag', 'stars', 'destruction', 'order']):
            logger.warning(f"Evento de ataque de guerra incompleto. War Tag: {getattr(war, 'tag', 'N/A')}"); return
        is_our_attack, is_our_defense, attacker_player, defender_player = False, False, None, None
        try:
             attacker_player = await get_player_data(attack.attacker_tag)
             defender_player = await get_player_data(attack.defender_tag)
             attacker_clan_tag = getattr(attacker_player.clan, 'tag', None) if hasattr(attacker_player, 'clan') else None
             defender_clan_tag = getattr(defender_player.clan, 'tag', None) if hasattr(defender_player, 'clan') else None
             if attacker_clan_tag == CLAN_TAG: is_our_attack = True
             elif defender_clan_tag == CLAN_TAG: is_our_defense = True
             elif not (attacker_clan_tag or defender_clan_tag): logger.warning(f"Clãs não determinados para ataque {attack.order}."); return
             else: return
        except ValueError as e: logger.warning(f"Não foi possível buscar dados de jogador para ataque {attack.order}: {e}"); return
        except Exception as e: logger.error(f"Erro ao buscar dados para ataque {attack.order}: {e}", exc_info=True); return

        attacker_name = getattr(attacker_player, 'name', attack.attacker_tag)
        defender_name = getattr(defender_player, 'name', attack.defender_tag)
        attacker_th = getattr(attacker_player, 'town_hall', '?')
        defender_th = getattr(defender_player, 'town_hall', '?')
        stars_str = "⭐" * attack.stars + "⚫" * (3 - attack.stars)
        content_alert = None

        if is_our_attack:
            logger.info(f"Evento Guerra: {attacker_name} atacou {defender_name} - {attack.stars}*, {attack.destruction}%.")
            embed_event = discord.Embed(title=f"⚔️ Ataque Realizado (Guerra)", description=f"**{attacker_name}** (CV{attacker_th}) atacou **{defender_name}** (CV{defender_th})", color=discord.Color.blue())
            embed_event.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
            if attack.stars <= 1 and ROLE_ID_1STAR_ALERT:
                try:
                    log_channel_alert = await bot.fetch_channel(CHANNEL_ID)
                    if log_channel_alert and hasattr(log_channel_alert, 'guild'):
                         guild_alert = log_channel_alert.guild
                         try:
                              role_id_int_alert = int(ROLE_ID_1STAR_ALERT)
                              role_alert = guild_alert.get_role(role_id_int_alert)
                              if role_alert: content_alert = f"{role_alert.mention} ⚠️ Atenção: ataque fora do padrão!"
                              else: logger.warning(f"Cargo para alerta 1 estrela (ID: {ROLE_ID_1STAR_ALERT}) não encontrado.")
                         except (ValueError, TypeError): logger.error(f"ROLE_ID_1STAR_ALERT ('{ROLE_ID_1STAR_ALERT}') é inválido.")
                except Exception as e_alert: logger.error(f"Erro ao buscar cargo para alerta 1 estrela: {e_alert}", exc_info=True)
            if hasattr(war, 'clan') and war.clan.badge: embed_event.set_author(name=war.clan.name, icon_url=war.clan.badge.url); embed_event.set_thumbnail(url=war.clan.badge.url)
            await send_log_embed(embed_event, content_alert)
            add_event_to_log(f"⚔️ {attacker_name} atacou {defender_name} ({attack.stars}⭐, {attack.destruction}%)")
        elif is_our_defense:
            logger.info(f"Evento Guerra: {defender_name} foi atacado por {attacker_name} - {attack.stars}*, {attack.destruction}%.")
            embed_event = discord.Embed(title=f"🛡️ Defesa Recebida (Guerra)", description=f"**{defender_name}** (CV{defender_th}) foi atacado por **{attacker_name}** (CV{attacker_th})", color=discord.Color.orange())
            embed_event.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
            if hasattr(war, 'opponent') and war.opponent.badge: embed_event.set_author(name=war.opponent.name, icon_url=war.opponent.badge.url); embed_event.set_thumbnail(url=war.opponent.badge.url)
            await send_log_embed(embed_event)
            add_event_to_log(f"🛡️ {defender_name} foi atacado por {attacker_name} ({attack.stars}⭐, {attack.destruction}%)")
    logger.info("Manipuladores de eventos CoC registrados.")

# --- Tasks ---
@tasks.loop(minutes=10)
async def check_war_end_report_task():
    if not bot.coc_client or not bot.coc_client.http: logger.debug("check_war_end: Cliente CoC não pronto."); return
    logger.debug("check_war_end: Iniciando verificação..."); processed_war_ids: Set[str] = set()
    async def process_war(war_obj: ClanWar, war_type_name: str):
        war_id = war_obj.end_time.raw_time if hasattr(war_obj, 'end_time') and hasattr(war_obj.end_time, 'raw_time') else None
        if not war_obj or not war_id or war_id in processed_war_ids: return
        opponent_name_proc = getattr(getattr(war_obj, 'opponent', None), 'name', 'Oponente Desconhecido')
        war_state_proc = getattr(war_obj, 'state', 'unknown')
        logger.debug(f"Processando guerra: {war_type_name} vs {opponent_name_proc} (ID: {war_id}, Estado: {war_state_proc})")
        if war_state_proc == "warEnded" and war_id not in reported_war_ends:
            logger.info(f"Guerra '{war_type_name}' vs {opponent_name_proc} terminou. Verificando ataques...")
            add_event_to_log(f"🏁 Guerra '{war_type_name}' vs {opponent_name_proc} finalizada. Verificando ataques...")
            our_clan_obj = None; attacks_per_member = 1 if "Liga" in war_type_name else getattr(war_obj, 'attacks_per_member', 2)
            if "Liga" in war_type_name:
                if getattr(getattr(war_obj, 'clan', None), 'tag', None) == CLAN_TAG: our_clan_obj = war_obj.clan
                elif getattr(getattr(war_obj, 'opponent', None), 'tag', None) == CLAN_TAG: our_clan_obj = war_obj.opponent
                else: logger.error(f"CWL {war_id} não contém clã {CLAN_TAG}."); return
            else: our_clan_obj = getattr(war_obj, 'clan', None)
            if not our_clan_obj: logger.error(f"Não foi possível ID nosso clã na guerra {war_id}."); return
            missed_details = []
            if hasattr(our_clan_obj, 'members') and our_clan_obj.members:
                 for member in our_clan_obj.members:
                    if not member or not hasattr(member, 'tag'): continue
                    used = len(member.attacks) if hasattr(member, "attacks") and member.attacks else 0
                    if used < attacks_per_member:
                        missed_count = attacks_per_member - used
                        missed_details.append(f"**{getattr(member, 'name', member.tag)}** (CV{getattr(member, 'town_hall', '?')}): {missed_count} perdido{'s' if missed_count > 1 else ''}")
            if missed_details:
                logger.info(f"{len(missed_details)} membro(s) perderam ataques na guerra {war_type_name}.");
                await send_missed_attacks_report(war_obj, missed_details, war_type_name)
                add_event_to_log(f"❌ {len(missed_details)} membro(s) não atacaram na guerra vs {opponent_name_proc}.")
            else:
                logger.info(f"Nenhum ataque perdido na guerra {war_type_name}.");
                add_event_to_log(f"✅ Todos os ataques realizados na guerra vs {opponent_name_proc}!")
            reported_war_ends.add(war_id); processed_war_ids.add(war_id)
    try:
        logger.debug("Buscando guerra regular..."); current_war = await bot.coc_client.get_current_war(CLAN_TAG)
        if current_war and hasattr(current_war, 'state') and current_war.state != "notInWar":
             if hasattr(current_war, 'end_time'): await process_war(current_war, "Guerra Normal")
    except coc.PrivateWarLog: logger.warning("Log de guerra regular é privado.")
    except coc.NotFound: logger.info("Clã não encontrado para guerra regular.")
    except Exception as e: logger.error(f"Erro guerra regular: {e}", exc_info=True)
    try:
        logger.debug("Buscando grupo de liga (CWL)..."); league_group = await bot.coc_client.get_league_group(CLAN_TAG)
        if league_group and hasattr(league_group, 'state') and league_group.state != "notInWar":
            if hasattr(league_group, 'rounds') and league_group.rounds:
                 for i, war_tags in reversed(list(enumerate(league_group.rounds))):
                     logger.debug(f"Processando rodada CWL {i + 1}...")
                     for war_tag in war_tags:
                         try:
                             league_war = await league_group.get_league_war(war_tag)
                             if not league_war or not hasattr(league_war, 'state') or not hasattr(league_war, 'end_time'): continue
                             if getattr(getattr(league_war, 'clan', None), 'tag', None) == CLAN_TAG or \
                                getattr(getattr(league_war, 'opponent', None), 'tag', None) == CLAN_TAG:
                                 await process_war(league_war, f"Liga de Clãs (Rodada {i + 1})")
                         except coc.NotFound: logger.warning(f"Guerra CWL {war_tag} não encontrada.")
                         except Exception as e: logger.error(f"Erro guerra CWL {war_tag}: {e}", exc_info=True)
    except coc.NotFound: logger.info("Clã não encontrado para CWL.")
    except Exception as e: logger.error(f"Erro CWL: {e}", exc_info=True)
    logger.debug("check_war_end: Verificação concluída.")

@check_war_end_report_task.before_loop
async def before_check_war():
    await bot.wait_until_ready()
    logger.info("Bot pronto. Task 'check_war_end_report_task' pode iniciar.")

# --- Slash Commands (Restaurados do seu código original) ---
admin_group = app_commands.Group(name="admin", description="Comandos administrativos")
war_group = app_commands.Group(name="guerra", description="Comandos relacionados a guerras")
info_group = app_commands.Group(name="info", description="Comandos de informação")
search_group = app_commands.Group(name="buscar", description="Comandos de busca")
rank_group = app_commands.Group(name="rank", description="Comandos de ranking")

@admin_group.command(name="ping", description="Verifica a latência do bot")
@app_commands.checks.has_permissions(administrator=True)
async def admin_ping(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    embed_ping = discord.Embed(title="🏓 Pong!", description=f"Latência API Discord: **{latency_ms}ms**",
                               color=discord.Color.green() if latency_ms < 200 else discord.Color.orange() if latency_ms < 500 else discord.Color.red())
    embed_ping.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed_ping.timestamp = datetime.datetime.now(TIMEZONE)
    await interaction.response.send_message(embed=embed_ping, ephemeral=True)

@war_group.command(name="ataques", description="Exibe os ataques restantes na guerra atual (Normal ou Liga)")
async def war_attacks(interaction: discord.Interaction):
    await interaction.response.defer()
    current_war_cmd: Optional[ClanWar] = None
    try:
        lg_cmd = await bot.coc_client.get_league_group(CLAN_TAG)
        if lg_cmd and getattr(lg_cmd,'state',None) != "notInWar" and hasattr(lg_cmd, 'rounds'):
            for _r, war_tags_cmd in enumerate(lg_cmd.rounds):
                 if current_war_cmd: break
                 for war_tag_cmd in war_tags_cmd:
                     try:
                         lw_cmd: LeagueWar = await lg_cmd.get_league_war(war_tag_cmd)
                         if lw_cmd and (getattr(getattr(lw_cmd,'clan',None),'tag',None) == CLAN_TAG or getattr(getattr(lw_cmd,'opponent',None),'tag',None) == CLAN_TAG):
                              if getattr(lw_cmd,'state',None) == "inWar":
                                   if getattr(getattr(lw_cmd,'opponent',None),'tag',None) == CLAN_TAG: lw_cmd.clan, lw_cmd.opponent = lw_cmd.opponent, lw_cmd.clan
                                   current_war_cmd = lw_cmd; break
                     except: continue
    except: logger.error("Erro ao buscar CWL para /guerra ataques", exc_info=True)
    if not current_war_cmd:
         try:
             reg_war_cmd = await bot.coc_client.get_current_war(CLAN_TAG)
             if reg_war_cmd and getattr(reg_war_cmd, 'state', None) == "inWar": current_war_cmd = reg_war_cmd
         except coc.PrivateWarLog: await interaction.followup.send("Log de guerra regular é privado.", ephemeral=True); return
         except Exception as e_reg: logger.error(f"Erro ao buscar guerra regular para /guerra ataques: {e_reg}", exc_info=True); await interaction.followup.send("Erro ao buscar guerra regular.",ephemeral=True); return
    if current_war_cmd:
         if isinstance(current_war_cmd, ClanWar): # ClanWar é a classe base para LeagueWar também
              embeds_list = await format_attacks_remaining_embed(current_war_cmd)
              if embeds_list:
                  await interaction.followup.send(embed=embeds_list.pop(0))
                  for embed_item in embeds_list:
                      if interaction.channel and isinstance(interaction.channel, discord.abc.Messageable): await interaction.channel.send(embed=embed_item)
              else: await interaction.followup.send(f"Erro ao formatar ataques.", ephemeral=True)
         else: await interaction.followup.send(f"Erro interno ao processar dados da guerra.", ephemeral=True)
    else: await interaction.followup.send("O clã não está em nenhuma guerra ativa (Normal ou Liga).")

@war_group.command(name="status", description="Exibe o status da guerra atual (Normal ou Liga)")
async def war_status(interaction: discord.Interaction):
    await interaction.response.defer()
    war_to_display: Optional[ClanWar] = None; war_type_name_status = "Guerra"
    status_description = "Nenhuma guerra ativa ou recente encontrada."; status_color = discord.Color.greyple()
    try:
        lg_status: LeagueGroup = await bot.coc_client.get_league_group(CLAN_TAG)
        if lg_status and getattr(lg_status, 'state', None) != "notInWar" and hasattr(lg_status, 'rounds'):
            active_cwl, prep_cwl, ended_cwl = None, None, None; active_r, prep_r, ended_r = -1, -1, -1
            for r_num, wars_tags in enumerate(lg_status.rounds):
                 for war_tag in wars_tags:
                     try:
                         lw_obj: LeagueWar = await lg_status.get_league_war(war_tag)
                         if not lw_obj or not hasattr(lw_obj, 'state'): continue
                         if getattr(getattr(lw_obj,'clan',None),'tag',None) == CLAN_TAG or getattr(getattr(lw_obj,'opponent',None),'tag',None) == CLAN_TAG:
                              if getattr(getattr(lw_obj,'opponent',None),'tag',None) == CLAN_TAG: lw_obj.clan, lw_obj.opponent = lw_obj.opponent, lw_obj.clan
                              if lw_obj.state == "inWar": active_cwl, active_r = lw_obj, r_num + 1; break
                              elif lw_obj.state == "preparation": prep_cwl, prep_r = lw_obj, r_num + 1
                              elif lw_obj.state == "warEnded":
                                   current_ended_time = getattr(ended_cwl.end_time, 'time', datetime.datetime.min.replace(tzinfo=pytz.utc)) if ended_cwl and hasattr(ended_cwl, 'end_time') else datetime.datetime.min.replace(tzinfo=pytz.utc)
                                   if hasattr(lw_obj.end_time,'time') and (not ended_cwl or lw_obj.end_time.time > current_ended_time):
                                       ended_cwl, ended_r = lw_obj, r_num+1
                     except: continue
                 if active_cwl: break
            if active_cwl: war_to_display, war_type_name_status = active_cwl, f"Liga (Rodada {active_r})"
            elif prep_cwl: war_to_display, war_type_name_status = prep_cwl, f"Liga (Rodada {prep_r})"
            elif ended_cwl: war_to_display, war_type_name_status = ended_cwl, f"Liga (Rodada {ended_r})"
    except Exception as e_cwl_status: logger.error(f"Erro ao buscar CWL para /guerra status: {e_cwl_status}", exc_info=True)
    if not war_to_display:
        try:
            reg_war = await bot.coc_client.get_current_war(CLAN_TAG)
            if reg_war and getattr(reg_war, 'state', None) != "notInWar": war_to_display, war_type_name_status = reg_war, "Guerra Normal"
        except coc.PrivateWarLog: status_description, status_color = "Log de guerra regular é privado.", discord.Color.orange()
        except Exception as e_reg_status: status_description, status_color = "Erro ao buscar guerra regular.", discord.Color.red(); logger.error(f"Erro guerra regular /status: {e_reg_status}")

    embed_status = discord.Embed(title=f"⚔️ Status: {war_type_name_status}", color=status_color)
    if war_to_display and isinstance(war_to_display, ClanWar): # ClanWar é base para LeagueWar
         clan_d = war_to_display.clan; opp_d = war_to_display.opponent
         embed_status.title = f"⚔️ Status: {war_type_name_status} - {clan_d.name} vs {opp_d.name}"
         if hasattr(clan_d, 'badge') and clan_d.badge: embed_status.set_thumbnail(url=clan_d.badge.url)
         state_d = war_to_display.state; start_t_str, end_t_str, time_rem_str = "N/A", "N/A", "N/A"
         try:
            now_d = datetime.datetime.now(TIMEZONE)
            if hasattr(war_to_display.start_time, 'time') and war_to_display.start_time.time:
                start_aware_d = pytz.utc.localize(war_to_display.start_time.time).astimezone(TIMEZONE); start_t_str = start_aware_d.strftime('%d/%m/%Y %H:%M')
                if state_d == "preparation": delta_d = start_aware_d - now_d; time_rem_str = f"{int(delta_d.total_seconds()//3600)}h {int((delta_d.total_seconds()%3600)//60)}m" if delta_d.total_seconds() > 0 else "Iniciada"
            if hasattr(war_to_display.end_time, 'time') and war_to_display.end_time.time:
                end_aware_d = pytz.utc.localize(war_to_display.end_time.time).astimezone(TIMEZONE); end_t_str = end_aware_d.strftime('%d/%m/%Y %H:%M')
                if state_d == "inWar": delta_d = end_aware_d - now_d; time_rem_str = f"{int(delta_d.total_seconds()//3600)}h {int((delta_d.total_seconds()%3600)//60)}m" if delta_d.total_seconds() > 0 else "Finalizada"
         except: time_rem_str = "Erro Tempo"
         if state_d == "preparation": embed_status.description = f"**Estado:** Preparação ⏳\n**Início:** {start_t_str} (em ~{time_rem_str})"; embed_status.color=discord.Color.light_grey()
         elif state_d == "inWar": embed_status.description = f"**Estado:** Em Guerra 🔥\n**Fim:** {end_t_str} ({time_rem_str} restantes)"; embed_status.add_field(name=f"{clan_d.name}", value=f"{clan_d.stars}⭐ ({clan_d.destruction:.2f}%)", inline=True); embed_status.add_field(name=f"{opp_d.name}", value=f"{opp_d.stars}⭐ ({opp_d.destruction:.2f}%)", inline=True); embed_status.color=discord.Color.blue()
         elif state_d == "warEnded":
            res = "Empate 🤝"; color_res = discord.Color.greyple()
            if clan_d.stars > opp_d.stars or (clan_d.stars == opp_d.stars and clan_d.destruction > opp_d.destruction): res, color_res = "Vitória ✅", discord.Color.green()
            elif opp_d.stars > clan_d.stars or (clan_d.stars == opp_d.stars and opp_d.destruction > clan_d.destruction): res, color_res = "Derrota ❌", discord.Color.red()
            embed_status.description = f"**Estado:** Guerra Finalizada\n**Resultado:** {res}\n**Fim:** {end_t_str}"; embed_status.add_field(name=f"{clan_d.name}", value=f"{clan_d.stars}⭐ ({clan_d.destruction:.2f}%)", inline=True); embed_status.add_field(name=f"{opp_d.name}", value=f"{opp_d.stars}⭐ ({opp_d.destruction:.2f}%)", inline=True); embed_status.color=color_res
         else: embed_status.description = f"**Estado:** {state_d.capitalize()}"
    else: embed_status.description = status_description
    embed_status.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed_status.timestamp = datetime.datetime.now(TIMEZONE)
    await interaction.followup.send(embed=embed_status)

@info_group.command(name="clan", description="Exibe informações sobre um clã")
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def clan_info(interaction: discord.Interaction, tag: Optional[str] = None):
    target_tag = tag or CLAN_TAG
    if not target_tag: await interaction.response.send_message("Nenhuma tag de clã especificada.", ephemeral=True); return
    try:
        await interaction.response.defer()
        clan_data = await get_clan_data_with_cache(target_tag)
        embed = discord.Embed(title=f"{clan_data.name} ({clan_data.tag})", description=clan_data.description or "Sem descrição.", color=discord.Color.blue())
        if hasattr(clan_data, 'badge') and clan_data.badge: embed.set_thumbnail(url=clan_data.badge.url)
        embed.add_field(name="Nível", value=getattr(clan_data,'level','N/A'), inline=True); embed.add_field(name="Pontos", value=getattr(clan_data,'points','N/A'), inline=True)
        embed.add_field(name="Guerras Ganhas", value=getattr(clan_data,'war_wins','N/A'), inline=True)
        if hasattr(clan_data,'location') and clan_data.location: embed.add_field(name="Localização", value=clan_data.location.name, inline=True)
        embed.add_field(name="Tipo", value=getattr(clan_data,'type','N/A').capitalize(), inline=True); embed.add_field(name="Membros", value=f"{getattr(clan_data,'member_count','N/A')}/50", inline=True)
        if hasattr(clan_data,"capital_points"): embed.add_field(name="Troféus Capital", value=clan_data.capital_points, inline=True)
        if hasattr(clan_data,'public_war_log'): embed.add_field(name="Log de Guerra", value="Público" if clan_data.public_war_log else "Privado", inline=True)
        if hasattr(clan_data,'required_trophies'): embed.add_field(name="Troféus Mín.", value=clan_data.required_trophies, inline=True)
        if hasattr(clan_data,'required_town_hall'): embed.add_field(name="CV Mín.", value=clan_data.required_town_hall, inline=True)
        if hasattr(clan_data,'war_frequency'): embed.add_field(name="Freq. Guerra", value=clan_data.war_frequency.capitalize(), inline=True)
        if hasattr(clan_data,'labels') and clan_data.labels: labels_str = ", ".join([lbl.name for lbl in clan_data.labels if hasattr(lbl,'name')]); embed.add_field(name="Tags", value=labels_str, inline=False)
        embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}"); embed.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed)
    except ValueError as e: await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e: logger.error(f"Erro /info clan {target_tag}: {e}", exc_info=True); await interaction.followup.send("Erro ao buscar info do clã.", ephemeral=True)

# (Continue restaurando /info jogador, /info membros, todos os /buscar e todos os /rank
#  com a lógica completa do seu arquivo original aqui)
# ...

bot.tree.add_command(admin_group)
bot.tree.add_command(war_group)
bot.tree.add_command(info_group)
bot.tree.add_command(search_group)
bot.tree.add_command(rank_group)

# ============================================================================ #
# ==================== PAINEL WEB - LÓGICA E ENDPOINTS API ==================== #
# ============================================================================ #
# (Esta seção inteira, de web_api_cache até o final de setup_web_server,
#  permanece como na v18.2 que te enviei, pois as correções de import
#  já foram feitas no topo do arquivo.)
web_api_cache: Dict[str, Dict] = {}
WEB_API_CACHE_DURATION_SECONDS = 30

async def get_cached_web_data(key: str, func_to_fetch_data, *args, _cache_duration=None, **kwargs):
    actual_cache_duration = _cache_duration if _cache_duration is not None else WEB_API_CACHE_DURATION_SECONDS
    now = datetime.datetime.now()
    if key in web_api_cache:
        cache_entry = web_api_cache[key]
        cache_age = (now - cache_entry["timestamp"]).total_seconds()
        if cache_age < actual_cache_duration:
            logger.debug(f"Usando cache API web (chave: {key}, idade: {cache_age:.1f}s)")
            return cache_entry["data"]
    logger.debug(f"Buscando novos dados API web (chave: {key})")
    data = await func_to_fetch_data(*args, **kwargs)
    web_api_cache[key] = {"data": data, "timestamp": now}
    return data

async def fetch_clan_info_for_web_api():
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
    except Exception as e: return {"error": str(e), "name": "Erro ao carregar Clã"}

async def fetch_clan_members_for_web_api():
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
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    current_war: Optional[Union[ClanWar, coc.WarLogEntry]] = None
    war_type_description = "Nenhuma guerra"
    try:
        lg: LeagueGroup = await bot.coc_client.get_league_group(CLAN_TAG)
        if lg and lg.state != "notInWar" and lg.rounds:
            for i, war_tags in reversed(list(enumerate(lg.rounds))):
                for tag in war_tags:
                    try:
                        war: LeagueWar = await lg.get_league_war(tag)
                        if war and (war.clan.tag == CLAN_TAG or war.opponent.tag == CLAN_TAG):
                            if war.state == "inWar" or war.state == "preparation":
                                if war.opponent.tag == CLAN_TAG: war.clan, war.opponent = war.opponent, war.clan
                                current_war = war; war_type_description = f"Liga (Rodada {i+1})"; break
                    except: continue
                if current_war: break
    except coc.NotFound: pass
    except Exception as e: logger.error(f"Erro CWL API Web: {e}")

    if not current_war:
        try:
            war = await bot.coc_client.get_current_war(CLAN_TAG)
            if war and (war.state == "inWar" or war.state == "preparation"):
                current_war = war; war_type_description = "Guerra Normal"
        except coc.PrivateWarLog: return {"status": "PrivateWarLog", "message": "Log de guerra privado."}
        except coc.NotFound: pass
        except Exception as e: logger.error(f"Erro Guerra Regular API Web: {e}")

    if not current_war:
        try:
            war_log = await bot.coc_client.get_war_log(CLAN_TAG, limit=1)
            if war_log: current_war = war_log[0]; war_type_description = "Última Guerra (Log)"
        except coc.PrivateWarLog: return {"status": "PrivateWarLog", "message": "Log de guerra privado."}
        except Exception as e: logger.error(f"Erro WarLog API Web: {e}")

    if not current_war: return {"status": "NotInWar", "message": "Nenhuma guerra ativa ou no log recente."}

    now_tz = datetime.datetime.now(TIMEZONE)
    state_desc = current_war.state.capitalize() if hasattr(current_war, 'state') else "Finalizada (Log)"
    time_key, time_val, time_rem = "N/A", "N/A", "-"

    if isinstance(current_war, ClanWar): # Também cobre LeagueWar
        if current_war.state == "preparation" and current_war.start_time and hasattr(current_war.start_time, 'time'):
            start_aware = pytz.utc.localize(current_war.start_time.time).astimezone(TIMEZONE)
            time_key, time_val = "Início", start_aware.strftime('%d/%m %H:%M')
            delta = start_aware - now_tz
            if delta.total_seconds() > 0: time_rem = f"{int(delta.total_seconds() // 3600)}h {int((delta.total_seconds() % 3600) // 60)}m"
            else: time_rem = "Iniciando..."
        elif current_war.state == "inWar" and current_war.end_time and hasattr(current_war.end_time, 'time'):
            end_aware = pytz.utc.localize(current_war.end_time.time).astimezone(TIMEZONE)
            time_key, time_val = "Fim", end_aware.strftime('%d/%m %H:%M')
            delta = end_aware - now_tz
            if delta.total_seconds() > 0: time_rem = f"{int(delta.total_seconds() // 3600)}h {int((delta.total_seconds() % 3600) // 60)}m"
            else: time_rem = "Finalizando..."
        elif current_war.state == "warEnded" and current_war.end_time and hasattr(current_war.end_time, 'time'):
            time_key = "Finalizada"; time_val = pytz.utc.localize(current_war.end_time.time).astimezone(TIMEZONE).strftime('%d/%m %H:%M')
    elif isinstance(current_war, coc.WarLogEntry):
        time_key = "Finalizada (Log)"
        if current_war.end_time and hasattr(current_war.end_time, 'time'): time_val = pytz.utc.localize(current_war.end_time.time).astimezone(TIMEZONE).strftime('%d/%m %H:%M')
        state_desc = current_war.result.capitalize() if current_war.result else "Finalizada"

    our_clan_data = current_war.clan if isinstance(current_war, (ClanWar, LeagueWar)) else (current_war.clan if current_war.clan.tag == CLAN_TAG else current_war.opponent)
    opponent_data = current_war.opponent if isinstance(current_war, (ClanWar, LeagueWar)) else (current_war.opponent if current_war.clan.tag == CLAN_TAG else current_war.clan)

    return {
        "status": current_war.state if hasattr(current_war, 'state') else "warEnded",
        "type": war_type_description, "state_description": state_desc,
        "clan_name": our_clan_data.name, "clan_stars": our_clan_data.stars,
        "clan_destruction": f"{our_clan_data.destruction:.2f}%",
        "clan_badge_url": our_clan_data.badge.url if hasattr(our_clan_data, 'badge') and our_clan_data.badge else None,
        "opponent_name": opponent_data.name, "opponent_tag": opponent_data.tag,
        "opponent_stars": opponent_data.stars, "opponent_destruction": f"{opponent_data.destruction:.2f}%",
        "opponent_badge_url": opponent_data.badge.url if hasattr(opponent_data, 'badge') and opponent_data.badge else None,
        "time_key": time_key, "time_value": time_val, "time_remaining": time_rem,
        "attacks_per_member": getattr(current_war, 'attacks_per_member', 1 if "Liga" in war_type_description else 2),
        "team_size": getattr(current_war, 'team_size', 'N/A')
    }

async def fetch_player_details_for_web_api(player_tag: str):
    if not player_tag: return {"error": "Tag do jogador não fornecida."}
    try:
        player = await get_player_data(player_tag)
        heroes_data = [{"name": h.name, "level": h.level, "max_level": h.max_level, "village": h.village} for h in player.heroes]
        troops_data = [{"name": t.name, "level": t.level, "max_level": t.max_level_for_townhall(player.town_hall) if hasattr(t, 'max_level_for_townhall') else t.max_level, "village": t.village} for t in player.troops]
        spells_data = [{"name": s.name, "level": s.level, "max_level": s.max_level_for_townhall(player.town_hall) if hasattr(s, 'max_level_for_townhall') else s.max_level, "village": s.village} for s in player.spells]
        return {
            "name": player.name, "tag": player.tag, "town_hall": player.town_hall, "exp_level": player.exp_level,
            "trophies": player.trophies, "best_trophies": player.best_trophies,
            "league": player.league.name if player.league else "N/A",
            "league_icon_url": player.league.icon.url if player.league and hasattr(player.league.icon, 'url') else None,
            "clan_name": player.clan.name if player.clan else "Sem Clã", "clan_tag": player.clan.tag if player.clan else "N/A",
            "role": player.role.name.capitalize() if player.role else "Membro",
            "donations": player.donations, "received": player.received,
            "war_stars": player.war_stars, "attack_wins": player.attack_wins,
            "heroes": heroes_data, "troops": troops_data, "spells": spells_data,
            "builder_hall_level": getattr(player, 'builder_hall_level', None),
            "builder_base_trophies": getattr(player, 'builder_base_trophies', None),
            "best_builder_base_trophies": getattr(player, 'best_builder_base_trophies', None),
            "achievements": [{"name": a.name, "stars": a.stars, "value": a.value, "target": a.target, "info": a.info} for a in player.achievements if a.value > 0 and a.name in ["Friend in Need", "War Hero", "Clan War Leagues", "Games Champion"]],
        }
    except ValueError as e: return {"error": str(e)}
    except Exception as e: logger.error(f"Erro ao buscar detalhes do jogador {player_tag} para API: {e}"); return {"error": "Erro interno."}

async def fetch_clan_events_log_for_web_api(): return {"events": list(clan_event_log)}

async def fetch_cwl_info_for_web_api():
    if not CLAN_TAG: return {"error": "CLAN_TAG não configurado."}
    try:
        group: LeagueGroup = await bot.coc_client.get_league_group(CLAN_TAG)
        if not group or group.state == "notInWar": return {"status": "notInWar", "message": "Clã não está em CWL."}
        rounds_data = []
        for i, round_war_tags in enumerate(group.rounds):
            round_info = {"round_number": i + 1, "wars": []}
            for war_tag in round_war_tags:
                try:
                    war: LeagueWar = await group.get_league_war(war_tag)
                    if not war: continue
                    our_clan_is_clan1 = war.clan.tag == CLAN_TAG
                    clan1_data, clan2_data = (war.clan, war.opponent) if our_clan_is_clan1 else (war.opponent, war.clan)
                    round_info["wars"].append({
                        "war_tag": war_tag, "state": war.state,
                        "clan1_name": clan1_data.name, "clan1_tag": clan1_data.tag, "clan1_stars": clan1_data.stars, "clan1_destruction": f"{clan1_data.destruction:.2f}%", "clan1_badge_url": getattr(clan1_data.badge, 'url', None),
                        "clan2_name": clan2_data.name, "clan2_tag": clan2_data.tag, "clan2_stars": clan2_data.stars, "clan2_destruction": f"{clan2_data.destruction:.2f}%", "clan2_badge_url": getattr(clan2_data.badge, 'url', None),
                        "end_time_str": pytz.utc.localize(war.end_time.time).astimezone(TIMEZONE).strftime('%d/%m %H:%M') if war.end_time and hasattr(war.end_time, 'time') else "N/A"
                    })
                except Exception as e_war: logger.warning(f"Erro CWL war {war_tag}: {e_war}"); round_info["wars"].append({"war_tag": war_tag, "error": "Erro."})
            rounds_data.append(round_info)
        clan_list_data = []
        if hasattr(group, 'clans') and group.clans:
            clan_list_data = [{"name": c.name, "tag": c.tag, "level": c.level, "badge_url": c.badge.url if hasattr(c, 'badge') and c.badge else None} for c in group.clans]
        return { "status": group.state, "season": group.season, "rounds": rounds_data, "clans": clan_list_data }
    except coc.NotFound: return {"status": "notInWar", "message": "Clã não em CWL."}
    except Exception as e: return {"error": str(e)}

async def api_clan_info_handler(request): data = await get_cached_web_data(f"web_clan_info_{CLAN_TAG}", fetch_clan_info_for_web_api); return web.json_response(data)
async def api_members_handler(request): data = await get_cached_web_data(f"web_clan_members_{CLAN_TAG}", fetch_clan_members_for_web_api); return web.json_response(data)
async def api_war_status_handler(request): data = await get_cached_web_data(f"web_war_status_{CLAN_TAG}", fetch_war_status_for_web_api, _cache_duration=15); return web.json_response(data)
async def api_player_details_handler(request):
    player_tag = request.match_info.get('player_tag', None)
    if not player_tag: return web.json_response({"error": "Tag não especificada."}, status=400)
    player_tag_cleaned = f"#{player_tag.lstrip('#')}"
    data = await get_cached_web_data(f"web_player_{player_tag_cleaned}", fetch_player_details_for_web_api, player_tag=player_tag_cleaned, _cache_duration=120)
    return web.json_response(data)
async def api_clan_events_log_handler(request): data = await fetch_clan_events_log_for_web_api(); return web.json_response(data)
async def api_cwl_info_handler(request): data = await get_cached_web_data(f"web_cwl_info_{CLAN_TAG}", fetch_cwl_info_for_web_api, _cache_duration=300); return web.json_response(data)
async def handle_panel_index(request):
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    index_path = os.path.join(static_dir, "painel.html")
    try: return web.FileResponse(index_path)
    except FileNotFoundError: return web.Response(text="Painel não encontrado (painel.html).", status=404)
    except Exception: return web.Response(text="Erro ao carregar painel.", status=500)

async def setup_web_server():
    app = web.Application()
    async def health(request): return web.Response(text=f"Bot running! Web panel active. v{BOT_VERSION}")
    app.router.add_get("/api/clan", api_clan_info_handler); app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/war", api_war_status_handler); app.router.add_get("/api/player/{player_tag}", api_player_details_handler)
    app.router.add_get("/api/events", api_clan_events_log_handler); app.router.add_get("/api/cwl", api_cwl_info_handler)
    app.router.add_get("/painel", handle_panel_index)
    static_path = os.path.join(os.path.dirname(__file__), "static"); os.makedirs(static_path, exist_ok=True)
    app.router.add_static('/static/', path=static_path, name='static', show_index=False)
    app.router.add_get("/", health)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
    try: await site.start(); logger.info(f"Servidor web iniciado na porta {site.name.split(':')[-1]}"); return runner
    except Exception as e: logger.error(f"Falha ao iniciar servidor web: {e}", exc_info=True); return None

async def setup_hook():
    logger.info("Executando setup_hook...")
    logger.info("Inicializando cliente CoC...")
    bot.coc_client = coc.EventsClient()
    max_retries, retry_delay, login_success = 3, 5, False
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentativa login CoC ({attempt + 1}/{max_retries})...")
            if not COC_EMAIL or not COC_PASSWORD: logger.error("COC_EMAIL/PASSWORD não definidos."); break
            await bot.coc_client.login(COC_EMAIL, COC_PASSWORD)
            logger.info("Login CoC bem-sucedido!"); login_success = True; break
        except coc.InvalidCredentials as e: logger.error(f"Login CoC Falhou: Credenciais Inválidas. {e}"); break
        except coc.Maintenance as e: logger.warning(f"API CoC em manutenção: {e}."); break
        except asyncio.TimeoutError: logger.error(f"Timeout login CoC ({attempt + 1})."); await asyncio.sleep(retry_delay)
        except Exception as e: logger.error(f"Erro login CoC ({attempt + 1}): {e}", exc_info=True); await asyncio.sleep(retry_delay)
    if login_success:
        logger.info("Registrando listeners CoC..."); await register_coc_events(bot.coc_client)
        if CLAN_TAG:
            try: bot.coc_client.add_clan_updates(CLAN_TAG); bot.coc_client.add_war_updates(CLAN_TAG); logger.info(f"Updates CoC ativados para {CLAN_TAG}.")
            except Exception as e: logger.error(f"Erro ao add updates CoC: {e}")
    else: logger.error("Não foi possível logar no CoC.")
    logger.info("Configurando servidor web..."); bot.web_runner = await setup_web_server()
    if not bot.web_runner: logger.warning("Falha config servidor web.")
    logger.info("Sincronizando comandos de app..."); synced_cmds = []
    try:
        if TEST_GUILD_ID:
            try: guild_obj = discord.Object(id=int(TEST_GUILD_ID)); bot.tree.copy_global_to(guild=guild_obj); synced_cmds = await bot.tree.sync(guild=guild_obj)
            except: logger.error(f"TEST_GUILD_ID inválido. Sincronizando globalmente..."); synced_cmds = await bot.tree.sync()
        else: synced_cmds = await bot.tree.sync()
        logger.info(f"{len(synced_cmds)} comandos (/) sincronizados.")
    except Exception as e: logger.error(f"Erro ao sincronizar comandos: {e}", exc_info=True)
    logger.info("setup_hook concluído.")

async def main():
    bot.setup_hook = setup_hook
    async with bot:
        try:
            if not DISCORD_TOKEN: logger.critical("DISCORD_TOKEN não encontrado."); return
            logger.info("Iniciando bot Discord..."); await bot.start(DISCORD_TOKEN)
        except discord.LoginFailure: logger.critical("Login Discord Falhou: Token inválido.")
        except discord.PrivilegedIntentsRequired: logger.critical(f"Intents Privilegiadas não habilitadas.")
        except Exception as e: logger.critical(f"Erro crítico no bot: {e}", exc_info=True)
        finally:
            logger.info("Desligando bot...")
            if 'check_war_end_report_task' in globals() and check_war_end_report_task.is_running(): check_war_end_report_task.cancel()
            if hasattr(bot, "web_runner") and bot.web_runner: await bot.web_runner.cleanup()
            if hasattr(bot, "coc_client") and bot.coc_client.http and not bot.coc_client.http.closed: await bot.coc_client.close()
            logger.info("Bot desligado.")

def handle_asyncio_exception(loop, context):
    msg = context.get("exception", context["message"])
    logger.error(f"Erro não tratado no loop asyncio: {msg}", exc_info=context.get('exception'))

if __name__ == "__main__":
    required = ["DISCORD_TOKEN", "COC_EMAIL", "COC_PASSWORD", "CLAN_TAG", "CHANNEL_ID"]
    if any(not os.getenv(v) for v in required):
         logger.critical(f"Variáveis de ambiente faltando: {', '.join(v for v in required if not os.getenv(v))}.")
    else:
        loop = asyncio.get_event_loop()
        try: loop.set_exception_handler(handle_asyncio_exception); loop.run_until_complete(main())
        except KeyboardInterrupt: logger.info("Bot interrompido.")
        except RuntimeError as e:
             if "Event loop is closed" not in str(e): logger.warning(f"RuntimeError: {e}", exc_info=True)
        finally:
            if loop.is_running(): loop.stop()
            if not loop.is_closed():
                pending_tasks = [t for t in asyncio.all_tasks(loop=loop) if t is not asyncio.current_task(loop=loop)]
                if pending_tasks:
                    logger.info(f"Cancelando {len(pending_tasks)} tarefas pendentes...")
                    for task in pending_tasks: task.cancel()
                    loop.run_until_complete(asyncio.gather(*pending_tasks, return_exceptions=True))
                loop.close()
            logger.info("Programa finalizado.")
