# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands
import coc
from pymongo import DESCENDING

logger = logging.getLogger("profile_cog")

class ProfileCog(commands.Cog, name="Perfis de Membros"):
    """Cog para gerenciar perfis de membros e comandos relacionados."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    async def fetch_player_profile_data(self, player_tag: str) -> dict:
        """Busca dados completos de um jogador para o perfil, usado pela API e comandos."""
        try:
            player_data = await self.bot.api_client.get_player(player_tag)
            if not player_data:
                return {"error": "Jogador não encontrado."}

            trophy_history = []
            if self.db is not None:
                cursor = self.db.trophy_history.find({"player_tag": player_tag}).sort("timestamp", DESCENDING).limit(30)
                trophy_history = [{"trophies": doc["trophies"], "timestamp": doc["timestamp"].strftime("%d/%m")} async for doc in cursor]
                trophy_history.reverse()

            profile = {
                "name": player_data.name,
                "tag": player_data.tag,
                "town_hall": player_data.town_hall,
                "heroes": [{"name": h.name, "level": h.level, "max_level": h.max_level} for h in player_data.heroes if h.is_home_base],
                "donations": player_data.donations,
                "received": player_data.received,
                "trophies": player_data.trophies,
                "league": player_data.league.name if player_data.league else "N/A",
                "trophy_history": trophy_history
            }
            return profile
        except coc.NotFound:
            return {"error": "Jogador não encontrado com a tag fornecida."}
        except Exception as e:
            logger.error(f"Erro ao buscar perfil para {player_tag}: {e}", exc_info=True)
            return {"error": "Ocorreu um erro interno ao buscar o perfil."}

    @commands.command(name='perfil')
    async def profile_command(self, ctx: commands.Context, *, player_identifier: str):
        """Mostra o perfil de um membro do clã. Use a tag ou o nome do jogador."""
        await ctx.typing()
        
        try:
            player_tag = None
            if coc.utils.is_valid_tag(player_identifier):
                 player_tag = coc.utils.correct_tag(player_identifier)
            else:
                clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
                member = clan.get_member_by(name=player_identifier, case_sensitive=False)
                if not member:
                    await ctx.send(f"❌ Não encontrei nenhum membro com o nome '{player_identifier}' no clã.")
                    return
                player_tag = member.tag

            profile_data = await self.fetch_player_profile_data(player_tag)

            if "error" in profile_data:
                await ctx.send(f"❌ {profile_data['error']}")
                return

            embed = discord.Embed(
                title=f"Perfil de {profile_data['name']} (CV{profile_data['town_hall']})",
                description=f"TAG: `{profile_data['tag']}`",
                color=discord.Color.blue()
            )

            embed.add_field(name="🏆 Troféus", value=f"{profile_data['trophies']}", inline=True)
            embed.add_field(name="🛡️ Liga", value=profile_data['league'], inline=True)
            embed.add_field(name="🎁 Doações", value=f"**Doadas:** {profile_data['donations']}\n**Recebidas:** {profile_data['received']}", inline=True)

            heroes_str = "\n".join([f"**{hero['name']}:** {hero['level']} / {hero['max_level']}" for hero in profile_data['heroes']])
            if heroes_str:
                embed.add_field(name="👑 Heróis", value=heroes_str, inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro no comando !perfil: {e}", exc_info=True)
            await ctx.send("Ocorreu um erro ao processar o comando.")

async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
