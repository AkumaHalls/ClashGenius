# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands
import difflib
import coc
import datetime
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
import re

logger = logging.getLogger("smurf_detection_cog")

class SmurfDetectionCog(commands.Cog, name="Detetor de Smurfs IA"):
    """Sistema avançado de IA para detecção de contas secundárias com análise multicamada."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        
        # Pesos para o sistema de pontuação (ajustáveis conforme necessário)
        self.weights = {
            'db_link': 100,              # Vínculo confirmado no banco = 100% certeza
            'name_exact': 50,            # Nomes muito similares
            'name_high': 35,             # Nomes similares
            'name_moderate': 20,         # Nomes moderadamente similares
            'donation_pattern': 25,      # Padrão de doações similar
            'rush_pattern': 20,          # Ambos rushados de forma similar
            'activity_sync': 15,         # Atividade sincronizada suspeita
            'clan_history': 18,          # Histórico de clãs similar
            'hero_neglect': 15,          # Padrão de heróis negligenciados
            'war_pattern': 12,           # Padrão de guerra similar
            'trophy_manipulation': 10,   # Manipulação de troféus
            'builder_neglect': 8,        # Base do construtor negligenciada
        }

    # ==================== NORMALIZAÇÃO E SIMILARIDADE ====================
    
    def _normalize_name(self, name: str) -> str:
        """Normalização avançada de nomes para comparação."""
        name = name.lower().strip()
        
        # Remove emojis e caracteres especiais
        name = re.sub(r'[^\w\s]', '', name)
        
        # Lista expandida de sufixos/prefixos comuns
        ignore_patterns = [
            r'\bmini\b', r'\bsec\b', r'\bconta\b', r'\bjr\b', r'\bsr\b',
            r'\bv[0-9]\b', r'\b2\b', r'\b3\b', r'\bbr\b', r'\bpl\b',
            r'\bclash\b', r'\bth\d+\b', r'\bcv\d+\b', r'\balt\b',
            r'\bmain\b', r'\bprincipal\b', r'\bsmurf\b', r'\bfeeder\b',
            r'\bdonador\b', r'\bdoa\b', r'\bwar\b', r'\bguerra\b'
        ]
        
        for pattern in ignore_patterns:
            name = re.sub(pattern, '', name)
        
        # Remove espaços, números e underscores
        name = re.sub(r'[0-9_\-\s]', '', name)
        
        return name

    def check_name_similarity(self, name1: str, name2: str) -> Dict[str, float]:
        """
        Análise avançada de similaridade com múltiplas métricas.
        Retorna: dict com 'score', 'normalized_score', 'raw_score'
        """
        # Similaridade bruta
        raw_score = difflib.SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
        
        # Similaridade normalizada (sem sufixos)
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)
        
        if not n1 or not n2:
            normalized_score = 0.0
        else:
            normalized_score = difflib.SequenceMatcher(None, n1, n2).ratio()
        
        # Verifica padrões comuns de nomes relacionados
        bonus = 0.0
        
        # Verifica se um nome contém o outro
        if n1 and n2:
            if n1 in n2 or n2 in n1:
                bonus = 0.15
            
            # Verifica prefixos/sufixos numéricos (ex: Player1, Player2)
            base1 = re.sub(r'\d+$', '', n1)
            base2 = re.sub(r'\d+$', '', n2)
            if base1 and base2 and base1 == base2:
                bonus = 0.25
        
        final_score = min(1.0, max(raw_score, normalized_score) + bonus)
        
        return {
            'score': final_score,
            'normalized_score': normalized_score,
            'raw_score': raw_score,
            'bonus': bonus
        }

    # ==================== ANÁLISE DE BANCO DE DADOS ====================
    
    async def get_confirmed_links(self, member_tags: List[str]) -> Dict[int, List[str]]:
        """
        Busca vínculos confirmados no banco de dados.
        Retorna: {discord_id: [tag1, tag2, ...]}
        """
        if self.db is None:
            return {}
        
        duplicates = defaultdict(list)
        try:
            cursor = self.db.users.find({"player_tag": {"$in": member_tags}})
            
            discord_map = defaultdict(set)
            async for doc in cursor:
                d_id = doc.get("discord_id")
                tag = doc.get("player_tag")
                if d_id and tag:
                    discord_map[d_id].add(tag)
            
            # Retorna apenas usuários com múltiplas contas
            for d_id, tags in discord_map.items():
                if len(tags) > 1:
                    duplicates[d_id] = list(tags)
                    
        except Exception as e:
            logger.error(f"Erro ao buscar vínculos no DB: {e}", exc_info=True)
        
        return duplicates

    # ==================== ANÁLISES INDIVIDUAIS ====================
    
    def analyze_rush_pattern(self, member: coc.Player) -> Dict:
        """Detecta padrão de conta rushada."""
        score = 0
        details = []
        
        th = member.town_hall
        # Agora usando o objeto Player, war_stars deve existir
        stars = getattr(member, 'war_stars', 0)
        
        # Expectativa base de estrelas por TH (conservador)
        expected_stars = {
            7: 50, 8: 100, 9: 150, 10: 250, 11: 400,
            12: 600, 13: 850, 14: 1100, 15: 1400, 16: 1700
        }
        
        if th in expected_stars:
            expected = expected_stars[th]
            deficit = expected - stars
            
            if deficit > expected * 0.7:  # 70% abaixo do esperado
                score = 20
                details.append(f"Severamente rushado: {stars}/{expected} ⭐ esperadas")
            elif deficit > expected * 0.5:  # 50% abaixo
                score = 15
                details.append(f"Muito rushado: {stars}/{expected} ⭐ esperadas")
            elif deficit > expected * 0.3:  # 30% abaixo
                score = 10
                details.append(f"Rushado: {stars}/{expected} ⭐ esperadas")
        
        return {'score': score, 'details': details}

    def analyze_donation_pattern(self, member: coc.Player) -> Dict:
        """Detecta padrão de conta feeder/doadora."""
        score = 0
        details = []
        
        donations = member.donations
        received = member.received
        # attack_wins só existe no objeto Player completo
        attacks = getattr(member, 'attack_wins', 0)
        
        # Padrão feeder clássico: muitas doações, pouco ataque
        if donations > 1000:
            if attacks < 10:
                score = 25
                details.append(f"Feeder extremo: {donations} doações, apenas {attacks} vitórias")
            elif attacks < 50:
                score = 18
                details.append(f"Padrão feeder: {donations} doações, {attacks} vitórias")
        
        # Proporção doação/recebimento muito alta
        if received > 0:
            ratio = donations / received
            if ratio > 10:
                score += 8
                details.append(f"Proporção anormal doação/recebimento: {ratio:.1f}:1")
        elif donations > 500:  # Doa muito mas não recebe nada
            score += 10
            details.append(f"Doa {donations} mas nunca recebe tropas")
        
        return {'score': score, 'details': details}

    def analyze_builder_base(self, member: coc.Player) -> Dict:
        """Analisa negligência da Base do Construtor."""
        score = 0
        details = []
        
        try:
            th = member.town_hall
            # builder_hall existe no objeto Player completo
            bh = member.builder_hall if hasattr(member, 'builder_hall') else 0
            
            if bh > 0:
                gap = th - bh
                
                if gap >= 7:
                    score = 8
                    details.append(f"BB muito negligenciada: CV{th} vs BH{bh}")
                elif gap >= 5:
                    score = 5
                    details.append(f"BB negligenciada: CV{th} vs BH{bh}")
        except:
            pass
        
        return {'score': score, 'details': details}

    def analyze_trophy_pattern(self, member: coc.Player) -> Dict:
        """Detecta manipulação de troféus."""
        score = 0
        details = []
        
        trophies = member.trophies
        th = member.town_hall
        
        # Troféus muito baixos para o TH (conta dropando troféus)
        expected_min = {
            10: 1800, 11: 2200, 12: 2600,
            13: 3000, 14: 3400, 15: 3800, 16: 4200
        }
        
        if th in expected_min:
            if trophies < expected_min[th] * 0.5:
                score = 10
                details.append(f"Troféus muito baixos: {trophies} (CV{th})")
            elif trophies < expected_min[th] * 0.7:
                score = 5
                details.append(f"Troféus baixos: {trophies} (CV{th})")
        
        return {'score': score, 'details': details}

    def analyze_war_pattern(self, member: coc.Player) -> Dict:
        """Analisa padrão de participação em guerras."""
        score = 0
        details = []
        
        try:
            # Tenta usar war_preference se disponível (coc.py), senão fallback
            # Normalmente no coc.py é war_opted_in (bool) ou war_preference (str 'in'/'out')
            opted_in = getattr(member, 'war_opted_in', None)
            
            # Se for False (está fora), analisa
            if opted_in is False:
                 # Não participa de guerras mas tem conta no clã pode ser smurf de doação
                if member.donations > 500:
                    score = 12
                    details.append("Fora de guerra mas doa muito (possível feeder)")
        except:
            pass
        
        return {'score': score, 'details': details}

    def analyze_account_depth(self, member: coc.Player) -> Dict:
        """Análise completa e agregada da conta."""
        total_score = 0
        all_details = []
        analyses = {}
        
        # Executa todas as análises individuais
        rush = self.analyze_rush_pattern(member)
        donation = self.analyze_donation_pattern(member)
        builder = self.analyze_builder_base(member)
        trophy = self.analyze_trophy_pattern(member)
        war = self.analyze_war_pattern(member)
        
        # Agrega resultados
        for name, analysis in [
            ('rush', rush), ('donation', donation), ('builder', builder),
            ('trophy', trophy), ('war', war)
        ]:
            analyses[name] = analysis
            total_score += analysis['score']
            all_details.extend(analysis['details'])
        
        return {
            'total_score': total_score,
            'details': all_details,
            'analyses': analyses
        }

    # ==================== ANÁLISE COMPARATIVA ====================
    
    def compare_activity_patterns(self, m1: coc.Player, m2: coc.Player) -> Dict:
        """Compara padrões de atividade entre duas contas."""
        score = 0
        details = []
        
        # Compara proporções de doação
        try:
            if m1.donations > 100 and m2.donations > 100:
                r1 = m1.donations / (m1.received + 1)
                r2 = m2.donations / (m2.received + 1)
                
                if abs(r1 - r2) < 1.0:  # Proporções muito similares
                    score += 15
                    details.append(f"Padrão de doação similar: {r1:.1f} vs {r2:.1f}")
        except:
            pass
        
        # Compara níveis de troféus (contas sincronizadas)
        trophy_diff = abs(m1.trophies - m2.trophies)
        if trophy_diff < 200:  # Muito próximos
            score += 8
            details.append(f"Troféus sincronizados: {m1.trophies} vs {m2.trophies}")
        
        return {'score': score, 'details': details}

    # ==================== SISTEMA DE PONTUAÇÃO ====================
    
    def calculate_confidence(self, total_points: float) -> Tuple[str, str, discord.Color]:
        """
        Calcula nível de confiança baseado na pontuação.
        Retorna: (nível, emoji, cor)
        """
        if total_points >= 80:
            return ("ALTÍSSIMA", "🔴", discord.Color.red())
        elif total_points >= 60:
            return ("ALTA", "🟠", discord.Color.orange())
        elif total_points >= 40:
            return ("MÉDIA", "🟡", discord.Color.gold())
        elif total_points >= 25:
            return ("BAIXA", "🟢", discord.Color.green())
        else:
            return ("MÍNIMA", "⚪", discord.Color.light_gray())

    async def analyze_pair(self, m1: coc.Player, m2: coc.Player, 
                           confirmed_links: Dict) -> Optional[Dict]:
        """
        Análise completa entre duas contas.
        Retorna dict com score e evidências ou None se não suspeito.
        """
        total_score = 0
        evidence = []
        
        # 1. Verifica se está no banco de dados (prioridade máxima)
        db_linked = False
        for d_id, tags in confirmed_links.items():
            if m1.tag in tags and m2.tag in tags:
                db_linked = True
                total_score += self.weights['db_link']
                evidence.append("✅ **CONFIRMADO**: Vinculadas ao mesmo Discord ID no banco")
                break
        
        # 2. Análise de similaridade de nome
        if not db_linked:  # Só analisa se não tiver confirmação do DB
            name_sim = self.check_name_similarity(m1.name, m2.name)
            
            if name_sim['score'] >= 0.85:
                points = self.weights['name_exact']
                total_score += points
                evidence.append(f"📝 Nomes muito similares: **{name_sim['score']*100:.1f}%** de correspondência")
            elif name_sim['score'] >= 0.70:
                points = self.weights['name_high']
                total_score += points
                evidence.append(f"📝 Nomes similares: **{name_sim['score']*100:.1f}%**")
            elif name_sim['score'] >= 0.55:
                points = self.weights['name_moderate']
                total_score += points
                evidence.append(f"📝 Nomes moderadamente similares: **{name_sim['score']*100:.1f}%**")
        
        # 3. Análise de padrões de atividade
        activity = self.compare_activity_patterns(m1, m2)
        if activity['score'] > 0:
            total_score += activity['score']
            evidence.extend([f"⚡ {d}" for d in activity['details']])
        
        # 4. Compara padrões de rush (ambos rushados de forma similar)
        rush1 = self.analyze_rush_pattern(m1)
        rush2 = self.analyze_rush_pattern(m2)
        if rush1['score'] >= 10 and rush2['score'] >= 10:
            total_score += self.weights['rush_pattern']
            evidence.append(f"🚀 Ambos com padrão rushado similar")
        
        # Só retorna se houver suspeita mínima
        if total_score >= 20 or db_linked:
            return {
                'm1': m1,
                'm2': m2,
                'score': total_score,
                'evidence': evidence,
                'db_linked': db_linked
            }
        
        return None

    # ==================== COMANDO PRINCIPAL ====================
    
    @app_commands.command(name="smurfs", description="🕵️ IA Avançada: Análise multicamada para detecção de contas secundárias")
    async def slash_analyze_smurfs(self, interaction: discord.Interaction):
        """Comando principal de análise."""
        
        # Verificação de permissões
        if interaction.user.id != interaction.guild.owner_id:
            user_roles = [r.id for r in interaction.user.roles]
            allowed = False
            
            if hasattr(self.bot, 'leader_role_id') and self.bot.leader_role_id in user_roles:
                allowed = True
            if hasattr(self.bot, 'coleader_role_id') and self.bot.coleader_role_id in user_roles:
                allowed = True
            if interaction.user.guild_permissions.administrator:
                allowed = True
            
            if not allowed:
                await interaction.response.send_message(
                    "❌ Apenas Líderes, Co-Líderes e Administradores podem usar esta IA.",
                    ephemeral=True
                )
                return

        await interaction.response.defer(thinking=True)

        try:
            # Obtém dados básicos do clã para pegar as tags
            clan = await self.bot.get_clan_data_with_cache(self.bot.clan_tag)
            if not clan:
                await interaction.followup.send("❌ Erro ao obter dados do clã.")
                return

            member_tags = [m.tag for m in clan.members]
            
            # --- MODIFICAÇÃO IMPORTANTE: BUSCA DADOS COMPLETOS ---
            # O objeto ClanMember não tem war_stars, então buscamos objetos Player completos
            members = []
            try:
                # get_players retorna um AsyncIterator na versão moderna do coc.py
                async for player in self.bot.api_client.get_players(member_tags):
                    members.append(player)
            except Exception as e:
                logger.error(f"Erro ao buscar detalhes completos dos jogadores: {e}")
                # Fallback: Tenta continuar com o que tem, mas avisa no log
                # Se falhar totalmente, aborta
                await interaction.followup.send("❌ Erro ao buscar detalhes profundos dos jogadores (API). Tente novamente mais tarde.")
                return

            if not members:
                 await interaction.followup.send("❌ Nenhum jogador encontrado para análise.")
                 return

            # ===== FASE 1: ANÁLISE DE VÍNCULOS NO BANCO =====
            confirmed_links = await self.get_confirmed_links(member_tags)
            
            # ===== FASE 2: ANÁLISE INDIVIDUAL DE COMPORTAMENTO =====
            individual_suspects = []
            for member in members:
                analysis = self.analyze_account_depth(member)
                
                # Considera suspeito se score >= 30
                if analysis['total_score'] >= 30:
                    level, emoji, _ = self.calculate_confidence(analysis['total_score'])
                    individual_suspects.append({
                        'member': member,
                        'score': analysis['total_score'],
                        'level': level,
                        'emoji': emoji,
                        'details': analysis['details']
                    })
            
            # Ordena por score
            individual_suspects.sort(key=lambda x: x['score'], reverse=True)
            
            # ===== FASE 3: ANÁLISE COMPARATIVA (PARES) =====
            pair_suspects = []
            processed = set()
            
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    m1, m2 = members[i], members[j]
                    pair_id = tuple(sorted([m1.tag, m2.tag]))
                    
                    if pair_id in processed:
                        continue
                    
                    result = await self.analyze_pair(m1, m2, confirmed_links)
                    if result:
                        level, emoji, _ = self.calculate_confidence(result['score'])
                        result['level'] = level
                        result['emoji'] = emoji
                        pair_suspects.append(result)
                        processed.add(pair_id)
            
            # Ordena pares por score
            pair_suspects.sort(key=lambda x: x['score'], reverse=True)
            
            # ===== CONSTRUÇÃO DO RELATÓRIO =====
            
            embed = discord.Embed(
                title="🕵️ Relatório de Inteligência Artificial - Detecção de Smurfs",
                description=f"**Análise Multicamada Completa**\n"
                           f"👥 **{len(members)}** membros analisados\n"
                           f"🔍 **{len(pair_suspects)}** pares suspeitos identificados\n"
                           f"⚠️ **{len(individual_suspects)}** contas com comportamento suspeito\n"
                           f"✅ **{len(confirmed_links)}** vínculos confirmados no banco de dados",
                color=discord.Color.dark_purple(),
                timestamp=datetime.datetime.utcnow()
            )
            
            # SEÇÃO 1: Vínculos Confirmados (DB) - Prioridade Máxima
            if confirmed_links:
                text = ""
                for d_id, tags in list(confirmed_links.items())[:5]:
                    user_obj = self.bot.get_user(d_id)
                    user_name = user_obj.name if user_obj else f"ID: {d_id}"
                    
                    accounts = []
                    for tag in tags:
                        # Busca o jogador na lista 'members' já carregada para evitar nova chamada
                        m = next((p for p in members if p.tag == tag), None)
                        if m:
                            accounts.append(f"**{m.name}** (CV{m.town_hall})")
                        else:
                            accounts.append(f"Tag: {tag}")
                    
                    text += f"🔴 **{user_name}**\n└ {' + '.join(accounts)}\n\n"
                
                if len(confirmed_links) > 5:
                    text += f"*...e mais {len(confirmed_links) - 5} vínculos confirmados*"
                
                embed.add_field(
                    name="✅ CONFIRMADO - Banco de Dados (100% Certeza)",
                    value=text or "Nenhum",
                    inline=False
                )
            
            # SEÇÃO 2: Pares Altamente Suspeitos
            high_confidence = [p for p in pair_suspects if p['score'] >= 60]
            if high_confidence:
                text = ""
                for p in high_confidence[:8]:
                    m1, m2 = p['m1'], p['m2']
                    text += f"{p['emoji']} **{m1.name}** ↔️ **{m2.name}**\n"
                    text += f"├ Confiança: **{p['level']}** ({p['score']:.0f} pontos)\n"
                    text += f"└ {p['evidence'][0] if p['evidence'] else 'Análise de padrões'}\n\n"
                
                if len(high_confidence) > 8:
                    text += f"*...e mais {len(high_confidence) - 8} pares suspeitos*"
                
                embed.add_field(
                    name="🔥 Pares com Alta Probabilidade",
                    value=text,
                    inline=False
                )
            
            # SEÇÃO 3: Comportamento Individual Suspeito
            if individual_suspects:
                text = ""
                for s in individual_suspects[:10]:
                    m = s['member']
                    text += f"{s['emoji']} **{m.name}** (CV{m.town_hall})\n"
                    text += f"├ Nível: **{s['level']}** ({s['score']} pts)\n"
                    if s['details']:
                        text += f"└ {s['details'][0]}\n"
                    text += "\n"
                
                if len(individual_suspects) > 10:
                    text += f"*...e mais {len(individual_suspects) - 10} contas*"
                
                embed.add_field(
                    name="📊 Análise Comportamental Individual",
                    value=text,
                    inline=False
                )
            
            # SEÇÃO 4: Suspeitas Moderadas
            moderate = [p for p in pair_suspects if 30 <= p['score'] < 60]
            if moderate:
                text = ""
                for p in moderate[:5]:
                    text += f"{p['emoji']} **{p['m1'].name}** ↔️ **{p['m2'].name}** ({p['score']:.0f} pts)\n"
                
                if len(moderate) > 5:
                    text += f"*...e mais {len(moderate) - 5} pares*"
                
                embed.add_field(
                    name="🟡 Suspeitas Moderadas",
                    value=text,
                    inline=False
                )
            
            # Mensagem final
            if not confirmed_links and not pair_suspects and not individual_suspects:
                embed.description = "✅ **NENHUMA ANOMALIA DETECTADA**\n\nO clã está limpo segundo os critérios de análise atual."
                embed.color = discord.Color.green()
            
            # Footer informativo
            embed.set_footer(
                text="🤖 Clash Genius AI v2.0 | Sistema de Pontuação Ponderada | Análise baseada em +12 fatores"
            )
            
            await interaction.followup.send(embed=embed)
            
            logger.info(f"Análise de smurfs concluída: {len(pair_suspects)} pares, {len(individual_suspects)} individuais")

        except Exception as e:
            logger.error(f"Erro crítico no slash_analyze_smurfs: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ Ocorreu um erro interno durante a análise. O erro foi registrado nos logs."
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(SmurfDetectionCog(bot))
