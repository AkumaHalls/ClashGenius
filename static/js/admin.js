document.addEventListener('DOMContentLoaded', () => {
    // Lógica para a página de login
    const loginForm = document.querySelector('form[action="/admin/login"]');
    if (loginForm) {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('error')) {
            const errorMessageEl = document.getElementById('error-message');
            if(errorMessageEl) errorMessageEl.textContent = 'Senha incorreta. Tente novamente.';
        }
        // Captura guild_id da URL, se presente
        const guildId = urlParams.get('guild_id');
        const guildIdInput = document.getElementById('guild_id');
        if (guildId && guildIdInput) {
            guildIdInput.value = guildId;
        }
    }

    // Só executa o resto se estiver no painel admin
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
    const dbWarsTableBody = document.querySelector('#db-wars-table tbody');
    const dbNotesTableBody = document.querySelector('#db-notes-table tbody');
    const sendAnnouncementBtn = document.getElementById('send-announcement-btn');
    const announcementChannelInput = document.getElementById('announcement-channel-id');
    const announcementMessageInput = document.getElementById('announcement-message');

    // Watchlist selectors
    const addWatchlistForm = document.getElementById('admin-add-watchlist-form');
    const watchlistTableBody = document.querySelector('#admin-watchlist-table tbody');
    const watchlistAddFeedback = document.getElementById('watchlist-add-feedback');
    const watchlistListFeedback = document.getElementById('watchlist-list-feedback');

    // Seletores para Navegação por Abas
    const navLinks = document.querySelectorAll('.admin-nav .nav-link');
    const contentSections = document.querySelectorAll('.admin-section');
    const initialSectionId = navLinks.length > 0 ? navLinks[0].dataset.section : 'admin-geral';
    let currentActiveSectionId = localStorage.getItem('activeAdminSection') || initialSectionId;


    // --- Funções API ---
    async function fetchAdminAPI(endpoint, options = {}) {
        // Adiciona tratamento para POST sem body esperado na resposta
        const isPostWithoutBodyResponse = options.method === 'POST' && (endpoint.startsWith('watchlist/') || endpoint === 'actions');

        try {
            const response = await fetch(`/api/admin/${endpoint}`, options);

            if (response.status === 204) return { status: 'success', message: 'Operação concluída.' }; // Handle No Content globally

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: `Erro HTTP ${response.status}` }));
                throw new Error(errorData.message || `Falha ao acessar ${endpoint}`);
            }

            // Para POSTs específicos que podem não retornar JSON mas indicam sucesso com 200 OK
            if (isPostWithoutBodyResponse && response.status === 200) {
                 // Tenta pegar JSON, se falhar, retorna sucesso genérico
                 try { return await response.json(); } catch(e) { return { status: 'success', message: 'Ação executada.' }; }
            }

            return response.json(); // Default: return JSON
        } catch (error) {
            console.error(`Erro na API admin em ${endpoint}:`, error);
            const feedbackEl = document.getElementById('actions-feedback') || document.getElementById('settings-feedback') || document.getElementById('watchlist-add-feedback') || document.getElementById('watchlist-list-feedback');
            displayFeedback(feedbackEl, `Erro: ${error.message}`, true);
            throw error; // Re-throw para indicar falha
        }
    }

    // --- Funções de UI ---
    function displayFeedback(element, message, isError = false, duration = 4000) {
        if (!element) return;
        element.textContent = message;
        element.classList.toggle('error', isError);
        // Clear previous timeouts if any
        if (element.timeoutId) clearTimeout(element.timeoutId);
        element.timeoutId = setTimeout(() => { element.textContent = ''; element.classList.remove('error'); }, duration);
    }

    function updateStatus(data) {
        if (statusTextEl) {
            statusTextEl.textContent = data.maintenance_mode ? 'ATIVADO' : 'DESATIVADO';
            statusTextEl.className = `status-badge ${data.maintenance_mode ? 'status-on' : 'status-off'}`;
        }
        if(botVersionEl) botVersionEl.textContent = data.version || '-';
    }

    function updateDiagnostics(data) {
        if (!data) return; // Adiciona verificação
        const { api_status, recent_logs } = data;
        if(apiStatusBadge && api_status) { // Adiciona verificação para api_status
            apiStatusBadge.className = `status-badge status-${api_status.status}`;
            apiStatusBadge.textContent = api_status.status === 'ok' ? 'Operacional' : (api_status.status === 'maintenance' ? 'Manutenção' : 'Erro');
        }
        if(apiStatusMessage && api_status) apiStatusMessage.textContent = api_status.message; // Adiciona verificação para api_status
        if(recentLogsBox) recentLogsBox.textContent = Array.isArray(recent_logs) && recent_logs.length > 0 ? recent_logs.join('\n') : 'Nenhum log recente.'; // Verifica se é array
    }

    function populateSettingsForm(data) {
        if (!data || data.error || !settingsForm) return;
        for (const key in data) {
            const input = document.getElementById(key);
            if (input) {
                // Handle boolean specifically for select/checkbox
                if (key === "auto_add_watchlist_enabled" && input.tagName === 'SELECT') {
                    input.value = data[key] ? 'true' : 'false';
                } else if (input.type === 'checkbox') {
                     input.checked = !!data[key]; // Generic checkbox handling
                } else {
                   input.value = data[key] !== null && data[key] !== undefined ? data[key] : ''; // Handle null/undefined
                }
            }
        }
    }


    function updateDbViewer(data) {
        if (!data || data.error) return; // Adiciona verificação

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
                 navigator.clipboard.writeText(text).then(() => {
                     const originalText = td.textContent;
                     td.textContent = 'Copiado!';
                     setTimeout(() => { td.textContent = originalText; }, 1500);
                 }).catch(err => console.error('Falha ao copiar ID:', err));
             };
             return td;
         };


        if(dbWarsTableBody && Array.isArray(data.last_wars)) { // Verifica se é array
            dbWarsTableBody.innerHTML = data.last_wars.length > 0
                ? data.last_wars.map(w => {
                     const row = document.createElement('tr');
                     row.innerHTML = `<td>${w.opponent || 'N/A'}</td><td>${formatDbDate(w.end_time)}</td>`;
                     row.appendChild(createClickToCopyCell(w.id)); // Adiciona célula clicável
                     return row.outerHTML;
                  }).join('')
                : '<tr><td colspan="3">Nenhum registro de guerra encontrado.</td></tr>';
        } else if (dbWarsTableBody) {
             dbWarsTableBody.innerHTML = '<tr><td colspan="3">Erro ao carregar guerras.</td></tr>';
        }

        if(dbNotesTableBody && Array.isArray(data.last_notes)) { // Verifica se é array
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
        }
    }

    // --- Watchlist Functions ---
    async function loadWatchlist() {
        if (!watchlistTableBody) return;
        watchlistTableBody.innerHTML = '<tr><td colspan="6"><div class="loading-spinner" style="margin: 10px auto; width: 20px; height: 20px;"></div></td></tr>'; // Add spinner
        try {
            const response = await fetchAdminAPI('watchlist'); // Uses GET by default
             // A resposta pode ser um objeto com erro ou um array
            if (response.error) {
                 watchlistTableBody.innerHTML = `<tr><td colspan="6" class="error-text">Erro: ${response.error}</td></tr>`;
                 return;
            }
            // Assume que se não tem erro, é o array (pode estar vazio)
            const watchlist = Array.isArray(response) ? response : [];

            if (watchlist.length === 0) {
                 watchlistTableBody.innerHTML = '<tr><td colspan="6">Nenhum jogador na lista de observação.</td></tr>';
                 return;
            }
            watchlistTableBody.innerHTML = watchlist.map(player => {
                let dateStr = '-';
                if (player.date_added) {
                     try { dateStr = new Date(player.date_added).toLocaleDateString('pt-BR'); }
                     catch(e) { console.warn("Invalid date format from watchlist:", player.date_added); dateStr = player.date_added; } // Usa a string se der erro
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

            // Attach remove button listeners
            watchlistTableBody.querySelectorAll('.admin-remove-btn').forEach(btn => {
                btn.addEventListener('click', handleRemoveWatchlist);
            });
        } catch (error) {
             watchlistTableBody.innerHTML = '<tr><td colspan="6" class="error-text">Erro ao carregar a lista. Verifique a consola.</td></tr>';
             console.error("Error loading watchlist:", error); // Log detailed error
        }
    }


    async function handleAddWatchlist(event) {
        event.preventDefault();
        if (!addWatchlistForm) return;
        const formData = new FormData(addWatchlistForm);
        const data = Object.fromEntries(formData.entries());

        // Basic tag validation (starts with #, reasonable length)
        if (!data.player_tag || !data.player_tag.startsWith('#') || data.player_tag.length < 5) {
             displayFeedback(watchlistAddFeedback, 'Por favor, insira uma tag de jogador válida (Ex: #ABC123XYZ).', true);
             return;
        }

        displayFeedback(watchlistAddFeedback, 'Adicionando...');
        try {
            const response = await fetchAdminAPI('watchlist/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            // A resposta pode ou não ter uma 'message', mas o status indica sucesso
             displayFeedback(watchlistAddFeedback, response.message || 'Jogador adicionado/atualizado.');
             if (response.status === 'success' || !response.error) { // Considera sucesso se não houver erro explícito
                 addWatchlistForm.reset();
                 loadWatchlist(); // Reload the list
             } else {
                  // Se houve erro específico retornado pela API
                  displayFeedback(watchlistAddFeedback, response.message || 'Erro desconhecido ao adicionar.', true);
             }
        } catch (error) {
            // Error already displayed by fetchAdminAPI, just clear the loading message
            displayFeedback(watchlistAddFeedback, `Erro: ${error.message}`, true);
        }
    }

    async function handleRemoveWatchlist(event) {
        const button = event.target;
        const playerTag = button.dataset.tag;
        const playerName = button.closest('tr')?.cells[0]?.textContent || playerTag; // Get name for confirmation
        if (!playerTag || !confirm(`Tem certeza que deseja remover ${playerName} (${playerTag}) da lista?`)) {
            return;
        }

        button.disabled = true; // Disable button during request
        button.textContent = '...';
        displayFeedback(watchlistListFeedback, 'Removendo...');
        try {
             const response = await fetchAdminAPI('watchlist/remove', {
                method: 'POST', // Use POST for removal
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ player_tag: playerTag })
            });

             // Verifica se a resposta indica sucesso ou item não encontrado
             if (response.status === 'success' || response.status === 'not_found' || !response.error) {
                 displayFeedback(watchlistListFeedback, response.message || "Operação concluída.");
                 loadWatchlist(); // Reload the list after successful removal or if not found
             } else {
                 // Se houve outro erro
                 displayFeedback(watchlistListFeedback, response.message || 'Erro ao remover.', true);
                 button.disabled = false; // Re-enable button on error
                 button.textContent = 'Remover';
             }
        } catch (error) {
           // Error already displayed by fetchAdminAPI
           button.disabled = false; // Re-enable button on error
           button.textContent = 'Remover';
        }
    }

    // --- Navegação por Abas ---
    function setActiveAdminSection(newSectionId) {
        if (!newSectionId || newSectionId === currentActiveSectionId) return;

        const oldSectionEl = document.getElementById(currentActiveSectionId);
        const newSectionEl = document.getElementById(newSectionId);

        if (!newSectionEl) {
            console.warn(`Admin section with ID "${newSectionId}" not found.`);
            return;
        }

        oldSectionEl?.classList.remove('active-section');
        navLinks.forEach(link => link?.classList.remove('active-nav-link'));

        newSectionEl.classList.add('active-section');
        const newLink = document.querySelector(`.admin-nav .nav-link[data-section="${newSectionId}"]`);
        newLink?.classList.add('active-nav-link');

        localStorage.setItem('activeAdminSection', newSectionId);
        currentActiveSectionId = newSectionId;
    }

    // --- Carregamento Inicial e Event Listeners ---
    async function loadAllAdminData() {
        try {
            // Fetch status separadamente
            const status = await fetch('/api/status').then(res => res.ok ? res.json() : { maintenance_mode: true, version: '?', error: 'Status fetch failed' }).catch(err => {
                 console.error("Falha ao buscar status:", err);
                 return { maintenance_mode: true, version: '?', error: 'Status fetch failed'};
            });
             updateStatus(status);
             if (status.error) return; // Para se o status falhar

            // Carrega dados específicos da aba ativa primeiro
            if (currentActiveSectionId === 'admin-diagnostico') {
                const diagnostics = await fetchAdminAPI('diagnostics').catch(() => null);
                updateDiagnostics(diagnostics);
            } else if (currentActiveSectionId === 'admin-configuracoes') {
                const settings = await fetchAdminAPI('settings').catch(() => null);
                populateSettingsForm(settings);
            } else if (currentActiveSectionId === 'admin-db') {
                 const dbData = await fetchAdminAPI('db_viewer').catch(() => null);
                 updateDbViewer(dbData);
            } else if (currentActiveSectionId === 'admin-watchlist') {
                 await loadWatchlist();
            }

            // Opcional: Carregar outros dados em segundo plano se necessário,
            // mas geralmente é melhor carregar sob demanda ao clicar na aba
            // para evitar sobrecarga inicial.

        } catch (error) {
            console.error("Falha ao carregar dados do admin.", error);
            // Pode exibir uma mensagem de erro mais genérica se necessário
        }
    }

    // Define a aba ativa inicial
    setActiveAdminSection(currentActiveSectionId);

    // Adiciona listeners aos links de navegação
    navLinks.forEach((link) => {
        link?.addEventListener('click', (e) => {
            e.preventDefault();
            const sectionId = link.dataset.section;
            setActiveAdminSection(sectionId);
            // Carrega os dados da nova aba ativa
            loadAllAdminData();
        });
    });


    // Attach form/button listeners only if elements exist
    if (toggleBtn) {
        toggleBtn.addEventListener('click', async () => {
            let originalText = toggleBtn.textContent; // Guarda texto original
            try {
                toggleBtn.disabled = true; toggleBtn.textContent = 'Aguarde...';
                // Usa fetchAdminAPI que já trata erros
                await fetchAdminAPI('actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'toggle_maintenance' }) // Assumindo que a API aceita essa ação
                 });
                 // Re-busca o status para ter certeza
                const status = await fetch('/api/status').then(res => res.ok ? res.json() : { maintenance_mode: false }).catch(()=>({ maintenance_mode: false }));
                updateStatus(status);
                displayFeedback(actionsFeedback, status.maintenance_mode ? 'Modo manutenção ATIVADO.' : 'Modo manutenção DESATIVADO.');
            } catch (error) { /* Erro já tratado por fetchAdminAPI */ }
            finally { toggleBtn.disabled = false; toggleBtn.textContent = originalText; } // Restaura texto original
        });
    }


    if (testBtn) {
        testBtn.addEventListener('click', async () => {
             let originalText = testBtn.textContent;
            try {
                testBtn.disabled = true; testBtn.textContent = 'Enviando...';
                // Usa fetchAdminAPI
                await fetchAdminAPI('actions', {
                     method: 'POST',
                     headers: { 'Content-Type': 'application/json' },
                     body: JSON.stringify({ action: 'send_test_embed' }) // Assumindo ação
                 });
                displayFeedback(actionsFeedback, "Mensagem de teste enviada!");
            } catch (error) { /* Erro já tratado */ }
            finally { testBtn.disabled = false; testBtn.textContent = originalText; }
        });
    }

    if (settingsForm) {
        settingsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(settingsForm);
            const settings = {};
            // Process form data, converting relevant fields
            for (const [key, value] of formData.entries()) {
                 if (key === "auto_add_watchlist_enabled") {
                    settings[key] = value === 'true'; // Convert select string to boolean
                } else if (key.includes('_id') && value.match(/^\d+$/)) {
                     // Converte apenas se for número e tiver ID no nome
                     settings[key] = parseInt(value, 10);
                 } else if (value.match(/^\d+$/) && !key.includes('message')) {
                      // Converte outros campos numéricos (exceto mensagem)
                      settings[key] = parseInt(value, 10);
                 }
                 else {
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
            } catch(error) { /* Error handled by fetchAdminAPI */ }
        });
    }


    document.querySelectorAll('.action-btn').forEach(button => {
        button.addEventListener('click', async () => {
             let originalText = button.textContent;
             button.disabled = true; button.textContent = 'Executando...';
            const action = button.dataset.action;
            const payload = JSON.parse(button.dataset.payload || '{}'); // Garante que payload seja objeto
            displayFeedback(actionsFeedback, `Executando ${action}...`);
            try {
                const response = await fetchAdminAPI('actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action, payload })
                });
                displayFeedback(actionsFeedback, response.message || `Ação '${action}' concluída.`);
            } catch (error) { /* Error handled by fetchAdminAPI */ }
             finally { button.disabled = false; button.textContent = originalText; }
        });
    });

    if (sendAnnouncementBtn) {
        sendAnnouncementBtn.addEventListener('click', async () => {
            let originalText = sendAnnouncementBtn.textContent;
            sendAnnouncementBtn.disabled = true; sendAnnouncementBtn.textContent = 'Enviando...';
            const channelId = announcementChannelInput?.value; // Usa optional chaining
            const message = announcementMessageInput?.value;
            if (!channelId || !channelId.match(/^\d+$/) || !message) {
                 displayFeedback(actionsFeedback, "Preencha um ID de canal válido e a mensagem.", true);
                 sendAnnouncementBtn.disabled = false; sendAnnouncementBtn.textContent = originalText;
                 return;
            }
            displayFeedback(actionsFeedback, 'Enviando anúncio...');
            try {
                const response = await fetchAdminAPI('actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'send_announcement', payload: { channel_id: channelId, message: message }})
                });
                displayFeedback(actionsFeedback, response.message || 'Anúncio enviado.');
                 if((response.status === 'success' || !response.error) && announcementMessageInput) announcementMessageInput.value = ''; // Clear message on success
            } catch (error) { /* Error handled by fetchAdminAPI */ }
             finally { sendAnnouncementBtn.disabled = false; sendAnnouncementBtn.textContent = originalText; }
        });
    }


    // Watchlist Add Form Listener
    if (addWatchlistForm) {
        addWatchlistForm.addEventListener('submit', handleAddWatchlist);
    }

    // Initial load for the active tab
    loadAllAdminData();
    // Não precisa de setInterval aqui, carrega ao mudar de aba
});
