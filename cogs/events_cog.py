# -*- coding: utf-8 -*-
import logging
import discord
from discord.ext import commands, tasks
import coc
import asyncio
import datetime

logger = logging.getLogger("events_cog")

class EventsCog(commands.Cog, name="Eventos do Clã"):
    """Cog para gerenciar e notificar todos os eventos do clã e de guerra."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # USA DIRETAMENTE O CLIENTE PRINCIPAL, JÁ LOGADO
        self.api_client: coc.Client = bot.api_client
        self.war_attack_cache = {"war_end_time": None, "processed_attacks": set()}

    async def cog_load(self):
        """Adiciona os listeners de evento ao cliente principal quando o cog é carregado."""
        try:
            logger.info("Registrando listeners de eventos do clã no cliente principal...")
            self._add_event_listeners()
            self.check_new_attack_task.start()
            logger.info("Listeners de eventos registrados com sucesso.")
        except Exception as e:
            logger.error(f"Erro crítico ao carregar EventsCog: {e}", exc_info=True)
            
    async def cog_unload(self):
        """Remove os listeners de evento ao descarregar o cog."""
        self.check_new_attack_task.cancel()
        self._remove_event_listeners()
        logger.info("Listeners de eventos removidos.")

    def _add_event_listeners(self):
        """Adiciona as funções deste cog como listeners no cliente de API principal."""
        # SOLUÇÃO DEFINITIVA: Registra os eventos no api_client principal
        self.api_client.add_listener(self.on_clan_member_join, "on_clan_member_join")
        self.api_client.add_listener(self.on_clan_member_leave, "on_clan_member_leave")
        self.api_client.add_listener(self.on_clan_member_role_change, "on_clan_member_role_change")
        self.api_client.add_listener(self.on_clan_member_trophies_change, "on_clan_member_trophies_change")
        self.api_client.add_listener(self.on_clan_member_league_change, "on_clan_member_league_change")
        self.api_client.add_listener(self.on_member_donations, "on_member_donations")
        self.api_client.add_listener(self.on_member_received, "on_member_received")

    def _remove_event_listeners(self):
        """Remove os listeners para evitar duplicação ao recarregar o cog."""
        self.api_client.remove_listener(self.on_clan_member_join, "on_clan_member_join")
        self.api_client.remove_listener(self.on_clan_member_leave, "on_clan_member_leave")
        self.api_client.remove_listener(self.on_clan_member_role_change, "on_clan_member_role_change")
        self.api_client.remove_listener(self.on_clan_member_trophies_change, "on_clan_member_trophies_change")
        self.api_client.remove_listener(self.on_clan_member_league_change, "on_clan_member_league_change")
        self.api_client.remove_listener(self.on_member_donations, "on_member_donations")
        self.api_client.remove_listener(self.on_member_received, "on_member_received")

    async def _send_log_embed(self, embed_to_log: discord.Embed, content: str = None, target_channel_id: int = None):
        """Função centralizada para enviar embeds para o canal de log."""
        channel_id_to_use = target_channel_id or self.bot.channel_id
        if not channel_id_to_use: return

        await self.bot.wait_until_ready()
        try:
            channel = self.bot.get_channel(channel_id_to_use) or await self.bot.fetch_channel(channel_id_to_use)
            embed_to_log.set_footer(text=f"Bot: {self.bot.user.name} | v{self.bot.bot_version} • {self.bot.timezone.localize(datetime.datetime.now()).strftime('%d/%m/%Y %H:%M')}")
            embed_to_log.timestamp = self.bot.timezone.localize(datetime.datetime.now())
            await channel.send(content=content, embed=embed_to_log)
        except (discord.NotFound, discord.Forbidden, Exception) as e:
            logger.error(f"Erro ao enviar embed para o canal {channel_id_to_use}: {e}", exc_info=True)

    # --- FUNÇÕES QUE RESPONDEM AOS EVENTOS ---
    async def on_clan_member_join(self, member, clan):
        if self.bot.maintenance_mode or clan.tag != self.bot.clan_tag: return
        embed = discord.Embed(title="➡️ Novo Membro no Clã", description=f"**{member.name}** ({member.tag}) entrou no clã.", color=discord.Color.blue())
        embed.add_field(name="CV", value=member.town_hall, inline=True)
        embed.add_field(name="Liga", value=member.league.name if member.league else "N/A", inline=True)
        embed.add_field(name="Troféus", value=f"🏆 {member.trophies}", inline=True)
        await self._send_log_embed(embed)

    async def on_clan_member_leave(self, member, clan):
        if self.bot.maintenance_mode or clan.tag != self.bot.clan_tag: return
        embed = discord.Embed(title="⬅️ Membro Saiu do Clã", description=f"**{member.name}** ({member.tag}) saiu do clã.", color=discord.Color.dark_grey())
        embed.add_field(name="CV", value=member.town_hall, inline=True)
        embed.add_field(name="Cargo", value=member.role.name.capitalize() if member.role else "N/A", inline=True)
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
            
            attacker_str = f"{attacker.map_position:02d} {attacker.name} (CV{attacker.town_hall})"
            defender_str = f"{defender.map_position:02d} {defender.name} (CV{defender.town_hall})"
            
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
                if war.clan.badge: embed.set_thumbnail(url=war.clan.badge.url)
                await self._send_log_embed(embed)
        except Exception as e:
            logger.error(f"Erro em on_war_attack: {e}", exc_info=True)
    
    async def on_clan_member_role_change(self, old_member, new_member):
        if self.bot.maintenance_mode: return
        embed = discord.Embed(title="✨ Mudança de Cargo", description=f"O cargo de **{new_member.name}** foi alterado.", color=discord.Color.purple())
        embed.add_field(name="Cargo Antigo", value=old_member.role.name.capitalize(), inline=True)
        embed.add_field(name="Novo Cargo", value=new_member.role.name.capitalize(), inline=True)
        await self._send_log_embed(embed)
        
    async def on_clan_member_trophies_change(self, old_member, new_member):
        if self.bot.maintenance_mode: return
        diff = new_member.trophies - old_member.trophies
        if diff == 0: return
        action = "ganhou" if diff > 0 else "perdeu"
        color = discord.Color.green() if diff > 0 else discord.Color.red()
        emoji = "🏆" if diff > 0 else "💔"
        embed = discord.Embed(description=f"{emoji} **{new_member.name}** {action} **{abs(diff)}** troféus (Total: {new_member.trophies})", color=color)
        await self._send_log_embed(embed)

    async def on_clan_member_league_change(self, old_member, new_member):
        if self.bot.maintenance_mode: return
        embed = discord.Embed(title="🛡️ Mudança de Liga", description=f"**{new_member.name}** mudou de liga!", color=0x6E2C00)
        embed.add_field(name="Liga Anterior", value=old_member.league.name if old_member.league else "N/A", inline=True)
        embed.add_field(name="Nova Liga", value=new_member.league.name if new_member.league else "N/A", inline=True)
        if hasattr(new_member.league, 'icon') and hasattr(new_member.league.icon, 'medium'):
            embed.set_thumbnail(url=new_member.league.icon.medium)
        await self._send_log_embed(embed)

    async def on_member_donations(self, old_member, new_member):
        if self.bot.maintenance_mode: return
        diff = new_member.donations - old_member.donations
        if diff <= 0: return
        embed = discord.Embed(description=f"🎁 **{new_member.name}** doou **{diff}** tropas (Total: {new_member.donations}).", color=0xf1c40f)
        embed.set_author(name=f"Clã: {new_member.clan.name}", icon_url=new_member.clan.badge.url)
        await self._send_log_embed(embed)

    async def on_member_received(self, old_member, new_member):
        if self.bot.maintenance_mode: return
        diff = new_member.received - old_member.received
        if diff <= 0: return
        embed = discord.Embed(description=f"📥 **{new_member.name}** recebeu **{diff}** tropas (Total: {new_member.received}).", color=0x3498db)
        embed.set_author(name=f"Clã: {new_member.clan.name}", icon_url=new_member.clan.badge.url)
        await self._send_log_embed(embed)

    # --- TASKS ---
    @tasks.loop(seconds=30)
    async def check_new_attack_task(self):
        await self.bot.wait_until_ready()
        if not self.api_client: return
        try:
            war = await self.api_client.get_current_war(self.bot.clan_tag)
            if not war or war.state != 'inWar':
                self.war_attack_cache = {"war_end_time": None, "processed_attacks": set()}
                return

            if self.war_attack_cache["war_end_time"] != war.end_time.time:
                self.war_attack_cache = {"war_end_time": war.end_time.time, "processed_attacks": {a.order for a in war.attacks}}
                return
            
            new_attacks = [a for a in war.attacks if a.order not in self.war_attack_cache["processed_attacks"]]
            if new_attacks:
                for attack in sorted(new_attacks, key=lambda a: a.order):
                    await self.on_war_attack(attack, war)
                    self.war_attack_cache["processed_attacks"].add(attack.order)
        except (coc.PrivateWarLog, coc.NotFound): pass
        except Exception as e:
            logger.error(f"Erro na task de novos ataques: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))

