# -*- coding: utf-8 -*-
"""
Módulo do Conselheiro de Guerra IA - ClashGenius (v5.8 - API Update October 2025)
Sistema inteligente para análise e geração de planos táticos de guerra.
CORREÇÕES: Adicionado suporte ao CV17 e ao novo herói "Battle Copter".
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from discord.ext import commands
import datetime
import pytz
import discord
from collections import defaultdict

class AttackType(Enum):
    """Tipos de ataque disponíveis."""
    MIRROR = "mirror"
    DIP = "dip"
    SAFE = "safe"
    CLEANUP = "cleanup"
    BONUS = "bonus"
    DESPERATE = "desperate"  # NOVO: Para jogadores muito fracos

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
        self.logger = logging.getLogger("war_advisor_v5.8")
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
        
        # ATUALIZADO: Adicionado multiplicador para o CV17
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
                    # ATUALIZADO: Ajuste no multiplicador para o novo herói
                    if hero.name == "Battle Copter":
                        hero_multiplier = max(1, player.town_hall // 4) # Multiplicador ligeiramente menor
                    else:
                        hero_multiplier = max(1, player.town_hall // 3)

                    if hero.is_upgrading:
                        hero_penalty += hero.level * hero_multiplier * 0.8
                    else:
                        hero_bonus += hero.level * hero_multiplier
        
        final_strength = int(base_strength + hero_bonus - hero_penalty)
        return final_strength

    def _is_viable_target(self, attacker: Any, target: Any, flexible_rules: bool = False, 
                         is_cleanup: bool = False, is_bonus: bool = False, is_desperate: bool = False) -> Tuple[bool, str]:
        """Verifica se um alvo é viável com validações aprimoradas."""
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
        
        # Análise de força (mais flexível para bônus e desesperado)
        if not flexible_rules and not is_cleanup and not is_bonus and not is_desperate:
            attacker_strength = self._calculate_player_strength(attacker)
            target_strength = self._calculate_player_strength(target)
            strength_ratio = attacker_strength / max(target_strength, 1)
            
            if strength_ratio < 0.6:
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

    def _get_viable_targets(self, opponent_members: List[Any], assigned_targets: set, attacker: Any, 
                          flexible_rules: bool = False, is_bonus: bool = False, is_desperate: bool = False, 
                          attacked_bases: set = None) -> List[Any]:
        """Obtém alvos viáveis com logging detalhado."""
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

    def _find_optimal_target(self, attacker: Any, viable_targets: List[Any], attack_type: AttackType) -> Optional[Any]:
        """Encontra o alvo ótimo com base na estratégia."""
        if not viable_targets: 
            return None
        
        attacker_strength = self._calculate_player_strength(attacker)
        
        if attack_type == AttackType.DIP:
            higher_th_candidates = [t for t in viable_targets if t.town_hall == attacker.town_hall + 1]
            if higher_th_candidates:
                weakest_higher = min(higher_th_candidates, key=self._calculate_player_strength)
                if self._calculate_player_strength(weakest_higher) < attacker_strength * 1.15:
                    return weakest_higher
            return min(viable_targets, key=lambda t: abs(self._calculate_player_strength(t) - attacker_strength))

        elif attack_type == AttackType.SAFE:
            safe_candidates = [t for t in viable_targets if self._calculate_player_strength(t) < attacker_strength]
            return max(safe_candidates, key=self._calculate_player_strength) if safe_candidates else min(viable_targets, key=self._calculate_player_strength)
        
        elif attack_type == AttackType.BONUS:
            return min(viable_targets, key=self._calculate_player_strength)
            
        elif attack_type == AttackType.DESPERATE:
            # Para ataques desesperados, escolhe o mais fraco possível
            return min(viable_targets, key=self._calculate_player_strength)

        else:  # MIRROR
            mirror = next((t for t in viable_targets if t.map_position == attacker.map_position), None)
            if mirror: return mirror
            return min(viable_targets, key=lambda t: abs(t.map_position - attacker.map_position))

    def _calculate_confidence_score(self, attacker: Any, target: Any, attack_type: AttackType) -> float:
        """Calcula pontuação de confiança com critérios ajustados."""
        if not target: return 0.3
        
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        strength_ratio = attacker_strength / max(target_strength, 1)
        
        if attack_type == AttackType.DESPERATE:
            # Confiança baixa mas não zero para ataques desesperados
            return 0.4 if strength_ratio >= 0.7 else 0.3
        
        if strength_ratio >= 1.3: base_confidence = 0.9
        elif strength_ratio >= 1.1: base_confidence = 0.8
        elif strength_ratio >= 0.9: base_confidence = 0.65
        elif strength_ratio >= 0.7: base_confidence = 0.5  # Mais flexível
        else: base_confidence = 0.4
        
        th_diff = target.town_hall - attacker.town_hall
        th_modifier = 1.0 if th_diff <= 0 else 0.7 if th_diff == 1 else 0.5  # Mais flexível
        
        final_confidence = base_confidence * th_modifier
        return max(0.3, min(0.95, final_confidence))

    def _determine_attack_strategy(self, attacker: Any, mirror_target: Optional[Any], is_weakest_attacker: bool = False) -> AttackType:
        """Determina estratégia de ataque com lógica conservadora."""
        if not mirror_target:
            return AttackType.BONUS if is_weakest_attacker else AttackType.SAFE

        attacker_strength = self._calculate_player_strength(attacker)
        mirror_strength = self._calculate_player_strength(mirror_target)
        strength_diff = attacker_strength - mirror_strength
        
        if is_weakest_attacker and strength_diff < self.STRENGTH_DISADVANTAGE_THRESHOLD:
            return AttackType.BONUS
        
        if mirror_target.town_hall > attacker.town_hall: return AttackType.SAFE
        if strength_diff > self.STRENGTH_ADVANTAGE_THRESHOLD: return AttackType.DIP
        if strength_diff < self.STRENGTH_DISADVANTAGE_THRESHOLD: return AttackType.SAFE
        return AttackType.MIRROR

    def _generate_phase1_recommendations(self, war: Any, our_clan: Any, opponent: Any) -> List[AttackRecommendation]:
        """Gera recomendações para fase 1 com validação aprimorada."""
        recommendations = []
        assigned_targets = set()
        
        all_attackers_strength = sorted([m for m in our_clan.members if not m.attacks], key=self._calculate_player_strength)
        weakest_attacker_tags = {m.tag for m in all_attackers_strength[:3]}

        sorted_attackers = sorted(
            [m for m in our_clan.members if not m.attacks], 
            key=lambda x: (-self._calculate_player_strength(x), x.map_position)
        )
        
        for member in sorted_attackers:
            is_weakest = member.tag in weakest_attacker_tags
            mirror = next((m for m in opponent.members if m.map_position == member.map_position), None)
            attack_type = self._determine_attack_strategy(member, mirror, is_weakest_attacker=is_weakest)
            
            is_bonus_attack = attack_type == AttackType.BONUS
            viable = self._get_viable_targets(opponent.members, assigned_targets, member, is_bonus=is_bonus_attack)
            if not viable:
                viable = self._get_viable_targets(opponent.members, assigned_targets, member, flexible_rules=True, is_bonus=is_bonus_attack)
            if not viable: continue

            target = self._find_optimal_target(member, viable, attack_type)
            if not target: continue

            confidence = self._calculate_confidence_score(member, target, attack_type)
            
            alternatives = sorted([t for t in viable if t.map_position != target.map_position], 
                                  key=lambda t: abs(self._calculate_player_strength(t) - self._calculate_player_strength(member)))
            
            rec = AttackRecommendation(
                member_name=member.name, member_th=member.town_hall, member_pos=member.map_position,
                attack_number=1, attack_type=attack_type, recommended_target_pos=target.map_position,
                recommended_target_th=target.town_hall,
                justification=self._generate_intelligent_justification(member, target, attack_type, mirror),
                confidence_score=confidence, alternative_targets=[t.map_position for t in alternatives[:3]]
            )
            
            assigned_targets.add(target.map_position)
            recommendations.append(rec)

        return recommendations

    def _generate_intelligent_justification(self, attacker: Any, target: Any, attack_type: AttackType, mirror: Optional[Any]) -> str:
        """Gera justificativas mais detalhadas e inteligentes."""
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        strength_diff = attacker_strength - target_strength
        
        if attack_type == AttackType.DIP:
            return f"DIP calculado: Sua força (+{strength_diff}) permite atacar um alvo superior e liberar jogadores mais fracos."
        elif attack_type == AttackType.SAFE:
            if mirror and self._calculate_player_strength(mirror) > attacker_strength:
                return f"Estratégia segura: Seu espelho é muito forte. Garanta 3⭐ no #{target.map_position}."
            return f"Ataque seguro: Força superior (+{strength_diff}) para garantir 3⭐ e manter o equilíbrio."
        elif attack_type == AttackType.BONUS:
            return f"Ataque para bônus: Como um dos CVs mais baixos, seu objetivo é garantir estrelas no alvo mais fraco disponível (#{target.map_position})."
        elif attack_type == AttackType.DESPERATE:
            return f"Ataque desesperado: Suas opções são limitadas. Foque em conseguir pelo menos 1-2⭐ no #{target.map_position}."
        else: # MIRROR
            if target.map_position == attacker.map_position:
                return f"Espelho ({strength_diff:+} de força): O alvo ideal para sua posição e força."
            return f"Pseudo-espelho: Alvo mais próximo em força ({strength_diff:+}) e posição."

    def _get_cleanup_targets(self, opponent: Any) -> List[Dict[str, Any]]:
        """Identifica alvos de limpeza priorizados."""
        targets = []
        for m in opponent.members:
            if hasattr(m, 'best_opponent_attack') and m.best_opponent_attack and 1 <= m.best_opponent_attack.stars < 3:
                priority = (3 - m.best_opponent_attack.stars) * 1000 + (100 - m.best_opponent_attack.destruction)
                targets.append({
                    "position": m.map_position, "tag": m.tag, "stars": m.best_opponent_attack.stars,
                    "destruction": m.best_opponent_attack.destruction, "th": m.town_hall, "priority": priority
                })
        return sorted(targets, key=lambda x: x['priority'], reverse=True)

    def _generate_phase2_recommendations(self, war: Any, our_clan: Any, opponent: Any) -> List[AttackRecommendation]:
        """Gera recomendações para fase 2 - VERSÃO CORRIGIDA que garante recomendações para TODOS."""
        recommendations = []
        cleanup_targets = self._get_cleanup_targets(opponent)
        
        # Identifica TODOS os atacantes com ataques restantes
        attackers_remaining = [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member]
        total_attacks_remaining = sum(war.attacks_per_member - len(m.attacks) for m in attackers_remaining)
        
        self.logger.info(f"FASE 2: {len(attackers_remaining)} jogadores com {total_attacks_remaining} ataques restantes")
        
        # Identifica os 3 mais fracos entre TODOS os que ainda têm ataques
        all_attackers_strength = sorted(attackers_remaining, key=self._calculate_player_strength)
        weakest_attacker_tags = {m.tag for m in all_attackers_strength[:3]}

        # Ordena atacantes por força (mais fortes primeiro para pegar os melhores alvos)
        sorted_attackers = sorted(attackers_remaining, key=self._calculate_player_strength, reverse=True)
        
        assigned_targets = set()

        # Mapeia bases já atacadas por cada jogador
        attacked_bases_by_player = defaultdict(set)
        for m in our_clan.members:
            for a in m.attacks:
                attacked_bases_by_player[m.tag].add(a.defender_tag)

        # Processa CADA atacante individualmente
        for member in sorted_attackers:
            is_weakest = member.tag in weakest_attacker_tags
            attacks_needed = war.attacks_per_member - len(member.attacks)
            
            self.logger.info(f"Processando {member.name} (TH{member.town_hall}) - {attacks_needed} ataques restantes")
            
            # Gera recomendação para CADA ataque restante
            for attack_num in range(attacks_needed):
                current_attack_number = len(member.attacks) + attack_num + 1
                target_found = False
                
                # ESTRATÉGIA 1: Tenta encontrar alvo de LIMPEZA primeiro
                for potential_target in cleanup_targets:
                    target_pos = potential_target['position']
                    if target_pos in assigned_targets or potential_target['tag'] in attacked_bases_by_player[member.tag]:
                        continue

                    target_obj = next((m for m in opponent.members if m.map_position == target_pos), None)
                    if target_obj and self._is_viable_target(member, target_obj, is_cleanup=True)[0]:
                        rec = AttackRecommendation(
                            member_name=member.name, member_th=member.town_hall, member_pos=member.map_position,
                            attack_number=current_attack_number, attack_type=AttackType.CLEANUP,
                            recommended_target_pos=potential_target["position"], recommended_target_th=potential_target["th"],
                            justification=f"LIMPEZA! #{potential_target['position']} com {'⭐' * potential_target['stars']} ({potential_target['destruction']}%)",
                            confidence_score=self._calculate_confidence_score(member, target_obj, AttackType.CLEANUP)
                        )
                        assigned_targets.add(potential_target['position'])
                        recommendations.append(rec)
                        target_found = True
                        break

                # ESTRATÉGIA 2: Se não há limpeza, busca alvo FRESH
                if not target_found:
                    attack_type = AttackType.BONUS if is_weakest else AttackType.SAFE
                    
                    # Tenta alvos normais primeiro
                    viable_targets = self._get_viable_targets(
                        opponent.members, assigned_targets, member, 
                        is_bonus=is_weakest, attacked_bases=attacked_bases_by_player[member.tag]
                    )
                    
                    # Se não tem alvos normais, tenta flexível
                    if not viable_targets:
                        viable_targets = self._get_viable_targets(
                            opponent.members, assigned_targets, member, 
                            flexible_rules=True, is_bonus=is_weakest, 
                            attacked_bases=attacked_bases_by_player[member.tag]
                        )
                    
                    # ÚLTIMO RECURSO: Ataque desesperado (ignora quase todas as regras)
                    if not viable_targets:
                        self.logger.warning(f"Usando ataque DESESPERADO para {member.name}")
                        viable_targets = self._get_viable_targets(
                            opponent.members, assigned_targets, member, 
                            flexible_rules=True, is_desperate=True, 
                            attacked_bases=attacked_bases_by_player[member.tag]
                        )
                        attack_type = AttackType.DESPERATE
                    
                    if viable_targets:
                        optimal_target = self._find_optimal_target(member, viable_targets, attack_type)
                        if optimal_target:
                            rec = AttackRecommendation(
                                member_name=member.name, member_th=member.town_hall, member_pos=member.map_position,
                                attack_number=current_attack_number, attack_type=attack_type,
                                recommended_target_pos=optimal_target.map_position, recommended_target_th=optimal_target.town_hall,
                                justification=self._generate_intelligent_justification(member, optimal_target, attack_type, None),
                                confidence_score=self._calculate_confidence_score(member, optimal_target, attack_type)
                            )
                            assigned_targets.add(optimal_target.map_position)
                            recommendations.append(rec)
                            target_found = True
                
                # Se AINDA não encontrou, força um alvo qualquer (emergência)
                if not target_found:
                    available_targets = [t for t in opponent.members 
                                       if t.map_position not in assigned_targets 
                                       and t.tag not in attacked_bases_by_player[member.tag]
                                       and not (hasattr(t, 'best_opponent_attack') and t.best_opponent_attack and t.best_opponent_attack.stars == 3)]
                    
                    if available_targets:
                        emergency_target = min(available_targets, key=self._calculate_player_strength)
                        rec = AttackRecommendation(
                            member_name=member.name, member_th=member.town_hall, member_pos=member.map_position,
                            attack_number=current_attack_number, attack_type=AttackType.DESPERATE,
                            recommended_target_pos=emergency_target.map_position, recommended_target_th=emergency_target.town_hall,
                            justification=f"EMERGÊNCIA: Último alvo disponível. Foque em conseguir qualquer estrela possível.",
                            confidence_score=0.3
                        )
                        assigned_targets.add(emergency_target.map_position)
                        recommendations.append(rec)
                        self.logger.warning(f"Ataque de EMERGÊNCIA para {member.name} -> #{emergency_target.map_position}")
                    else:
                        self.logger.error(f"ERRO CRÍTICO: Não foi possível encontrar alvo para {member.name} ataque #{current_attack_number}")
        
        self.logger.info(f"FASE 2 FINALIZADA: {len(recommendations)} recomendações geradas de {total_attacks_remaining} ataques restantes")
        return recommendations

    def create_war_plan(self, war: Any, clan_tag: str, prediction_data: Dict) -> Dict[str, Any]:
        """Cria plano de guerra com validação aprimorada."""
        if not war or war.state not in ['inWar', 'preparation']:
            return {"success": False, "error": "A guerra não está ativa ou em preparação."}
        
        try:
            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan
            
            war_phase = self._determine_war_phase(war)
            
            phase_map = {
                WarPhase.PREPARATION: (f"Fase 1 - Ataques Táticos (v5.8)", self._generate_phase1_recommendations),
                WarPhase.PHASE_1: (f"Fase 1 - Ataques Táticos (v5.8)", self._generate_phase1_recommendations),
                WarPhase.PHASE_2: (f"Fase 2 - Limpeza e Finalização (v5.8)", self._generate_phase2_recommendations)
            }
            
            phase_title, rec_func = phase_map.get(war_phase)
            recommendations = rec_func(war, our_clan, opponent)
            
            # CRÍTICO: Não filtra mais por confiança mínima para garantir que todos apareçam
            filtered_recommendations = recommendations
            
            filtered_recommendations.sort(key=lambda x: (x.member_pos, x.attack_number))
            
            if not filtered_recommendations:
                return { "success": True, "phase_title": "Análise Completa", "recommendations": [], "warning": "Nenhuma recomendação encontrada." }

            avg_conf = sum(r.confidence_score for r in filtered_recommendations) / len(filtered_recommendations) if filtered_recommendations else 0
            
            rec_dict = [r.__dict__ | {'attack_type': r.attack_type.value} for r in filtered_recommendations]

            return {
                "success": True, "phase_title": phase_title, "recommendations": rec_dict,
                "prediction_summary": prediction_data.get("summary_panel", "Análise em andamento..."),
                "generated_at": datetime.datetime.now(pytz.utc).isoformat(),
                "statistics": {
                    "total_recommendations": len(rec_dict),
                    "average_confidence": avg_conf,
                    "attack_types": {t.value: sum(1 for r in rec_dict if r['attack_type'] == t.value) for t in AttackType}
                },
                "version": "5.8 - API Update October 2025"
            }

        except Exception as e:
            self.logger.error(f"Erro crítico ao gerar plano de guerra v5.8: {e}", exc_info=True)
            return {"success": False, "error": f"Erro interno: {e}"}


class WarAdvisorCog(commands.Cog, name="Conselheiro de Guerra IA"):
    """Cog do Discord para o sistema de conselheiro de guerra (v5.8)."""
    
    def __init__(self, bot):
        self.bot = bot
        self.war_advisor = WarAdvisorSystem()
        self.logger = logging.getLogger(f"{__name__}.WarAdvisorCog")

    @commands.command(name='plano')
    @commands.has_permissions(administrator=True)
    async def force_plan_generation(self, ctx):
        """Gera plano de guerra com correções para a nova atualização."""
        await ctx.send("🔄 **Gerando plano de guerra v5.8 (API Update October 2025)...**")
        
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            prediction = await self.bot.war_prediction_system.predict_war_outcome(war, self.bot.clan_tag)
            plan = self.war_advisor.create_war_plan(war, self.bot.clan_tag, prediction)

            if not plan.get("success"):
                return await ctx.send(f"❌ **Erro:** {plan.get('error')}")
            
            embed = discord.Embed(
                title=f"🎯 {plan.get('phase_title')}", 
                description=f"**Sistema v5.8** - Compatível com CV17 e o novo Herói.",
                color=discord.Color.blue()
            )
            
            stats = plan.get("statistics", {})
            if stats:
                types = stats.get('attack_types', {})
                stats_text = (f"**Total:** {stats.get('total_recommendations', 0)} | "
                              f"**Confiança Média:** {stats.get('average_confidence', 0):.0%}\n"
                              f"**Tipos:** Mirror({types.get('mirror',0)}) DIP({types.get('dip',0)}) Safe({types.get('safe',0)}) "
                              f"Cleanup({types.get('cleanup',0)}) Bonus({types.get('bonus',0)}) Desperate({types.get('desperate',0)})")
                embed.add_field(name="📊 Estatísticas", value=stats_text, inline=False)
            
            if plan.get("warning"):
                embed.add_field(name="⚠️ Aviso", value=plan.get("warning"), inline=False)
            
            # Mostra todas as recomendações em grupos por jogador
            recommendations = plan.get("recommendations", [])
            current_player = None
            player_attacks = []
            
            for rec in recommendations[:25]:  # Limite para não quebrar o Discord
                if current_player != rec['member_name']:
                    # Se mudou de jogador, mostra os ataques do jogador anterior
                    if current_player and player_attacks:
                        embed.add_field(
                            name=f"👤 {current_player}",
                            value="\n".join(player_attacks),
                            inline=False
                        )
                    
                    # Inicia novo jogador
                    current_player = rec['member_name']
                    player_attacks = []
                
                # Adiciona ataque do jogador atual
                emoji = "🟢" if rec['confidence_score'] >= 0.8 else "🟡" if rec['confidence_score'] >= 0.65 else "🟠" if rec['confidence_score'] >= 0.4 else "🔴"
                type_emoji = {
                    "mirror": "🪞", "dip": "⚡", "safe": "🛡️", 
                    "cleanup": "🧹", "bonus": "💰", "desperate": "🆘"
                }.get(rec['attack_type'], "⚔️")
                
                attack_info = (f"**Atk{rec['attack_number']}:** {type_emoji} #{rec['recommended_target_pos']} "
                              f"(TH{rec['recommended_target_th']}) - {emoji} {rec['confidence_score']:.0%}")
                player_attacks.append(attack_info)
            
            # Adiciona o último jogador
            if current_player and player_attacks:
                embed.add_field(
                    name=f"👤 {current_player}",
                    value="\n".join(player_attacks),
                    inline=False
                )
            
            if len(recommendations) > 25:
                embed.add_field(
                    name="ℹ️ Informação", 
                    value=f"Mostrando os primeiros 25 ataques de {len(recommendations)} recomendações totais. Veja o painel web para a lista completa.", 
                    inline=False
                )
            
            embed.set_footer(text=f"ClashGenius - {plan.get('version', 'API Update October 2025')}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro no comando plano v5.8: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro crítico:** {e}")

    @commands.command(name='analise')
    @commands.has_permissions(administrator=True)
    async def analyze_war_balance(self, ctx):
        """Analisa o equilíbrio da guerra com sistema aprimorado."""
        await ctx.send("⚖️ **Analisando equilíbrio da guerra com IA v5.8...**")
        
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state not in ['inWar', 'preparation']:
                await ctx.send("❌ Nenhuma guerra ativa encontrada.")
                return
            
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            opp_clan = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
            
            our_strength = sum(self.war_advisor._calculate_player_strength(m) for m in our_clan.members)
            opp_strength = sum(self.war_advisor._calculate_player_strength(m) for m in opp_clan.members)
            
            advantage_percent = ((our_strength - opp_strength) / max(opp_strength, 1)) * 100
            
            if advantage_percent > 10: 
                status_text, strategy, color = (
                    f"🟢 **Vantagem Clara** (+{advantage_percent:.1f}%)", 
                    "Mix de DIP e Mirror. Busque maximizar estrelas.", 
                    discord.Color.green()
                )
            elif advantage_percent > 3: 
                status_text, strategy, color = (
                    f"🟡 **Leve Vantagem** (+{advantage_percent:.1f}%)", 
                    "Foco em Mirror com alguns DIPs calculados.", 
                    discord.Color.gold()
                )
            elif advantage_percent > -3: 
                status_text, strategy, color = (
                    f"🟡 **Guerra Equilibrada** ({advantage_percent:+.1f}%)", 
                    "Disciplina total. Ataques Mirror e Safe apenas.", 
                    discord.Color.gold()
                )
            else: 
                status_text, strategy, color = (
                    f"🔴 **Desvantagem** ({advantage_percent:.1f}%)", 
                    "Máxima disciplina. Safe e limpeza apenas.", 
                    discord.Color.red()
                )

            embed = discord.Embed(title="⚖️ Análise Estratégica da Guerra v5.8", color=color)
            embed.add_field(
                name="💪 Análise de Força", 
                value=f"**Nosso Clã:** {our_strength:,}\n**Oponente:** {opp_strength:,}\n**Status:** {status_text}", 
                inline=False
            )
            embed.add_field(name="🎯 Estratégia Recomendada", value=strategy, inline=False)
            
            # Adiciona informações sobre ataques restantes se estiver na Fase 2
            if war.state == 'inWar':
                attackers_remaining = [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member]
                total_attacks_remaining = sum(war.attacks_per_member - len(m.attacks) for m in attackers_remaining)
                
                embed.add_field(
                    name="⚔️ Status dos Ataques", 
                    value=f"**Jogadores com ataques restantes:** {len(attackers_remaining)}\n**Total de ataques restantes:** {total_attacks_remaining}", 
                    inline=False
                )
            
            embed.set_footer(text="Sistema v5.8 - Análise considera heróis em upgrade e garante recomendações para todos")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro na análise v5.8: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro na análise:** {e}")

    @commands.command(name='debug_ataques')
    @commands.has_permissions(administrator=True)
    async def debug_remaining_attacks(self, ctx):
        """Comando para debugar quem ainda tem ataques restantes."""
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state not in ['inWar', 'preparation']:
                await ctx.send("❌ Nenhuma guerra ativa encontrada.")
                return
            
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            
            embed = discord.Embed(
                title="🔍 Debug - Ataques Restantes", 
                description="Análise detalhada de quem ainda pode atacar:",
                color=discord.Color.orange()
            )
            
            attackers_info = []
            total_remaining = 0
            
            for member in sorted(our_clan.members, key=lambda x: x.map_position):
                attacks_used = len(member.attacks)
                attacks_remaining = war.attacks_per_member - attacks_used
                total_remaining += attacks_remaining
                
                if attacks_remaining > 0:
                    strength = self.war_advisor._calculate_player_strength(member)
                    status = "🔴 FRACO" if strength < 1000 else "🟡 MÉDIO" if strength < 2000 else "🟢 FORTE"
                    
                    attackers_info.append(
                        f"**#{member.map_position} {member.name}** (TH{member.town_hall})\n"
                        f"└ Ataques: {attacks_used}/{war.attacks_per_member} | Restantes: {attacks_remaining} | {status}"
                    )
            
            if attackers_info:
                # Divide em chunks para não quebrar o limite do Discord
                chunk_size = 10
                for i in range(0, len(attackers_info), chunk_size):
                    chunk = attackers_info[i:i + chunk_size]
                    embed.add_field(
                        name=f"👥 Jogadores {i+1}-{min(i+chunk_size, len(attackers_info))}",
                        value="\n\n".join(chunk),
                        inline=False
                    )
            
            embed.add_field(
                name="📊 Resumo",
                value=f"**Total de jogadores com ataques restantes:** {len(attackers_info)}\n**Total de ataques restantes:** {total_remaining}",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro no debug: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro no debug:** {e}")

async def setup(bot: commands.Bot):
    """Configura o cog no bot."""
    await bot.add_cog(WarAdvisorCog(bot))
