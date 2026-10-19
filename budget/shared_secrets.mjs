// Fill blank add-on options from a shared secrets file that lives only on the Green.
// Looks for addon_secrets.json in the Home Assistant config folder (/homeassistant for
// homeassistant_config maps, /config for config maps). An option set in the add-on's
// Configuration tab always wins; only blank options are filled. Everything it does is
// printed to the add-on log so a missing or broken file is easy to spot.
import { existsSync, readFileSync, writeFileSync, renameSync } from 'node:fs'

const OPTIONS = '/data/options.json'
const CANDIDATES = ['/homeassistant/addon_secrets.json', '/config/addon_secrets.json']
// Options this add-on accepts. Home Assistant leaves optional options without a default out of
// options.json, so they have to be listed here to be filled.
const KEYS = ['simplefin_setup_token', 'claude_code_oauth_token', 'claude_model', 'api_token']

const blank = (v) => v === '' || v === null || v === undefined

function main() {
  let opts
  try {
    opts = JSON.parse(readFileSync(OPTIONS, 'utf8'))
  } catch (e) {
    console.log(`shared_secrets: cannot read ${OPTIONS}: ${e.message}`)
    return
  }
  let shared
  let found = ''
  for (const path of CANDIDATES) {
    if (!existsSync(path)) continue
    try {
      shared = JSON.parse(readFileSync(path, 'utf8').replace(/^\uFEFF/, ''))
    } catch (e) {
      console.log(`shared_secrets: ${path} is not valid JSON (${e.message}). Check for a trailing comma or a missing quote.`)
      return
    }
    found = path
    break
  }
  if (shared === undefined) {
    console.log('shared_secrets: addon_secrets.json not found in ' + CANDIDATES.join(' or '))
    return
  }
  if (shared === null || typeof shared !== 'object' || Array.isArray(shared)) {
    console.log(`shared_secrets: ${found} must be a JSON object like {"key": "value"}`)
    return
  }
  const accepted = new Set([...KEYS, ...Object.keys(opts)])
  const filled = Object.keys(shared).filter((k) => accepted.has(k) && blank(opts[k]) && !blank(shared[k]))
  if (filled.length) {
    for (const k of filled) opts[k] = shared[k]
    try {
      writeFileSync(OPTIONS + '.tmp', JSON.stringify(opts))
      renameSync(OPTIONS + '.tmp', OPTIONS)
    } catch (e) {
      console.log(`shared_secrets: could not write ${OPTIONS}: ${e.message}`)
      return
    }
  }
  console.log(`shared_secrets: read ${found} (${Object.keys(shared).length} keys); filled ${filled.length}: ` + (filled.sort().join(', ') || 'nothing (all already set or blank)'))
}

main()
