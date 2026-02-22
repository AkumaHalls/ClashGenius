# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands
import difflib
import coc
import datetime
from collections import defaultdict
from typing import List, Dict, Any, Tuple
import re
import random

logger = logging.getLogger("smurf_detection_cog")

class SmurfDetectionCog(commands.Cog, name="Detetor de Smurfs IA"):
    """
    Sistema Pericial de Detecção de Contas Secundárias (Dossiê Dinâmico).
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.MIN_SIMILARITY_TO_INVESTIGATE = 65

    # ==================== EXTRAÇÃO DE DADOS ====================

    def _extract_account_stats(self, player: coc.Player) -> Dict[str, Any]:
        obstacles = 0
        ach_tidy = player.get_achievement(name="Nice and Tidy")
        if ach_tidy: obstacles = ach_tidy.value

        gold_grab = 0
        ach_gold = player.get_achievement(name="Gold Grab")
        if ach_gold: gold_grab = ach_gold.value

        capital_gold = 0
        ach_capital = player.get_achievement(name="Aggressive Capitalism")
        if ach_capital: capital_gold = ach_capital.value

        home_heroes = ["Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion", "Minion Prince"]
        heroes_lvl = sum(h.level for h in player.heroes if h.name in home_heroes)

        account_mass = (player.town_hall * 1000) + (heroes_lvl * 50) + (obstacles * 2) + (gold_grab / 1000000) + (capital_gold / 50000)

        return {
            "th": player.town_hall,
            "heroes": heroes_lvl,
            "obstacles": obstacles,
            "gold_grab": gold_grab,
            "capital_gold": capital_gold,
            "mass": account_mass
        }

    # ==================== ANÁLISE LEXICAL ====================

    def _clean_name(self, name: str) -> str:
        n = name.lower().strip()
        dirty_words = [
            r'\bmini\b', r'\bsec\b', r'\bconta\b', r'\bjr\b', r'\bsecundaria\b',
            r'\bv\d+\b', r'\b2\b', r'\b3\b', r'\bsmurf\b', r'\balt\b', 
            r'\bpro\b', r'\bclash\b', r'\bfake\b', r'\bdoacao\b'
        ]
        for word in dirty_words: n = re.sub(word, '', n)
        n = re.sub(r'[^\w]', '', n)
        n = re.sub(r'\d+$', '', n)
        return n.strip()

    def _get_identity_match(self, name1: str, name2: str) -> int:
        n1 = self._clean_name(name1)
        n2 = self._clean_name(name2)
        if not n1 or not n2: return 0
        if n1 == n2: return 100
        if (len(n1) >= 4 and n1 in n2) or (len(n2) >= 4 and n2 in n1): return 85
        return int(difflib.SequenceMatcher(None, n1, n2).ratio() * 100)

    # ==================== O TRIBUNAL DA IA (DOSSIÊ DINÂMICO) ====================

    def _format_large_number(self, num: int) -> str:
        if num >= 1_000_000_000: return f"{num/1_000_000_000:.1f} Bilhões"
        if num >= 1_000_000: return f"{num/1_000_000:.1f} Milhões"
        return f"{num:,}"

    def _judge_relationship(self, p1: coc.Player, stats1: Dict, p2: coc.Player, stats2: Dict, similarity: int) -> Tuple[bool, int, str, coc.Player, coc.Player]:
        if stats1['mass'] >= stats2['mass']:
            main_p, main_s, smurf_p, smurf_s = p1, stats1, p2, stats2
        else:
            main_p, main_s, smurf_p, smurf_s = p2, stats2, p1, stats1

        confidence = similarity
        reasons = []

        # Fatores Matemáticos Exatos
        mass_ratio = main_s['mass'] / max(smurf_s['mass'], 1)
        gold_diff = main_s['gold_grab'] - smurf_s['gold_grab']
        obs_diff = main_s['obstacles'] - smurf_s['obstacles']
        th_diff = main_s['th'] - smurf_s['th']
        hero_diff = main_s['heroes'] - smurf_s['heroes']

        # Montagem Dinâmica de Frases (Para nunca gerar o mesmo relatório)
        if similarity >= 90:
            reasons.append(random.choice([
                "Assinatura nominal virtualmente idêntica detectada.",
                "Padrão de nomenclatura compartilha o mesmo radical primário.",
                "Forte correlação lexical entre os apelidos (Match > 90%)."
            ]))

        if mass_ratio > 2.0:
            confidence += 15
            reasons.append(random.choice([
                f"Discrepância colossal de evolução: A conta principal é {mass_ratio:.1f}x mais pesada matematicamente.",
                f"Evidência de conta 'Doadora/Espectadora': O progresso difere em {mass_ratio:.1f} vezes.",
            ]))
            if gold_diff > 500_000_000:
                reasons.append(f"A disparidade de {self._format_large_number(gold_diff)} de ouro roubado comprova que '{smurf_p.name}' é uma conta recente.")
        elif mass_ratio < 1.15:
            confidence -= 25
            reasons.append("ALERTA DE FALSO POSITIVO: As contas possuem tempo de vida e farm quase idênticos. Risco de serem irmãos/amigos jogando juntos com nomes de clã padronizados.")

        if th_diff >= 3:
            confidence += 10
            reasons.append(f"A conta secundária está defasada em {th_diff} níveis de Centro de Vila.")
        
        if hero_diff > 80:
            reasons.append(f"Diferença gritante de esforço: '{main_p.name}' tem {hero_diff} níveis de heróis a mais.")

        if obs_diff > 3000:
             reasons.append(f"Dados históricos irrefutáveis: A conta principal removeu {obs_diff:,} obstáculos a mais, atestando anos de diferença na data de criação.")

        confidence = min(max(int(confidence), 0), 99)
        is_smurf = confidence >= 80  # Subi a régua de exigência para 80% para evitar erro humano
        
        final_reasoning = "\n".join([f"▪️ {r}" for r in reasons])
        return is_smurf, confidence, final_reasoning, main_p, smurf_p

    # ==================== COMANDO DISCORD ====================

    @app_commands.command(name="smurfs", description="🕵️ Gera um Dossiê Pericial irrefutável das contas secundárias no clã.")
    @app_commands.default_permissions(administrator=True)
    async def slash_analyze_smurfs(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        try:
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            if not clan:
                await interaction.followup.send("❌ Erro de comunicação com os servidores da Supercell.")
                return

            member_tags = [m.tag for m in clan.members]
            players_full = []
            async for p in self.bot.api_client.get_players(member_tags):
                players_full.append(p)

            p_stats = {p.tag: self._extract_account_stats(p) for p in players_full}

            # Link DB Exato
            db_owners = defaultdict(list)
            if self.db is not None:
                cursor = self.db.users.find({"player_tag": {"$in": member_tags}})
                async for doc in cursor:
                    if doc.get("discord_id"): db_owners[doc.get("discord_id")].append(doc.get("player_tag"))

            investigations = []
            processed_tags = set()

            # Processa DB
            for d_id, tags in db_owners.items():
                if len(tags) > 1:
                    group = [p for p in players_full if p.tag in tags]
                    group.sort(key=lambda x: p_stats[x.tag]['mass'], reverse=True)
                    investigations.append({
                        "main": group[0], "smurfs": group[1:], "confidence": 100,
                        "reason": f"▪️ Vínculo absoluto confirmado no Banco de Dados via Discord ID: <@{d_id}>."
                    })
                    for p in group: processed_tags.add(p.tag)

            # Processa IA
            candidates = [p for p in players_full if p.tag not in processed_tags]
            for i in range(len(candidates)):
                p1 = candidates[i]
                if p1.tag in processed_tags: continue

                group_smurfs = []
                best_confidence = 0
                best_reason = ""
                main_acc = p1

                for j in range(i + 1, len(candidates)):
                    p2 = candidates[j]
                    if p2.tag in processed_tags: continue

                    sim = self._get_identity_match(p1.name, p2.name)
                    if sim >= self.MIN_SIMILARITY_TO_INVESTIGATE:
                        is_smurf, conf, reason, m_p, s_p = self._judge_relationship(p1, p_stats[p1.tag], p2, p_stats[p2.tag], sim)
                        if is_smurf:
                            main_acc = m_p 
                            group_smurfs.append(s_p)
                            processed_tags.add(s_p.tag)
                            if conf > best_confidence:
                                best_confidence = conf
                                best_reason = reason

                if group_smurfs:
                    processed_tags.add(main_acc.tag)
                    investigations.append({
                        "main": main_acc, "smurfs": group_smurfs,
                        "confidence": best_confidence, "reason": best_reason
                    })

            if not investigations:
                await interaction.followup.send("✅ **Clã Limpo:** A IA não detectou contas suspeitas de serem da mesma pessoa nesta auditoria.")
                return

            # HEADER DO RELATÓRIO
            embed = discord.Embed(
                title="📂 DOSSIÊ PERICIAL: MÚLTIPLAS CONTAS",
                description="Este relatório cruza telemetria de jogo (Loot Histórico, Níveis Heróicos e Obstáculos) com Lexicologia para determinar com precisão a posse de contas secundárias.",
                color=0x2b2d31, # Cor dark premium do Discord
                timestamp=datetime.datetime.now()
            )

            investigations.sort(key=lambda x: x['confidence'], reverse=True)

            def format_stats(p_tag):
                s = p_stats[p_tag]
                loot_str = self._format_large_number(s['gold_grab'])
                return f"**CV:** {s['th']} | **Heróis:** {s['heroes']} | **Loot:** {loot_str}"

            for inv in investigations:
                main = inv['main']
                smurfs = inv['smurfs']
                conf = inv['confidence']
                
                if conf == 100:
                    status = "🟢 CONFIRMAÇÃO SISTÊMICA (100%)"
                elif conf >= 90:
                    status = f"🔴 RISCO EXTREMO ({conf}%)"
                else:
                    status = f"🟠 ALTA SUSPEITA ({conf}%)"

                body = f"```yaml\n{status}\n```"
                body += f"👑 **[MAIN] {main.name}** (`{main.tag}`)\n> └ {format_stats(main.tag)}\n\n"
                
                for s in smurfs:
                    body += f"👶 **[SMURF] {s.name}** (`{s.tag}`)\n> └ {format_stats(s.tag)}\n\n"
                
                body += f"**🔎 Argumentação Lógica da IA:**\n{inv['reason']}"
                
                embed.add_field(name="━"*30, value=body, inline=False)
                
            embed.set_footer(text="AIA (Auditoria de Inteligência Artificial) • ClashGenius", icon_url="https://cdn-icons-png.flaticon.com/512/2102/2102633.png")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro no dossie smurf: {e}", exc_info=True)
            await interaction.followup.send("❌ Erro fatal ao gerar o dossiê.")

async def setup(bot: commands.Bot):
    await bot.add_cog(SmurfDetectionCog(bot))
