# -*- coding: utf-8 -*-
import datetime
import discord
import pytz
from typing import Dict, Optional

def _calculate_post_war_stats(war_doc: Dict) -> Dict:
    """Calcula estatísticas detalhadas de uma guerra finalizada a partir do documento do DB."""
    our_member_tags = {m['tag'] for m in war_doc.get('our_clan_members_in_war', []) if 'tag' in m}
    all_attacks = war_doc.get('all_attacks', [])
    our_attacks = [a for a in all_attacks if a.get("attacker_tag") in our_member_tags]

    player_scores = {}
    if our_attacks:
        for attack in our_attacks:
            score = attack.get('stars', 0) * 1000 + attack.get('destruction', 0)
            
            th_diff = attack.get('defender_townhall', 0) - attack.get('attacker_townhall', 0)
            if th_diff > 0:
                score += th_diff * 200
            
            attacker_tag = attack.get('attacker_tag')
            if attacker_tag not in player_scores:
                player_scores[attacker_tag] = {"score": 0, "attacks": []}
            
            player_scores[attacker_tag]["score"] += score
            player_scores[attacker_tag]["attacks"].append(attack)

    sorted_players = sorted(player_scores.items(), key=lambda item: item[1]["score"], reverse=True)
    
    war_heroes = []
    for i, (player_tag, data) in enumerate(sorted_players[:3]):
        member_info = next((m for m in war_doc.get('our_clan_members_in_war', []) if m.get('tag') == player_tag), {})
        total_stars = sum(a.get('stars', 0) for a in data["attacks"])
        avg_destruction = sum(a.get('destruction', 0) for a in data["attacks"]) / len(data["attacks"]) if data["attacks"] else 0
        
        reason = f"{total_stars} estrelas e {avg_destruction:.1f}% de destruição média em {len(data['attacks'])} ataque(s)."
        if any(a.get('defender_townhall', 0) > a.get('attacker_townhall', 0) for a in data["attacks"]):
            reason += " Destaque por atacar CVs mais altos."

        war_heroes.append({
            "rank": i + 1,
            "name": member_info.get("name", "N/A"),
            "tag": player_tag,
            "town_hall": member_info.get("townhall", "?"),
            "reason": reason,
            "attacks": data["attacks"]
        })

    points_to_improve = []
    for th_level in range(10, 17):
        attacks_against_th = [a for a in our_attacks if a.get('defender_townhall') == th_level]
        if len(attacks_against_th) >= 3:
            avg_stars = sum(a.get('stars', 0) for a in attacks_against_th) / len(attacks_against_th)
            if avg_stars < 2.3:
                points_to_improve.append(f"Baixa média de estrelas ({avg_stars:.2f}⭐) contra CV{th_level}.")
    
    if not points_to_improve:
        points_to_improve.append("Bom desempenho geral, manter o foco!")

    return {
        "war_heroes": war_heroes,
        "points_to_improve": points_to_improve
    }

def create_post_war_analysis_embed(war_doc: Dict) -> Optional[discord.Embed]:
    """Gera o embed de análise pós-guerra a partir de um documento de guerra do banco de dados."""
    if not war_doc:
        return None

    try:
        war_data = war_doc.get("war_data", {})
        analysis = _calculate_post_war_stats(war_doc)
        
        war_heroes = analysis["war_heroes"]
        points_to_improve = analysis["points_to_improve"]

        clan_stars = war_data.get("clan_stars", 0)
        opponent_stars = war_data.get("opponent_stars", 0)

        result_color = discord.Color.green() if clan_stars > opponent_stars else discord.Color.red()
        result_text = "Vitória" if clan_stars > opponent_stars else "Derrota"
        
        if clan_stars == opponent_stars:
            clan_destruction = float(war_data.get("clan_destruction", "0%").replace('%',''))
            opponent_destruction = float(war_data.get("opponent_destruction", "0%").replace('%',''))
            if clan_destruction > opponent_destruction:
                result_text = "Vitória"
                result_color = discord.Color.green()
            elif opponent_destruction > clan_destruction:
                result_text = "Derrota"
                result_color = discord.Color.red()
            else:
                 result_text = "Empate"
                 result_color = discord.Color.gold()

        embed = discord.Embed(
            title=f"Análise Pós-Guerra: {result_text} vs {war_data.get('opponent_name')}",
            description=f"Placar final: **{clan_stars}⭐** vs {opponent_stars}⭐",
            color=result_color
        )

        if war_heroes:
            mvp = war_heroes[0]
            embed.add_field(
                name="🏆 MVP da Guerra",
                value=f"**{mvp.get('name')} (CV{mvp.get('town_hall')})**\n*_{mvp.get('reason')}_*",
                inline=False
            )
            
            jogadas_str = ""
            for hero in war_heroes:
                ataque_destaque = max(hero['attacks'], key=lambda a: a.get('stars', 0) * 1000 + a.get('destruction', 0))
                stars_str = "⭐" * ataque_destaque.get('stars', 0)
                jogadas_str += f"`{hero['rank']}.` **{hero.get('name')}** vs {ataque_destaque.get('defender_name')} - {stars_str} {ataque_destaque.get('destruction')}% \n"
            
            embed.add_field(
                name="⚔️ Heróis da Guerra",
                value=jogadas_str,
                inline=False
            )
        
        if points_to_improve:
            embed.add_field(
                name="🎯 Pontos a Melhorar",
                value="• " + "\n• ".join(points_to_improve),
                inline=False
            )
        
        if war_data.get('clan_badge_url'):
            embed.set_thumbnail(url=war_data.get('clan_badge_url'))

        return embed

    except Exception:
        return None
