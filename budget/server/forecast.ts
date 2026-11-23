import { nextPayday } from '../shared/plan-math.ts'
import { db, meta } from './db.ts'
import { cardsDue } from './debts.ts'
import { loadPlan } from './plan.ts'
import { today } from './queries.ts'
import { CADENCES, detectRecurring, normalize } from './recurring.ts'

// "Until payday": where the checking account's balance goes between today and
// the next paycheck, and whether it dips below the amount the user wants to
// keep there. Bills come from recurring detection (the ones charged to this
// account), card and loan payments from their due dates, and everyday spending
// from this account's own pace over the last 60 days.

export type ForecastItem = { date: string; label: string; amount: number; kind: 'bill' | 'card' | 'everyday' }
export type Forecast = {
  account: { id: string; name: string }
  accounts: { id: string; name: string }[] // checking and savings accounts to pick from
  balance: number
  payday: string | null
  paydaySource: 'plan' | 'deposits' | null
  until: string // last day forecast (the day before payday)
  items: ForecastItem[]
  everydayPerDay: number
  low: { amount: number; date: string }
  threshold: number
  warning: string | null
  notes: string[]
}

export const DEFAULT_LOW = 200
const EVERYDAY_DAYS = 60
// Without a payday, look this far ahead.
const FALLBACK_DAYS = 14
// A bill this many days late (not charged yet, not stopped) still counts, as due today.
const LATE_DAYS = 3

const DAY = 86400000
const dayNum = (date: string) => Math.round(Date.parse(`${date}T00:00:00Z`) / DAY)
const fromDayNum = (n: number) => new Date(n * DAY).toISOString().slice(0, 10)
const round = (n: number) => Math.round(n * 100) / 100
const usd = (n: number) => `${n < 0 ? '-' : ''}$${Math.round(Math.abs(n)).toLocaleString('en-US')}`
const shortDate = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })

export function forecastSettings() {
  const threshold = Number(meta.get('forecast_low'))
  return { accountId: meta.get('forecast_account'), threshold: meta.get('forecast_low') != null && Number.isFinite(threshold) ? threshold : DEFAULT_LOW }
}

export function saveForecastSettings(input: { accountId?: unknown; threshold?: unknown }) {
  if ('accountId' in input) {
    const id = typeof input.accountId === 'string' ? input.accountId : ''
    if (id && db.prepare(`SELECT 1 FROM accounts WHERE id = ? AND type = 'depository'`).get(id)) meta.set('forecast_account', id)
    else meta.delete('forecast_account')
  }
  if ('threshold' in input) {
    const n = Number(input.threshold)
    if (input.threshold === '' || input.threshold == null || !Number.isFinite(n) || n < 0) meta.delete('forecast_low')
    else meta.set('forecast_low', String(Math.round(n)))
  }
}

// The account paychecks land in, unless the user picked one.
function pickAccount(): { id: string; name: string; balance: number | null; available: number | null } | null {
  const chosen = forecastSettings().accountId
  const pick = db.prepare(`SELECT id, name, balance, available FROM accounts WHERE id = ? AND type = 'depository'`)
  if (chosen) {
    const a = pick.get(chosen) as any
    if (a) return a
  }
  const busiest = db.prepare(`
    SELECT a.id, COUNT(*) AS n FROM ledger l JOIN categories c ON c.id = l.category_id JOIN accounts a ON a.id = l.account_id
    WHERE a.type = 'depository' AND c.kind = 'income' AND l.amount < 0 AND l.date >= date('now', '-90 days')
    GROUP BY a.id ORDER BY n DESC, SUM(-l.amount) DESC LIMIT 1`).get() as { id: string } | undefined
  return busiest ? (pick.get(busiest.id) as any) : null
}

export function forecast(): Forecast | null {
  const account = pickAccount()
  if (!account) return null
  const now = today()
  const notes: string[] = []
  const { threshold } = forecastSettings()

  const { plan, saved } = loadPlan()
  const payday = plan.income.paycheck > 0 ? nextPayday(plan.income, now) : null
  if (!payday) notes.push(`Set your paycheck in Plan to forecast to payday. This looks ${FALLBACK_DAYS} days ahead.`)
  const until = payday ? fromDayNum(dayNum(payday) - 1) : fromDayNum(dayNum(now) + FALLBACK_DAYS)

  const items: ForecastItem[] = []

  // Card and loan payments due before payday that haven't been paid yet (a
  // missed one counts today). Assumed to come out of this account.
  for (const c of cardsDue()) {
    if (c.status === 'paid' || c.status === 'unknown') continue
    const date = c.status === 'missed' ? now : c.due
    if (date > until) continue
    const min = (db.prepare('SELECT min_payment FROM accounts WHERE id = ?').get(c.id) as { min_payment: number | null }).min_payment
    const amount = c.lastPayment?.amount ?? min
    if (!amount) {
      notes.push(`No payment amount known for ${c.name}; it isn't counted.`)
      continue
    }
    items.push({ date, label: `${c.name} payment`, amount: round(amount), kind: 'card' })
  }

  // Bills charged to this account, every time they come up before payday.
  const recurring = detectRecurring()
  const cards = items.filter((i) => i.kind === 'card')
  for (const r of recurring) {
    if (r.stopped || r.accountId !== account.id) continue
    const step = CADENCES.find((c) => c.name === r.cadence)?.days ?? 30.44
    const amount = round(r.variable ? Math.max(r.amount, r.average) : r.amount)
    let at = dayNum(r.nextDate)
    if (at < dayNum(now) - LATE_DAYS) continue
    // A loan payment the bills also list as a due date is counted once, as the due date.
    if (r.category === 'Debt Payments' && cards.some((c) => Math.abs(dayNum(c.date) - at) <= 5 && Math.abs(c.amount - amount) <= c.amount * 0.15)) continue
    for (; at <= dayNum(until); at = Math.round(at + step)) {
      items.push({ date: fromDayNum(Math.max(at, dayNum(now))), label: r.merchant, amount, kind: 'bill' })
    }
  }

  // Everyday spending from this account: what it spent in the last 60 days in
  // expense categories, leaving out loan payments, interest and the bills above.
  const billKeys = new Set(recurring.map((r) => r.key))
  const spent = db.prepare(`
    SELECT COALESCE(l.merchant, l.name) AS label, l.amount FROM ledger l JOIN categories c ON c.id = l.category_id
    WHERE l.account_id = ? AND c.kind = 'expense' AND c.name NOT IN ('Debt Payments', 'Interest') AND l.amount > 0
      AND l.date > date(?, '-${EVERYDAY_DAYS} days') AND l.date <= ?`).all(account.id, now, now) as { label: string; amount: number }[]
  const first = (db.prepare('SELECT MIN(date) AS d FROM transactions WHERE account_id = ? AND pending = 0').get(account.id) as { d: string | null }).d
  const days = first ? Math.min(EVERYDAY_DAYS, Math.max(14, dayNum(now) - dayNum(first) + 1)) : EVERYDAY_DAYS
  const everydayPerDay = round(spent.filter((s) => !billKeys.has(normalize(s.label ?? ''))).reduce((s, x) => s + x.amount, 0) / days)
  const everydayDays = dayNum(until) - dayNum(now)
  if (everydayPerDay > 0 && everydayDays > 0) {
    items.push({ date: until, label: `Everyday spending, about $${Math.round(everydayPerDay)} a day`, amount: round(everydayPerDay * everydayDays), kind: 'everyday' })
  }
  items.sort((a, b) => a.date.localeCompare(b.date) || (a.kind === 'everyday' ? 1 : 0) - (b.kind === 'everyday' ? 1 : 0))

  // Day by day: today's bills, then from tomorrow a day's everyday spending.
  const balance = round(account.available ?? account.balance ?? 0)
  let running = balance
  let low = { amount: balance, date: now }
  for (let d = dayNum(now); d <= dayNum(until); d++) {
    const date = fromDayNum(d)
    for (const i of items) if (i.kind !== 'everyday' && i.date === date) running -= i.amount
    if (d > dayNum(now)) running -= everydayPerDay
    if (running < low.amount) low = { amount: round(running), date }
  }

  const before = payday ? `before payday on ${shortDate(payday)}` : `in the next ${FALLBACK_DAYS} days`
  const warning = low.amount < threshold ? `${account.name} may drop to ${usd(low.amount)} on ${shortDate(low.date)}, ${before}.` : null

  return {
    account: { id: account.id, name: account.name },
    accounts: db.prepare(`SELECT id, name FROM accounts WHERE type = 'depository' ORDER BY name`).all() as { id: string; name: string }[],
    balance,
    payday,
    paydaySource: payday ? (saved ? 'plan' : 'deposits') : null,
    until,
    items,
    everydayPerDay,
    low,
    threshold,
    warning,
    notes,
  }
}

// For /api/summary and the daily briefing.
export function forecastBrief() {
  const f = forecast()
  return f && { account: f.account.name, balance: f.balance, payday: f.payday, low: f.low, warning: f.warning }
}
