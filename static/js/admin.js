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
                icon = "⛔";
                colorClass = "alert-critical";
                message = `Atenção: O membro <strong>${member.name}</strong> violou a diretriz principal do clã. O sistema forense registra exatos <strong>${diffDays} dias</strong> sem qualquer participação no campo de guerra. Remoção recomendada.`;
            } else if (diffDays >= 22) {
                alertType = "ALERTA VERMELHO (22+ dias)";
                icon = "🚨";
                colorClass = "alert-danger";
                message = `Risco altíssimo de desligamento: A conta de <strong>${member.name}</strong> está congelada há <strong>${diffDays} dias</strong>. Sugere-se intervenção imediata da liderança para cobrança.`;
            } else {
                alertType = "ATENÇÃO TÁTICA (15+ dias)";
                icon = "🎯";
                colorClass = "alert-warning";
                message = `A conta <strong>${member.name}</strong> acaba de entrar no radar de ociosidade. A nossa telemetria aponta <strong>${diffDays} dias</strong> sem se voluntariar para o confronto.`;
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
                <div style="font-size: 3rem; margin-bottom: 10px;">✅</div>
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

// Dispara a leitura assim que a página carrega
window.fetchRadarInactivityData();
setInterval(window.fetchRadarInactivityData, 30 * 60 * 1000);

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
    async function fetchAdminAPI(endpoint, options = {}) {
        const isPostWithoutBodyResponse = options.method === 'POST' && (endpoint.startsWith('watchlist/') || endpoint === 'actions' || endpoint === 'settings');

        try {
            const response = await fetch(`/api/admin/${endpoint}`, options);

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

        const channelSelects = ['channel_id', 'post_war_analysis_channel_id', 'post_war_verdict_channel_id', 'clan_games_channel_id', 'cwl_planner_channel_id', 'donations_channel_id', 'watchlist_alert_channel_id', 'low_performance_channel_id', 'capital_report_channel_id', 'smurf_log_channel_id', 'maintenance_alert_channel_id'];
        const roleSelects = ['role_id_1star_alert', 'role_id_missed_attack', 'leader_role_id', 'coleader_role_id'];

        channelSelects.forEach(id => {
            const select = document.getElementById(id);
            if (select && discordData.channels) {
                select.innerHTML = '<option value="0">Nenhum / Desativado</option>' + 
                    discordData.channels.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
            }
        });

        roleSelects.forEach(id => {
            const select = document.getElementById(id);
            if (select && discordData.roles) {
                select.innerHTML = '<option value="0">Nenhum / Desativado</option>' + 
                    discordData.roles.map(r => `<option value="${r.id}">${r.name}</option>`).join('');
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
             td.onclick = () => {
                 const textArea = document.createElement("textarea");
                 textArea.value = text;
                 document.body.appendChild(textArea);
                 textArea.select();
                 try {
                     const successful = document.execCommand('copy');
                     if(successful){
                         const originalText = td.textContent;
                         td.textContent = 'Copiado!';
                         setTimeout(() => { td.textContent = originalText; }, 1500);
                     } else { throw new Error('execCommand failed'); }
                 } catch (err) { console.error('Falha ao copiar ID:', err); }
                 document.body.removeChild(textArea);
             };
             return td;
         };

        if(dbWarsTableBody && Array.isArray(data.last_wars)) { 
            dbWarsTableBody.innerHTML = data.last_wars.length > 0
                ? data.last_wars.map(w => {
                     const row = document.createElement('tr');
                     row.innerHTML = `<td>${w.opponent || 'N/A'}</td><td>${formatDbDate(w.end_time)}</td>`;
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
                        <td>${n.player_tag || 'N/A'}</td>
                        <td>${n.note || '-'}</td>
                        <td class="priority-cell priority-${n.priority || 'none'}">${n.priority || 'none'}</td>
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
                 watchlistTableBody.innerHTML = `<tr><td colspan="6" class="error-text">Erro: ${response.error}</td></tr>`;
                 displayFeedback(watchlistListFeedback, `Erro: ${response.error}`, true);
                 return;
            }
            const watchlist = Array.isArray(response) ? response : [];

            if (watchlist.length === 0) {
                 watchlistTableBody.innerHTML = '<tr><td colspan="6">Nenhum jogador na lista de observação.</td></tr>';
                 return;
            }
            watchlistTableBody.innerHTML = watchlist.map(player => {
                let dateStr = '-';
                if (player.date_added) {
                     try { dateStr = new Date(player.date_added).toLocaleDateString('pt-BR'); }
                     catch(e) { dateStr = player.date_added; } 
                }
                return `
                <tr>
                    <td><strong>${player.name || 'N/A'}</strong></td>
                    <td style="font-family: monospace; color: var(--color-accent);">${player._id || 'N/A'}</td>
                    <td>${player.reason || '-'}</td>
                    <td>${player.details || '-'}</td>
                    <td>${dateStr}</td>
                    <td><button class="admin-remove-btn btn-admin btn-danger" data-tag="${player._id || ''}" style="padding: 5px 10px;">Remover</button></td>
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
        } catch (error) {}
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
                 button.disabled = false; 
                 button.textContent = 'Remover';
             }
        } catch (error) {
           button.disabled = false; 
           button.textContent = 'Remover';
        }
    }

    // =========================================================
    // RENDERIZADOR XAI (EXPLAINABLE AI) - TERMINAL FORENSE
    // =========================================================
    async function loadRadarDossier() {
        const container = document.getElementById('radar-dossier-container');
        if(!container) return;
        container.innerHTML = '<div style="text-align:center;"><div class="loading-spinner" style="margin: 20px auto;"></div><p style="color:var(--color-text-secondary);font-family:monospace;margin-top:10px;">Executando DBSCAN e Varredura Forense ao vivo...</p></div>';
        
        try {
            const response = await fetchAdminAPI('actions', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'get_smurf_dossier', payload: {}})
            });
            
            if(response && response.error) {
                container.innerHTML = `<p class="error-text">${response.error}</p>`;
                return;
            }
            
            let dossier = [];
            if (Array.isArray(response)) {
                dossier = response;
            } else if (response && Array.isArray(response.dossier)) {
                dossier = response.dossier;
            } else if (response && Array.isArray(response.data)) {
                dossier = response.data;
            } else if (response && Array.isArray(response.message)) {
                dossier = response.message;
            }
            
            if(dossier.length === 0) {
                container.innerHTML = `
                <div style="text-align:center; padding: 30px; background: rgba(46, 204, 113, 0.05); border: 1px solid rgba(46, 204, 113, 0.2); border-radius: 8px;">
                    <h3 style="color: var(--color-success); margin-bottom:10px;">🛡️ Clã Limpo (Status Verde)</h3>
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
                            weightBadge = `<span style="display:inline-block; padding: 2px 6px; background: rgba(255,255,255,0.1); border-radius:3px; margin-right: 8px; font-weight:bold; color: ${color};">[Peso: ${t.weight}]</span>`;
                        } else {
                            weightBadge = `<span style="display:inline-block; padding: 2px 6px; background: rgba(255,255,255,0.1); border-radius:3px; margin-right: 8px; color: #a0aec0;">[${t.axis}]</span>`;
                        }
                        terminalHtml += `<div style="margin-bottom: 8px; padding-left: 10px; border-left: 2px solid ${color}55;">${weightBadge} <span style="color: #e2e8f0;">${t.text}</span></div>`;
                    });
                }
                
                html += `
                <div style="background: rgba(0,0,0,0.25); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                    <div style="padding: 15px 20px; background: linear-gradient(90deg, ${color}22 0%, transparent 100%); border-bottom: 1px solid ${color}44; display:flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-size: 0.75em; text-transform: uppercase; letter-spacing: 1px; color: ${color}; font-weight: bold;">Identificação XAI</span>
                            <h4 style="margin: 5px 0 0 0; font-size: 1.2em; display:flex; align-items:center; gap: 10px;">
                                👑 ${doc.main_name} <span style="font-size:0.7em; color:var(--color-text-secondary);">${doc.main_tag}</span>
                                <span style="color:${color};">↔️</span>
                                👶 ${doc.smurf_name} <span style="font-size:0.7em; color:var(--color-text-secondary);">${doc.smurf_tag}</span>
                            </h4>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 1.8em; font-weight: 900; color: ${color}; line-height: 1;">${doc.confidence}%</div>
                            <div style="font-size: 0.8em; color: var(--color-text-secondary); text-transform:uppercase;">${doc.risk_label}</div>
                        </div>
                    </div>
                    
                    <div style="height: 4px; background: rgba(255,255,255,0.05); width: 100%;">
                        <div style="height: 100%; width: ${doc.confidence}%; background: ${color}; box-shadow: 0 0 10px ${color};"></div>
                    </div>
                    
                    <div style="padding: 20px;">
                        <div style="margin-bottom: 8px; font-size: 0.85em; color: var(--color-text-secondary); text-transform:uppercase; font-weight:bold; letter-spacing: 1px;">🧠 Motor de Inferência (Cadeia Lógica)</div>
                        <div style="background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px; padding: 15px; font-family: 'Courier New', monospace; font-size: 0.9em; line-height: 1.5; max-height: 250px; overflow-y: auto;">
                            ${terminalHtml}
                        </div>
                    </div>
                    
                    <div style="padding: 15px 20px; background: rgba(0,0,0,0.2); border-top: 1px solid rgba(255,255,255,0.05); display: flex; gap: 15px;">
                        <button onclick="judgeSmurf('${doc.pair_id}', 'absolve_smurf')" class="btn-admin" style="background: rgba(46, 204, 113, 0.15); color: #2ecc71; border: 1px solid #2ecc71; flex: 1; transition: all 0.2s;">🟢 Falso Positivo (Limpar)</button>
                        <button onclick="judgeSmurf('${doc.pair_id}', 'condemn_smurf')" class="btn-admin" style="background: rgba(231, 76, 60, 0.15); color: #e74c3c; border: 1px solid #e74c3c; flex: 1; transition: all 0.2s;">🔴 Condenar p/ Watchlist</button>
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
            ? '⚠️ TEM CERTEZA?\n\nA Matriz Forense enviará ambas as contas para a Watchlist como "Smurfs Confirmadas" e apagará o dossiê da tela principal.' 
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
                    <td><strong>${m.name}</strong></td>
                    <td style="font-family: monospace; color: var(--color-accent);">${m.tag}</td>
                    <td style="font-weight: bold;">${tier}</td>
                    <td style="color: ${probColor}; font-weight: 900; font-size: 1.1em;">${prob}</td>
                    <td>${wars} / 50</td>
                </tr>`;
            }).join('');

        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="5" class="error-text">Erro ao carregar Analytics: ${error.message}</td></tr>`;
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
                     initDiscoHook();
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
            } catch(error) { }
        });
    }

    document.querySelectorAll('.action-btn').forEach(button => {
        button.addEventListener('click', async () => {
             let originalText = button.textContent;
             button.disabled = true; button.textContent = 'Executando...';
            const action = button.dataset.action;
            const payload = JSON.parse(button.dataset.payload || '{}'); 
            displayFeedback(actionsFeedback, `Executando ${action}...`);
            try {
                const response = await fetchAdminAPI('actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action, payload })
                });
                displayFeedback(actionsFeedback, response.message || `Ação '${action}' concluída.`);
            } catch (error) {}
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
            } catch (error) {}
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
    let dhInitialized = false;
    const DH_COLOR_PRESETS = [
        '#5865f2', '#57f287', '#faa61a', '#ed4245', '#eb459e',
        '#ff73fa', '#00b0f4', '#4e5058', '#95ef1a', '#fee75c',
        '#b9bbbe', '#1abc9c', '#3498db', '#9b59b6', '#e67e22'
    ];

    window.initDiscoHook = function() {
        if (dhInitialized) return;
        dhInitialized = true;

        if (!document.getElementById('dh-embeds-list')) return;

        dhEmbeds = [];
        dhEmbedIdCounter = 0;

        document.getElementById('dh-add-embed-btn').addEventListener('click', () => addDhEmbed());
        document.getElementById('dh-clear-btn').addEventListener('click', clearDhAll);
        document.getElementById('dh-export-json-btn').addEventListener('click', exportDhJSON);
        document.getElementById('dh-import-json-btn').addEventListener('click', importDhJSON);
        document.getElementById('dh-example-btn').addEventListener('click', loadDhExample);
        document.getElementById('dh-send-btn').addEventListener('click', sendDhWebhook);
        document.getElementById('dh-content').addEventListener('input', updateDhPreview);
        document.getElementById('dh-webhook-url').addEventListener('input', () => {
            localStorage.setItem('dh_saved_webhook', document.getElementById('dh-webhook-url').value);
        });

        const savedWebhook = localStorage.getItem('dh_saved_webhook');
        if (savedWebhook) document.getElementById('dh-webhook-url').value = savedWebhook;
    };

    function dhCreateEmbedId() { return ++dhEmbedIdCounter; }

    function addDhEmbed(data) {
        const id = dhCreateEmbedId();
        const embed = {
            id,
            title: data?.title || '',
            description: data?.description || '',
            color: data?.color || '#5865f2',
            author_name: data?.author_name || '',
            author_url: data?.author_url || '',
            author_icon_url: data?.author_icon_url || '',
            footer_text: data?.footer_text || '',
            footer_icon_url: data?.footer_icon_url || '',
            thumbnail_url: data?.thumbnail_url || '',
            image_url: data?.image_url || '',
            fields: data?.fields ? data.fields.map(f => ({ ...f })) : [],
            url: data?.url || ''
        };
        dhEmbeds.push(embed);
        renderDhEmbedCard(embed);
        updateDhPreview();
    }

    function renderDhEmbedCard(embed) {
        const container = document.getElementById('dh-embeds-list');
        const card = document.createElement('div');
        card.className = 'dh-embed-card';
        card.id = `dh-embed-card-${embed.id}`;
        card.innerHTML = `
            <div class="dh-embed-header" data-id="${embed.id}">
                <div class="dh-embed-header-left">
                    <span class="dh-embed-header-color" style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${embed.color}"></span>
                    Embed #${dhEmbeds.indexOf(embed) + 1}
                </div>
                <div class="dh-embed-header-actions">
                    <button class="dh-move-up" title="Mover para cima">↑</button>
                    <button class="dh-move-down" title="Mover para baixo">↓</button>
                    <button class="dh-duplicate" title="Duplicar">⧉</button>
                    <button class="dh-toggle-body" title="Expandir/Recolher">−</button>
                    <button class="dh-remove danger" title="Remover">✕</button>
                </div>
            </div>
            <div class="dh-embed-body">
                <div class="dh-field-row">
                    <div class="dh-field-group">
                        <label>Title</label>
                        <input type="text" class="dh-embed-title-input" value="${escapeHtml(embed.title)}" placeholder="Título do embed">
                    </div>
                    <div class="dh-field-group">
                        <label>URL (link do título)</label>
                        <input type="url" class="dh-embed-url-input" value="${escapeHtml(embed.url)}" placeholder="https://...">
                    </div>
                </div>
                <div class="dh-field-group">
                    <label>Description</label>
                    <textarea class="dh-embed-desc-input" rows="2" placeholder="Descrição do embed">${escapeHtml(embed.description)}</textarea>
                </div>
                <div class="dh-field-row">
                    <div class="dh-field-group">
                        <label>Color</label>
                        <div class="dh-color-input-wrap">
                            <input type="color" class="dh-embed-color-picker" value="${embed.color}">
                            <input type="text" class="dh-embed-color-text" value="${embed.color}" placeholder="#5865f2">
                        </div>
                        <div class="dh-color-presets">${DH_COLOR_PRESETS.map(c =>
                            `<div class="dh-color-preset ${c === embed.color ? 'active' : ''}" style="background:${c}" data-color="${c}"></div>`
                        ).join('')}</div>
                    </div>
                    <div class="dh-field-group">
                        <label>Thumbnail URL</label>
                        <input type="url" class="dh-embed-thumb-input" value="${escapeHtml(embed.thumbnail_url)}" placeholder="https://...">
                    </div>
                </div>
                <div class="dh-field-row">
                    <div class="dh-field-group">
                        <label>Author Name</label>
                        <input type="text" class="dh-embed-author-name-input" value="${escapeHtml(embed.author_name)}" placeholder="Nome do autor">
                    </div>
                    <div class="dh-field-group">
                        <label>Author URL</label>
                        <input type="url" class="dh-embed-author-url-input" value="${escapeHtml(embed.author_url)}" placeholder="https://...">
                    </div>
                </div>
                <div class="dh-field-group">
                    <label>Author Icon URL</label>
                    <input type="url" class="dh-embed-author-icon-input" value="${escapeHtml(embed.author_icon_url)}" placeholder="https://...">
                </div>
                <div class="dh-field-row">
                    <div class="dh-field-group">
                        <label>Footer Text</label>
                        <input type="text" class="dh-embed-footer-text-input" value="${escapeHtml(embed.footer_text)}" placeholder="Texto do footer">
                    </div>
                    <div class="dh-field-group">
                        <label>Footer Icon URL</label>
                        <input type="url" class="dh-embed-footer-icon-input" value="${escapeHtml(embed.footer_icon_url)}" placeholder="https://...">
                    </div>
                </div>
                <div class="dh-field-group">
                    <label>Image URL</label>
                    <input type="url" class="dh-embed-image-input" value="${escapeHtml(embed.image_url)}" placeholder="https://...">
                </div>
                <div class="dh-field-group">
                    <label>Fields</label>
                    <div class="dh-fields-container" id="dh-fields-${embed.id}"></div>
                    <button class="dh-add-field-btn" data-id="${embed.id}">+ Add Field</button>
                </div>
            </div>
        `;

        container.appendChild(card);

        const body = card.querySelector('.dh-embed-body');
        const header = card.querySelector('.dh-embed-header');

        header.querySelector('.dh-toggle-body').addEventListener('click', (e) => {
            e.stopPropagation();
            body.classList.toggle('collapsed');
            header.querySelector('.dh-toggle-body').textContent = body.classList.contains('collapsed') ? '+' : '−';
        });

        header.querySelector('.dh-remove').addEventListener('click', (e) => {
            e.stopPropagation();
            removeDhEmbed(embed.id);
        });

        header.querySelector('.dh-duplicate').addEventListener('click', (e) => {
            e.stopPropagation();
            duplicateDhEmbed(embed.id);
        });

        header.querySelector('.dh-move-up').addEventListener('click', (e) => {
            e.stopPropagation();
            moveDhEmbed(embed.id, -1);
        });

        header.querySelector('.dh-move-down').addEventListener('click', (e) => {
            e.stopPropagation();
            moveDhEmbed(embed.id, 1);
        });

        header.addEventListener('click', () => {
            body.classList.toggle('collapsed');
            header.querySelector('.dh-toggle-body').textContent = body.classList.contains('collapsed') ? '+' : '−';
        });

        const idx = dhEmbeds.findIndex(e => e.id === embed.id);
        const embedRef = dhEmbeds[idx];

        const bindInput = (selector, key, transform) => {
            const el = card.querySelector(selector);
            if (!el) return;
            el.addEventListener('input', () => {
                embedRef[key] = transform ? transform(el.value) : el.value;
                updateHeaderColor(embed.id);
                updateDhPreview();
            });
        };

        bindInput('.dh-embed-title-input', 'title');
        bindInput('.dh-embed-url-input', 'url');
        bindInput('.dh-embed-desc-input', 'description');
        bindInput('.dh-embed-color-picker', 'color');
        bindInput('.dh-embed-color-text', 'color');
        bindInput('.dh-embed-thumb-input', 'thumbnail_url');
        bindInput('.dh-embed-author-name-input', 'author_name');
        bindInput('.dh-embed-author-url-input', 'author_url');
        bindInput('.dh-embed-author-icon-input', 'author_icon_url');
        bindInput('.dh-embed-footer-text-input', 'footer_text');
        bindInput('.dh-embed-footer-icon-input', 'footer_icon_url');
        bindInput('.dh-embed-image-input', 'image_url');

        card.querySelectorAll('.dh-color-preset').forEach(el => {
            el.addEventListener('click', () => {
                const color = el.dataset.color;
                embedRef.color = color;
                const picker = card.querySelector('.dh-embed-color-picker');
                const text = card.querySelector('.dh-embed-color-text');
                if (picker) picker.value = color;
                if (text) text.value = color;
                card.querySelectorAll('.dh-color-preset').forEach(p => p.classList.remove('active'));
                el.classList.add('active');
                updateHeaderColor(embed.id);
                updateDhPreview();
            });
        });

        card.querySelector('.dh-add-field-btn').addEventListener('click', () => {
            addDhField(embed.id);
        });

        embedRef.fields.forEach(f => {
            renderDhField(embed.id, f);
        });

        updateHeaderColor(embed.id);
    }

    function renderDhField(embedId, field) {
        const container = document.getElementById(`dh-fields-${embedId}`);
        if (!container) return;
        const idx = dhEmbeds.find(e => e.id === embedId).fields.indexOf(field);
        const item = document.createElement('div');
        item.className = 'dh-field-item';
        item.dataset.fieldIdx = idx;
        item.innerHTML = `
            <input type="text" class="dh-field-name" value="${escapeHtml(field.name || '')}" placeholder="Nome">
            <textarea class="dh-field-value" rows="1" placeholder="Valor">${escapeHtml(field.value || '')}</textarea>
            <label class="dh-field-inline-label">
                <input type="checkbox" class="dh-field-inline" ${field.inline ? 'checked' : ''}>
                <span>Inline</span>
            </label>
            <button class="dh-field-remove" title="Remover campo">✕</button>
        `;

        container.appendChild(item);

        const embedRef = dhEmbeds.find(e => e.id === embedId);
        const fieldRef = embedRef.fields.find(f => f === field);

        item.querySelector('.dh-field-name').addEventListener('input', (e) => {
            fieldRef.name = e.target.value;
            updateDhPreview();
        });
        item.querySelector('.dh-field-value').addEventListener('input', (e) => {
            fieldRef.value = e.target.value;
            updateDhPreview();
        });
        item.querySelector('.dh-field-inline').addEventListener('change', (e) => {
            fieldRef.inline = e.target.checked;
            updateDhPreview();
        });
        item.querySelector('.dh-field-remove').addEventListener('click', () => {
            embedRef.fields = embedRef.fields.filter(f => f !== fieldRef);
            container.removeChild(item);
            updateDhPreview();
        });
    }

    function addDhField(embedId) {
        const embedRef = dhEmbeds.find(e => e.id === embedId);
        if (!embedRef) return;
        const field = { name: '', value: '', inline: false };
        embedRef.fields.push(field);
        renderDhField(embedId, field);
        updateDhPreview();
    }

    function removeDhEmbed(id) {
        dhEmbeds = dhEmbeds.filter(e => e.id !== id);
        const card = document.getElementById(`dh-embed-card-${id}`);
        if (card) card.remove();
        renumberDhEmbeds();
        updateDhPreview();
    }

    function duplicateDhEmbed(id) {
        const embed = dhEmbeds.find(e => e.id === id);
        if (!embed) return;
        const newEmbed = JSON.parse(JSON.stringify(embed));
        newEmbed.id = dhCreateEmbedId();
        dhEmbeds.push(newEmbed);
        renderDhEmbedCard(newEmbed);
        updateDhPreview();
    }

    function moveDhEmbed(id, direction) {
        const idx = dhEmbeds.findIndex(e => e.id === id);
        if (idx === -1) return;
        const newIdx = idx + direction;
        if (newIdx < 0 || newIdx >= dhEmbeds.length) return;
        [dhEmbeds[idx], dhEmbeds[newIdx]] = [dhEmbeds[newIdx], dhEmbeds[idx]];
        const container = document.getElementById('dh-embeds-list');
        container.innerHTML = '';
        dhEmbeds.forEach(e => renderDhEmbedCard(e));
        updateDhPreview();
    }

    function renumberDhEmbeds() {
        dhEmbeds.forEach((e, i) => {
            const card = document.getElementById(`dh-embed-card-${e.id}`);
            if (card) {
                const left = card.querySelector('.dh-embed-header-left');
                if (left) left.innerHTML = `<span class="dh-embed-header-color" style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${e.color}"></span> Embed #${i + 1}`;
            }
        });
    }

    function updateHeaderColor(id) {
        const embed = dhEmbeds.find(e => e.id === id);
        if (!embed) return;
        const card = document.getElementById(`dh-embed-card-${id}`);
        if (card) {
            const colorDot = card.querySelector('.dh-embed-header-color');
            if (colorDot) colorDot.style.background = embed.color;
            card.querySelectorAll('.dh-color-preset').forEach(p => {
                p.classList.toggle('active', p.dataset.color === embed.color);
            });
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function getDhPayload() {
        const content = document.getElementById('dh-content').value || '';
        const embeds = dhEmbeds.map(e => {
            const embed = {};
            if (e.title) embed.title = e.title;
            if (e.description) embed.description = e.description;
            if (e.url) embed.url = e.url;
            if (e.color) embed.color = parseInt(e.color.replace('#', ''), 16);
            if (e.author_name) {
                embed.author = { name: e.author_name };
                if (e.author_url) embed.author.url = e.author_url;
                if (e.author_icon_url) embed.author.icon_url = e.author_icon_url;
            }
            if (e.footer_text) {
                embed.footer = { text: e.footer_text };
                if (e.footer_icon_url) embed.footer.icon_url = e.footer_icon_url;
            }
            if (e.thumbnail_url) embed.thumbnail = { url: e.thumbnail_url };
            if (e.image_url) embed.image = { url: e.image_url };
            if (e.fields && e.fields.length > 0) {
                embed.fields = e.fields.map(f => ({
                    name: f.name || ' ',
                    value: f.value || ' ',
                    inline: !!f.inline
                }));
            }
            return embed;
        }).filter(e => Object.keys(e).length > 0);

        const payload = {};
        if (content) payload.content = content;
        if (embeds.length > 0) payload.embeds = embeds;
        return payload;
    }

    function updateDhPreview() {
        const container = document.getElementById('dh-preview-messages');
        if (!container) return;
        const payload = getDhPayload();
        const content = document.getElementById('dh-content').value || '';

        const count = document.getElementById('dh-content-count');
        if (count) {
            count.textContent = `${content.length}/2000`;
            count.className = 'dh-char-count';
            if (content.length > 2000) count.classList.add('exceed');
            else if (content.length > 1800) count.classList.add('warn');
        }

        if (!content && (!payload.embeds || payload.embeds.length === 0)) {
            container.innerHTML = `
                <div class="dh-preview-placeholder">
                    <div style="font-size: 3rem; margin-bottom: 10px; opacity: 0.3;">💬</div>
                    <div style="color: var(--color-text-secondary);">Preencha os dados ao lado para ver o preview</div>
                </div>`;
            return;
        }

        let html = '';
        if (content) {
            html += `<div class="dh-msg-content">${formatDhContent(content)}</div>`;
        }

        if (payload.embeds) {
            payload.embeds.forEach(embed => {
                html += renderDhEmbedPreview(embed);
            });
        }

        container.innerHTML = html;
    }

    function formatDhContent(text) {
        return escapeHtml(text)
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/~~(.+?)~~/g, '<s>$1</s>')
            .replace(/__(.+?)__/g, '<u>$1</u>')
            .replace(/`(.+?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
            .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
    }

    function renderDhEmbedPreview(embed) {
        const color = embed.color ? `#${embed.color.toString(16).padStart(6, '0')}` : '#5865f2';
        let html = `<div class="dh-embed-preview"><div class="dh-embed-color" style="background:${color}"></div><div class="dh-embed-body-preview">`;

        if (embed.thumbnail) {
            html += `<div class="dh-embed-thumbnail"><img src="${escapeHtml(embed.thumbnail.url)}" alt="" onerror="this.style.display='none'"></div>`;
        }

        if (embed.author) {
            html += `<div class="dh-embed-author">`;
            if (embed.author.icon_url) html += `<img src="${escapeHtml(embed.author.icon_url)}" alt="" onerror="this.style.display='none'">`;
            html += `<span>`;
            if (embed.author.url) html += `<a href="${escapeHtml(embed.author.url)}" target="_blank" rel="noopener">`;
            html += escapeHtml(embed.author.name);
            if (embed.author.url) html += `</a>`;
            html += `</span></div>`;
        }

        if (embed.title) {
            html += `<div class="dh-embed-title">`;
            if (embed.url) html += `<a href="${escapeHtml(embed.url)}" target="_blank" rel="noopener">`;
            html += escapeHtml(embed.title);
            if (embed.url) html += `</a>`;
            html += `</div>`;
        }

        if (embed.description) {
            html += `<div class="dh-embed-description">${formatDhContent(embed.description)}</div>`;
        }

        if (embed.fields && embed.fields.length > 0) {
            html += `<div class="dh-embed-fields">`;
            embed.fields.forEach(f => {
                const inlineClass = f.inline ? ' inline' : '';
                html += `<div class="dh-embed-field${inlineClass}">`;
                html += `<div class="dh-embed-field-name">${escapeHtml(f.name)}</div>`;
                html += `<div class="dh-embed-field-value">${formatDhContent(f.value)}</div>`;
                html += `</div>`;
            });
            html += `</div>`;
        }

        if (embed.image) {
            html += `<div class="dh-embed-image"><img src="${escapeHtml(embed.image.url)}" alt="" onerror="this.style.display='none'"></div>`;
        }

        if (embed.footer || embed.timestamp) {
            html += `<div class="dh-embed-footer">`;
            if (embed.footer) {
                if (embed.footer.icon_url) html += `<img src="${escapeHtml(embed.footer.icon_url)}" alt="" onerror="this.style.display='none'">`;
                html += `<span>${escapeHtml(embed.footer.text)}</span>`;
            }
            if (embed.timestamp) {
                const ts = new Date(embed.timestamp);
                if (!isNaN(ts)) html += `<span class="dh-embed-timestamp">${ts.toLocaleDateString('pt-BR')}</span>`;
            }
            html += `</div>`;
        }

        html += `</div></div>`;
        return html;
    }

    async function sendDhWebhook() {
        const url = document.getElementById('dh-webhook-url').value.trim();
        const feedback = document.getElementById('dh-feedback');
        if (!url) {
            feedback.className = 'dh-send-status error';
            feedback.textContent = 'Insira uma URL de Webhook primeiro.';
            return;
        }

        const payload = getDhPayload();
        if (!payload.content && (!payload.embeds || payload.embeds.length === 0)) {
            feedback.className = 'dh-send-status error';
            feedback.textContent = 'Adicione conteúdo ou pelo menos um embed.';
            return;
        }

        const btn = document.getElementById('dh-send-btn');
        const originalText = btn.textContent;
        btn.textContent = 'Enviando...';
        btn.disabled = true;
        feedback.className = 'dh-send-status loading';
        feedback.textContent = 'Enviando...';

        try {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                feedback.className = 'dh-send-status success';
                const wait = response.status === 204 ? '' : ' (resposta recebida)';
                feedback.textContent = `✅ Mensagem enviada com sucesso!${wait}`;
            } else {
                const errText = await response.text().catch(() => 'Erro desconhecido');
                feedback.className = 'dh-send-status error';
                feedback.textContent = `❌ Erro ${response.status}: ${errText.substring(0, 200)}`;
            }
        } catch (err) {
            feedback.className = 'dh-send-status error';
            feedback.textContent = `❌ Falha na conexão: ${err.message}`;
        } finally {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    }

    function clearDhAll() {
        const webhook = document.getElementById('dh-webhook-url').value;
        localStorage.setItem('dh_saved_webhook', webhook);
        document.getElementById('dh-content').value = '';
        document.getElementById('dh-embeds-list').innerHTML = '';
        dhEmbeds = [];
        dhEmbedIdCounter = 0;
        document.getElementById('dh-feedback').textContent = '';
        document.getElementById('dh-feedback').className = '';
        updateDhPreview();
    }

    function exportDhJSON() {
        const payload = getDhPayload();
        showDhModal('📤 Exportar JSON', JSON.stringify(payload, null, 2), false);
    }

    function importDhJSON() {
        showDhModal('📥 Importar JSON', '', true);
    }

    function showDhModal(title, jsonContent, isImport) {
        const existing = document.querySelector('.dh-modal-overlay');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.className = 'dh-modal-overlay';
        overlay.innerHTML = `
            <div class="dh-modal">
                <h3>${title}</h3>
                <textarea id="dh-json-textarea" ${isImport ? 'placeholder="Cole o JSON do payload aqui..."' : ''}>${escapeHtml(jsonContent)}</textarea>
                <div class="dh-modal-actions">
                    <button class="dh-modal-close">Cancelar</button>
                    ${isImport ? '<button class="dh-modal-import primary">Importar</button>' : '<button class="dh-modal-copy primary">Copiar</button>'}
                </div>
            </div>
        `;

        document.body.appendChild(overlay);

        overlay.querySelector('.dh-modal-close').addEventListener('click', () => overlay.remove());
        overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });

        if (isImport) {
            overlay.querySelector('.dh-modal-import').addEventListener('click', () => {
                const text = document.getElementById('dh-json-textarea').value;
                try {
                    const data = JSON.parse(text);
                    importDhFromPayload(data);
                    overlay.remove();
                } catch (e) {
                    alert('JSON inválido: ' + e.message);
                }
            });
        } else {
            overlay.querySelector('.dh-modal-copy').addEventListener('click', () => {
                const ta = document.getElementById('dh-json-textarea');
                ta.select();
                document.execCommand('copy');
                overlay.querySelector('.dh-modal-copy').textContent = 'Copiado!';
                setTimeout(() => overlay.remove(), 800);
            });
        }
    }

    function importDhFromPayload(data) {
        document.getElementById('dh-embeds-list').innerHTML = '';
        dhEmbeds = [];
        dhEmbedIdCounter = 0;

        if (data.content) {
            document.getElementById('dh-content').value = data.content;
        }

        if (data.embeds && Array.isArray(data.embeds)) {
            data.embeds.forEach(ed => {
                addDhEmbed({
                    title: ed.title || '',
                    description: ed.description || '',
                    color: ed.color ? '#' + ed.color.toString(16).padStart(6, '0') : '#5865f2',
                    url: ed.url || '',
                    author_name: ed.author?.name || '',
                    author_url: ed.author?.url || '',
                    author_icon_url: ed.author?.icon_url || '',
                    footer_text: ed.footer?.text || '',
                    footer_icon_url: ed.footer?.icon_url || '',
                    thumbnail_url: ed.thumbnail?.url || '',
                    image_url: ed.image?.url || '',
                    fields: (ed.fields || []).map(f => ({
                        name: f.name || '',
                        value: f.value || '',
                        inline: !!f.inline
                    }))
                });
            });
        }
        updateDhPreview();
    }

    function loadDhExample() {
        clearDhAll();
        document.getElementById('dh-content').value = 'Bem-vindo ao **DiscoHook**! 🎉\n\nUse este editor para criar mensagens personalizadas com embeds ricos para o seu servidor Discord.';
        addDhEmbed({
            title: 'O que é isso?',
            description: 'DiscoHook é um editor visual de embeds do Discord. Você pode criar mensagens estilizadas com cores, campos, imagens e muito mais, e enviá-las via Webhook.',
            color: '#58b9ff',
            author_name: 'DiscoHook',
            footer_text: 'Criado com DiscoHook',
            fields: [
                { name: '📝 Content', value: 'Texto simples acima dos embeds', inline: true },
                { name: '🎨 Embeds', value: 'Mensagens ricas com formatação', inline: true },
                { name: '🔗 Webhook', value: 'Envie para qualquer canal do Discord', inline: false }
            ]
        });
        addDhEmbed({
            title: 'Discord Bot',
            description: 'Nosso bot complementar pode ajudar com formatação, reaction roles e restaurar mensagens.',
            color: '#5865f2',
            fields: [
                { name: '/format', value: 'Formatação especial para menções e emojis', inline: true },
                { name: '/reaction-role', value: 'Cargos por reação', inline: true }
            ]
        });
        updateDhPreview();
        document.getElementById('dh-feedback').className = '';
        document.getElementById('dh-feedback').textContent = '';
    }

    // Initial load
    loadDataForCurrentTab();
    initTooltips();
});
