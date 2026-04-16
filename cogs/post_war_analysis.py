# -*- coding: utf-8 -*-
import datetime
import discord
import pytz
import logging
from typing import Dict, Optional, List

logger = logging.getLogger("post_war_analysis")

def _calculate_post_war_stats(war_doc: Dict) -> Dict:
    """Calcula estatísticas avançadas e gera premiações dinâmicas para o clã."""
    our_member_tags = {m['tag'] for m in war_doc.get('our_clan_members_in_war', []) if 'tag' in m}
    all_attacks = war_doc.get('all_attacks', [])
    
    # Filtra nossos ataques e tenta ordenar cronologicamente
    our_attacks = sorted(
        [a for a in all_attacks if a.get("attacker_tag") in our_member_tags], 
        key=lambda x: x.get("order", 9999)
    )

    player_scores = {}
    base_stars_tracker = {}
    cleanup_attempts = 0
    successful_cleanups = 0
    failed_dips = 0
    first_blood_tag = None

    for attack in our_attacks:
        if not all(k in attack for k in ['stars', 'destruction', 'defender_townhall', 'attacker_townhall', 'attacker_tag', 'defender_tag']):
            continue

        stars = attack.get('stars', 0)
        destruction = attack.get('destruction', 0)
        att_th = attack.get('attacker_townhall', 0)
        def_th = attack.get('defender_townhall', 0)
        att_tag = attack.get('attacker_tag')
        def_tag = attack.get('defender_tag')

        # 1. Pontuação Base
        score = stars * 1000 + destruction
        th_diff = def_th - att_th
        if th_diff > 0: score += th_diff * 300 # Bônus maior por atacar CV acima
        elif th_diff < 0: score -= abs(th_diff) * 150 # Penalidade leve por DIP

        if att_tag not in player_scores:
            player_scores[att_tag] = {"score": 0, "attacks": [], "name": attack.get("attacker_name", "Desconhecido"), "th": att_th}
        
        player_scores[att_tag]["score"] += score
        player_scores[att_tag]["attacks"].append(attack)

        # 2. Vanguarda (First Blood de PT)
        if stars == 3 and not first_blood_tag:
            first_blood_tag = att_tag

        # 3. Análise de Limpeza (Cleanups)
        prev_stars = base_stars_tracker.get(def_tag, 0)
        if 0 < prev_stars < 3:
            cleanup_attempts += 1
            if stars > prev_stars:
                successful_cleanups += 1
                player_scores[att_tag]["score"] += 500 # Bônus oculto por salvar a base
        base_stars_tracker[def_tag] = max(prev_stars, stars)

        # 4. Desperdício Bélico (Falha em DIP)
        if att_th > def_th and stars < 3:
            failed_dips += 1

    # ================= TOP 3: ATAQUES HEROICOS =================
    # Calcula o "Peso do Ataque" para encontrar as jogadas mais difíceis da guerra
    all_successful_attacks = [a for a in our_attacks if a.get('stars', 0) >= 2]
    
    def attack_epicness(a):
        base = a.get('stars', 0) * 1000 + a.get('destruction', 0)
        diff = a.get('defender_townhall', 0) - a.get('attacker_townhall', 0)
        return base + (diff * 800) # Peso gigantesco para quem ataca para cima
        
    top_attacks = sorted(all_successful_attacks, key=attack_epicness, reverse=True)[:3]

    # ================= PREMIAÇÕES DINÂMICAS =================
    awards = []
    
    sorted_players = sorted(player_scores.items(), key=lambda item: item[1]["score"], reverse=True)
    
    # O MVP
    if sorted_players:
        mvp_tag, mvp_data = sorted_players[0]
        awards.append({
            "title": "🏆 O General (MVP)",
            "player": f"{mvp_data['name']} (CV{mvp_data['th']})",
            "reason": f"Maior impacto balístico geral da guerra."
        })

    # O Matador de Gigantes
    giant_slayer = None
    max_diff = 0
    for attack in our_attacks:
        diff = attack.get('defender_townhall', 0) - attack.get('attacker_townhall', 0)
        if diff > max_diff and attack.get('stars', 0) >= 2:
            max_diff = diff
            giant_slayer = attack
            
    if giant_slayer and max_diff > 0:
        awards.append({
            "title": "🗡️ Matador de Gigantes",
            "player": f"{giant_slayer.get('attacker_name')} (CV{giant_slayer.get('attacker_townhall')})",
            "reason": f"Atacou um CV{giant_slayer.get('defender_townhall')} (+{max_diff} CVs) garantindo {giant_slayer.get('stars')}⭐."
        })

    # A Vanguarda
    if first_blood_tag and first_blood_tag in player_scores:
        vg_data = player_scores[first_blood_tag]
        if first_blood_tag != sorted_players[0][0]:
            awards.append({
                "title": "🚀 A Vanguarda",
                "player": f"{vg_data['name']} (CV{vg_data['th']})",
                "reason": "Abriu o mapa garantindo o primeiro PT da guerra."
            })

    # ================= INSIGHTS TÁTICOS =================
    tactical_insights = []
    
    if cleanup_attempts > 0:
        efficiency = (successful_cleanups / cleanup_attempts) * 100
        if efficiency >= 75:
            tactical_insights.append(f"🟢 **Sinergia de Limpeza:** Operamos com {efficiency:.0f}% de eficiência, corrigindo falhas sem desperdiçar cartuchos.")
        elif efficiency <= 40:
            tactical_insights.append(f"🔴 **Desperdício em Limpezas:** Apenas {efficiency:.0f}% das nossas limpezas renderam estrelas novas. Batemos muito na mesma parede.")
        else:
            tactical_insights.append(f"🟡 **Sinergia de Limpeza:** Mediana ({efficiency:.0f}%).")

    if failed_dips > 0:
        tactical_insights.append(f"⚠️ **Erro de Superioridade (DIP):** Tivemos {failed_dips} ataque(s) onde nosso CV era maior que o alvo e não garantimos o PT. Isso esvazia nossa vantagem matemática.")
    elif our_attacks:
        tactical_insights.append("✅ **Execução de Superioridade:** Excelente! Não tivemos falhas graves (DIPs) atacando Centros de Vila menores.")

    for th_level in range(10, 17):
        attacks_against_th = [a for a in our_attacks if a.get('defender_townhall') == th_level]
        if len(attacks_against_th) >= 3:
            avg_stars = sum(a.get('stars', 0) for a in attacks_against_th) / len(attacks_against_th)
            if avg_stars <= 1.8:
                tactical_insights.append(f"📉 **Bloqueio no CV{th_level}:** Nossa média de ataque contra eles foi péssima ({avg_stars:.1f}⭐). Precisamos rever as composições.")

    return {
        "awards": awards,
        "top_attacks": top_attacks,
        "tactical_insights": tactical_insights
    }

def create_post_war_analysis_embed(war_doc: Dict) -> Optional[discord.Embed]:
    """Gera o embed de análise pós-guerra a partir do documento."""
    if not war_doc:
        return None

    try:
        war_data = war_doc.get("war_data", {})
        analysis = _calculate_post_war_stats(war_doc)
        
        awards = analysis["awards"]
        top_attacks = analysis["top_attacks"]
        insights = analysis["tactical_insights"]

        clan_stars = war_data.get("clan_stars", 0)
        opponent_stars = war_data.get("opponent_stars", 0)

        result_color = discord.Color.green() if clan_stars > opponent_stars else discord.Color.red()
        result_text = "Vitória" if clan_stars > opponent_stars else "Derrota"
        
        if clan_stars == opponent_stars:
            clan_destruction = float(str(war_data.get("clan_destruction", "0")).replace('%',''))
            opponent_destruction = float(str(war_data.get("opponent_destruction", "0")).replace('%',''))
            if clan_destruction > opponent_destruction:
                result_text = "Vitória por Destruição"
                result_color = discord.Color.green()
            elif opponent_destruction > clan_destruction:
                result_text = "Derrota por Destruição"
                result_color = discord.Color.red()
            else:
                 result_text = "Empate Perfeito"
                 result_color = discord.Color.gold()

        embed = discord.Embed(
            title=f"📊 Veredito de Batalha: {result_text}",
            description=f"**Alvo:** {war_data.get('opponent_name')}\n**Placar:** {clan_stars}⭐ vs {opponent_stars}⭐",
            color=result_color
        )

        # Seção 1: Condecorações
        if awards:
            awards_text = ""
            for aw in awards:
                awards_text += f"{aw['title']}: **{aw['player']}**\n└ *{aw['reason']}*\n\n"
            embed.add_field(name="🏅 Condecorações de Honra", value=awards_text.strip(), inline=False)

        # Seção 2: Top 3 Ataques Heroicos
        if top_attacks:
            ataques_str = ""
            for i, atk in enumerate(top_attacks, 1):
                stars_str = "⭐" * atk.get('stars', 0)
                diff = atk.get('defender_townhall', 0) - atk.get('attacker_townhall', 0)
                
                if diff > 0: tipo = f"🔥 Desvantagem (+{diff} CV)"
                elif diff == 0: tipo = "🪞 Combate Justo"
                else: tipo = "⚡ Ataque Seguro"
                
                ataques_str += f"`{i}.` **{atk.get('attacker_name')}** (CV{atk.get('attacker_townhall')}) vs **{atk.get('defender_name')}** (CV{atk.get('defender_townhall')})\n└ {stars_str} {atk.get('destruction')}% - *{tipo}*\n"
            
            embed.add_field(name="⚔️ Top 3: Heróis da Batalha", value=ataques_str, inline=False)
        
        # Seção 3: Diagnóstico Tático
        if insights:
            insights_text = "\n\n".join(insights)
            embed.add_field(name="🧠 Parecer do Motor Matemático", value=insights_text, inline=False)
        else:
            embed.add_field(name="🧠 Parecer do Motor Matemático", value="A guerra seguiu padrões normais sem anomalias táticas graves.", inline=False)
        
        if war_data.get('clan_badge_url'):
            embed.set_thumbnail(url=war_data.get('clan_badge_url'))

        embed.set_footer(text="Inteligência Analítica v4.0 - ClashGenius")

        return embed

    except Exception as e:
        logger.error(f"Erro ao criar embed de análise pós-guerra: {e}", exc_info=True)
        return None
