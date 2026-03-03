# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import difflib
import coc
import datetime
from collections import defaultdict
from typing import List, Dict, Any, Tuple
import re
import random
import pytz

logger = logging.getLogger("smurf_detection_cog")

class SmurfDetectionCog(commands.Cog, name="Detetor de Smurfs IA"):
    """
    Sistema Pericial de Detecção de Contas Secundárias (Dossiê Dinâmico e Matriz Comportamental).
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        
        # --- PARÂMETROS TÁTICOS (CONFIGURADOS PELO LÍDER) ---
        self.SYNC_WINDOW_MINUTES = 5
        self.EVIDENCE_EXPIRY_DAYS = 30
        self.MIN_SIMILARITY_TO_INVESTIGATE = 65
        
        # Variáveis de Memória Temporária para a Matriz Comportamental
        self.last_clan_state: Dict[str, Dict[str, int]] = {}
        self.last_war_attacks: set = set()

    async def cog_load(self):
        self.behavior_monitor_task.start()
        self.garbage_collector_task.start()
        logger.info("Radar de Comportamento e Lixeiro Smurf ativados.")

    async def cog_unload(self):
        self.behavior_monitor_task.cancel()
        self.garbage_collector_task.cancel()

    # ==================== EXTRAÇÃO DE DADOS ====================

    def _extract_account_stats(self, player: coc.Player) -> Dict[str, Any]:
        obstacles = 0
        ach_tidy = player.get_achievement(name="Nice and Tidy")
        if ach_tidy: obstacles = ach_tidy.value

        gold_grab = 0
        ach_gold = player.get_achievement(name="Gold Grab")
        if ach_gold: gold_grab = ach_gold.value

        capital_gold = 0
        ach_capital = player.get_achievement(name="Aggressive Capitalism")
        if ach_capital: capital_gold = ach_capital.value

        home_heroes = ["Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion", "Minion Prince"]
        heroes_lvl = sum(h.level for h in player.heroes if h.name in home_heroes)

        account_mass = (player.town_hall * 1000) + (heroes_lvl * 50) + (obstacles * 2) + (gold_grab / 1000000) + (capital_gold / 50000)

        return {
            "th": player.town_hall,
            "heroes": heroes_lvl,
            "obstacles": obstacles,
            "gold_grab": gold_grab,
            "capital_gold": capital_gold,
            "mass": account_mass
        }

    # ==================== ANÁLISE LEXICAL E COMPORTAMENTAL ====================

    def _clean_name(self, name: str) -> str:
        n = name.lower().strip()
        dirty_words = [
            r'\bmini\b', r'\bsec\b', r'\bconta\b', r'\bjr\b', r'\bsecundaria\b',
            r'\bv\d+\b', r'\b2\b', r'\b3\b', r'\bsmurf\b', r'\balt\b', 
            r'\bpro\b', r'\bclash\b', r'\bfake\b', r'\bdoacao\b'
        ]
        for word in dirty_words: n = re.sub(word, '', n)
        n = re.sub(r'[^\w]', '', n)
        n = re.sub(r'\d+$', '', n)
        return n.strip()

    def _get_identity_match(self, name1: str, name2: str) -> int:
        n1 = self._clean_name(name1)
        n2 = self._clean_name(name2)
        if not n1 or not n2: return 0
        if n1 == n2: return 100
        if (len(n1) >= 4 and n1 in n2) or (len(n2) >= 4 and n2 in n1): return 85
        return int(difflib.SequenceMatcher(None, n1, n2).ratio() * 100)

    async def _add_suspicion_points(self, p1: coc.ClanMember, p2: coc.ClanMember, points: int, reason: str):
        if self.db is None: return 
        if p1.tag == p2.tag: return
        
        pair_id = f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}"
        now = datetime.datetime.now(pytz.utc)
        
        await self.db.smurf_evidence.update_one(
            {"_id": pair_id},
            {
                "$setOnInsert": {
                    "tag1": p1.tag, "name1": p1.name, 
                    "tag2": p2.tag, "name2": p2.name, 
                    "score": 0, "reasons": []
                },
                "$inc": {"score": points},
                "$set": {"last_updated": now},
                "$push": {"reasons": f"[{now.strftime('%d/%m %H:%M')}] {reason}"}
            },
            upsert=True
        )

    # ==================== O LIXEIRO DA IA (GARBAGE COLLECTOR) ====================
    @tasks.loop(hours=24)
    async def garbage_collector_task(self):
        if not self.bot.is_ready() or self.db is None: return 
        
        try:
            cutoff_date = datetime.datetime.now(pytz.utc) - datetime.timedelta(days=self.EVIDENCE_EXPIRY_DAYS)
            
            cursor = self.db.smurf_evidence.find({"last_updated": {"$lt": cutoff_date}})
            docs_to_delete = await cursor.to_list(length=None)
            
            if not docs_to_delete: return
            
            result = await self.db.smurf_evidence.delete_many({"last_updated": {"$lt": cutoff_date}})
            
            log_channel_id = getattr(self.bot, 'smurf_log_channel_id', 0)
            if not log_channel_id: 
                log_channel_id = getattr(self.bot, 'ai_log_channel_id', getattr(self.bot, 'channel_id', 0))
            
            channel = self.bot.get_channel(int(log_channel_id))
            if channel:
                desc = f"Apagadas **{result.deleted_count}** evidências comportamentais inativas há mais de {self.EVIDENCE_EXPIRY_DAYS} dias.\n\n"
                for doc in docs_to_delete[:10]: 
                    desc += f"▫️ `{doc['name1']}` & `{doc['name2']}` (Perderam {doc.get('score', 0)} Pts de suspeita)\n"
                
                if len(docs_to_delete) > 10:
                    desc += f"\n*... e mais {len(docs_to_delete) - 10} conexões apagadas da memória.*"

                embed = discord.Embed(
                    title="🧹 Limpeza de Memória Comportamental",
                    description=desc,
                    color=0x95a5a6
                )
                await channel.send(embed=embed)
                
            logger.info(f"Smurf Garbage Collector rodou. {result.deleted_count} documentos apagados.")

        except Exception as e:
            logger.error(f"Erro no Smurf Garbage Collector: {e}")

    @garbage_collector_task.before_loop
    async def before_garbage_collector(self):
        await self.bot.wait_until_ready()

    # ==================== O RADAR COMPORTAMENTAL ====================
    @tasks.loop(minutes=5)
    async def behavior_monitor_task(self):
        if not self.bot.is_ready() or not self.bot.api_client: return
        
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            if not clan: return

            current_state = {m.tag: {"donations": m.donations, "received": m.received, "member": m} for m in clan.members}
            
            # 1. RADAR DE DOAÇÃO CRUZADA
            if self.last_clan_state:
                donors = []
                receivers = []
                
                for tag, state in current_state.items():
                    if tag in self.last_clan_state:
                        diff_donated = state["donations"] - self.last_clan_state[tag]["donations"]
                        diff_received = state["received"] - self.last_clan_state[tag]["received"]
                        
                        if diff_donated > 0: donors.append((state["member"], diff_donated))
                        if diff_received > 0: receivers.append((state["member"], diff_received))
                
                if donors and receivers:
                    for d_member, d_amount in donors:
                        for r_member, r_amount in receivers:
                            if abs(d_amount - r_amount) <= 5: 
                                await self._add_suspicion_points(
                                    d_member, r_member, 15, 
                                    f"Doação Cruzada: {d_member.name} doou ~{d_amount} tropas ao mesmo tempo que {r_member.name} recebeu."
                                )

            self.last_clan_state = current_state

            # 2. RADAR DE SINCRONIA DE GUERRA
            try:
                war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
                if war and war.state == "inWar":
                    current_attacks = set()
                    my_clan = war.clan if coc.utils.correct_tag(war.clan.tag) == coc.utils.correct_tag(self.bot.clan_tag) else war.opponent
                    
                    for m in my_clan.members:
                        for atk in m.attacks:
                            current_attacks.add(atk.attacker_tag)
                            
                    if self.last_war_attacks:
                        new_attacks = current_attacks - self.last_war_attacks
                        
                        if len(new_attacks) >= 2:
                            attackers = [current_state.get(tag, {}).get("member") for tag in new_attacks]
                            attackers = [a for a in attackers if a is not None]
                            
                            for i in range(len(attackers)):
                                for j in range(i+1, len(attackers)):
                                    await self._add_suspicion_points(
                                        attackers[i], attackers[j], 20, 
                                        f"Sincronia de Guerra: Realizaram ataques com menos de {self.SYNC_WINDOW_MINUTES} minutos de diferença."
                                    )
                                    
                    self.last_war_attacks = current_attacks
            except coc.PrivateWarLog: pass
            except coc.NotFound: pass

        except Exception as e:
            logger.error(f"Erro no Behavior Monitor: {e}")

    @behavior_monitor_task.before_loop
    async def before_behavior_monitor(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(10)


    # ==================== O TRIBUNAL DA IA (DOSSIÊ DINÂMICO) ====================

    def _format_large_number(self, num: int) -> str:
        if num >= 1_000_000_000: return f"{num/1_000_000_000:.1f} Bilhões"
        if num >= 1_000_000: return f"{num/1_000_000:.1f} Milhões"
        return f"{num:,}"

    def _judge_relationship(self, p1: coc.Player, stats1: Dict, p2: coc.Player, stats2: Dict, name_sim: int, db_evidence: Dict) -> Tuple[bool, int, str, coc.Player, coc.Player]:
        if stats1['mass'] >= stats2['mass']:
            main_p, main_s, smurf_p, smurf_s = p1, stats1, p2, stats2
        else:
            main_p, main_s, smurf_p, smurf_s = p2, stats2, p1, stats1

        confidence = name_sim
        reasons = []

        behavior_score = db_evidence.get('score', 0)
        if behavior_score > 0:
            confidence += min(40, behavior_score)
            reasons.append(f"🔥 ALERTA COMPORTAMENTAL: Acumularam {behavior_score} pontos de suspeita nos radares de Sincronia e Doação.")
            for r in db_evidence.get('reasons', [])[-3:]: 
                reasons.append(f"  └ {r}")

        mass_ratio = main_s['mass'] / max(smurf_s['mass'], 1)
        gold_diff = main_s['gold_grab'] - smurf_s['gold_grab']
        obs_diff = main_s['obstacles'] - smurf_s['obstacles']
        th_diff = main_s['th'] - smurf_s['th']
        hero_diff = main_s['heroes'] - smurf_s['heroes']

        if name_sim >= 90:
            reasons.append(random.choice([
                "Assinatura nominal virtualmente idêntica detectada.",
                "Padrão de nomenclatura compartilha o mesmo radical primário.",
                "Forte correlação lexical entre os apelidos."
            ]))

        if mass_ratio > 2.0:
            confidence += 15
            reasons.append(random.choice([
                f"Discrepância colossal de evolução: A conta principal é {mass_ratio:.1f}x mais pesada matematicamente.",
                f"Evidência de conta 'Doadora/Espectadora': O progresso difere em {mass_ratio:.1f} vezes.",
            ]))
            if gold_diff > 500_000_000:
                reasons.append(f"A disparidade de {self._format_large_number(gold_diff)} de ouro roubado comprova que '{smurf_p.name}' é uma conta recente.")
        elif mass_ratio < 1.15 and behavior_score == 0:
            confidence -= 25
            reasons.append("ALERTA DE FALSO POSITIVO: As contas possuem tempo de vida e farm quase idênticos. Risco de serem irmãos/amigos jogando juntos com nomes de clã padronizados.")

        if th_diff >= 3:
            confidence += 10
            reasons.append(f"A conta secundária está defasada em {th_diff} níveis de Centro de Vila.")
        
        if hero_diff > 80:
            reasons.append(f"Diferença gritante de esforço: '{main_p.name}' tem {hero_diff} níveis de heróis a mais.")

        if obs_diff > 3000:
             reasons.append(f"Dados históricos irrefutáveis: A conta principal removeu {obs_diff:,} obstáculos a mais, atestando anos de diferença na data de criação.")

        confidence = min(max(int(confidence), 0), 99)
        is_smurf = confidence >= 80 
        
        final_reasoning = "\n".join([f"▪️ {r}" for r in reasons])
        return is_smurf, confidence, final_reasoning, main_p, smurf_p

    # ==================== COMANDO DISCORD ====================

    @app_commands.command(name="smurfs", description="🕵️ Gera um Dossiê Pericial irrefutável (Nome + Comportamento) das multicontas do clã.")
    @app_commands.default_permissions(administrator=True)
    async def slash_analyze_smurfs(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        try:
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            if not clan:
                await interaction.followup.send("❌ Erro de comunicação com os servidores da Supercell.")
                return

            member_tags = [m.tag for m in clan.members]
            players_full = []
            async for p in self.bot.api_client.get_players(member_tags):
                players_full.append(p)

            p_stats = {p.tag: self._extract_account_stats(p) for p in players_full}

            db_owners = defaultdict(list)
            if self.db is not None:
                cursor = self.db.users.find({"player_tag": {"$in": member_tags}})
                async for doc in cursor:
                    if doc.get("discord_id"): db_owners[doc.get("discord_id")].append(doc.get("player_tag"))

            behavior_matrix = {}
            if self.db is not None:
                cursor = self.db.smurf_evidence.find({"score": {"$gt": 10}})
                async for doc in cursor:
                    behavior_matrix[doc["_id"]] = doc

            investigations = []
            processed_tags = set()

            for d_id, tags in db_owners.items():
                if len(tags) > 1:
                    group = [p for p in players_full if p.tag in tags]
                    group.sort(key=lambda x: p_stats[x.tag]['mass'], reverse=True)
                    investigations.append({
                        "main": group[0], "smurfs": group[1:], "confidence": 100,
                        "reason": f"▪️ Vínculo absoluto confirmado no Banco de Dados via Discord ID: <@{d_id}>."
                    })
                    for p in group: processed_tags.add(p.tag)

            candidates = [p for p in players_full if p.tag not in processed_tags]
            for i in range(len(candidates)):
                p1 = candidates[i]
                if p1.tag in processed_tags: continue

                group_smurfs = []
                best_confidence = 0
                best_reason = ""
                main_acc = p1

                for j in range(i + 1, len(candidates)):
                    p2 = candidates[j]
                    if p2.tag in processed_tags: continue

                    pair_id = f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}"
                    evidence_doc = behavior_matrix.get(pair_id, {})
                    
                    sim = self._get_identity_match(p1.name, p2.name)
                    
                    if sim >= self.MIN_SIMILARITY_TO_INVESTIGATE or evidence_doc.get("score", 0) >= 30:
                        is_smurf, conf, reason, m_p, s_p = self._judge_relationship(p1, p_stats[p1.tag], p2, p_stats[p2.tag], sim, evidence_doc)
                        if is_smurf:
                            main_acc = m_p 
                            group_smurfs.append(s_p)
                            processed_tags.add(s_p.tag)
                            if conf > best_confidence:
                                best_confidence = conf
                                best_reason = reason

                if group_smurfs:
                    processed_tags.add(main_acc.tag)
                    investigations.append({
                        "main": main_acc, "smurfs": group_smurfs,
                        "confidence": best_confidence, "reason": best_reason
                    })

            if not investigations:
                await interaction.followup.send("✅ **Clã Limpo:** A IA não detectou contas suspeitas baseadas em nomes ou telemetria nas últimas semanas.")
                return

            embed = discord.Embed(
                title="📂 DOSSIÊ PERICIAL: MÚLTIPLAS CONTAS",
                description="Este relatório cruza telemetria de jogo, radares comportamentais de guerra/doação e lexicologia para determinar a posse de contas secundárias.",
                color=0x2b2d31, 
                timestamp=datetime.datetime.now()
            )

            investigations.sort(key=lambda x: x['confidence'], reverse=True)

            def format_stats(p_tag):
                s = p_stats[p_tag]
                loot_str = self._format_large_number(s['gold_grab'])
                return f"**CV:** {s['th']} | **Heróis:** {s['heroes']} | **Loot:** {loot_str}"

            for inv in investigations:
                main = inv['main']
                smurfs = inv['smurfs']
                conf = inv['confidence']
                
                if conf == 100:
                    status = "🟢 CONFIRMAÇÃO SISTÊMICA (100%)"
                elif conf >= 90:
                    status = f"🔴 RISCO EXTREMO ({conf}%)"
                else:
                    status = f"🟠 ALTA SUSPEITA ({conf}%)"

                body = f"```yaml\n{status}\n```"
                body += f"👑 **[MAIN] {main.name}** (`{main.tag}`)\n> └ {format_stats(main.tag)}\n\n"
                
                for s in smurfs:
                    body += f"👶 **[SMURF] {s.name}** (`{s.tag}`)\n> └ {format_stats(s.tag)}\n\n"
                
                body += f"**🔎 Argumentação Lógica da IA:**\n{inv['reason']}"
                
                embed.add_field(name="━"*30, value=body, inline=False)
                
            embed.set_footer(text="AIA (Auditoria de IA) com Radar Comportamental • ClashGenius", icon_url="https://cdn-icons-png.flaticon.com/512/2102/2102633.png")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro no dossie smurf: {e}", exc_info=True)
            await interaction.followup.send("❌ Erro fatal ao gerar o dossiê.")

    # ==================== FUNÇÕES PARA O PAINEL WEB (API) ====================

    async def get_web_dossier(self) -> List[Dict[str, Any]]:
        """Busca todas as evidências comportamentais ativas no banco de dados para a tela de Radar Pericial."""
        if self.db is None: return []
        try:
            cursor = self.db.smurf_evidence.find({"score": {"$gt": 0}}).sort("score", -1)
            docs = await cursor.to_list(length=None)
            return docs
        except Exception as e:
            logger.error(f"Erro ao buscar dossiê web: {e}")
            return []

    async def absolve_pair(self, pair_id: str) -> Dict[str, str]:
        """Classifica o par como Falso Positivo e apaga do banco."""
        if self.db is None: return {"status": "error", "message": "Banco de dados offline."}
        try:
            result = await self.db.smurf_evidence.delete_one({"_id": pair_id})
            if result.deleted_count > 0:
                return {"status": "success", "message": "Contas absolvidas! Ficha comportamental limpa."}
            return {"status": "error", "message": "Par não encontrado ou já apagado."}
        except Exception as e:
            logger.error(f"Erro ao absolver smurfs {pair_id}: {e}")
            return {"status": "error", "message": "Falha ao processar absolvição no banco."}

    async def condemn_pair(self, pair_id: str) -> Dict[str, str]:
        """Apaga o registro do comportamento e lança ambas as tags diretamente na Watchlist."""
        if self.db is None: return {"status": "error", "message": "Banco de dados offline."}
        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if not watchlist_cog: return {"status": "error", "message": "Módulo de Watchlist não carregado."}
        
        try:
            doc = await self.db.smurf_evidence.find_one({"_id": pair_id})
            if not doc: return {"status": "error", "message": "Documento não encontrado."}
            
            # Adiciona as duas tags à Watchlist
            reason = "Condenado pela IA como Smurf"
            details = f"Vínculo detectado entre {doc.get('name1')} e {doc.get('name2')} (Score: {doc.get('score', 0)})"
            
            await watchlist_cog.add_to_watchlist(doc.get('tag1'), doc.get('name1'), reason, details)
            await watchlist_cog.add_to_watchlist(doc.get('tag2'), doc.get('name2'), reason, details)
            
            # Limpa do Radar Pericial
            await self.db.smurf_evidence.delete_one({"_id": pair_id})
            
            return {"status": "success", "message": "Contas condenadas e adicionadas à Watchlist com sucesso!"}
        except Exception as e:
            logger.error(f"Erro ao condenar smurfs {pair_id}: {e}")
            return {"status": "error", "message": "Falha ao processar a condenação."}


async def setup(bot: commands.Bot):
    await bot.add_cog(SmurfDetectionCog(bot))
