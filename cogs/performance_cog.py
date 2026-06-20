# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import geniuslib as coc
from geniuslib.formatters import format_th, format_trophies
import asyncio
from pymongo import DESCENDING

logger = logging.getLogger("performance_cog")

class PerformanceCog(commands.Cog, name="Análise de Desempenho"):
    """Cog que audita o clã e dedura jogadores com métricas ruins (Sanguessugas e Desertores)."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.weekly_report_task.start()

    def cog_unload(self):
        self.weekly_report_task.cancel()

    async def generate_performance_report(self):
        # 1. Obter membros atuais do clã
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan: return None

        members = {m.tag: m for m in clan.members}
        bad_performers = []

        # 2. Obter as últimas 10 guerras do banco de dados (Amostragem justa)
        recent_wars = []
        if self.db is not None:
            cursor = self.db.war_history.find({}).sort("war_data.end_time_iso", DESCENDING).limit(10)
            recent_wars = [doc async for doc in cursor]

        for tag, member in members.items():
            reasons = []
            
            # REGRA 1: Doações Sanguessugas
            if member.received > 1500 and member.donations < (member.received * 0.1):
                reasons.append(f"🩸 **Sanguessuga:** Recebeu {member.received}, mas doou apenas {member.donations}.")
            elif member.received > 500 and member.donations == 0:
                reasons.append(f"🩸 **Zero Doações:** Recebeu {member.received} e não doou NADA.")

            # REGRA 2: Histórico de Guerra
            missed_attacks = 0
            total_stars = 0
            wars_played = 0
            attacks_done = 0

            for war_doc in recent_wars:
                our_members = war_doc.get("our_clan_members_in_war", [])
                member_war_data = next((m for m in our_members if m["tag"] == tag), None)
                
                if member_war_data:
                    wars_played += 1
                    attacks = member_war_data.get("attacks_made", [])
                    attacks_per_member = war_doc.get("war_data", {}).get("attacks_per_member", 2)
                    
                    missed = attacks_per_member - len(attacks)
                    missed_attacks += missed
                    attacks_done += len(attacks)
                    total_stars += sum(a.get("stars", 0) for a in attacks)

            if missed_attacks >= 2:
                reasons.append(f"⚔️ **Desertor:** Perdeu {missed_attacks} ataques nas últimas {wars_played} guerras disputadas.")
            
            if attacks_done >= 4:
                avg_stars = total_stars / attacks_done
                if avg_stars <= 1.2:
                    reasons.append(f"📉 **Mira Torta:** Média péssima de {avg_stars:.1f} estrelas por ataque.")

            # Se a ficha dele for suja, vai para a lista de corte
            if reasons:
                bad_performers.append({
                    "member": member,
                    "reasons": reasons,
                    "score": len(reasons) + (missed_attacks * 2) # Pesa mais quem falta na guerra
                })

        # Ordena pelos piores (maior score de infrações)
        bad_performers.sort(key=lambda x: x["score"], reverse=True)
        return bad_performers

    @app_commands.command(name="faxina", description="🧹 Gera um relatório dos piores desempenhos do clã (Sanguessugas e Desertores).")
    @app_commands.default_permissions(administrator=True)
    async def faxina_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        bad_performers = await self.generate_performance_report()
        
        if bad_performers is None:
            await interaction.followup.send("❌ Erro ao buscar dados na API da Supercell.")
            return
        
        if not bad_performers:
            await interaction.followup.send("✅ Uau! Nenhum jogador apresentou métricas tóxicas nas últimas avaliações.")
            return

        embed = discord.Embed(
            title="🧹 Relatório de Faxina (Baixo Desempenho)",
            description="Membros identificados com métricas ativamente prejudiciais ao clã nas últimas análises de Guerra e Doação.",
            color=discord.Color.brand_red()
        )

        for bp in bad_performers[:10]: # Limita aos 10 Piores pra não explodir o limite do Discord
            member = bp["member"]
            reasons_text = "\n".join(bp["reasons"])
            embed.add_field(
                name=f"🗑️ {member.name} ({format_th(member.town_hall)})",
                value=f"{reasons_text}\n`Tag: {member.tag}`",
                inline=False
            )

        embed.set_footer(text="IA de Auditoria do ClashGenius | Avaliação baseada nas últimas 10 guerras.")
        await interaction.followup.send(embed=embed)

    @tasks.loop(hours=168) # Roda automaticamente a cada 7 dias
    async def weekly_report_task(self):
        if self.bot.maintenance_mode or not self.bot.low_performance_channel_id:
            return
        
        logger.info("Executando Relatório Semanal de Faxina...")
        try:
            bad_performers = await self.generate_performance_report()
            if not bad_performers: return 

            channel = self.bot.get_channel(self.bot.low_performance_channel_id) or await self.bot.fetch_channel(self.bot.low_performance_channel_id)
            if not channel: return

            embed = discord.Embed(
                title="📊 Auditoria Semanal de Desempenho",
                description="A IA identificou os seguintes membros apresentando **baixo desempenho crítico** ou comportamento de sanguessuga:",
                color=discord.Color.orange()
            )

            for bp in bad_performers[:10]:
                member = bp["member"]
                reasons_text = "\n".join(bp["reasons"])
                embed.add_field(
                    name=f"⚠️ {member.name} ({format_th(member.town_hall)})",
                    value=f"{reasons_text}\n`Tag: {member.tag}`",
                    inline=False
                )

            embed.set_footer(text=f"Para ver este relatório a qualquer momento, digite /faxina")
            await channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro no Relatório Semanal: {e}", exc_info=True)

    @weekly_report_task.before_loop
    async def before_weekly_report(self):
        await self.bot.wait_until_ready()
        # Atrasa 5 minutos na primeira vez pra não sobrecarregar o bot na hora que ele liga
        await asyncio.sleep(300)

async def setup(bot: commands.Bot):
    await bot.add_cog(PerformanceCog(bot))