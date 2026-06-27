# ⚡ CLASHGENIUS — O GÊNIO DAS GUERRAS 🧠🔥

![Versão](https://img.shields.io/badge/versão-31.2.1--GeniusLib--v4.3.0-ff00aa?style=flat-square&logo=python)
![Status](https://img.shields.io/badge/Status-Operacional-00ff41?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10%2B-0080ff?logo=python&style=flat-square)
![Hospedagem](https://img.shields.io/badge/hospedagem-render.com-00fff9?style=flat-square&logo=render)
![Tema](https://img.shields.io/badge/tema-cyberpunk--2088-b300ff?style=flat-square)

> **ClashGenius** é um bot + painel web definitivo para análise completa do seu clã no Clash of Clans.  
> Monitoramento em tempo real, inteligência artificial preditiva, detecção de smurfs, plano de rotação CWL e um **painel web cyberpunk** com neons, partículas e tooltips interativas.

---

## 🚀 DESTAQUES

### 🖥️ PAINEL WEB CYBERPUNK
Acesse em: `https://SEU_DOMINIO.onrender.com/painel`

| Aba | Descrição |
|-----|-----------|
| **Clã** | Visão geral com badges neon, barra de ocupação animada, cards pulsantes de estatísticas e gráfico de desempenho das últimas guerras |
| **Destaques** | Top 3 doadores, heróis da última guerra (MVP) e gráfico de atividade |
| **Guerra** | Detalhes completos, previsão da IA, plano de ataque inteligente, eventos e escalações |
| **Ataques Pendentes** | Cartões de alerta com gravidade (amarelo/vermelho) e tooltips explicativos |
| **CWL** | Status da liga, cronograma, e plano de rotação gerado por IA |
| **Jogos do Clã** | Progresso da caravana, top farmers e parasitas (0 pontos) |
| **Capital** | Raio-X completo: ataques, saque, ausentes e incompletos |
| **Histórico** | Log completo de guerras passadas com modal detalhado |
| **Membros** | Grid completo com fotos, status CWL, notas, prioridades e perfil individual com análise de IA |
| **Upgrades** (novo) | Modal de perfil agora exibe botão **🔨 Upgrades** com custo total de ouro, elixir, DE e tempo estimado para maximizar — alimentado pelo `Upgrade Tracker` da GeniusLib |

### 🧠 INTELIGÊNCIA ARTIFICIAL

- **War Prediction System v3** — Ensemble de GradientBoosting + RandomForest para prever resultados de guerra
- **War Advisor** — Plano de ataque tático com recomendações por membro e contagem regressiva de fase
- **CWL Rotation Planner** — Escalação inteligente com rotação justa baseada em participação
- **Player Analytics (K-Means)** — Classifica cada membro em tiers (General, Especialista, Instável, Risco)
- **Random Forest** — Calcula a confiabilidade de cada jogador atacar na próxima guerra
- **Smurf Detection (XAI)** — DBSCAN + Cosseno + Fuzzy Logic + DTW para detectar contas vinculadas

### 🔨 UPGRADE TRACKER (novo)
- Integração com `geniuslib.upgrade_tracker` — estimativa de custos e tempo de upgrades
- Comando Discord `/upgrades @jogador` com resumo completo de ouro/elixir/DE/tempo
- Botão **🔨 Upgrades** no modal de perfil do painel web
- Aba **Upgrades** no perfil interativo (`!ver`) com dados reais da API
- Cálculo automático de tudo que falta para maximizar até o próximo TH

### 📤 EXPORTADOR DE DADOS (novo)
- Exporte dados do clã e membros em **JSON** ou **CSV**
- Comando Discord `/exportar clan` ou `/exportar membros` (admin)
- Botões de exportação no painel web (seção Membros) e no painel admin
- Download direto via Blob — sem necessidade de serviços externos

### ⚖️ COMPARADOR DE JOGADORES (novo)
- Comando Discord `/comparar @jogador1 @jogador2`
- Comparação lado a lado: TH, troféus, estrelas de guerra, ataques, defesas, doações
- Diferença numérica entre os dois jogadores
- API REST `/api/compare/players` e `/api/compare/clans`

### 🔗 MIDDLEWARE PIPELINE (novo)
- Pipeline de middlewares request/response registrado no HTTP client da GeniusLib
- Logging automático de todas as requisições à API CoC
- Monitoramento de latência e status codes anômalos (4xx/5xx)
- Integração com o sistema de Health Stats existente no admin

### 🕵️ RADAR PERICIAL (ANTI-SMURF)

- Análise fonética de nomes (fuzzywuzzy)
- Similaridade de vetores de progresso (distância de cossenos)
- Forense de laboratório (Mula Signature)
- Correlação temporal de ataques (Dynamic Time Warping)
- Painel de julgamento: **Absolver** (falso positivo) ou **Condenar** (envia para Watchlist)

### 🔐 PAINEL ADMIN

Acesse em: `https://SEU_DOMINIO.onrender.com/admin`

- **Login** com tela de "Área Restrita" com efeitos de raio e fogo
- **Geral** — Controle de manutenção, informações do sistema
- **Diagnóstico** — Status da API CoC e logs recentes
- **Configurações** — Gerenciamento completo de canais, cargos e funções do Discord
- **Watchlist** — Lista de observação com filtro e remoção
- **Radar Pericial** — Dossiê completo de smurfs com julgamento
- **Analytics IA** — Classificação de todos os membros por machine learning
- **Ações** — Cache, sincronização de comandos slash e anúncios
- **Base de Dados** — Visualizador do MongoDB (guerras e notas)
- **DiscoHook** — Editor visual de embeds do Discord: crie mensagens ricas com múltiplos embeds, campos, cores, imagens e envie diretamente via Webhook — com preview ao vivo estilo Discord e detecção automática de nome/avatar do webhook

### 🎨 TEMA CYBERPUNK 2088

- Cores neon: ciano (`#00fff9`), rosa (`#ff00aa`), roxo (`#b300ff`), verde (`#00ff41`)
- Animações: scanlines, grid background, glow pulsante, glitch text
- Partículas flutuantes no background
- Tooltips neon interativos em todos os elementos
- Cards com bordas animadas e cantos cyberpunk
- Efeito de varredura (card-scan) nos cards
- Fontes: Orbitron (títulos), Rajdhani (corpo), Fira Code (mono)

---

## 📋 FUNCIONALIDADES COMPLETAS

### 👁️ EVENTOS MONITORADOS (DISCORD)
- Entrada/saída de membros com embed detalhado
- Doações recebidas e enviadas
- Mudanças de cargo, liga e troféus
- Alertas de guerra (início, fim, ataques perdidos)
- Notificações de CWL, Jogos do Clã e Capital
- Detecção e alerta de smurfs

### 📊 MÉTRICAS POR MEMBRO
- Perfil completo com heróis, liga e tropas
- Hitrate: estrelas, destruição média, taxa de participação
- Evolução de troféus (gráfico interativo Chart.js)
- Última guerra registrada
- Notas personalizadas com prioridade (verde/amarelo/vermelho)
- Status CWL: Fixo (⭐), Ativo ou Reserva
- **Upgrade Tracker** — custo total de ouro/elixir/DE e tempo para maximizar o jogador (novo)
- **Exportação** — download do perfil em JSON (novo)

### 📤 EXPORTAÇÃO (novo)
- Exporte dados completos do clã (JSON) e dos membros (CSV)
- Botões no painel web e no painel admin
- Comando Discord `/exportar` para administradores

### ⚖️ COMPARAÇÃO (novo)
- Compare dois jogadores lado a lado com `/comparar`
- Diferenças destacadas em TH, troféus, estrelas, doações

---

## 📦 REQUISITOS

- Python 3.10+
- Conta Supercell ID (API Developer)
- Bot do Discord com token e intents configuradas
- Canal de logs no Discord
- MongoDB Atlas (ou local) para persistência
- Render.com ou similar para hospedagem
- **Dependências**: `discord.py`, `geniuslib (v4.3.0+)`, `aiohttp`, `motor`, `pymongo`, `numpy`, `scikit-learn`, `thefuzz`, `cryptography`, `python-dotenv`, `pytz`, `pillow`, `matplotlib`

---

## ⚙️ INSTALAÇÃO

```bash
# Clone
git clone https://github.com/seu-repo/ClashGenius.git
cd ClashGenius

# Ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/macOS
. venv\Scripts\activate    # Windows

# Dependências
pip install -r requirements.txt
```

### 🔧 Configuração (.env)

```env
DISCORD_TOKEN=seu_token_discord
COC_EMAIL=seu_email_supercell
COC_PASSWORD=sua_senha_supercell
CLAN_TAG=#TAG_DO_CLAN
CHANNEL_ID=id_canal_logs
MONGO_DB_URL=sua_url_mongodb
ADMIN_PASSWORD=senha_admin
FERNET_KEY=chave_criptografia
BASE_URL=https://seu-site.onrender.com
```

Para gerar a `FERNET_KEY`:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### ▶️ Executar

```bash
python clash.py
```

---

## 🏗️ ARQUITETURA

```
ClashGenius/
├── clash.py                  # Inicialização e servidor web aiohttp
├── war_predictor.py          # Sistema de previsão (ML ensemble)
├── formatting.py             # Utilitários de formatação
├── cogs/
│   ├── admin_cog.py          # Painel de administração
│   ├── web_api_cog.py        # API REST do painel web
│   ├── tasks_cog.py          # Tarefas em segundo plano
│   ├── events_cog.py         # Monitoramento de eventos
│   ├── database_cog.py       # Camada de persistência MongoDB
│   ├── smurf_detection_cog.py # Detecção de smurfs (XAI)
│   ├── player_analytics_cog.py # K-Means + Random Forest
│   ├── war_advisor_cog.py    # Conselheiro de guerra IA
│   ├── cwl_planner_cog.py    # Planejador CWL
│   ├── capital_cog.py        # Monitoramento da Capital
│   ├── clan_games_cog.py     # Rastreador de Jogos do Clã
│   ├── profile_cog.py        # Perfil de membros
│   ├── watchlist_cog.py      # Lista de observação
│   ├── donation_cog.py       # Monitoramento de doações
│   ├── performance_cog.py    # Análise de performance
│   ├── maintenance_cog.py    # Modo manutenção
│   ├── slash_cog.py          # Comandos slash
│   ├── general_cog.py        # Comandos gerais
│   ├── super_profile_cog.py  # Perfil super detalhado
│   ├── post_war_analysis.py  # Análise pós-guerra
│   └── __init__.py
└── static/
    ├── painel.html            # Página principal
    ├── admin_login.html       # Login admin (com raio e fogo)
        ├── admin_panel.html       # Painel admin (inclui aba DiscoHook)
        ├── maintenance.html       # Página de manutenção
    ├── css/
    │   └── style.css          # Tema cyberpunk completo
    └── js/
        ├── scripts.js         # Lógica do painel principal
        └── admin.js           # Lógica do painel admin
```

---

## 🔄 VERSÃO ATUAL: 31.2.1-GeniusLib-v4.3.0

### Últimas atualizações (v31.2.0)

- **GeniusLib v4.3.0** — integração completa com TH18 e novos conteúdos:
  - **Dragon Duke** — novo herói voador adicionado a todos os perfis e análises
  - **Ruin Witch, Angry Spell, Greedy Raven, Meteor Castle** — novos itens de jogo em constantes e upgrade tracker
  - **PlayerClan expandido** — campos `clan_points`, `clan_capital_points` agora disponíveis
  - **Battlelog & League History** — novos endpoints disponíveis na API
  - **Upgrade Tracker TH18** — níveis máximos para todas as categorias (BK/AQ nv 110, GW nv 85, etc.)
- **Perfis atualizados** — Dragon Duke visível em todos os comandos de perfil (`!perfil`, `!ver`, web)
- **Análise Rushed** — agora suporta TH17 e TH18 com metas de heróis atualizadas
- **Detecção de pets corrigida** — `!ver` agora lê pets de `player.pets` em vez de `player.heroes`

### Versões anteriores

- **GeniusLib v4.1.0** — Formatters, Raid Analytics, Health Stats
- **Tema Cyberpunk 2088** — overhaul visual completo com neons, animações e partículas
- **Aba CLAN reformulada** — badge neon, barra de ocupação, cards pulsantes, gráfico de desempenho
- **Tooltips interativos** — sistema global de tooltips neon em todo o site
- **Clique liberado** — qualquer visitante pode ver perfis de membros
- **Admin com raio e fogo** — tela de login com efeitos dramáticos de área restrita
- **Aba DiscoHook** — editor visual de embeds do Discord no painel admin
- **Radar Pericial corrigido** — membros que saem do clã somem automaticamente do radar
- **Gráfico de desempenho** — barras visuais das últimas 10 guerras no resumo do clã

---

## 📜 LICENÇA

MIT — Use, modifique e compartilhe livremente.

---

<p align="center">
  <sub>Feito com ❤️ por +Constantine+ e a comunidade</sub><br>
  <sub>Clash Genius Bot v31.2.1-GeniusLib-v4.3.0</sub>
</p>
