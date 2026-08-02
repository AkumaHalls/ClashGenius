# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any
import discord
import geniuslib as coc
from geniuslib.formatters import format_th, format_trophies, format_number
from geniuslib.upgrade_tracker import get_th_upgrade_summary
from discord.ext import commands
from pymongo import DESCENDING

logger = logging.getLogger("profile_cog")

class ProfileCog(commands.Cog, name="Perfis de Membros"):
    """Cog para buscar dados detalhados e hitrate histórico do jogador."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    async def fetch_player_profile_data(self, player_tag: str) -> Dict[str, Any]:
        """Busca dados da API da Supercell e cruza com o Hitrate do BD."""
        try:
            # 1. DADOS EM TEMPO REAL DA SUPERCELL (Liga, Heróis, Doações)
            player = await self.bot.api_client.get_player(player_tag)
            if not player:
                return {"error": "Jogador não encontrado na Supercell."}

            home_heroes = ["Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion", "Minion Prince", "Dragon Duke"]
            heroes_data = [
                {"name": h.name, "level": h.level, "max_level": h.max_level, "equipment": [{"name": e.name, "level": e.level, "max_level": e.max_level} for e in getattr(h, 'equipment', [])]}
                for h in getattr(player, 'heroes', []) if h.name in home_heroes
            ]
            
            pets_data = [
                {"name": p.name, "level": p.level, "max_level": p.max_level}
                for p in getattr(player, 'pets', [])
            ]

            equipment_data = [
                {"name": e.name, "level": e.level, "max_level": e.max_level, "village": e.village}
                for e in getattr(player, 'equipment', [])
            ]

            troops_data = [{"name": t.name, "level": t.level, "max_level": t.max_level} for t in getattr(player, 'troops', []) if getattr(t, 'village', 'home') == 'home']
            spells_data = [{"name": s.name, "level": s.level, "max_level": s.max_level} for s in getattr(player, 'spells', []) if getattr(s, 'village', 'home') == 'home']
            
            legend_stats = getattr(player, 'legend_statistics', None)
            legend_data = {}
            if legend_stats:
                legend_data = {
                    "current_season": {"trophies": getattr(legend_stats, 'current_season', None) and getattr(legend_stats.current_season, 'trophies', 0)},
                    "previous_season": {"trophies": getattr(legend_stats, 'previous_season', None) and getattr(legend_stats.previous_season, 'trophies', 0)},
                    "best_season": {"trophies": getattr(legend_stats, 'best_season', None) and getattr(legend_stats.best_season, 'trophies', 0)},
                    "legend_trophies": getattr(legend_stats, 'legend_trophies', 0),
                }
            
            capital_gold = getattr(player, 'clan_capital_contributions', 0)
            
            league_icon = player.league.icon.url if player.league and player.league.icon else None

            # 2.5. UPGRADE TRACKER
            upgrade_summary = get_th_upgrade_summary(player, target_th=None, builder_count=5)
            upgrade_data = {}
            if upgrade_summary and upgrade_summary.upgrades:
                upgrade_data = {
                    "total_gold": upgrade_summary.total_gold,
                    "total_elixir": upgrade_summary.total_elixir,
                    "total_dark_elixir": upgrade_summary.total_dark_elixir,
                    "total_time_seconds": upgrade_summary.total_time_seconds,
                    "total_upgrades": len(upgrade_summary.upgrades),
                    "current_th": upgrade_summary.current_th,
                    "target_th": upgrade_summary.target_th,
                    "estimated_real_time_days": round(upgrade_summary.estimated_real_time.total_seconds() / 86400, 1),
                }

            hitrate_data = {
                "total_wars": 0,
                "attacks_made": 0,
                "attacks_missed": 0,
                "total_stars": 0,
                "three_star_attacks": 0,
                "avg_destruction": 0.0
            }

            war_history_list = []

            if self.db is not None:
                # Procura as últimas 50 guerras onde o jogador estava na escalação
                pipeline = [
                    {"$match": {"our_clan_members_in_war.tag": player_tag}},
                    {"$sort": {"war_data.end_time_iso": DESCENDING}},
                    {"$limit": 50},  # <--- LIMITE ALTERADO PARA 50 AQUI
                    {"$unwind": "$our_clan_members_in_war"},
                    {"$match": {"our_clan_members_in_war.tag": player_tag}}
                ]
                
                cursor = self.db.war_history.aggregate(pipeline)
                total_destruction = 0
                
                async for doc in cursor:
                    member_data = doc.get("our_clan_members_in_war", {})
                    war_info = doc.get("war_data", {})
                    attacks_per_member = war_info.get("attacks_per_member", 2)
                    
                    hitrate_data["total_wars"] += 1
                    attacks = member_data.get("attacks_made", [])
                    
                    hitrate_data["attacks_made"] += len(attacks)
                    hitrate_data["attacks_missed"] += (attacks_per_member - len(attacks))

                    war_stars = 0
                    war_destruction = 0.0
                    for atk in attacks:
                        stars = atk.get("stars", 0)
                        hitrate_data["total_stars"] += stars
                        war_stars += stars
                        war_destruction += atk.get("destruction", 0)
                        total_destruction += atk.get("destruction", 0)
                        if stars == 3:
                            hitrate_data["three_star_attacks"] += 1

                    # Carteira de Combate: dados por guerra
                    clan_stars = war_info.get("clan_stars", 0)
                    opp_stars = war_info.get("opponent_stars", 0)
                    clan_dest = float(str(war_info.get("clan_destruction", "0%")).replace('%', ''))
                    opp_dest = float(str(war_info.get("opponent_destruction", "0%")).replace('%', ''))
                    result = "Empate"
                    if clan_stars > opp_stars or (clan_stars == opp_stars and clan_dest > opp_dest):
                        result = "Vitória"
                    elif opp_stars > clan_stars or (clan_stars == opp_stars and opp_dest > clan_dest):
                        result = "Derrota"

                    war_history_list.append({
                        "opponent_name": war_info.get("opponent_name", "Desconhecido"),
                        "end_time_iso": war_info.get("end_time_iso"),
                        "result": result,
                        "is_cwl": war_info.get("is_cwl", False),
                        "stars": war_stars,
                        "destruction": round(war_destruction, 1),
                        "attacks_made": len(attacks),
                        "attacks_missed": max(attacks_per_member - len(attacks), 0),
                    })
                            
                if hitrate_data["attacks_made"] > 0:
                    hitrate_data["avg_destruction"] = round(total_destruction / hitrate_data["attacks_made"], 1)

            war_history_list = war_history_list[:15]

            return {
                "name": player.name,
                "tag": player.tag,
                "town_hall": player.town_hall,
                "trophies": player.trophies,
                "league": player.league.name if player.league else "Sem Liga",
                "league_icon": league_icon,
                "donations": player.donations,
                "received": player.received,
                "heroes": heroes_data,
                "pets": pets_data,
                "equipment": equipment_data,
                "troops": troops_data,
                "spells": spells_data,
                "legend_stats": legend_data,
                "capital_gold": capital_gold,
                "role": player.role.name.capitalize() if hasattr(player, 'role') and hasattr(player.role, 'name') else "Membro",
                "hitrate": hitrate_data,
                "upgrade_data": upgrade_data,
                "war_history": war_history_list
            }

        except coc.NotFound:
            return {"error": "Jogador não encontrado."}
        except Exception as e:
            logger.error(f"Erro fetch_player_profile_data: {e}", exc_info=True)
            return {"error": "Falha de conexão com a API da Supercell ou Banco de Dados."}

    def create_profile_embed(self, data: Dict[str, Any]) -> discord.Embed:
        """Gera o embed de perfil do jogador com todos os dados enriquecidos."""
        embed = discord.Embed(color=0x2b2d31)
        embed.set_author(name=f"{data.get('name', '?')} ({data.get('tag', '?')})", icon_url=data.get('league_icon'))
        embed.set_thumbnail(url=f"https://coc.guide/static/imgs/other/town-hall-{data.get('town_hall', 1)}.png")

        header = f"🏛️ **{format_th(data.get('town_hall', 0))}** | {format_trophies(data.get('trophies', 0))} | {data.get('role', 'Membro')}"
        embed.description = header

        season = (
            f"🎁 **Doadas:** {data.get('donations', 0):,}\n"
            f"📥 **Recebidas:** {data.get('received', 0):,}"
        )
        embed.add_field(name="📊 Temporada", value=season, inline=False)

        heroes = data.get('heroes', [])
        if heroes:
            hero_emojis = {"Barbarian King": "👑", "Archer Queen": "👸", "Grand Warden": "🧙‍♂️", "Royal Champion": "🏇", "Minion Prince": "🦇", "Dragon Duke": "🐉"}
            lines = []
            for h in heroes:
                emoji = hero_emojis.get(h['name'], "🦸")
                equip_str = ""
                for eq in h.get('equipment', []):
                    equip_str += f"`{eq['name']}` {eq['level']} "
                lines.append(f"{emoji} Nvl {h['level']}  {equip_str}")
            embed.add_field(name="🦸 Heróis", value="\n".join(lines), inline=False)

        pets = data.get('pets', [])
        if pets:
            embed.add_field(name="🐕 Pets", value=" ".join(f"🐾 **{p['name']}** {p['level']}" for p in pets), inline=False)

        equipment = data.get('equipment', [])
        if equipment:
            equip_lines = []
            for eq in equipment:
                equip_lines.append(f"`{eq['name']}` {eq['level']}/{eq.get('max_level', '?')}")
            embed.add_field(name="⚔️ Equipamentos", value="\n".join(equip_lines[:10]), inline=False)

        legend = data.get('legend_stats', {})
        if legend and legend.get('legend_trophies', 0):
            ls = f"🏆 **Legends:** {legend.get('legend_trophies', 0)}"
            if legend.get('best_season', {}).get('trophies'):
                ls += f"\n⭐ **Best Season:** {legend['best_season']['trophies']}"
            embed.add_field(name="👑 Lenda Liga", value=ls, inline=False)

        if data.get('capital_gold', 0):
            embed.add_field(name="🏰 Capital", value=f"⚒️ **Contribuições:** {data['capital_gold']:,}", inline=False)

        ug = data.get('upgrade_data', {})
        if ug and ug.get('total_upgrades', 0) > 0:
            embed.add_field(
                name="🔨 Upgrades Pendentes",
                value=(
                    f"📦 **Total:** {ug['total_upgrades']} upgrades\n"
                    f"🪙 **Ouro:** {format_number(ug['total_gold'])}\n"
                    f"🧪 **Elixir:** {format_number(ug['total_elixir'])}\n"
                    f"💎 **Elixir N:** {format_number(ug['total_dark_elixir'])}\n"
                    f"⏳ **Tempo real:** ~{ug['estimated_real_time_days']} dias"
                ),
                inline=False
            )

        hit = data.get('hitrate', {})
        if hit and hit.get('total_wars', 0) > 0:
            hr = (
                f"📊 **Guerras:** {hit.get('total_wars', 0)}\n"
                f"⚔️ **Ataques:** {hit.get('attacks_made', 0)} | Perdidos: {hit.get('attacks_missed', 0)}\n"
                f"⭐ **Média:** {hit.get('total_stars', 0) / max(hit.get('attacks_made', 1), 1):.1f} | 3⭐: {hit.get('three_star_attacks', 0)}\n"
                f"💥 **Destruição Média:** {hit.get('avg_destruction', 0)}%"
            )
            embed.add_field(name="📈 Hitrate", value=hr, inline=False)

        embed.set_footer(text="ClashGenius • Perfil de Membro")
        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
