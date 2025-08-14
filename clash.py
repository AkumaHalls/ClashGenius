# -*- coding: utf-8 -*-
# Versão 20.1.4-FIXED - Lógica do painel web e integração com MongoDB restauradas.

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
import coc
import pytz
from dotenv import load_dotenv
import motor.motor_asyncio

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

# --- Constantes e Configurações Globais ---
BOT_VERSION = "20.1.4-FIXED"
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

# --- FUNÇÕES DE BANCO DE DADOS (MongoDB) ---
async def load_player_notes_from_db() -> Dict[str, Dict[str, str]]:
    """Carrega todas as notas de jogadores do MongoDB."""
    if not hasattr(bot, 'db') or not bot.db:
        logger.warning("Banco de dados não disponível, não é possível carregar as notas.")
        return {}
    try:
        notes_cursor = bot.db.player_notes.find({})
        notes_from_db = {}
        async for note_doc in notes_cursor:
            # Schema esperado: {_id: player_tag, text: "...", priority: "..."}
            if "_id" in note_doc:
                notes_from_db[note_doc["_id"]] = {
                    "text": note_doc.get("text", ""),
                    "priority": note_doc.get("priority", "none")
                }
        logger.info(f"Carregadas {len(notes_from_db)} notas do MongoDB.")
        return notes_from_db
    except Exception as e:
        logger.error(f"Erro ao carregar notas do MongoDB: {e}", exc_info=True)
        return {}

async def save_player_note_to_db(player_tag: str, text: str, priority: str):
    """Salva ou atualiza a nota de um jogador no MongoDB."""
    if not hasattr(bot, 'db') or not bot.db:
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

# --- FUNÇÕES AUXILIARES (HELPERS) ---
async def send_log_embed(embed_to_log: discord.Embed, content: str = None) -> None:
    if not CHANNEL_ID:
        logger.warning("CHANNEL_ID não configurado. Não é possível enviar o embed.")
        return
    
    if not bot.is_ready():
        logger.warning("O Bot não está pronto. A aguardar antes de enviar o embed.")
        await bot.wait_until_ready()

    try:
        channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
        if not embed_to_log.footer:
            embed_to_log.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
        if not embed_to_log.timestamp:
            embed_to_log.timestamp = datetime.datetime.now(TIMEZONE)
        
        await channel.send(content=content, embed=embed_to_log)
        logger.info(f"Embed enviado com sucesso: {embed_to_log.title}")
    except (discord.NotFound, discord.Forbidden) as e:
        logger.error(f"Não foi possível enviar mensagem para o canal {CHANNEL_ID}: {e}")
    except Exception as e:
        logger.error(f"Erro inesperado ao enviar embed: {e}", exc_info=True)

# --- FUNÇÕES DE BUSCA DE DADOS (API CoC) ---
async def get_player_data(tag: str) -> Any:
    global coc_client
    if not coc_client:
        logger.error("coc_client não inicializado")
        return None
        
    normalized_tag = coc.utils.correct_tag(tag)
    if normalized_tag in player_short_term_cache:
        return player_short_term_cache[normalized_tag]
    
    try:
        player = await coc_client.get_player(normalized_tag)
        player_short_term_cache[normalized_tag] = player
        return player
    except Exception as e:
        logger.error(f"Erro ao buscar dados do jogador {tag}: {e}")
        return None

async def get_clan_data_with_cache(tag: str) -> Any:
    global coc_client
    if not coc_client:
        logger.error("coc_client não inicializado")
        return None
        
    normalized_tag = coc.utils.correct_tag(tag)
    now = datetime.datetime.now()
    
    if normalized_tag in clan_cache:
        cache_entry = clan_cache[normalized_tag]
        if "timestamp" in cache_entry and isinstance(cache_entry["timestamp"], datetime.datetime):
            if (now - cache_entry["timestamp"]).total_seconds() < CACHE_DURATION_SECONDS:
                return cache_entry["data"]
    
    try:
        clan_data = await coc_client.get_clan(normalized_tag)
        clan_cache[normalized_tag] = {"data": clan_data, "timestamp": now}
        return clan_data
    except Exception as e:
        logger.error(f"Erro ao buscar dados do clã {tag}: {e}")
        return None

# --- DEFINIÇÃO DOS EVENTOS DO COC (Versão Nova) ---
async def on_clan_member_join(member, clan):
    try:
        logger.info(f"Evento disparado: {member.name} entrou no clã {clan.name}")
        if clan.tag != CLAN_TAG: 
            return
            
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
        if clan.tag != CLAN_TAG: 
            return
            
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
        logger.info(f"Evento disparado: Ataque de {attack.attacker.name}")
        if not (attack.attacker.clan and attack.attacker.clan.tag == CLAN_TAG):
            return
        
        war_type = "CWL" if war.is_cwl else "Guerra"
        embed = discord.Embed(title=f"⚔️ Ataque na {war_type}!", color=discord.Color.orange())
        stars = "⭐" * attack.stars + "⚫" * (3 - attack.stars)
        our_clan = war.clan if war.clan.tag == CLAN_TAG else war.opponent
        opponent_clan = war.opponent if war.clan.tag == CLAN_TAG else war.clan

        embed.description = (
            f"**{attack.attacker.name}** atacou **{attack.defender.name}**\n"
            f"`CV{attack.attacker.town_hall} vs CV{attack.defender.town_hall}`"
        )
        embed.add_field(name="Resultado do Ataque", value=f"{stars} **{attack.destruction}%**", inline=False)
        embed.add_field(name="Placar Atual", value=f"**{our_clan.name}:** {our_clan.stars}⭐\n**{opponent_clan.name}:** {opponent_clan.stars}⭐", inline=True)
        embed.add_field(name="Ataques Usados", value=f"{our_clan.attacks_used} / {war.team_size * war.attacks_per_member}", inline=True)
        await send_log_embed(embed)
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
        if diff == 0:
            return
            
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

# --- CONFIGURAÇÃO DOS EVENTOS COC ---
async def setup_coc_events():
    global coc_client, events_client
    
    try:
        logger.info("Iniciando configuração dos eventos CoC...")
        
        if coc_client and hasattr(coc_client, '_session') and coc_client._session and not coc_client._session.closed:
            await coc_client.close()
        
        events_client = coc.EventsClient()
        await events_client.login(COC_EMAIL, COC_PASSWORD)
        logger.info("Login no CoC EventsClient bem-sucedido.")
        
        events_client.add_clan_updates(CLAN_TAG)
        events_client.add_war_updates(CLAN_TAG)
        
        @events_client.event
        @coc.ClanEvents.member_join()
        async def _(member, clan): await on_clan_member_join(member, clan)
            
        @events_client.event
        @coc.ClanEvents.member_leave()
        async def _(member, clan): await on_clan_member_leave(member, clan)
            
        @events_client.event
        @coc.WarEvents.attack()
        async def _(attack, war): await on_war_attack(attack, war)
            
        @events_client.event
        @coc.ClanEvents.member_role()
        async def _(old_member, new_member): await on_clan_member_role_change(old_member, new_member)
            
        @events_client.event
        @coc.ClanEvents.member_trophies()
        async def _(old_member, new_member): await on_clan_member_trophies_change(old_member, new_member)
            
        @events_client.event
        @coc.ClanEvents.member_league()
        async def _(old_member, new_member): await on_clan_member_league_change(old_member, new_member)
        
        coc_client = events_client
        logger.info("Todos os eventos do CoC foram registrados com sucesso!")
        
        test_clan = await coc_client.get_clan(CLAN_TAG)
        logger.info(f"Teste de conexão bem-sucedido: {test_clan.name} tem {test_clan.member_count} membros")
        
    except Exception as e:
        logger.error(f"Erro ao configurar eventos CoC: {e}", exc_info=True)

# --- ROTINAS E HANDLERS DO PAINEL WEB (Lógica antiga restaurada e adaptada) ---
async def get_cached_web_data(key: str, func, *args):
    now = datetime.datetime.now()
    if key in web_api_cache and (now - web_api_cache[key]["timestamp"]).total_seconds() < WEB_API_CACHE_DURATION_SECONDS:
        return web_api_cache[key]["data"]
    
    data = await func(*args)
    web_api_cache[key] = {"data": data, "timestamp": now}
    return data

def format_war_time_details(war_obj: coc.ClanWar, time_now_tz: datetime.datetime) -> Dict[str, Any]:
    details: Dict[str, Any] = { "time_key": "N/A", "time_value": "N/A", "time_remaining": "N/A" }
    if war_obj.state == "preparation":
        start_aware = war_obj.start_time.time.astimezone(TIMEZONE)
        details.update({"time_key": "Início", "time_value": start_aware.strftime('%d/%m/%y %H:%M')})
        delta = start_aware - time_now_tz
        if delta.total_seconds() > 0:
            d, r = divmod(delta.total_seconds(), 86400)
            h, r_h = divmod(r, 3600)
            m, _ = divmod(r_h, 60)
            details["time_remaining"] = f"{int(d)}d {int(h)}h {int(m)}m" if d > 0 else f"{int(h)}h {int(m)}m"
        else:
            details["time_remaining"] = "Iniciando..."
    elif war_obj.state in ["inWar", "warEnded"]:
        end_aware = war_obj.end_time.time.astimezone(TIMEZONE)
        details.update({"time_key": "Fim" if war_obj.state == "inWar" else "Finalizada em", "time_value": end_aware.strftime('%d/%m/%y %H:%M')})
        if war_obj.state == "inWar":
            delta = end_aware - time_now_tz
            if delta.total_seconds() > 0:
                d, r = divmod(delta.total_seconds(), 86400)
                h, r_h = divmod(r, 3600)
                m, _ = divmod(r_h, 60)
                details["time_remaining"] = f"{int(d)}d {int(h)}h {int(m)}m" if d > 0 else f"{int(h)}h {int(m)}m"
            else:
                details["time_remaining"] = "Finalizando..."
        else:
            details["time_remaining"] = "-"
    return details

async def get_current_or_last_war(clan_tag_param: str) -> Optional[coc.ClanWar]:
    try:
        # Prioriza CWL se estiver ativa
        league_group = await coc_client.get_league_group(clan_tag_param)
        if league_group.state != "notInWar":
            for war_tag in reversed([tag for rd in league_group.rounds for tag in rd if tag != "#0"]):
                try:
                    lg_war = await coc_client.get_league_war(war_tag)
                    if lg_war.state in ('inWar', 'preparation'):
                        return lg_war
                except coc.NotFound:
                    continue
            # Se não encontrar guerra ativa, pega a mais recente finalizada
            for war_tag in reversed([tag for rd in league_group.rounds for tag in rd if tag != "#0"]):
                try:
                    return await coc_client.get_league_war(war_tag)
                except coc.NotFound:
                    continue
    except coc.NotFound:
        pass  # Clã não está em CWL, continua para guerra normal
    except Exception as e:
        logger.error(f"Erro ao buscar guerra CWL: {e}", exc_info=True)

    try:
        # Busca guerra normal
        return await coc_client.get_current_war(clan_tag_param)
    except coc.PrivateWarLog:
        logger.warning(f"Log de guerra do clã {clan_tag_param} é privado.")
    except Exception as e:
        logger.error(f"Erro ao buscar guerra regular: {e}", exc_info=True)
    
    return None

async def fetch_clan_info_for_web() -> Dict[str, Any]:
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        districts = [{"name": d.name, "level": d.hall_level} for d in clan.capital_districts] if clan.capital_districts else []
        return {
            "name": clan.name, "tag": clan.tag, "level": clan.level, "points": clan.points,
            "capital_points": clan.capital_points, "member_count": clan.member_count,
            "description": clan.description, "war_wins": clan.war_wins,
            "location": clan.location.name if clan.location else "N/A",
            "type": clan.type.capitalize() if clan.type else "N/A",
            "badge_url": clan.badge.url, "version": BOT_VERSION, "capital_districts": districts,
            "capital_league": clan.capital_league.name
        }
    except Exception as e:
        logger.error(f"Erro ao buscar info do clã para web: {e}")
        return {"error": str(e)}

async def fetch_clan_members_for_web() -> Dict[str, Any]:
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        player_notes = await load_player_notes_from_db()
        members_data = []
        for m in sorted(clan.members, key=lambda x: x.trophies, reverse=True):
            note_info = player_notes.get(m.tag, {"text": "", "priority": "none"})
            members_data.append({
                "name": m.name, "tag": m.tag, "town_hall": m.town_hall,
                "league": m.league.name, "trophies": m.trophies, "role": m.role.name.capitalize(),
                "donations": m.donations, "received": m.received,
                "note": note_info.get("text", ""), "note_priority": note_info.get("priority", "none")
            })
        return {"members": members_data, "clan_name": clan.name}
    except Exception as e:
        logger.error(f"Erro ao buscar membros para web: {e}")
        return {"error": str(e)}

async def fetch_current_war_details_for_web() -> Dict[str, Any]:
    try:
        war = await get_current_or_last_war(CLAN_TAG)
        if not war or war.state == "notInWar":
            return {"error": "Nenhuma guerra para detalhar."}

        our_clan, opp_clan = (war.clan, war.opponent) if war.clan.tag == CLAN_TAG else (war.opponent, war.clan)
        time_details = format_war_time_details(war, datetime.datetime.now(TIMEZONE))
        
        all_attacks = []
        if war.attacks:
            for attack in sorted(war.attacks, key=lambda a: a.order):
                attacker = await get_player_data(attack.attacker_tag)
                defender = await get_player_data(attack.defender_tag)
                all_attacks.append({
                    "order": attack.order, "attacker_name": attacker.name, "attacker_townhall": attacker.town_hall,
                    "defender_name": defender.name, "defender_townhall": defender.town_hall,
                    "stars": attack.stars, "destruction": attack.destruction, "duration": f"{attack.duration}s"
                })

        def get_team_details(team_members):
            details = []
            for member in sorted(team_members, key=lambda m: m.map_position):
                attacks_made = [{"stars": a.stars, "destruction": a.destruction, "defender_name": war.get_member(a.defender_tag).name, "defender_townhall": war.get_member(a.defender_tag).town_hall} for a in member.attacks]
                defenses_received = [{"stars": d.stars, "destruction": d.destruction, "attacker_name": war.get_member(d.attacker_tag).name, "attacker_townhall": war.get_member(d.attacker_tag).town_hall} for d in member.defenses]
                details.append({
                    "name": member.name, "townhall": member.town_hall, "map_position": member.map_position,
                    "attacks_used": len(member.attacks), "attacks_made": attacks_made, "defenses_received": defenses_received
                })
            return details

        our_clan_members_in_war = get_team_details(our_clan.members)
        opponent_clan_members_in_war = get_team_details(opp_clan.members)

        def get_star_dist(attacks):
            dist = {0:0, 1:0, 2:0, 3:0}
            for attack in attacks:
                dist[attack.stars] += 1
            return dist

        our_attacks = [a for a in war.attacks if a.attacker.clan.tag == our_clan.tag]
        opp_attacks = [a for a in war.attacks if a.attacker.clan.tag == opp_clan.tag]

        war_data = {
            "status": war.state, "state_description": str(war.state).capitalize(),
            "clan_name": our_clan.name, "clan_stars": our_clan.stars, "clan_destruction": f"{our_clan.destruction:.2f}%",
            "clan_badge_url": our_clan.badge.url, "clan_attacks_used": our_clan.attacks_used,
            "opponent_name": opp_clan.name, "opponent_stars": opp_clan.stars, "opponent_destruction": f"{opp_clan.destruction:.2f}%",
            "opponent_badge_url": opp_clan.badge.url, "opponent_attacks_used": opp_clan.attacks_used,
            **time_details, "attacks_per_member": war.attacks_per_member, "team_size": war.team_size,
            "clan_star_distribution": get_star_dist(our_attacks),
            "opponent_star_distribution": get_star_dist(opp_attacks),
            "clan_avg_stars": f"{our_clan.stars / len(our_attacks):.2f}" if our_attacks else "0.00",
            "opponent_avg_stars": f"{opp_clan.stars / len(opp_attacks):.2f}" if opp_attacks else "0.00",
            "clan_avg_duration": f"{sum(a.duration for a in our_attacks) / len(our_attacks):.1f}s" if our_attacks else "0s",
            "opponent_avg_duration": f"{sum(a.duration for a in opp_attacks) / len(opp_attacks):.1f}s" if opp_attacks else "0s",
        }
        
        return {
            "war_data": war_data, "all_attacks": all_attacks,
            "our_clan_members_in_war": our_clan_members_in_war,
            "opponent_clan_members_in_war": opponent_clan_members_in_war
        }
    except Exception as e:
        logger.error(f"Erro ao buscar detalhes da guerra para web: {e}", exc_info=True)
        return {"error": str(e)}

async def fetch_war_attacks_remaining_for_web() -> Dict[str, Any]:
    try:
        war = await get_current_or_last_war(CLAN_TAG)
        if not war or war.state not in ["inWar", "preparation"]:
            return {"message": "Não há guerra em andamento ou preparação."}
        
        our_clan = war.clan if war.clan.tag == CLAN_TAG else war.opponent
        pending = []
        for m in sorted(our_clan.members, key=lambda x: x.map_position):
            attacks_left = war.attacks_per_member - len(m.attacks)
            if attacks_left > 0:
                pending.append({"name": m.name, "town_hall": m.town_hall, "attacks_left": attacks_left})
        
        return {"members_pending": pending, "clan_name": our_clan.name}
    except Exception as e:
        logger.error(f"Erro ao buscar ataques restantes: {e}")
        return {"error": str(e)}

async def fetch_war_log_for_web(limit: int = 10) -> Dict[str, Any]:
    try:
        log = await coc_client.get_war_log(CLAN_TAG, limit=limit)
        entries = []
        for entry in log:
            res = "Empate"
            if entry.result == "win": res = "Vitória"
            if entry.result == "lose": res = "Derrota"
            entries.append({
                "end_time": entry.end_time.time.astimezone(TIMEZONE).strftime('%d/%m/%y %H:%M'),
                "opponent_name": entry.opponent.name, "opponent_badge_url": entry.opponent.badge.url,
                "clan_stars": entry.clan.stars, "clan_destruction": f"{entry.clan.destruction:.2f}",
                "opponent_stars": entry.opponent.stars, "opponent_destruction": f"{entry.opponent.destruction:.2f}",
                "result": res, "team_size": entry.team_size, "is_cwl": entry.is_league_entry
            })
        return {"log": entries}
    except Exception as e:
        logger.error(f"Erro ao buscar log de guerra: {e}")
        return {"error": str(e)}

async def fetch_cwl_info_for_web() -> Dict[str, Any]:
    try:
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
                    our_clan, opp_clan = (war.clan, war.opponent) if war.clan.tag == CLAN_TAG else (war.opponent, war.clan)
                    td = format_war_time_details(war, datetime.datetime.now(TIMEZONE))
                    r_info["wars"].append({
                        "state": war.state, "clan_name": our_clan.name, "clan_stars": our_clan.stars,
                        "clan_destruction": f"{our_clan.destruction:.2f}%", "clan_badge_url": our_clan.badge.url,
                        "opponent_name": opp_clan.name, "opponent_stars": opp_clan.stars,
                        "opponent_destruction": f"{opp_clan.destruction:.2f}%", "opponent_badge_url": opp_clan.badge.url,
                        **td
                    })
                except Exception as e_w:
                    r_info["wars"].append({"error": f"Erro ao carregar guerra {war_tag}: {e_w}"})
            rounds_data.append(r_info)
            
        return {
            "status": "InCwl", "state": lg.state, "season": lg.season,
            "clans_in_group": [{"name": c.name, "tag": c.tag, "level": c.level, "badge_url": c.badge.url} for c in lg.clans],
            "rounds": rounds_data
        }
    except coc.NotFound:
        return {"status": "NotInCwl", "message": "Grupo CWL não encontrado."}
    except Exception as e:
        logger.error(f"Erro ao buscar info CWL: {e}")
        return {"error": str(e)}

# --- Handlers da API ---
async def api_clan_info_handler(request: web.Request) -> web.Response:
    data = await get_cached_web_data("web_clan_info", fetch_clan_info_for_web)
    return web.json_response(data)

async def api_members_handler(request: web.Request) -> web.Response:
    data = await get_cached_web_data("web_clan_members", fetch_clan_members_for_web)
    return web.json_response(data)

async def api_current_war_details_handler(request: web.Request) -> web.Response:
    data = await get_cached_web_data("web_current_war_details", fetch_current_war_details_for_web)
    return web.json_response(data)

async def api_war_attacks_remaining_handler(request: web.Request) -> web.Response:
    data = await get_cached_web_data("web_war_attacks_remaining", fetch_war_attacks_remaining_for_web)
    return web.json_response(data)

async def api_war_log_handler(request: web.Request) -> web.Response:
    limit = int(request.query.get("limit", 10))
    data = await get_cached_web_data(f"web_war_log_{limit}", fetch_war_log_for_web, limit)
    return web.json_response(data)

async def api_cwl_info_handler(request: web.Request) -> web.Response:
    data = await get_cached_web_data("web_cwl_info", fetch_cwl_info_for_web)
    return web.json_response(data)

async def api_save_player_note_handler(request: web.Request) -> web.Response:
    player_tag = request.match_info.get('player_tag')
    if not player_tag:
        return web.json_response({"error": "Player tag não fornecida"}, status=400)
    
    player_tag_fmt = coc.utils.correct_tag(player_tag)
    try:
        data = await request.json()
        note_text = data.get("text", "")
        note_priority = data.get("priority", "none")

        await save_player_note_to_db(player_tag_fmt, note_text, note_priority)
        
        # Invalida o cache de membros para refletir a nova nota
        if "web_clan_members" in web_api_cache:
            del web_api_cache["web_clan_members"]

        return web.json_response({"message": "Nota salva com sucesso."}, status=200)
    except json.JSONDecodeError:
        return web.json_response({"error": "Payload JSON inválido"}, status=400)
    except ConnectionError as e:
        return web.json_response({"error": str(e)}, status=503)
    except Exception as e:
        logger.error(f"Erro ao salvar nota para {player_tag_fmt}: {e}", exc_info=True)
        return web.json_response({"error": "Erro interno do servidor"}, status=500)

async def setup_web_server() -> Optional[web.AppRunner]:
    try:
        app = web.Application()
        app['bot'] = bot
        
        # Rotas da API
        app.router.add_get("/api/clan", api_clan_info_handler)
        app.router.add_get("/api/members", api_members_handler)
        app.router.add_get("/api/current_war_details", api_current_war_details_handler)
        app.router.add_get("/api/war_attacks_remaining", api_war_attacks_remaining_handler)
        app.router.add_get("/api/war_log", api_war_log_handler)
        app.router.add_get("/api/cwl_info", api_cwl_info_handler)
        app.router.add_post("/api/notes/{player_tag}", api_save_player_note_handler)
        
        app.router.add_get("/api/status", lambda r: web.json_response({
            "status": "online", 
            "version": BOT_VERSION,
            "timestamp": datetime.datetime.now(TIMEZONE).isoformat()
        }))
        
        # Rotas estáticas
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        if os.path.exists(static_dir):
            app.router.add_static('/static/', path=static_dir, name='static')
            painel_file = os.path.join(static_dir, "painel.html")
            if os.path.exists(painel_file):
                app.router.add_get("/painel", lambda r: web.FileResponse(painel_file))
        
        app.router.add_get("/", lambda r: web.Response(text=f"Bot running! v{BOT_VERSION}"))

        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logger.info(f"Servidor web iniciado na porta {port}")
        return runner
        
    except Exception as e:
        logger.error(f"Erro ao configurar servidor web: {e}", exc_info=True)
        return None

# --- EVENTO ON_READY DO BOT DO DISCORD ---
@bot.event
async def on_ready():
    logger.info(f"Bot {bot.user.name} online! Versão: {BOT_VERSION}")
    try:
        await setup_coc_events()
        
        clan = await coc_client.get_clan(CLAN_TAG)
        embed = discord.Embed(
            title=f"✅ ClashGenius Online | {clan.name}", 
            description=f"Monitoramento ativado para o clã **{clan.name} ({clan.tag})**.", 
            color=discord.Color.green()
        )
        embed.add_field(
            name="📊 Status do Clã", 
            value=f"**Membros:** {clan.member_count}/50\n**Troféus:** 🏆 {clan.points}", 
            inline=True
        )
        embed.add_field(
            name="⚙️ Status do Bot", 
            value=f"**Versão:** {BOT_VERSION}\n**API CoC:** ✅ OK", 
            inline=True
        )
        if clan.badge:
            embed.set_thumbnail(url=clan.badge.url)
        await send_log_embed(embed)
        
    except Exception as e:
        logger.error(f"Erro ao enviar o embed de inicialização: {e}", exc_info=True)

# --- FUNÇÃO PRINCIPAL DE EXECUÇÃO ---
async def main():
    global coc_client
    web_runner = None
    
    try:
        coc_client = coc.Client()
        
        bot.coc_client = coc_client
        bot.db = None
        bot.db_client = None

        if MONGO_DB_URL:
            try:
                bot.db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)
                db_name = motor.motor_asyncio.get_database_name_from_url(MONGO_DB_URL)
                if not db_name:
                    db_name = "clash_genius_db" # fallback
                    logger.warning(f"Nome do banco de dados não encontrado na URL. Usando '{db_name}'.")
                bot.db = bot.db_client[db_name]
                await bot.db.command('ping')
                logger.info(f"Conectado ao MongoDB: {bot.db.name}")
            except Exception as e:
                logger.error(f"Falha ao conectar ao MongoDB: {e}", exc_info=True)
        else:
            logger.warning("MONGO_DB_URL não definida. A base de dados para notas está desativada.")

        try:
            await coc_client.login(COC_EMAIL, COC_PASSWORD)
            logger.info("Login inicial no CoC bem-sucedido.")
        except coc.InvalidCredentials as e:
            logger.error(f"Credenciais do CoC inválidas: {e}")
            return
        except Exception as e:
            logger.error(f"Falha no login do CoC: {e}", exc_info=True)
            return

        web_runner = await setup_web_server()
        await bot.start(DISCORD_TOKEN)
        
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro na função main: {e}", exc_info=True)
    finally:
        try:
            if web_runner: await web_runner.cleanup()
            if coc_client: await coc_client.close()
            if events_client: await events_client.close()
            if hasattr(bot, 'db_client') and bot.db_client: bot.db_client.close()
        except Exception as e:
            logger.error(f"Erro no cleanup: {e}")

if __name__ == "__main__":
    if not all([DISCORD_TOKEN, COC_EMAIL, COC_PASSWORD, CLAN_TAG]):
        logger.critical("Variáveis de ambiente essenciais faltando.")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Bot desligado manualmente.")
