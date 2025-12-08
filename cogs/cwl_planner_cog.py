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
    
    @property
    def participation_urgency(self) -> float:
        if self.forced_inclusion: return 100.0
        if self.forced_exclusion: return -100.0
        return (self.consecutive_days_rested * 2.0) - (max(0, self.consecutive_days_played - 3) * 1.5)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CWLPlayer":
        if "player" in data: data = data["player"] # Compatibilidade backward
        
        metrics_data = data.get("metrics", {})
        metrics = PlayerMetrics(**metrics_data) if metrics_data else PlayerMetrics()
        
        return cls(
            tag=data.get("tag", ""), name=data.get("name", "Unknown"), town_hall=data.get("town_hall", 1),
            days_played=data.get("days_played", 0), status=PlayerStatus(data.get("status", "active")),
            metrics=metrics, consecutive_days_played=data.get("consecutive_days_played", 0),
            consecutive_days_rested=data.get("consecutive_days_rested", 0),
            forced_inclusion=data.get("forced_inclusion", False), forced_exclusion=data.get("forced_exclusion", False),
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
    def to_dict(self) -> Dict[str, Any]: return asdict(self)

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
            "strategy_used": self.strategy_used.name,
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
    wins: int = 0; losses: int = 0; draws: int = 0
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
    def evaluate(self, p, ctx) -> float: return (p.metrics.reliability_score - 0.5) * 2
    @property
    def weight(self): return 0.20
    @property
    def name(self): return "Reliability"

class UrgencyFactor(DecisionFactor):
    def evaluate(self, p, ctx) -> float:
        needed = ctx["min_games_target"] - p.days_played
        if needed <= 0: return -0.3
        if needed >= ctx["days_remaining"]: return 1.0
        return needed / ctx["days_remaining"]
    @property
    def weight(self): return 0.10
    @property
    def name(self): return "Urgency"

class IntelligentRotationEngine:
    def __init__(self, team_size: int, total_days: int = 7):
        self.team_size = team_size; self.total_days = total_days
        self.factors = [FairnessFactor(), StrengthFactor(), FatigueFactor(), ReliabilityFactor(), UrgencyFactor()]
    
    def _get_weights(self, strategy: RotationStrategy) -> Dict[str, float]:
        w = {f.name: f.weight for f in self.factors}
        if strategy == RotationStrategy.AGGRESSIVE: w.update({"Strength": 0.5, "Fairness": 0.1, "Reliability": 0.25})
        elif strategy == RotationStrategy.FAIR: w.update({"Fairness": 0.45, "Urgency": 0.2, "Strength": 0.15})
        elif strategy == RotationStrategy.SURVIVAL: w.update({"Reliability": 0.4, "Strength": 0.35, "Fatigue": 0.05})
        total = sum(w.values())
        return {k: v/total for k, v in w.items()}
    
    def calc_score(self, p: CWLPlayer, ctx: Dict, strat: RotationStrategy) -> Tuple[float, Dict]:
        w = self._get_weights(strat)
        breakdown = {}
        total = 0.0
        for f in self.factors:
            score = f.evaluate(p, ctx)
            weighted = score * w.get(f.name, f.weight)
            breakdown[f.name] = {"raw": score, "weight": w.get(f.name), "weighted": weighted}
            total += weighted
        if p.forced_inclusion: total += 10.0
        if p.forced_exclusion: total -= 10.0
        return total, breakdown

    def get_strategy(self, state: SeasonState, day: int, opp: Optional[OpponentAnalysis]) -> RotationStrategy:
        rem = self.total_days - day + 1
        if rem <= 2: return RotationStrategy.FAIR
        if state.context == WarContext.LOSING and state.relegation_zone: return RotationStrategy.AGGRESSIVE
        if state.context == WarContext.COMPETITIVE:
            if opp and opp.threat_level in ["high", "extreme"]: return RotationStrategy.AGGRESSIVE
            return RotationStrategy.BALANCED
        if state.context == WarContext.WINNING and rem >= 4: return RotationStrategy.FAIR
        return RotationStrategy.BALANCED

    def calculate_rotation(self, roster, active_bench, backup_bench, day, strategy, season_state=None) -> Tuple[List, List, List]:
        warnings = []
        available = [p for p in roster + active_bench if not p.forced_exclusion]
        all_p = available + backup_bench
        ctx = {
            "total_days": self.total_days, "current_day": day, "days_remaining": self.total_days - day + 1,
            "total_players": len(all_p), "team_size": self.team_size,
            "max_th": max((p.town_hall for p in all_p), default=17), "min_games_target": max(1, int(self.total_days * 0.4))
        }
        
        scores = []
        for p in available:
            s, bd = self.calc_score(p, ctx, strategy)
            scores.append((p, s))
        scores.sort(key=lambda x: x[1], reverse=True)
        
        new_roster = [x[0] for x in scores[:self.team_size]]
        
        # Validação de Roster
        if len(new_roster) < self.team_size:
            missing = self.team_size - len(new_roster)
            warnings.append(f"🚨 CRÍTICO: Faltam {missing} jogadores!")
            needed = min(missing, len(backup_bench))
            pulls = sorted(backup_bench, key=lambda p: -p.town_hall)[:needed]
            new_roster.extend(pulls)
        
        # Substituições
        old_tags = {p.tag for p in roster}
        subs = []
        p_in = [p for p in new_roster if p.tag not in old_tags]
        p_out = [p for p in roster if p.tag not in {x.tag for x in new_roster}]
        
        # Ordena para parear melhor
        p_in.sort(key=lambda p: p.town_hall, reverse=True)
        p_out.sort(key=lambda p: p.town_hall, reverse=True)
        
        for pi, po in zip(p_in, p_out):
            subs.append({"out": po.to_dict(), "in": pi.to_dict(), "reason": "Rotação Estratégica"})
            
        return new_roster, subs, warnings

    def get_contingency(self, roster, bench, day) -> List[Dict]:
        cont = []
        bench_s = sorted(bench, key=lambda p: (-p.town_hall, p.days_played))
        for r in roster:
            subs = [p for p in bench_s if abs(p.town_hall - r.town_hall) <= 1]
            if subs: cont.append({"if_unavailable": r.to_dict(), "replace_with": subs[0].to_dict(), "priority": "high" if r.town_hall >= 15 else "normal"})
        return cont

    def predict_issues(self, schedule, all_players) -> List[Dict]:
        issues = []
        participation = defaultdict(int)
        for d in schedule:
            for p in d.active_roster: participation[p.tag] += 1
        
        min_acc = max(1, int(len(schedule) * 0.3))
        for p in all_players:
            g = participation.get(p.tag, 0)
            if g == 0: issues.append({"player": p.to_dict(), "type": "ZERO", "severity": "critical", "message": f"{p.name} não vai jogar", "suggested_action": "Forçar inclusão"})
            elif g < min_acc: issues.append({"player": p.to_dict(), "type": "LOW", "severity": "warning", "message": f"{p.name} jogará pouco ({g})", "suggested_action": "Rotacionar"})
        return issues

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

# ==================== COG ====================

class CwlPlannerCog(commands.Cog, name="Planeador de CWL"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot; self.db = bot.db
        self.cwl_plan_collection = self.db.cwl_plan if self.db is not None else None
        self.cwl_state_collection = self.db.cwl_state if self.db is not None else None
        self.metrics_collection = self.db.player_metrics if self.db is not None else None
        
        self.engine: Optional[IntelligentRotationEngine] = None
        self.analyzer: Optional[OpponentAnalyzer] = None
        
        self.daily_posted = set(); self.alerts_posted = set()
        self.last_members = set(); self.leavers = set()
        self.season_state = None
        self.config = {"auto_strat": True}

    async def cog_load(self):
        await self._load_state()
        self.monitor_task.start()
        self.metrics_task.start()

    async def cog_unload(self):
        await self._save_state()
        self.monitor_task.cancel()
        self.metrics_task.cancel()

    async def _init_logic(self, size):
        self.engine = IntelligentRotationEngine(size)
        if self.bot.api_client: self.analyzer = OpponentAnalyzer(self.bot.api_client)

    async def _load_state(self):
        if not self.cwl_state_collection: return
        try:
            s = await self.cwl_state_collection.find_one({"_id": "cog_state"})
            if s:
                self.daily_posted = set(s.get("daily", []))
                self.alerts_posted = set(s.get("alerts", []))
                self.leavers = set(s.get("leavers", []))
                if s.get("season"): self.season_state = SeasonState(**s.get("season"))
        except: pass

    async def _save_state(self):
        if not self.cwl_state_collection: return
        try:
            data = {"daily": list(self.daily_posted), "alerts": list(self.alerts_posted), "leavers": list(self.leavers)}
            if self.season_state: data["season"] = asdict(self.season_state)
            await self.cwl_state_collection.update_one({"_id": "cog_state"}, {"$set": data}, upsert=True)
        except: pass

    # --- CORREÇÃO DO ROSTER 14/15 ---
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
            
            # Pega lista oficial da CWL
            cwl_roster = next((c for c in group.clans if c.tag == self.bot.clan_tag), None)
            if not cwl_roster: return [], curr_tags

            db_cog = self.bot.get_cog("Banco de Dados")
            notes = await db_cog.load_player_notes_from_db() if db_cog else {}
            
            players = []
            # Combina quem está no clã, quem está na guerra, e quem está inscrito na CWL
            all_relevant_tags = curr_tags.union(war_tags)
            
            for m in cwl_roster.members:
                # Se estiver no clã ou na guerra, é relevante
                if m.tag in all_relevant_tags:
                    note = notes.get(m.tag, {})
                    try: status = PlayerStatus(note.get('cwl_status', 'active'))
                    except: status = PlayerStatus.ACTIVE
                    
                    players.append(CWLPlayer(
                        tag=m.tag, name=m.name, town_hall=m.town_hall, status=status,
                        notes=note.get('notes', ''), forced_inclusion=note.get('forced_in', False), forced_exclusion=note.get('forced_out', False)
                    ))
            
            # FALLBACK CRÍTICO: Se a guerra tem 15 e achamos menos que 15, cria "Unknowns"
            # Isso impede o crash de "14 jogadores"
            if active_war and len(players) < active_war.team_size:
                missing_count = active_war.team_size - len(players)
                # Verifica se as tags da guerra estão na lista de players
                player_tags = {p.tag for p in players}
                for tag in war_tags:
                    if tag not in player_tags:
                        # Adiciona jogador fantasma para completar o time
                        logger.warning(f"Adicionando jogador fantasma para tag {tag}")
                        players.append(CWLPlayer(
                            tag=tag, name="Unknown/Left", town_hall=1, status=PlayerStatus.ACTIVE
                        ))
            
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

    async def generate_plan(self) -> Dict:
        if not self.cwl_plan_collection: return {"error": "DB off"}
        if not self.bot.api_client: return {"error": "API off"}
        
        try:
            group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not group or group.state == "notInWar": return {"error": "CWL off"}
            
            # Acha guerra ativa
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
            if day >= 8: return {"finished": True, "schedule": (await self.cwl_plan_collection.find_one({"_id": group.season}))['schedule']}

            players, _ = await self._fetch_pool(war)
            if not players: return {"error": "Sem players"}
            
            await self._init_logic(war.team_size)
            existing = await self.cwl_plan_collection.find_one({"_id": group.season})
            
            roster, active, backup = await self._build_state(players, war, day, existing)
            
            # Valida 15/15
            if len(roster) < war.team_size:
                logger.warning(f"Roster incompleto ({len(roster)}/{war.team_size}). Tentando preencher com Unknowns.")
                needed = war.team_size - len(roster)
                for _ in range(needed):
                    roster.append(CWLPlayer(tag="#UNKNOWN", name="Desconhecido", town_hall=1, status=PlayerStatus.ACTIVE))

            strat = self.engine.get_strategy(SeasonState(), day, None) if self.config['auto_strat'] else RotationStrategy.BALANCED
            
            schedule = []
            # Dia atual
            cont = self.engine.get_contingency(roster, active+backup, day)
            schedule.append(DayPlan(day, roster.copy(), [], active, backup, strat, None, 1.0, [], cont).to_dict())
            
            # Futuro
            curr_r, curr_a, curr_b = roster.copy(), active.copy(), backup.copy()
            for d in range(day+1, 8):
                new_r, subs, warns = self.engine.calculate_rotation(curr_r, curr_a, curr_b, d, strat)
                
                # Update counters simplified
                for p in new_r: p.days_played += 1
                
                curr_r = new_r
                schedule.append(DayPlan(d, new_r, subs, curr_a, curr_b, strat, None, 0.8, warns).to_dict())
            
            data = {
                "schedule": schedule,
                "participation_score": [p.to_dict() for p in players],
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

    @tasks.loop(hours=1)
    async def metrics_task(self):
        pass # Simplificado para evitar erros de None

    # --- COMANDOS ---
    @commands.command(name='resetarplano')
    @commands.has_permissions(administrator=True)
    async def reset_plan_command(self, ctx):
        """Reseta TOTALMENTE o plano da CWL atual."""
        await ctx.message.add_reaction("🧹")
        if not self.bot.api_client: return await ctx.send("API off")
        try:
            group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not group: return await ctx.send("Sem CWL")
            
            # DELETA O PLANO DO DB
            await self.cwl_plan_collection.delete_one({"_id": group.season})
            self.posted_daily_plans.clear()
            
            await ctx.send("✅ Plano deletado. Gerando um novo do zero...")
            res = await self.generate_plan()
            
            if "error" in res: await ctx.send(f"❌ Erro ao gerar novo: {res['error']}")
            else: await ctx.send("✅ Novo plano limpo gerado com sucesso!")
            
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
        else: await ctx.send(f"Dia {res['current_day']} | Tamanho: {res['team_size']}")

async def setup(bot: commands.Bot):
    if bot.cwl_planner_channel_id and bot.db is not None:
        await bot.add_cog(CwlPlannerCog(bot))
