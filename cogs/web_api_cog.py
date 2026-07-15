# -*- coding: utf-8 -*-
import logging
import datetime
import re
import pytz
from typing import Dict, Any

import geniuslib as coc
from geniuslib.formatters import format_th, format_trophies, format_player_brief, format_clan_brief, format_number
from geniuslib.upgrade_tracker import get_th_upgrade_summary
from geniuslib.battlelog_analytics import (
    battle_attack_stats,
    battle_defense_stats,
    battle_loot_summary,
    battle_win_rate,
    battle_consistency_score,
    battle_period_summary,
    league_history_progression,
    decode_army_code,
)
from cogs.post_war_analysis import analyze_war
try:
    from geniuslib.upgrade_tracker import _TH_MAX_LEVELS
    _HAS_TH_TABLE = bool(_TH_MAX_LEVELS.get("building"))
except ImportError:
    _HAS_TH_TABLE = False
from geniuslib.exporter import to_json, to_csv, to_dict
from geniuslib.comparer import compare_players, compare_clans
from discord.ext import commands
from pymongo import DESCENDING

try:
    from formatting import format_war_time_details
except ImportError:
    format_war_time_details = None
    logging.getLogger("web_api_cog").error("Falha ao importar format_war_time_details de formatting")

try:
    from simple_cache import cache
except ImportError:
    cache = None
    logging.getLogger("web_api_cog").warning("simple_cache não disponível")

logger = logging.getLogger("web_api_cog")

class WebApiCog(commands.Cog, name="Web API"):
    """Cog para gerenciar toda a lógica de busca de dados para o painel web."""

    MAX_WAR_HISTORY = 500

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    async def format_war_details_for_web(self, war: coc.ClanWar) -> Dict[str, Any]:
        try:
            if not war or not war.clan or not war.opponent:
                return {"error": "Dados da guerra incompletos."}

            prediction_data = {} 
            if hasattr(self.bot, 'war_prediction_system') and self.bot.war_prediction_system and self.bot.war_prediction_system.is_initialized:
                 prediction_data = await self.bot.war_prediction_system.predict_war_outcome(war, self.bot.clan_tag)

            our_clan, opp_clan = (war.clan, war.opponent) if war.clan.tag == self.bot.clan_tag else (war.opponent, war.clan)

            def get_team_details(team, war_obj):
                if not team or not hasattr(team, 'members'): return []
                details = []
                for m in team.members:
                    if not m: continue
                    attacks_made_formatted = []
                    for a in getattr(m, 'attacks', []):
                         defender_attacked_obj = war_obj.get_member(getattr(a, 'defender_tag', None))
                         defender_attacked_name = getattr(defender_attacked_obj, 'name', getattr(a, 'defender_tag', '?'))
                         defender_attacked_th = getattr(defender_attacked_obj, 'town_hall', 0)
                         attacks_made_formatted.append({
                             "stars": getattr(a,'stars', 0),
                             "destruction": getattr(a,'destruction', 0),
                             "defender_name": defender_attacked_name,
                             "defender_townhall": defender_attacked_th
                         })

                    defenses_received_formatted = []
                    for d in getattr(m, 'defenses', []):
                        attacker_defense_obj = war_obj.get_member(getattr(d, 'attacker_tag', None))
                        attacker_defense_name = getattr(attacker_defense_obj, 'name', getattr(d, 'attacker_tag', '?'))
                        attacker_defense_th = getattr(attacker_defense_obj, 'town_hall', 0)
                        defenses_received_formatted.append({
                            "stars": getattr(d,'stars', 0),
                            "destruction": getattr(d,'destruction', 0),
                            "attacker_name": attacker_defense_name,
                            "attacker_townhall": attacker_defense_th
                        })

                    details.append({
                        "name": getattr(m, 'name', 'N/A'),
                        "tag": getattr(m, 'tag', '#?'),
                        "townhall": getattr(m, 'town_hall', 0),
                        "map_position": getattr(m, 'map_position', 0),
                        "attacks_used": len(getattr(m, 'attacks', [])),
                        "attacks_made": attacks_made_formatted,
                        "defenses_received": defenses_received_formatted
                    })
                return sorted(details, key=lambda x: x['map_position'])

            def get_star_dist(attacks):
                dist = {i: 0 for i in range(4)}
                for a in attacks:
                    if a and hasattr(a, 'stars'): dist[a.stars] += 1
                return dist

            our_attacks_raw = [a for a in getattr(war, 'attacks', []) if a and getattr(getattr(a, 'attacker', None), 'clan', None) and a.attacker.clan.tag == our_clan.tag]
            opp_attacks_raw = [a for a in getattr(war, 'attacks', []) if a and getattr(getattr(a, 'attacker', None), 'clan', None) and a.attacker.clan.tag == opp_clan.tag]

            all_attacks_data = []
            for attack in getattr(war, 'attacks', []):
                if not attack: continue
                attacker = war.get_member(getattr(attack, 'attacker_tag', None))
                defender = war.get_member(getattr(attack, 'defender_tag', None))
                all_attacks_data.append({
                    "order": getattr(attack, 'order', 0),
                    "attacker_clan_tag": getattr(getattr(attacker, 'clan', None), 'tag', None),
                    "attacker_tag": getattr(attacker, 'tag', getattr(attack, 'attacker_tag', '?')),
                    "attacker_name": getattr(attacker, 'name', getattr(attack, 'attacker_tag', '?')),
                    "attacker_townhall": getattr(attacker, 'town_hall', 0),
                    "defender_tag": getattr(defender, 'tag', getattr(attack, 'defender_tag', '?')),
                    "defender_name": getattr(defender, 'name', getattr(attack, 'defender_tag', '?')),
                    "defender_townhall": getattr(defender, 'town_hall', 0),
                    "stars": getattr(attack, 'stars', 0),
                    "destruction": getattr(attack, 'destruction', 0),
                    "duration": f"{getattr(attack, 'duration', 0)}s"
                })

            time_details = {}
            if format_war_time_details:
                 time_details = format_war_time_details(war, datetime.datetime.now(pytz.utc))
            else:
                 time_details = {"time_key": "Tempo", "time_value": "-", "time_remaining": "-", "end_time_iso": None}

            return {
                "war_data": {
                    "clan_tag": getattr(our_clan, 'tag', '#?'),
                    "status": str(getattr(war, 'state', 'unknown')),
                    "state_description": str(getattr(war, 'state', 'unknown')).capitalize(),
                    "clan_name": getattr(our_clan, 'name', 'N/A'),
                    "clan_stars": getattr(our_clan, 'stars', 0),
                    "clan_destruction": f"{getattr(our_clan, 'destruction', 0.0):.2f}%",
                    "clan_badge_url": getattr(getattr(our_clan, 'badge', None), 'url', None),
                    "clan_attacks_used": getattr(our_clan, 'attacks_used', 0),
                    "opponent_name": getattr(opp_clan, 'name', 'N/A'),
                    "opponent_stars": getattr(opp_clan, 'stars', 0),
                    "opponent_destruction": f"{getattr(opp_clan, 'destruction', 0.0):.2f}%",
                    "opponent_badge_url": getattr(getattr(opp_clan, 'badge', None), 'url', None),
                    "opponent_attacks_used": getattr(opp_clan, 'attacks_used', 0),
                    **time_details,
                    "attacks_per_member": getattr(war, 'attacks_per_member', 2),
                    "team_size": getattr(war, 'team_size', 0),
                    "clan_star_distribution": get_star_dist(our_attacks_raw),
                    "opponent_star_distribution": get_star_dist(opp_attacks_raw),
                    "clan_avg_stars": f"{our_clan.stars / len(our_attacks_raw):.2f}" if our_attacks_raw else "0.00",
                    "opponent_avg_stars": f"{opp_clan.stars / len(opp_attacks_raw):.2f}" if opp_attacks_raw else "0.00",
                    "is_cwl": getattr(war, 'is_cwl', False)
                },
                "all_attacks": sorted(all_attacks_data, key=lambda x: x['order']),
                "our_clan_members_in_war": get_team_details(our_clan, war),
                "opponent_clan_members_in_war": get_team_details(opp_clan, war),
                "prediction": prediction_data
            }
        except Exception as e:
            logger.error(f"Erro ao formatar detalhes da guerra: {e}", exc_info=True)
            return {"error": "Erro interno ao formatar dados da guerra."}

    async def fetch_clan_info_for_web(self):
        if cache:
            cached = cache.get("clan_info")
            if cached: return cached
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan: return {"error": "Não foi possível carregar os dados do clã."}
        capital_league_name = getattr(getattr(clan, 'capital_league', None), 'name', 'N/A')
        result = {
            "name": getattr(clan, 'name', 'N/A'), "tag": getattr(clan, 'tag', 'N/A'),
            "level": getattr(clan, 'level', 0), "points": getattr(clan, 'points', 0),
            "capital_points": getattr(clan, 'capital_points', 0), "member_count": getattr(clan, 'member_count', 0),
            "description": getattr(clan, 'description', ''), "war_wins": getattr(clan, 'war_wins', 0),
            "location": getattr(getattr(clan, 'location', None), 'name', 'N/A'),
            "type": str(getattr(clan, 'type', 'N/A')).capitalize(),
            "badge_url": getattr(getattr(clan, 'badge', None), 'url', None),
            "version": self.bot.bot_version,
            "capital_league": capital_league_name,
        }
        if cache: cache.set("clan_info", result, ttl=60)
        return result

    async def fetch_current_war_details_for_web(self, force_api_call=False):
        if cache and not force_api_call:
            cached = cache.get("current_war")
            if cached: return cached
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag, ignore_cache=force_api_call)
            if not war or war.state == "notInWar":
                 return {"error": "Nenhuma guerra para detalhar."}
            response_data = await self.format_war_details_for_web(war)
            if cache and not response_data.get("error"): cache.set("current_war", response_data, ttl=30)
            return response_data
        except (coc.NotFound, coc.PrivateWarLog):
            return {"error": "Nenhuma guerra para detalhar ou log privado."}
        except Exception as e:
            logger.error(f"Erro em fetch_current_war_details_for_web: {e}", exc_info=True)
            return {"error": "Erro interno ao processar dados da guerra."}

    async def fetch_player_profile_for_web(self, player_tag: str):
        try:
            player = await self.bot.api_client.get_player(player_tag)
            if not player: return {"error": "Jogador não encontrado na Supercell."}
            home_heroes = ["Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion", "Minion Prince", "Dragon Duke"]
            heroes_data = [{"name": h.name, "level": h.level, "max_level": h.max_level, "equipment": [{"name": e.name, "level": e.level, "max_level": e.max_level} for e in getattr(h, 'equipment', [])]} for h in player.heroes if h.name in home_heroes]
            league_icon = player.league.icon.url if player.league and player.league.icon else None
            
            pets_data = [{"name": p.name, "level": p.level, "max_level": p.max_level} for p in getattr(player, 'pets', [])]
            equipment_data = [{"name": e.name, "level": e.level, "max_level": e.max_level} for e in getattr(player, 'equipment', []) if getattr(e, 'village', 'home') == 'home']
            
            legend = getattr(player, 'legend_statistics', None)
            legend_data = {}
            if legend:
                legend_data = {
                    "legend_trophies": getattr(legend, 'legend_trophies', 0),
                    "current_season": getattr(legend, 'current_season', None) and getattr(legend.current_season, 'trophies', 0),
                    "previous_season": getattr(legend, 'previous_season', None) and getattr(legend.previous_season, 'trophies', 0),
                    "best_season": getattr(legend, 'best_season', None) and getattr(legend.best_season, 'trophies', 0),
                }
            
            capital_gold = getattr(player, 'clan_capital_contributions', 0)
            
            # === NOVO CÁLCULO DE HITRATE COM LIMITE DINÂMICO ===
            hitrate = {
                "total_wars": 0, "attacks_made": 0, "attacks_missed": 0, 
                "total_stars": 0, "three_star_attacks": 0, "avg_destruction": 0.0
            }
            
            if self.db:
                # Agora varre a memória profunda baseada no MAX_WAR_HISTORY (500) em vez de ser burra com 50
                cursor = self.db.war_history.find({"our_clan_members_in_war.tag": player.tag}).sort("war_data.end_time_iso", -1).limit(self.MAX_WAR_HISTORY)
                total_destruction = 0
                async for war_doc in cursor:
                    hitrate["total_wars"] += 1
                    apm = war_doc.get("war_data", {}).get("attacks_per_member", 2)
                    
                    for member in war_doc.get("our_clan_members_in_war", []):
                        if member.get("tag") == player.tag:
                            attacks = member.get("attacks_made", [])
                            hitrate["attacks_made"] += len(attacks)
                            hitrate["attacks_missed"] += (apm - len(attacks))
                            
                            for atk in attacks:
                                stars = atk.get("stars", 0)
                                hitrate["total_stars"] += stars
                                total_destruction += atk.get("destruction", 0)
                                if stars == 3: hitrate["three_star_attacks"] += 1
                            break
                            
                if hitrate["attacks_made"] > 0:
                    hitrate["avg_destruction"] = round(total_destruction / hitrate["attacks_made"], 2)

            return {
                "name": player.name, "tag": player.tag, "town_hall": player.town_hall, "trophies": player.trophies,
                "league": player.league.name if player.league else "Sem Liga", "league_icon": league_icon,
                "donations": player.donations, "received": player.received, "heroes": heroes_data,
                "pets": pets_data, "equipment": equipment_data, "legend_stats": legend_data,
                "capital_gold": capital_gold,
                "role": player.role.name.capitalize() if hasattr(player, 'role') and hasattr(player.role, 'name') else "Membro",
                "hitrate": hitrate
            }
        except Exception as e:
            logger.error(f"Erro em fetch_player_profile_for_web: {e}", exc_info=True)
            return {"error": "Falha de conexão com a API da Supercell."}

    async def fetch_clan_members_for_web(self):
        if cache:
            cached = cache.get("clan_members")
            if cached: return cached
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan: return {"error": "Não foi possível carregar os dados do clã."}

        db_cog = self.bot.get_cog("Banco de Dados")
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        analytics_cog = self.bot.get_cog("Player Analytics")

        player_notes = await db_cog.load_player_notes_from_db() if db_cog else {}
        members_list = []

        last_war_dates = {}
        if self.db is not None:
            try:
                pipeline = [
                    {"$unwind": "$our_clan_members_in_war"},
                    {"$sort": {"war_data.end_time_iso": DESCENDING}},
                    {"$group": {
                        "_id": "$our_clan_members_in_war.tag",
                        "last_war_date": {"$first": "$war_data.end_time_iso"}
                    }}
                ]
                results = await self.db.war_history.aggregate(pipeline).to_list(length=None)
                last_war_dates = {item["_id"]: item["last_war_date"] for item in results}
            except Exception as e: pass

        insights_dict = {}
        if analytics_cog:
            try:
                await analytics_cog.process_and_train(self.bot.clan_tag)
                current_tags = [m.tag for m in clan.members]
                insights_data = await analytics_cog.get_player_insights(current_tags)
                if "insights" in insights_data:
                    for insight in insights_data["insights"]:
                        insights_dict[insight["tag"]] = insight
            except Exception as e:
                logger.error(f"Erro ao processar ML Analytics em members_for_web: {e}")

        for member in clan.members:
            note_data = player_notes.get(member.tag, {})
            watchlist_entry = await watchlist_cog.is_on_watchlist(member.tag) if watchlist_cog else None
            last_war_date_iso = last_war_dates.get(member.tag)
            player_insight = insights_dict.get(member.tag, {})

            members_list.append({
                "tag": member.tag, "name": member.name, "town_hall": member.town_hall,
                "league": member.league.name if member.league else "Sem Liga",
                "trophies": member.trophies,
                "role": member.role.name.capitalize() if member.role and hasattr(member.role, 'name') else "Membro",
                "donations": member.donations, "received": member.received,
                "note": note_data.get("text", ""), "note_priority": note_data.get("priority", "none"),
                "cwl_status": note_data.get("cwl_status", "active"),
                "isOnWatchlist": bool(watchlist_entry),
                "watchlistReason": watchlist_entry.get('reason', None) if watchlist_entry else None,
                "watchlistDetails": watchlist_entry.get('details', None) if watchlist_entry else None,
                "last_war_date": last_war_date_iso,
                "attack_probability": player_insight.get("attack_probability"),
                "tier": player_insight.get("tier", "Não Classificado"),
                "wars_participated_ml": player_insight.get("wars_participated", 0)
            })
            
        role_order = {"Leader": 0, "Co-leader": 1, "Admin": 2, "Member": 3}
        sorted_members = sorted(members_list, key=lambda m: (role_order.get(m["role"], 4), -m["trophies"]))
        result = {"clan_name": clan.name, "members": sorted_members, "version": self.bot.bot_version}
        if cache: cache.set("clan_members", result, ttl=30)
        return result

    async def fetch_missed_attacks_history_for_web(self):
        if self.db is None: return {"error": "Histórico indisponível (DB não conectado)."}
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
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
                end_date_str = war_data.get("end_time_iso")
                end_date_formatted = "Data Inválida"
                if end_date_str:
                    try:
                        end_time_dt = datetime.datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
                        end_date_formatted = end_time_dt.astimezone(self.bot.timezone).strftime('%d/%m/%y')
                    except ValueError: pass
                wars_with_missed_attacks.append({
                    "opponent_name": war_data.get("opponent_name", "Oponente Desconhecido"),
                    "end_date": end_date_formatted,
                    "missed_attacks_members": missed_attacks_members, "is_latest": is_first_war
                })
                is_first_war = False
        return {"clan_name": clan.name, "wars_with_missed_attacks": wars_with_missed_attacks}

    async def fetch_war_log_for_web(self):
        if self.db is None: return {"error": "Histórico indisponível (DB não conectado)."}
        
        log_cursor = self.db.war_history.find({}, {"war_data": 1, "_id": 1}).sort("war_data.end_time_iso", DESCENDING).limit(self.MAX_WAR_HISTORY)
        
        entries = []
        async for war_doc in log_cursor:
            war_data = war_doc.get("war_data", {})
            end_time_str = war_data.get("end_time_iso")
            end_time_formatted = "Data Inválida"
            if end_time_str:
                try:
                    end_time_dt = datetime.datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                    end_time_formatted = end_time_dt.astimezone(self.bot.timezone).strftime('%d/%m/%y %H:%M')
                except ValueError: pass

            clan_stars = war_data.get("clan_stars", 0)
            opp_stars = war_data.get("opponent_stars", 0)
            clan_dest = float(war_data.get("clan_destruction", "0%").replace('%',''))
            opp_dest = float(war_data.get("opponent_destruction", "0%").replace('%',''))
            result = "Empate"
            if clan_stars > opp_stars or (clan_stars == opp_stars and clan_dest > opp_dest): result = "Vitória"
            elif opp_stars > clan_stars or (clan_stars == opp_stars and opp_dest > clan_dest): result = "Derrota"
            entries.append({
                "war_id": war_doc.get("_id"), "end_time_iso": end_time_str, "end_time_formatted": end_time_formatted,
                "opponent_name": war_data.get("opponent_name"), "opponent_badge_url": war_data.get("opponent_badge_url"),
                "clan_stars": clan_stars, "opponent_stars": opp_stars,
                "result": result, "team_size": war_data.get("team_size"), "is_cwl": war_data.get("is_cwl", False)
            })
        return {"log": entries}

    async def fetch_cwl_info_for_web(self):
        if not self.bot.api_client: return {"error": "API do CoC não iniciada."}
        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group: return {"status": "NotInCwl", "message": "O clã não está participando da CWL nesta temporada."}
            
            clans_in_group = [{"name": c.name, "tag": c.tag, "level": c.level, "badge_url": getattr(c.badge, 'url', None)} for c in cwl_group.clans]
            rounds_info = []
            
            for i, a_round in enumerate(cwl_group.rounds):
                round_data = {"round_number": i + 1, "wars": []}
                for war_tag in a_round:
                    if war_tag == '#0': continue
                    try:
                        war = await self.bot.api_client.get_league_war(war_tag)
                        if war and war.clan and war.opponent:
                             war_time_details = format_war_time_details(war, datetime.datetime.now(pytz.utc)) if format_war_time_details else {}
                             round_data["wars"].append({
                                "war_tag": war_tag,
                                "clan_name": war.clan.name, "clan_badge_url": getattr(war.clan.badge, 'url', None), "clan_stars": war.clan.stars,
                                "opponent_name": war.opponent.name, "opponent_badge_url": getattr(war.opponent.badge, 'url', None), "opponent_stars": war.opponent.stars,
                                "state_description": str(war.state).capitalize(),
                                **war_time_details
                            })
                    except coc.NotFound:
                        round_data["wars"].append({
                            "war_tag": war_tag, "clan_name": "N/A", "clan_badge_url": None, "clan_stars": 0,
                            "opponent_name": "N/A", "opponent_badge_url": None, "opponent_stars": 0,
                            "state_description": "Não Iniciada", "error": "Guerra não encontrada."
                        })
                    except Exception as e:
                         round_data["wars"].append({
                            "war_tag": war_tag, "clan_name": "Erro", "clan_badge_url": None, "clan_stars": 0,
                            "opponent_name": "Erro", "opponent_badge_url": None, "opponent_stars": 0,
                            "state_description": "Erro", "error": str(e)
                        })
                rounds_info.append(round_data)
            return {"status": "InCwl", "season": cwl_group.season, "state": str(cwl_group.state).capitalize(), "clans_in_group": clans_in_group, "rounds": rounds_info}
        except coc.NotFound: return {"status": "NotInCwl", "message": "O clã não está inscrito na CWL."}
        except Exception as e: return {"status": "Error", "error": "Erro ao buscar dados da CWL."}

    async def fetch_highlights_for_web(self):
        if cache:
            cached = cache.get("highlights")
            if cached: return cached
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan: return {"error": "Não foi possível carregar destaques."}
        
        active_members = sorted(clan.members, key=lambda m: m.donations, reverse=True)
        top_donors = []
        for i, m in enumerate(active_members[:3]):
            ratio = (m.donations / max(m.received, 1)) if m.received > 0 else m.donations
            reason = f"🧠 Análise Logística: Sustentou a economia bélica do clã. Injetou tropas com taxa de eficiência de {ratio:.1f}x." if i == 0 else f"Fornecedor de recursos ativo: {m.donations} doadas."
            top_donors.append({
                "name": m.name, "town_hall": m.town_hall, "donations": m.donations, "reason": reason
            })

        war_end_date_str = ""
        war_heroes = []
        if self.db is not None:
            latest_war_doc = await self.db.war_history.find_one({}, sort=[("war_data.end_time_iso", DESCENDING)])
            if latest_war_doc:
                end_time_str = latest_war_doc.get("war_data", {}).get("end_time_iso")
                if end_time_str:
                    try:
                         end_time = datetime.datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                         war_end_date_str = end_time.astimezone(self.bot.timezone).strftime('%d/%m')
                    except ValueError: pass

                try:
                    analysis = analyze_war(latest_war_doc)
                    for award in analysis.get("awards", []):
                        player_str = award.get("player", "")
                        m = re.match(r'(.+?)\s*\(CV(\d+)\)', player_str)
                        name = m.group(1) if m else player_str
                        th = int(m.group(2)) if m else 0
                        war_heroes.append({
                            "name": name,
                            "town_hall": th,
                            "rank": len(war_heroes) + 1,
                            "reason": award["title"] + ": " + award["reason"]
                        })
                except Exception as e:
                    logger.warning(f"analyze_war falhou nos destaques web: {e}")

        top_10 = active_members[:10]
        chart_data = {"labels": [m.name for m in top_10], "donations": [m.donations for m in top_10], "received": [m.received for m in top_10]}
        
        result = {
            "clan_name": clan.name, "war_date": war_end_date_str, 
            "top_donors": top_donors, "war_heroes": war_heroes, 
            "activity_chart_data": chart_data
        }
        if cache: cache.set("highlights", result, ttl=30)
        return result

    # === GENIUSLIB V4.2.0: UPGRADE TRACKER ===
    async def fetch_player_upgrades_for_web(self, player_tag: str):
        try:
            player = await self.bot.api_client.get_player(player_tag)
            if not player:
                return {"error": "Jogador não encontrado."}
            summary = get_th_upgrade_summary(player, target_th=None, builder_count=5)
            if not summary or not summary.upgrades:
                return {
                    "name": player.name,
                    "tag": player.tag,
                    "town_hall": player.town_hall,
                    "message": "Nenhum upgrade pendente encontrado.",
                    "upgrades": [],
                "_has_th_table": _HAS_TH_TABLE
            }
            upgrades_list = []
            for u in summary.upgrades:
                upgrades_list.append({
                    "name": u.name,
                    "item_type": u.item_type,
                    "from_level": u.from_level,
                    "to_level": u.to_level,
                    "gold": u.gold,
                    "elixir": u.elixir,
                    "dark_elixir": u.dark_elixir,
                    "time_seconds": u.time_seconds,
                })
            return {
                "name": player.name,
                "tag": player.tag,
                "town_hall": player.town_hall,
                "current_th": summary.current_th,
                "target_th": summary.target_th,
                "total_gold": summary.total_gold,
                "total_elixir": summary.total_elixir,
                "total_dark_elixir": summary.total_dark_elixir,
                "total_time_seconds": summary.total_time_seconds,
                "estimated_real_time_days": round(summary.estimated_real_time.total_seconds() / 86400, 1),
                "total_upgrades": len(summary.upgrades),
                "builder_count": summary.builder_count,
                "upgrades": upgrades_list,
                "_has_th_table": _HAS_TH_TABLE
            }
        except coc.NotFound:
            return {"error": "Jogador não encontrado."}
        except Exception as e:
            logger.error(f"Erro em fetch_player_upgrades_for_web: {e}", exc_info=True)
            return {"error": "Erro ao buscar dados de upgrades."}

    # === GENIUSLIB V4.2.0: EXPORTADOR ===
    async def export_clan_data_for_web(self, export_format: str = "json"):
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan:
            return {"error": "Clã não encontrado."}
        if export_format == "json":
            return {"format": "json", "data": to_json(clan)}
        elif export_format == "csv":
            return {"format": "csv", "data": to_csv(clan, "clan")}
        return {"error": "Formato inválido. Use 'json' ou 'csv'."}

    async def export_players_for_web(self, export_format: str = "json"):
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan:
            return {"error": "Clã não encontrado."}
        players = []
        for member in clan.members:
            try:
                player = await self.bot.api_client.get_player(member.tag)
                if player:
                    players.append(player)
            except Exception:
                continue
        if export_format == "json":
            from geniuslib.exporter import export_players
            return {"format": "json", "data": export_players(players, "json")}
        elif export_format == "csv":
            from geniuslib.exporter import export_players
            return {"format": "csv", "data": export_players(players, "csv")}
        return {"error": "Formato inválido."}

    # === GENIUSLIB V4.2.0: COMPARADOR ===
    async def compare_players_for_web(self, tag1: str, tag2: str):
        try:
            p1 = await self.bot.api_client.get_player(coc.utils.correct_tag(tag1))
            p2 = await self.bot.api_client.get_player(coc.utils.correct_tag(tag2))
            if not p1 or not p2:
                return {"error": "Um dos jogadores não foi encontrado."}
            result = compare_players(p1, p2)
            result["left"]["town_hall_name"] = format_th(result["left"]["town_hall"])
            result["right"]["town_hall_name"] = format_th(result["right"]["town_hall"])
            return result
        except coc.NotFound:
            return {"error": "Jogador não encontrado."}
        except Exception as e:
            logger.error(f"Erro em compare_players_for_web: {e}", exc_info=True)
            return {"error": "Erro ao comparar jogadores."}

    async def compare_clans_for_web(self, tag1: str, tag2: str):
        try:
            c1 = await self.bot.api_client.get_clan(coc.utils.correct_tag(tag1))
            c2 = await self.bot.api_client.get_clan(coc.utils.correct_tag(tag2))
            if not c1 or not c2:
                return {"error": "Um dos clãs não foi encontrado."}
            return compare_clans(c1, c2)
        except coc.NotFound:
            return {"error": "Clã não encontrado."}
        except Exception as e:
            logger.error(f"Erro em compare_clans_for_web: {e}", exc_info=True)
            return {"error": "Erro ao comparar clãs."}

    # === GENIUSLIB V5.1.0: LEGEND LEAGUE / BATTLE LOGS ===
    async def fetch_legend_data_for_web(self, player_tag: str) -> Dict[str, Any]:
        """Busca dados de Legend League para o painel web."""
        try:
            player = await self.bot.api_client.get_player(player_tag)
            if not player:
                return {"error": "Jogador não encontrado."}

            entries = await self.bot.api_client.get_player_battlelog(player_tag)
            if not entries:
                return {
                    "name": player.name,
                    "tag": player.tag,
                    "town_hall": player.town_hall,
                    "message": "Nenhum battle log encontrado. O jogador precisa estar na Legend League.",
                    "attacks": {},
                    "defenses": {},
                    "loot": {},
                    "win_rate": 0.0,
                    "consistency": 0.0,
                }

            attack_stats = battle_attack_stats(entries)
            defense_stats = battle_defense_stats(entries)
            loot = battle_loot_summary(entries)
            win = battle_win_rate(entries)
            consistency = battle_consistency_score(entries)

            return {
                "name": player.name,
                "tag": player.tag,
                "town_hall": player.town_hall,
                "league": player.league.name if player.league else None,
                "attacks": attack_stats,
                "defenses": defense_stats,
                "loot": loot,
                "win_rate": round(win, 1),
                "consistency": round(consistency, 1),
                "_raw_entries": [
                    {
                        "army_share_code": getattr(e, 'army_share_code', None),
                        "army": decode_army_code(
                            getattr(e, 'army_share_code', None),
                            getattr(self.bot.api_client, '_static_data', {}),
                        ) if getattr(e, 'army_share_code', None) else None,
                        "stars": getattr(e, 'stars', 0),
                        "destruction_percentage": getattr(e, 'destruction_percentage', 0),
                        "attack": getattr(e, 'attack', None),
                    }
                    for e in entries
                ],
            }
        except coc.NotFound:
            return {"error": "Jogador não encontrado."}
        except Exception as e:
            logger.error(f"Erro em fetch_legend_data_for_web: {e}", exc_info=True)
            return {"error": "Erro ao buscar dados de Legend League."}

    async def fetch_legend_history_for_web(self, player_tag: str) -> Dict[str, Any]:
        """Busca histórico de ligas para o painel web."""
        try:
            player = await self.bot.api_client.get_player(player_tag)
            if not player:
                return {"error": "Jogador não encontrado."}

            history = await self.bot.api_client.get_player_league_history(player_tag)
            if not history:
                return {
                    "name": player.name,
                    "tag": player.tag,
                    "message": "Nenhum histórico de ligas encontrado.",
                    "progression": {},
                }

            progression = league_history_progression(history)
            return {
                "name": player.name,
                "tag": player.tag,
                "progression": progression,
            }
        except coc.NotFound:
            return {"error": "Jogador não encontrado."}
        except Exception as e:
            logger.error(f"Erro em fetch_legend_history_for_web: {e}", exc_info=True)
            return {"error": "Erro ao buscar histórico de ligas."}

    async def fetch_legend_clan_summary_for_web(self, dias: int = 1) -> Dict[str, Any]:
        """Busca resumo da clan em Legend League para o painel web."""
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            if not clan:
                return {"error": "Clã não encontrado."}

            legend_members = [
                m for m in clan.members
                if m.league and "legend" in m.league.name.lower()
            ]

            if not legend_members:
                return {
                    "clan_name": clan.name,
                    "clan_tag": clan.tag,
                    "message": "Nenhum membro Legend encontrado.",
                    "members": [],
                    "period": {},
                }

            all_entries = []
            member_data = []
            for member in legend_members:
                try:
                    entries = await self.bot.api_client.get_player_battlelog(member.tag)
                    if entries:
                        all_entries.extend(entries)
                        stats = battle_attack_stats(entries)
                        member_data.append({
                            "tag": member.tag,
                            "name": member.name,
                            "town_hall": member.town_hall,
                            "attacks": stats["total_attacks"],
                            "wins": stats["wins"],
                            "avg_stars": stats["avg_stars"],
                        })
                except Exception:
                    continue

            today = datetime.date.today()
            start = today - datetime.timedelta(days=dias)
            period = battle_period_summary(all_entries, start, today) if all_entries else {}

            return {
                "clan_name": clan.name,
                "clan_tag": clan.tag,
                "legend_count": len(legend_members),
                "members": member_data,
                "period": period,
            }
        except Exception as e:
            logger.error(f"Erro em fetch_legend_clan_summary_for_web: {e}", exc_info=True)
            return {"error": "Erro ao buscar resumo da clan em Legend."}

async def setup(bot: commands.Bot):
    if 'cogs.player_analytics_cog' not in bot.extensions:
        try:
            await bot.load_extension('cogs.player_analytics_cog')
        except Exception as e:
            logger.error(f"Falha ao carregar Player Analytics Cog: {e}")
            
    await bot.add_cog(WebApiCog(bot))
