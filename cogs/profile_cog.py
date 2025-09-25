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

    async def fetch_player_profile_data(self, player_tag: str) -> dict:
        """Busca dados completos de um jogador para o perfil, usado pela API e comandos."""
        try:
            player_data = await self.bot.api_client.get_player(player_tag)
            if not player_data:
                return {"error": "Jogador não encontrado."}

            # Histórico de troféus
            trophy_history = []
            if self.db is not None:
                cursor = self.db.trophy_history.find({"player_tag": player_tag}).sort("timestamp", DESCENDING).limit(30)
                trophy_history = [{"trophies": doc["trophies"], "timestamp": doc["timestamp"].strftime("%d/%m")} async for doc in cursor]
                trophy_history.reverse()

            # Calcular progresso dos heróis
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

            # Calcular estatísticas de ataques
            attack_wins = player_data.attack_wins or 0
            defense_wins = player_data.defense_wins or 0
            total_attacks = attack_wins + (player_data.clan.get("attacks_won", 0) if player_data.clan else 0)
            
            # Informações do clã
            clan_info = None
            if player_data.clan:
                clan_info = {
                    "name": player_data.clan.name,
                    "tag": player_data.clan.tag,
                    "role": player_data.role,
                    "level": player_data.clan.level if hasattr(player_data.clan, 'level') else 'N/A'
                }

            # Calcular razão doação/recebimento
            donation_ratio = 0
            if player_data.received > 0:
                donation_ratio = round(player_data.donations / player_data.received, 2)

            profile = {
                "name": player_data.name,
                "tag": player_data.tag,
                "town_hall": player_data.town_hall,
                "exp_level": player_data.exp_level,
                "heroes": heroes_data,
                "total_hero_progress": round((total_hero_levels / max_hero_levels) * 100, 1) if max_hero_levels > 0 else 0,
                "donations": player_data.donations,
                "received": player_data.received,
                "donation_ratio": donation_ratio,
                "trophies": player_data.trophies,
                "best_trophies": player_data.best_trophies,
                "league": player_data.league.name if player_data.league else "N/A",
                "league_icon": player_data.league.icon.medium if player_data.league and player_data.league.icon else None,
                "trophy_history": trophy_history,
                "attack_wins": attack_wins,
                "defense_wins": defense_wins,
                "clan_info": clan_info,
                "war_stars": player_data.war_stars or 0,
                "clan_capital_gold": player_data.clan_capital_contributions or 0,
                "builder_hall": player_data.builder_hall_level if hasattr(player_data, 'builder_hall_level') else 0
            }
            return profile
        except coc.NotFound:
            return {"error": "Jogador não encontrado com a tag fornecida."}
        except Exception as e:
            logger.error(f"Erro ao buscar perfil para {player_tag}: {e}", exc_info=True)
            return {"error": "Ocorreu um erro interno ao buscar o perfil."}

    def create_trophy_graph(self, trophy_history: list) -> str:
        """Cria um gráfico simples de troféus usando caracteres."""
        if not trophy_history or len(trophy_history) < 2:
            return "📊 Histórico insuficiente"
        
        # Pegar últimos 10 registros
        recent_history = trophy_history[-10:]
        values = [entry["trophies"] for entry in recent_history]
        
        if not values:
            return "📊 Sem dados"
        
        min_val, max_val = min(values), max(values)
        if max_val == min_val:
            return f"📊 Estável em {max_val} 🏆"
        
        # Criar gráfico simples
        graph = "📊 "
        for i in range(len(values) - 1):
            current, next_val = values[i], values[i + 1]
            if next_val > current:
                graph += "📈"
            elif next_val < current:
                graph += "📉"
            else:
                graph += "➡️"
        
        trend = "📈 Subindo" if values[-1] > values[0] else "📉 Descendo" if values[-1] < values[0] else "➡️ Estável"
        return f"{graph}\n{trend} ({values[0]} → {values[-1]})"

    def get_hero_emoji(self, hero_name: str) -> str:
        """Retorna emoji para o herói."""
        hero_emojis = {
            "Barbarian King": "👑",
            "Archer Queen": "🏹",
            "Grand Warden": "🔮",
            "Royal Champion": "⚡",
            "Battle Machine": "🤖"
        }
        return hero_emojis.get(hero_name, "👑")

    def get_league_emoji(self, league_name: str) -> str:
        """Retorna emoji para a liga."""
        league_emojis = {
            "Bronze": "🥉",
            "Silver": "🥈", 
            "Gold": "🥇",
            "Crystal": "💎",
            "Master": "🎖️",
            "Champion": "🏆",
            "Titan": "⚡",
            "Legend": "🌟"
        }
        for league, emoji in league_emojis.items():
            if league.lower() in league_name.lower():
                return emoji
        return "🏆"

    @commands.command(name='perfil')
    async def profile_command(self, ctx: commands.Context, *, player_identifier: str = None):
        """
        Mostra o perfil completo de um membro do clã.
        
        Uso: !perfil [tag/nome]
        Se não especificar, mostra seu próprio perfil (se registrado).
        """
        await ctx.typing()
        
        try:
            player_tag = None
            
            # Se não forneceu identificador, tenta buscar pelo usuário do Discord
            if not player_identifier:
                if self.db:
                    user_data = await self.db.users.find_one({"discord_id": ctx.author.id})
                    if user_data and "player_tag" in user_data:
                        player_tag = user_data["player_tag"]
                    else:
                        await ctx.send("❌ Você não tem uma tag registrada! Use `!perfil <tag/nome>` ou registre-se primeiro.")
                        return
                else:
                    await ctx.send("❌ Por favor, forneça uma tag ou nome do jogador.")
                    return
            
            # Verifica se é uma tag válida
            elif coc.utils.is_valid_tag(player_identifier):
                player_tag = coc.utils.correct_tag(player_identifier)
            else:
                # Busca por nome no clã
                clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
                member = clan.get_member_by(name=player_identifier, case_sensitive=False)
                if not member:
                    await ctx.send(f"❌ Não encontrei nenhum membro com o nome '{player_identifier}' no clã.")
                    return
                player_tag = member.tag

            profile_data = await self.fetch_player_profile_data(player_tag)

            if "error" in profile_data:
                await ctx.send(f"❌ {profile_data['error']}")
                return

            # Criar embed principal
            embed = discord.Embed(
                title=f"📋 {profile_data['name']}",
                description=f"🏰 **CV{profile_data['town_hall']}** • 🎯 **Nível {profile_data['exp_level']}** • `{profile_data['tag']}`",
                color=discord.Color.blue()
            )

            # Thumbnail com ícone da liga
            if profile_data['league_icon']:
                embed.set_thumbnail(url=profile_data['league_icon'])

            # Campo de troféus
            league_emoji = self.get_league_emoji(profile_data['league'])
            trophy_text = f"🏆 **Atual:** {profile_data['trophies']}\n🥇 **Recorde:** {profile_data['best_trophies']}\n{league_emoji} **Liga:** {profile_data['league']}"
            embed.add_field(name="🏆 Troféus", value=trophy_text, inline=True)

            # Campo de doações
            ratio_emoji = "🟢" if profile_data['donation_ratio'] >= 1.0 else "🟡" if profile_data['donation_ratio'] >= 0.5 else "🔴"
            donation_text = f"📤 **Doadas:** {profile_data['donations']:,}\n📥 **Recebidas:** {profile_data['received']:,}\n{ratio_emoji} **Razão:** {profile_data['donation_ratio']}"
            embed.add_field(name="🎁 Doações", value=donation_text, inline=True)

            # Campo de batalhas
            if profile_data.get('attack_wins') or profile_data.get('defense_wins'):
                battle_text = f"⚔️ **Ataques:** {profile_data['attack_wins']:,}\n🛡️ **Defesas:** {profile_data['defense_wins']:,}"
                if profile_data.get('war_stars'):
                    battle_text += f"\n⭐ **Estrelas:** {profile_data['war_stars']:,}"
                embed.add_field(name="⚔️ Batalhas", value=battle_text, inline=True)

            # Campo de heróis
            if profile_data['heroes']:
                heroes_text = ""
                for hero in profile_data['heroes']:
                    emoji = self.get_hero_emoji(hero['name'])
                    progress_bar = "▰" * int(hero['progress'] / 10) + "▱" * (10 - int(hero['progress'] / 10))
                    heroes_text += f"{emoji} **{hero['name'].replace(' ', ' ')}:** {hero['level']}/{hero['max_level']} `{progress_bar}` {hero['progress']}%\n"
                
                if profile_data['total_hero_progress']:
                    heroes_text += f"\n📊 **Progresso Total:** {profile_data['total_hero_progress']}%"
                
                embed.add_field(name="👑 Heróis", value=heroes_text, inline=False)

            # Informações do clã
            if profile_data['clan_info']:
                clan_text = f"🏴 **{profile_data['clan_info']['name']}**\n👤 **Cargo:** {profile_data['clan_info']['role']}\n📊 **Nível:** {profile_data['clan_info']['level']}"
                embed.add_field(name="🏴 Clã", value=clan_text, inline=True)

            # Capital do Clã e Base do Construtor
            extra_info = []
            if profile_data.get('clan_capital_gold'):
                extra_info.append(f"🏛️ **Capital:** {profile_data['clan_capital_gold']:,} ouro")
            if profile_data.get('builder_hall'):
                extra_info.append(f"🔨 **CV Construtor:** {profile_data['builder_hall']}")
            
            if extra_info:
                embed.add_field(name="📊 Extras", value="\n".join(extra_info), inline=True)

            # Gráfico de troféus
            if profile_data['trophy_history']:
                trophy_graph = self.create_trophy_graph(profile_data['trophy_history'])
                embed.add_field(name="📈 Tendência de Troféus", value=trophy_graph, inline=False)

            # Footer com timestamp
            embed.set_footer(text=f"Atualizado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}")

            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro no comando !perfil: {e}", exc_info=True)
            await ctx.send("❌ Ocorreu um erro ao processar o comando. Tente novamente.")

    @commands.command(name='perfil-detalhado', aliases=['pd', 'profile-detail'])
    async def detailed_profile_command(self, ctx: commands.Context, *, player_identifier: str = None):
        """Versão mais detalhada do perfil com múltiplos embeds."""
        await ctx.typing()
        
        try:
            # Mesmo processo de busca do comando principal
            player_tag = None
            
            if not player_identifier:
                if self.db:
                    user_data = await self.db.users.find_one({"discord_id": ctx.author.id})
                    if user_data and "player_tag" in user_data:
                        player_tag = user_data["player_tag"]
                    else:
                        await ctx.send("❌ Você não tem uma tag registrada!")
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

            # Embed 1: Informações principais
            main_embed = discord.Embed(
                title=f"📋 Perfil Detalhado: {profile_data['name']}",
                description=f"🏰 **CV{profile_data['town_hall']}** • 🎯 **Nível {profile_data['exp_level']}**",
                color=discord.Color.gold()
            )
            main_embed.add_field(name="🏷️ Tag", value=f"`{profile_data['tag']}`", inline=True)
            main_embed.add_field(name="🏆 Troféus", value=f"{profile_data['trophies']}", inline=True)
            main_embed.add_field(name="🥇 Recorde", value=f"{profile_data['best_trophies']}", inline=True)

            # Embed 2: Heróis detalhados
            heroes_embed = discord.Embed(title="👑 Heróis Detalhados", color=discord.Color.purple())
            for hero in profile_data['heroes']:
                emoji = self.get_hero_emoji(hero['name'])
                progress = f"{hero['level']}/{hero['max_level']} ({hero['progress']}%)"
                heroes_embed.add_field(name=f"{emoji} {hero['name']}", value=progress, inline=True)

            # Embed 3: Estatísticas de batalha
            battle_embed = discord.Embed(title="⚔️ Estatísticas de Batalha", color=discord.Color.red())
            battle_embed.add_field(name="🗡️ Vitórias em Ataques", value=f"{profile_data['attack_wins']:,}", inline=True)
            battle_embed.add_field(name="🛡️ Vitórias em Defesas", value=f"{profile_data['defense_wins']:,}", inline=True)
            battle_embed.add_field(name="⭐ Estrelas de Guerra", value=f"{profile_data['war_stars']:,}", inline=True)

            # Enviar embeds
            await ctx.send(embed=main_embed)
            await asyncio.sleep(1)  # Pequena pausa entre envios
            await ctx.send(embed=heroes_embed)
            await asyncio.sleep(1)
            await ctx.send(embed=battle_embed)

        except Exception as e:
            logger.error(f"Erro no comando !perfil-detalhado: {e}", exc_info=True)
            await ctx.send("❌ Ocorreu um erro ao processar o comando.")

async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
