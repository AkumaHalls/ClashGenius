# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
from typing import Dict, List, Any, Optional, Set, Tuple, Callable
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
    PRIORITY = "priority"
    RESTING = "resting"


class RotationStrategy(Enum):
    AGGRESSIVE = auto()
    BALANCED = auto()
    FAIR = auto()
    SURVIVAL = auto()


class WarContext(Enum):
    WINNING = auto()
    COMPETITIVE = auto()
    LOSING = auto()
    COMFORTABLE = auto()


# ==================== MODELOS DE DADOS ====================

@dataclass
class PlayerMetrics:
    attack_success_rate: float = 0.0
    average_stars: float = 0.0
    defense_weight: float = 0.0
    reliability_score: float = 1.0
    versatility: float = 0.5
    last_updated: Optional[datetime.datetime] = None
    
    def overall_score(self) -> float:
        return (
            self.attack_success_rate * 0.35 +
            (self.average_stars / 3.0) * 0.25 +
            self.reliability_score * 0.25 +
            self.versatility * 0.15
        )


@dataclass
class CWLPlayer:
    tag: str
    name: str
    town_hall: int
    days_played: int = 0
    status: PlayerStatus = PlayerStatus.ACTIVE
    metrics: PlayerMetrics = field(default_factory=PlayerMetrics)
    consecutive_days_played: int = 0
    consecutive_days_rested: int = 0
    forced_inclusion: bool = False
    forced_exclusion: bool = False
    notes: str = ""
    
    def __post_init__(self):
        if isinstance(self.status, str):
            try:
                self.status = PlayerStatus(self.status)
            except ValueError:
                self.status = PlayerStatus.ACTIVE
    
    @property
    def effective_strength(self) -> float:
        base_strength = self.town_hall * 10
        metric_modifier = self.metrics.overall_score()
        fatigue_penalty = min(0.15, self.consecutive_days_played * 0.03)
        rest_bonus = min(0.1, self.consecutive_days_rested * 0.02)
        return base_strength * (1 + metric_modifier - fatigue_penalty + rest_bonus)
    
    @property
    def participation_urgency(self) -> float:
        if self.forced_inclusion: return 100.0
        if self.forced_exclusion: return -100.0
        rest_urgency = self.consecutive_days_rested * 2.0
        overplay_penalty = max(0, self.consecutive_days_played - 3) * 1.5
        return rest_urgency - overplay_penalty
    
    def to_dict(self) -> Dict[str, Any]:
        # CORREÇÃO: Converte explicitamente o Enum 'status' para valor string
        return {
            "tag": self.tag,
            "name": self.name,
            "town_hall": self.town_hall,
            "days_played": self.days_played,
            "status": self.status.value, # Importante: .value aqui
            "metrics": asdict(self.metrics),
            "consecutive_days_played": self.consecutive_days_played,
            "consecutive_days_rested": self.consecutive_days_rested,
            "forced_inclusion": self.forced_inclusion,
            "forced_exclusion": self.forced_exclusion,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CWLPlayer":
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
    clan_tag: str
    clan_name: str
    estimated_strength: float
    th_distribution: Dict[int, int]
    threat_level: str
    recommended_strategy: RotationStrategy
    
    def to_dict(self) -> Dict[str, Any]:
        # CORREÇÃO: Converte explicitamente o Enum 'recommended_strategy' para nome string
        return {
            "clan_tag": self.clan_tag,
            "clan_name": self.clan_name,
            "estimated_strength": self.estimated_strength,
            "th_distribution": self.th_distribution,
            "threat_level": self.threat_level,
            "recommended_strategy": self.recommended_strategy.name # Importante: .name aqui
        }


@dataclass 
class DayPlan:
    day: int
    active_roster: List[CWLPlayer]
    substitutions: List[Dict[str, Any]]
    active_bench: List[CWLPlayer]
    backup_bench: List[CWLPlayer]
    strategy_used: RotationStrategy = RotationStrategy.BALANCED
    opponent_analysis: Optional[OpponentAnalysis] = None
    confidence_score: float = 0.0
    risk_factors: List[str] = field(default_factory=list)
    contingency_subs: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day,
            "active_roster": [p.to_dict() for p in self.active_roster],
            "substitutions": self.substitutions,
            "active_bench": [p.to_dict() for p in self.active_bench],
            "backup_bench": [p.to_dict() for p in self.backup_bench],
            "strategy_used": self.strategy_used.name, # Já estava correto aqui
            "opponent_analysis": self.opponent_analysis.to_dict() if self.opponent_analysis else None,
            "confidence_score": self.confidence_score,
            "risk_factors": self.risk_factors,
            "contingency_subs": self.contingency_subs,
            "notes": self.notes
        }


@dataclass
class SeasonState:
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
        if self.promotion_zone: return WarContext.COMPETITIVE
        if self.relegation_zone: return WarContext.LOSING
        if self.current_position <= 2: return WarContext.WINNING
        if self.current_position >= self.total_clans - 1: return WarContext.LOSING
        return WarContext.COMFORTABLE


# ==================== MOTOR DE DECISÃO INTELIGENTE ====================

class DecisionFactor(ABC):
    @abstractmethod
    def evaluate(self, player: CWLPlayer, context: Dict[str, Any]) -> float: pass
    @property
    @abstractmethod
    def weight(self) -> float: pass
    @property
    @abstractmethod
    def name(self) -> str: pass

class FairnessFactor(DecisionFactor):
    def evaluate(self, player: CWLPlayer, context: Dict[str, Any]) -> float:
        team_size = context.get("team_size", 15)
        total_players = context.get("total_players", 1)
        current_day = context.get("current_day", 1)
        ideal = (team_size / total_players) * (current_day - 1)
        return max(-1.0, min(1.0, (ideal - player.days_played) / 3))
    @property
    def weight(self) -> float: return 0.25
    @property
    def name(self) -> str: return "Fairness"

class StrengthFactor(DecisionFactor):
    def evaluate(self, player: CWLPlayer, context: Dict[str, Any]) -> float:
        max_th = context.get("max_th", 17)
        norm = player.effective_strength / (max_th * 15)
        return max(-1.0, min(1.0, (norm - 0.5) * 2))
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
        needed = context.get("min_games_target", 1) - player.days_played
        if needed <= 0: return -0.3
        days_left = context.get("days_remaining", 1)
        if needed >= days_left: return 1.0
        return needed / days_left
    @property
    def weight(self) -> float: return 0.10
    @property
    def name(self) -> str: return "Urgency"


class IntelligentRotationEngine:
    def __init__(self, team_size: int, total_days: int = 7):
        self.team_size = team_size
        self.total_days = total_days
        self.decision_factors = [FairnessFactor(), StrengthFactor(), FatigueFactor(), ReliabilityFactor(), UrgencyFactor()]
    
    def _adjust_weights_for_strategy(self, strategy: RotationStrategy) -> Dict[str, float]:
        base = {f.name: f.weight for f in self.decision_factors}
        if strategy == RotationStrategy.AGGRESSIVE:
            base.update({"Strength": 0.50, "Fairness": 0.10, "Reliability": 0.25})
        elif strategy == RotationStrategy.FAIR:
            base.update({"Fairness": 0.45, "Urgency": 0.20, "Strength": 0.15})
        elif strategy == RotationStrategy.SURVIVAL:
            base.update({"Reliability": 0.40, "Strength": 0.35, "Fatigue": 0.05})
        total = sum(base.values())
        return {k: v/total for k, v in base.items()}
    
    def calculate_player_score(self, player: CWLPlayer, context: Dict[str, Any], strategy: RotationStrategy) -> Tuple[float, Dict[str, float]]:
        weights = self._adjust_weights_for_strategy(strategy)
        breakdown = {}
        total = 0.0
        for f in self.decision_factors:
            score = f.evaluate(player, context)
            w = weights.get(f.name, f.weight)
            weighted = score * w
            breakdown[f.name] = {"raw": score, "weight": w, "weighted": weighted}
            total += weighted
        if player.forced_inclusion: total += 10.0
        if player.forced_exclusion: total -= 10.0
        return total, breakdown
    
    def determine_optimal_strategy(self, season_state: SeasonState, current_day: int, opponent: Optional[OpponentAnalysis]) -> RotationStrategy:
        remaining = self.total_days - current_day + 1
        ctx = season_state.context
        if remaining <= 2: return RotationStrategy.FAIR
        if ctx == WarContext.LOSING and season_state.relegation_zone: return RotationStrategy.AGGRESSIVE
        if ctx == WarContext.COMPETITIVE:
            if opponent and opponent.threat_level in ["high", "extreme"]: return RotationStrategy.AGGRESSIVE
            return RotationStrategy.BALANCED
        if ctx == WarContext.COMFORTABLE: return RotationStrategy.FAIR
        if ctx == WarContext.WINNING and remaining >= 4: return RotationStrategy.FAIR
        return RotationStrategy.BALANCED
    
    def calculate_rotation(self, roster: List[CWLPlayer], active_bench: List[CWLPlayer], backup_bench: List[CWLPlayer], current_day: int, strategy: RotationStrategy, season_state: Optional[SeasonState] = None) -> Tuple[List[CWLPlayer], List[Dict[str, Any]], List[str]]:
        warnings = []
        remaining = self.total_days - current_day + 1
        available = [p for p in roster + active_bench if not p.forced_exclusion]
        all_p = available + backup_bench
        context = {
            "total_days": self.total_days, "current_day": current_day, "days_remaining": remaining,
            "total_players": len(all_p), "team_size": self.team_size,
            "max_th": max((p.town_hall for p in all_p), default=17), "min_games_target": max(1, int(self.total_days * 0.4))
        }
        
        scores = []
        for p in available:
            s, bd = self.calculate_player_score(p, context, strategy)
            scores.append((p, s, bd))
        scores.sort(key=lambda x: x[1], reverse=True)
        
        new_roster = [x[0] for x in scores[:self.team_size]]
        new_bench = [x[0] for x in scores[self.team_size:]]
        
        # Garante min CVs altos
        th_counts = defaultdict(int)
        for p in new_roster: th_counts[p.town_hall] += 1
        max_th = max(th_counts.keys()) if th_counts else 17
        high_th = sum(v for k, v in th_counts.items() if k >= max_th - 1)
        
        if high_th < min(5, self.team_size // 3):
            warnings.append(f"⚠️ Poucos CVs altos ({high_th}) no roster")
            high_on_bench = [p for p in new_bench if p.town_hall >= max_th - 1]
            low_in_roster = sorted([p for p in new_roster if p.town_hall < max_th - 1], key=lambda p: p.town_hall)
            swaps = min(len(high_on_bench), len(low_in_roster), min(5, self.team_size // 3) - high_th)
            for i in range(swaps):
                new_roster.remove(low_in_roster[i]); new_roster.append(high_on_bench[i])
                new_bench.remove(high_on_bench[i]); new_bench.append(low_in_roster[i])
        
        old_tags = {p.tag for p in roster}
        new_tags = {p.tag for p in new_roster}
        
        players_out = [p for p in roster if p.tag not in new_tags]
        players_in = [p for p in new_roster if p.tag not in old_tags]
        
        # Sort for better matching in substitutions logic if needed
        players_out.sort(key=lambda p: -p.days_played)
        players_in.sort(key=lambda p: p.days_played)

        subs = []
        for po, pi in zip(players_out, players_in):
            _, out_bd = self.calculate_player_score(po, context, strategy)
            _, in_bd = self.calculate_player_score(pi, context, strategy)
            reasons = []
            for f in ["Fairness", "Fatigue", "Urgency"]:
                out_val = out_bd.get(f, {}).get("raw", 0)
                in_val = in_bd.get(f, {}).get("raw", 0)
                if abs(in_val - out_val) > 0.3:
                    if f == "Fairness" and in_val > out_val: reasons.append("equilíbrio")
                    elif f == "Fatigue" and in_val > out_val: reasons.append("descanso")
                    elif f == "Urgency" and in_val > out_val: reasons.append("medalhas")
            reason_str = ", ".join(reasons) if reasons else "otimização"
            subs.append({"out": po.to_dict(), "in": pi.to_dict(), "reason": reason_str.capitalize(), "score_diff": 0})
            
        if len(new_roster) < self.team_size:
            deficit = self.team_size - len(new_roster)
            warnings.append(f"🚨 CRÍTICO: Faltam {deficit} jogadores!")
            needed = min(deficit, len(backup_bench))
            pulls = sorted(backup_bench, key=lambda p: -p.town_hall)[:needed]
            new_roster.extend(pulls)
            for p in pulls: subs.append({"out": None, "in": p.to_dict(), "reason": "EMERGÊNCIA", "emergency": True})
            
        return new_roster, subs, warnings

    def generate_contingency_plan(self, roster: List[CWLPlayer], bench: List[CWLPlayer], current_day: int) -> List[Dict[str, Any]]:
        contingencies = []
        bench_sorted = sorted(bench, key=lambda p: (-p.town_hall, p.days_played))
        for rp in roster:
            subs = [p for p in bench_sorted if abs(p.town_hall - rp.town_hall) <= 1]
            if subs:
                contingencies.append({
                    "if_unavailable": rp.to_dict(), "replace_with": subs[0].to_dict(),
                    "th_diff": subs[0].town_hall - rp.town_hall, "priority": "high" if rp.town_hall >= 15 else "normal"
                })
        return contingencies

    def predict_participation_issues(self, schedule: List[DayPlan], all_players: List[CWLPlayer]) -> List[Dict[str, Any]]:
        issues = []
        participation = defaultdict(int)
        for day in schedule:
            for player in day.active_roster: participation[player.tag] += 1
        
        total_days = len(schedule)
        min_acc = max(1, int(total_days * 0.3))
        ideal = (15 * total_days) / len(all_players) if all_players else 0
        
        for p in all_players:
            g = participation.get(p.tag, 0)
            if g == 0: issues.append({"player": p.to_dict(), "type": "ZERO", "severity": "critical", "message": f"{p.name} não jogará!", "suggested_action": "Forçar inclusão"})
            elif g < min_acc: issues.append({"player": p.to_dict(), "type": "LOW", "severity": "warning", "message": f"{p.name} jogará pouco ({g})", "suggested_action": "Rotacionar"})
            elif g > ideal * 1.5: issues.append({"player": p.to_dict(), "type": "HIGH", "severity": "info", "message": f"{p.name} jogará {g} (alto)", "suggested_action": "Descanso"})
        return issues


class OpponentAnalyzer:
    def __init__(self, api_client): self.api_client = api_client
    async def analyze_opponent(self, tag: str, name: str, war: Optional[coc.ClanWar] = None) -> OpponentAnalysis:
        th_dist = defaultdict(int); strength = 0.0
        try:
            if war:
                clan = war.opponent if war.clan.tag != tag else war.clan
                for m in clan.members: th_dist[m.town_hall] += 1; strength += m.town_hall * 10
            else:
                clan = await self.api_client.get_clan(tag)
                for m in clan.members: th_dist[m.town_hall] += 1; strength += m.town_hall * 10
        except Exception: pass
        
        max_th = max(th_dist.keys()) if th_dist else 15
        high_th = sum(v for k, v in th_dist.items() if k >= max_th - 1)
        
        if high_th >= 10 and max_th >= 16: threat = "extreme"
        elif high_th >= 7 or max_th >= 16: threat = "high"
        elif high_th >= 4: threat = "medium"
        else: threat = "low"
        
        strat_map = {"extreme": RotationStrategy.AGGRESSIVE, "high": RotationStrategy.AGGRESSIVE, "medium": RotationStrategy.BALANCED, "low": RotationStrategy.FAIR}
        return OpponentAnalysis(tag, name, strength, dict(th_dist), threat, strat_map[threat])


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
        
        self.posted_daily_plans: Set[str] = set()
        self.posted_inactivity_alerts: Set[str] = set()
        self.last_known_members: Set[str] = set()
        self.reported_leavers: Set[str] = set()
        self.season_state: Optional[SeasonState] = None
        
        self.config = {
            "min_participation_percent": 0.3, "max_consecutive_days": 5,
            "alert_hours_before_end": 4, "auto_adjust_strategy": True
        }

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
        if self.bot.api_client:
            self.opponent_analyzer = OpponentAnalyzer(self.bot.api_client)

    async def _load_persistent_state(self):
        if self.cwl_state_collection is None: return
        try:
            state = await self.cwl_state_collection.find_one({"_id": "cog_state"})
            if state:
                self.posted_daily_plans = set(state.get("posted_daily_plans", []))
                self.posted_inactivity_alerts = set(state.get("posted_inactivity_alerts", []))
                self.last_known_members = set(state.get("last_known_members", []))
                self.reported_leavers = set(state.get("reported_leavers", []))
                if state.get("season_state"):
                    self.season_state = SeasonState(**state.get("season_state"))
                logger.info("Estado persistente carregado com sucesso.")
            self._cache_initialized = True
        except Exception as e:
            logger.error(f"Erro ao carregar estado persistente: {e}")

    async def _save_persistent_state(self):
        if self.cwl_state_collection is None: return
        try:
            state_data = {
                "posted_daily_plans": list(self.posted_daily_plans),
                "posted_inactivity_alerts": list(self.posted_inactivity_alerts),
                "last_known_members": list(self.last_known_members),
                "reported_leavers": list(self.reported_leavers),
                "updated_at": datetime.datetime.now(pytz.utc)
            }
            
            if self.season_state:
                state_data["season_state"] = asdict(self.season_state)
            
            await self.cwl_state_collection.update_one(
                {"_id": "cog_state"},
                {"$set": state_data},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Erro ao salvar estado persistente: {e}")

    async def _load_player_metrics(self, player_tag: str) -> PlayerMetrics:
        if self.player_metrics_collection is None: return PlayerMetrics()
        try:
            doc = await self.player_metrics_collection.find_one({"_id": player_tag})
            if doc:
                return PlayerMetrics(
                    attack_success_rate=doc.get("attack_success_rate", 0.0),
                    average_stars=doc.get("average_stars", 0.0),
                    defense_weight=doc.get("defense_weight", 0.0),
                    reliability_score=doc.get("reliability_score", 1.0),
                    versatility=doc.get("versatility", 0.5),
                    last_updated=doc.get("last_updated")
                )
        except Exception: pass
        return PlayerMetrics()

    async def _update_player_metrics_from_war(self, war: coc.ClanWar):
        if self.player_metrics_collection is None or not war: return
        try:
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            for member in our_clan.members:
                if member.attacks:
                    existing = await self._load_player_metrics(member.tag)
                    stars = sum(a.stars for a in member.attacks)
                    rate = sum(1 for a in member.attacks if a.stars == 3) / len(member.attacks)
                    avg = stars / len(member.attacks)
                    
                    war_len = (war.end_time.time - war.start_time.time).total_seconds()
                    rel = existing.reliability_score
                    for a in member.attacks:
                        timing = (a.time.time - war.start_time.time).total_seconds()
                        rel = min(1.0, rel + 0.05) if timing < war_len * 0.8 else max(0.3, rel - 0.1)

                    await self.player_metrics_collection.update_one(
                        {"_id": member.tag},
                        {"$set": {
                            "attack_success_rate": 0.3 * rate + 0.7 * existing.attack_success_rate,
                            "average_stars": 0.3 * avg + 0.7 * existing.average_stars,
                            "reliability_score": rel,
                            "last_updated": datetime.datetime.now(pytz.utc)
                        }},
                        upsert=True
                    )
        except Exception as e:
            logger.error(f"Erro ao atualizar métricas: {e}")

    async def _update_season_state(self, cwl_group) -> SeasonState:
        try:
            our_clan = next((c for c in cwl_group.clans if c.tag == self.bot.clan_tag), None)
            if not our_clan: return SeasonState()
            
            clans_sorted = sorted(cwl_group.clans, key=lambda c: (-c.stars, c.destruction_percentage))
            pos = next((i + 1 for i, c in enumerate(clans_sorted) if c.tag == self.bot.clan_tag), len(clans_sorted))
            
            state = SeasonState(
                current_position=pos,
                total_clans=len(cwl_group.clans),
                total_stars=our_clan.stars,
                stars_behind_leader=clans_sorted[0].stars - our_clan.stars,
                stars_ahead_of_relegation=our_clan.stars - clans_sorted[-1].stars,
                promotion_zone=pos <= 2,
                relegation_zone=pos >= len(cwl_group.clans) - 1
            )
            self.season_state = state
            return state
        except Exception: return SeasonState()

    async def _send_planner_embed(self, embed: discord.Embed) -> bool:
        if not self.bot.cwl_planner_channel_id:
            logger.warning("Canal do planejador CWL não configurado.")
            return False
        try:
            channel = self.bot.get_channel(self.bot.cwl_planner_channel_id) or await self.bot.fetch_channel(self.bot.cwl_planner_channel_id)
            await channel.send(embed=embed)
            return True
        except Exception as e:
            logger.error(f"Falha ao enviar embed: {e}")
            return False

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

            if wars_by_state['inWar']:
                active_war, day_number, active_war_tag, opp = wars_by_state['inWar'][0]
            elif wars_by_state['preparation']:
                active_war, day_number, active_war_tag, opp = wars_by_state['preparation'][0]
            elif wars_by_state['warEnded']:
                last_war, last_day, last_tag, opp = max(wars_by_state['warEnded'], key=lambda x: x[1])
                day_number = min(last_day + 1, 8)
                active_war, active_war_tag = last_war, last_tag
            
            if day_number == 0: day_number = 1 if cwl_group.state == "preparation" else 8
            
            if self.opponent_analyzer and active_war and opp:
                opponent_info = await self.opponent_analyzer.analyze_opponent(opp.tag, opp.name, active_war)
            
            await self._initialize_engine(active_war.team_size if active_war else 15)
            
            return {
                "active_war": active_war,
                "day_number": day_number,
                "season": cwl_group.season,
                "war_tag": active_war_tag,
                "team_size": active_war.team_size if active_war else 15,
                "cwl_state": cwl_group.state,
                "season_state": season_state,
                "opponent_analysis": opponent_info,
                "cwl_group": cwl_group
            }
        except Exception as e:
            logger.error(f"Erro get_current_cwl_war_info: {e}")
            return None

    async def _fetch_cwl_player_pool(self, active_war: Optional[coc.ClanWar] = None) -> Tuple[List[CWLPlayer], Set[str]]:
        if not self.bot.api_client: return [], set()
        try:
            cwl_group, clan = await asyncio.gather(self.bot.api_client.get_league_group(self.bot.clan_tag), self.bot.api_client.get_clan(self.bot.clan_tag))
            if not cwl_group: return [], set()
            
            current_member_tags = {m.tag for m in clan.members}
            war_participant_tags = set()
            if active_war:
                side = active_war.clan if active_war.clan.tag == self.bot.clan_tag else active_war.opponent
                war_participant_tags = {m.tag for m in side.members}
            
            our_cwl_clan = next((c for c in cwl_group.clans if c.tag == self.bot.clan_tag), None)
            if not our_cwl_clan: return [], current_member_tags
            
            db_cog = self.bot.get_cog("Banco de Dados")
            player_statuses = await db_cog.load_player_notes_from_db() if db_cog else {}
            
            players = []
            all_relevant_tags = current_member_tags.union(war_participant_tags)

            for member in our_cwl_clan.members:
                if member.tag in all_relevant_tags:
                    status_data = player_statuses.get(member.tag, {})
                    try: status = PlayerStatus(status_data.get('cwl_status', 'active'))
                    except ValueError: status = PlayerStatus.ACTIVE
                    
                    players.append(CWLPlayer(
                        tag=member.tag, name=member.name, town_hall=member.town_hall, status=status,
                        metrics=await self._load_player_metrics(member.tag),
                        notes=status_data.get('notes', ''),
                        forced_inclusion=status_data.get('forced_in', False),
                        forced_exclusion=status_data.get('forced_out', False)
                    ))
            
            # Fallback para jogadores desconhecidos na guerra
            if active_war and len(players) < active_war.team_size:
                player_tags = {p.tag for p in players}
                for tag in war_participant_tags:
                    if tag not in player_tags:
                        logger.warning(f"Adicionando jogador fantasma para tag {tag}")
                        players.append(CWLPlayer(tag=tag, name="Unknown/Left", town_hall=1, status=PlayerStatus.ACTIVE))

            return players, current_member_tags
        except Exception: return [], set()

    async def _build_initial_state_from_war(self, players: List[CWLPlayer], active_war: coc.ClanWar, current_day: int, plan_doc: Optional[Dict[str, Any]] = None) -> Tuple[List[CWLPlayer], List[CWLPlayer], List[CWLPlayer]]:
        participation_history = defaultdict(lambda: {"days_played": 0, "consecutive": 0, "last_day": 0})
        if plan_doc and 'schedule' in plan_doc:
            for day_data in plan_doc['schedule']:
                if day_data.get('day', 0) < current_day:
                    for p_data in day_data.get('active_roster', []):
                        tag = p_data.get('tag') or p_data.get('player', {}).get('tag')
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
        
        season, current_day, active_war = info['season'], info['day_number'], info['active_war']
        
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
        
        if not active_war: return {"error": "Não foi possível encontrar guerra ativa."}
        
        try:
            players, _ = await self._fetch_cwl_player_pool(active_war)
            if not players: return {"error": "Não foi possível buscar jogadores da CWL."}
            
            plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
            
            plan_data = await self._generate_intelligent_plan(
                players=players,
                team_size=info['team_size'],
                active_war=active_war,
                current_day=current_day,
                season_state=info.get('season_state'),
                opponent_analysis=info.get('opponent_analysis'),
                existing_plan=plan_doc
            )
            
            if "error" in plan_data: return plan_data
            
            # Predict issues
            if self.rotation_engine and 'schedule' in plan_data:
                all_players_val = [CWLPlayer.from_dict(p) for p in (plan_data['schedule'][-1]['active_roster'] + plan_data['schedule'][-1]['active_bench'] + plan_data['schedule'][-1]['backup_bench'])]
                day_plans = [DayPlan(day=d['day'], active_roster=[CWLPlayer.from_dict(p) for p in d['active_roster']], substitutions=[], active_bench=[], backup_bench=[]) for d in plan_data['schedule']]
                issues = self.rotation_engine.predict_participation_issues(day_plans, all_players_val)
                plan_data['predicted_issues'] = issues
                
                critical = len([i for i in issues if i['severity'] == 'critical'])
                if critical:
                    warning = plan_data.get('warning') or ""
                    plan_data['warning'] = (warning + f"\n🚨 {critical} jogadores com problemas críticos de participação!").strip()
            
            # Save to DB
            await self.cwl_plan_collection.update_one(
                {"_id": season},
                {"$set": {
                    "schedule": plan_data['schedule'],
                    "participation_score": plan_data.get('participation_score', []),
                    "warning": plan_data.get('warning'),
                    "predicted_issues": plan_data.get('predicted_issues', []),
                    "season_state": asdict(info.get('season_state')) if info.get('season_state') else None,
                    "last_updated": datetime.datetime.now(pytz.utc),
                    "team_size": info['team_size']
                }},
                upsert=True
            )
            
            plan_data['current_day'] = current_day
            plan_data['season_state'] = asdict(info.get('season_state')) if info.get('season_state') else None
            return plan_data
            
        except Exception as e:
            logger.error(f"Erro fatal em generate_rotation_plan: {e}", exc_info=True)
            return {"error": str(e)}

    async def _generate_intelligent_plan(self, players: List[CWLPlayer], team_size: int, active_war: coc.ClanWar, current_day: int, season_state: SeasonState, opponent_analysis: Optional[OpponentAnalysis], existing_plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.rotation_engine: await self._initialize_engine(team_size)
        
        roster, active_bench, backup_bench = await self._build_initial_state_from_war(players, active_war, current_day, existing_plan)
        
        strategy = self.rotation_engine.determine_optimal_strategy(season_state, current_day, opponent_analysis) if self.config["auto_adjust_strategy"] else RotationStrategy.BALANCED
        
        schedule = []
        warnings = []
        
        if len(roster) < team_size: warnings.append(f"⚠️ Roster inicial ({len(roster)}) menor que tamanho da guerra ({team_size}).")
        
        contingency = self.rotation_engine.generate_contingency_plan(roster, active_bench + backup_bench, current_day)
        
        day_plan = DayPlan(
            day=current_day,
            active_roster=roster.copy(),
            substitutions=[],
            active_bench=sorted(active_bench, key=lambda p: (-p.participation_urgency, -p.town_hall)),
            backup_bench=sorted(backup_bench, key=lambda p: -p.town_hall),
            strategy_used=strategy,
            opponent_analysis=opponent_analysis,
            confidence_score=0.9,
            risk_factors=warnings.copy(),
            contingency_subs=contingency
        )
        schedule.append(day_plan)
        
        current_roster = roster.copy()
        current_active_bench = active_bench.copy()
        current_backup_bench = backup_bench.copy()
        
        for day in range(current_day + 1, 8):
            for p in current_roster:
                p.consecutive_days_played += 1
                p.consecutive_days_rested = 0
            for p in current_active_bench + current_backup_bench:
                p.consecutive_days_rested += 1
                p.consecutive_days_played = 0
            
            day_strategy = self.rotation_engine.determine_optimal_strategy(season_state, day, None)
            new_roster, substitutions, day_warnings = self.rotation_engine.calculate_rotation(
                current_roster, current_active_bench, current_backup_bench, day, day_strategy, season_state
            )
            warnings.extend(day_warnings)
            
            old_roster_tags = {p.tag for p in current_roster}
            new_roster_tags = {p.tag for p in new_roster}
            
            players_out = [p for p in current_roster if p.tag not in new_roster_tags]
            
            for player in players_out:
                if player.status in [PlayerStatus.ACTIVE, PlayerStatus.PRIORITY]:
                    current_active_bench.append(player)
                else:
                    current_backup_bench.append(player)
            
            current_active_bench = [p for p in current_active_bench if p.tag not in new_roster_tags]
            current_backup_bench = [p for p in current_backup_bench if p.tag not in new_roster_tags]
            
            for player in new_roster:
                if player.tag not in old_roster_tags:
                    player.days_played += 1
            
            current_roster = new_roster
            contingency = self.rotation_engine.generate_contingency_plan(current_roster, current_active_bench + current_backup_bench, day)
            
            day_plan = DayPlan(
                day=day,
                active_roster=current_roster.copy(),
                substitutions=substitutions,
                active_bench=sorted(current_active_bench, key=lambda p: (-p.participation_urgency, -p.town_hall)),
                backup_bench=sorted(current_backup_bench, key=lambda p: -p.town_hall),
                strategy_used=day_strategy,
                confidence_score=0.8,
                risk_factors=day_warnings,
                contingency_subs=contingency
            )
            schedule.append(day_plan)
        
        all_players_final = current_roster + current_active_bench + current_backup_bench
        participation_score = sorted(
            [{"player": p.to_dict(), "days_played": p.days_played, "urgency": p.participation_urgency} for p in all_players_final],
            key=lambda x: x['days_played'],
            reverse=True
        )
        
        return {
            "schedule": [d.to_dict() for d in schedule],
            "participation_score": participation_score,
            "warning": "\n".join(set(warnings)) if warnings else None,
            "strategy_summary": {"primary_strategy": strategy.name, "season_context": season_state.context.name}
        }

    # ==================== TASKS ====================

    @tasks.loop(minutes=15)
    async def cwl_monitoring_task(self):
        await self.bot.wait_until_ready()
        if hasattr(self.bot, 'coc_client_ready'):
            await self.bot.coc_client_ready.wait()
        
        try:
            await self._check_roster_changes()
            info = await self._get_current_cwl_war_info()
            if not info:
                if self.posted_daily_plans:
                    self.posted_daily_plans.clear()
                    self.posted_inactivity_alerts.clear()
                    self.reported_leavers.clear()
                    await self._save_persistent_state()
                return
            
            plan_data = await self.generate_rotation_plan()
            if "error" not in plan_data:
                await self._post_daily_plan_if_needed(info, plan_data)
                if info['active_war']:
                    await self._check_and_alert_inactivity(info['active_war'], info['war_tag'])
                    await self._alert_predicted_issues(plan_data)
            
            await self._save_persistent_state()
        except Exception as e:
            logger.error(f"Erro monitor task: {e}", exc_info=True)

    @tasks.loop(hours=1)
    async def metrics_update_task(self):
        await self.bot.wait_until_ready()
        if hasattr(self.bot, 'coc_client_ready'):
            await self.bot.coc_client_ready.wait()
        try:
            info = await self._get_current_cwl_war_info()
            if info and info['active_war']:
                st = info['active_war'].state
                ended = st == 'warEnded' if isinstance(st, str) else st.value == 'warEnded'
                if ended: await self._update_player_metrics_from_war(info['active_war'])
        except Exception as e:
            logger.error(f"Erro metrics task: {e}")

    @cwl_monitoring_task.before_loop
    async def before_cwl_monitoring(self): await self.bot.wait_until_ready()

    @metrics_update_task.before_loop
    async def before_metrics_update(self): await self.bot.wait_until_ready()

    async def _alert_predicted_issues(self, plan_data: Dict[str, Any]):
        issues = plan_data.get('predicted_issues', [])
        critical = [i for i in issues if i['severity'] == 'critical']
        if not critical: return
        
        key = f"issues-{len(critical)}-{datetime.date.today().isoformat()}"
        if key in self.posted_inactivity_alerts: return
        
        embed = discord.Embed(title="🚨 Problemas de Participação", color=discord.Color.orange(), timestamp=datetime.datetime.now(pytz.utc))
        for issue in critical[:5]:
            p = issue['player']
            embed.add_field(name=f"❌ {p.get('name', 'Unknown')}", value=f"{issue['message']}\n💡 *{issue['suggested_action']}*", inline=False)
        
        if await self._send_planner_embed(embed):
            self.posted_inactivity_alerts.add(key)

    async def _check_roster_changes(self):
        if not self.bot.api_client: return
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            curr = {m.tag for m in clan.members}
            if not self.last_known_members:
                self.last_known_members = curr
                return
            leavers = self.last_known_members - curr
            if leavers:
                info = await self._get_current_cwl_war_info()
                if info:
                    new_leavers = leavers - self.reported_leavers
                    if new_leavers:
                        p_info = []
                        for tag in new_leavers:
                            try:
                                p = await self.bot.api_client.get_player(tag)
                                p_info.append(f"• **{p.name}**")
                            except: p_info.append(f"• {tag}")
                        
                        embed = discord.Embed(title="🚪 Saídas na CWL!", description="O plano será ajustado.", color=discord.Color.red(), timestamp=datetime.datetime.now(pytz.utc))
                        embed.add_field(name="Jogadores", value="\n".join(p_info), inline=False)
                        await self._send_planner_embed(embed)
                        self.reported_leavers.update(new_leavers)
            self.last_known_members = curr
        except Exception: pass

    async def _post_daily_plan_if_needed(self, info: Dict[str, Any], plan_data: Dict[str, Any]):
        tag = info.get('war_tag')
        if not tag or tag in self.posted_daily_plans: return
        
        day = info['day_number']
        war = info['active_war']
        if not war: return
        
        plan = next((p for p in plan_data.get('schedule', []) if p['day'] == day), None)
        if not plan: return
        
        opp = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
        strat = plan.get('strategy_used', 'BALANCED')
        
        embed = discord.Embed(title=f"📋 Plano CWL - Dia {day} vs {opp.name}", description=f"**Estratégia:** {strat}", color=discord.Color.blue(), timestamp=datetime.datetime.now(pytz.utc))
        
        roster = sorted(plan['active_roster'], key=lambda p: p.get('town_hall', 0), reverse=True)
        lines = [f"`{i+1:02d}.` **{p.get('name')}** (CV{p.get('town_hall')}) - {p.get('days_played')}d" for i, p in enumerate(roster)]
        
        if len(lines) > 15:
            mid = len(lines) // 2
            embed.add_field(name="⚔️ Escalação (1/2)", value="\n".join(lines[:mid]), inline=False)
            embed.add_field(name="⚔️ Escalação (2/2)", value="\n".join(lines[mid:]), inline=False)
        else:
            embed.add_field(name="⚔️ Escalação", value="\n".join(lines), inline=False)
        
        subs = plan.get('substitutions', [])
        if subs:
            s_lines = [f"🔴 **{s['out']['name']}** → 🟢 **{s['in']['name']}**" for s in subs[:8]]
            embed.add_field(name="🔄 Substituições", value="\n".join(s_lines), inline=False)
        else:
            embed.add_field(name="🔄 Substituições", value="✅ Manter equipe.", inline=False)
        
        if plan_data.get('warning'):
            embed.add_field(name="⚠️ Avisos", value=plan_data['warning'], inline=False)
            
        if await self._send_planner_embed(embed):
            self.posted_daily_plans.add(tag)

    async def _check_and_alert_inactivity(self, war: coc.ClanWar, war_tag: str):
        if not war_tag: return
        rem = war.end_time.seconds_until
        if not (900 < rem < self.config["alert_hours_before_end"] * 3600): return
        
        clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
        inactive = [m for m in clan.members if len(m.attacks) < war.attacks_per_member]
        if not inactive: return
        
        alert_id = f"{war_tag}-inact-{len(inactive)}"
        if alert_id in self.posted_inactivity_alerts: return
        
        h = int(rem / 3600); m = int((rem % 3600) / 60)
        embed = discord.Embed(title="🚨 ALERTA INATIVIDADE", description=f"Faltam **{h}h {m}min**!", color=discord.Color.red() if h < 2 else discord.Color.orange(), timestamp=datetime.datetime.now(pytz.utc))
        
        lines = [f"• **{m.name}**" for m in inactive[:15]]
        embed.add_field(name=f"Pendentes ({len(inactive)})", value="\n".join(lines), inline=False)
        
        if await self._send_planner_embed(embed):
            self.posted_inactivity_alerts.add(alert_id)

    # ==================== COMANDOS ====================

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
                s = res.get('strategy_summary', {})
                await ctx.send(f"✅ Plano IA regenerado!\n🧠 Estratégia: **{s.get('primary_strategy')}**")
                info = await self._get_current_cwl_war_info()
                if info: await self._post_daily_plan_if_needed(info, res)
        except Exception as e: logger.error(e); await ctx.send(f"❌ Erro: {e}")

    @commands.command(name='estrategia')
    @commands.has_permissions(administrator=True)
    async def set_strategy_command(self, ctx: commands.Context, estrategia: str):
        s_map = {"agressivo": RotationStrategy.AGGRESSIVE, "balanceado": RotationStrategy.BALANCED, "justo": RotationStrategy.FAIR, "auto": None}
        s_lower = estrategia.lower()
        if s_lower not in s_map: return await ctx.send("❌ Opções: auto, agressivo, balanceado, justo")
        
        if s_lower == "auto":
            self.config["auto_adjust_strategy"] = True
            await ctx.send("✅ Estratégia: **Automática**")
        else:
            self.config["auto_adjust_strategy"] = False
            await ctx.send(f"✅ Estratégia: **{s_map[s_lower].name}**")
        self.posted_daily_plans.clear()
        await self.generate_rotation_plan()

    @commands.command(name='statusplano')
    async def plan_status_command(self, ctx: commands.Context):
        info = await self._get_current_cwl_war_info()
        if not info: return await ctx.send("CWL inativa.")
        plan = await self.generate_rotation_plan()
        embed = discord.Embed(title="📊 Status CWL", color=discord.Color.blue())
        embed.add_field(name="Dia", value=str(info['day_number']))
        if 'error' not in plan:
            s = plan.get('strategy_summary', {})
            embed.add_field(name="Estratégia", value=s.get('primary_strategy', 'N/A'))
            if plan.get('warning'): embed.add_field(name="Avisos", value=plan['warning'], inline=False)
        await ctx.send(embed=embed)
        
    @commands.command(name='resetarplano')
    @commands.has_permissions(administrator=True)
    async def reset_plan_command(self, ctx):
        await ctx.message.add_reaction("🧹")
        try:
            info = await self._get_current_cwl_war_info()
            if not info: return await ctx.send("Sem CWL ativa.")
            await self.cwl_plan_collection.delete_one({"_id": info['season']})
            self.posted_daily_plans.clear()
            await ctx.send("✅ Plano deletado. Gerando novo...")
            await self.generate_rotation_plan()
        except Exception as e: await ctx.send(f"Erro: {e}")

async def setup(bot: commands.Bot):
    if bot.cwl_planner_channel_id and bot.db is not None:
        await bot.add_cog(CwlPlannerCog(bot))
