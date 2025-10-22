document.addEventListener('DOMContentLoaded', () => {
    // Lógica para a página de login
    const loginForm = document.querySelector('form[action="/admin/login"]');
    if (loginForm) {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('error')) {
            const errorMessageEl = document.getElementById('error-message');
            if(errorMessageEl) errorMessageEl.textContent = 'Senha incorreta. Tente novamente.';
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
    const dbWarsTableBody = document.querySelector('#db-wars-table tbody');
    const dbNotesTableBody = document.querySelector('#db-notes-table tbody');
    const sendAnnouncementBtn = document.getElementById('send-announcement-btn');

    // Watchlist selectors
    const addWatchlistForm = document.getElementById('admin-add-watchlist-form');
    const watchlistTableBody = document.querySelector('#admin-watchlist-table tbody');
    const watchlistAddFeedback = document.getElementById('watchlist-add-feedback');
    const watchlistListFeedback = document.getElementById('watchlist-list-feedback');


    // --- Funções API ---
    async function fetchAdminAPI(endpoint, options = {}) {
        try {
            const response = await fetch(`/api/admin/${endpoint}`, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: `Erro HTTP ${response.status}` }));
                throw new Error(errorData.message || `Falha ao acessar ${endpoint}`);
            }
             // Handle 204 No Content for successful deletions/updates without body
            if (response.status === 204) return { status: 'success', message: 'Operação concluída.'};
            // Handle successful POST/DELETE with body
            if (options.method === 'POST' && response.status === 200) {
                 const data = await response.json();
                 // Assume success if status is ok and there's a message
                 if (data.status === 'success' || data.message) {
                      return data;
                 }
            }
            // Default: return JSON for GET or if specific success conditions not met
            return response.json();
        } catch (error) {
            console.error(`Erro na API admin em ${endpoint}:`, error);
            const feedbackEl = document.getElementById('actions-feedback') || document.getElementById('settings-feedback') || document.getElementById('watchlist-add-feedback') || document.getElementById('watchlist-list-feedback');
            displayFeedback(feedbackEl, `Erro: ${error.message}`, true);
            throw error; // Re-throw to indicate failure
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
        const { api_status, recent_logs } = data;
        if(apiStatusBadge) {
            apiStatusBadge.className = `status-badge status-${api_status.status}`;
            apiStatusBadge.textContent = api_status.status === 'ok' ? 'Operacional' : (api_status.status === 'maintenance' ? 'Manutenção' : 'Erro');
        }
        if(apiStatusMessage) apiStatusMessage.textContent = api_status.message;
        if(recentLogsBox) recentLogsBox.textContent = recent_logs.length > 0 ? recent_logs.join('\n') : 'Nenhum log recente.';
    }

    function populateSettingsForm(data) {
        if (data.error || !settingsForm) return;
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
        if (data.error) return;
        if(dbWarsTableBody) {
            dbWarsTableBody.innerHTML = data.last_wars.length > 0
                ? data.last_wars.map(w => `<tr><td>${w.opponent}</td><td>${w.end_time ? new Date(w.end_time).toLocaleString('pt-BR') : 'N/A'}</td><td>${w.id}</td></tr>`).join('')
                : '<tr><td colspan="3">Nenhum registro de guerra encontrado.</td></tr>';
        }
        if(dbNotesTableBody) {
            dbNotesTableBody.innerHTML = data.last_notes.length > 0
                ? data.last_notes.map(n => `<tr><td>${n.player_tag}</td><td>${n.note}</td><td class="priority-cell priority-${n.priority}">${n.priority}</td></tr>`).join('')
                : '<tr><td colspan="3">Nenhuma nota de jogador encontrada.</td></tr>';
        }
    }

    // --- Watchlist Functions ---
    async function loadWatchlist() {
        if (!watchlistTableBody) return;
        watchlistTableBody.innerHTML = '<tr><td colspan="6"><div class="loading-spinner" style="margin: 10px auto; width: 20px; height: 20px;"></div></td></tr>'; // Add spinner
        try {
            const watchlist = await fetchAdminAPI('watchlist'); // Uses GET by default
            if (watchlist.error) {
                 watchlistTableBody.innerHTML = `<tr><td colspan="6" class="error-text">Erro: ${watchlist.error}</td></tr>`;
                 return;
            }
            if (!Array.isArray(watchlist) || watchlist.length === 0) {
                 watchlistTableBody.innerHTML = '<tr><td colspan="6">Nenhum jogador na lista de observação.</td></tr>';
                 return;
            }
            watchlistTableBody.innerHTML = watchlist.map(player => {
                let dateStr = '-';
                if (player.date_added) {
                     try { dateStr = new Date(player.date_added).toLocaleDateString('pt-BR'); }
                     catch(e) { console.warn("Invalid date format from watchlist:", player.date_added); }
                }
                return `
                <tr>
                    <td>${player.name || 'N/A'}</td>
                    <td>${player._id}</td>
                    <td>${player.reason || '-'}</td>
                    <td>${player.details || '-'}</td>
                    <td>${dateStr}</td>
                    <td><button class="admin-remove-btn" data-tag="${player._id}">Remover</button></td>
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
            displayFeedback(watchlistAddFeedback, response.message);
            if (response.status === 'success') {
                addWatchlistForm.reset();
                loadWatchlist(); // Reload the list
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
            displayFeedback(watchlistListFeedback, response.message || "Operação concluída."); // Show message from backend
            loadWatchlist(); // Reload the list after successful removal or if not found
        } catch (error) {
           // Error already displayed by fetchAdminAPI
           button.disabled = false; // Re-enable button on error
           button.textContent = 'Remover';
        }
        // Button state is handled by reloading the list on success
    }


    // --- Carregamento Inicial e Event Listeners ---
    async function loadAllAdminData() {
        try {
            // Fetch status separately as it doesn't require admin auth
            const status = await fetch('/api/status').then(res => res.json()).catch(err => {
                 console.error("Failed to fetch status:", err);
                 return { maintenance_mode: true, version: '?', error: 'Status fetch failed'}; // Assume maintenance if status fails
            });
             updateStatus(status);
             if (status.error) return; // Stop if status fetch failed

            const [diagnostics, settings, dbData] = await Promise.all([
                fetchAdminAPI('diagnostics'),
                fetchAdminAPI('settings'),
                fetchAdminAPI('db_viewer')
            ]);

            updateDiagnostics(diagnostics);
            populateSettingsForm(settings);
            updateDbViewer(dbData);
            loadWatchlist(); // Load watchlist data

        } catch (error) {
            console.error("Falha ao carregar dados do admin.", error);
            // Don't show generic error if specific handled by fetchAdminAPI
        }
    }

    // Attach form/button listeners only if elements exist
    if (toggleBtn) {
        toggleBtn.addEventListener('click', async () => {
            try {
                toggleBtn.disabled = true; toggleBtn.textContent = 'Aguarde...';
                await fetch('/admin/toggle_maintenance', { method: 'POST' });
                const status = await fetch('/api/status').then(res => res.json());
                updateStatus(status);
                displayFeedback(actionsFeedback, status.maintenance_mode ? 'Modo manutenção ATIVADO.' : 'Modo manutenção DESATIVADO.');
            } catch (error) { console.error('Erro ao alternar modo manutenção:', error); displayFeedback(actionsFeedback, `Erro: ${error.message}`, true); }
            finally { toggleBtn.disabled = false; toggleBtn.textContent = 'Ativar/Desativar'; }
        });
    }


    if (testBtn) {
        testBtn.addEventListener('click', async () => {
            try {
                testBtn.disabled = true; testBtn.textContent = 'Enviando...';
                await fetch('/admin/send_test_embed', { method: 'POST' });
                displayFeedback(actionsFeedback, "Mensagem de teste enviada!");
            } catch (error) { console.error('Erro ao enviar embed de teste:', error); displayFeedback(actionsFeedback, `Erro: ${error.message}`, true); }
            finally { testBtn.disabled = false; testBtn.textContent = 'Enviar Mensagem de Teste'; }
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
                     settings[key] = parseInt(value, 10); // Convert IDs to numbers if they are digits
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
                displayFeedback(settingsFeedback, response.message);
            } catch(error) { /* Error handled by fetchAdminAPI */ }
        });
    }


    document.querySelectorAll('.action-btn').forEach(button => {
        button.addEventListener('click', async () => {
            const action = button.dataset.action;
            const payload = JSON.parse(button.dataset.payload);
            displayFeedback(actionsFeedback, `Executando ${action}...`);
            try {
                const response = await fetchAdminAPI('actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action, payload })
                });
                displayFeedback(actionsFeedback, response.message);
            } catch (error) { /* Error handled by fetchAdminAPI */ }
        });
    });

    if (sendAnnouncementBtn) {
        sendAnnouncementBtn.addEventListener('click', async () => {
            const channelIdInput = document.getElementById('announcement-channel-id');
            const messageInput = document.getElementById('announcement-message');
            const channelId = channelIdInput.value;
            const message = messageInput.value;
            if (!channelId || !channelId.match(/^\d+$/) || !message) {
                 displayFeedback(actionsFeedback, "Preencha um ID de canal válido e a mensagem.", true);
                 return;
            }
            displayFeedback(actionsFeedback, 'Enviando anúncio...');
            try {
                const response = await fetchAdminAPI('actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action: 'send_announcement', payload: { channel_id: channelId, message: message }})
                });
                displayFeedback(actionsFeedback, response.message);
                 if(response.status === 'success') messageInput.value = ''; // Clear message on success
            } catch (error) { /* Error handled by fetchAdminAPI */ }
        });
    }


    // Watchlist Add Form Listener
    if (addWatchlistForm) {
        addWatchlistForm.addEventListener('submit', handleAddWatchlist);
    }

    // Initial load and periodic refresh
    loadAllAdminData();
    setInterval(loadAllAdminData, 30000); // Refresh every 30 seconds
});

