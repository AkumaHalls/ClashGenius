# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands
from pymongo.errors import PyMongoError

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
        """Analisa o banco de dados em busca de duplicatas no histórico de guerras."""
        if self.db is None:
            await ctx.send("❌ O bot não está conectado a um banco de dados.")
            return

        await ctx.message.add_reaction("🔎")
        
        pipeline = [
            {"$group": {
                "_id": "$_id",  # Agrupa por nosso ID de guerra único
                "uniqueIds": {"$addToSet": "$_id"},
                "count": {"$sum": 1}
            }},
            {"$match": {
                "count": {"$gt": 1}  # Filtra apenas os que têm mais de 1 entrada (duplicatas)
            }}
        ]

        try:
            duplicates = await self.db.war_history.aggregate(pipeline).to_list(length=None)
            
            if not duplicates:
                await ctx.message.remove_reaction("🔎", self.bot.user)
                await ctx.message.add_reaction("✅")
                await ctx.send("✅ Análise concluída. Nenhuma guerra duplicada encontrada no histórico.")
                return

            total_duplicates_to_remove = sum(d['count'] - 1 for d in duplicates)
            
            # Salva os dados para o comando de confirmação
            self.cleanup_confirmation_data[ctx.author.id] = duplicates

            embed = discord.Embed(
                title="⚠️ Análise de Duplicatas no Histórico de Guerras",
                description=(
                    "A análise encontrou registros de guerra duplicados no banco de dados, "
                    "provavelmente causados por reinicializações anteriores do bot."
                ),
                color=discord.Color.orange()
            )
            embed.add_field(
                name="Resultados da Análise",
                value=(
                    f"**Grupos de duplicatas encontrados:** {len(duplicates)}\n"
                    f"**Total de registros a serem removidos:** {total_duplicates_to_remove}"
                ),
                inline=False
            )
            embed.add_field(
                name="Ação Necessária",
                value=(
                    "Para remover as entradas duplicadas e limpar o histórico, "
                    "use o comando `!dbcleanup confirmar`.\n\n"
                    "**Atenção:** Esta ação é irreversível."
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
                war_id = group['_id']
                # Pega todos os IDs de documento para este war_id (embora o _id já seja o que precisamos)
                # Na verdade, precisamos encontrar os documentos reais.
                
                # Encontra todos os documentos com o mesmo `_id` de guerra
                cursor = self.db.war_history.find({"_id": war_id})
                docs_to_delete = await cursor.to_list(length=None)
                
                # Mantém o primeiro e remove o resto
                if docs_to_delete:
                    docs_to_delete.pop(0) # Remove o primeiro da lista para mantê-lo
                
                if docs_to_delete:
                    # Coleta os IDs internos do MongoDB (`_id` do documento, não o nosso `_id` de guerra)
                    mongo_ids_to_delete = [doc['_id'] for doc in docs_to_delete]
                    result = await self.db.war_history.delete_many({"_id": {"$in": mongo_ids_to_delete}})
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
