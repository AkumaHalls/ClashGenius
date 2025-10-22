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
        # Garante que a coleção só é acessada se a BD existir
        self.watchlist_collection = self.db.clan_watchlist if self.db is not None else None
        # ID do canal para enviar alertas (pode ser configurável futuramente)
        self.alert_channel_id = bot.channel_id # Usando o canal de logs principal por padrão

    async def _send_watchlist_alert(self, member: coc.Player, entry: Dict[str, Any]):
        """Envia um alerta para o canal configurado."""
        if not self.alert_channel_id:
            logger.warning("ID do canal de alerta da Watchlist não configurado.")
            return

        try:
            channel = self.bot.get_channel(self.alert_channel_id) or await self.bot.fetch_channel(self.alert_channel_id)

            embed = discord.Embed(
                title="⚠️ ALERTA: Jogador da Lista de Observação Entrou!",
                description=f"O jogador **{member.name}** (`{member.tag}`) acabou de entrar no clã.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Motivo na Lista", value=f"_{entry.get('reason', 'Não especificado')}_", inline=False)
            if entry.get('details'):
                embed.add_field(name="Detalhes Adicionais", value=entry.get('details'), inline=False)
            embed.add_field(name="Data de Adição à Lista", value=entry.get('date_added', 'Desconhecida').strftime('%d/%m/%Y'), inline=True)
            embed.set_thumbnail(url=member.league.icon.medium if member.league and member.league.icon else None)

            # Marca cargos de liderança (exemplo, precisa ajustar IDs)
            # leader_role_id = 12345
            # coleader_role_id = 67890
            # content = f"<@&{leader_role_id}> <@&{coleader_role_id}> Atenção!"
            content = "Atenção, Liderança!" # Mensagem padrão

            await channel.send(content=content, embed=embed)
            logger.info(f"Alerta de Watchlist enviado para o canal {self.alert_channel_id} sobre o jogador {member.tag}.")

        except Exception as e:
            logger.error(f"Falha ao enviar alerta de Watchlist: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_clan_member_join(self, member: coc.Player, clan: coc.Clan):
        """Listener que verifica se o membro que entrou está na watchlist."""
        # Ignora eventos de outros clãs ou se o bot estiver em manutenção ou sem DB
        if self.bot.maintenance_mode or clan.tag != self.bot.clan_tag or self.watchlist_collection is None:
            return

        logger.debug(f"Verificando watchlist para {member.name} ({member.tag}) que entrou no clã.")
        entry = await self.is_on_watchlist(member.tag)
        if entry:
            logger.info(f"Jogador {member.name} ({member.tag}) encontrado na watchlist. Enviando alerta.")
            await self._send_watchlist_alert(member, entry)
        else:
            logger.debug(f"Jogador {member.name} ({member.tag}) não encontrado na watchlist.")

    # --- Funções de Banco de Dados ---

    async def add_to_watchlist(self, player_tag: str, player_name: str, reason: str, details: Optional[str] = None) -> bool:
        """Adiciona ou atualiza um jogador na watchlist."""
        if self.watchlist_collection is None:
            logger.error("Watchlist DB Collection não disponível.")
            return False
        try:
            player_tag_cleaned = coc.utils.correct_tag(player_tag)
            await self.watchlist_collection.update_one(
                {"_id": player_tag_cleaned},
                {
                    "$set": {
                        "name": player_name,
                        "reason": reason,
                        "details": details,
                        "date_added": datetime.datetime.now(datetime.timezone.utc)
                    }
                },
                upsert=True
            )
            logger.info(f"Jogador {player_name} ({player_tag_cleaned}) adicionado/atualizado na watchlist. Motivo: {reason}")
            return True
        except Exception as e:
            logger.error(f"Erro ao adicionar/atualizar {player_tag} na watchlist: {e}", exc_info=True)
            return False

    async def remove_from_watchlist(self, player_tag: str) -> bool:
        """Remove um jogador da watchlist."""
        if self.watchlist_collection is None:
            logger.error("Watchlist DB Collection não disponível.")
            return False
        try:
            player_tag_cleaned = coc.utils.correct_tag(player_tag)
            result = await self.watchlist_collection.delete_one({"_id": player_tag_cleaned})
            if result.deleted_count > 0:
                logger.info(f"Jogador {player_tag_cleaned} removido da watchlist.")
                return True
            else:
                logger.warning(f"Tentativa de remover {player_tag_cleaned} da watchlist, mas não foi encontrado.")
                return False
        except Exception as e:
            logger.error(f"Erro ao remover {player_tag} da watchlist: {e}", exc_info=True)
            return False

    async def is_on_watchlist(self, player_tag: str) -> Optional[Dict[str, Any]]:
        """Verifica se um jogador está na watchlist e retorna os detalhes se estiver."""
        if self.watchlist_collection is None:
            return None
        try:
            player_tag_cleaned = coc.utils.correct_tag(player_tag)
            entry = await self.watchlist_collection.find_one({"_id": player_tag_cleaned})
            return entry
        except Exception as e:
            logger.error(f"Erro ao verificar {player_tag} na watchlist: {e}", exc_info=True)
            return None

    async def get_full_watchlist(self) -> List[Dict[str, Any]]:
        """Retorna todos os jogadores na watchlist."""
        if self.watchlist_collection is None:
            return []
        try:
            cursor = self.watchlist_collection.find({}).sort("name", 1)
            return await cursor.to_list(length=None) # Retorna todos os documentos
        except Exception as e:
            logger.error(f"Erro ao buscar a watchlist completa: {e}", exc_info=True)
            return []

async def setup(bot: commands.Bot):
    # Só carrega o Cog se o banco de dados estiver configurado
    if bot.db is not None:
        await bot.add_cog(WatchlistCog(bot))
    else:
        logger.warning("Cog 'WatchlistCog' não carregado (Banco de dados não configurado).")
