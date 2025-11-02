# -*- coding: utf-8 -*-
import logging
import datetime
import pytz
from typing import Dict, Any

import coc
from discord.ext import commands
from pymongo import DESCENDING

# Importa a função diretamente
try:
    from formatting import format_war_time_details
except ImportError:
    format_war_time_details = None
    logger.error("Falha ao importar format_war_time_details de formatting")


logger = logging.getLogger("web_api_cog")

class WebApiCog(commands.Cog, name="Web API"):
    """Cog para gerenciar toda a lógica de busca de dados para o painel web."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        # REMOVIDO: self.watchlist_cog = None (Será obtido just-in-time)

    # REMOVIDO: Método cog_load que tentava obter watchlist_cog

    async def format_war_details_for_web(self, war: coc.ClanWar) -> Dict[str, Any]:
        # (Código mantido igual)
        try:
            if not war or not war.clan or not war.opponent:
                return {"error": "Dados da guerra incompletos."}

            prediction_data = {} # Inicializa vazio
            # Verifica se war_prediction_system existe e está inicializado
            if hasattr(self.bot, 'war_prediction_system') and self.bot.war_prediction_system and self.bot.war_prediction_system.is_initialized:
                 prediction_data = await self.bot.war_prediction_system.predict_war_outcome(war, self.bot.clan_tag)
            else:
                 logger.warning("War prediction system não disponível ou não inicializado ao formatar detalhes da guerra.")


            our_clan, opp_clan = (war.clan, war.opponent) if war.clan.tag == self.bot.clan_tag else (war.opponent, war.clan)

            def get_team_details(team, war_obj):
                if not team or not hasattr(team, 'members'): return []
                details = []
                for m in team.members:
                    if not m: continue
                    # Correção defensiva para nomes de membros
                    defender_member_obj = war_obj.get_member(getattr(m, 'tag', None)) # Tenta buscar objeto membro
                    defender_name_fallback = getattr(m, 'tag', '?') # Usa tag se nome não for encontrado
                    attacks_made_formatted = []
                    for a in getattr(m, 'attacks', []):
                         defender_attacked_obj = war_obj.get_member(getattr(a, 'defender_tag', None))
                         defender_attacked_name = getattr(defender_attacked_obj, 'name', getattr(a, 'defender_tag', '?'))
                         defender_attacked_th = getattr(defender_attacked_obj, 'town_hall', '?')
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
                        attacker_defense_th = getattr(attacker_defense_obj, 'town_hall', '?')
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

            # Filtra ataques válidos de forma mais segura
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
                    "attacker_tag": getattr(attacker, 'tag', getattr(attack, 'attacker_tag', '?')), # Salva a tag do atacante
                    "attacker_name": getattr(attacker, 'name', getattr(attack, 'attacker_tag', '?')),
                    "attacker_townhall": getattr(attacker, 'town_hall', '?'),
                    "defender_name": getattr(defender, 'name', getattr(attack, 'defender_tag', '?')),
                    "defender_townhall": getattr(defender, 'town_hall', '?'),
                    "stars": getattr(attack, 'stars', 0),
                    "destruction": getattr(attack, 'destruction', 0),
                    "duration": f"{getattr(attack, 'duration', 0)}s"
                })

            # Verifica se format_war_time_details foi importado
            time_details = {}
            if format_war_time_details:
                 time_details = format_war_time_details(war, datetime.datetime.now(pytz.utc))
            else:
                 logger.error("format_war_time_details não disponível para formatar tempos.")
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
                    **time_details, # Adiciona os detalhes de tempo
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
        # (Código mantido igual)
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan: return {"error": "Não foi possível carregar os dados do clã."}
        capital_league_name = getattr(getattr(clan, 'capital_league', None), 'name', 'N/A')
        return {
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

    async def fetch_current_war_details_for_web(self, force_api_call=False):
       # (Código mantido igual)
        try:
            # Forçar a busca na API pode ser útil aqui
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag, ignore_cache=force_api_call)
            if not war or war.state == "notInWar":
                 return {"error": "Nenhuma guerra para detalhar."}
            response_data = await self.format_war_details_for_web(war)
            return response_data
        except (coc.NotFound, coc.PrivateWarLog):
            return {"error": "Nenhuma guerra para detalhar ou log privado."} # Mensagem mais clara
        except Exception as e:
            logger.error(f"Erro em fetch_current_war_details_for_web: {e}", exc_info=True)
            return {"error": "Erro interno ao processar dados da guerra."}

    async def fetch_clan_members_for_web(self):
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan: return {"error": "Não foi possível carregar os dados do clã."}

        # <<< MODIFICADO: Obtém cogs aqui >>>
        db_cog = self.bot.get_cog("Banco de Dados")
        watchlist_cog = self.bot.get_cog("Lista de Observação") # Tenta obter aqui

        player_notes = await db_cog.load_player_notes_from_db() if db_cog else {}
        members_list = []

        if not watchlist_cog:
             logger.error("WatchlistCog não carregado em fetch_clan_members_for_web.")
             # Não define como None, apenas loga

        # *** NOVO: Busca as últimas datas de guerra para todos de uma vez ***
        last_war_dates = {}
        # *** CORREÇÃO: Usar 'is not None' para verificar o DB ***
        if self.db is not None:
            try:
                # Agrega para encontrar a data mais recente por jogador que participou
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
                logger.info(f"Encontradas últimas datas de guerra para {len(last_war_dates)} jogadores.")
            except Exception as e:
                logger.error(f"Erro ao buscar últimas datas de guerra: {e}")
        # *** FIM NOVO ***


        for member in clan.members:
            note_data = player_notes.get(member.tag, {})
            # Verifica se watchlist_cog existe antes de chamar
            watchlist_entry = await watchlist_cog.is_on_watchlist(member.tag) if watchlist_cog else None

            # *** NOVO: Adiciona a data da última guerra ***
            last_war_date_iso = last_war_dates.get(member.tag)
            # *** FIM NOVO ***

            members_list.append({
                "tag": member.tag, "name": member.name, "town_hall": member.town_hall,
                "league": member.league.name if member.league else "Sem Liga",
                "trophies": member.trophies,
                "role": member.role.name.capitalize() if member.role and hasattr(member.role, 'name') else "Membro", # Mais seguro
                "donations": member.donations, "received": member.received,
                "note": note_data.get("text", ""), "note_priority": note_data.get("priority", "none"),
                "cwl_status": note_data.get("cwl_status", "active"),
                "isOnWatchlist": bool(watchlist_entry),
                "watchlistReason": watchlist_entry.get('reason', None) if watchlist_entry else None,
                "watchlistDetails": watchlist_entry.get('details', None) if watchlist_entry else None,
                "last_war_date": last_war_date_iso # *** NOVO *** Adiciona a data (ou None)
            })
        role_order = {"Leader": 0, "Co-leader": 1, "Admin": 2, "Member": 3}
        sorted_members = sorted(members_list, key=lambda m: (role_order.get(m["role"], 4), -m["trophies"]))
        return {"clan_name": clan.name, "members": sorted_members, "version": self.bot.bot_version}

    async def fetch_missed_attacks_history_for_web(self):
        # *** CORREÇÃO: Usar 'is not None' para verificar o DB ***
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
                attacks_made = len(member.get("attacks_made", [])) # Usa attacks_made se disponível
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
                    except ValueError: logger.warning(f"Formato de data inválido no histórico: {end_date_str}")
                wars_with_missed_attacks.append({
                    "opponent_name": war_data.get("opponent_name", "Oponente Desconhecido"),
                    "end_date": end_date_formatted,
                    "missed_attacks_members": missed_attacks_members, "is_latest": is_first_war
                })
                is_first_war = False
        return {"clan_name": clan.name, "wars_with_missed_attacks": wars_with_missed_attacks}

    async def fetch_war_log_for_web(self):
        # *** CORREÇÃO: Usar 'is not None' para verificar o DB ***
        if self.db is None: return {"error": "Histórico indisponível (DB não conectado)."}
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
                except ValueError: logger.warning(f"Formato de data inválido no log de guerra: {end_time_str}")

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
       # (Código mantido igual)
        if not self.bot.api_client: return {"error": "API do CoC não iniciada."}
        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group: return {"status": "NotInCwl", "message": "O clã não está participando da CWL nesta temporada."}
            clans_in_group = [{"name": c.name, "tag": c.tag, "level": c.level, "badge_url": getattr(c.badge, 'url', None)} for c in cwl_group.clans] # Mais seguro
            rounds_info = []
            for i, a_round in enumerate(cwl_group.rounds):
                round_data = {"round_number": i + 1, "wars": []}
                for war_tag in a_round:
                    if war_tag == '#0': continue
                    try:
                        war = await self.bot.api_client.get_league_war(war_tag)
                        if war and war.clan and war.opponent: # Verifica se dados existem
                             # Verifica se format_war_time_details está disponível
                             war_time_details = format_war_time_details(war, datetime.datetime.now(pytz.utc)) if format_war_time_details else {}
                             round_data["wars"].append({
                                "war_tag": war_tag,
                                "clan_name": war.clan.name, "clan_badge_url": getattr(war.clan.badge, 'url', None), "clan_stars": war.clan.stars,
                                "opponent_name": war.opponent.name, "opponent_badge_url": getattr(war.opponent.badge, 'url', None), "opponent_stars": war.opponent.stars,
                                "state_description": str(war.state).capitalize(), # Adiciona estado
                                **war_time_details
                            })
                    except coc.NotFound: round_data["wars"].append({"error": f"Guerra {war_tag} não encontrada (API)." })
                    except Exception as e: logger.warning(f"Não foi possível buscar a guerra da CWL {war_tag}: {e}"); round_data["wars"].append({"error": f"Erro ao buscar guerra {war_tag}." })
                rounds_info.append(round_data)
            return {"status": "InCwl", "season": cwl_group.season, "state": str(cwl_group.state).capitalize(), "clans_in_group": clans_in_group, "rounds": rounds_info}
        except coc.NotFound: return {"status": "NotInCwl", "message": "O clã não está inscrito na CWL."}
        except Exception as e: logger.error(f"Erro inesperado ao buscar dados da CWL: {e}", exc_info=True); return {"status": "Error", "error": "Erro ao buscar dados da CWL."}


    async def fetch_highlights_for_web(self):
        # *** CORREÇÃO: Usar 'is not None' para verificar o DB ***
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan: return {"error": "Não foi possível carregar destaques."}
        top_donors_data = [{"name": m.name, "donations": m.donations, "town_hall": m.town_hall} for m in sorted(clan.members, key=lambda m: m.donations, reverse=True)[:3]]
        war_heroes, war_end_date_str = [], ""
        if self.db is not None:
            latest_war_doc = await self.db.war_history.find_one({}, sort=[("war_data.end_time_iso", DESCENDING)])
            if latest_war_doc:
                # Importa localmente para evitar dependência circular na inicialização
                try:
                     from cogs.post_war_analysis import _calculate_post_war_stats
                     analysis = _calculate_post_war_stats(latest_war_doc)
                     war_heroes = analysis.get("war_heroes", [])
                except ImportError:
                     logger.error("Falha ao importar _calculate_post_war_stats para destaques.")
                except Exception as e:
                     logger.error(f"Erro ao calcular heróis da guerra para destaques: {e}")

                end_time_str = latest_war_doc.get("war_data", {}).get("end_time_iso")
                if end_time_str:
                    try:
                         end_time = datetime.datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                         war_end_date_str = end_time.astimezone(self.bot.timezone).strftime('%d/%m')
                    except ValueError: war_end_date_str = "Data Inv."
        active_members = sorted(clan.members, key=lambda m: m.donations, reverse=True)[:10]
        chart_data = {"labels": [m.name for m in active_members], "donations": [m.donations for m in active_members], "received": [m.received for m in active_members]}
        return {"top_donors": top_donors_data, "war_heroes": war_heroes, "activity_chart_data": chart_data, "clan_name": clan.name, "war_date": war_end_date_str}


async def setup(bot: commands.Bot):
    await bot.add_cog(WebApiCog(bot))

