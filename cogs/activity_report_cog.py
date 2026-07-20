# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import geniuslib as coc
from geniuslib.formatters import format_th, format_trophies
import asyncio
import datetime
import pytz
from pymongo import DESCENDING

logger = logging.getLogger("activity_report_cog")

class ActivityReportCog(commands.Cog, name="Relatório de Atividade"):
    """Cog para gerar relatórios de atividade diários e semanais do clã."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.war_history = self.db.war_history if self.db is not None else None
        self.donation_snapshots = self.db.donation_snapshots if self.db is not None else None
        self.battle_logs = self.db.battle_logs if self.db is not None else None
        self.watchlist = self.db.clan_watchlist if self.db is not None else None
        self.daily_report_task.start()
        self.weekly_report_task.start()

    def cog_unload(self):
        self.daily_report_task.cancel()
        self.weekly_report_task.cancel()

    async def get_war_activity(self, days: int = 1) -> dict:
        """Obtém atividade de guerra dos últimos N dias."""
        if self.war_history is None:
            return {}

        now = datetime.datetime.now(pytz.utc)
        cutoff = now - datetime.timedelta(days=days)
        
        cursor = self.war_history.find({
            "war_data.end_time_iso": {"$gte": cutoff.isoformat()}
        }).sort("war_data.end_time_iso", DESCENDING)
        
        wars = [doc async for doc in cursor]
        
        member_activity = {}
        for war in wars:
            members = war.get("our_clan_members_in_war", [])
            attacks_per = war.get("war_data", {}).get("attacks_per_member", 2)
            
            for member in members:
                tag = member.get("tag")
                if not tag:
                    continue
                
                if tag not in member_activity:
                    member_activity[tag] = {
                        "name": member.get("name", "?"),
                        "wars_participated": 0,
                        "total_attacks": 0,
                        "total_stars": 0,
                        "missed_attacks": 0,
                        "last_war_date": None
                    }
                
                member_activity[tag]["wars_participated"] += 1
                attacks = member.get("attacks_made", [])
                member_activity[tag]["total_attacks"] += len(attacks)
                member_activity[tag]["total_stars"] += sum(a.get("stars", 0) for a in attacks)
                member_activity[tag]["missed_attacks"] += max(0, attacks_per - len(attacks))
                
                war_date = war.get("war_data", {}).get("end_time_iso")
                if war_date:
                    member_activity[tag]["last_war_date"] = war_date
        
        return member_activity

    async def get_donation_activity(self, days: int = 1) -> dict:
        """Obtém atividade de doações dos últimos N dias."""
        if self.donation_snapshots is None:
            return {}

        now = datetime.datetime.now(pytz.utc)
        cutoff = now - datetime.timedelta(days=days)
        
        latest_cursor = self.donation_snapshots.find({}).sort("timestamp", -1).limit(1)
        latest = await latest_cursor.to_list(length=1)
        
        old_cursor = self.donation_snapshots.find({"timestamp": {"$gte": cutoff}}).sort("timestamp", 1).limit(1)
        old = await old_cursor.to_list(length=1)
        
        if not latest or not old:
            return {}
        
        latest_snapshot = latest[0]
        old_snapshot = old[0]
        
        donation_activity = {}
        for member in latest_snapshot.get("members", []):
            tag = member.get("tag")
            if not tag:
                continue
            
            old_member = next((m for m in old_snapshot.get("members", []) if m.get("tag") == tag), None)
            old_donated = old_member.get("donations", 0) if old_member else 0
            old_received = old_member.get("received", 0) if old_member else 0
            
            donation_activity[tag] = {
                "name": member.get("name", "?"),
                "donated": member.get("donations", 0) - old_donated,
                "received": member.get("received", 0) - old_received
            }
        
        return donation_activity

    async def get_watchlist_members(self) -> set:
        """Obtém membros na lista de observação."""
        if self.watchlist is None:
            return set()
        
        cursor = self.watchlist.find({})
        docs = [doc async for doc in cursor]
        return {doc.get("_id") for doc in docs}

    async def generate_activity_report(self, days: int = 1, member_tag: str = None) -> discord.Embed:
        """Gera um relatório de atividade."""
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan:
            return None
        
        war_activity = await self.get_war_activity(days)
        donation_activity = await self.get_donation_activity(days)
        watchlist = await self.get_watchlist_members()
        
        period_name = "Diário" if days == 1 else "Semanal"
        now = datetime.datetime.now(pytz.timezone("America/Sao_Paulo"))
        date_str = now.strftime("%d/%m/%Y") if days == 1 else f"{(now - datetime.timedelta(days=days)).strftime('%d/%m')} - {now.strftime('%d/%m/%Y')}"
        
        active_members = []
        partial_members = []
        inactive_members = []
        
        for member in clan.members:
            tag = member.tag
            war_data = war_activity.get(tag, {})
            donation_data = donation_activity.get(tag, {})
            
            wars_participated = war_data.get("wars_participated", 0)
            missed_attacks = war_data.get("missed_attacks", 0)
            donated = donation_data.get("donated", 0)
            total_stars = war_data.get("total_stars", 0)
            last_war = war_data.get("last_war_date")
            
            status = "active"
            reasons = []
            
            if wars_participated == 0 and days >= 1:
                status = "inactive"
                reasons.append("Sem guerras")
            
            if missed_attacks > 0:
                if status == "active":
                    status = "partial"
                reasons.append(f"{missed_attacks} ataques perdidos")
            
            if donated == 0 and days >= 1:
                if status == "active":
                    status = "partial"
                reasons.append("Sem doações")
            
            if tag in watchlist:
                reasons.append("Em observação")
            
            member_info = {
                "tag": tag,
                "name": member.name,
                "th": member.town_hall,
                "trophies": member.trophies,
                "league": member.league.name if member.league else "N/A",
                "wars_participated": wars_participated,
                "total_stars": total_stars,
                "missed_attacks": missed_attacks,
                "donated": donated,
                "reasons": reasons
            }
            
            if status == "active":
                active_members.append(member_info)
            elif status == "partial":
                partial_members.append(member_info)
            else:
                inactive_members.append(member_info)
        
        active_members.sort(key=lambda x: x["total_stars"], reverse=True)
        partial_members.sort(key=lambda x: x["missed_attacks"], reverse=True)
        inactive_members.sort(key=lambda x: x["name"])
        
        total_members = len(clan.members)
        active_count = len(active_members)
        active_pct = int((active_count / total_members * 100)) if total_members > 0 else 0
        
        total_donated = sum(m["donated"] for m in active_members + partial_members + inactive_members)
        top_donor = max(active_members + partial_members + inactive_members, key=lambda x: x["donated"]) if active_members + partial_members + inactive_members else None
        
        if member_tag:
            member_info = next((m for m in active_members + partial_members + inactive_members if m["tag"] == member_tag), None)
            if member_info:
                embed = discord.Embed(
                    title=f"📊 Atividade de {member_info['name']}",
                    description=f"Liga: {member_info['league']} | TH: {member_info['th']} | Troféus: {member_info['trophies']}",
                    color=discord.Color.blue()
                )
                embed.add_field(name="⚔️ Guerras", value=f"{member_info['wars_participated']} participadas | {member_info['total_stars']}⭐ | {member_info['missed_attacks']} perdidos", inline=False)
                embed.add_field(name="🎁 Doações", value=f"{member_info['donated']} doadas", inline=False)
                if member_info['reasons']:
                    embed.add_field(name="⚠️ Observações", value="\n".join(member_info['reasons']), inline=False)
                return embed
            else:
                return discord.Embed(description="Membro não encontrado.", color=discord.Color.red())
        
        embed = discord.Embed(
            title=f"📊 Relatório {period_name} de Atividade — {date_str}",
            color=discord.Color.blue()
        )
        
        if active_members:
            active_list = "\n".join([
                f"  {m['name']} — {m['trophies']}t | {m['league']} | {m['wars_participated']} guerras | {m['total_stars']}⭐ | {m['donated']} doações"
                for m in active_members[:10]
            ])
            embed.add_field(name=f"🟢 Ativos ({active_count})", value=active_list, inline=False)
        
        if partial_members:
            partial_list = "\n".join([
                f"  {m['name']} — {', '.join(m['reasons'])}"
                for m in partial_members[:5]
            ])
            embed.add_field(name=f"🟡 Parciais ({len(partial_members)})", value=partial_list, inline=False)
        
        if inactive_members:
            inactive_list = "\n".join([
                f"  {m['name']} — {', '.join(m['reasons']) if m['reasons'] else 'Sem atividade'}"
                for m in inactive_members[:5]
            ])
            embed.add_field(name=f"🔴 Inativos ({len(inactive_members)})", value=inactive_list, inline=False)
        
        summary = f"• {active_count}/{total_members} ativos ({active_pct}%)\n• {total_donated} doações totais"
        if top_donor and top_donor['donated'] > 0:
            summary += f"\n• Top doador: {top_donor['name']} ({top_donor['donated']})"
        
        embed.add_field(name="📈 Resumo", value=summary, inline=False)
        embed.set_footer(text=f"ClashGenius | Relatório {period_name.lower()}")
        
        return embed

    @app_commands.command(name="atividade", description="📊 Gera um relatório de atividade do clã.")
    @app_commands.describe(dias="Número de dias para analisar (padrão: 1)", membro="Tag do membro para detalhes")
    @app_commands.default_permissions(administrator=True)
    async def atividade_cmd(self, interaction: discord.Interaction, dias: int = 1, membro: str = None):
        await interaction.response.defer(thinking=True)
        
        member_tag = None
        if membro:
            member_tag = membro if membro.startswith("#") else f"#{membro}"
        
        embed = await self.generate_activity_report(days=dias, member_tag=member_tag)
        if embed is None:
            await interaction.followup.send("❌ Erro ao buscar dados na API da Supercell.")
            return
        
        await interaction.followup.send(embed=embed)

    @tasks.loop(time=datetime.time(hour=8, minute=0, tzinfo=pytz.timezone("America/Sao_Paulo")))
    async def daily_report_task(self):
        if self.bot.maintenance_mode or not getattr(self.bot, 'activity_report_channel_id', None):
            return
        
        logger.info("Gerando relatório diário de atividade...")
        try:
            embed = await self.generate_activity_report(days=1)
            if embed is None:
                return
            
            channel = self.bot.get_channel(self.bot.activity_report_channel_id) or await self.bot.fetch_channel(self.bot.activity_report_channel_id)
            if channel:
                await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro no relatório diário: {e}", exc_info=True)

    @daily_report_task.before_loop
    async def before_daily_report(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(60)

    @tasks.loop(time=datetime.time(hour=20, minute=0, tzinfo=pytz.timezone("America/Sao_Paulo")))
    async def weekly_report_task(self):
        now = datetime.datetime.now(pytz.timezone("America/Sao_Paulo"))
        if now.weekday() != 6:
            return
        
        if self.bot.maintenance_mode or not getattr(self.bot, 'activity_report_channel_id', None):
            return
        
        logger.info("Gerando relatório semanal de atividade...")
        try:
            embed = await self.generate_activity_report(days=7)
            if embed is None:
                return
            
            channel = self.bot.get_channel(self.bot.activity_report_channel_id) or await self.bot.fetch_channel(self.bot.activity_report_channel_id)
            if channel:
                await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro no relatório semanal: {e}", exc_info=True)

    @weekly_report_task.before_loop
    async def before_weekly_report(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(120)

async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityReportCog(bot))
