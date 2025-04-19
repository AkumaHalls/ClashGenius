# 🎉 ClashGenius - Seu Gênio Assistente de Clash of Clans para Discord! 🎉

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Badge"/>
  <img src="https://img.shields.io/badge/discord.py-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord.py Badge"/>
  <img src="https://img.shields.io/badge/coc.py-FFD700?style=for-the-badge" alt="coc.py Badge"/>
  <img src="https://img.shields.io/github/stars/AkumaHalls/ClashGenius?style=for-the-badge&logo=github" alt="GitHub Stars"/>
  <img src="https://img.shields.io/github/issues/AkumaHalls/ClashGenius?style=for-the-badge&logo=github" alt="GitHub Issues"/>
</p>

E aí, Chefe! 🏰 Cansado de perder os eventos importantes do seu clã no Clash of Clans enquanto conversa no Discord? Seus problemas acabaram! ✨

O **ClashGenius** é um bot super esperto para Discord, feito em Python, que fica de olho no seu clã 24/7 e te conta TUDO o que está rolando, diretamente no seu servidor! Chega de perder doações, entradas/saídas, guerras e até os preciosos ataques do Fim de Semana de Raids! ⚔️💰

## 🤖 O que esse Gênio faz?

* **👀 Monitoramento Ninja:**
    * 🎁 Registra quem doou e recebeu tropas (chega de caloteiros! 😉).
    * ➡️⬅️ Avisa instantaneamente quando um membro entra ou sai do clã.
    * ⚔️ Acompanha guerras normais E de liga (CWL):
        * Anuncia o início da preparação e da batalha!
        * Reporta cada ataque realizado pelos seus membros.
        * Dá alertas quando o tempo da guerra está acabando! ⏰
        * Grita VITÓRIA (ou consola na derrota 😥) e mostra quem não atacou! ❌
    * 🏰 Fica de olho no Fim de Semana de Raid:
        * Avisa quando começa e termina!
        * Mostra o progresso do ouro coletado! 💰
        * Comemora distritos destruídos! 🎉
        * Lista os maiores contribuidores no final! 🌟
* **📊 Comandos Informativos (para Admins):**
    * Use comandos simples no Discord para obter infos fresquinhas do clã!
    * Veja rankings de doações, troféus e mais!
    * Confira ataques restantes na guerra.
    * Busque detalhes de um membro específico.
    * E muito mais! (Use `!ajuda` no Discord).

## 🚀 Começando em 3, 2, 1... Partiu!

Preparado para turbinar seu servidor Discord com o ClashGenius? É moleza!

1.  **✅ Pré-requisitos:**
    * Tenha o **Python 3.8 ou superior** instalado na sua máquina. Se não tiver, baixe em [python.org](https://www.python.org/).
    * Tenha o `git` instalado (para clonar o repositório).

2.  **🐑 Clone a Magia:**
    Abra seu terminal ou prompt de comando e digite:
    ```bash
    git clone [https://github.com/AkumaHalls/ClashGenius.git](https://github.com/AkumaHalls/ClashGenius.git)
    cd ClashGenius
    ```

3.  **🛡️ Crie um Ambiente Virtual (Recomendado!):**
    Para não bagunçar suas instalações Python, vamos criar um ambiente isolado:
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
    Com o ambiente virtual ativo, instale tudo que o bot precisa com um comando:
    ```bash
    pip install -r requirements.txt
    ```

5.  **🔑 Configure seus Segredos (Arquivo `.env`):**
    * Crie um arquivo chamado `.env` **na mesma pasta** onde está o `clash.py`.
    * **NUNCA compartilhe este arquivo ou envie para o GitHub!** Ele contém suas senhas! Adicione `.env` ao seu arquivo `.gitignore` se ainda não estiver lá.
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
        * `DISCORD_TOKEN`: Crie um Bot no [Portal de Desenvolvedores do Discord](https://discord.com/developers/applications), habilite as **Privileged Gateway Intents** (Server Members Intent e Message Content Intent) e copie o Token do Bot.
        * `COC_EMAIL` / `COC_PASSWORD`: São as credenciais que você usa para logar no Clash of Clans via Supercell ID.
        * `CLAN_TAG`: A tag do seu clã no jogo (ex: `#2YC2Y2Y0`). **Precisa começar com `#`**.
        * `CHANNEL_ID`: O ID numérico do canal no Discord onde o bot enviará as mensagens. Ative o Modo Desenvolvedor no Discord (Configurações > Avançado), clique com o botão direito no canal desejado e selecione "Copiar ID do Canal".

6.  **▶️ Ligue o Bot!**
    Finalmente! Com o ambiente virtual ativo e o `.env` configurado, execute:
    ```bash
    python clash.py
    ```
    Se tudo deu certo, você verá mensagens de log no terminal e o bot ficará online no Discord! 🥳

## ⚙️ Comandos Mágicos (Para Admins no Discord)

Use esses comandos no canal que você configurou:

* `!ajuda` ou `!help`: Mostra esta lista incrível de comandos!
* `!status`: Exibe um resumo completão do clã, guerras, raids e status do bot.
* `!top [tipo] [limite]`: Mostra rankings!
    * `tipo`: `doacoes`, `recebidos`, `trofeus`, `capital` (para o último raid).
    * `limite` (opcional): Quantos mostrar (padrão 10). Ex: `!top doacoes 5`
* `!ataques`: Mostra quem ainda não atacou na Guerra Normal atual.
* `!ligaataques`: Mostra quem ainda não atacou na Guerra de Liga (CWL) atual.
* `!membro #TAGJOGADOR`: Mostra informações detalhadas sobre um jogador.
* `!capital`: Exibe informações sobre o Capital do Clã e o último/atual Raid Weekend.
* `!setcanal #canal`: **(Admin)** Define/altera o canal onde o bot envia as mensagens.
* `!setclan #NOVATAG`: **(Admin)** Muda o clã que o bot está monitorando (limpa caches antigos!).

## ✨ Eventos Automáticos (A Mágica Acontece Sozinha!)

O ClashGenius fica de olho e avisa sobre:

* Doações e Tropas Recebidas
* Entradas e Saídas de Membros
* Início de Preparação e Batalha de Guerras (Normal e CWL)
* Ataques realizados em Guerras
* Alertas de Tempo Restante para Guerra
* Fim de Guerras (Vitória/Derrota/Empate)
* Membros que não atacaram na Guerra
* Início e Fim do Raid Weekend
* Progresso de Ouro e Distritos Destruídos no Raid

## 🤝 Contribuições

Sentiu falta de algo? Encontrou um bug (espero que não! 🐞)? Quer ajudar?

* Abra uma [Issue](https://github.com/AkumaHalls/ClashGenius/issues) para reportar problemas ou sugerir ideias.
* Faça um [Pull Request](https://github.com/AkumaHalls/ClashGenius/pulls) se você fez alguma melhoria incrível!

## 💡 Dúvidas ou Sugestões?

Abra uma [Issue](https://github.com/AkumaHalls/ClashGenius/issues) no repositório!

---

**Divirta-se usando o ClashGenius para levar seu clã e servidor Discord a um novo nível! 💪**
