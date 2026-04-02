// Minimal Service Worker to resolve "POST unsupported" and "206 Partial Content" errors.
const CACHE_NAME = 'infracontrol-cache-v1';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
    // 1. NE PAS mettre en cache les requêtes POST
    if (event.request.method === 'POST') {
        return; // Laisser passer sans cache
    }

    event.respondWith(
        fetch(event.request)
            .then((response) => {
                // 2. NE PAS mettre en cache les réponses partielles (status 206)
                // Cela cause des erreurs "Partial response is unsupported" dans Cache API
                if (!response || response.status !== 200 || response.type !== 'basic') {
                    return response;
                }

                // Pour les requêtes standards GET 200, on peut mettre en cache
                const responseToCache = response.clone();
                caches.open(CACHE_NAME).then((cache) => {
                    cache.put(event.request, responseToCache);
                });

                return response;
            })
            .catch(() => {
                // Fallback si réseau coupé
                return caches.match(event.request);
            })
    );
});
