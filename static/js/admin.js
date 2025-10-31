document.addEventListener('DOMContentLoaded', () => {
    // Lógica para a página de login (mantida)
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
    const geralFeedback = document.getElementById('geral-feedback'); // Feedback para aba Geral
    const dbFeedback = document.getElementById('db-feedback'); // Feedback para aba DB
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
    // Encontra o link inicial ou usa o primeiro
    const initialSectionId = document.querySelector('.admin-nav .nav-link')?.dataset.section || 'admin-geral'; // Mais robusto
    let currentActiveSectionId = localStorage.getItem('activeAdminSection') || initialSectionId;


    // --- Funções API --- (sem alterações)
    async function fetchAdminAPI(endpoint, options = {}) {
        // Adiciona tratamento para POST sem body esperado na resposta
        const isPostWithoutBodyResponse = options.method === 'POST' && (endpoint.startsWith('watchlist/') || endpoint === 'actions' || endpoint === 'settings'); // Inclui settings

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
            // Determina qual feedback usar baseado na aba ativa
            let feedbackEl = actionsFeedback; // Default
            if (currentActiveSectionId === 'admin-configuracoes') feedbackEl = settingsFeedback;
            else if (currentActiveSectionId === 'admin-watchlist') feedbackEl = watchlistListFeedback || watchlistAddFeedback; // Tenta os dois
            else if (currentActiveSectionId === 'admin-geral') feedbackEl = geralFeedback;
            else if (currentActiveSectionId === 'admin-db') feedbackEl = dbFeedback;

            displayFeedback(feedbackEl, `Erro: ${error.message}`, true);
            throw error; // Re-throw para indicar falha
        }
    }

    // --- Funções de UI --- (sem alterações significativas)
    function displayFeedback(element, message, isError = false, duration = 4000) {
        if (!element) return;
        element.textContent = message;
        element.classList.remove('error', 'success'); // Remove ambas
        element.classList.add(isError ? 'error' : 'success'); // Adiciona a correta
        // Clear previous timeouts if any
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
                   // A API (get_settings) agora envia IDs como string,
                   // então apenas definimos o valor diretamente.
                   input.value = data[key] !== null && data[key] !== undefined ? data[key] : ''; // Handle null/undefined
                }
            }
        }
    }


    function updateDbViewer(data) {
        if (!data || data.error) {
             displayFeedback(dbFeedback, data?.error || 'Erro ao carregar dados do DB.', true);
             return; // Adiciona verificação
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
                 // Use execCommand as fallback for clipboard
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
             displayFeedback(dbFeedback, 'Erro ao carregar histórico de guerras.', true);
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
             displayFeedback(dbFeedback, 'Erro ao carregar notas de jogadores.', true);
        }
    }

    // --- Watchlist Functions --- (sem alterações)
    async function loadWatchlist() {
        if (!watchlistTableBody) return;
        watchlistTableBody.innerHTML = '<tr><td colspan="6"><div class="loading-spinner" style="margin: 10px auto; width: 20px; height: 20px;"></div></td></tr>'; // Add spinner
        try {
            const response = await fetchAdminAPI('watchlist'); // Uses GET by default
             // A resposta pode ser um objeto com erro ou um array
            if (response.error) {
                 watchlistTableBody.innerHTML = `<tr><td colspan="6" class="error-text">Erro: ${response.error}</td></tr>`;
                 displayFeedback(watchlistListFeedback, `Erro: ${response.error}`, true);
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
             // Erro já tratado por fetchAdminAPI, apenas atualiza a tabela
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
            // Error already displayed by fetchAdminAPI
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
                 // Não mostra feedback aqui, pois fetchAdminAPI já mostrou
                 button.disabled = false; // Re-enable button on error
                 button.textContent = 'Remover';
             }
        } catch (error) {
           // Error handled by fetchAdminAPI
           button.disabled = false; // Re-enable button on error
           button.textContent = 'Remover';
        }
    }

    // --- Navegação por Abas ---
    function setActiveAdminSection(newSectionId) {
        console.log(`Tentando ativar a seção: ${newSectionId}`); // Log de depuração
        if (!newSectionId || newSectionId === currentActiveSectionId) {
            console.log(`Seção '${newSectionId}' já ativa ou inválida.`);
            return;
        }

        const oldSectionEl = document.getElementById(currentActiveSectionId);
        const newSectionEl = document.getElementById(newSectionId);

        if (!newSectionEl) {
            console.warn(`Admin section with ID "${newSectionId}" not found.`);
            return;
        }

        // Esconde a seção antiga
        if (oldSectionEl) {
            oldSectionEl.classList.remove('active-section');
            console.log(`Removida classe 'active-section' de: ${currentActiveSectionId}`);
        } else {
            console.warn(`Elemento da seção antiga '${currentActiveSectionId}' não encontrado.`);
        }

        // Remove a classe ativa de todos os links
        navLinks.forEach(link => link?.classList.remove('active-nav-link'));

        // Mostra a nova seção e ativa o link
        newSectionEl.classList.add('active-section');
        console.log(`Adicionada classe 'active-section' a: ${newSectionId}`);
        const newLink = document.querySelector(`.admin-nav .nav-link[data-section="${newSectionId}"]`);
        if (newLink) {
            newLink.classList.add('active-nav-link');
            console.log(`Adicionada classe 'active-nav-link' ao link para: ${newSectionId}`);
        } else {
            console.warn(`Link de navegação para a seção '${newSectionId}' não encontrado.`);
        }

        localStorage.setItem('activeAdminSection', newSectionId);
        currentActiveSectionId = newSectionId;
    }

    // --- Carregamento Inicial e Event Listeners ---
    async function loadDataForCurrentTab() {
        console.log(`Carregando dados para a aba: ${currentActiveSectionId}`); // Log
        // Limpa feedbacks antigos ao carregar dados
        [settingsFeedback, actionsFeedback, geralFeedback, dbFeedback, watchlistAddFeedback, watchlistListFeedback].forEach(el => {
             if (el) el.textContent = '';
        });
        try {
            // Sempre busca o status geral
            const status = await fetch('/api/status').then(res => res.ok ? res.json() : { maintenance_mode: true, version: '?', error: 'Status fetch failed' }).catch(err => {
                 console.error("Falha ao buscar status:", err);
                 return { maintenance_mode: true, version: '?', error: 'Status fetch failed'};
            });
             updateStatus(status);
             if (status.error && currentActiveSectionId === 'admin-geral') { // Mostra erro se for aba geral
                 displayFeedback(geralFeedback, status.error, true);
                 return;
             }

            // Carrega dados específicos da aba ativa
            switch (currentActiveSectionId) {
                case 'admin-geral':
                    // Status já carregado
                    break;
                case 'admin-diagnostico':
                    const diagnostics = await fetchAdminAPI('diagnostics');
                    updateDiagnostics(diagnostics);
                    break;
                case 'admin-configuracoes':
                    const settings = await fetchAdminAPI('settings');
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
                     // Geralmente não há dados para carregar aqui, apenas ações
                     break;
                default:
                    console.warn(`Nenhuma lógica de carregamento definida para a aba: ${currentActiveSectionId}`);
            }
        } catch (error) {
            console.error(`Falha ao carregar dados para a aba ${currentActiveSectionId}:`, error);
            // O erro específico da API já foi mostrado por fetchAdminAPI
        }
    }

    // --- Inicialização ---

    // Define a aba ativa inicial VISUALMENTE no HTML (importante!)
    contentSections.forEach(section => {
        if (section) section.classList.toggle('active-section', section.id === currentActiveSectionId);
    });
    navLinks.forEach(link => {
        if (link) link.classList.toggle('active-nav-link', link.dataset.section === currentActiveSectionId);
    });
     console.log(`Seção ativa inicial definida como: ${currentActiveSectionId}`);

    // Adiciona listeners aos links de navegação
    navLinks.forEach((link) => {
        link?.addEventListener('click', (e) => {
            e.preventDefault(); // Impede a navegação padrão do link '#'
            const sectionId = link.dataset.section;
            if (sectionId !== currentActiveSectionId) { // Só faz algo se for uma aba diferente
                 setActiveAdminSection(sectionId);
                 // Carrega os dados da nova aba ativa
                 loadDataForCurrentTab();
            }
        });
    });


    // --- Anexar Listeners para Botões e Formulários (com verificações) ---

    if (toggleBtn) {
        toggleBtn.addEventListener('click', async () => {
            let originalText = toggleBtn.textContent;
            toggleBtn.disabled = true; toggleBtn.textContent = 'Aguarde...';
            try {
                // Endpoint direto para toggle, não precisa de 'actions'
                await fetch('/admin/toggle_maintenance', { method: 'POST' });
                 // Re-busca o status para ter certeza
                const status = await fetch('/api/status').then(res => res.ok ? res.json() : { maintenance_mode: false }).catch(()=>({ maintenance_mode: false }));
                updateStatus(status);
                displayFeedback(geralFeedback, status.maintenance_mode ? 'Modo manutenção ATIVADO.' : 'Modo manutenção DESATIVADO.');
            } catch (error) {
                console.error('Erro ao alternar modo manutenção:', error);
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
                // Endpoint direto para teste, não precisa de 'actions'
                await fetch('/admin/send_test_embed', { method: 'POST' });
                displayFeedback(geralFeedback, "Mensagem de teste enviada!");
            } catch (error) {
                 console.error('Erro ao enviar embed de teste:', error);
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
            // Process form data, converting relevant fields
            for (const [key, value] of formData.entries()) {
                
                // <<< INÍCIO DA ALTERAÇÃO (submit settings) >>>
                if (key === "auto_add_watchlist_enabled") {
                    settings[key] = value === 'true'; // Convert select string to boolean
                
                } else if ((key.includes('_id') || key.includes('channel_id')) && value.match(/^\d+$/)) {
                    // **NÃO** usa parseInt(). Envia como string para preservar precisão.
                    // O backend Python (update_settings) já espera por isso e converterá para int.
                    settings[key] = value;
                
                } else if (value.match(/^\d+$/) && !key.includes('message')) {
                     // Converte outros campos numéricos (exceto mensagem e IDs)
                     if (value !== '') settings[key] = parseInt(value, 10);
                     else settings[key] = null; 
                
                } else {
                     settings[key] = value;
                }
                // <<< FIM DA ALTERAÇÃO (submit settings) >>>
            }

            displayFeedback(settingsFeedback, 'Salvando...');
            try {
                const response = await fetchAdminAPI('settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                displayFeedback(settingsFeedback, response.message || 'Configurações salvas.');
                
                // <<< NOVO: Recarrega os dados para mostrar o valor salvo (como string) >>>
                if (response.status === 'success') {
                    const reloadedSettings = await fetchAdminAPI('settings');
                    populateSettingsForm(reloadedSettings);
                }
                // <<< FIM NOVO >>>

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

    if (addWatchlistForm) {
        addWatchlistForm.addEventListener('submit', handleAddWatchlist);
    }

    // --- Carregamento Inicial ---
    loadDataForCurrentTab(); // Carrega dados para a aba ativa ao iniciar

});
