# -*- coding: utf-8 -*-
# Versão 20.1.16-FINAL-STABLE - Adicionado monitoramento de doações e tropas recebidas.

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
# <-- USANDO AS VARIÁVEIS EXISTENTES -- >
ROLE_ID_1STAR_ALERT = int(os.getenv("ROLE_ID_1STAR_ALERT", 0)) 
ROLE_ID_MISSED_ATTACK = int(os.getenv("ROLE_ID_MISSED_ATTACK", 0))

# --- Constantes e Configurações Globais ---
BOT_VERSION = "20.1.22-REPORTS-FIX"
TIMEZONE = pytz.timezone('America/Sao_Paulo')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# --- Inicialização dos Clientes ---
bot = commands.Bot(command_prefix="!", intents=intents)
coc_client: Optional[coc.Client] = None
events_client: Optional[coc.EventsClient] = None

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
        await bot.db.player_notes.update_one(
            {"_id": player_tag},
            {"$set": {"text": text, "priority": priority}},
            upsert=True
        )
        logger.info(f"Nota salva no MongoDB para {player_tag}.")
    except Exception as e:
        logger.error(f"Erro ao salvar nota no MongoDB para {player_tag}: {e}", exc_info=True)
        raise

async def save_war_to_history(war_data: Dict[str, Any]):
    """Salva os dados completos de uma guerra na coleção de histórico."""
    if not hasattr(bot, 'db') or bot.db is None:
        logger.error("Banco de dados não disponível, não é possível salvar o histórico da guerra.")
        return
    try:
        war_collection = bot.db.war_history
        # Usar end_time como _id para garantir unicidade
        war_data['_id'] = war_data['war_data']['end_time_iso']
        
        await war_collection.replace_one({'_id': war_data['_id']}, war_data, upsert=True)
        logger.info(f"Guerra finalizada em {war_data['_id']} salva no histórico.")

        # Lógica para manter apenas as últimas 9 guerras
        count = await war_collection.count_documents({})
        if count > 9:
            # Encontra a guerra mais antiga (menor end_time) e a remove
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
    if not coc_client: return None
    normalized_tag = coc.utils.correct_tag(tag)
    if normalized_tag in player_short_term_cache:
        return player_short_term_cache[normalized_tag]
    try:
        player = await coc_client.get_player(normalized_tag)
        player_short_term_cache[normalized_tag] = player
        return player
    except Exception:
        return None

async def get_clan_data_with_cache(tag: str) -> Optional[coc.Clan]:
    if not coc_client: return None
    normalized_tag = coc.utils.correct_tag(tag)
    now = datetime.datetime.now()
    if normalized_tag in clan_cache and (now - clan_cache[normalized_tag]["timestamp"]).total_seconds() < CACHE_DURATION_SECONDS:
        return clan_cache[normalized_tag]["data"]
    try:
        clan_data = await coc_client.get_clan(normalized_tag)
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
        is_our_attack = hasattr(attack.attacker, 'clan') and attack.attacker.clan and attack.attacker.clan.tag == CLAN_TAG
        if not is_our_attack: return
        
        logger.info(f"Ataque de {attack.attacker.name} processado pela task.")
        war_type = "CWL" if war.is_cwl else "Guerra"
        our_clan = war.clan if war.clan.tag == CLAN_TAG else war.opponent
        opponent_clan = war.opponent if war.clan.tag == CLAN_TAG else war.clan
        
        # Envia a notificação normal de ataque
        embed = discord.Embed(title=f"⚔️ Ataque na {war_type}!", color=discord.Color.orange())
        stars = "⭐" * attack.stars + "⚫" * (3 - attack.stars)
        embed.description = (
            f"**{attack.attacker.name}** atacou **{attack.defender.name}**\n"
            f"`CV{attack.attacker.town_hall} vs CV{attack.defender.town_hall}`"
        )
        embed.add_field(name="Resultado do Ataque", value=f"{stars} **{attack.destruction}%**", inline=False)
        embed.add_field(name="Placar Atual", value=f"**{our_clan.name}:** {our_clan.stars}⭐\n**{opponent_clan.name}:** {opponent_clan.stars}⭐", inline=True)
        embed.add_field(name="Ataques Usados", value=f"{our_clan.attacks_used} / {war.team_size * war.attacks_per_member}", inline=True)
        await send_log_embed(embed)

        # Alerta de ataque fora do padrão
        if attack.stars <= 1:
            logger.info(f"Ataque fora do padrão detectado por {attack.attacker.name}.")
            alert_embed = discord.Embed(
                title=f"⚠️ Ataque fora do padrão!",
                description=f"**{our_clan.name}**\n⚔️ **Ataque Realizado ({war_type})**",
                color=discord.Color.red()
            )
            alert_embed.add_field(
                name="Detalhes",
                value=f"{attack.attacker.name} (CV{attack.attacker.town_hall}) atacou {attack.defender.name} (CV{attack.defender.town_hall})",
                inline=False
            )
            alert_embed.add_field(
                name="Resultado",
                value=f"{'⚫⚫⚫' if attack.stars == 0 else '⭐⚫⚫'} ({attack.destruction}%)",
                inline=False
            )
            if hasattr(opponent_clan.badge, 'url'):
                alert_embed.set_thumbnail(url=opponent_clan.badge.url)
            
            role_mention = ""
            if ROLE_ID_1STAR_ALERT: # <-- USANDO A VARIÁVEL CORRETA
                role_mention = f"<@&{ROLE_ID_1STAR_ALERT}>"
            else:
                logger.warning("ROLE_ID_1STAR_ALERT não configurado. Não foi possível marcar o cargo.")
            
            await send_log_embed(alert_embed, content=f"{role_mention} Atenção ao ataque fora do padrão!")

    except Exception as e:
        logger.error(f"Erro no evento war_attack: {e}", exc_info=True)

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
    if end_time and hasattr(end_time, 'time'):
        details["end_time_iso"] = end_time.time.isoformat()

    if state == "preparation" and hasattr(war_obj, 'start_time') and war_obj.start_time:
        start_aware = war_obj.start_time.time.astimezone(TIMEZONE)
        details.update({"time_key": "Início", "time_value": start_aware.strftime('%d/%m/%y %H:%M')})
        delta = start_aware - time_now_tz
        if delta.total_seconds() > 0:
            h, rem = divmod(delta.seconds, 3600)
            m, _ = divmod(rem, 60)
            details["time_remaining"] = f"{delta.days}d {h}h {m}m" if delta.days > 0 else f"{h}h {m}m"
        else:
            details["time_remaining"] = "Iniciando..."
    elif state in ["inWar", "warEnded"] and hasattr(war_obj, 'end_time') and war_obj.end_time:
        end_aware = war_obj.end_time.time.astimezone(TIMEZONE)
        details.update({"time_key": "Fim" if state == "inWar" else "Finalizada em", "time_value": end_aware.strftime('%d/%m/%y %H:%M')})
        if state == "inWar":
            delta = end_aware - time_now_tz
            if delta.total_seconds() > 0:
                h, rem = divmod(delta.seconds, 3600)
                m, _ = divmod(rem, 60)
                details["time_remaining"] = f"{delta.days}d {h}h {m}m" if delta.days > 0 else f"{h}h {m}m"
            else:
                details["time_remaining"] = "Finalizando..."
    return details

async def get_current_or_last_war(clan_tag_param: str) -> Optional[coc.ClanWar]:
    if not coc_client: return None
    current_war_in_war: Optional[coc.ClanWar] = None
    current_war_preparation: Optional[coc.ClanWar] = None
    best_ended_cwl_war: Optional[coc.ClanWar] = None
    try:
        league_group = await coc_client.get_league_group(clan_tag_param)
        if league_group and getattr(league_group, 'state', None) != "notInWar" and hasattr(league_group, 'rounds'):
            all_round_war_tags = [tag for round_tags in league_group.rounds for tag in round_tags if tag != "#0"]
            for war_tag_str in reversed(all_round_war_tags):
                try:
                    lg_war = await coc_client.get_league_war(war_tag_str)
                    if lg_war and (lg_war.clan.tag == clan_tag_param or lg_war.opponent.tag == clan_tag_param):
                        if lg_war.state == "inWar":
                            current_war_in_war = lg_war
                            return current_war_in_war
                        elif lg_war.state == "preparation" and not current_war_preparation:
                            current_war_preparation = lg_war
                        elif lg_war.state == "warEnded":
                            if not best_ended_cwl_war or (hasattr(lg_war, 'end_time') and hasattr(best_ended_cwl_war, 'end_time') and lg_war.end_time.time > best_ended_cwl_war.end_time.time):
                                best_ended_cwl_war = lg_war
                except (coc.NotFound, AttributeError):
                    continue
            if current_war_preparation:
                return current_war_preparation
            if best_ended_cwl_war:
                return best_ended_cwl_war
    except coc.NotFound:
        pass
    except Exception as e:
        logger.error(f"Erro ao buscar dados da CWL: {e}", exc_info=True)
    try:
        regular_war = await coc_client.get_current_war(clan_tag_param)
        if regular_war and regular_war.state != "notInWar":
            return regular_war
    except (coc.PrivateWarLog, coc.NotFound):
        pass
    except Exception as e:
        logger.error(f"Erro ao buscar guerra regular: {e}", exc_info=True)
    return None

async def fetch_clan_info_for_web():
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        if not clan:
            return {"error": "Não foi possível carregar os dados do clã."}
        return {
            "name": clan.name, "tag": clan.tag, "level": clan.level, "points": clan.points,
            "capital_points": getattr(clan, 'capital_points', 'N/A'), "member_count": clan.member_count,
            "description": clan.description, "war_wins": getattr(clan, 'war_wins', 'N/A'),
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
        if not clan:
            return {"error": "Não foi possível carregar os membros do clã."}
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
            all_attacks_data.append({
                "order": attack.order, "attacker_name": getattr(attacker, 'name', attack.attacker_tag),
                "attacker_townhall": getattr(attacker, 'town_hall', '?'),
                "defender_name": getattr(defender, 'name', attack.defender_tag),
                "defender_townhall": getattr(defender, 'town_hall', '?'), "stars": attack.stars,
                "destruction": attack.destruction, "duration": f"{attack.duration}s"
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
                "clan_attacks_used": getattr(our_clan, 'attacks_used', 0), "opponent_name": opp_clan_name,
                "opponent_stars": getattr(opp_clan, 'stars', 0),
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

async def fetch_war_attacks_remaining_for_web():
    try:
        war = await get_current_or_last_war(CLAN_TAG)
        if not war or war.state not in ["inWar", "preparation"]:
            return {"message": "Não há guerra em andamento ou preparação."}
        our_clan = war.clan if war.clan.tag == CLAN_TAG else war.opponent
        pending = [{"name": m.name, "town_hall": m.town_hall, "attacks_left": war.attacks_per_member - len(m.attacks)}
                   for m in sorted(our_clan.members, key=lambda x: x.map_position)
                   if war.attacks_per_member - len(m.attacks) > 0]
        return {"members_pending": pending, "clan_name": our_clan.name}
    except Exception as e:
        logger.error(f"Erro em fetch_war_attacks_remaining_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar ataques pendentes."}

async def fetch_war_log_for_web():
    """Busca o histórico de guerras do MongoDB."""
    if not hasattr(bot, 'db') or bot.db is None:
        return {"error": "Histórico indisponível (DB não conectado)."}
    try:
        war_collection = bot.db.war_history
        # Busca as 9 guerras mais recentes, ordenadas pela data de término
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
        if not coc_client: return {"error": "Cliente CoC não inicializado."}
        lg = await coc_client.get_league_group(CLAN_TAG)
        if lg.state == "notInWar":
            return {"status": "NotInCwl", "message": "Clã não está em CWL."}
        
        rounds_data = []
        for i, round_tags in enumerate(lg.rounds):
            r_info = {"round_number": i + 1, "wars": []}
            for war_tag in round_tags:
                if war_tag == "#0":
                    r_info["wars"].append({"message": "Rodada de descanso."})
                    continue
                try:
                    war = await coc_client.get_league_war(war_tag)
                    if not war: continue
                    our_clan, opp_clan = (war.clan, war.opponent) if war.clan.tag == CLAN_TAG else (war.opponent, war.clan)
                    r_info["wars"].append({
                        "state": str(war.state), "clan_name": our_clan.name, "clan_stars": our_clan.stars,
                        "clan_destruction": f"{our_clan.destruction:.2f}%", "clan_badge_url": our_clan.badge.url,
                        "opponent_name": opp_clan.name, "opponent_stars": opp_clan.stars,
                        "opponent_destruction": f"{opp_clan.destruction:.2f}%", "opponent_badge_url": opp_clan.badge.url,
                        **format_war_time_details(war, datetime.datetime.now(TIMEZONE))
                    })
                except Exception as e:
                    r_info["wars"].append({"error": f"Erro ao carregar guerra {war_tag}: {e}"})
            rounds_data.append(r_info)
        
        return {
            "status": "InCwl", "state": str(lg.state), "season": lg.season,
            "clans_in_group": [{"name": c.name, "tag": c.tag, "level": c.level, "badge_url": c.badge.url} for c in lg.clans],
            "rounds": rounds_data
        }
    except coc.NotFound:
        return {"status": "NotInCwl", "message": "Grupo CWL não encontrado."}
    except Exception as e:
        logger.error(f"Erro em fetch_cwl_info_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar dados da CWL."}

# --- Handlers da API ---
async def api_clan_info_handler(request):
    return web.json_response(await get_cached_web_data("web_clan_info", fetch_clan_info_for_web))

async def api_members_handler(request):
    return web.json_response(await get_cached_web_data("web_clan_members", fetch_clan_members_for_web))

async def api_current_war_details_handler(request):
    return web.json_response(await get_cached_web_data("web_current_war_details", fetch_current_war_details_for_web))

async def api_war_attacks_remaining_handler(request):
    return web.json_response(await get_cached_web_data("web_war_attacks_remaining", fetch_war_attacks_remaining_for_web))

async def api_war_log_handler(request):
    return web.json_response(await get_cached_web_data("web_war_log", fetch_war_log_for_web))

async def api_historic_war_handler(request):
    """Busca os dados completos de uma guerra específica do histórico."""
    war_id = request.match_info.get('war_id')
    if not war_id or not hasattr(bot, 'db') or bot.db is None:
        return web.json_response({"error": "ID da guerra inválido ou DB não conectado."}, status=400)
    try:
        war_collection = bot.db.war_history
        war_data = await war_collection.find_one({"_id": war_id})
        if war_data:
            return web.json_response(war_data)
        else:
            return web.json_response({"error": "Guerra não encontrada no histórico."}, status=404)
    except Exception as e:
        logger.error(f"Erro ao buscar guerra histórica {war_id}: {e}", exc_info=True)
        return web.json_response({"error": "Erro interno ao buscar guerra histórica."}, status=500)


async def api_cwl_info_handler(request):
    return web.json_response(await get_cached_web_data("web_cwl_info", fetch_cwl_info_for_web))

async def api_save_player_note_handler(request):
    player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
    try:
        data = await request.json()
        await save_player_note_to_db(player_tag, data.get("text", ""), data.get("priority", "none"))
        if "web_clan_members" in web_api_cache:
            del web_api_cache["web_clan_members"]
        return web.json_response({"message": "Nota salva com sucesso."})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

@tasks.loop(minutes=5)
async def check_war_end_task():
    """Verifica se uma guerra terminou para salvar no histórico e enviar relatórios."""
    global last_war_end_time
    await bot.wait_until_ready()
    if not coc_client:
        return

    try:
        war = await coc_client.get_current_war(CLAN_TAG)
        if war and war.state == 'warEnded' and hasattr(war, 'end_time'):
            current_end_time = war.end_time.time
            if last_war_end_time is None or current_end_time > last_war_end_time:
                logger.info(f"Nova guerra finalizada detectada: {war.clan.name} vs {war.opponent.name}.")
                last_war_end_time = current_end_time

                # Relatório de ataques perdidos
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
                    if ROLE_ID_MISSED_ATTACK: # <-- USANDO A VARIÁVEL CORRETA
                        role_mention = f"<@&{ROLE_ID_MISSED_ATTACK}>"
                    
                    await send_log_embed(report_embed, content=f"{role_mention} Atenção aos ataques perdidos!")

                # Salva no histórico do painel
                war_details = await fetch_current_war_details_for_web()
                if 'error' not in war_details:
                    await save_war_to_history(war_details)
                else:
                    logger.error(f"Não foi possível obter detalhes da guerra finalizada para salvar: {war_details.get('error')}")

    except coc.PrivateWarLog:
        pass
    except Exception as e:
        logger.error(f"Erro na task de verificação de fim de guerra: {e}", exc_info=True)

@tasks.loop(seconds=30)
async def check_new_attack_task():
    """Verifica periodicamente por novos ataques na guerra, contornando o bug dos eventos."""
    global war_attack_cache
    await bot.wait_until_ready()
    if not coc_client:
        return

    try:
        war = await coc_client.get_current_war(CLAN_TAG)
        
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

    except coc.PrivateWarLog:
        pass
    except Exception as e:
        logger.error(f"Erro na task de verificação de novos ataques: {e}", exc_info=True)


async def setup_web_server():
    app = web.Application()
    app.router.add_get("/api/clan", api_clan_info_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/current_war_details", api_current_war_details_handler)
    app.router.add_get("/api/war_attacks_remaining", api_war_attacks_remaining_handler)
    app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler)
    app.router.add_post("/api/notes/{player_tag}", api_save_player_note_handler)
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
    logger.info(f"Servidor web iniciado na porta {port}")
    return runner

# --- EVENTO ON_READY E MAIN ---
@bot.event
async def on_ready():
    logger.info(f"Bot {bot.user.name} online! Versão: {BOT_VERSION}")
    try:
        await setup_coc_events()
        
        if not check_war_end_task.is_running():
            check_war_end_task.start()
        if not check_new_attack_task.is_running():
            check_new_attack_task.start()
            
        if coc_client:
            clan = await coc_client.get_clan(CLAN_TAG)
            embed = discord.Embed(title=f"✅ ClashGenius Online | {clan.name}",
                                  description=f"Monitoramento ativado para **{clan.name} ({clan.tag})**.",
                                  color=discord.Color.green())
            embed.add_field(name="📊 Status do Clã",
                            value=f"**Membros:** {clan.member_count}/50\n**Troféus:** 🏆 {clan.points}", inline=True)
            embed.add_field(name="⚙️ Status do Bot", value=f"**Versão:** {BOT_VERSION}\n**API CoC:** ✅ OK", inline=True)
            if clan.badge:
                embed.set_thumbnail(url=clan.badge.url)
            await send_log_embed(embed)
        else:
            logger.error("Cliente CoC não inicializado. Não foi possível enviar o status online.")
            embed = discord.Embed(title="❌ ClashGenius com Erro na Inicialização",
                                  description="Não foi possível conectar à API do Clash of Clans. Verifique as credenciais e reinicie.",
                                  color=discord.Color.red())
            await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no on_ready: {e}", exc_info=True)

async def main():
    global coc_client
    try:
        if MONGO_DB_URL:
            try:
                bot.db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)
                db_name = parse_uri(MONGO_DB_URL).get('database')
                bot.db = bot.db_client[db_name or 'clash_genius_db']
                await bot.db.command('ping')
                logger.info(f"Conectado ao MongoDB: {bot.db.name}")
            except Exception as e:
                logger.error(f"Falha ao conectar ao MongoDB: {e}", exc_info=True)
                bot.db = None
        else:
            logger.warning("MONGO_DB_URL não definida. As notas não serão salvas em banco de dados.")
            bot.db = None
        
        web_runner = await setup_web_server()
        await bot.start(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Erro na função main: {e}", exc_info=True)
    finally:
        if 'web_runner' in locals() and web_runner:
            await web_runner.cleanup()
        if coc_client:
            await coc_client.close()
        if events_client:
            await events_client.close()
        if hasattr(bot, 'db_client'):
            bot.db_client.close()

if __name__ == "__main__":
    if not all([DISCORD_TOKEN, COC_EMAIL, COC_PASSWORD, CLAN_TAG]):
        logger.critical("Variáveis de ambiente essenciais faltando.")
    else:
        asyncio.run(main())
