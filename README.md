# 🏆 Clash of Clans Discord Bot 🏆

<div align="center">
  
  ![Clash of Clans Bot](https://i.imgur.com/oTm5VIO.gif)
  
  [![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
  [![Discord.py](https://img.shields.io/badge/Discord.py-2.0+-blue.svg)](https://discordpy.readthedocs.io/)
  [![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
  
  **Um bot avançado de monitoramento para o seu clã no Clash of Clans! 🚀**
  
</div>

## 📋 Recursos

Este bot monitora automaticamente seu clã do Clash of Clans e envia atualizações para um canal de texto do Discord, incluindo:

- 📥 **Monitoramento de membros** - Notifica quando alguém entra ou sai do clã
- 🎁 **Rastreamento de doações** - Acompanha doações e recebimentos de tropas
- ⚔️ **Alertas de Guerra** - Notifica o início, progresso e fim das guerras de clãs
- 🔍 **Ataques detalhados** - Informa sobre todos os novos ataques durante as guerras
- 📊 **Relatórios diários** - Gera resumos de troféus e ligas de jogadores
- ❌ **Monitoramento de atividade** - Identifica membros que não usaram seus ataques de guerra

## 🤖 Comandos

| Comando | Descrição |
|---------|-----------|
| `!coc clan` | Exibe informações detalhadas sobre o clã |
| `!coc war` | Mostra o status da guerra atual com análise detalhada |
| `!coc doadores` | Exibe o ranking dos top 10 doadores do clã |
| `!coc trofeus` | Mostra o ranking de troféus dos membros do clã |
| `!coc ajuda` | Exibe a lista de comandos disponíveis |

## 🔄 Atualizações Automáticas

### Monitoramento do Clã (a cada 30 minutos)
- 👥 Notifica novos membros e saídas
- 🎁 Rastreia mudanças em doações
- 📊 Gera relatórios diários de troféus

### Monitoramento de Guerra (a cada 15 minutos)
- 🏁 Notifica mudanças no estado da guerra (preparação, início, fim)
- ⚔️ Notifica sobre novos ataques
- 🛡️ Alerta quando a base do seu clã é atacada

## ⚙️ Configuração

### Pré-requisitos
- Python 3.8+
- Token de Bot do Discord
- Chave de API do Clash of Clans
- Tag do seu clã no Clash of Clans

### Variáveis de Ambiente
Configure um arquivo `.env` com as seguintes informações:

```
DISCORD_TOKEN=seu_token_do_discord
COC_API_KEY=sua_chave_api_clash_of_clans
CLAN_TAG=#tag_do_seu_cla
GUILD_ID=id_do_seu_servidor_discord
LOG_CHANNEL_ID=id_do_canal_de_logs
```

### Instalação

1. Clone este repositório
   ```bash
   git clone https://github.com/seu_usuario/clash-of-clans-discord-bot.git
   cd clash-of-clans-discord-bot
   ```

2. Instale as dependências
   ```bash
   pip install -r requirements.txt
   ```

3. Configure o arquivo `.env` com suas credenciais

4. Execute o bot
   ```bash
   python bot.py
   ```

## 📋 Dependências

- [discord.py](https://discordpy.readthedocs.io/) - API Discord para Python
- [aiohttp](https://docs.aiohttp.org/) - Cliente HTTP assíncrono
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Carregamento de variáveis de ambiente

## 🛠️ Como contribuir

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Faça commit das suas alterações (`git commit -m 'Adiciona nova feature'`)
4. Faça push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📸 Demonstração

<div align="center">
  <img src="https://i.imgur.com/example1.png" width="45%" />
  <img src="https://i.imgur.com/example2.png" width="45%" />
</div>

## 📄 Licença

Este projeto está licenciado sob a licença MIT - veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

<div align="center">
  <p>Desenvolvido com ❤️ para a comunidade Clash of Clans</p>
  
  <a href="https://discord.gg/seu-servidor">
    <img src="https://img.shields.io/badge/Discord-Junte--se_ao_nosso_servidor-7289DA?style=for-the-badge&logo=discord&logoColor=white" />
  </a>
</div>
