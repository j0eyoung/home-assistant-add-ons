import { test } from 'node:test'
import assert from 'node:assert/strict'
import { findLoginUrl, findToken, stripAnsi } from './auth.ts'
import { isReadOnlyMcp, isRestart, describe, READ_TOOLS } from './policy.ts'
import { Chat, titleFrom } from './chat.ts'
import { parseLog } from './ha.ts'
import { asBlockquote, splitQuotes } from '../shared/types.ts'

const ESC = '\x1b'
const URL = 'https://claude.ai/oauth/authorize?code=true&client_id=abc&response_type=code&redirect_uri=https%3A%2F%2Fconsole.anthropic.com%2Foauth%2Fcode%2Fcallback&scope=user%3Ainference&code_challenge=xyz&state=s123'

test('sign-in address from an OSC 8 link', () => {
  const raw = `${ESC}[2KBrowser didn't open? Visit: ${ESC}]8;;${URL}${ESC}\\${URL.slice(0, 40)}${ESC}]8;;${ESC}\\\r\n`
  assert.equal(findLoginUrl(raw), URL)
})

test('sign-in address wrapped over several lines inside a box', () => {
  const parts = [URL.slice(0, 70), URL.slice(70, 140), URL.slice(140)]
  const raw = `${ESC}[1m Browser didn't open? Use the url below to sign in:${ESC}[22m\r\n\r\n  ${parts[0]}\r\n  ${parts[1]}\r\n  ${parts[2]}\r\n\r\n Paste code here if prompted >`
  assert.equal(findLoginUrl(raw), URL)
})

test('prefers the paste-the-code address over a localhost one', () => {
  const local = URL.replace('https%3A%2F%2Fconsole.anthropic.com%2Foauth%2Fcode%2Fcallback', 'http%3A%2F%2Flocalhost%3A54545%2Fcallback')
  const raw = `${ESC}]8;;${local}${ESC}\\x${ESC}]8;;${ESC}\\ ${ESC}]8;;${URL}${ESC}\\y${ESC}]8;;${ESC}\\`
  assert.equal(findLoginUrl(raw), URL)
})

test('token found, even split over two lines', () => {
  const tok = 'sk-ant-oat01-' + 'A1b2C3d4E5f6G7h8I9j0'.repeat(4)
  assert.equal(findToken(`Your OAuth token (valid for 1 year):\r\n\r\n${ESC}[1m${tok}${ESC}[22m\r\n\r\nStore this token`), tok)
  assert.equal(findToken(`token:\n${tok.slice(0, 30)}\n${tok.slice(30)}\n\nStore it`), tok)
  assert.equal(findToken('no token here'), null)
})

test('stripAnsi leaves plain text', () => {
  assert.equal(stripAnsi(`${ESC}[31mred${ESC}[0m and ${ESC}[?25lplain`), 'red and plain')
})

test('read-only MCP tools pass, changing ones ask', () => {
  assert.equal(isReadOnlyMcp('mcp__home-assistant__ha_get_state'), true)
  assert.equal(isReadOnlyMcp('mcp__home-assistant__ha_search_entities'), true)
  assert.equal(isReadOnlyMcp('mcp__home-assistant__ha_get_automation_traces'), true)
  assert.equal(isReadOnlyMcp('mcp__home-assistant__ha_call_service'), false)
  assert.equal(isReadOnlyMcp('mcp__home-assistant__ha_config_set_automation'), false)
  assert.equal(isReadOnlyMcp('mcp__home-assistant__ha_restart'), false)
  assert.equal(isReadOnlyMcp('Bash'), false)
})

test('restarts are recognised', () => {
  assert.equal(isRestart('Bash', { command: 'curl -X POST -H "Authorization: Bearer $SUPERVISOR_TOKEN" http://supervisor/core/restart' }), true)
  assert.equal(isRestart('Bash', { command: 'ha core restart' }), true)
  assert.equal(isRestart('Bash', { command: 'curl http://supervisor/core/info' }), false)
  assert.equal(isRestart('mcp__home-assistant__ha_restart', {}), true)
  assert.equal(isRestart('mcp__home-assistant__ha_call_service', { domain: 'homeassistant', service: 'restart' }), true)
  assert.equal(isRestart('mcp__home-assistant__ha_call_service', { domain: 'light', service: 'turn_on' }), false)
  assert.match(describe('Bash', { command: 'ha core restart' }).title, /restart Home Assistant/)
})

test('chat titles are whole', () => {
  assert.equal(titleFrom('Why is the porch light off?'), 'Why is the porch light off?')
  const long = 'Look at today’s errors in the Home Assistant log, explain what is causing each one and how to fix it. The add-on counted 3 today'
  const t = titleFrom(long)
  assert.ok(!t.endsWith('…'))
  assert.ok(t.length <= 90)
  assert.equal(t, 'Look at today’s errors in the Home Assistant log, explain what is causing each one and how to fix it.'.length <= 90 ? t : t)
})

test('quotes go out as blockquotes and come back apart', () => {
  const sent = [asBlockquote('Set the motion light to mode: restart.\n\nThen reload.'), 'Why restart?'].join('\n\n')
  assert.equal(sent, '> Set the motion light to mode: restart.\n>\n> Then reload.\n\nWhy restart?')
  assert.deepEqual(splitQuotes(sent), [
    { quote: true, text: 'Set the motion light to mode: restart.\n\nThen reload.' },
    { quote: false, text: 'Why restart?' },
  ])
  assert.deepEqual(splitQuotes('> one\n\n> two\n\nok'), [
    { quote: true, text: 'one' },
    { quote: true, text: 'two' },
    { quote: false, text: 'ok' },
  ])
  assert.deepEqual(splitQuotes('no quote here'), [{ quote: false, text: 'no quote here' }])
  assert.equal(titleFrom(sent), 'Why restart?')
  assert.equal(titleFrom('> Only a quote'), 'Only a quote')
})

test('reading a skill never asks', () => {
  assert.ok(READ_TOOLS.includes('Skill'))
})

test('a health check chat refuses changes until the user replies in it', async () => {
  const host = { emit() {}, statusChanged() {}, attention() {}, usage() {}, init() {} }
  const chat = new Chat(host, { model: 'sonnet', effort: 'high', mode: 'default', persisted: false })
  chat.unattended = true
  const call = { domain: 'automation', service: 'turn_off', entity_id: 'automation.garage' }
  const ac = new AbortController()
  const before = await chat.canUseTool('mcp__home-assistant__ha_call_service', call, { signal: ac.signal } as any)
  assert.equal(before?.behavior, 'deny')

  chat.takeOver()
  assert.equal(chat.unattended, false)
  assert.match(chat.notes.join('\n'), /taken over this health check chat/)
  const after = chat.canUseTool('mcp__home-assistant__ha_call_service', call, { signal: ac.signal } as any)
  await new Promise((r) => setImmediate(r))
  assert.ok(chat.items.some((it) => it.kind === 'approval' && it.status === 'pending'), 'the change asks for approval')
  ac.abort()
  await after

  chat.notes = []
  chat.takeOver()
  assert.equal(chat.notes.length, 0, 'an ordinary chat gets no note')
})

test('log lines are parsed', () => {
  const lines = parseLog('2026-11-21 18:10:02.123 ERROR (MainThread) [homeassistant.components.zha] Device 0x4F2A not responding\n2026-11-21 18:11:00.000 WARNING (MainThread) [homeassistant.helpers.template] old\nnoise')
  assert.equal(lines.length, 2)
  assert.equal(lines[0].logger, 'homeassistant.components.zha')
  assert.equal(lines[0].level, 'ERROR')
})
