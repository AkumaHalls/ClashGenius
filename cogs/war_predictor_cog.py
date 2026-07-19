# -*- coding: utf-8 -*-
import logging
from discord.ext import commands

from war_predictor import WarPredictionSystemV3

logger = logging.getLogger("war_predictor_cog")


class WarPredictorCog(commands.Cog, name="Preditor de Guerra"):
    """Cog que gerencia o sistema de predição de guerra por Machine Learning."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.system = WarPredictionSystemV3(db_connection=bot.db)
        bot.war_prediction_system = self.system
        logger.info("WarPredictorCog carregado. Sistema será inicializado em segundo plano.")

    async def cog_load(self):
        logger.info("Inicializando WarPredictionSystemV3...")
        await self.system.initialize_system()
        logger.info("WarPredictionSystemV3 inicializado com sucesso.")


async def setup(bot: commands.Bot):
    cog = WarPredictorCog(bot)
    await bot.add_cog(cog)
    await cog.cog_load()
