# -*- coding: utf-8 -*-
import logging
import datetime
import pytz
from typing import Dict, Any, Optional

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
            # A chave 'capital_districts' foi removida para corrigir o erro e atender ao pedido.
        }

    async def fetch_current_war_details_for_web(self, force_api_call=False):
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            # A função format_war_details_for_web está no bot principal
            response_data = await self.bot.format_war_details_for_web(war)
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
        for member in clan.members:
            note_data = player_notes.get(member.tag, {})
            members_list.append({
                "tag": member.tag, "name": member.name, "town_hall": member.town_hall,
                "league": member.league.name if member.league else "Sem Liga",
                "trophies": member.trophies, "role": member.role.name.capitalize() if member.role else "Membro",
                "donations": member.donations, "received": member.received,
                "note": note_data.get("text", ""), "note_priority": note_data.get("priority", "none"),
                "cwl_status": note_data.get("cwl_status", "active")
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
                end_time_dt = datetime.datetime.fromisoformat(war_data.get("end_time_iso"))
                wars_with_missed_attacks.append({
                    "opponent_name": war_data.get("opponent_name", "Oponente Desconhecido"),
                    "end_date": end_time_dt.astimezone(self.bot.timezone).strftime('%d/%m/%y'),
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
            if war_data.get("end_time_iso"):
                end_time_dt = datetime.datetime.fromisoformat(war_data.get("end_time_iso"))
                result = "Vitória" if war_data.get("clan_stars", 0) > war_data.get("opponent_stars", 0) else "Derrota" if war_data.get("clan_stars", 0) < war_data.get("opponent_stars", 0) else "Empate"
                entries.append({
                    "war_id": war_doc.get("_id"),
                    "end_time_iso": war_data.get("end_time_iso"), 
                    "end_time_formatted": end_time_dt.astimezone(self.bot.timezone).strftime('%d/%m/%y %H:%M'),
                    "opponent_name": war_data.get("opponent_name"), "opponent_badge_url": war_data.get("opponent_badge_url"),
                    "clan_stars": war_data.get("clan_stars"), "opponent_stars": war_data.get("opponent_stars"),
                    "result": result, "team_size": war_data.get("team_size"), "is_cwl": war_data.get("is_cwl", False)
                })
        return {"log": entries}

    async def fetch_cwl_info_for_web(self):
        if not self.bot.api_client: return {"error": "API do CoC não iniciada."}
        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group: return {"status": "NotInCwl"}
            
            clans_in_group = [{"name": c.name, "tag": c.tag, "level": c.level, "badge_url": c.badge.url} for c in cwl_group.clans]
            rounds_info = []
            
            for i, a_round in enumerate(cwl_group.rounds):
                round_data = {"round_number": i + 1, "wars": []}
                for war_tag in a_round:
                    if war_tag == '#0': continue
                    try:
                        war = await self.bot.api_client.get_league_war(war_tag)
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
                if latest_war_doc.get("war_data", {}).get("end_time_iso"):
                    end_time = datetime.datetime.fromisoformat(latest_war_doc["war_data"]["end_time_iso"])
                    war_end_date_str = end_time.astimezone(self.bot.timezone).strftime('%d/%m')
        active_members = sorted(clan.members, key=lambda m: m.donations, reverse=True)[:10]
        chart_data = {"labels": [m.name for m in active_members], "donations": [m.donations for m in active_members], "received": [m.received for m in active_members]}
        return {"top_donors": top_donors_data, "war_heroes": war_heroes, "activity_chart_data": chart_data, "clan_name": clan.name, "war_date": war_end_date_str}

async def setup(bot: commands.Bot):
    await bot.add_cog(WebApiCog(bot))
