# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
import asyncio
from typing import Dict, Any, Optional
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import os

logger = logging.getLogger("capital_cog")

class CapitalCog(commands.Cog, name="Monitoramento da Capital"):
    """Cog para gerenciar a Capital e Gerar Imagens de Resumo no estilo exato do ClashPerk/In-Game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_raid_state = None
        self.font_path = "supercell_magic.ttf"
        
        # Assets originais em alta definição da Wiki
        self.assets = {
            "bg": "https://static.wikia.nocookie.net/clashofclans/images/2/23/Capital_Peak_Scenery.png",
            "medal": "https://static.wikia.nocookie.net/clashofclans/images/5/52/Raid_Medal.png",
            "trophy": "https://static.wikia.nocookie.net/clashofclans/images/0/05/Capital_Trophy.png",
            "xp": "https://static.wikia.nocookie.net/clashofclans/images/c/c9/XP.png"
        }
        self.auto_raid_summary.start()

    async def cog_unload(self):
        self.auto_raid_summary.cancel()

    # ========================================================
    # >>> DOWNLOADER DE FONTE OFICIAL <<<
    # ========================================================
    async def _ensure_font_exists(self):
        """Baixa a fonte oficial do Clash of Clans se não existir na VPS (Render)."""
        if not os.path.exists(self.font_path):
            try:
                font_url = "https://raw.githubusercontent.com/ApexzXD/Clash-of-Clans-API/master/Font/Supercell-Magic.ttf"
                async with aiohttp.ClientSession() as session:
                    async with session.get(font_url) as resp:
                        if resp.status == 200:
                            with open(self.font_path, 'wb') as f:
                                f.write(await resp.read())
                            logger.info("Fonte Supercell-Magic baixada com sucesso!")
            except Exception as e:
                logger.error(f"Erro ao baixar a fonte: {e}")

    # ========================================================
    # >>> FUNÇÃO DO PAINEL WEB (NÃO APAGAR) <<<
    # ========================================================
    async def fetch_capital_data_for_web(self) -> Dict[str, Any]:
        try:
            raid_log = await self.bot.api_client.get_raid_log(self.bot.clan_tag, limit=1)
            if not raid_log: return {"error": "Nenhum histórico de Raide encontrado."}
            raid = raid_log[0]
            members_data = []
            for m in raid.members:
                limit = getattr(m, 'attack_limit', 5) + getattr(m, 'bonus_attack_limit', 0)
                members_data.append({
                    "name": m.name, "tag": m.tag, "attacks": getattr(m, 'attack_count', 0),
                    "limit": limit, "looted": getattr(m, 'capital_resources_looted', 0)
                })
            members_data.sort(key=lambda x: x["looted"], reverse=True)
            return {
                "raid": {
                    "state": getattr(raid, 'state', 'ended'),
                    "start_time": raid.start_time.time.isoformat() if getattr(raid, 'start_time', None) else None,
                    "end_time": raid.end_time.time.isoformat() if getattr(raid, 'end_time', None) else None,
                    "total_loot": getattr(raid, 'total_loot', 0),
                    "total_attacks": getattr(raid, 'attack_count', 0),
                    "destroyed_districts": getattr(raid, 'destroyed_district_count', 0),
                    "offensive_reward": getattr(raid, 'offensive_reward', 0),
                    "defensive_reward": getattr(raid, 'defensive_reward', 0)
                },
                "members": members_data
            }
        except coc.errors.Maintenance: return {"error": "A API da Supercell está em manutenção."}
        except Exception as e: return {"error": "Erro interno ao processar dados da Capital."}

    # ========================================================
    # >>> DADOS DA IMAGEM E UTILITÁRIOS <<<
    # ========================================================
    def _translate_date(self, date_obj) -> str:
        if not date_obj: return "??"
        meses = {"Jan": "Jan", "Feb": "Fev", "Mar": "Mar", "Apr": "Abr", "May": "Mai", "Jun": "Jun", 
                 "Jul": "Jul", "Aug": "Ago", "Sep": "Set", "Oct": "Out", "Nov": "Nov", "Dec": "Dez"}
        en_month = date_obj.strftime("%b")
        pt_month = meses.get(en_month, en_month)
        return f"{date_obj.strftime('%d')} {pt_month}"

    async def fetch_raid_data(self) -> Dict[str, Any]:
        try:
            clan, raid_log = await asyncio.gather(
                self.bot.api_client.get_clan(self.bot.clan_tag),
                self.bot.api_client.get_raid_log(self.bot.clan_tag, limit=1)
            )
            if not raid_log: return {"error": "Nenhum histórico."}
            raid = raid_log[0]

            start_str = self._translate_date(getattr(raid, 'start_time', None).time if getattr(raid, 'start_time', None) else None)
            end_time = getattr(raid, 'end_time', None).time if getattr(raid, 'end_time', None) else None
            end_str = self._translate_date(end_time)
            year = end_time.strftime("%Y") if end_time else "2025"
            date_range = f"{start_str} - {end_str} {year}"

            total_medals = getattr(raid, 'offensive_reward', 0) + getattr(raid, 'defensive_reward', 0)
            
            league_name = "Desconhecida"
            league_icon_url = self.assets['trophy'] 
            if clan.capital_league:
                league_name = getattr(clan.capital_league, 'name', 'Desconhecida')
                if hasattr(clan.capital_league, 'icon') and clan.capital_league.icon:
                    league_icon_url = getattr(clan.capital_league.icon, 'url', self.assets['trophy'])

            return {
                "clan_name": clan.name, "clan_badge_url": clan.badge.url, "clan_level": clan.level,
                "date_range": date_range, "total_medals": total_medals,
                "total_trophies": getattr(clan, 'capital_points', 0),
                "clan_xp": getattr(raid, 'clan_xp_reward', 0),
                "league_name": league_name, "league_icon_url": league_icon_url,
                "state": getattr(raid, 'state', 'ended')
            }
        except Exception as e: return {"error": "Erro ao processar dados."}

    async def _fetch_image(self, session, url):
        headers = { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" }
        try:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200: return Image.open(BytesIO(await resp.read())).convert("RGBA")
        except: pass
        return None

    def _draw_text_outlined(self, draw, pos, text, font, fill_color, stroke_color=(0,0,0), stroke_width=3):
        """Escreve o texto com a borda preta grossa, marca registrada da UI do Clash."""
        x, y = pos
        # Desenha a borda
        for dx in range(-stroke_width, stroke_width+1):
            for dy in range(-stroke_width, stroke_width+1):
                if dx*dx + dy*dy <= stroke_width*stroke_width:
                    draw.text((x+dx, y+dy), text, font=font, fill=stroke_color)
        # Desenha o texto principal
        draw.text((x, y), text, font=font, fill=fill_color)

    # ========================================================
    # >>> COMPOSITOR DE ARTE (CLASHPERK CLONE) <<<
    # ========================================================
    def generate_game_style_image(self, data: Dict, images: Dict[str, Image.Image]) -> BytesIO:
        W, H = 1000, 620
        base = Image.new('RGBA', (W, H), color=(234, 230, 223)) # Cor bege de fundo da UI base
        draw = ImageDraw.Draw(base)

        # Sistema de Fonte
        def get_font(size):
            try: return ImageFont.truetype(self.font_path, size)
            except: 
                try: return ImageFont.truetype("arialbd.ttf", size)
                except: return ImageFont.load_default()

        f_huge = get_font(52)
        f_title = get_font(34)
        f_sub = get_font(26)
        f_small = get_font(22)

        # 1. PARTE SUPERIOR: Fundo da Capital
        bg_img = images.get('bg')
        if bg_img:
            # Corta e redimensiona para o topo
            bg_img = bg_img.resize((W, int(W * bg_img.height / bg_img.width)), Image.LANCZOS)
            bg_img = bg_img.crop((0, 0, W, 310))
            base.paste(bg_img, (0, 0))
        else:
            draw.rectangle([0, 0, W, 310], fill=(70, 90, 110))

        # Divider branco grosso
        draw.rectangle([0, 305, W, 315], fill=(255, 255, 255))

        # 2. CABEÇALHO ESQUERDO (Badge e Nome)
        if images.get('badge'):
            badge = images['badge'].resize((90, 90), Image.LANCZOS)
            base.paste(badge, (20, 15), badge)
        self._draw_text_outlined(draw, (120, 35), data['clan_name'], f_title, (255, 255, 255), stroke_width=4)

        # 3. CABEÇALHO DIREITO (Títulos e Data)
        txt_title = "Resultados do Fim de Semana"
        txt_date = data['date_range']
        tw = draw.textlength(txt_title, font=f_sub)
        dw = draw.textlength(txt_date, font=f_sub)
        self._draw_text_outlined(draw, (W - tw - 20, 25), txt_title, f_sub, (255, 255, 255), stroke_width=3)
        self._draw_text_outlined(draw, (W - dw - 20, 60), txt_date, f_sub, (255, 255, 255), stroke_width=3)

        # 4. BANNER CENTRAL TRANSLÚCIDO (Medalhas/Loot Principal)
        pill_w, pill_h = 400, 80
        pill_x, pill_y = (W - pill_w) // 2, 170
        
        txt_reward = "Você recebeu:"
        rw = draw.textlength(txt_reward, font=f_sub)
        self._draw_text_outlined(draw, ((W - rw) // 2, pill_y - 35), txt_reward, f_sub, (255, 255, 255), stroke_width=3)

        # Desenha a pílula preta translúcida
        overlay = Image.new('RGBA', (W, H), (0,0,0,0))
        d_overlay = ImageDraw.Draw(overlay)
        d_overlay.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h], radius=40, fill=(0, 0, 0, 140))
        base = Image.alpha_composite(base, overlay)
        draw = ImageDraw.Draw(base)

        # Ícone de Medalha / Troféu Ouro
        icon_main = images.get('medal') or images.get('trophy')
        if icon_main:
            icon_main = icon_main.resize((110, 110), Image.LANCZOS)
            base.paste(icon_main, (pill_x - 40, pill_y - 15), icon_main)
        
        # Texto da Medalha
        val_txt = f"+{data['total_medals']}" if data['total_medals'] > 0 else "0"
        vw = draw.textlength(val_txt, font=f_huge)
        self._draw_text_outlined(draw, (pill_x + (pill_w - vw)//2 + 20, pill_y + 10), val_txt, f_huge, (255, 255, 255), stroke_width=4)

        # 5. PAINÉIS INFERIORES
        y_bot = 330
        h_bot = 260
        w_panel = 460

        # --- PAINEL ESQUERDO (TROFÉUS E XP) ---
        p1_x = 25
        # Fundo do painel
        draw.rounded_rectangle([p1_x, y_bot, p1_x + w_panel, y_bot + h_bot], radius=15, fill=(202, 195, 179), outline=(163, 156, 141), width=4)
        
        # Título "Total de Troféus:"
        self._draw_text_outlined(draw, (p1_x + 60, y_bot + 25), "Total de Troféus:", f_title, (255, 255, 255), stroke_width=3)
        
        # Valor dos Troféus
        trophy_val = f"{data['total_trophies']}"
        self._draw_text_outlined(draw, (p1_x + 90, y_bot + 80), trophy_val, f_huge, (255, 255, 255), stroke_width=4)
        
        # Ícone do Troféu
        if images.get('trophy'):
            ic = images['trophy'].resize((70, 70), Image.LANCZOS)
            base.paste(ic, (p1_x + 90 + int(draw.textlength(trophy_val, font=f_huge)) + 15, y_bot + 80), ic)

        # Pílula de XP
        xp_y = y_bot + 180
        draw.rounded_rectangle([p1_x + 30, xp_y, p1_x + w_panel - 30, xp_y + 55], radius=25, fill=(225, 221, 211), outline=(255, 255, 255), width=2)
        if images.get('xp'):
            xp_ic = images['xp'].resize((45, 45), Image.LANCZOS)
            base.paste(xp_ic, (p1_x + 40, xp_y + 5), xp_ic)
        self._draw_text_outlined(draw, (p1_x + 100, xp_y + 12), f"XP do Clã: {data['clan_xp']}", f_sub, (255, 255, 255), stroke_width=3)


        # --- PAINEL DIREITO (LIGA) ---
        p2_x = W - w_panel - 25
        # Fundo do painel direito
        draw.rounded_rectangle([p2_x, y_bot, p2_x + w_panel, y_bot + h_bot], radius=15, fill=(202, 195, 179), outline=(163, 156, 141), width=4)
        
        # Faixa cinza escura da liga
        draw.rounded_rectangle([p2_x, y_bot + 70, p2_x + w_panel, y_bot + h_bot], radius=15, fill=(103, 106, 107))
        # Refaz o preenchimento reto em cima para não ter cantos arredondados vazando
        draw.rectangle([p2_x, y_bot + 70, p2_x + w_panel, y_bot + 100], fill=(103, 106, 107))

        # Título Liga
        txt_league_title = "Liga Atual da Capital"
        lw = draw.textlength(txt_league_title, font=f_sub)
        self._draw_text_outlined(draw, (p2_x + (w_panel - lw)//2, y_bot + 20), txt_league_title, f_sub, (255, 255, 255), stroke_width=3)

        # Sinal de Igual, Ícone e Nome da Liga
        self._draw_text_outlined(draw, (p2_x + 30, y_bot + 130), "=", f_huge, (255, 255, 255), stroke_width=4)
        
        if images.get('league'):
            l_ic = images['league'].resize((120, 120), Image.LANCZOS)
            base.paste(l_ic, (p2_x + 100, y_bot + 100), l_ic)
            
        self._draw_text_outlined(draw, (p2_x + 230, y_bot + 120), data['league_name'], f_title, (255, 255, 255), stroke_width=3)
        self._draw_text_outlined(draw, (p2_x + 230, y_bot + 175), f"{data['total_trophies']} Troféus", f_small, (255, 215, 0), stroke_width=2) # Texto dourado

        # Retorna a imagem montada
        buffer = BytesIO()
        base.convert("RGB").save(buffer, format="PNG", quality=100)
        buffer.seek(0)
        return buffer

    async def _process_and_send(self, interaction: Optional[discord.Interaction] = None, automated: bool = False):
        if automated and (self.bot.maintenance_mode or not getattr(self.bot, 'capital_report_channel_id', None)): return

        channel = None
        if automated:
            channel_id = self.bot.capital_report_channel_id
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if not channel: return
        
        await self._ensure_font_exists()
        
        data = await self.fetch_raid_data()
        if "error" in data:
            if interaction: await interaction.followup.send(f"❌ {data['error']}")
            return

        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_image(session, self.assets['bg']),
                self._fetch_image(session, self.assets['medal']),
                self._fetch_image(session, self.assets['trophy']),
                self._fetch_image(session, self.assets['xp']),
                self._fetch_image(session, data['clan_badge_url']),
                self._fetch_image(session, data['league_icon_url'])
            ]
            res = await asyncio.gather(*tasks)
            image_assets = {'bg': res[0], 'medal': res[1], 'trophy': res[2], 'xp': res[3], 'badge': res[4], 'league': res[5]}

        image_buffer = await asyncio.to_thread(self.generate_game_style_image, data, image_assets)
        
        file = discord.File(fp=image_buffer, filename="raid_summary.png")
        embed = discord.Embed(color=discord.Color(0xEAE6DF)) # Cor da borda do embed combinando com a imagem
        embed.set_image(url="attachment://raid_summary.png")

        if interaction: await interaction.followup.send(file=file, embed=embed)
        elif channel: await channel.send(content="🏕️ **Resultados do Fim de Semana da Capital!**", file=file, embed=embed)

    @tasks.loop(minutes=30)
    async def auto_raid_summary(self):
        try:
            data = await self.fetch_raid_data()
            if "error" in data: return
            current_state = data.get("state", "ended")
            if self.last_raid_state == "ongoing" and current_state == "ended":
                await self._process_and_send(automated=True)
            self.last_raid_state = current_state
        except Exception as e: logger.error(f"Erro no auto_raid_summary: {e}")

    @auto_raid_summary.before_loop
    async def before_auto_raid(self):
        await self.bot.wait_until_ready()
        try:
            data = await self.fetch_raid_data()
            if "error" not in data: self.last_raid_state = data.get("state", "ended")
        except: pass

    @app_commands.command(name="gerar_raide", description="Gera a imagem do resumo da Capital idêntica à do jogo.")
    @app_commands.default_permissions(administrator=True)
    async def cmd_gerar_raide(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._process_and_send(interaction=interaction, automated=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(CapitalCog(bot))
