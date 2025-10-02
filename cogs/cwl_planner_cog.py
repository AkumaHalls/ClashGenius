# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
from typing import Dict, List, Any, Optional

logger = logging.getLogger("cwl_planner_cog")

class CwlPlannerCog(commands.Cog, name="Planeador de CWL"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_client: coc.Client = self.bot.api_client 
        self.db = bot.db
        self.posted_daily_plans = set()
        self.posted_inactivity_alerts = set()

    async def cog_load(self):
        self.cwl_monitoring_task.start()

    async def cog_unload(self):
        self.cwl_monitoring_task.cancel()

    async def _send_planner_embed(self, embed: discord.Embed):
        if not self.bot.cwl_planner_channel_id: return
        try:
            channel = self.bot.get_channel(self.bot.cwl_planner_channel_id) or await self.bot.fetch_channel(self.bot.cwl_planner_channel_id)
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Falha ao enviar embed para o canal do planeador CWL: {e}")

    async def get_cwl_members_for_planning(self) -> Optional[List[Dict[str, Any]]]:
        try:
            await self.bot.coc_client_ready.wait()
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group:
                logger.warning("get_cwl_members_for_planning: O clã não parece estar em uma CWL.")
                return None

            our_clan_from_cwl = next((c for c in cwl_group.clans if c.tag == self.bot.clan_tag), None)
            
            if not our_clan_from_cwl:
                logger.warning("get_cwl_members_for_planning: Não foi possível encontrar o clã no grupo da CWL.")
                return None

            return [{"name": m.name, "tag": m.tag, "town_hall": m.town_hall} for m in our_clan_from_cwl.members]
        except coc.NotFound:
            logger.warning("get_cwl_members_for_planning: coc.NotFound - O clã não está em CWL.")
            return None
        except Exception as e:
            logger.error(f"Erro ao buscar membros da CWL para o planeamento: {e}", exc_info=True)
            return None

    async def generate_rotation_plan(self) -> Dict[str, Any]:
        cwl_members = await self.get_cwl_members_for_planning()
        if cwl_members is None:
            return {"error": "Não foi possível buscar os membros inscritos na CWL. O clã está em uma liga de guerra?"}

        if len(cwl_members) < 15:
            return {"error": "Não há membros suficientes (mínimo 15) na lista da CWL para gerar um plano."}
        
        clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
        current_member_tags = {m.tag for m in clan.members}
        
        db_cog = self.bot.get_cog("Banco de Dados")
        player_statuses = await db_cog.load_player_notes_from_db() if db_cog else {}
        
        active_players = []
        backup_players = []
        
        for member in cwl_members:
            if member['tag'] in current_member_tags:
                status = player_statuses.get(member['tag'], {}).get('cwl_status', 'active')
                if status == 'active':
                    active_players.append(member)
                else:
                    backup_players.append(member)

        active_players.sort(key=lambda p: p['town_hall'], reverse=True)
        backup_players.sort(key=lambda p: p['town_hall'], reverse=True)

        roster_size = 30 if len(cwl_members) >= 30 else 15
        
        schedule = []
        
        initial_roster = active_players[:roster_size]
        if len(initial_roster) < roster_size:
            needed = roster_size - len(initial_roster)
            initial_roster.extend(backup_players[:needed])

        bench = [p for p in active_players if p not in initial_roster] + [p for p in backup_players if p not in initial_roster]
        
        current_roster = initial_roster.copy()
        
        day_1_substitutions = []
        initial_roster_tags = {p['tag'] for p in initial_roster}
        left_tags_before_start = initial_roster_tags - current_member_tags
        
        for left_tag in left_tags_before_start:
            player_out = next((p for p in cwl_members if p['tag'] == left_tag), None)
            if player_out and bench:
                player_in = bench.pop(0)
                current_roster = [p for p in current_roster if p['tag'] != left_tag]
                current_roster.append(player_in)
                day_1_substitutions.append({
                    "out": player_out, "in": player_in,
                    "reason": "Membro saiu do clã antes do início e foi substituído."
                })

        schedule.append({
            "day": 1,
            "active_roster": sorted(current_roster, key=lambda p: p['town_hall'], reverse=True),
            "substitutions": day_1_substitutions
        })

        for day in range(2, 8):
            substitutions = []
            
            previous_roster_tags = {p['tag'] for p in schedule[-1]['active_roster']}
            newly_left_tags = previous_roster_tags - current_member_tags
            
            if newly_left_tags:
                for left_tag in newly_left_tags:
                    player_out = next((p for p in cwl_members if p['tag'] == left_tag), None)
                    if not player_out: continue

                    player_to_remove = next((p for p in current_roster if p['tag'] == left_tag), None)
                    if player_to_remove:
                        if bench:
                            player_in = bench.pop(0)
                            current_roster.remove(player_to_remove)
                            current_roster.append(player_in)
                            substitutions.append({
                                "out": player_out, "in": player_in,
                                "reason": "Membro saiu do clã e foi substituído."
                            })
                            logger.info(f"Substituição dinâmica no Dia {day}: {player_out['name']} (saiu) -> {player_in['name']} (entrou)")
                        else:
                            current_roster.remove(player_to_remove)
                            logger.warning(f"Jogador {player_out['name']} saiu, mas não há reservas. Escalação do Dia {day} ficará com um a menos.")
            
            if bench:
                temp_roster_for_rotation = sorted(current_roster, key=lambda p: p['town_hall'])
                
                for _ in range(3):
                    if not bench: break
                    
                    player_out = None
                    for p in temp_roster_for_rotation:
                        status = player_statuses.get(p['tag'], {}).get('cwl_status', 'active')
                        if status == 'active':
                            player_out = p
                            break
                    
                    if player_out is None and temp_roster_for_rotation:
                        player_out = temp_roster_for_rotation[0]
                    
                    if player_out:
                        player_in = bench.pop(0)
                        
                        current_roster = [p for p in current_roster if p['tag'] != player_out['tag']]
                        current_roster.append(player_in)
                        
                        temp_roster_for_rotation = [p for p in temp_roster_for_rotation if p['tag'] != player_out['tag']]

                        bench.append(player_out)
                        
                        substitutions.append({
                            "out": player_out, "in": player_in,
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
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()
        
        try:
            logger.info("Verificando status da CWL...")
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)

            # Limpa o cache se a CWL terminou ou está em preparação para uma nova
            if not cwl_group or cwl_group.state in ("warEnded", "preparation"):
                if self.posted_daily_plans:
                    logger.info("CWL não está em guerra. Limpando cache de planos postados.")
                    self.posted_daily_plans.clear()
                    self.posted_inactivity_alerts.clear()
                return
            
            # Se o estado é 'inWar', prossegue com a lógica
            if cwl_group.state == "inWar":
                active_war = None
                async for war in cwl_group.get_wars(self.bot.clan_tag):
                    if war.state == "inWar":
                        active_war = war
                        break
                
                if not active_war:
                    logger.warning("Estado do grupo é 'inWar', mas nenhuma guerra ativa foi encontrada.")
                    return

                day_number = -1
                for i, round_war_tags in enumerate(cwl_group.rounds):
                    if active_war.tag in round_war_tags:
                        day_number = i + 1
                        break
                
                if day_number == -1:
                    logger.error(f"Não foi possível determinar o dia da CWL para a guerra ativa {active_war.tag}.")
                    return
                
                logger.info(f"Guerra ativa encontrada: Dia {day_number} vs {active_war.opponent.name}.")
                await self.post_daily_plan_if_needed(active_war, cwl_group.season, day_number)
                await self.check_and_alert_inactivity(active_war)

        except coc.NotFound:
            if self.posted_daily_plans:
                logger.info("Clã não está em CWL (coc.NotFound). Limpando cache.")
                self.posted_daily_plans.clear()
                self.posted_inactivity_alerts.clear()
        except Exception as e:
            logger.error(f"Erro na tarefa de monitorização da CWL: {e}", exc_info=True)

    async def post_daily_plan_if_needed(self, war: coc.ClanWar, season: str, day_number: int):
        war_tag_id = war.tag
        if war_tag_id in self.posted_daily_plans:
            logger.info(f"Plano para o Dia {day_number} (guerra {war_tag_id}) já foi postado. Ignorando.")
            return

        logger.info(f"Postando plano para o Dia {day_number} (guerra {war_tag_id})...")
        
        plan_data = await self.generate_rotation_plan()
        if "error" in plan_data: 
            logger.error(f"Erro ao gerar plano de rotação: {plan_data['error']}")
            return

        current_day_plan = next((p for p in plan_data["schedule"] if p["day"] == day_number), None)
        
        if not current_day_plan: 
            logger.warning(f"Nenhum plano encontrado no cronograma para o Dia {day_number}.")
            return
        
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
            default_message = "Manter a escalação do dia anterior." if day_number > 1 else "Escalação inicial definida. Vamos com tudo!"
            embed.add_field(name="🔄 Alterações na Equipa", value=default_message, inline=False)
        
        if opponent.badge:
            embed.set_thumbnail(url=opponent.badge.url)

        await self._send_planner_embed(embed)
        self.posted_daily_plans.add(war_tag_id)
        logger.info(f"Plano para o Dia {day_number} enviado e tag {war_tag_id} adicionada ao cache.")

    async def check_and_alert_inactivity(self, war: coc.ClanWar):
        time_left = war.end_time.seconds_until
        if not (15 * 60 < time_left < 4 * 3600): return

        our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
        inactive_members = [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member]

        if not inactive_members: return

        alert_id = f"{war.tag}-inactivity"
        if alert_id in self.posted_inactivity_alerts: return
            
        logger.warning(f"Detectando inatividade na CWL. {len(inactive_members)} membros ainda não atacaram.")

        hours, remainder = divmod(int(time_left), 3600)
        minutes, _ = divmod(remainder, 60)
        time_left_str = f"{hours}h e {minutes}m"

        embed = discord.Embed(
            title=f"🚨 ALERTA DE INATIVIDADE NA CWL!",
            description=f"A guerra contra **{war.opponent.name}** termina em aproximadamente **{time_left_str}**!",
            color=discord.Color.red()
        )
        inactive_str = "\n".join([f"**{m.name}** (CV{m.town_hall})" for m in inactive_members])
        embed.add_field(name="Jogadores com Ataques Pendentes", value=inactive_str, inline=False)
        embed.set_footer(text="É crucial que todos os ataques sejam feitos para não comprometer o resultado!")
        
        if war.opponent.badge:
            embed.set_thumbnail(url=war.opponent.badge.url)

        await self._send_planner_embed(embed)
        self.posted_inactivity_alerts.add(alert_id)

    @tasks.loop(count=1)
    async def before_cwl_monitoring_task(self):
        await self.bot.wait_until_ready()

    # NOVO COMANDO MANUAL PARA DEBUG
    @commands.command(name='forcarplano', aliases=['forceplan'])
    @commands.has_permissions(administrator=True)
    async def force_plan_command(self, ctx: commands.Context):
        """(Admin) Força a verificação e postagem do plano de CWL do dia atual."""
        await ctx.message.add_reaction("🔄")
        logger.info(f"Comando !forcarplano invocado por {ctx.author.name}.")
        
        # Roda a mesma lógica da task, mas manualmente
        try:
            self.posted_daily_plans.clear() # Limpa o cache para garantir que poste
            await self.cwl_monitoring_task.func(self)
            await ctx.message.add_reaction("✅")
            await ctx.message.remove_reaction("🔄", self.bot.user)
        except Exception as e:
            await ctx.message.add_reaction("❌")
            await ctx.message.remove_reaction("🔄", self.bot.user)
            await ctx.send(f"Ocorreu um erro ao forçar o plano: `{e}`")
            logger.error(f"Erro ao executar !forcarplano: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    if bot.cwl_planner_channel_id:
        await bot.add_cog(CwlPlannerCog(bot))
    else:
        logger.warning("Cog 'CwlPlannerCog' não carregado (ID do canal não configurado).")

