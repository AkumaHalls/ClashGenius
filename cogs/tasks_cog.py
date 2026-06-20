# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import geniuslib as coc
from geniuslib.formatters import format_th
import asyncio
import datetime
import pytz
from typing import Dict, Any, Optional

try:
    from cogs.post_war_analysis import create_post_war_analysis_embed
except ImportError:
    create_post_war_analysis_embed = None
    logger = logging.getLogger("tasks_cog")
    logger.error("Falha ao importar create_post_war_analysis_embed de cogs.post_war_analysis")
except Exception:
    create_post_war_analysis_embed = None

logger = logging.getLogger("tasks_cog")

class TasksCog(commands.Cog, name="Tarefas em Segundo Plano"):
    """Cog para gerir todas as tarefas que rodam em segundo plano."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.last_prediction_sent_time = None
        self.tasks_started = False
        logger.info("TasksCog __init__ concluído.")

    async def cog_load(self):
        logger.info("Iniciando cog_load para TasksCog...")
        logger.info("cog_load para TasksCog concluído (tasks serão iniciadas após 'on_ready').")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.tasks_started:
            logger.info("TasksCog: Evento on_ready recebido. Iniciando tasks...")
            try:
                await asyncio.wait_for(self.bot.db_ready.wait(), timeout=30.0)
                await asyncio.wait_for(self.bot.coc_client_ready.wait(), timeout=60.0) 

                if not self.check_war_end_task.is_running(): self.check_war_end_task.start()
                if not self.donation_snapshot_task.is_running(): self.donation_snapshot_task.start()
                if not self.cleanup_old_snapshots_task.is_running(): self.cleanup_old_snapshots_task.start()
                if not self.check_api_status_task.is_running(): self.check_api_status_task.start()
                if not self.check_cwl_end_task.is_running(): self.check_cwl_end_task.start()

                self.tasks_started = True
                logger.info("TasksCog: Todas as tasks verificadas/iniciadas.")
            except asyncio.TimeoutError:
                 logger.critical("TasksCog: Timeout esperando DB ou CoC estarem prontos no listener on_ready. Tasks podem não iniciar.")
            except Exception as e:
                 logger.critical(f"TasksCog: Erro fatal ao iniciar tasks no listener on_ready: {e}", exc_info=True)


    def cog_unload(self):
        logger.info("Descarregando TasksCog e cancelando tasks...")
        if self.check_war_end_task.is_running(): self.check_war_end_task.cancel()
        if self.donation_snapshot_task.is_running(): self.donation_snapshot_task.cancel()
        if self.cleanup_old_snapshots_task.is_running(): self.cleanup_old_snapshots_task.cancel()
        if self.check_api_status_task.is_running(): self.check_api_status_task.cancel()
        if self.check_cwl_end_task.is_running(): self.check_cwl_end_task.cancel()
        self.tasks_started = False
        logger.info("Tasks canceladas.")

    # --- Tarefas de Doações ---
    @tasks.loop(hours=1)
    async def donation_snapshot_task(self):
        if self.bot.maintenance_mode or self.db is None: return
        logger.info("Executando snapshot de doações...")
        try:
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            if not clan:
                logger.warning("Snapshot de doações: Não foi possível obter dados do clã.")
                return

            snapshot_members = [{"tag": m.tag, "name": m.name, "donations": m.donations, "received": m.received} for m in clan.members]
            snapshot_doc = {"timestamp": datetime.datetime.now(pytz.utc), "clan_tag": self.bot.clan_tag, "members": snapshot_members}
            await self.db.donation_snapshots.insert_one(snapshot_doc)
            logger.info(f"Snapshot de doações para {len(snapshot_members)} membros salvo com sucesso.")
        except Exception as e:
            logger.error(f"Erro na tarefa de snapshot de doações: {e}", exc_info=True)


    @tasks.loop(hours=24)
    async def cleanup_old_snapshots_task(self):
        if self.bot.maintenance_mode or self.db is None: return
        logger.info("Executando limpeza de snapshots antigos...")
        eight_days_ago = datetime.datetime.now(pytz.utc) - datetime.timedelta(days=8)
        try:
            result = await self.db.donation_snapshots.delete_many({"timestamp": {"$lt": eight_days_ago}})
            if result.deleted_count > 0:
                logger.info(f"Limpeza de snapshots: {result.deleted_count} registros antigos removidos.")
            else:
                logger.info("Limpeza de snapshots: Nenhum registro antigo encontrado para remover.")
        except Exception as e:
            logger.error(f"Erro ao limpar snapshots antigos: {e}", exc_info=True)


    # --- Tarefa de Fim de Guerra ---
    async def _send_log_embed(self, embed_to_log: discord.Embed, content: str = None, target_channel_id: int = None):
        if self.bot.maintenance_mode: return
        channel_id_to_use = target_channel_id if target_channel_id else self.bot.channel_id
        if not channel_id_to_use:
            logger.warning("Tentativa de enviar embed, mas channel_id não configurado.")
            return
        try:
            channel = self.bot.get_channel(channel_id_to_use) or await self.bot.fetch_channel(channel_id_to_use)
            now_in_timezone = datetime.datetime.now(self.bot.timezone)
            embed_to_log.set_footer(text=f"Bot: {self.bot.user.name} | v{self.bot.bot_version} • {now_in_timezone.strftime('%d/%m/%Y %H:%M')}")
            embed_to_log.timestamp = now_in_timezone
            await channel.send(content=content, embed=embed_to_log)
        except (discord.NotFound, discord.Forbidden):
             logger.error(f"Erro ao enviar embed para o canal {channel_id_to_use}: Canal não encontrado ou sem permissão.")
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar embed para o canal {channel_id_to_use}: {e}", exc_info=True)

    def _get_war_id(self, war: coc.ClanWar) -> str:
        if hasattr(war, 'tag') and war.tag and war.tag != '#0': return war.tag
        if hasattr(war, 'preparation_start_time') and war.preparation_start_time and hasattr(war.preparation_start_time, 'time'): return war.preparation_start_time.time.isoformat()
        if hasattr(war, 'end_time') and war.end_time and hasattr(war.end_time, 'time'): return war.end_time.time.isoformat()
        fallback_time = datetime.datetime.now(pytz.utc).isoformat()
        opp_tag = getattr(getattr(war, 'opponent', None), 'tag', 'no_opp')
        return f"unknown_{opp_tag}_{fallback_time}"

    async def _scan_war_log_for_missed(self):
        """Varre o war log como fallback para guerras que o get_current_war perdeu."""
        try:
            war_log = await self.bot.api_client.get_war_log(self.bot.clan_tag)
            if not war_log: return
            now = datetime.datetime.now(pytz.utc)
            for entry in war_log[:5]:
                if entry.state == coc.WarState.war_ended and entry.end_time and entry.end_time.time:
                    end_utc = entry.end_time.time.replace(tzinfo=pytz.utc)
                    if (now - end_utc).total_seconds() > 7200:
                        continue
                    war_id = self._get_war_id(entry)
                    if war_id in self.bot.processed_war_ids:
                        continue
                    if not entry.clan or not entry.opponent:
                        continue
                    if entry.clan.tag != self.bot.clan_tag and entry.opponent.tag != self.bot.clan_tag:
                        continue
                    logger.info(f"_scan_war_log_for_missed: Guerra perdida encontrada! ID: {war_id}")
                    war_result = coc.get_war_result(entry, self.bot.clan_tag)
                    missed_count = coc.count_missed_attacks(entry, self.bot.clan_tag)
                    opp = entry.opponent if entry.clan.tag == self.bot.clan_tag else entry.clan
                    our_clan = entry.clan if entry.clan.tag == self.bot.clan_tag else entry.opponent
                    embed = discord.Embed(
                        title=f"🚩 Ataques Perdidos (Recuperado do Histórico)",
                        color=discord.Color.dark_gold()
                    )
                    embed.add_field(name="Placar Final", value=f"**{our_clan.name}:** {our_clan.stars}⭐\n**{opp.name}:** {opp.stars}⭐", inline=False)
                    embed.add_field(name="Resultado", value=f"**{war_result.upper()}**", inline=False)
                    missed_members = [m for m in our_clan.members if len(m.attacks) < (entry.attacks_per_member or 1)]
                    if missed_members:
                        lines = [f"**{m.name}** ({m.tag}): {(entry.attacks_per_member or 1) - len(m.attacks)} perdido(s)" for m in missed_members]
                        embed.add_field(name="Jogadores com Ataques Pendentes", value="\n".join(lines), inline=False)
                    role_mention = f"<@&{self.bot.role_id_missed_attack}>" if self.bot.role_id_missed_attack else ""
                    await self._send_log_embed(embed, content=f"{role_mention} Alerta!", target_channel_id=self.bot.post_war_analysis_channel_id)
                    self.bot.processed_war_ids.add(war_id)
        except Exception as e:
            logger.debug(f"_scan_war_log_for_missed: {e}")

    async def process_ended_war(self, war: coc.ClanWar, war_id: str) -> bool:
        """Processa uma guerra finalizada, salva no DB, envia alertas e adiciona à watchlist."""
        try:
            war_type = "CWL" if war.is_cwl else "Normal"
            our_clan_in_war = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            opponent_clan_in_war = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
            opponent_name = opponent_clan_in_war.name if opponent_clan_in_war else "Desconhecido"
            war_end_time_utc = war.end_time.time.replace(tzinfo=pytz.utc) if war.end_time and war.end_time.time else datetime.datetime.now(pytz.utc)
            logger.info(f"Processando guerra ({war_type}) contra {opponent_name} (ID: {war_id})...")

            war_result = coc.get_war_result(war, self.bot.clan_tag)
            missed_count = coc.count_missed_attacks(war, self.bot.clan_tag)

            db_cog = self.bot.get_cog("Banco de Dados")
            web_api_cog = self.bot.get_cog("Web API")

            if db_cog and web_api_cog:
                war_details_for_db = await web_api_cog.format_war_details_for_web(war)
                if 'error' not in war_details_for_db:
                    await db_cog.save_war_to_history(war_details_for_db, war_id)
                    if create_post_war_analysis_embed:
                        verdict_channel = self.bot.post_war_verdict_channel_id or self.bot.post_war_analysis_channel_id
                        if verdict_channel:
                            analysis_embed = create_post_war_analysis_embed(war_details_for_db)
                            if analysis_embed: await self._send_log_embed(analysis_embed, target_channel_id=verdict_channel)
                    if not create_post_war_analysis_embed:
                         logger.error("Função create_post_war_analysis_embed não disponível.")
                else: logger.error(f"Falha ao obter detalhes da guerra {war_id} para salvar no DB: {war_details_for_db['error']}.")
            else: logger.error("DB Cog ou Web API Cog não encontrados para processar fim de guerra.")

            if missed_count > 0:
                missed_members = [m for m in our_clan_in_war.members if len(m.attacks) < (war.attacks_per_member or 1)]
                missed_lines = [f"**{m.name}** ({m.tag}) ({format_th(m.town_hall)}): {(war.attacks_per_member or 1) - len(m.attacks)} perdido(s)" for m in missed_members]
                embed = discord.Embed(title="🚩 Relatório de Ataques Perdidos", color=discord.Color.dark_gold())
                embed.add_field(name="Placar Final", value=f"**{our_clan_in_war.name}:** {our_clan_in_war.stars}⭐\n**{opponent_clan_in_war.name}:** {opponent_clan_in_war.stars}⭐", inline=False)
                embed.add_field(name="Resultado", value=f"**{war_result.upper()}**", inline=True)
                if missed_members:
                    embed.add_field(name="Jogadores com Ataques Pendentes", value="\n".join(missed_lines), inline=False)
                if opponent_clan_in_war.badge: embed.set_thumbnail(url=opponent_clan_in_war.badge.url)
                role_mention = f"<@&{self.bot.role_id_missed_attack}>" if self.bot.role_id_missed_attack else ""
                await self._send_log_embed(embed, content=f"{role_mention} Atenção!", target_channel_id=self.bot.post_war_analysis_channel_id)

                watchlist_cog = self.bot.get_cog("Lista de Observação")
                if watchlist_cog and self.bot.auto_add_watchlist_enabled:
                    logger.info(f"Adicionando {len(missed_members)} membros à watchlist automaticamente...")
                    for member in missed_members:
                        await watchlist_cog.add_to_watchlist( 
                            player_tag=member.tag,
                            player_name=member.name,
                            reason=f"{(war.attacks_per_member or 1) - len(member.attacks)} ataque(s) perdido(s) vs {opponent_name}",
                            details=f"Guerra terminada em {war_end_time_utc.strftime('%d/%m/%Y')}"
                        )
                    logger.info("Membros adicionados à watchlist.")
                elif not watchlist_cog:
                    logger.warning("WatchlistCog não carregada ao processar fim de guerra, não foi possível adicionar membros automaticamente.")
                elif not self.bot.auto_add_watchlist_enabled:
                    logger.info("Adição automática à watchlist desabilitada.")
            else:
                logger.info(f"check_war_end_task: Nenhum membro com ataque perdido na guerra {war_id}.")

            logger.info(f"Processamento da guerra {war_id} contra {opponent_name} concluído.")
            return True
        except Exception as e:
            logger.error(f"Erro crítico ao processar guerra {war_id}: {e}", exc_info=True)
            return False

    @tasks.loop(seconds=60.0)
    async def check_war_end_task(self):
        if self.bot.maintenance_mode: return
        if not self.bot.api_client or not self.bot.coc_client_ready.is_set():
             logger.debug("check_war_end_task: Pulando execução - Cliente CoC não está pronto.")
             return

        wars_to_check = []
        try:
            current_war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if current_war:
                is_our_war = current_war.clan.tag == self.bot.clan_tag or current_war.opponent.tag == self.bot.clan_tag
                if is_our_war: wars_to_check.append(current_war)
        except coc.PrivateWarLog: pass
        except coc.NotFound: pass
        except Exception as e: logger.error(f"check_war_end_task: Erro ao buscar guerra atual: {e}", exc_info=True)

        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if cwl_group:
                for round_tags in cwl_group.rounds:
                    for war_tag in round_tags:
                        if war_tag == '#0': continue
                        try:
                            cwl_war = await self.bot.api_client.get_league_war(war_tag)
                            is_our_cwl_war = cwl_war.clan.tag == self.bot.clan_tag or cwl_war.opponent.tag == self.bot.clan_tag
                            if is_our_cwl_war: wars_to_check.append(cwl_war)
                        except coc.NotFound: continue
                        except Exception as inner_e: logger.error(f"check_war_end_task: Erro ao buscar guerra CWL específica {war_tag}: {inner_e}")
        except coc.NotFound: pass
        except Exception as e: logger.error(f"check_war_end_task: Erro ao buscar grupo de CWL: {e}", exc_info=True)

        if not wars_to_check:
            await self._scan_war_log_for_missed()
            return

        now = datetime.datetime.now(pytz.utc)
        processed_in_this_run = 0
        for war in wars_to_check:
            try:
                if not war or not hasattr(war, 'clan') or not hasattr(war, 'opponent') or not war.clan or not war.opponent:
                    logger.warning("check_war_end_task: Guerra encontrada com dados incompletos. Pulando.")
                    continue
                is_our_war = war.clan.tag == self.bot.clan_tag or war.opponent.tag == self.bot.clan_tag
                if not is_our_war: continue
                war_ended_by_state = war.state == coc.WarState.war_ended
                end_time_utc = war.end_time.time.replace(tzinfo=pytz.utc) if war.end_time and war.end_time.time else None
                war_ended_by_time = end_time_utc is not None and now > end_time_utc
                if not war_ended_by_state and not war_ended_by_time: continue
                unique_war_id = self._get_war_id(war)
                if unique_war_id in self.bot.processed_war_ids: continue
                process_reason = "estado 'warEnded'" if war_ended_by_state else "tempo expirado"
                logger.info(f"check_war_end_task: Nova guerra terminada ({process_reason}) encontrada (ID: {unique_war_id}). Estado API: {war.state}")
                if await self.process_ended_war(war, unique_war_id):
                    self.bot.processed_war_ids.add(unique_war_id)
                    processed_in_this_run += 1
                    logger.info(f"check_war_end_task: Guerra {unique_war_id} adicionada às processadas.")
                else: logger.error(f"check_war_end_task: Falha ao processar a guerra {unique_war_id}.")
            except Exception as e:
                war_identifier = self._get_war_id(war) if war else "desconhecida"
                logger.error(f"check_war_end_task: Erro ao verificar/processar guerra específica ({war_identifier}): {e}", exc_info=True)
        if processed_in_this_run > 0:
             logger.info(f"check_war_end_task: {processed_in_this_run} guerra(s) terminada(s) processada(s) nesta execução.")
        else:
             logger.debug("check_war_end_task: Nenhuma guerra terminada nova encontrada nesta execução.")


    @commands.command(name='syncwar')
    @commands.has_permissions(administrator=True)
    async def sync_war(self, ctx: commands.Context):
        """(Admin) Força a execução da verificação de fim de guerra."""
        await ctx.message.add_reaction("🔄")
        logger.info(f"Comando !syncwar invocado por {ctx.author.name}.")
        try:
            await self.check_war_end_task.coro(self) 
            await ctx.send("✅ Sincronização de fim de guerra forçada concluída.")
        except Exception as e:
            logger.error(f"Erro no comando !syncwar: {e}", exc_info=True)
            await ctx.send(f"❌ Erro crítico durante a sincronização forçada: {e}")
        finally:
             try: await ctx.message.remove_reaction("🔄", self.bot.user)
             except discord.errors.NotFound: pass


    # --- Tarefa de Fim de CWL ---
    @tasks.loop(minutes=15)
    async def check_cwl_end_task(self):
        if self.bot.maintenance_mode: return
        if not self.bot.api_client or not self.bot.coc_client_ready.is_set():
            return
        capital_cog = self.bot.get_cog("Monitoramento da Capital")
        if capital_cog:
            await capital_cog.check_cwl_end()

    @check_cwl_end_task.before_loop
    async def before_cwl_end(self):
        await self.bot.wait_until_ready()
        await self.bot.db_ready.wait()
        await self.bot.coc_client_ready.wait()

    # --- Tarefa de Status da API ---
    @tasks.loop(minutes=1)
    async def check_api_status_task(self):
        if self.bot.maintenance_mode or not self.bot.coc_client_ready.is_set():
            logger.debug("check_api_status_task: Pulando execução - Manutenção ou Cliente CoC não pronto.")
            return

        try:
            current_status = "error"
            status_message = "Desconhecido"

            # O Módulo de Tarefas agora verifica a API por conta própria, sem depender do AdminCog!
            if not self.bot.api_client:
                current_status = "error"
                status_message = "Cliente CoC não inicializado."
            else:
                try:
                    await self.bot.api_client.get_clan(self.bot.clan_tag)
                    current_status = "ok"
                    status_message = "API CoC Online"
                except coc.Maintenance:
                    current_status = "maintenance"
                    status_message = "Os servidores do Clash of Clans estão em manutenção."
                except coc.NotFound:
                    current_status = "error"
                    status_message = "Clã não encontrado (Tag inválida?)."
                except coc.LoginError:
                    current_status = "error"
                    status_message = "Erro de login na API da Supercell."
                except Exception as e:
                    current_status = "error"
                    status_message = f"Falha na comunicação: {str(e)}"

            if current_status != self.bot.last_api_status:
                logger.info(f"Status API CoC mudou: '{self.bot.last_api_status}' -> '{current_status}'. Notificando.")
                if current_status == "maintenance" or current_status == "error":
                    embed_color = discord.Color.orange()
                    title = "🚨 Alerta API Supercell 🚨"
                    description = "Acesso à API Clash of Clans instável/manutenção."
                    impact = "**Painel Web:** Indisponível.\n**Alertas Discord:** Podem ser afetados."
                else: 
                    embed_color = discord.Color.green()
                    title = "✅ API Supercell Operacional"
                    description = "API Clash of Clans voltou ao normal."
                    impact = "**Painel Web:** Acesso restaurado.\n**Alertas Discord:** Normais."

                embed = discord.Embed(title=title, description=description, color=embed_color)
                embed.add_field(name="Motivo", value=status_message, inline=False)
                embed.add_field(name="Impacto", value=impact, inline=False)
                
                await self._send_log_embed(embed, target_channel_id=self.bot.channel_id)
                self.bot.last_api_status = current_status
            else:
                 logger.debug(f"check_api_status_task: Status API CoC permaneceu '{current_status}'.")

        except Exception as e:
            logger.error(f"Erro na tarefa check_api_status_task: {e}", exc_info=True)


    # --- Funções before_loop ---
    @check_war_end_task.before_loop
    @donation_snapshot_task.before_loop
    @cleanup_old_snapshots_task.before_loop
    @check_api_status_task.before_loop
    async def before_tasks_start(self):
        """Espera o bot, DB e CoC estarem prontos antes de iniciar as tasks."""
        logger.debug(f"before_tasks_start: Aguardando on_ready...")
        await self.bot.wait_until_ready()
        logger.debug(f"before_tasks_start: Aguardando db_ready...")
        await self.bot.db_ready.wait()
        logger.debug(f"before_tasks_start: Aguardando coc_client_ready...")
        await self.bot.coc_client_ready.wait()
        logger.debug(f"before_tasks_start: Todas as dependências prontas. Task pode iniciar.")


async def setup(bot: commands.Bot):
     logger.info("Configurando TasksCog...")
     try:
         await bot.add_cog(TasksCog(bot))
         logger.info("TasksCog adicionado com sucesso.")
     except Exception as e:
         logger.critical(f"### ERRO FATAL AO ADICIONAR TASKSCOG ###: {e}", exc_info=True)
