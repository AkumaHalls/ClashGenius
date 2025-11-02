# -*- coding: utf-8 -*-3
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
from typing import Dict, List, Any, Optional
import datetime  # Importado
import pytz      # Importado
import math      # Importado

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

    # <<< INÍCIO DA REFORMULAÇÃO (Melhorias 1, 3, 4) >>>
    async def _generate_new_7_day_plan(self) -> Dict[str, Any]:
        """
        Lógica "CÉREBRO" (v2) de geração de plano.
        Gera um plano de 7 dias com rotação justa, priorizando "ativos"
        e usando "backups" apenas como último recurso.
        """
        logger.info("Iniciando geração de plano 'Cérebro' v2...")
        
        cwl_members_list = await self.get_cwl_members_for_planning()
        if cwl_members_list is None:
            return {"error": "Não foi possível buscar os membros inscritos na CWL. O clã está em uma liga de guerra?"}
        
        # Mapeia tags para dados para fácil acesso
        cwl_members_map = {m['tag']: m for m in cwl_members_list}

        if len(cwl_members_list) < 15:
            return {"error": "Não há membros suficientes (mínimo 15) na lista da CWL para gerar um plano."}
        
        clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
        current_member_tags = {m.tag for m in clan.members}
        
        db_cog = self.bot.get_cog("Banco de Dados")
        player_statuses = await db_cog.load_player_notes_from_db() if db_cog else {}
        
        active_players = []
        backup_players = []
        
        # 1. Separa jogadores por status (Ativo/Backup)
        for tag, member_data in cwl_members_map.items():
            # Só considera jogadores que AINDA estão no clã
            if tag in current_member_tags:
                status = player_statuses.get(tag, {}).get('cwl_status', 'active')
                if status == 'active':
                    active_players.append(member_data)
                else:
                    backup_players.append(member_data)

        if not active_players:
             return {"error": "Não há jogadores marcados como 'Ativo' no clã para gerar um plano."}

        # Ordena ambas as listas por CV (mais forte primeiro)
        active_players.sort(key=lambda p: p['town_hall'], reverse=True)
        backup_players.sort(key=lambda p: p['town_hall'], reverse=True)
        
        # Mapeamento de tags para nomes (para o placar)
        all_active_players_map = {p['tag']: p['name'] for p in active_players}

        roster_size = 15 # Fixo em 15 para simplificar a rotação
        num_to_rotate = 3 # Quantos rodam por dia
        
        schedule = []
        
        # 2. Cria escalação inicial e bancos de reservas
        initial_roster = active_players[:roster_size]
        
        # Fila de Ativos (jogadores "ativos" que começam no banco)
        banco_ativos_queue = active_players[roster_size:]
        
        # Fila de Backups (só usados em último caso)
        banco_backups_queue = backup_players[:]
        
        # Completa a escalação inicial se faltarem "ativos"
        needed = roster_size - len(initial_roster)
        if needed > 0:
            logger.warning(f"Menos de {roster_size} jogadores 'ativos'. Completando com backups...")
            backups_to_add = banco_backups_queue[:needed]
            initial_roster.extend(backups_to_add)
            # Remove os backups usados da fila de backups
            banco_backups_queue = banco_backups_queue[needed:]

        # 3. Prepara o "Placar de Participação" (Melhoria 3)
        # Começa com 0 para todos os ativos, 1 para quem começa jogando
        participation_count = {p['tag']: 0 for p in active_players}
        for p in initial_roster:
             if p['tag'] in participation_count: # Só conta se for "ativo"
                participation_count[p['tag']] = 1

        current_roster = initial_roster
        
        # 4. Loop de Rotação (Dias 1 a 7)
        for day in range(1, 8):
            substitutions = []
            
            # A rotação só acontece a partir do Dia 2
            if day > 1:
                # 4a. Identifica quem sai
                # Ordena os "ativos" da escalação atual por:
                # 1. Mais dias jogados (desc)
                # 2. CV mais fraco (asc)
                players_out_candidates = [
                    p for p in current_roster 
                    if p['tag'] in participation_count # Filtra apenas "ativos"
                ]
                players_out_candidates.sort(
                    key=lambda p: (participation_count[p['tag']], -p['town_hall']), 
                    reverse=True
                )
                
                players_to_remove = players_out_candidates[:num_to_rotate]
                
                # 4b. Identifica quem entra
                players_to_add = []
                num_needed = len(players_to_remove)
                
                for _ in range(num_needed):
                    if banco_ativos_queue: # Prioridade 1: Fila de Ativos
                        player_in = banco_ativos_queue.pop(0)
                        players_to_add.append(player_in)
                    elif banco_backups_queue: # Prioridade 2: Fila de Backups (Último caso)
                        logger.warning(f"Dia {day}: Fila de ativos vazia. Usando backup.")
                        player_in = banco_backups_queue.pop(0)
                        players_to_add.append(player_in)
                    else:
                        logger.warning(f"Dia {day}: Fim das filas de rotação.")
                        break # Ninguém mais para adicionar
                
                # 4c. Realiza a troca
                new_roster = [p for p in current_roster if p not in players_to_remove]
                new_roster.extend(players_to_add)

                # 4d. Atualiza as filas e o placar
                for p_out, p_in in zip(players_to_remove, players_to_add):
                    substitutions.append({
                        "out": p_out, "in": p_in,
                        "reason": f"Rotação justa (Sai: {p_out['name']}, Entra: {p_in['name']})"
                    })
                    
                    # Devolve o jogador que saiu para o fim da sua fila apropriada
                    if p_out['tag'] in all_active_players_map:
                        banco_ativos_queue.append(p_out)
                    else:
                        banco_backups_queue.append(p_out)
                
                current_roster = new_roster
                
                # Atualiza o placar de participação
                for p in current_roster:
                    if p['tag'] in participation_count: # Só conta "ativos"
                        participation_count[p['tag']] += 1
            
            # 4e. Salva o plano do dia
            schedule.append({
                "day": day,
                "active_roster": sorted(current_roster, key=lambda p: p['town_hall'], reverse=True),
                "substitutions": substitutions
            })

        logger.info(f"Plano v2 gerado. Placar final: {participation_count}")
        
        return {
            "schedule": schedule,
            "participation_count": participation_count, # Melhoria 3
            "banco_ativos": banco_ativos_queue,       # Melhoria 4
            "banco_backups": banco_backups_queue,      # Melhoria 4
            "all_active_players_map": all_active_players_map, # Helper para UI
            "summary": f"Plano de rotação para {len(active_players)} ativos e {len(backup_players)} backups."
        }
    # <<< FIM DA REFORMULAÇÃO >>>

    async def _update_existing_plan(self, plan_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Carrega um plano existente e o ATUALIZA com base em jogadores que saíram.
        (v2 - Simplificado: Apenas verifica saídas e tenta substituir)
        """
        logger.info("Atualizando plano de CWL existente...")
        schedule = plan_doc.get('schedule', [])
        banco_ativos = plan_doc.get('banco_ativos', [])
        banco_backups = plan_doc.get('banco_backups', [])
        participation_count = plan_doc.get('participation_count', {})
        all_active_players_map = plan_doc.get('all_active_players_map', {})
        warning = plan_doc.get('warning') # Carrega aviso antigo, se houver

        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            current_member_tags = {m.tag for m in clan.members}
            info = await self._get_current_cwl_war_info()
            current_day = info['day_number'] if info else 1

            # Bancos de reservas VÁLIDOS (jogadores que ainda estão no clã)
            available_bench_ativos = [p for p in banco_ativos if p['tag'] in current_member_tags]
            available_bench_backups = [p for p in banco_backups if p['tag'] in current_member_tags]
            
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

                    if available_bench_ativos:
                        replacement = available_bench_ativos.pop(0)
                        banco_ativos = [p for p in banco_ativos if p['tag'] != replacement['tag']]
                    elif available_bench_backups:
                        replacement = available_bench_backups.pop(0)
                        banco_backups = [p for p in banco_backups if p['tag'] != replacement['tag']]
                    
                    if replacement:
                        # Adiciona o substituto ao roster
                        new_roster_for_this_day.append(replacement)
                        # Adiciona o jogador que saiu ao fim da sua fila (para manter a lógica)
                        if player['tag'] in all_active_players_map:
                             banco_ativos.append(player)
                        else:
                             banco_backups.append(player)
                        
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
                    day_plan['active_roster'] = sorted(new_roster_for_this_day, key=lambda p: p['town_hall'], reverse=True)
                    day_plan['substitutions'] = substitutions_for_this_day
                
                new_schedule.append(day_plan)

            logger.info("Atualização do plano concluída.")
            return {
                "schedule": new_schedule, 
                "banco_ativos": banco_ativos,
                "banco_backups": banco_backups,
                "participation_count": participation_count,
                "all_active_players_map": all_active_players_map,
                "warning": warning
            }

        except Exception as e:
            logger.error(f"Erro crítico ao ATUALIZAR plano de CWL: {e}", exc_info=True)
            # Retorna o plano antigo em caso de erro
            return plan_doc


    async def generate_rotation_plan(self) -> Dict[str, Any]:
        """
        Função principal da API (v2).
        Decide se deve criar um novo plano (v2) ou atualizar um existente (v2).
        """
        if self.cwl_plan_collection is None:
            return {"error": "O banco de dados não está configurado para salvar o plano."}

        info = await self._get_current_cwl_war_info()
        if not info:
            return {"error": "O clã não está em uma guerra CWL ativa no momento."}

        season = info['season']
        
        try:
            plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
            
            # --- LÓGICA DE ATUALIZAÇÃO SIMPLIFICADA ---
            # Para garantir que a lógica "Cérebro" seja usada, forçamos a
            # recriação do plano se ele for de um formato antigo (sem 'participation_count')
            # ou se for o Dia 1 (para pegar novos membros que entraram).
            
            is_new_format = plan_doc and 'participation_count' in plan_doc
            is_day_one = info.get('day_number', 1) == 1

            if plan_doc is None or not is_new_format or is_day_one:
                # 1. GERA NOVO PLANO (v2)
                if is_day_one and is_new_format: logger.info(f"Dia 1 detectado. Recriando plano v2 para {season}...")
                elif not is_new_format: logger.info(f"Formato antigo detectado. Gerando novo plano v2 para {season}...")
                else: logger.info(f"Nenhum plano encontrado. Gerando novo plano v2 para {season}...")

                plan_data = await self._generate_new_7_day_plan()
                
                if "error" in plan_data:
                    return plan_data # Retorna o erro
                
                # Salva o plano v2 completo no DB
                await self.cwl_plan_collection.update_one(
                    {"_id": season},
                    {"$set": {
                        "schedule": plan_data['schedule'], 
                        "banco_ativos": plan_data['banco_ativos'],
                        "banco_backups": plan_data['banco_backups'],
                        "participation_count": plan_data['participation_count'],
                        "all_active_players_map": plan_data['all_active_players_map'],
                        "last_updated": datetime.datetime.now(pytz.utc)
                    }},
                    upsert=True
                )
                logger.info(f"Novo plano v2 para {season} salvo no DB.")
                return plan_data
            
            else:
                # 2. PLANO v2 EXISTE E NÃO É DIA 1: Carrega e ATUALIZA (v2)
                logger.info(f"Carregando e atualizando plano v2 existente para {season}...")
                plan_data = await self._update_existing_plan(plan_doc)
                
                # Salva o plano atualizado no DB
                await self.cwl_plan_collection.update_one(
                    {"_id": season},
                    {"$set": {
                        "schedule": plan_data['schedule'], 
                        "banco_ativos": plan_data['banco_ativos'], 
                        "banco_backups": plan_data['banco_backups'],
                        "participation_count": plan_data['participation_count'],
                        "all_active_players_map": plan_data['all_active_players_map'],
                        "warning": plan_data.get('warning'),
                        "last_updated": datetime.datetime.now(pytz.utc)
                    }}
                )
                logger.info(f"Plano v2 para {season} atualizado no DB.")
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
                subs_str += f"_*Motivo: {sub.get('reason', 'Rotação')}_*\n\n" # Usa .get() para segurança
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

