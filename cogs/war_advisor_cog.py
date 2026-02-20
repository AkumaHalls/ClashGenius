# -*- coding: utf-8 -*-
"""
Módulo do Conselheiro de Guerra IA - ClashGenius (v6.0 - Deep Tactical Update)
Sistema inteligente para análise e geração de planos táticos de guerra.
UPGRADES: Bottom-Up Strategy, Equipamentos de Heróis e Correção do Minion Prince.
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
    DESPERATE = "desperate"

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

    def _setup_logging(self):
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _calculate_player_strength(self, player: Any) -> int:
        """Calcula o 'Peso Bélico' real do jogador (CV, Heróis e Equipamentos)."""
        if not player or not hasattr(player, 'town_hall'):
            return 0
        
        # Multiplicadores atualizados até o CV17
        th_multipliers = {
            1: 10, 2: 20, 3: 40, 4: 80, 5: 120, 6: 180, 7: 250, 8: 350, 9: 500, 
            10: 700, 11: 950, 12: 1250, 13: 1600, 14: 2000, 15: 2500, 16: 3100, 17: 3800
        }
        base_strength = th_multipliers.get(player.town_hall, player.town_hall * 100)
        
        hero_bonus = 0
        hero_penalty = 0
        equipment_bonus = 0
        
        # Filtro de Heróis apenas da Vila Principal (Ignora Base do Construtor)
        home_heroes = ["Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion", "Minion Prince"]
        
        if hasattr(player, 'heroes') and player.heroes:
            for hero in player.heroes:
                if hero.name in home_heroes:
                    # Príncipe Minion e Campeã têm peso ligeiramente diferente, mas mantemos a média
                    hero_multiplier = max(1, player.town_hall // 3)

                    # Tenta capturar se está em upgrade (algumas versões do coc.py não tem o atributo preenchido em wars)
                    is_upg = getattr(hero, 'is_upgrading', False)
                    
                    if is_upg:
                        hero_penalty += hero.level * hero_multiplier * 0.8
                    else:
                        hero_bonus += hero.level * hero_multiplier

        # IA v6.0: Considera os Equipamentos dos Heróis na força de ataque
        if hasattr(player, 'hero_equipment') and player.hero_equipment:
            for eq in player.hero_equipment:
                # Cada nível de equipamento adiciona peso substancial ao jogador
                equipment_bonus += eq.level * 15

        final_strength = int(base_strength + hero_bonus + equipment_bonus - hero_penalty)
        return final_strength

    def _is_viable_target(self, attacker: Any, target: Any, flexible_rules: bool = False, 
                         is_cleanup: bool = False, is_bonus: bool = False, is_desperate: bool = False) -> Tuple[bool, str]:
        """Avalia friamente se o alvo tem chance matemática de ser derrotado pelo atacante."""
        attacker_th = attacker.town_hall
        target_th = target.town_hall
        
        # Alvo já com 3 estrelas não deve ser atacado
        if hasattr(target, 'best_opponent_attack') and target.best_opponent_attack and target.best_opponent_attack.stars == 3:
            return False, "Alvo já destruído 100%"

        if is_desperate:
            if target_th > attacker_th + 2:
                return False, f"Alvo impenetrável mesmo em desespero (CV{target_th} vs CV{attacker_th})"
            return True, "Viável para ataque suicida"

        if target_th > attacker_th + self.MAX_TH_DIFFERENCE_UP:
            return False, f"Alvo muito blindado (CV{target_th} vs CV{attacker_th})"
        
        if not flexible_rules and not is_cleanup and not is_bonus and target_th < attacker_th - self.MAX_TH_DIFFERENCE_DOWN:
            return False, f"Alvo fraco demais (Desperdício de ataque)"
        
        position_diff = target.map_position - attacker.map_position
        if not flexible_rules and not is_cleanup and not is_bonus and not is_desperate:
            if position_diff > self.MAX_POSITION_DIFFERENCE_UP:
                return False, f"Alvo muito superior no mapa (#{target.map_position} vs #{attacker.map_position})"
            if position_diff < -self.MAX_POSITION_DIFFERENCE_DOWN:
                return False, f"Alvo muito inferior no mapa (#{target.map_position} vs #{attacker.map_position})"
        
        if not flexible_rules and not is_cleanup and not is_bonus and not is_desperate:
            attacker_strength = self._calculate_player_strength(attacker)
            target_strength = self._calculate_player_strength(target)
            strength_ratio = attacker_strength / max(target_strength, 1)
            
            if strength_ratio < 0.6:
                return False, f"Falta poder de fogo (Força Relativa: {strength_ratio:.2f})"
        
        return True, "Alvo taticamente viável"

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
        viable_targets = []
        attacked_bases = attacked_bases or set()
        
        for member in opponent_members:
            if member.map_position in assigned_targets: 
                continue
            if member.tag in attacked_bases:
                continue
            
            is_viable, reason = self._is_viable_target(
                attacker, member, flexible_rules=flexible_rules, is_bonus=is_bonus, is_desperate=is_desperate
            )
            
            if is_viable:
                viable_targets.append(member)
            else:
                self.logger.debug(f"Alvo #{member.map_position} bloqueado para {attacker.name}: {reason}")
        
        return viable_targets

    def _find_optimal_target(self, attacker: Any, viable_targets: List[Any], attack_type: AttackType) -> Optional[Any]:
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
        
        elif attack_type in [AttackType.BONUS, AttackType.DESPERATE]:
            return min(viable_targets, key=self._calculate_player_strength)

        else:  # MIRROR
            mirror = next((t for t in viable_targets if t.map_position == attacker.map_position), None)
            if mirror: return mirror
            return min(viable_targets, key=lambda t: abs(t.map_position - attacker.map_position))

    def _calculate_confidence_score(self, attacker: Any, target: Any, attack_type: AttackType) -> float:
        if not target: return 0.3
        
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        strength_ratio = attacker_strength / max(target_strength, 1)
        
        if attack_type == AttackType.DESPERATE:
            return 0.4 if strength_ratio >= 0.7 else 0.3
        
        if strength_ratio >= 1.3: base_confidence = 0.9
        elif strength_ratio >= 1.1: base_confidence = 0.8
        elif strength_ratio >= 0.9: base_confidence = 0.65
        elif strength_ratio >= 0.7: base_confidence = 0.5
        else: base_confidence = 0.4
        
        th_diff = target.town_hall - attacker.town_hall
        th_modifier = 1.0 if th_diff <= 0 else 0.7 if th_diff == 1 else 0.5
        
        final_confidence = base_confidence * th_modifier
        return max(0.3, min(0.95, final_confidence))

    def _determine_attack_strategy(self, attacker: Any, mirror_target: Optional[Any], is_weakest_attacker: bool = False) -> AttackType:
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
        """IA v6.0: Estratégia Bottom-Up (Mais fracos limpam a base primeiro)"""
        recommendations = []
        assigned_targets = set()
        
        # Identifica os 3 mais fracos da guerra inteira para dar passes bônus
        all_attackers_strength = sorted([m for m in our_clan.members if not m.attacks], key=self._calculate_player_strength)
        weakest_attacker_tags = {m.tag for m in all_attackers_strength[:3]}

        # Ordena de forma crescente: Mais Fracos Primeiro (Bottom-Up Strategy)
        sorted_attackers = sorted(
            [m for m in our_clan.members if not m.attacks], 
            key=lambda x: (self._calculate_player_strength(x), -x.map_position)
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
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        strength_diff = attacker_strength - target_strength
        
        if attack_type == AttackType.DIP:
            return f"DIP Tático: Sua força (+{strength_diff}) esmaga o alvo e libera nossos jogadores inferiores."
        elif attack_type == AttackType.SAFE:
            if mirror and self._calculate_player_strength(mirror) > attacker_strength:
                return f"Recuo Seguro: Seu espelho está blindado. Ataque o #{target.map_position} para garantir as estrelas."
            return f"Estratégia Conservadora: A superioridade de força (+{strength_diff}) minimiza os riscos de falha."
        elif attack_type == AttackType.BONUS:
            return f"Scout/Bônus: Como vanguarda leve, foque na vila mais acessível (#{target.map_position}) para revelar armadilhas."
        elif attack_type == AttackType.DESPERATE:
            return f"Ataque Kamikaze: Opções esgotadas. Jogue pelo erro do oponente no #{target.map_position} e tente a 1 estrela."
        else: # MIRROR
            if target.map_position == attacker.map_position:
                return f"Combate Direto: Equilíbrio perfeito. O espelho é seu."
            return f"Ajuste Tático: Este alvo (#{target.map_position}) simula o peso do seu espelho original."

    def _get_cleanup_targets(self, opponent: Any) -> List[Dict[str, Any]]:
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
        """IA v6.0: Foca os pesados em finalizar as bases feridas (Clean Up)."""
        recommendations = []
        cleanup_targets = self._get_cleanup_targets(opponent)
        
        attackers_remaining = [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member]
        total_attacks_remaining = sum(war.attacks_per_member - len(m.attacks) for m in attackers_remaining)
        
        all_attackers_strength = sorted(attackers_remaining, key=self._calculate_player_strength)
        weakest_attacker_tags = {m.tag for m in all_attackers_strength[:3]}

        # Fase 2: Pesados atacam primeiro para garantir as limpezas prioritárias
        sorted_attackers = sorted(attackers_remaining, key=self._calculate_player_strength, reverse=True)
        assigned_targets = set()

        attacked_bases_by_player = defaultdict(set)
        for m in our_clan.members:
            for a in m.attacks:
                attacked_bases_by_player[m.tag].add(a.defender_tag)

        for member in sorted_attackers:
            is_weakest = member.tag in weakest_attacker_tags
            attacks_needed = war.attacks_per_member - len(member.attacks)
            
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
                            justification=f"Operação Limpeza: Fechar o #{potential_target['position']} que está com {'⭐' * potential_target['stars']} ({potential_target['destruction']}%).",
                            confidence_score=self._calculate_confidence_score(member, target_obj, AttackType.CLEANUP)
                        )
                        assigned_targets.add(potential_target['position'])
                        recommendations.append(rec)
                        target_found = True
                        break

                if not target_found:
                    attack_type = AttackType.BONUS if is_weakest else AttackType.SAFE
                    
                    viable_targets = self._get_viable_targets(
                        opponent.members, assigned_targets, member, 
                        is_bonus=is_weakest, attacked_bases=attacked_bases_by_player[member.tag]
                    )
                    
                    if not viable_targets:
                        viable_targets = self._get_viable_targets(
                            opponent.members, assigned_targets, member, 
                            flexible_rules=True, is_bonus=is_weakest, 
                            attacked_bases=attacked_bases_by_player[member.tag]
                        )
                    
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
                            justification=f"Ataque Final: Sobras do mapa. Tente raspar % no #{emergency_target.map_position}.",
                            confidence_score=0.3
                        )
                        assigned_targets.add(emergency_target.map_position)
                        recommendations.append(rec)
                    else:
                        self.logger.error(f"ERRO CRÍTICO: Não foi possível encontrar alvo para {member.name}")
        
        return recommendations

    def create_war_plan(self, war: Any, clan_tag: str, prediction_data: Dict) -> Dict[str, Any]:
        if not war or war.state not in ['inWar', 'preparation']:
            return {"success": False, "error": "A guerra não está ativa ou em preparação."}
        
        try:
            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan
            
            war_phase = self._determine_war_phase(war)
            
            phase_map = {
                WarPhase.PREPARATION: (f"Fase 1 - Vanguarda e Reconhecimento (IA v6.0)", self._generate_phase1_recommendations),
                WarPhase.PHASE_1: (f"Fase 1 - Vanguarda e Reconhecimento (IA v6.0)", self._generate_phase1_recommendations),
                WarPhase.PHASE_2: (f"Fase 2 - Arremate e Finalização (IA v6.0)", self._generate_phase2_recommendations)
            }
            
            phase_title, rec_func = phase_map.get(war_phase)
            recommendations = rec_func(war, our_clan, opponent)
            
            filtered_recommendations = recommendations
            filtered_recommendations.sort(key=lambda x: (x.member_pos, x.attack_number))
            
            if not filtered_recommendations:
                return { "success": True, "phase_title": "Análise Concluída", "recommendations": [], "warning": "Nenhum alvo encontrado. Mapa pode estar fechado." }

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
                "version": "Inteligência ClashGenius v6.0"
            }

        except Exception as e:
            self.logger.error(f"Erro ao gerar plano v6.0: {e}", exc_info=True)
            return {"success": False, "error": f"Erro interno: {e}"}


class WarAdvisorCog(commands.Cog, name="Conselheiro de Guerra IA"):
    """Cog do Discord para o sistema de conselheiro tático."""
    
    def __init__(self, bot):
        self.bot = bot
        self.war_advisor = WarAdvisorSystem()
        self.logger = logging.getLogger(f"{__name__}.WarAdvisorCog")

    @commands.command(name='plano')
    @commands.has_permissions(administrator=True)
    async def force_plan_generation(self, ctx):
        """Gera plano tático de guerra com a IA v6.0."""
        await ctx.send("🧠 **IA processando plano de guerra tático (v6.0)...**")
        
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            prediction = await self.bot.war_prediction_system.predict_war_outcome(war, self.bot.clan_tag)
            plan = self.war_advisor.create_war_plan(war, self.bot.clan_tag, prediction)

            if not plan.get("success"):
                return await ctx.send(f"❌ **Erro da IA:** {plan.get('error')}")
            
            embed = discord.Embed(
                title=f"🎯 {plan.get('phase_title')}", 
                description=f"**Módulo Tático v6.0** - Calcula Heróis Corretos, CV17 e Equipamentos.",
                color=discord.Color.blue()
            )
            
            stats = plan.get("statistics", {})
            if stats:
                types = stats.get('attack_types', {})
                stats_text = (f"**Total Ataques:** {stats.get('total_recommendations', 0)} | "
                              f"**Certeza Média:** {stats.get('average_confidence', 0):.0%}\n"
                              f"**Distribuição:** Mirror({types.get('mirror',0)}) DIP({types.get('dip',0)}) Safe({types.get('safe',0)}) "
                              f"Cleanup({types.get('cleanup',0)}) Bonus({types.get('bonus',0)}) Desperate({types.get('desperate',0)})")
                embed.add_field(name="📊 Tática Global", value=stats_text, inline=False)
            
            if plan.get("warning"):
                embed.add_field(name="⚠️ Situação Atípica", value=plan.get("warning"), inline=False)
            
            recommendations = plan.get("recommendations", [])
            current_player = None
            player_attacks = []
            
            for rec in recommendations[:25]:
                if current_player != rec['member_name']:
                    if current_player and player_attacks:
                        embed.add_field(
                            name=f"👤 {current_player}",
                            value="\n".join(player_attacks),
                            inline=False
                        )
                    current_player = rec['member_name']
                    player_attacks = []
                
                emoji = "🟢" if rec['confidence_score'] >= 0.8 else "🟡" if rec['confidence_score'] >= 0.65 else "🟠" if rec['confidence_score'] >= 0.4 else "🔴"
                type_emoji = {
                    "mirror": "🪞", "dip": "⚡", "safe": "🛡️", 
                    "cleanup": "🧹", "bonus": "💰", "desperate": "🆘"
                }.get(rec['attack_type'], "⚔️")
                
                attack_info = (f"**Ataque {rec['attack_number']}:** {type_emoji} Alvo #{rec['recommended_target_pos']} "
                              f"(CV{rec['recommended_target_th']}) - Força Bruta {emoji} {rec['confidence_score']:.0%}")
                player_attacks.append(attack_info)
            
            if current_player and player_attacks:
                embed.add_field(name=f"👤 {current_player}", value="\n".join(player_attacks), inline=False)
            
            if len(recommendations) > 25:
                embed.add_field(
                    name="🌐 Terminal Web", 
                    value=f"Acima estão as ordens para os 25 primeiros ataques. Veja o painel Web para o briefing completo.", 
                    inline=False
                )
            
            embed.set_footer(text=f"Processado por {plan.get('version', 'IA v6.0')}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro na matriz do conselheiro: {e}", exc_info=True)
            await ctx.send("❌ **Falha catastrófica no núcleo do Conselheiro.**")

    @commands.command(name='analise')
    @commands.has_permissions(administrator=True)
    async def analyze_war_balance(self, ctx):
        """Avalia quem tem as melhores chances matemáticas de vitória."""
        await ctx.send("⚖️ **Iniciando cálculo matemático de poder bélico...**")
        
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state not in ['inWar', 'preparation']:
                await ctx.send("❌ Nenhuma linha de frente ativa no momento.")
                return
            
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            opp_clan = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
            
            our_strength = sum(self.war_advisor._calculate_player_strength(m) for m in our_clan.members)
            opp_strength = sum(self.war_advisor._calculate_player_strength(m) for m in opp_clan.members)
            
            advantage_percent = ((our_strength - opp_strength) / max(opp_strength, 1)) * 100
            
            if advantage_percent > 10: 
                status_text, strategy, color = (
                    f"🟢 **Dominância Estimada** (+{advantage_percent:.1f}%)", 
                    "Sua tribo é mais pesada. Façam os ataques iniciais de baixo pra cima em Mirror, e usem os Tops para DIP sem dó.", 
                    discord.Color.green()
                )
            elif advantage_percent > 3: 
                status_text, strategy, color = (
                    f"🟡 **Vantagem Moderada** (+{advantage_percent:.1f}%)", 
                    "Pequena superioridade bélica. Foco total em Mirror e limpeza milimétrica.", 
                    discord.Color.gold()
                )
            elif advantage_percent > -3: 
                status_text, strategy, color = (
                    f"🟡 **Guerra Espelhada** ({advantage_percent:+.1f}%)", 
                    "Equilíbrio mortal. A vitória dependerá puramente da habilidade dos ataques (menos fails ganha).", 
                    discord.Color.gold()
                )
            else: 
                status_text, strategy, color = (
                    f"🔴 **Desvantagem Bélica** ({advantage_percent:.1f}%)", 
                    "O oponente é visivelmente mais upado. O único jeito é não errar alvos de base e torcer para o desespero deles na Fase 2.", 
                    discord.Color.red()
                )

            embed = discord.Embed(title="⚖️ Relatório Bélico v6.0", color=color)
            embed.add_field(
                name="💪 Acúmulo de Força (Heróis + CV + Pets)", 
                value=f"**O Nosso Clã:** {our_strength:,}\n**Os Inimigos:** {opp_strength:,}\n**Situação:** {status_text}", 
                inline=False
            )
            embed.add_field(name="🎯 Diretriz Recomendada pela IA", value=strategy, inline=False)
            
            if war.state == 'inWar':
                attackers_remaining = [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member]
                total_attacks_remaining = sum(war.attacks_per_member - len(m.attacks) for m in attackers_remaining)
                
                embed.add_field(
                    name="⚔️ Fôlego de Batalha", 
                    value=f"**Membros com ataques na manga:** {len(attackers_remaining)}\n**Total de tiros restantes:** {total_attacks_remaining}", 
                    inline=False
                )
            
            embed.set_footer(text="Inteligência v6.0 - Ignora Máquina de Batalha e pontua Equipamentos")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro na medição: {e}", exc_info=True)
            await ctx.send(f"❌ **Falha ao ler os pesos de guerra:** {e}")

    @commands.command(name='debug_ataques')
    @commands.has_permissions(administrator=True)
    async def debug_remaining_attacks(self, ctx):
        """Lista quem são os responsáveis pelos tiros restantes."""
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state not in ['inWar', 'preparation']:
                await ctx.send("❌ Nenhuma guerra em curso.")
                return
            
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            
            embed = discord.Embed(
                title="🔍 Balanço de Cartuchos Restantes", 
                description="Visão da equipe sobre os ataques pendentes:",
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
                    status = "🔴 LEVE" if strength < 1000 else "🟡 MÉDIO" if strength < 2000 else "🟢 PESADO"
                    
                    attackers_info.append(
                        f"**#{member.map_position} {member.name}** (CV{member.town_hall})\n"
                        f"└ Feitos: {attacks_used}/{war.attacks_per_member} | Faltam: {attacks_remaining} | Escala: {status}"
                    )
            
            if attackers_info:
                chunk_size = 10
                for i in range(0, len(attackers_info), chunk_size):
                    chunk = attackers_info[i:i + chunk_size]
                    embed.add_field(
                        name=f"👥 Lote {i+1}-{min(i+chunk_size, len(attackers_info))}",
                        value="\n\n".join(chunk),
                        inline=False
                    )
            
            embed.add_field(
                name="📊 Somatória Geral",
                value=f"**Players Incompletos:** {len(attackers_info)}\n**Munição Total Restante:** {total_remaining}",
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro no balanço de munição: {e}", exc_info=True)
            await ctx.send(f"❌ **Falha ao mapear cartuchos.**")

async def setup(bot: commands.Bot):
    await bot.add_cog(WarAdvisorCog(bot))
