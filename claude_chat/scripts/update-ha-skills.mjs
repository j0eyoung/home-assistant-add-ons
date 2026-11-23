// Refresh the bundled Home Assistant skills plugin from https://github.com/homeassistant-ai/skills.
// Usage (from claude_chat/): node scripts/update-ha-skills.mjs [git ref, default main]
// Copies the plugin manifest, the skills folder and the licence into plugins/home-assistant-skills
// and records the commit in SOURCE.txt. Review the diff before committing.
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const REPO = 'https://github.com/homeassistant-ai/skills.git'
const ref = process.argv[2] ?? 'main'
const root = path.resolve(import.meta.dirname, '..')
const src = path.join(root, '.ha-skills-src')
const dest = path.join(root, 'plugins', 'home-assistant-skills')

const git = (...args) => {
  const r = spawnSync('git', args, { encoding: 'utf8' })
  if (r.status !== 0) throw new Error(`git ${args.join(' ')} failed: ${r.stderr.trim()}`)
  return r.stdout.trim()
}

fs.rmSync(src, { recursive: true, force: true })
try {
  git('clone', '--quiet', '--depth', '1', '--branch', ref, REPO, src)
  const commit = git('-C', src, 'rev-parse', 'HEAD')
  const date = git('-C', src, 'log', '-1', '--format=%cs')
  const version = JSON.parse(fs.readFileSync(path.join(src, '.claude-plugin', 'plugin.json'), 'utf8')).version

  fs.rmSync(dest, { recursive: true, force: true })
  fs.mkdirSync(dest, { recursive: true })
  fs.cpSync(path.join(src, '.claude-plugin', 'plugin.json'), path.join(dest, '.claude-plugin', 'plugin.json'))
  fs.cpSync(path.join(src, 'skills'), path.join(dest, 'skills'), { recursive: true })
  fs.cpSync(path.join(src, 'LICENSE'), path.join(dest, 'LICENSE'))
  fs.writeFileSync(
    path.join(dest, 'SOURCE.txt'),
    `Home Assistant skills plugin ${version}, copied from ${REPO.replace(/\.git$/, '')}\ncommit ${commit} (${date})\nRefresh with: node scripts/update-ha-skills.mjs\n`,
  )
  console.log(`home-assistant-skills ${version} (${commit.slice(0, 7)}, ${date}) -> ${path.relative(root, dest)}`)
} finally {
  fs.rmSync(src, { recursive: true, force: true })
}
