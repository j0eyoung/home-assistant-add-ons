import { useCallback, useEffect, useRef, useState } from 'react'
import { api, dollars, money, monthLabel, thisMonth } from './api.ts'
import type { BudgetRow, Status } from './api.ts'
import { Backups } from './Backups.tsx'
import { CashFlow } from './CashFlow.tsx'
import { CsvImport } from './CsvImport.tsx'
import { DebtPage } from './Debt.tsx'
import { Icon } from './Icon.tsx'
import { PlanPage, PlanStrip } from './Plan.tsx'
import { RecurringPage } from './Recurring.tsx'
import { SafeToSpend } from './SafeToSpend.tsx'
import { Sign } from './Sign.tsx'
import { Transactions } from './Transactions.tsx'
import type { Mode as TxMode } from './Transactions.tsx'
import { UntilPayday } from './UntilPayday.tsx'
import { YearPage } from './Year.tsx'

const TABS = ['Dashboard', 'Transactions', 'Budget', 'Recurring', 'Debt', 'Plan', 'Year', 'Accounts', 'Ask'] as const
type Tab = (typeof TABS)[number]

export function App() {
  const [tab, setTab] = useState<Tab>('Dashboard')
  const [month, setMonth] = useState(thisMonth())
  const [status, setStatus] = useState<Status | null>(null)
  const [error, setError] = useState('')
  const activeTab = useRef<HTMLButtonElement>(null)

  const loadStatus = useCallback(() => {
    api<Status>('status').then(setStatus).catch((e) => setError(e.message))
  }, [])
  useEffect(loadStatus, [loadStatus])
  const setReviewCount = useCallback((n: number) => setStatus((s) => (s ? { ...s, toReview: n } : s)), [])
  const setOwed = useCallback((o: { total: number; count: number }) =>
    setStatus((s) => (s ? { ...s, owedToYou: { ...o, oldest: s.owedToYou?.oldest ?? null } } : s)), [])
  // Which list the Transactions tab opens on when the dashboard sends you there.
  const [txStart, setTxStart] = useState<TxMode | null>(null)
  const openTab = (t: Tab, mode: TxMode | null = null) => {
    setTxStart(mode)
    setTab(t)
  }
  // On a phone the tabs scroll sideways; keep the current one in view. (Block
  // body: newer browsers return a promise from scrollIntoView, which React
  // would take for a cleanup function.)
  useEffect(() => {
    activeTab.current?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }, [tab])

  const toReview = status?.toReview ?? 0
  const issues = status?.health?.issues ?? []
  return (
    <>
      <header className="shell-bar">
        <div className="shell-in">
          <h1><img className="logo" src="./icon.svg" alt="" />Budget</h1>
          <nav aria-label="Sections">
            {TABS.map((t) => (
              <button key={t} ref={t === tab ? activeTab : undefined} className={t === tab ? 'active' : ''} aria-current={t === tab ? 'page' : undefined}
                onClick={() => openTab(t)}>
                {t}{t === 'Transactions' && toReview > 0 && <span className="count" aria-label={`${toReview} to review`}>{toReview}</span>}
              </button>
            ))}
          </nav>
          <input type="month" value={month} aria-label="Month" onChange={(e) => setMonth(e.target.value || thisMonth())} />
        </div>
      </header>
      <div className="app">
      {error && <p className="error" role="alert" onClick={() => setError('')}>{error}</p>}
      {status && !status.connected && tab !== 'Accounts' && (
        <p className="notice">No bank connection yet. Go to Accounts and paste a SimpleFIN setup token.</p>
      )}
      {issues.length > 0 && (
        <details className="notice warn" open={issues.length === 1}>
          <summary><strong><Icon name="warning" size={18} />Needs attention{issues.length > 1 ? `: ${issues.length} things` : ''}</strong><span className="sum-toggle">Details</span></summary>
          <ul>{issues.map((i) => <li key={i}>{i}</li>)}</ul>
        </details>
      )}
      <main>
        {tab === 'Dashboard' && (
          <Dashboard month={month} status={status} onError={setError} onOpenPlan={() => openTab('Plan')}
            onOpenReview={() => openTab('Transactions', 'review')} onOpenBudget={() => openTab('Budget')}
            onOpenOwed={() => openTab('Transactions', 'owed')} />
        )}
        {tab === 'Transactions' && (
          <Transactions month={month} toReview={toReview} owedCount={status?.owedToYou?.count ?? 0}
            startMode={txStart ?? (toReview > 0 ? 'review' : 'all')} onError={setError} onReviewCount={setReviewCount}
            onOwed={setOwed} onStatus={loadStatus} />
        )}
        {tab === 'Budget' && <Budget month={month} onError={setError} />}
        {tab === 'Recurring' && <RecurringPage onError={setError} />}
        {tab === 'Debt' && <DebtPage onError={setError} />}
        {tab === 'Plan' && <PlanPage status={status} onError={setError} />}
        {tab === 'Year' && <YearPage onError={setError} />}
        {tab === 'Accounts' && <Accounts status={status} onError={setError} onStatus={loadStatus} />}
        {tab === 'Ask' && <Ask status={status} onError={setError} />}
      </main>
      </div>
    </>
  )
}

type PageProps = { onError: (message: string) => void }
type Tracked = { id: number; name: string; total: number; since: string; thisMonth: number }

function Dashboard({ month, status, onError, onOpenPlan, onOpenReview, onOpenBudget, onOpenOwed }: PageProps & {
  month: string
  status: Status | null
  onOpenPlan: () => void
  onOpenReview: () => void
  onOpenBudget: () => void
  onOpenOwed: () => void
}) {
  const owedToYou = status?.owedToYou
  // null while the month loads, so nothing shows as $0 in the meantime.
  const [rows, setRows] = useState<BudgetRow[] | null>(null)
  const [worth, setWorth] = useState<{ date: string; assets: number; debts: number }[]>([])
  const [tracked, setTracked] = useState<Tracked[]>([])
  const [insight, setInsight] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setRows(null)
    api<BudgetRow[]>(`budget?month=${month}`).then(setRows).catch((e) => onError(e.message))
    api(`insights?month=${month}`).then((r) => setInsight(r?.content ?? null)).catch((e) => onError(e.message))
    api<Tracked[]>(`tracked?month=${month}`).then(setTracked).catch((e) => onError(e.message))
    api('networth').then(setWorth).catch((e) => onError(e.message))
  }, [month, onError])

  const all = rows ?? []
  const spent = all.filter((r) => r.kind === 'expense').reduce((sum, r) => sum + r.spent, 0)
  const income = -all.filter((r) => r.kind === 'income').reduce((sum, r) => sum + r.spent, 0) || 0
  const saved = -all.filter((r) => r.kind === 'savings').reduce((sum, r) => sum + r.spent, 0) || 0
  const shown = (n: number) => (rows ? dollars(n) : '…')
  const latest = worth.at(-1)

  const generate = async () => {
    setBusy(true)
    try {
      setInsight((await api('insights', 'POST', { month })).content)
    } catch (e: any) {
      onError(e.message)
    }
    setBusy(false)
  }

  const toReview = status?.toReview ?? 0
  const current = month === thisMonth()
  const side = current || toReview > 0

  return (
    <>
      <div className="dash" style={side ? undefined : { gridTemplateColumns: 'minmax(0, 1fr)' }}>
        <Sign month={month} rows={rows} onOpenBudget={onOpenBudget} />
        {side && (
          <div className="dash-side">
            {current && <SafeToSpend onError={onError} onOpenPlan={onOpenPlan} />}
            {current && <UntilPayday onError={onError} />}
            {toReview > 0 && (
              <button className="service" onClick={onOpenReview}>
                <span>
                  <span className="svc-title">To review</span>
                  <strong>{toReview} new</strong>
                  <span className="svc-small">{toReview === 1 ? 'charge whose category is a guess' : 'charges whose category is a guess'}</span>
                </span>
                <span className="go">Review <Icon name="arrow-right" size={18} /></span>
              </button>
            )}
            {current && <Today status={status} onError={onError} />}
            {current && <PlanStrip onError={onError} onOpen={onOpenPlan} />}
          </div>
        )}
      </div>
      <section>
        <h2>{monthLabel(month)} in figures</h2>
        <dl className="figures">
          <div><dt>Income</dt><dd>{shown(income)}<small>{income - spent >= 0 ? '+' : '−'}{dollars(Math.abs(income - spent))} after spending</small></dd></div>
          <div><dt>Pre-tax savings</dt><dd>{shown(saved)}<small>401k, HSA, investments</small></dd></div>
          <div><dt>Net worth</dt><dd>{latest ? dollars(latest.assets - latest.debts) : '—'}<small>{latest ? `${dollars(latest.debts)} owed` : 'connect an account'}</small></dd></div>
          {owedToYou && owedToYou.count > 0 && (
            <div>
              <dt>Owed to you</dt>
              <dd>{dollars(owedToYou.total)}<small>
                <button className="link left quiet" onClick={onOpenOwed}>{owedToYou.count} {owedToYou.count === 1 ? 'charge' : 'charges'} to be paid back</button>
              </small></dd>
            </div>
          )}
          {tracked.map((t) => {
            const months = Math.max(1, monthsBetween(t.since.slice(0, 7), thisMonth()) + 1)
            return (
              <div key={t.id}>
                <dt>{t.name} to date</dt>
                <dd>{dollars(t.total)}<small>{dollars(t.thisMonth)} this month · {dollars(t.total / months)}/mo since {monthLabel(t.since.slice(0, 7))}</small></dd>
              </div>
            )
          })}
        </dl>
      </section>
      <CashFlow onError={onError} />
      {worth.length > 1 && (
        <section>
          <h2>Net worth over time</h2>
          <Sparkline values={worth.map((w) => w.assets - w.debts)} />
        </section>
      )}
      <section>
        <h2>Monthly insights</h2>
        {insight ? <p className="insight">{insight}</p> : <p className="muted">No review generated for this month yet.</p>}
        <button onClick={generate} disabled={busy}>
          {busy ? 'Generating…' : insight ? 'Regenerate' : 'Generate review'}
        </button>
        {status && !status.aiConfigured && <span className="muted"> Connect Claude in the Accounts tab first.</span>}
      </section>
    </>
  )
}

function monthsBetween(from: string, to: string) {
  const [fy, fm] = from.split('-').map(Number)
  const [ty, tm] = to.split('-').map(Number)
  return (ty - fy) * 12 + (tm - fm)
}

// Today's "anything to flag?" check. Written once a day after the sync; the
// button regenerates it on demand.
function Today({ status, onError }: PageProps & { status: Status | null }) {
  const [text, setText] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    api('briefing').then((r) => setText(r.briefing?.text ?? null)).catch((e) => onError(e.message))
  }, [onError])
  const refresh = async () => {
    setBusy(true)
    try {
      setText((await api('briefing', 'POST')).briefing.text)
    } catch (e: any) {
      onError(e.message)
    }
    setBusy(false)
  }
  if (!text && !status?.aiConfigured) return null
  return (
    <section className="today">
      <div className="chart-head">
        <h2>Today</h2>
        <button onClick={refresh} disabled={busy}>{busy ? 'Checking…' : text ? 'Check again' : 'Check today'}</button>
      </div>
      {text ? <p className="insight">{text}</p> : <p className="muted">Not checked yet today.</p>}
    </section>
  )
}

function Sparkline({ values }: { values: number[] }) {
  const min = Math.min(...values)
  const range = Math.max(...values) - min || 1
  const points = values.map((v, i) => `${(i / (values.length - 1)) * 100},${38 - ((v - min) / range) * 36}`).join(' ')
  return (
    <svg className="sparkline" viewBox="0 0 100 40" preserveAspectRatio="none">
      <polyline points={points} fill="none" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

function Budget({ month, onError }: PageProps & { month: string }) {
  const [rows, setRows] = useState<BudgetRow[]>([])
  const [message, setMessage] = useState('')
  const load = useCallback(() => {
    api<BudgetRow[]>(`budget?month=${month}`).then(setRows).catch((e) => onError(e.message))
  }, [month, onError])
  useEffect(load, [load])

  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn()
      load()
    } catch (e: any) {
      onError(e.message)
    }
  }
  const save = (id: number, value: string) => run(() => api(`budget/${id}`, 'PUT', { amount: Number(value) || 0 }))
  const track = (id: number, on: boolean) => run(() => api(`categories/${id}`, 'PATCH', { track: on }))
  const fill = () => {
    if (!window.confirm('Set a target for every category that has none, from its 3-month average rounded up to the next $10? Existing targets stay as they are.')) return
    run(async () => {
      const r = await api('budget/fill', 'POST', { month })
      setMessage(r.filled ? `Filled ${r.filled} targets. Trim any that look high.` : 'Nothing to fill: every category with spending already has a target.')
    })
  }

  const addCategory = async () => {
    const name = window.prompt('New category name')
    if (!name?.trim()) return
    const kind = window.prompt('Kind: expense, income, savings or transfer', 'expense') || 'expense'
    run(() => api('categories', 'POST', { name, kind }))
  }

  const expenses = rows.filter((r) => r.kind === 'expense')
  return (
    <>
    <section>
      <div className="toolbar">
        <span className="muted grow">Monthly targets apply to every month. Leave blank for no target.</span>
        <button onClick={fill}>Fill empty targets from 3-month average</button>
        <button onClick={addCategory}>Add category</button>
      </div>
      {message && <p className="muted">{message}</p>}
      <div className="table-wrap">
        <table className="budget-table">
          <thead>
            <tr>
              <th>Category</th><th className="num">Monthly target</th><th className="num opt">3-mo avg</th><th className="num opt">Last month</th>
              <th className="num">Spent</th><th className="num">Remaining</th><th className="track" title="Show a running total on the dashboard">On dashboard</th>
            </tr>
          </thead>
          <tbody>
            {expenses.map((r) => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td className="num">
                  <input className="amount" type="number" min="0" step="10" defaultValue={r.budget || ''} key={r.budget}
                    placeholder={r.avg3 > 0 ? String(Math.ceil(r.avg3 / 10) * 10) : ''}
                    onBlur={(e) => Number(e.target.value || 0) !== r.budget && save(r.id, e.target.value)} />
                </td>
                <td className="num opt muted">{r.avg3 ? dollars(r.avg3) : '—'}</td>
                <td className="num opt muted">{r.prev ? dollars(r.prev) : '—'}</td>
                <td className="num">{money(r.spent)}</td>
                <td className={`num ${r.budget && r.spent > r.budget ? 'over' : ''}`}>{r.budget ? money(r.budget - r.spent) : '—'}</td>
                <td className="track"><input type="checkbox" checked={Boolean(r.track)} onChange={(e) => track(r.id, e.target.checked)} /></td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td>Total</td>
              <td className="num">{money(expenses.reduce((s, r) => s + r.budget, 0))}</td>
              <td className="num opt">{dollars(expenses.reduce((s, r) => s + r.avg3, 0))}</td>
              <td className="num opt">{dollars(expenses.reduce((s, r) => s + r.prev, 0))}</td>
              <td className="num">{money(expenses.reduce((s, r) => s + r.spent, 0))}</td>
              <td />
              <td className="track" />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>
    <Rules onError={onError} />
    </>
  )
}

// Merchant rules: one merchant always lands in one category. Delete a rule for
// merchants like Costco where each trip can be groceries, pharmacy or gas.
function Rules({ onError }: PageProps) {
  const [rules, setRules] = useState<{ pattern: string; category: string }[]>([])
  const load = useCallback(() => {
    api('rules').then(setRules).catch((e) => onError(e.message))
  }, [onError])
  useEffect(load, [load])
  const remove = async (pattern: string) => {
    try {
      await api(`rules/${encodeURIComponent(pattern)}`, 'DELETE')
      load()
    } catch (e: any) {
      onError(e.message)
    }
  }
  return (
    <section>
      <h2>Merchant rules</h2>
      <p className="muted">Made when you answer OK to "always put this merchant in this category". Already-labelled transactions keep their category when a rule is deleted; new ones go back to the AI.</p>
      {!rules.length && <p className="muted">No rules yet.</p>}
      {rules.map((r) => (
        <div className="account" key={r.pattern}>
          <div>{r.pattern} <span className="muted"><Icon name="arrow-right" size={14} /> {r.category}</span></div>
          <button className="link" onClick={() => remove(r.pattern)}>Delete</button>
        </div>
      ))}
    </section>
  )
}

const ACCOUNT_TYPES = ['depository', 'credit', 'loan', 'investment', 'other']

function Accounts({ status, onError, onStatus }: PageProps & { status: Status | null; onStatus: () => void }) {
  const [accounts, setAccounts] = useState<any[]>([])
  const [token, setToken] = useState('')
  const [manual, setManual] = useState({ name: '', org_name: '', type: 'loan', balance: '' })
  const [busy, setBusy] = useState('')
  const load = useCallback(() => {
    api('accounts').then(setAccounts).catch((e) => onError(e.message))
  }, [onError])
  useEffect(load, [load])

  const run = async (label: string, fn: () => Promise<any>) => {
    setBusy(label)
    try {
      const r = await fn()
      if (r?.errors?.length) onError(r.errors.join(' | '))
    } catch (e: any) {
      onError(e.message)
    }
    setBusy('')
    load()
    onStatus()
  }

  const connect = () => run('connect', async () => {
    const r = await api('simplefin/connect', 'POST', { setup_token: token })
    setToken('')
    return r
  })
  const sync = () => run('sync', () => api('sync', 'POST'))
  const disconnect = () => {
    if (window.confirm('Disconnect SimpleFIN? Synced accounts and transactions stay until you delete them.')) run('disconnect', () => api('simplefin/disconnect', 'POST'))
  }
  const addManual = () => run('manual', async () => {
    await api('accounts', 'POST', manual)
    setManual({ name: '', org_name: '', type: 'loan', balance: '' })
  })
  const setType = (a: any, type: string) => run('type', () => api(`accounts/${encodeURIComponent(a.id)}`, 'PATCH', { type }))
  const setBalance = (a: any, balance: string) => run('balance', () => api(`accounts/${encodeURIComponent(a.id)}`, 'PATCH', { balance }))
  const remove = (a: any) => {
    const hint = a.replaced_by || a.source === 'simplefin' ? '\n\nIf this is the old copy of a reconnected account, use Merge instead: it keeps the history.' : ''
    if (window.confirm(`Delete ${a.name} and its ${a.transaction_count} transactions from this app?${hint}`)) run('delete', () => api(`accounts/${encodeURIComponent(a.id)}`, 'DELETE'))
  }
  // Merging an old copy of an account into its replacement (see server/merge.ts).
  const [merging, setMerging] = useState<{ from: any; into: string } | null>(null)
  const [merged, setMerged] = useState('')
  const merge = (from: any, into: string) => run('merge', async () => {
    const r = await api(`accounts/${encodeURIComponent(from.id)}/merge`, 'POST', { into })
    setMerging(null)
    setMerged(`Merged ${from.name}: ${r.moved} older transactions moved over, ${r.matched} the new account already had kept once${r.backfilled ? `, ${r.backfilled} more fetched from SimpleFIN` : ''}.${r.warning ? ` ${r.warning}` : ''}`)
  })
  const accountLabel = (id: string) => {
    const a = accounts.find((x) => x.id === id)
    return a ? `${a.org_name ? `${a.org_name} ` : ''}${a.name} (as of ${a.balance_date})` : id
  }
  const stale = (a: any) => a.source === 'simplefin' && a.balance_date && a.balance_date < new Date(Date.now() - 3 * 86400000).toISOString().slice(0, 10)

  const groups = Object.entries(
    accounts.reduce<Record<string, any[]>>((g, a) => ((g[a.org_name || (a.source === 'manual' ? 'Manual' : 'Other')] ??= []).push(a), g), {}),
  )

  return (
    <>
      <section>
        <h2>SimpleFIN</h2>
        {status?.connected ? (
          <div className="toolbar">
            <span>Connected{status.lastSync ? `, last sync ${new Date(status.lastSync).toLocaleString()}` : ''}</span>
            <button onClick={sync} disabled={Boolean(busy)}>{busy === 'sync' ? 'Syncing…' : 'Sync now'}</button>
            <button className="link" onClick={disconnect} disabled={Boolean(busy)}>Disconnect</button>
          </div>
        ) : (
          <div className="toolbar">
            <input className="grow" placeholder="Paste a setup token from bridge.simplefin.org" value={token} onChange={(e) => setToken(e.target.value)} />
            <button onClick={connect} disabled={!token.trim() || Boolean(busy)}>{busy === 'connect' ? 'Connecting…' : 'Connect'}</button>
          </div>
        )}
        <p className="muted">
          SimpleFIN allows about 24 requests a day; the app syncs once a day on its own.
          {status?.health?.lastBackup ? ` Last backup ${new Date(status.health.lastBackup).toLocaleString()}.` : ''}
        </p>
      </section>

      <CsvImport accounts={accounts} onError={onError} onDone={load} />

      {merged && <p className="toast" role="status" onClick={() => setMerged('')}>{merged}</p>}

      {groups.map(([org, list]) => (
        <section key={org}>
          <h2>{org}</h2>
          {list.map((a) => (
            <div className="account-block" key={a.id}>
              <div className="account">
                <div>
                  <div>{a.name}</div>
                  <div className="muted">
                    <select value={a.type} onChange={(e) => setType(a, e.target.value)}>
                      {ACCOUNT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                    {' '}as of {a.balance_date} · {a.transaction_count} transactions
                    {' '}<button className="link" onClick={() => remove(a)}>Delete</button>
                  </div>
                </div>
                {a.source === 'manual' ? (
                  <input className="amount" type="number" step="0.01" defaultValue={a.balance} key={a.balance}
                    onBlur={(e) => Number(e.target.value) !== a.balance && setBalance(a, e.target.value)} />
                ) : (
                  <div className={`num ${a.balance < 0 ? 'over' : ''}`}>{money(a.balance)}</div>
                )}
              </div>
              {stale(a) && merging?.from.id !== a.id && (
                <div className="panel merge-hint">
                  <span>
                    {a.replaced_by
                      ? <>Stopped updating. <strong>{accountLabel(a.replaced_by)}</strong> looks like the same account, reconnected at SimpleFIN.</>
                      : 'Stopped updating. If the bank was reconnected and this account now shows twice, merge this old copy into the new one.'}
                  </span>
                  <span className="panel-actions">
                    {a.replaced_by ? (
                      <button className="primary" onClick={() => setMerging({ from: a, into: a.replaced_by })}>Merge into it…</button>
                    ) : (
                      <select value="" onChange={(e) => e.target.value && setMerging({ from: a, into: e.target.value })}>
                        <option value="">Merge into…</option>
                        {accounts.filter((x) => x.id !== a.id).map((x) => <option key={x.id} value={x.id}>{accountLabel(x.id)}</option>)}
                      </select>
                    )}
                  </span>
                </div>
              )}
              {merging && merging.from.id === a.id && (
                <div className="panel merge-hint">
                  <span>
                    Merge this account ({a.transaction_count} transactions) into <strong>{accountLabel(merging.into)}</strong>? Its transactions, balance history and
                    debt settings move over; any the new account already has are kept once, with your categories, splits and notes. Then this copy disappears.
                    A copy of everything is saved first as before-merge.db in the backups folder.
                  </span>
                  <span className="panel-actions">
                    <button className="primary" onClick={() => merge(a, merging.into)} disabled={Boolean(busy)}>{busy === 'merge' ? 'Merging…' : 'Merge'}</button>
                    <button onClick={() => setMerging(null)} disabled={busy === 'merge'}>Cancel</button>
                  </span>
                </div>
              )}
            </div>
          ))}
        </section>
      ))}

      <ClaudeConnect onError={onError} onStatus={onStatus} />

      <Backups onError={onError} onDone={() => { load(); onStatus() }} />

      <section>
        <h2>Add a manual account</h2>
        <p className="muted">For anything SimpleFIN can't reach (e.g. a loan servicer). Enter balances owed as negative numbers.</p>
        <div className="toolbar">
          <input placeholder="Account name" value={manual.name} onChange={(e) => setManual({ ...manual, name: e.target.value })} />
          <input placeholder="Institution" value={manual.org_name} onChange={(e) => setManual({ ...manual, org_name: e.target.value })} />
          <select value={manual.type} onChange={(e) => setManual({ ...manual, type: e.target.value })}>
            {ACCOUNT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <input className="amount" type="number" step="0.01" placeholder="Balance" value={manual.balance} onChange={(e) => setManual({ ...manual, balance: e.target.value })} />
          <button onClick={addManual} disabled={!manual.name.trim() || Boolean(busy)}>Add</button>
        </div>
      </section>
    </>
  )
}


function ClaudeConnect({ onError, onStatus }: PageProps & { onStatus: () => void }) {
  const [state, setState] = useState<any>(null)
  const [code, setCode] = useState('')
  const load = useCallback(() => {
    api('claude/status').then(setState).catch((e) => onError(e.message))
  }, [onError])
  useEffect(load, [load])
  // While a sign-in is running, poll for the link and the final result.
  useEffect(() => {
    if (!state?.login?.running) return
    const t = setInterval(load, 2000)
    return () => clearInterval(t)
  }, [state?.login?.running, load])

  const call = async (path: string, body?: unknown) => {
    try {
      await api(path, 'POST', body)
      load()
      onStatus()
    } catch (e: any) {
      onError(e.message)
    }
  }

  const signedIn = Boolean(state?.loggedIn && !state?.expired)
  // The app-level status (which gates the AI buttons) must follow the sign-in state.
  useEffect(() => {
    if (state) onStatus()
  }, [signedIn, state, onStatus])
  return (
    <section>
      <h2>Claude</h2>
      <p className="muted">Categorization, questions, daily checks and monthly reviews run through Claude Code on your subscription. Nothing is sent anywhere else.</p>
      {signedIn ? (
        <div className="toolbar">
          <span>Signed in{state.authMethod ? ` (${state.authMethod})` : ''}</span>
          <button className="link" onClick={() => call('claude/logout')}>Sign out</button>
        </div>
      ) : state?.login?.running ? (
        <div>
          {state.login.url ? (
            <p>Open <a href={state.login.url} target="_blank" rel="noreferrer">this sign-in link</a>, approve, then paste the code here:</p>
          ) : (
            <p className="muted">Starting sign-in…</p>
          )}
          <div className="toolbar">
            <input className="grow" placeholder="Paste the code" value={code} onChange={(e) => setCode(e.target.value)} />
            <button onClick={() => { call('claude/login/code', { code }); setCode('') }} disabled={!code.trim()}>Submit</button>
          </div>
          {state.login.message && <p className="muted">{state.login.message}</p>}
        </div>
      ) : (
        <div className="toolbar">
          <button onClick={() => call('claude/login')}>Connect Claude</button>
          {state?.hasToken && <span className="muted">Using the token from the add-on options.</span>}
          {state?.expired && <span className="muted">Previous sign-in expired.</span>}
          {state?.login?.message && !state?.login?.running && <span className="muted">{state.login.message}</span>}
        </div>
      )}
    </section>
  )
}

function Ask({ status, onError }: PageProps & { status: Status | null }) {
  const [question, setQuestion] = useState('')
  const [log, setLog] = useState<{ question: string; answer: string; sql: string }[]>([])
  const [busy, setBusy] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return
    setBusy(true)
    try {
      const r = await api('ask', 'POST', { question })
      setLog((l) => [{ question, answer: r.answer, sql: r.sql }, ...l])
      setQuestion('')
    } catch (err: any) {
      onError(err.message)
    }
    setBusy(false)
  }

  return (
    <section>
      {status && !status.aiConfigured && <p className="notice">Connect Claude in the Accounts tab to use this.</p>}
      <form className="toolbar" onSubmit={submit}>
        <input className="grow" placeholder="How much did I spend on dining last month?" value={question} onChange={(e) => setQuestion(e.target.value)} />
        <button disabled={busy}>{busy ? 'Thinking…' : 'Ask'}</button>
      </form>
      {log.map((entry, i) => (
        <div className="qa" key={log.length - i}>
          <div className="question">{entry.question}</div>
          <p className="insight">{entry.answer}</p>
          <details>
            <summary className="muted">Query used</summary>
            <code>{entry.sql}</code>
          </details>
        </div>
      ))}
    </section>
  )
}
