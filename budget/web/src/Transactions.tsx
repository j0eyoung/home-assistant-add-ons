import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import { api, money, monthLabel } from './api.ts'
import type { Category, Transaction } from './api.ts'
import { photoToJpeg } from './photo.ts'
import { SplitEditor } from './SplitEditor.tsx'
import type { Proposal } from './SplitEditor.tsx'

const CADENCES = ['weekly', 'every 2 weeks', 'twice a month', 'monthly', 'quarterly', 'yearly']
const KINDS: [Category['kind'], string][] = [['expense', 'Spending'], ['income', 'Income'], ['savings', 'Savings'], ['transfer', 'Transfers']]
// Matches REVIEW_DAYS in server/db.ts.
const REVIEW_DAYS = 60

type OnError = (message: string) => void
type Mode = 'review' | 'all'
// What's open under a transaction; one at a time.
type Panel =
  | { kind: 'split'; proposal?: Proposal }
  | { kind: 'note' }
  | { kind: 'recurring' }
  | { kind: 'rule'; categoryId: number; others: number }
  | { kind: 'receipt'; categoryId: number; summary: string; warning?: string }

const label = (t: Transaction) => t.merchant || t.name
const day = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

// Whether a transaction is in the review queue (same test as NEEDS_REVIEW on the server).
function needsReview(t: Transaction) {
  const since = new Date(Date.now() - REVIEW_DAYS * 86400000).toISOString().slice(0, 10)
  return !t.reviewed && !t.pending && (t.category_source === 'ai' || t.category_source === 'none') && t.date >= since
}

function sourceTag(t: Transaction) {
  if (t.category_source === 'ai') return t.reviewed ? 'AI ✓' : 'AI guess'
  if (t.category_source === 'none') return 'not categorized'
  return t.category_source === 'rule' ? 'rule' : 'you'
}

// Categories grouped by kind. With a placeholder it acts as a picker that
// resets after each choice (bulk "Set category…").
export function CategorySelect({ categories, value, onChange, placeholder }: {
  categories: Category[]
  value: number | null
  onChange: (id: number) => void
  placeholder?: string
}) {
  return (
    <select value={value ?? ''} onChange={(e) => e.target.value && onChange(Number(e.target.value))}>
      {placeholder && <option value="">{placeholder}</option>}
      {KINDS.map(([kind, title]) => {
        const list = categories.filter((c) => c.kind === kind)
        return list.length ? (
          <optgroup key={kind} label={title}>
            {list.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </optgroup>
        ) : null
      })}
    </select>
  )
}

export function Transactions({ month, toReview, startInReview, onError, onReviewCount }: {
  month: string
  toReview: number
  startInReview: boolean
  onError: OnError
  onReviewCount: (n: number) => void
}) {
  const [mode, setMode] = useState<Mode>(startInReview ? 'review' : 'all')
  const [rows, setRows] = useState<Transaction[]>([])
  const [loaded, setLoaded] = useState(false)
  const [categories, setCategories] = useState<Category[]>([])
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState<{ id: string; panel: Panel } | null>(null)
  // Reviewed during this visit to the queue: hidden once their panel closes.
  const [done, setDone] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<Set<string>>(new Set())
  // Touch screens: the row whose actions are showing.
  const [focus, setFocus] = useState<string | null>(null)
  const [reading, setReading] = useState<string | null>(null)
  const [toast, setToast] = useState('')
  const receiptInput = useRef<HTMLInputElement>(null)
  const receiptFor = useRef<Transaction | null>(null)

  const load = useCallback(() => {
    const params = new URLSearchParams(mode === 'review' ? { review: '1' } : { month })
    if (mode === 'all' && q) params.set('q', q)
    if (mode === 'all' && category) params.set('category', category)
    api<Transaction[]>(`transactions?${params}`)
      .then((r) => {
        setRows(r)
        setLoaded(true)
      })
      .catch((e) => onError(e.message))
  }, [mode, month, q, category, onError])
  useEffect(load, [load])
  useEffect(() => {
    api<Category[]>('categories').then(setCategories).catch((e) => onError(e.message))
  }, [onError])

  const remaining = mode === 'review' ? rows.filter((t) => !done.has(t.id)).length : toReview
  useEffect(() => {
    if (mode === 'review' && loaded) onReviewCount(remaining)
  }, [mode, loaded, remaining, onReviewCount])

  const switchMode = (m: Mode) => {
    if (m === mode) return
    setMode(m)
    setLoaded(false)
    setRows([])
    setOpen(null)
    setDone(new Set())
    setSelected(new Set())
  }

  const categoryName = (id: number | null) => categories.find((c) => c.id === id)?.name ?? '—'
  const flash = (text: string) => {
    setToast(text)
    window.setTimeout(() => setToast((current) => (current === text ? '' : current)), 6000)
  }
  const patch = (t: Transaction, body: object) => api(`transactions/${encodeURIComponent(t.id)}`, 'PATCH', body)
  const fail = (e: any) => onError(e.message)

  // After transactions were reviewed: the queue hides them, the count drops.
  const touched = (ids: string[]) => {
    const set = new Set(ids)
    const leaving = rows.filter((t) => set.has(t.id) && needsReview(t)).length
    setRows((rs) => rs.map((t) => (set.has(t.id) ? { ...t, reviewed: 1 } : t)))
    if (mode === 'review') setDone((d) => new Set([...d, ...ids]))
    else if (leaving) onReviewCount(Math.max(0, toReview - leaving))
  }

  const togglePanel = (t: Transaction, panel: Panel) =>
    setOpen(open?.id === t.id && open.panel.kind === panel.kind ? null : { id: t.id, panel })

  const looksRight = async (t: Transaction) => {
    try {
      await patch(t, { reviewed: true })
      touched([t.id])
      if (open?.id === t.id) setOpen(null)
    } catch (e) {
      fail(e)
    }
  }

  // Saves the new category for this transaction only, then offers a merchant rule.
  const changeCategory = async (t: Transaction, categoryId: number) => {
    try {
      const r = await patch(t, { category_id: categoryId })
      setRows((rs) => rs.map((x) => (x.id === t.id ? { ...x, category_id: categoryId, category_source: 'user' } : x)))
      touched([t.id])
      setOpen({ id: t.id, panel: { kind: 'rule', categoryId, others: r.others } })
    } catch (e) {
      fail(e)
    }
  }

  const always = async (t: Transaction, categoryId: number) => {
    try {
      const r = await patch(t, { category_id: categoryId, remember: true })
      setOpen(null)
      flash(`${label(t)} will always go in ${categoryName(categoryId)}.${r.alsoUpdated ? ` Moved ${plural(r.alsoUpdated, 'other charge')}.` : ''}`)
      if (r.alsoUpdated) load()
    } catch (e) {
      fail(e)
    }
  }

  const bulk = async (body: object, ids: string[]) => {
    setBusy(true)
    try {
      await api('transactions/bulk', 'POST', { ids, ...body })
      touched(ids)
      setSelected(new Set())
      return true
    } catch (e) {
      fail(e)
      return false
    } finally {
      setBusy(false)
    }
  }

  const bulkCategory = async (categoryId: number) => {
    const ids = [...selected]
    if (await bulk({ category_id: categoryId }, ids)) {
      flash(`Moved ${plural(ids.length, 'transaction')} to ${categoryName(categoryId)}.`)
      load()
    }
  }

  const allRight = async () => {
    const ids = rows.filter((t) => !done.has(t.id) && open?.id !== t.id).map((t) => t.id)
    if (await bulk({ reviewed: true }, ids)) flash(`Marked ${plural(ids.length, 'transaction')} as right.`)
  }

  const toggleSelect = (id: string) =>
    setSelected((s) => {
      const next = new Set(s)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const recategorizeAll = async () => {
    setBusy(true)
    try {
      await api('categorize', 'POST', { force: true })
      load()
    } catch (e) {
      fail(e)
    }
    setBusy(false)
  }

  // Receipt photo: Claude groups the items into categories. One category asks
  // to recategorize; several open the split editor prefilled for confirmation.
  const pickReceipt = (t: Transaction) => {
    receiptFor.current = t
    receiptInput.current?.click()
  }
  const readReceipt = async (file: File | undefined) => {
    const t = receiptFor.current
    if (receiptInput.current) receiptInput.current.value = ''
    if (!file || !t) return
    setReading(t.id)
    try {
      const image = await photoToJpeg(file)
      const r = await api(`transactions/${encodeURIComponent(t.id)}/receipt`, 'POST', { image: image.data, media_type: image.mediaType })
      const warning = r.mismatch ? `The receipt total (${money(r.receiptTotal)}) doesn't match the charge (${money(t.amount)}); amounts were scaled to the charge. Check it's the right receipt.` : undefined
      setOpen(r.parts.length === 1
        ? { id: t.id, panel: { kind: 'receipt', categoryId: r.parts[0].category_id, summary: r.summary, warning } }
        : { id: t.id, panel: { kind: 'split', proposal: { parts: r.parts, summary: r.summary, warning } } })
    } catch (e) {
      fail(e)
    }
    setReading(null)
  }
  const acceptReceipt = async (t: Transaction, p: { categoryId: number; summary: string }) => {
    try {
      await patch(t, { category_id: p.categoryId, ...(t.notes ? {} : { notes: p.summary }) })
      setRows((rs) => rs.map((x) => (x.id === t.id ? { ...x, category_id: p.categoryId, category_source: 'user', notes: x.notes || p.summary } : x)))
      touched([t.id])
      setOpen(null)
    } catch (e) {
      fail(e)
    }
  }

  const saveNote = async (t: Transaction, notes: string) => {
    try {
      await patch(t, { notes })
      setRows((rs) => rs.map((x) => (x.id === t.id ? { ...x, notes: notes.trim() || null } : x)))
      setOpen(null)
    } catch (e) {
      fail(e)
    }
  }

  const markRecurring = async (t: Transaction, cadence: string) => {
    try {
      await api('recurring', 'PUT', { label: label(t), status: 'yes', cadence })
      setOpen(null)
      flash(`${label(t)} added to Recurring (${cadence}).`)
    } catch (e) {
      fail(e)
    }
  }

  const actions = (t: Transaction) =>
    reading === t.id ? (
      <span className="muted">reading receipt…</span>
    ) : (
      <>
        <button className="mini" onClick={() => togglePanel(t, { kind: 'note' })}>{t.notes ? 'edit note' : 'note'}</button>
        {!t.pending && <button className="mini" onClick={() => togglePanel(t, { kind: 'split' })}>split</button>}
        {!t.pending && t.amount > 0 && <button className="mini" onClick={() => pickReceipt(t)}>receipt</button>}
        {t.amount > 0 && <button className="mini" onClick={() => togglePanel(t, { kind: 'recurring' })}>recurring</button>}
      </>
    )

  const panelFor = (t: Transaction) => {
    if (open?.id !== t.id) return null
    const p = open.panel
    const close = () => setOpen(null)
    switch (p.kind) {
      case 'split':
        return (
          <SplitEditor key={p.proposal ? p.proposal.summary : 'manual'} t={t} categories={categories} proposal={p.proposal} onError={onError}
            onCancel={close}
            onDone={() => {
              close()
              touched([t.id])
              load()
            }} />
        )
      case 'rule':
        return (
          <div className="panel">
            <span>
              Always put “{label(t)}” in {categoryName(p.categoryId)}?{' '}
              <span className="muted">
                {p.others ? `Also moves ${plural(p.others, 'other charge')} from them, and future ones.` : 'Future charges from them will go there too.'}
              </span>
            </span>
            <span className="panel-actions">
              <button className="primary" onClick={() => always(t, p.categoryId)}>Always</button>
              <button onClick={close}>Just this one</button>
            </span>
          </div>
        )
      case 'receipt':
        return (
          <div className="panel">
            <span>
              <span className="note">{p.summary}</span>
              {p.warning && <span className="over small"> {p.warning}</span>}
              <br />Put this {money(t.amount)} charge in {categoryName(p.categoryId)}?
            </span>
            <span className="panel-actions">
              <button className="primary" onClick={() => acceptReceipt(t, p)}>Yes</button>
              <button onClick={close}>Cancel</button>
            </span>
          </div>
        )
      case 'note':
        return <NoteEditor initial={t.notes ?? ''} onSave={(n) => saveNote(t, n)} onCancel={close} />
      case 'recurring':
        return <RecurringPicker name={label(t)} onSave={(c) => markRecurring(t, c)} onCancel={close} />
    }
  }

  const visible = mode === 'review' ? rows.filter((t) => !done.has(t.id) || open?.id === t.id) : rows
  const allSelected = visible.length > 0 && visible.every((t) => selected.has(t.id))

  return (
    <section className="transactions">
      <div className="toolbar">
        <div className="segmented" role="tablist">
          <button role="tab" aria-selected={mode === 'review'} className={mode === 'review' ? 'active' : ''} onClick={() => switchMode('review')}>
            To review{remaining ? <span className="count">{remaining}</span> : null}
          </button>
          <button role="tab" aria-selected={mode === 'all'} className={mode === 'all' ? 'active' : ''} onClick={() => switchMode('all')}>
            All in {monthLabel(month, false)}
          </button>
        </div>
        {mode === 'all' && (
          <>
            <input className="grow" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="">All categories</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <span className="muted">{plural(rows.length, 'transaction')}</span>
            <button onClick={recategorizeAll} disabled={busy}>{busy ? 'Categorizing…' : 'Re-run AI categories'}</button>
          </>
        )}
        {/* capture opens the camera on phones; on desktop it's a normal file picker */}
        <input ref={receiptInput} type="file" accept="image/*" capture="environment" hidden onChange={(e) => readReceipt(e.target.files?.[0])} />
      </div>

      {toast && <p className="toast" role="status" onClick={() => setToast('')}>{toast}</p>}

      {mode === 'review' ? (
        <>
          {remaining > 0 ? (
            <div className="review-head">
              <p className="muted">
                Charges from the last {REVIEW_DAYS} days whose category is a guess. Fix the wrong ones (a fix can become a rule for that merchant), then mark the rest as right.
              </p>
              <span className="panel-actions">
                <button onClick={() => setSelected(allSelected ? new Set() : new Set(visible.map((t) => t.id)))}>{allSelected ? 'Select none' : 'Select all'}</button>
                <button className="primary" onClick={allRight} disabled={busy}>All {remaining} look right</button>
              </span>
            </div>
          ) : loaded && !visible.length ? (
            <p className="empty">✓ All caught up. New charges show up here after each bank sync.</p>
          ) : null}
          <div className="review-list">
            {visible.map((t) => (
              <div key={t.id} className={`review-card ${open?.id === t.id && open.panel.kind === 'split' ? 'wide' : ''} ${selected.has(t.id) ? 'selected' : ''}`}>
                <div className="rc-top">
                  <input type="checkbox" checked={selected.has(t.id)} onChange={() => toggleSelect(t.id)} aria-label={`Select ${label(t)}`} />
                  <div className="rc-what">
                    <div className="rc-merchant">{label(t)}</div>
                    <div className="muted">
                      {day(t.date)}{t.account_name ? ` · ${t.account_name}` : ''}{t.merchant && t.name && t.name !== t.merchant ? ` · ${t.name}` : ''}
                    </div>
                    {t.notes && <div className="note">{t.notes}</div>}
                  </div>
                  <div className={`num rc-amount ${t.amount < 0 ? 'inflow' : ''}`}>{money(-t.amount)}</div>
                </div>
                <div className="rc-cat">
                  {t.splits.length ? (
                    <span>Split into {t.splits.length}</span>
                  ) : (
                    <>
                      <CategorySelect categories={categories} value={t.category_id} onChange={(id) => changeCategory(t, id)} />
                      {/* Every card is the AI's guess; only say so when it's something else. */}
                      {(t.category_source !== 'ai' || t.reviewed > 0) && <span className="tag">{sourceTag(t)}</span>}
                    </>
                  )}
                  {!done.has(t.id) && <button className="primary right-end" onClick={() => looksRight(t)}>Looks right</button>}
                </div>
                <div className="rc-actions">{actions(t)}</div>
                {panelFor(t)}
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="table-wrap">
          <table className="tx-table">
            <thead>
              <tr>
                <th className="sel">
                  <input type="checkbox" checked={allSelected} aria-label="Select all"
                    onChange={() => setSelected(allSelected ? new Set() : new Set(rows.map((t) => t.id)))} />
                </th>
                <th className="date">Date</th><th>Description</th><th className="acct">Account</th><th className="category">Category</th><th className="num">Amount</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => {
                const splitTotal = t.splits.reduce((s, p) => s + p.amount, 0)
                return (
                  <Fragment key={t.id}>
                    <tr className={[t.pending ? 'pending' : '', focus === t.id ? 'focused' : '', selected.has(t.id) ? 'selected' : ''].join(' ')}>
                      <td className="sel"><input type="checkbox" checked={selected.has(t.id)} onChange={() => toggleSelect(t.id)} aria-label={`Select ${label(t)}`} /></td>
                      <td className="date">{t.date}</td>
                      <td className="desc-cell">
                        <div className="desc">
                          <span className="desc-text" title={t.name !== label(t) ? t.name : undefined}>{label(t)}{t.pending ? ' (pending)' : ''}</span>
                          <button className="mini more" aria-label="Actions" onClick={() => setFocus(focus === t.id ? null : t.id)}>⋯</button>
                          <span className={`row-actions ${reading === t.id ? 'busy' : ''}`}>{actions(t)}</span>
                        </div>
                        <div className="tx-meta muted">{day(t.date)}{t.account_name ? ` · ${t.account_name}` : ''}</div>
                        {t.notes && <div className="note">{t.notes}</div>}
                      </td>
                      <td className="acct muted">{t.account_name}</td>
                      <td className="category">
                        {t.splits.length ? (
                          <button className="mini split-label" onClick={() => togglePanel(t, { kind: 'split' })}>
                            Split into {t.splits.length}{Math.abs(splitTotal - t.amount) > 0.005 ? ' ⚠' : ''}
                          </button>
                        ) : (
                          <>
                            <CategorySelect categories={categories} value={t.category_id} onChange={(id) => changeCategory(t, id)} />
                            <span className={`tag ${needsReview(t) ? 'guess' : ''}`}>{sourceTag(t)}</span>
                          </>
                        )}
                      </td>
                      <td className={`num ${t.amount < 0 ? 'inflow' : ''}`}>{money(-t.amount)}</td>
                    </tr>
                    {t.splits.map((s) => (
                      <tr className="split-row" key={`${t.id}-${s.id}`}>
                        <td className="sel" />
                        <td className="date" />
                        <td className="muted">↳ part</td>
                        <td className="acct" />
                        <td className="category">{categoryName(s.category_id)}</td>
                        <td className="num muted">{money(-s.amount)}</td>
                      </tr>
                    ))}
                    {open?.id === t.id && (
                      <tr className="panel-row">
                        <td colSpan={6}>{panelFor(t)}</td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
          {loaded && !rows.length && <p className="muted">No transactions{q || category ? ' match' : ` in ${monthLabel(month)}`}.</p>}
        </div>
      )}

      {/* After the list so it sticks to the bottom of the screen while scrolling through it. */}
      {selected.size > 0 && (
        <div className="bulk-bar">
          <strong>{selected.size} selected</strong>
          <CategorySelect categories={categories} value={null} placeholder="Move to…" onChange={bulkCategory} />
          {mode === 'review' && <button onClick={() => bulk({ reviewed: true }, [...selected])} disabled={busy}>Looks right</button>}
          <button onClick={() => setSelected(new Set())}>Clear</button>
        </div>
      )}
    </section>
  )
}

function NoteEditor({ initial, onSave, onCancel }: { initial: string; onSave: (notes: string) => void; onCancel: () => void }) {
  const [text, setText] = useState(initial)
  return (
    <form className="panel" onSubmit={(e) => { e.preventDefault(); onSave(text) }}>
      <input className="grow" autoFocus placeholder="Note" value={text} onChange={(e) => setText(e.target.value)} />
      <span className="panel-actions">
        <button className="primary" type="submit">Save note</button>
        <button type="button" onClick={onCancel}>Cancel</button>
      </span>
    </form>
  )
}

function RecurringPicker({ name, onSave, onCancel }: { name: string; onSave: (cadence: string) => void; onCancel: () => void }) {
  const [cadence, setCadence] = useState('monthly')
  return (
    <div className="panel">
      <label>
        How often does {name} charge?
        <select value={cadence} onChange={(e) => setCadence(e.target.value)}>
          {CADENCES.map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      <span className="panel-actions">
        <button className="primary" onClick={() => onSave(cadence)}>Add to Recurring</button>
        <button onClick={onCancel}>Cancel</button>
      </span>
    </div>
  )
}
