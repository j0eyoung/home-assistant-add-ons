// Types shared by the server and the browser. Plain TypeScript only (no Node or DOM imports).

export type Question = {
  question: string
  header: string
  multiSelect?: boolean
  options: { label: string; description: string; preview?: string }[]
}

export type Item =
  | { kind: 'user'; id: string; text: string; images?: number }
  | { kind: 'text'; id: string; text: string; parent?: string | null }
  | { kind: 'thinking'; id: string; text: string; parent?: string | null }
  | {
      kind: 'tool'
      id: string
      name: string
      input: Record<string, any>
      status: 'running' | 'done' | 'error'
      result?: string
      parent?: string | null
      // 'available' once a file edit can be undone, 'done' after it was undone
      undo?: 'available' | 'done'
    }
  | {
      kind: 'approval'
      id: string
      tool: string
      title: string
      input: Record<string, any>
      risk?: string
      reason?: string
      alwaysLabel: string
      status: 'pending' | 'allowed' | 'denied' | 'cancelled'
    }
  | { kind: 'question'; id: string; questions: Question[]; status: 'pending' | 'answered' | 'cancelled'; answers?: Record<string, string> }
  | { kind: 'plan'; id: string; plan: string; status: 'pending' | 'approved' | 'rejected' | 'cancelled' }
  | { kind: 'notice'; id: string; level: 'info' | 'ok' | 'warn' | 'error'; text: string }
  | { kind: 'done'; id: string; seconds: number; cost?: number; error?: string }

export type ChatStatus = 'idle' | 'running' | 'waiting'

export type ChatSummary = {
  id: string
  title: string
  updated: number
  status: ChatStatus
}

export type ModelOption = { value: string; displayName: string; description?: string; efforts?: string[] }

export type Usage = { kind: string; percent: number | null; resetsAt: number | null; status: string; at: number }

export type HomeCard = {
  key: 'errors' | 'unavailable' | 'updates' | 'backup' | 'health'
  level: 'error' | 'warn' | 'neutral' | 'ok'
  title: string
  detail: string
  action: string
  prompt: string
}

export type AuthInfo = {
  signedIn: boolean
  method: string
  source: string
  email?: string
  plan?: string
  canSignOut: boolean
}

export type Settings = {
  notifyService: string
  notifyWhen: 'away' | 'always' | 'never'
  backupBeforeEdits: boolean
  health: { schedule: 'off' | 'daily' | 'weekly'; time: string; weekday: number; lastRun: string }
}

export type Mention = { type: 'entity' | 'area'; id: string; label: string; detail?: string }

export type SlashCommand = { name: string; description: string; argumentHint?: string }

export type AppState = {
  auth: AuthInfo
  user: string
  models: ModelOption[]
  commands: SlashCommand[]
  defaults: { model: string; effort: string; mode: string }
  usage: Usage | null
  settings: Settings
  ha: { connected: boolean; slug: string; notifyServices: string[]; demo: boolean }
  workDir: string
  version: string
}

// Messages over the websocket
export type ClientMsg =
  | { t: 'subscribe'; chatId: string | null }
  | { t: 'send'; chatId: string | null; text: string; images?: { data: string; mediaType: string }[]; mentions?: Mention[]; model?: string; effort?: string; mode?: string }
  | { t: 'stop'; chatId: string }
  | { t: 'approve'; chatId: string; id: string; decision: 'once' | 'always' | 'deny'; reason?: string }
  | { t: 'answer'; chatId: string; id: string; answers: Record<string, string> | null }
  | { t: 'plan'; chatId: string; id: string; decision: 'auto' | 'ask' | 'keep'; feedback?: string }
  | { t: 'settings'; chatId: string; model?: string; effort?: string; mode?: string }
  | { t: 'visible'; visible: boolean }

export type ServerMsg =
  | { t: 'snapshot'; chatId: string; title: string; items: Item[]; status: ChatStatus; model: string; effort: string; mode: string }
  | { t: 'item'; chatId: string; item: Item }
  | { t: 'delta'; chatId: string; id: string; text: string }
  | { t: 'status'; chatId: string; status: ChatStatus; title?: string; model?: string; effort?: string; mode?: string }
  | { t: 'created'; chatId: string; clientRef: string }
  | { t: 'chats'; chats: ChatSummary[] }
  | { t: 'state'; state: Partial<AppState> }
  | { t: 'error'; text: string }

export const MODES: { value: string; label: string; hint: string }[] = [
  { value: 'default', label: 'Ask before edits', hint: 'Claude asks before changing files or running commands' },
  { value: 'acceptEdits', label: 'Edit automatically', hint: 'File edits go ahead; commands and service calls still ask' },
  { value: 'plan', label: 'Plan mode', hint: 'Claude looks around and proposes a plan before changing anything' },
  { value: 'bypassPermissions', label: 'Don’t ask', hint: 'Everything runs without asking. Use with care' },
]

export const EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max']

// Text the server appends to a message for Claude; the chat shows the message without it.
export const CONTEXT_OPEN = '<claude-chat-context>'
export const CONTEXT_CLOSE = '</claude-chat-context>'
export function stripContext(text: string): string {
  const i = text.indexOf(CONTEXT_OPEN)
  return (i >= 0 ? text.slice(0, i) : text).trimEnd()
}
