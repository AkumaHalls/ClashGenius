# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import DESCENDING
import coc
from typing import Dict, Any, Optional
import datetime
import json # Import json for dumps default

logger = logging.getLogger("admin_cog")

class AdminCog(commands.Cog, name="Painel de Administração Avançado"):
    """Cog para gerenciar a lógica do backend do painel de administração avançado."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        # Obtém referência à WatchlistCog após o bot estar pronto
        self.watchlist_cog = None

    async def cog_load(self):
        # Espera o bot estar pronto para garantir que todas as Cogs foram carregadas
        await self.bot.wait_until_ready()
        self.watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not self.watchlist_cog:
            logger.error("WatchlistCog não encontrada! A funcionalidade de watchlist no painel admin não funcionará.")
            self.watchlist_cog = None # Define como None para evitar erros

    async def sync_commands(self, scope: str, guild: Optional[discord.Guild] = None) -> Dict[str, Any]:
        """Lógica centralizada para sincronizar comandos de barra."""
        target_guild = guild if scope == 'guild' else None
        scope_name = f"o servidor '{guild.name}'" if target_guild else "globalmente"
        logger.info(f"Sincronização iniciada para o escopo: {scope_name}")
        try:
            self.bot.tree.clear_commands(guild=target_guild)
            await self.bot.tree.sync(guild=target_guild)

            synced = await self.bot.tree.sync(guild=target_guild)

            message = f"Sincronizados {len(synced)} comandos com sucesso no escopo '{scope}'."
            logger.info(message)
            return {"status": "success", "message": message}
        except Exception as e:
            message = f"Falha ao sincronizar comandos no escopo '{scope}': {e}"
            logger.error(message, exc_info=True)
            return {"status": "error", "message": message}

    async def get_api_status(self) -> Dict[str, Any]:
        """Verifica o status da API da Supercell."""
        try:
            await self.bot.api_client.get_clan(self.bot.clan_tag)
            return {"status": "ok", "message": "API do Clash of Clans operacional."}
        except coc.errors.Maintenance:
            return {"status": "maintenance", "message": "A API do Clash of Clans está em manutenção. Tente novamente mais tarde."}
        except Exception as e:
            return {"status": "error", "message": f"Erro de conexão com a API: Acesso temporariamente indisponível. ({type(e).__name__})"}

    async def get_diagnostics(self) -> Dict[str, Any]:
        """Coleta dados de diagnóstico do bot."""
        api_status = await self.get_api_status()
        recent_logs = self.bot.log_handler.buffer
        return {
            "api_status": api_status,
            "recent_logs": recent_logs
        }

    async def get_settings(self) -> Dict[str, Any]:
        if self.db is None:
            return {"error": "Banco de dados não configurado."}

        settings = await self.db.system_config.find_one({"_id": "bot_settings"})
        defaults = {
            "channel_id": self.bot.channel_id,
            "post_war_analysis_channel_id": self.bot.post_war_analysis_channel_id,
            "clan_games_channel_id": self.bot.clan_games_channel_id,
            "cwl_planner_channel_id": self.bot.cwl_planner_channel_id,
            "donations_channel_id": getattr(self.bot, 'donations_channel_id', 0),
            "role_id_1star_alert": self.bot.role_id_1star_alert,
            "role_id_missed_attack": self.bot.role_id_missed_attack,
            "maintenance_message": self.bot.maintenance_message
        }
        if not settings:
            return defaults
        for key, value in defaults.items():
            settings.setdefault(key, value)
        # Remove o _id interno do MongoDB antes de retornar
        settings.pop('_id', None)
        return settings

    async def update_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        if self.db is None:
            return {"error": "Banco de dados não configurado."}
        update_data = {}
        for key, value in new_settings.items():
            try:
                # Converte IDs para int, se possível e necessário
                processed_value = int(value) if "id" in key and value and isinstance(value, str) and value.isdigit() else value
                if hasattr(self.bot, key):
                    setattr(self.bot, key, processed_value)
                update_data[key] = processed_value # Adiciona ao dict para salvar no DB
            except (ValueError, TypeError):
                 if hasattr(self.bot, key):
                    setattr(self.bot, key, value)
                 update_data[key] = value # Adiciona ao dict para salvar no DB

        await self.db.system_config.update_one(
            {"_id": "bot_settings"},
            {"$set": update_data}, # Salva apenas os dados processados
            upsert=True
        )
        logger.info(f"Configurações do bot atualizadas via painel admin: {update_data}")
        return {"status": "success", "message": "Configurações salvas."}

    async def get_db_viewer_data(self) -> Dict[str, Any]:
        if self.db is None:
            return {"error": "Banco de dados não configurado."}
        wars_cursor = self.db.war_history.find({}, {"war_data.opponent_name": 1, "war_data.end_time_iso": 1, "_id": 1}).sort("war_data.end_time_iso", DESCENDING).limit(5)
        # Usamos json.dumps com default=str para lidar com datetime
        last_wars = [{"opponent": w.get("war_data", {}).get("opponent_name", "N/A"), "end_time": w.get("war_data", {}).get("end_time_iso", "N/A"),"id": w.get("_id", "N/A")} async for w in wars_cursor]
        notes_cursor = self.db.player_notes.find({}).sort([("$natural", -1)]).limit(5)
        last_notes = [{"player_tag": n.get("_id", "N/A"),"note": n.get("text", ""),"priority": n.get("priority", "none")} async for n in notes_cursor]
        return {"last_wars": last_wars, "last_notes": last_notes}

    async def send_announcement(self, channel_id_str: str, message: str) -> Dict[str, Any]:
        if not channel_id_str or not message:
            return {"status": "error", "message": "ID do canal e mensagem são obrigatórios."}
        try:
            channel_id = int(channel_id_str)
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            embed = discord.Embed(title="📢 Anúncio do Administrador",description=message,color=discord.Color.orange(),timestamp=datetime.datetime.now(self.bot.timezone))
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
        if cache_key == 'all':
            self.bot.web_api_cache.clear()
            logger.info("Todo o cache da web foi limpo via painel.")
            return {"status": "success", "message": "Todo o cache da web foi limpo."}
        elif cache_key in self.bot.web_api_cache:
            self.bot.web_api_cache.pop(cache_key)
            logger.info(f"Cache da web para '{cache_key}' limpo via painel.")
            return {"status": "success", "message": f"Cache '{cache_key}' foi limpo."}
        return {"status": "not_found", "message": f"Cache '{cache_key}' não encontrado."}

    # --- Funções para interagir com WatchlistCog (chamadas pela API web) ---
    async def get_watchlist_admin(self):
        if not self.watchlist_cog: return {"error": "Watchlist Cog não carregada."}
        return await self.watchlist_cog.get_full_watchlist()

    async def add_to_watchlist_admin(self, player_tag: str, player_name: str, reason: str, details: Optional[str] = None):
        if not self.watchlist_cog: return {"error": "Watchlist Cog não carregada."}
        return await self.watchlist_cog.add_to_watchlist(player_tag, player_name, reason, details)

    async def remove_from_watchlist_admin(self, player_tag: str):
        if not self.watchlist_cog: return {"error": "Watchlist Cog não carregada."}
        return await self.watchlist_cog.remove_from_watchlist(player_tag)

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
