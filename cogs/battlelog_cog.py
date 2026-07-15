# -*- coding: utf-8 -*-
import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
import geniuslib as coc
from geniuslib.battlelog_analytics import (
    battle_attack_stats,
    battle_defense_stats,
    battle_loot_summary,
    battle_win_rate,
    battle_consistency_score,
    battle_streak,
    battle_period_summary,
    league_history_progression,
    tier_group_mvp,
    tier_group_attack_analysis,
    tier_group_defense_analysis,
    tier_group_member_stats,
)
import datetime
import pytz
import asyncio
from typing import Optional

logger = logging.getLogger("battlelog_cog")


class BattleLogCog(commands.Cog, name="Legend League"):
    """Cog para relatórios de Legend League e battle logs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = bot.db
        self.battlelog_collection = self.db.battle_logs if self.db is not None else None
        self.tasks_started = False

    async def cog_load(self):
        pass

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.tasks_started:
            try:
                await asyncio.wait_for(self.bot.db_ready.wait(), timeout=30.0)
                await asyncio.wait_for(self.bot.coc_client_ready.wait(), timeout=60.0)

                if not self.snapshot_battle_logs_task.is_running():
                    self.snapshot_battle_logs_task.start()
                if not self.daily_legend_report_task.is_running():
                    self.daily_legend_report_task.start()

                self.tasks_started = True
                logger.info("BattleLogCog: Tasks iniciadas com sucesso.")
            except asyncio.TimeoutError:
                logger.critical("BattleLogCog: Timeout esperando DB ou CoC prontos.")
            except Exception as e:
                logger.critical(f"BattleLogCog: Erro ao iniciar tasks: {e}", exc_info=True)

    def cog_unload(self):
        if self.snapshot_battle_logs_task.is_running():
            self.snapshot_battle_logs_task.cancel()
        if self.daily_legend_report_task.is_running():
            self.daily_legend_report_task.cancel()
        self.tasks_started = False

    async def _get_legend_members(self):
        """Retorna membros da clan que estão em Legend League."""
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag)
            legend_members = []
            for member in clan.members:
                if member.league and "legend" in member.league.name.lower():
                    legend_members.append(member)
            return legend_members
        except Exception as e:
            logger.error(f"Erro ao buscar membros Legend: {e}")
            return []

    async def _fetch_battlelog(self, player_tag: str):
        """Busca battle log de um jogador com tratamento de erros."""
        try:
            entries = await self.bot.api_client.get_player_battlelog(player_tag)
            return entries
        except Exception as e:
            logger.warning(f"Erro ao buscar battlelog para {player_tag}: {e}")
            return []

    async def _fetch_league_history(self, player_tag: str):
        """Busca histórico de ligas de um jogador."""
        try:
            history = await self.bot.api_client.get_player_league_history(player_tag)
            return history
        except Exception as e:
            logger.warning(f"Erro ao buscar league history para {player_tag}: {e}")
            return []

    # --- Background Tasks ---

    @tasks.loop(hours=2)
    async def snapshot_battle_logs_task(self):
        """Salva snapshots de battle logs de todos os membros Legend na MongoDB."""
        if self.bot.maintenance_mode or self.battlelog_collection is None:
            return

        logger.info("Iniciando snapshot de battle logs...")
        try:
            members = await self._get_legend_members()
            if not members:
                logger.info("Nenhum membro Legend encontrado.")
                return

            saved_count = 0
            for member in members:
                entries = await self._fetch_battlelog(member.tag)
                if not entries:
                    continue

                entry_dicts = []
                for e in entries:
                    entry_dicts.append({
                        "battle_type": e.battle_type,
                        "attack": e.attack,
                        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                        "opponent_player_tag": e.opponent_player_tag,
                        "stars": e.stars,
                        "destruction_percentage": e.destruction_percentage,
                        "looted_resources": [{"name": r.name, "amount": r.amount} for r in e.looted_resources],
                    })

                snapshot_doc = {
                    "player_tag": member.tag,
                    "player_name": member.name,
                    "clan_tag": self.bot.clan_tag,
                    "snapshot_time": datetime.datetime.now(pytz.utc),
                    "entries": entry_dicts,
                }
                await self.battlelog_collection.insert_one(snapshot_doc)
                saved_count += 1

                await asyncio.sleep(1)

            logger.info(f"Snapshot de battle logs: {saved_count}/{len(members)} membros salvos.")
        except Exception as e:
            logger.error(f"Erro no snapshot de battle logs: {e}", exc_info=True)

    @snapshot_battle_logs_task.before_loop
    async def before_snapshot_battle_logs(self):
        await self.bot.wait_until_ready()

    @tasks.loop(time=datetime.time(hour=23, minute=59, tzinfo=pytz.timezone("America/Sao_Paulo")))
    async def daily_legend_report_task(self):
        """Gera e envia relatório diário de Legend League."""
        if self.bot.maintenance_mode:
            return

        logger.info("Gerando relatório diário de Legend...")
        try:
            channel = self.bot.get_channel(self.bot.channel_id)
            if not channel:
                logger.warning("Canal principal não encontrado para relatório diário.")
                return

            members = await self._get_legend_members()
            if not members:
                return

            all_entries = []
            for member in members:
                entries = await self._fetch_battlelog(member.tag)
                if entries:
                    all_entries.extend(entries)
                await asyncio.sleep(1)

            if not all_entries:
                return

            stats = battle_attack_stats(all_entries)
            defense = battle_defense_stats(all_entries)
            loot = battle_loot_summary(all_entries)
            win = battle_win_rate(all_entries)

            now = datetime.datetime.now(self.bot.timezone)
            embed = discord.Embed(
                title="⚔️ Relatório Diário - Legend League",
                color=discord.Color.gold(),
            )
            embed.description = f"**Data:** {now.strftime('%d/%m/%Y')}\n**Membros Legend:** {len(members)}"

            embed.add_field(
                name="⚔️ Ataques",
                value=(
                    f"**Total:** {stats['total_attacks']}\n"
                    f"**Vitórias:** {stats['wins']} ({win:.1f}%)\n"
                    f"**Derrotas:** {stats['losses']}\n"
                    f"**Stars Médios:** {stats['avg_stars']:.1f}\n"
                    f"**Destruição Média:** {stats['avg_destruction']:.1f}%"
                ),
                inline=True,
            )
            embed.add_field(
                name="🛡️ Defesas",
                value=(
                    f"**Total:** {defense['total_defenses']}\n"
                    f"**Vitórias:** {defense['wins']}\n"
                    f"**Derrotas:** {defense['losses']}\n"
                    f"**Stars Recebidos:** {defense['total_stars_received']}"
                ),
                inline=True,
            )
            embed.add_field(
                name="💰 Saque",
                value=(
                    f"**Gold:** {loot['total_gold']:,}\n"
                    f"**Elixir:** {loot['total_elixir']:,}\n"
                    f"**Dark:** {loot['total_dark']:,}"
                ),
                inline=True,
            )

            embed.set_footer(text=f"Bot: {self.bot.user.name} | v{self.bot.bot_version} • {now.strftime('%d/%m/%Y %H:%M')}")
            embed.timestamp = now
            await channel.send(embed=embed)
            logger.info("Relatório diário de Legend enviado.")
        except Exception as e:
            logger.error(f"Erro no relatório diário de Legend: {e}", exc_info=True)

    @daily_legend_report_task.before_loop
    async def before_daily_legend_report(self):
        await self.bot.wait_until_ready()

    # --- Slash Commands ---

    @app_commands.command(name="legend", description="Relatório completo de Legend League de um jogador.")
    @app_commands.describe(jogador="Tag do jogador (ex: #2ABC)")
    async def cmd_legend(self, interaction: discord.Interaction, jogador: str):
        await interaction.response.defer()

        try:
            player = await self.bot.api_client.get_player(jogador)
        except Exception:
            await interaction.followup.send("❌ Jogador não encontrado.", ephemeral=True)
            return

        entries = await self._fetch_battlelog(player.tag)
        if not entries:
            await interaction.followup.send(
                f"⚠️ Nenhum battle log encontrado para **{player.name}**. "
                "O jogador precisa estar na Legend League.",
                ephemeral=True,
            )
            return

        attack_stats = battle_attack_stats(entries)
        defense_stats = battle_defense_stats(entries)
        loot = battle_loot_summary(entries)
        win = battle_win_rate(entries)
        consistency = battle_consistency_score(entries)
        current_streak, best_streak, streak_type = battle_streak(entries)

        now = datetime.datetime.now(self.bot.timezone)
        embed = discord.Embed(
            title=f"⚔️ Legend League - {player.name}",
            color=discord.Color.gold(),
        )
        embed.description = f"**Tag:** {player.tag} | **TH:** {player.town_hall}"

        embed.add_field(
            name="⚔️ Ataques",
            value=(
                f"**Total:** {attack_stats['total_attacks']}\n"
                f"**Vitórias:** {attack_stats['wins']}\n"
                f"**Derrotas:** {attack_stats['losses']}\n"
                f"**Win Rate:** {win:.1f}%\n"
                f"**Stars Médios:** {attack_stats['avg_stars']:.1f}\n"
                f"**Destruição Média:** {attack_stats['avg_destruction']:.1f}%"
            ),
            inline=True,
        )
        embed.add_field(
            name="🛡️ Defesas",
            value=(
                f"**Total:** {defense_stats['total_defenses']}\n"
                f"**Vitórias:** {defense_stats['wins']}\n"
                f"**Derrotas:** {defense_stats['losses']}\n"
                f"**Stars Recebidos:** {defense_stats['total_stars_received']}"
            ),
            inline=True,
        )
        embed.add_field(
            name="📊 Performance",
            value=(
                f"**Consistência:** {consistency:.0f}/100\n"
                f"**Sequência Atual:** {current_streak} {streak_type}\n"
                f"**Melhor Sequência:** {best_streak}"
            ),
            inline=True,
        )
        embed.add_field(
            name="💰 Saque Total",
            value=(
                f"**Gold:** {loot['total_gold']:,}\n"
                f"**Elixir:** {loot['total_elixir']:,}\n"
                f"**Dark:** {loot['total_dark']:,}"
            ),
            inline=True,
        )

        star_dist = attack_stats["star_distribution"]
        embed.add_field(
            name="⭐ Distribuição de Stars",
            value=(
                f"⭐⭐⭐ {star_dist[3]} | "
                f"⭐⭐ {star_dist[2]} | "
                f"⭐ {star_dist[1]} | "
                f"💀 {star_dist[0]}"
            ),
            inline=False,
        )

        league_icon = player.league.icon.url if player.league and player.league.icon else None
        if league_icon:
            embed.set_thumbnail(url=league_icon)

        embed.set_footer(text=f"Bot: {self.bot.user.name} | v{self.bot.bot_version} • {now.strftime('%d/%m/%Y %H:%M')}")
        embed.timestamp = now
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="legend_historico", description="Histórico de ligas de um jogador.")
    @app_commands.describe(jogador="Tag do jogador (ex: #2ABC)")
    async def cmd_legend_historico(self, interaction: discord.Interaction, jogador: str):
        await interaction.response.defer()

        try:
            player = await self.bot.api_client.get_player(jogador)
        except Exception:
            await interaction.followup.send("❌ Jogador não encontrado.", ephemeral=True)
            return

        history = await self._fetch_league_history(player.tag)
        if not history:
            await interaction.followup.send(
                f"⚠️ Nenhum histórico de ligas encontrado para **{player.name}**.",
                ephemeral=True,
            )
            return

        progression = league_history_progression(history)

        now = datetime.datetime.now(self.bot.timezone)
        embed = discord.Embed(
            title=f"📜 Histórico de Ligas - {player.name}",
            color=discord.Color.blue(),
        )
        embed.description = f"**Temporadas:** {progression['total_seasons']} | **Melhor Posição:** #{progression['best_placement']}"

        embed.add_field(
            name="🏆 Troféus",
            value=(
                f"**Melhor:** {progression['best_trophies']:,}\n"
                f"**Pior:** {progression['worst_trophies']:,}\n"
                f"**Média:** {progression['avg_trophies']:,.1f}"
            ),
            inline=True,
        )
        embed.add_field(
            name="📊 Win Rates",
            value=(
                f"**Ataque:** {progression['avg_attack_win_rate']:.1f}%\n"
                f"**Defesa:** {progression['avg_defense_win_rate']:.1f}%"
            ),
            inline=True,
        )
        embed.add_field(
            name="⭐ Total",
            value=f"**Stars de Ataque:** {progression['total_attack_stars']}",
            inline=True,
        )

        trend = progression["trophy_trend"]
        if trend:
            recent = trend[-5:]
            trend_text = "\n".join(
                f"S{t['season']}: {t['trophies']:,} (#{t['placement']})"
                for t in recent
            )
            embed.add_field(name="📈 Últimas Temporadas", value=f"```{trend_text}```", inline=False)

        embed.set_footer(text=f"Bot: {self.bot.user.name} | v{self.bot.bot_version} • {now.strftime('%d/%m/%Y %H:%M')}")
        embed.timestamp = now
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="legend_resumo", description="Resumo da clan em Legend League.")
    @app_commands.describe(dias="Número de dias para analisar (padrão: 1)")
    async def cmd_legend_resumo(self, interaction: discord.Interaction, dias: int = 1):
        await interaction.response.defer()

        members = await self._get_legend_members()
        if not members:
            await interaction.followup.send("⚠️ Nenhum membro Legend encontrado na clan.", ephemeral=True)
            return

        all_entries = []
        member_names = {}
        for member in members:
            entries = await self._fetch_battlelog(member.tag)
            if entries:
                all_entries.extend(entries)
                member_names[member.tag] = member.name
            await asyncio.sleep(1)

        if not all_entries:
            await interaction.followup.send("⚠️ Nenhum battle log encontrado.", ephemeral=True)
            return

        today = datetime.date.today()
        start = today - datetime.timedelta(days=dias)
        period = battle_period_summary(all_entries, start, today)

        now = datetime.datetime.now(self.bot.timezone)
        embed = discord.Embed(
            title=f"📊 Resumo Legend - Último(s) {dias} dia(s)",
            color=discord.Color.green(),
        )
        embed.description = f"**Período:** {start.strftime('%d/%m/%Y')} - {today.strftime('%d/%m/%Y')}\n**Membros:** {len(members)}"

        attacks = period["attacks"]
        embed.add_field(
            name="⚔️ Ataques",
            value=(
                f"**Total:** {attacks['total_attacks']}\n"
                f"**Win Rate:** {period['win_rate']:.1f}%\n"
                f"**Stars Médios:** {attacks['avg_stars']:.1f}"
            ),
            inline=True,
        )

        defenses = period["defenses"]
        embed.add_field(
            name="🛡️ Defesas",
            value=(
                f"**Total:** {defenses['total_defenses']}\n"
                f"**Vitórias:** {defenses['wins']}\n"
                f"**Derrotas:** {defenses['losses']}"
            ),
            inline=True,
        )

        loot = period["loot"]
        embed.add_field(
            name="💰 Saque Total",
            value=(
                f"**Gold:** {loot['total_gold']:,}\n"
                f"**Elixir:** {loot['total_elixir']:,}\n"
                f"**Dark:** {loot['total_dark']:,}"
            ),
            inline=True,
        )

        embed.set_footer(text=f"Bot: {self.bot.user.name} | v{self.bot.bot_version} • {now.strftime('%d/%m/%Y %H:%M')}")
        embed.timestamp = now
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="legend_exercitos", description="Análise dos exércitos usados em Legend League.")
    @app_commands.describe(jogador="Tag do jogador (ex: #2ABC)")
    async def cmd_legend_exercitos(self, interaction: discord.Interaction, jogador: str):
        await interaction.response.defer()

        try:
            player = await self.bot.api_client.get_player(jogador)
        except Exception:
            await interaction.followup.send("❌ Jogador não encontrado.", ephemeral=True)
            return

        entries = await self._fetch_battlelog(player.tag)
        if not entries:
            await interaction.followup.send(
                f"⚠️ Nenhum battle log encontrado para **{player.name}**.",
                ephemeral=True,
            )
            return

        attacks = [e for e in entries if e.is_attack]
        if not attacks:
            await interaction.followup.send("⚠️ Nenhum ataque encontrado.", ephemeral=True)
            return

        from collections import Counter
        army_codes = Counter(a.army_share_code for a in attacks if a.army_share_code)

        now = datetime.datetime.now(self.bot.timezone)
        embed = discord.Embed(
            title=f"🗡️ Exércitos - {player.name}",
            color=discord.Color.purple(),
        )
        embed.description = f"**Total de Ataques:** {len(attacks)}"

        if army_codes:
            top_armies = army_codes.most_common(5)
            army_text = "\n".join(
                f"`{code}` — {count} uso{'s' if count > 1 else ''}"
                for code, count in top_armies
            )
            embed.add_field(name="📋 Códigos de Exército Mais Usados", value=army_text, inline=False)
        else:
            embed.add_field(name="📋 Códigos de Exército", value="Nenhum código de exército registrado.", inline=False)

        star_by_code = {}
        for a in attacks:
            code = a.army_share_code or "Desconhecido"
            if code not in star_by_code:
                star_by_code[code] = []
            star_by_code[code].append(a.stars)

        if star_by_code:
            code_stats = []
            for code, stars_list in sorted(star_by_code.items(), key=lambda x: -sum(x[1]) / len(x[1])):
                avg = sum(stars_list) / len(stars_list)
                code_stats.append(f"`{code}` — {avg:.1f} stars/ataque ({len(stars_list)} usos)")

            embed.add_field(
                name="⭐ Efetividade por Código",
                value="\n".join(code_stats[:5]),
                inline=False,
            )

        embed.set_footer(text=f"Bot: {self.bot.user.name} | v{self.bot.bot_version} • {now.strftime('%d/%m/%Y %H:%M')}")
        embed.timestamp = now
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(BattleLogCog(bot))
