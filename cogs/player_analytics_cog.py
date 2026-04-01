# -*- coding: utf-8 -*-
import logging
import pandas as pd
from typing import Dict, List, Any
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from discord.ext import commands

logger = logging.getLogger("player_analytics_cog")

class PlayerAnalyticsCog(commands.Cog, name="Player Analytics"):
    """Cog de Analytics e Machine Learning para analisar assiduidade e desempenho."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.scaler = StandardScaler()
        # K-Means agrupará os jogadores em 4 categorias distintas (Tiers)
        self.kmeans = KMeans(n_clusters=4, random_state=42, n_init='auto')
        self.is_trained = False
        self.player_stats_cache = pd.DataFrame()

    async def _load_raw_player_data(self, clan_tag: str) -> pd.DataFrame:
        """Extrai dados das últimas 50 guerras do banco para um DataFrame Pandas."""
        if self.bot.db is None:
            return pd.DataFrame()

        cursor = self.bot.db.war_history.find({}).sort("war_data.end_time_iso", -1).limit(50)
        
        records = []
        async for war in cursor:
            war_id = war.get("_id")
            members = war.get("our_clan_members_in_war", [])
            
            for member in members:
                tag = member.get("tag")
                # CORREÇÃO: O nome correto do campo no seu banco de dados é "attacks_made"
                attacks = member.get("attacks_made", [])
                attacks_used = len(attacks)
                stars = sum(a.get("stars", 0) for a in attacks)
                destruction = sum(a.get("destruction", 0) for a in attacks)
                
                records.append({
                    "war_id": war_id,
                    "player_tag": tag,
                    "name": member.get("name"),
                    "attacks_used": attacks_used,
                    "possible_attacks": war.get("war_data", {}).get("attacks_per_member", 2),
                    "stars": stars,
                    "destruction": destruction
                })
                
        return pd.DataFrame(records)

    async def process_and_train(self, clan_tag: str):
        """Processa os dados brutos, extrai features e treina a IA."""
        df = await self._load_raw_player_data(clan_tag)
        if df.empty:
            logger.warning("Nenhum dado de guerra encontrado para analytics.")
            return

        # Agrupar por jogador
        stats = df.groupby("player_tag").agg(
            name=("name", "first"),
            wars_played=("war_id", "nunique"),
            total_attacks_used=("attacks_used", "sum"),
            total_possible_attacks=("possible_attacks", "sum"),
            total_stars=("stars", "sum"),
            total_destruction=("destruction", "sum")
        ).reset_index()

        # Engenharia de Features
        stats["attack_rate"] = stats["total_attacks_used"] / stats["total_possible_attacks"].clip(lower=1)
        stats["avg_stars"] = stats["total_stars"] / stats["total_attacks_used"].clip(lower=1)
        stats["avg_destruction"] = stats["total_destruction"] / stats["total_attacks_used"].clip(lower=1)
        
        self.player_stats_cache = stats.fillna(0)

        # Scikit-Learn (Clustering)
        features = self.player_stats_cache[["attack_rate", "avg_stars", "avg_destruction"]]
        
        if len(features) >= 4: 
            features_scaled = self.scaler.fit_transform(features)
            self.player_stats_cache["cluster"] = self.kmeans.fit_predict(features_scaled)
            self._assign_cluster_labels()
            self.is_trained = True
            logger.info(f"Modelos de Analytics treinados com sucesso para {len(stats)} jogadores.")

    def _assign_cluster_labels(self):
        """Traduz a matemática da IA em nomes orgânicos de Tiers."""
        cluster_means = self.player_stats_cache.groupby("cluster")[["attack_rate", "avg_stars"]].mean()
        
        labels = {}
        for cluster_id in cluster_means.index:
            rate = cluster_means.loc[cluster_id, "attack_rate"]
            stars = cluster_means.loc[cluster_id, "avg_stars"]
            
            if rate >= 0.9 and stars >= 2.2:
                labels[cluster_id] = "Carregador (Elite)"
            elif rate >= 0.8 and stars >= 1.5:
                labels[cluster_id] = "Operário Confiável"
            elif rate < 0.5:
                labels[cluster_id] = "Peso Morto (Risco)"
            else:
                labels[cluster_id] = "Inconstante"
                
        self.player_stats_cache["tier_label"] = self.player_stats_cache["cluster"].map(labels)

    async def get_player_insights(self, current_roster_tags: List[str]) -> Dict[str, Any]:
        """Gera o JSON para ser consumido pela Web API."""
        if not self.is_trained or self.player_stats_cache.empty:
            return {"error": "Sem dados suficientes ou em processamento."}
            
        active_stats = self.player_stats_cache[self.player_stats_cache["player_tag"].isin(current_roster_tags)]
        
        results = []
        for _, row in active_stats.iterrows():
            credit_score = min(row["attack_rate"] * 100, 100.0) 
            
            results.append({
                "tag": row["player_tag"],
                "name": row["name"],
                "wars_participated": int(row["wars_played"]),
                "attack_probability": round(credit_score, 1),
                "tier": row.get("tier_label", "Não Classificado"),
                "avg_stars": round(row["avg_stars"], 2)
            })
            
        return {"insights": sorted(results, key=lambda x: x["attack_probability"], reverse=True)}

async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerAnalyticsCog(bot))
