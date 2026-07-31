# -*- coding: utf-8 -*-
import datetime
import random
import discord
import pytz
import logging
from typing import Dict, Optional, List, Tuple

import geniuslib as coc

logger = logging.getLogger("post_war_analysis")

MAX_FIELD_VALUE = 1024
MAX_EMBED_FIELDS = 25
MAX_EMBED_TOTAL = 5900


def _chunk_text(text: str, limit: int = MAX_FIELD_VALUE) -> List[str]:
    """Divide um texto longo em pedaços de até `limit` caracteres, quebrando em quebras de linha."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    chunks = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        chunks.append(text)
    return chunks


def _fields_size(embed: discord.Embed) -> int:
    return sum(len(f.name) + len(f.value) for f in embed.fields)


def _build_analysis_embeds(title: str, description: str, color, footer: str, thumbnail: Optional[str], fields: List[Tuple[str, str, bool]]) -> List[discord.Embed]:
    """Monta uma lista de embeds a partir de campos, respeitando os limites do Discord
    (1024 chars por campo, 25 campos por embed, ~6000 chars por embed)."""
    overhead = len(title) + len(description) + len(footer) + 40
    embeds: List[discord.Embed] = []
    current: Optional[discord.Embed] = None

    for name, value, inline in fields:
        for chunk in _chunk_text(value):
            if current is None or len(current.fields) >= MAX_EMBED_FIELDS:
                current = discord.Embed(title=title, description=description, color=color)
                embeds.append(current)
            elif _fields_size(current) + overhead + len(chunk) + len(name) > MAX_EMBED_TOTAL:
                current = discord.Embed(title=title, description=description, color=color)
                embeds.append(current)
            current.add_field(name=name, value=chunk, inline=inline)

    if not embeds:
        embeds.append(discord.Embed(title=title, description=description, color=color))

    if thumbnail:
        embeds[0].set_thumbnail(url=thumbnail)
    for e in embeds:
        e.set_footer(text=footer)
    return embeds


def _format_attack_line(atk: Dict, index: int = None) -> str:
    prefix = f"`{index}.` " if index else ""
    stars_str = "⭐" * atk.get('stars', 0)
    diff = atk.get('defender_townhall', 0) - atk.get('attacker_townhall', 0)
    if diff > 0:
        tipo = f"🔥 Desvantagem (+{diff} CV)"
    elif diff == 0:
        tipo = "🪞 Combate Justo"
    else:
        tipo = "⚡ Ataque Seguro"
    return (f"{prefix}**{atk.get('attacker_name')}** (CV{atk.get('attacker_townhall')}) vs "
            f"**{atk.get('defender_name')}** (CV{atk.get('defender_townhall')})\n"
            f"└ {stars_str} {atk.get('destruction')}% - *{tipo}*")


def _format_bad_attack_line(atk: Dict, index: int = None) -> str:
    prefix = f"`{index}.` " if index else ""
    stars_str = "⭐" * atk.get('stars', 0)
    diff = atk.get('defender_townhall', 0) - atk.get('attacker_townhall', 0)
    context = ""
    if atk.get('stars', 0) == 0:
        context = "— 💀 nenhuma estrela"
    elif diff > 0:
        context = f"— ⚠️ tinha vantagem de {diff} CV(s)"
    return (f"{prefix}**{atk.get('attacker_name')}** (CV{atk.get('attacker_townhall')}) vs "
            f"**{atk.get('defender_name')}** (CV{atk.get('defender_townhall')}) "
            f"→ {stars_str} {atk.get('destruction')}% {context}")


def _format_best_player(p: Dict) -> str:
    return (f"**{p['name']}** (CV{p['th']}) — {p['total_stars']}⭐ em {p['attacks']} ataque(s), "
            f"{p['triples']}x 3⭐, média {p['avg_stars']:.1f}⭐/ataque")


def _format_worst_player(p: Dict) -> str:
    return (f"**{p['name']}** (CV{p['th']}) — média {p['avg_stars']:.1f}⭐ em {p['attacks']} ataque(s). "
            f"{', '.join(p['reasons'])}.")


def _format_missed_attack(m: Dict) -> str:
    return f"**{m['name']}** (CV{m['th']}) — {m['missing']} ataque(s) não realizado(s)"


def _format_defense_hero(d: Dict) -> str:
    return (f"**{d['name']}** (CV{d['th']}) — segurou {d['held']} de {d['defenses']} defesa(s) com até 1⭐ "
            f"(cedeu {d['stars_given']}⭐ no total)")


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
    failed_dip_attacks = []
    zero_star_attacks = []
    failed_cleanups = []
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

        if stars == 0:
            zero_star_attacks.append(attack)

        if att_th > def_th and stars < 3:
            failed_dips += 1
            failed_dip_attacks.append(attack)

        prev_stars = base_stars_tracker.get(def_tag, 0)
        if 0 < prev_stars < 3:
            cleanup_attempts += 1
            new_stars_gained = max(0, stars - prev_stars)
            if new_stars_gained > 0:
                successful_cleanups += 1
                player_scores[att_tag]["score"] += 500
            else:
                failed_cleanups.append(attack)
        base_stars_tracker[def_tag] = max(prev_stars, stars)

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

    # ---- Ranking individual nomeado ----
    best_players = []
    for tag, data in sorted_players[:5]:
        attacks = data["attacks"]
        total = sum(a.get('stars', 0) for a in attacks)
        triples = sum(1 for a in attacks if a.get('stars', 0) == 3)
        best_players.append({
            "name": data["name"],
            "th": data["th"],
            "attacks": len(attacks),
            "total_stars": total,
            "triples": triples,
            "avg_stars": total / len(attacks) if attacks else 0.0,
        })

    worst_players = []
    for tag, data in player_scores.items():
        attacks = data["attacks"]
        if not attacks:
            continue
        total = sum(a.get('stars', 0) for a in attacks)
        avg_stars = total / len(attacks)
        reasons = []
        if any(a.get('attacker_townhall', 0) > a.get('defender_townhall', 0) and a.get('stars', 0) < 3 for a in attacks):
            reasons.append("falhou em DIP (CV superior sem 3⭐)")
        if any(a.get('stars', 0) == 0 for a in attacks):
            reasons.append("teve ataque(s) de 0⭐")
        if avg_stars < 1.5:
            reasons.append(f"média baixa de {avg_stars:.1f}⭐/ataque")
        if reasons:
            worst_players.append({
                "name": data["name"],
                "th": data["th"],
                "attacks": len(attacks),
                "total_stars": total,
                "avg_stars": avg_stars,
                "reasons": reasons,
            })
    worst_players.sort(key=lambda p: (p["avg_stars"], -p["attacks"]))
    worst_players = worst_players[:5]

    apm = war_doc.get('war_data', {}).get('attacks_per_member', 2)
    missed_attacks = []
    for m in war_doc.get('our_clan_members_in_war', []):
        attacks_used = len(m.get('attacks_made', []))
        missing = max(0, apm - attacks_used)
        if missing > 0:
            missed_attacks.append({"name": m.get('name', '?'), "th": m.get('townhall', 0), "missing": missing})
    missed_attacks.sort(key=lambda x: -x['missing'])

    defense_heroes = []
    for m in war_doc.get('our_clan_members_in_war', []):
        defenses = m.get('defenses_received', [])
        if not defenses:
            continue
        held = [d for d in defenses if d.get('stars', 3) <= 1]
        if not held:
            continue
        stars_given = sum(d.get('stars', 0) for d in defenses)
        defense_heroes.append({
            "name": m.get('name', '?'),
            "th": m.get('townhall', 0),
            "defenses": len(defenses),
            "held": len(held),
            "stars_given": stars_given,
        })
    defense_heroes.sort(key=lambda x: (-x['held'], x['stars_given']))
    defense_heroes = defense_heroes[:3]

    # ---- Análise tática e recomendações ----
    tactical_insights = []
    recommendations = []

    team_size = war_doc.get('war_data', {}).get('team_size', 0)
    max_stars = team_size * 3 if team_size > 0 else 1
    clan_stars = war_doc.get('war_data', {}).get('clan_stars', 0)
    opponent_stars = war_doc.get('war_data', {}).get('opponent_stars', 0)

    star_efficiency = (clan_stars / max_stars * 100) if max_stars > 0 else 0

    star_dist = war_doc.get('war_data', {}).get('clan_star_distribution', {})
    if star_dist:
        d0 = star_dist.get(0, 0)
        d1 = star_dist.get(1, 0)
        d2 = star_dist.get(2, 0)
        d3 = star_dist.get(3, 0)
        tactical_insights.append(f"📈 **Distribuição de Estrelas:** {d3}x ⭐⭐⭐ | {d2}x ⭐⭐ | {d1}x ⭐ | {d0}x zerados")

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

    if best_players and best_players[0]['total_stars'] >= 4:
        praise_templates = [
            f"🔥 **Ponta de Lança:** **{best_players[0]['name']}** (CV{best_players[0]['th']}) foi o motor ofensivo com {best_players[0]['total_stars']}⭐ em {best_players[0]['attacks']} ataque(s) ({best_players[0]['triples']}x 3⭐).",
            f"🔥 **Destaque Individual:** **{best_players[0]['name']}** liderou em estrelas com {best_players[0]['total_stars']}⭐ — referência de execução nesta guerra.",
        ]
        tactical_insights.append(random.choice(praise_templates))

    if cleanup_attempts > 0:
        efficiency = (successful_cleanups / cleanup_attempts) * 100
        if efficiency >= 75:
            tactical_insights.append(f"🟢 **Sinergia de Limpeza:** Operamos com {efficiency:.0f}% de eficiência em limpezas, corrigindo falhas sem desperdiçar cartuchos.")
        elif efficiency <= 40:
            clean_names = ", ".join(f"**{a.get('attacker_name', '?')}**" for a in failed_cleanups[:5])
            clean_suffix = " e outros." if len(failed_cleanups) > 5 else "."
            templates = [
                f"🔴 **Desperdício em Limpezas:** Apenas {efficiency:.0f}% das nossas limpezas renderam estrelas novas. {clean_names}{clean_suffix} bateram em bases já danificadas sem fechar o serviço.",
                f"🔴 **Retrabalho Bélico:** {efficiency:.0f}% de aproveitamento nas limpezas — {clean_names}{clean_suffix} desperdiçou(aram) ataques em bases já batidas.",
                f"🔴 **Falha de Finalização:** Das {cleanup_attempts} tentativas de limpeza, só {successful_cleanups} agregaram estrelas novas ({clean_names}{clean_suffix}). Precisamos de mais coordenação.",
            ]
            tactical_insights.append(random.choice(templates))
        else:
            templates = [
                f"🟡 **Sinergia de Limpeza:** Mediana ({efficiency:.0f}%). Algumas bases precisaram de retrabalho, outras foram bem finalizadas.",
                f"🟡 **Limpezas:** {efficiency:.0f}% de taxa de sucesso em {cleanup_attempts} tentativas. Podemos melhorar a comunicação de desfechos.",
            ]
            tactical_insights.append(random.choice(templates))

    if failed_dips > 0:
        dip_names = ", ".join(f"**{a.get('attacker_name', '?')}**" for a in failed_dip_attacks[:5])
        dip_suffix = " e outros." if len(failed_dip_attacks) > 5 else "."
        dip_templates = [
            f"⚠️ **Erro de Superioridade (DIP):** {failed_dips} ataque(s) onde nosso CV era maior que o alvo e não garantimos o PT — {dip_names}{dip_suffix} Isso esvazia nossa vantagem matemática.",
            f"⚠️ **Falha Tática (DIP):** {failed_dips} ataque(s) desperdiçado(s) em bases inferiores sem garantir 3⭐ ({dip_names}{dip_suffix}). Cada erro desses custa estrelas preciosas.",
            f"⚠️ **Desperdício de Vantagem:** {failed_dips} ataque(s) de cima para baixo sem capitalização ({dip_names}{dip_suffix}). Revisar composições para DIP é urgente.",
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

    if zero_star_attacks:
        zero_names = ", ".join(f"**{a.get('attacker_name', '?')}**" for a in zero_star_attacks[:6])
        zero_suffix = " e outros." if len(zero_star_attacks) > 6 else "."
        zero_templates = [
            f"💀 **Ataques Zerados:** {len(zero_star_attacks)} ataque(s) terminaram sem estrela alguma — {zero_names}{zero_suffix} Cada 0⭐ é estrela entregue ao adversário.",
            f"💀 **Sangria de Estrelas:** Tivemos {len(zero_star_attacks)} ataque(s) de 0⭐ ({zero_names}{zero_suffix}). Esses ataques pesaram diretamente no placar.",
        ]
        tactical_insights.append(random.choice(zero_templates))

    if missed_attacks:
        missed_names = ", ".join(f"**{m['name']}**" for m in missed_attacks[:5])
        missed_suffix = " e outros." if len(missed_attacks) > 5 else "."
        miss_templates = [
            f"🚩 **Cartuchos Queimados:** {len(missed_attacks)} jogador(es) não usaram todos os ataques ({missed_names}{missed_suffix}). Ataques perdidos não se recuperam.",
            f"🚩 **Ataques no Bolso:** {sum(m['missing'] for m in missed_attacks)} ataque(s) ficaram sem uso ({missed_names}{missed_suffix}). Cada ataque não usado é estrela desperdiçada.",
        ]
        tactical_insights.append(random.choice(miss_templates))
        if not any("não us" in r for r in recommendations):
            rec_missed_templates = [
                f"📌 **Recomendação Presença:** {', '.join(m['name'] for m in missed_attacks[:4])} precisa(m) garantir presença e executar todos os ataques na próxima guerra.",
                f"📌 **Ação para o próximo war:** Reforçar com {', '.join(m['name'] for m in missed_attacks[:4])} a importância de usar todos os ataques — cada falta custa caro ao placar.",
            ]
            recommendations.append(random.choice(rec_missed_templates))

    for th_level in range(10, 20):
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
        "best_players": best_players,
        "worst_players": worst_players,
        "missed_attacks": missed_attacks,
        "failed_dip_attacks": failed_dip_attacks,
        "zero_star_attacks": zero_star_attacks,
        "defense_heroes": defense_heroes,
        "tactical_insights": tactical_insights,
        "recommendations": recommendations,
        "star_efficiency": star_efficiency,
    }


def analyze_war(war_doc: Dict) -> Dict:
    """Análise pública de guerra — retorna awards, top_attacks, insights."""
    return _calculate_post_war_stats(war_doc)


def create_post_war_analysis_embed(war_doc: Dict) -> Optional[List[discord.Embed]]:
    """Gera os embeds de análise pós-guerra a partir do documento.
    A mensagem é dividida em múltiplos embeds automaticamente caso ultrapasse os limites do Discord."""
    if not war_doc:
        return None

    try:
        war_data = war_doc.get("war_data", {})
        analysis = _calculate_post_war_stats(war_doc)

        awards = analysis["awards"]
        top_attacks = analysis["top_attacks"]
        best_players = analysis["best_players"]
        worst_players = analysis["worst_players"]
        missed_attacks = analysis["missed_attacks"]
        zero_star_attacks = analysis["zero_star_attacks"]
        defense_heroes = analysis["defense_heroes"]
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

        title = f"📊 Veredito de Batalha: {result_text}"
        description = f"**Alvo:** {war_data.get('opponent_name')}\n**Placar:** {clan_stars}⭐ vs {opponent_stars}⭐"
        if clan_stars == opponent_stars:
            description += f"\n**Destruição:** {war_data.get('clan_destruction')} vs {war_data.get('opponent_destruction')}"
        team_size = war_data.get('team_size')
        if team_size:
            description += f"\n**Guerra:** {team_size}v{team_size}"
        description += f"\n**Eficiência:** {analysis['star_efficiency']:.0f}%"

        fields = []

        if awards:
            awards_text = ""
            for aw in awards:
                awards_text += f"{aw['title']}: **{aw['player']}**\n└ *{aw['reason']}*\n\n"
            fields.append(("🏅 Condecorações de Honra", awards_text.strip(), False))

        if top_attacks:
            ataques_str = "\n".join(_format_attack_line(atk, i) for i, atk in enumerate(top_attacks, 1))
            fields.append(("⚔️ Top 3: Heróis da Batalha", ataques_str, False))

        if best_players:
            best_str = "\n".join(_format_best_player(p) for p in best_players)
            fields.append(("🌟 Melhores Guerreiros (nomeados)", best_str, False))

        if defense_heroes:
            def_str = "\n".join(_format_defense_hero(d) for d in defense_heroes)
            fields.append(("🛡️ Muralha de Ferro — Defesas Sólidas", def_str, False))

        if worst_players:
            worst_str = "\n".join(_format_worst_player(p) for p in worst_players)
            fields.append(("📉 Alvos de Atenção (nomeados)", worst_str, False))

        if zero_star_attacks:
            zero_str = "\n".join(_format_bad_attack_line(a, i) for i, a in enumerate(zero_star_attacks[:8], 1))
            fields.append(("💀 Ataques de 0 Estrelas", zero_str, False))

        if missed_attacks:
            missed_str = "\n".join(_format_missed_attack(m) for m in missed_attacks)
            fields.append(("🚩 Ataques Não Realizados", missed_str, False))

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
            fields.append(("🧠 Parecer do Motor Matemático", "\n\n".join(all_insights), False))

        footer_templates = [
            "Inteligência Analítica v6.0 - ClashGenius",
            "🧠 Motor de Análise Tática v6.0 - ClashGenius",
            "📊 Sistema de Veredito Inteligente v6.0 - ClashGenius",
            "⚙️ Analisador de Desempenho Bélico v6.0 - ClashGenius",
        ]
        footer = random.choice(footer_templates)

        return _build_analysis_embeds(
            title=title,
            description=description,
            color=result_color,
            footer=footer,
            thumbnail=war_data.get('clan_badge_url'),
            fields=fields,
        )

    except Exception as e:
        logger.error(f"Erro ao criar embeds de análise pós-guerra: {e}", exc_info=True)
        return None
