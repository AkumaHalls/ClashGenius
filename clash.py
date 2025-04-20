# -*- coding: utf-8 -*-
# Versão 15.0.11 - Correção Final de SyntaxError e Indentação

import discord
from discord import app_commands
from discord.ext import commands, tasks
import coc
from coc import errors as coc_errors
import asyncio
import os
import logging
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from aiohttp import web
from typing import Optional

# Carrega variáveis de ambiente
load_dotenv()

# --- Configuração de Logging ---
log_formatter = logging.Formatter('%(asctime)s-%(levelname)s-[%(funcName)s]: %(message)s')
file_handler = logging.FileHandler("bot.log", encoding='utf-8')
file_handler.setFormatter(log_formatter)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler], force=True)
logger = logging.getLogger("clash-bot")
logger.info("Logging configurado em nível INFO.")

# --- Configurações e Validação ---
TOKEN = os.getenv('DISCORD_TOKEN')
EMAIL = os.getenv('COC_EMAIL')
PASSWORD = os.getenv('COC_PASSWORD')
CLAN_TAG = os.getenv('CLAN_TAG')
CHANNEL_ID_STR = os.getenv('CHANNEL_ID')
PORT = int(os.environ.get("PORT", 10000))

if not all([TOKEN, CLAN_TAG, CHANNEL_ID_STR]): logger.critical("FATAL: TOKEN, CLAN_TAG ou CHANNEL_ID faltando."); exit("Erro Conf.")
if not EMAIL or not PASSWORD: logger.critical("FATAL: Email/Senha CoC não configurados."); exit("Erro Conf: Credenciais CoC faltando.")
try: CHANNEL_ID = int(CHANNEL_ID_STR)
except ValueError: logger.critical(f"FATAL: CHANNEL_ID inválido ('{CHANNEL_ID_STR}')."); exit("Erro Conf.")
if not CLAN_TAG.startswith('#'): CLAN_TAG = f'#{CLAN_TAG}'
if not coc.utils.is_valid_tag(CLAN_TAG): logger.critical(f"FATAL: CLAN_TAG '{CLAN_TAG}' inválido."); exit("Erro Conf.")

# --- Caches ---
member_cache = {'members': {}, 'count': 0}
donation_cache = {}
war_cache = {'war_end_reported': {}, 'league_war_end_reported': {}, 'league_start_announced': False}
raid_weekend_cache = {'current_raid': None}

# --- Timezone ---
try: TIMEZONE = pytz.timezone('America/Sao_Paulo'); logger.info(f"Timezone: {TIMEZONE}")
except pytz.UnknownTimeZoneError: logger.error("TZ 'America/Sao_Paulo' não encontrado. Usando UTC."); TIMEZONE = pytz.utc

# --- Bot Discord ---
intents = discord.Intents.default(); intents.message_content = True; intents.members = True
bot = commands.Bot(command_prefix=commands.when_mentioned_or("!"), intents=intents, help_command=None)

# --- Emojis ---
emojis = {
    'donation': '🎁', 'join': '➡️', 'leave': '⬅️', 'war_win': '🏆', 'war_lose': '😥',
    'war_tie': '🤝', 'war_attack': '⚔️', 'war_defense': '🛡️', 'raid': '🔥', 'level_up': '⭐',
    'trophy': '🏆', 'time': '⏰', 'clan_capital': '🏰', 'missed_attack': '❌', 'info': 'ℹ️',
    'error': '❌', 'success': '✅', 'warning': '⚠️', 'league': '🌟',
    'received': '📥', 'progress': '📊', 'destruction': '💥', 'sync': '🔄', 'admin': '🛠️'
}

# --- Cliente CoC ---
coc_client = None

# --- Servidor Web para Health Check (Render) ---
async def health_check(request):
    return web.Response(text="ClashGenius is running!")

@bot.event
async def setup_hook():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    try:
        await site.start()
        logger.info(f"Servidor web de health check iniciado em http://0.0.0.0:{PORT}")
        bot.web_runner = runner
        bot.web_site = site
    except Exception as e:
        logger.critical(f"Falha ao iniciar servidor web na porta {PORT}: {e}", exc_info=True)
        # Adicionado um pass aqui para evitar erro caso a inicialização falhe,
        # mas o ideal seria tratar melhor ou parar o bot.
        pass


@bot.event
async def before_closing():
    logger.info("Recebido sinal para encerrar...")
    if hasattr(bot, 'web_runner'):
        logger.info("Encerrando servidor web...")
        try: await bot.web_runner.cleanup(); logger.info("Servidor web encerrado.")
        except Exception as e: logger.error(f"Erro ao encerrar servidor web: {e}", exc_info=True)
    if coc_client and hasattr(coc_client, 'close'):
        logger.info("Fechando cliente CoC...");
        try: await coc_client.close(); logger.info("Cliente CoC fechado.")
        except Exception as e: logger.error(f"Erro ao fechar cliente CoC: {e}")

# --- Inicialização CoC ---
async def initialize_coc_client():
    global coc_client
    logger.info("--- Iniciando Login Cliente CoC ---")
    if not EMAIL or not PASSWORD: logger.critical("Email/Senha CoC não encontrados."); return False
    last_error = None
    for attempt in range(1, 4):
        try:
            logger.info(f"[Tentativa {attempt}/3] Criando Client...")
            # Usando key_count=5 e key_names genérico como sugerido pela documentação atual do coc.py
            temp_client = coc.Client(key_count=5, key_names="cocpy-bot", throttle_limit=20)
            logger.info(f"[Tentativa {attempt}/3] Login com Email/Senha...")
            await asyncio.wait_for(temp_client.login(EMAIL, PASSWORD), timeout=60.0)

            # Se login() completou sem erro, consideramos OK.
            coc_client = temp_client; logger.info(f"[Tentativa {attempt}/3] Login CoC OK."); return True

        except coc_errors.AuthenticationError as e: logger.error(f"[Tentativa {attempt}/3] Falha autenticação: {e}"); last_error = e; return False # Erro fatal, não adianta tentar de novo
        except coc_errors.Maintenance as e: logger.warning(f"[Tentativa {attempt}/3] API CoC em manutenção: {e}"); last_error = e
        except asyncio.TimeoutError: logger.error(f"[Tentativa {attempt}/3] Timeout login API CoC."); last_error = asyncio.TimeoutError("Timeout login API CoC.")
        except Exception as e: logger.error(f"[Tentativa {attempt}/3] Erro login CoC: {e}", exc_info=True); last_error = e

        # Se chegou aqui, houve um erro (exceto AuthenticationError), espera e tenta novamente
        if attempt < 3:
            wait_time = 15 * attempt; logger.info(f"Aguardando {wait_time}s antes da próxima tentativa...")
            await asyncio.sleep(wait_time)

    # Se todas as tentativas falharam
    logger.critical(f"--- Falha login CoC após {attempt} tentativas. Último erro: {last_error} ---"); coc_client = None; return False

# --- Funções Auxiliares ---
async def get_clan_data(tag=None, timeout=30.0):
    global CLAN_TAG, coc_client
    if not coc_client or not hasattr(coc_client, 'http') or not coc_client.http: logger.error("CoC Client inválido em get_clan_data."); return None
    target_tag = tag or CLAN_TAG
    if not target_tag: logger.error("Tag clã não definida (get_clan_data)."); return None
    if not coc.utils.is_valid_tag(target_tag): raise coc_errors.InvalidTag(f"Tag clã inválida: {target_tag}")
    try:
        logger.debug(f"Buscando dados clã: {target_tag} (Timeout: {timeout}s)")
        clan = await asyncio.wait_for(coc_client.get_clan(target_tag), timeout=timeout)
        logger.debug(f"Dados clã '{getattr(clan, 'name', target_tag)}' recebidos.")
        return clan
    except coc_errors.NotFound: logger.error(f"Clã '{target_tag}' não encontrado."); raise
    except coc_errors.Maintenance as e: logger.warning(f"API CoC em manutenção (clã '{target_tag}'): {e}"); raise
    except coc_errors.ClashOfClansException as e: logger.warning(f"Erro API CoC ({type(e).__name__}) clã '{target_tag}': {e}"); raise
    except asyncio.TimeoutError: logger.error(f"Timeout ({timeout}s) clã '{target_tag}'."); raise
    except Exception as e: logger.error(f"Erro Inesperado ({type(e).__name__}) clã '{target_tag}': {e}", exc_info=True); raise

async def send_embeds_splitted(channel: discord.TextChannel, base_embed: discord.Embed, field_name: str, items_list: list, max_len: int = 1024, max_items_per_embed: int = 25):
    if not channel: # Adiciona verificação se o canal é válido
        logger.error("send_embeds_splitted: Canal inválido recebido.")
        return
    if not items_list: logger.debug(f"send_embeds_splitted: Lista vazia p/ '{field_name}' canal #{getattr(channel, 'name', '?')}."); return
    current_embed = base_embed.copy(); current_field_value = ""; fields_in_current_embed = len(current_embed.fields); total_embeds_sent = 0
    # Corrigido: Verificar se a lista é realmente uma lista de strings antes de juntar
    if items_list and all(isinstance(item, str) for item in items_list):
        fits_in_one_field = len("\n".join(items_list)) <= max_len
    else:
        fits_in_one_field = False # Assume que não cabe se não for lista de strings
    can_add_one_more_field = fields_in_current_embed < max_items_per_embed
    clear_fields_initially = not (fits_in_one_field and can_add_one_more_field)
    if clear_fields_initially and fields_in_current_embed > 0: logger.debug("send_embeds_splitted: Limpando campos base."); current_embed.clear_fields(); fields_in_current_embed = 0
    elif not can_add_one_more_field: logger.warning(f"send_embeds_splitted: Embed base já cheio."); return
    temp_field_list = []
    for i, item in enumerate(items_list):
        # Garante que o item é uma string
        item_str = str(item)
        item_line = item_str + "\n"; projected_length = len(current_field_value) + len(item_line)
        if projected_length > max_len or not current_field_value: # Inicia novo campo se > max_len ou se campo atual está vazio
            if current_field_value: # Se havia algo no campo anterior, adiciona-o à lista temporária
                 part_num = (total_embeds_sent * max_items_per_embed) + len(temp_field_list) + 1
                 # Modificado: Simplifica a lógica do título da parte
                 field_title = f"{field_name} (Parte {part_num})" if len(items_list) > max_items_per_embed else field_name
                 temp_field_list.append({"name": field_title, "value": current_field_value, "inline": False})
            current_field_value = item_line # Começa o novo campo com o item atual
            # Verifica se o embed atual está cheio (considerando os campos já adicionados + os temporários)
            if fields_in_current_embed + len(temp_field_list) >= max_items_per_embed:
                # Adiciona os campos temporários ao embed atual até o limite
                for field_data in temp_field_list:
                    if len(current_embed.fields) < max_items_per_embed: current_embed.add_field(**field_data)
                    else: break # Para se o embed ficar cheio
                # Envia o embed atual
                try:
                    logger.debug(f"Enviando embed dividido ({total_embeds_sent + 1}) #{getattr(channel, 'name', '?')}")
                    await channel.send(embed=current_embed)
                    total_embeds_sent += 1
                    await asyncio.sleep(0.3) # Pequena pausa entre embeds
                except Exception as e: logger.error(f"Erro enviar embed dividido: {e}", exc_info=True); return # Para se houver erro no envio
                # Prepara o próximo embed (cópia do base, sem campos)
                current_embed = base_embed.copy(); current_embed.clear_fields(); fields_in_current_embed = 0; temp_field_list = []
        else: # Se cabe, adiciona ao campo atual
            current_field_value += item_line

    # Adiciona o último campo restante (se houver) à lista temporária
    if current_field_value:
         part_num = (total_embeds_sent * max_items_per_embed) + len(temp_field_list) + 1
         field_title = f"{field_name} (Parte {part_num})" if len(items_list) > max_items_per_embed else field_name
         temp_field_list.append({"name": field_title, "value": current_field_value, "inline": False})

    # Adiciona os campos temporários restantes ao embed atual
    for field_data in temp_field_list:
         if len(current_embed.fields) < max_items_per_embed: current_embed.add_field(**field_data)
         else: logger.warning("Limite campos atingido no final send_embeds_splitted."); break

    # Envia o último embed se ele tiver campos
    if len(current_embed.fields) > 0:
         try:
             logger.debug(f"Enviando último embed ({total_embeds_sent + 1}) #{getattr(channel, 'name', '?')}")
             await channel.send(embed=current_embed)
         except Exception as e: logger.error(f"Erro enviar último embed: {e}", exc_info=True)

async def get_player_name(tag):
    global coc_client; fallback_name = f"Jogador ({tag[-4:]})" if tag else "Jogador (?)"
    if not coc_client or not tag: return fallback_name
    if not coc.utils.is_valid_tag(tag): return fallback_name
    try: player = await asyncio.wait_for(coc_client.get_player(tag), timeout=15.0); return getattr(player, 'name', fallback_name)
    except (coc_errors.NotFound, coc_errors.Maintenance, asyncio.TimeoutError, coc_errors.InvalidTag): return fallback_name
    except Exception as e: logger.error(f"Erro get_player_name {tag}: {e}", exc_info=False); return fallback_name

# --- Tarefas de Monitoramento ---
@tasks.loop(minutes=5)
async def check_donations():
    try:
        global donation_cache, coc_client
        if not coc_client: return
        clan = await get_clan_data(timeout=45)
        if not clan or not hasattr(clan, 'members') or not clan.members: return
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            try: logger.debug(f"[Task Dono] Canal {CHANNEL_ID} cache miss, fetch..."); channel = await bot.fetch_channel(CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden): logger.error(f"[Task Dono] Canal ID {CHANNEL_ID} inacessível."); return
            except Exception as e: logger.error(f"[Task Dono] Erro fetch canal {CHANNEL_ID}: {e}"); return
        dono_upd = []; rec_upd = []; curr_time = datetime.now(TIMEZONE); cache = donation_cache.copy(); state = {}; initial = not cache
        for m in clan.members:
            tag = m.tag
            name = m.name
            if not tag: logger.warning(f"Membro {name} clã {clan.name} sem tag. Pulando."); continue
            d = m.donations
            r = m.received
            data = {'name': name, 'donations': d, 'received': r}
            state[tag] = data
            if not initial and tag in cache:
                old = cache[tag]
                d_diff = data['donations'] - old.get('donations', 0)
                r_diff = data['received'] - old.get('received', 0)
                if d_diff > 0: dono_upd.append(f"{emojis['donation']}`{name}`+**{d_diff}** ({data['donations']:,})")
                if r_diff > 0: rec_upd.append(f"{emojis['received']}`{name}`+**{r_diff}** ({data['received']:,})")
        donation_cache = state
        if (dono_upd or rec_upd) and not initial:
            logger.info(f"[Task Dono] {len(dono_upd)} doações, {len(rec_upd)} recebidos.")
            base = discord.Embed(title=f"{emojis['donation']} Doações/Recebidos", color=discord.Color.blue(), timestamp=curr_time).set_footer(text=f"Clã: {clan.name}")
            if channel: # Verifica canal
                await send_embeds_splitted(channel, base, "Atualizações", dono_upd + rec_upd, max_items_per_embed=15)
        elif initial and state: logger.info("[Task Dono] Cache init.")
        else: logger.debug("[Task Dono] Sem novas doações.")
    except Exception as e: logger.error(f"Erro GERAL task check_donations: {e}", exc_info=True)

@tasks.loop(minutes=10)
async def check_members():
    try:
        global member_cache, coc_client
        if not coc_client: return
        clan = await get_clan_data(timeout=45)
        if not clan or not hasattr(clan, 'members'): return
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            try: logger.debug(f"[Task Memb] Canal {CHANNEL_ID} cache miss, fetch..."); channel = await bot.fetch_channel(CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden): logger.error(f"[Task Memb] Canal ID {CHANNEL_ID} inacessível."); return
            except Exception as e: logger.error(f"[Task Memb] Erro fetch canal {CHANNEL_ID}: {e}"); return
        curr_list = clan.members or []; curr_dict = {m.tag: m.name for m in curr_list if m.tag}; curr_time = datetime.now(TIMEZONE); footer = f"Clã: {clan.name}"
        if not member_cache['members'] and member_cache['count'] == 0:
            logger.info("[Task Memb] Cache init..."); member_cache['members'] = curr_dict; member_cache['count'] = len(curr_dict); logger.info(f"[Task Memb] Cache: {member_cache['count']} membros.");
            init_emb = discord.Embed(title=f"{emojis['info']} Monitoramento Membros ON", description=f"Clã **{clan.name}**\nMembros: **{member_cache['count']}**", color=0xAAAAAA, timestamp=curr_time).set_footer(text=footer)
            if channel: # Verifica canal
                try: await channel.send(embed=init_emb)
                except Exception as e: logger.error(f"[Task Memb] Erro embed inicial: {e}")
            return
        old_set = set(member_cache['members'].keys()); curr_set = set(curr_dict.keys()); left = old_set - curr_set; joined = curr_set - old_set; tasks = []; logs = []
        if left:
            logger.info(f"[Task Memb] {len(left)} saídas.");
            for tag in left:
                 name = member_cache['members'].get(tag, f"M({tag[-4:]})"); logs.append(f"Saiu:{name}({tag})");
                 emb = discord.Embed(title=f"{emojis['leave']} Saída", description=f"**{name}** saiu.", color=discord.Color.red(), timestamp=curr_time).set_footer(text=footer);
                 if channel: tasks.append(channel.send(embed=emb)) # Verifica se canal existe
        if joined:
            logger.info(f"[Task Memb] {len(joined)} entradas.");
            for tag in joined:
                name = curr_dict.get(tag, f"M({tag[-4:]})"); logs.append(f"Entrou:{name}({tag})");
                m_det = next((m for m in curr_list if m.tag == tag), None); details = ""; l_icon = None
                if m_det: th=m_det.town_hall; lvl=m_det.exp_level; tr=m_det.trophies; lg_ic=getattr(m_det.league,'icon',None); l_icon=lg_ic.url if lg_ic else None; details=f"CV{th}|Lvl{lvl}|{tr}{emojis['trophy']}"
                emb = discord.Embed(title=f"{emojis['join']} Entrada", description=f"**{name}** entrou!", color=discord.Color.green(), timestamp=curr_time);
                if l_icon: emb.set_thumbnail(url=l_icon);
                if details: emb.add_field(name="Detalhes", value=details, inline=False);
                emb.set_footer(text=footer);
                if channel: tasks.append(channel.send(embed=emb)) # Verifica se canal existe
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True); errors = sum(1 for r in results if isinstance(r, Exception));
            if errors > 0: logger.error(f"[Task Memb] {errors} erros ao enviar embeds de entrada/saída.")
            if logs: logger.info(f"[Task Memb] Detalhes: {', '.join(logs)}")
            member_cache['members'] = curr_dict; new_count = len(curr_dict); member_cache['count'] = new_count
            if (left or joined) and errors == 0 and channel: # Verifica se canal existe
                 cnt_emb = discord.Embed(description=f"Membros: **{new_count}/50**", color=0xAAAAAA);
                 try: await channel.send(embed=cnt_emb, delete_after=60)
                 except Exception as e: logger.error(f"[Task Memb] Erro embed contagem: {e}")
        else: logger.debug("[Task Memb] Sem alterações.")
    except Exception as e: logger.error(f"Erro GERAL task check_members: {e}", exc_info=True)

async def check_war_attacks_and_report(war, war_type="Guerra Normal"):
    try:
        global war_cache, coc_client, bot, CHANNEL_ID, CLAN_TAG, TIMEZONE, emojis
        if not coc_client: return
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            try: logger.debug(f"[Task WarAtk] Canal {CHANNEL_ID} cache miss, fetch..."); channel = await bot.fetch_channel(CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden): logger.error(f"[Task WarAtk] ({war_type}) Canal ID {CHANNEL_ID} inacessível."); return
            except Exception as e: logger.error(f"[Task WarAtk] ({war_type}) Erro fetch canal {CHANNEL_ID}: {e}"); return
        our_c = war.clan if hasattr(war, 'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'opponent', None)
        en_c = war.opponent if hasattr(war, 'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'clan', None)
        if not our_c or not en_c: logger.error(f"[Task WarAtk] Erro ID clãs {war_type} ({getattr(war, 'tag', 'TAG Desconhecida')})"); return # Log Tag se possível
        op_name = en_c.name; prep_time = war.preparation_start_time.time if war.preparation_start_time else datetime.now();
        # Usa getattr para war.tag
        war_tag_part = getattr(war, 'tag', None) or f"{our_c.tag}-{op_name}-{prep_time.isoformat()}"
        war_id = f"{'league-' if war.is_cwl else 'war-'}{war_tag_part}"
        if war_id not in war_cache: war_cache[war_id] = {'attacks': {}, 'time_alerts': set(), 'state': war.state}
        war_data = war_cache[war_id]; curr_time = datetime.now(TIMEZONE); curr_state = war.state
        if curr_state != war_data.get('state'): logger.info(f"[Task WarAtk] {war_type} ID:{war_id[-25:]} | Estado: {war_data.get('state')}->{curr_state}"); war_data['state'] = curr_state
        logger.debug(f"[Task WarAtk] Verificando {war_type} ID:{war_id[-25:]} | Estado:{curr_state}")
        if curr_state == 'inWar':
            members = our_c.members; send_tasks = []; new_atks_cycle = False
            for m in members:
                tag = m.tag
                name = m.name
                th = m.town_hall
                if not tag: logger.warning(f"Membro {name} guerra {war_type} sem tag. Pulando."); continue
                m_atks = m.attacks
                curr_atk_c = len(m_atks)
                prev_atk_c = war_data.get('attacks', {}).get(tag, 0)
                if curr_atk_c > prev_atk_c:
                    new_atks_cycle = True; new_list = m_atks[prev_atk_c:]; logger.info(f"[Task WarAtk] {war_type} ID {war_id[-25:]}: {name} +{len(new_list)} atk(s).")
                    for att in new_list:
                        if not all(hasattr(att, a) for a in ['defender_tag', 'stars', 'destruction']): logger.warning(" Atk dados faltando."); continue
                        def_tag = att.defender_tag; stars = att.stars; destr = round(att.destruction, 1); stars_emo = ("⭐"*stars)+("⚫"*(3-stars))
                        defender_name, defender_th = "?", "?";
                        try:
                            defender_player_obj = await asyncio.wait_for(coc_client.get_player(def_tag), timeout=10.0)
                            defender_name = getattr(defender_player_obj, 'name', f'Defensor({def_tag[-4:]})')
                            defender_th = getattr(defender_player_obj, 'town_hall', '?')
                        except coc_errors.NotFound: defender_name = f"Defensor NF ({def_tag[-4:]})"; logger.warning(f"[Task WarAtk] Defensor {def_tag} NotFound.")
                        except asyncio.TimeoutError: defender_name = f"Defensor TO ({def_tag[-4:]})"; logger.warning(f"[Task WarAtk] Timeout def {def_tag}.")
                        except coc_errors.Maintenance: defender_name = f"Defensor Maint. ({def_tag[-4:]})"; logger.warning(f"[Task WarAtk] API Maint. def {def_tag}.")
                        except Exception as e_def: defender_name = f"Defensor Err ({def_tag[-4:]})"; logger.error(f"[Task WarAtk] Erro def {def_tag}: {e_def}", exc_info=False)
                        atk_emb = discord.Embed(title=f"{emojis['war_attack']} Ataque {war_type}!", color=discord.Color.orange(), timestamp=curr_time)
                        atk_emb.add_field(name="Atacante", value=f"`{name}` (CV{th})", inline=True); atk_emb.add_field(name="Defensor", value=f"`{defender_name}` (CV{defender_th})", inline=True); atk_emb.add_field(name="Resultado", value=f"**{stars}** {stars_emo} **{destr}%** {emojis['destruction']}", inline=False); atk_emb.set_footer(text=f"Guerra vs {op_name}")
                        if channel: send_tasks.append(channel.send(embed=atk_emb)) # Verifica canal
                    war_data['attacks'][tag] = curr_atk_c
            if send_tasks:
                 logger.info(f"[Task WarAtk] Enviando {len(send_tasks)} embeds atk...");
                 results = await asyncio.gather(*send_tasks, return_exceptions=True)
                 errors = sum(1 for r in results if isinstance(r, Exception))
                 if errors > 0: logger.error(f"[Task WarAtk] {errors} erros ao enviar embeds de ataque.")
            if not new_atks_cycle: logger.debug(f"[Task WarAtk] {war_type} {war_id[-25:]}: Sem novos atks.")
            end_time = war.end_time
            if end_time and hasattr(end_time, 'time'):
                # Correção: Usar timezones consistentes para comparação
                now_utc = datetime.now(pytz.utc)
                end_time_utc = end_time.time.astimezone(pytz.utc)
                t_left = end_time_utc - now_utc
                h_left = t_left.total_seconds() / 3600 if t_left.total_seconds() > 0 else 0
                a_hours = [12, 6, 3, 1]
                if 'time_alerts' not in war_data: war_data['time_alerts'] = set()
                for h in a_hours:
                    if h not in war_data['time_alerts'] and 0 < h_left <= h:
                        war_data['time_alerts'].add(h); logger.info(f"[Task WarAtk] Alerta {h}h {war_type} ID: {war_id[-25:]}")
                        missing = []; per = war.attacks_per_member
                        for m in members:
                            if len(m.attacks) < per: missing.append(f"`{m.name}`: **{per - len(m.attacks)}** atk(s)")
                        if missing and channel:
                            end_timestamp_int = int(end_time_utc.timestamp())
                            a_emb = discord.Embed(
                                title=f"{emojis['time']} ALERTA: Restam {h}h {war_type}!",
                                description=f"vs **{op_name}**, fim <t:{end_timestamp_int}:R>.",
                                color=discord.Color.orange(),
                                timestamp=end_time_utc # Usar timestamp consistente
                            )
                            await send_embeds_splitted(channel, a_emb, "Ataques Pendentes", missing, max_items_per_embed=15)
                        elif not missing: logger.info(f" [Task WarAtk] Alerta {h}h - Todos atacaram.")
                        break # Sai do loop após encontrar e processar o primeiro alerta aplicável
        rep_key = 'war_end_reported' if not war.is_cwl else 'league_war_end_reported'
        if rep_key not in war_cache: war_cache[rep_key] = {}
        if curr_state == 'warEnded' and war_id not in war_cache.get(rep_key, {}):
            war_cache[rep_key][war_id] = True; logger.info(f"[Task WarAtk] {war_type} ID:{war_id[-25:]} FIM. Relatório.")
            try:
                os_val=our_c.stars; es_val=en_c.stars; od_val=round(our_c.destruction,2); ed_val=round(en_c.destruction,2); on_val=our_c.name; en_val=en_c.name
                res, emo, col = ("EMPATE", emojis['war_tie'], 0xFFD700) if os_val==es_val and od_val==ed_val else (("VITÓRIA", emojis['war_win'], 0x00FF00) if os_val>es_val or (os_val==es_val and od_val>ed_val) else ("DERROTA", emojis['war_lose'], 0xFF0000))
                end_emb=discord.Embed(title=f"{emo} {war_type.upper()} FIM: {res}! {emo}", description=f"vs **{en_val}**", color=col)
                end_emb.add_field(name=f"{emojis['clan_capital']} {on_val}", value=f"**{os_val}**⭐({od_val}%)", inline=True); end_emb.add_field(name=f"{emojis['war_attack']} {en_val}", value=f"**{es_val}**⭐({ed_val}%)", inline=True)
                if war.end_time and hasattr(war.end_time, 'time'): end_emb.timestamp = war.end_time.time.astimezone(TIMEZONE)
                if channel: await channel.send(embed=end_emb); await asyncio.sleep(0.5) # Verifica canal
                missed = []; per = war.attacks_per_member
                for m in getattr(our_c,'members',[]):
                    if len(m.attacks) < per: missed.append(f"`{m.name}`(CV{m.town_hall}): **{per - len(m.attacks)}** perdido(s)")
                if missed and channel: # Verifica canal
                    miss_emb = discord.Embed(title=f"{emojis['missed_attack']} Ataques Ñ Realizados", description=f"vs **{en_val}**:", color=0xFF0000);
                    if war.end_time and hasattr(war.end_time, 'time'): miss_emb.timestamp = war.end_time.time.astimezone(TIMEZONE);
                    await send_embeds_splitted(channel, miss_emb, "Membros", missed, max_items_per_embed=15)
                elif not missed and channel: # Verifica canal
                    all_atk_emb = discord.Embed(title=f"{emojis['success']} Ataques Completos!", description=f"Todos atacaram vs **{en_val}**!", color=0x00FF00);
                    if war.end_time and hasattr(war.end_time, 'time'): all_atk_emb.timestamp = war.end_time.time.astimezone(TIMEZONE);
                    await channel.send(embed=all_atk_emb)
                logger.info(f"[Task WarAtk] Relatório final {war_type} ID:{war_id[-25:]} enviado.")
            except Exception as e: logger.error(f"[Task WarAtk] Erro relatório final {war_type} ID {war_id[-25:]}: {e}", exc_info=True)
    except Exception as e: logger.error(f"Erro GERAL check_war_attacks ({war_type}): {e}", exc_info=True)

@tasks.loop(minutes=15)
async def check_war():
    try:
        global coc_client, war_cache
        if not coc_client: return
        #logger.debug("[Task War] Verificando guerra normal...") # Log menos verboso
        war = await asyncio.wait_for(coc_client.get_current_war(CLAN_TAG, war_tag="#0"), timeout=60.0)
        if not war or war.state=='notInWar' or war.is_cwl:
            #logger.info("[Task War] Nenhuma guerra normal ativa ou clã está em CWL.") # Log desnecessário a cada 15min
            return
        our_c = war.clan if hasattr(war, 'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'opponent', None) # Safety checks
        en_c = war.opponent if hasattr(war, 'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'clan', None)
        if not our_c or not en_c:
             logger.error(f"[Task War] Erro ao identificar clãs na guerra {getattr(war, 'tag', 'TAG Desconhecida')}") # Log Tag se possível
             return
        op_name = en_c.name
        prep_time = war.preparation_start_time.time if war.preparation_start_time else datetime.now()

        # --- CORREÇÃO APLICADA AQUI (Erro 1) ---
        war_tag_part = getattr(war, 'tag', None) or f"{our_c.tag}-{op_name}-{prep_time.isoformat()}"
        # --- FIM DA CORREÇÃO ---

        war_id = f"war-{war_tag_part}"

        if war.state=='preparation':
            if war_id not in war_cache: war_cache[war_id] = {'attacks':{}, 'time_alerts':set(), 'state':'unknown'}
            if war_cache.get(war_id,{}).get('state') != 'preparation':
                logger.info(f"[Task War] Nova Guerra prep. ID: {war_id[-25:]}"); war_cache[war_id]['state']='preparation'
                size=war.team_size; st_obj = war.start_time; st_ts = int(st_obj.time.timestamp()) if st_obj and hasattr(st_obj, 'time') else None
                prep_emb=discord.Embed(title=f"{emojis['war_attack']} Preparação Guerra!", description=f"**`{our_c.name}`** vs **`{op_name}`** ({size}v{size})", color=discord.Color.blue())
                if st_ts: prep_emb.add_field(name="Início Batalha", value=f"<t:{st_ts}:R> (<t:{st_ts}:F>)", inline=False)
                if st_obj and hasattr(st_obj, 'time'): prep_emb.timestamp = st_obj.time.astimezone(TIMEZONE)
                channel = bot.get_channel(CHANNEL_ID)
                if not channel:
                    try: logger.debug(f"[Task War] Canal {CHANNEL_ID} cache miss, fetch..."); channel = await bot.fetch_channel(CHANNEL_ID)
                    except (discord.NotFound, discord.Forbidden): logger.error(f"[Task War] Canal ID {CHANNEL_ID} inacessível p/ anúncio prep."); return
                    except Exception as e: logger.error(f"[Task War] Erro fetch canal {CHANNEL_ID} p/ anúncio prep: {e}"); return
                if channel: # Verifica se canal existe
                    try: await channel.send(embed=prep_emb); logger.info(f"[Task War] Anúncio prep ID:{war_id[-25:]} enviado.")
                    except Exception as e: logger.error(f"[Task War] Erro send anúncio prep: {e}", exc_info=True)
            else: logger.debug(f"[Task War] Guerra {war_id[-25:]} já em prep cache.")
            return # Retorna se estiver em preparação

        # Se não estiver em preparação, verifica ataques
        await check_war_attacks_and_report(war, war_type="Guerra Normal")

    except coc_errors.NotFound: logger.info("[Task War] Nenhuma guerra normal ativa (NotFound).")
    except coc_errors.PrivateWarLog: logger.info("[Task War] Log de Guerra Privado.")
    except coc_errors.Maintenance: logger.warning("[Task War] API CoC em manutenção.")
    except asyncio.TimeoutError: logger.error("[Task War] Timeout ao buscar guerra atual.")
    except Exception as e: logger.error(f"[Task War] Erro GERAL: {e}", exc_info=True)

@tasks.loop(minutes=20)
async def check_league_war():
    try:
        global coc_client, war_cache
        if not coc_client: return
        #logger.debug("[Task CWL] Verificando grupo liga...") # Log menos verboso
        lg = await asyncio.wait_for(coc_client.get_league_group(CLAN_TAG), timeout=90.0)
        if not lg or lg.state=="notInWar":
            if war_cache.get('league_start_announced',False): logger.info("[Task CWL] Grupo Liga inativo. Reset flag."); war_cache['league_start_announced']=False
            #logger.debug("[Task CWL] Não em CWL."); # Log desnecessário a cada 20min
            return
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            try: logger.debug(f"[Task CWL] Canal {CHANNEL_ID} cache miss, fetch..."); channel = await bot.fetch_channel(CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden): logger.error(f"[Task CWL] Canal ID {CHANNEL_ID} inacessível."); return
            except Exception as e: logger.error(f"[Task CWL] Erro fetch canal {CHANNEL_ID}: {e}"); return
        if not war_cache.get('league_start_announced',False) and channel: # Verifica canal
            war_cache['league_start_announced']=True; clans=lg.clans; names=[f"- `{c.name}` (Lvl {c.level})" for c in clans]; season=lg.season; lg_name=lg.league.name; curr_time=datetime.now(TIMEZONE)
            lg_emb=discord.Embed(title=f"{emojis['league']} CWL Iniciada: {lg_name}! {emojis['league']}", description=f"Temporada: **{season}**", color=discord.Color.purple(), timestamp=curr_time)
            await send_embeds_splitted(channel, lg_emb, "Clãs no Grupo", names, max_items_per_embed=10)
            logger.info(f"[Task CWL] Anúncio Liga {season} ({lg_name}) enviado.")
        all_wars = [];
        try: #logger.debug("[Task CWL] Buscando guerras..."); # Log menos verboso
             all_wars = await asyncio.wait_for(lg.get_wars(CLAN_TAG), timeout=90.0)
        except coc_errors.NotFound: logger.info(f"[Task CWL] Nenhuma guerra para {CLAN_TAG} no grupo.")
        except asyncio.TimeoutError: logger.error("[Task CWL] Timeout ao buscar guerras da liga.")
        except Exception as e: logger.error(f"[Task CWL] Erro get_wars: {e}", exc_info=True)

        curr_round = None; ended_unrep = []
        for war in all_wars:
            if not war or not all(hasattr(war,a) for a in ['state','preparation_start_time','clan','opponent']): continue
            try:
                 our_c = war.clan if hasattr(war, 'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'opponent', None)
                 en_c = war.opponent if hasattr(war, 'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'clan', None)
                 if not our_c or not en_c: logger.warning(f"[Task CWL] Não identificou clãs G. Liga {getattr(war, 'tag', '?')}. Pulando."); continue
                 prep_time_obj = getattr(war,'preparation_start_time', None)
                 prep_time = prep_time_obj.time if prep_time_obj and hasattr(prep_time_obj, 'time') else datetime.now()
                 # Usa getattr para war.tag
                 war_tag_part = getattr(war, 'tag', None) or f"{getattr(our_c,'tag','?')}-{getattr(en_c,'name','?')}-{prep_time.isoformat()}"
                 war_id = f"league-{war_tag_part}"
                 report_key = 'league_war_end_reported'
                 if report_key not in war_cache: war_cache[report_key] = {} # Garante que a chave existe
            except Exception as e: logger.error(f"[Task CWL] Erro processar dados básicos G. Liga ({getattr(war, 'tag', '?')}): {e}", exc_info=True); continue

            if war.state in ['inWar', 'preparation']:
                curr_round = war; break # Encontrou a rodada atual, sai do loop
            elif war.state == 'warEnded' and war_id not in war_cache.get(report_key, {}):
                ended_unrep.append(war) # Adiciona à lista de finalizadas não reportadas

        if curr_round:
            war = curr_round # Renomeia para 'war' para consistência
            try:
                our_c = war.clan if hasattr(war, 'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'opponent', None)
                en_c = war.opponent if hasattr(war, 'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'clan', None)
                if not our_c or not en_c: raise ValueError("Clãs G. Liga inválidos na guerra atual")
                opponent_name_cache = getattr(en_c, 'name', '?')
                prep_time_obj = getattr(war, 'preparation_start_time', None)
                prep_time = prep_time_obj.time if prep_time_obj and hasattr(prep_time_obj, 'time') else datetime.now()
                # Usa getattr para war.tag
                war_tag_part = getattr(war, 'tag', None) or f"{getattr(our_c,'tag','?')}-{opponent_name_cache}-{prep_time.isoformat()}"
                war_id = f"league-{war_tag_part}"
            except Exception as e_id_curr:
                logger.error(f"[Task CWL] Erro ao processar dados/ID da G. Liga atual ({getattr(war, 'tag', '?')}): {e_id_curr}", exc_info=True)
                return # Retorna se não conseguir processar a guerra atual

            if war.state=='preparation':
                 if war_id not in war_cache: war_cache[war_id]={'attacks':{},'time_alerts':set(),'state':'unknown'}
                 if war_cache.get(war_id,{}).get('state')!='preparation':
                     logger.info(f"[Task CWL] Nova G. Liga prep. ID: {war_id}"); war_cache[war_id]['state']='preparation'
                     st_obj=war.start_time; st_ts=int(st_obj.time.timestamp()) if st_obj and hasattr(st_obj, 'time') else None; round_n=str(sum(1 for w in all_wars if w.state == 'warEnded') + 1) if all_wars else "?"
                     prep_emb=discord.Embed(title=f"{emojis['league']} Preparação CWL (R{round_n})", description=f"**`{our_c.name}`** vs **`{opponent_name_cache}`**", color=discord.Color.blue())
                     if st_ts: prep_emb.add_field(name="Início Batalha", value=f"<t:{st_ts}:R> (<t:{st_ts}:F>)", inline=False)
                     if st_obj and hasattr(st_obj, 'time'): prep_emb.timestamp = st_obj.time.astimezone(TIMEZONE)
                     if channel: # Verifica canal
                         try: await channel.send(embed=prep_emb); logger.info(f"[Task CWL] Anúncio prep Liga ID:{war_id} (R{round_n}) enviado.")
                         except Exception as e: logger.error(f"[Task CWL] Erro send anúncio prep Liga: {e}", exc_info=True)
                 else: logger.debug(f"[Task CWL] G. Liga {war_id} já em prep cache.")
            elif war.state == 'inWar': logger.debug(f"[Task CWL] Check ataques Liga ID:{war_id}"); await check_war_attacks_and_report(war, war_type="Guerra de Liga")
        elif ended_unrep:
             logger.info(f"[Task CWL] Processando {len(ended_unrep)} finalizada(s) ñ reportada(s).")
             for war in ended_unrep: logger.debug(f"[Task CWL] Reportando G. Liga finalizada ID: league-{getattr(war, 'tag', '?')}"); await check_war_attacks_and_report(war, war_type="Guerra de Liga") # Usa getattr
        else: logger.info("[Task CWL] Nenhuma G. Liga ativa/prep ou pendente.")
    except coc_errors.NotFound:
         if war_cache.get('league_start_announced',False): logger.info("[Task CWL] Grupo liga NotFound. Reset flag."); war_cache['league_start_announced']=False
         logger.info("[Task CWL] Não em Grupo CWL (NotFound).")
    except coc_errors.Maintenance: logger.warning("[Task CWL] API CoC em manutenção.")
    except asyncio.TimeoutError: logger.error("[Task CWL] Timeout ao buscar grupo da liga.")
    except Exception as e: logger.error(f"[Task CWL] Erro GERAL: {e}",exc_info=True); war_cache['league_start_announced']=False # Reset flag em caso de erro geral

@tasks.loop(hours=1)
async def check_raid_weekend():
    try:
        global raid_weekend_cache, coc_client
        if not coc_client: return
        #logger.debug("[Task Raid] Verificando Raid...") # Log menos verboso
        rl = await asyncio.wait_for(coc_client.get_clan_capital_raid_seasons(CLAN_TAG, limit=1), timeout=60.0)
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            try: logger.debug(f"[Task Raid] Canal {CHANNEL_ID} cache miss, fetch..."); channel = await bot.fetch_channel(CHANNEL_ID)
            except (discord.NotFound, discord.Forbidden): logger.error(f"[Task Raid] Canal ID {CHANNEL_ID} inacessível."); return
            except Exception as e: logger.error(f"[Task Raid] Erro fetch canal {CHANNEL_ID}: {e}"); return
        curr_time = datetime.now(TIMEZONE);
        try: # Tenta obter nome do clã, mas continua se falhar
            clan_data = await get_clan_data(timeout=15)
            clan_name = getattr(clan_data, 'name', CLAN_TAG) if clan_data else CLAN_TAG
        except Exception as e_clan:
            logger.warning(f"[Task Raid] Não foi possível obter nome do clã: {e_clan}")
            clan_name = CLAN_TAG

        async def send_raid_report(data, emoji, title, color, type="final"): # Interna
            st_str = data.get('start_time_str', 'N/A'); loot = data.get('total_loot', 0); state = data.get('state', 'N/A').capitalize(); attacks = data.get('total_attacks', '?'); dist_d = data.get('districts_destroyed', '?')
            r_time = data.get('end_time') or datetime.now(TIMEZONE)
            emb = discord.Embed(title=f"{emoji} {title} {emoji}", description=f"**Início:** {st_str}\n**Estado:** {state}", color=color, timestamp=r_time)
            emb.add_field(name=f"{emojis['clan_capital']} Ouro", value=f"**{loot:,}**", inline=True); emb.add_field(name=f"{emojis['war_attack']} Atks", value=f"{attacks}", inline=True); emb.add_field(name=f"{emojis['destruction']} Distr", value=f"{dist_d}", inline=True)
            members = data.get('members', {})
            top_contributors_list = [] # Lista para guardar os contribuidores formatados
            if members:
                m_map = {}
                try:
                    clan_for_map = await get_clan_data(timeout=15)
                    if clan_for_map: m_map = {m.tag: m.name for m in getattr(clan_for_map, 'members', []) if m.tag}
                except Exception as e_map:
                    logger.warning(f"[Task Raid] Erro ao obter mapa de membros para relatório: {e_map}")
                s_m = sorted(members.items(), key=lambda i: i[1].get('loot', 0), reverse=True);
                top_contributors_list = [f"{i}. `{m_map.get(t, d.get('name', '?'))}`: **{d.get('loot', 0):,}**" for i, (t, d) in enumerate(s_m, 1)]

            emb.set_footer(text=f"Clã: {clan_name}")
            if channel: # Verifica canal
                 try: await channel.send(embed=emb)
                 except Exception as e: logger.error(f"[Task Raid] Erro send embed relatório {type}: {e}")
                 # Envia a lista de contribuidores separadamente se existir
                 if top_contributors_list:
                     field_title = f"🌟 Top Contribs ({type.capitalize()}) 🌟"
                     top_emb = discord.Embed(title=field_title, color=color) # Cria novo embed para a lista
                     await send_embeds_splitted(channel, top_emb, "Ranking", top_contributors_list, max_items_per_embed=15)
                     await asyncio.sleep(0.3) # Pausa após enviar a lista
            else:
                logger.warning("[Task Raid] Canal inválido para enviar relatório de raid.")

        if not rl: # API vazia
             cached = raid_weekend_cache.get('current_raid')
             if cached and cached.get('state') in ['ongoing', 'ended_due_to_api_error']:
                  if cached.get('state') != 'ended_due_to_api_error':
                       logger.warning("[Task Raid] API vazia, marcando raid como erro."); raid_weekend_cache['current_raid']['state'] = 'ended_due_to_api_error'
                       err_emb = discord.Embed(title=f"{emojis['error']} Erro Dados Raid", description="API não retornou dados da raid.", color=0xFF0000, timestamp=curr_time)
                       if channel: # Verifica canal
                            try: await channel.send(embed=err_emb)
                            except Exception as e: logger.error(f"[Task Raid] Erro enviar embed erro API vazia: {e}")
             else: logger.info("[Task Raid] Sem dados Raid API.")
             return

        curr_r = rl[0]
        if not curr_r or not all(hasattr(curr_r,a) for a in ['start_time','state','capital_total_loot','total_attacks','districts_destroyed']): logger.error(f"[Task Raid] Objeto Raid API inválido: {curr_r}"); return
        st_obj = curr_r.start_time;
        # Verifica se start_time tem o atributo 'time' antes de usar
        if not st_obj or not hasattr(st_obj, 'time'): logger.error("[Task Raid] Objeto Raid sem start_time válido."); return
        r_iso = st_obj.time.isoformat(); r_id = f"{CLAN_TAG}-{r_iso}"
        cached = raid_weekend_cache.get('current_raid'); prev_id = cached['id'] if cached else None; prev_state = cached['state'] if cached else None

        if r_id != prev_id: # Nova Raid
            logger.info(f"[Task Raid] Nova Raid ID: {r_id}. Anterior: {prev_id}")
            if prev_id and prev_state in ['ongoing','ended_due_to_api_error']:
                logger.info(f"[Task Raid] Raid anterior '{prev_state}'. Report presumido.");
                cached['state']='ended(presumed)';
                cached['end_time']=curr_time;
                await send_raid_report(cached,emojis['warning'],"RAID ANTERIOR FIM (Presumido)",0x808080,"presumido") # Envia relatório da anterior

            st_aware = st_obj.time.astimezone(TIMEZONE); st_str = st_aware.strftime('%d/%m %H:%M'); end_obj = curr_r.end_time; end_aware = end_obj.time.astimezone(TIMEZONE) if end_obj and hasattr(end_obj, 'time') else None
            m_dict = {m.tag:{'name':m.name,'loot':m.capital_resources_looted} for m in getattr(curr_r,'members',[]) if m.tag}
            d_dict = {d.id:{'name':d.name,'destruction':d.destruction_percent} for d in getattr(curr_r,'attack_log',[]) if hasattr(d,'id')} # Usa attack_log para distritos, mais preciso
            raid_weekend_cache['current_raid'] = {'id': r_id, 'start_time': st_aware, 'start_time_str': st_str, 'end_time': end_aware, 'state': curr_r.state, 'members': m_dict, 'districts': d_dict, 'total_loot': curr_r.capital_total_loot, 'total_attacks': curr_r.total_attacks, 'districts_destroyed': curr_r.districts_destroyed}
            logger.info(f"[Task Raid] Cache raid ID:{r_id} init. Estado:{curr_r.state}")

            if curr_r.state == 'ongoing' and channel: # Verifica canal
                end_ts = int(end_aware.timestamp()) if end_aware else None
                start_emb = discord.Embed(title=f"{emojis['raid']} Raid Iniciado! {emojis['raid']}", description="Ataquem Capital!", color=0xFF0000, timestamp=st_aware)
                start_emb.add_field(name="Início", value=st_str, inline=True);
                if end_ts: start_emb.add_field(name="Fim Prev.", value=f"<t:{end_ts}:R>", inline=True)
                start_emb.set_footer(text=f"Clã: {clan_name}")
                try: await channel.send(embed=start_emb); logger.info(f"[Task Raid] Anúncio início Raid ID:{r_id} enviado.")
                except Exception as e: logger.error(f"[Task Raid] Erro send anúncio início: {e}")

        elif r_id == prev_id: # Mesma Raid
            logger.debug(f"[Task Raid] Mesmo ID:{r_id}. API:{curr_r.state}, Cache:{prev_state}")
            curr_data = raid_weekend_cache['current_raid']
            if prev_state != 'ended' and curr_r.state == 'ended': # Finalizou
                logger.info(f"[Task Raid] Raid {r_id} FIM (API 'ended'). Relatório.");
                end_obj_f = curr_r.end_time;
                curr_data['state']='ended';
                curr_data['end_time']=end_obj_f.time.astimezone(TIMEZONE) if end_obj_f and hasattr(end_obj_f, 'time') else curr_time;
                curr_data['total_loot']=curr_r.capital_total_loot; curr_data['total_attacks']=curr_r.total_attacks; curr_data['districts_destroyed']=curr_r.districts_destroyed;
                curr_data['members']={m.tag:{'name':m.name,'loot':m.capital_resources_looted} for m in getattr(curr_r,'members',[]) if m.tag}
                await send_raid_report(curr_data, emojis['clan_capital'], "RAID FINALIZADO!", 0x808080, "final"); logger.info(f"[Task Raid] Relatório final ID:{r_id} enviado.")
            elif prev_state == 'ended' and curr_r.state == 'ongoing': logger.warning(f"[Task Raid] Raid {r_id}: ended->ongoing."); curr_data['state']='ongoing';
            elif curr_r.state == 'ongoing': # Verifica progresso
                #logger.debug(f"[Task Raid] Raid {r_id} ongoing. Check progresso."); # Log menos verboso
                loot_ch=[]; dist_ch=[]; prog_found=False
                new_m_state={}; cache_m=curr_data.get('members',{});
                m_map = {}
                try:
                    clan_for_map = await get_clan_data(timeout=15)
                    if clan_for_map: m_map = {m.tag: m.name for m in getattr(clan_for_map, 'members', []) if m.tag}
                except Exception as e_map:
                    logger.warning(f"[Task Raid] Erro ao obter mapa de membros para progresso: {e_map}")

                for m in getattr(curr_r, 'members', []):
                    tag = getattr(m, 'tag', None)
                    if not tag: logger.warning(f"Membro {getattr(m, 'name', '?')} raid sem tag. Pulando."); continue
                    name = getattr(m, 'name', '?')
                    c_loot = getattr(m, 'capital_resources_looted', 0)
                    new_m_state[tag] = {'name': name, 'loot': c_loot}
                    p_loot = cache_m.get(tag, {'loot': 0})['loot']
                    diff = c_loot - p_loot
                    if diff > 0:
                        prog_found = True
                        disp_n = m_map.get(tag, name) # Usa nome do mapa se disponível
                        loot_ch.append(f"{emojis['raid']}`{disp_n}`+**{diff:,}** ({c_loot:,})")

                new_d_state={}; cache_d=curr_data.get('districts',{}); atk_log=getattr(curr_r,'attack_log',[])
                if atk_log:
                    for d_log in atk_log:
                        if not all(hasattr(d_log,a) for a in ['id','name','destruction_percent']): continue;
                        d_id=d_log.id; name=d_log.name; c_dest=d_log.destruction_percent; new_d_state[d_id]={'name':name,'destruction':c_dest};
                        p_dest=cache_d.get(d_id,{'destruction':0})['destruction'];
                        if c_dest==100 and p_dest<100: prog_found=True; dist_ch.append(f"{emojis['destruction']}**{name}** 100%!")
                else: new_d_state=cache_d # Mantém o cache antigo se não houver attack_log

                if prog_found and channel: # Verifica canal
                    logger.info(f"[Task Raid] Progresso {r_id}: {len(loot_ch)} loot, {len(dist_ch)} distritos.")
                    prog_emb = discord.Embed(title=f"{emojis['progress']} Progresso Raid", color=0x008080, timestamp=curr_time)
                    c_loot=curr_r.capital_total_loot; c_atks=curr_r.total_attacks; c_dist=curr_r.districts_destroyed
                    prog_emb.add_field(name="Status Atual", value=f"Ouro:**{c_loot:,}**|Atk:{c_atks}|Distr:{c_dist}", inline=False)
                    prog_emb.set_footer(text=f"Clã: {clan_name}")

                    # Envia embed de status antes das listas
                    try:
                        await channel.send(embed=prog_emb)
                        await asyncio.sleep(0.3)
                    except Exception as e: logger.error(f"[Task Raid] Erro send embed progresso (status): {e}")

                    # Envia listas separadas
                    if loot_ch:
                        loot_emb = discord.Embed(title=f"{emojis['clan_capital']} Ouro Obtido", color=0x008080)
                        await send_embeds_splitted(channel,loot_emb, "Jogadores", loot_ch, max_items_per_embed=15);
                        await asyncio.sleep(0.3) # Pausa
                    if dist_ch:
                        dist_emb = discord.Embed(title=f"{emojis['destruction']} Distritos Destruídos", color=0x008080)
                        # Usa send_embeds_splitted para o caso de muitos distritos cairem ao mesmo tempo
                        await send_embeds_splitted(channel, dist_emb, "Distritos", dist_ch, max_items_per_embed=20)
                        await asyncio.sleep(0.3) # Pausa

                    # Atualiza cache
                    curr_data['members']=new_m_state; curr_data['districts']=new_d_state; curr_data['total_loot']=c_loot; curr_data['total_attacks']=c_atks; curr_data['districts_destroyed']=c_dist
                elif prog_found and not channel:
                     logger.warning("[Task Raid] Progresso encontrado, mas canal inválido para enviar.")
                else: logger.debug(f"[Task Raid] Raid {r_id} ongoing, sem progresso.")
            else: logger.info(f"[Task Raid] Raid {r_id} API '{curr_r.state}' (cache '{prev_state}').")
            if prev_state == 'ended_due_to_api_error' and curr_r.state in ['ongoing','ended']: logger.info(f"[Task Raid] API Raid {r_id} voltou. Estado '{curr_r.state}'."); curr_data['state']=curr_r.state
    except coc_errors.Maintenance: logger.warning("[Task Raid] API CoC em manutenção.")
    except asyncio.TimeoutError: logger.error("[Task Raid] Timeout ao buscar dados da raid.")
    except Exception as e: logger.error(f"[Task Raid] Erro GERAL: {e}", exc_info=True);

# --- Evento Ready ---
@bot.event
async def on_ready():
    global coc_client
    logger.info(f'Bot {bot.user.name} ({bot.user.id}) pronto.')
    logger.info(f"discord.py: {discord.__version__} | coc.py: {coc.__version__}")
    logger.info(f"Monitorando Clã: {CLAN_TAG} | Canal ID: {CHANNEL_ID}")
    start_time = datetime.now(TIMEZONE)
    try: synced = await bot.tree.sync(); logger.info(f"Sincronizados {len(synced)} comandos barra.")
    except Exception as e: logger.error(f"Falha sincronizar comandos: {e}", exc_info=True)
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        try: logger.debug(f"[OnReady] Canal {CHANNEL_ID} cache miss, fetch..."); channel = await bot.fetch_channel(CHANNEL_ID)
        except (discord.NotFound, discord.Forbidden): logger.error(f"[OnReady] Canal ID {CHANNEL_ID} inacessível."); channel = None
        except Exception as e: logger.error(f"[OnReady] Erro fetch canal {CHANNEL_ID}: {e}"); channel = None
    logger.info("Inicializando cliente CoC...")
    login_ok = await initialize_coc_client() # Tenta inicializar o cliente CoC
    if not login_ok:
        logger.critical("Falha login CoC após tentativas.");
        if channel:
            err_emb = discord.Embed(title=f"{emojis['error']} Erro Crítico - API CoC", description="**Falha autenticação API.**\nMonitoramento/comandos CoC offline.", color=discord.Color.red(), timestamp=start_time)
            try: await channel.send(embed=err_emb)
            except Exception as e: logger.error(f"Erro enviar embed (falha login CoC): {e}")
        logger.warning("Bot rodando só com Discord (sem monitoramento CoC).")
    else: # Se login CoC OK
        logger.info("CoC OK. Verificando clã...")
        try:
            clan = await get_clan_data(timeout=60);
            if clan:
                logger.info(f"Acesso clã '{clan.name}' OK.")
                tasks=[check_donations, check_members, check_war, check_league_war, check_raid_weekend]; logs=[]; ok=True
                logger.info("Iniciando tasks...")
                for t in tasks:
                    name = t.coro.__name__
                    if not t.is_running():
                        try:
                            t.start()
                            logs.append(f"{name}: OK {emojis['success']}")
                            logger.debug(f"Task '{name}' iniciada.")
                        except RuntimeError as e_runtime: # Erro comum se a task já foi iniciada/parada rapidamente
                            if "Cannot run the event loop while another loop is running" in str(e_runtime):
                                logger.warning(f"Task '{name}' já parece estar rodando (RuntimeError).")
                                logs.append(f"{name}: Já ON? {emojis['warning']}")
                            else:
                                logger.error(f"Erro start {name}: {e_runtime}", exc_info=True)
                                logs.append(f"{name}: ERRO {emojis['error']}")
                                ok = False
                        except Exception as e:
                            logger.error(f"Erro start {name}: {e}", exc_info=True)
                            logs.append(f"{name}: ERRO {emojis['error']}")
                            ok = False
                    else:
                        logs.append(f"{name}: Já ON {emojis['warning']}")
                        logger.warning(f"Task '{name}' já estava rodando.")
                status= "\n".join(f"- {s}" for s in logs) if logs else "Nenhuma."; logger.info(f"Status tasks: {'; '.join(logs)}.")
                if channel:
                    on_emb=discord.Embed(title=f"{emojis['success']} Bot Online!", description=f"Clã: **{clan.name}** (`{CLAN_TAG}`)", color=discord.Color.green(), timestamp=start_time)
                    on_emb.add_field(name="Tarefas", value=status, inline=False);
                    if not ok: on_emb.add_field(name=f"{emojis['warning']} Atenção", value="Falha iniciar uma ou mais tarefas. Verifique os logs.", inline=False); on_emb.color=discord.Color.orange() # Mensagem mais informativa
                    on_emb.set_footer(text=f"Bot: {bot.user.name} | v15.0.11");
                    try: await channel.send(embed=on_emb)
                    except Exception as e: logger.error(f"Erro enviar embed (online): {e}")
            else:
                logger.critical(f"FALHA GRAVE: Clã {CLAN_TAG} inacessível pós-login OK.");
                if channel:
                    err_emb = discord.Embed(title=f"{emojis['error']} Erro Crítico - Acesso Clã", description=f"**Falha obter dados clã `{CLAN_TAG}`.**\nVerifique a TAG e as permissões da API Key.", color=discord.Color.red(), timestamp=start_time) # Dica adicional
                    try: await channel.send(embed=err_emb)
                    except Exception as e: logger.error(f"Erro enviar embed (falha obter clã): {e}")
        except Exception as e:
             logger.critical(f"FALHA GRAVE: Erro on_ready ao verificar clã/iniciar tasks: {e}", exc_info=True);
             if channel:
                 err_emb = discord.Embed(title=f"{emojis['error']} Erro Crítico - Init", description=f"**Erro inesperado durante inicialização:**\n`{e}`", color=discord.Color.red(), timestamp=start_time)
                 try: await channel.send(embed=err_emb)
                 except Exception as e2: logger.error(f"Erro enviar embed (erro API on_ready): {e2}")

# --- Tratador de Erros App Commands ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    error_embed = discord.Embed(color=discord.Color.red(), timestamp=datetime.now(TIMEZONE));
    cmd_name = interaction.command.name if interaction.command else 'N/A';
    error_embed.set_footer(text=f"Comando: /{cmd_name}");
    handled = False;
    original_error = error.original if isinstance(error, app_commands.CommandInvokeError) else error

    # Log mais detalhado para erros inesperados
    if not isinstance(original_error, (coc_errors.NotFound, coc_errors.Maintenance, asyncio.TimeoutError, coc_errors.AuthenticationError, coc_errors.InvalidTag, coc_errors.PrivateWarLog, app_commands.CheckFailure, app_commands.CommandOnCooldown, app_commands.MissingPermissions, app_commands.BotMissingPermissions)):
        logger.error(f"Erro não tratado em /{cmd_name}: {type(original_error).__name__} - {original_error}", exc_info=True)
    else:
        logger.warning(f"Erro esperado em /{cmd_name}: {type(original_error).__name__} - {original_error}")

    # Tratamento de erros específicos
    if isinstance(original_error, app_commands.CheckFailure):
        handled = True; error_embed.title = f"{emojis['error']} Acesso Negado"; error_embed.description = "Você não tem permissão para usar este comando ou outra verificação falhou."
    elif isinstance(original_error, app_commands.CommandOnCooldown):
        handled = True; error_embed.title = f"{emojis['time']} Cooldown"; error_embed.description = f"Aguarde `{original_error.retry_after:.1f}s` para usar este comando novamente."; error_embed.color = 0xFFA500
    elif isinstance(original_error, app_commands.MissingPermissions):
        handled = True; error_embed.title = f"{emojis['error']} Permissão Negada (Usuário)"; error_embed.description = f"Você precisa da permissão: `{', '.join(original_error.missing_permissions)}`."
    elif isinstance(original_error, app_commands.BotMissingPermissions):
        handled = True; error_embed.title = f"{emojis['error']} Permissão Negada (Bot)"; error_embed.description = f"Eu preciso da permissão: `{', '.join(original_error.missing_permissions)}` para executar este comando."
    elif isinstance(original_error, coc_errors.NotFound):
        handled = True; error_embed.title = f"{emojis['error']} Não Encontrado"; error_embed.description = "Recurso CoC (Clã, Jogador, Guerra) não encontrado. Verifique a TAG fornecida."
    elif isinstance(original_error, coc_errors.AuthenticationError):
        handled = True; error_embed.title = f"{emojis['error']} Erro Autenticação CoC"; error_embed.description = "Falha ao autenticar com a API do CoC. Verifique as credenciais (Email/Senha ou API Key)."; error_embed.color=0xCC0000
    elif isinstance(original_error, coc_errors.Maintenance):
        handled = True; error_embed.title = f"{emojis['warning']} Manutenção API CoC"; error_embed.description = "A API do Clash of Clans está em manutenção. Tente novamente mais tarde."; error_embed.color=0xFFA500
    elif isinstance(original_error, coc_errors.InvalidTag):
        handled = True; error_embed.title = f"{emojis['error']} TAG Inválida"; error_embed.description = "A TAG fornecida não é válida. Verifique o formato (ex: #ABCDEFGH)."
    elif isinstance(original_error, coc_errors.PrivateWarLog):
         handled=True; error_embed.title=f"{emojis['warning']}Log de Guerra Privado"; error_embed.description="O log de guerra deste clã é privado e não pode ser acessado."; error_embed.color=0xFFA500
    elif isinstance(original_error, coc_errors.ClashOfClansException): # Outros erros CoC
        handled = True; error_embed.title = f"{emojis['warning']} Erro API CoC"; error_embed.description = f"Ocorreu um erro na API do CoC: `{type(original_error).__name__}`."; error_embed.color=0xFFA500
    elif isinstance(original_error, asyncio.TimeoutError):
        handled = True; error_embed.title = f"{emojis['error']} Timeout"; error_embed.description = "A operação demorou muito para responder. Tente novamente."
    elif not coc_client and not isinstance(original_error, (coc_errors.AuthenticationError, coc_errors.Maintenance)): # Se CoC client não está pronto
        handled = True; error_embed.title = f"{emojis['error']} API CoC Offline"; error_embed.description = "A conexão com a API do CoC não está ativa no momento."; error_embed.color=0xFF8C00

    # Erro genérico se não foi tratado acima
    if not handled:
        error_embed.title = f"{emojis['error']} Erro Inesperado"
        error_embed.description = f"Ocorreu um erro inesperado ao executar o comando.\nTipo: `{type(original_error).__name__}`"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=error_embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    except discord.NotFound: logger.warning(f"Interação /{cmd_name} expirou antes de enviar erro.")
    except Exception as e_send: logger.error(f"Falha ao enviar mensagem de erro para /{cmd_name}: {e_send}", exc_info=True)


# --- Comandos de Barra ---
admin_group = app_commands.Group(name="admin", description="Comandos administrativos.", default_permissions=discord.Permissions(administrator=True))
war_group = app_commands.Group(name="guerra", description="Comandos de Guerras e CWL.") # Removido default_permissions para permitir uso geral
info_group = app_commands.Group(name="info", description="Comandos de informação.")

@admin_group.command(name="status", description="Exibe status atual do bot, clã, guerras e raids.")
@app_commands.checks.has_permissions(administrator=True) # Permissão verificada aqui
async def status_command(interaction: discord.Interaction):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        clan = await get_clan_data(timeout=45);
        if not clan: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Erro obter dados clã `{CLAN_TAG}`!", color=discord.Color.red())); return
        # --- LINHA 877 CORRIGIDA ---
        c_n=clan.name; c_t=clan.tag; c_desc=clan.description or "S/Desc"; c_lvl=clan.level; m_cnt=clan.member_count; m_max=50; loc=getattr(clan.location,'name',"Global"); c_pts=clan.points; c_pts_vs=getattr(clan, 'clan_versus_points', 0); w_lg=getattr(clan.war_league,'name',"Nenhuma"); cap_lg=getattr(clan.capital_league,'name',"Nenhuma"); b_url=getattr(clan.badge,'url',None)
        # --- FIM DA CORREÇÃO ---
        emb=discord.Embed(title=f"{emojis['info']} Status: {c_n} ({c_t})",description=f"_{c_desc}_",color=discord.Color.blue());
        if b_url: emb.set_thumbnail(url=b_url)
        emb.add_field(name="Nível",value=str(c_lvl),inline=True); emb.add_field(name="Membros",value=f"{m_cnt}/{m_max}",inline=True); emb.add_field(name="Local",value=loc,inline=True); emb.add_field(name="Troféus Vila",value=f"{c_pts:,}{emojis['trophy']}",inline=True); emb.add_field(name="Troféus Constr.",value=f"{c_pts_vs:,}{emojis['trophy']}",inline=True); emb.add_field(name="Liga Guerra",value=w_lg,inline=True); emb.add_field(name="Liga Capital",value=cap_lg,inline=True);
        ws = f"{emojis['warning']} Verificando..."
        try:
            war = await asyncio.wait_for(coc_client.get_current_war(CLAN_TAG, war_tag="#0"), timeout=45.0)
            if not war or war.state=='notInWar' or war.is_cwl: ws = f"{emojis['success']} Não em Guerra Normal."
            else:
                state=war.state; opp=war.opponent; our_w=war.clan; opp_n=opp.name; our_s=our_w.stars; opp_s=opp.stars; st_obj=war.start_time; et_obj=war.end_time; st_ts=int(st_obj.time.timestamp()) if st_obj and hasattr(st_obj,'time') else None; et_ts=int(et_obj.time.timestamp()) if et_obj and hasattr(et_obj,'time') else None
                if state=='preparation' and st_ts: ws=f"{emojis['time']} **Prep.** vs `{opp_n}` (<t:{st_ts}:R>)"
                elif state=='inWar' and et_ts: ws=f"{emojis['war_attack']} **Guerra** vs `{opp_n}` ({our_s}⭐/{opp_s}⭐) Fim: <t:{et_ts}:R>"
                elif state=='warEnded': our_d=round(our_w.destruction,1); opp_d=round(opp.destruction,1); emoji_r,rt=(emojis['war_win'],"Vitória") if our_s>opp_s or (our_s==opp_s and our_d>opp_d) else (emojis['war_lose'],"Derrota") if our_s<opp_s or (our_s==opp_s and our_d<opp_d) else (emojis['war_tie'],"Empate"); ws=f"{emoji_r} **Fim** vs `{opp_n}` ({rt} {our_s}⭐/{opp_s}⭐)"
                else: ws=f"{emojis['warning']} Estado G: {state}"
        except (coc_errors.NotFound, coc_errors.PrivateWarLog): ws = f"{emojis['success']} Não em Guerra Normal / Log Privado."
        except asyncio.TimeoutError: ws = f"{emojis['error']} Timeout ao verificar Guerra Normal."
        except Exception as e: ws = f"{emojis['error']} Erro G: {type(e).__name__}"; logger.error(f"Erro ao verificar Guerra Normal em /admin status: {e}", exc_info=True)
        emb.add_field(name="Guerra Normal", value=ws, inline=False)
        ls=f"{emojis['warning']} Verificando...";
        try:
            lg = await asyncio.wait_for(coc_client.get_league_group(CLAN_TAG),timeout=60.0);
            if lg and lg.state!="notInWar":
                 season=lg.season; state=lg.state.capitalize(); lg_name=lg.league.name; ls=f"{emojis['league']} **Em CWL** ({lg_name} {season}) Grupo: **{state}**"
                 active_w=None; lg_wars=[];
                 try:
                     lg_wars = await asyncio.wait_for(lg.get_wars(CLAN_TAG),timeout=60.0)
                 except asyncio.TimeoutError: logger.warning(f"Timeout ao buscar guerras da liga no comando /admin status")
                 except Exception as e_get_wars_status: logger.warning(f"Erro ao buscar guerras da liga no comando /admin status: {e_get_wars_status}")

                 current_round=next((w for w in lg_wars if w and w.state in ['inWar','preparation']), None) # Adicionado 'w and'
                 if current_round:
                    active_w=current_round;
                    # Safety checks para clãs
                    our_w_lg = active_w.clan if hasattr(active_w, 'clan') and active_w.clan.tag == CLAN_TAG else getattr(active_w, 'opponent', None)
                    opp_lg = active_w.opponent if hasattr(active_w, 'clan') and active_w.clan.tag == CLAN_TAG else getattr(active_w, 'clan', None)
                    if our_w_lg and opp_lg: # Verifica se ambos clãs foram identificados
                        opp_lg_n=opp_lg.name;
                        state_t="Guerra" if active_w.state=='inWar' else "Prep.";
                        st_em=emojis['war_attack'] if state_t=="Guerra" else emojis['time'];
                        time_obj=active_w.end_time if state_t=="Guerra" else active_w.start_time;
                        t_rel=f"<t:{int(time_obj.time.timestamp())}:R>" if time_obj and hasattr(time_obj, 'time') else "?";
                        ls+=f"\n{st_em} Rodada: **{state_t}** vs `{opp_lg_n}` ({t_rel})";
                        if state_t=="Guerra":
                             our_s=our_w_lg.stars; opp_s=opp_lg.stars; ls+=f" ({our_s}⭐/{opp_s}⭐)"
                    else:
                        ls += f"\n{emojis['error']} Erro ao identificar clãs da rodada atual."
                 else:
                    ls+=f"\n{emojis['info']} Nenhuma rodada CWL ativa."
            else: ls=f"{emojis['success']} Não em CWL."
        except coc_errors.NotFound: ls=f"{emojis['success']} Não em CWL (grupo não encontrado)."
        except asyncio.TimeoutError: ls = f"{emojis['error']} Timeout ao verificar CWL."
        except Exception as e: ls=f"{emojis['error']} Erro Liga: {type(e).__name__}"; logger.error(f"Erro ao verificar CWL em /admin status: {e}", exc_info=True)
        emb.add_field(name="Guerra de Liga (CWL)", value=ls, inline=False)
        rs=f"{emojis['warning']} Verificando..."
        try:
            rl=await asyncio.wait_for(coc_client.get_clan_capital_raid_seasons(CLAN_TAG,limit=1),timeout=45.0);
            if rl and rl[0] and hasattr(rl[0],'state'):
                 r=rl[0]; state=r.state.capitalize(); loot=r.capital_total_loot; attacks=r.total_attacks; d_d=r.districts_destroyed; st_obj=r.start_time; et_obj=r.end_time; st_str=st_obj.time.astimezone(TIMEZONE).strftime('%d/%m %H:%M') if st_obj and hasattr(st_obj,'time') else '?'; et_ts=int(et_obj.time.timestamp()) if et_obj and hasattr(et_obj,'time') else None
                 if state=='Ongoing' and et_ts: rs=f"{emojis['raid']} **Ativo** (<t:{et_ts}:R>)\nOuro:**{loot:,}** Atk:{attacks} Distr:{d_d}"
                 elif state=='Ended': rs=f"{emojis['clan_capital']} **Inativo**. Último ({st_str}):\nOuro:**{loot:,}** Atk:{attacks} Distr:{d_d}"
                 else: rs=f"{emojis['clan_capital']} Estado Raid: **{state}**"
            else: rs=f"{emojis['clan_capital']} Sem info raid."
        except coc_errors.NotFound: rs=f"{emojis['clan_capital']}Sem info raid (NotFound)."
        except asyncio.TimeoutError: rs = f"{emojis['error']} Timeout ao verificar Raid."
        except Exception as e: rs=f"{emojis['error']}Erro Raid: {type(e).__name__}."; logger.error(f"Erro ao verificar Raid em /admin status: {e}", exc_info=True)
        emb.add_field(name="Raid Weekend", value=rs, inline=False)
        lat=bot.latency*1000; emb.add_field(name="Status Bot", value=f"{emojis['success']}Online|Lat:{lat:.0f}ms", inline=False); emb.timestamp=datetime.now(TIMEZONE)
        await interaction.followup.send(embed=emb)
    except Exception as e: logger.error(f"Erro GERAL cmd /admin status:{e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Ocorreu um erro ao executar o comando status: {e}", ephemeral=True)

@admin_group.command(name="top", description="Mostra rankings do clã (doações, troféus, capital, etc).")
@app_commands.describe(tipo="O tipo de ranking a ser exibido.", limite="O número de membros a serem exibidos no ranking (1-50).")
@app_commands.choices(tipo=[ app_commands.Choice(name="Doações (Temporada)", value="doacoes"), app_commands.Choice(name="Recebidos (Temporada)", value="recebidos"), app_commands.Choice(name="Troféus (Vila Principal)", value="trofeus"), app_commands.Choice(name="Contribuição Capital (Última Raid)", value="capital"),])
@app_commands.checks.has_permissions(administrator=True) # Permissão verificada aqui
async def top_command(interaction: discord.Interaction, tipo: app_commands.Choice[str], limite: app_commands.Range[int, 1, 50] = 10):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    selected_type = tipo.value
    await interaction.response.defer(ephemeral=False)
    try:
        clan = await get_clan_data(timeout=45)
        if not clan or not hasattr(clan,'members'): await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Erro obter membros clã `{CLAN_TAG}`!", color=discord.Color.red())); return
        types_map = {"doacoes": ("doações", f"{emojis['donation']} Top {limite} Doadores", discord.Color.green()), "recebidos": ("recebidos", f"{emojis['received']} Top {limite} Recebedores", discord.Color.orange()), "trofeus": ("troféus", f"{emojis['trophy']} Top {limite} Troféus", discord.Color.gold()), "capital": ("capital", f"{emojis['clan_capital']} Top {limite} Contrib. Capital", 0x9B59B6) }
        internal_type, title, color = types_map[selected_type]
        m_list = clan.members or []
        if not m_list and internal_type != "capital": await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Lista membros vazia.", color=discord.Color.orange)); return
        fmt_list = []
        if internal_type == "doações": s_list=sorted(m_list,key=lambda m:m.donations,reverse=True)[:limite]; fmt_list=[f"{i}. `{m.name}`(CV{m.town_hall}):**{m.donations:,}**{emojis['donation']}" for i,m in enumerate(s_list,1)]
        elif internal_type == "recebidos": s_list=sorted(m_list,key=lambda m:m.received,reverse=True)[:limite]; fmt_list=[f"{i}. `{m.name}`(CV{m.town_hall}):**{m.received:,}**{emojis['received']}" for i,m in enumerate(s_list,1)]
        elif internal_type == "troféus": s_list=sorted(m_list,key=lambda m:m.trophies,reverse=True)[:limite]; fmt_list=[f"{i}. `{m.name}`(CV{m.town_hall}):**{m.trophies:,}**{emojis['trophy']}" for i,m in enumerate(s_list,1)]
        elif internal_type == "capital":
            try:
                rl=await asyncio.wait_for(coc_client.get_clan_capital_raid_seasons(CLAN_TAG,limit=1),timeout=45.0);
                if not rl or not rl[0] or not rl[0].members: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']}Sem dados membros últ. raid.", color=discord.Color.orange)); return
                m_data={m.tag:{'name':m.name,'loot':m.capital_resources_looted} for m in rl[0].members}; s_raid=sorted(m_data.items(),key=lambda i:i[1]['loot'],reverse=True)[:limite]; fmt_list=[f"{i}. `{d['name']}`:**{d['loot']:,}**{emojis['clan_capital']}" for i,(t,d) in enumerate(s_raid,1)]
                if rl[0].start_time and hasattr(rl[0].start_time, 'time'): title += f" ({rl[0].start_time.time.astimezone(TIMEZONE).strftime('%d/%m')})"
            except asyncio.TimeoutError: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']}Timeout ao buscar dados da Raid.", color=discord.Color.red)); logger.warning(f"Timeout /top capital"); return
            except Exception as e: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']}Erro ao buscar dados Capital: {type(e).__name__}", color=discord.Color.red)); logger.warning(f"Erro /top capital: {e}", exc_info=True); return
        if not fmt_list: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Nenhum dado para ranking '{tipo.name}'.", color=discord.Color.orange)); return
        base_emb=discord.Embed(title=title,color=color); base_emb.set_footer(text=f"Clã: {clan.name} | Verif:{datetime.now(TIMEZONE).strftime('%d/%m %H:%M')}")
        # Passar interaction.channel para send_embeds_splitted
        if interaction.channel: # Garante que o canal existe
             await send_embeds_splitted(interaction.channel, base_emb, "Ranking", fmt_list, max_len=1024, max_items_per_embed=20)
        else:
             logger.error(f"Erro /admin top: Canal da interação não encontrado.")
             await interaction.followup.send(f"{emojis['error']}Erro: Não foi possível encontrar o canal para enviar a resposta.", ephemeral=True)
    except Exception as e: logger.error(f"Erro GERAL cmd /admin top:{e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Ocorreu um erro ao gerar o ranking: {e}", ephemeral=True)

@admin_group.command(name="setcanal", description="Define o canal onde o bot enviará logs e notificações.")
@app_commands.describe(canal="O canal de texto para enviar as mensagens.")
@app_commands.checks.has_permissions(administrator=True) # Permissão verificada aqui
async def set_canal_command(interaction: discord.Interaction, canal: discord.TextChannel):
    global CHANNEL_ID
    target_channel = canal
    if not interaction.guild: # Adiciona verificação se o comando foi usado em um servidor
        await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Este comando só pode ser usado em um servidor.", color=discord.Color.red()), ephemeral=True); return
    if not target_channel.permissions_for(interaction.guild.me).send_messages or not target_channel.permissions_for(interaction.guild.me).embed_links:
         await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Sem permissão p/ enviar msgs/embeds em {target_channel.mention}.", color=discord.Color.red()), ephemeral=True); return
    try:
         await interaction.response.defer(ephemeral=True)
         CHANNEL_ID = target_channel.id
         # TODO: Salvar CHANNEL_ID permanentemente (ex: em .env ou DB) seria ideal
         logger.info(f"Canal logs -> {target_channel.name}({CHANNEL_ID}) por {interaction.user}")
         confirm_embed = discord.Embed(title=f"{emojis['success']} Canal Logs Alterado", description=f"Logs e notificações serão enviados para {target_channel.mention}.", color=discord.Color.green())
         await interaction.followup.send(embed=confirm_embed, ephemeral=True)

         # --- CORREÇÃO APLICADA AQUI (Erro 2) ---
         await interaction.followup.send(embed=discord.Embed(description=f"{emojis['info']} Canal alterado. As tarefas continuarão rodando. Se necessário, reinicie o bot para garantir a aplicação completa.", color=discord.Color.blue()), ephemeral=True)
         # --- FIM DA CORREÇÃO ---

    except Exception as e: logger.error(f"Erro cmd /admin setcanal: {e}",exc_info=True); await interaction.followup.send(f"{emojis['error']}Ocorreu um erro ao definir o canal: {e}", ephemeral=True)


@admin_group.command(name="setclan", description="Define qual clã o bot deve monitorar.")
@app_commands.describe(tag="A tag do novo clã a ser monitorado (incluindo #).")
@app_commands.checks.has_permissions(administrator=True) # Permissão verificada aqui
async def set_clan_command(interaction: discord.Interaction, tag: str):
    global CLAN_TAG, member_cache, donation_cache, war_cache, raid_weekend_cache, coc_client
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    clan_tag_input = tag.strip().upper();
    if not clan_tag_input.startswith('#'): clan_tag_input = '#' + clan_tag_input
    if not coc.utils.is_valid_tag(clan_tag_input): await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Tag `{clan_tag_input}` inválida.", color=discord.Color.red), ephemeral=True); return
    if clan_tag_input == CLAN_TAG: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['info']} Já monitorando `{clan_tag_input}`.", color=discord.Color.blue), ephemeral=True); return
    await interaction.response.defer(ephemeral=True)
    try:
        logger.info(f"Tentando setclan {clan_tag_input} por {interaction.user}...")
        clan = await asyncio.wait_for(coc_client.get_clan(clan_tag_input),timeout=45.0);
        new_clan_name=clan.name; new_clan_tag=clan.tag; new_clan_badge_url=getattr(clan.badge,'url',None)
        change_embed = discord.Embed(title=f"{emojis['success']} Clã Alvo Alterado!", description=f"Monitorando **{new_clan_name}** (`{new_clan_tag}`).\nLimpando caches e reiniciando tarefas...", color=discord.Color.green())
        if new_clan_badge_url: change_embed.set_thumbnail(url=new_clan_badge_url)
        await interaction.followup.send(embed=change_embed, ephemeral=True)

        old_tag = CLAN_TAG; CLAN_TAG = new_clan_tag
        # TODO: Salvar CLAN_TAG permanentemente (ex: em .env ou DB) seria ideal

        # Limpa Caches
        member_cache={'members':{},'count':0}; donation_cache={}; raid_weekend_cache={'current_raid':None}; war_cache={'war_end_reported':{},'league_war_end_reported':{},'league_start_announced':False}
        logger.info(f"Clã {old_tag}->{CLAN_TAG}({new_clan_name}). Caches limpos.")

        # Reinicia Tasks
        await interaction.followup.send(embed=discord.Embed(description=f"{emojis['info']} Reiniciando tasks p/ **{new_clan_name}**...", color=discord.Color.blue()), ephemeral=True)
        tasks_list=[check_donations,check_members,check_war,check_league_war,check_raid_weekend]; restart_log=[]; all_ok = True
        for t in tasks_list:
              task_name=t.coro.__name__; status_emoji=emojis['error']; status_text="Erro"
              try:
                  if t.is_running(): t.restart(); status_emoji=emojis['success']; status_text="Reiniciada"
                  else: t.start(); status_emoji=emojis['success']; status_text="Iniciada"
              except Exception as e: logger.error(f"Erro restart task {task_name} (setclan): {e}", exc_info=True); status_text="Erro"; all_ok=False
              restart_log.append(f"- {task_name}: {status_text} {status_emoji}")

        restart_embed = discord.Embed(title=f"{emojis['success'] if all_ok else emojis['warning']} Tarefas Reiniciadas p/ {new_clan_name}", description="Status:\n"+"\n".join(restart_log), color=discord.Color.green() if all_ok else discord.Color.orange())
        status_channel = bot.get_channel(CHANNEL_ID);
        try:
            if status_channel: await status_channel.send(embed=restart_embed)
            else: await interaction.followup.send(embed=restart_embed, ephemeral=False) # Envia no canal do comando se o canal de log não for encontrado
            await interaction.followup.send(f"{emojis['success']} Tasks reiniciadas p/ **{new_clan_name}**.", ephemeral=True)
        except Exception as e: logger.error(f"Erro enviar status restart (setclan): {e}"); await interaction.followup.send(f"{emojis['error']} Tasks reiniciadas, erro ao enviar status.", ephemeral=True)
        logger.info(f"Tasks reiniciadas (setclan p/ {CLAN_TAG}) ({'; '.join(restart_log)}).")

    except coc_errors.NotFound: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']}Clã `{clan_tag_input}` não encontrado!", color=discord.Color.red), ephemeral=True)
    except asyncio.TimeoutError: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']}Timeout ao buscar clã `{clan_tag_input}`!", color=discord.Color.red), ephemeral=True)
    except Exception as e: logger.error(f"Erro cmd /admin setclan {clan_tag_input}: {e}",exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro ao definir clã: {e}", ephemeral=True)

@war_group.command(name="ataques", description="Mostra quem ainda não atacou na Guerra Normal atual.")
async def ataques_command(interaction: discord.Interaction):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        war = await asyncio.wait_for(coc_client.get_current_war(CLAN_TAG, war_tag="#0"), timeout=45.0)
        if war and war.is_cwl: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Clã em CWL. Use `/guerra liga_ataques`.", color=discord.Color.orange)); return
        await display_attacks_remaining_slash(interaction, war, war_type="Guerra Normal")
    except coc_errors.NotFound: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Não em Guerra Normal.", color=discord.Color.orange))
    except coc_errors.PrivateWarLog: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Log de Guerra Privado. Não é possível verificar ataques.", color=discord.Color.orange))
    except asyncio.TimeoutError: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Timeout ao buscar dados da guerra.", color=discord.Color.red))
    except Exception as e: logger.error(f"Erro /guerra ataques: {e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro ao verificar ataques: {e}", ephemeral=True)

@war_group.command(name="liga_ataques", description="Mostra quem ainda não atacou na rodada atual da CWL.")
async def liga_ataques_command(interaction: discord.Interaction):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        lg = await asyncio.wait_for(coc_client.get_league_group(CLAN_TAG), timeout=60.0)
        if not lg or lg.state == "notInWar": await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Não em CWL.", color=discord.Color.orange)); return
        curr_war = None; lg_wars = [];
        try: lg_wars = await asyncio.wait_for(lg.get_wars(CLAN_TAG), timeout=60.0)
        except asyncio.TimeoutError: logger.warning(f"Timeout ao buscar guerras da liga em /guerra liga_ataques")
        except Exception as e_wars: logger.warning(f"Erro ao buscar guerras da liga em /guerra liga_ataques: {e_wars}")

        curr_war = next((w for w in lg_wars if w and w.state == 'inWar'), None) or next((w for w in lg_wars if w and w.state == 'preparation'), None) # Adicionado 'w and'
        if not curr_war: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Nenhuma rodada CWL ativa ou em preparação encontrada.", color=discord.Color.orange)); return
        await display_attacks_remaining_slash(interaction, curr_war, war_type="Guerra de Liga")
    except coc_errors.NotFound: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Não em CWL (grupo não encontrado).", color=discord.Color.orange))
    except asyncio.TimeoutError: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Timeout ao buscar dados da CWL.", color=discord.Color.red))
    except Exception as e: logger.error(f"Erro /guerra liga_ataques: {e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro ao verificar ataques da liga: {e}", ephemeral=True)

@info_group.command(name="membro", description="Mostra detalhes e estatísticas de um jogador.")
@app_commands.describe(tag="A tag do jogador (incluindo o #).")
async def membro_command(interaction: discord.Interaction, tag: str):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    player_tag=tag.strip().upper();
    if not player_tag.startswith('#'): player_tag='#'+player_tag
    if not coc.utils.is_valid_tag(player_tag): await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} Tag `{player_tag}` inválida.", color=discord.Color.red), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        player=await asyncio.wait_for(coc_client.get_player(player_tag),timeout=30.0);
        p_n=player.name; p_t=player.tag; p_th=player.town_hall; p_th_w=player.town_hall_weapon; p_xp=player.exp_level; p_lg=player.league; p_tr=player.trophies; p_btr=player.best_trophies; p_ws=player.war_stars; p_don=player.donations; p_rec=player.received; p_cl=player.clan; p_role=player.role if p_cl else 'N/A'; p_hr=player.heroes; p_pet=player.pets
        title=f"{p_lg.name if p_lg else ''} {p_n} ({p_t})"
        emb=discord.Embed(title=title, color=discord.Color.orange());
        if p_lg and p_lg.icon: emb.set_thumbnail(url=p_lg.icon.url)
        cl_info="S/ clã";
        if p_cl:
            cl_name = getattr(p_cl, 'name', 'Nome Clã?') # Safety check
            cl_tag = getattr(p_cl, 'tag', None)
            cl_badge_url = getattr(p_cl.badge, 'url', None) if hasattr(p_cl, 'badge') else None
            cl_info=f"[{cl_name}]({coc.utils.clan_link(cl_tag) if cl_tag else '#'})" if cl_tag else cl_name
            cl_info += f"\nCargo: **{p_role}**";
            if cl_badge_url: emb.set_author(name=f"Membro de {cl_name}", icon_url=cl_badge_url)
        emb.add_field(name=f"{emojis['clan_capital']} Clã",value=cl_info,inline=False)
        emb.add_field(name="CV", value=f"**{p_th}**"+(f" (Arma:{p_th_w})" if p_th_w else ""), inline=True); emb.add_field(name="XP Lvl", value=str(p_xp), inline=True); emb.add_field(name="Liga", value=f"{p_tr:,}{emojis['trophy']}"+(f" ({p_lg.name})" if p_lg else ""), inline=True); emb.add_field(name="Recorde", value=f"{p_btr:,}{emojis['trophy']}", inline=True); emb.add_field(name="Estrelas G.", value=f"{p_ws:,}⭐", inline=True); emb.add_field(name="Doa/Rec", value=f"{p_don:,}{emojis['donation']}/{p_rec:,}{emojis['received']}", inline=True);

        hv_heroes = [h for h in p_hr if h.is_home_base] if p_hr else [] # Garante que p_hr não é None
        if hv_heroes: # Verifica se a lista não está vazia
             # Cria a lista de strings formatadas
             hero_lines = [f"- {h.name}: **{h.level}**/{h.max_level}" for h in hv_heroes]
             # Junta as linhas em uma única string
             h_str = "\n".join(hero_lines)
             # Adiciona o campo ao embed se a string foi criada
             emb.add_field(name=f"{emojis['war_attack']} Heróis",value=h_str,inline=False)

        pet_list = p_pet if p_pet else []
        if pet_list:
            pet_lines = [f"- {p.name}: **{p.level}**/{p.max_level}" for p in pet_list]
            pet_str = "\n".join(pet_lines)
            emb.add_field(name="🐾 Pets",value=pet_str,inline=False)

        emb.description=f"[Ver perfil]({coc.utils.player_link(p_t)})"; emb.set_footer(text=f"Verif:{datetime.now(TIMEZONE):%d/%m/%Y %H:%M}")
        await interaction.followup.send(embed=emb)
    except coc_errors.NotFound: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Jogador `{player_tag}` não encontrado.", color=discord.Color.red))
    except asyncio.TimeoutError: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Timeout ao buscar dados do jogador `{player_tag}`.", color=discord.Color.red))
    except Exception as e: logger.error(f"Erro /info membro {player_tag}:{e}",exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro ao buscar dados do jogador: {e}", ephemeral=True)

@info_group.command(name="capital", description="Mostra informações sobre a Capital do Clã e a última Raid.")
async def capital_command(interaction: discord.Interaction):
    if not coc_client: await interaction.response.send_message(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red()), ephemeral=True); return
    await interaction.response.defer(ephemeral=False)
    try:
        clan=await get_clan_data(timeout=45);
        if not clan: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']}Erro dados clã `{CLAN_TAG}`!", color=discord.Color.red)); return

        c_n = clan.name
        emb = discord.Embed(title=f"{emojis['clan_capital']} Capital: {c_n}", color=0x9B59B6) # Usa int para cor
        if clan.badge:
            emb.set_thumbnail(url=clan.badge.url)

        cap_info=clan.clan_capital; dist_field_added=False; final_embeds = [] # Lista para guardar embeds a serem enviados
        dist_list = []
        dist_title = f"{emojis['clan_capital']} Distritos"

        try:
            if cap_info:
                hall_lvl=cap_info.capital_hall_level; emb.description=f"Salão Capital: **{hall_lvl}**"; districts=cap_info.districts;
                dist_list=[f"- {d.name}: Lvl **{d.hall_level}**" for d in districts] if districts else ["N/D"];
                dist_title=f"{emojis['clan_capital']} Distritos ({len(dist_list) if dist_list != ['N/D'] else 0})" # Conta corretamente
                if len("\n".join(dist_list)) > 1024 and dist_list != ["N/D"]:
                     dist_field_added=True
                     # Não adiciona ao embed principal, será enviado separadamente
                elif dist_list != ["N/D"]: emb.add_field(name=dist_title, value="\n".join(dist_list), inline=False)
                else: emb.add_field(name=dist_title, value="N/D.", inline=False)
            else: emb.description="Infos Capital indisponíveis."
        except Exception as e: emb.description=f"Erro Capital:{e}"; logger.error(f"Erro /info capital (detalhes):{e}",exc_info=True)

        raid_title=f"{emojis['raid']} Última/Atual Raid"; rf_v=f"{emojis['warning']} Verificando..."; top_s=""; raid_found=False; top_raiders_list = []
        try:
            rl=await asyncio.wait_for(coc_client.get_clan_capital_raid_seasons(CLAN_TAG,limit=1),timeout=45.0);
            if rl and rl[0] and hasattr(rl[0],'state'):
                 raid_found=True; r=rl[0]; state=r.state.capitalize(); loot=r.capital_total_loot; attacks=r.total_attacks; d_d=r.districts_destroyed; st_obj=r.start_time; et_obj=r.end_time; st=st_obj.time.astimezone(TIMEZONE).strftime('%d/%m %H:%M') if st_obj and hasattr(st_obj,'time') else '?'; et_ts=int(et_obj.time.timestamp()) if et_obj and hasattr(et_obj,'time') else None; t_inf=f"(Fim: <t:{et_ts}:R>)" if et_ts and state=='Ongoing' else ""; st_t="Ativo" if state=='Ongoing' else "Finalizado"; s_em=emojis['raid'] if state=='Ongoing' else emojis['success']
                 rf_v=(f"**Estado:** {s_em}{st_t} {t_inf}\n**Início:** {st}\n{emojis['clan_capital']}Ouro:**{loot:,}** {emojis['war_attack']}Atk:{attacks} {emojis['destruction']}Distr:{d_d}")
                 if r.members:
                     m_data={m.tag:{'name':m.name,'loot':m.capital_resources_looted} for m in r.members};
                     s_raiders=sorted(m_data.items(),key=lambda i:i[1]['loot'],reverse=True)[:5]; # Top 5 apenas para o embed principal
                     top_s="\n".join([f"{i}. `{d['name']}`:**{d['loot']:,}**" for i,(t,d) in enumerate(s_raiders,1)])
                     # Guarda a lista completa para possível split
                     full_raiders_sorted = sorted(m_data.items(), key=lambda i: i[1]['loot'], reverse=True)
                     top_raiders_list = [f"{i}. `{d['name']}`:**{d['loot']:,}**" for i, (t, d) in enumerate(full_raiders_sorted, 1)]
            else: rf_v=f"{emojis['warning']}Nenhum dado raid."
        except asyncio.TimeoutError: rf_v = f"{emojis['error']} Timeout ao buscar Raid."
        except Exception as e: rf_v=f"{emojis['error']}Erro Raid: {type(e).__name__}."

        # Adiciona info da raid ao embed principal (se não foi dividido pelos distritos)
        if not dist_field_added: emb.add_field(name=raid_title, value=rf_v, inline=False);
        # Adiciona top 5 ao embed principal (se não foi dividido pelos distritos e se houver top)
        if raid_found and top_s and not dist_field_added:
             emb.add_field(name="🌟 Top Contribs", value=top_s, inline=False)

        emb.set_footer(text=f"Verif:{datetime.now(TIMEZONE):%d/%m/%Y %H:%M}")

        # Envia o embed principal
        await interaction.followup.send(embed=emb)

        # Se os distritos foram separados, envia-os agora usando send_embeds_splitted
        if dist_field_added and interaction.channel and dist_list != ["N/D"]:
            await send_embeds_splitted(interaction.channel, discord.Embed(color=emb.color), dist_title, dist_list, max_items_per_embed=15)
            await asyncio.sleep(0.3) # Pequena pausa

        # Se a raid foi encontrada e a lista completa de raiders é longa OU se os distritos foram divididos, envia-a separadamente
        if raid_found and top_raiders_list and interaction.channel and (len("\n".join(top_raiders_list)) > 1024 or dist_field_added):
            top_emb = discord.Embed(title="🌟 Top Contribs Raid", color=emb.color)
            await send_embeds_splitted(interaction.channel, top_emb, "Ranking", top_raiders_list, max_items_per_embed=15)

    except asyncio.TimeoutError: await interaction.followup.send(f"{emojis['error']}Timeout ao buscar dados do clã.", ephemeral=True)
    except Exception as e: logger.error(f"Erro GERAL cmd /info capital:{e}", exc_info=True); await interaction.followup.send(f"{emojis['error']}Erro ao buscar informações da capital: {e}", ephemeral=True)

@bot.tree.command(name="ajuda", description="Mostra informações sobre os comandos do bot.")
async def ajuda_command(interaction: discord.Interaction):
    embed = discord.Embed(title=f"{emojis['info']} Ajuda - {bot.user.name}", description="Monitora eventos CoC e fornece infos via comandos de barra (`/`).", color=discord.Color.green())
    if bot.user.avatar: embed.set_thumbnail(url=bot.user.avatar.url)
    embed.add_field(name=f"{emojis['admin']} Admin (`/admin ...`) [ADM]", value=f"`status`: Exibe status geral.\n`top`: Mostra rankings do clã.\n`setcanal`: Define canal de logs.\n`setclan`: Define clã a monitorar.", inline=False)
    embed.add_field(name=f"{emojis['war_attack']} Guerra (`/guerra ...`)", value=f"`ataques`: Mostra ataques restantes na Guerra Normal.\n`liga_ataques`: Mostra ataques restantes na CWL.", inline=False)
    embed.add_field(name=f"{emojis['info']} Info (`/info ...`)", value=f"`membro <TAG>`: Detalhes de um jogador.\n`capital`: Infos da Capital do Clã.", inline=False)
    embed.add_field(name="👀 Eventos Monitorados Auto", value=f"Entrada/Saída de membros, Doações, Ataques de Guerra/Liga, Progresso/Fim de Raid são enviados automaticamente no canal definido por `/admin setcanal`.", inline=False) # Descrição melhorada
    embed.set_footer(text=f"Versão: 15.0.11")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Função auxiliar corrigida para receber interaction e tratar canal
async def display_attacks_remaining_slash(interaction: discord.Interaction, war, war_type="Guerra"):
    if not interaction.channel: # Verifica se o canal da interação é válido
         logger.error(f"Erro display_attacks_remaining_slash: Canal da interação inválido.")
         # Tenta enviar no followup mesmo assim, pode funcionar se a interação ainda for válida
         try: await interaction.followup.send(f"{emojis['error']}Erro: Não foi possível encontrar o canal para enviar a resposta.", ephemeral=True)
         except Exception as e_followup: logger.error(f"Erro ao enviar msg de erro (canal inválido) em display_attacks_remaining_slash: {e_followup}")
         return

    if not war or war.state not in ['inWar', 'preparation']: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Não em {war_type} ativa ou em preparação.", color=discord.Color.orange())); return # Mensagem ajustada
    our_c = war.clan if hasattr(war, 'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'opponent', None)
    en_c = war.opponent if hasattr(war, 'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'clan', None)
    if not our_c or not en_c: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['error']} Erro identificar clãs na {war_type}.", color=discord.Color.red())); return
    state_info = ""; time_ref = None; color = discord.Color.blue(); timestamp = datetime.now(TIMEZONE)
    if war.state == 'preparation' and war.start_time and hasattr(war.start_time, 'time'):
        time_ref = war.start_time.time.astimezone(TIMEZONE); state_info = f"**Estado:** Prep.\n**Início:** <t:{int(time_ref.timestamp())}:R>"; timestamp = time_ref
    elif war.state == 'inWar' and war.end_time and hasattr(war.end_time, 'time'):
        time_ref = war.end_time.time.astimezone(TIMEZONE); state_info = f"**Estado:** Guerra\n**Término:** <t:{int(time_ref.timestamp())}:R>"; color = discord.Color.orange(); timestamp = time_ref
    else: # Caso não tenha tempo de início/fim ou estado inesperado
         state_info = f"**Estado:** {war.state.capitalize()}"

    attacks_per = war.attacks_per_member; remaining = []; total_possible = 0; total_done = 0; members = our_c.members or []
    if not members: await interaction.followup.send(embed=discord.Embed(description=f"{emojis['warning']} Lista membros da {war_type} indisponível.", color=discord.Color.orange)); return
    for m in members:
        total_possible += attacks_per; attacks_d = len(m.attacks); total_done += attacks_d; attacks_l = attacks_per - attacks_d
        if attacks_l > 0: name=m.name; th=m.town_hall; map_pos=m.map_position; remaining.append(f"{map_pos}. `{name}` (CV{th}): **{attacks_l}** atk(s)")
    title = f"{emojis['war_attack']} Ataques Restantes - {war_type} vs {en_c.name}"; base_embed = discord.Embed(title=title, description=state_info, color=color, timestamp=timestamp); base_embed.set_footer(text=f"Clã: {our_c.name}")
    summary = f"**{total_done} / {total_possible}** ataques realizados."; base_embed.add_field(name="Resumo", value=summary, inline=False)
    if not remaining: base_embed.add_field(name="Situação", value=f"{emojis['success']} Todos atacaram!", inline=False); base_embed.color = discord.Color.green(); await interaction.followup.send(embed=base_embed)
    else:
        temp_embed = base_embed.copy(); field_title = "Membros Pendentes"; full_list_str = "\n".join(remaining)
        if len(full_list_str) <= 1024 and len(remaining) <= 20 : # Cabe em um único campo
            temp_embed.add_field(name=field_title, value=full_list_str, inline=False);
            await interaction.followup.send(embed=temp_embed)
        else: # Precisa dividir
             # Envia o embed base primeiro
             await interaction.followup.send(embed=base_embed)
             # Depois envia a lista de membros pendentes separadamente
             if interaction.channel: # Garante que canal existe para o split
                 await send_embeds_splitted(interaction.channel, discord.Embed(color=color), field_title, remaining, max_items_per_embed=15)
             else:
                 logger.error(f"Erro display_attacks_remaining_slash: Canal inválido para enviar split.")


# Adiciona os grupos à árvore
bot.tree.add_command(admin_group)
bot.tree.add_command(war_group)
bot.tree.add_command(info_group)

# --- Função Principal ---
async def main():
    global coc_client
    if not TOKEN: logger.critical("Token Discord não encontrado."); return
    logger.info("Iniciando bot Discord (main)...")
    try:
        await bot.start(TOKEN)
    except discord.LoginFailure: logger.critical("Login Discord falhou: Token inválido.")
    except discord.PrivilegedIntentsRequired: logger.critical("Login Discord falhou: Intenções Privilegiadas não habilitadas (Gateway Intents).")
    except KeyboardInterrupt: logger.info("Desligamento manual solicitado.")
    except Exception as e: logger.critical(f"Erro fatal no loop principal do bot: {e}", exc_info=True)
    finally:
        # Garante que o cliente CoC seja fechado ao sair
        if coc_client and hasattr(coc_client, 'is_closed') and not coc_client.is_closed: # Verifica se existe e não está fechado
            logger.info("Fechando cliente CoC no final do main...")
            try:
                 await coc_client.close()
                 logger.info("Cliente CoC fechado no final do main.")
            except Exception as e_close:
                 logger.error(f"Erro ao fechar cliente CoC no finally: {e_close}", exc_info=True)
        logger.info("Bot encerrado.")

if __name__ == "__main__":
    try:
        # A política de loop de eventos do Windows só é necessária se você estiver executando no Windows
        # e usando versões mais antigas do Python ou enfrentando problemas específicos.
        # Pode ser removido se não for necessário.
        if os.name == 'nt':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except Exception as e_run:
        # Log crítico se asyncio.run falhar
        # Tenta usar o logger configurado, se falhar, usa print
        try:
            logger.critical(f"Erro crítico irrecuperável ao executar asyncio.run(main): {e_run}", exc_info=True)
        except:
            print(f"ERRO CRÍTICO IRRECUPERÁVEL (logger falhou): {e_run}")
