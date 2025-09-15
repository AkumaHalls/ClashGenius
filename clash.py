# -*- coding: utf-8 -*-
# Versão 20.1.90-STATIC-FIX

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
BOT_VERSION = "20.1.90-STATIC-FIX"
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

    async def get_clan_data_with_cache(self, tag: str) -> Optional[coc.Clan]:
        if not self.api_client: return None
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

    async def setup_hook(self) -> None:
        logger.info("Executando setup_hook...")

        if MONGO_DB_URL:
            try:
                db_name = parse_uri(MONGO_DB_URL).get('database', 'genius_db')
                self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)
                self.db = self.mongo_client[db_name]
                logger.info(f"Conectado ao MongoDB: {db_name}")
            except Exception as e:
                logger.error(f"Falha ao conectar com o MongoDB: {e}", exc_info=True)
        else:
            logger.warning("URL do MongoDB não fornecida.")

        self.war_prediction_system = WarPredictionSystemV3(db_connection=self.db)
        await self.war_prediction_system.initialize_system()
        
        try:
            self.api_client = coc.Client()
            await self.api_client.login(self.coc_email, self.coc_password)
            logger.info("Login no coc.Client (api_client) bem-sucedido.")
        except Exception as e:
            logger.critical(f"Falha CRÍTICA no login do coc.Client: {e}", exc_info=True)
        
        logger.info("Carregando cogs...")
        for filename in os.listdir('./cogs'):
            if filename.endswith('_cog.py'):
                cog_name = filename[:-3]
                try:
                    await self.load_extension(f'cogs.{cog_name}')
                    logger.info(f"Cog '{cog_name}' carregado com sucesso.")
                except Exception as e:
                    logger.error(f"Falha ao carregar o cog '{cog_name}'. Erro: {e}", exc_info=True)

        self.loop.create_task(setup_web_server(self))

    async def on_ready(self):
        logger.info(f'Bot {self.user.name} está online e pronto!')

    async def close(self):
        logger.info("Fechando conexões...")
        if self.api_client:
            await self.api_client.close()
        if self.mongo_client:
            self.mongo_client.close()
        await super().close()

    # MÉTODOS DE BUSCA DE DADOS (AGORA PARTE DA CLASSE)
    async def fetch_clan_info_for_web(self):
        clan = await self.get_clan_data_with_cache(self.clan_tag)
        if not clan: return {"error": "Não foi possível carregar os dados do clã."}
        return {
            "name": getattr(clan, 'name', 'N/A'), "tag": getattr(clan, 'tag', 'N/A'),
            "level": getattr(clan, 'level', 0), "points": getattr(clan, 'points', 0),
            "capital_points": getattr(clan, 'capital_points', 0), "member_count": getattr(clan, 'member_count', 0),
            "description": getattr(clan, 'description', ''), "war_wins": getattr(clan, 'war_wins', 0),
            "location": getattr(clan.location, 'name', 'N/A') if hasattr(clan, 'location') and clan.location else 'N/A',
            "type": str(getattr(clan, 'type', 'N/A')).capitalize(),
            "badge_url": getattr(clan.badge, 'url', None) if hasattr(clan, 'badge') else None,
            "version": BOT_VERSION
        }

    async def fetch_current_war_details_for_web(self):
        try:
            war = await self.api_client.get_current_war(self.clan_tag)
            if not war or war.state == "notInWar": return {"error": "Nenhuma guerra para detalhar."}
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
                    "opponent_avg_stars": f"{opp_clan.stars / len(opp_attacks):.2f}" if opp_attacks else "0.00"
                },
                "all_attacks": all_attacks_data,
                "our_clan_members_in_war": get_team_details(our_clan, war),
                "opponent_clan_members_in_war": get_team_details(opp_clan, war),
                "prediction": prediction_data
            }
        except (coc.NotFound, coc.PrivateWarLog):
            return {"error": "Nenhuma guerra para detalhar."}
        except Exception as e:
            logger.error(f"Erro em fetch_current_war_details_for_web: {e}", exc_info=True)
            return {"error": "Erro interno ao processar dados da guerra."}
            
# --- SERVIDOR WEB ---
async def setup_web_server(bot_instance: ClashGeniusBot):
    app = web.Application()

    async def get_cached_web_data(key: str, func, *args):
        now = datetime.datetime.now()
        if key in bot_instance.web_api_cache and (now - bot_instance.web_api_cache[key]["timestamp"]).total_seconds() < bot_instance.WEB_API_CACHE_DURATION_SECONDS:
            return bot_instance.web_api_cache[key]["data"]
        data = await func(*args)
        bot_instance.web_api_cache[key] = {"data": data, "timestamp": now}
        return data

    # --- Handlers da API ---
    async def api_clan_handler(request): return web.json_response(await get_cached_web_data('clan', bot_instance.fetch_clan_info_for_web))
    async def api_current_war_details_handler(request): return web.json_response(await get_cached_web_data('war_details', bot_instance.fetch_current_war_details_for_web))
    # Adicione os outros handlers da API aqui, espelhando a estrutura acima
    async def api_members_handler(request): return web.json_response(await get_cached_web_data('members', bot_instance.fetch_clan_members_for_web))
    async def api_missed_attacks_history_handler(request): return web.json_response(await get_cached_web_data('missed_attacks', bot_instance.fetch_missed_attacks_history_for_web))
    async def api_war_log_handler(request): return web.json_response(await get_cached_web_data('war_log', bot_instance.fetch_war_log_for_web))
    async def api_cwl_info_handler(request): return web.json_response(await get_cached_web_data('cwl', bot_instance.fetch_cwl_info_for_web))
    async def api_highlights_handler(request): return web.json_response(await get_cached_web_data('highlights', bot_instance.fetch_highlights_for_web))

    async def api_save_player_note_handler(request):
        db_cog = bot_instance.get_cog("Banco de Dados")
        if not db_cog: return web.json_response({"error": "Cog de DB não encontrado."}, status=500)
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        data = await request.json()
        await db_cog.save_player_note_to_db(player_tag, data.get('text', ''), data.get('priority', 'none'))
        bot_instance.web_api_cache.pop('members', None)
        return web.Response(status=204)

    async def api_historic_war_handler(request):
        if bot_instance.db is None: return web.json_response({"error": "DB não conectado."}, status=503)
        war_doc = await bot_instance.db.war_history.find_one({"_id": request.match_info['war_id']})
        return web.json_response(war_doc, dumps=lambda v: json.dumps(v, default=str)) if war_doc else web.json_response({"error": "Guerra não encontrada."}, status=404)

    async def api_member_profile_handler(request):
        player_tag = coc.utils.correct_tag(request.match_info['player_tag'])
        player_data = await bot_instance.api_client.get_player(player_tag)
        if not player_data: return web.json_response({"error": "Jogador não encontrado."}, status=404)
        trophy_history = []
        if bot_instance.db is not None:
             cursor = bot_instance.db.trophy_history.find({"player_tag": player_tag}).sort("timestamp", DESCENDING).limit(30)
             trophy_history = [{"trophies": doc["trophies"], "timestamp": doc["timestamp"].strftime("%d/%m")} async for doc in cursor]
             trophy_history.reverse()
        profile = {
            "name": player_data.name, "tag": player_data.tag, "town_hall": player_data.town_hall,
            "heroes": [{"name": h.name, "level": h.level, "max_level": h.max_level} for h in player_data.heroes if h.is_home_base],
            "donations": player_data.donations, "received": player_data.received, "trophies": player_data.trophies,
            "league": player_data.league.name if player_data.league else "N/A", "trophy_history": trophy_history
        }
        return web.json_response(profile)

    async def api_cwl_generate_plan_handler(request):
        cwl_cog = bot_instance.get_cog("Planejador de CWL")
        if not cwl_cog: return web.json_response({"error": "O módulo do planejador CWL não está ativo."}, status=500)
        plan = await cwl_cog.generate_rotation_plan()
        return web.json_response(plan)

    async def api_cwl_inactivity_check_handler(request):
        cwl_cog = bot_instance.get_cog("Planejador de CWL")
        if not cwl_cog: return web.json_response({"error": "O módulo do planejador CWL não está ativo."}, status=500)
        alert = await cwl_cog.get_inactivity_alert()
        return web.json_response(alert)

    # --- Rotas da API ---
    app.router.add_get("/api/clan", api_clan_handler)
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
    app.router.add_post("/api/cwl/generate_plan", api_cwl_generate_plan_handler)
    app.router.add_get("/api/cwl/inactivity_check", api_cwl_inactivity_check_handler)

    # --- Rotas Estáticas e Principais ---
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app.router.add_static('/static/', path=static_dir, name='static')
    app.router.add_get("/painel", lambda r: web.FileResponse(os.path.join(static_dir, "painel.html")))
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

