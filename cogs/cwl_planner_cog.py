# -*- coding: utf-8 -*-3
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
from typing import Dict, List, Any, Optional
import datetime
import pytz
from collections import deque # Usado para a fila de rotação

logger = logging.getLogger("cwl_planner_cog")

class CwlPlannerCog(commands.Cog, name="Planeador de CWL"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_client: coc.Client = self.bot.api_client 
        self.db = bot.db
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
        Busca a guerra ativa, o dia atual, a temporada E O TAMANHO da CWL.
        """
        try:
            cwl_group = await self.bot.api_client.get_league_group(self.bot.clan_tag)
            if not cwl_group or cwl_group.state == "notInWar": # Mudado de != "inWar"
                return None 

            active_war = None
            day_number = -1
            active_war_tag = None
            team_size = 15 # Default
            
            # Tenta encontrar a guerra do dia atual ou futura
            found_war = False
            for i, round_war_tags in enumerate(cwl_group.rounds):
                for war_tag in round_war_tags:
                    if war_tag == '#0': continue
                    try:
                        war = await self.bot.api_client.get_league_war(war_tag)
                        if war.clan.tag == self.bot.clan_tag or war.opponent.tag == self.bot.clan_tag:
                            team_size = war.team_size # Captura o team_size da primeira guerra que encontrar
                            
                            if war.state == 'inWar':
                                active_war = war
                                day_number = i + 1
                                active_war_tag = war_tag
                                found_war = True
                                break
                            elif war.state == 'preparation' and not active_war: # Só usa preparation se não achou 'inWar'
                                active_war = war
                                day_number = i + 1
                                active_war_tag = war_tag
                                found_war = True
                                break
                    except coc.NotFound:
                        continue
                if found_war:
                    break
            
            # Se não encontrou nenhuma guerra (inWar ou preparation), mas o grupo está 'inWar'
            # Significa que a CWL acabou (dia 8) ou está entre guerras
            if not active_war and cwl_group.state == "inWar":
                 day_number = 8 # Indica que acabou
                 # Tenta pegar o team_size da última guerra, se possível
                 try:
                     last_war_tag = next(wt for r in reversed(cwl_group.rounds) for wt in reversed(r) if wt != '#0')
                     if last_war_tag:
                         last_war = await self.bot.api_client.get_league_war(last_war_tag)
                         team_size = last_war.team_size
                 except Exception:
                     team_size = 15 # Mantém o default se falhar

            return {
                "active_war": active_war,
                "day_number": day_number,
                "season": cwl_group.season,
                "war_tag": active_war_tag,
                "team_size": team_size # NOVO: Retorna o tamanho da guerra
            }

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

    def _get_player_pool_entry(self, player_data: Dict[str, Any]) -> Dict[str, Any]:
         """Cria a estrutura de dados padrão para um jogador no plano."""
         return {"player": player_data, "days_played": 0}

    async def _generate_new_7_day_plan(self, team_size: int, active_war: coc.ClanWar) -> Dict[str, Any]:
        """
        NOVA LÓGICA (O "CÉREBRO"): Gera um plano de 7 dias com rotação justa.
        MODIFICADO: Agora usa a 'active_war' (guerra do Dia 1) como ponto de partida.
        """
        cwl_members = await self.get_cwl_members_for_planning()
        if cwl_members is None:
            return {"error": "Não foi possível buscar os membros inscritos na CWL. O clã está em uma liga de guerra?"}

        roster_size = team_size 
        
        clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
        current_member_tags = {m.tag for m in clan.members}
        
        db_cog = self.bot.get_cog("Banco de Dados")
        player_statuses = await db_cog.load_player_notes_from_db() if db_cog else {}
        
        # --- LÓGICA MODIFICADA: Baseia-se na guerra ativa ---
        
        # 1. Pega o roster REAL da guerra ativa
        our_clan_in_war = active_war.clan if active_war.clan.tag == self.bot.clan_tag else active_war.opponent
        actual_roster_tags = {m.tag for m in our_clan_in_war.members}
        
        logger.info(f"Roster real da guerra Dia 1 detectado com {len(actual_roster_tags)} membros.")

        # 2. Constrói os pools (roster, banco ativo, banco backup)
        current_roster = []
        current_active_bench = deque()
        current_backup_bench = deque()
        warning = None # V4: Adiciona a variável de aviso

        all_cwl_players_pool = []
        for member in cwl_members:
            # Só planeia para quem está no clã
            if member['tag'] in current_member_tags:
                all_cwl_players_pool.append(self._get_player_pool_entry(member))
        
        if len(actual_roster_tags) < roster_size:
            warning = f"Aviso Dia 1: Roster real ({len(actual_roster_tags)}) é MENOR que o tamanho da guerra ({team_size}). O plano pode ficar inconsistente."
            logger.warning(warning)
        elif len(actual_roster_tags) > roster_size:
             warning = f"Aviso Dia 1: Roster real ({len(actual_roster_tags)}) é MAIOR que o tamanho da guerra ({team_size}). Usando roster real."
             logger.warning(warning)


        for p_entry in all_cwl_players_pool:
            player_tag = p_entry['player']['tag']
            
            if player_tag in actual_roster_tags:
                # Este jogador está no roster ATUAL do Dia 1
                current_roster.append(p_entry)
            else:
                # Este jogador está no BANCO
                status = player_statuses.get(player_tag, {}).get('cwl_status', 'active')
                if status == 'active':
                    current_active_bench.append(p_entry)
                else:
                    current_backup_bench.append(p_entry)
                    
        # Ordena os bancos para a rotação (Ativos: mais fracos primeiro | Backups: mais fortes primeiro)
        current_active_bench = deque(sorted(current_active_bench, key=lambda p: p['player']['town_hall']))
        current_backup_bench = deque(sorted(current_backup_bench, key=lambda p: p['player']['town_hall'], reverse=True))

        logger.info(f"Plano Dia 1 (Baseado na Realidade): {len(current_roster)} no roster, {len(current_active_bench)} no banco ativo, {len(current_backup_bench)} no banco backup.")
        
        # --- Fim da Lógica Modificada ---
        
        # --- Dia 1: Definição Inicial ---
        # (Bloco de 'needed_for_roster_1' removido, pois agora usamos o roster real)
        
        # Incrementa dias jogados para o Dia 1
        for p in current_roster:
            p['days_played'] += 1

        schedule = []
        schedule.append({
            "day": 1,
            "active_roster": current_roster,
            "substitutions": [],
            "active_bench": list(current_active_bench), # Salva foto do banco
            "backup_bench": list(current_backup_bench) # Salva foto do banco
        })

        # --- Dias 2-7: Rotação Justa ---
        num_to_rotate = 5 if roster_size == 30 else 3 # Roda 5 em 30v30, 3 em 15v15

        for day in range(2, 8):
            substitutions = []
            
            roster_sorted = sorted(current_roster, key=lambda p: p['days_played'], reverse=True)
            
            players_to_sit = []
            players_to_play = []

            players_to_sit = roster_sorted[:num_to_rotate]
            
            for _ in range(num_to_rotate):
                if current_active_bench:
                    players_to_play.append(current_active_bench.popleft())
            
            needed = num_to_rotate - len(players_to_play)
            if needed > 0:
                 # V4 (BUG 4): Adiciona aviso se backups forem usados na rotação
                 if not warning: # Só define o aviso se não houver um aviso mais antigo
                    warning = f"Aviso Dia {day}: Banco de 'Ativos' vazio. 'Backups' serão usados na rotação."
                 logger.warning(f"CWL Dia {day}: Banco de Ativos vazio. Puxando {needed} jogador(es) do Backup.")
                 for _ in range(needed):
                     if current_backup_bench:
                         players_to_play.append(current_backup_bench.popleft())
                     else:
                         logger.error(f"CWL Dia {day}: Faltam jogadores! Banco de Ativos e Backup vazios.")
                         pass 
            
            new_roster = [p for p in current_roster if p not in players_to_sit] # Remove quem saiu
            
            for i in range(len(players_to_sit)):
                player_out = players_to_sit[i]
                
                if i < len(players_to_play):
                    player_in = players_to_play[i]
                    new_roster.append(player_in) # Adiciona novo jogador
                    
                    status_out = player_statuses.get(player_out['player']['tag'], {}).get('cwl_status', 'active')
                    if status_out == 'active':
                        current_active_bench.append(player_out) 
                    else:
                        current_backup_bench.append(player_out) 

                    substitutions.append({
                        "out": player_out['player'], "in": player_in['player'],
                        "reason": f"Rotação justa (Saiu: {player_out['days_played']} dias | Entrou: {player_in['days_played']} dias)"
                    })
                else:
                    new_roster.append(player_out)
                    logger.warning(f"CWL Dia {day}: {player_out['player']['name']} foi mantido no roster (sem substituto).")

            for p in new_roster:
                p['days_played'] += 1
            
            current_roster = new_roster 

            schedule.append({
                "day": day,
                "active_roster": current_roster,
                "substitutions": substitutions,
                "active_bench": list(current_active_bench),
                "backup_bench": list(current_backup_bench)
            })
        
        all_players_pool = active_pool + backup_pool
        participation_score = [
            {"player": p['player'], "days_played": p['days_played']}
            for p in all_players_pool
        ]
        participation_score.sort(key=lambda x: x['days_played'], reverse=True)

        return {
            "schedule": schedule,
            "participation_score": participation_score,
            "active_bench_final": list(current_active_bench), 
            "backup_bench_final": list(current_backup_bench),
            "warning": warning # V4: Retorna o aviso
        }

    async def _update_existing_plan(self, plan_doc: Dict[str, Any], current_day: int, team_size: int) -> Dict[str, Any]:
        """
        V4 - LÓGICA DE "RESET": Recalcula o futuro (Dias 2-7) a partir do Dia 1
        para corrigir o bug de dias acumulados (38/7).
        """
        logger.info(f"Atualizando plano (v4 - Reset) (Dia Atual: {current_day})...")
        
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            current_member_tags = {m.tag for m in clan.members}
            db_cog = self.bot.get_cog("Banco de Dados")
            player_statuses = await db_cog.load_player_notes_from_db() if db_cog else {}

            # 1. Carrega o estado base (Dia 1) - A FONTE DA VERDADE
            base_state_doc = next((d for d in plan_doc['schedule'] if d['day'] == 1), None)
            if not base_state_doc:
                raise KeyError("Plano salvo não contém o Dia 1. Forçando recriação.")

            # 2. Migra os dados do Dia 1 para o formato novo (se necessário)
            # V4 (BUG 2): Força 'days_played' para 1 (Dia 1) ou 0 (Banco) para
            #             corrigir os dias acumulados (38/7).
            current_roster = []
            for p_data in base_state_doc.get('active_roster', []):
                p_entry = {'player': p_data, 'days_played': 1} if 'player' not in p_data else p_data.copy()
                p_entry['days_played'] = 1 # Força reset para 1
                current_roster.append(p_entry)

            current_active_bench = deque()
            for p_data in base_state_doc.get('active_bench', []):
                p_entry = {'player': p_data, 'days_played': 0} if 'player' not in p_data else p_data.copy()
                p_entry['days_played'] = 0 # Força reset para 0
                current_active_bench.append(p_entry)

            current_backup_bench = deque()
            for p_data in base_state_doc.get('backup_bench', []):
                p_entry = {'player': p_data, 'days_played': 0} if 'player' not in p_data else p_data.copy()
                p_entry['days_played'] = 0 # Força reset para 0
                current_backup_bench.append(p_entry)
            
            logger.info("Migração e Reset do Dia 1 concluídos. Recalculando Dias 2-7...")

            # 3. Simula do Dia 2 até o Dia 7
            new_schedule = [base_state_doc] # Começa com o Dia 1
            num_to_rotate = 5 if team_size == 30 else 3
            warning = plan_doc.get('warning') # Carrega aviso antigo (ex: Dia 1 usou backup)

            for day in range(2, 8):
                
                # A. Substituições de Emergência (Leavers)
                final_roster_pool = []
                roster_substitutions_this_day = []
                
                for p_entry in current_roster:
                    if p_entry['player']['tag'] in current_member_tags:
                        final_roster_pool.append(p_entry) # OK
                    else:
                        # LEAVER! Tenta substituir
                        replacement = None
                        if current_active_bench:
                            replacement = current_active_bench.popleft()
                        elif current_backup_bench:
                            replacement = current_backup_bench.popleft()
                            if not warning: warning = f"Aviso Dia {day}: {replacement['player']['name']} (Backup) entrou no lugar de um jogador que saiu."
                        
                        if replacement:
                            final_roster_pool.append(replacement)
                            roster_substitutions_this_day.append({
                                "out": p_entry['player'], "in": replacement['player'],
                                "reason": f"Subst. Emergência (Dia {day}): {p_entry['player']['name']} saiu."
                            })
                        else:
                            final_roster_pool.append(p_entry) # Mantém o leaver se não há substituto
                
                current_active_bench = deque([p for p in current_active_bench if p['player']['tag'] in current_member_tags])
                current_backup_bench = deque([p for p in current_backup_bench if p['player']['tag'] in current_member_tags])
                current_roster = final_roster_pool # Roster atualizado pós-leavers

                # B. Rotação Justa (Lógica idêntica a _generate_new_7_day_plan)
                substitutions = list(roster_substitutions_this_day)
                roster_sorted = sorted(current_roster, key=lambda p: p['days_played'], reverse=True)
                
                players_to_sit = roster_sorted[:num_to_rotate]
                players_to_play = []

                for _ in range(num_to_rotate):
                    if current_active_bench:
                        players_to_play.append(current_active_bench.popleft())
                
                needed = num_to_rotate - len(players_to_play)
                if needed > 0:
                     if not warning: warning = f"Aviso Dia {day}: Banco de 'Ativos' vazio. 'Backups' serão usados na rotação."
                     for _ in range(needed):
                         if current_backup_bench:
                             players_to_play.append(current_backup_bench.popleft())
                
                new_roster = [p for p in current_roster if p not in players_to_sit]
                
                for i in range(len(players_to_sit)):
                    player_out = players_to_sit[i]
                    if i < len(players_to_play):
                        player_in = players_to_play[i]
                        new_roster.append(player_in)
                        
                        status_out = player_statuses.get(player_out['player']['tag'], {}).get('cwl_status', 'active')
                        if status_out == 'active': current_active_bench.append(player_out)
                        else: current_backup_bench.append(player_out)

                        substitutions.append({
                            "out": player_out['player'], "in": player_in['player'],
                            "reason": f"Rotação justa (Saiu: {player_out['days_played']}d | Entrou: {player_in['days_played']}d)"
                        })
                    else:
                        new_roster.append(player_out) # Mantém se não há substituto
                
                # C. Incrementa dias
                for p in new_roster:
                    p['days_played'] += 1
                
                current_roster = new_roster

                # D. Salva o dia
                new_schedule.append({
                    "day": day,
                    "active_roster": current_roster,
                    "substitutions": substitutions,
                    "active_bench": list(current_active_bench),
                    "backup_bench": list(current_backup_bench)
                })

            # 4. Gera placar final
            all_players_pool = current_roster + list(current_active_bench) + list(current_backup_bench)
            participation_score = [
                {"player": p['player'], "days_played": p['days_played']}
                for p in all_players_pool
            ]
            participation_score.sort(key=lambda x: x['days_played'], reverse=True)

            logger.info("Recálculo completo do plano (v4) concluído.")
            return {
                "schedule": new_schedule,
                "participation_score": participation_score,
                "active_bench_final": list(current_active_bench),
                "backup_bench_final": list(current_backup_bench),
                "warning": warning # Retorna o aviso atualizado
            }

        except KeyError as e:
            # V4 (BUG 1/3): Se a migração falhar (ex: 'active_roster' não existe no Dia 1)
            logger.error(f"Erro de Chave (KeyError) ao ATUALIZAR plano de CWL (v4): {e}. Forçando recriação.", exc_info=True)
            return {"error": "MIGRATION_FAILED"} # Erro especial
        except Exception as e:
            logger.error(f"Erro crítico ao ATUALIZAR plano de CWL (v4): {e}", exc_info=True)
            return {"error": f"Erro ao atualizar: {e}"}


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
        current_day = info['day_number']
        team_size = info['team_size'] # Pega o team_size
        active_war = info['active_war'] # Pega a guerra ativa
        
        if current_day == 8:
             plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
             if plan_doc:
                 logger.info(f"CWL Dia {current_day}. Retornando plano final salvo.")
                 
                 # Tenta migrar/ler o placar final
                 try:
                     # V4: Tenta ler o placar salvo
                     participation_score = plan_doc.get('participation_score', [])
                     if not participation_score: # Se não houver, tenta calcular do último dia
                        all_players_pool = plan_doc['schedule'][-1]['active_roster'] + plan_doc['schedule'][-1].get('active_bench', []) + plan_doc['schedule'][-1].get('backup_bench', [])
                        participation_score = []
                        for p_data in all_players_pool:
                            player_info = p_data.get('player', p_data) 
                            days_played = p_data.get('days_played', 7) 
                            participation_score.append({"player": player_info, "days_played": days_played})
                        participation_score.sort(key=lambda x: x['days_played'], reverse=True)
                 except Exception as e:
                     logger.error(f"Erro ao migrar placar final: {e}")
                     participation_score = []
                 
                 return {
                     "current_day": current_day,
                     "schedule": plan_doc['schedule'],
                     "participation_score": participation_score,
                     "active_bench_final": plan_doc.get('active_bench_final', []),
                     "backup_bench_final": plan_doc.get('backup_bench_final', [])
                 }
             else:
                 return {"error": "CWL terminada, mas nenhum plano encontrado no histórico."}


        try:
            plan_doc = await self.cwl_plan_collection.find_one({"_id": season})
            
            is_old_format = False
            if plan_doc:
                try:
                    first_player = plan_doc['schedule'][0]['active_roster'][0]
                    if 'player' not in first_player:
                        is_old_format = True
                        logger.warning(f"Plano antigo (sem 'player' key) detectado para {season}. Gerando um novo plano.")
                except (IndexError, KeyError, TypeError) as e:
                    is_old_format = True
                    logger.warning(f"Plano malformado ou vazio detectado para {season} ({e}). Gerando um novo plano.")
            
            is_wrong_size = False
            if plan_doc and not is_old_format:
                 try:
                     saved_size = len(plan_doc['schedule'][0]['active_roster'])
                     if saved_size != team_size:
                         is_wrong_size = True
                         logger.warning(f"Mudança no tamanho da CWL detectada! (Salvo: {saved_size}v{saved_size}, Atual: {team_size}v{team_size}). Gerando novo plano.")
                 except Exception:
                     pass 

            if plan_doc is None or is_old_format or is_wrong_size:
                # --- ALTERAÇÃO PRINCIPAL AQUI ---
                if not active_war:
                    logger.error(f"Gerando NOVO plano para {season}, mas a guerra do Dia {current_day} não foi encontrada. O plano não pode ser criado.")
                    return {"error": f"Erro crítico: Não foi possível encontrar a guerra ativa do Dia {current_day} para gerar o plano inicial."}
                
                logger.info(f"Gerando NOVO plano de CWL ({team_size}v{team_size}) para a temporada {season} baseado na guerra ATIVA...")
                plan_data = await self._generate_new_7_day_plan(team_size, active_war) # Passa a guerra ativa
                # --- FIM DA ALTERAÇÃO ---
                
                if "error" in plan_data: return plan_data
                
                await self.cwl_plan_collection.update_one(
                    {"_id": season},
                    {"$set": { 
                        "schedule": plan_data['schedule'],
                        "participation_score": plan_data['participation_score'],
                        "active_bench_final": plan_data['active_bench_final'],
                        "backup_bench_final": plan_data['backup_bench_final'],
                        "warning": plan_data.get('warning'), # V4
                        "last_updated": datetime.datetime.now(pytz.utc)
                    }},
                    upsert=True
                )
                logger.info(f"Novo plano para {season} salvo no DB.")
                plan_data["current_day"] = current_day 
                return plan_data
            
            else:
                logger.info(f"Carregando e atualizando plano existente (v4 - Reset) para {season} (Dia {current_day}, {team_size}v{team_size})...")
                # V4: Chama a nova lógica de 'Reset'
                plan_data = await self._update_existing_plan(plan_doc, current_day, team_size)
                
                # V4 (BUG 1/3): Se a atualização/migração falhar, apaga o plano e recria do zero
                if "error" in plan_data and plan_data["error"] == "MIGRATION_FAILED": 
                    logger.error(f"Falha na migração/atualização (v4) do plano {season}. Forçando geração de NOVO plano.")
                    await self.cwl_plan_collection.delete_one({"_id": season}) # Deleta o plano antigo
                    # Chama a si mesmo de novo (recursivo), mas agora plan_doc será None
                    return await self.generate_rotation_plan() 
                elif "error" in plan_data:
                    logger.error(f"Erro não-migratório ao atualizar (v4): {plan_data['error']}")
                    return plan_data # Retorna o erro normal

                # Salva o plano recalculado
                await self.cwl_plan_collection.update_one(
                    {"_id": season},
                    {"$set": { 
                        "schedule": plan_data['schedule'],
                        "participation_score": plan_data['participation_score'],
                        "active_bench_final": plan_data['active_bench_final'],
                        "backup_bench_final": plan_data['backup_bench_final'],
                        "warning": plan_data.get('warning'), # V4
                        "last_updated": datetime.datetime.now(pytz.utc)
                    }}
                )
                logger.info(f"Plano (v4) para {season} atualizado no DB.")
                plan_data["current_day"] = current_day 
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
            active_war_tag_str = info['war_tag']

            if not active_war or not active_war_tag_str:
                 logger.info(f"CWL ativa (Dia {day_number}), mas sem guerra 'inWar' ou 'preparation' (provavelmente entre rounds).")
                 return

            logger.info(f"Guerra ativa encontrada: Dia {day_number} vs {active_war.opponent.name}.")
            await self.post_daily_plan_if_needed(active_war, active_war_tag_str, season, day_number)
            await self.check_and_alert_inactivity(active_war, active_war_tag_str)

        except Exception as e:
            logger.error(f"Erro na tarefa de monitorização da CWL: {e}", exc_info=True)

    async def post_daily_plan_if_needed(self, war: coc.ClanWar, war_tag_id: str, season: str, day_number: int):
        if war_tag_id in self.posted_daily_plans:
            logger.info(f"Plano para o Dia {day_number} (guerra {war_tag_id}) já foi postado. Ignorando.")
            return

        logger.info(f"Postando plano para o Dia {day_number} (guerra {war_tag_id})...")
        
        plan_data = await self.generate_rotation_plan() 
        if "error" in plan_data: 
            logger.error(f"Erro ao gerar plano de rotação para postagem: {plan_data['error']}")
            if "não está em uma guerra CWL ativa" in plan_data['error']:
                 self.posted_daily_plans.add(war_tag_id)
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
        
        roster_list = []
        sorted_roster_for_display = sorted(current_day_plan["active_roster"], key=lambda p: p['player']['town_hall'], reverse=True)
        
        for i, p_entry in enumerate(sorted_roster_for_display):
            player_data = p_entry.get('player') 
            roster_list.append(f"`{i+1:02d}.` {player_data.get('name', 'N/A')} (CV{player_data.get('town_hall', '?')})")
        
        roster_str = "\n".join(roster_list)

        embed.add_field(name=f"⚔️ Escalação Ativa ({len(roster_list)}v{len(roster_list)})", value=roster_str or "N/A", inline=False)

        if current_day_plan["substitutions"]:
            subs_str = ""
            for sub in current_day_plan["substitutions"]:
                subs_str += f"🔴 **Sai:** {sub['out']['name']} (CV{sub['out']['town_hall']})\n"
                subs_str += f"🟢 **Entra:** {sub['in']['name']} (CV{sub['in']['town_hall']})\n"
                subs_str += f"_*Motivo: {sub['reason']}_*\n\n"
            embed.add_field(name="🔄 Alterações na Equipa", value=subs_str.strip(), inline=False)
        else:
            default_message = "Manter a escalação do dia anterior." if day_number > 1 else "Escalação inicial definida. Vamos com tudo!"
            embed.add_field(name="🔄 Alterações na Equipa", value=default_message, inline=False)
        
        if plan_data.get("warning"):
             embed.add_field(name="⚠️ Aviso da IA", value=plan_data["warning"], inline=False)

        if opponent.badge:
            embed.set_thumbnail(url=opponent.badge.url)

        await self._send_planner_embed(embed)
        self.posted_daily_plans.add(war_tag_id)
        logger.info(f"Plano para o Dia {day_number} enviado e tag {war_tag_id} adicionada ao cache.")

    async def check_and_alert_inactivity(self, war: coc.ClanWar, war_tag_id: str):
        time_left = war.end_time.seconds_until
        if not (15 * 60 < time_left < 4 * 3600): return

        our_clan = war.clan if war.clan.tag == self.bot.clan_tag else war.opponent
        inactive_members = [m for m in our_clan.members if len(m.attacks) < war.attacks_per_member]

        if not inactive_members: return

        alert_id = f"{war_tag_id}-inactivity"
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
            await self.cwl_monitoring_task.coro(self) 
            
            await ctx.message.add_reaction("✅")
            await ctx.message.remove_reaction("🔄", self.bot.user)
        except Exception as e:
            await ctx.message.add_reaction("❌")
            await ctx.message.remove_reaction("🔄", self.bot.user)
            await ctx.send(f"Ocorreu um erro ao forçar o plano: `{e}`")
            logger.error(f"Erro ao executar !forcarplano: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    if bot.cwl_planner_channel_id and bot.db is not None:
        await bot.add_cog(CwlPlannerCog(bot))
    else:
        logger.warning("Cog 'CwlPlannerCog' não carregado (ID do canal ou DB não configurado).")
