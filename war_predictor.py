# -*- coding: utf-8 -*-
# Versão 20.1.63-UI-IMPROVEMENTS - Melhorias na interface do painel.

import logging
import math
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

# --- Estrutura de Dados para as Features da IA ---

@dataclass
class WarFeatures:
    """Estrutura para organizar as características (features) da guerra para o modelo de ML."""
    star_difference: float
    destruction_difference: float
    attacks_remaining_difference: int
    town_hall_advantage: float
    efficiency_ratio: float
    three_star_rate_difference: float
    war_progress_percentage: float
    historical_win_rate: float
    unused_member_strength_diff: float

# --- Classe Principal da IA ---

class AdvancedWarMLPredictor:
    """
    Sistema avançado de Machine Learning para previsão de resultados de guerras no Clash of Clans.
    Esta classe é responsável por extrair dados, treinar um modelo e gerar previsões.
    """
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self.logger = logging.getLogger("advanced_war_ml")
        if not self.logger.handlers:
            self.logger.addHandler(logging.StreamHandler())
            self.logger.setLevel(logging.INFO)
            
        self.model = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        self.scaler = StandardScaler() 
        self.analysis_log = {}

    async def predict_war_outcome(self, war, clan_tag) -> Dict[str, Any]:
        """
        Ponto de entrada principal para gerar uma predição de guerra.
        """
        try:
            self.analysis_log = {} 
            if war.state != 'inWar':
                return {"summary": "A guerra não está em andamento para previsões.", "probability": 0, "confidence": 0}

            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan

            definitive_scenario = self._check_definitive_scenarios(war, our_clan, opponent)
            if definitive_scenario:
                self.analysis_log['method'] = "Cenário Definitivo"
                self.analysis_log['reason'] = definitive_scenario['summary']
                definitive_scenario['analysis_log'] = self.analysis_log
                return definitive_scenario
            
            features = await self._extract_war_features(war, our_clan, opponent)
            if features is None:
                 return {"summary": "Aguardando dados completos da guerra para iniciar a análise...", "probability": 0, "confidence": 0}

            feature_vector = np.array(list(features.__dict__.values())).reshape(1, -1)
            
            historical_data = await self._load_historical_training_data()
            
            win_probability = 50.0 
            
            if len(historical_data) >= 10:
                try:
                    self.analysis_log['method'] = f"Modelo ML treinado com {len(historical_data)} guerras"
                    X = np.array([list(d['features'].__dict__.values()) for d in historical_data])
                    y = np.array([d['result'] for d in historical_data])
                    
                    X_scaled = self.scaler.fit_transform(X)
                    self.model.fit(X_scaled, y)
                    
                    feature_vector_scaled = self.scaler.transform(feature_vector)
                    prediction = self.model.predict(feature_vector_scaled)[0]
                    win_probability = np.clip(prediction * 100, 1, 99)
                except Exception as ml_error:
                    self.analysis_log['method'] = "Heurístico (Fallback de ML)"
                    self.logger.warning(f"Erro no ML, usando heurística. Erro: {ml_error}")
                    win_probability = self._heuristic_prediction(features)
            else:
                self.analysis_log['method'] = f"Heurístico ({len(historical_data)}/10 guerras no histórico)"
                self.logger.info(f"Dados históricos insuficientes. Usando predição heurística.")
                win_probability = self._heuristic_prediction(features)

            confidence = 50 + (features.war_progress_percentage / 2)
            
            total_attacks_per_team = war.team_size * war.attacks_per_member
            final_result = self._generate_final_message(win_probability, confidence, features, our_clan, opponent, total_attacks_per_team, war.state)
            self.analysis_log['final_prediction'] = final_result['summary_discord'] # Log para o Discord
            final_result['analysis_log'] = self.analysis_log
            return final_result

        except Exception as e:
            self.logger.error(f"Erro na predição ML avançada: {e}", exc_info=True)
            return {"summary": f"Erro na análise preditiva: {type(e).__name__}", "probability": 0, "confidence": 0}

    def _check_definitive_scenarios(self, war, our_clan, opponent) -> Optional[Dict[str, Any]]:
        """Verifica se o resultado da guerra já está matematicamente decidido."""
        our_rem = (war.team_size * war.attacks_per_member) - our_clan.attacks_used
        opp_rem = (war.team_size * war.attacks_per_member) - opponent.attacks_used

        message = None
        if our_rem == 0 and (our_clan.stars < opponent.stars or (our_clan.stars == opponent.stars and our_clan.destruction < opponent.destruction)):
            message = f"Derrota confirmada. {our_clan.name} usou todos os ataques e não pode mais virar."
        if opp_rem == 0 and (our_clan.stars > opponent.stars or (our_clan.stars == opponent.stars and our_clan.destruction > opponent.destruction)):
            message = f"Vitória garantida! O oponente não tem mais ataques."
        if (our_clan.stars + our_rem * 3) < opponent.stars:
            message = "A derrota é matematicamente inevitável."
        if our_clan.stars > (opponent.stars + opp_rem * 3):
            message = f"Vitória garantida! O oponente não pode mais nos alcançar."

        if message:
            return {"summary": message, "probability": 0 if our_clan.stars < opponent.stars else 100, "confidence": 100}
        return None

    async def _extract_war_features(self, war, our_clan, opponent) -> Optional[WarFeatures]:
        """Coleta e calcula todas as métricas (features) da guerra atual."""
        try:
            total_attacks = war.team_size * war.attacks_per_member
            our_attacks = [a for a in war.attacks if getattr(getattr(a, 'attacker', None), 'clan', None) and a.attacker.clan.tag == our_clan.tag]
            opp_attacks = [a for a in war.attacks if getattr(getattr(a, 'attacker', None), 'clan', None) and a.attacker.clan.tag == opponent.tag]

            our_efficiency = self._calculate_attack_efficiency(our_attacks)
            opp_efficiency = self._calculate_attack_efficiency(opp_attacks)
            
            our_3star_rate = sum(1 for a in our_attacks if a.stars == 3) / max(len(our_attacks), 1)
            opp_3star_rate = sum(1 for a in opp_attacks if a.stars == 3) / max(len(opp_attacks), 1)
            
            our_unused_strength, opp_unused_strength = self._calculate_unused_strength(war, our_clan, opponent)
            
            historical_data = await self._get_clan_historical_performance(our_clan.tag)

            our_th_sum = sum(getattr(m, 'town_hall', 0) for m in our_clan.members if m)
            opp_th_sum = sum(getattr(m, 'town_hall', 0) for m in opponent.members if m)

            features = WarFeatures(
                star_difference=our_clan.stars - opponent.stars,
                destruction_difference=our_clan.destruction - opponent.destruction,
                attacks_remaining_difference=(total_attacks - our_clan.attacks_used) - (total_attacks - opponent.attacks_used),
                town_hall_advantage=our_th_sum - opp_th_sum,
                efficiency_ratio=our_efficiency / max(opp_efficiency, 0.01),
                three_star_rate_difference=our_3star_rate - opp_3star_rate,
                war_progress_percentage=(len(our_attacks) + len(opp_attacks)) / max((total_attacks * 2), 1) * 100,
                historical_win_rate=historical_data.get('win_rate', 50),
                unused_member_strength_diff=our_unused_strength - opp_unused_strength
            )
            self.analysis_log['features'] = features.__dict__ # Log features
            return features
        except (AttributeError, TypeError) as e:
            self.logger.warning(f"Aguardando dados da guerra se estabilizarem. Erro: {e}")
            return None 

    def _calculate_attack_efficiency(self, attacks: List) -> float:
        """Calcula a eficiência média de um conjunto de ataques."""
        if not attacks: return 1.0
        return sum(a.stars + a.destruction / 100 for a in attacks) / len(attacks)

    def _calculate_unused_strength(self, war, our_clan, opponent):
        """Calcula a 'força' (soma de CVs) dos jogadores que ainda não atacaram."""
        our_attackers_left = [m for m in our_clan.members if m and len(m.attacks) < war.attacks_per_member]
        opp_attackers_left = [m for m in opponent.members if m and len(m.attacks) < war.attacks_per_member]
        our_strength = sum(getattr(m, 'town_hall', 0) for m in our_attackers_left)
        opp_strength = sum(getattr(m, 'town_hall', 0) for m in opp_attackers_left)
        return our_strength, opp_strength

    async def _load_historical_training_data(self) -> List[Dict]:
        """Carrega os dados de guerras passadas do banco de dados."""
        if self.db is None: return []
        try:
            cursor = self.db.war_history.find({}).sort("war_data.end_time_iso", -1).limit(50)
            processed_wars = []
            async for doc in cursor:
                processed = self._process_historical_war(doc)
                if processed:
                    processed_wars.append(processed)
            return processed_wars
        except Exception as e:
            self.logger.error(f"Erro ao carregar dados históricos: {e}")
            return []

    def _process_historical_war(self, doc: Dict) -> Optional[Dict]:
        """Transforma um documento do banco de dados em um formato útil para o ML."""
        try:
            wd = doc.get('war_data', {})
            our_clan_members = doc.get('our_clan_members_in_war', [])
            opp_clan_members = doc.get('opponent_clan_members_in_war', [])
            
            if not all([wd, our_clan_members, opp_clan_members]): return None

            result = 1 if wd['clan_stars'] > wd['opponent_stars'] else 0

            our_th_sum = sum(m.get('townhall', 0) for m in our_clan_members)
            opp_th_sum = sum(m.get('townhall', 0) for m in opp_clan_members)

            features = WarFeatures(
                 star_difference=wd['clan_stars'] - wd['opponent_stars'],
                 destruction_difference=float(wd['clan_destruction'][:-1]) - float(wd['opponent_destruction'][:-1]),
                 attacks_remaining_difference=0,
                 town_hall_advantage=our_th_sum - opp_th_sum,
                 efficiency_ratio=float(wd.get('clan_avg_stars', '1.0')) / max(float(wd.get('opponent_avg_stars', '1.0')), 0.01),
                 three_star_rate_difference=wd.get('clan_star_distribution', {}).get('3', 0) / max(wd.get('clan_attacks_used', 1), 1) - wd.get('opponent_star_distribution', {}).get('3', 0) / max(wd.get('opponent_attacks_used', 1), 1),
                 war_progress_percentage=100.0,
                 historical_win_rate=50.0,
                 unused_member_strength_diff=0.0
            )
            return {'features': features, 'result': result}
        except (KeyError, TypeError, ValueError) as e:
            self.logger.debug(f"Skipping historical war due to missing data: {e}")
            return None

    async def _get_clan_historical_performance(self, clan_tag: str) -> Dict:
        """Calcula a taxa de vitórias do clã com base no histórico."""
        if self.db is None: return {'win_rate': 50.0}
        try:
            total_wars = await self.db.war_history.count_documents({"war_data.clan_tag": clan_tag})
            if total_wars < 5: return {'win_rate': 50.0}
            wins = await self.db.war_history.count_documents({
                "war_data.clan_tag": clan_tag, 
                "$expr": {"$gt": ["$war_data.clan_stars", "$war_data.opponent_stars"]}
            })
            return {'win_rate': (wins / total_wars) * 100}
        except Exception:
             return {'win_rate': 50.0}

    def _heuristic_prediction(self, features: WarFeatures) -> float:
        """Define uma previsão baseada em um sistema de pontuação, caso o ML não possa ser usado."""
        score = 50.0
        score += features.star_difference * 8
        score += features.destruction_difference * 0.2
        score += features.attacks_remaining_difference * 3
        score += (features.efficiency_ratio - 1) * 20
        score += features.town_hall_advantage * 0.1
        score += features.unused_member_strength_diff * 0.05
        return np.clip(score, 1, 99)

    def _generate_final_message(self, prob, confidence, features, our_clan, opponent, total_attacks_per_team, war_state):
        """Cria a mensagem final de predição, incluindo um conselho tático."""
        if prob >= 85: title = "🎯 Vitória Altamente Provável"
        elif prob >= 65: title = "✅ Vantagem Clara"
        elif prob >= 55: title = "⚖️ Ligeira Vantagem"
        elif prob <= 15: title = "🚨 Situação Crítica"
        elif prob <= 35: title = "⚠️ Desvantagem Clara"
        else: title = "🔄 Guerra em Equilíbrio"

        details = ""
        star_diff = features.star_difference
        if star_diff < 0:
            stars_needed = abs(int(star_diff)) + 1
            details = f"Para virar, {our_clan.name} precisa de {stars_needed}★ a mais que o oponente."
        elif star_diff > 0:
            stars_needed_opp = int(star_diff) + 1
            details = f"{opponent.name} ainda pode virar se conseguir {stars_needed_opp}★ a mais."
        else: 
            details = "A guerra está empatada em estrelas."
        
        tactical_advice = ""
        our_rem_attacks = total_attacks_per_team - our_clan.attacks_used
        if str(war_state) == 'inWar' and prob < 65 and our_rem_attacks > 0:
            if star_diff < 0:
                tactical_advice = "A virada é possível! Precisamos de ataques de 3 estrelas."
            else:
                 tactical_advice = "Manter a consistência nos ataques garantirá a vitória."
        elif prob >= 85:
            tactical_advice = "Administrar a vantagem é a chave. Ataques seguros para garantir estrelas."

        # Retorna um dicionário com as informações separadas
        return {
            "summary_panel": f"{title}. {details}", # Mensagem curta para o painel
            "summary_discord": f"{title}. {details} {tactical_advice}".strip(), # Mensagem para o Discord
            "probability": prob,
            "confidence": confidence
        }
