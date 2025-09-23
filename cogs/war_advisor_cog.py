# -*- coding: utf-8 -*-
"""
Módulo do Conselheiro de Guerra IA - ClashGenius (v5.2 - Lógica Segura)
Sistema inteligente para análise e geração de planos táticos de guerra.
CORREÇÕES: Adicionada trava de segurança para ataques a CV superior.
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
    MAX_TH_DIFFERENCE_UP = 1
    MAX_TH_DIFFERENCE_DOWN = 3
    STRENGTH_ADVANTAGE_THRESHOLD = 150
    STRENGTH_DISADVANTAGE_THRESHOLD = -100
    WAR_PHASE_SPLIT_HOURS = 12
    MIN_CONFIDENCE_SCORE = 0.4
    
    def __init__(self):
        self.logger = logging.getLogger("war_advisor_v5.2")
        self._setup_logging()

    def _setup_logging(self):
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _calculate_player_strength(self, player: Any) -> int:
        if not player or not hasattr(player, 'town_hall'):
            return 0
        
        th_multipliers = {
            1: 10, 2: 20, 3: 40, 4: 80, 5: 120, 6: 180, 7: 250, 8: 350, 9: 500, 
            10: 700, 11: 950, 12: 1250, 13: 1600, 14: 2000, 15: 2500, 16: 3100, 17: 3800
        }
        base_strength = th_multipliers.get(player.town_hall, player.town_hall * 100)
        
        hero_bonus = 0
        if hasattr(player, 'heroes') and player.heroes:
            for hero in player.heroes:
                if hero.is_home_base:
                    hero_multiplier = max(1, player.town_hall // 3)
                    hero_bonus += hero.level * hero_multiplier
        
        return int(base_strength + hero_bonus)

    def _is_viable_target(self, attacker: Any, target: Any, flexible_rules: bool = False) -> Tuple[bool, str]:
        attacker_th = attacker.town_hall
        target_th = target.town_hall
        
        if target_th > attacker_th + self.MAX_TH_DIFFERENCE_UP:
            return False, f"Alvo muito superior (TH{target_th} vs TH{attacker_th})"
        
        if not flexible_rules and target_th < attacker_th - self.MAX_TH_DIFFERENCE_DOWN:
            return False, f"Alvo muito inferior (desperdício de potencial)"
        
        if hasattr(target, 'best_opponent_attack') and target.best_opponent_attack and target.best_opponent_attack.stars == 3:
            return False, "Alvo já possui 3 estrelas"
        
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
        viable_targets = []
        for member in opponent_members:
            if member.map_position in assigned_targets: continue
            is_viable, reason = self._is_viable_target(attacker, member, flexible_rules=flexible_rules)
            if is_viable:
                viable_targets.append(member)
            else:
                self.logger.debug(f"Alvo #{member.map_position} não viável para {attacker.name}: {reason}")
        return viable_targets

    def _find_optimal_target(self, attacker: Any, viable_targets: List[Any], attack_type: AttackType) -> Optional[Any]:
        if not viable_targets: return None
        attacker_strength = self._calculate_player_strength(attacker)
        if attack_type == AttackType.DIP:
            candidates = [t for t in viable_targets if t.town_hall >= attacker.town_hall]
            return max(candidates, key=self._calculate_player_strength) if candidates else max(viable_targets, key=self._calculate_player_strength)
        elif attack_type == AttackType.SAFE:
            candidates = [t for t in viable_targets if t.town_hall <= attacker.town_hall and self._calculate_player_strength(t) <= attacker_strength]
            return min(candidates, key=self._calculate_player_strength) if candidates else min(viable_targets, key=self._calculate_player_strength)
        else: # MIRROR
            mirror = next((t for t in viable_targets if t.map_position == attacker.map_position), None)
            return mirror if mirror else min(viable_targets, key=lambda t: abs(self._calculate_player_strength(t) - attacker_strength))

    def _calculate_confidence_score(self, attacker: Any, target: Any, attack_type: AttackType) -> float:
        if not target: return 0.3
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)
        strength_ratio = attacker_strength / max(target_strength, 1)
        
        if 1.1 <= strength_ratio <= 1.3: base_confidence = 0.9
        elif 1.0 <= strength_ratio < 1.1: base_confidence = 0.8
        elif 0.9 <= strength_ratio < 1.0: base_confidence = 0.7
        elif strength_ratio > 1.3: base_confidence = 0.8
        else: base_confidence = 0.5
        
        th_diff = target.town_hall - attacker.town_hall
        if th_diff == 0: th_modifier = 1.0
        elif th_diff == 1: th_modifier = 0.8
        elif th_diff == -1: th_modifier = 1.1
        elif th_diff <= -2: th_modifier = 1.2
        else: th_modifier = 0.6
        
        type_modifier = 1.0
        if attack_type == AttackType.MIRROR and target.map_position == attacker.map_position: type_modifier = 1.1
        elif attack_type == AttackType.SAFE and strength_ratio > 1.2: type_modifier = 1.15
        elif attack_type == AttackType.DIP and 1.0 <= strength_ratio <= 1.2: type_modifier = 1.05
        
        final_confidence = base_confidence * th_modifier * type_modifier
        return max(0.4, min(0.95, final_confidence))

    def _determine_attack_strategy(self, attacker: Any, mirror_target: Optional[Any]) -> AttackType:
        if not mirror_target: return AttackType.SAFE
        
        attacker_strength = self._calculate_player_strength(attacker)
        mirror_strength = self._calculate_player_strength(mirror_target)
        strength_diff = attacker_strength - mirror_strength
        
        # Trava de Segurança: Se o espelho já é um CV acima, não arriscar um DIP
        if mirror_target.town_hall > attacker.town_hall:
             return AttackType.MIRROR if strength_diff > self.STRENGTH_DISADVANTAGE_THRESHOLD else AttackType.SAFE

        if strength_diff > self.STRENGTH_ADVANTAGE_THRESHOLD: return AttackType.DIP
        if strength_diff < self.STRENGTH_DISADVANTAGE_THRESHOLD: return AttackType.SAFE
        
        return AttackType.MIRROR

    def _generate_phase1_recommendations(self, war: Any, our_clan: Any, opponent: Any) -> List[AttackRecommendation]:
        recommendations = []
        assigned_targets = set()
        sorted_attackers = sorted([m for m in our_clan.members if not m.attacks], key=self._calculate_player_strength, reverse=True)

        for member in sorted_attackers:
            mirror = next((m for m in opponent.members if m.map_position == member.map_position), None)
            attack_type = self._determine_attack_strategy(member, mirror)
            
            viable = self._get_viable_targets(opponent.members, assigned_targets, member)
            if not viable:
                self.logger.warning(f"Nenhum alvo viável para {member.name}. Tentando com regras flexíveis...")
                viable = self._get_viable_targets(opponent.members, assigned_targets, member, flexible_rules=True)
            if not viable:
                self.logger.error(f"Nenhum alvo para {member.name} mesmo com regras flexíveis.")
                continue

            target = self._find_optimal_target(member, viable, attack_type)
            if not target: continue

            confidence = self._calculate_confidence_score(member, target, attack_type)
            
            alternatives = sorted([t for t in viable if t.map_position != target.map_position], key=lambda t: abs(self._calculate_player_strength(t) - self._calculate_player_strength(member)))
            
            rec = AttackRecommendation(
                member_name=member.name, member_th=member.town_hall, member_pos=member.map_position,
                attack_number=1, attack_type=attack_type, recommended_target_pos=target.map_position,
                recommended_target_th=target.town_hall, 
                justification=self._generate_intelligent_justification(member, target, attack_type, mirror),
                confidence_score=confidence, 
                alternative_targets=[t.map_position for t in alternatives[:2]]
            )
            assigned_targets.add(target.map_position)
            recommendations.append(rec)
            self.logger.info(f"Rec: {member.name} (TH{member.town_hall}) -> #{target.map_position} (TH{target.town_hall}) - {attack_type.value} - {confidence:.0%}")

        return recommendations

    def _generate_intelligent_justification(self, attacker: Any, target: Any, attack_type: AttackType, mirror: Optional[Any]) -> str:
        s_diff = self._calculate_player_strength(attacker) - self._calculate_player_strength(target)
        is_mirror = target.map_position == attacker.map_position
        
        if attack_type == AttackType.DIP:
            return f"DIP estratégico no #{target.map_position}. Sua força superior (+{s_diff}) permite atacar um alvo forte e aliviar o time."
        elif attack_type == AttackType.SAFE:
            if mirror and mirror.town_hall > attacker.town_hall:
                return f"Seu espelho (#{mirror.map_position}, TH{mirror.town_hall}) é superior. Ataque seguro para garantir 3 estrelas."
            else:
                return f"Ataque seguro no #{target.map_position}. Foque em garantir 3 estrelas com sua vantagem ({s_diff})."
        else: # MIRROR
            if is_mirror:
                if abs(s_diff) < 50: return "Ataque equilibrado no seu espelho. Forças similares - foque na execução perfeita."
                return f"Ataque seu espelho com {'leve vantagem' if s_diff > 0 else 'desafio'} ({s_diff:+} força). Busque {'3 estrelas com confiança' if s_diff > 0 else '2-3 estrelas'}."
            else:
                return f"Seu espelho não estava disponível. Atacando #{target.map_position} com força similar para manter equilíbrio."

    def _get_cleanup_targets(self, opponent: Any) -> List[Dict[str, Any]]:
        targets = []
        for m in opponent.members:
            if hasattr(m, 'best_opponent_attack') and m.best_opponent_attack and 1 <= m.best_opponent_attack.stars < 3:
                prio = (3 - m.best_opponent_attack.stars) * 1000 + (100 - m.best_opponent_attack.destruction) * 10 + max(0, 50 - m.map_position)
                targets.append({"position": m.map_position, "stars": m.best_opponent_attack.stars, "destruction": m.best_opponent_attack.destruction, "th": m.town_hall, "priority": prio})
        return sorted(targets, key=lambda x: x['priority'], reverse=True)

    def _generate_phase2_recommendations(self, war: Any, our_clan: Any, opponent: Any) -> List[AttackRecommendation]:
        recommendations = []
        cleanup_targets = self._get_cleanup_targets(opponent)
        attackers = sorted([m for m in our_clan.members if len(m.attacks) < war.attacks_per_member], key=self._calculate_player_strength, reverse=True)
        assigned = set()

        for member in attackers:
            target_info = next((t for t in cleanup_targets if t['position'] not in assigned and self._is_viable_target(member, next(m for m in opponent.members if m.map_position == t['position']))[0]), None)
            
            if target_info:
                target_obj = next(m for m in opponent.members if m.map_position == target_info['position'])
                rec = AttackRecommendation(
                    member_name=member.name, member_th=member.town_hall, member_pos=member.map_position, attack_number=len(member.attacks) + 1,
                    attack_type=AttackType.CLEANUP, recommended_target_pos=target_info["position"], recommended_target_th=target_info["th"],
                    justification=f"LIMPEZA CRÍTICA! #{target_info['position']} tem {'★' * target_info['stars']} ({target_info['destruction']}%).",
                    confidence_score=self._calculate_confidence_score(member, target_obj, AttackType.CLEANUP)
                )
                assigned.add(target_info['position'])
                recommendations.append(rec)
            else:
                fresh = self._get_viable_targets(opponent.members, assigned, member)
                if fresh:
                    safe_target = self._find_optimal_target(member, fresh, AttackType.SAFE)
                    if safe_target:
                        rec = AttackRecommendation(
                            member_name=member.name, member_th=member.town_hall, member_pos=member.map_position, attack_number=len(member.attacks) + 1,
                            attack_type=AttackType.SAFE, recommended_target_pos=safe_target.map_position, recommended_target_th=safe_target.town_hall,
                            justification="Sem limpeza viável. Ataque fresh para maximizar estrelas totais.",
                            confidence_score=self._calculate_confidence_score(member, safe_target, AttackType.SAFE)
                        )
                        assigned.add(safe_target.map_position)
                        recommendations.append(rec)
        return recommendations

    def create_war_plan(self, war: Any, clan_tag: str, prediction_data: Dict) -> Dict[str, Any]:
        if not war or war.state not in ['inWar', 'preparation']:
            return {"success": False, "error": "A guerra não está ativa ou em preparação."}
        try:
            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan
            if not our_clan or not opponent: return {"success": False, "error": "Erro ao identificar os clãs."}
            
            war_phase = self._determine_war_phase(war)
            phase_map = {
                WarPhase.PREPARATION: ("Fase 1 - Ataques Táticos Inteligentes", self._generate_phase1_recommendations),
                WarPhase.PHASE_1: ("Fase 1 - Ataques Táticos Inteligentes", self._generate_phase1_recommendations),
                WarPhase.PHASE_2: ("Fase 2 - Limpeza Estratégica", self._generate_phase2_recommendations)
            }
            phase_title, rec_func = phase_map.get(war_phase)
            recommendations = rec_func(war, our_clan, opponent)

            if not recommendations:
                return {"success": True, "phase_title": "Análise Completa - Nenhuma recomendação necessária", "recommendations": []}

            recommendations.sort(key=lambda x: x.member_pos)
            avg_conf = sum(r.confidence_score for r in recommendations) / len(recommendations) if recommendations else 0
            self.logger.info(f"Plano gerado: {len(recommendations)} recs, confiança média: {avg_conf:.1%}")
            
            rec_dict = []
            for r in recommendations:
                data = r.__dict__; data['attack_type'] = r.attack_type.value; rec_dict.append(data)

            return {
                "success": True, "phase_title": phase_title, "recommendations": rec_dict,
                "prediction_summary": prediction_data.get("summary_panel", "Análise em andamento..."),
                "generated_at": datetime.datetime.now(pytz.utc).isoformat(),
                "statistics": {
                    "total_recommendations": len(rec_dict), "average_confidence": avg_conf,
                    "attack_types": {t.value: sum(1 for r in rec_dict if r['attack_type'] == t.value) for t in AttackType}
                }}
        except Exception as e:
            self.logger.error(f"Erro crítico ao gerar plano de guerra: {e}", exc_info=True)
            return {"success": False, "error": f"Erro interno: {e}"}

class WarAdvisorCog(commands.Cog, name="Conselheiro de Guerra IA"):
    def __init__(self, bot):
        self.bot = bot
        self.war_advisor = WarAdvisorSystem()
        self.logger = logging.getLogger(f"{__name__}.WarAdvisorCog")

    @commands.command(name='plano')
    @commands.has_permissions(administrator=True)
    async def force_plan_generation(self, ctx):
        await ctx.send("🔄 **Gerando plano de guerra v5.2...**")
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            prediction = await self.bot.war_prediction_system.predict_war_outcome(war, self.bot.clan_tag)
            plan = self.war_advisor.create_war_plan(war, self.bot.clan_tag, prediction)

            if not plan.get("success"):
                await ctx.send(f"❌ **Erro:** {plan.get('error')}")
                return
            
            embed = discord.Embed(title=f"🎯 {plan.get('phase_title')}", description=f"**IA v5.2** - Análise com trava de segurança de CV.", color=discord.Color.green())
            stats = plan.get("statistics", {})
            if stats:
                types = stats.get('attack_types', {})
                embed.add_field(name="📊 Estatísticas", value=f"**Total:** {stats.get('total_recommendations', 0)}\n**Confiança:** {stats.get('average_confidence', 0):.0%}\n**Tipos:** M({types.get('mirror',0)}) D({types.get('dip',0)}) S({types.get('safe',0)})", inline=False)
            
            for rec in plan.get("recommendations", [])[:10]:
                emoji = "🟢" if rec['confidence_score'] > 0.8 else "🟡" if rec['confidence_score'] > 0.6 else "🟠"
                value = f"**🎯 Alvo:** #{rec['recommended_target_pos']} (TH{rec['recommended_target_th']})\n**{emoji} Confiança:** {rec['confidence_score']:.0%}\n**🤖 IA:** _{rec['justification']}_"
                if rec.get('alternative_targets'): value += f"\n**📋 Alt:** #{', #'.join(map(str, rec['alternative_targets']))}"
                embed.add_field(name=f"#{rec['member_pos']} {rec['member_name']} (TH{rec['member_th']})", value=value, inline=False)
            
            if len(plan.get("recommendations", [])) > 10:
                embed.add_field(name="ℹ️ Informação", value=f"Mostrando 10 de {len(plan.get('recommendations', []))} recomendações.", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Erro no comando plano: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro crítico:** {e}")

    @commands.command(name='analise')
    @commands.has_permissions(administrator=True)
    async def analyze_war_balance(self, ctx):
        await ctx.send("⚖️ Analisando equilíbrio da guerra...")
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state not in ['inWar', 'preparation']:
                await ctx.send("❌ Nenhuma guerra ativa encontrada.")
                return
            
            our_clan, opp_clan = (war.clan, war.opponent) if war.clan.tag == self.bot.clan_tag else (war.opponent, war.clan)
            our_strength = sum(self.war_advisor._calculate_player_strength(m) for m in our_clan.members)
            opp_strength = sum(self.war_advisor._calculate_player_strength(m) for m in opp_clan.members)
            adv_percent = ((our_strength - opp_strength) / opp_strength) * 100
            
            our_th = {th: sum(1 for m in our_clan.members if m.town_hall == th) for th in range(17, 0, -1) if any(m.town_hall == th for m in our_clan.members)}
            opp_th = {th: sum(1 for m in opp_clan.members if m.town_hall == th) for th in range(17, 0, -1) if any(m.town_hall == th for m in opp_clan.members)}

            embed = discord.Embed(title="⚖️ Análise de Equilíbrio da Guerra", color=discord.Color.green())
            
            if adv_percent > 10: text, strat = f"🟢 **Grande vantagem** (+{adv_percent:.1f}%)", "Ataques ousados (DIP)."
            elif adv_percent > 5: text, strat = f"🟢 **Leve vantagem** (+{adv_percent:.1f}%)", "Mix de mirror e dip."
            elif adv_percent > -5: text, strat = f"🟡 **Equilibrada** ({adv_percent:+.1f}%)", "Foco em ataques mirror."
            elif adv_percent > -10: text, strat = f"🟠 **Leve desvantagem** ({adv_percent:.1f}%)", "Ataques seguros e limpeza."
            else: text, strat = f"🔴 **Grande desvantagem** ({adv_percent:.1f}%)", "Máxima disciplina, ataques seguros."
            
            embed.add_field(name="💪 Força Total", value=f"**Nós:** {our_strength:,}\n**Oponente:** {opp_strength:,}\n{text}", inline=True)
            embed.add_field(name="🎯 Estratégia", value=strat, inline=False)
            
            th_analysis = [f"TH{th}: {our_th.get(th, 0)} vs {opp_th.get(th, 0)}" for th in sorted(set(our_th.keys()) | set(opp_th.keys()), reverse=True)]
            if th_analysis: embed.add_field(name="🏰 Distribuição de TH", value="\n".join(th_analysis), inline=False)
            
            await ctx.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Erro na análise: {e}", exc_info=True)
            await ctx.send(f"❌ **Erro:** {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(WarAdvisorCog(bot))

