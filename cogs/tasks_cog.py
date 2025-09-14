# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import datetime
import pytz
from typing import Dict

# A análise pós-guerra é um módulo separado, então importamos diretamente
from .post_war_analysis import create_post_war_analysis_embed

logger = logging.getLogger("tasks_cog")

# --- Funções de Banco de Dados Movidas para cá ---
async def load_player_notes_from_db(db) -> Dict[str, Dict[str, str]]:
    if db is None:
        logger.warning("Banco de dados não disponível, não é possível carregar as notas.")
        return {}
    try:
        notes_cursor = db.player_notes.find({})
        notes_from_db = {note_doc["_id"]: {"text": note_doc.get("text", ""),"priority": note_doc.get("priority", "none")} async for note_doc in notes_cursor if "_id" in note_doc}
        return notes_from_db
    except Exception as e:
        logger.error(f"Erro ao carregar notas do MongoDB: {e}", exc_info=True)
        return {}

async def save_player_note_to_db(db, player_tag: str, text: str, priority: str):
    if db is None:
        logger.error("Banco de dados não disponível, não é possível salvar a nota.")
        raise ConnectionError("Banco de dados não conectado.")
    try:
        player_tag_decoded = coc.utils.correct_tag(player_tag)
        await db.player_notes.update_one(
            {"_id": player_tag_decoded},
            {"$set": {"text": text, "priority": priority}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Erro ao salvar nota no MongoDB para {player_tag}: {e}", exc_info=True)
        raise

class TasksCog(commands.Cog, name="Tarefas em Segundo Plano"):
    """Cog para gerenciar todas as tarefas que rodam em loop."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_client: coc.Client = bot.api_client
        self.last_war_end_time: datetime.datetime = None

    async def cog_load(self):
        """Inicia todas as tarefas quando o cog é carregado."""
        self.check_war_end_task.start()
        self.daily_player_data_snapshot.start()
        self.send_online_status_task.start()
        logger.info("Tarefas em segundo plano iniciadas.")

    async def cog_unload(self):
        """Para todas as tarefas quando o cog é descarregado."""
        self.check_war_end_task.cancel()
        self.daily_player_data_snapshot.cancel()
        self.send_online_status_task.cancel()
        logger.info("Tarefas em segundo plano paradas.")

    @tasks.loop(seconds=60.0)
    async def check_war_end_task(self):
        await self.bot.wait_until_ready()
        if not self.api_client: return

        events_cog = self.bot.get_cog("Eventos do Clã")
        if not events_cog: return

        try:
            war = await self.api_client.get_current_war(self.bot.clan_tag)
            if war and war.state == 'warEnded' and hasattr(war, 'end_time'):
                if self.last_war_end_time is None or war.end_time.time > self.last_war_end_time:
                    logger.info("Nova guerra finalizada detectada.")
                    self.last_war_end_time = war.end_time.time
                    
                    war_details = await self.bot.fetch_current_war_details_for_web()
                    if 'error' not in war_details: 
                        await self.bot.save_war_to_history(war_details)
                    
                    if hasattr(self.bot, 'db') and self.bot.db:
                        war_doc_from_db = await self.bot.db.war_history.find_one({"_id": war_details["war_data"]["end_time_iso"]})
                        
                        if war_doc_from_db and self.bot.post_war_analysis_channel_id:
                            analysis_embed = create_post_war_analysis_embed(war_doc_from_db)
                            if analysis_embed:
                                await events_cog._send_log_embed(analysis_embed, target_channel_id=self.bot.post_war_analysis_channel_id)
                                logger.info(f"Análise pós-guerra enviada para o canal {self.bot.post_war_analysis_channel_id}.")

                    our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
                    missed = [f"**{m.name}** (CV{m.town_hall}): {war.attacks_per_member - len(m.attacks)} perdido(s)" for m in our_clan.members if len(m.attacks) < war.attacks_per_member]
                    if missed:
                        embed = discord.Embed(title=f"🚩 Relatório de Ataques Perdidos", color=discord.Color.dark_gold())
                        embed.add_field(name="Placar Final", value=f"**{war.clan.name}:** {war.clan.stars}⭐\n**{war.opponent.name}:** {war.opponent.stars}⭐", inline=False)
                        embed.add_field(name="Detalhes", value="\n".join(missed), inline=False)
                        if hasattr(war.opponent.badge, 'url'): embed.set_thumbnail(url=war.opponent.badge.url)
                        role_mention = f"<@&{self.bot.role_id_missed_attack}>" if self.bot.role_id_missed_attack else ""
                        await events_cog._send_log_embed(embed, content=f"{role_mention} Atenção!")
                    
        except (coc.PrivateWarLog, coc.NotFound): pass
        except Exception as e:
            logger.error(f"Erro na task de fim de guerra: {e}", exc_info=True)

    @tasks.loop(hours=24)
    async def daily_player_data_snapshot(self):
        await self.bot.wait_until_ready()
        if not self.api_client or not hasattr(self.bot, 'db') or self.bot.db is None:
            return
        
        logger.info("Iniciando snapshot diário de dados dos jogadores.")
        try:
            clan = await self.api_client.get_clan(self.bot.clan_tag)
            snapshot_time = datetime.datetime.now(pytz.utc)
            records = []
            for member in clan.members:
                records.append({
                    "player_tag": member.tag, "trophies": member.trophies,
                    "donations": member.donations, "received": member.received,
                    "timestamp": snapshot_time
                })
            if records:
                await self.bot.db.trophy_history.insert_many(records)
                logger.info(f"Snapshot salvo para {len(records)} jogadores.")
        except Exception as e:
            logger.error(f"Erro na task de snapshot diário: {e}", exc_info=True)

    @tasks.loop(seconds=15, count=1)
    async def send_online_status_task(self):
        await self.bot.wait_until_ready()
        
        events_cog = self.bot.get_cog("Eventos do Clã")
        if not events_cog:
            await asyncio.sleep(5)
            events_cog = self.bot.get_cog("Eventos do Clã")
            if not events_cog:
                logger.error("Cog de eventos não encontrado para enviar status online.")
                return

        try:
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            embed = discord.Embed(title=f"✅ ClashGenius Online | {clan.name}", description=f"Monitoramento ativado para **{clan.name} ({clan.tag})**.", color=discord.Color.green())
            embed.add_field(name="📊 Status do Clã", value=f"**Membros:** {clan.member_count}/50\n**Troféus:** 🏆 {clan.points}", inline=True)
            embed.add_field(name="⚙️ Status do Bot", value=f"**Versão:** {self.bot.bot_version}\n**API CoC:** ✅ OK", inline=True)
            if clan.badge: embed.set_thumbnail(url=clan.badge.url)
            await events_cog._send_log_embed(embed)
        except Exception as e:
            logger.error(f"Falha ao enviar status online: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TasksCog(bot))
