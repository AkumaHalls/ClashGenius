# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import geniuslib as coc
from geniuslib.formatters import format_th, format_trophies, format_attack as fmt_attack
import asyncio
import datetime
from typing import Optional

logger = logging.getLogger("events_cog")

# ========================================================
# >>> VISÃO DO PERFIL (DENTRO DA MENSAGEM EFÊMERA) <<<
# ========================================================
class ProfileDetailView(discord.ui.View):
    """View que fica anexada ao relatório efêmero, contendo as abas do perfil."""
    def __init__(self, bot: commands.Bot, player_tag: str):
        super().__init__(timeout=None)
        self.bot = bot
        self.player_tag = player_tag

    @discord.ui.button(label="Visão Geral", style=discord.ButtonStyle.primary, custom_id="tab_overview", disabled=True)
    async def btn_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Tropas (Units)", style=discord.ButtonStyle.secondary, custom_id="tab_units")
    async def btn_units(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🛠️ O módulo visualizador de Tropas e Feitiços será implementado em breve!", ephemeral=True)

    @discord.ui.button(label="Evolução (Rushed)", style=discord.ButtonStyle.secondary, custom_id="tab_rushed")
    async def btn_rushed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚙️ A calculadora de Nível de Rush (Pressa de CV) está em desenvolvimento!", ephemeral=True)

# ========================================================
# >>> BOTÃO DE ABRIR PERFIL (NA MENSAGEM DE RH) <<<
# ========================================================
class OpenProfileButtonView(discord.ui.View):
    """View que fica anexada aos alertas de Entrada/Saída do RH."""
    def __init__(self, bot: commands.Bot, player_tag: str):
        super().__init__(timeout=None) 
        self.bot = bot
        self.player_tag = player_tag

    def format_large_number(self, num: int) -> str:
        if num >= 1_000_000_000: return f"{num/1_000_000_000:.2f}B"
        if num >= 1_000_000: return f"{num/1_000_000:.2f}M"
        return f"{num:,}"

    def get_achievement_val(self, player, name: str) -> int:
        ach = player.get_achievement(name)
        return ach.value if ach else 0

    @discord.ui.button(label="📋 Ver Perfil Completo", style=discord.ButtonStyle.secondary, custom_id="btn_open_profile")
    async def btn_open_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        try:
            player = await self.bot.api_client.get_player(self.player_tag)
            
            embed = discord.Embed(color=0x2b2d31)
            
            embed.set_author(name=f"{player.name} ({player.tag})", icon_url=player.league.icon.url if player.league else None)
            embed.set_thumbnail(url=f"https://coc.guide/static/imgs/other/town-hall-{player.town_hall}.png")
            
            header_stats = f"🏛️ **{format_th(player.town_hall)}** | 💠 **Nvl {player.exp_level}** | 🏆 **{player.trophies:,}** | ⭐ **{player.war_stars}**"
            embed.description = header_stats

            season_stats = (
                f"🎁 **Doadas:** {player.donations}\n"
                f"📥 **Recebidas:** {player.received}\n"
                f"⚔️ **Ataques Vencidos:** {player.attack_wins}\n"
                f"🛡️ **Defesas Vencidas:** {player.defense_wins}"
            )
            embed.add_field(name="📊 Estatísticas da Temporada", value=season_stats, inline=False)

            gold = self.format_large_number(self.get_achievement_val(player, "Gold Grab"))
            elixir = self.format_large_number(self.get_achievement_val(player, "Elixir Escapade"))
            dark = self.format_large_number(self.get_achievement_val(player, "Heroic Heist"))
            
            donated_lifetime = self.format_large_number(self.get_achievement_val(player, "Friend in Need"))
            cg_points = f"{self.get_achievement_val(player, 'Games Champion'):,}"
            
            cap_looted = f"{self.get_achievement_val(player, 'Aggressive Capitalism'):,}"
            cap_contrib = f"{self.get_achievement_val(player, 'Most Valuable Clanmate'):,}"

            economy_stats = (
                f"**Total Saqueado:**\n🟡 {gold} | 🟣 {elixir} | ⚫ {dark}\n"
                f"**Tropas Doadas (Vitalício):** {donated_lifetime}\n"
                f"**Pontos nos Jogos do Clã:** {cg_points}\n"
                f"**Capital do Clã:**\n"
                f"> 🪙 Saqueado: {cap_looted}\n"
                f"> ⚒️ Contribuído: {cap_contrib}"
            )
            embed.add_field(name="💰 Conquistas Financeiras", value=economy_stats, inline=False)

            hero_emojis = {
                "Barbarian King": "👑", "Archer Queen": "👸", 
                "Grand Warden": "🧙‍♂️", "Royal Champion": "🏇", "Minion Prince": "🦇",
                "Dragon Duke": "🐉"
            }
            heroes_str = ""
            for h in player.heroes:
                if h.is_home_base:
                    emoji = hero_emojis.get(h.name, "🦸")
                    heroes_str += f"{emoji} {h.level}  "
            
            if not heroes_str: heroes_str = "Nenhum Herói"
            embed.add_field(name="🦸 Heróis", value=heroes_str, inline=False)

            pets_str = ""
            for p in player.pets:
                pets_str += f"🐾 {p.name} **{p.level}**  "
            if pets_str:
                embed.add_field(name="🐕 Pets", value=pets_str.strip(), inline=False)

            equip_str = ""
            for h in player.heroes:
                if h.is_home_base and hasattr(h, 'equipment') and h.equipment:
                    equip_str += f"**{h.name}:** "
                    for eq in h.equipment:
                        equip_str += f"`{eq.name}` {eq.level}  "
                    equip_str += "\n"
            if equip_str:
                embed.add_field(name="⚔️ Equipamentos", value=equip_str.strip(), inline=False)

            legend = getattr(player, 'legend_statistics', None)
            if legend:
                ls = []
                if getattr(legend, 'legend_trophies', 0):
                    ls.append(f"🏆 **Legends:** {legend.legend_trophies}")
                if getattr(legend, 'best_season', None):
                    ls.append(f"⭐ **Melhor Temporada:** {legend.best_season.trophies}")
                if ls:
                    embed.add_field(name="👑 Lenda Liga", value="\n".join(ls), inline=False)

            cap_contrib = getattr(player, 'clan_capital_contributions', 0)
            if cap_contrib:
                embed.add_field(name="🏰 Capital", value=f"⚒️ **Contribuições:** {cap_contrib:,}", inline=False)

            discord_str = "❌ `Não Vinculado no Sistema`"
            if self.bot.db is not None:
                db_user = await self.bot.db.users.find_one({"player_tag": player.tag})
                if db_user and db_user.get("discord_id"):
                    discord_str = f"✅ `<@{db_user['discord_id']}>`"
            embed.add_field(name="Discord", value=discord_str, inline=False)
            
            embed.set_footer(text="ClashGenius • Módulo de RH • Visão Privada")

            view_tabs = ProfileDetailView(self.bot, self.player_tag)
            await interaction.followup.send(embed=embed, view=view_tabs, ephemeral=True)

        except coc.errors.NotFound:
            await interaction.followup.send("❌ Jogador não encontrado na base de dados da Supercell.", ephemeral=True)
        except Exception as e:
            logger.error(f"Erro ao gerar perfil por botão no RH: {e}")
            await interaction.followup.send("❌ Erro interno ao buscar dados do jogador.", ephemeral=True)

# ========================================================
# >>> COG DE EVENTOS DO CLÃ ORIGINAL RESTAURADA E BLINDADA <<<
# ========================================================
class EventsCog(commands.Cog, name="Eventos do Clã"):
    """Cog para gerenciar e notificar eventos do clã e de guerra."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.events_client = coc.EventsClient(raid_clan_tag=bot.clan_tag)
        self.war_attack_cache = {"war_end_time": None, "processed_attacks": set()}
        self._add_event_listeners()

    def _add_event_listeners(self):
        """Aplica os decoradores de evento aos métodos de handle."""

        @self.events_client.event
        @coc.ClanEvents.member_join()
        async def on_clan_member_join(member, clan):
            await self.handle_clan_member_join(member, clan)

        @self.events_client.event
        @coc.ClanEvents.member_leave()
        async def on_clan_member_leave(member, clan):
            await self.handle_clan_member_leave(member, clan)

        @self.events_client.event
        @coc.ClanEvents.member_role()
        async def on_clan_member_role_change(old_member, new_member):
            await self.handle_clan_member_role_change(old_member, new_member)

        @self.events_client.event
        @coc.ClanEvents.member_trophies()
        async def on_clan_member_trophies_change(old_member, new_member):
            await self.handle_clan_member_trophies_change(old_member, new_member)

        @self.events_client.event
        @coc.ClanEvents.member_league()
        async def on_clan_member_league_change(old_member, new_member):
            await self.handle_clan_member_league_change(old_member, new_member)

        @self.events_client.event
        @coc.ClanEvents.member_donations()
        async def on_member_donations(old_member, new_member):
            await self.handle_member_donations(old_member, new_member)

        @self.events_client.event
        @coc.ClanEvents.member_received()
        async def on_member_received(old_member, new_member):
            await self.handle_member_received(old_member, new_member)

    async def cog_load(self):
        """Inicia o login do cliente de eventos e a task de ataques."""
        self.bot.loop.create_task(self.start_events_client())
        self.check_new_attack_task.start()
        self.check_war_preference_task.start()
        logger.info("Cog de Eventos carregado e task de login/ataques iniciada.")

    async def start_events_client(self):
        """Função segura para logar o cliente de eventos após o bot estar pronto."""
        await self.bot.wait_until_ready()
        try:
            self.events_client.add_clan_updates(self.bot.clan_tag)
            await self.events_client.login(self.bot.coc_email, self.bot.coc_password)
            logger.info("Cliente de eventos (EventsClient) logado e escutando.")
        except Exception as e:
            logger.error(f"Falha CRÍTICA no login do EventsClient: {e}", exc_info=True)

    async def cog_unload(self):
        """Para a task e fecha o cliente de eventos."""
        self.check_new_attack_task.cancel()
        self.check_war_preference_task.cancel()
        if self.events_client:
            await self.events_client.close()

    async def _send_log_embed(self, embed_to_log: discord.Embed, content: str = None, target_channel_id: int = None, view: Optional[discord.ui.View] = None):
        """Envia embeds de log de forma segura para o canal especificado, com fallback para o canal geral."""
        channel_id_to_use = target_channel_id if target_channel_id else getattr(self.bot, 'channel_id', None)
        if not channel_id_to_use: return
        
        try:
            channel = self.bot.get_channel(channel_id_to_use) or await self.bot.fetch_channel(channel_id_to_use)
            now_in_timezone = datetime.datetime.now(self.bot.timezone)
            embed_to_log.set_footer(text=f"Bot: {self.bot.user.name} | v{self.bot.bot_version} • {now_in_timezone.strftime('%d/%m/%Y %H:%M')}")
            embed_to_log.timestamp = now_in_timezone
            
            try:
                if view:
                    await channel.send(content=content, embed=embed_to_log, view=view)
                else:
                    await channel.send(content=content, embed=embed_to_log)
            except discord.errors.HTTPException as e:
                if e.status == 429:
                    logger.warning(f"Rate Limit (429) no canal de logs {channel_id_to_use}. Mensagem ignorada para proteção.")
                else:
                    logger.error(f"Erro HTTP ao enviar log: {e}")

        except Exception as e:
            logger.error(f"Erro ao enviar embed para o canal {channel_id_to_use}: {e}", exc_info=True)

    # --- FUNÇÕES QUE RESPONDEM AOS EVENTOS ---

    async def handle_clan_member_join(self, member, clan):
        # Correção da barreira invisível do '#': Verifica a tag de forma segura
        if self.bot.maintenance_mode or coc.utils.correct_tag(clan.tag) != coc.utils.correct_tag(self.bot.clan_tag):
            return

        logger.info(f"Evento member_join DETECTADO para {member.name} ({member.tag}).")

        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if watchlist_cog:
            await watchlist_cog.check_and_alert_on_join(member)

        embed = discord.Embed(title="➡️ Membro Entrou no Clã", description=f"**{member.name}** (`{member.tag}`) juntou-se ao clã.", color=discord.Color.brand_green())
        embed.add_field(name="CV", value=format_th(member.town_hall), inline=True)
        if hasattr(member, 'league') and member.league and hasattr(member.league, 'name'):
            embed.add_field(name="Liga", value=member.league.name, inline=True)
        
        view = OpenProfileButtonView(self.bot, member.tag)
        await self._send_log_embed(embed, target_channel_id=self.bot.watchlist_alert_channel_id, view=view)

    async def handle_clan_member_leave(self, member, clan):
        if self.bot.maintenance_mode or coc.utils.correct_tag(clan.tag) != coc.utils.correct_tag(self.bot.clan_tag): return
        
        embed = discord.Embed(title="⬅️ Membro Saiu do Clã", description=f"**{member.name}** (`{member.tag}`) deixou a equipe.", color=discord.Color.dark_grey())
        embed.add_field(name="CV", value=format_th(member.town_hall), inline=True)
        role_name = member.role.name.capitalize() if member.role and hasattr(member.role, 'name') else "N/A"
        embed.add_field(name="Cargo", value=role_name, inline=True)
        
        view = OpenProfileButtonView(self.bot, member.tag)
        await self._send_log_embed(embed, target_channel_id=self.bot.watchlist_alert_channel_id, view=view)

    async def on_war_attack(self, attack, war):
        if self.bot.maintenance_mode: return
        try:
            is_our_attack = war.clan.get_member(attack.attacker_tag) is not None

            if is_our_attack:
                attacker = war.clan.get_member(attack.attacker_tag)
                defender = war.opponent.get_member(attack.defender_tag)
            else:
                attacker = war.opponent.get_member(attack.attacker_tag)
                defender = war.clan.get_member(attack.defender_tag)

            if not attacker or not defender:
                logger.warning(f"on_war_attack: attacker={attack.attacker_tag} found={attacker is not None}, defender={attack.defender_tag} found={defender is not None}")
                return

            war_type = "CWL" if war.is_cwl else "Guerra"
            stars_str = "⭐" * attack.stars + "⚫" * (3 - attack.stars)

            our_sorted = {m.tag: i+1 for i, m in enumerate(war.clan.members)}
            opp_sorted = {m.tag: i+1 for i, m in enumerate(war.opponent.members)}

            attacker_pos = (our_sorted if is_our_attack else opp_sorted).get(attacker.tag) or attacker.map_position
            defender_pos = (opp_sorted if is_our_attack else our_sorted).get(defender.tag) or defender.map_position
            attacker_map_pos = f"{attacker_pos:02d}" if attacker_pos is not None else "??"
            defender_map_pos = f"{defender_pos:02d}" if defender_pos is not None else "??"

            attacker_str = f"`{attacker_map_pos}` **{attacker.name}** ({format_th(attacker.town_hall)})"
            defender_str = f"`{defender_map_pos}` **{defender.name}** ({format_th(defender.town_hall)})"

            extra_info = []
            if attack.duration:
                mins, secs = divmod(int(attack.duration), 60)
                extra_info.append(f"⏱ Duração: `{mins}:{secs:02d}`")
            fresh = getattr(attack, 'is_fresh_attack', None)
            if fresh is not None:
                extra_info.append("🆕 Ataque Fresco" if fresh else "🔁 Limpeza")
            durations = [a.duration for a in war.clan.attacks if getattr(a, 'duration', None)]
            if durations:
                avg_dur = sum(durations) / len(durations)
                am, as_ = divmod(int(avg_dur), 60)
                extra_info.append(f"📊 Média do Clã: `{am}:{as_:02d}`")

            extra_str = "\n".join(extra_info) if extra_info else ""

            if is_our_attack:
                if attack.stars <= 1:
                    alert_embed = discord.Embed(title=f"⚠️ Ataque fora do padrão!", description=f"**{attacker.clan.name}**\n⚔️ **Ataque Realizado ({war_type})**", color=discord.Color.red())
                    alert_embed.add_field(name="Detalhes", value=f"{attacker_str} atacou {defender_str}", inline=False)
                    alert_embed.add_field(name="Resultado", value=f"{'⚫⚫⚫' if attack.stars == 0 else '⭐⚫⚫'} ({attack.destruction}%)", inline=False)
                    if extra_str:
                        alert_embed.add_field(name="Info Extra", value=extra_str, inline=False)
                    if war.opponent.badge: alert_embed.set_thumbnail(url=war.opponent.badge.url)
                    role_mention = f"<@&{self.bot.role_id_1star_alert}>" if self.bot.role_id_1star_alert else ""
                    
                    await self._send_log_embed(alert_embed, content=f"{role_mention} Atenção ao ataque fora do padrão!", target_channel_id=self.bot.post_war_analysis_channel_id)
                else:
                    embed = discord.Embed(title=f"⚔️ Ataque Realizado ({war_type})", description=f"{attacker.clan.name}", color=discord.Color.blue())
                    embed.add_field(name="Detalhes", value=f"{attacker_str} atacou {defender_str}", inline=False)
                    embed.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
                    if extra_str:
                        embed.add_field(name="Info Extra", value=extra_str, inline=False)
                    if war.opponent.badge: embed.set_thumbnail(url=war.opponent.badge.url)
                    
                    await self._send_log_embed(embed, target_channel_id=self.bot.post_war_analysis_channel_id)
            else:
                embed = discord.Embed(title=f"🛡️ Defesa Recebida ({war_type})", description=f"{defender.clan.name}", color=discord.Color.orange())
                embed.add_field(name="Detalhes", value=f"{defender_str} foi atacado por {attacker_str}", inline=False)
                embed.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
                if extra_str:
                    embed.add_field(name="Info Extra", value=extra_str, inline=False)
                if hasattr(war, 'clan') and war.clan and hasattr(war.clan, 'badge') and war.clan.badge:
                     embed.set_thumbnail(url=war.clan.badge.url)
                
                await self._send_log_embed(embed, target_channel_id=self.bot.post_war_analysis_channel_id)
        except Exception as e:
            logger.error(f"Erro em on_war_attack: {e}", exc_info=True)

    async def handle_clan_member_role_change(self, old_member, new_member):
        if self.bot.maintenance_mode or (new_member.clan and coc.utils.correct_tag(new_member.clan.tag) != coc.utils.correct_tag(self.bot.clan_tag)): return
        
        old_role = old_member.role.name.capitalize() if old_member.role and hasattr(old_member.role, 'name') else "N/A"
        new_role = new_member.role.name.capitalize() if new_member.role and hasattr(new_member.role, 'name') else "N/A"
        if old_role == new_role: return

        embed = discord.Embed(title="✨ Mudança de Cargo", description=f"A patente de **{new_member.name}** (`{new_member.tag}`) foi alterada.", color=discord.Color.blurple())
        embed.add_field(name="Cargo Antigo", value=old_role, inline=True)
        embed.add_field(name="Novo Cargo", value=new_role, inline=True)
        
        view = OpenProfileButtonView(self.bot, new_member.tag)
        await self._send_log_embed(embed, target_channel_id=self.bot.watchlist_alert_channel_id, view=view)

    async def handle_clan_member_trophies_change(self, old_member, new_member):
        if self.bot.maintenance_mode or (new_member.clan and coc.utils.correct_tag(new_member.clan.tag) != coc.utils.correct_tag(self.bot.clan_tag)): return
        
        diff = new_member.trophies - old_member.trophies
        if abs(diff) < 5: return
        action = "ganhou" if diff > 0 else "perdeu"
        color = discord.Color.green() if diff > 0 else discord.Color.red()
        emoji = "🏆" if diff > 0 else "💔"
        embed = discord.Embed(description=f"{emoji} **{new_member.name}** {action} **{abs(diff)}** troféus (Total: {format_trophies(new_member.trophies)})", color=color)
        
        await self._send_log_embed(embed, target_channel_id=self.bot.channel_id)

    async def handle_clan_member_league_change(self, old_member, new_member):
        if self.bot.maintenance_mode or (new_member.clan and coc.utils.correct_tag(new_member.clan.tag) != coc.utils.correct_tag(self.bot.clan_tag)): return
        
        old_league = old_member.league.name if old_member.league and hasattr(old_member.league, 'name') else "N/A"
        new_league = new_member.league.name if new_member.league and hasattr(new_member.league, 'name') else "N/A"
        if old_league == new_league: return

        embed = discord.Embed(title="🛡️ Mudança de Liga", description=f"**{new_member.name}** mudou de liga!", color=0x6E2C00)
        embed.add_field(name="Liga Anterior", value=old_league, inline=True)
        embed.add_field(name="Nova Liga", value=new_league, inline=True)
        if hasattr(new_member.league, 'icon') and hasattr(new_member.league.icon, 'medium'):
            embed.set_thumbnail(url=new_member.league.icon.medium)
            
        await self._send_log_embed(embed, target_channel_id=self.bot.channel_id)

    async def handle_member_donations(self, old_member, new_member):
        if self.bot.maintenance_mode or (new_member.clan and coc.utils.correct_tag(new_member.clan.tag) != coc.utils.correct_tag(self.bot.clan_tag)): return
        
        diff = new_member.donations - old_member.donations
        if diff <= 0: return
        embed = discord.Embed(description=f"🎁 **{new_member.name}** doou **{diff}** tropas (Total: {new_member.donations}).", color=0xf1c40f)
        if new_member.clan and new_member.clan.badge:
             embed.set_author(name=f"Clã: {new_member.clan.name}", icon_url=new_member.clan.badge.url)
             
        await self._send_log_embed(embed, target_channel_id=self.bot.donations_channel_id)

    async def handle_member_received(self, old_member, new_member):
        if self.bot.maintenance_mode or (new_member.clan and coc.utils.correct_tag(new_member.clan.tag) != coc.utils.correct_tag(self.bot.clan_tag)): return
        
        diff = new_member.received - old_member.received
        if diff <= 0: return
        embed = discord.Embed(description=f"📥 **{new_member.name}** recebeu **{diff}** tropas (Total: {new_member.received}).", color=0x3498db)
        if new_member.clan and new_member.clan.badge:
             embed.set_author(name=f"Clã: {new_member.clan.name}", icon_url=new_member.clan.badge.url)
             
        await self._send_log_embed(embed, target_channel_id=self.bot.donations_channel_id)

    async def handle_member_war_opted_in_change(self, member, old_status=None, new_status=None):
        if self.bot.maintenance_mode: return
        if member.clan and coc.utils.correct_tag(member.clan.tag) != coc.utils.correct_tag(self.bot.clan_tag): return

        if old_status is None or new_status is None:
            raw = getattr(member, '_raw_data', {}) or {}
            raw_pref = raw.get('warPreference', None)
            if raw_pref is None:
                if old_status is None: old_status = False
                if new_status is None: new_status = False
            else:
                if old_status is None: old_status = raw_pref == 'in'
                if new_status is None: new_status = raw_pref == 'in'

        if old_status == new_status: return

        status_text = "✅ Optado (Guerra)" if new_status else "❌ Fora (Guerra)"
        color = discord.Color.green() if new_status else discord.Color.red()

        embed = discord.Embed(
            title="⚔️ Mudança de Status de Guerra",
            description=f"**{member.name}** alterou seu status de guerra.",
            color=color
        )
        embed.add_field(name="Status Antigo", value="✅ Optado" if old_status else "❌ Fora", inline=True)
        embed.add_field(name="Novo Status", value=status_text, inline=True)
        embed.add_field(name="CV", value=format_th(getattr(member, 'town_hall', 0)), inline=True)

        channel_id = self.bot.war_preference_channel_id or self.bot.channel_id
        await self._send_log_embed(embed, target_channel_id=channel_id)

    @tasks.loop(minutes=5)
    async def check_war_preference_task(self):
        if self.bot.maintenance_mode or not self.bot.api_client: return
        try:
            clan = await self.bot.api_client.get_clan(self.bot.clan_tag, lookup_cache=False)
            if not clan or not clan.members: return

            member_tags = [m.tag for m in clan.members]

            sem = asyncio.Semaphore(10)

            async def fetch_pref(tag):
                async with sem:
                    try:
                        player = await self.bot.api_client.get_player(tag, lookup_cache=False)
                        opted = getattr(player, 'war_opted_in', None)
                        if opted is None:
                            opted = False
                        return tag, opted
                    except Exception:
                        return tag, False

            results = await asyncio.gather(*[fetch_pref(t) for t in member_tags], return_exceptions=True)
            now = {}
            for r in results:
                if isinstance(r, tuple):
                    now[r[0]] = r[1]

            if not hasattr(self, '_last_war_prefs'):
                amostra = []
                for tag in list(now.keys())[:3]:
                    m = discord.utils.get(clan.members, tag=tag)
                    name = m.name if m else tag
                    amostra.append(f"{name}={now[tag]}")
                logger.info(f"[WarPref-1st] _last_war_prefs initialized with {len(now)} members. Amostra: {amostra}")
                self._last_war_prefs = now
                return

            changes = 0
            for tag, opted_in in now.items():
                old = self._last_war_prefs.get(tag)
                if old is not None and old != opted_in:
                    changes += 1
                    member_cached = discord.utils.get(clan.members, tag=tag)
                    if member_cached:
                        logger.info(f"[WarPref-CHANGE] {member_cached.name} ({tag}): {old} -> {opted_in}")
                        await self.handle_member_war_opted_in_change(member_cached, old_status=old, new_status=opted_in)

            if changes == 0:
                logger.info(f"[WarPref] No changes detected ({len(now)} members checked)")
            else:
                logger.info(f"[WarPref] {changes} change(s) detected and notified")

            self._last_war_prefs = now
        except Exception as e:
            logger.error(f"[WarPref-ERROR] {e}", exc_info=True)

    @check_war_preference_task.before_loop
    async def before_check_war_preference_task(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(30)

    @tasks.loop(seconds=30)
    async def check_new_attack_task(self):
        if not self.bot.coc_client_ready.is_set() or not self.bot.api_client:
            return
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state != coc.WarState.in_war:
                if self.war_attack_cache["war_end_time"] is not None:
                    self.war_attack_cache = {"war_end_time": None, "processed_attacks": set()}
                return

            current_war_end_time = war.end_time.time if war.end_time else None

            if self.war_attack_cache["war_end_time"] != current_war_end_time:
                self.war_attack_cache = {"war_end_time": current_war_end_time, "processed_attacks": set()}
                if hasattr(war, 'attacks'):
                    for attack in war.attacks:
                        if attack and hasattr(attack, 'order'):
                            self.war_attack_cache["processed_attacks"].add(attack.order)
                return

            new_attacks = []
            if hasattr(war, 'attacks'):
                for attack in war.attacks:
                    if attack and hasattr(attack, 'order') and attack.order not in self.war_attack_cache["processed_attacks"]:
                        new_attacks.append(attack)

            if new_attacks:
                for attack in sorted(new_attacks, key=lambda a: a.order):
                    self.war_attack_cache["processed_attacks"].add(attack.order)
                    await self.on_war_attack(attack, war)

        except (coc.PrivateWarLog, coc.NotFound):
            if self.war_attack_cache["war_end_time"] is not None:
                self.war_attack_cache = {"war_end_time": None, "processed_attacks": set()}
        except Exception as e:
            logger.error(f"Erro na task de novos ataques: {e}", exc_info=True)

    @check_new_attack_task.before_loop
    async def before_check_new_attack_task(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))

