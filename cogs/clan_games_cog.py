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
class ClanGamesCog(commands.Cog, name="Jogos do Clã"):
    """Cog para gerenciar todas as funcionalidades dos Jogos do Clã."""
    
    # O construtor recebe o 'bot' para ter acesso a tudo que ele possui
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Acessamos os clientes e a conexão com o DB que foram anexados ao bot no clash.py
        self.api_client: coc.Client = bot.api_client
        self.db = bot.db
        self.clan_tag: str = bot.clan_tag
        # Pega o ID do canal a partir da instância do bot
        self.channel_id: int = bot.clan_games_channel_id
        
        self.snapshot_collection = self.db.clan_games_snapshot if self.db else None
        
        # Inicia as tarefas em segundo plano
        self.auto_manage_clan_games.start()
        self.periodic_status_update.start()

    def cog_unload(self):
        """Função chamada quando o cog é descarregado, para parar as tasks."""
        self.auto_manage_clan_games.cancel()
        self.periodic_status_update.cancel()

    async def _is_snapshot_active(self) -> bool:
        """Verifica se existe um snapshot ativo no banco de dados."""
        if not self.snapshot_collection:
            return False
        return await self.snapshot_collection.count_documents({}) > 0

    async def take_snapshot(self, ctx: Optional[commands.Context] = None, automated: bool = False):
        """Tira um snapshot dos pontos de todos os membros no início dos Jogos do Clã."""
        if not self.snapshot_collection: 
            if ctx: await ctx.send("❌ O banco de dados não está configurado para os Jogos do Clã.")
            return

        if await self._is_snapshot_active():
            msg = "⚠️ O monitoramento dos Jogos do Clã já está ativo."
            logger.warning(msg)
            if ctx: await ctx.send(msg)
            return

        clan = await self.api_client.get_clan(self.clan_tag)
        if not clan: 
            if ctx: await ctx.send("❌ Não foi possível obter os dados do clã.")
            return

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
            
            # Envia a mensagem para o canal correto
            target_channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
            if automated:
                await target_channel.send(f"🎉 **Os Jogos do Clã começaram!**\n{msg}")
            elif ctx:
                await ctx.send(msg) # Responde ao comando
                await target_channel.send(f"▶️ Monitoramento iniciado manualmente por {ctx.author.mention}.")


    async def clear_snapshot(self, ctx: Optional[commands.Context] = None, automated: bool = False):
        """Limpa o snapshot, finalizando o monitoramento dos Jogos do Clã."""
        if not self.snapshot_collection: return
        
        await self.snapshot_collection.delete_many({})
        msg = "⏹️ Monitoramento dos Jogos do Clã finalizado. Dados limpos."
        logger.info(msg)
        
        # Envia a mensagem para o canal correto
        target_channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
        if automated:
            await target_channel.send(msg)
        elif ctx:
            await ctx.send(msg) # Responde ao comando
            await target_channel.send(f"⏹️ Monitoramento finalizado manualmente por {ctx.author.mention}.")


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
        
    # --- GRUPO DE COMANDOS 'cgs' ---
    @commands.group(name='cgs', invoke_without_command=True)
    async def cgs_group(self, ctx: commands.Context):
        """Grupo de comandos para os Jogos do Clã. Use '!cgs status' para ver o placar."""
        # Se chamado sem subcomando, executa o status por padrão
        await self.post_status_update(ctx)
    
    @cgs_group.command(name='status')
    async def post_status_update_command(self, ctx: commands.Context):
        """Posta uma atualização do status dos Jogos do Clã."""
        await self.post_status_update(ctx)

    @cgs_group.command(name='start')
    @commands.has_permissions(administrator=True)
    async def start_manual_cgs(self, ctx: commands.Context):
        """(Admin) Inicia manualmente o monitoramento dos Jogos do Clã."""
        await self.take_snapshot(ctx=ctx)

    @cgs_group.command(name='stop')
    @commands.has_permissions(administrator=True)
    async def stop_manual_cgs(self, ctx: commands.Context):
        """(Admin) Para manualmente o monitoramento dos Jogos do Clã."""
        await self.clear_snapshot(ctx=ctx)

    async def post_status_update(self, ctx: Optional[discord.Context] = None, is_final_report: bool = False):
        """Busca os dados, calcula os pontos e posta uma atualização no canal."""
        is_manual_request = ctx is not None
        
        if not self.snapshot_collection or not await self._is_snapshot_active():
            if is_manual_request: await ctx.send("Nenhum monitoramento dos Jogos do Clã ativo no momento.")
            return
        
        if is_manual_request: await ctx.message.add_reaction("🔄")

        try:
            initial_data_cursor = self.snapshot_collection.find({})
            initial_data = {doc["_id"]: doc for doc in await initial_data_cursor.to_list(length=100)}
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
                    top_contributors_str += f"`{i+1:2}.` **{player['name']}**: {player['score']:,} pontos\n"
            if not top_contributors_str: top_contributors_str = "Ninguém pontuou ainda."
            
            embed.add_field(name="🏆 Maiores Contribuidores", value=top_contributors_str, inline=False)
            
            channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
            await channel.send(embed=embed)
            if is_manual_request:
                await ctx.message.remove_reaction("🔄", self.bot.user)
                await ctx.message.add_reaction("✅")
        except Exception as e:
            logger.error(f"Falha ao enviar status dos Jogos do Clã: {e}", exc_info=True)
            if is_manual_request: 
                try:
                    await ctx.message.remove_reaction("🔄", self.bot.user)
                    await ctx.message.add_reaction("❌")
                    await ctx.send(f"Ocorreu um erro ao gerar o relatório: {e}")
                except discord.HTTPException:
                    pass

# Função obrigatória no final de cada arquivo de Cog
async def setup(bot: commands.Bot):
    # A verificação agora usa os atributos anexados ao bot
    # Isso garante que o cog só carregue se o bot estiver configurado corretamente
    if hasattr(bot, 'clan_games_channel_id') and bot.clan_games_channel_id and hasattr(bot, 'db') and bot.db:
        await bot.add_cog(ClanGamesCog(bot))
    else:
        logger.warning("Cog 'ClanGamesCog' não foi carregado porque o ID do canal dos Jogos do Clã ou a conexão com o banco de dados não estão configurados na instância do bot.")

