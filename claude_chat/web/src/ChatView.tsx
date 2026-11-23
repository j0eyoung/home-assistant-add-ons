import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { AppState, ChatStatus, Item } from '../../shared/types.ts'
import { splitQuotes } from '../../shared/types.ts'
import { api } from './api.ts'
import { Icon } from './Icon.tsx'
import { Markdown } from './Markdown.tsx'
import { ApprovalCard, PlanCard, QuestionCard, Thinking, ToolRow } from './Items.tsx'
import { Composer } from './Composer.tsx'
import type { Outgoing } from './Composer.tsx'

export type ChatData = { id: string; title: string; items: Item[]; status: ChatStatus; model: string; effort: string; mode: string }

type Props = {
  chat: ChatData
  state: AppState | null
  draft: { text: string; n: number } | null
  onSend: (o: Outgoing) => void
  onStop: () => void
  onSettings: (s: { model?: string; effort?: string; mode?: string }) => void
  onApprove: (id: string, d: 'once' | 'always' | 'deny', reason?: string) => void
  onAnswer: (id: string, a: Record<string, string> | null) => void
  onPlan: (id: string, d: 'auto' | 'ask' | 'keep', fb?: string) => void
}

function Elapsed({ since }: { since: number }) {
  const [, tick] = useState(0)
  useEffect(() => {
    const t = setInterval(() => tick((x) => x + 1), 1000)
    return () => clearInterval(t)
  }, [])
  const s = Math.max(0, Math.round((Date.now() - since) / 1000))
  return <>{s < 60 ? `${s}s` : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`}</>
}

// Select text in the conversation and a "Quote" button appears by it; the quote goes above your next message.
type Picked = { text: string; x: number; y: number; below: boolean }

function useQuotePicker(scroller: React.RefObject<HTMLDivElement | null>) {
  const [picked, setPicked] = useState<Picked | null>(null)
  const pressing = useRef(false)
  const dragging = useRef(false)

  useEffect(() => {
    // On a phone the system's own copy menu sits above the selection, so the button goes below it
    const coarse = window.matchMedia('(pointer: coarse)').matches
    let raf = 0
    const update = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const el = scroller.current
        const s = window.getSelection()
        const text = s && !s.isCollapsed && s.rangeCount ? s.toString().trim() : ''
        if (!el || !s || !text || !el.contains(s.anchorNode) || !el.contains(s.focusNode)) {
          if (!pressing.current) setPicked(null)
          return
        }
        if (dragging.current) return setPicked(null)
        const r = s.getRangeAt(0).getBoundingClientRect()
        const box = el.getBoundingClientRect()
        const below = coarse || r.top - 44 < box.top
        const y = Math.min(Math.max(below ? r.bottom + 8 : r.top - 8, box.top + 44), box.bottom - 8)
        const x = Math.min(Math.max(r.left + r.width / 2, box.left + 60), box.right - 60)
        setPicked({ text, x, y, below })
      })
    }
    const down = (e: PointerEvent) => {
      if (e.pointerType === 'mouse' && !(e.target as HTMLElement).closest('.quotebtn')) dragging.current = true
    }
    const up = () => {
      if (!dragging.current) return
      dragging.current = false
      update()
    }
    const el = scroller.current
    document.addEventListener('selectionchange', update)
    document.addEventListener('pointerdown', down)
    document.addEventListener('pointerup', up)
    el?.addEventListener('scroll', update, { passive: true })
    return () => {
      cancelAnimationFrame(raf)
      document.removeEventListener('selectionchange', update)
      document.removeEventListener('pointerdown', down)
      document.removeEventListener('pointerup', up)
      el?.removeEventListener('scroll', update)
    }
  }, [])

  const clear = () => {
    pressing.current = false
    window.getSelection()?.removeAllRanges()
    setPicked(null)
  }
  return { picked, pressing, clear }
}

function UserText({ text }: { text: string }) {
  const parts = useMemo(() => splitQuotes(text), [text])
  if (!parts.some((x) => x.quote)) return <div className="usertext">{text}</div>
  return (
    <>
      {parts.map((x, i) =>
        x.quote ? (
          <div key={i} className="userquote">
            {x.text}
          </div>
        ) : (
          <div key={i} className="usertext">
            {x.text}
          </div>
        ),
      )}
    </>
  )
}

export function ChatView(p: Props) {
  const scroller = useRef<HTMLDivElement>(null)
  const stick = useRef(true)
  const [runSince, setRunSince] = useState(Date.now())
  const [quote, setQuote] = useState<{ text: string; n: number } | null>(null)
  const { picked, pressing, clear } = useQuotePicker(scroller)
  const { chat } = p

  const addQuote = () => {
    if (!picked) return
    setQuote((q) => ({ text: picked.text, n: (q?.n ?? 0) + 1 }))
    clear()
  }

  useEffect(() => {
    if (chat.status === 'running') setRunSince((x) => (x && Date.now() - x < 2000 ? x : Date.now()))
  }, [chat.status === 'running'])

  // Children of helper agents render inside their parent tool row
  const { top, children } = useMemo(() => {
    const children = new Map<string, Item[]>()
    const top: Item[] = []
    for (const it of chat.items) {
      const parent = (it as any).parent as string | null | undefined
      if (parent) children.set(parent, [...(children.get(parent) ?? []), it])
      else top.push(it)
    }
    return { top, children }
  }, [chat.items])

  useLayoutEffect(() => {
    const el = scroller.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  })

  const onScroll = () => {
    const el = scroller.current
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120
  }

  const lastText = [...top].reverse().find((it) => it.kind === 'text')
  const streamingId = chat.status === 'running' && top[top.length - 1]?.kind === 'text' ? top[top.length - 1].id : null
  const liveThinking = chat.status === 'running' && top[top.length - 1]?.kind === 'thinking' ? top[top.length - 1].id : null
  const showCost = p.state?.auth.method === 'api_key'

  const undo = (toolUseId: string) => async (force?: boolean) => {
    const r = await api<{ ok: boolean; error?: string }>(`chats/${chat.id}/undo`, { method: 'POST', json: { toolUseId, force } }).catch((e) => ({ ok: false, error: e.message }))
    return r.ok ? null : r.error ?? 'Couldn’t undo that change.'
  }

  return (
    <div className="chatview">
      <div className="thread" ref={scroller} onScroll={onScroll}>
        <div className="col">
          {top.map((it) => {
            switch (it.kind) {
              case 'user':
                return (
                  <div key={it.id} className="user">
                    {it.images ? (
                      <span className="imgnote">
                        <Icon name="image" size={14} /> {it.images} picture{it.images > 1 ? 's' : ''}
                      </span>
                    ) : null}
                    <UserText text={it.text} />
                  </div>
                )
              case 'text':
                return it.text.trim() ? <Markdown key={it.id} text={it.text} className={`claude ${it.id === streamingId ? 'streaming' : ''}`} /> : null
              case 'thinking':
                return it.text.trim() || it.id === liveThinking ? <Thinking key={it.id} text={it.text} live={it.id === liveThinking} /> : null
              case 'tool':
                return <ToolRow key={it.id} item={it} children={children.get(it.id)} onUndo={undo(it.id)} />
              case 'approval':
                return <ApprovalCard key={it.id} item={it} onDecide={(d, r) => p.onApprove(it.id, d, r)} />
              case 'question':
                return <QuestionCard key={it.id} item={it} onAnswer={(a) => p.onAnswer(it.id, a)} />
              case 'plan':
                return <PlanCard key={it.id} item={it} onDecide={(d, fb) => p.onPlan(it.id, d, fb)} />
              case 'notice':
                return (
                  <div key={it.id} className={`notice ${it.level}`}>
                    <Icon name={it.level === 'ok' ? 'check' : it.level === 'error' ? 'x' : it.level === 'warn' ? 'shield' : 'spark'} size={14} />
                    <span>{it.text}</span>
                  </div>
                )
              case 'done':
                return it.error ? (
                  <div key={it.id} className="notice error">
                    <Icon name="x" size={14} />
                    <span>{it.error}</span>
                  </div>
                ) : (
                  <div key={it.id} className="turnfoot">
                    {it.seconds >= 1 ? `Worked for ${it.seconds < 60 ? `${Math.round(it.seconds)}s` : `${Math.floor(it.seconds / 60)}m ${Math.round(it.seconds % 60)}s`}` : ''}
                    {showCost && it.cost ? ` · $${it.cost.toFixed(2)}` : ''}
                  </div>
                )
            }
          })}
          {chat.status !== 'idle' && (
            <div className={`working ${chat.status}`}>
              <span className="dot" />
              {chat.status === 'waiting' ? 'Waiting for you' : streamingId ? 'Writing' : 'Working'}
              {chat.status === 'running' && (
                <span className="muted">
                  {' '}
                  · <Elapsed since={runSince} />
                </span>
              )}
            </div>
          )}
          {!top.length && <p className="hint center">Loading the chat…</p>}
          {lastText === undefined && chat.status === 'idle' && top.length > 0 && <div className="spacer" />}
        </div>
      </div>
      {picked && (
        <button
          type="button"
          className={`quotebtn ${picked.below ? 'below' : 'above'}`}
          style={{ left: picked.x, top: picked.y }}
          onPointerDown={() => (pressing.current = true)}
          onPointerCancel={() => (pressing.current = false)}
          onMouseDown={(e) => e.preventDefault()}
          onClick={addQuote}
        >
          <Icon name="quote" size={14} />
          Quote
        </button>
      )}
      <div className="composerdock">
        <Composer
          quote={quote}
          scope={chat.id}
          placeholder="Reply to Claude…"
          running={chat.status !== 'idle'}
          models={p.state?.models ?? []}
          commands={p.state?.commands ?? []}
          model={chat.model}
          effort={chat.effort}
          mode={chat.mode}
          onChange={p.onSettings}
          onSend={p.onSend}
          onStop={p.onStop}
          draft={p.draft}
        />
      </div>
    </div>
  )
}
