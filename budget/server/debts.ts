import { db } from './db.ts'
import { today } from './queries.ts'

const DAY = 86400000

// Debts plus what the last ~90 days say about how fast each is shrinking.
// payments_per_month: money paid in. paydown_per_month: payments minus new
// charges and interest, i.e. how much the balance actually drops.
export function debtSummary() {
  const accounts = db.prepare(`
    SELECT id, name, org_name, type, source, balance, apr, min_payment, in_plan, promo_apr, promo_end, due_day, autopay
    FROM accounts WHERE balance < 0 AND type IN ('credit', 'loan', 'other') ORDER BY balance`).all() as any[]
  const due = new Map(cardsDue().map((c) => [c.id, c]))
  const firstTx = db.prepare('SELECT MIN(date) AS d FROM transactions WHERE account_id = ? AND pending = 0')
  const flows = db.prepare(`
    SELECT COALESCE(SUM(CASE WHEN l.amount < 0 AND c.kind = 'transfer' THEN -l.amount ELSE 0 END), 0) AS payments,
      COALESCE(SUM(l.amount), 0) AS net
    FROM ledger l LEFT JOIN categories c ON c.id = l.category_id
    WHERE l.account_id = ? AND l.pending = 0 AND l.date >= ?`)
  const now = Date.parse(today())

  return accounts.map((a) => {
    const first = (firstTx.get(a.id) as { d: string | null }).d
    const days = first ? Math.min(90, Math.round((now - Date.parse(first)) / DAY)) : 0
    let payments: number | null = null
    let paydown: number | null = null
    if (days >= 25) {
      const since = new Date(now - days * DAY).toISOString().slice(0, 10)
      const f = flows.get(a.id, since) as { payments: number; net: number }
      payments = (f.payments * 30.44) / days
      paydown = (-f.net * 30.44) / days
    }
    return {
      id: a.id,
      name: a.name,
      org_name: a.org_name,
      type: a.type,
      source: a.source,
      owed: -a.balance,
      apr: a.apr,
      min_payment: a.min_payment,
      in_plan: Boolean(a.in_plan),
      promo_apr: a.promo_apr as number | null,
      promo_end: a.promo_end as string | null,
      payments_per_month: payments,
      paydown_per_month: paydown,
      history_days: days,
      due_day: a.due_day as number | null,
      autopay: Boolean(a.autopay),
      due: due.get(a.id) ?? null,
    }
  })
}

// ---- Due dates ----

export type DueStatus = 'paid' | 'not due yet' | 'due soon' | 'missed' | 'unknown'
export type CardDue = {
  id: string
  name: string
  type: string
  autopay: boolean
  due: string // next due date, today or later
  lastDue: string // the due date before it
  status: DueStatus
  lastPayment: { date: string; amount: number } | null
  message: string | null
}

const DUE_SOON_DAYS = 5
// Payments can take a couple of days to show up after the due date.
const POSTING_DAYS = 2

const dayNum = (date: string) => Math.round(Date.parse(`${date}T00:00:00Z`) / DAY)
const shortDate = (d: string) => new Date(`${d}T00:00:00Z`).toLocaleString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })

// The due date in a month (YYYY-MM): due_day, or the month's last day if it's shorter.
function dueIn(month: string, day: number): string {
  const [y, m] = month.split('-').map(Number)
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate()
  return `${month}-${String(Math.min(day, last)).padStart(2, '0')}`
}
const shiftMonth = (month: string, n: number) => {
  const [y, m] = month.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1 + n, 1)).toISOString().slice(0, 7)
}

// For every card or loan with a due day and money owed: the next due date, and
// whether the payment for it (or for the one before) has posted. A payment is
// money arriving on the account in a transfer category, pending included,
// since a payment that's been sent counts. "missed": more than POSTING_DAYS
// past the last due date with no payment since the due date before it.
// "due soon": autopay off, the next due date within DUE_SOON_DAYS, and no
// payment since the last due date.
export function cardsDue(): CardDue[] {
  const accounts = db.prepare(`
    SELECT id, name, type, autopay, due_day FROM accounts
    WHERE due_day BETWEEN 1 AND 31 AND balance < 0 AND type IN ('credit', 'loan', 'other') ORDER BY name`).all() as any[]
  const payments = db.prepare(`
    SELECT l.date, -l.amount AS amount FROM ledger l JOIN categories c ON c.id = l.category_id
    WHERE l.account_id = ? AND l.amount < 0 AND c.kind = 'transfer' ORDER BY l.date DESC`)
  const firstTx = db.prepare('SELECT MIN(date) AS d FROM transactions WHERE account_id = ?')
  const now = today()
  const month = now.slice(0, 7)
  return accounts.map((a) => {
    const thisMonth = dueIn(month, a.due_day)
    const next = thisMonth >= now ? thisMonth : dueIn(shiftMonth(month, 1), a.due_day)
    const last = thisMonth < now ? thisMonth : dueIn(shiftMonth(month, -1), a.due_day)
    const before = dueIn(shiftMonth(last.slice(0, 7), -1), a.due_day)
    const paid = payments.all(a.id) as { date: string; amount: number }[]
    const since = (d: string) => paid.some((p) => p.date > d)
    const first = (firstTx.get(a.id) as { d: string | null }).d
    let status: DueStatus
    let message: string | null = null
    // A manual account (a mortgage servicer, say) has no transactions, so its
    // payments can't be seen.
    if (!first) status = 'unknown'
    else if (since(last)) status = 'paid'
    else if (dayNum(now) - dayNum(last) > POSTING_DAYS && !since(before)) {
      // Without history back to the due date before, there's no telling.
      if (first > before) status = 'unknown'
      else {
        status = 'missed'
        message = `${a.name} was due ${shortDate(last)} and no payment has posted.`
      }
    } else if (!a.autopay && dayNum(next) - dayNum(now) <= DUE_SOON_DAYS) {
      status = 'due soon'
      message = `${a.name} is due ${next === now ? 'today' : shortDate(next)} and hasn't been paid since ${shortDate(last)}.`
    } else status = 'not due yet'
    return {
      id: a.id,
      name: a.name,
      type: a.type,
      autopay: Boolean(a.autopay),
      due: next,
      lastDue: last,
      status,
      lastPayment: paid[0] ? { date: paid[0].date, amount: Math.round(paid[0].amount * 100) / 100 } : null,
      message,
    }
  })
}
