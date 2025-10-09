# -*- coding: utf-8 -*-
# Versão 20.2.04-Hotfix-Integrity

import os
import logging
import asyncio
import datetime
from typing import Dict, Any, Optional

import discord
from discord.ext import commands
import coc
import pytz
from dotenv import load_dotenv
import motor.motor_asyncio
from pymongo.uri_parser import parse_uri
from aiohttp import web
from aiohttp_session import setup as setup_session, get_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
import base64
from cryptography.fernet import Fernet
import json

from formatting import format_war_time_details
from war_predictor import WarPredictionSystemV3

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("clash_genius_bot")

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

BOT_VERSION = "20.2.04-Hotfix-Integrity"
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
        self.db = None
        self.mongo_client = None
        self.clan_cache: Dict[str, Dict[str, Any]] = {}
        self.CACHE_DURATION_SECONDS = 300
        self.web_api_cache: Dict[str, Dict[str, Any]] = {}
        self.WEB_API_CACHE_DURATION_SECONDS = 45
        self.db_ready = asyncio.Event()
        self.coc_client_ready = asyncio.Event()
        self.processed_war_ids = set()

    async def setup_hook(self) -> None:
        logger.info("Executando setup_hook...")
        if MONGO_DB_URL:
            try:
                db_name = parse_uri(MONGO_DB_URL).get('database', 'genius_db')
                self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)
                self.db = self.mongo_client[db_name]
                logger.info(f"Conectado ao MongoDB: {db_name}")
                await self.load_initial_state_from_db()
                self.db_ready.set()
            except Exception as e:
                logger.error(f"Falha ao conectar com o MongoDB: {e}", exc_info=True)
        else:
            logger.warning("URL do MongoDB não fornecida. Recursos de persistência desativados.")
            self.db_ready.set()

        self.war_prediction_system = WarPredictionSystemV3(db_connection=self.db)
        await self.war_prediction_system.initialize_system()
        
        logger.info("Carregando cogs...")
        cog_files = [
            'events_cog', 'tasks_cog', 'database_cog', 'general_cog', 
            'cwl_planner_cog', 'clan_games_cog', 'war_advisor_cog', 'profile_cog',
            'maintenance_cog', 'web_api_cog'
        ]
        for cog_name in cog_files:
            try:
                await self.load_extension(f'cogs.{cog_name}')
                logger.info(f"Cog '{cog_name}' carregado com sucesso.")
            except Exception as e:
                logger.error(f"Falha ao carregar o cog '{cog_name}'. Erro: {e}", exc_info=True)

        self.loop.create_task(self.coc_login_task())
        self.loop.create_task(setup_web_server(self))
        
    async def load_initial_state_from_db(self):
        if self.db is None: return
        config = await self.db.system_config.find_one({"_id": "maintenance_mode"})
        if config:
            self.maintenance_mode = config.get("enabled", False)
            logger.info(f"Modo manutenção carregado do DB. Estado: {'ATIVADO' if self.maintenance_mode else 'DESATIVADO'}")
        
        processed_wars_cursor = self.db.war_history.find({}, {"_id": 1})
        self.processed_war_ids = {doc["_id"] async for doc in processed_wars_cursor}
        logger.info(f"Carregados {len(self.processed_war_ids)} IDs de guerras já processadas do histórico.")

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

    # CORREÇÃO: Função movida de volta para a classe principal do bot para ser acessível a todos os cogs.
    async def format_war_details_for_web(self, war: coc.ClanWar) -> Dict[str, Any]:
        try:
            if not war or not war.clan or not war.opponent:
                return {"error": "Dados da guerra incompletos."}

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

            our_attacks = [a for a in war.attacks if a and getattr(a.attacker, 'clan', None) and a.attacker.clan.tag == our_clan.tag]
            opp_attacks = [a for a in war.attacks if a and getattr(a.attacker, 'clan', None) and a.attacker.clan.tag == opp_clan.tag]
            
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
                    "is_cwl": war.is_cwl
                },
                "all_attacks": all_attacks_data,
                "our_clan_members_in_war": get_team_details(our_clan, war),
                "opponent_clan_members_in_war": get_team_details(opp_clan, war),
                "prediction": prediction_data
            }
        except Exception as e:
            logger.error(f"Erro ao formatar detalhes da guerra: {e}", exc_info=True)
            return {"error": "Erro interno ao formatar dados da guerra."}


async def setup_web_server(bot_instance: ClashGeniusBot):
    app = web.Application()
    
    await bot_instance.wait_until_ready()
    web_api_cog = bot_instance.get_cog("Web API")
    db_cog = bot_instance.get_cog("Banco de Dados")
    profile_cog = bot_instance.get_cog("Perfis de Membros")
    cwl_cog = bot_instance.get_cog("Planeador de CWL")
    maintenance_cog = bot_instance.get_cog("Manutenção do Sistema")
    war_advisor_cog = bot_instance.get_cog("Conselheiro de Guerra IA")

    if not all([web_api_cog, db_cog, profile_cog, cwl_cog, maintenance_cog, war_advisor_cog]):
        logger.critical("Um ou mais cogs essenciais para o servidor web não foram carregados. O servidor não pode iniciar.")
        return

    async def handle_web_response(request, key, func, *args, **kwargs):
        now = datetime.datetime.now()
        if not kwargs.get('force_api_call', False) and key in bot_instance.web_api_cache and (now - bot_instance.web_api_cache[key]["timestamp"]).total_seconds() < bot_instance.WEB_API_CACHE_DURATION_SECONDS:
            return web.json_response(bot_instance.web_api_cache[key]["data"])
        
        if not bot_instance.coc_client_ready.is_set():
            return web.json_response({"error": "O bot ainda está a iniciar... Por favor, aguarde."}, status=503)

        data = await func(*args, **kwargs)
        if 'error' not in data and not kwargs.get('force_api_call', False):
             bot_instance.web_api_cache[key] = {"data": data, "timestamp": now}
        return web.json_response(data)

    # Handlers da API
    async def api_clan_handler(r): return await handle_web_response(r, 'clan', web_api_cog.fetch_clan_info_for_web)
    async def api_members_handler(r): return await handle_web_response(r, 'members', web_api_cog.fetch_clan_members_for_web)
    async def api_current_war_details_handler(r): return await handle_web_response(r, 'war_details', web_api_cog.fetch_current_war_details_for_web)
    async def api_missed_attacks_history_handler(r): return await handle_web_response(r, 'missed_attacks', web_api_cog.fetch_missed_attacks_history_for_web)
    async def api_war_log_handler(r): return await handle_web_response(r, 'war_log', web_api_cog.fetch_war_log_for_web)
    async def api_cwl_info_handler(r): return await handle_web_response(r, 'cwl', web_api_cog.fetch_cwl_info_for_web)
    async def api_highlights_handler(r): return await handle_web_response(r, 'highlights', web_api_cog.fetch_highlights_for_web)

    async def api_save_player_note_handler(request):
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        data = await request.json()
        await db_cog.save_player_note_to_db(player_tag, data.get('text', ''), data.get('priority', 'none'))
        bot_instance.web_api_cache.pop('members', None)
        return web.Response(status=204)

    async def api_historic_war_handler(request):
        war_id = request.match_info['war_id']
        war_doc = await bot_instance.db.war_history.find_one({"_id": war_id})
        return web.json_response(war_doc, dumps=lambda v: json.dumps(v, default=str)) if war_doc else web.json_response({"error": "Guerra não encontrada."}, status=404)

    async def api_member_profile_handler(request):
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        profile_data = await profile_cog.fetch_player_profile_data(player_tag)
        return web.json_response(profile_data, status=404 if "error" in profile_data else 200)

    # CORREÇÃO: Adicionando a rota do planejador de CWL que estava faltando
    async def api_cwl_generate_plan_handler(request):
        bot_instance.web_api_cache.pop('cwl_plan', None)
        plan = await cwl_cog.generate_rotation_plan()
        return web.json_response(plan)

    # CORREÇÃO: Adicionando a rota do conselheiro de guerra que estava faltando
    async def api_war_advisor_plan_handler(request):
        try:
            war = await bot_instance.api_client.get_current_war(bot_instance.clan_tag)
            prediction_data = await bot_instance.war_prediction_system.predict_war_outcome(war, bot_instance.clan_tag)
            plan = war_advisor_cog.war_advisor.create_war_plan(war, bot_instance.clan_tag, prediction_data)
            return web.json_response(plan)
        except (coc.NotFound, coc.PrivateWarLog):
            return web.json_response({"success": False, "error": "Nenhuma guerra ativa."}, status=404) # HTTP 404
        except Exception as e:
            logger.error(f"Erro no endpoint do war_advisor: {e}", exc_info=True)
            return web.json_response({"success": False, "error": "Erro interno."}, status=500)


    app.router.add_get("/api/clan", api_clan_handler)
    app.router.add_get("/api/members", api_members_handler)
    app.router.add_get("/api/current_war_details", api_current_war_details_handler)
    app.router.add_get("/api/missed_attacks_history", api_missed_attacks_history_handler)
    app.router.add_get("/api/war_log", api_war_log_handler)
    app.router.add_get("/api/cwl_info", api_cwl_info_handler)
    app.router.add_get("/api/highlights", api_highlights_handler)
    app.router.add_post("/api/notes/{player_tag:.*}", api_save_player_note_handler)
    app.router.add_get("/api/war_history/{war_id:.*}", api_historic_war_handler)
    app.router.add_get("/api/player_profile/{player_tag:.*}", api_member_profile_handler)
    app.router.add_post("/api/cwl/generate_plan", api_cwl_generate_plan_handler)
    app.router.add_get("/api/war_advisor_plan", api_war_advisor_plan_handler)
    
    static_dir = os.path.join(os.path.dirname(__file__), "static")

    # --- ADMIN PANEL ROUTES ---
    async def admin_login_page(r): return web.FileResponse(os.path.join(static_dir, "admin_login.html"))
    async def admin_panel_page(r):
        session = await get_session(r)
        if not session.get('admin'):
            return web.HTTPFound('/admin')
        return web.FileResponse(os.path.join(static_dir, "admin_panel.html"))

    async def admin_login_handler(r):
        data = await r.post()
        if data.get('password') == ADMIN_PASSWORD:
            session = await get_session(r)
            session['admin'] = True
            return web.HTTPFound('/admin/panel')
        return web.HTTPFound('/admin?error=1')

    async def admin_logout_handler(r):
        session = await get_session(r)
        session.pop('admin', None)
        return web.HTTPFound('/admin')
    
    async def admin_api_handler(request):
        session = await get_session(request)
        if not session.get('admin'):
            return web.json_response({"status": "unauthorized"}, status=403)
        
        action = request.match_info.get('action')
        if not maintenance_cog:
            return web.json_response({"status": "error", "message": "Maintenance cog not found"}, status=500)

        if action == 'toggle_maintenance':
            return await maintenance_cog.toggle_maintenance_mode_web()
        elif action == 'send_test_embed':
            return await maintenance_cog.send_test_embed_web()
        elif action == 'get_status':
            return web.json_response({
                "status": "ok", 
                "maintenance_mode": bot_instance.maintenance_mode, 
                "version": BOT_VERSION
            })
        return web.json_response({"status": "error", "message": "Invalid action"}, status=400)


    app.router.add_get("/admin", admin_login_page)
    app.router.add_post("/admin/login", admin_login_handler)
    app.router.add_get("/admin/logout", admin_logout_handler)
    app.router.add_get("/admin/panel", admin_panel_page)
    app.router.add_post("/admin/api/{action}", admin_api_handler)
    app.router.add_get("/api/admin/status", lambda r: admin_api_handler(r, 'get_status')) # Ajuste para GET
    
    async def painel_handler(request):
        session = await get_session(request)
        is_admin = session.get('admin', False)
        if bot_instance.maintenance_mode and not is_admin:
            return web.FileResponse(os.path.join(static_dir, "maintenance.html"))
        return web.FileResponse(os.path.join(static_dir, "painel.html"))

    app.router.add_static('/static/', path=static_dir, name='static')
    app.router.add_get("/painel", painel_handler)
    app.router.add_get("/", lambda r: web.Response(text=f"Bot running! v{BOT_VERSION}"))
    
    secret_key = base64.urlsafe_b64decode(Fernet.generate_key() if not FERNET_KEY else FERNET_KEY.encode())
    setup_session(app, EncryptedCookieStorage(secret_key))

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

