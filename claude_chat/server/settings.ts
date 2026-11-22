import fs from 'node:fs'
import path from 'node:path'
import { config } from './config.ts'
import type { Settings, Usage } from '../shared/types.ts'

// Preferences changed in the page (not the add-on options): notifications,
// backups, the health check schedule. Small JSON file in /data.
const FILE = path.join(config.dataDir, 'settings.json')

const DEFAULTS: Settings = {
  notifyService: '',
  notifyWhen: 'away',
  backupBeforeEdits: false,
  health: { schedule: 'off', time: '08:00', weekday: 1, lastRun: '' },
}

type Stored = Settings & { usage?: Usage | null }

function load(): Stored {
  try {
    const s = JSON.parse(fs.readFileSync(FILE, 'utf8'))
    return { ...DEFAULTS, ...s, health: { ...DEFAULTS.health, ...(s.health ?? {}) } }
  } catch {
    return { ...DEFAULTS, health: { ...DEFAULTS.health } }
  }
}

let current: Stored = load()

function save(): void {
  fs.writeFileSync(FILE + '.tmp', JSON.stringify(current, null, 2))
  fs.renameSync(FILE + '.tmp', FILE)
}

export function getSettings(): Settings {
  const { usage: _u, ...s } = current
  return s
}

export function updateSettings(patch: Partial<Settings>): Settings {
  const next: Stored = { ...current, ...patch }
  if (patch.health) next.health = { ...current.health, ...patch.health }
  if (!['away', 'always', 'never'].includes(next.notifyWhen)) next.notifyWhen = 'away'
  if (!['off', 'daily', 'weekly'].includes(next.health.schedule)) next.health.schedule = 'off'
  if (!/^\d{2}:\d{2}$/.test(next.health.time)) next.health.time = '08:00'
  next.health.weekday = Math.min(6, Math.max(0, Math.round(Number(next.health.weekday) || 0)))
  current = next
  save()
  return getSettings()
}

export function getUsage(): Usage | null {
  return current.usage ?? null
}

export function setUsage(u: Usage): void {
  current.usage = u
  save()
}
