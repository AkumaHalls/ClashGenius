document.addEventListener('DOMContentLoaded', () => {
    // Lógica para a página de login
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

    if (!window.location.pathname.includes('/admin/panel')) return;

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

    // ========================================================
    // >>> POPULA OS NOVOS DROPDOWNS DO DISCORD <<<
    // ========================================================
    function populateDiscordDropdowns(discordData) {
        if (!discordData || discordData.error) return;

        // <<< ADICIONADO A VARIÁVEL DO CANAL DE FAXINA AQUI >>>
        const channelSelects = ['channel_id', 'post_war_analysis_channel_id', 'clan_games_channel_id', 'cwl_planner_channel_id', 'donations_channel_id', 'watchlist_alert_channel_id', 'low_performance_channel_id'];
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
                    // Para os novos dropdowns de Canais e Roles
                    const valStr = String(data[key] || "0");
                    
                    // Mecanismo de Prevenção: Se o ID existir na DB mas o bot não o encontrar mais no Discord,
                    // nós criamos uma opção provisória para ele não ser apagado do banco de dados acidentalmente.
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
    // ========================================================

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
                    <td>${player.name || 'N/A'}</td>
                    <td>${player._id || 'N/A'}</td>
                    <td>${player.reason || '-'}</td>
                    <td>${player.details || '-'}</td>
                    <td>${dateStr}</td>
                    <td><button class="admin-remove-btn" data-tag="${player._id || ''}">Remover</button></td>
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

    async function loadDataForCurrentTab() {
        [settingsFeedback, actionsFeedback, geralFeedback, dbFeedback, watchlistAddFeedback, watchlistListFeedback].forEach(el => {
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
                    // >>> GERA E PREENCHE OS DROP DOWN LISTS AQUI <<<
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
                 case 'admin-acoes':
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
                    // ID puro enviado perfeitamente via select agora.
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

    // Initial load
    loadDataForCurrentTab();
});
