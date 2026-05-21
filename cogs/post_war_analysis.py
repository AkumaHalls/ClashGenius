# -*- coding: utf-8 -*-
import datetime
import random
import discord
import pytz
import logging
from typing import Dict, Optional, List

logger = logging.getLogger("post_war_analysis")

def _calculate_post_war_stats(war_doc: Dict) -> Dict:
    """Calcula estatísticas avançadas e gera premiações dinâmicas para o clã."""
    our_member_tags = {m['tag'] for m in war_doc.get('our_clan_members_in_war', []) if 'tag' in m}
    all_attacks = war_doc.get('all_attacks', [])
    
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
    total_stars = 0
    total_attacks_count = 0

    for attack in our_attacks:
        if not all(k in attack for k in ['stars', 'destruction', 'defender_townhall', 'attacker_townhall', 'attacker_tag', 'defender_tag']):
            continue

        stars = attack.get('stars', 0)
        destruction = attack.get('destruction', 0)
        att_th = attack.get('attacker_townhall', 0)
        def_th = attack.get('defender_townhall', 0)
        att_tag = attack.get('attacker_tag')
        def_tag = attack.get('defender_tag')

        total_stars += stars
        total_attacks_count += 1

        score = stars * 1000 + destruction
        th_diff = def_th - att_th
        if th_diff > 0: score += th_diff * 300
        elif th_diff < 0: score -= abs(th_diff) * 150

        if att_tag not in player_scores:
            player_scores[att_tag] = {"score": 0, "attacks": [], "name": attack.get("attacker_name", "Desconhecido"), "th": att_th}
        
        player_scores[att_tag]["score"] += score
        player_scores[att_tag]["attacks"].append(attack)

        if stars == 3 and not first_blood_tag:
            first_blood_tag = att_tag

        prev_stars = base_stars_tracker.get(def_tag, 0)
        if 0 < prev_stars < 3:
            cleanup_attempts += 1
            if stars > prev_stars:
                successful_cleanups += 1
                player_scores[att_tag]["score"] += 500
        base_stars_tracker[def_tag] = max(prev_stars, stars)

        if att_th > def_th and stars < 3:
            failed_dips += 1

    all_successful_attacks = [a for a in our_attacks if a.get('stars', 0) >= 2]
    
    def attack_epicness(a):
        base = a.get('stars', 0) * 1000 + a.get('destruction', 0)
        diff = a.get('defender_townhall', 0) - a.get('attacker_townhall', 0)
        return base + (diff * 800)
        
    top_attacks = sorted(all_successful_attacks, key=attack_epicness, reverse=True)[:3]

    awards = []
    
    sorted_players = sorted(player_scores.items(), key=lambda item: item[1]["score"], reverse=True)
    
    if sorted_players:
        mvp_tag, mvp_data = sorted_players[0]
        mvp_reason_templates = [
            "Maior impacto balístico geral da guerra.",
            "Domínio absoluto no campo de batalha, liderando pelo exemplo.",
            "Performance de elite — o pilar ofensivo do clã nesta guerra.",
            "Eficiência cirúrgica: nenhum outro membro contribuiu tanto para o placar.",
        ]
        awards.append({
            "title": "🏆 O General (MVP)",
            "player": f"{mvp_data['name']} (CV{mvp_data['th']})",
            "reason": random.choice(mvp_reason_templates)
        })

    giant_slayer = None
    max_diff = 0
    for attack in our_attacks:
        diff = attack.get('defender_townhall', 0) - attack.get('attacker_townhall', 0)
        if diff > max_diff and attack.get('stars', 0) >= 2:
            max_diff = diff
            giant_slayer = attack
            
    if giant_slayer and max_diff > 0:
        gs_reason_templates = [
            f"Atacou um CV{giant_slayer.get('defender_townhall')} (+{max_diff} CVs) garantindo {giant_slayer.get('stars')}⭐.",
            f"Subiu de patamar e enfrentou um CV{giant_slayer.get('defender_townhall')} com coragem — {giant_slayer.get('stars')}⭐ de prêmio.",
            f"Venceu a diferença de {max_diff} CVs contra um CV{giant_slayer.get('defender_townhall')}, provando que tamanho não é documento.",
        ]
        awards.append({
            "title": "🗡️ Matador de Gigantes",
            "player": f"{giant_slayer.get('attacker_name')} (CV{giant_slayer.get('attacker_townhall')})",
            "reason": random.choice(gs_reason_templates)
        })

    if first_blood_tag and first_blood_tag in player_scores:
        vg_data = player_scores[first_blood_tag]
        if first_blood_tag != sorted_players[0][0]:
            vg_reason_templates = [
                "Abriu o mapa garantindo o primeiro PT da guerra.",
                "Quebrou o gelo com maestria — primeiro 3⭐ do confronto.",
                "Iniciou a ofensiva com o pé direito, destruindo a primeira base.",
            ]
            awards.append({
                "title": "🚀 A Vanguarda",
                "player": f"{vg_data['name']} (CV{vg_data['th']})",
                "reason": random.choice(vg_reason_templates)
            })

    tactical_insights = []
    recommendations = []

    team_size = war_doc.get('war_data', {}).get('team_size', 0)
    max_stars = team_size * 3 if team_size > 0 else 1
    clan_stars = war_doc.get('war_data', {}).get('clan_stars', 0)
    opponent_stars = war_doc.get('war_data', {}).get('opponent_stars', 0)

    star_efficiency = (total_stars / max_stars * 100) if max_stars > 0 else 0

    efficiency_templates_high = [
        f"🟢 **Eficiência de Estrelas:** {star_efficiency:.0f}% de aproveitamento — performance sólida e consistente.",
        f"🟢 **Aproveitamento Geral:** Convertemos {star_efficiency:.0f}% das estrelas possíveis. Um desempenho respeitável.",
        f"🟢 **Métrica Ofensiva:** {star_efficiency:.0f}% de estrelas conquistadas. O motor de guerra funcionou bem.",
    ]
    efficiency_templates_mid = [
        f"🟡 **Eficiência de Estrelas:** {star_efficiency:.0f}% de aproveitamento — há espaço claro para melhoria.",
        f"🟡 **Aproveitamento Geral:** Ficamos com {star_efficiency:.0f}% das estrelas. Precisamos afinar as composições.",
        f"🟡 **Métrica Ofensiva:** {star_efficiency:.0f}% de conversão. Algumas bases poderiam ter sido melhor exploradas.",
    ]
    efficiency_templates_low = [
        f"🔴 **Eficiência de Estrelas:** Apenas {star_efficiency:.0f}% de aproveitamento — muito abaixo do potencial do clã.",
        f"🔴 **Aproveitamento Geral:** {star_efficiency:.0f}% é um número preocupante. Precisamos revisar estratégias.",
        f"🔴 **Métrica Ofensiva:** {star_efficiency:.0f}% de estrelas conquistadas. O ataque precisa de reestruturação urgente.",
    ]

    if star_efficiency >= 80:
        tactical_insights.append(random.choice(efficiency_templates_high))
    elif star_efficiency >= 60:
        tactical_insights.append(random.choice(efficiency_templates_mid))
    else:
        tactical_insights.append(random.choice(efficiency_templates_low))

    if cleanup_attempts > 0:
        efficiency = (successful_cleanups / cleanup_attempts) * 100
        if efficiency >= 75:
            tactical_insights.append(f"🟢 **Sinergia de Limpeza:** Operamos com {efficiency:.0f}% de eficiência em limpezas, corrigindo falhas sem desperdiçar cartuchos.")
        elif efficiency <= 40:
            templates = [
                f"🔴 **Desperdício em Limpezas:** Apenas {efficiency:.0f}% das nossas limpezas renderam estrelas novas. Batemos muito na mesma parede.",
                f"🔴 **Retrabalho Bélico:** {efficiency:.0f}% de aproveitamento nas limpezas — vários ataques foram desperdiçados em bases já batidas.",
                f"🔴 **Falha de Finalização:** Das {cleanup_attempts} tentativas de limpeza, só {successful_cleanups} agregaram estrelas novas. Precisamos de mais coordenação.",
            ]
            tactical_insights.append(random.choice(templates))
        else:
            templates = [
                f"🟡 **Sinergia de Limpeza:** Mediana ({efficiency:.0f}%). Algumas bases precisaram de retrabalho, outras foram bem finalizadas.",
                f"🟡 **Limpezas:** {efficiency:.0f}% de taxa de sucesso em {cleanup_attempts} tentativas. Podemos melhorar a comunicação de desfechos.",
            ]
            tactical_insights.append(random.choice(templates))

    if failed_dips > 0:
        dip_templates = [
            f"⚠️ **Erro de Superioridade (DIP):** Tivemos {failed_dips} ataque(s) onde nosso CV era maior que o alvo e não garantimos o PT. Isso esvazia nossa vantagem matemática.",
            f"⚠️ **Falha Tática (DIP):** {failed_dips} ataque(s) desperdiçado(s) em bases inferiores sem garantir 3⭐. Cada erro desses custa estrelas preciosas.",
            f"⚠️ **Desperdício de Vantagem:** Em {failed_dips} ocasião(ões) atacamos de cima para baixo e não capitalizamos. Revisar composições para DIP é urgente.",
        ]
        tactical_insights.append(random.choice(dip_templates))
        
        rec_dip_templates = [
            f"📌 **Recomendação DIP:** Treinar ataques específicos para cenários de superioridade de CV. Composições como QC Hybrid ou Yeti Smash são boas opções.",
            f"📌 **Para melhorar:** Quando atacamos de CV superior, precisamos garantir o 3⭐. Vale a pena ensaiar ataques DIP em wars de treino.",
            f"📌 **Sugestão:** Mapear as bases mais fracas do oponente e designar atacantes com histórico de 3⭐ em DIP para esses alvos.",
        ]
        recommendations.append(random.choice(rec_dip_templates))
    elif our_attacks:
        dip_good_templates = [
            "✅ **Execução de Superioridade:** Excelente! Não tivemos falhas graves (DIPs) atacando Centros de Vila menores.",
            "✅ **Domínio Tático:** Todos os ataques com vantagem de CV resultaram em 3⭐. A disciplina tática está em dia.",
            "✅ **Zero DIPs:** Nenhum ataque de CV superior foi desperdiçado. Isso é marca de um clã bem treinado.",
        ]
        tactical_insights.append(random.choice(dip_good_templates))

    for th_level in range(10, 18):
        attacks_against_th = [a for a in our_attacks if a.get('defender_townhall') == th_level]
        if len(attacks_against_th) >= 3:
            avg_stars = sum(a.get('stars', 0) for a in attacks_against_th) / len(attacks_against_th)
            if avg_stars <= 1.8:
                block_templates = [
                    f"📉 **Bloqueio no CV{th_level}:** Nossa média de ataque contra eles foi péssima ({avg_stars:.1f}⭐). Precisamos rever as composições.",
                    f"📉 **Ponto Cego — CV{th_level}:** Tivemos dificuldade consistente contra bases desse nível. Média de {avg_stars:.1f}⭐ em {len(attacks_against_th)} ataques.",
                    f"📉 **Gargalo Tático:** CV{th_level} foi nosso calcanhar de Aquiles. Apenas {avg_stars:.1f}⭐ de média em {len(attacks_against_th)} tentativas.",
                ]
                tactical_insights.append(random.choice(block_templates))
                
                rec_block_templates = [
                    f"📌 **Recomendação CV{th_level}:** Estudar bases desse nível no mapa e designar atacantes com composições específicas para elas (ex: Zap Witch, QC Lalo).",
                    f"📌 **Para melhorar vs CV{th_level}:** Sugiro um treino focado em aberturas contra bases desse TH, especialmente ataques de 2⭐+ consistentes.",
                    f"📌 **Ação para CV{th_level}:** Revisar os replays dos ataques que falharam e identificar padrões — pode ser composição, rota de entrada ou feitiçaria.",
                ]
                recommendations.append(random.choice(rec_block_templates))

    our_th_levels = [m.get('townhall', 0) for m in war_doc.get('our_clan_members_in_war', [])]
    opp_th_levels = [m.get('townhall', 0) for m in war_doc.get('opponent_clan_members_in_war', [])]
    our_avg_th = sum(our_th_levels) / len(our_th_levels) if our_th_levels else 0
    opp_avg_th = sum(opp_th_levels) / len(opp_th_levels) if opp_th_levels else 0
    th_gap = our_avg_th - opp_avg_th

    if abs(th_gap) >= 0.5:
        if th_gap > 0:
            gap_templates = [
                f"📊 **Vantagem de CV:** Nosso clã tinha em média CV{our_avg_th:.1f} contra CV{opp_avg_th:.1f} do oponente (+{th_gap:.1f} CVs). Deveríamos ter capitalizado mais.",
                f"📊 **Superioridade TH:** Entramos com vantagem média de {th_gap:.1f} níveis de CV. Resultado poderia ter sido mais folgado.",
            ]
            tactical_insights.append(random.choice(gap_templates))
        else:
            gap_templates = [
                f"📊 **Desvantagem de CV:** Enfrentamos um oponente com média CV{opp_avg_th:.1f} contra nossos CV{our_avg_th:.1f} ({abs(th_gap):.1f} CVs abaixo). Guerreiro, não covarde.",
                f"📊 **Superados em CV:** O inimigo tinha {abs(th_gap):.1f} níveis de CV de média a mais. Cada estrela conquistada foi mérito.",
            ]
            tactical_insights.append(random.choice(gap_templates))

    star_diff = clan_stars - opponent_stars
    if star_diff > 5:
        char_templates = [
            "💬 **Caráter da Guerra:** Vitória dominante. Controlamos o ritmo do início ao fim.",
            "💬 **Observação Geral:** Foi uma guerra de mão única — nossa superioridade foi esmagadora.",
            "💬 **Panorama:** Não houve contestação real. Executamos o plano de guerra com maestria.",
        ]
        tactical_insights.append(random.choice(char_templates))
    elif star_diff > 0:
        char_templates = [
            "💬 **Caráter da Guerra:** Vitória suada. Cada estrela foi conquistada com mérito.",
            "💬 **Observação Geral:** Guerra equilibrada, decidida nos detalhes. Resiliência fez a diferença.",
            "💬 **Panorama:** Foi uma batalha de tirar o fôlego. Nosso planejamento tático prevaleceu por pouco.",
        ]
        tactical_insights.append(random.choice(char_templates))
    elif star_diff == 0:
        char_templates = [
            "💬 **Caráter da Guerra:** Empate técnico. Foi uma guerra equilibrada onde qualquer detalhe poderia ter virado.",
            "💬 **Observação Geral:** Guerra decidida nos centésimos — literalmente. Precisamos de mais agressividade nas finalizações.",
            "💬 **Panorama:** Tudo igual no placar. Demonstramos resiliência, mas faltou algo a mais para virar.",
        ]
        tactical_insights.append(random.choice(char_templates))
    else:
        if abs(star_diff) <= 3:
            char_templates = [
                f"💬 **Caráter da Guerra:** Derrota apertada por {abs(star_diff)}⭐. Estivemos muito perto da vitória.",
                f"💬 **Observação Geral:** Perdemos por pouco. Com ajustes finos, o resultado poderia ter sido diferente.",
                f"💬 **Panorama:** Batalha muito equilibrada. O placar de {abs(star_diff)}⭐ de diferença não reflete o esforço.",
            ]
        else:
            char_templates = [
                f"💬 **Caráter da Guerra:** Derrota expressiva por {abs(star_diff)}⭐. Precisamos reavaliar nossa abordagem.",
                f"💬 **Observação Geral:** O placar final mostra que fomos superados em vários aspectos. Hora de reestruturar.",
                f"💬 **Panorama:** Guerra difícil onde o abismo de estrelas ficou claro. Precisamos evoluir coletivamente.",
            ]
        tactical_insights.append(random.choice(char_templates))

    if cleanup_attempts > 0 and efficiency <= 40:
        if not any("coorden" in r for r in recommendations):
            rec_clean_templates = [
                "📌 **Recomendação Geral:** Melhorar a comunicação de desfechos no Discord. Designar um coordenador para organizar limpezas.",
                "📌 **Sugestão de Guerra:** Criar um canal de texto temporário durante a guerra para coordenar finalizações em tempo real.",
                "📌 **Para evoluir:** Limpezas mal-sucedidas custam estrelas. Que tal um sistema de call de bases no chat?",
            ]
            recommendations.append(random.choice(rec_clean_templates))

    if total_attacks_count > 0 and total_stars / total_attacks_count < 1.5:
        if not any("composi" in r for r in recommendations):
            rec_composition_templates = [
                "📌 **Recomendação de Composições:** Média de estrelas baixa sugere que as composições não estão adequadas às bases. Revisar o planejamento de ataques.",
                "📌 **Sugestão Tática:** Investir em treinos de QC Lalo e Yeti Smash — são composições versáteis que funcionam bem na maioria dos THs atuais.",
                "📌 **Para melhorar:** Considerar ataques de espelho (mirror) onde cada um estuda a base do seu oponente direto com antecedência.",
            ]
            recommendations.append(random.choice(rec_composition_templates))

    if star_diff < 0 and abs(th_gap) < 0.5:
        if not any("estudo" in r for r in recommendations):
            rec_prep_templates = [
                "📌 **Recomendação Pré-Guerra:** Com THs equivalentes, a derrota indica falha de preparação. Sugiro estudos de base em grupo antes da guerra.",
                "📌 **Ação:** Marcar um 'film study' antes da próxima guerra — todos analisam as bases do oponente e propõem ataques.",
                "📌 **Estratégia:** Pré-mapear os ataques da primeira leva com base no espelho. Planejamento é meio caminho andado.",
            ]
            recommendations.append(random.choice(rec_prep_templates))

    grade_templates_s = [
        "🎯 **Nota de Performance:** S — Desempenho lendário. Poucos clãs operam neste nível.",
        "🎯 **Rating Final:** S — Excelência absoluta. Este é o padrão ouro de guerra.",
        "🎯 **Classificação:** S — Perfeição tática. Um exemplo de execução de guerra.",
    ]
    grade_templates_a = [
        "🎯 **Nota de Performance:** A — Desempenho muito bom. Pequenos ajustes levariam ao topo.",
        "🎯 **Rating Final:** A — Sólido. Consistência é o caminho para a excelência.",
        "🎯 **Classificação:** A — Acima da média. Quase lá — mais alguns ajustes e chegamos ao S.",
    ]
    grade_templates_b = [
        "🎯 **Nota de Performance:** B — Desempenho mediano. Há espaço claro para evolução.",
        "🎯 **Rating Final:** B — Cumprimos o básico, mas o extraordinário ainda está distante.",
        "🎯 **Classificação:** B — Precisa melhorar. Vamos trabalhar os pontos fracos identificados.",
    ]
    grade_templates_c = [
        "🎯 **Nota de Performance:** C — Abaixo do esperado. Precisamos revisar nossa estratégia de guerra.",
        "🎯 **Rating Final:** C — Resultado insatisfatório. É hora de uma reavaliação séria dos nossos métodos.",
        "🎯 **Classificação:** C — Desempenho fraco. Muito trabalho pela frente para recuperar o nível.",
    ]
    grade_templates_d = [
        "🎯 **Nota de Performance:** D — Performance crítica. Precisamos de uma reformulação tática urgente.",
        "🎯 **Rating Final:** D — Muito abaixo do potencial do clã. Reunião de guerra necessária.",
        "🎯 **Classificação:** D — Resultado preocupante. Cada membro precisa reavaliar sua contribuição.",
    ]

    if star_efficiency >= 90:
        grade = random.choice(grade_templates_s)
    elif star_efficiency >= 75:
        grade = random.choice(grade_templates_a)
    elif star_efficiency >= 60:
        grade = random.choice(grade_templates_b)
    elif star_efficiency >= 45:
        grade = random.choice(grade_templates_c)
    else:
        grade = random.choice(grade_templates_d)

    tactical_insights.append(grade)

    return {
        "awards": awards,
        "top_attacks": top_attacks,
        "tactical_insights": tactical_insights,
        "recommendations": recommendations,
        "star_efficiency": star_efficiency,
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
        recommendations = analysis["recommendations"]

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

        if awards:
            awards_text = ""
            for aw in awards:
                awards_text += f"{aw['title']}: **{aw['player']}**\n└ *{aw['reason']}*\n\n"
            embed.add_field(name="🏅 Condecorações de Honra", value=awards_text.strip(), inline=False)

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
        
        all_insights = []
        if insights:
            all_insights.extend(insights)
        else:
            neutral_templates = [
                "A guerra seguiu padrões normais sem anomalias táticas graves.",
                "Desempenho dentro da média esperada para o nível do clã.",
                "Batalha convencional sem grandes desvios do planejado.",
            ]
            all_insights.append(random.choice(neutral_templates))

        if recommendations:
            sep_templates = [
                "\n━━━━━━━━━━━━━━━\n📋 **Recomendações e Pontos a Melhorar:**",
                "\n━━━━━━━━━━━━━━━\n🔧 **Áreas de Desenvolvimento:**",
                "\n━━━━━━━━━━━━━━━\n📌 **O que podemos fazer melhor:**",
            ]
            all_insights.append(random.choice(sep_templates))
            all_insights.extend(recommendations)

        if all_insights:
            insights_text = "\n\n".join(all_insights)
            embed.add_field(name="🧠 Parecer do Motor Matemático", value=insights_text, inline=False)
        
        if war_data.get('clan_badge_url'):
            embed.set_thumbnail(url=war_data.get('clan_badge_url'))

        footer_templates = [
            "Inteligência Analítica v5.0 - ClashGenius",
            "🧠 Motor de Análise Tática v5.0 - ClashGenius",
            "📊 Sistema de Veredito Inteligente v5.0 - ClashGenius",
            "⚙️ Analisador de Desempenho Bélico v5.0 - ClashGenius",
        ]
        embed.set_footer(text=random.choice(footer_templates))

        return embed

    except Exception as e:
        logger.error(f"Erro ao criar embed de análise pós-guerra: {e}", exc_info=True)
        return None
