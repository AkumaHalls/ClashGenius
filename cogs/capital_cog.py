# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
import asyncio
from typing import Dict, Any, Optional, Tuple
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps
import aiohttp
import datetime

logger = logging.getLogger("capital_cog")

class CapitalCog(commands.Cog, name="Monitoramento da Capital"):
    """Cog para gerenciar a Capital e Gerar Imagens de Resumo no estilo oficial."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_raid_state = None
        # URLs dos assets oficiais do jogo
        self.assets = {
            "bg": "https://i.imgur.com/9Y9t8bM.jpg",           # Fundo da Capital
            "medal": "https://i.imgur.com/sP0Q9pX.png",        # Ícone Medalha Raide
            "trophy": "https://i.imgur.com/5j1c2eH.png",       # Ícone Troféu Capital
            "xp": "https://i.imgur.com/1Q8Z9dY.png",           # Ícone XP Clã
            "banner": "https://i.imgur.com/LdLlVjZ.png"        # Textura para banners
        }
        self.auto_raid_summary.start()

    async def cog_unload(self):
        self.auto_raid_summary.cancel()

    async def fetch_raid_data(self) -> Dict[str, Any]:
        """Busca dados completos da Raide e do Clã para a imagem."""
        try:
            # Busca dados do clã (para troféus totais e liga) e do log de raide
            clan_task = self.bot.api_client.get_clan(self.bot.clan_tag)
            raid_log_task = self.bot.api_client.get_raid_log(self.bot.clan_tag, limit=1)
            clan, raid_log = await asyncio.gather(clan_task, raid_log_task)

            if not raid_log: return {"error": "Nenhum histórico de Raide encontrado."}
            raid = raid_log[0]

            # Formata as datas (ex: "23 Ago - 26 Ago 2024")
            start = raid.start_time.time.strftime("%d %b")
            end = raid.end_time.time.strftime("%d %b %Y")
            date_range = f"{start} - {end}"

            # Calcula medalhas totais (estimativa)
            total_medals = getattr(raid, 'offensive_reward', 0) + getattr(raid, 'defensive_reward', 0)
            
            # Tenta pegar a liga, se não tiver, usa um placeholder
            league_name = getattr(clan.capital_league, 'name', 'Desconhecida')
            league_icon_url = getattr(clan.capital_league.icon, 'url', self.assets['trophy'])

            return {
                "clan_name": clan.name,
                "clan_badge_url": clan.badge.url,
                "date_range": date_range,
                "total_medals": total_medals,
                "total_trophies": clan.capital_points, # Troféus totais do clã na capital
                "clan_xp": getattr(raid, 'clan_xp_reward', 0),
                "league_name": league_name,
                "league_icon_url": league_icon_url,
                "state": getattr(raid, 'state', 'ended')
            }
        except coc.errors.Maintenance: return {"error": "A API da Supercell está em manutenção."}
        except Exception as e:
            logger.error(f"Erro ao buscar dados da Capital: {e}", exc_info=True)
            return {"error": "Erro interno ao processar dados."}

    async def _fetch_image(self, session, url):
        """Baixa uma imagem e retorna como objeto PIL RGBA."""
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return Image.open(BytesIO(data)).convert("RGBA")
        except: return None

    def _draw_rounded_panel(self, img, xy, corner_radius, fill_color, border_color=None, border_width=0):
        """Desenha um painel retangular com bordas arredondadas estilo UI do jogo."""
        draw = ImageDraw.Draw(img)
        x0, y0, x1, y1 = xy
        # Desenha o preenchimento
        draw.rounded_rectangle(xy, corner_radius, fill=fill_color)
        # Desenha a borda se especificada
        if border_color and border_width > 0:
             draw.rounded_rectangle(xy, corner_radius, fill=None, outline=border_color, width=border_width)

    def generate_game_style_image(self, data: Dict, images: Dict[str, Image.Image]) -> BytesIO:
        """Monta a imagem final imitando o layout do jogo."""
        W, H = 1000, 600
        # 1. Fundo
        base = images.get('bg', Image.new('RGBA', (W, H))).resize((W, H), Image.LANCZOS)
        draw = ImageDraw.Draw(base)

        # Fontes (Tenta usar Arial Bold para simular o estilo, com fallback)
        def get_font(size, bold=True):
            try: return ImageFont.truetype("arialbd.ttf" if bold else "arial.ttf", size)
            except: return ImageFont.load_default()

        font_title = get_font(48)
        font_subtitle = get_font(32)
        font_medals = get_font(80)
        font_panel_title = get_font(36)
        font_panel_value = get_font(50)
        font_xp = get_font(30)
        font_league = get_font(42)

        # === CABEÇALHO ===
        # Nome do Clã (com sombra)
        draw.text((103, 33), data['clan_name'], font=font_title, fill=(0,0,0)) # Sombra
        draw.text((100, 30), data['clan_name'], font=font_title, fill=(255, 255, 255))
        
        # Badge do Clã
        if images.get('badge'):
            badge = images['badge'].resize((80, 80), Image.LANCZOS)
            base.paste(badge, (15, 15), badge)

        # Título e Data (lado direito)
        title_txt = "Resultado do Fim de Semana"
        date_txt = data['date_range']
        
        # Sombra e texto do título
        draw.text((W - draw.textlength(title_txt, font=font_subtitle) - 30 + 2, 32), title_txt, font=font_subtitle, fill=(0,0,0))
        draw.text((W - draw.textlength(title_txt, font=font_subtitle) - 30, 30), title_txt, font=font_subtitle, fill=(255, 255, 255))
        # Sombra e texto da data
        draw.text((W - draw.textlength(date_txt, font=font_subtitle) - 30 + 2, 72), date_txt, font=font_subtitle, fill=(0,0,0))
        draw.text((W - draw.textlength(date_txt, font=font_subtitle) - 30, 70), date_txt, font=font_subtitle, fill=(255, 200, 0)) # Amarelo ouro

        # === BANNER DE RECOMPENSA (CENTRO) ===
        banner_y = 150
        # Texto "Você recebeu:"
        reward_txt = "Recompensa Total:"
        draw.text(((W - draw.textlength(reward_txt, font=font_subtitle))/2 + 2, banner_y - 40 + 2), reward_txt, font=font_subtitle, fill=(0,0,0))
        draw.text(((W - draw.textlength(reward_txt, font=font_subtitle))/2, banner_y - 40), reward_txt, font=font_subtitle, fill=(255,255,255))

        # Fundo do banner semi-transparente
        banner_bg = Image.new('RGBA', (600, 120), (0, 0, 0, 150))
        base.paste(banner_bg, ((W-600)//2, banner_y), banner_bg)
        self._draw_rounded_panel(base, ((W-600)//2, banner_y, (W+600)//2, banner_y + 120), 20, (0,0,0,0), (255, 215, 0), 3) # Borda dourada

        # Ícone de Medalha e Valor
        medal_icon = images.get('medal', Image.new('RGBA',(1,1))).resize((100, 100), Image.LANCZOS)
        medal_val_txt = f"+{data['total_medals']:,}"
        total_w = 100 + draw.textlength(medal_val_txt, font=font_medals) + 20
        start_x = (W - total_w) / 2
        
        base.paste(medal_icon, (int(start_x), banner_y + 10), medal_icon)
        draw.text((int(start_x) + 120 + 3, banner_y + 15 + 3), medal_val_txt, font=font_medals, fill=(0,0,0)) # Sombra
        draw.text((int(start_x) + 120, banner_y + 15), medal_val_txt, font=font_medals, fill=(255, 255, 255))

        # === PAINÉIS INFERIORES ===
        panel_y = 320
        panel_h = 230
        panel_w = 460
        panel_bg_color = (230, 225, 210, 230) # Cor bege estilo UI do jogo
        panel_border = (180, 170, 150)

        # --- PAINEL ESQUERDO: TROFÉUS E XP ---
        self._draw_rounded_panel(base, (30, panel_y, 30 + panel_w, panel_y + panel_h), 25, panel_bg_color, panel_border, 4)
        
        # Título Troféus
        draw.text((60, panel_y + 20), "Total de Troféus:", font=font_panel_title, fill=(60, 60, 60))
        
        # Ícone e Valor Troféus
        trophy_icon = images.get('trophy', Image.new('RGBA',(1,1))).resize((70, 70), Image.LANCZOS)
        base.paste(trophy_icon, (60, panel_y + 70), trophy_icon)
        draw.text((140, panel_y + 75), f"{data['total_trophies']:,}", font=font_panel_value, fill=(0,0,0))

        # Barra de XP
        xp_bar_y = panel_y + 160
        self._draw_rounded_panel(base, (50, xp_bar_y, 30 + panel_w - 20, xp_bar_y + 50), 15, (210, 205, 190), (190, 185, 170), 2)
        xp_icon = images.get('xp', Image.new('RGBA',(1,1))).resize((40, 40), Image.LANCZOS)
        base.paste(xp_icon, (60, xp_bar_y + 5), xp_icon)
        draw.text((110, xp_bar_y + 10), f"XP do Clã Ganho: {data['clan_xp']}", font=font_xp, fill=(60, 60, 60))

        # --- PAINEL DIREITO: LIGA ---
        self._draw_rounded_panel(base, (W - 30 - panel_w, panel_y, W - 30, panel_y + panel_h), 25, panel_bg_color, panel_border, 4)
        
        # Título Liga
        draw.text((W - panel_w + 60 - 30, panel_y + 20), "Resultado da Liga:", font=font_panel_title, fill=(60, 60, 60))
        
        # Ícone e Nome da Liga
        if images.get('league'):
            league_icon = images['league'].resize((100, 100), Image.LANCZOS)
            base.paste(league_icon, (W - panel_w + 60 - 30, panel_y + 80), league_icon)
        
        draw.text((W - panel_w + 180 - 30, panel_y + 100), data['league_name'], font=font_league, fill=(0,0,0))

        # Rodapé
        draw.text((30, H - 30), "Gerado pelo ClashGenius", font=get_font(18), fill=(200, 200, 200, 150))

        buffer = BytesIO()
        base.convert("RGB").save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

    async def _process_and_send(self, interaction: Optional[discord.Interaction] = None, automated: bool = False):
        if automated and (self.bot.maintenance_mode or not getattr(self.bot, 'capital_report_channel_id', None)): return

        channel = None
        if automated:
            channel_id = self.bot.capital_report_channel_id
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if not channel: return
        
        data = await self.fetch_raid_data()
        if "error" in data:
            if interaction: await interaction.followup.send(f"❌ {data['error']}")
            return

        # Baixa todos os assets necessários em paralelo
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_image(session, self.assets['bg']),
                self._fetch_image(session, self.assets['medal']),
                self._fetch_image(session, self.assets['trophy']),
                self._fetch_image(session, self.assets['xp']),
                self._fetch_image(session, data['clan_badge_url']),
                self._fetch_image(session, data['league_icon_url'])
            ]
            results = await asyncio.gather(*tasks)
            image_assets = {
                'bg': results[0], 'medal': results[1], 'trophy': results[2],
                'xp': results[3], 'badge': results[4], 'league': results[5]
            }

        # Gera a imagem em uma thread separada
        image_buffer = await asyncio.to_thread(self.generate_game_style_image, data, image_assets)
        
        file = discord.File(fp=image_buffer, filename="raid_summary.png")
        embed = discord.Embed(color=discord.Color(0x2B2D31))
        embed.set_image(url="attachment://raid_summary.png")

        if interaction: await interaction.followup.send(file=file, embed=embed)
        elif channel: await channel.send(content="🏕️ **Resumo Oficial da Capital**", file=file, embed=embed)

    @tasks.loop(minutes=30)
    async def auto_raid_summary(self):
        try:
            data = await self.fetch_raid_data()
            if "error" in data: return
            current_state = data["state"]
            if self.last_raid_state == "ongoing" and current_state == "ended":
                logger.info("Raide finalizada. Gerando imagem estilo jogo...")
                await self._process_and_send(automated=True)
            self.last_raid_state = current_state
        except Exception as e: logger.error(f"Erro no auto_raid_summary: {e}")

    @auto_raid_summary.before_loop
    async def before_auto_raid(self):
        await self.bot.wait_until_ready()
        try:
            data = await self.fetch_raid_data()
            if "error" not in data: self.last_raid_state = data["state"]
        except: pass

    @app_commands.command(name="gerar_raide", description="Gera a imagem do resumo da Capital no estilo oficial do jogo.")
    @app_commands.default_permissions(administrator=True)
    async def cmd_gerar_raide(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._process_and_send(interaction=interaction, automated=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(CapitalCog(bot))
