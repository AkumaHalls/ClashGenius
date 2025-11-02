# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import DESCENDING
import coc
from typing import Dict, Any, Optional, List # <<< ADICIONADO List
import datetime
import json # Import json for dumps default

logger = logging.getLogger("admin_cog")

class AdminCog(commands.Cog, name="Painel de Administração Avançado"):
    """Cog para gerenciar a lógica do backend do painel de administração avançado."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        # Referências de cogs são obtidas "just-in-time"

    # ... (sync_commands, get_api_status, get_diagnostics, get_settings, update_settings, get_db_viewer_data, send_announcement, clear_web_cache - MANTIDOS IGUAIS) ...
    async def sync_commands(self, scope: str, guild: Optional[discord.Guild] = None) -> Dict[str, Any]:
        """Lógica centralizada para sincronizar comandos de barra."""
        target_guild = guild if scope == 'guild' else None
        scope_name = f"o servidor '{guild.name}'" if target_guild else "globalmente"
        logger.info(f"Sincronização iniciada para o escopo: {scope_name}")
        try:
            # Limpa comandos antigos antes de sincronizar
            # Para limpar globalmente, não passe 'guild'
            if scope == 'global':
                 self.bot.tree.clear_commands(guild=None)
                 await self.bot.tree.sync()
                 logger.info("Comandos globais limpos.")
            # Para limpar no servidor específico
            elif target_guild:
                 self.bot.tree.clear_commands(guild=target_guild)
                 await self.bot.tree.sync(guild=target_guild)
                 logger.info(f"Comandos limpos no servidor {target_guild.name}.")

            # Sincroniza os comandos atuais
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
             # Se o cliente nem existe, é um erro interno do bot ou falha grave no login
             logger.error("get_api_status: Tentativa de verificar status sem api_client.")
             return {"status": "error", "message": "Erro interno: Cliente CoC não inicializado."}
        try:
            # Tenta uma chamada leve à API para verificar a conexão e autenticação
            await self.bot.api_client.get_clan(self.bot.clan_tag) # Usar tag do clã configurada
            return {"status": "ok", "message": "API do Clash of Clans operacional."}
        except coc.errors.Maintenance:
            logger.warning("API CoC está em manutenção.")
            return {"status": "maintenance", "message": "A API do Clash of Clans está em manutenção. Tente novamente mais tarde."}
        except coc.errors.LoginError: # Trata erro de login aqui também
             logger.error("Erro de autenticação com a API CoC.")
             # Tentar relogar pode causar loops, melhor sinalizar o erro
             # self.bot.coc_client_ready.clear()
             # self.bot.api_client = None
             # asyncio.create_task(self.bot.coc_login_task())
             return {"status": "error", "message": "Erro de autenticação com a API CoC. Verifique as credenciais."}
        except coc.errors.NotFound:
             logger.error(f"Erro ao verificar status: Clã {self.bot.clan_tag} não encontrado. Verifique CLAN_TAG.")
             return {"status": "error", "message": f"Erro de configuração: Clã {self.bot.clan_tag} não encontrado."}
        except Exception as e:
            # Captura outros erros de conexão ou inesperados
            logger.error(f"Erro inesperado ao verificar status da API: {type(e).__name__} - {e}", exc_info=False) # Log mais conciso
            return {"status": "error", "message": f"Erro de conexão com a API: Acesso temporariamente indisponível."}

    async def get_diagnostics(self) -> Dict[str, Any]:
        """Coleta dados de diagnóstico do bot."""
        api_status = await self.get_api_status()
        # Garante que log_handler existe
        recent_logs = getattr(self.bot, 'log_handler', None)
        log_buffer = recent_logs.buffer if recent_logs else ["Log handler não encontrado."]
        return {
            "api_status": api_status,
            "recent_logs": log_buffer
        }

    # <<< INÍCIO DA ALTERAÇÃO (get_settings) >>>
    async def get_settings(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Obtém as configurações atuais do bot, mesclando com defaults e buscando nomes de canais/cargos."""
        
        # 1. Tenta obter o Guild (servidor) a partir da sessão do usuário
        guild_id_str = session.get('guild_id')
        guild = None
        if guild_id_str:
            try:
                guild = self.bot.get_guild(int(guild_id_str))
            except (ValueError, TypeError):
                logger.warning(f"get_settings: guild_id inválido na sessão: {guild_id_str}")
        if not guild and guild_id_str:
            logger.warning(f"get_settings: Não foi possível encontrar o Guild (servidor) ID: {guild_id_str}. Nomes de cargos não serão carregados.")
        elif not guild_id_str:
            logger.warning("get_settings: Usuário não logou com ID do Servidor. Nomes de cargos não serão carregados.")


        # 2. Define os valores default (como números)
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

        # 3. Busca configurações do DB
        merged_settings = defaults.copy() # Começa com os defaults
        if self.db is not None:
            try:
                settings_from_db = await self.db.system_config.find_one({"_id": "bot_settings"})
                if settings_from_db:
                    merged_settings.update(settings_from_db) # Sobrescreve defaults com valores do DB
                else:
                    logger.warning("Documento 'bot_settings' não encontrado, usando defaults.")
            except Exception as e:
                logger.error(f"Erro ao buscar settings do DB: {e}", exc_info=True)
        else:
             logger.warning("DB não disponível, retornando configurações default.")

        merged_settings.pop('_id', None) # Remove ID interno

        # 4. Prepara o dicionário final com nomes
        settings_with_names = {}

        for key, value in merged_settings.items():
            # Se for um ID de canal ou cargo...
            if ("_id" in key or "channel_id" in key) and isinstance(value, (int, float, str)):
                id_str = str(value)
                id_int = 0
                try:
                    id_int = int(id_str)
                except (ValueError, TypeError):
                    pass # Mantém 0 se não for um ID válido
                
                if id_int == 0:
                    settings_with_names[key] = {"id": id_str, "name": "Nenhum"}
                    continue

                item_name = "Não encontrado"
                
                # Tenta buscar
                if "channel_id" in key:
                    channel = self.bot.get_channel(id_int)
                    if channel:
                        item_name = f"#{channel.name}"
                
                elif "role_id" in key:
                    role = None
                    if guild: # Só busca cargos se o guild foi encontrado
                        role = guild.get_role(id_int)
                    if role:
                        item_name = f"@{role.name}"
                    elif guild:
                        item_name = "Cargo não encontrado"
                    else:
                        item_name = "Sem Info do Servidor"
                
                # Armazena o ID (como string) e o nome
                settings_with_names[key] = {"id": id_str, "name": item_name}

            # Converte booleano para string para o select (HTML)
            elif key == "auto_add_watchlist_enabled":
                settings_with_names[key] = "true" if value else "false"
            
            # Mantém outros valores (como maintenance_message)
            else:
                settings_with_names[key] = value

        return settings_with_names
    # <<< FIM DA ALTERAÇÃO (get_settings) >>>

    async def update_settings(self, new_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza as configurações no bot e no banco de dados."""
        if self.db is None: return {"status": "error", "message": "Banco de dados não configurado."}
        update_data = {}
        successful_updates = {}
        for key, value in new_settings.items():
            try:
                processed_value = value
                
                # O Javascript agora envia IDs como STRING para preservar a precisão.
                # O Python DEVE converter essa string para int antes de salvar no DB
                # e de atualizar o atributo do bot (que espera int).
                if isinstance(value, str) and ("_id" in key or "channel_id" in key) and value.isdigit():
                    try:
                        processed_value = int(value) # Converte a string longa para int (Python suporta)
                    except ValueError:
                         logger.warning(f"Valor de ID inválido '{value}' para '{key}'. Ignorando conversão.")
                         processed_value = value # Mantém como string se falhar (improvável)
                
                # Converte flag booleana
                elif key == "auto_add_watchlist_enabled":
                     processed_value = str(value).lower() in ['true', 'on', '1', 'yes']

                # Atualiza o atributo no bot se ele existir
                if hasattr(self.bot, key):
                    setattr(self.bot, key, processed_value)
                    successful_updates[key] = processed_value # Guarda o valor processado
                else:
                     logger.warning(f"Tentativa de atualizar setting inexistente no bot: '{key}'")

                # Adiciona ao dict para salvar no DB (sempre salva, mesmo que não exista no bot)
                update_data[key] = processed_value

            except (ValueError, TypeError) as e:
                 logger.warning(f"Erro ao processar setting '{key}' com valor '{value}': {e}. Usando valor original.")
                 # Tenta salvar o valor original se a conversão falhar
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
             # Busca últimas guerras, tratando ausência de campos
             wars_cursor = self.db.war_history.find(
                 {},
                 {"war_data.opponent_name": 1, "war_data.end_time_iso": 1, "_id": 1}
             ).sort("war_data.end_time_iso", DESCENDING).limit(5)
             last_wars = [
                 {"opponent": w.get("war_data", {}).get("opponent_name", "N/A"),
                  "end_time": w.get("war_data", {}).get("end_time_iso"), # Deixa como ISO para JS formatar
                  "id": w.get("_id")}
                 async for w in wars_cursor if w.get("_id") # Garante que tem ID
             ]

             # Busca últimas notas
             notes_cursor = self.db.player_notes.find({}).sort([("$natural", -1)]).limit(5)
             last_notes = [
                 {"player_tag": n.get("_id"),
                  "note": n.get("text", ""),
                  "priority": n.get("priority", "none")}
                 async for n in notes_cursor if n.get("_id") # Garante que tem ID (_id é a tag)
             ]
             return {"last_wars": last_wars, "last_notes": last_notes}
        except Exception as e:
             logger.error(f"Erro ao buscar dados para DB viewer: {e}", exc_info=True)
             return {"error": "Erro ao buscar dados do banco."}

    async def send_announcement(self, channel_id_str: str, message: str) -> Dict[str, Any]:
        # (Código mantido igual)
        if not channel_id_str or not message: return {"status": "error", "message": "ID do canal e mensagem são obrigatórios."}
        try:
            channel_id = int(channel_id_str); channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            embed = discord.Embed(title="📢 Anúncio do Administrador",description=message,color=discord.Color.orange(),timestamp=datetime.datetime.now(self.bot.timezone))
            embed.set_footer(text=f"Enviado via Painel Clash Genius v{self.bot.bot_version}")
            await channel.send(embed=embed)
            logger.info(f"Anúncio enviado para o canal {channel_id} via painel.")
            return {"status": "success", "message": "Anúncio enviado com sucesso!"}
        except ValueError: return {"status": "error", "message": "O ID do canal deve ser um número."}
        except (discord.NotFound, discord.Forbidden): return {"status": "error", "message": "Canal não encontrado ou sem permissão."}
        except Exception as e: logger.error(f"Erro ao enviar anúncio: {e}", exc_info=True); return {"status": "error", "message": f"Erro interno: {e}"}

    async def clear_web_cache(self, cache_key: str) -> Dict[str, Any]:
        # (Código mantido igual)
        if cache_key == 'all': self.bot.web_api_cache.clear(); logger.info("Cache web limpo via painel."); return {"status": "success", "message": "Todo o cache da web foi limpo."}
        elif cache_key in self.bot.web_api_cache: self.bot.web_api_cache.pop(cache_key); logger.info(f"Cache '{cache_key}' limpo via painel."); return {"status": "success", "message": f"Cache '{cache_key}' foi limpo."}
        return {"status": "not_found", "message": f"Cache '{cache_key}' não encontrado."}

    # --- Funções para interagir com WatchlistCog (chamadas pela API web) ---
    async def get_watchlist_admin(self) -> List[Dict[str, Any]]: # <<< CORRIGIDO: Retorna List[Dict] ou Dict com erro
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not watchlist_cog:
            logger.error("get_watchlist_admin: Watchlist Cog não carregada.")
            return {"error": "Watchlist Cog não carregada."} # Retorna dict de erro

        try:
            watchlist_data = await watchlist_cog.get_full_watchlist()
            # <<< ADICIONADO: Converte datetime para string ISO >>>
            processed_data = []
            for player in watchlist_data:
                if 'date_added' in player and isinstance(player['date_added'], datetime.datetime):
                    player['date_added'] = player['date_added'].isoformat() # Converte para string
                processed_data.append(player)
            return processed_data
        except Exception as e:
            logger.error(f"Erro ao buscar/processar watchlist: {e}", exc_info=True)
            return {"error": "Erro interno ao buscar watchlist."} # Retorna dict de erro


    async def add_to_watchlist_admin(self, player_tag: str, player_name: str, reason: str, details: Optional[str] = None) -> bool:
        # <<< CORRIGIDO: Retorna bool como esperado pelas rotas >>>
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not watchlist_cog:
            logger.error("add_to_watchlist_admin: Watchlist Cog não carregada.")
            return False # Indica falha
        try:
             # Chama a função do cog e retorna seu resultado (True/False)
             return await watchlist_cog.add_to_watchlist(player_tag, player_name, reason, details)
        except Exception as e:
             logger.error(f"Erro ao chamar add_to_watchlist: {e}", exc_info=True)
             return False # Indica falha


    async def remove_from_watchlist_admin(self, player_tag: str) -> bool:
        # <<< CORRIGIDO: Retorna bool como esperado pelas rotas >>>
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not watchlist_cog:
            logger.error("remove_from_watchlist_admin: Watchlist Cog não carregada.")
            return False # Indica falha
        try:
            # Chama a função do cog e retorna seu resultado (True/False)
            return await watchlist_cog.remove_from_watchlist(player_tag)
        except Exception as e:
             logger.error(f"Erro ao chamar remove_from_watchlist: {e}", exc_info=True)
             return False # Indica falha


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))

