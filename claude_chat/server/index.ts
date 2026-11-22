import http from 'node:http'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import express from 'express'
import { WebSocketServer } from 'ws'
import { config } from './config.ts'
import { Hub } from './hub.ts'
import * as auth from './auth.ts'
import * as ha from './ha.ts'
import { getSettings, updateSettings } from './settings.ts'
import type { AppState, ClientMsg } from '../shared/types.ts'

const here = path.dirname(fileURLToPath(import.meta.url))
const dist = path.join(here, '..', 'dist')
const hub = new Hub()
const app = express()
app.disable('x-powered-by')
app.use(express.json({ limit: '30mb' }))

// Only Home Assistant's ingress proxy may talk to the add-on: the page has
// no login of its own and Claude can change the configuration.
const INGRESS = new Set(['172.30.32.2', '127.0.0.1', '::1'])
function allowed(addr: string | undefined): boolean {
  if (!config.onHA) return true
  const a = (addr ?? '').replace(/^::ffff:/, '')
  return INGRESS.has(a)
}

app.use((req, res, next) => {
  if (!allowed(req.socket.remoteAddress)) {
    res.status(403).send('Open Claude Chat from the Home Assistant sidebar.')
    return
  }
  const name = req.get('X-Remote-User-Display-Name') || req.get('X-Remote-User-Name')
  if (name) hub.userName = name
  next()
})

const wrap = (fn: (req: express.Request, res: express.Response) => Promise<unknown> | unknown) => async (req: express.Request, res: express.Response) => {
  try {
    const out = await fn(req, res)
    if (!res.headersSent) res.json(out ?? { ok: true })
  } catch (e: any) {
    console.error(req.method, req.path, e)
    if (!res.headersSent) res.status(500).json({ error: e.message ?? String(e) })
  }
}

async function appState(): Promise<AppState> {
  const [authI, services, self] = await Promise.all([auth.authInfo(), ha.notifyServices().catch(() => []), ha.haConnected() ? ha.selfInfo() : Promise.resolve({ slug: 'claude_chat' })])
  return {
    auth: authI,
    user: hub.userName.split(' ')[0] || '',
    models: hub.models,
    commands: hub.commands,
    defaults: hub.defaults(),
    usage: hub.usageInfo,
    settings: getSettings(),
    ha: { connected: ha.haConnected(), slug: self.slug, notifyServices: services, demo: config.demo },
    workDir: config.workDir,
    version: config.version,
  }
}

app.get('/api/state', wrap(() => appState()))
app.get('/api/chats', wrap(() => hub.listChats()))
app.get('/api/home', wrap((req) => ha.homeCards(req.query.refresh === '1')))
app.get('/api/mentions', wrap((req) => ha.searchMentions(String(req.query.q ?? ''))))

app.post('/api/chats/:id/rename', wrap(async (req) => hub.rename(String(req.params.id), String(req.body?.title ?? ''))))
app.delete('/api/chats/:id', wrap(async (req) => hub.remove(String(req.params.id))))
app.post('/api/chats/:id/undo', wrap(async (req, res) => {
  const chat = await hub.open(String(req.params.id))
  if (!chat) return res.status(404).json({ error: 'Chat not found' })
  return chat.undo(String(req.body?.toolUseId ?? ''), Boolean(req.body?.force))
}))

app.put('/api/settings', wrap((req) => updateSettings(req.body ?? {})))
app.post('/api/notify/test', wrap(async () => {
  const s = getSettings()
  if (!s.notifyService) return { ok: false, error: 'Pick a phone first.' }
  const ok = await ha.notify(s.notifyService, 'Claude Chat', 'Notifications work. You’ll hear from Claude here when it needs you.')
  return ok ? { ok } : { ok, error: 'Home Assistant didn’t accept the notification. Check the service name.' }
}))
app.post('/api/health/run', wrap(async () => {
  const chat = await hub.runHealthCheck()
  return chat ? { ok: true, chatId: chat.id } : { ok: false, error: 'Sign in to Claude first.' }
}))

// House memory: CLAUDE.md in the working folder, read by Claude Code in every chat
const memoryFile = () => path.join(config.workDir, 'CLAUDE.md')
app.get('/api/memory', wrap(() => ({ path: memoryFile(), text: fs.existsSync(memoryFile()) ? fs.readFileSync(memoryFile(), 'utf8') : '' })))
app.put('/api/memory', wrap((req) => {
  const text = String(req.body?.text ?? '')
  fs.writeFileSync(memoryFile(), text.endsWith('\n') || !text ? text : text + '\n')
  return { ok: true }
}))

app.get('/api/auth', wrap(async () => ({ info: await auth.authInfo(0), signIn: auth.signInState() })))
app.post('/api/auth/start', wrap(() => auth.startSignIn()))
app.post('/api/auth/code', wrap((req) => auth.sendSignInCode(String(req.body?.code ?? ''))))
app.post('/api/auth/cancel', wrap(() => auth.cancelSignIn()))
app.post('/api/auth/token', wrap(async (req) => {
  const r = auth.saveCredential(String(req.body?.value ?? ''))
  if (r.ok) {
    hub.initDone = false
    void hub.warmUp()
  }
  return r
}))
app.post('/api/auth/signout', wrap(() => auth.signOut()))

if (fs.existsSync(dist)) {
  app.use(express.static(dist, { index: false, maxAge: '1h' }))
  app.get(/^(?!\/api\/).*/, (_req, res) => {
    res.set('Cache-Control', 'no-cache')
    res.sendFile(path.join(dist, 'index.html'))
  })
}

const server = http.createServer(app)
const wss = new WebSocketServer({ noServer: true, maxPayload: 40 * 1024 * 1024 })

server.on('upgrade', (req, socket, head) => {
  if (!allowed(req.socket.remoteAddress) || !(req.url ?? '').split('?')[0].endsWith('/ws')) {
    socket.destroy()
    return
  }
  wss.handleUpgrade(req, socket, head, (ws) => wss.emit('connection', ws, req))
})

wss.on('connection', async (ws) => {
  const client = hub.addClient(ws)
  hub.send(client, { t: 'chats', chats: await hub.listChats() })
  ws.on('message', async (raw) => {
    let msg: ClientMsg
    try {
      msg = JSON.parse(String(raw))
    } catch {
      return
    }
    try {
      await handle(client, msg)
    } catch (e: any) {
      console.error('ws', msg.t, e)
      hub.send(client, { t: 'error', text: e.message ?? String(e) })
    }
  })
})

async function handle(client: ReturnType<Hub['addClient']>, msg: ClientMsg): Promise<void> {
  switch (msg.t) {
    case 'subscribe': {
      client.chatId = msg.chatId
      if (!msg.chatId) return
      const chat = await hub.open(msg.chatId)
      if (!chat) return hub.send(client, { t: 'error', text: 'That chat no longer exists.' })
      hub.send(client, { t: 'snapshot', chatId: chat.id, title: chat.title, items: chat.items, status: chat.status, model: chat.model, effort: chat.effort, mode: chat.mode })
      return
    }
    case 'send': {
      const text = msg.text.trim()
      if (!text && !msg.images?.length) return
      let chat = msg.chatId ? await hub.open(msg.chatId) : null
      if (!chat) {
        chat = hub.newChat({ model: msg.model, effort: msg.effort, mode: msg.mode })
        client.chatId = chat.id
        hub.send(client, { t: 'snapshot', chatId: chat.id, title: chat.title, items: [], status: 'idle', model: chat.model, effort: chat.effort, mode: chat.mode })
      } else if (msg.model || msg.effort || msg.mode) {
        await chat.applySettings({ model: msg.model, effort: msg.effort, mode: msg.mode })
      }
      await chat.send(text, msg.images ?? [], msg.mentions ?? [])
      hub.pushChats()
      return
    }
    case 'stop':
      await hub.chats.get(msg.chatId)?.stop()
      return
    case 'approve':
      hub.chats.get(msg.chatId)?.decide(msg.id, msg.decision, msg.reason)
      return
    case 'answer':
      hub.chats.get(msg.chatId)?.answer(msg.id, msg.answers)
      return
    case 'plan':
      await hub.chats.get(msg.chatId)?.decidePlan(msg.id, msg.decision, msg.feedback)
      return
    case 'settings': {
      const chat = await hub.open(msg.chatId)
      await chat?.applySettings(msg)
      return
    }
    case 'visible':
      client.visible = Boolean(msg.visible)
      return
  }
}

server.listen(config.port, () => {
  console.log(`Claude Chat ${config.version} on port ${config.port}; working folder ${config.workDir}${config.demo ? ' (sample Home Assistant data)' : ''}`)
  void hub.warmUp()
  // Fetch ha-mcp and its Python once in the background, so the first chat's MCP start is quick
  if (config.enableHaMcp && config.supervisorToken) {
    const warm = spawn('uvx', ['--python', '3.13', '--index-strategy', 'unsafe-best-match', '--from', `ha-mcp@${config.haMcpVersion}`, 'python', '-c', ''], { env: auth.claudeEnv(false), stdio: 'ignore' })
    warm.on('error', (e) => console.error('ha-mcp warm-up failed:', e.message))
    warm.on('close', (code) => console.log(code === 0 ? `ha-mcp ${config.haMcpVersion} ready` : `ha-mcp warm-up exited with ${code}; Claude will retry when a chat starts`))
  }
})

setInterval(() => hub.sweep(), 10 * 60 * 1000).unref()
setInterval(() => void hub.healthTick().catch((e) => console.error('health check', e)), 60 * 1000).unref()

for (const sig of ['SIGTERM', 'SIGINT'] as const) {
  process.on(sig, () => {
    for (const c of hub.chats.values()) c.close()
    process.exit(0)
  })
}
