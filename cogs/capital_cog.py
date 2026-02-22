# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
import asyncio
from typing import Dict, Any, Optional
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import aiohttp

logger = logging.getLogger("capital_cog")

class CapitalCog(commands.Cog, name="Monitoramento da Capital"):
    """Cog para gerenciar a Capital do Clã, Painel Web e Gerar Imagens de Resumo Premium."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_raid_state = None
        # URLs dos assets oficiais (ícones do jogo)
        self.icon_gold_url = "https://i.imgur.com/Sy8C85a.png" # Ícone Ouro Capital HD
        self.icon_medal_url = "https://i.imgur.com/sP0Q9pX.png" # Ícone Medalha Raide HD
        self.bg_overlay_url = "https://i.imgur.com/LdLlVjZ.png" # Textura de fundo sutil
        self.auto_raid_summary.start()

    async def cog_unload(self):
        self.auto_raid_summary.cancel()

    async def fetch_capital_data_for_web(self) -> Dict[str, Any]:
        """Busca os dados da Raide atual para alimentar o Painel Web e a Imagem."""
        try:
            raid_log = await self.bot.api_client.get_raid_log(self.bot.clan_tag, limit=1)
            if not raid_log:
                 return {"error": "Nenhum histórico de Raide encontrado."}
            
            raid = raid_log[0]
            
            members_data = []
            for m in raid.members:
                attack_limit = getattr(m, 'attack_limit', 5)
                bonus_limit = getattr(m, 'bonus_attack_limit', 0)
                members_data.append({
                    "name": m.name,
                    "tag": m.tag,
                    "attacks": getattr(m, 'attack_count', 0),
                    "limit": attack_limit + bonus_limit,
                    "looted": getattr(m, 'capital_resources_looted', 0)
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
        except Exception as e:
            logger.error(f"Erro ao buscar dados da Capital: {e}", exc_info=True)
            return {"error": "Erro interno ao processar dados da Capital."}

    async def _fetch_image_asset(self, session, url):
        """Baixa uma imagem da web e retorna como objeto PIL."""
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return Image.open(BytesIO(data)).convert("RGBA")
        except Exception as e:
            logger.error(f"Erro ao baixar asset {url}: {e}")
        return None

    # ========================================================
    # >>> GERADOR DE IMAGEM PREMIUM (ESTILO PRO) <<<
    # ========================================================
    def generate_pro_raid_image(self, clan_name: str, raid_data: Dict, icon_gold: Optional[Image.Image], icon_medal: Optional[Image.Image], bg_texture: Optional[Image.Image]) -> BytesIO:
        """Monta a imagem usando assets reais e layout profissional."""
        width, height = 900, 500
        
        # 1. Fundo Base (Degradê Dark Premium)
        base_img = Image.new('RGBA', (width, height), color=(20, 25, 35, 255))
        draw = ImageDraw.Draw(base_img)
        
        # Adiciona textura de fundo se disponível
        if bg_texture:
            bg_texture = bg_texture.resize((width, height))
            base_img = Image.alpha_composite(base_img, bg_texture)
        
        # Faixa de Título Superior
        header_height = 70
        draw.rectangle([0, 0, width, header_height], fill=(30, 35, 45, 255))
        draw.rectangle([0, header_height-4, width, header_height], fill=(255, 200, 0, 180)) # Linha dourada sutil

        # Fontes (Tenta carregar Arial Bold, senão usa default)
        try:
            font_header = ImageFont.truetype("arialbd.ttf", 36)
            font_sub = ImageFont.truetype("arial.ttf", 24)
            font_huge_num = ImageFont.truetype("arialbd.ttf", 72)
            font_big_num = ImageFont.truetype("arialbd.ttf", 58)
            font_label = ImageFont.truetype("arialbd.ttf", 28)
        except IOError:
            font_header = ImageFont.load_default(); font_sub = ImageFont.load_default()
            font_huge_num = ImageFont.load_default(); font_big_num = ImageFont.load_default(); font_label = ImageFont.load_default()

        # Texto do Cabeçalho
        draw.text((30, 15), f"CLÃ: {clan_name.upper()}", fill=(255, 255, 255), font=font_header)
        draw.text((width - 350, 22), "RESUMO DO FIM DE SEMANA", fill=(180, 180, 190), font=font_sub)

        # Função auxiliar para desenhar caixas translúcidas
        def draw_translucent_box(x, y, w, h, color_rgb, alpha):
            overlay = Image.new('RGBA', base_img.size, (0,0,0,0))
            dr = ImageDraw.Draw(overlay)
            dr.rectangle([x, y, x+w, y+h], fill=(color_rgb[0], color_rgb[1], color_rgb[2], alpha), outline=(color_rgb[0]+30, color_rgb[1]+30, color_rgb[2]+30), width=2)
            return Image.alpha_composite(base_img, overlay)

        # --- SEÇÃO PRINCIPAL: OURO TOTAL ---
        base_img = draw_translucent_box(30, 100, width - 60, 150, (40, 44, 52), 220)
        draw = ImageDraw.Draw(base_img) # Atualiza o drawer
        
        draw.text((50, 115), "OURO TOTAL SAQUEADO", fill=(255, 215, 0), font=font_label)
        loot_text = f"{raid_data['total_loot']:,}".replace(",", ".")
        draw.text((160, 155), loot_text, fill=(255, 255, 255), font=font_huge_num)

        if icon_gold:
            icon_gold = icon_gold.resize((100, 100), Image.LANCZOS)
            base_img.paste(icon_gold, (50, 145), icon_gold)

        # --- SEÇÃO INFERIOR DIVIDIDA ---
        box_width = (width - 90) // 2
        box_y = 280
        box_h = 180

        # Caixa Esquerda: Medalhas
        base_img = draw_translucent_box(30, box_y, box_width, box_h, (40, 44, 52), 220)
        draw = ImageDraw.Draw(base_img)
        medals = raid_data.get('offensive_reward', 0) + raid_data.get('defensive_reward', 0)
        draw.text((50, box_y + 20), "MEDALHAS ESTIMADAS", fill=(0, 200, 255), font=font_label)
        draw.text((140, box_y + 65), f"{medals:,}".replace(",", "."), fill=(255, 255, 255), font=font_big_num)
        
        if icon_medal:
            icon_medal = icon_medal.resize((80, 80), Image.LANCZOS)
            base_img.paste(icon_medal, (50, box_y + 65), icon_medal)

        # Caixa Direita: Estatísticas
        base_img = draw_translucent_box(60 + box_width, box_y, box_width, box_h, (35, 38, 45), 230)
        draw = ImageDraw.Draw(base_img)
        start_x_right = 80 + box_width
        draw.text((start_x_right, box_y + 20), "ESTATÍSTICAS DA GUERRA", fill=(200, 200, 200), font=font_label)
        
        # Linhas de estatística
        draw.text((start_x_right, box_y + 70), f"Ataques Usados:", fill=(160, 160, 170), font=font_sub)
        draw.text((start_x_right + 200, box_y + 68), f"{raid_data['total_attacks']}", fill=(255, 255, 255), font=font_label)
        
        draw.text((start_x_right, box_y + 110), f"Distritos Destruídos:", fill=(160, 160, 170), font=font_sub)
        draw.text((start_x_right + 230, box_y + 108), f"{raid_data['destroyed_districts']}", fill=(255, 255, 255), font=font_label)
        
        # Status final
        status_txt = "FINALIZADO" if raid_data.get('state') != "ongoing" else "EM ANDAMENTO"
        status_col = (50, 255, 50) if status_txt == "FINALIZADO" else (255, 200, 0)
        draw.rectangle([width-180, height-40, width-30, height-10], fill=status_col)
        draw.text((width-170, height-38), status_txt, fill=(0,0,0), font=ImageFont.truetype("arialbd.ttf", 20))

        # Finaliza e salva no buffer
        buffer = BytesIO()
        base_img.convert("RGB").save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

    # ========================================================
    # >>> MOTOR AUTÔNOMO E COMANDO (COM DOWNLOAD DE ASSETS) <<<
    # ========================================================
    async def _process_and_send_image(self, interaction: Optional[discord.Interaction] = None, automated: bool = False):
        """Função central que baixa assets, gera a imagem e envia."""
        if automated and (self.bot.maintenance_mode or not getattr(self.bot, 'capital_report_channel_id', None)): return

        channel = None
        if automated:
            channel_id = self.bot.capital_report_channel_id
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if not channel: return
        
        data = await self.fetch_capital_data_for_web()
        if "error" in data:
            if interaction: await interaction.followup.send(f"❌ {data['error']}")
            return

        # Baixa os assets em tempo real antes de gerar a imagem
        async with aiohttp.ClientSession() as session:
            icon_gold_task = asyncio.create_task(self._fetch_image_asset(session, self.icon_gold_url))
            icon_medal_task = asyncio.create_task(self._fetch_image_asset(session, self.icon_medal_url))
            bg_texture_task = asyncio.create_task(self._fetch_image_asset(session, self.bg_overlay_url))
            icon_gold, icon_medal, bg_texture = await asyncio.gather(icon_gold_task, icon_medal_task, bg_texture_task)

        clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
        
        # Roda a geração da imagem (que é pesada) em uma thread separada para não travar o bot
        image_buffer = await asyncio.to_thread(self.generate_pro_raid_image, clan.name, data["raid"], icon_gold, icon_medal, bg_texture)
        
        file = discord.File(fp=image_buffer, filename="raid_summary_pro.png")
        embed = discord.Embed(color=discord.Color(0x1a1d26)) # Cor escura do fundo da imagem
        embed.set_image(url="attachment://raid_summary_pro.png")

        if interaction:
            await interaction.followup.send(file=file, embed=embed)
        elif channel:
            await channel.send(content="🏕️ **Resumo do Fim de Semana da Capital**", file=file, embed=embed)

    @tasks.loop(minutes=30)
    async def auto_raid_summary(self):
        try:
            data = await self.fetch_capital_data_for_web()
            if "error" in data: return
            current_state = data["raid"]["state"]
            if self.last_raid_state == "ongoing" and current_state == "ended":
                logger.info("Raide finalizada. Iniciando geração de imagem PRO...")
                await self._process_and_send_image(automated=True)
            self.last_raid_state = current_state
        except Exception as e: logger.error(f"Erro no auto_raid_summary: {e}")

    @auto_raid_summary.before_loop
    async def before_auto_raid(self):
        await self.bot.wait_until_ready()
        try:
            data = await self.fetch_capital_data_for_web()
            if "error" not in data: self.last_raid_state = data["raid"]["state"]
        except Exception: pass

    @app_commands.command(name="gerar_raide", description="Gera a imagem PREMIUM do resumo da Capital agora.")
    @app_commands.default_permissions(administrator=True)
    async def cmd_gerar_raide(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._process_and_send_image(interaction=interaction, automated=False)

async def setup(bot: commands.Bot):
    await bot.add_cog(CapitalCog(bot))
