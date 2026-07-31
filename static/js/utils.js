// Utilitários compartilhados entre scripts.js e admin.js

function escapeHtml(str) {
    const map = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
    return String(str).replace(/[&<>"']/g, c => map[c]);
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

