# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
from typing import Dict, List, Any, Optional

logger = logging.getLogger("cwl_planner_cog")

class CwlPlannerCog(commands.Cog, name="Planeador de CWL"):
    """
    Cog para gerir toda a lógica do Planeador Estratégico de CWL.
    Este módulo é responsável por analisar os membros, gerar o plano de 7 dias,
    e monitorizar a inatividade e o plano diário durante a guerra.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # A referência ao api_client será usada APÓS a confirmação de que ele está pronto.
        self.api_client: coc.Client = self.bot.api_client 
        self.db = bot.db
        self.posted_daily_plans = set() # Para evitar posts duplicados
        self.posted_inactivity_alerts = set() # Para evitar alertas duplicados

    async def cog_load(self):
        """Inicia as tarefas em segundo plano quando o cog é carregado."""
        self.cwl_monitoring_task.start()

    async def cog_unload(self):
        """Para as tarefas quando o cog é descarregado."""
        self.cwl_monitoring_task.cancel()

    async def _send_planner_embed(self, embed: discord.Embed):
        """Envia um embed para o canal configurado do planeador CWL."""
        if not self.bot.cwl_planner_channel_id: return
        try:
            channel = self.bot.get_channel(self.bot.cwl_planner_channel_id) or await self.bot.fetch_channel(self.bot.cwl_planner_channel_id)
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Falha ao enviar embed para o canal do planeador CWL: {e}")

    async def get_cwl_members_for_planning(self) -> List[Dict[str, Any]]:
        """Busca e ordena os membros que estão na CWL."""
        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group:
                logger.warning("Tentativa de buscar membros da CWL, mas o clã não está em uma.")
                return []
            
            our_clan_in_cwl = cwl_group.get_clan(self.bot.clan_tag)
            if not our_clan_in_cwl or not our_clan_in_cwl.members:
                logger.warning("Não foi possível encontrar os membros do nosso clã no grupo da CWL.")
                return []

            sorted_members = sorted(our_clan_in_cwl.members, key=lambda m: m.town_hall, reverse=True)
            return [{"name": m.name, "tag": m.tag, "town_hall": m.town_hall} for m in sorted_members]
        except coc.NotFound:
             logger.info("O clã não está atualmente em uma CWL.")
             return []
        except Exception as e:
            logger.error(f"Erro ao buscar membros da CWL para o planeamento: {e}")
            return []

    async def generate_rotation_plan(self) -> Dict[str, Any]:
        """Gera o plano de rotação completo para os 7 dias de CWL."""
        await self.bot.coc_client_ready.wait()  # GARANTE QUE O CLIENTE COC ESTÁ PRONTO
        
        cwl_members = await self.get_cwl_members_for_planning()
        
        if not cwl_members:
            return {"error": "Não foi possível buscar os membros inscritos na CWL. O clã está em uma liga de guerra?"}
        
        if len(cwl_members) < 15:
            return {"error": "Não há membros suficientes (mínimo 15) inscritos na CWL para criar um plano."}

        roster_size = 30 if len(cwl_members) >= 30 else 15
        initial_roster = cwl_members[:roster_size]
        bench = cwl_members[roster_size:]
        
        schedule = []
        current_roster = initial_roster.copy()
        
        for day in range(1, 8):
            substitutions = []
            if bench and day > 1:
                current_roster.sort(key=lambda p: p['town_hall'], reverse=True)
                num_subs = min(3, len(bench), len(current_roster))
                players_out = current_roster[-num_subs:]
                players_in = bench[:num_subs]
                
                current_roster = current_roster[:-num_subs]
                current_roster.extend(players_in)
                bench = bench[num_subs:]
                bench.extend(players_out)

                for i in range(num_subs):
                    substitutions.append({
                        "out": players_out[i],
                        "in": players_in[i],
                        "reason": f"Rotação para maximizar medalhas e participação."
                    })

            schedule.append({
                "day": day,
                "active_roster": sorted(current_roster, key=lambda p: p['town_hall'], reverse=True),
                "substitutions": substitutions
            })

        return {
            "summary": f"Plano de rotação para {len(cwl_members)} membros numa CWL {roster_size}x{roster_size}.",
            "schedule": schedule
        }

    @tasks.loop(minutes=15)
    async def cwl_monitoring_task(self):
        """Tarefa principal que monitoriza a CWL e envia os alertas necessários."""
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()
        
        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group or cwl_group.state != "inWar":
                self.posted_daily_plans.clear()
                self.posted_inactivity_alerts.clear()
                return

            our_clan_info = cwl_group.get_clan(self.bot.clan_tag)
            if not our_clan_info: return

            active_war = None
            for war_tag in cwl_group.get_wars_for_clan(self.bot.clan_tag):
                war = await self.bot.api_client.get_league_war(war_tag)
                if war.state == "inWar":
                    active_war = war
                    break
            
            if not active_war: return

            await self.post_daily_plan_if_needed(active_war, cwl_group.season)
            await self.check_and_alert_inactivity(active_war)

        except coc.NotFound:
            self.posted_daily_plans.clear()
            self.posted_inactivity_alerts.clear()
        except Exception as e:
            logger.error(f"Erro na tarefa de monitorização da CWL: {e}", exc_info=True)

    async def post_daily_plan_if_needed(self, war: coc.ClanWar, season: str):
        """Verifica se o plano para a guerra atual já foi postado e, se não, posta."""
        war_id = war.end_time.time.day
        if war_id in self.posted_daily_plans:
            return

        logger.info(f"Nova guerra da CWL detetada (dia {war_id}). A gerar e postar o plano diário.")
        
        plan_data = await self.generate_rotation_plan()
        if "error" in plan_data: return

        current_day_plan = next((p for p in plan_data["schedule"] if len(self.posted_daily_plans) < p["day"]), None)
        if not current_day_plan: return
        
        day_number = current_day_plan["day"]
        opponent = war.opponent if war.clan.tag == self.bot.clan_tag else war.clan

        embed = discord.Embed(
            title=f"📋 Plano Estratégico CWL - Dia {day_number} vs {opponent.name}",
            description=f"Temporada: {season}. Foco total para garantir a vitória!",
            color=discord.Color.blue()
        )
        
        roster_str = "\n".join([f"`{i+1:02d}.` {p['name']} (CV{p['town_hall']})" for i, p in enumerate(current_day_plan["active_roster"])])
        embed.add_field(name="⚔️ Escalação Ativa para Hoje", value=roster_str or "N/A", inline=False)

        if current_day_plan["substitutions"]:
            subs_str = ""
            for sub in current_day_plan["substitutions"]:
                subs_str += f"🔴 **Sai:** {sub['out']['name']} (CV{sub['out']['town_hall']})\n"
                subs_str += f"🟢 **Entra:** {sub['in']['name']} (CV{sub['in']['town_hall']})\n"
                subs_str += f"_*Motivo: {sub['reason']}_*\n\n"
            embed.add_field(name="🔄 Alterações na Equipa", value=subs_str, inline=False)
        else:
            embed.add_field(name="🔄 Alterações na Equipa", value="A mesma escalação do dia anterior. Vamos com tudo!", inline=False)
        
        if opponent.badge:
            embed.set_thumbnail(url=opponent.badge.url)

        await self._send_planner_embed(embed)
        self.posted_daily_plans.add(war_id)

    async def check_and_alert_inactivity(self, war: coc.ClanWar):
        """Verifica jogadores inativos e envia um alerta se necessário."""
        time_left = war.end_time.seconds_until
        if not (15 * 60 < time_left < 4 * 3600):
            return

        our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
        inactive_members = [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member]

        if not inactive_members:
            return

        alert_id = f"{war.end_time.time.day}-{len(inactive_members)}"
        if alert_id in self.posted_inactivity_alerts:
            return
            
        logger.warning(f"A detetar inatividade na guerra da CWL. {len(inactive_members)} membros ainda não atacaram.")

        hours, remainder = divmod(int(time_left), 3600)
        minutes, _ = divmod(remainder, 60)
        time_left_str = f"{hours}h e {minutes}m"

        embed = discord.Embed(
            title=f"🚨 ALERTA DE INATIVIDADE NA CWL!",
            description=f"A guerra contra **{war.opponent.name}** termina em aproximadamente **{time_left_str}**!",
            color=discord.Color.red()
        )

        inactive_str = "\n".join([f"**{m.name}** (CV{m.town_hall})" for m in inactive_members])
        embed.add_field(
            name="Jogadores com Ataques Pendentes",
            value=inactive_str,
            inline=False
        )
        embed.set_footer(text="É crucial que todos os ataques sejam feitos para não comprometer o resultado!")
        
        if war.opponent.badge:
            embed.set_thumbnail(url=war.opponent.badge.url)

        await self._send_planner_embed(embed)
        self.posted_inactivity_alerts.add(alert_id)

    @cwl_monitoring_task.before_loop
    async def before_cwl_monitoring_task(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    # Só carrega o cog se o ID do canal estiver configurado
    if bot.cwl_planner_channel_id:
        await bot.add_cog(CwlPlannerCog(bot))
    else:
        logger.warning("Cog 'CwlPlannerCog' não carregado (ID do canal não configurado).")

