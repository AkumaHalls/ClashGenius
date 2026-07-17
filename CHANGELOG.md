# Changelog ΓÇö ClashGenius

Todas as mudan├ºas not├íveis neste projeto. Formato baseado em [Keep a Changelog](https://keepachangelog.com/).

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
