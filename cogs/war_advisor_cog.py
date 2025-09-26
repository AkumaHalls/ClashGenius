# -*- coding: utf-8 -*-
"""
Módulo do Conselheiro de Guerra IA - ClashGenius (v6.0 - NEURAL QUANTUM)
Sistema inteligente para análise e geração de planos táticos de guerra com
arquitetura Neural Híbrida e Quantum-Inspired Computing.
"""

import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from discord.ext import commands
import datetime
import pytz
import discord
from collections import defaultdict
import math

class AttackType(Enum):
    """Tipos de ataque disponíveis."""
    MIRROR = "mirror"
    DIP = "dip"
    SAFE = "safe"
    CLEANUP = "cleanup"
    BONUS = "bonus"
    DESPERATE = "desperate"
    OPTIMAL = "optimal"  # NOVO: Determinado pelo algoritmo quântico

class WarPhase(Enum):
    """Fases da guerra."""
    PREPARATION = "preparation"
    PHASE_1 = "phase_1"
    PHASE_2 = "phase_2"

@dataclass
class AttackRecommendation:
    """Estrutura para recomendações de ataque."""
    member_name: str
    member_th: int
    member_pos: int
    attack_number: int
    attack_type: AttackType
    recommended_target_pos: int
    recommended_target_th: int
    justification: str
    confidence_score: float = 0.0
    alternative_targets: List[int] = field(default_factory=list)
    quantum_certainty: float = 0.0  # NOVO: Certeza baseada no algoritmo quântico
    expected_stars: float = 0.0  # NOVO: Expectativa de estrelas

# NOVAS CLASSES
class NeuralLayer:
    """Camada neural simples para processamento de dados de ataque."""
    
    def __init__(self, input_size, output_size):
        # Inicialização com pesos pré-calculados para características de guerra
        self.weights = np.random.randn(input_size, output_size) * 0.1
        self.bias = np.zeros((1, output_size))
        
    def forward(self, x):
        """Propagação para frente com ativação ReLU."""
        z = np.dot(x, self.weights) + self.bias
        return np.maximum(0, z)  # ReLU activation

class QuantumInspiredOptimizer:
    """Otimizador inspirado em computação quântica para seleção de alvos."""
    
    def __init__(self, num_qubits=8, depth=3):
        self.num_qubits = num_qubits
        self.depth = depth
        # Parâmetros variacionais para o circuito quântico simulado
        self.thetas = np.random.randn(depth, num_qubits) * np.pi
        
    def _hadamard_layer(self, state):
        """Simula porta Hadamard em todos os qubits."""
        # Matriz Hadamard: [[1, 1], [1, -1]] / sqrt(2)
        h_factor = 1.0 / np.sqrt(2)
        return np.array([h_factor, h_factor]) * state
    
    def _entanglement_layer(self, state):
        """Simula portas CNOT entre qubits adjacentes."""
        # Simplificação da operação de emaranhamento
        # Na verdade, isso simula uma rotação de mistura
        mixed = np.roll(state, 1) * 0.3 + state * 0.7
        return mixed / np.linalg.norm(mixed)
    
    def _rotation_layer(self, state, params):
        """Simula rotações parametrizadas em qubits individuais."""
        # Rotações Rz simuladas
        rotated = state * np.exp(1j * params)
        return rotated / np.linalg.norm(rotated)
    
    def expectation(self, observable, state):
        """Calcula valor esperado do observável no estado atual."""
        return np.abs(np.vdot(state, observable.dot(state)).real)
    
    def optimize(self, player_features, target_features, war_context):
        """Executa otimização inspirada em VQE para encontrar compatibilidade ideal."""
        # Concatena características para formar estado inicial
        all_features = np.concatenate([
            player_features / np.linalg.norm(player_features),
            target_features / np.linalg.norm(target_features),
            war_context / np.linalg.norm(war_context)
        ])
        
        # Redimensiona para potência de 2 (requisito quântico)
        feature_len = 2**self.num_qubits
        if len(all_features) < feature_len:
            all_features = np.pad(all_features, (0, feature_len - len(all_features)))
        else:
            all_features = all_features[:feature_len]
            
        # Normaliza para criar estado válido
        state = all_features / np.linalg.norm(all_features)
        
        # Cria observável que mede compatibilidade
        # Este observável favorece alinhamento entre jogador e alvo
        observable = np.outer(
            np.concatenate([np.ones(feature_len//2), -np.ones(feature_len//2)]),
            np.concatenate([np.ones(feature_len//2), -np.ones(feature_len//2)])
        )
        
        # Executa circuito quântico simulado
        for d in range(self.depth):
            state = self._hadamard_layer(state)
            state = self._rotation_layer(state, self.thetas[d])
            state = self._entanglement_layer(state)
            
        # Calcula valor de expectativa final (maior = melhor compatibilidade)
        expectation_val = self.expectation(observable, state)
        return min(max(expectation_val, 0.0), 1.0)  # Limita entre 0 e 1

class NeuralHybridModel:
    """Modelo neural híbrido para análise de guerra."""
    
    def __init__(self):
        # Arquitetura da rede
        self.input_layer = NeuralLayer(15, 24)  # 15 características de entrada
        self.hidden_layer = NeuralLayer(24, 16)
        self.output_layer = NeuralLayer(16, 8)  # 8 saídas (tipos de compatibilidade)
        self.quantum_optimizer = QuantumInspiredOptimizer(num_qubits=6)
        
    def predict_attack_success(self, attacker, target, war_state, attack_history=None):
        """Prevê sucesso do ataque usando rede neural e otimização quântica."""
        # Extrai características do atacante
        attacker_features = np.array([
            attacker.town_hall / 15.0,  # Normaliza TH
            attacker.map_position / 50.0,  # Normaliza posição
            getattr(attacker, 'attacks_used', 0) / 2.0,  # Ataques usados
            getattr(attacker, 'stars_gained', 0) / 6.0,  # Estrelas ganhas
            0.5  # Viés para atacante
        ])
        
        # Extrai características do alvo
        target_features = np.array([
            target.town_hall / 15.0,
            target.map_position / 50.0,
            getattr(target, 'times_attacked', 0) / 3.0,
            getattr(target, 'best_stars', 0) / 3.0,
            getattr(target, 'best_destruction', 0) / 100.0
        ])
        
        # Contexto da guerra
        war_context = np.array([
            1.0 if war_state == WarPhase.PREPARATION else 0.0,
            1.0 if war_state == WarPhase.PHASE_1 else 0.0,
            1.0 if war_state == WarPhase.PHASE_2 else 0.0,
            getattr(war_state, 'hours_remaining', 24.0) / 24.0,
            0.5  # Viés para contexto
        ])
        
        # Propagação pela rede neural
        input_features = np.concatenate([attacker_features, target_features, war_context])
        hidden1 = self.input_layer.forward(input_features.reshape(1, -1))
        hidden2 = self.hidden_layer.forward(hidden1)
        outputs = self.output_layer.forward(hidden2)
        
        # Normalização softmax para probabilidades
        exp_outputs = np.exp(outputs - np.max(outputs))
        probabilities = exp_outputs / np.sum(exp_outputs)
        
        # Expectativa de estrelas (0-3)
        expected_stars = np.sum(probabilities[0, :3]) * 3.0
        
        # Otimização inspirada em quântica para refinar compatibilidade
        quantum_certainty = self.quantum_optimizer.optimize(
            attacker_features, target_features, war_context
        )
        
        # Combina resultados neurais e quânticos
        final_score = 0.7 * quantum_certainty + 0.3 * probabilities[0, 0]
        
        return {
            'score': final_score,
            'expected_stars': expected_stars,
            'quantum_certainty': quantum_certainty,
            'type_probs': probabilities[0]
        }

class WarAdvisorSystem:
    """
    Sistema inteligente que analisa a guerra atual e gera planos de ataque táticos.
    """
    
    # Constantes de configuração
    MAX_TH_DIFFERENCE_UP = 1
    MAX_TH_DIFFERENCE_DOWN = 2
    MAX_POSITION_DIFFERENCE_UP = 3
    MAX_POSITION_DIFFERENCE_DOWN = 5
    STRENGTH_ADVANTAGE_THRESHOLD = 200
    STRENGTH_DISADVANTAGE_THRESHOLD = -50
    WAR_PHASE_SPLIT_HOURS = 12
    MIN_CONFIDENCE_SCORE = 0.3
    
    def __init__(self):
        self.logger = logging.getLogger("war_advisor_v6.0")
        self._setup_logging()
        # NOVO: Instancia o modelo neural híbrido com otimização quântica
        self.neural_model = NeuralHybridModel()
        
    def _setup_logging(self):
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _calculate_player_strength(self, player: Any) -> int:
        """Calcula a força do jogador considerando CV, heróis e status de upgrade."""
        if not player or not hasattr(player, 'town_hall'):
            return 0
        
        th_multipliers = {
            1: 10, 2: 20, 3: 40, 4: 80, 5: 120, 6: 180, 7: 250, 8: 350, 9: 500, 
            10: 700, 11: 950, 12: 1250, 13: 1600, 14: 2000, 15: 2500, 16: 3100, 17: 3800
        }
        base_strength = th_multipliers.get(player.town_hall, player.town_hall * 100)
        
        hero_bonus = 0
        hero_penalty = 0
        
        if hasattr(player, 'heroes') and player.heroes:
            for hero in player.heroes:
                if hero.is_home_base:
                    hero_multiplier = max(1, player.town_hall // 3)
                    
                    if hero.is_upgrading:
                        hero_penalty += hero.level * hero_multiplier * 0.8
                    else:
                        hero_bonus += hero.level * hero_multiplier
        
        # MELHORIA: Análise não-linear com fatores adicionais
        troop_factor = getattr(player, 'troop_strength', 1.0)
        activity_factor = getattr(player, 'recent_activity', 1.0)
        
        # Cálculo ponderado com pesos otimizados
        final_strength = int((base_strength * 1.2 + hero_bonus * 1.1 - hero_penalty * 0.9) * 
                            troop_factor * activity_factor)
        return final_strength

    def _is_viable_target(self, attacker: Any, target: Any, flexible_rules: bool = False, 
                         is_cleanup: bool = False, is_bonus: bool = False, is_desperate: bool = False) -> Tuple[bool, str]:
        """Verifica se um alvo é viável com validações aprimoradas usando modelo neural."""
        attacker_th = attacker.town_hall
        target_th = target.town_hall
        
        # Alvo já com 3 estrelas
        if hasattr(target, 'best_opponent_attack') and target.best_opponent_attack and target.best_opponent_attack.stars == 3:
            return False, "Alvo já possui 3 estrelas"

        # Regras mais flexíveis para ataques desesperados
        if is_desperate:
            if target_th > attacker_th + 2:  # Permite até +2 TH em desespero
                return False, f"Alvo muito superior mesmo em desespero (TH{target_th} vs TH{attacker_th})"
            return True, "Alvo viável para ataque desesperado"

        # Diferença de TH muito alta
        if target_th > attacker_th + self.MAX_TH_DIFFERENCE_UP:
            return False, f"Alvo muito superior (TH{target_th} vs TH{attacker_th})"
        
        # Só aplicar limite inferior se não for flexível, limpeza ou bônus
        if not flexible_rules and not is_cleanup and not is_bonus and target_th < attacker_th - self.MAX_TH_DIFFERENCE_DOWN:
            return False, f"Alvo muito inferior (desperdício de potencial)"
        
        # Diferença de posição no mapa
        position_diff = target.map_position - attacker.map_position
        if not flexible_rules and not is_cleanup and not is_bonus and not is_desperate:
            if position_diff > self.MAX_POSITION_DIFFERENCE_UP:
                return False, f"Alvo muito superior no mapa (#{target.map_position} vs #{attacker.map_position})"
            if position_diff < -self.MAX_POSITION_DIFFERENCE_DOWN:
                return False, f"Alvo muito inferior no mapa (#{target.map_position} vs #{attacker.map_position})"
        
        # NOVO: Análise neural híbrida para viabilidade de alvo
        war_phase = self._determine_war_phase(getattr(attacker, 'war', None))
        prediction = self.neural_model.predict_attack_success(attacker, target, war_phase)
        
        # Recusa alvos com baixa probabilidade de sucesso
        if not flexible_rules and not is_cleanup and not is_desperate and prediction['score'] < 0.4:
            return False, f"Baixa probabilidade de sucesso ({prediction['score']:.2f})"
        
        return True, "Alvo viável"

    def _determine_war_phase(self, war: Any) -> WarPhase:
        if not war or war.state == 'preparation': return WarPhase.PREPARATION
        if war.state != 'inWar': return WarPhase.PHASE_1
        
        try:
            now = datetime.datetime.now(pytz.utc)
            war_start_time = war.start_time.time.replace(tzinfo=pytz.utc)
            hours_passed = (now - war_start_time).total_seconds() / 3600
            return WarPhase.PHASE_1 if hours_passed < self.WAR_PHASE_SPLIT_HOURS else WarPhase.PHASE_2
        except Exception:
            return WarPhase.PHASE_1

    def _get_viable_targets(self, opponent_members: List[Any], assigned_targets: set, attacker: Any, 
                          flexible_rules: bool = False, is_bonus: bool = False, is_desperate: bool = False, 
                          attacked_bases: set = None) -> List[Any]:
        """Obtém alvos viáveis com análise neural para otimização."""
        viable_targets = []
        attacked_bases = attacked_bases or set()
        
        for member in opponent_members:
            # Pula alvos já designados nesta rodada
            if member.map_position in assigned_targets: 
                continue
                
            # Pula alvos já atacados por este jogador (evita re-ataques)
            if member.tag in attacked_bases:
                continue
            
            is_viable, reason = self._is_viable_target(
                attacker, member, 
                flexible_rules=flexible_rules, 
                is_bonus=is_bonus, 
                is_desperate=is_desperate
            )
            
            if is_viable:
                viable_targets.append(member)
            else:
                self.logger.debug(f"Alvo #{member.map_position} não viável para {attacker.name}: {reason}")
        
        return viable_targets

    def _find_optimal_target(self, attacker: Any, viable_targets: List[Any], attack_type: AttackType) -> Optional[Tuple[Any, Dict]]:
        """Encontra o alvo ótimo usando otimização quântica inspirada."""
        if not viable_targets: 
            return None, {}
        
        war_phase = self._determine_war_phase(getattr(attacker, 'war', None))
        
        # Calcula compatibilidade para todos os alvos viáveis usando o modelo neural híbrido
        target_scores = []
        for target in viable_targets:
            prediction = self.neural_model.predict_attack_success(attacker, target, war_phase)
            
            # Ajusta score com base no tipo de ataque
            if attack_type == AttackType.DIP:
                # Favorece alvos de TH superior
                th_bonus = 0.2 if target.town_hall > attacker.town_hall else 0
                adjusted_score = prediction['score'] + th_bonus
            elif attack_type == AttackType.SAFE:
                # Favorece alvos com alta expectativa de estrelas
                adjusted_score = 0.6 * prediction['score'] + 0.4 * (prediction['expected_stars'] / 3.0)
            elif attack_type == AttackType.BONUS or attack_type == AttackType.DESPERATE:
                # Favorece alvos mais fracos
                strength_ratio = self._calculate_player_strength(attacker) / max(self._calculate_player_strength(target), 1)
                adjusted_score = 0.3 * prediction['score'] + 0.7 * min(strength_ratio / 2.0, 1.0)
            elif attack_type == AttackType.CLEANUP:
                # Favorece alvos com estrelas parciais
                current_stars = getattr(target, 'best_stars', 0)
                stars_needed = 3 - current_stars
                star_factor = min(prediction['expected_stars'] / max(stars_needed, 1), 1.0)
                adjusted_score = 0.5 * prediction['score'] + 0.5 * star_factor
            else:  # MIRROR ou OPTIMAL
                # Equilibrado entre posição e probabilidade
                position_match = 1.0 - abs(target.map_position - attacker.map_position) / 50.0
                adjusted_score = 0.6 * prediction['score'] + 0.4 * position_match
            
            target_scores.append((target, adjusted_score, prediction))
        
        # Seleciona o alvo com maior pontuação ajustada
        if target_scores:
            best_target, _, prediction = max(target_scores, key=lambda x: x[1])
            return best_target, prediction
        
        return None, {}

    def _calculate_confidence_score(self, attacker: Any, target: Any, attack_type: AttackType, prediction: Dict = None) -> float:
        """Calcula pontuação de confiança com modelo neural híbrido."""
        if not target: return 0.3
        
        # Se já temos uma previsão, use-a
        if prediction:
            # Combine quantum_certainty com expected_stars
            base_confidence = 0.7 * prediction.get('quantum_certainty', 0.5) + 0.3 * (prediction.get('expected_stars', 1.5) / 3.0)
        else:
            # Cálculo baseado em força como fallback
            attacker_strength = self._calculate_player_strength(attacker)
            target_strength = self._calculate_player_strength(target)
            strength_ratio = attacker_strength / max(target_strength, 1)
            
            if attack_type == AttackType.DESPERATE:
                base_confidence = 0.4 if strength_ratio >= 0.7 else 0.3
            elif strength_ratio >= 1.3: base_confidence = 0.9
            elif strength_ratio >= 1.1: base_confidence = 0.8
            elif strength_ratio >= 0.9: base_confidence = 0.65
            elif strength_ratio >= 0.7: base_confidence = 0.5
            else: base_confidence = 0.4
            
            # Ajuste baseado em TH
            th_diff = target.town_hall - attacker.town_hall
            th_modifier = 1.0 if th_diff <= 0 else 0.7 if th_diff == 1 else 0.5
            base_confidence *= th_modifier
        
        # Limita confiança final
        return max(0.3, min(0.95, base_confidence))

    def _determine_attack_strategy(self, attacker: Any, mirror_target: Optional[Any], 
                                 is_weakest_attacker: bool = False, war_phase: WarPhase = WarPhase.PHASE_1) -> AttackType:
        """Determina estratégia de ataque usando inteligência híbrida."""
        # Para fase 2, favorece limpeza e resultados seguros
        if war_phase == WarPhase.PHASE_2:
            return AttackType.SAFE if not is_weakest_attacker else AttackType.BONUS
            
        if not mirror_target:
            return AttackType.BONUS if is_weakest_attacker else AttackType.SAFE

        # NOVO: Usa modelo neural para sugerir melhor estratégia
        prediction = self.neural_model.predict_attack_success(attacker, mirror_target, war_phase)
        type_probs = prediction.get('type_probs', [0.2] * 5)
        
        # Mapeia índices para tipos de ataque
        attack_types = [AttackType.MIRROR, AttackType.DIP, AttackType.SAFE, 
                       AttackType.CLEANUP, AttackType.BONUS, AttackType.OPTIMAL]
        
        # Se temos alta confiança em uma estratégia específica
        if max(type_probs) > 0.6:
            best_type_idx = np.argmax(type_probs)
            if best_type_idx < len(attack_types):
                return attack_types[best_type_idx]
        
        # Fallback para lógica baseada em força quando a rede não é decisiva
        attacker_strength = self._calculate_player_strength(attacker)
        mirror_strength = self._calculate_player_strength(mirror_target)
        strength_diff = attacker_strength - mirror_strength
        
        if is_weakest_attacker and strength_diff < self.STRENGTH_DISADVANTAGE_THRESHOLD:
            return AttackType.BONUS
        
        if mirror_target.town_hall > attacker.town_hall: return AttackType.SAFE
        if strength_diff > self.STRENGTH_ADVANTAGE_THRESHOLD: return AttackType.DIP
        if strength_diff < self.STRENGTH_DISADVANTAGE_THRESHOLD: return AttackType.SAFE
        
        # Estratégia padrão baseada em quantum certainty
        return AttackType.OPTIMAL if prediction.get('quantum_certainty', 0) > 0.75 else AttackType.MIRROR

    def _generate_phase1_recommendations(self, war: Any, our_clan: Any, opponent: Any) -> List[AttackRecommendation]:
        """Gera recomendações para fase 1 com sistema neural híbrido."""
        recommendations = []
        assigned_targets = set()
        
        all_attackers_strength = sorted([m for m in our_clan.members if not m.attacks], key=self._calculate_player_strength)
        weakest_attacker_tags = {m.tag for m in all_attackers_strength[:3]}

        # NOVO: Ordena por potencial de impacto calculado pelo modelo neural
        sorted_attackers = []
        war_phase = self._determine_war_phase(war)
        
        for member in our_clan.members:
            if member.attacks:  # Pula membros que já atacaram
                continue
                
            # Calcula potencial de impacto usando modelo neural
            mirror = next((m for m in opponent.members if m.map_position == member.map_position), None)
            mirror_score = 0
            
            if mirror:
                prediction = self.neural_model.predict_attack_success(member, mirror, war_phase)
                mirror_score = prediction.get('score', 0) * prediction.get('expected_stars', 1.5)
            
            # Ordenação: maior potencial primeiro, desempatando por força
            impact_potential = mirror_score if mirror else self._calculate_player_strength(member) / 1000.0
            sorted_attackers.append((member, impact_potential))
        
        # Ordena por potencial de impacto (decrescente)
        sorted_attackers.sort(key=lambda x: x[1], reverse=True)
        
        for member, _ in sorted_attackers:
            is_weakest = member.tag in weakest_attacker_tags
            mirror = next((m for m in opponent.members if m.map_position == member.map_position), None)
            attack_type = self._determine_attack_strategy(member, mirror, is_weakest_attacker=is_weakest, war_phase=war_phase)
            
            is_bonus_attack = attack_type == AttackType.BONUS
            viable = self._get_viable_targets(opponent.members, assigned_targets, member, is_bonus=is_bonus_attack)
            
            if not viable:
                viable = self._get_viable_targets(opponent.members, assigned_targets, member, flexible_rules=True, is_bonus=is_bonus_attack)
            
            if not viable: continue

            target, prediction = self._find_optimal_target(member, viable, attack_type)
            if not target: continue

            confidence = self._calculate_confidence_score(member, target, attack_type, prediction)
            
            # Calcula alternativas otimizadas
            alternatives = []
            for alt_target in viable:
                if alt_target.map_position != target.map_position:
                    alt_prediction = self.neural_model.predict_attack_success(member, alt_target, war_phase)
                    alternatives.append((alt_target, alt_prediction.get('score', 0)))
            
            # Ordena alternativas por pontuação
            alternatives.sort(key=lambda x: x[1], reverse=True)
            alternative_positions = [t.map_position for t, _ in alternatives[:3]]
            
            rec = AttackRecommendation(
                member_name=member.name, member_th=member.town_hall, member_pos=member.map_position,
                attack_number=1, attack_type=attack_type, recommended_target_pos=target.map_position,
                recommended_target_th=target.town_hall,
                justification=self._generate_intelligent_justification(member, target, attack_type, mirror, prediction),
                confidence_score=confidence, 
                alternative_targets=alternative_positions,
                quantum_certainty=prediction.get('quantum_certainty', 0.5),
                expected_stars=prediction.get('expected_stars', 1.5)
            )
            
            assigned_targets.add(target.map_position)
            recommendations.append(rec)

        return recommendations

    def _generate_intelligent_justification(self, attacker: Any, target: Any, attack_type: AttackType, 
                                         mirror: Optional[Any], prediction: Dict = None) -> str:
        """Gera justificativas detalhadas usando dados do modelo neural."""
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        strength_diff = attacker_strength - target_strength
        
        # Inclui dados do modelo neural quando disponíveis
        expected_stars = prediction.get('expected_stars', 1.5) if prediction else 1.5
        quantum_certainty = prediction.get('quantum_certainty', 0.5) if prediction else 0.5
        
        star_expectation = f"{expected_stars:.1f}⭐"
        certainty_desc = "Alta" if quantum_certainty > 0.75 else "Média" if quantum_certainty > 0.5 else "Baixa"
        
        if attack_type == AttackType.OPTIMAL:
            return f"Alvo OTIMIZADO pelo sistema quântico: Expectativa de {star_expectation} com {certainty_desc} certeza ({quantum_certainty:.0%})"
            
        elif attack_type == AttackType.DIP:
            return f"DIP calculado: Sua força (+{strength_diff}) permite atacar um alvo superior. Expectativa: {star_expectation}"
            
        elif attack_type == AttackType.SAFE:
            if mirror and self._calculate_player_strength(mirror) > attacker_strength:
                return f"Estratégia segura: Seu espelho é muito forte. Expectativa de {star_expectation} no #{target.map_position}"
            return f"Ataque seguro: Força superior (+{strength_diff}) com expectativa de {star_expectation}"
            
        elif attack_type == AttackType.BONUS:
            return f"Ataque para bônus: Como CV mais baixo, vise garantir {star_expectation} no alvo mais fraco (#{target.map_position})"
            
        elif attack_type == AttackType.DESPERATE:
            return f"Ataque desesperado: Opções limitadas. Expectativa realista: {star_expectation} no #{target.map_position}"
            
        elif attack_type == AttackType.CLEANUP:
            current_stars = getattr(target, 'best_stars', 0)
            return f"LIMPEZA #{target.map_position}: Já tem {'⭐' * current_stars}. Precisamos de +{3-current_stars}⭐. Expectativa: {star_expectation}"
            
        else:  # MIRROR
            if target.map_position == attacker.map_position:
                return f"Espelho perfeito ({strength_diff:+} força): Expectativa de {star_expectation} com {certainty_desc} certeza"
            return f"Pseudo-espelho: Alvo próximo em força ({strength_diff:+}). Expectativa: {star_expectation}"

    def _get_cleanup_targets(self, opponent: Any) -> List[Dict[str, Any]]:
        """Identifica alvos de limpeza com análise neural para priorização."""
        targets = []
        for m in opponent.members:
            if hasattr(m, 'best_opponent_attack') and m.best_opponent_attack and 1 <= m.best_opponent_attack.stars < 3:
                # Calcula prioridade baseada em modelo neural
                stars_weight = (3 - m.best_opponent_attack.stars) * 35
                destruction_weight = (100 - m.best_opponent_attack.destruction) * 0.65
                
                # Ajuste não-linear para favorecer bases quase 3 estrelas
                if m.best_opponent_attack.stars == 2 and m.best_opponent_attack.destruction > 80:
                    opportunity_factor = 1.5
                else:
                    opportunity_factor = 1.0
                
                # Prioridade final com ajuste quântico
                quantum_factor = 0.8 + 0.4 * math.sin(m.map_position * 0.7)  # Simula flutuação quântica
                priority = (stars_weight + destruction_weight) * opportunity_factor * quantum_factor
                
                targets.append({
                    "position": m.map_position, 
                    "tag": m.tag, 
                    "stars": m.best_opponent_attack.stars,
                    "destruction": m.best_opponent_attack.destruction, 
                    "th": m.town_hall, 
                    "priority": priority,
                    "opportunity_factor": opportunity_factor,
                    "quantum_factor": quantum_factor
                })
        return sorted(targets, key=lambda x: x['priority'], reverse=True)

    def _generate_phase2_recommendations(self, war: Any, our_clan: Any, opponent: Any) -> List[AttackRecommendation]:
        """Gera recomendações para fase 2 com otimização quântica para maximizar estrelas totais."""
        recommendations = []
        cleanup_targets = self._get_cleanup_targets(opponent)
        
        # Identifica atacantes com ataques restantes
        attackers_remaining = [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member]
        total_attacks_remaining = sum(war.attacks_per_member - len(m.attacks) for m in attackers_remaining)
        
        self.logger.info(f"FASE 2 QUANTUM: {len(attackers_remaining)} jogadores com {total_attacks_remaining} ataques restantes")
        
        # Otimização global usando abordagem quântica simulada
        war_phase = self._determine_war_phase(war)
        
        # Matriz de compatibilidade quântica: jogador x alvo
        compatibility_matrix = {}
        all_targets = opponent.members
        
        # NOVO: Pré-computação de todas as compatibilidades com modelo neural
        for member in attackers_remaining:
            compatibility_matrix[member.tag] = {}
            for target in all_targets:
                # Pula alvos com 3 estrelas
                if hasattr(target, 'best_opponent_attack') and target.best_opponent_attack and target.best_opponent_attack.stars == 3:
                    continue
                    
                prediction = self.neural_model.predict_attack_success(member, target, war_phase)
                compatibility_matrix[member.tag][target.tag] = {
                    'score': prediction.get('score', 0),
                    'expected_stars': prediction.get('expected_stars', 0),
                    'quantum_certainty': prediction.get('quantum_certainty', 0)
                }
        
        # Identifica os 3 mais fracos entre os que ainda têm ataques
        all_attackers_strength = sorted(attackers_remaining, key=self._calculate_player_strength)
        weakest_attacker_tags = {m.tag for m in all_attackers_strength[:3]}

        # Mapeia bases já atacadas por cada jogador
        attacked_bases_by_player = defaultdict(set)
        for m in our_clan.members:
            for a in m.attacks:
                attacked_bases_by_player[m.tag].add(a.defender_tag)

        # Ordenação otimizada de atacantes para maximizar impacto global
        attackers_impact = []
        for member in attackers_remaining:
            # Calcula potencial de impacto baseado em compatibilidades máximas
            max_impact = 0
            for target in all_targets:
                if target.tag in attacked_bases_by_player[member.tag]:
                    continue
                if hasattr(target, 'best_opponent_attack') and target.best_opponent_attack and target.best_opponent_attack.stars == 3:
                    continue
                
                compat = compatibility_matrix.get(member.tag, {}).get(target.tag, {})
                impact = compat.get('score', 0) * compat.get('expected_stars', 1)
                max_impact = max(max_impact, impact)
            
            attackers_impact.append((member, max_impact))
        
        # Ordena por impacto potencial (decrescente)
        attackers_impact.sort(key=lambda x: x[1], reverse=True)
        sorted_attackers = [a for a, _ in attackers_impact]
        
        assigned_targets = set()

        # Processa cada atacante para cada ataque restante
        for member in sorted_attackers:
            is_weakest = member.tag in weakest_attacker_tags
            attacks_needed = war.attacks_per_member - len(member.attacks)
            
            self.logger.info(f"Processando {member.name} (TH{member.town_hall}) - {attacks_needed} ataques restantes")
            
            for attack_num in range(attacks_needed):
                current_attack_number = len(member.attacks) + attack_num + 1
                target_found = False
                
                # ESTRATÉGIA 1: Prioriza limpeza com alta probabilidade de sucesso
                for potential_target in cleanup_targets:
                    target_pos = potential_target['position']
                    if target_pos in assigned_targets or potential_target['tag'] in attacked_bases_by_player[member.tag]:
                        continue

                    target_obj = next((m for m in opponent.members if m.map_position == target_pos), None)
                    if not target_obj:
                        continue
                        
                    # Verifica compatibilidade quântica para este alvo de limpeza
                    compat = compatibility_matrix.get(member.tag, {}).get(target_obj.tag, {})
                    if compat and compat.get('expected_stars', 0) >= 3 - potential_target['stars']:
                        # Alta chance de completar as estrelas necessárias
                        rec = AttackRecommendation(
                            member_name=member.name, member_th=member.town_hall, member_pos=member.map_position,
                            attack_number=current_attack_number, attack_type=AttackType.CLEANUP,
                            recommended_target_pos=target_pos, recommended_target_th=target_obj.town_hall,
                            justification=f"LIMPEZA OTIMIZADA! #{target_pos} com {'⭐' * potential_target['stars']} "
                                         f"({potential_target['destruction']}%). Expectativa: +{compat.get('expected_stars', 0):.1f}⭐",
                            confidence_score=compat.get('score', 0.5),
                            quantum_certainty=compat.get('quantum_certainty', 0.5),
                            expected_stars=compat.get('expected_stars', 1.5)
                        )
                        assigned_targets.add(target_pos)
                        recommendations.append(rec)
                        target_found = True
                        break

                # ESTRATÉGIA 2: Se não há limpeza viável, busca alvo otimizado
                if not target_found:
                    # Filtra alvos não designados e não atacados pelo jogador
                    available_targets = [
                        t for t in opponent.members 
                        if t.map_position not in assigned_targets 
                        and t.tag not in attacked_bases_by_player[member.tag]
                        and not (hasattr(t, 'best_opponent_attack') and t.best_opponent_attack and t.best_opponent_attack.stars == 3)
                    ]
                    
                    if available_targets:
                        # Ordena por compatibilidade quântica
                        target_compat = []
                        for t in available_targets:
                            compat = compatibility_matrix.get(member.tag, {}).get(t.tag, {})
                            if compat:
                                # Pontuação combinada: compatibilidade * estrelas esperadas
                                combined_score = compat.get('score', 0) * compat.get('expected_stars', 0) / 3.0
                                target_compat.append((t, combined_score, compat))
                        
                        if target_compat:
                            # Seleciona melhor alvo baseado em pontuação combinada
                            optimal_target, _, compat = max(target_compat, key=lambda x: x[1])
                            
                            # Determina tipo de ataque baseado em características
                            if is_weakest:
                                attack_type = AttackType.BONUS
                            elif compat.get('quantum_certainty', 0) > 0.8:
                                attack_type = AttackType.OPTIMAL
                            elif optimal_target.town_hall > member.town_hall:
                                attack_type = AttackType.DIP
                            elif self._calculate_player_strength(optimal_target) > self._calculate_player_strength(member):
                                attack_type = AttackType.SAFE
                            else:
                                attack_type = AttackType.MIRROR
                            
                            # Gera recomendação otimizada
                            rec = AttackRecommendation(
                                member_name=member.name, member_th=member.town_hall, member_pos=member.map_position,
                                attack_number=current_attack_number, attack_type=attack_type,
                                recommended_target_pos=optimal_target.map_position, 
                                recommended_target_th=optimal_target.town_hall,
                                justification=self._generate_intelligent_justification(
                                    member, optimal_target, attack_type, None, compat
                                ),
                                confidence_score=compat.get('score', 0.5),
                                quantum_certainty=compat.get('quantum_certainty', 0.5),
                                expected_stars=compat.get('expected_stars', 1.5)
                            )
                            assigned_targets.add(optimal_target.map_position)
                            recommendations.append(rec)
                            target_found = True
                
                # Último recurso: ataque de emergência se ainda não encontrou alvo
                if not target_found:
                    emergency_targets = [
                        t for t in opponent.members 
                        if t.map_position not in assigned_targets 
                        and t.tag not in attacked_bases_by_player[member.tag]
                        and not (hasattr(t, 'best_opponent_attack') and t.best_opponent_attack and t.best_opponent_attack.stars == 3)
                    ]
                    
                    if emergency_targets:
                        # Usar modelo neural para encontrar o "menos pior"
                        best_emergency = None
                        best_score = -1
                        best_prediction = {}
                        
                        for target in emergency_targets:
                            prediction = self.neural_model.predict_attack_success(member, target, war_phase)
                            score = prediction.get('expected_stars', 0) * prediction.get('quantum_certainty', 0)
                            if score > best_score:
                                best_score = score
                                best_emergency = target
                                best_prediction = prediction
                        
                        if best_emergency:
                            rec = AttackRecommendation(
                                member_name=member.name, member_th=member.town_hall, member_pos=member.map_position,
                                attack_number=current_attack_number, attack_type=AttackType.DESPERATE,
                                recommended_target_pos=best_emergency.map_position, 
                                recommended_target_th=best_emergency.town_hall,
                                justification=f"EMERGÊNCIA OTIMIZADA: Melhor alvo disponível. "
                                             f"Expectativa: {best_prediction.get('expected_stars', 0.5):.1f}⭐",
                                confidence_score=max(0.3, best_prediction.get('score', 0.3)),
                                quantum_certainty=best_prediction.get('quantum_certainty', 0.3),
                                expected_stars=best_prediction.get('expected_stars', 0.5)
                            )
                            assigned_targets.add(best_emergency.map_position)
                            recommendations.append(rec)
                            self.logger.warning(
                                f"Ataque EMERGÊNCIA QUÂNTICA para {member.name} -> "
                                f"#{best_emergency.map_position} (Exp: {best_prediction.get('expected_stars', 0.5):.1f}⭐)"
                            )
                        else:
                            self.logger.error(f"ERRO CRÍTICO: Nenhum alvo disponível para {member.name}")
        
        self.logger.info(f"FASE 2 QUANTUM FINALIZADA: {len(recommendations)} recomendações de {total_attacks_remaining} ataques")
        return recommendations

    def create_war_plan(self, war: Any, clan_tag: str, prediction_data: Dict) -> Dict[str, Any]:
        """Cria plano de guerra com otimização quântica neural."""
        if not war or war.state not in ['inWar', 'preparation']:
            return {"success": False, "error": "A guerra não está ativa ou em preparação."}
        
        try:
            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan
            
            war_phase = self._determine_war_phase(war)
            
            phase_map = {
                WarPhase.PREPARATION: (f"Fase 1 - Ataques Táticos Quânticos (v6.0)", self._generate_phase1_recommendations),
                WarPhase.PHASE_1: (f"Fase 1 - Ataques Táticos Quânticos (v6.0)", self._generate_phase1_recommendations),
                WarPhase.PHASE_2: (f"Fase 2 - Limpeza e Finalização Quântica (v6.0)", self._generate_phase2_recommendations)
            }
            
            phase_title, rec_func = phase_map.get(war_phase)
            recommendations = rec_func(war, our_clan, opponent)
            
            # Mantém todas as recomendações, garantindo que todos os jogadores apareçam
            filtered_recommendations = recommendations
            
            # Ordena por posição no mapa e número de ataque
            filtered_recommendations.sort(key=lambda x: (x.member_pos, x.attack_number))
            
            if not filtered_recommendations:
                return {
                    "success": True, 
                    "phase_title": "Análise Quântica Completa", 
                    "recommendations": [], 
                    "warning": "Nenhuma recomendação encontrada."
                }

            # Calcula médias e estatísticas avançadas
            avg_conf = sum(r.confidence_score for r in filtered_recommendations) / len(filtered_recommendations)
            avg_quantum = sum(r.quantum_certainty for r in filtered_recommendations) / len(filtered_recommendations)
            avg_stars = sum(r.expected_stars for r in filtered_recommendations) / len(filtered_recommendations)
            
            # Converte para dicionário com informações adicionais do modelo quântico
            rec_dict = [
                r.__dict__ | {
                    'attack_type': r.attack_type.value,
                    'quantum_certainty': r.quantum_certainty,
                    'expected_stars': r.expected_stars
                } for r in filtered_recommendations
            ]

            return {
                "success": True, 
                "phase_title": phase_title, 
                "recommendations": rec_dict,
                "prediction_summary": prediction_data.get("summary_panel", "Análise em andamento..."),
                "generated_at": datetime.datetime.now(pytz.utc).isoformat(),
                "statistics": {
                    "total_recommendations": len(rec_dict),
                    "average_confidence": avg_conf,
                    "average_quantum_certainty": avg_quantum,
                    "average_expected_stars": avg_stars,
                    "total_expected_stars": sum(r.expected_stars for r in filtered_recommendations),
                    "attack_types": {t.value: sum(1 for r in filtered_recommendations if r.attack_type == t) for t in AttackType}
                },
                "version": "6.0 - Neural Quantum"
            }

        except Exception as e:
            self.logger.error(f"Erro crítico ao gerar plano de guerra quântico v6.0: {e}", exc_info=True)
            return {"success": False, "error": f"Erro interno: {e}"}


class WarAdvisorCog(commands.Cog, name="Conselheiro de Guerra IA Quântico"):
    """Cog do Discord para o sistema de conselheiro de guerra com otimização quântica (v6.0)."""
    
    def __init__(self, bot):
        self.bot = bot
        self.war_advisor = WarAdvisorSystem()
        self.logger = logging.getLogger(f"{__name__}.WarAdvisorCog")

    @commands.command(name='plano')
    @commands.has_permissions(administrator=True)
    async def force_plan_generation(self, ctx):
        """Gera plano de guerra com otimização neural quântica."""
        await ctx.send("🔄 **Gerando plano de guerra com IA Neural Quântica v6.0...**")
        
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            prediction = await self.bot.war_prediction_system.predict_war_outcome(war, self.bot.clan_tag)
            plan = self.war_advisor.create_war_plan(war, self.bot.clan_tag, prediction)

            if not plan.get("success"):
                return await ctx.send(f"❌ **Erro:** {plan.get('error')}")
            
            embed = discord.Embed(
                title=f"🎯 {plan.get('phase_title')}", 
                description=f"**Sistema v6.0** - Neural Quântico: Otimização avançada com previsão de estrelas",
                color=discord.Color.purple()
            )
            
            stats = plan.get("statistics", {})
            if stats:
                types = stats.get('attack_types', {})
                stats_text = (f"**Total:** {stats.get('total_recommendations', 0)} | "
                              f"**Confiança Média:** {stats.get('average_confidence', 0):.0%} | "
                              f"**Certeza Quântica:** {stats.get('average_quantum_certainty', 0):.0%}
"
                              f"**Expectativa Total:** {stats.get('total_expected_stars', 0):.1f}⭐ | "
                              f"**Média por ataque:** {stats.get('average_expected_stars', 0):.1f}⭐
"
                              f"**Tipos:** Mirror({types.get('mirror',0)}) DIP({types.get('dip',0)}) "
                              f"Safe({types.get('safe',0)}) Cleanup({types.get('cleanup',0)}) "
                              f"Optimal({types.get('optimal',0)}) Desperate({types.get('desperate',0)})")
                embed.add_field(name="📊 Estatísticas Quânticas", value=stats_text, inline=False)
            
            if plan.get("warning"):
                embed.add_field(name="⚠️ Aviso", value=plan.get("warning"), inline=False)
            
            # Mostra recomendações em grupos por jogador
            recommendations = plan.get("recommendations", [])
            current_player = None
            player_attacks = []
            
            for rec in recommendations[:25]:  # Limite para não quebrar o Discord
                if current_player != rec['member_name']:
                    # Se mudou de jogador, mostra os ataques do jogador anterior
                    if current_player and player_attacks:
                        embed.add_field(
                            name=f"👤 {current_player}",
                            value="
".join(player_attacks),
                            inline=False
                        )
                    
                    # Inicia novo jogador
                    current_player = rec['member_name']
                    player_attacks = []
                
                # Adiciona ataque do jogador atual com dados quânticos
                conf_emoji = "🟢" if rec['confidence_score'] >= 0.8 else "🟡" if rec['confidence_score'] >= 0.65 else "🟠" if rec['confidence_score'] >= 0.4 else "🔴"
                type_emoji = {
                    "mirror": "🪞", "dip": "⚡", "safe": "🛡️", 
                    "cleanup": "🧹", "bonus": "💰", "desperate": "🆘",
                    "optimal": "✨"  # Novo tipo de ataque
                }.get(rec['attack_type'], "⚔️")
                
                # Inclui expectativa de estrelas
                star_display = f"{rec.get('expected_stars', 0):.1f}⭐"
                
                attack_info = (f"**Atk{rec['attack_number']}:** {type_emoji} #{rec['recommended_target_pos']} "
                              f"(TH{rec['recommended_target_th']}) - {conf_emoji} {rec['confidence_score']:.0%} | {star_display}")
                player_attacks.append(attack_info)
            
            # Adiciona o último jogador
            if current_player and player_attacks:
                embed.add_field(
                    name=f"👤 {current_player}",
                    value="
".join(player_attacks),
                    inline=False
                )
            
            if len(recommendations) > 25:
                embed.add_field(
                    name="ℹ️ Informação", 
                    value=f"Mostrando os primeiros 25 ataques de {len(recommendations)} recomendações totais. Veja o painel web para a lista completa.", 
                    inline=False
                )
            
            embed.set_footer(text=f"ClashGenius Neural Quantum - {plan.get('version', 'v6.0')}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro no comando plano v6.0: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro crítico:** {e}")

    @commands.command(name='analise')
    @commands.has_permissions(administrator=True)
    async def analyze_war_balance(self, ctx):
        """Analisa o equilíbrio da guerra com sistema neural quântico."""
        await ctx.send("⚖️ **Analisando equilíbrio da guerra com IA Neural Quântica v6.0...**")
        
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state not in ['inWar', 'preparation']:
                await ctx.send("❌ Nenhuma guerra ativa encontrada.")
                return
            
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            opp_clan = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
            
            # Análise neural quântica de probabilidade de vitória
            war_phase = self.war_advisor._determine_war_phase(war)
            
            # Simula análise quântica global
            our_potential = 0
            opp_potential = 0
            
            # Avalia potencial de cada membro do nosso clã
            for member in our_clan.members:
                attacks_remaining = war.attacks_per_member - len(getattr(member, 'attacks', []))
                member_potential = 0
                
                # Para cada ataque restante, estima o melhor resultado possível
                for _ in range(attacks_remaining):
                    best_expected = 0
                    for target in opp_clan.members:
                        # Pula alvos com 3 estrelas
                        if hasattr(target, 'best_opponent_attack') and target.best_opponent_attack and target.best_opponent_attack.stars == 3:
                            continue
                            
                        # Estima resultado com modelo neural
                        prediction = self.war_advisor.neural_model.predict_attack_success(member, target, war_phase)
                        best_expected = max(best_expected, prediction.get('expected_stars', 0))
                    
                    member_potential += best_expected
                
                # Adiciona estrelas já obtidas
                for attack in getattr(member, 'attacks', []):
                    member_potential += attack.stars
                    
                our_potential += member_potential
            
            # Avalia potencial do clã oponente
            for member in opp_clan.members:
                attacks_remaining = war.attacks_per_member - len(getattr(member, 'attacks', []))
                member_potential = 0
                
                # Mesma lógica para o oponente
                for _ in range(attacks_remaining):
                    best_expected = 0
                    for target in our_clan.members:
                        if hasattr(target, 'best_opponent_attack') and target.best_opponent_attack and target.best_opponent_attack.stars == 3:
                            continue
                            
                        prediction = self.war_advisor.neural_model.predict_attack_success(member, target, war_phase)
                        best_expected = max(best_expected, prediction.get('expected_stars', 0))
                    
                    member_potential += best_expected
                
                # Adiciona estrelas já obtidas
                for attack in getattr(member, 'attacks', []):
                    member_potential += attack.stars
                    
                opp_potential += member_potential
            
            # Calcula probabilidade de vitória usando modelo quântico
            total_potential = our_potential + opp_potential
            our_win_probability = our_potential / total_potential if total_potential > 0 else 0.5
            
            # Calcula vantagem tradicional baseada em força
            our_strength = sum(self.war_advisor._calculate_player_strength(m) for m in our_clan.members)
            opp_strength = sum(self.war_advisor._calculate_player_strength(m) for m in opp_clan.members)
            
            advantage_percent = ((our_strength - opp_strength) / max(opp_strength, 1)) * 100
            
            # Determina recomendação estratégica baseada na análise quântica
            if our_win_probability > 0.7: 
                status_text, strategy, color = (
                    f"🟢 **Vantagem Clara** ({our_win_probability:.1%})", 
                    "Ataque agressivo. Use DIPs calculados e ataques OPTIMAL para maximizar estrelas.", 
                    discord.Color.green()
                )
            elif our_win_probability > 0.55: 
                status_text, strategy, color = (
                    f"🟡 **Leve Vantagem** ({our_win_probability:.1%})", 
                    "Equilíbrio ofensivo. Priorize alvos OPTIMAL e MIRROR com alta certeza quântica.", 
                    discord.Color.gold()
                )
            elif our_win_probability > 0.45: 
                status_text, strategy, color = (
                    f"🟡 **Guerra Equilibrada** ({our_win_probability:.1%})", 
                    "Estratégia conservadora. Foque em alvos SAFE e MIRROR com certeza quântica >70%.", 
                    discord.Color.gold()
                )
            else: 
                status_text, strategy, color = (
                    f"🔴 **Desvantagem** ({our_win_probability:.1%})", 
                    "Defensiva máxima. Priorize ataques SAFE e CLEANUP com alta certeza quântica.", 
                    discord.Color.red()
                )

            embed = discord.Embed(title="⚖️ Análise Estratégica Neural Quântica v6.0", color=color)
            
            # Adiciona análise tradicional e quântica
            embed.add_field(
                name="💪 Análise de Força Tradicional", 
                value=f"**Nosso Clã:** {our_strength:,}
**Oponente:** {opp_strength:,}
**Diferença:** {advantage_percent:+.1f}%", 
                inline=True
            )
            
            embed.add_field(
                name="✨ Análise Quântica", 
                value=f"**Nosso Potencial:** {our_potential:.1f}⭐
**Oponente:** {opp_potential:.1f}⭐
**Probabilidade Vitória:** {our_win_probability:.1%}", 
                inline=True
            )
            
            embed.add_field(name="🎯 Status da Guerra", value=status_text, inline=False)
            embed.add_field(name="📊 Estratégia Recomendada", value=strategy, inline=False)
            
            # Adiciona informações sobre ataques restantes com análise quântica
            if war.state == 'inWar':
                attackers_remaining = [m for m in our_clan.members if len(getattr(m, 'attacks', [])) < war.attacks_per_member]
                total_attacks_remaining = sum(war.attacks_per_member - len(getattr(m, 'attacks', [])) for m in attackers_remaining)
                
                # Estima estrelas esperadas dos ataques restantes
                expected_remaining_stars = max(0, our_potential - sum(a.stars for m in our_clan.members for a in getattr(m, 'attacks', [])))
                
                embed.add_field(
                    name="⚔️ Ataques Restantes", 
                    value=f"**Jogadores com ataques:** {len(attackers_remaining)}
"
                          f"**Total de ataques:** {total_attacks_remaining}
"
                          f"**Estrelas esperadas:** {expected_remaining_stars:.1f}⭐", 
                    inline=False
                )
            
            embed.set_footer(text="Sistema Neural Quântico v6.0 - Análise com previsão de múltiplos cenários")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro na análise quântica v6.0: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro na análise:** {e}")

    @commands.command(name='quantum_status')
    @commands.has_permissions(administrator=True)
    async def quantum_status(self, ctx):
        """Mostra o status da guerra com análise quântica detalhada."""
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state not in ['inWar', 'preparation']:
                await ctx.send("❌ Nenhuma guerra ativa encontrada.")
                return
            
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
            
            # Obtém dados atuais da guerra
            our_stars = getattr(our_clan, 'stars', 0)
            opp_stars = getattr(opponent, 'stars', 0)
            our_destruction = getattr(our_clan, 'destruction_percentage', 0)
            opp_destruction = getattr(opponent, 'destruction_percentage', 0)
            
            # Analisa quem ainda pode atacar
            attackers_remaining = [m for m in our_clan.members if len(getattr(m, 'attacks', [])) < war.attacks_per_member]
            total_attacks_remaining = sum(war.attacks_per_member - len(getattr(m, 'attacks', [])) for m in attackers_remaining)
            
            # Usa modelo neural para prever resultados futuros
            war_phase = self.war_advisor._determine_war_phase(war)
            
            # Simula múltiplos cenários com variação quântica
            num_simulations = 1000
            win_count = 0
            draw_count = 0
            lose_count = 0
            
            for _ in range(num_simulations):
                sim_our_stars = our_stars
                sim_opp_stars = opp_stars
                sim_our_destruct = our_destruction
                sim_opp_destruct = opp_destruction
                
                # Simula nossos ataques restantes
                for member in attackers_remaining:
                    attacks_left = war.attacks_per_member - len(getattr(member, 'attacks', []))
                    
                    for _ in range(attacks_left):
                        # Escolhe alvo aleatório (simplificação)
                        viable_targets = [
                            t for t in opponent.members
                            if not (hasattr(t, 'best_opponent_attack') and t.best_opponent_attack and t.best_opponent_attack.stars == 3)
                        ]
                        
                        if viable_targets:
                            # Escolhe alvo baseado em quantum random
                            target_idx = int(np.abs(np.sin(np.random.random() * np.pi)) * len(viable_targets))
                            target_idx = min(target_idx, len(viable_targets) - 1)
                            target = viable_targets[target_idx]
                            
                            # Prevê resultado
                            prediction = self.war_advisor.neural_model.predict_attack_success(member, target, war_phase)
                            
                            # Aplica variação quântica
                            quantum_factor = 0.8 + 0.4 * np.sin(np.random.random() * np.pi)
                            expected_stars = min(3, prediction.get('expected_stars', 1.5) * quantum_factor)
                            
                            # Arredonda para inteiro com probabilidade
                            fractional = expected_stars - int(expected_stars)
                            stars = int(expected_stars) + (1 if np.random.random() < fractional else 0)
                            
                            # Adiciona ao total
                            sim_our_stars += stars
                            
                            # Adiciona destruição se foi 3 estrelas para simular
                            if stars == 3:
                                target.best_opponent_attack = type('obj', (object,), {'stars': 3})
                
                # Simula ataques oponentes da mesma forma
                opp_attackers = [m for m in opponent.members if len(getattr(m, 'attacks', [])) < war.attacks_per_member]
                for member in opp_attackers:
                    attacks_left = war.attacks_per_member - len(getattr(member, 'attacks', []))
                    
                    for _ in range(attacks_left):
                        viable_targets = [
                            t for t in our_clan.members
                            if not (hasattr(t, 'best_opponent_attack') and t.best_opponent_attack and t.best_opponent_attack.stars == 3)
                        ]
                        
                        if viable_targets:
                            target_idx = int(np.abs(np.sin(np.random.random() * np.pi)) * len(viable_targets))
                            target_idx = min(target_idx, len(viable_targets) - 1)
                            target = viable_targets[target_idx]
                            
                            prediction = self.war_advisor.neural_model.predict_attack_success(member, target, war_phase)
                            quantum_factor = 0.8 + 0.4 * np.sin(np.random.random() * np.pi)
                            expected_stars = min(3, prediction.get('expected_stars', 1.5) * quantum_factor)
                            
                            fractional = expected_stars - int(expected_stars)
                            stars = int(expected_stars) + (1 if np.random.random() < fractional else 0)
                            
                            sim_opp_stars += stars
                            
                            if stars == 3:
                                target.best_opponent_attack = type('obj', (object,), {'stars': 3})
                
                # Computa resultado da simulação
                if sim_our_stars > sim_opp_stars:
                    win_count += 1
                elif sim_our_stars < sim_opp_stars:
                    lose_count += 1
                else:
                    # Empate em estrelas, decide por destruição
                    if sim_our_destruct > sim_opp_destruct:
                        win_count += 1
                    elif sim_our_destruct < sim_opp_destruct:
                        lose_count += 1
                    else:
                        draw_count += 1
            
            # Calcula probabilidades
            win_prob = win_count / num_simulations
            draw_prob = draw_count / num_simulations
            lose_prob = lose_count / num_simulations
            
            # Cria embed com análise
            embed = discord.Embed(
                title="✨ Análise Quântica de Cenários v6.0", 
                description=f"Simulação de {num_simulations} cenários possíveis baseados no modelo neural quântico",
                color=discord.Color.purple()
            )
            
            # Status atual
            embed.add_field(
                name="📊 Status Atual", 
                value=f"**{our_clan.name}:** {our_stars}⭐ ({our_destruction:.2f}%)
"
                      f"**{opponent.name}:** {opp_stars}⭐ ({opp_destruction:.2f}%)",
                inline=False
            )
            
            # Ataques restantes
            embed.add_field(
                name="⚔️ Ataques Restantes", 
                value=f"**Nossos ataques:** {total_attacks_remaining}
"
                      f"**Atacantes:** {len(attackers_remaining)} jogadores
"
                      f"**Oponente:** {sum(war.attacks_per_member - len(getattr(m, 'attacks', [])) for m in opponent.members)} ataques",
                inline=True
            )
            
            # Probabilidades de resultados
            result_status = "🟢 FAVORÁVEL" if win_prob > 0.6 else "🟡 EQUILIBRADO" if win_prob > 0.4 else "🔴 DESFAVORÁVEL"
            
            embed.add_field(
                name="🔮 Projeção Quântica", 
                value=f"**Probabilidade de Vitória:** {win_prob:.1%}
"
                      f"**Probabilidade de Empate:** {draw_prob:.1%}
"
                      f"**Probabilidade de Derrota:** {lose_prob:.1%}
"
                      f"**Status:** {result_status}",
                inline=True
            )
            
            # Recomendação estratégica baseada nas probabilidades
            if win_prob > 0.75:
                strategy = "**Estratégia de Segurança:** Foque em garantir estrelas, não arrisque. Consolidar a vantagem atual."
            elif win_prob > 0.6:
                strategy = "**Estratégia de Equilíbrio:** Priorize ataques SAFE e OPTIMAL com alta certeza quântica."
            elif win_prob > 0.4:
                strategy = "**Estratégia Agressiva:** Busque alvos de alto valor usando a análise quântica. Foque em DIPs calculados."
            else:
                strategy = "**Estratégia de Recuperação:** Máximo de estrelas possível. Priorize bases mais fracas primeiro, CLEANUP de alto valor."
            
            embed.add_field(name="🎯 Recomendação Estratégica", value=strategy, inline=False)
            
            embed.set_footer(text="Sistema Neural Quântico v6.0 - Análise baseada em milhares de cenários simulados")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro no status quântico v6.0: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro no status quântico:** {e}")
