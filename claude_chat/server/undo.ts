import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { config } from './config.ts'

// Per-edit undo. Before Claude edits or writes a file, its old content is
// kept; after the edit the new content's hash is kept, so undo can tell when
// the file has changed again since (then it refuses instead of losing work).

const DIR = path.join(config.dataDir, 'undo')
fs.mkdirSync(DIR, { recursive: true })
const MAX_BYTES = 2 * 1024 * 1024
const MAX_ENTRIES = 60

type Entry = { path: string; before: string | null; afterHash?: string; at: number; undone?: boolean }
type Store = Record<string, Entry>

const file = (chatId: string) => path.join(DIR, `${chatId.replace(/[^A-Za-z0-9-]/g, '')}.json`)
const hash = (s: string) => crypto.createHash('sha256').update(s).digest('hex')

function load(chatId: string): Store {
  try {
    return JSON.parse(fs.readFileSync(file(chatId), 'utf8'))
  } catch {
    return {}
  }
}

function save(chatId: string, s: Store): void {
  const entries = Object.entries(s).sort((a, b) => b[1].at - a[1].at).slice(0, MAX_ENTRIES)
  fs.writeFileSync(file(chatId), JSON.stringify(Object.fromEntries(entries)))
}

function readOrNull(p: string): string | null {
  try {
    return fs.readFileSync(p, 'utf8')
  } catch {
    return null
  }
}

export function beforeEdit(chatId: string, toolUseId: string, p: string): void {
  if (!p) return
  try {
    if (fs.existsSync(p) && fs.statSync(p).size > MAX_BYTES) return
  } catch {
    return
  }
  const s = load(chatId)
  s[toolUseId] = { path: p, before: readOrNull(p), at: Date.now() }
  save(chatId, s)
}

// Returns true when the edit can be undone.
export function afterEdit(chatId: string, toolUseId: string): boolean {
  const s = load(chatId)
  const e = s[toolUseId]
  if (!e) return false
  const now = readOrNull(e.path)
  if (now === null || now === e.before) {
    delete s[toolUseId]
    save(chatId, s)
    return false
  }
  e.afterHash = hash(now)
  save(chatId, s)
  return true
}

export function undoable(chatId: string): Set<string> {
  const s = load(chatId)
  return new Set(Object.entries(s).filter(([, e]) => e.afterHash && !e.undone).map(([k]) => k))
}

export function undoneIds(chatId: string): Set<string> {
  const s = load(chatId)
  return new Set(Object.entries(s).filter(([, e]) => e.undone).map(([k]) => k))
}

export function undo(chatId: string, toolUseId: string, force = false): { ok: boolean; path?: string; error?: string; changedSince?: boolean } {
  const s = load(chatId)
  const e = s[toolUseId]
  if (!e || !e.afterHash || e.undone) return { ok: false, error: 'This change can’t be undone any more.' }
  const now = readOrNull(e.path)
  if (!force && (now === null || hash(now) !== e.afterHash)) {
    return { ok: false, changedSince: true, path: e.path, error: `${path.basename(e.path)} has changed since this edit. Undo the later changes first, or undo anyway to put back the version from before this edit.` }
  }
  if (e.before === null) fs.rmSync(e.path, { force: true })
  else fs.writeFileSync(e.path, e.before)
  e.undone = true
  save(chatId, s)
  return { ok: true, path: e.path }
}

export function forgetChat(chatId: string): void {
  fs.rmSync(file(chatId), { force: true })
}
