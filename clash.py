# -*- coding: utf-8 -*-
# Versão 14.11 - Mantém chamada documentada v3.9.1, melhora log em except genérico

import discord
from discord.ext import commands, tasks
import coc
from coc import errors as coc_errors # Importa como coc_errors
import asyncio
import os
import logging
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

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
    'error': '❌', 'success': '✅', 'warning': '⚠️', 'league': '🌟'
}

# --- Cliente CoC ---
coc_client = None

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
        except coc_errors.AuthenticationError as e_auth: # Mantém específico pois parece funcionar
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
    # *** CORREÇÃO APLICADA AQUI - Tratamento genérico refinado ***
    except coc_errors.NotFound:
        logger.error(f"Clã '{target_tag}' não encontrado."); return None
    except coc_errors.ClashOfClansException as e_coc:
        logger.warning(f"Erro API CoC ({type(e_coc).__name__}) buscando clã '{target_tag}': {e_coc}"); return None
    except asyncio.TimeoutError:
        logger.error(f"Timeout buscando clã '{target_tag}'."); return None
    except Exception as e:
        logger.error(f"Erro Inesperado ({type(e).__name__}) buscando clã '{target_tag}': {e}", exc_info=True); return None

async def send_embeds_splitted(channel, base_embed, field_name, members_list, max_len=1000):
    # Sem alterações
    if not members_list:
        try: base_embed.add_field(name=field_name, value="Nenhum.", inline=False); await channel.send(embed=base_embed)
        except Exception as e: logger.error(f"Erro send_embeds_splitted (vazio): {e}", exc_info=True)
        return
    current_embed = base_embed.copy(); current_value = ""; first_embed = True
    if current_embed.fields: current_embed.clear_fields()
    for item in members_list:
        item_line = item + "\n"
        if len(current_value) + len(item_line) > max_len:
            current_embed.add_field(name=field_name if first_embed else f"{field_name}(cont.)", value=current_value or " ", inline=False)
            try: await channel.send(embed=current_embed); await asyncio.sleep(0.5)
            except Exception as e: logger.error(f"Erro send_embeds_splitted (dividido): {e}", exc_info=True); return
            current_embed = base_embed.copy(); current_embed.clear_fields(); current_value = item_line; first_embed = False
        else: current_value += item_line
    if current_value:
        current_embed.add_field(name=field_name if first_embed else f"{field_name}(cont.)", value=current_value or " ", inline=False)
        try: await channel.send(embed=current_embed)
        except Exception as e: logger.error(f"Erro send_embeds_splitted (final): {e}", exc_info=True)

async def get_player_name(tag):
    # Sem alterações
    global coc_client; fallback_name = f"Jogador ({tag[-4:]})" if tag else "Jogador (?)"
    if not coc_client or not tag: return fallback_name
    try: player = await asyncio.wait_for(coc_client.get_player(tag), timeout=15.0); return getattr(player, 'name', fallback_name)
    except (coc_errors.NotFound, asyncio.TimeoutError): return fallback_name
    except Exception as e: logger.error(f"Erro get_player_name {tag}: {e}", exc_info=True); return fallback_name

# --- Tarefas de Monitoramento ---
@tasks.loop(minutes=5)
async def check_donations():
    # Sem alterações
    global donation_cache, coc_client
    if not coc_client: logger.debug("check_donations pulado: cliente CoC inválido."); return
    clan = await get_clan_data()
    if not clan or not hasattr(clan, 'members') or not clan.members:
        logger.debug("check_donations pulado: dados clã/membros indisponíveis."); return
    try:
        channel=bot.get_channel(CHANNEL_ID)
        if not channel: logger.warning("check_donations: Canal ID não encontrado."); return
        messages=[]
        current_time_str=datetime.now(TIMEZONE).strftime('%H:%M')
        local_cache=donation_cache.copy()
        new_state={}
        is_initial = not local_cache
        for member in clan.members:
            tag = getattr(member, 'tag', None)
            if not tag:
                continue
            donations = getattr(member, 'donations', 0)
            received = getattr(member, 'received', 0)
            name = getattr(member, 'name', f'Membro({tag[-4:]})')
            current_data={'name': name, 'donations': donations, 'received': received}
            new_state[tag]=current_data
            if not is_initial and tag in local_cache:
                old=local_cache[tag]
                old_don=old.get('donations', 0)
                old_rec=old.get('received', 0)
                don_diff = current_data['donations']-old_don
                rec_diff = current_data['received']-old_rec
                if don_diff > 0: messages.append(f"{emojis['donation']} `{name}` doou {don_diff}T! (T:{current_data['donations']:,})")
                if rec_diff > 0: messages.append(f"{emojis['donation']} `{name}` recebeu {rec_diff}T! (T:{current_data['received']:,})")
        donation_cache = new_state
        if messages and not is_initial:
            logger.info(f"Detectadas {len(messages)} alterações doações/rec.")
            full_msg=f"{emojis['time']}[{current_time_str}] {emojis['donation']}Doações/Rec:\n" + "\n".join(messages)
            if len(full_msg)>1950:
                parts=[messages[i:i+5] for i in range(0,len(messages),5)];
                for i,p in enumerate(parts):
                    chunk=f"{emojis['time']}[{current_time_str}]{emojis['donation']}Doa/Rec({i+1}/{len(parts)}):\n"+"\n".join(p)
                    try: await channel.send(chunk); await asyncio.sleep(1)
                    except Exception as e: logger.error(f"Erro send doação parte: {e}")
            else:
                try: await channel.send(full_msg)
                except Exception as e: logger.error(f"Erro send doação full: {e}")
        elif is_initial and new_state: logger.info("Cache doações inicializado.")
        else: logger.debug("check_donations executado, sem novas doações.")
    except Exception as e: logger.error(f"Erro GERAL check_donations: {e}", exc_info=True)

@tasks.loop(minutes=10)
async def check_members():
    # Sem alterações
    global member_cache, coc_client
    if not coc_client: logger.debug("check_members pulado: cliente CoC inválido."); return
    clan = await get_clan_data()
    if not clan or not hasattr(clan, 'members') or not clan.members:
        logger.debug("check_members pulado: dados clã/membros indisponíveis."); return
    try:
        channel=bot.get_channel(CHANNEL_ID)
        if not channel: logger.warning("check_members: Canal ID não encontrado."); return
        current_dict={getattr(m,'tag',None): getattr(m,'name','?') for m in clan.members if hasattr(m,'tag')}
        current_dict={k:v for k,v in current_dict.items() if k}
        current_time_str=datetime.now(TIMEZONE).strftime('%H:%M')
        if not member_cache['members']:
            logger.info("Cache membros inicializando...");
            member_cache['members']=current_dict
            member_cache['count']=len(current_dict)
            logger.info(f"Cache membros inicializado: {member_cache['count']} membros.");
            return
        old_set=set(member_cache['members'].keys())
        current_set=set(current_dict.keys())
        left=old_set-current_set
        joined=current_set-old_set
        if left or joined:
            log_msgs=[]
            send_tasks=[]
            for tag in left: name=member_cache['members'].get(tag,f"M({tag[-4:]})"); msg=f"{emojis['time']}[{current_time_str}] {emojis['leave']}**Saída:** {name} saiu."; send_tasks.append(channel.send(msg)); log_msgs.append(f"Saiu:{name}({tag})")
            for tag in joined: name=current_dict.get(tag,f"M({tag[-4:]})"); msg=f"{emojis['time']}[{current_time_str}] {emojis['join']}**Entrada:** {name} entrou."; send_tasks.append(channel.send(msg)); log_msgs.append(f"Entrou:{name}({tag})")
            if send_tasks:
                logger.info(f"Detectadas {len(joined)} entradas, {len(left)} saídas.")
                results=await asyncio.gather(*send_tasks, return_exceptions=True);
                for i,res in enumerate(results):
                    if isinstance(res,Exception): logger.error(f"Erro send msg membro [{i}]: {res}")
            if log_msgs: logger.info(f"Detalhes Membros: {', '.join(log_msgs)}")
            member_cache['members']=current_dict
            member_cache['count']=len(current_dict)
        else: logger.debug(f"check_members executado, sem alterações.")
    except Exception as e: logger.error(f"Erro GERAL check_members: {e}", exc_info=True)

async def check_war_attacks_and_report(war, war_type="Guerra Normal"):
    # Sem alterações
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
        curr_t=datetime.now(TIMEZONE).strftime('%H:%M')
        current_state = getattr(war,'state','unknown')

        if war_id in war_cache: war_cache[war_id]['state'] = current_state
        logger.debug(f"Verificando {war_type} ID:{war_id[-15:]} | Estado API:{current_state} Cache:{war_data['state']}")

        if current_state=='inWar':
            m_check=getattr(our_c,'members',[])
            new_attacks_found = False
            for m in m_check:
                tag = getattr(m, 'tag', None)
                if not tag:
                    continue
                m_att=getattr(m,'attacks',[])
                curr_c=len(m_att)
                prev_c=war_data.get('attacks',{}).get(tag,0);
                if curr_c>prev_c:
                    new_attacks_found = True
                    new_att=m_att[prev_c:]
                    logger.info(f"Novo(s) ataque(s) {war_type} ID {war_id[-15:]} por {getattr(m,'name','?')}")
                    for att in new_att:
                        if not all(hasattr(att,a) for a in ['defender_tag','stars','destruction']): logger.warning("Ataque dados faltando."); continue
                        def_n=await get_player_name(att.defender_tag)
                        stars=getattr(att,'stars',0)
                        destr=round(getattr(att,'destruction',0.0),1)
                        star_txt=("⭐"*stars)+("⚫"*(3-stars)) if stars>=0 else "Erro"
                        att_th=getattr(m,'town_hall','?')
                        att_n=getattr(m,'name','?')
                        def_th="?";
                        try:
                            defender_player = await asyncio.wait_for(coc_client.get_player(att.defender_tag), timeout=10.0)
                            def_th = getattr(defender_player, 'town_hall', '?')
                        except (coc_errors.NotFound, asyncio.TimeoutError): def_th = "?"
                        except Exception as e_th: logger.warning(f"Erro buscar TH def {att.defender_tag}: {e_th}"); def_th = "?"
                        msg=(f"{emojis['time']}[{curr_t}] {emojis['war_attack']}**Ataque {war_type}!**\n`{att_n}`(CV{att_th}) vs `{def_n}`(CV{def_th})\n-> {stars}{star_txt} {destr}%")
                        try: await channel.send(msg)
                        except Exception as e: logger.error(f"Erro send atq: {e}")
                    war_data['attacks'][tag]=curr_c
            if not new_attacks_found: logger.debug(f"{war_type} {war_id[-15:]}: Sem novos ataques.")

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
                            if left>0: m_list.append(f"`{getattr(m,'name','?')}`:{left}a.")
                        if m_list:
                            alert_emb=discord.Embed(title=f"{emojis['time']}ALERTA {h}h {war_type.upper()}",description=f"~**{h}h** vs **{getattr(en_c,'name','?')}**!",color=discord.Color.orange());
                            await send_embeds_splitted(channel,alert_emb,"Ataques restantes:",m_list,max_len=1000);
                            logger.info(f"Alerta {h}h enviado {war_type} ID:{war_id[-15:]}")
                        else: logger.info(f"Alerta {h}h {war_type} ID:{war_id[-15:]} - Todos atacaram.")
                        break

        rep_key='war_end_reported' if war_type=="Guerra Normal" else 'league_war_end_reported';
        if rep_key not in war_cache: war_cache[rep_key]={}
        if current_state=='warEnded' and war_id not in war_cache.get(rep_key,{}):
             war_cache[rep_key][war_id]=True; logger.info(f"{war_type} ID:{war_id[-15:]} TERMINOU. Relatório.")
             try:
                 our_s=getattr(our_c,'stars',0); en_s=getattr(en_c,'stars',0); our_d=round(getattr(our_c,'destruction',0.0),2); en_d=round(getattr(en_c,'destruction',0.0),2); our_n=getattr(our_c,'name','Nosso Clã'); en_n=getattr(en_c,'name','Oponente');
                 res, emo, col = "EMPATE", emojis['war_tie'], discord.Color.gold()
                 if our_s>en_s or (our_s==en_s and our_d>en_d): res,emo,col="VITÓRIA",emojis['war_win'],discord.Color.green()
                 elif our_s<en_s or (our_s==en_s and our_d<en_d): res,emo,col="DERROTA",emojis['war_lose'],discord.Color.red()
                 end_emb=discord.Embed(title=f"{emo}{war_type.upper()} FIM - {res}!{emo}",description=f"**{our_n}** vs **{en_n}**",color=col);
                 end_emb.add_field(name=f"{our_n}",value=f"{our_s}⭐({our_d}%)",inline=True);
                 end_emb.add_field(name=f"{en_n}",value=f"{en_s}⭐({en_d}%)",inline=True)
                 end_time_obj = getattr(war,'end_time', None)
                 if end_time_obj and hasattr(end_time_obj, 'time'): end_emb.timestamp = end_time_obj.time.astimezone(TIMEZONE)
                 try: await channel.send(embed=end_emb); await asyncio.sleep(1)
                 except Exception as e: logger.error(f"Erro send embed fim {war_type}: {e}")

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
                         missed_list.append(f"`{name}`(CV{th}):{missed}a. perdidos")
                 if missed_list:
                     missed_emb=discord.Embed(title=f"{emojis['missed_attack']} Ataques Ñ Realizados - {war_type}",description=f"vs **{en_n}**",color=discord.Color.dark_red());
                     await send_embeds_splitted(channel,missed_emb,"Membros:",missed_list,max_len=1000);
                     logger.info(f"Relatório perdidos enviado {war_type} ID:{war_id[-15:]}")
                 else:
                     msg_ok=f"{emojis['success']}Todos atacaram {war_type} vs **{en_n}**!"; await channel.send(msg_ok);
                     logger.info(f"Todos atacaram {war_type} ID:{war_id[-15:]}")
             except Exception as e: logger.error(f"Erro relatório final {war_type} ID {war_id[-15:]}: {e}",exc_info=True)
             if war_id in war_cache:
                  try: del war_cache[war_id]; logger.info(f"Cache {war_type} ID:{war_id[-15:]} removido.")
                  except KeyError: pass
    except Exception as e: logger.error(f"Erro GERAL check_war_attacks ({war_type}): {e}", exc_info=True)

@tasks.loop(minutes=15)
async def check_war():
    # Sem alterações
    global coc_client, war_cache
    if not coc_client: logger.debug("check_war pulado."); return
    try:
        logger.debug("Verificando guerra normal...")
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
                prep_emb=discord.Embed(title=f"⚔️ PREPARAÇÃO GUERRA! ⚔️", description=f"**{getattr(our_c,'name','?')}** vs **{e_n}**\n{size}v{size}"+(f"\nInício:<t:{st_ts}:R>" if st_ts else ""), color=discord.Color.blue());
                chan=bot.get_channel(CHANNEL_ID);
                if chan:
                    try: await chan.send(embed=prep_emb); logger.info(f"Anúncio prep Guerra ID:{war_id[-15:]} enviado.")
                    except Exception as e_send: logger.error(f"Erro send anúncio prep G: {e_send}")
                else: logger.warning("Canal não encontrado anúncio prep G.")
            else: logger.debug(f"Guerra {war_id[-15:]} já em prep.")
            return
        await check_war_attacks_and_report(war, war_type="Guerra Normal")
    except coc_errors.NotFound: logger.info("Nenhuma guerra normal ativa.")
    except coc_errors.ClashOfClansException as e_coc:
        logger.warning(f"Erro API CoC ({type(e_coc).__name__}) check_war: {e_coc}")
    except asyncio.TimeoutError:
        logger.warning(f"Timeout check_war.")
    except AttributeError as e_atr: logger.error(f"Erro Atributo check_war: {e_atr}", exc_info=True)
    except Exception as e: logger.error(f"Erro GERAL check_war: {e}", exc_info=True)

@tasks.loop(minutes=20)
async def check_league_war():
    # Sem alterações
    global coc_client, war_cache
    if not coc_client: logger.debug("check_league_war pulado."); return
    try:
        logger.debug("Verificando grupo liga...")
        lg=await asyncio.wait_for(coc_client.get_league_group(CLAN_TAG),timeout=60.0);
        if not lg or getattr(lg,'state','notInWar')=="notInWar":
            if war_cache.get('league_start_announced',False): logger.info("Liga fim/saiu. Reset flag."); war_cache['league_start_announced']=False
            logger.debug("Não em guerra liga."); return

        chan=bot.get_channel(CHANNEL_ID);
        if not chan: logger.warning("check_league_war: Canal ID não encontrado."); return

        if not war_cache.get('league_start_announced',False):
            war_cache['league_start_announced']=True
            clans=getattr(lg,'clans',[])
            names=[getattr(c,'name','?') for c in clans]
            season=getattr(lg,'season','?')
            lg_emb=discord.Embed(title=f"{emojis['league']} LIGA COMEÇOU! {emojis['league']}", description=f"Temp:{season}\n**Grupo:**\n"+"\n".join(f"- `{n}`" for n in names), color=discord.Color.purple());
            try: await chan.send(embed=lg_emb); logger.info(f"Anúncio Liga temp {season} enviado.")
            except Exception as e_send: logger.error(f"Erro send anúncio Liga: {e_send}")

        try:
            logger.debug("Buscando guerras liga...")
            all_wars = await asyncio.wait_for(lg.get_wars(CLAN_TAG),timeout=60.0)
            if not all_wars : logger.info("Nenhuma guerra liga encontrada."); return
        except Exception as e: logger.error(f"Erro get_wars liga: {e}"); return

        active_war_found = False
        for war in all_wars:
             if not war or not all(hasattr(war,a) for a in ['state','preparation_start_time','clan','opponent']): logger.warning(f"Guerra liga inválida: {war}"); continue
             try:
                 our_c=war.clan if hasattr(war, 'clan') and war.clan.tag==CLAN_TAG else getattr(war,'opponent', None)
                 en_c=war.opponent if hasattr(war, 'clan') and war.clan.tag==CLAN_TAG else getattr(war,'clan', None)
                 if not our_c or not en_c: logger.error("Erro ID clãs G Liga."); continue
                 prep_time_obj = getattr(war,'preparation_start_time', None)
                 prep_time_iso = prep_time_obj.time.isoformat() if prep_time_obj and hasattr(prep_time_obj, 'time') else datetime.now().isoformat()
                 war_id=f"league-{getattr(our_c,'tag','?')}-{getattr(en_c,'tag','?')}-{prep_time_iso}";
                 rep_key='league_war_end_reported'
             except Exception as e: logger.error(f"Erro gerar ID G Liga: {e}"); continue

             if rep_key not in war_cache: war_cache[rep_key]={}
             if war.state=='warEnded' and war_id in war_cache.get(rep_key,{}): logger.debug(f"G Liga {war_id[-15:]} já reportada."); continue

             active_war_found = True
             if war.state=='preparation':
                 if war_id not in war_cache: war_cache[war_id]={'attacks':{},'time_alerts':set(),'state':'unknown'}
                 if war_cache.get(war_id,{}).get('state')!='preparation':
                     logger.info(f"Nova G Liga prep. ID: {war_id[-15:]}")
                     war_cache[war_id]['state']='preparation'
                     start_time_obj = getattr(war,'start_time', None)
                     st_ts = int(start_time_obj.time.astimezone(TIMEZONE).timestamp()) if start_time_obj and hasattr(start_time_obj, 'time') else None
                     round_n="?";
                     prep_emb=discord.Embed(title=f"{emojis['league']}PREP LIGA(R{round_n})", description=f"**{getattr(our_c,'name','?')}** vs **{getattr(en_c,'name','?')}**"+(f"\nInício:<t:{st_ts}:R>" if st_ts else ""), color=discord.Color.blue());
                     try: await chan.send(embed=prep_emb); logger.info(f"Anúncio prep Liga ID:{war_id[-15:]} enviado.")
                     except Exception as e_send: logger.error(f"Erro send anúncio prep Liga: {e_send}")
                 else: logger.debug(f"G Liga {war_id[-15:]} já em prep.")
                 continue
             logger.debug(f"Chamando check_attacks para Liga ID:{war_id[-15:]}")
             await check_war_attacks_and_report(war, war_type="Guerra de Liga")
             # break
        if not active_war_found: logger.info("Nenhuma G Liga ativa ou pendente encontrada.")
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
    global raid_weekend_cache, coc_client
    # Adicionado check explícito
    if not coc_client:
        logger.debug("check_raid_weekend pulado: cliente CoC inválido/não inicializado.")
        return
    try:
        logger.debug("Verificando Raid Weekend...")
        # *** CORREÇÃO APLICADA AQUI - Mantém chamada documentada p/ v3.9.1 ***
        rl=await asyncio.wait_for(coc_client.get_clan_capital_raid_seasons(CLAN_TAG, limit=1), timeout=45.0)

        channel=bot.get_channel(CHANNEL_ID)
        if not channel: logger.warning("check_raid_weekend: Canal ID não encontrado."); return

        if not rl:
             cached=raid_weekend_cache.get('current_raid');
             if cached and cached.get('state') in ['ongoing', 'ended_due_to_api_error']:
                  logger.warning("API não retornou raids, mas cache indica ongoing/erro.");
                  raid_weekend_cache['current_raid']['state']='ended_due_to_api_error'
             else: logger.info("Nenhum dado Raid Weekend na API.")
             return

        curr_r=rl[0];
        if not curr_r or not all(hasattr(curr_r,a) for a in ['start_time','state','capital_total_loot']):
            logger.error(f"Objeto Raid inválido: {curr_r}"); return

        curr_t=datetime.now(TIMEZONE).strftime('%H:%M')
        start_time_obj = getattr(curr_r, 'start_time', None)
        r_id = f"{CLAN_TAG}-{start_time_obj.time.isoformat()}" if start_time_obj and hasattr(start_time_obj, 'time') else f"{CLAN_TAG}-unknown_start"
        cached=raid_weekend_cache.get('current_raid')
        prev_id=cached['id'] if cached else None
        prev_state=cached['state'] if cached else None

        async def send_raid_report(raid_data, title_emoji, title_text, color, report_type="final"):
            # Sem alterações
            start_str = raid_data.get('start_time_str','N/A')
            loot = raid_data.get('total_loot',0)
            state = raid_data.get('state','N/A')
            emb = discord.Embed(title=f"{title_emoji}{title_text}{title_emoji}", description=f"Início: {start_str}\nOuro Total: **{loot:,}**\nEstado: {state}", color=color);
            members_data = raid_data.get('members',{})
            if members_data:
                try:
                    clan_now = await get_clan_data()
                    m_map = {m.tag:m.name for m in getattr(clan_now,'members',[]) if hasattr(m,'tag')} if clan_now else {}
                except Exception: m_map = {}
                sorted_members = sorted(members_data.items(), key=lambda i:i[1].get('loot', 0), reverse=True)
                top_list = [f"{i}.`{m_map.get(tag, data.get('name','?'))}`: **{data.get('loot',0):,}**" for i, (tag, data) in enumerate(sorted_members[:5], 1)]
                if top_list: emb.add_field(name=f"🌟 Top Contribs ({report_type}) 🌟", value="\n".join(top_list), inline=False)
            try: await channel.send(embed=emb)
            except Exception as e: logger.error(f"Erro send embed relatório raid {report_type}: {e}")

        if r_id != prev_id:
            logger.info(f"Novo Raid ID: {r_id}. Anterior: {prev_id}")
            if prev_id and prev_state in ['ongoing', 'ended_due_to_api_error']:
                logger.info(f"Raid anterior ({prev_id}) '{prev_state}'. Relatório presumido.")
                await send_raid_report(cached, emojis['clan_capital'], "RAID (ANTERIOR) TERMINOU!", discord.Color.dark_grey(), report_type="presumido")

            start_time_str = start_time_obj.time.astimezone(TIMEZONE).strftime('%d/%m %H:%M') if start_time_obj and hasattr(start_time_obj, 'time') else "N/A"
            members_dict = {m.tag:{'name':getattr(m,'name','?'),'loot':getattr(m,'capital_resources_looted',0)} for m in getattr(curr_r,'members',[]) if hasattr(m,'tag')}
            districts_dict = {d.id:{'name':getattr(d,'name','?'),'destruction':getattr(d,'destruction_percent',0)} for d in getattr(curr_r,'attack_log',[]) if hasattr(d,'id')}
            raid_weekend_cache['current_raid'] = { 'id': r_id, 'start_time': start_time_obj, 'start_time_str': start_time_str, 'state': curr_r.state, 'members': members_dict, 'districts': districts_dict, 'total_loot': getattr(curr_r,'capital_total_loot',0) };
            logger.info(f"Cache raid ID: {r_id}, Estado: {curr_r.state}")
            if curr_r.state == 'ongoing':
                start_emb=discord.Embed(title=f"{emojis['raid']}RAID COMEÇOU!{emojis['raid']}",description=f"Ataquem Capital!\nInício: {start_time_str}",color=discord.Color.red());
                try: await channel.send(embed=start_emb); logger.info(f"Anúncio início Raid ID:{r_id} enviado.")
                except Exception as e: logger.error(f"Erro send anúncio início Raid: {e}")

        elif r_id == prev_id:
            logger.debug(f"Mesmo Raid ID: {r_id}. API: {curr_r.state}, Cache: {prev_state}")
            if prev_state == 'ended' and curr_r.state == 'ongoing':
                raid_weekend_cache['current_raid']['state'] = 'ongoing'
                start_emb=discord.Embed(title=f"{emojis['raid']}RAID RECOMEÇOU?{emojis['raid']}",description=f"Estado->'ongoing'.\nInício: {cached['start_time_str']}",color=discord.Color.orange());
                try: await channel.send(embed=start_emb); logger.warning(f"Raid {r_id}: ended->ongoing.")
                except Exception as e: logger.error(f"Erro send anúncio reinício Raid: {e}")
            elif prev_state != 'ended' and curr_r.state == 'ended':
                logger.info(f"Raid {r_id} terminou. Relatório final.")
                raid_weekend_cache['current_raid']['state'] = 'ended'
                raid_weekend_cache['current_raid']['total_loot'] = getattr(curr_r,'capital_total_loot',cached.get('total_loot',0));
                raid_weekend_cache['current_raid']['members'] = {m.tag:{'name':getattr(m,'name','?'),'loot':getattr(m,'capital_resources_looted',0)} for m in getattr(curr_r,'members',[]) if hasattr(m,'tag')};
                raid_weekend_cache['current_raid']['districts'] = {d.id:{'name':getattr(d,'name','?'),'destruction':getattr(d,'destruction_percent',0)} for d in getattr(curr_r,'attack_log',[]) if hasattr(d,'id')};
                await send_raid_report(raid_weekend_cache['current_raid'], emojis['clan_capital'], "RAID TERMINOU!", discord.Color.dark_grey(), report_type="final")
                logger.info(f"Relatório final Raid ID:{r_id} enviado.")
            elif curr_r.state == 'ongoing':
                logger.debug(f"Raid {r_id} ongoing. Verificando progresso.")
                new_m_loot={}
                loot_msgs=[]
                progress_found = False
                try: clan_now = await get_clan_data(); m_map = {m.tag:m.name for m in getattr(clan_now,'members',[]) if hasattr(m,'tag')} if clan_now else {}
                except Exception: m_map = {}
                curr_m_list = getattr(curr_r,'members',[]); cached_members = cached.get('members', {})
                for m in curr_m_list:
                    tag = getattr(m, 'tag', None)
                    if not tag:
                        continue
                    c_loot=getattr(m,'capital_resources_looted',0)
                    m_n=getattr(m,'name','?')
                    new_m_loot[tag]={'name':m_n,'loot':c_loot};
                    p_loot = cached_members.get(tag,{'loot':0})['loot']
                    diff = c_loot - p_loot
                    if diff > 0:
                        progress_found = True; display_name = m_map.get(tag,m_n)
                        loot_msgs.append(f"{emojis['raid']}`{display_name}` +{diff:,} Ouro! (Total: {c_loot:,})")
                if loot_msgs:
                    logger.info(f"{len(loot_msgs)} alterações loot Raid {r_id}.")
                    full_msg=f"{emojis['time']}[{curr_t}] {emojis['clan_capital']} Progresso Raid:\n"+"\n".join(loot_msgs);
                    try:
                        if len(full_msg)>1950: await channel.send(full_msg[:1950]+"...")
                        else: await channel.send(full_msg)
                    except Exception as e: logger.error(f"Erro send progresso loot raid: {e}")
                raid_weekend_cache['current_raid']['members'] = new_m_loot;

                new_dist_state={}
                dist_msgs=[]
                curr_a_log = getattr(curr_r,'attack_log',[]); cached_districts = cached.get('districts', {})
                for d in curr_a_log:
                    if not all(hasattr(d,a) for a in ['id','name','destruction_percent']):
                        continue
                    d_id = d.id
                    c_dest = getattr(d,'destruction_percent',0)
                    d_n = getattr(d,'name','?')
                    new_dist_state[d_id]={'name':d_n,'destruction':c_dest};
                    p_dest = cached_districts.get(d_id,{'destruction':0})['destruction'];
                    if c_dest == 100 and p_dest < 100:
                         progress_found = True; dist_msgs.append(f"🎉 Distrito **{d_n}** 100%!")
                if dist_msgs:
                     logger.info(f"{len(dist_msgs)} distritos destruídos Raid {r_id}.")
                     try: await channel.send(f"{emojis['time']}[{curr_t}]\n"+"\n".join(dist_msgs))
                     except Exception as e: logger.error(f"Erro send msg distrito destruído: {e}")
                raid_weekend_cache['current_raid']['districts'] = new_dist_state;
                raid_weekend_cache['current_raid']['total_loot'] = getattr(curr_r,'capital_total_loot',cached.get('total_loot',0))
                if not progress_found: logger.debug(f"Raid {r_id} ongoing, sem progresso.")
            else: logger.info(f"Raid {r_id} estado '{curr_r.state}' (cache era '{prev_state}').")
    # *** CORREÇÃO APLICADA AQUI - Tratamento genérico refinado ***
    except coc_errors.ClashOfClansException as e_coc:
        logger.warning(f"Erro API CoC ({type(e_coc).__name__}) check_raid: {e_coc}")
    except asyncio.TimeoutError:
         logger.warning(f"Timeout check_raid.")
    except Exception as e:
        logger.error(f"Erro GERAL check_raid: {e}", exc_info=True); # Log traceback para erros inesperados

# --- Eventos e Comandos ---

@bot.event
async def on_ready():
    # Sem alterações
    global coc_client
    logger.info(f'Bot {bot.user.name} ({bot.user.id}) online e pronto!')
    logger.info(f"Monitorando Clã: {CLAN_TAG} | Canal ID: {CHANNEL_ID}")
    channel=bot.get_channel(CHANNEL_ID)
    if not channel: logger.error(f"Canal ID {CHANNEL_ID} NÃO ENCONTRADO.")
    logger.info("Tentando inicializar e logar cliente CoC...")
    login_successful = await initialize_coc_client()
    if not login_successful:
        logger.critical("Falha login CoC. API indisponível.")
        if channel:
            try:
                await channel.send(f"{emojis['error']}**ERRO CRÍTICO:** Falha login API CoC.")
            except Exception as e_send_err:
                logger.error(f"Erro ao enviar msg (falha login CoC) para canal {CHANNEL_ID}: {e_send_err}")
        logger.warning("Bot rodando apenas com Discord.")
    else:
        logger.info("Cliente CoC OK. Verificando acesso clã...")
        try:
            clan_test = await get_clan_data();
            if clan_test:
                logger.info(f"Acesso API CoC e clã '{getattr(clan_test,'name',CLAN_TAG)}' OK.")
                task_list = [check_donations, check_members, check_war, check_league_war, check_raid_weekend]; start_log = []
                logger.info("Iniciando tasks monitoramento...")
                for task in task_list:
                    task_name = task.coro.__name__
                    if not task.is_running():
                        try: task.start(); start_log.append(f"{task_name}:OK"); logger.debug(f"Task '{task_name}' iniciada.")
                        except RuntimeError as e_task: logger.error(f"Erro start task {task_name}: {e_task}"); start_log.append(f"{task_name}:ERRO")
                    else: start_log.append(f"{task_name}:JáRodando"); logger.warning(f"Task '{task_name}' já rodando.")
                logger.info(f"Status tasks: {'; '.join(start_log)}.")
                if channel:
                    try:
                        await channel.send(f"🤖**Bot Online e Monitorando!**🤖\nClã:`{getattr(clan_test,'name',CLAN_TAG)}`")
                    except Exception as e_send_err:
                         logger.error(f"Erro ao enviar msg (online) para canal {CHANNEL_ID}: {e_send_err}")
                else: logger.info("Inicialização completa (sem canal msg).")
            else:
                logger.critical(f"FALHA GRAVE: Não obter dados clã {CLAN_TAG} pós-login.")
                if channel:
                    try:
                        await channel.send(f"{emojis['error']}**ERRO CRÍTICO:** Falha obter dados clã `{CLAN_TAG}`.")
                    except Exception as e_send_err:
                        logger.error(f"Erro ao enviar msg (falha obter clã) para canal {CHANNEL_ID}: {e_send_err}")
        except Exception as e_ready_get:
             logger.critical(f"FALHA GRAVE: Erro verificar clã on_ready: {e_ready_get}", exc_info=True)
             if channel:
                 try:
                     await channel.send(f"{emojis['error']}**ERRO CRÍTICO:** Erro API on_ready.")
                 except Exception as e_send_err:
                     logger.error(f"Erro ao enviar msg (erro API on_ready) para canal {CHANNEL_ID}: {e_send_err}")

@bot.event
async def on_command_error(ctx, error):
    # Sem alterações
    if isinstance(error, commands.CommandNotFound): return
    if isinstance(error, commands.MissingRequiredArgument): await ctx.send(f"{emojis['error']} Falta arg: `{error.param.name}`.")
    elif isinstance(error, commands.MissingPermissions): await ctx.send(f"{emojis['error']} Sem perm: `{', '.join(error.missing_permissions)}`.")
    elif isinstance(error, commands.ChannelNotFound): await ctx.send(f"{emojis['error']} Canal ñ enc: `{error.argument}`.")
    elif isinstance(error, commands.CommandInvokeError):
         original=error.original; logger.error(f"Erro cmd '{ctx.command}': {original}",exc_info=True)
         if isinstance(original, coc_errors.NotFound): await ctx.send(f"{emojis['error']} API: Ñ enc.")
         elif isinstance(original, coc_errors.AuthenticationError): await ctx.send(f"{emojis['error']} API: Autenticação falhou.")
         elif isinstance(original, coc_errors.ClashOfClansException): await ctx.send(f"{emojis['warning']} API CoC Error: {type(original).__name__}.") # Mostra nome do erro genérico
         elif isinstance(original, asyncio.TimeoutError): await ctx.send(f"{emojis['error']} API: Timeout.")
         elif not coc_client: await ctx.send(f"{emojis['error']} API CoC não conectada.")
         else: await ctx.send(f"{emojis['error']} Erro interno cmd.")
    elif isinstance(error, commands.CheckFailure): await ctx.send(f"{emojis['error']} Sem permissão.")
    elif isinstance(error, commands.BadArgument): await ctx.send(f"{emojis['error']} Argumento inválido.")
    else: logger.error(f"Erro cmd ñ tratado: {type(error).__name__}-{error}",exc_info=True); await ctx.send(f"{emojis['error']} Erro inesperado cmd.")

# --- Comandos ---

async def display_attacks_remaining(ctx, war, war_type="Guerra"):
    # Sem alterações
    if not war or war.state not in ['inWar', 'preparation']: await ctx.send(f"{emojis['warning']} Clã não em {war_type} ativa."); return
    if not coc_client: await ctx.send(f"{emojis['error']} API CoC indisponível."); return
    our_c = war.clan if hasattr(war,'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'opponent', None)
    en_c = war.opponent if hasattr(war,'clan') and war.clan.tag == CLAN_TAG else getattr(war, 'clan', None)
    if not our_c or not en_c: await ctx.send(f"{emojis['error']} Erro identificar clãs {war_type}."); return

    state_info = ""; time_ref = None
    if war.state == 'preparation' and hasattr(war, 'start_time') and hasattr(war.start_time, 'time'):
        time_ref = war.start_time.time.astimezone(TIMEZONE); state_info = f"(Prep - Início: <t:{int(time_ref.timestamp())}:R>)"
    elif war.state == 'inWar' and hasattr(war, 'end_time') and hasattr(war.end_time, 'time'):
        time_ref = war.end_time.time.astimezone(TIMEZONE); state_info = f"(Guerra - Fim: <t:{int(time_ref.timestamp())}:R>)"
    attacks_per_member = getattr(war, 'attacks_per_member', 1); remaining_list = []
    members_in_war = getattr(our_c, 'members', [])
    if not members_in_war: await ctx.send(f"{emojis['warning']} Lista membros {war_type} indisponível."); return
    for member in members_in_war:
        attacks_done = len(getattr(member, 'attacks', [])); attacks_left = attacks_per_member - attacks_done
        if attacks_left > 0: name = getattr(member, 'name', '?'); th = getattr(member, 'town_hall', '?'); remaining_list.append(f"`{name}` (CV{th}): {attacks_left}a")
    title = f"{emojis['war_attack']} Ataques Restantes - {war_type} vs {getattr(en_c, 'name', '?')}"
    base_embed = discord.Embed(title=title, description=state_info, color=discord.Color.blue())
    if time_ref: base_embed.timestamp = time_ref
    base_embed.set_footer(text=f"Verif: {datetime.now(TIMEZONE).strftime('%d/%m %H:%M')}")
    if not remaining_list: await ctx.send(embed=base_embed.add_field(name="Situação", value=f"{emojis['success']} Todos atacaram!", inline=False))
    else: await send_embeds_splitted(ctx.channel, base_embed, "Quem Falta:", remaining_list, max_len=1000)

@bot.command(name='status', help="Exibe status atual bot e clã.")
@commands.has_permissions(administrator=True)
async def status_command(ctx):
    # Sem alterações
    if not coc_client: await ctx.send(f"{emojis['error']} API CoC indisponível."); return
    async with ctx.typing():
        try:
            clan=await get_clan_data();
            if not clan: await ctx.send(f"{emojis['error']}Erro obter dados clã `{CLAN_TAG}`!"); return
            c_n=getattr(clan,'name','?')
            c_t=getattr(clan,'tag',CLAN_TAG)
            c_desc=getattr(clan,'description',"S/Desc") or "S/Desc"
            c_lvl=getattr(clan,'level','?')
            m_cnt=getattr(clan,'member_count','?')
            loc=getattr(getattr(clan,'location',None),'name',"Global")
            c_pts=getattr(clan,'points','?')
            w_lg=getattr(getattr(clan,'war_league',None),'name',"N/A")
            cap_lg=getattr(getattr(clan,'capital_league',None),'name',"N/A")
            b_url=getattr(getattr(clan,'badge',None),'url',None)
            emb=discord.Embed(title=f"{emojis['info']} Status - {c_n} ({c_t})",description=c_desc,color=discord.Color.blue());
            if b_url: emb.set_thumbnail(url=b_url)
            emb.add_field(name="Nível",value=c_lvl,inline=True); emb.add_field(name="Membros",value=f"{m_cnt}/50",inline=True); emb.add_field(name="Local",value=loc,inline=True); emb.add_field(name="Troféus",value=f"{c_pts:,}🏆",inline=True); emb.add_field(name="LGuerra",value=w_lg,inline=True); emb.add_field(name="LCapital",value=cap_lg,inline=True)

            ws = f"{emojis['warning']}Verificando...";
            try:
                war = await asyncio.wait_for(coc_client.get_current_war(CLAN_TAG), timeout=30.0)
                if not war or getattr(war,'state', 'notInWar') == 'notInWar' or getattr(war, 'is_cwl', False): ws = f"{emojis['success']}Não em G. Normal."
                elif hasattr(war, 'state'):
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
                        if state == 'preparation' and st_ts: ws = f"{emojis['time']} Prep vs `{opp_n}`(<t:{st_ts}:R>)"
                        elif state == 'inWar' and et_ts: ws = f"{emojis['war_attack']} Guerra vs `{opp_n}`(<t:{et_ts}:R>)\n**{our_s}**⭐vs**{opp_s}**⭐"
                        elif state == 'warEnded':
                            our_d=round(getattr(our_w,'destruction',0.0),1)
                            opp_d=round(getattr(opp,'destruction',0.0),1)
                            emoji_r=emojis['war_win'] if our_s>opp_s or (our_s==opp_s and our_d>opp_d) else (emojis['war_lose'] if our_s<opp_s or (our_s==opp_s and our_d<opp_d) else emojis['war_tie']); ws = f"{emoji_r} Fim vs `{opp_n}`"
                        else: ws = f"{emojis['warning']} Estado G: {state}"
                    else: ws = f"{emojis['warning']} Dados G incompletos."
                else: ws = f"{emojis['warning']} Dados G inválidos."
            except coc_errors.NotFound: ws = f"{emojis['success']}Não em G. Normal."
            except coc_errors.ClashOfClansException as e_coc: ws = f"{emojis['error']}Erro API G ({type(e_coc).__name__})"; logger.warning(f"Erro API GW !status: {e_coc}")
            except asyncio.TimeoutError: ws=f"{emojis['error']}Timeout G."; logger.warning("Timeout GW !status")
            except Exception as e_stat_war: ws = f"{emojis['error']}Erro G"; logger.error(f"Erro GW !status: {e_stat_war}", exc_info=True)
            emb.add_field(name="G. Normal", value=ws, inline=False)

            ls=f"{emojis['warning']}Verificando...";
            try:
                lg=await asyncio.wait_for(coc_client.get_league_group(CLAN_TAG),timeout=45.0);
                if lg and getattr(lg,'state','notInWar')!="notInWar":
                    season=getattr(lg,'season','?')
                    state=getattr(lg,'state','?')
                    ls=f"{emojis['league']} Em Liga({season})|E:{state}"
                    active_w=None;
                    try: lg_wars = await asyncio.wait_for(lg.get_wars(CLAN_TAG),timeout=45.0);
                    except Exception: lg_wars=[]
                    for w in lg_wars:
                        if getattr(w,'state',None) in ['inWar','preparation']: active_w=w; break;
                    if active_w:
                        our_w_lg = active_w.clan if hasattr(active_w.clan, 'tag') and active_w.clan.tag == CLAN_TAG else getattr(active_w, 'opponent', None)
                        opp_lg = active_w.opponent if hasattr(active_w.clan, 'tag') and active_w.clan.tag == CLAN_TAG else getattr(active_w, 'clan', None)
                        if our_w_lg and opp_lg:
                           opp_lg_n=getattr(opp_lg,'name','?')
                           st_em=emojis['war_attack'] if active_w.state=='inWar' else emojis['time'];
                           time_obj = active_w.end_time if active_w.state=='inWar' else active_w.start_time
                           t_rel = f"<t:{int(time_obj.time.astimezone(TIMEZONE).timestamp())}:R>" if time_obj and hasattr(time_obj, 'time') else "?"
                           state_t="Guerra" if active_w.state=='inWar' else "Prep";
                           ls+=f"\n{st_em} Rodada vs `{opp_lg_n}`({state_t},{t_rel})";
                           if active_w.state=='inWar':
                               our_s=getattr(our_w_lg,'stars',0)
                               opp_s=getattr(opp_lg,'stars',0)
                               ls+=f"\n**{our_s}**⭐vs**{opp_s}**⭐"
                        else: ls+=f"\n{emojis['error']}Erro ID clãs rodada."
                    else: ls+=f"\n{emojis['info']}Nenhuma rodada ativa."
                else: ls=f"{emojis['success']} Não em Liga."
            except coc_errors.NotFound: ls=f"{emojis['success']}Não em Liga."
            except coc_errors.ClashOfClansException as e_coc: ls = f"{emojis['error']}Erro API Liga ({type(e_coc).__name__})"; logger.warning(f"Erro API Liga !status: {e_coc}")
            except asyncio.TimeoutError: ls=f"{emojis['error']}Timeout Liga."; logger.warning("Timeout Liga !status")
            except Exception as e_lg: ls=f"{emojis['error']}Erro Liga"; logger.warning(f"Erro Liga !status: {e_lg}", exc_info=True)
            emb.add_field(name="G. Liga", value=ls, inline=False)

            rs=f"{emojis['warning']}Verificando...";
            try:
                # *** CORREÇÃO APLICADA AQUI - Nome do Método ***
                rl=await asyncio.wait_for(coc_client.get_clan_capital_raid_seasons(CLAN_TAG,limit=1),timeout=30.0);
                if rl and rl[0] and hasattr(rl[0],'state'):
                    r=rl[0]
                    state=r.state
                    loot=getattr(r,'capital_total_loot',0)
                    end_time_obj = getattr(r, 'end_time', None)
                    et_ts = int(end_time_obj.time.astimezone(TIMEZONE).timestamp()) if end_time_obj and hasattr(end_time_obj, 'time') else None
                    if state=='ongoing' and et_ts: rs=f"{emojis['raid']} Raid ativo!(<t:{et_ts}:R>)\nOuro:**{loot:,}**"
                    elif state=='ended':
                         start_time_obj = getattr(r, 'start_time', None)
                         st_str = start_time_obj.time.astimezone(TIMEZONE).strftime('%d/%m') if start_time_obj and hasattr(start_time_obj, 'time') else '?'
                         rs=f"{emojis['clan_capital']} Raid inativo. Último ({st_str}): **{loot:,}** Ouro."
                    else: rs=f"{emojis['clan_capital']} Raid inativo(E:{state})."
                else: rs=f"{emojis['clan_capital']} Sem info raid."
            except coc_errors.NotFound: rs=f"{emojis['clan_capital']}Sem info raid (NotFound)."
            except coc_errors.ClashOfClansException as e_coc: rs = f"{emojis['error']}Erro API Raid ({type(e_coc).__name__})"; logger.warning(f"Erro API Raid !status: {e_coc}")
            except asyncio.TimeoutError: rs=f"{emojis['error']}Timeout Raid."; logger.warning("Timeout Raid !status")
            except Exception as e_rs: rs=f"{emojis['error']}Erro Raid"; logger.warning(f"Erro Raid !status: {e_rs}", exc_info=True)
            emb.add_field(name="Raid", value=rs, inline=False)

            lat=bot.latency*1000
            emb.add_field(name="Bot", value=f"{emojis['success']}Online|Lat:{lat:.0f}ms", inline=False)
            emb.set_footer(text=f"Verif:{datetime.now(TIMEZONE).strftime('%H:%M:%S')}")
            await ctx.send(embed=emb)
        except Exception as e: logger.error(f"Erro GERAL cmd status:{e}", exc_info=True); await ctx.send(f"{emojis['error']}Erro status:{e}")

@bot.command(name='top', help="Rankings: top [tipo] [limite=10]")
@commands.has_permissions(administrator=True)
async def top_command(ctx, tipo: str = "doacoes", limite: int = 10):
    # Sem alterações
    if not coc_client: await ctx.send(f"{emojis['error']} API CoC indisponível."); return
    tipo=tipo.lower().strip()
    limite=min(50,max(1,limite))
    valid=["doacoes","doações","recebidos","trofeus","troféus","capital"]
    if tipo not in valid: await ctx.send(f"{emojis['error']}Tipo inválido!"); return
    async with ctx.typing():
        try:
            clan=await get_clan_data();
            if not clan or not hasattr(clan,'members') or not clan.members: await ctx.send(f"{emojis['error']}Erro dados membros `{CLAN_TAG}`!"); return
            title=""
            color=discord.Color.blue()
            fmt_list=[]
            m_list=list(clan.members) if clan.members else []
            if not m_list: await ctx.send(f"{emojis['warning']} Lista membros vazia."); return

            if tipo in ["doacoes","doações"]: title=f"{emojis['donation']}Top {limite} Doadores"; color=discord.Color.green(); s_list=sorted(m_list,key=lambda m:getattr(m,'donations',0),reverse=True)[:limite]; fmt_list=[f"{i}.`{getattr(m,'name','?')}`(CV{getattr(m,'town_hall','?')}):**{getattr(m,'donations',0):,}**" for i,m in enumerate(s_list,1)]
            elif tipo=="recebidos": title=f"{emojis['donation']}Top {limite} Recebedores"; color=discord.Color.orange(); s_list=sorted(m_list,key=lambda m:getattr(m,'received',0),reverse=True)[:limite]; fmt_list=[f"{i}.`{getattr(m,'name','?')}`(CV{getattr(m,'town_hall','?')}):**{getattr(m,'received',0):,}**" for i,m in enumerate(s_list,1)]
            elif tipo in ["trofeus","troféus"]: title=f"{emojis['trophy']}Top {limite} Troféus"; color=discord.Color.gold(); s_list=sorted(m_list,key=lambda m:getattr(m,'trophies',0),reverse=True)[:limite]; fmt_list=[f"{i}.`{getattr(m,'name','?')}`(CV{getattr(m,'town_hall','?')}):**{getattr(m,'trophies',0):,}**🏆" for i,m in enumerate(s_list,1)]
            elif tipo=="capital":
                title=f"{emojis['clan_capital']}Top {limite} Capital(Últ.Raid)"; color=0x9B59B6;
                try:
                    # *** CORREÇÃO APLICADA AQUI - Nome do Método ***
                    rl=await asyncio.wait_for(coc_client.get_clan_capital_raid_seasons(CLAN_TAG,limit=1),timeout=30.0);
                    if not rl or not rl[0] or not hasattr(rl[0],'members') or not rl[0].members: await ctx.send(f"{emojis['warning']}Sem dados membros últ. raid."); return
                    m_data={m.tag:{'name':getattr(m,'name','?'),'loot':getattr(m,'capital_resources_looted',0)} for m in rl[0].members if hasattr(m,'tag')};
                    s_raid=sorted(m_data.items(),key=lambda i:i[1]['loot'],reverse=True)[:limite];
                    fmt_list=[f"{i}.`{d['name']}`:**{d['loot']:,}**{emojis['clan_capital']}" for i,(t,d) in enumerate(s_raid,1)]
                except coc_errors.NotFound: await ctx.send(f"{emojis['warning']} Sem histórico raid ou clã não encontrado.")
                except coc_errors.ClashOfClansException as e_coc: await ctx.send(f"{emojis['error']}Erro API Capital ({type(e_coc).__name__})."); logger.warning(f"Erro API Capital !top: {e_coc}")
                except asyncio.TimeoutError: await ctx.send(f"{emojis['error']}Timeout Capital."); logger.warning("Timeout Capital !top")
                except Exception as e: logger.error(f"Erro top capital:{e}",exc_info=True); await ctx.send(f"{emojis['error']}Erro Capital:{e}"); return

            if not fmt_list: await ctx.send(f"{emojis['warning']} Nenhum dado para ranking '{tipo}'."); return
            base_emb=discord.Embed(title=title,color=color)
            c_n=getattr(clan,'name',CLAN_TAG)
            base_emb.set_footer(text=f"{c_n}|{datetime.now(TIMEZONE).strftime('%d/%m %H:%M')}")
            await send_embeds_splitted(ctx.channel,base_emb,"Ranking:",fmt_list,max_len=1000)
        except Exception as e: logger.error(f"Erro GERAL top:{e}",exc_info=True); await ctx.send(f"{emojis['error']}Erro ranking:{e}")

@bot.command(name='ataques', help="Ataques restantes guerra normal.")
@commands.has_permissions(administrator=True)
async def ataques_command(ctx):
    # Sem alterações
    if not coc_client: await ctx.send(f"{emojis['error']} API CoC indisponível."); return
    async with ctx.typing():
        try:
            war = await asyncio.wait_for(coc_client.get_current_war(CLAN_TAG), timeout=30.0)
            if war and getattr(war, 'is_cwl', False): await ctx.send(f"{emojis['warning']}Clã em Liga. Use `!ligaataques`."); return
            await display_attacks_remaining(ctx, war, war_type="Guerra Normal")
        except coc_errors.NotFound: await ctx.send(f"{emojis['warning']}Clã não em guerra normal.")
        except coc_errors.ClashOfClansException as e_coc: await ctx.send(f"{emojis['error']}Erro API ({type(e_coc).__name__}) guerra."); logger.warning(f"Erro API !ataques: {e_coc}")
        except asyncio.TimeoutError: await ctx.send(f"{emojis['error']}Timeout guerra."); logger.warning("Timeout !ataques command")
        except Exception as e: logger.error(f"Erro !ataques: {e}", exc_info=True); await ctx.send(f"{emojis['error']}Erro verificar ataques guerra.")

@bot.command(name='ligaataques', help="Ataques restantes guerra liga.")
@commands.has_permissions(administrator=True)
async def liga_ataques_command(ctx):
    # Sem alterações
    if not coc_client: await ctx.send(f"{emojis['error']} API CoC indisponível."); return
    async with ctx.typing():
        try:
            lg = await asyncio.wait_for(coc_client.get_league_group(CLAN_TAG), timeout=45.0)
            if not lg or getattr(lg, 'state', 'notInWar') == "notInWar": await ctx.send(f"{emojis['warning']}Clã não em Liga!"); return
            curr_war = None
            lg_wars = [];
            try: lg_wars = await asyncio.wait_for(lg.get_wars(CLAN_TAG), timeout=45.0)
            except Exception as e_get_wars: logger.warning(f"Erro buscar guerras liga !ligaataques: {e_get_wars}")
            for w in lg_wars:
                if getattr(w, 'state', None) == 'inWar': curr_war = w; break
                elif getattr(w, 'state', None) == 'preparation': curr_war = w
            if not curr_war: await ctx.send(f"{emojis['warning']}Nenhuma G.Liga ativa encontrada."); return
            await display_attacks_remaining(ctx, curr_war, war_type="Guerra de Liga")
        except coc_errors.NotFound: await ctx.send(f"{emojis['warning']}Clã não em Liga (grupo ñ enc).")
        except coc_errors.ClashOfClansException as e_coc: await ctx.send(f"{emojis['error']}Erro API ({type(e_coc).__name__}) liga."); logger.warning(f"Erro API !ligaataques: {e_coc}")
        except asyncio.TimeoutError: await ctx.send(f"{emojis['error']}Timeout liga."); logger.warning("Timeout !ligaataques command")
        except Exception as e: logger.error(f"Erro !ligaataques: {e}", exc_info=True); await ctx.send(f"{emojis['error']}Erro verificar ataques liga.")

@bot.command(name='membro', help="Detalhes jogador: !membro <#TAG>")
@commands.has_permissions(administrator=True)
async def membro_command(ctx, player_tag: str = None):
    # Sem alterações
    if not coc_client: await ctx.send(f"{emojis['error']} API CoC indisponível."); return
    if not player_tag: await ctx.send(f"{emojis['error']}Forneça tag."); return
    player_tag=player_tag.strip().upper()
    if not player_tag.startswith('#'): player_tag='#'+player_tag
    if not coc.utils.is_valid_tag(player_tag): await ctx.send(f"{emojis['error']}Tag `{player_tag}` inválida."); return
    async with ctx.typing():
        try:
            player=await asyncio.wait_for(coc_client.get_player(player_tag),timeout=20.0);
            p_n=getattr(player,'name','?')
            p_t=getattr(player,'tag',player_tag)
            p_th=getattr(player,'town_hall','?')
            p_xp=getattr(player,'exp_level','?')
            p_lg=getattr(player,'league',None)
            p_tr=getattr(player,'trophies',0)
            p_btr=getattr(player,'best_trophies',0)
            p_ws=getattr(player,'war_stars',0)
            p_aw=getattr(player,'attack_wins',0)
            p_dw=getattr(player,'defense_wins',0)
            p_don=getattr(player,'donations',0)
            p_rec=getattr(player,'received',0)
            p_cl=getattr(player,'clan',None)
            p_hr=getattr(player,'heroes',[])
            p_pet=getattr(player,'pets',[])
            p_th_weapon=getattr(player,'town_hall_weapon',None)

            emb=discord.Embed(title=f"{p_n}({p_t})",description=f"CV{p_th}(Arma:{p_th_weapon or 'N/A'})|Lvl{p_xp}XP",color=discord.Color.orange());
            if p_lg and hasattr(p_lg,'icon') and hasattr(p_lg.icon,'url'): emb.set_thumbnail(url=p_lg.icon.url)
            clan_info = "Sem clã";
            if p_cl and hasattr(p_cl,'name') and hasattr(p_cl,'tag'): clan_info = f"{getattr(p_cl,'name','?')} ({getattr(p_cl,'tag','?')})"
            emb.add_field(name="Clã",value=clan_info,inline=False)
            lg_txt=f"{p_lg.name}({p_tr:,}🏆)" if p_lg and hasattr(p_lg,'name') else "S/Liga"; emb.add_field(name="Liga",value=lg_txt,inline=True)
            if not p_lg: emb.add_field(name="Troféus",value=f"{p_tr:,}🏆",inline=True)
            emb.add_field(name="Melhor",value=f"{p_btr:,}🏆",inline=True); emb.add_field(name="Estrelas G",value=f"{p_ws:,}⭐",inline=True); emb.add_field(name="Atq Win",value=f"{p_aw:,}",inline=True); emb.add_field(name="Def Win",value=f"{p_dw:,}",inline=True); emb.add_field(name="Doa",value=f"{p_don:,}🎁",inline=True); emb.add_field(name="Rec",value=f"{p_rec:,}🎁",inline=True);
            ratio=f"{(p_don/p_rec):.2f}" if p_rec > 0 else ("∞" if p_don > 0 else "N/A");
            emb.add_field(name="D/R",value=ratio,inline=True)
            h_str="\n".join([f"- {getattr(h,'name','?')}:**{getattr(h,'level','?')}**/{getattr(h,'max_level','?')}" for h in p_hr if getattr(h,'is_home_base',False)]) or "N/A";
            if h_str != "N/A": emb.add_field(name="Heróis",value=h_str,inline=False)
            pet_str="\n".join([f"- {getattr(p,'name','?')}:**{getattr(p,'level','?')}**/{getattr(p,'max_level','?')}" for p in p_pet]) or "N/A";
            if pet_str != "N/A": emb.add_field(name="Pets",value=pet_str,inline=False)
            emb.set_footer(text=f"Verif:{datetime.now(TIMEZONE).strftime('%d/%m %H:%M')}"); await ctx.send(embed=emb)
        except coc_errors.NotFound: await ctx.send(f"{emojis['error']}Jogador `{player_tag}` ñ enc.")
        except coc_errors.ClashOfClansException as e_coc: await ctx.send(f"{emojis['error']}Erro API ({type(e_coc).__name__}) jogador."); logger.warning(f"Erro API !membro: {e_coc}")
        except asyncio.TimeoutError: await ctx.send(f"{emojis['error']}Timeout jogador."); logger.warning("Timeout !membro command")
        except Exception as e: logger.error(f"Erro !membro {player_tag}:{e}",exc_info=True); await ctx.send(f"{emojis['error']}Erro jogador:{e}")

@bot.command(name='capital', help="Infos Capital Clã e último raid.")
@commands.has_permissions(administrator=True)
async def capital_command(ctx):
    # Sem alterações
    if not coc_client: await ctx.send(f"{emojis['error']} API CoC indisponível."); return
    async with ctx.typing():
        clan=await get_clan_data();
        if not clan: await ctx.send(f"{emojis['error']}Erro dados clã `{CLAN_TAG}`!"); return
        c_n=getattr(clan,'name',CLAN_TAG)
        emb=discord.Embed(title=f"{emojis['clan_capital']}Capital-{c_n}",color=0x9B59B6)
        badge=getattr(getattr(clan,'badge',None),'url',None)
        if badge: emb.set_thumbnail(url=badge)

        cap_desc = ""; cap_info = getattr(clan, 'clan_capital', None)
        try:
            if cap_info:
                 hall_lvl=getattr(cap_info,'capital_hall_level','?')
                 cap_desc=f"Nível Salão Capital: **{hall_lvl}**"
                 districts = getattr(cap_info,'districts',[]); d_str="\n".join([f"- {getattr(d,'name','?')}: Nível **{getattr(d,'hall_level','?')}**" for d in districts]) if districts else "N/D"
                 emb.add_field(name="Distritos",value=d_str,inline=False)
            else: emb.description="Infos Capital indisponíveis."
        except Exception as e: emb.description=f"Erro Capital:{e}"; logger.error(f"Erro Capital !capital:{e}",exc_info=True)
        if cap_desc: emb.description = cap_desc

        rf_v=f"{emojis['warning']}Verificando..."
        top_s=""
        try:
            # *** CORREÇÃO APLICADA AQUI - Nome do Método ***
            rl=await asyncio.wait_for(coc_client.get_clan_capital_raid_seasons(CLAN_TAG,limit=1),timeout=30.0);
            if rl and rl[0] and hasattr(rl[0],'state'):
                r=rl[0]; state=r.state; loot=getattr(r,'capital_total_loot',0); attacks=getattr(r,'total_attacks','?'); d_d=getattr(r,'districts_destroyed','?')
                st_obj = getattr(r, 'start_time', None); et_obj = getattr(r, 'end_time', None)
                st = st_obj.time.astimezone(TIMEZONE).strftime('%d/%m %H:%M') if st_obj and hasattr(st_obj, 'time') else '?'
                et_ts = int(et_obj.time.astimezone(TIMEZONE).timestamp()) if et_obj and hasattr(et_obj, 'time') else None;
                t_inf=f"(<t:{et_ts}:R>)" if et_ts else "";
                st_t="Ativo" if state=='ongoing' else "Finalizado"
                s_em=emojis['raid'] if state=='ongoing' else emojis['success']
                rf_v=(f"Início:{st}\nEstado:**{st_t}**{t_inf}\nOuro:**{loot:,}**\nAtaques:{attacks}|Distritos:{d_d}")
                if getattr(r,'members',[]):
                    m_map={m.tag:m.name for m in getattr(clan,'members',[])}; s_raiders=sorted(r.members,key=lambda m:getattr(m,'capital_resources_looted',0),reverse=True)[:5];
                    top_s="\n".join([f"{i}.`{m_map.get(m.tag,getattr(m,'name','?'))}`:**{getattr(m,'capital_resources_looted',0):,}**" for i,m in enumerate(s_raiders,1) if hasattr(m,'tag')])
            else: rf_v=f"{emojis['warning']}Nenhum dado raid."
        except coc_errors.NotFound: rf_v=f"{emojis['warning']}Nenhum dado raid (NotFound)."
        except coc_errors.ClashOfClansException as e_coc: rf_v = f"{emojis['error']}Erro API Raid ({type(e_coc).__name__})."; logger.warning(f"Erro API Raid !capital: {e_coc}")
        except asyncio.TimeoutError: rf_v=f"{emojis['error']}Timeout Raid."; logger.warning("Timeout Raid !capital")
        except Exception as e: rf_v=f"{emojis['error']}Erro Raid."; logger.warning(f"Erro Raid !capital:{e}", exc_info=True)

        emb.add_field(name=f"{emojis['clan_capital']}Últ/Atual Raid",value=rf_v,inline=False)
        if top_s: emb.add_field(name="🌟Top Contribs",value=top_s,inline=False)
        emb.set_footer(text=f"Verif:{datetime.now(TIMEZONE).strftime('%d/%m %H:%M')}"); await ctx.send(embed=emb)

@bot.command(name='setcanal', help="Define canal logs: !setcanal #canal")
@commands.has_permissions(administrator=True)
async def set_canal_command(ctx, channel: discord.TextChannel = None):
    # Sem alterações
    global CHANNEL_ID
    target_channel=channel or ctx.channel
    if not isinstance(target_channel,discord.TextChannel): await ctx.send(f"{emojis['error']}Canal inválido."); return
    try:
         test_msg=await target_channel.send(f"{emojis['warning']}Testando...");
         CHANNEL_ID=target_channel.id
         logger.info(f"Canal->{target_channel.name}({CHANNEL_ID}) por {ctx.author}")
         await ctx.send(f"{emojis['success']}Canal logs:{target_channel.mention}!"); await test_msg.edit(content=f"{emojis['success']}Permissão OK!")
         confirm_msg=await ctx.send(f"{emojis['warning']}Reiniciar tasks?(S/N)")
         check=lambda m: m.author==ctx.author and m.channel==ctx.channel and m.content.lower() in ['sim','s','yes','y','não','nao','n','no']
         try:
             resp=await bot.wait_for('message',timeout=30.0,check=check);
             if resp.content.lower() in ['sim','s','yes','y']:
                  await ctx.send(f"{emojis['info']}Reiniciando...");
                  tasks_list=[check_donations,check_members,check_war,check_league_war,check_raid_weekend]
                  restart_log = []
                  for t in tasks_list:
                      task_name = t.coro.__name__
                      status = "ERRO_RESTART"
                      if t.is_running():
                          try:
                              t.restart()
                              status = "OK"
                          except Exception as e_restart:
                              logger.error(f"Erro restart task {task_name}: {e_restart}")
                      else:
                          try:
                              t.start()
                              status = "Iniciada"
                          except Exception as e_start:
                              logger.error(f"Erro start task {task_name}: {e_start}")
                              status="ERRO_START"
                      restart_log.append(f"{task_name}:{status}")
                  await target_channel.send(f"{emojis['success']}Tasks reiniciadas ({'; '.join(restart_log)})."); logger.info(f"Tasks reiniciadas(canal) ({'; '.join(restart_log)}).")
             else: await ctx.send(f"{emojis['info']}Tasks não reiniciadas.")
         except asyncio.TimeoutError: await ctx.send(f"{emojis['warning']}Timeout. Tasks não reiniciadas.")
         finally:
             try:
                 await confirm_msg.delete()
             except discord.HTTPException:
                 logger.debug(f"Não foi possível deletar a msg de confirmação em setcanal (ID: {confirm_msg.id})")
                 pass
    except discord.errors.Forbidden: await ctx.send(f"{emojis['error']}Sem permissão em {target_channel.mention}.")
    except Exception as e: logger.error(f"Erro setcanal {target_channel.mention}: {e}",exc_info=True); await ctx.send(f"{emojis['error']}Erro setcanal.")

@bot.command(name='setclan', help="Define clã monitorar: !setclan #TAG")
@commands.has_permissions(administrator=True)
async def set_clan_command(ctx, clan_tag: str = None):
    # Sem alterações
    global CLAN_TAG,member_cache,donation_cache,war_cache,raid_weekend_cache, coc_client
    if not coc_client: await ctx.send(f"{emojis['error']} API CoC indisponível."); return
    if not clan_tag: await ctx.send(f"{emojis['error']}Forneça tag. Ex:`!setclan #TAG`"); return
    clan_tag=clan_tag.strip().upper()
    if not clan_tag.startswith('#'): clan_tag='#'+clan_tag
    if not coc.utils.is_valid_tag(clan_tag): await ctx.send(f"{emojis['error']}Tag `{clan_tag}` inválida."); return
    if clan_tag == CLAN_TAG: await ctx.send(f"{emojis['info']} Já monitorando `{clan_tag}`."); return
    async with ctx.typing():
        try:
            logger.info(f"Tentando setclan {clan_tag} por {ctx.author}..."); clan=await asyncio.wait_for(coc_client.get_clan(clan_tag),timeout=30.0);
            old_tag=CLAN_TAG
            CLAN_TAG=clan.tag
            await ctx.send(f"{emojis['info']}Clã **{clan.name}**({CLAN_TAG})OK. Limpando caches...")
            member_cache={'members':{},'count':0}
            donation_cache={}
            war_cache={'war_end_reported':{},'league_war_end_reported':{},'league_start_announced':False}; keys_to_del=[k for k in war_cache if k.startswith(('#','league-')) and k not in ['war_end_reported','league_war_end_reported','league_start_announced']];
            for k in keys_to_del:
                if k in war_cache: del war_cache[k]
            raid_weekend_cache={'current_raid':None}
            logger.info(f"Clã {old_tag}->{CLAN_TAG}({clan.name}) por {ctx.author}. Caches limpos.")
            await ctx.send(f"{emojis['success']}Clã->**{clan.name}**({CLAN_TAG}). Caches limpos.")
            confirm_msg=await ctx.send(f"{emojis['warning']}Reiniciar tasks?(S/N)")
            check=lambda m: m.author==ctx.author and m.channel==ctx.channel and m.content.lower() in ['sim','s','yes','y','não','nao','n','no']
            try:
                resp=await bot.wait_for('message',timeout=30.0,check=check);
                if resp.content.lower() in ['sim','s','yes','y']:
                    await ctx.send(f"{emojis['info']}Reiniciando...");
                    tasks_list=[check_donations,check_members,check_war,check_league_war,check_raid_weekend]
                    restart_log = []
                    for t in tasks_list:
                        task_name = t.coro.__name__
                        status = "ERRO_RESTART"
                        if t.is_running():
                            try:
                                t.restart()
                                status="OK"
                            except Exception as e_restart:
                                logger.error(f"Erro restart task {task_name}: {e_restart}")
                        else:
                            try:
                                t.start()
                                status="Iniciada"
                            except Exception as e_start:
                                logger.error(f"Erro start task {task_name}: {e_start}")
                                status="ERRO_START"
                        restart_log.append(f"{task_name}:{status}")
                    await ctx.send(f"{emojis['success']}Tasks reiniciadas para {clan.name} ({'; '.join(restart_log)})."); logger.info(f"Tasks reiniciadas(clã {CLAN_TAG}) ({'; '.join(restart_log)}).")
                else: await ctx.send(f"{emojis['info']}Tasks não reiniciadas.")
            except asyncio.TimeoutError: await ctx.send(f"{emojis['warning']}Timeout. Tasks não reiniciadas.")
            finally:
                try:
                    await confirm_msg.delete()
                except discord.HTTPException:
                    logger.debug(f"Não foi possível deletar a msg de confirmação em setclan (ID: {confirm_msg.id})")
                    pass
        except coc_errors.NotFound: await ctx.send(f"{emojis['error']}Clã `{clan_tag}` não encontrado!")
        except coc_errors.ClashOfClansException as e_coc: await ctx.send(f"{emojis['error']}Erro API ({type(e_coc).__name__}) verificando tag clã."); logger.warning(f"Erro API !setclan: {e_coc}")
        except asyncio.TimeoutError: await ctx.send(f"{emojis['error']}Timeout tag clã."); logger.warning("Timeout !setclan command")
        except Exception as e: logger.error(f"Erro setclan {clan_tag}: {e}",exc_info=True); await ctx.send(f"{emojis['error']}Erro setclan:{e}")

@bot.command(name='ajuda', aliases=['help', 'comandos'])
async def ajuda_command(ctx):
    embed=discord.Embed(title=f"{emojis['info']} Ajuda - Bot Monitor CoC", description="Monitora eventos e fornece infos.", color=discord.Color.green());
    if bot.user.avatar: embed.set_thumbnail(url=bot.user.avatar.url)
    embed.add_field(name="🛠️ Config (Admin)", value=f"`!setcanal #canal`\n`!setclan #TAG`", inline=False)
    embed.add_field(name="📊 Infos (Admin)", value=f"`!status`\n`!top [tipo] [limite]`\n`!ataques`|`!ligaataques`\n`!membro #TAG`\n`!capital`", inline=False)
    embed.add_field(name="👀 Eventos Auto", value=f"{emojis['donation']} Doações\n{emojis['join']}/{emojis['leave']}Entr/Saída\n{emojis['war_attack']}Ataques\n{emojis['war_win']}Guerras\n{emojis['time']}Alertas\n{emojis['missed_attack']}Perdidos\n{emojis['raid']}Raid", inline=False)
    # *** CORREÇÃO APLICADA AQUI - Versão Atualizada ***
    embed.set_footer(text=f"Bot V14.10 | Use {bot.command_prefix}comando"); await ctx.send(embed=embed) # Atualiza número da versão

# --- Função Principal ---
async def main():
    # Sem alterações
    if not TOKEN: logger.critical("Token Discord não encontrado."); return
    logger.info("Iniciando bot Discord...")
    try: await bot.start(TOKEN)
    except discord.LoginFailure: logger.critical("Login Discord falhou: Token inválido.")
    except discord.PrivilegedIntentsRequired: logger.critical("Login Discord falhou: Intenções privilegiadas não habilitadas.")
    except KeyboardInterrupt: logger.info("Desligamento via Ctrl+C.")
    except Exception as e: logger.critical(f"Erro fatal bot: {e}", exc_info=True)
    finally: # Limpeza
         if bot and not bot.is_closed():
              logger.info("Fechando conexão bot Discord...")
              try: await bot.close()
              except Exception as e_close: logger.error(f"Erro ao fechar bot: {e_close}")
              logger.info("Conexão bot Discord fechada.")
         if coc_client and hasattr(coc_client, 'close'):
             logger.info("Fechando cliente CoC...")
             try: await coc_client.close()
             except Exception as e_coc_close: logger.error(f"Erro ao fechar cliente CoC: {e_coc_close}")
             logger.info("Cliente CoC fechado.")
         logger.info("Bot encerrado.")

if __name__ == "__main__":
    try:
        if os.name == 'nt': asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except Exception as e_run: logger.critical(f"Erro crítico executar main: {e_run}", exc_info=True)