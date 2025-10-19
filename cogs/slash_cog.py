# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands
import coc

logger = logging.getLogger("slash_cog")

class SlashCog(commands.Cog, name="Comandos de Barra"):
    """Cog para gerenciar todos os comandos de barra (/), mantendo-os organizados."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Comandos Gerais ---
    @app_commands.command(name="ping", description="Verifica a latência do bot.")
    async def ping_slash(self, interaction: discord.Interaction):
        """Verifica a latência atual do bot."""
        latency_ms = round(self.bot.latency * 1000)
        await interaction.response.send_message(f'Pong! 🏓 Latência: {latency_ms}ms')

    @app_commands.command(name="perfil", description="Mostra o perfil de um jogador do clã.")
    @app_commands.describe(jogador="Tag ou nome do jogador para pesquisar.")
    async def perfil_slash(self, interaction: discord.Interaction, jogador: str):
        """Mostra o perfil completo de um membro do clã."""
        await interaction.response.defer(ephemeral=False)
        profile_cog = self.bot.get_cog("Perfis de Membros")
        if not profile_cog:
            await interaction.followup.send("❌ Ocorreu um erro interno (Cog de Perfis não encontrado).")
            return
        try:
            player_tag = None
            if coc.utils.is_valid_tag(jogador):
                player_tag = coc.utils.correct_tag(jogador)
            else:
                clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
                member = clan.get_member_by(name=jogador, case_sensitive=False)
                if not member:
                    await interaction.followup.send(f"❌ Não encontrei nenhum membro com o nome '{jogador}' no clã.")
                    return
                player_tag = member.tag
            profile_data = await profile_cog.fetch_player_profile_data(player_tag)
            if "error" in profile_data:
                await interaction.followup.send(f"❌ {profile_data['error']}")
                return
            embed = profile_cog.create_profile_embed(profile_data)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro no comando /perfil: {e}", exc_info=True)
            await interaction.followup.send("❌ Ocorreu um erro inesperado ao processar o comando.")

    # --- Comandos de Doações ---
    @app_commands.command(name="doacoes", description="Gera relatórios de doações.")
    @app_commands.describe(periodo="O período do relatório ('daily' ou 'weekly').")
    @app_commands.choices(periodo=[
        app_commands.Choice(name="Diário", value="daily"),
        app_commands.Choice(name="Semanal", value="weekly")
    ])
    @app_commands.default_permissions(administrator=True)
    async def doacoes_slash(self, interaction: discord.Interaction, periodo: app_commands.Choice[str]):
        """Gera e envia o relatório de doações diário ou semanal."""
        await interaction.response.defer(ephemeral=True)
        donation_cog = self.bot.get_cog("Gerenciador de Doações")
        if not donation_cog:
            await interaction.followup.send("❌ Ocorreu um erro interno (Cog de Doações não encontrado).")
            return
            
        days = 1 if periodo.value == 'daily' else 7
        success = await donation_cog.generate_and_send_report(days=days, force=True)
        if success:
            await interaction.followup.send(f"✅ Relatório de doações `{periodo.name}` gerado e enviado com sucesso!", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ Não foi possível gerar o relatório de doações `{periodo.name}`. Verifique os logs.", ephemeral=True)

    # --- Comandos de Guerra ---
    @app_commands.command(name="plano_guerra", description="Gera e exibe o plano de ataque da IA para a guerra atual.")
    @app_commands.default_permissions(administrator=True)
    async def plano_guerra_slash(self, interaction: discord.Interaction):
        """Gera e exibe o plano de ataque da IA para a guerra atual."""
        await interaction.response.defer()
        war_advisor_cog = self.bot.get_cog("Conselheiro de Guerra IA")
        if not war_advisor_cog:
            await interaction.followup.send("❌ Ocorreu um erro interno (Cog de Guerra não encontrado).")
            return
        
        class FakeContext:
            async def send(self, *args, **kwargs):
                await interaction.followup.send(*args, **kwargs)
        
        await war_advisor_cog.force_plan_generation(FakeContext())

    @app_commands.command(name="analise_guerra", description="Analisa o equilíbrio de força da guerra atual.")
    @app_commands.default_permissions(administrator=True)
    async def analise_guerra_slash(self, interaction: discord.Interaction):
        """Analisa o equilíbrio de força da guerra atual."""
        await interaction.response.defer()
        war_advisor_cog = self.bot.get_cog("Conselheiro de Guerra IA")
        if not war_advisor_cog:
            await interaction.followup.send("❌ Ocorreu um erro interno (Cog de Guerra não encontrado).")
            return

        class FakeContext:
            async def send(self, *args, **kwargs):
                await interaction.followup.send(*args, **kwargs)
        
        await war_advisor_cog.analyze_war_balance(FakeContext())

    # --- Comandos Administrativos ---
    @app_commands.command(name="painel_admin", description="[Admin] Gera um link de login para o painel de administração.")
    @app_commands.default_permissions(administrator=True)
    async def painel_admin_slash(self, interaction: discord.Interaction):
        """Gera um link de login seguro para o painel web."""
        if not self.bot.base_url:
            await interaction.response.send_message(
                "❌ A `BASE_URL` não está configurada no ambiente do bot. Não é possível gerar o link.",
                ephemeral=True
            )
            return

        login_url = f"{self.bot.base_url}/admin?guild_id={interaction.guild.id}"
        
        embed = discord.Embed(
            title="🔗 Link de Acesso ao Painel Admin",
            description=(
                "Use o botão abaixo para acessar o painel de administração. "
                "Este link já contém a identificação do seu servidor, permitindo o uso de todas as funcionalidades.\n\n"
                "**Este link é para seu uso exclusivo. Não o compartilhe.**"
            ),
            color=discord.Color.blurple()
        )
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Acessar Painel de Administração", url=login_url, emoji="⚙️"))
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    @app_commands.command(name="sync", description="[Admin] Sincroniza os comandos de barra com o Discord.")
    @app_commands.describe(escopo="O escopo da sincronização: 'guild' (este servidor) ou 'global' (todos).")
    @app_commands.choices(escopo=[
        app_commands.Choice(name="Servidor (Guild)", value="guild"),
        app_commands.Choice(name="Global", value="global")
    ])
    @app_commands.default_permissions(administrator=True)
    async def sync_slash(self, interaction: discord.Interaction, escopo: app_commands.Choice[str]):
        """Sincroniza os comandos de barra, limpando os antigos do escopo selecionado."""
        await interaction.response.defer(ephemeral=True)
        
        target_guild = interaction.guild if escopo.value == 'guild' else None
        scope_name = f"o servidor '{interaction.guild.name}'" if target_guild else "globalmente"
        
        try:
            logger.info(f"Iniciando limpeza e sincronização para o escopo: {scope_name}")
            
            # Limpa os comandos do escopo especificado
            self.bot.tree.clear_commands(guild=target_guild)
            await self.bot.tree.sync(guild=target_guild)
            logger.info(f"Comandos de barra foram limpos de: {scope_name}.")
            
            # Sincroniza os comandos atuais do código para o escopo
            synced = await self.bot.tree.sync(guild=target_guild)
            
            msg = f"✅ Comandos limpos e {len(synced)} comandos atuais sincronizados com sucesso em `{scope_name}`."
            await interaction.followup.send(msg, ephemeral=True)
            logger.info(msg)
        except Exception as e:
            logger.error(f"Falha ao sincronizar comandos de barra: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Falha ao sincronizar: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    """Função de setup para carregar o cog no bot."""
    await bot.add_cog(SlashCog(bot))

