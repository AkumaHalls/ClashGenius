// maintenance.html — polling de status (externo para CSP)
document.addEventListener('DOMContentLoaded', () => {
    const messageEl = document.getElementById('maintenance-message');
    const botTextEl = document.getElementById('bot-status-text');
    const botDotEl = document.getElementById('bot-status-dot');
    const cocTextEl = document.getElementById('coc-status-text');
    const cocDotEl = document.getElementById('coc-status-dot');
    let attempts = 0;

    const setStatus = (el, dot, text, color, dotBg, dotShadow) => {
        el.textContent = text;
        el.style.color = color;
        if (dot) { dot.style.background = dotBg; dot.style.boxShadow = dotShadow; }
    };

    const checkStatus = async () => {
        attempts++;
        const dots = '.'.repeat((attempts % 3) + 1);
        setStatus(botTextEl, botDotEl, 'BOT: VERIFICANDO' + dots, 'var(--neon-yellow)', 'var(--neon-yellow)', '0 0 10px var(--neon-yellow)');
        setStatus(cocTextEl, cocDotEl, 'API CoC: VERIFICANDO' + dots, 'var(--neon-yellow)', 'var(--neon-yellow)', '0 0 10px var(--neon-yellow)');

        try {
            const [statusResp, cocResp] = await Promise.all([
                fetch('/api/status', { cache: 'no-store' }).catch(() => null),
                fetch('/api/coc_status', { cache: 'no-store' }).catch(() => null)
            ]);

            if (statusResp && statusResp.ok) {
                const data = await statusResp.json();
                const versionEl = document.getElementById('version-display');
                if (versionEl && data.version) versionEl.textContent = data.version;
                if (data.maintenance_mode === false || !data.maintenance_mode) {
                    setStatus(botTextEl, botDotEl, 'BOT: OPERACIONAL', 'var(--neon-green)', 'var(--neon-green)', '0 0 10px var(--neon-green)');
                    setTimeout(() => { window.location.href = '/painel'; }, 2000);
                    return;
                }
                setStatus(botTextEl, botDotEl, 'BOT: MANUTENÇÃO ATIVA', 'var(--neon-yellow)', 'var(--neon-yellow)', '0 0 10px var(--neon-yellow)');
                if (data.maintenance_message && messageEl) {
                    // textContent: mensagem vem do banco e não deve ser interpretada como HTML.
                    messageEl.textContent = data.maintenance_message;
                }
            } else {
                setStatus(botTextEl, botDotEl, 'BOT: OFFLINE', 'var(--neon-red)', 'var(--neon-red)', '0 0 10px var(--neon-red)');
                if (messageEl) messageEl.textContent = 'Servidor do Clash Genius está offline. Tentando reconectar...';
            }

            if (cocResp && cocResp.ok) {
                const cocData = await cocResp.json();
                if (cocData.status === 'ok') {
                    setStatus(cocTextEl, cocDotEl, 'API CoC: ONLINE', 'var(--neon-green)', 'var(--neon-green)', '0 0 10px var(--neon-green)');
                } else if (cocData.status === 'maintenance') {
                    setStatus(cocTextEl, cocDotEl, 'API CoC: MANUTENÇÃO SUPERCELL', 'var(--neon-orange)', 'var(--neon-orange)', '0 0 10px var(--neon-orange)');
                } else {
                    setStatus(cocTextEl, cocDotEl, 'API CoC: INDISPONÍVEL', 'var(--neon-red)', 'var(--neon-red)', '0 0 10px var(--neon-red)');
                }
            } else {
                setStatus(cocTextEl, cocDotEl, 'API CoC: SEM RESPOSTA', 'var(--neon-red)', 'var(--neon-red)', '0 0 10px var(--neon-red)');
            }
        } catch (error) {
            console.error('Erro ao verificar status:', error);
            if (messageEl) messageEl.textContent = 'Não foi possível conectar ao servidor do Clash Genius.';
        }
    };

    checkStatus();
    setInterval(checkStatus, 15000);
});
