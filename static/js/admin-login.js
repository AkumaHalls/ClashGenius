// admin_login.html — lógica da tela de acesso (externo para CSP sem 'unsafe-inline')
document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('particle-background');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        class Particle {
            constructor() { this.reset(); }
            reset() {
                this.x = Math.random() * canvas.width;
                this.y = Math.random() * canvas.height;
                this.size = Math.random() * 2 + 0.5;
                this.speedX = (Math.random() - 0.5) * 0.3;
                this.speedY = (Math.random() - 0.5) * 0.3;
                this.opacity = Math.random() * 0.5 + 0.1;
            }
            update() {
                this.x += this.speedX;
                this.y += this.speedY;
                if (this.x < 0 || this.x > canvas.width || this.y < 0 || this.y > canvas.height) this.reset();
            }
            draw() {
                ctx.fillStyle = `rgba(0, 200, 255, ${this.opacity})`;
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
                ctx.fill();
            }
        }
        const particles = Array.from({ length: 80 }, () => new Particle());
        function animate() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            particles.forEach(p => { p.update(); p.draw(); });
            requestAnimationFrame(animate);
        }
        animate();
    }

    const urlParams = new URLSearchParams(window.location.search);
    const guildId = urlParams.get('guild_id');
    if (guildId) document.getElementById('login-guild-id').value = guildId;
    if (urlParams.has('error')) document.getElementById('login-feedback').textContent = 'ACESSO NEGADO: Senha incorreta.';
});

function showRegister() {
    document.getElementById('login-form-section').style.display = 'none';
    document.getElementById('forgot-form-section').style.display = 'none';
    document.getElementById('register-form-section').classList.add('active');
    document.getElementById('register-form-section').style.display = 'block';
}

function showLogin() {
    document.getElementById('register-form-section').style.display = 'none';
    document.getElementById('forgot-form-section').style.display = 'none';
    document.getElementById('login-form-section').style.display = 'block';
}

function showForgot() {
    document.getElementById('login-form-section').style.display = 'none';
    document.getElementById('register-form-section').style.display = 'none';
    document.getElementById('forgot-form-section').classList.add('active');
    document.getElementById('forgot-form-section').style.display = 'block';
    setTimeout(() => document.getElementById('forgot-username').focus(), 100);
}

async function doLogin() {
    const username = document.getElementById('login-username').value.trim().toLowerCase();
    const password = document.getElementById('login-password').value;
    const guildId = document.getElementById('login-guild-id').value;
    const fb = document.getElementById('login-feedback');
    if (!username || !password) { fb.textContent = 'Preencha usuario e senha.'; return; }
    fb.textContent = 'Autenticando...';
    try {
        const resp = await fetch('/api/admin/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, guild_id: guildId })
        });
        const data = await resp.json();
        if (data.status === 'success') {
            window.location.href = '/admin/panel';
        } else {
            fb.textContent = data.message || 'Falha na autenticacao.';
        }
    } catch (e) {
        fb.textContent = 'Erro de conexao com o servidor.';
    }
}

async function doRegister() {
    const username = document.getElementById('reg-username').value.trim().toLowerCase();
    const password = document.getElementById('reg-password').value;
    const discord = document.getElementById('reg-discord').value.trim();
    const fb = document.getElementById('register-feedback');
    if (!username || !password) { fb.textContent = 'Preencha usuario e senha.'; return; }
    if (username.length < 3) { fb.textContent = 'Usuario deve ter no minimo 3 caracteres.'; return; }
    if (password.length < 8) { fb.textContent = 'Senha deve ter no minimo 8 caracteres.'; return; }
    fb.textContent = 'Enviando solicitacao...';
    try {
        const resp = await fetch('/api/admin/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, discord })
        });
        const data = await resp.json();
        fb.textContent = data.status === 'success' ? data.message : (data.message || 'Erro ao solicitar.');
        if (data.status === 'success') {
            document.getElementById('reg-username').value = '';
            document.getElementById('reg-password').value = '';
            document.getElementById('reg-discord').value = '';
        }
    } catch (e) {
        fb.textContent = 'Erro de conexao com o servidor.';
    }
}

async function doForgotPassword() {
    const username = document.getElementById('forgot-username').value.trim().toLowerCase();
    const fb = document.getElementById('forgot-feedback');
    if (!username) { fb.textContent = 'Informe o usuário.'; return; }
    fb.textContent = 'Enviando solicitação...';
    try {
        const resp = await fetch('/api/admin/auth/forgot-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const data = await resp.json();
        fb.textContent = data.message || 'Solicitação registrada.';
        if (data.status === 'success') {
            document.getElementById('forgot-username').value = '';
        }
    } catch (e) {
        fb.textContent = 'Erro de conexao com o servidor.';
    }
}

function useMasterPassword() {
    document.getElementById('login-form-section').style.display = 'none';
    document.getElementById('register-form-section').style.display = 'none';
    document.getElementById('forgot-form-section').style.display = 'none';
    document.querySelector('.login-card').style.display = 'none';
    document.getElementById('master-password-section').style.display = 'block';
    document.getElementById('mp-guild-id').value = document.getElementById('login-guild-id').value;
    setTimeout(() => document.querySelector('#master-password-section input[type="password"]').focus(), 100);
}

const ACTIONS = {
    'login': doLogin,
    'register': doRegister,
    'forgot-password': doForgotPassword,
    'show-login': showLogin,
    'show-register': showRegister,
    'show-forgot': showForgot,
    'use-master-password': useMasterPassword,
    'reload': () => window.location.reload(),
};

document.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-action]');
    if (!trigger) return;
    const action = ACTIONS[trigger.dataset.action];
    if (action) action(event);
});

if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
}
