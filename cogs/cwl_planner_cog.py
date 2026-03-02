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
import asyncio
from abc import ABC, abstractmethod

logger = logging.getLogger("cwl_planner_cog")

# ==================== FUNÇÕES AUXILIARES ====================

def sanitize_for_mongo(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: sanitize_for_mongo(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_mongo(v) for v in data]
    elif isinstance(data, Enum):
        return data.value if isinstance(data.value, (str, int, float, bool)) else data.name
    elif hasattr(data, "to_dict"):
        return sanitize_for_mongo(data.to_dict())
    else:
        return data

def normalize_tag(tag: str) -> str:
    if not tag: return ""
    clean = tag.strip().upper()
    return clean if clean.startswith("#") else f"#{clean}"

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
        return (self.attack_success_rate * 0.35 + (self.average_stars / 3.0) * 0.25 + self.reliability_score * 0.25 + self.versatility * 0.15)

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
            try: self.status = PlayerStatus(self.status)
            except ValueError: self.status = PlayerStatus.ACTIVE
    
    @property
    def effective_strength(self) -> float:
        base = self.town_hall * 10
        mod = self.metrics.overall_score()
        fatigue = min(0.15, self.consecutive_days_played * 0.03)
        rest = min(0.1, self.consecutive_days_rested * 0.02)
        return base * (1 + mod - fatigue + rest)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.tag,
            "name": self.name,
            "town_hall": self.town_hall,
            "days_played": self.days_played,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "metrics": asdict(self.metrics),
            "consecutive_days_played": self.consecutive_days_played,
            "consecutive_days_rested": self.consecutive_days_rested,
            "forced_inclusion": self.forced_inclusion,
            "forced_exclusion": self.forced_exclusion,
            "notes": self.notes
        }

@dataclass
class OpponentAnalysis:
    clan_tag: str
    clan_name: str
    estimated_strength: float
    th_distribution: Dict[int, int]
    threat_level: str
    recommended_strategy: RotationStrategy
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['recommended_strategy'] = self.recommended_strategy.name
        return d

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
            "strategy_used": self.strategy_used.name if isinstance(self.strategy_used, Enum) else self.strategy_used,
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
    promotion_zone: bool = False
    relegation_zone: bool = False
    
    @property
    def context(self) -> WarContext:
        if self.promotion_zone: return WarContext.COMPETITIVE
        if self.relegation_zone: return WarContext.LOSING
        if self.current_position <= 2: return WarContext.WINNING
        if self.current_position >= self.total_clans - 1: return WarContext.LOSING
        return WarContext.COMFORTABLE

# ==================== ENGINE DE ROTAÇÃO ====================

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
    def evaluate(self, p, ctx) -> float:
        ideal = (ctx["team_size"] / ctx["total_players"]) * (ctx["current_day"] - 1)
        return max(-1.0, min(1.0, (ideal - p.days_played) / 3))
    @property
    def weight(self): return 0.25
    @property
    def name(self): return "Fairness"

class StrengthFactor(DecisionFactor):
    def evaluate(self, p, ctx) -> float:
        return max(-1.0, min(1.0, (p.effective_strength / (ctx["max_th"] * 15) - 0.5) * 2))
    @property
    def weight(self): return 0.30
    @property
    def name(self): return "Strength"

class FatigueFactor(DecisionFactor):
    def evaluate(self, p, ctx) -> float:
        if p.consecutive_days_played >= 4: return -0.8
        if p.consecutive_days_played >= 3: return -0.4
        if p.consecutive_days_rested >= 2: return 0.6
        return 0.0
    @property
    def weight(self): return 0.15
    @property
    def name(self): return "Fatigue"

class ReliabilityFactor(DecisionFactor):
    def evaluate(self, p, ctx) -> float:
        return (p.metrics.reliability_score - 0.5) * 2
    @property
    def weight(self): return 0.20
    @property
    def name(self): return "Reliability"

class UrgencyFactor(DecisionFactor):
    def evaluate(self, p, ctx) -> float:
        needed = ctx["min_games_target"] - p.days_played
        if needed <= 0: return -0.3
        if needed >= ctx["days_remaining"]: return 1.0
        return needed / max(1, ctx["days_remaining"])
    @property
    def weight(self): return 0.10
    @property
    def name(self): return "Urgency"


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
    
    def calc_score(self, p: CWLPlayer, ctx: Dict, strat: RotationStrategy) -> Tuple[float, Dict]:
        weights = self._adjust_weights_for_strategy(strat)
        breakdown = {}
        total = 0.0
        for f in self.decision_factors:
            score = f.evaluate(p, ctx)
            if p.status == PlayerStatus.PRIORITY and f.name == "Fairness":
                score = 1.0 
            weighted = score * weights.get(f.name, f.weight)
            breakdown[f.name] = {"raw": score, "weight": weights.get(f.name), "weighted": weighted}
            total += weighted
            
        if p.status == PlayerStatus.PRIORITY:
            total += 1000.0
            
        if p.forced_inclusion: total += 10.0
        if p.forced_exclusion: total -= 10.0
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
    
    def calculate_rotation(self, roster: List[CWLPlayer], active_bench: List[CWLPlayer], backup_bench: List[CWLPlayer], current_day: int, strategy: RotationStrategy) -> Tuple[List[CWLPlayer], List[Dict[str, Any]], List[str]]:
        warnings = []
        remaining = self.total_days - current_day + 1
        available = [p for p in roster + active_bench if not p.forced_exclusion]
        all_p = available + backup_bench
        ctx = {
            "total_days": self.total_days, "current_day": current_day, "days_remaining": remaining,
            "total_players": len(all_p), "team_size": self.team_size,
            "max_th": max((p.town_hall for p in all_p), default=17), "min_games_target": max(1, int(self.total_days * 0.4))
        }
        
        scores = []
        for p in available:
            s, bd = self.calc_score(p, ctx, strategy)
            scores.append((p, s))
        scores.sort(key=lambda x: x[1], reverse=True)
        
        new_roster = [x[0] for x in scores[:self.team_size]]
        new_bench = [x[0] for x in scores[self.team_size:]]
        
        th_counts = defaultdict(int)
        for p in new_roster: th_counts[p.town_hall] += 1
        max_th = max(th_counts.keys()) if th_counts else 17
        high_th = sum(v for k, v in th_counts.items() if k >= max_th - 1)
        
        if high_th < min(5, self.team_size // 3):
            warnings.append(f"⚠️ Poucos CVs altos ({high_th}) no roster")
            high_on_bench = sorted([p for p in new_bench if p.town_hall >= max_th - 1], key=lambda x: x.days_played)
            low_in_roster = sorted([p for p in new_roster if p.town_hall < max_th - 1 and p.status != PlayerStatus.PRIORITY and not p.forced_inclusion], key=lambda p: p.town_hall)
            
            swaps = min(len(high_on_bench), len(low_in_roster), min(5, self.team_size // 3) - high_th)
            for i in range(swaps):
                p_out = low_in_roster[i]
                p_in = high_on_bench[i]
                if p_out in new_roster and p_in in new_bench:
                    new_roster.remove(p_out)
                    new_roster.append(p_in)
                    new_bench.remove(p_in)
                    new_bench.append(p_out)
        
        old_tags = {p.tag for p in roster}
        new_tags = {p.tag for p in new_roster}
        
        players_out = [p for p in roster if p.tag not in new_tags]
        players_in = [p for p in new_roster if p.tag not in old_tags]
        
        subs = []
        for po, pi in zip(players_out, players_in):
            subs.append({"out": po.to_dict(), "in": pi.to_dict(), "reason": "Rotação Automática (IA)", "score_diff": 0})
            
        if len(new_roster) < self.team_size:
            deficit = self.team_size - len(new_roster)
            warnings.append(f"🚨 CRÍTICO: Faltam {deficit} jogadores!")
            needed = min(deficit, len(backup_bench))
            pulls = sorted(backup_bench, key=lambda p: -p.town_hall)[:needed]
            new_roster.extend(pulls)
            for p in pulls: subs.append({"out": None, "in": p.to_dict(), "reason": "EMERGÊNCIA (Backup)", "emergency": True})
            
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

class OpponentAnalyzer:
    def __init__(self, api_client): self.api = api_client
    async def analyze(self, tag, name, war=None) -> OpponentAnalysis:
        dist = defaultdict(int); strength = 0.0
        try:
            clan = war.opponent if war and war.clan.tag != tag else (war.clan if war else await self.api.get_clan(tag))
            for m in clan.members: dist[m.town_hall] += 1; strength += m.town_hall * 10
        except coc.NotFound:
            logger.warning(f"Clã oponente {tag} não encontrado para análise.")
        except coc.Maintenance:
            logger.warning(f"API em manutenção ao tentar analisar clã oponente {tag}.")
        except Exception as e:
            logger.error(f"Erro inesperado na análise do oponente {tag}: {e}")
        
        max_th = max(dist.keys()) if dist else 15
        high = sum(v for k, v in dist.items() if k >= max_th - 1)
        threat = "extreme" if high >= 10 and max_th >= 16 else "high" if high >= 7 else "medium" if high >= 4 else "low"
        strat = {"extreme": RotationStrategy.AGGRESSIVE, "high": RotationStrategy.AGGRESSIVE, "medium": RotationStrategy.BALANCED, "low": RotationStrategy.FAIR}[threat]
        return OpponentAnalysis(tag, name, strength, dict(dist), threat, strat)

# ==================== COG PRINCIPAL ====================

class CwlPlannerCog(commands.Cog, name="CWLPlanner"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.cwl_plan_collection = self.db.cwl_plan if self.db is not None else None
        self.cwl_state_collection = self.db.cwl_state if self.db is not None else None
        self.rotation_engine: Optional[IntelligentRotationEngine] = None
        self.opponent_analyzer: Optional[OpponentAnalyzer] = None
        self.posted_daily_plans: Set[str] = set()
        self.season_state: Optional[SeasonState] = None
        self.config = {"min_participation_percent": 0.3, "auto_adjust_strategy": True}
        self.is_generating_plan = False  
        print(">>> [CWLPlanner] Plugin inicializado!")

    async def cog_load(self):
        await self._load_state()
        self.monitor_task.start()

    async def cog_unload(self):
        await self._save_state()
        self.monitor_task.cancel()

    async def _init_logic(self, size):
        self.rotation_engine = IntelligentRotationEngine(size)
        if self.bot.api_client:
            self.opponent_analyzer = OpponentAnalyzer(self.bot.api_client)

    async def _load_state(self):
        if self.cwl_state_collection is None: return
        try:
            s = await self.cwl_state_collection.find_one({"_id": "cog_state"})
            if s:
                self.posted_daily_plans = set(s.get("posted_daily_plans", []))
                if s.get("season_state"):
                    self.season_state = SeasonState(**s.get("season_state"))
        except Exception as e:
            logger.error(f"Erro ao carregar estado persistente: {e}")

    async def _save_state(self):
        if self.cwl_state_collection is None: return
        try:
            state_data = {
                "posted_daily_plans": list(self.posted_daily_plans),
                "updated_at": datetime.datetime.now(pytz.utc)
            }
            if self.season_state: state_data["season_state"] = asdict(self.season_state)
            await self.cwl_state_collection.update_one({"_id": "cog_state"}, {"$set": sanitize_for_mongo(state_data)}, upsert=True)
        except Exception as e:
            logger.error(f"Erro ao salvar estado persistente: {e}")

    async def _fetch_pool(self, active_war: Optional[coc.ClanWar], team_size: int = 15) -> Tuple[List[CWLPlayer], Set[str]]:
        if not self.bot.api_client: return [], set()
        try:
            my_tag = normalize_tag(self.bot.clan_tag)
            group, clan = await asyncio.gather(self.bot.api_client.get_league_group(my_tag), self.bot.api_client.get_clan(my_tag))
            if not group: return [], set()
            
            curr_tags = {m.tag for m in clan.members}
            war_tags = set()
            if active_war:
                side = active_war.clan if normalize_tag(active_war.clan.tag) == my_tag else active_war.opponent
                war_tags = {m.tag for m in side.members}
            
            cwl_roster = next((c for c in group.clans if normalize_tag(c.tag) == my_tag), None)
            if not cwl_roster: 
                logger.warning(f"Roster CWL não encontrado para {my_tag}")
                cwl_members = clan.members
            else:
                cwl_members = cwl_roster.members

            valid_cwl_tags = {m.tag for m in cwl_members}
            all_relevant_tags = valid_cwl_tags.union(war_tags).union(curr_tags)

            db_cog = self.bot.get_cog("Banco de Dados")
            notes = await db_cog.load_player_notes_from_db() if db_cog else {}
            
            players = []
            member_map = {m.tag: m for m in clan.members}

            for tag in all_relevant_tags:
                m = member_map.get(tag)
                if not m: m = next((x for x in cwl_members if x.tag == tag), None)
                
                # --- CIRURGIA DE BLINDAGEM ---
                # A IA não apaga o jogador. Se ele não está na liga, marca como "Não Inscrito"
                # Se não está no clã, marca como "Saiu". Ambos recebem "forced_exclusion" para não sujar o plano
                if m:
                    note = notes.get(m.tag, {})
                    try: 
                        status = PlayerStatus(note.get('cwl_status', 'active'))
                    except ValueError: 
                        status = PlayerStatus.ACTIVE
                        
                    forced_inclusion = note.get('forced_in', False)
                    forced_exclusion = note.get('forced_out', False)
                    display_name = m.name

                    is_in_league = m.tag in valid_cwl_tags
                    is_in_clan = m.tag in curr_tags

                    if not is_in_league:
                        status = PlayerStatus.UNAVAILABLE
                        forced_exclusion = True
                        forced_inclusion = False
                        display_name = f"{m.name} 🚫 (Não Inscrito)"
                    elif not is_in_clan:
                        status = PlayerStatus.UNAVAILABLE
                        forced_exclusion = True
                        forced_inclusion = False
                        display_name = f"{m.name} 🛑 (Saiu)"

                    players.append(CWLPlayer(
                        tag=m.tag, name=display_name, town_hall=m.town_hall, status=status,
                        notes=note.get('notes', ''), forced_inclusion=forced_inclusion, forced_exclusion=forced_exclusion
                    ))
            
            if len(players) < team_size:
                for i in range(team_size - len(players)):
                    players.append(CWLPlayer(tag=f"#UNK{i}", name=f"Vaga {i+1}", town_hall=1, status=PlayerStatus.ACTIVE))

            return players, war_tags
        except Exception as e:
            logger.error(f"Erro fetch pool: {e}", exc_info=True)
            return [], set()

    async def _build_state(self, players, war, day, plan, my_tag):
        hist = defaultdict(lambda: {"days": 0, "cons": 0, "last": 0})
        if plan and 'schedule' in plan:
            for d in plan['schedule']:
                if d.get('day', 0) < day:
                    for p in d.get('active_roster', []):
                        tag = p.get('tag') or p.get('player', {}).get('tag')
                        if tag:
                            hist[tag]["days"] += 1
                            hist[tag]["cons"] = hist[tag]["cons"] + 1 if hist[tag]["last"] == d['day'] - 1 else 1
                            hist[tag]["last"] = d['day']
        
        war_tags = set()
        if war:
            side = war.clan if normalize_tag(war.clan.tag) == my_tag else war.opponent
            war_tags = {m.tag for m in side.members}

        roster, active, backup = [], [], []
        
        for p in players:
            h = hist[p.tag]
            p.days_played = h["days"]
            if p.tag in war_tags:
                p.days_played = max(p.days_played, day)
                p.consecutive_days_rested = 0
                roster.append(p)
            else:
                p.consecutive_days_rested = day - h["last"] if h["last"] > 0 else day - 1
                if p.status in [PlayerStatus.ACTIVE, PlayerStatus.PRIORITY]: active.append(p)
                else: backup.append(p)
        return roster, active, backup

    # ==================== CONTROLE DE PERSISTÊNCIA ====================

    async def generate_rotation_plan(self, force_recalculate: bool = False) -> Dict[str, Any]:
        return await self.generate_plan(force_recalculate=force_recalculate)

    async def generate_plan(self, force_recalculate: bool = False) -> Dict:
        if self.cwl_plan_collection is None: return {"error": "DB off"}
        if not self.bot.api_client: return {"error": "API off"}
        
        try:
            my_tag = normalize_tag(self.bot.clan_tag)
            
            try:
                group = await self.bot.api_client.get_league_group(my_tag)
            except coc.NotFound:
                return {"error": "CWL off", "status": "NotInCwl"}
                
            if not group or group.state == "notInWar": return {"error": "CWL off", "status": "NotInCwl"}
            
            existing = await self.cwl_plan_collection.find_one({"_id": group.season})
            
            if existing and not force_recalculate:
                logger.info("Recuperando plano de Rotação CWL salvo no Banco de Dados...")
                return sanitize_for_mongo(existing)

            logger.info("Iniciando Cérebro de Rotação (Gerando novo plano)...")
            fallback_team_size = existing.get("team_size", 15) if existing else 15

            tasks = [self.bot.api_client.get_league_war(t) for r in group.rounds for t in r if t != '#0']
            war_tags_list = [t for r in group.rounds for t in r if t != '#0']
            war_round_map = {t: i+1 for i, r in enumerate(group.rounds) for t in r if t != '#0'}
            
            results = await asyncio.gather(*tasks, return_exceptions=True)

            war = None; day = 0
            states = {'inWar': [], 'preparation': [], 'warEnded': []}
            any_clan_war = None

            for w, w_tag in zip(results, war_tags_list):
                if isinstance(w, Exception) or not w: continue
                
                w_clan = normalize_tag(w.clan.tag); w_opp = normalize_tag(w.opponent.tag)
                if w_clan == my_tag or w_opp == my_tag:
                    any_clan_war = w
                    st = w.state.value if hasattr(w.state, 'value') else str(w.state)
                    op = w.opponent if w_clan == my_tag else w.clan
                    idx = war_round_map.get(w_tag, 0)
                    if st in states: states[st].append((w, idx, w_tag, op))

            if states['inWar']: war, day, tag, opp = states['inWar'][0]
            elif states['preparation']: 
                states['preparation'].sort(key=lambda x: x[1])
                war, day, tag, opp = states['preparation'][0]
            elif states['warEnded']: 
                latest = max(states['warEnded'], key=lambda x: x[1])
                war, day, tag, opp = latest; day = min(day + 1, 8)
            
            used_fallback = False
            if not war:
                if any_clan_war:
                    war = any_clan_war; day = existing.get("current_day", 1) if existing else 1
                    used_fallback = True
                elif existing:
                    day = existing.get("current_day", 1); fallback_team_size = existing.get("team_size", 15)
                else:
                    day = 1
                    used_fallback = True

            team_size = war.team_size if war else fallback_team_size

            if day >= 8 and not used_fallback: 
                if existing:
                    existing["finished"] = True; existing["current_day"] = 8
                    return sanitize_for_mongo(existing)
                return {"finished": True, "error": "CWL Finalizada."}

            players, _ = await self._fetch_pool(war, team_size)
            if not players: return {"error": "Roster vazio. Ninguém cadastrado."}
            
            await self._init_logic(team_size)
            roster, active, backup = await self._build_state(players, war, day, existing, my_tag)
            
            if not war or used_fallback:
                if len(roster) < team_size:
                    needed = team_size - len(roster)
                    roster.extend([p for p in active if p not in roster][:needed])
            
            if len(roster) < team_size:
                for i in range(team_size - len(roster)):
                    roster.append(CWLPlayer(tag=f"#UNK_F{i}", name="Vaga", town_hall=1))

            strat = RotationStrategy.BALANCED
            if self.config['auto_adjust_strategy'] and self.season_state:
                strat = self.rotation_engine.determine_optimal_strategy(self.season_state, day, None)
            
            schedule = []
            if existing and 'schedule' in existing:
                schedule = [d for d in existing['schedule'] if d['day'] < day]

            cont = self.rotation_engine.generate_contingency_plan(roster, active+backup, day)
            curr_plan = DayPlan(day, roster.copy(), [], active, backup, strat, None, 1.0, [], cont)
            schedule.append(sanitize_for_mongo(curr_plan.to_dict()))
            
            curr_r = roster.copy(); curr_a = active.copy(); curr_b = backup.copy()
            for d in range(day+1, 8):
                new_r, subs, warns = self.rotation_engine.calculate_rotation(curr_r, curr_a, curr_b, d, strat)
                for p in new_r: p.days_played += 1
                curr_r = new_r
                schedule.append(sanitize_for_mongo(DayPlan(d, new_r, subs, curr_a, curr_b, strat, None, 0.8, warns).to_dict()))
            
            # EMPACOTAMENTO DOS DADOS EXTRAS PARA O FRONTEND NÃO CRASHAR
            clans_data = []
            if group and hasattr(group, 'clans'):
                for c in group.clans:
                    clans_data.append({
                        "name": c.name, 
                        "tag": c.tag, 
                        "badge_url": c.badge.url if hasattr(c, 'badge') and c.badge else ""
                    })

            rounds_list = []
            if group and hasattr(group, 'rounds'):
                for i in range(1, len(group.rounds) + 1):
                    if i < day:
                        rounds_list.append("warEnded")
                    elif i == day:
                        prep_states = states.get('preparation', [])
                        is_prep = any(idx == day for w, idx, t, op in prep_states)
                        rounds_list.append("preparation" if is_prep else "inWar")
                    else:
                        rounds_list.append("unstarted")

            data = {
                "schedule": schedule,
                "participation_score": [sanitize_for_mongo(p.to_dict()) for p in players],
                "warning": "Modo Fallback" if used_fallback else "",
                "current_day": day, "team_size": team_size, "season": group.season, "status": "InCwl",
                "state": group.state, "clans": clans_data, "rounds": rounds_list
            }
            
            await self.cwl_plan_collection.update_one({"_id": group.season}, {"$set": sanitize_for_mongo(data)}, upsert=True)
            return data

        except Exception as e:
            logger.error(f"Generate error: {e}", exc_info=True)
            return {"error": f"Erro interno: {str(e)}"}

    @tasks.loop(minutes=15)
    async def monitor_task(self):
        if not self.bot.is_ready(): return
        if getattr(self, "is_generating_plan", False): return
            
        self.is_generating_plan = True
        try:
            await self.generate_plan(force_recalculate=False)
        finally:
            self.is_generating_plan = False

    @monitor_task.before_loop
    async def before_monitor_task(self):
        await self.bot.wait_until_ready()

    @commands.command(name='resetarplano')
    @commands.has_permissions(administrator=True)
    async def reset_plan_command(self, ctx):
        await self.cwl_plan_collection.delete_many({})
        self.posted_daily_plans.clear()
        await ctx.send("✅ Banco de dados resetado. Recalculando do zero...")
        await self.generate_plan(force_recalculate=True)

    @commands.command(name='cwl_status_debug')
    async def cwl_debug(self, ctx):
        await ctx.send("✅ O plugin CWLPlanner está carregado e funcionando com persistência DB!")

async def setup(bot: commands.Bot):
    await bot.add_cog(CwlPlannerCog(bot))
