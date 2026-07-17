# ClashGenius — O Gênio das Guerras

![Versao](https://img.shields.io/badge/versao-32.2.3--GeniusLib--v5.3.0-182c61?style=flat-square&logo=python)
![Status](https://img.shields.io/badge/Status-Operacional-16a34a?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10%2B-2563eb?logo=python&style=flat-square)
![Hospedagem](https://img.shields.io/badge/hospedagem-render.com-0ea5e9?style=flat-square&logo=render)

> **ClashGenius** é um bot Discord + painel web para análise completa de clãs no Clash of Clans.
> Monitoramento em tempo real, inteligência artificial preditiva, detecção de smurfs, plano de rotação CWL e um **painel web profissional** com sidebar, dark/light theme e analytics avançados.

---

## Destaques

| Módulo | Descrição |
|--------|-----------|
| **Painel Web** | Dashboard com sidebar, 10 abas (Clã, Destaques, Guerra, Pendências, CWL, Jogos, Capital, Legend, Histórico, Membros), dark/light theme |
| **Legend League** | Análise completa de battle logs: ataques, defesas, saques, exércitos com cópia para o Clash, histórico de progressão |
| **Inteligência Artificial** | War Prediction (ensemble ML), War Advisor (algoritmo húngaro), Player Analytics (K-Means), Smurf Detection (IsolationForest + XGBoost), CWL Planner (K-Means + fairness) |
| **Painel Admin** | 9 abas: Geral, Diagnóstico, Configurações, Watchlist, Radar Pericial, Analytics IA, Ações, Base de Dados, DiscoHook |
| **Segurança** | Auth com registro/aprovação, CSRF, XSS sanitization, encrypted sessions, security headers, anti-DevTools |

---

## Painel Web

Acesse em: `https://SEU_DOMINIO.onrender.com/painel`

### Abas Públicas

| Aba | Descrição |
|-----|-----------|
| **Clã** | Visão geral com badge, barra de ocupação, cards de estatísticas, gráfico de desempenho das últimas guerras |
| **Destaques** | Top 3 doadores, heroes da última guerra (MVP), gráfico de atividade |
| **Guerra** | Detalhes completos, previsão da IA, plano de ataque inteligente, eventos e escalações |
| **Pendências** | Cartões de alerta com gravidade (amarelo/vermelho) e tooltips |
| **CWL** | Status da liga, cronograma e plano de rotação gerado por IA |
| **Jogos do Clã** | Progresso da caravana, top farmers e parasitas (0 pontos) |
| **Capital** | Raio-x: ataques, saque, ausentes e incompletos |
| **Legend** | Dashboard de Legend League com seletor de jogador, 4 cards de resumo e 5 sub-abas |
| **Histórico** | Log completo de guerras passadas com modal detalhado |
| **Membros** | Grid com fotos, status CWL, notas, prioridades e perfil individual com análise de IA |

### Sub-Abas da Legend

| Sub-aba | Conteúdo |
|---------|----------|
| **Ataques** | Estatísticas de ataque (total, vitórias, derrotas, estrelas médias, destruição média) |
| **Defesas** | Estatísticas defensivas (total, vitórias, derrotas, estrelas concedidas) |
| **Saques** | Resumo de saques (total, ouro, elixir, elixir negro, média por ataque) |
| **Exércitos** | Cards estruturados por composição com desempenho, badges de tropas, heroes com pets/equipamento, botão copiar para importar no Clash |
| **Histórico** | Progressão de ligas ao longo das temporadas |

---

## Inteligência Artificial

### War Prediction System v3
- **Algoritmo**: Ensemble de GradientBoosting + RandomForest
- **Features**: diferença de estrelas, vantagem de TH, momentum, sinergia do clã, pressão
- **Saída**: probabilidade de vitória com nível de confiança

### War Advisor
- **Algoritmo**: Algoritmo Húngaro (scipy `linear_sum_assignment`)
- **Estratégias**: mirror, dip, safe, cleanup, bonus, desperate
- **Fases**: prep, early, late (contagem regressiva de fase)
- **Força do jogador**: TH + heroes + equipment + pets

### Player Analytics
- **Algoritmo**: K-Means (4 clusters) + RandomForest
- **Classificação**: General, Especialista, Instável, Risco
- **Saída**: probabilidade de atacar na próxima guerra

### Smurf Detection v3
- **Algoritmos**: IsolationForest + XGBoost + Distância Cosseno + Fuzzy Logic + Calibração Bayesiana
- **Sinais**: análise fonética de nomes, vetores de tropas, sincronização de doações, sincronização de guerra, clustering de conquistas, assinatura forense (Mula Signature)
- **Telemetria**: feedback loop com rotulagem de falsos positivos

### CWL Planner
- **Algoritmo**: K-Means clustering + fairness scoring
- **Estratégias**: agressivo, balanceado, justo
- **Participação**: peso baseado no histórico de participação

---

## Comandos Discord

### Slash Commands

| Comando | Descrição |
|---------|-----------|
| `/legend [tag]` | Battle log de Legend League |
| `/legend_historico [tag]` | Histórico de ligas |
| `/legend_resumo [dias]` | Resumo da clan em Legend |
| `/legend_exercitos [tag]` | Composições de exércitos |
| `/perfil <jogador>` | Perfil completo (heroes, liga, hitrate, equipment, pets) |
| `/upgrades <jogador>` | Upgrade tracker (gold/elixir/DE/tempo para max) |
| `/comparar <j1> <j2>` | Comparação lado a lado com diferenças |
| `/exportar <tipo> <formato>` | Exportar clan/membros em JSON ou CSV |
| `/plano_guerra` | Gerar plano de ataque IA |
| `/analise_guerra` | Análise de equilíbrio de guerra |
| `/buscar_clas <nome> [limite]` | Buscar clans por nome |
| `/war_log [tag]` | Histórico de guerras |
| `/verificar_conta <tag> <token>` | Verificar conta CoC via API token |
| `/legends [tag]` | Estatísticas de Legend League |
| `/painel_admin` | Gerar link seguro do painel admin |
| `/doacoes <periodo>` | Relatório de doações (admin) |
| `/sync <escopo>` | Sincronizar comandos slash |
| `/smurfs_scan` | Scan manual de smurfs |
| `/relatorio_desempenho` | Relatório de performance semanal |
| `/ping` | Latência do bot |

### Comandos de Prefixo

| Comando | Descrição |
|---------|-----------|
| `!ping` | Latência do bot |
| `!ver <tag>` | Perfil super detalhado com UI Discord (botões, upgrade tracker, barras de progresso) |

---

## Painel Admin

Acesse em: `https://SEU_DOMINIO.onrender.com/admin`

### Sistema de Auth
- Registro com aprovação pendente
- Roles: admin (acesso total) e viewer (somente leitura)
- Senhas com PBKDF2 (100k iterações + salt)
- Sessions com cookies criptografados (Fernet)
- CSRF token em todos os endpoints POST

### Abas

| Aba | Descrição |
|-----|-----------|
| **Geral** | Controle de manutenção, informações do sistema |
| **Diagnóstico** | Status da API CoC, logs recentes, health stats |
| **Configurações** | Gerenciamento de canais, cargos e funções do Discord |
| **Watchlist** | Lista de observação com filtro e remoção |
| **Radar Pericial** | Dossiê completo de smurfs com julgamento (Absolver/Condenar) |
| **Analytics IA** | Classificação de todos os membros por ML |
| **Ações** | Cache, sincronização de comandos, anúncios, **envio de changelog para Discord** |
| **Base de Dados** | Visualizador do MongoDB (guerras e notas) |
| **DiscoHook** | Editor visual de embeds do Discord com preview ao vivo |

### Botão de Changelog

Na aba **Ações** do painel admin, o botão **📋 Enviar Changelog para Discord** lê o `CHANGELOG.md`, extrai a versão mais recente e envia um embed formatado com emojis para o canal configurado (`CHANGELOG_CHANNEL_ID`).

| Categoria | Emoji |
|-----------|-------|
| Adicionado | ✨ |
| Alterado | 🔧 |
| Corrigido | 🐛 |
| Removido | 🗑️ |
| Sincronizado | 🔄 |

---

## API REST

### Endpoints Públicos (19)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/clan` | GET | Dados do clã |
| `/api/members` | GET | Lista completa de membros |
| `/api/current_war_details` | GET | Guerra atual com detalhes e previsão |
| `/api/war_log` | GET | Histórico de guerras |
| `/api/cwl_info` | GET | Informações da CWL |
| `/api/highlights` | GET | Destaques (doadores, MVP, atividade) |
| `/api/capital` | GET | Dados de raid da Capital |
| `/api/clan_games` | GET | Progresso dos Jogos do Clã |
| `/api/player_profile/{tag}` | GET | Perfil detalhado do jogador |
| `/api/player_upgrades/{tag}` | GET | Upgrade tracker do jogador |
| `/api/legend` | GET | Dados de Legend League |
| `/api/legend/history` | GET | Histórico de Legend League |
| `/api/legend/clan` | GET | Resumo da clan em Legend |
| `/api/export/clan` | GET | Exportar dados do clã |
| `/api/export/players` | GET | Exportar dados dos membros |
| `/api/compare/players` | GET | Comparar dois jogadores |
| `/api/compare/clans` | GET | Comparar dois clans |
| `/api/coc_status` | GET | Status da conexão com API CoC |
| `/api/status` | GET | Status do bot |

### Endpoints Admin (16+)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/admin/diagnostics` | GET | Diagnósticos do sistema |
| `/api/admin/settings` | GET/POST | Configurações do bot |
| `/api/admin/db_viewer` | GET | Visualizador do MongoDB |
| `/api/admin/actions` | POST | Ações (cache, sync, anúncios, changelog) |
| `/api/admin/watchlist` | GET | Watchlist |
| `/api/admin/watchlist/add` | POST | Adicionar à watchlist |
| `/api/admin/watchlist/remove` | POST | Remover da watchlist |
| `/api/admin/smurf_dossier` | GET | Dossiê de smurfs |
| `/api/admin/discord_data` | GET | Canais e cargos do Discord |
| `/api/admin/auth/login` | POST | Login |
| `/api/admin/auth/register` | POST | Registro |
| `/api/admin/auth/pending` | GET | Usuários pendentes |
| `/api/admin/auth/approve/{user}` | POST | Aprovar usuário |
| `/api/admin/auth/reject/{user}` | POST | Rejeitar usuário |
| `/api/admin/auth/users` | GET | Listar usuários |
| `/api/admin/auth/role` | POST | Alterar role |

---

## Tarefas Automáticas

| Tarefa | Frequência | Descrição |
|--------|------------|-----------|
| War End Detection | 5 min | Detecta fim de guerra, armazena no DB |
| Donation Snapshots | 1 hora | Snapshots de doações para tendências |
| API Status Check | 10 min | Ping na API CoC, rastreia status |
| CWL End Detection | 5 min | Detecta fim da temporada CWL |
| Battle Log Snapshot | 2 horas | Busca battle logs de todos os membros Legend |
| Daily Legend Report | 23:59 | Relatório diário de Legend no Discord |
| Clan Games Snapshot | 6 horas | Progresso dos Jogos do Clã |
| Capital Raid Snapshot | 6 horas | Dados de raid da Capital |
| Donation Report | 22:00 diário | Relatório diário de doações |
| Donation Weekly | Segunda 22:00 | Relatório semanal de doações |
| Performance Audit | Segunda 20:00 | Identifica leeches, desertores, zero-doações |
| Smurf Monitor | 15 min | Monitora mudanças no clã para sinais de smurf |
| Smurf Retrain | 6 horas | Retreina modelo XGBoost com nova telemetria |

---

## Segurança

| Recurso | Descrição |
|---------|-----------|
| **XSS Sanitization** | `escapeHtml()` em todo output dinâmico |
| **CSRF Protection** | Token em todos os endpoints POST |
| **Encrypted Sessions** | Cookies criptografados com Fernet |
| **PBKDF2** | Hash de senhas com 100k iterações + salt |
| **Security Headers** | X-Content-Type-Options, X-Frame-Options, Referrer-Policy |
| **Anti-DevTools** | Bloqueio de right-click, F12, Ctrl+Shift+I/J/C |
| **Role-Based Access** | admin vs viewer no painel admin |
| **Cache TTL** | 45s para web API, 300s para API CoC |

---

## Tema Visual

### v32 — Design Profissional
- Layout sidebar vertical (estilo ClashLens)
- Inter font (tipografia moderna)
- Tema dark/light com toggle
- CSS variables completo
- Tailwind CDN para utilitários
- Cards e componentes com espaçamento consistente

### Abas e Sub-abas
- Navegação vertical na sidebar
- Tabs internas com borda inferior
- Grid responsivo com `auto-fit`
- Hover com borda accent

---

## Requisitos

- Python 3.10+
- Conta Supercell ID (API Developer)
- Bot do Discord com token e intents
- Canal de logs no Discord
- MongoDB Atlas (ou local)
- Render.com ou similar para hospedagem

### Dependências

| Pacote | Versão | Finalidade |
|--------|--------|------------|
| `discord.py` | 2.5.2 | Framework do bot Discord |
| `geniuslib` | v5.3.0 | Wrapper async da API CoC (models, analytics, formatters, upgrade tracker, exporter, comparer, battlelog, middleware) |
| `python-dotenv` | latest | Variáveis de ambiente |
| `aiohttp` | latest | Servidor web + HTTP client |
| `pytz` | latest | Timezone |
| `motor` | latest | Driver async MongoDB |
| `aiohttp-session` | latest | Sessões HTTP |
| `cryptography` | latest | Criptografia Fernet |
| `pandas` | latest | Manipulação de dados para ML |
| `xgboost` | latest | Classificador para detecção de smurfs |
| `numpy` | 1.26.4 | Computação numérica |
| `scikit-learn` | 1.4.1.post1 | ML (KMeans, RandomForest, IsolationForest, GradientBoosting) |
| `thefuzz` | 0.22.1 | Fuzzy string matching |
| `python-Levenshtein` | 0.25.0 | Distância Levenshtein rápida |
| `scipy` | latest | Algoritmo húngaro |
| `Pillow` | >=10.0.0 | Geração de imagens de Capital |
| `psutil` | latest | Diagnósticos do sistema |

---

## Instalação

```bash
# Clone
git clone https://github.com/AkumaHalls/ClashGenius.git
cd ClashGenius

# Ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/macOS
. venv\Scripts\activate    # Windows

# Dependências
pip install -r requirements.txt
```

### Variáveis de Ambiente (.env)

```env
# Obrigatório
DISCORD_TOKEN=seu_token_discord
COC_EMAIL=seu_email_supercell
COC_PASSWORD=sua_senha_supercell
CLAN_TAG=#TAG_DO_CLAN
CHANNEL_ID=id_canal_logs
MONGO_DB_URL=sua_url_mongodb
ADMIN_PASSWORD=senha_admin
FERNET_KEY=chave_criptografia
BASE_URL=https://seu-site.onrender.com

# Opcional (canais dedicados)
AI_LOG_CHANNEL_ID=
POST_WAR_ANALYSIS_CHANNEL_ID=
POST_WAR_VERDICT_CHANNEL_ID=
CLAN_GAMES_CHANNEL_ID=
CWL_PLANNER_CHANNEL_ID=
DONATIONS_CHANNEL_ID=
SMURF_LOG_CHANNEL_ID=
WATCHLIST_ALERT_CHANNEL_ID=
LOW_PERFORMANCE_CHANNEL_ID=
CAPITAL_REPORT_CHANNEL_ID=
MAINTENANCE_ALERT_CHANNEL_ID=
WAR_PREFERENCE_CHANNEL_ID=
CHANGELOG_CHANNEL_ID=1526649554240536687

# Opcional (roles)
ROLE_ID_1STAR_ALERT=
ROLE_ID_MISSED_ATTACK=
LEADER_ROLE_ID=
COLEADER_ROLE_ID=

# Opcional (config)
AUTO_ADD_WATCHLIST_ENABLED=true
PORT=10000
RENDER=false
```

Para gerar a `FERNET_KEY`:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### Executar

```bash
python clash.py
```

---

## Arquitetura

```
ClashGenius/
├── clash.py                        # Bot + servidor web aiohttp
├── war_predictor.py                # Motor de previsão ML
├── formatting.py                   # Utilitários de formatação
├── simple_cache.py                 # Cache in-memory TTL com LRU
├── CHANGELOG.md                    # Histórico de versões
├── requirements.txt                # Dependências
├── cogs/
│   ├── admin_cog.py               # Backend do admin + changelog sender
│   ├── web_api_cog.py             # API REST do painel web
│   ├── tasks_cog.py               # Tarefas em segundo plano
│   ├── events_cog.py              # Event listeners do Discord
│   ├── database_cog.py            # Persistência MongoDB
│   ├── slash_cog.py               # 14+ slash commands
│   ├── general_cog.py             # Comandos gerais (!ping)
│   ├── profile_cog.py             # Dados de perfil
│   ├── super_profile_cog.py       # Perfil super detalhado (!ver)
│   ├── war_predictor_cog.py       # Previsão de guerra (ML)
│   ├── war_advisor_cog.py         # Conselheiro de guerra IA
│   ├── cwl_planner_cog.py         # Planejador CWL
│   ├── clan_games_cog.py          # Rastreador de Jogos do Clã
│   ├── capital_cog.py             # Monitoramento da Capital
│   ├── donation_cog.py            # Rastreamento de doações
│   ├── watchlist_cog.py           # Lista de observação
│   ├── smurf_detection_cog.py     # Detecção de smurfs (ML)
│   ├── performance_cog.py         # Auditoria de performance
│   ├── maintenance_cog.py         # Modo manutenção
│   ├── player_analytics_cog.py    # Análise de jogadores (ML)
│   ├── battlelog_cog.py           # Legend League battle logs
│   └── post_war_analysis.py       # Utilitário de pós-guerra
└── static/
    ├── painel.html                 # Painel principal
    ├── admin_login.html            # Login admin
    ├── admin_panel.html            # Painel admin
    ├── maintenance.html            # Página de manutenção
    ├── css/style.css               # Tema profissional v32
    ├── js/
    │   ├── scripts.js              # Lógica do painel principal
    │   └── admin.js                # Lógica do painel admin
    ├── images/                     # Favicons, badges, ícones
    └── audio/WARS.mp3             # Música de fundo
```

---

## Banco de Dados (MongoDB)

| Coleção | Descrição |
|---------|-----------|
| `war_history` | Dados completos de guerras com detalhes por membro |
| `donation_snapshots` | Snapshots horários de doações |
| `player_notes` | Notas dos jogadores com prioridade |
| `player_snapshots` | Snapshots de stats ao longo do tempo |
| `watchlist` | Jogadores observados com motivo e data |
| `smurf_evidence` | Evidências de detecção de smurfs |
| `clan_games_snapshot` | Snapshots de progresso dos Jogos do Clã |
| `system_config` | Configurações do bot |
| `panel_users` | Contas do painel web (roles: admin/viewer) |
| `users` | Vinculação Discord-CoC (player_tag + discord_id) |

---

## Changelog

Consulte [CHANGELOG.md](CHANGELOG.md) para o histórico completo de versões.

### Versão Atual: 32.2.3-GeniusLib-v5.3.0

- **v32.2.3** — Botão de changelog no admin panel com embed formatado para Discord
- **v32.2.2** — Assets servidos via GeniusLib, rota estática `/assets/`
- **v32.2.1** — Fix: tropas e feitiços ausentes no perfil
- **v32.2.0** — GeniusLib v5.3.0, bundle de assets local
- **v32.1.0** — Legend army cards redesign: cards estruturados, cópia para Clash
- **v32.0.0** — Redesign profissional: sidebar layout, Inter font, dark/light theme
- **v31.3.x** — Legend League completo: battlelog cog, web API, dashboard
- **v31.2.x** — GeniusLib v4.3.0, Dragon Duke, TH17/TH18, bugfixes
- **v31.1.0** — Security overhaul: XSS, CSRF, encrypted sessions
- **v31.0.0** — DiscoHook, post-war analysis, capital image
- **v30.x** — Migração GeniusLib v4.0.0, war preference, enhanced profiles

---

## Licença

MIT — Use, modifique e compartilhe livremente.

---

<p align="center">
  <sub>Feito com dedicação por +Constantine+ e a comunidade</sub><br>
  <sub>ClashGenius v32.2.3-GeniusLib-v5.3.0</sub>
</p>
