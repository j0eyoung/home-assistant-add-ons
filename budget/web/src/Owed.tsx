import { useCallback, useEffect, useState } from 'react'
import { api, money, shortDate } from './api.ts'
import { Icon } from './Icon.tsx'

type Charge = { id: string; transaction_id: string; date: string; description: string; amount: number; account: string | null; notes: string | null; repaid_by: string | null }
type Deposit = { id: string; date: string; description: string; amount: number; account: string | null; category?: string | null }
type Data = {
  categoryId: number | null
  total: number
  open: Charge[]
  paid: (Charge & { deposit: Deposit | null })[]
  deposits: Deposit[]
}

const cents = (n: number) => Math.round(n * 100)
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

// Transactions → Owed to you: charges in Reimbursable that haven't been paid
// back, each matched to the deposit that repays it (or marked paid back by hand).
export function OwedList({ onError, onCount }: { onError: (m: string) => void; onCount: (owed: { total: number; count: number }) => void }) {
  const [data, setData] = useState<Data | null>(null)
  const [matching, setMatching] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const show = useCallback((d: Data) => {
    setData(d)
    onCount({ total: d.total, count: d.open.length })
  }, [onCount])
  useEffect(() => {
    api<Data>('reimbursements').then(show).catch((e) => onError(e.message))
  }, [show, onError])

  const run = async (path: string, body?: object) => {
    setBusy(true)
    try {
      show(await api<Data>(path, 'POST', body))
      setMatching(null)
    } catch (e: any) {
      onError(e.message)
    }
    setBusy(false)
  }

  if (!data) return null
  return (
    <>
      <div className="review-head">
        <p className="muted">
          Charges in the <strong>Reimbursable</strong> category: money someone will pay back, so it doesn't count as spending.
          Put a charge here with its category (or <strong>paid back later</strong> on the charge). When the money arrives, match it to the deposit.
        </p>
        {data.open.length > 0 && <strong className="owed-total">{money(data.total)} owed</strong>}
      </div>
      {!data.open.length && <p className="empty"><Icon name="check" size={18} />Nothing waiting to be paid back.</p>}
      <div className="review-list">
        {data.open.map((c) => (
          <div key={c.id} className={`review-card ${matching === c.id ? 'wide' : ''}`}>
            <div className="rc-top">
              <div className="rc-what">
                <div className="rc-merchant">{c.description}</div>
                <div className="muted">{shortDate(c.date)}{c.account ? ` · ${c.account}` : ''}{c.id !== c.transaction_id ? ' · part of a split' : ''}</div>
                {c.notes && <div className="note">{c.notes}</div>}
              </div>
              <div className="num rc-amount">{money(c.amount)}</div>
            </div>
            {matching === c.id ? (
              <MatchPanel charge={c} open={data.open} deposits={data.deposits} busy={busy}
                onMatch={(deposit, charges) => run('reimbursements/match', { deposit, charges })} onCancel={() => setMatching(null)} />
            ) : (
              <div className="rc-actions">
                <button className="primary" onClick={() => setMatching(c.id)} disabled={busy}>Match a deposit</button>
                <button onClick={() => run(`reimbursements/${encodeURIComponent(c.transaction_id)}/paid`)} disabled={busy}>Paid back another way</button>
              </div>
            )}
          </div>
        ))}
      </div>
      {data.paid.length > 0 && (
        <details className="owed-paid">
          <summary>Paid back in the last 90 days ({data.paid.length})</summary>
          {data.paid.map((p) => (
            <div className="line" key={p.id}>
              <span>
                {p.description}<span className="small muted"> · {shortDate(p.date)} · </span>
                <span className="small muted">
                  {p.deposit ? `paid back by ${p.deposit.description}, ${shortDate(p.deposit.date)}` : 'marked paid back'}
                </span>
              </span>
              <span>
                {money(p.amount)}{' '}
                <button className="mini" onClick={() => run(`reimbursements/${encodeURIComponent(p.transaction_id)}/undo`)} disabled={busy}>Undo</button>
              </span>
            </div>
          ))}
        </details>
      )}
    </>
  )
}

// Pick the deposit, tick the charges it covers (this one ticked to start), see the difference.
function MatchPanel({ charge, open, deposits, busy, onMatch, onCancel }: {
  charge: Charge
  open: Charge[]
  deposits: Deposit[]
  busy: boolean
  onMatch: (deposit: string, charges: string[]) => void
  onCancel: () => void
}) {
  const [deposit, setDeposit] = useState<string | null>(null)
  const [ticked, setTicked] = useState<Set<string>>(new Set([charge.transaction_id]))
  const [all, setAll] = useState(false)
  // Exact matches to this charge first, then the newest.
  const sorted = [...deposits].sort((a, b) =>
    Number(cents(b.amount) === cents(charge.amount)) - Number(cents(a.amount) === cents(charge.amount)) || b.date.localeCompare(a.date))
  const shown = all ? sorted : sorted.slice(0, 8)
  const picked = deposits.find((d) => d.id === deposit)
  // A split charge's parts share one transaction; count each transaction once by its owed parts.
  const chargesTotal = open.filter((c) => ticked.has(c.transaction_id)).reduce((s, c) => s + c.amount, 0)
  const difference = picked ? cents(picked.amount) - cents(chargesTotal) : 0
  const toggle = (id: string) => setTicked((s) => {
    const next = new Set(s)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })
  const byTransaction = [...new Map(open.map((c) => [c.transaction_id, c])).values()]

  return (
    <div className="match-panel">
      <h3>Which deposit paid it back?</h3>
      {!deposits.length && <p className="muted small">No money has come into a bank account since this charge. Check back after the next sync.</p>}
      <div className="choice-list">
        {shown.map((d) => (
          <label key={d.id} className={`choice ${deposit === d.id ? 'on' : ''}`}>
            <input type="radio" name={`deposit-${charge.id}`} checked={deposit === d.id} onChange={() => setDeposit(d.id)} />
            <span className="grow-text">{d.description}<span className="muted small"> · {shortDate(d.date)}{d.account ? ` · ${d.account}` : ''}{d.category ? ` · ${d.category}` : ''}</span></span>
            <strong className="nowrap">{money(d.amount)}{cents(d.amount) === cents(charge.amount) && <span className="tag">same amount</span>}</strong>
          </label>
        ))}
      </div>
      {sorted.length > shown.length && <button className="mini" onClick={() => setAll(true)}>Show {sorted.length - shown.length} more</button>}
      {byTransaction.length > 1 && (
        <>
          <h3>Charges it covers</h3>
          <div className="choice-list">
            {byTransaction.map((c) => (
              <label key={c.transaction_id} className="choice">
                <input type="checkbox" checked={ticked.has(c.transaction_id)} onChange={() => toggle(c.transaction_id)} />
                <span className="grow-text">{c.description}<span className="muted small"> · {shortDate(c.date)}</span></span>
                <strong className="nowrap">{money(open.filter((o) => o.transaction_id === c.transaction_id).reduce((s, o) => s + o.amount, 0))}</strong>
              </label>
            ))}
          </div>
        </>
      )}
      {picked && (
        <p className="small">
          {plural(ticked.size, 'charge')}, {money(chargesTotal)}. Deposit {money(picked.amount)}.{' '}
          {difference === 0 ? 'They match.'
            : difference < 0 ? `${money(-difference / 100)} less than the charges; split a charge if part of it was yours.`
            : `${money(difference / 100)} more than the charges; the extra won't count as income either.`}
        </p>
      )}
      <div className="panel-actions">
        <button className="primary" disabled={!picked || !ticked.size || busy} onClick={() => picked && onMatch(picked.id, [...ticked])}>Match</button>
        <button onClick={onCancel}>Cancel</button>
      </div>
    </div>
  )
}
