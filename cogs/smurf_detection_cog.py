# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands
import difflib
import coc
import datetime # <--- Adicionado o import que faltava

logger = logging.getLogger("smurf_detection_cog")

class SmurfDetectionCog(commands.Cog, name="Detetor de Contas Secundárias"):
    """Cog para analisar o clã em busca de indícios de contas secundárias (Smurfs)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def check_name_similarity(self, name1: str, name2: str) -> float:
        """Calcula a similaridade entre dois nomes (0 a 1)."""
        # Remove caracteres comuns que geram falso positivo se o nome for curto
        clean_n1 = name1.lower().replace(" ", "").replace("-", "").replace("_", "")
        clean_n2 = name2.lower().replace(" ", "").replace("-", "").replace("_", "")
        
        # O SequenceMatcher encontra a maior sequência de caracteres iguais
        return difflib.SequenceMatcher(None, clean_n1, clean_n2).ratio()

    def is_feeder_account(self, member: coc.ClanMember) -> bool:
        """
        Heurística para identificar contas 'Feeder' (Doação apenas).
        Critérios (ajustáveis):
        - TH abaixo de 12 (exemplo)
        - Doações altas (> 500)
        - Ataques na temporada baixos (< 10)
        """
        if member.town_hall < 12 and member.donations > 500 and member.attack_wins < 10:
            return True
        return False

    @commands.command(name='analise_smurfs', aliases=['checksmurfs', 'smurfs'])
    async def analyze_smurfs(self, ctx: commands.Context):
        """Analisa os membros do clã em busca de possíveis contas secundárias."""
        
        # Verifica permissões (Líder/Co-Líder ou Admin)
        is_admin = ctx.author.guild_permissions.administrator
        has_role = False
        if self.bot.leader_role_id and any(r.id == self.bot.leader_role_id for r in ctx.author.roles): has_role = True
        if self.bot.coleader_role_id and any(r.id == self.bot.coleader_role_id for r in ctx.author.roles): has_role = True
        
        if not (is_admin or has_role):
            await ctx.send("❌ Você não tem permissão para executar esta análise.")
            return

        await ctx.typing()
        
        try:
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            if not clan:
                await ctx.send("❌ Não foi possível obter dados do clã.")
                return

            members = list(clan.members)
            suspects_name = []
            suspects_feeder = []
            processed_pairs = set()

            # 1. Análise de Similaridade de Nomes
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    m1 = members[i]
                    m2 = members[j]
                    
                    # Evita duplicatas
                    pair_id = tuple(sorted((m1.tag, m2.tag)))
                    if pair_id in processed_pairs:
                        continue
                    
                    similarity = self.check_name_similarity(m1.name, m2.name)
                    
                    # Se similaridade > 80% ou nomes contêm indícios claros
                    indicios = ["mini", "sec", "jr", "conta", "2", "3"]
                    name_indicates = any(ind in m1.name.lower() or ind in m2.name.lower() for ind in indicios)
                    
                    threshold = 0.80 if not name_indicates else 0.65 # Tolerância menor se tiver palavras chave

                    if similarity >= threshold:
                        suspects_name.append({
                            "m1": m1,
                            "m2": m2,
                            "similarity": round(similarity * 100, 1)
                        })
                        processed_pairs.add(pair_id)

            # 2. Análise Comportamental (Feeder/Doação)
            for member in members:
                if self.is_feeder_account(member):
                    suspects_feeder.append(member)

            # --- Construção do Relatório ---
            embed = discord.Embed(
                title="🕵️ Relatório de Análise de Contas Secundárias",
                description=f"Análise realizada em {len(members)} membros.",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now()
            )

            if not suspects_name and not suspects_feeder:
                embed.description += "\n\n✅ **Nenhum indício suspeito encontrado.**"
                await ctx.send(embed=embed)
                return

            # Adiciona suspeitas por nome
            if suspects_name:
                text_names = ""
                # Limita para não estourar o limite do Discord (1024 chars)
                for item in suspects_name[:15]: 
                    m1 = item['m1']
                    m2 = item['m2']
                    text_names += f"🔹 **{m1.name}** vs **{m2.name}**\n   `{item['similarity']}% similar` | Tags: {m1.tag} / {m2.tag}\n"
                
                if len(suspects_name) > 15:
                    text_names += f"\n... e mais {len(suspects_name) - 15} pares."
                
                embed.add_field(name="🔡 Nomes Similares (Possíveis Donos Iguais)", value=text_names, inline=False)

            # Adiciona suspeitas por comportamento
            if suspects_feeder:
                text_feeders = ""
                for m in suspects_feeder[:15]:
                    text_feeders += f"🔸 **{m.name}** (CV{m.town_hall})\n   Doações: {m.donations} | Ataques: {m.attack_wins}\n"
                
                if len(suspects_feeder) > 15:
                    text_feeders += f"\n... e mais {len(suspects_feeder) - 15} contas."

                embed.add_field(name="🤖 Possíveis Contas de Doação (Feeders)", value=text_feeders, inline=False)
                embed.set_footer(text="Nota: Estes são apenas indícios baseados em dados públicos.")

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro na análise de smurfs: {e}", exc_info=True)
            await ctx.send("❌ Ocorreu um erro ao realizar a análise.")

async def setup(bot: commands.Bot):
    await bot.add_cog(SmurfDetectionCog(bot))
