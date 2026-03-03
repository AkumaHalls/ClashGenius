# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import difflib
import coc
import datetime
from collections import defaultdict
from typing import List, Dict, Any, Tuple, Optional
import re
import random
import pytz

logger = logging.getLogger("smurf_detection_cog")

class SmurfDetectionCog(commands.Cog, name="Detetor de Smurfs IA"):
    """
    Sistema Pericial de Detecção de Contas Secundárias (XAI - Explainable AI).
    Cruza Lexicologia, Forense de Laboratório, Telemetria de Combate e Discrepância de Massa.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        
        # --- PARÂMETROS FORENSES ---
        self.SYNC_WINDOW_MINUTES = 5
        self.DECAY_DAYS = 7           # Dias para iniciar a regeneração (esquecimento)
        self.DECAY_PERCENTAGE = 0.15  # Perde 15% da suspeita a cada ciclo
        self.MIN_SIMILARITY = 60
        
        # --- MEMÓRIA RAM DA IA ---
        self.last_clan_state: Dict[str, Dict[str, int]] = {}
        self.last_war_attacks: set = set()

    async def cog_load(self):
        self.behavior_monitor_task.start()
        self.regenerative_ai_task.start()
        logger.info("XAI: Radares Forenses e Matriz Regenerativa ativados.")

    async def cog_unload(self):
        self.behavior_monitor_task.cancel()
        self.regenerative_ai_task.cancel()

    # ==================== EXTRAÇÃO DE DADOS & FORENSE DE LABORATÓRIO ====================

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

        # Calculo de Massa Bruta
        account_mass = (player.town_hall * 1000) + (heroes_lvl * 50) + (obstacles * 2) + (gold_grab / 1000000) + (capital_gold / 50000)

        return {
            "th": player.town_hall,
            "heroes": heroes_lvl,
            "obstacles": obstacles,
            "gold_grab": gold_grab,
            "capital_gold": capital_gold,
            "mass": account_mass
        }

    def _analyze_mula_signature(self, player: coc.Player) -> Tuple[bool, int, str]:
        """Eixo 2: Analisa se a conta existe apenas para doar tropas pesadas (Conta Mula)."""
        if player.town_hall < 12:
            return False, 0, "" 
            
        donation_troops = ["Electro Dragon", "Balloon", "Yeti", "Rage Spell", "Freeze Spell"]
        basic_troops = ["Barbarian", "Archer", "Giant", "Goblin"]
        
        don_levels = []
        bas_levels = []
        
        for t in player.troops + player.spells:
            if t.is_home_base:
                if t.name in donation_troops:
                    don_levels.append(t.level / max(t.max_level, 1))
                elif t.name in basic_troops:
                    bas_levels.append(t.level / max(t.max_level, 1))
                    
        if not don_levels or not bas_levels:
            return False, 0, ""
            
        avg_don = sum(don_levels) / len(don_levels)
        avg_bas = sum(bas_levels) / len(bas_levels)
        
        if avg_don > 0.80 and avg_bas < 0.40:
            score = int((avg_don - avg_bas) * 100)
            return True, score, f"Assinatura 'Mula' detectada. Tropas de suporte (Dragão Elétrico/Balão) estão {avg_don*100:.0f}% maximizadas, enquanto tropas básicas estão sucateadas ({avg_bas*100:.0f}%)."
            
        return False, 0, ""

    # ==================== ANÁLISE LEXICAL E SINCRONIA ====================

    def _clean_name(self, name: str) -> str:
        n = name.lower().strip()
        dirty_words = [
            r'\bmini\b', r'\bsec\b', r'\bconta\b', r'\bjr\b', r'\bsecundaria\b',
            r'\bv\d+\b', r'\b2\b', r'\b3\b', r'\bsmurf\b', r'\balt\b', 
            r'\bpro\b', r'\bclash\b', r'\bfake\b', r'\bdoacao\b', r'\bsecundária\b'
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

    async def _log_telemetry(self, p1: coc.ClanMember, p2: coc.ClanMember, points: int, log_msg: str):
        """Eixo 3: Registra na Matriz Comportamental o cruzamento de atividades (Mutex)."""
        if self.db is None or p1.tag == p2.tag: return 
        
        pair_id = f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}"
        now = datetime.datetime.now(pytz.utc)
        
        await self.db.smurf_evidence.update_one(
            {"_id": pair_id},
            {
                "$setOnInsert": {"tag1": p1.tag, "tag2": p2.tag, "score": 0, "logs": []},
                "$inc": {"score": points},
                "$set": {"last_updated": now},
                "$push": {"logs": {"$each": [f"[{now.strftime('%d/%m %H:%M')}] {log_msg}"], "$slice": -5}}
            },
            upsert=True
        )

    # ==================== A CURA DA IA (REGENERAÇÃO) ====================
    
    @tasks.loop(hours=24)
    async def regenerative_ai_task(self):
        """Reduz a suspeita de contas que pararam de interagir juntas (Atenuação)."""
        if not self.bot.is_ready() or self.db is None: return 
        
        try:
            decay_date = datetime.datetime.now(pytz.utc) - datetime.timedelta(days=self.DECAY_DAYS)
            
            cursor = self.db.smurf_evidence.find({"last_updated": {"$lt": decay_date}, "score": {"$gt": 0}})
            async for doc in cursor:
                new_score = int(doc["score"] * (1.0 - self.DECAY_PERCENTAGE))
                
                if new_score < 5:
                    await self.db.smurf_evidence.delete_one({"_id": doc["_id"]})
                else:
                    await self.db.smurf_evidence.update_one(
                        {"_id": doc["_id"]}, 
                        {
                            "$set": {"score": new_score, "last_updated": datetime.datetime.now(pytz.utc)},
                            "$push": {"logs": {"$each": [f"[{datetime.datetime.now().strftime('%d/%m')}] 📉 Regeneração: Score atenuado para {new_score} por inatividade conjunta."], "$slice": -5}}
                        }
                    )
            logger.info("XAI: Ciclo Regenerativo concluído.")
        except Exception as e:
            logger.error(f"Erro no ciclo regenerativo: {e}")

    @regenerative_ai_task.before_loop
    async def before_regenerative(self):
        await self.bot.wait_until_ready()

    # ==================== O RADAR COMPORTAMENTAL CONTÍNUO ====================
    
    @tasks.loop(minutes=5)
    async def behavior_monitor_task(self):
        """Vigia o clã em tempo real em busca de 'Dança de Logoff' e Doações Cruzadas."""
        if not self.bot.is_ready() or not self.bot.api_client: return
        
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            if not clan: return

            current_state = {m.tag: {"donations": m.donations, "received": m.received, "member": m} for m in clan.members}
            
            # RADAR: DOAÇÃO CRUZADA
            if self.last_clan_state:
                donors, receivers = [], []
                for tag, state in current_state.items():
                    if tag in self.last_clan_state:
                        d_diff = state["donations"] - self.last_clan_state[tag]["donations"]
                        r_diff = state["received"] - self.last_clan_state[tag]["received"]
                        if d_diff > 0: donors.append((state["member"], d_diff))
                        if r_diff > 0: receivers.append((state["member"], r_diff))
                
                if donors and receivers:
                    for d_member, d_amount in donors:
                        for r_member, r_amount in receivers:
                            if abs(d_amount - r_amount) <= 5: 
                                await self._log_telemetry(d_member, r_member, 15, f"Doação Sincronizada: {d_member.name} doou tropas ao mesmo tempo que {r_member.name} recebeu.")

            self.last_clan_state = current_state

            # RADAR: SINCRONIA DE COMBATE (Mutex)
            try:
                war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
                if war and war.state == "inWar":
                    current_attacks = {atk.attacker_tag for m in war.clan.members for atk in m.attacks}
                            
                    if self.last_war_attacks:
                        new_attacks = current_attacks - self.last_war_attacks
                        if len(new_attacks) >= 2:
                            attackers = [current_state[tag]["member"] for tag in new_attacks if tag in current_state]
                            for i in range(len(attackers)):
                                for j in range(i+1, len(attackers)):
                                    await self._log_telemetry(attackers[i], attackers[j], 20, "Efeito Fantasma (Mutex): Realizaram ataques coordenados na mesma janela de 5 minutos.")
                    self.last_war_attacks = current_attacks
            except Exception: pass

        except Exception as e:
            logger.error(f"Erro no Radar Comportamental: {e}")

    @behavior_monitor_task.before_loop
    async def before_behavior_monitor(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)


    # ==================== O CÉREBRO DA IA (PROCESSAMENTO CENTRAL) ====================

    def _format_large_number(self, num: int) -> str:
        if num >= 1_000_000_000: return f"{num/1_000_000_000:.1f} Bilhões"
        if num >= 1_000_000: return f"{num/1_000_000:.1f} Milhões"
        return f"{num:,}"

    def _generate_xai_dossier(self, p1: coc.Player, p2: coc.Player, telemetry: Dict) -> Optional[Dict]:
        """Aplica os pesos forenses e gera os pensamentos da IA."""
        stats1 = self._extract_account_stats(p1)
        stats2 = self._extract_account_stats(p2)
        
        if stats1['mass'] >= stats2['mass']:
            main_p, main_s, smurf_p, smurf_s = p1, stats1, p2, stats2
        else:
            main_p, main_s, smurf_p, smurf_s = p2, stats2, p1, stats1

        confidence = 0
        thoughts = []

        # [EIXO 1]: Lexical
        sim = self._get_identity_match(main_p.name, smurf_p.name)
        if sim >= self.MIN_SIMILARITY:
            weight = int(sim * 0.35) 
            confidence += weight
            thoughts.append({"axis": "Lexical", "weight": f"{weight}%", "text": f"Correlação semântica detectada. Radical dos apelidos compartilha {sim}% de identidade."})

        # [EIXO 2]: Mutex / Comportamento (Telemetria do Banco)
        behavior_score = telemetry.get('score', 0)
        if behavior_score > 0:
            weight = min(behavior_score, 45) 
            confidence += weight
            thoughts.append({"axis": "Comportamento (Mutex)", "weight": f"{weight}%", "text": f"Sincronia fantasma detectada. Contas acumularam {behavior_score} pontos de telemetria operando juntas."})
            for log in telemetry.get('logs', [])[-2:]:
                thoughts.append({"axis": "Log de Rede", "weight": "Info", "text": log})

        # [EIXO 3]: Forense de Laboratório (Conta Mula)
        is_mula, mula_score, mula_reason = self._analyze_mula_signature(smurf_p)
        if is_mula:
            weight = 20 
            confidence += weight
            thoughts.append({"axis": "Forense Lab (Mula)", "weight": f"{weight}%", "text": mula_reason})

        # [EIXO 4]: Discrepância de Patente/Massa (Confirmação Auxiliar)
        mass_ratio = main_s['mass'] / max(smurf_s['mass'], 1)
        if mass_ratio > 2.0:
            confidence += 10
            thoughts.append({"axis": "Massa Bruta", "weight": "10%", "text": f"Desnível evolutivo colossal. A conta principal é {mass_ratio:.1f}x mais pesada que a secundária."})
        elif mass_ratio < 1.15 and behavior_score < 15:
            confidence -= 30
            thoughts.append({"axis": "Atenuante", "weight": "-30%", "text": "Risco de Falso Positivo. Evolução paralela quase idêntica, sugerindo dois jogadores reais distintos."})

        confidence = min(max(int(confidence), 0), 99)
        
        if confidence < 50 and behavior_score < 20:
            return None

        risk_label = "Risco Extremo" if confidence >= 85 else ("Alta Suspeita" if confidence >= 65 else "Em Observação")
        risk_color = "var(--color-danger)" if confidence >= 85 else ("var(--color-warning)" if confidence >= 65 else "var(--color-info)")

        return {
            "pair_id": f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}",
            "main_name": main_p.name, "main_tag": main_p.tag,
            "smurf_name": smurf_p.name, "smurf_tag": smurf_p.tag,
            "confidence": confidence,
            "risk_label": risk_label,
            "risk_color": risk_color,
            "thoughts": thoughts
        }

    # ==================== COMANDO DISCORD ====================

    @app_commands.command(name="smurfs", description="🕵️ Executa a Matriz Forense XAI em todo o clã.")
    @app_commands.default_permissions(administrator=True)
    async def slash_analyze_smurfs(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        try:
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            if not clan: return await interaction.followup.send("❌ Erro de comunicação com a Supercell.")

            member_tags = [m.tag for m in clan.members]
            players_full = [p async for p in self.bot.api_client.get_players(member_tags)]

            telemetry_matrix = {}
            if self.db is not None:
                cursor = self.db.smurf_evidence.find({})
                async for doc in cursor: telemetry_matrix[doc["_id"]] = doc

            results = []
            processed = set()

            for i in range(len(players_full)):
                p1 = players_full[i]
                if p1.tag in processed: continue

                for j in range(i + 1, len(players_full)):
                    p2 = players_full[j]
                    if p2.tag in processed: continue

                    pair_id = f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}"
                    telemetry = telemetry_matrix.get(pair_id, {})
                    
                    if self._get_identity_match(p1.name, p2.name) >= self.MIN_SIMILARITY or telemetry.get("score", 0) > 0:
                        dossier = self._generate_xai_dossier(p1, p2, telemetry)
                        if dossier:
                            results.append(dossier)
                            processed.add(dossier["smurf_tag"])

            if not results:
                return await interaction.followup.send("✅ **Clã Limpo:** A XAI não detectou anomalias forenses.")

            results.sort(key=lambda x: x['confidence'], reverse=True)

            embed = discord.Embed(title="📂 XAI FORENSE: DETECÇÃO DE MÚLTIPLAS CONTAS", color=0x2b2d31)
            for r in results[:5]: 
                body = f"👑 **[MAIN] {r['main_name']}** (`{r['main_tag']}`)\n👶 **[SMURF] {r['smurf_name']}** (`{r['smurf_tag']}`)\n\n"
                body += "**🧠 Pensamentos da IA:**\n" + "\n".join([f"▫️ `{t['axis']}`: {t['text']}" for t in r['thoughts']])
                embed.add_field(name=f"Risco: {r['confidence']}% - {r['risk_label']}", value=body, inline=False)
                
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro no slash /smurfs: {e}")
            await interaction.followup.send("❌ Erro fatal ao rodar a Matriz Forense.")

    # ==================== APIs PARA O PAINEL WEB (XAI EXPORT) ====================

    async def get_web_dossier(self) -> List[Dict[str, Any]]:
        """API que varre a base de dados, processa a XAI e entrega o dossiê formatado para o HTML."""
        if self.db is None or not self.bot.api_client: return []
        try:
            cursor = self.db.smurf_evidence.find({"score": {"$gt": 0}})
            db_docs = await cursor.to_list(length=None)
            
            if not db_docs: return []
            
            tags_to_fetch = set()
            for doc in db_docs:
                tags_to_fetch.add(doc["tag1"])
                tags_to_fetch.add(doc["tag2"])
                
            players = {p.tag: p async for p in self.bot.api_client.get_players(tags_to_fetch)}
            
            xai_results = []
            for doc in db_docs:
                p1 = players.get(doc["tag1"])
                p2 = players.get(doc["tag2"])
                if p1 and p2:
                    dossier = self._generate_xai_dossier(p1, p2, doc)
                    if dossier: xai_results.append(dossier)
                    
            xai_results.sort(key=lambda x: x['confidence'], reverse=True)
            return xai_results
            
        except Exception as e:
            logger.error(f"Erro na exportação do dossiê XAI para Web: {e}", exc_info=True)
            return []

    async def absolve_pair(self, pair_id: str) -> Dict[str, str]:
        if self.db is None: return {"status": "error", "message": "Banco offline."}
        try:
            res = await self.db.smurf_evidence.delete_one({"_id": pair_id})
            if res.deleted_count > 0: return {"status": "success", "message": "Absolvido! Matriz limpa."}
            return {"status": "error", "message": "Evidência fantasma ou já processada."}
        except Exception as e: return {"status": "error", "message": str(e)}

    async def condemn_pair(self, pair_id: str) -> Dict[str, str]:
        if self.db is None: return {"status": "error", "message": "Banco offline."}
        w_cog = self.bot.get_cog("Lista de Observação")
        if not w_cog: return {"status": "error", "message": "Módulo de Watchlist desativado."}
        
        try:
            doc = await self.db.smurf_evidence.find_one({"_id": pair_id})
            if not doc: return {"status": "error", "message": "Dossiê não encontrado."}
            
            reason = "Condenado pela IA XAI (Contas Vinculadas)"
            await w_cog.add_to_watchlist(doc['tag1'], "Desconhecido", reason, f"Vinculado a {doc['tag2']}")
            await w_cog.add_to_watchlist(doc['tag2'], "Desconhecido", reason, f"Vinculado a {doc['tag1']}")
            await self.db.smurf_evidence.delete_one({"_id": pair_id})
            
            return {"status": "success", "message": "Contas enviadas para a Watchlist com sucesso."}
        except Exception as e: return {"status": "error", "message": str(e)}

async def setup(bot: commands.Bot):
    await bot.add_cog(SmurfDetectionCog(bot))
