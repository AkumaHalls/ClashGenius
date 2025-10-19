# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
import datetime
import pytz
from typing import List, Dict, Optional

logger = logging.getLogger("donation_cog")

class DonationsCog(commands.Cog, name="Relatório de Doações"):
    """
    Cog para analisar e enviar relatórios diários e semanais de doações dos jogadores.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        # Coleção para guardar o estado dos relatórios (último envio)
        self.reports_log = self.db.reports_log if self.db else None
        self.report_time = datetime.time(21, 0) # Horário de envio dos relatórios (21:00)

        self.send_donation_reports.start()

    async def cog_unload(self):
        self.send_donation_reports.cancel()

    async def _get_current_clan_donations(self) -> Dict[str, Dict]:
        """Busca os dados de doação atuais de todos os membros do clã."""
        try:
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            if not clan:
                return {}
            
            # Usando um dict comprehension para criar o dicionário de dados
            return {
                member.tag: {
                    "name": member.name,
                    "donations": member.donations,
                    "received": member.received
                }
                for member in clan.members
            }
        except Exception as e:
            logger.error(f"Erro ao buscar dados atuais do clã: {e}", exc_info=True)
            return {}

    async def _generate_report_embed(self, period: str, days: int) -> Optional[discord.Embed]:
        """
        Gera um embed com o relatório de doações para um determinado período.
        """
        logger.info(f"Gerando relatório de doações para o período: {period.capitalize()}")

        if not self.db:
            logger.error("Banco de dados não configurado para gerar relatório de doações.")
            return None

        end_data = await self._get_current_clan_donations()
        
        start_time_utc = datetime.datetime.now(pytz.utc) - datetime.timedelta(days=days)
        
        start_snapshot_doc = await self.db.donation_snapshots.find_one(
            {'timestamp': {'$lte': start_time_utc}},
            sort=[('timestamp', -1)]
        )

        if not start_snapshot_doc or 'members' not in start_snapshot_doc:
            logger.warning(f"Nenhum snapshot de {days} dia(s) atrás encontrado para gerar o relatório.")
            return None
            
        start_data = {member['tag']: member for member in start_snapshot_doc['members']}

        player_stats = []
        total_donated = 0
        total_received = 0

        for tag, end_stats in end_data.items():
            start_stats = start_data.get(tag)
            if start_stats:
                donated = end_stats["donations"] - start_stats["donations"]
                received = end_stats["received"] - start_stats["received"]
                
                if donated >= 0 or received >= 0: # Inclui mesmo se as doações diminuirem (saída/retorno)
                    player_stats.append({
                        "name": end_stats["name"],
                        "donated": donated,
                        "received": received
                    })
                    total_donated += donated
                    total_received += received

        if not player_stats:
            logger.info("Nenhuma atividade de doação no período para gerar relatório.")
            return None

        player_stats.sort(key=lambda x: x["donated"], reverse=True)
        
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        
        title = f"Daily Donations" if period == 'daily' else f"Weekly Donations"
        embed = discord.Embed(
            title=f"{clan.name} (#{clan.tag.strip('#')})",
            color=discord.Color.from_rgb(47, 49, 54) # Cor escura do Discord
        )
        if clan.badge:
            embed.set_thumbnail(url=clan.badge.url)

        end_time_local = datetime.datetime.now(self.bot.timezone).replace(hour=self.report_time.hour, minute=self.report_time.minute)
        start_time_local = end_time_local - datetime.timedelta(days=days)
        
        description = f"**{title}**\n"
        description += f"`{start_time_local.strftime('%d de %B de %Y %H:%M')} - {end_time_local.strftime('%d de %B de %Y %H:%M')}`\n\n"
        
        lines = []
        # Limita a 30 jogadores para não exceder o limite do embed
        for p in player_stats[:30]:
             # Garante que números negativos não quebrem o alinhamento
            donated_str = str(p['donated']).ljust(5)
            received_str = str(p['received']).ljust(5)
            lines.append(f"{donated_str} {received_str} {p['name']}")

        # Divide em múltiplos campos se a lista for muito grande
        report_str = "\n".join(lines)
        if not report_str:
            report_str = "Nenhuma atividade registrada no período."

        description += f"```{'Doadas'.ljust(5)} {'Recebidas'.ljust(5)} Jogador\n{'-'*40}\n{report_str}```"
        embed.description = description

        embed.set_footer(text=f"Total: {total_donated:,} doadas / {total_received:,} recebidas.")
        return embed

    async def _send_report(self, period: str, days: int, channel_id: int):
        """Função unificada para gerar e enviar um relatório."""
        embed = await self._generate_report_embed(period, days)
        if embed and channel_id:
            try:
                channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
                await channel.send(embed=embed)
                logger.info(f"Relatório de doações '{period}' enviado com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao enviar relatório de doações '{period}': {e}")
        elif not channel_id:
            logger.warning("ID do canal de doações não configurado. Relatório não enviado.")

    @tasks.loop(minutes=30)
    async def send_donation_reports(self):
        """Verifica se é hora de enviar os relatórios diários ou semanais."""
        if self.reports_log is None or self.bot.maintenance_mode or not self.bot.donations_channel_id:
            return

        now_local = datetime.datetime.now(self.bot.timezone)
        
        daily_log = await self.reports_log.find_one({"_id": "daily_donation_report"})
        last_sent_daily = daily_log.get("last_sent") if daily_log else None
        
        if now_local.time() >= self.report_time:
            if last_sent_daily is None or last_sent_daily.date() < now_local.date():
                logger.info("Hora de enviar o relatório diário de doações.")
                await self._send_report('daily', 1, self.bot.donations_channel_id)
                await self.reports_log.update_one(
                    {"_id": "daily_donation_report"},
                    {"$set": {"last_sent": datetime.datetime.now(pytz.utc)}},
                    upsert=True
                )

        if now_local.weekday() == 6: # 6 = Domingo
            weekly_log = await self.reports_log.find_one({"_id": "weekly_donation_report"})
            last_sent_weekly = weekly_log.get("last_sent") if weekly_log else None
            
            if now_local.time() >= self.report_time:
                if last_sent_weekly is None or last_sent_weekly.date() < now_local.date():
                    logger.info("Hora de enviar o relatório semanal de doações.")
                    await self._send_report('weekly', 7, self.bot.donations_channel_id)
                    await self.reports_log.update_one(
                        {"_id": "weekly_donation_report"},
                        {"$set": {"last_sent": datetime.datetime.now(pytz.utc)}},
                        upsert=True
                    )
    
    @send_donation_reports.before_loop
    async def before_send_donation_reports(self):
        await self.bot.wait_until_ready()
        await self.bot.db_ready.wait()
        await self.bot.coc_client_ready.wait()

    @commands.group(name='doacoes', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def donations(self, ctx: commands.Context):
        """Mostra informações sobre os comandos de doação."""
        await ctx.send("Use `!doacoes daily` ou `!doacoes weekly` para gerar relatórios manuais.")

    @donations.command(name='daily')
    @commands.has_permissions(administrator=True)
    async def force_daily_report(self, ctx: commands.Context):
        """Força a geração e envio do relatório diário."""
        await ctx.message.add_reaction("🔄")
        await self._send_report('daily', 1, ctx.channel.id)
        await ctx.message.remove_reaction("🔄", self.bot.user)
        await ctx.message.add_reaction("✅")
        
    @donations.command(name='weekly')
    @commands.has_permissions(administrator=True)
    async def force_weekly_report(self, ctx: commands.Context):
        """Força a geração e envio do relatório semanal."""
        await ctx.message.add_reaction("🔄")
        await self._send_report('weekly', 7, ctx.channel.id)
        await ctx.message.remove_reaction("🔄", self.bot.user)
        await ctx.message.add_reaction("✅")

async def setup(bot: commands.Bot):
    # Renomeado para donation_cog.py
    await bot.add_cog(DonationsCog(bot))
