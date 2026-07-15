# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import geniuslib as coc
from geniuslib.raid_analytics import (
    raid_summary, count_missed_raid_attacks, get_inactive_raid_members,
    member_raid_contribution, clan_offensive_stats, clan_defensive_stats,
    get_wasted_attacks, get_raid_cleanup_attacks, best_raid_attack,
    average_attack_destruction, total_member_destruction
)
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import os
import datetime
import pytz
from math import ceil

logger = logging.getLogger("capital_cog")

LEAGUE_COLORS = {
    "Bronze": (205, 127, 50),
    "Prata": (192, 192, 192),
    "Ouro": (255, 215, 0),
    "Master": (147, 112, 219),
    "Champion": (0, 255, 255),
    "Campeão": (0, 255, 255),
    "Titã": (255, 69, 0),
    "Lenda": (255, 20, 100),
}

class CapitalCog(commands.Cog, name="Monitoramento da Capital"):
    """Cog para gerenciar a Capital e Gerar Imagens de Resumo no estilo exato do ClashPerk/In-Game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_raid_state = None
        self.last_cwl_state = None
        self.font_path = "supercell_magic.ttf"

        self.assets = {
            "bg": "https://static.wikia.nocookie.net/clashofclans/images/2/23/Capital_Peak_Scenery.png",
            "medal": "https://static.wikia.nocookie.net/clashofclans/images/5/52/Raid_Medal.png",
            "trophy": "https://static.wikia.nocookie.net/clashofclans/images/0/05/Capital_Trophy.png",
            "xp": "https://static.wikia.nocookie.net/clashofclans/images/c/c9/XP.png",
            "star": "https://static.wikia.nocookie.net/clashofclans/images/8/8f/Star.png",
        }
        self.auto_raid_summary.start()

    async def cog_unload(self):
        self.auto_raid_summary.cancel()

    # ========================================================
    # >>> DOWNLOADER DE FONTE OFICIAL <<<
    # ========================================================
    async def _ensure_font_exists(self):
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

            total_attacks = getattr(raid, 'attack_count', 0)
            total_loot = getattr(raid, 'total_loot', 0)
            destroyed = getattr(raid, 'destroyed_district_count', 0)

            top_attackers = []
            detailed_members = []
            if hasattr(raid, 'members') and raid.members:
                members = []
                for m in raid.members:
                    member_data = {
                        "name": m.name,
                        "attacks": getattr(m, 'attack_count', 0),
                        "looted": getattr(m, 'capital_resources_looted', 0),
                        "contribution_pct": round(member_raid_contribution(m), 1),
                        "avg_destruction": round(average_attack_destruction(m), 1),
                        "total_destruction": round(total_member_destruction(m), 1),
                    }
                    best = best_raid_attack(m)
                    if best:
                        member_data["best_attack"] = {"stars": best.stars, "destruction": best.destruction, "target": getattr(best, 'target', '?')}
                    members.append(member_data)
                    if hasattr(m, 'attacks') and m.attacks:
                        attack_details = []
                        for atk in m.attacks:
                            attack_details.append({
                                "target": getattr(atk, 'target', '?'),
                                "destruction": getattr(atk, 'destruction', 0),
                                "stars": getattr(atk, 'stars', 0),
                                "duration": getattr(atk, 'duration', 0),
                            })
                        member_data["attack_details"] = attack_details
                    detailed_members.append(member_data)
                members.sort(key=lambda x: x["looted"], reverse=True)
                top_attackers = members[:3]

            # Dados de ataque log (quais clãs foram atacados)
            attack_log = []
            if hasattr(raid, 'attack_log') and raid.attack_log:
                for entry in raid.attack_log:
                    clan_data = {
                        "name": getattr(entry, 'name', '?'),
                        "tag": getattr(entry, 'tag', '?'),
                        "destroyed_districts": getattr(entry, 'destroyed_district_count', 0),
                        "total_districts": getattr(entry, 'district_count', 0),
                        "total_loot": getattr(entry, 'looted', 0),
                    }
                    attack_log.append(clan_data)

            # Dados de defesa
            defense_log = []
            if hasattr(raid, 'defense_log') and raid.defense_log:
                for entry in raid.defense_log:
                    defense_data = {
                        "attacker": getattr(entry, 'name', '?'),
                        "tag": getattr(entry, 'tag', '?'),
                        "attack_count": getattr(entry, 'attack_count', 0),
                        "destroyed_districts": getattr(entry, 'destroyed_district_count', 0),
                        "total_loot": getattr(entry, 'looted', 0),
                    }
                    defense_log.append(defense_data)

            # Estatísticas analíticas via raid_analytics
            summary = raid_summary(raid)
            off_stats = clan_offensive_stats(raid)
            def_stats = clan_defensive_stats(raid)
            missed = count_missed_raid_attacks(raid, self.bot.clan_tag)
            inactive = [m.name for m in get_inactive_raid_members(raid)]
            wasted = sum(1 for _ in get_wasted_attacks(raid, self.bot.clan_tag))
            cleanups = sum(1 for _ in get_raid_cleanup_attacks(raid, self.bot.clan_tag))

            return {
                "clan_name": clan.name, "clan_badge_url": clan.badge.url, "clan_level": clan.level,
                "date_range": date_range, "total_medals": total_medals,
                "total_trophies": getattr(clan, 'capital_points', 0),
                "clan_xp": getattr(raid, 'clan_xp_reward', 0),
                "league_name": league_name, "league_icon_url": league_icon_url,
                "state": getattr(raid, 'state', 'ended'),
                "total_attacks": total_attacks,
                "total_loot": total_loot,
                "destroyed_districts": destroyed,
                "top_attackers": top_attackers,
                "detailed_members": detailed_members,
                "attack_log": attack_log,
                "defense_log": defense_log,
                "analytics": {
                    "missed_attacks": missed,
                    "inactive_members": inactive,
                    "wasted_attacks": wasted,
                    "cleanup_attacks": cleanups,
                    "offensive_efficiency": off_stats["efficiency"],
                    "districts_destroyed": off_stats["districts_destroyed"],
                    "total_districts": off_stats["total_districts"],
                    "defensive_loot_lost": def_stats["total_loot_lost"],
                    "defensive_attacks": def_stats["attacks_received"],
                    "member_count": summary["members_raided"],
                    "top_attacker": summary["top_attacker"],
                    "top_attacker_loot": summary["top_attacker_loot"],
                },
            }
        except Exception as e:
            logger.error(f"Erro fetch_raid_data: {e}", exc_info=True)
            return {"error": "Erro ao processar dados."}

    async def fetch_cwl_data(self) -> Dict[str, Any]:
        """Busca dados da CWL para gerar imagem de resumo final."""
        try:
            group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not group:
                return {"error": "Nenhum grupo CWL ativo."}

            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)

            league_name = "Desconhecida"
            if clan.war_league:
                league_name = getattr(clan.war_league, 'name', 'Desconhecida')

            season = getattr(group, 'season', 'Desconhecida')
            group_state = getattr(group, 'state', 'ended')

            my_tag = coc.utils.correct_tag(self.bot.clan_tag)

            total_stars = 0
            total_attacks = 0
            total_destruction = 0.0
            wars_fought = 0
            member_stats = {}
            team_size = 15

            for round_tags in group.rounds:
                for war_tag in round_tags:
                    if war_tag == '#0': continue
                    try:
                        war = await self.bot.api_client.get_league_war(war_tag)
                        our_clan = war.clan if coc.utils.correct_tag(war.clan.tag) == my_tag else war.opponent
                        if our_clan:
                            if wars_fought == 0:
                                team_size = getattr(war, 'team_size', 15)
                            total_stars += getattr(our_clan, 'stars', 0)
                            total_destruction += getattr(our_clan, 'destruction_percentage', 0)
                            wars_fought += 1
                            for m in our_clan.members:
                                tag = m.tag
                                if tag not in member_stats:
                                    member_stats[tag] = {"name": m.name, "stars": 0, "attacks": 0}
                                member_stats[tag]["stars"] += getattr(m, 'stars', 0)
                                member_stats[tag]["attacks"] += len(getattr(m, 'attacks', []))
                                total_attacks += len(getattr(m, 'attacks', []))
                    except Exception as e:
                        logger.error(f"Erro ao buscar guerra CWL {war_tag}: {e}")
                        continue

            top_attackers = sorted(member_stats.values(), key=lambda x: x["stars"], reverse=True)[:3]
            avg_destruction = total_destruction / wars_fought if wars_fought > 0 else 0

            return {
                "clan_name": clan.name,
                "clan_badge_url": clan.badge.url,
                "clan_level": clan.level,
                "league_name": league_name,
                "season": season,
                "total_stars": total_stars,
                "total_attacks": total_attacks,
                "total_destruction": round(avg_destruction, 1),
                "wars_fought": wars_fought,
                "team_size": team_size,
                "member_count": len(member_stats),
                "top_attackers": top_attackers,
                "clan_xp": 0,
            }
        except coc.NotFound:
            return {"error": "CWL não ativa."}
        except Exception as e:
            logger.error(f"Erro fetch_cwl_data: {e}", exc_info=True)
            return {"error": "Erro ao processar dados CWL."}

    async def _fetch_image(self, session, url):
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    return Image.open(BytesIO(await resp.read())).convert("RGBA")
        except Exception:
            pass
        return None

    def _draw_text_outlined(self, draw, pos, text, font, fill_color, stroke_color=(0, 0, 0), stroke_width=3):
        x, y = pos
        for dx in range(-stroke_width, stroke_width + 1):
            for dy in range(-stroke_width, stroke_width + 1):
                if dx * dx + dy * dy <= stroke_width * stroke_width:
                    draw.text((x + dx, y + dy), text, font=font, fill=stroke_color)
        draw.text((x, y), text, font=font, fill=fill_color)

    def _draw_gradient_bg(self, draw, w, h, top_color, bottom_color):
        for y in range(h):
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * y / h)
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * y / h)
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * y / h)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

    def _draw_rounded_rect(self, draw, rect, radius, fill=None, outline=None, width=1):
        x1, y1, x2, y2 = rect
        if fill:
            draw.rounded_rectangle(rect, radius=radius, fill=fill)
        if outline:
            draw.rounded_rectangle(rect, radius=radius, outline=outline, width=width)

    def _get_font(self, size):
        try:
            return ImageFont.truetype(self.font_path, size)
        except Exception:
            try:
                return ImageFont.truetype("arialbd.ttf", size)
            except Exception:
                return ImageFont.load_default()

    # ========================================================
    # >>> GERADOR DE IMAGEM DA CAPITAL (MODERNO DARK) <<<
    # ========================================================
    def generate_game_style_image(self, data: Dict, images: Dict[str, Image.Image]) -> BytesIO:
        W, H = 1000, 680
        base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)

        f_huge = self._get_font(52)
        f_big = self._get_font(40)
        f_title = self._get_font(34)
        f_sub = self._get_font(24)
        f_small = self._get_font(20)
        f_tiny = self._get_font(16)

        # Gradiente escuro
        self._draw_gradient_bg(draw, W, H, (10, 12, 20), (22, 26, 38))

        # Linha decorativa neon no topo
        for i in range(3):
            glow_r = int(120 + (255 - 120) * (1 - i / 3))
            draw.line([(0, i), (W, i)], fill=(glow_r, 180, 255, 120 - i * 30), width=3 - i)

        # --- CABEÇALHO ---
        clan_name = data.get('clan_name', 'Clã')
        level = data.get('clan_level', 0)
        date_range = data.get('date_range', '')

        badge = images.get('badge')
        if badge:
            badge = badge.resize((80, 80), Image.LANCZOS)
            base.paste(badge, (30, 35), badge)
            # Brilho sutil no badge
            for r in range(12, 18):
                glow = Image.new('RGBA', (80, 80), (0, 0, 0, 0))
                dg = ImageDraw.Draw(glow)
                dg.ellipse([-r, -r, 80 + r, 80 + r], fill=(255, 215, 0, 12))
                base.paste(glow, (30 - r, 35 - r), glow)

        self._draw_text_outlined(draw, (125, 35), f"{clan_name}", f_title, (255, 255, 255), stroke_width=3)
        self._draw_text_outlined(draw, (125, 75), f"Nível {level}", f_small, (200, 200, 200), stroke_width=2)

        # Liga no canto superior direito
        league_icon = images.get('league')
        if league_icon:
            li = league_icon.resize((70, 70), Image.LANCZOS)
            base.paste(li, (W - 100, 30), li)
        l_name = data.get('league_name', '')
        lw = draw.textlength("Resultados da Capital", font=f_sub)
        self._draw_text_outlined(draw, (W - lw - 100, 35), "Resultados da Capital", f_sub, (255, 215, 0), stroke_width=3)
        dw = draw.textlength(date_range, font=f_small)
        self._draw_text_outlined(draw, (W - dw - 100, 68), date_range, f_small, (180, 180, 180), stroke_width=2)

        # --- BANNER DE MEDALHAS ---
        pill_y = 150
        pill_h = 85
        overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d_overlay = ImageDraw.Draw(overlay)
        d_overlay.rounded_rectangle([80, pill_y, W - 80, pill_y + pill_h], radius=42, fill=(20, 24, 38, 220))
        d_overlay.rounded_rectangle([80, pill_y, W - 80, pill_y + pill_h], radius=42, outline=(255, 215, 0, 60), width=2)
        base = Image.alpha_composite(base, overlay)
        draw = ImageDraw.Draw(base)

        medal = images.get('medal') or images.get('trophy')
        if medal:
            mi = medal.resize((70, 70), Image.LANCZOS)
            base.paste(mi, (100, pill_y + 7), mi)

        self._draw_text_outlined(draw, (180, pill_y + 10), "RECOMPENSA DA RAIDE", f_sub, (255, 215, 0), stroke_width=2)
        val_txt = f"+{data['total_medals']}" if data['total_medals'] > 0 else "0"
        vw = draw.textlength(val_txt, font=f_huge)
        self._draw_text_outlined(draw, (180, pill_y + 35), val_txt, f_huge, (255, 255, 255), stroke_width=4)

        # --- STATS GRID ---
        stats = [
            ("TROFÉUS", f"{data['total_trophies']:,}", images.get('trophy'), (255, 215, 0)),
            ("ATAQUES", str(data.get('total_attacks', 0)), images.get('medal'), (100, 200, 255)),
            ("DISTRITOS", str(data.get('destroyed_districts', 0)), images.get('star'), (255, 100, 100)),
            ("SAQUETOTAL", f"{data.get('total_loot', 0):,}", images.get('medal'), (100, 255, 150)),
        ]

        card_w = 200
        card_h = 120
        gap = 15
        total_w = 4 * card_w + 3 * gap
        start_x = (W - total_w) // 2
        card_y = pill_y + pill_h + 25

        for i, (label, value, icon, accent) in enumerate(stats):
            cx = start_x + i * (card_w + gap)
            cy = card_y
            # Card BG
            card_overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card_overlay)
            cd.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=12, fill=(30, 34, 50, 200))
            cd.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=12, outline=(accent[0], accent[1], accent[2], 60), width=1)
            base = Image.alpha_composite(base, card_overlay)
            draw = ImageDraw.Draw(base)

            # Icon
            if icon:
                ic = icon.resize((32, 32), Image.LANCZOS)
                base.paste(ic, (cx + (card_w - 32) // 2, cy + 10), ic)

            # Value
            vw = draw.textlength(value, font=f_big)
            self._draw_text_outlined(draw, (cx + (card_w - vw) // 2, cy + 42), value, f_big, (255, 255, 255), stroke_width=3)
            # Label
            lw = draw.textlength(label, font=f_tiny)
            draw.text((cx + (card_w - lw) // 2, cy + card_h - 25), label, font=f_tiny, fill=accent)

        # --- TOP ATACANTES ---
        attackers = data.get('top_attackers', [])
        atk_y = card_y + card_h + 25
        atk_h = 150

        overlay2 = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(overlay2)
        d2.rounded_rectangle([60, atk_y, W - 60, atk_y + atk_h], radius=16, fill=(20, 24, 40, 200))
        d2.rounded_rectangle([60, atk_y, W - 60, atk_y + atk_h], radius=16, outline=(255, 215, 0, 40), width=1)
        base = Image.alpha_composite(base, overlay2)
        draw = ImageDraw.Draw(base)

        self._draw_text_outlined(draw, (80, atk_y + 12), "TOP ATACANTES", f_sub, (255, 215, 0), stroke_width=2)

        medals_emoji = ["🥇", "🥈", "🥉"]
        if attackers:
            for rank, a in enumerate(attackers[:3]):
                ay = atk_y + 42 + rank * 34
                self._draw_text_outlined(draw, (85, ay), f"{medals_emoji[rank]}  {a['name']}", f_small, (255, 255, 255), stroke_width=2)
                atk_txt = f"{a['attacks']} ataques"
                atkw = draw.textlength(atk_txt, font=f_small)
                self._draw_text_outlined(draw, (W - 300, ay), atk_txt, f_small, (150, 200, 255), stroke_width=2)
                loot_txt = f"{a['looted']:,} de ouro"
                lootw = draw.textlength(loot_txt, font=f_small)
                self._draw_text_outlined(draw, (W - 120, ay), loot_txt, f_small, (255, 215, 0), stroke_width=2)
        else:
            self._draw_text_outlined(draw, (W // 2 - 100, atk_y + 70), "Nenhum atacante disponível", f_small, (150, 150, 150), stroke_width=2)

        # --- FOOTER ---
        footer_y = H - 45
        draw.line([(40, footer_y - 5), (W - 40, footer_y - 5)], fill=(255, 255, 255, 30), width=1)

        xp_val = data.get('clan_xp', 0)
        xp_icon = images.get('xp')
        if xp_icon:
            xi = xp_icon.resize((28, 28), Image.LANCZOS)
            base.paste(xi, (50, footer_y - 10), xi)
        self._draw_text_outlined(draw, (85, footer_y - 7), f"XP do Clã: +{xp_val}", f_small, (200, 200, 200), stroke_width=2)

        self._draw_text_outlined(draw, (W // 2 - 80, footer_y - 7), "Raide Semanal", f_small, (150, 150, 150), stroke_width=2)

        league_txt = data.get('league_name', '')
        self._draw_text_outlined(draw, (W - 250, footer_y - 7), league_txt, f_small, (255, 215, 0), stroke_width=2)

        buffer = BytesIO()
        base.convert("RGB").save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

    # ========================================================
    # >>> GERADOR DE IMAGEM CWL (MODERNO DARK) <<<
    # ========================================================
    def generate_cwl_report_image(self, data: Dict, images: Dict[str, Image.Image]) -> BytesIO:
        W, H = 1000, 680
        base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)

        f_huge = self._get_font(52)
        f_big = self._get_font(40)
        f_title = self._get_font(34)
        f_sub = self._get_font(24)
        f_small = self._get_font(20)
        f_tiny = self._get_font(16)

        # Gradiente escuro com tom azulado
        self._draw_gradient_bg(draw, W, H, (8, 10, 30), (20, 24, 45))

        # Linha decorativa neon azul
        for i in range(3):
            glow_r = int(80 + (180 - 80) * (1 - i / 3))
            draw.line([(0, i), (W, i)], fill=(glow_r, 160, 255, 120 - i * 30), width=3 - i)

        # --- CABEÇALHO ---
        clan_name = data.get('clan_name', 'Clã')
        level = data.get('clan_level', 0)
        league_name = data.get('league_name', '')
        season = data.get('season', '')

        badge = images.get('badge')
        if badge:
            badge = badge.resize((80, 80), Image.LANCZOS)
            base.paste(badge, (30, 35), badge)
            for r in range(12, 18):
                glow = Image.new('RGBA', (80, 80), (0, 0, 0, 0))
                dg = ImageDraw.Draw(glow)
                dg.ellipse([-r, -r, 80 + r, 80 + r], fill=(100, 180, 255, 12))
                base.paste(glow, (30 - r, 35 - r), glow)

        self._draw_text_outlined(draw, (125, 35), f"{clan_name}", f_title, (255, 255, 255), stroke_width=3)
        self._draw_text_outlined(draw, (125, 75), f"Nível {level}", f_small, (200, 200, 200), stroke_width=2)

        # Liga no canto
        league_icon = images.get('league')
        if league_icon:
            li = league_icon.resize((70, 70), Image.LANCZOS)
            base.paste(li, (W - 100, 30), li)

        lw = draw.textlength("Guerras de Clãs", font=f_sub)
        self._draw_text_outlined(draw, (W - lw - 100, 35), "Guerras de Clãs", f_sub, (100, 200, 255), stroke_width=3)
        sw = draw.textlength(season, font=f_small)
        self._draw_text_outlined(draw, (W - sw - 100, 68), season, f_small, (180, 180, 180), stroke_width=2)

        # --- BANNER PRINCIPAL ---
        pill_y = 150
        pill_h = 85
        overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d_overlay = ImageDraw.Draw(overlay)
        d_overlay.rounded_rectangle([80, pill_y, W - 80, pill_y + pill_h], radius=42, fill=(20, 24, 45, 220))
        d_overlay.rounded_rectangle([80, pill_y, W - 80, pill_y + pill_h], radius=42, outline=(100, 180, 255, 60), width=2)
        base = Image.alpha_composite(base, overlay)
        draw = ImageDraw.Draw(base)

        star_img = images.get('star')
        if star_img:
            si = star_img.resize((65, 65), Image.LANCZOS)
            base.paste(si, (100, pill_y + 10), si)

        self._draw_text_outlined(draw, (180, pill_y + 10), "RESULTADO DA TEMPORADA", f_sub, (100, 200, 255), stroke_width=2)
        val_txt = f"{data['total_stars']} ⭐"
        vw = draw.textlength(val_txt, font=f_huge)
        self._draw_text_outlined(draw, (180, pill_y + 32), val_txt, f_huge, (255, 255, 255), stroke_width=4)

        wars_txt = f"{data.get('wars_fought', 0)} guerras"
        tw = draw.textlength(wars_txt, font=f_small)
        self._draw_text_outlined(draw, (180 + vw + 20, pill_y + 42), wars_txt, f_small, (150, 150, 150), stroke_width=2)

        # --- STATS GRID ---
        stats = [
            ("ESTRELAS", f"{data['total_stars']}", star_img or images.get('trophy'), (255, 215, 0)),
            ("ATAQUES", str(data.get('total_attacks', 0)), images.get('medal'), (100, 200, 255)),
            ("MEMBROS", str(data.get('member_count', 0)), images.get('badge'), (255, 100, 100)),
            ("DESTRUIÇÃO", f"{data.get('total_destruction', 0)}%", images.get('trophy'), (100, 255, 150)),
        ]

        card_w = 200
        card_h = 120
        gap = 15
        total_w = 4 * card_w + 3 * gap
        start_x = (W - total_w) // 2
        card_y = pill_y + pill_h + 25

        for i, (label, value, icon, accent) in enumerate(stats):
            cx = start_x + i * (card_w + gap)
            cy = card_y
            card_overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card_overlay)
            cd.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=12, fill=(25, 28, 50, 200))
            cd.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=12, outline=(accent[0], accent[1], accent[2], 60), width=1)
            base = Image.alpha_composite(base, card_overlay)
            draw = ImageDraw.Draw(base)

            if icon:
                ic = icon.resize((32, 32), Image.LANCZOS)
                base.paste(ic, (cx + (card_w - 32) // 2, cy + 10), ic)

            vw = draw.textlength(value, font=f_big)
            self._draw_text_outlined(draw, (cx + (card_w - vw) // 2, cy + 42), value, f_big, (255, 255, 255), stroke_width=3)
            lw = draw.textlength(label, font=f_tiny)
            draw.text((cx + (card_w - lw) // 2, cy + card_h - 25), label, font=f_tiny, fill=accent)

        # --- TOP ATACANTES ---
        attackers = data.get('top_attackers', [])
        atk_y = card_y + card_h + 25
        atk_h = 150

        overlay2 = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(overlay2)
        d2.rounded_rectangle([60, atk_y, W - 60, atk_y + atk_h], radius=16, fill=(20, 24, 45, 200))
        d2.rounded_rectangle([60, atk_y, W - 60, atk_y + atk_h], radius=16, outline=(100, 180, 255, 40), width=1)
        base = Image.alpha_composite(base, overlay2)
        draw = ImageDraw.Draw(base)

        self._draw_text_outlined(draw, (80, atk_y + 12), "TOP ATACANTES", f_sub, (100, 200, 255), stroke_width=2)

        medals_emoji = ["🥇", "🥈", "🥉"]
        if attackers:
            for rank, a in enumerate(attackers[:3]):
                ay = atk_y + 42 + rank * 34
                self._draw_text_outlined(draw, (85, ay), f"{medals_emoji[rank]}  {a['name']}", f_small, (255, 255, 255), stroke_width=2)
                atk_txt = f"{a['attacks']} ataques"
                self._draw_text_outlined(draw, (W - 300, ay), atk_txt, f_small, (150, 200, 255), stroke_width=2)
                star_txt = f"{a['stars']} ⭐"
                self._draw_text_outlined(draw, (W - 120, ay), star_txt, f_small, (255, 215, 0), stroke_width=2)
        else:
            self._draw_text_outlined(draw, (W // 2 - 100, atk_y + 70), "Nenhum atacante disponível", f_small, (150, 150, 150), stroke_width=2)

        # --- FOOTER ---
        footer_y = H - 45
        draw.line([(40, footer_y - 5), (W - 40, footer_y - 5)], fill=(255, 255, 255, 30), width=1)
        self._draw_text_outlined(draw, (W // 2 - 100, footer_y - 7), "Temporada Finalizada", f_small, (150, 150, 150), stroke_width=2)
        self._draw_text_outlined(draw, (W - 250, footer_y - 7), league_name, f_small, (100, 200, 255), stroke_width=2)

        buffer = BytesIO()
        base.convert("RGB").save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

    # ========================================================
    # >>> PROCESSAMENTO E ENVIO <<<
    # ========================================================
    async def _process_and_send_raid(self, interaction: Optional[discord.Interaction] = None, automated: bool = False):
        if automated and (self.bot.maintenance_mode or not getattr(self.bot, 'capital_report_channel_id', None)):
            return

        channel = None
        if automated:
            channel_id = self.bot.capital_report_channel_id
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if not channel:
                return

        await self._ensure_font_exists()

        data = await self.fetch_raid_data()
        if "error" in data:
            if interaction:
                await interaction.followup.send(f"\u274c {data['error']}")
            return

        async with aiohttp.ClientSession() as session:
            tasks_list = [
                self._fetch_image(session, self.assets['bg']),
                self._fetch_image(session, self.assets['medal']),
                self._fetch_image(session, self.assets['trophy']),
                self._fetch_image(session, self.assets['xp']),
                self._fetch_image(session, self.assets['star']),
                self._fetch_image(session, data['clan_badge_url']),
                self._fetch_image(session, data['league_icon_url']),
            ]
            res = await asyncio.gather(*tasks_list)
            image_assets = {
                'bg': res[0], 'medal': res[1], 'trophy': res[2],
                'xp': res[3], 'star': res[4], 'badge': res[5], 'league': res[6],
            }

        image_buffer = await asyncio.to_thread(self.generate_game_style_image, data, image_assets)

        file = discord.File(fp=image_buffer, filename="raid_summary.png")
        embed = discord.Embed(color=discord.Color(0x0A0C14))
        embed.set_image(url="attachment://raid_summary.png")

        if interaction:
            await interaction.followup.send(file=file, embed=embed)
        elif channel:
            await channel.send(
                content="\U0001f3d5\ufe0f **Resultados do Fim de Semana da Capital!**",
                file=file, embed=embed
            )

    async def _process_and_send_cwl(self, automated: bool = False):
        if automated and (self.bot.maintenance_mode or not getattr(self.bot, 'capital_report_channel_id', None)):
            return

        channel_id = self.bot.capital_report_channel_id
        channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
        if not channel:
            return

        await self._ensure_font_exists()

        data = await self.fetch_cwl_data()
        if "error" in data:
            logger.warning(f"CWL report not sent: {data['error']}")
            return

        async with aiohttp.ClientSession() as session:
            tasks_list = [
                self._fetch_image(session, self.assets['medal']),
                self._fetch_image(session, self.assets['trophy']),
                self._fetch_image(session, self.assets['xp']),
                self._fetch_image(session, self.assets['star']),
                self._fetch_image(session, data['clan_badge_url']),
            ]
            league_icon_url = None
            try:
                clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
                if clan.war_league and hasattr(clan.war_league, 'icon') and clan.war_league.icon:
                    league_icon_url = clan.war_league.icon.url
            except Exception:
                pass

            tasks_list.append(self._fetch_image(session, league_icon_url or self.assets['trophy']))

            res = await asyncio.gather(*tasks_list)
            image_assets = {
                'medal': res[0], 'trophy': res[1],
                'xp': res[2], 'star': res[3], 'badge': res[4], 'league': res[5],
            }

        image_buffer = await asyncio.to_thread(self.generate_cwl_report_image, data, image_assets)

        file = discord.File(fp=image_buffer, filename="cwl_summary.png")
        embed = discord.Embed(color=discord.Color(0x0A0C14))
        embed.set_image(url="attachment://cwl_summary.png")

        await channel.send(
            content="\U0001f3c6 **Resultado da Temporada de Guerras de Clãs!**",
            file=file, embed=embed
        )

    # ========================================================
    # >>> TAREFAS AUTOMÁTICAS <<<
    # ========================================================
    @tasks.loop(minutes=30)
    async def auto_raid_summary(self):
        try:
            data = await self.fetch_raid_data()
            if "error" in data:
                return
            current_state = data.get("state", "ended")
            if self.last_raid_state == "ongoing" and current_state == "ended":
                await self._process_and_send_raid(automated=True)
            self.last_raid_state = current_state
        except Exception as e:
            logger.error(f"Erro no auto_raid_summary: {e}")

    @auto_raid_summary.before_loop
    async def before_auto_raid(self):
        await self.bot.wait_until_ready()
        try:
            data = await self.fetch_raid_data()
            if "error" not in data:
                self.last_raid_state = data.get("state", "ended")
        except Exception:
            pass

    async def check_cwl_end(self):
        """Verifica se a CWL terminou e envia o resumo."""
        try:
            current_state = None
            try:
                group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
                current_state = getattr(group, 'state', 'ended')
            except coc.NotFound:
                current_state = 'notInWar'

            if self.last_cwl_state == 'inWar' and current_state in ('ended', 'notInWar', None):
                logger.info("CWL ended! Generating report image...")
                await self._process_and_send_cwl(automated=True)

            self.last_cwl_state = current_state
        except Exception as e:
            logger.error(f"Erro check_cwl_end: {e}")

    # ========================================================
    # >>> COMANDOS SLASH <<<
    # ========================================================
    @app_commands.command(name="gerar_raide", description="Gera a imagem do resumo da Capital.")
    @app_commands.default_permissions(administrator=True)
    async def cmd_gerar_raide(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._process_and_send_raid(interaction=interaction, automated=False)

    @app_commands.command(name="gerar_cwl", description="Gera a imagem do resumo da CWL.")
    @app_commands.default_permissions(administrator=True)
    async def cmd_gerar_cwl(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._process_and_send_cwl(automated=False)
        await interaction.followup.send("\u2705 Imagem da CWL gerada e enviada ao canal de relatórios!")


async def setup(bot: commands.Bot):
    await bot.add_cog(CapitalCog(bot))
