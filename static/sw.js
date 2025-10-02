const CACHE_NAME = 'library-cache-v1';
// Add the URLs of all your core pages and assets to this list.
const urlsToCache = [
  '/',
  '/student_login',
  '/student_register',
  '/static/icon-192x192.png',
  '/static/icon-512x512.png'
  // We don't cache librarian pages as they are less frequently used on the go.
];

// Install the service worker and cache the app shell
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

// Intercept network requests and serve from cache if available
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Cache hit - return response from cache
        if (response) {
          return response;
        }
        // Not in cache - fetch from network
        return fetch(event.request);
      }
    )
  );
});