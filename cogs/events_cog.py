# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
import datetime

logger = logging.getLogger("events_cog")

class EventsCog(commands.Cog, name="Eventos do Clã"):
    """Cog para gerenciar e notificar eventos do clã e de guerra."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Este cog terá seu próprio cliente de eventos, como manda a biblioteca coc.py
        self.events_client = coc.EventsClient()
        self.war_attack_cache = {"war_end_time": None, "processed_attacks": set()}

        # Registra os handlers de eventos
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
        if self.events_client:
            await self.events_client.close()

    async def _send_log_embed(self, embed_to_log: discord.Embed, content: str = None, target_channel_id: int = None):
        """Envia embeds de log de forma segura, evitando crash por Rate Limit (429)."""
        channel_id_to_use = target_channel_id or self.bot.channel_id
        if not channel_id_to_use: return
        try:
            channel = self.bot.get_channel(channel_id_to_use) or await self.bot.fetch_channel(channel_id_to_use)
            now_in_timezone = datetime.datetime.now(self.bot.timezone)
            embed_to_log.set_footer(text=f"Bot: {self.bot.user.name} | v{self.bot.bot_version} • {now_in_timezone.strftime('%d/%m/%Y %H:%M')}")
            embed_to_log.timestamp = now_in_timezone
            
            # --- PROTEÇÃO ANTI-SPAM / RATE LIMIT ---
            try:
                await channel.send(content=content, embed=embed_to_log)
            except discord.errors.HTTPException as e:
                if e.status == 429:
                    # Se tomar Rate Limit, APENAS LOGA e desiste dessa mensagem.
                    # Tentar de novo (retry) em logs automáticos é perigoso e pode banir o IP.
                    logger.warning(f"Rate Limit (429) no canal de logs {channel_id_to_use}. Mensagem ignorada para proteção.")
                    return
                else:
                    logger.error(f"Erro HTTP ao enviar log: {e}")
            # ---------------------------------------

        except Exception as e:
            logger.error(f"Erro ao enviar embed para o canal {channel_id_to_use}: {e}", exc_info=True)

    # --- FUNÇÕES QUE RESPONDEM AOS EVENTOS ---

    async def handle_clan_member_join(self, member, clan):
        if self.bot.maintenance_mode or clan.tag != self.bot.clan_tag:
            return

        logger.info(f"Evento member_join DETECTADO para {member.name} ({member.tag}).")

        watchlist_cog = self.bot.get_cog("Lista de Observação")
        if watchlist_cog:
            await watchlist_cog.check_and_alert_on_join(member)

        embed = discord.Embed(title="➡️ Membro Entrou no Clã", description=f"**{member.name}** ({member.tag}) entrou no clã.", color=discord.Color.dark_green())
        embed.add_field(name="CV", value=member.town_hall, inline=True)
        if hasattr(member, 'league') and member.league and hasattr(member.league, 'name'):
            embed.add_field(name="Liga", value=member.league.name, inline=True)
        await self._send_log_embed(embed)

    async def handle_clan_member_leave(self, member, clan):
        if self.bot.maintenance_mode or clan.tag != self.bot.clan_tag: return
        embed = discord.Embed(title="⬅️ Membro Saiu do Clã", description=f"**{member.name}** ({member.tag}) saiu do clã.", color=discord.Color.dark_grey())
        embed.add_field(name="CV", value=member.town_hall, inline=True)
        role_name = member.role.name.capitalize() if member.role and hasattr(member.role, 'name') else "N/A"
        embed.add_field(name="Cargo", value=role_name, inline=True)
        await self._send_log_embed(embed)

    async def on_war_attack(self, attack, war):
        if self.bot.maintenance_mode: return
        try:
            attacker = war.get_member(attack.attacker_tag)
            defender = war.get_member(attack.defender_tag)

            if not attacker or not defender: return

            is_our_attack = attacker.clan.tag == self.bot.clan_tag
            war_type = "CWL" if war.is_cwl else "Guerra"
            stars_str = "⭐" * attack.stars + "⚫" * (3 - attack.stars)

            attacker_map_pos = f"{attacker.map_position:02d}" if hasattr(attacker, 'map_position') else "??"
            defender_map_pos = f"{defender.map_position:02d}" if hasattr(defender, 'map_position') else "??"

            attacker_str = f"`{attacker_map_pos}` **{attacker.name}** (CV{attacker.town_hall})"
            defender_str = f"`{defender_map_pos}` **{defender.name}** (CV{defender.town_hall})"

            if is_our_attack:
                embed = discord.Embed(title=f"⚔️ Ataque Realizado ({war_type})", description=f"{attacker.clan.name}", color=discord.Color.blue())
                embed.add_field(name="Detalhes", value=f"{attacker_str} atacou {defender_str}", inline=False)
                embed.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
                if war.opponent.badge: embed.set_thumbnail(url=war.opponent.badge.url)
                await self._send_log_embed(embed)

                if attack.stars <= 1:
                    alert_embed = discord.Embed(title=f"⚠️ Ataque fora do padrão!", description=f"**{attacker.clan.name}**\n⚔️ **Ataque Realizado ({war_type})**", color=discord.Color.red())
                    alert_embed.add_field(name="Detalhes", value=f"{attacker_str} atacou {defender_str}", inline=False)
                    alert_embed.add_field(name="Resultado", value=f"{'⚫⚫⚫' if attack.stars == 0 else '⭐⚫⚫'} ({attack.destruction}%)", inline=False)
                    if war.opponent.badge: alert_embed.set_thumbnail(url=war.opponent.badge.url)
                    role_mention = f"<@&{self.bot.role_id_1star_alert}>" if self.bot.role_id_1star_alert else ""
                    await self._send_log_embed(alert_embed, content=f"{role_mention} Atenção ao ataque fora do padrão!")
            else:
                embed = discord.Embed(title=f"🛡️ Defesa Recebida ({war_type})", description=f"{defender.clan.name}", color=discord.Color.orange())
                embed.add_field(name="Detalhes", value=f"{defender_str} foi atacado por {attacker_str}", inline=False)
                embed.add_field(name="Resultado", value=f"{stars_str} ({attack.destruction}%)", inline=False)
                if hasattr(war, 'clan') and war.clan and hasattr(war.clan, 'badge') and war.clan.badge:
                     embed.set_thumbnail(url=war.clan.badge.url)
                await self._send_log_embed(embed)
        except Exception as e:
            logger.error(f"Erro em on_war_attack: {e}", exc_info=True)

    async def handle_clan_member_role_change(self, old_member, new_member):
        if self.bot.maintenance_mode: return
        old_role = old_member.role.name.capitalize() if old_member.role and hasattr(old_member.role, 'name') else "N/A"
        new_role = new_member.role.name.capitalize() if new_member.role and hasattr(new_member.role, 'name') else "N/A"
        if old_role == new_role: return

        embed = discord.Embed(title="✨ Mudança de Cargo", description=f"O cargo de **{new_member.name}** foi alterado.", color=discord.Color.purple())
        embed.add_field(name="Cargo Antigo", value=old_role, inline=True)
        embed.add_field(name="Novo Cargo", value=new_role, inline=True)
        await self._send_log_embed(embed)

    async def handle_clan_member_trophies_change(self, old_member, new_member):
        if self.bot.maintenance_mode: return
        diff = new_member.trophies - old_member.trophies
        if abs(diff) < 5: return
        action = "ganhou" if diff > 0 else "perdeu"
        color = discord.Color.green() if diff > 0 else discord.Color.red()
        emoji = "🏆" if diff > 0 else "💔"
        embed = discord.Embed(description=f"{emoji} **{new_member.name}** {action} **{abs(diff)}** troféus (Total: {new_member.trophies})", color=color)
        await self._send_log_embed(embed)

    async def handle_clan_member_league_change(self, old_member, new_member):
        if self.bot.maintenance_mode: return
        old_league = old_member.league.name if old_member.league and hasattr(old_member.league, 'name') else "N/A"
        new_league = new_member.league.name if new_member.league and hasattr(new_member.league, 'name') else "N/A"
        if old_league == new_league: return

        embed = discord.Embed(title="🛡️ Mudança de Liga", description=f"**{new_member.name}** mudou de liga!", color=0x6E2C00)
        embed.add_field(name="Liga Anterior", value=old_league, inline=True)
        embed.add_field(name="Nova Liga", value=new_league, inline=True)
        if hasattr(new_member.league, 'icon') and hasattr(new_member.league.icon, 'medium'):
            embed.set_thumbnail(url=new_member.league.icon.medium)
        await self._send_log_embed(embed)

    async def handle_member_donations(self, old_member, new_member):
        if self.bot.maintenance_mode: return
        diff = new_member.donations - old_member.donations
        if diff <= 0: return
        embed = discord.Embed(description=f"🎁 **{new_member.name}** doou **{diff}** tropas (Total: {new_member.donations}).", color=0xf1c40f)
        if new_member.clan and new_member.clan.badge:
             embed.set_author(name=f"Clã: {new_member.clan.name}", icon_url=new_member.clan.badge.url)
        await self._send_log_embed(embed)

    async def handle_member_received(self, old_member, new_member):
        if self.bot.maintenance_mode: return
        diff = new_member.received - old_member.received
        if diff <= 0: return
        embed = discord.Embed(description=f"📥 **{new_member.name}** recebeu **{diff}** tropas (Total: {new_member.received}).", color=0x3498db)
        if new_member.clan and new_member.clan.badge:
             embed.set_author(name=f"Clã: {new_member.clan.name}", icon_url=new_member.clan.badge.url)
        await self._send_log_embed(embed)

    @tasks.loop(seconds=30)
    async def check_new_attack_task(self):
        if not self.bot.coc_client_ready.is_set() or not self.bot.api_client:
            return
        try:
            war = await self.bot.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state != 'inWar':
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
