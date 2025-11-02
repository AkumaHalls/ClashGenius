# -*- coding: utf-8 -*-3
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
from typing import Dict, List, Any, Optional
import datetime  # Importado
import pytz      # Importado

logger = logging.getLogger("cwl_planner_cog")

class CwlPlannerCog(commands.Cog, name="Planeador de CWL"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_client: coc.Client = self.bot.api_client 
        self.db = bot.db
        # Coleção para salvar o plano da temporada
        self.cwl_plan_collection = self.db.cwl_plan if self.db is not None else None
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

    async def _get_current_cwl_war_info(self) -> Optional[Dict[str, Any]]:
        """
        Busca a guerra ativa, o dia atual e a temporada da CWL.
        Refatorado da cwl_monitoring_task.
        """
        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group or cwl_group.state != "inWar":
                return None # Não está em CWL ou não está em período de guerra

            active_war = None
            day_number = -1
            active_war_tag = None # <<< ADICIONADO: Variável para guardar o war_tag
            
            for i, round_war_tags in enumerate(cwl_group.rounds):
                for war_tag in round_war_tags:
                    if war_tag == '#0': continue
                    try:
                        war = await self.bot.api_client.get_league_war(war_tag)
                        # Verifica se é a nossa guerra
                        if war.clan.tag == self.bot.clan_tag or war.opponent.tag == self.bot.clan_tag:
                            if war.state == 'inWar':
                                active_war = war
                                day_number = i + 1
                                active_war_tag = war_tag # <<< ADICIONADO: Guarda o war_tag
                                break
                    except coc.NotFound:
                        continue
                if active_war:
                    break

            if active_war:
                return {
                    "active_war": active_war,
                    "day_number": day_number,
                    "season": cwl_group.season,
                    "war_tag": active_war_tag # <<< ADICIONADO: Retorna o war_tag
                }
            
            logger.warning("CWL state é 'inWar' mas nenhuma guerra ativa foi encontrada.")
            return None # Está em CWL, mas talvez entre as guerras

        except coc.NotFound:
            return None # Não está em CWL
        except Exception as e:
            logger.error(f"Erro ao buscar _get_current_cwl_war_info: {e}", exc_info=True)
            return None

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

    async def _generate_new_7_day_plan(self) -> Dict[str, Any]:
        """
        Lógica original de geração de plano, agora refatorada.
        Gera um plano de 7 dias do zero.
        """
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
            # Só considera jogadores que AINDA estão no clã para o plano inicial
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

        # Banco são todos que sobraram
        bench = [p for p in active_players if p not in initial_roster] + [p for p in backup_players if p not in initial_roster]
        
        current_roster = initial_roster.copy()
        
        # Plano do Dia 1
        schedule.append({
            "day": 1,
            "active_roster": sorted(current_roster, key=lambda p: p['town_hall'], reverse=True),
            "substitutions": [] # Nenhuma substituição no dia 1
        })

        # Gera rotação para os dias 2-7
        for day in range(2, 8):
            substitutions = []
            
            # Tira os 3 mais fracos (que são 'active') e coloca 3 do banco
            if bench:
                # Ordena o roster atual por CV (do mais fraco ao mais forte)
                temp_roster_for_rotation = sorted(current_roster, key=lambda p: p['town_hall'])
                
                players_out_count = 0
                players_out_tags = set()

                # Tenta tirar 3 jogadores "active"
                for player_out in temp_roster_for_rotation:
                    if players_out_count >= 3: break
                    status = player_statuses.get(player_out['tag'], {}).get('cwl_status', 'active')
                    if status == 'active': # Só tira quem é 'active'
                        player_in = bench.pop(0) # Pega o primeiro do banco
                        
                        # Tira o 'player_out' do roster e adiciona o 'player_in'
                        # (current_roster é atualizado via 'players_out_tags' no final)
                        players_out_tags.add(player_out['tag'])
                        current_roster.append(player_in) 
                        
                        bench.append(player_out) # Devolve o 'player_out' para o fim do banco
                        
                        substitutions.append({
                            "out": player_out, "in": player_in,
                            "reason": f"Rotação automática do Dia {day}."
                        })
                        players_out_count += 1
                        
                        if not bench: break # Acabou o banco

                # Atualiza o roster principal
                current_roster = [p for p in current_roster if p['tag'] not in players_out_tags]

            schedule.append({
                "day": day,
                "active_roster": sorted(current_roster, key=lambda p: p['town_hall'], reverse=True),
                "substitutions": substitutions
            })

        return {
            "summary": f"Plano de rotação para {len(cwl_members)} membros ({roster_size}x{roster_size}).",
            "schedule": schedule,
            "bench": bench # Salva o banco de reservas
        }

    async def _update_existing_plan(self, plan_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Carrega um plano existente e o ATUALIZA com base em jogadores que saíram.
        """
        logger.info("Atualizando plano de CWL existente...")
        schedule = plan_doc['schedule']
        bench = plan_doc['bench']
        warning = plan_doc.get('warning') # Carrega aviso antigo, se houver

        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            current_member_tags = {m.tag for m in clan.members}
            info = await self._get_current_cwl_war_info()
            current_day = info['day_number'] if info else 1

            # Banco de reservas VÁLIDO (jogadores que ainda estão no clã)
            available_bench = [p for p in bench if p['tag'] in current_member_tags]
            # Ordena por CV (mais forte primeiro) para garantir a melhor substituição
            available_bench.sort(key=lambda p: p['town_hall'], reverse=True) 

            new_schedule = []
            
            # Itera por todos os dias do plano
            for day_plan in schedule:
                # Não altera o passado
                if day_plan['day'] < current_day:
                    new_schedule.append(day_plan)
                    continue

                # Dia atual ou futuro: Verifica o roster
                current_roster = day_plan['active_roster']
                new_roster_for_this_day = []
                substitutions_for_this_day = day_plan.get('substitutions', [])
                roster_changed_this_day = False

                for player in current_roster:
                    # Se o jogador está no clã, ele permanece
                    if player['tag'] in current_member_tags:
                        new_roster_for_this_day.append(player)
                        continue

                    # JOGADOR SAIU/BANIDO! Tenta substituir.
                    roster_changed_this_day = True
                    replacement = None

                    if available_bench:
                        replacement = available_bench.pop(0) # Pega o reserva mais forte
                        
                        # Atualiza o banco principal (remove o substituto, adiciona o que saiu)
                        bench = [p for p in bench if p['tag'] != replacement['tag']]
                        bench.append(player) 
                        
                        new_roster_for_this_day.append(replacement)
                        sub_reason = f"Subst. (Dia {current_day}): {player['name']} saiu."
                        substitutions_for_this_day.append({"out": player, "in": replacement, "reason": sub_reason})
                        logger.info(f"CWL Dia {day_plan['day']}: {player['name']} substituído por {replacement['name']}.")
                    else:
                        # Não há substitutos!
                        new_roster_for_this_day.append(player) # Mantém o jogador que saiu (não há o que fazer)
                        warning = "Atenção: Jogadores saíram mas não há substitutos no banco!"
                        logger.warning(f"CWL Dia {day_plan['day']}: {player['name']} saiu, mas SEM substitutos!")

                # Se o roster mudou, atualiza o plano do dia
                if roster_changed_this_day:
                    day_plan['active_roster'] = new_roster_for_this_day
                    day_plan['substitutions'] = substitutions_for_this_day
                
                new_schedule.append(day_plan)

            logger.info("Atualização do plano concluída.")
            return {"schedule": new_schedule, "bench": bench, "warning": warning}

        except Exception as e:
            logger.error(f"Erro crítico ao ATUALIZAR plano de CWL: {e}", exc_info=True)
            return {"schedule": schedule, "bench": bench, "warning": f"Erro ao atualizar: {e}"}


    async def generate_rotation_plan(self) -> Dict[str, Any]:
        """
        Função principal da API. Decide se deve criar um novo plano ou atualizar um existente.
        """
        if self.cwl_plan_collection is None:
            return {"error": "O banco de dados não está configurado para salvar o plano."}

        info = await self._get_current_cwl_war_info()
        if not info:
            return {"error": "O clã não está em uma guerra CWL ativa no momento."}

        season = info['season']
        
        try:
            plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
            
            if plan_doc is None:
                # 1. NÃO HÁ PLANO: Gera um novo e salva
                logger.info(f"Gerando novo plano de CWL para a temporada {season}...")
                plan_data = await self._generate_new_7_day_plan()
                
                if "error" in plan_data:
                    return plan_data # Retorna o erro
                
                # Salva o plano novo no DB
                await self.cwl_plan_collection.update_one(
                    {"_id": season},
                    {"$set": {
                        "schedule": plan_data['schedule'], 
                        "bench": plan_data['bench'],
                        "last_updated": datetime.datetime.now(pytz.utc)
                    }},
                    upsert=True
                )
                logger.info(f"Novo plano para {season} salvo no DB.")
                return plan_data
            
            else:
                # 2. PLANO EXISTE: Carrega e ATUALIZA
                logger.info(f"Carregando e atualizando plano existente para {season}...")
                plan_data = await self._update_existing_plan(plan_doc)
                
                # Salva o plano atualizado no DB
                await self.cwl_plan_collection.update_one(
                    {"_id": season},
                    {"$set": {
                        "schedule": plan_data['schedule'], 
                        "bench": plan_data['bench'], 
                        "warning": plan_data.get('warning'),
                        "last_updated": datetime.datetime.now(pytz.utc)
                    }}
                )
                logger.info(f"Plano para {season} atualizado no DB.")
                return plan_data

        except Exception as e:
            logger.error(f"Erro fatal em generate_rotation_plan: {e}", exc_info=True)
            return {"error": f"Erro fatal ao processar o plano: {e}"}

    @tasks.loop(minutes=15)
    async def cwl_monitoring_task(self):
        await self.bot.wait_until_ready()
        await self.bot.coc_client_ready.wait()
        
        try:
            logger.info("Verificando status da CWL (lógica robusta)...")
            info = await self._get_current_cwl_war_info()

            if not info:
                if self.posted_daily_plans:
                    logger.info("CWL não está em guerra. Limpando cache de planos postados.")
                    self.posted_daily_plans.clear()
                    self.posted_inactivity_alerts.clear()
                return
            
            active_war = info['active_war']
            day_number = info['day_number']
            season = info['season']
            active_war_tag_str = info['war_tag'] # <<< CORRIGIDO: Usa o 'war_tag' retornado por info

            # Verificação de segurança caso 'war_tag' não seja retornado
            if not active_war_tag_str:
                 logger.error("cwl_monitoring_task: _get_current_cwl_war_info não retornou um 'war_tag'.")
                 return

            logger.info(f"Guerra ativa encontrada: Dia {day_number} vs {active_war.opponent.name}.")
            await self.post_daily_plan_if_needed(active_war, active_war_tag_str, season, day_number)
            await self.check_and_alert_inactivity(active_war, active_war_tag_str) # <<< MODIFICADO: Passa o war_tag_str

        except Exception as e:
            logger.error(f"Erro na tarefa de monitorização da CWL: {e}", exc_info=True)

    async def post_daily_plan_if_needed(self, war: coc.ClanWar, war_tag_id: str, season: str, day_number: int):
        if war_tag_id in self.posted_daily_plans:
            logger.info(f"Plano para o Dia {day_number} (guerra {war_tag_id}) já foi postado. Ignorando.")
            return

        logger.info(f"Postando plano para o Dia {day_number} (guerra {war_tag_id})...")
        
        # Usa a nova função que carrega/atualiza
        plan_data = await self.generate_rotation_plan() 
        if "error" in plan_data: 
            logger.error(f"Erro ao gerar plano de rotação para postagem: {plan_data['error']}")
            # Não posta se deu erro (ex: não está em CWL)
            if "não está em uma guerra CWL ativa" in plan_data['error']:
                 self.posted_daily_plans.add(war_tag_id) # Evita tentar de novo
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
        
        # Adiciona o aviso se houver um
        if plan_data.get("warning"):
             embed.add_field(name="⚠️ Aviso da IA", value=plan_data["warning"], inline=False)

        if opponent.badge:
            embed.set_thumbnail(url=opponent.badge.url)

        await self._send_planner_embed(embed)
        self.posted_daily_plans.add(war_tag_id)
        logger.info(f"Plano para o Dia {day_number} enviado e tag {war_tag_id} adicionada ao cache.")

    async def check_and_alert_inactivity(self, war: coc.ClanWar, war_tag_id: str): # <<< MODIFICADO: Recebe war_tag_id
        time_left = war.end_time.seconds_until
        if not (15 * 60 < time_left < 4 * 3600): return

        our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
        inactive_members = [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member]

        if not inactive_members: return

        alert_id = f"{war_tag_id}-inactivity" # <<< CORRIGIDO: Usa war_tag_id
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

    @commands.command(name='forcarplano', aliases=['forceplan'])
    @commands.has_permissions(administrator=True)
    async def force_plan_command(self, ctx: commands.Context):
        """(Admin) Força a verificação e postagem do plano de CWL do dia atual."""
        await ctx.message.add_reaction("🔄")
        logger.info(f"Comando !forcarplano invocado por {ctx.author.name}.")
        
        try:
            self.posted_daily_plans.clear() 
            # Chama a task principal, que agora usa o helper
            await self.cwl_monitoring_task.coro(self) 
            
            await ctx.message.add_reaction("✅")
            await ctx.message.remove_reaction("🔄", self.bot.user)
        except Exception as e:
            await ctx.message.add_reaction("❌")
            await ctx.message.remove_reaction("🔄", self.bot.user)
            await ctx.send(f"Ocorreu um erro ao forçar o plano: `{e}`")
            logger.error(f"Erro ao executar !forcarplano: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    # Adiciona verificação do DB, pois o cwl_plan_collection é necessário
    if bot.cwl_planner_channel_id and bot.db is not None:
        await bot.add_cog(CwlPlannerCog(bot))
    else:
        logger.warning("Cog 'CwlPlannerCog' não carregado (ID do canal ou DB não configurado).")
