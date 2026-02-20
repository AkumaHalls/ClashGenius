# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands
import difflib
import coc
import datetime
from collections import defaultdict
from typing import List, Dict, Any
import re
import asyncio

logger = logging.getLogger("smurf_detection_cog")

class SmurfDetectionCog(commands.Cog, name="Detetor de Smurfs IA"):
    """
    Sistema reformulado de detecção de contas secundárias (Smurfs).
    Foca em Identidade (Nomes, Vínculos DB) e Maturidade (Conquistas, Heróis e CV).
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.CONFIDENCE_THRESHOLD = 75  # Limiar ajustado para a nova fórmula dinâmica

    # ==================== ANÁLISE DE MATURIDADE ====================

    def _get_account_maturity_metrics(self, player: coc.Player) -> Dict[str, Any]:
        """
        Extrai métricas que indicam a 'idade real' e o esforço da conta.
        """
        obstacles = 0
        achievement = player.get_achievement(name="Nice and Tidy")
        if achievement: obstacles = achievement.value

        war_stars = player.war_stars

        donations_total = 0
        fin_ach = player.get_achievement(name="Friend in Need")
        if fin_ach: donations_total = fin_ach.value

        # Novo: Nível total de heróis (indicador massivo de Main vs Smurf)
        heroes_total_level = sum(h.level for h in player.heroes if h.is_home_village)

        # Novo Balanceamento de Pontuação (0 a 100)
        score = 0
        score += min(obstacles / 3000, 1.0) * 25       # 25% peso
        score += min(war_stars / 1000, 1.0) * 25       # 25% peso
        score += min(donations_total / 50000, 1.0) * 20 # 20% peso
        score += min(heroes_total_level / 200, 1.0) * 30 # 30% peso (Heróis altos indicam Main)
        
        return {
            "score": int(score * 100),
            "obstacles": obstacles,
            "stars": war_stars,
            "heroes_lvl": heroes_total_level
        }

    # ==================== ANÁLISE DE IDENTIDADE ====================

    def _normalize_name(self, name: str) -> str:
        """Limpa o nome para encontrar a raiz da identidade."""
        n = name.lower().strip()
        # Regex expandida com termos comuns em PT-BR e EN
        subs = [
            r'\bmini\b', r'\bsec\b', r'\bconta\b', r'\bjr\b', r'\bsecundaria\b',
            r'\bv\d+\b', r'\b2\b', r'\b3\b', r'\bsmurf\b', r'\balt\b', 
            r'\byt\b', r'\bpro\b', r'\bclash\b', r'\bfake\b', r'\bdoacao\b', r'\bdonator\b'
        ]
        for s in subs:
            n = re.sub(s, '', n)
        
        # Remove caracteres especiais
        n = re.sub(r'[^\w]', '', n)
        # Remove números soltos no final (ex: Joao123 -> Joao)
        n = re.sub(r'\d+$', '', n)
        return n.strip()

    def _calculate_name_similarity(self, name1: str, name2: str) -> int:
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)
        
        if not n1 or not n2: return 0
        if n1 == n2: return 95
        if (len(n1) > 3 and n1 in n2) or (len(n2) > 3 and n2 in n1): return 85
            
        return int(difflib.SequenceMatcher(None, n1, n2).ratio() * 100)

    # ==================== COMANDO ====================

    @app_commands.command(name="smurfs", description="🕵️ IA Sherlock: Detecta multicontas via identidade e histórico.")
    async def slash_analyze_smurfs(self, interaction: discord.Interaction):
        
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

            member_tags = [m.tag for m in clan.members]
            
            players_full = []
            async for p in self.bot.api_client.get_players(member_tags):
                players_full.append(p)

            db_owners = defaultdict(list)
            if self.db is not None:
                cursor = self.db.users.find({"player_tag": {"$in": member_tags}})
                async for doc in cursor:
                    if doc.get("discord_id"):
                        db_owners[doc.get("discord_id")].append(doc.get("player_tag"))

            detected_groups = []
            processed_tags = set()

            # --- PASSO 1: Vínculos Confirmados (DB) ---
            for d_id, tags in db_owners.items():
                if len(tags) > 1:
                    group = [p for p in players_full if p.tag in tags]
                    group.sort(key=lambda x: self._get_account_maturity_metrics(x)['score'], reverse=True)
                    
                    detected_groups.append({
                        "type": "CONFIRMADO (Registro)",
                        "confidence": 100,
                        "members": group,
                        "reason": f"Mesmo Discord ID (<@{d_id}>)"
                    })
                    for p in group: processed_tags.add(p.tag)

            # --- PASSO 2: Análise Heurística Inteligente ---
            candidates = [p for p in players_full if p.tag not in processed_tags]
            candidates.sort(key=lambda x: self._get_account_maturity_metrics(x)['score'], reverse=True)

            for i in range(len(candidates)):
                p1 = candidates[i]
                if p1.tag in processed_tags: continue

                possible_smurfs = []
                p1_metrics = self._get_account_maturity_metrics(p1)
                group_confidence = 0

                for j in range(i + 1, len(candidates)):
                    p2 = candidates[j]
                    if p2.tag in processed_tags: continue

                    similarity = self._calculate_name_similarity(p1.name, p2.name)
                    p2_metrics = self._get_account_maturity_metrics(p2)

                    # Novo motor de confiança ponderada
                    if similarity >= 65:  # Base da identidade parecida
                        confidence = similarity
                        
                        maturity_diff = p1_metrics['score'] - p2_metrics['score']
                        th_diff = p1.town_hall - p2.town_hall
                        
                        # Bônus: Se o TH do Main for consideravelmente maior
                        if th_diff >= 2: confidence += 10
                        elif th_diff < 0: confidence -= 10 # Se a suposta Smurf tem CV maior, reduz a chance
                        
                        # Bônus: Disparidade de esforço na conta (Main farmada vs Smurf rushada)
                        if maturity_diff > 30: confidence += 15
                        
                        # Bônus: Smurfs geralmente têm menos troféus que a principal
                        if (p1.trophies - p2.trophies) > 1000: confidence += 5

                        if confidence >= self.CONFIDENCE_THRESHOLD:
                            possible_smurfs.append(p2)
                            processed_tags.add(p2.tag)
                            group_confidence = max(group_confidence, min(confidence, 99)) # Limita a 99% para diferenciar do DB

                if possible_smurfs:
                    processed_tags.add(p1.tag)
                    group = [p1] + possible_smurfs
                    # Garante que a Main absoluta fique no topo da exibição
                    group.sort(key=lambda x: self._get_account_maturity_metrics(x)['score'], reverse=True)
                    
                    detected_groups.append({
                        "type": "SUSPEITA (IA)",
                        "confidence": group_confidence,
                        "members": group,
                        "reason": "Padrão de Identidade + Disparidade de Status"
                    })

            # --- PASSO 3: Geração do Embed ---
            if not detected_groups:
                await interaction.followup.send("✅ Nenhuma multiconta detectada fora do normal.")
                return

            embed = discord.Embed(
                title="🕵️ Relatório de Identidade e Smurfs",
                description="Cruzamento de **Registros do Banco** e **Motor Heurístico** (Nomes, Heróis, CV e Conquistas).\n*As contas com maior probabilidade de serem as 'Principais' estão coroadas 👑.*",
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now()
            )

            for group in detected_groups:
                main_acc = group['members'][0]
                others = group['members'][1:]
                
                m_metrics = self._get_account_maturity_metrics(main_acc)
                main_desc = f"👑 **{main_acc.name}** (CV{main_acc.town_hall}) - *Score: {m_metrics['score']}/100 | Heróis Lvl {m_metrics['heroes_lvl']}*"
                
                others_desc = []
                for smurf in others:
                    s_metrics = self._get_account_maturity_metrics(smurf)
                    others_desc.append(f"└ 👶 **{smurf.name}** (CV{smurf.town_hall}) - *Score: {s_metrics['score']}/100 | Heróis Lvl {s_metrics['heroes_lvl']}*")

                confidence_text = f"**Confiança:** {group['confidence']}%"
                full_text = f"{main_desc}\n" + "\n".join(others_desc) + f"\n🔎 *{group['reason']}* | {confidence_text}"
                
                emoji = "🔗" if group['confidence'] == 100 else ("⚠️" if group['confidence'] >= 85 else "👀")
                embed.add_field(name=f"{emoji} {group['type']}", value=full_text, inline=False)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro na análise smurf: {e}", exc_info=True)
            await interaction.followup.send("❌ Erro interno ao processar.")

async def setup(bot: commands.Bot):
    await bot.add_cog(SmurfDetectionCog(bot))
