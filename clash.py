# -*- coding: utf-8 -*-
# Versão 14.12 - Adiciona servidor web aiohttp para compatibilidade com Render.com
# Versão 14.13 - Melhoria visual dos logs com Embeds (Solicitação do usuário)

import discord
from discord.ext import commands, tasks
import coc
from coc import errors as coc_errors
import asyncio
import os
import logging
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from aiohttp import web # <--- Adicionado para o servidor web

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
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# --- Emojis ---
emojis = {
    'donation': '🎁', 'join': '➡️', 'leave': '⬅️', 'war_win': '🏆', 'war_lose': '😥',
    'war_tie': '🤝', 'war_attack': '⚔️', 'war_defense': '🛡️', 'raid': '🔥', 'level_up': '⭐',
    'trophy': '🏆', 'time': '⏰', 'clan_capital': '🏰', 'missed_attack': '❌', 'info': 'ℹ️',
    'error': '❌', 'success': '✅', 'warning': '⚠️', 'league': '🌟',
    'received': '📥', # Adicionado para diferenciar recebido
    'progress': '📊', # Adicionado para progresso
    'destruction': '💥' # Adicionado para destruição
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

@bot.event
async def before_closing():
    logger.info("Recebido sinal para encerrar...")
    if hasattr(bot, 'web_runner'):
        logger.info("Encerrando servidor web...")
        try:
            await bot.web_runner.cleanup()
            logger.info("Servidor web encerrado.")
        except Exception as e:
            logger.error(f"Erro ao encerrar servidor web: {e}", exc_info=True)
    if coc_client and hasattr(coc_client, 'close'):
        logger.info("Fechando cliente CoC...")
        try:
            await coc_client.close()
            logger.info("Cliente CoC fechado.")
        except Exception as e_coc_close:
            logger.error(f"Erro ao fechar cliente CoC: {e_coc_close}")

# --- Inicialização CoC ---
async def initialize_coc_client():
    global coc_client
    logger.info("--- Iniciando Login Cliente CoC ---")
    if not EMAIL or not PASSWORD: logger.critical("Email/Senha CoC não encontrados."); return False
    for attempt in range(1, 4):
        try:
            logger.info(f"[Tentativa {attempt}/3] Criando Client...")
            temp_client = coc.Client(key_count=1, key_names="cocpy-bot-v14", throttle_limit=20)
            logger.info(f"[Tentativa {attempt}/3] Login com Email/Senha...")
            await asyncio.wait_for(temp_client.login(EMAIL, PASSWORD), timeout=60.0)
            if hasattr(temp_client, 'http') and temp_client.http:
                 coc_client = temp_client; logger.info(f"[Tentativa {attempt}/3] Login CoC OK."); return True
            else: logger.error(f"[Tentativa {attempt}/3] Login OK, mas HTTP session inválida.")
        except coc_errors.AuthenticationError as e_auth:
            logger.error(f"[Tentativa {attempt}/3] Falha autenticação: {e_auth}"); return False
        except asyncio.TimeoutError: logger.error(f"[Tentativa {attempt}/3] Timeout login.")
        except Exception as e_login: logger.error(f"[Tentativa {attempt}/3] Erro login: {e_login}", exc_info=True)
        if attempt < 3: wait_time = 15 * attempt; logger.info(f"Aguardando {wait_time}s..."); await asyncio.sleep(wait_time)
    logger.critical("--- Falha em todas as tentativas de login CoC ---"); coc_client = None; return False

# --- Funções Auxiliares ---
async def get_clan_data(tag=None):
    global CLAN_TAG, coc_client
    if not coc_client or not hasattr(coc_client, 'http') or not coc_client.http:
        logger.error("CoC Client inválido ou não inicializado em get_clan_data.")
        return None
    target_tag = tag or CLAN_TAG
    if not target_tag: logger.error("Tag clã não definida (get_clan_data)."); return None
    try:
        logger.debug(f"Buscando dados clã: {target_tag}")
        clan = await asyncio.wait_for(coc_client.get_clan(target_tag), timeout=30.0)
        logger.debug(f"Dados clã '{getattr(clan, 'name', target_tag)}' recebidos.")
        return clan
    except coc_errors.NotFound:
        logger.error(f"Clã '{target_tag}' não encontrado."); return None
    except coc_errors.ClashOfClansException as e_coc:
        logger.warning(f"Erro API CoC ({type(e_coc).__name__}) buscando clã '{target_tag}': {e_coc}"); return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout buscando clã '{target_tag}'."); return None
    except Exception as e:
        logger.error(f"Erro Inesperado ({type(e).__name__}) buscando clã '{target_tag}': {e}", exc_info=True); return None

async def send_embeds_splitted(channel, base_embed, field_name, items_list, max_len=1024, max_items_per_embed=25):
    # <<< EMBED START >>>
    # Adaptada para Embeds: max_len agora é por valor do campo, e max_items_per_embed limita campos por embed
    if not items_list:
        try:
            # Não envia embed vazio, apenas loga ou lida de outra forma se necessário
            logger.debug("send_embeds_splitted: Lista de itens vazia.")
            # Se quiser enviar uma mensagem indicando que está vazio:
            # base_embed.add_field(name=field_name, value="Nenhum item.", inline=False)
            # await channel.send(embed=base_embed)
        except Exception as e:
            logger.error(f"Erro send_embeds_splitted (lista vazia): {e}", exc_info=True)
        return

    current_embed = base_embed.copy()
    current_value = ""
    item_count_in_current_embed = 0
    embed_count = 0

    # Limpa campos pré-existentes se for o primeiro embed a ser criado por esta função
    if len(current_embed.fields) > 0:
         logger.warning("Embed base passado para send_embeds_splitted já continha campos. Limpando.")
         current_embed.clear_fields()

    for i, item in enumerate(items_list):
        item_line = item + "\n"

        # Verifica se adicionar esta linha excede o limite do valor do campo
        # OU se já atingiu o limite de campos por embed (Discord limita a 25)
        # OU se o tamanho total do embed excederia o limite (6000 caracteres) - Verificação simplificada
        if (len(current_value) + len(item_line) > max_len) or \
           (item_count_in_current_embed >= max_items_per_embed) or \
           (len(current_embed) + len(item_line) > 5900): # Deixa margem

            # Adiciona o campo atual antes de criar um novo
            if current_value:
                current_embed.add_field(
                    name=f"{field_name} (Parte {embed_count + 1})" if embed_count > 0 or len(items_list) > max_items_per_embed else field_name,
                    value=current_value,
                    inline=False
                )
                item_count_in_current_embed += 1

            # Envia o embed atual
            try:
                logger.debug(f"Enviando embed dividido (Parte {embed_count + 1})")
                await channel.send(embed=current_embed)
                await asyncio.sleep(0.5) # Pequena pausa entre embeds
            except discord.HTTPException as e:
                logger.error(f"Erro HTTP ao enviar embed dividido (Parte {embed_count + 1}): {e.status} {e.code} - {e.text}", exc_info=True)
                # Tentar enviar uma versão mais curta se for erro de tamanho? Pode ser complexo.
                return # Aborta se falhar
            except Exception as e:
                logger.error(f"Erro ao enviar embed dividido (Parte {embed_count + 1}): {e}", exc_info=True)
                return # Aborta se falhar

            # Prepara o próximo embed
            embed_count += 1
            current_embed = base_embed.copy()
            current_embed.clear_fields() # Garante que está limpo
            current_value = item_line
            item_count_in_current_embed = 0 # Reset counter for the new embed field

        else:
            current_value += item_line

    # Envia o último embed se houver conteúdo restante
    if current_value:
        current_embed.add_field(
             name=f"{field_name} (Parte {embed_count + 1})" if embed_count > 0 or item_count_in_current_embed > 0 else field_name,
             value=current_value,
             inline=False
        )
        try:
            logger.debug(f"Enviando último embed (Parte {embed_count + 1 if embed_count > 0 or item_count_in_current_embed > 0 else 1})")
            await channel.send(embed=current_embed)
        except discord.HTTPException as e:
            logger.error(f"Erro HTTP ao enviar último embed: {e.status} {e.code} - {e.text}", exc_info=True)
        except Exception as e:
            logger.error(f"Erro ao enviar último embed: {e}", exc_info=True)
    # <<< EMBED END >>>

async def get_player_name(tag):
    global coc_client; fallback_name = f"Jogador ({tag[-4:]})" if tag else "Jogador (?)"
    if not coc_client or not tag: return fallback_name
    try: player = await asyncio.wait_for(coc_client.get_player(tag), timeout=15.0); return getattr(player, 'name', fallback_name)
    except (coc_errors.NotFound, asyncio.TimeoutError): return fallback_name
    except Exception as e: logger.error(f"Erro get_player_name {tag}: {e}", exc_info=True); return fallback_name

# --- Tarefas de Monitoramento ---
@tasks.loop(minutes=5)
async def check_donations():
    # <<< EMBED START >>>
    global donation_cache, coc_client
    if not coc_client: logger.debug("check_donations pulado: cliente CoC inválido."); return
    clan = await get_clan_data()
    if not clan or not hasattr(clan, 'members') or not clan.members:
        logger.debug("check_donations pulado: dados clã/membros indisponíveis."); return
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel: logger.warning("check_donations: Canal ID não encontrado."); return

        donation_updates = []
        reception_updates = []
        current_time = datetime.now(TIMEZONE)
        local_cache = donation_cache.copy()
        new_state = {}
        is_initial = not local_cache

        for member in clan.members:
            tag = getattr(member, 'tag', None)
            if not tag: continue
            donations = getattr(member, 'donations', 0)
            received = getattr(member, 'received', 0)
            name = getattr(member, 'name', f'Membro({tag[-4:]})')
            current_data = {'name': name, 'donations': donations, 'received': received}
            new_state[tag] = current_data

            if not is_initial and tag in local_cache:
                old = local_cache[tag]
                old_don = old.get('donations', 0)
                old_rec = old.get('received', 0)
                don_diff = current_data['donations'] - old_don
                rec_diff = current_data['received'] - old_rec

                if don_diff > 0:
                    donation_updates.append(f"{emojis['donation']} `{name}` doou **{don_diff}** (Total: {current_data['donations']:,})")
                if rec_diff > 0:
                    reception_updates.append(f"{emojis['received']} `{name}` recebeu **{rec_diff}** (Total: {current_data['received']:,})")

        donation_cache = new_state

        if (donation_updates or reception_updates) and not is_initial:
            logger.info(f"Detectadas {len(donation_updates)} doações, {len(reception_updates)} recebimentos.")

            embed = discord.Embed(
                title=f"{emojis['donation']} Atualização de Doações/Recebimentos",
                color=discord.Color.blue(),
                timestamp=current_time
            )
            embed.set_footer(text=f"Clã: {getattr(clan, 'name', CLAN_TAG)}")

            all_updates = donation_updates + reception_updates
            update_text = "\n".join(all_updates)

            # Limitar o tamanho da descrição ou usar campos se for muito longo
            if len(update_text) <= 4096: # Limite da descrição do Embed
                 embed.description = update_text
                 try:
                     await channel.send(embed=embed)
                 except discord.HTTPException as e:
                     logger.error(f"Erro HTTP ao enviar embed de doações: {e.status} {e.code} - {e.text}. Tamanho: {len(embed)}", exc_info=True)
                     # Fallback para mensagem de texto se o embed falhar (ou dividir)
                     await channel.send(f"{emojis['time']}[{current_time.strftime('%H:%M')}] {emojis['donation']} Doa/Rec:\n" + update_text[:1900] + "...") # Envia truncado
                 except Exception as e:
                     logger.error(f"Erro ao enviar embed de doações: {e}", exc_info=True)

            else:
                # Se for muito longo para a descrição, usa a função de split
                logger.info("Lista de doações/recebimentos muito longa, dividindo...")
                # Cria um embed base sem descrição para a função de split
                base_embed_split = discord.Embed(
                    title=f"{emojis['donation']} Atualização de Doações/Recebimentos",
                    color=discord.Color.blue(),
                    timestamp=current_time
                )
                base_embed_split.set_footer(text=f"Clã: {getattr(clan, 'name', CLAN_TAG)}")
                await send_embeds_splitted(channel, base_embed_split, "Atualizações", all_updates, max_len=1024, max_items_per_embed=15) # Ajuste max_items se necessário


        elif is_initial and new_state:
            logger.info("Cache doações inicializado.")
        else:
            logger.debug("check_donations executado, sem novas doações/recebimentos.")

    except Exception as e:
        logger.error(f"Erro GERAL check_donations: {e}", exc_info=True)
    # <<< EMBED END >>>

@tasks.loop(minutes=10)
async def check_members():
    # <<< EMBED START >>>
    global member_cache, coc_client
    if not coc_client: logger.debug("check_members pulado: cliente CoC inválido."); return
    clan = await get_clan_data()
    if not clan or not hasattr(clan, 'members') or not clan.members:
        logger.debug("check_members pulado: dados clã/membros indisponíveis."); return
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel: logger.warning("check_members: Canal ID não encontrado."); return

        current_dict = {getattr(m, 'tag', None): getattr(m, 'name', '?') for m in clan.members if hasattr(m, 'tag')}
        current_dict = {k: v for k, v in current_dict.items() if k}
        current_time = datetime.now(TIMEZONE)

        if not member_cache['members']:
            logger.info("Cache membros inicializando...")
            member_cache['members'] = current_dict
            member_cache['count'] = len(current_dict)
            logger.info(f"Cache membros inicializado: {member_cache['count']} membros.");
            # Opcional: Enviar embed de status inicial
            # init_embed = discord.Embed(title=f"{emojis['info']} Monitoramento de Membros Iniciado",
            #                            description=f"Clã **{getattr(clan, 'name', CLAN_TAG)}**\nMembros atuais: **{member_cache['count']}**",
            #                            color=discord.Color.light_grey(), timestamp=current_time)
            # try: await channel.send(embed=init_embed)
            # except Exception as e: logger.error(f"Erro ao enviar embed inicial de membros: {e}")
            return

        old_set = set(member_cache['members'].keys())
        current_set = set(current_dict.keys())
        left_tags = old_set - current_set
        joined_tags = current_set - old_set

        send_tasks = []
        log_msgs = []

        if left_tags:
            logger.info(f"Detectadas {len(left_tags)} saídas.")
            for tag in left_tags:
                name = member_cache['members'].get(tag, f"Membro ({tag[-4:]})")
                log_msgs.append(f"Saiu:{name}({tag})")
                embed = discord.Embed(
                    title=f"{emojis['leave']} Saída de Membro",
                    description=f"**{name}** saiu do clã.",
                    color=discord.Color.red(),
                    timestamp=current_time
                )
                embed.set_footer(text=f"Clã: {getattr(clan, 'name', CLAN_TAG)}")
                send_tasks.append(channel.send(embed=embed))

        if joined_tags:
            logger.info(f"Detectadas {len(joined_tags)} entradas.")
            for tag in joined_tags:
                name = current_dict.get(tag, f"Membro ({tag[-4:]})")
                log_msgs.append(f"Entrou:{name}({tag})")
                # Tenta obter mais detalhes do membro que entrou
                member_details = next((m for m in clan.members if getattr(m, 'tag', None) == tag), None)
                details_text = ""
                if member_details:
                    th = getattr(member_details, 'town_hall', '?')
                    lvl = getattr(member_details, 'exp_level', '?')
                    trophies = getattr(member_details, 'trophies', 0)
                    league_name = getattr(getattr(member_details, 'league', None), 'name', 'Sem Liga')
                    details_text = f"CV{th} | Nível {lvl} | {trophies}{emojis['trophy']} | {league_name}"

                embed = discord.Embed(
                    title=f"{emojis['join']} Entrada de Membro",
                    description=f"**{name}** entrou no clã!",
                    color=discord.Color.green(),
                    timestamp=current_time
                )
                if details_text:
                     embed.add_field(name="Detalhes", value=details_text, inline=False)
                embed.set_footer(text=f"Clã: {getattr(clan, 'name', CLAN_TAG)}")
                send_tasks.append(channel.send(embed=embed))

        if send_tasks:
            results = await asyncio.gather(*send_tasks, return_exceptions=True)
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    logger.error(f"Erro send embed membro [{i}]: {res}", exc_info=True)

            if log_msgs:
                logger.info(f"Detalhes Membros: {', '.join(log_msgs)}")

            # Atualiza o cache *depois* de processar as mudanças
            member_cache['members'] = current_dict
            member_cache['count'] = len(current_dict)
            # Envia uma atualização do total de membros
            count_embed = discord.Embed(
                description=f"Total de membros atualizado: **{member_cache['count']}/50**",
                color=discord.Color.light_grey(),
                timestamp=current_time
            )
            try:
                await channel.send(embed=count_embed)
            except Exception as e:
                logger.error(f"Erro ao enviar embed de contagem de membros: {e}")

        else:
            logger.debug(f"check_members executado, sem alterações.")

    except Exception as e:
        logger.error(f"Erro GERAL check_members: {e}", exc_info=True)
    # <<< EMBED END >>>


async def check_war_attacks_and_report(war, war_type="Guerra Normal"):
    # <<< EMBED START >>> (Principalmente na parte de reportar ataques individuais)
    global war_cache, coc_client, bot, CHANNEL_ID, CLAN_TAG, TIMEZONE, emojis
    if not coc_client: logger.debug("check_war_attacks pulado: cliente CoC inválido."); return
    channel=bot.get_channel(CHANNEL_ID)
    if not channel: logger.warning(f"check_war_attacks ({war_type}): Canal ID não encontrado."); return
    try:
        our_c=war.clan if hasattr(war,'clan') and war.clan.tag==CLAN_TAG else getattr(war,'opponent',None);
        en_c=war.opponent if hasattr(war,'clan') and war.clan.tag==CLAN_TAG else getattr(war,'clan',None);
        if not our_c or not en_c: logger.error(f"Erro ID clãs {war_type} ({getattr(war, 'tag', 'N/A')})"); return

        prep_time_obj = getattr(war,'preparation_start_time', None)
        prep_time_iso = prep_time_obj.time.isoformat() if prep_time_obj and hasattr(prep_time_obj, 'time') else datetime.now().isoformat()
        war_id=f"{getattr(our_c,'tag','?')}-{getattr(en_c,'tag','?')}-{prep_time_iso}";

        if war_id not in war_cache: war_cache[war_id]={'attacks':{},'time_alerts':set(),'state':getattr(war,'state','unknown')}
        war_data=war_cache[war_id]
        current_time = datetime.now(TIMEZONE)
        current_state = getattr(war,'state','unknown')

        if war_id in war_cache: war_cache[war_id]['state'] = current_state
        logger.debug(f"Verificando {war_type} ID:{war_id[-15:]} | Estado API:{current_state} Cache:{war_data['state']}")

        if current_state=='inWar':
            m_check=getattr(our_c,'members',[])
            new_attacks_found = False
            for m in m_check:
                tag = getattr(m, 'tag', None)
                if not tag: continue
                m_att=getattr(m,'attacks',[])
                curr_c=len(m_att)
                prev_c=war_data.get('attacks',{}).get(tag,0);
                if curr_c>prev_c:
                    new_attacks_found = True
                    new_att=m_att[prev_c:]
                    attacker_name=getattr(m,'name','?')
                    attacker_th=getattr(m,'town_hall','?')
                    logger.info(f"Novo(s) ataque(s) {war_type} ID {war_id[-15:]} por {attacker_name}")
                    for att in new_att:
                        if not all(hasattr(att,a) for a in ['defender_tag','stars','destruction']):
                            logger.warning("Ataque dados faltando."); continue

                        defender_tag = att.defender_tag
                        stars=getattr(att,'stars',0)
                        destruction=round(getattr(att,'destruction',0.0),1)
                        star_emojis=("⭐"*stars)+("⚫"*(3-stars)) if stars>=0 else "Erro" # Emojis de estrela

                        # Tenta obter nome e TH do defensor (com fallback e timeout)
                        defender_name = "?"
                        defender_th = "?"
                        try:
                            defender_player = await asyncio.wait_for(coc_client.get_player(defender_tag), timeout=10.0)
                            defender_name = getattr(defender_player, 'name', f'Defensor({defender_tag[-4:]})')
                            defender_th = getattr(defender_player, 'town_hall', '?')
                        except (coc_errors.NotFound, asyncio.TimeoutError):
                            defender_name = f'Defensor({defender_tag[-4:]})'
                        except Exception as e_th:
                            logger.warning(f"Erro buscar dados def {defender_tag}: {e_th}")
                            defender_name = f'Defensor({defender_tag[-4:]})'

                        # --- Criação do Embed para o Ataque ---
                        attack_embed = discord.Embed(
                            title=f"{emojis['war_attack']} Ataque em {war_type}!",
                            color=discord.Color.orange(), # Ou outra cor para ataque
                            timestamp=current_time
                        )
                        attack_embed.add_field(name="Atacante", value=f"`{attacker_name}` (CV{attacker_th})", inline=True)
                        attack_embed.add_field(name="Defensor", value=f"`{defender_name}` (CV{defender_th})", inline=True)
                        attack_embed.add_field(name="Resultado", value=f"**{stars}** {star_emojis}  **{destruction}%** {emojis['destruction']}", inline=False)
                        attack_embed.set_footer(text=f"Guerra vs {getattr(en_c,'name','?')}")

                        try:
                            await channel.send(embed=attack_embed)
                        except Exception as e:
                            logger.error(f"Erro send embed atq: {e}", exc_info=True)
                            # Fallback para texto se embed falhar
                            fallback_msg = (f"{emojis['time']}[{current_time.strftime('%H:%M')}] {emojis['war_attack']}**Ataque {war_type}!**\n"
                                            f"`{attacker_name}`(CV{attacker_th}) vs `{defender_name}`(CV{defender_th})\n"
                                            f"-> {stars}{star_emojis} {destruction}%")
                            try: await channel.send(fallback_msg)
                            except Exception as ef: logger.error(f"Erro send fallback msg atq: {ef}")

                    war_data['attacks'][tag]=curr_c
            if not new_attacks_found: logger.debug(f"{war_type} {war_id[-15:]}: Sem novos ataques.")

            # Lógica de Alertas de Tempo (já usa Embed, mantida)
            end_time_obj = getattr(war,'end_time', None)
            if end_time_obj and hasattr(end_time_obj, 'time'):
                end_time_utc = end_time_obj.time.astimezone(pytz.utc)
                t_left=end_time_utc - datetime.now(pytz.utc);
                h_left=t_left.total_seconds()/3600 if t_left.total_seconds()>0 else 0
                alert_h=[12,6,3,1]
                for h in alert_h:
                    if 'time_alerts' not in war_data: war_data['time_alerts'] = set()
                    if h not in war_data.get('time_alerts',set()) and 0<h_left<=h:
                        war_data['time_alerts'].add(h); logger.info(f"Gerando alerta {h}h {war_type} ID: {war_id[-15:]}")
                        m_list=[]
                        att_per=getattr(war,'attacks_per_member',1)
                        m_alert=getattr(our_c,'members',[])
                        for m in m_alert:
                            used=len(getattr(m,'attacks',[]))
                            left=att_per-used
                            if left>0: m_list.append(f"`{getattr(m,'name','?')}`: **{left}** ataque(s) restante(s)") # Melhoria texto
                        if m_list:
                             # Ajuste no título e descrição do alerta
                             alert_emb=discord.Embed(title=f"{emojis['time']} ALERTA: Restam {h}h na {war_type}!",
                                                     description=f"Atenção! A {war_type} contra **{getattr(en_c,'name','?')}** está acabando.",
                                                     color=discord.Color.orange());
                             alert_emb.timestamp = end_time_obj.time.astimezone(TIMEZONE) # Adiciona timestamp do fim
                             # Usa a função de split adaptada para embeds
                             await send_embeds_splitted(channel, alert_emb, "Ataques Pendentes", m_list, max_len=1024, max_items_per_embed=15);
                             logger.info(f"Alerta {h}h enviado {war_type} ID:{war_id[-15:]}")
                        else:
                            logger.info(f"Alerta {h}h {war_type} ID:{war_id[-15:]} - Todos atacaram.")
                            # Opcional: Enviar msg que todos atacaram
                            all_attacked_embed = discord.Embed(
                                title=f"{emojis['success']} {war_type}: Todos Atacaram!",
                                description=f"Todos os membros realizaram seus ataques na guerra contra **{getattr(en_c,'name','?')}**.",
                                color=discord.Color.green(),
                                timestamp=current_time # Timestamp da verificação
                            )
                            try: await channel.send(embed=all_attacked_embed)
                            except Exception as e: logger.error(f"Erro ao enviar embed 'todos atacaram' (alerta {h}h): {e}")
                        break # Sai do loop de horas após encontrar o primeiro alerta

        # Relatório Final (já usa Embed, mantido)
        rep_key='war_end_reported' if war_type=="Guerra Normal" else 'league_war_end_reported';
        if rep_key not in war_cache: war_cache[rep_key]={}
        if current_state=='warEnded' and war_id not in war_cache.get(rep_key,{}):
             war_cache[rep_key][war_id]=True; logger.info(f"{war_type} ID:{war_id[-15:]} TERMINOU. Relatório.")
             try:
                 our_s=getattr(our_c,'stars',0); en_s=getattr(en_c,'stars',0); our_d=round(getattr(our_c,'destruction',0.0),2); en_d=round(getattr(en_c,'destruction',0.0),2); our_n=getattr(our_c,'name','Nosso Clã'); en_n=getattr(en_c,'name','Oponente');
                 res, emo, col = "EMPATE", emojis['war_tie'], discord.Color.gold()
                 if our_s>en_s or (our_s==en_s and our_d>en_d): res,emo,col="VITÓRIA",emojis['war_win'],discord.Color.green()
                 elif our_s<en_s or (our_s==en_s and our_d<en_d): res,emo,col="DERROTA",emojis['war_lose'],discord.Color.red()
                 end_emb=discord.Embed(title=f"{emo} {war_type.upper()} FINALIZADA: {res}! {emo}", # Título mais descritivo
                                      description=f"Resultado da guerra contra **{en_n}**",
                                      color=col);
                 end_emb.add_field(name=f"{emojis['clan_capital']} {our_n}",value=f"**{our_s}** {emojis['level_up']} ({our_d}%)",inline=True); # Usando estrela emoji
                 end_emb.add_field(name=f"{emojis['war_attack']} {en_n}",value=f"**{en_s}** {emojis['level_up']} ({en_d}%)",inline=True); # Usando estrela emoji
                 end_time_obj = getattr(war,'end_time', None)
                 if end_time_obj and hasattr(end_time_obj, 'time'): end_emb.timestamp = end_time_obj.time.astimezone(TIMEZONE)
                 try: await channel.send(embed=end_emb); await asyncio.sleep(1)
                 except Exception as e: logger.error(f"Erro send embed fim {war_type}: {e}")

                 # Relatório de Ataques Perdidos (já usa Embed, melhorando texto)
                 missed_list=[]
                 att_per=getattr(war,'attacks_per_member',1)
                 m_check_end=getattr(our_c,'members',[])
                 for m in m_check_end:
                     used=len(getattr(m,'attacks',[]))
                     needed=att_per
                     if used<needed:
                         missed=needed-used
                         th=getattr(m,'town_hall','?')
                         name=getattr(m,'name','?')
                         missed_list.append(f"`{name}` (CV{th}): **{missed}** ataque(s) perdido(s)") # Texto mais claro
                 if missed_list:
                     missed_emb=discord.Embed(title=f"{emojis['missed_attack']} Ataques Não Realizados - {war_type}",
                                             description=f"Membros que não usaram todos os ataques contra **{en_n}**:", # Descrição
                                             color=discord.Color.dark_red());
                     if end_time_obj and hasattr(end_time_obj, 'time'): missed_emb.timestamp = end_time_obj.time.astimezone(TIMEZONE) # Timestamp fim
                     await send_embeds_splitted(channel, missed_emb,"Membros", missed_list, max_len=1024, max_items_per_embed=15);
                     logger.info(f"Relatório perdidos enviado {war_type} ID:{war_id[-15:]}")
                 else:
                    # Mensagem "Todos atacaram" agora como Embed
                    msg_ok_embed=discord.Embed(title=f"{emojis['success']} Ataques Completos!",
                                               description=f"Todos os membros atacaram na {war_type} contra **{en_n}**!",
                                               color=discord.Color.green())
                    if end_time_obj and hasattr(end_time_obj, 'time'): msg_ok_embed.timestamp = end_time_obj.time.astimezone(TIMEZONE)
                    try: await channel.send(embed=msg_ok_embed);
                    except Exception as e: logger.error(f"Erro ao enviar embed 'todos atacaram' (final): {e}")
                    logger.info(f"Todos atacaram {war_type} ID:{war_id[-15:]}")
             except Exception as e: logger.error(f"Erro relatório final {war_type} ID {war_id[-15:]}: {e}",exc_info=True)
             # Limpeza do cache (mantida)
             if war_id in war_cache:
                  try: del war_cache[war_id]; logger.info(f"Cache {war_type} ID:{war_id[-15:]} removido.")
                  except KeyError: pass
    except Exception as e: logger.error(f"Erro GERAL check_war_attacks ({war_type}): {e}", exc_info=True)
    # <<< EMBED END >>>

@tasks.loop(minutes=15)
async def check_war():
    global coc_client, war_cache
    if not coc_client: logger.debug("check_war pulado."); return
    try:
        logger.debug("Verificando guerra normal...")
        # <<< EMBED START >>> (Pequeno ajuste no embed de preparação)
        war=await asyncio.wait_for(coc_client.get_current_war(CLAN_TAG),timeout=45.0);
        if not war or getattr(war,'state','notInWar')=='notInWar' or getattr(war,'is_cwl',False):
            logger.debug("Não em guerra normal ou é CWL."); return

        our_c=war.clan if hasattr(war,'clan') and war.clan.tag==CLAN_TAG else getattr(war,'opponent',None);
        en_c=war.opponent if hasattr(war,'clan') and war.clan.tag==CLAN_TAG else getattr(war,'clan',None);
        if not our_c or not en_c: raise AttributeError("Clãs guerra não ID.")
        prep_time_obj = getattr(war,'preparation_start_time', None)
        prep_time_iso = prep_time_obj.time.isoformat() if prep_time_obj and hasattr(prep_time_obj, 'time') else datetime.now().isoformat()
        war_id=f"{getattr(our_c,'tag','?')}-{getattr(en_c,'tag','?')}-{prep_time_iso}";

        if war.state=='preparation':
            if war_id not in war_cache: war_cache[war_id] = {'attacks':{}, 'time_alerts':set(), 'state':'unknown'}
            if war_cache.get(war_id,{}).get('state') != 'preparation':
                logger.info(f"Nova Guerra Normal prep. ID: {war_id[-15:]}")
                war_cache[war_id]['state']='preparation'
                e_n=getattr(en_c,'name','?')
                size=getattr(war,'team_size','?')
                start_time_obj = getattr(war,'start_time', None)
                st_ts = int(start_time_obj.time.astimezone(TIMEZONE).timestamp()) if start_time_obj and hasattr(start_time_obj, 'time') else None
                # Embed de Preparação (ligeiramente melhorado)
                prep_emb=discord.Embed(
                    title=f"{emojis['war_attack']} Preparação de Guerra Iniciada! {emojis['war_attack']}",
                    description=f"**`{getattr(our_c,'name','Nosso Clã')}`** vs **`{e_n}`**\nTamanho: **{size} vs {size}**",
                    color=discord.Color.blue()
                )
                if st_ts:
                    prep_emb.add_field(name="Início da Batalha", value=f"<t:{st_ts}:R> (<t:{st_ts}:F>)", inline=False)
                if start_time_obj and hasattr(start_time_obj, 'time'):
                     prep_emb.timestamp = start_time_obj.time.astimezone(TIMEZONE) # Timestamp do início real da guerra

                chan=bot.get_channel(CHANNEL_ID);
                if chan:
                    try: await chan.send(embed=prep_emb); logger.info(f"Anúncio prep Guerra ID:{war_id[-15:]} enviado.")
                    except Exception as e_send: logger.error(f"Erro send anúncio prep G: {e_send}", exc_info=True)
                else: logger.warning("Canal não encontrado anúncio prep G.")
            else: logger.debug(f"Guerra {war_id[-15:]} já em prep.")
            return # Sai se estiver em preparação

        # Chama a função que agora também lida com embeds para ataques
        await check_war_attacks_and_report(war, war_type="Guerra Normal")
        # <<< EMBED END >>>
    except coc_errors.NotFound: logger.info("Nenhuma guerra normal ativa.")
    except coc_errors.ClashOfClansException as e_coc:
        logger.warning(f"Erro API CoC ({type(e_coc).__name__}) check_war: {e_coc}")
    except asyncio.TimeoutError:
        logger.warning(f"Timeout check_war.")
    except AttributeError as e_atr: logger.error(f"Erro Atributo check_war: {e_atr}", exc_info=True)
    except Exception as e: logger.error(f"Erro GERAL check_war: {e}", exc_info=True)

@tasks.loop(minutes=20)
async def check_league_war():
    global coc_client, war_cache
    if not coc_client: logger.debug("check_league_war pulado."); return
    try:
        logger.debug("Verificando grupo liga...")
        # <<< EMBED START >>> (Pequenos ajustes nos embeds de liga)
        lg=await asyncio.wait_for(coc_client.get_league_group(CLAN_TAG),timeout=60.0);
        if not lg or getattr(lg,'state','notInWar')=="notInWar":
            if war_cache.get('league_start_announced',False): logger.info("Liga fim/saiu. Reset flag."); war_cache['league_start_announced']=False
            logger.debug("Não em guerra liga."); return

        chan=bot.get_channel(CHANNEL_ID);
        if not chan: logger.warning("check_league_war: Canal ID não encontrado."); return

        # Anúncio de Início da Liga (Embed parece OK, talvez adicionar ano à temporada)
        if not war_cache.get('league_start_announced',False):
            war_cache['league_start_announced']=True
            clans=getattr(lg,'clans',[])
            names=[f"- `{getattr(c,'name','?')}` (Nível {getattr(c,'level','?')})" for c in clans] # Adiciona nível do clã
            season=getattr(lg,'season','?') # Formato YYYY-MM
            league_name = getattr(getattr(lg, 'league', None), 'name', 'Liga Desconhecida') # Nome da Liga (ex: Mestre III)
            lg_emb=discord.Embed(
                 title=f"{emojis['league']} CWL Iniciada: {league_name}! {emojis['league']}",
                 description=f"Temporada: **{season}**",
                 color=discord.Color.purple(),
                 timestamp=datetime.now(TIMEZONE) # Timestamp do anúncio
            )
            # Usar send_embeds_splitted para a lista de clãs se for muito longa
            await send_embeds_splitted(chan, lg_emb, "Clãs no Grupo", names, max_len=1024, max_items_per_embed=10)
            logger.info(f"Anúncio Liga temp {season} enviado.")
            # try: await chan.send(embed=lg_emb); logger.info(f"Anúncio Liga temp {season} enviado.")
            # except Exception as e_send: logger.error(f"Erro send anúncio Liga: {e_send}")

        try:
            logger.debug("Buscando guerras liga...")
            all_wars = await asyncio.wait_for(lg.get_wars(CLAN_TAG),timeout=60.0)
            if not all_wars : logger.info("Nenhuma guerra liga encontrada para o clã."); return
        except coc_errors.NotFound: # Tratamento específico se get_wars não encontrar guerras para o *nosso clã* no grupo
            logger.info(f"Nenhuma guerra de liga encontrada para o clã {CLAN_TAG} neste grupo/temporada.")
            return
        except Exception as e: logger.error(f"Erro get_wars liga: {e}"); return

        active_war_found = False
        current_round_war = None # Para guardar a guerra da rodada atual (prep ou inWar)

        # Encontrar a guerra da rodada atual
        for war in all_wars:
             if not war or not all(hasattr(war,a) for a in ['state','preparation_start_time','clan','opponent']):
                 logger.warning(f"Guerra liga inválida encontrada: {war}"); continue
             if war.state in ['inWar', 'preparation']:
                 current_round_war = war
                 break # Encontrou a guerra ativa/preparação

        if current_round_war:
            war = current_round_war # Renomeia para usar o código existente
            active_war_found = True
            try:
                 our_c=war.clan if hasattr(war, 'clan') and war.clan.tag==CLAN_TAG else getattr(war,'opponent', None)
                 en_c=war.opponent if hasattr(war, 'clan') and war.clan.tag==CLAN_TAG else getattr(war,'clan', None)
                 if not our_c or not en_c: logger.error("Erro ID clãs G Liga."); raise ValueError("Clãs inválidos") # Pula para o próximo war se der erro aqui
                 prep_time_obj = getattr(war,'preparation_start_time', None)
                 prep_time_iso = prep_time_obj.time.isoformat() if prep_time_obj and hasattr(prep_time_obj, 'time') else datetime.now().isoformat()
                 war_id=f"league-{getattr(our_c,'tag','?')}-{getattr(en_c,'tag','?')}-{prep_time_iso}";
                 rep_key='league_war_end_reported'
            except Exception as e: logger.error(f"Erro processar dados G Liga: {e}"); active_war_found = False # Marca como não ativa se falhar

            if active_war_found:
                 if rep_key not in war_cache: war_cache[rep_key]={}
                 if war.state=='warEnded' and war_id in war_cache.get(rep_key,{}):
                     logger.debug(f"G Liga {war_id[-15:]} já reportada."); active_war_found = False # Não processa de novo

            if active_war_found and war.state=='preparation':
                 if war_id not in war_cache: war_cache[war_id]={'attacks':{},'time_alerts':set(),'state':'unknown'}
                 if war_cache.get(war_id,{}).get('state')!='preparation':
                     logger.info(f"Nova G Liga prep. ID: {war_id[-15:]}")
                     war_cache[war_id]['state']='preparation'
                     start_time_obj = getattr(war,'start_time', None)
                     st_ts = int(start_time_obj.time.astimezone(TIMEZONE).timestamp()) if start_time_obj and hasattr(start_time_obj, 'time') else None

                     # Identificar rodada (pode ser impreciso se API não der)
                     round_n = "?"
                     # Tentar inferir a rodada baseado nas guerras finalizadas? Complexo. Deixar "?" por enquanto.

                     # Embed de Preparação da Liga (melhorado)
                     prep_emb=discord.Embed(
                         title=f"{emojis['league']} Preparação CWL (Rodada {round_n}) {emojis['league']}",
                         description=f"**`{getattr(our_c,'name','Nosso Clã')}`** vs **`{getattr(en_c,'name','Oponente')}`**",
                         color=discord.Color.blue()
                     )
                     if st_ts:
                         prep_emb.add_field(name="Início da Batalha", value=f"<t:{st_ts}:R> (<t:{st_ts}:F>)", inline=False)
                     if start_time_obj and hasattr(start_time_obj, 'time'):
                          prep_emb.timestamp = start_time_obj.time.astimezone(TIMEZONE) # Timestamp do início real

                     try: await chan.send(embed=prep_emb); logger.info(f"Anúncio prep Liga ID:{war_id[-15:]} enviado.")
                     except Exception as e_send: logger.error(f"Erro send anúncio prep Liga: {e_send}", exc_info=True)
                 else: logger.debug(f"G Liga {war_id[-15:]} já em prep.")

            elif active_war_found: # Se não está em 'preparation', deve estar em 'inWar' ou 'warEnded' (e não reportada)
                 logger.debug(f"Chamando check_attacks para Liga ID:{war_id[-15:]} (Estado: {war.state})")
                 await check_war_attacks_and_report(war, war_type="Guerra de Liga")

        else: # Se não encontrou guerra em 'inWar' ou 'preparation'
             # Verifica se a última guerra já terminou e precisa ser reportada (caso a task rode bem na hora da transição)
             ended_but_not_reported = []
             for war in all_wars:
                 if not war or not all(hasattr(war,a) for a in ['state','preparation_start_time','clan','opponent']): continue
                 if war.state == 'warEnded':
                     try:
                         our_c=war.clan if hasattr(war, 'clan') and war.clan.tag==CLAN_TAG else getattr(war,'opponent', None)
                         en_c=war.opponent if hasattr(war, 'clan') and war.clan.tag==CLAN_TAG else getattr(war,'clan', None)
                         if not our_c or not en_c: continue
                         prep_time_obj = getattr(war,'preparation_start_time', None)
                         prep_time_iso = prep_time_obj.time.isoformat() if prep_time_obj and hasattr(prep_time_obj, 'time') else datetime.now().isoformat()
                         war_id=f"league-{getattr(our_c,'tag','?')}-{getattr(en_c,'tag','?')}-{prep_time_iso}";
                         rep_key='league_war_end_reported'
                         if rep_key not in war_cache: war_cache[rep_key]={}
                         if war_id not in war_cache.get(rep_key,{}):
                             ended_but_not_reported.append(war)
                     except Exception as e_check_ended:
                         logger.error(f"Erro ao verificar guerra finalizada da liga: {e_check_ended}")

             if ended_but_not_reported:
                  logger.info(f"Encontrada(s) {len(ended_but_not_reported)} guerra(s) de liga finalizada(s) e não reportada(s).")
                  for war in ended_but_not_reported:
                       await check_war_attacks_and_report(war, war_type="Guerra de Liga") # Chama para reportar
             else:
                 logger.info("Nenhuma G Liga ativa (prep/inWar) ou pendente de relatório encontrada.")
        # <<< EMBED END >>>
    except coc_errors.NotFound:
         if war_cache.get('league_start_announced',False): logger.info("Grupo liga não encontrado. Reset flag."); war_cache['league_start_announced']=False
         logger.info("Clã não em Grupo Liga.")
    except coc_errors.ClashOfClansException as e_coc:
        logger.warning(f"Erro API CoC ({type(e_coc).__name__}) check_lg_war: {e_coc}")
    except asyncio.TimeoutError:
         logger.warning(f"Timeout check_lg_war.")
    except Exception as e: logger.error(f"Erro GERAL check_lg_war: {e}",exc_info=True); war_cache['league_start_announced']=False

@tasks.loop(hours=1)
async def check_raid_weekend():
    # <<< EMBED START >>> (Melhorias nos embeds de início e progresso)
    global raid_weekend_cache, coc_client
    if not coc_client:
        logger.debug("check_raid_weekend pulado: cliente CoC inválido/não inicializado.")
        return
    try:
        logger.debug("Verificando Raid Weekend...")
        rl=await asyncio.wait_for(coc_client.get_clan_capital_raid_seasons(CLAN_TAG, limit=1), timeout=45.0)

        channel=bot.get_channel(CHANNEL_ID)
        if not channel: logger.warning("check_raid_weekend: Canal ID não encontrado."); return

        if not rl:
             cached=raid_weekend_cache.get('current_raid');
             if cached and cached.get('state') in ['ongoing', 'ended_due_to_api_error']:
                  logger.warning("API não retornou raids, mas cache indica ongoing/erro.");
                  raid_weekend_cache['current_raid']['state']='ended_due_to_api_error'
                  # Opcional: Enviar mensagem de erro?
                  # error_embed = discord.Embed(title=f"{emojis['error']} Erro ao buscar Raid Weekend",
                  #                             description="Não foi possível obter dados da API, mas um Raid estava em andamento.",
                  #                             color=discord.Color.dark_red(), timestamp=datetime.now(TIMEZONE))
                  # try: await channel.send(embed=error_embed)
                  # except Exception as e: logger.error(f"Erro ao enviar embed de erro da raid: {e}")
             else: logger.info("Nenhum dado Raid Weekend na API.")
             return

        curr_r=rl[0];
        if not curr_r or not all(hasattr(curr_r,a) for a in ['start_time','state','capital_total_loot']):
            logger.error(f"Objeto Raid inválido: {curr_r}"); return

        current_time = datetime.now(TIMEZONE)
        start_time_obj = getattr(curr_r, 'start_time', None)
        r_id = f"{CLAN_TAG}-{start_time_obj.time.isoformat()}" if start_time_obj and hasattr(start_time_obj, 'time') else f"{CLAN_TAG}-unknown_start"
        cached=raid_weekend_cache.get('current_raid')
        prev_id=cached['id'] if cached else None
        prev_state=cached['state'] if cached else None
        clan_name_cache = getattr(await get_clan_data(), 'name', CLAN_TAG) # Cache nome clã p/ rodapé

        async def send_raid_report(raid_data, title_emoji, title_text, color, report_type="final"):
            # Função auxiliar já usa Embed, adicionando timestamp e footer
            start_str = raid_data.get('start_time_str','N/A')
            loot = raid_data.get('total_loot',0)
            state = raid_data.get('state','N/A').capitalize() # Capitaliza 'ongoing'/'ended'
            attacks = raid_data.get('total_attacks', '?') # Pega total de ataques se disponível no cache
            dist_destroyed = raid_data.get('districts_destroyed', '?') # Pega distritos destruídos

            report_time = raid_data.get('end_time', datetime.now(TIMEZONE)) if report_type == "final" else datetime.now(TIMEZONE)

            emb = discord.Embed(
                 title=f"{title_emoji} {title_text} {title_emoji}",
                 description=f"**Início:** {start_str}\n**Estado:** {state}",
                 color=color,
                 timestamp=report_time
             )
            emb.add_field(name=f"{emojis['clan_capital']} Ouro Total", value=f"**{loot:,}**", inline=True)
            emb.add_field(name=f"{emojis['war_attack']} Ataques Usados", value=f"{attacks}", inline=True)
            emb.add_field(name=f"{emojis['destruction']} Distritos Destruídos", value=f"{dist_destroyed}", inline=True)

            members_data = raid_data.get('members',{})
            if members_data:
                try:
                    # Tentar pegar nomes atuais (pode falhar se membro saiu)
                    clan_now = await get_clan_data(timeout=15) # Timeout menor
                    m_map = {m.tag:m.name for m in getattr(clan_now,'members',[]) if hasattr(m,'tag')} if clan_now else {}
                except Exception: m_map = {}

                # Usa nome do cache da raid se não encontrar no clã atual
                sorted_members = sorted(members_data.items(), key=lambda i:i[1].get('loot', 0), reverse=True)
                top_list = [
                    f"{i}. `{m_map.get(tag, data.get('name','?'))}`: **{data.get('loot',0):,}**"
                    for i, (tag, data) in enumerate(sorted_members[:10], 1) # Top 10
                ]
                if top_list:
                    # Usar send_embeds_splitted se a lista for longa
                    field_title = f"🌟 Top Contribuições ({report_type.capitalize()}) 🌟"
                    if len("\n".join(top_list)) > 1024:
                         await send_embeds_splitted(channel, emb, field_title, top_list, max_len=1024, max_items_per_embed=10)
                         # O embed base já foi enviado pela função splitted, então retornamos
                         return
                    else:
                         emb.add_field(name=field_title, value="\n".join(top_list), inline=False)

            emb.set_footer(text=f"Clã: {clan_name_cache}")

            try:
                # A função splitted já envia, então só enviamos se não foi dividida
                if not (members_data and len("\n".join(top_list)) > 1024):
                    await channel.send(embed=emb)
            except Exception as e:
                logger.error(f"Erro send embed relatório raid {report_type}: {e}", exc_info=True)


        # Lógica principal do check_raid_weekend
        if r_id != prev_id:
            logger.info(f"Novo Raid ID: {r_id}. Anterior: {prev_id}")
            if prev_id and prev_state in ['ongoing', 'ended_due_to_api_error']:
                logger.info(f"Raid anterior ({prev_id}) '{prev_state}'. Gerando relatório presumido.")
                # Atualiza dados do cache antigo com o que tivermos antes de reportar
                cached['state'] = 'ended (presumed)'
                cached['end_time'] = current_time # Marca hora atual como fim presumido
                await send_raid_report(cached, emojis['warning'], "RAID ANTERIOR FINALIZADA (Presumido)", discord.Color.dark_grey(), report_type="presumido")

            # Inicializa cache para a nova raid
            start_time_str = start_time_obj.time.astimezone(TIMEZONE).strftime('%d/%m/%Y %H:%M') if start_time_obj and hasattr(start_time_obj, 'time') else "N/A"
            members_dict = {m.tag:{'name':getattr(m,'name','?'),'loot':getattr(m,'capital_resources_looted',0)} for m in getattr(curr_r,'members',[]) if hasattr(m,'tag')}
            districts_dict = {d.id:{'name':getattr(d,'name','?'),'destruction':getattr(d,'destruction_percent',0)} for d in getattr(curr_r,'attack_log',[]) if hasattr(d,'id')} # Usar attack_log para distritos atacados
            raid_weekend_cache['current_raid'] = {
                'id': r_id,
                'start_time': start_time_obj,
                'start_time_str': start_time_str,
                'state': curr_r.state,
                'members': members_dict,
                'districts': districts_dict, # Armazena estado inicial dos distritos
                'total_loot': getattr(curr_r,'capital_total_loot',0),
                'total_attacks': getattr(curr_r, 'total_attacks', 0), # Armazena ataques iniciais
                'districts_destroyed': getattr(curr_r, 'districts_destroyed', 0) # Armazena distritos destruídos iniciais
            };
            logger.info(f"Cache raid ID: {r_id}, Estado: {curr_r.state}")

            if curr_r.state == 'ongoing':
                # Embed de início de Raid
                end_time_obj = getattr(curr_r, 'end_time', None) # Pega fim estimado
                end_ts = int(end_time_obj.time.astimezone(TIMEZONE).timestamp()) if end_time_obj and hasattr(end_time_obj, 'time') else None

                start_embed=discord.Embed(
                    title=f"{emojis['raid']} Raid Weekend Iniciado! {emojis['raid']}",
                    description=f"Preparem seus ataques na Capital do Clã!",
                    color=discord.Color.red(), # Vermelho para início/ação
                    timestamp=start_time_obj.time.astimezone(TIMEZONE) if start_time_obj else current_time
                )
                start_embed.add_field(name="Início", value=start_time_str, inline=True)
                if end_ts:
                     start_embed.add_field(name="Término Previsto", value=f"<t:{end_ts}:R>", inline=True)
                start_embed.set_footer(text=f"Clã: {clan_name_cache}")

                try: await channel.send(embed=start_embed); logger.info(f"Anúncio início Raid ID:{r_id} enviado.")
                except Exception as e: logger.error(f"Erro send anúncio início Raid: {e}", exc_info=True)

        elif r_id == prev_id: # Mesma Raid, verificar mudanças
            logger.debug(f"Mesmo Raid ID: {r_id}. API: {curr_r.state}, Cache: {prev_state}")
            current_raid_data = raid_weekend_cache['current_raid']

            # Transição para 'ended'
            if prev_state != 'ended' and curr_r.state == 'ended':
                logger.info(f"Raid {r_id} terminou. Gerando relatório final.")
                # Atualiza cache com dados finais
                current_raid_data['state'] = 'ended'
                current_raid_data['total_loot'] = getattr(curr_r,'capital_total_loot', current_raid_data.get('total_loot',0));
                current_raid_data['members'] = {m.tag:{'name':getattr(m,'name','?'),'loot':getattr(m,'capital_resources_looted',0)} for m in getattr(curr_r,'members',[]) if hasattr(m,'tag')};
                # Pega dados finais dos distritos (se API fornecer no final)
                # current_raid_data['districts'] = {d.id:{'name':getattr(d,'name','?'),'destruction':getattr(d,'destruction_percent',0)} for d in getattr(curr_r,'defense_log',[]) if hasattr(d,'id')} # defense_log pode ter info final? verificar API
                current_raid_data['total_attacks'] = getattr(curr_r, 'total_attacks', current_raid_data.get('total_attacks', '?'))
                current_raid_data['districts_destroyed'] = getattr(curr_r, 'districts_destroyed', current_raid_data.get('districts_destroyed', '?'))
                current_raid_data['end_time'] = getattr(curr_r, 'end_time', None).time.astimezone(TIMEZONE) if getattr(curr_r, 'end_time', None) else current_time

                await send_raid_report(current_raid_data, emojis['clan_capital'], "RAID WEEKEND FINALIZADO!", discord.Color.dark_grey(), report_type="final")
                logger.info(f"Relatório final Raid ID:{r_id} enviado.")

            # Transição de 'ended' para 'ongoing' (Incomum, mas tratar)
            elif prev_state == 'ended' and curr_r.state == 'ongoing':
                 logger.warning(f"Raid {r_id}: Estado mudou de 'ended' para 'ongoing'.")
                 current_raid_data['state'] = 'ongoing' # Atualiza cache
                 restart_embed=discord.Embed(
                      title=f"{emojis['warning']} Raid Weekend Reiniciado?",
                      description=f"O estado da Raid Weekend (ID: ...{r_id[-10:]}) mudou de finalizado para em andamento.",
                      color=discord.Color.orange(),
                      timestamp=current_time
                 )
                 restart_embed.set_footer(text=f"Clã: {clan_name_cache}")
                 try: await channel.send(embed=restart_embed);
                 except Exception as e: logger.error(f"Erro send anúncio reinício Raid: {e}", exc_info=True)

            # Raid continua 'ongoing', verificar progresso
            elif curr_r.state == 'ongoing':
                logger.debug(f"Raid {r_id} ongoing. Verificando progresso.")
                loot_changes = []
                district_changes = []
                progress_found = False

                # Verificar Loot dos Membros
                new_member_state = {}
                cached_members = current_raid_data.get('members', {})
                try: # Pega nomes atuais para exibição
                    clan_now = await get_clan_data(timeout=15); m_map = {m.tag:m.name for m in getattr(clan_now,'members',[]) if hasattr(m,'tag')} if clan_now else {}
                except Exception: m_map = {}

                for m in getattr(curr_r, 'members', []):
                    tag = getattr(m, 'tag', None)
                    if not tag: continue
                    current_loot = getattr(m, 'capital_resources_looted', 0)
                    member_name = getattr(m, 'name', '?')
                    new_member_state[tag] = {'name': member_name, 'loot': current_loot}
                    previous_loot = cached_members.get(tag, {'loot': 0})['loot']
                    loot_diff = current_loot - previous_loot
                    if loot_diff > 0:
                        progress_found = True
                        display_name = m_map.get(tag, member_name) # Usa nome atual se possível
                        loot_changes.append(f"{emojis['raid']} `{display_name}` +**{loot_diff:,}** (Total: {current_loot:,})")

                # Verificar Distritos Destruídos
                new_district_state = {}
                cached_districts = current_raid_data.get('districts', {})
                # Usar attack_log para ver distritos atacados/destruídos na raid atual
                for district_log in getattr(curr_r, 'attack_log', []):
                    if not all(hasattr(district_log, a) for a in ['id', 'name', 'destruction_percent']): continue
                    d_id = district_log.id
                    d_name = getattr(district_log, 'name', '?')
                    current_destruction = getattr(district_log, 'destruction_percent', 0)
                    new_district_state[d_id] = {'name': d_name, 'destruction': current_destruction}
                    previous_destruction = cached_districts.get(d_id, {'destruction': 0})['destruction']

                    if current_destruction == 100 and previous_destruction < 100:
                        progress_found = True
                        district_changes.append(f"{emojis['destruction']} Distrito **{d_name}** destruído (100%)!")

                # Enviar Embed de Progresso se houver mudanças
                if progress_found:
                    logger.info(f"Progresso detectado Raid {r_id}: {len(loot_changes)} loot, {len(district_changes)} distritos.")
                    progress_embed = discord.Embed(
                        title=f"{emojis['progress']} Progresso da Raid Weekend",
                        color=discord.Color.teal(), # Cor para progresso
                        timestamp=current_time
                    )
                    # Adiciona campos separados para loot e distritos se houver
                    if loot_changes:
                        loot_text = "\n".join(loot_changes)
                        if len(loot_text) <= 1024:
                             progress_embed.add_field(name=f"{emojis['clan_capital']} Ouro Coletado", value=loot_text, inline=False)
                        else:
                             # Se muito longo, apenas indica que houve e loga (ou usa split)
                             progress_embed.add_field(name=f"{emojis['clan_capital']} Ouro Coletado", value=f"{len(loot_changes)} membros contribuíram (lista longa no log).", inline=False)
                             logger.debug(f"Loot changes (Raid {r_id}):\n{loot_text}")


                    if district_changes:
                        district_text = "\n".join(district_changes)
                        # Campo de distrito é geralmente curto
                        progress_embed.add_field(name=f"{emojis['destruction']} Distritos Destruídos", value=district_text, inline=False)

                    # Adiciona informações gerais
                    current_total_loot = getattr(curr_r,'capital_total_loot',0)
                    current_attacks = getattr(curr_r, 'total_attacks', '?')
                    current_dist_destroyed = getattr(curr_r, 'districts_destroyed', '?')
                    progress_embed.add_field(name="Status Geral", value=f"Ouro Total: **{current_total_loot:,}**\nAtaques: {current_attacks}\nDistritos: {current_dist_destroyed}", inline=False)

                    progress_embed.set_footer(text=f"Clã: {clan_name_cache}")

                    try:
                        await channel.send(embed=progress_embed)
                    except Exception as e:
                        logger.error(f"Erro send embed progresso raid: {e}", exc_info=True)

                    # Atualizar cache com os novos estados
                    current_raid_data['members'] = new_member_state
                    current_raid_data['districts'] = new_district_state
                    current_raid_data['total_loot'] = current_total_loot
                    current_raid_data['total_attacks'] = current_attacks
                    current_raid_data['districts_destroyed'] = current_dist_destroyed
                else:
                    logger.debug(f"Raid {r_id} ongoing, sem progresso detectado nesta verificação.")
            else: # Outros estados (ex: ended_due_to_api_error)
                logger.info(f"Raid {r_id} em estado '{curr_r.state}' (cache era '{prev_state}'). Nenhuma ação específica.")

    except coc_errors.ClashOfClansException as e_coc:
        logger.warning(f"Erro API CoC ({type(e_coc).__name__}) check_raid: {e_coc}")
    except asyncio.TimeoutError:
         logger.warning(f"Timeout check_raid.")
    except Exception as e:
        logger.error(f"Erro GERAL check_raid: {e}", exc_info=True);
    # <<< EMBED END >>>


# --- Eventos e Comandos ---

@bot.event
async def on_ready():
    # <<< EMBED START >>> (Mensagens de status/erro no on_ready)
    global coc_client
    logger.info(f'Bot {bot.user.name} ({bot.user.id}) online e pronto!')
    logger.info(f"Monitorando Clã: {CLAN_TAG} | Canal ID: {CHANNEL_ID}")
    channel = bot.get_channel(CHANNEL_ID)
    start_time = datetime.now(TIMEZONE)

    if not channel:
        logger.error(f"Canal ID {CHANNEL_ID} NÃO ENCONTRADO.")
        # Não pode enviar mensagem se o canal não existe

    logger.info("Tentando inicializar e logar cliente CoC...")
    login_successful = await initialize_coc_client()

    if not login_successful:
        logger.critical("Falha login CoC. API indisponível.")
        if channel:
            error_embed = discord.Embed(
                title=f"{emojis['error']} Erro Crítico na Inicialização",
                description="**Falha ao autenticar com a API do Clash of Clans.**\n"
                            "As funcionalidades relacionadas ao jogo (monitoramento, comandos CoC) estarão indisponíveis.\n"
                            "Verifique as credenciais `COC_EMAIL` e `COC_PASSWORD`.",
                color=discord.Color.dark_red(),
                timestamp=start_time
            )
            try:
                await channel.send(embed=error_embed)
            except Exception as e_send_err:
                logger.error(f"Erro ao enviar embed (falha login CoC) para canal {CHANNEL_ID}: {e_send_err}")
        logger.warning("Bot rodando apenas com funcionalidades básicas do Discord.")
    else:
        logger.info("Cliente CoC OK. Verificando acesso ao clã...")
        try:
            clan_test = await get_clan_data();
            if clan_test:
                clan_name = getattr(clan_test,'name',CLAN_TAG)
                logger.info(f"Acesso API CoC e clã '{clan_name}' OK.")
                task_list = [check_donations, check_members, check_war, check_league_war, check_raid_weekend];
                start_log = []
                logger.info("Iniciando tasks monitoramento...")
                for task in task_list:
                    task_name = task.coro.__name__
                    if not task.is_running():
                        try: task.start(); start_log.append(f"{task_name}: Iniciada {emojis['success']}"); logger.debug(f"Task '{task_name}' iniciada.")
                        except RuntimeError as e_task: logger.error(f"Erro start task {task_name}: {e_task}"); start_log.append(f"{task_name}: Erro Start {emojis['error']}")
                    else: start_log.append(f"{task_name}: Já Rodando {emojis['warning']}"); logger.warning(f"Task '{task_name}' já rodando.")

                status_tasks = "\n".join(f"- {s}" for s in start_log)
                logger.info(f"Status inicialização tasks: {'; '.join(start_log)}.")

                if channel:
                    online_embed = discord.Embed(
                         title=f"{emojis['success']} Bot Online e Monitorando!",
                         description=f"Monitoramento do clã **{clan_name}** (`{CLAN_TAG}`) iniciado.",
                         color=discord.Color.green(),
                         timestamp=start_time
                    )
                    online_embed.add_field(name="Status das Tarefas", value=status_tasks if status_tasks else "Nenhuma tarefa iniciada.", inline=False)
                    online_embed.set_footer(text=f"Bot: {bot.user.name}")
                    try:
                        await channel.send(embed=online_embed)
                    except Exception as e_send_err:
                         logger.error(f"Erro ao enviar embed (online) para canal {CHANNEL_ID}: {e_send_err}")
                else: logger.info("Inicialização completa (sem canal para mensagem de status).")
            else:
                # Falha ao obter dados do clã *depois* do login CoC
                logger.critical(f"FALHA GRAVE: Login CoC OK, mas não foi possível obter dados do clã {CLAN_TAG}.")
                if channel:
                    error_embed = discord.Embed(
                        title=f"{emojis['error']} Erro Crítico na Inicialização",
                        description=f"**Falha ao obter dados do clã `{CLAN_TAG}` após login na API.**\n"
                                    "Verifique se a TAG do clã está correta e se o bot tem permissão para vê-lo.\n"
                                    "Funcionalidades podem estar comprometidas.",
                        color=discord.Color.dark_red(),
                        timestamp=start_time
                    )
                    try:
                        await channel.send(embed=error_embed)
                    except Exception as e_send_err:
                        logger.error(f"Erro ao enviar embed (falha obter clã) para canal {CHANNEL_ID}: {e_send_err}")
        except Exception as e_ready_get:
             logger.critical(f"FALHA GRAVE: Erro inesperado ao verificar clã no on_ready: {e_ready_get}", exc_info=True)
             if channel:
                 error_embed = discord.Embed(
                        title=f"{emojis['error']} Erro Crítico na Inicialização",
                        description=f"**Ocorreu um erro inesperado ao verificar o clã durante a inicialização.**\n"
                                    f"Erro: `{e_ready_get}`\n"
                                    "Verifique os logs para mais detalhes.",
                        color=discord.Color.dark_red(),
                        timestamp=start_time
                    )
                 try:
                     await channel.send(embed=error_embed)
                 except Exception as e_send_err:
                     logger.error(f"Erro ao enviar embed (erro API on_ready) para canal {CHANNEL_ID}: {e_send_err}")
    # <<< EMBED END >>>


@bot.event
async def on_command_error(ctx, error):
    # <<< EMBED START >>> (Melhorar mensagens de erro dos comandos)
    error_handled = False
    error_embed = discord.Embed(color=discord.Color.red(), timestamp=datetime.now(TIMEZONE))
    error_embed.set_footer(text=f"Comando: {ctx.command.name if ctx.command else 'N/A'}")

    if isinstance(error, commands.CommandNotFound):
        # Ignora comando não encontrado silenciosamente
        # error_embed.title = f"{emojis['warning']} Comando Não Encontrado"
        # error_embed.description = f"O comando `{ctx.invoked_with}` não existe."
        # await ctx.send(embed=error_embed, delete_after=10) # Apaga rápido
        return # Não faz nada
    elif isinstance(error, commands.MissingRequiredArgument):
        error_handled = True
        error_embed.title = f"{emojis['error']} Argumento Faltando"
        error_embed.description = f"O argumento obrigatório `{error.param.name}` não foi fornecido."
    elif isinstance(error, commands.MissingPermissions):
        error_handled = True
        error_embed.title = f"{emojis['error']} Permissão Negada"
        error_embed.description = f"Você não tem a(s) permissão(ões) necessária(s): `{', '.join(error.missing_permissions)}`."
    elif isinstance(error, commands.ChannelNotFound):
        error_handled = True
        error_embed.title = f"{emojis['error']} Canal Não Encontrado"
        error_embed.description = f"O canal `{error.argument}` não foi encontrado."
    elif isinstance(error, commands.CommandInvokeError):
         error_handled = True
         original = error.original
         logger.error(f"Erro ao invocar comando '{ctx.command}': {original}", exc_info=True)
         error_embed.title = f"{emojis['error']} Erro na Execução do Comando"

         if isinstance(original, coc_errors.NotFound):
             error_embed.description = f"Erro na API CoC: Recurso não encontrado (verifique a tag informada)."
         elif isinstance(original, coc_errors.AuthenticationError):
             error_embed.description = f"Erro na API CoC: Falha na autenticação. O bot pode estar deslogado."
         elif isinstance(original, coc_errors.Maintenance):
              error_embed.description = f"{emojis['warning']} API CoC em Manutenção. Tente novamente mais tarde."
              error_embed.color = discord.Color.orange()
         elif isinstance(original, coc_errors.ClashOfClansException):
             error_embed.description = f"{emojis['warning']} Erro na API CoC: `{type(original).__name__}`. Consulte os logs para detalhes."
             error_embed.color = discord.Color.orange()
         elif isinstance(original, asyncio.TimeoutError):
             error_embed.description = f"{emojis['error']} Erro: Tempo limite excedido ao contatar a API CoC."
         elif not coc_client:
             error_embed.description = f"{emojis['error']} Erro: A conexão com a API CoC não está ativa no momento."
         else:
             error_embed.description = f"Ocorreu um erro inesperado ao executar o comando.\nErro: `{original}`"
    elif isinstance(error, commands.CheckFailure): # Ex: Falha no has_permissions
        error_handled = True
        error_embed.title = f"{emojis['error']} Acesso Negado"
        error_embed.description = f"Você não tem permissão para usar este comando."
    elif isinstance(error, commands.BadArgument):
        error_handled = True
        error_embed.title = f"{emojis['error']} Argumento Inválido"
        error_embed.description = f"Um dos argumentos fornecidos é inválido. Verifique o tipo esperado (ex: texto, número, #tag)."
        # Tentar ser mais específico se possível?
        # if hasattr(error, 'param'): error_embed.description += f"\nArgumento problemático: `{error.param.name}`"

    if error_handled:
        try:
            await ctx.send(embed=error_embed)
        except Exception as e_send:
             logger.error(f"Erro ao enviar embed de erro de comando: {e_send}")
    else:
        # Erro não tratado especificamente
        logger.error(f"Erro de comando não tratado: {type(error).__name__} - {error}", exc_info=True)
        error_embed.title = f"{emojis['error']} Erro Inesperado no Comando"
        error_embed.description = f"Ocorreu um erro inesperado.\nTipo: `{type(error).__name__}`\nDetalhe: `{error}`\nPor favor, reporte se persistir."
        try:
            await ctx.send(embed=error_embed)
        except Exception as e_send:
             logger.error(f"Erro ao enviar embed de erro de comando não tratado: {e_send}")
    # <<< EMBED END >>>


# --- Comandos --- (Os comandos já usam Embeds, mas revisando alguns textos/layouts)

async def display_attacks_remaining(ctx, war, war_type="Guerra"):
    # Função auxiliar para !ataques e !ligaataques (Já usa embed, melhorias)
    if not war or war.state not in ['inWar', 'preparation']:
        await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} O clã não está em uma {war_type} ativa ou em preparação.", color=discord.Color.orange())); return
    if not coc_client:
        await ctx.send(embed=discord.Embed(description=f"{emojis['error']} A API do CoC está indisponível no momento.", color=discord.Color.red())); return

    our_c = war.clan if hasattr(war,'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'opponent', None)
    en_c = war.opponent if hasattr(war,'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'clan', None)
    if not our_c or not en_c:
        await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro ao identificar os clãs participantes da {war_type}.", color=discord.Color.red())); return

    state_info = ""
    time_ref = None
    color = discord.Color.blue()
    timestamp = datetime.now(TIMEZONE)

    if war.state == 'preparation' and hasattr(war, 'start_time') and hasattr(war.start_time, 'time'):
        time_ref = war.start_time.time.astimezone(TIMEZONE)
        state_info = f"**Estado:** Preparação\n**Início da Batalha:** <t:{int(time_ref.timestamp())}:R>"
        timestamp = time_ref # Usa o timestamp do início
    elif war.state == 'inWar' and hasattr(war, 'end_time') and hasattr(war.end_time, 'time'):
        time_ref = war.end_time.time.astimezone(TIMEZONE)
        state_info = f"**Estado:** Em Guerra\n**Término:** <t:{int(time_ref.timestamp())}:R>"
        color = discord.Color.orange()
        timestamp = time_ref # Usa o timestamp do fim

    attacks_per_member = getattr(war, 'attacks_per_member', 1)
    remaining_list = []
    total_attacks_possible = 0
    total_attacks_done = 0

    members_in_war = getattr(our_c, 'members', [])
    if not members_in_war:
        await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} Lista de membros da {war_type} indisponível.", color=discord.Color.orange())); return

    for member in members_in_war:
        total_attacks_possible += attacks_per_member
        attacks_done = len(getattr(member, 'attacks', []));
        total_attacks_done += attacks_done
        attacks_left = attacks_per_member - attacks_done
        if attacks_left > 0:
            name = getattr(member, 'name', '?');
            th = getattr(member, 'town_hall', '?');
            map_pos = getattr(member, 'map_position', '?') # Posição no mapa
            remaining_list.append(f"{map_pos}. `{name}` (CV{th}): **{attacks_left}** atk(s)")

    title = f"{emojis['war_attack']} Ataques Restantes - {war_type} vs {getattr(en_c, 'name', '?')}"
    base_embed = discord.Embed(title=title, description=state_info, color=color, timestamp=timestamp)
    base_embed.set_footer(text=f"Clã: {getattr(our_c, 'name', '?')}")

    attacks_summary = f"**{total_attacks_done} / {total_attacks_possible}** ataques realizados."
    base_embed.add_field(name="Resumo de Ataques", value=attacks_summary, inline=False)

    if not remaining_list:
        base_embed.add_field(name="Situação", value=f"{emojis['success']} Todos os ataques foram realizados!", inline=False)
        base_embed.color = discord.Color.green() # Muda cor para verde
        await ctx.send(embed=base_embed)
    else:
        # Usa a função de split adaptada
        await send_embeds_splitted(ctx.channel, base_embed, "Membros com Ataques Pendentes", remaining_list, max_len=1024, max_items_per_embed=15)

@bot.command(name='status', help="Exibe status atual bot e clã.")
@commands.has_permissions(administrator=True)
async def status_command(ctx):
    # Comando já usa Embed, apenas pequenas melhorias visuais/texto
    if not coc_client: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red)); return
    async with ctx.typing():
        try:
            clan=await get_clan_data();
            if not clan: await ctx.send(embed=discord.Embed(description=f"{emojis['error']}Erro ao obter dados do clã `{CLAN_TAG}`!", color=discord.Color.red)); return

            c_n=getattr(clan,'name','?')
            c_t=getattr(clan,'tag',CLAN_TAG)
            c_desc=getattr(clan,'description',"Sem descrição") or "Sem descrição"
            c_lvl=getattr(clan,'level','?')
            m_cnt=getattr(clan,'member_count','?')
            m_max=getattr(clan,'max_members', 50) # Pega o max_members real se disponível
            loc=getattr(getattr(clan,'location',None),'name',"Global")
            c_pts=getattr(clan,'points','?')
            c_pts_vs=getattr(clan,'versus_points','?') # Troféus da base construtor
            w_lg=getattr(getattr(clan,'war_league',None),'name',"Nenhuma")
            cap_lg=getattr(getattr(clan,'capital_league',None),'name',"Nenhuma")
            b_url=getattr(getattr(clan,'badge',None),'url',None)

            emb=discord.Embed(title=f"{emojis['info']} Status: {c_n} ({c_t})",description=f"_{c_desc}_",color=discord.Color.blue());
            if b_url: emb.set_thumbnail(url=b_url)
            emb.add_field(name="Nível",value=str(c_lvl),inline=True);
            emb.add_field(name="Membros",value=f"{m_cnt}/{m_max}",inline=True);
            emb.add_field(name="Local",value=loc,inline=True);
            emb.add_field(name="Troféus Vila",value=f"{c_pts:,}{emojis['trophy']}",inline=True);
            emb.add_field(name="Troféus Constr.",value=f"{c_pts_vs:,}{emojis['trophy']}",inline=True); # Troféus construtor
            emb.add_field(name="Liga Guerra",value=w_lg,inline=True);
            emb.add_field(name="Liga Capital",value=cap_lg,inline=True);

            # --- Status Guerra Normal ---
            ws = f"{emojis['warning']} Verificando..."
            try:
                war = await asyncio.wait_for(coc_client.get_current_war(CLAN_TAG), timeout=30.0)
                if not war or getattr(war,'state', 'notInWar') == 'notInWar' or getattr(war, 'is_cwl', False):
                    ws = f"{emojis['success']} Não está em Guerra Normal."
                else:
                    state = war.state
                    opp = getattr(war, 'opponent', None)
                    our_w = getattr(war, 'clan', None)
                    if opp and our_w and our_w.tag == CLAN_TAG:
                        opp_n = getattr(opp, 'name', '?')
                        our_s = getattr(our_w, 'stars', 0)
                        opp_s = getattr(opp, 'stars', 0)
                        start_time_obj = getattr(war, 'start_time', None); end_time_obj = getattr(war, 'end_time', None)
                        st_ts = int(start_time_obj.time.astimezone(TIMEZONE).timestamp()) if start_time_obj and hasattr(start_time_obj, 'time') else None
                        et_ts = int(end_time_obj.time.astimezone(TIMEZONE).timestamp()) if end_time_obj and hasattr(end_time_obj, 'time') else None

                        if state == 'preparation' and st_ts:
                            ws = f"{emojis['time']} **Preparação** vs `{opp_n}`\nInício: <t:{st_ts}:R>"
                        elif state == 'inWar' and et_ts:
                            ws = f"{emojis['war_attack']} **Em Guerra** vs `{opp_n}`\nPlacar: **{our_s}** ⭐ vs **{opp_s}** ⭐\nFim: <t:{et_ts}:R>"
                        elif state == 'warEnded':
                            our_d=round(getattr(our_w,'destruction',0.0),1)
                            opp_d=round(getattr(opp,'destruction',0.0),1)
                            emoji_r, result_text = (emojis['war_win'], "Vitória") if our_s > opp_s or (our_s == opp_s and our_d > opp_d) else \
                                                  (emojis['war_lose'], "Derrota") if our_s < opp_s or (our_s == opp_s and our_d < opp_d) else \
                                                  (emojis['war_tie'], "Empate")
                            ws = f"{emoji_r} **Finalizada** vs `{opp_n}`\nResultado: **{result_text}** ({our_s} ⭐ / {opp_s} ⭐)"
                        else:
                            ws = f"{emojis['warning']} Estado Desconhecido: {state}"
                    else: ws = f"{emojis['warning']} Dados da guerra incompletos."
            except coc_errors.NotFound: ws = f"{emojis['success']} Não está em Guerra Normal."
            except coc_errors.ClashOfClansException as e_coc: ws = f"{emojis['error']} Erro API Guerra ({type(e_coc).__name__})"; logger.warning(f"Erro API GW !status: {e_coc}")
            except asyncio.TimeoutError: ws=f"{emojis['error']} Timeout ao verificar Guerra."; logger.warning("Timeout GW !status")
            except Exception as e_stat_war: ws = f"{emojis['error']} Erro ao verificar Guerra"; logger.error(f"Erro GW !status: {e_stat_war}", exc_info=True)
            emb.add_field(name="Guerra Normal", value=ws, inline=False)

            # --- Status Guerra de Liga ---
            ls=f"{emojis['warning']} Verificando..."
            try:
                lg=await asyncio.wait_for(coc_client.get_league_group(CLAN_TAG),timeout=45.0);
                if lg and getattr(lg,'state','notInWar')!="notInWar":
                    season=getattr(lg,'season','?')
                    state=getattr(lg,'state','?').capitalize()
                    lg_name = getattr(getattr(lg,'league',None),'name', '?')
                    ls = f"{emojis['league']} **Em CWL** ({lg_name} - {season})\nEstado Grupo: **{state}**"
                    active_w=None;
                    try: lg_wars = await asyncio.wait_for(lg.get_wars(CLAN_TAG),timeout=45.0);
                    except Exception: lg_wars=[]

                    current_round_war = next((w for w in lg_wars if getattr(w,'state',None) in ['inWar','preparation']), None)

                    if current_round_war:
                        active_w = current_round_war
                        our_w_lg = active_w.clan if hasattr(active_w.clan, 'tag') and active_w.clan.tag == CLAN_TAG else getattr(active_w, 'opponent', None)
                        opp_lg = active_w.opponent if hasattr(active_w.clan, 'tag') and active_w.clan.tag == CLAN_TAG else getattr(active_w, 'clan', None)
                        if our_w_lg and opp_lg:
                           opp_lg_n=getattr(opp_lg,'name','?')
                           state_t = "Em Guerra" if active_w.state=='inWar' else "Preparação"
                           st_em = emojis['war_attack'] if active_w.state=='inWar' else emojis['time']
                           time_obj = active_w.end_time if active_w.state=='inWar' else active_w.start_time
                           t_rel = f"<t:{int(time_obj.time.astimezone(TIMEZONE).timestamp())}:R>" if time_obj and hasattr(time_obj, 'time') else "?"
                           ls+=f"\n{st_em} Rodada Atual: **{state_t}** vs `{opp_lg_n}` ({t_rel})";
                           if active_w.state=='inWar':
                               our_s=getattr(our_w_lg,'stars',0)
                               opp_s=getattr(opp_lg,'stars',0)
                               ls+=f"\nPlacar: **{our_s}** ⭐ vs **{opp_s}** ⭐"
                        else: ls+=f"\n{emojis['error']} Erro ao identificar clãs da rodada."
                    else: ls+=f"\n{emojis['info']} Nenhuma rodada ativa (preparação/guerra) encontrada."
                else: ls=f"{emojis['success']} Não está em CWL."
            except coc_errors.NotFound: ls=f"{emojis['success']} Não está em CWL (grupo não encontrado)."
            except coc_errors.ClashOfClansException as e_coc: ls = f"{emojis['error']} Erro API Liga ({type(e_coc).__name__})"; logger.warning(f"Erro API Liga !status: {e_coc}")
            except asyncio.TimeoutError: ls=f"{emojis['error']} Timeout ao verificar Liga."; logger.warning("Timeout Liga !status")
            except Exception as e_lg: ls=f"{emojis['error']} Erro ao verificar Liga"; logger.warning(f"Erro Liga !status: {e_lg}", exc_info=True)
            emb.add_field(name="Guerra de Liga (CWL)", value=ls, inline=False)

             # --- Status Raid Weekend ---
            rs=f"{emojis['warning']} Verificando..."
            try:
                rl=await asyncio.wait_for(coc_client.get_clan_capital_raid_seasons(CLAN_TAG,limit=1),timeout=30.0);
                if rl and rl[0] and hasattr(rl[0],'state'):
                    r=rl[0]
                    state=r.state.capitalize()
                    loot=getattr(r,'capital_total_loot',0)
                    attacks=getattr(r,'total_attacks','?')
                    dist_destroyed=getattr(r,'districts_destroyed','?')
                    start_time_obj = getattr(r, 'start_time', None)
                    end_time_obj = getattr(r, 'end_time', None)
                    st_str = start_time_obj.time.astimezone(TIMEZONE).strftime('%d/%m %H:%M') if start_time_obj and hasattr(start_time_obj, 'time') else '?'
                    et_ts = int(end_time_obj.time.astimezone(TIMEZONE).timestamp()) if end_time_obj and hasattr(end_time_obj, 'time') else None

                    if state=='Ongoing' and et_ts:
                        rs=f"{emojis['raid']} **Raid Ativo**\nInício: {st_str}\nTérmino: <t:{et_ts}:R>\nOuro: **{loot:,}** | Ataques: {attacks} | Distritos: {dist_destroyed}"
                    elif state=='Ended':
                         rs=f"{emojis['clan_capital']} **Raid Inativo**. Última ({st_str}):\nOuro: **{loot:,}** | Ataques: {attacks} | Distritos: {dist_destroyed}"
                    else: rs=f"{emojis['clan_capital']} Raid em estado: **{state}**"
                else: rs=f"{emojis['clan_capital']} Sem informações de Raid Weekend."
            except coc_errors.NotFound: rs=f"{emojis['clan_capital']} Sem informações de Raid (NotFound)."
            except coc_errors.ClashOfClansException as e_coc: rs = f"{emojis['error']} Erro API Raid ({type(e_coc).__name__})"; logger.warning(f"Erro API Raid !status: {e_coc}")
            except asyncio.TimeoutError: rs=f"{emojis['error']} Timeout ao verificar Raid."; logger.warning("Timeout Raid !status")
            except Exception as e_rs: rs=f"{emojis['error']} Erro ao verificar Raid"; logger.warning(f"Erro Raid !status: {e_rs}", exc_info=True)
            emb.add_field(name="Raid Weekend", value=rs, inline=False)

            # --- Status do Bot ---
            lat=bot.latency*1000
            emb.add_field(name="Status do Bot", value=f"{emojis['success']} Online | Latência: **{lat:.0f}ms**", inline=False)
            emb.timestamp = datetime.now(TIMEZONE) # Adiciona timestamp da verificação
            await ctx.send(embed=emb)
        except Exception as e:
             logger.error(f"Erro GERAL cmd status:{e}", exc_info=True);
             await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Ocorreu um erro ao gerar o status: {e}", color=discord.Color.red));

@bot.command(name='top', help="Rankings: top [tipo] [limite=10]")
@commands.has_permissions(administrator=True)
async def top_command(ctx, tipo: str = "doacoes", limite: int = 10):
    # Comando já usa Embed, apenas pequenas melhorias
    if not coc_client: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red)); return
    tipo=tipo.lower().strip()
    limite=min(50,max(1,limite)) # Limite entre 1 e 50
    valid_types = {
        "doacoes": ("doações", f"{emojis['donation']} Top {limite} Doadores (Temporada)", discord.Color.green()),
        "doações": ("doações", f"{emojis['donation']} Top {limite} Doadores (Temporada)", discord.Color.green()),
        "recebidos": ("recebidos", f"{emojis['received']} Top {limite} Recebedores (Temporada)", discord.Color.orange()),
        "trofeus": ("troféus", f"{emojis['trophy']} Top {limite} Troféus (Vila Principal)", discord.Color.gold()),
        "troféus": ("troféus", f"{emojis['trophy']} Top {limite} Troféus (Vila Principal)", discord.Color.gold()),
        "capital": ("capital", f"{emojis['clan_capital']} Top {limite} Contrib. Capital (Últ. Raid)", 0x9B59B6) # Roxo
    }

    if tipo not in valid_types:
        valid_str = ", ".join(valid_types.keys())
        await ctx.send(embed=discord.Embed(title=f"{emojis['error']} Tipo de Ranking Inválido", description=f"Tipos válidos: `{valid_str}`", color=discord.Color.red)); return

    internal_type, title, color = valid_types[tipo]

    async with ctx.typing():
        try:
            clan=await get_clan_data();
            if not clan or not hasattr(clan,'members') or not clan.members:
                await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro ao obter dados dos membros do clã `{CLAN_TAG}`!", color=discord.Color.red)); return

            m_list=list(clan.members) if clan.members else []
            if not m_list and internal_type != "capital": # Capital busca dados da raid separadamente
                await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} A lista de membros do clã está vazia ou indisponível.", color=discord.Color.orange)); return

            fmt_list=[]
            if internal_type == "doações":
                s_list=sorted(m_list,key=lambda m:getattr(m,'donations',0),reverse=True)[:limite];
                fmt_list=[f"{i}. `{getattr(m,'name','?')}` (CV{getattr(m,'town_hall','?')}) : **{getattr(m,'donations',0):,}** {emojis['donation']}" for i,m in enumerate(s_list,1)]
            elif internal_type == "recebidos":
                s_list=sorted(m_list,key=lambda m:getattr(m,'received',0),reverse=True)[:limite];
                fmt_list=[f"{i}. `{getattr(m,'name','?')}` (CV{getattr(m,'town_hall','?')}) : **{getattr(m,'received',0):,}** {emojis['received']}" for i,m in enumerate(s_list,1)]
            elif internal_type == "troféus":
                s_list=sorted(m_list,key=lambda m:getattr(m,'trophies',0),reverse=True)[:limite];
                fmt_list=[f"{i}. `{getattr(m,'name','?')}` (CV{getattr(m,'town_hall','?')}) : **{getattr(m,'trophies',0):,}** {emojis['trophy']}" for i,m in enumerate(s_list,1)]
            elif internal_type == "capital":
                try:
                    rl=await asyncio.wait_for(coc_client.get_clan_capital_raid_seasons(CLAN_TAG,limit=1),timeout=30.0);
                    if not rl or not rl[0] or not hasattr(rl[0],'members') or not rl[0].members:
                         await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} Sem dados de membros da última Raid Weekend.", color=discord.Color.orange)); return

                    # Usa nomes do log da raid, pois membro pode ter saído
                    m_data={m.tag:{'name':getattr(m,'name','?'),'loot':getattr(m,'capital_resources_looted',0)} for m in rl[0].members if hasattr(m,'tag')};
                    s_raid=sorted(m_data.items(),key=lambda i:i[1]['loot'],reverse=True)[:limite];
                    fmt_list=[f"{i}. `{d['name']}` : **{d['loot']:,}** {emojis['clan_capital']}" for i,(t,d) in enumerate(s_raid,1)]
                    # Adiciona info sobre quando foi a raid
                    raid_start_time = getattr(rl[0], 'start_time', None)
                    if raid_start_time and hasattr(raid_start_time, 'time'):
                        title += f" ({raid_start_time.time.astimezone(TIMEZONE).strftime('%d/%m')})"

                except coc_errors.NotFound: await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} Sem histórico de Raid Weekend encontrado.", color=discord.Color.orange)); return
                except coc_errors.ClashOfClansException as e_coc: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro API ao buscar dados da Capital ({type(e_coc).__name__}).", color=discord.Color.red)); logger.warning(f"Erro API Capital !top: {e_coc}"); return
                except asyncio.TimeoutError: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Timeout ao buscar dados da Capital.", color=discord.Color.red)); logger.warning("Timeout Capital !top"); return
                except Exception as e: logger.error(f"Erro top capital:{e}",exc_info=True); await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro inesperado ao buscar dados da Capital: {e}", color=discord.Color.red)); return

            if not fmt_list:
                await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} Nenhum dado encontrado para o ranking '{tipo}'.", color=discord.Color.orange)); return

            base_emb=discord.Embed(title=title,color=color)
            c_n=getattr(clan,'name',CLAN_TAG)
            base_emb.set_footer(text=f"Clã: {c_n} | Verificado: {datetime.now(TIMEZONE).strftime('%d/%m %H:%M')}")
            # Usa a função de split adaptada
            await send_embeds_splitted(ctx.channel, base_emb, "Ranking", fmt_list, max_len=1024, max_items_per_embed=20) # Aumenta um pouco o limite de itens por embed aqui

        except Exception as e:
            logger.error(f"Erro GERAL cmd top:{e}", exc_info=True);
            await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro ao gerar o ranking: {e}", color=discord.Color.red))

@bot.command(name='ataques', help="Ataques restantes guerra normal.")
@commands.has_permissions(administrator=True)
async def ataques_command(ctx):
    # Usa a função auxiliar display_attacks_remaining
    if not coc_client: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red)); return
    async with ctx.typing():
        try:
            war = await asyncio.wait_for(coc_client.get_current_war(CLAN_TAG), timeout=30.0)
            if war and getattr(war, 'is_cwl', False):
                 await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} O clã está em Guerra de Liga (CWL). Use `!ligaataques` para ver os ataques restantes da rodada atual.", color=discord.Color.orange)); return
            await display_attacks_remaining(ctx, war, war_type="Guerra Normal")
        except coc_errors.NotFound: await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} O clã não está participando de uma Guerra Normal no momento.", color=discord.Color.orange))
        except coc_errors.ClashOfClansException as e_coc: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro na API CoC ({type(e_coc).__name__}) ao verificar a guerra.", color=discord.Color.red)); logger.warning(f"Erro API !ataques: {e_coc}")
        except asyncio.TimeoutError: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Timeout ao verificar a Guerra Normal.", color=discord.Color.red)); logger.warning("Timeout !ataques command")
        except Exception as e: logger.error(f"Erro !ataques: {e}", exc_info=True); await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro inesperado ao verificar ataques da guerra: {e}", color=discord.Color.red))

@bot.command(name='ligaataques', help="Ataques restantes guerra liga.")
@commands.has_permissions(administrator=True)
async def liga_ataques_command(ctx):
    # Usa a função auxiliar display_attacks_remaining
    if not coc_client: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red)); return
    async with ctx.typing():
        try:
            lg = await asyncio.wait_for(coc_client.get_league_group(CLAN_TAG), timeout=45.0)
            if not lg or getattr(lg, 'state', 'notInWar') == "notInWar":
                await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} O clã não está participando de uma Guerra de Liga (CWL) no momento.", color=discord.Color.orange)); return

            curr_war = None
            lg_wars = [];
            try: lg_wars = await asyncio.wait_for(lg.get_wars(CLAN_TAG), timeout=45.0)
            except Exception as e_get_wars: logger.warning(f"Erro buscar guerras liga !ligaataques: {e_get_wars}")

            # Encontra a guerra da rodada atual (prioriza 'inWar', depois 'preparation')
            curr_war = next((w for w in lg_wars if getattr(w, 'state', None) == 'inWar'), None)
            if not curr_war:
                 curr_war = next((w for w in lg_wars if getattr(w, 'state', None) == 'preparation'), None)

            if not curr_war:
                 await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} Nenhuma rodada da Guerra de Liga ativa (em guerra ou preparação) encontrada.", color=discord.Color.orange)); return

            await display_attacks_remaining(ctx, curr_war, war_type="Guerra de Liga")
        except coc_errors.NotFound: await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} Clã não encontrado em um grupo de Guerra de Liga.", color=discord.Color.orange))
        except coc_errors.ClashOfClansException as e_coc: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro na API CoC ({type(e_coc).__name__}) ao verificar a liga.", color=discord.Color.red)); logger.warning(f"Erro API !ligaataques: {e_coc}")
        except asyncio.TimeoutError: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Timeout ao verificar a Guerra de Liga.", color=discord.Color.red)); logger.warning("Timeout !ligaataques command")
        except Exception as e: logger.error(f"Erro !ligaataques: {e}", exc_info=True); await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro inesperado ao verificar ataques da liga: {e}", color=discord.Color.red))

@bot.command(name='membro', help="Detalhes jogador: !membro <#TAG>")
@commands.has_permissions(administrator=True)
async def membro_command(ctx, player_tag: str = None):
     # Comando já usa Embed, apenas pequenas melhorias
    if not coc_client: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red)); return
    if not player_tag: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Por favor, forneça a TAG do jogador. Ex: `!membro #Y9PVY2C`", color=discord.Color.red)); return

    player_tag=player_tag.strip().upper()
    if not player_tag.startswith('#'): player_tag='#'+player_tag
    if not coc.utils.is_valid_tag(player_tag): await ctx.send(embed=discord.Embed(description=f"{emojis['error']} A tag `{player_tag}` é inválida.", color=discord.Color.red)); return

    async with ctx.typing():
        try:
            player=await asyncio.wait_for(coc_client.get_player(player_tag),timeout=20.0);
            p_n=getattr(player,'name','?')
            p_t=getattr(player,'tag',player_tag)
            p_th=getattr(player,'town_hall','?')
            p_th_weapon=getattr(player,'town_hall_weapon',None)
            p_xp=getattr(player,'exp_level','?')
            p_lg=getattr(player,'league',None)
            p_tr=getattr(player,'trophies',0)
            p_btr=getattr(player,'best_trophies',0)
            p_ws=getattr(player,'war_stars',0)
            p_aw=getattr(player,'attack_wins',0) # Ataques vencidos (Multiplayer)
            p_dw=getattr(player,'defense_wins',0) # Defesas vencidas
            p_don=getattr(player,'donations',0)
            p_rec=getattr(player,'received',0)
            p_cl=getattr(player,'clan',None)
            p_role=getattr(player,'role','?') if p_cl else 'N/A' # Cargo no clã
            p_hr=getattr(player,'heroes',[])
            p_pet=getattr(player,'pets',[])
            p_spells = getattr(player, 'spells', []) # Feitiços (para contar)
            p_troops = getattr(player, 'troops', []) # Tropas (para contar)

            # Montar Embed
            title=f"{p_lg.name if p_lg and hasattr(p_lg,'name') else ''} {p_n} ({p_t})" # Liga no título
            emb=discord.Embed(title=title, color=discord.Color.orange());
            if p_lg and hasattr(p_lg,'icon') and hasattr(p_lg.icon,'url'): emb.set_thumbnail(url=p_lg.icon.url)

            # Informações do Clã
            clan_info = "Sem clã";
            if p_cl and hasattr(p_cl,'name') and hasattr(p_cl,'tag') and hasattr(p_cl,'badge') and hasattr(p_cl.badge,'url'):
                clan_info = f"[{getattr(p_cl,'name','?')}]({coc.utils.clan_link(p_cl.tag)})\nCargo: **{p_role}**" # Link clã
                emb.set_author(name=f"Membro de {p_cl.name}", icon_url=p_cl.badge.url) # Author com badge clã
            elif p_cl and hasattr(p_cl,'name'): # Fallback sem link/badge
                 clan_info = f"{getattr(p_cl,'name','?')}\nCargo: **{p_role}**"
            emb.add_field(name=f"{emojis['clan_capital']} Clã",value=clan_info,inline=False)

            # Infos Gerais
            emb.add_field(name="CV", value=f"**{p_th}**" + (f" (Arma: {p_th_weapon})" if p_th_weapon else ""), inline=True)
            emb.add_field(name="Nível XP", value=str(p_xp), inline=True)
            emb.add_field(name="Liga", value=f"{p_tr:,}{emojis['trophy']}" + (f" ({p_lg.name})" if p_lg else ""), inline=True)
            emb.add_field(name="Recorde Troféus", value=f"{p_btr:,}{emojis['trophy']}", inline=True)
            emb.add_field(name="Estrelas Guerra", value=f"{p_ws:,}⭐", inline=True)
            emb.add_field(name="Doações Temp.", value=f"{p_don:,}{emojis['donation']} / {p_rec:,}{emojis['received']}", inline=True)

            # Heróis (Home Village)
            hv_heroes = [h for h in p_hr if getattr(h,'is_home_base',False)]
            h_str="\n".join([f"- {getattr(h,'name','?')}: **{getattr(h,'level','?')}** / {getattr(h,'max_level','?')}" for h in hv_heroes]) or "N/A";
            if h_str != "N/A": emb.add_field(name=f"{emojis['war_attack']} Heróis (Vila Principal)",value=h_str,inline=False)

            # Pets (Home Village)
            # A API pode não retornar pets diretamente no player, verificar se p_pet existe e tem itens
            if p_pet:
                pet_str="\n".join([f"- {getattr(p,'name','?')}: **{getattr(p,'level','?')}** / {getattr(p,'max_level','?')}" for p in p_pet]) or "N/A";
                if pet_str != "N/A": emb.add_field(name="🐾 Pets",value=pet_str,inline=False)

            # Adicionar link para o perfil (opcional)
            player_link = coc.utils.player_link(p_t)
            emb.description = f"[Ver perfil no jogo]({player_link})" # Adiciona link na descrição

            emb.set_footer(text=f"Verificado: {datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M:%S')}")
            await ctx.send(embed=emb)

        except coc_errors.NotFound: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Jogador com a tag `{player_tag}` não encontrado.", color=discord.Color.red))
        except coc_errors.ClashOfClansException as e_coc: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro na API CoC ({type(e_coc).__name__}) ao buscar o jogador.", color=discord.Color.red)); logger.warning(f"Erro API !membro: {e_coc}")
        except asyncio.TimeoutError: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Timeout ao buscar dados do jogador.", color=discord.Color.red)); logger.warning("Timeout !membro command")
        except Exception as e: logger.error(f"Erro !membro {player_tag}:{e}",exc_info=True); await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro inesperado ao buscar jogador: {e}", color=discord.Color.red))


@bot.command(name='capital', help="Infos Capital Clã e último raid.")
@commands.has_permissions(administrator=True)
async def capital_command(ctx):
    # Comando já usa Embed, melhorias
    if not coc_client: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível.", color=discord.Color.red)); return
    async with ctx.typing():
        clan=await get_clan_data();
        if not clan: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro ao obter dados do clã `{CLAN_TAG}`!", color=discord.Color.red)); return

        c_n=getattr(clan,'name',CLAN_TAG)
        emb=discord.Embed(title=f"{emojis['clan_capital']} Capital do Clã: {c_n}",color=0x9B59B6) # Roxo
        badge=getattr(getattr(clan,'badge',None),'url',None)
        if badge: emb.set_thumbnail(url=badge)

        # Informações da Capital (Nível Salão, Distritos)
        cap_info = getattr(clan, 'clan_capital', None)
        try:
            if cap_info:
                 hall_lvl=getattr(cap_info,'capital_hall_level','?')
                 emb.description=f"Nível do Salão da Capital: **{hall_lvl}**"
                 districts = getattr(cap_info,'districts',[]);
                 d_list = [f"- {getattr(d,'name','?')}: Nível **{getattr(d,'hall_level','?')}**" for d in districts] if districts else ["N/D"]
                 # Usar split se a lista de distritos for muito longa
                 dist_field_title = f"{emojis['clan_capital']} Distritos ({len(d_list)})"
                 if len("\n".join(d_list)) > 1024:
                      await send_embeds_splitted(ctx.channel, emb, dist_field_title, d_list, max_len=1024, max_items_per_embed=10)
                      # O embed base já foi enviado, não precisa adicionar campo aqui
                 elif d_list != ["N/D"]:
                      emb.add_field(name=dist_field_title, value="\n".join(d_list), inline=False)
                 else:
                      emb.add_field(name=dist_field_title, value="Nenhum distrito encontrado.", inline=False)

            else: emb.description="Informações sobre a Capital do Clã indisponíveis."
        except Exception as e:
            emb.description=f"Erro ao buscar detalhes da Capital: {e}";
            logger.error(f"Erro Capital !capital (detalhes):{e}",exc_info=True)


        # Informações da Última/Atual Raid Weekend
        raid_field_title = f"{emojis['raid']} Última/Atual Raid Weekend"
        rf_v=f"{emojis['warning']} Verificando..."
        top_s=""
        raid_found = False
        try:
            rl=await asyncio.wait_for(coc_client.get_clan_capital_raid_seasons(CLAN_TAG,limit=1),timeout=30.0);
            if rl and rl[0] and hasattr(rl[0],'state'):
                raid_found = True
                r=rl[0]; state=r.state.capitalize(); loot=getattr(r,'capital_total_loot',0); attacks=getattr(r,'total_attacks','?'); d_d=getattr(r,'districts_destroyed','?')
                st_obj = getattr(r, 'start_time', None); et_obj = getattr(r, 'end_time', None)
                st = st_obj.time.astimezone(TIMEZONE).strftime('%d/%m %H:%M') if st_obj and hasattr(st_obj, 'time') else '?'
                et_ts = int(et_obj.time.astimezone(TIMEZONE).timestamp()) if et_obj and hasattr(et_obj, 'time') else None;
                t_inf=f"(Término: <t:{et_ts}:R>)" if et_ts and state == 'Ongoing' else "";
                st_t="Ativo" if state=='Ongoing' else "Finalizado"
                s_em=emojis['raid'] if state=='Ongoing' else emojis['success']

                rf_v=(f"**Estado:** {s_em} {st_t} {t_inf}\n"
                      f"**Início:** {st}\n"
                      f"{emojis['clan_capital']} Ouro Total: **{loot:,}**\n"
                      f"{emojis['war_attack']} Ataques: {attacks}\n"
                      f"{emojis['destruction']} Distritos Destruídos: {d_d}")

                # Top Contribuintes (se houver membros na raid)
                if getattr(r,'members',[]):
                    # Usar nomes do log da raid
                    m_data={m.tag:{'name':getattr(m,'name','?'),'loot':getattr(m,'capital_resources_looted',0)} for m in r.members if hasattr(m,'tag')};
                    s_raiders=sorted(m_data.items(),key=lambda i:i[1]['loot'],reverse=True)[:5]; # Top 5
                    top_s="\n".join([f"{i}. `{d['name']}`: **{d['loot']:,}**" for i,(t,d) in enumerate(s_raiders,1)])
            else: rf_v=f"{emojis['warning']} Nenhum dado da última Raid Weekend encontrado."
        except coc_errors.NotFound: rf_v=f"{emojis['warning']} Nenhum histórico de Raid Weekend encontrado (NotFound)."
        except coc_errors.ClashOfClansException as e_coc: rf_v = f"{emojis['error']} Erro API Raid ({type(e_coc).__name__})."; logger.warning(f"Erro API Raid !capital: {e_coc}")
        except asyncio.TimeoutError: rf_v=f"{emojis['error']} Timeout ao verificar Raid."; logger.warning("Timeout Raid !capital")
        except Exception as e: rf_v=f"{emojis['error']} Erro ao verificar Raid."; logger.warning(f"Erro Raid !capital:{e}", exc_info=True)

        # Adiciona o campo da Raid (se não foi enviado pelo split dos distritos)
        if not (cap_info and districts and len("\n".join(d_list)) > 1024):
             emb.add_field(name=raid_field_title, value=rf_v, inline=False)

        # Adiciona Top Contribuintes se houver e se a raid foi encontrada
        if raid_found and top_s:
            # Adiciona campo de top (se não foi enviado pelo split dos distritos)
             if not (cap_info and districts and len("\n".join(d_list)) > 1024):
                  emb.add_field(name="🌟 Top Contribuições (Últ. Raid)", value=top_s, inline=False)
             else: # Se o embed base já foi enviado, envia o top separadamente
                  top_embed = discord.Embed(title="🌟 Top Contribuições (Últ. Raid)", description=top_s, color=emb.color)
                  try: await ctx.send(embed=top_embed)
                  except Exception as e: logger.error(f"Erro ao enviar embed TOP separado (!capital): {e}")


        emb.set_footer(text=f"Verificado: {datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M:%S')}")
        # Envia o embed principal (se não foi enviado pelo split dos distritos)
        if not (cap_info and districts and len("\n".join(d_list)) > 1024):
            await ctx.send(embed=emb)


@bot.command(name='setcanal', help="Define canal logs: !setcanal #canal")
@commands.has_permissions(administrator=True)
async def set_canal_command(ctx, channel: discord.TextChannel = None):
    # <<< EMBED START >>> (Usar embeds para confirmações e erros)
    global CHANNEL_ID
    target_channel = channel or ctx.channel
    if not isinstance(target_channel, discord.TextChannel):
         await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Canal inválido. Por favor, mencione um canal de texto existente.", color=discord.Color.red)); return
    try:
         # Testar permissão enviando uma mensagem de teste
         test_msg = await target_channel.send(embed=discord.Embed(description=f"{emojis['warning']} Testando permissões neste canal...", color=discord.Color.orange))
         await test_msg.edit(embed=discord.Embed(description=f"{emojis['success']} Permissões OK!", color=discord.Color.green), delete_after=5.0) # Confirma e apaga

         old_channel_id = CHANNEL_ID
         CHANNEL_ID = target_channel.id
         logger.info(f"Canal de logs alterado para {target_channel.name}({CHANNEL_ID}) por {ctx.author}")

         confirm_embed = discord.Embed(
             title=f"{emojis['success']} Canal de Logs Alterado",
             description=f"O canal para envio de logs e notificações foi definido para {target_channel.mention}.",
             color=discord.Color.green()
         )
         await ctx.send(embed=confirm_embed)

         # Perguntar sobre reiniciar tasks
         restart_q_embed = discord.Embed(
             description=f"{emojis['warning']} Deseja reiniciar as tarefas de monitoramento agora para aplicar a mudança imediatamente? (Responda com `sim` ou `não`)",
             color=discord.Color.orange
         )
         confirm_msg = await ctx.send(embed=restart_q_embed)

         check = lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['sim','s','yes','y','não','nao','n','no']
         try:
             resp = await bot.wait_for('message', timeout=30.0, check=check);
             # Deletar a pergunta e a resposta do usuário
             try: await confirm_msg.delete()
             except discord.HTTPException: pass
             try: await resp.delete()
             except discord.HTTPException: pass

             if resp.content.lower() in ['sim','s','yes','y']:
                  await ctx.send(embed=discord.Embed(description=f"{emojis['info']} Reiniciando tarefas...", color=discord.Color.blue), delete_after=10.0)
                  tasks_list=[check_donations,check_members,check_war,check_league_war,check_raid_weekend]
                  restart_log = []
                  for t in tasks_list:
                      task_name = t.coro.__name__
                      status_emoji = emojis['error']
                      status_text = "Erro"
                      try:
                          if t.is_running():
                              t.restart()
                              status_emoji = emojis['success']
                              status_text = "Reiniciada"
                          else:
                              t.start()
                              status_emoji = emojis['success']
                              status_text = "Iniciada"
                      except Exception as e_restart:
                          logger.error(f"Erro ao reiniciar/iniciar task {task_name} (setcanal): {e_restart}")
                          status_text = f"Erro ({e_restart})"
                      restart_log.append(f"- {task_name}: {status_text} {status_emoji}")

                  restart_embed = discord.Embed(
                      title=f"{emojis['success']} Tarefas Reiniciadas",
                      description="As tarefas de monitoramento foram reiniciadas e usarão o novo canal.\n\n**Status:**\n" + "\n".join(restart_log),
                      color=discord.Color.green
                  )
                  await target_channel.send(embed=restart_embed) # Envia no *novo* canal
                  logger.info(f"Tasks reiniciadas (setcanal) ({'; '.join(restart_log)}).")
             else:
                 await ctx.send(embed=discord.Embed(description=f"{emojis['info']} As tarefas não foram reiniciadas. A mudança de canal será efetiva na próxima execução automática ou reinicialização do bot.", color=discord.Color.light_grey))
         except asyncio.TimeoutError:
             try: await confirm_msg.delete() # Tenta deletar mesmo no timeout
             except discord.HTTPException: pass
             await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} Tempo esgotado. As tarefas não foram reiniciadas.", color=discord.Color.orange))

    except discord.errors.Forbidden:
        await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Permissão Negada! O bot não tem permissão para enviar mensagens em {target_channel.mention}.", color=discord.Color.red))
    except Exception as e:
        logger.error(f"Erro no comando setcanal para {target_channel.mention}: {e}",exc_info=True);
        await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Ocorreu um erro inesperado ao definir o canal: {e}", color=discord.Color.red))
    # <<< EMBED END >>>


@bot.command(name='setclan', help="Define clã monitorar: !setclan #TAG")
@commands.has_permissions(administrator=True)
async def set_clan_command(ctx, clan_tag: str = None):
    # <<< EMBED START >>> (Usar embeds para confirmações e erros)
    global CLAN_TAG,member_cache,donation_cache,war_cache,raid_weekend_cache, coc_client
    if not coc_client: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} API CoC indisponível. Não é possível alterar o clã agora.", color=discord.Color.red)); return
    if not clan_tag: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Forneça a TAG do clã. Ex: `!setclan #TAGCLAN`", color=discord.Color.red)); return

    clan_tag=clan_tag.strip().upper()
    if not clan_tag.startswith('#'): clan_tag='#'+clan_tag
    if not coc.utils.is_valid_tag(clan_tag): await ctx.send(embed=discord.Embed(description=f"{emojis['error']} A tag `{clan_tag}` é inválida.", color=discord.Color.red)); return
    if clan_tag == CLAN_TAG: await ctx.send(embed=discord.Embed(description=f"{emojis['info']} O bot já está monitorando o clã `{clan_tag}`.", color=discord.Color.blue)); return

    async with ctx.typing():
        try:
            logger.info(f"Tentando definir clã para {clan_tag} por {ctx.author}...")
            # Verificar acesso ao novo clã
            clan = await asyncio.wait_for(coc_client.get_clan(clan_tag),timeout=30.0);
            new_clan_name = getattr(clan, 'name', clan_tag)
            new_clan_tag = getattr(clan, 'tag', clan_tag) # Usa a tag retornada pela API (caso haja diferença de casing)
            new_clan_badge_url = getattr(getattr(clan,'badge',None),'url',None)

            # Confirmação da mudança
            change_embed = discord.Embed(
                 title=f"{emojis['success']} Clã Alvo Alterado!",
                 description=f"Monitoramento alterado para o clã **{new_clan_name}** (`{new_clan_tag}`).\n\n"
                             f"{emojis['warning']} Limpando caches de dados antigos...",
                 color=discord.Color.green
            )
            if new_clan_badge_url: change_embed.set_thumbnail(url=new_clan_badge_url)
            await ctx.send(embed=change_embed)

            old_tag=CLAN_TAG
            CLAN_TAG=new_clan_tag # Atualiza a variável global

            # Limpar caches
            member_cache={'members':{},'count':0}
            donation_cache={}
            # Limpa cache de guerra de forma mais segura
            war_cache = {'war_end_reported': war_cache.get('war_end_reported',{}), # Mantém reported
                         'league_war_end_reported': war_cache.get('league_war_end_reported',{}),
                         'league_start_announced': False} # Reseta outros
            raid_weekend_cache={'current_raid':None}
            logger.info(f"Clã alterado de {old_tag} para {CLAN_TAG} ({new_clan_name}) por {ctx.author}. Caches limpos.")

            await ctx.send(embed=discord.Embed(description=f"{emojis['success']} Caches limpos.", color=discord.Color.green), delete_after=10.0)

            # Perguntar sobre reiniciar tasks
            restart_q_embed = discord.Embed(
                description=f"{emojis['warning']} Deseja reiniciar as tarefas de monitoramento agora para o novo clã? (Responda com `sim` ou `não`)",
                color=discord.Color.orange
            )
            confirm_msg = await ctx.send(embed=restart_q_embed)

            check=lambda m: m.author==ctx.author and m.channel==ctx.channel and m.content.lower() in ['sim','s','yes','y','não','nao','n','no']
            try:
                resp=await bot.wait_for('message',timeout=30.0,check=check);
                # Deletar a pergunta e a resposta
                try: await confirm_msg.delete()
                except discord.HTTPException: pass
                try: await resp.delete()
                except discord.HTTPException: pass

                if resp.content.lower() in ['sim','s','yes','y']:
                    await ctx.send(embed=discord.Embed(description=f"{emojis['info']} Reiniciando tarefas para **{new_clan_name}**...", color=discord.Color.blue), delete_after=10.0)
                    tasks_list=[check_donations,check_members,check_war,check_league_war,check_raid_weekend]
                    restart_log = []
                    for t in tasks_list:
                        task_name = t.coro.__name__
                        status_emoji = emojis['error']
                        status_text = "Erro"
                        try:
                            if t.is_running():
                                t.restart()
                                status_emoji = emojis['success']
                                status_text = "Reiniciada"
                            else:
                                t.start()
                                status_emoji = emojis['success']
                                status_text = "Iniciada"
                        except Exception as e_restart:
                            logger.error(f"Erro ao reiniciar/iniciar task {task_name} (setclan): {e_restart}")
                            status_text = f"Erro ({e_restart})"
                        restart_log.append(f"- {task_name}: {status_text} {status_emoji}")

                    restart_embed = discord.Embed(
                        title=f"{emojis['success']} Tarefas Reiniciadas para {new_clan_name}",
                        description="As tarefas de monitoramento foram reiniciadas para o novo clã.\n\n**Status:**\n" + "\n".join(restart_log),
                        color=discord.Color.green
                    )
                    status_channel = bot.get_channel(CHANNEL_ID) # Canal atual de logs
                    if status_channel: await status_channel.send(embed=restart_embed)
                    else: await ctx.send(embed=restart_embed) # Envia no canal do comando se o de log falhar
                    logger.info(f"Tasks reiniciadas (setclan para {CLAN_TAG}) ({'; '.join(restart_log)}).")
                else:
                    await ctx.send(embed=discord.Embed(description=f"{emojis['info']} As tarefas não foram reiniciadas. O monitoramento do novo clã iniciará na próxima execução automática ou reinicialização do bot.", color=discord.Color.light_grey))
            except asyncio.TimeoutError:
                try: await confirm_msg.delete()
                except discord.HTTPException: pass
                await ctx.send(embed=discord.Embed(description=f"{emojis['warning']} Tempo esgotado. As tarefas não foram reiniciadas.", color=discord.Color.orange))

        except coc_errors.NotFound: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Clã com a tag `{clan_tag}` não encontrado!", color=discord.Color.red))
        except coc_errors.ClashOfClansException as e_coc: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro na API CoC ({type(e_coc).__name__}) ao verificar a tag do clã.", color=discord.Color.red)); logger.warning(f"Erro API !setclan: {e_coc}")
        except asyncio.TimeoutError: await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Timeout ao verificar a tag do clã.", color=discord.Color.red)); logger.warning("Timeout !setclan command")
        except Exception as e: logger.error(f"Erro setclan {clan_tag}: {e}",exc_info=True); await ctx.send(embed=discord.Embed(description=f"{emojis['error']} Erro inesperado ao definir o clã: {e}", color=discord.Color.red))
    # <<< EMBED END >>>

@bot.command(name='ajuda', aliases=['help', 'comandos'])
async def ajuda_command(ctx):
    # Comando já usa Embed, pequenas melhorias
    embed=discord.Embed(
        title=f"{emojis['info']} Ajuda - {bot.user.name}",
        description="Monitora eventos do Clash of Clans e fornece informações sobre o clã.",
        color=discord.Color.green()
    )
    if bot.user.avatar: embed.set_thumbnail(url=bot.user.avatar.url)

    embed.add_field(
        name="🛠️ Comandos de Configuração (Admin)",
        value=f"`{bot.command_prefix}setcanal #canal` - Define o canal para receber logs e notificações.\n"
              f"`{bot.command_prefix}setclan #TAGCLAN` - Define qual clã o bot deve monitorar.",
        inline=False
    )
    embed.add_field(
        name="📊 Comandos de Informação (Admin)",
        value=f"`{bot.command_prefix}status` - Exibe um resumo do status atual do clã, guerras e raids.\n"
              f"`{bot.command_prefix}top [tipo] [limite]` - Mostra rankings (tipos: `doacoes`, `recebidos`, `trofeus`, `capital`). Limite padrão é 10.\n"
              f"`{bot.command_prefix}ataques` - Lista membros com ataques restantes na Guerra Normal atual.\n"
              f"`{bot.command_prefix}ligaataques` - Lista membros com ataques restantes na rodada atual da CWL.\n"
              f"`{bot.command_prefix}membro #TAGJOGADOR` - Exibe detalhes de um jogador específico.\n"
              f"`{bot.command_prefix}capital` - Mostra informações sobre a Capital do Clã e a última Raid Weekend.",
        inline=False
    )
    embed.add_field(
        name="👀 Eventos Monitorados Automaticamente",
        value=f"{emojis['donation']}/{emojis['received']} Doações e Recebimentos\n"
              f"{emojis['join']}/{emojis['leave']} Entradas e Saídas de Membros\n"
              f"{emojis['war_attack']} Ataques em Guerras (Normal e CWL)\n"
              f"{emojis['war_win']}/{emojis['war_lose']}/{emojis['war_tie']} Início e Fim de Guerras\n"
              f"{emojis['time']} Alertas de Tempo Restante em Guerras\n"
              f"{emojis['missed_attack']} Relatório de Ataques Não Realizados\n"
              f"{emojis['raid']} Início, Fim e Progresso da Raid Weekend",
        inline=False
    )
    embed.set_footer(text=f"Versão do Bot: 14.13 | Prefixo: {bot.command_prefix}") # Atualiza versão
    await ctx.send(embed=embed)

# --- Função Principal ---
async def main():
    global coc_client
    if not TOKEN: logger.critical("Token Discord não encontrado."); return

    logger.info("Iniciando bot Discord (main)...")
    try:
        # setup_hook (web server) e on_ready (CoC login, tasks) são chamados pelo bot.start()
        await bot.start(TOKEN)
    except discord.LoginFailure: logger.critical("Login Discord falhou: Token inválido.")
    except discord.PrivilegedIntentsRequired: logger.critical("Login Discord falhou: Intenções privilegiadas (Members/Message Content) não habilitadas no Portal do Desenvolvedor Discord.")
    except KeyboardInterrupt: logger.info("Desligamento manual solicitado.")
    except Exception as e: logger.critical(f"Erro fatal no loop principal do bot: {e}", exc_info=True)
    # before_closing é chamado automaticamente

if __name__ == "__main__":
    try:
        # Necessário para AIOHTTP no Windows em alguns casos
        if os.name == 'nt': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except Exception as e_run:
        logger.critical(f"Erro crítico ao executar asyncio.run(main): {e_run}", exc_info=True)
