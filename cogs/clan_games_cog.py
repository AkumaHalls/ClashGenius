# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import pytz
import datetime
from typing import Optional

logger = logging.getLogger("clan_games_cog")

# A classe agora herda de commands.Cog
class ClanGamesCog(commands.Cog):
    """Cog para gerenciar todas as funcionalidades dos Jogos do Clã."""
    
    # O construtor recebe o 'bot' para ter acesso a tudo que ele possui
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Acessamos os clientes e a conexão com o DB que foram anexados ao bot no clash.py
        self.api_client: coc.Client = bot.api_client
        self.db = bot.db
        self.clan_tag: str = bot.clan_tag
        self.channel_id: int = bot.clan_games_channel_id
        
        self.snapshot_collection = self.db.clan_games_snapshot if self.db else None
        
        # Inicia as tarefas em segundo plano
        self.auto_manage_clan_games.start()
        self.periodic_status_update.start()

    async def _is_snapshot_active(self) -> bool:
        """Verifica se existe um snapshot ativo no banco de dados."""
        if not self.snapshot_collection:
            return False
        return await self.snapshot_collection.count_documents({}) > 0

    async def take_snapshot(self, automated: bool = False):
        """Tira um snapshot dos pontos de todos os membros no início dos Jogos do Clã."""
        if not self.snapshot_collection: return

        if await self._is_snapshot_active():
            logger.warning("Tentativa de iniciar Jogos do Clã, mas um snapshot já está ativo.")
            return

        clan = await self.api_client.get_clan(self.clan_tag)
        if not clan: return

        snapshot_data = []
        for member in clan.members:
            try:
                player = await self.api_client.get_player(member.tag)
                games_achievement = player.get_achievement("Games Champion")
                snapshot_data.append({
                    "_id": player.tag,
                    "initial_points": games_achievement.value,
                    "name": player.name
                })
            except Exception as e:
                logger.error(f"Não foi possível obter dados para o jogador {member.name} ({member.tag}): {e}")

        if snapshot_data:
            await self.snapshot_collection.insert_many(snapshot_data)
            msg = f"✅ Monitoramento dos Jogos do Clã iniciado! Snapshot salvo para **{len(snapshot_data)}** membros."
            logger.info(msg)
            if automated:
                try:
                    channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
                    await channel.send(f"🎉 **Os Jogos do Clã começaram!**\n{msg}")
                except Exception as e:
                    logger.error(f"Falha ao enviar mensagem de início automático dos Jogos do Clã: {e}")

    async def clear_snapshot(self, automated: bool = False):
        """Limpa o snapshot, finalizando o monitoramento dos Jogos do Clã."""
        if not self.snapshot_collection: return
        
        await self.snapshot_collection.delete_many({})
        msg = "⏹️ Monitoramento dos Jogos do Clã finalizado. Dados limpos."
        logger.info(msg)
        if automated:
            try:
                channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
                await channel.send(msg)
            except Exception as e:
                 logger.error(f"Falha ao enviar mensagem de fim automático dos Jogos do Clã: {e}")

    @tasks.loop(hours=8)
    async def periodic_status_update(self):
        """Tarefa que roda em segundo plano para postar atualizações periódicas."""
        if await self._is_snapshot_active():
            logger.info("Enviando atualização periódica dos Jogos do Clã...")
            await self.post_status_update()
    
    @tasks.loop(hours=1)
    async def auto_manage_clan_games(self):
        """Verifica a cada hora se os Jogos do Clã devem começar ou terminar."""
        now_utc = datetime.datetime.now(pytz.utc)
        
        # Lógica de Início: dia 22, a partir das 8h UTC
        if now_utc.day == 22 and now_utc.hour >= 8 and not await self._is_snapshot_active():
            logger.info("Data de início dos Jogos do Clã detectada. Iniciando monitoramento automático.")
            await self.take_snapshot(automated=True)

        # Lógica de Fim: dia 28, a partir das 8h UTC
        if now_utc.day == 28 and now_utc.hour >= 8 and await self._is_snapshot_active():
            logger.info("Data de término dos Jogos do Clã detectada. Finalizando monitoramento.")
            await self.post_status_update(is_final_report=True)
            await self.clear_snapshot(automated=True)

    @periodic_status_update.before_loop
    @auto_manage_clan_games.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()
        
    # O comando agora está dentro do Cog, usando o decorador @commands.command()
    @commands.command(name='cgs')
    async def post_status_update(self, ctx: Optional[discord.Context] = None, is_final_report: bool = False):
        """Busca os dados, calcula os pontos e posta uma atualização no canal."""
        # Se for chamado por uma task, ctx será None
        is_manual_request = ctx is not None
        
        if not self.snapshot_collection or not await self._is_snapshot_active():
            if is_manual_request: await ctx.send("Nenhum monitoramento dos Jogos do Clã ativo no momento.")
            return
        
        if is_manual_request: await ctx.message.add_reaction("🔄")

        initial_data_cursor = self.snapshot_collection.find({})
        initial_data = {doc["_id"]: doc for doc in await initial_data_cursor.to_list(length=50)}
        clan = await self.api_client.get_clan(self.clan_tag)
        
        player_scores = []
        total_points = 0
        
        for member in clan.members:
            if member.tag in initial_data:
                try:
                    player = await self.api_client.get_player(member.tag)
                    current_points = player.get_achievement("Games Champion").value
                    initial_points = initial_data[member.tag]["initial_points"]
                    score = current_points - initial_points
                    player_scores.append({"name": member.name, "score": score})
                    total_points += score
                except Exception:
                    player_scores.append({"name": initial_data[member.tag]["name"], "score": 0})

        player_scores.sort(key=lambda x: x["score"], reverse=True)

        embed_title = "🏁 Relatório Final dos Jogos do Clã" if is_final_report else "🏅 Status dos Jogos do Clã"
        embed = discord.Embed(title=embed_title, color=discord.Color.gold())
        if clan.badge: embed.set_thumbnail(url=clan.badge.url)

        MAX_POINTS = 50000
        progress = min(total_points / MAX_POINTS, 1.0)
        filled_blocks = int(progress * 20)
        empty_blocks = 20 - filled_blocks
        progress_bar = "█" * filled_blocks + "░" * empty_blocks
        
        embed.add_field(
            name="Progresso Total do Clã",
            value=f"**{total_points:,} / {MAX_POINTS:,} Pontos**\n`{progress_bar}` {progress:.1%}",
            inline=False
        )

        top_contributors_str = ""
        for i, player in enumerate(player_scores[:10]): # Mostra o top 10
            if player['score'] > 0:
                top_contributors_str += f"`{i+1}.` **{player['name']}**: {player['score']:,} pontos\n"
        if not top_contributors_str: top_contributors_str = "Ninguém pontuou."
        
        embed.add_field(name="🏆 Maiores Contribuidores", value=top_contributors_str, inline=False)
        
        try:
            channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
            await channel.send(embed=embed)
            if is_manual_request:
                await ctx.message.remove_reaction("🔄", self.bot.user)
                await ctx.message.add_reaction("✅")
        except Exception as e:
            logger.error(f"Falha ao enviar status dos Jogos do Clã: {e}")
            if is_manual_request: await ctx.send(f"Erro ao enviar a mensagem: {e}")

# Função obrigatória no final de cada arquivo de Cog
# Ela permite que o bot carregue esta classe
async def setup(bot: commands.Bot):
    # Condição para só carregar o Cog se as configurações necessárias existirem
    if CLAN_GAMES_CHANNEL_ID and bot.db:
        await bot.add_cog(ClanGamesCog(bot))
        logger.info("Cog 'ClanGamesCog' carregado.")
    else:
        logger.warning("Cog 'ClanGamesCog' não carregado (ID do canal ou DB não configurado).")
