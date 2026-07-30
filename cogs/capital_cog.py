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
            "bg": "https://static.wikia.nocookie.net/clashofclans/images/e/ea/DMap_Capital_Peak.jpg/revision/latest?cb=20220505204357",
            "medal": "https://static.wikia.nocookie.net/clashofclans/images/5/52/Raid_Medal.png",
            "trophy": "https://static.wikia.nocookie.net/clashofclans/images/0/05/Capital_Trophy.png",
            "xp": "https://static.wikia.nocookie.net/clashofclans/images/c/c9/XP.png",
            "star": "https://static.wikia.nocookie.net/clashofclans/images/8/8f/Star.png",
            "cwl_bg": "https://static.wikia.nocookie.net/clashofclans/images/1/19/Scenery_War_Arena.png/revision/latest?cb=20230612110722",
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
        W, H = 1100, 800
        base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)

        f_huge = self._get_font(58)
        f_big = self._get_font(38)
        f_title = self._get_font(32)
        f_sub = self._get_font(24)
        f_small = self._get_font(18)
        f_tiny = self._get_font(14)

        league_color = self._get_league_color(data.get('league_name', ''))

        # --- BACKGROUND: Capital Peak Scenery com vinheta escura ---
        bg_img = images.get('bg')
        if bg_img:
            bg_img = bg_img.resize((W, H), Image.LANCZOS)
            if bg_img.mode != 'RGBA':
                bg_img = bg_img.convert('RGBA')
            base.paste(bg_img, (0, 0), bg_img)
            overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            dov = ImageDraw.Draw(overlay)
            dov.rectangle([0, 0, W, H], fill=(0, 0, 0, 210))
            dov.ellipse([-W//4, -H//6, W+W//4, H+H//6], fill=(0, 0, 0, 60))
            base = Image.alpha_composite(base, overlay)
        else:
            self._draw_gradient_bg(draw, W, H, (8, 8, 18), (16, 18, 32))

        draw = ImageDraw.Draw(base)
        self._draw_diagonal_accents(draw, W, H, league_color)

        # --- HEADER ---
        header_h = 110
        header = Image.new('RGBA', (W, header_h), (0, 0, 0, 0))
        dh = ImageDraw.Draw(header)
        dh.rounded_rectangle([0, 0, W, header_h], radius=0, fill=(10, 10, 24, 200))
        base.paste(header, (0, 0), header)
        draw = ImageDraw.Draw(base)

        badge = images.get('badge')
        if badge:
            badge = badge.resize((70, 70), Image.LANCZOS)
            base.paste(badge, (32, 20), badge)

        clan_name = data.get('clan_name', 'Clã')
        level = data.get('clan_level', 0)
        self._draw_text_outlined(draw, (118, 22), clan_name, f_title, (255, 255, 255), stroke_width=3)
        self._draw_text_outlined(draw, (118, 62), f"Nível {level}", f_small, (180, 180, 195), stroke_width=2)

        league_icon = images.get('league')
        if league_icon:
            li = league_icon.resize((56, 56), Image.LANCZOS)
            base.paste(li, (W - 88, 27), li)

        date_range = data.get('date_range', '')
        drw = draw.textlength(date_range, font=f_small)
        draw.text((W - drw - 28, 78), date_range, font=f_small, fill=(140, 140, 160))

        section_label = "RESULTADOS DO FIM DE SEMANA"
        slw = draw.textlength(section_label, font=f_sub)
        draw.text((W - slw - 28, 34), section_label, font=f_sub, fill=(255, 215, 0))

        # --- HERO MEDAL BANNER ---
        hero_y = 140
        hero_h = 110
        hero = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dh = ImageDraw.Draw(hero)

        accent_color = league_color if league_color != (255, 215, 0) else (255, 215, 0)
        dh.rounded_rectangle([40, hero_y, W - 40, hero_y + hero_h], radius=18, fill=(18, 18, 36, 230))
        dh.rounded_rectangle([40, hero_y, W - 40, hero_y + hero_h], radius=18,
                             outline=(accent_color[0], accent_color[1], accent_color[2], 80), width=2)

        glow_grad = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dg = ImageDraw.Draw(glow_grad)
        for x in range(0, W, 2):
            a = max(0, int(40 - 40 * abs(x - W // 2) / (W // 2)))
            dg.line([(x, hero_y), (x, hero_y + hero_h)], fill=(accent_color[0], accent_color[1], accent_color[2], a))
        hero = Image.alpha_composite(hero, glow_grad)
        base = Image.alpha_composite(base, hero)
        draw = ImageDraw.Draw(base)

        medal = images.get('medal') or images.get('trophy')
        if medal:
            mi = medal.resize((80, 80), Image.LANCZOS)
            base.paste(mi, (58, hero_y + 15), mi)

        total_medals = data.get('total_medals', 0)
        val_txt = f"+{total_medals:,}" if total_medals > 0 else "0"
        self._draw_text_outlined(draw, (155, hero_y + 12), "MEDALHAS DE RAIDE", f_sub, accent_color, stroke_width=2)
        self._draw_text_outlined(draw, (155, hero_y + 42), val_txt, f_huge, (255, 255, 255), stroke_width=5)

        # efficiency badge on right side of hero
        an = data.get('analytics', {})
        eff = an.get('offensive_efficiency', 0)
        eff_label = f"{eff:.1f}% eficiência"
        elw = draw.textlength(eff_label, font=f_small)
        self._draw_text_outlined(draw, (W - elw - 60, hero_y + 18), eff_label, f_small, (100, 255, 180), stroke_width=2)

        members_raided = an.get('member_count', 0)
        atk_count = data.get('total_attacks', 0)
        detail_line = f"{members_raided} participantes  •  {atk_count} ataques"
        dlw = draw.textlength(detail_line, font=f_small)
        self._draw_text_outlined(draw, (W - dlw - 60, hero_y + 50), detail_line, f_small, (180, 180, 195), stroke_width=2)

        # --- STATS CARDS ---
        stats = [
            ("TROFÉUS DA CAPITAL", f"{data.get('total_trophies', 0):,}", images.get('trophy'), (255, 215, 0)),
            ("OURO SAQUEADO", f"{data.get('total_loot', 0):,}", images.get('medal'), (255, 180, 50)),
            ("DISTRITOS", str(data.get('destroyed_districts', 0)), images.get('star'), (255, 80, 80)),
            ("ATAQUES", str(atk_count), images.get('medal'), (80, 180, 255)),
        ]

        card_w = 235
        card_h = 105
        gap = 20
        total_w = 4 * card_w + 3 * gap
        start_x = (W - total_w) // 2
        card_y = hero_y + hero_h + 28

        for i, (label, value, icon, accent) in enumerate(stats):
            cx = start_x + i * (card_w + gap)
            cy = card_y
            card = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card)
            cd.rounded_rectangle([0, 0, card_w, card_h], radius=14, fill=(14, 14, 30, 230))
            cd.rounded_rectangle([0, 0, card_w, card_h], radius=14,
                                 outline=(accent[0], accent[1], accent[2], 50), width=1)
            # accent top bar
            cd.rounded_rectangle([0, 0, card_w, 4], radius=2, fill=accent)
            base.paste(card, (cx, cy), card)
            draw = ImageDraw.Draw(base)

            if icon:
                ic = icon.resize((28, 28), Image.LANCZOS)
                base.paste(ic, (cx + 16, cy + 14), ic)

            vw = draw.textlength(value, font=f_big)
            self._draw_text_outlined(draw, (cx + card_w - vw - 16, cy + 14), value, f_big, (255, 255, 255), stroke_width=3)
            lw = draw.textlength(label, font=f_tiny)
            draw.text((cx + 16, cy + card_h - 26), label, font=f_tiny, fill=accent)

        # --- ANALYTICS SECTION ---
        an_y = card_y + card_h + 28
        an = data.get('analytics', {})

        panel = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dp = ImageDraw.Draw(panel)
        dp.rounded_rectangle([40, an_y, 530, an_y + 130], radius=14, fill=(14, 14, 30, 230))
        dp.rounded_rectangle([40, an_y, 530, an_y + 130], radius=14, outline=(255, 255, 255, 20), width=1)
        base = Image.alpha_composite(base, panel)
        draw = ImageDraw.Draw(base)

        self._draw_text_outlined(draw, (58, an_y + 14), "ANÁLISE DE DESEMPENHO", f_sub, (255, 215, 0), stroke_width=2)

        ana_items = [
            (f"⚔️  {an.get('districts_destroyed', 0)}/{an.get('total_districts', 0)} distritos destruídos", (255, 180, 80)),
            (f"🛡️  {an.get('defensive_attacks', 0)} ataques recebidos  •  {an.get('defensive_loot_lost', 0):,} ouro perdido", (255, 120, 120)),
            (f"💀  {an.get('missed_attacks', 0)} ataques perdidos  •  {len(an.get('inactive_members', []))} inativos", (255, 100, 100)),
            (f"♻️  {an.get('wasted_attacks', 0)} desperdiçados  •  {an.get('cleanup_attacks', 0)} cleanups", (180, 180, 255)),
        ]
        for j, (txt, color) in enumerate(ana_items):
            ty = an_y + 46 + j * 20
            draw.text((58, ty), txt, font=f_tiny, fill=color)

        # --- TOP ATTACKERS ---
        atk_panel_x = 560
        attackers = data.get('top_attackers', [])
        dp.rounded_rectangle([atk_panel_x, an_y, W - 40, an_y + 130], radius=14, fill=(14, 14, 30, 230))
        dp.rounded_rectangle([atk_panel_x, an_y, W - 40, an_y + 130], radius=14, outline=(255, 215, 0, 30), width=1)

        self._draw_text_outlined(draw, (atk_panel_x + 18, an_y + 14), "TOP ATACANTES", f_sub, (255, 215, 0), stroke_width=2)

        medals_emoji = ["🥇", "🥈", "🥉"]
        if attackers:
            for rank, a in enumerate(attackers[:3]):
                ay = an_y + 46 + rank * 28
                self._draw_text_outlined(draw, (atk_panel_x + 18, ay), f"{medals_emoji[rank]}  {a['name']}", f_small, (255, 255, 255), stroke_width=2)
                loot_txt = f"{a['looted']:,} ouro  •  {a['attacks']} atqs"
                ltw = draw.textlength(loot_txt, font=f_tiny)
                draw.text((W - ltw - 58, ay + 2), loot_txt, font=f_tiny, fill=(255, 215, 0))
        else:
            draw.text((atk_panel_x + 40, an_y + 70), "Nenhum atacante", font=f_small, fill=(150, 150, 160))

        # --- ATTACK LOG ---
        attack_log = data.get('attack_log', [])
        log_y = an_y + 145
        log = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dl = ImageDraw.Draw(log)
        dl.rounded_rectangle([40, log_y, W - 40, log_y + 80], radius=14, fill=(14, 14, 30, 230))
        dl.rounded_rectangle([40, log_y, W - 40, log_y + 80], radius=14, outline=(255, 255, 255, 20), width=1)
        base = Image.alpha_composite(base, log)
        draw = ImageDraw.Draw(base)

        self._draw_text_outlined(draw, (58, log_y + 12), "CLÃS ATACADOS", f_sub, (80, 180, 255), stroke_width=2)

        if attack_log:
            clans_txt = "  ⚔️  ".join([f"{c['name']} ({c['destroyed_districts']}/{c['total_districts']} distritos)" for c in attack_log[:4]])
            draw.text((58, log_y + 46), clans_txt, font=f_tiny, fill=(180, 180, 200))
        else:
            draw.text((58, log_y + 46), "Nenhum ataque registrado", font=f_tiny, fill=(150, 150, 160))

        # --- DEFENSE LOG ---
        defense_log = data.get('defense_log', [])
        def_y = log_y + 95
        defe = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        ddef = ImageDraw.Draw(defe)
        ddef.rounded_rectangle([40, def_y, W - 40, def_y + 80], radius=14, fill=(14, 14, 30, 230))
        ddef.rounded_rectangle([40, def_y, W - 40, def_y + 80], radius=14, outline=(255, 255, 255, 20), width=1)
        base = Image.alpha_composite(base, defe)
        draw = ImageDraw.Draw(base)

        self._draw_text_outlined(draw, (58, def_y + 12), "DEFESAS", f_sub, (255, 120, 120), stroke_width=2)

        if defense_log:
            def_txt = "  🛡️  ".join([f"{d['attacker']} ({d['destroyed_districts']} distritos, {d['total_loot']:,} ouro)" for d in defense_log[:3]])
            draw.text((58, def_y + 46), def_txt, font=f_tiny, fill=(180, 180, 200))
        else:
            draw.text((58, def_y + 46), "Nenhuma defesa registrada", font=f_tiny, fill=(150, 150, 160))

        # --- FOOTER ---
        footer_y = H - 38
        draw.line([(40, footer_y - 6), (W - 40, footer_y - 6)], fill=(255, 255, 255, 16), width=1)

        xp_val = data.get('clan_xp', 0)
        xp_icon = images.get('xp')
        if xp_icon:
            xi = xp_icon.resize((22, 22), Image.LANCZOS)
            base.paste(xi, (50, footer_y - 10), xi)
        draw.text((80, footer_y - 8), f"XP do Clã: +{xp_val}", font=f_tiny, fill=(180, 180, 195))

        week_year = data.get('date_range', '')
        draw.text((W // 2 - 80, footer_y - 8), "Raide Semanal", font=f_tiny, fill=(140, 140, 160))

        league_txt = data.get('league_name', '')
        ltw = draw.textlength(league_txt, font=f_tiny)
        draw.text((W - ltw - 50, footer_y - 8), league_txt, font=f_tiny, fill=accent_color)

        buffer = BytesIO()
        base.convert("RGB").save(buffer, format="PNG", quality=95)
        buffer.seek(0)
        return buffer

    def _get_league_color(self, league_name: str):
        for key, color in LEAGUE_COLORS.items():
            if key.lower() in league_name.lower():
                return color
        return (255, 215, 0)

    def _draw_diagonal_accents(self, draw, w, h, accent_color):
        for i in range(0, w + h, 60):
            a = max(0, 30 - 30 * abs(i - (w + h) // 2) / ((w + h) // 2))
            draw.line([(i, 0), (i - h, h)], fill=(accent_color[0], accent_color[1], accent_color[2], int(a)), width=1)

    # ========================================================
    # >>> GERADOR DE IMAGEM CWL (MODERNO DARK) <<<
    # ========================================================
    def generate_cwl_report_image(self, data: Dict, images: Dict[str, Image.Image]) -> BytesIO:
        W, H = 1100, 800
        base = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(base)

        f_huge = self._get_font(58)
        f_big = self._get_font(38)
        f_title = self._get_font(32)
        f_sub = self._get_font(24)
        f_small = self._get_font(18)
        f_tiny = self._get_font(14)

        cwl_accent = (80, 200, 255)

        # --- BACKGROUND: War Arena Scenery com vinheta escura ---
        cwl_bg = images.get('cwl_bg')
        if cwl_bg:
            cwl_bg = cwl_bg.resize((W, H), Image.LANCZOS)
            if cwl_bg.mode != 'RGBA':
                cwl_bg = cwl_bg.convert('RGBA')
            base.paste(cwl_bg, (0, 0), cwl_bg)
            overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
            dov = ImageDraw.Draw(overlay)
            dov.rectangle([0, 0, W, H], fill=(0, 0, 0, 210))
            dov.ellipse([-W//4, -H//6, W+W//4, H+H//6], fill=(0, 0, 0, 60))
            base = Image.alpha_composite(base, overlay)
        else:
            self._draw_gradient_bg(draw, W, H, (6, 8, 28), (14, 16, 40))

        draw = ImageDraw.Draw(base)
        self._draw_diagonal_accents(draw, W, H, cwl_accent)

        # --- HEADER ---
        header_h = 110
        header = Image.new('RGBA', (W, header_h), (0, 0, 0, 0))
        dh = ImageDraw.Draw(header)
        dh.rounded_rectangle([0, 0, W, header_h], radius=0, fill=(8, 8, 26, 200))
        base.paste(header, (0, 0), header)
        draw = ImageDraw.Draw(base)

        badge = images.get('badge')
        if badge:
            badge = badge.resize((70, 70), Image.LANCZOS)
            base.paste(badge, (32, 20), badge)

        clan_name = data.get('clan_name', 'Clã')
        level = data.get('clan_level', 0)
        self._draw_text_outlined(draw, (118, 22), clan_name, f_title, (255, 255, 255), stroke_width=3)
        self._draw_text_outlined(draw, (118, 62), f"Nível {level}", f_small, (180, 180, 195), stroke_width=2)

        league_icon = images.get('league')
        if league_icon:
            li = league_icon.resize((56, 56), Image.LANCZOS)
            base.paste(li, (W - 88, 27), li)

        season = data.get('season', '')
        sw = draw.textlength(season, font=f_small)
        draw.text((W - sw - 28, 78), season, font=f_small, fill=(140, 140, 160))

        section_label = "GUERRAS DE CLÃS"
        slw = draw.textlength(section_label, font=f_sub)
        draw.text((W - slw - 28, 34), section_label, font=f_sub, fill=cwl_accent)

        # --- HERO BANNER ---
        hero_y = 140
        hero_h = 110
        hero = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dh = ImageDraw.Draw(hero)
        dh.rounded_rectangle([40, hero_y, W - 40, hero_y + hero_h], radius=18, fill=(16, 16, 38, 230))
        dh.rounded_rectangle([40, hero_y, W - 40, hero_y + hero_h], radius=18,
                             outline=(cwl_accent[0], cwl_accent[1], cwl_accent[2], 80), width=2)

        glow_grad = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dg = ImageDraw.Draw(glow_grad)
        for x in range(0, W, 2):
            a = max(0, int(40 - 40 * abs(x - W // 2) / (W // 2)))
            dg.line([(x, hero_y), (x, hero_y + hero_h)], fill=(cwl_accent[0], cwl_accent[1], cwl_accent[2], a))
        hero = Image.alpha_composite(hero, glow_grad)
        base = Image.alpha_composite(base, hero)
        draw = ImageDraw.Draw(base)

        star_img = images.get('star')
        if star_img:
            si = star_img.resize((75, 75), Image.LANCZOS)
            base.paste(si, (55, hero_y + 17), si)

        total_stars = data.get('total_stars', 0)
        self._draw_text_outlined(draw, (148, hero_y + 12), "RESULTADO DA TEMPORADA", f_sub, cwl_accent, stroke_width=2)
        val_txt = f"{total_stars} ⭐"
        self._draw_text_outlined(draw, (148, hero_y + 42), val_txt, f_huge, (255, 255, 255), stroke_width=5)

        wars_fought = data.get('wars_fought', 0)
        team_size = data.get('team_size', 15)
        detail_line = f"{wars_fought} guerras  •  {team_size}v{team_size}"
        dlw = draw.textlength(detail_line, font=f_small)
        self._draw_text_outlined(draw, (W - dlw - 60, hero_y + 22), detail_line, f_small, (180, 180, 195), stroke_width=2)
        avg_dest = data.get('total_destruction', 0)
        dest_line = f"{avg_dest}% destruição média"
        d2w = draw.textlength(dest_line, font=f_small)
        self._draw_text_outlined(draw, (W - d2w - 60, hero_y + 54), dest_line, f_small, (100, 255, 180), stroke_width=2)

        # --- STATS CARDS ---
        stats = [
            ("ESTRELAS", f"{total_stars}", star_img or images.get('trophy'), (255, 215, 0)),
            ("ATAQUES", str(data.get('total_attacks', 0)), images.get('medal'), (80, 200, 255)),
            ("MEMBROS", str(data.get('member_count', 0)), images.get('badge'), (255, 100, 100)),
            ("DESTRUIÇÃO", f"{avg_dest}%", images.get('trophy'), (100, 255, 150)),
        ]

        card_w = 235
        card_h = 105
        gap = 20
        total_w = 4 * card_w + 3 * gap
        start_x = (W - total_w) // 2
        card_y = hero_y + hero_h + 28

        for i, (label, value, icon, accent) in enumerate(stats):
            cx = start_x + i * (card_w + gap)
            cy = card_y
            card = Image.new('RGBA', (card_w, card_h), (0, 0, 0, 0))
            cd = ImageDraw.Draw(card)
            cd.rounded_rectangle([0, 0, card_w, card_h], radius=14, fill=(14, 14, 32, 230))
            cd.rounded_rectangle([0, 0, card_w, card_h], radius=14,
                                 outline=(accent[0], accent[1], accent[2], 50), width=1)
            cd.rounded_rectangle([0, 0, card_w, 4], radius=2, fill=accent)
            base.paste(card, (cx, cy), card)
            draw = ImageDraw.Draw(base)

            if icon:
                ic = icon.resize((28, 28), Image.LANCZOS)
                base.paste(ic, (cx + 16, cy + 14), ic)

            vw = draw.textlength(value, font=f_big)
            self._draw_text_outlined(draw, (cx + card_w - vw - 16, cy + 14), value, f_big, (255, 255, 255), stroke_width=3)
            lw = draw.textlength(label, font=f_tiny)
            draw.text((cx + 16, cy + card_h - 26), label, font=f_tiny, fill=accent)

        # --- TOP ATACANTES ---
        attackers = data.get('top_attackers', [])
        atk_y = card_y + card_h + 28

        panel = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        dp = ImageDraw.Draw(panel)
        dp.rounded_rectangle([40, atk_y, W - 40, atk_y + 130], radius=14, fill=(14, 14, 32, 230))
        dp.rounded_rectangle([40, atk_y, W - 40, atk_y + 130], radius=14, outline=(cwl_accent[0], cwl_accent[1], cwl_accent[2], 30), width=1)
        base = Image.alpha_composite(base, panel)
        draw = ImageDraw.Draw(base)

        self._draw_text_outlined(draw, (58, atk_y + 14), "TOP ATACANTES", f_sub, cwl_accent, stroke_width=2)

        medals_emoji = ["🥇", "🥈", "🥉"]
        if attackers:
            for rank, a in enumerate(attackers[:3]):
                ay = atk_y + 50 + rank * 28
                self._draw_text_outlined(draw, (58, ay), f"{medals_emoji[rank]}  {a['name']}", f_small, (255, 255, 255), stroke_width=2)
                star_txt = f"{a['stars']} ⭐  •  {a['attacks']} atqs"
                stw = draw.textlength(star_txt, font=f_tiny)
                draw.text((W - stw - 58, ay + 2), star_txt, font=f_tiny, fill=(255, 215, 0))
        else:
            draw.text((W // 2 - 80, atk_y + 70), "Nenhum atacante disponível", font=f_small, fill=(150, 150, 160))

        # --- FOOTER ---
        footer_y = H - 38
        draw.line([(40, footer_y - 6), (W - 40, footer_y - 6)], fill=(255, 255, 255, 16), width=1)
        draw.text((W // 2 - 80, footer_y - 8), "Temporada Finalizada", font=f_tiny, fill=(140, 140, 160))
        league_name = data.get('league_name', '')
        ltw = draw.textlength(league_name, font=f_tiny)
        draw.text((W - ltw - 50, footer_y - 8), league_name, font=f_tiny, fill=cwl_accent)

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
                self._fetch_image(session, self.assets['cwl_bg']),
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
                'cwl_bg': res[0], 'medal': res[1], 'trophy': res[2],
                'xp': res[3], 'star': res[4], 'badge': res[5], 'league': res[6],
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
