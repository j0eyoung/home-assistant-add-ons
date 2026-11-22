import { useCallback, useEffect, useRef, useState } from 'react'
import type { AppState, ChatSummary, Item, ServerMsg } from '../../shared/types.ts'
import { api, Socket } from './api.ts'
import { Icon } from './Icon.tsx'
import { Sidebar } from './Sidebar.tsx'
import { Home } from './Home.tsx'
import { ChatView } from './ChatView.tsx'
import type { ChatData } from './ChatView.tsx'
import { Settings } from './Settings.tsx'
import type { Outgoing } from './Composer.tsx'

const socket = new Socket()

function upsert(items: Item[], item: Item): Item[] {
  const i = items.findIndex((x) => x.id === item.id)
  if (i < 0) return [...items, item]
  const next = items.slice()
  next[i] = item
  return next
}

export function App() {
  const [state, setState] = useState<AppState | null>(null)
  const [chats, setChats] = useState<ChatSummary[]>([])
  const [current, setCurrent] = useState<string | null>(null)
  const [chat, setChat] = useState<ChatData | null>(null)
  const [homeSettings, setHomeSettings] = useState({ model: 'sonnet', effort: 'high', mode: 'default' })
  const [draft, setDraftState] = useState<{ text: string; n: number } | null>(null)
  const [drawer, setDrawer] = useState(false)
  const [haNarrow, setHaNarrow] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [connected, setConnected] = useState(true)
  const [toast, setToast] = useState<string | null>(null)
  const currentRef = useRef<string | null>(null)
  const awaitingNew = useRef(false)
  const defaultsSet = useRef(false)

  const setDraft = (text: string) => setDraftState((d) => ({ text, n: (d?.n ?? 0) + 1 }))

  const loadState = useCallback(async () => {
    const s = await api<AppState>('state').catch(() => null)
    if (!s) return
    setState(s)
    if (!defaultsSet.current) {
      defaultsSet.current = true
      setHomeSettings(s.defaults)
    }
  }, [])

  const open = useCallback((id: string | null) => {
    currentRef.current = id
    awaitingNew.current = false
    setCurrent(id)
    setChat(null)
    setDrawer(false)
    socket.send({ t: 'subscribe', chatId: id })
  }, [])

  useEffect(() => {
    void loadState()
    socket.onOpen = () => socket.send({ t: 'subscribe', chatId: currentRef.current })
    socket.onState = setConnected
    const off = socket.listen((m: ServerMsg) => {
      switch (m.t) {
        case 'snapshot':
          if (m.chatId === currentRef.current || awaitingNew.current) {
            awaitingNew.current = false
            currentRef.current = m.chatId
            setCurrent(m.chatId)
            setChat({ id: m.chatId, title: m.title, items: m.items, status: m.status, model: m.model, effort: m.effort, mode: m.mode })
          }
          return
        case 'item':
          setChat((c) => (c && c.id === m.chatId ? { ...c, items: upsert(c.items, m.item) } : c))
          return
        case 'delta':
          setChat((c) => {
            if (!c || c.id !== m.chatId) return c
            const i = c.items.findIndex((x) => x.id === m.id)
            if (i < 0) return c
            const it = c.items[i] as any
            const items = c.items.slice()
            items[i] = { ...it, text: (it.text ?? '') + m.text }
            return { ...c, items }
          })
          return
        case 'status':
          setChat((c) =>
            c && c.id === m.chatId
              ? { ...c, status: m.status, title: m.title ?? c.title, model: m.model ?? c.model, effort: m.effort ?? c.effort, mode: m.mode ?? c.mode }
              : c,
          )
          return
        case 'chats':
          setChats(m.chats)
          return
        case 'state':
          setState((s) => (s ? { ...s, ...m.state } : s))
          return
        case 'error':
          setToast(m.text)
          return
      }
    })
    // Home Assistant tells an add-on panel its route and layout this way
    const onMsg = (e: MessageEvent) => {
      const d = e.data
      if (!d || d.type !== 'home-assistant/properties') return
      setHaNarrow(Boolean(d.narrow))
      const route = `${d.route?.prefix ?? ''}${d.route?.path ?? ''}`
      const ask = route.match(/\/ask\/(.+)$/)
      if (ask) {
        try {
          open(null)
          setDraft(decodeURIComponent(ask[1]))
        } catch {
          // a malformed link; ignore it
        }
      }
    }
    window.addEventListener('message', onMsg)
    if (window.parent !== window) window.parent.postMessage({ type: 'home-assistant/subscribe-properties' }, '*')
    return () => {
      off()
      window.removeEventListener('message', onMsg)
    }
  }, [])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 5000)
    return () => clearTimeout(t)
  }, [toast])

  // Keep the sign-in and usage fresh when someone comes back to the page
  useEffect(() => {
    const onVis = () => document.visibilityState === 'visible' && void loadState()
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [])

  const send = (o: Outgoing) => {
    if (!state?.auth.signedIn) {
      setSettingsOpen(true)
      return
    }
    if (!current) {
      awaitingNew.current = true
      socket.send({ t: 'send', chatId: null, text: o.text, images: o.images, mentions: o.mentions, ...homeSettings })
    } else {
      socket.send({ t: 'send', chatId: current, text: o.text, images: o.images, mentions: o.mentions })
    }
  }

  const changeChatSettings = (s: { model?: string; effort?: string; mode?: string }) => {
    if (!chat) return
    setChat({ ...chat, ...s })
    socket.send({ t: 'settings', chatId: chat.id, ...s })
  }

  const title = current ? chat?.title ?? chats.find((c) => c.id === current)?.title ?? '' : ''

  return (
    <div className={`shell ${haNarrow ? 'narrow' : ''} ${drawer ? 'drawer-open' : ''}`}>
      <div className="scrim" onClick={() => setDrawer(false)} />
      <Sidebar
        chats={chats}
        current={current}
        state={state}
        onOpen={open}
        onRename={(id, t) => void api(`chats/${id}/rename`, { method: 'POST', json: { title: t } }).catch((e) => setToast(e.message))}
        onDelete={(id) => {
          void api(`chats/${id}`, { method: 'DELETE' }).catch((e) => setToast(e.message))
          if (id === current) open(null)
        }}
        onSettings={() => {
          setDrawer(false)
          setSettingsOpen(true)
        }}
      />
      <main className="main">
        <header className="topbar">
          <button type="button" className="iconbtn menuonly" aria-label="Chats" onClick={() => setDrawer(true)}>
            <Icon name="menu" />
          </button>
          <span className="toptitle">{title}</span>
          {current && (
            <span className="chip" title="Claude works in this folder">
              <Icon name="folder" size={12} />
              {state?.workDir ?? '/config'}
            </span>
          )}
          <span className="grow" />
          {!connected && <span className="chip warn">Reconnecting…</span>}
          {current && (
            <button type="button" className="iconbtn menuonly" aria-label="New chat" onClick={() => open(null)}>
              <Icon name="plus" />
            </button>
          )}
        </header>
        {current ? (
          chat ? (
            <ChatView
              chat={chat}
              state={state}
              draft={draft}
              onSend={send}
              onStop={() => socket.send({ t: 'stop', chatId: chat.id })}
              onSettings={changeChatSettings}
              onApprove={(id, decision, reason) => socket.send({ t: 'approve', chatId: chat.id, id, decision, reason })}
              onAnswer={(id, answers) => socket.send({ t: 'answer', chatId: chat.id, id, answers })}
              onPlan={(id, decision, feedback) => socket.send({ t: 'plan', chatId: chat.id, id, decision, feedback })}
            />
          ) : (
            <div className="loading">Loading the chat…</div>
          )
        ) : (
          <Home
            state={state}
            draft={draft}
            setDraft={setDraft}
            settings={homeSettings}
            setSettings={(s) => setHomeSettings((h) => ({ ...h, ...s }))}
            onSend={send}
            onAuthChanged={() => void loadState()}
            onOpenChat={open}
          />
        )}
      </main>
      {settingsOpen && state && <Settings state={state} onClose={() => setSettingsOpen(false)} onChanged={() => void loadState()} onOpenChat={open} />}
      {toast && (
        <div className="toast" role="status">
          {toast}
          <button type="button" className="iconbtn" aria-label="Dismiss" onClick={() => setToast(null)}>
            <Icon name="x" size={14} />
          </button>
        </div>
      )}
    </div>
  )
}
