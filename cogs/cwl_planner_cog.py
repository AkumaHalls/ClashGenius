# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from enum import Enum, auto
import datetime
import pytz
import math
import asyncio
from abc import ABC, abstractmethod

logger = logging.getLogger("cwl_planner_cog")


# ==================== ENUMS E CONSTANTES ====================

class PlayerStatus(Enum):
    ACTIVE = "active"
    BACKUP = "backup"
    UNAVAILABLE = "unavailable"
    PRIORITY = "priority"  # Jogadores que PRECISAM jogar (ex: quase sem dias)
    RESTING = "resting"    # Descansando por já ter jogado muito


class RotationStrategy(Enum):
    AGGRESSIVE = auto()    # Maximiza força, menos rotação
    BALANCED = auto()      # Equilíbrio entre força e fairness
    FAIR = auto()          # Prioriza participação igual
    SURVIVAL = auto()      # Modo emergência - poucos jogadores


class WarContext(Enum):
    WINNING = auto()       # Ganhando na liga
    COMPETITIVE = auto()   # Disputando posição
    LOSING = auto()        # Perdendo, precisa recuperar
    COMFORTABLE = auto()   # Posição confortável


# ==================== MODELOS DE DADOS ====================

@dataclass
class PlayerMetrics:
    """Métricas detalhadas de um jogador."""
    attack_success_rate: float = 0.0      # Taxa de 3 estrelas
    average_stars: float = 0.0            # Média de estrelas por ataque
    defense_weight: float = 0.0           # Peso defensivo baseado no CV
    reliability_score: float = 1.0        # Confiabilidade (ataca no horário, etc)
    versatility: float = 0.5              # Capacidade de atacar CVs diferentes
    last_updated: Optional[datetime.datetime] = None
    
    def overall_score(self) -> float:
        """Calcula score geral do jogador."""
        return (
            self.attack_success_rate * 0.35 +
            (self.average_stars / 3.0) * 0.25 +
            self.reliability_score * 0.25 +
            self.versatility * 0.15
        )


@dataclass
class CWLPlayer:
    """Modelo centralizado para jogadores da CWL."""
    tag: str
    name: str
    town_hall: int
    days_played: int = 0
    status: PlayerStatus = PlayerStatus.ACTIVE
    metrics: PlayerMetrics = field(default_factory=PlayerMetrics)
    consecutive_days_played: int = 0      # Dias seguidos jogando
    consecutive_days_rested: int = 0      # Dias seguidos descansando
    forced_inclusion: bool = False        # Forçado a jogar por liderança
    forced_exclusion: bool = False        # Forçado a não jogar
    notes: str = ""
    
    def __post_init__(self):
        if isinstance(self.status, str):
            try:
                self.status = PlayerStatus(self.status)
            except ValueError:
                self.status = PlayerStatus.ACTIVE
    
    @property
    def effective_strength(self) -> float:
        """Força efetiva considerando CV e métricas."""
        base_strength = self.town_hall * 10
        metric_modifier = self.metrics.overall_score()
        fatigue_penalty = min(0.15, self.consecutive_days_played * 0.03)
        rest_bonus = min(0.1, self.consecutive_days_rested * 0.02)
        
        return base_strength * (1 + metric_modifier - fatigue_penalty + rest_bonus)
    
    @property
    def participation_urgency(self) -> float:
        """Urgência de participação (quanto maior, mais precisa jogar)."""
        if self.forced_inclusion:
            return 100.0
        if self.forced_exclusion:
            return -100.0
        
        # Base: dias sem jogar aumenta urgência
        rest_urgency = self.consecutive_days_rested * 2.0
        
        # Penalidade se já jogou muito
        overplay_penalty = max(0, self.consecutive_days_played - 3) * 1.5
        
        return rest_urgency - overplay_penalty
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.tag,
            "name": self.name,
            "town_hall": self.town_hall,
            "days_played": self.days_played,
            "status": self.status.value,
            "metrics": asdict(self.metrics),
            "consecutive_days_played": self.consecutive_days_played,
            "consecutive_days_rested": self.consecutive_days_rested,
            "forced_inclusion": self.forced_inclusion,
            "forced_exclusion": self.forced_exclusion,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CWLPlayer":
        # Suporta formato antigo e novo
        if "player" in data:
            player_data = data["player"]
            return cls(
                tag=player_data.get("tag", ""),
                name=player_data.get("name", ""),
                town_hall=player_data.get("town_hall", 1),
                days_played=data.get("days_played", 0),
                status=PlayerStatus(data.get("status", "active"))
            )
        
        metrics_data = data.get("metrics", {})
        metrics = PlayerMetrics(**metrics_data) if metrics_data else PlayerMetrics()
        
        return cls(
            tag=data.get("tag", ""),
            name=data.get("name", ""),
            town_hall=data.get("town_hall", 1),
            days_played=data.get("days_played", 0),
            status=PlayerStatus(data.get("status", "active")),
            metrics=metrics,
            consecutive_days_played=data.get("consecutive_days_played", 0),
            consecutive_days_rested=data.get("consecutive_days_rested", 0),
            forced_inclusion=data.get("forced_inclusion", False),
            forced_exclusion=data.get("forced_exclusion", False),
            notes=data.get("notes", "")
        )


@dataclass
class OpponentAnalysis:
    """Análise do oponente para o dia."""
    clan_tag: str
    clan_name: str
    estimated_strength: float
    th_distribution: Dict[int, int]  # CV -> quantidade
    threat_level: str  # "low", "medium", "high", "extreme"
    recommended_strategy: RotationStrategy
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass 
class DayPlan:
    """Plano de um dia específico - versão aprimorada."""
    day: int
    active_roster: List[CWLPlayer]
    substitutions: List[Dict[str, Any]]
    active_bench: List[CWLPlayer]
    backup_bench: List[CWLPlayer]
    strategy_used: RotationStrategy = RotationStrategy.BALANCED
    opponent_analysis: Optional[OpponentAnalysis] = None
    confidence_score: float = 0.0  # 0-1, quão confiante estamos neste plano
    risk_factors: List[str] = field(default_factory=list)
    contingency_subs: List[Dict[str, Any]] = field(default_factory=list)  # Substituições de emergência
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day,
            "active_roster": [p.to_dict() for p in self.active_roster],
            "substitutions": self.substitutions,
            "active_bench": [p.to_dict() for p in self.active_bench],
            "backup_bench": [p.to_dict() for p in self.backup_bench],
            "strategy_used": self.strategy_used.name,
            "opponent_analysis": self.opponent_analysis.to_dict() if self.opponent_analysis else None,
            "confidence_score": self.confidence_score,
            "risk_factors": self.risk_factors,
            "contingency_subs": self.contingency_subs,
            "notes": self.notes
        }


@dataclass
class SeasonState:
    """Estado completo da season para decisões contextuais."""
    current_position: int = 0
    total_clans: int = 8
    total_stars: int = 0
    stars_behind_leader: int = 0
    stars_ahead_of_relegation: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    promotion_zone: bool = False
    relegation_zone: bool = False
    
    @property
    def context(self) -> WarContext:
        if self.promotion_zone:
            return WarContext.COMPETITIVE
        if self.relegation_zone:
            return WarContext.LOSING
        if self.current_position <= 2:
            return WarContext.WINNING
        if self.current_position >= self.total_clans - 1:
            return WarContext.LOSING
        return WarContext.COMFORTABLE


# ==================== MOTOR DE DECISÃO INTELIGENTE ====================

class DecisionFactor(ABC):
    """Base para fatores de decisão no algoritmo."""
    @abstractmethod
    def evaluate(self, player: CWLPlayer, context: Dict[str, Any]) -> float:
        pass
    @property
    @abstractmethod
    def weight(self) -> float:
        pass
    @property
    @abstractmethod
    def name(self) -> str:
        pass

class FairnessFactor(DecisionFactor):
    def evaluate(self, player: CWLPlayer, context: Dict[str, Any]) -> float:
        total_days = context.get("total_days", 7)
        current_day = context.get("current_day", 1)
        total_players = context.get("total_players", 1)
        team_size = context.get("team_size", 15)
        ideal_participation = (team_size / total_players) * (current_day - 1)
        actual_participation = player.days_played
        deficit = ideal_participation - actual_participation
        return max(-1.0, min(1.0, deficit / 3))
    @property
    def weight(self) -> float: return 0.25
    @property
    def name(self) -> str: return "Fairness"

class StrengthFactor(DecisionFactor):
    def evaluate(self, player: CWLPlayer, context: Dict[str, Any]) -> float:
        max_th = context.get("max_th", 17)
        normalized_strength = player.effective_strength / (max_th * 15)
        return max(-1.0, min(1.0, (normalized_strength - 0.5) * 2))
    @property
    def weight(self) -> float: return 0.30
    @property
    def name(self) -> str: return "Strength"

class FatigueFactor(DecisionFactor):
    def evaluate(self, player: CWLPlayer, context: Dict[str, Any]) -> float:
        if player.consecutive_days_played >= 4: return -0.8
        if player.consecutive_days_played >= 3: return -0.4
        if player.consecutive_days_rested >= 2: return 0.6
        if player.consecutive_days_rested >= 1: return 0.3
        return 0.0
    @property
    def weight(self) -> float: return 0.15
    @property
    def name(self) -> str: return "Fatigue"

class ReliabilityFactor(DecisionFactor):
    def evaluate(self, player: CWLPlayer, context: Dict[str, Any]) -> float:
        return (player.metrics.reliability_score - 0.5) * 2
    @property
    def weight(self) -> float: return 0.20
    @property
    def name(self) -> str: return "Reliability"

class UrgencyFactor(DecisionFactor):
    def evaluate(self, player: CWLPlayer, context: Dict[str, Any]) -> float:
        days_remaining = context.get("days_remaining", 1)
        min_games_needed = context.get("min_games_target", 1)
        games_still_needed = min_games_needed - player.days_played
        if games_still_needed <= 0: return -0.3
        if games_still_needed >= days_remaining: return 1.0
        urgency_ratio = games_still_needed / days_remaining
        return urgency_ratio
    @property
    def weight(self) -> float: return 0.10
    @property
    def name(self) -> str: return "Urgency"


class IntelligentRotationEngine:
    """Motor de rotação com IA para decisões complexas."""
    
    def __init__(self, team_size: int, total_days: int = 7):
        self.team_size = team_size
        self.total_days = total_days
        self.decision_factors: List[DecisionFactor] = [
            FairnessFactor(), StrengthFactor(), FatigueFactor(), ReliabilityFactor(), UrgencyFactor()
        ]
    
    def _adjust_weights_for_strategy(self, strategy: RotationStrategy) -> Dict[str, float]:
        base_weights = {f.name: f.weight for f in self.decision_factors}
        if strategy == RotationStrategy.AGGRESSIVE:
            base_weights["Strength"] = 0.50; base_weights["Fairness"] = 0.10; base_weights["Reliability"] = 0.25
        elif strategy == RotationStrategy.FAIR:
            base_weights["Fairness"] = 0.45; base_weights["Urgency"] = 0.20; base_weights["Strength"] = 0.15
        elif strategy == RotationStrategy.SURVIVAL:
            base_weights["Reliability"] = 0.40; base_weights["Strength"] = 0.35; base_weights["Fatigue"] = 0.05
        total = sum(base_weights.values())
        return {k: v/total for k, v in base_weights.items()}
    
    def calculate_player_score(self, player: CWLPlayer, context: Dict[str, Any], strategy: RotationStrategy) -> Tuple[float, Dict[str, float]]:
        adjusted_weights = self._adjust_weights_for_strategy(strategy)
        breakdown = {}
        total_score = 0.0
        for factor in self.decision_factors:
            factor_score = factor.evaluate(player, context)
            weight = adjusted_weights.get(factor.name, factor.weight)
            weighted_score = factor_score * weight
            breakdown[factor.name] = {"raw": factor_score, "weight": weight, "weighted": weighted_score}
            total_score += weighted_score
        if player.forced_inclusion: total_score += 10.0
        if player.forced_exclusion: total_score -= 10.0
        return total_score, breakdown
    
    def determine_optimal_strategy(self, season_state: SeasonState, current_day: int, opponent_analysis: Optional[OpponentAnalysis]) -> RotationStrategy:
        days_remaining = self.total_days - current_day + 1
        context = season_state.context
        if days_remaining <= 2: return RotationStrategy.FAIR
        if context == WarContext.LOSING and season_state.relegation_zone: return RotationStrategy.AGGRESSIVE
        if context == WarContext.COMPETITIVE:
            if opponent_analysis and opponent_analysis.threat_level in ["high", "extreme"]: return RotationStrategy.AGGRESSIVE
            return RotationStrategy.BALANCED
        if context == WarContext.COMFORTABLE: return RotationStrategy.FAIR
        if context == WarContext.WINNING and days_remaining >= 4: return RotationStrategy.FAIR
        return RotationStrategy.BALANCED
    
    def calculate_rotation(self, roster: List[CWLPlayer], active_bench: List[CWLPlayer], backup_bench: List[CWLPlayer], current_day: int, strategy: RotationStrategy, season_state: Optional[SeasonState] = None) -> Tuple[List[CWLPlayer], List[Dict[str, Any]], List[str]]:
        warnings = []
        days_remaining = self.total_days - current_day + 1
        all_available = [p for p in roster + active_bench if not p.forced_exclusion]
        all_players = all_available + backup_bench
        context = {
            "total_days": self.total_days, "current_day": current_day, "days_remaining": days_remaining,
            "total_players": len(all_players), "team_size": self.team_size,
            "max_th": max((p.town_hall for p in all_players), default=17), "min_games_target": max(1, int(self.total_days * 0.4))
        }
        player_scores = []
        for player in all_available:
            score, breakdown = self.calculate_player_score(player, context, strategy)
            player_scores.append((player, score, breakdown))
        player_scores.sort(key=lambda x: x[1], reverse=True)
        new_roster = [p for p, _, _ in player_scores[:self.team_size]]
        new_bench = [p for p, _, _ in player_scores[self.team_size:]]
        
        # Garante distribuição mínima de CVs altos
        th_counts = defaultdict(int)
        for p in new_roster: th_counts[p.town_hall] += 1
        max_th = max(th_counts.keys()) if th_counts else 17
        high_th_count = sum(v for k, v in th_counts.items() if k >= max_th - 1)
        if high_th_count < min(5, self.team_size // 3):
            warnings.append(f"⚠️ Poucos jogadores de CV alto ({high_th_count}) no roster")
            high_th_on_bench = [p for p in new_bench if p.town_hall >= max_th - 1]
            low_th_in_roster = sorted([p for p in new_roster if p.town_hall < max_th - 1], key=lambda p: p.town_hall)
            swaps_needed = min(len(high_th_on_bench), len(low_th_in_roster), min(5, self.team_size // 3) - high_th_count)
            for i in range(swaps_needed):
                new_roster.remove(low_th_in_roster[i]); new_roster.append(high_th_on_bench[i])
                new_bench.remove(high_th_on_bench[i]); new_bench.append(low_th_in_roster[i])
        
        old_roster_tags = {p.tag for p in roster}
        new_roster_tags = {p.tag for p in new_roster}
        players_out = [p for p in roster if p.tag not in new_roster_tags]
        players_in = [p for p in new_roster if p.tag not in old_roster_tags]
        
        substitutions = []
        for p_out, p_in in zip(sorted(players_out, key=lambda p: -p.days_played), sorted(players_in, key=lambda p: p.days_played)):
            _, out_breakdown = self.calculate_player_score(p_out, context, strategy)
            _, in_breakdown = self.calculate_player_score(p_in, context, strategy)
            reason_parts = []
            for factor_name in ["Fairness", "Fatigue", "Urgency"]:
                out_val = out_breakdown.get(factor_name, {}).get("raw", 0)
                in_val = in_breakdown.get(factor_name, {}).get("raw", 0)
                if abs(in_val - out_val) > 0.3:
                    if factor_name == "Fairness" and in_val > out_val: reason_parts.append(f"equilíbrio")
                    elif factor_name == "Fatigue" and in_val > out_val: reason_parts.append(f"descanso")
                    elif factor_name == "Urgency" and in_val > out_val: reason_parts.append(f"medalhas")
            reason = ", ".join(reason_parts) if reason_parts else "otimização"
            substitutions.append({"out": p_out.to_dict(), "in": p_in.to_dict(), "reason": reason.capitalize(), "score_diff": self.calculate_player_score(p_in, context, strategy)[0] - self.calculate_player_score(p_out, context, strategy)[0]})
        
        if len(new_roster) < self.team_size:
            deficit = self.team_size - len(new_roster)
            warnings.append(f"🚨 CRÍTICO: Faltam {deficit} jogadores!")
            needed = min(deficit, len(backup_bench))
            emergency_pulls = sorted(backup_bench, key=lambda p: -p.town_hall)[:needed]
            new_roster.extend(emergency_pulls)
            for p in emergency_pulls: substitutions.append({"out": None, "in": p.to_dict(), "reason": "EMERGÊNCIA", "emergency": True})
        
        return new_roster, substitutions, warnings
    
    def generate_contingency_plan(self, roster: List[CWLPlayer], bench: List[CWLPlayer], current_day: int) -> List[Dict[str, Any]]:
        contingencies = []
        bench_sorted = sorted(bench, key=lambda p: (-p.town_hall, p.days_played))
        for roster_player in roster:
            suitable_subs = [p for p in bench_sorted if abs(p.town_hall - roster_player.town_hall) <= 1]
            if suitable_subs:
                best_sub = suitable_subs[0]
                contingencies.append({"if_unavailable": roster_player.to_dict(), "replace_with": best_sub.to_dict(), "th_diff": best_sub.town_hall - roster_player.town_hall, "priority": "high" if roster_player.town_hall >= 15 else "normal"})
        return contingencies
    
    def predict_participation_issues(self, schedule: List[DayPlan], all_players: List[CWLPlayer]) -> List[Dict[str, Any]]:
        issues = []
        participation = defaultdict(int)
        for day in schedule:
            for player in day.active_roster: participation[player.tag] += 1
        total_days = len(schedule)
        min_acceptable = max(1, int(total_days * 0.3))
        ideal_games = (self.team_size * total_days) / len(all_players) if all_players else 0
        for player in all_players:
            games = participation.get(player.tag, 0)
            if games == 0: issues.append({"player": player.to_dict(), "type": "ZERO_GAMES", "severity": "critical", "message": f"{player.name} não jogará nenhum dia!", "suggested_action": "Forçar inclusão"})
            elif games < min_acceptable: issues.append({"player": player.to_dict(), "type": "BELOW_MINIMUM", "severity": "warning", "message": f"{player.name} jogará apenas {games}/{min_acceptable} dias", "suggested_action": "Rotacionar mais"})
            elif games > ideal_games * 1.5: issues.append({"player": player.to_dict(), "type": "OVERPLAYED", "severity": "info", "message": f"{player.name} jogará {games} dias (acima do ideal)", "suggested_action": "Dar descanso"})
        return issues


class OpponentAnalyzer:
    def __init__(self, api_client): self.api_client = api_client
    async def analyze_opponent(self, opponent_tag: str, opponent_name: str, war: Optional[coc.ClanWar] = None) -> OpponentAnalysis:
        th_distribution = defaultdict(int); estimated_strength = 0.0
        try:
            if war:
                opponent_clan = war.opponent if war.clan.tag != opponent_tag else war.clan
                for member in opponent_clan.members: th_distribution[member.town_hall] += 1; estimated_strength += member.town_hall * 10
            else:
                clan = await self.api_client.get_clan(opponent_tag)
                for member in clan.members: th_distribution[member.town_hall] += 1; estimated_strength += member.town_hall * 10
        except Exception as e: logger.warning(f"Erro ao analisar oponente {opponent_tag}: {e}")
        max_th = max(th_distribution.keys()) if th_distribution else 15
        high_th_count = sum(v for k, v in th_distribution.items() if k >= max_th - 1)
        if high_th_count >= 10 and max_th >= 16: threat_level = "extreme"
        elif high_th_count >= 7 or max_th >= 16: threat_level = "high"
        elif high_th_count >= 4: threat_level = "medium"
        else: threat_level = "low"
        strategy_map = {"extreme": RotationStrategy.AGGRESSIVE, "high": RotationStrategy.AGGRESSIVE, "medium": RotationStrategy.BALANCED, "low": RotationStrategy.FAIR}
        return OpponentAnalysis(clan_tag=opponent_tag, clan_name=opponent_name, estimated_strength=estimated_strength, th_distribution=dict(th_distribution), threat_level=threat_level, recommended_strategy=strategy_map[threat_level])


# ==================== COG PRINCIPAL ====================

class CwlPlannerCog(commands.Cog, name="Planeador de CWL"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.cwl_plan_collection = self.db.cwl_plan if self.db is not None else None
        self.cwl_state_collection = self.db.cwl_state if self.db is not None else None
        self.player_metrics_collection = self.db.player_metrics if self.db is not None else None
        self.rotation_engine: Optional[IntelligentRotationEngine] = None
        self.opponent_analyzer: Optional[OpponentAnalyzer] = None
        self.config = {"min_participation_percent": 0.3, "max_consecutive_days": 5, "alert_hours_before_end": 4, "auto_adjust_strategy": True}
        
        # Cache
        self.posted_daily_plans: Set[str] = set()
        self.posted_inactivity_alerts: Set[str] = set()
        self.last_known_members: Set[str] = set()
        self.reported_leavers: Set[str] = set()
        self.season_state: Optional[SeasonState] = None

    async def cog_load(self):
        await self._load_persistent_state()
        self.cwl_monitoring_task.start()
        self.metrics_update_task.start()

    async def cog_unload(self):
        await self._save_persistent_state()
        self.cwl_monitoring_task.cancel()
        self.metrics_update_task.cancel()

    async def _initialize_engine(self, team_size: int):
        self.rotation_engine = IntelligentRotationEngine(team_size)
        if self.bot.api_client: self.opponent_analyzer = OpponentAnalyzer(self.bot.api_client)

    async def _load_persistent_state(self):
        if self.cwl_state_collection is None: return
        try:
            state = await self.cwl_state_collection.find_one({"_id": "cog_state"})
            if state:
                self.posted_daily_plans = set(state.get("posted_daily_plans", []))
                self.posted_inactivity_alerts = set(state.get("posted_inactivity_alerts", []))
                self.last_known_members = set(state.get("last_known_members", []))
                self.reported_leavers = set(state.get("reported_leavers", []))
                if state.get("season_state"): self.season_state = SeasonState(**state.get("season_state"))
        except Exception as e: logger.error(f"Erro ao carregar estado: {e}")

    async def _save_persistent_state(self):
        if self.cwl_state_collection is None: return
        try:
            state_data = {
                "posted_daily_plans": list(self.posted_daily_plans), "posted_inactivity_alerts": list(self.posted_inactivity_alerts),
                "last_known_members": list(self.last_known_members), "reported_leavers": list(self.reported_leavers), "updated_at": datetime.datetime.now(pytz.utc)
            }
            if self.season_state: state_data["season_state"] = asdict(self.season_state)
            await self.cwl_state_collection.update_one({"_id": "cog_state"}, {"$set": state_data}, upsert=True)
        except Exception as e: logger.error(f"Erro ao salvar estado: {e}")

    async def _load_player_metrics(self, player_tag: str) -> PlayerMetrics:
        if self.player_metrics_collection is None: return PlayerMetrics()
        try:
            doc = await self.player_metrics_collection.find_one({"_id": player_tag})
            if doc: return PlayerMetrics(attack_success_rate=doc.get("attack_success_rate", 0.0), average_stars=doc.get("average_stars", 0.0), defense_weight=doc.get("defense_weight", 0.0), reliability_score=doc.get("reliability_score", 1.0), versatility=doc.get("versatility", 0.5), last_updated=doc.get("last_updated"))
        except Exception: pass
        return PlayerMetrics()

    async def _update_player_metrics_from_war(self, war: coc.ClanWar):
        if self.player_metrics_collection is None or not war: return
        try:
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            for member in our_clan.members:
                if member.attacks:
                    existing = await self._load_player_metrics(member.tag)
                    total_stars = sum(a.stars for a in member.attacks)
                    new_rate = sum(1 for a in member.attacks if a.stars == 3) / len(member.attacks)
                    new_avg = total_stars / len(member.attacks)
                    
                    # Reliability
                    war_len = (war.end_time.time - war.start_time.time).total_seconds()
                    reliability = existing.reliability_score
                    for attack in member.attacks:
                        timing = (attack.time.time - war.start_time.time).total_seconds()
                        reliability = min(1.0, reliability + 0.05) if timing < war_len * 0.8 else max(0.3, reliability - 0.1)

                    await self.player_metrics_collection.update_one({"_id": member.tag}, {"$set": {
                        "attack_success_rate": 0.3 * new_rate + 0.7 * existing.attack_success_rate,
                        "average_stars": 0.3 * new_avg + 0.7 * existing.average_stars,
                        "reliability_score": reliability,
                        "last_updated": datetime.datetime.now(pytz.utc)
                    }}, upsert=True)
        except Exception as e: logger.error(f"Erro ao atualizar métricas: {e}")

    async def _update_season_state(self, cwl_group) -> SeasonState:
        try:
            our_clan = next((c for c in cwl_group.clans if c.tag == self.bot.clan_tag), None)
            if not our_clan: return SeasonState()
            clans_sorted = sorted(cwl_group.clans, key=lambda c: (-c.stars, c.destruction_percentage))
            pos = next((i + 1 for i, c in enumerate(clans_sorted) if c.tag == self.bot.clan_tag), len(clans_sorted))
            self.season_state = SeasonState(current_position=pos, total_clans=len(cwl_group.clans), total_stars=our_clan.stars, stars_behind_leader=clans_sorted[0].stars - our_clan.stars, stars_ahead_of_relegation=our_clan.stars - clans_sorted[-1].stars, promotion_zone=pos<=2, relegation_zone=pos>=len(cwl_group.clans)-1)
            return self.season_state
        except Exception: return SeasonState()

    async def _send_planner_embed(self, embed: discord.Embed) -> bool:
        if not self.bot.cwl_planner_channel_id: return False
        try:
            channel = self.bot.get_channel(self.bot.cwl_planner_channel_id) or await self.bot.fetch_channel(self.bot.cwl_planner_channel_id)
            await channel.send(embed=embed)
            return True
        except Exception as e: logger.error(f"Falha ao enviar embed: {e}"); return False

    async def _get_current_cwl_war_info(self) -> Optional[Dict[str, Any]]:
        if not self.bot.api_client: return None
        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group or cwl_group.state == "notInWar": return None
            
            season_state = await self._update_season_state(cwl_group)
            active_war, day_number, active_war_tag, opponent_info = None, 0, None, None
            wars_by_state = {'inWar': [], 'preparation': [], 'warEnded': []}

            for round_idx, round_tags in enumerate(cwl_group.rounds):
                for war_tag in round_tags:
                    if war_tag == '#0': continue
                    try:
                        war = await self.bot.api_client.get_league_war(war_tag)
                        if war.clan.tag == self.bot.clan_tag or war.opponent.tag == self.bot.clan_tag:
                            state = war.state if isinstance(war.state, str) else war.state.value
                            opp = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
                            wars_by_state.get(state, []).append((war, round_idx + 1, war_tag, opp))
                    except (coc.NotFound, Exception): continue

            if wars_by_state['inWar']: active_war, day_number, active_war_tag, opp = wars_by_state['inWar'][0]
            elif wars_by_state['preparation']: active_war, day_number, active_war_tag, opp = wars_by_state['preparation'][0]
            elif wars_by_state['warEnded']:
                last_war, last_day, last_tag, opp = max(wars_by_state['warEnded'], key=lambda x: x[1])
                day_number, active_war, active_war_tag = min(last_day + 1, 8), last_war, last_tag
            
            if day_number == 0: day_number = 1 if cwl_group.state == "preparation" else 8
            
            if self.opponent_analyzer and active_war and opp:
                opponent_info = await self.opponent_analyzer.analyze_opponent(opp.tag, opp.name, active_war)
            
            await self._initialize_engine(active_war.team_size if active_war else 15)
            
            return {"active_war": active_war, "day_number": day_number, "season": cwl_group.season, "war_tag": active_war_tag, "team_size": active_war.team_size if active_war else 15, "cwl_state": cwl_group.state, "season_state": season_state, "opponent_analysis": opponent_info, "cwl_group": cwl_group}
        except Exception as e: logger.error(f"Erro get_current_cwl_war_info: {e}"); return None

    async def _fetch_cwl_player_pool(self, active_war: Optional[coc.ClanWar] = None) -> Tuple[List[CWLPlayer], Set[str]]:
        if not self.bot.api_client: return [], set()
        try:
            cwl_group, clan = await asyncio.gather(self.bot.api_client.get_league_group(self.bot.clan_tag), self.bot.api_client.get_clan(self.bot.clan_tag))
            if not cwl_group: return [], set()
            
            current_member_tags = {m.tag for m in clan.members}
            
            # --- CORREÇÃO DO ROSTER: INCLUIR JOGADORES DA GUERRA MESMO FORA DO CLÃ ---
            war_participant_tags = set()
            if active_war:
                side = active_war.clan if active_war.clan.tag == self.bot.clan_tag else active_war.opponent
                war_participant_tags = {m.tag for m in side.members}
            
            our_cwl_clan = next((c for c in cwl_group.clans if c.tag == self.bot.clan_tag), None)
            if not our_cwl_clan: return [], current_member_tags
            
            db_cog = self.bot.get_cog("Banco de Dados")
            player_statuses = await db_cog.load_player_notes_from_db() if db_cog else {}
            
            players = []
            for member in our_cwl_clan.members:
                # Verifica se está no clã OU na guerra
                if member.tag in current_member_tags or member.tag in war_participant_tags:
                    status_data = player_statuses.get(member.tag, {})
                    try: status = PlayerStatus(status_data.get('cwl_status', 'active'))
                    except ValueError: status = PlayerStatus.ACTIVE
                    
                    players.append(CWLPlayer(
                        tag=member.tag, name=member.name, town_hall=member.town_hall, status=status,
                        metrics=await self._load_player_metrics(member.tag),
                        notes=status_data.get('notes', ''), forced_inclusion=status_data.get('forced_in', False), forced_exclusion=status_data.get('forced_out', False)
                    ))
            return players, current_member_tags
        except Exception: return [], set()

    async def _build_initial_state_from_war(self, players: List[CWLPlayer], active_war: coc.ClanWar, current_day: int, plan_doc: Optional[Dict[str, Any]] = None) -> Tuple[List[CWLPlayer], List[CWLPlayer], List[CWLPlayer]]:
        participation_history = defaultdict(lambda: {"days_played": 0, "consecutive": 0, "last_day": 0})
        if plan_doc and 'schedule' in plan_doc:
            for day_data in plan_doc['schedule']:
                if day_data.get('day', 0) < current_day:
                    for p in day_data.get('active_roster', []):
                        tag = p.get('tag') or p.get('player', {}).get('tag')
                        if tag:
                            h = participation_history[tag]
                            h["days_played"] += 1
                            h["consecutive"] = h["consecutive"] + 1 if h["last_day"] == day_data['day'] - 1 else 1
                            h["last_day"] = day_data['day']
        
        our_clan = active_war.clan if active_war.clan.tag == self.bot.clan_tag else active_war.opponent
        real_roster_tags = {m.tag for m in our_clan.members}
        
        roster, active_bench, backup_bench = [], [], []
        for player in players:
            hist = participation_history[player.tag]
            player.days_played = hist["days_played"]
            
            if player.tag in real_roster_tags:
                player.days_played = max(player.days_played, current_day)
                player.consecutive_days_played = hist["consecutive"] + 1 if hist["last_day"] == current_day - 1 else 1
                player.consecutive_days_rested = 0
                roster.append(player)
            else:
                player.consecutive_days_rested = current_day - hist["last_day"] if hist["last_day"] > 0 else current_day - 1
                player.consecutive_days_played = 0
                if player.status in [PlayerStatus.ACTIVE, PlayerStatus.PRIORITY]: active_bench.append(player)
                else: backup_bench.append(player)
        return roster, active_bench, backup_bench

    async def generate_rotation_plan(self) -> Dict[str, Any]:
        if self.cwl_plan_collection is None: return {"error": "DB off"}
        info = await self._get_current_cwl_war_info()
        if not info: return {"error": "CWL off"}
        
        season, current_day = info['season'], info['day_number']
        
        if current_day >= 8:
            plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
            return {"current_day": current_day, "schedule": plan_doc['schedule'], "participation_score": plan_doc.get('participation_score', []), "finished": True} if plan_doc else {"error": "CWL acabou"}
        
        if not info['active_war']: return {"error": "Sem guerra ativa"}
        
        try:
            # Passa active_war para incluir participantes fora do clã
            players, _ = await self._fetch_cwl_player_pool(info['active_war'])
            if not players: return {"error": "Players not found"}
            
            plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
            
            plan_data = await self._generate_intelligent_plan(
                players=players, team_size=info['team_size'], active_war=info['active_war'],
                current_day=current_day, season_state=info.get('season_state'),
                opponent_analysis=info.get('opponent_analysis'), existing_plan=plan_doc
            )
            
            if self.rotation_engine and 'schedule' in plan_data:
                all_players_val = [CWLPlayer.from_dict(p) for p in (plan_data['schedule'][-1]['active_roster'] + plan_data['schedule'][-1]['active_bench'] + plan_data['schedule'][-1]['backup_bench'])]
                day_plans = [DayPlan(day=d['day'], active_roster=[CWLPlayer.from_dict(p) for p in d['active_roster']], substitutions=[], active_bench=[], backup_bench=[]) for d in plan_data['schedule']]
                issues = self.rotation_engine.predict_participation_issues(day_plans, all_players_val)
                plan_data['predicted_issues'] = issues
                
                critical = len([i for i in issues if i['severity'] == 'critical'])
                if critical:
                    warn = plan_data.get('warning') or ""
                    plan_data['warning'] = (warn + f"\n🚨 {critical} problemas críticos!").strip()

            await self.cwl_plan_collection.update_one({"_id": season}, {"$set": {
                "schedule": plan_data['schedule'], "participation_score": plan_data.get('participation_score', []),
                "warning": plan_data.get('warning'), "predicted_issues": plan_data.get('predicted_issues', []),
                "season_state": asdict(info.get('season_state')) if info.get('season_state') else None,
                "last_updated": datetime.datetime.now(pytz.utc), "team_size": info['team_size']
            }}, upsert=True)
            
            plan_data['current_day'] = current_day
            plan_data['season_state'] = asdict(info.get('season_state')) if info.get('season_state') else None
            return plan_data
        except Exception as e: logger.error(f"Erro fatal rotation: {e}", exc_info=True); return {"error": str(e)}

    async def _generate_intelligent_plan(self, players: List[CWLPlayer], team_size: int, active_war: coc.ClanWar, current_day: int, season_state: SeasonState, opponent_analysis: Optional[OpponentAnalysis], existing_plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.rotation_engine: await self._initialize_engine(team_size)
        
        roster, active_bench, backup_bench = await self._build_initial_state_from_war(players, active_war, current_day, existing_plan)
        
        strategy = self.rotation_engine.determine_optimal_strategy(season_state, current_day, opponent_analysis) if self.config["auto_adjust_strategy"] else RotationStrategy.BALANCED
        
        schedule, warnings = [], []
        if len(roster) < team_size: warnings.append(f"⚠️ Roster inicial ({len(roster)}) menor que guerra ({team_size})")
        
        # Dia atual
        contingency = self.rotation_engine.generate_contingency_plan(roster, active_bench + backup_bench, current_day)
        schedule.append(DayPlan(
            day=current_day, active_roster=roster.copy(), substitutions=[],
            active_bench=sorted(active_bench, key=lambda p: (-p.participation_urgency, -p.town_hall)),
            backup_bench=sorted(backup_bench, key=lambda p: -p.town_hall),
            strategy_used=strategy, opponent_analysis=opponent_analysis,
            confidence_score=0.9, risk_factors=warnings.copy(), contingency_subs=contingency
        ))
        
        # Simula futuro
        curr_roster, curr_active, curr_backup = roster.copy(), active_bench.copy(), backup_bench.copy()
        
        for day in range(current_day + 1, 8):
            # Update counters
            for p in curr_roster: p.consecutive_days_played += 1; p.consecutive_days_rested = 0
            for p in curr_active + curr_backup: p.consecutive_days_rested += 1; p.consecutive_days_played = 0
            
            day_strat = self.rotation_engine.determine_optimal_strategy(season_state, day, None)
            new_roster, subs, day_warns = self.rotation_engine.calculate_rotation(curr_roster, curr_active, curr_backup, day, day_strat, season_state)
            warnings.extend(day_warns)
            
            # Update lists
            old_tags = {p.tag for p in curr_roster}
            new_tags = {p.tag for p in new_roster}
            out_players = [p for p in curr_roster if p.tag not in new_tags]
            
            for p in out_players:
                if p.status in [PlayerStatus.ACTIVE, PlayerStatus.PRIORITY]: curr_active.append(p)
                else: curr_backup.append(p)
            
            curr_active = [p for p in curr_active if p.tag not in new_tags]
            curr_backup = [p for p in curr_backup if p.tag not in new_tags]
            
            for p in new_roster:
                if p.tag not in old_tags: p.days_played += 1
            
            curr_roster = new_roster
            
            schedule.append(DayPlan(
                day=day, active_roster=curr_roster.copy(), substitutions=subs,
                active_bench=sorted(curr_active, key=lambda p: (-p.participation_urgency, -p.town_hall)),
                backup_bench=sorted(curr_backup, key=lambda p: -p.town_hall),
                strategy_used=day_strat, confidence_score=0.8, risk_factors=day_warns
            ))
            
        all_final = curr_roster + curr_active + curr_backup
        scores = sorted([{"player": p.to_dict(), "days_played": p.days_played, "urgency": p.participation_urgency} for p in all_final], key=lambda x: x['days_played'], reverse=True)
        
        return {
            "schedule": [d.to_dict() for d in schedule], "participation_score": scores,
            "warning": "\n".join(set(warnings)) if warnings else None,
            "strategy_summary": {"primary_strategy": strategy.name, "season_context": season_state.context.name}
        }

    @commands.command(name='forcarplano')
    @commands.has_permissions(administrator=True)
    async def force_plan_command(self, ctx: commands.Context):
        await ctx.message.add_reaction("🔄")
        try:
            self.posted_daily_plans.clear()
            res = await self.generate_rotation_plan()
            if "error" in res: await ctx.send(f"❌ {res['error']}")
            else:
                await ctx.message.add_reaction("✅")
                strat = res.get('strategy_summary', {})
                await ctx.send(f"✅ Plano IA v5.8 regenerado!\n🧠 Estratégia: **{strat.get('primary_strategy')}**\n🎯 Contexto: **{strat.get('season_context')}**")
                info = await self._get_current_cwl_war_info()
                if info: await self._post_daily_plan_if_needed(info, res)
        except Exception as e: logger.error(e); await ctx.send(f"❌ Erro: {e}")

    # Outros comandos mantidos (statusplano, participacao, forcarjogador etc.)
    @commands.command(name='statusplano')
    async def plan_status_command(self, ctx: commands.Context):
        info = await self._get_current_cwl_war_info()
        if not info: return await ctx.send("CWL inativa.")
        plan = await self.generate_rotation_plan()
        embed = discord.Embed(title="📊 Status CWL IA v5.8", color=discord.Color.blue())
        embed.add_field(name="Dia", value=str(info['day_number']))
        if 'error' not in plan:
            strat = plan.get('strategy_summary', {})
            embed.add_field(name="Estratégia", value=strat.get('primary_strategy', 'N/A'))
            warn = plan.get('warning')
            if warn: embed.add_field(name="⚠️ Avisos", value=warn, inline=False)
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    if bot.cwl_planner_channel_id and bot.db is not None:
        await bot.add_cog(CwlPlannerCog(bot))
