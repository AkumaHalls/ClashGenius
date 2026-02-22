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

logger = logging.getLogger("capital_cog")

class CapitalCog(commands.Cog, name="Monitoramento da Capital"):
    """Cog para gerenciar a Capital do Clã, Painel Web e Gerar Imagens de Resumo."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_raid_state = None
        self.auto_raid_summary.start()

    async def cog_unload(self):
        self.auto_raid_summary.cancel()

    async def fetch_capital_data_for_web(self) -> Dict[str, Any]:
        """Busca os dados da Raide atual para alimentar o Painel Web."""
        try:
            # CORREÇÃO: O método correto em coc.py é get_raid_log, não get_raid_seasons
            raid_log = await self.bot.api_client.get_raid_log(self.bot.clan_tag, limit=1)
            if not raid_log:
                 return {"error": "Nenhum histórico de Raide encontrado."}
            
            raid = raid_log[0]
            
            members_data = []
            for m in raid.members:
                # Usando getattr para blindar contra atualizações da Supercell onde atributos sumam
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

        except coc.errors.Maintenance:
            return {"error": "A API da Supercell está em manutenção."}
        except Exception as e:
            logger.error(f"Erro ao buscar dados da Capital para a Web: {e}", exc_info=True)
            return {"error": "Erro interno ao processar dados da Capital."}

    # ========================================================
    # >>> GERADOR DE IMAGEM (ESTILO CLASHPERK) <<<
    # ========================================================
    def generate_raid_image(self, clan_name: str, raid_data: Dict) -> BytesIO:
        """Desenha uma imagem premium do zero com os resultados da raide."""
        width, height = 800, 450
        
        # Criação do Fundo Escuro Premium (Estilo Discord/Clash)
        img = Image.new('RGB', (width, height), color=(26, 32, 44))
        draw = ImageDraw.Draw(img)
        
        # Borda Superior Dourada
        draw.rectangle([0, 0, width, 15], fill=(212, 175, 55))

        # Título
        try:
            # Tenta carregar uma fonte do sistema, se não achar usa a default pixelada
            font_title = ImageFont.truetype("arialbd.ttf", 40)
            font_subtitle = ImageFont.truetype("arial.ttf", 25)
            font_large = ImageFont.truetype("arialbd.ttf", 60)
        except IOError:
            font_title = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()
            font_large = ImageFont.load_default()

        # Textos do Cabeçalho
        draw.text((40, 40), f"Clã: {clan_name}", fill=(255, 255, 255), font=font_title)
        draw.text((40, 90), "RESUMO DO FIM DE SEMANA DE RAIDE", fill=(160, 174, 192), font=font_subtitle)

        # Desenho dos Cartões Internos
        def draw_rounded_rect(draw, xy, radius, fill):
            x0, y0, x1, y1 = xy
            draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
            draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
            draw.pieslice([x0, y0, x0 + radius * 2, y0 + radius * 2], 180, 270, fill=fill)
            draw.pieslice([x1 - radius * 2, y0, x1, y0 + radius * 2], 270, 360, fill=fill)
            draw.pieslice([x0, y1 - radius * 2, x0 + radius * 2, y1], 90, 180, fill=fill)
            draw.pieslice([x1 - radius * 2, y1 - radius * 2, x1, y1], 0, 90, fill=fill)

        # Caixa de Ouro (Loot Total)
        draw_rounded_rect(draw, [40, 150, 380, 280], 15, fill=(45, 55, 72))
        draw.text((60, 170), "Ouro Saqueado Total", fill=(212, 175, 55), font=font_subtitle)
        draw.text((60, 205), f"{raid_data['total_loot']:,}", fill=(255, 255, 255), font=font_large)

        # Caixa de Medalhas (Ofensiva + Defensiva)
        medals = raid_data.get('offensive_reward', 0) + raid_data.get('defensive_reward', 0)
        draw_rounded_rect(draw, [420, 150, 760, 280], 15, fill=(45, 55, 72))
        draw.text((440, 170), "Medalhas de Raide (Estimativa)", fill=(104, 211, 145), font=font_subtitle)
        draw.text((440, 205), f"{medals:,}", fill=(255, 255, 255), font=font_large)

        # Estatísticas Secundárias
        draw_rounded_rect(draw, [40, 310, 760, 410], 15, fill=(23, 25, 35))
        draw.text((80, 330), f"Ataques Usados: {raid_data['total_attacks']}", fill=(226, 232, 240), font=font_subtitle)
        draw.text((80, 365), f"Distritos Destruídos: {raid_data['destroyed_districts']}", fill=(226, 232, 240), font=font_subtitle)
        
        # Status
        state_text = "Em Andamento" if raid_data.get('state') == "ongoing" else "Finalizado"
        draw.text((500, 345), f"Status: {state_text}", fill=(255, 100, 100) if state_text == "Finalizado" else (100, 255, 100), font=font_title)

        # Salva em memória (buffer) para mandar pro Discord sem criar arquivo físico
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    # ========================================================
    # >>> MOTOR AUTÔNOMO <<<
    # ========================================================
    @tasks.loop(minutes=30)
    async def auto_raid_summary(self):
        """Verifica a cada 30 min se a Raide acabou. Se acabou, gera e posta a imagem."""
        if self.bot.maintenance_mode or not getattr(self.bot, 'capital_report_channel_id', None):
            return

        try:
            data = await self.fetch_capital_data_for_web()
            if "error" in data: return

            current_state = data["raid"]["state"]

            # Lógica: Se antes estava 'ongoing' (rolando) e agora virou 'ended' (acabou)
            if self.last_raid_state == "ongoing" and current_state == "ended":
                logger.info("Raide da Capital encerrada! Gerando imagem de resumo...")
                
                channel_id = self.bot.capital_report_channel_id
                channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
                
                if channel:
                    clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
                    image_buffer = self.generate_raid_image(clan.name, data["raid"])
                    
                    file = discord.File(fp=image_buffer, filename="raid_summary.png")
                    
                    # Cria um Embed anexando a imagem desenhada
                    embed = discord.Embed(
                        title="🏕️ O Fim de Semana de Raide Chegou ao Fim!",
                        description="Confira o resumo financeiro do clã abaixo. Os parasitas que não atacaram já estão sendo listados no Painel Web.",
                        color=discord.Color.dark_theme()
                    )
                    embed.set_image(url="attachment://raid_summary.png")
                    
                    await channel.send(embed=embed, file=file)

            # Atualiza a memória do bot
            self.last_raid_state = current_state

        except Exception as e:
            logger.error(f"Erro no monitoramento autônomo da Raide: {e}")

    @auto_raid_summary.before_loop
    async def before_auto_raid(self):
        await self.bot.wait_until_ready()
        
        # Pega o status inicial para não disparar logo ao ligar
        try:
            data = await self.fetch_capital_data_for_web()
            if "error" not in data:
                self.last_raid_state = data["raid"]["state"]
        except Exception:
            pass

    # ========================================================
    # >>> COMANDO MANUAL <<<
    # ========================================================
    @app_commands.command(name="gerar_raide", description="Gera e envia a imagem com o resumo da Capital agora.")
    @app_commands.default_permissions(administrator=True)
    async def cmd_gerar_raide(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        data = await self.fetch_capital_data_for_web()
        if "error" in data:
            await interaction.followup.send(f"❌ {data['error']}")
            return

        clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
        image_buffer = self.generate_raid_image(clan.name, data["raid"])
        file = discord.File(fp=image_buffer, filename="raid_summary.png")
        
        embed = discord.Embed(
            title="🏕️ Resumo Atual da Raide (Solicitado Manualmente)",
            color=discord.Color.dark_theme()
        )
        embed.set_image(url="attachment://raid_summary.png")
        
        await interaction.followup.send(embed=embed, file=file)


async def setup(bot: commands.Bot):
    await bot.add_cog(CapitalCog(bot))
