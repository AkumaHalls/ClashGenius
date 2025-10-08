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
        logger.info("Tarefas em segundo plano iniciadas.")

    async def cog_unload(self):
        self.check_war_end_task.cancel()
        self.daily_player_data_snapshot.cancel()
        self.send_online_status_task.cancel()
        self.post_war_prediction_task.cancel()

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
        """Gera um ID único e consistente para uma guerra."""
        if hasattr(war, 'tag') and war.tag and war.tag != '#0':
            return war.tag
        if hasattr(war, 'preparation_start_time') and war.preparation_start_time and hasattr(war.preparation_start_time, 'time'):
            return war.preparation_start_time.time.isoformat()
        return war.end_time.time.isoformat()

    async def process_ended_war(self, war: coc.ClanWar, war_id: str):
        """Função centralizada para processar uma guerra finalizada."""
        war_type = "CWL" if war.is_cwl else "Normal"
        
        # A API retorna o objeto do nosso clã em 'clan' ou 'opponent'. Precisamos identificá-lo.
        our_clan_in_war = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
        opponent_clan_in_war = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
        
        opponent_name = opponent_clan_in_war.name if opponent_clan_in_war else "Desconhecido"
        
        logger.info(f"A processar guerra ({war_type}) contra {opponent_name} (ID: {war_id})...")
        
        db_cog = self.bot.get_cog("Banco de Dados")
        if db_cog:
            # CORREÇÃO: Para garantir que os dados salvos são da guerra correta,
            # passamos a guerra específica para a função de formatação.
            war_details_for_db = await self.bot.format_war_details_for_web(war)
            
            if 'error' not in war_details_for_db:
                await db_cog.save_war_to_history(war_details_for_db, war_id)
                
                if self.bot.post_war_analysis_channel_id:
                    logger.info("A gerar a análise pós-guerra...")
                    analysis_embed = create_post_war_analysis_embed(war_details_for_db)
                    if analysis_embed:
                        await self._send_log_embed(analysis_embed, target_channel_id=self.bot.post_war_analysis_channel_id)
                        logger.info("Análise pós-guerra enviada com sucesso.")
            else:
                 logger.error(f"Falha ao obter detalhes da guerra para salvar no DB: {war_details_for_db['error']}.")
        else:
            logger.warning("Cog de Banco de Dados não encontrado. A guerra não será salva no histórico.")

        missed = [f"**{m.name}** (CV{m.town_hall}): {war.attacks_per_member - len(m.attacks)} perdido(s)" for m in our_clan_in_war.members if len(m.attacks) < war.attacks_per_member]
        if missed:
            embed = discord.Embed(title="🚩 Relatório de Ataques Perdidos", color=discord.Color.dark_gold())
            embed.add_field(name="Placar Final", value=f"**{our_clan_in_war.name}:** {our_clan_in_war.stars}⭐\n**{opponent_clan_in_war.name}:** {opponent_clan_in_war.stars}⭐", inline=False)
            embed.add_field(name="Jogadores com Ataques Pendentes", value="\n".join(missed), inline=False)
            if opponent_clan_in_war.badge: embed.set_thumbnail(url=opponent_clan_in_war.badge.url)
            role_mention = f"<@&{self.bot.role_id_missed_attack}>" if self.bot.role_id_missed_attack else ""
            await self._send_log_embed(embed, content=f"{role_mention} Atenção!")
            logger.info("Relatório de ataques perdidos enviado.")
        
        logger.info(f"Processamento da guerra contra {opponent_name} concluído.")
        return True

    @tasks.loop(seconds=60.0)
    async def check_war_end_task(self):
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()
        
        if not self.bot.api_client: return
        
        try:
            wars_to_check = []

            # 1. Coleta a guerra normal se existir
            try:
                current_war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
                if current_war:
                    wars_to_check.append(current_war)
            except (coc.PrivateWarLog, coc.NotFound):
                pass

            # 2. Coleta as guerras da CWL se o clã estiver em uma
            try:
                cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
                if cwl_group:
                    for war_tag in cwl_group.get_war_tags(self.bot.clan_tag):
                        if war_tag == '#0': continue
                        try:
                            cwl_war = await self.bot.api_client.get_league_war(war_tag)
                            wars_to_check.append(cwl_war)
                        except coc.NotFound:
                            logger.warning(f"Não foi possível encontrar a guerra da CWL com a tag: {war_tag}")
                            continue
            except coc.NotFound:
                pass
            
            if not wars_to_check:
                return

            # 3. Itera sobre a lista consolidada de guerras
            for war in wars_to_check:
                # VALIDAÇÃO CRÍTICA: Verifica se nosso clã está na guerra e se a guerra terminou
                is_our_war = war.clan.tag == self.bot.clan_tag or war.opponent.tag == self.bot.clan_tag
                if not is_our_war:
                    logger.debug(f"Guerra {war.clan.name} vs {war.opponent.name} ignorada, não é do nosso clã.")
                    continue

                if war.state != 'warEnded':
                    continue

                unique_war_id = self._get_war_id(war)
                
                if unique_war_id not in self.bot.processed_war_ids:
                    logger.info(f"Nova guerra terminada encontrada para processar (ID: {unique_war_id}).")
                    if await self.process_ended_war(war, unique_war_id):
                        self.bot.processed_war_ids.add(unique_war_id)
                else:
                    logger.debug(f"Guerra {unique_war_id} já processada, ignorando.")

        except Exception as e:
            logger.error(f"Erro inesperado na task de fim de guerra: {e}", exc_info=True)


    @commands.command(name='syncwar')
    @commands.has_permissions(administrator=True)
    async def sync_war(self, ctx: commands.Context):
        """Força a sincronização e o relatório da última guerra terminada."""
        await ctx.message.add_reaction("🔄")
        await self.bot.coc_client_ready.wait()
        
        logger.info(f"Comando !syncwar invocado por {ctx.author.name}.")
        try:
            await self.check_war_end_task.coro(self)
            await ctx.send("✅ Sincronização forçada concluída. Verifique os canais de relatório.")
        except Exception as e:
            logger.error(f"Erro no comando !syncwar: {e}", exc_info=True)
            await ctx.send(f"❌ Erro crítico: {e}")
        finally:
            await ctx.message.remove_reaction("🔄", self.bot.user)

    @tasks.loop(minutes=10)
    async def post_war_prediction_task(self):
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()
        
        if self.bot.maintenance_mode or not self.bot.ai_log_channel_id or not self.bot.api_client:
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
