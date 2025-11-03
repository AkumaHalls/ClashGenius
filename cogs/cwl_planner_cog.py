# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
from typing import Dict, List, Any, Optional, Set, Tuple
import datetime
import pytz
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
        # NOVO: Cache de membros para detectar mudanças
        self.last_known_members: Set[str] = set()
        self.reported_leavers: Set[str] = set() # Para não repetir alertas

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

    # NOVO: Método para enviar alertas críticos
    async def _send_critical_alert(self, title: str, description: str, fields: List[Dict[str, Any]] = None):
        """Envia alertas críticos com destaque especial"""
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
        """
        Busca a guerra ativa, o dia atual, a temporada E O TAMANHO da CWL.
        MELHORADO: Mais robusto na detecção do dia atual.
        """
        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group or cwl_group.state == "notInWar":
                return None 

            active_war = None
            day_number = -1
            active_war_tag = None
            team_size = 15
            
            # Procura a guerra ativa (inWar tem prioridade, depois preparation)
            found_war = False
            wars_by_state = {'inWar': [], 'preparation': [], 'warEnded': []}
            
            for i, round_war_tags in enumerate(cwl_group.rounds):
                for war_tag in round_war_tags:
                    if war_tag == '#0': continue
                    try:
                        war = await self.bot.api_client.get_league_war(war_tag)
                        if war.clan.tag == self.bot.clan_tag or war.opponent.tag == self.bot.clan_tag:
                            team_size = war.team_size
                            wars_by_state[war.state].append((war, i + 1, war_tag))
                    except coc.NotFound:
                        continue
            
            # Prioridade: inWar > preparation > warEnded (última guerra)
            if wars_by_state['inWar']:
                active_war, day_number, active_war_tag = wars_by_state['inWar'][0]
            elif wars_by_state['preparation']:
                active_war, day_number, active_war_tag = wars_by_state['preparation'][0]
            elif wars_by_state['warEnded']:
                # Pega a última guerra encerrada para determinar o dia
                last_war, last_day, _ = max(wars_by_state['warEnded'], key=lambda x: x[1])
                day_number = min(last_day + 1, 8) # Próximo dia ou fim (8)
                team_size = last_war.team_size

            if not active_war and day_number == -1:
                day_number = 8 # CWL acabou

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

    # NOVO: Método para detectar mudanças no roster do clã
    async def _detect_roster_changes(self) -> Tuple[Set[str], Set[str]]:
        """
        Detecta quem saiu ou entrou no clã desde a última verificação.
        Retorna: (set de tags que saíram, set de tags que entraram)
        """
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

    # NOVO: Método para verificar inconsistências entre plano e realidade
    async def _validate_plan_vs_reality(self, plan_data: Dict[str, Any], current_day: int) -> Dict[str, Any]:
        """
        Compara o plano salvo com a realidade da guerra atual.
        Retorna um relatório de inconsistências.
        """
        issues = {
            "missing_players": [],  # Jogadores no plano que não estão no clã
            "unexpected_players": [],  # Jogadores na guerra que não estão no plano
            "status_changes": [],  # Mudanças de status (active/backup)
            "is_valid": True
        }
        
        try:
            info = await self._get_current_cwl_war_info()
            if not info or not info['active_war']:
                return issues
            
            active_war = info['active_war']
            our_clan_in_war = active_war.clan if active_war.clan.tag == self.bot.clan_tag else active_war.opponent
            real_roster_tags = {m.tag for m in our_clan_in_war.members}
            
            current_day_plan = next((d for d in plan_data['schedule'] if d['day'] == current_day), None)
            if not current_day_plan:
                return issues
            
            planned_roster_tags = {p['player']['tag'] for p in current_day_plan['active_roster']}
            
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            current_clan_members = {m.tag for m in clan.members}
            
            # Verifica jogadores no plano que não estão mais no clã
            for player_entry in current_day_plan['active_roster']:
                player_tag = player_entry['player']['tag']
                if player_tag not in current_clan_members:
                    issues["missing_players"].append(player_entry['player'])
                    issues["is_valid"] = False
            
            # Verifica jogadores na guerra que não estavam no plano
            for member_tag in real_roster_tags:
                if member_tag not in planned_roster_tags:
                    try:
                        member = await self.bot.api_client.get_player(member_tag)
                        issues["unexpected_players"].append({
                            "name": member.name,
                            "tag": member.tag,
                            "town_hall": member.town_hall
                        })
                        issues["is_valid"] = False
                    except:
                        pass
            
            return issues
        
        except Exception as e:
            logger.error(f"Erro ao validar plano vs realidade: {e}", exc_info=True)
            return issues

    async def get_cwl_members_for_planning(self) -> Optional[List[Dict[str, Any]]]:
        try:
            await self.bot.coc_client_ready.wait()
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group:
                logger.warning("get_cwl_members_for_planning: O clã não parece estar em uma CWL.")
                return None

            our_clan_from_cwl = next((c for c in cwl_group.clans if c.tag == self.bot.clan_tag), None)
            
            if not our_clan_from_cwl:
                logger.warning("get_cwl_members_for_planning: Não foi possível encontrar o clã no grupo da CWL.")
                return None

            return [{"name": m.name, "tag": m.tag, "town_hall": m.town_hall} for m in our_clan_from_cwl.members]
        except coc.NotFound:
            logger.warning("get_cwl_members_for_planning: coc.NotFound - O clã não está em CWL.")
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar membros da CWL para o planeamento: {e}", exc_info=True)
            return None

    def _get_player_pool_entry(self, player_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria a estrutura de dados padrão para um jogador no plano."""
        return {"player": player_data, "days_played": 0}

    async def _generate_new_7_day_plan(self, team_size: int, active_war: coc.ClanWar, starting_day: int = 1) -> Dict[str, Any]:
        """
        MELHORADO: Gera um plano de 7 dias com rotação justa.
        Agora suporta começar em qualquer dia da CWL.
        
        Args:
            team_size: Tamanho da guerra (15 ou 30)
            active_war: Guerra ativa para usar como base
            starting_day: Dia atual da CWL (1-7)
        """
        cwl_members = await self.get_cwl_members_for_planning()
        if cwl_members is None:
            return {"error": "Não foi possível buscar os membros inscritos na CWL. O clã está em uma liga de guerra?"}

        roster_size = team_size 
        
        clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
        current_member_tags = {m.tag for m in clan.members}
        
        db_cog = self.bot.get_cog("Banco de Dados")
        player_statuses = await db_cog.load_player_notes_from_db() if db_cog else {}
        
        # Pega o roster REAL da guerra ativa
        our_clan_in_war = active_war.clan if active_war.clan.tag == self.bot.clan_tag else active_war.opponent
        actual_roster_tags = {m.tag for m in our_clan_in_war.members}
        
        logger.info(f"Gerando plano começando do Dia {starting_day}. Roster real detectado com {len(actual_roster_tags)} membros.")

        # Constrói os pools
        current_roster = []
        current_active_bench = deque()
        current_backup_bench = deque()
        warning = None

        all_cwl_players_pool = []
        for member in cwl_members:
            if member['tag'] in current_member_tags:
                all_cwl_players_pool.append(self._get_player_pool_entry(member))
        
        # Validações
        if len(actual_roster_tags) < roster_size:
            warning = f"⚠️ Aviso Dia {starting_day}: Roster real ({len(actual_roster_tags)}) é MENOR que o tamanho da guerra ({team_size})."
            logger.warning(warning)
        elif len(actual_roster_tags) > roster_size:
            warning = f"⚠️ Aviso Dia {starting_day}: Roster real ({len(actual_roster_tags)}) é MAIOR que o tamanho da guerra ({team_size})."
            logger.warning(warning)

        # Distribui jogadores
        for p_entry in all_cwl_players_pool:
            player_tag = p_entry['player']['tag']
            
            if player_tag in actual_roster_tags:
                current_roster.append(p_entry)
            else:
                status = player_statuses.get(player_tag, {}).get('cwl_status', 'active')
                if status == 'active':
                    current_active_bench.append(p_entry)
                else:
                    current_backup_bench.append(p_entry)
        
        # Ordena os bancos
        current_active_bench = deque(sorted(current_active_bench, key=lambda p: p['player']['town_hall']))
        current_backup_bench = deque(sorted(current_backup_bench, key=lambda p: p['player']['town_hall'], reverse=True))

        logger.info(f"Pools iniciais: {len(current_roster)} roster, {len(current_active_bench)} banco ativo, {len(current_backup_bench)} banco backup.")
        
        # NOVO: Ajusta days_played baseado no starting_day
        for p in current_roster:
            p['days_played'] = starting_day  # Se começar no dia 2, eles já jogaram 2 dias
        
        # Para o banco, assume que não jogaram ainda (ou menos que o roster)
        for p in list(current_active_bench) + list(current_backup_bench):
            p['days_played'] = max(0, starting_day - 1)  # Jogaram 1 dia a menos que o roster

        # Gera o cronograma
        schedule = []
        
        # Adiciona o dia atual
        schedule.append({
            "day": starting_day,
            "active_roster": [p.copy() for p in current_roster],
            "substitutions": [],
            "active_bench": [p.copy() for p in current_active_bench],
            "backup_bench": [p.copy() for p in current_backup_bench]
        })

        # Gera os próximos dias (até o dia 7)
        num_to_rotate = 5 if roster_size == 30 else 3

        for day in range(starting_day + 1, 8):
            substitutions = []
            
            roster_sorted = sorted(current_roster, key=lambda p: p['days_played'], reverse=True)
            players_to_sit = roster_sorted[:num_to_rotate]
            players_to_play = []

            for _ in range(num_to_rotate):
                if current_active_bench:
                    players_to_play.append(current_active_bench.popleft())
            
            needed = num_to_rotate - len(players_to_play)
            if needed > 0:
                if not warning:
                    warning = f"⚠️ Aviso Dia {day}: Banco de 'Ativos' vazio. 'Backups' serão usados na rotação."
                for _ in range(needed):
                    if current_backup_bench:
                        players_to_play.append(current_backup_bench.popleft())
            
            new_roster = [p for p in current_roster if p not in players_to_sit]
            
            for i in range(len(players_to_sit)):
                player_out = players_to_sit[i]
                
                if i < len(players_to_play):
                    player_in = players_to_play[i]
                    new_roster.append(player_in)
                    
                    status_out = player_statuses.get(player_out['player']['tag'], {}).get('cwl_status', 'active')
                    if status_out == 'active':
                        current_active_bench.append(player_out) 
                    else:
                        current_backup_bench.append(player_out) 

                    substitutions.append({
                        "out": player_out['player'], 
                        "in": player_in['player'],
                        "reason": f"Rotação justa (Saiu: {player_out['days_played']}d | Entrou: {player_in['days_played']}d)"
                    })
                else:
                    new_roster.append(player_out)

            for p in new_roster:
                p['days_played'] += 1
            
            current_roster = new_roster

            schedule.append({
                "day": day,
                "active_roster": [p.copy() for p in current_roster],
                "substitutions": substitutions,
                "active_bench": [p.copy() for p in current_active_bench],
                "backup_bench": [p.copy() for p in current_backup_bench]
            })
        
        all_players_pool = current_roster + list(current_active_bench) + list(current_backup_bench)
        participation_score = [
            {"player": p['player'], "days_played": p['days_played']}
            for p in all_players_pool
        ]
        participation_score.sort(key=lambda x: x['days_played'], reverse=True)

        return {
            "schedule": schedule,
            "participation_score": participation_score,
            "active_bench_final": list(current_active_bench), 
            "backup_bench_final": list(current_backup_bench),
            "warning": warning,
            "starting_day": starting_day  # NOVO: Marca de onde começou o plano
        }

    async def _update_existing_plan(self, plan_doc: Dict[str, Any], current_day: int, team_size: int) -> Dict[str, Any]:
        """
        MELHORADO: Recalcula o futuro (Dias atuais até 7) com validação robusta.
        Agora detecta e reporta mudanças críticas no roster.
        """
        logger.info(f"Atualizando plano (Dia Atual: {current_day})...")
        
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            current_member_tags = {m.tag for m in clan.members}
            db_cog = self.bot.get_cog("Banco de Dados")
            player_statuses = await db_cog.load_player_notes_from_db() if db_cog else {}

            # NOVO: Detecta mudanças críticas antes de recalcular
            critical_changes = {
                "players_left": [],
                "status_changes": [],
                "emergency_substitutions": []
            }

            # Carrega o estado base (Dia 1)
            base_state_doc = next((d for d in plan_doc['schedule'] if d['day'] == 1), None)
            if not base_state_doc:
                raise KeyError("Plano salvo não contém o Dia 1. Forçando recriação.")

            # Migra/normaliza dados
            current_roster = []
            for p_data in base_state_doc.get('active_roster', []):
                p_entry = {'player': p_data, 'days_played': 1} if 'player' not in p_data else p_data.copy()
                p_entry['days_played'] = 1
                current_roster.append(p_entry)

            current_active_bench = deque()
            for p_data in base_state_doc.get('active_bench', []):
                p_entry = {'player': p_data, 'days_played': 0} if 'player' not in p_data else p_data.copy()
                p_entry['days_played'] = 0
                current_active_bench.append(p_entry)

            current_backup_bench = deque()
            for p_data in base_state_doc.get('backup_bench', []):
                p_entry = {'player': p_data, 'days_played': 0} if 'player' not in p_data else p_data.copy()
                p_entry['days_played'] = 0
                current_backup_bench.append(p_entry)

            # Simula do Dia 2 até o Dia atual para acumular days_played corretamente
            num_to_rotate = 5 if team_size == 30 else 3
            
            for simulate_day in range(2, current_day + 1):
                # Incrementa days_played para quem está no roster
                for p in current_roster:
                    p['days_played'] += 1
                
                # Simula rotação básica (sem substituições reais, só para manter contador)
                if simulate_day < current_day:  # Não roda no dia atual, só até o anterior
                    roster_sorted = sorted(current_roster, key=lambda p: p['days_played'], reverse=True)
                    players_to_sit = roster_sorted[:num_to_rotate]
                    
                    for _ in range(num_to_rotate):
                        if current_active_bench:
                            current_active_bench.popleft()
                    
                    for player_out in players_to_sit:
                        current_active_bench.append(player_out)

            logger.info(f"Simulação até Dia {current_day} concluída. Recalculando do Dia {current_day} até 7...")

            # Agora recalcula do dia atual até o dia 7
            new_schedule = plan_doc['schedule'][:current_day]  # Mantém histórico
            warning = plan_doc.get('warning')

            for day in range(current_day, 8):
                logger.debug(f"Processando Dia {day}...")
                
                # Revalida pools
                final_roster_pool = []
                roster_substitutions_this_day = []
                
                # Valida Roster
                for p_entry in current_roster:
                    player_tag = p_entry['player']['tag']
                    player_name = p_entry['player']['name']
                    
                    # Jogador saiu do clã
                    if player_tag not in current_member_tags:
                        logger.warning(f"Dia {day}: {player_name} saiu do clã! Substituindo...")
                        
                        # NOVO: Adiciona ao relatório de mudanças críticas
                        if player_tag not in self.reported_leavers:
                            critical_changes["players_left"].append(p_entry['player'])
                            self.reported_leavers.add(player_tag)
                        
                        replacement = None
                        if current_active_bench: 
                            replacement = current_active_bench.popleft()
                        elif current_backup_bench: 
                            replacement = current_backup_bench.popleft()
                        
                        if replacement:
                            final_roster_pool.append(replacement)
                            critical_changes["emergency_substitutions"].append({
                                "day": day,
                                "out": p_entry['player'],
                                "in": replacement['player'],
                                "reason": "Jogador saiu do clã"
                            })
                            roster_substitutions_this_day.append({
                                "out": p_entry['player'], 
                                "in": replacement['player'], 
                                "reason": f"🚨 EMERGÊNCIA (Dia {day}): {player_name} saiu do clã"
                            })
                        else:
                            logger.error(f"Dia {day}: SEM SUBSTITUTO para {player_name}!")
                            if not warning:
                                warning = f"🚨 CRÍTICO: Faltam jogadores no Dia {day}!"
                        continue

                    # Mudança de status
                    current_status = player_statuses.get(player_tag, {}).get('cwl_status', 'active')
                    if current_status == 'backup':
                        logger.info(f"Dia {day}: {player_name} mudou para 'Backup'. Movendo...")
                        current_backup_bench.append(p_entry)
                        
                        critical_changes["status_changes"].append({
                            "player": p_entry['player'],
                            "from": "active",
                            "to": "backup",
                            "day": day
                        })
                        
                        replacement = None
                        if current_active_bench: 
                            replacement = current_active_bench.popleft()
                        
                        if replacement:
                            final_roster_pool.append(replacement)
                            roster_substitutions_this_day.append({
                                "out": p_entry['player'], 
                                "in": replacement['player'], 
                                "reason": f"Mudança de Status (Dia {day}): {player_name} → Backup"
                            })
                        else:
                            logger.error(f"Dia {day}: Sem substituto para {player_name} (mudou para Backup).")
                        continue
                    
                    final_roster_pool.append(p_entry)
                
                # Revalida bancos
                validated_active_bench = deque()
                validated_backup_bench = deque()
                
                for p_entry in current_active_bench:
                    player_tag = p_entry['player']['tag']
                    if player_tag not in current_member_tags: 
                        if player_tag not in self.reported_leavers:
                            critical_changes["players_left"].append(p_entry['player'])
                            self.reported_leavers.add(player_tag)
                        continue
                    
                    current_status = player_statuses.get(player_tag, {}).get('cwl_status', 'active')
                    if current_status == 'active': 
                        validated_active_bench.append(p_entry)
                    else: 
                        validated_backup_bench.append(p_entry)
                
                for p_entry in current_backup_bench:
                    player_tag = p_entry['player']['tag']
                    if player_tag not in current_member_tags: 
                        if player_tag not in self.reported_leavers:
                            critical_changes["players_left"].append(p_entry['player'])
                            self.reported_leavers.add(player_tag)
                        continue
                    
                    current_status = player_statuses.get(player_tag, {}).get('cwl_status', 'active')
                    if current_status == 'active': 
                        validated_active_bench.append(p_entry)
                    else: 
                        validated_backup_bench.append(p_entry)
                
                current_roster = final_roster_pool
                current_active_bench = deque(sorted(validated_active_bench, key=lambda p: p['player']['town_hall']))
                current_backup_bench = deque(sorted(validated_backup_bench, key=lambda p: p['player']['town_hall'], reverse=True))

                # Rotação justa (se não for o dia atual de atualização)
                substitutions = list(roster_substitutions_this_day)
                
                if day > current_day:  # Só faz rotação programada nos dias futuros
                    roster_sorted = sorted(current_roster, key=lambda p: p['days_played'], reverse=True)
                    players_to_sit = roster_sorted[:num_to_rotate]
                    players_to_play = []

                    for _ in range(num_to_rotate):
                        if current_active_bench:
                            players_to_play.append(current_active_bench.popleft())
                    
                    needed = num_to_rotate - len(players_to_play)
                    if needed > 0:
                        if not warning: 
                            warning = f"⚠️ Aviso Dia {day}: Banco de 'Ativos' vazio. 'Backups' na rotação."
                        for _ in range(needed):
                            if current_backup_bench:
                                players_to_play.append(current_backup_bench.popleft())
                    
                    new_roster = [p for p in current_roster if p not in players_to_sit]
                    
                    for i in range(len(players_to_sit)):
                        player_out = players_to_sit[i]
                        if i < len(players_to_play):
                            player_in = players_to_play[i]
                            new_roster.append(player_in)
                            
                            status_out = player_statuses.get(player_out['player']['tag'], {}).get('cwl_status', 'active')
                            if status_out == 'active': 
                                current_active_bench.append(player_out)
                            else: 
                                current_backup_bench.append(player_out)

                            substitutions.append({
                                "out": player_out['player'], 
                                "in": player_in['player'],
                                "reason": f"Rotação justa (Saiu: {player_out['days_played']}d | Entrou: {player_in['days_played']}d)"
                            })
                        else:
                            new_roster.append(player_out)
                    
                    current_roster = new_roster

                # Incrementa days_played
                for p in current_roster:
                    p['days_played'] += 1

                # Salva o dia
                new_schedule.append({
                    "day": day,
                    "active_roster": [p.copy() for p in current_roster],
                    "substitutions": substitutions,
                    "active_bench": [p.copy() for p in current_active_bench],
                    "backup_bench": [p.copy() for p in current_backup_bench]
                })

            # Gera placar final
            all_players_pool = current_roster + list(current_active_bench) + list(current_backup_bench)
            participation_score = [
                {"player": p['player'], "days_played": p['days_played']}
                for p in all_players_pool
            ]
            participation_score.sort(key=lambda x: x['days_played'], reverse=True)

            # NOVO: Envia alerta se houver mudanças críticas
            if any([critical_changes["players_left"], critical_changes["emergency_substitutions"], critical_changes["status_changes"]]):
                await self._send_critical_changes_alert(critical_changes, current_day)

            logger.info("Recálculo completo do plano concluído.")
            return {
                "schedule": new_schedule,
                "participation_score": participation_score,
                "active_bench_final": list(current_active_bench),
                "backup_bench_final": list(current_backup_bench),
                "warning": warning,
                "critical_changes": critical_changes  # NOVO: Retorna as mudanças
            }

        except KeyError as e:
            logger.error(f"Erro de Chave ao ATUALIZAR plano: {e}. Forçando recriação.", exc_info=True)
            return {"error": "MIGRATION_FAILED"}
        except Exception as e:
            logger.error(f"Erro crítico ao ATUALIZAR plano: {e}", exc_info=True)
            return {"error": f"Erro ao atualizar: {e}"}

    # NOVO: Método para enviar alerta de mudanças críticas
    async def _send_critical_changes_alert(self, changes: Dict[str, Any], current_day: int):
        """Envia um alerta detalhado sobre mudanças críticas no roster"""
        fields = []
        
        if changes["players_left"]:
            # <<< INÍCIO DA CORREÇÃO >>>
            # O erro estava aqui. A string "
            # " estava em uma linha separada, quebrando a sintaxe do Python.
            players_list = "\n".join([
            # <<< FIM DA CORREÇÃO >>>
                f"• **{p['name']}** (CV{p['town_hall']}) - Tag: `{p['tag']}`"
                for p in changes["players_left"]
            ])
            fields.append({
                "name": "🚪 Jogadores que SAÍRAM do Clã",
                "value": players_list,
                "inline": False
            })
        
        if changes["emergency_substitutions"]:
            subs_list = "\n".join([
                f"**Dia {sub['day']}:** {sub['out']['name']} → {sub['in']['name']}\n└ Motivo: {sub['reason']}"
                for sub in changes["emergency_substitutions"]
            ])
            fields.append({
                "name": "🔄 Substituições de EMERGÊNCIA",
                "value": subs_list,
                "inline": False
            })
        
        if changes["status_changes"]:
            status_list = "\n".join([
                f"• **{sc['player']['name']}** (Dia {sc['day']}): {sc['from']} → {sc['to']}"
                for sc in changes["status_changes"]
            ])
            fields.append({
                "name": "📊 Mudanças de Status",
                "value": status_list,
                "inline": False
            })
        
        await self._send_critical_alert(
            title="MUDANÇAS CRÍTICAS NO ROSTER DA CWL!",
            description=f"Foram detectadas mudanças importantes no roster durante o Dia {current_day} da CWL. **Verifique imediatamente e ajuste o plano se necessário!**",
            fields=fields
        )

    async def generate_rotation_plan(self) -> Dict[str, Any]:
        """
        MELHORADO: Função principal da API com melhor suporte para dias intermediários.
        """
        if self.cwl_plan_collection is None:
            return {"error": "O banco de dados não está configurado para salvar o plano."}

        info = await self._get_current_cwl_war_info()
        if not info:
            return {"error": "O clã não está em uma guerra CWL ativa no momento."}

        season = info['season']
        current_day = info['day_number']
        team_size = info['team_size']
        active_war = info['active_war']
        
        if current_day == 8:
            plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
            if plan_doc:
                logger.info(f"CWL Dia {current_day}. Retornando plano final.")
                
                participation_score = plan_doc.get('participation_score', [])
                if not participation_score:
                    try:
                        all_players_pool = plan_doc['schedule'][-1]['active_roster'] + \
                                         plan_doc['schedule'][-1].get('active_bench', []) + \
                                         plan_doc['schedule'][-1].get('backup_bench', [])
                        participation_score = []
                        for p_data in all_players_pool:
                            player_info = p_data.get('player', p_data) 
                            days_played = p_data.get('days_played', 7) 
                            participation_score.append({"player": player_info, "days_played": days_played})
                        participation_score.sort(key=lambda x: x['days_played'], reverse=True)
                    except Exception as e:
                        logger.error(f"Erro ao calcular placar final: {e}")
                        participation_score = []
                
                return {
                    "current_day": current_day,
                    "schedule": plan_doc['schedule'],
                    "participation_score": participation_score,
                    "active_bench_final": plan_doc.get('active_bench_final', []),
                    "backup_bench_final": plan_doc.get('backup_bench_final', [])
                }
            else:
                return {"error": "CWL terminada, mas nenhum plano encontrado no histórico."}

        try:
            plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
            
            # Verifica se é formato antigo
            is_old_format = False
            if plan_doc:
                try:
                    first_player = plan_doc['schedule'][0]['active_roster'][0]
                    if 'player' not in first_player:
                        is_old_format = True
                        logger.warning(f"Plano antigo detectado para {season}. Gerando novo.")
                except (IndexError, KeyError, TypeError) as e:
                    is_old_format = True
                    logger.warning(f"Plano malformado detectado ({e}). Gerando novo.")
            
            # Verifica mudança de tamanho
            is_wrong_size = False
            if plan_doc and not is_old_format:
                try:
                    saved_size = len(plan_doc['schedule'][0]['active_roster'])
                    if saved_size != team_size:
                        is_wrong_size = True
                        logger.warning(f"Mudança de tamanho detectada! (Salvo: {saved_size}, Atual: {team_size})")
                except Exception:
                    pass

            # Se não existe plano OU é formato antigo OU mudou o tamanho -> CRIA NOVO
            if plan_doc is None or is_old_format or is_wrong_size:
                if not active_war:
                    return {"error": f"Erro: Não foi possível encontrar a guerra ativa do Dia {current_day}."}
                
                logger.info(f"Gerando NOVO plano de CWL ({team_size}v{team_size}) para {season} a partir do Dia {current_day}...")
                plan_data = await self._generate_new_7_day_plan(team_size, active_war, starting_day=current_day)
                
                if "error" in plan_data: 
                    return plan_data
                
                await self.cwl_plan_collection.update_one(
                    {"_id": season},
                    {"$set": { 
                        "schedule": plan_data['schedule'],
                        "participation_score": plan_data['participation_score'],
                        "active_bench_final": plan_data['active_bench_final'],
                        "backup_bench_final": plan_data['backup_bench_final'],
                        "warning": plan_data.get('warning'),
                        "starting_day": plan_data.get('starting_day', current_day),
                        "last_updated": datetime.datetime.now(pytz.utc)
                    }},
                    upsert=True
                )
                logger.info(f"Novo plano para {season} salvo no DB.")
                plan_data["current_day"] = current_day 
                return plan_data
            
            # Se existe plano válido -> ATUALIZA
            else:
                logger.info(f"Atualizando plano existente para {season} (Dia {current_day})...")
                plan_data = await self._update_existing_plan(plan_doc, current_day, team_size)
                
                # Se falhou a migração, apaga e recria
                if "error" in plan_data and plan_data["error"] == "MIGRATION_FAILED": 
                    logger.error(f"Falha na atualização. Forçando novo plano.")
                    await self.cwl_plan_collection.delete_one({"_id": season})
                    return await self.generate_rotation_plan()
                elif "error" in plan_data:
                    return plan_data

                # Salva o plano atualizado
                await self.cwl_plan_collection.update_one(
                    {"_id": season},
                    {"$set": { 
                        "schedule": plan_data['schedule'],
                        "participation_score": plan_data['participation_score'],
                        "active_bench_final": plan_data['active_bench_final'],
                        "backup_bench_final": plan_data['backup_bench_final'],
                        "warning": plan_data.get('warning'),
                        "critical_changes": plan_data.get('critical_changes', {}),  # NOVO
                        "last_updated": datetime.datetime.now(pytz.utc)
                    }}
                )
                logger.info(f"Plano para {season} atualizado no DB.")
                plan_data["current_day"] = current_day 
                return plan_data

        except Exception as e:
            logger.error(f"Erro fatal em generate_rotation_plan: {e}", exc_info=True)
            return {"error": f"Erro fatal: {e}"}

    @tasks.loop(minutes=15)
    async def cwl_monitoring_task(self):
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()
        
        try:
            logger.info("Verificando status da CWL...")
            
            # NOVO: Detecta mudanças no roster antes de tudo
            leavers, joiners = await self._detect_roster_changes()
            
            if leavers:
                # Alerta imediato sobre jogadores que saíram
                players_info = []
                for tag in leavers:
                    if tag not in self.reported_leavers:
                        try:
                            player = await self.bot.api_client.get_player(tag)
                            players_info.append({
                                "name": player.name,
                                "tag": player.tag,
                                "town_hall": player.town_hall
                            })
                            self.reported_leavers.add(tag)
                        except:
                            pass
                
                if players_info:
                    await self._send_critical_alert(
                        title="JOGADORES SAÍRAM DO CLÃ DURANTE A CWL!",
                        description="Os seguintes jogadores saíram do clã. O plano será recalculado automaticamente.",
                        fields=[{
                            "name": "Jogadores que Saíram",
                            "value": "\n".join([f"• **{p['name']}** (CV{p['town_hall']}) - `{p['tag']}`" for p in players_info]),
                            "inline": False
                        }]
                    )
            
            info = await self._get_current_cwl_war_info()

            if not info:
                if self.posted_daily_plans:
                    logger.info("CWL não está em guerra. Limpando cache.")
                    self.posted_daily_plans.clear()
                    self.posted_inactivity_alerts.clear()
                    self.reported_leavers.clear()
                return
            
            active_war = info['active_war']
            day_number = info['day_number']
            season = info['season']
            active_war_tag_str = info['war_tag']

            if not active_war or not active_war_tag_str:
                logger.info(f"CWL ativa (Dia {day_number}), mas sem guerra atual (entre rounds).")
                return

            logger.info(f"Guerra ativa: Dia {day_number} vs {active_war.opponent.name}.")
            
            # NOVO: Valida o plano contra a realidade antes de postar
            plan_data = await self.generate_rotation_plan()
            if "error" not in plan_data:
                validation = await self._validate_plan_vs_reality(plan_data, day_number)
                if not validation["is_valid"]:
                    await self._send_validation_alert(validation, day_number)
            
            await self.post_daily_plan_if_needed(active_war, active_war_tag_str, season, day_number)
            await self.check_and_alert_inactivity(active_war, active_war_tag_str)

        except Exception as e:
            logger.error(f"Erro na tarefa de monitorização da CWL: {e}", exc_info=True)

    # NOVO: Método para enviar alertas de validação
    async def _send_validation_alert(self, validation: Dict[str, Any], current_day: int):
        """Envia alerta sobre inconsistências entre plano e realidade"""
        fields = []
        
        if validation["missing_players"]:
            players_list = "\n".join([
                f"• **{p['name']}** (CV{p['town_hall']})"
                for p in validation["missing_players"]
            ])
            fields.append({
                "name": "❌ No Plano, mas NÃO no Clã",
                "value": players_list,
                "inline": False
            })
        
        if validation["unexpected_players"]:
            players_list = "\n".join([
                f"• **{p['name']}** (CV{p['town_hall']})"
                for p in validation["unexpected_players"]
            ])
            fields.append({
                "name": "⚠️ Na Guerra, mas NÃO no Plano",
                "value": players_list,
                "inline": False
            })
        
        if fields:
            await self._send_critical_alert(
                title=f"INCONSISTÊNCIAS NO PLANO DA CWL - DIA {current_day}!",
                description="O roster da guerra atual não corresponde ao plano gerado. Verifique imediatamente!",
                fields=fields
            )

    async def post_daily_plan_if_needed(self, war: coc.ClanWar, war_tag_id: str, season: str, day_number: int):
        if war_tag_id in self.posted_daily_plans:
            logger.info(f"Plano para o Dia {day_number} já postado. Ignorando.")
            return

        logger.info(f"Postando plano para o Dia {day_number}...")
        
        plan_data = await self.generate_rotation_plan() 
        if "error" in plan_data: 
            logger.error(f"Erro ao gerar plano: {plan_data['error']}")
            if "não está em uma guerra CWL ativa" in plan_data['error']:
                self.posted_daily_plans.add(war_tag_id)
            return

        current_day_plan = next((p for p in plan_data["schedule"] if p["day"] == day_number), None)
        
        if not current_day_plan: 
            logger.warning(f"Nenhum plano encontrado para o Dia {day_number}.")
            return
        
        opponent = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan

        embed = discord.Embed(
            title=f"📋 Plano Estratégico CWL - Dia {day_number} vs {opponent.name}",
            description=f"Temporada: {season}. Foco total para garantir a vitória!",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(pytz.utc)
        )
        
        roster_list = []
        sorted_roster_for_display = sorted(current_day_plan["active_roster"], key=lambda p: p['player']['town_hall'], reverse=True)
        
        for i, p_entry in enumerate(sorted_roster_for_display):
            player_data = p_entry.get('player') 
            days = p_entry.get('days_played', 0)
            roster_list.append(f"`{i+1:02d}.` {player_data.get('name', 'N/A')} (CV{player_data.get('town_hall', '?')}) - {days} dias")
        
        roster_str = "\n".join(roster_list)

        embed.add_field(
            name=f"⚔️ Escalação Ativa ({len(roster_list)}v{len(roster_list)})", 
            value=roster_str or "N/A", 
            inline=False
        )

        if current_day_plan["substitutions"]:
            subs_str = ""
            for sub in current_day_plan["substitutions"]:
                subs_str += f"🔴 **Sai:** {sub['out']['name']} (CV{sub['out']['town_hall']})\n"
                subs_str += f"🟢 **Entra:** {sub['in']['name']} (CV{sub['in']['town_hall']})\n"
                subs_str += f"_*{sub['reason']}_*\n"
            embed.add_field(name="🔄 Alterações na Equipa", value=subs_str.strip(), inline=False)
        else:
            default_message = "Manter a escalação do dia anterior." if day_number > 1 else "Escalação inicial definida. Vamos com tudo!"
            embed.add_field(name="🔄 Alterações na Equipa", value=default_message, inline=False)
        
        # NOVO: Mostra banco ativo
        if current_day_plan.get("active_bench"):
            bench_list = [f"• {p['player']['name']} (CV{p['player']['town_hall']})" 
                         for p in sorted(current_day_plan["active_bench"], 
                                       key=lambda x: x['player']['town_hall'], reverse=True)[:5]]
            if bench_list:
                embed.add_field(
                    name=f"🪑 Banco Ativo (Próximos {len(bench_list)})",
                    value="\n".join(bench_list),
                    inline=True
                )
        
        if plan_data.get("warning"):
            embed.add_field(name="⚠️ Aviso da IA", value=plan_data["warning"], inline=False)

        # NOVO: Mostra se houve mudanças críticas
        if plan_data.get("critical_changes"):
            changes = plan_data["critical_changes"]
            if any([changes.get("players_left"), changes.get("emergency_substitutions")]):
                embed.color = discord.Color.orange()
                embed.add_field(
                    name="🚨 Mudanças Críticas Detectadas",
                    value="Foram feitas substituições de emergência. Veja as mensagens anteriores.",
                    inline=False
                )

        if opponent.badge:
            embed.set_thumbnail(url=opponent.badge.url)

        embed.set_footer(text=f"Atualizado automaticamente • Dia {day_number}/7")

        await self._send_planner_embed(embed)
        self.posted_daily_plans.add(war_tag_id)
        logger.info(f"Plano para o Dia {day_number} enviado.")

    async def check_and_alert_inactivity(self, war: coc.ClanWar, war_tag_id: str):
        time_left = war.end_time.seconds_until
        if not (15 * 60 < time_left < 4 * 3600): 
            return

        our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
        inactive_members = [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member]

        if not inactive_members: 
            return

        alert_id = f"{war_tag_id}-inactivity"
        if alert_id in self.posted_inactivity_alerts: 
            return
            
        logger.warning(f"Detectando inatividade: {len(inactive_members)} membros.")

        hours, remainder = divmod(int(time_left), 3600)
        minutes, _ = divmod(remainder, 60)
        time_left_str = f"{hours}h e {minutes}m"

        embed = discord.Embed(
            title=f"🚨 ALERTA DE INATIVIDADE NA CWL!",
            description=f"A guerra contra **{war.opponent.name}** termina em aproximadamente **{time_left_str}**!",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(pytz.utc)
        )
        inactive_str = "\n".join([f"**{m.name}** (CV{m.town_hall}) - {len(m.attacks)}/{war.attacks_per_member} ataques" for m in inactive_members])
        embed.add_field(name=f"⏰ Jogadores com Ataques Pendentes ({len(inactive_members)})", value=inactive_str, inline=False)
        embed.set_footer(text="É crucial que todos os ataques sejam feitos!")
        
        if war.opponent.badge:
            embed.set_thumbnail(url=war.opponent.badge.url)

        await self._send_planner_embed(embed)
        self.posted_inactivity_alerts.add(alert_id)

    @commands.command(name='forcarplano', aliases=['forceplan'])
    @commands.has_permissions(administrator=True)
    async def force_plan_command(self, ctx: commands.Context):
        """(Admin) Força a verificação e postagem do plano de CWL do dia atual."""
        await ctx.message.add_reaction("🔄")
        logger.info(f"Comando !forcarplano invocado por {ctx.author.name}.")
        
        try:
            self.posted_daily_plans.clear() 
            self.reported_leavers.clear()  # NOVO: Limpa cache de leavers
            await self.cwl_monitoring_task.coro(self) 
            
            await ctx.message.add_reaction("✅")
            await ctx.message.remove_reaction("🔄", self.bot.user)
        except Exception as e:
            await ctx.message.add_reaction("❌")
            await ctx.message.remove_reaction("🔄", self.bot.user)
            await ctx.send(f"Ocorreu um erro: `{e}`")
            logger.error(f"Erro ao executar !forcarplano: {e}", exc_info=True)

    # NOVO: Comando para ver status do plano
    @commands.command(name='statusplano', aliases=['planstatus'])
    async def plan_status_command(self, ctx: commands.Context):
        """Mostra o status atual do plano de CWL"""
        await ctx.message.add_reaction("🔍")
        
        try:
            info = await self._get_current_cwl_war_info()
            if not info:
                await ctx.send("❌ O clã não está em uma CWL ativa no momento.")
                return
            
            plan_data = await self.generate_rotation_plan()
            if "error" in plan_data:
                await ctx.send(f"❌ Erro ao gerar plano: {plan_data['error']}")
                return
            
            current_day = info['day_number']
            season = info['season']
            
            embed = discord.Embed(
                title=f"📊 Status do Plano de CWL",
                description=f"**Temporada:** {season}\n**Dia Atual:** {current_day}/7",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(pytz.utc)
            )
            
            # Mostra próximas rotações
            future_days = [d for d in plan_data['schedule'] if d['day'] > current_day]
            if future_days:
                next_day = future_days[0]
                if next_day['substitutions']:
                    subs_preview = "\n".join([
                        f"• {sub['out']['name']} → {sub['in']['name']}"
                        for sub in next_day['substitutions'][:3]
                    ])
                    embed.add_field(
                        name=f"🔄 Próximas Alterações (Dia {next_day['day']})",
                        value=subs_preview + ("\n..." if len(next_day['substitutions']) > 3 else ""),
                        inline=False
                    )
            
            # Mostra estatísticas
            current_plan = next((d for d in plan_data['schedule'] if d['day'] == current_day), None)
            if current_plan:
                embed.add_field(
                    name="📈 Estatísticas",
                    value=f"**Roster Ativo:** {len(current_plan['active_roster'])}\n"
                          f"**Banco Ativo:** {len(current_plan.get('active_bench', []))}\n"
                          f"**Banco Backup:** {len(current_plan.get('backup_bench', []))}",
                    inline=True
                )
            
            # Mostra avisos
            if plan_data.get("warning"):
                embed.add_field(
                    name="⚠️ Avisos",
                    value=plan_data["warning"],
                    inline=False
                )
            
            embed.set_footer(text=f"Use !forcarplano para atualizar")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Erro ao buscar status: `{e}`")
            logger.error(f"Erro em statusplano: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    if bot.cwl_planner_channel_id and bot.db is not None:
        await bot.add_cog(CwlPlannerCog(bot))
    else:
        logger.warning("Cog 'CwlPlannerCog' não carregado (ID do canal ou DB não configurado).")
