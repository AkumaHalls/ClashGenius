# -*- coding: utf-8 -*-
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from discord.ext import commands

logger = logging.getLogger("player_analytics_cog")

class PlayerAnalyticsCog(commands.Cog, name="Player Analytics"):
    """Cog de Analytics e Machine Learning para analisar assiduidade e risco de jogadores."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.scaler = StandardScaler()
        # K-Means dividirá os jogadores com base em desempenho, não apenas presença
        self.kmeans = KMeans(n_clusters=4, random_state=42, n_init='auto')
        self.is_trained = False
        self.player_stats_cache = pd.DataFrame()

    async def _load_raw_player_data(self, clan_tag: str) -> pd.DataFrame:
        """Extrai as últimas 50 guerras, adicionando o fator de 'idade da guerra' para a IA."""
        if self.bot.db is None:
            return pd.DataFrame()

        cursor = self.bot.db.war_history.find({}).sort("war_data.end_time_iso", -1).limit(50)
        
        records = []
        war_age = 0 # 0 é a guerra mais recente (ontem), 49 é a mais antiga
        
        async for war in cursor:
            war_id = war.get("_id")
            members = war.get("our_clan_members_in_war", [])
            
            for member in members:
                tag = member.get("tag")
                attacks = member.get("attacks_made", [])
                attacks_used = len(attacks)
                stars = sum(a.get("stars", 0) for a in attacks)
                destruction = sum(a.get("destruction", 0) for a in attacks)
                
                records.append({
                    "player_tag": tag,
                    "name": member.get("name"),
                    "attacks_used": attacks_used,
                    "possible_attacks": war.get("war_data", {}).get("attacks_per_member", 2),
                    "stars": stars,
                    "destruction": destruction,
                    "war_age": war_age
                })
            war_age += 1
            
        return pd.DataFrame(records)

    async def process_and_train(self, clan_tag: str):
        """Aplica Decaimento Exponencial e Curvas de Confiança nos dados."""
        df = await self._load_raw_player_data(clan_tag)
        if df.empty:
            logger.warning("Nenhum dado de guerra encontrado para analytics.")
            return

        stats_list = []
        # Avalia o histórico de cada jogador separadamente
        for tag, group in df.groupby("player_tag"):
            total_wars = len(group)
            total_attacks = group["attacks_used"].sum()
            
            group = group.copy()
            # 1. DECAIMENTO EXPONENCIAL: Guerras recentes pesam absurdamente mais que as antigas.
            # Se a guerra for muito velha (war_age alto), o peso matemático dela cai para quase zero.
            group["weight"] = np.exp(-group["war_age"] / 5.0) 
            
            weighted_attacks = (group["attacks_used"] * group["weight"]).sum()
            weighted_possible = (group["possible_attacks"] * group["weight"]).sum()
            
            # Taxa de ataque focada no presente (0.0 a 1.0)
            attack_rate = weighted_attacks / max(weighted_possible, 1.0)
            
            # 2. CURVA DE CONFIANÇA (Laplace): 
            # Mata o problema de "1 guerra = 100%". 
            # 1 Guerra jogada = Confiança de 28%. 6 Guerras = Confiança de 86%.
            confidence = 1.0 - np.exp(-total_wars / 3.0)
            
            # 3. PREDIÇÃO MATEMÁTICA FINAL: A união da assiduidade recente com a confiança da IA.
            probability = (attack_rate * confidence) * 100.0
            
            # Estatísticas brutas para gerar as Tags de Desempenho
            avg_stars = group["stars"].sum() / max(total_attacks, 1)
            avg_dest = group["destruction"].sum() / max(total_attacks, 1)
            
            stats_list.append({
                "player_tag": tag,
                "name": group["name"].iloc[0],
                "wars_played": total_wars,
                "attack_rate": attack_rate, 
                "avg_stars": avg_stars,
                "avg_destruction": avg_dest,
                "probability": probability
            })
            
        self.player_stats_cache = pd.DataFrame(stats_list)

        # 4. K-MEANS CLUSTERING: Separa a galera em 4 Tiers baseados na matemática acima
        features = self.player_stats_cache[["attack_rate", "avg_stars", "avg_destruction"]]
        if len(features) >= 4: 
            features_scaled = self.scaler.fit_transform(features)
            self.player_stats_cache["cluster"] = self.kmeans.fit_predict(features_scaled)
            self._assign_cluster_labels()
            self.is_trained = True
            
    def _assign_cluster_labels(self):
        """Nomeia os grupos formados pela IA com base em suas médias centrais."""
        cluster_means = self.player_stats_cache.groupby("cluster")[["attack_rate", "avg_stars"]].mean()
        labels = {}
        for cluster_id in cluster_means.index:
            rate = cluster_means.loc[cluster_id, "attack_rate"]
            stars = cluster_means.loc[cluster_id, "avg_stars"]
            
            if rate >= 0.80 and stars >= 2.0:
                labels[cluster_id] = "General (Elite)"
            elif rate >= 0.65 and stars >= 1.3:
                labels[cluster_id] = "Especialista Confiável"
            elif rate < 0.40:
                labels[cluster_id] = "Descartável (Risco)"
            else:
                labels[cluster_id] = "Incerto / Instável"
                
        self.player_stats_cache["tier_label"] = self.player_stats_cache["cluster"].map(labels)

    async def get_player_insights(self, current_roster_tags: List[str]) -> Dict[str, Any]:
        """Entrega o dossiê preditivo para o Frontend (incluindo o tratamento de Nulls)."""
        if not self.is_trained or self.player_stats_cache.empty:
            return {"error": "Aguardando volume de dados para treinamento."}
            
        results = []
        for tag in current_roster_tags:
            row = self.player_stats_cache[self.player_stats_cache["player_tag"] == tag]
            
            # Se a IA achou o histórico dele no banco
            if not row.empty:
                r = row.iloc[0]
                results.append({
                    "tag": tag,
                    "wars_participated": int(r["wars_played"]),
                    "attack_probability": round(r["probability"], 1),
                    "tier": r.get("tier_label", "Análise Inconclusiva"),
                    "avg_stars": round(r["avg_stars"], 2)
                })
            # Se o jogador está no clã, mas NUNCA foi pra guerra (Fim do Bug "Null")
            else:
                results.append({
                    "tag": tag,
                    "wars_participated": 0,
                    "attack_probability": 0.0,
                    "tier": "Sem Histórico (Novo)",
                    "avg_stars": 0.0
                })
            
        return {"insights": sorted(results, key=lambda x: x["attack_probability"], reverse=True)}

async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerAnalyticsCog(bot))
