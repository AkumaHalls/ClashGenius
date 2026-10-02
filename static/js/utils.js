// Utilitários compartilhados entre scripts.js e admin.js

function escapeHtml(str) {
    const map = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
    return String(str).replace(/[&<>"']/g, c => map[c]);
}

// Fetch para a API admin com CSRF automático em mutations
async function fetchAdminAPI(path, options = {}) {
    const url = '/api/admin/' + path;
    const opts = { credentials: 'include', ...options };
    const method = (opts.method || 'GET').toUpperCase();
    if (method !== 'GET' && method !== 'HEAD') {
        opts.headers = { ...opts.headers };
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content) opts.headers['X-CSRF-Token'] = meta.content;
    }
    const resp = await fetch(url, opts);
    const data = await resp.json().catch(() => null);
    if (!resp.ok) {
        throw new Error((data && data.message) || ('HTTP ' + resp.status));
    }
    return data;
}

// Menu hambúrguer responsivo (público + admin)
document.addEventListener('DOMContentLoaded', function () {
    const toggle = document.getElementById('nav-toggle');
    if (!toggle) return;
    const nav = toggle.closest('.admin-header, .header-content')
        ? toggle.nextElementSibling
        : document.querySelector('.main-nav, .admin-nav');
    const menu = nav ? nav.querySelector('ul') : null;
    if (!menu) return;

    function closeMenu() {
        toggle.setAttribute('aria-expanded', 'false');
        menu.classList.remove('open');
    }

    toggle.addEventListener('click', function (e) {
        e.stopPropagation();
        const open = menu.classList.toggle('open');
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });

    menu.querySelectorAll('a').forEach(function (link) {
        link.addEventListener('click', closeMenu);
    });

    document.addEventListener('click', function (e) {
        if (!e.target.closest('.main-nav, .admin-nav, .nav-toggle')) closeMenu();
    });

    window.addEventListener('resize', function () {
        if (window.innerWidth > 768) closeMenu();
    });
});

// Registro do Service Worker (PWA)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
        navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(function () {});
    });
}

