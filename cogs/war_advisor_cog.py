# -*- coding: utf-8 -*-
"""
Módulo do Conselheiro de Guerra IA - ClashGenius (v5.4 - CORREÇÕES CRÍTICAS)
Sistema inteligente para análise e geração de planos táticos de guerra.
CORREÇÕES: Lógica de DIP completamente reescrita, verificação de heróis melhorada,
validação de diferenças de posição no mapa, e sistema de fallback mais inteligente.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from discord.ext import commands
import datetime
import pytz
import discord

class AttackType(Enum):
    """Tipos de ataque disponíveis."""
    MIRROR = "mirror"
    DIP = "dip"
    SAFE = "safe"
    CLEANUP = "cleanup"

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

class WarAdvisorSystem:
    """
    Sistema inteligente que analisa a guerra atual e gera planos de ataque táticos.
    """
    
    # Constantes de configuração corrigidas
    MAX_TH_DIFFERENCE_UP = 1  # Máximo 1 CV acima
    MAX_TH_DIFFERENCE_DOWN = 2  # Máximo 2 CVs abaixo (reduzido de 3)
    MAX_POSITION_DIFFERENCE_UP = 3  # Máximo 3 posições acima no mapa
    MAX_POSITION_DIFFERENCE_DOWN = 5  # Máximo 5 posições abaixo no mapa
    STRENGTH_ADVANTAGE_THRESHOLD = 200  # Aumentado para ser mais conservador
    STRENGTH_DISADVANTAGE_THRESHOLD = -50  # Mais rigoroso
    WAR_PHASE_SPLIT_HOURS = 12
    MIN_CONFIDENCE_SCORE = 0.5  # Aumentado
    
    def __init__(self):
        self.logger = logging.getLogger("war_advisor_v5.4")
        self._setup_logging()

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
        
        # Base de força por CV (valores ajustados)
        th_multipliers = {
            1: 10, 2: 20, 3: 40, 4: 80, 5: 120, 6: 180, 7: 250, 8: 350, 9: 500, 
            10: 700, 11: 950, 12: 1250, 13: 1600, 14: 2000, 15: 2500, 16: 3100, 17: 3800
        }
        base_strength = th_multipliers.get(player.town_hall, player.town_hall * 100)
        
        # Cálculo aprimorado de força dos heróis
        hero_bonus = 0
        hero_penalty = 0
        
        if hasattr(player, 'heroes') and player.heroes:
            for hero in player.heroes:
                if hero.is_home_base:  # Apenas heróis da vila principal
                    hero_multiplier = max(1, player.town_hall // 3)
                    
                    if hero.is_upgrading:
                        # PENALIDADE SEVERA para heróis em upgrade
                        hero_penalty += hero.level * hero_multiplier * 0.8
                        self.logger.debug(f"Herói {hero.name} em upgrade - penalidade aplicada")
                    else:
                        # Bônus para heróis disponíveis
                        hero_bonus += hero.level * hero_multiplier
        
        final_strength = int(base_strength + hero_bonus - hero_penalty)
        self.logger.debug(f"Força calculada para {player.name if hasattr(player, 'name') else 'jogador'}: {final_strength} (base: {base_strength}, heróis: +{hero_bonus}, penalidade: -{hero_penalty})")
        
        return final_strength

    def _is_viable_target(self, attacker: Any, target: Any, flexible_rules: bool = False) -> Tuple[bool, str]:
        """Verifica se um alvo é viável com validações aprimoradas."""
        attacker_th = attacker.town_hall
        target_th = target.town_hall
        attacker_pos = attacker.map_position
        target_pos = target.map_position
        
        # Verificação de CV
        if target_th > attacker_th + self.MAX_TH_DIFFERENCE_UP:
            return False, f"Alvo muito superior (TH{target_th} vs TH{attacker_th})"
        
        if not flexible_rules and target_th < attacker_th - self.MAX_TH_DIFFERENCE_DOWN:
            return False, f"Alvo muito inferior (desperdício de potencial)"
        
        # NOVA VERIFICAÇÃO: Diferença de posição no mapa
        position_diff = target_pos - attacker_pos
        if not flexible_rules:
            if position_diff > self.MAX_POSITION_DIFFERENCE_UP:
                return False, f"Alvo muito superior no mapa (#{target_pos} vs #{attacker_pos})"
            if position_diff < -self.MAX_POSITION_DIFFERENCE_DOWN:
                return False, f"Alvo muito inferior no mapa (#{target_pos} vs #{attacker_pos})"
        
        # Verificação de 3 estrelas
        if hasattr(target, 'best_opponent_attack') and target.best_opponent_attack and target.best_opponent_attack.stars == 3:
            return False, "Alvo já possui 3 estrelas"
        
        # Verificação de força relativa
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        strength_ratio = attacker_strength / max(target_strength, 1)
        
        if not flexible_rules and strength_ratio < 0.6:
            return False, f"Força insuficiente (ratio: {strength_ratio:.2f})"
        
        return True, "Alvo viável"

    def _determine_war_phase(self, war: Any) -> WarPhase:
        if war.state == 'preparation': return WarPhase.PREPARATION
        if war.state != 'inWar': return WarPhase.PHASE_1
        
        try:
            now = datetime.datetime.now(pytz.utc)
            war_start_time = war.start_time.time.replace(tzinfo=pytz.utc)
            hours_passed = (now - war_start_time).total_seconds() / 3600
            return WarPhase.PHASE_1 if hours_passed < self.WAR_PHASE_SPLIT_HOURS else WarPhase.PHASE_2
        except Exception:
            return WarPhase.PHASE_1

    def _get_viable_targets(self, opponent_members: List[Any], assigned_targets: set, attacker: Any, flexible_rules: bool = False) -> List[Any]:
        """Obtém alvos viáveis com logging detalhado."""
        viable_targets = []
        for member in opponent_members:
            if member.map_position in assigned_targets: 
                continue
            
            is_viable, reason = self._is_viable_target(attacker, member, flexible_rules=flexible_rules)
            if is_viable:
                viable_targets.append(member)
            else:
                self.logger.debug(f"Alvo #{member.map_position} (TH{member.town_hall}) não viável para {attacker.name} (TH{attacker.town_hall}, #{attacker.map_position}): {reason}")
        
        self.logger.info(f"{attacker.name}: {len(viable_targets)} alvos viáveis encontrados (flexible: {flexible_rules})")
        return viable_targets

    def _find_optimal_target(self, attacker: Any, viable_targets: List[Any], attack_type: AttackType) -> Optional[Any]:
        """Encontra o alvo ótimo com lógica completamente reescrita."""
        if not viable_targets: 
            return None
        
        attacker_strength = self._calculate_player_strength(attacker)
        attacker_pos = attacker.map_position
        
        self.logger.debug(f"Buscando alvo {attack_type.value} para {attacker.name} (força: {attacker_strength})")
        
        if attack_type == AttackType.DIP:
            # LÓGICA DE DIP COMPLETAMENTE REESCRITA
            # DIP deve ser um ataque estratégico, não um salto no escuro
            
            # 1. Procura alvos do MESMO CV que sejam mais fortes (rushados/heróis fracos)
            same_th_candidates = [t for t in viable_targets if t.town_hall == attacker.town_hall]
            if same_th_candidates:
                # Pega o mais forte do mesmo CV que ainda seja atacável
                strongest_same_th = max(same_th_candidates, key=self._calculate_player_strength)
                strongest_strength = self._calculate_player_strength(strongest_same_th)
                
                # Só recomenda se tiver vantagem significativa
                if attacker_strength >= strongest_strength * 1.1:
                    self.logger.debug(f"DIP no mesmo CV: {strongest_same_th.map_position} (força: {strongest_strength})")
                    return strongest_same_th
            
            # 2. Se não há bons alvos no mesmo CV, procura 1 CV acima MAS só os mais fracos
            higher_th_candidates = [t for t in viable_targets if t.town_hall == attacker.town_hall + 1]
            if higher_th_candidates:
                # Pega apenas o mais fraco do CV superior
                weakest_higher = min(higher_th_candidates, key=self._calculate_player_strength)
                weakest_strength = self._calculate_player_strength(weakest_higher)
                
                # Só recomenda se tiver chance real de sucesso
                if attacker_strength >= weakest_strength * 0.85:
                    self.logger.debug(f"DIP 1 CV acima: {weakest_higher.map_position} (força: {weakest_strength})")
                    return weakest_higher
            
            # 3. Fallback: pega o alvo mais próximo em força (conservador)
            self.logger.debug("DIP fallback: alvo mais próximo em força")
            return min(viable_targets, key=lambda t: abs(self._calculate_player_strength(t) - attacker_strength))

        elif attack_type == AttackType.SAFE:
            # Para ataques seguros, prioriza alvos mais fracos garantindo 3 estrelas
            safe_candidates = [t for t in viable_targets 
                             if t.town_hall <= attacker.town_hall 
                             and self._calculate_player_strength(t) <= attacker_strength * 0.9]
            
            if safe_candidates:
                # Pega o mais forte entre os seguros (maximiza estrelas sem risco)
                return max(safe_candidates, key=self._calculate_player_strength)
            else:
                # Fallback: o mais fraco disponível
                return min(viable_targets, key=self._calculate_player_strength)
        
        else:  # MIRROR
            # Procura o espelho exato primeiro
            mirror = next((t for t in viable_targets if t.map_position == attacker.map_position), None)
            if mirror:
                self.logger.debug(f"Mirror encontrado: {mirror.map_position}")
                return mirror
            
            # Se não há espelho, pega o alvo mais próximo em posição E força
            def mirror_score(target):
                pos_diff = abs(target.map_position - attacker_pos)
                strength_diff = abs(self._calculate_player_strength(target) - attacker_strength)
                return pos_diff + (strength_diff / 100)  # Normaliza força para peso similar à posição
            
            return min(viable_targets, key=mirror_score)

    def _calculate_confidence_score(self, attacker: Any, target: Any, attack_type: AttackType) -> float:
        """Calcula pontuação de confiança com critérios mais rigorosos."""
        if not target: 
            return 0.3
        
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        strength_ratio = attacker_strength / max(target_strength, 1)
        
        # Base de confiança baseada em força (mais rigorosa)
        if strength_ratio >= 1.3: base_confidence = 0.9
        elif strength_ratio >= 1.2: base_confidence = 0.85
        elif strength_ratio >= 1.1: base_confidence = 0.8
        elif strength_ratio >= 1.0: base_confidence = 0.75
        elif strength_ratio >= 0.9: base_confidence = 0.65
        elif strength_ratio >= 0.8: base_confidence = 0.5
        else: base_confidence = 0.3
        
        # Modificador de CV
        th_diff = target.town_hall - attacker.town_hall
        if th_diff == 0: th_modifier = 1.0
        elif th_diff == 1: th_modifier = 0.7  # Mais rigoroso para CV acima
        elif th_diff == -1: th_modifier = 1.1
        elif th_diff <= -2: th_modifier = 1.15
        else: th_modifier = 0.4  # Muito rigoroso para 2+ CVs acima
        
        # Modificador de posição no mapa
        pos_diff = abs(target.map_position - attacker.map_position)
        if pos_diff <= 2: pos_modifier = 1.0
        elif pos_diff <= 5: pos_modifier = 0.95
        elif pos_diff <= 8: pos_modifier = 0.85
        else: pos_modifier = 0.7
        
        # Modificador de tipo de ataque
        type_modifier = 1.0
        if attack_type == AttackType.MIRROR and target.map_position == attacker.map_position:
            type_modifier = 1.1
        elif attack_type == AttackType.SAFE and strength_ratio > 1.2:
            type_modifier = 1.1
        elif attack_type == AttackType.DIP:
            # DIP é mais arriscado, confiança menor
            if target.town_hall > attacker.town_hall:
                type_modifier = 0.8
            else:
                type_modifier = 0.95
        
        final_confidence = base_confidence * th_modifier * pos_modifier * type_modifier
        result = max(0.3, min(0.95, final_confidence))
        
        self.logger.debug(f"Confiança calculada para {attacker.name} -> #{target.map_position}: {result:.0%} "
                         f"(base: {base_confidence:.2f}, th: {th_modifier:.2f}, pos: {pos_modifier:.2f}, type: {type_modifier:.2f})")
        
        return result

    def _determine_attack_strategy(self, attacker: Any, mirror_target: Optional[Any]) -> AttackType:
        """Determina estratégia de ataque com lógica mais conservadora."""
        if not mirror_target: 
            self.logger.debug(f"Sem espelho para {attacker.name}, estratégia: SAFE")
            return AttackType.SAFE
        
        attacker_strength = self._calculate_player_strength(attacker)
        mirror_strength = self._calculate_player_strength(mirror_target)
        strength_diff = attacker_strength - mirror_strength
        
        # Log da análise
        self.logger.debug(f"Estratégia para {attacker.name}: força {attacker_strength} vs espelho {mirror_strength} (diff: {strength_diff})")
        
        # Se o espelho já é superior em CV, não arriscar DIP
        if mirror_target.town_hall > attacker.town_hall:
            if strength_diff > 0:
                self.logger.debug("Espelho CV superior mas força favorável: MIRROR")
                return AttackType.MIRROR
            else:
                self.logger.debug("Espelho CV superior e força desfavorável: SAFE")
                return AttackType.SAFE
        
        # Decisão baseada em força (thresholds mais conservadores)
        if strength_diff > self.STRENGTH_ADVANTAGE_THRESHOLD:
            self.logger.debug("Grande vantagem de força: DIP")
            return AttackType.DIP
        elif strength_diff < self.STRENGTH_DISADVANTAGE_THRESHOLD:
            self.logger.debug("Desvantagem de força: SAFE")
            return AttackType.SAFE
        else:
            self.logger.debug("Força equilibrada: MIRROR")
            return AttackType.MIRROR

    def _generate_phase1_recommendations(self, war: Any, our_clan: Any, opponent: Any) -> List[AttackRecommendation]:
        """Gera recomendações para fase 1 com validação aprimorada."""
        recommendations = []
        assigned_targets = set()
        
        # Ordena atacantes por força (mais forte primeiro para DIP, depois por posição para equilíbrio)
        sorted_attackers = sorted(
            [m for m in our_clan.members if not m.attacks], 
            key=lambda x: (-self._calculate_player_strength(x), x.map_position)
        )
        
        self.logger.info(f"Gerando recomendações para {len(sorted_attackers)} atacantes")

        for member in sorted_attackers:
            self.logger.debug(f"\n--- Analisando {member.name} (#{member.map_position}, TH{member.town_hall}) ---")
            
            # Encontra o espelho
            mirror = next((m for m in opponent.members if m.map_position == member.map_position), None)
            
            # Determina estratégia
            attack_type = self._determine_attack_strategy(member, mirror)
            
            # Busca alvos viáveis
            viable = self._get_viable_targets(opponent.members, assigned_targets, member)
            if not viable:
                self.logger.warning(f"Nenhum alvo viável para {member.name}. Tentando com regras flexíveis...")
                viable = self._get_viable_targets(opponent.members, assigned_targets, member, flexible_rules=True)
            
            if not viable:
                self.logger.error(f"IMPOSSÍVEL encontrar alvo para {member.name}!")
                continue

            # Encontra o alvo ótimo
            target = self._find_optimal_target(member, viable, attack_type)
            if not target:
                self.logger.error(f"Falha ao encontrar alvo ótimo para {member.name}")
                continue

            # Calcula confiança
            confidence = self._calculate_confidence_score(member, target, attack_type)
            
            # Verifica se a confiança é aceitável
            if confidence < self.MIN_CONFIDENCE_SCORE:
                self.logger.warning(f"Confiança baixa ({confidence:.0%}) para {member.name} -> #{target.map_position}. Tentando SAFE...")
                # Tenta encontrar um alvo mais seguro
                safe_target = self._find_optimal_target(member, viable, AttackType.SAFE)
                if safe_target:
                    safe_confidence = self._calculate_confidence_score(member, safe_target, AttackType.SAFE)
                    if safe_confidence > confidence:
                        target = safe_target
                        attack_type = AttackType.SAFE
                        confidence = safe_confidence

            # Alternativas
            alternatives = sorted(
                [t for t in viable if t.map_position != target.map_position], 
                key=lambda t: abs(self._calculate_player_strength(t) - self._calculate_player_strength(member))
            )
            
            # Cria recomendação
            rec = AttackRecommendation(
                member_name=member.name,
                member_th=member.town_hall,
                member_pos=member.map_position,
                attack_number=1,
                attack_type=attack_type,
                recommended_target_pos=target.map_position,
                recommended_target_th=target.town_hall,
                justification=self._generate_intelligent_justification(member, target, attack_type, mirror),
                confidence_score=confidence,
                alternative_targets=[t.map_position for t in alternatives[:3]]  # Mais alternativas
            )
            
            assigned_targets.add(target.map_position)
            recommendations.append(rec)
            
            self.logger.info(f"✅ {member.name} (#{member.map_position}, TH{member.town_hall}) -> "
                           f"#{target.map_position} (TH{target.town_hall}) - {attack_type.value} - {confidence:.0%}")

        return recommendations

    def _generate_intelligent_justification(self, attacker: Any, target: Any, attack_type: AttackType, mirror: Optional[Any]) -> str:
        """Gera justificativas mais detalhadas e inteligentes."""
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        strength_diff = attacker_strength - target_strength
        is_mirror = target.map_position == attacker.map_position
        pos_diff = target.map_position - attacker.map_position
        
        if attack_type == AttackType.DIP:
            if target.town_hall > attacker.town_hall:
                return f"DIP calculado: Atacando TH{target.town_hall} superior. Sua força (+{strength_diff}) compensa a diferença de CV. Foque na execução!"
            else:
                return f"DIP no TH{target.town_hall}: Alvo forte do mesmo nível (+{strength_diff} força). Libera jogadores mais fracos para espelhos fáceis."
        
        elif attack_type == AttackType.SAFE:
            if mirror and mirror.town_hall > attacker.town_hall:
                return f"Estratégia segura: Seu espelho (TH{mirror.town_hall}) é muito superior. Garantindo 3⭐ no #{target.map_position}."
            elif mirror and self._calculate_player_strength(mirror) > attacker_strength + 100:
                return f"Ataque conservador: Espelho muito forte (+{self._calculate_player_strength(mirror) - attacker_strength}). Priorizando resultado garantido."
            else:
                return f"Ataque seguro: Força superior (+{strength_diff}) garante 3⭐. Posição {pos_diff:+} no mapa mantém equilíbrio."
        
        else:  # MIRROR
            if is_mirror:
                if abs(strength_diff) < 50:
                    return f"Espelho equilibrado: Forças similares ({strength_diff:+}). Vitória depende da estratégia e execução!"
                elif strength_diff > 0:
                    return f"Espelho favorável: Vantagem de {strength_diff} força. Aproveite para 3⭐ com confiança!"
                else:
                    return f"Espelho desafiador: Déficit de {abs(strength_diff)} força. Foque em 2⭐ seguras, 3⭐ se possível."
            else:
                return f"Pseudo-espelho: Seu espelho não estava disponível. #{target.map_position} tem força similar ({strength_diff:+}) mantendo equilíbrio."

    def _get_cleanup_targets(self, opponent: Any) -> List[Dict[str, Any]]:
        """Identifica alvos de limpeza priorizados."""
        targets = []
        for m in opponent.members:
            if hasattr(m, 'best_opponent_attack') and m.best_opponent_attack and 1 <= m.best_opponent_attack.stars < 3:
                # Prioridade: estrelas faltantes > destruição baixa > posição alta
                priority = (3 - m.best_opponent_attack.stars) * 1000 + \
                          (100 - m.best_opponent_attack.destruction) * 10 + \
                          max(0, 50 - m.map_position)
                
                targets.append({
                    "position": m.map_position,
                    "stars": m.best_opponent_attack.stars,
                    "destruction": m.best_opponent_attack.destruction,
                    "th": m.town_hall,
                    "priority": priority
                })
        
        return sorted(targets, key=lambda x: x['priority'], reverse=True)

    def _generate_phase2_recommendations(self, war: Any, our_clan: Any, opponent: Any) -> List[AttackRecommendation]:
        """Gera recomendações para fase 2 (limpeza)."""
        recommendations = []
        cleanup_targets = self._get_cleanup_targets(opponent)
        attackers = sorted(
            [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member], 
            key=self._calculate_player_strength, 
            reverse=True
        )
        assigned = set()

        self.logger.info(f"Fase 2: {len(cleanup_targets)} alvos de limpeza, {len(attackers)} atacantes")

        for member in attackers:
            # Prioriza limpeza
            target_info = next((t for t in cleanup_targets 
                              if t['position'] not in assigned 
                              and self._is_viable_target(member, next(m for m in opponent.members if m.map_position == t['position']))[0]), 
                              None)
            
            if target_info:
                target_obj = next(m for m in opponent.members if m.map_position == target_info['position'])
                rec = AttackRecommendation(
                    member_name=member.name,
                    member_th=member.town_hall,
                    member_pos=member.map_position,
                    attack_number=len(member.attacks) + 1,
                    attack_type=AttackType.CLEANUP,
                    recommended_target_pos=target_info["position"],
                    recommended_target_th=target_info["th"],
                    justification=f"LIMPEZA PRIORITÁRIA! #{target_info['position']} com {'⭐' * target_info['stars']} ({target_info['destruction']}%). Foque no 3⭐!",
                    confidence_score=self._calculate_confidence_score(member, target_obj, AttackType.CLEANUP)
                )
                assigned.add(target_info['position'])
                recommendations.append(rec)
            else:
                # Ataque fresh se não há limpeza viável
                fresh_targets = self._get_viable_targets(opponent.members, assigned, member)
                if fresh_targets:
                    safe_target = self._find_optimal_target(member, fresh_targets, AttackType.SAFE)
                    if safe_target:
                        rec = AttackRecommendation(
                            member_name=member.name,
                            member_th=member.town_hall,
                            member_pos=member.map_position,
                            attack_number=len(member.attacks) + 1,
                            attack_type=AttackType.SAFE,
                            recommended_target_pos=safe_target.map_position,
                            recommended_target_th=safe_target.town_hall,
                            justification="Ataque fresh: Sem limpeza viável. Maximize estrelas totais com ataque seguro.",
                            confidence_score=self._calculate_confidence_score(member, safe_target, AttackType.SAFE)
                        )
                        assigned.add(safe_target.map_position)
                        recommendations.append(rec)

        return recommendations

    def create_war_plan(self, war: Any, clan_tag: str, prediction_data: Dict) -> Dict[str, Any]:
        """Cria plano de guerra com validação aprimorada."""
        if not war or war.state not in ['inWar', 'preparation']:
            return {"success": False, "error": "A guerra não está ativa ou em preparação."}
        
        try:
            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan
            
            if not our_clan or not opponent:
                return {"success": False, "error": "Erro ao identificar os clãs."}
            
            # Determina fase
            war_phase = self._determine_war_phase(war)
            
            # Mapeia fase para função
            phase_map = {
                WarPhase.PREPARATION: ("Fase 1 - Ataques Táticos Inteligentes (v5.4)", self._generate_phase1_recommendations),
                WarPhase.PHASE_1: ("Fase 1 - Ataques Táticos Inteligentes (v5.4)", self._generate_phase1_recommendations),
                WarPhase.PHASE_2: ("Fase 2 - Limpeza Estratégica (v5.4)", self._generate_phase2_recommendations)
            }
            
            phase_title, rec_func = phase_map.get(war_phase)
            
            # Gera recomendações
            self.logger.info(f"Gerando plano para fase: {war_phase}")
            recommendations = rec_func(war, our_clan, opponent)

            # Filtra recomendações com confiança muito baixa
            filtered_recommendations = [r for r in recommendations if r.confidence_score >= self.MIN_CONFIDENCE_SCORE]
            
            if len(filtered_recommendations) < len(recommendations):
                self.logger.warning(f"Filtradas {len(recommendations) - len(filtered_recommendations)} recomendações com confiança baixa")

            if not filtered_recommendations:
                return {
                    "success": True, 
                    "phase_title": "Análise Completa - Situação Complexa", 
                    "recommendations": [],
                    "warning": "Nenhuma recomendação com confiança adequada encontrada. Revise manualmente."
                }

            # Ordena por posição no mapa
            filtered_recommendations.sort(key=lambda x: x.member_pos)
            
            # Calcula estatísticas
            avg_conf = sum(r.confidence_score for r in filtered_recommendations) / len(filtered_recommendations)
            
            # Log do resumo
            self.logger.info(f"Plano v5.4 gerado: {len(filtered_recommendations)} recomendações, confiança média: {avg_conf:.1%}")
            
            # Converte para dicionário
            rec_dict = []
            for r in filtered_recommendations:
                data = r.__dict__.copy()
                data['attack_type'] = r.attack_type.value
                rec_dict.append(data)

            return {
                "success": True,
                "phase_title": phase_title,
                "recommendations": rec_dict,
                "prediction_summary": prediction_data.get("summary_panel", "Análise em andamento..."),
                "generated_at": datetime.datetime.now(pytz.utc).isoformat(),
                "statistics": {
                    "total_recommendations": len(rec_dict),
                    "filtered_recommendations": len(recommendations) - len(filtered_recommendations),
                    "average_confidence": avg_conf,
                    "attack_types": {t.value: sum(1 for r in rec_dict if r['attack_type'] == t.value) for t in AttackType}
                },
                "version": "5.4 - Correções Críticas"
            }

        except Exception as e:
            self.logger.error(f"Erro crítico ao gerar plano de guerra v5.4: {e}", exc_info=True)
            return {"success": False, "error": f"Erro interno: {e}"}


class WarAdvisorCog(commands.Cog, name="Conselheiro de Guerra IA v5.4"):
    """Cog do Discord para o sistema de conselheiro de guerra corrigido."""
    
    def __init__(self, bot):
        self.bot = bot
        self.war_advisor = WarAdvisorSystem()
        self.logger = logging.getLogger(f"{__name__}.WarAdvisorCog")

    @commands.command(name='plano')
    @commands.has_permissions(administrator=True)
    async def force_plan_generation(self, ctx):
        """Gera plano de guerra com sistema corrigido."""
        await ctx.send("🔄 **Gerando plano de guerra v5.4 (Sistema Corrigido)...**")
        
        try:
            # Busca dados da guerra
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            prediction = await self.bot.war_prediction_system.predict_war_outcome(war, self.bot.clan_tag)
            
            # Gera plano
            plan = self.war_advisor.create_war_plan(war, self.bot.clan_tag, prediction)

            if not plan.get("success"):
                await ctx.send(f"❌ **Erro:** {plan.get('error')}")
                return
            
            # Cria embed principal
            embed = discord.Embed(
                title=f"🎯 {plan.get('phase_title')}", 
                description=f"**Sistema v5.4** - Correções críticas aplicadas:\n" +
                           "• Lógica de DIP reescrita\n" +
                           "• Verificação de heróis em upgrade\n" +
                           "• Validação de diferenças de posição\n" +
                           "• Confiança mínima aumentada",
                color=discord.Color.green()
            )
            
            # Adiciona estatísticas
            stats = plan.get("statistics", {})
            if stats:
                types = stats.get('attack_types', {})
                filtered_count = stats.get('filtered_recommendations', 0)
                
                stats_text = f"**Total:** {stats.get('total_recommendations', 0)}\n"
                stats_text += f"**Confiança Média:** {stats.get('average_confidence', 0):.0%}\n"
                stats_text += f"**Tipos:** Mirror({types.get('mirror',0)}) DIP({types.get('dip',0)}) Safe({types.get('safe',0)})\n"
                
                if filtered_count > 0:
                    stats_text += f"**⚠️ Filtradas:** {filtered_count} (confiança baixa)"
                
                embed.add_field(name="📊 Estatísticas", value=stats_text, inline=False)
            
            # Adiciona aviso se houver
            if plan.get("warning"):
                embed.add_field(name="⚠️ Aviso", value=plan.get("warning"), inline=False)
            
            # Adiciona recomendações (máximo 10 para não estourar limite do embed)
            recommendations = plan.get("recommendations", [])
            for i, rec in enumerate(recommendations[:10]):
                # Emoji baseado na confiança
                if rec['confidence_score'] >= 0.8:
                    emoji = "🟢"
                elif rec['confidence_score'] >= 0.7:
                    emoji = "🟡"
                elif rec['confidence_score'] >= 0.6:
                    emoji = "🟠"
                else:
                    emoji = "🔴"
                
                # Emoji do tipo de ataque
                type_emoji = {
                    "mirror": "🪞",
                    "dip": "⚡",
                    "safe": "🛡️",
                    "cleanup": "🧹"
                }.get(rec['attack_type'], "⚔️")
                
                # Monta o valor do campo
                value = f"**🎯 Alvo:** #{rec['recommended_target_pos']} (TH{rec['recommended_target_th']})\n"
                value += f"**{emoji} Confiança:** {rec['confidence_score']:.0%}\n"
                value += f"**{type_emoji} Tipo:** {rec['attack_type'].upper()}\n"
                value += f"**🤖 IA:** _{rec['justification']}_"
                
                # Adiciona alternativas se existirem
                if rec.get('alternative_targets'):
                    alts = rec['alternative_targets'][:2]  # Máximo 2 alternativas
                    value += f"\n**📋 Alternativas:** #{', #'.join(map(str, alts))}"
                
                embed.add_field(
                    name=f"#{rec['member_pos']} {rec['member_name']} (TH{rec['member_th']})",
                    value=value,
                    inline=False
                )
            
            # Informa se há mais recomendações
            if len(recommendations) > 10:
                embed.add_field(
                    name="ℹ️ Informação", 
                    value=f"Mostrando 10 de {len(recommendations)} recomendações. Use comando específico para ver todas.", 
                    inline=False
                )
            
            # Adiciona rodapé com versão
            embed.set_footer(text=f"ClashGenius v5.4 - {plan.get('version', 'Sistema Corrigido')}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro no comando plano v5.4: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro crítico:** {e}")

    @commands.command(name='analise')
    @commands.has_permissions(administrator=True)
    async def analyze_war_balance(self, ctx):
        """Analisa o equilíbrio da guerra com sistema aprimorado."""
        await ctx.send("⚖️ **Analisando equilíbrio da guerra com IA v5.4...**")
        
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state not in ['inWar', 'preparation']:
                await ctx.send("❌ Nenhuma guerra ativa encontrada.")
                return
            
            # Identifica os clãs
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            opp_clan = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
            
            # Calcula força total (considerando heróis em upgrade)
            our_strength = sum(self.war_advisor._calculate_player_strength(m) for m in our_clan.members)
            opp_strength = sum(self.war_advisor._calculate_player_strength(m) for m in opp_clan.members)
            
            # Calcula vantagem percentual
            advantage_percent = ((our_strength - opp_strength) / opp_strength) * 100
            
            # Analisa distribuição de TH
            our_th_dist = {}
            opp_th_dist = {}
            
            for th in range(17, 0, -1):
                our_count = sum(1 for m in our_clan.members if m.town_hall == th)
                opp_count = sum(1 for m in opp_clan.members if m.town_hall == th)
                
                if our_count > 0 or opp_count > 0:
                    our_th_dist[th] = our_count
                    opp_th_dist[th] = opp_count
            
            # Conta heróis em upgrade
            our_upgrading_heroes = 0
            opp_upgrading_heroes = 0
            
            for member in our_clan.members:
                if hasattr(member, 'heroes') and member.heroes:
                    our_upgrading_heroes += sum(1 for hero in member.heroes if hero.is_home_base and hero.is_upgrading)
            
            for member in opp_clan.members:
                if hasattr(member, 'heroes') and member.heroes:
                    opp_upgrading_heroes += sum(1 for hero in member.heroes if hero.is_home_base and hero.is_upgrading)

            # Cria embed
            embed = discord.Embed(title="⚖️ Análise Estratégica da Guerra v5.4", color=discord.Color.blue())
            
            # Determina status e estratégia
            if advantage_percent > 15:
                status_text = f"🟢 **Vantagem Dominante** (+{advantage_percent:.1f}%)"
                strategy = "Ataques agressivos (DIP). Aproveite para treinar estratégias."
                color = discord.Color.green()
            elif advantage_percent > 8:
                status_text = f"🟢 **Grande Vantagem** (+{advantage_percent:.1f}%)"
                strategy = "Mix de DIP e Mirror. Busque maximizar estrelas."
                color = discord.Color.green()
            elif advantage_percent > 3:
                status_text = f"🟡 **Leve Vantagem** (+{advantage_percent:.1f}%)"
                strategy = "Foco em Mirror com alguns DIPs calculados."
                color = discord.Color.gold()
            elif advantage_percent > -3:
                status_text = f"🟡 **Guerra Equilibrada** ({advantage_percent:+.1f}%)"
                strategy = "Disciplina total. Ataques Mirror e Safe apenas."
                color = discord.Color.gold()
            elif advantage_percent > -8:
                status_text = f"🟠 **Leve Desvantagem** ({advantage_percent:.1f}%)"
                strategy = "Ataques seguros. Priorize 2 estrelas garantidas."
                color = discord.Color.orange()
            else:
                status_text = f"🔴 **Grande Desvantagem** ({advantage_percent:.1f}%)"
                strategy = "Máxima disciplina. Safe e limpeza apenas."
                color = discord.Color.red()
            
            embed.color = color
            
            # Campo de força
            embed.add_field(
                name="💪 Análise de Força",
                value=f"**Nosso Clã:** {our_strength:,}\n" +
                      f"**Oponente:** {opp_strength:,}\n" +
                      f"**Status:** {status_text}",
                inline=True
            )
            
            # Campo de estratégia
            embed.add_field(
                name="🎯 Estratégia Recomendada",
                value=strategy,
                inline=False
            )
            
            # Heróis em upgrade (NOVO)
            if our_upgrading_heroes > 0 or opp_upgrading_heroes > 0:
                hero_text = f"**Nossos heróis em upgrade:** {our_upgrading_heroes}\n"
                hero_text += f"**Heróis inimigos em upgrade:** {opp_upgrading_heroes}\n"
                
                if our_upgrading_heroes > opp_upgrading_heroes:
                    hero_text += "⚠️ **Desvantagem** - Mais heróis nossos indisponíveis"
                elif our_upgrading_heroes < opp_upgrading_heroes:
                    hero_text += "✅ **Vantagem** - Menos heróis nossos indisponíveis"
                else:
                    hero_text += "🟡 **Neutro** - Mesmo número de heróis indisponíveis"
                
                embed.add_field(name="🦸 Status dos Heróis", value=hero_text, inline=False)
            
            # Distribuição de TH
            th_analysis = []
            for th in sorted(set(our_th_dist.keys()) | set(opp_th_dist.keys()), reverse=True):
                our_count = our_th_dist.get(th, 0)
                opp_count = opp_th_dist.get(th, 0)
                
                if our_count > opp_count:
                    indicator = f"✅ +{our_count - opp_count}"
                elif our_count < opp_count:
                    indicator = f"❌ -{opp_count - our_count}"
                else:
                    indicator = "🟡 ="
                
                th_analysis.append(f"**TH{th}:** {our_count} vs {opp_count} {indicator}")
            
            if th_analysis:
                embed.add_field(
                    name="🏰 Distribuição por Town Hall",
                    value="\n".join(th_analysis[:10]),  # Máximo 10 para não estourar
                    inline=False
                )
            
            # Rodapé
            embed.set_footer(text="Sistema v5.4 - Análise considera heróis em upgrade")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro na análise v5.4: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro na análise:** {e}")

    @commands.command(name='debug_player')
    @commands.has_permissions(administrator=True)
    async def debug_player_strength(self, ctx, position: int):
        """Debug da força de um jogador específico."""
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war:
                await ctx.send("❌ Nenhuma guerra ativa.")
                return
            
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            player = next((m for m in our_clan.members if m.map_position == position), None)
            
            if not player:
                await ctx.send(f"❌ Jogador na posição #{position} não encontrado.")
                return
            
            # Calcula força detalhada
            strength = self.war_advisor._calculate_player_strength(player)
            
            # Informações detalhadas
            embed = discord.Embed(
                title=f"🔍 Debug: {player.name}",
                description=f"Posição #{player.map_position} - TH{player.town_hall}",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="💪 Força Total", value=f"{strength:,}", inline=True)
            
            # Heróis
            if hasattr(player, 'heroes') and player.heroes:
                hero_info = []
                hero_bonus = 0
                hero_penalty = 0
                
                for hero in player.heroes:
                    if hero.is_home_base:
                        multiplier = max(1, player.town_hall // 3)
                        if hero.is_upgrading:
                            penalty = hero.level * multiplier * 0.8
                            hero_penalty += penalty
                            hero_info.append(f"❌ {hero.name}: Lv{hero.level} (UPGRADE: -{penalty:.0f})")
                        else:
                            bonus = hero.level * multiplier
                            hero_bonus += bonus
                            hero_info.append(f"✅ {hero.name}: Lv{hero.level} (+{bonus:.0f})")
                
                if hero_info:
                    embed.add_field(
                        name="🦸 Heróis",
                        value="\n".join(hero_info) + f"\n\n**Total Bônus:** +{hero_bonus:.0f}\n**Total Penalidade:** -{hero_penalty:.0f}",
                        inline=False
                    )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro no debug: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro:** {e}")


async def setup(bot: commands.Bot):
    """Configura o cog no bot."""
    await bot.add_cog(WarAdvisorCog(bot))
