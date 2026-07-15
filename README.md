# ClashGenius ΓÇö O Genio das Guerras

![Versao](https://img.shields.io/badge/versao-32.1.0--GeniusLib--v5.1.2-182c61?style=flat-square&logo=python)
![Status](https://img.shields.io/badge/Status-Operacional-16a34a?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10%2B-2563eb?logo=python&style=flat-square)
![Hospedagem](https://img.shields.io/badge/hospedagem-render.com-0ea5e9?style=flat-square&logo=render)

> **ClashGenius** e um bot Discord + painel web para analise completa de cl├ús no Clash of Clans.
> Monitoramento em tempo real, inteligencia artificial preditiva, deteccao de smurfs, plano de rotacao CWL e um **painel web profissional** com sidebar, dark/light theme e analytics avancados.

---

## Destaques

| Modulo | Descricao |
|--------|-----------|
| **Painel Web** | Dashboard com sidebar, 10 abas (Clan, Destaques, Guerra, Pendencias, CWL, Jogos, Capital, Legend, Historico, Membros), dark/light theme |
| **Legend League** | Analise completa de battle logs: ataques, defesas, saques, exercitos com copia para o Clash, historico de progressao |
| **Inteligencia Artificial** | War Prediction (ensemble ML), War Advisor (algoritmo hungaro), Player Analytics (K-Means), Smurf Detection (IsolationForest + XGBoost), CWL Planner (K-Means + fairness) |
| **Painel Admin** | 9 abas: Geral, Diagnostico, Configuracoes, Watchlist, Radar Pericial, Analytics IA, Acoes, Base de Dados, DiscoHook |
| **Seguranca** | Auth com registro/aprovacao, CSRF, XSS sanitization, encrypted sessions, security headers, anti-DevTools |

---

## Painel Web

Acesse em: `https://SEU_DOMINIO.onrender.com/painel`

### Abas Publicas

| Aba | Descricao |
|-----|-----------|
| **Cl├ú** | Visao geral com badge, barra de ocupacao, cards de estatisticas, grafico de desempenho das ultimas guerras |
| **Destaques** | Top 3 doadores, heroes da ultima guerra (MVP), grafico de atividade |
| **Guerra** | Detalhes completos, previsao da IA, plano de ataque inteligente, eventos e escalacoes |
| **Pendencias** | Cartoes de alerta com gravidade (amarelo/vermelho) e tooltips |
| **CWL** | Status da liga, cronograma e plano de rotacao gerado por IA |
| **Jogos do Cl├ú** | Progresso da caravana, top farmers e parasitas (0 pontos) |
| **Capital** | Raio-x: ataques, saque, ausentes e incompletos |
| **Legend** | Dashboard de Legend League com seletor de jogador, 4 cards de resumo e 5 sub-abas |
| **Historico** | Log completo de guerras passadas com modal detalhado |
| **Membros** | Grid com fotos, status CWL, notas, prioridades e perfil individual com analise de IA |

### Sub-Abas da Legend

| Sub-aba | Conteudo |
|---------|----------|
| **Ataques** | Estatisticas de ataque (total, vitorias, derrotas, estrelas medias, destruicao media) |
| **Defesas** | Estatisticas defensivas (total, vitorias, derrotas, estrelas concedidas) |
| **Saques** | Resumo de saques (total, ouro, elixir, elixir negro, media por ataque) |
| **Exercitos** | Cards estruturados por composicao com desempenho, badges de tropas, herois com pets/equipamento, botao copiar para importar no Clash |
| **Historico** | Progressao de ligas ao longo das temporadas |

---

## Inteligencia Artificial

### War Prediction System v3
- **Algoritmo**: Ensemble de GradientBoosting + RandomForest
- **Features**: diferenca de estrelas, vantagem de TH, momentum, sinergia do cl├ú, pressao
- **Saida**: probabilidade de vitoria com nivel de confianca

### War Advisor
- **Algoritmo**: Algoritmo Hungaro (scipy `linear_sum_assignment`)
- **Estrategias**: mirror, dip, safe, cleanup, bonus, desperate
- **Fases**: prep, early, late (contagem regressiva de fase)
- **Forca do jogador**: TH + heroes + equipment + pets

### Player Analytics
- **Algoritmo**: K-Means (4 clusters) + RandomForest
- **Classificacao**: General, Especialista, Instavel, Risco
- **Saida**: probabilidade de atacar na proxima guerra

### Smurf Detection v3
- **Algoritmos**: IsolationForest + XGBoost + Distancia Cosseno + Fuzzy Logic + Calibracao Bayesiana
- **Sinais**: analise fonetica de nomes, vetores de tropas, sincronizacao de doacoes, sincronizacao de guerra, clustering de conquistas, assinatura forense (Mula Signature)
- **Telemetria**: feedback loop com rotulagem de falsos positivos

### CWL Planner
- **Algoritmo**: K-Means clustering + fairness scoring
- **Estrategias**: agressivo, balanceado, justo
- **Participacao**: peso baseado na historico de participacao

---

## Comandos Discord

### Slash Commands

| Comando | Descricao |
|---------|-----------|
| `/legend [tag]` | Battle log de Legend League |
| `/legend_historico [tag]` | Historico de ligas |
| `/legend_resumo [dias]` | Resumo da clan em Legend |
| `/legend_exercitos [tag]` | Composicoes de exercitos |
| `/perfil <jogador>` | Perfil completo (heroes, liga, hitrate, equipment, pets) |
| `/upgrades <jogador>` | Upgrade tracker (gold/elixir/DE/tempo para max) |
| `/comparar <j1> <j2>` | Comparacao lado a lado com diferencas |
| `/exportar <tipo> <formato>` | Exportar clan/membros em JSON ou CSV |
| `/plano_guerra` | Gerar plano de ataque IA |
| `/analise_guerra` | Analise de equilibrio de guerra |
| `/buscar_clas <nome> [limite]` | Buscar clans por nome |
| `/war_log [tag]` | Historico de guerras |
| `/verificar_conta <tag> <token>` | Verificar conta CoC via API token |
| `/legends [tag]` | Estatisticas de Legend League |
| `/painel_admin` | Gerar link seguro do painel admin |
| `/doacoes <periodo>` | Relatorio de doacoes (admin) |
| `/sync <escopo>` | Sincronizar comandos slash |
| `/smurfs_scan` | Scan manual de smurfs |
| `/relatorio_desempenho` | Relatorio de performance semanal |
| `/ping` | Latencia do bot |

### Comandos de Prefixo

| Comando | Descricao |
|---------|-----------|
| `!ping` | Latencia do bot |
| `!ver <tag>` | Perfil super detalhado com UI Discord (botoes, upgrade tracker, barras de progresso) |

---

## Painel Admin

Acesse em: `https://SEU_DOMINIO.onrender.com/admin`

### Sistema de Auth
- Registro com aprovacao pendente
- Roles: admin (acesso total) e viewer (somente leitura)
- Senhas com PBKDF2 (100k iteracoes + salt)
- Sessions com cookies criptografados (Fernet)
- CSRF token em todos os endpoints POST

### Abas

| Aba | Descricao |
|-----|-----------|
| **Geral** | Controle de manutencao, informacoes do sistema |
| **Diagnostico** | Status da API CoC, logs recentes, health stats |
| **Configuracoes** | Gerenciamento de canais, cargos e funcoes do Discord |
| **Watchlist** | Lista de observacao com filtro e remocao |
| **Radar Pericial** | Dossi completo de smurfs com julgamento (Absolver/Condenar) |
| **Analytics IA** | Classificacao de todos os membros por ML |
| **Acoes** | Cache, sincronizacao de comandos, anuncios |
| **Base de Dados** | Visualizador do MongoDB (guerras e notas) |
| **DiscoHook** | Editor visual de embeds do Discord com preview ao vivo |

---

## API REST

### Endpoints Publicos (16+)

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/api/clan` | GET | Dados do cl├ú |
| `/api/members` | GET | Lista completa de membros |
| `/api/current_war_details` | GET | Guerra atual com detalhes e previsao |
| `/api/war_log` | GET | Historico de guerras |
| `/api/cwl_info` | GET | Informacoes da CWL |
| `/api/highlights` | GET | Destaques (doadores, MVP, atividade) |
| `/api/capital` | GET | Dados de raid da Capital |
| `/api/clan_games` | GET | Progresso dos Jogos do Cl├ú |
| `/api/player_profile/{tag}` | GET | Perfil detalhado do jogador |
| `/api/player_upgrades/{tag}` | GET | Upgrade tracker do jogador |
| `/api/legend` | GET | Dados de Legend League |
| `/api/legend/history` | GET | Historico de Legend League |
| `/api/legend/clan` | GET | Resumo da clan em Legend |
| `/api/export/clan` | GET | Exportar dados do cl├ú |
| `/api/export/players` | GET | Exportar dados dos membros |
| `/api/compare/players` | GET | Comparar dois jogadores |
| `/api/compare/clans` | GET | Comparar dois clans |
| `/api/coc_status` | GET | Status da conexao com API CoC |
| `/api/status` | GET | Status do bot |

### Endpoints Admin (16+)

| Endpoint | Metodo | Descricao |
|----------|--------|-----------|
| `/api/admin/diagnostics` | GET | Diagnosticos do sistema |
| `/api/admin/settings` | GET/POST | Configuracoes do bot |
| `/api/admin/db_viewer` | GET | Visualizador do MongoDB |
| `/api/admin/actions` | POST | Acoes (cache, sync, anuncios) |
| `/api/admin/watchlist` | GET | Watchlist |
| `/api/admin/watchlist/add` | POST | Adicionar a watchlist |
| `/api/admin/watchlist/remove` | POST | Remover da watchlist |
| `/api/admin/smurf_dossier` | GET | Dossi de smurfs |
| `/api/admin/discord_data` | GET | Canais e cargos do Discord |
| `/api/admin/auth/login` | POST | Login |
| `/api/admin/auth/register` | POST | Registro |
| `/api/admin/auth/pending` | GET | Usuarios pendentes |
| `/api/admin/auth/approve/{user}` | POST | Aprovar usuario |
| `/api/admin/auth/reject/{user}` | POST | Rejeitar usuario |
| `/api/admin/auth/users` | GET | Listar usuarios |
| `/api/admin/auth/role` | POST | Alterar role |

---

## Tarefas Automaticas

| Tarefa | Frequencia | Descricao |
|--------|------------|-----------|
| War End Detection | 5 min | Detecta fim de guerra, armazena no DB |
| Donation Snapshots | 1 hora | Snapshots de doacoes para tendencias |
| API Status Check | 10 min | Ping na API CoC, rastreia status |
| CWL End Detection | 5 min | Detecta fim da temporada CWL |
| Battle Log Snapshot | 2 horas | Busca battle logs de todos os membros Legend |
| Daily Legend Report | 23:59 | Relatorio diario de Legend no Discord |
| Clan Games Snapshot | 6 horas | Progresso dos Jogos do Cl├ú |
| Capital Raid Snapshot | 6 horas | Dados de raid da Capital |
| Donation Report | 22:00 diario | Relatorio diario de doacoes |
| Donation Weekly | Segunda 22:00 | Relatorio semanal de doacoes |
| Performance Audit | Segunda 20:00 | Identifica leeches, desertores, zero-doacoes |
| Smurf Monitor | 15 min | Monitora mudancas no cl├ú para sinais de smurf |
| Smurf Retrain | 6 horas | Retreina modelo XGBoost com nova telemetria |

---

## Seguranca

| Recurso | Descricao |
|---------|-----------|
| **XSS Sanitization** | `escapeHtml()` em todo output dinamico |
| **CSRF Protection** | Token em todos os endpoints POST |
| **Encrypted Sessions** | Cookies criptografados com Fernet |
| **PBKDF2** | Hash de senhas com 100k iteracoes + salt |
| **Security Headers** | X-Content-Type-Options, X-Frame-Options, Referrer-Policy |
| **Anti-DevTools** | Bloqueio de right-click, F12, Ctrl+Shift+I/J/C |
| **Role-Based Access** | admin vs viewer no painel admin |
| **Cache TTL** | 45s para web API, 300s para API CoC |

---

## Tema Visual

### v32 ΓÇö Design Profissional
- Layout sidebar vertical (estilo ClashLens)
- Inter font (tipografia moderna)
- Tema dark/light com toggle
- CSS variables completo
- Tailwind CDN para utilitarios
- Cards e componentes com espacamento consistente

### Abas e Sub-abas
- Navegacao vertical na sidebar
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

### Dependencias

| Pacote | Versao | Finalidade |
|--------|--------|------------|
| `discord.py` | 2.5.2 | Framework do bot Discord |
| `geniuslib` | v5.1.2 | Wrapper async da API CoC (models, analytics, formatters, upgrade tracker, exporter, comparer, battlelog, middleware) |
| `python-dotenv` | latest | Variaveis de ambiente |
| `aiohttp` | latest | Servidor web + HTTP client |
| `pytz` | latest | Timezone |
| `motor` | latest | Driver async MongoDB |
| `aiohttp-session` | latest | Sessoes HTTP |
| `cryptography` | latest | Criptografia Fernet |
| `pandas` | latest | Manipulacao de dados para ML |
| `xgboost` | latest | Classificador para deteccao de smurfs |
| `numpy` | 1.26.4 | Computacao numerica |
| `scikit-learn` | 1.4.1.post1 | ML (KMeans, RandomForest, IsolationForest, GradientBoosting) |
| `thefuzz` | 0.22.1 | Fuzzy string matching |
| `python-Levenshtein` | 0.25.0 | Distancia Levenshtein rapida |
| `scipy` | latest | Algoritmo hungaro |
| `Pillow` | >=10.0.0 | Geracao de imagens de Capital |
| `psutil` | latest | Diagnosticos do sistema |

---

## Instalacao

```bash
# Clone
git clone https://github.com/AkumaHalls/ClashGenius.git
cd ClashGenius

# Ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/macOS
. venv\Scripts\activate    # Windows

# Dependencias
pip install -r requirements.txt
```

### Variaveis de Ambiente (.env)

```env
# Obrigatorio
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
Γö£ΓöÇΓöÇ clash.py                        # Bot + servidor web aiohttp
Γö£ΓöÇΓöÇ war_predictor.py                # Motor de previsao ML
Γö£ΓöÇΓöÇ formatting.py                   # Utilitarios de formatacao
Γö£ΓöÇΓöÇ simple_cache.py                 # Cache in-memory TTL com LRU
Γö£ΓöÇΓöÇ requirements.txt                # Dependencias
Γö£ΓöÇΓöÇ cogs/
Γöé   Γö£ΓöÇΓöÇ admin_cog.py               # Backend do admin
Γöé   Γö£ΓöÇΓöÇ web_api_cog.py             # API REST do painel web
Γöé   Γö£ΓöÇΓöÇ tasks_cog.py               # Tarefas em segundo plano
Γöé   Γö£ΓöÇΓöÇ events_cog.py              # Event listeners do Discord
Γöé   Γö£ΓöÇΓöÇ database_cog.py            # Persistencia MongoDB
Γöé   Γö£ΓöÇΓöÇ slash_cog.py               # 14 slash commands
Γöé   Γö£ΓöÇΓöÇ general_cog.py             # Comandos gerais (!ping)
Γöé   Γö£ΓöÇΓöÇ profile_cog.py             # Dados de perfil
Γöé   Γö£ΓöÇΓöÇ super_profile_cog.py       # Perfil super detalhado (!ver)
Γöé   Γö£ΓöÇΓöÇ war_predictor_cog.py       # Previsao de guerra (ML)
Γöé   Γö£ΓöÇΓöÇ war_advisor_cog.py         # Conselheiro de guerra IA
Γöé   Γö£ΓöÇΓöÇ cwl_planner_cog.py         # Planejador CWL
Γöé   Γö£ΓöÇΓöÇ clan_games_cog.py          # Rastreador de Jogos do Cl├ú
Γöé   Γö£ΓöÇΓöÇ capital_cog.py             # Monitoramento da Capital
Γöé   Γö£ΓöÇΓöÇ donation_cog.py            # Rastreamento de doacoes
Γöé   Γö£ΓöÇΓöÇ watchlist_cog.py           # Lista de observacao
Γöé   Γö£ΓöÇΓöÇ smurf_detection_cog.py     # Deteccao de smurfs (ML)
Γöé   Γö£ΓöÇΓöÇ performance_cog.py         # Auditoria de performance
Γöé   Γö£ΓöÇΓöÇ maintenance_cog.py         # Modo manutencao
Γöé   Γö£ΓöÇΓöÇ player_analytics_cog.py    # Analise de jogadores (ML)
Γöé   Γö£ΓöÇΓöÇ battlelog_cog.py           # Legend League battle logs
Γöé   ΓööΓöÇΓöÇ post_war_analysis.py       # Utilitario de pos-guerra
ΓööΓöÇΓöÇ static/
    Γö£ΓöÇΓöÇ painel.html                # Painel principal
    Γö£ΓöÇΓöÇ admin_login.html           # Login admin
    Γö£ΓöÇΓöÇ admin_panel.html           # Painel admin
    Γö£ΓöÇΓöÇ maintenance.html           # Pagina de manutencao
    Γö£ΓöÇΓöÇ css/style.css              # Tema profissional v32
    Γö£ΓöÇΓöÇ js/
    Γöé   Γö£ΓöÇΓöÇ scripts.js             # Logica do painel principal
    Γöé   ΓööΓöÇΓöÇ admin.js               # Logica do painel admin
    Γö£ΓöÇΓöÇ images/                    # Favicons, badges, icones
    ΓööΓöÇΓöÇ audio/WARS.mp3             # Musica de fundo
```

---

## Banco de Dados (MongoDB)

| Colecao | Descricao |
|---------|-----------|
| `war_history` | Dados completos de guerras com detalhes por membro |
| `donation_snapshots` | Snapshots horarios de doacoes |
| `player_notes` | Notas dos jogadores com prioridade |
| `player_snapshots` | Snapshots de stats ao longo do tempo |
| `watchlist` | Jogadores observados com motivo e data |
| `smurf_evidence` | Evidencias de deteccao de smurfs |
| `clan_games_snapshot` | Snapshots de progresso dos Jogos do Cl├ú |
| `system_config` | Configuracoes do bot |
| `panel_users` | Contas do painel web (roles: admin/viewer) |
| `users` | Vinculacao Discord-CoC (player_tag + discord_id) |

---

## Changelog

Consulte [CHANGELOG.md](CHANGELOG.md) para o historico completo de versoes.

### Versao Atual: 32.1.0-GeniusLib-v5.1.2

- **v32.1.0** ΓÇö Legend army cards redesign: cards estruturados, copia para Clash, stats de desempenho, agrupamento por performance
- **v32.0.0** ΓÇö Redesign profissional: sidebar layout, Inter font, dark/light theme, CSS variables
- **v31.3.x** ΓÇö Legend League completo: battlelog cog, web API, dashboard, GeniusLib v5.1.x
- **v31.2.x** ΓÇö GeniusLib v4.3.0, Dragon Duke, TH17/TH18, bugfixes
- **v31.1.0** ΓÇö Security overhaul: XSS, CSRF, encrypted sessions, security headers
- **v31.0.0** ΓÇö DiscoHook, post-war analysis, capital image
- **v30.x** ΓÇö Migracao GeniusLib v4.0.0, war preference, enhanced profiles

---

## Licenca

MIT ΓÇö Use, modifique e compartilhe livremente.

---

<p align="center">
  <sub>Feito com dedica├º├úo por +Constantine+ e a comunidade</sub><br>
  <sub>ClashGenius v32.1.0-GeniusLib-v5.1.2</sub>
</p>
