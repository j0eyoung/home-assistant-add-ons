import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

// Runs as Home Assistant does: Claude Code's HOME in the data folder.
const dir = path.resolve('data', `home-test-${process.pid}`)
process.env.DATA_DIR = dir
process.env.OWN_HOME = '1'
const { config, keepChats } = await import('./config.ts')
const { claudeEnv } = await import('./auth.ts')

test.after(() => fs.rmSync(dir, { recursive: true, force: true }))

test('the chat list reads the same home Claude saves chats in', () => {
  assert.equal(config.homeDir, path.join(dir, 'home'))
  assert.equal(process.env.HOME, config.homeDir)
  assert.equal(claudeEnv(false).HOME, config.homeDir)
})

test('chats are kept past Claude Code\'s 30-day cleanup', () => {
  const s = JSON.parse(fs.readFileSync(path.join(config.homeDir, '.claude', 'settings.json'), 'utf8'))
  assert.equal(s.cleanupPeriodDays, 36500)
})

test('a cleanup period already set is left alone, and other settings kept', () => {
  const file = path.join(dir, 'own-settings.json')
  fs.writeFileSync(file, JSON.stringify({ cleanupPeriodDays: 90, model: 'opus' }))
  keepChats(file)
  assert.deepEqual(JSON.parse(fs.readFileSync(file, 'utf8')), { cleanupPeriodDays: 90, model: 'opus' })
  fs.writeFileSync(file, JSON.stringify({ model: 'opus' }))
  keepChats(file)
  assert.deepEqual(JSON.parse(fs.readFileSync(file, 'utf8')), { model: 'opus', cleanupPeriodDays: 36500 })
})

test('a broken settings file is never overwritten', () => {
  const file = path.join(dir, 'broken-settings.json')
  fs.writeFileSync(file, '{ not json')
  keepChats(file)
  assert.equal(fs.readFileSync(file, 'utf8'), '{ not json')
})
