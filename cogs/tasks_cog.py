# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
import datetime
from typing import Dict, Any

from cogs.post_war_analysis import create_post_war_analysis_embed

logger = logging.getLogger("tasks_cog")

class TasksCog(commands.Cog, name="Tarefas em Segundo Plano"):
    """Cog para gerenciar todas as tarefas que rodam em segundo plano."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.last_war_end_time: datetime.datetime = None
        self.last_prediction_sent_time = None

    async def cog_load(self):
        self.check_war_end_task.start()
        self.daily_player_data_snapshot.start()
        self.send_online_status_task.start()
        self.post_war_prediction_task.start()
        logger.info("Tarefas em segundo plano iniciadas.")

    async def cog_unload(self):
        self.check_war_end_task.cancel()
        self.daily_player_data_snapshot.cancel()
        self.send_online_status_task.cancel()
        self.post_war_prediction_task.cancel()

    async def _send_log_embed(self, embed_to_log: discord.Embed, content: str = None, target_channel_id: int = None):
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

    async def process_ended_war(self, war: coc.ClanWar):
        """Função centralizada para processar uma guerra finalizada."""
        logger.info(f"A processar guerra ({'CWL' if war.is_cwl else 'Normal'}) contra {war.opponent.name}...")
        
        # Usamos force_api_call=True para garantir que pegamos os dados mais recentes para o relatório
        war_details = await self.bot.fetch_current_war_details_for_web(force_api_call=True)
        if 'error' in war_details:
            logger.error(f"Falha ao obter detalhes da guerra: {war_details['error']}.")
            return False

        db_cog = self.bot.get_cog("Banco de Dados")
        if db_cog:
            await db_cog.save_war_to_history(war_details)
        else:
            logger.warning("Cog de Banco de Dados não encontrado. A guerra não será salva no histórico.")

        if self.bot.post_war_analysis_channel_id:
            logger.info("A gerar a análise pós-guerra...")
            analysis_embed = create_post_war_analysis_embed(war_details)
            if analysis_embed:
                await self._send_log_embed(analysis_embed, target_channel_id=self.bot.post_war_analysis_channel_id)
                logger.info("Análise pós-guerra enviada com sucesso.")
            else:
                logger.warning("A análise pós-guerra resultou num embed nulo e não foi enviada.")
        
        our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
        missed = [f"**{m.name}** (CV{m.town_hall}): {war.attacks_per_member - len(m.attacks)} perdido(s)" for m in our_clan.members if len(m.attacks) < war.attacks_per_member]
        if missed:
            embed = discord.Embed(title="🚩 Relatório de Ataques Perdidos", color=discord.Color.dark_gold())
            embed.add_field(name="Placar Final", value=f"**{war.clan.name}:** {war.clan.stars}⭐\n**{war.opponent.name}:** {war.opponent.stars}⭐", inline=False)
            embed.add_field(name="Jogadores com Ataques Pendentes", value="\n".join(missed), inline=False)
            if war.opponent.badge: embed.set_thumbnail(url=war.opponent.badge.url)
            role_mention = f"<@&{self.bot.role_id_missed_attack}>" if self.bot.role_id_missed_attack else ""
            await self._send_log_embed(embed, content=f"{role_mention} Atenção!")
            logger.info("Relatório de ataques perdidos enviado.")
        
        logger.info(f"Processamento da guerra contra {war.opponent.name} concluído.")
        return True

    @tasks.loop(seconds=60.0)
    async def check_war_end_task(self):
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait() # Garante que o cliente CoC está logado
        
        # CORREÇÃO: Usa self.bot.api_client que é a referência correta e atualizada
        if not self.bot.api_client: return
        
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            
            if war and war.state == 'warEnded' and hasattr(war, 'end_time'):
                if self.last_war_end_time is None or war.end_time.time > self.last_war_end_time:
                    if await self.process_ended_war(war):
                        self.last_war_end_time = war.end_time.time

        except (coc.PrivateWarLog, coc.NotFound):
            pass
        except Exception as e:
            logger.error(f"Erro inesperado na task de fim de guerra: {e}", exc_info=True)

    @commands.command(name='syncwar')
    @commands.has_permissions(administrator=True)
    async def sync_war(self, ctx: commands.Context):
        """Força a sincronização e o relatório da última guerra terminada."""
        await ctx.message.add_reaction("🔄")
        await self.bot.coc_client_ready.wait() # Garante que o cliente CoC está logado
        
        logger.info(f"Comando !syncwar invocado por {ctx.author.name}.")
        try:
            # CORREÇÃO: Usa self.bot.api_client
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if war and war.state == 'warEnded':
                if await self.process_ended_war(war):
                    self.last_war_end_time = war.end_time.time
                    await ctx.send("✅ Sincronização da guerra concluída com sucesso! Relatórios enviados.")
                else:
                    await ctx.send("⚠️ Ocorreu um erro ao processar a guerra. Verifique os logs.")
            else:
                await ctx.send("ℹ️ Nenhuma guerra terminada encontrada para sincronizar no momento.")
        except coc.NotFound:
            await ctx.send("ℹ️ Nenhuma guerra (normal ou CWL) encontrada.")
        except Exception as e:
            logger.error(f"Erro no comando !syncwar: {e}", exc_info=True)
            await ctx.send(f"❌ Erro crítico: {e}")
        finally:
            await ctx.message.remove_reaction("🔄", self.bot.user)

    @tasks.loop(minutes=10)
    async def post_war_prediction_task(self):
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()
        
        if not self.bot.ai_log_channel_id or not self.bot.api_client:
            return
            
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state != 'inWar':
                return

            now = datetime.datetime.now()
            if self.last_prediction_sent_time and (now - self.last_prediction_sent_time).total_seconds() < 25 * 60:
                return

            logger.info("A gerar 'pensamento' da IA sobre a guerra atual.")
            prediction = await self.bot.war_prediction_system.predict_war_outcome(war, self.bot.clan_tag)

            if "error" in prediction:
                logger.warning(f"IA não conseguiu gerar previsão: {prediction['error']}")
                return

            our_clan, opp_clan = (war.clan, war.opponent) if war.clan.tag == self.bot.clan_tag else (war.opponent, war.clan)
            
            embed = discord.Embed(
                title="🧠 Relatório de Análise da IA de Guerra (v3.0)",
                description=f"**{our_clan.name}** vs **{opp_clan.name}**",
                color=discord.Color.purple()
            )
            
            embed.add_field(name="🚨 Situação", value=prediction.get("summary_discord", "N/A"), inline=False)
            embed.add_field(name="Probabilidade de Vitória", value=f"**{prediction.get('probability', 0.0):.1f}%**", inline=True)
            embed.add_field(name="Confiança da IA", value=f"{prediction.get('confidence', 0.0):.1f}%", inline=True)
            embed.add_field(name="Método de Análise", value=prediction.get("analysis_log", {}).get("method", "N/A"), inline=True)

            if prediction.get("tactical_insights"):
                insights = "• " + "\n• ".join(prediction["tactical_insights"])
                embed.add_field(name="💡 Insights Táticos", value=insights, inline=False)
            
            if prediction.get("risk_factors"):
                risks = "• " + "\n• ".join(prediction["risk_factors"])
                embed.add_field(name="⚠️ Fatores de Risco", value=risks, inline=False)
            
            features = prediction.get("analysis_log", {}).get("features", {})
            metrics_str = (
                f"**Star Diff:** `{features.get('star_difference', 0):.2f}`\n"
                f"**Destr Diff:** `{features.get('destruction_difference', 0):.2f}%`\n"
                f"**Atk Rem Diff:** `{features.get('attacks_remaining_difference', 0)}`\n"
                f"**Momentum:** `{features.get('momentum_indicator', 0):.2f}`\n"
                f"**Synergy:** `{features.get('clan_synergy_score', 0):.2f}`\n"
                f"**Pressure:** `{features.get('pressure_index', 0):.2f}`"
            )
            embed.add_field(name="📊 Métricas Chave Analisadas", value=metrics_str, inline=False)
            
            if opp_clan.badge:
                embed.set_thumbnail(url=opp_clan.badge.url)

            await self._send_log_embed(embed, target_channel_id=self.bot.ai_log_channel_id)
            self.last_prediction_sent_time = now

        except (coc.PrivateWarLog, coc.NotFound):
            pass
        except Exception as e:
            logger.error(f"Erro na tarefa de previsão da IA: {e}", exc_info=True)


    @tasks.loop(hours=24)
    async def daily_player_data_snapshot(self):
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()
        if not self.bot.api_client or self.db is None:
            return
        
        logger.info("Iniciando snapshot diário de dados dos jogadores.")
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            snapshot_time = datetime.datetime.now(self.bot.timezone)
            records = []
            for member in clan.members:
                records.append({
                    "player_tag": member.tag,
                    "trophies": member.trophies,
                    "donations": member.donations,
                    "received": member.received,
                    "timestamp": snapshot_time
                })
            if records:
                await self.db.trophy_history.insert_many(records)
                logger.info(f"Snapshot salvo para {len(records)} jogadores.")
        except Exception as e:
            logger.error(f"Erro na task de snapshot diário: {e}", exc_info=True)

    @tasks.loop(seconds=10, count=1)
    async def send_online_status_task(self):
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()
        if not self.bot.api_client: await asyncio.sleep(5)
        try:
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            embed = discord.Embed(title=f"✅ ClashGenius Online | {clan.name}", description=f"Monitoramento ativado para **{clan.name} ({clan.tag})**.", color=discord.Color.green())
            embed.add_field(name="📊 Status do Clã", value=f"**Membros:** {clan.member_count}/50\n**Troféus:** 🏆 {clan.points}", inline=True)
            embed.add_field(name="⚙️ Status do Bot", value=f"**Versão:** {self.bot.bot_version}\n**API CoC:** ✅ OK", inline=True)
            if clan.badge: embed.set_thumbnail(url=clan.badge.url)
            await self._send_log_embed(embed)
        except Exception as e:
            logger.error(f"Falha ao enviar status online: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TasksCog(bot))

