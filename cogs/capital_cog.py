# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands
import coc
from typing import Dict, Any

logger = logging.getLogger("capital_cog")

class CapitalCog(commands.Cog, name="Monitoramento da Capital"):
    """Cog para gerenciar e auditar os Finais de Semana de Raide da Capital do Clã."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db

    async def fetch_capital_data_for_web(self) -> Dict[str, Any]:
        """Busca os dados da Raide atual/recente e cruza com a lista do clã para achar os inativos."""
        if not self.bot.api_client:
            return {"error": "API CoC não inicializada."}
        
        try:
            # 1. Busca o log mais recente da capital
            raid_log = await self.bot.api_client.get_raid_log(self.bot.clan_tag, limit=1)
            if not raid_log:
                return {"error": "Nenhum registro de Raide (Capital) encontrado para este clã."}
            
            latest_raid = raid_log[0]
            
            # Dados Gerais
            raid_data = {
                "state": latest_raid.state,
                "start_time": latest_raid.start_time.time.isoformat() if latest_raid.start_time else None,
                "end_time": latest_raid.end_time.time.isoformat() if latest_raid.end_time else None,
                "total_loot": latest_raid.total_loot,
                "total_attacks": latest_raid.attack_count,
                "destroyed_districts": latest_raid.destroyed_district_count,
                "offensive_reward": latest_raid.offensive_reward,
                "defensive_reward": latest_raid.defensive_reward
            }

            # 2. Processa quem atacou
            raid_members_map = {}
            for member in latest_raid.members:
                raid_members_map[member.tag] = {
                    "name": member.name,
                    "tag": member.tag,
                    "attacks": member.attack_count,
                    "limit": member.attack_limit + member.bonus_attack_limit,
                    "looted": member.capital_resources_looted
                }
            
            # 3. Cruza com os membros atuais do clã para pegar quem fez ZERO ataques
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            if clan:
                for clan_member in clan.members:
                    if clan_member.tag not in raid_members_map:
                        # Jogador está no clã, mas não participou da raide
                        raid_members_map[clan_member.tag] = {
                            "name": clan_member.name,
                            "tag": clan_member.tag,
                            "attacks": 0,
                            "limit": 6, # Padrão
                            "looted": 0
                        }

            members_data = list(raid_members_map.values())
            
            # Ordena do maior loot para o menor
            members_data.sort(key=lambda x: x["looted"], reverse=True)

            return {
                "raid": raid_data,
                "members": members_data
            }
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados da Capital: {e}", exc_info=True)
            return {"error": f"Erro interno ao auditar a capital: {str(e)}"}

    @app_commands.command(name="capital", description="🏰 Raio-X da Capital: Mostra Top Atacantes e Inativos (0 ataques).")
    async def capital_report(self, interaction: discord.Interaction):
        """Comando de barra para gerar o relatório da capital no Discord."""
        await interaction.response.defer(thinking=True)
        
        try:
            data = await self.fetch_capital_data_for_web()
            if "error" in data:
                await interaction.followup.send(f"❌ {data['error']}")
                return
            
            raid = data["raid"]
            members = data["members"]

            top_attackers = members[:5] # Top 5
            zero_attacks = [m for m in members if m["attacks"] == 0]
            missed_some_attacks = [m for m in members if 0 < m["attacks"] < m["limit"]]

            status_pt = "Em Andamento" if raid["state"] == "ongoing" else "Finalizada"

            embed = discord.Embed(
                title="🏰 Raio-X da Capital do Clã",
                description=f"**Status:** {status_pt}\n**Ouro Saqueado Global:** 🪙 {raid['total_loot']:,}\n**Distritos Destruídos:** 🏚️ {raid['destroyed_districts']}",
                color=discord.Color.purple(),
                timestamp=datetime.datetime.now()
            )

            # TOP Atacantes
            top_text = ""
            medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
            for i, m in enumerate(top_attackers):
                if m["attacks"] > 0:
                    top_text += f"{medals[i]} **{m['name']}** ━ 🪙 {m['looted']:,} *(Ataques: {m['attacks']}/{m['limit']})*\n"
            embed.add_field(name="🏆 Máquinas de Farm (Top 5)", value=top_text or "Nenhum ataque registrado.", inline=False)

            # Inativos Totais (Zero Ataques)
            zero_text = ""
            for m in zero_attacks:
                zero_text += f"🔴 {m['name']}\n"
            
            if zero_text:
                if len(zero_text) > 1000:
                    zero_text = zero_text[:950] + "\n... e outros."
                embed.add_field(name=f"🛑 Sangue-Sugas (0 Ataques) - {len(zero_attacks)} membros", value=zero_text, inline=False)
            else:
                embed.add_field(name="🛑 Sangue-Sugas", value="Incrível! Todos atacaram a capital.", inline=False)

            # Ataques Incompletos
            inc_text = ""
            for m in missed_some_attacks:
                inc_text += f"🟡 **{m['name']}** (Fez {m['attacks']}/{m['limit']})\n"
            
            if inc_text:
                if len(inc_text) > 1000:
                    inc_text = inc_text[:950] + "\n... e outros."
                embed.add_field(name="⚠️ Faltou Terminar", value=inc_text, inline=False)

            embed.set_footer(text=f"Auditoria ClashGenius | Total de Ataques: {raid['total_attacks']}")
            
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro no comando /capital: {e}", exc_info=True)
            await interaction.followup.send("❌ Ocorreu um erro catastrófico ao gerar a auditoria da capital.")

async def setup(bot: commands.Bot):
    await bot.add_cog(CapitalCog(bot))