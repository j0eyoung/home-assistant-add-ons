import { useEffect, useState } from 'react'
import type { AppState, Settings as S } from '../../shared/types.ts'
import { MODES } from '../../shared/types.ts'
import { api, copyText } from './api.ts'
import { Icon } from './Icon.tsx'
import { SignIn } from './SignIn.tsx'

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

export function Settings({ state, onClose, onChanged, onOpenChat }: { state: AppState; onClose: () => void; onChanged: () => void; onOpenChat: (id: string) => void }) {
  const [s, setS] = useState<S>(state.settings)
  const [memory, setMemory] = useState<{ path: string; text: string } | null>(null)
  const [memSaved, setMemSaved] = useState('')
  const [testMsg, setTestMsg] = useState('')
  const [askText, setAskText] = useState('Why is the porch light off?')
  const [copied, setCopied] = useState('')

  useEffect(() => {
    void api<{ path: string; text: string }>('memory').then(setMemory).catch(() => setMemory({ path: '', text: '' }))
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', esc)
    return () => window.removeEventListener('keydown', esc)
  }, [])

  const save = async (patch: Partial<S>) => {
    const next = { ...s, ...patch, health: { ...s.health, ...(patch.health ?? {}) } }
    setS(next)
    const r = await api<S>('settings', { method: 'PUT', json: patch }).catch(() => null)
    if (r) setS(r)
    onChanged()
  }

  const link = `/${state.ha.slug}/ask/${encodeURIComponent(askText)}`
  const yaml = `type: button\nname: Ask Claude\nicon: mdi:creation\ntap_action:\n  action: navigate\n  navigation_path: ${link}`
  const copy = (what: string, text: string) =>
    void copyText(text).then((ok) => {
      setCopied(ok ? what : '')
      setTimeout(() => setCopied(''), 1500)
    })
  const modeLabel = MODES.find((m) => m.value === state.defaults.mode)?.label ?? state.defaults.mode

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="settings" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <header>
          <h2 id="settings-title">Settings</h2>
          <button type="button" className="iconbtn" aria-label="Close" onClick={onClose}>
            <Icon name="x" />
          </button>
        </header>
        <div className="settingsbody">
          <section>
            <h3>
              <Icon name="key" /> Account
            </h3>
            <SignIn info={state.auth} onChanged={onChanged} />
          </section>

          <section>
            <h3>
              <Icon name="bell" /> Phone notifications
            </h3>
            <p className="hint">Get a push when Claude needs your OK or finishes a long job. Tapping it opens Claude Chat.</p>
            <div className="field">
              <label htmlFor="notify-service">Send to</label>
              <select id="notify-service" value={s.notifyService} onChange={(e) => void save({ notifyService: e.target.value })}>
                <option value="">Don’t send notifications</option>
                {state.ha.notifyServices.map((n) => (
                  <option key={n} value={n}>
                    {n.replace(/^mobile_app_/, '').replace(/_/g, ' ')} ({n})
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="notify-when">When</label>
              <select id="notify-when" value={s.notifyWhen} onChange={(e) => void save({ notifyWhen: e.target.value as S['notifyWhen'] })} disabled={!s.notifyService}>
                <option value="away">When I’m not looking at that chat</option>
                <option value="always">Always</option>
                <option value="never">Never</option>
              </select>
            </div>
            <div className="btns">
              <button
                type="button"
                className="btn"
                disabled={!s.notifyService}
                onClick={async () => {
                  const r = await api<{ ok: boolean; error?: string }>('notify/test', { method: 'POST' }).catch((e) => ({ ok: false, error: e.message }))
                  setTestMsg(r.ok ? 'Sent. Check your phone.' : r.error ?? 'Failed')
                }}
              >
                Send a test
              </button>
              {testMsg && <span className="hint">{testMsg}</span>}
            </div>
          </section>

          <section>
            <h3>
              <Icon name="shield" /> Safety
            </h3>
            <label className="check">
              <input id="backup-before" type="checkbox" checked={s.backupBeforeEdits} onChange={(e) => void save({ backupBeforeEdits: e.target.checked })} />
              <span>
                Back up the Home Assistant configuration before Claude’s first edit in each chat
                <small>A partial backup without the database, named “Before Claude: …”. Every change can also be undone from the chat.</small>
              </span>
            </label>
            <p className="hint">After any YAML edit Claude checks the configuration, and a restart is blocked until the check passes.</p>
          </section>

          <section>
            <h3>
              <Icon name="heart" /> Health check
            </h3>
            <p className="hint">Claude reads the log, unavailable devices, failed automations, updates and backups, then sends you a summary. It doesn’t change anything. Each run uses some of your plan.</p>
            <div className="fieldrow">
              <div className="field">
                <label htmlFor="health-schedule">Run</label>
                <select id="health-schedule" value={s.health.schedule} onChange={(e) => void save({ health: { ...s.health, schedule: e.target.value as S['health']['schedule'] } })}>
                  <option value="off">Only when I ask</option>
                  <option value="daily">Every day</option>
                  <option value="weekly">Every week</option>
                </select>
              </div>
              {s.health.schedule === 'weekly' && (
                <div className="field">
                  <label htmlFor="health-day">On</label>
                  <select id="health-day" value={s.health.weekday} onChange={(e) => void save({ health: { ...s.health, weekday: Number(e.target.value) } })}>
                    {DAYS.map((d, i) => (
                      <option key={d} value={i}>
                        {d}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {s.health.schedule !== 'off' && (
                <div className="field">
                  <label htmlFor="health-time">At</label>
                  <input id="health-time" type="time" value={s.health.time} onChange={(e) => void save({ health: { ...s.health, time: e.target.value } })} />
                </div>
              )}
            </div>
            <div className="btns">
              <button
                type="button"
                className="btn"
                onClick={async () => {
                  const r: { ok: boolean; chatId?: string; error?: string } = await api<{ ok: boolean; chatId?: string; error?: string }>('health/run', { method: 'POST' }).catch((e) => ({ ok: false, error: e.message }))
                  if (r.ok && r.chatId) {
                    onClose()
                    onOpenChat(r.chatId)
                  } else setTestMsg(r.error ?? 'Failed')
                }}
              >
                Run a health check now
              </button>
              {s.health.lastRun && <span className="hint">Last run {s.health.lastRun}</span>}
            </div>
          </section>

          <section>
            <h3>
              <Icon name="brain" /> House memory
            </h3>
            <p className="hint">
              Notes Claude reads in every chat: room and device names, who lives here, how you like automations written. Say “remember …” in a chat and Claude adds a line. Kept in <code>{memory?.path || 'CLAUDE.md'}</code>.
            </p>
            <textarea id="memory-text" className="memory" value={memory?.text ?? ''} onChange={(e) => setMemory({ path: memory?.path ?? '', text: e.target.value })} placeholder={'# Our home\n- The living room lamps are the "Den" area in Home Assistant\n- Put new automations in packages/, one file per room'} rows={8} />
            <div className="btns">
              <button
                type="button"
                className="btn"
                onClick={async () => {
                  await api('memory', { method: 'PUT', json: { text: memory?.text ?? '' } })
                  setMemSaved('Saved')
                  setTimeout(() => setMemSaved(''), 1500)
                }}
              >
                Save memory
              </button>
              {memSaved && <span className="hint">{memSaved}</span>}
            </div>
          </section>

          <section>
            <h3>
              <Icon name="link" /> Ask Claude from a dashboard
            </h3>
            <p className="hint">A dashboard button can open Claude Chat with a question already typed in. Write the question, then copy the button.</p>
            <div className="field">
              <label htmlFor="ask-text">Question</label>
              <input id="ask-text" value={askText} onChange={(e) => setAskText(e.target.value)} />
            </div>
            <pre className="snippet">{yaml}</pre>
            <div className="btns">
              <button type="button" className="btn" onClick={() => copy('yaml', yaml)}>
                <Icon name="copy" size={14} /> {copied === 'yaml' ? 'Copied' : 'Copy button card'}
              </button>
              <button type="button" className="btn" onClick={() => copy('link', link)}>
                <Icon name="link" size={14} /> {copied === 'link' ? 'Copied' : 'Copy link'}
              </button>
            </div>
          </section>

          <section>
            <h3>
              <Icon name="settings" /> Defaults
            </h3>
            <p className="hint">
              New chats start with {state.models.find((m) => m.value === state.defaults.model)?.displayName ?? state.defaults.model}, {state.defaults.effort} effort, “{modeLabel}”. Change these in the add-on’s Configuration tab; each chat can switch from its chat box.
            </p>
            <p className="hint">
              Claude works in <code>{state.workDir}</code>. Version {state.version}.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
