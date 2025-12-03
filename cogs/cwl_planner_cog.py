# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import datetime
import pytz
import math
import asyncio

logger = logging.getLogger("cwl_planner_cog")


@dataclass
class CWLPlayer:
    """Modelo centralizado para jogadores da CWL."""
    tag: str
    name: str
    town_hall: int
    days_played: int = 0
    status: str = "active"  # active, backup, unavailable
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CWLPlayer":
        # Suporta formato antigo e novo
        if "player" in data:
            player_data = data["player"]
            return cls(
                tag=player_data["tag"],
                name=player_data["name"],
                town_hall=player_data["town_hall"],
                days_played=data.get("days_played", 0),
                status=data.get("status", "active")
            )
        return cls(**data)


@dataclass
class DayPlan:
    """Plano de um dia específico."""
    day: int
    active_roster: List[CWLPlayer]
    substitutions: List[Dict[str, Any]]
    active_bench: List[CWLPlayer]
    backup_bench: List[CWLPlayer]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day,
            "active_roster": [{"player": p.to_dict(), "days_played": p.days_played} for p in self.active_roster],
            "substitutions": self.substitutions,
            "active_bench": [{"player": p.to_dict(), "days_played": p.days_played} for p in self.active_bench],
            "backup_bench": [{"player": p.to_dict(), "days_played": p.days_played} for p in self.backup_bench]
        }


class RotationEngine:
    """Motor de rotação inteligente - separado para testabilidade."""
    
    def __init__(self, team_size: int, total_days: int = 7):
        self.team_size = team_size
        self.total_days = total_days
    
    def calculate_fair_rotation(
        self,
        roster: List[CWLPlayer],
        active_bench: List[CWLPlayer],
        backup_bench: List[CWLPlayer],
        current_day: int
    ) -> Tuple[List[CWLPlayer], List[CWLPlayer], List[Dict[str, Any]]]:
        """
        Calcula rotação garantindo distribuição justa de participação.
        
        Retorna: (novo_roster, jogadores_que_saíram, substituições)
        """
        days_remaining = self.total_days - current_day + 1
        total_players = len(roster) + len(active_bench) + len(backup_bench)
        
        if days_remaining <= 0 or not active_bench:
            return roster, [], []
        
        # Calcula participação ideal
        total_slots = self.team_size * days_remaining
        ideal_games_per_player = total_slots / total_players if total_players > 0 else 0
        
        # Identifica quem PRECISA jogar para atingir mínimo justo
        all_players = roster + active_bench + backup_bench
        participation_deficit = []
        
        for player in all_players:
            # Quantos dias esse jogador deveria ter jogado até agora para ser justo?
            expected_by_now = (current_day - 1) * (self.team_size / total_players)
            deficit = expected_by_now - player.days_played
            participation_deficit.append((player, deficit))
        
        # Ordena por déficit (quem mais precisa jogar primeiro)
        participation_deficit.sort(key=lambda x: (-x[1], -x[0].town_hall))
        
        # Determina quantidade de rotação baseado em déficit real
        players_with_deficit = [p for p, d in participation_deficit if d > 0.5 and p in active_bench]
        
        # Rotação mínima baseada em fairness
        min_rotation = max(1, len(players_with_deficit))
        # Rotação máxima baseada em estabilidade (não trocar mais que 40% do time)
        max_rotation = max(1, int(self.team_size * 0.4))
        
        num_to_rotate = min(min_rotation, max_rotation, len(active_bench))
        
        # Seleciona quem SAI: mais dias jogados + menor CV
        roster_sorted = sorted(roster, key=lambda p: (-p.days_played, p.town_hall))
        players_out = roster_sorted[:num_to_rotate]
        
        # Seleciona quem ENTRA: menos dias jogados + maior CV
        bench_sorted = sorted(active_bench, key=lambda p: (p.days_played, -p.town_hall))
        players_in = bench_sorted[:num_to_rotate]
        
        # Monta novo roster
        new_roster = [p for p in roster if p not in players_out] + players_in
        
        # Gera substituições
        substitutions = []
        for i, (p_out, p_in) in enumerate(zip(players_out, players_in)):
            substitutions.append({
                "out": p_out.to_dict(),
                "in": p_in.to_dict(),
                "reason": f"Rotação justa (Saiu: {p_out.days_played}d jogados | Entrou: {p_in.days_played}d jogados)"
            })
        
        return new_roster, players_out, substitutions
    
    def validate_participation_projection(
        self,
        schedule: List[DayPlan],
        all_players: List[CWLPlayer]
    ) -> Dict[str, Any]:
        """
        Valida se o plano garante participação mínima para todos.
        """
        participation_count = defaultdict(int)
        
        for day_plan in schedule:
            for player in day_plan.active_roster:
                participation_count[player.tag] += 1
        
        issues = []
        min_expected = max(1, len(schedule) * 0.3)  # Pelo menos 30% dos dias
        
        for player in all_players:
            games = participation_count.get(player.tag, 0)
            if games < min_expected and player.status == "active":
                issues.append({
                    "player": player.to_dict(),
                    "games_scheduled": games,
                    "minimum_expected": min_expected
                })
        
        return {
            "is_fair": len(issues) == 0,
            "underserved_players": issues,
            "participation_summary": dict(participation_count)
        }


class CwlPlannerCog(commands.Cog, name="Planeador de CWL"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # self.api_client removido daqui para evitar referência None na inicialização
        self.db = bot.db
        self.cwl_plan_collection = self.db.cwl_plan if self.db is not None else None
        self.cwl_state_collection = self.db.cwl_state if self.db is not None else None
        
        # Cache com persistência
        self._cache_initialized = False
        self.posted_daily_plans: Set[str] = set()
        self.posted_inactivity_alerts: Set[str] = set()
        self.last_known_members: Set[str] = set()
        self.reported_leavers: Set[str] = set()

    async def cog_load(self):
        await self._load_persistent_state()
        self.cwl_monitoring_task.start()

    async def cog_unload(self):
        await self._save_persistent_state()
        self.cwl_monitoring_task.cancel()

    async def _load_persistent_state(self):
        """Carrega estado persistente do banco de dados."""
        if self.cwl_state_collection is None:
            return
        
        try:
            state = await self.cwl_state_collection.find_one({"_id": "cog_state"})
            if state:
                self.posted_daily_plans = set(state.get("posted_daily_plans", []))
                self.posted_inactivity_alerts = set(state.get("posted_inactivity_alerts", []))
                self.last_known_members = set(state.get("last_known_members", []))
                self.reported_leavers = set(state.get("reported_leavers", []))
                logger.info("Estado persistente carregado com sucesso.")
            self._cache_initialized = True
        except Exception as e:
            logger.error(f"Erro ao carregar estado persistente: {e}")

    async def _save_persistent_state(self):
        """Salva estado para persistência."""
        if self.cwl_state_collection is None:
            return
        
        try:
            await self.cwl_state_collection.update_one(
                {"_id": "cog_state"},
                {"$set": {
                    "posted_daily_plans": list(self.posted_daily_plans),
                    "posted_inactivity_alerts": list(self.posted_inactivity_alerts),
                    "last_known_members": list(self.last_known_members),
                    "reported_leavers": list(self.reported_leavers),
                    "updated_at": datetime.datetime.now(pytz.utc)
                }},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Erro ao salvar estado persistente: {e}")

    async def _send_planner_embed(self, embed: discord.Embed):
        """Envia embed para o canal do planejador com tratamento de erro robusto."""
        if not self.bot.cwl_planner_channel_id:
            logger.warning("Canal do planejador CWL não configurado.")
            return False
        
        try:
            channel = self.bot.get_channel(self.bot.cwl_planner_channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(self.bot.cwl_planner_channel_id)
            
            await channel.send(embed=embed)
            return True
        except discord.NotFound:
            logger.error(f"Canal {self.bot.cwl_planner_channel_id} não encontrado.")
        except discord.Forbidden:
            logger.error(f"Sem permissão para enviar no canal {self.bot.cwl_planner_channel_id}.")
        except Exception as e:
            logger.error(f"Falha ao enviar embed: {e}", exc_info=True)
        return False

    async def _get_current_cwl_war_info(self) -> Optional[Dict[str, Any]]:
        """Busca informações detalhadas sobre o estado atual da CWL com cache."""
        if not self.bot.api_client:
            logger.warning("API Client não está pronto em _get_current_cwl_war_info")
            return None

        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            
            if not cwl_group or cwl_group.state == "notInWar":
                return None

            active_war = None
            day_number = 0
            active_war_tag = None
            team_size = 15

            wars_by_state = {'inWar': [], 'preparation': [], 'warEnded': []}

            for round_index, round_war_tags in enumerate(cwl_group.rounds):
                for war_tag in round_war_tags:
                    if war_tag == '#0':
                        continue
                    
                    try:
                        war = await self.bot.api_client.get_league_war(war_tag)
                        
                        # Verifica se nosso clã está nessa guerra
                        is_our_war = (
                            war.clan.tag == self.bot.clan_tag or 
                            war.opponent.tag == self.bot.clan_tag
                        )
                        
                        if is_our_war:
                            team_size = war.team_size
                            war_state = war.state if isinstance(war.state, str) else war.state.value
                            wars_by_state.get(war_state, []).append((war, round_index + 1, war_tag))
                    
                    except coc.NotFound:
                        logger.debug(f"Guerra {war_tag} não encontrada.")
                        continue
                    except Exception as e:
                        logger.warning(f"Erro ao buscar guerra {war_tag}: {e}")
                        continue

            # Prioridade: guerra ativa > preparação > mais recente terminada
            if wars_by_state['inWar']:
                active_war, day_number, active_war_tag = wars_by_state['inWar'][0]
            elif wars_by_state['preparation']:
                active_war, day_number, active_war_tag = wars_by_state['preparation'][0]
            elif wars_by_state['warEnded']:
                last_war, last_day, last_tag = max(wars_by_state['warEnded'], key=lambda x: x[1])
                day_number = min(last_day + 1, 8)
                team_size = last_war.team_size
                active_war = last_war
                active_war_tag = last_tag

            if day_number == 0:
                day_number = 1 if cwl_group.state == "preparation" else 8

            return {
                "active_war": active_war,
                "day_number": day_number,
                "season": cwl_group.season,
                "war_tag": active_war_tag,
                "team_size": team_size,
                "cwl_state": cwl_group.state
            }

        except coc.NotFound:
            logger.info("Clã não está em CWL.")
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar info CWL: {e}", exc_info=True)
            return None

    async def _fetch_cwl_player_pool(self) -> Tuple[List[CWLPlayer], Set[str]]:
        """
        Busca o pool de jogadores da CWL de forma atômica.
        
        Retorna: (lista de jogadores válidos, tags dos membros atuais do clã)
        """
        if not self.bot.api_client:
            return [], set()

        try:
            # Busca paralela para reduzir janela de race condition
            cwl_group_task = self.bot.api_client.get_league_group(self.bot.clan_tag)
            clan_task = self.bot.api_client.get_clan(self.bot.clan_tag)
            
            cwl_group, clan = await asyncio.gather(cwl_group_task, clan_task)
            
            if not cwl_group:
                return [], set()
            
            current_member_tags = {m.tag for m in clan.members}
            
            our_cwl_clan = next(
                (c for c in cwl_group.clans if c.tag == self.bot.clan_tag), 
                None
            )
            
            if not our_cwl_clan:
                return [], current_member_tags
            
            # Carrega status dos jogadores do banco
            db_cog = self.bot.get_cog("Banco de Dados")
            player_statuses = {}
            if db_cog:
                player_statuses = await db_cog.load_player_notes_from_db()
            
            players = []
            for member in our_cwl_clan.members:
                if member.tag in current_member_tags:
                    status = player_statuses.get(member.tag, {}).get('cwl_status', 'active')
                    players.append(CWLPlayer(
                        tag=member.tag,
                        name=member.name,
                        town_hall=member.town_hall,
                        status=status
                    ))
            
            return players, current_member_tags
        
        except coc.NotFound:
            logger.info("Não foi possível buscar pool CWL - clã não em CWL.")
            return [], set()
        except Exception as e:
            logger.error(f"Erro ao buscar pool de jogadores CWL: {e}", exc_info=True)
            return [], set()

    async def _build_initial_state_from_war(
        self,
        players: List[CWLPlayer],
        active_war: coc.ClanWar,
        current_day: int
    ) -> Tuple[List[CWLPlayer], List[CWLPlayer], List[CWLPlayer]]:
        """
        Constrói o estado inicial baseado na guerra real atual.
        """
        our_clan = (
            active_war.clan 
            if active_war.clan.tag == self.bot.clan_tag 
            else active_war.opponent
        )
        real_roster_tags = {m.tag for m in our_clan.members}
        
        roster = []
        active_bench = []
        backup_bench = []
        
        for player in players:
            # Define days_played baseado no dia atual
            if player.tag in real_roster_tags:
                player.days_played = current_day
                roster.append(player)
            else:
                player.days_played = max(0, current_day - 1)
                if player.status == "active":
                    active_bench.append(player)
                else:
                    backup_bench.append(player)
        
        return roster, active_bench, backup_bench

    async def generate_rotation_plan(self) -> Dict[str, Any]:
        """
        Gera ou atualiza o plano de rotação da CWL.
        """
        if self.cwl_plan_collection is None:
            return {"error": "Banco de dados não configurado."}
        
        info = await self._get_current_cwl_war_info()
        if not info:
            return {"error": "CWL não está ativa."}
        
        season = info['season']
        current_day = info['day_number']
        team_size = info['team_size']
        active_war = info['active_war']
        
        # CWL terminou
        if current_day >= 8:
            plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
            if plan_doc:
                return {
                    "current_day": current_day,
                    "schedule": plan_doc['schedule'],
                    "participation_score": plan_doc.get('participation_score', []),
                    "finished": True
                }
            return {"error": "CWL finalizada, histórico não encontrado."}
        
        if not active_war:
            return {"error": "Não foi possível encontrar guerra ativa."}
        
        try:
            # Busca pool de jogadores
            players, current_member_tags = await self._fetch_cwl_player_pool()
            if not players:
                return {"error": "Não foi possível buscar jogadores da CWL."}
            
            # Verifica se já existe plano
            plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
            
            # Valida se o plano existente é compatível
            needs_regeneration = False
            if plan_doc:
                try:
                    stored_team_size = len(plan_doc['schedule'][0]['active_roster'])
                    if stored_team_size != team_size:
                        needs_regeneration = True
                        logger.warning(f"Team size mudou: {stored_team_size} -> {team_size}")
                except (KeyError, IndexError):
                    needs_regeneration = True
            
            # Gera ou atualiza plano
            if plan_doc is None or needs_regeneration:
                plan_data = await self._generate_full_plan(
                    players, team_size, active_war, current_day
                )
            else:
                plan_data = await self._update_plan(
                    plan_doc, players, team_size, active_war, current_day, current_member_tags
                )
            
            if "error" in plan_data:
                return plan_data
            
            # Valida fairness do plano
            engine = RotationEngine(team_size)
            # Reconstrói lista de CWLPlayer para validação
            all_players_for_validation = []
            if plan_data.get('schedule'):
                last_day = plan_data['schedule'][-1]
                for p_data in (last_day.get('active_roster', []) + 
                              last_day.get('active_bench', []) + 
                              last_day.get('backup_bench', [])):
                    all_players_for_validation.append(CWLPlayer.from_dict(p_data))
            
            # Converte schedule para DayPlan para validação
            day_plans = []
            for day_data in plan_data['schedule']:
                day_plans.append(DayPlan(
                    day=day_data['day'],
                    active_roster=[CWLPlayer.from_dict(p) for p in day_data['active_roster']],
                    substitutions=day_data['substitutions'],
                    active_bench=[CWLPlayer.from_dict(p) for p in day_data.get('active_bench', [])],
                    backup_bench=[CWLPlayer.from_dict(p) for p in day_data.get('backup_bench', [])]
                ))
            
            fairness_check = engine.validate_participation_projection(day_plans, all_players_for_validation)
            plan_data['fairness_validation'] = fairness_check
            
            if not fairness_check['is_fair']:
                # CORREÇÃO AQUI: Garante que 'warning' seja string antes de concatenar (trata None)
                current_warning = plan_data.get('warning') or ""
                
                plan_data['warning'] = (
                    current_warning + 
                    f"\n⚠️ {len(fairness_check['underserved_players'])} jogadores podem ficar sub-representados."
                ).strip()
            
            # Persiste no banco
            await self.cwl_plan_collection.update_one(
                {"_id": season},
                {"$set": {
                    "schedule": plan_data['schedule'],
                    "participation_score": plan_data.get('participation_score', []),
                    "warning": plan_data.get('warning'),
                    "fairness_validation": fairness_check,
                    "last_updated": datetime.datetime.now(pytz.utc),
                    "team_size": team_size
                }},
                upsert=True
            )
            
            plan_data['current_day'] = current_day
            return plan_data
            
        except Exception as e:
            logger.error(f"Erro fatal em generate_rotation_plan: {e}", exc_info=True)
            return {"error": str(e)}

    async def _generate_full_plan(
        self,
        players: List[CWLPlayer],
        team_size: int,
        active_war: coc.ClanWar,
        starting_day: int
    ) -> Dict[str, Any]:
        """
        Gera um plano completo de 7 dias a partir do dia atual.
        """
        roster, active_bench, backup_bench = await self._build_initial_state_from_war(
            players, active_war, starting_day
        )
        
        engine = RotationEngine(team_size)
        schedule = []
        warning = None
        
        # Valida roster inicial
        if len(roster) < team_size:
            warning = f"⚠️ Roster inicial ({len(roster)}) menor que tamanho da guerra ({team_size})."
        
        # Dia inicial - estado atual
        schedule.append(DayPlan(
            day=starting_day,
            active_roster=roster.copy(),
            substitutions=[],
            active_bench=sorted(active_bench, key=lambda p: (p.days_played, -p.town_hall)),
            backup_bench=sorted(backup_bench, key=lambda p: (p.days_played, -p.town_hall))
        ))
        
        # Simula dias futuros
        current_roster = roster.copy()
        current_active_bench = active_bench.copy()
        current_backup_bench = backup_bench.copy()
        
        for day in range(starting_day + 1, 8):
            new_roster, players_out, substitutions = engine.calculate_fair_rotation(
                current_roster,
                current_active_bench,
                current_backup_bench,
                day
            )
            
            # Move jogadores que saíram para os benches apropriados
            for player in players_out:
                if player.status == "active":
                    current_active_bench.append(player)
                else:
                    current_backup_bench.append(player)
            
            # Remove jogadores que entraram do bench
            new_roster_tags = {p.tag for p in new_roster}
            current_active_bench = [p for p in current_active_bench if p.tag not in new_roster_tags]
            current_backup_bench = [p for p in current_backup_bench if p.tag not in new_roster_tags]
            
            # Incrementa days_played para quem está no roster
            for player in new_roster:
                player.days_played += 1
            
            current_roster = new_roster
            
            schedule.append(DayPlan(
                day=day,
                active_roster=current_roster.copy(),
                substitutions=substitutions,
                active_bench=sorted(current_active_bench, key=lambda p: (p.days_played, -p.town_hall)),
                backup_bench=sorted(current_backup_bench, key=lambda p: (p.days_played, -p.town_hall))
            ))
        
        # Calcula score de participação
        all_players = current_roster + current_active_bench + current_backup_bench
        participation_score = sorted(
            [{"player": p.to_dict(), "days_played": p.days_played} for p in all_players],
            key=lambda x: x['days_played'],
            reverse=True
        )
        
        return {
            "schedule": [day.to_dict() for day in schedule],
            "participation_score": participation_score,
            "warning": warning,
            "starting_day": starting_day
        }

    async def _update_plan(
        self,
        plan_doc: Dict[str, Any],
        players: List[CWLPlayer],
        team_size: int,
        active_war: coc.ClanWar,
        current_day: int,
        current_member_tags: Set[str]
    ) -> Dict[str, Any]:
        """
        Atualiza plano existente considerando mudanças no roster real.
        """
        logger.info(f"Atualizando plano existente para dia {current_day}")
        
        # Reconstrói histórico de participação dos dias passados
        participation_map = defaultdict(int)
        for day_data in plan_doc['schedule']:
            if day_data['day'] < current_day:
                for p_data in day_data.get('active_roster', []):
                    tag = p_data.get('player', p_data).get('tag')
                    if tag:
                        participation_map[tag] += 1
        
        # Atualiza days_played baseado no histórico real
        for player in players:
            player.days_played = participation_map.get(player.tag, 0)
        
        # Detecta mudanças críticas
        critical_changes = {"players_left": [], "new_players": []}
        
        stored_tags = set()
        for day_data in plan_doc['schedule']:
            for p_data in (day_data.get('active_roster', []) + 
                          day_data.get('active_bench', []) + 
                          day_data.get('backup_bench', [])):
                tag = p_data.get('player', p_data).get('tag')
                if tag:
                    stored_tags.add(tag)
        
        current_player_tags = {p.tag for p in players}
        
        for tag in stored_tags - current_player_tags:
            if tag not in self.reported_leavers:
                critical_changes["players_left"].append(tag)
                self.reported_leavers.add(tag)
        
        for tag in current_player_tags - stored_tags:
            player = next((p for p in players if p.tag == tag), None)
            if player:
                critical_changes["new_players"].append(player.to_dict())
        
        # Regenera plano a partir do dia atual
        plan_data = await self._generate_full_plan(players, team_size, active_war, current_day)
        
        # Preserva histórico dos dias passados
        past_days = [d for d in plan_doc['schedule'] if d['day'] < current_day]
        future_days = [d for d in plan_data['schedule'] if d['day'] >= current_day]
        plan_data['schedule'] = past_days + future_days
        plan_data['critical_changes'] = critical_changes
        
        # Envia alertas se necessário
        if critical_changes["players_left"] or critical_changes["new_players"]:
            await self._send_critical_changes_alert(critical_changes, current_day)
        
        return plan_data

    async def _send_critical_changes_alert(self, changes: Dict[str, Any], current_day: int):
        """Envia alerta sobre mudanças críticas no roster."""
        if not self.bot.api_client: return

        fields = []
        
        if changes.get("players_left"):
            # Tenta buscar nomes dos jogadores que saíram
            player_names = []
            for tag in changes["players_left"]:
                try:
                    player = await self.bot.api_client.get_player(tag)
                    player_names.append(f"• **{player.name}** ({tag})")
                except:
                    player_names.append(f"• {tag}")
            
            fields.append({
                "name": "🚪 Saíram do Clã",
                "value": "\n".join(player_names[:10]),  # Limita a 10
                "inline": False
            })
        
        if changes.get("new_players"):
            new_list = [f"• **{p['name']}** (CV{p['town_hall']})" for p in changes["new_players"][:10]]
            fields.append({
                "name": "🆕 Novos no Pool",
                "value": "\n".join(new_list),
                "inline": False
            })
        
        if fields:
            embed = discord.Embed(
                title="🚨 MUDANÇAS NO ROSTER CWL",
                description=f"Detectadas no Dia {current_day}",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now(pytz.utc)
            )
            for field in fields:
                embed.add_field(**field)
            
            embed.set_footer(text="O plano foi automaticamente ajustado.")
            await self._send_planner_embed(embed)

    @tasks.loop(minutes=15)
    async def cwl_monitoring_task(self):
        """Task principal de monitoramento da CWL."""
        await self.bot.wait_until_ready()
        
        if hasattr(self.bot, 'coc_client_ready'):
            await self.bot.coc_client_ready.wait()
        
        try:
            # Detecta mudanças no roster do clã
            await self._check_roster_changes()
            
            # Busca info da CWL
            info = await self._get_current_cwl_war_info()
            
            if not info:
                # CWL não ativa - limpa cache
                if self.posted_daily_plans:
                    self.posted_daily_plans.clear()
                    self.posted_inactivity_alerts.clear()
                    self.reported_leavers.clear()
                    await self._save_persistent_state()
                return
            
            # Gera/atualiza plano
            plan_data = await self.generate_rotation_plan()
            
            if "error" not in plan_data:
                # Posta plano diário se necessário
                await self._post_daily_plan_if_needed(info, plan_data)
                
                # Verifica inatividade
                if info['active_war']:
                    await self._check_and_alert_inactivity(info['active_war'], info['war_tag'])
            
            # Salva estado periodicamente
            await self._save_persistent_state()
            
        except Exception as e:
            logger.error(f"Erro na task de monitoramento CWL: {e}", exc_info=True)

    @cwl_monitoring_task.before_loop
    async def before_cwl_monitoring(self):
        """Aguarda bot estar pronto antes de iniciar monitoramento."""
        await self.bot.wait_until_ready()

    async def _check_roster_changes(self):
        """Detecta e alerta sobre mudanças no roster do clã."""
        if not self.bot.api_client: return

        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            current_members = {m.tag for m in clan.members}
            
            if not self.last_known_members:
                self.last_known_members = current_members
                return
            
            leavers = self.last_known_members - current_members
            joiners = current_members - self.last_known_members
            
            # Alerta sobre saídas durante CWL
            if leavers:
                info = await self._get_current_cwl_war_info()
                if info:  # Só alerta se CWL estiver ativa
                    new_leavers = leavers - self.reported_leavers
                    if new_leavers:
                        players_info = []
                        for tag in new_leavers:
                            try:
                                player = await self.bot.api_client.get_player(tag)
                                players_info.append({"name": player.name, "tag": tag})
                            except:
                                players_info.append({"name": "Desconhecido", "tag": tag})
                        
                        if players_info:
                            embed = discord.Embed(
                                title="🚪 Jogadores Saíram Durante CWL!",
                                description="Os seguintes jogadores deixaram o clã:",
                                color=discord.Color.red(),
                                timestamp=datetime.datetime.now(pytz.utc)
                            )
                            embed.add_field(
                                name="Jogadores",
                                value="\n".join([f"• **{p['name']}**" for p in players_info]),
                                inline=False
                            )
                            await self._send_planner_embed(embed)
                        
                        self.reported_leavers.update(new_leavers)
            
            self.last_known_members = current_members
            
        except Exception as e:
            logger.error(f"Erro ao verificar mudanças no roster: {e}")

    async def _post_daily_plan_if_needed(self, info: Dict[str, Any], plan_data: Dict[str, Any]):
        """Posta o plano diário se ainda não foi postado."""
        war_tag = info.get('war_tag')
        if not war_tag or war_tag in self.posted_daily_plans:
            return
        
        current_day = info['day_number']
        active_war = info['active_war']
        season = info['season']
        
        if not active_war:
            return
        
        # Encontra o plano do dia atual
        current_day_plan = next(
            (p for p in plan_data.get('schedule', []) if p['day'] == current_day),
            None
        )
        
        if not current_day_plan:
            return
        
        # Identifica oponente
        opponent = (
            active_war.opponent 
            if active_war.clan.tag == self.bot.clan_tag 
            else active_war.clan
        )
        
        # Constrói embed
        embed = discord.Embed(
            title=f"📋 Plano CWL - Dia {current_day} vs {opponent.name}",
            description=f"**Season:** {season}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(pytz.utc)
        )
        
        # Roster ordenado por CV
        roster = sorted(
            current_day_plan['active_roster'],
            key=lambda p: p.get('player', p).get('town_hall', 0),
            reverse=True
        )
        
        roster_lines = []
        for i, p_data in enumerate(roster):
            player = p_data.get('player', p_data)
            days = p_data.get('days_played', 0)
            roster_lines.append(
                f"`{i+1:02d}.` **{player['name']}** (CV{player['town_hall']}) - {days}d jogados"
            )
        
        roster_text = "\n".join(roster_lines)
        
        # Divide se muito grande
        if len(roster_text) > 1024:
            mid = len(roster_lines) // 2
            embed.add_field(
                name="⚔️ Escalação (1/2)",
                value="\n".join(roster_lines[:mid]),
                inline=False
            )
            embed.add_field(
                name="⚔️ Escalação (2/2)",
                value="\n".join(roster_lines[mid:]),
                inline=False
            )
        else:
            embed.add_field(name="⚔️ Escalação", value=roster_text, inline=False)
        
        # Substituições
        subs = current_day_plan.get('substitutions', [])
        if subs:
            subs_lines = [
                f"🔴 **{s['out']['name']}** → 🟢 **{s['in']['name']}**"
                for s in subs
            ]
            embed.add_field(
                name="🔄 Substituições",
                value="\n".join(subs_lines[:10]),  # Limita
                inline=False
            )
        else:
            embed.add_field(
                name="🔄 Substituições",
                value="Manter equipe atual.",
                inline=False
            )
        
        # Warning se existir
        if plan_data.get('warning'):
            embed.add_field(
                name="⚠️ Avisos",
                value=plan_data['warning'],
                inline=False
            )
        
        embed.set_footer(text="Use /forcarplano para regenerar o plano.")
        
        success = await self._send_planner_embed(embed)
        if success:
            self.posted_daily_plans.add(war_tag)

    async def _check_and_alert_inactivity(self, war: coc.ClanWar, war_tag: str):
        """Verifica e alerta sobre jogadores inativos."""
        if not war_tag:
            return
        
        # Só alerta quando faltam entre 15min e 4h
        time_left = war.end_time.seconds_until
        if not (15 * 60 < time_left < 4 * 3600):
            return
        
        our_clan = (
            war.clan 
            if war.clan.tag == self.bot.clan_tag 
            else war.opponent
        )
        
        inactive = [
            m for m in our_clan.members 
            if len(m.attacks) < war.attacks_per_member
        ]
        
        if not inactive:
            return
        
        alert_id = f"{war_tag}-inactivity-{len(inactive)}"
        if alert_id in self.posted_inactivity_alerts:
            return
        
        hours_left = int(time_left / 3600)
        mins_left = int((time_left % 3600) / 60)
        
        embed = discord.Embed(
            title="🚨 ALERTA DE INATIVIDADE",
            description=f"Faltam **{hours_left}h {mins_left}min** para o fim da guerra!",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(pytz.utc)
        )
        
        inactive_list = [
            f"• **{m.name}** - {len(m.attacks)}/{war.attacks_per_member} ataques"
            for m in inactive
        ]
        
        embed.add_field(
            name=f"Jogadores Pendentes ({len(inactive)})",
            value="\n".join(inactive_list[:15]),  # Limita
            inline=False
        )
        
        if len(inactive) > 15:
            embed.add_field(
                name="",
                value=f"*...e mais {len(inactive) - 15} jogadores*",
                inline=False
            )
        
        success = await self._send_planner_embed(embed)
        if success:
            self.posted_inactivity_alerts.add(alert_id)

    @commands.command(name='forcarplano')
    @commands.has_permissions(administrator=True)
    async def force_plan_command(self, ctx: commands.Context):
        """Força regeneração do plano de CWL."""
        await ctx.message.add_reaction("🔄")
        
        try:
            # Limpa cache para forçar regeneração
            self.posted_daily_plans.clear()
            
            # Regenera
            plan_data = await self.generate_rotation_plan()
            
            if "error" in plan_data:
                await ctx.send(f"❌ Erro: {plan_data['error']}")
                return
            
            await ctx.message.add_reaction("✅")
            await ctx.send("✅ Plano regenerado com sucesso! O plano diário será postado em breve.")
            
            # Força postagem imediata
            info = await self._get_current_cwl_war_info()
            if info:
                await self._post_daily_plan_if_needed(info, plan_data)
                
        except Exception as e:
            logger.error(f"Erro ao forçar plano: {e}", exc_info=True)
            await ctx.send(f"❌ Erro inesperado: {e}")

    @commands.command(name='statusplano')
    async def plan_status_command(self, ctx: commands.Context):
        """Mostra status atual do planejamento CWL."""
        info = await self._get_current_cwl_war_info()
        
        if not info:
            embed = discord.Embed(
                title="📊 Status CWL",
                description="CWL não está ativa no momento.",
                color=discord.Color.gray()
            )
            await ctx.send(embed=embed)
            return
        
        plan_data = await self.generate_rotation_plan()
        
        embed = discord.Embed(
            title="📊 Status do Plano CWL",
            color=discord.Color.green() if "error" not in plan_data else discord.Color.red()
        )
        
        embed.add_field(name="Season", value=info['season'], inline=True)
        embed.add_field(name="Dia Atual", value=str(info['day_number']), inline=True)
        embed.add_field(name="Tamanho", value=f"{info['team_size']}v{info['team_size']}", inline=True)
        
        if "error" in plan_data:
            embed.add_field(name="❌ Erro", value=plan_data['error'], inline=False)
        else:
            # Fairness check
            fairness = plan_data.get('fairness_validation', {})
            if fairness.get('is_fair'):
                embed.add_field(
                    name="✅ Distribuição",
                    value="Todos os jogadores têm participação justa.",
                    inline=False
                )
            else:
                underserved = fairness.get('underserved_players', [])
                embed.add_field(
                    name="⚠️ Atenção",
                    value=f"{len(underserved)} jogadores podem jogar menos que o ideal.",
                    inline=False
                )
            
            if plan_data.get('warning'):
                embed.add_field(name="⚠️ Avisos", value=plan_data['warning'], inline=False)
        
        embed.set_footer(text="Use /forcarplano para regenerar.")
        await ctx.send(embed=embed)

    @commands.command(name='participacao')
    async def participation_command(self, ctx: commands.Context):
        """Mostra projeção de participação de todos os jogadores."""
        plan_data = await self.generate_rotation_plan()
        
        if "error" in plan_data:
            await ctx.send(f"❌ {plan_data['error']}")
            return
        
        scores = plan_data.get('participation_score', [])
        if not scores:
            await ctx.send("Não há dados de participação disponíveis.")
            return
        
        embed = discord.Embed(
            title="📈 Projeção de Participação CWL",
            description="Dias jogados (projetados) por jogador",
            color=discord.Color.blue()
        )
        
        # Agrupa por dias jogados
        by_days = defaultdict(list)
        for entry in scores:
            days = entry.get('days_played', 0)
            player = entry.get('player', {})
            by_days[days].append(f"**{player.get('name', '?')}** (CV{player.get('town_hall', '?')})")
        
        for days in sorted(by_days.keys(), reverse=True):
            players = by_days[days]
            value = "\n".join(players[:10])
            if len(players) > 10:
                value += f"\n*...e mais {len(players) - 10}*"
            
            embed.add_field(
                name=f"📅 {days} dias",
                value=value,
                inline=True
            )
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function para carregar o cog."""
    if bot.cwl_planner_channel_id and bot.db is not None:
        await bot.add_cog(CwlPlannerCog(bot))
        logger.info("CwlPlannerCog carregado com sucesso.")
    else:
        logger.warning(
            "CwlPlannerCog não carregado: "
            f"channel_id={bot.cwl_planner_channel_id}, db={bot.db is not None}"
        )
