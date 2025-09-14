# -*- coding: utf-8 -*-
# Versão 20.1.75-EVENTS-COG

import os
import logging
import asyncio
import datetime
from typing import Dict, List, Optional, Any

import discord
from discord.ext import commands, tasks
import coc
import pytz
from dotenv import load_dotenv
import motor.motor_asyncio
from pymongo.uri_parser import parse_uri
from pymongo import DESCENDING
from aiohttp import web
from aiohttp_session import setup, get_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
import base64
from cryptography.fernet import Fernet
import json

# --- Importações dos Módulos Locais ---
from formatting import format_war_time_details
from war_predictor import WarPredictionSystemV3
from cogs.post_war_analysis import create_post_war_analysis_embed

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
AI_LOG_CHANNEL_ID = int(os.getenv("AI_LOG_CHANNEL_ID", 0))
POST_WAR_ANALYSIS_CHANNEL_ID = int(os.getenv("POST_WAR_ANALYSIS_CHANNEL_ID", 0))
CLAN_GAMES_CHANNEL_ID = int(os.getenv("CLAN_GAMES_CHANNEL_ID", 0))
MONGO_DB_URL = os.getenv("MONGO_DB_URL")
ROLE_ID_1STAR_ALERT = int(os.getenv("ROLE_ID_1STAR_ALERT", 0))
ROLE_ID_MISSED_ATTACK = int(os.getenv("ROLE_ID_MISSED_ATTACK", 0))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
FERNET_KEY = os.getenv("FERNET_KEY")

# --- Constantes e Configurações Globais ---
BOT_VERSION = "20.1.75-EVENTS-COG"
TIMEZONE = pytz.timezone('America/Sao_Paulo')
MAINTENANCE_MODE = False

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# --- Inicialização dos Clientes e Sistemas ---
bot = commands.Bot(command_prefix="!", intents=intents)
api_client: Optional[coc.Client] = None
war_prediction_system: Optional[WarPredictionSystemV3] = None

# --- Caches ---
player_short_term_cache: Dict[str, Any] = {}
clan_cache: Dict[str, Dict[str, Any]] = {}
web_api_cache: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION_SECONDS = 300
WEB_API_CACHE_DURATION_SECONDS = 45
last_war_end_time: Optional[datetime.datetime] = None

# --- FUNÇÕES AUXILIARES E DE LOG ---
async def send_ai_log_embed(war, prediction_result: Dict):
    """Envia o log de análise detalhado da IA para um canal específico no Discord."""
    events_cog = bot.get_cog("Eventos do Clã")
    if not events_cog:
        logger.error("Cog 'Eventos do Clã' não encontrado para enviar log da IA.")
        return

    try:
        our_clan = war.clan if war.clan.tag == CLAN_TAG else war.opponent
        opponent = war.opponent if war.clan.tag == CLAN_TAG else war.clan

        embed = discord.Embed(
            title="🧠 Relatório de Análise da IA de Guerra (v3.0)",
            description=f"**{our_clan.name}** vs **{opponent.name}**\n\n{prediction_result.get('summary_discord', 'N/A')}",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Probabilidade de Vitória", value=f"**{prediction_result.get('probability', 0):.1f}%**", inline=True)
        embed.add_field(name="Confiança da IA", value=f"{prediction_result.get('confidence', 0):.1f}%", inline=True)
        embed.add_field(name="Método de Análise", value=prediction_result.get('analysis_log', {}).get('method', 'Desconhecido'), inline=True)
        
        if prediction_result.get('tactical_insights'):
            embed.add_field(name="💡 Insights Táticos", value="• " + "\n• ".join(prediction_result['tactical_insights']), inline=False)
            
        if prediction_result.get('risk_factors'):
            embed.add_field(name="⚠️ Fatores de Risco", value="• " + "\n• ".join(prediction_result['risk_factors']), inline=False)

        features = prediction_result.get('analysis_log', {}).get('features')
        if features:
            features_text = (
                f"```"
                f"Star Diff: {features.get('star_difference', 0):>+.2f}\n"
                f"Destr Diff: {features.get('destruction_difference', 0):>+.2f}%\n"
                f"Atk Rem Diff: {features.get('attacks_remaining_difference', 0):>+d}\n"
                f"Momentum: {features.get('momentum_indicator', 0):>.2f}\n"
                f"Synergy: {features.get('clan_synergy_score', 0):>.2f}\n"
                f"Pressure: {features.get('pressure_index', 0):>.2f}\n"
                f"```"
            )
            embed.add_field(name="Métricas Chave Analisadas", value=features_text, inline=False)
        
        await events_cog._send_log_embed(embed, target_channel_id=AI_LOG_CHANNEL_ID)
        logger.info(f"Log de análise da IA v3.0 enviado para o canal {AI_LOG_CHANNEL_ID}.")

    except Exception as e:
        logger.error(f"Erro ao enviar log da IA para o Discord: {e}", exc_info=True)

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
    if MAINTENANCE_MODE: return
    if not hasattr(bot, 'db') or bot.db is None:
        logger.error("Banco de dados não disponível, não é possível salvar o histórico da guerra.")
        return
    try:
        war_collection = bot.db.war_history
        sanitized_war_data = _sanitize_keys_for_mongo(war_data)
        if 'war_data' in sanitized_war_data and 'end_time_iso' in sanitized_war_data['war_data'] and sanitized_war_data['war_data']['end_time_iso']:
            sanitized_war_data['_id'] = sanitized_war_data['war_data']['end_time_iso']
            
            await war_collection.replace_one({'_id': sanitized_war_data['_id']}, sanitized_war_data, upsert=True)
            logger.info(f"Guerra finalizada em {sanitized_war_data['_id']} salva no histórico.")

            count = await war_collection.count_documents({})
            if count > 50: 
                oldest_wars_cursor = war_collection.find().sort("war_data.end_time_iso", 1).limit(count - 50)
                async for old_war in oldest_wars_cursor:
                    await war_collection.delete_one({"_id": old_war["_id"]})
                    logger.info(f"Guerra mais antiga ({old_war['_id']}) removida do histórico para manter o limite de 50.")
        else:
            logger.error("Tentativa de salvar guerra no histórico sem 'end_time_iso'. Dados incompletos.")
    except Exception as e:
        logger.error(f"Erro ao salvar guerra no histórico do MongoDB: {e}", exc_info=True)

# --- FUNÇÕES DE BUSCA DE DADOS (API CoC) ---
async def get_player_data(tag: str) -> Optional[coc.Player]:
    if not api_client: return None
    normalized_tag = coc.utils.correct_tag(tag)
    if normalized_tag in player_short_term_cache:
        return player_short_term_cache[normalized_tag]
    try:
        player = await api_client.get_player(normalized_tag)
        player_short_term_cache[normalized_tag] = player
        # Adiciona o jogador ao histórico de troféus
        if hasattr(bot, 'db') and bot.db is not None:
            await bot.db.trophy_history.insert_one({
                "player_tag": normalized_tag,
                "trophies": player.trophies,
                "timestamp": datetime.datetime.now(pytz.utc)
            })
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
        
async def get_current_war_gracefully(clan_tag: str) -> Optional[coc.ClanWar]:
    if not api_client:
        return None
    try:
        return await api_client.get_current_war(clan_tag)
    except (coc.NotFound, coc.PrivateWarLog):
        return None

# --- ROTINAS E HANDLERS DO PAINEL WEB ---
async def get_cached_web_data(key: str, func, *args):
    now = datetime.datetime.now()
    if key in web_api_cache and (now - web_api_cache[key]["timestamp"]).total_seconds() < WEB_API_CACHE_DURATION_SECONDS:
        return web_api_cache[key]["data"]
    data = await func(*args)
    web_api_cache[key] = {"data": data, "timestamp": now}
    return data

async def calculate_war_prediction(war: coc.ClanWar) -> Dict[str, Any]:
    if not war_prediction_system:
        return {"summary_panel": "Sistema de IA não inicializado.", "probability": 50.0, "confidence": 0.0}
    try:
        result = await war_prediction_system.predict_war_outcome(war, CLAN_TAG)

        if 'analysis_log' in result and AI_LOG_CHANNEL_ID:
            await send_ai_log_embed(war, result)
        
        return result
            
    except Exception as e:
        logger.error(f"Erro fatal na previsão inteligente: {e}", exc_info=True)
        return {"summary_panel": "Análise indisponível devido a um erro interno."}

async def fetch_clan_info_for_web():
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        if not clan:
            return {"error": "Não foi possível carregar os dados do clã."}
        
        return {
            "name": getattr(clan, 'name', 'N/A'),
            "tag": getattr(clan, 'tag', 'N/A'),
            "level": getattr(clan, 'level', 0),
            "points": getattr(clan, 'points', 0),
            "capital_points": getattr(clan, 'capital_points', 0),
            "member_count": getattr(clan, 'member_count', 0),
            "description": getattr(clan, 'description', ''),
            "war_wins": getattr(clan, 'war_wins', 0),
            "location": getattr(clan.location, 'name', 'N/A') if hasattr(clan, 'location') and clan.location else 'N/A',
            "type": str(getattr(clan, 'type', 'N/A')).capitalize(),
            "badge_url": getattr(clan.badge, 'url', None) if hasattr(clan, 'badge') else None,
            "version": BOT_VERSION,
            "capital_districts": [{"name": d.name, "level": d.hall_level} for d in getattr(clan, 'capital_districts', [])],
            "capital_league": getattr(clan.capital_league, 'name', 'N/A') if hasattr(clan, 'capital_league') and clan.capital_league else 'N/A'
        }
    except Exception as e:
        logger.error(f"Erro em fetch_clan_info_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar informações do clã."}

async def fetch_current_war_details_for_web():
    try:
        war = await get_current_war_gracefully(CLAN_TAG)
        if not war or war.state == "notInWar":
            return {"error": "Nenhuma guerra para detalhar."}
        if not war.clan or not war.opponent:
            return {"error": "Dados da guerra incompletos (clã ou oponente faltando)."}

        prediction_data = await calculate_war_prediction(war)

        our_clan, opp_clan = (war.clan, war.opponent) if war.clan.tag == CLAN_TAG else (war.opponent, war.clan)
        
        def get_team_details(team, war_obj):
            if not team or not hasattr(team, 'members'): return []
            details = []
            for m in team.members:
                if not m: continue
                details.append({
                    "name": m.name, "tag": m.tag, "townhall": m.town_hall, "map_position": m.map_position,
                    "attacks_used": len(m.attacks),
                    "attacks_made": [{"stars": a.stars, "destruction": a.destruction, "defender_name": getattr(war_obj.get_member(a.defender_tag), 'name', a.defender_tag), "defender_townhall": getattr(war_obj.get_member(a.defender_tag), 'town_hall', '?')} for a in m.attacks],
                    "defenses_received": [{"stars": d.stars, "destruction": d.destruction, "attacker_name": getattr(war_obj.get_member(d.attacker_tag), 'name', d.attacker_tag), "attacker_townhall": getattr(war_obj.get_member(d.attacker_tag), 'town_hall', '?')} for d in m.defenses]
                })
            return sorted(details, key=lambda x: x['map_position'])

        def get_star_dist(attacks):
            dist = {i: 0 for i in range(4)}
            for a in attacks:
                if a: dist[a.stars] += 1
            return dist

        our_attacks = [a for a in war.attacks if a and getattr(getattr(a, 'attacker', None), 'clan', None) and a.attacker.clan.tag == our_clan.tag]
        opp_attacks = [a for a in war.attacks if a and getattr(getattr(a, 'attacker', None), 'clan', None) and a.attacker.clan.tag == opp_clan.tag]
        
        all_attacks_data = []
        for attack in war.attacks:
            if not attack: continue
            attacker = war.get_member(attack.attacker_tag)
            defender = war.get_member(attack.defender_tag)
            all_attacks_data.append({
                "order": attack.order, "attacker_clan_tag": getattr(getattr(attacker, 'clan', None), 'tag', None),
                "attacker_tag": getattr(attacker, 'tag', attack.attacker_tag), "attacker_name": getattr(attacker, 'name', attack.attacker_tag),
                "attacker_townhall": getattr(attacker, 'town_hall', '?'), "defender_name": getattr(defender, 'name', attack.defender_tag),
                "defender_townhall": getattr(defender, 'town_hall', '?'), "stars": attack.stars, "destruction": attack.destruction,
                "duration": f"{attack.duration}s"
            })

        return {
            "war_data": {
                "clan_tag": our_clan.tag, "status": str(war.state), "state_description": str(war.state).capitalize(),
                "clan_name": our_clan.name, "clan_stars": our_clan.stars, "clan_destruction": f"{our_clan.destruction:.2f}%",
                "clan_badge_url": our_clan.badge.url if our_clan.badge else None, "clan_attacks_used": our_clan.attacks_used,
                "opponent_name": opp_clan.name, "opponent_stars": opp_clan.stars, "opponent_destruction": f"{opp_clan.destruction:.2f}%",
                "opponent_badge_url": opp_clan.badge.url if opp_clan.badge else None, "opponent_attacks_used": opp_clan.attacks_used,
                **format_war_time_details(war, datetime.datetime.now(pytz.utc)),
                "attacks_per_member": war.attacks_per_member, "team_size": war.team_size,
                "clan_star_distribution": get_star_dist(our_attacks), "opponent_star_distribution": get_star_dist(opp_attacks),
                "clan_avg_stars": f"{our_clan.stars / len(our_attacks):.2f}" if our_attacks else "0.00",
                "opponent_avg_stars": f"{opp_clan.stars / len(opp_attacks):.2f}" if opp_attacks else "0.00",
                "clan_avg_duration": f"{sum(a.duration for a in our_attacks) / len(our_attacks):.1f}s" if our_attacks else "0s",
                "opponent_avg_duration": f"{sum(a.duration for a in opp_attacks) / len(opp_attacks):.1f}s" if opp_attacks else "0s",
            },
            "all_attacks": all_attacks_data,
            "our_clan_members_in_war": get_team_details(our_clan, war),
            "opponent_clan_members_in_war": get_team_details(opp_clan, war),
            "prediction": prediction_data
        }
    except Exception as e:
        logger.error(f"Erro em fetch_current_war_details_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar dados da guerra."}

async def fetch_clan_members_for_web():
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        if not clan:
            return {"error": "Não foi possível carregar os dados do clã."}

        player_notes = await load_player_notes_from_db()
        members_list = []
        for member in clan.members:
            note_data = player_notes.get(member.tag, {})
            members_list.append({
                "tag": member.tag, "name": member.name, "town_hall": member.town_hall,
                "league": member.league.name if member.league else "Sem Liga",
                "trophies": member.trophies, "role": member.role.name.capitalize() if member.role else "Membro",
                "donations": member.donations, "received": member.received,
                "note": note_data.get("text", ""), "note_priority": note_data.get("priority", "none")
            })
        
        role_order = {"Leader": 0, "Co-leader": 1, "Admin": 2, "Member": 3}
        sorted_members = sorted(members_list, key=lambda m: (role_order.get(m["role"], 4), -m["trophies"]))

        return {"clan_name": clan.name, "members": sorted_members, "version": BOT_VERSION}
    except Exception as e:
        logger.error(f"Erro em fetch_clan_members_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar a lista de membros."}

async def fetch_missed_attacks_history_for_web():
    if not hasattr(bot, 'db') or bot.db is None:
        return {"error": "Histórico indisponível (Banco de dados não conectado)."}
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        if not clan:
            return {"error": "Não foi possível carregar os dados do clã para o histórico."}

        war_collection = bot.db.war_history
        log_cursor = war_collection.find({}).sort("war_data.end_time_iso", DESCENDING)
        
        wars_with_missed_attacks = []
        is_first_war = True

        async for war_doc in log_cursor:
            war_data = war_doc.get("war_data", {})
            our_members_in_war = war_doc.get("our_clan_members_in_war", [])
            
            missed_attacks_members = []
            attacks_per_member = war_data.get("attacks_per_member", 2)

            for member in our_members_in_war:
                attacks_made = member.get("attacks_used", 0)
                attacks_left = attacks_per_member - attacks_made
                if attacks_left > 0:
                    missed_attacks_members.append({
                        "name": member.get("name", "Nome desconhecido"), "tag": member.get("tag", "#?"),
                        "town_hall": member.get("townhall", "?"), "attacks_left": attacks_left,
                    })
            
            if missed_attacks_members and war_data.get("end_time_iso"):
                end_time_dt = datetime.datetime.fromisoformat(war_data.get("end_time_iso"))
                wars_with_missed_attacks.append({
                    "opponent_name": war_data.get("opponent_name", "Oponente Desconhecido"),
                    "end_date": end_time_dt.astimezone(TIMEZONE).strftime('%d/%m/%y'),
                    "missed_attacks_members": missed_attacks_members, "is_latest": is_first_war
                })
                is_first_war = False
        
        return {"clan_name": clan.name, "wars_with_missed_attacks": wars_with_missed_attacks}
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
            if war_data.get("end_time_iso"):
                end_time_dt = datetime.datetime.fromisoformat(war_data.get("end_time_iso"))
                result = "Vitória" if war_data.get("clan_stars", 0) > war_data.get("opponent_stars", 0) else \
                         "Derrota" if war_data.get("clan_stars", 0) < war_data.get("opponent_stars", 0) else "Empate"
                entries.append({
                    "end_time_iso": war_data.get("end_time_iso"),
                    "end_time_formatted": end_time_dt.astimezone(TIMEZONE).strftime('%d/%m/%y %H:%M'),
                    "opponent_name": war_data.get("opponent_name"), "opponent_badge_url": war_data.get("opponent_badge_url"),
                    "clan_stars": war_data.get("clan_stars"), "clan_destruction": war_data.get("clan_destruction"),
                    "opponent_stars": war_data.get("opponent_stars"), "opponent_destruction": war_data.get("opponent_destruction"),
                    "result": result, "team_size": war_data.get("team_size"),
                    "is_cwl": "CWL" in war_data.get("status", "").lower()
                })
        return {"log": entries}
    except Exception as e:
        logger.error(f"Erro em fetch_war_log_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar histórico de guerras."}

async def fetch_cwl_info_for_web():
    try:
        if not api_client: return {"error": "CWLFeatureDisabled", "message": "API do CoC não iniciada."}
        
        cwl_war = await api_client.get_league_group(CLAN_TAG)
        if not cwl_war: return {"status": "NotInCwl", "message": "O clã não está em uma CWL."}

        season, state = cwl_war.season, str(cwl_war.state).capitalize()
        clans_in_group = [{"name": c.name, "tag": c.tag, "level": c.level, "badge_url": c.badge.url} for c in cwl_war.clans]
        
        rounds_info = []
        for i, a_round in enumerate(cwl_war.rounds):
            round_data = {"round_number": i + 1, "wars": []}
            for war_tag in a_round:
                try:
                    war = await api_client.get_league_war(war_tag)
                    if war:
                        round_data["wars"].append({
                            "war_tag": war_tag, "clan_name": war.clan.name, "clan_badge_url": war.clan.badge.url,
                            "clan_stars": war.clan.stars, "clan_destruction": f"{war.clan.destruction:.2f}%",
                            "opponent_name": war.opponent.name, "opponent_badge_url": war.opponent.badge.url,
                            "opponent_stars": war.opponent.stars, "opponent_destruction": f"{war.opponent.destruction:.2f}%",
                            **format_war_time_details(war, datetime.datetime.now(pytz.utc))
                        })
                except Exception as e:
                    logger.warning(f"Não foi possível buscar a guerra da CWL {war_tag}: {e}")
            rounds_info.append(round_data)

        return {"status": "InCwl", "season": season, "state": state, "clans_in_group": clans_in_group, "rounds": rounds_info}
    except coc.NotFound:
        return {"status": "NotInCwl", "message": "O clã não está em uma CWL."}
    except Exception as e:
        logger.error(f"Erro em fetch_cwl_info_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao buscar dados da CWL."}

async def fetch_highlights_for_web():
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        if not clan: return {"error": "Não foi possível carregar os dados do clã."}
        
        top_donors = sorted(clan.members, key=lambda m: m.donations, reverse=True)[:3]
        top_donors_data = [{"name": m.name, "donations": m.donations, "town_hall": m.town_hall} for m in top_donors]

        war_heroes, war_end_date_str = [], ""
        if hasattr(bot, 'db') and bot.db is not None:
            latest_war_doc = await bot.db.war_history.find_one({}, sort=[("war_data.end_time_iso", DESCENDING)])
            if latest_war_doc:
                from cogs.post_war_analysis import _calculate_post_war_stats
                analysis = _calculate_post_war_stats(latest_war_doc)
                war_heroes = analysis.get("war_heroes", [])
                
                if latest_war_doc.get("war_data", {}).get("end_time_iso"):
                    end_time = datetime.datetime.fromisoformat(latest_war_doc["war_data"]["end_time_iso"])
                    war_end_date_str = end_time.astimezone(TIMEZONE).strftime('%d/%m')
        
        active_members = sorted(clan.members, key=lambda m: m.donations, reverse=True)[:10]
        chart_data = {"labels": [m.name for m in active_members], "donations": [m.donations for m in active_members], "received": [m.received for m in active_members]}

        return {
            "top_donors": top_donors_data, 
            "war_heroes": war_heroes,
            "activity_chart_data": chart_data, 
            "clan_name": clan.name, 
            "war_date": war_end_date_str
        }
    except Exception as e:
        logger.error(f"Erro em fetch_highlights_for_web: {e}", exc_info=True)
        return {"error": "Erro interno ao processar destaques."}


async def api_clan_info_handler(request): return web.json_response(await get_cached_web_data('clan_info', fetch_clan_info_for_web))
async def api_members_handler(request): return web.json_response(await get_cached_web_data('members', fetch_clan_members_for_web))
async def api_current_war_details_handler(request): return web.json_response(await get_cached_web_data('current_war_details', fetch_current_war_details_for_web))
async def api_missed_attacks_history_handler(request): return web.json_response(await get_cached_web_data('missed_attacks_history', fetch_missed_attacks_history_for_web))
async def api_war_log_handler(request): return web.json_response(await get_cached_web_data('war_log', fetch_war_log_for_web))
async def api_cwl_info_handler(request): return web.json_response(await get_cached_web_data('cwl_info', fetch_cwl_info_for_web))
async def api_highlights_handler(request): return web.json_response(await get_cached_web_data('highlights', fetch_highlights_for_web))

async def api_save_player_note_handler(request):
    try:
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        data = await request.json()
        await save_player_note_to_db(player_tag, data.get('text', ''), data.get('priority', 'none'))
        web_api_cache.pop('members', None)
        return web.Response(status=204)
    except Exception as e:
        logger.error(f"Erro ao salvar nota via API: {e}", exc_info=True)
        return web.json_response({"error": "Erro ao salvar a nota."}, status=500)

async def api_historic_war_handler(request):
    if not hasattr(bot, 'db') or bot.db is None: return web.json_response({"error": "Banco de dados não conectado."}, status=503)
    try:
        war_doc = await bot.db.war_history.find_one({"_id": request.match_info['war_id']})
        return web.json_response(war_doc, dumps=lambda v: json.dumps(v, default=str)) if war_doc else web.json_response({"error": "Guerra não encontrada."}, status=404)
    except Exception as e:
        logger.error(f"Erro ao buscar guerra histórica: {e}", exc_info=True)
        return web.json_response({"error": "Erro interno no servidor."}, status=500)
        
async def api_member_profile_handler(request):
    """API para buscar o perfil detalhado de um membro."""
    try:
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        logger.info(f"Buscando perfil para a tag: {player_tag}")
        
        player_data = await get_player_data(player_tag)
        if not player_data:
            logger.warning(f"Jogador com a tag {player_tag} não encontrado pela API do CoC.")
            return web.json_response({"error": "Jogador não encontrado."}, status=404)
        
        trophy_history = []
        if hasattr(bot, 'db') and bot.db is not None:
             cursor = bot.db.trophy_history.find({"player_tag": player_tag}).sort("timestamp", DESCENDING).limit(30)
             trophy_history = [{"trophies": doc["trophies"], "timestamp": doc["timestamp"].strftime("%d/%m")} async for doc in cursor]
             trophy_history.reverse()

        profile = {
            "name": player_data.name, "tag": player_data.tag, "town_hall": player_data.town_hall,
            "heroes": [{"name": h.name, "level": h.level, "max_level": h.max_level} for h in player_data.heroes if h.is_home_base],
            "donations": player_data.donations, "received": player_data.received,
            "trophies": player_data.trophies, "league": player_data.league.name if player_data.league else "N/A",
            "trophy_history": trophy_history,
        }
        return web.json_response(profile)
    except coc.NotFound:
        logger.warning(f"coc.NotFound para a tag {request.match_info['player_tag']}")
        return web.json_response({"error": "Jogador não encontrado (API)."}, status=404)
    except Exception as e:
        logger.error(f"Erro ao buscar perfil do membro via API para tag {request.match_info['player_tag']}: {e}", exc_info=True)
        return web.json_response({"error": "Erro interno ao buscar perfil."}, status=500)

@tasks.loop(seconds=60.0)
async def check_war_end_task():
    global last_war_end_time
    await bot.wait_until_ready()
    if not api_client: return

    events_cog = bot.get_cog("Eventos do Clã")
    if not events_cog: return

    try:
        war = await api_client.get_current_war(CLAN_TAG)
        if war and war.state == 'warEnded' and hasattr(war, 'end_time'):
            if last_war_end_time is None or war.end_time.time > last_war_end_time:
                logger.info(f"Nova guerra finalizada detectada.")
                last_war_end_time = war.end_time.time
                
                war_details = await fetch_current_war_details_for_web()
                if 'error' not in war_details: 
                    await save_war_to_history(war_details)
                
                war_doc_from_db = await bot.db.war_history.find_one({"_id": war_details["war_data"]["end_time_iso"]})
                
                if war_doc_from_db and POST_WAR_ANALYSIS_CHANNEL_ID:
                    analysis_embed = create_post_war_analysis_embed(war_doc_from_db)
                    if analysis_embed:
                        await events_cog._send_log_embed(analysis_embed, target_channel_id=POST_WAR_ANALYSIS_CHANNEL_ID)
                        logger.info(f"Análise pós-guerra enviada para o canal {POST_WAR_ANALYSIS_CHANNEL_ID}.")

                our_clan = war.clan if war.clan.tag == CLAN_TAG else war.opponent
                missed = [f"**{m.name}** (CV{m.town_hall}): {war.attacks_per_member - len(m.attacks)} perdido(s)" for m in our_clan.members if len(m.attacks) < war.attacks_per_member]
                if missed:
                    embed = discord.Embed(title=f"🚩 Relatório de Ataques Perdidos", color=discord.Color.dark_gold())
                    embed.add_field(name="Placar Final", value=f"**{war.clan.name}:** {war.clan.stars}⭐\n**{war.opponent.name}:** {war.opponent.stars}⭐", inline=False)
                    embed.add_field(name="Detalhes", value="\n".join(missed), inline=False)
                    if hasattr(war.opponent.badge, 'url'): embed.set_thumbnail(url=war.opponent.badge.url)
                    role_mention = f"<@&{ROLE_ID_MISSED_ATTACK}>" if ROLE_ID_MISSED_ATTACK else ""
                    await events_cog._send_log_embed(embed, content=f"{role_mention} Atenção!")
                
    except (coc.PrivateWarLog, coc.NotFound): pass
    except Exception as e:
        logger.error(f"Erro na task de fim de guerra: {e}", exc_info=True)

@tasks.loop(hours=24)
async def daily_player_data_snapshot():
    await bot.wait_until_ready()
    if not api_client or not hasattr(bot, 'db') or bot.db is None:
        logger.info("Snapshot diário pulado (API ou DB não prontos).")
        return
    
    logger.info("Iniciando snapshot diário de dados dos jogadores.")
    try:
        clan = await api_client.get_clan(CLAN_TAG)
        snapshot_time = datetime.datetime.now(pytz.utc)
        records = []
        for member in clan.members:
            records.append({
                "player_tag": member.tag,
                "trophies": member.trophies,
                "donations": member.donations,
                "received": member.received,
                "timestamp": snapshot_time
            })
        if records:
            await bot.db.trophy_history.insert_many(records)
            logger.info(f"Snapshot salvo para {len(records)} jogadores.")
    except Exception as e:
        logger.error(f"Erro na task de snapshot diário: {e}", exc_info=True)

@tasks.loop(seconds=10, count=1)
async def send_online_status_task():
    await bot.wait_until_ready()
    if not api_client: await asyncio.sleep(5)
    
    events_cog = bot.get_cog("Eventos do Clã")
    if not events_cog:
        logger.error("Cog de eventos não encontrado para enviar status online.")
        return

    try:
        clan = await api_client.get_clan(CLAN_TAG)
        embed = discord.Embed(title=f"✅ ClashGenius Online | {clan.name}", description=f"Monitoramento ativado para **{clan.name} ({clan.tag})**.", color=discord.Color.green())
        embed.add_field(name="📊 Status do Clã", value=f"**Membros:** {clan.member_count}/50\n**Troféus:** 🏆 {clan.points}", inline=True)
        embed.add_field(name="⚙️ Status do Bot", value=f"**Versão:** {BOT_VERSION}\n**API CoC:** ✅ OK", inline=True)
        if clan.badge: embed.set_thumbnail(url=clan.badge.url)
        await events_cog._send_log_embed(embed)
    except Exception as e:
        logger.error(f"Falha ao enviar status online: {e}", exc_info=True)

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
    app.router.add_get("/api/player_profile/{player_tag:.*}", api_member_profile_handler)
    app.router.add_get("/api/status", lambda r: web.json_response({"status": "online", "version": BOT_VERSION}))
    
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.router.add_static('/static/', path=static_dir, name='static')
    app.router.add_get("/painel", lambda r: web.FileResponse(os.path.join(static_dir, "painel.html")))
    app.router.add_get("/", lambda r: web.Response(text=f"Bot running! v{BOT_VERSION}"))
    
    # Rotas do Admin
    async def admin_login_page(r): return web.FileResponse(os.path.join(static_dir, "admin_login.html")) if not (await get_session(r)).get('admin') else web.HTTPFound('/admin/panel')
    async def admin_panel_page(r): return web.FileResponse(os.path.join(static_dir, "admin_panel.html")) if (await get_session(r)).get('admin') else web.HTTPFound('/admin')
    async def admin_login_handler(r):
        data = await r.post()
        if data.get('password') == ADMIN_PASSWORD:
            (await get_session(r))['admin'] = True
            return web.HTTPFound('/admin/panel')
        return web.HTTPFound('/admin?error=1')
    async def admin_logout_handler(r):
        (await get_session(r)).pop('admin', None)
        return web.HTTPFound('/admin')
    
    async def admin_api_handler(request, action):
        if not (await get_session(request)).get('admin'): return web.json_response({"status": "unauthorized"}, status=403)
        events_cog = bot.get_cog("Eventos do Clã")
        if not events_cog: return web.json_response({"status": "error", "message": "Events cog not loaded."}, status=500)
        global MAINTENANCE_MODE
        if action == 'toggle_maintenance':
            MAINTENANCE_MODE = not MAINTENANCE_MODE
            bot.maintenance_mode = MAINTENANCE_MODE
            status_str = "ATIVADO" if MAINTENANCE_MODE else "DESATIVADO"
            embed = discord.Embed(title=f"🚨 Modo Manutenção {status_str} 🚨", color=discord.Color.orange() if MAINTENANCE_MODE else discord.Color.green())
            await events_cog._send_log_embed(embed)
            return web.json_response({"status": "success", "maintenance_mode": MAINTENANCE_MODE})
        elif action == 'send_test_embed':
            embed = discord.Embed(title="✅ Mensagem de Teste", description="Comunicação OK!", color=discord.Color.blue())
            await events_cog._send_log_embed(embed)
            return web.json_response({"status": "success"})
        elif action == 'get_status':
            return web.json_response({"status": "ok", "maintenance_mode": MAINTENANCE_MODE, "version": BOT_VERSION})
    
    app.router.add_get("/admin", admin_login_page)
    app.router.add_post("/admin/login", admin_login_handler)
    app.router.add_get("/admin/logout", admin_logout_handler)
    app.router.add_get("/admin/panel", admin_panel_page)
    app.router.add_post("/admin/toggle_maintenance", lambda r: admin_api_handler(r, 'toggle_maintenance'))
    app.router.add_post("/admin/send_test_embed", lambda r: admin_api_handler(r, 'send_test_embed'))
    app.router.add_get("/api/admin/status", lambda r: admin_api_handler(r, 'get_status'))

    secret_key = base64.urlsafe_b64decode(Fernet.generate_key() if not FERNET_KEY else FERNET_KEY.encode())
    setup(app, EncryptedCookieStorage(secret_key))
    
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Servidor web iniciado em http://0.0.0.0:{port}")

@bot.event
async def on_ready():
    global war_prediction_system, api_client
    logger.info(f'Bot {bot.user} está online e pronto!')
    try:
        if MONGO_DB_URL:
            db_name = parse_uri(MONGO_DB_URL).get('database', 'clash_data')
            bot.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)
            bot.db = bot.mongo_client[db_name]
            logger.info(f"Conectado ao MongoDB: {db_name}")
            war_prediction_system = WarPredictionSystemV3(db_connection=bot.db)
            await war_prediction_system.initialize_system()
        else:
            bot.db = None
            logger.warning("URL do MongoDB não fornecida.")
            war_prediction_system = WarPredictionSystemV3()
            await war_prediction_system.initialize_system()
    except Exception as e:
        logger.error(f"Falha ao conectar com o MongoDB: {e}", exc_info=True)
        bot.db = None
        war_prediction_system = WarPredictionSystemV3()
        await war_prediction_system.initialize_system()

    bot.clan_tag = CLAN_TAG
    bot.clan_games_channel_id = CLAN_GAMES_CHANNEL_ID
    bot.channel_id = CHANNEL_ID
    bot.role_id_1star_alert = ROLE_ID_1STAR_ALERT
    bot.role_id_missed_attack = ROLE_ID_MISSED_ATTACK
    bot.maintenance_mode = MAINTENANCE_MODE
    bot.bot_version = BOT_VERSION
    bot.timezone = TIMEZONE

    if not check_war_end_task.is_running(): check_war_end_task.start()
    if not send_online_status_task.is_running(): send_online_status_task.start()
    if not daily_player_data_snapshot.is_running(): daily_player_data_snapshot.start()

async def main():
    global api_client
    async with bot:
        try:
            api_client = coc.Client()
            await api_client.login(COC_EMAIL, COC_PASSWORD)
            bot.api_client = api_client
            logger.info("Login no coc.Client (api_client) bem-sucedido.")

            logger.info("Carregando cogs...")
            for filename in os.listdir('./cogs'):
                if filename.endswith('_cog.py') and not filename.startswith('__'):
                    try:
                        await bot.load_extension(f'cogs.{filename[:-3]}')
                        logger.info(f"Cog '{filename[:-3]}' carregado com sucesso.")
                    except Exception as e:
                        logger.error(f"Falha ao carregar o cog '{filename[:-3]}'. Erro: {e}", exc_info=True)
            
            await setup_web_server()
            await bot.start(DISCORD_TOKEN)
        except Exception as e:
            logger.critical(f"Erro crítico na inicialização: {e}", exc_info=True)
        finally:
            if api_client: await api_client.close()
            if hasattr(bot, 'mongo_client'): bot.mongo_client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot desligado manualmente.")

