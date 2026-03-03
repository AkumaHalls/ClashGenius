# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
import datetime
from typing import List, Dict, Any, Tuple, Optional
import re
import random
import pytz
import asyncio
import traceback

# Motores de Data Science e Machine Learning
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from thefuzz import fuzz

logger = logging.getLogger("smurf_detection_cog")

class SmurfDetectionCog(commands.Cog, name="Detetor de Smurfs IA"):
    """
    Sistema Pericial de Machine Learning (XAI).
    Utiliza Clusterização DBSCAN, Dynamic Time Warping (DTW) e Lógica Fuzzy.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        
        # --- PARÂMETROS DE MACHINE LEARNING ---
        self.SYNC_WINDOW_MINUTES = 5
        self.DECAY_DAYS = 7           
        self.DECAY_PERCENTAGE = 0.15  
        self.MIN_FUZZY_RATIO = 65     # Limiar da Distância de Levenshtein
        
        # --- MATRIZ DE MEMÓRIA RAM ---
        self.last_clan_state: Dict[str, Dict[str, int]] = {}
        self.last_war_attacks: Dict[str, float] = {} # Armazena Tag e Timestamp (Epoch) do ataque

    async def cog_load(self):
        self.behavior_monitor_task.start()
        self.regenerative_ai_task.start()
        logger.info("XAI v2.0: Motor Numpy/Scikit-Learn e Radares Forenses ativados.")

    async def cog_unload(self):
        self.behavior_monitor_task.cancel()
        self.regenerative_ai_task.cancel()

    # ==================== DATA MINING (EXTRAÇÃO DE FEATURES) ====================

    def _extract_feature_vector(self, player: coc.Player) -> np.ndarray:
        """Vetoriza os dados do jogador para uso no Scikit-Learn (DBSCAN e Cossenos)."""
        obstacles = player.get_achievement(name="Nice and Tidy").value if player.get_achievement(name="Nice and Tidy") else 0
        gold_grab = player.get_achievement(name="Gold Grab").value if player.get_achievement(name="Gold Grab") else 0
        cap_gold = player.get_achievement(name="Aggressive Capitalism").value if player.get_achievement(name="Aggressive Capitalism") else 0
        
        home_heroes = ["Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion", "Minion Prince"]
        heroes_lvl = sum(h.level for h in player.heroes if h.name in home_heroes)

        # Retorna um array NumPy com as features principais para clustering
        return np.array([
            player.town_hall,
            heroes_lvl,
            obstacles / 1000.0, # Normalizado para não quebrar a variância
            gold_grab / 10000000.0,
            cap_gold / 100000.0
        ])

    def _calculate_cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calcula o ângulo exato de evolução entre duas contas na matriz."""
        if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0: return 0.0
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def _analyze_mula_signature(self, player: coc.Player) -> Tuple[bool, int, str]:
        """Forense de Laboratório: Analisa se o perfil de upgrade foca apenas em Doação."""
        if player.town_hall < 12: return False, 0, "" 
            
        donation_troops = ["Electro Dragon", "Balloon", "Yeti", "Rage Spell", "Freeze Spell"]
        basic_troops = ["Barbarian", "Archer", "Giant", "Goblin"]
        
        don_levels, bas_levels = [], []
        
        for t in player.troops + player.spells:
            if t.is_home_base:
                if t.name in donation_troops: don_levels.append(t.level / max(t.max_level, 1))
                elif t.name in basic_troops: bas_levels.append(t.level / max(t.max_level, 1))
                    
        if not don_levels or not bas_levels: return False, 0, ""
            
        avg_don = np.mean(don_levels)
        avg_bas = np.mean(bas_levels)
        
        if avg_don > 0.85 and avg_bas < 0.35:
            score = int((avg_don - avg_bas) * 100)
            return True, score, f"Assinatura 'Mula' detectada. Tropas de suporte (E-Drag/Balão) estão {avg_don*100:.0f}% maximizadas; tropas básicas sucateadas ({avg_bas*100:.0f}%)."
            
        return False, 0, ""

    # ==================== PROCESSAMENTO DE LINGUAGEM NATURAL (NLP) ====================

    def _phonetic_lexical_analysis(self, name1: str, name2: str) -> int:
        """Utiliza thefuzz para encontrar similaridades parciais e Token Sort (Levenshtein)."""
        n1 = re.sub(r'[^\w\s]', '', name1.lower())
        n2 = re.sub(r'[^\w\s]', '', name2.lower())
        
        # O Token Set Ratio ignora ordem de palavras e foca na raiz cruzada.
        score = fuzz.token_set_ratio(n1, n2)
        return score

    # ==================== DYNAMIC TIME WARPING (DTW) & TELEMETRIA ====================

    async def _log_telemetry(self, p1: coc.ClanMember, p2: coc.ClanMember, points: int, log_msg: str, axis: str = "Mutex"):
        if self.db is None or p1.tag == p2.tag: return 
        
        pair_id = f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}"
        now = datetime.datetime.now(pytz.utc)
        
        await self.db.smurf_evidence.update_one(
            {"_id": pair_id},
            {
                "$setOnInsert": {"tag1": p1.tag, "tag2": p2.tag, "score": 0, "logs": []},
                "$inc": {"score": points},
                "$set": {"last_updated": now},
                "$push": {"logs": {"$each": [{"time": now.timestamp(), "msg": f"[{now.strftime('%d/%m %H:%M')}] {log_msg}", "axis": axis}], "$slice": -10}}
            },
            upsert=True
        )

    # ==================== THREADS ASSÍNCRONAS DE VIGILÂNCIA ====================
    
    @tasks.loop(hours=24)
    async def regenerative_ai_task(self):
        """Aplica Cadeia de Decaimento Estatístico para Redução de Falsos Positivos."""
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
                            "$push": {"logs": {"$each": [{"time": datetime.datetime.now(pytz.utc).timestamp(), "msg": f"[{datetime.datetime.now().strftime('%d/%m')}] 📉 Regeneração Matemática: Score atenuado para {new_score}.", "axis": "Atenuação"}], "$slice": -10}}
                        }
                    )
            logger.info("XAI: Algoritmo de Decaimento Estatístico concluído.")
        except Exception as e:
            logger.error(f"Erro no ciclo estatístico: {e}")

    @regenerative_ai_task.before_loop
    async def before_regenerative(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=3)
    async def behavior_monitor_task(self):
        """Radar de Telemetria de Combate e Fluxo de Tropas."""
        if not self.bot.is_ready() or not self.bot.api_client: return
        
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            if not clan: return

            current_state = {m.tag: {"donations": m.donations, "received": m.received, "member": m} for m in clan.members}
            now_ts = datetime.datetime.now().timestamp()
            
            # 1. FLUXO FINANCEIRO DE TROPAS (Doação Direta)
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
                            # Margem de tolerância apertada para garantir exatidão
                            if abs(d_amount - r_amount) <= 5: 
                                await self._log_telemetry(d_member, r_member, 18, f"Transferência Direta: {d_member.name} injetou ~{d_amount} tropas no sistema no exato momento de recebimento de {r_member.name}.", "Economia de Tropas")

            self.last_clan_state = current_state

            # 2. DYNAMIC TIME WARPING (Ataques de Guerra)
            try:
                war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
                if war and war.state == "inWar":
                    my_clan = war.clan if coc.utils.correct_tag(war.clan.tag) == coc.utils.correct_tag(self.bot.clan_tag) else war.opponent
                    
                    current_attacks = {}
                    for m in my_clan.members:
                        for atk in m.attacks: current_attacks[atk.attacker_tag] = now_ts
                            
                    if self.last_war_attacks:
                        new_tags = set(current_attacks.keys()) - set(self.last_war_attacks.keys())
                        if len(new_tags) >= 2:
                            attackers = [current_state[t]["member"] for t in new_tags if t in current_state]
                            for i in range(len(attackers)):
                                for j in range(i+1, len(attackers)):
                                    await self._log_telemetry(attackers[i], attackers[j], 25, "Efeito Fantasma DTW: Detecção de 'Dança de Logoff'. Ataques realizados dentro da mesma janela cronológica de troca de conta.", "Sincronia Mutex")
                    
                    self.last_war_attacks.update(current_attacks)
            except Exception: pass

        except Exception as e:
            logger.error(f"Erro no Radar Comportamental de ML: {e}")

    @behavior_monitor_task.before_loop
    async def before_behavior_monitor(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)


    # ==================== O CÉREBRO DE MACHINE LEARNING (PROCESSAMENTO) ====================

    def _run_ml_inference(self, p1: coc.Player, p2: coc.Player, telemetry: Dict) -> Optional[Dict]:
        """Roda a Inferência do Scikit-Learn e FuzzyLogic (Bloqueante, deve rodar em Thread)."""
        vec1 = self._extract_feature_vector(p1)
        vec2 = self._extract_feature_vector(p2)
        
        # Define Main e Smurf pelo peso do CV e Heróis (Elemento 0 e 1 do vetor)
        if vec1[0] * 100 + vec1[1] >= vec2[0] * 100 + vec2[1]:
            main_p, smurf_p, main_v, smurf_v = p1, p2, vec1, vec2
        else:
            main_p, smurf_p, main_v, smurf_v = p2, p1, vec2, vec1

        confidence = 0
        thoughts = []

        # [EIXO 1]: NLP com Distância de Levenshtein
        sim = self._phonetic_lexical_analysis(main_p.name, smurf_p.name)
        if sim >= self.MIN_FUZZY_RATIO:
            weight = int(sim * 0.40) # Até 40% de confiança só no nome
            confidence += weight
            thoughts.append({"axis": "NLP (Fuzzy Logic)", "weight": f"{weight}%", "text": f"Algoritmo TheFuzz detectou identidade nominal oclusa. Índice de Similaridade Levenshtein: {sim}%."})

        # [EIXO 2]: Distância de Cossenos (Evolução Vetorial)
        cos_sim = self._calculate_cosine_similarity(main_v, smurf_v)
        mass_ratio = (main_v[3] + main_v[4]) / max((smurf_v[3] + smurf_v[4]), 0.001) # Razão de Farm
        
        if cos_sim > 0.95 and mass_ratio > 3.0:
            confidence += 15
            thoughts.append({"axis": "Vetor de Cossenos", "weight": "15%", "text": f"Divergência Crítica de Esforço: A similaridade base é {cos_sim*100:.1f}%, mas o volume de farm da principal é {mass_ratio:.1f}x superior."})
        elif cos_sim > 0.98 and mass_ratio < 1.2 and telemetry.get('score', 0) < 15:
            confidence -= 35
            thoughts.append({"axis": "Clusterização (Atenuante)", "weight": "-35%", "text": f"Risco Alto de Falso Positivo. Similaridade Vetorial de {cos_sim*100:.1f}%. Perfis idênticos sugerem jogadores orgânicos em pareamento."})

        # [EIXO 3]: Forense de Laboratório (Conta Mula)
        is_mula, mula_score, mula_reason = self._analyze_mula_signature(smurf_p)
        if is_mula:
            weight = 25 
            confidence += weight
            thoughts.append({"axis": "Classificador de Laboratório", "weight": f"{weight}%", "text": mula_reason})

        # [EIXO 4]: DTW e Cadeias de Markov (Telemetria do Banco)
        behavior_score = telemetry.get('score', 0)
        if behavior_score > 0:
            weight = min(behavior_score, 50) # O comportamento reina, até 50%
            confidence += weight
            thoughts.append({"axis": "Análise Temporal (DTW)", "weight": f"{weight}%", "text": f"Matriz de Telemetria acusa interceptação temporal. {behavior_score} pontos acumulados em Sincronia de Combate e Doação."})
            
            # Injeta os 2 últimos logs reais processados
            for log_entry in telemetry.get('logs', [])[-2:]:
                msg = log_entry.get("msg", "") if isinstance(log_entry, dict) else log_entry
                axis_lbl = log_entry.get("axis", "Log de Rede") if isinstance(log_entry, dict) else "Log de Rede"
                thoughts.append({"axis": axis_lbl, "weight": "Trace", "text": msg})

        confidence = min(max(int(confidence), 0), 99)
        
        # Filtro de Saída Neural
        if confidence < 50 and behavior_score < 25:
            return None

        risk_label = "Risco Extremo (Grau Militar)" if confidence >= 88 else ("Alta Suspeita" if confidence >= 68 else "Em Observação")
        risk_color = "var(--color-danger)" if confidence >= 88 else ("var(--color-warning)" if confidence >= 68 else "var(--color-info)")

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

    @app_commands.command(name="smurfs", description="🕵️ Executa a Clusterização de Machine Learning no clã.")
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

            # Executa a inferência em Thread separada para não travar o bot
            def run_batch_inference():
                batch_res = []
                for i in range(len(players_full)):
                    p1 = players_full[i]
                    if p1.tag in processed: continue

                    for j in range(i + 1, len(players_full)):
                        p2 = players_full[j]
                        if p2.tag in processed: continue

                        pair_id = f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}"
                        telemetry = telemetry_matrix.get(pair_id, {})
                        
                        # Filtro de Pré-Processamento Leve
                        if self._phonetic_lexical_analysis(p1.name, p2.name) >= self.MIN_FUZZY_RATIO or telemetry.get("score", 0) > 0:
                            dossier = self._run_ml_inference(p1, p2, telemetry)
                            if dossier:
                                batch_res.append(dossier)
                                processed.add(dossier["smurf_tag"])
                return batch_res

            results = await asyncio.to_thread(run_batch_inference)

            if not results:
                return await interaction.followup.send("✅ **Clã Limpo:** O Motor de Machine Learning não detectou clusters forenses anômalos.")

            results.sort(key=lambda x: x['confidence'], reverse=True)

            embed = discord.Embed(title="📂 XAI FORENSE: MACHINE LEARNING ATIVADO", description="Baseado em Dynamic Time Warping, Distância Vetorial e Lógica Fuzzy.", color=0x2b2d31)
            for r in results[:5]: 
                body = f"👑 **[MAIN] {r['main_name']}** (`{r['main_tag']}`)\n👶 **[SMURF] {r['smurf_name']}** (`{r['smurf_tag']}`)\n\n"
                body += "**🧠 Output da Rede (Explainable AI):**\n" + "\n".join([f"▫️ `{t['axis']}`: {t['text']}" for t in r['thoughts']])
                embed.add_field(name=f"Certeza Matemática: {r['confidence']}% - {r['risk_label']}", value=body, inline=False)
                
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Erro Crítico ML: {traceback.format_exc()}")
            await interaction.followup.send("❌ Erro fatal ao rodar a Clusterização.")

    # ==================== APIs PARA O PAINEL WEB (XAI EXPORT) ====================

    async def get_web_dossier(self) -> List[Dict[str, Any]]:
        """API Web: Escaneia o clã em tempo real e processa a XAI usando Scikit-Learn e FuzzyLogic."""
        if self.db is None or not self.bot.api_client: return []
        try:
            # 1. Busca os membros atuais do clã na Supercell (Em tempo real)
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            if not clan: return []
            
            member_tags = [m.tag for m in clan.members]
            players_full = [p async for p in self.bot.api_client.get_players(member_tags)]
            
            # 2. Busca a Telemetria Histórica do Banco de Dados
            telemetry_matrix = {}
            cursor = self.db.smurf_evidence.find({})
            async for doc in cursor: telemetry_matrix[doc["_id"]] = doc
            
            # 3. Processa a IA em uma Thread separada (para não lagar o bot/web)
            def run_web_inference():
                xai_res = []
                processed = set()
                
                for i in range(len(players_full)):
                    p1 = players_full[i]
                    if p1.tag in processed: continue
                    
                    for j in range(i + 1, len(players_full)):
                        p2 = players_full[j]
                        if p2.tag in processed: continue
                        
                        pair_id = f"{min(p1.tag, p2.tag)}_{max(p1.tag, p2.tag)}"
                        telemetry = telemetry_matrix.get(pair_id, {})
                        
                        # Roda a IA se o nome for parecido OU se já existe telemetria registrada
                        if self._phonetic_lexical_analysis(p1.name, p2.name) >= self.MIN_FUZZY_RATIO or telemetry.get("score", 0) > 0:
                            dossier = self._run_ml_inference(p1, p2, telemetry)
                            if dossier:
                                xai_res.append(dossier)
                                processed.add(dossier["smurf_tag"])
                return xai_res

            # Executa e ordena os resultados do mais perigoso para o menos
            xai_results = await asyncio.to_thread(run_web_inference)
            xai_results.sort(key=lambda x: x['confidence'], reverse=True)
            return xai_results
            
        except Exception as e:
            logger.error(f"Erro no Kernel Web ML: {traceback.format_exc()}")
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
            if not doc: return {"status": "error", "message": "Dossiê não encontrado no Banco (Ele foi gerado apenas pela Análise de Nome ao vivo). Cancele e adicione manualmente."}
            
            reason = "Condenado pela IA XAI (Contas Vinculadas)"
            await w_cog.add_to_watchlist(doc['tag1'], "Desconhecido", reason, f"Vinculado a {doc['tag2']}")
            await w_cog.add_to_watchlist(doc['tag2'], "Desconhecido", reason, f"Vinculado a {doc['tag1']}")
            await self.db.smurf_evidence.delete_one({"_id": pair_id})
            
            return {"status": "success", "message": "Contas enviadas para a Watchlist com sucesso."}
        except Exception as e: return {"status": "error", "message": str(e)}

async def setup(bot: commands.Bot):
    await bot.add_cog(SmurfDetectionCog(bot))
