# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
import pytz
import datetime
from typing import Optional, List # Adicionado List
import math # Adicionado math

logger = logging.getLogger("clan_games_cog")

# CORREÇÃO AQUI: Adicionado `name="Gerenciador de Doações"` -> Nome correto é "Jogos do Clã"
class ClanGamesCog(commands.Cog, name="Jogos do Clã"): # Nome corrigido
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
        # Usa find_one para eficiência
        return await self.snapshot_collection.find_one({}) is not None

    async def _send_to_channel(self, message: str = None, embed: discord.Embed = None, embeds: List[discord.Embed] = None):
        """Envia uma mensagem, um embed ou uma lista de embeds para o canal configurado."""
        if not self.channel_id:
            logger.warning("ID do canal dos Jogos do Clã não configurado.")
            return
        try:
            channel = self.bot.get_channel(self.channel_id) or await self.bot.fetch_channel(self.channel_id)
            if embeds: # Se for uma lista de embeds
                for emb in embeds:
                    await channel.send(embed=emb)
                    await asyncio.sleep(0.5) # Pequeno delay entre embeds
            elif embed: # Se for um único embed
                await channel.send(embed=embed)
            elif message: # Se for apenas texto
                await channel.send(content=message)
        except discord.NotFound:
             logger.error(f"Canal dos Jogos do Clã (ID: {self.channel_id}) não encontrado.")
        except discord.Forbidden:
             logger.error(f"Sem permissão para enviar mensagem no canal dos Jogos do Clã (ID: {self.channel_id}).")
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem/embeds para o canal dos Jogos do Clã: {e}", exc_info=True)


    async def take_snapshot(self, automated: bool = False):
        """Tira um snapshot dos pontos de todos os membros no início dos Jogos do Clã."""
        if self.snapshot_collection is None:
             logger.warning("DB não disponível para take_snapshot.")
             return

        if await self._is_snapshot_active() and automated:
            logger.info("Snapshot dos Jogos do Clã já está ativo. Iniciando automaticamente ignorado.")
            return

        # Limpa qualquer snapshot existente antes de criar um novo (manual ou automático)
        if await self._is_snapshot_active():
            logger.info("Limpando snapshot existente antes de criar um novo.")
            await self.clear_snapshot(automated=False, silent=True) # Limpa silenciosamente

        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            if not clan:
                logger.error("take_snapshot: Não foi possível obter dados do clã.")
                return

            snapshot_data = []
            utc_now = datetime.datetime.now(pytz.utc) # Timestamp do snapshot

            for member in clan.members:
                try:
                    # Tenta obter o achievement Games Champion
                    player = await self.bot.api_client.get_player(member.tag)
                    games_achievement = player.get_achievement("Games Champion")
                    initial_points_value = games_achievement.value if games_achievement else 0 # Default 0 se não tiver

                    snapshot_data.append({
                        "_id": player.tag, # Usa a tag como ID único
                        "initial_points": initial_points_value,
                        "name": player.name # Salva o nome no momento do snapshot
                    })
                except coc.NotFound:
                     logger.warning(f"Jogador {member.name} ({member.tag}) não encontrado na API ao tirar snapshot.")
                except Exception as e:
                    logger.error(f"Não foi possível obter dados para o jogador {member.name} ({member.tag}) no snapshot: {e}")

            if snapshot_data:
                await self.snapshot_collection.insert_many(snapshot_data)
                msg = f"✅ Monitoramento dos Jogos do Clã iniciado! Snapshot salvo para **{len(snapshot_data)}** membros."
                logger.info(msg)
                # Envia apenas se não for chamada silenciosa (ex: !cgs start)
                if not automated:
                     await self._send_to_channel(message=f"🎉 **Os Jogos do Clã começaram (ou foram reiniciados)!**\n{msg}")
            else:
                 logger.warning("Nenhum dado de jogador pôde ser salvo no snapshot.")

        except Exception as e:
             logger.error(f"Erro geral ao tirar snapshot dos Jogos do Clã: {e}", exc_info=True)


    async def clear_snapshot(self, automated: bool = False, silent: bool = False):
        """Limpa o snapshot, finalizando o monitoramento dos Jogos do Clã."""
        if self.snapshot_collection is None:
             logger.warning("DB não disponível para clear_snapshot.")
             return
        try:
            await self.snapshot_collection.delete_many({})
            msg = "⏹️ Monitoramento dos Jogos do Clã finalizado. Dados limpos."
            logger.info(msg)
            if not silent: # Envia apenas se não for chamada silenciosa
                await self._send_to_channel(message=msg)
        except Exception as e:
             logger.error(f"Erro ao limpar snapshot dos Jogos do Clã: {e}", exc_info=True)


    @tasks.loop(hours=8)
    async def periodic_status_update(self):
        """Tarefa que roda em segundo plano para postar atualizações periódicas."""
        if self.bot.maintenance_mode: return # Respeita modo manutenção
        if await self._is_snapshot_active():
            logger.info("Enviando atualização periódica dos Jogos do Clã...")
            await self.post_status_update()
        else:
            logger.debug("Atualização periódica Jogos do Clã pulada (snapshot não ativo).")

    @tasks.loop(minutes=15)
    async def auto_manage_clan_games(self):
        """Verifica a cada 15 minutos se os Jogos do Clã devem começar ou terminar."""
        if self.bot.maintenance_mode: return # Respeita modo manutenção
        now_utc = datetime.datetime.now(pytz.utc)

        try:
            # Período de Início: Dias 22 a 27 (UTC)
            if 22 <= now_utc.day < 28 and not await self._is_snapshot_active():
                logger.info("Período dos Jogos do Clã ativo e sem snapshot. Iniciando monitoramento automático.")
                await self.take_snapshot(automated=True) # Tira o snapshot

            # Período de Fim: Dia 28 (UTC) ou depois
            elif now_utc.day >= 28 and await self._is_snapshot_active():
                logger.info("Data de término dos Jogos do Clã detectada. Finalizando monitoramento automático.")
                await self.post_status_update(is_final_report=True) # Posta relatório final
                await self.clear_snapshot(automated=True) # Limpa o snapshot
        except Exception as e:
             logger.error(f"Erro em auto_manage_clan_games: {e}", exc_info=True)


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
        await self.take_snapshot(automated=False) # Chama take_snapshot (que já limpa antes)
        await ctx.message.remove_reaction("🔄", self.bot.user)
        await ctx.message.add_reaction("✅")
        # Mensagem é enviada por take_snapshot

    @cgs.command(name='stop')
    @commands.has_permissions(administrator=True)
    async def cgs_stop(self, ctx: commands.Context):
        """(Admin) Força o fim do monitoramento dos Jogos do Clã."""
        if not await self._is_snapshot_active():
            await ctx.send("O monitoramento não está ativo.")
            return
        await ctx.message.add_reaction("🔄")
        await self.post_status_update(ctx, is_final_report=True) # Posta relatório final no canal do comando
        await self.clear_snapshot(automated=False) # Limpa snapshot e envia msg pro canal configurado
        await ctx.message.remove_reaction("🔄", self.bot.user)
        await ctx.message.add_reaction("✅")
        # Mensagens são enviadas por post_status_update e clear_snapshot

    async def post_status_update(self, ctx: Optional[commands.Context] = None, is_final_report: bool = False):
        """Busca os dados, calcula os pontos e posta uma atualização (possivelmente em múltiplos embeds)."""
        is_manual_request = ctx is not None

        if not await self._is_snapshot_active():
            if is_manual_request: await ctx.send("Nenhum monitoramento dos Jogos do Clã ativo no momento.")
            return

        if is_manual_request: await ctx.message.add_reaction("🔄")

        try:
            # Busca dados iniciais e atuais
            initial_data_cursor = self.snapshot_collection.find({})
            initial_data = {doc["_id"]: doc for doc in await initial_data_cursor.to_list(length=None)} # Busca todos
            clan = await self.bot.api_client.get_clan(self.clan_tag)
            if not clan:
                 logger.error("post_status_update: Falha ao obter dados do clã.")
                 if is_manual_request: await ctx.send("❌ Falha ao obter dados do clã.")
                 return

            player_scores = []
            total_points = 0
            current_member_tags = {m.tag for m in clan.members}

            # Processa membros que estavam no snapshot
            processed_tags = set()
            for member_tag, initial_info in initial_data.items():
                processed_tags.add(member_tag)
                member_in_clan = clan.get_member(member_tag)
                if member_in_clan:
                    try:
                        player = await self.bot.api_client.get_player(member_tag)
                        current_achievement = player.get_achievement("Games Champion")
                        current_points_value = current_achievement.value if current_achievement else 0
                        initial_points = initial_info.get("initial_points", 0)
                        score = max(0, current_points_value - initial_points) # Garante >= 0
                        player_scores.append({"name": member_in_clan.name, "score": score, "tag": member_tag})
                        total_points += score
                    except coc.NotFound:
                         logger.warning(f"Jogador {initial_info.get('name', member_tag)} (no snapshot) não encontrado na API.")
                         # Adiciona com score 0 se não for encontrado na API
                         player_scores.append({"name": initial_info.get('name', member_tag), "score": 0, "tag": member_tag})
                    except Exception as e:
                         logger.error(f"Erro ao processar jogador {initial_info.get('name', member_tag)} do snapshot: {e}")
                         player_scores.append({"name": initial_info.get('name', member_tag), "score": 0, "tag": member_tag})
                else:
                    # Membro saiu, adiciona com score 0 (ou buscar histórico se necessário no futuro)
                    player_scores.append({"name": initial_info.get("name", member_tag) + " (Saiu)", "score": 0, "tag": member_tag})

            # Processa membros que entraram DEPOIS do snapshot e pontuaram
            for member in clan.members:
                if member.tag not in processed_tags:
                    try:
                        player = await self.bot.api_client.get_player(member.tag)
                        current_achievement = player.get_achievement("Games Champion")
                        current_points_value = current_achievement.value if current_achievement else 0
                        # Como não temos snapshot, o score é o valor atual (assume que começou do 0)
                        # Idealmente, precisaríamos de um snapshot inicial para TODOS, mas isso aproxima.
                        if current_points_value > 0:
                             score = current_points_value # Score é o total, pois não há 'initial'
                             player_scores.append({"name": member.name + " *", "score": score, "tag": member.tag}) # Marca com *
                             total_points += score
                    except coc.NotFound:
                         logger.warning(f"Jogador {member.name} ({member.tag}) (entrou depois) não encontrado na API.")
                    except Exception as e:
                         logger.error(f"Erro ao processar jogador {member.name} ({member.tag}) que entrou depois: {e}")


            player_scores.sort(key=lambda x: x["score"], reverse=True)

            # --- Criação dos Embeds ---
            embeds_to_send = []
            embed_title = "🏁 Relatório Final dos Jogos do Clã" if is_final_report else "🏅 Status dos Jogos do Clã"
            MAX_POINTS = 50000 # Pontuação máxima dos jogos
            MAX_PLAYERS_PER_FIELD = 15 # Quantos jogadores cabem bem em um campo
            MAX_FIELDS_PER_EMBED = 20 # Limite seguro de campos por embed (total 25)

            # --- Embed Principal (Cabeçalho) ---
            embed = discord.Embed(title=embed_title, color=discord.Color.gold())
            if clan.badge: embed.set_thumbnail(url=clan.badge.url)

            progress = min(total_points / MAX_POINTS, 1.0) if MAX_POINTS > 0 else 0
            filled_blocks = int(progress * 20)
            progress_bar = "█" * filled_blocks + "░" * (20 - filled_blocks)

            embed.add_field(
                name="Progresso Total do Clã",
                value=f"**{total_points:,} / {MAX_POINTS:,} Pontos**\n`{progress_bar}` {progress:.1%}",
                inline=False
            )
            embeds_to_send.append(embed)

            # --- Adiciona Campos de Jogadores ---
            current_embed = embed
            players_with_score = [p for p in player_scores if p['score'] > 0]
            total_players_with_score = len(players_with_score)
            num_fields_needed = math.ceil(total_players_with_score / MAX_PLAYERS_PER_FIELD) if total_players_with_score > 0 else 1 # Pelo menos 1 campo (ou msg 'ninguém')
            embed_index = 0 # Índice do embed atual (0 para o principal)

            if not players_with_score:
                 current_embed.add_field(name="Participantes (0)", value="Ninguém pontuou ainda.", inline=False)
            else:
                for i in range(0, total_players_with_score, MAX_PLAYERS_PER_FIELD):
                    chunk = players_with_score[i:i + MAX_PLAYERS_PER_FIELD]
                    field_name = f"🏆 Contribuidores ({i + 1} - {i + len(chunk)})"
                    field_value = ""
                    rank_offset = i + 1 # Para o ranking correto

                    for rank, player in enumerate(chunk, start=rank_offset):
                         line = f"`{rank}.` **{player['name']}**: {player['score']:,} pontos\n"
                         # Verifica se adicionar a linha excede o limite de caracteres do campo
                         if len(field_value) + len(line) > 1024:
                             # Se exceder, finaliza o campo atual e começa um novo (se possível)
                             current_embed.add_field(name=field_name, value=field_value, inline=False)
                             field_value = line # Começa o novo valor com a linha atual
                             field_name += " (cont.)" # Indica continuação
                             # Verifica se precisa de um novo embed
                             if len(current_embed.fields) >= MAX_FIELDS_PER_EMBED:
                                 embed_index += 1
                                 current_embed = discord.Embed(title=f"{embed_title} (Página {embed_index + 1})", color=discord.Color.gold())
                                 if clan.badge: current_embed.set_thumbnail(url=clan.badge.url)
                                 embeds_to_send.append(current_embed)
                         else:
                              field_value += line

                    # Adiciona o último (ou único) pedaço do campo
                    if field_value:
                        # Verifica se precisa de um novo embed antes de adicionar o último campo
                        if len(current_embed.fields) >= MAX_FIELDS_PER_EMBED:
                            embed_index += 1
                            current_embed = discord.Embed(title=f"{embed_title} (Página {embed_index + 1})", color=discord.Color.gold())
                            if clan.badge: current_embed.set_thumbnail(url=clan.badge.url)
                            embeds_to_send.append(current_embed)
                        current_embed.add_field(name=field_name, value=field_value, inline=False)


            # --- Envio ---
            if is_manual_request:
                # Envia no canal do comando
                for i, emb_to_send in enumerate(embeds_to_send):
                    # Adiciona timestamp e rodapé
                    emb_to_send.timestamp = datetime.datetime.now(self.bot.timezone)
                    emb_to_send.set_footer(text=f"ClashGenius | Página {i + 1}/{len(embeds_to_send)}")
                    await ctx.send(embed=emb_to_send)
                    if len(embeds_to_send) > 1: await asyncio.sleep(0.5)
            else:
                 # Envia para o canal configurado
                 # Adiciona timestamp e rodapé
                 for i, emb_to_send in enumerate(embeds_to_send):
                     emb_to_send.timestamp = datetime.datetime.now(self.bot.timezone)
                     emb_to_send.set_footer(text=f"ClashGenius | Página {i + 1}/{len(embeds_to_send)}")
                 await self._send_to_channel(embeds=embeds_to_send)


            if is_manual_request:
                try:
                    await ctx.message.remove_reaction("🔄", self.bot.user)
                    await ctx.message.add_reaction("✅")
                except discord.HTTPException: pass # Ignora erro se a reação já foi removida

        except Exception as e:
            logger.error(f"Erro ao postar status dos Jogos do Clã: {e}", exc_info=True)
            if is_manual_request:
                 await ctx.send(f"❌ Erro ao gerar o status dos Jogos do Clã: {e}")
                 try: await ctx.message.remove_reaction("🔄", self.bot.user)
                 except discord.HTTPException: pass
                 await ctx.message.add_reaction("❌")


async def setup(bot: commands.Bot):
    if bot.clan_games_channel_id and bot.db is not None:
        await bot.add_cog(ClanGamesCog(bot))
    else:
        logger.warning("Cog 'ClanGamesCog' não carregado (ID do canal ou DB não configurado).")
