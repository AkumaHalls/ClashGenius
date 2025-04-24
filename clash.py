# -*- coding: utf-8 -*-
# Versão 16.0.22 - Substituída display_attacks_remaining_slash pela versão funcional da v15

import discord
from discord import app_commands
from discord.ext import commands
import coc
from coc import utils as coc_utils
from coc import errors as coc_errors
import asyncio
import os
import logging
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from aiohttp import web
from typing import Optional, List

# Carrega variáveis de ambiente
load_dotenv()

# --- Configuração de Logging ---
log_formatter = logging.Formatter('%(asctime)s-%(levelname)s-[%(funcName)s]: %(message)s')
file_handler = logging.FileHandler("bot.log", encoding='utf-8')
file_handler.setFormatter(log_formatter)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logging.getLogger("coc").setLevel(logging.INFO)
logging.getLogger("coc.events").setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler], force=True)
logger = logging.getLogger("clash-bot")
logger.info("Logging configurado em nível INFO.")

# --- Configurações e Validação ---
TOKEN = os.getenv('DISCORD_TOKEN')
EMAIL = os.getenv('COC_EMAIL')
PASSWORD = os.getenv('COC_PASSWORD')
CLAN_TAG_ENV = os.getenv('CLAN_TAG')
CHANNEL_ID_STR = os.getenv('CHANNEL_ID')
PORT = int(os.environ.get("PORT", 10000))

if not all([TOKEN, CLAN_TAG_ENV, CHANNEL_ID_STR]): logger.critical("FATAL: TOKEN, CLAN_TAG ou CHANNEL_ID faltando no .env"); exit("Erro Conf.")
if not EMAIL or not PASSWORD: logger.critical("FATAL: Email/Senha CoC não configurados."); exit("Erro Conf: Credenciais CoC faltando.")
try: CHANNEL_ID = int(CHANNEL_ID_STR)
except ValueError: logger.critical(f"FATAL: CHANNEL_ID inválido ('{CHANNEL_ID_STR}')."); exit("Erro Conf.")
CLAN_TAGS_TO_MONITOR = []
if not coc_utils.is_valid_tag(CLAN_TAG_ENV): logger.critical(f"FATAL: CLAN_TAG '{CLAN_TAG_ENV}' inválido no .env."); exit("Erro Conf.")
CLAN_TAGS_TO_MONITOR.append(coc_utils.correct_tag(CLAN_TAG_ENV))
MONITORED_CLAN_NAME = CLAN_TAG_ENV

# --- Timezone ---
try: TIMEZONE = pytz.timezone('America/Sao_Paulo'); logger.info(f"Timezone: {TIMEZONE}")
except pytz.UnknownTimeZoneError: logger.error("TZ 'America/Sao_Paulo' não encontrado. Usando UTC."); TIMEZONE = pytz.utc

# --- Bot Discord ---
intents = discord.Intents.default(); intents.message_content = True; intents.members = True; intents.guilds = True
bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), intents=intents, help_command=None)

# --- Emojis ---
emojis = {
    'donation': '🎁', 'join': '➡️', 'leave': '⬅️', 'war_win': '🏆', 'war_lose': '😥',
    'war_tie': '🤝', 'war_attack': '⚔️', 'war_defense': '🛡️', 'raid': '🔥', 'level_up': '⭐',
    'trophy': '🏆', 'time': '⏰', 'clan_capital': '🏰', 'missed_attack': '❌', 'info': 'ℹ️',
    'error': '❌', 'success': '✅', 'warning': '⚠️', 'league': '🌟',
    'received': '📥', 'progress': '📊', 'destruction': '💥', 'sync': '🔄', 'admin': '🛠️',
    'search': '🔍', 'ranking': '📊',
    'role': '👤', 'label': '🏷️', 'equipment': '⚙️', 'achievement': '🏅',
    'upgrade': '⏫'
}

# --- Cliente CoC (EventsClient) ---
coc_client: Optional[coc.EventsClient] = None

# --- Caches ---
member_cache = {}

# --- Variável Global para Canal ---
log_channel: Optional[discord.TextChannel] = None

# --- Servidor Web ---
async def health_check(request):
    return web.Response(text="ClashGenius v16 is running!")

@bot.event
async def setup_hook():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    try:
        await site.start(); logger.info(f"Servidor web iniciado em http://0.0.0.0:{PORT}")
        bot.web_runner = runner; bot.web_site = site
    except Exception as e: logger.critical(f"Falha ao iniciar servidor web na porta {PORT}: {e}", exc_info=True); pass

@bot.event
async def before_closing():
    global coc_client
    logger.info("Recebido sinal para encerrar...")
    if hasattr(bot, 'web_runner'):
        logger.info("Encerrando servidor web...");
        try: await bot.web_runner.cleanup(); logger.info("Servidor web encerrado.")
        except Exception as e: logger.error(f"Erro ao encerrar servidor web: {e}", exc_info=True)
    if coc_client:
        logger.info("Fechando cliente CoC EventsClient..."); coc_client.close(); logger.info("Cliente CoC EventsClient fechado.")
    logger.info("Bot encerrado.")

# --- Inicialização CoC EventsClient ---
async def initialize_coc_client():
    global coc_client, CLAN_TAGS_TO_MONITOR
    logger.info("--- Iniciando Login CoC EventsClient ---")
    if not EMAIL or not PASSWORD: logger.critical("Email/Senha CoC não encontrados."); return False
    last_error = None
    for attempt in range(1, 4):
        try:
            logger.info(f"[Tentativa {attempt}/3] Criando EventsClient...")
            temp_client = coc.EventsClient(throttle_limit=20)
            temp_client._auto_register = False
            logger.info(f"[Tentativa {attempt}/3] Login com Email/Senha...")
            await asyncio.wait_for(temp_client.login(EMAIL, PASSWORD), timeout=90.0)
            coc_client = temp_client
            logger.info(f"[Tentativa {attempt}/3] Login CoC EventsClient OK.")
            register_coc_events(coc_client)
            logger.info(f"Adicionando clã(s) {CLAN_TAGS_TO_MONITOR} ao monitoramento...")
            coc_client.add_clan_updates(*CLAN_TAGS_TO_MONITOR)
            coc_client.add_war_updates(*CLAN_TAGS_TO_MONITOR)
            logger.info("Eventos Clã, Guerra e Clãs registrados no EventsClient.")
            return True
        except coc_errors.InvalidCredentials as e: logger.error(f"[Tentativa {attempt}/3] Falha autenticação (InvalidCredentials): {e}"); last_error = e; return False
        except coc_errors.Maintenance as e: logger.warning(f"[Tentativa {attempt}/3] API CoC em manutenção (EventsClient): {e}"); last_error = e
        except asyncio.TimeoutError: logger.error(f"[Tentativa {attempt}/3] Timeout login EventsClient."); last_error = asyncio.TimeoutError("Timeout login API CoC.")
        except coc_errors.ClashOfClansException as e:
             logger.error(f"[Tentativa {attempt}/3] Erro API CoC ({type(e).__name__}): {e}", exc_info=True); last_error = e
             if isinstance(e, coc_errors.Forbidden): return False
        except Exception as e: logger.error(f"[Tentativa {attempt}/3] Erro login/registro eventos: {e}", exc_info=True); last_error = e
        if attempt < 3: wait_time = 30 * attempt; logger.info(f"Aguardando {wait_time}s..."); await asyncio.sleep(wait_time)
    logger.critical(f"--- Falha login CoC EventsClient após {attempt} tentativas. Último erro: {last_error} ---"); coc_client = None; return False

# --- Funções Auxiliares ---
async def get_clan_data(tag=None, timeout=30.0):
    global coc_client
    client_to_use = coc_client
    if not client_to_use:
        logger.warning("Cliente CoC principal inválido em get_clan_data. Tentando cliente temporário.")
        try:
            async with coc.Client(timeout=timeout) as temp_client:
                await temp_client.login(EMAIL, PASSWORD)
                client_to_use = temp_client
        except Exception as e_temp:
            logger.error(f"Falha ao criar/logar cliente temporário em get_clan_data: {e_temp}")
            return None
    if not client_to_use: return None
    target_tag = tag or (CLAN_TAGS_TO_MONITOR[0] if CLAN_TAGS_TO_MONITOR else None)
    if not target_tag: logger.error("Tag clã não definida."); return None
    if not coc_utils.is_valid_tag(target_tag): raise coc.InvalidTag(f"Tag clã inválida: {target_tag}")
    try:
        logger.debug(f"Buscando dados clã: {target_tag} (Timeout: {timeout}s)")
        clan = await asyncio.wait_for(client_to_use.get_clan(target_tag), timeout=timeout)
        logger.debug(f"Dados clã '{getattr(clan, 'name', target_tag)}' recebidos."); return clan
    except coc.NotFound: logger.error(f"Clã '{target_tag}' não encontrado."); raise
    except coc.Maintenance as e: logger.warning(f"API CoC em manutenção (clã '{target_tag}'): {e}"); raise
    except coc.ClashOfClansException as e: logger.warning(f"Erro API CoC ({type(e).__name__}) clã '{target_tag}': {e}"); raise
    except asyncio.TimeoutError: logger.error(f"Timeout ({timeout}s) clã '{target_tag}'."); raise
    except Exception as e: logger.error(f"Erro Inesperado ({type(e).__name__}) clã '{target_tag}': {e}", exc_info=True); raise

async def get_player_data(tag, timeout=20.0):
    global coc_client
    client_to_use = coc_client
    if not client_to_use:
        logger.warning("Cliente CoC principal inválido em get_player_data. Tentando cliente temporário.")
        try:
            async with coc.Client(timeout=timeout) as temp_client:
                await temp_client.login(EMAIL, PASSWORD)
                client_to_use = temp_client
        except Exception as e_temp:
            logger.error(f"Falha ao criar/logar cliente temporário em get_player_data: {e_temp}")
            return None
    if not client_to_use: return None
    player_tag = coc_utils.correct_tag(tag)
    if not coc_utils.is_valid_tag(player_tag): raise coc.InvalidTag(f"Tag jogador inválida: {player_tag}")
    try:
        logger.debug(f"Buscando dados jogador: {player_tag} (Timeout: {timeout}s)")
        player = await asyncio.wait_for(client_to_use.get_player(player_tag), timeout=timeout)
        logger.debug(f"Dados jogador '{getattr(player, 'name', player_tag)}' recebidos."); return player
    except coc.NotFound: logger.error(f"Jogador '{player_tag}' não encontrado."); raise
    except coc.Maintenance as e: logger.warning(f"API CoC em manutenção (jogador '{player_tag}'): {e}"); raise
    except coc.ClashOfClansException as e: logger.warning(f"Erro API CoC ({type(e).__name__}) jogador '{player_tag}': {e}"); raise
    except asyncio.TimeoutError: logger.error(f"Timeout ({timeout}s) jogador '{player_tag}'."); raise
    except Exception as e: logger.error(f"Erro Inesperado ({type(e).__name__}) jogador '{player_tag}': {e}", exc_info=True); raise

async def send_log_embed(embed: discord.Embed, add_timestamp=True):
    global log_channel
    if not log_channel and CHANNEL_ID:
        try: log_channel = await bot.fetch_channel(CHANNEL_ID); logger.info(f"Canal log ({CHANNEL_ID}) cacheado.")
        except (discord.NotFound, discord.Forbidden): logger.error(f"Canal log ID {CHANNEL_ID} inválido."); log_channel = None
        except Exception as e: logger.error(f"Erro buscar canal log ({CHANNEL_ID}): {e}"); return
    if log_channel:
        try:
            if add_timestamp and not embed.timestamp: embed.timestamp = datetime.now(TIMEZONE)
            await log_channel.send(embed=embed)
        except discord.Forbidden: logger.error(f"Sem permissão canal {log_channel.name} ({CHANNEL_ID}).")
        except discord.HTTPException as e: logger.error(f"Erro HTTP enviar log embed: {e.status} {e.code} - {e.text}")
        except Exception as e: logger.error(f"Erro enviar log embed: {e}", exc_info=True)
    else:
        logger.warning(f"Log Embed não enviado: Canal ({CHANNEL_ID}) inválido ou inacessível.")

async def send_embeds_splitted(channel: discord.TextChannel, base_embed: discord.Embed, field_name: str, items_list: list, max_len: int = 1024, max_items_per_embed: int = 25):
    """Envia uma lista de itens dividida em múltiplos embeds/campos se necessário."""
    if not channel:
        logger.error("send_embeds_splitted: Canal inválido fornecido.")
        return
    if not items_list:
        logger.debug(f"send_embeds_splitted: Lista de itens para '{field_name}' está vazia.")
        return

    current_embed = base_embed.copy()
    if len(current_embed.fields) > 0:
        logger.debug("send_embeds_splitted: Limpando campos preexistentes do embed base.")
        current_embed.clear_fields()

    current_field_value = ""
    part_count = 1
    embed_count = 1
    first_field_added_to_current_embed = False

    for i, item in enumerate(items_list):
        item_str = str(item)
        item_line = item_str + "\n"

        if len(item_line) > max_len:
            logger.warning(f"Item muito longo para caber em um campo: '{item_str[:50]}...' Pulando.")
            continue

        if len(current_field_value) + len(item_line) > max_len and current_field_value:
            field_title = f"{field_name} (Parte {part_count})" if len(items_list) > 1 else field_name
            current_embed.add_field(name=field_title, value=current_field_value, inline=False)
            first_field_added_to_current_embed = True
            part_count += 1
            current_field_value = ""

            if len(current_embed.fields) >= max_items_per_embed:
                try:
                    logger.debug(f"Enviando embed {embed_count} (cheio) para '{field_name}'")
                    await channel.send(embed=current_embed)
                    embed_count += 1
                    current_embed = base_embed.copy().clear_fields()
                    first_field_added_to_current_embed = False
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.error(f"Erro ao enviar embed dividido {embed_count}: {e}", exc_info=True)
                    return

        current_field_value += item_line

    if current_field_value:
        field_title = f"{field_name} (Parte {part_count})" if (len(items_list) > 1 or part_count > 1 or embed_count > 1) else field_name
        if len(current_embed.fields) < max_items_per_embed:
            current_embed.add_field(name=field_title, value=current_field_value, inline=False)
            first_field_added_to_current_embed = True
        else:
            try:
                if first_field_added_to_current_embed:
                     logger.debug(f"Enviando embed {embed_count} (antes do último campo) para '{field_name}'")
                     await channel.send(embed=current_embed)
                     embed_count += 1
                current_embed = base_embed.copy().clear_fields()
                current_embed.add_field(name=field_title, value=current_field_value, inline=False)
                first_field_added_to_current_embed = True
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Erro ao enviar embed antes do último campo {embed_count}: {e}", exc_info=True)
                return

    if len(current_embed.fields) > 0 and first_field_added_to_current_embed:
        try:
            logger.debug(f"Enviando último embed {embed_count} para '{field_name}'")
            await channel.send(embed=current_embed)
        except Exception as e:
            logger.error(f"Erro ao enviar último embed {embed_count}: {e}", exc_info=True)


async def fetch_location_id(location_name_or_id: str) -> Optional[int or str]:
    """Tenta encontrar o ID de uma localização pelo nome ou retorna o ID/string global."""
    global coc_client
    if not coc_client: return None
    if location_name_or_id.isdigit():
        try: return int(location_name_or_id)
        except ValueError: return None

    if location_name_or_id.lower() == "global":
        return "global"

    try:
        async with coc.Client(timeout=10) as temp_loc_client:
            login_success = False
            try:
                await temp_loc_client.login(EMAIL, PASSWORD)
                login_success = True
            except coc_errors.InvalidCredentials:
                logger.warning("Login falhou no client temporário de fetch_location_id, tentando com key...")
                try:
                    key = coc_client.http.keys[0] if coc_client and coc_client.http.keys else None
                    if not key: logger.error("Nenhuma key disponível para client temporário em fetch_location_id."); return None
                    await temp_loc_client.login_with_keys(key)
                    login_success = True
                except Exception as e_key: logger.error(f"Erro ao logar com key no client temporário fetch_location_id: {e_key}")
            except Exception as e_login: logger.error(f"Erro inesperado no login do client temporário fetch_location_id: {e_login}")

            if not login_success: logger.error("Falha na autenticação do client temporário para fetch_location_id."); return None

            locations = await temp_loc_client.search_locations(name=location_name_or_id, limit=1)
            if locations: return locations[0].id
            else: return None
    except Exception as e:
        logger.warning(f"Erro ao buscar ID da localização '{location_name_or_id}': {e}")
        return None

# --- Event Handlers ---
def register_coc_events(client: coc.EventsClient):
    logger.info("Registrando Handlers de Eventos CoC...")

    # --- Handlers Clã ---
    @client.event
    @coc.ClanEvents.member_join()
    async def member_join(member: coc.ClanMember, clan: coc.Clan):
        global member_cache; tag = getattr(member, 'tag', None); name = getattr(member, 'name', '?'); clan_tag = getattr(clan, 'tag', '?'); clan_name = getattr(clan, 'name', '?'); logger.info(f"[EVENT] {name} ({tag}) ENTROU em {clan_name} ({clan_tag})")
        if tag: member_cache[tag] = {'name': name, 'role': str(member.role), 'trophies': member.trophies, 'league': member.league.name if member.league else 'N/A'}
        embed = discord.Embed(title=f"{emojis['join']} Entrada no Clã", description=f"**{name}** (`{tag}`) entrou em **{clan_name}**!", color=discord.Color.green())
        details = [];
        if hasattr(member, 'town_hall'): details.append(f"CV{member.town_hall}")
        if hasattr(member, 'exp_level'): details.append(f"Nível {member.exp_level}")
        if hasattr(member, 'trophies'): details.append(f"{member.trophies:,}{emojis['trophy']}")
        if hasattr(member, 'league') and member.league: details.append(member.league.name)
        if details: embed.add_field(name="Detalhes", value=" | ".join(details), inline=False)
        if hasattr(member, 'league') and member.league and member.league.icon: embed.set_thumbnail(url=member.league.icon.url)
        embed.set_footer(text=f"Clã: {clan_name} ({clan_tag})"); await send_log_embed(embed)

    @client.event
    @coc.ClanEvents.member_leave()
    async def member_leave(member: coc.ClanMember, clan: coc.Clan):
        global member_cache; tag = getattr(member, 'tag', None); clan_tag = getattr(clan, 'tag', '?'); clan_name = getattr(clan, 'name', '?'); cached_info = member_cache.pop(tag, None) if tag else None; name = cached_info.get('name', '?') if cached_info else getattr(member, 'name', '?')
        logger.info(f"[EVENT] {name} ({tag}) SAIU de {clan_name} ({clan_tag})")
        embed = discord.Embed(title=f"{emojis['leave']} Saída do Clã", description=f"**{name}** (`{tag}`) saiu de **{clan_name}**.", color=discord.Color.red())
        if cached_info:
             details = [];
             if 'role' in cached_info: details.append(f"Cargo: {cached_info['role']}")
             if 'trophies' in cached_info: details.append(f"{cached_info['trophies']:,}{emojis['trophy']}")
             if 'league' in cached_info: details.append(cached_info['league'])
             if details: embed.add_field(name="Últimos Dados Conhecidos", value=" | ".join(details), inline=False)
        embed.set_footer(text=f"Clã: {clan_name} ({clan_tag})"); await send_log_embed(embed)

    @client.event
    @coc.ClanEvents.member_donations()
    async def member_donations(old_member: coc.ClanMember, member: coc.ClanMember):
        clan = member.clan; tag = getattr(member, 'tag', '?'); name = getattr(member, 'name', '?'); clan_tag = getattr(clan, 'tag', '?'); clan_name = getattr(clan, 'name', '?'); donated = member.donations - old_member.donations
        if donated <= 0: return
        logger.info(f"[EVENT] {name} ({tag}) doou {donated} tropas em {clan_name}")
        embed = discord.Embed(description=f"{emojis['donation']} `{name}` doou **{donated}** tropas (Total: {member.donations:,}).", color=discord.Color.blue())
        embed.set_footer(text=f"Clã: {clan_name}"); await send_log_embed(embed, add_timestamp=False)

    @client.event
    @coc.ClanEvents.member_received()
    async def member_received(old_member: coc.ClanMember, member: coc.ClanMember):
        clan = member.clan; tag = getattr(member, 'tag', '?'); name = getattr(member, 'name', '?'); clan_tag = getattr(clan, 'tag', '?'); clan_name = getattr(clan, 'name', '?'); received = member.received - old_member.received
        if received <= 0: return
        logger.info(f"[EVENT] {name} ({tag}) recebeu {received} tropas em {clan_name}")
        embed = discord.Embed(description=f"{emojis['received']} `{name}` recebeu **{received}** tropas (Total: {member.received:,}).", color=discord.Color.orange())
        embed.set_footer(text=f"Clã: {clan_name}"); await send_log_embed(embed, add_timestamp=False)

    @client.event
    @coc.ClanEvents.member_role_change()
    async def member_role_change(old_member: coc.ClanMember, member: coc.ClanMember):
        global member_cache; clan = member.clan; tag = getattr(member, 'tag', '?'); name = getattr(member, 'name', '?'); clan_tag = getattr(clan, 'tag', '?'); clan_name = getattr(clan, 'name', '?'); old_role = str(old_member.role) if hasattr(old_member, 'role') else '?'; new_role = str(member.role) if hasattr(member, 'role') else '?'
        if old_role == new_role: return
        logger.info(f"[EVENT] Cargo de {name} ({tag}) mudou de {old_role} para {new_role} em {clan_name}")
        if tag and tag in member_cache: member_cache[tag]['role'] = new_role
        embed = discord.Embed(title=f"{emojis['role']} Mudança de Cargo", description=f"O cargo de **{name}** (`{tag}`) foi alterado.", color=discord.Color.light_grey())
        embed.add_field(name="Cargo Anterior", value=old_role, inline=True); embed.add_field(name="Novo Cargo", value=new_role, inline=True); embed.set_footer(text=f"Clã: {clan_name} ({clan_tag})"); await send_log_embed(embed)

    @client.event
    @coc.ClanEvents.member_league_change()
    async def member_league_change(old_member: coc.ClanMember, member: coc.ClanMember):
        global member_cache; clan = member.clan; tag = getattr(member, 'tag', '?'); name = getattr(member, 'name', '?'); clan_tag = getattr(clan, 'tag', '?'); clan_name = getattr(clan, 'name', '?'); old_league = old_member.league.name if old_member.league else 'Nenhuma'; new_league = member.league.name if member.league else 'Nenhuma'
        if old_league == new_league: return
        logger.info(f"[EVENT] Liga de {name} ({tag}) mudou de {old_league} para {new_league} em {clan_name}")
        if tag and tag in member_cache: member_cache[tag]['league'] = new_league
        embed = discord.Embed(title=f"{emojis['league']} Mudança de Liga", description=f"**{name}** (`{tag}`) mudou de liga.", color=discord.Color.gold())
        embed.add_field(name="Liga Anterior", value=old_league, inline=True); embed.add_field(name="Nova Liga", value=new_league, inline=True)
        if member.league and member.league.icon: embed.set_thumbnail(url=member.league.icon.url)
        embed.set_footer(text=f"Clã: {clan_name} ({clan_tag})"); await send_log_embed(embed)

    @client.event
    @coc.ClanEvents.member_trophies_change()
    async def member_trophies_change(old_member: coc.ClanMember, member: coc.ClanMember):
        global member_cache; clan = member.clan; tag = getattr(member, 'tag', '?'); name = getattr(member, 'name', '?'); clan_tag = getattr(clan, 'tag', '?'); clan_name = getattr(clan, 'name', '?'); old_trophies = old_member.trophies; new_trophies = member.trophies; diff = new_trophies - old_trophies; sign = "+" if diff > 0 else ""
        if diff == 0: return
        logger.info(f"[EVENT] Troféus de {name} ({tag}): {old_trophies} -> {new_trophies} ({sign}{diff}) em {clan_name}")
        if tag and tag in member_cache: member_cache[tag]['trophies'] = new_trophies
        embed = discord.Embed(description=f"{emojis['trophy']} `{name}`: {old_trophies:,} → **{new_trophies:,}** ({sign}{diff})", color=discord.Color.gold() if diff > 0 else discord.Color.dark_grey())
        embed.set_footer(text=f"Clã: {clan_name}"); await send_log_embed(embed, add_timestamp=False)

    # --- Handlers Guerra ---
    @client.event
    @coc.WarEvents.war_attack()
    async def war_attack(attack: coc.WarAttack, war: coc.ClanWar):
        is_relevant_clan = (
            attack.attacker is not None and attack.attacker.clan is not None and attack.attacker.clan.tag in CLAN_TAGS_TO_MONITOR
        ) or (
            attack.defender is not None and attack.defender.clan is not None and attack.defender.clan.tag in CLAN_TAGS_TO_MONITOR
        )
        if not is_relevant_clan:
             logger.debug(f"[EVENT WarAtk] Ataque {attack.order} não pertence diretamente ao clã monitorado. Ignorando.")
             return
        if not attack.attacker or not attack.attacker.clan or attack.attacker.clan.tag not in CLAN_TAGS_TO_MONITOR:
            logger.debug(f"[EVENT WarAtk] Atacante {attack.attacker_tag} não é do clã monitorado. Ignorando notificação.")
            return

        attacker = attack.attacker
        defender = attack.defender

        att_name = getattr(attacker, 'name', 'Atacante?')
        att_tag = getattr(attacker, 'tag', '?')
        att_th = getattr(attacker, 'town_hall', '?')
        clan_tag = getattr(attacker.clan, 'tag', '?')

        def_tag = getattr(attack, 'defender_tag', '?')
        def_name = "Defensor?"
        def_th = "?"

        war_identifier = getattr(war.opponent, 'tag', '?')
        logger.info(f"[EVENT WarAtk] Ataque detectado: {att_name}({att_tag}) vs {def_tag} | Guerra vs {war_identifier} | Estado Guerra: {war.state}")

        if not defender and def_tag != '?':
            try:
                logger.debug(f"Buscando dados defensor {def_tag}...")
                defender_player_obj = await asyncio.wait_for(coc_client.get_player(def_tag), timeout=25.0)
                def_name = getattr(defender_player_obj, 'name', f'Defensor({def_tag[-4:]})')
                def_th = getattr(defender_player_obj, 'town_hall', '?')
                logger.debug(f"Dados defensor {def_tag} obtidos: {def_name} (CV{def_th})")
            except coc_errors.NotFound: def_name = f"Defensor NF ({def_tag[-4:]})"; logger.warning(f"[EVENT WarAtk] Defensor {def_tag} NotFound.")
            except asyncio.TimeoutError: def_name = f"Defensor TO ({def_tag[-4:]})"; logger.warning(f"[EVENT WarAtk] Timeout buscar def {def_tag}.")
            except coc_errors.Maintenance: def_name = f"Defensor Maint. ({def_tag[-4:]})"; logger.warning(f"[EVENT WarAtk] API Maint. buscar def {def_tag}.")
            except Exception as e_def: def_name = f"Defensor Err ({def_tag[-4:]})"; logger.error(f"[EVENT WarAtk] Erro buscar def {def_tag}: {e_def}", exc_info=False)
        elif defender:
            def_name = getattr(defender, 'name', 'Defensor?')
            def_th = getattr(defender, 'town_hall', '?')

        stars = attack.stars
        destruction = round(attack.destruction, 1)
        stars_emo = ("⭐" * stars) + ("⚫" * (3 - stars))

        war_type = "Guerra de Liga" if war.is_cwl else "Guerra Normal"
        opponent_clan = war.opponent if war.clan.tag == clan_tag else war.clan
        opponent_name = getattr(opponent_clan, 'name', 'Oponente?')

        atk_emb = discord.Embed(
            title=f"{emojis['war_attack']} Ataque {war_type}!",
            color=discord.Color.blue(),
            timestamp=datetime.now(TIMEZONE)
        )
        atk_emb.add_field(name="Atacante", value=f"`{att_name}` (CV{att_th})", inline=True)
        atk_emb.add_field(name="Defensor", value=f"`{def_name}` (CV{def_th})", inline=True)
        atk_emb.add_field(name="Resultado", value=f"**{stars}** {stars_emo} **{destruction}%** {emojis['destruction']}", inline=False)
        atk_emb.set_footer(text=f"Guerra vs {opponent_name}")

        await send_log_embed(atk_emb)

# --- Evento Ready ---
@bot.event
async def on_ready():
    global coc_client, log_channel, MONITORED_CLAN_NAME, member_cache
    logger.info(f'Bot {bot.user.name} ({bot.user.id}) pronto.')
    logger.info(f"discord.py: {discord.__version__} | coc.py: {coc.__version__}")
    logger.info(f"Monitorando Clã(s): {CLAN_TAGS_TO_MONITOR}")
    logger.info(f"Canal ID Logs: {CHANNEL_ID}")
    start_time = datetime.now(TIMEZONE)
    try: synced = await bot.tree.sync(); logger.info(f"Sincronizados {len(synced)} comandos barra.")
    except Exception as e: logger.error(f"Falha sincronizar comandos: {e}", exc_info=True)
    try: log_channel = await bot.fetch_channel(CHANNEL_ID); logger.info(f"Canal log ({log_channel.name} - {CHANNEL_ID}) encontrado.")
    except (discord.NotFound, discord.Forbidden): logger.error(f"Canal log ID {CHANNEL_ID} inválido."); log_channel = None
    except Exception as e: logger.error(f"Erro ao buscar canal log ({CHANNEL_ID}): {e}"); log_channel = None
    logger.info("Inicializando CoC EventsClient...")
    login_ok = await initialize_coc_client()
    if not login_ok:
        logger.critical("Falha login CoC EventsClient.");
        if log_channel: await send_log_embed(discord.Embed(title=f"{emojis['error']} Erro Crítico - API CoC", description="**Falha autenticação API.**\nMonitoramento CoC offline.", color=discord.Color.red(), timestamp=start_time))
        coc_client = None
    else:
        logger.info("CoC EventsClient OK. Verificando clã principal...")
        try:
            clan = await get_clan_data(CLAN_TAGS_TO_MONITOR[0], timeout=60)
            if clan:
                MONITORED_CLAN_NAME = clan.name
                logger.info(f"Acesso clã '{clan.name}' OK.")
                logger.info("Inicializando cache membros..."); member_cache.clear()
                for member in getattr(clan, 'members', []):
                    if member.tag: member_cache[member.tag] = {'name': member.name, 'role': str(member.role), 'trophies': member.trophies, 'league': member.league.name if member.league else 'N/A'}
                logger.info(f"Cache membros inicializado com {len(member_cache)} membros.")
                online_emb = discord.Embed(title=f"{emojis['success']} Bot Online e Monitorando!", description=f"Eventos do clã **{clan.name}** (`{clan.tag}`) e Guerras monitorados.", color=discord.Color.green(), timestamp=start_time)
                online_emb.add_field(name="Monitoramento", value=f"Event-Driven Ativo {emojis['sync']}", inline=False);
                online_emb.set_footer(text=f"Bot: {bot.user.name} | v16.0.22"); # Versão atualizada
                await send_log_embed(online_emb)
            else:
                logger.critical(f"FALHA GRAVE: Clã {CLAN_TAGS_TO_MONITOR[0]} inacessível pós-login.");
                await send_log_embed(discord.Embed(title=f"{emojis['error']} Erro Crítico - Acesso Clã", description=f"**Falha obter dados clã `{CLAN_TAGS_TO_MONITOR[0]}`.**", color=discord.Color.red(), timestamp=start_time))
        except Exception as e:
             logger.critical(f"FALHA GRAVE: Erro on_ready verificar clã: {e}", exc_info=True);
             await send_log_embed(discord.Embed(title=f"{emojis['error']} Erro Crítico - Init", description=f"**Erro inesperado inicialização:**\n`{e}`", color=discord.Color.red(), timestamp=start_time))

# --- Tratador de Erros App Commands ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    error_embed = discord.Embed(color=discord.Color.red(), timestamp=datetime.now(TIMEZONE));
    cmd_name = interaction.command.name if interaction.command else 'N/A'; error_embed.set_footer(text=f"Comando: /{cmd_name}"); handled = False; original_error = error.original if isinstance(error, app_commands.CommandInvokeError) else error
    if not isinstance(original_error, (coc_errors.NotFound, coc_errors.Maintenance, asyncio.TimeoutError, coc_errors.InvalidCredentials, coc_errors.InvalidTag, coc_errors.PrivateWarLog, coc_errors.Forbidden, app_commands.CheckFailure, app_commands.CommandOnCooldown, app_commands.MissingPermissions, app_commands.BotMissingPermissions)): logger.error(f"Erro não tratado /{cmd_name}: {type(original_error).__name__} - {original_error}", exc_info=True)
    else: logger.warning(f"Erro esperado /{cmd_name}: {type(original_error).__name__} - {original_error}")
    if isinstance(original_error, app_commands.CheckFailure): handled = True; error_embed.title = f"{emojis['error']} Acesso Negado"; error_embed.description = "Você não tem permissão."
    elif isinstance(original_error, app_commands.CommandOnCooldown): handled = True; error_embed.title = f"{emojis['time']} Cooldown"; error_embed.description = f"Aguarde `{original_error.retry_after:.1f}s`."; error_embed.color = 0xFFA500
    elif isinstance(original_error, app_commands.MissingPermissions): handled = True; error_embed.title = f"{emojis['error']} Permissão Negada (Usuário)"; error_embed.description = f"Falta permissão: `{', '.join(original_error.missing_permissions)}`."
    elif isinstance(original_error, app_commands.BotMissingPermissions): handled = True; error_embed.title = f"{emojis['error']} Permissão Negada (Bot)"; error_embed.description = f"Preciso permissão: `{', '.join(original_error.missing_permissions)}`."
    elif isinstance(original_error, coc.NotFound): handled = True; error_embed.title = f"{emojis['error']} Não Encontrado"; error_embed.description = "Recurso CoC não encontrado."
    elif isinstance(original_error, coc.InvalidCredentials): handled = True; error_embed.title = f"{emojis['error']} Erro Credenciais CoC"; error_embed.description = "Credenciais (Email/Senha) inválidas."; error_embed.color=0xCC0000
    elif isinstance(original_error, coc.Forbidden): handled = True; error_embed.title = f"{emojis['error']} Erro Permissão API CoC"; error_embed.description = "Acesso negado pela API (IP/chave?)."; error_embed.color=0xCC0000
    elif isinstance(original_error, coc.Maintenance): handled = True; error_embed.title = f"{emojis['warning']} Manutenção API CoC"; error_embed.description = "API em manutenção."; error_embed.color=0xFFA500
    elif isinstance(original_error, coc.InvalidTag): handled = True; error_embed.title = f"{emojis['error']} TAG Inválida"; error_embed.description = "TAG inválida."
    elif isinstance(original_error, coc.PrivateWarLog): handled=True; error_embed.title=f"{emojis['warning']}Log Guerra Privado"; error_embed.description="Log privado."; error_embed.color=0xFFA500
    elif isinstance(original_error, coc.ClashOfClansException): handled = True; error_embed.title = f"{emojis['warning']} Erro API CoC"; error_embed.description = f"Erro API: `{type(original_error).__name__}`."; error_embed.color=0xFFA500
    elif isinstance(original_error, asyncio.TimeoutError): handled = True; error_embed.title = f"{emojis['error']} Timeout"; error_embed.description = "Operação demorou."
    elif not coc_client and not isinstance(original_error, (coc.InvalidCredentials, coc.Maintenance)): handled = True; error_embed.title = f"{emojis['error']} API CoC Offline"; error_embed.description = "API CoC inativa."; error_embed.color=0xFF8C00
    if not handled: error_embed.title = f"{emojis['error']} Erro Inesperado"; error_embed.description = f"Erro: `{type(original_error).__name__}`"
    try:
        resp_method = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
        await resp_method(embed=error_embed, ephemeral=True)
    except discord.NotFound: logger.warning(f"Interação /{cmd_name} expirou.")
    except Exception as e_send: logger.error(f"Falha enviar msg erro /{cmd_name}: {e_send}", exc_info=True)

# --- Comandos de Barra ---
admin_group = app_commands.Group(name="admin", description="Comandos administrativos.", default_permissions=discord.Permissions(administrator=True))
war_group = app_commands.Group(name="guerra", description="Comandos de Guerras e CWL.")
info_group = app_commands.Group(name="info", description="Comandos de informação.")
buscar_group = app_commands.Group(name="buscar", description="Comandos para buscar clans e jogadores.")
rank_group = app_commands.Group(name="rank", description="Comandos para exibir rankings.")

# --- Comandos (continuação) ---
@admin_group.command(name="status", description="Exibe status atual do bot e do clã monitorado.")
@app_commands.checks.has_permissions(administrator=True)
async def status_command(interaction: discord.Interaction):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    clan_tag_to_show = CLAN_TAGS_TO_MONITOR[0] if CLAN_TAGS_TO_MONITOR else None
    if not clan_tag_to_show: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Nenhum clã configurado.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        clan = await get_clan_data(clan_tag_to_show, timeout=45);
        if not clan: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Erro obter dados clã `{clan_tag_to_show}`!", color=discord.Color.red())); return
        c_n=clan.name; c_t=clan.tag; c_desc=clan.description or "S/Desc"; c_lvl=clan.level; m_cnt=clan.member_count; m_max=50; loc=getattr(clan.location,'name',"Global"); c_pts=clan.points; c_pts_vs=getattr(clan, 'clan_versus_points', 0); w_lg=getattr(clan.war_league,'name',"Nenhuma"); cap_lg=getattr(clan.capital_league,'name',"Nenhuma"); b_url=getattr(clan.badge,'url',None)
        emb=discord.Embed(title=f"{emojis['info']} Status: {c_n} ({c_t})",description=f"_{c_desc}_",color=discord.Color.blue());
        if b_url: emb.set_thumbnail(url=b_url)
        emb.add_field(name="Nível",value=str(c_lvl),inline=True); emb.add_field(name="Membros",value=f"{m_cnt}/{m_max}",inline=True); emb.add_field(name="Local",value=loc,inline=True); emb.add_field(name="Troféus Vila",value=f"{c_pts:,}{emojis['trophy']}",inline=True); emb.add_field(name="Troféus Constr.",value=f"{c_pts_vs:,}{emojis['trophy']}",inline=True); emb.add_field(name="Liga Guerra",value=w_lg,inline=True); emb.add_field(name="Liga Capital",value=cap_lg,inline=True);
        ws = f"{emojis['warning']} Verificando Guerra..."; ls = f"{emojis['warning']} Verificando CWL..."
        try:
            war = await coc_client.get_current_war(clan.tag)
            if not war or war.state=='notInWar' or war.is_cwl: ws = f"{emojis['success']} Não em Guerra Normal."
            else:
                state=war.state; opp=war.opponent; our_w=war.clan; opp_n=opp.name; our_s=our_w.stars; opp_s=opp.stars; st_obj=war.start_time; et_obj=war.end_time; st_ts=int(st_obj.time.timestamp()) if st_obj and hasattr(st_obj,'time') else None; et_ts=int(et_obj.time.timestamp()) if et_obj and hasattr(et_obj,'time') else None
                if state=='preparation' and st_ts: ws=f"{emojis['time']} **Prep.** vs `{opp_n}` (<t:{st_ts}:R>)"
                elif state=='inWar' and et_ts: ws=f"{emojis['war_attack']} **Guerra** vs `{opp_n}` ({our_s}⭐/{opp_s}⭐) Fim: <t:{et_ts}:R>"
                elif state=='warEnded': our_d=round(our_w.destruction,1); opp_d=round(opp.destruction,1); emoji_r,rt=(emojis['war_win'],"Vitória") if our_s>opp_s or (our_s==opp_s and our_d>opp_d) else (emojis['war_lose'],"Derrota") if our_s<opp_s or (our_s==opp_s and our_d<opp_d) else (emojis['war_tie'],"Empate"); ws=f"{emoji_r} **Fim** vs `{opp_n}` ({rt} {our_s}⭐/{opp_s}⭐)"
                else: ws=f"{emojis['warning']} Estado G: {state}"
        except coc.PrivateWarLog: ws = f"{emojis['warning']} Log Guerra Privado."
        except coc.NotFound: ws = f"{emojis['success']} Não em Guerra Normal (NotFound)."
        except Exception as e_war: ws = f"{emojis['error']} Erro G: {type(e_war).__name__}"; logger.error(f"Erro GW /admin status: {e_war}", exc_info=False)
        emb.add_field(name="Guerra Normal", value=ws, inline=False)
        try:
            lg = await coc_client.get_league_group(clan.tag)
            if lg and lg.state!="notInWar":
                 season=lg.season; state=lg.state.capitalize(); lg_name=lg.league.name; ls=f"{emojis['league']} **Em CWL** ({lg_name} {season}) Grupo: **{state}**"
                 active_w=None; lg_wars=[];
                 try: lg_wars = await lg.get_wars(clan.tag)
                 except Exception as e_get_wars_status: logger.warning(f"Erro buscar guerras liga /admin status: {e_get_wars_status}")
                 current_round=next((w for w in lg_wars if w and w.state in ['inWar','preparation']), None)
                 if current_round:
                    active_w=current_round; our_w_lg = active_w.clan if hasattr(active_w, 'clan') and active_w.clan.tag == clan.tag else getattr(active_w, 'opponent', None); opp_lg = active_w.opponent if hasattr(active_w, 'clan') and active_w.clan.tag == clan.tag else getattr(active_w, 'clan', None)
                    if our_w_lg and opp_lg: opp_lg_n=opp_lg.name; state_t="Guerra" if active_w.state=='inWar' else "Prep."; st_em=emojis['war_attack'] if state_t=="Guerra" else emojis['time']; time_obj=active_w.end_time if state_t=="Guerra" else active_w.start_time; t_rel=f"<t:{int(time_obj.time.timestamp())}:R>" if time_obj and hasattr(time_obj, 'time') else "?"; ls+=f"\n{st_em} Rodada: **{state_t}** vs `{opp_lg_n}` ({t_rel})";
                    if state_t=="Guerra": our_s=our_w_lg.stars; opp_s=opp_lg.stars; ls+=f" ({our_s}⭐/{opp_s}⭐)"
                 else: ls+=f"\n{emojis['info']} Nenhuma rodada CWL ativa."
            else: ls=f"{emojis['success']} Não em CWL."
        except coc.NotFound: ls=f"{emojis['success']} Não em CWL (grupo não encontrado)."
        except Exception as e_cwl: ls=f"{emojis['error']} Erro Liga: {type(e_cwl).__name__}"; logger.error(f"Erro CWL /admin status: {e_cwl}", exc_info=False)
        emb.add_field(name="Guerra de Liga (CWL)", value=ls, inline=False)
        lat=bot.latency*1000
        event_status = f"{emojis['success']} Conectado" if coc_client else f"{emojis['error']} Desconectado"
        emb.add_field(name="Status Bot", value=f"Discord: {emojis['success']}Online | Lat:{lat:.0f}ms\nCoC Events: {event_status}", inline=False);
        emb.timestamp=datetime.now(TIMEZONE)
        await interaction.followup.send(embed=emb)
    except Exception as e:
         logger.error(f"Erro GERAL cmd /admin status:{e}", exc_info=True);
         try:
             if not interaction.response.is_done():
                  await interaction.followup.send(f"{emojis['error']}Ocorreu um erro: {type(e).__name__}", ephemeral=True)
             else: logger.warning(f"Erro ocorreu após followup.send em /admin status: {e}")
         except Exception as e_send_err: logger.error(f"Erro ao tentar enviar mensagem de erro para /admin status: {e_send_err}")

@admin_group.command(name="top", description="Mostra rankings do clã (doações, troféus).")
@app_commands.describe(tipo="O tipo de ranking a ser exibido.", limite="O número de membros a serem exibidos no ranking (1-50).")
@app_commands.choices(tipo=[ app_commands.Choice(name="Doações (Temporada)", value="doacoes"), app_commands.Choice(name="Recebidos (Temporada)", value="recebidos"), app_commands.Choice(name="Troféus (Vila Principal)", value="trofeus"),])
@app_commands.checks.has_permissions(administrator=True)
async def top_command(interaction: discord.Interaction, tipo: app_commands.Choice[str], limite: app_commands.Range[int, 1, 50] = 10):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    clan_tag_to_show = CLAN_TAGS_TO_MONITOR[0] if CLAN_TAGS_TO_MONITOR else None
    if not clan_tag_to_show: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Nenhum clã configurado.", color=discord.Color.red()), ephemeral=True); return
    selected_type = tipo.value
    await interaction.response.defer(ephemeral=False)
    try:
        clan = await get_clan_data(clan_tag_to_show, timeout=45)
        if not clan or not hasattr(clan,'members'): await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Erro obter membros clã `{clan_tag_to_show}`!", color=discord.Color.red())); return
        types_map = {"doacoes": ("doações", f"{emojis['donation']} Top {limite} Doadores", discord.Color.green()), "recebidos": ("recebidos", f"{emojis['received']} Top {limite} Recebedores", discord.Color.orange()), "trofeus": ("troféus", f"{emojis['trophy']} Top {limite} Troféus", discord.Color.gold()) }
        internal_type, title, color = types_map[selected_type]; m_list = clan.members or []
        if not m_list: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Lista membros vazia.", color=discord.Color.orange())); return
        fmt_list = []
        if internal_type == "doações": s_list=sorted(m_list,key=lambda m:m.donations,reverse=True)[:limite]; fmt_list=[f"{i}. `{m.name}`(CV{m.town_hall}):**{m.donations:,}**{emojis['donation']}" for i,m in enumerate(s_list,1)]
        elif internal_type == "recebidos": s_list=sorted(m_list,key=lambda m:m.received,reverse=True)[:limite]; fmt_list=[f"{i}. `{m.name}`(CV{m.town_hall}):**{m.received:,}**{emojis['received']}" for i,m in enumerate(s_list,1)]
        elif internal_type == "troféus": s_list=sorted(m_list,key=lambda m:m.trophies,reverse=True)[:limite]; fmt_list=[f"{i}. `{m.name}`(CV{m.town_hall}):**{m.trophies:,}**{emojis['trophy']}" for i,m in enumerate(s_list,1)]
        if not fmt_list: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Nenhum dado ranking '{tipo.name}'.", color=discord.Color.orange())); return
        base_emb=discord.Embed(title=title,color=color); base_emb.set_footer(text=f"Clã: {clan.name} | Verif:{datetime.now(TIMEZONE).strftime('%d/%m %H:%M')}")
        if interaction.channel: await send_embeds_splitted(interaction.channel, base_emb, "Ranking", fmt_list, max_len=1024, max_items_per_embed=20)
        else: logger.error("Erro /admin top: Canal inválido."); await interaction.followup.send(f"{emojis['error']}Erro: Canal inválido.", ephemeral=True)
    except Exception as e: logger.error(f"Erro GERAL cmd /admin top:{e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro ranking: {e}", ephemeral=True)

@admin_group.command(name="setcanal", description="Define o canal onde o bot enviará logs e notificações.")
@app_commands.describe(canal="O canal de texto para enviar as mensagens.")
@app_commands.checks.has_permissions(administrator=True)
async def set_canal_command(interaction: discord.Interaction, canal: discord.TextChannel):
    global CHANNEL_ID, log_channel; target_channel = canal
    if not interaction.guild: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Comando servidor.", color=discord.Color.red()), ephemeral=True); return
    if not target_channel.permissions_for(interaction.guild.me).send_messages or not target_channel.permissions_for(interaction.guild.me).embed_links: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Sem permissão msgs/embeds em {target_channel.mention}.", color=discord.Color.red), ephemeral=True); return
    try:
         await interaction.response.defer(ephemeral=True)
         test_embed = discord.Embed(description=f"{emojis['info']} Testando permissões...", color=discord.Color.yellow())
         await target_channel.send(embed=test_embed, delete_after=5.0)
         CHANNEL_ID = target_channel.id; log_channel = target_channel;
         logger.info(f"Canal logs -> {target_channel.name}({CHANNEL_ID}) por {interaction.user}")
         confirm_embed = discord.Embed(title=f"{emojis['success']} Canal Logs Alterado", description=f"Logs enviados para {target_channel.mention}.", color=discord.Color.green())
         await interaction.followup.send(embed=confirm_embed, ephemeral=True)
         await send_log_embed(discord.Embed(description=f"{emojis['success']} Este canal foi definido para logs por {interaction.user.mention}."), add_timestamp=True)
    except discord.Forbidden: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Permissão Negada ao enviar msg teste em {target_channel.mention}.", color=discord.Color.red()), ephemeral=True)
    except Exception as e: logger.error(f"Erro cmd /admin setcanal: {e}",exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro definir canal: {e}", ephemeral=True)

@admin_group.command(name="setclan", description="Define qual clã o bot deve monitorar (substitui o atual).")
@app_commands.describe(tag="A tag do novo clã a ser monitorado (incluindo #).")
@app_commands.checks.has_permissions(administrator=True)
async def set_clan_command(interaction: discord.Interaction, tag: str):
    global CLAN_TAGS_TO_MONITOR, MONITORED_CLAN_NAME, coc_client, member_cache
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    clan_tag_input = coc_utils.correct_tag(tag);
    if not coc_utils.is_valid_tag(clan_tag_input): await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Tag `{tag}` inválida.", color=discord.Color.red), ephemeral=True); return
    if clan_tag_input in CLAN_TAGS_TO_MONITOR: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['info']} Já monitorando `{clan_tag_input}`.", color=discord.Color.blue), ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    try:
        logger.info(f"Tentando setclan {clan_tag_input} por {interaction.user}...");
        new_clan = await coc_client.get_clan(clan_tag_input);
        new_clan_name=new_clan.name; new_clan_tag=new_clan.tag; new_clan_badge_url=getattr(new_clan.badge,'url',None)
        old_tags = list(CLAN_TAGS_TO_MONITOR);
        if old_tags:
            logger.info(f"Removendo monitoramento clãs: {old_tags}");
            coc_client.remove_clan_updates(*old_tags)
            coc_client.remove_war_updates(*old_tags)
        member_cache.clear();
        CLAN_TAGS_TO_MONITOR.clear();
        CLAN_TAGS_TO_MONITOR.append(new_clan_tag);
        MONITORED_CLAN_NAME = new_clan_name
        logger.info(f"Adicionando monitoramento para {new_clan_tag} ({new_clan_name})");
        coc_client.add_clan_updates(new_clan_tag)
        coc_client.add_war_updates(new_clan_tag)
        logger.info("Inicializando cache membros novo clã...");
        for member in getattr(new_clan, 'members', []):
             if member.tag: member_cache[member.tag] = {'name': member.name, 'role': str(member.role), 'trophies': member.trophies, 'league': member.league.name if member.league else 'N/A'}
        logger.info(f"Cache membros inicializado com {len(member_cache)} membros para {new_clan_name}.")
        change_embed = discord.Embed(title=f"{emojis['success']} Clã Monitorado Alterado!", description=f"Monitorando **{new_clan_name}** (`{new_clan_tag}`).\nMonitoramento clãs anteriores (`{', '.join(old_tags)}`) removido.\nCache membros atualizado.", color=discord.Color.green())
        if new_clan_badge_url: change_embed.set_thumbnail(url=new_clan_badge_url)
        await interaction.followup.send(embed=change_embed, ephemeral=True)
        await send_log_embed(discord.Embed(description=f"{emojis['sync']} Monitoramento alterado para **{new_clan_name}** (`{new_clan_tag}`) por {interaction.user.mention}."), add_timestamp=True)
    except coc.NotFound: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']}Clã `{clan_tag_input}` não encontrado!", color=discord.Color.red), ephemeral=True)
    except Exception as e: logger.error(f"Erro cmd /admin setclan {clan_tag_input}: {e}",exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro definir clã: {e}", ephemeral=True)

@war_group.command(name="ataques", description="Mostra quem ainda não atacou na Guerra Normal atual.")
async def ataques_command(interaction: discord.Interaction):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    clan_tag_to_show = CLAN_TAGS_TO_MONITOR[0] if CLAN_TAGS_TO_MONITOR else None
    if not clan_tag_to_show: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Nenhum clã configurado.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        war = await coc_client.get_current_war(clan_tag_to_show)
        if war and war.is_cwl: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Clã em CWL. Use `/guerra liga_ataques`.", color=discord.Color.orange())); return
        await display_attacks_remaining_slash(interaction, war, war_type="Guerra Normal")
    except coc.NotFound: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Não em Guerra Normal.", color=discord.Color.orange))
    except coc.PrivateWarLog: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Log Guerra Privado.", color=discord.Color.orange))
    except Exception as e: logger.error(f"Erro /guerra ataques: {e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro verificar ataques: {e}", ephemeral=True)

@war_group.command(name="liga_ataques", description="Mostra quem ainda não atacou na rodada atual da CWL.")
async def liga_ataques_command(interaction: discord.Interaction):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    clan_tag_to_show = CLAN_TAGS_TO_MONITOR[0] if CLAN_TAGS_TO_MONITOR else None
    if not clan_tag_to_show: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Nenhum clã configurado.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        lg = await coc_client.get_league_group(clan_tag_to_show)
        if not lg or lg.state == "notInWar": await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Não em CWL.", color=discord.Color.orange())); return
        curr_war = None; lg_wars = [];
        try: lg_wars = await lg.get_wars(clan_tag_to_show)
        except Exception as e_wars: logger.warning(f"Erro buscar guerras liga /liga_ataques: {e_wars}")
        curr_war = next((w for w in lg_wars if w and w.state == 'inWar'), None) or next((w for w in lg_wars if w and w.state == 'preparation'), None)
        if not curr_war: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Nenhuma rodada CWL ativa/prep.", color=discord.Color.orange())); return
        await display_attacks_remaining_slash(interaction, curr_war, war_type="Guerra de Liga")
    except coc.NotFound: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Não em CWL (grupo n encontrado).", color=discord.Color.orange))
    except Exception as e: logger.error(f"Erro /guerra liga_ataques: {e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro ataques liga: {e}", ephemeral=True)

@war_group.command(name="log", description="Exibe o histórico de guerras do clã (requer log público).")
@app_commands.describe(limite="Número de guerras a exibir (máx 25).")
async def warlog_command(interaction: discord.Interaction, limite: app_commands.Range[int, 1, 25] = 10):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    clan_tag_to_show = CLAN_TAGS_TO_MONITOR[0] if CLAN_TAGS_TO_MONITOR else None
    if not clan_tag_to_show: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Nenhum clã configurado.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        log_entries = await coc_client.get_war_log(clan_tag_to_show, limit=limite); clan = await get_clan_data(clan_tag_to_show); clan_name = getattr(clan, 'name', clan_tag_to_show); clan_badge = getattr(clan.badge, 'url', None) if clan else None
        if not log_entries: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Nenhum registro guerra `{clan_name}`.", color=discord.Color.orange())); return
        base_embed = discord.Embed(title=f"{emojis['war_attack']} Histórico Guerras - {clan_name}", color=discord.Color.blue());
        if clan_badge: base_embed.set_thumbnail(url=clan_badge); base_embed.set_footer(text=f"Últimas {len(log_entries)} guerras.")
        war_list = []
        for entry in log_entries:
            our_clan_log = entry.clan; opponent_log = entry.opponent;
            if not our_clan_log or not opponent_log: continue
            result = entry.result or "Desconhecido"; end_time = entry.end_time;
            stars = f"{getattr(our_clan_log, 'stars', '?')}⭐ - {getattr(opponent_log, 'stars', '?')}⭐"
            destr = f"{getattr(our_clan_log, 'destruction', 0.0):.1f}% - {getattr(opponent_log, 'destruction', 0.0):.1f}%"
            team_size = entry.team_size; end_str = f"<t:{int(end_time.time.timestamp())}:R>" if end_time else "Data?";
            result_str = getattr(result, 'name', str(result))
            result_emo = emojis['war_win'] if result_str.lower() == 'win' else emojis['war_lose'] if result_str.lower() == 'lose' else emojis['war_tie'] if result_str.lower() == 'tie' else '❓'
            war_list.append(f"{result_emo} **{result_str.capitalize()}** vs `{opponent_log.name}` ({team_size}v{team_size})\n   Placar: {stars} ({destr}) - {end_str}")
        if interaction.channel: await send_embeds_splitted(interaction.channel, base_embed, "Guerras Recentes", war_list, max_items_per_embed=5)
        else: logger.error("Erro /guerra log: Canal inválido."); await interaction.followup.send(f"{emojis['error']}Erro: Canal inválido.", ephemeral=True)
    except coc.PrivateWarLog: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Log guerras privado `{clan_tag_to_show}`.", color=discord.Color.orange()))
    except Exception as e: logger.error(f"Erro /guerra log: {e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro log guerras: {e}", ephemeral=True)

@info_group.command(name="membro", description="Mostra detalhes e estatísticas de um jogador.")
@app_commands.describe(tag="A tag do jogador (incluindo o #).")
async def membro_command(interaction: discord.Interaction, tag: str):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    player_tag = coc_utils.correct_tag(tag)
    if not coc_utils.is_valid_tag(player_tag): await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Tag `{tag}` inválida.", color=discord.Color.red), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        player = await get_player_data(player_tag);
        if not player: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Jogador `{player_tag}` não encontrado.", color=discord.Color.red())); return
        p_n=player.name; p_t=player.tag; p_th=player.town_hall; p_th_w=player.town_hall_weapon; p_xp=player.exp_level; p_lg=player.league; p_tr=player.trophies; p_btr=player.best_trophies; p_ws=player.war_stars; p_don=player.donations; p_rec=player.received; p_cl=player.clan; p_role=str(player.role) if p_cl else 'N/A'; p_heroes = getattr(player, 'heroes', []); p_pets = getattr(player, 'pets', []); p_troops = getattr(player, 'troops', []); p_spells = getattr(player, 'spells', []); p_achievements = getattr(player, 'achievements', []); p_labels = getattr(player, 'labels', []); p_legend_stats = getattr(player, 'legend_statistics', None); p_equipment = getattr(player, 'hero_equipment', [])
        title=f"{p_lg.name if p_lg else ''} {p_n} ({p_t})"; emb=discord.Embed(title=title, color=discord.Color.orange());
        emb.description = f"[Ver perfil no Clash of Stats](https://www.clashofstats.com/players/{p_t[1:]}/summary)"
        if p_lg and p_lg.icon: emb.set_thumbnail(url=p_lg.icon.url)
        cl_info="Sem clã";
        if p_cl: cl_name = getattr(p_cl, 'name', '?'); cl_tag = getattr(p_cl, 'tag', None); cl_badge_url = getattr(p_cl.badge, 'url', None) if hasattr(p_cl, 'badge') else None;
        cl_info = f"{cl_name} (`{cl_tag}`)" if cl_tag else cl_name; cl_info += f"\nCargo: **{p_role}**";
        if p_cl and cl_badge_url: emb.set_author(name=f"Membro de {cl_name}", icon_url=cl_badge_url)
        emb.add_field(name=f"{emojis['clan_capital']} Clã",value=cl_info,inline=False)
        emb.add_field(name="CV", value=f"**{p_th}**"+(f" (Arma:{p_th_w})" if p_th_w else ""), inline=True); emb.add_field(name="XP Lvl", value=str(p_xp), inline=True); emb.add_field(name="Liga", value=f"{p_tr:,}{emojis['trophy']}"+(f" ({p_lg.name})" if p_lg else ""), inline=True); emb.add_field(name="Recorde", value=f"{p_btr:,}{emojis['trophy']}", inline=True); emb.add_field(name="Estrelas G.", value=f"{p_ws:,}⭐", inline=True); emb.add_field(name="Doa/Rec", value=f"{p_don:,}{emojis['donation']}/{p_rec:,}{emojis['received']}", inline=True);
        hv_heroes = [h for h in p_heroes if h.is_home_base];
        if hv_heroes: h_str="\n".join([f"- {h.name}: **{h.level}**/{h.max_level}" for h in hv_heroes]) or "N/A"; emb.add_field(name=f"{emojis['war_attack']} Heróis",value=h_str,inline=False)
        if p_pets: pet_str="\n".join([f"- {p.name}: **{p.level}**/{p.max_level}" for p in p_pets]) or "N/A"; emb.add_field(name="🐾 Pets",value=pet_str,inline=False)
        if p_equipment: equip_str="\n".join([f"- {e.name}: **{e.level}**/{e.max_level}" for e in p_equipment]) or "N/A"; emb.add_field(name=f"{emojis['equipment']} Equipamentos",value=equip_str,inline=False)
        if p_labels: label_str = ", ".join([f"`{lbl.name}`" for lbl in p_labels]); emb.add_field(name=f"{emojis['label']} Selos", value=label_str, inline=False)
        legend_info = []
        if p_legend_stats:
            if p_legend_stats.legend_trophies: legend_info.append(f"Troféus Lenda: **{p_legend_stats.legend_trophies}** {emojis['trophy']}")
        if legend_info: emb.add_field(name=f"{emojis['league']} Liga Lenda", value="\n".join(legend_info), inline=False)
        emb.set_footer(text=f"Verif:{datetime.now(TIMEZONE):%d/%m/%Y %H:%M}")
        achievements_list = [];
        if p_achievements: achievements_list = [f"{emojis['achievement']} {a.name}: **{a.value}**/{a.target} ({'Completa' if a.is_completed else 'Em progresso'})" for a in p_achievements]
        await interaction.followup.send(embed=emb)
        if achievements_list and interaction.channel:
             ach_embed = discord.Embed(title=f"{emojis['achievement']} Conquistas - {p_n}", color=emb.color)
             await send_embeds_splitted(interaction.channel, ach_embed, "Progresso", achievements_list, max_items_per_embed=10)
    except coc.NotFound: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Jogador `{player_tag}` não encontrado.", color=discord.Color.red()))
    except Exception as e: logger.error(f"Erro /info membro {player_tag}:{e}",exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro dados jogador: {e}", ephemeral=True)

@buscar_group.command(name="clan", description="Busca clãs por nome e outros critérios.")
@app_commands.describe(nome="Nome (ou parte do nome) do clã.", min_membros="Número mínimo de membros.", max_membros="Número máximo de membros.", min_pontos="Pontos mínimos do clã (troféus).", min_nivel="Nível mínimo do clã.", limite="Número máximo de resultados (1-25).")
async def buscar_clan_command(interaction: discord.Interaction, nome: str, min_membros: app_commands.Range[int, 1, 50] = None, max_membros: app_commands.Range[int, 1, 50] = None, min_pontos: int = None, min_nivel: app_commands.Range[int, 1, 50] = None, limite: app_commands.Range[int, 1, 25] = 10):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        if not nome: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Por favor, forneça um nome.", color=discord.Color.red())); return
        resultados = await coc_client.search_clans(name=nome, limit=limite, min_members=min_membros, max_members=max_membros, min_clan_points=min_pontos, min_clan_level=min_nivel)
        if not resultados: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Nenhum clã encontrado.", color=discord.Color.orange())); return
        base_embed = discord.Embed(title=f"{emojis['search']} Busca Clãs: '{nome}'", color=discord.Color.blue()); base_embed.set_footer(text=f"Encontrados: {len(resultados)} (Máx {limite})")
        clan_list = []
        for clan in resultados: badge_url = getattr(clan.badge, 'url', None); clan_list.append(f"{emojis['clan_capital']} **{clan.name}** (`{clan.tag}`)\n   Nvl: {clan.level} | Membros: {clan.member_count}/50 | Pontos: {clan.points:,}{emojis['trophy']}\n   Local: {getattr(clan.location, 'name', 'N/A')} | Liga Guerra: {getattr(clan.war_league, 'name', 'N/A')}")
        if interaction.channel: await send_embeds_splitted(interaction.channel, base_embed, "Clãs Encontrados", clan_list, max_items_per_embed=5)
        else: logger.error("Erro /buscar clan: Canal inválido."); await interaction.followup.send(f"{emojis['error']}Erro: Canal inválido.", ephemeral=True)
    except Exception as e: logger.error(f"Erro /buscar clan: {e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro buscar clãs: {e}", ephemeral=True)

@buscar_group.command(name="jogador", description="Busca jogadores por nome.")
@app_commands.describe(nome="Nome (ou parte do nome) do jogador.", limite="Número máximo de resultados (1-25).")
async def buscar_jogador_command(interaction: discord.Interaction, nome: str, limite: app_commands.Range[int, 1, 25] = 10):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        async with coc.Client(timeout=20) as temp_search_client:
            login_success = False
            try:
                await temp_search_client.login(EMAIL, PASSWORD)
                login_success = True
            except coc_errors.InvalidCredentials:
                logger.warning("Login com email/senha falhou no Client temporário buscar_jogador, tentando com key...")
                try:
                    key = coc_client.http.keys[0] if coc_client and coc_client.http.keys else None
                    if not key: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']}Erro de autenticação para busca (sem key).", color=discord.Color.red()), ephemeral=True); return
                    await temp_search_client.login_with_keys(key)
                    login_success = True
                except Exception as key_login_err: logger.error(f"Falha ao logar com key no client temporário buscar_jogador: {key_login_err}")
            except Exception as login_err: logger.error(f"Erro inesperado no login do client temporário buscar_jogador: {login_err}")
            if not login_success: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']}Erro de autenticação para busca.", color=discord.Color.red()), ephemeral=True); return

            logger.debug(f"Buscando jogadores com nome '{nome}' usando cliente temporário...")
            resultados = await temp_search_client.search_players(name=nome, limit=limite)
            logger.debug(f"Busca por '{nome}' retornou {len(resultados) if resultados else 0} resultados.")

        if not resultados: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Nenhum jogador encontrado '{nome}'.", color=discord.Color.orange())); return

        base_embed = discord.Embed(title=f"{emojis['search']} Busca Jogadores: '{nome}'", color=discord.Color.green()); base_embed.set_footer(text=f"Encontrados: {len(resultados)} (Máx {limite})")
        player_list = []
        for player in resultados:
            league_name = getattr(player.league, 'name', 'N/A')
            clan_name = getattr(player.clan, 'name', 'Sem clã')
            player_list.append(f"{emojis['trophy']} **{player.name}** (`{player.tag}`) - CV{player.town_hall}\n   XP: {player.exp_level} | Troféus: {player.trophies:,} ({league_name})\n   Clã: {clan_name}")

        if interaction.channel: await send_embeds_splitted(interaction.channel, base_embed, "Jogadores Encontrados", player_list, max_items_per_embed=5)
        else: logger.error("Erro /buscar jogador: Canal inválido."); await interaction.followup.send(f"{emojis['error']}Erro: Canal inválido.", ephemeral=True)

    except coc.InvalidCredentials: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']}Erro de autenticação para busca.", color=discord.Color.red()), ephemeral=True); return
    except Exception as e:
        logger.error(f"Erro GERAL /buscar jogador: {e}", exc_info=True)
        await interaction.followup.send(f"{emojis['error']}Erro buscar jogadores: {e}", ephemeral=True)

@rank_group.command(name="clans", description="Exibe o ranking de clãs local.")
@app_commands.describe(localizacao="Nome ou ID da localização (ex: Brazil, 57000011).", limite="Número de clãs a exibir (1-50).")
async def rank_clans_command(interaction: discord.Interaction, localizacao: str, limite: app_commands.Range[int, 1, 50] = 10):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False);
    location_id = await fetch_location_id(localizacao)
    if location_id is None or location_id == "global": await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Localização '{localizacao}' não encontrada ou inválida. Use um nome ou ID específico.", color=discord.Color.red())); return
    loc_name = localizacao.capitalize()
    try:
        rankings = await coc_client.get_location_clans(location_id=location_id, limit=limite)
        try:
            loc_obj = await coc_client.get_location(location_id); loc_name = loc_obj.name if loc_obj else loc_name
        except Exception: pass
        if not rankings: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Nenhum clã ranking '{loc_name}'.", color=discord.Color.orange())); return
        base_embed = discord.Embed(title=f"{emojis['ranking']} Ranking Clãs - {loc_name}", color=discord.Color.gold()); base_embed.set_footer(text=f"Top {len(rankings)}")
        rank_list = [];
        for i, clan in enumerate(rankings, 1): rank_list.append(f"**{i}.** {emojis['clan_capital']} **{clan.name}** (`{clan.tag}`)\n    Pontos: {clan.points:,}{emojis['trophy']} | Nvl: {clan.level} | Membros: {clan.member_count}")
        if interaction.channel: await send_embeds_splitted(interaction.channel, base_embed, "Ranking", rank_list, max_items_per_embed=5)
        else: logger.error("Erro /rank clans: Canal inválido."); await interaction.followup.send(f"{emojis['error']}Erro: Canal inválido.", ephemeral=True)
    except Exception as e: logger.error(f"Erro GERAL /rank clans: {e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro ranking clãs: {e}", ephemeral=True)

@rank_group.command(name="jogadores", description="Exibe o ranking de jogadores (global ou local).")
@app_commands.describe(localizacao="Nome ou ID da localização (ex: Brazil, 57000011) ou 'global'.", limite="Número de jogadores a exibir (1-50).")
async def rank_jogadores_command(interaction: discord.Interaction, localizacao: str = "global", limite: app_commands.Range[int, 1, 50] = 10):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False); location_id = await fetch_location_id(localizacao)
    if location_id is None and localizacao.lower() != "global": await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Localização '{localizacao}' não encontrada.", color=discord.Color.red())); return
    loc_name = localizacao.capitalize()
    try:
        loc_id_param = location_id if localizacao.lower() != "global" else "global"
        rankings = await coc_client.get_location_players(location_id=loc_id_param, limit=limite)
        if localizacao.lower() != "global" and isinstance(loc_id_param, int):
            try:
                loc_obj = await coc_client.get_location(loc_id_param); loc_name = loc_obj.name if loc_obj else loc_name
            except Exception: pass
        elif loc_id_param == "global": loc_name = "Global"
        if not rankings: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Nenhum jogador ranking '{loc_name}'.", color=discord.Color.orange())); return
        base_embed = discord.Embed(title=f"{emojis['ranking']} Ranking Jogadores - {loc_name}", color=discord.Color.purple()); base_embed.set_footer(text=f"Top {len(rankings)}")
        rank_list = [];
        for i, player in enumerate(rankings, 1): clan_name = getattr(player.clan, 'name', 'Sem clã'); rank_list.append(f"**{i}.** {emojis['trophy']} **{player.name}** (`{player.tag}`)\n    Troféus: {player.trophies:,} | Nvl: {player.exp_level} | Clã: {clan_name}")
        if interaction.channel: await send_embeds_splitted(interaction.channel, base_embed, "Ranking", rank_list, max_items_per_embed=5)
        else: logger.error("Erro /rank jogadores: Canal inválido."); await interaction.followup.send(f"{emojis['error']}Erro: Canal inválido.", ephemeral=True)
    except Exception as e: logger.error(f"Erro GERAL /rank jogadores: {e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro ranking jogadores: {e}", ephemeral=True)

@bot.tree.command(name="ligas", description="Mostra informações sobre as ligas do Clash of Clans.")
async def ligas_command(interaction: discord.Interaction):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        async with coc.Client(timeout=30) as temp_league_client:
            login_success = False
            try:
                await temp_league_client.login(EMAIL, PASSWORD)
                login_success = True
            except coc_errors.InvalidCredentials:
                logger.warning("Login falhou no client /ligas, tentando key...")
                login_success = False
                try:
                    key = coc_client.http.keys[0] if coc_client and coc_client.http.keys else None
                    if key: await temp_league_client.login_with_keys(key); login_success = True
                    else: logger.error("Nenhuma key CoC disponível para client /ligas.")
                except Exception as e_key: logger.error(f"Erro login com key /ligas: {e_key}")
            except Exception as e_login: logger.error(f"Erro login client /ligas: {e_login}")
            if not login_success: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']}Erro autenticação para buscar ligas.", color=discord.Color.red()), ephemeral=True); return

            logger.debug("Buscando ligas usando cliente temporário...")
            leagues = await temp_league_client.search_leagues(limit=30);
            capital_leagues = await temp_league_client.get_capital_leagues();
            builder_leagues = await temp_league_client.get_builder_base_leagues()
            logger.debug("Busca de ligas concluída.")

        emb_main = discord.Embed(title=f"{emojis['trophy']} Ligas - Vila Principal", color=discord.Color.gold());
        main_list = [f"- {lg.name}" for lg in leagues if hasattr(lg, 'id') and lg.id < 30000000] if isinstance(leagues, list) else []
        if main_list:
             if len("\n".join(main_list)) > 1024 and interaction.channel: await send_embeds_splitted(interaction.channel, emb_main, "Ligas", main_list, max_items_per_embed=15)
             else: emb_main.description = "\n".join(main_list); await interaction.followup.send(embed=emb_main)
        else: await interaction.followup.send(embed=discord.Embed(description="Nenhuma liga da vila principal encontrada.", color=discord.Color.orange()))
        if interaction.channel:
             await asyncio.sleep(0.5)
             emb_builder = discord.Embed(title=f"{emojis['trophy']} Ligas - Base Construtor", color=discord.Color.blue());
             builder_list = [f"- {lg.name}" for lg in builder_leagues] if isinstance(builder_leagues, list) else []
             if builder_list: emb_builder.description = "\n".join(builder_list); await interaction.channel.send(embed=emb_builder)
             else: await interaction.channel.send(embed=discord.Embed(description="Nenhuma liga construtor.", color=discord.Color.orange()))
             await asyncio.sleep(0.5)
             emb_capital = discord.Embed(title=f"{emojis['clan_capital']} Ligas - Capital", color=discord.Color.purple());
             capital_list = [f"- {lg.name}" for lg in capital_leagues] if isinstance(capital_leagues, list) else []
             if capital_list: emb_capital.description = "\n".join(capital_list); await interaction.channel.send(embed=emb_capital)
             else: await interaction.channel.send(embed=discord.Embed(description="Nenhuma liga capital.", color=discord.Color.orange()))
        else:
             logger.warning("/ligas: Canal inválido para enviar embeds adicionais.")
    except coc.InvalidCredentials: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']}Erro autenticação para buscar ligas.", color=discord.Color.red()), ephemeral=True); return
    except Exception as e: logger.error(f"Erro GERAL /ligas: {e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro buscar ligas: {e}", ephemeral=True)

@bot.tree.command(name="ajuda", description="Mostra informações sobre os comandos do bot.")
async def ajuda_command(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{emojis['info']} Ajuda - {bot.user.name}", description=f"Monitora eventos CoC (**v16.0.22 - Event Driven**) e fornece infos via comandos de barra (`/`).", color=discord.Color.green()) # Versão atualizada
    if bot.user.avatar: embed.set_thumbnail(url=bot.user.avatar.url)
    embed.add_field(name=f"{emojis['admin']} Admin (`/admin ...`) [ADM]", value=f"`status`: Status geral.\n`top [tipo] [limite]`: Rankings clã (doacoes, recebidos, trofeus).\n`setcanal <#canal>`: Define canal logs.\n`setclan <#TAG>`: Define clã.", inline=False)
    embed.add_field(name=f"{emojis['war_attack']} Guerra (`/guerra ...`)", value=f"`ataques`: Ataques restantes Guerra Normal.\n`liga_ataques`: Ataques restantes CWL.\n`log [limite]`: Histórico guerras.", inline=False)
    embed.add_field(name=f"{emojis['info']} Info (`/info ...`)", value=f"`membro <#TAG>`: Detalhes jogador.", inline=False)
    embed.add_field(name=f"{emojis['search']} Busca (`/buscar ...`)", value=f"`clan [nome]`: Busca clãs.\n`jogador [nome]`: Busca jogadores.", inline=False)
    embed.add_field(name=f"{emojis['ranking']} Ranking (`/rank ...`)", value=f"`clans <local>`: Ranking clãs local.\n`jogadores [local]`: Ranking jogadores.", inline=False)
    embed.add_field(name=f"{emojis['league']} Ligas (`/ligas`)", value="Mostra ligas do jogo.", inline=False)
    embed.add_field(name="👀 Eventos Monitorados (Tempo Real)", value=f"Entrada/Saída, Doações/Recebidos, Mudança Cargo/Liga/Troféus, **Ataques de Guerra**.", inline=False)
    embed.set_footer(text=f"Versão: 16.0.22"); await interaction.response.send_message(embed=embed, ephemeral=True) # Versão atualizada

# --- SUBSTITUÍDO PELA VERSÃO v15 ---
async def display_attacks_remaining_slash(interaction: discord.Interaction, war, war_type="Guerra"):
    """Função copiada da v15 para exibir ataques restantes, priorizando um único embed."""
    if not interaction.channel:
         logger.error(f"Erro display_attacks_remaining_slash: Canal da interação inválido.")
         try: await interaction.followup.send(f"{emojis['error']}Erro: Não foi possível encontrar o canal para enviar a resposta.", ephemeral=True)
         except Exception as e_followup: logger.error(f"Erro ao enviar msg de erro (canal inválido) em display_attacks_remaining_slash: {e_followup}")
         return

    if not war or war.state not in ['inWar', 'preparation']: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Não em {war_type} ativa ou em preparação.", color=discord.Color.orange())); return

    # Determina nosso clã e oponente (lógica adaptada da v15/v16)
    our_c = None
    en_c = None
    # Prioriza identificar baseado na lista de monitoramento (se houver mais de um clã um dia)
    our_clan_tag = CLAN_TAGS_TO_MONITOR[0] if CLAN_TAGS_TO_MONITOR else None
    if our_clan_tag:
        if hasattr(war, 'clan') and war.clan and war.clan.tag == our_clan_tag:
            our_c = war.clan
            en_c = war.opponent
        elif hasattr(war, 'opponent') and war.opponent and war.opponent.tag == our_clan_tag:
            # Isso pode acontecer em CWL onde nosso clã é o 'opponent' no objeto war
            our_c = war.opponent
            en_c = war.clan
    # Fallback se a tag não bateu ou não há tag monitorada definida
    if not our_c:
        our_c = war.clan if hasattr(war, 'clan') else None
        en_c = war.opponent if hasattr(war, 'opponent') else None

    if not our_c or not en_c: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Erro identificar clãs na {war_type}.", color=discord.Color.red())); return

    our_c_name = getattr(our_c, 'name', '?')
    en_c_name = getattr(en_c, 'name', '?')

    state_info = ""; time_ref = None; color = discord.Color.blue(); timestamp = datetime.now(TIMEZONE)
    if war.state == 'preparation' and war.start_time and hasattr(war.start_time, 'time'):
        time_ref = war.start_time.time.astimezone(TIMEZONE); state_info = f"**Estado:** Prep.\n**Início:** <t:{int(time_ref.timestamp())}:R>"; timestamp = time_ref
    elif war.state == 'inWar' and war.end_time and hasattr(war.end_time, 'time'):
        time_ref = war.end_time.time.astimezone(TIMEZONE); state_info = f"**Estado:** Guerra\n**Término:** <t:{int(time_ref.timestamp())}:R>"; color = discord.Color.orange(); timestamp = time_ref
    else:
         state_info = f"**Estado:** {war.state.capitalize()}"

    attacks_per = war.attacks_per_member; remaining = []; total_possible = 0; total_done = 0; members = our_c.members or []
    if not members: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Lista membros da {war_type} indisponível.", color=discord.Color.orange())); return
    for m in members:
        total_possible += attacks_per; attacks_d = len(m.attacks); total_done += attacks_d; attacks_l = attacks_per - attacks_d
        if attacks_l > 0: name=m.name; th=m.town_hall; map_pos=m.map_position; remaining.append(f"{map_pos}. `{name}` (CV{th}): **{attacks_l}** atk(s)")

    title = f"{emojis['war_attack']} Ataques Restantes - {war_type} vs {en_c_name}"; base_embed = discord.Embed(title=title, description=state_info, color=color, timestamp=timestamp); base_embed.set_footer(text=f"Clã: {our_c_name}")
    summary = f"**{total_done} / {total_possible}** ataques realizados."; base_embed.add_field(name="Resumo", value=summary, inline=False)

    if not remaining:
        base_embed.add_field(name="Situação", value=f"{emojis['success']} Todos atacaram!", inline=False); base_embed.color = discord.Color.green();
        await interaction.followup.send(embed=base_embed)
    else:
        temp_embed = base_embed.copy(); # Copia embed base para potencialmente adicionar a lista
        field_title = "Membros Pendentes";
        full_list_str = "\n".join(remaining)

        # Tenta adicionar a lista toda em um campo se couber (1024 chars)
        # O limite de 20 itens era da v15, removido aqui para focar no limite de caracteres
        if len(full_list_str) <= 1024:
            logger.info(f"display_attacks_remaining_slash (v15 logic): Lista cabe em 1 campo ({len(full_list_str)} chars).")
            temp_embed.add_field(name=field_title, value=full_list_str, inline=False);
            await interaction.followup.send(embed=temp_embed) # Envia embed único
        else: # Se não couber, envia base e chama split
            logger.info(f"display_attacks_remaining_slash (v15 logic): Lista excede 1024 chars ({len(full_list_str)}). Usando send_embeds_splitted.")
            await interaction.followup.send(embed=base_embed) # Envia embed base sem a lista
            if interaction.channel:
                # Cria um embed novo e limpo para a função de split
                split_list_embed = discord.Embed(color=color)
                await send_embeds_splitted(interaction.channel, split_list_embed, field_title, remaining, max_items_per_embed=25) # Usa 25 como limite por embed
            else:
                 logger.error(f"Erro display_attacks_remaining_slash (v15 logic): Canal split inválido.")
# --- FIM DA SUBSTITUIÇÃO ---

# Adiciona os grupos à árvore
bot.tree.add_command(admin_group)
bot.tree.add_command(war_group)
bot.tree.add_command(info_group)
bot.tree.add_command(buscar_group)
bot.tree.add_command(rank_group)

# --- Função Principal ---
async def main():
    global coc_client
    if not TOKEN: logger.critical("Token Discord não encontrado."); return
    logger.info("Iniciando bot Discord (main)...")
    try: await bot.start(TOKEN)
    except discord.LoginFailure: logger.critical("Login Discord falhou: Token inválido.")
    except discord.PrivilegedIntentsRequired: logger.critical("Login Discord falhou: Intenções Privilegiadas não habilitadas.")
    except KeyboardInterrupt: logger.info("Desligamento manual solicitado.")
    except Exception as e: logger.critical(f"Erro fatal no loop principal do bot: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        if os.name == 'nt': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except Exception as e_run:
        try: logger.critical(f"Erro crítico irrecuperável ao executar asyncio.run(main): {e_run}", exc_info=True)
        except: print(f"ERRO CRÍTICO IRRECUPERÁVEL (logger falhou): {e_run}")
