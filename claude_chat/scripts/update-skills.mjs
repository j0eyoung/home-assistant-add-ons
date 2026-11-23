// Refresh the skills bundled in plugins/ from their GitHub repos.
// Usage (from claude_chat/): node scripts/update-skills.mjs [plugin ...]   (no names: all of them)
// Each plugin folder is rebuilt from the files listed below, with a SOURCE.txt naming the commit.
// Review the diff before committing: a skill is instructions Claude follows.
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const PLUGINS = {
  // Home Assistant best practices, from the ha-mcp team. The repo is already a Claude Code plugin.
  'home-assistant-skills': {
    repo: 'https://github.com/homeassistant-ai/skills',
    copy: { '.claude-plugin/plugin.json': '.claude-plugin/plugin.json', skills: 'skills', LICENSE: 'LICENSE' },
    version: (src) => JSON.parse(read(src, '.claude-plugin/plugin.json')).version,
  },
  // ESPHome YAML, external components and debugging. The repo has no Claude Code manifest, so one is written here.
  'esphome-skills': {
    repo: 'https://github.com/poolski/agent-skills',
    copy: {
      'skills/esphome-components/SKILL.md': 'skills/esphome-components/SKILL.md',
      'skills/esphome-components/references': 'skills/esphome-components/references',
      'skills/esphome-components/CHANGELOG.md': 'skills/esphome-components/CHANGELOG.md',
      'skills/esphome-components/LICENSE': 'LICENSE',
    },
    version: (src) => read(src, 'skills/esphome-components/CHANGELOG.md').match(/^## \[([^\]]+)\]/m)?.[1] ?? '0.0.0',
    manifest: {
      name: 'esphome-skills',
      description: 'ESPHome device YAML, external components, Home Assistant integration and debugging (from poolski/agent-skills)',
      repository: 'https://github.com/poolski/agent-skills',
      license: 'MIT',
    },
  },
}

const root = path.resolve(import.meta.dirname, '..')
const read = (dir, file) => fs.readFileSync(path.join(dir, file), 'utf8')
const git = (...args) => {
  const r = spawnSync('git', args, { encoding: 'utf8' })
  if (r.status !== 0) throw new Error(`git ${args.join(' ')} failed: ${r.stderr.trim()}`)
  return r.stdout.trim()
}

const names = process.argv.slice(2)
for (const name of names.length ? names : Object.keys(PLUGINS)) {
  const p = PLUGINS[name]
  if (!p) throw new Error(`Unknown plugin ${name}; known: ${Object.keys(PLUGINS).join(', ')}`)
  const src = path.join(root, '.skills-src', name)
  const dest = path.join(root, 'plugins', name)
  fs.rmSync(src, { recursive: true, force: true })
  try {
    git('clone', '--quiet', '--depth', '1', `${p.repo}.git`, src)
    const commit = git('-C', src, 'rev-parse', 'HEAD')
    const date = git('-C', src, 'log', '-1', '--format=%cs')
    const version = p.version(src)

    fs.rmSync(dest, { recursive: true, force: true })
    for (const [from, to] of Object.entries(p.copy)) fs.cpSync(path.join(src, from), path.join(dest, to), { recursive: true })
    if (p.manifest) {
      fs.mkdirSync(path.join(dest, '.claude-plugin'), { recursive: true })
      fs.writeFileSync(path.join(dest, '.claude-plugin', 'plugin.json'), JSON.stringify({ ...p.manifest, version }, null, 2) + '\n')
    }
    fs.writeFileSync(path.join(dest, 'SOURCE.txt'), `${name} ${version}, copied from ${p.repo}\ncommit ${commit} (${date})\nRefresh with: node scripts/update-skills.mjs ${name}\n`)
    console.log(`${name} ${version} (${commit.slice(0, 7)}, ${date}) -> ${path.relative(root, dest)}`)
  } finally {
    fs.rmSync(src, { recursive: true, force: true })
  }
}
fs.rmSync(path.join(root, '.skills-src'), { recursive: true, force: true })
