# -*- coding: utf-8 -*-
"""
Módulo do Conselheiro de Guerra IA - ClashGenius (v5.6 - ESTRATÉGIA DE BÔNUS)
Sistema inteligente para análise e geração de planos táticos de guerra.
NOVO: Adicionada a estratégia "Bônus" para os jogadores mais fracos do clã,
recomendando os alvos mais fáceis para garantir estrelas.
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
    MIN_CONFIDENCE_SCORE = 0.5
    
    def __init__(self):
        self.logger = logging.getLogger("war_advisor_v5.6")
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
        
        final_strength = int(base_strength + hero_bonus - hero_penalty)
        return final_strength

    def _is_viable_target(self, attacker: Any, target: Any, flexible_rules: bool = False, is_cleanup: bool = False, is_bonus: bool = False) -> Tuple[bool, str]:
        """Verifica se um alvo é viável com validações aprimoradas."""
        attacker_th = attacker.town_hall
        target_th = target.town_hall
        
        if hasattr(target, 'best_opponent_attack') and target.best_opponent_attack and target.best_opponent_attack.stars == 3:
            return False, "Alvo já possui 3 estrelas"

        if target_th > attacker_th + self.MAX_TH_DIFFERENCE_UP:
            return False, f"Alvo muito superior (TH{target_th} vs TH{attacker_th})"
        
        if not flexible_rules and not is_cleanup and not is_bonus and target_th < attacker_th - self.MAX_TH_DIFFERENCE_DOWN:
            return False, f"Alvo muito inferior (desperdício de potencial)"
        
        position_diff = target.map_position - attacker.map_position
        if not flexible_rules and not is_cleanup and not is_bonus:
            if position_diff > self.MAX_POSITION_DIFFERENCE_UP:
                return False, f"Alvo muito superior no mapa (#{target.map_position} vs #{attacker.map_position})"
            if position_diff < -self.MAX_POSITION_DIFFERENCE_DOWN:
                return False, f"Alvo muito inferior no mapa (#{target.map_position} vs #{attacker.map_position})"
        
        if not flexible_rules and not is_cleanup and not is_bonus:
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

    def _get_viable_targets(self, opponent_members: List[Any], assigned_targets: set, attacker: Any, flexible_rules: bool = False, is_bonus: bool = False) -> List[Any]:
        """Obtém alvos viáveis com logging detalhado."""
        viable_targets = []
        for member in opponent_members:
            if member.map_position in assigned_targets: 
                continue
            
            is_viable, reason = self._is_viable_target(attacker, member, flexible_rules=flexible_rules, is_bonus=is_bonus)
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
            self.logger.debug(f"Buscando alvo BONUS para {attacker.name}: o mais fraco disponível.")
            return min(viable_targets, key=self._calculate_player_strength)

        else:  # MIRROR
            mirror = next((t for t in viable_targets if t.map_position == attacker.map_position), None)
            if mirror: return mirror
            return min(viable_targets, key=lambda t: abs(t.map_position - attacker.map_position))

    def _calculate_confidence_score(self, attacker: Any, target: Any, attack_type: AttackType) -> float:
        """Calcula pontuação de confiança com critérios rigorosos."""
        if not target: return 0.3
        
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        strength_ratio = attacker_strength / max(target_strength, 1)
        
        if strength_ratio >= 1.3: base_confidence = 0.9
        elif strength_ratio >= 1.1: base_confidence = 0.8
        elif strength_ratio >= 0.9: base_confidence = 0.65
        else: base_confidence = 0.4
        
        th_diff = target.town_hall - attacker.town_hall
        th_modifier = 1.0 if th_diff <= 0 else 0.7 if th_diff == 1 else 0.4
        
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
            self.logger.debug(f"Atacante fraco com espelho difícil. Estratégia: BONUS")
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
        """Gera recomendações para fase 2 (limpeza e ataques restantes)."""
        recommendations = []
        cleanup_targets = self._get_cleanup_targets(opponent)
        
        all_attackers_strength = sorted([m for m in our_clan.members if len(m.attacks) < war.attacks_per_member], key=self._calculate_player_strength)
        weakest_attacker_tags = {m.tag for m in all_attackers_strength[:3]}

        attackers = sorted(
            [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member],
            key=self._calculate_player_strength,
            reverse=True
        )
        assigned_targets = set()

        attacked_bases_by_player = defaultdict(set)
        for m in our_clan.members:
            for a in m.attacks:
                attacked_bases_by_player[m.tag].add(a.defender_tag)

        self.logger.info(f"Fase 2: {len(cleanup_targets)} alvos de limpeza, {len(attackers)} atacantes")

        for member in attackers:
            is_weakest = member.tag in weakest_attacker_tags
            target_info = None
            
            # 1. Tenta encontrar um alvo de LIMPEZA
            for potential_target in cleanup_targets:
                target_pos = potential_target['position']
                if target_pos in assigned_targets or potential_target['tag'] in attacked_bases_by_player[member.tag]:
                    continue

                target_obj = next((m for m in opponent.members if m.map_position == target_pos), None)
                if target_obj and self._is_viable_target(member, target_obj, is_cleanup=True)[0]:
                    target_info = potential_target
                    break

            # 2. Se encontrou alvo de limpeza, cria a recomendação
            if target_info:
                target_obj = next(m for m in opponent.members if m.map_position == target_info['position'])
                rec = AttackRecommendation(
                    member_name=member.name, member_th=member.town_hall, member_pos=member.map_position,
                    attack_number=len(member.attacks) + 1, attack_type=AttackType.CLEANUP,
                    recommended_target_pos=target_info["position"], recommended_target_th=target_info["th"],
                    justification=f"LIMPEZA PRIORITÁRIA! #{target_info['position']} com {'⭐' * target_info['stars']} ({target_info['destruction']}%). Foque no 3⭐!",
                    confidence_score=self._calculate_confidence_score(member, target_obj, AttackType.CLEANUP)
                )
                assigned_targets.add(target_info['position'])
                recommendations.append(rec)
            
            # 3. Se NÃO há limpeza, decide entre BÔNUS (para os fracos) ou SAFE (para os demais)
            else:
                attack_type = AttackType.BONUS if is_weakest else AttackType.SAFE
                
                # Busca alvos viáveis para o ataque fresh
                fresh_viable_targets = self._get_viable_targets(opponent.members, assigned_targets, member, is_bonus=is_weakest)
                
                if fresh_viable_targets:
                    optimal_target = self._find_optimal_target(member, fresh_viable_targets, attack_type)
                    if optimal_target:
                        rec = AttackRecommendation(
                            member_name=member.name, member_th=member.town_hall, member_pos=member.map_position,
                            attack_number=len(member.attacks) + 1, attack_type=attack_type,
                            recommended_target_pos=optimal_target.map_position, recommended_target_th=optimal_target.town_hall,
                            justification=self._generate_intelligent_justification(member, optimal_target, attack_type, None),
                            confidence_score=self._calculate_confidence_score(member, optimal_target, attack_type)
                        )
                        assigned_targets.add(optimal_target.map_position)
                        recommendations.append(rec)
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
                WarPhase.PREPARATION: (f"Fase 1 - Ataques Táticos (v5.6)", self._generate_phase1_recommendations),
                WarPhase.PHASE_1: (f"Fase 1 - Ataques Táticos (v5.6)", self._generate_phase1_recommendations),
                WarPhase.PHASE_2: (f"Fase 2 - Limpeza e Finalização (v5.6)", self._generate_phase2_recommendations)
            }
            
            phase_title, rec_func = phase_map.get(war_phase)
            recommendations = rec_func(war, our_clan, opponent)
            
            filtered_recommendations = [r for r in recommendations if r.confidence_score >= self.MIN_CONFIDENCE_SCORE]
            
            if not filtered_recommendations and recommendations:
                 filtered_recommendations = recommendations

            filtered_recommendations.sort(key=lambda x: x.member_pos)
            
            if not filtered_recommendations:
                return { "success": True, "phase_title": "Análise Completa", "recommendations": [], "warning": "Nenhuma recomendação com confiança adequada encontrada." }

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
                "version": "5.6 - Estratégia de Bônus"
            }

        except Exception as e:
            self.logger.error(f"Erro crítico ao gerar plano de guerra v5.6: {e}", exc_info=True)
            return {"success": False, "error": f"Erro interno: {e}"}


class WarAdvisorCog(commands.Cog, name="Conselheiro de Guerra IA"):
    """Cog do Discord para o sistema de conselheiro de guerra (v5.6)."""
    
    def __init__(self, bot):
        self.bot = bot
        self.war_advisor = WarAdvisorSystem()
        self.logger = logging.getLogger(f"{__name__}.WarAdvisorCog")

    @commands.command(name='plano')
    @commands.has_permissions(administrator=True)
    async def force_plan_generation(self, ctx):
        """Gera plano de guerra com a estratégia de bônus."""
        await ctx.send("🔄 **Gerando plano de guerra v5.6 (Estratégia de Bônus)...**")
        
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            prediction = await self.bot.war_prediction_system.predict_war_outcome(war, self.bot.clan_tag)
            plan = self.war_advisor.create_war_plan(war, self.bot.clan_tag, prediction)

            if not plan.get("success"):
                return await ctx.send(f"❌ **Erro:** {plan.get('error')}")
            
            embed = discord.Embed(
                title=f"🎯 {plan.get('phase_title')}", 
                description=f"**Sistema v5.6** - Nova estratégia de **Bônus** para os jogadores mais fracos garantirem estrelas.",
                color=discord.Color.blue()
            )
            
            stats = plan.get("statistics", {})
            if stats:
                types = stats.get('attack_types', {})
                stats_text = (f"**Total:** {stats.get('total_recommendations', 0)} | "
                              f"**Confiança Média:** {stats.get('average_confidence', 0):.0%}\n"
                              f"**Tipos:** Mirror({types.get('mirror',0)}) DIP({types.get('dip',0)}) Safe({types.get('safe',0)}) Cleanup({types.get('cleanup',0)}) Bonus({types.get('bonus',0)})")
                embed.add_field(name="📊 Estatísticas", value=stats_text, inline=False)
            
            if plan.get("warning"):
                embed.add_field(name="⚠️ Aviso", value=plan.get("warning"), inline=False)
            
            for rec in plan.get("recommendations", [])[:10]:
                emoji = "🟢" if rec['confidence_score'] >= 0.8 else "🟡" if rec['confidence_score'] >= 0.65 else "🟠"
                type_emoji = {"mirror": "🪞", "dip": "⚡", "safe": "🛡️", "cleanup": "🧹", "bonus": "💰"}.get(rec['attack_type'], "⚔️")
                
                value = (f"**🎯 Alvo:** #{rec['recommended_target_pos']} (TH{rec['recommended_target_th']})\n"
                         f"**{emoji} Confiança:** {rec['confidence_score']:.0%}\n"
                         f"**{type_emoji} Tipo:** {rec['attack_type'].upper()}\n"
                         f"**🤖 IA:** _{rec['justification']}_")
                
                embed.add_field(
                    name=f"#{rec['member_pos']} {rec['member_name']} (TH{rec['member_th']}) - Atk {rec['attack_number']}",
                    value=value,
                    inline=False
                )
            
            if len(plan.get("recommendations", [])) > 10:
                embed.add_field(name="ℹ️ Informação", value="Mostrando as 10 primeiras recomendações. Veja o painel web para a lista completa.", inline=False)
            
            embed.set_footer(text=f"ClashGenius - {plan.get('version', 'Sistema Corrigido')}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro no comando plano v5.6: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro crítico:** {e}")

    @commands.command(name='analise')
    @commands.has_permissions(administrator=True)
    async def analyze_war_balance(self, ctx):
        """Analisa o equilíbrio da guerra com sistema aprimorado."""
        await ctx.send("⚖️ **Analisando equilíbrio da guerra com IA v5.6...**")
        
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
            
            if advantage_percent > 10: status_text, strategy, color = f"🟢 **Vantagem Clara** (+{advantage_percent:.1f}%)", "Mix de DIP e Mirror. Busque maximizar estrelas.", discord.Color.green()
            elif advantage_percent > 3: status_text, strategy, color = f"🟡 **Leve Vantagem** (+  {advantage_percent:.1f}%)", "Foco em Mirror com alguns DIPs calculados.", discord.Color.gold()
            elif advantage_percent > -3: status_text, strategy, color = f"🟡 **Guerra Equilibrada** ({advantage_percent:+.1f}%)", "Disciplina total. Ataques Mirror e Safe apenas.", discord.Color.gold()
            else: status_text, strategy, color = f"🔴 **Desvantagem** ({advantage_percent:.1f}%)", "Máxima disciplina. Safe e limpeza apenas.", discord.Color.red()

            embed = discord.Embed(title="⚖️ Análise Estratégica da Guerra v5.6", color=color)
            embed.add_field(name="💪 Análise de Força", value=f"**Nosso Clã:** {our_strength:,}\n**Oponente:** {opp_strength:,}\n**Status:** {status_text}", inline=False)
            embed.add_field(name="🎯 Estratégia Recomendada", value=strategy, inline=False)
            embed.set_footer(text="Sistema v5.6 - Análise considera heróis em upgrade")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro na análise v5.6: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro na análise:** {e}")

async def setup(bot: commands.Bot):
    """Configura o cog no bot."""
    await bot.add_cog(WarAdvisorCog(bot))

