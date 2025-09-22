# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import pytz
import datetime
from typing import Optional

logger = logging.getLogger("clan_games_cog")

class ClanGamesCog(commands.Cog, name="Jogos do Clã"):
    """Cog para gerenciar todas as funcionalidades dos Jogos do Clã."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.clan_tag: str = bot.clan_tag
        self.channel_id: int = bot.clan_games_channel_id
        
        self.snapshot_collection = self.db.clan_games_snapshot if self.db is not None else None
        
        self.auto_manage_clan_games.start()
        self.periodic_status_update.start()

    async def cog_unload(self):
        """Para as tasks quando o cog é descarregado."""
        self.auto_manage_clan_games.cancel()
        self.periodic_status_update.cancel()

    async def _is_snapshot_active(self) -> bool:
        """Verifica se existe um snapshot ativo no banco de dados."""
        if self.snapshot_collection is None:
            return False
        return await self.snapshot_collection.count_documents({}) > 0

    async def _send_to_channel(self, message: str = None, embed: discord.Embed = None):
        """Envia uma mensagem ou embed para o canal configurado."""
        if not self.channel_id:
            logger.warning("ID do canal dos Jogos do Clã não configurado.")
            return
        try:
            channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
            await channel.send(content=message, embed=embed)
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem para o canal dos Jogos do Clã: {e}")

    async def take_snapshot(self, automated: bool = False):
        """Tira um snapshot dos pontos de todos os membros no início dos Jogos do Clã."""
        if self.snapshot_collection is None: return

        if await self._is_snapshot_active() and automated:
            logger.warning("Tentativa de iniciar Jogos do Clã automaticamente, mas um snapshot já está ativo.")
            return

        # CORREÇÃO: Mesmo que não seja automatizado, se já houver um snapshot, limpamos primeiro.
        if await self._is_snapshot_active():
            await self.clear_snapshot(automated=False, silent=True) # Limpa silenciosamente antes de um novo start manual

        clan = await self.bot.api_client.get_clan(self.clan_tag)
        if not clan: return

        snapshot_data = []
        # A API retorna o valor da conquista ANTES do evento começar.
        # Precisamos buscar os dados históricos dos jogadores para pegar o valor real.
        # Esta é uma limitação da API que contornamos com o snapshot.
        # A lógica assume que os pontos da conquista "Games Champion" são o total histórico.
        for member in clan.members:
            try:
                player = await self.bot.api_client.get_player(member.tag)
                games_achievement = player.get_achievement("Games Champion")
                # No momento do snapshot, o valor atual da conquista é o ponto inicial.
                # Se alguém já pontuou, precisamos subtrair essa pontuação para ter o valor real de "início".
                # A API não nos dá o placar atual dos jogos, apenas o valor da conquista.
                # A lógica de cálculo (current - initial) depende de um snapshot TIRADO NO MOMENTO CERTO.
                # A melhor aproximação que podemos fazer agora é pegar o valor atual da conquista.
                initial_points_value = games_achievement.value

                # Se o bot tirou o snapshot tarde, o "initial_points_value" já inclui os pontos atuais.
                # A única forma de corrigir é apagar e tirar um novo, o que não temos como "voltar no tempo".
                # A solução mais robusta é instruir o usuário a usar `!cgs stop` e `!cgs start` para resetar.
                
                snapshot_data.append({
                    "_id": player.tag,
                    "initial_points": initial_points_value,
                    "name": player.name
                })
            except Exception as e:
                logger.error(f"Não foi possível obter dados para o jogador {member.name} ({member.tag}): {e}")

        if snapshot_data:
            await self.snapshot_collection.insert_many(snapshot_data)
            msg = f"✅ Monitoramento dos Jogos do Clã iniciado! Snapshot salvo para **{len(snapshot_data)}** membros."
            logger.info(msg)
            if automated:
                await self._send_to_channel(message=f"🎉 **Os Jogos do Clã começaram!**\n{msg}")

    async def clear_snapshot(self, automated: bool = False, silent: bool = False):
        """Limpa o snapshot, finalizando o monitoramento dos Jogos do Clã."""
        if self.snapshot_collection is None: return
        
        await self.snapshot_collection.delete_many({})
        msg = "⏹️ Monitoramento dos Jogos do Clã finalizado. Dados limpos."
        logger.info(msg)
        if automated and not silent:
            await self._send_to_channel(message=msg)

    @tasks.loop(hours=8)
    async def periodic_status_update(self):
        """Tarefa que roda em segundo plano para postar atualizações periódicas."""
        if await self._is_snapshot_active():
            logger.info("Enviando atualização periódica dos Jogos do Clã...")
            await self.post_status_update()
    
    @tasks.loop(minutes=15)
    async def auto_manage_clan_games(self):
        """Verifica a cada 15 minutos se os Jogos do Clã devem começar ou terminar."""
        now_utc = datetime.datetime.now(pytz.utc)
        
        if now_utc.day >= 22 and now_utc.day < 28 and not await self._is_snapshot_active():
            logger.info("Período dos Jogos do Clã ativo e sem snapshot. Iniciando monitoramento.")
            await self.take_snapshot(automated=True)

        if now_utc.day >= 28 and await self._is_snapshot_active():
            logger.info("Data de término dos Jogos do Clã detectada. Finalizando monitoramento.")
            await self.post_status_update(is_final_report=True)
            await self.clear_snapshot(automated=True)

    @periodic_status_update.before_loop
    @auto_manage_clan_games.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()
        
    @commands.group(name='cgs', invoke_without_command=True)
    async def cgs(self, ctx: commands.Context):
        """Grupo de comandos para os Jogos do Clã. Mostra o status por padrão."""
        await self.post_status_update(ctx)

    @cgs.command(name='start')
    @commands.has_permissions(administrator=True)
    async def cgs_start(self, ctx: commands.Context):
        """(Admin) Força o início do monitoramento dos Jogos do Clã, limpando qualquer snapshot anterior."""
        await ctx.message.add_reaction("🔄")
        # MELHORIA: Limpa antes de começar para garantir um estado limpo.
        await self.clear_snapshot(automated=False, silent=True)
        await self.take_snapshot(automated=False)
        await ctx.message.remove_reaction("🔄", self.bot.user)
        await ctx.message.add_reaction("✅")
        await ctx.send("Monitoramento dos Jogos do Clã (re)iniciado manualmente.")

    @cgs.command(name='stop')
    @commands.has_permissions(administrator=True)
    async def cgs_stop(self, ctx: commands.Context):
        """(Admin) Força o fim do monitoramento dos Jogos do Clã."""
        if not await self._is_snapshot_active():
            await ctx.send("O monitoramento não está ativo.")
            return
        await self.post_status_update(ctx, is_final_report=True)
        await self.clear_snapshot(automated=False)
        await ctx.send("Monitoramento dos Jogos do Clã finalizado manualmente.")

    async def post_status_update(self, ctx: Optional[commands.Context] = None, is_final_report: bool = False):
        """Busca os dados, calcula os pontos e posta uma atualização."""
        is_manual_request = ctx is not None
        
        if not await self._is_snapshot_active():
            if is_manual_request: await ctx.send("Nenhum monitoramento dos Jogos do Clã ativo no momento.")
            return
        
        if is_manual_request: await ctx.message.add_reaction("🔄")

        initial_data_cursor = self.snapshot_collection.find({})
        initial_data = {doc["_id"]: doc for doc in await initial_data_cursor.to_list(length=50)}
        clan = await self.bot.api_client.get_clan(self.clan_tag)
        
        player_scores = []
        total_points = 0
        
        for member in clan.members:
            if member.tag in initial_data:
                try:
                    player = await self.bot.api_client.get_player(member.tag)
                    current_points = player.get_achievement("Games Champion").value
                    initial_points = initial_data[member.tag]["initial_points"]
                    score = current_points - initial_points
                    # Garante que a pontuação não seja negativa se um membro entrou depois do snapshot
                    score = max(0, score)
                    player_scores.append({"name": member.name, "score": score})
                    total_points += score
                except Exception:
                    player_scores.append({"name": initial_data[member.tag].get("name", member.name), "score": 0})
        
        # Adiciona membros que entraram depois do snapshot mas já pontuaram.
        # Esta lógica é complexa devido à natureza da API e pode ser omitida pela simplicidade.
        # Por enquanto, focamos em corrigir o bug principal.

        player_scores.sort(key=lambda x: x["score"], reverse=True)

        embed_title = "🏁 Relatório Final dos Jogos do Clã" if is_final_report else "🏅 Status dos Jogos do Clã"
        embed = discord.Embed(title=embed_title, color=discord.Color.gold())
        if clan.badge: embed.set_thumbnail(url=clan.badge.url)

        MAX_POINTS = 50000
        progress = min(total_points / MAX_POINTS, 1.0)
        filled_blocks = int(progress * 20)
        progress_bar = "█" * filled_blocks + "░" * (20 - filled_blocks)
        
        embed.add_field(
            name="Progresso Total do Clã",
            value=f"**{total_points:,} / {MAX_POINTS:,} Pontos**\n`{progress_bar}` {progress:.1%}",
            inline=False
        )

        top_contributors_str = ""
        for i, player in enumerate(player_scores[:10]):
            if player['score'] > 0:
                top_contributors_str += f"`{i+1}.` **{player['name']}**: {player['score']:,} pontos\n"
        if not top_contributors_str: top_contributors_str = "Ninguém pontuou (ou o snapshot precisa ser resetado)."
        
        embed.add_field(name="🏆 Maiores Contribuidores", value=top_contributors_str, inline=False)
        
        if is_manual_request:
            await ctx.send(embed=embed)
        else:
            await self._send_to_channel(embed=embed)
        
        if is_manual_request:
            await ctx.message.remove_reaction("🔄", self.bot.user)
            await ctx.message.add_reaction("✅")

async def setup(bot: commands.Bot):
    if bot.clan_games_channel_id and bot.db is not None:
        await bot.add_cog(ClanGamesCog(bot))
    else:
        logger.warning("Cog 'ClanGamesCog' não carregado (ID do canal ou DB não configurado).")

