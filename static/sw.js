/* ClashGenius Service Worker
   Estratégia:
   - Navegação: network-first, fallback para cache e offline.html
   - API (/api/* e /assets/*): network-first, fallback para cache
   - Estáticos (css/js/imagens): cache-first com atualização em segundo plano
   - Cache versionado e limpo no activate
*/
const CACHE = 'clashgenius-v34.4.0';
const PRECACHE = [
  '/painel',
  '/offline.html',
  '/site.webmanifest',
  '/static/css/style.css',
  '/static/js/utils.js',
  '/static/js/scripts.js',
  '/static/js/admin.js',
  '/static/js/pwa-install.js',
  '/static/images/android-chrome-192x192.png',
  '/static/images/android-chrome-512x512.png',
  '/static/images/maskable-192x192.png',
  '/static/images/maskable-512x512.png',
  '/static/images/apple-touch-icon.png',
  '/static/images/favicon-16x16.png',
  '/static/images/favicon-32x32.png',
  '/static/images/favicon.ico',
  '/static/images/default_badge.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Navegação de páginas: network-first, cache de reserva, offline.html por último
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
          return response;
        })
        .catch(() =>
          caches.match(request).then((cached) =>
            cached || caches.match('/offline.html')
          )
        )
    );
    return;
  }

  // Dados da API: network-first com cache de reserva
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/assets/')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
          }
          return response;
        })
        .catch(() =>
          caches.match(request).then((cached) =>
            cached || new Response(JSON.stringify({ status: 'offline' }), {
              status: 503,
              headers: { 'Content-Type': 'application/json' }
            })
          )
        )
    );
    return;
  }

  // Estáticos: cache-first
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
          }
        }).catch(() => {});
        return cached;
      }
      return fetch(request).then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {});
        }
        return response;
      });
    })
  );
});
