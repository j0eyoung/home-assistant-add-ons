// Image build step: put the Claude Code binary that the Agent SDK installed for
// this platform on PATH as `claude` (so Claude's own Bash calls and the sign-in
// can run it), and drop the other platforms' copies, which are ~230 MB each.
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const sdkDir = path.dirname(require.resolve('@anthropic-ai/claude-agent-sdk'))
const scope = path.join(sdkDir, '..')
const report = process.report?.getReport()
const musl = process.platform === 'linux' && !report?.header?.glibcVersionRuntime ? '-musl' : ''
const want = `claude-agent-sdk-${process.platform}-${process.arch}${musl}`
const exe = path.join(scope, want, process.platform === 'win32' ? 'claude.exe' : 'claude')

if (!fs.existsSync(exe)) {
  console.error(`Claude Code binary not found at ${exe}`)
  process.exit(1)
}
for (const name of fs.readdirSync(scope)) {
  if (name.startsWith('claude-agent-sdk-') && name !== want) {
    fs.rmSync(path.join(scope, name), { recursive: true, force: true })
    console.log(`removed ${name}`)
  }
}
fs.chmodSync(exe, 0o755)
const link = '/usr/local/bin/claude'
fs.rmSync(link, { force: true })
fs.symlinkSync(exe, link)
console.log(`${link} -> ${exe}`)
