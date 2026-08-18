# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import geniuslib as coc
import datetime
from typing import List, Dict, Any, Tuple, Optional
import re
import pytz
import asyncio
import traceback
import time

# Motores de Data Science e Machine Learning
import numpy as np
import pandas as pd
from thefuzz import fuzz as fuzzy
from sklearn.ensemble import IsolationForest
import xgboost as xgb
import pickle

logger = logging.getLogger("smurf_detection_cog")

class SmurfDetectionCog(commands.Cog, name="Detetor de Smurfs IA"):
    """
    Sistema Pericial de Machine Learning (XAI) v3.0.
    Motores: IsolationForest, Distância de Cossenos, Perfil de Troféus/Achievements/Tropas,
    Calibragem Bayesiana, Baselines Estatísticos e Feedback Loop.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

        self.DECAY_DAYS = 7
        self.DECAY_PERCENTAGE = 0.15
        self.MIN_FUZZY_RATIO = 78
        self.DONATION_SYNC_THRESHOLD = 0
        self.WAR_SYNC_SECONDS = 90
        self.TELEMETRY_DONATION_POINTS = 3
        self.TELEMETRY_WAR_POINTS = 8
        self.TELEMETRY_COOLDOWN_HOURS = 4
        self.ISOLATION_FOREST_CONTAMINATION = 0.15
        self._if_score_cache: Dict[str, float] = {}
        self._pair_if_score_cache: Dict[str, float] = {}
        self._donation_pair_history_ttl: Dict[str, float] = {}
        self._if_score_cache_maxsize = 1000
        self._pair_if_score_cache_maxsize = 1000
        self._if_score_cache_ttl = 86400
        self._pair_if_score_cache_ttl = 86400
        self._if_score_ts: Dict[str, float] = {}
        self._pair_if_score_ts: Dict[str, float] = {}

        # Bayesian prior: P(smurf) = 5% for any random pair
        self.BAYESIAN_PRIOR = 0.05

        # XGBoost training config
        self.XGB_PSEUDO_WEIGHT = 0.3
        self.XGB_MIN_REAL_LABELS = 5
        self.XGB_MIN_TOTAL_SAMPLES = 20

        self.last_clan_state: Dict[str, Dict[str, int]] = {}
        self.last_war_attacks: Dict[str, float] = {}
        self._telemetry_cooldown: Dict[str, float] = {}
        self._donation_pair_history: Dict[str, int] = {}
        self._last_clan_baselines: Optional[Dict] = None
        self._last_clan_players: list = []
        self._isolation_forest: Optional[IsolationForest] = None
        self._pair_isolation_forest: Optional[IsolationForest] = None
        self._xgb_model: Optional[xgb.XGBClassifier] = None
        self._xgb_retrain_counter = 0
        self._xgb_is_trained: bool = False
        self._xgb_real_labels: int = 0
        self._judged_pairs: set = set()

    async def _load_judged_pairs(self):
        if self.db is None:
            return
        try:
            cursor = self.db.smurf_training.find(
                {"real_label": {"$exists": True}},
                {"_id": 1}
            )
            async for doc in cursor:
                self._judged_pairs.add(doc["_id"])
            logger.info(f"XAI: {len(self._judged_pairs)} pares julgados carregados do banco.")
        except Exception as e:
            logger.error(f"Erro ao carregar pares julgados: {e}")

    async def cog_load(self):
        await self._load_judged_pairs()
        self.behavior_monitor_task.start()
        self.regenerative_ai_task.start()
        logger.info("XAI v2.0: Motor Matemático e Radares Forenses ativados.")

    async def cog_unload(self):
        self.behavior_monitor_task.cancel()
        self.regenerative_ai_task.cancel()

    def _evict_if_score_cache(self):
        if len(self._if_score_cache) > self._if_score_cache_maxsize:
            now = time.monotonic()
            expired = [k for k, t in self._if_score_cache.items()
                       if now - t > self._if_score_cache_ttl] if hasattr(self, '_if_score_ts') else []
            for k in expired:
                self._if_score_cache.pop(k, None)
                if hasattr(self, '_if_score_ts'):
                    self._if_score_ts.pop(k, None)
            while len(self._if_score_cache) > self._if_score_cache_maxsize:
                if hasattr(self, '_if_score_ts') and self._if_score_ts:
                    oldest = min(self._if_score_ts, key=self._if_score_ts.get)
                    self._if_score_cache.pop(oldest, None)
                    self._if_score_ts.pop(oldest, None)
                else:
                    self._if_score_cache.pop(next(iter(self._if_score_cache)), None)

    def _evict_pair_if_score_cache(self):
        if len(self._pair_if_score_cache) > self._pair_if_score_cache_maxsize:
            if hasattr(self, '_pair_if_score_ts') and self._pair_if_score_ts:
                while len(self._pair_if_score_cache) > self._pair_if_score_cache_maxsize:
                    oldest = min(self._pair_if_score_ts, key=self._pair_if_score_ts.get)
                    self._pair_if_score_cache.pop(oldest, None)
                    self._pair_if_score_ts.pop(oldest, None)
            else:
                while len(self._pair_if_score_cache) > self._pair_if_score_cache_maxsize:
                    self._pair_if_score_cache.pop(next(iter(self._pair_if_score_cache)), None)

    # ==================== DATA MINING (EXTRAÇÃO DE FEATURES) ====================

    def _extract_troop_profile(self, player: coc.Player) -> np.ndarray:
        """Perfil de升级 de tropas por categoria (6 dimensões)."""
        categories = {
            'war_elite': ["Electro Dragon", "Balloon", "Yeti", "Dragon", "Lava Hound"],
            'farming': ["Barbarian", "Archer", "Goblin", "Giant", "Minion"],
            'dark_elite': ["Hog Rider", "Miner", "Electro Titan", "Headhunter", "Ice Golem"],
            'spells': ["Rage Spell", "Freeze Spell", "Lightning Spell", "Heal Spell", "Invisibility Spell"],
            'siege': ["Wall Wrecker", "Battle Blimp", "Stone Slammer", "Siege Barracks", "Log Launcher"],
            'air_support': ["Healer", "Baby Dragon", "Inferno Dragon", "Dragon Rider", "Minion Prince"],
        }
        profile = []
        for cat_name, troop_names in categories.items():
            levels = []
            for t in player.troops + player.spells:
                try:
                    if t.village == coc.VillageType.home and t.name in troop_names:
                        levels.append(t.level / max(t.max_level, 1))
                except Exception:
                    continue
            profile.append(np.mean(levels) if levels else 0.0)
        return np.array(profile)

    def _extract_achievement_profile(self, player: coc.Player) -> np.ndarray:
        """Fingerprint completo de achievements (10 dimensões)."""
        keys = [
            "Gold Grab", "Elixir Escapade", "Heroic Heist", "Dark SpoT",
            "War Hero", "Conqueror", "Nice and Tidy", "Aggressive Capitalism",
            "Games Champion", "Unlimited Power",
        ]
        vec = []
        for key in keys:
            ach = player.get_achievement(name=key)
            vec.append(min((ach.value if ach else 0) / 1e7, 1.0))
        return np.array(vec)

    def _extract_feature_vector(self, player: coc.Player) -> np.ndarray:
        """Vetoriza o perfil evolutivo do jogador em 12 dimensões."""
        try:
            home_heroes = ["Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion", "Minion Prince", "Dragon Duke"]
            heroes_lvl = sum(h.level for h in player.heroes if h.name in home_heroes)
            max_hero_lvl = sum(h.max_level for h in player.heroes if hasattr(h, 'max_level') and h.name in home_heroes) or 1

            ach_gold = player.get_achievement(name="Gold Grab")
            ach_war = player.get_achievement(name="War Hero")
            ach_attacker = player.get_achievement(name="Conqueror")
            ach_games = player.get_achievement(name="Games Champion")

            return np.array([
                player.town_hall / 17.0,
                heroes_lvl / max_hero_lvl,
                min(player.attack_wins / 5000.0, 1.0),
                min(player.defense_wins / 1000.0, 1.0),
                min(player.war_stars / 5000.0, 1.0),
                min(player.trophies / 6000.0, 1.0),
                min((ach_gold.value if ach_gold else 0) / 2e9, 1.0),
                min((ach_war.value if ach_war else 0) / 2000.0, 1.0),
                min((ach_attacker.value if ach_attacker else 0) / 2000.0, 1.0),
                min((ach_games.value if ach_games else 0) / 1000.0, 1.0),
                player.exp_level / 500.0,
                player.builder_hall_level / 10.0 if hasattr(player, 'builder_hall_level') else 0.0,
            ])
        except Exception:
            return np.zeros(12)

    def _extract_hero_equipment_fingerprint(self, player: coc.Player) -> np.ndarray:
        """Fingerprint de equipamentos dos heróis — sinal forte de individualidade.
        Retorna vetor binário (tem/não tem) + nível normalizado apenas para equipamentos desbloqueados no TH."""
        eqp = player.hero_equipment if hasattr(player, 'hero_equipment') else []
        names_ordered = [
            "Barbarian Puppet", "Rage Vial", "Archer Puppet", "Invisibility Vial",
            "Eternal Tome", "Life Gem", "Rage Gem", "Healing Tome",
            "Royal Gem", "Seeking Shield", "Hog Rider Puppet", "Skeleton Spell",
            "Lava Puppet", "Frozen Arrow", "Giant Arrow", "Electro Boots",
        ]
        # TH level determina quais equipamentos estão desbloqueados
        th = player.town_hall
        unlocked_slots = 0
        if th >= 8: unlocked_slots = 1
        if th >= 9: unlocked_slots = 2
        if th >= 10: unlocked_slots = 3
        if th >= 11: unlocked_slots = 4
        if th >= 12: unlocked_slots = 5
        if th >= 13: unlocked_slots = 6
        if th >= 14: unlocked_slots = 7
        if th >= 15: unlocked_slots = 8
        # Apenas considera equipamentos até o slot desbloqueado
        vec = []
        for i, name in enumerate(names_ordered):
            if i >= unlocked_slots:
                vec.append(0.0)  # Slot ainda não desbloqueado = 0
                continue
            found = next((e for e in eqp if e.name == name), None)
            if found:
                vec.append(found.level / max(found.max_level, 1))
            else:
                vec.append(0.0)
        return np.array(vec)

    def _compute_deviation_vector(self, player_vec: np.ndarray, clan_mean: np.ndarray, clan_std: np.ndarray) -> np.ndarray:
        """Quanto cada feature desvia da média do clã em desvios padrão."""
        safe_std = np.where(clan_std < 0.01, 0.01, clan_std)
        return (player_vec - clan_mean) / safe_std

    def _calculate_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calcula o ângulo exato de evolução entre duas contas."""
        if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0: return 0.0
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def _analyze_mula_signature(self, player: coc.Player) -> Tuple[bool, int, str]:
        """Forense de Laboratório: Analisa se o perfil de upgrade foca apenas em Doação.
        Só suspeita em TH14+ (onde equipamentos e meta de doação são definidos)."""
        if player.town_hall < 14: return False, 0, ""
            
        donation_troops = ["Electro Dragon", "Balloon", "Yeti", "Rage Spell", "Freeze Spell"]
        basic_troops = ["Barbarian", "Archer", "Giant", "Goblin"]
        don_levels, bas_levels = [], []
        
        for t in player.troops + player.spells:
            try:
                if t.village == coc.VillageType.home:
                    if t.name in donation_troops: don_levels.append(t.level / max(t.max_level, 1))
                    elif t.name in basic_troops: bas_levels.append(t.level / max(t.max_level, 1))
            except (IndexError, AttributeError, KeyError):
                continue
                    
        if not don_levels or not bas_levels: return False, 0, ""
            
        avg_don = np.mean(don_levels)
        avg_bas = np.mean(bas_levels)
        
        if avg_don > 0.85 and avg_bas < 0.35:
            score = int((avg_don - avg_bas) * 100)
            return True, score, f"Assinatura 'Mula' detectada. Tropas de suporte estão {avg_don*100:.0f}% maximizadas; tropas básicas sucateadas ({avg_bas*100:.0f}%)."
            
        return False, 0, ""

    # ==================== APRENDIZADO DE MÁQUINA (XGBoost) ====================

    def _extract_pair_features(self, p1: coc.Player, p2: coc.Player, telemetry: Dict, baseline: Optional[Dict]) -> pd.DataFrame:
        """Extrai features de TODOS os eixos analíticos para o XGBoost decidir."""
        v1 = self._extract_feature_vector(p1)
        v2 = self._extract_feature_vector(p2)
        t1 = self._extract_troop_profile(p1)
        t2 = self._extract_troop_profile(p2)
        a1 = self._extract_achievement_profile(p1)
        a2 = self._extract_achievement_profile(p2)
        h1 = self._extract_hero_equipment_fingerprint(p1)
        h2 = self._extract_hero_equipment_fingerprint(p2)

        feat_cos = self._calculate_cosine_similarity(v1, v2)
        troop_cos = self._calculate_cosine_similarity(t1, t2)
        ach_cos = self._calculate_cosine_similarity(a1, a2)
        hero_cos = self._calculate_cosine_similarity(h1, h2)

        behavior_score = int(telemetry.get('score', 0))
        logs = telemetry.get('logs', [])
        don_count = sum(1 for l in logs if (l.get("axis") if isinstance(l, dict) else "") == "Economia de Tropas")
        war_count = sum(1 for l in logs if (l.get("axis") if isinstance(l, dict) else "") == "Sincronia Mutex")
        name_sim = self._phonetic_lexical_analysis(p1.name, p2.name)

        if_main = self._get_isolation_forest_score(p1)
        if_smurf = self._get_isolation_forest_score(p2)
        pair_if = self._get_pair_isolation_forest_score(p1, p2)
        is_mula, mula_score, _ = self._analyze_mula_signature(p2)
        is_asymmetric, asym_ratio, _ = self._analyze_donation_asymmetry(telemetry)

        feat = {
            'name_sim': name_sim / 100.0,
            'feat_cos': feat_cos,
            'troop_cos': troop_cos,
            'ach_cos': ach_cos,
            'hero_cos': hero_cos,
            'th_gap': abs(p1.town_hall - p2.town_hall) / 10.0,
            'exp_gap': min(abs(p1.exp_level - p2.exp_level), 200) / 200.0,
            'war_stars_gap': min(abs(p1.war_stars - p2.war_stars), 2000) / 2000.0,
            'attack_wins_gap': min(abs(p1.attack_wins - p2.attack_wins), 2000) / 2000.0,
            'behavior_score': behavior_score / 100.0,
            'don_count': min(don_count, 50) / 50.0,
            'war_count': min(war_count, 20) / 20.0,
            'has_war_sync': 1.0 if war_count > 0 else 0.0,
            'pair_if': pair_if,
            'if_main': if_main,
            'if_smurf': if_smurf,
            'is_mula': 1.0 if is_mula else 0.0,
            'mula_score': mula_score / 100.0,
            'don_asymmetry': asym_ratio,
            'is_asymmetric': 1.0 if is_asymmetric else 0.0,
        }

        if baseline and len(self._last_clan_players) >= 5:
            feat['feat_z'] = self._get_z_score(feat_cos, baseline['feat_mean'], baseline['feat_std'])
            feat['troop_z'] = self._get_z_score(troop_cos, baseline['troop_mean'], baseline['troop_std'])
            feat['ach_z'] = self._get_z_score(ach_cos, baseline['ach_mean'], baseline['ach_std'])

            dev1 = self._compute_deviation_vector(v1, baseline['vec_mean'], baseline['vec_std'])
            dev2 = self._compute_deviation_vector(v2, baseline['vec_mean'], baseline['vec_std'])
            dev_cos = self._calculate_deviation_similarity(dev1, dev2)
            feat['dev_cos'] = dev_cos
            feat['dev_mag'] = (np.linalg.norm(dev1) + np.linalg.norm(dev2)) / 20.0

            h_self_sims = []
            for p in self._last_clan_players:
                hp = self._extract_hero_equipment_fingerprint(p)
                h_self_sims.append(self._calculate_cosine_similarity(h1, hp))
            if len(h_self_sims) > 2:
                feat['hero_z'] = self._get_z_score(hero_cos, np.mean(h_self_sims), max(np.std(h_self_sims), 0.01))
            else:
                feat['hero_z'] = 0.0
        else:
            for k in ['feat_z', 'troop_z', 'ach_z', 'dev_cos', 'dev_mag', 'hero_z']:
                feat[k] = 0.0

        return pd.DataFrame([feat])

    def _ensure_xgb_model(self):
        """Cria ou recria o modelo XGBoost."""
        self._xgb_model = xgb.XGBClassifier(
            n_estimators=150, max_depth=5, learning_rate=0.08,
            subsample=0.8, colsample_bytree=0.8,
            scale_pos_weight=3.0,
            random_state=42, use_label_encoder=False,
            eval_metric='logloss',
        )

    async def _store_training_example_async(self, pair_id: str, tag1: str, tag2: str,
                                             features: dict, pseudo_label: float):
        """Armazena cada avaliação de par como exemplo de treinamento (pseudo-labelado)."""
        if self.db is None:
            return
        try:
            existing = await self.db.smurf_training.find_one({"_id": pair_id})
            if existing and existing.get("real_label") is not None:
                return
            if existing:
                await self.db.smurf_training.update_one(
                    {"_id": pair_id},
                    {"$set": {
                        "features": features,
                        "pseudo_label": pseudo_label,
                        "updated_at": datetime.datetime.now(pytz.utc),
                    }}
                )
            else:
                await self.db.smurf_training.insert_one({
                    "_id": pair_id,
                    "tag1": tag1,
                    "tag2": tag2,
                    "features": features,
                    "pseudo_label": pseudo_label,
                    "pseudo_weight": self.XGB_PSEUDO_WEIGHT,
                    "real_label": None,
                    "real_weight": 0.0,
                    "created_at": datetime.datetime.now(pytz.utc),
                    "updated_at": datetime.datetime.now(pytz.utc),
                })
        except Exception:
            pass

    async def _train_xgb_from_db(self):
        """Treina XGBoost com TODAS as features + pseudo-labels + feedback real."""
        if self.db is None:
            return
        try:
            cursor = self.db.smurf_training.find({})
            docs = []
            async for doc in cursor:
                docs.append(doc)

            if len(docs) < self.XGB_MIN_TOTAL_SAMPLES:
                logger.info(f"XGBoost: aguardando mais dados ({len(docs)}/{self.XGB_MIN_TOTAL_SAMPLES})")
                return

            real_labels = sum(1 for d in docs if d.get("real_label") is not None)
            if real_labels < self.XGB_MIN_REAL_LABELS:
                logger.info(f"XGBoost: aguardando mais labels reais ({real_labels}/{self.XGB_MIN_REAL_LABELS})")
                return

            self._ensure_xgb_model()

            feature_names = [
                'name_sim', 'feat_cos', 'troop_cos', 'ach_cos', 'hero_cos',
                'th_gap', 'exp_gap', 'war_stars_gap', 'attack_wins_gap',
                'behavior_score', 'don_count', 'war_count', 'has_war_sync',
                'pair_if', 'if_main', 'if_smurf',
                'is_mula', 'mula_score', 'don_asymmetry', 'is_asymmetric',
                'feat_z', 'troop_z', 'ach_z', 'dev_cos', 'dev_mag', 'hero_z',
            ]
            rows = []
            labels = []
            weights = []
            for doc in docs:
                feats = doc.get("features", {})
                if not feats:
                    continue
                row = [feats.get(k, 0.0) for k in feature_names]
                rows.append(row)

                if doc.get("real_label") is not None:
                    labels.append(doc["real_label"])
                    weights.append(doc.get("real_weight", 1.0))
                else:
                    labels.append(doc.get("pseudo_label", 0.5))
                    weights.append(doc.get("pseudo_weight", self.XGB_PSEUDO_WEIGHT))

            X = pd.DataFrame(rows, columns=feature_names)
            y = np.array([min(max(l, 0.0), 1.0) for l in labels])
            w = np.array(weights)

            self._xgb_model.fit(X, y, sample_weight=w)
            self._xgb_is_trained = True
            self._xgb_real_labels = real_labels
            logger.info(f"XGBoost treinado: {len(docs)} amostras, {real_labels} labels reais, {len(docs)-real_labels} pseudo-labels")
        except Exception as e:
            logger.error(f"Erro treino XGBoost: {e}")

    def _xgb_predict(self, pair_features: pd.DataFrame) -> float:
        """Retorna probabilidade prevista pelo XGBoost."""
        if self._xgb_model is None:
            return 0.5
        try:
            return float(self._xgb_model.predict_proba(pair_features)[0, 1])
        except Exception:
            return 0.5

    # ==================== PROCESSAMENTO DE LINGUAGEM NATURAL ====================

    def _phonetic_lexical_analysis(self, name1: str, name2: str) -> int:
        n1 = re.sub(r'[^\w\s]', '', name1.lower())
        n2 = re.sub(r'[^\w\s]', '', name2.lower())
        ratio = fuzzy.ratio(n1, n2)
        token_ratio = fuzzy.token_set_ratio(n1, n2)
        return max(ratio, token_ratio)

    # ==================== BASELINE ESTATÍSTICO DO CLÃ ====================

    def _compute_name_similarity_baseline(self, players) -> Tuple[float, float]:
        """Calcula média e desvio padrão da similaridade de nomes entre todos os pares do clã."""
        sims = []
        names = [getattr(p, 'name', '') or p.get('name', '') for p in players]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                sims.append(fuzzy.ratio(names[i], names[j]))
        if len(sims) < 2:
            return 30.0, 15.0
        return float(np.mean(sims)), float(np.std(sims))

    def _compute_feature_similarity_baseline(self, vectors: List[np.ndarray]) -> Tuple[float, float]:
        """Calcula média e desvio padrão da similaridade de cossenos entre todos os pares."""
        sims = []
        for i in range(len(vectors)):
            for j in range(i + 1, len(vectors)):
                v1, v2 = vectors[i], vectors[j]
                n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
                if n1 > 0 and n2 > 0:
                    sims.append(float(np.dot(v1, v2) / (n1 * n2)))
        if len(sims) < 2:
            return 0.5, 0.2
        return float(np.mean(sims)), float(np.std(sims))

    def _compute_troop_similarity_baseline(self, profiles: List[np.ndarray]) -> Tuple[float, float]:
        """Calcula média e desvio padrão da similaridade de tropas entre todos os pares do clã."""
        sims = []
        for i in range(len(profiles)):
            for j in range(i + 1, len(profiles)):
                v1, v2 = profiles[i], profiles[j]
                n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
                if n1 > 0 and n2 > 0:
                    sims.append(float(np.dot(v1, v2) / (n1 * n2)))
        if len(sims) < 2:
            return 0.85, 0.10
        return float(np.mean(sims)), float(np.std(sims))

    def _compute_ach_similarity_baseline(self, profiles: List[np.ndarray]) -> Tuple[float, float]:
        """Calcula média e desvio padrão da similaridade de achievements entre todos os pares do clã."""
        sims = []
        for i in range(len(profiles)):
            for j in range(i + 1, len(profiles)):
                v1, v2 = profiles[i], profiles[j]
                n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
                if n1 > 0 and n2 > 0:
                    sims.append(float(np.dot(v1, v2) / (n1 * n2)))
        if len(sims) < 2:
            return 0.85, 0.10
        return float(np.mean(sims)), float(np.std(sims))

    def _prepare_clan_baselines(self, clan_members: List[coc.ClanMember], players_full: List[coc.Player]):
        """Prepara baselines estatísticos e treina Isolation Forest (individual + par)."""
        player_map = {p.tag: p for p in players_full}
        member_players = [player_map[m.tag] for m in clan_members if m.tag in player_map]

        if len(member_players) < 5:
            self._last_clan_baselines = None
            self._isolation_forest = None
            self._pair_isolation_forest = None
            return

        vectors = [self._extract_feature_vector(p) for p in member_players]
        troop_profiles = [self._extract_troop_profile(p) for p in member_players]
        ach_profiles = [self._extract_achievement_profile(p) for p in member_players]
        hero_eq_profiles = [self._extract_hero_equipment_fingerprint(p) for p in member_players]
        self._last_clan_players = list(member_players)
        name_mean, name_std = self._compute_name_similarity_baseline(member_players)
        feat_mean, feat_std = self._compute_feature_similarity_baseline(vectors)
        troop_mean, troop_std = self._compute_troop_similarity_baseline(troop_profiles)
        ach_mean, ach_std = self._compute_ach_similarity_baseline(ach_profiles)

        arr_v = np.array(vectors)
        arr_t = np.array(troop_profiles)
        arr_a = np.array(ach_profiles)
        arr_h = np.array(hero_eq_profiles) if hero_eq_profiles else np.array([])

        self._last_clan_baselines = {
            'name_mean': name_mean, 'name_std': name_std,
            'feat_mean': feat_mean, 'feat_std': feat_std,
            'troop_mean': troop_mean, 'troop_std': troop_std,
            'ach_mean': ach_mean, 'ach_std': ach_std,
            'vec_mean': np.mean(arr_v, axis=0) if len(arr_v) > 0 else np.zeros(12),
            'vec_std': np.std(arr_v, axis=0) if len(arr_v) > 0 else np.ones(12),
            'troop_vec_mean': np.mean(arr_t, axis=0) if len(arr_t) > 0 else np.zeros(6),
            'troop_vec_std': np.std(arr_t, axis=0) if len(arr_t) > 0 else np.ones(6),
            'ach_vec_mean': np.mean(arr_a, axis=0) if len(arr_a) > 0 else np.zeros(10),
            'ach_vec_std': np.std(arr_a, axis=0) if len(arr_a) > 0 else np.ones(10),
            'hero_eq_mean': np.mean(arr_h, axis=0) if len(arr_h) > 0 else np.zeros(16),
            'hero_eq_std': np.std(arr_h, axis=0) if len(arr_h) > 0 else np.ones(16),
        }

        try:
            X = np.array(vectors)
            if len(X) >= 10:
                model = IsolationForest(
                    contamination=self.ISOLATION_FOREST_CONTAMINATION,
                    random_state=42, n_estimators=100
                )
                model.fit(X)
                self._isolation_forest = model
                # Cache decision function thresholds for calibration
                self._if_threshold = np.percentile(model.decision_function(X), 100 * self.ISOLATION_FOREST_CONTAMINATION)
            else:
                self._isolation_forest = None
                self._if_threshold = 0.0

            pair_vectors = []
            for i in range(len(member_players)):
                for j in range(i + 1, len(member_players)):
                    stacked = np.concatenate([
                        vectors[i], troop_profiles[i], ach_profiles[i],
                        vectors[j], troop_profiles[j], ach_profiles[j],
                    ])
                    pair_vectors.append(stacked)
            
            # Fix: check AFTER building all pair vectors
            if len(pair_vectors) >= 20:
                pair_model = IsolationForest(
                    contamination=0.1, random_state=42, n_estimators=100
                )
                pair_model.fit(np.array(pair_vectors))
                self._pair_isolation_forest = pair_model
                self._pair_if_threshold = np.percentile(pair_model.decision_function(np.array(pair_vectors)), 10)
            else:
                self._pair_isolation_forest = None
                self._pair_if_threshold = 0.0
        except Exception:
            self._isolation_forest = None
            self._pair_isolation_forest = None
            self._if_threshold = 0.0
            self._pair_if_threshold = 0.0



    def _get_isolation_forest_score(self, player: coc.Player) -> float:
        """Retorna score de anomalia do IsolationForest (0=normal, 1=anômalo)."""
        if self._isolation_forest is None:
            return 0.0
        cache_key = player.tag
        cached = self._if_score_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            vec = self._extract_feature_vector(player).reshape(1, -1)
            score = self._isolation_forest.decision_function(vec)[0]
            if self._if_threshold != 0.0:
                anomaly_score = max(0.0, min(1.0, (self._if_threshold - score) / (abs(self._if_threshold) + 0.1)))
            else:
                anomaly_score = 0.0
            self._if_score_cache[cache_key] = anomaly_score
            self._if_score_ts[cache_key] = time.monotonic()
            self._evict_if_score_cache()
            return anomaly_score
        except Exception:
            return 0.0

    def _get_pair_isolation_forest_score(self, p1: coc.Player, p2: coc.Player) -> float:
        """Score de anomalia do par (0=normal, 1=anômalo)."""
        if self._pair_isolation_forest is None:
            return 0.0
        pair_key = f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}"
        cached = self._pair_if_score_cache.get(pair_key)
        if cached is not None:
            return cached
        try:
            v1, t1, a1 = (
                self._extract_feature_vector(p1),
                self._extract_troop_profile(p1),
                self._extract_achievement_profile(p1),
            )
            v2, t2, a2 = (
                self._extract_feature_vector(p2),
                self._extract_troop_profile(p2),
                self._extract_achievement_profile(p2),
            )
            stacked = np.concatenate([v1, t1, a1, v2, t2, a2]).reshape(1, -1)
            score = self._pair_isolation_forest.decision_function(stacked)[0]
            if self._pair_if_threshold != 0.0:
                anomaly_score = max(0.0, min(1.0, (self._pair_if_threshold - score) / (abs(self._pair_if_threshold) + 0.1)))
            else:
                anomaly_score = 0.0
            self._pair_if_score_cache[pair_key] = anomaly_score
            self._pair_if_score_ts[pair_key] = time.monotonic()
            self._evict_pair_if_score_cache()
            return anomaly_score
        except Exception:
            return 0.0

    def _calculate_bayesian_confidence(self, likelihood_ratios: List[float]) -> float:
        """Calcula confiança via Teorema de Bayes."""
        prior_odds = self.BAYESIAN_PRIOR / (1.0 - self.BAYESIAN_PRIOR)
        posterior_odds = prior_odds
        for lr in likelihood_ratios:
            posterior_odds *= lr
        posterior_prob = posterior_odds / (1.0 + posterior_odds)
        return min(max(int(posterior_prob * 100), 0), 99)

    def _get_z_score(self, value: float, mean: float, std: float) -> float:
        return (value - mean) / max(std, 0.001)

    # ==================== TELEMETRIA (GRAVAÇÃO DB) ====================

    async def _log_telemetry(self, p1: coc.ClanMember, p2: coc.ClanMember, points: int, log_msg: str, axis: str = "Mutex"):
        if self.db is None or p1.tag == p2.tag: return

        pair_id = f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}"
        now = datetime.datetime.now(pytz.utc)
        now_ts = now.timestamp()

        cooldown_key = f"telemetry:{pair_id}"
        last_log = self._telemetry_cooldown.get(cooldown_key, 0.0)
        if now_ts - last_log < self.TELEMETRY_COOLDOWN_HOURS * 3600:
            return
        self._telemetry_cooldown[cooldown_key] = now_ts
        if len(self._telemetry_cooldown) > 2000:
            stale = [k for k, v in self._telemetry_cooldown.items() if now_ts - v > self.TELEMETRY_COOLDOWN_HOURS * 3600]
            for k in stale[:500]:
                self._telemetry_cooldown.pop(k, None)

        await self.db.smurf_evidence.update_one(
            {"_id": pair_id},
            {
                "$setOnInsert": {"tag1": p1.tag, "tag2": p2.tag},
                "$inc": {"score": points},
                "$set": {"last_updated": now},
                "$push": {"logs": {"$each": [{"time": now_ts, "msg": f"[{now.strftime('%d/%m %H:%M')}] {log_msg}", "axis": axis}], "$slice": -30}}
            },
            upsert=True
        )

    # ==================== THREADS ASSÍNCRONAS DE VIGILÂNCIA ====================
    
    @tasks.loop(hours=24)
    async def regenerative_ai_task(self):
        if not self.bot.is_ready() or self.db is None: return 
        try:
            decay_date = datetime.datetime.now(pytz.utc) - datetime.timedelta(days=self.DECAY_DAYS)
            cursor = self.db.smurf_evidence.find({"last_updated": {"$lt": decay_date}, "score": {"$gt": 0}})
            
            async for doc in cursor:
                new_score = int(doc["score"] * (1.0 - self.DECAY_PERCENTAGE))
                if new_score < 5:
                    await self.db.smurf_evidence.delete_one({"_id": doc["_id"]})
                else:
                    await self.db.smurf_evidence.update_one(
                        {"_id": doc["_id"]}, 
                        {
                            "$set": {"score": new_score, "last_updated": datetime.datetime.now(pytz.utc)},
                            "$push": {"logs": {"$each": [{"time": datetime.datetime.now(pytz.utc).timestamp(), "msg": f"[{datetime.datetime.now().strftime('%d/%m')}] 📉 Atenuação: Score caiu para {new_score}.", "axis": "Regeneração"}], "$slice": -30}}
                        }
                    )
        except Exception: pass
        # Cleanup in-memory donation pair history (TTL 7 days)
        now = datetime.datetime.now().timestamp()
        expired = [k for k, v in self._donation_pair_history_ttl.items() if now - v > 7 * 86400]
        for k in expired:
            self._donation_pair_history.pop(k, None)
            self._donation_pair_history_ttl.pop(k, None)
        # Treina XGBoost com feedback acumulado
        self._xgb_retrain_counter += 1
        if self._xgb_retrain_counter % 3 == 0:
            await self._train_xgb_from_db()

    @regenerative_ai_task.before_loop
    async def before_regenerative(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=3)
    async def behavior_monitor_task(self):
        if not self.bot.is_ready() or not self.bot.api_client: return
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            if not clan: return

            clan_tags = {m.tag for m in clan.members}
            current_state = {m.tag: {"donations": m.donations, "received": m.received, "member": m} for m in clan.members}
            now_ts = datetime.datetime.now().timestamp()

            # RADAR DE DOAÇÕES (mais conservador)
            if self.last_clan_state:
                donors, receivers = [], []
                for tag, state in current_state.items():
                    if tag in self.last_clan_state:
                        d_diff = state["donations"] - self.last_clan_state[tag]["donations"]
                        r_diff = state["received"] - self.last_clan_state[tag]["received"]
                        if d_diff > 0: donors.append((state["member"], d_diff))
                        if r_diff > 0: receivers.append((state["member"], r_diff))

                if donors and receivers:
                    for d_member, d_amount in donors:
                        for r_member, r_amount in receivers:
                            if d_member.tag in clan_tags and r_member.tag in clan_tags:
                                if d_amount > 0 and r_amount > 0 and d_amount == r_amount:
                                    pair_id = f"{min(d_member.tag, r_member.tag)}_{max(d_member.tag, r_member.tag)}"
                                    self._donation_pair_history[pair_id] = self._donation_pair_history.get(pair_id, 0) + 1
                                    self._donation_pair_history_ttl[pair_id] = now_ts
                                    hit_count = self._donation_pair_history.get(pair_id, 0)
                                    if hit_count >= 1:
                                        await self._log_telemetry(
                                            d_member, r_member, self.TELEMETRY_DONATION_POINTS,
                                            f"Transferência (reincidência #{hit_count}): {d_member.name} doou {d_amount} e {r_member.name} recebeu {r_amount} simultaneamente.",
                                            "Economia de Tropas"
                                        )

            self.last_clan_state = current_state

            # RADAR DE GUERRA (janela mais curta: 30s entre ataques)
            try:
                war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
                if war and war.state == "inWar":
                    my_clan = war.clan if coc.utils.correct_tag(war.clan.tag) == coc.utils.correct_tag(self.bot.clan_tag) else war.opponent
                    current_attacks = {}
                    for m in my_clan.members:
                        for atk in m.attacks:
                            current_attacks[atk.attacker_tag] = now_ts

                    if self.last_war_attacks:
                        new_attackers = []
                        for tag, ts in current_attacks.items():
                            if tag not in self.last_war_attacks:
                                new_attackers.append((tag, ts))

                        for i in range(len(new_attackers)):
                            for j in range(i + 1, len(new_attackers)):
                                t1, ts1 = new_attackers[i]
                                t2, ts2 = new_attackers[j]
                                if abs(ts1 - ts2) <= self.WAR_SYNC_SECONDS:
                                    m1 = current_state.get(t1, {}).get("member")
                                    m2 = current_state.get(t2, {}).get("member")
                                    if m1 and m2 and m1.tag in clan_tags and m2.tag in clan_tags:
                                        await self._log_telemetry(
                                            m1, m2, self.TELEMETRY_WAR_POINTS,
                                            f"Ataques sincronizados em <{self.WAR_SYNC_SECONDS}s: {m1.name} e {m2.name} atacaram no mesmo intervalo.",
                                            "Sincronia Mutex"
                                        )

                    self.last_war_attacks.update(current_attacks)
            except Exception:
                pass

        except Exception:
            pass

    @behavior_monitor_task.before_loop
    async def before_behavior_monitor(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)

    # ==================== O CÉREBRO DE MACHINE LEARNING (PROCESSAMENTO) ====================

    def _analyze_donation_asymmetry(self, telemetry: Dict) -> Tuple[bool, float, str]:
        """Analisa se as doações entre o par são unidirecionais (alimentação) ou recíprocas."""
        logs = telemetry.get('logs', [])
        don_logs = [
            log for log in logs
            if (log.get("axis") if isinstance(log, dict) else "") == "Economia de Tropas"
        ]
        if len(don_logs) < 2:
            return False, 0.0, ""

        main_to_smurf = 0
        smurf_to_main = 0
        for log in don_logs:
            msg = log.get("msg", "") if isinstance(log, dict) else str(log)
            if "doou" in msg and "recebeu" in msg:
                main_to_smurf += 1
            elif "recebeu" in msg and "doou" in msg:
                smurf_to_main += 1

        total = main_to_smurf + smurf_to_main
        if total == 0:
            return False, 0.0, ""

        ratio = max(main_to_smurf, smurf_to_main) / total
        if ratio > 0.85 and total >= 3:
            direction = "main→smurf" if main_to_smurf > smurf_to_main else "smurf→main"
            return True, ratio, f"Doações unidirecionais ({direction}): {ratio:.0%} em {total} eventos — padrão de alimentação."
        return False, ratio, ""

    def _calculate_deviation_similarity(self, dev1: np.ndarray, dev2: np.ndarray) -> float:
        """Similaridade dos DESVIOS do clã. Se ambos se desviam no mesmo sentido, é suspeito."""
        n1, n2 = np.linalg.norm(dev1), np.linalg.norm(dev2)
        if n1 < 0.01 and n2 < 0.01:
            return 0.0
        if n1 < 0.01 or n2 < 0.01:
            return 0.0
        return float(np.dot(dev1, dev2) / (n1 * n2))

    def _run_ml_inference(self, p1: coc.Player, p2: coc.Player, telemetry: Dict) -> Optional[Dict]:
        """
        Motor de decisão final: XGBoost é o juiz primário.
        Regras Bayesianas são usadas apenas para:
        - Explicabilidade (thoughts)
        - Pseudo-labeling para cold start
        - Fallback quando o modelo não tem dados suficientes
        """
        v1 = self._extract_feature_vector(p1)
        v2 = self._extract_feature_vector(p2)
        t1 = self._extract_troop_profile(p1)
        t2 = self._extract_troop_profile(p2)
        a1 = self._extract_achievement_profile(p1)
        a2 = self._extract_achievement_profile(p2)
        h1 = self._extract_hero_equipment_fingerprint(p1)
        h2 = self._extract_hero_equipment_fingerprint(p2)

        if np.sum(v1) >= np.sum(v2):
            main_p, smurf_p = p1, p2
        else:
            main_p, smurf_p = p2, p1

        baseline = self._last_clan_baselines
        behavior_score = int(telemetry.get('score', 0))
        thoughts = []
        likelihood_ratios = [1.0]
        axis_count = 0
        pair_id = f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}"

        # ---- EIXO 1: Nome (z-score vs baseline do clã) ----
        sim = self._phonetic_lexical_analysis(main_p.name, smurf_p.name)
        if baseline and len(self._last_clan_players) >= 5:
            name_z = self._get_z_score(sim, baseline['name_mean'], baseline['name_std'])
            if name_z > 3.0 and sim >= self.MIN_FUZZY_RATIO:
                likelihood_ratios.append(25.0)
                axis_count += 1
                thoughts.append({"axis": "Nomes", "weight": "LR=25",
                    "text": f"Nomes extremamente similares para o clã (z={name_z:.1f}, sim={sim}%)."})
            elif name_z > 2.0 and sim >= self.MIN_FUZZY_RATIO:
                likelihood_ratios.append(8.0)
                axis_count += 1
                thoughts.append({"axis": "Nomes", "weight": "LR=8",
                    "text": f"Nomes anormalmente similares (z={name_z:.1f}, sim={sim}%)."})
        elif sim >= self.MIN_FUZZY_RATIO:
            likelihood_ratios.append(3.0)
            axis_count += 1
            thoughts.append({"axis": "Nomes", "weight": "LR=3",
                "text": f"Similaridade nominal: {sim}%."})

        # ---- EIXO 2: Vetor de Desvio do Clã ----
        if baseline and len(self._last_clan_players) >= 5:
            dev1 = self._compute_deviation_vector(v1, baseline['vec_mean'], baseline['vec_std'])
            dev2 = self._compute_deviation_vector(v2, baseline['vec_mean'], baseline['vec_std'])
            dev_cos = self._calculate_deviation_similarity(dev1, dev2)
            dev_mag1 = np.linalg.norm(dev1)
            dev_mag2 = np.linalg.norm(dev2)
            avg_dev_mag = (dev_mag1 + dev_mag2) / 2.0

            baseline_cos_sims = []
            vecs = [self._extract_feature_vector(p) for p in self._last_clan_players]
            for i in range(len(vecs)):
                for j in range(i + 1, len(vecs)):
                    d1 = self._compute_deviation_vector(vecs[i], baseline['vec_mean'], baseline['vec_std'])
                    d2 = self._compute_deviation_vector(vecs[j], baseline['vec_mean'], baseline['vec_std'])
                    baseline_cos_sims.append(self._calculate_deviation_similarity(d1, d2))

            dev_mean = np.mean(baseline_cos_sims) if baseline_cos_sims else 0.0
            dev_std = np.std(baseline_cos_sims) if baseline_cos_sims else 0.15
            dev_z = self._get_z_score(dev_cos, dev_mean, max(dev_std, 0.01))

            if dev_z > 3.0 and avg_dev_mag > 0.5:
                likelihood_ratios.append(18.0)
                axis_count += 1
                thoughts.append({"axis": "Desvio do Clã", "weight": "LR=18",
                    "text": f"Ambos fogem do padrão do clã no mesmo sentido (z={dev_z:.1f}, desvio médio={avg_dev_mag:.1f}σ). Suspeito."})
            elif dev_z > 2.0 and avg_dev_mag > 0.5:
                likelihood_ratios.append(5.0)
                axis_count += 1
                thoughts.append({"axis": "Desvio do Clã", "weight": "LR=5",
                    "text": f"Desvios anormalmente alinhados (z={dev_z:.1f}, mag={avg_dev_mag:.1f}σ)."})
            elif avg_dev_mag < 0.3:
                likelihood_ratios.append(0.3)
                thoughts.append({"axis": "Atenuante", "weight": "LR=0.3",
                    "text": f"Ambos conformam à média do clã (desvio médio={avg_dev_mag:.1f}σ). Legítimos."})
        else:
            cos_sim = self._calculate_cosine_similarity(v1, v2)
            if cos_sim > 0.95:
                likelihood_ratios.append(3.0)
                axis_count += 1
                thoughts.append({"axis": "Evolução", "weight": "LR=3",
                    "text": f"Similaridade base: {cos_sim*100:.1f}%."})

        # ---- EIXO 3: Perfil de Tropas ----
        troop_sim = self._calculate_cosine_similarity(t1, t2)
        if baseline and len(self._last_clan_players) >= 5:
            troop_z = self._get_z_score(troop_sim, baseline['troop_mean'], baseline['troop_std'])
            if troop_z > 3.0:
                likelihood_ratios.append(6.0)
                axis_count += 1
                thoughts.append({"axis": "Tropas", "weight": "LR=6",
                    "text": f"Padrão de tropas extremamente anômalo para o clã (z={troop_z:.1f}, cos={troop_sim:.2f})."})
            elif troop_z > 2.0:
                likelihood_ratios.append(2.5)
                axis_count += 1
                thoughts.append({"axis": "Tropas", "weight": "LR=2.5",
                    "text": f"Padrão de tropas anormalmente similar (z={troop_z:.1f}, cos={troop_sim:.2f})."})
            elif troop_z < -1.5:
                likelihood_ratios.append(0.4)
                thoughts.append({"axis": "Atenuante", "weight": "LR=0.4",
                    "text": f"Perfil de tropas abaixo da média do clã (z={troop_z:.1f}) — provavelmente legítimo."})
        elif troop_sim > 0.95:
            likelihood_ratios.append(1.5)
            axis_count += 1
            thoughts.append({"axis": "Tropas", "weight": "LR=1.5",
                "text": f"Similaridade de tropas base: {troop_sim*100:.1f}%."})

        # ---- EIXO 4: Fingerprint de Achievements ----
        ach_sim = self._calculate_cosine_similarity(a1, a2)
        if baseline and len(self._last_clan_players) >= 5:
            ach_z = self._get_z_score(ach_sim, baseline['ach_mean'], baseline['ach_std'])
            if ach_z > 3.0:
                likelihood_ratios.append(6.0)
                axis_count += 1
                thoughts.append({"axis": "Achievements", "weight": "LR=6",
                    "text": f"DNA de achievements extremamente anômalo para o clã (z={ach_z:.1f}, cos={ach_sim:.2f})."})
            elif ach_z > 2.0:
                likelihood_ratios.append(2.5)
                axis_count += 1
                thoughts.append({"axis": "Achievements", "weight": "LR=2.5",
                    "text": f"DNA de achievements anormalmente similar (z={ach_z:.1f}, cos={ach_sim:.2f})."})
            elif ach_z < -1.5:
                likelihood_ratios.append(0.4)
                thoughts.append({"axis": "Atenuante", "weight": "LR=0.4",
                    "text": f"Perfil de achievements abaixo da média do clã (z={ach_z:.1f}) — provavelmente legítimo."})
        elif ach_sim > 0.97:
            likelihood_ratios.append(1.5)
            axis_count += 1
            thoughts.append({"axis": "Achievements", "weight": "LR=1.5",
                "text": f"Similaridade de achievements base: {ach_sim*100:.1f}%."})

        # ---- EIXO 5: Hero Equipment Fingerprint ----
        h_sim = self._calculate_cosine_similarity(h1, h2)
        if baseline and len(self._last_clan_players) >= 5:
            h_sims_baseline = []
            for p in self._last_clan_players:
                hp = self._extract_hero_equipment_fingerprint(p)
                h_sims_baseline.append(self._calculate_cosine_similarity(h1, hp))
            h_std_baseline = np.std(h_sims_baseline) if len(h_sims_baseline) > 2 else 0.15
            h_z = self._get_z_score(h_sim, np.mean(h_sims_baseline), max(h_std_baseline, 0.01))
            if h_z > 3.0:
                likelihood_ratios.append(14.0)
                axis_count += 1
                thoughts.append({"axis": "Equipamentos", "weight": "LR=14",
                    "text": f"Fingerprint de equipamentos quase idêntico (z={h_z:.1f}, cos={h_sim:.2f}). Altamente suspeito."})
            elif h_z > 2.0:
                likelihood_ratios.append(5.0)
                axis_count += 1
                thoughts.append({"axis": "Equipamentos", "weight": "LR=5",
                    "text": f"Equipamentos anormalmente similares (z={h_z:.1f}, cos={h_sim:.2f})."})
        elif h_sim > 0.9:
            likelihood_ratios.append(4.0)
            axis_count += 1
            thoughts.append({"axis": "Equipamentos", "weight": "LR=4",
                "text": f"Similaridade de equipamentos base: {h_sim*100:.1f}%."})

        # ---- EIXO 6: Isolation Forest (individual) ----
        if_main = self._get_isolation_forest_score(main_p)
        if_smurf = self._get_isolation_forest_score(smurf_p)
        if if_main > 0.6 and if_smurf > 0.6:
            likelihood_ratios.append(12.0)
            axis_count += 1
            thoughts.append({"axis": "Outlier IF", "weight": "LR=12",
                "text": f"Ambas contas fogem do padrão do clã (main={if_main:.0%}, smurf={if_smurf:.0%})."})
        elif if_smurf > 0.7:
            likelihood_ratios.append(4.0)
            axis_count += 1
            thoughts.append({"axis": "Outlier IF", "weight": "LR=4",
                "text": f"Conta secundária foge do padrão do clã (score={if_smurf:.0%})."})

        # ---- EIXO 7: Isolation Forest (par) ----
        pair_if = self._get_pair_isolation_forest_score(p1, p2)
        if pair_if > 0.7:
            likelihood_ratios.append(10.0)
            axis_count += 1
            thoughts.append({"axis": "Par Anômalo", "weight": "LR=10",
                "text": f"O par como um todo é anômalo (score={pair_if:.0%})."})

        # ---- EIXO 8: Mula ----
        is_mula, mula_score, mula_reason = self._analyze_mula_signature(smurf_p)
        if is_mula:
            likelihood_ratios.append(7.0)
            axis_count += 1
            thoughts.append({"axis": "Mula", "weight": "LR=7", "text": mula_reason})

        # ---- EIXO 9: Telemetria ----
        telemetry_logs = telemetry.get('logs', [])
        has_war_sync = any(
            (log.get("axis") if isinstance(log, dict) else "") == "Sincronia Mutex"
            for log in telemetry_logs
        )
        is_asymmetric, asym_ratio, asym_reason = self._analyze_donation_asymmetry(telemetry)

        if behavior_score > 25 and has_war_sync:
            likelihood_ratios.append(12.0)
            axis_count += 1
            thoughts.append({"axis": "Telemetria", "weight": "LR=12",
                "text": f"Score: {behavior_score} — guerra E doações sincronizadas. Padrão forte de mutex."})
        elif behavior_score > 25 and is_asymmetric:
            likelihood_ratios.append(8.0)
            axis_count += 1
            thoughts.append({"axis": "Telemetria", "weight": "LR=8",
                "text": f"Score: {behavior_score}. {asym_reason}"})
        elif behavior_score > 25:
            likelihood_ratios.append(4.0)
            axis_count += 1
            thoughts.append({"axis": "Telemetria", "weight": "LR=4",
                "text": f"Score de telemetria: {behavior_score} (apenas doações)."})
        elif behavior_score > 10 and has_war_sync:
            likelihood_ratios.append(5.0)
            axis_count += 1
            thoughts.append({"axis": "Telemetria", "weight": "LR=5",
                "text": f"Score: {behavior_score} com guerra sincronizada."})
        elif behavior_score > 15 and is_asymmetric:
            likelihood_ratios.append(3.0)
            axis_count += 1
            thoughts.append({"axis": "Telemetria", "weight": "LR=3",
                "text": f"Score: {behavior_score}. {asym_reason}"})
        elif behavior_score > 15:
            likelihood_ratios.append(1.5)
            axis_count += 1
            thoughts.append({"axis": "Telemetria", "weight": "LR=1.5",
                "text": f"Score de telemetria: {behavior_score} (doações)."})

        for log_entry in telemetry.get('logs', []):
            msg = log_entry.get("msg", "") if isinstance(log_entry, dict) else log_entry
            axis_lbl = log_entry.get("axis", "Log") if isinstance(log_entry, dict) else "Log"
            thoughts.append({"axis": axis_lbl, "weight": "Trace", "text": msg})

        # ---- Pseudo-label Bayesiano (para cold start + explainability) ----
        strong_axes = sum(1 for lr in likelihood_ratios if lr >= 3.0)
        bayesian_conf = self._calculate_bayesian_confidence(likelihood_ratios)
        evidence_count = axis_count

        if evidence_count < 1 and behavior_score < 10:
            return None
        if bayesian_conf >= 85 and strong_axes < 3:
            bayesian_conf = min(bayesian_conf, 84)

        # ---- EXTRAIR 26 FEATURES para o XGBoost ----
        pair_features_df = self._extract_pair_features(p1, p2, telemetry, baseline)
        feature_dict = pair_features_df.iloc[0].to_dict()

        # ---- VEREDITO FINAL: XGBoost (quando treinado) vs Bayes (cold start) ----
        if self._xgb_is_trained and self._xgb_model is not None:
            try:
                ml_prob = self._xgb_predict(pair_features_df)
                confidence = int(ml_prob * 100)
                evidence_count_str = f"ML ativo: {self._xgb_real_labels} labels reais"
                thoughts.append({"axis": "IA XGBoost", "weight": "Veredito Final",
                    "text": f"Probabilidade ML: {ml_prob:.0%}. Modelo treinado com {self._xgb_real_labels} casos reais."})
            except Exception:
                confidence = bayesian_conf
                thoughts.append({"axis": "IA XGBoost", "weight": "Fallback",
                    "text": "Erro na predição ML, usando fallback Bayesiano."})
        else:
            confidence = bayesian_conf
            if self._xgb_real_labels > 0:
                ml_status = f"({self._xgb_real_labels}/{self.XGB_MIN_REAL_LABELS} labels — aguardando mais dados)"
            else:
                ml_status = "sem dados de treinamento ainda"
            thoughts.append({"axis": "IA XGBoost", "weight": "Info",
                "text": f"Modo cold start ({ml_status}). Use Absolver/Condenar para treinar o modelo."})

        # ---- MIN-EVIDENCE: exige pelo menos 1 eixo forte pra reportar ----
        if strong_axes < 1 and behavior_score < 15:
            return None

        # ---- RISK LABELS: só acusar quando tem evidência real ----
        if self._xgb_is_trained and confidence >= 85:
            risk_label = "Risco Extremo"
            risk_color = "var(--color-danger)"
        elif self._xgb_is_trained and confidence >= 60:
            risk_label = "Alta Suspeita"
            risk_color = "var(--color-warning)"
        elif self._xgb_is_trained and confidence >= 30:
            risk_label = "Em Observação"
            risk_color = "var(--color-info)"
        elif not self._xgb_is_trained and strong_axes >= 3 and confidence >= 50:
            risk_label = "Suspeita Moderada (Cold Start)"
            risk_color = "var(--color-warning)"
        elif not self._xgb_is_trained and strong_axes >= 2 and confidence >= 40:
            risk_label = "Em Observação (Cold Start)"
            risk_color = "var(--color-info)"
        else:
            risk_label = "Baixa Confiança"
            risk_color = "var(--color-muted)"

        return {
            "pair_id": pair_id,
            "main_name": main_p.name, "main_tag": main_p.tag,
            "smurf_name": smurf_p.name, "smurf_tag": smurf_p.tag,
            "confidence": confidence,
            "risk_label": risk_label,
            "risk_color": risk_color,
            "thoughts": thoughts,
            "evidence_count": evidence_count,
            "strong_axes": strong_axes,
            "model_status": "trained" if self._xgb_is_trained else "cold_start",
        }

    # ==================== COMANDO DISCORD ====================

    @app_commands.command(name="smurfs", description="🕵️ Executa a Matriz Forense XAI no Clã.")
    @app_commands.default_permissions(administrator=True)
    async def slash_analyze_smurfs(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            if not clan: 
                return await interaction.followup.send("❌ Erro de comunicação com a Supercell.")

            member_tags = {m.tag for m in clan.members}
            telemetry_matrix = {}
            
            if self.db is not None:
                cursor = self.db.smurf_evidence.find({"score": {"$gt": 3}})
                async for doc in cursor: 
                    telemetry_matrix[doc["_id"]] = doc
                    if doc.get("tag1"): member_tags.add(doc.get("tag1"))
                    if doc.get("tag2"): member_tags.add(doc.get("tag2"))

            member_tags = {t for t in member_tags if t}
            if not member_tags:
                return await interaction.followup.send("✅ **Clã Limpo:** A XAI não detectou matrizes anômalas.")

            players_full = []
            async for p in self.bot.api_client.get_players(list(member_tags)):
                players_full.append(p)

            self._prepare_clan_baselines(clan.members, players_full)

            results = []
            processed = set()

            for i in range(len(players_full)):
                p1 = players_full[i]
                if p1.tag in processed: continue

                for j in range(i + 1, len(players_full)):
                    p2 = players_full[j]
                    if p2.tag in processed: continue

                    pair_id = f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}"
                    if pair_id in self._judged_pairs:
                        continue
                    telemetry = telemetry_matrix.get(pair_id)
                    
                    dossier = self._run_ml_inference(p1, p2, telemetry or {})
                    if dossier:
                        results.append(dossier)
                        processed.add(dossier["smurf_tag"])

            if not results:
                return await interaction.followup.send("✅ **Clã Limpo:** A Inteligência Artificial cruzou os dados e não detectou smurfs atuando.")

            results.sort(key=lambda x: x['confidence'], reverse=True)

            embed = discord.Embed(title="📂 XAI FORENSE: RELATÓRIO DO MOTOR DE INFERÊNCIA", description="Cruzamento via Dynamic Time Warping, Distância de Cossenos e Lógica Fuzzy.", color=0x2b2d31)
            
            for r in results[:5]: 
                body = f"👑 **[MAIN]** {r['main_name']} (`{r['main_tag']}`)\n👶 **[SMURF]** {r['smurf_name']} (`{r['smurf_tag']}`)\n\n"
                
                thoughts_text = "\n".join([f"▫️ `{t['axis']}`: {t['text']}" for t in r['thoughts']])
                if len(thoughts_text) > 750:
                    thoughts_text = thoughts_text[:750] + "...\n*[Laudo completo com histórico integral disponível no Painel Web]*"
                    
                body += "**🧠 Explicabilidade (Por que a IA acha isso?):**\n" + thoughts_text
                embed.add_field(name=f"Grau de Certeza: {r['confidence']}% - {r['risk_label']}", value=body, inline=False)
                
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro Crítico ML no Slash Command: {traceback.format_exc()}")
            await interaction.followup.send("❌ Erro fatal ao rodar a Matriz de Clusterização no Discord.")

    @app_commands.command(name="smurfs_cleanup", description="🧹 Limpa dados antigos do radar pericial (falsos positivos do sistema antigo).")
    @app_commands.default_permissions(administrator=True)
    async def slash_cleanup_smurfs(self, interaction: discord.Interaction):
        """Remove todos os registros de telemetria antigos e dados de aprendizado."""
        await interaction.response.defer(thinking=True)
        if self.db is None:
            return await interaction.followup.send("❌ Banco de dados offline.")

        try:
            ev_count = await self.db.smurf_evidence.count_documents({})
            train_count = await self.db.smurf_training.count_documents({})

            await self.db.smurf_evidence.delete_many({})
            await self.db.smurf_training.delete_many({})

            self._telemetry_cooldown.clear()
            self.last_clan_state.clear()
            self.last_war_attacks.clear()
            self._judged_pairs.clear()
            self._xgb_model = None
            self._xgb_is_trained = False
            self._xgb_real_labels = 0
            self._xgb_retrain_counter = 0

            await interaction.followup.send(
                f"🧹 **Radar Pericial limpo!**\n"
                f"- {ev_count} evidências antigas removidas\n"
                f"- {train_count} registros de treinamento removidos\n"
                f"- Modelo XGBoost resetado\n"
                f"- Cooldowns resetados\n\n"
                f"O novo sistema (v4.0 IA) vai começar do zero e aprender com seus feedbacks."
            )
        except Exception as e:
            logger.error(f"Erro no cleanup: {traceback.format_exc()}")
            await interaction.followup.send(f"❌ Erro ao limpar: {e}")

    # ==================== APIs PARA O PAINEL WEB (XAI EXPORT) ====================

    async def get_training_status(self) -> Dict[str, Any]:
        """Retorna o progresso de treino do XGBoost para o painel admin."""
        if self.db is None:
            return {"real_labels": 0, "real_labels_needed": self.XGB_MIN_REAL_LABELS,
                    "total_samples": 0, "total_samples_needed": self.XGB_MIN_TOTAL_SAMPLES,
                    "model_status": "unavailable"}
        try:
            total_samples = await self.db.smurf_training.count_documents({})
            real_labels = await self.db.smurf_training.count_documents({"real_label": {"$exists": True}})
            if self._xgb_is_trained:
                status = "trained"
            elif real_labels >= self.XGB_MIN_REAL_LABELS and total_samples >= self.XGB_MIN_TOTAL_SAMPLES:
                status = "ready"
            else:
                status = "cold_start"
            return {
                "real_labels": real_labels,
                "real_labels_needed": self.XGB_MIN_REAL_LABELS,
                "total_samples": total_samples,
                "total_samples_needed": self.XGB_MIN_TOTAL_SAMPLES,
                "model_status": status,
            }
        except Exception:
            return {"real_labels": 0, "real_labels_needed": self.XGB_MIN_REAL_LABELS,
                    "total_samples": 0, "total_samples_needed": self.XGB_MIN_TOTAL_SAMPLES,
                    "model_status": "error"}

    async def get_web_dossier(self) -> List[Dict[str, Any]]:
        """API Web Segura: Escaneia o banco e a Supercell sem travar."""
        if self.db is None or not self.bot.api_client: return []
            
        try:
            telemetry_matrix = {}
            member_tags = set()
            
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            current_member_tags = set()
            if clan:
                for m in clan.members:
                    member_tags.add(m.tag)
                    current_member_tags.add(m.tag)
            
            cursor = self.db.smurf_evidence.find({"score": {"$gt": 10}}) 
            async for doc in cursor: 
                telemetry_matrix[doc["_id"]] = doc
                if doc.get("tag1"): member_tags.add(doc.get("tag1"))
                if doc.get("tag2"): member_tags.add(doc.get("tag2"))
            
            member_tags = {t for t in member_tags if t}
            if not member_tags: return []
            
            players_full = []
            async for p in self.bot.api_client.get_players(list(member_tags)):
                players_full.append(p)
            
            if len(players_full) < 2: return []

            if clan:
                self._prepare_clan_baselines(clan.members, players_full)

            xai_res = []
            processed = set()
            
            for i in range(len(players_full)):
                p1 = players_full[i]
                if p1.tag in processed: continue
                
                for j in range(i + 1, len(players_full)):
                    p2 = players_full[j]
                    if p2.tag in processed: continue
                    
                    if p1.tag not in current_member_tags and p2.tag not in current_member_tags:
                        continue
                    
                    pair_id = f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}"
                    if pair_id in self._judged_pairs:
                        continue
                    telemetry = telemetry_matrix.get(pair_id)
                    
                    if telemetry or self._phonetic_lexical_analysis(p1.name, p2.name) >= self.MIN_FUZZY_RATIO:
                        dossier = self._run_ml_inference(p1, p2, telemetry or {})
                        if dossier:
                            xai_res.append(dossier)
                            processed.add(dossier["smurf_tag"])
                            
            xai_res.sort(key=lambda x: x['confidence'], reverse=True)
            return xai_res
            
        except Exception as e:
            logger.error(f"Erro crítico na XAI Web: {traceback.format_exc()}")
            return []

    # ==================== BOTÕES DO PAINEL ====================
    async def absolve_pair(self, pair_id: str) -> Dict[str, str]:
        if self.db is None: return {"status": "error", "message": "Banco offline."}
        try:
            doc = await self.db.smurf_evidence.find_one({"_id": pair_id})
            if doc:
                await self.db.smurf_evidence.delete_one({"_id": pair_id})
                await self.db.smurf_training.update_one(
                    {"_id": pair_id},
                    {"$set": {
                        "real_label": 0,
                        "real_weight": 1.0,
                        "updated_at": datetime.datetime.now(pytz.utc),
                    }},
                    upsert=True
                )
                self._judged_pairs.add(pair_id)
                self._xgb_retrain_counter += 1
                self._xgb_real_labels += 1
                await self._train_xgb_from_db()
                return {"status": "success", "message": "Absolvido! IA registrou como falso positivo e recalibrou o modelo ML."}
            return {"status": "error", "message": "Evidência não encontrada no banco."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def condemn_pair(self, pair_id: str) -> Dict[str, str]:
        if self.db is None: return {"status": "error", "message": "Banco offline."}
        w_cog = self.bot.get_cog("Lista de Observação")
        if not w_cog: return {"status": "error", "message": "Módulo de Watchlist desativado."}

        try:
            doc = await self.db.smurf_evidence.find_one({"_id": pair_id})
            if not doc: return {"status": "error", "message": "Dossiê não encontrado no Banco."}

            # --- NOVO: Puxar os nomes reais da API da Supercell ---
            name1, name2 = "Desconhecido", "Desconhecido"
            if self.bot.api_client:
                try:
                    p1 = await self.bot.api_client.get_player(doc['tag1'])
                    name1 = p1.name
                except Exception: pass
                try:
                    p2 = await self.bot.api_client.get_player(doc['tag2'])
                    name2 = p2.name
                except Exception: pass

            reason = "Condenado pela IA XAI (Contas Vinculadas)"

            await w_cog.add_to_watchlist(doc['tag1'], name1, reason, f"Vinculado a {name2} ({doc['tag2']})")
            await w_cog.add_to_watchlist(doc['tag2'], name2, reason, f"Vinculado a {name1} ({doc['tag1']})")

            await self.db.smurf_evidence.delete_one({"_id": pair_id})
            await self.db.smurf_training.update_one(
                {"_id": pair_id},
                {"$set": {
                    "real_label": 1,
                    "real_weight": 1.0,
                    "updated_at": datetime.datetime.now(pytz.utc),
                }},
                upsert=True
            )

            self._judged_pairs.add(pair_id)
            self._xgb_retrain_counter += 1
            self._xgb_real_labels += 1
            await self._train_xgb_from_db()
            return {"status": "success", "message": "Contas enviadas para a Watchlist com sucesso. IA recalibrada."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

async def setup(bot: commands.Bot):
    await bot.add_cog(SmurfDetectionCog(bot))
