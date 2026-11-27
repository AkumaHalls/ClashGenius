// trocar_senha.html — fluxo de definição de senha (externo para CSP)
document.addEventListener('DOMContentLoaded', async () => {
    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.content : '';

    const form = document.getElementById('change-password-form');
    const fb = document.getElementById('change-password-feedback');
    if (!form || !fb) return;

    try {
        const resp = await fetch('/api/admin/auth/me', { credentials: 'include' });
        if (resp.ok) {
            const data = await resp.json();
            const usernameInput = document.getElementById('cp-username');
            if (usernameInput) usernameInput.value = data.username || '';
        }
    } catch (e) { /* sessão limitada pode não expor /me */ }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        fb.textContent = 'Definindo senha...';
        fb.style.color = '';

        const newPass = document.getElementById('cp-new-password').value;
        const confirmPass = document.getElementById('cp-confirm-password').value;

        if (!newPass || !confirmPass) {
            fb.textContent = 'Preencha ambos os campos.';
            fb.style.color = '#e74c3c';
            return;
        }
        if (newPass !== confirmPass) {
            fb.textContent = 'As senhas não conferem.';
            fb.style.color = '#e74c3c';
            return;
        }
        if (newPass.length < 8) {
            fb.textContent = 'A senha deve ter no mínimo 8 caracteres.';
            fb.style.color = '#e74c3c';
            return;
        }

        try {
            const resp = await fetch('/api/admin/auth/change-password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                credentials: 'include',
                body: JSON.stringify({ new_password: newPass, confirm_password: confirmPass })
            });
            const data = await resp.json();
            fb.textContent = data.message || (data.status === 'success' ? 'Senha alterada! Redirecionando...' : 'Erro ao alterar.');
            fb.style.color = data.status === 'success' ? '#2ecc71' : '#e74c3c';
            if (data.status === 'success') {
                setTimeout(() => window.location.href = '/admin/panel', 1500);
            }
        } catch (e) {
            fb.textContent = 'Erro de conexão com o servidor.';
            fb.style.color = '#e74c3c';
        }
    });
});
