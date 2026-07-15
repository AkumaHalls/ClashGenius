# -*- coding: utf-8 -*-
"""
Módulo do Conselheiro de Guerra IA - ClashGenius (v7.0 - Otimização Combinatória)
Sistema inteligente usando Algoritmo Húngaro (Linear Sum Assignment) e Matrizes.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from discord.ext import commands
import datetime
import pytz
import discord
import numpy as np
from scipy.optimize import linear_sum_assignment

class AttackType(Enum):
    MIRROR = "mirror"
    DIP = "dip"
    SAFE = "safe"
    CLEANUP = "cleanup"
    BONUS = "bonus"
    DESPERATE = "desperate"

class WarPhase(Enum):
    PREPARATION = "preparation"
    PHASE_1 = "phase_1"
    PHASE_2 = "phase_2"

@dataclass
class AttackRecommendation:
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
    WAR_PHASE_SPLIT_HOURS = 12
    
    def __init__(self):
        self.logger = logging.getLogger("war_advisor_v6.0_matrix")
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
        if not player or not hasattr(player, 'town_hall'): return 0
        
        th_multipliers = {
            1: 10, 2: 20, 3: 40, 4: 80, 5: 120, 6: 180, 7: 250, 8: 350, 9: 500, 
            10: 700, 11: 950, 12: 1250, 13: 1600, 14: 2000, 15: 2500, 16: 3100, 17: 3800
        }
        base_strength = th_multipliers.get(player.town_hall, player.town_hall * 100)
        
        hero_bonus = 0
        hero_penalty = 0
        equipment_bonus = 0
        
        home_heroes = ["Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion", "Minion Prince", "Dragon Duke"]
        
        if hasattr(player, 'heroes') and player.heroes:
            for hero in player.heroes:
                if hero.name in home_heroes:
                    hero_multiplier = max(1, player.town_hall // 3)
                    is_upg = getattr(hero, 'is_upgrading', False)
                    if is_upg: hero_penalty += hero.level * hero_multiplier * 0.8
                    else: hero_bonus += hero.level * hero_multiplier

        if hasattr(player, 'hero_equipment') and player.hero_equipment:
            for eq in player.hero_equipment:
                equipment_bonus += eq.level * 15

        return int(base_strength + hero_bonus + equipment_bonus - hero_penalty)

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

    def _calculate_match_metrics(self, attacker: Any, target: Any) -> Tuple[float, AttackType]:
        """Gera a probabilidade matemática e classifica o tipo de combate."""
        attacker_strength = self._calculate_player_strength(attacker)
        target_strength = self._calculate_player_strength(target)

        strength_ratio = attacker_strength / max(target_strength, 1)
        th_diff = attacker.town_hall - target.town_hall

        # Cálculo Vectorial de Probabilidade (Distância de Força)
        if th_diff == 0: prob = 0.50
        elif th_diff == 1: prob = 0.85
        elif th_diff >= 2: prob = 0.98
        elif th_diff == -1: prob = 0.15
        else: prob = 0.01

        # Ajuste Fino pelo Peso Bélico (Heróis + Equipamentos)
        prob += (strength_ratio - 1.0) * 0.35
        prob = max(0.01, min(0.99, prob))

        # Classificação Tática
        if th_diff > 0: a_type = AttackType.DIP
        elif th_diff < 0: a_type = AttackType.DESPERATE
        elif strength_ratio > 1.15: a_type = AttackType.SAFE
        elif strength_ratio < 0.85: a_type = AttackType.BONUS
        else: a_type = AttackType.MIRROR

        return prob, a_type

    def _generate_intelligent_justification(self, attacker: Any, target: Any, attack_type: AttackType, prob: float) -> str:
        """Explica a decisão da matriz de forma humana e técnica."""
        prob_pct = prob * 100
        if attack_type == AttackType.DIP:
            return f"[Garantia Matemática] Otimização de mapa (DIP Tático). A disparidade de força garante {prob_pct:.1f}% de chance de fechar a base de forma segura."
        elif attack_type == AttackType.CLEANUP:
            return f"[Correção de Rota] Alocação matemática para resgate. Sua força ({prob_pct:.1f}% de êxito estimado) foi calculada como a mais eficiente para raspar as estrelas restantes."
        elif attack_type == AttackType.SAFE:
            return f"[Recuo Tático] Vantagem bélica detectada. Atribuído a este alvo para minimizar os riscos de falha sistêmica ({prob_pct:.1f}% de confiança)."
        elif attack_type == AttackType.DESPERATE:
            return f"[Sacrifício Estratégico] Alvo superior (Chance remota: {prob_pct:.1f}%). Objetivo de vanguarda: Buscar as 2 estrelas ou revelar armadilhas."
        elif attack_type == AttackType.BONUS:
            return f"[Mapa Fechado] Treino/Scout. A matriz designou este alvo excedente para você praticar (Confiança: {prob_pct:.1f}%)."
        else: # MIRROR
            return f"[Combate Direto] O peso vetorial se alinha perfeitamente com seu espelho. Probabilidade de fechamento em {prob_pct:.1f}%."

    def _generate_recommendations_via_matrix(self, war: Any, our_clan: Any, opponent: Any, phase: WarPhase) -> List[AttackRecommendation]:
        """O Cérebro Húngaro: Resolve o problema de atribuição maximizando estrelas."""
        recommendations = []
        is_phase2 = (phase == WarPhase.PHASE_2)

        # 1. Definir Atacantes (Slots de Ataque)
        attack_slots = []
        for member in our_clan.members:
            attacks_used = len(member.attacks)
            attacks_left = war.attacks_per_member - attacks_used
            if attacks_left > 0:
                # Fase 1: Otimiza 1 ataque por pessoa. Fase 2: Otimiza todos restantes.
                num_to_plan = attacks_left if is_phase2 else 1
                for i in range(num_to_plan):
                     attack_slots.append({"member": member, "attack_number": attacks_used + i + 1})

        if not attack_slots: return []

        # 2. Definir Defensores (Bases Inimigas)
        target_slots = []
        for opp in opponent.members:
            stars = opp.best_opponent_attack.stars if hasattr(opp, 'best_opponent_attack') and opp.best_opponent_attack else 0
            is_closed = (stars == 3)
            # Se a base já tomou 3 estrelas, damos um peso residual minúsculo só pra preencher a matriz
            stars_left = max(3.0 - stars, 0.01) if not is_closed else 0.01
            target_slots.append({"member": opp, "stars_left": stars_left, "is_closed": is_closed})

        # Preenchimento de Matriz: Evita que atacantes fiquem de fora se houver poucos alvos vivos
        original_targets = list(target_slots)
        while len(target_slots) < len(attack_slots):
            target_slots.extend(original_targets)

        num_atk = len(attack_slots)
        num_def = len(target_slots)

        cost_matrix = np.zeros((num_atk, num_def))
        prob_matrix = np.zeros((num_atk, num_def))
        type_matrix = np.empty((num_atk, num_def), dtype=object)

        # 3. Preencher Custos Matemáticos
        for i, atk_slot in enumerate(attack_slots):
            attacker = atk_slot["member"]
            for j, def_slot in enumerate(target_slots):
                defender = def_slot["member"]
                
                prob, a_type = self._calculate_match_metrics(attacker, defender)
                
                if def_slot["is_closed"]:
                    # Custo gigantesco para bases que já foram destruídas (IA evita)
                    cost = 100.0 - prob 
                    a_type = AttackType.BONUS
                else:
                    if is_phase2 and def_slot["stars_left"] < 3:
                        a_type = AttackType.CLEANUP
                        expected_value = prob * def_slot["stars_left"] * 1.5 # Prioridade extra pra cleanup na Fase 2
                    else:
                        expected_value = prob * def_slot["stars_left"]

                    # Queremos o MENOR custo, então subtraímos o Valor Esperado de 10
                    cost = 10.0 - expected_value

                    # Punição severa: Impede um CV16 de atacar um CV13 e roubar alvo dos menores
                    th_diff = attacker.town_hall - defender.town_hall
                    if th_diff > 1:
                        cost += (th_diff * 3.0)
                        
                cost_matrix[i, j] = cost
                prob_matrix[i, j] = prob
                type_matrix[i, j] = a_type

        # 4. RESOLUÇÃO: O Algoritmo Húngaro (SciPy) cruza os dados e acha a Otimização Perfeita
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        for i, j in zip(row_ind, col_ind):
            atk_slot = attack_slots[i]
            def_slot = target_slots[j]
            attacker = atk_slot["member"]
            defender = def_slot["member"]
            prob = prob_matrix[i, j]
            a_type = type_matrix[i, j]

            justification = self._generate_intelligent_justification(attacker, defender, a_type, prob)

            rec = AttackRecommendation(
                member_name=attacker.name, member_th=attacker.town_hall, member_pos=attacker.map_position,
                attack_number=atk_slot["attack_number"], attack_type=a_type,
                recommended_target_pos=defender.map_position, recommended_target_th=defender.town_hall,
                justification=justification,
                confidence_score=prob
            )
            recommendations.append(rec)

        return recommendations

    def create_war_plan(self, war: Any, clan_tag: str, prediction_data: Dict) -> Dict[str, Any]:
        if not war or war.state not in ['inWar', 'preparation']:
            return {"success": False, "error": "A guerra não está ativa ou em preparação."}
        
        try:
            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan
            
            war_phase = self._determine_war_phase(war)
            
            # --- O NOVO CÉREBRO MATEMÁTICO É ACIONADO AQUI ---
            recommendations = self._generate_recommendations_via_matrix(war, our_clan, opponent, war_phase)
            
            phase_title = "Fase 2 - Arremate Otimizado (IA v6.0)" if war_phase == WarPhase.PHASE_2 else "Fase 1 - Vanguarda Otimizada (IA v6.0)"
            
            # Ordena por mapa para organizar a visualização
            recommendations.sort(key=lambda x: (x.member_pos, x.attack_number))
            
            if not recommendations:
                return { "success": True, "phase_title": "Análise Concluída", "recommendations": [], "warning": "Nenhum alvo encontrado. Mapa pode estar fechado." }

            avg_conf = sum(r.confidence_score for r in recommendations) / len(recommendations)
            rec_dict = [r.__dict__ | {'attack_type': r.attack_type.value} for r in recommendations]

            return {
                "success": True, "phase_title": phase_title, "recommendations": rec_dict,
                "prediction_summary": prediction_data.get("summary_panel", "Análise em andamento..."),
                "generated_at": datetime.datetime.now(pytz.utc).isoformat(),
                "statistics": {
                    "total_recommendations": len(rec_dict),
                    "average_confidence": avg_conf,
                    "attack_types": {t.value: sum(1 for r in rec_dict if r['attack_type'] == t.value) for t in AttackType}
                },
                "version": "Motor de Combinação Húngaro v6.0"
            }
        except Exception as e:
            self.logger.error(f"Erro ao gerar plano via Matriz: {e}", exc_info=True)
            return {"success": False, "error": f"Erro interno: {e}"}

class WarAdvisorCog(commands.Cog, name="Conselheiro de Guerra IA"):
    def __init__(self, bot):
        self.bot = bot
        self.war_advisor = WarAdvisorSystem()
        self.logger = logging.getLogger(f"{__name__}.WarAdvisorCog")

    @commands.command(name='plano')
    @commands.has_permissions(administrator=True)
    async def force_plan_generation(self, ctx):
        await ctx.send("🧠 **Matriz Húngara processando plano de guerra tático (v6.0)...**")
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            prediction = await self.bot.war_prediction_system.predict_war_outcome(war, self.bot.clan_tag)
            plan = self.war_advisor.create_war_plan(war, self.bot.clan_tag, prediction)

            if not plan.get("success"):
                return await ctx.send(f"❌ **Erro da IA:** {plan.get('error')}")
            
            embed = discord.Embed(
                title=f"🎯 {plan.get('phase_title')}", 
                description=f"**Módulo Tático de Matrizes** - Otimização global de ataques em andamento.",
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
            
            if plan.get("warning"): embed.add_field(name="⚠️ Situação Atípica", value=plan.get("warning"), inline=False)
            
            recommendations = plan.get("recommendations", [])
            current_player = None
            player_attacks = []
            
            for rec in recommendations[:25]:
                if current_player != rec['member_name']:
                    if current_player and player_attacks:
                        embed.add_field(name=f"👤 {current_player}", value="\n".join(player_attacks), inline=False)
                    current_player = rec['member_name']
                    player_attacks = []
                
                emoji = "🟢" if rec['confidence_score'] >= 0.8 else "🟡" if rec['confidence_score'] >= 0.65 else "🟠" if rec['confidence_score'] >= 0.4 else "🔴"
                type_emoji = {"mirror": "🪞", "dip": "⚡", "safe": "🛡️", "cleanup": "🧹", "bonus": "💰", "desperate": "🆘"}.get(rec['attack_type'], "⚔️")
                
                attack_info = (f"**Ataque {rec['attack_number']}:** {type_emoji} Alvo #{rec['recommended_target_pos']} "
                              f"(CV{rec['recommended_target_th']}) - Confiança: {emoji} {rec['confidence_score']:.0%}")
                player_attacks.append(attack_info)
            
            if current_player and player_attacks:
                embed.add_field(name=f"👤 {current_player}", value="\n".join(player_attacks), inline=False)
            
            if len(recommendations) > 25:
                embed.add_field(name="🌐 Terminal Web", value=f"Exibindo 25 primeiros ataques. Veja o painel Web para o briefing completo.", inline=False)
            
            embed.set_footer(text=f"Processado por {plan.get('version', 'IA v6.0')}")
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Erro na matriz do conselheiro: {e}", exc_info=True)
            await ctx.send("❌ **Falha catastrófica no núcleo do Conselheiro.**")

    @commands.command(name='analise')
    @commands.has_permissions(administrator=True)
    async def analyze_war_balance(self, ctx):
        await ctx.send("⚖️ **Iniciando cálculo matemático de poder bélico...**")
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state not in ['inWar', 'preparation']:
                return await ctx.send("❌ Nenhuma linha de frente ativa no momento.")
            
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            opp_clan = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
            
            our_strength = sum(self.war_advisor._calculate_player_strength(m) for m in our_clan.members)
            opp_strength = sum(self.war_advisor._calculate_player_strength(m) for m in opp_clan.members)
            advantage_percent = ((our_strength - opp_strength) / max(opp_strength, 1)) * 100
            
            if advantage_percent > 10: status_text, strategy, color = (f"🟢 **Dominância Estimada** (+{advantage_percent:.1f}%)", "Otimização focada em velocidade e DIP Tático seguro.", discord.Color.green())
            elif advantage_percent > 3: status_text, strategy, color = (f"🟡 **Vantagem Moderada** (+{advantage_percent:.1f}%)", "Otimização equilibrada. Foco na limpeza impecável da base.", discord.Color.gold())
            elif advantage_percent > -3: status_text, strategy, color = (f"🟡 **Guerra Espelhada** ({advantage_percent:+.1f}%)", "A Matriz buscará a distribuição perfeita para evitar falhas.", discord.Color.gold())
            else: status_text, strategy, color = (f"🔴 **Desvantagem Bélica** ({advantage_percent:.1f}%)", "O algoritmo priorizará maximização agressiva de estrelas.", discord.Color.red())

            embed = discord.Embed(title="⚖️ Relatório Bélico v6.0", color=color)
            embed.add_field(name="💪 Acúmulo Vetorial (Heróis + CV + Equipamentos)", value=f"**O Nosso Clã:** {our_strength:,}\n**Os Inimigos:** {opp_strength:,}\n**Situação:** {status_text}", inline=False)
            embed.add_field(name="🎯 Diretriz da Matriz", value=strategy, inline=False)
            
            if war.state == 'inWar':
                attackers_remaining = [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member]
                total_attacks_remaining = sum(war.attacks_per_member - len(m.attacks) for m in attackers_remaining)
                embed.add_field(name="⚔️ Fôlego de Batalha", value=f"**Membros com ataques na manga:** {len(attackers_remaining)}\n**Total de tiros restantes:** {total_attacks_remaining}", inline=False)
            
            embed.set_footer(text="Inteligência Vetorial v6.0")
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ **Falha ao ler os pesos de guerra:** {e}")

    @commands.command(name='debug_ataques')
    @commands.has_permissions(administrator=True)
    async def debug_remaining_attacks(self, ctx):
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state not in ['inWar', 'preparation']:
                return await ctx.send("❌ Nenhuma guerra em curso.")
            
            our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            embed = discord.Embed(title="🔍 Balanço de Cartuchos Restantes", description="Visão da equipe sobre os ataques pendentes:", color=discord.Color.orange())
            
            attackers_info, total_remaining = [], 0
            for member in sorted(our_clan.members, key=lambda x: x.map_position):
                attacks_remaining = war.attacks_per_member - len(member.attacks)
                total_remaining += attacks_remaining
                if attacks_remaining > 0:
                    strength = self.war_advisor._calculate_player_strength(member)
                    status = "🔴 LEVE" if strength < 1000 else "🟡 MÉDIO" if strength < 2000 else "🟢 PESADO"
                    attackers_info.append(f"**#{member.map_position} {member.name}** (CV{member.town_hall})\n└ Faltam: {attacks_remaining} | Escala: {status}")
            
            if attackers_info:
                for i in range(0, len(attackers_info), 10):
                    embed.add_field(name=f"👥 Lote {i+1}-{min(i+10, len(attackers_info))}", value="\n\n".join(attackers_info[i:i + 10]), inline=False)
            
            embed.add_field(name="📊 Somatória Geral", value=f"**Players Incompletos:** {len(attackers_info)}\n**Munição Total Restante:** {total_remaining}", inline=False)
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"❌ **Falha ao mapear cartuchos.**")

async def setup(bot: commands.Bot):
    await bot.add_cog(WarAdvisorCog(bot))
