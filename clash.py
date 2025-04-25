# -*- coding: utf-8 -*-
# Versão 16.0.34 - Corrigido CommandSignatureMismatch forçando sync para Guilda de Teste

import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
from coc import utils as coc_utils
# Exceções são importadas diretamente de 'coc' agora
import asyncio
import os
import logging
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from aiohttp import web
from typing import Optional, List, Set

# Carrega variáveis de ambiente
load_dotenv()

# --- Constantes ---
BOT_VERSION = "16.0.34" # Define a versão atual aqui

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
logger.info(f"Logging configurado em nível INFO. Versão: {BOT_VERSION}")

# --- Configurações e Validação ---
TOKEN = os.getenv('DISCORD_TOKEN')
EMAIL = os.getenv('COC_EMAIL')
PASSWORD = os.getenv('COC_PASSWORD')
CLAN_TAG_ENV = os.getenv('CLAN_TAG')
CHANNEL_ID_STR = os.getenv('CHANNEL_ID')
PORT = int(os.environ.get("PORT", 10000))
ROLE_ID_1STAR_ALERT_STR = os.getenv('ROLE_ID_1STAR_ALERT')
ROLE_ID_MISSED_ATTACK_STR = os.getenv('ROLE_ID_MISSED_ATTACK')
# --- NOVA VARIÁVEL PARA GUILD DE TESTE ---
TEST_GUILD_ID_STR = os.getenv('TEST_GUILD_ID')
# --- FIM NOVA VARIÁVEL ---

if not all([TOKEN, CLAN_TAG_ENV, CHANNEL_ID_STR]): logger.critical("FATAL: TOKEN, CLAN_TAG ou CHANNEL_ID faltando no .env"); exit("Erro Conf.")
if not EMAIL or not PASSWORD: logger.critical("FATAL: Email/Senha CoC não configurados."); exit("Erro Conf: Credenciais CoC faltando.")
try: CHANNEL_ID = int(CHANNEL_ID_STR)
except ValueError: logger.critical(f"FATAL: CHANNEL_ID inválido ('{CHANNEL_ID_STR}')."); exit("Erro Conf.")

TEST_GUILD_ID = None
if TEST_GUILD_ID_STR:
    try: TEST_GUILD_ID = int(TEST_GUILD_ID_STR)
    except ValueError: logger.warning(f"TEST_GUILD_ID ('{TEST_GUILD_ID_STR}') inválido no .env. Sincronização global será tentada.")
else: logger.warning("TEST_GUILD_ID não definido no .env. Sincronização global será tentada (pode demorar ou falhar).")


ROLE_ID_1STAR_ALERT = None
if ROLE_ID_1STAR_ALERT_STR:
    try: ROLE_ID_1STAR_ALERT = int(ROLE_ID_1STAR_ALERT_STR)
    except ValueError: logger.warning(f"ROLE_ID_1STAR_ALERT ('{ROLE_ID_1STAR_ALERT_STR}') inválido no .env. Alerta de 1 estrela não mencionará cargo.")
else: logger.info("ROLE_ID_1STAR_ALERT não definido no .env. Alerta de 1 estrela não mencionará cargo.")

ROLE_ID_MISSED_ATTACK = None
if ROLE_ID_MISSED_ATTACK_STR:
    try: ROLE_ID_MISSED_ATTACK = int(ROLE_ID_MISSED_ATTACK_STR)
    except ValueError: logger.warning(f"ROLE_ID_MISSED_ATTACK ('{ROLE_ID_MISSED_ATTACK_STR}') inválido no .env. Relatório de ataques perdidos não mencionará cargo.")
else: logger.info("ROLE_ID_MISSED_ATTACK não definido no .env. Relatório de ataques perdidos não mencionará cargo.")

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
clan_data_cache = {}
reported_war_ends: Set[str] = set()

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
    if check_war_end_report_task.is_running():
        logger.info("Parando task check_war_end_report_task...")
        check_war_end_report_task.cancel()
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
            logger.info("Eventos Clã e Guerra registrados no EventsClient.")
            return True
        except coc.InvalidCredentials as e: logger.error(f"[Tentativa {attempt}/3] Falha autenticação (InvalidCredentials): {e}"); last_error = e; return False
        except coc.Maintenance as e: logger.warning(f"[Tentativa {attempt}/3] API CoC em manutenção (EventsClient): {e}"); last_error = e
        except asyncio.TimeoutError: logger.error(f"[Tentativa {attempt}/3] Timeout login EventsClient."); last_error = asyncio.TimeoutError("Timeout login API CoC.")
        except coc.ClashOfClansException as e:
             logger.error(f"[Tentativa {attempt}/3] Erro API CoC ({type(e).__name__}): {e}", exc_info=True); last_error = e
             if isinstance(e, coc.Forbidden): return False
        except Exception as e: logger.error(f"[Tentativa {attempt}/3] Erro login/registro eventos: {e}", exc_info=True); last_error = e
        if attempt < 3: wait_time = 30 * attempt; logger.info(f"Aguardando {wait_time}s..."); await asyncio.sleep(wait_time)
    logger.critical(f"--- Falha login CoC EventsClient após {attempt} tentativas. Último erro: {last_error} ---"); coc_client = None; return False

# --- Funções Auxiliares ---
# ... (get_clan_data_with_cache, get_clan_data, get_player_data, send_log_embed, send_embeds_splitted, fetch_location_id) ...
# (Sem alterações nestas funções)
async def get_clan_data_with_cache(tag=None, timeout=30.0, force_refresh=False):
    """Busca dados do clã, usando cache para nome e badge."""
    global coc_client, clan_data_cache
    target_tag = tag or (CLAN_TAGS_TO_MONITOR[0] if CLAN_TAGS_TO_MONITOR else None)
    if not target_tag: return None

    if not force_refresh and target_tag in clan_data_cache and 'name' in clan_data_cache[target_tag] and 'badge_url' in clan_data_cache[target_tag]:
        return clan_data_cache[target_tag]

    try:
        clan = await get_clan_data(target_tag, timeout)
        if clan:
            clan_data_cache[target_tag] = {
                'name': getattr(clan, 'name', '?'),
                'tag': getattr(clan, 'tag', '?'),
                'badge_url': getattr(clan.badge, 'url', None) if hasattr(clan, 'badge') else None
            }
            logger.debug(f"Cache clã {target_tag} atualizado.")
            return clan
        else:
            return None
    except Exception as e:
        logger.error(f"Erro ao buscar dados do clã {target_tag} em get_clan_data_with_cache: {e}")
        return clan_data_cache.get(target_tag)

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
        return clan
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
        return player
    except coc.NotFound: logger.error(f"Jogador '{player_tag}' não encontrado."); raise
    except coc.Maintenance as e: logger.warning(f"API CoC em manutenção (jogador '{player_tag}'): {e}"); raise
    except coc.ClashOfClansException as e: logger.warning(f"Erro API CoC ({type(e).__name__}) jogador '{player_tag}': {e}"); raise
    except asyncio.TimeoutError: logger.error(f"Timeout ({timeout}s) jogador '{player_tag}'."); raise
    except Exception as e: logger.error(f"Erro Inesperado ({type(e).__name__}) jogador '{player_tag}': {e}", exc_info=True); raise

async def send_log_embed(embed: discord.Embed, add_timestamp=True, add_bot_footer=True, content=None):
    """Envia um embed para o canal de log, com opção de adicionar texto e rodapé padrão."""
    global log_channel, bot, BOT_VERSION
    if not log_channel and CHANNEL_ID:
        try: log_channel = await bot.fetch_channel(CHANNEL_ID); logger.info(f"Canal log ({CHANNEL_ID}) cacheado.")
        except (discord.NotFound, discord.Forbidden): logger.error(f"Canal log ID {CHANNEL_ID} inválido."); log_channel = None
        except Exception as e: logger.error(f"Erro buscar canal log ({CHANNEL_ID}): {e}"); return
    if log_channel:
        try:
            if add_timestamp and not embed.timestamp:
                embed.timestamp = datetime.now(TIMEZONE)

            if add_bot_footer:
                footer_text = f"Bot: {bot.user.name} | v{BOT_VERSION}"
                if embed.timestamp is None:
                     footer_text += f" • {discord.utils.format_dt(datetime.now(TIMEZONE), style='R')}"
                embed.set_footer(text=footer_text)

            if content:
                await log_channel.send(content=content, embed=embed)
            else:
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
            # Adiciona rodapé padrão ao último embed do split, se não tiver o rodapé do embed base
            if not current_embed.footer and base_embed.footer:
                 current_embed.set_footer(text=base_embed.footer.text, icon_url=base_embed.footer.icon_url)
            elif not current_embed.footer: # Adiciona rodapé genérico se base não tinha
                 footer_text = f"Bot: {bot.user.name} | v{BOT_VERSION}"
                 if current_embed.timestamp is None:
                      footer_text += f" • {discord.utils.format_dt(datetime.now(TIMEZONE), style='R')}"
                 current_embed.set_footer(text=footer_text)

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
            except coc.InvalidCredentials:
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
# ... (Handlers de Clã: member_join, member_leave, member_donations, member_received, member_role_change, member_league_change, member_trophies_change) ...
# ... (Handler de Guerra: war_attack) ...
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
        badge_url = clan_data_cache.get(clan_tag, {}).get('badge_url', getattr(clan.badge, 'url', None))
        embed.set_author(name=f"{clan_name} ({clan_tag})", icon_url=badge_url if badge_url else discord.Embed.Empty)
        await send_log_embed(embed)

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
        badge_url = clan_data_cache.get(clan_tag, {}).get('badge_url', getattr(clan.badge, 'url', None))
        embed.set_author(name=f"{clan_name} ({clan_tag})", icon_url=badge_url if badge_url else discord.Embed.Empty)
        await send_log_embed(embed)

    @client.event
    @coc.ClanEvents.member_donations()
    async def member_donations(old_member: coc.ClanMember, member: coc.ClanMember):
        clan = member.clan
        tag = getattr(member, 'tag', '?')
        name = getattr(member, 'name', '?')
        clan_tag = getattr(clan, 'tag', '?')
        clan_name = getattr(clan, 'name', '?')
        donated = member.donations - old_member.donations
        total_donations = member.donations

        if donated <= 0: return
        logger.info(f"[EVENT] {name} ({tag}) doou {donated} tropas em {clan_name}")

        badge_url = clan_data_cache.get(clan_tag, {}).get('badge_url')
        if not badge_url:
            try:
                clan_full_data = await get_clan_data_with_cache(clan_tag, force_refresh=False)
                badge_url = clan_data_cache.get(clan_tag, {}).get('badge_url')
            except Exception: pass

        embed = discord.Embed(color=discord.Color.blue())
        embed.set_author(name=f"{clan_name} ({clan_tag})", icon_url=badge_url if badge_url else discord.Embed.Empty)
        if badge_url:
             embed.set_thumbnail(url=badge_url)

        field_title = f"{emojis['donation']} Doado"
        field_value = f"**{donated}** tropas por `{name}` (Total: {total_donations:,})"
        embed.add_field(name=field_title, value=field_value, inline=False)

        await send_log_embed(embed, add_timestamp=True, add_bot_footer=True)

    @client.event
    @coc.ClanEvents.member_received()
    async def member_received(old_member: coc.ClanMember, member: coc.ClanMember):
        clan = member.clan
        tag = getattr(member, 'tag', '?')
        name = getattr(member, 'name', '?')
        clan_tag = getattr(clan, 'tag', '?')
        clan_name = getattr(clan, 'name', '?')
        received = member.received - old_member.received
        total_received = member.received

        if received <= 0: return
        logger.info(f"[EVENT] {name} ({tag}) recebeu {received} tropas em {clan_name}")

        badge_url = clan_data_cache.get(clan_tag, {}).get('badge_url')
        if not badge_url:
            try:
                clan_full_data = await get_clan_data_with_cache(clan_tag, force_refresh=False)
                badge_url = clan_data_cache.get(clan_tag, {}).get('badge_url')
            except Exception: pass

        embed = discord.Embed(color=discord.Color.orange())
        embed.set_author(name=f"{clan_name} ({clan_tag})", icon_url=badge_url if badge_url else discord.Embed.Empty)
        if badge_url:
            embed.set_thumbnail(url=badge_url)

        field_title = f"{emojis['received']} Recebido"
        field_value = f"**{received}** tropas por `{name}` (Total: {total_received:,})"
        embed.add_field(name=field_title, value=field_value, inline=False)

        await send_log_embed(embed, add_timestamp=True, add_bot_footer=True)

    @client.event
    @coc.ClanEvents.member_role_change()
    async def member_role_change(old_member: coc.ClanMember, member: coc.ClanMember):
        global member_cache; clan = member.clan; tag = getattr(member, 'tag', '?'); name = getattr(member, 'name', '?'); clan_tag = getattr(clan, 'tag', '?'); clan_name = getattr(clan, 'name', '?'); old_role = str(old_member.role) if hasattr(old_member, 'role') else '?'; new_role = str(member.role) if hasattr(member, 'role') else '?'
        if old_role == new_role: return
        logger.info(f"[EVENT] Cargo de {name} ({tag}) mudou de {old_role} para {new_role} em {clan_name}")
        if tag and tag in member_cache: member_cache[tag]['role'] = new_role
        embed = discord.Embed(title=f"{emojis['role']} Mudança de Cargo", description=f"O cargo de **{name}** (`{tag}`) foi alterado.", color=discord.Color.light_grey())
        embed.add_field(name="Cargo Anterior", value=old_role, inline=True); embed.add_field(name="Novo Cargo", value=new_role, inline=True)
        badge_url = clan_data_cache.get(clan_tag, {}).get('badge_url', getattr(clan.badge, 'url', None))
        embed.set_author(name=f"{clan_name} ({clan_tag})", icon_url=badge_url if badge_url else discord.Embed.Empty)
        await send_log_embed(embed)

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
        badge_url = clan_data_cache.get(clan_tag, {}).get('badge_url', getattr(clan.badge, 'url', None))
        embed.set_author(name=f"{clan_name} ({clan_tag})", icon_url=badge_url if badge_url else discord.Embed.Empty)
        await send_log_embed(embed)

    @client.event
    @coc.ClanEvents.member_trophies_change()
    async def member_trophies_change(old_member: coc.ClanMember, member: coc.ClanMember):
        global member_cache; clan = member.clan; tag = getattr(member, 'tag', '?'); name = getattr(member, 'name', '?'); clan_tag = getattr(clan, 'tag', '?'); clan_name = getattr(clan, 'name', '?'); old_trophies = old_member.trophies; new_trophies = member.trophies; diff = new_trophies - old_trophies; sign = "+" if diff > 0 else ""
        if diff == 0: return
        logger.info(f"[EVENT] Troféus de {name} ({tag}): {old_trophies} -> {new_trophies} ({sign}{diff}) em {clan_name}")
        if tag and tag in member_cache: member_cache[tag]['trophies'] = new_trophies
        embed = discord.Embed(description=f"{emojis['trophy']} `{name}`: {old_trophies:,} → **{new_trophies:,}** ({sign}{diff})", color=discord.Color.gold() if diff > 0 else discord.Color.dark_grey())
        embed.set_footer(text=f"Clã: {clan_name}")
        await send_log_embed(embed, add_timestamp=False, add_bot_footer=False)

    # --- Handlers Guerra ---
    @client.event
    @coc.WarEvents.war_attack()
    async def war_attack(attack: coc.WarAttack, war: coc.ClanWar):
        global ROLE_ID_1STAR_ALERT, log_channel, clan_data_cache
        is_relevant_clan = (
            attack.attacker is not None and attack.attacker.clan is not None and attack.attacker.clan.tag in CLAN_TAGS_TO_MONITOR
        ) or (
            attack.defender is not None and attack.defender.clan is not None and attack.defender.clan.tag in CLAN_TAGS_TO_MONITOR
        )
        if not is_relevant_clan: return
        if not attack.attacker or not attack.attacker.clan or attack.attacker.clan.tag not in CLAN_TAGS_TO_MONITOR: return

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
            except Exception as e_def: logger.warning(f"Erro ao buscar defensor {def_tag}: {e_def}")
        elif defender:
            def_name = getattr(defender, 'name', 'Defensor?')
            def_th = getattr(defender, 'town_hall', '?')

        stars = attack.stars
        destruction = round(attack.destruction, 1)
        stars_emo = ("⭐" * stars) + ("⚫" * (3 - stars))
        war_type = "Guerra de Liga" if war.is_cwl else "Guerra Normal"
        opponent_clan = war.opponent if war.clan.tag == clan_tag else war.clan
        opponent_name = getattr(opponent_clan, 'name', 'Oponente?')

        mention_content = None
        if stars == 1 and ROLE_ID_1STAR_ALERT and log_channel:
            try:
                guild = log_channel.guild
                role_to_mention = guild.get_role(ROLE_ID_1STAR_ALERT)
                if role_to_mention:
                    alert_message = "⚠️ Atenção: ataque fora do padrão detectado! Analise para ver o que aconteceu."
                    mention_content = f"{role_to_mention.mention} {alert_message}"
                    logger.info(f"Ataque 1 estrela detectado. Preparando menção para role ID {ROLE_ID_1STAR_ALERT}.")
                else: logger.warning(f"Cargo para alerta 1 estrela (ID: {ROLE_ID_1STAR_ALERT}) não encontrado no servidor.")
            except Exception as e: logger.error(f"Erro ao tentar obter/mencionar cargo para alerta 1 estrela: {e}")

        atk_emb = discord.Embed(title=f"{emojis['war_attack']} Ataque {war_type}!", color=discord.Color.blue())
        atk_emb.add_field(name="Atacante", value=f"`{att_name}` (CV{att_th})", inline=True)
        atk_emb.add_field(name="Defensor", value=f"`{def_name}` (CV{def_th})", inline=True)
        atk_emb.add_field(name="Resultado", value=f"**{stars}** {stars_emo} **{destruction}%** {emojis['destruction']}", inline=False)
        clan_full_data = clan_data_cache.get(clan_tag, {})
        clan_name = clan_full_data.get('name', war.clan.name)
        badge_url = clan_full_data.get('badge_url', getattr(war.clan.badge, 'url', None))
        atk_emb.set_author(name=f"{clan_name} ({clan_tag})", icon_url=badge_url if badge_url else discord.Embed.Empty)

        await send_log_embed(atk_emb, add_timestamp=True, add_bot_footer=True, content=mention_content)

    # Handler on_war_state_change removido na v16.0.32

# --- Evento Ready ---
# ... (igual v16.0.32, inicia a task) ...
@bot.event
async def on_ready():
    global coc_client, log_channel, MONITORED_CLAN_NAME, member_cache, clan_data_cache
    logger.info(f'Bot {bot.user.name} ({bot.user.id}) pronto.')
    logger.info(f"discord.py: {discord.__version__} | coc.py: {coc.__version__}")
    logger.info(f"Monitorando Clã(s): {CLAN_TAGS_TO_MONITOR}")
    logger.info(f"Canal ID Logs: {CHANNEL_ID}")
    start_time = datetime.now(TIMEZONE)
    # --- CORREÇÃO: Sincronizar para Guilda de Teste ---
    try:
        if TEST_GUILD_ID:
             logger.info(f"Sincronizando comandos para a Guilda ID: {TEST_GUILD_ID}...")
             guild_obj = discord.Object(id=TEST_GUILD_ID)
             # Limpa comandos da guilda primeiro (opcional, mas ajuda a evitar conflitos)
             # bot.tree.clear_commands(guild=guild_obj)
             # await bot.tree.sync(guild=guild_obj)
             synced = await bot.tree.sync(guild=guild_obj)
             logger.info(f"Sincronizados {len(synced)} comandos para a Guilda {TEST_GUILD_ID}.")
        else:
             logger.warning("TEST_GUILD_ID não definido. Tentando sincronização global...")
             synced = await bot.tree.sync()
             logger.info(f"Sincronizados {len(synced)} comandos globalmente.")
    except Exception as e:
        logger.error(f"Falha sincronizar comandos: {e}", exc_info=True)
    # --- FIM CORREÇÃO ---
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
            clan_initial_data = await get_clan_data_with_cache(CLAN_TAGS_TO_MONITOR[0], force_refresh=True)
            if clan_initial_data:
                if isinstance(clan_initial_data, dict):
                    MONITORED_CLAN_NAME = clan_initial_data.get('name', '?')
                    clan_tag = clan_initial_data.get('tag', '?')
                    clan_obj_for_members = await get_clan_data(clan_tag) if clan_tag != '?' else None
                else:
                    MONITORED_CLAN_NAME = clan_initial_data.name
                    clan_tag = clan_initial_data.tag
                    clan_obj_for_members = clan_initial_data
                logger.info(f"Acesso clã '{MONITORED_CLAN_NAME}' OK.")

                logger.info("Inicializando cache membros..."); member_cache.clear()
                if clan_obj_for_members and hasattr(clan_obj_for_members, 'members'):
                    for member in clan_obj_for_members.members:
                        if member.tag: member_cache[member.tag] = {'name': member.name, 'role': str(member.role), 'trophies': member.trophies, 'league': member.league.name if member.league else 'N/A'}
                    logger.info(f"Cache membros inicializado com {len(member_cache)} membros.")
                else:
                    logger.warning("Não foi possível obter a lista de membros para inicializar o cache.")

                online_emb = discord.Embed(title=f"{emojis['success']} Bot Online e Monitorando!", description=f"Eventos do clã **{MONITORED_CLAN_NAME}** (`{clan_tag}`) e Guerras monitorados.", color=discord.Color.green())
                online_emb.add_field(name="Monitoramento", value=f"Event-Driven Ativo {emojis['sync']}", inline=False);
                await send_log_embed(online_emb, add_timestamp=True, add_bot_footer=True)

                if not check_war_end_report_task.is_running():
                     logger.info("Iniciando task check_war_end_report_task...")
                     check_war_end_report_task.start()
                else:
                     logger.warning("Task check_war_end_report_task já estava rodando.")

            else:
                logger.critical(f"FALHA GRAVE: Clã {CLAN_TAGS_TO_MONITOR[0]} inacessível pós-login.");
                await send_log_embed(discord.Embed(title=f"{emojis['error']} Erro Crítico - Acesso Clã", description=f"**Falha obter dados clã `{CLAN_TAGS_TO_MONITOR[0]}`.**", color=discord.Color.red(), timestamp=start_time))
        except Exception as e:
             logger.critical(f"FALHA GRAVE: Erro on_ready verificar clã: {e}", exc_info=True);
             await send_log_embed(discord.Embed(title=f"{emojis['error']} Erro Crítico - Init", description=f"**Erro inesperado inicialização:**\n`{e}`", color=discord.Color.red(), timestamp=start_time))


# --- Tratador de Erros App Commands ---
# ... (Igual v16.0.33) ...
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    error_embed = discord.Embed(color=discord.Color.red(), timestamp=datetime.now(TIMEZONE));
    cmd_name = interaction.command.name if interaction.command else 'N/A';
    error_embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • Comando: /{cmd_name}")
    handled = False; original_error = error.original if isinstance(error, app_commands.CommandInvokeError) else error

    expected_errors = (
        coc.NotFound, coc.Maintenance, asyncio.TimeoutError, coc.InvalidCredentials,
        # coc.InvalidTag removido, tratado abaixo se necessário
        coc.PrivateWarLog, coc.Forbidden,
        app_commands.CheckFailure, app_commands.CommandOnCooldown,
        app_commands.MissingPermissions, app_commands.BotMissingPermissions
    )

    if not isinstance(original_error, expected_errors):
        if isinstance(original_error, coc.ClashOfClansException) and "Invalid tag" in str(original_error):
             logger.warning(f"Erro esperado /{cmd_name}: Invalid Tag (detectado pela mensagem) - {original_error}")
             handled = True; error_embed.title = f"{emojis['error']} TAG Inválida"; error_embed.description = "TAG inválida."
             error_embed.color = discord.Color.red()
        else:
             logger.error(f"Erro não tratado /{cmd_name}: {type(original_error).__name__} - {original_error}", exc_info=True)
    else:
        logger.warning(f"Erro esperado /{cmd_name}: {type(original_error).__name__} - {original_error}")

    if isinstance(original_error, app_commands.CheckFailure): handled = True; error_embed.title = f"{emojis['error']} Acesso Negado"; error_embed.description = "Você não tem permissão."
    elif isinstance(original_error, app_commands.CommandOnCooldown): handled = True; error_embed.title = f"{emojis['time']} Cooldown"; error_embed.description = f"Aguarde `{original_error.retry_after:.1f}s`."; error_embed.color = 0xFFA500
    elif isinstance(original_error, app_commands.MissingPermissions): handled = True; error_embed.title = f"{emojis['error']} Permissão Negada (Usuário)"; error_embed.description = f"Falta permissão: `{', '.join(original_error.missing_permissions)}`."
    elif isinstance(original_error, app_commands.BotMissingPermissions): handled = True; error_embed.title = f"{emojis['error']} Permissão Negada (Bot)"; error_embed.description = f"Preciso permissão: `{', '.join(original_error.missing_permissions)}`."
    elif isinstance(original_error, coc.NotFound): handled = True; error_embed.title = f"{emojis['error']} Não Encontrado"; error_embed.description = "Recurso CoC não encontrado."
    elif isinstance(original_error, coc.InvalidCredentials): handled = True; error_embed.title = f"{emojis['error']} Erro Credenciais CoC"; error_embed.description = "Credenciais (Email/Senha) inválidas."; error_embed.color=0xCC0000
    elif isinstance(original_error, coc.Forbidden): handled = True; error_embed.title = f"{emojis['error']} Erro Permissão API CoC"; error_embed.description = "Acesso negado pela API (IP/chave?)."; error_embed.color=0xCC0000
    elif isinstance(original_error, coc.Maintenance): handled = True; error_embed.title = f"{emojis['warning']} Manutenção API CoC"; error_embed.description = "API em manutenção."; error_embed.color=0xFFA500
    elif isinstance(original_error, coc.PrivateWarLog): handled=True; error_embed.title=f"{emojis['warning']}Log Guerra Privado"; error_embed.description="Log privado."; error_embed.color=0xFFA500
    elif isinstance(original_error, coc.ClashOfClansException) and not handled:
        handled = True; error_embed.title = f"{emojis['warning']} Erro API CoC"; error_embed.description = f"Erro API: `{type(original_error).__name__}`."; error_embed.color=0xFFA500
    elif isinstance(original_error, asyncio.TimeoutError): handled = True; error_embed.title = f"{emojis['error']} Timeout"; error_embed.description = "Operação demorou."
    elif not coc_client and not isinstance(original_error, (coc.InvalidCredentials, coc.Maintenance)): handled = True; error_embed.title = f"{emojis['error']} API CoC Offline"; error_embed.description = "API CoC inativa."; error_embed.color=0xFF8C00

    if not handled: error_embed.title = f"{emojis['error']} Erro Inesperado"; error_embed.description = f"Erro: `{type(original_error).__name__}`"
    try:
        resp_method = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
        await resp_method(embed=error_embed, ephemeral=True)
    except discord.NotFound: logger.warning(f"Interação /{cmd_name} expirou.")
    except Exception as e_send: logger.error(f"Falha enviar msg erro /{cmd_name}: {e_send}", exc_info=True)


# --- Comandos de Barra ---
# ... (Definições de Grupos) ...
admin_group = app_commands.Group(name="admin", description="Comandos administrativos.", default_permissions=discord.Permissions(administrator=True))
war_group = app_commands.Group(name="guerra", description="Comandos de Guerras e CWL.")
info_group = app_commands.Group(name="info", description="Comandos de informação.")
buscar_group = app_commands.Group(name="buscar", description="Comandos para buscar clans e jogadores.")
rank_group = app_commands.Group(name="rank", description="Comandos para exibir rankings.")

# --- Comandos (Restantes sem alterações relevantes) ---
# ... (status_command, top_command, setcanal, setclan) ...
# ... (ataques_command, liga_ataques_command, warlog_command) ...
# ... (membro_command) ...
# ... (buscar_clan_command, buscar_jogador_command) ...
# ... (rank_clans_command, rank_jogadores_command) ...
# ... (ligas_command) ...
# ... (ajuda_command) ...

# --- Função Display Attacks (Versão v15) ---
# ... (Igual v16.0.30) ...
async def display_attacks_remaining_slash(interaction: discord.Interaction, war, war_type="Guerra"):
    """Função copiada da v15 para exibir ataques restantes, priorizando um único embed."""
    if not interaction.channel: logger.error(f"Erro display_attacks_remaining_slash: Canal da interação inválido."); await interaction.followup.send(f"{emojis['error']}Erro: Não foi possível encontrar o canal para enviar a resposta.", ephemeral=True); return
    if not war or war.state not in ['inWar', 'preparation']: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Não em {war_type} ativa ou em preparação.", color=discord.Color.orange())); return

    our_c = None
    en_c = None
    our_clan_tag = CLAN_TAGS_TO_MONITOR[0] if CLAN_TAGS_TO_MONITOR else None
    if our_clan_tag:
        if hasattr(war, 'clan') and war.clan and war.clan.tag == our_clan_tag:
            our_c = war.clan
            en_c = war.opponent
        elif hasattr(war, 'opponent') and war.opponent and war.opponent.tag == our_clan_tag:
            our_c = war.opponent
            en_c = war.clan
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
    for m in members: total_possible += attacks_per; attacks_d = len(m.attacks); total_done += attacks_d; attacks_l = attacks_per - attacks_d;
    if attacks_l > 0: name=m.name; th=m.town_hall; map_pos=m.map_position; remaining.append(f"{map_pos}. `{name}` (CV{th}): **{attacks_l}** atk(s)")

    title = f"{emojis['war_attack']} Ataques Restantes - {war_type} vs {en_c_name}";
    base_embed = discord.Embed(title=title, description=state_info, color=color, timestamp=timestamp);
    base_embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • Clã: {our_c_name}")

    summary = f"**{total_done} / {total_possible}** ataques realizados."; base_embed.add_field(name="Resumo", value=summary, inline=False)

    if not remaining:
        base_embed.add_field(name="Situação", value=f"{emojis['success']} Todos atacaram!", inline=False); base_embed.color = discord.Color.green();
        await interaction.followup.send(embed=base_embed)
    else:
        temp_embed = base_embed.copy();
        field_title = "Membros Pendentes";
        full_list_str = "\n".join(remaining)

        if len(full_list_str) <= 1024:
            logger.info(f"display_attacks_remaining_slash (v15 logic): Lista cabe em 1 campo ({len(full_list_str)} chars).")
            temp_embed.add_field(name=field_title, value=full_list_str, inline=False);
            await interaction.followup.send(embed=temp_embed)
        else:
            logger.info(f"display_attacks_remaining_slash (v15 logic): Lista excede 1024 chars ({len(full_list_str)}). Usando send_embeds_splitted.")
            await interaction.followup.send(embed=base_embed)
            if interaction.channel:
                split_list_embed = discord.Embed(color=color)
                split_list_embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
                await send_embeds_splitted(interaction.channel, split_list_embed, field_title, remaining, max_items_per_embed=25)
            else:
                 logger.error(f"Erro display_attacks_remaining_slash (v15 logic): Canal split inválido.")


# --- NOVA TASK E FUNÇÃO AUXILIAR ---
# ... (send_missed_attacks_report, check_war_end_report_task) ...
# (Sem alterações nestas funções)
async def send_missed_attacks_report(war_obj: coc.ClanWar, missed_list: List[str], war_type_str: str):
    """Formata e envia o relatório de ataques perdidos."""
    global log_channel, ROLE_ID_MISSED_ATTACK, clan_data_cache, bot

    if not log_channel:
        logger.error("Relatório de ataques perdidos não enviado: Canal de log inválido.")
        return
    if not missed_list:
        logger.info(f"Tentativa de enviar relatório de ataques perdidos, mas a lista está vazia ({war_type_str}).")
        return

    mention_str = ""
    role_to_mention = None
    if ROLE_ID_MISSED_ATTACK:
        try:
            guild = log_channel.guild
            role_to_mention = guild.get_role(ROLE_ID_MISSED_ATTACK)
            if role_to_mention:
                mention_str = role_to_mention.mention
            else:
                logger.warning(f"Cargo para ataques perdidos (ID: {ROLE_ID_MISSED_ATTACK}) não encontrado.")
        except Exception as e:
            logger.error(f"Erro ao obter cargo para ataques perdidos: {e}")

    custom_message = f"{mention_str} Ataques Não Realizados! Estes membros estão liberados para serem banidos por não atacar:".strip()

    our_clan_obj = None
    opponent_clan_obj = None
    war_clan_tag = None
    if war_obj.clan.tag in CLAN_TAGS_TO_MONITOR:
        our_clan_obj = war_obj.clan
        opponent_clan_obj = war_obj.opponent
        war_clan_tag = war_obj.clan.tag
    elif war_obj.opponent.tag in CLAN_TAGS_TO_MONITOR:
        our_clan_obj = war_obj.opponent
        opponent_clan_obj = war_obj.clan
        war_clan_tag = war_obj.opponent.tag

    if not our_clan_obj or not opponent_clan_obj or not war_clan_tag:
        logger.error("Não foi possível identificar clãs no objeto de guerra para o relatório de ataques perdidos.")
        return

    opponent_name = getattr(opponent_clan_obj, 'name', '?')

    clan_info = clan_data_cache.get(war_clan_tag, {})
    if not clan_info or not isinstance(clan_info, dict):
        try: clan_info = await get_clan_data_with_cache(war_clan_tag) or {}
        except Exception: clan_info = {}
    badge_url = clan_info.get('badge_url')

    missed_embed = discord.Embed(
        title=f"{emojis['missed_attack']} Ataques Não Realizados - {war_type_str}",
        description=f"Membros que não usaram todos os ataques contra **{opponent_name}**:",
        color=discord.Color.red()
    )
    if badge_url:
        missed_embed.set_thumbnail(url=badge_url)

    missed_embed.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION}")
    missed_embed.timestamp = datetime.now(TIMEZONE)

    try:
        await log_channel.send(custom_message)
        await asyncio.sleep(0.3)
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem de alerta para ataques perdidos: {e}")

    await send_embeds_splitted(log_channel, missed_embed, "Membros", missed_list)


@tasks.loop(minutes=15)
async def check_war_end_report_task():
    global coc_client, reported_war_ends, CLAN_TAGS_TO_MONITOR

    if not coc_client:
        return

    clan_tag = CLAN_TAGS_TO_MONITOR[0]
    if not clan_tag:
        return

    logger.debug(f"Task check_war_end: Verificando guerras para {clan_tag}...")

    try:
        # --- Verifica Guerra Normal ---
        try:
            war = await coc_client.get_current_war(clan_tag)
            if war and not war.is_cwl and war.state == 'warEnded':
                prep_time_str = war.preparation_start_time.time.isoformat() if war.preparation_start_time else "unknown_time"
                opponent_tag_str = getattr(war.opponent, 'tag', 'unknown_opponent')
                war_id = f"war-{opponent_tag_str}-{prep_time_str}"

                if war_id not in reported_war_ends:
                    logger.info(f"Task check_war_end: Guerra Normal vs {war.opponent.name} finalizada detectada.")
                    missed_list = []
                    attacks_per = war.attacks_per_member
                    our_clan_obj = war.clan

                    if hasattr(our_clan_obj, 'members') and our_clan_obj.members:
                        for m in our_clan_obj.members:
                            attacks_made = len(m.attacks)
                            attacks_missed = attacks_per - attacks_made
                            if attacks_missed > 0:
                                missed_list.append(f"`{m.name}` (CV{m.town_hall}): **{attacks_missed}** perdido(s)")

                        if missed_list:
                            await send_missed_attacks_report(war, missed_list, "Guerra Normal")
                        else:
                             logger.info(f"Guerra Normal vs {war.opponent.name} finalizada. Todos atacaram.")

                        reported_war_ends.add(war_id)
                        logger.info(f"Guerra Normal {war_id} marcada como reportada.")
                    else:
                        logger.warning(f"Não foi possível obter lista de membros para Guerra Normal finalizada {war_id}")
        except coc.NotFound:
            pass
        except coc.PrivateWarLog:
            logger.warning("Task check_war_end: Log de guerra normal privado.")
        except Exception as e:
            logger.error(f"Task check_war_end: Erro ao verificar guerra normal: {e}", exc_info=True)


        # --- Verifica Guerra de Liga (CWL) ---
        try:
            lg = await coc_client.get_league_group(clan_tag)
            if lg and lg.state != "notInWar":
                lg_wars = await lg.get_wars(clan_tag)
                for lw in lg_wars:
                    if lw.state == 'warEnded':
                        our_clan_lw = None
                        opponent_lw = None
                        if lw.clan.tag == clan_tag:
                            our_clan_lw = lw.clan
                            opponent_lw = lw.opponent
                        elif lw.opponent.tag == clan_tag:
                            our_clan_lw = lw.opponent
                            opponent_lw = lw.clan
                        else:
                             continue

                        prep_time_lw_str = lw.preparation_start_time.time.isoformat() if lw.preparation_start_time else "unknown_time"
                        opponent_lw_tag_str = getattr(opponent_lw, 'tag', 'unknown_opponent')
                        league_war_id = f"league-{opponent_lw_tag_str}-{prep_time_lw_str}"

                        if league_war_id not in reported_war_ends:
                             logger.info(f"Task check_war_end: Guerra de Liga vs {opponent_lw.name} finalizada detectada.")
                             missed_list_lw = []
                             attacks_per_lw = lw.attacks_per_member

                             if hasattr(our_clan_lw, 'members') and our_clan_lw.members:
                                 for m in our_clan_lw.members:
                                     attacks_made = len(m.attacks)
                                     attacks_missed = attacks_per_lw - attacks_made
                                     if attacks_missed > 0:
                                         missed_list_lw.append(f"`{m.name}` (CV{m.town_hall}): **{attacks_missed}** perdido(s)")

                                 if missed_list_lw:
                                     await send_missed_attacks_report(lw, missed_list_lw, "Guerra de Liga")
                                 else:
                                     logger.info(f"Guerra de Liga vs {opponent_lw.name} finalizada. Todos atacaram.")

                                 reported_war_ends.add(league_war_id)
                                 logger.info(f"Guerra de Liga {league_war_id} marcada como reportada.")
                             else:
                                 logger.warning(f"Não foi possível obter lista de membros para Guerra de Liga finalizada {league_war_id}")
        except coc.NotFound:
             pass
        except Exception as e:
            logger.error(f"Task check_war_end: Erro ao verificar CWL: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Task check_war_end: Erro GERAL na task: {e}", exc_info=True)


# Adiciona os grupos à árvore
bot.tree.add_command(admin_group)
bot.tree.add_command(war_group)
bot.tree.add_command(info_group)
bot.tree.add_command(buscar_group)
bot.tree.add_command(rank_group)

# --- Função Principal ---
# ... (Igual v16.0.32) ...
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
