// Lets the phone install the app from its own address. Always goes to the network first (your plan changes daily),
// and keeps a copy of the page, its files and today's plan. When the add-on can't be reached, the app opens from that
// copy so you can keep logging (the page holds your sets until it can send them). With no copy yet, it shows a short
// offline page instead of a browser error, drawn like the app: a teal letterhead over paper, light or dark with the phone.
const CACHE = "workouts-offline-1";
const KEEP = (url) => url.origin === self.location.origin
  && (url.pathname.includes("/static/") || url.pathname.endsWith("/api/plan") || url.pathname.endsWith("/api/status"));

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(
  caches.keys().then((keys) => Promise.all(keys.filter((k) => k.startsWith("workouts-") && k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim())));

// Network first; a good answer replaces the kept copy, and the copy is used only when the network fails
async function networkFirst(request, cacheKey) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(request);
    if (res.ok) cache.put(cacheKey || request, res.clone());
    return res;
  } catch (err) {
    const kept = await cache.match(cacheKey || request);
    if (kept) return kept;
    throw err;
  }
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (req.mode === "navigate") {
    // one copy of the page, whatever the address bar says (the home-screen icon may add ?source=pwa)
    e.respondWith(networkFirst(req, new URL("./", self.registration.scope).href).catch(offlinePage));
    return;
  }
  if (KEEP(url)) e.respondWith(networkFirst(req));
});

function offlinePage() {
  return new Response(
    `<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1"><title>Workouts</title>
     <style>
       :root { --paper: #fafaf7; --ink: #1b232d; --ink-2: #4d5763; --teal: #0e6a70; --rule: #26303b; --sheet: #fff; }
       @media (prefers-color-scheme: dark) { :root { --paper: #121619; --ink: #e8eae5; --ink-2: #a7b0ba; --teal: #0f5d62; --rule: #c5cbd1; --sheet: #1a1f24; } }
       body { margin: 0; font: 16px/1.45 "Atkinson Hyperlegible Next", system-ui, sans-serif; background: var(--paper); color: var(--ink); }
       header { background: var(--teal); color: #fff; padding: 22px 16px 18px; font-size: 1.6rem; font-weight: 800; }
       main { padding: 22px 16px; max-width: 560px; }
       h1 { font-size: 1.1rem; margin: 0 0 6px; padding-bottom: 5px; border-bottom: 1.5px solid var(--rule); }
       p { color: var(--ink-2); margin: 10px 0 18px; }
       button { font: inherit; font-weight: 800; min-height: 48px; padding: 0 18px; border-radius: 3px; border: 1.5px solid var(--teal);
         background: var(--teal); color: #fff; cursor: pointer; }
     </style>
     <header>Workouts</header>
     <main><h1>Can't reach Home Assistant</h1>
       <p>This app works on your home Wi-Fi (or VPN). Check the connection and try again.</p>
       <button onclick="location.reload()">Try again</button></main>`,
    { headers: { "Content-Type": "text/html; charset=utf-8" } });
}
