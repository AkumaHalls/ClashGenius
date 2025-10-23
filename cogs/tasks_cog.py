# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
import datetime
import pytz
from typing import Dict, Any, Optional

from cogs.post_war_analysis import create_post_war_analysis_embed

logger = logging.getLogger("tasks_cog")

# Tempo máximo de espera para dependências (em segundos)
WAIT_TIMEOUT = 60.0

class TasksCog(commands.Cog, name="Tarefas em Segundo Plano"):
    """Cog para gerir todas as tarefas que rodam em segundo plano."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.last_prediction_sent_time = None
        self.watchlist_cog = None
        logger.info("TasksCog __init__ concluído.")

    async def cog_load(self):
        """Método chamado pelo discord.py após a Cog ser carregada, com timeouts."""
        logger.info("Iniciando cog_load para TasksCog...")
        try:
            logger.info(f"Aguardando bot.wait_until_ready (timeout: {WAIT_TIMEOUT}s)...")
            await asyncio.wait_for(self.bot.wait_until_ready(), timeout=WAIT_TIMEOUT)
            logger.info("Bot está pronto.")

            logger.info(f"Aguardando bot.db_ready.wait (timeout: {WAIT_TIMEOUT}s)...")
            await asyncio.wait_for(self.bot.db_ready.wait(), timeout=WAIT_TIMEOUT)
            logger.info("DB está pronto.")

            logger.info(f"Aguardando bot.coc_client_ready.wait (timeout: {WAIT_TIMEOUT}s)...")
            await asyncio.wait_for(self.bot.coc_client_ready.wait(), timeout=WAIT_TIMEOUT)
            logger.info("Cliente CoC está pronto.")

        except asyncio.TimeoutError as e:
            logger.critical(f"### TIMEOUT EM COG_LOAD (TasksCog) ###: Uma dependência demorou mais de {WAIT_TIMEOUT}s para ficar pronta. Verifique os logs anteriores para erros de login (Discord, DB ou CoC). O bot pode não funcionar corretamente.", exc_info=False)
            # Decide se quer parar o bot ou continuar com funcionalidade limitada
            # await self.bot.close() # Descomente para parar o bot em caso de timeout
            return # Não inicia as tasks se houve timeout

        except Exception as e:
             logger.critical(f"### ERRO INESPERADO EM COG_LOAD (TasksCog) DURANTE WAITS ###: {e}", exc_info=True)
             return # Não inicia as tasks se houve erro

        # Continua se todos os waits foram bem-sucedidos
        self.watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not self.watchlist_cog:
            logger.error("WatchlistCog não encontrada em TasksCog! Adição automática desativada.")
            self.watchlist_cog = None

        logger.info("Tentando iniciar as tasks.loop em cog_load...")
        try:
            if not self.check_war_end_task.is_running():
                self.check_war_end_task.start()
                logger.info("check_war_end_task iniciada.")
            if not self.donation_snapshot_task.is_running():
                self.donation_snapshot_task.start()
                logger.info("donation_snapshot_task iniciada.")
            if not self.cleanup_old_snapshots_task.is_running():
                self.cleanup_old_snapshots_task.start()
                logger.info("cleanup_old_snapshots_task iniciada.")
            if not self.check_api_status_task.is_running():
                self.check_api_status_task.start()
                logger.info("check_api_status_task iniciada.")
            logger.info("Verificação/Início das tasks.loop concluída em cog_load.")
        except Exception as e:
            logger.critical(f"### ERRO FATAL AO INICIAR TASKS EM COG_LOAD ###: {e}", exc_info=True)


    def cog_unload(self):
        """Para todas as tarefas quando o cog é descarregado."""
        logger.info("Descarregando TasksCog e cancelando tasks...")
        if self.check_war_end_task.is_running(): self.check_war_end_task.cancel()
        if self.donation_snapshot_task.is_running(): self.donation_snapshot_task.cancel()
        if self.cleanup_old_snapshots_task.is_running(): self.cleanup_old_snapshots_task.cancel()
        if self.check_api_status_task.is_running(): self.check_api_status_task.cancel()
        logger.info("Tasks canceladas.")

    # --- Tarefas de Doações ---
    @tasks.loop(hours=1)
    async def donation_snapshot_task(self):
        """Tira um snapshot horário das doações de todos os membros."""
        # (Código mantido igual)
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
        """Limpa snapshots de doações com mais de 8 dias, uma vez por dia."""
        # (Código mantido igual)
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
        # (Código mantido igual)
        if self.bot.maintenance_mode: return
        channel_id_to_use = target_channel_id or self.bot.channel_id
        if not channel_id_to_use:
            logger.warning(f"Tentativa de enviar embed, mas channel_id não configurado (target: {target_channel_id}, default: {self.bot.channel_id})")
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
        # (Código mantido igual)
        if hasattr(war, 'tag') and war.tag and war.tag != '#0': return war.tag
        if hasattr(war, 'preparation_start_time') and war.preparation_start_time and hasattr(war.preparation_start_time, 'time'): return war.preparation_start_time.time.isoformat()
        if hasattr(war, 'end_time') and war.end_time and hasattr(war.end_time, 'time'): return war.end_time.time.isoformat()
        return f"unknown_{datetime.datetime.now(pytz.utc).isoformat()}"


    async def process_ended_war(self, war: coc.ClanWar, war_id: str) -> bool:
        """Processa uma guerra finalizada, salva no DB, envia alertas e adiciona à watchlist."""
        # (Código mantido igual)
        try:
            war_type = "CWL" if war.is_cwl else "Normal"
            our_clan_in_war = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
            opponent_clan_in_war = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan
            opponent_name = opponent_clan_in_war.name if opponent_clan_in_war else "Desconhecido"
            war_end_time_utc = war.end_time.time.replace(tzinfo=pytz.utc) if war.end_time and war.end_time.time else datetime.datetime.now(pytz.utc)
            logger.info(f"Processando guerra ({war_type}) contra {opponent_name} (ID: {war_id})...")

            db_cog = self.bot.get_cog("Banco de Dados")
            web_api_cog = self.bot.get_cog("Web API")

            if db_cog and web_api_cog:
                war_details_for_db = await web_api_cog.format_war_details_for_web(war)
                if 'error' not in war_details_for_db:
                    await db_cog.save_war_to_history(war_details_for_db, war_id)
                    if self.bot.post_war_analysis_channel_id:
                        analysis_embed = create_post_war_analysis_embed(war_details_for_db)
                        if analysis_embed: await self._send_log_embed(analysis_embed, target_channel_id=self.bot.post_war_analysis_channel_id)
                else: logger.error(f"Falha ao obter detalhes da guerra {war_id} para salvar no DB: {war_details_for_db['error']}.")

            missed_members = [m for m in our_clan_in_war.members if len(m.attacks) < war.attacks_per_member]
            if missed_members:
                missed_lines = [f"**{m.name}** ({m.tag}) (CV{m.town_hall}): {war.attacks_per_member - len(m.attacks)} perdido(s)" for m in missed_members]
                embed = discord.Embed(title="🚩 Relatório de Ataques Perdidos", color=discord.Color.dark_gold())
                embed.add_field(name="Placar Final", value=f"**{our_clan_in_war.name}:** {our_clan_in_war.stars}⭐\n**{opponent_clan_in_war.name}:** {opponent_clan_in_war.stars}⭐", inline=False)
                embed.add_field(name="Jogadores com Ataques Pendentes", value="\n".join(missed_lines), inline=False)
                if opponent_clan_in_war.badge: embed.set_thumbnail(url=opponent_clan_in_war.badge.url)
                role_mention = f"<@&{self.bot.role_id_missed_attack}>" if self.bot.role_id_missed_attack else ""
                await self._send_log_embed(embed, content=f"{role_mention} Atenção!", target_channel_id=self.bot.channel_id)

                if self.watchlist_cog and self.bot.auto_add_watchlist_enabled:
                    logger.info(f"Adicionando {len(missed_members)} membros à watchlist automaticamente...")
                    for member in missed_members:
                        await self.watchlist_cog.add_missed_attack_to_watchlist(member.tag, member.name, opponent_name, war_end_time_utc)
                    logger.info("Membros adicionados à watchlist.")
                elif not self.watchlist_cog: logger.warning("WatchlistCog não carregada, não foi possível adicionar membros automaticamente.")
                elif not self.bot.auto_add_watchlist_enabled: logger.info("Adição automática à watchlist desabilitada.")

            logger.info(f"Processamento da guerra {war_id} contra {opponent_name} concluído.")
            return True
        except Exception as e:
            logger.error(f"Erro crítico ao processar guerra {war_id}: {e}", exc_info=True)
            return False

    @tasks.loop(seconds=60.0)
    async def check_war_end_task(self):
        # (Código mantido igual)
        if self.bot.maintenance_mode: return
        if not self.bot.api_client or not self.coc_client_ready.is_set(): return # Verifica se CoC está pronto também

        wars_to_check = []
        try:
            current_war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if current_war: wars_to_check.append(current_war)
        except coc.PrivateWarLog: logger.info("Log de guerra privado.")
        except coc.NotFound: logger.info("Nenhuma guerra atual encontrada.")
        except Exception as e: logger.error(f"Erro ao buscar guerra atual: {e}", exc_info=True)

        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if cwl_group:
                for round_tags in cwl_group.rounds:
                    for war_tag in round_tags:
                        if war_tag == '#0': continue
                        try: cwl_war = await self.bot.api_client.get_league_war(war_tag); wars_to_check.append(cwl_war)
                        except coc.NotFound: continue
                        except Exception as inner_e: logger.error(f"Erro ao buscar guerra CWL específica {war_tag}: {inner_e}")
        except coc.NotFound: logger.info("Nenhum grupo de CWL ativo encontrado.")
        except Exception as e: logger.error(f"Erro ao buscar grupo de CWL: {e}", exc_info=True)

        if not wars_to_check: return

        now = datetime.datetime.now(pytz.utc)
        for war in wars_to_check:
            try:
                if not war or not war.clan or not war.opponent: continue
                is_our_war = war.clan.tag == self.bot.clan_tag or war.opponent.tag == self.bot.clan_tag
                if not is_our_war: continue

                war_ended_by_state = war.state == 'warEnded'
                end_time_utc = war.end_time.time.replace(tzinfo=pytz.utc) if war.end_time and war.end_time.time else None
                war_ended_by_time = end_time_utc is not None and now > end_time_utc

                if not war_ended_by_state and not war_ended_by_time: continue

                unique_war_id = self._get_war_id(war)
                if unique_war_id in self.bot.processed_war_ids: continue

                process_reason = "estado 'warEnded'" if war_ended_by_state else "tempo expirado"
                logger.info(f"Nova guerra terminada ({process_reason}) encontrada (ID: {unique_war_id}). Estado API: {war.state}")

                if await self.process_ended_war(war, unique_war_id):
                    self.bot.processed_war_ids.add(unique_war_id)
                    logger.info(f"Guerra {unique_war_id} adicionada às processadas.")
                else: logger.error(f"Falha ao processar a guerra {unique_war_id}.")
            except Exception as e:
                war_identifier = self._get_war_id(war) if war else "desconhecida"
                logger.error(f"Erro ao verificar guerra específica ({war_identifier}): {e}", exc_info=True)


    @commands.command(name='syncwar')
    @commands.has_permissions(administrator=True)
    async def sync_war(self, ctx: commands.Context):
        """(Admin) Força a execução da verificação de fim de guerra."""
        # (Código mantido igual)
        await ctx.message.add_reaction("🔄")
        logger.info(f"Comando !syncwar invocado por {ctx.author.name}.")
        try:
            await self.check_war_end_task() # Chama a task diretamente
            await ctx.send("✅ Sincronização de fim de guerra forçada concluída.")
        except Exception as e:
            logger.error(f"Erro no comando !syncwar: {e}", exc_info=True)
            await ctx.send(f"❌ Erro crítico: {e}")
        finally:
             try: await ctx.message.remove_reaction("🔄", self.bot.user)
             except discord.errors.NotFound: pass


    # --- Tarefa de Status da API ---
    @tasks.loop(minutes=1)
    async def check_api_status_task(self):
        """Verifica o status da API da Supercell e notifica no Discord se houver mudança."""
        # (Código mantido igual)
        if self.bot.maintenance_mode: return
        admin_cog = self.bot.get_cog("Painel de Administração Avançado")
        if not admin_cog or not self.coc_client_ready.is_set(): return # Verifica CoC pronto

        api_status_data = await admin_cog.get_api_status()
        current_status = api_status_data.get("status", "error")
        status_message = api_status_data.get("message", "N/A")

        if current_status != self.bot.last_api_status:
            logger.info(f"Status API CoC mudou: '{self.bot.last_api_status}' -> '{current_status}'. Notificando.")
            if current_status=="maintenance" or current_status=="error":
                embed_color=discord.Color.orange(); title="🚨 Alerta API Supercell 🚨"
                description="Acesso à API Clash of Clans instável/manutenção."
                impact="**Painel Web:** Indisponível.\n**Alertas Discord:** Podem ser afetados."
            else:
                embed_color=discord.Color.green(); title="✅ API Supercell Operacional"
                description="API Clash of Clans voltou ao normal."
                impact="**Painel Web:** Acesso restaurado.\n**Alertas Discord:** Normais."
            embed = discord.Embed(title=title,description=description,color=embed_color)
            embed.add_field(name="Motivo", value=status_message, inline=False)
            embed.add_field(name="Impacto", value=impact, inline=False)
            await self._send_log_embed(embed, target_channel_id=self.bot.channel_id)
            self.bot.last_api_status = current_status


    # --- Funções before_loop removidas ---
    # As esperas agora estão centralizadas no cog_load

# Função setup
async def setup(bot: commands.Bot):
     logger.info("Configurando TasksCog...")
     try:
         await bot.add_cog(TasksCog(bot))
         logger.info("TasksCog adicionado com sucesso.")
     except Exception as e:
         logger.critical(f"### ERRO FATAL AO ADICIONAR TASKSCOG ###: {e}", exc_info=True)

