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
import asyncio  # <--- ADICIONADO: Essencial para _fetch_pool
from abc import ABC, abstractmethod

logger = logging.getLogger("cwl_planner_cog")

# ==================== FUNÇÕES AUXILIARES ====================

def sanitize_for_mongo(data: Any) -> Any:
    """
    Converte recursivamente objetos não suportados pelo MongoDB (como Enums)
    para tipos suportados (strings, ints, etc).
    """
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
    promotion_zone: bool = False; relegation_zone: bool = False
    
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
            weighted = score * weights.get(f.name, f.weight)
            breakdown[f.name] = {"raw": score, "weight": weights.get(f.name), "weighted": weighted}
            total += weighted
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
        
        # Garante min CVs altos
        th_counts = defaultdict(int)
        for p in new_roster: th_counts[p.town_hall] += 1
        max_th = max(th_counts.keys()) if th_counts else 17
        high_th = sum(v for k, v in th_counts.items() if k >= max_th - 1)
        
        if high_th < min(5, self.team_size // 3):
            warnings.append(f"⚠️ Poucos CVs altos ({high_th}) no roster")
            high_on_bench = sorted([p for p in new_bench if p.town_hall >= max_th - 1], key=lambda x: x.days_played)
            low_in_roster = sorted([p for p in new_roster if p.town_hall < max_th - 1], key=lambda p: p.town_hall)
            swaps = min(len(high_on_bench), len(low_in_roster), min(5, self.team_size // 3) - high_th)
            for i in range(swaps):
                if low_in_roster[i] in new_roster: new_roster.remove(low_in_roster[i])
                new_roster.append(high_on_bench[i])
                if high_on_bench[i] in new_bench: new_bench.remove(high_on_bench[i])
                new_bench.append(low_in_roster[i])
        
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
        except: pass
        
        max_th = max(dist.keys()) if dist else 15
        high = sum(v for k, v in dist.items() if k >= max_th - 1)
        threat = "extreme" if high >= 10 and max_th >= 16 else "high" if high >= 7 else "medium" if high >= 4 else "low"
        strat = {"extreme": RotationStrategy.AGGRESSIVE, "high": RotationStrategy.AGGRESSIVE, "medium": RotationStrategy.BALANCED, "low": RotationStrategy.FAIR}[threat]
        return OpponentAnalysis(tag, name, strength, dict(dist), threat, strat)

# ==================== COG PRINCIPAL ====================

class CwlPlannerCog(commands.Cog, name="Planeador de CWL"):
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

    async def _fetch_pool(self, active_war: Optional[coc.ClanWar] = None) -> Tuple[List[CWLPlayer], Set[str]]:
        if not self.bot.api_client: return [], set()
        try:
            group, clan = await asyncio.gather(self.bot.api_client.get_league_group(self.bot.clan_tag), self.bot.api_client.get_clan(self.bot.clan_tag))
            if not group: return [], set()
            
            curr_tags = {m.tag for m in clan.members}
            war_tags = set()
            if active_war:
                side = active_war.clan if active_war.clan.tag == self.bot.clan_tag else active_war.opponent
                war_tags = {m.tag for m in side.members}
            
            cwl_roster = next((c for c in group.clans if c.tag == self.bot.clan_tag), None)
            if not cwl_roster: return [], curr_tags

            db_cog = self.bot.get_cog("Banco de Dados")
            notes = await db_cog.load_player_notes_from_db() if db_cog else {}
            
            players = []
            all_relevant_tags = curr_tags.union(war_tags)
            
            for m in cwl_roster.members:
                if m.tag in all_relevant_tags:
                    note = notes.get(m.tag, {})
                    try: status = PlayerStatus(note.get('cwl_status', 'active'))
                    except: status = PlayerStatus.ACTIVE
                    
                    players.append(CWLPlayer(
                        tag=m.tag, name=m.name, town_hall=m.town_hall, status=status,
                        notes=note.get('notes', ''), forced_inclusion=note.get('forced_in', False), forced_exclusion=note.get('forced_out', False)
                    ))
            
            if active_war and len(players) < active_war.team_size:
                player_tags = {p.tag for p in players}
                for tag in war_tags:
                    if tag not in player_tags:
                        players.append(CWLPlayer(tag=tag, name="Unknown/Left", town_hall=1, status=PlayerStatus.ACTIVE))
            
            return players, curr_tags
        except Exception as e:
            logger.error(f"Erro fetch pool: {e}")
            return [], set()

    async def _build_state(self, players, war, day, plan):
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
        
        war_tags = {m.tag for m in (war.clan if war.clan.tag == self.bot.clan_tag else war.opponent).members}
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

    # ALIAS NECESSÁRIO PARA O CLASH.PY
    async def generate_rotation_plan(self) -> Dict[str, Any]:
        return await self.generate_plan()

    async def generate_plan(self) -> Dict:
        if self.cwl_plan_collection is None: return {"error": "DB off"}
        if not self.bot.api_client: return {"error": "API off"}
        
        try:
            group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not group or group.state == "notInWar": return {"error": "CWL off"}
            
            war, day, tag, opp = None, 0, None, None
            states = {'inWar': [], 'preparation': [], 'warEnded': []}
            for i, r in enumerate(group.rounds):
                for t in r:
                    if t == '#0': continue
                    try:
                        w = await self.bot.api_client.get_league_war(t)
                        if w.clan.tag == self.bot.clan_tag or w.opponent.tag == self.bot.clan_tag:
                            st = w.state if isinstance(w.state, str) else w.state.value
                            op = w.opponent if w.clan.tag == self.bot.clan_tag else w.clan
                            states.get(st, []).append((w, i+1, t, op))
                    except: pass
            
            if states['inWar']: war, day, tag, opp = states['inWar'][0]
            elif states['preparation']: war, day, tag, opp = states['preparation'][0]
            elif states['warEnded']: 
                war, day, tag, opp = max(states['warEnded'], key=lambda x: x[1])
                day = min(day + 1, 8)
            
            if not war: return {"error": "Sem guerra"}

            # === CORREÇÃO CRÍTICA AQUI: Retorna dados completos no fim da temporada ===
            if day >= 8: 
                saved_plan = await self.cwl_plan_collection.find_one({"_id": group.season})
                if saved_plan:
                    # Retorna objeto completo para o frontend não travar
                    return {
                        "finished": True, 
                        "schedule": saved_plan.get('schedule', []),
                        "participation_score": saved_plan.get('participation_score', []),
                        "current_day": 8,
                        "team_size": saved_plan.get('team_size', 15),
                        "warning": "Temporada finalizada."
                    }
                return {"finished": True, "error": "CWL finalizada, plano não encontrado."}
            # =========================================================================

            players, _ = await self._fetch_pool(war)
            if not players: return {"error": "Sem players"}
            
            await self._init_logic(war.team_size)
            existing = await self.cwl_plan_collection.find_one({"_id": group.season})
            
            roster, active, backup = await self._build_state(players, war, day, existing)
            
            if len(roster) < war.team_size:
                needed = war.team_size - len(roster)
                for _ in range(needed):
                    roster.append(CWLPlayer(tag="#UNKNOWN", name="Desconhecido", town_hall=1, status=PlayerStatus.ACTIVE))

            strat = self.rotation_engine.determine_optimal_strategy(
                self.season_state or SeasonState(), day, None
            ) if self.config['auto_adjust_strategy'] else RotationStrategy.BALANCED
            
            schedule = []
            cont = self.rotation_engine.generate_contingency_plan(roster, active+backup, day)
            schedule.append(sanitize_for_mongo(DayPlan(day, roster.copy(), [], active, backup, strat, None, 1.0, [], cont).to_dict()))
            
            curr_r, curr_a, curr_b = roster.copy(), active.copy(), backup.copy()
            for d in range(day+1, 8):
                new_r, subs, warns = self.rotation_engine.calculate_rotation(curr_r, curr_a, curr_b, d, strat)
                for p in new_r: p.days_played += 1
                curr_r = new_r
                schedule.append(sanitize_for_mongo(DayPlan(d, new_r, subs, curr_a, curr_b, strat, None, 0.8, warns).to_dict()))
            
            data = {
                "schedule": schedule,
                "participation_score": [sanitize_for_mongo(p.to_dict()) for p in players],
                "warning": "",
                "current_day": day,
                "team_size": war.team_size
            }
            
            await self.cwl_plan_collection.update_one({"_id": group.season}, {"$set": data}, upsert=True)
            return data

        except Exception as e:
            logger.error(f"Generate error: {e}", exc_info=True)
            return {"error": str(e)}

    # --- TASKS ---
    @tasks.loop(minutes=15)
    async def monitor_task(self):
        if not self.bot.is_ready(): return
        await self.generate_plan()

    @monitor_task.before_loop
    async def before_monitor_task(self):
        await self.bot.wait_until_ready()

    # --- COMANDOS ---
    @commands.command(name='resetarplano')
    @commands.has_permissions(administrator=True)
    async def reset_plan_command(self, ctx):
        await ctx.message.add_reaction("🧹")
        if not self.bot.api_client: return await ctx.send("API off")
        try:
            group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not group: return await ctx.send("Sem CWL")
            await self.cwl_plan_collection.delete_one({"_id": group.season})
            self.posted_daily_plans.clear()
            await ctx.send("✅ Plano deletado. Gerando novo...")
            res = await self.generate_plan()
            if "error" in res: await ctx.send(f"❌ Erro: {res['error']}")
            else: await ctx.send("✅ Sucesso!")
        except Exception as e: await ctx.send(f"Erro: {e}")

    @commands.command(name='forcarplano')
    @commands.has_permissions(administrator=True)
    async def force_plan(self, ctx):
        await ctx.message.add_reaction("🔄")
        res = await self.generate_plan()
        if "error" in res: await ctx.send(f"Erro: {res['error']}")
        else: await ctx.send("✅ Plano atualizado.")

    @commands.command(name='statusplano')
    async def status_plan(self, ctx):
        res = await self.generate_plan()
        if "error" in res: await ctx.send(res['error'])
        else: await ctx.send(f"Dia {res.get('current_day', '?')} | Tamanho: {res.get('team_size', '?')}")

async def setup(bot: commands.Bot):
    if bot.cwl_planner_channel_id and bot.db is not None:
        await bot.add_cog(CwlPlannerCog(bot))
