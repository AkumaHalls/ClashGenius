# -*- coding: utf-8 -*-
# Versão 20.1.16-FINAL-STABLE - Adicionado monitoramento de doações e tropas recebidas. #

import os
import logging
import asyncio
import datetime
import json
from aiohttp import web
from typing import Dict, List, Optional, Any, Set
import discord
from discord.ext import commands, tasks
import coc
import pytz
from dotenv import load_dotenv
import motor.motor_asyncio
from pymongo.uri_parser import parse_uri
from pymongo import DESCENDING

# --- Configuração do Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("coc_discord_bot")

# --- Carregar Variáveis de Ambiente ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COC_EMAIL = os.getenv("COC_EMAIL")
COC_PASSWORD = os.getenv("COC_PASSWORD")
CLAN_TAG = os.getenv("CLAN_TAG")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
MONGO_DB_URL = os.getenv("MONGO_DB_URL")
ROLE_ID_1STAR_ALERT = int(os.getenv("ROLE_ID_1STAR_ALERT", 0)) 
ROLE_ID_MISSED_ATTACK = int(os.getenv("ROLE_ID_MISSED_ATTACK", 0))

# --- Constantes e Configurações Globais ---
BOT_VERSION = "20.1.31-HIGHLIGHTS-STRICT-FILTER"
TIMEZONE = pytz.timezone('America/Sao_Paulo')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# --- Inicialização dos Clientes ---
bot = commands.Bot(command_prefix="!", intents=intents)
coc_client: Optional[coc.Client] = None
events_client: Optional[coc.EventsClient] = None
api_client: Optional[coc.Client] = None

# --- Caches em Memória ---
player_short_term_cache: Dict[str, Any] = {}
clan_cache: Dict[str, Dict[str, Any]] = {}
web_api_cache: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION_SECONDS = 300
WEB_API_CACHE_DURATION_SECONDS = 45
last_war_end_time: Optional[datetime.datetime] = None
war_attack_cache: Dict[str, Any] = {"war_end_time": None, "processed_attacks": set()}


# --- FUNÇÕES DE BANCO DE DADOS (MongoDB) ---
async def load_player_notes_from_db() -> Dict[str, Dict[str, str]]:
    if not hasattr(bot, 'db') or bot.db is None:
        logger.warning("Banco de dados não disponível, não é possível carregar as notas.")
        return {}
    try:
        notes_cursor = bot.db.player_notes.find({})
        notes_from_db = {note_doc["_id"]: {"text": note_doc.get("text", ""),"priority": note_doc.get("priority", "none")} async for note_doc in notes_cursor if "_id" in note_doc}
        logger.info(f"Carregadas {len(notes_from_db)} notas do MongoDB.")
        return notes_from_db
    except Exception as e:
        logger.error(f"Erro ao carregar notas do MongoDB: {e}", exc_info=True)
        return {}

async def save_player_note_to_db(player_tag: str, text: str, priority: str):
    if not hasattr(bot, 'db') or bot.db is None:
        logger.error("Banco de dados não disponível, não é possível salvar a nota.")
        raise ConnectionError("Banco de dados não conectado.")
    try:
        player_tag_decoded = coc.utils.correct_tag(player_tag)
        await bot.db.player_notes.update_one(
            {"_id": player_tag_decoded},
            {"$set": {"text": text, "priority": priority}},
            upsert=True
        )
        logger.info(f"Nota salva no MongoDB para {player_tag_decoded}.")
    except Exception as e:
        logger.error(f"Erro ao salvar nota no MongoDB para {player_tag}: {e}", exc_info=True)
        raise

def _sanitize_keys_for_mongo(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _sanitize_keys_for_mongo(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_keys_for_mongo(elem) for elem in obj]
    return obj

async def save_war_to_history(war_data: Dict[str, Any]):
    if not hasattr(bot, 'db') or bot.db is None:
        logger.error("Banco de dados não disponível, não é possível salvar o histórico da guerra.")
        return
    try:
        war_collection = bot.db.war_history
        sanitized_war_data = _sanitize_keys_for_mongo(war_data)
        sanitized_war_data['_id'] = sanitized_war_data['war_data']['end_time_iso']
        
        await war_collection.replace_one({'_id': sanitized_war_data['_id']}, sanitized_war_data, upsert=True)
        logger.info(f"Guerra finalizada em {sanitized_war_data['_id']} salva no histórico.")

        count = await war_collection.count_documents({})
        if count > 9:
            oldest_wars_cursor = war_collection.find().sort("war_data.end_time_iso", 1).limit(count - 9)
            async for old_war in oldest_wars_cursor:
                await war_collection.delete_one({"_id": old_war["_id"]})
                logger.info(f"Guerra mais antiga ({old_war['_id']}) removida do histórico para manter o limite de 9.")

    except Exception as e:
        logger.error(f"Erro ao salvar guerra no histórico do MongoDB: {e}", exc_info=True)


# --- FUNÇÕES AUXILIARES (HELPERS) ---
async def send_log_embed(embed_to_log: discord.Embed, content: str = None) -> None:
    if not CHANNEL_ID: return
    await bot.wait_until_ready()
    try:
        channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
        embed_to_log.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
        embed_to_log.timestamp = datetime.datetime.now(TIMEZONE)
        await channel.send(content=content, embed=embed_to_log)
    except (discord.NotFound, discord.Forbidden, Exception) as e:
        logger.error(f"Erro ao enviar embed para o canal {CHANNEL_ID}: {e}", exc_info=True)

# --- FUNÇÕES DE BUSCA DE DADOS (API CoC) ---
async def get_player_data(tag: str) -> Optional[coc.Player]:
    if not api_client: return None
    normalized_tag = coc.utils.correct_tag(tag)
    if normalized_tag in player_short_term_cache:
        return player_short_term_cache[normalized_tag]
    try:
        player = await api_client.get_player(normalized_tag)
        player_short_term_cache[normalized_tag] = player
        return player
    except Exception:
        return None

async def get_clan_data_with_cache(tag: str) -> Optional[coc.Clan]:
    if not api_client: return None
    normalized_tag = coc.utils.correct_tag(tag)
    now = datetime.datetime.now()
    if normalized_tag in clan_cache and (now - clan_cache[normalized_tag]["timestamp"]).total_seconds() < CACHE_DURATION_SECONDS:
        return clan_cache[normalized_tag]["data"]
    try:
        clan_data = await api_client.get_clan(normalized_tag)
        clan_cache[normalized_tag] = {"data": clan_data, "timestamp": now}
        return clan_data
    except Exception as e:
        logger.error(f"Erro ao buscar dados do clã {tag}: {e}")
        return None

# --- DEFINIÇÃO DOS EVENTOS DO COC ---
async def on_clan_member_join(member, clan):
    try:
        logger.info(f"Evento disparado: {member.name} entrou no clã {clan.name}")
        if clan.tag != CLAN_TAG: return
        embed = discord.Embed(
            title="➡️ Novo Membro no Clã",
            description=f"**{member.name}** ({member.tag}) entrou no clã.",
            color=discord.Color.blue()
        )
        embed.add_field(name="CV", value=member.town_hall, inline=True)
        embed.add_field(name="Liga", value=member.league.name if member.league else "N/A", inline=True)
        embed.add_field(name="Troféus", value=f"🏆 {member.trophies}", inline=True)
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no evento member_join: {e}", exc_info=True)

async def on_clan_member_leave(member, clan):
    try:
        logger.info(f"Evento disparado: {member.name} saiu do clã {clan.name}")
        if clan.tag != CLAN_TAG: return
        embed = discord.Embed(
            title="⬅️ Membro Saiu do Clã",
            description=f"**{member.name}** ({member.tag}) saiu do clã.",
            color=discord.Color.dark_grey()
        )
        embed.add_field(name="CV", value=member.town_hall, inline=True)
        embed.add_field(name="Cargo", value=member.role.name.capitalize() if member.role else "N/A", inline=True)
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no evento member_leave: {e}", exc_info=True)

async def on_war_attack(attack, war):
    try:
        if not attack or not hasattr(attack, 'attacker') or not attack.attacker: return
        
        attacker = war.get_member(attack.attacker_tag)
        defender = war.get_member(attack.defender_tag)
        
        if not attacker or not defender: return

        is_our_attack = attacker.clan.tag == CLAN_TAG
        war_type = "CWL" if war.is_cwl else "Guerra"
        stars_str = "⭐" * attack.stars + "⚫" * (3 - attack.stars)
        
        attacker_pos = f"{attacker.map_position:02d}"
        defender_pos = f"{defender.map_position:02d}"
        
        attacker_str = f"{attacker_pos} {attacker.name} (CV{attacker.town_hall})"
        defender_str = f"{defender_pos} {defender.name} (CV{defender.town_hall})"
        
        if is_our_attack:
            logger.info(f"Ataque realizado por {attacker.name} processado.")
            attack_embed = discord.Embed(
                title=f"⚔️ Ataque Realizado ({war_type})",
                description=f"{attacker.clan.name}",
                color=discord.Color.blue()
            )
            attack_embed.add_field(
                name="Detalhes",
                value=f"{attacker_str} atacou {defender_str}",
                inline=False
            )
            attack_embed.add_field(
                name="Resultado",
                value=f"{stars_str} ({attack.destruction}%)",
                inline=False
            )
            if hasattr(war.opponent.badge, 'url'):
                attack_embed.set_thumbnail(url=war.opponent.badge.url)
            await send_log_embed(attack_embed)

            if attack.stars <= 1:
                logger.info(f"Ataque fora do padrão detectado por {attacker.name}.")
                alert_embed = discord.Embed(
                    title=f"⚠️ Ataque fora do padrão!",
                    description=f"**{attacker.clan.name}**\n⚔️ **Ataque Realizado ({war_type})**",
                    color=discord.Color.red()
                )
                alert_embed.add_field(
                    name="Detalhes",
                    value=f"{attacker_str} atacou {defender_str}",
                    inline=False
                )
                alert_embed.add_field(
                    name="Resultado",
                    value=f"{'⚫⚫⚫' if attack.stars == 0 else '⭐⚫⚫'} ({attack.destruction}%)",
                    inline=False
                )
                if hasattr(war.opponent.badge, 'url'):
                    alert_embed.set_thumbnail(url=war.opponent.badge.url)
                
                role_mention = ""
                if ROLE_ID_1STAR_ALERT:
                    role_mention = f"<@&{ROLE_ID_1STAR_ALERT}>"
                else:
                    logger.warning("ROLE_ID_1STAR_ALERT não configurado.")
                await send_log_embed(alert_embed, content=f"{role_mention} Atenção ao ataque fora do padrão!")
        else:
            logger.info(f"Defesa de {defender.name} processada.")
            defense_embed = discord.Embed(
                title=f"🛡️ Defesa Recebida ({war_type})",
                description=f"{defender.clan.name}",
                color=discord.Color.orange()
            )
            defense_embed.add_field(
                name="Detalhes",
                value=f"{defender_str} foi atacado por {attacker_str}",
                inline=False
            )
            defense_embed.add_field(
                name="Resultado",
                value=f"{stars_str} ({attack.destruction}%)",
                inline=False
            )
            if hasattr(war.clan.badge, 'url'):
                defense_embed.set_thumbnail(url=war.clan.badge.url)
            await send_log_embed(defense_embed)
            
    except Exception as e:
        logger.error(f"Erro em on_war_attack: {e}", exc_info=True)


async def on_clan_member_role_change(old_member, new_member):
    try:
        logger.info(f"Evento disparado: Mudança de cargo de {new_member.name}")
        embed = discord.Embed(
            title="✨ Mudança de Cargo",
            description=f"O cargo de **{new_member.name}** foi alterado.",
            color=discord.Color.purple()
        )
        embed.add_field(name="Cargo Antigo", value=old_member.role.name.capitalize(), inline=True)
        embed.add_field(name="Novo Cargo", value=new_member.role.name.capitalize(), inline=True)
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no evento member_role_change: {e}", exc_info=True)


async def on_clan_member_trophies_change(old_member, new_member):
    try:
        diff = new_member.trophies - old_member.trophies
        if diff == 0: return
        
        logger.info(f"Evento disparado: {new_member.name} mudança de troféus: {diff}")
        action = "ganhou" if diff > 0 else "perdeu"
        color = discord.Color.green() if diff > 0 else discord.Color.red()
        trophy_emoji = "🏆" if diff > 0 else "💔"
        
        embed = discord.Embed(
            description=f"{trophy_emoji} **{new_member.name}** {action} **{abs(diff)}** troféus (Total: {new_member.trophies})",
            color=color
        )
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no evento member_trophies_change: {e}", exc_info=True)


async def on_clan_member_league_change(old_member, new_member):
    try:
        logger.info(f"Evento disparado: {new_member.name} mudou de liga")
        embed = discord.Embed(
            title="🛡️ Mudança de Liga",
            description=f"**{new_member.name}** mudou de liga!",
            color=0x6E2C00
        )
        embed.add_field(name="Liga Anterior", value=old_member.league.name if old_member.league else "N/A", inline=True)
        embed.add_field(name="Nova Liga", value=new_member.league.name if new_member.league else "N/A", inline=True)
        
        if hasattr(new_member.league, 'icon') and hasattr(new_member.league.icon, 'medium'):
            embed.set_thumbnail(url=new_member.league.icon.medium)
            
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no evento member_league_change: {e}", exc_info=True)

async def on_member_donations(old_member, new_member):
    try:
        donation_diff = new_member.donations - old_member.donations
        if donation_diff <= 0: return
        logger.info(f"Evento: {new_member.name} doou {donation_diff} tropas.")
        embed = discord.Embed(
            description=f"🎁 **{new_member.name}** doou **{donation_diff}** tropas (Total: {new_member.donations}).",
            color=0xf1c40f # Gold color
        )
        embed.set_author(name=f"Clã: {new_member.clan.name}", icon_url=new_member.clan.badge.url)
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no evento member_donations: {e}", exc_info=True)

async def on_member_received(old_member, new_member):
    try:
        received_diff = new_member.received - old_member.received
        if received_diff <= 0: return
        logger.info(f"Evento: {new_member.name} recebeu {received_diff} tropas.")
        embed = discord.Embed(
            description=f"📥 **{new_member.name}** recebeu **{received_diff}** tropas (Total: {new_member.received}).",
            color=0x3498db # Blue color
        )
        embed.set_author(name=f"Clã: {new_member.clan.name}", icon_url=new_member.clan.badge.url)
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no evento member_received: {e}", exc_info=True)

# --- CONFIGURAÇÃO DOS EVENTOS COC ---
async def setup_coc_events():
    global coc_client, events_client
    try:
        logger.info("Iniciando configuração dos eventos CoC...")
        events_client = coc.EventsClient()
        await events_client.login(COC_EMAIL, COC_PASSWORD)
        logger.info("Login no CoC EventsClient bem-sucedido.")
        
        events_client.add_clan_updates(CLAN_TAG)

        @events_client.event
        @coc.ClanEvents.member_join()
        async def _(member, clan):
            await on_clan_member_join(member, clan)

        @events_client.event
        @coc.ClanEvents.member_leave()
        async def _(member, clan):
            await on_clan_member_leave(member, clan)

        @events_client.event
        @coc.ClanEvents.member_role()
        async def _(old_member, new_member):
            await on_clan_member_role_change(old_member, new_member)

        @events_client.event
        @coc.ClanEvents.member_trophies()
        async def _(old_member, new_member):
            await on_clan_member_trophies_change(old_member, new_member)

        @events_client.event
        @coc.ClanEvents.member_league()
        async def _(old_member, new_member):
            await on_clan_member_league_change(old_member, new_member)
            
        @events_client.event
        @coc.ClanEvents.member_donations()
        async def _(old_member, new_member):
            await on_member_donations(old_member, new_member)

        @events_client.event
        @coc.ClanEvents.member_received()
        async def _(old_member, new_member):
            await on_member_received(old_member, new_member)

        coc_client = events_client
        logger.info("Eventos de CLÃ registrados com sucesso!")

    except Exception as e:
        logger.error(f"Erro ao configurar eventos CoC: {e}", exc_info=True)
        coc_client = None

# --- ROTINAS E HANDLERS DO PAINEL WEB ---
async def get_cached_web_data(key: str, func, *args):
    now = datetime.datetime.now()
    if key in web_api_cache and (now - web_api_cache[key]["timestamp"]).total_seconds() < WEB_API_CACHE_DURATION_SECONDS:
        return web_api_cache[key]["data"]
    data = await func(*args)
    web_api_cache[key] = {"data": data, "timestamp": now}
    return data

def format_war_time_details(war_obj, time_now_tz):
    details = {"time_key": "N/A", "time_value": "N/A", "time_remaining": "N/A", "end_time_iso": None}
    if not war_obj: return details

    state = getattr(war_obj, 'state', 'unknown')
    end_time = getattr(war_obj, 'end_time', None)
    start_time = getattr(war_obj, 'start_time', None)
    
    if end_time:
        details["end_time_iso"] = end_time.time.isoformat()

    if state == 'preparation':
        details["time_key"] = "Guerra começa em"
        details["time_value"] = start_time.time.astimezone(TIMEZONE).strftime('%d/%m %H:%M') if start_time else "N/A"
        time_left = start_time.seconds_until if start_time else 0
        details["time_remaining"] = f"{time_left // 3600}h {(time_left % 3600) // 60}m"
    elif state == 'inWar':
        details["time_key"] = "Guerra termina em"
        details["time_value"] = end_time.time.astimezone(TIMEZONE).strftime('%d/%m %H:%M') if end_time else "N/A"
        time_left = end_time.seconds_until if end_time else 0
        details["time_remaining"] = f"{time_left // 3600}h {(time_left % 3600) // 60}m"
    elif state == 'warEnded':
        details["time_key"] = "Guerra terminou em"
        details["time_value"] = end_time.time.astimezone(TIMEZONE).strftime('%d/%m %H:%M') if end_time else "N/A"
        details["time_remaining"] = "Finalizada"
        
    return details

async def get_current_or_last_war(clan_tag):
    if not api_client: return None
    try:
        return await api_client.get_current_war(clan_tag)
    except (coc.PrivateWarLog, coc.NotFound):
        # Se não há guerra atual ou o log é privado, tenta o log público
        try:
            war_log = await api_client.get_war_log(clan_tag, limit=1)
            if war_log and war_log[0].end_time.seconds_since < (3600 * 48): # Se a última guerra terminou há menos de 2 dias
                # A API não permite buscar uma guerra antiga completa pelo log.
                # A melhor abordagem é construir os dados a partir do log, o que é limitado.
                # Para esta função, vamos retornar None e deixar a lógica de 'highlights' tratar isso.
                 return None
            return None
        except Exception:
            return None
    except Exception:
        return None

async def fetch_clan_info_for_web():
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        if not clan:
            return {"error": "Não foi possível carregar os dados do clã."}
        
        return {
            "name": clan.name, "tag": clan.tag, "level": clan.level, "points": clan.points,
            "capital_points": getattr(clan, 'capital_points', 'N/A'),
            "member_count": clan.member_count, "description": clan.description,
            "war_wins": getattr(clan, 'war_wins', 'N/A'),
            "location": getattr(clan.location, 'name', 'N/A') if clan.location else 'N/A',
            "type": str(clan.type).capitalize(), "badge_url": clan.badge.url, "version": BOT_VERSION,
            "capital_districts": [{"name": d.name, "level": d.hall_level} for d in getattr(clan, 'capital_districts', [])],
            "capital_league": getattr(clan.capital_league, 'name', 'N/A') if hasattr(clan, 'capital_league') else 'N/A'
        }
    except Exception as e:
        logger.error(f"Erro em fetch_clan_info_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar dados do clã."}

async def fetch_clan_members_for_web():
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        if not clan: return {"error": "Não foi possível carregar os membros do clã."}
        
        notes = await load_player_notes_from_db()
        members_data = []
        
        for m in sorted(clan.members, key=lambda x: x.trophies, reverse=True):
            if not m: continue
            note = notes.get(m.tag, {})
            members_data.append({
                "name": m.name, "tag": m.tag, "town_hall": m.town_hall,
                "league": getattr(m.league, 'name', 'Sem Liga'), "trophies": m.trophies,
                "role": str(m.role).capitalize(), "donations": m.donations, "received": m.received,
                "note": note.get("text", ""), "note_priority": note.get("priority", "none")
            })
        return {"members": members_data, "clan_name": clan.name}
    except Exception as e:
        logger.error(f"Erro em fetch_clan_members_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar lista de membros."}

async def fetch_current_war_details_for_web():
    try:
        war = await get_current_or_last_war(CLAN_TAG)
        if not war or war.state == "notInWar":
            return {"error": "Nenhuma guerra para detalhar."}
        if not war.clan or not war.opponent:
            return {"error": "Dados da guerra incompletos (clã ou oponente faltando)."}

        our_clan, opp_clan = (war.clan, war.opponent) if war.clan.tag == CLAN_TAG else (war.opponent, war.clan)
        our_clan_name = getattr(our_clan, 'name', 'Nosso Clã')
        opp_clan_name = getattr(opp_clan, 'name', 'Oponente')

        all_attacks_data = []
        for attack in war.attacks:
            if not attack: continue
            attacker = war.get_member(attack.attacker_tag)
            defender = war.get_member(attack.defender_tag)
            attacker_clan_tag_to_save = getattr(getattr(attacker, 'clan', None), 'tag', None)
            all_attacks_data.append({
                "order": attack.order,
                "attacker_clan_tag": attacker_clan_tag_to_save,
                "attacker_tag": getattr(attacker, 'tag', None),
                "attacker_name": getattr(attacker, 'name', attack.attacker_tag),
                "attacker_townhall": getattr(attacker, 'town_hall', '?'),
                "defender_name": getattr(defender, 'name', attack.defender_tag),
                "defender_townhall": getattr(defender, 'town_hall', '?'),
                "stars": attack.stars, "destruction": attack.destruction,
                "duration": f"{attack.duration}s"
            })

        def get_team_details(team):
            if not team or not hasattr(team, 'members'): return []
            details = []
            for m in team.members:
                if not m: continue
                details.append({
                    "name": m.name, "townhall": m.town_hall, "map_position": m.map_position,
                    "attacks_used": len(m.attacks),
                    "attacks_made": [{"stars": a.stars, "destruction": a.destruction, "defender_name": getattr(war.get_member(a.defender_tag), 'name', a.defender_tag), "defender_townhall": getattr(war.get_member(a.defender_tag), 'town_hall', '?')} for a in m.attacks],
                    "defenses_received": [{"stars": d.stars, "destruction": d.destruction, "attacker_name": getattr(war.get_member(d.attacker_tag), 'name', d.attacker_tag), "attacker_townhall": getattr(war.get_member(d.attacker_tag), 'town_hall', '?')} for d in m.defenses]
                })
            return sorted(details, key=lambda x: x['map_position'])

        def get_star_dist(attacks):
            dist = {i: 0 for i in range(4)}
            for a in attacks:
                if a: dist[a.stars] += 1
            return dist

        our_attacks = [a for a in war.attacks if a and getattr(getattr(a, 'attacker', None), 'clan', None) and a.attacker.clan.tag == our_clan.tag]
        opp_attacks = [a for a in war.attacks if a and getattr(getattr(a, 'attacker', None), 'clan', None) and a.attacker.clan.tag == opp_clan.tag]

        return {
            "war_data": {
                "status": str(war.state), "state_description": str(war.state).capitalize(),
                "clan_name": our_clan_name, "clan_stars": getattr(our_clan, 'stars', 0),
                "clan_destruction": f"{getattr(our_clan, 'destruction', 0.0):.2f}%",
                "clan_badge_url": getattr(our_clan.badge, 'url', None) if hasattr(our_clan, 'badge') else None,
                "clan_attacks_used": getattr(our_clan, 'attacks_used', 0),
                "opponent_name": opp_clan_name, "opponent_stars": getattr(opp_clan, 'stars', 0),
                "opponent_destruction": f"{getattr(opp_clan, 'destruction', 0.0):.2f}%",
                "opponent_badge_url": getattr(opp_clan.badge, 'url', None) if hasattr(opp_clan, 'badge') else None,
                "opponent_attacks_used": getattr(opp_clan, 'attacks_used', 0),
                **format_war_time_details(war, datetime.datetime.now(TIMEZONE)),
                "attacks_per_member": war.attacks_per_member, "team_size": war.team_size,
                "clan_star_distribution": get_star_dist(our_attacks),
                "opponent_star_distribution": get_star_dist(opp_attacks),
                "clan_avg_stars": f"{our_clan.stars / len(our_attacks):.2f}" if our_attacks else "0.00",
                "opponent_avg_stars": f"{opp_clan.stars / len(opp_attacks):.2f}" if opp_attacks else "0.00",
                "clan_avg_duration": f"{sum(a.duration for a in our_attacks) / len(our_attacks):.1f}s" if our_attacks else "0s",
                "opponent_avg_duration": f"{sum(a.duration for a in opp_attacks) / len(opp_attacks):.1f}s" if opp_attacks else "0s",
            },
            "all_attacks": all_attacks_data,
            "our_clan_members_in_war": get_team_details(our_clan),
            "opponent_clan_members_in_war": get_team_details(opp_clan)
        }
    except Exception as e:
        logger.error(f"Erro em fetch_current_war_details_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar dados da guerra."}

async def fetch_missed_attacks_history_for_web():
    if not hasattr(bot, 'db') or bot.db is None:
        return {"error": "Histórico indisponível (Banco de dados não conectado)."}
    try:
        war_collection = bot.db.war_history
        log_cursor = war_collection.find({}).sort("war_data.end_time_iso", DESCENDING)
        
        missed_attacks_history = []
        clan = await get_clan_data_with_cache(CLAN_TAG)
        if not clan:
             return {"error": "Não foi possível carregar os dados do clã para o histórico."}

        async for war_doc in log_cursor:
            war_data = war_doc.get("war_data", {})
            attacks_per_member = war_data.get("attacks_per_member", 2)
            war_date_iso = war_data.get("end_time_iso")
            
            if war_date_iso:
                try:
                    end_time_dt = datetime.datetime.fromisoformat(war_date_iso)
                    war_date_formatted = end_time_dt.astimezone(TIMEZONE).strftime('%d/%m/%y')
                except ValueError:
                    war_date_formatted = "Data inválida"
            else:
                war_date_formatted = "Data desconhecida"

            our_members_in_war = war_doc.get("our_clan_members_in_war", [])
            for member in our_members_in_war:
                attacks_made = member.get("attacks_used", 0)
                attacks_left = attacks_per_member - attacks_made
                if attacks_left > 0:
                    missed_attacks_history.append({
                        "name": member.get("name", "Nome desconhecido"),
                        "town_hall": member.get("townhall", "?"),
                        "attacks_left": attacks_left,
                        "war_date": war_date_formatted
                    })
        
        return {"missed_attacks": missed_attacks_history, "clan_name": clan.name}
    except Exception as e:
        logger.error(f"Erro em fetch_missed_attacks_history_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar histórico de ataques pendentes."}

async def fetch_war_log_for_web():
    if not hasattr(bot, 'db') or bot.db is None:
        return {"error": "Histórico indisponível (DB não conectado)."}
    try:
        war_collection = bot.db.war_history
        log_cursor = war_collection.find({}, {"war_data": 1}).sort("war_data.end_time_iso", DESCENDING).limit(9)
        entries = []
        async for war_doc in log_cursor:
            war_data = war_doc.get("war_data", {})
            end_time_dt = datetime.datetime.fromisoformat(war_data.get("end_time_iso"))
            result = "Vitória" if war_data.get("clan_stars", 0) > war_data.get("opponent_stars", 0) else \
                     "Derrota" if war_data.get("clan_stars", 0) < war_data.get("opponent_stars", 0) else "Empate"
            entries.append({
                "end_time_iso": war_data.get("end_time_iso"),
                "end_time_formatted": end_time_dt.astimezone(TIMEZONE).strftime('%d/%m/%y %H:%M'),
                "opponent_name": war_data.get("opponent_name"),
                "opponent_badge_url": war_data.get("opponent_badge_url"),
                "clan_stars": war_data.get("clan_stars"),
                "clan_destruction": war_data.get("clan_destruction"),
                "opponent_stars": war_data.get("opponent_stars"),
                "opponent_destruction": war_data.get("opponent_destruction"),
                "result": result,
                "team_size": war_data.get("team_size"),
                "is_cwl": "CWL" in war_data.get("status", "").lower()
            })
        return {"log": entries}
    except Exception as e:
        logger.error(f"Erro em fetch_war_log_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar histórico de guerras."}

async def fetch_cwl_info_for_web():
    try:
        if not api_client:
            return {"error": "CWLFeatureDisabled", "message": "API do CoC não iniciada."}
        
        cwl_war = await api_client.get_league_group(CLAN_TAG)

        if not cwl_war:
            return {"status": "NotInCwl", "message": "O clã não está em uma CWL."}

        season = cwl_war.season
        state = str(cwl_war.state).capitalize()
        clans_in_group = [{"name": c.name, "tag": c.tag, "level": c.level, "badge_url": c.badge.url} for c in cwl_war.clans]
        
        rounds_info = []
        for a_round in cwl_war.rounds:
            round_data = {"round_number": cwl_war.rounds.index(a_round) + 1, "wars": []}
            for war_tag in a_round:
                try:
                    war = await api_client.get_league_war(war_tag)
                    if war:
                        details = {
                            "war_tag": war_tag,
                            "clan_name": war.clan.name, "clan_badge_url": war.clan.badge.url,
                            "clan_stars": war.clan.stars, "clan_destruction": f"{war.clan.destruction:.2f}%",
                            "opponent_name": war.opponent.name, "opponent_badge_url": war.opponent.badge.url,
                            "opponent_stars": war.opponent.stars, "opponent_destruction": f"{war.opponent.destruction:.2f}%",
                            **format_war_time_details(war, datetime.datetime.now(TIMEZONE))
                        }
                        round_data["wars"].append(details)
                    else:
                        round_data["wars"].append({"war_tag": war_tag, "message": "Guerra não encontrada."})
                except Exception as e:
                    logger.warning(f"Não foi possível buscar a guerra da CWL {war_tag}: {e}")
                    round_data["wars"].append({"war_tag": war_tag, "error": "Erro ao buscar guerra."})
            rounds_info.append(round_data)

        return {
            "status": "InCwl", "season": season, "state": state,
            "clans_in_group": clans_in_group, "rounds": rounds_info
        }
    except coc.NotFound:
        return {"status": "NotInCwl", "message": "O clã não está em uma CWL."}
    except Exception as e:
        logger.error(f"Erro em fetch_cwl_info_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao buscar dados da CWL."}

# --- INÍCIO: Função para a aba Destaques com filtro estrito ---
async def fetch_highlights_for_web():
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        if not clan:
            return {"error": "Não foi possível carregar os dados do clã."}
        
        top_donors = sorted(clan.members, key=lambda m: m.donations, reverse=True)[:3]
        top_donors_data = [{"name": m.name, "donations": m.donations, "town_hall": m.town_hall} for m in top_donors]

        best_attacks_data = []
        our_attacks_list = []

        # Tenta pegar a guerra atual, se ela já terminou
        last_war = await get_current_or_last_war(CLAN_TAG)
        if last_war and last_war.state == 'warEnded':
            our_clan_war_object = last_war.clan if last_war.clan.tag == CLAN_TAG else last_war.opponent
            for member in our_clan_war_object.members:
                for attack in member.attacks:
                    defender = last_war.get_member(attack.defender_tag)
                    our_attacks_list.append({
                        "attacker_name": member.name,
                        "defender_name": getattr(defender, 'name', 'N/A'),
                        "defender_townhall": getattr(defender, 'town_hall', '?'),
                        "stars": attack.stars,
                        "destruction": attack.destruction,
                    })
        # Se não, busca no histórico do banco de dados a última guerra finalizada
        elif hasattr(bot, 'db') and bot.db is not None:
            latest_war_doc = await bot.db.war_history.find_one({}, sort=[("war_data.end_time_iso", DESCENDING)])
            if latest_war_doc and 'all_attacks' in latest_war_doc:
                all_attacks_from_db = latest_war_doc.get('all_attacks', [])
                # FILTRO ESTRITO: Pega apenas ataques onde a tag do clã do atacante é a do nosso clã
                our_attacks_list = [
                    atk for atk in all_attacks_from_db 
                    if atk.get("attacker_clan_tag") == CLAN_TAG
                ]

        if our_attacks_list:
            sorted_attacks = sorted(
                our_attacks_list, 
                key=lambda a: (a.get('stars', 0), float(str(a.get('destruction', '0')).replace('%',''))),
                reverse=True
            )
            best_attacks_data = sorted_attacks[:3]

        active_members = sorted(clan.members, key=lambda m: m.donations, reverse=True)[:10]
        chart_data = {
            "labels": [m.name for m in active_members],
            "donations": [m.donations for m in active_members],
            "received": [m.received for m in active_members]
        }

        return {
            "top_donors": top_donors_data,
            "best_attacks": best_attacks_data,
            "activity_chart_data": chart_data,
            "clan_name": clan.name
        }

    except Exception as e:
        logger.error(f"Erro em fetch_highlights_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar destaques."}
# --- FIM: Função para a aba Destaques ---


async def api_clan_info_handler(request):
    data = await get_cached_web_data('clan_info', fetch_clan_info_for_web)
    return web.json_response(data)

async def api_members_handler(request):
    data = await get_cached_web_data('members', fetch_clan_members_for_web)
    return web.json_response(data)

async def api_current_war_details_handler(request):
    data = await get_cached_web_data('current_war_details', fetch_current_war_details_for_web)
    return web.json_response(data)

async def api_missed_attacks_history_handler(request):
    data = await get_cached_web_data('missed_attacks_history', fetch_missed_attacks_history_for_web)
    return web.json_response(data)

async def api_war_log_handler(request):
    data = await get_cached_web_data('war_log', fetch_war_log_for_web)
    return web.json_response(data)

async def api_cwl_info_handler(request):
    data = await get_cached_web_data('cwl_info', fetch_cwl_info_for_web)
    return web.json_response(data)

async def api_highlights_handler(request):
    data = await get_cached_web_data('highlights', fetch_highlights_for_web)
    return web.json_response(data)

async def api_save_player_note_handler(request):
    player_tag_encoded = request.match_info['player_tag']
    try:
        player_tag = coc.utils.correct_tag(player_tag_encoded)
        data = await request.json()
        note_text = data.get('text', '')
        priority = data.get('priority', 'none')
        await save_player_note_to_db(player_tag, note_text, priority)
        web_api_cache.pop('members', None)
        return web.Response(status=204)
    except Exception as e:
        logger.error(f"Erro ao salvar nota via API para {player_tag_encoded}: {e}", exc_info=True)
        return web.json_response({"error": "Erro ao salvar a nota."}, status=500)


async def api_historic_war_handler(request):
    war_id = request.match_info['war_id']
    if not hasattr(bot, 'db') or bot.db is None:
        return web.json_response({"error": "Banco de dados não conectado."}, status=503)
    try:
        war_doc = await bot.db.war_history.find_one({"_id": war_id})
        if war_doc:
            return web.json_response(war_doc)
        else:
            return web.json_response({"error": "Guerra não encontrada no histórico."}, status=404)
    except Exception as e:
        logger.error(f"Erro ao buscar guerra histórica {war_id}: {e}", exc_info=True)
        return web.json_response({"error": "Erro interno no servidor."}, status=500)

# --- TAREFAS EM BACKGROUND ---
@tasks.loop(seconds=60.0)
async def check_war_end_task():
    global last_war_end_time
    await bot.wait_until_ready()
    if not api_client: return

    try:
        war = await api_client.get_current_war(CLAN_TAG)
        if war and war.state == 'warEnded' and hasattr(war, 'end_time'):
            current_end_time = war.end_time.time
            if last_war_end_time is None or current_end_time > last_war_end_time:
                logger.info(f"Nova guerra finalizada detectada: {war.clan.name} vs {war.opponent.name}.")
                last_war_end_time = current_end_time

                our_clan = war.clan if war.clan.tag == CLAN_TAG else war.opponent
                missed_attacks_members = []
                for member in our_clan.members:
                    attacks_left = war.attacks_per_member - len(member.attacks)
                    if attacks_left > 0:
                        missed_attacks_members.append(f"**{member.name}** (CV{member.town_hall}): {attacks_left} ataque(s) perdido(s)")

                if missed_attacks_members:
                    logger.info("Gerando relatório de ataques perdidos.")
                    war_type = "Guerra Normal" if not war.is_cwl else "CWL"
                    report_embed = discord.Embed(
                        title=f"🚩 Relatório de Ataques Perdidos - {war_type}",
                        description=f"Guerra entre **{war.clan.name}** vs **{war.opponent.name}** finalizada.",
                        color=discord.Color.dark_gold()
                    )
                    report_embed.add_field(
                        name="Placar Final",
                        value=f"**{war.clan.name}:** {war.clan.stars}⭐ ({war.clan.destruction:.2f}%)\n"
                              f"**{war.opponent.name}:** {war.opponent.stars}⭐ ({war.opponent.destruction:.2f}%)",
                        inline=False
                    )
                    report_embed.add_field(
                        name="Detalhes dos Ataques Perdidos",
                        value="\n".join(missed_attacks_members),
                        inline=False
                    )
                    if hasattr(war.opponent.badge, 'url'):
                        report_embed.set_thumbnail(url=war.opponent.badge.url)

                    role_mention = ""
                    if ROLE_ID_MISSED_ATTACK:
                        role_mention = f"<@&{ROLE_ID_MISSED_ATTACK}>"
                    await send_log_embed(report_embed, content=f"{role_mention} Atenção aos ataques perdidos!")

                war_details = await fetch_current_war_details_for_web()
                if 'error' not in war_details:
                    await save_war_to_history(war_details)
                else:
                    logger.error(f"Não foi possível obter detalhes da guerra finalizada para salvar: {war_details.get('error')}")

    except (coc.PrivateWarLog, coc.NotFound):
        pass
    except Exception as e:
        logger.error(f"Erro na task de verificação de fim de guerra: {e}", exc_info=True)

@tasks.loop(seconds=30)
async def check_new_attack_task():
    global war_attack_cache
    await bot.wait_until_ready()
    if not api_client: return

    try:
        war = await api_client.get_current_war(CLAN_TAG)
        if not war or war.state != 'inWar':
            if war_attack_cache["war_end_time"] is not None:
                logger.info("Guerra não está ativa. Limpando cache de ataques.")
                war_attack_cache = {"war_end_time": None, "processed_attacks": set()}
            return

        current_war_end_time = war.end_time.time
        if war_attack_cache["war_end_time"] != current_war_end_time:
            logger.info(f"Nova guerra detectada (fim em {current_war_end_time}). Resetando cache de ataques.")
            war_attack_cache["war_end_time"] = current_war_end_time
            war_attack_cache["processed_attacks"] = {attack.order for attack in war.attacks}
            return

        current_attack_orders = {attack.order for attack in war.attacks}
        new_attack_orders = current_attack_orders - war_attack_cache["processed_attacks"]

        if new_attack_orders:
            logger.info(f"Detectados {len(new_attack_orders)} novo(s) ataque(s).")
            for attack in sorted(war.attacks, key=lambda a: a.order):
                if attack.order in new_attack_orders:
                    await on_war_attack(attack, war)
                    war_attack_cache["processed_attacks"].add(attack.order)

    except (coc.PrivateWarLog, coc.NotFound):
        pass
    except Exception as e:
        logger.error(f"Erro na task de verificação de novos ataques: {e}", exc_info=True)

@tasks.loop(seconds=10, count=1)
async def send_online_status_task():
    await bot.wait_until_ready()
    while not api_client:
        await asyncio.sleep(5)
        logger.info("Aguardando inicialização do api_client para enviar status online...")

    try:
        clan = await api_client.get_clan(CLAN_TAG)
        embed = discord.Embed(title=f"✅ ClashGenius Online | {clan.name}",
                              description=f"Monitoramento ativado para **{clan.name} ({clan.tag})**.",
                              color=discord.Color.green())
        embed.add_field(name="📊 Status do Clã",
                        value=f"**Membros:** {clan.member_count}/50\n**Troféus:** 🏆 {clan.points}", inline=True)
        embed.add_field(name="⚙️ Status do Bot", value=f"**Versão:** {BOT_VERSION}\n**API CoC:** ✅ OK", inline=True)
        if clan.badge:
            embed.set_thumbnail(url=clan.badge.url)
        await send_log_embed(embed)
        logger.info("Notificação de status online enviada com sucesso.")
    except Exception as e:
        logger.error(f"Falha ao enviar notificação de status online: {e}", exc_info=True)
        embed = discord.Embed(title="❌ ClashGenius com Erro na Inicialização",
                              description="Não foi possível obter dados do clã para a notificação de status. Verifique as permissões e a API do CoC.",
                              color=discord.Color.red())
        await send_log_embed(embed)

async def setup_web_server():
    app = web.Application()
    app.router.add_get("/api/clan", api_clan_info_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/current_war_details", api_current_war_details_handler)
    app.router.add_get("/api/missed_attacks_history", api_missed_attacks_history_handler)
    app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler)
    app.router.add_get("/api/highlights", api_highlights_handler)
    app.router.add_post("/api/notes/{player_tag:.*}", api_save_player_note_handler)
    app.router.add_get("/api/war_history/{war_id}", api_historic_war_handler)
    app.router.add_get("/api/status", lambda r: web.json_response({"status": "online", "version": BOT_VERSION}))
    
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.router.add_static('/static/', path=static_dir, name='static')
    app.router.add_get("/painel", lambda r: web.FileResponse(os.path.join(static_dir, "painel.html")))
    app.router.add_get("/", lambda r: web.Response(text=f"Bot running! v{BOT_VERSION}"))
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Servidor web iniciado em http://0.0.0.0:{port}")

# --- EVENTOS DO BOT DISCORD ---
@bot.event
async def on_ready():
    logger.info(f'Bot {bot.user} está online e pronto!')
    
    try:
        if MONGO_DB_URL:
            logger.info("Conectando ao MongoDB...")
            parsed_uri = parse_uri(MONGO_DB_URL)
            db_name = parsed_uri.get('database', 'clash_data')
            bot.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)
            bot.db = bot.mongo_client[db_name]
            logger.info(f"Conectado ao MongoDB, usando banco de dados: {db_name}")
        else:
            bot.db = None
            logger.warning("URL do MongoDB não fornecida. Recursos de persistência desativados.")
    except Exception as e:
        logger.error(f"Falha ao conectar com o MongoDB: {e}", exc_info=True)
        bot.db = None

    if not check_war_end_task.is_running():
        check_war_end_task.start()
    if not check_new_attack_task.is_running():
        check_new_attack_task.start()
    if not send_online_status_task.is_running():
        send_online_status_task.start()

# --- COMANDOS DO BOT ---
@bot.command()
async def ping(ctx):
    await ctx.send(f'Pong! Latência: {round(bot.latency * 1000)}ms')

# --- FUNÇÃO PRINCIPAL ---
async def main():
    global api_client
    try:
        api_client = coc.Client()
        await api_client.login(COC_EMAIL, COC_PASSWORD)
        logger.info("Login no coc.Client (api_client) bem-sucedido.")
    except Exception as e:
        logger.critical(f"Erro crítico ao fazer login no api_client: {e}", exc_info=True)

    try:
        await setup_coc_events()
        await setup_web_server()
        await bot.start(DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"Erro crítico na inicialização do bot: {e}", exc_info=True)
    finally:
        if events_client:
            await events_client.close()
        if api_client:
            await api_client.close()
        if hasattr(bot, 'mongo_client'):
            bot.mongo_client.close()
        await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot desligado manualmente.")

