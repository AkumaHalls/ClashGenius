# -*- coding: utf-8 -*-
import logging
import datetime
import pytz
from typing import Dict, Any

import coc
from discord.ext import commands
from pymongo import DESCENDING

from formatting import format_war_time_details

logger = logging.getLogger("web_api_cog")

class WebApiCog(commands.Cog, name="Web API"):
    """Cog para gerenciar toda a lógica de busca de dados para o painel web."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        # Obtém referência à WatchlistCog após o bot estar pronto
        self.watchlist_cog = None

    async def cog_load(self):
        # Espera o bot estar pronto para garantir que todas as Cogs foram carregadas
        await self.bot.wait_until_ready()
        self.watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not self.watchlist_cog:
            logger.error("WatchlistCog não encontrada! A funcionalidade de watchlist no painel web não funcionará.")
            self.watchlist_cog = None # Define como None para evitar erros repetidos

    async def format_war_details_for_web(self, war: coc.ClanWar) -> Dict[str, Any]:
        try:
            if not war or not war.clan or not war.opponent:
                return {"error": "Dados da guerra incompletos."}

            prediction_data = await self.bot.war_prediction_system.predict_war_outcome(war, self.bot.clan_tag)
            our_clan, opp_clan = (war.clan, war.opponent) if war.clan.tag == self.bot.clan_tag else (war.opponent, war.clan)

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

            our_attacks_raw = [a for a in war.attacks if a and getattr(a.attacker, 'clan', None) and a.attacker.clan.tag == our_clan.tag]
            opp_attacks_raw = [a for a in war.attacks if a and getattr(a.attacker, 'clan', None) and a.attacker.clan.tag == opp_clan.tag]

            all_attacks_data = []
            for attack in war.attacks:
                if not attack: continue
                attacker = war.get_member(attack.attacker_tag)
                defender = war.get_member(attack.defender_tag)
                all_attacks_data.append({
                    "order": attack.order, "attacker_clan_tag": getattr(getattr(attacker, 'clan', None), 'tag', None),
                    "attacker_tag": getattr(attacker, 'tag', attack.attacker_tag),
                    "attacker_name": getattr(attacker, 'name', attack.attacker_tag),
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
                    "clan_star_distribution": get_star_dist(our_attacks_raw), "opponent_star_distribution": get_star_dist(opp_attacks_raw),
                    "clan_avg_stars": f"{our_clan.stars / len(our_attacks_raw):.2f}" if our_attacks_raw else "0.00",
                    "opponent_avg_stars": f"{opp_clan.stars / len(opp_attacks_raw):.2f}" if opp_attacks_raw else "0.00",
                    "is_cwl": war.is_cwl
                },
                "all_attacks": sorted(all_attacks_data, key=lambda x: x['order']), # Ordena ataques
                "our_clan_members_in_war": get_team_details(our_clan, war),
                "opponent_clan_members_in_war": get_team_details(opp_clan, war),
                "prediction": prediction_data
            }
        except Exception as e:
            logger.error(f"Erro ao formatar detalhes da guerra: {e}", exc_info=True)
            return {"error": "Erro interno ao formatar dados da guerra."}

    async def fetch_clan_info_for_web(self):
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
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
            "version": self.bot.bot_version,
            "capital_league": capital_league_name,
            # Removido districts
        }

    async def fetch_current_war_details_for_web(self, force_api_call=False):
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state == "notInWar":
                 return {"error": "Nenhuma guerra para detalhar."}
            response_data = await self.format_war_details_for_web(war)
            return response_data
        except (coc.NotFound, coc.PrivateWarLog):
            return {"error": "Nenhuma guerra para detalhar."}
        except Exception as e:
            logger.error(f"Erro em fetch_current_war_details_for_web: {e}", exc_info=True)
            return {"error": "Erro interno ao processar dados da guerra."}

    async def fetch_clan_members_for_web(self):
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan: return {"error": "Não foi possível carregar os dados do clã."}
        db_cog = self.bot.get_cog("Banco de Dados")
        player_notes = await db_cog.load_player_notes_from_db() if db_cog else {}
        members_list = []

        if not self.watchlist_cog:
             logger.error("WatchlistCog não carregado em fetch_clan_members_for_web.")
             self.watchlist_cog = None

        for member in clan.members:
            note_data = player_notes.get(member.tag, {})
            watchlist_entry = await self.watchlist_cog.is_on_watchlist(member.tag) if self.watchlist_cog else None

            members_list.append({
                "tag": member.tag, "name": member.name, "town_hall": member.town_hall,
                "league": member.league.name if member.league else "Sem Liga",
                "trophies": member.trophies, "role": member.role.name.capitalize() if member.role else "Membro",
                "donations": member.donations, "received": member.received,
                "note": note_data.get("text", ""), "note_priority": note_data.get("priority", "none"),
                "cwl_status": note_data.get("cwl_status", "active"),
                "isOnWatchlist": bool(watchlist_entry),
                "watchlistReason": watchlist_entry.get('reason', None) if watchlist_entry else None,
                "watchlistDetails": watchlist_entry.get('details', None) if watchlist_entry else None
            })
        role_order = {"Leader": 0, "Co-leader": 1, "Admin": 2, "Member": 3}
        sorted_members = sorted(members_list, key=lambda m: (role_order.get(m["role"], 4), -m["trophies"]))
        return {"clan_name": clan.name, "members": sorted_members, "version": self.bot.bot_version}

    async def fetch_missed_attacks_history_for_web(self):
        if self.db is None: return {"error": "Histórico indisponível."}
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
                 # Tenta analisar a data, mas usa string se falhar
                end_date_str = war_data.get("end_time_iso")
                end_date_formatted = "Data Inválida"
                if end_date_str:
                    try:
                        end_time_dt = datetime.datetime.fromisoformat(end_date_str.replace("Z", "+00:00")) # Garante compatibilidade
                        end_date_formatted = end_time_dt.astimezone(self.bot.timezone).strftime('%d/%m/%y')
                    except ValueError:
                         logger.warning(f"Formato de data inválido no histórico: {end_date_str}")

                wars_with_missed_attacks.append({
                    "opponent_name": war_data.get("opponent_name", "Oponente Desconhecido"),
                    "end_date": end_date_formatted,
                    "missed_attacks_members": missed_attacks_members, "is_latest": is_first_war
                })
                is_first_war = False
        return {"clan_name": clan.name, "wars_with_missed_attacks": wars_with_missed_attacks}

    async def fetch_war_log_for_web(self):
        if self.db is None: return {"error": "Histórico indisponível."}
        log_cursor = self.db.war_history.find({}, {"war_data": 1, "_id": 1}).sort("war_data.end_time_iso", DESCENDING).limit(50)
        entries = []
        async for war_doc in log_cursor:
            war_data = war_doc.get("war_data", {})
            end_time_str = war_data.get("end_time_iso")
            end_time_formatted = "Data Inválida"
            if end_time_str:
                try:
                    end_time_dt = datetime.datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                    end_time_formatted = end_time_dt.astimezone(self.bot.timezone).strftime('%d/%m/%y %H:%M')
                except ValueError:
                    logger.warning(f"Formato de data inválido no log de guerra: {end_time_str}")

            clan_stars = war_data.get("clan_stars", 0)
            opp_stars = war_data.get("opponent_stars", 0)
            clan_dest = float(war_data.get("clan_destruction", "0%").replace('%',''))
            opp_dest = float(war_data.get("opponent_destruction", "0%").replace('%',''))

            result = "Empate"
            if clan_stars > opp_stars or (clan_stars == opp_stars and clan_dest > opp_dest):
                result = "Vitória"
            elif opp_stars > clan_stars or (clan_stars == opp_stars and opp_dest > clan_dest):
                result = "Derrota"

            entries.append({
                "war_id": war_doc.get("_id"),
                "end_time_iso": end_time_str,
                "end_time_formatted": end_time_formatted,
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

            clans_in_group = [{"name": c.name, "tag": c.tag, "level": c.level, "badge_url": c.badge.url} for c in cwl_group.clans]
            rounds_info = []

            for i, a_round in enumerate(cwl_group.rounds):
                round_data = {"round_number": i + 1, "wars": []}
                for war_tag in a_round:
                    if war_tag == '#0': continue
                    try:
                        war = await self.bot.api_client.get_league_war(war_tag)
                        if war:
                             war_time_details = format_war_time_details(war, datetime.datetime.now(pytz.utc))
                             round_data["wars"].append({
                                "war_tag": war_tag,
                                "clan_name": war.clan.name, "clan_badge_url": war.clan.badge.url, "clan_stars": war.clan.stars,
                                "opponent_name": war.opponent.name, "opponent_badge_url": war.opponent.badge.url, "opponent_stars": war.opponent.stars,
                                **war_time_details # Inclui time_key, time_value, etc.
                            })
                    except coc.NotFound:
                         round_data["wars"].append({"error": f"Guerra {war_tag} não encontrada (API)." })
                    except Exception as e:
                        logger.warning(f"Não foi possível buscar a guerra da CWL {war_tag}: {e}")
                        round_data["wars"].append({"error": f"Erro ao buscar guerra {war_tag}." })
                rounds_info.append(round_data)

            return {"status": "InCwl", "season": cwl_group.season, "state": str(cwl_group.state).capitalize(), "clans_in_group": clans_in_group, "rounds": rounds_info}
        except coc.NotFound:
            return {"status": "NotInCwl", "message": "O clã não está inscrito na CWL."}
        except Exception as e:
            logger.error(f"Erro inesperado ao buscar dados da CWL: {e}", exc_info=True)
            return {"status": "Error", "error": "Erro ao buscar dados da CWL."}

    async def fetch_highlights_for_web(self):
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan: return {"error": "Não foi possível carregar destaques."}
        top_donors_data = [{"name": m.name, "donations": m.donations, "town_hall": m.town_hall} for m in sorted(clan.members, key=lambda m: m.donations, reverse=True)[:3]]
        war_heroes, war_end_date_str = [], ""
        if self.db is not None:
            latest_war_doc = await self.db.war_history.find_one({}, sort=[("war_data.end_time_iso", DESCENDING)])
            if latest_war_doc:
                from cogs.post_war_analysis import _calculate_post_war_stats
                analysis = _calculate_post_war_stats(latest_war_doc)
                war_heroes = analysis.get("war_heroes", [])
                end_time_str = latest_war_doc.get("war_data", {}).get("end_time_iso")
                if end_time_str:
                    try:
                         end_time = datetime.datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                         war_end_date_str = end_time.astimezone(self.bot.timezone).strftime('%d/%m')
                    except ValueError:
                         war_end_date_str = "Data Inv."
        active_members = sorted(clan.members, key=lambda m: m.donations, reverse=True)[:10]
        chart_data = {"labels": [m.name for m in active_members], "donations": [m.donations for m in active_members], "received": [m.received for m in active_members]}
        return {"top_donors": top_donors_data, "war_heroes": war_heroes, "activity_chart_data": chart_data, "clan_name": clan.name, "war_date": war_end_date_str}

async def setup(bot: commands.Bot):
    await bot.add_cog(WebApiCog(bot))
