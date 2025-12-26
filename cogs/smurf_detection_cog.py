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
    Foca em Identidade (Nomes, Vínculos DB) e Maturidade (Conquistas de Longo Prazo),
    ignorando se a vila é rushada ou não.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.CONFIDENCE_THRESHOLD = 70  # Mostra apenas suspeitas com >70% de chance

    # ==================== ANÁLISE DE MATURIDADE ====================

    def _get_account_maturity_metrics(self, player: coc.Player) -> Dict[str, Any]:
        """
        Extrai métricas que indicam a 'idade real' da conta, impossíveis de comprar com gemas.
        """
        # 1. Obstáculos Removidos (Nice and Tidy)
        # Uma conta principal de 5 anos tem >4000 obstáculos. Um smurf de 1 ano tem <500.
        obstacles = 0
        achievement = player.get_achievement(name="Nice and Tidy")
        if achievement:
            obstacles = achievement.value

        # 2. Estrelas de Guerra (War Hero)
        war_stars = player.war_stars

        # 3. Doações Totais (Friend in Need)
        donations_total = 0
        fin_ach = player.get_achievement(name="Friend in Need")
        if fin_ach:
            donations_total = fin_ach.value

        # Pontuação de "Main Account" (0 a 100)
        # Baseado empiricamente em contas ativas
        score = 0
        score += min(obstacles / 2000, 1.0) * 40  # 40% do peso
        score += min(war_stars / 1000, 1.0) * 30  # 30% do peso
        score += min(donations_total / 50000, 1.0) * 30 # 30% do peso
        
        return {
            "score": int(score * 100),
            "obstacles": obstacles,
            "stars": war_stars,
            "is_likely_smurf": (score * 100) < 25 and player.town_hall >= 11
        }

    # ==================== ANÁLISE DE IDENTIDADE ====================

    def _normalize_name(self, name: str) -> str:
        """Limpa o nome para encontrar a raiz da identidade."""
        n = name.lower().strip()
        # Remove sufixos comuns de smurf
        subs = [
            r'\bmini\b', r'\bsec\b', r'\bconta\b', r'\bjr\b', 
            r'\bv\d+\b', r'\b2\b', r'\b3\b', r'\bsmurf\b', r'\balt\b', 
            r'\byt\b', r'\bpro\b', r'\bclash\b'
        ]
        for s in subs:
            n = re.sub(s, '', n)
        # Remove caracteres especiais e números soltos no fim
        n = re.sub(r'[^\w]', '', n)
        n = re.sub(r'\d+$', '', n)
        return n

    def _calculate_name_similarity(self, name1: str, name2: str) -> int:
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)
        
        if not n1 or not n2: return 0
        
        # Identidade Exata após limpeza (Ex: "João" e "João Mini")
        if n1 == n2: return 95
        
        # Inclusão (Ex: "Dark" e "DarkSoldier")
        if (len(n1) > 3 and n1 in n2) or (len(n2) > 3 and n2 in n1):
            return 85
            
        # Similaridade Difusa (Levenshtein)
        return int(difflib.SequenceMatcher(None, n1, n2).ratio() * 100)

    # ==================== COMANDO ====================

    @app_commands.command(name="smurfs", description="🕵️ IA Sherlock: Detecta multicontas via identidade e histórico.")
    async def slash_analyze_smurfs(self, interaction: discord.Interaction):
        
        # 1. Permissão: Só Liderança
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
            
            # Fetch players detalhados (necessário para Achievements)
            players_full = []
            async for p in self.bot.api_client.get_players(member_tags):
                players_full.append(p)

            # Mapa de donos confirmados pelo DB
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
                    # Ordena por maturidade (provável Main primeiro)
                    group.sort(key=lambda x: self._get_account_maturity_metrics(x)['score'], reverse=True)
                    
                    detected_groups.append({
                        "type": "CONFIRMADO (Registro)",
                        "confidence": 100,
                        "members": group,
                        "reason": f"Mesmo Discord ID (<@{d_id}>)"
                    })
                    for p in group: processed_tags.add(p.tag)

            # --- PASSO 2: Análise Heurística (Nomes + Maturidade) ---
            # Filtra quem já foi processado
            candidates = [p for p in players_full if p.tag not in processed_tags]
            # Ordena por "Score de Main" decrescente
            candidates.sort(key=lambda x: self._get_account_maturity_metrics(x)['score'], reverse=True)

            for i in range(len(candidates)):
                p1 = candidates[i]
                if p1.tag in processed_tags: continue

                possible_smurfs = []
                p1_metrics = self._get_account_maturity_metrics(p1)

                for j in range(i + 1, len(candidates)):
                    p2 = candidates[j]
                    if p2.tag in processed_tags: continue

                    similarity = self._calculate_name_similarity(p1.name, p2.name)
                    p2_metrics = self._get_account_maturity_metrics(p2)

                    # Apenas agrupa se houver alta similaridade de nome
                    if similarity >= 80:
                        # Se os nomes são iguais, verifica se a maturidade é diferente
                        # (Geralmente Main tem score 80+ e Smurf tem score <30)
                        maturity_diff = abs(p1_metrics['score'] - p2_metrics['score'])
                        
                        confidence = similarity
                        # Se a diferença de maturidade for alta, aumenta a confiança de ser Main+Smurf
                        if maturity_diff > 40: confidence += 10
                        
                        if confidence >= self.CONFIDENCE_THRESHOLD:
                            possible_smurfs.append(p2)
                            processed_tags.add(p2.tag)

                if possible_smurfs:
                    processed_tags.add(p1.tag)
                    group = [p1] + possible_smurfs
                    detected_groups.append({
                        "type": "SUSPEITA (IA)",
                        "confidence": 85, # Média estimada
                        "members": group,
                        "reason": "Padrão de Nome + Disparidade de Conquistas"
                    })

            # Geração do Embed
            if not detected_groups:
                await interaction.followup.send("✅ Nenhuma multiconta detectada fora do normal.")
                return

            embed = discord.Embed(
                title="🕵️ Relatório de Identidade e Smurfs",
                description="Análise baseada em **Vínculos de Registro** e **Maturidade da Conta** (Obstáculos/Estrelas).\n*Mostrando provável Main 👑 e suas secundárias.*",
                color=discord.Color.gold(),
                timestamp=datetime.datetime.now()
            )

            for group in detected_groups:
                main_acc = group['members'][0]
                others = group['members'][1:]
                
                m_metrics = self._get_account_maturity_metrics(main_acc)
                main_desc = f"👑 **{main_acc.name}** (CV{main_acc.town_hall}) - *{m_metrics['obstacles']} Obs. Removidos*"
                
                others_desc = []
                for smurf in others:
                    s_metrics = self._get_account_maturity_metrics(smurf)
                    others_desc.append(f"└ 👶 **{smurf.name}** (CV{smurf.town_hall}) - *{s_metrics['obstacles']} Obs.*")

                full_text = f"{main_desc}\n" + "\n".join(others_desc) + f"\n🔎 *{group['reason']}*"
                
                emoji = "🔗" if group['confidence'] == 100 else "⚠️"
                embed.add_field(name=f"{emoji} Grupo Detectado", value=full_text, inline=False)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro na análise smurf: {e}", exc_info=True)
            await interaction.followup.send("❌ Erro interno ao processar.")

async def setup(bot: commands.Bot):
    await bot.add_cog(SmurfDetectionCog(bot))
