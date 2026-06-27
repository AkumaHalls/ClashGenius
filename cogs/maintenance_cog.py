# -*- coding: utf-8 -*-
import logging
import asyncio
import discord
from discord.ext import commands
from pymongo.errors import PyMongoError
from aiohttp import web

logger = logging.getLogger("maintenance_cog")

class MaintenanceCog(commands.Cog, name="Manutenção do Sistema"):
    """Cog para comandos de manutenção do bot e do banco de dados."""

    MAINTENANCE_ROLE_ID = 1362076878458065037

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.cleanup_confirmation_data = {}

    async def toggle_maintenance_mode_web(self):
        """Ativa/desativa o modo de manutenção a partir de um pedido web."""
        self.bot.maintenance_mode = not self.bot.maintenance_mode
        
        if self.db is not None:
            await self.db.system_config.update_one(
                {"_id": "maintenance_mode"},
                {"$set": {"enabled": self.bot.maintenance_mode}},
                upsert=True
            )
        
        status_str = "ATIVADO" if self.bot.maintenance_mode else "DESATIVADO"
        embed_color = discord.Color.orange() if self.bot.maintenance_mode else discord.Color.green()
        embed = discord.Embed(
            title=f"🚨 Modo Manutenção {status_str} 🚨",
            description="O painel web está agora " + ("indisponível para membros." if self.bot.maintenance_mode else "totalmente operacional."),
            color=embed_color
        )
        embed.add_field(
            name="Impacto", 
            value="**Alertas no Discord:** " + ("PAUSADOS" if self.bot.maintenance_mode else "ATIVOS") +
                  "\n**Acesso ao Painel:** " + ("Apenas Admins" if self.bot.maintenance_mode else "Público"),
            inline=False
        )
        role_mention = f"<@&{self.MAINTENANCE_ROLE_ID}>"
        channel_id = self.bot.maintenance_alert_channel_id or self.bot.channel_id
        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                channel = None
        if channel:
            try:
                await channel.send(content=role_mention, embed=embed)
            except discord.errors.HTTPException as e:
                if e.status == 429:
                    await asyncio.sleep(5)
                    await channel.send(content=role_mention, embed=embed)
                else:
                    raise e
        
        return web.json_response({"status": "success", "maintenance_mode": self.bot.maintenance_mode})

    async def send_test_embed_web(self):
        """Envia um embed de teste a partir de um pedido web."""
        embed = discord.Embed(title="✅ Mensagem de Teste (Web)", description="Comunicação OK!", color=discord.Color.blue())
        channel_id = self.bot.maintenance_alert_channel_id or self.bot.channel_id
        channel = self.bot.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except Exception:
                channel = None
        if channel:
            await channel.send(embed=embed)
            return web.json_response({"status": "success"})
        return web.json_response({"status": "error", "message": "Channel not found"}, status=500)

    @commands.group(name='dbcleanup', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def db_cleanup(self, ctx: commands.Context):
        """Analisa o banco de dados em busca de duplicatas de conteúdo no histórico de guerras."""
        if self.db is None:
            await ctx.send("❌ O bot não está conectado a um banco de dados.")
            return

        await ctx.message.add_reaction("🔎")
        
        pipeline = [
            {
                "$group": {
                    "_id": "$_id",
                    "unique_doc_ids": {"$addToSet": "$_id"},
                    "count": {"$sum": 1}
                }
            },
            {
                "$match": {
                    "count": {"$gt": 1}
                }
            }
        ]

        try:
            duplicates = await self.db.war_history.aggregate(pipeline).to_list(length=None)
            
            if not duplicates:
                await ctx.send("✅ Análise concluída. Nenhuma guerra com conteúdo duplicado encontrada.")
                return

            total_duplicates_to_remove = sum(d['count'] - 1 for d in duplicates)
            self.cleanup_confirmation_data[ctx.author.id] = duplicates
            
            embed = discord.Embed(
                title="⚠️ Análise de Duplicatas",
                description="Foram encontrados múltiplos registros para a mesma guerra.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Registros a remover", value=total_duplicates_to_remove)
            embed.add_field(name="Ação", value="Use `!dbcleanup confirmar` para remover as duplicatas.")
            await ctx.send(embed=embed)

        except PyMongoError as e:
            await ctx.send(f"❌ Erro de banco de dados: `{e}`")
        finally:
            await ctx.message.remove_reaction("🔎", self.bot.user)


    @db_cleanup.command(name='confirmar')
    @commands.has_permissions(administrator=True)
    async def db_cleanup_confirm(self, ctx: commands.Context):
        """Confirma e executa a limpeza das guerras duplicadas."""
        if ctx.author.id not in self.cleanup_confirmation_data:
            await ctx.send("⚠️ Nenhuma análise pendente. Execute `!dbcleanup` primeiro.")
            return

        duplicates = self.cleanup_confirmation_data.pop(ctx.author.id)
        await ctx.send(f"⏳ Iniciando limpeza de {sum(d['count'] - 1 for d in duplicates)} registros...")
        
        deleted_count = 0
        try:
            for group in duplicates:
                ids_to_delete = group['unique_doc_ids'][1:]
                if ids_to_delete:
                    result = await self.db.war_history.delete_many({"_id": {"$in": ids_to_delete}})
                    deleted_count += result.deleted_count
            await ctx.send(f"✅ Limpeza Concluída! Removidos **{deleted_count}** registros duplicados.")
        except PyMongoError as e:
            await ctx.send(f"❌ Erro durante a limpeza: `{e}`")

async def setup(bot: commands.Bot):
    await bot.add_cog(MaintenanceCog(bot))
