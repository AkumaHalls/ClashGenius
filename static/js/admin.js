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

    // Lógica para o painel de administração
    const toggleBtn = document.getElementById('toggle-maintenance-btn');
    const testBtn = document.getElementById('send-test-embed-btn');
    const statusTextEl = document.getElementById('maintenance-status-text');
    const botVersionEl = document.getElementById('bot-version-text');

    async function fetchAdminStatus() {
        if (!statusTextEl) return;
        try {
            const response = await fetch('/api/admin/status');
            const data = await response.json();
            if (data.maintenance_mode) {
                statusTextEl.textContent = 'ATIVADO';
                statusTextEl.className = 'status-badge status-on';
            } else {
                statusTextEl.textContent = 'DESATIVADO';
                statusTextEl.className = 'status-badge status-off';
            }
            if(botVersionEl) botVersionEl.textContent = data.version || '-';
        } catch (error) {
            statusTextEl.textContent = 'Erro';
            statusTextEl.className = 'status-badge';
            console.error('Erro ao buscar status do admin:', error);
        }
    }

    if (toggleBtn) {
        toggleBtn.addEventListener('click', async () => {
            try {
                toggleBtn.disabled = true;
                toggleBtn.textContent = 'Aguarde...';
                await fetch('/admin/toggle_maintenance', { method: 'POST' });
                await fetchAdminStatus();
            } catch (error) {
                console.error('Erro ao alternar modo manutenção:', error);
                alert('Ocorreu um erro. Verifique o console.');
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
                const response = await fetch('/admin/send_test_embed', { method: 'POST' });
                const data = await response.json();
                if(data.status === 'success') {
                    alert('Mensagem de teste enviada com sucesso!');
                } else {
                    alert('Falha ao enviar mensagem: ' + (data.message || 'Erro desconhecido'));
                }
            } catch (error) {
                console.error('Erro ao enviar embed de teste:', error);
                alert('Ocorreu um erro. Verifique o console.');
            } finally {
                testBtn.disabled = false;
                testBtn.textContent = 'Enviar Mensagem de Teste';
            }
        });
    }
    
    // Carregar o status inicial ao carregar a página do painel
    if(document.body.classList.contains('admin-page') && window.location.pathname.includes('panel')) {
        fetchAdminStatus();
        setInterval(fetchAdminStatus, 15000); // Atualiza o status a cada 15 segundos
    }

    // Efeito de partículas no fundo (reutilizado de scripts.js)
    const particleCanvas = document.getElementById('particle-background');
    if (particleCanvas) {
       // ... (código das partículas pode ser colado aqui se quiser fundo animado também)
    }
});
