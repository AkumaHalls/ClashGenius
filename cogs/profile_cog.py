# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any
import coc
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

            home_heroes = ["Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion", "Minion Prince"]
            heroes_data = [
                {"name": h.name, "level": h.level, "max_level": h.max_level} 
                for h in getattr(player, 'heroes', []) if h.name in home_heroes
            ]
            
            league_icon = player.league.icon.url if player.league and player.league.icon else None

            # 2. PERÍCIA DE BANCO DE DADOS: CARTÃO DE BATALHA (Hitrate)
            hitrate_data = {
                "total_wars": 0,
                "attacks_made": 0,
                "attacks_missed": 0,
                "total_stars": 0,
                "three_star_attacks": 0,
                "avg_destruction": 0.0
            }

            if self.db is not None:
                # Procura as últimas 15 guerras onde o jogador estava na escalação
                pipeline = [
                    {"$match": {"our_clan_members_in_war.tag": player_tag}},
                    {"$sort": {"war_data.end_time_iso": DESCENDING}},
                    {"$limit": 15},
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
                    
                    for atk in attacks:
                        stars = atk.get("stars", 0)
                        hitrate_data["total_stars"] += stars
                        total_destruction += atk.get("destruction", 0)
                        if stars == 3:
                            hitrate_data["three_star_attacks"] += 1
                            
                if hitrate_data["attacks_made"] > 0:
                    hitrate_data["avg_destruction"] = round(total_destruction / hitrate_data["attacks_made"], 1)

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
                "role": player.role.name.capitalize() if hasattr(player, 'role') and hasattr(player.role, 'name') else "Membro",
                "hitrate": hitrate_data
            }

        except coc.NotFound:
            return {"error": "Jogador não encontrado."}
        except Exception as e:
            logger.error(f"Erro fetch_player_profile_data: {e}", exc_info=True)
            return {"error": "Falha de conexão com a API da Supercell ou Banco de Dados."}

async def setup(bot: commands.Bot):
    await bot.add_cog(ProfileCog(bot))
