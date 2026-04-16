# -*- coding: utf-8 -*-
"""
Sistema Avançado de Machine Learning para Predição de Guerras - ClashGenius v4.0
Arquitetura modular com ensemble learning, feature engineering avançada e aprendizado contínuo.
Atualizado com Geração de Linguagem Natural Dinâmica (NLG) para relatórios orgânicos.
"""

import logging
import math
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict, Counter

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.preprocessing import StandardScaler

# ================== ESTRUTURAS DE DADOS ==================

@dataclass
class AdvancedWarFeatures:
    """Features expandidas com engenharia sofisticada"""
    # Features básicas
    star_difference: float
    destruction_difference: float
    attacks_remaining_difference: int
    town_hall_advantage: float
    efficiency_ratio: float
    three_star_rate_difference: float
    war_progress_percentage: float
    historical_win_rate: float
    unused_member_strength_diff: float
    
    # Features temporais e de timing
    momentum_indicator: float = 0.5 # Tendência dos últimos ataques
    
    # Features de coordenação
    clan_synergy_score: float = 0.5 # Eficiência em cleanups
    
    # Features psicológicas
    pressure_index: float = 0.0 # Nível de pressão sobre nosso clã

# ================== FEATURE ENGINEERING ==================

class AdvancedFeatureEngineer:
    """Sistema de engenharia de features para extrair métricas avançadas da guerra."""
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self.logger = logging.getLogger("feature_engineer")

    async def extract_all_features(self, war: Any, our_clan: Any, opponent: Any, clan_tag: str) -> Optional[AdvancedWarFeatures]:
        """Ponto de entrada para extração de todas as features."""
        try:
            # Extrai as features básicas
            basic_features = self._extract_basic_features(war, our_clan, opponent)
            
            # Extrai features temporais
            temporal_features = self._extract_temporal_features(war, our_clan, opponent)
            
            # Extrai features de coordenação
            coordination_features = self._extract_coordination_features(war, our_clan)
            
            # Extrai features psicológicas
            psychological_features = self._extract_psychological_features(war, our_clan, opponent)

            # Busca o histórico de vitórias
            historical_win_rate = await self._get_historical_win_rate(clan_tag)
            
            # Combina tudo em um objeto
            all_features = {
                **basic_features,
                **temporal_features,
                **coordination_features,
                **psychological_features,
                'historical_win_rate': historical_win_rate
            }
            
            return AdvancedWarFeatures(**all_features)

        except Exception as e:
            self.logger.error(f"Erro na extração de features: {e}", exc_info=True)
            return None

    def _extract_basic_features(self, war: Any, our_clan: Any, opponent: Any) -> Dict[str, float]:
        """Extrai as features básicas e essenciais da guerra."""
        total_attacks = war.team_size * war.attacks_per_member
        our_attacks = [a for a in war.attacks if getattr(a, 'attacker', None) and a.attacker.clan.tag == our_clan.tag]
        opp_attacks = [a for a in war.attacks if getattr(a, 'attacker', None) and a.attacker.clan.tag == opponent.tag]

        our_efficiency = self._calculate_attack_efficiency(our_attacks)
        opp_efficiency = self._calculate_attack_efficiency(opp_attacks)
        
        our_3star_rate = sum(1 for a in our_attacks if a.stars == 3) / max(len(our_attacks), 1)
        opp_3star_rate = sum(1 for a in opp_attacks if a.stars == 3) / max(len(opp_attacks), 1)
        
        our_unused_strength, opp_unused_strength = self._calculate_unused_strength(war, our_clan, opponent)

        return {
            'star_difference': float(our_clan.stars - opponent.stars),
            'destruction_difference': float(our_clan.destruction - opponent.destruction),
            'attacks_remaining_difference': (total_attacks - our_clan.attacks_used) - (total_attacks - opponent.attacks_used),
            'town_hall_advantage': sum(m.town_hall for m in our_clan.members) - sum(m.town_hall for m in opponent.members),
            'efficiency_ratio': our_efficiency / max(opp_efficiency, 0.01),
            'three_star_rate_difference': our_3star_rate - opp_3star_rate,
            'war_progress_percentage': (len(our_attacks) + len(opp_attacks)) / max((total_attacks * 2), 1) * 100,
            'unused_member_strength_diff': our_unused_strength - opp_unused_strength,
        }

    def _extract_temporal_features(self, war: Any, our_clan: Any, opponent: Any) -> Dict[str, float]:
        """Extrai features relacionadas ao 'momentum' da guerra."""
        our_attacks = sorted([a for a in war.attacks if a.attacker.clan.tag == our_clan.tag], key=lambda a: a.order)
        opp_attacks = sorted([a for a in war.attacks if a.attacker.clan.tag == opponent.tag], key=lambda a: a.order)

        return {'momentum_indicator': self._calculate_momentum_indicator(our_attacks, opp_attacks)}

    def _extract_coordination_features(self, war: Any, our_clan: Any) -> Dict[str, float]:
        """Extrai features sobre a sinergia e coordenação do clã."""
        our_attacks = [a for a in war.attacks if a.attacker.clan.tag == our_clan.tag]
        return {'clan_synergy_score': self._calculate_clan_synergy(our_attacks)}

    def _extract_psychological_features(self, war: Any, our_clan: Any, opponent: Any) -> Dict[str, float]:
        """Extrai features que medem a pressão sobre o clã."""
        return {'pressure_index': self._calculate_pressure_index(war, our_clan, opponent)}
        
    async def _get_historical_win_rate(self, clan_tag: str) -> float:
        """Busca a taxa de vitória histórica do clã no banco de dados."""
        if self.db is None: return 50.0
        try:
            total_wars = await self.db.war_history.count_documents({"war_data.clan_tag": clan_tag})
            if total_wars < 5: return 50.0
            wins = await self.db.war_history.count_documents({
                "war_data.clan_tag": clan_tag, 
                "$expr": {"$gt": ["$war_data.clan_stars", "$war_data.opponent_stars"]}
            })
            return (wins / total_wars) * 100
        except Exception:
            return 50.0

    # --- Métodos Auxiliares de Cálculo de Features ---
    def _calculate_attack_efficiency(self, attacks: List[Any]) -> float:
        if not attacks: return 1.0
        return sum(a.stars + a.destruction / 100 for a in attacks) / len(attacks)

    def _calculate_unused_strength(self, war: Any, our_clan: Any, opponent: Any) -> Tuple[float, float]:
        our_attackers_left = [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member]
        opp_attackers_left = [m for m in opponent.members if len(m.attacks) < war.attacks_per_member]
        return sum(m.town_hall for m in our_attackers_left), sum(m.town_hall for m in opp_attackers_left)

    def _calculate_momentum_indicator(self, our_attacks: List[Any], opp_attacks: List[Any]) -> float:
        """Calcula o momentum baseado nos últimos 5 ataques de cada clã."""
        if not our_attacks and not opp_attacks: return 0.5
        
        recent_our_perf = np.mean([a.stars for a in our_attacks[-5:]]) if our_attacks else 0
        recent_opp_perf = np.mean([a.stars for a in opp_attacks[-5:]]) if opp_attacks else 0
        
        total_perf = recent_our_perf + recent_opp_perf
        return recent_our_perf / total_perf if total_perf > 0 else 0.5
        
    def _calculate_clan_synergy(self, our_attacks: List[Any]) -> float:
        """Mede a eficiência em ataques de limpeza (cleanups)."""
        attacks_by_base = defaultdict(list)
        for attack in our_attacks:
            attacks_by_base[attack.defender_tag].append(attack)
            
        cleanups = 0
        successful_cleanups = 0
        for base_tag, attacks in attacks_by_base.items():
            if len(attacks) > 1:
                first_attack_stars = attacks[0].stars
                for cleanup_attack in attacks[1:]:
                    cleanups += 1
                    if cleanup_attack.stars > first_attack_stars:
                        successful_cleanups += 1
        
        return successful_cleanups / cleanups if cleanups > 0 else 0.5
        
    def _calculate_pressure_index(self, war: Any, our_clan: Any, opponent: Any) -> float:
        """Calcula um índice de pressão sobre nosso clã."""
        star_diff_normalized = (opponent.stars - our_clan.stars) / max(war.team_size, 1)
        progress_factor = (our_clan.attacks_used + opponent.attacks_used) / max(war.team_size * war.attacks_per_member * 2, 1)
        
        pressure = (star_diff_normalized * 0.6) + (progress_factor * 0.4)
        return np.clip(pressure, 0, 1)


# ================== SISTEMA DE MODELOS ==================

class EnsembleMLSystem:
    """Sistema de ensemble que combina múltiplos modelos de ML para maior precisão."""
    
    def __init__(self):
        self.logger = logging.getLogger("ensemble_ml")
        self.models = {
            'gbr': GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42),
            'rf': RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)
        }
        self.weights = {'gbr': 0.6, 'rf': 0.4}
        self.scaler = StandardScaler()
        self.is_trained = False

    def train(self, historical_data: List[Dict]):
        """Treina todos os modelos do ensemble com dados históricos."""
        if len(historical_data) < 10:
            self.logger.warning(f"Dados históricos insuficientes para treinar ({len(historical_data)}/10). O sistema usará heurística.")
            self.is_trained = False
            return
            
        try:
            # Garante que todas as features existam nos dados históricos
            feature_names = list(AdvancedWarFeatures.__annotations__.keys())
            X_list = []
            y_list = []

            for d in historical_data:
                feature_dict = asdict(d['features'])
                # Garante a ordem correta e valores padrão para features faltantes
                ordered_features = [feature_dict.get(name, 0.0) for name in feature_names]
                X_list.append(ordered_features)
                y_list.append(d['result'])

            X = np.array(X_list)
            y = np.array(y_list)

            if X.shape[0] == 0:
                self.logger.warning("Nenhum dado válido para treinamento após o processamento.")
                self.is_trained = False
                return

            X_scaled = self.scaler.fit_transform(X)
            
            for name, model in self.models.items():
                model.fit(X_scaled, y)
            
            self.is_trained = True
            self.logger.info(f"Ensemble de ML treinado com sucesso usando {len(historical_data)} guerras.")
        except Exception as e:
            self.logger.error(f"Erro durante o treinamento do ensemble: {e}", exc_info=True)
            self.is_trained = False


    def predict(self, features: AdvancedWarFeatures) -> float:
        """Realiza uma predição combinando os resultados do ensemble."""
        if not self.is_trained:
            return self._heuristic_prediction(features)

        try:
            feature_vector = np.array(list(asdict(features).values())).reshape(1, -1)
            feature_vector_scaled = self.scaler.transform(feature_vector)
            
            weighted_prediction = 0.0
            for name, model in self.models.items():
                prediction = model.predict(feature_vector_scaled)[0]
                weighted_prediction += self.weights[name] * prediction
            
            return np.clip(weighted_prediction * 100, 1, 99)
        except Exception as e:
            self.logger.warning(f"Erro na predição do ensemble, usando heurística. Erro: {e}")
            return self._heuristic_prediction(features)
    
    def _heuristic_prediction(self, features: AdvancedWarFeatures) -> float:
        """Fallback para uma predição baseada em regras caso o modelo não esteja treinado."""
        score = 50.0
        score += features.star_difference * 8
        score += features.destruction_difference * 0.2
        score += features.attacks_remaining_difference * 3
        score += (features.efficiency_ratio - 1) * 20
        score += (features.momentum_indicator - 0.5) * 10
        score -= features.pressure_index * 5
        
        return np.clip(score, 1, 99)

# ================== SISTEMA PRINCIPAL ==================

class WarPredictionSystemV3:
    """Sistema principal que integra a engenharia de features, o ML e a geração de explicações."""
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self.logger = logging.getLogger("war_prediction_v3")
        self.feature_engineer = AdvancedFeatureEngineer(db_connection)
        self.ml_system = EnsembleMLSystem()
        self.is_initialized = False

    async def initialize_system(self):
        """Carrega dados históricos e treina os modelos."""
        if self.is_initialized:
            return
        historical_data = await self._load_historical_data()
        self.ml_system.train(historical_data)
        self.is_initialized = True
        self.logger.info("Sistema de Predição v3.0 inicializado.")

    async def predict_war_outcome(self, war: Any, clan_tag: str) -> Dict[str, Any]:
        """Ponto de entrada principal para gerar uma análise completa da guerra."""
        if not self.is_initialized:
            await self.initialize_system()
        
        if not war or not hasattr(war, 'state') or war.state == 'notInWar':
            return {"summary_panel": "Nenhuma guerra ativa para análise.", "probability": 50.0, "confidence": 0.0}

        try:
            if not war.clan or not war.opponent:
                return {"summary_panel": "Dados da guerra incompletos.", "probability": 50.0, "confidence": 10.0}

            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan
            
            if war.state == 'preparation':
                 return {"summary_panel": "Análise preditiva ficará disponível quando o campo de batalha for aberto.", "probability": 50.0, "confidence": 20.0}
            
            definitive = self._check_definitive_scenarios(war, our_clan, opponent)
            if definitive:
                return definitive
            
            features = await self.feature_engineer.extract_all_features(war, our_clan, opponent, clan_tag)
            if features is None:
                return {"summary_panel": "Aguardando volume de dados balísticos para iniciar a inferência...", "probability": 50.0, "confidence": 10.0}

            probability = self.ml_system.predict(features)
            confidence, tactical_insights, risk_factors = self._generate_qualitative_analysis(features, probability)
            
            summaries = self._generate_summaries(features, probability, our_clan.name, tactical_insights, risk_factors)
            
            return {
                "probability": probability,
                "confidence": confidence,
                "summary_panel": summaries['panel'],
                "summary_discord": summaries['discord'],
                "tactical_insights": tactical_insights,
                "risk_factors": risk_factors,
                "analysis_log": {"features": asdict(features), "method": "Ensemble ML" if self.ml_system.is_trained else "Heurística"}
            }

        except Exception as e:
            self.logger.error(f"Erro fatal na predição: {e}", exc_info=True)
            return {"summary_panel": f"Erro na análise: {type(e).__name__}", "probability": 50.0, "confidence": 0.0}
    
    async def _load_historical_data(self) -> List[Dict]:
        """Carrega e processa dados históricos do MongoDB para treinamento."""
        if self.db is None: return []
        try:
            # Aumentado de 50 para 500 para permitir aprendizado profundo
            cursor = self.db.war_history.find({}).sort("war_data.end_time_iso", -1).limit(500)
            processed_wars = []
            async for doc in cursor:
                try:
                    features = AdvancedWarFeatures(
                        star_difference=doc['war_data']['clan_stars'] - doc['war_data']['opponent_stars'],
                        destruction_difference=float(doc['war_data']['clan_destruction'][:-1]) - float(doc['war_data']['opponent_destruction'][:-1]),
                        attacks_remaining_difference=0,
                        town_hall_advantage=sum(m['townhall'] for m in doc['our_clan_members_in_war']) - sum(m['townhall'] for m in doc['opponent_clan_members_in_war']),
                        efficiency_ratio=float(doc['war_data'].get('clan_avg_stars', 1.5)) / max(float(doc['war_data'].get('opponent_avg_stars', 1.5)), 0.1),
                        three_star_rate_difference=(doc['war_data']['clan_star_distribution']['3'] / max(doc['war_data']['clan_attacks_used'],1)) - (doc['war_data']['opponent_star_distribution']['3'] / max(doc['war_data']['opponent_attacks_used'],1)),
                        war_progress_percentage=100.0,
                        historical_win_rate=50.0,
                        unused_member_strength_diff=0.0,
                        momentum_indicator=0.5,
                        clan_synergy_score=0.5,
                        pressure_index=0.0
                    )
                    result = 1 if features.star_difference > 0 or (features.star_difference == 0 and features.destruction_difference > 0) else 0
                    processed_wars.append({'features': features, 'result': result})
                except (KeyError, TypeError, ValueError):
                    continue
            return processed_wars
        except Exception as e:
            self.logger.error(f"Erro ao carregar dados históricos: {e}")
            return []

    def _check_definitive_scenarios(self, war: Any, our_clan: Any, opponent: Any) -> Optional[Dict[str, Any]]:
        """Verifica se a guerra já tem um resultado matemático garantido."""
        our_rem = (war.team_size * war.attacks_per_member) - our_clan.attacks_used
        opp_rem = (war.team_size * war.attacks_per_member) - opponent.attacks_used

        if our_clan.stars > (opponent.stars + opp_rem * 3):
            return {"summary_panel": "Vitória matematicamente garantida!", "summary_discord": "Vitória matematicamente garantida!", "probability": 100.0, "confidence": 100.0}
        
        if (our_clan.stars + our_rem * 3) < opponent.stars:
            return {"summary_panel": "Derrota matematicamente inevitável.", "summary_discord": "Derrota matematicamente inevitável.", "probability": 0.0, "confidence": 100.0}
        
        return None

    def _generate_qualitative_analysis(self, features: AdvancedWarFeatures, probability: float) -> Tuple[float, List[str], List[str]]:
        """Extrai os dados matemáticos brutos para serem transformados em texto orgânico."""
        confidence = 50.0
        confidence += min(features.war_progress_percentage, 80) * 0.4
        confidence -= abs(probability - 50) * 0.2
        confidence = np.clip(confidence, 10, 95)
        
        insights = []
        if features.momentum_indicator > 0.55: 
            insights.append(f"o ritmo atual de estrelas sugere um forte 'momentum' a nosso favor (índice de {features.momentum_indicator:.2f})")
        elif features.momentum_indicator < 0.45:
            insights.append(f"nossa cadência de ataques desacelerou (momentum de {features.momentum_indicator:.2f})")
            
        if features.clan_synergy_score > 0.6: 
            insights.append(f"estamos operando com uma alta sinergia de {features.clan_synergy_score*100:.0f}% nas limpezas de mapa")
            
        if features.efficiency_ratio > 1.1:
            insights.append(f"a nossa eficiência de destruição por ataque está {(features.efficiency_ratio - 1)*100:.0f}% superior à do oponente")

        risks = []
        if features.attacks_remaining_difference < -1: 
            risks.append(f"o adversário ainda retém {abs(features.attacks_remaining_difference)} ataques a mais que nós na manga")
        if features.unused_member_strength_diff < -100: 
            risks.append("o peso bélico (Heróis e CVs) que o inimigo ainda não usou é preocupantemente maior que a nossa reserva atual")
        if features.pressure_index > 0.65: 
            risks.append(f"o sistema acusa uma pressão matemática severa ({features.pressure_index:.1f}/1.0) sobre os nossos próximos atacantes")

        return confidence, insights, risks

    def _generate_summaries(self, features: AdvancedWarFeatures, probability: float, our_clan_name: str, insights: List[str], risks: List[str]) -> Dict[str, str]:
        """Constrói uma narrativa orgânica, fluida e única baseada nas variáveis do Machine Learning."""
        
        prog = int(features.war_progress_percentage)
        prob = int(probability)
        star_diff = int(features.star_difference)
        dest_diff = features.destruction_difference
        
        # 1. Abertura Baseada no Progresso e ML
        if prog < 20:
            texto = f"A guerra ainda está no início ({prog}% de progresso), mas o modelo preditivo já projeta nossa chance de vitória em {prob}%. "
        elif prog > 85:
            texto = f"Entramos na reta final do confronto. Com os dados consolidados, a probabilidade atual de sairmos vitoriosos cravou em {prob}%. "
        else:
            texto = f"Com o campo de batalha em {prog}% de andamento, a Inteligência Artificial calcula {prob}% de chance de vitória para nós. "
            
        # 2. Leitura Real do Placar
        if star_diff > 0:
            texto += f"No momento, sustentamos uma vantagem de {star_diff} estrelas. "
        elif star_diff < 0:
            texto += f"Estamos correndo atrás de um déficit de {abs(star_diff)} estrelas. "
        else:
            if dest_diff > 0:
                texto += f"O placar de estrelas está empatado, mas levamos vantagem de {dest_diff:.1f}% na destruição total. "
            else:
                texto += f"O placar está empatado e estamos levemente atrás na destruição por {abs(dest_diff):.1f}%. "

        # 3. Costurando as Bibliotecas Inteligentes (Insights)
        if insights:
            texto += f"O algoritmo destaca que {insights[0]}, o que tem impactado diretamente o nosso resultado. "
            if len(insights) > 1:
                texto += f"Além disso, {insights[1]}. "
                
        # 4. Injetando a Realidade dos Riscos
        if risks:
            texto += f"No entanto, é fundamental ter cuidado: a telemetria aponta que {risks[0]}, o que pode causar uma virada surpresa no final. "

        # 5. Diretriz Tática Orgânica
        if probability >= 75:
            texto += "O foco agora é pura administração: priorizem ataques seguros em bases já mapeadas para não dar margem de erro ao adversário."
        elif probability <= 35:
            texto += "O cenário exige agressividade extrema. Para quebrar a probabilidade atual, precisaremos arriscar estratégias de 3 estrelas nas bases mais difíceis."
        else:
            texto += "A guerra está totalmente em aberto e cada estrela conquistada a partir de agora mudará drasticamente essa projeção matemática."
            
        return {
            "panel": texto,
            "discord": f"**📊 Projeção em Tempo Real**\n{texto}"
        }
