// =========================================================
// GAVETA GLOBAL DO RADAR DE INATIVIDADE (À PROVA DE FALHAS)
// =========================================================

window.toggleRadarDrawer = function() {
    const drawer = document.getElementById('radar-drawer');
    if (drawer) drawer.classList.toggle('open');
};

// A Mente da IA: Faz a leitura das datas e julga as penalidades
window.updateRadarNotifications = function(members) {
    const drawerContent = document.getElementById('radar-content');
    const badge = document.getElementById('radar-badge');
    if (!drawerContent || !badge) return;

    drawerContent.innerHTML = '';
    let alertCount = 0;
    const now = new Date();

    members.forEach(member => {
        let lastWarStr = member.last_war_date;
        
        // Pula quem nunca participou (não possui data)
        if (!lastWarStr) return;
        
        // Como o seu web_api_cog envia "last_war_date" em formato ISO (ex: 2026-03-01T22:00:00Z),
        // o JavaScript entende perfeitamente e converte para data.
        let lastWar = new Date(lastWarStr);

        // Se a data for inválida, ignora para não quebrar a tela
        if (isNaN(lastWar.getTime())) return;

        // Calcula quantos dias exatos se passaram
        const diffTime = now.getTime() - lastWar.getTime();
        const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

        if (diffDays >= 15) {
            alertCount++;
            let alertType, icon, message, colorClass;

            if (diffDays >= 30) {
                alertType = "INFRAÇÃO GRAVE (30+ dias)";
                icon = '<img src="/assets/icons/Icon_HV_Attack_Star.png" class="icon-sm" alt="critical">';
                colorClass = "alert-critical";
                message = `Atenção: O membro <strong>${escapeHtml(member.name)}</strong> violou a diretriz principal do clã. O sistema forense registra exatos <strong>${diffDays} dias</strong> sem qualquer participação no campo de guerra. Remoção recomendada.`;
            } else if (diffDays >= 22) {
                alertType = "ALERTA VERMELHO (22+ dias)";
                icon = '<img src="/assets/icons/Icon_HV_Raid_Attack.png" class="icon-sm" alt="alert">';
                colorClass = "alert-danger";
                message = `Risco altíssimo de desligamento: A conta de <strong>${escapeHtml(member.name)}</strong> está congelada há <strong>${diffDays} dias</strong>. Sugere-se intervenção imediata da liderança para cobrança.`;
            } else {
                alertType = "ATENÇÃO TÁTICA (15+ dias)";
                icon = '<img src="/assets/icons/Icon_HV_Sword.png" class="icon-sm" alt="target">';
                colorClass = "alert-warning";
                message = `A conta <strong>${escapeHtml(member.name)}</strong> acaba de entrar no radar de ociosidade. A nossa telemetria aponta <strong>${diffDays} dias</strong> sem se voluntariar para o confronto.`;
            }

            const alertHTML = `
                <div class="radar-alert ${colorClass}">
                    <div class="alert-icon">${icon}</div>
                    <div class="alert-text">
                        <strong>${alertType}</strong>
                        <span>${message}</span>
                    </div>
                </div>
            `;
            drawerContent.innerHTML += alertHTML;
        }
    });

    if (alertCount === 0) {
        drawerContent.innerHTML = `
            <div class="radar-empty">
                <div style="font-size: 3rem; margin-bottom: 10px;"><img src="/assets/icons/Icon_HV_Shield.png" class="icon-sm" alt="clean"></div>
                <p>O radar está limpo.<br>Nenhum membro detectado em inatividade bélica no momento!</p>
            </div>`;
        badge.style.display = 'none';
    } else {
        badge.textContent = alertCount;
        badge.style.display = 'flex';
    }
};

window.fetchRadarInactivityData = async function() {
    const drawerContent = document.getElementById('radar-content');
    
    try {
        // CORREÇÃO: Apontando para a rota EXATA definida no seu arquivo clash.py (api_members_handler)
        let response = await fetch('/api/members');
        
        if (response.ok) {
            const data = await response.json();
            if (data && data.members) {
                window.updateRadarNotifications(data.members);
            } else {
                if (drawerContent) drawerContent.innerHTML = '<div class="radar-empty"><p style="color:#f1c40f;">Nenhum membro encontrado na API.</p></div>';
            }
        } else {
             if (drawerContent) drawerContent.innerHTML = `<div class="radar-empty"><p style="color:#e74c3c;">Erro de conexão com o Banco de Dados (Código ${response.status}).</p></div>`;
        }
    } catch (e) {
        console.error('Falha de leitura térmica do radar:', e);
        if (drawerContent) drawerContent.innerHTML = `<div class="radar-empty"><p style="color:#e74c3c;">Falha crítica ao tentar buscar as datas de inatividade.</p></div>`;
    }
};

// Dispara a leitura assim que a página carrega (apenas no painel admin)
if (window.location.pathname.includes('admin')) {
    window.fetchRadarInactivityData();
    setInterval(window.fetchRadarInactivityData, 30 * 60 * 1000);
}

// =========================================================
// RESTANTE DO CÓDIGO PADRÃO DO PAINEL ADMIN
// =========================================================
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.querySelector('form[action="/admin/login"]');
    if (loginForm) {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('error')) {
            const errorMessageEl = document.getElementById('error-message');
            if(errorMessageEl) errorMessageEl.textContent = 'Senha incorreta. Tente novamente.';
        }
        const guildId = urlParams.get('guild_id');
        const guildIdInput = document.getElementById('guild_id');
        if (guildId && guildIdInput) {
            guildIdInput.value = guildId;
        }
    }

    if (!window.location.pathname.includes('/admin')) return;

    // --- Autenticação de Usuário e Restrições de Role ---
    let currentUserRole = 'admin';
    let currentUsername = '';

    async function checkUserAuth() {
        try {
            const resp = await fetch('/api/admin/auth/me');
            if (resp.ok) {
                const data = await resp.json();
                currentUserRole = data.role || 'admin';
                currentUsername = data.username || '';
            }
        } catch(e) {}
        
        const roleBadge = document.getElementById('user-role-badge');
        if (roleBadge) {
            const isViewer = currentUserRole === 'viewer';
            roleBadge.textContent = isViewer ? 'Membro Sênior' : 'Admin';
            roleBadge.style.color = isViewer ? 'var(--neon-orange)' : 'var(--neon-cyan)';
            roleBadge.style.borderColor = isViewer ? 'rgba(255,165,0,0.3)' : 'rgba(0,255,249,0.3)';
            roleBadge.style.background = isViewer ? 'rgba(255,165,0,0.1)' : 'rgba(0,255,249,0.1)';
        }

        if (currentUserRole === 'viewer') {
            document.querySelectorAll('[data-viewer-hide]').forEach(el => el.style.display = 'none');
            document.querySelectorAll('[data-admin-only]').forEach(el => el.style.display = 'none');
            document.querySelectorAll('.control-btn, .btn-admin, .logout-btn, [data-write-only]').forEach(el => {
                if (el.classList.contains('logout-btn')) return;
                el.disabled = true; el.style.opacity = '0.4'; el.style.pointerEvents = 'none';
            });
            document.querySelectorAll('form').forEach(f => {
                f.querySelectorAll('button, input[type="submit"], select, input, textarea').forEach(el => {
                    el.disabled = true; el.style.opacity = '0.5';
                });
            });
        }
    }
    checkUserAuth();

    // --- Seletores ---
    const toggleBtn = document.getElementById('toggle-maintenance-btn');
    const testBtn = document.getElementById('send-test-embed-btn');
    const statusTextEl = document.getElementById('maintenance-status-text');
    const botVersionEl = document.getElementById('bot-version-text');
    const apiStatusBadge = document.getElementById('api-status-badge');
    const apiStatusMessage = document.getElementById('api-status-message');
    const recentLogsBox = document.getElementById('recent-logs-box');
    const settingsForm = document.getElementById('settings-form');
    const settingsFeedback = document.getElementById('settings-feedback');
    const actionsFeedback = document.getElementById('actions-feedback');
    const geralFeedback = document.getElementById('geral-feedback'); 
    const dbFeedback = document.getElementById('db-feedback');
    const dbWarsTableBody = document.querySelector('#db-wars-table tbody');
    const dbNotesTableBody = document.querySelector('#db-notes-table tbody');
    const sendAnnouncementBtn = document.getElementById('send-announcement-btn');
    const announcementChannelInput = document.getElementById('announcement-channel-id');
    const announcementMessageInput = document.getElementById('announcement-message');

    const addWatchlistForm = document.getElementById('admin-add-watchlist-form');
    const watchlistTableBody = document.querySelector('#admin-watchlist-table tbody');
    const watchlistAddFeedback = document.getElementById('watchlist-add-feedback');
    const watchlistListFeedback = document.getElementById('watchlist-list-feedback');
    const watchlistFilterName = document.getElementById('watchlist-filter-name');
    const watchlistFilterTag = document.getElementById('watchlist-filter-tag');
    
    const radarFeedback = document.getElementById('radar-feedback');

    const navLinks = document.querySelectorAll('.admin-nav .nav-link');
    const contentSections = document.querySelectorAll('.admin-section');
    const initialSectionId = document.querySelector('.admin-nav .nav-link')?.dataset.section || 'admin-geral'; 
    let currentActiveSectionId = localStorage.getItem('activeAdminSection') || initialSectionId;

    // --- Funções API --- 
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    async function fetchAdminAPI(endpoint, options = {}) {
        const isPostWithoutBodyResponse = options.method === 'POST' && (endpoint.startsWith('watchlist/') || endpoint === 'actions' || endpoint === 'settings');
        
        // Garantir que credentials seja incluído para enviar cookies de sessão
        const defaultOptions = {
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        };

        // Add CSRF token for non-GET requests
        if (options.method && options.method !== 'GET') {
            const csrfToken = getCsrfToken();
            if (csrfToken) {
                defaultOptions.headers['X-CSRF-Token'] = csrfToken;
            }
        }

            const finalOptions = {
                ...defaultOptions,
                ...options,
                headers: {
                    ...defaultOptions.headers,
                    ...(options.headers || {})
                }
            };

        try {
            const response = await fetch(`/api/admin/${endpoint}`, finalOptions);

            if (response.status === 204) return { status: 'success', message: 'Operação concluída.' };

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: `Erro HTTP ${response.status}` }));
                throw new Error(errorData.message || `Falha ao acessar ${endpoint}`);
            }

            if (isPostWithoutBodyResponse && response.status === 200) {
                 try { return await response.json(); } catch(e) { return { status: 'success', message: 'Ação executada.' }; }
            }

            return response.json(); 
        } catch (error) {
            console.error(`Erro na API admin em ${endpoint}:`, error);
            let feedbackEl = actionsFeedback; 
            if (currentActiveSectionId === 'admin-configuracoes') feedbackEl = settingsFeedback;
            else if (currentActiveSectionId === 'admin-watchlist') feedbackEl = watchlistListFeedback || watchlistAddFeedback;
            else if (currentActiveSectionId === 'admin-geral') feedbackEl = geralFeedback;
            else if (currentActiveSectionId === 'admin-db') feedbackEl = dbFeedback;
            else if (currentActiveSectionId === 'admin-radar') feedbackEl = radarFeedback;

            displayFeedback(feedbackEl, `Erro: ${error.message}`, true);
            throw error; 
        }
    }

    function displayFeedback(element, message, isError = false, duration = 4000) {
        if (!element) return;
        element.textContent = message;
        element.classList.remove('error', 'success'); 
        element.classList.add(isError ? 'error' : 'success'); 
        if (element.timeoutId) clearTimeout(element.timeoutId);
        element.timeoutId = setTimeout(() => { element.textContent = ''; element.classList.remove('error', 'success'); }, duration);
    }

    function updateStatus(data) {
        if (statusTextEl) {
            statusTextEl.textContent = data.maintenance_mode ? 'ATIVADO' : 'DESATIVADO';
            statusTextEl.className = `status-badge ${data.maintenance_mode ? 'status-on' : 'status-off'}`;
        }
        if(botVersionEl) botVersionEl.textContent = data.version || '-';
    }

    function updateDiagnostics(data) {
        if (!data) return; 
        const { api_status, recent_logs } = data;
        if(apiStatusBadge && api_status) { 
            apiStatusBadge.className = `status-badge status-${api_status.status}`;
            apiStatusBadge.textContent = api_status.status === 'ok' ? 'Operacional' : (api_status.status === 'maintenance' ? 'Manutenção' : 'Erro');
        }
        if(apiStatusMessage && api_status) apiStatusMessage.textContent = api_status.message; 
        if(recentLogsBox) recentLogsBox.textContent = Array.isArray(recent_logs) && recent_logs.length > 0 ? recent_logs.join('\n') : 'Nenhum log recente.'; 
    }

    function populateDiscordDropdowns(discordData) {
        if (!discordData || discordData.error) return;

        const channelSelects = ['channel_id', 'post_war_analysis_channel_id', 'post_war_verdict_channel_id', 'clan_games_channel_id', 'cwl_planner_channel_id', 'donations_channel_id', 'watchlist_alert_channel_id', 'low_performance_channel_id', 'capital_report_channel_id', 'smurf_log_channel_id', 'maintenance_alert_channel_id', 'changelog_channel_id', 'war_preference_channel_id'];
        const roleSelects = ['role_id_1star_alert', 'role_id_missed_attack', 'leader_role_id', 'coleader_role_id', 'maintenance_role_id'];

        channelSelects.forEach(id => {
            const select = document.getElementById(id);
            if (select && discordData.channels) {
                select.innerHTML = '<option value="0">Nenhum / Desativado</option>' + 
                    discordData.channels.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
            }
        });

        roleSelects.forEach(id => {
            const select = document.getElementById(id);
            if (select && discordData.roles) {
                select.innerHTML = '<option value="0">Nenhum / Desativado</option>' + 
                    discordData.roles.map(r => `<option value="${r.id}">${escapeHtml(r.name)}</option>`).join('');
            }
        });
    }

    function populateSettingsForm(data) {
        if (!data || data.error || !settingsForm) return;

        for (const key in data) {
            const input = document.getElementById(key);
            if (input) {
                if (input.tagName === 'SELECT') {
                    const valStr = String(data[key] || "0");
                    let optionExists = false;
                    for (let i = 0; i < input.options.length; i++) {
                        if (input.options[i].value === valStr) {
                            optionExists = true;
                            break;
                        }
                    }
                    if (!optionExists && valStr !== "0") {
                        const dummyOpt = document.createElement("option");
                        dummyOpt.value = valStr;
                        dummyOpt.text = `ID Desconhecido (Salvo: ${valStr})`;
                        input.add(dummyOpt);
                    }
                    input.value = valStr;
                } else if (input.type === 'checkbox') {
                    input.checked = (data[key] === 'true' || data[key] === true);
                } else {
                    input.value = data[key] !== null && data[key] !== undefined ? data[key] : '';
                }
            }
        }
    }

    function updateDbViewer(data) {
        if (!data || data.error) {
             displayFeedback(dbFeedback, data?.error || 'Erro ao carregar dados do DB.', true);
             return; 
        }

        const formatDbDate = (isoString) => {
             if (!isoString) return 'N/A';
             try { return new Date(isoString).toLocaleString('pt-BR'); }
             catch(e) { return 'Data Inválida'; }
        }

        const createClickToCopyCell = (text) => {
             if (!text) return '<td>N/A</td>';
             const td = document.createElement('td');
             td.textContent = text;
             td.style.cursor = 'pointer';
             td.title = 'Clique para copiar';
             td.onclick = async () => {
                 try {
                     await navigator.clipboard.writeText(text);
                     const originalText = td.textContent;
                     td.textContent = 'Copiado!';
                     setTimeout(() => { td.textContent = originalText; }, 1500);
                 } catch (err) { console.error('Falha ao copiar ID:', err); }
             };
             return td;
         };

        if(dbWarsTableBody && Array.isArray(data.last_wars)) { 
            dbWarsTableBody.innerHTML = data.last_wars.length > 0
                ? data.last_wars.map(w => {
                     const row = document.createElement('tr');
                     row.innerHTML = `<td>${escapeHtml(w.opponent || 'N/A')}</td><td>${formatDbDate(w.end_time)}</td>`;
                     row.appendChild(createClickToCopyCell(w.id)); 
                     return row.outerHTML;
                  }).join('')
                : '<tr><td colspan="3">Nenhum registro de guerra encontrado.</td></tr>';
        } else if (dbWarsTableBody) {
             dbWarsTableBody.innerHTML = '<tr><td colspan="3">Erro ao carregar guerras.</td></tr>';
             displayFeedback(dbFeedback, 'Erro ao carregar histórico de guerras.', true);
        }

        if(dbNotesTableBody && Array.isArray(data.last_notes)) { 
            dbNotesTableBody.innerHTML = data.last_notes.length > 0
                ? data.last_notes.map(n => `
                    <tr>
                        <td>${escapeHtml(n.player_tag || 'N/A')}</td>
                        <td>${escapeHtml(n.note || '-')}</td>
                        <td class="priority-cell priority-${escapeHtml(n.priority || 'none')}">${escapeHtml(n.priority || 'none')}</td>
                    </tr>`).join('')
                : '<tr><td colspan="3">Nenhuma nota de jogador encontrada.</td></tr>';
        } else if (dbNotesTableBody) {
             dbNotesTableBody.innerHTML = '<tr><td colspan="3">Erro ao carregar notas.</td></tr>';
             displayFeedback(dbFeedback, 'Erro ao carregar notas de jogadores.', true);
        }
    }

    function applyWatchlistFilter() {
        if (!watchlistTableBody) return; 

        const filterName = watchlistFilterName ? watchlistFilterName.value.toLowerCase() : '';
        const filterTag = watchlistFilterTag ? watchlistFilterTag.value.toLowerCase() : '';

        const rows = watchlistTableBody.querySelectorAll('tr');

        rows.forEach(row => {
            const cellName = row.cells[0] ? row.cells[0].textContent.toLowerCase() : '';
            const cellTag = row.cells[1] ? row.cells[1].textContent.toLowerCase() : '';
            const nameMatch = cellName.includes(filterName);
            const tagMatch = cellTag.includes(filterTag);
            if (nameMatch && tagMatch) { row.style.display = ''; } else { row.style.display = 'none'; }
        });
    }

    async function loadWatchlist() {
        if (!watchlistTableBody) return;
        watchlistTableBody.innerHTML = '<tr><td colspan="6"><div class="loading-spinner" style="margin: 10px auto; width: 20px; height: 20px;"></div></td></tr>'; 
        try {
            const response = await fetchAdminAPI('watchlist'); 
            if (response.error) {
                 watchlistTableBody.innerHTML = `<tr><td colspan="6" class="error-text">Erro: ${escapeHtml(response.error)}</td></tr>`;
                 displayFeedback(watchlistListFeedback, `Erro: ${response.error}`, true);
                 return;
            }
            const watchlist = Array.isArray(response) ? response : [];

            if (watchlist.length === 0) {
                 watchlistTableBody.innerHTML = '<tr><td colspan="6">Nenhum jogador na lista de observação.</td></tr>';
                 return;
            }
            const isViewer = currentUserRole === 'viewer';
            const actionHeader = document.querySelector('#admin-watchlist-table thead th:last-child');
            if (actionHeader) actionHeader.style.display = isViewer ? 'none' : '';
            if (isViewer) {
                const addForm = document.getElementById('admin-add-watchlist-form');
                if (addForm) addForm.style.display = 'none';
            }
            watchlistTableBody.innerHTML = watchlist.map(player => {
                let dateStr = '-';
                if (player.date_added) {
                     try { dateStr = new Date(player.date_added).toLocaleDateString('pt-BR'); }
                     catch(e) { dateStr = player.date_added; } 
                }
                return `
                <tr>
                    <td><strong>${escapeHtml(player.name || 'N/A')}</strong></td>
                    <td style="font-family: monospace; color: var(--color-accent);">${escapeHtml(player._id || 'N/A')}</td>
                    <td>${escapeHtml(player.reason || '-')}</td>
                    <td>${escapeHtml(player.details || '-')}</td>
                    <td>${escapeHtml(dateStr)}</td>
                    <td>${isViewer ? '' : `<button class="admin-remove-btn btn-admin btn-danger" data-tag="${escapeHtml(player._id || '')}" style="padding: 5px 10px;">Remover</button>`}</td>
                </tr>`;
            }).join('');

            watchlistTableBody.querySelectorAll('.admin-remove-btn').forEach(btn => {
                btn.addEventListener('click', handleRemoveWatchlist);
            });

            applyWatchlistFilter();
        } catch (error) {
             watchlistTableBody.innerHTML = '<tr><td colspan="6" class="error-text">Erro ao carregar a lista. Verifique a consola.</td></tr>';
        }
    }

    async function handleAddWatchlist(event) {
        event.preventDefault();
        if (!addWatchlistForm) return;
        const formData = new FormData(addWatchlistForm);
        const data = Object.fromEntries(formData.entries());

        if (!data.player_tag || !data.player_tag.startsWith('#') || data.player_tag.length < 5) {
             displayFeedback(watchlistAddFeedback, 'Por favor, insira uma tag válida (Ex: #ABC123XYZ).', true);
             return;
        }

        displayFeedback(watchlistAddFeedback, 'Adicionando...');
        try {
            const response = await fetchAdminAPI('watchlist/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
             displayFeedback(watchlistAddFeedback, response.message || 'Jogador adicionado/atualizado.');
             if (response.status === 'success' || !response.error) { 
                 addWatchlistForm.reset();
                 loadWatchlist(); 
             } else {
                  displayFeedback(watchlistAddFeedback, response.message || 'Erro desconhecido ao adicionar.', true);
              }
        } catch (error) { displayFeedback(watchlistAddFeedback, 'Erro de conexão ao adicionar.', true); }
    }

    async function handleRemoveWatchlist(event) {
        const button = event.target;
        const playerTag = button.dataset.tag;
        const playerName = button.closest('tr')?.cells[0]?.textContent || playerTag; 
        if (!playerTag || !confirm(`Tem certeza que deseja remover ${playerName} (${playerTag}) da lista?`)) {
            return;
        }

        button.disabled = true; 
        button.textContent = '...';
        displayFeedback(watchlistListFeedback, 'Removendo...');
        try {
             const response = await fetchAdminAPI('watchlist/remove', {
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ player_tag: playerTag })
            });

             if (response.status === 'success' || response.status === 'not_found' || !response.error) {
                 displayFeedback(watchlistListFeedback, response.message || "Operação concluída.");
                 loadWatchlist(); 
             } else {
                 displayFeedback(watchlistListFeedback, response.message || 'Erro ao remover.', true);
                 button.disabled = false; 
                 button.textContent = 'Remover';
             }
        } catch (error) {
           displayFeedback(watchlistListFeedback, `Erro: ${error.message}`, true);
           button.disabled = false; 
           button.textContent = 'Remover';
        }
    }

    // =========================================================
    // RENDERIZADOR XAI (EXPLAINABLE AI) - TERMINAL FORENSE
    // =========================================================
async function loadRadarDossier() {
        const container = document.getElementById('radar-dossier-container');
        if (!container) return;
        try {
            const data = await fetchAdminAPI('smurf_dossier');
            
            if(data && data.error) {
                container.innerHTML = `<p class="error-text">${escapeHtml(data.error)}</p>`;
                return;
            }
            
            let dossier = [];
            if (Array.isArray(data)) {
                dossier = data;
            } else if (data && Array.isArray(data.dossier)) {
                dossier = data.dossier;
            } else if (data && Array.isArray(data.data)) {
                dossier = data.data;
            } else if (data && Array.isArray(data.message)) {
                dossier = data.message;
            }
            
            if(dossier.length === 0) {
                container.innerHTML = `
                <div style="text-align:center; padding: 30px; background: rgba(46, 204, 113, 0.05); border: 1px solid rgba(46, 204, 113, 0.2); border-radius: 8px;">
                    <h3 style="color: var(--color-success); margin-bottom:10px;"><img src="/assets/icons/Icon_HV_Shield.png" class="icon-sm" alt="clean"> Clã Limpo (Status Verde)</h3>
                    <p style="color: var(--color-text-secondary);">A Inteligência Forense cruzou todos os eixos de guerra, doação, laboratório e lexicologia nas últimas horas e não encontrou elos suspeitos.</p>
                </div>`;
                return;
            }
            
            let html = '<div class="dossier-grid" style="display: grid; gap: 20px;">';
            
            dossier.forEach(doc => {
                const color = doc.risk_color;
                
                let terminalHtml = '';
                if(doc.thoughts && doc.thoughts.length > 0) {
                    doc.thoughts.forEach(t => {
                        let weightBadge = '';
                        if(t.weight !== "Info" && t.weight !== "Trace") {
                            weightBadge = `<span style="display:inline-block; padding: 2px 6px; background: rgba(255,255,255,0.1); border-radius:3px; margin-right: 8px; font-weight:bold; color: ${color};">[Peso: ${escapeHtml(t.weight)}]</span>`;
                        } else {
                            weightBadge = `<span style="display:inline-block; padding: 2px 6px; background: rgba(255,255,255,0.1); border-radius:3px; margin-right: 8px; color: #a0aec0;">[${escapeHtml(t.axis)}]</span>`;
                        }
                        terminalHtml += `<div style="margin-bottom: 8px; padding-left: 10px; border-left: 2px solid ${color}55;">${weightBadge} <span style="color: #e2e8f0;">${escapeHtml(t.text)}</span></div>`;
                    });
                }
                
                html += `
                <div style="background: rgba(0,0,0,0.25); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                    <div style="padding: 15px 20px; background: linear-gradient(90deg, ${color}22 0%, transparent 100%); border-bottom: 1px solid ${color}44; display:flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-size: 0.75em; text-transform: uppercase; letter-spacing: 1px; color: ${color}; font-weight: bold;">Identificação XAI</span>
                            <h4 style="margin: 5px 0 0 0; font-size: 1.2em; display:flex; align-items:center; gap: 10px;">
                                <img src="/assets/icons/Icon_HV_Podium.png" class="icon-sm" alt="main"> ${escapeHtml(doc.main_name)} <span style="font-size:0.7em; color:var(--color-text-secondary);">${escapeHtml(doc.main_tag)}</span>
                                <span style="color:${color};"><img src="/assets/icons/Icon_HV_Raid_Attack.png" class="icon-sm" alt="link"></span>
                                <img src="/assets/icons/no_star.png" class="icon-sm" alt="smurf"> ${escapeHtml(doc.smurf_name)} <span style="font-size:0.7em; color:var(--color-text-secondary);">${escapeHtml(doc.smurf_tag)}</span>
                            </h4>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 1.8em; font-weight: 900; color: ${color}; line-height: 1;">${doc.confidence}%</div>
                            <div style="font-size: 0.8em; color: var(--color-text-secondary); text-transform:uppercase;">${escapeHtml(doc.risk_label)}</div>
                        </div>
                    </div>
                    
                    <div style="height: 4px; background: rgba(255,255,255,0.05); width: 100%;">
                        <div style="height: 100%; width: ${doc.confidence}%; background: ${color}; box-shadow: 0 0 10px ${color};"></div>
                    </div>
                    
                    <div style="padding: 20px;">
                        <div style="margin-bottom: 8px; font-size: 0.85em; color: var(--color-text-secondary); text-transform:uppercase; font-weight:bold; letter-spacing: 1px;"><img src="/assets/icons/Icon_HV_Attack_Star.png" class="icon-sm" alt="AI"> Motor de Inferência (Cadeia Lógica)</div>
                        <div style="background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px; padding: 15px; font-family: 'Courier New', monospace; font-size: 0.9em; line-height: 1.5; max-height: 250px; overflow-y: auto;">
                            ${terminalHtml}
                        </div>
                    </div>
                    
                    <div style="padding: 15px 20px; background: rgba(0,0,0,0.2); border-top: 1px solid rgba(255,255,255,0.05); display: flex; gap: 15px;">
                        <button onclick="judgeSmurf('${escapeHtml(doc.pair_id)}', 'absolve_smurf')" class="btn-admin" style="background: rgba(46, 204, 113, 0.15); color: #2ecc71; border: 1px solid #2ecc71; flex: 1; transition: all 0.2s;"><img src="/assets/icons/Icon_HV_Shield.png" class="icon-sm" alt="safe"> Falso Positivo (Limpar)</button>
                        <button onclick="judgeSmurf('${escapeHtml(doc.pair_id)}', 'condemn_smurf')" class="btn-admin" style="background: rgba(231, 76, 60, 0.15); color: #e74c3c; border: 1px solid #e74c3c; flex: 1; transition: all 0.2s;"><img src="/assets/icons/Icon_HV_Attack_Star.png" class="icon-sm" alt="danger"> Condenar p/ Watchlist</button>
                    </div>
                </div>`;
            });
            html += '</div>';
            container.innerHTML = html;
            
        } catch(e) {
            container.innerHTML = '<p class="error-text">Falha de comunicação com o Módulo XAI Forense.</p>';
        }
    }
    
    window.judgeSmurf = async (pairId, action) => {
        const isCondemn = action === 'condemn_smurf';
        const msg = isCondemn 
            ? 'ATENÇÃO: TEM CERTEZA?\n\nA Matriz Forense enviará ambas as contas para a Watchlist como "Smurfs Confirmadas" e apagará o dossiê da tela principal.' 
            : 'Absolver Contas?\n\nA IA aprenderá que este padrão é falso positivo e atenuará a pontuação vetorial desta ligação.';
            
        if(!confirm(msg)) return;
        
        const feedback = document.getElementById('radar-feedback');
        displayFeedback(feedback, 'Processando veredito na Base de Dados...');
        
        try {
            const response = await fetchAdminAPI('actions', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: action, payload: {pair_id: pairId}})
            });
            displayFeedback(feedback, response.message || 'Sentença aplicada!');
            loadRadarDossier(); 
        } catch (e) {
             displayFeedback(feedback, 'Erro ao comunicar com o Kernel Central.', true);
        }
    };

    window.cleanupSmurfDB = async () => {
        if(!confirm('ATENÇÃO: TEM CERTEZA?\n\nIsso vai APAGAR TODAS as evidências do Radar Pericial e resetar o banco de dados.\n\nOs dados antigos (sistema v2.0) eram cheios de falsos positivos. Após limpar, o novo sistema v3.0 vai começar do zero com regras muito mais precisas.')) return;

        const feedback = document.getElementById('radar-feedback');
        displayFeedback(feedback, 'Limpando banco de dados do Radar Pericial...');
        
        try {
            const response = await fetchAdminAPI('actions', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'smurf_cleanup', payload: {}})
            });
            displayFeedback(feedback, response.message || 'Banco limpo com sucesso!');
            loadRadarDossier();
        } catch (e) {
            displayFeedback(feedback, 'Erro ao limpar banco de dados.', true);
        }
    };

    function setActiveAdminSection(newSectionId) {
        if (!newSectionId || newSectionId === currentActiveSectionId) return;

        const oldSectionEl = document.getElementById(currentActiveSectionId);
        const newSectionEl = document.getElementById(newSectionId);

        if (!newSectionEl) return;

        if (oldSectionEl) { oldSectionEl.classList.remove('active-section'); }
        navLinks.forEach(link => link?.classList.remove('active-nav-link'));

        newSectionEl.classList.add('active-section');
        const newLink = document.querySelector(`.admin-nav .nav-link[data-section="${newSectionId}"]`);
        if (newLink) newLink.classList.add('active-nav-link');

        const wrapper = document.querySelector('.admin-sections-wrapper');
        if (wrapper) wrapper.classList.toggle('allow-scroll', newSectionId === 'admin-discohook');

        localStorage.setItem('activeAdminSection', newSectionId);
        currentActiveSectionId = newSectionId;
    }

    async function loadAnalyticsData() {
        const tbody = document.querySelector('#analytics-table tbody');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="5"><div class="loading-spinner" style="margin: 10px auto; width: 20px; height: 20px;"></div></td></tr>';

        try {
            // A IA já injetou os dados mágicos aqui dentro da sua rota de membros!
            const response = await fetch('/api/members');
            if (!response.ok) throw new Error('Falha ao buscar dados da IA');
            const data = await response.json();

            if (!data.members || data.members.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5">Nenhum membro encontrado.</td></tr>';
                return;
            }

            // Ordena os jogadores: dos mais confiáveis para os menos confiáveis
            const sortedMembers = data.members.sort((a, b) => (b.attack_probability || 0) - (a.attack_probability || 0));

            tbody.innerHTML = sortedMembers.map(m => {
                const prob = m.attack_probability !== undefined ? `${m.attack_probability}%` : 'Aguardando Guerras...';
                const tier = m.tier || 'Sem Dados Suficientes';
                const wars = m.wars_participated_ml || 0;

                // Colore a porcentagem baseada na confiabilidade
                let probColor = 'var(--color-text-main)';
                if (m.attack_probability >= 90) probColor = '#2ecc71'; // Verde (Confiável)
                else if (m.attack_probability >= 60) probColor = '#f1c40f'; // Amarelo (Atenção)
                else if (m.attack_probability !== undefined) probColor = '#e74c3c'; // Vermelho (Risco)

                return `
                <tr>
                    <td><strong>${escapeHtml(m.name)}</strong></td>
                    <td style="font-family: monospace; color: var(--color-accent);">${escapeHtml(m.tag)}</td>
                    <td style="font-weight: bold;">${escapeHtml(tier)}</td>
                    <td style="color: ${probColor}; font-weight: 900; font-size: 1.1em;">${prob}</td>
                    <td>${wars} / 50</td>
                </tr>`;
            }).join('');

        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="5" class="error-text">Erro ao carregar Analytics: ${escapeHtml(error.message)}</td></tr>`;
        }
    }

    function initTooltips() {
        document.querySelectorAll('[data-tooltip]').forEach(el => {
            if (el.querySelector('.cyber-tooltip')) return;
            const tip = document.createElement('span');
            tip.className = 'cyber-tooltip';
            tip.textContent = el.dataset.tooltip;
            el.appendChild(tip);
            el.style.position = 'relative';
            el.style.cursor = 'help';
        });
    }

    async function loadDataForCurrentTab() {
        [settingsFeedback, actionsFeedback, geralFeedback, dbFeedback, watchlistAddFeedback, watchlistListFeedback, radarFeedback].forEach(el => {
             if (el) el.textContent = '';
        });
        try {
            const status = await fetch('/api/status').then(res => res.ok ? res.json() : { maintenance_mode: true, version: '?', error: 'Status fetch failed' }).catch(err => {
                 return { maintenance_mode: true, version: '?', error: 'Status fetch failed'};
            });
            updateStatus(status);
            if (status.error && currentActiveSectionId === 'admin-geral') { 
                displayFeedback(geralFeedback, status.error, true);
                return;
            }

            switch (currentActiveSectionId) {
                case 'admin-geral':
                    break;
                case 'admin-diagnostico':
                    const diagnostics = await fetchAdminAPI('diagnostics');
                    updateDiagnostics(diagnostics);
                    break;
                case 'admin-configuracoes':
                    const [settings, discordData] = await Promise.all([
                        fetchAdminAPI('settings'),
                        fetchAdminAPI('discord_data')
                    ]);
                    populateDiscordDropdowns(discordData);
                    populateSettingsForm(settings);
                    break;
                case 'admin-db':
                     const dbData = await fetchAdminAPI('db_viewer');
                     updateDbViewer(dbData);
                    break;
                case 'admin-watchlist':
                     await loadWatchlist();
                    break;
                case 'admin-radar':
                     await loadRadarDossier();
                    break;
                case 'admin-analytics':
                     await loadAnalyticsData();
                    break;
                 case 'admin-acoes':
                     break;
                 case 'admin-discohook':
                     break;
                 case 'admin-users':
                     await loadPendingUsers();
                     await loadActiveUsers();
                     break;
             }
        } catch (error) {
            console.error(`Falha ao carregar dados para a aba ${currentActiveSectionId}:`, error);
        }
    }

    contentSections.forEach(section => {
        if (section) section.classList.toggle('active-section', section.id === currentActiveSectionId);
    });
    navLinks.forEach(link => {
        if (link) link.classList.toggle('active-nav-link', link.dataset.section === currentActiveSectionId);
    });
    const wrapper = document.querySelector('.admin-sections-wrapper');
    if (wrapper) wrapper.classList.toggle('allow-scroll', currentActiveSectionId === 'admin-discohook');

    navLinks.forEach((link) => {
        link?.addEventListener('click', (e) => {
            e.preventDefault(); 
            const sectionId = link.dataset.section;
            if (sectionId !== currentActiveSectionId) { 
                 setActiveAdminSection(sectionId);
                 loadDataForCurrentTab();
            }
        });
    });

    if (toggleBtn) {
        toggleBtn.addEventListener('click', async () => {
            let originalText = toggleBtn.textContent;
            toggleBtn.disabled = true; toggleBtn.textContent = 'Aguarde...';
            try {
                await fetch('/admin/toggle_maintenance', { method: 'POST' });
                const status = await fetch('/api/status').then(res => res.ok ? res.json() : { maintenance_mode: false }).catch(()=>({ maintenance_mode: false }));
                updateStatus(status);
                displayFeedback(geralFeedback, status.maintenance_mode ? 'Modo manutenção ATIVADO.' : 'Modo manutenção DESATIVADO.');
            } catch (error) {
                displayFeedback(geralFeedback, `Erro: ${error.message || 'Falha na comunicação.'}`, true);
            }
            finally { toggleBtn.disabled = false; toggleBtn.textContent = originalText; }
        });
    }

    if (testBtn) {
        testBtn.addEventListener('click', async () => {
             let originalText = testBtn.textContent;
            testBtn.disabled = true; testBtn.textContent = 'Enviando...';
            try {
                await fetch('/admin/send_test_embed', { method: 'POST' });
                displayFeedback(geralFeedback, "Mensagem de teste enviada!");
            } catch (error) {
                 displayFeedback(geralFeedback, `Erro: ${error.message || 'Falha na comunicação.'}`, true);
            }
            finally { testBtn.disabled = false; testBtn.textContent = originalText; }
        });
    }

    if (settingsForm) {
        settingsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(settingsForm);
            const settings = {};
            
            for (const [key, value] of formData.entries()) {
                if (key === "auto_add_watchlist_enabled") {
                    settings[key] = value === 'true';
                } else if ((key.includes('_id') || key.includes('channel_id')) && value.match(/^\d+$/)) {
                    settings[key] = value;
                } else if (value.match(/^\d+$/) && !key.includes('message')) {
                     if (value !== '') settings[key] = parseInt(value, 10);
                     else settings[key] = null; 
                } else {
                     settings[key] = value;
                }
            }

            displayFeedback(settingsFeedback, 'Salvando...');
            try {
                const response = await fetchAdminAPI('settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                displayFeedback(settingsFeedback, response.message || 'Configurações salvas.');
            } catch(error) { displayFeedback(settingsFeedback, 'Erro de conexão ao salvar.', true); }
        });
    }

    document.querySelectorAll('.action-btn').forEach(button => {
        button.addEventListener('click', async () => {
             let originalText = button.textContent;
             button.disabled = true; button.textContent = 'Executando...';
            const action = button.dataset.action;
            const payload = JSON.parse(button.dataset.payload || '{}');

            if (action === 'export_clan_json' || action === 'export_players_csv') {
                try {
                    const endpoint = action === 'export_clan_json' ? 'export/clan?format=json' : 'export/players?format=csv';
                    const resp = await fetch(`/api/admin/${endpoint}`);
                    const data = await resp.json();
                    if (data.error) { displayFeedback(actionsFeedback, data.error, true); return; }
                    const ext = action === 'export_clan_json' ? 'json' : 'csv';
                    const mime = action === 'export_clan_json' ? 'application/json' : 'text/csv';
                    const blob = new Blob([data.data], { type: mime });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `clashgenius_admin_export.${ext}`;
                    a.click();
                    URL.revokeObjectURL(url);
                    displayFeedback(actionsFeedback, `Exportação concluída!`);
                } catch (error) {
                    displayFeedback(actionsFeedback, 'Erro na exportação.', true);
                }
                finally { button.disabled = false; button.textContent = originalText; }
                return;
            }

            displayFeedback(actionsFeedback, `Executando ${action}...`);
            try {
                const response = await fetchAdminAPI('actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action, payload })
                });
                displayFeedback(actionsFeedback, response.message || `Ação '${action}' concluída.`);
            } catch (error) { displayFeedback(actionsFeedback, 'Erro de conexão ao executar ação.', true); }
             finally { button.disabled = false; button.textContent = originalText; }
        });
    });

    if (sendAnnouncementBtn) {
        sendAnnouncementBtn.addEventListener('click', async () => {
            let originalText = sendAnnouncementBtn.textContent;
            sendAnnouncementBtn.disabled = true; sendAnnouncementBtn.textContent = 'Enviando...';
            const channelId = announcementChannelInput?.value; 
            const message = announcementMessageInput?.value;
            if (!channelId || !channelId.match(/^\d+$/) || !message) {
                 displayFeedback(actionsFeedback, "Preencha um ID numérico e a mensagem.", true);
                 sendAnnouncementBtn.disabled = false; sendAnnouncementBtn.textContent = originalText;
                 return;
            }
            displayFeedback(actionsFeedback, 'Enviando...');
            try {
                const response = await fetchAdminAPI('actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'send_announcement', payload: { channel_id: channelId, message: message }})
                });
                displayFeedback(actionsFeedback, response.message || 'Enviado.');
                 if((response.status === 'success' || !response.error) && announcementMessageInput) announcementMessageInput.value = ''; 
            } catch (error) { displayFeedback(actionsFeedback, 'Erro de conexão ao enviar anúncio.', true); }
             finally { sendAnnouncementBtn.disabled = false; sendAnnouncementBtn.textContent = originalText; }
        });
    }

    if (addWatchlistForm) {
        addWatchlistForm.addEventListener('submit', handleAddWatchlist);
    }
    if (watchlistFilterName) watchlistFilterName.addEventListener('input', applyWatchlistFilter);
    if (watchlistFilterTag) watchlistFilterTag.addEventListener('input', applyWatchlistFilter);

    // =========================================================
    // DISCOHOOK EMBED EDITOR
    // =========================================================
    let dhEmbeds = [];
    let dhEmbedIdCounter = 0;
    const DH_COLOR_PRESETS = [
        '#5865f2', '#57f287', '#faa61a', '#ed4245', '#eb459e',
        '#ff73fa', '#00b0f4', '#4e5058', '#95ef1a', '#fee75c',
        '#b9bbbe', '#1abc9c', '#3498db', '#9b59b6', '#e67e22'
    ];

    function dhInitEditor() {
        const list = document.getElementById('dh-embeds-list');
        if (!list) return;
        dhEmbeds = [];
        dhEmbedIdCounter = 0;
        el('dh-add-embed-btn').onclick = () => dhAddEmbed();
        el('dh-clear-btn').onclick = dhClearAll;
        el('dh-export-json-btn').onclick = dhExportJSON;
        el('dh-import-json-btn').onclick = dhImportJSON;
        el('dh-example-btn').onclick = dhLoadExample;
        el('dh-send-btn').onclick = dhSendWebhook;
        el('dh-content').oninput = dhUpdatePreview;
        el('dh-webhook-url').oninput = function() {
            try { localStorage.setItem('dh_saved_webhook', this.value); } catch(e) {}
            dhFetchWebhookInfo(this.value.trim());
        };
        try {
            const saved = localStorage.getItem('dh_saved_webhook');
            if (saved) {
                el('dh-webhook-url').value = saved;
                dhFetchWebhookInfo(saved);
            }
        } catch(e) {}
    }

    function el(id) { return document.getElementById(id); }

    function dhFetchWebhookInfo(url) {
        var info = el('dh-webhook-info');
        var avatar = el('dh-webhook-avatar');
        var name = el('dh-webhook-name');
        var channel = el('dh-webhook-channel');
        if (!url || !url.match(/^https:\/\/(discord|discordapp)\.com\/api\/webhooks\//)) {
            info.style.display = 'none';
            return;
        }
        fetch(url, { method: 'GET', headers: { 'Accept': 'application/json' } })
            .then(function(r) { if (!r.ok) throw new Error(); return r.json(); })
            .then(function(d) {
                avatar.src = d.avatar
                    ? 'https://cdn.discordapp.com/avatars/' + d.id + '/' + d.avatar + '.png?size=32'
                    : 'https://cdn.discordapp.com/embed/avatars/0.png';
                name.textContent = d.name || 'Sem nome';
                channel.textContent = d.channel_id ? '#' + d.channel_id : '';
                info.style.display = 'flex';
            })
            .catch(function() { info.style.display = 'none'; });
    }

    function dhCreateId() { return ++dhEmbedIdCounter; }

    function dhAddEmbed(data) {
        const id = dhCreateId();
        const embed = {
            id, title: data?.title || '', description: data?.description || '',
            color: data?.color || '#5865f2', url: data?.url || '',
            author_name: data?.author_name || '', author_url: data?.author_url || '',
            author_icon_url: data?.author_icon_url || '',
            footer_text: data?.footer_text || '', footer_icon_url: data?.footer_icon_url || '',
            thumbnail_url: data?.thumbnail_url || '', image_url: data?.image_url || '',
            fields: data?.fields ? data.fields.map(f => ({ ...f })) : []
        };
        dhEmbeds.push(embed);
        dhRenderCard(embed);
        dhUpdatePreview();
    }

    function dhEsc(s) { return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

    function dhRenderCard(embed) {
        const container = el('dh-embeds-list');
        const idx = dhEmbeds.indexOf(embed);
        const card = document.createElement('div');
        card.className = 'dh-embed-card';
        card.id = 'dh-card-' + embed.id;
        const ec = dhEsc;
        card.innerHTML =
            '<div class="dh-embed-header" data-id="' + embed.id + '">' +
                '<div class="dh-embed-header-left">' +
                    '<span class="dh-embed-header-color" style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' + embed.color + '"></span>' +
                    'Embed #' + (idx + 1) +
                '</div>' +
                '<div class="dh-embed-header-actions">' +
                    '<button class="dh-mvup" title="↑">↑</button>' +
                    '<button class="dh-mvdn" title="↓">↓</button>' +
                    '<button class="dh-dub" title="⧉">⧉</button>' +
                    '<button class="dh-tog" title="−">−</button>' +
                    '<button class="dh-rm danger" title="✕">✕</button>' +
                '</div>' +
            '</div>' +
            '<div class="dh-embed-body">' +
                '<div class="dh-field-row">' +
                    '<div class="dh-field-group"><label>Title</label><input type="text" class="dh-fi-title" value="' + ec(embed.title) + '" placeholder="Título"></div>' +
                    '<div class="dh-field-group"><label>URL</label><input type="url" class="dh-fi-url" value="' + ec(embed.url) + '" placeholder="https://..."></div>' +
                '</div>' +
                '<div class="dh-field-group"><label>Description</label><textarea class="dh-fi-desc" rows="2" placeholder="Descrição">' + ec(embed.description) + '</textarea></div>' +
                '<div class="dh-field-row">' +
                    '<div class="dh-field-group"><label>Color</label>' +
                        '<div class="dh-color-input-wrap">' +
                            '<input type="color" class="dh-fi-color" value="' + embed.color + '">' +
                            '<input type="text" class="dh-fi-colortxt" value="' + embed.color + '" placeholder="#5865f2">' +
                        '</div>' +
                        '<div class="dh-color-presets">' + DH_COLOR_PRESETS.map(function(c) {
                            return '<div class="dh-color-preset' + (c === embed.color ? ' active' : '') + '" style="background:' + c + '" data-c="' + c + '"></div>';
                        }).join('') + '</div>' +
                    '</div>' +
                    '<div class="dh-field-group"><label>Thumbnail URL</label><input type="url" class="dh-fi-thumb" value="' + ec(embed.thumbnail_url) + '" placeholder="https://..."></div>' +
                '</div>' +
                '<div class="dh-field-row">' +
                    '<div class="dh-field-group"><label>Author Name</label><input type="text" class="dh-fi-aname" value="' + ec(embed.author_name) + '" placeholder="Nome"></div>' +
                    '<div class="dh-field-group"><label>Author URL</label><input type="url" class="dh-fi-aurl" value="' + ec(embed.author_url) + '" placeholder="https://..."></div>' +
                '</div>' +
                '<div class="dh-field-group"><label>Author Icon URL</label><input type="url" class="dh-fi-aicon" value="' + ec(embed.author_icon_url) + '" placeholder="https://..."></div>' +
                '<div class="dh-field-row">' +
                    '<div class="dh-field-group"><label>Footer Text</label><input type="text" class="dh-fi-ftext" value="' + ec(embed.footer_text) + '" placeholder="Texto"></div>' +
                    '<div class="dh-field-group"><label>Footer Icon URL</label><input type="url" class="dh-fi-ficon" value="' + ec(embed.footer_icon_url) + '" placeholder="https://..."></div>' +
                '</div>' +
                '<div class="dh-field-group"><label>Image URL</label><input type="url" class="dh-fi-img" value="' + ec(embed.image_url) + '" placeholder="https://..."></div>' +
                '<div class="dh-field-group"><label>Fields</label><div class="dh-fields-container" id="dh-fc-' + embed.id + '"></div><button class="dh-addf" data-id="' + embed.id + '">+ Add Field</button></div>' +
            '</div>';
        container.appendChild(card);

        var body = card.querySelector('.dh-embed-body');
        var hdr = card.querySelector('.dh-embed-header');

        hdr.querySelector('.dh-tog').onclick = function(e) { e.stopPropagation(); dhToggleBody(embed.id); };
        hdr.querySelector('.dh-rm').onclick = function(e) { e.stopPropagation(); dhRemove(embed.id); };
        hdr.querySelector('.dh-dub').onclick = function(e) { e.stopPropagation(); dhDuplicate(embed.id); };
        hdr.querySelector('.dh-mvup').onclick = function(e) { e.stopPropagation(); dhMove(embed.id, -1); };
        hdr.querySelector('.dh-mvdn').onclick = function(e) { e.stopPropagation(); dhMove(embed.id, 1); };
        hdr.onclick = function() { dhToggleBody(embed.id); };

        function dhBind(sel, key) {
            var el = card.querySelector(sel);
            if (el) el.oninput = function() { embed[key] = this.value; dhUpdateHeadColor(embed.id); dhUpdatePreview(); };
        }
        dhBind('.dh-fi-title', 'title');
        dhBind('.dh-fi-url', 'url');
        dhBind('.dh-fi-desc', 'description');
        dhBind('.dh-fi-color', 'color');
        dhBind('.dh-fi-colortxt', 'color');
        dhBind('.dh-fi-thumb', 'thumbnail_url');
        dhBind('.dh-fi-aname', 'author_name');
        dhBind('.dh-fi-aurl', 'author_url');
        dhBind('.dh-fi-aicon', 'author_icon_url');
        dhBind('.dh-fi-ftext', 'footer_text');
        dhBind('.dh-fi-ficon', 'footer_icon_url');
        dhBind('.dh-fi-img', 'image_url');

        card.querySelectorAll('.dh-color-preset').forEach(function(el) {
            el.onclick = function() {
                embed.color = this.dataset.c;
                var p = card.querySelector('.dh-fi-color');
                var t = card.querySelector('.dh-fi-colortxt');
                if (p) p.value = embed.color;
                if (t) t.value = embed.color;
                card.querySelectorAll('.dh-color-preset').forEach(function(x) { x.classList.remove('active'); });
                this.classList.add('active');
                dhUpdateHeadColor(embed.id);
                dhUpdatePreview();
            };
        });

        card.querySelector('.dh-addf').onclick = function() { dhAddField(embed.id); };
        embed.fields.forEach(function(f) { dhRenderField(embed.id, f); });
        dhUpdateHeadColor(embed.id);
    }

    function dhToggleBody(id) {
        var card = el('dh-card-' + id);
        if (!card) return;
        var body = card.querySelector('.dh-embed-body');
        var tog = card.querySelector('.dh-tog');
        if (!body || !tog) return;
        body.classList.toggle('collapsed');
        tog.textContent = body.classList.contains('collapsed') ? '+' : '−';
    }

    function dhRenderField(eid, field) {
        var container = el('dh-fc-' + eid);
        if (!container) return;
        var embed = dhEmbeds.find(function(e) { return e.id === eid; });
        if (!embed) return;
        var item = document.createElement('div');
        item.className = 'dh-field-item';
        item.innerHTML =
            '<input type="text" class="dh-fname" value="' + dhEsc(field.name) + '" placeholder="Nome">' +
            '<textarea class="dh-fval" rows="1" placeholder="Valor">' + dhEsc(field.value) + '</textarea>' +
            '<label class="dh-field-inline-label"><input type="checkbox" class="dh-finline"' + (field.inline ? ' checked' : '') + '><span>Inline</span></label>' +
            '<button class="dh-field-remove" title="✕">✕</button>';
        container.appendChild(item);
        item.querySelector('.dh-fname').oninput = function() { field.name = this.value; dhUpdatePreview(); };
        item.querySelector('.dh-fval').oninput = function() { field.value = this.value; dhUpdatePreview(); };
        item.querySelector('.dh-finline').onchange = function() { field.inline = this.checked; dhUpdatePreview(); };
        item.querySelector('.dh-field-remove').onclick = function() {
            embed.fields = embed.fields.filter(function(f) { return f !== field; });
            container.removeChild(item);
            dhUpdatePreview();
        };
    }

    function dhAddField(id) {
        var embed = dhEmbeds.find(function(e) { return e.id === id; });
        if (!embed) return;
        var field = { name: '', value: '', inline: false };
        embed.fields.push(field);
        dhRenderField(id, field);
        dhUpdatePreview();
    }

    function dhRemove(id) {
        dhEmbeds = dhEmbeds.filter(function(e) { return e.id !== id; });
        var card = el('dh-card-' + id);
        if (card) card.remove();
        dhRenumber();
        dhUpdatePreview();
    }

    function dhDuplicate(id) {
        var embed = dhEmbeds.find(function(e) { return e.id === id; });
        if (!embed) return;
        var clone = JSON.parse(JSON.stringify(embed));
        clone.id = dhCreateId();
        dhEmbeds.push(clone);
        dhRenderCard(clone);
        dhUpdatePreview();
    }

    function dhMove(id, dir) {
        var idx = dhEmbeds.findIndex(function(e) { return e.id === id; });
        if (idx === -1) return;
        var ni = idx + dir;
        if (ni < 0 || ni >= dhEmbeds.length) return;
        var tmp = dhEmbeds[idx]; dhEmbeds[idx] = dhEmbeds[ni]; dhEmbeds[ni] = tmp;
        el('dh-embeds-list').innerHTML = '';
        dhEmbeds.forEach(function(e) { dhRenderCard(e); });
        dhUpdatePreview();
    }

    function dhRenumber() {
        dhEmbeds.forEach(function(e, i) {
            var card = el('dh-card-' + e.id);
            if (!card) return;
            var left = card.querySelector('.dh-embed-header-left');
            if (left) left.innerHTML = '<span class="dh-embed-header-color" style="display:inline-block;width:10px;height:10px;border-radius:2px;background:' + e.color + '"></span> Embed #' + (i + 1);
        });
    }

    function dhUpdateHeadColor(id) {
        var e = dhEmbeds.find(function(x) { return x.id === id; });
        if (!e) return;
        var card = el('dh-card-' + id);
        if (!card) return;
        var dot = card.querySelector('.dh-embed-header-color');
        if (dot) dot.style.background = e.color;
        card.querySelectorAll('.dh-color-preset').forEach(function(p) { p.classList.toggle('active', p.dataset.c === e.color); });
    }

    function dhGetPayload() {
        var content = (el('dh-content').value || '');
        var embeds = dhEmbeds.map(function(e) {
            var obj = {};
            if (e.title) obj.title = e.title;
            if (e.description) obj.description = e.description;
            if (e.url) obj.url = e.url;
            if (e.color) obj.color = parseInt(e.color.replace('#', ''), 16);
            if (e.author_name) {
                obj.author = { name: e.author_name };
                if (e.author_url) obj.author.url = e.author_url;
                if (e.author_icon_url) obj.author.icon_url = e.author_icon_url;
            }
            if (e.footer_text) {
                obj.footer = { text: e.footer_text };
                if (e.footer_icon_url) obj.footer.icon_url = e.footer_icon_url;
            }
            if (e.thumbnail_url) obj.thumbnail = { url: e.thumbnail_url };
            if (e.image_url) obj.image = { url: e.image_url };
            if (e.fields && e.fields.length) {
                obj.fields = e.fields.map(function(f) { return { name: f.name || ' ', value: f.value || ' ', inline: !!f.inline }; });
            }
            return obj;
        }).filter(function(o) { return Object.keys(o).length > 0; });
        var p = {};
        if (content) p.content = content;
        if (embeds.length) p.embeds = embeds;
        return p;
    }

    function dhUpdatePreview() {
        var container = el('dh-preview-messages');
        if (!container) return;
        var content = (el('dh-content').value || '');
        var payload = dhGetPayload();

        var count = el('dh-content-count');
        if (count) {
            count.textContent = content.length + '/2000';
            count.className = 'dh-char-count';
            if (content.length > 2000) count.classList.add('exceed');
            else if (content.length > 1800) count.classList.add('warn');
        }

        if (!content && (!payload.embeds || !payload.embeds.length)) {
            container.innerHTML = '<div class="dh-preview-placeholder"><div style="font-size:3rem;margin-bottom:10px;opacity:0.3;"><svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg></div><div style="color:var(--color-text-secondary);">Preencha os dados ao lado para ver o preview</div></div>';
            return;
        }
        var html = '';
        if (content) html += '<div class="dh-msg-content">' + dhFormatContent(content) + '</div>';
        if (payload.embeds) payload.embeds.forEach(function(e) { html += dhRenderPreview(e); });
        container.innerHTML = html;
    }

    function dhFormatContent(t) {
        return dhEsc(t)
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/~~(.+?)~~/g, '<s>$1</s>')
            .replace(/__(.+?)__/g, '<u>$1</u>')
            .replace(/`(.+?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
            .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
    }

    function dhRenderPreview(embed) {
        var color = embed.color ? '#' + embed.color.toString(16).padStart(6, '0') : '#5865f2';
        var h = '<div class="dh-embed-preview"><div class="dh-embed-color" style="background:' + color + '"></div><div class="dh-embed-body-preview">';
        if (embed.thumbnail) h += '<div class="dh-embed-thumbnail"><img src="' + dhEsc(embed.thumbnail.url) + '" alt="" onerror="this.style.display=\'none\'"></div>';
        if (embed.author) {
            h += '<div class="dh-embed-author">';
            if (embed.author.icon_url) h += '<img src="' + dhEsc(embed.author.icon_url) + '" alt="" onerror="this.style.display=\'none\'">';
            h += '<span>';
            if (embed.author.url) h += '<a href="' + dhEsc(embed.author.url) + '" target="_blank" rel="noopener">';
            h += dhEsc(embed.author.name);
            if (embed.author.url) h += '</a>';
            h += '</span></div>';
        }
        if (embed.title) {
            h += '<div class="dh-embed-title">';
            if (embed.url) h += '<a href="' + dhEsc(embed.url) + '" target="_blank" rel="noopener">';
            h += dhEsc(embed.title);
            if (embed.url) h += '</a>';
            h += '</div>';
        }
        if (embed.description) h += '<div class="dh-embed-description">' + dhFormatContent(embed.description) + '</div>';
        if (embed.fields && embed.fields.length) {
            h += '<div class="dh-embed-fields">';
            embed.fields.forEach(function(f) {
                h += '<div class="dh-embed-field' + (f.inline ? ' inline' : '') + '"><div class="dh-embed-field-name">' + dhEsc(f.name) + '</div><div class="dh-embed-field-value">' + dhFormatContent(f.value) + '</div></div>';
            });
            h += '</div>';
        }
        if (embed.image) h += '<div class="dh-embed-image"><img src="' + dhEsc(embed.image.url) + '" alt="" onerror="this.style.display=\'none\'"></div>';
        if (embed.footer || embed.timestamp) {
            h += '<div class="dh-embed-footer">';
            if (embed.footer) {
                if (embed.footer.icon_url) h += '<img src="' + dhEsc(embed.footer.icon_url) + '" alt="" onerror="this.style.display=\'none\'">';
                h += '<span>' + dhEsc(embed.footer.text) + '</span>';
            }
            if (embed.timestamp) {
                var ts = new Date(embed.timestamp);
                if (!isNaN(ts)) h += '<span class="dh-embed-timestamp">' + ts.toLocaleDateString('pt-BR') + '</span>';
            }
            h += '</div>';
        }
        h += '</div></div>';
        return h;
    }

    async function dhSendWebhook() {
        var url = el('dh-webhook-url').value.trim();
        var fb = el('dh-feedback');
        if (!url) { fb.className = 'dh-send-status error'; fb.textContent = 'Insira uma URL de Webhook primeiro.'; return; }
        var payload = dhGetPayload();
        if (!payload.content && (!payload.embeds || !payload.embeds.length)) {
            fb.className = 'dh-send-status error'; fb.textContent = 'Adicione conteúdo ou pelo menos um embed.'; return;
        }
        var btn = el('dh-send-btn');
        var orig = btn.textContent;
        btn.textContent = 'Enviando...'; btn.disabled = true;
        fb.className = 'dh-send-status loading'; fb.textContent = 'Enviando...';
        try {
            var r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            if (r.ok) {
                fb.className = 'dh-send-status success';
                fb.textContent = 'Mensagem enviada com sucesso!';
            } else {
                var err = await r.text().catch(function() { return 'Erro desconhecido'; });
                fb.className = 'dh-send-status error';
                fb.textContent = 'Erro ' + r.status + ': ' + err.substring(0, 200);
            }
        } catch (err) {
            fb.className = 'dh-send-status error';
            fb.textContent = 'Falha: ' + err.message;
        }
        btn.textContent = orig; btn.disabled = false;
    }

    function dhClearAll() {
        el('dh-content').value = '';
        el('dh-embeds-list').innerHTML = '';
        dhEmbeds = []; dhEmbedIdCounter = 0;
        el('dh-feedback').textContent = ''; el('dh-feedback').className = '';
        dhUpdatePreview();
    }

    function dhExportJSON() { dhShowModal('Exportar JSON', JSON.stringify(dhGetPayload(), null, 2), false); }
    function dhImportJSON() { dhShowModal('Importar JSON', '', true); }

    function dhShowModal(title, json, isImport) {
        var old = document.querySelector('.dh-modal-overlay');
        if (old) old.remove();
        var ov = document.createElement('div');
        ov.className = 'dh-modal-overlay';
        ov.innerHTML = '<div class="dh-modal"><h3>' + title + '</h3><textarea id="dh-json-ta"' + (isImport ? ' placeholder="Cole o JSON..."' : '') + '>' + dhEsc(json) + '</textarea><div class="dh-modal-actions"><button class="dh-mc">Cancelar</button>' + (isImport ? '<button class="dh-mi primary">Importar</button>' : '<button class="dh-mcp primary">Copiar</button>') + '</div></div>';
        document.body.appendChild(ov);
        ov.querySelector('.dh-mc').onclick = function() { ov.remove(); };
        ov.onclick = function(e) { if (e.target === ov) ov.remove(); };
        if (isImport) {
            ov.querySelector('.dh-mi').onclick = function() {
                try {
                    var data = JSON.parse(el('dh-json-ta').value);
                    dhImportPayload(data); ov.remove();
                } catch (e) { alert('JSON inválido: ' + e.message); }
            };
        } else {
            ov.querySelector('.dh-mcp').onclick = function() {
                var ta = el('dh-json-ta'); ta.select();
                try { document.execCommand('copy'); } catch(e) {}
                this.textContent = 'Copiado!';
                setTimeout(function() { ov.remove(); }, 800);
            };
        }
    }

    function dhImportPayload(data) {
        el('dh-embeds-list').innerHTML = '';
        dhEmbeds = []; dhEmbedIdCounter = 0;
        if (data.content) el('dh-content').value = data.content;
        if (data.embeds && Array.isArray(data.embeds)) {
            data.embeds.forEach(function(ed) {
                dhAddEmbed({
                    title: ed.title || '', description: ed.description || '',
                    color: ed.color ? '#' + ed.color.toString(16).padStart(6, '0') : '#5865f2',
                    url: ed.url || '', author_name: (ed.author && ed.author.name) || '',
                    author_url: (ed.author && ed.author.url) || '', author_icon_url: (ed.author && ed.author.icon_url) || '',
                    footer_text: (ed.footer && ed.footer.text) || '', footer_icon_url: (ed.footer && ed.footer.icon_url) || '',
                    thumbnail_url: (ed.thumbnail && ed.thumbnail.url) || '', image_url: (ed.image && ed.image.url) || '',
                    fields: (ed.fields || []).map(function(f) { return { name: f.name || '', value: f.value || '', inline: !!f.inline }; })
                });
            });
        }
        dhUpdatePreview();
    }

    function dhLoadExample() {
        dhClearAll();
        el('dh-content').value = 'Bem-vindo ao **DiscoHook**!\n\nUse este editor para criar mensagens personalizadas com embeds ricos.';
        dhAddEmbed({
            title: 'O que é isso?',
            description: 'Editor visual de embeds do Discord. Crie mensagens estilizadas com cores, campos, imagens e envie via Webhook.',
            color: '#58b9ff', author_name: 'DiscoHook', footer_text: 'Criado com DiscoHook',
            fields: [
                { name: 'Content', value: 'Texto acima dos embeds', inline: true },
                { name: 'Embeds', value: 'Mensagens ricas formatadas', inline: true },
                { name: 'Webhook', value: 'Envie para qualquer canal', inline: false }
            ]
        });
        dhAddEmbed({
            title: 'Discord Bot', description: 'Bot complementar para formatação, reaction roles e restauração.',
            color: '#5865f2',
            fields: [
                { name: '/format', value: 'Formatação especial', inline: true },
                { name: '/reaction-role', value: 'Cargos por reação', inline: true }
            ]
        });
        dhUpdatePreview();
        el('dh-feedback').className = ''; el('dh-feedback').textContent = '';
    }

    // Inicializa o DiscoHook imediatamente
    dhInitEditor();

    // Initial load
    loadDataForCurrentTab();
    initTooltips();

    // ==================== USER MANAGEMENT ====================
    async function loadPendingUsers() {
        const container = document.getElementById('pending-users-list');
        if (!container) return;
        try {
            const data = await fetchAdminAPI('auth/pending');
            if (!data || data.length === 0) {
                container.innerHTML = '<p style="color:var(--color-text-secondary);font-style:italic;">Nenhuma solicitação pendente.</p>';
                return;
            }
            container.innerHTML = data.map(u => `
                <div style="display:flex;align-items:center;justify-content:space-between;padding:10px;margin-bottom:8px;background:rgba(0,0,0,0.3);border:1px solid rgba(255,215,0,0.2);border-radius:6px;">
                    <div>
                        <strong style="color:var(--neon-orange);">${escapeHtml(u.username)}</strong>
                        ${u.discord ? `<span style="color:var(--color-text-secondary);margin-left:10px;">${escapeHtml(u.discord)}</span>` : ''}
                        <span style="color:var(--color-text-secondary);font-size:0.85em;margin-left:10px;">${new Date(u.created_at).toLocaleString('pt-BR')}</span>
                    </div>
                    <div>
                        <button onclick="approveUser('${escapeHtml(u.username)}')" style="background:rgba(46,204,113,0.2);border:1px solid #2ecc71;color:#2ecc71;padding:6px 15px;border-radius:4px;cursor:pointer;margin-right:5px;font-family:'Rajdhani',sans-serif;font-weight:600;">✓ Aprovar</button>
                        <button onclick="rejectUser('${escapeHtml(u.username)}')" style="background:rgba(231,76,60,0.2);border:1px solid #e74c3c;color:#e74c3c;padding:6px 15px;border-radius:4px;cursor:pointer;font-family:'Rajdhani',sans-serif;font-weight:600;">✕ Rejeitar</button>
                    </div>
                </div>
            `).join('');
        } catch(e) {
            container.innerHTML = `<p class="error-text">Erro ao carregar: ${escapeHtml(e.message)}</p>`;
        }
    }

    async function loadActiveUsers() {
        const container = document.getElementById('active-users-list');
        if (!container) return;
        try {
            const data = await fetchAdminAPI('auth/users');
            if (!data || data.length === 0) {
                container.innerHTML = '<p style="color:var(--color-text-secondary);font-style:italic;">Nenhum usuário cadastrado.</p>';
                return;
            }
            const active = data.filter(u => u.status === 'active');
            if (active.length === 0) {
                container.innerHTML = '<p style="color:var(--color-text-secondary);font-style:italic;">Nenhum usuário ativo.</p>';
                return;
            }
            container.innerHTML = `
                <table style="width:100%;border-collapse:collapse;">
                    <thead>
                        <tr style="border-bottom:1px solid rgba(0,255,249,0.2);">
                            <th style="padding:8px;text-align:left;color:var(--color-text-secondary);font-size:0.85em;">Usuário</th>
                            <th style="padding:8px;text-align:left;color:var(--color-text-secondary);font-size:0.85em;">Tipo</th>
                            <th style="padding:8px;text-align:left;color:var(--color-text-secondary);font-size:0.85em;">Discord</th>
                            <th style="padding:8px;text-align:left;color:var(--color-text-secondary);font-size:0.85em;">Criado em</th>
                            <th style="padding:8px;text-align:left;color:var(--color-text-secondary);font-size:0.85em;">Ação</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${active.map(u => `
                            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                                <td style="padding:8px;font-weight:600;">${escapeHtml(u.username)}</td>
                                <td style="padding:8px;"><span style="padding:2px 8px;border-radius:3px;font-size:0.85em;background:${u.role === 'admin' ? 'rgba(0,255,249,0.15)' : 'rgba(255,165,0,0.15)'};color:${u.role === 'admin' ? 'var(--neon-cyan)' : 'var(--neon-orange)'};">${u.role === 'admin' ? 'Admin' : 'Membro Sênior'}</span></td>
                                <td style="padding:8px;color:var(--color-text-secondary);">${escapeHtml(u.discord || '-')}</td>
                                <td style="padding:8px;color:var(--color-text-secondary);font-size:0.85em;">${u.created_at ? new Date(u.created_at).toLocaleString('pt-BR') : '-'}</td>
                                <td style="padding:8px;">
                                    <select onchange="changeUserRole('${escapeHtml(u.username)}', this.value)" style="background:rgba(0,0,0,0.5);border:1px solid rgba(255,255,255,0.2);color:#fff;padding:4px 8px;border-radius:4px;font-family:'Rajdhani',sans-serif;font-size:0.85em;">
                                        <option value="admin" ${u.role === 'admin' ? 'selected' : ''}>Admin</option>
                                        <option value="viewer" ${u.role === 'viewer' ? 'selected' : ''}>Membro Sênior</option>
                                    </select>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                <p style="color:var(--color-text-secondary);font-size:0.85em;margin-top:10px;">Total: ${active.length} usuário(s) ativo(s)</p>
            `;
        } catch(e) {
            container.innerHTML = `<p class="error-text">Erro ao carregar: ${escapeHtml(e.message)}</p>`;
        }
    }

    window.approveUser = async function(username) {
        const fb = document.getElementById('users-feedback');
        if (!fb) return;
        try {
            const data = await fetchAdminAPI('auth/approve/' + encodeURIComponent(username), {method: 'POST'});
            fb.textContent = data.message || 'Aprovado!';
            fb.className = 'feedback-text success';
            await loadPendingUsers();
            await loadActiveUsers();
        } catch(e) {
            fb.textContent = 'Erro: ' + e.message;
            fb.className = 'feedback-text error';
        }
    };

    window.rejectUser = async function(username) {
        const fb = document.getElementById('users-feedback');
        if (!fb) return;
        try {
            const data = await fetchAdminAPI('auth/reject/' + encodeURIComponent(username), {method: 'POST'});
            fb.textContent = data.message || 'Rejeitado!';
            fb.className = 'feedback-text success';
            await loadPendingUsers();
        } catch(e) {
            fb.textContent = 'Erro: ' + e.message;
            fb.className = 'feedback-text error';
        }
    };

    window.changeUserRole = async function(username, newRole) {
        const fb = document.getElementById('users-feedback');
        if (!fb) return;
        fb.textContent = 'Alterando role...';
        fb.className = 'feedback-text';
        try {
            const data = await fetchAdminAPI('auth/role', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username, role: newRole})
            });
            fb.textContent = data.message || 'Role alterada!';
            fb.className = 'feedback-text success';
            await loadActiveUsers();
        } catch(e) {
            fb.textContent = 'Erro: ' + e.message;
            fb.className = 'feedback-text error';
        }
    };
});
