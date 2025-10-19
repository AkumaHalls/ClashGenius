# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands
import coc
from typing import Optional

logger = logging.getLogger("slash_cog")

class SlashCog(commands.Cog, name="Comandos de Barra"):
    """
    Cog dedicado a agrupar todos os comandos de barra (slash commands) do bot
    para uma melhor organização e experiência de usuário.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Exemplo de comando simples
    @app_commands.command(name="ping", description="Verifica a latência do bot.")
    async def ping(self, interaction: discord.Interaction):
        """Verifica a latência atual do bot."""
        await interaction.response.send_message(f'Pong! 🏓 Latência: {round(self.bot.latency * 1000)}ms')

    # Exemplo de comando complexo com autocomplete e lógica reaproveitada
    @app_commands.command(name="perfil", description="Mostra o perfil completo de um membro do clã.")
    @app_commands.describe(jogador="Tag ou nome do jogador (deixe em branco para ver seu perfil).")
    async def perfil(self, interaction: discord.Interaction, jogador: Optional[str] = None):
        """Mostra o perfil de um jogador do clã."""
        # Adia a resposta, pois a busca na API pode demorar mais de 3 segundos
        await interaction.response.defer()

        # Pega o ProfileCog para reutilizar a lógica de busca de perfil
        profile_cog = self.bot.get_cog("Perfis de Membros")
        if not profile_cog:
            await interaction.followup.send("❌ Ocorreu um erro interno (ProfileCog não encontrado).")
            return

        player_tag = None
        
        # Lógica para encontrar a tag do jogador (reaproveitada do comando antigo)
        if not jogador:
            if self.bot.db:
                user_data = await self.bot.db.users.find_one({"discord_id": interaction.user.id})
                if user_data and "player_tag" in user_data:
                    player_tag = user_data["player_tag"]
                else:
                    await interaction.followup.send("❌ Você não tem uma tag registrada! Use `/perfil jogador:<tag/nome>` ou registre-se.")
                    return
            else:
                await interaction.followup.send("❌ Por favor, forneça uma tag ou nome do jogador.")
                return
        elif coc.utils.is_valid_tag(jogador):
            player_tag = coc.utils.correct_tag(jogador)
        else:
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            if not clan:
                await interaction.followup.send("❌ Não foi possível carregar os dados do clã para buscar o jogador.")
                return
            member = clan.get_member_by(name=jogador, case_sensitive=False)
            if not member:
                await interaction.followup.send(f"❌ Não encontrei nenhum membro com o nome '{jogador}' no clã.")
                return
            player_tag = member.tag
        
        # Reutiliza a função que busca e formata os dados do perfil
        profile_data = await profile_cog.fetch_player_profile_data(player_tag)

        if "error" in profile_data:
            await interaction.followup.send(f"❌ {profile_data['error']}")
            return

        # Reutiliza a função que cria o embed
        embed = profile_cog.create_profile_embed(profile_data) # Vamos precisar criar essa função

        # Envia a resposta final (usando followup porque adiamos a resposta inicial)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SlashCog(bot))
