// Lets the phone install the app from its own address. Always goes to the network (your plan changes daily);
// only when the add-on can't be reached does it show a short offline page instead of a browser error,
// drawn like the app: a teal letterhead over paper, light or dark with the phone.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;
  e.respondWith(fetch(e.request).catch(() => new Response(
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
    { headers: { "Content-Type": "text/html; charset=utf-8" } })));
});
