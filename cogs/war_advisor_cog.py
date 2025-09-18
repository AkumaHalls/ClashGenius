# -*- coding: utf-8 -*-
"""
Módulo do Conselheiro de Guerra IA - ClashGenius (v4.0 - Melhorado)
Sistema inteligente para análise e geração de planos táticos de guerra.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from discord.ext import commands
import datetime
import pytz

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
    Sistema que analisa a guerra atual e gera planos de ataque táticos inteligentes.
    """
    
    # Constantes de configuração
    STRENGTH_DIFFERENCE_THRESHOLD = 50
    WAR_PHASE_SPLIT_HOURS = 12
    MIN_CONFIDENCE_SCORE = 0.3
    
    def __init__(self):
        self.logger = logging.getLogger("war_advisor_v4.0")
        self._setup_logging()

    def _setup_logging(self):
        """Configura logging específico para o módulo."""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _calculate_player_strength(self, player: Any) -> int:
        """
        Calcula uma pontuação de força mais precisa para um jogador.
        
        Args:
            player: Objeto do jogador
            
        Returns:
            int: Pontuação de força do jogador
        """
        if not player:
            return 0
        
        base_strength = player.town_hall * 100
        
        hero_bonus = 0
        if hasattr(player, 'heroes') and player.heroes:
            hero_bonus = sum(hero.level for hero in player.heroes if hero.is_home_base) * 2
        
        donation_bonus = 0
        if hasattr(player, 'donations') and player.donations:
            donation_bonus = min(player.donations * 0.1, 50) # Cap em 50
        
        return int(base_strength + hero_bonus + donation_bonus)

    def _determine_war_phase(self, war: Any) -> WarPhase:
        """
        Determina a fase atual da guerra de forma mais robusta.
        
        Args:
            war: Objeto da guerra
            
        Returns:
            WarPhase: Fase atual da guerra
        """
        if war.state == 'preparation':
            return WarPhase.PREPARATION
        
        if war.state != 'inWar':
            raise ValueError(f"Estado de guerra inválido: {war.state}")
        
        if not hasattr(war, 'start_time') or not war.start_time.time:
            return WarPhase.PHASE_1
        
        try:
            now = datetime.datetime.now(pytz.utc)
            war_start_time = war.start_time.time.replace(tzinfo=pytz.utc)
            hours_passed = (now - war_start_time).total_seconds() / 3600
            
            return WarPhase.PHASE_1 if hours_passed < self.WAR_PHASE_SPLIT_HOURS else WarPhase.PHASE_2
        except Exception as e:
            self.logger.warning(f"Erro ao calcular fase da guerra: {e}. Usando PHASE_1 como fallback.")
            return WarPhase.PHASE_1

    def _generate_provisional_plan(self, our_clan: Any) -> List[AttackRecommendation]:
        """
        Gera um plano preliminar mais inteligente para o dia de preparação.
        
        Args:
            our_clan: Nosso clã
            
        Returns:
            List[AttackRecommendation]: Lista de recomendações preliminares
        """
        recommendations = []
        
        for member in sorted(our_clan.members, key=lambda m: m.map_position):
            if member.attacks: # Skip membros que já atacaram
                continue
                
            rec = AttackRecommendation(
                member_name=member.name,
                member_th=member.town_hall,
                member_pos=member.map_position,
                attack_number=1,
                attack_type=AttackType.MIRROR,
                recommended_target_pos=member.map_position,
                recommended_target_th=member.town_hall, # Estimativa
                justification="Plano preliminar: prepare-se para atacar seu espelho. Será refinado no início da guerra.",
                confidence_score=0.5, # Confiança média para planos preliminares
                alternative_targets=[max(1, member.map_position - 1), member.map_position + 1]
            )
            recommendations.append(rec)
            
        return recommendations

    def _find_optimal_target(self, attacker: Any, opponent_members: List[Any], 
                           assigned_targets: set, attack_type: AttackType) -> Optional[Any]:
        """
        Encontra o alvo ótimo baseado no tipo de ataque e força do atacante.
        """
        attacker_strength = self._calculate_player_strength(attacker)
        available_targets = [
            m for m in opponent_members 
            if m.map_position not in assigned_targets
        ]
        
        if not available_targets:
            return None
        
        if attack_type == AttackType.DIP:
            suitable_targets = [
                t for t in available_targets 
                if self._calculate_player_strength(t) < attacker_strength
            ]
            return max(suitable_targets, key=self._calculate_player_strength) if suitable_targets else None
            
        elif attack_type == AttackType.SAFE:
            return min(available_targets, key=self._calculate_player_strength)
            
        else: # MIRROR
            mirror_pos = attacker.map_position
            mirror_target = next((t for t in available_targets if t.map_position == mirror_pos), None)
            
            if mirror_target:
                return mirror_target
            
            return min(available_targets, key=lambda t: abs(t.map_position - mirror_pos))

    def _calculate_confidence_score(self, attacker: Any, target: Any, attack_type: AttackType) -> float:
        """
        Calcula uma pontuação de confiança para a recomendação.
        """
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        
        strength_ratio = attacker_strength / max(target_strength, 1)
        
        if attack_type == AttackType.DIP:
            return min(0.9, max(0.3, (strength_ratio - 1.0) * 0.5 + 0.5))
        elif attack_type == AttackType.SAFE:
            return min(0.95, max(0.6, strength_ratio * 0.4 + 0.3))
        else: # MIRROR
            diff = abs(strength_ratio - 1.0)
            return max(0.4, 0.8 - diff * 0.3)

    def _generate_phase1_recommendations(self, our_clan: Any, opponent: Any) -> List[AttackRecommendation]:
        """
        Gera recomendações táticas melhoradas para a primeira fase da guerra.
        """
        recommendations = []
        opponent_map = {m.map_position: m for m in opponent.members}
        assigned_targets = set()

        for member in sorted(our_clan.members, key=lambda m: m.map_position):
            if member.attacks:
                continue

            member_strength = self._calculate_player_strength(member)
            mirror = opponent_map.get(member.map_position)
            
            if not mirror:
                self.logger.warning(f"Espelho não encontrado para {member.name} (pos: {member.map_position})")
                continue

            mirror_strength = self._calculate_player_strength(mirror)
            attack_type = AttackType.MIRROR # Default
            target = None

            strength_diff = member_strength - mirror_strength

            if strength_diff > self.STRENGTH_DIFFERENCE_THRESHOLD:
                attack_type = AttackType.DIP
                target = self._find_optimal_target(member, opponent.members, assigned_targets, AttackType.DIP)
                
            elif strength_diff < -self.STRENGTH_DIFFERENCE_THRESHOLD:
                attack_type = AttackType.SAFE
                target = self._find_optimal_target(member, opponent.members, assigned_targets, AttackType.SAFE)

            if not target:
                attack_type = AttackType.MIRROR
                target = self._find_optimal_target(member, opponent.members, assigned_targets, AttackType.MIRROR)

            if target and target.map_position not in assigned_targets:
                confidence = self._calculate_confidence_score(member, target, attack_type)
                
                alternative_targets = []
                for alt_target in opponent.members:
                    if (alt_target.map_position != target.map_position and 
                        alt_target.map_position not in assigned_targets):
                        alternative_targets.append(alt_target.map_position)
                alternative_targets = sorted(alternative_targets)[:2] # Máximo 2 alternativas

                justifications = {
                    AttackType.DIP: f"Você tem vantagem significativa (+{int(strength_diff)}). Ataque um alvo forte para aliviar o time.",
                    AttackType.SAFE: f"Seu espelho é mais forte (-{int(abs(strength_diff))}). Garanta 3 estrelas num alvo mais acessível.",
                    AttackType.MIRROR: "Ataque equilibrado no seu espelho. Objetivo: mínimo 2 estrelas, idealmente 3."
                }

                rec = AttackRecommendation(
                    member_name=member.name, member_th=member.town_hall,
                    member_pos=member.map_position, attack_number=1,
                    attack_type=attack_type, recommended_target_pos=target.map_position,
                    recommended_target_th=target.town_hall, justification=justifications[attack_type],
                    confidence_score=confidence, alternative_targets=alternative_targets
                )
                
                assigned_targets.add(target.map_position)
                recommendations.append(rec)

        return recommendations

    def _get_cleanup_targets(self, war: Any, opponent: Any) -> List[Dict[str, Any]]:
        """
        Identifica alvos que precisam de limpeza de forma mais eficiente.
        """
        three_starred_tags = {a.defender_tag for a in war.attacks if a.stars == 3}
        
        cleanup_targets = []
        for member in opponent.members:
            if member.tag in three_starred_tags or not member.defenses:
                continue
            
            best_defense = max(member.defenses, key=lambda d: d.stars)
            if 1 <= best_defense.stars < 3:
                priority_score = (best_defense.stars * 1000) - best_defense.destruction
                cleanup_targets.append({
                    "position": member.map_position, "stars": best_defense.stars,
                    "destruction": best_defense.destruction, "tag": member.tag,
                    "th": member.town_hall, "priority": priority_score
                })
        
        cleanup_targets.sort(key=lambda x: x['priority'])
        return cleanup_targets

    def _generate_phase2_recommendations(self, war: Any, our_clan: Any, opponent: Any) -> List[AttackRecommendation]:
        """
        Gera recomendações melhoradas para a segunda fase (limpeza).
        """
        recommendations = []
        cleanup_targets = self._get_cleanup_targets(war, opponent)
        
        available_attackers = [
            m for m in our_clan.members 
            if len(m.attacks) < war.attacks_per_member
        ]
        available_attackers.sort(key=self._calculate_player_strength, reverse=True)

        for member in available_attackers:
            attack_num = len(member.attacks) + 1
            
            if cleanup_targets:
                target = cleanup_targets.pop(0)
                confidence = 0.8 if target['stars'] == 1 else 0.6
                
                rec = AttackRecommendation(
                    member_name=member.name, member_th=member.town_hall,
                    member_pos=member.map_position, attack_number=attack_num,
                    attack_type=AttackType.CLEANUP, recommended_target_pos=target["position"],
                    recommended_target_th=target["th"],
                    justification=f"LIMPEZA CRÍTICA no #{target['position']} ({target['stars']}★ {target['destruction']}%). A 3ª estrela é fundamental!",
                    confidence_score=confidence
                )
            else:
                safe_target_pos = min(member.map_position + 2, len(opponent.members))
                safe_target = next(
                    (m for m in opponent.members if m.map_position == safe_target_pos),
                    opponent.members[-1] # Fallback
                )
                
                rec = AttackRecommendation(
                    member_name=member.name, member_th=member.town_hall,
                    member_pos=member.map_position, attack_number=attack_num,
                    attack_type=AttackType.SAFE, recommended_target_pos=safe_target.map_position,
                    recommended_target_th=safe_target.town_hall,
                    justification="Sem alvos para limpeza. Ataque seguro para garantir estrelas adicionais.",
                    confidence_score=0.7
                )
            
            recommendations.append(rec)
            
        return recommendations

    def create_war_plan(self, war: Any, clan_tag: str, prediction_data: Dict) -> Dict[str, Any]:
        """
        Ponto de entrada principal para gerar o plano de guerra com melhorias significativas.
        """
        if not war or war.state not in ['inWar', 'preparation']:
            return {
                "success": False, "error": "A guerra não está ativa ou em preparação.",
                "error_code": "INVALID_WAR_STATE"
            }

        try:
            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan
            
            if not our_clan or not opponent:
                return {
                    "success": False, "error": "Erro ao identificar os clãs da guerra.",
                    "error_code": "CLAN_IDENTIFICATION_ERROR"
                }
            
            war_phase = self._determine_war_phase(war)
            
            if war_phase == WarPhase.PREPARATION:
                phase_title = "Plano Preliminar - Preparação"
                recommendations = self._generate_provisional_plan(our_clan)
                status = "provisional"
                if not opponent.members:
                    phase_title += " (Será refinado no início da guerra)"
                    
            elif war_phase == WarPhase.PHASE_1:
                phase_title = "Fase 1 - Ataques Iniciais Táticos"
                recommendations = self._generate_phase1_recommendations(our_clan, opponent)
                status = "active"
                
            else: # WarPhase.PHASE_2
                phase_title = "Fase 2 - Limpeza e Finalização"
                recommendations = self._generate_phase2_recommendations(war, our_clan, opponent)
                status = "cleanup"

            recommendations.sort(key=lambda x: x.member_pos)
            
            recommendations_dict = [
                {
                    "member_name": r.member_name, "member_th": r.member_th,
                    "member_pos": r.member_pos, "attack_number": r.attack_number,
                    "type": r.attack_type.value, "recommended_target_pos": r.recommended_target_pos,
                    "recommended_target_th": r.recommended_target_th, "justification": r.justification,
                    "confidence_score": r.confidence_score, "alternative_targets": r.alternative_targets
                }
                for r in recommendations
            ]
            
            total_recommendations = len(recommendations_dict)
            high_confidence_count = len([r for r in recommendations if r.confidence_score >= 0.7])
            avg_confidence = sum(r.confidence_score for r in recommendations) / max(total_recommendations, 1)
            
            return {
                "success": True, "clan_name": our_clan.name,
                "opponent_name": opponent.name, "war_phase": war_phase.value,
                "phase_title": phase_title, "recommendations": recommendations_dict,
                "status": status,
                "statistics": {
                    "total_recommendations": total_recommendations,
                    "high_confidence_attacks": high_confidence_count,
                    "average_confidence": round(avg_confidence, 2)
                },
                "prediction_summary": prediction_data.get("summary_panel", "Análise em andamento..."),
                "generated_at": datetime.datetime.now(pytz.utc).isoformat()
            }

        except Exception as e:
            self.logger.error(f"Erro crítico ao gerar plano de guerra: {e}", exc_info=True)
            return {
                "success": False, "error": "Erro interno ao processar dados da guerra.",
                "error_code": "INTERNAL_PROCESSING_ERROR",
                "details": str(e) if self.logger.level <= logging.DEBUG else None
            }


class WarAdvisorCog(commands.Cog, name="Conselheiro de Guerra IA"):
    """Cog do Discord para o sistema de conselheiro de guerra."""
    
    def __init__(self, bot):
        self.bot = bot
        self.war_advisor = WarAdvisorSystem()
        self.logger = logging.getLogger(f"{__name__}.WarAdvisorCog")

    async def cog_load(self):
        """Executado quando o cog é carregado."""
        self.logger.info("War Advisor Cog carregado com sucesso!")

    async def cog_unload(self):
        """Executado quando o cog é descarregado."""
        self.logger.info("War Advisor Cog descarregado.")

async def setup(bot: commands.Bot):
    """Setup function para carregar o cog."""
    await bot.add_cog(WarAdvisorCog(bot))

