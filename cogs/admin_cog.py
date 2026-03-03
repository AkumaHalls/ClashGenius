# -*- coding: utf-8 -*-
import logging
import sys
import psutil
import datetime
from discord.ext import commands
import coc

logger = logging.getLogger("admin_cog")

class AdminCog(commands.Cog, name="Painel de Administração Avançado"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def get_diagnostics(self):
        process = psutil.Process()
        memory_info = process.memory_info()
        uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(process.create_time())
        db_status = "Online" if self.bot.db is not None else "Offline"
        
        cogs_status = []
        for name, cog in self.bot.cogs.items():
            status = "Carregado"
            cogs_status.append({"name": name, "status": status})

        return {
            "uptime": str(uptime).split('.')[0],
            "memory_usage": f"{memory_info.rss / 1024 / 1024:.2f} MB",
            "cpu_usage": f"{process.cpu_percent()}%",
            "db_status": db_status,
            "cogs": cogs_status,
            "bot_latency": f"{self.bot.latency * 1000:.0f} ms"
        }

    async def get_settings(self, session):
        guild_id = session.get('guild_id')
        guild = self.bot.get_guild(int(guild_id)) if guild_id else None
        
        channels = [{"id": str(c.id), "name": c.name} for c in guild.text_channels] if guild else []
        roles = [{"id": str(r.id), "name": r.name} for r in guild.roles] if guild else []

        return {
            "channel_id": str(self.bot.channel_id),
            "ai_log_channel_id": str(self.bot.ai_log_channel_id),
            "post_war_analysis_channel_id": str(self.bot.post_war_analysis_channel_id),
            "clan_games_channel_id": str(self.bot.clan_games_channel_id),
            "cwl_planner_channel_id": str(self.bot.cwl_planner_channel_id),
            "donations_channel_id": str(self.bot.donations_channel_id),
            "watchlist_alert_channel_id": str(self.bot.watchlist_alert_channel_id),
            "low_performance_channel_id": str(self.bot.low_performance_channel_id),
            "capital_report_channel_id": str(self.bot.capital_report_channel_id),
            "smurf_log_channel_id": str(self.bot.smurf_log_channel_id), # NOVO CANAL ADICIONADO AQUI
            "role_id_1star_alert": str(self.bot.role_id_1star_alert),
            "role_id_missed_attack": str(self.bot.role_id_missed_attack),
            "leader_role_id": str(self.bot.leader_role_id),
            "coleader_role_id": str(self.bot.coleader_role_id),
            "maintenance_message": self.bot.maintenance_message,
            "auto_add_watchlist_enabled": self.bot.auto_add_watchlist_enabled,
            "available_channels": channels,
            "available_roles": roles
        }

    async def update_settings(self, data):
        try:
            settings_to_update = {
                "channel_id": int(data.get("channel_id", self.bot.channel_id) or 0),
                "ai_log_channel_id": int(data.get("ai_log_channel_id", self.bot.ai_log_channel_id) or 0),
                "post_war_analysis_channel_id": int(data.get("post_war_analysis_channel_id", self.bot.post_war_analysis_channel_id) or 0),
                "clan_games_channel_id": int(data.get("clan_games_channel_id", self.bot.clan_games_channel_id) or 0),
                "cwl_planner_channel_id": int(data.get("cwl_planner_channel_id", self.bot.cwl_planner_channel_id) or 0),
                "donations_channel_id": int(data.get("donations_channel_id", self.bot.donations_channel_id) or 0),
                "watchlist_alert_channel_id": int(data.get("watchlist_alert_channel_id", self.bot.watchlist_alert_channel_id) or 0),
                "low_performance_channel_id": int(data.get("low_performance_channel_id", self.bot.low_performance_channel_id) or 0),
                "capital_report_channel_id": int(data.get("capital_report_channel_id", self.bot.capital_report_channel_id) or 0),
                "smurf_log_channel_id": int(data.get("smurf_log_channel_id", self.bot.smurf_log_channel_id) or 0), # NOVO CANAL ADICIONADO AQUI
                "role_id_1star_alert": int(data.get("role_id_1star_alert", self.bot.role_id_1star_alert) or 0),
                "role_id_missed_attack": int(data.get("role_id_missed_attack", self.bot.role_id_missed_attack) or 0),
                "leader_role_id": int(data.get("leader_role_id", self.bot.leader_role_id) or 0),
                "coleader_role_id": int(data.get("coleader_role_id", self.bot.coleader_role_id) or 0),
                "maintenance_message": data.get("maintenance_message", self.bot.maintenance_message),
                "auto_add_watchlist_enabled": data.get("auto_add_watchlist_enabled", self.bot.auto_add_watchlist_enabled)
            }

            for key, value in settings_to_update.items():
                setattr(self.bot, key, value)

            if self.bot.db is not None:
                await self.bot.db.system_config.update_one(
                    {"_id": "bot_settings"},
                    {"$set": settings_to_update},
                    upsert=True
                )
                logger.info("Configurações atualizadas no banco de dados com sucesso.")
                return {"status": "success", "message": "Configurações salvas!"}
            else:
                return {"status": "warning", "message": "Configurações aplicadas apenas na memória (banco offline)."}

        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}", exc_info=True)
            return {"status": "error", "message": f"Erro interno: {e}"}

    async def get_db_viewer_data(self):
        if self.bot.db is None: return {"error": "Banco Offline"}
        data = {}
        collections = await self.bot.db.list_collection_names()
        for coll_name in collections:
            cursor = self.bot.db[coll_name].find().limit(50)
            data[coll_name] = [doc async for doc in cursor]
        return data

    async def get_watchlist_admin(self):
        if self.bot.db is None: return {"error": "Banco Offline"}
        try:
             cursor = self.bot.db.watchlist.find()
             watchlist = []
             async for doc in cursor:
                  watchlist.append({
                       "player_tag": doc.get("player_tag", ""),
                       "player_name": doc.get("player_name", "Desconhecido"),
                       "reason": doc.get("reason", ""),
                       "details": doc.get("details", ""),
                       "added_by": doc.get("added_by", "Sistema"),
                       "added_at": doc.get("added_at", "").isoformat() if isinstance(doc.get("added_at"), datetime.datetime) else str(doc.get("added_at", ""))
                  })
             return watchlist
        except Exception as e:
             logger.error(f"Erro ao buscar watchlist pro admin: {e}")
             return {"error": "Erro interno."}

    async def add_to_watchlist_admin(self, tag, name, reason, details):
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not watchlist_cog: return False
        try:
            return await watchlist_cog.add_to_watchlist_core(tag, name, reason, details, added_by="Painel Admin")
        except Exception as e:
            logger.error(f"Erro ao adicionar na watchlist pelo admin: {e}")
            return False

    async def remove_from_watchlist_admin(self, tag):
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not watchlist_cog: return False
        try:
            return await watchlist_cog.remove_from_watchlist_core(tag)
        except Exception as e:
            logger.error(f"Erro ao remover da watchlist pelo admin: {e}")
            return False

    async def get_discord_data(self):
        guilds_data = []
        for g in self.bot.guilds:
            roles = [{"id": str(r.id), "name": r.name} for r in g.roles]
            channels = [{"id": str(c.id), "name": c.name} for c in g.text_channels]
            guilds_data.append({"id": str(g.id), "name": g.name, "roles": roles, "channels": channels})
        return {"guilds": guilds_data}

    async def send_announcement(self, channel_id, message):
        try:
            channel = self.bot.get_channel(int(channel_id))
            if channel:
                await channel.send(message)
                return {"status": "success", "message": "Anúncio enviado!"}
            return {"status": "error", "message": "Canal não encontrado."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def clear_web_cache(self, cache_key):
        if cache_key == "all":
            self.bot.web_api_cache.clear()
            self.bot.clan_cache.clear()
            return {"status": "success", "message": "Todo o cache foi limpo!"}
        elif cache_key in self.bot.web_api_cache:
            del self.bot.web_api_cache[cache_key]
            return {"status": "success", "message": f"Cache '{cache_key}' limpo!"}
        return {"status": "error", "message": "Chave de cache não encontrada."}

    async def sync_commands(self, scope, guild=None):
        try:
            if scope == 'global':
                 synced = await self.bot.tree.sync()
                 return {"status": "success", "message": f"{len(synced)} comandos sincronizados globalmente."}
            elif scope == 'guild' and guild:
                 synced = await self.bot.tree.sync(guild=guild)
                 return {"status": "success", "message": f"{len(synced)} comandos sincronizados no servidor {guild.name}."}
            return {"status": "error", "message": "Parâmetros de sincronização inválidos."}
        except Exception as e:
             return {"status": "error", "message": str(e)}

    async def get_api_status(self):
         if not self.bot.api_client: return {"status": "error", "message": "Cliente CoC não inicializado."}
         try:
              await self.bot.api_client.get_clan(self.bot.clan_tag)
              return {"status": "ok", "message": "API CoC Online"}
         except coc.Maintenance: return {"status": "maintenance", "message": "Os servidores do Clash of Clans estão em manutenção."}
         except coc.NotFound: return {"status": "error", "message": "Clã não encontrado (Tag inválida?)."}
         except coc.LoginError: return {"status": "error", "message": "Erro de login na API da Supercell."}
         except Exception as e: return {"status": "error", "message": f"Falha na comunicação: {str(e)}"}

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
