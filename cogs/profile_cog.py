# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands
import coc
from pymongo import DESCENDING
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger("profile_cog")

class ProfileCog(commands.Cog, name="Perfis de Membros"):
    """Cog para gerenciar perfis de membros e comandos relacionados."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        
    def create_profile_embed(self, profile_data: dict) -> discord.Embed:
        """Cria e retorna um discord.Embed a partir dos dados do perfil."""
        embed = discord.Embed(
            title=f"📋 {profile_data['name']}",
            description=f"🏰 **CV{profile_data['town_hall']}** • 🎯 **Nível {profile_data['exp_level']}** • `{profile_data['tag']}`",
            color=discord.Color.blue()
        )

        if profile_data['league_icon']:
            embed.set_thumbnail(url=profile_data['league_icon'])

        league_emoji = self.get_league_emoji(profile_data['league'])
        trophy_text = f"🏆 **Atual:** {profile_data['trophies']}\n🥇 **Recorde:** {profile_data['best_trophies']}\n{league_emoji} **Liga:** {profile_data['league']}"
        embed.add_field(name="🏆 Troféus", value=trophy_text, inline=True)

        ratio_emoji = "🟢" if profile_data['donation_ratio'] >= 1.0 else "🟡" if profile_data['donation_ratio'] >= 0.5 else "🔴"
        donation_text = f"📤 **Doadas:** {profile_data['donations']:,}\n📥 **Recebidas:** {profile_data['received']:,}\n{ratio_emoji} **Razão:** {profile_data['donation_ratio']}"
        embed.add_field(name="🎁 Doações", value=donation_text, inline=True)

        if profile_data.get('attack_wins') or profile_data.get('defense_wins'):
            battle_text = f"⚔️ **Ataques:** {profile_data['attack_wins']:,}\n🛡️ **Defesas:** {profile_data['defense_wins']:,}"
            if profile_data.get('war_stars'):
                battle_text += f"\n⭐ **Estrelas:** {profile_data['war_stars']:,}"
            embed.add_field(name="⚔️ Batalhas", value=battle_text, inline=True)

        if profile_data['heroes']:
            heroes_text = ""
            for hero in profile_data['heroes']:
                emoji = self.get_hero_emoji(hero['name'])
                progress_bar = "▰" * int(hero['progress'] / 10) + "▱" * (10 - int(hero['progress'] / 10))
                heroes_text += f"{emoji} **{hero['name'].replace(' ', ' ')}:** {hero['level']}/{hero['max_level']} `{progress_bar}` {hero['progress']}%\n"
            
            if profile_data['total_hero_progress']:
                heroes_text += f"\n📊 **Progresso Total:** {profile_data['total_hero_progress']}%"
            
            embed.add_field(name="👑 Heróis", value=heroes_text, inline=False)

        if profile_data['clan_info']:
            clan_text = f"🏴 **{profile_data['clan_info']['name']}**\n👤 **Cargo:** {profile_data['clan_info']['role']}\n📊 **Nível:** {profile_data['clan_info']['level']}"
            embed.add_field(name="🏴 Clã", value=clan_text, inline=True)

        extra_info = []
        if profile_data.get('clan_capital_gold'):
            extra_info.append(f"🏛️ **Capital:** {profile_data['clan_capital_gold']:,} ouro")
        if profile_data.get('builder_hall'):
            extra_info.append(f"🔨 **CV Construtor:** {profile_data['builder_hall']}")
        
        if extra_info:
            embed.add_field(name="📊 Extras", value="\n".join(extra_info), inline=True)

        if profile_data['trophy_history']:
            trophy_graph = self.create_trophy_graph(profile_data['trophy_history'])
            embed.add_field(name="📈 Tendência de Troféus", value=trophy_graph, inline=False)

        embed.set_footer(text=f"Atualizado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}")
        return embed

    async def fetch_player_profile_data(self, player_tag: str) -> dict:
        """Busca dados completos de um jogador para o perfil, usado pela API e comandos."""
        try:
            player_data = await self.bot.api_client.get_player(player_tag)
            if not player_data:
                return {"error": "Jogador não encontrado."}

            trophy_history = []
            if self.db is not None:
                cursor = self.db.trophy_history.find({"player_tag": player_tag}).sort("timestamp", DESCENDING).limit(30)
                trophy_history = [{"trophies": doc["trophies"], "timestamp": doc["timestamp"].strftime("%d/%m")} async for doc in cursor]
                trophy_history.reverse()

            cwl_status = "active"
            if self.db is not None:
                note_doc = await self.db.player_notes.find_one({"_id": player_tag})
                if note_doc and "cwl_status" in note_doc:
                    cwl_status = note_doc["cwl_status"]

            heroes_data = []
            total_hero_levels = 0
            max_hero_levels = 0
            
            for hero in player_data.heroes:
                if hero.is_home_base:
                    heroes_data.append({
                        "name": hero.name,
                        "level": hero.level,
                        "max_level": hero.max_level,
                        "progress": round((hero.level / hero.max_level) * 100, 1) if hero.max_level > 0 else 0
                    })
                    total_hero_levels += hero.level
                    max_hero_levels += hero.max_level

            attack_wins = player_data.attack_wins or 0
            defense_wins = player_data.defense_wins or 0
            
            clan_info = None
            if player_data.clan:
                try:
                    clan_info = {
                        "name": player_data.clan.name,
                        "tag": player_data.clan.tag,
                        "role": player_data.role.in_game_name if hasattr(player_data.role, 'in_game_name') else str(player_data.role),
                        "level": getattr(player_data.clan, 'level', 'N/A')
                    }
                except AttributeError as e:
                    logger.warning(f"Erro ao acessar dados do clã para {player_tag}: {e}")
                    clan_info = { "name": "N/A", "tag": "N/A", "role": "N/A", "level": "N/A" }


            donation_ratio = round(player_data.donations / player_data.received, 2) if player_data.received > 0 else 0

            profile = {
                "name": player_data.name, "tag": player_data.tag, "town_hall": player_data.town_hall,
                "exp_level": player_data.exp_level, "heroes": heroes_data,
                "total_hero_progress": round((total_hero_levels / max_hero_levels) * 100, 1) if max_hero_levels > 0 else 0,
                "donations": player_data.donations, "received": player_data.received, "donation_ratio": donation_ratio,
                "trophies": player_data.trophies, "best_trophies": player_data.best_trophies,
                "league": player_data.league.name if player_data.league else "N/A",
                "league_icon": player_data.league.icon.medium if player_data.league and player_data.league.icon else None,
                "trophy_history": trophy_history, "attack_wins": attack_wins, "defense_wins": defense_wins,
                "clan_info": clan_info, "war_stars": getattr(player_data, 'war_stars', 0),
                "clan_capital_gold": getattr(player_data, 'clan_capital_contributions', 0),
                "builder_hall": getattr(player_data, 'builder_hall_level', 0), "cwl_status": cwl_status
            }
            return profile
        except coc.NotFound:
            return {"error": "Jogador não encontrado com a tag fornecida."}
        except Exception as e:
            logger.error(f"Erro ao buscar perfil para {player_tag}: {e}", exc_info=True)
            return {"error": "Ocorreu um erro interno ao buscar o perfil."}

    def create_trophy_graph(self, trophy_history: list) -> str:
        """Cria um gráfico simples de troféus usando caracteres."""
        if not trophy_history or len(trophy_history) < 2: return "📊 Histórico insuficiente"
        recent_history = trophy_history[-10:]
        values = [entry["trophies"] for entry in recent_history]
        if not values: return "📊 Sem dados"
        min_val, max_val = min(values), max(values)
        if max_val == min_val: return f"📊 Estável em {max_val} 🏆"
        graph = "📊 "
        for i in range(len(values) - 1):
            graph += "📈" if values[i+1] > values[i] else "📉" if values[i+1] < values[i] else "➡️"
        trend = "📈 Subindo" if values[-1] > values[0] else "📉 Descendo" if values[-1] < values[0] else "➡️ Estável"
        return f"{graph}\n{trend} ({values[0]} → {values[-1]})"

    def get_hero_emoji(self, hero_name: str) -> str:
        """Retorna emoji para o herói."""
        hero_emojis = { "Barbarian King": "👑", "Archer Queen": "🏹", "Grand Warden": "🔮", "Royal Champion": "⚡", "Battle Machine": "🤖", "Battle Copter": "🚁" }
        return hero_emojis.get(hero_name, "🦸")

    def get_league_emoji(self, league_name: str) -> str:
        """Retorna emoji para a liga."""
        league_emojis = { "Bronze": "🥉", "Silver": "🥈", "Gold": "🥇", "Crystal": "💎", "Master": "🎖️", "Champion": "🏆", "Titan": "⚡", "Legend": "🌟" }
        for league, emoji in league_emojis.items():
            if league.lower() in league_name.lower(): return emoji
        return "🏆"

    @commands.command(name='perfil')
    async def profile_command(self, ctx: commands.Context, *, player_identifier: str = None):
        """Mostra o perfil completo de um membro do clã."""
        await ctx.typing()
        
        try:
            player_tag = None
            if not player_identifier:
                if self.db:
                    user_data = await self.db.users.find_one({"discord_id": ctx.author.id})
                    if user_data and "player_tag" in user_data:
                        player_tag = user_data["player_tag"]
                    else:
                        await ctx.send("❌ Você não tem uma tag registrada! Use `!perfil <tag/nome>` ou registre-se.")
                        return
                else:
                    await ctx.send("❌ Por favor, forneça uma tag ou nome do jogador.")
                    return
            elif coc.utils.is_valid_tag(player_identifier):
                player_tag = coc.utils.correct_tag(player_identifier)
            else:
                clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
                member = clan.get_member_by(name=player_identifier, case_sensitive=False)
                if not member:
                    await ctx.send(f"❌ Não encontrei '{player_identifier}' no clã.")
                    return
                player_tag = member.tag

            profile_data = await self.fetch_player_profile_data(player_tag)

            if "error" in profile_data:
                await ctx.send(f"❌ {profile_data['error']}")
                return

            embed = self.create_profile_embed(profile_data)
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro no comando !perfil: {e}", exc_info=True)
            await ctx.send("❌ Ocorreu um erro ao processar o comando.")

async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
