/* ClashGenius - Instalação como App (PWA)
   - Android/Chrome: captura beforeinstallprompt e mostra botão "Instalar App"
   - iOS Safari: não tem beforeinstallprompt; mostra dica de "Adicionar à Tela de Início"
   - Esconde o botão quando o app já está instalado ou rodando standalone
*/
(function () {
    'use strict';

    var deferredPrompt = null;
    var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;
    var isStandalone = window.matchMedia && window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

    function installButton() {
        return document.getElementById('pwa-install-btn');
    }

    function showButton() {
        if (isStandalone) return;
        if (installButton()) return;
        var btn = document.createElement('button');
        btn.id = 'pwa-install-btn';
        btn.className = 'pwa-install-btn';
        btn.textContent = '📲 Instalar App';
        btn.setAttribute('aria-label', 'Instalar o ClashGenius como aplicativo');
        btn.addEventListener('click', function () {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then(function () { deferredPrompt = null; });
            } else if (isIOS) {
                showIosHint();
            }
        });
        document.body.appendChild(btn);
    }

    function hideButton() {
        var btn = installButton();
        if (btn) btn.remove();
    }

    function showIosHint() {
        var overlay = document.createElement('div');
        overlay.className = 'pwa-install-modal';
        overlay.innerHTML =
            '<div class="pwa-install-modal-content">' +
            '<button class="pwa-install-modal-close" aria-label="Fechar">&times;</button>' +
            '<div class="pwa-install-modal-icon">📲</div>' +
            '<h3>Instalar no iPhone/iPad</h3>' +
            '<ol>' +
            '<li>Toque no botão <b>Compartilhar</b> <span>⬆️</span> no Safari</li>' +
            '<li>Role até <b>Adicionar à Tela de Início</b></li>' +
            '<li>Toque em <b>Adicionar</b></li>' +
            '</ol>' +
            '<p class="pwa-install-modal-note">O ClashGenius vira um app com ícone na tela inicial.</p>' +
            '</div>';
        overlay.addEventListener('click', function (e) {
            if (e.target === overlay || e.target.classList.contains('pwa-install-modal-close')) {
                overlay.remove();
            }
        });
        document.body.appendChild(overlay);
    }

    window.addEventListener('beforeinstallprompt', function (e) {
        e.preventDefault();
        deferredPrompt = e;
        showButton();
    });

    window.addEventListener('appinstalled', function () {
        deferredPrompt = null;
        hideButton();
    });

    window.addEventListener('load', function () {
        if (isStandalone) return;
        if (isIOS) {
            setTimeout(showButton, 5000);
        } else if (window.chrome) {
            // Chrome no desktop só dispara beforeinstallprompt sob critérios do navegador
        }
    });
})();
