# -*- coding: utf-8 -*-
"""
Módulo do Conselheiro de Guerra IA - ClashGenius (v2 - Integrado com War Predictor)
Este módulo agora consome a análise do war_predictor.py para gerar
recomendações de ataque dinâmicas e contextuais.
"""

import logging
from typing import Dict, List, Any
from discord.ext import commands

class WarAdvisorSystem:
    """
    Sistema que analisa a guerra atual e a predição da IA para gerar um plano de ataque tático.
    """
    def __init__(self):
        self.logger = logging.getLogger("war_advisor_v2")

    def _get_player_strength(self, player: Any) -> int:
        """Calcula uma pontuação de força simples para um jogador."""
        if not player:
            return 0
        return player.town_hall * 100

    def _generate_recommendations(self, war: Any, our_clan: Any, opponent: Any, prediction_data: Dict) -> List[Dict]:
        """Gera a lista de recomendações de ataque usando a predição da IA."""
        recommendations = []
        
        our_members_map = {m.tag: m for m in our_clan.members}
        opponent_map = {m.map_position: m for m in opponent.members}
        three_starred_targets = {a.defender_tag for a in war.attacks if a.stars == 3}

        # --- Análise de Contexto da IA ---
        features = prediction_data.get("analysis_log", {}).get("features", {})
        pressure_index = features.get("pressure_index", 0.0)
        momentum = features.get("momentum_indicator", 0.5)

        # --- FASE 2: FOCO EM LIMPEZA (CLEANUP) ---
        cleanup_targets = []
        for member in opponent.members:
            if member.tag in three_starred_targets or not member.defenses:
                continue
            
            best_defense = max(member.defenses, key=lambda d: d.stars)
            if 1 <= best_defense.stars < 3:
                cleanup_targets.append({
                    "position": member.map_position,
                    "stars": best_defense.stars,
                    "destruction": best_defense.destruction,
                })
        cleanup_targets.sort(key=lambda x: (-x['stars'], -x['destruction']))

        # --- GERAÇÃO DE RECOMENDAÇÕES PARA CADA MEMBRO ---
        for member in sorted(our_clan.members, key=lambda m: m.map_position):
            attacks_made = len(member.attacks)
            if attacks_made >= war.attacks_per_member:
                continue

            attack_number = attacks_made + 1
            rec = {
                "member_name": member.name, "member_th": member.town_hall,
                "member_pos": member.map_position, "attack_number": attack_number,
            }

            # Lógica para o segundo ataque (ou se a sinergia for alta): priorizar limpeza
            if (attack_number > 1 or features.get("clan_synergy_score", 0.5) > 0.6) and cleanup_targets:
                target = cleanup_targets.pop(0)
                rec.update({
                    "type": "cleanup",
                    "recommended_target_pos": target["position"],
                    "recommended_target_th": opponent_map.get(target["position"]).town_hall,
                    "justification": f"Limpeza no alvo #{target['position']} ({target['stars']}★ {target['destruction']}%). A 3ª estrela é crucial!"
                })
                recommendations.append(rec)
                continue

            # Lógica para o primeiro ataque baseada em força e contexto da IA
            mirror = opponent_map.get(member.map_position)
            if not mirror: continue

            our_strength = self._get_player_strength(member)
            mirror_strength = self._get_player_strength(mirror)

            # Se a pressão estiver alta, priorize ataques seguros
            if pressure_index > 0.6 and our_strength <= mirror_strength:
                 target_pos = member.map_position + 1
                 target = opponent_map.get(target_pos, mirror)
                 rec.update({
                    "type": "safe",
                    "recommended_target_pos": target.map_position,
                    "recommended_target_th": target.town_hall,
                    "justification": "Pressão alta! Garanta 3 estrelas num alvo mais seguro para não arriscar."
                 })
            # Se o momentum estiver a nosso favor, seja agressivo
            elif momentum > 0.6 and our_strength > mirror_strength:
                 target_pos = member.map_position - 1
                 target = opponent_map.get(target_pos, mirror)
                 rec.update({
                    "type": "dip",
                    "recommended_target_pos": target.map_position,
                    "recommended_target_th": target.town_hall,
                    "justification": "O momentum é nosso! Ataque um alvo forte para maximizar a vantagem."
                 })
            # Lógica Padrão (Dip / Safe / Mirror)
            elif our_strength > mirror_strength + 50:
                target_pos = member.map_position - 1
                target = opponent_map.get(target_pos, mirror)
                rec.update({
                    "type": "dip", "recommended_target_pos": target.map_position,
                    "recommended_target_th": target.town_hall,
                    "justification": "Você tem vantagem. Ataque um alvo mais forte para aliviar para o time."
                })
            elif our_strength < mirror_strength - 50:
                target_pos = member.map_position + 1
                target = opponent_map.get(target_pos, mirror)
                rec.update({
                    "type": "safe", "recommended_target_pos": target.map_position,
                    "recommended_target_th": target.town_hall,
                    "justification": "Seu espelho é forte. Garanta 3 estrelas num alvo mais acessível."
                })
            else:
                rec.update({
                    "type": "mirror", "recommended_target_pos": mirror.map_position,
                    "recommended_target_th": mirror.town_hall,
                    "justification": "Ataque seu espelho. O objetivo é garantir no mínimo 2 estrelas."
                })
            recommendations.append(rec)

        return recommendations

    def create_war_plan(self, war: Any, clan_tag: str, prediction_data: Dict) -> Dict[str, Any]:
        """Ponto de entrada principal para gerar o plano de guerra, agora recebendo a predição."""
        if not war or war.state != 'inWar':
            return {"error": "A guerra não está ativa."}

        try:
            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan

            recommendations = self._generate_recommendations(war, our_clan, opponent, prediction_data)
            recommendations.sort(key=lambda x: x['member_pos'])

            return {
                "clan_name": our_clan.name,
                "opponent_name": opponent.name,
                "recommendations": recommendations,
                "prediction_summary": prediction_data.get("summary_panel", "Análise em andamento.")
            }

        except Exception as e:
            self.logger.error(f"Erro ao gerar plano de guerra: {e}", exc_info=True)
            return {"error": "Ocorreu um erro interno ao gerar o plano de ataque."}


# Adicionado para que o bot possa carregar este arquivo como uma extensão (cog)
class WarAdvisorCog(commands.Cog, name="Conselheiro de Guerra IA"):
    def __init__(self, bot):
        self.bot = bot
        # A lógica principal está na classe WarAdvisorSystem, que é instanciada no bot.
        # Este cog serve principalmente para organização e carregamento.
        
async def setup(bot: commands.Bot):
    await bot.add_cog(WarAdvisorCog(bot))
