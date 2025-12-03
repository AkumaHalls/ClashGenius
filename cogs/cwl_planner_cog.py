# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
from typing import Dict, List, Any, Optional, Set, Tuple
import datetime
import pytz
import math  # Necessário para o cálculo dinâmico
from collections import deque

logger = logging.getLogger("cwl_planner_cog")

class CwlPlannerCog(commands.Cog, name="Planeador de CWL"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_client: coc.Client = self.bot.api_client 
        self.db = bot.db
        self.cwl_plan_collection = self.db.cwl_plan if self.db is not None else None
        self.posted_daily_plans = set()
        self.posted_inactivity_alerts = set()
        self.last_known_members: Set[str] = set()
        self.reported_leavers: Set[str] = set() 

    async def cog_load(self):
        self.cwl_monitoring_task.start()

    async def cog_unload(self):
        self.cwl_monitoring_task.cancel()

    async def _send_planner_embed(self, embed: discord.Embed):
        if not self.bot.cwl_planner_channel_id: return
        try:
            channel = self.bot.get_channel(self.bot.cwl_planner_channel_id) or await self.bot.fetch_channel(self.bot.cwl_planner_channel_id)
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Falha ao enviar embed para o canal do planeador CWL: {e}")

    async def _send_critical_alert(self, title: str, description: str, fields: List[Dict[str, Any]] = None):
        """Envia alertas críticos com destaque especial no canal."""
        embed = discord.Embed(
            title=f"🚨 {title}",
            description=description,
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(pytz.utc)
        )
        
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get('name', 'Campo'),
                    value=field.get('value', 'N/A'),
                    inline=field.get('inline', False)
                )
        
        embed.set_footer(text="⚠️ AÇÃO NECESSÁRIA - Verifique imediatamente!")
        await self._send_planner_embed(embed)

    async def _get_current_cwl_war_info(self) -> Optional[Dict[str, Any]]:
        """Busca informações detalhadas sobre o estado atual da CWL."""
        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group or cwl_group.state == "notInWar":
                return None 

            active_war = None
            day_number = -1
            active_war_tag = None
            team_size = 15
            
            wars_by_state = {'inWar': [], 'preparation': [], 'warEnded': []}
            
            for i, round_war_tags in enumerate(cwl_group.rounds):
                for war_tag in round_war_tags:
                    if war_tag == '#0': continue
                    try:
                        war = await self.bot.api_client.get_league_war(war_tag)
                        if war.clan.tag == self.bot.clan_tag or war.opponent.tag == self.bot.clan_tag:
                            team_size = war.team_size
                            wars_by_state[war.state.value].append((war, i + 1, war_tag))
                    except coc.NotFound:
                        continue
            
            if wars_by_state['inWar']:
                active_war, day_number, active_war_tag = wars_by_state['inWar'][0]
            elif wars_by_state['preparation']:
                active_war, day_number, active_war_tag = wars_by_state['preparation'][0]
            elif wars_by_state['warEnded']:
                last_war, last_day, _ = max(wars_by_state['warEnded'], key=lambda x: x[1])
                day_number = min(last_day + 1, 8) 
                team_size = last_war.team_size

            if not active_war and day_number == -1:
                day_number = 8 

            return {
                "active_war": active_war,
                "day_number": day_number,
                "season": cwl_group.season,
                "war_tag": active_war_tag,
                "team_size": team_size,
                "cwl_state": cwl_group.state
            }

        except coc.NotFound:
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar _get_current_cwl_war_info: {e}", exc_info=True)
            return None

    async def _detect_roster_changes(self) -> Tuple[Set[str], Set[str]]:
        """Detecta entradas e saídas de membros no clã."""
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            current_members = {m.tag for m in clan.members}
            
            if not self.last_known_members:
                self.last_known_members = current_members
                return (set(), set())
            
            leavers = self.last_known_members - current_members
            joiners = current_members - self.last_known_members
            self.last_known_members = current_members
            
            return (leavers, joiners)
        except Exception as e:
            logger.error(f"Erro ao detectar mudanças no roster: {e}", exc_info=True)
            return (set(), set())

    async def _validate_plan_vs_reality(self, plan_data: Dict[str, Any], current_day: int) -> Dict[str, Any]:
        """Valida se o plano do banco de dados bate com a guerra real."""
        issues = { "missing_players": [], "unexpected_players": [], "status_changes": [], "is_valid": True }
        try:
            info = await self._get_current_cwl_war_info()
            if not info or not info['active_war']: return issues
            
            active_war = info['active_war']
            our_clan_in_war = active_war.clan if active_war.clan.tag == self.bot.clan_tag else active_war.opponent
            real_roster_tags = {m.tag for m in our_clan_in_war.members}
            
            current_day_plan = next((d for d in plan_data['schedule'] if d['day'] == current_day), None)
            if not current_day_plan: return issues
            
            planned_roster_tags = {p['player']['tag'] for p in current_day_plan['active_roster']}
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            current_clan_members = {m.tag for m in clan.members}
            
            for player_entry in current_day_plan['active_roster']:
                player_tag = player_entry['player']['tag']
                if player_tag not in current_clan_members:
                    issues["missing_players"].append(player_entry['player'])
                    issues["is_valid"] = False
            
            for member_tag in real_roster_tags:
                if member_tag not in planned_roster_tags:
                    try:
                        member = await self.bot.api_client.get_player(member_tag)
                        issues["unexpected_players"].append({ "name": member.name, "tag": member.tag, "town_hall": member.town_hall })
                        issues["is_valid"] = False
                    except: pass
            return issues
        except Exception as e:
            logger.error(f"Erro ao validar plano vs realidade: {e}", exc_info=True)
            return issues

    async def get_cwl_members_for_planning(self) -> Optional[List[Dict[str, Any]]]:
        """Busca a lista oficial de inscritos na CWL."""
        try:
            await self.bot.coc_client_ready.wait()
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group: return None
            our_clan_from_cwl = next((c for c in cwl_group.clans if c.tag == self.bot.clan_tag), None)
            if not our_clan_from_cwl: return None
            return [{"name": m.name, "tag": m.tag, "town_hall": m.town_hall} for m in our_clan_from_cwl.members]
        except coc.NotFound: return None
        except Exception as e:
            logger.error(f"Erro ao buscar membros da CWL: {e}", exc_info=True)
            return None

    def _get_player_pool_entry(self, player_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"player": player_data, "days_played": 0}

    def _calculate_rotation_needed(self, roster_size: int, active_bench: List[Dict], backup_bench: List[Dict], current_day: int) -> int:
        """
        Calcula dinamicamente quantas pessoas precisam rodar por dia para que todos joguem.
        Isso resolve o problema de pessoas ficarem sem jogar.
        """
        days_remaining = 8 - current_day
        if days_remaining <= 0: return 0

        # Conta quantos no banco ativo ainda não jogaram (ou jogaram muito pouco)
        unplayed_active = len([p for p in active_bench if p['days_played'] == 0])
        
        # Se houver muitos unplayed, aumenta a rotação
        if unplayed_active > 0:
            needed = math.ceil(unplayed_active / days_remaining)
            # Garante um mínimo de 3, mas tenta forçar mais se necessário
            return max(3, needed)
        
        # Se todos já jogaram pelo menos 1 vez, mantém rotação padrão
        return 3 if roster_size == 15 else 5

    async def _generate_new_7_day_plan(self, team_size: int, active_war: coc.ClanWar, starting_day: int = 1) -> Dict[str, Any]:
        cwl_members = await self.get_cwl_members_for_planning()
        if cwl_members is None:
            return {"error": "Não foi possível buscar os membros inscritos na CWL."}

        roster_size = team_size 
        clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
        current_member_tags = {m.tag for m in clan.members}
        db_cog = self.bot.get_cog("Banco de Dados")
        player_statuses = await db_cog.load_player_notes_from_db() if db_cog else {}
        
        our_clan_in_war = active_war.clan if active_war.clan.tag == self.bot.clan_tag else active_war.opponent
        actual_roster_tags = {m.tag for m in our_clan_in_war.members}
        
        current_roster = []
        current_active_bench = []
        current_backup_bench = []
        warning = None

        all_cwl_players_pool = []
        for member in cwl_members:
            if member['tag'] in current_member_tags:
                all_cwl_players_pool.append(self._get_player_pool_entry(member))
        
        if len(actual_roster_tags) < roster_size:
            warning = f"⚠️ Aviso Dia {starting_day}: Roster real ({len(actual_roster_tags)}) é MENOR que o tamanho da guerra."
        
        for p_entry in all_cwl_players_pool:
            player_tag = p_entry['player']['tag']
            p_entry['days_played'] = starting_day if player_tag in actual_roster_tags else max(0, starting_day - 1)

            if player_tag in actual_roster_tags:
                current_roster.append(p_entry)
            else:
                status = player_statuses.get(player_tag, {}).get('cwl_status', 'active')
                if status == 'active': current_active_bench.append(p_entry)
                else: current_backup_bench.append(p_entry)
        
        schedule = []
        
        schedule.append({
            "day": starting_day,
            "active_roster": [p.copy() for p in current_roster],
            "substitutions": [],
            "active_bench": [p.copy() for p in sorted(current_active_bench, key=lambda x: (x['days_played'], -x['player']['town_hall']))],
            "backup_bench": [p.copy() for p in sorted(current_backup_bench, key=lambda x: (x['days_played'], -x['player']['town_hall']))]
        })

        for day in range(starting_day + 1, 8):
            # CÁLCULO DINÂMICO DE ROTAÇÃO
            num_to_rotate = self._calculate_rotation_needed(team_size, current_active_bench, current_backup_bench, day)
            
            substitutions = []
            
            # QUEM SAI: Mais dias jogados > Menor CV
            roster_candidates = sorted(current_roster, key=lambda p: (p['days_played'], -p['player']['town_hall']), reverse=True)
            players_to_sit = roster_candidates[:num_to_rotate]
            
            # QUEM ENTRA: Menos dias jogados > Maior CV
            current_active_bench.sort(key=lambda p: (p['days_played'], -p['player']['town_hall']))
            active_bench_deque = deque(current_active_bench)
            current_backup_bench.sort(key=lambda p: (p['days_played'], -p['player']['town_hall']))
            backup_bench_deque = deque(current_backup_bench)

            players_to_play = []
            for _ in range(num_to_rotate):
                if active_bench_deque: players_to_play.append(active_bench_deque.popleft())
            
            needed = num_to_rotate - len(players_to_play)
            if needed > 0:
                if not warning: warning = f"⚠️ Aviso Dia {day}: Banco de 'Ativos' vazio. Usando 'Backups'."
                for _ in range(needed):
                    if backup_bench_deque: players_to_play.append(backup_bench_deque.popleft())
            
            new_roster = [p for p in current_roster if p not in players_to_sit]
            
            for i in range(len(players_to_sit)):
                player_out = players_to_sit[i]
                if i < len(players_to_play):
                    player_in = players_to_play[i]
                    new_roster.append(player_in)
                    
                    status_out = player_statuses.get(player_out['player']['tag'], {}).get('cwl_status', 'active')
                    if status_out == 'active': active_bench_deque.append(player_out) 
                    else: backup_bench_deque.append(player_out) 

                    substitutions.append({
                        "out": player_out['player'], "in": player_in['player'],
                        "reason": f"Rotação (Saiu: {player_out['days_played']}d | Entrou: {player_in['days_played']}d)"
                    })
                else:
                    new_roster.append(player_out)

            for p in new_roster: p['days_played'] += 1
            
            current_roster = new_roster
            current_active_bench = list(active_bench_deque)
            current_backup_bench = list(backup_bench_deque)

            schedule.append({
                "day": day,
                "active_roster": [p.copy() for p in current_roster],
                "substitutions": substitutions,
                "active_bench": [p.copy() for p in current_active_bench],
                "backup_bench": [p.copy() for p in current_backup_bench]
            })
        
        all_players_pool = current_roster + current_active_bench + current_backup_bench
        participation_score = [ {"player": p['player'], "days_played": p['days_played']} for p in all_players_pool ]
        participation_score.sort(key=lambda x: x['days_played'], reverse=True)

        return {
            "schedule": schedule, "participation_score": participation_score,
            "active_bench_final": current_active_bench, "backup_bench_final": current_backup_bench,
            "warning": warning, "starting_day": starting_day
        }

    async def _update_existing_plan(self, plan_doc: Dict[str, Any], current_day: int, team_size: int, active_war: coc.ClanWar) -> Dict[str, Any]:
        """
        Recalcula o plano garantindo que o pool de jogadores esteja sempre atualizado via API.
        """
        logger.info(f"Atualizando plano (Dia Atual: {current_day})...")
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            current_member_tags = {m.tag for m in clan.members}
            db_cog = self.bot.get_cog("Banco de Dados")
            player_statuses = await db_cog.load_player_notes_from_db() if db_cog else {}
            critical_changes = { "players_left": [], "status_changes": [], "emergency_substitutions": [] }
            
            our_clan_in_war = active_war.clan if active_war.clan.tag == self.bot.clan_tag else active_war.opponent
            actual_roster_tags = {m.tag for m in our_clan_in_war.members}
            
            # --- CORREÇÃO: Sempre busca o pool da API para incluir novos membros ---
            all_cwl_players_pool_data = await self.get_cwl_members_for_planning()
            if not all_cwl_players_pool_data:
                # Fallback seguro
                if plan_doc['schedule']:
                    base_state = plan_doc['schedule'][0]
                    pool = base_state['active_roster'] + base_state.get('active_bench', []) + base_state.get('backup_bench', [])
                    all_cwl_players_pool_data = [p.get('player', p) for p in pool]
                else: return {"error": "Erro ao recuperar membros."}

            current_roster = []
            current_active_bench = []
            current_backup_bench = []
            warning = plan_doc.get('warning')

            all_pool_entries = [self._get_player_pool_entry(p) for p in all_cwl_players_pool_data if p['tag'] in current_member_tags]

            participation_map = {}
            for day_num in range(1, current_day):
                past_day = next((d for d in plan_doc['schedule'] if d['day'] == day_num), None)
                if past_day:
                    for p in past_day.get('active_roster', []):
                        tag = p.get('player', p).get('tag')
                        if tag: participation_map[tag] = participation_map.get(tag, 0) + 1

            for p_entry in all_pool_entries:
                tag = p_entry['player']['tag']
                p_entry['days_played'] = participation_map.get(tag, 0)

                if tag in actual_roster_tags: current_roster.append(p_entry)
                else:
                    status = player_statuses.get(tag, {}).get('cwl_status', 'active')
                    if status == 'active': current_active_bench.append(p_entry)
                    else: current_backup_bench.append(p_entry)

            new_schedule = plan_doc['schedule'][:current_day - 1]
            for p in current_roster: p['days_played'] += 1
            
            new_schedule.append({
                "day": current_day,
                "active_roster": [p.copy() for p in current_roster],
                "substitutions": [],
                "active_bench": [p.copy() for p in sorted(current_active_bench, key=lambda x: x['player']['town_hall'])],
                "backup_bench": [p.copy() for p in sorted(current_backup_bench, key=lambda x: x['player']['town_hall'])]
            })

            # SIMULAÇÃO FUTURA COM LÓGICA DINÂMICA
            for day in range(current_day + 1, 8):
                # 1. Validação de saídas
                valid_roster = []
                roster_subs_today = []
                for p in current_roster:
                    if p['player']['tag'] in current_member_tags: valid_roster.append(p)
                    else:
                        if p['player']['tag'] not in self.reported_leavers:
                            critical_changes["players_left"].append(p['player'])
                            self.reported_leavers.add(p['player']['tag'])
                        
                        # Tenta substituir quem saiu
                        current_active_bench.sort(key=lambda p: (p['days_played'], -p['player']['town_hall']))
                        rep = None
                        if current_active_bench: rep = current_active_bench.pop(0)
                        elif current_backup_bench: rep = current_backup_bench.pop(0)
                        
                        if rep:
                            valid_roster.append(rep)
                            roster_subs_today.append({"out": p['player'], "in": rep['player'], "reason": "Saiu do clã"})
                            critical_changes["emergency_substitutions"].append({"day": day, "out": p['player'], "in": rep['player'], "reason": "Saiu do clã"})
                        else:
                            if not warning: warning = f"🚨 CRÍTICO: Faltam jogadores no Dia {day}!"
                
                current_roster = valid_roster

                # 2. Preenchimento de vagas vazias (caso roster < team_size)
                fill_needed = team_size - len(current_roster)
                for _ in range(fill_needed):
                    current_active_bench.sort(key=lambda p: (p['days_played'], -p['player']['town_hall']))
                    rep = None
                    if current_active_bench: rep = current_active_bench.pop(0)
                    elif current_backup_bench: rep = current_backup_bench.pop(0)
                    
                    if rep:
                        current_roster.append(rep)
                        roster_subs_today.append({"out": {"name": "(Vaga)", "town_hall": "?"}, "in": rep['player'], "reason": "Preenchendo vaga"})
                    else:
                        break

                # 3. Rotação Dinâmica
                num_to_rotate = self._calculate_rotation_needed(team_size, current_active_bench, current_backup_bench, day)
                
                roster_candidates = sorted(current_roster, key=lambda p: (p['days_played'], -p['player']['town_hall']), reverse=True)
                players_to_sit = roster_candidates[:num_to_rotate]
                
                current_active_bench.sort(key=lambda p: (p['days_played'], -p['player']['town_hall']))
                active_q = deque(current_active_bench)
                current_backup_bench.sort(key=lambda p: (p['days_played'], -p['player']['town_hall']))
                backup_q = deque(current_backup_bench)
                
                incoming = []
                for _ in range(num_to_rotate):
                    if active_q: incoming.append(active_q.popleft())
                
                missing = num_to_rotate - len(incoming)
                for _ in range(missing):
                    if backup_q: incoming.append(backup_q.popleft())

                new_roster = [p for p in current_roster if p not in players_to_sit]
                
                for i, p_out in enumerate(players_to_sit):
                    if i < len(incoming):
                        p_in = incoming[i]
                        new_roster.append(p_in)
                        roster_subs_today.append({"out": p_out['player'], "in": p_in['player'], "reason": f"Rotação ({p_out['days_played']}d -> {p_in['days_played']}d)"})
                        
                        status = player_statuses.get(p_out['player']['tag'], {}).get('cwl_status', 'active')
                        if status == 'active': active_q.append(p_out)
                        else: backup_q.append(p_out)
                    else:
                        new_roster.append(p_out)

                current_roster = new_roster
                for p in current_roster: p['days_played'] += 1
                current_active_bench = list(active_q)
                current_backup_bench = list(backup_q)

                new_schedule.append({
                    "day": day, "active_roster": [p.copy() for p in current_roster], "substitutions": roster_subs_today,
                    "active_bench": [p.copy() for p in current_active_bench], "backup_bench": [p.copy() for p in current_backup_bench]
                })

            all_pool = current_roster + current_active_bench + current_backup_bench
            scores = [{"player": p['player'], "days_played": p['days_played']} for p in all_pool]
            scores.sort(key=lambda x: x['days_played'], reverse=True)

            if any([critical_changes["players_left"], critical_changes["emergency_substitutions"]]):
                await self._send_critical_changes_alert(critical_changes, current_day)

            return {
                "schedule": new_schedule, "participation_score": scores,
                "active_bench_final": current_active_bench, "backup_bench_final": current_backup_bench,
                "warning": warning, "critical_changes": critical_changes
            }

        except Exception as e:
            logger.error(f"Erro ao atualizar plano: {e}", exc_info=True)
            return {"error": str(e)}

    async def _send_critical_changes_alert(self, changes: Dict[str, Any], current_day: int):
        fields = []
        if changes["players_left"]:
            players_list = "\n".join([f"• **{p['name']}**" for p in changes["players_left"]])
            fields.append({ "name": "🚪 Saíram do Clã", "value": players_list, "inline": False })
        if changes["emergency_substitutions"]:
            subs_list = "\n".join([f"Dia {sub['day']}: {sub['out']['name']} -> {sub['in']['name']}" for sub in changes["emergency_substitutions"]])
            fields.append({ "name": "🔄 Substituições Emergência", "value": subs_list, "inline": False })
        await self._send_critical_alert("MUDANÇAS NO ROSTER!", f"Mudanças no Dia {current_day}.", fields=fields)

    async def generate_rotation_plan(self) -> Dict[str, Any]:
        if self.cwl_plan_collection is None: return {"error": "DB não configurado."}
        info = await self._get_current_cwl_war_info()
        if not info: return {"error": "CWL inativa."}

        season, current_day, team_size, active_war = info['season'], info['day_number'], info['team_size'], info['active_war']
        
        if current_day == 8:
            plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
            if plan_doc:
                return { "current_day": current_day, "schedule": plan_doc['schedule'], "participation_score": plan_doc.get('participation_score', []) }
            return {"error": "Histórico não encontrado."}

        try:
            plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
            
            is_invalid = False
            if plan_doc:
                try: 
                    if len(plan_doc['schedule'][0]['active_roster']) != team_size: is_invalid = True
                except: is_invalid = True
            
            if plan_doc is None or is_invalid:
                if not active_war: return {"error": "Guerra ativa não encontrada."}
                plan_data = await self._generate_new_7_day_plan(team_size, active_war, starting_day=current_day)
                if "error" in plan_data: return plan_data
                
                await self.cwl_plan_collection.update_one({"_id": season}, {"$set": { 
                        "schedule": plan_data['schedule'], "participation_score": plan_data['participation_score'],
                        "active_bench_final": plan_data['active_bench_final'], "backup_bench_final": plan_data['backup_bench_final'],
                        "warning": plan_data.get('warning'), "starting_day": plan_data.get('starting_day', current_day),
                        "last_updated": datetime.datetime.now(pytz.utc)
                    }}, upsert=True)
                plan_data["current_day"] = current_day 
                return plan_data
            else:
                plan_data = await self._update_existing_plan(plan_doc, current_day, team_size, active_war)
                if "error" in plan_data: return plan_data 

                await self.cwl_plan_collection.update_one({"_id": season}, {"$set": { 
                        "schedule": plan_data['schedule'], "participation_score": plan_data['participation_score'],
                        "active_bench_final": plan_data['active_bench_final'], "backup_bench_final": plan_data['backup_bench_final'],
                        "warning": plan_data.get('warning'), "critical_changes": plan_data.get('critical_changes', {}),
                        "last_updated": datetime.datetime.now(pytz.utc)
                    }})
                plan_data["current_day"] = current_day 
                return plan_data

        except Exception as e:
            logger.error(f"Erro fatal generate_rotation_plan: {e}", exc_info=True)
            return {"error": str(e)}

    @tasks.loop(minutes=15)
    async def cwl_monitoring_task(self):
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()
        try:
            leavers, _ = await self._detect_roster_changes()
            if leavers:
               players_info = []
               for tag in leavers:
                   if tag not in self.reported_leavers:
                       try:
                           p = await self.bot.api_client.get_player(tag)
                           players_info.append({"name": p.name, "tag": tag, "town_hall": p.town_hall})
                           self.reported_leavers.add(tag)
                       except: pass
               if players_info:
                   fields = [{"name": "Saíram", "value": "\n".join([p['name'] for p in players_info]), "inline": False}]
                   await self._send_critical_alert("JOGADORES SAÍRAM DO CLÃ!", "Verifique o roster.", fields)

            info = await self._get_current_cwl_war_info()
            if not info:
                if self.posted_daily_plans: self.posted_daily_plans.clear(); self.posted_inactivity_alerts.clear()
                return
            
            active_war, day_number, active_war_tag = info['active_war'], info['day_number'], info['war_tag']
            if not active_war or not active_war_tag: return

            plan_data = await self.generate_rotation_plan()
            if "error" not in plan_data:
                validation = await self._validate_plan_vs_reality(plan_data, day_number)
                if not validation["is_valid"]: await self._send_validation_alert(validation, day_number)
            
            await self.post_daily_plan_if_needed(active_war, active_war_tag, info['season'], day_number)
            await self.check_and_alert_inactivity(active_war, active_war_tag)
        except Exception as e: logger.error(f"Erro task CWL: {e}", exc_info=True)

    async def _send_validation_alert(self, validation: Dict[str, Any], current_day: int):
        fields = []
        if validation["missing_players"]:
            fields.append({ "name": "❌ Faltam no Clã", "value": "\n".join([p['name'] for p in validation["missing_players"]]), "inline": False })
        if validation["unexpected_players"]:
            fields.append({ "name": "⚠️ Intrusos na Guerra", "value": "\n".join([p['name'] for p in validation["unexpected_players"]]), "inline": False })
        if fields: await self._send_critical_alert("INCONSISTÊNCIAS PLANO vs REALIDADE", f"Dia {current_day}", fields)

    async def post_daily_plan_if_needed(self, war: coc.ClanWar, war_tag_id: str, season: str, day_number: int):
        if war_tag_id in self.posted_daily_plans: return
        plan_data = await self.generate_rotation_plan()
        if "error" in plan_data: return
        
        current_day_plan = next((p for p in plan_data["schedule"] if p["day"] == day_number), None)
        if not current_day_plan: return
        
        opponent = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
        embed = discord.Embed(title=f"📋 Plano CWL - Dia {day_number} vs {opponent.name}", description=f"Season: {season}", color=discord.Color.blue())
        
        roster_lines = [f"`{i+1:02d}.` {p['player']['name']} (CV{p['player']['town_hall']}) - {p['days_played']}d\n" for i, p in enumerate(sorted(current_day_plan["active_roster"], key=lambda p: p['player']['town_hall'], reverse=True))]
        roster_text = "".join(roster_lines)
        if len(roster_text) > 1024:
            embed.add_field(name="⚔️ Escalação (1)", value=roster_text[:1024], inline=False)
            embed.add_field(name="⚔️ Escalação (2)", value=roster_text[1024:2048], inline=False)
        else:
            embed.add_field(name="⚔️ Escalação", value=roster_text, inline=False)
        
        if current_day_plan["substitutions"]:
            subs_lines = [f"🔴 {s['out']['name']} -> 🟢 {s['in']['name']}" for s in current_day_plan["substitutions"]]
            embed.add_field(name="🔄 Substituições", value="\n".join(subs_lines), inline=False)
        else: embed.add_field(name="🔄 Substituições", value="Manter equipe.", inline=False)

        await self._send_planner_embed(embed)
        self.posted_daily_plans.add(war_tag_id)

    async def check_and_alert_inactivity(self, war: coc.ClanWar, war_tag_id: str):
        time_left = war.end_time.seconds_until
        if not (15 * 60 < time_left < 4 * 3600): return
        inactive = [m for m in (war.clan if war.clan.tag == self.bot.clan_tag else war.opponent).members if len(m.attacks) < war.attacks_per_member]
        if not inactive: return
        alert_id = f"{war_tag_id}-inactivity"
        if alert_id in self.posted_inactivity_alerts: return
        
        embed = discord.Embed(title="🚨 ALERTA INATIVIDADE", description=f"Faltam {int(time_left/3600)}h!", color=discord.Color.red())
        embed.add_field(name="Pendentes", value="\n".join([m.name for m in inactive]), inline=False)
        await self._send_planner_embed(embed)
        self.posted_inactivity_alerts.add(alert_id)

    @commands.command(name='forcarplano')
    @commands.has_permissions(administrator=True)
    async def force_plan_command(self, ctx: commands.Context):
        await ctx.message.add_reaction("🔄")
        self.posted_daily_plans.clear()
        await self.cwl_monitoring_task.coro(self)
        await ctx.message.add_reaction("✅")

    @commands.command(name='statusplano')
    async def plan_status_command(self, ctx: commands.Context):
        info = await self._get_current_cwl_war_info()
        if not info: return await ctx.send("CWL Inativa")
        embed = discord.Embed(title="Status CWL", description=f"Dia {info['day_number']}", color=discord.Color.green())
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    if bot.cwl_planner_channel_id and bot.db is not None: await bot.add_cog(CwlPlannerCog(bot))
