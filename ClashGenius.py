import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import datetime
import json
import os
from dotenv import load_dotenv

const app = require('express')();

app.get('/', (req, res) => res.send('LunaBot Online.'));

module.exports = () => {
  app.listen(3000);
}

# Carregar variáveis de ambiente
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
COC_API_KEY = os.getenv('COC_API_KEY')
CLAN_TAG = os.getenv('CLAN_TAG')
GUILD_ID = int(os.getenv('GUILD_ID'))
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID'))

# Configuração do bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!coc ', intents=intents)

# URLs da API do Clash of Clans
BASE_URL = "https://api.clashofclans.com/v1"

# Headers para a API do Clash of Clans
headers = {
    "Authorization": f"Bearer {COC_API_KEY}",
    "Accept": "application/json"
}

# Dicionário para armazenar dados anteriores para comparação
previous_data = {
    "members": {},
    "war": None,
    "donations": {},
    "capital": None  # Adicionada esta linha
}

# Função auxiliar para formatar a tag do clã
def format_tag(tag):
    if not tag.startswith('#'):
        tag = '#' + tag
    return tag.replace('#', '%23')

# Função para obter dados do clã
async def get_clan_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/clans/{format_tag(CLAN_TAG)}", headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"Erro ao obter dados do clã: {response.status}")
                return None

# Função para obter dados da guerra atual
async def get_current_war():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/clans/{format_tag(CLAN_TAG)}/currentwar", headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"Erro ao obter dados da guerra: {response.status}")
                return None
# Função para obter dados da Capital do Clã
async def get_clan_capital_info():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/clans/{format_tag(CLAN_TAG)}/capitalraidseasons", headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"Erro ao obter dados da Capital do Clã: {response.status}")
                return None

# Função para obter dados do histórico de guerras
async def get_war_log():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/clans/{format_tag(CLAN_TAG)}/warlog", headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"Erro ao obter histórico de guerras: {response.status}")
                return None

# Função para obter dados de um jogador específico
async def get_player_data(player_tag):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/players/{format_tag(player_tag)}", headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"Erro ao obter dados do jogador {player_tag}: {response.status}")
                return None

@bot.event
async def on_ready():
    print(f'{bot.user.name} está online!')
    # Iniciar as tarefas de monitoramento
    check_clan_status.start()
    check_war_status.start()
    check_clan_capital_status.start()

# Task para verificar o status do clã regularmente
@tasks.loop(minutes=5)
async def check_clan_status():
    try:
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            print(f"Não foi possível encontrar o servidor com ID {GUILD_ID}")
            return
        
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            print(f"Não foi possível encontrar o canal com ID {LOG_CHANNEL_ID}")
            return
        
        clan_data = await get_clan_data()
        if not clan_data:
            return
        
        # Verificar se memberList existe nos dados retornados
        if 'memberList' not in clan_data:
            print("Erro: memberList não encontrado nos dados do clã")
            return
            
        # Verificar mudanças nos membros
        current_members = {member['tag']: member for member in clan_data['memberList']}
        
        # Novos membros e membros que saíram
        if previous_data["members"]:
            # Verificar novos membros
            for tag, member in current_members.items():
                if tag not in previous_data["members"]:
                    await log_channel.send(f"📥 **Novo membro no clã!** {member['name']} (#{member['tag'][1:]}) entrou no clã!")
            
            # Verificar membros que saíram
            for tag, member in previous_data["members"].items():
                if tag not in current_members:
                    await log_channel.send(f"📤 **Membro saiu do clã!** {member['name']} (#{member['tag'][1:]}) saiu do clã!")
        
        # Verificar mudanças nas doações
        if previous_data["donations"]:
            for tag, member in current_members.items():
                if tag in previous_data["donations"]:
                    # Verificar se as chaves existem antes de acessá-las
                    if 'donations' in member and 'donationsReceived' in member and 'donations' in previous_data["donations"][tag] and 'donationsReceived' in previous_data["donations"][tag]:
                        old_donations = previous_data["donations"][tag]["donations"]
                        old_received = previous_data["donations"][tag]["donationsReceived"]
                        
                        new_donations = member["donations"]
                        new_received = member["donationsReceived"]
                        
                        if new_donations > old_donations:
                            diff = new_donations - old_donations
                            await log_channel.send(f"🎁 **Doações:** {member['name']} doou {diff} tropas! (Total: {new_donations})")
                        
                        if new_received > old_received:
                            diff = new_received - old_received
                            await log_channel.send(f"📦 **Recebimentos:** {member['name']} recebeu {diff} tropas! (Total: {new_received})")
        
        # Atualizar dados para a próxima verificação
        previous_data["members"] = current_members
        previous_data["donations"] = {}
        for m in clan_data['memberList']:
            if 'donations' in m and 'donationsReceived' in m:
                previous_data["donations"][m['tag']] = {"donations": m['donations'], "donationsReceived": m['donationsReceived']}
        
        # Log de troféus e ligas
        now = datetime.datetime.now()
        if now.hour == 0 and now.minute < 30:  # Fazer isso uma vez por dia, por volta da meia-noite
            trophy_log = "📊 **Registro diário de troféus**\n```\n"
            trophy_log += f"{'Nome':<15} | {'Troféus':<7} | {'Liga':<20}\n"
            trophy_log += "-" * 50 + "\n"
            
            for member in sorted(clan_data['memberList'], key=lambda x: x.get('trophies', 0), reverse=True):
                # Verificar se a chave 'trophies' existe
                trophies = member.get('trophies', 0)
                # Verificar se 'league' existe e tem a chave 'name'
                league_name = member.get('league', {}).get('name', 'Sem Liga')
                trophy_log += f"{member['name'][:15]:<15} | {trophies:<7} | {league_name:<20}\n"
            
            trophy_log += "```"
            await log_channel.send(trophy_log)
    except Exception as e:
        print(f"Erro em check_clan_status: {e}")

# Task para verificar o status da guerra regularmente
@tasks.loop(minutes=15)
async def check_war_status():
    try:
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            return
        
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            return
        
        war_data = await get_current_war()
        if not war_data or war_data.get('state') == 'notInWar':
            return
        
        # Se é a primeira verificação ou houve mudança no estado da guerra
        if not previous_data["war"] or previous_data["war"].get('state') != war_data.get('state'):
            if war_data.get('state') == 'preparation':
                # Verificar se as chaves necessárias existem
                clan_name = war_data.get('clan', {}).get('name', 'Nosso Clã')
                opponent_name = war_data.get('opponent', {}).get('name', 'Oponente')
                team_size = war_data.get('teamSize', '?')
                start_time = war_data.get('startTime', 'horário desconhecido')
                
                await log_channel.send(f"⚔️ **Preparação para guerra iniciada!**\n"
                                      f"**{clan_name}** vs **{opponent_name}**\n"
                                      f"Guerra de {team_size} vs {team_size}\n"
                                      f"A fase de batalha começa em {start_time}")
            
            elif war_data.get('state') == 'inWar':
                # Verificar se as chaves necessárias existem
                clan_name = war_data.get('clan', {}).get('name', 'Nosso Clã')
                opponent_name = war_data.get('opponent', {}).get('name', 'Oponente')
                end_time = war_data.get('endTime', 'horário desconhecido')
                
                await log_channel.send(f"🔥 **A guerra começou!**\n"
                                      f"**{clan_name}** vs **{opponent_name}**\n"
                                      f"A guerra termina em {end_time}")
            
            elif war_data.get('state') == 'warEnded':
                # Resultado da guerra
                clan_data = war_data.get('clan', {})
                opponent_data = war_data.get('opponent', {})
                
                clan_name = clan_data.get('name', 'Nosso Clã')
                opponent_name = opponent_data.get('name', 'Oponente')
                clan_stars = clan_data.get('stars', 0)
                opponent_stars = opponent_data.get('stars', 0)
                clan_destruction = clan_data.get('destructionPercentage', 0)
                opponent_destruction = opponent_data.get('destructionPercentage', 0)
                
                result = "Empate!"
                if clan_stars > opponent_stars:
                    result = f"**{clan_name}** venceu! 🎉"
                elif opponent_stars > clan_stars:
                    result = f"**{opponent_name}** venceu! 😢"
                elif clan_destruction > opponent_destruction:
                    result = f"**{clan_name}** venceu por porcentagem de destruição! 🎉"
                elif opponent_destruction > clan_destruction:
                    result = f"**{opponent_name}** venceu por porcentagem de destruição! 😢"
                
                await log_channel.send(f"🏁 **Guerra terminada!**\n"
                                      f"**{clan_name}** {clan_stars}⭐ ({clan_destruction:.2f}%)\n"
                                      f"**{opponent_name}** {opponent_stars}⭐ ({opponent_destruction:.2f}%)\n"
                                      f"Resultado: {result}")
                
                # Listar quem não usou os ataques
                missed_attacks = []
                for member in war_data.get('clan', {}).get('members', []):
                    attacks_used = len(member.get('attacks', []))
                    attacks_limit = 2  # Assumindo guerra normal de 2 ataques por pessoa
                    if attacks_used < attacks_limit:
                        missed_attacks.append((member.get('name', 'Membro desconhecido'), attacks_limit - attacks_used))
                
                if missed_attacks:
                    missed_msg = "❌ **Membros que não usaram todos os ataques:**\n```\n"
                    for name, missed in missed_attacks:
                        missed_msg += f"{name}: {missed} {'ataque' if missed == 1 else 'ataques'} não usado(s)\n"
                    missed_msg += "```"
                    await log_channel.send(missed_msg)
        
        # Verificar novos ataques desde a última checagem
        if previous_data["war"]:
            old_attacks = {}
            for member in previous_data["war"].get('clan', {}).get('members', []):
                for attack in member.get('attacks', []):
                    old_attacks[f"{member.get('tag', '')}-{attack.get('defenderTag', '')}"] = attack
            
            # Verificar novos ataques do nosso clã
            for member in war_data.get('clan', {}).get('members', []):
                for attack in member.get('attacks', []):
                    if 'tag' in member and 'defenderTag' in attack:
                        attack_id = f"{member['tag']}-{attack['defenderTag']}"
                        if attack_id not in old_attacks:
                            # Encontrar o nome do defensor
                            defender_name = "Oponente"
                            for opponent in war_data.get('opponent', {}).get('members', []):
                                if opponent.get('tag') == attack.get('defenderTag'):
                                    defender_name = opponent.get('name', 'Oponente')
                                    break
                            
                            stars = "⭐" * attack.get('stars', 0)
                            destruction = attack.get('destructionPercentage', 0)
                            await log_channel.send(f"⚔️ **Novo ataque!** {member.get('name', 'Membro')} atacou {defender_name} e conseguiu {stars} ({destruction}%)")
            
            # Verificar novos ataques do clã oponente
            old_opponent_attacks = {}
            for member in previous_data["war"].get('opponent', {}).get('members', []):
                for attack in member.get('attacks', []):
                    if 'tag' in member and 'defenderTag' in attack:
                        old_opponent_attacks[f"{member['tag']}-{attack['defenderTag']}"] = attack
            
            for member in war_data.get('opponent', {}).get('members', []):
                for attack in member.get('attacks', []):
                    if 'tag' in member and 'defenderTag' in attack:
                        attack_id = f"{member['tag']}-{attack['defenderTag']}"
                        if attack_id not in old_opponent_attacks:
                            # Encontrar o nome do defensor
                            defender_name = "Membro"
                            for our_member in war_data.get('clan', {}).get('members', []):
                                if our_member.get('tag') == attack.get('defenderTag'):
                                    defender_name = our_member.get('name', 'Membro')
                                    break
                            
                            stars = "⭐" * attack.get('stars', 0)
                            destruction = attack.get('destructionPercentage', 0)
                            await log_channel.send(f"🛡️ **Fomos atacados!** {member.get('name', 'Oponente')} atacou {defender_name} e conseguiu {stars} ({destruction}%)")
        
        # Atualizar dados da guerra para a próxima verificação
        previous_data["war"] = war_data
    except Exception as e:
        print(f"Erro em check_war_status: {e}")
        
        # Task para monitorar atividades da Capital do Clã
@tasks.loop(hours=6)  # Verificar a cada 6 horas é suficiente
async def check_clan_capital_status():
    try:
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            print(f"Não foi possível encontrar o servidor com ID {GUILD_ID}")
            return
        
        log_channel = guild.get_channel(LOG_CHANNEL_ID)
        if not log_channel:
            print(f"Não foi possível encontrar o canal com ID {LOG_CHANNEL_ID}")
            return
        
        capital_data = await get_clan_capital_info()
        if not capital_data or "items" not in capital_data or len(capital_data["items"]) == 0:
            return
        
        # Obter dados mais recentes da temporada atual da Capital
        latest_season = capital_data["items"][0]
        
        # Verificar se temos dados armazenados para comparação
        if "capital" not in previous_data or previous_data["capital"] is None:
            previous_data["capital"] = latest_season
            return
        
        # Comparar com os dados anteriores para verificar mudanças
        prev_season = previous_data["capital"]
        
        # Verificar se é uma nova temporada
        if prev_season.get("id") != latest_season.get("id"):
            start_date = latest_season.get("startTime", "desconhecido")
            end_date = latest_season.get("endTime", "desconhecido")
            await log_channel.send(f"🏛️ **Nova temporada da Capital do Clã iniciada!**\n"
                                 f"Período: {start_date} até {end_date}")
            
            # Se a temporada anterior terminou, mostrar resumo
            if "id" in prev_season:
                total_raid_medals = prev_season.get("totalAttacks", 0)
                offensive_reward = prev_season.get("offensiveReward", 0)
                defensive_reward = prev_season.get("defensiveReward", 0)
                
                await log_channel.send(f"🏆 **Resumo da temporada anterior:**\n"
                                     f"Total de ataques: {total_raid_medals}\n"
                                     f"Recompensas ofensivas: {offensive_reward} medalhas\n"
                                     f"Recompensas defensivas: {defensive_reward} medalhas\n"
                                     f"Total: {offensive_reward + defensive_reward} medalhas")
        
        # Verificar contribuições de ouro da capital
        if "members" in latest_season and "members" in prev_season:
            new_contributions = {}
            for member in latest_season.get("members", []):
                if "tag" in member and "name" in member and "capitalResourcesLooted" in member:
                    new_contributions[member["tag"]] = {
                        "name": member["name"],
                        "gold": member["capitalResourcesLooted"]
                    }
            
            old_contributions = {}
            for member in prev_season.get("members", []):
                if "tag" in member and "capitalResourcesLooted" in member:
                    old_contributions[member["tag"]] = member["capitalResourcesLooted"]
            
            # Verificar aumento nas contribuições
            contributions_log = ""
            for tag, data in new_contributions.items():
                old_gold = old_contributions.get(tag, 0)
                new_gold = data["gold"]
                
                if new_gold > old_gold:
                    contributions_log += f"{data['name']}: +{new_gold - old_gold} ouro\n"
            
            if contributions_log:
                await log_channel.send(f"💰 **Novas contribuições para a Capital do Clã:**\n```\n{contributions_log}```")
        
        # Verificar novos ataques em raids da capital
        if "attackLog" in latest_season and "attackLog" in prev_season:
            old_attacks = set()
            for attack in prev_season.get("attackLog", []):
                if "attacker" in attack and "defender" in attack:
                    attack_id = f"{attack['attacker'].get('tag', '')}-{attack['defender'].get('tag', '')}-{attack.get('destructionPercentage', 0)}"
                    old_attacks.add(attack_id)
            
            new_attacks = []
            for attack in latest_season.get("attackLog", []):
                if "attacker" in attack and "defender" in attack:
                    attack_id = f"{attack['attacker'].get('tag', '')}-{attack['defender'].get('tag', '')}-{attack.get('destructionPercentage', 0)}"
                    if attack_id not in old_attacks:
                        new_attacks.append(attack)
            
            for attack in new_attacks:
                attacker_name = attack.get("attacker", {}).get("name", "Membro desconhecido")
                district_name = attack.get("defender", {}).get("name", "Distrito desconhecido")
                destruction = attack.get("destructionPercentage", 0)
                await log_channel.send(f"⚔️ **Ataque na Capital do Clã!** {attacker_name} atacou {district_name} e conseguiu {destruction}% de destruição!")
        
        # Atualizar dados para a próxima verificação
        previous_data["capital"] = latest_season
        
    except Exception as e:
        print(f"Erro em check_clan_capital_status: {e}")

@check_clan_status.before_loop
@check_war_status.before_loop
@check_clan_capital_status.before_loop
async def before_check():
    await bot.wait_until_ready()

# Comando para mostrar informações do clã
@bot.command(name='clan')
async def clan_info(ctx):
    try:
        clan_data = await get_clan_data()
        if not clan_data:
            await ctx.send("Não foi possível obter informações do clã.")
            return
        
        embed = discord.Embed(
            title=f"{clan_data.get('name', 'Clã')} ({clan_data.get('tag', 'N/A')})", 
            description=clan_data.get('description', 'Sem descrição'), 
            color=0x00ff00
        )
        
        embed.add_field(name="Nível do Clã", value=clan_data.get('clanLevel', 'N/A'), inline=True)
        embed.add_field(name="Troféus", value=clan_data.get('clanPoints', 'N/A'), inline=True)
        
        # Verificar se alguma dessas chaves existe para troféus de guerra
        if 'clanVersusPoints' in clan_data:
            embed.add_field(name="Troféus de Guerra", value=clan_data['clanVersusPoints'], inline=True)
        elif 'warPoints' in clan_data:
            embed.add_field(name="Troféus de Guerra", value=clan_data['warPoints'], inline=True)
        elif 'clanBuilderBasePoints' in clan_data:
            embed.add_field(name="Troféus Base Construtor", value=clan_data['clanBuilderBasePoints'], inline=True)
        
        embed.add_field(name="Membros", value=f"{clan_data.get('members', 0)}/50", inline=True)
        embed.add_field(name="Tipo", value=clan_data.get('type', 'N/A'), inline=True)
        embed.add_field(name="Frequência de Guerra", value=clan_data.get('warFrequency', 'Desconhecido'), inline=True)
        embed.add_field(name="Streak de Vitórias", value=clan_data.get('warWinStreak', 0), inline=True)
        embed.add_field(name="Vitórias em Guerra", value=clan_data.get('warWins', 0), inline=True)
        embed.add_field(name="Empates em Guerra", value=clan_data.get('warTies', 0), inline=True)
        embed.add_field(name="Derrotas em Guerra", value=clan_data.get('warLosses', 0), inline=True)
        
        if clan_data.get('location'):
            embed.add_field(name="Localização", value=clan_data['location'].get('name', 'Desconhecida'), inline=True)
        
        if clan_data.get('badgeUrls', {}).get('medium'):
            embed.set_thumbnail(url=clan_data['badgeUrls']['medium'])
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"Erro ao processar informações do clã: {e}")

# Comando para mostrar o status da guerra atual
@bot.command(name='war')
async def war_status(ctx):
    try:
        war_data = await get_current_war()
        if not war_data:
            await ctx.send("Não foi possível obter informações da guerra.")
            return
        
        if war_data.get('state') == 'notInWar':
            await ctx.send("O clã não está em guerra no momento.")
            return
        
        clan_data = war_data.get('clan', {})
        opponent_data = war_data.get('opponent', {})
        
        clan_name = clan_data.get('name', 'Nosso Clã')
        opponent_name = opponent_data.get('name', 'Oponente')
        clan_stars = clan_data.get('stars', 0)
        opponent_stars = opponent_data.get('stars', 0)
        clan_attacks = clan_data.get('attacks', 0)
        clan_destruction = clan_data.get('destructionPercentage', 0)
        opponent_destruction = opponent_data.get('destructionPercentage', 0)
        
        embed = discord.Embed(title=f"Guerra: {clan_name} vs {opponent_name}", color=0xff0000)
        
        war_state = war_data.get('state', 'unknown')
        if war_state == 'preparation':
            embed.description = "⏳ Fase de preparação"
            embed.add_field(name="Início dos Ataques", value=war_data.get('startTime', 'Desconhecido'), inline=False)
        elif war_state == 'inWar':
            embed.description = "⚔️ Guerra em andamento"
            embed.add_field(name="Término", value=war_data.get('endTime', 'Desconhecido'), inline=False)
        else:  # warEnded
            embed.description = "🏁 Guerra finalizada"
        
        embed.add_field(name=clan_name, value=f"{clan_stars}⭐ ({clan_destruction:.2f}%)", inline=True)
        embed.add_field(name=opponent_name, value=f"{opponent_stars}⭐ ({opponent_destruction:.2f}%)", inline=True)
        
        # Detalhes dos ataques do nosso clã
        attacks_info = "```\n"
        attacks_info += f"{'Nome':<15} | {'Alvo':<15} | {'Estrelas':<8} | {'Destruição':<10}\n"
        attacks_info += "-" * 55 + "\n"
        
        has_attacks = False
        for member in clan_data.get('members', []):
            for attack in member.get('attacks', []):
                has_attacks = True
                # Encontrar nome do defensor
                defender_name = "Oponente"
                for opponent in opponent_data.get('members', []):
                    if opponent.get('tag') == attack.get('defenderTag'):
                        defender_name = opponent.get('name', 'Oponente')
                        break
                
                stars = "⭐" * attack.get('stars', 0)
                destruction = attack.get('destructionPercentage', 0)
                attacks_info += f"{member.get('name', 'Membro')[:15]:<15} | {defender_name[:15]:<15} | {stars:<8} | {destruction}%\n"
        
        attacks_info += "```"
        
        # Se não houver ataques ainda
        if not has_attacks:
            attacks_info = "Nenhum ataque realizado ainda."
        
        embed.add_field(name="Ataques do nosso clã", value=attacks_info, inline=False)
        
        # Membros que ainda não atacaram
        not_attacked = []
        attacks_limit = 2  # Assumindo guerra normal de 2 ataques por pessoa
        
        for member in clan_data.get('members', []):
            attacks_used = len(member.get('attacks', []))
            if attacks_used < attacks_limit:
                not_attacked.append((
                    member.get('name', 'Membro desconhecido'),
                    member.get('mapPosition', 0),
                    attacks_limit - attacks_used
                ))
        
        if not_attacked:
            not_attacked_msg = "```\n"
            not_attacked_msg += f"{'Nome':<15} | {'Posição':<8} | {'Ataques Restantes':<17}\n"
            not_attacked_msg += "-" * 45 + "\n"
            
            for name, position, remaining in sorted(not_attacked, key=lambda x: x[1]):
                not_attacked_msg += f"{name[:15]:<15} | {position:<8} | {remaining:<17}\n"
            
            not_attacked_msg += "```"
            embed.add_field(name="Membros com ataques pendentes", value=not_attacked_msg, inline=False)
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"Erro ao processar informações da guerra: {e}")

# Comando para mostrar os top doadores
@bot.command(name='doadores')
async def top_donators(ctx):
    try:
        clan_data = await get_clan_data()
        if not clan_data:
            await ctx.send("Não foi possível obter informações do clã.")
            return
        
        if 'memberList' not in clan_data:
            await ctx.send("Dados de membros não encontrados na resposta da API.")
            return
            
        members = clan_data['memberList']
        
        # Verificar se todos os membros têm a chave 'donations'
        for member in members:
            if 'donations' not in member:
                member['donations'] = 0
            if 'donationsReceived' not in member:
                member['donationsReceived'] = 0
        
        # Ordenar por doações
        donators = sorted(members, key=lambda x: x.get('donations', 0), reverse=True)
        
        embed = discord.Embed(title=f"Top Doadores de {clan_data.get('name', 'Clã')}", color=0x00ff00)
        
        donators_text = "```\n"
        donators_text += f"{'Posição':<8} | {'Nome':<15} | {'Doações':<8} | {'Recebidas':<9} | {'Razão':<5}\n"
        donators_text += "-" * 55 + "\n"
        
        for i, member in enumerate(donators[:10], 1):
            donations = member.get('donations', 0)
            received = member.get('donationsReceived', 0)
            ratio = donations / max(1, received)  # Evitar divisão por zero
            donators_text += f"{i:<8} | {member.get('name', 'Membro')[:15]:<15} | {donations:<8} | {received:<9} | {ratio:.1f}\n"
        
        donators_text += "```"
        embed.add_field(name="Top 10 Doadores", value=donators_text, inline=False)
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"Erro ao processar informações de doadores: {e}")

# Comando para mostrar ranking de troféus
@bot.command(name='trofeus')
async def trophies_ranking(ctx):
    try:
        clan_data = await get_clan_data()
        if not clan_data:
            await ctx.send("Não foi possível obter informações do clã.")
            return
        
        if 'memberList' not in clan_data:
            await ctx.send("Dados de membros não encontrados na resposta da API.")
            return
            
        members = clan_data['memberList']
        
        # Verificar se todos os membros têm a chave 'trophies'
        for member in members:
            if 'trophies' not in member:
                member['trophies'] = 0
        
        # Ordenar por troféus
        trophy_leaders = sorted(members, key=lambda x: x.get('trophies', 0), reverse=True)
        
        embed = discord.Embed(title=f"Ranking de Troféus de {clan_data.get('name', 'Clã')}", color=0x00ff00)
        
        trophies_text = "```\n"
        trophies_text += f"{'Posição':<8} | {'Nome':<15} | {'Troféus':<7} | {'TH':<3} | {'Liga':<20}\n"
        trophies_text += "-" * 60 + "\n"
        
        for i, member in enumerate(trophy_leaders, 1):
            # Obter informações detalhadas do jogador (TH)
            th_level = "?"
            if 'tag' in member:
                player_data = await get_player_data(member['tag'])
                if player_data and 'townHallLevel' in player_data:
                    th_level = player_data['townHallLevel']
            
            trophies = member.get('trophies', 0)
            league_name = member.get('league', {}).get('name', 'Sem Liga')
            trophies_text += f"{i:<8} | {member.get('name', 'Membro')[:15]:<15} | {trophies:<7} | {th_level:<3} | {league_name[:20]:<20}\n"
            
            # Limitar a 15 jogadores para não exceder o limite de caracteres do Discord
            if i >= 15:
                break
        
        trophies_text += "```"
        embed.add_field(name="Ranking de Troféus", value=trophies_text, inline=False)
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"Erro ao processar informações de troféus: {e}")

# Comando para mostrar informações da Capital do Clã
@bot.command(name='capital')
async def clan_capital_info(ctx):
    try:
        capital_data = await get_clan_capital_info()
        if not capital_data or "items" not in capital_data or len(capital_data["items"]) == 0:
            await ctx.send("Não foi possível obter informações da Capital do Clã.")
            return
        
        # Obter dados da temporada atual
        latest_season = capital_data["items"][0]
        
        embed = discord.Embed(
            title="Informações da Capital do Clã", 
            description=f"Temporada: {latest_season.get('id', 'N/A')}", 
            color=0x00ff00
        )
        
        # Informações gerais
        start_date = latest_season.get("startTime", "desconhecido")
        end_date = latest_season.get("endTime", "desconhecido")
        embed.add_field(name="Período", value=f"{start_date} até {end_date}", inline=False)
        
        # Recompensas
        offensive_reward = latest_season.get("offensiveReward", 0)
        defensive_reward = latest_season.get("defensiveReward", 0)
        total_rewards = offensive_reward + defensive_reward
        
        embed.add_field(name="Recompensas", value=f"Ofensivas: {offensive_reward}\nDefensivas: {defensive_reward}\nTotal: {total_rewards}", inline=True)
        
        # Total de distritos atacados
        total_districts = latest_season.get("districtsDestroyed", 0)
        total_attacks = latest_season.get("totalAttacks", 0)
        embed.add_field(name="Atividade do Clã", value=f"Distritos destruídos: {total_districts}\nTotal de ataques: {total_attacks}", inline=True)
        
        # Top contribuidores de ouro
        if "members" in latest_season:
            members = latest_season.get("members", [])
            sorted_members = sorted(members, key=lambda x: x.get("capitalResourcesLooted", 0), reverse=True)
            
            contributors = "```\n"
            contributors += f"{'Nome':<15} | {'Ouro':<10}\n"
            contributors += "-" * 30 + "\n"
            
            for i, member in enumerate(sorted_members[:10]):
                if "name" in member and "capitalResourcesLooted" in member:
                    contributors += f"{member['name'][:15]:<15} | {member['capitalResourcesLooted']:<10}\n"
            
            contributors += "```"
            embed.add_field(name="Top Contribuidores de Ouro", value=contributors, inline=False)
        
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"Erro ao processar informações da Capital do Clã: {e}")

# Comando de ajuda
@bot.command(name='ajuda')
async def help_command(ctx):
    embed = discord.Embed(title="Comandos do Bot de Clash of Clans", description="Lista de comandos disponíveis:", color=0x00ff00)
    
    commands = [
        ("!coc clan", "Mostra informações gerais sobre o clã"),
        ("!coc war", "Mostra o status da guerra atual"),
        ("!coc doadores", "Mostra o ranking de doadores do clã"),
        ("!coc trofeus", "Mostra o ranking de troféus do clã"),
        ("!coc capital", "Mostra informações da Capital do Clã"),  # Adicionada esta linha
        ("!coc ajuda", "Mostra esta mensagem de ajuda")
    ]
    
    for cmd, desc in commands:
        embed.add_field(name=cmd, value=desc, inline=False)
    
    await ctx.send(embed=embed)

# Executar o bot
if __name__ == "__main__":
    bot.run(TOKEN)
