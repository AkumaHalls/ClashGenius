# -*- coding: utf-8 -*-
# Versão 17.1 -

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
BOT_VERSION = "17.1"

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
    for embed in embeds_to_send:
        if not hasattr(embed, 'footer') or not hasattr(embed.footer, 'text') or not embed.footer.text:
             embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
        if not embed.timestamp:
             embed.timestamp = datetime.datetime.now(TIMEZONE)

    # Send all embeds
    for embed in embeds_to_send:
        try:
            await channel.send(embed=embed)
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
        embed = discord.Embed(
            title=f"⚔️ Guerra Não Ativa",
            description=f"A guerra contra **{opponent_name}** ({opponent_tag}) não está em andamento (Estado: {war.state}).",
            color=discord.Color.orange()
        )
        if clan_badge_url: embed.set_thumbnail(url=clan_badge_url)
        embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        embed.timestamp = datetime.datetime.now(TIMEZONE)
        return [embed]

    # Calculate time remaining safely
    try:
         time_now = datetime.datetime.now(TIMEZONE)
         # Ensure end_time is timezone-aware for comparison
         end_time_aware = war.end_time.astimezone(TIMEZONE) if war.end_time.tzinfo is None else war.end_time.astimezone(TIMEZONE)

         time_delta = end_time_aware - time_now
         if time_delta.total_seconds() < 0:
              time_remaining = "Finalizada" # War ended but state not updated?
         else:
             days = time_delta.days
             secs = time_delta.seconds
             hours, rem = divmod(secs, 3600)
             mins, secs = divmod(rem, 60)
             time_remaining = f"{days}d {hours}h {mins}m" if days > 0 else f"{hours}h {mins}m {int(secs)}s" # Cast secs to int

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
    base_embed = discord.Embed(
        title=f"🗡️ Ataques Restantes - {clan_name} vs {opponent_name}",
        description=f"**Placar:** {war.clan.stars}⭐ ({war.clan.destruction:.2f}%) vs {opponent_stars}⭐ ({opponent_destruction:.2f}%)\n"
                    f"**Fim:** {end_time_local} ({time_remaining} restantes)",
        color=discord.Color.blue()
    )
    if clan_badge_url: base_embed.set_thumbnail(url=clan_badge_url)


    # Use send_embeds_splitted logic internally to generate embeds
    embeds_to_send = []
    field_name = "Membros com Ataques Pendentes"
    if not members_with_attacks:
         embed = discord.Embed.from_dict(base_embed.to_dict())
         embed.add_field(name=field_name, value="✅ Todos os ataques já foram utilizados!", inline=False)
         embeds_to_send.append(embed)
    else:
        # Simplified splitting logic for this specific case
        current_embed = discord.Embed.from_dict(base_embed.to_dict())
        current_field_value = ""
        for item in members_with_attacks:
            item_line = item + "\n"
            if len(current_field_value) + len(item_line) > 1024:
                if current_field_value:
                    current_embed.add_field(name=field_name, value=current_field_value, inline=False)
                # Add completed embed only if it has fields (prevent empty base embed)
                if current_embed.fields:
                    embeds_to_send.append(current_embed)
                # Start new embed
                current_embed = discord.Embed.from_dict(base_embed.to_dict())
                current_field_value = item_line
                # Handle item too long (though unlikely here)
                if len(current_field_value) > 1024:
                    current_field_value = current_field_value[:1021] + "...\n"
            else:
                current_field_value += item_line

        # Add the last field and embed
        if current_field_value:
            current_embed.add_field(name=field_name, value=current_field_value, inline=False)
        if current_embed.fields: # Ensure the last embed has fields
            embeds_to_send.append(current_embed)

    # Add footers and timestamps
    for embed in embeds_to_send:
        if not hasattr(embed, 'footer') or not hasattr(embed.footer, 'text') or not embed.footer.text:
             embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        if not embed.timestamp:
             embed.timestamp = datetime.datetime.now(TIMEZONE)

    return embeds_to_send if embeds_to_send else None # Return None if something went wrong

# --- End refactored display_attacks_remaining ---

async def send_missed_attacks_report(war: ClanWar, # Use explicit type
                                    missed_members_details: List[str], # Now expects formatted details
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
            # Fetch channel and guild robustly
            log_channel = await bot.fetch_channel(CHANNEL_ID)
            if log_channel and hasattr(log_channel, 'guild'):
                 guild = log_channel.guild
                 # Ensure ROLE_ID is valid integer
                 try:
                     role_id_int = int(ROLE_ID_MISSED_ATTACK)
                     role = guild.get_role(role_id_int)
                     if role:
                         # NOVO: Adiciona menção ANTES do embed
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

    # Create base embed safely
    opponent_name = getattr(getattr(war, 'opponent', None), 'name', 'Oponente Desconhecido')
    base_embed = discord.Embed(
        # NOVO: Título como na imagem
        title=f"❌ Ataques Não Realizados - {war_type}",
        # NOVO: Descrição como na imagem
        description=f"Membros que não usaram todos os ataques contra **{opponent_name}**:",
        color=discord.Color.red()
    )
    # NOVO: Thumbnail como na imagem (se disponível)
    if hasattr(war, 'opponent') and hasattr(war.opponent, 'badge') and war.opponent.badge:
         base_embed.set_thumbnail(url=war.opponent.badge.url) # Usa badge do oponente

    try:
        # Fetch channel again for sending
        channel = await bot.fetch_channel(CHANNEL_ID)
        if isinstance(channel, discord.TextChannel):
             # NOVO: Envia a menção primeiro (se existir)
             if content:
                  await channel.send(content)
             # Envia os embeds com a lista usando a função splitter
             # Usa "Membros (Parte X)" como field_name se houver mais de um embed? send_embeds_splitted precisa de ajuste para isso.
             # Por ora, usa "Membros" como nome do campo.
             await send_embeds_splitted(channel, base_embed, "Membros", missed_members_details)
        else:
             logger.error(f"Canal de log ID {CHANNEL_ID} não é um canal de texto válido para relatório.")

    except discord.NotFound:
         logger.error(f"Canal de log ID {CHANNEL_ID} não encontrado para relatório.")
    except discord.Forbidden:
         logger.error(f"Sem permissão para enviar relatório de ataques perdidos no canal {CHANNEL_ID}.")
    except Exception as e:
        logger.error(f"Erro ao enviar relatório de ataques perdidos para o canal {CHANNEL_ID}: {e}", exc_info=True)

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
                  clan = await bot.coc_client.get_clan(CLAN_TAG)
                  clan_name = clan.name
                  clan_tag_formatted = clan.tag
             except Exception as e:
                  logger.error(f"Erro ao buscar dados do clã para status online: {e}")
                  # Continua com nome/tag padrão

        embed = discord.Embed(
            title="✅ Bot Online e Monitorando!",
            description=f"Eventos do clã **{clan_name}** (`{clan_tag_formatted}`) e Guerras monitorados.",
            color=discord.Color.green()
        )
        embed.add_field(name="Monitoramento", value="Event-Driven Ativo 🔄", inline=False)
        # Rodapé padrão será adicionado por send_log_embed
        await send_log_embed(embed)
        logger.info("Mensagem de status online enviada.")

    except Exception as e:
        logger.error(f"Erro ao enviar mensagem de status online: {e}", exc_info=True)

# Bot events
# ========================================================================================= #
# =============================  INÍCIO DA SEÇÃO MODIFICADA  ============================= #
# ========================================================================================= #
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
# ========================================================================================= #
# ==============================  FIM DA SEÇÃO MODIFICADA  =============================== #
# ========================================================================================= #

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Handle app command errors."""
    command_name = interaction.command.qualified_name if interaction.command else 'Comando Desconhecido'
    error_embed = discord.Embed(
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


    error_embed.description = error_message
    error_embed.set_footer(text=f"Comando: /{command_name}")
    error_embed.timestamp = datetime.datetime.now(TIMEZONE)

    try:
        # Use followup if already responded (e.g., deferred), otherwise send initial response
        if interaction.response.is_done():
            await interaction.followup.send(embed=error_embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
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
        clan = member.clan # Acessa o clã via membro
        logger.info(f"Evento: {member.name} ({member.tag}) entrou no clã {clan.name}.")
        embed = discord.Embed(
            title="👋 Novo Membro",
            description=f"**{member.name}** (`{member.tag}`) entrou no clã!",
            color=discord.Color.green()
        )
        embed.add_field(name="CV", value=getattr(member, 'town_hall', '?'), inline=True)
        embed.add_field(name="Nível", value=getattr(member, 'exp_level', '?'), inline=True)
        embed.add_field(name="Troféus", value=getattr(member, 'trophies', '?'), inline=True)
        if hasattr(member, 'league') and member.league:
            embed.add_field(name="Liga", value=member.league.name, inline=True)
        if hasattr(clan, 'badge') and clan.badge:
             embed.set_author(name=clan.name, icon_url=clan.badge.url)
             embed.set_thumbnail(url=clan.badge.url)
        await send_log_embed(embed)

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
        clan_obj = old_member.clan if hasattr(old_member, 'clan') else None
        clan_name = getattr(clan_obj, 'name', 'Clã Desconhecido')
        # clan_tag = getattr(clan_obj, 'tag', '') # Não usado diretamente no embed, mas disponível

        # Detalhes do membro que saiu, obtidos de old_member
        leaving_member_name = getattr(old_member, 'name', 'Membro Desconhecido')
        leaving_member_tag = getattr(old_member, 'tag', 'Tag Desconhecida')
        leaving_member_town_hall = getattr(old_member, 'town_hall', '?')
        leaving_member_exp_level = getattr(old_member, 'exp_level', '?')
        leaving_member_trophies = getattr(old_member, 'trophies', '?')
        leaving_member_league = getattr(old_member, 'league', None)
        league_name = getattr(leaving_member_league, 'name', 'Sem Liga') if leaving_member_league else 'Sem Liga'

        logger.info(f"Evento: {leaving_member_name} ({leaving_member_tag}) saiu do clã {clan_name}.")

        embed = discord.Embed(
            title="👋 Membro Saiu",
            description=f"**{leaving_member_name}** (`{leaving_member_tag}`) saiu do clã!",
            color=discord.Color.red()
        )
        embed.add_field(name="CV", value=leaving_member_town_hall, inline=True)
        embed.add_field(name="Nível", value=leaving_member_exp_level, inline=True)
        embed.add_field(name="Troféus", value=leaving_member_trophies, inline=True)
        embed.add_field(name="Liga", value=league_name, inline=True)

        if clan_obj and hasattr(clan_obj, 'badge') and clan_obj.badge:
             embed.set_author(name=clan_name, icon_url=clan_obj.badge.url)
             embed.set_thumbnail(url=clan_obj.badge.url)
        else:
            logger.warning(f"Não foi possível obter o emblema do clã {clan_name} ({getattr(clan_obj, 'tag', 'TAG CLÃ DESCONHECIDA')}) para o evento de saída de {leaving_member_name} ({leaving_member_tag}).")
            # Opcional: definir o nome do clã como autor mesmo sem o ícone
            # embed.set_author(name=clan_name)

        await send_log_embed(embed)

    @coc_client.event
    @coc.ClanEvents.member_donations(tags=[CLAN_TAG])
    async def on_member_donations(old_member: ClanMember, member: ClanMember):
        """Handle member donations event."""
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan = member.clan
        old_donations = getattr(old_member, 'donations', 0)
        new_donations = getattr(member, 'donations', 0)
        donation_difference = new_donations - old_donations
        if donation_difference <= 0: return
        logger.info(f"Evento: {member.name} doou {donation_difference} tropas (Total: {new_donations}).")
        embed = discord.Embed(color=discord.Color.green())
        if hasattr(clan, 'badge') and clan.badge:
             embed.set_author(name=clan.name, icon_url=clan.badge.url)
             embed.set_thumbnail(url=clan.badge.url)
        embed.add_field(name="🎁 Doação",
                         value=f"**{donation_difference}** tropas por `{member.name}` (Total doado: {new_donations})", inline=False)
        await send_log_embed(embed)

    @coc_client.event
    @coc.ClanEvents.member_received(tags=[CLAN_TAG])
    async def on_member_received(old_member: ClanMember, member: ClanMember):
        """Handle member received donations event."""
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan = member.clan
        old_received = getattr(old_member, 'received', 0)
        new_received = getattr(member, 'received', 0)
        received_difference = new_received - old_received
        if received_difference <= 0: return
        logger.info(f"Evento: {member.name} recebeu {received_difference} tropas (Total: {new_received}).")
        embed = discord.Embed(color=discord.Color.blue())
        if hasattr(clan, 'badge') and clan.badge:
            embed.set_author(name=clan.name, icon_url=clan.badge.url)
            embed.set_thumbnail(url=clan.badge.url)
        embed.add_field(name="📥 Recebimento",
                         value=f"`{member.name}` recebeu **{received_difference}** tropas (Total recebido: {new_received})", inline=False)
        await send_log_embed(embed)

    @coc_client.event
    @coc.ClanEvents.member_role_change(tags=[CLAN_TAG])
    async def on_member_role_change(old_member: ClanMember, member: ClanMember):
        # <<< NOVO LOG >>>
        logger.info(f"EVENTO DETECTADO: on_member_role_change para {getattr(member, 'tag', 'TAG DESCONHECIDA')}")
        """Handle member role change event."""
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan = member.clan
        old_role = getattr(old_member, 'role', None)
        new_role = getattr(member, 'role', None)
        if old_role == new_role: return
        logger.info(f"Evento: Cargo de {member.name} mudou de {old_role} para {new_role} em {clan.name}.")
        embed = discord.Embed(
            title="🔄 Mudança de Cargo",
            description=f"Cargo de **{member.name}** (`{member.tag}`) foi alterado!",
            color=discord.Color.gold()
        )
        embed.add_field(name="Cargo Anterior", value=old_role.name.capitalize() if old_role else 'N/A', inline=True)
        embed.add_field(name="Novo Cargo", value=new_role.name.capitalize() if new_role else 'N/A', inline=True)
        if hasattr(clan, 'badge') and clan.badge:
             embed.set_author(name=clan.name, icon_url=clan.badge.url)
             embed.set_thumbnail(url=clan.badge.url)
        await send_log_embed(embed)

    @coc_client.event
    @coc.ClanEvents.member_league_change(tags=[CLAN_TAG])
    async def on_member_league_change(old_member: ClanMember, member: ClanMember):
        """Handle member league change event."""
        if not member or not old_member or not hasattr(member, 'clan'): return
        clan = member.clan
        old_league = getattr(old_member, 'league', None)
        new_league = getattr(member, 'league', None)
        if old_league == new_league: return
        logger.info(f"Evento: Liga de {member.name} mudou de {old_league} para {new_league} em {clan.name}.")
        old_league_name = old_league.name if old_league else "Sem Liga"
        new_league_name = new_league.name if new_league else "Sem Liga"
        embed = discord.Embed(
            title="🏆 Mudança de Liga",
            description=f"Liga de **{member.name}** (`{member.tag}`) foi alterada!",
            color=discord.Color.purple()
        )
        embed.add_field(name="Liga Anterior", value=old_league_name, inline=True)
        embed.add_field(name="Nova Liga", value=new_league_name, inline=True)
        if hasattr(clan, 'badge') and clan.badge:
             embed.set_author(name=clan.name, icon_url=clan.badge.url)
             embed.set_thumbnail(url=clan.badge.url)
        await send_log_embed(embed)


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
        embed = discord.Embed(
            description=f"**{member.name}** {direction} **{abs(trophy_difference)}** troféus (Total: {new_trophies})",
            color=discord.Color.green() if trophy_difference > 0 else discord.Color.dark_red()
        )
        await send_log_embed(embed)


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

        if is_our_attack:
            logger.info(f"Evento Guerra: {attacker_name} atacou {defender_name} - {attack.stars} estrelas, {attack.destruction}% destruição.")
            embed = discord.Embed(
                title=f"⚔️ Ataque Realizado (Guerra)",
                description=f"**{attacker_name}** (CV{attacker_th}) atacou **{defender_name}** (CV{defender_th})",
                color=discord.Color.blue()
            )
            embed.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
            content = None
            if attack.stars <= 1 and ROLE_ID_1STAR_ALERT:
                try:
                    log_channel = await bot.fetch_channel(CHANNEL_ID)
                    if log_channel and hasattr(log_channel, 'guild'):
                         guild = log_channel.guild
                         try:
                              role_id_int = int(ROLE_ID_1STAR_ALERT)
                              role = guild.get_role(role_id_int)
                              if role: content = f"{role.mention} ⚠️ Atenção: ataque fora do padrão detectado!"
                              else: logger.warning(f"Cargo para alerta de 1 estrela (ID: {ROLE_ID_1STAR_ALERT}) não encontrado.")
                         except (ValueError, TypeError): logger.error(f"ROLE_ID_1STAR_ALERT ('{ROLE_ID_1STAR_ALERT}') é inválido.")
                    else: logger.warning("Não foi possível buscar o servidor do canal de log para alerta de 1 estrela.")
                except Exception as e: logger.error(f"Erro ao buscar cargo para alerta de 1 estrela: {e}", exc_info=True)

            # Use war.clan badge for our attacks
            if hasattr(war, 'clan') and hasattr(war.clan, 'badge') and war.clan.badge:
                 embed.set_author(name=war.clan.name, icon_url=war.clan.badge.url)
                 embed.set_thumbnail(url=war.clan.badge.url)
            await send_log_embed(embed, content)

        elif is_our_defense:
            logger.info(f"Evento Guerra: {defender_name} foi atacado por {attacker_name} - {attack.stars} estrelas, {attack.destruction}% destruição.")
            embed = discord.Embed(
                title=f"🛡️ Defesa Recebida (Guerra)",
                description=f"**{defender_name}** (CV{defender_th}) foi atacado por **{attacker_name}** (CV{attacker_th})",
                color=discord.Color.orange()
            )
            embed.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
             # Use war.opponent badge for defense log (assuming opponent is attacker's clan)
            if hasattr(war, 'opponent') and hasattr(war.opponent, 'badge') and war.opponent.badge:
                 embed.set_author(name=war.opponent.name, icon_url=war.opponent.badge.url)
                 embed.set_thumbnail(url=war.opponent.badge.url)
            await send_log_embed(embed)

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

    async def process_war(war: ClanWar, war_type_name: str): # Use explicit type ClanWar
        """Helper to process a single war (regular or CWL)."""
        # Use war end time ISO string as a unique ID
        war_id = war.end_time.raw_time if hasattr(war, 'end_time') and hasattr(war.end_time, 'raw_time') else None

        if not war or not war_id or war_id in processed_war_ids:
            # Log reason for skipping only if war object exists
            if war and war_id:
                 reason = "já processado neste ciclo" if war_id in processed_war_ids else "ID inválido"
                 logger.debug(f"Pulando processamento de guerra - {reason} (ID: {war_id})")
            elif not war:
                 logger.debug("Pulando processamento de guerra - objeto 'war' inválido.")
            return

        opponent_name = getattr(getattr(war, 'opponent', None), 'name', 'Oponente Desconhecido')
        war_state = getattr(war, 'state', 'unknown')
        logger.debug(f"Processando guerra: {war_type_name} contra {opponent_name} (ID: {war_id}, Estado: {war_state})")

        # Check if war ended and hasn't been reported yet
        if war_state == "warEnded" and war_id not in reported_war_ends:
            logger.info(f"Guerra '{war_type_name}' contra {opponent_name} terminou (ID: {war_id}). Verificando ataques perdidos...")

            # Determine which side is our clan and get attacks_per_member
            our_clan_obj = None
            attacks_per_member = 2 # Default for regular war

            if "Liga de Clãs" in war_type_name:
                 attacks_per_member = 1 # CWL is always 1 attack
                 # Ensure clan/opponent exist before checking tags
                 war_clan_tag = getattr(getattr(war, 'clan', None), 'tag', None)
                 war_opponent_tag = getattr(getattr(war, 'opponent', None), 'tag', None)
                 if war_clan_tag == CLAN_TAG:
                     our_clan_obj = war.clan
                 elif war_opponent_tag == CLAN_TAG:
                     our_clan_obj = war.opponent
                 else:
                      logger.error(f"Guerra da liga {war_id} não contém o clã {CLAN_TAG}? ClanTag: {war_clan_tag}, OppTag: {war_opponent_tag}")
                      return
            else: # Assume regular war
                 our_clan_obj = getattr(war, 'clan', None)
                 attacks_per_member = getattr(war, 'attacks_per_member', 2)

            if not our_clan_obj:
                 logger.error(f"Não foi possível identificar nosso clã na guerra {war_id}.")
                 return

            # Check for missed attacks
            missed_members_details = []
            if hasattr(our_clan_obj, 'members') and our_clan_obj.members:
                 for member in our_clan_obj.members:
                    # Ensure member object is valid
                    if not member or not hasattr(member, 'tag'): continue

                    attacks_used = len(member.attacks) if hasattr(member, "attacks") and member.attacks else 0
                    if attacks_used < attacks_per_member:
                        missed_count = attacks_per_member - attacks_used
                        member_name = getattr(member, 'name', member.tag) # Use tag as fallback name
                        member_th = getattr(member, 'town_hall', '?')
                        # <<< MODIFICAÇÃO APLICADA AQUI >>>
                        missed_members_details.append(
                            f"**{member_name}** (CV{member_th}): {missed_count} perdido{'s' if missed_count > 1 else ''}"
                        )
            else:
                 logger.warning(f"Objeto do clã '{getattr(our_clan_obj, 'name', 'N/A')}' na guerra {war_id} não possui lista de membros.")


            if missed_members_details:
                logger.info(f"{len(missed_members_details)} membro(s) perderam ataques na guerra {war_type_name} (ID: {war_id}).")
                await send_missed_attacks_report(war, missed_members_details, war_type_name)
            else:
                logger.info(f"Nenhum ataque perdido na guerra {war_type_name} (ID: {war_id}).")

            reported_war_ends.add(war_id) # Mark war as reported using its ID
            processed_war_ids.add(war_id) # Mark as processed in this cycle
            logger.debug(f"Guerra {war_id} marcada como reportada.")
        else:
             # Log why it wasn't processed
             if war_state != "warEnded":
                  logger.debug(f"Guerra {war_id} não está no estado 'warEnded' (Estado: {war_state}).")
             elif war_id in reported_war_ends:
                  logger.debug(f"Guerra {war_id} já foi reportada anteriormente.")
             else:
                  logger.debug(f"Guerra {war_id} não processada por outra razão.")


    # --- Check Regular War ---
    try:
        logger.debug("Buscando guerra atual (regular)...")
        current_war = await bot.coc_client.get_current_war(CLAN_TAG)
        if current_war and hasattr(current_war, 'state') and current_war.state != "notInWar":
             # Ensure war object is valid before processing
             if hasattr(current_war, 'end_time'):
                  await process_war(current_war, "Guerra Normal")
             else:
                  logger.warning("Objeto de guerra regular inválido (sem end_time).")
        elif current_war and hasattr(current_war, 'state'):
              logger.debug(f"Nenhuma guerra regular ativa ou terminada recentemente encontrada (Estado: {current_war.state}).")
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
        league_group = await bot.coc_client.get_league_group(CLAN_TAG)

        if league_group and hasattr(league_group, 'state') and league_group.state != "notInWar":
            logger.debug(f"Grupo de liga encontrado (Estado: {league_group.state}). Verificando rodadas...")
            # Iterate through rounds safely
            if hasattr(league_group, 'rounds') and league_group.rounds:
                 # Process rounds in reverse to likely get the most recent ended war first
                 for round_num, war_tags in reversed(list(enumerate(league_group.rounds))):
                     logger.debug(f"Processando rodada {round_num + 1} da CWL...")
                     for war_tag in war_tags:
                         try:
                             # Fetch the war object
                             league_war = await league_group.get_league_war(war_tag)

                             # Basic validation of the war object
                             if not league_war or not hasattr(league_war, 'state') or not hasattr(league_war, 'end_time'):
                                  logger.warning(f"Objeto da guerra da liga {war_tag} inválido ou incompleto.")
                                  continue

                             # Check if our clan is involved before processing
                             clan_tag_in_war = getattr(getattr(league_war, 'clan', None), 'tag', None)
                             opponent_tag_in_war = getattr(getattr(league_war, 'opponent', None), 'tag', None)

                             if CLAN_TAG == clan_tag_in_war or CLAN_TAG == opponent_tag_in_war:
                                 await process_war(league_war, f"Liga de Clãs (Rodada {round_num + 1})")
                             # else: # Optional: log skipped wars
                             #      logger.debug(f"Guerra da liga {war_tag} não envolve o clã {CLAN_TAG}.")

                         except coc.NotFound:
                              logger.warning(f"Guerra da liga com tag {war_tag} (Rodada {round_num + 1}) não encontrada.")
                         except Exception as e:
                              logger.error(f"Erro ao buscar/processar guerra da liga {war_tag} (Rodada {round_num + 1}): {e}", exc_info=True)
            else:
                 logger.debug("Grupo de liga não possui informações de rodadas ('rounds').")
        elif league_group and hasattr(league_group, 'state'):
             logger.debug(f"Nenhum grupo de liga ativo encontrado (Estado: {league_group.state}).")
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
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latência da API do Discord: **{latency_ms}ms**",
        color=discord.Color.green() if latency_ms < 200 else discord.Color.orange() if latency_ms < 500 else discord.Color.red()
    )
    embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
    embed.timestamp = datetime.datetime.now(TIMEZONE)
    await interaction.response.send_message(embed=embed, ephemeral=True) # Ephemeral for admin command

# War commands continued
@war_group.command(name="ataques", description="Exibe os ataques restantes na guerra atual (Normal ou Liga)")
async def war_attacks(interaction: discord.Interaction):
    """Display remaining attacks in the current war (tries CWL first, then regular)."""
    await interaction.response.defer() # Defer response as it involves API calls

    current_war: Optional[ClanWar] = None # Explicit type hint
    war_type_name = "Guerra" # Default name

    # Try CWL first
    try:
        league_group = await bot.coc_client.get_league_group(CLAN_TAG)
        if league_group and getattr(league_group,'state',None) != "notInWar" and hasattr(league_group, 'rounds'):
            # Find the current active war in CWL
            for round_num, war_tags in enumerate(league_group.rounds):
                 if current_war: break # Stop if found
                 for war_tag in war_tags:
                     try:
                         league_war = await league_group.get_league_war(war_tag)
                         # Check involvement and state safely
                         clan_tag_in_war = getattr(getattr(league_war, 'clan', None), 'tag', None)
                         opponent_tag_in_war = getattr(getattr(league_war, 'opponent', None), 'tag', None)
                         war_state = getattr(league_war, 'state', None)

                         if league_war and (CLAN_TAG == clan_tag_in_war or CLAN_TAG == opponent_tag_in_war):
                              if war_state == "inWar":
                                   # Need to potentially swap clan/opponent if our clan is opponent object
                                   if CLAN_TAG == opponent_tag_in_war:
                                        # Ensure swap happens correctly if possible, might need deep copy if objects are complex
                                        try:
                                            temp_clan = league_war.clan
                                            league_war.clan = league_war.opponent
                                            league_war.opponent = temp_clan
                                        except Exception as swap_err:
                                            logger.error(f"Erro ao tentar trocar clan/opponent no objeto league_war: {swap_err}")
                                            # Continue without swap? Might display wrong names/stats
                                   current_war = league_war
                                   war_type_name = f"Liga de Clãs (Rodada {round_num + 1})"
                                   break # Found active war
                     except coc.NotFound:
                          continue # Skip if war tag not found
                     except Exception as e:
                          logger.error(f"Erro ao buscar guerra da liga {war_tag} em /ataques: {e}")
                          continue # Skip this war tag on error

    except coc.NotFound:
         logger.info("/ataques: Clã não encontrado ao buscar grupo de liga.")
    except Exception as e:
         logger.error(f"Erro ao buscar grupo de liga (CWL) em /ataques: {e}", exc_info=True)


    # If no active CWL war found, check regular war
    if not current_war:
         try:
             regular_war = await bot.coc_client.get_current_war(CLAN_TAG)
             if regular_war and getattr(regular_war, 'state', None) == "inWar":
                  current_war = regular_war
                  war_type_name = "Guerra Normal"
         except coc.PrivateWarLog:
              await interaction.followup.send("Log de guerra regular é privado. Não é possível verificar ataques.", ephemeral=True)
              return
         except coc.NotFound:
              logger.info("/ataques: Clã não encontrado ao buscar guerra regular.")
         except Exception as e:
              logger.error(f"Erro ao buscar guerra regular em /ataques: {e}", exc_info=True)
              await interaction.followup.send("Erro ao buscar informações da guerra regular.", ephemeral=True)
              return # Stop if error fetching regular war

    # Now, format and send the embeds
    if current_war:
         # Ensure current_war is a valid ClanWar object before formatting
         if isinstance(current_war, coc.ClanWar):
              embeds = await format_attacks_remaining_embed(current_war)
              if embeds:
                  first_embed = embeds.pop(0)
                  await interaction.followup.send(embed=first_embed)
                  for embed in embeds:
                      try:
                          # Check if channel is accessible
                          if interaction.channel and isinstance(interaction.channel, discord.abc.Messageable):
                              await interaction.channel.send(embed=embed)
                          else:
                               logger.warning("interaction.channel não está acessível para enviar embeds adicionais.")
                               break
                      except Exception as e:
                          logger.error(f"Erro ao enviar embed adicional de /ataques: {e}")
                          break
              else:
                  await interaction.followup.send(f"Erro ao formatar informações de ataques para {war_type_name}.", ephemeral=True)
         else:
              logger.error(f"Objeto 'current_war' inválido ({type(current_war)}) passado para format_attacks_remaining_embed.")
              await interaction.followup.send(f"Erro interno ao processar dados da guerra ({war_type_name}).", ephemeral=True)

    else:
         # Neither CWL nor regular war is active and inWar
         await interaction.followup.send("O clã não está em nenhuma guerra ativa (Normal ou Liga) no momento.")


@war_group.command(name="status", description="Exibe o status da guerra atual (Normal ou Liga)")
async def war_status(interaction: discord.Interaction):
    """Display current war status (tries CWL first, then regular)."""
    await interaction.response.defer()

    war_to_display: Optional[ClanWar] = None # Explicit type hint
    war_type_name = "Guerra"
    status_description = "Nenhuma guerra ativa ou recente encontrada." # Default message
    status_color = discord.Color.greyple()

    # Try CWL first
    try:
        league_group = await bot.coc_client.get_league_group(CLAN_TAG)
        if league_group and getattr(league_group, 'state', None) != "notInWar" and hasattr(league_group, 'rounds'):
            active_cwl_war = None
            prep_cwl_war = None
            latest_ended_cwl_war = None
            current_round_num = -1
            prep_round_num = -1
            ended_round_num = -1

            # Iterate to find the most relevant war
            for round_num, war_tags in enumerate(league_group.rounds):
                 for war_tag in war_tags:
                     try:
                         league_war = await league_group.get_league_war(war_tag)
                         # Basic validation
                         if not league_war or not hasattr(league_war, 'state'): continue

                         clan_tag_in_war = getattr(getattr(league_war, 'clan', None), 'tag', None)
                         opponent_tag_in_war = getattr(getattr(league_war, 'opponent', None), 'tag', None)
                         war_state = league_war.state

                         if CLAN_TAG == clan_tag_in_war or CLAN_TAG == opponent_tag_in_war:
                              # Swap if our clan is opponent
                              if CLAN_TAG == opponent_tag_in_war:
                                   try:
                                        league_war.clan, league_war.opponent = league_war.opponent, league_war.clan
                                   except Exception as swap_err:
                                        logger.error(f"Erro ao tentar trocar clan/opponent no objeto league_war {war_tag}: {swap_err}")

                              if war_state == "inWar":
                                   active_cwl_war = league_war
                                   current_round_num = round_num + 1
                                   break # Prioritize active war
                              elif war_state == "preparation":
                                   prep_cwl_war = league_war
                                   prep_round_num = round_num + 1
                              elif war_state == "warEnded":
                                   # Check end_time validity
                                   if hasattr(league_war, 'end_time') and league_war.end_time:
                                       # Ensure latest_ended_cwl_war also has end_time before comparing
                                       current_latest_end_time = getattr(latest_ended_cwl_war, 'end_time', None)
                                       if not latest_ended_cwl_war or not current_latest_end_time or league_war.end_time > current_latest_end_time:
                                           latest_ended_cwl_war = league_war
                                           ended_round_num = round_num + 1

                     except coc.NotFound: continue
                     except Exception as e: logger.error(f"Erro ao buscar guerra da liga {war_tag} em /status: {e}")
                 if active_cwl_war: break # Exit outer loop

            # Determine which CWL war to display
            if active_cwl_war:
                war_to_display = active_cwl_war
                war_type_name = f"Liga de Clãs (Rodada {current_round_num})"
            elif prep_cwl_war:
                war_to_display = prep_cwl_war
                war_type_name = f"Liga de Clãs (Rodada {prep_round_num})"
            elif latest_ended_cwl_war:
                 war_to_display = latest_ended_cwl_war
                 war_type_name = f"Liga de Clãs (Rodada {ended_round_num})"


    except coc.NotFound:
        logger.info("/status: Clã não encontrado ao buscar grupo de liga.")
    except Exception as e:
        logger.error(f"Erro ao buscar grupo de liga (CWL) em /status: {e}", exc_info=True)


    # If no relevant CWL war found, check regular war
    if not war_to_display:
        try:
            regular_war = await bot.coc_client.get_current_war(CLAN_TAG)
            if regular_war and getattr(regular_war, 'state', None) != "notInWar":
                war_to_display = regular_war
                war_type_name = "Guerra Normal"
        except coc.PrivateWarLog:
            status_description = "Log de guerra regular é privado. Não é possível exibir status."
            status_color = discord.Color.orange()
        except coc.NotFound:
            logger.info("/status: Clã não encontrado ao buscar guerra regular.")
        except Exception as e:
            logger.error(f"Erro ao buscar guerra regular em /status: {e}", exc_info=True)
            status_description = "Erro ao buscar informações da guerra regular."
            status_color = discord.Color.red()


    # --- Format Embed based on war_to_display ---
    embed = discord.Embed(title=f"⚔️ Status: {war_type_name}", color=status_color)

    if war_to_display and isinstance(war_to_display, coc.ClanWar): # Ensure it's a valid war object
         clan = getattr(war_to_display, 'clan', None)
         opponent = getattr(war_to_display, 'opponent', None)

         if clan and opponent: # Proceed only if both exist
             clan_name = getattr(clan, 'name', 'Nosso Clã')
             opponent_name = getattr(opponent, 'name', 'Oponente')
             embed.title = f"⚔️ Status: {war_type_name} - {clan_name} vs {opponent_name}"
             if hasattr(clan, 'badge') and clan.badge:
                 embed.set_thumbnail(url=clan.badge.url)

             state = getattr(war_to_display, 'state', 'unknown')
             start_time_obj = getattr(war_to_display, 'start_time', None)
             end_time_obj = getattr(war_to_display, 'end_time', None)

             # Format time strings safely
             start_time_local_str = "N/A"
             end_time_local_str = "N/A"
             time_remaining_str = "N/A"

             try:
                 time_now = datetime.datetime.now(TIMEZONE)
                 if start_time_obj and isinstance(start_time_obj, Timestamp):
                     start_time_aware = start_time_obj.astimezone(TIMEZONE) if start_time_obj.tzinfo is None else start_time_obj.astimezone(TIMEZONE)
                     start_time_local_str = start_time_aware.strftime('%d/%m %H:%M')
                     if state == "preparation":
                          time_delta = start_time_aware - time_now
                          if time_delta.total_seconds() < 0: time_remaining_str = "Iniciada"
                          else:
                              days, rem = divmod(time_delta.total_seconds(), 86400)
                              hours, rem = divmod(rem, 3600)
                              mins, secs = divmod(rem, 60)
                              time_remaining_str = f"{int(days)}d {int(hours)}h {int(mins)}m" if days > 0 else f"{int(hours)}h {int(mins)}m {int(secs)}s"

                 if end_time_obj and isinstance(end_time_obj, Timestamp):
                     end_time_aware = end_time_obj.astimezone(TIMEZONE) if end_time_obj.tzinfo is None else end_time_obj.astimezone(TIMEZONE)
                     end_time_local_str = end_time_aware.strftime('%d/%m %H:%M')
                     if state == "inWar":
                          time_delta = end_time_aware - time_now
                          if time_delta.total_seconds() < 0: time_remaining_str = "Finalizada"
                          else:
                              days, rem = divmod(time_delta.total_seconds(), 86400)
                              hours, rem = divmod(rem, 3600)
                              mins, secs = divmod(rem, 60)
                              time_remaining_str = f"{int(days)}d {int(hours)}h {int(mins)}m" if days > 0 else f"{int(hours)}h {int(mins)}m {int(secs)}s"

             except Exception as e:
                 logger.error(f"Erro ao formatar tempos para /status: {e}")
                 time_remaining_str = "Erro de Tempo"


             # Build description and fields based on state
             if state == "preparation":
                 embed.description = f"**Estado:** Preparação ⏳\n**Início:** {start_time_local_str} (em ~{time_remaining_str})"
                 embed.color = discord.Color.light_grey()

             elif state == "inWar":
                 our_stars = getattr(clan, 'stars', 0)
                 our_destr = getattr(clan, 'destruction', 0.0)
                 opp_stars = getattr(opponent, 'stars', 0)
                 opp_destr = getattr(opponent, 'destruction', 0.0)
                 embed.description = f"**Estado:** Em Guerra 🔥\n**Fim:** {end_time_local_str} ({time_remaining_str} restantes)"
                 embed.add_field(name=f"{clan_name}", value=f"{our_stars}⭐ ({our_destr:.2f}%)", inline=True)
                 embed.add_field(name=f"{opponent_name}", value=f"{opp_stars}⭐ ({opp_destr:.2f}%)", inline=True)
                 embed.color = discord.Color.blue()

             elif state == "warEnded":
                 result = "Empate 🤝"
                 our_stars = getattr(clan, 'stars', 0)
                 opp_stars = getattr(opponent, 'stars', 0)
                 our_destr = getattr(clan, 'destruction', 0.0)
                 opp_destr = getattr(opponent, 'destruction', 0.0)
                 if our_stars > opp_stars or (our_stars == opp_stars and our_destr > opp_destr):
                      result = "Vitória ✅"; embed.color = discord.Color.green()
                 elif opp_stars > our_stars or (our_stars == opp_stars and opp_destr > our_destr):
                      result = "Derrota ❌"; embed.color = discord.Color.red()
                 embed.description = f"**Estado:** Guerra Finalizada\n**Resultado:** {result}\n**Fim:** {end_time_local_str}"
                 embed.add_field(name=f"{clan_name}", value=f"{our_stars}⭐ ({our_destr:.2f}%)", inline=True)
                 embed.add_field(name=f"{opponent_name}", value=f"{opp_stars}⭐ ({opp_destr:.2f}%)", inline=True)

             else: # Handle other potential states
                  embed.description = f"**Estado:** {state.capitalize()}"

         else: # Fallback if clan/opponent data missing
              embed.description = f"Informações da guerra ({war_type_name}) incompletas."
              embed.color = discord.Color.orange()
    else:
         embed.description = status_description # Use status set earlier


    embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
    embed.timestamp = datetime.datetime.now(TIMEZONE)
    await interaction.followup.send(embed=embed)


# Info commands
@info_group.command(name="clan", description="Exibe informações sobre um clã")
@app_commands.describe(tag="Tag do clã (opcional, usa o clã monitorado por padrão)")
async def clan_info(interaction: discord.Interaction, tag: Optional[str] = None): # Use Optional
    """Display clan information."""
    target_tag = tag or CLAN_TAG
    if not target_tag:
         await interaction.response.send_message("Nenhuma tag de clã especificada e nenhuma tag padrão configurada.", ephemeral=True)
         return

    try:
        await interaction.response.defer() # Defer as API call can take time
        clan = await get_clan_data_with_cache(target_tag) # Use cache and error handling helper

        embed = discord.Embed(
            title=f"{clan.name} ({clan.tag})",
            description=clan.description if clan.description else "Sem descrição.",
            color=discord.Color.blue()
        )
        if hasattr(clan, 'badge') and clan.badge: embed.set_thumbnail(url=clan.badge.url)

        # Use getattr for safer access to attributes
        embed.add_field(name="Nível", value=getattr(clan, 'level', 'N/A'), inline=True)
        embed.add_field(name="Pontos", value=getattr(clan, 'points', 'N/A'), inline=True)
        embed.add_field(name="Guerras Ganhas", value=getattr(clan, 'war_wins', 'N/A'), inline=True)
        if hasattr(clan, 'location') and clan.location: embed.add_field(name="Localização", value=clan.location.name, inline=True)
        embed.add_field(name="Tipo", value=getattr(clan, 'type', 'N/A').capitalize(), inline=True)
        embed.add_field(name="Membros", value=f"{getattr(clan, 'member_count', 'N/A')}/50", inline=True)
        if hasattr(clan, "capital_points"): embed.add_field(name="Troféus Capital", value=clan.capital_points, inline=True)
        if hasattr(clan, 'public_war_log'): embed.add_field(name="Log de Guerra", value="Público" if clan.public_war_log else "Privado", inline=True)
        if hasattr(clan, 'required_trophies'): embed.add_field(name="Troféus Mín.", value=clan.required_trophies, inline=True)
        if hasattr(clan, 'required_town_hall'): embed.add_field(name="CV Mín.", value=clan.required_town_hall, inline=True)
        if hasattr(clan, 'war_frequency'): embed.add_field(name="Freq. Guerra", value=clan.war_frequency.capitalize(), inline=True)

        # Add labels if available
        if hasattr(clan, 'labels') and clan.labels:
             labels_str = ", ".join([label.name for label in clan.labels if hasattr(label, 'name')])
             if labels_str and len(labels_str) < 1024: # Check length before adding
                  embed.add_field(name="Tags", value=labels_str, inline=False)


        embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        embed.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed)

    except ValueError as e: # Catch specific errors from get_clan_data
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
        player = await get_player_data(tag) # Uses helper with error handling

        embed = discord.Embed(
            title=f"{player.name} ({player.tag})",
            color=discord.Color.green()
        )
        if hasattr(player, 'league') and player.league and hasattr(player.league, 'icon') and hasattr(player.league.icon, 'url'):
             embed.set_thumbnail(url=player.league.icon.url) # Use league icon as thumbnail

        # --- Player Basic Info ---
        basic_info = [
             f"**CV:** {getattr(player, 'town_hall', '?')}",
             f"**Nível:** {getattr(player, 'exp_level', '?')}",
             f"**Liga:** {getattr(player.league, 'name', 'Sem Liga')}" if hasattr(player, 'league') else "Sem Liga",
             f"**Troféus:** {getattr(player, 'trophies', '?')}🏆",
             f"**Recorde:** {getattr(player, 'best_trophies', '?')}🏆"
        ]
        embed.add_field(name="Informações Básicas", value="\n".join(basic_info), inline=True)

        # --- Clan Info ---
        clan_info_parts = ["**Clã:** Sem Clã"]
        if hasattr(player, 'clan') and player.clan:
            clan_name = getattr(player.clan, 'name', 'Nome Desconhecido')
            clan_level = getattr(player.clan, 'level', '?')
            # Get role name safely
            player_role_obj = getattr(player, 'role', None)
            clan_role = player_role_obj.name.capitalize() if player_role_obj and hasattr(player_role_obj, 'name') else 'Membro'
            clan_info_parts = [
                 f"**Clã:** {clan_name}",
                 f"**Nível Clã:** {clan_level}",
                 f"**Cargo:** {clan_role}"
            ]
        embed.add_field(name="Clã", value="\n".join(clan_info_parts), inline=True)

        # --- Stats ---
        stats = []
        if hasattr(player, "war_stars"): stats.append(f"**Estrelas Guerra:** {player.war_stars}⭐")
        if hasattr(player, "attack_wins"): stats.append(f"**Ataques Vencidos:** {player.attack_wins}")
        if hasattr(player, "defense_wins"): stats.append(f"**Defesas Vencidas:** {player.defense_wins}")
        if hasattr(player, "donations"): stats.append(f"**Tropas Doadas:** {player.donations}")
        if hasattr(player, "received"): stats.append(f"**Tropas Recebidas:** {player.received}")
        # Add Builder Base stats if available
        if hasattr(player, 'builder_base_trophies'): stats.append(f"**Troféus BC:** {player.builder_base_trophies}🏆")
        if hasattr(player, 'best_builder_base_trophies'): stats.append(f"**Recorde BC:** {player.best_builder_base_trophies}🏆")

        if stats:
             # Split stats into two columns if too many
             if len(stats) > 4:
                  mid = len(stats) // 2 + (len(stats) % 2) # Split favoring first column
                  col1 = "\n".join(stats[:mid])
                  col2 = "\n".join(stats[mid:])
                  if len(col1) <= 1024: embed.add_field(name="Estatísticas (1/2)", value=col1, inline=True)
                  if len(col2) <= 1024: embed.add_field(name="Estatísticas (2/2)", value=col2, inline=True)
             elif len("\n".join(stats)) <= 1024:
                  embed.add_field(name="Estatísticas", value="\n".join(stats), inline=False)


        # --- Heroes ---
        if hasattr(player, 'heroes'):
            heroes_home = []
            heroes_builder = []
            for hero in player.heroes:
                hero_name = getattr(hero, 'name', '?')
                hero_level = getattr(hero, 'level', '?')
                hero_max = getattr(hero, 'max_level', '?')
                # Skip heroes with level 0 or invalid data
                if hero_level == 0 or hero_level == '?': continue
                hero_line = f"{hero_name}: **{hero_level}**/{hero_max}"
                if getattr(hero, 'is_home_base', True): # Assume home base if attribute missing
                    heroes_home.append(hero_line)
                else:
                    heroes_builder.append(hero_line)

            if heroes_home:
                home_text = "\n".join(heroes_home)
                if len(home_text) <= 1024: embed.add_field(name="Heróis (Base Principal)", value=home_text, inline=True)
            if heroes_builder:
                 builder_text = "\n".join(heroes_builder)
                 if len(builder_text) <= 1024: embed.add_field(name="Heróis (Base Construtor)", value=builder_text, inline=True)


        # --- Troops / Spells / Sieges (Optional, can be long) ---
        # Consider adding a separate command for this level of detail


        embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
        embed.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed)

    except ValueError as e: # Catch specific errors from get_player_data
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
        clan = await get_clan_data_with_cache(target_tag) # Use cache

        base_embed = discord.Embed( # Create the base embed first
            title=f"👥 Membros de {clan.name}",
            description=f"Total: {getattr(clan, 'member_count', 'N/A')}/50",
            color=discord.Color.blue()
        )
        if hasattr(clan, 'badge') and clan.badge: base_embed.set_thumbnail(url=clan.badge.url)

        members_list_details = []
        if hasattr(clan, 'members') and clan.members:
             role_order = {"leader": 0, "co-leader": 1, "admin": 2, "member": 3}
             sorted_members = sorted(clan.members, key=lambda m: (
                 role_order.get(getattr(getattr(m,'role',None), 'name', 'member').lower(), 4), # Safe role name access
                 -getattr(m, 'trophies', 0)
             ))
             for i, member in enumerate(sorted_members):
                name = getattr(member, 'name', 'Nome Desconhecido')
                th = getattr(member, 'town_hall', '?')
                role_name = getattr(getattr(member,'role',None), 'name', 'Membro').capitalize()
                trophies = getattr(member, 'trophies', 0)
                league_name = getattr(getattr(member, 'league', None), 'name', 'Sem Liga')
                donations = getattr(member, 'donations', 0)
                received = getattr(member, 'received', 0)
                # Format the string for the list, maybe add index
                members_list_details.append(f"{i+1}. **{name}** (CV{th}) | {role_name} | {trophies}🏆 | Doa:{donations}/Rec:{received}")
        else:
             members_list_details.append("Não foi possível listar os membros.")


        # Send the base embed first using followup
        await interaction.followup.send(embed=base_embed)

        # Now send the list using the splitter function to the channel
        # Create a minimal embed for the splitter to use as a base for fields
        splitter_base_embed = discord.Embed(color=discord.Color.blue())
        # Use a more generic field name if base_embed already has title
        await send_embeds_splitted(interaction.channel, splitter_base_embed, "Lista de Membros", members_list_details)


    except ValueError as e: # Catch specific errors from get_clan_data
         await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e:
        logger.error(f"Erro ao listar membros do clã {target_tag}: {e}", exc_info=True)
        # Check if followup was already sent before sending error
        if not interaction.is_expired(): # Check if interaction is still valid
             try:
                  await interaction.followup.send("Ocorreu um erro ao listar os membros.", ephemeral=True)
             except discord.NotFound: # Handle case where interaction expires just before sending error
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
    min_membros: Optional[app_commands.Range[int, 1, 50]] = None, # Add range validation
    max_membros: Optional[app_commands.Range[int, 1, 50]] = None,
    min_nivel: Optional[app_commands.Range[int, 1, None]] = None,
    localizacao: Optional[str] = None
):
    """Search for clans with filters."""
    await interaction.response.defer()
    search_params = {'name': nome, 'limit': 20} # Increase limit slightly

    if min_membros is not None: search_params['min_members'] = min_membros
    if max_membros is not None: search_params['max_members'] = max_membros
    if min_nivel is not None: search_params['min_clan_level'] = min_nivel
    if localizacao:
        try:
            # Attempt to fetch location ID case-insensitively might be better
            # For now, use as is
            location_id = await fetch_location_id(localizacao)
            search_params['location'] = location_id
            logger.info(f"Busca de clã usando localização ID {location_id} para '{localizacao}'.")
        except ValueError as e:
            await interaction.followup.send(f"Erro ao buscar localização: {e}", ephemeral=True)
            return

    try:
        logger.info(f"Buscando clãs com parâmetros: {search_params}")
        clans = await bot.coc_client.search_clans(**search_params)

        if not clans:
            await interaction.followup.send(f"Nenhum clã encontrado com os critérios fornecidos.")
            return

        embed = discord.Embed(
            title=f"Resultados da busca por '{nome}'",
            description="Clãs encontrados:",
            color=discord.Color.blue()
        )
        results_count = 0
        output_lines = []
        for i, clan in enumerate(clans):
            c_name = getattr(clan, 'name', 'Nome Desconhecido')
            c_tag = getattr(clan, 'tag', 'Tag Desconhecida')
            c_level = getattr(clan, 'level', '?')
            c_members = getattr(clan, 'member_count', '?')
            c_points = getattr(clan, 'points', '?')
            c_loc = getattr(getattr(clan, 'location', None), 'name', 'N/A')
            c_freq = getattr(clan, 'war_frequency', 'N/A').capitalize() if hasattr(clan, 'war_frequency') else 'N/A'


            line = f"{i+1}. **{c_name}** (`{c_tag}`)\n" \
                   f"   Nível: {c_level} | Membros: {c_members}/50 | Pontos: {c_points}🏆 | Local: {c_loc}"
            output_lines.append(line)
            results_count += 1
            if results_count >= 10: # Limit to 10 clans in the output for readability
                 break

        # Combine lines into description or fields checking limits
        output_text = "\n".join(output_lines)
        if len(output_text) <= 4096: # Max description length
             embed.description = output_text
        else:
             # Fallback to fields if description too long (less likely with 10 results)
             embed.description="Muitos resultados, exibindo os 10 primeiros:"
             for line in output_lines:
                 # Split line into name/value for field (crude split)
                 parts = line.split('\n   ', 1)
                 field_name = parts[0]
                 field_value = '   ' + parts[1] if len(parts) > 1 else "Detalhes indisponíveis"
                 if len(embed) + len(field_name) + len(field_value) < 6000 and len(embed.fields) < 25:
                      embed.add_field(name=field_name, value=field_value, inline=False)
                 else:
                      break


        embed.set_footer(text=f"Exibindo {results_count} de {len(clans)} resultados encontrados.")
        embed.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed)

    except ValueError as e: # Catch location error
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
        players = await bot.coc_client.search_players(name=nome, limit=20) # API limit might be lower

        if not players:
            await interaction.followup.send(f"Nenhum jogador encontrado com o nome '{nome}'.")
            return

        embed = discord.Embed(
            title=f"Resultados da busca por '{nome}'",
            description="Jogadores encontrados:",
            color=discord.Color.green()
        )
        results_count = 0
        output_lines = []

        for i, player in enumerate(players):
            p_name = getattr(player, 'name', 'Nome Desconhecido')
            p_tag = getattr(player, 'tag', 'Tag Desconhecida')
            p_th = getattr(player, 'town_hall', '?')
            p_trophies = getattr(player, 'trophies', '?')
            p_level = getattr(player, 'exp_level', '?')
            p_clan = getattr(player, 'clan', None)
            clan_info = f"{p_clan.name}" if p_clan and hasattr(p_clan, 'name') else "Sem clã"
            league_name = getattr(getattr(player, 'league', None), 'name', 'Sem Liga')

            line = f"{i+1}. **{p_name}** (`{p_tag}`) | CV{p_th} | Nível {p_level}\n" \
                   f"   {p_trophies}🏆 ({league_name}) | Clã: {clan_info}"
            output_lines.append(line)
            results_count += 1
            if results_count >= 10: # Limit display
                break

        # Combine into description
        output_text = "\n".join(output_lines)
        if len(output_text) <= 4096:
             embed.description = output_text
        else:
             # Fallback if needed (unlikely for 10 players)
             embed.description = "Muitos resultados, exibindo os 10 primeiros."
             # Could add fields here as fallback

        embed.set_footer(text=f"Exibindo {results_count} de {len(players)} resultados encontrados.")
        embed.timestamp = datetime.datetime.now(TIMEZONE)
        await interaction.followup.send(embed=embed)

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
        clan = await get_clan_data_with_cache(target_tag)

        base_embed = discord.Embed(
            title=f"🎁 Ranking de Doações - {clan.name}",
            color=discord.Color.gold()
        )
        if hasattr(clan, 'badge') and clan.badge: base_embed.set_thumbnail(url=clan.badge.url)

        rank_list = []
        if hasattr(clan, 'members') and clan.members:
             members = sorted(clan.members, key=lambda m: getattr(m, 'donations', 0), reverse=True)
             for i, member in enumerate(members):
                name = getattr(member, 'name', 'Nome Desconhecido')
                donations = getattr(member, 'donations', 0)
                received = getattr(member, 'received', 0)
                ratio = donations / received if received > 0 else float(donations) # Avoid division by zero, treat as float
                rank_list.append(f"{i+1}. **{name}** - Doou: {donations} / Recebeu: {received} (Ratio: {ratio:.2f})")
        else:
             rank_list.append("Não foi possível buscar os membros para o ranking.")

        await interaction.followup.send(embed=base_embed)
        splitter_base = discord.Embed(color=discord.Color.gold())
        await send_embeds_splitted(interaction.channel, splitter_base, "Ranking de Doações", rank_list)

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
        clan = await get_clan_data_with_cache(target_tag)

        base_embed = discord.Embed(
            title=f"🏆 Ranking de Troféus - {clan.name}",
            color=discord.Color.purple() # Changed color
        )
        if hasattr(clan, 'badge') and clan.badge: base_embed.set_thumbnail(url=clan.badge.url)

        rank_list = []
        if hasattr(clan, 'members') and clan.members:
             members = sorted(clan.members, key=lambda m: getattr(m, 'trophies', 0), reverse=True)
             for i, member in enumerate(members):
                name = getattr(member, 'name', 'Nome Desconhecido')
                trophies = getattr(member, 'trophies', 0)
                league_name = getattr(getattr(member, 'league', None), 'name', 'Sem Liga')
                rank_list.append(f"{i+1}. **{name}** - {trophies}🏆 ({league_name})")
        else:
             rank_list.append("Não foi possível buscar os membros para o ranking.")

        await interaction.followup.send(embed=base_embed)
        splitter_base = discord.Embed(color=discord.Color.purple())
        await send_embeds_splitted(interaction.channel, splitter_base, "Ranking de Troféus", rank_list)

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
        clan = await get_clan_data_with_cache(target_tag)

        base_embed = discord.Embed(
            title=f"🏠 Ranking de Casa de Vila - {clan.name}",
            color=discord.Color.dark_orange() # Changed color
        )
        if hasattr(clan, 'badge') and clan.badge: base_embed.set_thumbnail(url=clan.badge.url)

        rank_list = []
        if hasattr(clan, 'members') and clan.members:
             members = sorted(clan.members, key=lambda m: (getattr(m, 'town_hall', 0), getattr(m, 'exp_level', 0)), reverse=True)
             for i, member in enumerate(members):
                 name = getattr(member, 'name', 'Nome Desconhecido')
                 th = getattr(member, 'town_hall', '?')
                 level = getattr(member, 'exp_level', '?')
                 rank_list.append(f"{i+1}. **{name}** - CV{th} (Nível {level})")
        else:
             rank_list.append("Não foi possível buscar os membros para o ranking.")

        await interaction.followup.send(embed=base_embed)
        splitter_base = discord.Embed(color=discord.Color.dark_orange())
        await send_embeds_splitted(interaction.channel, splitter_base, "Ranking de CV", rank_list)

    except ValueError as e:
        await interaction.followup.send(str(e), ephemeral=True)
    except Exception as e:
        logger.error(f"Erro ao buscar ranking de CV para {target_tag}: {e}", exc_info=True)
        await interaction.followup.send("Ocorreu um erro ao buscar o ranking de CV.", ephemeral=True)


# Setup functions
async def setup_web_server():
    """Setup basic web server for health checks (Render)."""
    app = web.Application()
    async def health_handler(request):
        logger.debug("Health check endpoint '/' accessed.")
        return web.Response(text="Bot is running!")
    app.router.add_get("/", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    try:
         await site.start()
         logger.info(f"Servidor web para health check iniciado em 0.0.0.0:{port}")
         return runner
    except OSError as e:
        logger.error(f"Falha ao iniciar servidor web na porta {port}: {e} - Verifique se a porta está em uso.")
        return None # Indicate failure
    except Exception as e:
         logger.error(f"Erro inesperado ao iniciar servidor web: {e}", exc_info=True)
         return None

# ========================================================================================= #
# =============================  INÍCIO DA SEÇÃO MODIFICADA  ============================= #
# ========================================================================================= #
async def setup_hook():
    """Setup hook for the bot, called before bot logs in."""
    logger.info("Executando setup_hook...")

    # --- Initialize CoC Client ---
    logger.info("Inicializando cliente CoC...")
    bot.coc_client = coc.EventsClient()
    max_retries = 3
    retry_delay = 5
    login_success = False
    for attempt in range(max_retries):
        try:
            logger.info(f"Tentativa de login CoC ({attempt + 1}/{max_retries})...")
            # Ensure EMAIL/PASSWORD are provided
            if not COC_EMAIL or not COC_PASSWORD:
                 logger.error("COC_EMAIL ou COC_PASSWORD não definidos no ambiente. Login CoC abortado.")
                 break # Stop trying if no credentials
            await bot.coc_client.login(COC_EMAIL, COC_PASSWORD)
            logger.info("Login CoC bem-sucedido!")
            login_success = True
            break
        except coc.InvalidCredentials as e:
             logger.error(f"Login CoC Falhou: Credenciais Inválidas. Verifique COC_EMAIL/COC_PASSWORD. {e}")
             break # Don't retry on invalid credentials
        except coc.Maintenance as e:
             logger.warning(f"API CoC em manutenção: {e}. Funcionalidades CoC estarão indisponíveis.")
             # login_success remains False, events won't register
             break # Don't retry during maintenance
        except asyncio.TimeoutError:
             logger.error(f"Timeout no login CoC (Tentativa {attempt + 1}).")
             if attempt < max_retries - 1: await asyncio.sleep(retry_delay)
        except Exception as e:
             logger.error(f"Erro inesperado no login CoC (Tentativa {attempt + 1}): {e}", exc_info=True)
             if attempt < max_retries - 1: await asyncio.sleep(retry_delay)

    if not login_success:
         logger.error("Não foi possível logar no CoC após todas as tentativas ou devido a erro/manutenção.")
         # Bot will continue, but CoC features won't work
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

    # --- Start Health Check Web Server ---
    logger.info("Configurando servidor web para health check...")
    bot.web_runner = await setup_web_server() # Store the runner
    if bot.web_runner:
        logger.info("Servidor web configurado.")
    else:
        logger.warning("Falha ao configurar o servidor web.")

    # --- Sincronizar comandos de aplicativo ---
    # Movido de on_ready() para setup_hook() para melhor prática e robustez.
    # Os comandos são adicionados à bot.tree no escopo global, então já estarão disponíveis aqui.
    logger.info("Tentando sincronizar comandos de aplicativo (/) no setup_hook...")
    synced_commands_list = [] # Renomeada para evitar conflito com o módulo commands
    try:
        if TEST_GUILD_ID:
            try:
                guild_id_obj = discord.Object(id=int(TEST_GUILD_ID))
                # Para desenvolvimento, limpar comandos antigos no servidor de teste antes de sincronizar pode ser útil.
                # bot.tree.clear_commands(guild=guild_id_obj)
                # await bot.tree.sync(guild=guild_id_obj) # Sincroniza e sobrescreve
                logger.info(f"Sincronizando comandos para o servidor de teste ID: {TEST_GUILD_ID}")
                synced_commands_list = await bot.tree.sync(guild=guild_id_obj)
                logger.info(f"{len(synced_commands_list)} comandos (/) sincronizados com o servidor de teste (ID: {TEST_GUILD_ID}).")
            except (ValueError, TypeError):
                logger.error(f"TEST_GUILD_ID ('{TEST_GUILD_ID}') é inválido. Tentando sincronizar globalmente...")
                synced_commands_list = await bot.tree.sync()
                logger.info(f"{len(synced_commands_list)} comandos (/) sincronizados globalmente.")
        else:
            logger.info("Nenhum TEST_GUILD_ID definido. Sincronizando comandos globalmente...")
            synced_commands_list = await bot.tree.sync()
            logger.info(f"{len(synced_commands_list)} comandos (/) sincronizados globalmente.")

        if not synced_commands_list:
            logger.warning("Nenhum comando de aplicativo foi sincronizado. Verifique as definições e se foram adicionados à tree.")
        else:
            # Log dos nomes dos comandos sincronizados para depuração
            # nomes_comandos = [cmd.name for cmd in synced_commands_list]
            # logger.info(f"Comandos sincronizados: {nomes_comandos}")
            pass


    except discord.Forbidden as e:
        logger.error(f"Erro 403 Forbidden ao sincronizar comandos (/): {e}. Verifique as permissões do bot (application.commands).")
    except discord.HTTPException as e:
        logger.error(f"Erro HTTP ao sincronizar comandos (/): {e.status} - {e.text}", exc_info=True)
    except Exception as e:
        logger.error(f"Erro inesperado ao sincronizar comandos (/) no setup_hook: {e}", exc_info=True)

    logger.info("setup_hook concluído.")
# ========================================================================================= #
# ==============================  FIM DA SEÇÃO MODIFICADA  =============================== #
# ========================================================================================= #

# Main execution block
async def main():
    """Main function to start the bot."""
    # Assign the setup hook defined above
    bot.setup_hook = setup_hook

    async with bot: # Use bot as an async context manager
        try:
            if not DISCORD_TOKEN:
                 logger.critical("DISCORD_TOKEN não encontrado. O bot não pode iniciar.")
                 return # Stop execution

            logger.info("Iniciando conexão com o Discord...")
            await bot.start(DISCORD_TOKEN)

        except discord.LoginFailure:
             logger.critical("Login no Discord Falhou: Token inválido. Verifique DISCORD_TOKEN.")
        except discord.PrivilegedIntentsRequired as e:
             # Ensure shard_id is accessed correctly if available
             shard_info = f"(Shard ID: {e.shard_id})" if hasattr(e, 'shard_id') and e.shard_id is not None else ""
             logger.critical(f"Intents Privilegiadas {shard_info} não habilitadas no Portal do Desenvolvedor Discord.")
        except Exception as e:
            # Catch any other unexpected errors during bot run
            logger.critical(f"Erro crítico durante a execução do bot: {e}", exc_info=True)
        finally:
            logger.info("Iniciando processo de desligamento do bot...")
            # --- Cleanup ---
            # Stop background tasks gracefully
            if 'check_war_end_report_task' in globals() and check_war_end_report_task.is_running():
                 logger.info("Parando tarefa 'check_war_end_report_task'...")
                 check_war_end_report_task.cancel()
                 try:
                     # Wait for the task to acknowledge cancellation
                     await asyncio.sleep(1) # Give it a moment
                     logger.info("Tarefa 'check_war_end_report_task' cancelada.")
                 except asyncio.CancelledError:
                     logger.info("Tarefa 'check_war_end_report_task' foi cancelada com sucesso.")
                 except Exception as e:
                     logger.error(f"Erro durante cancelamento da tarefa 'check_war_end_report_task': {e}")


            # Cleanup web server
            if hasattr(bot, "web_runner") and bot.web_runner:
                logger.info("Limpando servidor web...")
                await bot.web_runner.cleanup()
                logger.info("Servidor web limpo.")

            # Close CoC client session
            # Check if http client exists and is not already closed
            if hasattr(bot, "coc_client") and bot.coc_client.http and hasattr(bot.coc_client.http, 'closed') and not bot.coc_client.http.closed:
                logger.info("Fechando cliente CoC...")
                await bot.coc_client.close()
                logger.info("Cliente CoC fechado.")
            elif hasattr(bot, "coc_client") and not bot.coc_client.http:
                 logger.info("Cliente CoC não foi logado, não há sessão para fechar.")
            else:
                 logger.info("Cliente CoC já estava fechado ou não inicializado.")


            logger.info("Desligamento do bot concluído.")


# Custom asyncio exception handler
def handle_asyncio_exception(loop, context):
    # context["message"] will always be there; but context["exception"] may not
    msg = context.get("exception", context["message"])
    # Log specific details if available (e.g., future)
    future = context.get('future')
    if future:
        logger.error(f"Erro não tratado no loop asyncio (Future: {future}): {msg}", exc_info=context.get('exception'))
    else:
        logger.error(f"Erro não tratado no loop asyncio: {msg}", exc_info=context.get('exception'))

# Run the bot using asyncio
if __name__ == "__main__":
    # Pre-run checks
    required_vars = ["DISCORD_TOKEN", "COC_EMAIL", "COC_PASSWORD", "CLAN_TAG", "CHANNEL_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
         logger.critical(f"Variáveis de ambiente obrigatórias faltando: {', '.join(missing_vars)}. Verifique .env ou configuração.")
    else:
        try:
            logger.info("Iniciando loop de eventos asyncio para main()...")
            # Setup asyncio exception handler for better debugging of loop errors
            # Use asyncio.run for simplified loop management
            asyncio.run(main())

        except KeyboardInterrupt:
            logger.info("Bot interrompido manualmente (KeyboardInterrupt).")
        except RuntimeError as e:
             # Catch potential loop errors during shutdown (e.g., "Event loop is closed")
             if "Event loop is closed" in str(e):
                  logger.info("Loop de eventos fechado durante o desligamento (normal).")
             else:
                  logger.warning(f"RuntimeError durante execução do loop: {e}", exc_info=True)
        except Exception as e:
            logger.critical(f"Erro fatal fora do loop principal do bot: {e}", exc_info=True)
        finally:
            logger.info("Programa finalizado.")
