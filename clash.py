# -*- coding: utf-8 -*-
# Versão 20.0.1-STABLE - Reestrutura completa baseada na documentação oficial do coc.py para estabilidade.

import os
import logging
import asyncio
import datetime
import json
from aiohttp import web
from typing import Dict, List, Optional, Union, Set, Any
import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
import pytz
from dotenv import load_dotenv
import motor.motor_asyncio

# --- Configuração do Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("coc_discord_bot")

# --- Carregar Variáveis de Ambiente ---
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
COC_EMAIL = os.getenv("COC_EMAIL")
COC_PASSWORD = os.getenv("COC_PASSWORD")
CLAN_TAG = os.getenv("CLAN_TAG")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))
MONGO_DB_URL = os.getenv("MONGO_DB_URL")

# --- Constantes e Configurações Globais ---
BOT_VERSION = "20.0.1-STABLE"
TIMEZONE = pytz.timezone('America/Sao_Paulo')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# --- Inicialização dos Clientes ---
bot = commands.Bot(command_prefix="!", intents=intents)
coc_client = coc.EventsClient()

# --- Funções Auxiliares (Helpers) ---
async def send_log_embed(embed_to_log: discord.Embed, content: str = None) -> None:
    if not CHANNEL_ID:
        logger.warning("CHANNEL_ID não configurado. Não é possível enviar o embed.")
        return
    
    if not bot.is_ready():
        logger.warning("O Bot não está pronto. A aguardar antes de enviar o embed.")
        await bot.wait_until_ready()

    try:
        channel = bot.get_channel(CHANNEL_ID) or await bot.fetch_channel(CHANNEL_ID)
        if not embed_to_log.footer:
            embed_to_log.set_footer(text=f"Bot: {bot.user.name} | v{BOT_VERSION} • {datetime.datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M')}")
        if not embed_to_log.timestamp:
            embed_to_log.timestamp = datetime.datetime.now(TIMEZONE)
        
        await channel.send(content=content, embed=embed_to_log)
    except (discord.NotFound, discord.Forbidden) as e:
        logger.error(f"Não foi possível enviar mensagem para o canal {CHANNEL_ID}: {e}")
    except Exception as e:
        logger.error(f"Erro inesperado ao enviar embed: {e}", exc_info=True)

# --- Eventos do CoC (Decoradores) ---
@coc.ClanEvents.member_join()
async def on_clan_member_join(member, clan):
    if clan.tag != CLAN_TAG: return
    embed = discord.Embed(title="➡️ Novo Membro no Clã", description=f"**{member.name}** ({member.tag}) entrou no clã.", color=discord.Color.blue())
    embed.add_field(name="CV", value=member.town_hall, inline=True)
    embed.add_field(name="Liga", value=member.league.name if member.league else "N/A", inline=True)
    embed.add_field(name="Troféus", value=f"🏆 {member.trophies}", inline=True)
    await send_log_embed(embed)

@coc.ClanEvents.member_leave()
async def on_clan_member_leave(member, clan):
    if clan.tag != CLAN_TAG: return
    embed = discord.Embed(title="⬅️ Membro Saiu do Clã", description=f"**{member.name}** ({member.tag}) saiu do clã.", color=discord.Color.dark_grey())
    embed.add_field(name="CV", value=member.town_hall, inline=True)
    embed.add_field(name="Cargo", value=member.role.name.capitalize() if member.role else "N/A", inline=True)
    await send_log_embed(embed)

@coc.WarEvents.attack()
async def on_war_attack(attack, war):
    if attack.attacker.clan.tag != CLAN_TAG: return
    
    war_type = "CWL" if war.is_cwl else "Guerra"
    embed = discord.Embed(title=f"⚔️ Ataque na {war_type}!", color=discord.Color.orange())
    stars = "⭐" * attack.stars + "⚫" * (3 - attack.stars)
    our_clan = war.clan if war.clan.tag == CLAN_TAG else war.opponent
    opponent_clan = war.opponent if war.clan.tag == CLAN_TAG else war.clan

    embed.description = (
        f"**{attack.attacker.name}** atacou **{attack.defender.name}**\n"
        f"`CV{attack.attacker.town_hall} vs CV{attack.defender.town_hall}`"
    )
    embed.add_field(name="Resultado do Ataque", value=f"{stars} **{attack.destruction}%**", inline=False)
    embed.add_field(name="Placar Atual", value=f"**{our_clan.name}:** {our_clan.stars}⭐\n**{opponent_clan.name}:** {opponent_clan.stars}⭐", inline=True)
    embed.add_field(name="Ataques Usados", value=f"{our_clan.attacks_used} / {war.team_size * war.attacks_per_member}", inline=True)
    await send_log_embed(embed)

@coc.ClanEvents.member_role()
async def on_clan_member_role_change(old_member, new_member):
    embed = discord.Embed(title="✨ Mudança de Cargo", description=f"O cargo de **{new_member.name}** foi alterado.", color=discord.Color.purple())
    embed.add_field(name="Cargo Antigo", value=old_member.role.name.capitalize(), inline=True)
    embed.add_field(name="Novo Cargo", value=new_member.role.name.capitalize(), inline=True)
    await send_log_embed(embed)

@coc.ClanEvents.member_trophies()
async def on_clan_member_trophies_change(old_member, new_member):
    diff = new_member.trophies - old_member.trophies
    action = "ganhou" if diff > 0 else "perdeu"
    color = discord.Color.green() if diff > 0 else discord.Color.red()
    embed = discord.Embed(description=f"**{new_member.name}** {action} **{abs(diff)}** troféus (Total: {new_member.trophies})", color=color)
    await send_log_embed(embed)

@coc.ClanEvents.member_league()
async def on_clan_member_league_change(old_member, new_member):
    embed = discord.Embed(title="🛡️ Mudança de Liga", description=f"**{new_member.name}** mudou de liga!", color=0x6E2C00)
    embed.add_field(name="Liga Anterior", value=old_member.league.name, inline=True)
    embed.add_field(name="Nova Liga", value=new_member.league.name, inline=True)
    if hasattr(new_member.league, 'icon') and hasattr(new_member.league.icon, 'medium'):
        embed.set_thumbnail(url=new_member.league.icon.medium)
    await send_log_embed(embed)

# --- Evento On_Ready do Bot do Discord ---
@bot.event
async def on_ready():
    logger.info(f"Bot {bot.user.name} online! Versão: {BOT_VERSION}")
    try:
        clan = await coc_client.get_clan(CLAN_TAG)
        embed = discord.Embed(title=f"✅ ClashGenius Online | {clan.name}", description=f"Monitoramento ativado para o clã **{clan.name} ({clan.tag})**.", color=discord.Color.green())
        embed.add_field(name="📊 Status do Clã", value=f"**Membros:** {clan.member_count}/50\n**Troféus:** 🏆 {clan.points}", inline=True)
        embed.add_field(name="⚙️ Status do Bot", value=f"**Versão:** {BOT_VERSION}\n**API CoC:** ✅ OK", inline=True)
        if clan.badge:
            embed.set_thumbnail(url=clan.badge.url)
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro ao enviar o embed de inicialização: {e}", exc_info=True)

# --- Função Principal de Execução ---
async def main():
    # Conexão com o MongoDB
    if MONGO_DB_URL:
        try:
            bot.db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)
            bot.db = bot.db_client.get_default_database()
            await bot.db.command('ping')
            logger.info(f"Conectado ao MongoDB: {bot.db.name}")
        except Exception as e:
            logger.error(f"Falha ao conectar ao MongoDB: {e}", exc_info=True)
    else:
        logger.warning("MONGO_DB_URL não definida. A base de dados está desativada.")

    # Login no cliente CoC
    try:
        await coc_client.login(COC_EMAIL, COC_PASSWORD)
        logger.info("Login no CoC bem-sucedido.")
    except coc.InvalidCredentials as e:
        logger.error(f"Credenciais do CoC inválidas: {e}")
        return
    except Exception as e:
        logger.error(f"Falha no login do CoC: {e}", exc_info=True)
        return

    # Adiciona os clãs para monitoramento
    coc_client.add_clan_updates(CLAN_TAG)
    coc_client.add_war_updates(CLAN_TAG)
    
    # Regista os eventos decorados
    coc_client.add_events(
        on_clan_member_join,
        on_clan_member_leave,
        on_war_attack,
        on_clan_member_role_change,
        on_clan_member_trophies_change,
        on_clan_member_league_change
    )
    logger.info("Todos os eventos do CoC foram registados.")

    # Inicia o bot do Discord em segundo plano
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    if not all([DISCORD_TOKEN, COC_EMAIL, COC_PASSWORD, CLAN_TAG]):
        logger.critical("Variáveis de ambiente essenciais faltando.")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Bot desligado manualmente.")
