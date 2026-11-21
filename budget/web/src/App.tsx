import { useCallback, useEffect, useRef, useState } from 'react'
import { addMonths, api, dollars, money, monthLabel, thisMonth } from './api.ts'
import type { BudgetRow, Status } from './api.ts'
import { Backups } from './Backups.tsx'
import { Card } from './Card.tsx'
import { CashFlow } from './CashFlow.tsx'
import { CsvImport } from './CsvImport.tsx'
import { DebtPage } from './Debt.tsx'
import { PlanPage, PlanStrip } from './Plan.tsx'
import { RecurringPage } from './Recurring.tsx'
import { SafeToSpend } from './SafeToSpend.tsx'
import { Transactions } from './Transactions.tsx'

const TABS = ['Dashboard', 'Transactions', 'Budget', 'Recurring', 'Debt', 'Plan', 'Accounts', 'Ask'] as const
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
  // On a phone the tabs scroll sideways; keep the current one in view. (Block
  // body: newer browsers return a promise from scrollIntoView, which React
  // would take for a cleanup function.)
  useEffect(() => {
    activeTab.current?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }, [tab])

  const toReview = status?.toReview ?? 0
  const issues = status?.health?.issues ?? []
  return (
    <div className="app">
      <header>
        <h1><img className="logo" src="./icon.svg" alt="" />Budget</h1>
        <nav>
          {TABS.map((t) => (
            <button key={t} ref={t === tab ? activeTab : undefined} className={t === tab ? 'active' : ''} onClick={() => setTab(t)}>
              {t}{t === 'Transactions' && toReview > 0 && <span className="count" aria-label={`${toReview} to review`}>{toReview}</span>}
            </button>
          ))}
        </nav>
        <input type="month" value={month} aria-label="Month" onChange={(e) => setMonth(e.target.value || thisMonth())} />
      </header>
      {error && <p className="error" onClick={() => setError('')}>{error}</p>}
      {status && !status.connected && tab !== 'Accounts' && (
        <p className="notice">No bank connection yet. Go to Accounts and paste a SimpleFIN setup token.</p>
      )}
      {issues.length > 0 && (
        <div className="notice warn">
          <strong>⚠ Needs attention</strong>
          <ul>{issues.map((i) => <li key={i}>{i}</li>)}</ul>
        </div>
      )}
      <main>
        {tab === 'Dashboard' && (
          <Dashboard month={month} status={status} onError={setError} onOpenPlan={() => setTab('Plan')} onOpenReview={() => setTab('Transactions')} />
        )}
        {tab === 'Transactions' && (
          <Transactions month={month} toReview={toReview} startInReview={toReview > 0} onError={setError} onReviewCount={setReviewCount} />
        )}
        {tab === 'Budget' && <Budget month={month} onError={setError} />}
        {tab === 'Recurring' && <RecurringPage onError={setError} />}
        {tab === 'Debt' && <DebtPage onError={setError} />}
        {tab === 'Plan' && <PlanPage status={status} onError={setError} />}
        {tab === 'Accounts' && <Accounts status={status} onError={setError} onStatus={loadStatus} />}
        {tab === 'Ask' && <Ask status={status} onError={setError} />}
      </main>
    </div>
  )
}

type PageProps = { onError: (message: string) => void }
type Tracked = { id: number; name: string; total: number; since: string; thisMonth: number }

function Dashboard({ month, status, onError, onOpenPlan, onOpenReview }: PageProps & {
  month: string
  status: Status | null
  onOpenPlan: () => void
  onOpenReview: () => void
}) {
  const [rows, setRows] = useState<BudgetRow[]>([])
  const [worth, setWorth] = useState<{ date: string; assets: number; debts: number }[]>([])
  const [tracked, setTracked] = useState<Tracked[]>([])
  const [insight, setInsight] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [allCategories, setAllCategories] = useState(false)

  useEffect(() => {
    api<BudgetRow[]>(`budget?month=${month}`).then(setRows).catch((e) => onError(e.message))
    api(`insights?month=${month}`).then((r) => setInsight(r?.content ?? null)).catch((e) => onError(e.message))
    api<Tracked[]>(`tracked?month=${month}`).then(setTracked).catch((e) => onError(e.message))
    api('networth').then(setWorth).catch((e) => onError(e.message))
  }, [month, onError])

  const expenses = rows.filter((r) => r.kind === 'expense')
  const spent = expenses.reduce((sum, r) => sum + r.spent, 0)
  const budgeted = expenses.reduce((sum, r) => sum + r.budget, 0)
  const prevSpent = expenses.reduce((sum, r) => sum + r.prev, 0)
  const income = -rows.filter((r) => r.kind === 'income').reduce((sum, r) => sum + r.spent, 0) || 0
  const saved = -rows.filter((r) => r.kind === 'savings').reduce((sum, r) => sum + r.spent, 0) || 0
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
  // Categories with spending this month first; budgeted or last-month-only ones behind "Show".
  const withSpending = expenses.filter((r) => r.spent > 0).sort((a, b) => b.spent - a.spent)
  const quiet = expenses.filter((r) => r.spent <= 0 && (r.budget > 0 || r.prev > 0)).sort((a, b) => b.budget + b.prev - (a.budget + a.prev))

  return (
    <>
      {current && <SafeToSpend onError={onError} onOpenPlan={onOpenPlan} />}
      {toReview > 0 && (
        <button className="nudge" onClick={onOpenReview}>
          <span>
            <strong>{toReview} {toReview === 1 ? 'charge' : 'charges'} to check</strong>
            <span className="muted"> · their categories are a guess</span>
          </span>
          <span className="nudge-go">Review →</span>
        </button>
      )}
      {current && <Today status={status} onError={onError} />}
      {current && <PlanStrip onError={onError} onOpen={onOpenPlan} />}
      <div className="cards">
        <Card label="Spent" value={dollars(spent)} sub={`${budgeted ? `of ${dollars(budgeted)} budgeted · ` : ''}${dollars(prevSpent)} last month`} />
        <Card label="Income" value={dollars(income)} sub={`${dollars(income - spent)} net`} />
        <Card label="Pre-tax savings" value={dollars(saved)} sub="401k, HSA, investment activity" />
        <Card label="Net worth" value={latest ? dollars(latest.assets - latest.debts) : '—'} sub={latest ? `${dollars(latest.debts)} owed` : 'connect an account'} />
        {tracked.map((t) => {
          const months = Math.max(1, monthsBetween(t.since.slice(0, 7), thisMonth()) + 1)
          return (
            <Card key={t.id} label={`${t.name} (to date)`} value={dollars(t.total)}
              sub={`${dollars(t.thisMonth)} in ${monthLabel(month, false)} · ${dollars(t.total / months)}/mo since ${monthLabel(t.since.slice(0, 7))}`} />
          )
        })}
      </div>
      <section>
        <h2>Spending by category <span className="muted">vs {monthLabel(addMonths(month, -1), false)}</span></h2>
        {withSpending.map((r) => <CategoryBar key={r.id} row={r} />)}
        {allCategories && quiet.map((r) => <CategoryBar key={r.id} row={r} />)}
        {quiet.length > 0 && (
          <button className="link left" onClick={() => setAllCategories(!allCategories)}>
            {allCategories ? 'Hide categories with no spending' : `Show ${quiet.length} with no spending yet`}
          </button>
        )}
        {!withSpending.length && <p className="muted">No spending recorded for this month.</p>}
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

function CategoryBar({ row }: { row: BudgetRow }) {
  const pct = row.budget ? Math.min(100, (row.spent / row.budget) * 100) : 100
  const over = row.budget > 0 && row.spent > row.budget
  const delta = row.spent - row.prev
  return (
    <div className="bar-row">
      <div className="bar-label">
        <span>
          {row.name}
          {row.prev > 0 || row.spent > 0 ? (
            <span className={`delta ${delta > 0.5 ? 'up' : delta < -0.5 ? 'down' : ''}`}>
              {delta > 0.5 ? '▲' : delta < -0.5 ? '▼' : '='} {dollars(row.prev)} last month
            </span>
          ) : null}
        </span>
        <span className={over ? 'over' : ''}>
          {money(row.spent)}{row.budget ? ` / ${money(row.budget)}` : ''}
        </span>
      </div>
      <div className="bar">
        <div className={`bar-fill ${over ? 'over-fill' : row.budget ? '' : 'unbudgeted'}`} style={{ width: `${Math.max(0, pct)}%` }} />
      </div>
    </div>
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
          <div>{r.pattern} <span className="muted">→ {r.category}</span></div>
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
    if (window.confirm(`Delete ${a.name} and its transactions from this app?`)) run('delete', () => api(`accounts/${encodeURIComponent(a.id)}`, 'DELETE'))
  }

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

      {groups.map(([org, list]) => (
        <section key={org}>
          <h2>{org}</h2>
          {list.map((a) => (
            <div className="account" key={a.id}>
              <div>
                <div>{a.name}</div>
                <div className="muted">
                  <select value={a.type} onChange={(e) => setType(a, e.target.value)}>
                    {ACCOUNT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                  {' '}as of {a.balance_date}
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
