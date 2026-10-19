// Lets the phone install the app from its own address. Always goes to the network (your plan changes daily);
// only when the add-on can't be reached does it show a short offline page instead of a browser error.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;
  e.respondWith(fetch(e.request).catch(() => new Response(
    `<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1"><title>Workouts</title>
     <body style="font:16px system-ui;background:#0f1216;color:#e9edf2;display:grid;place-items:center;min-height:90vh;text-align:center;padding:16px">
     <div><h2>Can't reach Home Assistant</h2><p>This app works on your home Wi-Fi (or VPN). Check the connection and try again.</p>
     <button onclick="location.reload()" style="font:inherit;padding:10px 18px;border-radius:12px;border:0;background:#ff7a3d">Try again</button></div>`,
    { headers: { "Content-Type": "text/html; charset=utf-8" } })));
});
