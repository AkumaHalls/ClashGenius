# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import DESCENDING
import coc
from typing import Dict, Any, Optional, List
import datetime
import json
import asyncio

logger = logging.getLogger("admin_cog")

class AdminCog(commands.Cog, name="Painel de Administração Avançado"):
    """Cog para gerenciar a lógica do backend do painel de administração avançado."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    async def sync_commands(self, scope: str, guild: Optional[discord.Guild] = None) -> Dict[str, Any]:
        target_guild = guild if scope == 'guild' else None
        scope_name = f"o servidor '{guild.name}'" if target_guild else "globalmente"
        logger.info(f"Sincronização iniciada para o escopo: {scope_name}")
        
        try:
            if scope == 'global':
                 synced = await self.bot.tree.sync()
                 message = f"✅ {len(synced)} comandos sincronizados globalmente! (Pode demorar um pouco para aparecer no app)."
                 logger.info(f"Comandos globais sincronizados: {len(synced)}")
                 
            elif target_guild:
                 self.bot.tree.copy_global_to(guild=target_guild)
                 synced = await self.bot.tree.sync(guild=target_guild)
                 message = f"⚡ {len(synced)} comandos forçados no servidor local! (Aparece na hora)."
                 logger.info(f"Comandos limpos e recarregados no servidor {target_guild.name}.")

            return {"status": "success", "message": message}
            
        except discord.errors.Forbidden as e:
             message = f"Falha ao sincronizar: O bot não tem permissão de criar comandos (application.commands) no servidor. Erro: {e}"
             logger.error(message)
             return {"status": "error", "message": message}
        except Exception as e:
            message = f"Falha crítica ao sincronizar comandos: {e}"
            logger.error(message, exc_info=True)
            return {"status": "error", "message": message}

    async def get_api_status(self) -> Dict[str, Any]:
        if not self.bot.api_client:
             return {"status": "error", "message": "Erro interno: Cliente CoC não inicializado."}
        try:
            await self.bot.api_client.get_clan(self.bot.clan_tag)
            return {"status": "ok", "message": "API do Clash of Clans operacional."}
        except coc.errors.Maintenance:
            return {"status": "maintenance", "message": "A API do Clash of Clans está em manutenção. Tente novamente mais tarde."}
        except coc.errors.LoginError:
             return {"status": "error", "message": "Erro de autenticação com a API CoC. Verifique as credenciais."}
        except coc.errors.NotFound:
             return {"status": "error", "message": f"Erro de configuração: Clã {self.bot.clan_tag} não encontrado."}
        except Exception as e:
            return {"status": "error", "message": f"Erro de conexão com a API: Acesso temporariamente indisponível."}

    async def get_diagnostics(self) -> Dict[str, Any]:
        api_status = await self.get_api_status()
        recent_logs = getattr(self.bot, 'log_handler', None)
        log_buffer = recent_logs.buffer if recent_logs else ["Log handler não encontrado."]
        return {"api_status": api_status, "recent_logs": log_buffer}

    async def get_discord_data(self) -> Dict[str, Any]:
        data = {"channels": [], "roles": []}
        try:
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    data["channels"].append({"id": str(channel.id), "name": f"[{guild.name}] #{channel.name}"})
                for role in guild.roles:
                    if role.name != "@everyone":
                        data["roles"].append({"id": str(role.id), "name": f"[{guild.name}] @{role.name}"})
            data["channels"] = sorted(data["channels"], key=lambda x: x["name"].lower())
            data["roles"] = sorted(data["roles"], key=lambda x: x["name"].lower())
        except Exception as e:
            logger.error(f"Erro ao buscar dados do Discord para o Dropdown: {e}", exc_info=True)
        return data

    async def get_settings(self, session: Dict[str, Any]) -> Dict[str, Any]:
        defaults = {
            "channel_id": getattr(self.bot, 'channel_id', 0),
            "post_war_analysis_channel_id": getattr(self.bot, 'post_war_analysis_channel_id', 0),
            "post_war_verdict_channel_id": getattr(self.bot, 'post_war_verdict_channel_id', 0),
            "clan_games_channel_id": getattr(self.bot, 'clan_games_channel_id', 0),
            "cwl_planner_channel_id": getattr(self.bot, 'cwl_planner_channel_id', 0),
            "donations_channel_id": getattr(self.bot, 'donations_channel_id', 0),
            "watchlist_alert_channel_id": getattr(self.bot, 'watchlist_alert_channel_id', getattr(self.bot, 'channel_id', 0)),
            "low_performance_channel_id": getattr(self.bot, 'low_performance_channel_id', 0),
            "capital_report_channel_id": getattr(self.bot, 'capital_report_channel_id', 0),
            "smurf_log_channel_id": getattr(self.bot, 'smurf_log_channel_id', 0), # INJEÇÃO DA VARIÁVEL
            "maintenance_alert_channel_id": getattr(self.bot, 'maintenance_alert_channel_id', 0),
            "role_id_1star_alert": getattr(self.bot, 'role_id_1star_alert', 0),
            "role_id_missed_attack": getattr(self.bot, 'role_id_missed_attack', 0),
            "leader_role_id": getattr(self.bot, 'leader_role_id', 0),
            "coleader_role_id": getattr(self.bot, 'coleader_role_id', 0),
            "maintenance_message": getattr(self.bot, 'maintenance_message', "Manutenção!"),
            "auto_add_watchlist_enabled": getattr(self.bot, 'auto_add_watchlist_enabled', True)
        }

        merged_settings = defaults.copy()
        if self.db is not None:
            try:
                settings_from_db = await self.db.system_config.find_one({"_id": "bot_settings"})
                if settings_from_db:
                    merged_settings.update(settings_from_db)
            except Exception as e: pass
        
        merged_settings.pop('_id', None)

        settings_for_frontend = {}
        for key, value in merged_settings.items():
            if ("_id" in key or "channel_id" in key) and isinstance(value, (int, float, str)):
                settings_for_frontend[key] = str(value)
            elif key == "auto_add_watchlist_enabled":
                settings_for_frontend[key] = "true" if value else "false"
            else:
                settings_for_frontend[key] = value

        return settings_for_frontend

    async def update_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        if self.db is None: return {"status": "error", "message": "Banco de dados não configurado."}
        update_data = {}
        successful_updates = {}
        for key, value in new_settings.items():
            try:
                processed_value = value
                if isinstance(value, str) and ("_id" in key or "channel_id" in key) and value.isdigit():
                    try: processed_value = int(value)
                    except ValueError: processed_value = value
                elif key == "auto_add_watchlist_enabled":
                     processed_value = str(value).lower() in ['true', 'on', '1', 'yes']

                if hasattr(self.bot, key):
                    setattr(self.bot, key, processed_value)
                    successful_updates[key] = processed_value
                else: pass
                update_data[key] = processed_value

            except (ValueError, TypeError) as e:
                 if hasattr(self.bot, key): setattr(self.bot, key, value)
                 update_data[key] = value

        try:
            await self.db.system_config.update_one( {"_id": "bot_settings"}, {"$set": update_data}, upsert=True)
            logger.info(f"Configurações do bot atualizadas via painel admin: {successful_updates}")
            return {"status": "success", "message": "Configurações salvas."}
        except Exception as e:
            return {"status": "error", "message": "Erro ao salvar configurações no banco de dados."}

    async def get_db_viewer_data(self) -> Dict[str, Any]:
        if self.db is None: return {"error": "Banco de dados não configurado."}
        try:
             wars_cursor = self.db.war_history.find({}, {"war_data.opponent_name": 1, "war_data.end_time_iso": 1, "_id": 1}).sort("war_data.end_time_iso", DESCENDING).limit(5)
             last_wars = [ {"opponent": w.get("war_data", {}).get("opponent_name", "N/A"), "end_time": w.get("war_data", {}).get("end_time_iso"), "id": w.get("_id")} async for w in wars_cursor if w.get("_id") ]
             notes_cursor = self.db.player_notes.find({}).sort([("$natural", -1)]).limit(5)
             last_notes = [ {"player_tag": n.get("_id"), "note": n.get("text", ""), "priority": n.get("priority", "none")} async for n in notes_cursor if n.get("_id") ]
             return {"last_wars": last_wars, "last_notes": last_notes}
        except Exception as e: return {"error": "Erro ao buscar dados do banco."}

    async def send_announcement(self, channel_id_str: str, message: str) -> Dict[str, Any]:
        if not channel_id_str or not message: return {"status": "error", "message": "ID do canal e mensagem são obrigatórios."}
        try:
            channel_id = int(channel_id_str)
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            embed = discord.Embed(title="📢 Anúncio do Administrador", description=message, color=discord.Color.orange(), timestamp=datetime.datetime.now(self.bot.timezone))
            try: await channel.send(embed=embed)
            except discord.errors.HTTPException as e:
                if e.status == 429:
                    await asyncio.sleep(5)
                    await channel.send(embed=embed) 
                else: raise e
            return {"status": "success", "message": "Anúncio enviado com sucesso!"}
        except Exception as e: return {"status": "error", "message": f"Erro interno: {e}"}

    async def clear_web_cache(self, cache_key: str) -> Dict[str, Any]:
        if cache_key == 'all':
            self.bot.web_api_cache.clear()
            return {"status": "success", "message": "Todo o cache da web foi limpo."}
        return {"status": "not_found", "message": f"Cache '{cache_key}' não encontrado."}

    async def get_watchlist_admin(self) -> List[Dict[str, Any]]:
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not watchlist_cog: return {"error": "Watchlist Cog não carregada."}
        try:
            watchlist_data = await watchlist_cog.get_full_watchlist()
            processed_data = []
            for player in watchlist_data:
                if 'date_added' in player and isinstance(player['date_added'], datetime.datetime):
                    player['date_added'] = player['date_added'].isoformat()
                processed_data.append(player)
            return processed_data
        except Exception as e: return {"error": "Erro interno ao buscar watchlist."}

    async def add_to_watchlist_admin(self, player_tag: str, player_name: str, reason: str, details: Optional[str] = None) -> bool:
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not watchlist_cog: return False
        try: return await watchlist_cog.add_to_watchlist(player_tag, player_name, reason, details)
        except Exception: return False

    async def remove_from_watchlist_admin(self, player_tag: str) -> bool:
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not watchlist_cog: return False
        try: return await watchlist_cog.remove_from_watchlist(player_tag)
        except Exception: return False

    # =========================================================
    # AÇÕES DO RADAR PERICIAL DA IA
    # =========================================================
    async def get_smurf_dossier(self):
        smurf_cog = self.bot.get_cog("Detetor de Smurfs IA")
        if not smurf_cog: return {"error": "Smurf Cog não carregado."}
        return await smurf_cog.get_web_dossier()

    async def absolve_smurf(self, pair_id):
        smurf_cog = self.bot.get_cog("Detetor de Smurfs IA")
        if not smurf_cog: return {"status": "error", "message": "Módulo offline."}
        return await smurf_cog.absolve_pair(pair_id)

    async def condemn_smurf(self, pair_id):
        smurf_cog = self.bot.get_cog("Detetor de Smurfs IA")
        if not smurf_cog: return {"status": "error", "message": "Módulo offline."}
        return await smurf_cog.condemn_pair(pair_id)

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
