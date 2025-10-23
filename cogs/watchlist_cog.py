# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands
import coc
import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger("watchlist_cog")

class WatchlistCog(commands.Cog, name="Lista de Observação"):
    """Cog para gerenciar a lista de observação de jogadores."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.watchlist_collection = self.db.clan_watchlist if self.db is not None else None
        # <<< MODIFICADO: Busca ID do canal de alerta aqui, com fallback para canal principal >>>
        self.alert_channel_id = getattr(self.bot, 'watchlist_alert_channel_id', self.bot.channel_id)
        if not self.alert_channel_id:
             logger.warning("Nenhum ID de canal configurado para alertas da Watchlist (nem watchlist_alert_channel_id nem channel_id). Alertas desativados.")

    async def _send_watchlist_alert(self, member: coc.Player, entry: Dict[str, Any]):
        """Envia um alerta para o canal configurado."""
        if not self.alert_channel_id:
            logger.warning("_send_watchlist_alert: ID do canal de alerta não configurado.")
            return

        logger.info(f"Tentando enviar alerta para canal ID: {self.alert_channel_id}") # Log ID do canal

        try:
            channel = self.bot.get_channel(self.alert_channel_id) or await self.bot.fetch_channel(self.alert_channel_id)
            if not channel: # <<< Adicionado verificação se canal foi encontrado >>>
                logger.error(f"Não foi possível encontrar o canal de alerta com ID: {self.alert_channel_id}")
                return

            logger.info(f"Canal '{channel.name}' encontrado.") # Log nome do canal

            embed = discord.Embed(
                title="⚠️ ALERTA: Jogador da Lista de Observação Entrou!",
                description=f"O jogador **{member.name}** (`{member.tag}`) acabou de entrar no clã.",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now(self.bot.timezone) # Adiciona timestamp
            )
            embed.add_field(name="Motivo na Lista", value=f"_{entry.get('reason', 'Não especificado')}_", inline=False)
            if entry.get('details'):
                embed.add_field(name="Detalhes Adicionais", value=entry.get('details'), inline=False)

            # Formata a data de adição
            date_added_str = "Desconhecida"
            if isinstance(entry.get('date_added'), datetime.datetime):
                try:
                    date_added_str = entry['date_added'].strftime('%d/%m/%Y')
                except Exception: pass # Ignora erro de formatação
            elif isinstance(entry.get('date_added'), str): # Se já for string (do DB corrigido)
                 try:
                     # Tenta parsear e formatar, ou usa a string
                     dt_obj = datetime.datetime.fromisoformat(entry['date_added'].replace("Z", "+00:00"))
                     date_added_str = dt_obj.strftime('%d/%m/%Y')
                 except ValueError:
                      date_added_str = entry['date_added'] # Usa a string como fallback

            embed.add_field(name="Data de Adição à Lista", value=date_added_str, inline=True)

            # Adiciona TH e Liga atuais do membro
            embed.add_field(name="CV Atual", value=member.town_hall, inline=True)
            embed.add_field(name="Liga Atual", value=member.league.name if member.league else "N/A", inline=True)

            if member.league and member.league.icon:
                 embed.set_thumbnail(url=member.league.icon.medium)
            else: # Fallback para badge do clã se não tiver liga
                 clan_data = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
                 if clan_data and clan_data.badge:
                      embed.set_thumbnail(url=clan_data.badge.url)


            # Monta a menção dos cargos (se configurados)
            mention_content = ""
            leader_role_id = getattr(self.bot, 'leader_role_id', 0)
            coleader_role_id = getattr(self.bot, 'coleader_role_id', 0)
            if leader_role_id: mention_content += f"<@&{leader_role_id}> "
            if coleader_role_id: mention_content += f"<@&{coleader_role_id}> "
            if not mention_content: mention_content = "Atenção, Liderança!" # Mensagem padrão

            # <<< Adicionado log antes de enviar >>>
            logger.info(f"Enviando alerta para '{channel.name}' mencionando: '{mention_content}'")
            await channel.send(content=mention_content.strip(), embed=embed)
            logger.info(f"Alerta de Watchlist enviado com sucesso para {member.tag}.")

        except discord.Forbidden:
             logger.error(f"Sem permissão para enviar mensagem no canal de alerta ID: {self.alert_channel_id}")
        except discord.HTTPException as e:
             logger.error(f"Erro HTTP ao enviar alerta de Watchlist: {e.status} - {e.text}")
        except Exception as e:
            logger.error(f"Falha inesperada ao enviar alerta de Watchlist: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_clan_member_join(self, member: coc.Player, clan: coc.Clan):
        """Listener que verifica se o membro que entrou está na watchlist."""
        # Ignora eventos de outros clãs ou se o bot estiver em manutenção ou sem DB
        if self.bot.maintenance_mode or clan.tag != self.bot.clan_tag or self.watchlist_collection is None:
            # <<< Adicionado log para clareza >>>
            if clan.tag != self.bot.clan_tag: logger.debug(f"Evento member_join ignorado (clã {clan.tag} != {self.bot.clan_tag})")
            elif self.bot.maintenance_mode: logger.debug("Evento member_join ignorado (modo manutenção)")
            elif self.watchlist_collection is None: logger.debug("Evento member_join ignorado (DB não disponível)")
            return

        logger.info(f"Membro {member.name} ({member.tag}) entrou. Verificando watchlist...") # <<< Log Informativo >>>
        entry = await self.is_on_watchlist(member.tag)
        if entry:
            logger.info(f"Jogador {member.name} ({member.tag}) ENCONTRADO na watchlist. Acionando alerta.") # <<< Log Detalhado >>>
            await self._send_watchlist_alert(member, entry)
        else:
            logger.info(f"Jogador {member.name} ({member.tag}) NÃO encontrado na watchlist.") # <<< Log Detalhado >>>

    # --- Funções de Banco de Dados ---
    # (add_to_watchlist, remove_from_watchlist, is_on_watchlist, get_full_watchlist - MANTIDAS IGUAIS) ...
    async def add_to_watchlist(self, player_tag: str, player_name: str, reason: str, details: Optional[str] = None) -> bool:
        """Adiciona ou atualiza um jogador na watchlist."""
        if self.watchlist_collection is None: logger.error("Watchlist DB Collection não disponível."); return False
        try:
            player_tag_cleaned = coc.utils.correct_tag(player_tag)
            # Garante que a data seja UTC timezone-aware
            utc_now = datetime.datetime.now(datetime.timezone.utc)
            await self.watchlist_collection.update_one(
                {"_id": player_tag_cleaned},
                {"$set": {"name": player_name, "reason": reason, "details": details, "date_added": utc_now }}, upsert=True
            )
            logger.info(f"Jogador {player_name} ({player_tag_cleaned}) adicionado/atualizado na watchlist. Motivo: {reason}")
            return True
        except Exception as e: logger.error(f"Erro ao adicionar/atualizar {player_tag} na watchlist: {e}", exc_info=True); return False

    async def remove_from_watchlist(self, player_tag: str) -> bool:
        """Remove um jogador da watchlist."""
        if self.watchlist_collection is None: logger.error("Watchlist DB Collection não disponível."); return False
        try:
            player_tag_cleaned = coc.utils.correct_tag(player_tag)
            result = await self.watchlist_collection.delete_one({"_id": player_tag_cleaned})
            if result.deleted_count > 0: logger.info(f"Jogador {player_tag_cleaned} removido da watchlist."); return True
            else: logger.warning(f"Tentativa de remover {player_tag_cleaned}, mas não foi encontrado."); return False # Retorna False se não encontrou
        except Exception as e: logger.error(f"Erro ao remover {player_tag} da watchlist: {e}", exc_info=True); return False

    async def is_on_watchlist(self, player_tag: str) -> Optional[Dict[str, Any]]:
        """Verifica se um jogador está na watchlist e retorna os detalhes se estiver."""
        if self.watchlist_collection is None: return None
        try:
            player_tag_cleaned = coc.utils.correct_tag(player_tag)
            entry = await self.watchlist_collection.find_one({"_id": player_tag_cleaned})
            return entry
        except Exception as e: logger.error(f"Erro ao verificar {player_tag} na watchlist: {e}", exc_info=True); return None

    async def get_full_watchlist(self) -> List[Dict[str, Any]]:
        """Retorna todos os jogadores na watchlist."""
        if self.watchlist_collection is None: return []
        try:
            cursor = self.watchlist_collection.find({}).sort("name", 1)
            # Retorna a lista diretamente
            return await cursor.to_list(length=None)
        except Exception as e: logger.error(f"Erro ao buscar a watchlist completa: {e}", exc_info=True); return []


async def setup(bot: commands.Bot):
    # Só carrega o Cog se o banco de dados estiver configurado
    if bot.db is not None:
        await bot.add_cog(WatchlistCog(bot))
    else:
        logger.warning("Cog 'WatchlistCog' não carregado (Banco de dados não configurado).")
