# -*- coding: utf-8 -*-
# Versão 20.1.95-AdvisorV4-FIX

import os
import logging
import asyncio
import datetime
from typing import Dict, List, Optional, Any

import discord
from discord.ext import commands
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
# A classe do sistema é importada diretamente do cog agora
from cogs.war_advisor_cog import WarAdvisorSystem

# --- Configuração do Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
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
CWL_PLANNER_CHANNEL_ID = int(os.getenv("CWL_PLANNER_CHANNEL_ID", 0))
MONGO_DB_URL = os.getenv("MONGO_DB_URL")
ROLE_ID_1STAR_ALERT = int(os.getenv("ROLE_ID_1STAR_ALERT", 0))
ROLE_ID_MISSED_ATTACK = int(os.getenv("ROLE_ID_MISSED_ATTACK", 0))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
FERNET_KEY = os.getenv("FERNET_KEY")

# --- Constantes e Configurações Globais ---
BOT_VERSION = "20.1.96-ProfileCog" # Atualiza a versão
TIMEZONE = pytz.timezone('America/Sao_Paulo')

class ClashGeniusBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coc_email = COC_EMAIL
        self.coc_password = COC_PASSWORD
        self.clan_tag = CLAN_TAG
        self.channel_id = CHANNEL_ID
        self.ai_log_channel_id = AI_LOG_CHANNEL_ID
        self.post_war_analysis_channel_id = POST_WAR_ANALYSIS_CHANNEL_ID
        self.clan_games_channel_id = CLAN_GAMES_CHANNEL_ID
        self.cwl_planner_channel_id = CWL_PLANNER_CHANNEL_ID
        self.role_id_1star_alert = ROLE_ID_1STAR_ALERT
        self.role_id_missed_attack = ROLE_ID_MISSED_ATTACK
        self.bot_version = BOT_VERSION
        self.timezone = TIMEZONE
        self.maintenance_mode = False

        self.api_client: Optional[coc.Client] = None
        self.war_prediction_system: Optional[WarPredictionSystemV3] = None
        # O war_advisor_system será instanciado dentro do seu respectivo cog.
        self.db = None
        self.mongo_client = None

        self.clan_cache: Dict[str, Dict[str, Any]] = {}
        self.CACHE_DURATION_SECONDS = 300
        self.web_api_cache: Dict[str, Dict[str, Any]] = {}
        self.WEB_API_CACHE_DURATION_SECONDS = 45

        self.db_ready = asyncio.Event()
        self.coc_client_ready = asyncio.Event()

    async def setup_hook(self) -> None:
        logger.info("Executando setup_hook...")
        if MONGO_DB_URL:
            try:
                db_name = parse_uri(MONGO_DB_URL).get('database', 'genius_db')
                self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)
                self.db = self.mongo_client[db_name]
                logger.info(f"Conectado ao MongoDB: {db_name}")
                self.db_ready.set()
            except Exception as e:
                logger.error(f"Falha ao conectar com o MongoDB: {e}", exc_info=True)
        else:
            logger.warning("URL do MongoDB não fornecida.")
            self.db_ready.set()

        self.war_prediction_system = WarPredictionSystemV3(db_connection=self.db)
        await self.war_prediction_system.initialize_system()
        
        logger.info("Carregando cogs...")
        cog_files = ['events_cog.py', 'tasks_cog.py', 'database_cog.py', 'general_cog.py', 
                     'cwl_planner_cog.py', 'clan_games_cog.py', 'war_advisor_cog.py', 'profile_cog.py']
        for filename in cog_files:
            if filename.endswith('.py'):
                cog_name = filename[:-3]
                try:
                    await self.load_extension(f'cogs.{cog_name}')
                    logger.info(f"Cog '{cog_name}' carregado com sucesso.")
                except Exception as e:
                    logger.error(f"Falha ao carregar o cog '{cog_name}'. Erro: {e}", exc_info=True)

        self.loop.create_task(self.coc_login_task())
        self.loop.create_task(setup_web_server(self))

    async def coc_login_task(self):
        try:
            self.api_client = coc.Client()
            await self.api_client.login(self.coc_email, self.coc_password)
            logger.info("Login no coc.Client (api_client) bem-sucedido.")
            self.coc_client_ready.set()
        except Exception as e:
            logger.critical(f"Falha CRÍTICA no login do coc.Client: {e}", exc_info=True)

    async def on_ready(self):
        logger.info(f'Bot {self.user.name} está online e pronto!')

    async def close(self):
        logger.info("Fechando conexões...")
        if self.api_client: await self.api_client.close()
        if self.mongo_client: self.mongo_client.close()
        await super().close()

    async def get_clan_data_with_cache(self, tag: str) -> Optional[coc.Clan]:
        await self.coc_client_ready.wait()
        normalized_tag = coc.utils.correct_tag(tag)
        now = datetime.datetime.now()
        if normalized_tag in self.clan_cache and (now - self.clan_cache[normalized_tag]["timestamp"]).total_seconds() < self.CACHE_DURATION_SECONDS:
            return self.clan_cache[normalized_tag]["data"]
        try:
            clan_data = await self.api_client.get_clan(normalized_tag)
            self.clan_cache[normalized_tag] = {"data": clan_data, "timestamp": now}
            return clan_data
        except Exception as e:
            logger.error(f"Erro ao buscar dados do clã {tag}: {e}")
            return None
            
    # --- MÉTODOS DE BUSCA DE DADOS ---
    async def fetch_clan_info_for_web(self):
        clan = await self.get_clan_data_with_cache(self.clan_tag)
        if not clan: return {"error": "Não foi possível carregar os dados do clã."}
        
        capital_league_name = "N/A"
        if hasattr(clan, 'capital_league') and clan.capital_league:
            capital_league_name = clan.capital_league.name

        return {
            "name": getattr(clan, 'name', 'N/A'), "tag": getattr(clan, 'tag', 'N/A'),
            "level": getattr(clan, 'level', 0), "points": getattr(clan, 'points', 0),
            "capital_points": getattr(clan, 'capital_points', 0), "member_count": getattr(clan, 'member_count', 0),
            "description": getattr(clan, 'description', ''), "war_wins": getattr(clan, 'war_wins', 0),
            "location": getattr(clan.location, 'name', 'N/A') if hasattr(clan, 'location') and clan.location else 'N/A',
            "type": str(getattr(clan, 'type', 'N/A')).capitalize(),
            "badge_url": getattr(clan.badge, 'url', None) if hasattr(clan, 'badge') else None,
            "version": BOT_VERSION,
            "capital_league": capital_league_name,
            "capital_districts": [{"name": d.name, "level": d.level} for d in clan.capital_districts] if hasattr(clan, 'capital_districts') else []
        }

    async def fetch_current_war_details_for_web(self, force_api_call=False):
        key = 'war_details'
        if not force_api_call:
            now = datetime.datetime.now()
            if key in self.web_api_cache and (now - self.web_api_cache[key]["timestamp"]).total_seconds() < self.WEB_API_CACHE_DURATION_SECONDS:
                return self.web_api_cache[key]["data"]

        try:
            war = await self.api_client.get_current_war(self.clan_tag)
            if not war:
                 return {"error": "Nenhuma guerra para detalhar."}

            if war.state == "notInWar":
                return {"error": "Nenhuma guerra para detalhar."}

            if not war.clan or not war.opponent: return {"error": "Dados da guerra incompletos."}
            
            prediction_data = await self.war_prediction_system.predict_war_outcome(war, self.clan_tag)
            our_clan, opp_clan = (war.clan, war.opponent) if war.clan.tag == self.clan_tag else (war.opponent, war.clan)

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
            
            response_data = {
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
                    "is_cwl": war.is_cwl
                },
                "all_attacks": all_attacks_data,
                "our_clan_members_in_war": get_team_details(our_clan, war),
                "opponent_clan_members_in_war": get_team_details(opp_clan, war),
                "prediction": prediction_data
            }
            if not force_api_call:
                self.web_api_cache[key] = {"data": response_data, "timestamp": datetime.datetime.now()}
            return response_data
            
        except (coc.NotFound, coc.PrivateWarLog):
            return {"error": "Nenhuma guerra para detalhar."}
        except Exception as e:
            logger.error(f"Erro em fetch_current_war_details_for_web: {e}", exc_info=True)
            return {"error": "Erro interno ao processar dados da guerra."}
            
    async def fetch_clan_members_for_web(self):
        clan = await self.get_clan_data_with_cache(self.clan_tag)
        if not clan: return {"error": "Não foi possível carregar os dados do clã."}
        db_cog = self.get_cog("Banco de Dados")
        player_notes = await db_cog.load_player_notes_from_db() if db_cog else {}
        members_list = []
        for member in clan.members:
            note_data = player_notes.get(member.tag, {})
            members_list.append({
                "tag": member.tag, "name": member.name, "town_hall": member.town_hall,
                "league": member.league.name if member.league else "Sem Liga",
                "trophies": member.trophies, "role": member.role.name.capitalize() if member.role else "Membro",
                "donations": member.donations, "received": member.received,
                "note": note_data.get("text", ""), 
                "note_priority": note_data.get("priority", "none"),
                "cwl_status": note_data.get("cwl_status", "active")
            })
        role_order = {"Leader": 0, "Co-leader": 1, "Admin": 2, "Member": 3}
        sorted_members = sorted(members_list, key=lambda m: (role_order.get(m["role"], 4), -m["trophies"]))
        return {"clan_name": clan.name, "members": sorted_members, "version": BOT_VERSION}

    async def fetch_missed_attacks_history_for_web(self):
        if self.db is None: return {"error": "Histórico indisponível."}
        clan = await self.get_clan_data_with_cache(self.clan_tag)
        if not clan: return {"error": "Não foi possível carregar os dados do clã para o histórico."}
        log_cursor = self.db.war_history.find({}).sort("war_data.end_time_iso", DESCENDING)
        wars_with_missed_attacks = []
        is_first_war = True
        async for war_doc in log_cursor:
            war_data = war_doc.get("war_data", {})
            our_members_in_war = war_doc.get("our_clan_members_in_war", [])
            missed_attacks_members = []
            attacks_per_member = war_data.get("attacks_per_member", 2)
            for member in our_members_in_war:
                attacks_made = len(member.get("attacks_made", []))
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
                    "end_date": end_time_dt.astimezone(self.timezone).strftime('%d/%m/%y'),
                    "missed_attacks_members": missed_attacks_members, "is_latest": is_first_war
                })
                is_first_war = False
        return {"clan_name": clan.name, "wars_with_missed_attacks": wars_with_missed_attacks}

    async def fetch_war_log_for_web(self):
        if self.db is None: return {"error": "Histórico indisponível."}
        log_cursor = self.db.war_history.find({}, {"war_data": 1}).sort("war_data.end_time_iso", DESCENDING).limit(9)
        entries = []
        async for war_doc in log_cursor:
            war_data = war_doc.get("war_data", {})
            if war_data.get("end_time_iso"):
                end_time_dt = datetime.datetime.fromisoformat(war_data.get("end_time_iso"))
                result = "Vitória" if war_data.get("clan_stars", 0) > war_data.get("opponent_stars", 0) else "Derrota" if war_data.get("clan_stars", 0) < war_data.get("opponent_stars", 0) else "Empate"
                entries.append({
                    "end_time_iso": war_data.get("end_time_iso"), "end_time_formatted": end_time_dt.astimezone(self.timezone).strftime('%d/%m/%y %H:%M'),
                    "opponent_name": war_data.get("opponent_name"), "opponent_badge_url": war_data.get("opponent_badge_url"),
                    "clan_stars": war_data.get("clan_stars"), "opponent_stars": war_data.get("opponent_stars"),
                    "result": result, "team_size": war_data.get("team_size"), "is_cwl": war_data.get("is_cwl", False)
                })
        return {"log": entries}

    async def fetch_cwl_info_for_web(self):
        if not self.api_client: return {"error": "API do CoC não iniciada."}
        try:
            cwl_group = await self.api_client.get_league_group(self.clan_tag)
            if not cwl_group: return {"status": "NotInCwl"}
            
            clans_in_group = [{"name": c.name, "tag": c.tag, "level": c.level, "badge_url": c.badge.url} for c in cwl_group.clans]
            rounds_info = []
            
            for i, a_round in enumerate(cwl_group.rounds):
                round_data = {"round_number": i + 1, "wars": []}
                
                # CORREÇÃO: Usar 'war_tags' em vez de iterar diretamente sobre 'a_round'
                for war_tag in a_round.war_tags:
                    # Ignorar tags de guerra vazias, comuns no dia de preparação
                    if war_tag == '#0': continue
                    try:
                        # Usamos get_league_war que é o método correto para CWL
                        war = await self.api_client.get_league_war(war_tag)
                        if war:
                            round_data["wars"].append({
                                "war_tag": war_tag, "clan_name": war.clan.name, "clan_badge_url": war.clan.badge.url, "clan_stars": war.clan.stars,
                                "opponent_name": war.opponent.name, "opponent_badge_url": war.opponent.badge.url, "opponent_stars": war.opponent.stars,
                                **format_war_time_details(war, datetime.datetime.now(pytz.utc))
                            })
                    except Exception as e: 
                        logger.warning(f"Não foi possível buscar a guerra da CWL {war_tag}: {e}")
                rounds_info.append(round_data)

            return {"status": "InCwl", "season": cwl_group.season, "state": str(cwl_group.state).capitalize(), "clans_in_group": clans_in_group, "rounds": rounds_info}
        except coc.NotFound: 
            return {"status": "NotInCwl"}
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar dados da CWL: {e}", exc_info=True)
            return {"status": "Error", "error": "Erro ao buscar dados da CWL."}


    async def fetch_highlights_for_web(self):
        clan = await self.get_clan_data_with_cache(self.clan_tag)
        if not clan: return {"error": "Não foi possível carregar destaques."}
        top_donors_data = [{"name": m.name, "donations": m.donations, "town_hall": m.town_hall} for m in sorted(clan.members, key=lambda m: m.donations, reverse=True)[:3]]
        war_heroes, war_end_date_str = [], ""
        if self.db is not None:
            latest_war_doc = await self.db.war_history.find_one({}, sort=[("war_data.end_time_iso", DESCENDING)])
            if latest_war_doc:
                from cogs.post_war_analysis import _calculate_post_war_stats
                analysis = _calculate_post_war_stats(latest_war_doc)
                war_heroes = analysis.get("war_heroes", [])
                if latest_war_doc.get("war_data", {}).get("end_time_iso"):
                    end_time = datetime.datetime.fromisoformat(latest_war_doc["war_data"]["end_time_iso"])
                    war_end_date_str = end_time.astimezone(self.timezone).strftime('%d/%m')
        active_members = sorted(clan.members, key=lambda m: m.donations, reverse=True)[:10]
        chart_data = {"labels": [m.name for m in active_members], "donations": [m.donations for m in active_members], "received": [m.received for m in active_members]}
        return {"top_donors": top_donors_data, "war_heroes": war_heroes, "activity_chart_data": chart_data, "clan_name": clan.name, "war_date": war_end_date_str}

async def setup_web_server(bot_instance: ClashGeniusBot):
    app = web.Application()

    async def get_cached_web_data(key: str, func, *args, **kwargs):
        now = datetime.datetime.now()
        if not kwargs.get('force_api_call', False) and key in bot_instance.web_api_cache and (now - bot_instance.web_api_cache[key]["timestamp"]).total_seconds() < bot_instance.WEB_API_CACHE_DURATION_SECONDS:
            return bot_instance.web_api_cache[key]["data"]
        
        if not bot_instance.coc_client_ready.is_set():
            return {"error": "O bot ainda está a iniciar... Por favor, aguarde.", "status_code": 503}

        data = await func(*args, **kwargs)
        if not kwargs.get('force_api_call', False):
            bot_instance.web_api_cache[key] = {"data": data, "timestamp": now}
        return data

    async def handle_web_response(request, key, func, *args, **kwargs):
        data = await get_cached_web_data(key, func, *args, **kwargs)
        status_code = data.pop("status_code", 200) if isinstance(data, dict) else 200
        return web.json_response(data, status=status_code)

    # --- Handlers da API ---
    async def api_clan_handler(request): return await handle_web_response(request, 'clan', bot_instance.fetch_clan_info_for_web)
    async def api_members_handler(request): return await handle_web_response(request, 'members', bot_instance.fetch_clan_members_for_web)
    async def api_current_war_details_handler(request): return await handle_web_response(request, 'war_details', bot_instance.fetch_current_war_details_for_web)
    async def api_missed_attacks_history_handler(request): return await handle_web_response(request, 'missed_attacks', bot_instance.fetch_missed_attacks_history_for_web)
    async def api_war_log_handler(request): return await handle_web_response(request, 'war_log', bot_instance.fetch_war_log_for_web)
    async def api_cwl_info_handler(request): return await handle_web_response(request, 'cwl', bot_instance.fetch_cwl_info_for_web)
    async def api_highlights_handler(request): return await handle_web_response(request, 'highlights', bot_instance.fetch_highlights_for_web)
    
    async def api_war_advisor_plan_handler(request):
        if not bot_instance.coc_client_ready.is_set():
            return web.json_response({"success": False, "error": "Bot a iniciar."}, status=503)
        try:
            advisor_cog = bot_instance.get_cog("Conselheiro de Guerra IA")
            if not advisor_cog or not hasattr(advisor_cog, 'war_advisor'):
                 return web.json_response({"success": False, "error": "Módulo do conselheiro não carregado."}, status=500)

            war = await bot_instance.api_client.get_current_war(bot_instance.clan_tag)
            if not war:
                return web.json_response({"success": False, "error": "Nenhuma guerra ativa."})

            prediction_data = await bot_instance.war_prediction_system.predict_war_outcome(war, bot_instance.clan_tag)
            
            plan = advisor_cog.war_advisor.create_war_plan(war, bot_instance.clan_tag, prediction_data)
            
            if war and war.state == 'inWar' and hasattr(war, 'start_time') and war.start_time.time:
                start_time_utc = war.start_time.time.replace(tzinfo=pytz.utc)
                phase_2_start_time = start_time_utc + datetime.timedelta(hours=12)
                plan['phase_2_start_time_iso'] = phase_2_start_time.isoformat()

            return web.json_response(plan)
        except (coc.NotFound, coc.PrivateWarLog):
            return web.json_response({"success": False, "error": "Nenhuma guerra ativa."})
        except Exception as e:
            logger.error(f"Erro no endpoint do war_advisor: {e}", exc_info=True)
            return web.json_response({"success": False, "error": "Erro interno."}, status=500)

    async def api_save_player_note_handler(request):
        db_cog = bot_instance.get_cog("Banco de Dados")
        if not db_cog: return web.json_response({"error": "Cog de DB não encontrado."}, status=500)
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        data = await request.json()
        await db_cog.save_player_note_to_db(player_tag, data.get('text', ''), data.get('priority', 'none'))
        bot_instance.web_api_cache.pop('members', None)
        return web.Response(status=204)

    async def api_save_cwl_player_status_handler(request):
        db_cog = bot_instance.get_cog("Banco de Dados")
        if not db_cog: return web.json_response({"error": "Cog de DB não encontrado."}, status=500)
        
        try:
            player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
            data = await request.json()
            status = data.get('status')

            if status not in ['active', 'backup']:
                return web.json_response({"error": "Status inválido."}, status=400)

            await db_cog.save_cwl_player_status_to_db(player_tag, status)
            
            # Limpa caches relevantes para forçar a atualização
            bot_instance.web_api_cache.pop('members', None)
            bot_instance.web_api_cache.pop('cwl_plan', None)
            
            return web.json_response({"success": True, "message": "Status salvo com sucesso."})
        except Exception as e:
            logger.error(f"Erro ao salvar status da CWL: {e}", exc_info=True)
            return web.json_response({"error": "Erro interno do servidor."}, status=500)


    async def api_historic_war_handler(request):
        if bot_instance.db is None: return web.json_response({"error": "DB não conectado."}, status=503)
        war_doc = await bot_instance.db.war_history.find_one({"_id": request.match_info['war_id']})
        return web.json_response(war_doc, dumps=lambda v: json.dumps(v, default=str)) if war_doc else web.json_response({"error": "Guerra não encontrada."}, status=404)

    async def api_member_profile_handler(request):
        profile_cog = bot_instance.get_cog("Perfis de Membros")
        if not profile_cog:
            return web.json_response({"error": "Módulo de perfis não carregado."}, status=500)
        
        try:
            player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
            profile_data = await profile_cog.fetch_player_profile_data(player_tag)
            
            if "error" in profile_data:
                return web.json_response(profile_data, status=404)
            
            return web.json_response(profile_data)
        except Exception as e:
            logger.error(f"Erro na API de perfil de membro: {e}", exc_info=True)
            return web.json_response({"error": "Erro interno do servidor."}, status=500)

    async def api_cwl_generate_plan_handler(request):
        cwl_cog = bot_instance.get_cog("Planeador de CWL")
        if not cwl_cog:
            return web.json_response({"error": "O módulo do planeador CWL não está ativo."}, status=500)
        bot_instance.web_api_cache.pop('cwl_plan', None)
        plan = await cwl_cog.generate_rotation_plan()
        return web.json_response(plan)

    async def api_cwl_inactivity_check_handler(request):
        cwl_cog = bot_instance.get_cog("Planeador de CWL")
        if not cwl_cog: return web.json_response({"error": "O módulo do planeador CWL não está ativo."}, status=500)
        alert = {"alert": None} 
        return web.json_response(alert)

    # --- Rotas da API ---
    app.router.add_get("/api/clan", api_clan_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/current_war_details", api_current_war_details_handler)
    app.router.add_get("/api/missed_attacks_history", api_missed_attacks_history_handler)
    app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler)
    app.router.add_get("/api/highlights", api_highlights_handler)
    app.router.add_get("/api/war_advisor_plan", api_war_advisor_plan_handler)
    app.router.add_post("/api/notes/{player_tag:.*}", api_save_player_note_handler)
    app.router.add_post("/api/cwl/player_status/{player_tag:.*}", api_save_cwl_player_status_handler)
    app.router.add_get("/api/war_history/{war_id}", api_historic_war_handler)
    app.router.add_get("/api/player_profile/{player_tag:.*}", api_member_profile_handler)
    app.router.add_get("/api/status", lambda r: web.json_response({"status": "online", "version": BOT_VERSION}))
    app.router.add_post("/api/cwl/generate_plan", api_cwl_generate_plan_handler)
    app.router.add_get("/api/cwl/inactivity_check", api_cwl_inactivity_check_handler)
    
    # --- Rotas Estáticas e Principais ---
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    
    async def painel_handler(request):
        session = await get_session(request)
        is_admin = session.get('admin', False)
        
        # Se o modo manutenção estiver ativo E o usuário NÃO for admin, mostra a página de manutenção
        if bot_instance.maintenance_mode and not is_admin:
            return web.FileResponse(os.path.join(static_dir, "maintenance.html"))
        
        # Caso contrário, mostra o painel normal
        return web.FileResponse(os.path.join(static_dir, "painel.html"))

    app.router.add_static('/static/', path=static_dir, name='static')
    app.router.add_get("/painel", painel_handler)
    app.router.add_get("/", lambda r: web.Response(text=f"Bot running! v{BOT_VERSION}"))
    
    # --- CÓDIGO DO ADMIN PANEL ---
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
        if action == 'toggle_maintenance':
            bot_instance.maintenance_mode = not bot_instance.maintenance_mode
            status_str = "ATIVADO" if bot_instance.maintenance_mode else "DESATIVADO"
            embed = discord.Embed(title=f"🚨 Modo Manutenção {status_str} 🚨", color=discord.Color.orange() if bot_instance.maintenance_mode else discord.Color.green())
            channel = bot_instance.get_channel(bot_instance.channel_id)
            if channel: await channel.send(embed=embed)
            return web.json_response({"status": "success", "maintenance_mode": bot_instance.maintenance_mode})
        elif action == 'send_test_embed':
            embed = discord.Embed(title="✅ Mensagem de Teste", description="Comunicação OK!", color=discord.Color.blue())
            channel = bot_instance.get_channel(bot_instance.channel_id)
            if channel: await channel.send(embed=embed)
            return web.json_response({"status": "success"})
        elif action == 'get_status':
            return web.json_response({"status": "ok", "maintenance_mode": bot_instance.maintenance_mode, "version": BOT_VERSION})

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

async def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    bot = ClashGeniusBot(command_prefix="!", intents=intents)
    try:
        await bot.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot desligado manualmente.")
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    asyncio.run(main())

