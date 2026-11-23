import { useEffect, useRef, useState } from 'react'
import type { Mention, ModelOption, SlashCommand } from '../../shared/types.ts'
import { MODES, EFFORTS, asBlockquote } from '../../shared/types.ts'
import { api, readImage } from './api.ts'
import { Icon } from './Icon.tsx'

export type Outgoing = { text: string; images: { data: string; mediaType: string }[]; mentions: Mention[] }
type Img = { data: string; mediaType: string; url: string }

type Props = {
  placeholder: string
  running: boolean
  models: ModelOption[]
  commands: SlashCommand[]
  model: string
  effort: string
  mode: string
  onChange: (s: { model?: string; effort?: string; mode?: string }) => void
  onSend: (o: Outgoing) => void
  onStop: () => void
  draft?: { text: string; n: number } | null
  // Text picked with "Quote" in the conversation; each new n adds one quote above the message
  quote?: { text: string; n: number } | null
  // Quotes belong to one chat: they are dropped when this changes
  scope?: string
  big?: boolean
}

type Popup = { kind: 'mention'; query: string; start: number; items: Mention[]; sel: number } | { kind: 'command'; items: SlashCommand[]; sel: number } | null

const modeLabel = (m: string) => MODES.find((x) => x.value === m)?.label ?? m
const effortLabel = (e: string) => (e === 'xhigh' ? 'Extra high' : e === 'max' ? 'Max' : e[0].toUpperCase() + e.slice(1))

export function Composer(p: Props) {
  const [text, setText] = useState('')
  const [images, setImages] = useState<Img[]>([])
  const [mentions, setMentions] = useState<Mention[]>([])
  const [quotes, setQuotes] = useState<string[]>([])
  const [popup, setPopup] = useState<Popup>(null)
  const [menu, setMenu] = useState<'mode' | 'model' | null>(null)
  const [dragging, setDragging] = useState(false)
  const ta = useRef<HTMLTextAreaElement>(null)
  const fileIn = useRef<HTMLInputElement>(null)
  const seq = useRef(0)

  useEffect(() => {
    if (p.draft) {
      setText(p.draft.text)
      setTimeout(() => {
        ta.current?.focus()
        ta.current?.setSelectionRange(p.draft!.text.length, p.draft!.text.length)
      }, 0)
    }
  }, [p.draft?.n])

  useEffect(() => {
    const q = p.quote?.text.trim()
    if (!q) return
    setQuotes((cur) => (cur.includes(q) ? cur : [...cur, q]))
    setTimeout(() => ta.current?.focus(), 0)
  }, [p.quote?.n])

  useEffect(() => setQuotes([]), [p.scope])

  useEffect(() => {
    const el = ta.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, window.innerHeight * 0.4) + 'px'
  }, [text])

  useEffect(() => {
    if (!menu) return
    const close = (e: MouseEvent) => {
      if (!(e.target as HTMLElement).closest('.menu, .menubtn')) setMenu(null)
    }
    window.addEventListener('mousedown', close)
    return () => window.removeEventListener('mousedown', close)
  }, [menu])

  const addFiles = async (files: FileList | File[]) => {
    const list = [...files].filter((f) => f.type.startsWith('image/')).slice(0, 6 - images.length)
    const read = (await Promise.all(list.map(readImage))).filter(Boolean) as Img[]
    if (read.length) setImages((cur) => [...cur, ...read].slice(0, 6))
  }

  const refreshPopup = (value: string, caret: number) => {
    const before = value.slice(0, caret)
    const m = before.match(/(^|\s)@([\w.\-]*)$/)
    if (m) {
      const query = m[2]
      const start = caret - query.length - 1
      const my = ++seq.current
      void api<Mention[]>(`mentions?q=${encodeURIComponent(query)}`)
        .then((items) => {
          if (my === seq.current) setPopup(items.length ? { kind: 'mention', query, start, items, sel: 0 } : null)
        })
        .catch(() => setPopup(null))
      return
    }
    const c = value.match(/^\/([\w:-]*)$/)
    if (c && p.commands.length) {
      const items = p.commands.filter((x) => x.name.toLowerCase().includes(c[1].toLowerCase())).slice(0, 12)
      setPopup(items.length ? { kind: 'command', items, sel: 0 } : null)
      return
    }
    setPopup(null)
  }

  const pick = (idx?: number) => {
    if (!popup) return
    const i = idx ?? popup.sel
    if (popup.kind === 'mention') {
      const m = popup.items[i]
      if (!m) return
      const token = m.type === 'entity' ? `@${m.id}` : `@${m.label.replace(/\s+/g, '_')}`
      const caret = ta.current?.selectionStart ?? text.length
      const next = text.slice(0, popup.start) + token + ' ' + text.slice(caret)
      setText(next)
      setMentions((cur) => [...cur.filter((x) => !(x.type === m.type && x.id === m.id)), { ...m, label: token }])
      const pos = popup.start + token.length + 1
      setTimeout(() => ta.current?.setSelectionRange(pos, pos), 0)
    } else {
      const c = popup.items[i]
      if (!c) return
      setText(`/${c.name} `)
    }
    setPopup(null)
    ta.current?.focus()
  }

  const send = () => {
    const t = text.trim()
    if (!t && !images.length && !quotes.length) return
    const used = mentions.filter((m) => text.includes(m.label))
    const body = [...quotes.map(asBlockquote), t].filter(Boolean).join('\n\n')
    p.onSend({ text: body, images: images.map(({ data, mediaType }) => ({ data, mediaType })), mentions: used })
    setText('')
    setImages([])
    setMentions([])
    setQuotes([])
    setPopup(null)
  }

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (popup) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault()
        const n = popup.items.length
        setPopup({ ...popup, sel: (popup.sel + (e.key === 'ArrowDown' ? 1 : n - 1)) % n } as Popup)
        return
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        pick()
        return
      }
      if (e.key === 'Escape') {
        setPopup(null)
        return
      }
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  const model = p.models.find((m) => m.value === p.model)
  const efforts = model?.efforts?.length ? model.efforts : EFFORTS

  return (
    <div
      className={`composer ${p.big ? 'big' : ''} ${dragging ? 'dragging' : ''}`}
      onDragOver={(e) => {
        if ([...e.dataTransfer.items].some((i) => i.kind === 'file')) {
          e.preventDefault()
          setDragging(true)
        }
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        void addFiles(e.dataTransfer.files)
      }}
    >
      {popup && (
        <div className="popup" role="listbox">
          {popup.kind === 'mention'
            ? popup.items.map((m, i) => (
                <button type="button" key={`${m.type}:${m.id}`} className={i === popup.sel ? 'on' : ''} onMouseDown={(e) => (e.preventDefault(), pick(i))} role="option" aria-selected={i === popup.sel}>
                  <Icon name={m.type === 'area' ? 'home' : 'at'} size={14} />
                  <span className="plabel">{m.label}</span>
                  <span className="pdetail">{m.detail}</span>
                </button>
              ))
            : popup.items.map((c, i) => (
                <button type="button" key={c.name} className={i === popup.sel ? 'on' : ''} onMouseDown={(e) => (e.preventDefault(), pick(i))} role="option" aria-selected={i === popup.sel}>
                  <Icon name="slash" size={14} />
                  <span className="plabel">/{c.name}</span>
                  <span className="pdetail">{c.description}</span>
                </button>
              ))}
        </div>
      )}
      {quotes.length > 0 && (
        <div className="quotes">
          {quotes.map((q, i) => (
            <div className="quotechip" key={q}>
              <Icon name="quote" size={14} />
              <div className="quotetext">{q}</div>
              <button type="button" className="iconbtn" aria-label="Remove quote" title="Remove quote" onClick={() => setQuotes(quotes.filter((_, k) => k !== i))}>
                <Icon name="x" size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
      {images.length > 0 && (
        <div className="thumbs">
          {images.map((im, i) => (
            <div className="thumb" key={i}>
              <img src={im.url} alt={`Attached picture ${i + 1}`} />
              <button type="button" aria-label="Remove picture" onClick={() => setImages(images.filter((_, k) => k !== i))}>
                <Icon name="x" size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
      <textarea
        id="composer-input"
        ref={ta}
        rows={p.big ? 2 : 1}
        value={text}
        placeholder={p.placeholder}
        onChange={(e) => {
          setText(e.target.value)
          refreshPopup(e.target.value, e.target.selectionStart)
        }}
        onKeyDown={onKey}
        onPaste={(e) => {
          const files = [...e.clipboardData.files]
          if (files.some((f) => f.type.startsWith('image/'))) {
            e.preventDefault()
            void addFiles(files)
          }
        }}
        onBlur={() => setTimeout(() => setPopup(null), 150)}
      />
      <div className="bar">
        <button type="button" className="iconbtn" aria-label="Attach a picture" title="Attach a picture" onClick={() => fileIn.current?.click()}>
          <Icon name="paperclip" />
        </button>
        <input ref={fileIn} type="file" accept="image/*" multiple hidden onChange={(e) => e.target.files && void addFiles(e.target.files)} />
        <div className="menuwrap">
          <button type="button" className={`menubtn ${p.mode === 'bypassPermissions' ? 'danger' : ''}`} onClick={() => setMenu(menu === 'mode' ? null : 'mode')} aria-expanded={menu === 'mode'}>
            <Icon name="shield" size={14} />
            {modeLabel(p.mode)}
            <Icon name="down" size={12} />
          </button>
          {menu === 'mode' && (
            <div className="menu up">
              {MODES.map((m) => (
                <button
                  type="button"
                  key={m.value}
                  className={m.value === p.mode ? 'on' : ''}
                  onClick={() => {
                    p.onChange({ mode: m.value })
                    setMenu(null)
                  }}
                >
                  <b>{m.label}</b>
                  <span>{m.hint}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <span className="grow" />
        <div className="menuwrap">
          <button type="button" className="menubtn" onClick={() => setMenu(menu === 'model' ? null : 'model')} aria-expanded={menu === 'model'}>
            {model?.displayName ?? p.model} · {effortLabel(p.effort)}
            <Icon name="down" size={12} />
          </button>
          {menu === 'model' && (
            <div className="menu up right">
              {p.models.map((m) => (
                <button type="button" key={m.value} className={m.value === p.model ? 'on' : ''} onClick={() => p.onChange({ model: m.value })}>
                  <b>{m.displayName}</b>
                  {m.description && <span>{m.description}</span>}
                </button>
              ))}
              <div className="menusep">Effort</div>
              <div className="seg">
                {efforts.map((e) => (
                  <button type="button" key={e} className={e === p.effort ? 'on' : ''} onClick={() => p.onChange({ effort: e })}>
                    {effortLabel(e)}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        {p.running ? (
          <button type="button" className="sendbtn stop" aria-label="Stop" title="Stop" onClick={p.onStop}>
            <Icon name="stop" />
          </button>
        ) : null}
        <button type="button" className="sendbtn" aria-label="Send" title="Send (Enter)" onClick={send} disabled={!text.trim() && !images.length && !quotes.length}>
          <Icon name="up" />
        </button>
      </div>
    </div>
  )
}
