# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import geniuslib as coc
import pytz
import datetime
from typing import Optional

logger = logging.getLogger("donation_cog")

# CORREÇÃO AQUI: Adicionado `name="Gerenciador de Doações"`
class DonationsCog(commands.Cog, name="Gerenciador de Doações"):
    """Cog para gerir relatórios de doações diários e semanais."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        # Garante que a coleção só é acedida se a BD existir
        self.snapshot_collection = self.db.donation_snapshots if self.db is not None else None
        self.reports_log = self.db.reports_log if self.db is not None else None
        self.post_reports_task.start()

    def cog_unload(self):
        self.post_reports_task.cancel()

    async def get_report_snapshots(self, days_ago: int) -> tuple:
        """Obtém os snapshots necessários para gerar um relatório."""
        if self.snapshot_collection is None:
            return None, None

        now = datetime.datetime.now(pytz.utc)
        
        # Snapshot mais recente (atual)
        latest_snapshot_cursor = self.snapshot_collection.find({}).sort("timestamp", -1).limit(1)
        latest_snapshot = await latest_snapshot_cursor.to_list(length=1)
        if not latest_snapshot:
            return None, None
        
        # Snapshot antigo para comparação
        time_ago = now - datetime.timedelta(days=days_ago)
        
        old_snapshot_cursor = self.snapshot_collection.find(
            {"timestamp": {"$gte": time_ago}}
        ).sort("timestamp", 1).limit(1)
        
        old_snapshot = await old_snapshot_cursor.to_list(length=1)
        if not old_snapshot:
            return None, None

        return latest_snapshot[0], old_snapshot[0]

    async def generate_and_send_report(self, days: int, force: bool = False, interaction: Optional[discord.Interaction] = None):
        """Gera e envia um relatório de doações para um determinado período."""
        period_name = "diário" if days == 1 else "semanal"
        if self.bot.donations_channel_id is None:
            logger.warning("ID do canal de doações não configurado. A saltar o relatório.")
            if interaction:
                await interaction.followup.send("❌ O canal de doações não está configurado.", ephemeral=True)
            return False

        logger.info(f"A gerar relatório de doações (período: {period_name}, forçado: {force})...")
        
        latest_snapshot, old_snapshot = await self.get_report_snapshots(days)
        
        if not latest_snapshot or not old_snapshot:
            warning_msg = f"Nenhum snapshot de {days} dia(s) atrás encontrado para gerar o relatório."
            logger.warning(warning_msg)
            if interaction:
                await interaction.followup.send(f"⚠️ {warning_msg} É necessário esperar que o bot recolha dados suficientes.", ephemeral=True)
            return False

        latest_members = {m['tag']: m for m in latest_snapshot.get('members', [])}
        old_members = {m['tag']: m for m in old_snapshot.get('members', [])}

        donation_data = []
        for tag, member_data in latest_members.items():
            old_data = old_members.get(tag)
            if old_data:
                donated = member_data['donations'] - old_data['donations']
                received = member_data['received'] - old_data['received']
                if donated > 0 or received > 0:
                    donation_data.append({
                        "name": member_data['name'],
                        "donated": donated,
                        "received": received
                    })
        
        donation_data.sort(key=lambda x: x['donated'], reverse=True)
        
        clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
        
        embed = discord.Embed(
            title=f"🏆 Relatório de Doações {period_name.capitalize()}",
            color=discord.Color.gold()
        )
        if clan and clan.badge:
            embed.set_thumbnail(url=clan.badge.url)

        start_date = old_snapshot['timestamp'].astimezone(self.bot.timezone).strftime('%d de %B de %Y %H:%M')
        end_date = latest_snapshot['timestamp'].astimezone(self.bot.timezone).strftime('%d de %B de %Y %H:%M')
        embed.description = f"**Período:** {start_date} - {end_date}"

        if not donation_data:
            embed.add_field(name="Nenhuma Atividade", value="Não houve doações registadas neste período.", inline=False)
        else:
            # Formatação melhorada para alinhamento
            formatted_lines = []
            # Encontra o comprimento máximo para cada coluna para alinhar
            max_donated_len = max(len(str(d['donated'])) for d in donation_data)
            max_received_len = max(len(str(d['received'])) for d in donation_data)

            for player in donation_data:
                donated_str = str(player['donated']).ljust(max_donated_len)
                received_str = str(player['received']).ljust(max_received_len)
                formatted_lines.append(f"`{donated_str} 📤 | {received_str} 📥` - {player['name']}")
            
            # Divide a lista em campos de 10 jogadores cada para evitar exceder o limite do Discord
            field_size = 10
            for i in range(0, len(formatted_lines), field_size):
                chunk = formatted_lines[i:i + field_size]
                field_name = f"Jogadores ({i+1}-{i+len(chunk)})"
                embed.add_field(name=field_name, value="\n".join(chunk), inline=False)

        try:
            channel = self.bot.get_channel(self.bot.donations_channel_id) or await self.bot.fetch_channel(self.bot.donations_channel_id)
            await channel.send(embed=embed)
            logger.info(f"Relatório de doações {period_name} enviado com sucesso.")
            if interaction:
                 await interaction.followup.send(f"✅ Relatório {period_name} enviado com sucesso!", ephemeral=True)
            return True
        except (discord.NotFound, discord.Forbidden) as e:
            logger.error(f"Não foi possível enviar o relatório de doações para o canal {self.bot.donations_channel_id}: {e}")
            if interaction:
                 await interaction.followup.send(f"❌ Erro ao enviar para o canal. Verifique as permissões.", ephemeral=True)
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar relatório de doações: {e}", exc_info=True)
            if interaction:
                 await interaction.followup.send(f"❌ Ocorreu um erro inesperado.", ephemeral=True)
            return False

    @tasks.loop(time=datetime.time(hour=0, minute=1, tzinfo=pytz.timezone('America/Sao_Paulo'))) # 21:01 no Brasil (UTC-3)
    async def post_reports_task(self):
        """Tarefa que posta os relatórios diários e semanais."""
        if self.bot.maintenance_mode: return
        
        await self.generate_and_send_report(days=1)
        
        # Se for domingo, envia o relatório semanal
        today = datetime.datetime.now(self.bot.timezone).weekday()
        if today == 6: # 0=Segunda, 6=Domingo
            await self.generate_and_send_report(days=7)

    @post_reports_task.before_loop
    async def before_post_reports_task(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(DonationsCog(bot))

