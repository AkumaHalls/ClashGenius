# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import logging

# Configura o logger para este cog
logger = logging.getLogger("general_cog")

class GeneralCog(commands.Cog, name="Comandos Gerais"):
    """Cog para comandos gerais e utilitários do bot."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='ping')
    async def ping(self, ctx: commands.Context):
        """Verifica a latência atual do bot."""
        await ctx.send(f'Pong! 🏓 Latência: {round(self.bot.latency * 1000)}ms')

# Função setup que o discord.py chama para carregar o cog
async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralCog(bot))
