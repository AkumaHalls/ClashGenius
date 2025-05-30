# -*- coding: utf-8 -*-
# Versão 18.2 - Painel Web SPA (Correção Sintaxe Decoradores Eventos)

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
from coc import ClanWar, Player, Clan, WarAttack, Timestamp, ClanMember
from coc.cwl import LeagueGroup, LeagueWar

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

BOT_VERSION = "18.2" # << VERSÃO ATUALIZADA
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

# --- Funções Auxiliares (get_clan_data, get_player_data, etc.) ---
# (Estas funções permanecem como na versão anterior, sem necessidade de alteração para esta correção)
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
    # (Código como antes)
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

# --- Funções de Guerra ---
# (COLE AQUI SUAS FUNÇÕES COMPLETAS format_attacks_remaining_embed e send_missed_attacks_report
#  da versão anterior que estava funcionando. Elas não mudam para esta correção de sintaxe.)
# Exemplo resumido - SUBSTITUA PELA SUA LÓGICA COMPLETA:
async def format_attacks_remaining_embed(war: ClanWar) -> Optional[List[discord.Embed]]:
    logger.debug(f"Formatando ataques restantes para guerra...") # Sua lógica completa aqui
    return [] # Substitua pelo retorno real
async def send_missed_attacks_report(war: ClanWar, missed_members_details: List[str], war_type: str) -> None:
    logger.debug(f"Enviando relatório de ataques perdidos...") # Sua lógica completa aqui
    pass


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
    # (COLE AQUI SUA LÓGICA COMPLETA de on_app_command_error da versão anterior)
    # Exemplo resumido - SUBSTITUA PELA SUA LÓGICA COMPLETA:
    logger.error(f"Erro de comando: {error}", exc_info=True)
    await interaction.response.send_message(f"Ocorreu um erro: {error}", ephemeral=True)


# --- CoC Event Handlers (Sintaxe dos decoradores corrigida) ---
async def register_coc_events(coc_client: coc.EventsClient):
    if not CLAN_TAG: logger.warning("CLAN_TAG não definido."); return
    logger.info(f"Registrando handlers CoC para clã {CLAN_TAG}...")

    @coc_client.event # CORRIGIDO
    @coc.ClanEvents.member_join(tags=[CLAN_TAG]) # CORRIGIDO
    async def on_member_join_event(old_member: Optional[ClanMember], member: ClanMember):
        if not member or not hasattr(member, 'clan'): return
        clan_name_join = member.clan.name if member.clan else "N/A"
        # (Sua lógica de criar e enviar embed de member_join aqui)
        # Exemplo:
        embed = discord.Embed(title="👋 Novo Membro", description=f"**{member.name}** (`{member.tag}`) entrou!", color=discord.Color.green())
        await send_log_embed(embed)
        add_event_to_log(f"👋 {member.name} (CV{member.town_hall}) entrou no clã {clan_name_join}.")

    @coc_client.event # CORRIGIDO
    @coc.ClanEvents.member_leave(tags=[CLAN_TAG]) # CORRIGIDO
    async def on_member_leave_event(old_member: ClanMember, member: ClanMember):
        if not old_member: return
        # (Sua lógica de criar e enviar embed de member_leave aqui)
        embed = discord.Embed(title="👋 Membro Saiu", description=f"**{old_member.name}** (`{old_member.tag}`) saiu.", color=discord.Color.red())
        await send_log_embed(embed)
        add_event_to_log(f"🚪 {old_member.name} (CV{old_member.town_hall}) saiu do clã.")

    @coc_client.event # CORRIGIDO
    @coc.ClanEvents.member_donations(tags=[CLAN_TAG]) # CORRIGIDO
    async def on_member_donations_event(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan'): return
        diff = member.donations - old_member.donations
        if diff <= 0: return
        # (Sua lógica de criar e enviar embed de doações aqui)
        add_event_to_log(f"🎁 {member.name} doou {diff} tropas.")

    @coc_client.event # CORRIGIDO
    @coc.ClanEvents.member_received(tags=[CLAN_TAG]) # CORRIGIDO
    async def on_member_received_event(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan'): return
        diff = member.received - old_member.received
        if diff <= 0: return
        # (Sua lógica de criar e enviar embed de recebimentos aqui)
        add_event_to_log(f"📥 {member.name} recebeu {diff} tropas.")

    @coc_client.event # CORRIGIDO
    @coc.ClanEvents.member_role_change(tags=[CLAN_TAG]) # CORRIGIDO
    async def on_member_role_change_event(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan') or old_member.role == member.role: return
        # (Sua lógica de criar e enviar embed de mudança de cargo aqui)
        add_event_to_log(f"🔄 Cargo de {member.name} mudou de {old_member.role} para {member.role}.")

    @coc_client.event # CORRIGIDO
    @coc.ClanEvents.member_league_change(tags=[CLAN_TAG]) # CORRIGIDO
    async def on_member_league_change_event(old_member: ClanMember, member: ClanMember):
        if not member or not old_member or not hasattr(member, 'clan') or old_member.league == member.league: return
        # (Sua lógica de criar e enviar embed de mudança de liga aqui)
        add_event_to_log(f"🏆 Liga de {member.name} mudou para {member.league.name if member.league else 'Sem Liga'}.")

    @coc_client.event # CORRIGIDO
    @coc.ClanEvents.member_trophies_change(tags=[CLAN_TAG]) # CORRIGIDO
    async def on_member_trophies_change_event(old_member: ClanMember, member: ClanMember):
        if not member or not old_member: return
        diff = member.trophies - old_member.trophies
        if abs(diff) < 5 : return
        # (Sua lógica de criar e enviar embed de mudança de troféus aqui)
        direction = "ganhou" if diff > 0 else "perdeu"
        add_event_to_log(f"🏆 {member.name} {direction} {abs(diff)} troféus (Total: {member.trophies}).")

    @coc_client.event # CORRIGIDO
    @coc.WarEvents.war_attack(tags=[CLAN_TAG]) # CORRIGIDO
    async def on_war_attack_event(attack: WarAttack, war: ClanWar):
        # (COLE AQUI SUA LÓGICA COMPLETA de on_war_attack da versão anterior,
        #  lembre-se de adicionar as chamadas a add_event_to_log no final dela)
        # Exemplo resumido - SUBSTITUA PELA SUA LÓGICA COMPLETA:
        logger.debug(f"Ataque de guerra detectado: {attack.attacker_tag} vs {attack.defender_tag}")
        # ... sua lógica de buscar players, determinar se é ataque/defesa, enviar embed ...
        # if is_our_attack: add_event_to_log(f"⚔️ {attacker_name} atacou {defender_name} ({attack.stars}⭐)")
        # elif is_our_defense: add_event_to_log(f"🛡️ {defender_name} foi atacado por {attacker_name} ({attack.stars}⭐)")
        pass

    logger.info("Manipuladores de eventos CoC registrados.")

# --- Tasks ---
@tasks.loop(minutes=10)
async def check_war_end_report_task():
    # (COLE AQUI SUA LÓGICA COMPLETA de check_war_end_report_task da versão anterior,
    #  incluindo a função interna process_war e as chamadas a add_event_to_log)
    # Exemplo resumido - SUBSTITUA PELA SUA LÓGICA COMPLETA:
    logger.debug("Verificando fim de guerra...")
    # ... sua lógica de buscar guerra regular, CWL, e chamar process_war ...
    # Dentro de process_war, após verificar ataques perdidos:
    # if missed_members_details_task: add_event_to_log(f"❌ {len(missed_members_details_task)} membro(s) não atacaram...")
    # else: add_event_to_log(f"✅ Todos os ataques realizados...")
    pass

@check_war_end_report_task.before_loop
async def before_check_war():
    await bot.wait_until_ready()
    logger.info("Bot pronto. Task 'check_war_end_report_task' pode iniciar.")

# --- Slash Commands ---
# (COLE AQUI TODOS OS SEUS GRUPOS DE COMANDOS E DEFINIÇÕES DE COMANDOS SLASH
#  da versão anterior que estava funcionando.)
# Exemplo:
# admin_group = app_commands.Group(name="admin", description="Comandos administrativos")
# @admin_group.command(name="ping", description="Verifica a latência do bot")
# async def admin_ping(interaction: discord.Interaction):
#     await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)}ms", ephemeral=True)
# bot.tree.add_command(admin_group)
# (Repita para war_group, info_group, search_group, rank_group)


# ============================================================================ #
# ==================== PAINEL WEB - LÓGICA E ENDPOINTS API ==================== #
# ============================================================================ #
# (O restante do código do painel web: web_api_cache, get_cached_web_data,
#  todas as funções fetch_..._for_web_api, todos os api_..._handler,
#  handle_panel_index, e setup_web_server permanecem EXATAMENTE como na última
#  resposta completa que te enviei (v18.0 com correção para WarLogEntry).
#  A única mudança foi nas importações no TOPO do arquivo.)
#
#  Para garantir, vou colar essa seção novamente. Certifique-se que as
#  importações no topo do arquivo estão corretas (com coc.cwl).

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
    current_war: Optional[Union[ClanWar, coc.WarLogEntry]] = None # Usa coc.WarLogEntry
    war_type_description = "Nenhuma guerra"
    try:
        lg: LeagueGroup = await bot.coc_client.get_league_group(CLAN_TAG) # LeagueGroup usado diretamente
        if lg and lg.state != "notInWar" and lg.rounds:
            for i, war_tags in reversed(list(enumerate(lg.rounds))):
                for tag in war_tags:
                    try:
                        war: LeagueWar = await lg.get_league_war(tag) # LeagueWar usado diretamente
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

    if isinstance(current_war, ClanWar): # Também cobre LeagueWar, pois herda de ClanWar
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
    elif isinstance(current_war, coc.WarLogEntry): # Uso de coc.WarLogEntry
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
        group: LeagueGroup = await bot.coc_client.get_league_group(CLAN_TAG) # LeagueGroup usado diretamente
        if not group or group.state == "notInWar": return {"status": "notInWar", "message": "Clã não está em CWL."}
        rounds_data = []
        for i, round_war_tags in enumerate(group.rounds):
            round_info = {"round_number": i + 1, "wars": []}
            for war_tag in round_war_tags:
                try:
                    war: LeagueWar = await group.get_league_war(war_tag) # LeagueWar usado diretamente
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
        if hasattr(group, 'clans') and group.clans: # Adicionando verificação
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
    # (Sua lógica de setup_hook completa aqui, incluindo login CoC, registro de eventos,
    #  configuração do servidor web, e sincronização de comandos slash)
    logger.info("Executando setup_hook...")
    # ... (Resto como na v18.1)
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
    # (Sua lógica completa de main aqui)
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
    # (Sua lógica completa de if __name__ == "__main__" aqui)
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
