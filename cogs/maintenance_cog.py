# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId

logger = logging.getLogger("maintenance_cog")

class MaintenanceCog(commands.Cog, name="Manutenção do Sistema"):
    """Cog para comandos de manutenção do bot e do banco de dados."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        # Armazena temporariamente os dados para a confirmação do cleanup
        self.cleanup_confirmation_data = {}

    @commands.group(name='dbcleanup', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def db_cleanup(self, ctx: commands.Context):
        """Analisa o banco de dados em busca de duplicatas de conteúdo no histórico de guerras."""
        if self.db is None:
            await ctx.send("❌ O bot não está conectado a um banco de dados.")
            return

        await ctx.message.add_reaction("🔎")
        
        # Pipeline aprimorado para detectar duplicatas de CONTEÚDO (baseado no tempo de término)
        pipeline = [
            {
                "$group": {
                    "_id": "$war_data.end_time_iso",  # Agrupa por tempo de término, que será igual para as duplicatas
                    "doc_ids": {"$addToSet": "$_id"}, # Pega os IDs únicos de cada documento MongoDB
                    "count": {"$sum": 1}
                }
            },
            {
                "$match": {
                    "count": {"$gt": 1}  # Filtra apenas os grupos com mais de 1 entrada (duplicatas)
                }
            }
        ]

        try:
            duplicates = await self.db.war_history.aggregate(pipeline).to_list(length=None)
            
            if not duplicates:
                await ctx.message.remove_reaction("🔎", self.bot.user)
                await ctx.message.add_reaction("✅")
                await ctx.send("✅ Análise concluída. Nenhuma guerra com conteúdo duplicado encontrada no histórico.")
                return

            total_duplicates_to_remove = sum(d['count'] - 1 for d in duplicates)
            
            # Salva os dados para o comando de confirmação
            self.cleanup_confirmation_data[ctx.author.id] = duplicates

            embed = discord.Embed(
                title="⚠️ Análise de Duplicatas de Conteúdo",
                description=(
                    "A análise encontrou múltiplos registros para a mesma guerra, "
                    "causados por um bug de reprocessamento anterior."
                ),
                color=discord.Color.orange()
            )
            embed.add_field(
                name="Resultados da Análise",
                value=(
                    f"**Grupos de guerras duplicadas:** {len(duplicates)}\n"
                    f"**Total de registros a serem removidos:** {total_duplicates_to_remove}"
                ),
                inline=False
            )
            embed.add_field(
                name="Ação Necessária",
                value=(
                    "Para remover as entradas duplicadas e limpar o histórico, "
                    "use o comando `!dbcleanup confirmar`.\n\n"
                    "**Atenção:** Apenas uma cópia de cada guerra será mantida."
                ),
                inline=False
            )
            embed.set_footer(text="Esta é apenas uma análise. Nenhum dado foi alterado ainda.")
            
            await ctx.message.remove_reaction("🔎", self.bot.user)
            await ctx.send(embed=embed)

        except PyMongoError as e:
            logger.error(f"Erro de banco de dados ao analisar duplicatas: {e}", exc_info=True)
            await ctx.send(f"❌ Ocorreu um erro ao consultar o banco de dados: `{e}`")
        except Exception as e:
            logger.error(f"Erro inesperado ao analisar duplicatas: {e}", exc_info=True)
            await ctx.send(f"❌ Um erro inesperado ocorreu: `{e}`")


    @db_cleanup.command(name='confirmar')
    @commands.has_permissions(administrator=True)
    async def db_cleanup_confirm(self, ctx: commands.Context):
        """Confirma e executa a limpeza das guerras duplicadas."""
        if ctx.author.id not in self.cleanup_confirmation_data:
            await ctx.send("⚠️ Nenhuma análise de limpeza pendente. Execute `!dbcleanup` primeiro para analisar os dados.")
            return

        duplicates = self.cleanup_confirmation_data.pop(ctx.author.id)
        
        await ctx.send(f"⏳ **Iniciando limpeza...** Removendo {sum(d['count'] - 1 for d in duplicates)} registros duplicados. Isso pode levar um momento.")
        await ctx.message.add_reaction("🔄")

        deleted_count = 0
        try:
            for group in duplicates:
                # Pega todos os IDs de documento MongoDB para este grupo de duplicatas
                doc_ids = group['doc_ids']
                
                # Ordena para garantir que estamos removendo os mais recentes, se houver diferença
                # (ObjectId no MongoDB contém um timestamp, então a ordem é cronológica)
                # Neste caso, como o ID pode ser qualquer string, apenas ordenamos alfabeticamente
                # e mantemos o primeiro.
                doc_ids.sort()
                
                # Mantém o primeiro e remove o resto
                ids_to_delete = doc_ids[1:]
                
                if ids_to_delete:
                    result = await self.db.war_history.delete_many({"_id": {"$in": ids_to_delete}})
                    deleted_count += result.deleted_count

            await ctx.message.remove_reaction("🔄", self.bot.user)
            await ctx.message.add_reaction("✅")
            await ctx.send(f"✅ **Limpeza Concluída!**\nForam removidos **{deleted_count}** registros de guerra duplicados do histórico.")

        except PyMongoError as e:
            logger.error(f"Erro de banco de dados durante a limpeza de duplicatas: {e}", exc_info=True)
            await ctx.send(f"❌ Ocorreu um erro durante a limpeza: `{e}`")
        except Exception as e:
            logger.error(f"Erro inesperado durante a limpeza: {e}", exc_info=True)
            await ctx.send(f"❌ Um erro inesperado ocorreu: `{e}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(MaintenanceCog(bot))
