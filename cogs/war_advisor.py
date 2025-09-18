# -*- coding: utf-8 -*-
"""
Módulo do Conselheiro de Guerra IA - ClashGenius
Este módulo contém a lógica para gerar recomendações de ataque dinâmicas
para guerras normais, otimizando a distribuição de ataques para maximizar estrelas.
"""

import logging
from typing import Dict, List, Any, Optional

class WarAdvisorSystem:
    """
    Sistema que analisa a guerra atual e gera um plano de ataque tático
    para cada membro do clã.
    """
    def __init__(self):
        self.logger = logging.getLogger("war_advisor")

    def _get_player_strength(self, player: Any) -> int:
        """Calcula uma pontuação de força simples para um jogador (pode ser expandido)."""
        if not player:
            return 0
        # Um CV mais alto tem um peso muito maior.
        return player.town_hall * 100

    def _generate_recommendations(self, war: Any, our_clan: Any, opponent: Any) -> List[Dict]:
        """Gera a lista de recomendações de ataque."""
        recommendations = []
        
        # Cria mapas para fácil acesso aos membros e seus espelhos
        our_members_map = {m.tag: m for m in our_clan.members}
        opponent_map = {m.map_position: m for m in opponent.members}
        
        # Mapeia alvos que já sofreram 3 estrelas para não recomendar limpeza neles
        three_starred_targets = {a.defender_tag for a in war.attacks if a.stars == 3}

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
                    "attacker": war.get_member(best_defense.attacker_tag)
                })
        
        # Ordena os alvos de limpeza: mais fáceis (2 estrelas, alta destruição) primeiro
        cleanup_targets.sort(key=lambda x: (-x['stars'], -x['destruction']))

        # --- GERAÇÃO DE RECOMENDAÇÕES PARA CADA MEMBRO ---
        for member in sorted(our_clan.members, key=lambda m: m.map_position):
            attacks_made = len(member.attacks)
            if attacks_made >= war.attacks_per_member:
                continue # Já usou todos os ataques

            attack_number = attacks_made + 1
            rec = {
                "member_name": member.name,
                "member_th": member.town_hall,
                "member_pos": member.map_position,
                "attack_number": attack_number,
            }

            # Lógica para o segundo ataque (ou posteriores): priorizar limpeza
            if attack_number > 1 and cleanup_targets:
                target = cleanup_targets.pop(0) # Pega o alvo de limpeza mais prioritário
                rec.update({
                    "type": "cleanup",
                    "recommended_target_pos": target["position"],
                    "recommended_target_th": opponent_map.get(target["position"]).town_hall,
                    "justification": f"Limpeza no alvo #{target['position']} ({target['stars']}★ {target['destruction']}%). A 3ª estrela é crucial!"
                })
                recommendations.append(rec)
                continue

            # Lógica para o primeiro ataque (ou se não houver alvos de limpeza)
            mirror = opponent_map.get(member.map_position)
            if not mirror: continue

            our_strength = self._get_player_strength(member)
            mirror_strength = self._get_player_strength(mirror)

            # Ataque "Dip" (Membro forte vs espelho mais fraco)
            if our_strength > mirror_strength + 50: # Vantagem de CV
                target_pos = member.map_position - 1
                target = opponent_map.get(target_pos, mirror)
                rec.update({
                    "type": "dip",
                    "recommended_target_pos": target.map_position,
                    "recommended_target_th": target.town_hall,
                    "justification": "Você tem vantagem. Ataque um alvo mais forte para aliviar para o time."
                })
            # Ataque "Seguro" (Membro fraco vs espelho mais forte)
            elif our_strength < mirror_strength - 50:
                target_pos = member.map_position + 1
                target = opponent_map.get(target_pos, mirror)
                rec.update({
                    "type": "safe",
                    "recommended_target_pos": target.map_position,
                    "recommended_target_th": target.town_hall,
                    "justification": "Seu espelho é forte. Garanta 3 estrelas num alvo mais acessível."
                })
            # Ataque Padrão (Forças equilibradas)
            else:
                rec.update({
                    "type": "mirror",
                    "recommended_target_pos": mirror.map_position,
                    "recommended_target_th": mirror.town_hall,
                    "justification": "Ataque seu espelho. O objetivo é garantir no mínimo 2 estrelas."
                })
            recommendations.append(rec)

        return recommendations

    def create_war_plan(self, war: Any, clan_tag: str) -> Dict[str, Any]:
        """Ponto de entrada principal para gerar o plano de guerra."""
        if not war or war.state != 'inWar':
            return {"error": "A guerra não está ativa."}

        try:
            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan

            recommendations = self._generate_recommendations(war, our_clan, opponent)
            
            # Ordena por posição do membro para exibição no painel
            recommendations.sort(key=lambda x: x['member_pos'])

            return {
                "clan_name": our_clan.name,
                "opponent_name": opponent.name,
                "recommendations": recommendations
            }

        except Exception as e:
            self.logger.error(f"Erro ao gerar plano de guerra: {e}", exc_info=True)
            return {"error": "Ocorreu um erro interno ao gerar o plano de ataque."}
