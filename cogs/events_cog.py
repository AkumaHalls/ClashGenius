# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands
import coc
import datetime
import asyncio
from typing import Optional

logger = logging.getLogger("events_cog")

# ========================================================
# >>> VISÃO DO PERFIL (DENTRO DA MENSAGEM EFÊMERA) <<<
# ========================================================
class ProfileDetailView(discord.ui.View):
    """View que fica anexada ao relatório efêmero, contendo as abas do perfil."""
    def __init__(self, bot: commands.Bot, player_tag: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.player_tag = player_tag

    @discord.ui.button(label="Visão Geral", style=discord.ButtonStyle.primary, custom_id="tab_overview", disabled=True)
    async def btn_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        # O botão principal fica desativado porque já estamos na Visão Geral
        pass

    @discord.ui.button(label="Tropas (Units)", style=discord.ButtonStyle.secondary, custom_id="tab_units")
    async def btn_units(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🛠️ O módulo visualizador de Tropas e Feitiços será implementado em breve!", ephemeral=True)

    @discord.ui.button(label="Evolução (Rushed)", style=discord.ButtonStyle.secondary, custom_id="tab_rushed")
    async def btn_rushed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚙️ A calculadora de Nível de Rush (Pressa de CV) está em desenvolvimento!", ephemeral=True)

# ========================================================
# >>> BOTÃO DE ABRIR PERFIL (NA MENSAGEM DE RH) <<<
# ========================================================
class OpenProfileButtonView(discord.ui.View):
    """View que fica anexada aos alertas de Entrada/Saída do RH."""
    def __init__(self, bot: commands.Bot, player_tag: str):
        super().__init__(timeout=None) 
        self.bot = bot
        self.player_tag = player_tag

    def format_large_number(self, num: int) -> str:
        if num >= 1_000_000_000: return f"{num/1_000_000_000:.2f}B"
        if num >= 1_000_000: return f"{num/1_000_000:.2f}M"
        return f"{num:,}"

    def get_achievement_val(self, player, name: str) -> int:
        ach = player.get_achievement(name)
        return ach.value if ach else 0

    @discord.ui.button(label="📋 Ver Perfil Completo", style=discord.ButtonStyle.secondary, custom_id="btn_open_profile")
    async def btn_open_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Manda o Discord "pensar" mas de forma Efêmera (Só o usuário vê)
        await interaction.response.defer(ephemeral=True)

        try:
            player = await self.bot.api_client.get_player(self.player_tag)
            
            # Montagem do Embed Principal (Estilo ClashPerk)
            embed = discord.Embed(color=0x2b2d31)
            
            # --- Cabeçalho ---
            embed.set_author(name=f"{player.name} ({player.tag})", icon_url=player.league.icon.url if player.league else None)
            embed.set_thumbnail(url=f"https://coc.guide/static/imgs/other/town-hall-{player.town_hall}.png")
            
            header_stats = f"🏛️ **CV {player.town_hall}** | 💠 **Nvl {player.exp_level}** | 🏆 **{player.trophies}** | ⭐ **{player.war_stars}**"
            embed.description = header_stats

            # --- Estatísticas da Temporada (Atuais) ---
            season_stats = (
                f"🎁 **Doadas:** {player.donations}\n"
                f"📥 **Recebidas:** {player.received}\n"
                f"⚔️ **Ataques Vencidos:** {player.attack_wins}\n"
                f"🛡️ **Defesas Vencidas:** {player.defense_wins}"
            )
            embed.add_field(name="📊 Estatísticas da Temporada", value=season_stats, inline=False)

            # --- Conquistas e Economia Vitalícia ---
            gold = self.format_large_number(self.get_achievement_val(player, "Gold Grab"))
            elixir = self.format_large_number(self.get_achievement_val(player, "Elixir Escapade"))
            dark = self.format_large_number(self.get_achievement_val(player, "Heroic Heist"))
            
            donated_lifetime = self.format_large_number(self.get_achievement_val(player, "Friend in Need"))
            cg_points = f"{self.get_achievement_val(player, 'Games Champion'):,}"
            
            cap_looted = f"{self.get_achievement_val(player, 'Aggressive Capitalism'):,}"
            cap_contrib = f"{self.get_achievement_val(player, 'Most Valuable Clanmate'):,}"

            economy_stats = (
                f"**Total Saqueado:**\n🟡 {gold} | 🟣 {elixir} | ⚫ {dark}\n"
                f"**Tropas Doadas (Vitalício):** {donated_lifetime}\n"
                f"**Pontos nos Jogos do Clã:** {cg_points}\n"
                f"**Capital do Clã:**\n"
                f"> 🪙 Saqueado: {cap_looted}\n"
                f"> ⚒️ Contribuído: {cap_contrib}"
            )
            embed.add_field(name="💰 Conquistas Financeiras", value=economy_stats, inline=False)

            # --- Nível dos Heróis ---
            hero_emojis = {
                "Barbarian King": "👑", "Archer Queen": "👸", 
                "Grand Warden": "🧙‍♂️", "Royal Champion": "🏇", "Minion Prince": "🦇"
            }
            heroes_str = ""
            for h in player.heroes:
                if h.is_home_base:
                    emoji = hero_emojis.get(h.name, "🦸")
                    heroes_str += f"{emoji} {h.level}  "
            
            if not heroes_str: heroes_str = "Nenhum Herói"
            embed.add_field(name="🦸 Heróis", value=heroes_str, inline=False)

            # --- Status no Banco de Dados / Discord ---
            discord_str = "❌ `Não Vinculado no Sistema`"
            if self.bot.db is not None:
                db_user = await self.bot.db.users.find_one({"player_tag": player.tag})
                if db_user and db_user.get("discord_id"):
                    discord_str = f"✅ `<@{db_user['discord_id']}>`"
            embed.add_field(name="Discord", value=discord_str, inline=False)
            
            embed.set_footer(text="ClashGenius • Módulo de RH • Visão Privada")

            # Envia a mensagem com os botões de Abas anexados
            view_tabs = ProfileDetailView(self.bot, self.player_tag)
            await interaction.followup.send(embed=embed, view=view_tabs, ephemeral=True)

        except coc.errors.NotFound:
            await interaction.followup.send("❌ Jogador não encontrado na base de dados da Supercell.", ephemeral=True)
        except Exception as e:
            logger.error(f"Erro ao gerar perfil por botão no RH: {e}")
            await interaction.followup.send("❌ Erro interno ao buscar dados do jogador.", ephemeral=True)


# ========================================================
# >>> COG DE EVENTOS DO CLÃ (O MOTOR) <<<
# ========================================================
class EventsCog(commands.Cog, name="Monitor de Eventos"):
    """Gerencia entradas, saídas e promoções do clã em tempo real."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Dispara assim que a cog for carregada para ligar o rastreamento da API."""
        self.bot.loop.create_task(self._start_tracking())

    async def cog_unload(self):
        """Desliga o rastreamento ao descarregar a cog."""
        if self.bot.api_client:
            self.bot.api_client.remove_clan_update(self.bot.clan_tag)

    async def _start_tracking(self):
        """A chave mágica: liga o motor de eventos da Supercell em segundo plano."""
        await self.bot.coc_client_ready.wait()
        
        # 1. Registra os ouvintes (Listeners)
        self.bot.api_client.add_events(
            self.on_clan_member_join,
            self.on_clan_member_leave,
            self.on_clan_member_role_change
        )
        
        # 2. Adiciona o Clã na lista de varredura
        self.bot.api_client.add_clan_update(self.bot.clan_tag)
        
        # 3. Liga o laço de repetição que fica perguntando à Supercell se algo mudou
        self.bot.api_client.start_updates('clan')
        
        logger.info(f"O radar do RH foi ligado com sucesso para o clã: {self.bot.clan_tag}")

    async def _send_rh_alert(self, embed: discord.Embed, tag: str = None):
        """Função base para enviar o alerta no canal de RH."""
        channel_id = self.bot.watchlist_alert_channel_id
        if not channel_id: return
        
        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if channel:
                if tag:
                    # Anexa o botão interativo se houver uma tag de jogador
                    view = OpenProfileButtonView(self.bot, tag)
                    await channel.send(embed=embed, view=view)
                else:
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Erro ao enviar alerta de RH para o Discord: {e}", exc_info=True)

    @coc.ClanEvents.member_join()
    async def on_clan_member_join(self, member: coc.ClanMember, clan: coc.Clan):
        if clan.tag != self.bot.clan_tag: return
        
        embed = discord.Embed(
            title="📥 Novo Recruta!",
            description=f"**{member.name}** (`{member.tag}`) juntou-se ao clã.",
            color=discord.Color.brand_green(),
            timestamp=datetime.datetime.now(self.bot.timezone)
        )
        if member.league and member.league.icon:
            embed.set_thumbnail(url=member.league.icon.url)
            
        embed.add_field(name="Nível CV", value=str(member.town_hall), inline=True)
        embed.add_field(name="Troféus", value=str(member.trophies), inline=True)
        
        # Envia e anexa o botão de Ver Perfil
        await self._send_rh_alert(embed, tag=member.tag)

    @coc.ClanEvents.member_leave()
    async def on_clan_member_leave(self, member: coc.ClanMember, clan: coc.Clan):
        if clan.tag != self.bot.clan_tag: return
        
        embed = discord.Embed(
            title="📤 Baixa no Clã",
            description=f"**{member.name}** (`{member.tag}`) deixou a equipe.",
            color=discord.Color.brand_red(),
            timestamp=datetime.datetime.now(self.bot.timezone)
        )
        # Envia e anexa o botão para caso você precise investigar porque ele saiu
        await self._send_rh_alert(embed, tag=member.tag)

    @coc.ClanEvents.member_role()
    async def on_clan_member_role_change(self, old_member: coc.ClanMember, new_member: coc.ClanMember):
        if new_member.clan.tag != self.bot.clan_tag: return
        
        embed = discord.Embed(
            title="🔄 Alteração de Cargo",
            description=f"A patente de **{new_member.name}** (`{new_member.tag}`) foi atualizada.",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(self.bot.timezone)
        )
        
        # Traduzindo papéis
        roles_pt = {"member": "Membro", "admin": "Ancião", "coLeader": "Co-Líder", "leader": "Líder"}
        old_role = roles_pt.get(str(old_member.role), str(old_member.role))
        new_role = roles_pt.get(str(new_member.role), str(new_member.role))
        
        embed.add_field(name="Antes", value=old_role, inline=True)
        embed.add_field(name="Agora", value=new_role, inline=True)
        
        await self._send_rh_alert(embed, tag=new_member.tag)

async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))
