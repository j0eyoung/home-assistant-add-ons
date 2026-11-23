import fs from 'node:fs'
import path from 'node:path'

// On Home Assistant the Supervisor writes /data/options.json; anywhere else this
// runs as a local development copy with its data in ./data.
const onHA = fs.existsSync('/data/options.json')
const dataDir = process.env.DATA_DIR ?? (onHA ? '/data' : path.resolve('data'))
fs.mkdirSync(dataDir, { recursive: true })

function readOptions(): Record<string, any> {
  try {
    return JSON.parse(fs.readFileSync('/data/options.json', 'utf8'))
  } catch {
    return {}
  }
}

const o = readOptions()
const str = (v: unknown, d: string) => (typeof v === 'string' && v.trim() ? v.trim() : d)

// The folder Claude works in. A typo'd path must never stop the add-on.
function workDir(): string {
  const fallback = onHA ? '/config' : path.resolve(dataDir, 'work')
  const wanted = str(o.working_directory, process.env.WORK_DIR ?? fallback)
  if (fs.existsSync(wanted) && fs.statSync(wanted).isDirectory()) return wanted
  if (wanted !== fallback) console.warn(`working_directory ${wanted} does not exist; using ${fallback}`)
  fs.mkdirSync(fallback, { recursive: true })
  return fallback
}

const work = workDir()

// Plugins shipped with the add-on and loaded in every chat (plugins/<name>/SOURCE.txt says where each came from).
const appDir = path.resolve(import.meta.dirname, '..')
const plugins = ['home-assistant-skills', 'esphome-skills'].map((p) => path.join(appDir, 'plugins', p)).filter((p) => fs.existsSync(path.join(p, '.claude-plugin', 'plugin.json')))

export const config = {
  onHA,
  port: Number(process.env.PORT ?? 8099),
  dataDir,
  // Claude Code's HOME: sessions, settings and its own sign-in live here so they survive updates.
  // A local development copy keeps the developer's own HOME (and Claude sign-in) unless told not to.
  homeDir: onHA || process.env.OWN_HOME === '1' ? path.join(dataDir, 'home') : '',
  workDir: work,
  // Home Assistant's configuration folder (the config:rw map)
  haConfigDir: onHA ? '/config' : process.env.HA_CONFIG_DIR ?? work,
  oauthToken: str(o.claude_code_oauth_token, process.env.CLAUDE_CODE_OAUTH_TOKEN ?? '').replace(/\s+/g, ''),
  model: str(o.model, process.env.CLAUDE_MODEL ?? 'sonnet'),
  effort: str(o.effort, 'high'),
  permissionMode: str(o.permission_mode, 'default'),
  enableHaMcp: onHA && o.enable_ha_mcp !== false,
  haMcpVersion: str(o.ha_mcp_version, '7.11.0'),
  supervisorToken: process.env.SUPERVISOR_TOKEN ?? '',
  plugins: plugins.map((p) => ({ type: 'local' as const, path: p })),
  // Sample Home Assistant data for working on the page away from Home Assistant
  demo: !onHA && process.env.DEMO_HA === '1',
  version: process.env.ADDON_VERSION ?? '0.1.0',
}

// Claude Code deletes saved chats older than cleanupPeriodDays (30 by default) each
// time it starts. Keep them until they're deleted here, unless a period is already set.
export function keepChats(settingsFile: string): void {
  try {
    const s = fs.existsSync(settingsFile) ? JSON.parse(fs.readFileSync(settingsFile, 'utf8')) : {}
    if (s.cleanupPeriodDays !== undefined) return
    s.cleanupPeriodDays = 36500
    fs.mkdirSync(path.dirname(settingsFile), { recursive: true })
    fs.writeFileSync(settingsFile, JSON.stringify(s, null, 2) + '\n')
  } catch (e: any) {
    console.warn(`could not set cleanupPeriodDays in ${settingsFile}: ${e.message}`)
  }
}

if (config.homeDir) {
  fs.mkdirSync(config.homeDir, { recursive: true })
  // The chat list, chat history, rename and delete read Claude Code's saved chats from
  // this process's HOME, so it must be the HOME Claude Code runs with (see claudeEnv).
  // Set before the Agent SDK is first used: it remembers the folder.
  process.env.HOME = config.homeDir
  keepChats(path.join(config.homeDir, '.claude', 'settings.json'))
}
