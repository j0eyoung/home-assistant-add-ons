import { useEffect, useState } from 'react'
import { api, dollars, money, shortDate } from './api.ts'

type Forecast = {
  account: { id: string; name: string }
  accounts: { id: string; name: string }[]
  balance: number
  payday: string | null
  paydaySource: 'plan' | 'deposits' | null
  until: string
  items: { date: string; label: string; amount: number; kind: 'bill' | 'card' | 'everyday' }[]
  everydayPerDay: number
  low: { amount: number; date: string }
  threshold: number
  warning: string | null
  notes: string[]
}

// Dashboard: where checking goes between today and the next paycheck. Blue
// like the other information panels; construction orange when it dips below
// the amount the user wants to keep there.
export function UntilPayday({ onError }: { onError: (m: string) => void }) {
  const [f, setF] = useState<Forecast | null>(null)
  const [threshold, setThreshold] = useState('')
  useEffect(() => {
    api<Forecast | null>('forecast').then(setF).catch((e) => onError(e.message))
  }, [onError])
  useEffect(() => {
    if (f) setThreshold(String(f.threshold))
  }, [f])
  if (!f) return null

  const save = async (body: { accountId?: string; threshold?: string }) => {
    try {
      setF(await api<Forecast | null>('forecast', 'PUT', body))
    } catch (e: any) {
      onError(e.message)
    }
  }
  const low = f.warning != null
  const lines = f.items
  const payments = lines.filter((i) => i.kind !== 'everyday')
  return (
    <section className={`service ${low ? 'caution-panel' : ''}`}>
      <h2>Until payday{f.payday ? `, ${shortDate(f.payday)}` : ''}</h2>
      <div className="figure">
        {f.low.amount < 0 ? '−' : ''}{dollars(Math.abs(f.low.amount))}
        <span>lowest, on {shortDate(f.low.date)}</span>
      </div>
      <p className="small">
        {f.account.name} has {money(f.balance)} now.{' '}
        {payments.length
          ? `${payments.length} ${payments.length === 1 ? 'bill or payment' : 'bills and payments'} (${money(payments.reduce((s, i) => s + i.amount, 0))}) before payday.`
          : 'No bills before payday.'}
      </p>
      {low && <p className="small strong-line">Below the {dollars(f.threshold)} you want to keep there.</p>}
      {f.notes.map((n) => <p className="small" key={n}>{n}</p>)}
      <details>
        <summary>What comes out</summary>
        {lines.length ? lines.map((i, n) => (
          <div className="line" key={n}>
            <span>{i.label}<span className="small"> · {i.kind === 'everyday' ? `until ${shortDate(i.date)}` : shortDate(i.date)}</span></span>
            <span>{money(i.amount)}</span>
          </div>
        )) : <p className="small">Nothing expected.</p>}
        <p className="small">
          Bills are the regular ones charged to this account; card and loan payments come from their due dates in the Debt tab
          {f.paydaySource === 'deposits' ? '; payday is worked out from your paychecks (set it in Plan to be exact)' : ''}.
        </p>
      </details>
      <details>
        <summary>Settings</summary>
        <div className="toolbar tight">
          <label className="small">Account
            <select value={f.account.id} onChange={(e) => save({ accountId: e.target.value })}>
              {f.accounts.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </label>
          <label className="small">Warn me below
            <input className="amount" type="number" min="0" step="50" value={threshold} onChange={(e) => setThreshold(e.target.value)}
              onBlur={() => Number(threshold) !== f.threshold && save({ threshold })} />
          </label>
        </div>
      </details>
    </section>
  )
}
