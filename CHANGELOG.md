# Changelog — ClashGenius

Todas as mudanças notáveis neste projeto. Formato baseado em [Keep a Changelog](https://keepachangelog.com/).
---

## [34.7.0] — 2026-08-17

### Corrigido
- **cogs/smurf_detection_cog.py** — Removido auto-treino com pseudo-labels (linhas 1111-1115) — training samples agora só são criados por Absolver/Condenar com julgamento humano real
- **MongoDB smurf_training** — Limpados 10 docs com `real_label=None` (lixo automático), restado apenas 1 doc com label real

### Alterado
- **cogs/smurf_detection_cog.py** — Adicionado min-evidence: pares precisam de pelo menos 1 eixo forte (ou behavior_score >= 15) pra aparecer no radar
- **cogs/smurf_detection_cog.py** — Risk labels agora são granulares: "Risco Extremo" (ML >= 85%), "Alta Suspeita" (ML >= 60%), "Em Observação" (ML >= 30%), "Suspeita Moderada (Cold Start)" (>= 50% com 3+ eixos), "Em Observação (Cold Start)" (>= 40% com 2+ eixos), "Baixa Confiança" (resto)
- **cogs/smurf_detection_cog.py** — Retornado `strong_axes` e `model_status` no resultado do dossier
- **static/js/admin.js** — Loading spinner "Analisando patrões comportamentais..." enquanto carrega radar
- **static/js/admin.js** — Badge ML/HEURÍSTICA no header de cada dossiê
- **static/js/admin.js** — Info de eixos fortes e modelo abaixo do score
- **static/js/admin.js** — Warning "Confiança Insuficiente" quando cold start com < 3 eixos
- **config.py** — Versão bumpada de 34.6.0 para 34.7.0

### Adicionado
- **cogs/smurf_detection_cog.py** — Novo método `get_training_status()` que retorna progresso do treino XGBoost (labels reais, amostras, status do modelo)
- **cogs/admin_cog.py** — Método delegador `get_smurf_training_status()` para expor status ao web server
- **web/admin_routes.py** — Nova rota GET `/smurf_training_status` no painel admin
- **static/admin_panel.html** — Container `<div id="radar-training-status">` na seção Radar Pericial
- **static/js/admin.js** — Função `loadTrainingStatus()` que renderiza barras de progresso do XGBoost (labels reais X/5, amostras X/20, status cold_start/ready/trained); chamada automaticamente ao abrir Radar Pericial e após Absolver/Condenar

### Alterado
- **config.py** — Versão bumpada de 34.5.6 para 34.6.0

---

## [34.5.6] — 2026-08-17

### Adicionado
- **scripts/download_assets.py** — Script que baixa assets da GeniusLib (385MB) do GitHub Releases quando não encontrados no disco
- **web/server.py** — Auto-healing: se assets não existem, baixa automaticamente do GitHub antes de servir

### Alterado
- **config.py** — Versão bumpada de 34.5.5 para 34.5.6

---

## [34.5.5] — 2026-08-17

### Alterado
- **requirements.txt** — geniuslib agora é instalado via PyPI (`>=5.5.4`) em vez de git+https, com GitHub Action de publish automático
- **config.py** — Versão bumpada de 34.5.4 para 34.5.5

---

## [34.5.4] — 2026-08-17

### Corrigido
- **requirements.txt** — GeniusLib agora inclui `translations.json` e `assets/` no package-data (v5.5.2), corrigindo `FileNotFoundError` no `_load_static()` durante login CoC no Render

### Alterado
- **config.py** — Versão bumpada de 34.5.3 para 34.5.4 (GeniusLib 5.5.2)

---

## [34.5.3] — 2026-08-17

### Corrigido
- **smurf_detection_cog.py** — Removido `NameError: 'player_info' is not defined` na linha 582 de `_prepare_clan_baselines` (referência duplicada obsoleta)

### Alterado
- **smurf_detection_cog.py** — Removido gate de similaridade de nomes (`MIN_FUZZY_RATIO >= 78`) no loop principal do `/smurfs` — todos os pares agora passam pelo ML, permitindo detecção baseada nos 9 eixos analíticos mesmo com nomes diferentes
- **smurf_detection_cog.py** — Threshold de telemetry no DB baixado de `score > 10` para `score > 3`, permitindo incluir pares com evidência mínima no scan
- **smurf_detection_cog.py** — Gates de evidência relaxados: removido bloqueio `evidence_count == 1 AND bayesian_conf < 60 AND behavior_score < 40`, e gate principal baixado de `evidence_count < 2 AND behavior_score < 15` para `evidence_count < 1 AND behavior_score < 10`
- **smurf_detection_cog.py** — Cap bayesiano para eixos fracos subiu de 79% para 84%
- **smurf_detection_cog.py** — `hit_count` no radar de doações baixado de 2 para 1, permitindo logging desde a primeira observação
- **smurf_detection_cog.py** — Cooldown de telemetry reduzido de 24h para 4h, acelerando acumulação de score
- **smurf_detection_cog.py** — Prior bayesiano aumentado de 2% para 5%, reduzindo viância para "clean" no cold start
- **config.py** — Versão bumpada de 34.5.2 para 34.5.3

---

## [34.5.2] — 2026-08-17

### Corrigido
- **smurf_detection_cog.py** — `_last_clan_players` agora armazena objetos `Player` completos em vez de dicts `{'name', 'tag'}`, corrigindo `AttributeError: 'dict' object has no attribute 'town_hall'` no `/smurfs`
- **smurf_detection_cog.py** — `_compute_name_similarity_baseline` aceita tanto objetos Player quanto dicts

### Alterado
- **Versão:** `34.5.2`

---

## [34.5.1] — 2026-08-17

### Corrigido
- **web/server.py** — Health check antecipado inicia porta 10000 imediatamente no setup_hook (antes de carregar cogs), evitando que Render envie SIGTERM por timeout de startup
- **web/server.py** — Rota `/` agora retorna 200 JSON em vez de 302 redirect, garantindo que health check do Render passe
- **clash.py** `close()` — Ordem de shutdown corrigida: `super().close()` (descarrega cogs) executado ANTES de fechar MongoDB, eliminando erro `Cannot use MongoClient after close` no CWLPlanner
- **clash.py** `close()` — Early web runner também é limpo durante shutdown

### Alterado
- **Versão:** `34.5.1`

---

## [34.5.0] — 2026-08-17

### Corrigido
- **cogs/war_attack_analysis.py** — `_HISTORY_CACHE` global agora tem TTL de 1h e max de 500 entradas com evicção periódica, impedindo crescimento indefinido
- **cogs/player_analytics_cog.py** — Adicionado `cog_unload()` que libera DataFrame, StandardScaler, KMeans e RandomForest da memória ao descarregar o cog
- **cogs/smurf_detection_cog.py** — Três caches sem limite agora têm max de 1000/2000 entradas com timestamps e evicção. Scores do IsolationForest reutilizados do cache. `_last_clan_players` limitado a 100
- **clash.py** — `clan_cache` limitado a 50 entradas, `web_api_cache` limitado a 200 com LRU, `processed_war_ids` limitado a 2000 com trim periódico
- **cogs/events_cog.py** — Views com `timeout=600` em vez de `None`. `cog_unload()` cancela os 7 updater tasks do EventsClient. Task de login armazenada para cleanup
- **web/middleware.py** — `RateLimiter` limpa chaves stale a cada 5min (chaves >10min sem uso removidas)
- **web/auth_routes.py** — Queries MongoDB agora usam `.limit()` e `cursor.close()` para evitar carregamento ilimitado
- **cogs/tasks_cog.py** — `.to_list(length=500)` em vez de `None` em agregações MongoDB. `processed_war_ids` limitado ao adicionar guerras
- **web/routes.py** — `web_api_cache` respeita `_WEB_API_CACHE_MAXSIZE` com LRU. Task de reconexão cancela a anterior
- **web/admin_routes.py** — HTML do painel admin cacheado em memória (lido do disco 1x)

### Alterado
- **config.py** — Versão bumpada de 34.4.1 para 34.5.0
- **static/sw.js** — Cache versionado para v34.5.0

---

## [34.4.1] — 2026-08-02

### Corrigido
- **static/css/style.css** — Aba Membros: as seções ficavam **lado a lado** porque eram filhas do grid `#membersGrid`; `.members-section` agora ocupa a largura toda (`grid-column: 1 / -1`), devolvendo aos cards o tamanho original
- **static/css/style.css** — Separadores agora **centralizados** (max-width 720px, `margin: 0 auto`, conteúdo centralizado com `justify-content: center`); contador deixou de ser jogado para a direita
- **static/js/scripts.js** — Título do separador de destaque renomeado de "Fixos & Admins" para **"Destaques & Admins"**
- **static/sw.js** — Cache versionado para v34.4.1
- **config.py** — Versão bumpada de 34.4.0 para 34.4.1

## [34.4.0] — 2026-08-02

### Adicionado
- **Aba Membros (Web)** — Nova área de **destaque no topo**: membros fixos (CWL `priority`) e marcados como ADMIN (borda) são agrupados sob uma **faixa separadora** em destaque (gradiente dourado→roxo com brilho e shimmer), separados dos demais membros por uma segunda faixa "Demais Membros"

### Alterado
- **static/js/scripts.js** — `populateMembersList` divide a lista em `featured`/`regular`, extrai o card para o helper `buildMemberCard` e renderiza duas seções com faixas separadoras (`.members-separator`, `.members-separator-featured`) e contadores; `applyMemberFilters` agora filtra por seção, esconde a seção vazia e atualiza o contador visível
- **static/css/style.css** — Novos estilos `.members-section`, `.members-separator` (+ variante `-featured` com shimmer/brilho) e `.members-separator-count` (pill), com media query ≤480px
- **static/sw.js** — Cache versionado para v34.4.0
- **config.py** — Versão bumpada de 34.3.0 para 34.4.0

## [34.3.0] — 2026-08-02

### Adicionado
- **Perfil do membro (Web)** — Novo card **Entrada**: data de entrada do jogador no clã, rastreada automaticamente via eventos do `EventsClient` (coleção `clan_membership` no MongoDB). Para membros já presentes antes da feature, a data é **estimada pela 1ª guerra registrada** no `war_history` (marcada com `*` e tooltip). Caso não haja histórico, mostra "Indeterminado"
- **Perfil do membro (Web)** — Novo card **Tempo de Casa**: quanto tempo o membro está na passagem atual pelo clã (reentrada zera a contagem), formatado em anos/meses/dias
- **Perfil do membro (Web)** — Nova seção **Carteira de Combate**: últimas 15 guerras do membro com oponente, data, resultado (Vitória/Derrota/Empate), estrelas, destruição e ataques perdidos
- **Perfil do membro (Web)** — **Percentil no clã**: posição do membro em troféus e doações (ex.: "Top 12% em troféus (5º)") calculada a partir do `/api/members`
- **cogs/tasks_cog.py** — Nova task `reconcile_membership_task` (a cada 6h): cria registros `first_seen` para membros sem dado, faz backfill pela 1ª guerra e marca `left_at` para quem saiu (rede de segurança se o bot ficar offline e perder eventos)

### Alterado
- **cogs/database_cog.py** — Novos helpers `record_member_join`, `record_member_leave` e `load_membership_records` para a coleção `clan_membership`
- **cogs/events_cog.py** — `handle_clan_member_join`/`handle_clan_member_leave` agora gravam entrada/saída no banco e invalidam o cache de `/api/members`
- **cogs/profile_cog.py** — `fetch_player_profile_data` passa a retornar `war_history` (carteira de combate) além do hitrate
- **cogs/web_api_cog.py** — `/api/members` agora inclui `joined_at`, `membership_source`, `rank_donations`, `rank_trophies`, `pct_donations` e `pct_trophies`
- **static/js/scripts.js** — Helper `formatTenure` + renderização dos novos cards, seção Carteira de Combate e percentil no modal de perfil
- **static/css/style.css** — Estilos de `.profile-percentil`, `.war-history-*` (lista de guerras com badges de resultado) e responsividade móvel
- **static/sw.js** — Cache versionado para v34.3.0
- **config.py** — Versão bumpada de 34.2.1 para 34.3.0

## [34.2.1] — 2026-07-31

### Corrigido
- **static/css/style.css** — Guerra: grid do Plano de Ataque IA (`.advisor-grid`, coluna mínima de 320px) estourada no celular tinha o lado direito cortado pelo `overflow-x:hidden`; agora vira 1 coluna ocupando a tela toda em ≤768px
- **static/css/style.css** — Ataques Pendentes: `.player-card-grid` (mínimo 280px) tinha folga zero no celular; vira 1 coluna em ≤768px
- **static/css/style.css** — Tabs da Guerra voltavam a empilhar em coluna vertical gigante (regra antiga ≤768px); agora ficam em linha com quebra
- **static/css/style.css** — Membros: `.member-card-stats` (2 colunas fixas) vira 1 coluna em ≤480px; `.cwl-status-selector` embrulha
- **static/css/style.css** — CWL/Jogos/Capital: overlay "fechado" (.locked-content) com `padding: 40px 50px` + 85% deixava uma coluna de ~99px de texto no celular; agora compacto em ≤480px (com fix correspondente em `painel.html`)
- **static/css/style.css** — Ranked: nome do jogador (`.ranked-member-name`, min 120px) em linha própria no celular; banner de guerra encerrada vira coluna; barras do resumo de guerras e gráfico de atividade mais compactos
- **static/sw.js** — Cache versionado para v34.2.1 (força atualização do CSS novo nos dispositivos com o app instalado)
- **config.py** — Versão bumpada de 34.2.0 para 34.2.1

## [34.2.0] — 2026-07-31

### Adicionado
- **PWA** — Site agora é instalável como aplicativo: novo `static/site.webmanifest` (tema dark `#0a0a0f`, `start_url /painel`, display standalone, ícones `any` + `maskable` 192/512) com rota dedicada `/site.webmanifest` no servidor com MIME correto
- **PWA** — Novo Service Worker `static/sw.js` registrado em todas as páginas: precache versionado, network-first para navegação/API com fallback, cache-first para estáticos e limpeza automática de caches antigos; rota `/sw.js` serve com `Service-Worker-Allowed: /`
- **PWA** — Nova página `static/offline.html` (rota `/offline`): visual dark consistente, últimos dados do clã vindos do `localStorage` e botão "Tentar novamente"
- **PWA** — Novo `static/js/pwa-install.js` (carregado em painel e admin): botão flutuante "📲 Instalar App" no `beforeinstallprompt`, modal com instruções para iPhone/iPad e ocultação automática quando instalado
- **PWA** — Metas PWA em todas as 4 páginas (theme-color, `mobile-web-app-capable`, apple equivalents) e ícones `maskable-192x192.png` / `maskable-512x512.png` gerados

### Alterado
- **static/css/style.css** — Menu hambúrguer com drawer responsivo para o painel público (`.nav-toggle` + `.main-nav` colapsado em ≤768px), botão compartilhado com o admin
- **static/css/style.css** — Mobile: `.legend-player-selector` quebra linha e campos ocupam 100%, `.note-text` mostra o texto completo em vez de ellipsis, `.member-cwl-status` embrulha, `.clan-pulse-grid` vira 1 coluna em ≤600px, `.modal-content` vira tela cheia em ≤480px, `overflow-x` protegido no body, safe-area (iPhone) em botões fixos e footer
- **static/js/utils.js** — Lógica do drawer hambúrguer (abrir/fechar, fechar ao clicar em link ou fora, reset em resize) + registro central do Service Worker
- **static/admin_panel.html** — Layout admin responsivo em ≤768px (nav vira drawer, `.form-grid`, watchlist e campos dh em 1 coluna, `#analytics-table` minimizada com scroll horizontal, tabelas de usuários e pendentes roláveis, header com wrap)
- **static/admin_login.html** — `overflow:hidden` corrigido em telas pequenas (formulário acessível com teclado), layout `100dvh`
- **static/maintenance.html** — Página de manutenção agora rola e centraliza corretamente em telas pequenas
- **static/painel.html** — Botão hambúrguer adicionado ao cabeçalho; manifest apontando para `/site.webmanifest`
- **web/server.py** — Rotas PWA (`/site.webmanifest`, `/sw.js`, `/offline`, `/offline.html`) com headers MIME/cache corretos (contorna MIME incorreto do Windows para `.webmanifest`)
- **config.py** — Versão bumpada de 34.1.0 para 34.2.0

## [34.1.0] — 2026-07-31

### Adicionado
- **cogs/war_attack_analysis.py** — Novo motor de análise tática em tempo real para o evento de ataque de guerra: explica por que um ataque foi ruim (DIP falho, destruição baixa, duração acima da média do clã, limpeza que não melhorou estrelas, alvo fora do posto, desvio do padrão pessoal via histórico do Mongo) e gera sugestões de melhoria
- **cogs/war_attack_analysis.py** — Selo de severidade nos ataques: 🔴 Crítico (0⭐ ou DIP falho), 🟠 Ruim (1⭐), 🔥 Excelente (3⭐), 🟢 Boa Defesa (defesa que segura), 📉 Defesa Caída
- **cogs/war_attack_analysis.py** — Análise de defesa recebida: destaca defesas sólidas (inclusive sobrevivência a múltiplos ataques) e aponta vulnerabilidades quando a base cai (inclusive para CV inferior)
- **cogs/war_attack_analysis.py** — Histórico do jogador consultado em `war_history` com cache em memória (média de estrelas, taxa de 3⭐, ataques perdidos nas últimas guerras)
- **cogs/war_attack_analysis.py** — Contexto ampliado: duração, fresco/limpeza, média do clã e placar atual da guerra em tempo real

### Alterado
- **cogs/events_cog.py** — `on_war_attack` usa o analisador nos 3 fluxos: alerta de ataque ruim ganha campos "⚡ Por que foi ruim" e "🎯 Sugestões de Melhoria"; ataques bons ganham "💪 Destaques"; defesa recebida ganha "🛡️ Análise". Fallback para o formato antigo se o analisador falhar
- **config.py** — Versão bumpada de 34.0.1 para 34.1.0

## [34.0.1] — 2026-07-31

### Corrigido
- **cogs/admin_cog.py** — `send_changelog` enviava mais do que a última versão: o parse pegava o texto inteiro após o primeiro `---`, incluindo os blocos `### ` de TODAS as versões antigas. Agora extrai apenas o primeiro bloco `## [versão]` do CHANGELOG.md

### Alterado
- **config.py** — Versão bumpada de 34.0.0 para 34.0.1

## [34.0.0] — 2026-07-31

### Adicionado
- **cogs/post_war_analysis.py** — Análise pós-guerra agora dá nome aos bois: novas seções "🌟 Melhores Guerreiros (nomeados)", "🛡️ Muralha de Ferro — Defesas Sólidas", "📉 Alvos de Atenção (nomeados)", "🚩 Ataques Não Realizados" e "💀 Ataques de 0 Estrelas", todas citando os nomes dos jogadores
- **cogs/post_war_analysis.py** — Insights táticos agora citam nomes em DIPs falhos, limpezas desperdiçadas e ataques zerados
- **cogs/post_war_analysis.py** — Adicionado insight de distribuição de estrelas (⭐x3/⭐x2/⭐x1/zerados) e destaque de ponta de lança no parecer do motor
- **cogs/post_war_analysis.py** — `create_post_war_analysis_embed` agora retorna `List[discord.Embed]`: mensagens longas são cortadas automaticamente em múltiplos embeds respeitando os limites do Discord (1024 chars por campo, 25 campos por embed, ~6000 chars por embed)
- **cogs/tasks_cog.py** — Novo helper `_send_log_embeds` que envia até 10 embeds por mensagem; análise pós-guerra usa ele para exibir a mensagem completa

### Alterado
- **cogs/post_war_analysis.py** — Cabeçalho do veredito agora inclui destruição (em empates), tamanho da guerra e eficiência de estrelas
- **cogs/post_war_analysis.py** — Footer do motor analítico atualizado para v6.0
- **config.py** — Versão bumpada de 33.5.0 para 34.0.0

## [33.5.0] — 2026-07-30

### Alterado
- **cogs/capital_cog.py** — Raid results image: agora usa o mapa real Capital Peak (DMap_Capital_Peak.jpg) como fundo com vinheta escura (vignette), substituindo o gradiente sólido anterior — assets do próprio jogo como background, conforme solicitado
- **cogs/capital_cog.py** — CWL results image: agora usa a War Arena Scenery como fundo com vinheta escura
- **cogs/capital_cog.py** — URL do asset bg corrigida (Capital_Peak_Scenery.png estava 404, migrado para DMap_Capital_Peak.jpg)
- **cogs/capital_cog.py** — Adicionado asset cwl_bg (War Arena Scenery) e respectivo fetch em _process_and_send_cwl
- **config.py** — Versão bumpada de 33.4.0 para 33.5.0

## [33.4.0] — 2026-07-30

### Alterado
- **cogs/capital_cog.py** — Redesign completo da imagem de Resultados do Fim de Semana da Capital (generate_game_style_image): layout 1100x800, gradiente escuro com acentos diagonais, cards com barra de cor superior, painéis de análise de desempenho e top atacantes lado a lado, log de clãs atacados e defesas, tipografia refinada
- **cogs/capital_cog.py** — Redesign completo da imagem de resumo CWL (generate_cwl_report_image) no mesmo estilo moderno do raid
- **cogs/capital_cog.py** — Adicionados métodos auxiliares _get_league_color() e _draw_diagonal_accents() para suporte visual
- **config.py** — Versão bumpada de 33.3.3 para 33.4.0

## [33.3.3] — 2026-07-28

### Corrigido
- web/auth.py - `get_db()` retornava `None` quando MongoDB indisponível, mas callers verificavam `isinstance(db, web.Response)` — causava crash `AttributeError` em TODOS os handlers; agora retorna tupla `(db, err)` com resposta 503 adequada
- web/auth.py - `check_password()` usava `==` para comparar hashes — vulnerável a timing attacks; migrado para `secrets.compare_digest()`
- web/auth.py - PBKDF2 iterações aumentadas de 100.000 para 600.000 (OWASP 2023)
- web/middleware.py - CSRF token comparado com `!=` (não timing-safe); migrado para `secrets.compare_digest()`
- web/admin_routes.py - Login admin usava `==` para comparar senha; migrado para `secrets.compare_digest()`
- web/routes.py - POST `/api/notes/{player_tag}` não requeria autenticação — qualquer usuário anônimo podia sobrescrever notas
- web/routes.py - POST `/api/cwl/player_status/{player_tag}` não requeria autenticação — qualquer usuário anônimo podia mudar status CWL
- web/routes.py - POST `/api/admin_border/{player_tag}` tinha auth check quebrado — usuários sem role passavam direto; agora retorna 401
- web/server.py - `FERNET_KEY` gerava chave nova silenciosamente quando não configurada, invalidando todas as sessões; agora é erro fatal
- web/auth_routes.py - Login retornava mensagens diferentes para "user not found" vs "wrong password" — permitia enumeração de usuários; agora retorna "Credenciais inválidas" em ambos
- web/routes.py - Parâmetro `dias` em `/api/legend/clan` não validado — causava ValueError 500 com input não-numérico
- web/server.py - Variável `PORT` não validada — causava ValueError com valor não-numérico
- web/admin_routes.py - `guild_id` era refletido sem encoding no redirect URL — potencial header injection
- web/routes.py - `asyncio.create_task()` sem armazenar referência — task podia ser garbage collected antes de completar
- clash.py - `loop.create_task()` para `coc_login_task` e `setup_web_server` sem armazenar referência
- static/images/site.webmanifest - Icon paths estavam errados (`/android-chrome-*.png` em vez de `/static/images/android-chrome-*.png`)
- web/routes.py - Todos os cogs tinham null-check ausente (profile_cog, cwl_cog, admin_cog, web_api_cog, maintenance_cog)
- web/middleware.py - `security_headers_middleware` não aplicava headers em responses de erro (exceptions não tratadas)
- web/auth_routes.py - Route regex `{username:.*}` aceitava qualquer string; restrito para `{username:[a-z0-9_]+}`
- requirements.txt - Dependências restauradas: pandas, Pillow, xgboost, scipy (usadas por smurf_detection_cog, capital_cog, war_advisor_cog)

### Adicionado
- web/middleware.py - Rate limiting global: 10 req/min para login/registro, 120/min para APIs, 200/min para estáticos
- web/server.py - Endpoint `/health` para monitoramento
- web/server.py - `SameSite=Lax` nos cookies de sessão
- web/middleware.py - CSP atualizado para whitelistar domínio do tracker (akuma-labs.duckdns.org)
- clash.py - Graceful shutdown com signal handlers (SIGINT/SIGTERM)

### Removido
- web/auth.py - Função `require_admin()` (dead code — definida mas nunca chamada)
- temp_check_emoji.ps1 - Script temporário de diagnóstico
- temp_fix_changelog.ps1 - Script temporário de reparo
- temp_fix_encoding.ps1 - Script temporário de encoding
- temp_update_changelog.ps1 - Script temporário de changelog
- requirements.txt - Dependência não utilizada removida: psutil

### Padronizado
- web/routes.py - Formato de erro padronizado para `{"status": "error", "message": "..."}` em todos os endpoints
- web/admin_routes.py - Null checks adicionados para todos os cogs (admin, maintenance, web_api)

---

## [33.3.2] — 2026-07-27

### Corrigido
- cogs/smurf_detection_cog.py - _pair_isolation_forest nunca treinava: check de tamanho movido para **depois** do loop de construção dos pair_vectors
- cogs/smurf_detection_cog.py - Hero equipment fingerprint retornava zeros para TH baixo: agora normaliza apenas slots desbloqueados por TH (TH8=1 slot...TH15=8 slots)
- cogs/smurf_detection_cog.py - token_set_ratio artificialmente dividido por 2: removido // 2, usa max(ratio, token_ratio) direto
- cogs/smurf_detection_cog.py - WAR_SYNC_SECONDS = 30s muito agressivo (falso positivo em guerras legítimas): aumentado para **90s**
- cogs/smurf_detection_cog.py - _donation_pair_history vazava memória (dict sem TTL): adicionado _donation_pair_history_ttl + limpeza 24h no 
egenerative_ai_task
- cogs/smurf_detection_cog.py - Isolation Forest mal calibrado (score_samples heurístico): migrou para decision_function + percentil de contaminação calibrado
- cogs/smurf_detection_cog.py - Mula signature disparava em TH12+: agora só em **TH14+** (onde equipamentos/meta de doação existem)

### Alterado
- cogs/smurf_detection_cog.py - Adicionados caches _if_score_cache, _pair_if_score_cache para evitar recomputação

---

## [33.3.1] — 2026-07-19

### Corrigido
- cogs/tournament_cog.py - end_check_task usava hora UTC mas verificava horário BRT (08:00 UTC = 05:00 BRT), resumo nunca era enviado; agora usa datetime.now(America/Sao_Paulo)
- cogs/activity_report_cog.py - get_donation_activity usava filtro $gte no cutoff que podia retornar o mesmo snapshot para latest e old, mostrando 0 doações; agora usa $lt para buscar snapshot anterior
- cogs/tournament_cog.py - Formato de week number %W gerava semana 00 no início do ano; alterado para %V (ISO week)
- web/routes.py - Endpoint /api/tournament retornava título/descrição de Embed em vez de dados estruturados; agora usa get_tournament_data_for_web() retornando promotions/demotions/unchanged

### Adicionado
- cogs/tournament_cog.py - Método get_tournament_data_for_web() retornando dict estruturado para a API web

---

## [33.3.0] — 2026-07-19

### Adicionado
- cogs/activity_report_cog.py - RelatÃ³rio de atividade diÃ¡rio (08:00 BRT) e semanal (domingo 20:00 BRT) com status de cada membro
- cogs/tournament_cog.py - Resumo de fim de torneio com promoÃ§Ãµes/rebaixamentos de liga
- Comando /atividade - Gera relatÃ³rio de atividade manualmente
- Comando /torneio - Gera resumo do torneio atual
- Comando /torneio_snapshot - Tira snapshot manual do torneio
- Nova aba "Ranked" no painel web com sub-tabs: Atividade, Torneio, Legend League, EstatÃ­sticas
- Endpoints /api/tournament para dados do torneio
- CSS para seÃ§Ã£o Ranked com estilos de member list

### Alterado
- cogs/events_cog.py - NotificaÃ§Ã£o de mudanÃ§a de liga agora mostra PROMOÃ‡ÃƒO/REBAIXAMENTO com cores e thumbnails
- static/painel.html - Aba "Legend" renomeada para "Ranked" com sub-tabs
- static/js/scripts.js - Adicionadas funÃ§Ãµes populateRankedActivity e populateRankedTournament
- static/css/style.css - Adicionados estilos para seÃ§Ã£o Ranked
- config.py - Adicionados ACTIVITY_REPORT_CHANNEL_ID e TOURNAMENT_SUMMARY_CHANNEL_ID
- .env.example - Adicionadas novas variÃ¡veis de ambiente
- clash.py - Registrados novos cogs activity_report_cog e tournament_cog

### Removido
- cogs/events_cog.py - NotificaÃ§Ã£o obsoleta de "ganhou/perdeu X tropheus" (sistema de ligas antigo)
- cogs/events_cog.py - Listener on_clan_member_trophies_change

---

## [33.2.0] — 2026-07-19

### Alterado
- static/css/style.css - adicionadas classes .star-icon, .icon-sm, .icon-inline, .war-ended-icon para substituir emojis por icones de jogo
- static/js/scripts.js - refatorado createStarString() para retornar HTML com img ao inves de texto com emojis; adicionada helper icon() com 15+ icones do jogo; substituidos ~150+ emojis em templates dinamicos
- static/painel.html - substituidos ~50+ emojis estaticos por imagens de icones do jogo
- static/admin_panel.html - substituidos ~80+ emojis por imagens de icones, SVGs ou texto
- static/admin_login.html - substituidos ~15 emojis por texto simples
- static/js/admin.js - substituidos 33 emojis por imagens de icones, SVGs ou texto
- static/maintenance.html - substituidos 2 emojis por SVGs de engrenagem

### Removido
- Todos os emojis do painel web (HTML, JS, CSS) - substituidos por imagens de icones do jogo servidas via /assets/
- Emojis do Discord bot NAO foram alterados (fora do escopo)

---

## [33.1.0] — 2026-07-19

### Adicionado
- **MAINTENANCE_ROLE_ID** em config.py — cargo de manutenção agora é configurável via env var e pelo painel admin
- **admin_cog.py** - maintenance_role_id adicionado ao get_settings/update_settings
- **admin_panel.html** - campo "Cargo: Manutenção" no form de configurações (dropdown de cargos)
- **.env.example** - template com todas as variáveis de ambiente documentadas
- **static/js/utils.js** - módulo compartilhado com escapeHtml para eliminar duplicação entre scripts.js e admin.js

### Corrigido
- **web/auth.py get_db()** retornava web.Response em caso de erro — callers tratavam como objeto DB e causavam AttributeError. Agora retorna None
- **cogs/tasks_cog.py** try/except quebrado com segundo except inacessível. Simplificado para um único except Exception
- **static/js/scripts.js:662** avg_duration exibia clan_avg_stars (bug de copy-paste). Corrigido para clan_avg_duration
- **web/auth.py check_password** engolia silenciosamente qualquer exceção. Agora loga warnings para erros de formato de hash
- **web/middleware.py** CSP incluía 'unsafe-eval' desnecessário (nenhum eval() no JS). Removido
- **cogs/war_predictor_cog.py** duplicava toda a lógica ML do war_predictor.py (~375 linhas). Reescrito para importar do módulo standalone
- **simple_cache.py** log de eviction contava itens já deletados incorretamente. Log agora é emitido antes da remoção e conta corretamente
- **admin.js** 4 catch blocks vazios (watchlist add, settings save, action execute, announcement send) agora mostram feedback de erro ao usuário
- **config.py** CHANGELOG_CHANNEL_ID tinha default hardcoded "1526649554240536687" que silenciava erros de configuração. Default agora é "0"
- **cogs/__init__.py** docstring dizia "modules" em vez de "cogs"
- **admin.js** execCommand('copy') deprecado substituído por navigator.clipboard.writeText (Clipboard API moderna)
- **admin.js** fetchRadarInactivityData executava em todas as páginas. Agora só executa no painel admin

### Removido
- **player_notes.json** arquivo morto vazio — notas são armazenadas no MongoDB (player_notes collection)
- **escapeHtml duplicado** entre scripts.js e admin.js — extraído para static/js/utils.js
- **código duplicado war_predictor** — ~375 linhas de classes ML removidas do cog, importadas do módulo standalone
- **MAINTENANCE_ROLE_ID hardcoded** em maintenance_cog.py — agora usa config via bot.maintenance_role_id

### Alterado
- Versao do bot: 33.1.0-GeniusLib-v5.3.0
- Badge do README atualizada para v33.1.0

---

## [33.0.0] — 2026-07-19

### Adicionado
- **config.py** - modulo centralizado de constantes (env vars, canais, roles, cache, versao)
- **web/ package** - decomposicao do monolith clash.py em modulos:
  - web/auth.py - helpers de autenticacao (get_db, hash_password, check_password)
  - web/middleware.py - security headers (com CSP), admin auth, CSRF
  - web/auth_routes.py - handlers de login, registro, aprovacao, roles
  - web/routes.py - 25+ endpoints publicos da API
  - web/admin_routes.py - admin API + paginas HTML admin
  - web/server.py - setup do aiohttp app, sessions, static files
- **Content-Security-Policy** header em todas as respostas web

### Removido
- **MAX_WAR_HISTORY** - limite artificial de 500 guerras removido de todos os modulos. Historico agora e ilimitado
- **Senha admin hardcoded "admin123"** - ADMIN_PASSWORD agora e obrigatorio via variavel de ambiente
- **Fallback getattr(bot, 'mongo')** - codigo morto removido (8 ocorrencias), substituido por helper get_db()
- **lightgbm** removido do requirements.txt (nao era importado)

### Corrigido
- **time.sleep(3600) sincrono** bloqueando event loop para await asyncio.sleep(3600)
- **clash.py monolith** (930 linhas) decomposto em 6 modulos (~295 linhas restantes, -68%)

### Alterado
- Versao do bot: 33.0.0-GeniusLib-v5.3.0
- Badge do README atualizada para v33.0.0

---


## [32.3.1] — 2026-07-17

### Corrigido
- **Admin Border visual mais chamativo** — borda rainbow agora usa `background-clip: border-box` com gradiente visível na borda + glow neon forte, substituindo o pseudo-elemento `::before` que ficava atrás do card
- Admin Border tem prioridade sobre o golden VIP quando ambas as classes estão presentes
- Ribbon admin agora tem animação de glow pulsante

### Alterado
- Versão do bot: 32.3.1-GeniusLib-v5.3.0

---

## [32.3.0] — 2026-07-17

### Adicionado
- **Admin Border** — Borda animada rainbow cyberpunk para marcar administradores (co-lideres)
  - Botão "🛡️ Admin" nos cards dos membros e no modal de perfil (somente admin/master)
  - Ribbon "🛡️ ADMIN" com gradiente animado no card do membro
  - Endpoint `POST /api/admin_border/{player_tag}` com verificação de permissão
  - Campo `admin_border` salvo no MongoDB (`player_notes`)
- **Histórico de Ataques Perdidos no Perfil** — nova seção "📋 Registro de Ataques Perdidos" no modal de perfil do jogador mostrando data da guerra, oponente e quantidade de ataques perdidos

### Corrigido
- **Ícone de ataque perdido após perdão** — o ícone ❗ agora só considera a guerra mais recente (flag `is_latest`), não mais todo o histórico. Antes, um jogador perdoado continuava com o ícone por guerras antigas
- **Cache de missed_attacks não invalidado** — ao adicionar/remover da watchlist, o cache `missed_attacks` agora também é limpo junto com o cache `members`
- **Dados missed_attacks desatualizados no refresh** — ao refrescar a aba de membros, `globalMissedAttacks` agora também é atualizado via `Promise.all`

### Alterado
- Versão do bot: 32.3.0-GeniusLib-v5.3.0
- Badge do README atualizada para v32.3.0

---

## [32.2.3] — 2026-07-17

### Adicionado
- **Botão de Changelog no Admin Panel** — novo botão "📋 Enviar Changelog para Discord" na aba Ações que lê o CHANGELOG.md e envia embed formatado para o canal #atualizacao
- Embed com cores, versão, data, e categorias com emojis (✨ Adicionado, 🔧 Alterado, 🐛 Corrigido, 🗑️ Removido)
- Variável de ambiente `CHANGELOG_CHANNEL_ID` (default: canal #atualizacao)
- `changelog_channel_id` adicionado às configurações editáveis pelo admin panel

### Alterado
- Versão do bot: 32.2.3-GeniusLib-v5.3.0
- Badge do README atualizada para v32.2.3

---

## [32.2.2] — 2026-07-15

### Alterado
- **Assets servidos via GeniusLib** — usa get_assets_dir() do GeniusLib v5.3.0 em vez de cópia local
- Rota estática mudou de `/static/images/assets/` para `/assets/`
- Removida cópia de 3000+ arquivos .webp de `static/images/assets/`
- Removido import pkg_resources não utilizado

### Alterado
- Versão do bot: 32.2.2-GeniusLib-v5.3.0

---

## [32.2.1] — 2026-07-15

### Corrigido
- **Tropas e Feitiços ausentes no perfil** — profile_cog.fetch_player_profile_data() não retornava 	roops nem spells (endpoint correto era chamado, mas os dados não estavam no dict de retorno)

### Alterado
- Versão do bot: 32.2.1-GeniusLib-v5.2.0

---
## [32.2.0] ΓÇö 2026-07-15

### Adicionado
- **Integra├º├úo com ClashKingAssets** ΓÇö mais de 3000 assets oficiais do Clash of Clans em WebP
  - Assets servidos diretamente da GeniusLib via `/static/images/assets/`
  - Troops, Heroes, Spells, Equipment, Pets, Buildings, Leagues, Resources e muito mais
  - Fun├º├úo helper `getAssetUrl()` no dashboard para gerar URLs corretas

### Alterado
- Dashboard agora usa assets oficiais para TH levels e herois (substituindo PNGs antigos)
- Herois no modal de perfil agora usam `getAssetUrl('heroes', nome)` em vez de mapeamento manual
- Town halls no war log, member grid e profile modal agora usam `buildings/home-village/town_hall/level_N.webp`
- Vers├úo do bot: `32.2.0-GeniusLib-v5.2.0`

### Removido
- Imagens antigas de herois removidas (`static/images/heroes/`)
- Town hall PNGs antigos removidos (`static/images/townhall*.png`)

---

### Adicionado
- **Legend Army Cards Redesign** ΓÇö reescrita completa da aba "Exercitos" no painel web
  - Cards estruturados com separadores visuais (Herois / Tropas / Feiticos)
  - Estatisticas de desempenho por exercito (estrelas medias, destruicao media, win rate)
  - Badges de tropas com quantidade em destaque
  - Herois com pet e equipamento exibidos em rows individuais
  - Botao **"Copiar"** para exportar army share code direto para o Clash of Clans
  - Agrupamento por performance: 3 Estrelas, 2+ Estrelas, Outros
  - CSS dedicado seguindo o design system v32 (CSS variables, responsivo)

### Corrigido
- XSS potencial no botao copiar ΓÇö migrado de inline `onclick` para `data-army-code` + event delegation
- Exercitos vazios (army object sem troops/spells/heroes) agora sao filtrados

---

## [32.0.0] ΓÇö 2025-07-14

### Adicionado
- **Redesign profissional completo** ΓÇö layout sidebar vertical (estilo ClashLens)
  - Sidebar fixa a esquerda com navegacao vertical
  - Conteudo principal a direita com scroll independente
  - Inter font (tipografia moderna)
  - Tema dark/light com toggle
  - Tailwind CDN para utilitarios de espacamento
  - CSS variables completo (light + dark themes)
  - Cards e componentes com espacamento consistente

### Removido
- Layout antigo com navbar horizontal
- Fontes Orbitron/Rajdhani/Fira Code (substituidas por Inter)
- Tema cyberpunk 2088 neon (substituido por design profissional limpo)

---

## [31.3.2] ΓÇö 2025-07-12

### Sincronizado
- Main-Estavel-ML atualizada com dev2 (Legend League completo)

---

## [31.3.1] ΓÇö 2025-07-12

### Corrigido
- `TypeError` em `from_timestamp()` quando `timestamp` e `None` no battle log (GeniusLib v5.1.1)

---

## [31.3.0] ΓÇö 2025-07-12

### Adicionado
- **Legend League (Battle Logs)** ΓÇö sistema completo de analise de Legend League
  - Cog `battlelog_cog.py` com 4 slash commands: `/legend`, `/legend_historico`, `/legend_resumo`, `/legend_exercitos`
  - Tarefas automaticas: snapshot de battle logs a cada 2h, relatorio diario as 23:59
  - Web API: 3 endpoints (`/api/legend`, `/api/legend/history`, `/api/legend/clan`)
  - Dashboard web: aba "Legend" com seletor de jogador, 4 cards de resumo (win rate, dano medio, estrelas, consistencia) e 5 sub-abas (Ataques, Defesas, Saques, Exercitos, Historico)
- **GeniusLib v5.1.0** ΓÇö models e analytics para battlelog e league history
  - 6 modelos: `BattleLogEntry`, `LeagueHistoryEntry`, `LeagueTierGroup`, `LeagueTierGroupMember`, `LeagueTierGroupBattleLogEntry`, `BattleLogResource`
  - 15 funcoes de analytics: win rate, streak, loot, progression, MVP, consistency score, etc.
  - Client retorna models tipados ao inves de dicts brutos

---

## [31.2.3] ΓÇö 2025-07-10

### Corrigido
- Missed attacks report: fallback scan quebrado, verificacao de estado incorreta, contagem de ataques errada

---

## [31.2.2] ΓÇö 2025-07-10

### Corrigido
- Role mention nao funcionava ΓÇö `allowed_mentions` default bloqueava mencoes de cargo

---

## [31.2.1] ΓÇö 2025-07-10

### Corrigido
- CSRF token validation
- Role mention em alertas de manutencao
- Channel fallback quando canal configurado nao existe
- Hardcoded channel ID removido
- Exception logging melhorado

---

## [31.2.0] ΓÇö 2025-07-10

### Adicionado
- **GeniusLib v4.3.0** ΓÇö Dragon Duke, Town Hall 17/18, pets fix
- Dragon Duke hero image e mapping

### Corrigido
- GeniusLib dependency: tag v4.3.0 ao inves de commit hash

---

## [31.1.0] ΓÇö 2025-07-09

### Adicionado
- **Security overhaul** completo
  - XSS sanitization com `escapeHtml()` em todo output dinamico
  - CSRF protection em todos os endpoints POST do admin
  - Encrypted cookie storage (Fernet) para sessoes
  - Security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy
  - Anti-DevTools: bloqueio de right-click, F12, Ctrl+Shift+I/J/C
- Watchlist ordenada por data de adicao (mais recente primeiro)

### Corrigido
- `EncryptedCookieStorage`: removido arg `same_site` (incompativel com aiohttp_session no Render)

---

## [31.0.0] ΓÇö 2025-07-08

### Adicionado
- **DiscoHook** ΓÇö editor visual de embeds do Discord no painel admin
  - Cria├º├úo de mensagens ricas com multiplos embeds, campos, cores, imagens
  - Envio direto via Webhook
  - Preview ao vivo estilo Discord
  - Deteccao automatica de nome/avatar do webhook
- **Post-War Analysis** ΓÇö analise pos-guerra separada para canal dedicado
- Seletor de canal de alerta de manutencao no admin

### Corrigido
- Aba guerra (layout e dados)
- Capital Image
- Modo manutencao, tooltips e perfil de membro

---

## [30.x] ΓÇö 2025-07-07

### Adicionado
- **Migracao para GeniusLib v4.0.0** ΓÇö wrapper async proprio para API CoC
- War preference tracking (opted-in/out)
- Enhanced profiles com mais dados
- War alerts melhorados
- Novos comandos: `!ver` (super profile com UI Discord)

### Corrigido
- 14 bugs criticos na migracao
- `/war_log` ΓÇö async loop corrigido
- `raw_attribute=True` para acessar dados brutos da API

---

## [29.x] ΓÇö 2025-07-06

### Adicionado
- **Radar Pericial v3** ΓÇö IsolationForest, Bayes, fingerprints para deteccao de smurfs
- Integracao GeniusLib v4.1.0 (formatters, raid_analytics, health_stats)
- **Player Analytics** ΓÇö K-Means para classificacao de membros (General, Especialista, Instavel, Risco)
- **War Advisor** ΓÇö plano de ataque IA com algoritmo hungaro
- **CWL Planner** ΓÇö escala├º├úo inteligente com K-Means + fairness scoring

### Corrigido
- IndexError em smurf_detection_cog quando Spell level fora de alcance
- Bare except blocks convertidos para excecoes especificas

---

## [28.x] ΓÇö 2025-07-05

### Adicionado
- **Tema Cyberpunk 2088** ΓÇö overhaul visual completo
  - Cores neon: ciano, rosa, roxo, verde
  - Animacoes: scanlines, grid background, glow pulsante, glitch text
  - Particulas flutuantes no background
  - Tooltips neon interativos
  - Fontes: Orbitron (titulos), Rajdhani (corpo), Fira Code (mono)
- **Upgrade Tracker** ΓÇö estimativa de custos e tempo de upgrades
- **Exportador de Dados** ΓÇö JSON e CSV para cl├ú e membros
- **Comparador de Jogadores** ΓÇö lado a lado com diferencas destacadas
- **Middleware Pipeline** ΓÇö logging e monitoramento de latencia na API CoC
- Aba Capital com raio-x completo (ataques, saque, ausentes, incompletos)
- Aba Jogos do Cl├ú com progresso da caravana
- Sistema de notas com prioridade (verde/amarelo/vermelho)
- Status CWL por membro (Fixo, Ativo, Reserva)

---

## [27.x] ΓÇö 2025-07-04

### Adicionado
- **Painel Web** ΓÇö dashboard cyberpunk completo
  - Abas: Clan, Destaques, Guerra, Pendencias, CWL, Jogos, Capital, Historico, Membros
  - Cards pulsantes com estatisticas
  - Graficos interativos (Chart.js)
  - Barra de ocupacao animada
- **Painel Admin** ΓÇö controle total do bot
  - Login com efeitos de raio e fogo
  - 9 abas: Geral, Diagnostico, Configuracoes, Watchlist, Radar Pericial, Analytics IA, Acoes, Base de Dados, DiscoHook
  - Sistema de usuarios com registro, aprovacao e roles (admin/viewer)
- **Web API** ΓÇö 16+ endpoints REST publicos e 16+ endpoints admin
- **Cache** ΓÇö in-memory TTL cache com LRU eviction e stats
- Background tasks: war end detection, donation snapshots, API status check, CWL detection

---

## Versoes Anteriores

- **v26.x** ΓÇö Deteccao de smurfs (fuzzywuzzy, cosseno, DTW), Watchlist, Donation tracking
- **v25.x** ΓÇö Clan Games monitor, Capital raid reports, Performance audits
- **v24.x** ΓÇö War Prediction v2 (RandomForest), Event listeners (join/leave/update)
- **v23.x** ΓÇö Bot Discord basico com comandos de guerra e doacoes
- **v1.0** ΓÇö Inicio do projeto
