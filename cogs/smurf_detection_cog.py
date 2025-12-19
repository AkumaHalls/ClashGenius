# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands
import difflib
import coc
import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
import re

logger = logging.getLogger("smurf_detection_cog")

class SmurfDetectionCog(commands.Cog, name="Detetor de Smurfs IA"):
    """Sistema avançado de IA para detecção de contas secundárias com análise multicamada."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        
        # Pesos Recalibrados para evitar Falsos Positivos em Líderes/Ativos
        self.weights = {
            'db_link': 100,              # 100% Certeza (Vínculo interno)
            'name_exact': 60,            # Nomes idênticos ou Variações claras (Rei -> Rei v2)
            'name_high': 40,             # Nomes muito similares
            'feeder_behavior': 35,       # Comportamento clássico de doador (Doa muito, ataca nada)
            'hero_rush': 25,             # Heróis muito baixos para o CV (Melhor indicador que estrelas)
            'war_stars_rush': 10,        # Estrelas baixas (Peso reduzido drasticamente)
            'activity_sync': 15,         # Troféus/Atividade idêntica
        }

    # ==================== UTILITÁRIOS ====================

    def _get_hero_levels(self, player: coc.Player) -> Tuple[int, int]:
        """Retorna (Soma dos Níveis dos Heróis, Média dos Níveis)."""
        total_levels = 0
        count = 0
        for hero in player.heroes:
            if hero.is_home_base: # Ignora heróis da base do construtor
                total_levels += hero.level
                count += 1
        return total_levels, (total_levels / count if count > 0 else 0)

    def _normalize_name(self, name: str) -> str:
        """Limpeza agressiva de nome para comparação."""
        name = name.lower().strip()
        # Remove sufixos comuns de contas secundárias
        subs = [r'\bmini\b', r'\bsec\b', r'\bconta\b', r'\bjr\b', r'\bv\d+\b', r'\b2\b', r'\b3\b', r'\bsmurf\b', r'\balt\b']
        for s in subs:
            name = re.sub(s, '', name)
        return re.sub(r'[^\w]', '', name) # Remove tudo que não for letra/número

    # ==================== ANÁLISES ====================

    def check_name_similarity(self, name1: str, name2: str) -> Dict[str, float]:
        """Comparação de nomes com proteção para nomes curtos."""
        n1_clean = self._normalize_name(name1)
        n2_clean = self._normalize_name(name2)
        
        # Proteção para nomes curtos (Ex: "Gui" e "Luiz" não devem bater)
        if len(n1_clean) < 4 or len(n2_clean) < 4:
            # Se for curto, exige correspondência EXATA ou contida (Ex: "Rei" em "Rei v2")
            if n1_clean == n2_clean:
                return {'score': 1.0, 'type': 'exact'}
            if (n1_clean in n2_clean or n2_clean in n1_clean) and abs(len(n1_clean) - len(n2_clean)) <= 3:
                 return {'score': 0.9, 'type': 'contained'}
            return {'score': 0.0, 'type': 'none'}

        # Para nomes longos, usa SequenceMatcher
        ratio = difflib.SequenceMatcher(None, n1_clean, n2_clean).ratio()
        return {'score': ratio, 'type': 'ratio'}

    def analyze_hero_rush(self, player: coc.Player) -> Dict:
        """
        Analisa se os heróis estão muito abaixo do esperado para o CV.
        Isso é o maior indicador de conta secundária feita às pressas.
        """
        total, avg = self._get_hero_levels(player)
        th = player.town_hall
        
        # Média mínima esperada de heróis por CV (Conservador)
        # CV16 espera média 70+, CV15 média 60+, etc.
        min_avg_map = {
            16: 65, 15: 55, 14: 45, 13: 35, 12: 25, 11: 15, 10: 10
        }
        
        if th in min_avg_map:
            expected = min_avg_map[th]
            if avg < expected:
                diff = expected - avg
                # Se a média dos heróis for 20 níveis abaixo do esperado
                if diff > 20: 
                    return {'score': self.weights['hero_rush'], 'details': [f"Heróis muito fracos (Média {int(avg)} vs Esperado {expected}+)"]}
                elif diff > 10:
                    return {'score': 15, 'details': [f"Heróis fracos (Média {int(avg)})"]}
        
        return {'score': 0, 'details': []}

    def analyze_war_stars_legacy(self, player: coc.Player) -> Dict:
        """
        Analisa estrelas, mas com peso MUITO menor.
        Líderes e jogadores antigos podem ter poucas estrelas se farmaram muito.
        """
        th = player.town_hall
        stars = player.war_stars
        
        # CV alto com MENOS de 200 estrelas é suspeito. 
        # Mas CV16 com 600 estrelas é NORMAL para quem não foca em guerra.
        if th >= 14 and stars < 200:
             return {'score': self.weights['war_stars_rush'], 'details': [f"Baixa exp. de guerra ({stars} ⭐)"]}
        elif th >= 11 and stars < 50:
             return {'score': self.weights['war_stars_rush'], 'details': [f"Conta nova/sem guerra ({stars} ⭐)"]}
             
        return {'score': 0, 'details': []}

    def analyze_feeder_behavior(self, player: coc.Player) -> Dict:
        """Detecta contas usadas apenas para doar (Feeders)."""
        donations = player.donations
        attacks = player.attack_wins
        
        # Ratio Doação/Ataque. Se doa 1000 e ataca 0, é feeder.
        if donations > 500:
            if attacks == 0:
                return {'score': self.weights['feeder_behavior'], 'details': [f"Feeder Puro: {donations} doações, 0 ataques"]}
            ratio = donations / attacks
            if ratio > 50: # Ex: 1000 doações e 20 ataques = ratio 50
                 return {'score': 20, 'details': [f"Comportamento de Doador ({int(ratio)}:1 doação/ataque)"]}
        
        return {'score': 0, 'details': []}

    async def get_confirmed_links(self, member_tags: List[str]) -> Dict[int, List[str]]:
        """Busca vínculos no DB."""
        if self.db is None: return {}
        duplicates = defaultdict(list)
        try:
            cursor = self.db.users.find({"player_tag": {"$in": member_tags}})
            discord_map = defaultdict(set)
            async for doc in cursor:
                if doc.get("discord_id") and doc.get("player_tag"):
                    discord_map[doc.get("discord_id")].add(doc.get("player_tag"))
            for d_id, tags in discord_map.items():
                if len(tags) > 1: duplicates[d_id] = list(tags)
        except Exception as e: logger.error(f"Erro DB: {e}")
        return duplicates

    # ==================== LÓGICA PRINCIPAL ====================

    @app_commands.command(name="smurfs", description="🕵️ IA Precisa: Detecção de contas secundárias (Versão Líder).")
    async def slash_analyze_smurfs(self, interaction: discord.Interaction):
        
        # 1. Permissão: Só para a chefia
        user_roles = [r.id for r in interaction.user.roles]
        is_boss = (interaction.user.id == interaction.guild.owner_id) or \
                  (interaction.user.guild_permissions.administrator) or \
                  (self.bot.leader_role_id in user_roles) or \
                  (self.bot.coleader_role_id in user_roles)
        
        if not is_boss:
            await interaction.response.send_message("❌ Acesso negado. Ferramenta exclusiva para Liderança.", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        try:
            # 2. Coleta de Dados
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            if not clan:
                await interaction.followup.send("❌ Erro ao ler dados do clã.")
                return

            member_tags = [m.tag for m in clan.members]
            players = []
            
            # Fetch completo para pegar heróis e estrelas
            async for p in self.bot.api_client.get_players(member_tags):
                players.append(p)

            confirmed_links = await self.get_confirmed_links(member_tags)

            # 3. Processamento
            pairs_found = []
            individuals_flagged = []
            processed_pairs = set()

            # --- Análise de Pares (Nome e Vínculo) ---
            for i in range(len(players)):
                p1 = players[i]
                
                # Análise Individual (Focada em Heróis e Doação)
                ind_score = 0
                ind_reasons = []
                
                # Checa Heróis (Peso alto)
                h_an = self.analyze_hero_rush(p1)
                if h_an['score'] > 0:
                    ind_score += h_an['score']
                    ind_reasons.extend(h_an['details'])
                
                # Checa Feeder (Peso alto)
                f_an = self.analyze_feeder_behavior(p1)
                if f_an['score'] > 0:
                    ind_score += f_an['score']
                    ind_reasons.extend(f_an['details'])

                # Checa Estrelas (Peso baixo - Apenas informativo se < 50)
                s_an = self.analyze_war_stars_legacy(p1)
                if s_an['score'] > 0:
                    ind_score += s_an['score']
                    ind_reasons.extend(s_an['details'])

                # Só reporta individualmente se tiver pontuação relevante (> 30)
                # Isso evita flagar líderes CV16 com muitas estrelas mas heróis bons
                if ind_score >= 30:
                    individuals_flagged.append({
                        'player': p1, 'score': ind_score, 'reasons': ind_reasons
                    })

                # Comparação de Pares
                for j in range(i + 1, len(players)):
                    p2 = players[j]
                    pair_id = tuple(sorted([p1.tag, p2.tag]))
                    if pair_id in processed_pairs: continue

                    pair_score = 0
                    pair_evidence = []

                    # Verifica DB
                    is_linked_db = False
                    for d_id, tags in confirmed_links.items():
                        if p1.tag in tags and p2.tag in tags:
                            pair_score = 100
                            pair_evidence.append("🔗 Vínculo confirmado (Banco de Dados)")
                            is_linked_db = True
                            break
                    
                    if not is_linked_db:
                        # Verifica Nome
                        name_check = self.check_name_similarity(p1.name, p2.name)
                        if name_check['score'] >= 0.85: # Exige 85% de similaridade
                            pair_score += self.weights['name_exact']
                            pair_evidence.append(f"🔡 Nomes quase idênticos ({int(name_check['score']*100)}%)")
                        elif name_check['score'] >= 0.70 and name_check['type'] != 'none':
                            pair_score += self.weights['name_high']
                            pair_evidence.append(f"🔡 Nomes similares")

                    if pair_score >= 40:
                        pairs_found.append({
                            'p1': p1, 'p2': p2, 'score': pair_score, 'evidence': pair_evidence
                        })
                        processed_pairs.add(pair_id)

            # 4. Geração do Relatório (Ordenado)
            pairs_found.sort(key=lambda x: x['score'], reverse=True)
            individuals_flagged.sort(key=lambda x: x['score'], reverse=True)

            embed = discord.Embed(
                title="🛡️ Relatório de Segurança: Smurfs & Secundárias",
                description=f"Análise focada em **Heróis** e **Padrões de Doação**.\nIgnorando falsos positivos baseados apenas em estrelas.",
                color=discord.Color.dark_red(),
                timestamp=datetime.datetime.now()
            )

            has_content = False

            # Seção 1: Vínculos Claros (Pares)
            if pairs_found:
                has_content = True
                text = ""
                count = 0
                for p in pairs_found:
                    if count >= 10: break # Limite visual
                    p1, p2 = p['p1'], p['p2']
                    emoji = "🔴" if p['score'] >= 80 else "🟠"
                    text += f"{emoji} **{p1.name}** ↔️ **{p2.name}**\n"
                    text += f"└ {', '.join(p['evidence'])}\n"
                    count += 1
                embed.add_field(name="👥 Contas Vinculadas / Nomes Iguais", value=text, inline=False)

            # Seção 2: Contas Feeder / Rushadas (Suspeita Individual)
            if individuals_flagged:
                has_content = True
                text = ""
                count = 0
                for item in individuals_flagged:
                    if count >= 10: break
                    p = item['player']
                    reasons = ", ".join(item['reasons'])
                    # Formatação clean
                    text += f"⚠️ **{p.name}** (CV{p.town_hall})\n"
                    text += f"└ {reasons}\n"
                    count += 1
                embed.add_field(name="🤖 Comportamento de Smurf/Feeder Detectado", value=text, inline=False)

            if not has_content:
                embed.description = "✅ **Nenhuma conta suspeita detectada.**\nTodos os membros parecem ter contas principais ou estão dentro dos padrões normais."
                embed.color = discord.Color.green()

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro em slash_analyze_smurfs: {e}", exc_info=True)
            await interaction.followup.send("❌ Erro interno na análise.")

async def setup(bot: commands.Bot):
    await bot.add_cog(SmurfDetectionCog(bot))
