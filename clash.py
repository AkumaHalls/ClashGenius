# -*- coding: utf-8 -*-
# Versão 20.1.3-FIXED - Erro global coc_client completamente resolvido

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
BOT_VERSION = "20.1.3-FIXED"
TIMEZONE = pytz.timezone('America/Sao_Paulo')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# --- Inicialização dos Clientes ---
bot = commands.Bot(command_prefix="!", intents=intents)
# CORREÇÃO: Inicializar como None, será criado depois
coc_client = None
events_client = None

# --- Caches em Memória ---
player_short_term_cache: Dict[str, Any] = {}
clan_cache: Dict[str, Dict[str, Any]] = {}
web_api_cache: Dict[str, Dict[str, Any]] = {}
CACHE_DURATION_SECONDS = 300
WEB_API_CACHE_DURATION_SECONDS = 45

# --- FUNÇÕES AUXILIARES (HELPERS) ---
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
        logger.info(f"Embed enviado com sucesso: {embed_to_log.title}")
    except (discord.NotFound, discord.Forbidden) as e:
        logger.error(f"Não foi possível enviar mensagem para o canal {CHANNEL_ID}: {e}")
    except Exception as e:
        logger.error(f"Erro inesperado ao enviar embed: {e}", exc_info=True)

# --- FUNÇÕES DE BUSCA DE DADOS (API CoC) ---
async def get_player_data(tag: str) -> Any:
    global coc_client
    if not coc_client:
        logger.error("coc_client não inicializado")
        return None
        
    normalized_tag = coc.utils.correct_tag(tag)
    if normalized_tag in player_short_term_cache:
        return player_short_term_cache[normalized_tag]
    
    try:
        player = await coc_client.get_player(normalized_tag)
        player_short_term_cache[normalized_tag] = player
        return player
    except Exception as e:
        logger.error(f"Erro ao buscar dados do jogador {tag}: {e}")
        return None

async def get_clan_data_with_cache(tag: str) -> Any:
    global coc_client
    if not coc_client:
        logger.error("coc_client não inicializado")
        return None
        
    normalized_tag = coc.utils.correct_tag(tag)
    now = datetime.datetime.now()
    
    if normalized_tag in clan_cache:
        cache_entry = clan_cache[normalized_tag]
        if "timestamp" in cache_entry and isinstance(cache_entry["timestamp"], datetime.datetime):
            if (now - cache_entry["timestamp"]).total_seconds() < CACHE_DURATION_SECONDS:
                return cache_entry["data"]
    
    try:
        clan_data = await coc_client.get_clan(normalized_tag)
        clan_cache[normalized_tag] = {"data": clan_data, "timestamp": now}
        return clan_data
    except Exception as e:
        logger.error(f"Erro ao buscar dados do clã {tag}: {e}")
        return None

# --- DEFINIÇÃO DOS EVENTOS DO COC ---
async def on_clan_member_join(member, clan):
    try:
        logger.info(f"Evento disparado: {member.name} entrou no clã {clan.name}")
        if clan.tag != CLAN_TAG: 
            return
            
        embed = discord.Embed(
            title="➡️ Novo Membro no Clã", 
            description=f"**{member.name}** ({member.tag}) entrou no clã.", 
            color=discord.Color.blue()
        )
        embed.add_field(name="CV", value=member.town_hall, inline=True)
        embed.add_field(name="Liga", value=member.league.name if member.league else "N/A", inline=True)
        embed.add_field(name="Troféus", value=f"🏆 {member.trophies}", inline=True)
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no evento member_join: {e}", exc_info=True)

async def on_clan_member_leave(member, clan):
    try:
        logger.info(f"Evento disparado: {member.name} saiu do clã {clan.name}")
        if clan.tag != CLAN_TAG: 
            return
            
        embed = discord.Embed(
            title="⬅️ Membro Saiu do Clã", 
            description=f"**{member.name}** ({member.tag}) saiu do clã.", 
            color=discord.Color.dark_grey()
        )
        embed.add_field(name="CV", value=member.town_hall, inline=True)
        embed.add_field(name="Cargo", value=member.role.name.capitalize() if member.role else "N/A", inline=True)
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no evento member_leave: {e}", exc_info=True)

async def on_war_attack(attack, war):
    try:
        logger.info(f"Evento disparado: Ataque de {attack.attacker.name}")
        if not (attack.attacker.clan and attack.attacker.clan.tag == CLAN_TAG):
            return
        
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
    except Exception as e:
        logger.error(f"Erro no evento war_attack: {e}", exc_info=True)

async def on_clan_member_role_change(old_member, new_member):
    try:
        logger.info(f"Evento disparado: Mudança de cargo de {new_member.name}")
        embed = discord.Embed(
            title="✨ Mudança de Cargo", 
            description=f"O cargo de **{new_member.name}** foi alterado.", 
            color=discord.Color.purple()
        )
        embed.add_field(name="Cargo Antigo", value=old_member.role.name.capitalize(), inline=True)
        embed.add_field(name="Novo Cargo", value=new_member.role.name.capitalize(), inline=True)
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no evento member_role_change: {e}", exc_info=True)

async def on_clan_member_trophies_change(old_member, new_member):
    try:
        diff = new_member.trophies - old_member.trophies
        # Só notificar mudanças significativas
        if abs(diff) < 10:  # Ignorar pequenas mudanças
            return
            
        logger.info(f"Evento disparado: {new_member.name} mudança de troféus: {diff}")
        action = "ganhou" if diff > 0 else "perdeu"
        color = discord.Color.green() if diff > 0 else discord.Color.red()
        embed = discord.Embed(
            description=f"**{new_member.name}** {action} **{abs(diff)}** troféus (Total: {new_member.trophies})", 
            color=color
        )
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no evento member_trophies_change: {e}", exc_info=True)

async def on_clan_member_league_change(old_member, new_member):
    try:
        logger.info(f"Evento disparado: {new_member.name} mudou de liga")
        embed = discord.Embed(
            title="🛡️ Mudança de Liga", 
            description=f"**{new_member.name}** mudou de liga!", 
            color=0x6E2C00
        )
        embed.add_field(name="Liga Anterior", value=old_member.league.name if old_member.league else "N/A", inline=True)
        embed.add_field(name="Nova Liga", value=new_member.league.name if new_member.league else "N/A", inline=True)
        if hasattr(new_member.league, 'icon') and hasattr(new_member.league.icon, 'medium'):
            embed.set_thumbnail(url=new_member.league.icon.medium)
        await send_log_embed(embed)
    except Exception as e:
        logger.error(f"Erro no evento member_league_change: {e}", exc_info=True)

# --- CONFIGURAÇÃO DOS EVENTOS COC ---
async def setup_coc_events():
    """Função para configurar eventos CoC após bot estar ready"""
    global coc_client, events_client
    
    try:
        logger.info("Iniciando configuração dos eventos CoC...")
        
        # Fechar cliente anterior se existir
        if coc_client and hasattr(coc_client, '_session') and coc_client._session and not coc_client._session.closed:
            await coc_client.close()
        
        # Criar EventsClient
        events_client = coc.EventsClient()
        
        # Login
        await events_client.login(COC_EMAIL, COC_PASSWORD)
        logger.info("Login no CoC EventsClient bem-sucedido.")
        
        # Registrar eventos usando decoradores corretos
        events_client.add_clan_updates(CLAN_TAG)
        events_client.add_war_updates(CLAN_TAG)
        
        # Registrar os eventos
        @events_client.event
        @coc.ClanEvents.member_join()
        async def _(member, clan):
            await on_clan_member_join(member, clan)
            
        @events_client.event
        @coc.ClanEvents.member_leave()
        async def _(member, clan):
            await on_clan_member_leave(member, clan)
            
        @events_client.event
        @coc.WarEvents.attack()
        async def _(attack, war):
            await on_war_attack(attack, war)
            
        @events_client.event
        @coc.ClanEvents.member_role()
        async def _(old_member, new_member):
            await on_clan_member_role_change(old_member, new_member)
            
        @events_client.event
        @coc.ClanEvents.member_trophies()
        async def _(old_member, new_member):
            await on_clan_member_trophies_change(old_member, new_member)
            
        @events_client.event
        @coc.ClanEvents.member_league()
        async def _(old_member, new_member):
            await on_clan_member_league_change(old_member, new_member)
        
        # Atualizar referência global
        coc_client = events_client
        
        logger.info("Todos os eventos do CoC foram registrados com sucesso!")
        
        # Testar conexão
        test_clan = await coc_client.get_clan(CLAN_TAG)
        logger.info(f"Teste de conexão bem-sucedido: {test_clan.name} tem {test_clan.member_count} membros")
        
    except Exception as e:
        logger.error(f"Erro ao configurar eventos CoC: {e}", exc_info=True)

# --- EVENTO ON_READY DO BOT DO DISCORD ---
@bot.event
async def on_ready():
    logger.info(f"Bot {bot.user.name} online! Versão: {BOT_VERSION}")
    try:
        # Primeiro, configurar os eventos CoC
        await setup_coc_events()
        
        # Depois, enviar mensagem de status
        clan = await coc_client.get_clan(CLAN_TAG)
        embed = discord.Embed(
            title=f"✅ ClashGenius Online | {clan.name}", 
            description=f"Monitoramento ativado para o clã **{clan.name} ({clan.tag})**.", 
            color=discord.Color.green()
        )
        embed.add_field(
            name="📊 Status do Clã", 
            value=f"**Membros:** {clan.member_count}/50\n**Troféus:** 🏆 {clan.points}", 
            inline=True
        )
        embed.add_field(
            name="⚙️ Status do Bot", 
            value=f"**Versão:** {BOT_VERSION}\n**API CoC:** ✅ OK", 
            inline=True
        )
        if clan.badge:
            embed.set_thumbnail(url=clan.badge.url)
        await send_log_embed(embed)
        
    except Exception as e:
        logger.error(f"Erro ao enviar o embed de inicialização: {e}", exc_info=True)

# --- ROTINAS E HANDLERS DO PAINEL WEB ---
async def get_cached_web_data(key: str, func, *args):
    now = datetime.datetime.now()
    if key in web_api_cache and (now - web_api_cache[key]["timestamp"]).total_seconds() < WEB_API_CACHE_DURATION_SECONDS:
        return web_api_cache[key]["data"]
    
    data = await func(*args)
    web_api_cache[key] = {"data": data, "timestamp": now}
    return data

async def fetch_clan_info_for_web() -> Dict[str, Any]:
    try:
        clan = await get_clan_data_with_cache(CLAN_TAG)
        if not clan:
            return {"error": "Clan not found"}
            
        return {
            "name": clan.name, 
            "tag": clan.tag, 
            "level": clan.level,
            "members": clan.member_count,
            "trophies": clan.points,
            "description": clan.description or "Sem descrição"
        }
    except Exception as e:
        logger.error(f"Erro ao buscar info do clã para web: {e}")
        return {"error": str(e)}

async def api_clan_info_handler(request: web.Request) -> web.Response:
    try:
        data = await get_cached_web_data("web_clan_info", fetch_clan_info_for_web)
        return web.json_response(data)
    except Exception as e:
        logger.error(f"Erro no handler clan info: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def setup_web_server() -> Optional[web.AppRunner]:
    try:
        app = web.Application()
        app['bot'] = bot
        
        # Rotas da API
        app.router.add_get("/api/clan", api_clan_info_handler)
        app.router.add_get("/api/status", lambda r: web.json_response({
            "status": "online", 
            "version": BOT_VERSION,
            "timestamp": datetime.datetime.now(TIMEZONE).isoformat()
        }))
        
        # Rotas estáticas
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        if os.path.exists(static_dir):
            app.router.add_static('/static/', path=static_dir, name='static')
            painel_file = os.path.join(static_dir, "painel.html")
            if os.path.exists(painel_file):
                app.router.add_get("/painel", lambda r: web.FileResponse(painel_file))
        
        app.router.add_get("/", lambda r: web.Response(text=f"Bot running! v{BOT_VERSION}"))

        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        logger.info(f"Servidor web iniciado na porta {port}")
        return runner
        
    except Exception as e:
        logger.error(f"Erro ao configurar servidor web: {e}", exc_info=True)
        return None

# Comando de teste para verificar se eventos funcionam
@bot.slash_command(name="test_events", description="Testa se os eventos estão funcionando")
async def test_events(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
        
        if not coc_client:
            await interaction.followup.send("❌ Cliente CoC não inicializado!")
            return
        
        # Buscar dados atuais do clã
        clan = await coc_client.get_clan(CLAN_TAG)
        
        embed = discord.Embed(
            title="🔍 Teste de Eventos",
            description=f"Testando conexão com o clã **{clan.name}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Status", value="✅ Conectado", inline=True)
        embed.add_field(name="Membros", value=f"{clan.member_count}/50", inline=True)
        embed.add_field(name="Eventos", value="✅ Registrados", inline=True)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Erro no teste: {e}")

# --- FUNÇÃO PRINCIPAL DE EXECUÇÃO ---
async def main():
    """Função principal - inicialização sequencial"""
    global coc_client
    web_runner = None
    
    try:
        # Inicializar cliente CoC básico para testes iniciais
        coc_client = coc.Client()
        
        # Adiciona os clientes ao bot para acesso global
        bot.coc_client = coc_client
        bot.db = None
        bot.db_client = None

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

        # Login inicial no cliente CoC básico
        try:
            await coc_client.login(COC_EMAIL, COC_PASSWORD)
            logger.info("Login inicial no CoC bem-sucedido.")
        except coc.InvalidCredentials as e:
            logger.error(f"Credenciais do CoC inválidas: {e}")
            return
        except Exception as e:
            logger.error(f"Falha no login do CoC: {e}", exc_info=True)
            return

        # Inicia o servidor web
        web_runner = await setup_web_server()
        
        # Inicia o bot (que vai chamar setup_coc_events no on_ready)
        await bot.start(DISCORD_TOKEN)
        
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro na função main: {e}", exc_info=True)
    finally:
        # Cleanup
        try:
            if web_runner:
                await web_runner.cleanup()
            if coc_client and hasattr(coc_client, 'close'):
                await coc_client.close()
            if events_client and hasattr(events_client, 'close'):
                await events_client.close()
            if hasattr(bot, 'db_client') and bot.db_client:
                bot.db_client.close()
        except Exception as e:
            logger.error(f"Erro no cleanup: {e}")

if __name__ == "__main__":
    if not all([DISCORD_TOKEN, COC_EMAIL, COC_PASSWORD, CLAN_TAG]):
        logger.critical("Variáveis de ambiente essenciais faltando.")
        logger.critical("Necessário: DISCORD_TOKEN, COC_EMAIL, COC_PASSWORD, CLAN_TAG")
    else:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Bot desligado manualmente.")
        except Exception as e:
            logger.error(f"Erro fatal: {e}", exc_info=True)
