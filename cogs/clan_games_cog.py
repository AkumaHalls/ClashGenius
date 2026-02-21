# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
import pytz
import datetime
from typing import Optional, List, Dict, Any
import asyncio

logger = logging.getLogger("clan_games_cog")

class ClanGamesCog(commands.Cog, name="Jogos do Clã"):
    """Cog para gerenciar todas as funcionalidades dos Jogos do Clã e enviar para a Web."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.clan_tag: str = bot.clan_tag
        self.snapshot_collection = self.db.clan_games_snapshot if self.db is not None else None
        
        # Guarda quem já platinou nesta temporada para não avisar repetido no Discord
        self.already_congratulated = set()

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
        return await self.snapshot_collection.find_one({}) is not None

    async def _send_to_channel(self, message: str = None, embed: discord.Embed = None, embeds: List[discord.Embed] = None):
        """Envia mensagens para o canal de Eventos configurado pelo Admin."""
        channel_id = self.bot.clan_games_channel_id
        if not channel_id:
            logger.warning("ID do canal dos Jogos do Clã não configurado.")
            return
        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if embeds: 
                for emb in embeds:
                    await channel.send(embed=emb)
                    await asyncio.sleep(0.5) 
            elif embed: 
                await channel.send(embed=embed)
            elif message: 
                await channel.send(content=message)
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem para o canal dos Jogos do Clã: {e}", exc_info=True)


    async def fetch_clan_games_data_for_web(self) -> Dict[str, Any]:
        """Calcula os pontos em tempo real e envia para ser renderizado no painel web."""
        if not await self._is_snapshot_active():
            return {"error": "Os Jogos do Clã não estão ativos no momento."}

        try:
            initial_data_cursor = self.snapshot_collection.find({})
            initial_data = {doc["_id"]: doc for doc in await initial_data_cursor.to_list(length=None)}
            
            clan = await self.bot.api_client.get_clan(self.clan_tag)
            if not clan:
                 return {"error": "Falha de comunicação com a API da Supercell."}

            player_scores = []
            total_points = 0
            processed_tags = set()

            # Processa membros que estavam no clan na hora que os jogos começaram
            for member_tag, initial_info in initial_data.items():
                processed_tags.add(member_tag)
                member_in_clan = clan.get_member(member_tag)
                
                if member_in_clan:
                    try:
                        player = await self.bot.api_client.get_player(member_tag)
                        current_achievement = player.get_achievement("Games Champion")
                        current_points_value = current_achievement.value if current_achievement else 0
                        initial_points = initial_info.get("initial_points", 0)
                        
                        score = max(0, current_points_value - initial_points) 
                        player_scores.append({
                            "name": member_in_clan.name, 
                            "tag": member_tag, 
                            "score": score,
                            "role": member_in_clan.role.name
                        })
                        total_points += score
                    except Exception as e:
                         player_scores.append({"name": initial_info.get('name', member_tag), "tag": member_tag, "score": 0, "role": "Membro"})
                else:
                    # O membro estava no clan no começo dos jogos, fez pontos, e saiu.
                    player_scores.append({"name": initial_info.get("name", member_tag) + " (Saiu)", "tag": member_tag, "score": 0, "role": "Ex-Membro"})

            # Verifica membros que entraram DEPOIS que o snapshot começou
            for member in clan.members:
                if member.tag not in processed_tags:
                    score = getattr(member, "clan_games_points", 0)
                    if score > 0:
                        player_scores.append({
                            "name": member.name + " (Novo)", 
                            "tag": member.tag, 
                            "score": score,
                            "role": member.role.name
                        }) 
                        total_points += score

            # Ordena do maior pontuador para o menor
            player_scores.sort(key=lambda x: x["score"], reverse=True)

            return {
                "active": True,
                "total_points": total_points,
                "max_points": 50000,
                "members": player_scores
            }

        except Exception as e:
            logger.error(f"Erro ao processar dados dos Jogos para a Web: {e}", exc_info=True)
            return {"error": "Erro interno ao processar pontuações."}


    async def take_snapshot(self, automated: bool = False):
        """Tira um snapshot dos pontos de todos os membros no início dos Jogos do Clã."""
        if self.snapshot_collection is None: return

        if await self._is_snapshot_active():
            await self.clear_snapshot(automated=False, silent=True) 

        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            if not clan: return

            snapshot_data = []
            self.already_congratulated = set() # Reseta os parabenizados da temporada

            for member in clan.members:
                try:
                    player = await self.bot.api_client.get_player(member.tag)
                    games_achievement = player.get_achievement("Games Champion")
                    initial_points_value = games_achievement.value if games_achievement else 0 

                    snapshot_data.append({
                        "_id": player.tag, 
                        "initial_points": initial_points_value,
                        "name": player.name 
                    })
                except Exception: pass

            if snapshot_data:
                await self.snapshot_collection.insert_many(snapshot_data)
                logger.info("Snapshot dos Jogos do Clã tirado com sucesso.")
                if not automated:
                     embed = discord.Embed(title="🎉 Início dos Jogos do Clã!", description=f"O monitoramento começou e os pontos iniciais de **{len(snapshot_data)}** guerreiros foram registrados.", color=discord.Color.blue())
                     await self._send_to_channel(embed=embed)

        except Exception as e:
             logger.error(f"Erro geral ao tirar snapshot: {e}", exc_info=True)


    async def clear_snapshot(self, automated: bool = False, silent: bool = False):
        """Limpa o snapshot e a memória de platina."""
        if self.snapshot_collection is None: return
        try:
            await self.snapshot_collection.delete_many({})
            self.already_congratulated = set()
            if not silent:
                embed = discord.Embed(title="⏹️ Jogos Finalizados", description="O painel de pontos e o monitoramento deste mês foram encerrados.", color=discord.Color.red())
                await self._send_to_channel(embed=embed)
        except Exception as e:
             logger.error(f"Erro ao limpar snapshot: {e}", exc_info=True)


    @tasks.loop(hours=8)
    async def periodic_status_update(self):
        """Gera relatórios esporádicos no Discord de como o clã está indo."""
        if self.bot.maintenance_mode: return 
        if await self._is_snapshot_active():
            await self.post_status_update()


    @tasks.loop(minutes=15)
    async def auto_manage_clan_games(self):
        """Motor inteligente: Começa e termina os jogos sozinho e parabeniza quem faz 4k."""
        if self.bot.maintenance_mode: return 
        now_utc = datetime.datetime.now(pytz.utc)

        try:
            is_active = await self._is_snapshot_active()
            
            # Os jogos do clã acontecem sempre do dia 22 ao 28 de cada mês
            if 22 <= now_utc.day < 28 and not is_active:
                await self.take_snapshot(automated=True) 

            elif now_utc.day >= 28 and is_active:
                await self.post_status_update(is_final_report=True) 
                await self.clear_snapshot(automated=True) 
            
            # Lógica de Parabenização de 4K: Verifica em tempo real
            if is_active and 22 <= now_utc.day < 28:
                data = await self.fetch_clan_games_data_for_web()
                if "error" not in data:
                    for p in data.get("members", []):
                        if p["score"] >= 4000 and p["tag"] not in self.already_congratulated:
                            self.already_congratulated.add(p["tag"])
                            embed = discord.Embed(
                                title="🔥 PLATINOU!",
                                description=f"O guerreiro **{p['name']}** bateu o máximo de **4.000 pontos** nos Jogos do Clã!\nObrigado por puxar o Clã pra cima! 🍻",
                                color=discord.Color.brand_green()
                            )
                            embed.set_thumbnail(url="https://clashofclans.com/uploaded-images-blog/Clan-Games-icon.png")
                            await self._send_to_channel(embed=embed)

        except Exception as e:
             logger.error(f"Erro no motor auto_manage: {e}", exc_info=True)


    @periodic_status_update.before_loop
    @auto_manage_clan_games.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()

    @commands.group(name='cgs', invoke_without_command=True)
    async def cgs(self, ctx: commands.Context):
        """Mostra o status de quem está ajudando nos Jogos."""
        await self.post_status_update(ctx)

    @cgs.command(name='start')
    @commands.has_permissions(administrator=True)
    async def cgs_start(self, ctx: commands.Context):
        await ctx.message.add_reaction("🔄")
        await self.take_snapshot(automated=False) 
        await ctx.message.remove_reaction("🔄", self.bot.user)

    @cgs.command(name='stop')
    @commands.has_permissions(administrator=True)
    async def cgs_stop(self, ctx: commands.Context):
        if not await self._is_snapshot_active():
            await ctx.send("O monitoramento não está ativo.")
            return
        await ctx.message.add_reaction("🔄")
        await self.post_status_update(ctx, is_final_report=True) 
        await self.clear_snapshot(automated=False) 
        await ctx.message.remove_reaction("🔄", self.bot.user)

    async def post_status_update(self, ctx: Optional[commands.Context] = None, is_final_report: bool = False):
        """Envia para o Discord um apanhado geral dos pontos usando os dados que a Web API gera."""
        is_manual_request = ctx is not None

        if not await self._is_snapshot_active():
            if is_manual_request: await ctx.send("Nenhum monitoramento dos Jogos do Clã ativo no momento.")
            return

        try:
            data = await self.fetch_clan_games_data_for_web()
            if "error" in data:
                if is_manual_request: await ctx.send(f"❌ {data['error']}")
                return

            total_points = data["total_points"]
            players = data["members"]

            embed_title = "🏁 Fim dos Jogos do Clã (Relatório)" if is_final_report else "🏅 Progresso nos Jogos do Clã"
            embed = discord.Embed(title=embed_title, color=discord.Color.gold())
            
            progress = min(total_points / 50000, 1.0)
            filled_blocks = int(progress * 20)
            progress_bar = "█" * filled_blocks + "░" * (20 - filled_blocks)

            embed.add_field(
                name="Meta do Clã",
                value=f"**{total_points:,} / 50.000 Pontos**\n`{progress_bar}` {progress:.1%}",
                inline=False
            )

            # TOP 5 Carregadores do Clã
            top_players = [p for p in players if p["score"] > 0][:5]
            if top_players:
                top_text = "\n".join([f"`{i+1}.` **{p['name']}**: {p['score']:,}" for i, p in enumerate(top_players)])
                embed.add_field(name="🏆 Top 5 Contribuidores", value=top_text, inline=False)
            else:
                embed.add_field(name="Participantes", value="Ninguém pontuou ainda.", inline=False)

            # Se for relatório final, expõe o Hall da Vergonha
            if is_final_report:
                zero_scorers = [p for p in players if p["score"] == 0]
                low_scorers = [p for p in players if 0 < p["score"] < 1000]

                if zero_scorers:
                    zero_names = ", ".join([p["name"] for p in zero_scorers])
                    if len(zero_names) > 1000: zero_names = zero_names[:950] + "..."
                    embed.add_field(name=f"🛑 Zero Pontos ({len(zero_scorers)} membros)", value=zero_names, inline=False)
                
                if low_scorers:
                    low_names = ", ".join([p["name"] for p in low_scorers])
                    if len(low_names) > 1000: low_names = low_names[:950] + "..."
                    embed.add_field(name=f"⚠️ Menos de 1k pontos ({len(low_scorers)} membros)", value=low_names, inline=False)

            embed.set_footer(text="Acesse o Painel Web para ver a lista completa de todos os jogadores.")

            if is_manual_request:
                await ctx.send(embed=embed)
            else:
                await self._send_to_channel(embed=embed)

        except Exception as e:
            logger.error(f"Erro ao postar status dos Jogos do Clã: {e}", exc_info=True)
            if is_manual_request: await ctx.send("❌ Erro ao gerar o status.")

async def setup(bot: commands.Bot):
    await bot.add_cog(ClanGamesCog(bot))
