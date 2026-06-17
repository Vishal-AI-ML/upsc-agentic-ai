/* UPSC AI service worker - app shell caching for installable PWA */
const CACHE = "upscai-shell-v2";
const CORE = [
  "./app-frontend.html",
  "./manifest.json",
  "./icon-192.webp",
  "./icon-512.webp",
];

// Pre-cache the app shell on install (best-effort; never fail the install).
self.addEventListener("install", (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(CORE).catch(() => {}))
  );
});

// Drop old caches when a new SW version activates.
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;

  // Only handle GET; never touch POST (API calls, auth, etc.).
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // Only manage same-origin assets. Let the browser handle cross-origin
  // requests directly (backend API, CDN libraries, YouTube, etc.).
  if (url.origin !== self.location.origin) return;

  // Navigations: network-first so fresh deploys win, fall back to cached shell.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match("./app-frontend.html"))
    );
    return;
  }

  // Static same-origin assets: cache-first, then network (and cache it).
  event.respondWith(
    caches.match(req).then((cached) => {
      if (cached) return cached;
      return fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((cache) => cache.put(req, copy).catch(() => {}));
        return res;
      });
    })
  );
});
