# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import geniuslib as coc
import pytz
import datetime
from typing import Optional, List, Dict, Any
import asyncio

logger = logging.getLogger("clan_games_cog")

class ClanGamesCog(commands.Cog, name="Jogos do Clã"):
    """Cog para gerenciar os Jogos do Clã usando comandos Slash e proteção contra reinícios."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.clan_tag: str = bot.clan_tag
        self.snapshot_collection = self.db.clan_games_snapshot if self.db is not None else None
        
        # Flexibilidade Padrão (pode ser sobrescrita pelo admin via comando)
        self.max_player_points = 4000
        self.max_clan_points = 50000
        
        # Previne spam de notificações para o mesmo jogador
        self.already_congratulated = set()

        self.auto_manage_clan_games.start()
        self.periodic_status_update.start()

    async def cog_unload(self):
        """Desliga os motores quando o módulo for recarregado/desligado."""
        self.auto_manage_clan_games.cancel()
        self.periodic_status_update.cancel()

    async def _is_snapshot_active(self) -> bool:
        """Verifica se já existe um snapshot gravado na base de dados."""
        if self.snapshot_collection is None:
            return False
        return await self.snapshot_collection.find_one({}) is not None

    async def _send_to_channel(self, message: str = None, embed: discord.Embed = None, embeds: List[discord.Embed] = None):
        """Envia mensagens para a sala de Eventos Secundários no Discord."""
        channel_id = self.bot.clan_games_channel_id
        if not channel_id:
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
            logger.error(f"Erro ao enviar aviso de Jogos do Clã: {e}")

    async def fetch_clan_games_data_for_web(self) -> Dict[str, Any]:
        """Calcula os pontos e alimenta o Painel Web."""
        if not await self._is_snapshot_active():
            return {"error": "Os Jogos do Clã não estão ativos no momento."}

        try:
            initial_data_cursor = self.snapshot_collection.find({})
            initial_data = {doc["_id"]: doc for doc in await initial_data_cursor.to_list(length=None)}
            
            clan = await self.bot.api_client.get_clan(self.clan_tag)
            if not clan:
                 return {"error": "Sem conexão com a Supercell."}

            player_scores = []
            total_points = 0
            processed_tags = set()

            for member_tag, initial_info in initial_data.items():
                processed_tags.add(member_tag)
                member_in_clan = clan.get_member(member_tag)
                
                if member_in_clan:
                    try:
                        player = await self.bot.api_client.get_player(member_tag)
                        ach = player.get_achievement("Games Champion")
                        current_pts = ach.value if ach else 0
                        initial_pts = initial_info.get("initial_points", 0)
                        
                        score = max(0, current_pts - initial_pts) 
                        player_scores.append({
                            "name": member_in_clan.name, "tag": member_tag, 
                            "score": score, "role": member_in_clan.role.name
                        })
                        total_points += score
                    except Exception:
                         player_scores.append({"name": initial_info.get('name', member_tag), "tag": member_tag, "score": 0, "role": "Membro"})
                else:
                    player_scores.append({"name": initial_info.get("name", member_tag) + " (Saiu)", "tag": member_tag, "score": 0, "role": "Ex-Membro"})

            # Checa os novatos que entraram depois do snapshot
            for member in clan.members:
                if member.tag not in processed_tags:
                    score = getattr(member, "clan_games_points", 0)
                    if score > 0:
                        player_scores.append({
                            "name": member.name + " (Novo)", "tag": member.tag, 
                            "score": score, "role": member.role.name
                        }) 
                        total_points += score

            player_scores.sort(key=lambda x: x["score"], reverse=True)

            return {
                "active": True,
                "total_points": total_points,
                "max_clan_points": self.max_clan_points,
                "max_player_points": self.max_player_points,
                "members": player_scores
            }

        except Exception as e:
            logger.error(f"Erro ao processar dados Web dos Jogos: {e}", exc_info=True)
            return {"error": "Erro interno ao processar pontos."}

    async def take_snapshot(self, automated: bool = False):
        """Salva a pontuação base de todos os membros."""
        if self.snapshot_collection is None: return

        if await self._is_snapshot_active():
            await self.clear_snapshot(automated=False, silent=True) 

        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            if not clan: return

            snapshot_data = []
            self.already_congratulated = set()

            for member in clan.members:
                try:
                    player = await self.bot.api_client.get_player(member.tag)
                    ach = player.get_achievement("Games Champion")
                    initial_pts = ach.value if ach else 0 

                    snapshot_data.append({
                        "_id": player.tag, 
                        "initial_points": initial_pts,
                        "name": player.name 
                    })
                except Exception: pass

            if snapshot_data:
                await self.snapshot_collection.insert_many(snapshot_data)
                logger.info("Snapshot inicial dos Jogos criado na DB.")
                if not automated:
                     embed = discord.Embed(title="🎉 O Rastreador dos Jogos Foi Iniciado!", description=f"Pontuação inicial de **{len(snapshot_data)}** jogadores salva na DB.\nO Painel Web agora está medindo o progresso do clã em tempo real.", color=discord.Color.blue())
                     await self._send_to_channel(embed=embed)

        except Exception as e:
             logger.error(f"Erro ao gerar snapshot: {e}", exc_info=True)

    async def clear_snapshot(self, automated: bool = False, silent: bool = False):
        """Apaga a tabela base, indicando que os jogos acabaram."""
        if self.snapshot_collection is None: return
        try:
            await self.snapshot_collection.delete_many({})
            self.already_congratulated = set()
            if not silent:
                embed = discord.Embed(title="⏹️ Rastreador Desligado", description="O monitoramento dos Jogos do Clã foi encerrado. A base de dados foi limpa.", color=discord.Color.red())
                await self._send_to_channel(embed=embed)
        except Exception as e:
             logger.error(f"Erro ao limpar banco de dados dos jogos: {e}", exc_info=True)

    @tasks.loop(hours=8)
    async def periodic_status_update(self):
        """A cada 8h avisa no Discord como o Clã está indo na tabela."""
        if self.bot.maintenance_mode: return 
        if await self._is_snapshot_active():
            await self.post_status_update()

    @tasks.loop(minutes=15)
    async def auto_manage_clan_games(self):
        """Motor que aciona inícios automáticos e envia prêmios por platinar."""
        if self.bot.maintenance_mode: return 
        now_utc = datetime.datetime.now(pytz.utc)

        try:
            is_active = await self._is_snapshot_active()
            
            if 22 <= now_utc.day < 28 and not is_active:
                logger.info("Automação: Dia 22 detectado. Iniciando os jogos sozinhos...")
                await self.take_snapshot(automated=True) 

            elif now_utc.day >= 28 and is_active:
                logger.info("Automação: Dia 28 chegou. Cuspir relatório final e encerrar.")
                await self.post_status_update(is_final_report=True) 
                await self.clear_snapshot(automated=True) 
            
            if is_active and 22 <= now_utc.day < 28:
                data = await self.fetch_clan_games_data_for_web()
                if "error" not in data:
                    for p in data.get("members", []):
                        if p["score"] >= self.max_player_points and p["tag"] not in self.already_congratulated:
                            self.already_congratulated.add(p["tag"])
                            embed = discord.Embed(
                                title="🔥 MÁQUINA DE FARM!",
                                description=f"O guerreiro **{p['name']}** bateu o máximo de **{self.max_player_points} pontos**!\nObrigado por ajudar o Clã nas recompensas! 🍻",
                                color=discord.Color.brand_green()
                            )
                            embed.set_thumbnail(url="https://clashofclans.com/uploaded-images-blog/Clan-Games-icon.png")
                            await self._send_to_channel(embed=embed)

        except Exception as e:
             logger.error(f"Erro no auto_manage: {e}", exc_info=True)

    @periodic_status_update.before_loop
    @auto_manage_clan_games.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()


    # ==================== COMANDOS SLASH ====================

    @app_commands.command(name="cgs_iniciar", description="Tira o Snapshot inicial agora (força o início do monitoramento).")
    @app_commands.default_permissions(administrator=True)
    async def cmd_cgs_start(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if await self._is_snapshot_active():
            await interaction.followup.send("⚠️ O Rastreador já está ativado e lendo pontos! Se iniciar agora, o progresso anterior de todos será reiniciado para zero.")
            return
        await self.take_snapshot(automated=False)
        await interaction.followup.send("✅ Rastreador ativado manualmente!")

    @app_commands.command(name="cgs_parar", description="Desliga o rastreio, zera o BD dos Jogos e cospe o placar final.")
    @app_commands.default_permissions(administrator=True)
    async def cmd_cgs_stop(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not await self._is_snapshot_active():
            await interaction.followup.send("❌ Não há nenhum monitoramento ativo no momento.")
            return
        await self.post_status_update(interaction=interaction, is_final_report=True) 
        await self.clear_snapshot(automated=False) 

    @app_commands.command(name="cgs_configurar", description="Altera os pontos máximos permitidos neste mês.")
    @app_commands.describe(max_jogador="O máximo de pontos que 1 pessoa pode fazer (ex: 4000)", meta_cla="O limite final do clã inteiro (ex: 50000)")
    @app_commands.default_permissions(administrator=True)
    async def cmd_cgs_set(self, interaction: discord.Interaction, max_jogador: int, meta_cla: int = 50000):
        self.max_player_points = max_jogador
        self.max_clan_points = meta_cla
        await interaction.response.send_message(f"⚙️ **Regras Atualizadas:**\n👤 Max. Jogador: **{max_jogador}**\n🏆 Meta do Clã: **{meta_cla}**")

    @app_commands.command(name="cgs_status", description="Mostra a barra de progresso no Discord imediatamente.")
    async def cmd_cgs_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.post_status_update(interaction=interaction)

    async def post_status_update(self, interaction: Optional[discord.Interaction] = None, is_final_report: bool = False):
        if not await self._is_snapshot_active():
            if interaction: await interaction.followup.send("Nenhum monitoramento dos Jogos do Clã ativo no momento.")
            return

        try:
            data = await self.fetch_clan_games_data_for_web()
            if "error" in data:
                if interaction: await interaction.followup.send(f"❌ {data['error']}")
                return

            total_points = data["total_points"]
            players = data["members"]

            embed_title = "🏁 Relatório Final dos Jogos" if is_final_report else "🏅 Progresso nos Jogos do Clã"
            embed = discord.Embed(title=embed_title, color=discord.Color.gold())
            
            progress = min(total_points / self.max_clan_points, 1.0)
            filled_blocks = int(progress * 20)
            progress_bar = "█" * filled_blocks + "░" * (20 - filled_blocks)

            embed.add_field(
                name="Meta do Clã",
                value=f"**{total_points:,} / {self.max_clan_points:,} Pontos**\n`{progress_bar}` {progress:.1%}",
                inline=False
            )

            top_players = [p for p in players if p["score"] > 0][:5]
            if top_players:
                top_text = "\n".join([f"`{i+1}.` **{p['name']}**: {p['score']:,}" for i, p in enumerate(top_players)])
                embed.add_field(name="🏆 Top 5 Carregadores", value=top_text, inline=False)
            else:
                embed.add_field(name="Participantes", value="Ninguém pontuou ainda.", inline=False)

            if is_final_report:
                zero_scorers = [p for p in players if p["score"] == 0]
                low_scorers = [p for p in players if 0 < p["score"] < 1000]

                if zero_scorers:
                    zero_names = ", ".join([p["name"] for p in zero_scorers])
                    if len(zero_names) > 1000: zero_names = zero_names[:950] + "..."
                    embed.add_field(name=f"🛑 Sugadores (0 Pontos) - {len(zero_scorers)} membros", value=zero_names, inline=False)
                
                if low_scorers:
                    low_names = ", ".join([p["name"] for p in low_scorers])
                    if len(low_names) > 1000: low_names = low_names[:950] + "..."
                    embed.add_field(name=f"⚠️ Contribuição Baixa (< 1k) - {len(low_scorers)} membros", value=low_names, inline=False)

            embed.set_footer(text="Acesse o Painel Web para a lista completa.")

            if interaction:
                await interaction.followup.send(embed=embed)
            else:
                await self._send_to_channel(embed=embed)

        except Exception as e:
            logger.error(f"Erro ao gerar embed de Jogos: {e}", exc_info=True)
            if interaction: await interaction.followup.send("❌ Erro interno.")

async def setup(bot: commands.Bot):
    await bot.add_cog(ClanGamesCog(bot))
