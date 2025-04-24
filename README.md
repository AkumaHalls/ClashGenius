# 🎉 ClashGenius - Seu Gênio Assistente de Clash of Clans para Discord! (v16 Event-Driven) 🎉

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Badge"/>
  <img src="https://img.shields.io/badge/discord.py-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord.py Badge"/>
  <img src="https://img.shields.io/badge/coc.py-FFD700?style=for-the-badge" alt="coc.py Badge"/>
      </p>

E aí, Chefe! 🏰 Cansado de perder os eventos importantes do seu clã no Clash of Clans enquanto conversa no Discord? Seus problemas acabaram! ✨

O **ClashGenius v16** é um bot esperto para Discord, feito em Python com `coc.py`, que usa **eventos em tempo real** da API do Clash of Clans para ficar de olho no seu clã 24/7 e te contar TUDO o que está rolando, diretamente no seu servidor! ⚔️💰

## 🤖 O que esse Gênio faz?

* **👀 Monitoramento por Eventos (Tempo Real):**
    * 🎁➡️⬅️ Avisa **instantaneamente** sobre Doações, Tropas Recebidas, Entradas e Saídas de membros.
    * 👤⭐ Avisa sobre mudanças de Cargo, Liga e Troféus dos membros.
    * ⚔️ Reporta cada ataque realizado pelos membros do seu clã em Guerras Normais e Guerras de Liga (CWL) assim que ocorrem.
    * *(Nota: Funções como anúncios automáticos de início/fim de guerra, alertas de tempo e monitoramento de raids foram removidas nesta versão baseada em eventos e podem ser re-adicionadas no futuro se necessário).*
* **📊 Comandos de Barra (`/`):**
    * Use comandos de barra intuitivos no Discord para obter infos fresquinhas do clã!
    * Veja rankings de doações, recebidos e troféus.
    * Confira ataques restantes na guerra atual (normal ou CWL).
    * Busque detalhes de jogadores e clãs.
    * Veja rankings globais ou locais.
    * E mais! (Use `/ajuda` no Discord).

## 🚀 Começando em 3, 2, 1... Partiu!

Preparado para turbinar seu servidor Discord com o ClashGenius? É moleza!

1.  **✅ Pré-requisitos:**
    * Tenha o **Python 3.8 ou superior** instalado na sua máquina. Se não tiver, baixe em [python.org](https://www.python.org/).
    * Tenha o `git` instalado (para clonar o repositório, se aplicável).

2.  **🐑 Obtenha o Código:**
    * Faça o download ou clone este repositório.
    * Navegue até a pasta do projeto no seu terminal: `cd ClashGenius` (ou o nome da pasta).

3.  **🛡️ Crie um Ambiente Virtual (Recomendado!):**
    * Para não bagunçar suas instalações Python, vamos criar um ambiente isolado:
        ```bash
        # No Linux/macOS
        python3 -m venv venv
        source venv/bin/activate

        # No Windows
        python -m venv venv
        .\venv\Scripts\activate
        ```
        *(Você verá `(venv)` no início da linha do seu terminal se deu certo!)*

4.  **✨ Instale as Dependências Mágicas:**
    * Com o ambiente virtual ativo, instale tudo que o bot precisa:
        ```bash
        # Se houver um requirements.txt:
        pip install -r requirements.txt
        # Ou instale manualmente (principais dependências):
        # pip install discord.py python-dotenv coc.py aiohttp pytz
        ```
        *(Certifique-se de que todas as bibliotecas importadas no `clash.py` estejam instaladas)*

5.  **🔑 Configure seus Segredos (Arquivo `.env`):**
    * Crie um arquivo chamado `.env` **na mesma pasta** onde está o `clash.py`.
    * **NUNCA compartilhe este arquivo ou envie para o GitHub!** Ele contém suas senhas! Adicione `.env` ao seu arquivo `.gitignore`.
    * Copie e cole o seguinte conteúdo no arquivo `.env`, substituindo os valores após o `=` com suas informações REAIS:

        ```dotenv
        # --- Discord Bot ---
        DISCORD_TOKEN=SEU_TOKEN_SUPER_SECRETO_DO_BOT_DISCORD

        # --- Clash of Clans API Login ---
        # Use as credenciais da sua conta Supercell ID
        COC_EMAIL=seu_email_supercell@exemplo.com
        COC_PASSWORD=sua_senha_supercell_id_aqui

        # --- Configurações do Clã ---
        CLAN_TAG=#SUA_TAG_DE_CLA_AQUI  # IMPORTANTE: Comece com #
        CHANNEL_ID=ID_DO_CANAL_DISCORD_PARA_ANUNCIOS # Apenas números!
        ```
    * **Como pegar as Infos:**
        * `DISCORD_TOKEN`: Crie um Bot no [Portal de Desenvolvedores do Discord](https://discord.com/developers/applications), vá na seção "Bot", clique em "Reset Token" (ou "View Token") e copie o token. **IMPORTANTE:** Habilite as **Privileged Gateway Intents** (Server Members Intent e Message Content Intent) na mesma página do Bot.
        * `COC_EMAIL` / `COC_PASSWORD`: São as credenciais que você usa para logar no Clash of Clans via Supercell ID. Elas são usadas para gerar as API Keys dinamicamente.
        * `CLAN_TAG`: A tag do seu clã no jogo (ex: `#2YC2Y2Y0`). **Precisa começar com `#`**.
        * `CHANNEL_ID`: O ID numérico do canal no Discord onde o bot enviará a maioria das mensagens e logs de eventos. Ative o Modo Desenvolvedor no Discord (Configurações > Avançado), clique com o botão direito no canal desejado e selecione "Copiar ID do Canal".

6.  **▶️ Ligue o Bot!**
    * Finalmente! Com o ambiente virtual ativo e o `.env` configurado, execute:
        ```bash
        python clash.py
        ```
    * Se tudo deu certo, você verá mensagens de log no terminal e o bot ficará online no Discord! 🥳

## ⚙️ Comandos de Barra Mágicos (`/`)

Use esses comandos no Discord (alguns podem requerer permissão de Admin):

* `/ajuda`: Mostra a lista de comandos disponíveis.
* `/admin status`: Exibe um resumo do clã, guerras e status do bot.
* `/admin top [tipo] [limite]`: Mostra rankings do clã.
    * `tipo`: `doacoes`, `recebidos`, `trofeus`.
    * `limite` (opcional): Quantos mostrar (padrão 10).
* `/admin setcanal [canal]`: **(Admin)** Define/altera o canal de logs/eventos.
* `/admin setclan [tag]`: **(Admin)** Muda o clã monitorado.
* `/guerra ataques`: Mostra quem falta atacar na Guerra Normal atual.
* `/guerra liga_ataques`: Mostra quem falta atacar na rodada da CWL atual.
* `/guerra log [limite]`: Exibe o histórico de guerras do clã (requer log público).
* `/info membro [tag]`: Mostra informações detalhadas sobre um jogador.
* `/buscar clan [nome] ...`: Busca clãs por nome e outros filtros.
* `/buscar jogador [nome] [limite]`: Busca jogadores por nome.
* `/rank clans [localizacao] [limite]`: Exibe ranking de clãs de uma localização.
* `/rank jogadores [localizacao] [limite]`: Exibe ranking de jogadores (local ou 'global').
* `/ligas`: Mostra as Ligas do jogo (Vila Principal, Construtor, Capital).

## ✨ Eventos Automáticos (A Mágica Acontece Sozinha!)

O ClashGenius v16 fica de olho e avisa **em tempo real** sobre:

* 🎁 Doações Realizadas
* 📥 Tropas Recebidas
* ➡️ Entradas de Membros
* ⬅️ Saídas de Membros
* 👤 Mudanças de Cargo
* 🌟 Mudanças de Liga
* 🏆 Mudanças de Troféus
* ⚔️ Ataques realizados em Guerras (Normal e CWL)

*(Estes eventos são enviados automaticamente no canal definido pelo `/admin setcanal`)*

## 🤝 Contribuições

Sentiu falta de algo? Encontrou um bug (espero que não! 🐞)? Quer ajudar?

* Abra uma **Issue** no repositório para reportar problemas ou sugerir ideias.
* Faça um **Pull Request** se você fez alguma melhoria incrível!

## 💡 Dúvidas ou Sugestões?

Abra uma **Issue** no repositório do projeto!

---

**Divirta-se usando o ClashGenius v16 para levar seu clã e servidor Discord a um novo nível! 💪**
