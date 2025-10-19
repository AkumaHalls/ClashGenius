# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands
from pymongo import DESCENDING
import coc
from typing import Dict, Any
import datetime

logger = logging.getLogger("admin_cog")

class AdminCog(commands.Cog, name="Painel de Administração Avançado"):
    """Cog para gerenciar a lógica do backend do painel de administração e comandos de sincronização."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    @commands.command(name='sync')
    @commands.has_permissions(administrator=True)
    async def sync(self, ctx: commands.Context):
        """Sincroniza os comandos de barra com o Discord."""
        logger.info(f"Comando !sync invocado por {ctx.author.name}.")
        await ctx.message.add_reaction("🔄")
        try:
            # Sincroniza a árvore de comandos de barra
            synced = await self.bot.tree.sync()
            await ctx.send(f"✅ Sincronizados {len(synced)} comandos de barra!")
            logger.info(f"{len(synced)} comandos de barra foram sincronizados com sucesso.")
        except Exception as e:
            await ctx.send(f"❌ Falha ao sincronizar: {e}")
            logger.error(f"Falha ao sincronizar comandos de barra: {e}", exc_info=True)
        finally:
             await ctx.message.remove_reaction("🔄", self.bot.user)


    async def get_api_status(self) -> Dict[str, Any]:
        """Verifica a conectividade com a API do Clash of Clans."""
        try:
            await self.bot.api_client.get_clan(self.bot.clan_tag)
            return {"status": "ok", "message": "API do Clash of Clans operacional."}
        except coc.errors.Maintenance:
            return {"status": "maintenance", "message": "API em manutenção."}
        except Exception as e:
            return {"status": "error", "message": f"Erro de conexão com a API: {e}"}

    async def get_diagnostics(self) -> Dict[str, Any]:
        """Coleta dados de diagnóstico do bot."""
        api_status = await self.get_api_status()
        return {
            "api_status": api_status,
            "recent_logs": [record.getMessage() for record in self.bot.log_handler.buffer]
        }

    async def get_settings(self) -> Dict[str, Any]:
        """Busca as configurações atuais do banco de dados."""
        if self.db is None:
            return {"error": "Banco de dados não configurado."}
        
        settings = await self.db.system_config.find_one({"_id": "bot_settings"})
        if not settings:
            return {
                "channel_id": self.bot.channel_id,
                "post_war_analysis_channel_id": self.bot.post_war_analysis_channel_id,
                "clan_games_channel_id": self.bot.clan_games_channel_id,
                "cwl_planner_channel_id": self.bot.cwl_planner_channel_id,
                "donations_channel_id": self.bot.donations_channel_id,
                "role_id_1star_alert": self.bot.role_id_1star_alert,
                "role_id_missed_attack": self.bot.role_id_missed_attack,
                "maintenance_message": self.bot.maintenance_message
            }
        return settings

    async def update_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza as configurações no bot e no banco de dados."""
        if self.db is None: return {"error": "Banco de dados não configurado."}

        for key, value in new_settings.items():
            try:
                processed_value = int(value) if "id" in key and value else value
                if hasattr(self.bot, key): setattr(self.bot, key, processed_value)
            except (ValueError, TypeError):
                 if hasattr(self.bot, key): setattr(self.bot, key, value)

        await self.db.system_config.update_one(
            {"_id": "bot_settings"}, {"$set": new_settings}, upsert=True
        )
        logger.info(f"Configurações do bot atualizadas via painel admin: {new_settings}")
        return {"status": "success", "message": "Configurações salvas."}

    async def get_db_viewer_data(self) -> Dict[str, Any]:
        """Busca os últimos registros do banco de dados para visualização."""
        if self.db is None: return {"error": "Banco de dados não configurado."}

        wars_cursor = self.db.war_history.find({}, {"war_data.opponent_name": 1, "war_data.end_time_iso": 1, "_id": 1}).sort("war_data.end_time_iso", DESCENDING).limit(5)
        last_wars = [ {"opponent": w.get("war_data", {}).get("opponent_name", "N/A"), "end_time": w.get("war_data", {}).get("end_time_iso", "N/A"), "id": w.get("_id", "N/A")} async for w in wars_cursor ]
        
        notes_cursor = self.db.player_notes.find({}).sort([("$natural", -1)]).limit(5)
        last_notes = [ {"player_tag": n.get("_id", "N/A"), "note": n.get("text", ""), "priority": n.get("priority", "none")} async for n in notes_cursor ]

        return {"last_wars": last_wars, "last_notes": last_notes}
    
    async def send_announcement(self, channel_id_str: str, message: str) -> Dict[str, Any]:
        """Envia uma mensagem de anúncio para um canal do Discord."""
        if not channel_id_str or not message:
            return {"status": "error", "message": "ID do canal e mensagem são obrigatórios."}
        
        try:
            channel_id = int(channel_id_str)
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            
            embed = discord.Embed(
                title="📢 Anúncio do Administrador",
                description=message,
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now(self.bot.timezone)
            )
            embed.set_footer(text=f"Enviado via Painel Clash Genius v{self.bot.bot_version}")
            await channel.send(embed=embed)
            logger.info(f"Anúncio enviado para o canal {channel_id} via painel.")
            return {"status": "success", "message": "Anúncio enviado com sucesso!"}
        except ValueError:
            return {"status": "error", "message": "O ID do canal deve ser um número."}
        except (discord.NotFound, discord.Forbidden):
            return {"status": "error", "message": "Não foi possível encontrar ou enviar mensagem para o canal."}
        except Exception as e:
            logger.error(f"Erro ao enviar anúncio: {e}", exc_info=True)
            return {"status": "error", "message": f"Erro interno: {e}"}

    async def clear_web_cache(self, cache_key: str) -> Dict[str, Any]:
        """Limpa uma chave específica do cache da API web."""
        if cache_key in self.bot.web_api_cache:
            self.bot.web_api_cache.pop(cache_key)
            logger.info(f"Cache da web para '{cache_key}' limpo via painel.")
            return {"status": "success", "message": f"Cache '{cache_key}' foi limpo."}
        return {"status": "not_found", "message": f"Cache '{cache_key}' não encontrado."}

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))

