import { useEffect, useState } from 'react'
import type { AuthInfo } from '../../shared/types.ts'
import { api, copyText } from './api.ts'
import { Icon } from './Icon.tsx'

type FlowState = { running: boolean; url: string | null; error: string | null; finished: boolean; waitingForCode: boolean }

// Three ways in, easiest first: the button (claude setup-token run for you),
// pasting a token or API key, or the token in the add-on options/addon_secrets.json.
export function SignIn({ info, onChanged, compact }: { info: AuthInfo | null; onChanged: () => void; compact?: boolean }) {
  const [flow, setFlow] = useState<FlowState | null>(null)
  const [code, setCode] = useState('')
  const [paste, setPaste] = useState('')
  const [showPaste, setShowPaste] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!flow?.running) return
    const t = setInterval(async () => {
      const r = await api<{ signIn: FlowState }>('auth').catch(() => null)
      if (!r) return
      setFlow(r.signIn)
      if (r.signIn.finished) {
        setMsg('Signed in')
        onChanged()
      }
    }, 1500)
    return () => clearInterval(t)
  }, [flow?.running])

  const start = async () => {
    setMsg(null)
    setBusy(true)
    const r = await api<{ ok: boolean; error?: string }>('auth/start', { method: 'POST' }).catch((e) => ({ ok: false, error: e.message }))
    setBusy(false)
    if (!r.ok) {
      setMsg(r.error ?? 'Could not start the sign-in.')
      setShowPaste(true)
      return
    }
    setFlow({ running: true, url: null, error: null, finished: false, waitingForCode: false })
  }

  const sendCode = async (e: React.FormEvent) => {
    e.preventDefault()
    const r = await api<{ ok: boolean; error?: string }>('auth/code', { method: 'POST', json: { code } }).catch((er) => ({ ok: false, error: er.message }))
    if (!r.ok) setMsg(r.error ?? 'That didn’t work.')
    else {
      setCode('')
      setFlow((f) => (f ? { ...f, waitingForCode: false } : f))
    }
  }

  const savePaste = async (e: React.FormEvent) => {
    e.preventDefault()
    const r = await api<{ ok: boolean; error?: string }>('auth/token', { method: 'POST', json: { value: paste } }).catch((er) => ({ ok: false, error: er.message }))
    if (!r.ok) setMsg(r.error ?? 'That didn’t work.')
    else {
      setPaste('')
      setShowPaste(false)
      setMsg('Saved')
      onChanged()
    }
  }

  const signOut = async () => {
    await api('auth/signout', { method: 'POST' }).catch(() => null)
    setMsg(null)
    onChanged()
  }

  if (info?.signedIn && !flow?.running) {
    return (
      <div className="signin done">
        <div className="signedin">
          <Icon name="check" className="ok" />
          <div>
            <b>{info.email || 'Signed in to Claude'}</b>
            <small>
              {[info.plan ? `${info.plan[0].toUpperCase()}${info.plan.slice(1)} plan` : '', info.source].filter(Boolean).join(' · ')}
            </small>
          </div>
        </div>
        <div className="btns">
          {info.canSignOut && (
            <button type="button" className="btn" onClick={signOut}>
              Sign out
            </button>
          )}
          <button type="button" className="btn" onClick={start} disabled={busy}>
            Sign in again
          </button>
          <button type="button" className="linkbtn" onClick={() => setShowPaste(!showPaste)}>
            Use a different token or API key
          </button>
        </div>
        {!info.canSignOut && <p className="hint">This sign-in comes from the add-on’s Configuration tab or addon_secrets.json. Signing in here takes over from it.</p>}
        {showPaste && <PasteForm paste={paste} setPaste={setPaste} onSubmit={savePaste} />}
        {msg && <p className="hint">{msg}</p>}
      </div>
    )
  }

  return (
    <div className={`signin ${compact ? 'compact' : ''}`}>
      {!flow?.running ? (
        <>
          <p>Sign in with your Claude account to start chatting. Your Pro or Max plan covers it; nothing is billed separately.</p>
          <div className="btns">
            <button type="button" className="btn primary" onClick={start} disabled={busy}>
              {busy ? 'Starting…' : 'Sign in with Claude'}
            </button>
            <button type="button" className="linkbtn" onClick={() => setShowPaste(!showPaste)}>
              Paste a token or API key instead
            </button>
          </div>
        </>
      ) : (
        <ol className="steps">
          <li className={flow.url ? '' : 'waiting'}>
            {flow.url ? (
              <>
                <span>Open the Claude sign-in page and approve.</span>
                <span className="btns">
                  <a className="btn primary" href={flow.url} target="_blank" rel="noopener noreferrer">
                    Open sign-in page
                  </a>
                  <button
                    type="button"
                    className="btn"
                    onClick={() =>
                      void copyText(flow.url!).then((ok) => {
                        setCopied(ok)
                        setTimeout(() => setCopied(false), 1500)
                      })
                    }
                  >
                    <Icon name="copy" size={14} /> {copied ? 'Copied' : 'Copy link'}
                  </button>
                </span>
              </>
            ) : (
              <span className="shimmer">Getting the sign-in page ready…</span>
            )}
          </li>
          <li>
            <span>Claude shows a code. Copy it and paste it here.</span>
            <form className="codeform" onSubmit={sendCode}>
              <input id="signin-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="Paste the code" autoComplete="off" disabled={!flow.url} />
              <button type="submit" className="btn primary" disabled={!code.trim()}>
                Finish
              </button>
            </form>
          </li>
          <li>
            <button
              type="button"
              className="linkbtn"
              onClick={async () => {
                await api('auth/cancel', { method: 'POST' }).catch(() => null)
                setFlow(null)
              }}
            >
              Cancel
            </button>
          </li>
        </ol>
      )}
      {flow?.error && <p className="error">{flow.error}</p>}
      {showPaste && <PasteForm paste={paste} setPaste={setPaste} onSubmit={savePaste} />}
      {msg && <p className="hint">{msg}</p>}
    </div>
  )
}

function PasteForm({ paste, setPaste, onSubmit }: { paste: string; setPaste: (v: string) => void; onSubmit: (e: React.FormEvent) => void }) {
  return (
    <form className="pasteform" onSubmit={onSubmit}>
      <label htmlFor="paste-token">
        A token from <code>claude setup-token</code> (starts <code>sk-ant-oat</code>) or an API key (<code>sk-ant-api</code>; billed to your API account)
      </label>
      <div className="row">
        <input id="paste-token" type="password" value={paste} onChange={(e) => setPaste(e.target.value)} placeholder="sk-ant-…" autoComplete="off" />
        <button type="submit" className="btn primary" disabled={!paste.trim()}>
          Save
        </button>
      </div>
    </form>
  )
}
