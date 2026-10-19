// Fill blank add-on options from a shared secrets file that lives only on the Green.
// Looks for addon_secrets.json in the Home Assistant config folder (/homeassistant for
// homeassistant_config maps, /config for config maps). An option set in the add-on's
// Configuration tab always wins; only blank options are filled, and only keys the add-on knows.
import { readFileSync, writeFileSync, renameSync } from 'node:fs'

const OPTIONS = '/data/options.json'
const CANDIDATES = ['/homeassistant/addon_secrets.json', '/config/addon_secrets.json']

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, 'utf8'))
  } catch {
    return undefined
  }
}

const opts = readJson(OPTIONS)
if (opts) {
  let shared = {}
  for (const path of CANDIDATES) {
    const data = readJson(path)
    if (data) {
      shared = data
      break
    }
  }
  const blank = (v) => v === '' || v === null || v === undefined
  const filled = Object.keys(shared).filter((k) => k in opts && blank(opts[k]) && !blank(shared[k]))
  if (filled.length) {
    for (const k of filled) opts[k] = shared[k]
    try {
      writeFileSync(OPTIONS + '.tmp', JSON.stringify(opts))
      renameSync(OPTIONS + '.tmp', OPTIONS)
      console.log('Filled from addon_secrets.json: ' + filled.sort().join(', '))
    } catch (e) {
      console.log('Could not apply addon_secrets.json: ' + e.message)
    }
  }
}
