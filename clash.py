# -*- coding: utf-8 -*-
# Versão 17.2 -

import os
import logging
import asyncio
import datetime
# import aiohttp # <- Linha original comentada/removida
from aiohttp import web # <- Nova linha para importar 'web' diretamente
from typing import Dict, List, Optional, Union, Set # Union é usado em outros lugares, mantenha o import geral
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
# Import specific types if needed, helps with clarity and potential future refactoring
from coc import ClanWar, Player, Clan, WarAttack, Timestamp, ClanMember # Explicit imports for clarity
import pytz
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'), # Specify encoding
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
# Ensure CHANNEL_ID is loaded as int, handle potential errors
try:
    # Use os.environ.get to avoid KeyError if not set, handle None
    channel_id_str = os.environ.get("CHANNEL_ID")
    if channel_id_str:
        CHANNEL_ID = int(channel_id_str)
    else:
        CHANNEL_ID = 0 # Default or indicate error
        logger.error("CHANNEL_ID não definido no .env. Usando 0 como padrão.")
except (TypeError, ValueError):
    logger.error(f"CHANNEL_ID ('{channel_id_str}') inválido no .env. Usando 0 como padrão.")
    CHANNEL_ID = 0 # Provide a default or handle error appropriately

ROLE_ID_1STAR_ALERT = os.getenv("ROLE_ID_1STAR_ALERT")
ROLE_ID_MISSED_ATTACK = os.getenv("ROLE_ID_MISSED_ATTACK")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

# Set timezone
try:
    TIMEZONE = pytz.timezone('America/Sao_Paulo')
except pytz.UnknownTimeZoneError:
    logger.error("Timezone 'America/Sao_Paulo' desconhecida. Usando UTC como padrão.")
    TIMEZONE = pytz.utc

# Bot version
BOT_VERSION = "17.2"

# Cache for reported war ends (using war end time ISO string as key)
reported_war_ends: Set[str] = set()

# Intents configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Initialize bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Helper functions
async def get_clan_data(tag: str) -> Clan: # Use explicit type
    """Fetch clan data with error handling."""
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

async def get_player_data(tag: str) -> Player: # Use explicit type
    """Fetch player data with error handling."""
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        if not tag.startswith("#"):
            tag = f"#{tag}"
        return await bot.coc_client.get_player(tag)
    except coc.NotFound:
        raise ValueError(f"Jogador com tag {tag} não encontrado.")
    except coc.Maintenance:
        raise ValueError("API do CoC está em manutenção. Tente novamente mais tarde.")
    except asyncio.TimeoutError:
        raise ValueError("Tempo limite excedido ao buscar dados do jogador. Tente novamente.")
    except coc.InvalidCredentials:
        raise ValueError("Credenciais inválidas para a API do CoC detectadas.")
    except coc.Forbidden:
        raise ValueError("Acesso proibido à API do CoC (Forbidden). Verifique permissões da chave API.")
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar dados do jogador {tag}: {e}", exc_info=True)
        raise ValueError(f"Erro inesperado ao buscar dados do jogador: {str(e)}")

# Cache for clan data
clan_cache: Dict[str, Dict] = {}
CACHE_DURATION_SECONDS = 300 # 5 minutes

async def get_clan_data_with_cache(tag: str) -> Clan: # Use explicit type
    """Get clan data with caching."""
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

    # Fetch new data if not in cache or expired
    logger.debug(f"Buscando novos dados para clã {tag}")
    clan = await get_clan_data(tag) # Uses the helper with error handling
    clan_cache[tag] = {
        "data": clan,
        "timestamp": now
    }
    return clan

async def fetch_location_id(location_name: str) -> int:
    """Fetch location ID from location name."""
    if not bot.coc_client or not bot.coc_client.http:
         raise ValueError("Cliente CoC não inicializado ou não logado.")
    try:
        locations = await bot.coc_client.search_locations(name=location_name, limit=1)
        if not locations:
            raise ValueError(f"Localização '{location_name}' não encontrada.")
        # Ensure location object and id attribute exist
        loc_obj = locations[0]
        if hasattr(loc_obj, 'id'):
            return loc_obj.id
        else:
            raise ValueError(f"Objeto de localização para '{location_name}' não possui ID.")
    except Exception as e:
        logger.error(f"Erro ao buscar ID da localização '{location_name}': {e}", exc_info=True)
        raise ValueError(f"Erro ao buscar ID da localização: {str(e)}")

async def send_log_embed(embed: discord.Embed, content: str = None) -> None:
    """Send embed with standard footer to log channel."""
    if not CHANNEL_ID or CHANNEL_ID == 0:
         logger.warning("CHANNEL_ID não configurado. Não é possível enviar embed de log.")
         return

    # Add standard footer if not present
    # Check if footer exists and if its text attribute exists and is not empty
    if not hasattr(embed, 'footer') or not hasattr(embed.footer, 'text') or not embed.footer.text:
         embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")

    # Add timestamp if not present
    if not embed.timestamp:
        embed.timestamp = datetime.datetime.now(TIMEZONE)

    try:
        # Use fetch_channel for robustness, especially after potential disconnects
        channel = await bot.fetch_channel(CHANNEL_ID)
        if isinstance(channel, discord.TextChannel): # Check if it's a text channel
            await channel.send(content=content, embed=embed)
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
    """Split a list of items into multiple embeds if necessary."""
    if not isinstance(channel, discord.TextChannel):
        logger.error("Canal inválido passado para send_embeds_splitted.")
        return

    if not items:
         # Send the base embed with a "not found" message if items list is empty
         embed = discord.Embed.from_dict(base_embed.to_dict()) # Create a copy
         embed.add_field(name=field_name, value="Nenhum item encontrado.", inline=False)
         if not hasattr(embed, 'footer') or not hasattr(embed.footer, 'text') or not embed.footer.text:
             embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
         if not embed.timestamp:
             embed.timestamp = datetime.datetime.now(TIMEZONE)
         try:
              await channel.send(embed=embed)
         except discord.Forbidden:
              logger.error(f"Sem permissão para enviar embed dividido (vazio) para o canal {channel.id}")
         except Exception as e:
              logger.error(f"Erro ao enviar embed dividido (vazio) para o canal {channel.id}: {e}", exc_info=True)
         return

    embeds_to_send = []
    current_embed = discord.Embed.from_dict(base_embed.to_dict())
    current_field_value = ""

    for item in items:
        item_line = item + "\n"
        # Check if adding this item exceeds field value limit OR embed total length limit
        # Use len(embed) check for overall length safety
        if (len(current_field_value) + len(item_line) > 1024 or
            len(current_embed) + len(item_line) > 5900): # Use 5900 for safety margin

            # Add the current field value if it's not empty
            if current_field_value:
                # Ensure field name is not empty
                safe_field_name = field_name if field_name else "Dados"
                current_embed.add_field(name=safe_field_name, value=current_field_value, inline=False)

            # Add the completed embed to the list only if it has fields
            if current_embed.fields:
                 embeds_to_send.append(current_embed)

            # Start a new embed based on the base
            current_embed = discord.Embed.from_dict(base_embed.to_dict())
            # Start the new field value with the current item
            current_field_value = item_line

            # Check if the single item itself is too long
            if len(current_field_value) > 1024:
                 logger.warning(f"Item individual muito longo para campo de embed: {item[:50]}...")
                 # Truncate the item value
                 current_field_value = current_field_value[:1021] + "...\n"

        else:
            current_field_value += item_line

    # Add the last field and embed
    if current_field_value:
        safe_field_name = field_name if field_name else "Dados"
        current_embed.add_field(name=safe_field_name, value=current_field_value, inline=False)
    if current_embed.fields: # Only add if it has fields
         embeds_to_send.append(current_embed)


    # Add footers and timestamps to all embeds just before sending
    for embed_item in embeds_to_send: # Renomeado para evitar conflito com 'embed' no escopo externo
        if not hasattr(embed_item, 'footer') or not hasattr(embed_item.footer, 'text') or not embed_item.footer.text:
             embed_item.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
        if not embed_item.timestamp:
             embed_item.timestamp = datetime.datetime.now(TIMEZONE)

    # Send all embeds
    for embed_to_send in embeds_to_send: # Renomeado para evitar conflito
        try:
            await channel.send(embed=embed_to_send)
        except discord.Forbidden:
             logger.error(f"Sem permissão para enviar embed dividido para o canal {channel.id}")
             break # Stop trying if permission denied
        except Exception as e:
            logger.error(f"Erro ao enviar embed dividido para o canal {channel.id}: {e}", exc_info=True)


# --- Refactored display_attacks_remaining ---
async def format_attacks_remaining_embed(war: ClanWar) -> Optional[List[discord.Embed]]: # Use explicit type
    """Formats embeds for remaining attacks in a war."""
    # Check if essential war attributes exist
    if not all(hasattr(war, attr) for attr in ['state', 'opponent', 'clan', 'end_time', 'stars', 'destruction']):
         logger.error("Objeto 'war' inválido recebido por format_attacks_remaining_embed.")
         return None # Return None or an error embed

    # Handle opponent/clan potentially missing attributes safely
    opponent_name = getattr(war.opponent, 'name', 'Oponente Desconhecido')
    opponent_tag = getattr(war.opponent, 'tag', 'Tag Desconhecida')
    clan_name = getattr(war.clan, 'name', 'Clã Desconhecido')
    clan_badge_url = getattr(war.clan.badge, 'url', None) if hasattr(war.clan, 'badge') else None
    opponent_stars = getattr(war.opponent, 'stars', 0)
    opponent_destruction = getattr(war.opponent, 'destruction', 0.0)

    if war.state != "inWar":
        # Return a single embed indicating not in war
        embed_msg = discord.Embed( # Renomeado para evitar conflito
            title=f"⚔️ Guerra Não Ativa",
            description=f"A guerra contra **{opponent_name}** ({opponent_tag}) não está em andamento (Estado: {war.state}).",
            color=discord.Color.orange()
        )
        if clan_badge_url: embed_msg.set_thumbnail(url=clan_badge_url)
        embed_msg.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        embed_msg.timestamp = datetime.datetime.now(TIMEZONE)
        return [embed_msg]

    # Calculate time remaining safely
    try:
         time_now = datetime.datetime.now(TIMEZONE)
         # Ensure end_time is timezone-aware for comparison
         end_time_aware = war.end_time.astimezone(TIMEZONE) # Correção: chamada direta
         time_delta = end_time_aware - time_now
         if time_delta.total_seconds() < 0:
              time_remaining = "Finalizada" # War ended but state not updated?
         else:
             days = time_delta.days
             secs = time_delta.seconds
             hours, rem = divmod(secs, 3600)
             mins, secs_rem = divmod(rem, 60) # secs_rem para evitar conflito
             time_remaining = f"{days}d {hours}h {mins}m" if days > 0 else f"{hours}h {mins}m {int(secs_rem)}s" # Cast secs to int

         end_time_local = end_time_aware.strftime('%d/%m %H:%M')
    except Exception as e:
         logger.error(f"Erro ao calcular tempo restante da guerra: {e}")
         time_remaining = "Erro"
         end_time_local = "Erro"


    # Prepare the remaining attacks list
    members_with_attacks = []
    # Determine attacks per member (1 for CWL, default 2 for regular)
    # Use attacks_per_member if available, default 2
    attack_count = getattr(war, 'attacks_per_member', 2)

    # Ensure members list exists
    if hasattr(war.clan, 'members') and war.clan.members:
         for member in war.clan.members:
            # Ensure member object and attacks attribute exist
            if not member or not hasattr(member, 'attacks'): continue
            attacks_used = len(member.attacks) if member.attacks else 0
            attacks_left = attack_count - attacks_used
            if attacks_left > 0:
                member_th = getattr(member, 'town_hall', '?')
                member_name = getattr(member, 'name', 'Membro Desconhecido')
                members_with_attacks.append(f"**{member_name}** (CV{member_th}) - {attacks_left} {'ataques' if attacks_left > 1 else 'ataque'} restante{'s' if attacks_left > 1 else ''}")
    else:
         logger.warning("Lista de membros não encontrada no objeto 'war.clan' para format_attacks_remaining_embed.")


    # Create the base embed
    base_embed_attacks = discord.Embed( # Renomeado
        title=f"🗡️ Ataques Restantes - {clan_name} vs {opponent_name}",
        description=f"**Placar:** {war.clan.stars}⭐ ({war.clan.destruction:.2f}%) vs {opponent_stars}⭐ ({opponent_destruction:.2f}%)\n"
                    f"**Fim:** {end_time_local} ({time_remaining} restantes)",
        color=discord.Color.blue()
    )
    if clan_badge_url: base_embed_attacks.set_thumbnail(url=clan_badge_url)


    # Use send_embeds_splitted logic internally to generate embeds
    embeds_to_send_attacks = [] # Renomeado
    field_name_attacks = "Membros com Ataques Pendentes" # Renomeado
    if not members_with_attacks:
         embed_single = discord.Embed.from_dict(base_embed_attacks.to_dict()) # Renomeado
         embed_single.add_field(name=field_name_attacks, value="✅ Todos os ataques já foram utilizados!", inline=False)
         embeds_to_send_attacks.append(embed_single)
    else:
        # Simplified splitting logic for this specific case
        current_embed_attacks = discord.Embed.from_dict(base_embed_attacks.to_dict()) # Renomeado
        current_field_value_attacks = "" # Renomeado
        for item in members_with_attacks:
            item_line = item + "\n"
            if len(current_field_value_attacks) + len(item_line) > 1024:
                if current_field_value_attacks:
                    current_embed_attacks.add_field(name=field_name_attacks, value=current_field_value_attacks, inline=False)
                # Add completed embed only if it has fields (prevent empty base embed)
                if current_embed_attacks.fields:
                    embeds_to_send_attacks.append(current_embed_attacks)
                # Start new embed
                current_embed_attacks = discord.Embed.from_dict(base_embed_attacks.to_dict())
                current_field_value_attacks = item_line
                # Handle item too long (though unlikely here)
                if len(current_field_value_attacks) > 1024:
                    current_field_value_attacks = current_field_value_attacks[:1021] + "...\n"
            else:
                current_field_value_attacks += item_line

        # Add the last field and embed
        if current_field_value_attacks:
            current_embed_attacks.add_field(name=field_name_attacks, value=current_field_value_attacks, inline=False)
        if current_embed_attacks.fields: # Ensure the last embed has fields
            embeds_to_send_attacks.append(current_embed_attacks)

    # Add footers and timestamps
    for embed_item in embeds_to_send_attacks:
        if not hasattr(embed_item, 'footer') or not hasattr(embed_item.footer, 'text') or not embed_item.footer.text:
             embed_item.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        if not embed_item.timestamp:
             embed_item.timestamp = datetime.datetime.now(TIMEZONE)

    return embeds_to_send_attacks if embeds_to_send_attacks else None # Return None if something went wrong

# --- End refactored display_attacks_remaining ---

# ========================================================================================= #
# =============================  INÍCIO DA SEÇÃO MODIFICADA  ============================= #
# ========================================================================================= #
async def send_missed_attacks_report(war: ClanWar,
                                    missed_members_details: List[str],
                                    war_type: str) -> None:
    """Send a report of missed attacks using formatted details."""
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

    # --- CORREÇÃO APLICADA AQUI ---
    start_time_local_str = "N/A"
    end_time_local_str = "N/A"

    if hasattr(war, 'start_time') and isinstance(war.start_time, Timestamp):
        try:
            # Correção: Chamada direta ao astimezone
            start_time_aware = war.start_time.astimezone(TIMEZONE)
            start_time_local_str = start_time_aware.strftime('%d/%m/%Y %H:%M')
        except Exception as e:
            logger.error(f"Erro ao formatar start_time para relatório de ataques perdidos: {e}", exc_info=True) # Adicionado exc_info
            start_time_local_str = "Erro na data"

    if hasattr(war, 'end_time') and isinstance(war.end_time, Timestamp):
        try:
            # Correção: Chamada direta ao astimezone
            end_time_aware = war.end_time.astimezone(TIMEZONE)
            end_time_local_str = end_time_aware.strftime('%d/%m/%Y %H:%M')
        except Exception as e:
            logger.error(f"Erro ao formatar end_time para relatório de ataques perdidos: {e}", exc_info=True) # Adicionado exc_info
            end_time_local_str = "Erro na data"
    # --- FIM DA CORREÇÃO ---

    description_text = (
        f"Membros que não usaram todos os ataques contra **{opponent_name}**.\n\n"
        f"**Data do Início da Guerra:** {start_time_local_str}\n"
        f"**Data do Fim da Guerra:** {end_time_local_str}"
    )

    base_embed_missed = discord.Embed( # Renomeado
        title=f"❌ Ataques Não Realizados - {war_type}",
        description=description_text,
        color=discord.Color.red()
    )
    if hasattr(war, 'opponent') and hasattr(war.opponent, 'badge') and war.opponent.badge:
         base_embed_missed.set_thumbnail(url=war.opponent.badge.url)

    try:
        channel_to_send = await bot.fetch_channel(CHANNEL_ID) # Renomeado
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
# ========================================================================================= #
# ==============================  FIM DA SEÇÃO MODIFICADA  =============================== #
# ========================================================================================= #

# <<< NOVA FUNÇÃO ADICIONADA >>>
async def send_online_status():
    """Envia uma mensagem de status online para o canal de log."""
    if not CHANNEL_ID or CHANNEL_ID == 0:
        logger.warning("CHANNEL_ID não configurado. Não é possível enviar status online.")
        return

    try:
        # Busca o clã principal para pegar o nome e tag
        clan_name = "Clã Desconhecido"
        clan_tag_formatted = CLAN_TAG if CLAN_TAG else "Nenhum"
        if CLAN_TAG and hasattr(bot, 'coc_client') and bot.coc_client.http: # Verifica se cliente coc está pronto
             try:
                  # Usa get_clan direto, pois o cache pode não estar populado no on_ready inicial
                  clan_data_status = await bot.coc_client.get_clan(CLAN_TAG) # Renomeado
                  clan_name = clan_data_status.name
                  clan_tag_formatted = clan_data_status.tag
             except Exception as e:
                  logger.error(f"Erro ao buscar dados do clã para status online: {e}")
                  # Continua com nome/tag padrão

        embed_online = discord.Embed( # Renomeado
            title="✅ Bot Online e Monitorando!",
            description=f"Eventos do clã **{clan_name}** (`{clan_tag_formatted}`) e Guerras monitorados.",
            color=discord.Color.green()
        )
        embed_online.add_field(name="Monitoramento", value="Event-Driven Ativo 🔄", inline=False)
        # Rodapé padrão será adicionado por send_log_embed
        await send_log_embed(embed_online)
        logger.info("Mensagem de status online enviada.")

    except Exception as e:
        logger.error(f"Erro ao enviar mensagem de status online: {e}", exc_info=True)

# Bot events
@bot.event
async def on_ready():
    """Handle bot ready event."""
    # Log basic info first
    logger.info(f"Bot {bot.user.name} (ID: {bot.user.id}) conectado ao Discord!")
    logger.info(f"Versão discord.py: {discord.__version__}")
    logger.info(f"Versão coc.py: {coc.__version__}")
    logger.info(f"Versão Bot: {BOT_VERSION}")
    logger.info(f"Pronto e operando em {len(bot.guilds)} servidor(es).")

    # Check CoC client status AFTER setup_hook should have run
    if hasattr(bot, 'coc_client') and bot.coc_client.http:
         logger.info("Cliente CoC parece estar pronto.")
         # Start background tasks if they aren't already running
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

    # A SINCRONIZAÇÃO DE COMANDOS FOI MOVIDA PARA O setup_hook() PARA MELHOR PRÁTICA.

    # <<< NOVO: Envia status online >>>
    await send_online_status()

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handle app command errors."""
    command_name = interaction.command.qualified_name if interaction.command else 'Comando Desconhecido'
    error_embed_cmd = discord.Embed( # Renomeado
        title="❌ Erro de Comando",
        color=discord.Color.red()
    )
    error_message = f"Ocorreu um erro inesperado: {str(error)}" # Default message

    # More specific error handling
    original_error = getattr(error, 'original', error) # Get original error if wrapped

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
        # Log the full traceback for unexpected internal errors
        error_message = f"Ocorreu um erro interno ao processar o comando."
        logger.error(f"Erro não tratado no comando '{command_name}': {original_error}", exc_info=original_error)


    error_embed_cmd.description = error_message
    error_embed_cmd.set_footer(text=f"Comando: /{command_name}")
    error_embed_cmd.timestamp = datetime.datetime.now(TIMEZONE)

    try:
        # Use followup if already responded (e.g., deferred), otherwise send initial response
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

# CoC event handlers
async def register_coc_events(coc_client: coc.EventsClient):
    """Register event handlers for the CoC client."""
    if not CLAN_TAG:
         logger.warning("CLAN_TAG não definido, eventos do clã não serão registrados.")
         return

    logger.info(f"Registrando manipuladores de eventos CoC para o clã {CLAN_TAG}...")

    # --- Padronização: (old_member, member) ---
    @coc_client.event
    @coc.ClanEvents.member_join(tags=[CLAN_TAG])
    async def on_member_join(old_member: Optional[ClanMember], member: ClanMember): # old_member pode ser None
        # <<< NOVO LOG >>>
        logger.info(f"EVENTO DETECTADO: on_member_join para {getattr(member, 'tag', 'TAG DESCONHECIDA')}")
        """Handle member join event."""
        if not member or not hasattr(member, 'clan'):
             logger.warning("Evento member_join recebido com objeto 'member' inválido ou sem clã.")
             return
        clan_obj_join = member.clan # Renomeado
        logger.info(f"Evento: {member.name} ({member.tag}) entrou no clã {clan_obj_join.name}.")
        embed_join = discord.Embed( # Renomeado
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
    async def on_member_leave(old_member: ClanMember, member: ClanMember): # member é o estado 'após', old_member é o estado 'antes'
        # Usa old_member para obter a tag do membro para o log inicial
        logger.info(f"EVENTO DETECTADO: on_member_leave para {getattr(old_member, 'tag', 'TAG DESCONHECIDA DO MEMBRO QUE SAIU')}")
        """Handle member leave event."""

        if not old_member:
            logger.warning("Evento member_leave: 'old_member' (estado anterior do membro) não fornecido. Não é possível obter detalhes do membro que saiu.")
            return

        # O clã de onde o membro saiu é obtido de old_member.clan
        clan_obj_leave = old_member.clan if hasattr(old_member, 'clan') else None # Renomeado
        clan_name_leave = getattr(clan_obj_leave, 'name', 'Clã Desconhecido') # Renomeado

        leaving_member_name = getattr(old_member, 'name', 'Membro Desconhecido')
        leaving_member_tag = getattr(old_member, 'tag', 'Tag Desconhecida')
        leaving_member_town_hall = getattr(old_member, 'town_hall', '?')
        leaving_member_exp_level = getattr(old_member, 'exp_level', '?')
        leaving_member_trophies = getattr(old_member, 'trophies', '?')
        leaving_member_league = getattr(old_member, 'league', None)
        league_name_leave = getattr(leaving_member_league, 'name', 'Sem Liga') if leaving_member_league else 'Sem Liga' # Renomeado

        logger.info(f"Evento: {leaving_member_name} ({leaving_member_tag}) saiu do clã {clan_name_leave}.")

        embed_leave = discord.Embed( # Renomeado
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
        """Handle member donations event."""
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan_obj_don = member.clan # Renomeado
        old_donations = getattr(old_member, 'donations', 0)
        new_donations = getattr(member, 'donations', 0)
        donation_difference = new_donations - old_donations
        if donation_difference <= 0: return
        logger.info(f"Evento: {member.name} doou {donation_difference} tropas (Total: {new_donations}).")
        embed_don = discord.Embed(color=discord.Color.green()) # Renomeado
        if hasattr(clan_obj_don, 'badge') and clan_obj_don.badge:
             embed_don.set_author(name=clan_obj_don.name, icon_url=clan_obj_don.badge.url)
             embed_don.set_thumbnail(url=clan_obj_don.badge.url)
        embed_don.add_field(name="🎁 Doação",
                         value=f"**{donation_difference}** tropas por `{member.name}` (Total doado: {new_donations})", inline=False)
        await send_log_embed(embed_don)

    @coc_client.event
    @coc.ClanEvents.member_received(tags=[CLAN_TAG])
    async def on_member_received(old_member: ClanMember, member: ClanMember):
        """Handle member received donations event."""
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan_obj_rec = member.clan # Renomeado
        old_received = getattr(old_member, 'received', 0)
        new_received = getattr(member, 'received', 0)
        received_difference = new_received - old_received
        if received_difference <= 0: return
        logger.info(f"Evento: {member.name} recebeu {received_difference} tropas (Total: {new_received}).")
        embed_rec = discord.Embed(color=discord.Color.blue()) # Renomeado
        if hasattr(clan_obj_rec, 'badge') and clan_obj_rec.badge:
            embed_rec.set_author(name=clan_obj_rec.name, icon_url=clan_obj_rec.badge.url)
            embed_rec.set_thumbnail(url=clan_obj_rec.badge.url)
        embed_rec.add_field(name="📥 Recebimento",
                         value=f"`{member.name}` recebeu **{received_difference}** tropas (Total recebido: {new_received})", inline=False)
        await send_log_embed(embed_rec)

    @coc_client.event
    @coc.ClanEvents.member_role_change(tags=[CLAN_TAG])
    async def on_member_role_change(old_member: ClanMember, member: ClanMember):
        # <<< NOVO LOG >>>
        logger.info(f"EVENTO DETECTADO: on_member_role_change para {getattr(member, 'tag', 'TAG DESCONHECIDA')}")
        """Handle member role change event."""
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan_obj_role = member.clan # Renomeado
        old_role = getattr(old_member, 'role', None)
        new_role = getattr(member, 'role', None)
        if old_role == new_role: return
        logger.info(f"Evento: Cargo de {member.name} mudou de {old_role} para {new_role} em {clan_obj_role.name}.")
        embed_role = discord.Embed( # Renomeado
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
        """Handle member league change event."""
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan_obj_league = member.clan # Renomeado
        old_league = getattr(old_member, 'league', None)
        new_league = getattr(member, 'league', None)
        if old_league == new_league: return
        logger.info(f"Evento: Liga de {member.name} mudou de {old_league} para {new_league} em {clan_obj_league.name}.")
        old_league_name = old_league.name if old_league else "Sem Liga"
        new_league_name = new_league.name if new_league else "Sem Liga"
        embed_league = discord.Embed( # Renomeado
            title="🏆 Mudança de Liga",
            description=f"Liga de **{member.name}** (`{member.tag}`) foi alterada!",
            color=discord.Color.purple()
        )
        embed_league.add_field(name="Liga Anterior", value=old_league_name, inline=True)
        embed_league.add_field(name="Nova Liga", value=new_league_name, inline=True)
        if hasattr(clan_obj_league, 'badge') and clan_obj_league.badge:
             embed_league.set_author(name=clan_obj_league.name, icon_url=clan_obj_league.badge.url)
             embed_league.set_thumbnail(url=clan_obj_league.badge.url)
        await send_log_embed(embed_league)


    # --- Evento de Troféus ---
    # Usando (old_member, member) como os outros para padronizar
    @coc_client.event
    @coc.ClanEvents.member_trophies_change(tags=[CLAN_TAG])
    async def on_member_trophies_change(old_member: ClanMember, member: ClanMember):
        """Handle member trophies change event."""
        if not member or not old_member:
             logger.warning("Evento member_trophies_change recebido com objeto 'member' ou 'old_member' inválido.")
             return

        # Calcula a diferença
        old_trophies = getattr(old_member, 'trophies', 0)
        new_trophies = getattr(member, 'trophies', 0)
        trophy_difference = new_trophies - old_trophies

        if abs(trophy_difference) < 5: return
        logger.info(f"Evento: Troféus de {member.name} mudaram em {trophy_difference} (Total: {new_trophies}).")
        direction = "ganhou" if trophy_difference > 0 else "perdeu"
        embed_trophies = discord.Embed( # Renomeado
            description=f"**{member.name}** {direction} **{abs(trophy_difference)}** troféus (Total: {new_trophies})",
            color=discord.Color.green() if trophy_difference > 0 else discord.Color.dark_red()
        )
        await send_log_embed(embed_trophies)


    # --- War Attack Event (assinatura parece correta) ---
    @coc_client.event
    @coc.WarEvents.war_attack(tags=[CLAN_TAG])
    async def on_war_attack(attack: WarAttack, war: ClanWar):
        """Handle war attack event."""
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
             return # Cannot determine context if player fetch fails unexpectedly

        # Check involvement only if tags were determined
        if attacker_clan_tag is not None and attacker_clan_tag == CLAN_TAG:
             is_our_attack = True
        elif defender_clan_tag is not None and defender_clan_tag == CLAN_TAG:
             is_our_defense = True
        # If tags are still None after trying to fetch, cannot determine side reliably
        elif attacker_clan_tag is None or defender_clan_tag is None:
             logger.warning(f"Não foi possível determinar clãs do atacante/defensor para ataque {attack.order} após tentativa de fetch.")
             # Avoid making assumptions and skip this attack event
             return
        else:
             logger.debug(f"Ataque de guerra ({attack.order}) não envolve o clã {CLAN_TAG}. Attacker: {attacker_clan_tag}, Defender: {defender_clan_tag}")
             return

        # Get player details (use fetched data or fallback to tags)
        attacker_name = getattr(attacker_player, 'name', attack.attacker_tag) if attacker_player else attack.attacker_tag
        defender_name = getattr(defender_player, 'name', attack.defender_tag) if defender_player else attack.defender_tag
        attacker_th = getattr(attacker_player, 'town_hall', '?') if attacker_player else '?'
        defender_th = getattr(defender_player, 'town_hall', '?') if defender_player else '?'

        stars_str = "⭐" * attack.stars + "⚫" * (3 - attack.stars)
        content_attack = None # Renomeado

        if is_our_attack:
            logger.info(f"Evento Guerra: {attacker_name} atacou {defender_name} - {attack.stars} estrelas, {attack.destruction}% destruição.")
            embed_attack = discord.Embed( # Renomeado
                title=f"⚔️ Ataque Realizado (Guerra)",
                description=f"**{attacker_name}** (CV{attacker_th}) atacou **{defender_name}** (CV{defender_th})",
                color=discord.Color.blue()
            )
            embed_attack.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
            
            if attack.stars <= 1 and ROLE_ID_1STAR_ALERT:
                try:
                    log_channel_attack = await bot.fetch_channel(CHANNEL_ID) # Renomeado
                    if log_channel_attack and hasattr(log_channel_attack, 'guild'):
                         guild_attack = log_channel_attack.guild # Renomeado
                         try:
                              role_id_int_attack = int(ROLE_ID_1STAR_ALERT) # Renomeado
                              role_attack = guild_attack.get_role(role_id_int_attack) # Renomeado
                              if role_attack: content_attack = f"{role_attack.mention} ⚠️ Atenção: ataque fora do padrão detectado!"
                              else: logger.warning(f"Cargo para alerta de 1 estrela (ID: {ROLE_ID_1STAR_ALERT}) não encontrado.")
                         except (ValueError, TypeError): logger.error(f"ROLE_ID_1STAR_ALERT ('{ROLE_ID_1STAR_ALERT}') é inválido.")
                    else: logger.warning("Não foi possível buscar o servidor do canal de log para alerta de 1 estrela.")
                except Exception as e: logger.error(f"Erro ao buscar cargo para alerta de 1 estrela: {e}", exc_info=True)

            # Use war.clan badge for our attacks
            if hasattr(war, 'clan') and hasattr(war.clan, 'badge') and war.clan.badge:
                 embed_attack.set_author(name=war.clan.name, icon_url=war.clan.badge.url)
                 embed_attack.set_thumbnail(url=war.clan.badge.url)
            await send_log_embed(embed_attack, content_attack)

        elif is_our_defense:
            logger.info(f"Evento Guerra: {defender_name} foi atacado por {attacker_name} - {attack.stars} estrelas, {attack.destruction}% destruição.")
            embed_defense = discord.Embed( # Renomeado
                title=f"🛡️ Defesa Recebida (Guerra)",
                description=f"**{defender_name}** (CV{defender_th}) foi atacado por **{attacker_name}** (CV{attacker_th})",
                color=discord.Color.orange()
            )
            embed_defense.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
             # Use war.opponent badge for defense log (assuming opponent is attacker's clan)
            if hasattr(war, 'opponent') and hasattr(war.opponent, 'badge') and war.opponent.badge:
                 embed_defense.set_author(name=war.opponent.name, icon_url=war.opponent.badge.url)
                 embed_defense.set_thumbnail(url=war.opponent.badge.url)
            await send_log_embed(embed_defense)

    logger.info("Manipuladores de eventos CoC registrados.")

# Task loops
@tasks.loop(minutes=10)
async def check_war_end_report_task():
    """Task to check for ended wars and report missed attacks."""
    if not bot.coc_client or not bot.coc_client.http:
         logger.debug("check_war_end_report_task: Cliente CoC não pronto, pulando ciclo.")
         return # Don't run if CoC client isn't ready

    logger.debug("check_war_end_report_task: Iniciando verificação de fim de guerra...")
    processed_war_ids: Set[str] = set() # Track wars processed in this cycle

    async def process_war(war_obj: ClanWar, war_type_name: str): # Renomeado 'war' para 'war_obj'
        """Helper to process a single war (regular or CWL)."""
        # Use war end time ISO string as a unique ID
        war_id = war_obj.end_time.raw_time if hasattr(war_obj, 'end_time') and hasattr(war_obj.end_time, 'raw_time') else None

        if not war_obj or not war_id or war_id in processed_war_ids:
            if war_obj and war_id:
                 reason = "já processado neste ciclo" if war_id in processed_war_ids else "ID inválido"
                 logger.debug(f"Pulando processamento de guerra - {reason} (ID: {war_id})")
            elif not war_obj:
                 logger.debug("Pulando processamento de guerra - objeto 'war_obj' inválido.")
            return

        opponent_name_proc = getattr(getattr(war_obj, 'opponent', None), 'name', 'Oponente Desconhecido') # Renomeado
        war_state_proc = getattr(war_obj, 'state', 'unknown') # Renomeado
        logger.debug(f"Processando guerra: {war_type_name} contra {opponent_name_proc} (ID: {war_id}, Estado: {war_state_proc})")

        if war_state_proc == "warEnded" and war_id not in reported_war_ends:
            logger.info(f"Guerra '{war_type_name}' contra {opponent_name_proc} terminou (ID: {war_id}). Verificando ataques perdidos...")

            our_clan_obj = None
            attacks_per_member = 2 

            if "Liga de Clãs" in war_type_name:
                 attacks_per_member = 1 
                 war_clan_tag = getattr(getattr(war_obj, 'clan', None), 'tag', None)
                 war_opponent_tag = getattr(getattr(war_obj, 'opponent', None), 'tag', None)
                 if war_clan_tag == CLAN_TAG:
                     our_clan_obj = war_obj.clan
                 elif war_opponent_tag == CLAN_TAG:
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

            missed_members_details = []
            if hasattr(our_clan_obj, 'members') and our_clan_obj.members:
                 for member_proc in our_clan_obj.members: # Renomeado
                    if not member_proc or not hasattr(member_proc, 'tag'): continue

                    attacks_used = len(member_proc.attacks) if hasattr(member_proc, "attacks") and member_proc.attacks else 0
                    if attacks_used < attacks_per_member:
                        missed_count = attacks_per_member - attacks_used
                        member_name_proc = getattr(member_proc, 'name', member_proc.tag) # Renomeado
                        member_th_proc = getattr(member_proc, 'town_hall', '?') # Renomeado
                        missed_members_details.append(
                            f"**{member_name_proc}** (CV{member_th_proc}): {missed_count} perdido{'s' if missed_count > 1 else ''}"
                        )
            else:
                 logger.warning(f"Objeto do clã '{getattr(our_clan_obj, 'name', 'N/A')}' na guerra {war_id} não possui lista de membros.")


            if missed_members_details:
                logger.info(f"{len(missed_members_details)} membro(s) perderam ataques na guerra {war_type_name} (ID: {war_id}).")
                await send_missed_attacks_report(war_obj, missed_members_details, war_type_name) # Passa war_obj
            else:
                logger.info(f"Nenhum ataque perdido na guerra {war_type_name} (ID: {war_id}).")

            reported_war_ends.add(war_id) 
            processed_war_ids.add(war_id) 
            logger.debug(f"Guerra {war_id} marcada como reportada.")
        else:
             if war_state_proc != "warEnded":
                  logger.debug(f"Guerra {war_id} não está no estado 'warEnded' (Estado: {war_state_proc}).")
             elif war_id in reported_war_ends:
                  logger.debug(f"Guerra {war_id} já foi reportada anteriormente.")
             else:
                  logger.debug(f"Guerra {war_id} não processada por outra razão.")


    # --- Check Regular War ---
    try:
        logger.debug("Buscando guerra atual (regular)...")
        current_war_reg = await bot.coc_client.get_current_war(CLAN_TAG) # Renomeado
        if current_war_reg and hasattr(current_war_reg, 'state') and current_war_reg.state != "notInWar":
             if hasattr(current_war_reg, 'end_time'):
                  await process_war(current_war_reg, "Guerra Normal")
             else:
                  logger.warning("Objeto de guerra regular inválido (sem end_time).")
        elif current_war_reg and hasattr(current_war_reg, 'state'):
              logger.debug(f"Nenhuma guerra regular ativa ou terminada recentemente encontrada (Estado: {current_war_reg.state}).")
        else:
             logger.debug("Nenhuma guerra regular encontrada.")


    except coc.PrivateWarLog:
        logger.warning("Log de guerra regular é privado. Não é possível verificar automaticamente.")
    except coc.NotFound:
         logger.info("Clã não encontrado ao buscar guerra regular (possivelmente tag inválida?).")
    except Exception as e:
        logger.error(f"Erro ao buscar/processar guerra regular: {e}", exc_info=True)


    # --- Check CWL War ---
    try:
        logger.debug("Buscando grupo de liga (CWL)...")
        league_group_cwl = await bot.coc_client.get_league_group(CLAN_TAG) # Renomeado

        if league_group_cwl and hasattr(league_group_cwl, 'state') and league_group_cwl.state != "notInWar":
            logger.debug(f"Grupo de liga encontrado (Estado: {league_group_cwl.state}). Verificando rodadas...")
            if hasattr(league_group_cwl, 'rounds') and league_group_cwl.rounds:
                 for round_num, war_tags_cwl in reversed(list(enumerate(league_group_cwl.rounds))): # Renomeado
                     logger.debug(f"Processando rodada {round_num + 1} da CWL...")
                     for war_tag_cwl in war_tags_cwl: # Renomeado
                         try:
                             league_war_cwl = await league_group_cwl.get_league_war(war_tag_cwl) # Renomeado

                             if not league_war_cwl or not hasattr(league_war_cwl, 'state') or not hasattr(league_war_cwl, 'end_time'):
                                  logger.warning(f"Objeto da guerra da liga {war_tag_cwl} inválido ou incompleto.")
                                  continue

                             clan_tag_in_cwl = getattr(getattr(league_war_cwl, 'clan', None), 'tag', None) # Renomeado
                             opponent_tag_in_cwl = getattr(getattr(league_war_cwl, 'opponent', None), 'tag', None) # Renomeado

                             if CLAN_TAG == clan_tag_in_cwl or CLAN_TAG == opponent_tag_in_cwl:
                                 await process_war(league_war_cwl, f"Liga de Clãs (Rodada {round_num + 1})")

                         except coc.NotFound:
                              logger.warning(f"Guerra da liga com tag {war_tag_cwl} (Rodada {round_num + 1}) não encontrada.")
                         except Exception as e:
                              logger.error(f"Erro ao buscar/processar guerra da liga {war_tag_cwl} (Rodada {round_num + 1}): {e}", exc_info=True)
            else:
                 logger.debug("Grupo de liga não possui informações de rodadas ('rounds').")
        elif league_group_cwl and hasattr(league_group_cwl, 'state'):
             logger.debug(f"Nenhum grupo de liga ativo encontrado (Estado: {league_group_cwl.state}).")
        else:
             logger.debug("Nenhum grupo de liga ativo encontrado (objeto nulo ou sem estado).")


    except coc.NotFound:
         logger.info("Clã não encontrado ao buscar grupo de liga (possivelmente não em CWL ou tag inválida).")
    except Exception as e:
        logger.error(f"Erro ao buscar/processar grupo de liga (CWL): {e}", exc_info=True)

    logger.debug("check_war_end_report_task: Verificação de fim de guerra concluída.")


@check_war_end_report_task.before_loop
async def before_check_war():
    """Wait for the bot to be ready before starting the task."""
    logger.info("Aguardando o bot ficar pronto para iniciar a tarefa 'check_war_end_report_task'...")
    await bot.wait_until_ready()
    logger.info("Bot pronto. Tarefa 'check_war_end_report_task' pode iniciar.")

# Command groups setup
admin_group = app_commands.Group(name="admin", description="Comandos administrativos")
war_group = app_commands.Group(name="guerra", description="Comandos relacionados a guerras")
info_group = app_commands.Group(name="info", description="Comandos de informação")
search_group = app_commands.Group(name="buscar", description="Comandos de busca")
rank_group = app_commands.Group(name="rank", description="Comandos de ranking")

# Add command groups to the bot's command tree
bot.tree.add_command(admin_group)
bot.tree.add_command(war_group)
bot.tree.add_command(info_group)
bot.tree.add_command(search_group)
bot.tree.add_command(rank_group)

# Admin commands
@admin_group.command(name="ping", description="Verifica a latência do bot")
@app_commands.checks.has_permissions(administrator=True) # Restrict to admins
async def admin_ping(interaction: discord.Interaction):
    """Check bot latency."""
    latency_ms = round(bot.latency * 1000)
    embed_ping = discord.Embed( # Renomeado
        title="🏓 Pong!",
        description=f"Latência da API do Discord: **{latency_ms}ms**",
        color=discord.Color.green() if latency_ms < 200 else discord.Color.orange() if latency_ms < 500 else discord.Color.red()
    )
    embed_ping.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
    embed_ping.timestamp = datetime.datetime.now(TIMEZONE)
    await interaction.response.send_message(embed=embed_ping, ephemeral=True) # Ephemeral for admin command

# War commands continued
@war_group.command(name="ataques", description="Exibe os ataques restantes na guerra atual (Normal ou Liga)")
async def war_attacks(interaction: discord.Interaction):
    """Display remaining attacks in the current war (tries CWL first, then regular)."""
    await interaction.response.defer() # Defer response as it involves API calls

    current_war_cmd: Optional[ClanWar] = None # Renomeado
    war_type_name_cmd = "Guerra" # Renomeado

    # Try CWL first
    try:
        league_group_cmd = await bot.coc_client.get_league_group(CLAN_TAG) # Renomeado
        if league_group_cmd and getattr(league_group_cmd,'state',None) != "notInWar" and hasattr(league_group_cmd, 'rounds'):
            for round_num_cmd, war_tags_cmd in enumerate(league_group_cmd.rounds): # Renomeado
                 if current_war_cmd: break 
                 for war_tag_cmd in war_tags_cmd: # Renomeado
                     try:
                         league_war_cmd_obj = await league_group_cmd.get_league_war(war_tag_cmd) # Renomeado
                         clan_tag_in_war_cmd = getattr(getattr(league_war_cmd_obj, 'clan', None), 'tag', None) # Renomeado
                         opponent_tag_in_war_cmd = getattr(getattr(league_war_cmd_obj, 'opponent', None), 'tag', None) # Renomeado
                         war_state_cmd = getattr(league_war_cmd_obj, 'state', None) # Renomeado

                         if league_war_cmd_obj and (CLAN_TAG == clan_tag_in_war_cmd or CLAN_TAG == opponent_tag_in_war_cmd):
                              if war_state_cmd == "inWar":
                                   if CLAN_TAG == opponent_tag_in_war_cmd:
                                        try:
                                            temp_clan = league_war_cmd_obj.clan
                                            league_war_cmd_obj.clan = league_war_cmd_obj.opponent
                                            league_war_cmd_obj.opponent = temp_clan
                                        except Exception as swap_err:
                                            logger.error(f"Erro ao tentar trocar clan/opponent no objeto league_war_cmd_obj: {swap_err}")
                                   current_war_cmd = league_war_cmd_obj
                                   war_type_name_cmd = f"Liga de Clãs (Rodada {round_num_cmd + 1})"
                                   break 
                     except coc.NotFound:
                          continue 
                     except Exception as e:
                          logger.error(f"Erro ao buscar guerra da liga {war_tag_cmd} em /ataques: {e}")
                          continue 

    except coc.NotFound:
         logger.info("/ataques: Clã não encontrado ao buscar grupo de liga.")
    except Exception as e:
         logger.error(f"Erro ao buscar grupo de liga (CWL) em /ataques: {e}", exc_info=True)


    # If no active CWL war found, check regular war
    if not current_war_cmd:
         try:
             regular_war_cmd = await bot.coc_client.get_current_war(CLAN_TAG) # Renomeado
             if regular_war_cmd and getattr(regular_war_cmd, 'state', None) == "inWar":
                  current_war_cmd = regular_war_cmd
                  war_type_name_cmd = "Guerra Normal"
         except coc.PrivateWarLog:
              await interaction.followup.send("Log de guerra regular é privado. Não é possível verificar ataques.", ephemeral=True)
              return
         except coc.NotFound:
              logger.info("/ataques: Clã não encontrado ao buscar guerra regular.")
         except Exception as e:
              logger.error(f"Erro ao buscar guerra regular em /ataques: {e}", exc_info=True)
              await interaction.followup.send("Erro ao buscar informações da guerra regular.", ephemeral=True)
              return 

    if current_war_cmd:
         if isinstance(current_war_cmd, coc.ClanWar):
              embeds_list_cmd = await format_attacks_remaining_embed(current_war_cmd) # Renomeado
              if embeds_list_cmd:
                  first_embed_cmd = embeds_list_cmd.pop(0) # Renomeado
                  await interaction.followup.send(embed=first_embed_cmd)
                  for embed_item_cmd in embeds_list_cmd: # Renomeado
                      try:
                          if interaction.channel and isinstance(interaction.channel, discord.abc.Messageable):
                              await interaction.channel.send(embed=embed_item_cmd)
                          else:
                               logger.warning("interaction.channel não está acessível para enviar embeds adicionais.")
                               break
                      except Exception as e:
                          logger.error(f"Erro ao enviar embed adicional de /ataques: {e}")
                          break
              else:
                  await interaction.followup.send(f"Erro ao formatar informações de ataques para {war_type_name_cmd}.", ephemeral=True)
         else:
              logger.error(f"Objeto 'current_war_cmd' inválido ({type(current_war_cmd)}) passado para format_attacks_remaining_embed.")
              await interaction.followup.send(f"Erro interno ao processar dados da guerra ({war_type_name_cmd}).", ephemeral=True)

    else:
         await interaction.followup.send("O clã não está em nenhuma guerra ativa (Normal ou Liga) no momento.")


@war_group.command(name="status", description="Exibe o status da guerra atual (Normal ou Liga)")
async def war_status(interaction: discord.Interaction):
    """Display current war status (tries CWL first, then regular)."""
    await interaction.response.defer()

    war_to_display: Optional[ClanWar] = None 
    war_type_name_status = "Guerra" # Renomeado
    status_description = "Nenhuma guerra ativa ou recente encontrada." 
    status_color = discord.Color.greyple()

    # Try CWL first
    try:
        league_group_status = await bot.coc_client.get_league_group(CLAN_TAG) # Renomeado
        if league_group_status and getattr(league_group_status, 'state', None) != "notInWar" and hasattr(league_group_status, 'rounds'):
            active_cwl_war = None
            prep_cwl_war = None
            latest_ended_cwl_war = None
            current_round_num = -1
            prep_round_num = -1
            ended_round_num = -1

            for round_num_status, war_tags_status in enumerate(league_group_status.rounds): # Renomeado
                 for war_tag_status in war_tags_status: # Renomeado
                     try:
                         league_war_status_obj = await league_group_status.get_league_war(war_tag_status) # Renomeado
                         if not league_war_status_obj or not hasattr(league_war_status_obj, 'state'): continue

                         clan_tag_in_war_status = getattr(getattr(league_war_status_obj, 'clan', None), 'tag', None) # Renomeado
                         opponent_tag_in_war_status = getattr(getattr(league_war_status_obj, 'opponent', None), 'tag', None) # Renomeado
                         war_state_status_val = league_war_status_obj.state # Renomeado

                         if CLAN_TAG == clan_tag_in_war_status or CLAN_TAG == opponent_tag_in_war_status:
                              if CLAN_TAG == opponent_tag_in_war_status:
                                   try:
                                        league_war_status_obj.clan, league_war_status_obj.opponent = league_war_status_obj.opponent, league_war_status_obj.clan
                                   except Exception as swap_err:
                                        logger.error(f"Erro ao tentar trocar clan/opponent no objeto league_war_status_obj {war_tag_status}: {swap_err}")

                              if war_state_status_val == "inWar":
                                   active_cwl_war = league_war_status_obj
                                   current_round_num = round_num_status + 1
                                   break 
                              elif war_state_status_val == "preparation":
                                   prep_cwl_war = league_war_status_obj
                                   prep_round_num = round_num_status + 1
                              elif war_state_status_val == "warEnded":
                                   if hasattr(league_war_status_obj, 'end_time') and league_war_status_obj.end_time:
                                       current_latest_end_time = getattr(latest_ended_cwl_war, 'end_time', None)
                                       if not latest_ended_cwl_war or not current_latest_end_time or league_war_status_obj.end_time > current_latest_end_time:
                                           latest_ended_cwl_war = league_war_status_obj
                                           ended_round_num = round_num_status + 1

                     except coc.NotFound: continue
                     except Exception as e: logger.error(f"Erro ao buscar guerra da liga {war_tag_status} em /status: {e}")
                 if active_cwl_war: break 

            if active_cwl_war:
                war_to_display = active_cwl_war
                war_type_name_status = f"Liga de Clãs (Rodada {current_round_num})"
            elif prep_cwl_war:
                war_to_display = prep_cwl_war
                war_type_name_status = f"Liga de Clãs (Rodada {prep_round_num})"
            elif latest_ended_cwl_war:
                 war_to_display = latest_ended_cwl_war
                 war_type_name_status = f"Liga de Clãs (Rodada {ended_round_num})"


    except coc.NotFound:
        logger.info("/status: Clã não encontrado ao buscar grupo de liga.")
    except Exception as e:
        logger.error(f"Erro ao buscar grupo de liga (CWL) em /status: {e}", exc_info=True)


    # If no relevant CWL war found, check regular war
    if not war_to_display:
        try:
            regular_war_status = await bot.coc_client.get_current_war(CLAN_TAG) # Renomeado
            if regular_war_status and getattr(regular_war_status, 'state', None) != "notInWar":
                war_to_display = regular_war_status
                war_type_name_status = "Guerra Normal"
        except coc.PrivateWarLog:
            status_description = "Log de guerra regular é privado. Não é possível exibir status."
            status_color = discord.Color.orange()
        except coc.NotFound:
            logger.info("/status: Clã não encontrado ao buscar guerra regular.")
        except Exception as e:
            logger.error(f"Erro ao buscar guerra regular em /status: {e}", exc_info=True)
            status_description = "Erro ao buscar informações da guerra regular."
            status_color = discord.Color.red()


    embed_status_final = discord.Embed(title=f"⚔️ Status: {war_type_name_status}", color=status_color) # Renomeado

    if war_to_display and isinstance(war_to_display, coc.ClanWar): 
         clan_disp = getattr(war_to_display, 'clan', None) # Renomeado
         opponent_disp = getattr(war_to_display, 'opponent', None) # Renomeado

         if clan_disp and opponent_disp: 
             clan_name_disp = getattr(clan_disp, 'name', 'Nosso Clã') # Renomeado
             opponent_name_disp = getattr(opponent_disp, 'name', 'Oponente') # Renomeado
             embed_status_final.title = f"⚔️ Status: {war_type_name_status} - {clan_name_disp} vs {opponent_name_disp}"
             if hasattr(clan_disp, 'badge') and clan_disp.badge:
                 embed_status_final.set_thumbnail(url=clan_disp.badge.url)

             state_disp = getattr(war_to_display, 'state', 'unknown') # Renomeado
             start_time_obj_disp = getattr(war_to_display, 'start_time', None) # Renomeado
             end_time_obj_disp = getattr(war_to_display, 'end_time', None) # Renomeado

             start_time_local_str_disp = "N/A" # Renomeado
             end_time_local_str_disp = "N/A" # Renomeado
             time_remaining_str_disp = "N/A" # Renomeado

             try:
                 time_now_disp = datetime.datetime.now(TIMEZONE) # Renomeado
                 if start_time_obj_disp and isinstance(start_time_obj_disp, Timestamp):
                     start_time_aware_disp = start_time_obj_disp.astimezone(TIMEZONE) # Renomeado
                     start_time_local_str_disp = start_time_aware_disp.strftime('%d/%m %H:%M')
                     if state_disp == "preparation":
                          time_delta_disp = start_time_aware_disp - time_now_disp # Renomeado
                          if time_delta_disp.total_seconds() < 0: time_remaining_str_disp = "Iniciada"
                          else:
                              days_disp, rem_disp = divmod(time_delta_disp.total_seconds(), 86400) # Renomeado
                              hours_disp, rem_disp = divmod(rem_disp, 3600) # Renomeado
                              mins_disp, secs_disp = divmod(rem_disp, 60) # Renomeado
                              time_remaining_str_disp = f"{int(days_disp)}d {int(hours_disp)}h {int(mins_disp)}m" if days_disp > 0 else f"{int(hours_disp)}h {int(mins_disp)}m {int(secs_disp)}s"

                 if end_time_obj_disp and isinstance(end_time_obj_disp, Timestamp):
                     end_time_aware_disp = end_time_obj_disp.astimezone(TIMEZONE) # Renomeado
                     end_time_local_str_disp = end_time_aware_disp.strftime('%d/%m %H:%M')
                     if state_disp == "inWar":
                          time_delta_disp_end = end_time_aware_disp - time_now_disp # Renomeado
                          if time_delta_disp_end.total_seconds() < 0: time_remaining_str_disp = "Finalizada"
                          else:
                              days_disp_end, rem_disp_end = divmod(time_delta_disp_end.total_seconds(), 86400) # Renomeado
                              hours_disp_end, rem_disp_end = divmod(rem_disp_end, 3600) # Renomeado
                              mins_disp_end, secs_disp_end = divmod(rem_disp_end, 60) # Renomeado
                              time_remaining_str_disp = f"{int(days_disp_end)}d {int(hours_disp_end)}h {int(mins_disp_end)}m" if days_disp_end > 0 else f"{int(hours_disp_end)}h {int(mins_disp_end)}m {int(secs_disp_end)}s"

             except Exception as e:
                 logger.error(f"Erro ao formatar tempos para /status: {e}")
                 time_remaining_str_disp = "Erro de Tempo"


             if state_disp == "preparation":
                 embed_status_final.description = f"**Estado:** Preparação ⏳\n**Início:** {start_time_local_str_disp} (em ~{time_remaining_str_disp})"
                 embed_status_final.color = discord.Color.light_grey()

             elif state_disp == "inWar":
                 our_stars_disp = getattr(clan_disp, 'stars', 0) # Renomeado
                 our_destr_disp = getattr(clan_disp, 'destruction', 0.0) # Renomeado
                 opp_stars_disp = getattr(opponent_disp, 'stars', 0) # Renomeado
                 opp_destr_disp = getattr(opponent_disp, 'destruction', 0.0) # Renomeado
                 embed_status_final.description = f"**Estado:** Em Guerra 🔥\n**Fim:** {end_time_local_str_disp} ({time_remaining_str_disp} restantes)"
                 embed_status_final.add_field(name=f"{clan_name_disp}", value=f"{our_stars_disp}⭐ ({our_destr_disp:.2f}%)", inline=True)
                 embed_status_final.add_field(name=f"{opponent_name_disp}", value=f"{opp_stars_disp}⭐ ({opp_destr_disp:.2f}%)", inline=True)
                 embed_status_final.color = discord.Color.blue()

             elif state_disp == "warEnded":
                 result_disp = "Empate 🤝" # Renomeado
                 our_stars_end = getattr(clan_disp, 'stars', 0) # Renomeado
                 opp_stars_end = getattr(opponent_disp, 'stars', 0) # Renomeado
                 our_destr_end = getattr(clan_disp, 'destruction', 0.0) # Renomeado
                 opp_destr_end = getattr(opponent_disp, 'destruction', 0.0) # Renomeado
                 if our_stars_end > opp_stars_end or (our_stars_end == opp_stars_end and our_destr_end > opp_destr_end):
                      result_disp = "Vitória ✅"; embed_status_final.color = discord.Color.green()
                 elif opp_stars_end > our_stars_end or (our_stars_end == opp_stars_end and opp_destr_end > our_destr_end):
                      result_disp = "Derrota ❌"; embed_status_final.color = discord.Color.red()
                 embed_status_final.description = f"**Estado:** Guerra Finalizada\n**Resultado:** {result_disp}\n**Fim:** {end_time_local_str_disp}"
                 embed_status_final.add_field(name=f"{clan_name_disp}", value=f"{our_stars_end}⭐ ({our_destr_end:.2f}%)", inline=True)
                 embed_status_final.add_field(name=f"{opponent_name_disp}", value=f"{opp_stars_end}⭐ ({opp_destr_end:.2f}%)", inline=True)

             else: 
                  embed_status_final.description = f"**Estado:** {state_disp.capitalize()}"

         else: 
              embed_status_final.description = f"Informações da guerra ({war_type_name_status}) incompletas."
              embed_status_final.color = discord.Color.orange()
    else:
         embed_status_final.description = status_description 


    embed_status_final.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
    embed_status_final.timestamp = datetime.datetime.now(TIMEZONE)
    await interaction.followup.send(embed=embed_status_final)


# Info commands
@info_group.command(name="clan", description="Exibe informações sobre um clã")
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def clan_info(interaction: discord.Interaction, tag: Optional[str] = None): 
    """Display clan information."""
    target_tag = tag or CLAN_TAG
    if not target_tag:
         await interaction.response.send_message("Nenhuma tag de clã especificada e nenhuma tag padrão configurada.", ephemeral=True)
         return

    try:
        await interaction.response.defer() 
        clan_data_info = await get_clan_data_with_cache(target_tag) # Renomeado

        embed_clan_info = discord.Embed( # Renomeado
            title=f"{clan_data_info.name} ({clan_data_info.tag})",
            description=clan_data_info.description if clan_data_info.description else "Sem descrição.",
            color=discord.Color.blue()
        )
        if hasattr(clan_data_info, 'badge') and clan_data_info.badge: embed_clan_info.set_thumbnail(url=clan_data_info.badge.url)

        embed_clan_info.add_field(name="Nível", value=getattr(clan_data_info, 'level', 'N/A'), inline=True)
        embed_clan_info.add_field(name="Pontos", value=getattr(clan_data_info, 'points', 'N/A'), inline=True)
        embed_clan_info.add_field(name="Guerras Ganhas", value=getattr(clan_data_info, 'war_wins', 'N/A'), inline=True)
        if hasattr(clan_data_info, 'location') and clan_data_info.location: embed_clan_info.add_field(name="Localização", value=clan_data_info.location.name, inline=True)
        embed_clan_info.add_field(name="Tipo", value=getattr(clan_data_info, 'type', 'N/A').capitalize(), inline=True)
        embed_clan_info.add_field(name="Membros", value=f"{getattr(clan_data_info, 'member_count', 'N/A')}/50", inline=True)
        if hasattr(clan_data_info, "capital_points"): embed_clan_info.add_field(name="Troféus Capital", value=clan_data_info.capital_points, inline=True)
        if hasattr(clan_data_info, 'public_war_log'): embed_clan_info.add_field(name="Log de Guerra", value="Público" if clan_data_info.public_war_log else "Privado", inline=True)
        if hasattr(clan_data_info, 'required_trophies'): embed_clan_info.add_field(name="Troféus Mín.", value=clan_data_info.required_trophies, inline=True)
        if hasattr(clan_data_info, 'required_town_hall'): embed_clan_info.add_field(name="CV Mín.", value=clan_data_info.required_town_hall, inline=True)
        if hasattr(clan_data_info, 'war_frequency'): embed_clan_info.add_field(name="Freq. Guerra", value=clan_data_info.war_frequency.capitalize(), inline=True)

        if hasattr(clan_data_info, 'labels') and clan_data_info.labels:
             labels_str = ", ".join([label.name for label in clan_data_info.labels if hasattr(label, 'name')])
             if labels_str and len(labels_str) < 1024: 
                  embed_clan_info.add_field(name="Tags", value=labels_str, inline=False)


        embed_clan_info.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        embed_clan_info.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed_clan_info)

    except ValueError as e: 
         await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e:
        logger.error(f"Erro ao buscar informações do clã {target_tag}: {e}", exc_info=True)
        await interaction.followup.send("Ocorreu um erro ao buscar informações do clã.", ephemeral=True)


@info_group.command(name="jogador", description="Exibe informações sobre um jogador")
@app_commands.describe(tag="Tag do jogador (Ex: #P0LGYC9YQ)")
async def player_info(interaction: discord.Interaction, tag: str):
    """Display player information."""
    try:
        await interaction.response.defer()
        player_data_info = await get_player_data(tag) # Renomeado

        embed_player_info = discord.Embed( # Renomeado
            title=f"{player_data_info.name} ({player_data_info.tag})",
            color=discord.Color.green()
        )
        if hasattr(player_data_info, 'league') and player_data_info.league and hasattr(player_data_info.league, 'icon') and hasattr(player_data_info.league.icon, 'url'):
             embed_player_info.set_thumbnail(url=player_data_info.league.icon.url) 

        basic_info_player = [ # Renomeado
             f"**CV:** {getattr(player_data_info, 'town_hall', '?')}",
             f"**Nível:** {getattr(player_data_info, 'exp_level', '?')}",
             f"**Liga:** {getattr(player_data_info.league, 'name', 'Sem Liga')}" if hasattr(player_data_info, 'league') else "Sem Liga",
             f"**Troféus:** {getattr(player_data_info, 'trophies', '?')}🏆",
             f"**Recorde:** {getattr(player_data_info, 'best_trophies', '?')}🏆"
        ]
        embed_player_info.add_field(name="Informações Básicas", value="\n".join(basic_info_player), inline=True)

        clan_info_parts_player = ["**Clã:** Sem Clã"] # Renomeado
        if hasattr(player_data_info, 'clan') and player_data_info.clan:
            clan_name_player = getattr(player_data_info.clan, 'name', 'Nome Desconhecido') # Renomeado
            clan_level_player = getattr(player_data_info.clan, 'level', '?') # Renomeado
            player_role_obj_player = getattr(player_data_info, 'role', None) # Renomeado
            clan_role_player = player_role_obj_player.name.capitalize() if player_role_obj_player and hasattr(player_role_obj_player, 'name') else 'Membro' # Renomeado
            clan_info_parts_player = [
                 f"**Clã:** {clan_name_player}",
                 f"**Nível Clã:** {clan_level_player}",
                 f"**Cargo:** {clan_role_player}"
            ]
        embed_player_info.add_field(name="Clã", value="\n".join(clan_info_parts_player), inline=True)

        stats_player = [] # Renomeado
        if hasattr(player_data_info, "war_stars"): stats_player.append(f"**Estrelas Guerra:** {player_data_info.war_stars}⭐")
        if hasattr(player_data_info, "attack_wins"): stats_player.append(f"**Ataques Vencidos:** {player_data_info.attack_wins}")
        if hasattr(player_data_info, "defense_wins"): stats_player.append(f"**Defesas Vencidas:** {player_data_info.defense_wins}")
        if hasattr(player_data_info, "donations"): stats_player.append(f"**Tropas Doadas:** {player_data_info.donations}")
        if hasattr(player_data_info, "received"): stats_player.append(f"**Tropas Recebidas:** {player_data_info.received}")
        if hasattr(player_data_info, 'builder_base_trophies'): stats_player.append(f"**Troféus BC:** {player_data_info.builder_base_trophies}🏆")
        if hasattr(player_data_info, 'best_builder_base_trophies'): stats_player.append(f"**Recorde BC:** {player_data_info.best_builder_base_trophies}🏆")

        if stats_player:
             if len(stats_player) > 4:
                  mid_player = len(stats_player) // 2 + (len(stats_player) % 2) # Renomeado
                  col1_player = "\n".join(stats_player[:mid_player]) # Renomeado
                  col2_player = "\n".join(stats_player[mid_player:]) # Renomeado
                  if len(col1_player) <= 1024: embed_player_info.add_field(name="Estatísticas (1/2)", value=col1_player, inline=True)
                  if len(col2_player) <= 1024: embed_player_info.add_field(name="Estatísticas (2/2)", value=col2_player, inline=True)
             elif len("\n".join(stats_player)) <= 1024:
                  embed_player_info.add_field(name="Estatísticas", value="\n".join(stats_player), inline=False)


        if hasattr(player_data_info, 'heroes'):
            heroes_home_player = [] # Renomeado
            heroes_builder_player = [] # Renomeado
            for hero_player in player_data_info.heroes: # Renomeado
                hero_name_player = getattr(hero_player, 'name', '?') # Renomeado
                hero_level_player = getattr(hero_player, 'level', '?') # Renomeado
                hero_max_player = getattr(hero_player, 'max_level', '?') # Renomeado
                if hero_level_player == 0 or hero_level_player == '?': continue
                hero_line_player = f"{hero_name_player}: **{hero_level_player}**/{hero_max_player}" # Renomeado
                if getattr(hero_player, 'is_home_base', True): 
                    heroes_home_player.append(hero_line_player)
                else:
                    heroes_builder_player.append(hero_line_player)

            if heroes_home_player:
                home_text_player = "\n".join(heroes_home_player) # Renomeado
                if len(home_text_player) <= 1024: embed_player_info.add_field(name="Heróis (Base Principal)", value=home_text_player, inline=True)
            if heroes_builder_player:
                 builder_text_player = "\n".join(heroes_builder_player) # Renomeado
                 if len(builder_text_player) <= 1024: embed_player_info.add_field(name="Heróis (Base Construtor)", value=builder_text_player, inline=True)


        embed_player_info.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        embed_player_info.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed_player_info)

    except ValueError as e: 
         await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e:
        logger.error(f"Erro ao buscar informações do jogador {tag}: {e}", exc_info=True)
        await interaction.followup.send("Ocorreu um erro ao buscar informações do jogador.", ephemeral=True)


@info_group.command(name="membros", description="Lista os membros do clã")
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def clan_members(interaction: discord.Interaction, tag: Optional[str] = None):
    """Display clan members."""
    target_tag = tag or CLAN_TAG
    if not target_tag:
         await interaction.response.send_message("Nenhuma tag de clã especificada e nenhuma tag padrão configurada.", ephemeral=True)
         return

    try:
        await interaction.response.defer()
        clan_members_data = await get_clan_data_with_cache(target_tag) # Renomeado

        base_embed_members = discord.Embed( # Renomeado
            title=f"👥 Membros de {clan_members_data.name}",
            description=f"Total: {getattr(clan_members_data, 'member_count', 'N/A')}/50",
            color=discord.Color.blue()
        )
        if hasattr(clan_members_data, 'badge') and clan_members_data.badge: base_embed_members.set_thumbnail(url=clan_members_data.badge.url)

        members_list_details_cmd = [] # Renomeado
        if hasattr(clan_members_data, 'members') and clan_members_data.members:
             role_order_members = {"leader": 0, "co-leader": 1, "admin": 2, "member": 3} # Renomeado
             sorted_members_cmd = sorted(clan_members_data.members, key=lambda m: ( # Renomeado
                 role_order_members.get(getattr(getattr(m,'role',None), 'name', 'member').lower(), 4), 
                 -getattr(m, 'trophies', 0)
             ))
             for i, member_item_cmd in enumerate(sorted_members_cmd): # Renomeado
                name_member_cmd = getattr(member_item_cmd, 'name', 'Nome Desconhecido') # Renomeado
                th_member_cmd = getattr(member_item_cmd, 'town_hall', '?') # Renomeado
                role_name_member_cmd = getattr(getattr(member_item_cmd,'role',None), 'name', 'Membro').capitalize() # Renomeado
                trophies_member_cmd = getattr(member_item_cmd, 'trophies', 0) # Renomeado
                league_name_member_cmd = getattr(getattr(member_item_cmd, 'league', None), 'name', 'Sem Liga') # Renomeado
                donations_member_cmd = getattr(member_item_cmd, 'donations', 0) # Renomeado
                received_member_cmd = getattr(member_item_cmd, 'received', 0) # Renomeado
                members_list_details_cmd.append(f"{i+1}. **{name_member_cmd}** (CV{th_member_cmd}) | {role_name_member_cmd} | {trophies_member_cmd}🏆 | Doa:{donations_member_cmd}/Rec:{received_member_cmd}")
        else:
             members_list_details_cmd.append("Não foi possível listar os membros.")


        await interaction.followup.send(embed=base_embed_members)

        splitter_base_embed_cmd = discord.Embed(color=discord.Color.blue()) # Renomeado
        await send_embeds_splitted(interaction.channel, splitter_base_embed_cmd, "Lista de Membros", members_list_details_cmd)


    except ValueError as e: 
         await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e:
        logger.error(f"Erro ao listar membros do clã {target_tag}: {e}", exc_info=True)
        if not interaction.is_expired(): 
             try:
                  await interaction.followup.send("Ocorreu um erro ao listar os membros.", ephemeral=True)
             except discord.NotFound: 
                  logger.warning("Interaction expired before sending error message for /info membros.")
        else:
            logger.warning("Interaction expired before sending error message for /info membros.")


# Search commands
@search_group.command(name="clan", description="Busca clãs por nome")
@app_commands.describe(
    nome="Nome (ou parte do nome) do clã",
    min_membros="Número mínimo de membros",
    max_membros="Número máximo de membros",
    min_nivel="Nível mínimo do clã",
    localizacao="Nome da localização (ex: Brazil)"
)
async def search_clan(
    interaction: discord.Interaction,
    nome: str,
    min_membros: Optional[app_commands.Range[int, 1, 50]] = None, 
    max_membros: Optional[app_commands.Range[int, 1, 50]] = None,
    min_nivel: Optional[app_commands.Range[int, 1, None]] = None,
    localizacao: Optional[str] = None
):
    """Search for clans with filters."""
    await interaction.response.defer()
    search_params_clan = {'name': nome, 'limit': 20} # Renomeado

    if min_membros is not None: search_params_clan['min_members'] = min_membros
    if max_membros is not None: search_params_clan['max_members'] = max_membros
    if min_nivel is not None: search_params_clan['min_clan_level'] = min_nivel
    if localizacao:
        try:
            location_id_search = await fetch_location_id(localizacao) # Renomeado
            search_params_clan['location'] = location_id_search
            logger.info(f"Busca de clã usando localização ID {location_id_search} para '{localizacao}'.")
        except ValueError as e:
            await interaction.followup.send(f"Erro ao buscar localização: {e}", ephemeral=True)
            return

    try:
        logger.info(f"Buscando clãs com parâmetros: {search_params_clan}")
        clans_found = await bot.coc_client.search_clans(**search_params_clan) # Renomeado

        if not clans_found:
            await interaction.followup.send(f"Nenhum clã encontrado com os critérios fornecidos.")
            return

        embed_search_clan = discord.Embed( # Renomeado
            title=f"Resultados da busca por '{nome}'",
            description="Clãs encontrados:",
            color=discord.Color.blue()
        )
        results_count_search = 0 # Renomeado
        output_lines_search = [] # Renomeado
        for i, clan_item_search in enumerate(clans_found): # Renomeado
            c_name_search = getattr(clan_item_search, 'name', 'Nome Desconhecido') # Renomeado
            c_tag_search = getattr(clan_item_search, 'tag', 'Tag Desconhecida') # Renomeado
            c_level_search = getattr(clan_item_search, 'level', '?') # Renomeado
            c_members_search = getattr(clan_item_search, 'member_count', '?') # Renomeado
            c_points_search = getattr(clan_item_search, 'points', '?') # Renomeado
            c_loc_search = getattr(getattr(clan_item_search, 'location', None), 'name', 'N/A') # Renomeado
            c_freq_search = getattr(clan_item_search, 'war_frequency', 'N/A').capitalize() if hasattr(clan_item_search, 'war_frequency') else 'N/A' # Renomeado


            line_search = f"{i+1}. **{c_name_search}** (`{c_tag_search}`)\n" \
                   f"   Nível: {c_level_search} | Membros: {c_members_search}/50 | Pontos: {c_points_search}🏆 | Local: {c_loc_search}" # Renomeado
            output_lines_search.append(line_search)
            results_count_search += 1
            if results_count_search >= 10: 
                 break

        output_text_search = "\n".join(output_lines_search) # Renomeado
        if len(output_text_search) <= 4096: 
             embed_search_clan.description = output_text_search
        else:
             embed_search_clan.description="Muitos resultados, exibindo os 10 primeiros:"
             for line_item_search in output_lines_search: # Renomeado
                 parts_search = line_item_search.split('\n   ', 1) # Renomeado
                 field_name_search = parts_search[0] # Renomeado
                 field_value_search = '   ' + parts_search[1] if len(parts_search) > 1 else "Detalhes indisponíveis" # Renomeado
                 if len(embed_search_clan) + len(field_name_search) + len(field_value_search) < 6000 and len(embed_search_clan.fields) < 25:
                      embed_search_clan.add_field(name=field_name_search, value=field_value_search, inline=False)
                 else:
                      break


        embed_search_clan.set_footer(text=f"Exibindo {results_count_search} de {len(clans_found)} resultados encontrados.")
        embed_search_clan.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed_search_clan)

    except ValueError as e: 
         await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e:
        logger.error(f"Erro ao buscar clãs: {e}", exc_info=True)
        await interaction.followup.send("Ocorreu um erro ao buscar clãs.", ephemeral=True)


@search_group.command(name="jogador", description="Busca jogadores por nome")
@app_commands.describe(nome="Nome (ou parte do nome) do jogador")
async def search_player(interaction: discord.Interaction, nome: str):
    """Search for players by name."""
    try:
        await interaction.response.defer()
        players_found_search = await bot.coc_client.search_players(name=nome, limit=20) # Renomeado

        if not players_found_search:
            await interaction.followup.send(f"Nenhum jogador encontrado com o nome '{nome}'.")
            return

        embed_search_player = discord.Embed( # Renomeado
            title=f"Resultados da busca por '{nome}'",
            description="Jogadores encontrados:",
            color=discord.Color.green()
        )
        results_count_player_search = 0 # Renomeado
        output_lines_player_search = [] # Renomeado

        for i, player_item_search in enumerate(players_found_search): # Renomeado
            p_name_search_item = getattr(player_item_search, 'name', 'Nome Desconhecido') # Renomeado
            p_tag_search_item = getattr(player_item_search, 'tag', 'Tag Desconhecida') # Renomeado
            p_th_search_item = getattr(player_item_search, 'town_hall', '?') # Renomeado
            p_trophies_search_item = getattr(player_item_search, 'trophies', '?') # Renomeado
            p_level_search_item = getattr(player_item_search, 'exp_level', '?') # Renomeado
            p_clan_search_item = getattr(player_item_search, 'clan', None) # Renomeado
            clan_info_search_item = f"{p_clan_search_item.name}" if p_clan_search_item and hasattr(p_clan_search_item, 'name') else "Sem clã" # Renomeado
            league_name_search_item = getattr(getattr(player_item_search, 'league', None), 'name', 'Sem Liga') # Renomeado

            line_player_search = f"{i+1}. **{p_name_search_item}** (`{p_tag_search_item}`) | CV{p_th_search_item} | Nível {p_level_search_item}\n" \
                   f"   {p_trophies_search_item}🏆 ({league_name_search_item}) | Clã: {clan_info_search_item}" # Renomeado
            output_lines_player_search.append(line_player_search)
            results_count_player_search += 1
            if results_count_player_search >= 10: 
                break

        output_text_player_search = "\n".join(output_lines_player_search) # Renomeado
        if len(output_text_player_search) <= 4096:
             embed_search_player.description = output_text_player_search
        else:
             embed_search_player.description = "Muitos resultados, exibindo os 10 primeiros."

        embed_search_player.set_footer(text=f"Exibindo {results_count_player_search} de {len(players_found_search)} resultados encontrados.")
        embed_search_player.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed_search_player)

    except Exception as e:
        logger.error(f"Erro ao buscar jogadores: {e}", exc_info=True)
        await interaction.followup.send("Ocorreu um erro ao buscar jogadores.", ephemeral=True)


# Rank commands
@rank_group.command(name="doacoes", description="Exibe o ranking de doações do clã")
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def donations_rank(interaction: discord.Interaction, tag: Optional[str] = None):
    """Display clan donations ranking."""
    target_tag = tag or CLAN_TAG
    if not target_tag:
         await interaction.response.send_message("Nenhuma tag de clã especificada e nenhuma tag padrão configurada.", ephemeral=True)
         return

    try:
        await interaction.response.defer()
        clan_rank_don = await get_clan_data_with_cache(target_tag) # Renomeado

        base_embed_rank_don = discord.Embed( # Renomeado
            title=f"🎁 Ranking de Doações - {clan_rank_don.name}",
            color=discord.Color.gold()
        )
        if hasattr(clan_rank_don, 'badge') and clan_rank_don.badge: base_embed_rank_don.set_thumbnail(url=clan_rank_don.badge.url)

        rank_list_don = [] # Renomeado
        if hasattr(clan_rank_don, 'members') and clan_rank_don.members:
             members_rank_don = sorted(clan_rank_don.members, key=lambda m: getattr(m, 'donations', 0), reverse=True) # Renomeado
             for i, member_rank_don_item in enumerate(members_rank_don): # Renomeado
                name_rank_don = getattr(member_rank_don_item, 'name', 'Nome Desconhecido') # Renomeado
                donations_rank_don = getattr(member_rank_don_item, 'donations', 0) # Renomeado
                received_rank_don = getattr(member_rank_don_item, 'received', 0) # Renomeado
                ratio_rank_don = donations_rank_don / received_rank_don if received_rank_don > 0 else float(donations_rank_don) # Renomeado
                rank_list_don.append(f"{i+1}. **{name_rank_don}** - Doou: {donations_rank_don} / Recebeu: {received_rank_don} (Ratio: {ratio_rank_don:.2f})")
        else:
             rank_list_don.append("Não foi possível buscar os membros para o ranking.")

        await interaction.followup.send(embed=base_embed_rank_don)
        splitter_base_rank_don = discord.Embed(color=discord.Color.gold()) # Renomeado
        await send_embeds_splitted(interaction.channel, splitter_base_rank_don, "Ranking de Doações", rank_list_don)

    except ValueError as e:
        await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e:
        logger.error(f"Erro ao buscar ranking de doações para {target_tag}: {e}", exc_info=True)
        await interaction.followup.send("Ocorreu um erro ao buscar o ranking de doações.", ephemeral=True)


@rank_group.command(name="trofeus", description="Exibe o ranking de troféus do clã")
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def trophies_rank(interaction: discord.Interaction, tag: Optional[str] = None):
    """Display clan trophies ranking."""
    target_tag = tag or CLAN_TAG
    if not target_tag:
         await interaction.response.send_message("Nenhuma tag de clã especificada e nenhuma tag padrão configurada.", ephemeral=True)
         return

    try:
        await interaction.response.defer()
        clan_rank_trophies = await get_clan_data_with_cache(target_tag) # Renomeado

        base_embed_rank_trophies = discord.Embed( # Renomeado
            title=f"🏆 Ranking de Troféus - {clan_rank_trophies.name}",
            color=discord.Color.purple() 
        )
        if hasattr(clan_rank_trophies, 'badge') and clan_rank_trophies.badge: base_embed_rank_trophies.set_thumbnail(url=clan_rank_trophies.badge.url)

        rank_list_trophies = [] # Renomeado
        if hasattr(clan_rank_trophies, 'members') and clan_rank_trophies.members:
             members_rank_trophies = sorted(clan_rank_trophies.members, key=lambda m: getattr(m, 'trophies', 0), reverse=True) # Renomeado
             for i, member_rank_trophies_item in enumerate(members_rank_trophies): # Renomeado
                name_rank_trophies = getattr(member_rank_trophies_item, 'name', 'Nome Desconhecido') # Renomeado
                trophies_rank_val = getattr(member_rank_trophies_item, 'trophies', 0) # Renomeado
                league_name_rank_trophies = getattr(getattr(member_rank_trophies_item, 'league', None), 'name', 'Sem Liga') # Renomeado
                rank_list_trophies.append(f"{i+1}. **{name_rank_trophies}** - {trophies_rank_val}🏆 ({league_name_rank_trophies})")
        else:
             rank_list_trophies.append("Não foi possível buscar os membros para o ranking.")

        await interaction.followup.send(embed=base_embed_rank_trophies)
        splitter_base_rank_trophies = discord.Embed(color=discord.Color.purple()) # Renomeado
        await send_embeds_splitted(interaction.channel, splitter_base_rank_trophies, "Ranking de Troféus", rank_list_trophies)

    except ValueError as e:
        await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e:
        logger.error(f"Erro ao buscar ranking de troféus para {target_tag}: {e}", exc_info=True)
        await interaction.followup.send("Ocorreu um erro ao buscar o ranking de troféus.", ephemeral=True)


@rank_group.command(name="cv", description="Exibe o ranking de Casa de Vila do clã")
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def th_rank(interaction: discord.Interaction, tag: Optional[str] = None):
    """Display clan Town Hall ranking."""
    target_tag = tag or CLAN_TAG
    if not target_tag:
         await interaction.response.send_message("Nenhuma tag de clã especificada e nenhuma tag padrão configurada.", ephemeral=True)
         return

    try:
        await interaction.response.defer()
        clan_rank_th = await get_clan_data_with_cache(target_tag) # Renomeado

        base_embed_rank_th = discord.Embed( # Renomeado
            title=f"🏠 Ranking de Casa de Vila - {clan_rank_th.name}",
            color=discord.Color.dark_orange() 
        )
        if hasattr(clan_rank_th, 'badge') and clan_rank_th.badge: base_embed_rank_th.set_thumbnail(url=clan_rank_th.badge.url)

        rank_list_th = [] # Renomeado
        if hasattr(clan_rank_th, 'members') and clan_rank_th.members:
             members_rank_th = sorted(clan_rank_th.members, key=lambda m: (getattr(m, 'town_hall', 0), getattr(m, 'exp_level', 0)), reverse=True) # Renomeado
             for i, member_rank_th_item in enumerate(members_rank_th): # Renomeado
                 name_rank_th_item = getattr(member_rank_th_item, 'name', 'Nome Desconhecido') # Renomeado
                 th_rank_val = getattr(member_rank_th_item, 'town_hall', '?') # Renomeado
                 level_rank_th_val = getattr(member_rank_th_item, 'exp_level', '?') # Renomeado
                 rank_list_th.append(f"{i+1}. **{name_rank_th_item}** - CV{th_rank_val} (Nível {level_rank_th_val})")
        else:
             rank_list_th.append("Não foi possível buscar os membros para o ranking.")

        await interaction.followup.send(embed=base_embed_rank_th)
        splitter_base_rank_th = discord.Embed(color=discord.Color.dark_orange()) # Renomeado
        await send_embeds_splitted(interaction.channel, splitter_base_rank_th, "Ranking de CV", rank_list_th)

    except ValueError as e:
        await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e:
        logger.error(f"Erro ao buscar ranking de CV para {target_tag}: {e}", exc_info=True)
        await interaction.followup.send("Ocorreu um erro ao buscar o ranking de CV.", ephemeral=True)


# Setup functions
async def setup_web_server():
    """Setup basic web server for health checks (Render)."""
    app_web = web.Application() # Renomeado
    async def health_handler(request):
        logger.debug("Health check endpoint '/' accessed.")
        return web.Response(text="Bot is running!")
    app_web.router.add_get("/", health_handler)

    runner_web = web.AppRunner(app_web) # Renomeado
    await runner_web.setup()
    port_web = int(os.environ.get("PORT", 8080)) # Renomeado
    site_web = web.TCPSite(runner_web, host="0.0.0.0", port=port_web) # Renomeado
    try:
         await site_web.start()
         logger.info(f"Servidor web para health check iniciado em 0.0.0.0:{port_web}")
         return runner_web
    except OSError as e:
        logger.error(f"Falha ao iniciar servidor web na porta {port_web}: {e} - Verifique se a porta está em uso.")
        return None 
    except Exception as e:
         logger.error(f"Erro inesperado ao iniciar servidor web: {e}", exc_info=True)
         return None

async def setup_hook():
    """Setup hook for the bot, called before bot logs in."""
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

    logger.info("Configurando servidor web para health check...")
    bot.web_runner = await setup_web_server() 
    if bot.web_runner:
        logger.info("Servidor web configurado.")
    else:
        logger.warning("Falha ao configurar o servidor web.")

    logger.info("Tentando sincronizar comandos de aplicativo (/) no setup_hook...")
    synced_commands_list_hook = []  # Renomeado
    try:
        if TEST_GUILD_ID:
            try:
                guild_id_obj_hook = discord.Object(id=int(TEST_GUILD_ID)) # Renomeado
                logger.info(f"Copiando comandos globais para o servidor de teste ID: {TEST_GUILD_ID} e sincronizando...")
                bot.tree.copy_global_to(guild=guild_id_obj_hook)  
                synced_commands_list_hook = await bot.tree.sync(guild=guild_id_obj_hook)
                logger.info(f"{len(synced_commands_list_hook)} comandos (/) sincronizados com o servidor de teste (ID: {TEST_GUILD_ID}).")
                if synced_commands_list_hook: 
                    nomes_comandos_sinc_hook = [cmd.name for cmd in synced_commands_list_hook] # Renomeado
                    logger.info(f"Nomes dos comandos sincronizados com o guild: {nomes_comandos_sinc_hook}")
                elif not synced_commands_list_hook and bot.tree.get_commands(): 
                    nomes_comandos_globais_hook = [cmd.name for cmd in bot.tree.get_commands()] # Renomeado
                    logger.warning(f"Nenhum comando sincronizado com o guild, mas a tree global possui: {nomes_comandos_globais_hook}")

            except (ValueError, TypeError):
                logger.error(f"TEST_GUILD_ID ('{TEST_GUILD_ID}') é inválido. Tentando sincronizar globalmente...")
                synced_commands_list_hook = await bot.tree.sync()
                logger.info(f"{len(synced_commands_list_hook)} comandos (/) sincronizados globalmente.")
        else:
            logger.info("Nenhum TEST_GUILD_ID definido. Sincronizando comandos globalmente...")
            synced_commands_list_hook = await bot.tree.sync()
            logger.info(f"{len(synced_commands_list_hook)} comandos (/) sincronizados globalmente.")

        if not synced_commands_list_hook:
            logger.warning("Nenhum comando de aplicativo foi sincronizado. Verifique as definições e se foram adicionados à tree.")
        
    except discord.Forbidden as e:
        logger.error(f"Erro 403 Forbidden ao sincronizar comandos (/): {e}. Verifique as permissões do bot (application.commands).")
    except discord.HTTPException as e:
        logger.error(f"Erro HTTP ao sincronizar comandos (/): {e.status} - {e.text}", exc_info=True)
    except Exception as e:
        logger.error(f"Erro inesperado ao sincronizar comandos (/) no setup_hook: {e}", exc_info=True)

    logger.info("setup_hook concluído.")

# Main execution block
async def main():
    """Main function to start the bot."""
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
             shard_info_main = f"(Shard ID: {e.shard_id})" if hasattr(e, 'shard_id') and e.shard_id is not None else "" # Renomeado
             logger.critical(f"Intents Privilegiadas {shard_info_main} não habilitadas no Portal do Desenvolvedor Discord.")
        except Exception as e:
            logger.critical(f"Erro crítico durante a execução do bot: {e}", exc_info=True)
        finally:
            logger.info("Iniciando processo de desligamento do bot...")
            if 'check_war_end_report_task' in globals() and check_war_end_report_task.is_running():
                 logger.info("Parando tarefa 'check_war_end_report_task'...")
                 check_war_end_report_task.cancel()
                 try:
                     await asyncio.sleep(1) 
                     logger.info("Tarefa 'check_war_end_report_task' cancelada.")
                 except asyncio.CancelledError:
                     logger.info("Tarefa 'check_war_end_report_task' foi cancelada com sucesso.")
                 except Exception as e:
                     logger.error(f"Erro durante cancelamento da tarefa 'check_war_end_report_task': {e}")

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
    msg = context.get("exception", context["message"])
    future_exc = context.get('future') # Renomeado
    if future_exc:
        logger.error(f"Erro não tratado no loop asyncio (Future: {future_exc}): {msg}", exc_info=context.get('exception'))
    else:
        logger.error(f"Erro não tratado no loop asyncio: {msg}", exc_info=context.get('exception'))

if __name__ == "__main__":
    required_vars = ["DISCORD_TOKEN", "COC_EMAIL", "COC_PASSWORD", "CLAN_TAG", "CHANNEL_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
         logger.critical(f"Variáveis de ambiente obrigatórias faltando: {', '.join(missing_vars)}. Verifique .env ou configuração.")
    else:
        loop_main = asyncio.get_event_loop() # Renomeado
        try:
            logger.info("Iniciando loop de eventos asyncio para main()...")
            loop_main.set_exception_handler(handle_asyncio_exception) 
            loop_main.run_until_complete(main())

        except KeyboardInterrupt:
            logger.info("Bot interrompido manualmente (KeyboardInterrupt).")
        except RuntimeError as e:
             if "Event loop is closed" in str(e):
                  logger.info("Loop de eventos fechado durante o desligamento (normal).")
             else:
                  logger.warning(f"RuntimeError durante execução do loop: {e}", exc_info=True)
        except Exception as e:
            logger.critical(f"Erro fatal fora do loop principal do bot: {e}", exc_info=True)
        finally:
            # loop_main já está definido
            if loop_main.is_running():
                loop_main.stop()
            if not loop_main.is_closed():
                tasks_main = [t for t in asyncio.all_tasks(loop=loop_main) if t is not asyncio.current_task(loop=loop_main)] # Renomeado
                if tasks_main:
                    logger.info(f"Cancelando {len(tasks_main)} tarefas pendentes...")
                    for task_item_main in tasks_main: # Renomeado
                        task_item_main.cancel()
                    loop_main.run_until_complete(asyncio.gather(*tasks_main, return_exceptions=True))
                    logger.info("Tarefas pendentes canceladas.")
                loop_main.close()
                logger.info("Loop de eventos asyncio fechado.")
            logger.info("Programa finalizado.")
