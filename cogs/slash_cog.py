# -*- coding: utf-8 -*-
import io
import logging
import discord
from discord import app_commands
from discord.ext import commands
import geniuslib as coc
from geniuslib.formatters import format_th, format_trophies, format_number
from geniuslib.upgrade_tracker import get_th_upgrade_summary, format_upgrade_summary
from geniuslib.comparer import compare_players, compare_clans

logger = logging.getLogger("slash_cog")

class SlashCog(commands.Cog, name="Comandos de Barra"):
    """Cog para gerir todos os comandos de barra (/), mantendo-os organizados."""

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
        # CORREÇÃO AQUI: Procura pelo nome correto "Gerenciador de Doações"
        donation_cog = self.bot.get_cog("Gerenciador de Doações")
        if not donation_cog:
            await interaction.followup.send("❌ Ocorreu um erro interno (Cog de Doações não encontrado).")
            return
            
        days = 1 if periodo.value == 'daily' else 7
        await donation_cog.generate_and_send_report(days=days, force=True, interaction=interaction)
        
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
                "Use o botão abaixo para aceder ao painel de administração. "
                "Este link já contém a identificação do seu servidor, permitindo o uso de todas as funcionalidades.\n\n"
                "**Este link é para seu uso exclusivo. Não o partilhe.**"
            ),
            color=discord.Color.blurple()
        )
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Aceder ao Painel de Administração", url=login_url, emoji="⚙️"))
        
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
        
        admin_cog = self.bot.get_cog("Painel de Administração Avançado")
        if not admin_cog:
            await interaction.followup.send("❌ Ocorreu um erro interno (Cog de Admin não encontrado).")
            return

        guild = interaction.guild if escopo.value == 'guild' else None
        result = await admin_cog.sync_commands(escopo.value, guild)

        if result['status'] == 'success':
            await interaction.followup.send(f"✅ {result['message']}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ {result['message']}", ephemeral=True)

    # --- NOVOS COMANDOS ---

    @app_commands.command(name="buscar_clas", description="🔍 Busca clãs por nome.")
    @app_commands.describe(nome="Nome do clã para buscar", limite="Máximo de resultados (1-10)")
    async def buscar_clas_slash(self, interaction: discord.Interaction, nome: str, limite: int = 5):
        await interaction.response.defer()
        try:
            clans = await self.bot.api_client.search_clans(name=nome, limit=min(max(limite, 1), 10))
            if not clans:
                await interaction.followup.send(f"❌ Nenhum clã encontrado para '{nome}'.")
                return
            embed = discord.Embed(title=f"🔍 Clãs encontrados para '{nome}'", color=0x2b2d31)
            for clan in clans[:10]:
                league_name = clan.war_league.name if clan.war_league else "Sem Liga"
                members_str = f"{clan.member_count}/50"
                th_str = f"TH{clan.required_townhall}" if clan.required_townhall else "Livre"
                embed.add_field(
                    name=f"{clan.name} ({clan.tag})",
                    value=f"🏆 **{clan.points}** | Nvl **{clan.level}** | 👥 {members_str} | TH mín: {th_str} | ⚔️ **{clan.war_wins}**/{clan.war_losses} ({clan.war_win_streak} streak)",
                    inline=False
                )
            embed.set_footer(text="ClashGenius • Busca de Clãs")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro em /buscar_clas: {e}", exc_info=True)
            await interaction.followup.send("❌ Erro ao buscar clãs.")

    @app_commands.command(name="war_log", description="📜 Mostra o histórico de guerras de um clã (scouting).")
    @app_commands.describe(tag="Tag do clã para scout (opcional, usa o clã principal se vazio)")
    async def war_log_slash(self, interaction: discord.Interaction, tag: str = None):
        await interaction.response.defer()
        try:
            clan_tag = coc.utils.correct_tag(tag) if tag else self.bot.clan_tag
            entries = await self.bot.api_client.get_war_log(clan_tag, limit=10)
            if not entries or len(entries) == 0:
                await interaction.followup.send(f"📜 Log de guerra privado ou vazio para `{clan_tag}`.")
                return
            clan = await self.bot.api_client.get_clan(clan_tag)
            embed = discord.Embed(title=f"📜 Histórico de Guerras: {clan.name}", color=0x2b2d31)
            if clan.badge:
                embed.set_thumbnail(url=clan.badge.url)
            count = 0
            async for entry in entries:
                if count >= 10: break
                try:
                    result_emoji = {"win": "✅", "lose": "❌", "tie": "🤝"}
                    emoji = result_emoji.get(str(getattr(entry, 'result', 'tie')), "❓")
                    opp = entry.opponent
                    opp_name = opp.name if opp else "Desconhecido"
                    entry_type = "CWL" if getattr(entry, 'is_league_entry', False) else "Normal"
                    embed.add_field(
                        name=f"{emoji} vs {opp_name}",
                        value=f"⭐ **{entry.clan.stars}** - **{entry.opponent.stars}** | {entry.team_size}v{entry.team_size} | {entry_type}",
                        inline=False
                    )
                    count += 1
                except Exception:
                    continue
            embed.set_footer(text="ClashGenius • Scouting de Guerras")
            await interaction.followup.send(embed=embed)
        except coc.PrivateWarLog:
            await interaction.followup.send(f"❌ Log de guerra privado para `{tag or self.bot.clan_tag}`.")
        except coc.NotFound:
            await interaction.followup.send(f"❌ Clã `{tag}` não encontrado.")
        except Exception as e:
            logger.error(f"Erro em /war_log: {e}", exc_info=True)
            await interaction.followup.send("❌ Erro ao buscar war log.")

    @app_commands.command(name="verificar_conta", description="🔗 Verifica sua conta do Clash of Clans via token.")
    @app_commands.describe(tag="Tag do jogador", token="Token de API gerado no jogo (Configurações > Defina um Token)")
    async def verificar_conta_slash(self, interaction: discord.Interaction, tag: str, token: str):
        await interaction.response.defer(ephemeral=True)
        try:
            player_tag = coc.utils.correct_tag(tag)
            player = await self.bot.api_client.get_player(player_tag)
            result = await self.bot.api_client.verify_player_token(player_tag, token)
            if result.get("success") or result.get("status") == "ok":
                if self.bot.db is not None:
                    await self.bot.db.users.update_one(
                        {"player_tag": player_tag},
                        {"$set": {"player_tag": player_tag, "discord_id": interaction.user.id, "verified_at": discord.utils.utcnow()}},
                        upsert=True
                    )
                await interaction.followup.send(f"✅ Conta **{player.name}** (`{player_tag}`) verificada e vinculada ao seu Discord!", ephemeral=True)
            else:
                await interaction.followup.send("❌ Token inválido. Gere um novo token no jogo: Configurações > Defina um Token de API.", ephemeral=True)
        except coc.NotFound:
            await interaction.followup.send(f"❌ Jogador `{tag}` não encontrado.", ephemeral=True)
        except Exception as e:
            logger.error(f"Erro em /verificar_conta: {e}", exc_info=True)
            await interaction.followup.send("❌ Erro ao verificar conta.", ephemeral=True)

    @app_commands.command(name="legends", description="👑 Mostra estatísticas de Lenda Liga de um jogador.")
    @app_commands.describe(tag="Tag do jogador (opcional, usa sua conta vinculada se vazio)")
    async def legends_slash(self, interaction: discord.Interaction, tag: str = None):
        await interaction.response.defer()
        try:
            player_tag = None
            if tag:
                player_tag = coc.utils.correct_tag(tag)
            elif self.bot.db is not None:
                user = await self.bot.db.users.find_one({"discord_id": interaction.user.id})
                if user:
                    player_tag = user.get("player_tag")
            if not player_tag:
                await interaction.followup.send("❌ Forneça uma tag ou vincule sua conta com `/verificar_conta`.")
                return
            
            player = await self.bot.api_client.get_player(player_tag)
            legend = getattr(player, 'legend_statistics', None)
            if not legend:
                await interaction.followup.send(f"❌ **{player.name}** não tem estatísticas de Lenda Liga.")
                return
            
            embed = discord.Embed(title=f"👑 Lenda Liga: {player.name}", color=0xffd700)
            if player.league and player.league.icon:
                embed.set_thumbnail(url=player.league.icon.url)
            
            lines = []
            if getattr(legend, 'legend_trophies', 0):
                lines.append(f"🏆 **Troféus Lenda:** {legend.legend_trophies}")
            if getattr(legend, 'current_season', None):
                lines.append(f"📊 **Temporada Atual:** {getattr(legend.current_season, 'trophies', 0)} troféus")
            if getattr(legend, 'previous_season', None):
                lines.append(f"📅 **Temporada Anterior:** {getattr(legend.previous_season, 'trophies', 0)} troféus")
            if getattr(legend, 'best_season', None):
                lines.append(f"⭐ **Melhor Temporada:** {getattr(legend.best_season, 'trophies', 0)} troféus")
            
            embed.description = "\n".join(lines) if lines else "Sem dados de lendaliga."
            embed.set_footer(text="ClashGenius • Lenda Liga")
            await interaction.followup.send(embed=embed)
        except coc.NotFound:
            await interaction.followup.send(f"❌ Jogador não encontrado.")
        except Exception as e:
            logger.error(f"Erro em /legends: {e}", exc_info=True)
            await interaction.followup.send("❌ Erro ao buscar dados de Lenda Liga.")

    # === GENIUSLIB V4.2.0: UPGRADE TRACKER ===
    @app_commands.command(name="upgrades", description="🔨 Mostra o resumo de upgrades pendentes de um jogador.")
    @app_commands.describe(jogador="Tag ou nome do jogador")
    async def upgrades_slash(self, interaction: discord.Interaction, jogador: str):
        await interaction.response.defer()
        try:
            player_tag = None
            if coc.utils.is_valid_tag(jogador):
                player_tag = coc.utils.correct_tag(jogador)
            else:
                clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
                member = clan.get_member_by(name=jogador, case_sensitive=False) if clan else None
                if not member:
                    await interaction.followup.send(f"❌ Membro '{jogador}' não encontrado no clã.")
                    return
                player_tag = member.tag
            player = await self.bot.api_client.get_player(player_tag)
            summary = get_th_upgrade_summary(player, target_th=None, builder_count=5)
            raw = format_upgrade_summary(summary)
            embed = discord.Embed(
                title=f"🔨 Upgrades: {player.name}",
                description=f"```{raw}```",
                color=0xffaa00
            )
            embed.set_footer(text="GeniusLib Upgrade Tracker v4.2.0")
            await interaction.followup.send(embed=embed)
        except coc.NotFound:
            await interaction.followup.send("❌ Jogador não encontrado.")
        except Exception as e:
            logger.error(f"Erro em /upgrades: {e}", exc_info=True)
            await interaction.followup.send("❌ Erro ao buscar dados de upgrades.")

    # === GENIUSLIB V4.2.0: COMPARADOR ===
    @app_commands.command(name="comparar", description="⚖️ Compara dois jogadores lado a lado.")
    @app_commands.describe(jogador1="Tag ou nome do primeiro jogador", jogador2="Tag ou nome do segundo jogador")
    async def comparar_slash(self, interaction: discord.Interaction, jogador1: str, jogador2: str):
        await interaction.response.defer()
        try:
            def resolve_tag(input_str):
                if coc.utils.is_valid_tag(input_str):
                    return coc.utils.correct_tag(input_str)
                return None

            tag1 = resolve_tag(jogador1)
            tag2 = resolve_tag(jogador2)
            if not tag1 or not tag2:
                await interaction.followup.send("❌ Forneça tags válidas para ambos os jogadores.")
                return

            p1 = await self.bot.api_client.get_player(tag1)
            p2 = await self.bot.api_client.get_player(tag2)
            result = compare_players(p1, p2)

            left = result["left"]
            right = result["right"]
            diff = result["diff"]

            embed = discord.Embed(title="⚖️ Comparação de Jogadores", color=0x2b2d31)
            embed.add_field(
                name=f"📊 {left['name']} ({left['tag']})",
                value=(
                    f"🏛️ TH: **{left['town_hall']}**\n"
                    f"🏆 Troféus: **{left['trophies']:,}**\n"
                    f"⭐ Estrelas Guerra: **{left['war_stars']}**\n"
                    f"⚔️ Ataques: **{left['attack_wins']}**\n"
                    f"🛡️ Defesas: **{left['defense_wins']}**\n"
                    f"🎁 Doações: **{left['donations']:,}**"
                ),
                inline=True
            )
            embed.add_field(
                name=f"📊 {right['name']} ({right['tag']})",
                value=(
                    f"🏛️ TH: **{right['town_hall']}**\n"
                    f"🏆 Troféus: **{right['trophies']:,}**\n"
                    f"⭐ Estrelas Guerra: **{right['war_stars']}**\n"
                    f"⚔️ Ataques: **{right['attack_wins']}**\n"
                    f"🛡️ Defesas: **{right['defense_wins']}**\n"
                    f"🎁 Doações: **{right['donations']:,}**"
                ),
                inline=True
            )
            diff_str = "\n".join([
                f"🏛️ TH: **{diff['town_hall']:+d}**",
                f"🏆 Troféus: **{diff['trophies']:+d}**",
                f"⭐ Estrelas: **{diff['war_stars']:+d}**",
                f"⚔️ Ataques: **{diff['attack_wins']:+d}**",
                f"🎁 Doações: **{diff['donations']:+d}**",
            ])
            embed.add_field(name="📉 Diferença (P1 - P2)", value=diff_str, inline=False)
            embed.set_footer(text="GeniusLib Comparer v4.2.0")
            await interaction.followup.send(embed=embed)
        except coc.NotFound:
            await interaction.followup.send("❌ Um dos jogadores não foi encontrado.")
        except Exception as e:
            logger.error(f"Erro em /comparar: {e}", exc_info=True)
            await interaction.followup.send("❌ Erro ao comparar jogadores.")

    # === GENIUSLIB V4.2.0: EXPORTADOR ===
    @app_commands.command(name="exportar", description="📤 Exporta dados do clã em JSON ou CSV.")
    @app_commands.describe(tipo="Tipo de dado: 'clan' ou 'membros'", formato="Formato: 'json' ou 'csv'")
    @app_commands.choices(tipo=[
        app_commands.Choice(name="Clã", value="clan"),
        app_commands.Choice(name="Membros", value="members"),
    ])
    @app_commands.choices(formato=[
        app_commands.Choice(name="JSON", value="json"),
        app_commands.Choice(name="CSV", value="csv"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def exportar_slash(self, interaction: discord.Interaction, tipo: app_commands.Choice[str], formato: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        try:
            web_api = self.bot.get_cog("Web API")
            if not web_api:
                await interaction.followup.send("❌ Cog Web API não encontrado.")
                return
            if tipo.value == "clan":
                result = await web_api.export_clan_data_for_web(formato.value)
            else:
                result = await web_api.export_players_for_web(formato.value)
            if "error" in result:
                await interaction.followup.send(f"❌ {result['error']}")
                return
            data_str = result["data"]
            ext = "json" if formato.value == "json" else "csv"
            filename = f"clashgenius_export.{ext}"
            if len(data_str) < 1900:
                await interaction.followup.send(f"📤 **Exportação em {formato.value.upper()}:**\n```{data_str[:1900]}```")
            else:
                await interaction.followup.send(
                    f"📤 Exportação gerada! ({len(data_str)} caracteres)",
                    file=discord.File(io.BytesIO(data_str.encode()), filename=filename)
                )
        except Exception as e:
            logger.error(f"Erro em /exportar: {e}", exc_info=True)
            await interaction.followup.send("❌ Erro ao exportar dados.")

# Esta função é ESSENCIAL para que o cog seja carregado.
async def setup(bot: commands.Bot):
    """Função de setup para carregar o cog no bot."""
    await bot.add_cog(SlashCog(bot))

