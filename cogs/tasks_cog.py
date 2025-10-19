# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
import datetime
import pytz  # Importa a biblioteca de fuso horário
from typing import Dict, Any

from cogs.post_war_analysis import create_post_war_analysis_embed

logger = logging.getLogger("tasks_cog")

class TasksCog(commands.Cog, name="Tarefas em Segundo Plano"):
    """Cog para gerir todas as tarefas que rodam em segundo plano."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.last_prediction_sent_time = None

    async def cog_load(self):
        self.check_war_end_task.start()
        self.daily_player_data_snapshot.start()
        self.send_online_status_task.start()
        self.post_war_prediction_task.start()
        self.donation_snapshot_task.start()
        logger.info("Tarefas em segundo plano iniciadas.")

    async def cog_unload(self):
        self.check_war_end_task.cancel()
        self.daily_player_data_snapshot.cancel()
        self.send_online_status_task.cancel()
        self.post_war_prediction_task.cancel()
        self.donation_snapshot_task.cancel()

    async def _send_log_embed(self, embed_to_log: discord.Embed, content: str = None, target_channel_id: int = None):
        if self.bot.maintenance_mode: return
        channel_id_to_use = target_channel_id or self.bot.channel_id
        if not channel_id_to_use: return
        await self.bot.wait_until_ready()
        try:
            channel = self.bot.get_channel(channel_id_to_use) or await self.bot.fetch_channel(channel_id_to_use)
            now_in_timezone = datetime.datetime.now(self.bot.timezone)
            embed_to_log.set_footer(text=f"Bot: {self.bot.user.name} | v{self.bot.bot_version} • {now_in_timezone.strftime('%d/%m/%Y %H:%M')}")
            embed_to_log.timestamp = now_in_timezone
            await channel.send(content=content, embed=embed_to_log)
        except (discord.NotFound, discord.Forbidden, Exception) as e:
            logger.error(f"Erro ao enviar embed para o canal {channel_id_to_use}: {e}", exc_info=True)

    def _get_war_id(self, war: coc.ClanWar) -> str:
        if hasattr(war, 'tag') and war.tag and war.tag != '#0':
            return war.tag
        if hasattr(war, 'preparation_start_time') and war.preparation_start_time and hasattr(war.preparation_start_time, 'time'):
            return war.preparation_start_time.time.isoformat()
        return war.end_time.time.isoformat()

    async def process_ended_war(self, war: coc.ClanWar, war_id: str):
        war_type = "CWL" if war.is_cwl else "Normal"
        our_clan_in_war = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
        opponent_clan_in_war = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
        
        opponent_name = opponent_clan_in_war.name if opponent_clan_in_war else "Desconhecido"
        logger.info(f"A processar guerra ({war_type}) contra {opponent_name} (ID: {war_id})...")
        
        db_cog = self.bot.get_cog("Banco de Dados")
        web_api_cog = self.bot.get_cog("Web API")
        
        if db_cog and web_api_cog:
            war_details_for_db = await web_api_cog.format_war_details_for_web(war)
            
            if 'error' not in war_details_for_db:
                await db_cog.save_war_to_history(war_details_for_db, war_id)
                
                if self.bot.post_war_analysis_channel_id:
                    analysis_embed = create_post_war_analysis_embed(war_details_for_db)
                    if analysis_embed:
                        await self._send_log_embed(analysis_embed, target_channel_id=self.bot.post_war_analysis_channel_id)
            else:
                 logger.error(f"Falha ao obter detalhes da guerra para salvar no DB: {war_details_for_db['error']}.")

        missed = [f"**{m.name}** (CV{m.town_hall}): {war.attacks_per_member - len(m.attacks)} perdido(s)" for m in our_clan_in_war.members if len(m.attacks) < war.attacks_per_member]
        if missed:
            embed = discord.Embed(title="🚩 Relatório de Ataques Perdidos", color=discord.Color.dark_gold())
            embed.add_field(name="Placar Final", value=f"**{our_clan_in_war.name}:** {our_clan_in_war.stars}⭐\n**{opponent_clan_in_war.name}:** {opponent_clan_in_war.stars}⭐", inline=False)
            embed.add_field(name="Jogadores com Ataques Pendentes", value="\n".join(missed), inline=False)
            if opponent_clan_in_war.badge: embed.set_thumbnail(url=opponent_clan_in_war.badge.url)
            role_mention = f"<@&{self.bot.role_id_missed_attack}>" if self.bot.role_id_missed_attack else ""
            await self._send_log_embed(embed, content=f"{role_mention} Atenção!")
        
        logger.info(f"Processamento da guerra contra {opponent_name} concluído.")
        return True

    @tasks.loop(seconds=60.0)
    async def check_war_end_task(self):
        if not self.bot.api_client: return
        
        try:
            wars_to_check = []
            try:
                current_war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
                if current_war:
                    wars_to_check.append(current_war)
            except (coc.PrivateWarLog, coc.NotFound):
                pass

            try:
                cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
                if cwl_group:
                    for round_tags in cwl_group.rounds:
                        for war_tag in round_tags:
                            if war_tag == '#0': continue
                            try:
                                cwl_war = await self.bot.api_client.get_league_war(war_tag)
                                wars_to_check.append(cwl_war)
                            except coc.NotFound:
                                continue
            except coc.NotFound:
                pass
            
            if not wars_to_check:
                return

            for war in wars_to_check:
                if not war or not hasattr(war, 'clan') or not war.clan: continue
                is_our_war = war.clan.tag == self.bot.clan_tag or war.opponent.tag == self.bot.clan_tag
                if not is_our_war:
                    continue
                
                now = datetime.datetime.now(pytz.utc)
                end_time_utc = war.end_time.time.replace(tzinfo=pytz.utc)
                is_ended_by_time = now > end_time_utc
                
                if war.state != 'warEnded' and not is_ended_by_time:
                    continue

                unique_war_id = self._get_war_id(war)
                if unique_war_id not in self.bot.processed_war_ids:
                    if is_ended_by_time and war.state != 'warEnded':
                        logger.warning(f"Forçando processamento da guerra (ID: {unique_war_id}) baseado no tempo. API state: {war.state}")
                        war.state = 'warEnded'

                    logger.info(f"Nova guerra terminada ({war.state}) encontrada para processar (ID: {unique_war_id}).")
                    if await self.process_ended_war(war, unique_war_id):
                        self.bot.processed_war_ids.add(unique_war_id)

        except Exception as e:
            logger.error(f"Erro inesperado na task de fim de guerra: {e}", exc_info=True)
            
    @check_war_end_task.before_loop
    async def before_check_war_end_task(self):
        """Espera o bot estar pronto antes de iniciar a task."""
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()

    @tasks.loop(hours=1)
    async def donation_snapshot_task(self):
        """Salva um snapshot das doações dos membros a cada hora."""
        if self.bot.maintenance_mode or not self.db:
            return

        logger.info("Executando snapshot de doações...")
        try:
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            if not clan:
                logger.warning("Não foi possível obter dados do clã para o snapshot de doações.")
                return

            members_data = [
                {
                    "tag": member.tag,
                    "name": member.name,
                    "donations": member.donations,
                    "received": member.received
                }
                for member in clan.members
            ]
            
            snapshot_doc = {
                "timestamp": datetime.datetime.now(pytz.utc),
                "members": members_data
            }
            
            await self.db.donation_snapshots.insert_one(snapshot_doc)

            # Limpa snapshots antigos (mantém por ~8 dias)
            cutoff_date = datetime.datetime.now(pytz.utc) - datetime.timedelta(days=8)
            await self.db.donation_snapshots.delete_many({"timestamp": {"$lt": cutoff_date}})

            logger.info(f"Snapshot de doações para {len(members_data)} membros salvo com sucesso.")

        except Exception as e:
            logger.error(f"Erro na tarefa de snapshot de doações: {e}", exc_info=True)
            
    @donation_snapshot_task.before_loop
    async def before_donation_snapshot_task(self):
        """Espera o bot estar pronto antes de iniciar a task."""
        await self.bot.wait_until_ready()
        await self.bot.db_ready.wait()
        await self.bot.coc_client_ready.wait()


    @commands.command(name='syncwar')
    @commands.has_permissions(administrator=True)
    async def sync_war(self, ctx: commands.Context):
        await ctx.message.add_reaction("🔄")
        logger.info(f"Comando !syncwar invocado por {ctx.author.name}.")
        try:
            await self.check_war_end_task.coro(self)
            await ctx.send("✅ Sincronização forçada concluída.")
        except Exception as e:
            logger.error(f"Erro no comando !syncwar: {e}", exc_info=True)
            await ctx.send(f"❌ Erro crítico: {e}")
        finally:
            await ctx.message.remove_reaction("🔄", self.bot.user)

    @tasks.loop(minutes=10)
    async def post_war_prediction_task(self):
        pass
        
    @post_war_prediction_task.before_loop
    async def before_post_war_prediction_task(self):
        """Espera o bot estar pronto antes de iniciar a task."""
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()

    @tasks.loop(hours=24)
    async def daily_player_data_snapshot(self):
        pass

    @daily_player_data_snapshot.before_loop
    async def before_daily_player_data_snapshot(self):
        """Espera o bot estar pronto antes de iniciar a task."""
        await self.bot.wait_until_ready()
        await self.bot.db_ready.wait()
        await self.bot.coc_client_ready.wait()

    @tasks.loop(seconds=10, count=1)
    async def send_online_status_task(self):
        pass
        
    @send_online_status_task.before_loop
    async def before_send_online_status_task(self):
        """Espera o bot estar pronto antes de iniciar a task."""
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(TasksCog(bot))

