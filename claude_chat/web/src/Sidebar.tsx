import { useMemo, useState } from 'react'
import type { AppState, ChatSummary } from '../../shared/types.ts'
import { Icon, Spark } from './Icon.tsx'

type Props = {
  chats: ChatSummary[]
  current: string | null
  state: AppState | null
  onOpen: (id: string | null) => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
  onSettings: () => void
}

function group(updated: number): string {
  const d = new Date(updated)
  const today = new Date()
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
  if (d.getTime() >= start) return 'Today'
  if (d.getTime() >= start - 86400000) return 'Yesterday'
  if (d.getTime() >= start - 6 * 86400000) return 'Previous 7 days'
  if (d.getTime() >= start - 29 * 86400000) return 'Previous 30 days'
  return 'Older'
}

function UsageMeter({ state }: { state: AppState }) {
  const u = state.usage
  if (!u || u.percent === null) return null
  const label = u.kind === 'five_hour' ? '5-hour limit' : u.kind.startsWith('seven_day') ? 'Weekly limit' : 'Usage limit'
  const reset = u.resetsAt ? new Date(u.resetsAt).toLocaleString([], { weekday: u.resetsAt - Date.now() > 86400000 ? 'short' : undefined, hour: 'numeric', minute: '2-digit' }) : null
  const level = u.percent >= 90 || u.status === 'rejected' ? 'danger' : u.percent >= 70 ? 'warn' : ''
  return (
    <div className="usage" title={reset ? `Resets ${reset}` : undefined}>
      <div className="usagehead">
        <span>{label}</span>
        <span>{u.percent}%</span>
      </div>
      <div className="meter">
        <span className={level} style={{ width: `${Math.min(100, u.percent)}%` }} />
      </div>
      {reset && <div className="usagereset">Resets {reset}</div>}
    </div>
  )
}

export function Sidebar(p: Props) {
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [confirm, setConfirm] = useState<string | null>(null)
  const [showOlder, setShowOlder] = useState(false)

  const groups = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const list = needle ? p.chats.filter((c) => c.title.toLowerCase().includes(needle)) : p.chats
    const out = new Map<string, ChatSummary[]>()
    for (const c of list) {
      const g = group(c.updated)
      out.set(g, [...(out.get(g) ?? []), c])
    }
    return [...out.entries()]
  }, [p.chats, q])

  const older = groups.filter(([g]) => g === 'Older')
  const recent = groups.filter(([g]) => g !== 'Older')
  const name = p.state?.user || ''
  const auth = p.state?.auth

  const row = (c: ChatSummary) => (
    <div key={c.id} className={`chatrow ${c.id === p.current ? 'on' : ''}`}>
      {editing === c.id ? (
        <form
          className="renameform"
          onSubmit={(e) => {
            e.preventDefault()
            p.onRename(c.id, draft)
            setEditing(null)
          }}
        >
          <input id={`rename-${c.id}`} value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus onBlur={() => setEditing(null)} onKeyDown={(e) => e.key === 'Escape' && setEditing(null)} />
        </form>
      ) : confirm === c.id ? (
        <div className="confirmrow">
          <span>Delete this chat?</span>
          <button type="button" className="btn small danger" onClick={() => (p.onDelete(c.id), setConfirm(null))}>
            Delete
          </button>
          <button type="button" className="btn small" onClick={() => setConfirm(null)}>
            Keep
          </button>
        </div>
      ) : (
        <>
          <button type="button" className="chattitle" onClick={() => p.onOpen(c.id)}>
            {c.status !== 'idle' && <span className={`dot ${c.status}`} title={c.status === 'waiting' ? 'Waiting for you' : 'Working'} />}
            {c.title}
          </button>
          <span className="rowactions">
            <button
              type="button"
              aria-label="Rename"
              title="Rename"
              onClick={() => {
                setDraft(c.title)
                setEditing(c.id)
              }}
            >
              <Icon name="pencil" size={14} />
            </button>
            <button type="button" aria-label="Delete" title="Delete" onClick={() => setConfirm(c.id)}>
              <Icon name="trash" size={14} />
            </button>
          </span>
        </>
      )}
    </div>
  )

  return (
    <nav className="sidebar" aria-label="Chats">
      <div className="brand">
        <Spark />
        Claude Chat
      </div>
      <button type="button" className="newchat" onClick={() => p.onOpen(null)}>
        <Icon name="plus" />
        New chat
      </button>
      <label className="search">
        <Icon name="search" size={14} />
        <input id="chat-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search chats" />
      </label>
      <div className="chatlist">
        {recent.map(([g, list]) => (
          <section key={g}>
            <h3>{g}</h3>
            {list.map(row)}
          </section>
        ))}
        {older.length > 0 &&
          (showOlder || q ? (
            older.map(([g, list]) => (
              <section key={g}>
                <h3>{g}</h3>
                {list.map(row)}
              </section>
            ))
          ) : (
            <button type="button" className="linkbtn showolder" onClick={() => setShowOlder(true)}>
              Show older chats ({older[0][1].length})
            </button>
          ))}
        {!p.chats.length && <p className="empty">Your chats appear here.</p>}
      </div>
      <div className="sidefoot">
        {p.state && <UsageMeter state={p.state} />}
        <button type="button" className="account" onClick={p.onSettings}>
          <span className="avatar">{(name || 'You').slice(0, 1).toUpperCase()}</span>
          <span className="acctext">
            {auth?.signedIn ? (auth.email || 'Claude account') : 'Not signed in'}
            <small>{auth?.signedIn ? [auth.plan ? `${auth.plan[0].toUpperCase()}${auth.plan.slice(1)} plan` : '', auth.method === 'api_key' ? 'API key' : ''].filter(Boolean).join(' · ') || auth.source : 'Open settings to sign in'}</small>
          </span>
          <Icon name="settings" />
        </button>
      </div>
    </nav>
  )
}
