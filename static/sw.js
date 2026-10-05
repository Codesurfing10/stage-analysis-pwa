/* Offline shell only — /api/* is always network-first and never cached */
const CACHE = "stage-pwa-shell-v4";
const SHELL = ["/", "/static/app.css", "/static/app.js", "/manifest.webmanifest", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

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
  const url = new URL(event.request.url);
  // API JSON must never be served from Cache Storage — network-first, no put.
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request, { cache: "no-store" }).catch(
        () =>
          new Response(JSON.stringify({ detail: "offline" }), {
            status: 503,
            headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
          })
      )
    );
    return;
  }

  // Shell: network-first so daily UI updates propagate; fall back to cache offline.
  if (event.request.method !== "GET") {
    return;
  }
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(event.request))
  );
});
