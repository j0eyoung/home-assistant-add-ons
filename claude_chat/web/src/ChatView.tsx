import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { AppState, ChatStatus, Item } from '../../shared/types.ts'
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

export function ChatView(p: Props) {
  const scroller = useRef<HTMLDivElement>(null)
  const stick = useRef(true)
  const [runSince, setRunSince] = useState(Date.now())
  const { chat } = p

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
                    <div className="usertext">{it.text}</div>
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
      <div className="composerdock">
        <Composer
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
