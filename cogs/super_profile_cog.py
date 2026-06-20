import discord
from discord.ext import commands
from discord.ui import View, Button
import geniuslib as coc
from geniuslib.formatters import format_th, format_trophies, format_number
from geniuslib.upgrade_tracker import get_th_upgrade_summary, format_upgrade_summary

# --- LÓGICA DE CÁLCULO (HELPERS) ---

def calculate_rushed_status(player):
    """Calcula se o jogador é rushed baseado nos heróis vs TH."""
    # Metas aproximadas de níveis de heróis para considerar "Não Rushed"
    th_hero_expectations = {
        9: 20, 10: 50, 11: 80, 12: 120, 13: 170, 14: 220, 15: 280, 16: 320, 17: 380, 18: 450
    }
    
    if player.town_hall < 9:
        return "N/A (TH Baixo)", discord.Color.blue()

    expected_total = th_hero_expectations.get(player.town_hall, 0)
    if expected_total == 0:
        return "Análise Indisponível", discord.Color.greyple()

    current_total = sum(h.level for h in player.heroes if h.village == coc.VillageType.home)
    
    ratio = current_total / expected_total
    
    if ratio >= 0.95: return "💎 Maxed / Sólido", discord.Color.green()
    if ratio >= 0.75: return "⚖️ Equilibrado", discord.Color.gold()
    if ratio >= 0.50: return "⚠️ Levemente Rushed", discord.Color.orange()
    return "🚨 MUITO RUSHED", discord.Color.red()

def get_progress_bar(current, maximum, length=10):
    """Cria uma barrinha visual de progresso [====....]"""
    if maximum == 0: maximum = 1 # Evitar divisão por zero
    percent = min(1.0, current / maximum)
    filled = int(length * percent)
    return "█" * filled + "░" * (length - filled) + f" {int(percent*100)}%"

# --- INTERFACE (VIEW) ---

class SuperProfileView(View):
    def __init__(self, ctx, player):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.player = player
        
        # Botão de Link Externo para Histórico (Solução sem Database)
        url_history = f"https://www.clashofstats.com/players/{player.tag.strip('#')}/history/"
        self.add_item(Button(label="Histórico Completo 🔗", url=url_history, style=discord.ButtonStyle.link))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("Apenas quem digitou o comando pode mexer aqui!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🏠 Geral", style=discord.ButtonStyle.primary, custom_id="btn_home")
    async def home_btn(self, interaction: discord.Interaction, button: Button):
        embed = self.create_home_embed()
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="⚔️ Tropas", style=discord.ButtonStyle.secondary, custom_id="btn_units")
    async def units_btn(self, interaction: discord.Interaction, button: Button):
        embed = self.create_units_embed()
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="🔨 Upgrades", style=discord.ButtonStyle.secondary, custom_id="btn_upgrades")
    async def upgrades_btn(self, interaction: discord.Interaction, button: Button):
        embed = self.create_upgrades_embed()
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="🚨 Rushed?", style=discord.ButtonStyle.danger, custom_id="btn_rushed")
    async def rushed_btn(self, interaction: discord.Interaction, button: Button):
        embed = self.create_rushed_embed()
        await interaction.response.edit_message(embed=embed)

    # --- GERADORES DE EMBED ---
    
    def create_home_embed(self):
        p = self.player
        embed = discord.Embed(title=f"Perfil: {p.name}", color=discord.Color.blurple())
        embed.description = f"**Tag:** {p.tag}\n**TH:** {format_th(p.town_hall)} ⭐{p.town_hall_weapon_level or 0}"
        
        clan_txt = f"{p.clan.name} ({p.role})" if p.clan else "Sem Clã"
        embed.add_field(name="🏰 Clã", value=clan_txt, inline=True)
        embed.add_field(name="🏆 Troféus", value=f"{format_trophies(p.trophies)} / PB: {p.best_trophies}", inline=True)
        embed.add_field(name="🌟 War Stars", value=str(p.war_stars), inline=True)
        
        # Tentativa de pegar ícone da liga
        if p.league:
            embed.set_thumbnail(url=p.league.icon.medium)
        elif p.clan and p.clan.badge:
             embed.set_thumbnail(url=p.clan.badge.medium)
             
        return embed

    def create_units_embed(self):
        p = self.player
        embed = discord.Embed(title=f"Tropas & Heróis - {p.name}", color=discord.Color.green())
        
        # Heróis
        heroes_txt = ""
        for h in p.heroes:
            if h.village == coc.VillageType.home:
                heroes_txt += f"**{h.name}**: {h.level}\n"
        if heroes_txt: embed.add_field(name="👑 Heróis", value=heroes_txt, inline=True)
        
        # Pets
        pets_txt = ""
        for pet in p.pets:
            if pet.village == coc.VillageType.home:
                pets_txt += f"**{pet.name}**: {pet.level}\n"
        if pets_txt: embed.add_field(name="🐾 Pets", value=pets_txt, inline=True)
        
        return embed

    def create_upgrades_embed(self):
        p = self.player
        embed = discord.Embed(title=f"Progresso TH{p.town_hall} - {p.name}", color=discord.Color.gold())
        
        try:
            summary = get_th_upgrade_summary(p, target_th=None, builder_count=5)
            if summary and summary.upgrades:
                raw = format_upgrade_summary(summary)
                lines = raw.split("\n")
                for line in lines:
                    if "📊" in line:
                        embed.description = f"**{line.strip()}**"
                    elif "🏠" in line or "🪙" in line or "🧪" in line or "💎" in line or "⏱" in line or "⏳" in line or "📦" in line:
                        embed.add_field(name="▸", value=line.strip(), inline=False)
            else:
                embed.description = "✅ Nenhum upgrade pendente encontrado!"
        except Exception:
            embed.description = "Dados de upgrade indisponíveis no momento."
        
        embed.set_footer(text="GeniusLib Upgrade Tracker v4.3.0 • Baseado nos dados da API")
        return embed

    def create_rushed_embed(self):
        p = self.player
        status, color = calculate_rushed_status(p)
        
        embed = discord.Embed(title="Análise de Vila (Rushed)", color=color)
        embed.add_field(name="Veredito", value=f"### {status}", inline=False)
        
        tips = "• Upe seus heróis antes de subir o TH!\n• Foque em maximizar o laboratório."
        if "Maxed" in status: tips = "• Parabéns! Você está pronto para o próximo TH."
        
        embed.add_field(name="Dica do Bot", value=tips, inline=False)
        return embed


# --- CLASSE COG ---

class SuperProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Novo comando com nome diferente para não conflitar
    @commands.command(name="ver", aliases=["view", "checar"])
    async def view_player(self, ctx, tag: str = None):
        """
        Visualizador de Perfil Interativo (Estilo App).
        Uso: !ver #TAG
        """
        if not tag:
            await ctx.send("Por favor, digite a tag. Ex: `!ver #TAG`")
            return

        tag = coc.utils.correct_tag(tag)

        try:
            player = await self.bot.api_client.get_player(tag)
        except coc.NotFound:
            await ctx.send("❌ Jogador não encontrado!")
            return

        # Envia a primeira mensagem com a View
        view = SuperProfileView(ctx, player)
        embed = view.create_home_embed()
        
        await ctx.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(SuperProfileCog(bot))