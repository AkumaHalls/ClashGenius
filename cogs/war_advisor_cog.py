# -*- coding: utf-8 -*-
"""
Módulo do Conselheiro de Guerra IA - ClashGenius (v3 - Fases de Guerra e Alvos Únicos)
Este módulo agora consome a análise do war_predictor.py, gerencia fases de guerra
e garante que os alvos iniciais recomendados sejam únicos.
"""

import logging
from typing import Dict, List, Any
from discord.ext import commands
import datetime
import pytz

class WarAdvisorSystem:
    """
    Sistema que analisa a guerra atual e a predição da IA para gerar um plano de ataque tático.
    """
    def __init__(self):
        self.logger = logging.getLogger("war_advisor_v3")

    def _get_player_strength(self, player: Any) -> int:
        """Calcula uma pontuação de força simples para um jogador."""
        if not player:
            return 0
        # Aumenta o peso do CV para diferenciar melhor os níveis
        return player.town_hall * 100

    def _is_first_half_of_war(self, war: Any) -> bool:
        """Verifica se a guerra está na primeira metade (primeiras 12 horas)."""
        now = datetime.datetime.now(pytz.utc)
        war_start_time = war.start_time.time.replace(tzinfo=pytz.utc)
        twelve_hours_in = war_start_time + datetime.timedelta(hours=12)
        return now < twelve_hours_in

    def _generate_recommendations_phase1(self, our_clan: Any, opponent: Any) -> List[Dict]:
        """Gera recomendações para a primeira fase da guerra (ataques iniciais)."""
        recommendations = []
        opponent_map = {m.map_position: m for m in opponent.members}
        assigned_targets = set() # NOVO: Para garantir alvos únicos

        for member in sorted(our_clan.members, key=lambda m: m.map_position):
            if member.attacks: # Se o membro já atacou, não gera recomendação inicial
                continue

            rec = {
                "member_name": member.name, "member_th": member.town_hall,
                "member_pos": member.map_position, "attack_number": 1,
            }

            mirror = opponent_map.get(member.map_position)
            if not mirror: continue

            our_strength = self._get_player_strength(member)
            
            # Tenta encontrar o alvo ideal
            target = None
            
            # 1. Lógica de "Dip" (atacar mais fraco)
            if our_strength > self._get_player_strength(mirror) + 50:
                # Procura o alvo mais forte que ainda não foi designado e que seja mais fraco que nós
                possible_targets = [
                    m for m in opponent.members 
                    if m.map_position not in assigned_targets and self._get_player_strength(m) < our_strength
                ]
                if possible_targets:
                    target = max(possible_targets, key=lambda m: self._get_player_strength(m))
                    rec.update({
                        "type": "dip",
                        "justification": "Você tem vantagem. Ataque um alvo forte para aliviar para o time."
                    })

            # 2. Lógica de "Safe" (atacar mais fraco que o espelho)
            if not target and our_strength < self._get_player_strength(mirror) - 50:
                # Procura o alvo mais fraco disponível
                possible_targets = [m for m in opponent.members if m.map_position not in assigned_targets]
                if possible_targets:
                    target = min(possible_targets, key=lambda m: self._get_player_strength(m))
                    rec.update({
                        "type": "safe",
                        "justification": "Seu espelho é forte. Garanta 3 estrelas num alvo mais acessível."
                    })

            # 3. Lógica do Espelho (se nenhuma outra se aplicar)
            if not target:
                target = mirror
                rec.update({
                    "type": "mirror",
                    "justification": "Ataque seu espelho. O objetivo é garantir no mínimo 2 estrelas."
                })
            
            # Garante que, se o alvo ideal já estiver pego, pegue o mais próximo disponível
            while target and target.map_position in assigned_targets:
                next_pos = target.map_position + 1
                target = opponent_map.get(next_pos)
                if not target: # Se chegar no fim da lista, para.
                    break

            if target:
                assigned_targets.add(target.map_position)
                rec.update({
                    "recommended_target_pos": target.map_position,
                    "recommended_target_th": target.town_hall
                })
                recommendations.append(rec)

        return recommendations

    def _generate_recommendations_phase2(self, war: Any, our_clan: Any, opponent: Any) -> List[Dict]:
        """Gera recomendações para a segunda fase da guerra (limpeza)."""
        recommendations = []
        three_starred_tags = {a.defender_tag for a in war.attacks if a.stars == 3}
        
        # Identifica alvos prioritários para limpeza
        cleanup_targets = []
        for member in opponent.members:
            if member.tag in three_starred_tags or not member.defenses:
                continue
            
            best_defense = max(member.defenses, key=lambda d: d.stars)
            if 1 <= best_defense.stars < 3:
                cleanup_targets.append({
                    "position": member.map_position,
                    "stars": best_defense.stars,
                    "destruction": best_defense.destruction,
                    "tag": member.tag,
                    "th": member.town_hall
                })
        cleanup_targets.sort(key=lambda x: (x['stars'], -x['destruction'])) # Prioriza 1 estrela, depois maior destruição

        # Designa os melhores jogadores para os alvos de limpeza
        available_attackers = [
            m for m in our_clan.members if len(m.attacks) < war.attacks_per_member
        ]
        available_attackers.sort(key=lambda m: self._get_player_strength(m), reverse=True)

        for member in available_attackers:
            rec = {
                "member_name": member.name, "member_th": member.town_hall,
                "member_pos": member.map_position, "attack_number": len(member.attacks) + 1,
            }
            if cleanup_targets:
                target = cleanup_targets.pop(0) # Pega o alvo de maior prioridade
                rec.update({
                    "type": "cleanup",
                    "recommended_target_pos": target["position"],
                    "recommended_target_th": target["th"],
                    "justification": f"Limpeza no alvo #{target['position']} ({target['stars']}★ {target['destruction']}%). A 3ª estrela é crucial!"
                })
            else:
                # Se não houver alvos de limpeza, recomenda um ataque seguro
                mirror = opponent.get_member(map_position=member.map_position)
                rec.update({
                    "type": "safe",
                    "recommended_target_pos": member.map_position + 2,
                    "recommended_target_th": opponent.get_member(map_position=member.map_position+2).town_hall if opponent.get_member(map_position=member.map_position+2) else mirror.town_hall,
                    "justification": "Não há alvos para limpeza. Faça um ataque seguro para garantir 3 estrelas."
                })
            recommendations.append(rec)
            
        return recommendations


    def create_war_plan(self, war: Any, clan_tag: str, prediction_data: Dict) -> Dict[str, Any]:
        """Ponto de entrada principal para gerar o plano de guerra, agora com fases."""
        if not war or war.state not in ['inWar', 'preparation']:
            return {"error": "A guerra não está ativa ou em preparação."}

        try:
            our_clan = war.clan if war.clan.tag == clan_tag else war.opponent
            opponent = war.opponent if war.clan.tag == clan_tag else war.clan
            
            is_first_half = self._is_first_half_of_war(war) if war.state == 'inWar' else True
            
            if war.state == 'preparation' or is_first_half:
                phase = 1
                phase_title = "Fase 1: Alvos para o Primeiro Ataque"
                recommendations = self._generate_recommendations_phase1(our_clan, opponent)
            else:
                phase = 2
                phase_title = "Fase 2: Alvos para Limpeza e Ataques Estratégicos"
                recommendations = self._generate_recommendations_phase2(war, our_clan, opponent)
            
            recommendations.sort(key=lambda x: x['member_pos'])

            return {
                "clan_name": our_clan.name,
                "opponent_name": opponent.name,
                "phase": phase,
                "phase_title": phase_title,
                "recommendations": recommendations,
                "prediction_summary": prediction_data.get("summary_panel", "Análise em andamento.")
            }

        except Exception as e:
            self.logger.error(f"Erro ao gerar plano de guerra: {e}", exc_info=True)
            return {"error": "Ocorreu um erro interno ao gerar o plano de ataque."}


class WarAdvisorCog(commands.Cog, name="Conselheiro de Guerra IA"):
    def __init__(self, bot):
        self.bot = bot
        
async def setup(bot: commands.Bot):
    await bot.add_cog(WarAdvisorCog(bot))

