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

# Motores de Ciência de Dados
import numpy as np
from sklearn.cluster import KMeans

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
    AGGRESSIVE = "Força Máxima (Tático)"
    BALANCED = "Balanceado (Seguro)"
    FAIR = "Oportunidade (Farm de Estrelas)"
    SURVIVAL = "Sobrevivência"

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
    attacks_missed: int = 0
    attacks_made: int = 0
    last_updated: Optional[datetime.datetime] = None
    
    @property
    def bayesian_miss_risk(self) -> float:
        """Inferência Bayesiana: Calcula a probabilidade preditiva de o jogador faltar ao ataque."""
        alpha_prior = 1  # Suposição base: 1 falta
        beta_prior = 9   # Suposição base: 9 ataques feitos (10% de risco inicial)
        alpha = alpha_prior + self.attacks_missed
        beta = beta_prior + self.attacks_made
        return alpha / (alpha + beta)
        
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
    xai_justification: str = "" # Novo campo XAI
    predicted_score: float = 0.0 # Novo campo ML
    
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
            "tag": self.tag, "name": self.name, "town_hall": self.town_hall,
            "days_played": self.days_played,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "metrics": asdict(self.metrics),
            "consecutive_days_played": self.consecutive_days_played,
            "consecutive_days_rested": self.consecutive_days_rested,
            "forced_inclusion": self.forced_inclusion,
            "forced_exclusion": self.forced_exclusion,
            "notes": self.notes,
            "xai_justification": self.xai_justification,
            "predicted_score": self.predicted_score
        }

@dataclass
class OpponentAnalysis:
    clan_tag: str
    clan_name: str
    estimated_strength: float
    th_distribution: Dict[str, int]
    threat_level: str
    recommended_strategy: str
    kmeans_confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass 
class DayPlan:
    day: int
    active_roster: List[CWLPlayer]
    substitutions: List[Dict[str, Any]]
    active_bench: List[CWLPlayer]
    backup_bench: List[CWLPlayer]
    strategy_used: str = "Balanceado"
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
            "strategy_used": self.strategy_used,
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

# ==================== MOTOR DE MACHINE LEARNING ====================

class IntelligentRotationEngine:
    def __init__(self, team_size: int, total_days: int = 7):
        self.team_size = team_size
        self.total_days = total_days
    
    def _evaluate_player(self, p: CWLPlayer, ctx: Dict, strat: str) -> Tuple[float, str]:
        """Calcula o Tensor de Força e gera a Justificativa XAI"""
        
        # 1. REGRA DE OURO: Titular Fixo (Priority) anula qualquer matemática.
        if p.status == PlayerStatus.PRIORITY:
            p.predicted_score = 9999.0
            return 9999.0, "⭐ TITULAR FIXO: Status Override. Jogador imune à rotação da IA."
            
        if p.forced_inclusion:
            return 8000.0, "🟢 FORÇADO: Líder exigiu inclusão manual no banco de dados."
            
        # 2. Avaliação Matemática Padrão
        base_power = p.town_hall * 10
        
        # Fadiga (Algoritmo da Mochila de Rotação)
        ideal_days = (ctx["team_size"] / ctx["total_players"]) * ctx["current_day"]
        fairness_deficit = ideal_days - p.days_played
        
        # Bayesiano (Risco de Falta)
        risk = p.metrics.bayesian_miss_risk
        
        # Equação do Tensor
        score = base_power
        score += fairness_deficit * 15.0 # Favorece quem jogou menos
        score -= (p.consecutive_days_played ** 2) * 2.0 # Punição quadrática por fadiga
        score -= risk * 50.0 # Punição brutal por risco de falta
        
        # Ajuste por Estratégia do Dia (K-Means Output)
        if strat == RotationStrategy.AGGRESSIVE.value:
            score += base_power * 0.5 # Peso maior na força bruta
            score -= risk * 100.0 # Tolerância zero a faltas contra clãs difíceis
        elif strat == RotationStrategy.FAIR.value:
            score += fairness_deficit * 30.0 # Peso máximo em quem não jogou
            
        # Geração da Justificativa XAI
        risk_pct = int(risk * 100)
        if fairness_deficit > 1.5:
            justification = f"⚖️ Equidade: Necessita farmar estrelas. Risco de falta: {risk_pct}%."
        elif strat == RotationStrategy.AGGRESSIVE.value and p.town_hall >= ctx["max_th"] - 1:
            justification = f"⚔️ Tático: Convocado por Força Bruta contra oponente extremo."
        elif p.consecutive_days_played == 0:
            justification = f"🔋 Descansado: Entra em rotação com {p.town_hall}0 de poder bélico."
        else:
            justification = f"🧠 Estatística: Selecionado pelo Score Global de {score:.1f} pts."
            
        p.predicted_score = score
        return score, justification
    
    def determine_optimal_strategy(self, current_day: int, opponent: Optional[OpponentAnalysis]) -> str:
        remaining = self.total_days - current_day + 1
        if remaining <= 1: return RotationStrategy.FAIR.value
        
        if opponent:
            if opponent.threat_level in ["Risco Extremo", "Ameaça Alta"]: 
                return RotationStrategy.AGGRESSIVE.value
            elif opponent.threat_level == "Clã Fraco/Morto": 
                return RotationStrategy.FAIR.value
                
        return RotationStrategy.BALANCED.value
    
    def calculate_rotation(self, roster: List[CWLPlayer], active_bench: List[CWLPlayer], backup_bench: List[CWLPlayer], current_day: int, strategy: str) -> Tuple[List[CWLPlayer], List[Dict[str, Any]], List[str]]:
        warnings = []
        available = [p for p in roster + active_bench if not p.forced_exclusion]
        all_p = available + backup_bench
        
        ctx = {
            "current_day": current_day,
            "total_players": max(len(all_p), 1), 
            "team_size": self.team_size,
            "max_th": max((p.town_hall for p in all_p), default=17)
        }
        
        # Pontuação Vetorial de Todos
        scored_players = []
        for p in available:
            score, just = self._evaluate_player(p, ctx, strategy)
            p.xai_justification = just
            scored_players.append((p, score))
            
        # Ordena: Titulares Fixos e Maiores Scores primeiro
        scored_players.sort(key=lambda x: x[1], reverse=True)
        
        new_roster = [x[0] for x in scored_players[:self.team_size]]
        new_bench = [x[0] for x in scored_players[self.team_size:]]
        
        old_tags = {p.tag for p in roster}
        new_tags = {p.tag for p in new_roster}
        
        players_out = [p for p in roster if p.tag not in new_tags]
        players_in = [p for p in new_roster if p.tag not in old_tags]
        
        subs = []
        for po, pi in zip(players_out, players_in):
            
            # XAI da Substituição
            reason_out = "Fadiga" if po.consecutive_days_played >= 3 else "Rotação de Equidade"
            if pi.status == PlayerStatus.PRIORITY: reason_out = "Dando vaga para Titular Fixo"
            
            subs.append({
                "out": po.to_dict(), 
                "in": pi.to_dict(), 
                "reason": f"{pi.xai_justification}", 
                "out_reason": reason_out
            })
            
        if len(new_roster) < self.team_size:
            deficit = self.team_size - len(new_roster)
            warnings.append(f"🚨 Faltam {deficit} membros ativos!")
            needed = min(deficit, len(backup_bench))
            pulls = sorted(backup_bench, key=lambda p: -p.town_hall)[:needed]
            for p in pulls:
                p.xai_justification = "🔥 EMERGÊNCIA: Puxado do Backup para não dar W.O."
                new_roster.append(p)
                subs.append({"out": None, "in": p.to_dict(), "reason": p.xai_justification})
            
        return new_roster, subs, warnings

# ==================== K-MEANS CLUSTERING (OPONENTES) ====================

class OpponentAnalyzerML:
    def __init__(self, api_client): 
        self.api = api_client
        
    async def run_kmeans_clustering(self, league_group: coc.LeagueGroup) -> Dict[str, str]:
        """Usa Scikit-Learn para clusterizar a força dos clãs em 3 categorias de ameaça."""
        clan_weights = {}
        for clan in league_group.clans:
            try:
                full_clan = await self.api.get_clan(clan.tag)
                weight = sum(m.town_hall ** 1.5 for m in full_clan.members) # Pesos exponenciais
                clan_weights[clan.tag] = weight
            except:
                clan_weights[clan.tag] = 500.0 # Fallback
                
        tags = list(clan_weights.keys())
        weights = np.array(list(clan_weights.values())).reshape(-1, 1)
        
        if len(weights) < 3: return {t: "Ameaça Média" for t in tags}
            
        # Clusterização K-Means
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10).fit(weights)
        centers = kmeans.cluster_centers_.flatten()
        sorted_indices = np.argsort(centers) # 0=Fraco, 1=Médio, 2=Forte
        
        threat_mapping = {}
        for i, tag in enumerate(tags):
            cluster_id = kmeans.labels_[i]
            if cluster_id == sorted_indices[2]: threat_mapping[tag] = "Risco Extremo"
            elif cluster_id == sorted_indices[1]: threat_mapping[tag] = "Ameaça Média"
            else: threat_mapping[tag] = "Clã Fraco/Morto"
            
        return threat_mapping

    async def analyze(self, tag: str, name: str, war=None, cluster_threat: str = "Ameaça Média") -> OpponentAnalysis:
        dist = defaultdict(int)
        strength = 0.0
        try:
            clan = war.opponent if war and war.clan.tag != tag else (war.clan if war else await self.api.get_clan(tag))
            for m in clan.members: 
                dist[str(m.town_hall)] += 1
                strength += m.town_hall * 10
        except: pass
        
        strat = RotationStrategy.BALANCED.value
        if cluster_threat == "Risco Extremo": strat = RotationStrategy.AGGRESSIVE.value
        elif cluster_threat == "Clã Fraco/Morto": strat = RotationStrategy.FAIR.value
            
        return OpponentAnalysis(tag, name, strength, dict(dist), cluster_threat, strat, 0.95)

# ==================== COG PRINCIPAL ====================

class CwlPlannerCog(commands.Cog, name="CWLPlanner"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.cwl_plan_collection = self.db.cwl_plan if self.db is not None else None
        self.cwl_state_collection = self.db.cwl_state if self.db is not None else None
        self.rotation_engine: Optional[IntelligentRotationEngine] = None
        self.opponent_analyzer: Optional[OpponentAnalyzerML] = None
        self.posted_daily_plans: Set[str] = set()
        self.season_state: Optional[SeasonState] = None
        self.is_generating_plan = False  

    async def cog_load(self):
        await self._load_state()
        self.monitor_task.start()

    async def cog_unload(self):
        await self._save_state()
        self.monitor_task.cancel()

    async def _init_logic(self, size):
        self.rotation_engine = IntelligentRotationEngine(size)
        if self.bot.api_client:
            self.opponent_analyzer = OpponentAnalyzerML(self.bot.api_client)

    async def _load_state(self):
        if self.cwl_state_collection is None: return
        try:
            s = await self.cwl_state_collection.find_one({"_id": "cog_state"})
            if s:
                self.posted_daily_plans = set(s.get("posted_daily_plans", []))
        except: pass

    async def _save_state(self):
        if self.cwl_state_collection is None: return
        try:
            await self.cwl_state_collection.update_one(
                {"_id": "cog_state"}, 
                {"$set": {"posted_daily_plans": list(self.posted_daily_plans), "updated_at": datetime.datetime.now(pytz.utc)}}, 
                upsert=True
            )
        except: pass

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
            cwl_members = cwl_roster.members if cwl_roster else clan.members

            valid_cwl_tags = {m.tag for m in cwl_members}
            all_relevant_tags = valid_cwl_tags.union(war_tags).union(curr_tags)

            db_cog = self.bot.get_cog("Banco de Dados")
            notes = await db_cog.load_player_notes_from_db() if db_cog else {}
            
            # --- INTEGRAÇÃO COM HITRATE PARA INFERÊNCIA BAYESIANA ---
            hist_cursor = self.db.war_history.find({"war_data.is_cwl": True}).sort("war_data.end_time_iso", -1).limit(10) if self.db else []
            hitrates = defaultdict(lambda: {"missed": 0, "made": 0})
            if self.db:
                async for h_war in hist_cursor:
                    for atk in h_war.get("all_attacks", []):
                        tag = normalize_tag(atk.get("attacker_tag", ""))
                        if tag: hitrates[tag]["made"] += 1
                    for m_atk in h_war.get("missed_attacks_members", []):
                        tag = normalize_tag(m_atk.get("tag", ""))
                        if tag: hitrates[tag]["missed"] += m_atk.get("attacks_left", 1)

            players = []
            member_map = {m.tag: m for m in clan.members}

            for tag in all_relevant_tags:
                m = member_map.get(tag) or next((x for x in cwl_members if x.tag == tag), None)
                if m and m.tag in valid_cwl_tags:
                    note = notes.get(m.tag, {})
                    try: status = PlayerStatus(note.get('cwl_status', 'active'))
                    except: status = PlayerStatus.ACTIVE
                        
                    metrics = PlayerMetrics(
                        attacks_made=hitrates[m.tag]["made"],
                        attacks_missed=hitrates[m.tag]["missed"]
                    )
                    
                    display_name = m.name
                    if not m.tag in curr_tags:
                        status = PlayerStatus.UNAVAILABLE
                        display_name = f"{m.name} 🛑 (Saiu)"
                        
                    players.append(CWLPlayer(
                        tag=m.tag, name=display_name, town_hall=m.town_hall, status=status,
                        metrics=metrics
                    ))
            
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
                        tag = p.get('tag')
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
            p.consecutive_days_played = h["cons"]
            if p.tag in war_tags:
                p.days_played = max(p.days_played, day)
                p.consecutive_days_rested = 0
                roster.append(p)
            else:
                p.consecutive_days_rested = day - h["last"] if h["last"] > 0 else day - 1
                if p.status in [PlayerStatus.ACTIVE, PlayerStatus.PRIORITY]: active.append(p)
                else: backup.append(p)
        return roster, active, backup

    async def generate_rotation_plan(self, force_recalculate: bool = False) -> Dict[str, Any]:
        if self.cwl_plan_collection is None: return {"error": "DB off"}
        if not self.bot.api_client: return {"error": "API off"}
        
        try:
            my_tag = normalize_tag(self.bot.clan_tag)
            try: group = await self.bot.api_client.get_league_group(my_tag)
            except coc.NotFound: return {"error": "CWL off", "status": "NotInCwl"}
            if not group or group.state == "notInWar": return {"error": "CWL off", "status": "NotInCwl"}
            
            existing = await self.cwl_plan_collection.find_one({"_id": group.season})
            if existing and not force_recalculate: return sanitize_for_mongo(existing)

            fallback_team_size = existing.get("team_size", 15) if existing else 15

            tasks_list = [self.bot.api_client.get_league_war(t) for r in group.rounds for t in r if t != '#0']
            war_tags_list = [t for r in group.rounds for t in r if t != '#0']
            war_round_map = {t: i+1 for i, r in enumerate(group.rounds) for t in r if t != '#0'}
            results = await asyncio.gather(*tasks_list, return_exceptions=True)

            war = None; day = 0
            states = {'inWar': [], 'preparation': [], 'warEnded': []}
            any_clan_war = None
            
            opponent_schedule_tags = {} # Dia -> Tag do Oponente

            for w, w_tag in zip(results, war_tags_list):
                if isinstance(w, Exception) or not w: continue
                w_clan = normalize_tag(w.clan.tag); w_opp = normalize_tag(w.opponent.tag)
                if w_clan == my_tag or w_opp == my_tag:
                    any_clan_war = w
                    st = w.state.value if hasattr(w.state, 'value') else str(w.state)
                    op = w.opponent if w_clan == my_tag else w.clan
                    idx = war_round_map.get(w_tag, 0)
                    opponent_schedule_tags[idx] = (op.tag, op.name, w)
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
                else: day = 1; used_fallback = True

            team_size = war.team_size if war else fallback_team_size

            if day >= 8 and not used_fallback: 
                if existing:
                    existing["finished"] = True; existing["current_day"] = 8
                    return sanitize_for_mongo(existing)
                return {"finished": True, "error": "CWL Finalizada."}

            players, _ = await self._fetch_pool(war, team_size)
            if not players: return {"error": "Roster vazio. Ninguém cadastrado."}
            
            await self._init_logic(team_size)
            
            # === RODA O K-MEANS CLUSTERING PARA OS OPONENTES ===
            cluster_threats = await self.opponent_analyzer.run_kmeans_clustering(group)

            roster, active, backup = await self._build_state(players, war, day, existing, my_tag)
            
            if not war or used_fallback:
                if len(roster) < team_size:
                    needed = team_size - len(roster)
                    roster.extend([p for p in active if p not in roster][:needed])
            
            schedule = []
            if existing and 'schedule' in existing:
                schedule = [d for d in existing['schedule'] if d['day'] < day]

            curr_r = roster.copy(); curr_a = active.copy(); curr_b = backup.copy()
            
            # Planeja os próximos dias usando ML
            for d in range(day, 8):
                # 1. Analisa o oponente do dia com K-Means
                opp_info = opponent_schedule_tags.get(d)
                opp_analysis = None
                if opp_info:
                    op_tag, op_name, op_war = opp_info
                    threat = cluster_threats.get(op_tag, "Ameaça Média")
                    opp_analysis = await self.opponent_analyzer.analyze(op_tag, op_name, op_war, threat)
                
                strat = self.rotation_engine.determine_optimal_strategy(d, opp_analysis)
                
                if d == day:
                    # O dia atual já está rolando/preparando, apenas recriamos a visão dele
                    curr_plan = DayPlan(d, curr_r.copy(), [], curr_a.copy(), curr_b.copy(), strat, opp_analysis, 1.0, [], [])
                    schedule.append(sanitize_for_mongo(curr_plan.to_dict()))
                else:
                    # Dias futuros (Cálculo Preditivo XAI)
                    new_r, subs, warns = self.rotation_engine.calculate_rotation(curr_r, curr_a, curr_b, d, strat)
                    for p in new_r: p.days_played += 1
                    curr_r = new_r
                    schedule.append(sanitize_for_mongo(DayPlan(d, new_r, subs, curr_a, curr_b, strat, opp_analysis, 0.85, warns).to_dict()))
            
            # Header Data para o Painel Web
            clans_data = []
            for c in group.clans:
                clans_data.append({"name": c.name, "tag": c.tag, "badge_url": c.badge.url if hasattr(c, 'badge') and c.badge else ""})

            rounds_list = []
            for i in range(1, len(group.rounds) + 1):
                if i < day: rounds_list.append("warEnded")
                elif i == day:
                    is_prep = any(idx == day for w, idx, t, op in states.get('preparation', []))
                    rounds_list.append("preparation" if is_prep else "inWar")
                else: rounds_list.append("unstarted")

            data = {
                "schedule": schedule,
                "participation_score": [sanitize_for_mongo(p.to_dict()) for p in players],
                "warning": "Modo Fallback" if used_fallback else "",
                "current_day": day, "team_size": team_size, "season": group.season, 
                "status": "InCwl", "state": group.state, 
                "clans": clans_data, "rounds": rounds_list
            }
            
            await self.cwl_plan_collection.update_one({"_id": group.season}, {"$set": sanitize_for_mongo(data)}, upsert=True)
            return data

        except Exception as e:
            logger.error(f"Generate error: {e}", exc_info=True)
            return {"error": f"Erro interno ML: {str(e)}"}

    @tasks.loop(minutes=20)
    async def monitor_task(self):
        if not self.bot.is_ready(): return
        if getattr(self, "is_generating_plan", False): return
        self.is_generating_plan = True
        try: await self.generate_plan(force_recalculate=False)
        finally: self.is_generating_plan = False

    @monitor_task.before_loop
    async def before_monitor_task(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(CwlPlannerCog(bot))
