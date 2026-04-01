# -*- coding: utf-8 -*-
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from discord.ext import commands

logger = logging.getLogger("player_analytics_cog")

class PlayerAnalyticsCog(commands.Cog, name="Player Analytics"):
    """Cog de Machine Learning Avançado para Predição Forense de Assiduidade e Clustering."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.scaler = StandardScaler()
        self.kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
        self.rf_model = RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)
        self.is_trained = False
        self.player_stats_cache = pd.DataFrame()

    async def _extract_time_series_data(self) -> pd.DataFrame:
        """Extrai os dados do MongoDB e constrói uma matriz temporal (ordem cronológica)."""
        if self.bot.db is None:
            return pd.DataFrame()

        # Busca as guerras ordenadas da MAIS ANTIGA (1) para a MAIS RECENTE (-1) e puxa até 150
        cursor = self.bot.db.war_history.find({}).sort("war_data.end_time_iso", 1).limit(150)
        
        records = []
        war_idx = 0
        
        async for war in cursor:
            war_id = war.get("_id")
            members = war.get("our_clan_members_in_war", [])
            attacks_per_member = war.get("war_data", {}).get("attacks_per_member", 2)
            
            for member in members:
                tag = member.get("tag")
                attacks = member.get("attacks_made", [])
                attacks_used = len(attacks)
                stars = sum(a.get("stars", 0) for a in attacks)
                destruction = sum(a.get("destruction", 0) for a in attacks)
                
                records.append({
                    "war_idx": war_idx,
                    "player_tag": tag,
                    "name": member.get("name"),
                    "attacks_used": attacks_used,
                    "possible_attacks": attacks_per_member,
                    "stars": stars,
                    "destruction": destruction
                })
            war_idx += 1
            
        return pd.DataFrame(records)

    async def process_and_train(self, clan_tag: str):
        """Pipeline de ML: Feature Engineering -> Random Forest -> K-Means Clustering."""
        df = await self._extract_time_series_data()
        if df.empty:
            logger.warning("Dados insuficientes no banco para treinar os modelos de ML.")
            return

        # 1. ENGENHARIA DE FEATURES (PANDAS)
        df = df.sort_values(by=["player_tag", "war_idx"])
        df["attendance_rate"] = df["attacks_used"] / df["possible_attacks"].clip(lower=1)
        df["stars_per_attack"] = df["stars"] / df["attacks_used"].clip(lower=1)
        df["dest_per_attack"] = df["destruction"] / df["attacks_used"].clip(lower=1)

        # Variáveis de Janela Deslizante (O que o jogador fez ANTES desta guerra específica)
        df["past_wars"] = df.groupby("player_tag").cumcount()
        df["hist_attendance"] = df.groupby("player_tag")["attendance_rate"].transform(lambda x: x.shift(1).expanding().mean()).fillna(0)
        # Momento recente: média das últimas 3 guerras
        df["recent_attendance"] = df.groupby("player_tag")["attendance_rate"].transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean()).fillna(0)
        df["hist_stars"] = df.groupby("player_tag")["stars_per_attack"].transform(lambda x: x.shift(1).expanding().mean()).fillna(0)

        # 2. TREINAMENTO DO MODELO PREDITIVO (RANDOM FOREST)
        # O alvo (target) é descobrir se ele atacou NESTA guerra, baseado no histórico passado.
        train_df = df[df["past_wars"] > 0].copy() # Remove a 1ª guerra de cada um (sem histórico prévio)
        ml_features = ["past_wars", "hist_attendance", "recent_attendance", "hist_stars"]
        
        if len(train_df) > 15:
            X_train = train_df[ml_features]
            y_train = train_df["attendance_rate"]
            self.rf_model.fit(X_train, y_train)
            model_ready = True
        else:
            model_ready = False

        # 3. EXTRAÇÃO DO ESTADO ATUAL DOS JOGADORES
        current_stats = []
        for tag, group in df.groupby("player_tag"):
            past_wars = len(group)
            hist_att = group["attendance_rate"].mean()
            recent_att = group["attendance_rate"].tail(3).mean()
            hist_str = group["stars_per_attack"].mean()
            avg_dest = group["dest_per_attack"].mean()
            
            current_stats.append({
                "player_tag": tag,
                "name": group["name"].iloc[-1], # Pega o nome mais atualizado
                "wars_played": past_wars,
                "past_wars": past_wars,
                "hist_attendance": hist_att,
                "recent_attendance": recent_att,
                "hist_stars": hist_str,
                "avg_destruction": avg_dest
            })
            
        current_df = pd.DataFrame(current_stats)

        # 4. INFERÊNCIA: PREVENDO A PRÓXIMA GUERRA
        if model_ready:
            # A IA calcula a probabilidade preditiva com base nas árvores de decisão
            X_current = current_df[["past_wars", "hist_attendance", "recent_attendance", "hist_stars"]]
            raw_probability = self.rf_model.predict(X_current)
        else:
            # Fallback seguro caso o clã seja recém-criado
            raw_probability = current_df["hist_attendance"]

        # Aplica a Curva de Confiança
        confidence_penalty = 1.0 - np.exp(-current_df["wars_played"] / 4.0)
        current_df["probability"] = (raw_probability * confidence_penalty) * 100.0

        # 5. CLUSTERING E RANQUEAMENTO DE TIERS (K-MEANS)
        cluster_features = current_df[["probability", "hist_stars", "avg_destruction"]].fillna(0)
        
        if len(cluster_features) >= 4:
            scaled_features = self.scaler.fit_transform(cluster_features)
            current_df["cluster"] = self.kmeans.fit_predict(scaled_features)
            
            cluster_centers = current_df.groupby("cluster")[["probability", "hist_stars"]].mean()
            cluster_centers["power_score"] = (cluster_centers["probability"] / 100.0) * 0.6 + (cluster_centers["hist_stars"] / 3.0) * 0.4
            
            ranked_clusters = cluster_centers.sort_values("power_score", ascending=False).index.tolist()
            
            tier_map = {
                ranked_clusters[0]: "General (Elite)",
                ranked_clusters[1]: "Especialista Confiável",
                ranked_clusters[2]: "Incerto / Instável",
                ranked_clusters[3]: "Descartável (Risco)"
            }
            current_df["tier_label"] = current_df["cluster"].map(tier_map)
            
            current_df.loc[current_df["wars_played"] < 4, "tier_label"] = "Novato (Em Avaliação)"
        else:
            current_df["tier_label"] = "Aguardando Dados"

        self.player_stats_cache = current_df
        self.is_trained = True
        logger.info(f"Pipeline ML concluído. Jogadores analisados: {len(current_df)}")

    async def get_player_insights(self, current_roster_tags: List[str]) -> Dict[str, Any]:
        """Formata o JSON de saída, tratando membros sem histórico."""
        if not self.is_trained or self.player_stats_cache.empty:
            return {"error": "Treinamento do modelo em andamento ou sem dados."}
            
        results = []
        for tag in current_roster_tags:
            row = self.player_stats_cache[self.player_stats_cache["player_tag"] == tag]
            
            if not row.empty:
                r = row.iloc[0]
                results.append({
                    "tag": tag,
                    "name": r["name"],
                    "wars_participated": int(r["wars_played"]),
                    "attack_probability": round(min(r["probability"], 100.0), 1),
                    "tier": r.get("tier_label", "Não Classificado"),
                    "avg_stars": round(r["hist_stars"], 2)
                })
            else:
                results.append({
                    "tag": tag,
                    "name": "Novo Membro",
                    "wars_participated": 0,
                    "attack_probability": 0.0,
                    "tier": "Sem Histórico (Novo)",
                    "avg_stars": 0.0
                })
            
        return {"insights": sorted(results, key=lambda x: x["attack_probability"], reverse=True)}

async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerAnalyticsCog(bot))
