# 🎉 ClashGenius - Seu Gênio Assistente e Painel de Guerra para Clash of Clans! (v18.0 Web-Enhanced) 🎉

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Badge"/>
  <img src="https://img.shields.io/badge/discord.py-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord.py Badge"/>
  <img src="https://img.shields.io/badge/coc.py-FFD700?style=for-the-badge" alt="coc.py Badge"/>
  <img src="https://img.shields.io/badge/aiohttp-00AFF0?style=for-the-badge&logo=aiohttp&logoColor=white" alt="aiohttp Badge"/>
</p>

<p align="center">
  <strong>Domine o campo de batalha com informações em tempo real, diretamente no Discord e agora em um painel web interativo!</strong>
</p>

E aí, Chefe! 🏰
Com o **ClashGenius v18.0**, você não apenas leva seu clã para o **próximo nível** com um bot inteligente que monitora tudo **em tempo real**, mas também visualiza todos os dados cruciais em um **PAINEL WEB** com temática de guerra, servido diretamente pelo bot! 🔥

---

## 🌟 NOVIDADE NA v18.0: Painel Web de Monitoramento! 🌟

Agora, além dos alertas no Discord, o ClashGenius oferece um **painel web interativo** para você e seu clã acompanharem:

* 📊 **Visão Geral do Clã:** Nome, tag, nível, descrição, membros, pontos, e mais.
* ⚔️ **Status da Guerra Detalhado:** Informações completas sobre a guerra atual (Normal ou CWL), placar, tempo restante, e informações dos oponentes.
* 🛡️ **Lista de Membros Completa:** Com CV, liga, troféus, doações, e cargos.
* 🎨 **Temática Imersiva:** Um visual inspirado no universo Clash of Clans e em temas de guerra para uma experiência mais rica!
* 🌐 **Acesso Fácil:** Basta acessar `https://SEU_DOMINIO.onrender.com/painel` no seu navegador.
* ⚙️ **Zero Dependências Extras:** O painel é servido diretamente pelo bot Python, sem necessidade de bancos de dados ou serviços adicionais.

<p align="center">
  <em>(Sugestão: Adicione aqui um screenshot ou GIF do seu painel em ação!)</em>
  <br>
  </p>

---

## 🔍 O que há de novo no v18.0?

* 🚀 **NOVO: Painel Web Interativo** para monitoramento visual dos dados do clã, guerra e membros!
* 🎨 **Interface do Painel Web com Temática de Guerra/Clash of Clans** para uma experiência imersiva.
* ✅ Sistema event-driven completo com cache e tratamento de erros.
* ✅ Relatórios automáticos de ataques perdidos (Guerra e CWL).
* ✅ Alertas com menções para ataques de 1 estrela e membros que não atacaram.
* ✅ Logs coloridos e profissionais, com datas localizadas para o Brasil.
* ✅ Sistema de comandos por grupos: `/admin`, `/guerra`, `/info`, `/buscar`, `/rank`.
* ✅ Exibição separada para Guerras Normais e Ligas (CWL).
* ✅ Sistema modular de funções e handlers com divisão por responsabilidades.
* ✅ Mensagens de erro amigáveis e embutidas para cada tipo de falha.

---

## 🧠 O que o ClashGenius faz?

### 👁️ Monitoramento por Eventos (Discord):
* Entrada e saída de membros.
* Doações e recebimentos.
* Mudanças de cargo, troféus e liga.
* Ataques e defesas em **guerras normais** e **ligas de clãs (CWL)**.

### ⚔️ Relatórios Automáticos (Discord):
* Quando uma guerra termina, o bot verifica e avisa quem **não usou todos os ataques**.
* Se alguém ataca com apenas **1 estrela**, o bot envia um alerta mencionando um cargo específico (opcional).

### 🖥️ Visualização de Dados (Painel Web):
* **Dashboard do Clã:** Informações vitais do seu clã em um só lugar.
* **Status da Guerra em Tempo Real:** Acompanhe o progresso da guerra atual.
* **Detalhes dos Membros:** Veja a lista completa de membros e suas estatísticas.
* **Navegação Intuitiva:** Menu para acessar rapidamente as seções de Clã, Guerra e Membros.

---

## 📦 Requisitos

* Python 3.8+
* Conta Supercell ID para gerar API Keys
* Token do Discord Bot
* Canal no Discord para logs
* Um ambiente de hospedagem (como a Render.com, que já suporta o servidor web `aiohttp` do bot)

---

## ⚙️ Como Instalar

1.  **Clone ou baixe o repositório**:
    ```bash
    git clone [https://github.com/AkumaHalls/clashgenius.git](https://github.com/AkumaHalls/clashgenius.git) # Substitua pelo seu repositório se for um fork
    cd clashgenius
    ```

2.  **Crie um ambiente virtual (recomendado)**:
    ```bash
    python -m venv venv
    # Linux/macOS:
    source venv/bin/activate
    # Windows:
    .\venv\Scripts\activate
    ```

3.  **Instale as dependências**:
    ```bash
    pip install -r requirements.txt
    ```
    (Certifique-se de que `aiohttp` e outras dependências como `python-dotenv`, `discord.py`, `coc.py`, `pytz` estão no seu `requirements.txt`)

4.  **Crie o arquivo `.env` com as configurações**:
    ```env
    DISCORD_TOKEN=seu_token_aqui
    COC_EMAIL=seu_email_supercell
    COC_PASSWORD=sua_senha_supercell
    CLAN_TAG=#TAG_DO_CLA
    CHANNEL_ID=ID_DO_CANAL_DE_LOGS_DISCORD
    ROLE_ID_1STAR_ALERT=ID_DO_CARGO_ALERTA_1_ESTRELA (opcional)
    ROLE_ID_MISSED_ATTACK=ID_DO_CARGO_ATAQUES_PERDIDOS (opcional)
    TEST_GUILD_ID=ID_DO_SEU_SERVIDOR_DISCORD_PARA_TESTES_RAPIDOS (opcional)
    # PORT=8080 (Opcional, a Render define automaticamente, mas pode ser útil para testes locais)
    ```
    **Importante:** A pasta `static` com os arquivos `painel.html`, `css/style.css` e `js/scripts.js` deve estar presente no mesmo diretório que o seu script Python principal.

---

## ▶️ Rodando o bot

Com o ambiente ativado e `.env` configurado, rode:

```bash
python clash.py # Ou o nome do seu arquivo python principal
