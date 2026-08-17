# -*- coding: utf-8 -*-
"""
Análise tática de ataques de guerra em tempo real.

Gera um dicionário com motivos, destaques, sugestões e contexto para o
evento `on_war_attack`, explicando *por que* um ataque foi bom ou ruim
e como o jogador/clã pode melhorar.
"""

import logging
import time

logger = logging.getLogger("war_attack_analysis")

try:
    from geniuslib.war_analytics import new_stars
except Exception:
    new_stars = None

_HISTORY_CACHE = {}
_HISTORY_CACHE_MAXSIZE = 500
_HISTORY_CACHE_TTL = 3600
_HISTORY_CACHE_TIMESTAMPS = {}
_HISTORY_LIMIT = 10
_MAX_REASONS = 6
_MAX_SUGGESTIONS = 5
_MAX_HIGHLIGHTS = 5
_MAX_CONTEXT = 6


def _fmt_duration(seconds):
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    mins, secs = divmod(seconds, 60)
    return f"{mins}:{secs:02d}"


def _evict_history_cache():
    now = time.monotonic()
    expired = [k for k, t in _HISTORY_CACHE_TIMESTAMPS.items() if now - t > _HISTORY_CACHE_TTL]
    for k in expired:
        _HISTORY_CACHE.pop(k, None)
        _HISTORY_CACHE_TIMESTAMPS.pop(k, None)
    while len(_HISTORY_CACHE) > _HISTORY_CACHE_MAXSIZE:
        oldest_key = min(_HISTORY_CACHE_TIMESTAMPS, key=_HISTORY_CACHE_TIMESTAMPS.get)
        _HISTORY_CACHE.pop(oldest_key, None)
        _HISTORY_CACHE_TIMESTAMPS.pop(oldest_key, None)


async def _get_player_history(db, player_tag):
    if db is None:
        return None
    _evict_history_cache()
    cached = _HISTORY_CACHE.get(player_tag)
    if cached is not None:
        return cached
    try:
        cursor = (
            db.war_history.find({"our_clan_members_in_war.tag": player_tag})
            .sort("war_data.end_time_iso", -1)
            .limit(_HISTORY_LIMIT)
        )
        total_attacks = 0
        total_stars = 0
        total_destruction = 0.0
        three_stars = 0
        missed = 0
        wars = 0
        async for war_doc in cursor:
            wars += 1
            apm = int(war_doc.get("war_data", {}).get("attacks_per_member", 2) or 2)
            for member in war_doc.get("our_clan_members_in_war", []):
                if member.get("tag") != player_tag:
                    continue
                attacks = member.get("attacks_made", [])
                total_attacks += len(attacks)
                missed += max(0, apm - len(attacks))
                for atk in attacks:
                    total_stars += int(atk.get("stars", 0) or 0)
                    total_destruction += float(atk.get("destruction", 0) or 0)
                    if int(atk.get("stars", 0) or 0) == 3:
                        three_stars += 1
                break
        if total_attacks == 0:
            return None
        result = {
            "wars": wars,
            "attacks": total_attacks,
            "avg_stars": total_stars / total_attacks,
            "three_star_rate": (three_stars / total_attacks) * 100,
            "avg_destruction": total_destruction / total_attacks,
            "missed": missed,
        }
        _HISTORY_CACHE[player_tag] = result
        _HISTORY_CACHE_TIMESTAMPS[player_tag] = time.monotonic()
        return result
    except Exception as e:
        logger.debug(f"_get_player_history({player_tag}) falhou: {e}")
        return None


def _clan_avg_duration(war, our_clan=True):
    clan = war.clan if our_clan else war.opponent
    durations = [a.duration for a in clan.attacks if getattr(a, "duration", None)]
    if not durations:
        return None
    return sum(durations) / len(durations)


def _war_scoreboard(war):
    try:
        clan = war.clan
        opp = war.opponent
        if not clan or not opp:
            return None
        return f"🏁 Placar: **{clan.name}** {clan.stars}⭐ x {opp.stars}⭐ **{opp.name}**"
    except Exception:
        return None


async def analyze_war_attack(*, attack, war, attacker, defender, is_our_attack, bot):
    """Analisa um ataque de guerra e retorna um dicionário estruturado.

    Returns
    -------
    dict
        ``side``: ``"attack"`` ou ``"defense"``
        ``is_bad``: bool
        ``severity_label``: selo de severidade (ex.: ``"🔴 Crítico"``)
        ``reasons``: motivos de o ataque ter sido ruim (lista)
        ``highlights``: destaques positivos (lista)
        ``suggestions``: sugestões de melhoria (lista)
        ``context``: linhas de contexto (duração, placar, histórico)
    """
    db = getattr(bot, "db", None)

    attacker_th = getattr(attacker, "town_hall", None) or 0
    defender_th = getattr(defender, "town_hall", None) or 0
    th_diff = defender_th - attacker_th
    stars = getattr(attack, "stars", 0) or 0
    destruction = float(getattr(attack, "destruction", 0) or 0)
    duration = getattr(attack, "duration", None)
    dur_str = _fmt_duration(duration)
    fresh = None
    try:
        fresh = bool(getattr(attack, "is_fresh_attack", True))
    except Exception:
        fresh = None

    avg_duration = None
    avg_str = None
    try:
        avg_duration = _clan_avg_duration(war, our_clan=is_our_attack)
        avg_str = _fmt_duration(avg_duration)
    except Exception:
        avg_duration = None

    history = None
    try:
        if db is not None and is_our_attack:
            history = await _get_player_history(db, getattr(attacker, "tag", None))
    except Exception:
        history = None

    gained = None
    if not fresh and new_stars is not None:
        try:
            gained = new_stars(attack)
        except Exception:
            gained = None

    attacker_map = getattr(attacker, "map_position", None)
    defender_map = getattr(defender, "map_position", None)
    pos_diff = None
    if attacker_map is not None and defender_map is not None:
        pos_diff = attacker_map - defender_map

    context = []
    if dur_str:
        context.append(f"⏱ Duração: `{dur_str}`")
    if fresh is not None:
        context.append("🆕 Ataque Fresco" if fresh else "🔁 Limpeza")
    if avg_str:
        context.append(f"📊 Média do Clã: `{avg_str}`")
    scoreboard = _war_scoreboard(war)
    if scoreboard:
        context.append(scoreboard)
    if history:
        context.append(
            f"📈 Histórico ({history['wars']} guerras): média {history['avg_stars']:.1f}⭐/ataque "
            f"| {history['three_star_rate']:.0f}% 3⭐ | {history['missed']} perdidos"
        )
    context = context[:_MAX_CONTEXT]

    reasons = []
    suggestions = []
    highlights = []

    if is_our_attack:
        if stars <= 1:
            if stars == 0:
                severity_label = "🔴 Crítico"
            elif th_diff < 0:
                severity_label = "🔴 Crítico"
            else:
                severity_label = "🟠 Ruim"

            if th_diff < 0:
                reasons.append(
                    f"⚔️ **Erro de DIP:** atacou com CV superior ({attacker_th} vs {defender_th}) "
                    "e não garantiu o 3⭐ — desperdício de vantagem."
                )
            elif th_diff == 0:
                reasons.append(
                    f"⚔️ **Igualdade desperdiçada:** CV{attacker_th} vs CV{defender_th} é um alvo "
                    "esperado de 3⭐ — rendeu menos."
                )
            else:
                reasons.append(
                    f"🎯 **Missão difícil:** atacou {th_diff} CV acima (CV{attacker_th} vs CV{defender_th}) "
                    "e não conseguiu finalizar."
                )

            if destruction < 50:
                reasons.append(
                    f"💥 **Destruição muito baixa:** {destruction:.0f}% — ataque travou cedo "
                    "(composição, funnel ou rota de entrada falharam)."
                )
            elif destruction < 80:
                reasons.append(
                    f"💥 **Finalização fraca:** {destruction:.0f}% de destruição para {stars}⭐ — "
                    "a base ficou viva no detalhe."
                )
            else:
                reasons.append(
                    f"🎲 **Azar no final:** {destruction:.0f}% é uma destruição alta para {stars}⭐ — "
                    "a finalização não veio no detalhe."
                )

            if dur_str and avg_str and duration is not None and avg_duration is not None:
                diff_dur = duration - avg_duration
                if diff_dur > 60:
                    reasons.append(
                        f"⏱ **Ataque lento:** {dur_str} contra média de {avg_str} "
                        f"({int(diff_dur)}s acima) — sinal de luta contra o tempo/funnel."
                    )
                elif duration < 60:
                    reasons.append(
                        f"⏱ **Finalização precoce:** {dur_str} — rápido demais, composição provavelmente equivocada."
                    )

            if not fresh and gained is not None:
                if gained == 0:
                    reasons.append(
                        "🔁 **Limpeza desperdiçada:** a base já tinha estrelas e este ataque não melhorou nada (0 estrelas novas)."
                    )
                elif gained < stars:
                    reasons.append(
                        f"🔁 **Limpeza fraca:** melhorou apenas {gained}⭐ da base — alvo não foi finalizado."
                    )
                else:
                    reasons.append(f"🔁 **Limpeza mal executada:** era limpeza e rendeu só {stars}⭐.")
            elif fresh:
                reasons.append(
                    "🆕 **Primeiro ataque desperdiçado:** base intocada agora precisará de limpeza "
                    "(custou 1 ataque extra do clã)."
                )

            if pos_diff is not None:
                if pos_diff > 3:
                    reasons.append(
                        f"🗺️ **Alvo abaixo do posto:** atacou a base `{defender_map:02d}` estando no "
                        f"`{attacker_map:02d}` — desceu {pos_diff} posições e ainda falhou."
                    )
                elif pos_diff < -3:
                    reasons.append(
                        f"🗺️ **Subiu demais no mapa:** saiu do posto `{attacker_map:02d}` para atacar "
                        f"`{defender_map:02d}` ({abs(pos_diff)} posições acima) — alvo fora do seu peso."
                    )

            if history and history["attacks"] >= 3 and history["avg_stars"] >= 2.0 and stars <= 1:
                reasons.append(
                    f"📉 **Abaixo do padrão pessoal:** média histórica de {history['avg_stars']:.1f}⭐/ataque "
                    f"({history['three_star_rate']:.0f}% de 3⭐) — este resultado está muito abaixo."
                )

            reasons = reasons[:_MAX_REASONS]

            joined = "\n".join(reasons).lower()
            if "erro de dip" in joined:
                suggestions.append(
                    "📌 **DIP:** treinar composições para cenário de CV superior (QC Hybrid, Yeti Smash) "
                    "e ensaiar em guerra amistosa."
                )
            if "destruição" in joined or "finalização" in joined or "azar no final" in joined:
                suggestions.append(
                    "📌 **Execução:** rever o replay — checar rota de entrada, funnel e uso de feitiços "
                    "(rage/invis) na reta final."
                )
            if "ataque lento" in joined:
                suggestions.append(
                    "📌 **Tempo:** praticar gestão de tempo e funnel — não insistir em caminho sem dano; "
                    "fechar com reserva de tempo."
                )
            if "limpeza" in joined:
                suggestions.append(
                    "📌 **Limpeza:** coordenar finalizações no Discord — alvos com 1⭐ devem ser atacados "
                    "por quem tem composição certa para fechar."
                )
            if "padrão pessoal" in joined:
                suggestions.append(
                    "📌 **Atenção individual:** desvio grande do próprio padrão — verificar alvo difícil, "
                    "heróis disponíveis ou preparo."
                )
            if "primeiro ataque" in joined:
                suggestions.append(
                    "📌 **Planejamento:** alvos novos devem ser prioridade do ataque principal; deixar 0⭐ "
                    "para limpeza pesa no placar."
                )
            if not suggestions:
                suggestions.append(
                    "📌 **Revisão:** assistir o replay e comparar com ataques de 3⭐ no mesmo CV "
                    "para ajustar a estratégia."
                )
            suggestions = suggestions[:_MAX_SUGGESTIONS]

            return {
                "side": "attack",
                "is_bad": True,
                "severity_label": severity_label,
                "reasons": reasons,
                "highlights": [],
                "suggestions": suggestions,
                "context": context,
            }

        severity_label = "🔥 Excelente" if stars == 3 else "🔵 Normal"

        if th_diff > 0:
            if stars == 3:
                highlights.append(
                    f"🔥 **Ataque de cima perfeito:** 3⭐ em um CV{defender_th} "
                    f"(desvantagem de {th_diff} CV)."
                )
            else:
                highlights.append(
                    f"⚔️ **Lutou contra a gravidade:** {stars}⭐ em alvo {th_diff} CV acima."
                )
        if not fresh and gained is not None and gained > 0:
            highlights.append(f"🔁 **Limpeza cirúrgica:** adicionou {gained}⭐ nova(s) à base.")
        if history and history["attacks"] >= 3 and stars == 3 and history["three_star_rate"] < 50:
            highlights.append(
                f"💪 **Acima do padrão:** 3⭐ é raro para {getattr(attacker, 'name', 'o jogador')} "
                f"({history['three_star_rate']:.0f}% de 3⭐ no histórico)."
            )
        if dur_str and avg_str and duration is not None and avg_duration is not None and duration < avg_duration:
            highlights.append(f"⏱ **Eficiência:** fechou em {dur_str} — mais rápido que a média ({avg_str}).")

        highlights = highlights[:_MAX_HIGHLIGHTS]

        return {
            "side": "attack",
            "is_bad": False,
            "severity_label": severity_label,
            "reasons": [],
            "highlights": highlights,
            "suggestions": [],
            "context": context,
        }

    if stars <= 1:
        severity_label = "🟢 Boa Defesa"
        highlights.append("🛡️ **Defesa sólida:** segurou o ataque.")
        if attacker_th >= defender_th:
            highlights.append(
                f"💪 **Muralha:** resistiu a um CV{attacker_th} (mesmo/maior nível) com a base em CV{defender_th}."
            )
        else:
            highlights.append(
                f"🛡️ **Vantagem mantida:** atacante era CV{attacker_th} (inferior) e não passou da base CV{defender_th}."
            )
        try:
            defense_count = len(defender.defenses)
        except Exception:
            defense_count = 0
        if defense_count >= 2:
            held = sum(1 for d in defender.defenses if getattr(d, "stars", 0) <= 1)
            highlights.append(
                f"🏰 **Sobreviveu a {defense_count} ataques** (segurou {held} com ≤1⭐)."
            )
        highlights = highlights[:_MAX_HIGHLIGHTS]

        return {
            "side": "defense",
            "is_bad": False,
            "severity_label": severity_label,
            "reasons": [],
            "highlights": highlights,
            "suggestions": [],
            "context": context,
        }

    severity_label = "📉 Defesa Caída"
    reasons.append(
        f"📉 **Base caiu:** tomou {stars}⭐ ({destruction:.0f}%) de um CV{attacker_th}."
    )
    if attacker_th < defender_th:
        reasons.append(
            f"😱 **Caiu para alvo inferior:** atacante CV{attacker_th} contra base CV{defender_th} — defesa vulnerável."
        )
    if dur_str and avg_str and duration is not None and avg_duration is not None and duration < avg_duration:
        reasons.append(f"⏱ **Queda rápida:** foi destruída em {dur_str} — defesa de baixa resistência.")
    reasons = reasons[:_MAX_REASONS]
    suggestions.append(
        "📌 **Defesa:** revisar layout/armadilhas — bases que caem fácil para CVs iguais precisam de "
        "ajuste (compartimentos, posicionamento de Torres Inferno/Teslas)."
    )

    return {
        "side": "defense",
        "is_bad": True,
        "severity_label": severity_label,
        "reasons": reasons,
        "highlights": [],
        "suggestions": suggestions,
        "context": context,
    }
