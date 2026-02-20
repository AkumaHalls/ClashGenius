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

logger = logging.getLogger("smurf_detection_cog")

class SmurfDetectionCog(commands.Cog, name="Detetor de Smurfs IA"):
    """
    Sistema Pericial de Detecção de Contas Secundárias.
    Cruza identidade lexical com 'Massa da Conta' (Tempo de vida, Loot e Heróis)
    para fornecer vereditos quase incontestáveis.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.MIN_SIMILARITY_TO_INVESTIGATE = 65

    # ==================== EXTRAÇÃO DE DADOS PERICIAIS ====================

    def _extract_account_stats(self, player: coc.Player) -> Dict[str, Any]:
        """Extrai os dados difíceis de forjar que provam a idade/esforço da conta."""
        
        # Obstáculos: Limitado a quem joga há muito tempo
        obstacles = 0
        ach_tidy = player.get_achievement(name="Nice and Tidy")
        if ach_tidy: obstacles = ach_tidy.value

        # Gold Grab: Ouro roubado na vida. Bilhões = Conta antiga/Main
        gold_grab = 0
        ach_gold = player.get_achievement(name="Gold Grab")
        if ach_gold: gold_grab = ach_gold.value

        # Capital Gold: Adicionado para punir smurfs inativas na capital
        capital_gold = 0
        ach_capital = player.get_achievement(name="Aggressive Capitalism")
        if ach_capital: capital_gold = ach_capital.value

        # Heróis Totais (Correção: Filtro por nome para evitar erro de versão da API)
        home_heroes = ["Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion", "Minion Prince"]
        heroes_lvl = sum(h.level for h in player.heroes if h.name in home_heroes)

        # "Massa da Conta": Uma fórmula matemática para definir quem é o "Pai" e quem é o "Filho"
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
        """Extrai a 'alma' do nome do jogador para comparações."""
        n = name.lower().strip()
        # Remove sufixos clássicos de contas secundárias
        dirty_words = [
            r'\bmini\b', r'\bsec\b', r'\bconta\b', r'\bjr\b', r'\bsecundaria\b',
            r'\bv\d+\b', r'\b2\b', r'\b3\b', r'\bsmurf\b', r'\balt\b', 
            r'\bpro\b', r'\bclash\b', r'\bfake\b', r'\bdoacao\b'
        ]
        for word in dirty_words:
            n = re.sub(word, '', n)
        
        n = re.sub(r'[^\w]', '', n) # Remove emojis e pontuações
        n = re.sub(r'\d+$', '', n)  # Remove números no final (Joao123 -> Joao)
        return n.strip()

    def _get_identity_match(self, name1: str, name2: str) -> int:
        n1 = self._clean_name(name1)
        n2 = self._clean_name(name2)
        
        if not n1 or not n2: return 0
        if n1 == n2: return 100
        
        # Se um nome contiver o outro completamente (ex: Dark / DarkLord)
        if (len(n1) >= 4 and n1 in n2) or (len(n2) >= 4 and n2 in n1): 
            return 85
            
        return int(difflib.SequenceMatcher(None, n1, n2).ratio() * 100)

    # ==================== O TRIBUNAL DA IA ====================

    def _judge_relationship(self, p1: coc.Player, stats1: Dict, p2: coc.Player, stats2: Dict, similarity: int) -> Tuple[bool, int, str, coc.Player, coc.Player]:
        """
        Julga se p1 e p2 são a mesma pessoa e quem é a Main.
        Retorna: (Is_Smurf, Confidence, Reasoning, Main_Player, Smurf_Player)
        """
        # Define quem é a provável principal baseada na "Massa da conta"
        if stats1['mass'] >= stats2['mass']:
            main_p, main_s = p1, stats1
            smurf_p, smurf_s = p2, stats2
        else:
            main_p, main_s = p2, stats2
            smurf_p, smurf_s = p1, stats1

        confidence = similarity
        reasons = []

        # Cálculo de disparidade (Quantas vezes a Main é maior que a Smurf?)
        mass_ratio = main_s['mass'] / max(smurf_s['mass'], 1)

        if similarity >= 85:
            reasons.append("Identidade visual idêntica/contida.")
        else:
            reasons.append("Nomes altamente sugestivos.")

        # Julgamento de Progressão
        if mass_ratio > 1.8:
            confidence += 15
            reasons.append(f"Disparidade brutal de progresso (Massa {mass_ratio:.1f}x maior).")
        elif mass_ratio > 1.3:
            confidence += 5
            reasons.append("Main é visivelmente mais velha/evoluída.")
        elif mass_ratio < 1.1:
            # Contas quase idênticas em tamanho (Pode ser irmãos, namorados, ou 2 mains)
            confidence -= 20
            reasons.append("Contas com progresso muito similar (Risco de serem pessoas diferentes na mesma casa).")

        # Julgamento de Town Hall
        th_diff = main_s['th'] - smurf_s['th']
        if th_diff >= 2:
            confidence += 10
            reasons.append(f"CV da Secundária é {th_diff} níveis menor.")
        
        # Julgamento de Esforço (Obstáculos)
        obs_diff = main_s['obstacles'] - smurf_s['obstacles']
        if obs_diff > 2000:
            reasons.append("A Main joga há muito mais anos (Obstáculos).")

        confidence = min(max(int(confidence), 0), 99) # Trava entre 0 e 99 (100 é reservado para DB)
        
        is_smurf = confidence >= 75
        final_reasoning = " | ".join(reasons)
        
        return is_smurf, confidence, final_reasoning, main_p, smurf_p

    # ==================== COMANDO DISCORD ====================

    @app_commands.command(name="smurfs", description="🕵️ IA Pericial: Identifica contas secundárias com laudo detalhado.")
    async def slash_analyze_smurfs(self, interaction: discord.Interaction):
        
        # Validação de Permissão
        user_roles = [r.id for r in interaction.user.roles]
        is_allowed = (interaction.user.guild_permissions.administrator) or \
                     (self.bot.leader_role_id in user_roles) or \
                     (self.bot.coleader_role_id in user_roles)
        
        if not is_allowed:
            await interaction.response.send_message("❌ Acesso exclusivo para Liderança.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        try:
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            if not clan:
                await interaction.followup.send("❌ Erro ao ler dados do clã.")
                return

            # Coleta de dados profundos da API
            member_tags = [m.tag for m in clan.members]
            players_full = []
            async for p in self.bot.api_client.get_players(member_tags):
                players_full.append(p)

            # Pré-calcula os status periciais para economizar processamento
            p_stats = {p.tag: self._extract_account_stats(p) for p in players_full}

            # Linkagem de Banco de Dados (Provas Cabais)
            db_owners = defaultdict(list)
            if self.db is not None:
                cursor = self.db.users.find({"player_tag": {"$in": member_tags}})
                async for doc in cursor:
                    if doc.get("discord_id"):
                        db_owners[doc.get("discord_id")].append(doc.get("player_tag"))

            investigations = []
            processed_tags = set()

            # PASSO 1: O que o Banco de Dados confirmar, é lei.
            for d_id, tags in db_owners.items():
                if len(tags) > 1:
                    group = [p for p in players_full if p.tag in tags]
                    # Define a principal baseada na massa
                    group.sort(key=lambda x: p_stats[x.tag]['mass'], reverse=True)
                    
                    investigations.append({
                        "main": group[0],
                        "smurfs": group[1:],
                        "confidence": 100,
                        "reason": f"Vínculo exato no Banco de Dados (Discord ID <@{d_id}>)."
                    })
                    for p in group: processed_tags.add(p.tag)

            # PASSO 2: Varredura Pericial da IA
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
                        is_smurf, conf, reason, m_p, s_p = self._judge_relationship(
                            p1, p_stats[p1.tag], p2, p_stats[p2.tag], sim
                        )
                        
                        if is_smurf:
                            main_acc = m_p # A IA atualiza quem é a real dona do grupo
                            group_smurfs.append(s_p)
                            processed_tags.add(s_p.tag)
                            if conf > best_confidence:
                                best_confidence = conf
                                best_reason = reason

                if group_smurfs:
                    processed_tags.add(main_acc.tag)
                    investigations.append({
                        "main": main_acc,
                        "smurfs": group_smurfs,
                        "confidence": best_confidence,
                        "reason": best_reason
                    })

            # PASSO 3: Geração do Laudo Final (Embed Detalhado)
            if not investigations:
                await interaction.followup.send("✅ Inspeção concluída. Nenhuma anomalia ou multiconta detectada.")
                return

            embed = discord.Embed(
                title="⚖️ Laudo Pericial de Multicontas",
                description="O sistema cruzou **identidade lexical** com **variáveis de tempo de vida, capital e loot** para determinar contas secundárias.\n*Se a confiança estiver alta e os atributos divergirem muito, o banimento é seguro.*",
                color=0xFF4444, # Vermelho alerta
                timestamp=datetime.datetime.now()
            )

            # Ordena para mostrar os casos de IA com maior probabilidade primeiro
            investigations.sort(key=lambda x: x['confidence'], reverse=True)

            def format_stats(p_tag):
                s = p_stats[p_tag]
                loot_format = f"{s['gold_grab']/1000000:.1f}M" if s['gold_grab'] < 1000000000 else f"{s['gold_grab']/1000000000:.1f}B"
                cap_format = f"{s['capital_gold']/1000000:.1f}M"
                return f"`Heróis: {s['heroes']:>3}` | `Obs: {s['obstacles']:>4}` | `Loot: {loot_format:>5}` | `Cap: {cap_format:>4}`"

            for inv in investigations:
                main = inv['main']
                smurfs = inv['smurfs']
                
                # Cabeçalho da Main
                emoji = "🔒" if inv['confidence'] == 100 else ("🚨" if inv['confidence'] >= 90 else "⚠️")
                title = f"{emoji} CONF {inv['confidence']}% | {main.name} & Secundárias"
                
                # Corpo de Dados
                body = f"👑 **{main.name}** (CV {main.town_hall})\n> {format_stats(main.tag)}\n"
                
                for s in smurfs:
                    body += f"└ 👶 **{s.name}** (CV {s.town_hall})\n> {format_stats(s.tag)}\n"
                
                body += f"\n📋 **Justificativa da IA:**\n*{inv['reason']}*"
                
                embed.add_field(name=title, value=body, inline=False)
                
            embed.set_footer(text="Atenção: 'Obs' = Obstáculos Removidos | 'Loot' = Ouro Roubado Vitalício | 'Cap' = Ouro da Capital")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro na pericia smurf: {e}", exc_info=True)
            await interaction.followup.send("❌ Ocorreu um erro interno durante a inspeção cruzada.")

async def setup(bot: commands.Bot):
    await bot.add_cog(SmurfDetectionCog(bot))
