# -*- coding: utf-8 -*-
# Versão 18.4 - Painel Web SPA (Correção ImportError LeagueGroup/LeagueWar para coc.py 3.9.1)

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
# Tentando importar LeagueGroup e LeagueWar diretamente do coc principal para a v3.9.1
from coc import ClanWar, Player, Clan, WarAttack, Timestamp, ClanMember, LeagueGroup, LeagueWar # <<< IMPORTAÇÃO CORRIGIDA/REVERTIDA

import pytz
from dotenv import load_dotenv

# Configure logging
# ... (o resto da configuração de logging como antes) ...
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
# ... (o resto do carregamento de .env como antes) ...
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


BOT_VERSION = "18.4" # << VERSÃO ATUALIZADA
# ... (o restante do seu arquivo Python, incluindo reported_war_ends, clan_event_log, add_event_to_log, intents,
#      definição do bot, todas as funções auxiliares, funções de guerra, event handlers, tasks,
#      comandos slash, e toda a seção do PAINEL WEB, permanecem EXATAMENTE como na versão 18.2
#      que te enviei, onde corrigimos a sintaxe dos decoradores. A ÚNICA mudança é a linha de importação
#      para LeagueGroup e LeagueWar.)

# !!! IMPORTANTE !!!
# O restante do código (aproximadamente da linha 45 até o final do arquivo na versão 18.2)
# deve ser colado aqui. Para não tornar esta resposta excessivamente longa repetindo
# todo o código novamente, estou apenas mostrando a parte inicial com a correção da importação.
#
# Certifique-se de que você está usando o corpo completo do arquivo da versão 18.2
# (aquela que corrigiu a sintaxe dos decoradores dos eventos) e apenas altere a linha de importação
# de LeagueGroup e LeagueWar como mostrado acima.

# Exemplo de onde as classes são usadas (não precisa mudar se importadas diretamente):
# async def fetch_cwl_info_for_web_api():
#    # ...
#    group: LeagueGroup = await bot.coc_client.get_league_group(CLAN_TAG)
#    # ...
#    war: LeagueWar = await group.get_league_war(war_tag)
#    # ...

# (COLE O RESTANTE DO SEU CÓDIGO DA VERSÃO 18.2 AQUI,
#  DA LINHA ~45 (após BOT_VERSION) ATÉ O FINAL DO ARQUIVO)
# ... (todo o resto do código como na versão 18.2) ...

# Para garantir que você tenha a seção do painel web correta, aqui está ela novamente,
# mas lembre-se que todo o código entre BOT_VERSION e esta seção também precisa estar presente.

# ============================================================================ #
# ==================== PAINEL WEB - LÓGICA E ENDPOINTS API ==================== #
# ============================================================================ #
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
    current_war: Optional[Union[ClanWar, coc.WarLogEntry]] = None
    war_type_description = "Nenhuma guerra"
    try:
        lg: LeagueGroup = await bot.coc_client.get_league_group(CLAN_TAG) # LeagueGroup usada diretamente
        if lg and lg.state != "notInWar" and lg.rounds:
            for i, war_tags in reversed(list(enumerate(lg.rounds))):
                for tag in war_tags:
                    try:
                        war: LeagueWar = await lg.get_league_war(tag) # LeagueWar usada diretamente
                        if war and (war.clan.tag == CLAN_TAG or war.opponent.tag == CLAN_TAG):
                            if war.state == "inWar" or war.state == "preparation":
                                if war.opponent.tag == CLAN_TAG: war.clan, war.opponent = war.opponent, war.clan
                                current_war = war; war_type_description = f"Liga (Rodada {i+1})"; break
                    except: continue
                if current_war: break
    except coc.NotFound: pass # É normal não estar em CWL
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
    elif isinstance(current_war, coc.WarLogEntry):
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
        group: LeagueGroup = await bot.coc_client.get_league_group(CLAN_TAG) # LeagueGroup usada diretamente
        if not group or group.state == "notInWar": return {"status": "notInWar", "message": "Clã não está em CWL."}
        rounds_data = []
        for i, round_war_tags in enumerate(group.rounds):
            round_info = {"round_number": i + 1, "wars": []}
            for war_tag in round_war_tags:
                try:
                    war: LeagueWar = await group.get_league_war(war_tag) # LeagueWar usada diretamente
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
        if hasattr(group, 'clans') and group.clans:
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
    logger.info("Executando setup_hook...")
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
