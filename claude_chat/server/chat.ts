import { randomUUID } from 'node:crypto'
import path from 'node:path'
import { query, getSessionMessages } from '@anthropic-ai/claude-agent-sdk'
import type { Query, SDKMessage, SDKUserMessage, CanUseTool, PermissionResult, HookCallbackMatcher, HookEvent, Options } from '@anthropic-ai/claude-agent-sdk'
import { config } from './config.ts'
import { claudeEnv, forgetStatus } from './auth.ts'
import { checkConfig, createBackup, describeMentions } from './ha.ts'
import { systemAppend } from './prompt.ts'
import { READ_TOOLS, EDIT_TOOLS, isReadOnlyMcp, isRestart, describe, alwaysKey, filePathOf } from './policy.ts'
import * as undoStore from './undo.ts'
import { getSettings } from './settings.ts'
import { CONTEXT_OPEN, CONTEXT_CLOSE, stripContext } from '../shared/types.ts'
import type { Item, ChatStatus, Mention, Question, ServerMsg } from '../shared/types.ts'

// One conversation. While it is open, a Claude Code process runs for it in
// streaming-input mode, so follow-up messages go straight in. After a quiet
// spell the process is closed; the next message resumes the session.

export type ChatHost = {
  emit: (msg: ServerMsg) => void
  statusChanged: (chat: Chat) => void
  attention: (chat: Chat, why: 'approval' | 'question' | 'plan' | 'finished', text: string) => void
  usage: (info: any) => void
  init: (q: Query) => void
}

class InputQueue implements AsyncIterable<SDKUserMessage> {
  items: SDKUserMessage[] = []
  waiters: ((r: IteratorResult<SDKUserMessage>) => void)[] = []
  closed = false
  push(m: SDKUserMessage): void {
    const w = this.waiters.shift()
    if (w) w({ value: m, done: false })
    else this.items.push(m)
  }
  close(): void {
    this.closed = true
    for (const w of this.waiters.splice(0)) w({ value: undefined as any, done: true })
  }
  [Symbol.asyncIterator](): AsyncIterator<SDKUserMessage> {
    return {
      next: () => {
        if (this.items.length) return Promise.resolve({ value: this.items.shift()!, done: false })
        if (this.closed) return Promise.resolve({ value: undefined as any, done: true })
        return new Promise((r) => this.waiters.push(r))
      },
    }
  }
}

type Pending = { resolve: (v: any) => void; kind: 'approval' | 'question' | 'plan'; input?: any; tool?: string }

const IDLE_CLOSE_MS = 15 * 60 * 1000
const MAX_RESULT = 200_000

export class Chat {
  id: string
  title: string
  items: Item[] = []
  index = new Map<string, number>()
  status: ChatStatus = 'idle'
  model: string
  effort: string
  mode: string
  persisted: boolean
  unattended = false
  host: ChatHost
  q: Query | null = null
  input: InputQueue | null = null
  pendings = new Map<string, Pending>()
  allowAlways = new Set<string>()
  backedUp = false
  notes: string[] = []
  lastActive = Date.now()
  turnStart = 0
  lastCost = 0
  stream = new Map<string, { msgId: string; blocks: Map<number, string>; json: Map<number, string> }>()
  finalCount = new Map<string, { text: number; thinking: number }>()
  idleTimer: NodeJS.Timeout | null = null
  loaded = false

  constructor(host: ChatHost, opts: { id?: string; title?: string; model: string; effort: string; mode: string; persisted: boolean }) {
    this.host = host
    this.id = opts.id ?? randomUUID()
    this.title = opts.title ?? 'New chat'
    this.model = opts.model
    this.effort = opts.effort
    this.mode = opts.mode
    this.persisted = opts.persisted
  }

  // ---- items ----

  upsert(item: Item, emit = true): void {
    const i = this.index.get(item.id)
    if (i === undefined) {
      this.index.set(item.id, this.items.length)
      this.items.push(item)
    } else {
      this.items[i] = item
    }
    if (emit) this.host.emit({ t: 'item', chatId: this.id, item })
  }

  get(id: string): Item | undefined {
    const i = this.index.get(id)
    return i === undefined ? undefined : this.items[i]
  }

  notice(level: 'info' | 'ok' | 'warn' | 'error', text: string): void {
    this.upsert({ kind: 'notice', id: randomUUID(), level, text })
  }

  setStatus(s: ChatStatus): void {
    if (this.status === s) return
    this.status = s
    this.host.emit({ t: 'status', chatId: this.id, status: s, title: this.title, model: this.model, effort: this.effort, mode: this.mode })
    this.host.statusChanged(this)
  }

  refreshStatus(): void {
    if (this.pendings.size) this.setStatus('waiting')
    else if (this.turnStart) this.setStatus('running')
    else this.setStatus('idle')
  }

  // ---- history ----

  async loadHistory(): Promise<void> {
    if (this.loaded || !this.persisted) {
      this.loaded = true
      return
    }
    this.loaded = true
    let msgs: any[] = []
    try {
      msgs = await getSessionMessages(this.id, { dir: config.workDir, includeSystemMessages: false })
    } catch (e: any) {
      console.error('Could not read chat history', this.id, e.message)
    }
    const undoable = undoStore.undoable(this.id)
    const undone = undoStore.undoneIds(this.id)
    for (const m of msgs) {
      const content = m.message?.content
      if (m.type === 'user') {
        if (typeof content === 'string') {
          this.addHistoryUser(m.uuid, content, 0)
          continue
        }
        if (!Array.isArray(content)) continue
        let text = ''
        let images = 0
        for (const b of content) {
          if (b.type === 'tool_result') this.applyToolResult(b, false)
          else if (b.type === 'text') text += (text ? '\n' : '') + b.text
          else if (b.type === 'image') images++
        }
        if (text || images) this.addHistoryUser(m.uuid, text, images)
      } else if (m.type === 'assistant' && Array.isArray(content)) {
        content.forEach((b: any, i: number) => {
          const id = `${m.uuid}:${i}`
          if (b.type === 'text' && b.text?.trim()) this.upsert({ kind: 'text', id, text: b.text, parent: m.parent_tool_use_id ?? null }, false)
          else if (b.type === 'thinking' && b.thinking?.trim()) this.upsert({ kind: 'thinking', id, text: b.thinking, parent: m.parent_tool_use_id ?? null }, false)
          else if (b.type === 'tool_use') {
            const undo = undone.has(b.id) ? 'done' : undoable.has(b.id) ? 'available' : undefined
            this.upsert({ kind: 'tool', id: b.id, name: b.name, input: b.input ?? {}, status: 'done', parent: m.parent_tool_use_id ?? null, undo }, false)
          }
        })
      }
    }
  }

  addHistoryUser(id: string, raw: string, images: number): void {
    // Claude Code stores slash-command plumbing and reminders as user text; keep the chat clean
    if (/^<(command-|local-command|system-reminder|bash-|user-memory)/.test(raw.trim())) {
      const cmd = raw.match(/<command-name>([^<]+)<\/command-name>/)?.[1]
      if (cmd) this.upsert({ kind: 'user', id, text: cmd }, false)
      return
    }
    if (raw.startsWith('[Request interrupted')) {
      this.upsert({ kind: 'notice', id, level: 'info', text: 'Stopped' }, false)
      return
    }
    this.upsert({ kind: 'user', id, text: stripContext(raw), images: images || undefined }, false)
  }

  // ---- sending ----

  async send(text: string, images: { data: string; mediaType: string }[] = [], mentions: Mention[] = []): Promise<void> {
    this.lastActive = Date.now()
    if (!this.persisted && this.title === 'New chat') this.title = titleFrom(text)
    const id = randomUUID()
    this.upsert({ kind: 'user', id, text, images: images.length || undefined })

    const extra: string[] = []
    const mentionText = await describeMentions(mentions)
    if (mentionText) extra.push(mentionText)
    if (this.notes.length) extra.push(...this.notes.splice(0))
    const full = extra.length ? `${text}\n\n${CONTEXT_OPEN}\n${extra.join('\n\n')}\n${CONTEXT_CLOSE}` : text
    const content: any[] = images.map((im) => ({ type: 'image', source: { type: 'base64', media_type: im.mediaType, data: im.data } }))
    content.push({ type: 'text', text: full })

    if (!this.q) await this.start()
    this.turnStart = this.turnStart || Date.now()
    this.setStatus('running')
    this.input!.push({ type: 'user', message: { role: 'user', content }, parent_tool_use_id: null } as SDKUserMessage)
    this.armIdle()
  }

  async start(): Promise<void> {
    this.input = new InputQueue()
    const hooks: Partial<Record<HookEvent, HookCallbackMatcher[]>> = {
      PreToolUse: [{ hooks: [this.preToolUse], timeout: 900 }],
      PostToolUse: [{ hooks: [this.postToolUse], timeout: 180 }],
    }
    const options: Options = {
      cwd: config.workDir,
      model: this.model,
      effort: this.effort as any,
      permissionMode: this.mode as any,
      allowDangerouslySkipPermissions: true,
      includePartialMessages: true,
      thinking: { type: 'adaptive', display: 'summarized' },
      canUseTool: this.canUseTool,
      hooks,
      allowedTools: READ_TOOLS,
      settingSources: ['user', 'project', 'local'],
      systemPrompt: { type: 'preset', preset: 'claude_code', append: await systemAppend() },
      env: claudeEnv(),
      mcpServers: haMcpServers(),
      stderr: (d: string) => {
        if (/error|fail/i.test(d)) console.error(`[claude ${this.id.slice(0, 8)}] ${d.trim()}`)
      },
      ...(this.persisted ? { resume: this.id } : { sessionId: this.id, title: this.title }),
    }
    this.q = query({ prompt: this.input, options })
    this.host.init(this.q)
    void this.consume(this.q)
  }

  async consume(q: Query): Promise<void> {
    try {
      for await (const m of q) this.handle(m)
    } catch (e: any) {
      const msg = String(e?.message ?? e)
      if (!/aborted|interrupted/i.test(msg)) {
        this.notice('error', friendlyError(msg))
        if (isAuthError(msg)) forgetStatus()
      }
    } finally {
      if (this.q === q) {
        this.q = null
        this.input = null
        for (const [id, p] of this.pendings) this.cancelPending(id, p)
        this.turnStart = 0
        this.refreshStatus()
      }
    }
  }

  armIdle(): void {
    if (this.idleTimer) clearTimeout(this.idleTimer)
    this.idleTimer = setTimeout(() => {
      if (this.status === 'idle' && this.input) this.input.close()
    }, IDLE_CLOSE_MS)
  }

  close(): void {
    this.input?.close()
    this.q?.close()
  }

  async stop(): Promise<void> {
    if (!this.q) return
    for (const [id, p] of this.pendings) this.cancelPending(id, p)
    try {
      await this.q.interrupt()
    } catch {
      // the process may already be gone
    }
  }

  async applySettings(s: { model?: string; effort?: string; mode?: string }): Promise<void> {
    if (s.model && s.model !== this.model) {
      this.model = s.model
      await this.q?.setModel(s.model).catch(() => undefined)
    }
    if (s.effort && s.effort !== this.effort) {
      this.effort = s.effort
      await this.q?.applyFlagSettings({ effortLevel: s.effort as any }).catch(() => undefined)
    }
    if (s.mode && s.mode !== this.mode) {
      this.mode = s.mode
      await this.q?.setPermissionMode(s.mode as any).catch(() => undefined)
    }
    this.host.emit({ t: 'status', chatId: this.id, status: this.status, model: this.model, effort: this.effort, mode: this.mode })
  }

  // ---- messages from Claude Code ----

  handle(m: SDKMessage): void {
    this.lastActive = Date.now()
    const anyM = m as any
    switch (m.type) {
      case 'system':
        if (anyM.subtype === 'init') {
          if (!this.persisted) this.persisted = true
          if (anyM.permissionMode && anyM.permissionMode !== this.mode) {
            this.mode = anyM.permissionMode
            this.host.emit({ t: 'status', chatId: this.id, status: this.status, mode: this.mode })
          }
          const failed = (anyM.mcp_servers ?? []).filter((s: any) => s.status === 'failed').map((s: any) => String(s.name))
          if (failed.includes('home-assistant')) this.notice('warn', 'Home Assistant’s tools (ha-mcp) didn’t start, so Claude will use the Home Assistant API directly. The add-on log has the reason.')
          const others = failed.filter((n: string) => n !== 'home-assistant')
          if (others.length) this.notice('warn', `Couldn’t start ${others.join(', ')}`)
        } else if (anyM.subtype === 'compact_boundary') {
          this.notice('info', 'Earlier messages were summarized to make room')
        } else if (anyM.subtype === 'local_command_output' && anyM.content) {
          this.notice('info', String(anyM.content))
        }
        return
      case 'stream_event':
        this.onStream(anyM.event, anyM.parent_tool_use_id ?? null)
        return
      case 'assistant':
        this.onAssistant(anyM)
        return
      case 'user':
        this.onUser(anyM)
        return
      case 'result':
        this.onResult(anyM)
        return
      case 'rate_limit_event':
        this.host.usage(anyM.rate_limit_info)
        return
      default:
        return
    }
  }

  onStream(ev: any, parent: string | null): void {
    const key = parent ?? ''
    if (ev.type === 'message_start') {
      this.stream.set(key, { msgId: ev.message?.id ?? randomUUID(), blocks: new Map(), json: new Map() })
      return
    }
    const st = this.stream.get(key)
    if (!st) return
    if (ev.type === 'content_block_start') {
      const cb = ev.content_block ?? {}
      if (cb.type === 'text' || cb.type === 'thinking') {
        const id = `${st.msgId}:${ev.index}`
        st.blocks.set(ev.index, id)
        this.upsert({ kind: cb.type, id, text: '', parent } as Item)
      } else if (cb.type === 'tool_use' && cb.id) {
        st.blocks.set(ev.index, cb.id)
        st.json.set(ev.index, '')
        this.upsert({ kind: 'tool', id: cb.id, name: cb.name, input: {}, status: 'running', parent })
      }
      return
    }
    if (ev.type === 'content_block_delta') {
      const id = st.blocks.get(ev.index)
      if (!id) return
      const d = ev.delta ?? {}
      const text = d.type === 'text_delta' ? d.text : d.type === 'thinking_delta' ? d.thinking : null
      if (text) {
        const it = this.get(id)
        if (it && (it.kind === 'text' || it.kind === 'thinking')) {
          it.text += text
          this.host.emit({ t: 'delta', chatId: this.id, id, text })
        }
      } else if (d.type === 'input_json_delta') {
        st.json.set(ev.index, (st.json.get(ev.index) ?? '') + (d.partial_json ?? ''))
      }
    }
  }

  onAssistant(m: any): void {
    const msgId: string = m.message?.id ?? m.uuid
    const parent: string | null = m.parent_tool_use_id ?? null
    const seen = this.finalCount.get(msgId) ?? { text: 0, thinking: 0 }
    this.finalCount.set(msgId, seen)
    const streamed = (kind: 'text' | 'thinking') => this.items.filter((it) => it.kind === kind && it.id.startsWith(`${msgId}:`))
    for (const b of m.message?.content ?? []) {
      if (b.type === 'text' || b.type === 'thinking') {
        const kind = b.type as 'text' | 'thinking'
        const text: string = kind === 'text' ? b.text : b.thinking
        const n = seen[kind]++
        const existing = streamed(kind)[n]
        if (existing) {
          if ((existing as any).text !== text && text) this.upsert({ ...(existing as any), text })
        } else if (text?.trim()) {
          this.upsert({ kind, id: `${msgId}:${kind[0]}${n}`, text, parent } as Item)
        }
      } else if (b.type === 'tool_use') {
        const prev = this.get(b.id)
        this.upsert({ kind: 'tool', id: b.id, name: b.name, input: b.input ?? {}, status: prev?.kind === 'tool' ? prev.status : 'running', parent, undo: prev?.kind === 'tool' ? prev.undo : undefined })
      }
    }
    if (m.error) {
      const e = String(m.error)
      this.notice('error', e === 'authentication_failed' ? 'Claude couldn’t sign in. Open Settings › Account to sign in again.' : e === 'rate_limit' ? 'You’ve reached your plan’s usage limit for now.' : e === 'billing_error' ? 'Your Claude account has a billing problem.' : `Claude reported an error: ${e}`)
      if (e === 'authentication_failed') forgetStatus()
    }
  }

  onUser(m: any): void {
    const content = m.message?.content
    if (!Array.isArray(content)) return
    for (const b of content) if (b.type === 'tool_result') this.applyToolResult(b, true)
  }

  applyToolResult(b: any, emit: boolean): void {
    const it = this.get(b.tool_use_id)
    if (!it || it.kind !== 'tool') return
    let text = ''
    if (typeof b.content === 'string') text = b.content
    else if (Array.isArray(b.content)) text = b.content.map((c: any) => (c.type === 'text' ? c.text : c.type === 'image' ? '[image]' : '')).join('\n')
    if (text.length > MAX_RESULT) text = text.slice(0, MAX_RESULT) + `\n… (${text.length - MAX_RESULT} more characters)`
    this.upsert({ ...it, status: b.is_error ? 'error' : 'done', result: text }, emit)
  }

  onResult(m: any): void {
    const seconds = Math.round((m.duration_ms ?? 0) / 100) / 10
    const total = typeof m.total_cost_usd === 'number' ? m.total_cost_usd : undefined
    const cost = total !== undefined ? Math.max(0, total - this.lastCost) : undefined
    if (total !== undefined) this.lastCost = total
    let error: string | undefined
    if (m.subtype !== 'success') error = (m.errors ?? []).join('; ') || m.subtype
    else if (m.is_error) error = String(m.result ?? 'Error')
    if (error) error = friendlyError(error)
    if (error && isAuthError(error)) forgetStatus()
    this.upsert({ kind: 'done', id: m.uuid ?? randomUUID(), seconds, cost, error })
    for (const it of this.items) if (it.kind === 'tool' && it.status === 'running') this.upsert({ ...it, status: 'done' })
    const long = this.turnStart && Date.now() - this.turnStart > 60000
    this.turnStart = (m.queued_turn_count ?? 0) > 0 ? Date.now() : 0
    this.refreshStatus()
    this.armIdle()
    const last = [...this.items].reverse().find((it) => it.kind === 'text' && !it.parent)
    if (long || this.unattended) this.host.attention(this, 'finished', error ? `Stopped: ${error}` : (last as any)?.text ?? 'Done')
  }

  // ---- approvals ----

  canUseTool: CanUseTool = async (toolName, input, opts) => {
    if (toolName === 'AskUserQuestion') return this.ask(input, opts.signal)
    if (toolName === 'ExitPlanMode') return this.planApproval(input, opts.signal)
    if (READ_TOOLS.includes(toolName) || isReadOnlyMcp(toolName)) return { behavior: 'allow', updatedInput: input }
    if (this.unattended) return { behavior: 'deny', message: 'This is an unattended health check: read only, don’t change anything.' }
    const always = alwaysKey(toolName)
    if (this.allowAlways.has(always.key) && !isRestart(toolName, input)) return { behavior: 'allow', updatedInput: input }

    const id = randomUUID()
    const d = describe(toolName, input, (opts as any).title)
    const item: Item = { kind: 'approval', id, tool: toolName, title: d.title, input, risk: d.risk, reason: (opts as any).decisionReason, alwaysLabel: always.label, status: 'pending' }
    this.upsert(item)
    const result = await this.wait<PermissionResult>(id, 'approval', opts.signal, { input, tool: toolName })
    return result
  }

  ask(input: any, signal: AbortSignal): Promise<PermissionResult> {
    const id = randomUUID()
    const questions: Question[] = input?.questions ?? []
    this.upsert({ kind: 'question', id, questions, status: 'pending' })
    return this.wait<PermissionResult>(id, 'question', signal, { input })
  }

  planApproval(input: any, signal: AbortSignal): Promise<PermissionResult> {
    const id = randomUUID()
    this.upsert({ kind: 'plan', id, plan: String(input?.plan ?? ''), status: 'pending' })
    return this.wait<PermissionResult>(id, 'plan', signal, { input })
  }

  wait<T>(id: string, kind: Pending['kind'], signal: AbortSignal, extra: { input?: any; tool?: string }): Promise<T> {
    return new Promise<T>((resolve) => {
      const p: Pending = { resolve, kind, ...extra }
      this.pendings.set(id, p)
      this.refreshStatus()
      const it = this.get(id)
      this.host.attention(this, kind, it?.kind === 'approval' ? it.title : kind === 'question' ? 'Claude has a question' : 'Claude has a plan for you to approve')
      signal.addEventListener('abort', () => this.cancelPending(id, p), { once: true })
    })
  }

  cancelPending(id: string, p: Pending): void {
    if (!this.pendings.has(id)) return
    this.pendings.delete(id)
    const it = this.get(id)
    if (it && 'status' in it && it.status === 'pending') this.upsert({ ...it, status: 'cancelled' } as Item)
    p.resolve({ behavior: 'deny', message: 'Cancelled', interrupt: true })
    this.refreshStatus()
  }

  decide(id: string, decision: 'once' | 'always' | 'deny', reason?: string): void {
    const p = this.pendings.get(id)
    const it = this.get(id)
    if (!p || p.kind !== 'approval' || it?.kind !== 'approval') return
    this.pendings.delete(id)
    if (decision === 'deny') {
      this.upsert({ ...it, status: 'denied' })
      p.resolve({ behavior: 'deny', message: reason?.trim() ? `The user said no: ${reason.trim()}` : 'The user said no to this. Ask what they would like instead.' })
    } else {
      if (decision === 'always') this.allowAlways.add(alwaysKey(it.tool).key)
      this.upsert({ ...it, status: 'allowed' })
      p.resolve({ behavior: 'allow', updatedInput: p.input })
    }
    this.refreshStatus()
  }

  answer(id: string, answers: Record<string, string> | null): void {
    const p = this.pendings.get(id)
    const it = this.get(id)
    if (!p || p.kind !== 'question' || it?.kind !== 'question') return
    this.pendings.delete(id)
    if (!answers) {
      this.upsert({ ...it, status: 'cancelled' })
      p.resolve({ behavior: 'deny', message: 'The user skipped these questions. Continue with your best judgement or ask in the chat.' })
    } else {
      this.upsert({ ...it, status: 'answered', answers })
      p.resolve({ behavior: 'allow', updatedInput: { ...p.input, answers } })
    }
    this.refreshStatus()
  }

  async decidePlan(id: string, decision: 'auto' | 'ask' | 'keep', feedback?: string): Promise<void> {
    const p = this.pendings.get(id)
    const it = this.get(id)
    if (!p || p.kind !== 'plan' || it?.kind !== 'plan') return
    this.pendings.delete(id)
    if (decision === 'keep') {
      this.upsert({ ...it, status: 'rejected' })
      p.resolve({ behavior: 'deny', message: feedback?.trim() ? `Keep planning. The user's feedback: ${feedback.trim()}` : 'The user wants to keep planning. Ask what to change.' })
    } else {
      this.upsert({ ...it, status: 'approved' })
      p.resolve({ behavior: 'allow', updatedInput: p.input })
      await this.applySettings({ mode: decision === 'auto' ? 'acceptEdits' : 'default' })
    }
    this.refreshStatus()
  }

  // ---- hooks: config check guard, backups, undo ----

  preToolUse = async (input: any): Promise<any> => {
    const tool: string = input.tool_name
    const ti = input.tool_input ?? {}
    if (EDIT_TOOLS.has(tool)) {
      const p = filePathOf(ti)
      if (p) undoStore.beforeEdit(this.id, input.tool_use_id, p)
      if (!this.backedUp && getSettings().backupBeforeEdits && underHaConfig(p) && !this.unattended) {
        this.backedUp = true
        this.notice('info', 'Making a backup of your Home Assistant configuration first…')
        const b = await createBackup(`Before Claude: ${this.title}`.slice(0, 80))
        this.notice(b.ok ? 'ok' : 'warn', b.ok ? `Backup “Before Claude: ${this.title}” saved` : `The backup failed (${b.error}). Carrying on without it.`)
      }
    }
    if (isRestart(tool, ti)) {
      const c = await checkConfig()
      if (c && !c.valid) {
        this.notice('error', 'Restart blocked: the configuration check found errors')
        return { hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny', permissionDecisionReason: `Home Assistant's configuration check failed, so restarting now would leave Home Assistant broken. Fix these errors first:\n${c.errors}` } }
      }
    }
    return {}
  }

  postToolUse = async (input: any): Promise<any> => {
    const tool: string = input.tool_name
    if (!EDIT_TOOLS.has(tool)) return {}
    const p = filePathOf(input.tool_input)
    if (undoStore.afterEdit(this.id, input.tool_use_id)) {
      const it = this.get(input.tool_use_id)
      if (it?.kind === 'tool') this.upsert({ ...it, undo: 'available' })
    }
    if (!/\.ya?ml$/i.test(p) || !underHaConfig(p)) return {}
    const c = await checkConfig()
    if (!c) return {}
    if (c.valid) {
      this.notice('ok', `Configuration check passed after editing ${path.basename(p)}`)
      return { hookSpecificOutput: { hookEventName: 'PostToolUse', additionalContext: 'Home Assistant configuration check: valid.' } }
    }
    this.notice('error', `Configuration check failed after editing ${path.basename(p)}`)
    return { hookSpecificOutput: { hookEventName: 'PostToolUse', additionalContext: `Home Assistant configuration check FAILED after this edit. Fix it before reloading or restarting:\n${c.errors}` } }
  }

  undo(toolUseId: string, force: boolean): { ok: boolean; error?: string; changedSince?: boolean } {
    const r = undoStore.undo(this.id, toolUseId, force)
    if (r.ok) {
      const it = this.get(toolUseId)
      if (it?.kind === 'tool') this.upsert({ ...it, undo: 'done' })
      const name = path.basename(r.path ?? '')
      this.notice('info', `Undid the change to ${name}`)
      this.notes.push(`Note: the user undid your earlier change to ${r.path}; it is back to how it was before that edit.${/\.ya?ml$/i.test(name) ? ' Reload whatever uses it if needed.' : ''}`)
    }
    return r
  }
}

export function underHaConfig(p: string): boolean {
  if (!p) return false
  const rel = path.relative(config.haConfigDir, path.resolve(config.workDir, p))
  return !rel.startsWith('..') && !path.isAbsolute(rel)
}

function haMcpServers(): Options['mcpServers'] {
  if (!config.enableHaMcp || !config.supervisorToken) return undefined
  return {
    'home-assistant': {
      type: 'stdio',
      command: 'uvx',
      args: ['--python', '3.13', '--index-strategy', 'unsafe-best-match', `ha-mcp@${config.haMcpVersion}`],
      env: { HOMEASSISTANT_URL: 'http://supervisor/core', HOMEASSISTANT_TOKEN: config.supervisorToken },
    },
  }
}

// A chat's name: its first line, whole when it is short; a long one stops at a
// sentence or word end (the list wraps titles rather than cutting them off).
export function titleFrom(text: string): string {
  const first = text.split('\n').map((l) => l.trim()).find(Boolean) ?? ''
  const t = first.replace(/\s+/g, ' ')
  if (!t) return 'New chat'
  if (t.length <= 90) return t
  const sentence = t.match(/^(.{20,90}?[.?!])\s/)?.[1]
  return sentence ?? t.slice(0, 90).replace(/\s+\S*$/, '')
}

const isAuthError = (msg: string) => /authenticat|oauth|log ?in|not logged|unauthori[sz]ed|\b401\b|invalid api key|token.*(expired|revoked|invalid)/i.test(msg)

function friendlyError(msg: string): string {
  if (isAuthError(msg)) return 'Claude couldn’t sign in. Open Settings › Account to sign in again.'
  if (/rate.?limit|usage limit|\b429\b/i.test(msg)) return 'You’ve reached your plan’s usage limit for now. The usage meter shows when it resets.'
  if (/overloaded|\b529\b/i.test(msg)) return 'Claude is busy right now. Try again in a minute.'
  if (/ENOENT|spawn/i.test(msg)) return `Claude Code couldn’t start: ${msg}`
  return msg.length > 400 ? msg.slice(0, 400) + '…' : msg
}
