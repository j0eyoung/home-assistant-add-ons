import { spawn, type ChildProcess } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { config } from './config.ts'
import type { AuthInfo } from '../shared/types.ts'

// Which Claude credential the chats use, in this order:
//   1. a token or API key saved from this page (/data/auth.json)
//   2. claude_code_oauth_token from the add-on options (or addon_secrets.json)
//   3. a full `claude auth login` kept in Claude Code's own HOME
// Sign-in from the page runs `claude setup-token` inside a pseudo-terminal:
// Claude Code only shows its paste-the-code prompt on a real terminal.

const AUTH_FILE = path.join(config.dataDir, 'auth.json')
const PTY_HELPER = path.join(path.dirname(fileURLToPath(import.meta.url)), 'pty_helper.py')
const require = createRequire(import.meta.url)

type Saved = { type: 'token' | 'api_key'; value: string; savedAt: string }

function readSaved(): Saved | null {
  try {
    const s = JSON.parse(fs.readFileSync(AUTH_FILE, 'utf8'))
    return s && typeof s.value === 'string' && s.value ? s : null
  } catch {
    return null
  }
}

function writeSaved(s: Saved | null): void {
  if (!s) {
    fs.rmSync(AUTH_FILE, { force: true })
  } else {
    fs.writeFileSync(AUTH_FILE, JSON.stringify(s), { mode: 0o600 })
  }
  statusCache = null
}

// The Claude Code binary the Agent SDK installed for this platform.
export function claudeBin(): string {
  if (process.env.CLAUDE_BIN) return process.env.CLAUDE_BIN
  try {
    const sdkDir = path.dirname(require.resolve('@anthropic-ai/claude-agent-sdk'))
    const report = process.report?.getReport() as any
    const musl = process.platform === 'linux' && !report?.header?.glibcVersionRuntime ? '-musl' : ''
    const dir = path.join(sdkDir, '..', `claude-agent-sdk-${process.platform}-${process.arch}${musl}`)
    const exe = path.join(dir, process.platform === 'win32' ? 'claude.exe' : 'claude')
    if (fs.existsSync(exe)) return exe
  } catch {
    // fall through to PATH
  }
  return 'claude'
}

// Environment for every Claude Code process the add-on starts.
export function claudeEnv(withCredential = true): Record<string, string> {
  const e: Record<string, string> = {}
  for (const [k, v] of Object.entries(process.env)) if (typeof v === 'string') e[k] = v
  if (config.homeDir) {
    e.HOME = config.homeDir
    e.XDG_CONFIG_HOME = path.join(config.dataDir, '.config')
    e.XDG_CACHE_HOME = path.join(config.dataDir, '.cache')
    e.XDG_DATA_HOME = path.join(config.dataDir, '.local', 'share')
    e.XDG_STATE_HOME = path.join(config.dataDir, '.local', 'state')
  }
  delete e.ANTHROPIC_API_KEY
  delete e.CLAUDE_CODE_OAUTH_TOKEN
  if (withCredential) {
    const s = readSaved()
    if (s?.type === 'api_key') e.ANTHROPIC_API_KEY = s.value
    else if (s?.type === 'token') e.CLAUDE_CODE_OAUTH_TOKEN = s.value
    else if (config.oauthToken) e.CLAUDE_CODE_OAUTH_TOKEN = config.oauthToken
  }
  e.DISABLE_AUTOUPDATER = '1'
  e.BROWSER = 'none'
  // ha-mcp's first start downloads its Python; give MCP servers time to come up
  e.MCP_TIMEOUT = '120000'
  // Home Assistant add-ons run as root in a throwaway container; Claude Code
  // only allows "Don't ask" mode as root when the environment says so.
  if (config.onHA) e.IS_SANDBOX = '1'
  return e
}

function sourceLabel(): { method: string; source: string; canSignOut: boolean } {
  const s = readSaved()
  if (s?.type === 'api_key') return { method: 'api_key', source: 'API key saved on this page', canSignOut: true }
  if (s?.type === 'token') return { method: 'token', source: 'Signed in on this page', canSignOut: true }
  if (config.oauthToken) return { method: 'token', source: 'Token from the add-on options or addon_secrets.json', canSignOut: false }
  return { method: 'login', source: 'Claude Code sign-in', canSignOut: true }
}

let statusCache: { at: number; info: AuthInfo } | null = null

function run(args: string[], env: Record<string, string>, timeoutMs: number): Promise<string> {
  return new Promise((resolve) => {
    const child = spawn(claudeBin(), args, { env, cwd: config.workDir, windowsHide: true })
    let out = ''
    child.stdout.on('data', (d) => (out += d))
    child.stderr.on('data', (d) => (out += d))
    const timer = setTimeout(() => child.kill(), timeoutMs)
    child.on('error', () => resolve(''))
    child.on('close', () => {
      clearTimeout(timer)
      resolve(out)
    })
  })
}

export async function authInfo(maxAgeMs = 5 * 60 * 1000): Promise<AuthInfo> {
  if (statusCache && Date.now() - statusCache.at < maxAgeMs) return statusCache.info
  const label = sourceLabel()
  let info: AuthInfo = { signedIn: false, ...label }
  const out = await run(['auth', 'status', '--json'], claudeEnv(), 45000)
  const i = out.indexOf('{')
  if (i < 0) {
    // No answer (a cold start can be slow): don't remember "signed out"; ask again next time
    statusCache = null
    return info
  }
  {
    try {
      const s = JSON.parse(out.slice(i))
      info = {
        ...label,
        signedIn: Boolean(s.loggedIn),
        email: s.email || undefined,
        plan: s.subscriptionType || undefined,
      }
    } catch {
      // leave signedIn false
    }
  }
  statusCache = { at: Date.now(), info }
  return info
}

export function forgetStatus(): void {
  statusCache = null
}

export function saveCredential(value: string): { ok: boolean; error?: string } {
  const v = value.replace(/\s+/g, '')
  if (/^sk-ant-oat\d+-/.test(v)) writeSaved({ type: 'token', value: v, savedAt: new Date().toISOString() })
  else if (/^sk-ant-api\d+-/.test(v)) writeSaved({ type: 'api_key', value: v, savedAt: new Date().toISOString() })
  else return { ok: false, error: 'That doesn’t look like a Claude token (sk-ant-oat…) or an API key (sk-ant-api…).' }
  return { ok: true }
}

export async function signOut(): Promise<void> {
  if (readSaved()) writeSaved(null)
  else await run(['auth', 'logout'], claudeEnv(false), 20000)
  statusCache = null
}

// ---- Sign in with Claude (claude setup-token in a pseudo-terminal) ----

type Flow = { proc: ChildProcess; raw: string; url: string | null; error: string | null; done: boolean; started: number; codeSent: boolean }
let flow: Flow | null = null

const ESC = String.fromCharCode(27)
const BEL = String.fromCharCode(7)
const OSC8 = new RegExp(`${ESC}\\]8;[^;]*;(https://[^${BEL}${ESC}]+)(?:${BEL}|${ESC}\\\\)`, 'g')
const ANSI = new RegExp(`${ESC}\\][^${BEL}]*(?:${BEL}|${ESC}\\\\)|${ESC}\\[[0-9;?]*[ -/]*[@-~]|${ESC}[()][0-9A-B]|${ESC}[=>]`, 'g')
const URL_CHARS = /[A-Za-z0-9._~:/?#@!$&()*+,;=%-]+/

export function stripAnsi(s: string): string {
  return s.replace(ANSI, '').replace(/\r(?!\n)/g, '\n')
}

// The sign-in address. Prefer the OSC 8 link (always whole); otherwise
// rebuild it from the screen text, where it can be wrapped over lines.
export function findLoginUrl(raw: string): string | null {
  const links = [...raw.matchAll(OSC8)].map((m) => m[1]).filter((u) => u.includes('/oauth/authorize'))
  const pick = (urls: string[]) => urls.find((u) => !/redirect_uri=http%3A%2F%2Flocalhost/i.test(u)) ?? urls[0] ?? null
  if (links.length) return pick(links)
  const lines = stripAnsi(raw).split('\n')
  const found: string[] = []
  for (let i = 0; i < lines.length; i++) {
    const at = lines[i].search(/https:\/\/(claude\.(ai|com)|console\.anthropic\.com|platform\.claude\.com)\//)
    if (at < 0) continue
    let url = lines[i].slice(at).match(URL_CHARS)?.[0] ?? ''
    for (let j = i + 1; j < lines.length; j++) {
      const t = lines[j].trim()
      if (!t || !new RegExp(`^${URL_CHARS.source}$`).test(t) || /^https:\/\//.test(t)) break
      url += t
    }
    if (url.includes('/oauth/authorize')) found.push(url)
  }
  return pick(found)
}

export function findToken(raw: string): string | null {
  const text = stripAnsi(raw).replace(/([A-Za-z0-9_-])\n([A-Za-z0-9_-])/g, '$1$2')
  return text.match(/sk-ant-oat\d+-[A-Za-z0-9_-]{20,}/)?.[0] ?? null
}

export function startSignIn(): { ok: boolean; error?: string } {
  if (flow && !flow.done && Date.now() - flow.started < 15 * 60 * 1000) return { ok: true }
  if (flow && !flow.done) flow.proc.kill()
  if (process.platform === 'win32') return { ok: false, error: 'The sign-in button works on Home Assistant. Here, paste a token instead.' }
  const env = { ...claudeEnv(false), PTY_COLS: '2000', PTY_ROWS: '60', TERM: 'xterm-256color', COLUMNS: '2000', LINES: '60' }
  const proc = spawn('python3', [PTY_HELPER, claudeBin(), 'setup-token'], { env, cwd: config.workDir })
  const f: Flow = { proc, raw: '', url: null, error: null, done: false, started: Date.now(), codeSent: false }
  flow = f
  const onData = (d: Buffer) => {
    f.raw += d.toString('utf8')
    if (f.raw.length > 400_000) f.raw = f.raw.slice(-200_000)
    if (!f.url) f.url = findLoginUrl(f.raw)
    const token = f.codeSent ? findToken(f.raw) : null
    if (token && !f.done) {
      writeSaved({ type: 'token', value: token, savedAt: new Date().toISOString() })
      f.done = true
      proc.kill()
    }
  }
  proc.stdout?.on('data', onData)
  proc.stderr?.on('data', onData)
  proc.on('error', (e) => {
    f.error = `Could not start the sign-in: ${e.message}`
    f.done = true
  })
  proc.on('close', () => {
    if (!f.done) {
      const tail = stripAnsi(f.raw).split('\n').map((l) => l.trim()).filter(Boolean).slice(-3).join(' ')
      f.error = f.codeSent ? `Sign-in didn’t finish. ${tail}`.trim() : 'Sign-in stopped before it was finished.'
      f.done = true
    }
    statusCache = null
  })
  return { ok: true }
}

export function signInState(): { running: boolean; url: string | null; error: string | null; finished: boolean; waitingForCode: boolean } {
  if (!flow) return { running: false, url: null, error: null, finished: false, waitingForCode: false }
  const finished = flow.done && !flow.error
  return { running: !flow.done, url: flow.url, error: flow.error, finished, waitingForCode: !flow.done && Boolean(flow.url) && !flow.codeSent }
}

export function sendSignInCode(code: string): { ok: boolean; error?: string } {
  if (!flow || flow.done) return { ok: false, error: 'Start the sign-in again; this one has ended.' }
  const c = code.trim()
  if (!c) return { ok: false, error: 'Paste the code from the Claude page first.' }
  flow.codeSent = true
  flow.proc.stdin?.write(c)
  setTimeout(() => flow?.proc.stdin?.write('\r'), 300)
  return { ok: true }
}

export function cancelSignIn(): void {
  if (flow && !flow.done) {
    flow.proc.kill()
    flow.done = true
    flow.error = null
  }
  flow = null
}
