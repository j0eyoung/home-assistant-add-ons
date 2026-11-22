import { listSessions, renameSession, deleteSession, query } from '@anthropic-ai/claude-agent-sdk'
import type { Query } from '@anthropic-ai/claude-agent-sdk'
import type { WebSocket } from 'ws'
import { Chat, titleFrom } from './chat.ts'
import type { ChatHost } from './chat.ts'
import { config } from './config.ts'
import { claudeEnv, authInfo } from './auth.ts'
import { notify } from './ha.ts'
import { getSettings, updateSettings, getUsage, setUsage } from './settings.ts'
import { HEALTH_PROMPT } from './prompt.ts'
import * as undoStore from './undo.ts'
import type { ChatSummary, ModelOption, ServerMsg, SlashCommand, Usage } from '../shared/types.ts'

type Client = { ws: WebSocket; chatId: string | null; visible: boolean }

const FALLBACK_MODELS: ModelOption[] = [
  { value: 'sonnet', displayName: 'Sonnet', efforts: ['low', 'medium', 'high', 'xhigh', 'max'] },
  { value: 'opus', displayName: 'Opus', efforts: ['low', 'medium', 'high', 'xhigh', 'max'] },
  { value: 'haiku', displayName: 'Haiku', efforts: ['low', 'medium', 'high', 'xhigh', 'max'] },
]

const HIDDEN_COMMANDS = new Set(['exit', 'quit', 'statusline', 'terminal-setup', 'vim', 'ide', 'install-github-app', 'login', 'logout', 'upgrade', 'theme', 'keybindings', 'doctor', 'resume', 'continue', 'add-dir', 'remote-control', 'mobile', 'desktop'])

export class Hub implements ChatHost {
  chats = new Map<string, Chat>()
  clients = new Set<Client>()
  models: ModelOption[] = FALLBACK_MODELS
  commands: SlashCommand[] = []
  usageInfo: Usage | null = getUsage()
  userName = ''
  listTimer: NodeJS.Timeout | null = null
  initDone = false

  // ---- clients ----

  addClient(ws: WebSocket): Client {
    const c: Client = { ws, chatId: null, visible: true }
    this.clients.add(c)
    ws.on('close', () => this.clients.delete(c))
    return c
  }

  send(c: Client, msg: ServerMsg): void {
    if (c.ws.readyState === 1) c.ws.send(JSON.stringify(msg))
  }

  emit(msg: ServerMsg): void {
    const chatId = (msg as any).chatId
    const data = JSON.stringify(msg)
    for (const c of this.clients) if (c.chatId === chatId && c.ws.readyState === 1) c.ws.send(data)
    if (msg.t === 'status') this.pushChats()
  }

  broadcast(msg: ServerMsg): void {
    const data = JSON.stringify(msg)
    for (const c of this.clients) if (c.ws.readyState === 1) c.ws.send(data)
  }

  statusChanged(): void {
    this.pushChats()
  }

  pushChats(): void {
    if (this.listTimer) return
    this.listTimer = setTimeout(async () => {
      this.listTimer = null
      this.broadcast({ t: 'chats', chats: await this.listChats() })
    }, 250)
  }

  // ---- chats ----

  async listChats(): Promise<ChatSummary[]> {
    let sessions: any[] = []
    try {
      sessions = await listSessions({ dir: config.workDir, limit: 300, includeWorktrees: false })
    } catch (e: any) {
      console.error('listSessions failed:', e.message)
    }
    const out = new Map<string, ChatSummary>()
    for (const s of sessions) {
      if (s.archived) continue
      const live = this.chats.get(s.sessionId)
      out.set(s.sessionId, {
        id: s.sessionId,
        title: live && live.title !== 'New chat' ? live.title : cleanTitle(s.customTitle || s.summary || s.firstPrompt || 'Untitled chat'),
        updated: live ? Math.max(live.lastActive, s.lastModified) : s.lastModified,
        status: live?.status ?? 'idle',
      })
    }
    for (const c of this.chats.values()) {
      if (!out.has(c.id) && c.items.length) out.set(c.id, { id: c.id, title: c.title, updated: c.lastActive, status: c.status })
    }
    return [...out.values()].sort((a, b) => b.updated - a.updated)
  }

  defaults(): { model: string; effort: string; mode: string } {
    return { model: config.model, effort: config.effort, mode: config.permissionMode }
  }

  newChat(opts: Partial<{ model: string; effort: string; mode: string }> = {}): Chat {
    const d = this.defaults()
    const chat = new Chat(this, { model: opts.model || d.model, effort: opts.effort || d.effort, mode: opts.mode || d.mode, persisted: false })
    chat.loaded = true
    this.chats.set(chat.id, chat)
    return chat
  }

  async open(id: string): Promise<Chat | null> {
    let chat = this.chats.get(id)
    if (!chat) {
      const list = await this.listChats()
      const s = list.find((x) => x.id === id)
      if (!s) return null
      const d = this.defaults()
      chat = new Chat(this, { id, title: s.title, model: d.model, effort: d.effort, mode: d.mode, persisted: true })
      this.chats.set(id, chat)
    }
    await chat.loadHistory()
    return chat
  }

  async rename(id: string, title: string): Promise<void> {
    const t = title.trim().slice(0, 120)
    if (!t) return
    const chat = this.chats.get(id)
    if (chat) chat.title = t
    if (!chat || chat.persisted) await renameSession(id, t, { dir: config.workDir }).catch((e) => console.error('rename failed', e.message))
    this.pushChats()
  }

  async remove(id: string): Promise<void> {
    const chat = this.chats.get(id)
    if (chat) {
      chat.close()
      this.chats.delete(id)
    }
    await deleteSession(id, { dir: config.workDir }).catch(() => undefined)
    undoStore.forgetChat(id)
    this.pushChats()
  }

  // Close idle processes and drop idle chats from memory after a while
  sweep(): void {
    for (const [id, c] of this.chats) {
      const watched = [...this.clients].some((cl) => cl.chatId === id)
      if (!c.q && c.status === 'idle' && !watched && Date.now() - c.lastActive > 60 * 60 * 1000) this.chats.delete(id)
    }
  }

  // ---- what Claude Code reports ----

  init(q: Query): void {
    q.initializationResult()
      .then((r) => this.absorbInit(r))
      .catch(() => undefined)
  }

  absorbInit(r: any): void {
    if (Array.isArray(r?.models) && r.models.length) {
      this.models = r.models.map((m: any) => ({ value: m.value, displayName: m.displayName || m.value, description: m.description, efforts: m.supportedEffortLevels }))
    }
    if (Array.isArray(r?.commands)) {
      this.commands = r.commands
        .filter((c: any) => c?.name && !HIDDEN_COMMANDS.has(c.name))
        .map((c: any) => ({ name: c.name, description: c.description ?? '', argumentHint: c.argumentHint || undefined }))
    }
    this.initDone = true
    this.broadcast({ t: 'state', state: { models: this.models, commands: this.commands } })
  }

  // Ask Claude Code for the model list and commands once, without starting a chat.
  async warmUp(): Promise<void> {
    if (this.initDone) return
    const info = await authInfo()
    if (!info.signedIn) return
    let close = () => {}
    const prompt: AsyncIterable<any> = {
      [Symbol.asyncIterator]: () => ({ next: () => new Promise((resolve) => (close = () => resolve({ value: undefined, done: true }))) }),
    }
    try {
      const q = query({ prompt, options: { cwd: config.workDir, env: claudeEnv(), settingSources: ['user', 'project', 'local'], persistSession: false } })
      const r = await Promise.race([q.initializationResult(), new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 60000))])
      this.absorbInit(r)
      close()
      q.close()
    } catch (e: any) {
      close()
      console.error('Could not read the model list:', e.message)
    }
  }

  usage(info: any): void {
    if (!info) return
    const pct = typeof info.utilization === 'number' ? (info.utilization <= 1 ? info.utilization * 100 : info.utilization) : null
    const kind = info.rateLimitType ?? 'five_hour'
    // Keep the five-hour window unless a weekly one is the one now limiting
    if (kind !== 'five_hour' && this.usageInfo?.kind === 'five_hour' && info.status === 'allowed' && Date.now() - this.usageInfo.at < 5 * 3600 * 1000) return
    this.usageInfo = { kind, percent: pct === null ? null : Math.round(pct), resetsAt: info.resetsAt ? (info.resetsAt < 1e12 ? info.resetsAt * 1000 : info.resetsAt) : null, status: info.status ?? 'allowed', at: Date.now() }
    setUsage(this.usageInfo)
    this.broadcast({ t: 'state', state: { usage: this.usageInfo } })
  }

  // ---- phone notifications ----

  attention(chat: Chat, why: 'approval' | 'question' | 'plan' | 'finished', text: string): void {
    const s = getSettings()
    if (!s.notifyService || s.notifyWhen === 'never') return
    const someoneLooking = [...this.clients].some((c) => c.visible && c.chatId === chat.id)
    if (s.notifyWhen === 'away' && someoneLooking) return
    const title = why === 'finished' ? `Claude finished: ${chat.title}` : `Claude needs you: ${chat.title}`
    const body = text.replace(/[#*_`>]/g, '').replace(/\s+/g, ' ').trim()
    void notify(s.notifyService, title.slice(0, 120), body.length > 240 ? body.slice(0, 237) + '…' : body)
  }

  // ---- scheduled health check ----

  async healthTick(): Promise<void> {
    const s = getSettings()
    const h = s.health
    if (h.schedule === 'off') return
    const now = new Date()
    const today = now.toLocaleDateString('en-CA')
    const hhmm = now.toTimeString().slice(0, 5)
    if (h.lastRun === today || hhmm < h.time) return
    if (h.schedule === 'weekly' && now.getDay() !== h.weekday) return
    updateSettings({ health: { ...h, lastRun: today } })
    await this.runHealthCheck()
  }

  async runHealthCheck(): Promise<Chat | null> {
    if (!(await authInfo()).signedIn) return null
    const chat = this.newChat({ mode: 'default' })
    chat.unattended = true
    chat.title = `Home health check · ${new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
    await chat.send(HEALTH_PROMPT)
    this.pushChats()
    return chat
  }
}

function cleanTitle(t: string): string {
  return titleFrom(t.replace(/<claude-chat-context>[\s\S]*/, '').replace(/…$/, ''))
}
