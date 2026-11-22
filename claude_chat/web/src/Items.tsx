import { useState } from 'react'
import type { Item, Question } from '../../shared/types.ts'
import { Icon } from './Icon.tsx'
import { Markdown, highlight } from './Markdown.tsx'

const base = (p: string) => String(p ?? '').split(/[\\/]/).pop() || String(p ?? '')

// ---- diffs ----

type Line = { t: ' ' | '+' | '-'; s: string }

export function lineDiff(a: string, b: string): Line[] {
  const A = a.split('\n')
  const B = b.split('\n')
  if (A.length * B.length > 250_000) return [...A.map((s) => ({ t: '-' as const, s })), ...B.map((s) => ({ t: '+' as const, s }))]
  const dp: number[][] = Array.from({ length: A.length + 1 }, () => new Array(B.length + 1).fill(0))
  for (let i = A.length - 1; i >= 0; i--) for (let j = B.length - 1; j >= 0; j--) dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
  const out: Line[] = []
  let i = 0
  let j = 0
  while (i < A.length && j < B.length) {
    if (A[i] === B[j]) {
      out.push({ t: ' ', s: A[i] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({ t: '-', s: A[i++] })
    else out.push({ t: '+', s: B[j++] })
  }
  while (i < A.length) out.push({ t: '-', s: A[i++] })
  while (j < B.length) out.push({ t: '+', s: B[j++] })
  return out
}

function editLines(name: string, input: any): Line[] {
  if (name === 'Write') return String(input?.content ?? '').split('\n').map((s) => ({ t: '+' as const, s }))
  if (name === 'MultiEdit') return (input?.edits ?? []).flatMap((e: any, k: number) => [...(k ? [{ t: ' ' as const, s: '⋯' }] : []), ...lineDiff(String(e.old_string ?? ''), String(e.new_string ?? ''))])
  if (name === 'NotebookEdit') return String(input?.new_source ?? '').split('\n').map((s) => ({ t: '+' as const, s }))
  return lineDiff(String(input?.old_string ?? ''), String(input?.new_string ?? ''))
}

export function Diff({ name, input, path }: { name: string; input: any; path?: string }) {
  const lines = editLines(name, input)
  const lang = /\.ya?ml$/i.test(path ?? '') ? 'yaml' : /\.json$/i.test(path ?? '') ? 'json' : /\.py$/i.test(path ?? '') ? 'python' : undefined
  return (
    <div className="diff">
      {path && <div className="diffhead">{path}</div>}
      <div className="diffbody">
        {lines.map((l, k) => (
          <div key={k} className={l.t === '+' ? 'add' : l.t === '-' ? 'del' : 'ctx'}>
            <span className="sign">{l.t === ' ' ? '' : l.t}</span>
            <span dangerouslySetInnerHTML={{ __html: highlight(l.s, lang) || '&nbsp;' }} />
          </div>
        ))}
      </div>
    </div>
  )
}

const counts = (name: string, input: any) => {
  const l = editLines(name, input)
  return { add: l.filter((x) => x.t === '+').length, del: l.filter((x) => x.t === '-').length }
}

// ---- tool rows ----

function toolLabel(name: string, input: any): { icon: string; verb: string; target: string } {
  switch (name) {
    case 'Read':
      return { icon: 'file', verb: 'Read', target: base(input.file_path) }
    case 'Edit':
    case 'MultiEdit':
      return { icon: 'edit', verb: 'Edited', target: base(input.file_path) }
    case 'Write':
      return { icon: 'write', verb: 'Wrote', target: base(input.file_path) }
    case 'NotebookEdit':
      return { icon: 'edit', verb: 'Edited', target: base(input.notebook_path) }
    case 'Bash':
      return { icon: 'term', verb: input.description ? '' : 'Ran', target: input.description || String(input.command ?? '').split('\n')[0] }
    case 'Glob':
      return { icon: 'search', verb: 'Found files', target: input.pattern ?? '' }
    case 'Grep':
      return { icon: 'search', verb: 'Searched for', target: `“${input.pattern ?? ''}”` }
    case 'WebFetch':
      return { icon: 'globe', verb: 'Read', target: input.url ?? '' }
    case 'WebSearch':
      return { icon: 'globe', verb: 'Searched the web for', target: `“${input.query ?? ''}”` }
    case 'TodoWrite':
      return { icon: 'list', verb: 'Updated the task list', target: '' }
    case 'Task':
    case 'Agent':
      return { icon: 'robot', verb: 'Helper', target: input.description ?? '' }
    case 'Skill':
      return { icon: 'bolt', verb: 'Used skill', target: input.skill ?? input.name ?? '' }
    default:
      if (name.startsWith('mcp__')) {
        const [, server, ...rest] = name.split('__')
        const action = rest.join(' ').replace(/^ha_/, '').replace(/_/g, ' ')
        const who = server === 'home-assistant' ? 'Home Assistant' : server
        const what = input.entity_id ?? input.domain ? [input.domain && input.service ? `${input.domain}.${input.service}` : '', input.entity_id ?? ''].filter(Boolean).join(' ') : ''
        return { icon: server === 'home-assistant' ? 'home' : 'bolt', verb: `${who} · ${action}`, target: String(what) }
      }
      return { icon: 'bolt', verb: name, target: '' }
  }
}

function Todos({ todos }: { todos: any[] }) {
  return (
    <ul className="todos">
      {todos.map((t, k) => (
        <li key={k} className={t.status}>
          <span className="box">{t.status === 'completed' ? <Icon name="check" size={12} /> : null}</span>
          {t.status === 'in_progress' ? t.activeForm || t.content : t.content}
        </li>
      ))}
    </ul>
  )
}

export function ToolRow({ item, children, onUndo }: { item: Extract<Item, { kind: 'tool' }>; children?: Item[]; onUndo: (force?: boolean) => Promise<string | null> }) {
  const [open, setOpen] = useState(false)
  const [undoMsg, setUndoMsg] = useState<string | null>(null)
  const label = toolLabel(item.name, item.input)
  const { icon, target } = label
  const RUNNING: Record<string, string> = { Read: 'Reading', Edited: 'Editing', Wrote: 'Writing', Ran: 'Running', 'Found files': 'Finding files', 'Searched for': 'Searching for' }
  const verb = item.status === 'running' ? RUNNING[label.verb] ?? label.verb : label.verb
  const isEdit = ['Edit', 'MultiEdit', 'Write', 'NotebookEdit'].includes(item.name)
  const c = isEdit ? counts(item.name, item.input) : null

  if (item.name === 'TodoWrite' && Array.isArray(item.input?.todos)) {
    return (
      <div className="tool todo-card">
        <div className="toolhead static">
          <Icon name="list" />
          <span>Tasks</span>
        </div>
        <Todos todos={item.input.todos} />
      </div>
    )
  }

  const undo = async (force = false) => {
    const err = await onUndo(force)
    setUndoMsg(err)
  }

  return (
    <div className={`tool ${item.status}`}>
      <button type="button" className="toolhead" onClick={() => setOpen(!open)} aria-expanded={open}>
        <Icon name={icon} />
        <span className="toolname">
          {verb && <b>{verb}</b>} {target}
          {c && (
            <span className="counts">
              {c.add > 0 && <span className="plus"> +{c.add}</span>}
              {c.del > 0 && <span className="minus"> −{c.del}</span>}
            </span>
          )}
          {children && children.length > 0 && <span className="muted"> · {children.filter((x) => x.kind === 'tool').length} steps</span>}
        </span>
        <span className="toolstate">
          {item.status === 'running' ? <span className="spin" /> : item.status === 'error' ? <Icon name="x" className="err" /> : <Icon name="check" className="ok" />}
          <Icon name={open ? 'down' : 'right'} size={14} />
        </span>
      </button>
      {item.undo === 'available' && (
        <div className="undo">
          <button type="button" className="linkbtn" onClick={() => void undo()}>
            <Icon name="undo" size={14} /> Undo this change
          </button>
          {undoMsg && (
            <div className="undomsg">
              {undoMsg}{' '}
              <button type="button" className="linkbtn" onClick={() => void undo(true)}>
                Undo anyway
              </button>
            </div>
          )}
        </div>
      )}
      {item.undo === 'done' && <div className="undo muted">Change undone</div>}
      {open && (
        <div className="tooldetail">
          {isEdit ? (
            <Diff name={item.name} input={item.input} path={item.input.file_path ?? item.input.notebook_path} />
          ) : item.name === 'Bash' ? (
            <pre className="cmd">
              <code dangerouslySetInnerHTML={{ __html: '$ ' + highlight(String(item.input.command ?? ''), 'bash') }} />
            </pre>
          ) : Object.keys(item.input ?? {}).length ? (
            <pre className="json">
              <code dangerouslySetInnerHTML={{ __html: highlight(JSON.stringify(item.input, null, 2), 'json') }} />
            </pre>
          ) : null}
          {item.result && !isEdit && <pre className={`output ${item.status === 'error' ? 'error' : ''}`}>{item.result}</pre>}
          {item.result && isEdit && item.status === 'error' && <pre className="output error">{item.result}</pre>}
          {children && children.length > 0 && (
            <div className="children">
              {children.map((ch) => (ch.kind === 'tool' ? <ToolRow key={ch.id} item={ch} onUndo={async () => null} /> : ch.kind === 'text' && ch.text.trim() ? <Markdown key={ch.id} text={ch.text} className="childtext" /> : null))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---- approvals, questions, plans ----

export function ApprovalCard({ item, onDecide }: { item: Extract<Item, { kind: 'approval' }>; onDecide: (d: 'once' | 'always' | 'deny', reason?: string) => void }) {
  const [why, setWhy] = useState<string | null>(null)
  const isEdit = ['Edit', 'MultiEdit', 'Write', 'NotebookEdit'].includes(item.tool)
  if (item.status !== 'pending') {
    return (
      <div className={`decided ${item.status}`}>
        <Icon name={item.status === 'allowed' ? 'check' : 'x'} size={14} />
        {item.status === 'allowed' ? 'Allowed' : item.status === 'denied' ? 'Declined' : 'Cancelled'}: {item.title.replace(/^Claude wants to /, '')}
      </div>
    )
  }
  return (
    <div className="card approval">
      <div className="cardhead">
        <Icon name="shield" />
        {item.title}
      </div>
      {item.risk && <div className="risk">{item.risk}</div>}
      {isEdit ? (
        <Diff name={item.tool} input={item.input} path={item.input.file_path ?? item.input.notebook_path} />
      ) : item.tool === 'Bash' ? (
        <pre className="cmd">
          <code dangerouslySetInnerHTML={{ __html: highlight(String(item.input.command ?? ''), 'bash') }} />
        </pre>
      ) : (
        <pre className="json">
          <code dangerouslySetInnerHTML={{ __html: highlight(JSON.stringify(item.input, null, 2), 'json') }} />
        </pre>
      )}
      {why === null ? (
        <div className="btns">
          <button type="button" className="btn primary" onClick={() => onDecide('once')} autoFocus>
            Allow
          </button>
          <button type="button" className="btn" onClick={() => onDecide('always')}>
            {item.alwaysLabel}
          </button>
          <button type="button" className="btn" onClick={() => onDecide('deny')}>
            Deny
          </button>
          <button type="button" className="linkbtn" onClick={() => setWhy('')}>
            Deny and say why
          </button>
        </div>
      ) : (
        <form
          className="whyform"
          onSubmit={(e) => {
            e.preventDefault()
            onDecide('deny', why)
          }}
        >
          <input id={`why-${item.id}`} value={why} onChange={(e) => setWhy(e.target.value)} placeholder="What should Claude do instead?" autoFocus />
          <button type="submit" className="btn">
            Deny
          </button>
          <button type="button" className="linkbtn" onClick={() => setWhy(null)}>
            Back
          </button>
        </form>
      )}
    </div>
  )
}

function QuestionBlock({ q, value, onChange }: { q: Question; value: string[]; onChange: (v: string[]) => void }) {
  const [other, setOther] = useState('')
  const toggle = (label: string) => {
    if (q.multiSelect) onChange(value.includes(label) ? value.filter((v) => v !== label) : [...value, label])
    else onChange([label])
  }
  return (
    <div className="qblock">
      <div className="qhead">
        <span className="chip">{q.header}</span>
        {q.question}
      </div>
      <div className="qopts">
        {q.options.map((o) => (
          <button type="button" key={o.label} className={`qopt ${value.includes(o.label) ? 'on' : ''}`} onClick={() => toggle(o.label)}>
            <b>{o.label}</b>
            <span>{o.description}</span>
            {o.preview && value.includes(o.label) && <pre className="preview">{o.preview}</pre>}
          </button>
        ))}
        <input
          className="qother"
          placeholder="Something else…"
          value={other}
          onChange={(e) => {
            setOther(e.target.value)
            onChange(e.target.value ? [e.target.value] : [])
          }}
        />
      </div>
    </div>
  )
}

export function QuestionCard({ item, onAnswer }: { item: Extract<Item, { kind: 'question' }>; onAnswer: (a: Record<string, string> | null) => void }) {
  const [vals, setVals] = useState<Record<string, string[]>>({})
  if (item.status !== 'pending') {
    return (
      <div className={`decided ${item.status === 'answered' ? 'allowed' : 'cancelled'}`}>
        <Icon name={item.status === 'answered' ? 'check' : 'x'} size={14} />
        {item.status === 'answered' ? Object.entries(item.answers ?? {}).map(([q, a]) => `${q} ${a}`).join(' · ') : 'Questions skipped'}
      </div>
    )
  }
  const ready = item.questions.every((q) => (vals[q.question] ?? []).length > 0)
  return (
    <div className="card question">
      <div className="cardhead">
        <Icon name="spark" />
        Claude has {item.questions.length === 1 ? 'a question' : 'some questions'}
      </div>
      {item.questions.map((q) => (
        <QuestionBlock key={q.question} q={q} value={vals[q.question] ?? []} onChange={(v) => setVals({ ...vals, [q.question]: v })} />
      ))}
      <div className="btns">
        <button type="button" className="btn primary" disabled={!ready} onClick={() => onAnswer(Object.fromEntries(item.questions.map((q) => [q.question, (vals[q.question] ?? []).join(', ')])))}>
          Send answers
        </button>
        <button type="button" className="btn" onClick={() => onAnswer(null)}>
          Skip
        </button>
      </div>
    </div>
  )
}

export function PlanCard({ item, onDecide }: { item: Extract<Item, { kind: 'plan' }>; onDecide: (d: 'auto' | 'ask' | 'keep', feedback?: string) => void }) {
  const [fb, setFb] = useState<string | null>(null)
  return (
    <div className={`card plan ${item.status}`}>
      <div className="cardhead">
        <Icon name="list" />
        {item.status === 'pending' ? 'Claude’s plan' : item.status === 'approved' ? 'Plan approved' : item.status === 'rejected' ? 'Kept planning' : 'Plan'}
      </div>
      <Markdown text={item.plan} />
      {item.status === 'pending' &&
        (fb === null ? (
          <div className="btns">
            <button type="button" className="btn primary" onClick={() => onDecide('auto')}>
              Go ahead, edit automatically
            </button>
            <button type="button" className="btn" onClick={() => onDecide('ask')}>
              Go ahead, ask before edits
            </button>
            <button type="button" className="btn" onClick={() => setFb('')}>
              Keep planning
            </button>
          </div>
        ) : (
          <form
            className="whyform"
            onSubmit={(e) => {
              e.preventDefault()
              onDecide('keep', fb)
            }}
          >
            <input id={`fb-${item.id}`} value={fb} onChange={(e) => setFb(e.target.value)} placeholder="What should change in the plan?" autoFocus />
            <button type="submit" className="btn">
              Send
            </button>
          </form>
        ))}
    </div>
  )
}

export function Thinking({ text, live }: { text: string; live: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="thinking">
      <button type="button" className="linkbtn" onClick={() => setOpen(!open)} aria-expanded={open}>
        <Icon name={open ? 'down' : 'right'} size={14} />
        {live ? <span className="shimmer">Thinking</span> : 'Thought about it'}
      </button>
      {open && <Markdown text={text} className="thinktext" />}
    </div>
  )
}
