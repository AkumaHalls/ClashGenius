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
import asyncio  # <--- Adicionado para o sleep do Rate Limit

logger = logging.getLogger("admin_cog")

class AdminCog(commands.Cog, name="Painel de Administração Avançado"):
    """Cog para gerenciar a lógica do backend do painel de administração avançado."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    async def sync_commands(self, scope: str, guild: Optional[discord.Guild] = None) -> Dict[str, Any]:
        """Lógica centralizada para sincronizar comandos de barra."""
        target_guild = guild if scope == 'guild' else None
        scope_name = f"o servidor '{guild.name}'" if target_guild else "globalmente"
        logger.info(f"Sincronização iniciada para o escopo: {scope_name}")
        try:
            if scope == 'global':
                 self.bot.tree.clear_commands(guild=None)
                 await self.bot.tree.sync()
                 logger.info("Comandos globais limpos.")
            elif target_guild:
                 self.bot.tree.clear_commands(guild=target_guild)
                 await self.bot.tree.sync(guild=target_guild)
                 logger.info(f"Comandos limpos no servidor {target_guild.name}.")

            synced = await self.bot.tree.sync(guild=target_guild)

            message = f"Sincronizados {len(synced)} comandos com sucesso no escopo '{scope}'."
            logger.info(message)
            return {"status": "success", "message": message}
        except discord.errors.Forbidden as e:
             message = f"Falha ao sincronizar: Permissão negada no escopo '{scope}'. Verifique as permissões do bot. Erro: {e}"
             logger.error(message)
             return {"status": "error", "message": message}
        except Exception as e:
            message = f"Falha ao sincronizar comandos no escopo '{scope}': {e}"
            logger.error(message, exc_info=True)
            return {"status": "error", "message": message}

    async def get_api_status(self) -> Dict[str, Any]:
        """Verifica o status da API da Supercell."""
        if not self.bot.api_client:
             logger.error("get_api_status: Tentativa de verificar status sem api_client.")
             return {"status": "error", "message": "Erro interno: Cliente CoC não inicializado."}
        try:
            await self.bot.api_client.get_clan(self.bot.clan_tag)
            return {"status": "ok", "message": "API do Clash of Clans operacional."}
        except coc.errors.Maintenance:
            logger.warning("API CoC está em manutenção.")
            return {"status": "maintenance", "message": "A API do Clash of Clans está em manutenção. Tente novamente mais tarde."}
        except coc.errors.LoginError:
             logger.error("Erro de autenticação com a API CoC.")
             return {"status": "error", "message": "Erro de autenticação com a API CoC. Verifique as credenciais."}
        except coc.errors.NotFound:
             logger.error(f"Erro ao verificar status: Clã {self.bot.clan_tag} não encontrado. Verifique CLAN_TAG.")
             return {"status": "error", "message": f"Erro de configuração: Clã {self.bot.clan_tag} não encontrado."}
        except Exception as e:
            logger.error(f"Erro inesperado ao verificar status da API: {type(e).__name__} - {e}", exc_info=False)
            return {"status": "error", "message": f"Erro de conexão com a API: Acesso temporariamente indisponível."}

    async def get_diagnostics(self) -> Dict[str, Any]:
        """Coleta dados de diagnóstico do bot."""
        api_status = await self.get_api_status()
        recent_logs = getattr(self.bot, 'log_handler', None)
        log_buffer = recent_logs.buffer if recent_logs else ["Log handler não encontrado."]
        return {
            "api_status": api_status,
            "recent_logs": log_buffer
        }

    async def get_settings(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Obtém as configurações atuais do bot."""
        guild_id_str = session.get('guild_id')
        guild = None
        if guild_id_str:
            try:
                guild = self.bot.get_guild(int(guild_id_str))
            except (ValueError, TypeError):
                logger.warning(f"get_settings: guild_id inválido na sessão: {guild_id_str}")
        
        defaults = {
            "channel_id": getattr(self.bot, 'channel_id', 0),
            "post_war_analysis_channel_id": getattr(self.bot, 'post_war_analysis_channel_id', 0),
            "clan_games_channel_id": getattr(self.bot, 'clan_games_channel_id', 0),
            "cwl_planner_channel_id": getattr(self.bot, 'cwl_planner_channel_id', 0),
            "donations_channel_id": getattr(self.bot, 'donations_channel_id', 0),
            "watchlist_alert_channel_id": getattr(self.bot, 'watchlist_alert_channel_id', getattr(self.bot, 'channel_id', 0)),
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
            except Exception as e:
                logger.error(f"Erro ao buscar settings do DB: {e}", exc_info=True)
        
        merged_settings.pop('_id', None)

        settings_with_names = {}
        for key, value in merged_settings.items():
            if ("_id" in key or "channel_id" in key) and isinstance(value, (int, float, str)):
                id_str = str(value)
                id_int = 0
                try:
                    id_int = int(id_str)
                except (ValueError, TypeError):
                    pass
                
                if id_int == 0:
                    settings_with_names[key] = {"id": id_str, "name": "Nenhum"}
                    continue

                item_name = "Não encontrado"
                if "channel_id" in key:
                    channel = self.bot.get_channel(id_int)
                    if channel:
                        item_name = f"#{channel.name}"
                elif "role_id" in key:
                    role = None
                    if guild:
                        role = guild.get_role(id_int)
                    if role:
                        item_name = f"@{role.name}"
                    elif guild:
                        item_name = "Cargo não encontrado"
                    else:
                        item_name = "Sem Info do Servidor"
                
                settings_with_names[key] = {"id": id_str, "name": item_name}
            elif key == "auto_add_watchlist_enabled":
                settings_with_names[key] = "true" if value else "false"
            else:
                settings_with_names[key] = value

        return settings_with_names

    async def update_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza as configurações no bot e no banco de dados."""
        if self.db is None: return {"status": "error", "message": "Banco de dados não configurado."}
        update_data = {}
        successful_updates = {}
        for key, value in new_settings.items():
            try:
                processed_value = value
                if isinstance(value, str) and ("_id" in key or "channel_id" in key) and value.isdigit():
                    try:
                        processed_value = int(value)
                    except ValueError:
                         processed_value = value
                elif key == "auto_add_watchlist_enabled":
                     processed_value = str(value).lower() in ['true', 'on', '1', 'yes']

                if hasattr(self.bot, key):
                    setattr(self.bot, key, processed_value)
                    successful_updates[key] = processed_value
                else:
                     logger.warning(f"Tentativa de atualizar setting inexistente no bot: '{key}'")

                update_data[key] = processed_value

            except (ValueError, TypeError) as e:
                 logger.warning(f"Erro ao processar setting '{key}' com valor '{value}': {e}. Usando valor original.")
                 if hasattr(self.bot, key): setattr(self.bot, key, value)
                 update_data[key] = value

        try:
            await self.db.system_config.update_one( {"_id": "bot_settings"}, {"$set": update_data}, upsert=True)
            logger.info(f"Configurações do bot atualizadas via painel admin: {successful_updates}")
            return {"status": "success", "message": "Configurações salvas."}
        except Exception as e:
            logger.error(f"Erro ao salvar settings no DB: {e}", exc_info=True)
            return {"status": "error", "message": "Erro ao salvar configurações no banco de dados."}

    async def get_db_viewer_data(self) -> Dict[str, Any]:
        """Busca os últimos registros de guerras e notas para o painel admin."""
        if self.db is None: return {"error": "Banco de dados não configurado."}
        try:
             wars_cursor = self.db.war_history.find(
                 {},
                 {"war_data.opponent_name": 1, "war_data.end_time_iso": 1, "_id": 1}
             ).sort("war_data.end_time_iso", DESCENDING).limit(5)
             last_wars = [
                 {"opponent": w.get("war_data", {}).get("opponent_name", "N/A"),
                  "end_time": w.get("war_data", {}).get("end_time_iso"),
                  "id": w.get("_id")}
                 async for w in wars_cursor if w.get("_id")
             ]

             notes_cursor = self.db.player_notes.find({}).sort([("$natural", -1)]).limit(5)
             last_notes = [
                 {"player_tag": n.get("_id"),
                  "note": n.get("text", ""),
                  "priority": n.get("priority", "none")}
                 async for n in notes_cursor if n.get("_id")
             ]
             return {"last_wars": last_wars, "last_notes": last_notes}
        except Exception as e:
             logger.error(f"Erro ao buscar dados para DB viewer: {e}", exc_info=True)
             return {"error": "Erro ao buscar dados do banco."}

    async def send_announcement(self, channel_id_str: str, message: str) -> Dict[str, Any]:
        """Envia um anúncio para um canal específico, com proteção contra Rate Limit."""
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

            # --- PROTEÇÃO RATE LIMIT ---
            try:
                await channel.send(embed=embed)
            except discord.errors.HTTPException as e:
                if e.status == 429: # Rate Limit
                    logger.warning(f"Rate Limit 429 detectado ao enviar anúncio. Aguardando 5s...")
                    await asyncio.sleep(5)
                    await channel.send(embed=embed) # Tenta novamente
                else:
                    raise e
            # ---------------------------

            logger.info(f"Anúncio enviado para o canal {channel_id} via painel.")
            return {"status": "success", "message": "Anúncio enviado com sucesso!"}

        except ValueError:
            return {"status": "error", "message": "O ID do canal deve ser um número."}
        except (discord.NotFound, discord.Forbidden):
            return {"status": "error", "message": "Canal não encontrado ou sem permissão."}
        except Exception as e:
            logger.error(f"Erro ao enviar anúncio: {e}", exc_info=True)
            return {"status": "error", "message": f"Erro interno: {e}"}

    async def clear_web_cache(self, cache_key: str) -> Dict[str, Any]:
        if cache_key == 'all':
            self.bot.web_api_cache.clear()
            logger.info("Cache web limpo via painel.")
            return {"status": "success", "message": "Todo o cache da web foi limpo."}
        elif cache_key in self.bot.web_api_cache:
            self.bot.web_api_cache.pop(cache_key)
            logger.info(f"Cache '{cache_key}' limpo via painel.")
            return {"status": "success", "message": f"Cache '{cache_key}' foi limpo."}
        return {"status": "not_found", "message": f"Cache '{cache_key}' não encontrado."}

    async def get_watchlist_admin(self) -> List[Dict[str, Any]]:
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not watchlist_cog:
            logger.error("get_watchlist_admin: Watchlist Cog não carregada.")
            return {"error": "Watchlist Cog não carregada."}

        try:
            watchlist_data = await watchlist_cog.get_full_watchlist()
            processed_data = []
            for player in watchlist_data:
                if 'date_added' in player and isinstance(player['date_added'], datetime.datetime):
                    player['date_added'] = player['date_added'].isoformat()
                processed_data.append(player)
            return processed_data
        except Exception as e:
            logger.error(f"Erro ao buscar/processar watchlist: {e}", exc_info=True)
            return {"error": "Erro interno ao buscar watchlist."}

    async def add_to_watchlist_admin(self, player_tag: str, player_name: str, reason: str, details: Optional[str] = None) -> bool:
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not watchlist_cog:
            return False
        try:
             return await watchlist_cog.add_to_watchlist(player_tag, player_name, reason, details)
        except Exception as e:
             logger.error(f"Erro ao chamar add_to_watchlist: {e}", exc_info=True)
             return False

    async def remove_from_watchlist_admin(self, player_tag: str) -> bool:
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not watchlist_cog:
            return False
        try:
            return await watchlist_cog.remove_from_watchlist(player_tag)
        except Exception as e:
             logger.error(f"Erro ao chamar remove_from_watchlist: {e}", exc_info=True)
             return False

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
