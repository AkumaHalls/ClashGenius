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
    
    async function fetchAdminAPI(endpoint, options = {}) {
        try {
            const response = await fetch(`/api/admin/${endpoint}`, options);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ message: `Erro HTTP ${response.status}` }));
                throw new Error(errorData.message || `Falha ao acessar ${endpoint}`);
            }
            return response.json();
        } catch (error) {
            console.error(`Erro na API admin em ${endpoint}:`, error);
            const feedbackEl = document.getElementById('actions-feedback') || document.getElementById('settings-feedback');
            if(feedbackEl) feedbackEl.textContent = `Erro: ${error.message}`;
            throw error;
        }
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
                input.value = data[key] || '';
            }
        }
    }

    function updateDbViewer(data) {
        if (data.error) return;
        
        if(dbWarsTableBody) {
            dbWarsTableBody.innerHTML = data.last_wars.length > 0 
                ? data.last_wars.map(w => `<tr><td>${w.opponent}</td><td>${new Date(w.end_time).toLocaleString('pt-BR')}</td><td>${w.id}</td></tr>`).join('')
                : '<tr><td colspan="3">Nenhum registro de guerra encontrado.</td></tr>';
        }

        if(dbNotesTableBody) {
            dbNotesTableBody.innerHTML = data.last_notes.length > 0
                ? data.last_notes.map(n => `<tr><td>${n.player_tag}</td><td>${n.note}</td><td class="priority-cell priority-${n.priority}">${n.priority}</td></tr>`).join('')
                : '<tr><td colspan="3">Nenhuma nota de jogador encontrada.</td></tr>';
        }
    }

    async function loadAllAdminData() {
        try {
            const [status, diagnostics, settings, dbData] = await Promise.all([
                fetch('/api/status').then(res => res.json()),
                fetchAdminAPI('diagnostics'),
                fetchAdminAPI('settings'),
                fetchAdminAPI('db_viewer')
            ]);
            
            updateStatus(status);
            updateDiagnostics(diagnostics);
            populateSettingsForm(settings);
            updateDbViewer(dbData);

        } catch (error) {
            console.error("Falha ao carregar todos os dados do admin.", error);
        }
    }

    if (toggleBtn) {
        toggleBtn.addEventListener('click', async () => {
            try {
                toggleBtn.disabled = true;
                toggleBtn.textContent = 'Aguarde...';
                await fetch('/admin/toggle_maintenance', { method: 'POST' });
                const status = await fetch('/api/status').then(res => res.json());
                updateStatus(status);
            } catch (error) {
                console.error('Erro ao alternar modo manutenção:', error);
            } finally {
                toggleBtn.disabled = false;
                toggleBtn.textContent = 'Ativar/Desativar';
            }
        });
    }

    if (testBtn) {
        testBtn.addEventListener('click', async () => {
            try {
                testBtn.disabled = true;
                testBtn.textContent = 'Enviando...';
                await fetch('/admin/send_test_embed', { method: 'POST' });
                if(actionsFeedback) actionsFeedback.textContent = "Mensagem de teste enviada!";
                setTimeout(() => { if(actionsFeedback) actionsFeedback.textContent = ''}, 3000);
            } catch (error) {
                console.error('Erro ao enviar embed de teste:', error);
            } finally {
                testBtn.disabled = false;
                testBtn.textContent = 'Enviar Mensagem de Teste';
            }
        });
    }

    if (settingsForm) {
        settingsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(settingsForm);
            const settings = Object.fromEntries(formData.entries());
            
            if(settingsFeedback) settingsFeedback.textContent = 'Salvando...';
            try {
                const response = await fetchAdminAPI('settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                if(settingsFeedback) settingsFeedback.textContent = response.message;
            } catch(error) {
                 if(settingsFeedback) settingsFeedback.textContent = `Erro ao salvar: ${error.message}`;
            } finally {
                setTimeout(() => { if(settingsFeedback) settingsFeedback.textContent = '' }, 3000);
            }
        });
    }
    
    document.querySelectorAll('.action-btn').forEach(button => {
        button.addEventListener('click', async () => {
            const action = button.dataset.action;
            const payload = JSON.parse(button.dataset.payload);
            
            if(actionsFeedback) actionsFeedback.textContent = `Executando ${action}...`;
            try {
                const response = await fetchAdminAPI('actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ action, payload })
                });
                if(actionsFeedback) actionsFeedback.textContent = response.message;
            } catch (error) {
                 if(actionsFeedback) actionsFeedback.textContent = `Erro na ação: ${error.message}`;
            } finally {
                 setTimeout(() => { if(actionsFeedback) actionsFeedback.textContent = '' }, 4000);
            }
        });
    });

    if (sendAnnouncementBtn) {
        sendAnnouncementBtn.addEventListener('click', async () => {
            const channelId = document.getElementById('announcement-channel-id').value;
            const message = document.getElementById('announcement-message').value;

            if (!channelId || !message) {
                if(actionsFeedback) actionsFeedback.textContent = "Preencha o ID do canal e a mensagem.";
                return;
            }

            if(actionsFeedback) actionsFeedback.textContent = 'Enviando anúncio...';
            try {
                const response = await fetchAdminAPI('actions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: 'send_announcement',
                        payload: { channel_id: channelId, message: message }
                    })
                });
                if(actionsFeedback) actionsFeedback.textContent = response.message;
                 if(response.status === 'success') {
                    document.getElementById('announcement-message').value = '';
                 }
            } catch (error) {
                if(actionsFeedback) actionsFeedback.textContent = `Erro ao enviar: ${error.message}`;
            } finally {
                setTimeout(() => {if(actionsFeedback) actionsFeedback.textContent = ''}, 4000);
            }
        });
    }
    
    loadAllAdminData();
    setInterval(loadAllAdminData, 30000);
});
