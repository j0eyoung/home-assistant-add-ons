import { config } from './config.ts'
import type { HomeCard, Mention } from '../shared/types.ts'

// Home Assistant and Supervisor APIs, reached with the add-on's SUPERVISOR_TOKEN.
// Everything here fails soft: a missing permission or an API change hides a
// card or a line of context, it never breaks the chat.

const SUP = 'http://supervisor'
export const haConnected = () => Boolean(config.supervisorToken)

async function call(url: string, init: RequestInit = {}, timeoutMs = 15000): Promise<Response> {
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${config.supervisorToken}`)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  return fetch(url, { ...init, headers, signal: AbortSignal.timeout(timeoutMs) })
}

async function json<T = any>(url: string, init: RequestInit = {}, timeoutMs = 15000): Promise<T | null> {
  if (!haConnected()) return null
  try {
    const r = await call(url, init, timeoutMs)
    if (!r.ok) return null
    return (await r.json()) as T
  } catch {
    return null
  }
}

export const coreGet = <T = any>(p: string) => json<T>(`${SUP}/core/api${p}`)
export const corePost = <T = any>(p: string, body: unknown, timeoutMs = 15000) =>
  json<T>(`${SUP}/core/api${p}`, { method: 'POST', body: JSON.stringify(body) }, timeoutMs)
const supGet = async <T = any>(p: string): Promise<T | null> => (await json<{ data: T }>(`${SUP}${p}`))?.data ?? null

export type State = { entity_id: string; state: string; attributes: Record<string, any>; last_changed: string; last_updated: string }

let statesCache: { at: number; states: State[] } = { at: 0, states: [] }
export async function getStates(maxAgeMs = 20000): Promise<State[]> {
  if (config.demo) return DEMO_STATES
  if (Date.now() - statesCache.at < maxAgeMs) return statesCache.states
  const s = await coreGet<State[]>('/states')
  if (s) statesCache = { at: Date.now(), states: s }
  return statesCache.states
}

export async function renderTemplate(template: string): Promise<string | null> {
  if (!haConnected()) return null
  try {
    const r = await call(`${SUP}/core/api/template`, { method: 'POST', body: JSON.stringify({ template }) })
    return r.ok ? await r.text() : null
  } catch {
    return null
  }
}

let coreConfig: any = null
async function getCoreConfig(): Promise<any> {
  if (!coreConfig) coreConfig = await coreGet('/config')
  return coreConfig
}

const fmtName = (s: State) => String(s.attributes.friendly_name || s.entity_id)

function sinceText(iso: string, tz?: string): string {
  const d = new Date(iso)
  const now = new Date()
  const opts: Intl.DateTimeFormatOptions = tz ? { timeZone: tz } : {}
  const day = (x: Date) => x.toLocaleDateString('en-CA', opts)
  if (day(d) === day(now)) return `since ${d.toLocaleTimeString('en-US', { ...opts, hour: 'numeric', minute: '2-digit' })}`
  const days = Math.round((now.getTime() - d.getTime()) / 86400000)
  return days <= 1 ? 'since yesterday' : days < 7 ? `since ${d.toLocaleDateString('en-US', { ...opts, weekday: 'long' })}` : `for ${days} days`
}

// ---- Config check, the guard before reloads and restarts ----

export async function checkConfig(): Promise<{ valid: boolean; errors: string } | null> {
  if (!haConnected()) return null
  const r = await corePost<{ result: string; errors: string | null }>('/config/core/check_config', {}, 120000)
  if (!r) return null
  return { valid: r.result === 'valid', errors: r.errors ?? '' }
}

// ---- Log ----

type LogLine = { date: string; time: string; level: string; logger: string; message: string }
const LOG_RE = /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:\.\d+)?\s+(ERROR|CRITICAL|WARNING)\s+\([^)]*\)\s+\[([^\]]+)\]\s+(.*)$/

export function parseLog(text: string): LogLine[] {
  const out: LogLine[] = []
  for (const raw of text.split('\n')) {
    const line = raw.replace(/\x1b\[[0-9;]*m/g, '').replace(/^\S+ \S+ \S+ homeassistant\[\d+\]: /, '').trim()
    const m = line.match(LOG_RE)
    if (m) out.push({ date: m[1], time: m[2], level: m[3], logger: m[4], message: m[5] })
  }
  return out
}

async function readLog(): Promise<string> {
  if (!haConnected()) return ''
  try {
    const r = await call(`${SUP}/core/logs`, { headers: { Accept: 'text/plain', Range: 'entries=:-4000:' } }, 20000)
    if (r.ok) return await r.text()
  } catch {
    // try the older endpoint
  }
  try {
    const r = await call(`${SUP}/core/api/error_log`, {}, 20000)
    if (r.ok) return await r.text()
  } catch {
    // no log access
  }
  return ''
}

async function todaysErrors(): Promise<{ count: number; groups: { logger: string; count: number; sample: string }[] } | null> {
  if (config.demo) return { count: 3, groups: [{ logger: 'homeassistant.components.zha', count: 2, sample: 'Device 0x4F2A not responding' }, { logger: 'homeassistant.helpers.template', count: 1, sample: "Template variable error: 'sensor.old_power' is undefined" }] }
  const text = await readLog()
  if (!text) return null
  const tz = (await getCoreConfig())?.time_zone
  const today = new Date().toLocaleDateString('en-CA', tz ? { timeZone: tz } : {})
  const lines = parseLog(text).filter((l) => l.date === today && l.level !== 'WARNING')
  const by = new Map<string, { logger: string; count: number; sample: string }>()
  for (const l of lines) {
    const g = by.get(l.logger) ?? { logger: l.logger, count: 0, sample: l.message.slice(0, 160) }
    g.count++
    by.set(l.logger, g)
  }
  return { count: lines.length, groups: [...by.values()].sort((a, b) => b.count - a.count) }
}

const shortLogger = (l: string) => l.replace(/^homeassistant\.components\./, '').replace(/^custom_components\./, '').replace(/^homeassistant\./, '')

// ---- Home cards ----

let cardsCache: { at: number; cards: HomeCard[] } = { at: 0, cards: [] }

export async function homeCards(force = false): Promise<HomeCard[]> {
  if (!force && Date.now() - cardsCache.at < 60000) return cardsCache.cards
  if (!haConnected() && !config.demo) return []
  const tz = config.demo ? undefined : (await getCoreConfig())?.time_zone
  const cards: HomeCard[] = []
  const [errors, states, backups] = await Promise.all([todaysErrors(), getStates(), config.demo ? DEMO_BACKUPS : supGet<{ backups: any[] }>('/backups')])

  if (errors) {
    if (errors.count) {
      const list = errors.groups.slice(0, 3).map((g) => `${shortLogger(g.logger)}: ${g.sample}${g.count > 1 ? ` (×${g.count})` : ''}`)
      cards.push({
        key: 'errors',
        level: 'error',
        title: `${errors.count} error${errors.count === 1 ? '' : 's'} in today’s log`,
        detail: list.join(' · '),
        action: 'Ask Claude to look',
        prompt: `Look at today's errors in the Home Assistant log, explain what is causing each one and how to fix it. The add-on counted ${errors.count} today:\n${errors.groups.slice(0, 8).map((g) => `- ${g.logger} (×${g.count}): ${g.sample}`).join('\n')}`,
      })
    } else {
      cards.push({ key: 'errors', level: 'ok', title: 'No errors in today’s log', detail: 'Warnings are left out of this count.', action: 'Ask about warnings', prompt: 'Are there any warnings in today’s Home Assistant log I should care about?' })
    }
  }

  const skip = new Set(['button', 'scene', 'event', 'image', 'update', 'tts', 'stt', 'conversation', 'wake_word', 'notify', 'assist_satellite'])
  const unavailable = states
    .filter((s) => s.state === 'unavailable' && !s.attributes.restored && !skip.has(s.entity_id.split('.')[0]))
    .sort((a, b) => b.last_changed.localeCompare(a.last_changed))
  if (unavailable.length) {
    cards.push({
      key: 'unavailable',
      level: 'warn',
      title: `${unavailable.length} entit${unavailable.length === 1 ? 'y' : 'ies'} unavailable`,
      detail: unavailable.slice(0, 3).map((s) => `${fmtName(s)} ${sinceText(s.last_changed, tz)}`).join(' · ') + (unavailable.length > 3 ? ` · and ${unavailable.length - 3} more` : ''),
      action: 'Ask Claude to look',
      prompt: `These entities are unavailable. Group them by device or integration, tell me the likely reason for each group and what to check:\n${unavailable.slice(0, 40).map((s) => `- ${s.entity_id} (${fmtName(s)}) ${sinceText(s.last_changed, tz)}`).join('\n')}`,
    })
  }

  const updates = states.filter((s) => s.entity_id.startsWith('update.') && s.state === 'on')
  if (updates.length) {
    const names = updates.map((s) => `${s.attributes.title || fmtName(s)} ${s.attributes.latest_version ?? ''}`.trim())
    cards.push({
      key: 'updates',
      level: 'neutral',
      title: updates.length === 1 ? `Update ready: ${names[0]}` : `${updates.length} updates ready`,
      detail: updates.length === 1 ? 'Check the release notes against your setup first.' : names.slice(0, 4).join(' · '),
      action: 'Ask Claude to review',
      prompt: `These updates are waiting. For each, read the release notes and tell me whether anything in them affects my setup (breaking changes for integrations I use, deprecated YAML I have). Don't install anything:\n${updates.map((s) => `- ${s.entity_id}: ${s.attributes.title || fmtName(s)} ${s.attributes.installed_version ?? '?'} → ${s.attributes.latest_version ?? '?'}`).join('\n')}`,
    })
  }

  const list = backups?.backups ?? []
  if (backups) {
    const newest = [...list].sort((a, b) => String(b.date).localeCompare(String(a.date)))[0]
    if (newest) {
      const days = Math.floor((Date.now() - new Date(newest.date).getTime()) / 86400000)
      const size = typeof newest.size === 'number' ? ` · ${newest.size >= 1024 ? (newest.size / 1024).toFixed(1) + ' GB' : Math.round(newest.size) + ' MB'}` : ''
      cards.push({
        key: 'backup',
        level: days > 7 ? 'warn' : 'ok',
        title: `Last backup ${days === 0 ? 'today' : days === 1 ? 'yesterday' : `${days} days ago`}`,
        detail: `${newest.name || 'Backup'} · ${newest.type === 'full' ? 'Full' : 'Partial'}${size}`,
        action: 'Ask about backups',
        prompt: 'Look at my Home Assistant backups (when they run, what they include, where they are stored) and tell me if anything should change.',
      })
    } else {
      cards.push({ key: 'backup', level: 'warn', title: 'No backups found', detail: 'Home Assistant has no backups stored.', action: 'Ask about backups', prompt: 'I have no Home Assistant backups. Help me set up automatic backups.' })
    }
  }

  cardsCache = { at: Date.now(), cards }
  return cards
}

// ---- Context for every chat ----

let contextCache: { at: number; text: string } = { at: 0, text: '' }

export async function haContext(): Promise<string> {
  if (Date.now() - contextCache.at < 10 * 60 * 1000 && contextCache.text) return contextCache.text
  if (!haConnected() && !config.demo) return ''
  const [cfg, states, areas, addons, errors] = await Promise.all([
    config.demo ? { version: '2026.11.2', location_name: 'Home', time_zone: 'America/Denver', unit_system: { temperature: '°F' } } : getCoreConfig(),
    getStates(),
    config.demo ? 'Kitchen, Living Room, Garage, Porch' : renderTemplate("{{ areas() | map('area_name') | join(', ') }}"),
    config.demo ? [] : supGet<{ addons: any[] }>('/addons').then((d) => d?.addons ?? []),
    todaysErrors(),
  ])
  const lines: string[] = ['## This Home Assistant']
  if (cfg) {
    lines.push(`- Version ${cfg.version}; location "${cfg.location_name}"; time zone ${cfg.time_zone}; units ${cfg.unit_system?.temperature ?? ''}`)
  }
  if (areas) lines.push(`- Areas: ${areas}`)
  if (states.length) {
    const by = new Map<string, number>()
    for (const s of states) {
      const d = s.entity_id.split('.')[0]
      by.set(d, (by.get(d) ?? 0) + 1)
    }
    const top = [...by.entries()].sort((a, b) => b[1] - a[1])
    lines.push(`- ${states.length} entities: ${top.map(([d, n]) => `${d} ${n}`).join(', ')}`)
    const unavailable = states.filter((s) => s.state === 'unavailable' && !s.attributes.restored).length
    if (unavailable) lines.push(`- ${unavailable} entities are unavailable right now`)
  }
  const installed = (addons as any[]).filter((a) => a.installed !== false)
  if (installed.length) lines.push(`- Add-ons: ${installed.map((a) => `${a.name} ${a.version} (${a.state})`).join(', ')}`)
  if (errors?.count) lines.push(`- Today's log has ${errors.count} errors, mostly from: ${errors.groups.slice(0, 5).map((g) => `${g.logger} ×${g.count}`).join(', ')}`)
  const text = lines.join('\n')
  contextCache = { at: Date.now(), text }
  return text
}

// ---- @ mentions ----

let areaCache: { at: number; areas: { id: string; name: string }[] } = { at: 0, areas: [] }
async function getAreas(): Promise<{ id: string; name: string }[]> {
  if (config.demo) return [{ id: 'kitchen', name: 'Kitchen' }, { id: 'living_room', name: 'Living Room' }, { id: 'garage', name: 'Garage' }, { id: 'porch', name: 'Porch' }]
  if (Date.now() - areaCache.at < 5 * 60 * 1000) return areaCache.areas
  const t = await renderTemplate("{% for a in areas() %}{{ a }}|{{ area_name(a) }}\n{% endfor %}")
  if (t !== null) {
    areaCache = {
      at: Date.now(),
      areas: t.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => {
        const [id, ...name] = l.split('|')
        return { id, name: name.join('|') }
      }),
    }
  }
  return areaCache.areas
}

export async function searchMentions(q: string): Promise<Mention[]> {
  const needle = q.trim().toLowerCase()
  const [states, areas] = await Promise.all([getStates(), getAreas()])
  const out: Mention[] = []
  for (const a of areas) {
    if (!needle || a.name.toLowerCase().includes(needle) || a.id.includes(needle)) out.push({ type: 'area', id: a.id, label: a.name, detail: 'Area' })
  }
  const scored = states
    .map((s) => {
      const name = fmtName(s).toLowerCase()
      const id = s.entity_id.toLowerCase()
      const score = !needle ? 1 : id === needle ? 100 : name.startsWith(needle) ? 50 : id.split('.')[1]?.startsWith(needle) ? 40 : name.includes(needle) ? 20 : id.includes(needle) ? 10 : 0
      return { s, score }
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score || fmtName(a.s).localeCompare(fmtName(b.s)))
  for (const { s } of scored.slice(0, 40)) out.push({ type: 'entity', id: s.entity_id, label: fmtName(s), detail: `${s.entity_id} · ${s.state}` })
  return out.slice(0, 40)
}

// What Claude sees for each mention in a message
export async function describeMentions(mentions: Mention[]): Promise<string> {
  if (!mentions.length) return ''
  const states = await getStates(5000)
  const parts: string[] = []
  for (const m of mentions.slice(0, 20)) {
    if (m.type === 'entity') {
      const s = states.find((x) => x.entity_id === m.id)
      if (!s) {
        parts.push(`- ${m.id}: not found in the current states`)
        continue
      }
      const attrs = JSON.stringify(s.attributes)
      parts.push(`- ${s.entity_id} ("${fmtName(s)}"): state ${s.state}, last changed ${s.last_changed}; attributes ${attrs.length > 1500 ? attrs.slice(0, 1500) + '…' : attrs}`)
    } else {
      const ents = config.demo ? '' : await renderTemplate(`{{ area_entities('${m.id.replace(/'/g, '')}') | join(', ') }}`)
      const list = (ents ?? '').split(',').map((e) => e.trim()).filter(Boolean)
      const lines = list.slice(0, 40).map((id) => {
        const s = states.find((x) => x.entity_id === id)
        return s ? `${id}=${s.state}` : id
      })
      parts.push(`- Area "${m.label}" (${m.id}): ${lines.length ? lines.join(', ') : 'no entities found'}`)
    }
  }
  return `The user mentioned these:\n${parts.join('\n')}`
}

// ---- Notifications, backups, add-on info ----

export async function notifyServices(): Promise<string[]> {
  if (config.demo) return ['mobile_app_pixel_9', 'mobile_app_ipad']
  const services = await coreGet<{ domain: string; services: Record<string, unknown> }[]>('/services')
  const notify = services?.find((d) => d.domain === 'notify')
  const names = Object.keys(notify?.services ?? {})
  return names.filter((n) => n.startsWith('mobile_app_')).concat(names.filter((n) => !n.startsWith('mobile_app_') && !['notify', 'send_message', 'persistent_notification'].includes(n)))
}

let self: { slug: string } | null = null
export async function selfInfo(): Promise<{ slug: string }> {
  if (self) return self
  const info = await supGet<{ slug: string }>('/addons/self/info')
  self = { slug: info?.slug ?? 'claude_chat' }
  return self
}

export async function notify(service: string, title: string, message: string): Promise<boolean> {
  if (!service || !haConnected()) return false
  const { slug } = await selfInfo()
  const r = await corePost(`/services/notify/${service}`, {
    title,
    message,
    data: { url: `/${slug}`, clickAction: `/${slug}`, tag: 'claude-chat', group: 'claude-chat' },
  })
  return r !== null
}

export async function createBackup(name: string): Promise<{ ok: boolean; slug?: string; error?: string }> {
  if (!haConnected()) return { ok: false, error: 'No Home Assistant connection' }
  try {
    const r = await call(`${SUP}/backups/new/partial`, { method: 'POST', body: JSON.stringify({ name, homeassistant: true, homeassistant_exclude_database: true }) }, 600000)
    const d: any = await r.json().catch(() => ({}))
    if (!r.ok || d.result === 'error') return { ok: false, error: d.message || `HTTP ${r.status}` }
    return { ok: true, slug: d.data?.slug }
  } catch (e: any) {
    return { ok: false, error: e.message }
  }
}

// ---- Sample data for working on the page away from Home Assistant ----

const now = Date.now()
const ago = (min: number) => new Date(now - min * 60000).toISOString()
const DEMO_STATES: State[] = [
  { entity_id: 'light.porch', state: 'off', attributes: { friendly_name: 'Porch light' }, last_changed: ago(300), last_updated: ago(300) },
  { entity_id: 'light.kitchen', state: 'on', attributes: { friendly_name: 'Kitchen lights', brightness: 180 }, last_changed: ago(40), last_updated: ago(40) },
  { entity_id: 'binary_sensor.front_door', state: 'unavailable', attributes: { friendly_name: 'Front door sensor' }, last_changed: ago(190), last_updated: ago(190) },
  { entity_id: 'switch.garage_plug', state: 'unavailable', attributes: { friendly_name: 'Garage plug' }, last_changed: ago(4000), last_updated: ago(4000) },
  { entity_id: 'sensor.dryer_power', state: '2.1', attributes: { friendly_name: 'Dryer power', unit_of_measurement: 'W' }, last_changed: ago(35), last_updated: ago(1) },
  { entity_id: 'automation.porch_light_at_dusk', state: 'on', attributes: { friendly_name: 'Porch light at dusk', id: '1700000000001', last_triggered: ago(300) }, last_changed: ago(9000), last_updated: ago(300) },
  { entity_id: 'update.home_assistant_core_update', state: 'on', attributes: { friendly_name: 'Home Assistant Core Update', title: 'Home Assistant Core', installed_version: '2026.11.2', latest_version: '2026.11.3' }, last_changed: ago(600), last_updated: ago(600) },
  { entity_id: 'climate.hallway', state: 'heat', attributes: { friendly_name: 'Hallway thermostat', current_temperature: 68, temperature: 70 }, last_changed: ago(120), last_updated: ago(3) },
]
const DEMO_BACKUPS = { backups: [{ slug: 'abc', name: 'Automatic backup 2026.11.2', date: new Date(now - 3 * 86400000).toISOString(), type: 'full', size: 1433.6 }] }
