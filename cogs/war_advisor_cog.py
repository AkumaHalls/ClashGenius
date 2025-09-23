# -*- coding: utf-8 -*-
"""
Módulo do Conselheiro de Guerra IA - ClashGenius (v5.1 - Lógica Flexível)
Sistema inteligente para análise e geração de planos táticos de guerra.
CORREÇÕES: Lógica de força, restrições de TH, análise de viabilidade e fallback para alvos.
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
    
    # Constantes de configuração mais inteligentes
    MAX_TH_DIFFERENCE_UP = 1    # Máximo 1 TH acima
    MAX_TH_DIFFERENCE_DOWN = 3  # Máximo 3 TH abaixo
    STRENGTH_ADVANTAGE_THRESHOLD = 150  # Vantagem significativa
    STRENGTH_DISADVANTAGE_THRESHOLD = -100 # Desvantagem significativa
    WAR_PHASE_SPLIT_HOURS = 12
    MIN_CONFIDENCE_SCORE = 0.4
    
    def __init__(self):
        self.logger = logging.getLogger("war_advisor_v5.1")
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
        Considera TH, heróis e peso geral.
        """
        if not player or not hasattr(player, 'town_hall'):
            return 0
        
        # Base strength baseada no TH com progressão exponencial
        th_multipliers = {
            1: 10, 2: 20, 3: 40, 4: 80, 5: 120, 6: 180, 7: 250,
            8: 350, 9: 500, 10: 700, 11: 950, 12: 1250, 13: 1600,
            14: 2000, 15: 2500, 16: 3100, 17: 3800
        }
        
        base_strength = th_multipliers.get(player.town_hall, player.town_hall * 100)
        
        # Bônus de heróis mais significativo
        hero_bonus = 0
        if hasattr(player, 'heroes') and player.heroes:
            for hero in player.heroes:
                if hero.is_home_base:
                    # Heróis têm peso maior em TH superiores
                    hero_multiplier = max(1, player.town_hall // 3)
                    hero_bonus += hero.level * hero_multiplier
        
        return int(base_strength + hero_bonus)

    def _is_viable_target(self, attacker: Any, target: Any, flexible_rules: bool = False) -> Tuple[bool, str]:
        """
        Verifica se um alvo é viável para um atacante.
        Retorna (viável, motivo).
        """
        attacker_th = attacker.town_hall
        target_th = target.town_hall
        
        # Regra fundamental: não atacar mais de 1 TH acima
        if target_th > attacker_th + self.MAX_TH_DIFFERENCE_UP:
            return False, f"Alvo muito superior (TH{target_th} vs TH{attacker_th})"
        
        # Evitar atacar muito abaixo (desperdício), a menos que as regras sejam flexíveis
        if not flexible_rules and target_th < attacker_th - self.MAX_TH_DIFFERENCE_DOWN:
            return False, f"Alvo muito inferior (desperdício de potencial)"
        
        # Verificar se o alvo já foi 3 estrelas
        if hasattr(target, 'best_opponent_attack') and target.best_opponent_attack:
            if target.best_opponent_attack.stars == 3:
                return False, "Alvo já possui 3 estrelas"
        
        return True, "Alvo viável"

    def _determine_war_phase(self, war: Any) -> WarPhase:
        if war.state == 'preparation':
            return WarPhase.PREPARATION
        if war.state != 'inWar':
            return WarPhase.PHASE_1
        
        try:
            now = datetime.datetime.now(pytz.utc)
            war_start_time = war.start_time.time.replace(tzinfo=pytz.utc)
            hours_passed = (now - war_start_time).total_seconds() / 3600
            return WarPhase.PHASE_1 if hours_passed < self.WAR_PHASE_SPLIT_HOURS else WarPhase.PHASE_2
        except Exception:
            return WarPhase.PHASE_1

    def _get_viable_targets(self, opponent_members: List[Any], assigned_targets: set, attacker: Any, flexible_rules: bool = False) -> List[Any]:
        """
        Retorna apenas alvos viáveis para o atacante específico.
        """
        viable_targets = []
        
        for member in opponent_members:
            if member.map_position in assigned_targets:
                continue
                
            is_viable, reason = self._is_viable_target(attacker, member, flexible_rules=flexible_rules)
            if is_viable:
                viable_targets.append(member)
            else:
                self.logger.debug(f"Alvo #{member.map_position} não viável para {attacker.name}: {reason}")
        
        return viable_targets

    def _find_optimal_target(self, attacker: Any, viable_targets: List[Any], attack_type: AttackType) -> Optional[Any]:
        """
        Lógica inteligente para encontrar o melhor alvo viável.
        """
        if not viable_targets:
            return None

        attacker_strength = self._calculate_player_strength(attacker)
        attacker_th = attacker.town_hall

        if attack_type == AttackType.DIP:
            # Para DIP: ataca o alvo mais forte possível que seja viável
            dip_candidates = [t for t in viable_targets if t.town_hall >= attacker_th]
            if dip_candidates:
                return max(dip_candidates, key=self._calculate_player_strength)
            else:
                return max(viable_targets, key=self._calculate_player_strength)

        elif attack_type == AttackType.SAFE:
            # Para SAFE: ataca o alvo mais fácil que garante 3 estrelas
            safe_candidates = [t for t in viable_targets if t.town_hall <= attacker_th and self._calculate_player_strength(t) <= attacker_strength]
            if safe_candidates:
                return min(safe_candidates, key=self._calculate_player_strength)
            else:
                return min(viable_targets, key=self._calculate_player_strength)
            
        else:  # MIRROR
            # Para MIRROR: busca o espelho ou alvo com força similar
            mirror_pos = attacker.map_position
            mirror_target = next((t for t in viable_targets if t.map_position == mirror_pos), None)
            
            if mirror_target:
                return mirror_target
            
            return min(viable_targets, key=lambda t: abs(self._calculate_player_strength(t) - attacker_strength))

    def _calculate_confidence_score(self, attacker: Any, target: Any, attack_type: AttackType) -> float:
        """
        Calcula a confiança da IA na recomendação baseada em múltiplos fatores.
        """
        if not target: return 0.3

        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        strength_ratio = attacker_strength / max(target_strength, 1)
        
        if 1.1 <= strength_ratio <= 1.3: base_confidence = 0.9
        elif 1.0 <= strength_ratio < 1.1: base_confidence = 0.8
        elif 0.9 <= strength_ratio < 1.0: base_confidence = 0.7
        elif strength_ratio > 1.3: base_confidence = 0.8
        else: base_confidence = 0.5
        
        th_difference = target.town_hall - attacker.town_hall
        if th_difference == 0: th_modifier = 1.0
        elif th_difference == 1: th_modifier = 0.8
        elif th_difference == -1: th_modifier = 1.1
        elif th_difference <= -2: th_modifier = 1.2
        else: th_modifier = 0.6
        
        attack_type_modifier = 1.0
        if attack_type == AttackType.MIRROR and target.map_position == attacker.map_position: attack_type_modifier = 1.1
        elif attack_type == AttackType.SAFE and strength_ratio > 1.2: attack_type_modifier = 1.15
        elif attack_type == AttackType.DIP and 1.0 <= strength_ratio <= 1.2: attack_type_modifier = 1.05
        
        final_confidence = base_confidence * th_modifier * attack_type_modifier
        return max(0.4, min(0.95, final_confidence))

    def _determine_attack_strategy(self, attacker: Any, mirror_target: Optional[Any]) -> AttackType:
        """
        Determina a estratégia de ataque mais inteligente.
        """
        if not mirror_target: return AttackType.SAFE
        
        attacker_strength = self._calculate_player_strength(attacker)
        mirror_strength = self._calculate_player_strength(mirror_target)
        strength_diff = attacker_strength - mirror_strength
        
        if mirror_target.town_hall > attacker.town_hall + 1: return AttackType.SAFE
        if strength_diff > self.STRENGTH_ADVANTAGE_THRESHOLD and mirror_target.town_hall <= attacker.town_hall: return AttackType.DIP
        if strength_diff < self.STRENGTH_DISADVANTAGE_THRESHOLD: return AttackType.SAFE
        
        return AttackType.MIRROR

    def _generate_phase1_recommendations(self, war: Any, our_clan: Any, opponent: Any) -> List[AttackRecommendation]:
        """
        Gera recomendações inteligentes para a Fase 1.
        """
        recommendations = []
        assigned_targets = set()
        
        sorted_attackers = sorted([m for m in our_clan.members if not m.attacks], key=self._calculate_player_strength, reverse=True)

        for member in sorted_attackers:
            mirror_target = next((m for m in opponent.members if m.map_position == member.map_position), None)
            attack_type = self._determine_attack_strategy(member, mirror_target)
            
            viable_targets = self._get_viable_targets(opponent.members, assigned_targets, member)
            
            # CORREÇÃO: Lógica de fallback para garantir que todos tenham um alvo.
            if not viable_targets:
                self.logger.warning(f"Nenhum alvo viável para {member.name} (TH{member.town_hall}) sob regras padrão. Tentando com regras flexíveis...")
                viable_targets = self._get_viable_targets(opponent.members, assigned_targets, member, flexible_rules=True)

            if not viable_targets:
                self.logger.warning(f"Ainda nenhum alvo viável para {member.name} (TH{member.town_hall}) mesmo com regras flexíveis.")
                continue

            target = self._find_optimal_target(member, viable_targets, attack_type)
            if not target: continue

            confidence = self._calculate_confidence_score(member, target, attack_type)
            
            member_strength = self._calculate_player_strength(member)
            remaining_targets = sorted([t for t in viable_targets if t.map_position != target.map_position], key=lambda t: abs(self._calculate_player_strength(t) - member_strength))
            alternative_targets = [t.map_position for t in remaining_targets[:2]]

            justification = self._generate_intelligent_justification(member, target, attack_type, mirror_target)

            rec = AttackRecommendation(
                member_name=member.name, member_th=member.town_hall, member_pos=member.map_position,
                attack_number=1, attack_type=attack_type, recommended_target_pos=target.map_position,
                recommended_target_th=target.town_hall, justification=justification,
                confidence_score=confidence, alternative_targets=alternative_targets
            )
            
            assigned_targets.add(target.map_position)
            recommendations.append(rec)
            self.logger.info(f"Recomendação: {member.name} (TH{member.town_hall}) -> #{target.map_position} (TH{target.town_hall}) - {attack_type.value} - {confidence:.0%}")

        return recommendations

    def _generate_intelligent_justification(self, attacker: Any, target: Any, attack_type: AttackType, mirror_target: Optional[Any]) -> str:
        """
        Gera justificativas inteligentes e contextuais.
        """
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        strength_diff = attacker_strength - target_strength
        
        is_mirror_attack = target.map_position == attacker.map_position
        
        if attack_type == AttackType.DIP:
            return f"DIP estratégico no #{target.map_position}. Sua força superior (+{strength_diff}) permite atacar um alvo forte e aliviar o time." if not is_mirror_attack else f"Ataque seu espelho com confiança! Você tem vantagem de força (+{strength_diff}). Busque 3 estrelas."
        
        elif attack_type == AttackType.SAFE:
            if mirror_target and mirror_target.town_hall > attacker.town_hall:
                return f"Seu espelho (#{mirror_target.map_position}, TH{mirror_target.town_hall}) é superior. Ataque seguro para garantir 3 estrelas."
            elif mirror_target:
                mirror_diff = attacker_strength - self._calculate_player_strength(mirror_target)
                return f"Seu espelho é desafiador (-{abs(mirror_diff)} força). Ataque mais fácil para garantir 3 estrelas."
            else:
                return f"Ataque seguro no #{target.map_position}. Foque em garantir 3 estrelas com sua vantagem ({strength_diff})."
        
        else:  # MIRROR
            if is_mirror_attack:
                if abs(strength_diff) < 50: return f"Ataque equilibrado no seu espelho. Forças similares - foque na execução perfeita."
                elif strength_diff > 0: return f"Ataque seu espelho com leve vantagem (+{strength_diff}). Busque 3 estrelas com confiança."
                else: return f"Desafio no seu espelho (-{abs(strength_diff)}). Execute perfeitamente para 2-3 estrelas."
            else: return f"Seu espelho não estava disponível. Atacando #{target.map_position} com força similar para manter equilíbrio."

    def _get_cleanup_targets(self, opponent: Any) -> List[Dict[str, Any]]:
        """Identifica alvos que precisam de limpeza, priorizando por importância."""
        cleanup_targets = []
        for member in opponent.members:
            if hasattr(member, 'best_opponent_attack') and member.best_opponent_attack and 1 <= member.best_opponent_attack.stars < 3:
                attack = member.best_opponent_attack
                stars_priority = (3 - attack.stars) * 1000
                destruction_priority = (100 - attack.destruction) * 10
                position_priority = max(0, 50 - member.map_position)
                total_priority = stars_priority + destruction_priority + position_priority
                cleanup_targets.append({"position": member.map_position, "stars": attack.stars, "destruction": attack.destruction, "th": member.town_hall, "priority": total_priority})
        return sorted(cleanup_targets, key=lambda x: x['priority'], reverse=True)

    def _generate_phase2_recommendations(self, war: Any, our_clan: Any, opponent: Any) -> List[AttackRecommendation]:
        """Gera recomendações inteligentes para a Fase 2 (limpeza)."""
        recommendations = []
        cleanup_targets = self._get_cleanup_targets(opponent)
        available_attackers = sorted([m for m in our_clan.members if len(m.attacks) < war.attacks_per_member], key=self._calculate_player_strength, reverse=True)
        assigned_cleanup_targets = set()

        for member in available_attackers:
            attack_num = len(member.attacks) + 1
            best_cleanup_target = None
            for cleanup_target_info in cleanup_targets:
                if cleanup_target_info['position'] not in assigned_cleanup_targets:
                    target = next((m for m in opponent.members if m.map_position == cleanup_target_info['position']), None)
                    if target and self._is_viable_target(member, target)[0]:
                        best_cleanup_target = cleanup_target_info
                        break
            
            if best_cleanup_target:
                target_obj = next(m for m in opponent.members if m.map_position == best_cleanup_target['position'])
                confidence = self._calculate_confidence_score(member, target_obj, AttackType.CLEANUP)
                justification = f"LIMPEZA CRÍTICA! #{best_cleanup_target['position']} tem {'★' * best_cleanup_target['stars']} ({best_cleanup_target['destruction']}%). Finalize para 3 estrelas!"
                rec = AttackRecommendation(member_name=member.name, member_th=member.town_hall, member_pos=member.map_position, attack_number=attack_num, attack_type=AttackType.CLEANUP, recommended_target_pos=best_cleanup_target["position"], recommended_target_th=best_cleanup_target["th"], justification=justification, confidence_score=confidence)
                assigned_cleanup_targets.add(best_cleanup_target['position'])
                recommendations.append(rec)
            else:
                available_fresh_targets = self._get_viable_targets(opponent.members, assigned_cleanup_targets, member)
                if available_fresh_targets:
                    safe_target = self._find_optimal_target(member, available_fresh_targets, AttackType.SAFE)
                    if safe_target:
                        confidence = self._calculate_confidence_score(member, safe_target, AttackType.SAFE)
                        rec = AttackRecommendation(member_name=member.name, member_th=member.town_hall, member_pos=member.map_position, attack_number=attack_num, attack_type=AttackType.SAFE, recommended_target_pos=safe_target.map_position, recommended_target_th=safe_target.town_hall, justification="Sem limpeza viável. Ataque fresh para maximizar estrelas totais.", confidence_score=confidence)
                        assigned_cleanup_targets.add(safe_target.map_position)
                        recommendations.append(rec)
        return recommendations

    def create_war_plan(self, war: Any, clan_tag: str, prediction_data: Dict) -> Dict[str, Any]:
        """Ponto de entrada principal para criar o plano de guerra inteligente."""
        if not war or war.state not in ['inWar', 'preparation']:
            return {"success": False, "error": "A guerra não está ativa ou em preparação."}
        
        try:
            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan
            if not our_clan or not opponent: return {"success": False, "error": "Erro ao identificar os clãs da guerra."}
            
            war_phase = self._determine_war_phase(war)
            
            recommendations = []
            if war_phase in [WarPhase.PREPARATION, WarPhase.PHASE_1]:
                phase_title = "Fase 1 - Ataques Táticos Inteligentes"
                recommendations = self._generate_phase1_recommendations(war, our_clan, opponent)
            else:
                phase_title = "Fase 2 - Limpeza Estratégica e Finalização"
                recommendations = self._generate_phase2_recommendations(war, our_clan, opponent)

            if not recommendations:
                return {"success": True, "phase_title": "Análise Completa - Nenhuma recomendação necessária", "recommendations": []}

            recommendations.sort(key=lambda x: x.member_pos)
            
            avg_confidence = sum(r.confidence_score for r in recommendations) / len(recommendations) if recommendations else 0
            self.logger.info(f"Plano gerado: {len(recommendations)} recomendações, confiança média: {avg_confidence:.1%}")
            
            recommendations_dict = []
            for r in recommendations:
                rec_data = r.__dict__
                rec_data['attack_type'] = r.attack_type.value
                recommendations_dict.append(rec_data)

            return {
                "success": True, "phase_title": phase_title, "recommendations": recommendations_dict,
                "prediction_summary": prediction_data.get("summary_panel", "Análise em andamento..."),
                "generated_at": datetime.datetime.now(pytz.utc).isoformat(),
                "statistics": {
                    "total_recommendations": len(recommendations), "average_confidence": avg_confidence,
                    "attack_types": {
                        "mirror": len([r for r in recommendations if r.attack_type == AttackType.MIRROR]),
                        "dip": len([r for r in recommendations if r.attack_type == AttackType.DIP]),
                        "safe": len([r for r in recommendations if r.attack_type == AttackType.SAFE]),
                        "cleanup": len([r for r in recommendations if r.attack_type == AttackType.CLEANUP])
                    }}}
        except Exception as e:
            self.logger.error(f"Erro crítico ao gerar plano de guerra: {e}", exc_info=True)
            return {"success": False, "error": f"Erro interno ao processar dados da guerra: {str(e)}"}

class WarAdvisorCog(commands.Cog, name="Conselheiro de Guerra IA"):
    def __init__(self, bot):
        self.bot = bot
        self.war_advisor = WarAdvisorSystem()
        self.logger = logging.getLogger(f"{__name__}.WarAdvisorCog")

    @commands.command(name='plano')
    @commands.has_permissions(administrator=True)
    async def force_plan_generation(self, ctx):
        """Força a geração e exibição do plano de guerra atual."""
        await ctx.send("🔄 **Gerando plano de guerra inteligente...** Analisando forças e viabilidades...")
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            prediction_data = await self.bot.war_prediction_system.predict_war_outcome(war, self.bot.clan_tag)
            plan = self.war_advisor.create_war_plan(war, self.bot.clan_tag, prediction_data)

            if not plan.get("success"):
                await ctx.send(f"❌ **Erro ao gerar o plano:** {plan.get('error')}")
                return
            
            embed = discord.Embed(title=f"🎯 {plan.get('phase_title')}", description=f"**IA v5.1** - Análise inteligente com fallback flexível", color=discord.Color.green())
            stats = plan.get("statistics", {})
            if stats:
                embed.add_field(name="📊 Estatísticas", value=f"**Total:** {stats.get('total_recommendations', 0)}\n**Confiança média:** {stats.get('average_confidence', 0):.0%}\n**Mirror:** {stats.get('attack_types', {}).get('mirror', 0)} | **DIP:** {stats.get('attack_types', {}).get('dip', 0)} | **Safe:** {stats.get('attack_types', {}).get('safe', 0)}", inline=False)
            
            recommendations = plan.get("recommendations", [])
            for rec in recommendations[:10]:
                confidence_emoji = "🟢" if rec['confidence_score'] > 0.8 else "🟡" if rec['confidence_score'] > 0.6 else "🟠"
                field_name = f"#{rec['member_pos']} {rec['member_name']} (TH{rec['member_th']})"
                field_value = f"**🎯 Alvo:** #{rec['recommended_target_pos']} (TH{rec['recommended_target_th']})\n**{confidence_emoji} Confiança:** {rec['confidence_score']:.0%}\n**🤖 IA:** _{rec['justification']}_"
                if rec.get('alternative_targets'): field_value += f"\n**📋 Alternativas:** #{', #'.join(map(str, rec['alternative_targets']))}"
                embed.add_field(name=field_name, value=field_value, inline=False)
            
            if len(recommendations) > 10:
                embed.add_field(name="ℹ️ Informação", value=f"Mostrando 10 de {len(recommendations)} recomendações.", inline=False)
            embed.set_footer(text=f"Gerado em: {plan.get('generated_at', 'N/A')}")
            await ctx.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Erro ao executar comando de plano: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro crítico:** {str(e)}")

    @commands.command(name='analise')
    @commands.has_permissions(administrator=True)
    async def analyze_war_balance(self, ctx):
        """Analisa o equilíbrio da guerra atual e sugere estratégia geral."""
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state not in ['inWar', 'preparation']:
                await ctx.send("❌ Nenhuma guerra ativa encontrada.")
                return
            
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
            
            our_total_strength = sum(self.war_advisor._calculate_player_strength(m) for m in our_clan.members)
            opp_total_strength = sum(self.war_advisor._calculate_player_strength(m) for m in opponent.members)
            advantage_percent = ((our_total_strength - opp_total_strength) / opp_total_strength) * 100
            
            our_th_dist = {th: sum(1 for m in our_clan.members if m.town_hall == th) for th in range(17, 0, -1) if any(m.town_hall == th for m in our_clan.members)}
            opp_th_dist = {th: sum(1 for m in opponent.members if m.town_hall == th) for th in range(17, 0, -1) if any(m.town_hall == th for m in opponent.members)}

            embed = discord.Embed(title="⚖️ Análise de Equilíbrio da Guerra", color=discord.Color.blue() if advantage_percent > 5 else discord.Color.orange() if advantage_percent < -5 else discord.Color.green())
            
            if advantage_percent > 10: advantage_text, strategy = f"🟢 **Grande vantagem** (+{advantage_percent:.1f}%)", "Ataques ousados (DIP) para maximizar estrelas."
            elif advantage_percent > 5: advantage_text, strategy = f"🟢 **Leve vantagem** (+{advantage_percent:.1f}%)", "Mix equilibrado de ataques mirror e dip seletivos."
            elif advantage_percent > -5: advantage_text, strategy = f"🟡 **Guerra equilibrada** ({advantage_percent:+.1f}%)", "Foco em execução perfeita e ataques mirror."
            elif advantage_percent > -10: advantage_text, strategy = f"🟠 **Leve desvantagem** ({advantage_percent:.1f}%)", "Ataques seguros e limpeza eficiente."
            else: advantage_text, strategy = f"🔴 **Grande desvantagem** ({advantage_percent:.1f}%)", "Máxima disciplina, ataques 100% seguros."
            
            embed.add_field(name="💪 Força Total", value=f"**Nós:** {our_total_strength:,}\n**Oponente:** {opp_total_strength:,}\n{advantage_text}", inline=True)
            embed.add_field(name="🎯 Estratégia Recomendada", value=strategy, inline=False)
            
            th_analysis = [f"TH{th}: {our_th_dist.get(th, 0)} vs {opp_th_dist.get(th, 0)} {'**(+'+str(our_th_dist.get(th, 0) - opp_th_dist.get(th, 0))+')**' if our_th_dist.get(th, 0) > opp_th_dist.get(th, 0) else '**('+str(our_th_dist.get(th, 0) - opp_th_dist.get(th, 0))+')**' if our_th_dist.get(th, 0) < opp_th_dist.get(th, 0) else ''}" for th in sorted(set(our_th_dist.keys()) | set(opp_th_dist.keys()), reverse=True)]
            if th_analysis: embed.add_field(name="🏰 Distribuição por Town Hall", value="\n".join(th_analysis), inline=False)
            
            await ctx.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Erro na análise da guerra: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro na análise:** {str(e)}")

async def setup(bot: commands.Bot):
    await bot.add_cog(WarAdvisorCog(bot))

