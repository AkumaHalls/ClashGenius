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

logger = logging.getLogger("tournament_cog")

class TournamentCog(commands.Cog, name="Torneio"):
    """Cog para rastrear torneios semanais e gerar resumos de promoção/rebaixamento."""

    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.tournament_snapshots = self.db.tournament_snapshots if self.db is not None else None
        self.snapshot_task.start()
        self.end_check_task.start()

    def cog_unload(self):
        self.snapshot_task.cancel()
        self.end_check_task.cancel()

    async def take_snapshot(self) -> bool:
        """Tira um snapshot dos membros atuais do clã."""
        if self.tournament_snapshots is None:
            return False
        
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan:
            return False
        
        now = datetime.datetime.now(pytz.utc)
        tournament_id = now.strftime("%Y-W%V")
        
        existing = await self.tournament_snapshots.find_one({"_id": tournament_id})
        if existing:
            return False
        
        members_data = []
        for member in clan.members:
            members_data.append({
                "tag": member.tag,
                "name": member.name,
                "trophies": member.trophies,
                "league": member.league.name if member.league else "N/A",
                "league_id": member.league.id if member.league else 0
            })
        
        await self.tournament_snapshots.insert_one({
            "_id": tournament_id,
            "start_time": now.isoformat(),
            "clan_tag": self.bot.clan_tag,
            "members": members_data
        })
        
        logger.info(f"Snapshot do torneio {tournament_id} salvo com {len(members_data)} membros.")
        return True

    async def generate_tournament_summary(self) -> discord.Embed:
        """Gera o resumo do torneio comparando snapshot inicial vs estado atual."""
        if self.tournament_snapshots is None:
            return None
        
        now = datetime.datetime.now(pytz.utc)
        tournament_id = now.strftime("%Y-W%V")
        
        snapshot = await self.tournament_snapshots.find_one({"_id": tournament_id})
        if not snapshot:
            return None
        
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan:
            return None
        
        promotions = []
        demotions = []
        unchanged = []
        
        for old_member in snapshot.get("members", []):
            tag = old_member.get("tag")
            current_member = next((m for m in clan.members if m.tag == tag), None)
            
            if not current_member:
                continue
            
            old_league = old_member.get("league", "N/A")
            new_league = current_member.league.name if current_member.league else "N/A"
            old_league_id = old_member.get("league_id", 0)
            new_league_id = current_member.league.id if current_member.league else 0
            old_trophies = old_member.get("trophies", 0)
            new_trophies = current_member.trophies
            
            trophy_diff = new_trophies - old_trophies
            
            member_info = {
                "name": current_member.name,
                "tag": tag,
                "th": current_member.town_hall,
                "old_league": old_league,
                "new_league": new_league,
                "old_trophies": old_trophies,
                "new_trophies": new_trophies,
                "trophy_diff": trophy_diff
            }
            
            if new_league_id > old_league_id:
                promotions.append(member_info)
            elif new_league_id < old_league_id:
                demotions.append(member_info)
            else:
                unchanged.append(member_info)
        
        promotions.sort(key=lambda x: x["trophy_diff"], reverse=True)
        demotions.sort(key=lambda x: x["trophy_diff"])
        unchanged.sort(key=lambda x: x["new_trophies"], reverse=True)
        
        start_time = snapshot.get("start_time", "?")
        br_tz = pytz.timezone("America/Sao_Paulo")
        start_dt = datetime.datetime.fromisoformat(start_time.replace("Z", "+00:00")).astimezone(br_tz)
        date_range = f"{start_dt.strftime('%d/%m')} - {now.astimezone(br_tz).strftime('%d/%m/%Y')}"
        
        embed = discord.Embed(
            title=f"🏅 Torneio Finalizado — {date_range}",
            color=discord.Color.gold()
        )
        
        if promotions:
            promo_list = "\n".join([
                f"  ↑ {m['name']} — {m['old_league']} → {m['new_league']} ({m['trophy_diff']:+d}t)"
                for m in promotions[:10]
            ])
            embed.add_field(name=f"📈 Promoções ({len(promotions)})", value=promo_list, inline=False)
        
        if demotions:
            demo_list = "\n".join([
                f"  ↓ {m['name']} — {m['old_league']} → {m['new_league']} ({m['trophy_diff']:+d}t)"
                for m in demotions[:10]
            ])
            embed.add_field(name=f"📉 Rebaixamentos ({len(demotions)})", value=demo_list, inline=False)
        
        if unchanged:
            top5 = unchanged[:5]
            top_list = "\n".join([
                f"  {i+1}. {m['name']} — {m['new_trophies']}t ({m['new_league']})"
                for i, m in enumerate(top5)
            ])
            embed.add_field(name="🏆 Top 5 do Clã", value=top_list, inline=False)
        
        best_climb = max(promotions, key=lambda x: x["trophy_diff"]) if promotions else None
        if best_climb and best_climb["trophy_diff"] > 0:
            embed.add_field(name="🎯 Melhor Climb", value=f"  ↑↑ {best_climb['name']} — subiu {best_climb['trophy_diff']} tropheus!", inline=False)
        
        summary = f"• {len(promotions)} promoções | {len(demotions)} rebaixamentos | {len(unchanged)} sem mudança"
        embed.add_field(name="📈 Resumo", value=summary, inline=False)
        embed.set_footer(text="ClashGenius | Resumo de Torneio")
        
        return embed

    async def get_tournament_data_for_web(self) -> dict:
        """Retorna dados do torneio como dict para a web API."""
        if self.tournament_snapshots is None:
            return None
        
        now = datetime.datetime.now(pytz.utc)
        tournament_id = now.strftime("%Y-W%V")
        
        snapshot = await self.tournament_snapshots.find_one({"_id": tournament_id})
        if not snapshot:
            return None
        
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        if not clan:
            return None
        
        promotions = []
        demotions = []
        unchanged = []
        
        for old_member in snapshot.get("members", []):
            tag = old_member.get("tag")
            current_member = next((m for m in clan.members if m.tag == tag), None)
            
            if not current_member:
                continue
            
            old_league = old_member.get("league", "N/A")
            new_league = current_member.league.name if current_member.league else "N/A"
            old_league_id = old_member.get("league_id", 0)
            new_league_id = current_member.league.id if current_member.league else 0
            old_trophies = old_member.get("trophies", 0)
            new_trophies = current_member.trophies
            
            member_info = {
                "name": current_member.name,
                "tag": tag,
                "old_league": old_league,
                "new_league": new_league,
                "old_trophies": old_trophies,
                "new_trophies": new_trophies,
                "trophy_diff": new_trophies - old_trophies
            }
            
            if new_league_id > old_league_id:
                promotions.append(member_info)
            elif new_league_id < old_league_id:
                demotions.append(member_info)
            else:
                unchanged.append(member_info)
        
        promotions.sort(key=lambda x: x["trophy_diff"], reverse=True)
        demotions.sort(key=lambda x: x["trophy_diff"])
        unchanged.sort(key=lambda x: x["new_trophies"], reverse=True)
        
        return {
            "promotions": promotions,
            "demotions": demotions,
            "unchanged": unchanged
        }

    @app_commands.command(name="torneio", description="🏅 Gera o resumo do torneio atual.")
    @app_commands.default_permissions(administrator=True)
    async def torneio_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        
        embed = await self.generate_tournament_summary()
        if embed is None:
            await interaction.followup.send("❌ Nenhum snapshot de torneio encontrado ou erro ao buscar dados.")
            return
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="torneio_snapshot", description="📸 Tira um snapshot manual do torneio atual.")
    @app_commands.default_permissions(administrator=True)
    async def torneio_snapshot_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        
        success = await self.take_snapshot()
        if success:
            await interaction.followup.send("✅ Snapshot do torneio salvo com sucesso!")
        else:
            await interaction.followup.send("⚠️ Snapshot já existe para este torneio ou erro ao salvar.")

    @tasks.loop(hours=1)
    async def snapshot_task(self):
        if self.bot.maintenance_mode or self.tournament_snapshots is None:
            return
        
        now = datetime.datetime.now(pytz.utc)
        tournament_id = now.strftime("%Y-W%V")
        
        existing = await self.tournament_snapshots.find_one({"_id": tournament_id})
        if not existing:
            logger.info(f"Novo torneio detectado ({tournament_id}), tirando snapshot...")
            await self.take_snapshot()

    @snapshot_task.before_loop
    async def before_snapshot(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(300)

    @tasks.loop(hours=1)
    async def end_check_task(self):
        if self.bot.maintenance_mode or not getattr(self.bot, 'tournament_summary_channel_id', None):
            return
        
        now_br = datetime.datetime.now(pytz.timezone("America/Sao_Paulo"))
        if now_br.weekday() == 0 and now_br.hour == 8:
            logger.info("Fim de torneio detectado, gerando resumo...")
            try:
                embed = await self.generate_tournament_summary()
                if embed:
                    channel = self.bot.get_channel(self.bot.tournament_summary_channel_id) or await self.bot.fetch_channel(self.bot.tournament_summary_channel_id)
                    if channel:
                        await channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Erro ao gerar resumo do torneio: {e}", exc_info=True)

    @end_check_task.before_loop
    async def before_end_check(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(600)

async def setup(bot: commands.Bot):
    await bot.add_cog(TournamentCog(bot))
