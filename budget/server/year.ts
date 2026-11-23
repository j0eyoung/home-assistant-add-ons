import { db } from './db.ts'
import { currentMonth, historyStart } from './queries.ts'

// The Year tab: a year's totals, spending by category with last year beside
// it, the figures that matter at tax time, and a CSV of the year's ledger.

const round = (n: number) => Math.round(n * 100) / 100
const MONTHS = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']

// Categories whose totals people look for at tax time, in this order.
const TAX_CATEGORIES = ['Taxes & Giving', 'Health', 'HSA Contribution', '401k Contribution', 'Interest']

export function years(): string[] {
  return (db.prepare(`SELECT DISTINCT substr(date, 1, 4) AS y FROM transactions WHERE pending = 0 ORDER BY y DESC`).all() as { y: string }[]).map((r) => r.y)
}

export function yearReport(year: string) {
  if (!/^\d{4}$/.test(year)) throw new Error('Pick a year')
  const now = currentMonth()
  // The current year runs to this month; last year is compared over the same months.
  const lastMonth = year === now.slice(0, 4) ? now.slice(5, 7) : '12'
  const months = MONTHS.filter((m) => m <= lastMonth)
  const prior = String(Number(year) - 1)
  const first = historyStart()

  const perMonth = db.prepare(`
    SELECT c.id, c.name, c.kind, substr(l.date, 6, 2) AS month, SUM(l.amount) AS amount
    FROM ledger l JOIN categories c ON c.id = l.category_id
    WHERE l.pending = 0 AND substr(l.date, 1, 4) = ? AND substr(l.date, 6, 2) <= ?
    GROUP BY c.id, month`).all(year, lastMonth) as { id: number; name: string; kind: string; month: string; amount: number }[]
  const priorTotals = new Map((db.prepare(`
    SELECT c.id, SUM(l.amount) AS amount FROM ledger l JOIN categories c ON c.id = l.category_id
    WHERE l.pending = 0 AND substr(l.date, 1, 4) = ? AND substr(l.date, 6, 2) <= ?
    GROUP BY c.id`).all(prior, lastMonth) as { id: number; amount: number }[]).map((r) => [r.id, r.amount]))
  const hasPrior = Boolean(db.prepare(`SELECT 1 FROM transactions WHERE pending = 0 AND substr(date, 1, 4) = ? LIMIT 1`).get(prior))

  // Income and savings arrive as negative amounts; show them positive.
  const sign = (kind: string) => (kind === 'income' || kind === 'savings' ? -1 : 1)
  const categories = new Map<number, { id: number; name: string; kind: string; months: Record<string, number>; total: number; prior: number | null }>()
  for (const r of perMonth) {
    if (!categories.has(r.id)) categories.set(r.id, { id: r.id, name: r.name, kind: r.kind, months: {}, total: 0, prior: null })
    const c = categories.get(r.id)!
    c.months[r.month] = round(sign(r.kind) * r.amount)
    c.total = round(c.total + sign(r.kind) * r.amount)
  }
  for (const c of categories.values()) c.prior = hasPrior ? round(sign(c.kind) * (priorTotals.get(c.id) ?? 0)) : null

  // Average over the year's months the history fully covers.
  const covered = months.filter((m) => !first || `${year}-${m}` >= first.slice(0, 7))
  const kindTotals = (y: string) => new Map((db.prepare(`
    SELECT c.kind, SUM(l.amount) AS amount FROM ledger l JOIN categories c ON c.id = l.category_id
    WHERE l.pending = 0 AND substr(l.date, 1, 4) = ? AND substr(l.date, 6, 2) <= ? GROUP BY c.kind`).all(y, lastMonth) as { kind: string; amount: number }[])
    .map((r) => [r.kind, r.amount]))
  const thisYear = kindTotals(year)
  const lastYear = kindTotals(prior)
  const figure = (kind: string) => ({
    total: round(sign(kind) * (thisYear.get(kind) ?? 0)),
    prior: hasPrior ? round(sign(kind) * (lastYear.get(kind) ?? 0)) : null,
  })
  const income = figure('income')
  const spending = figure('expense')

  const spendingRows = [...categories.values()]
    .filter((c) => c.kind === 'expense' && c.total !== 0)
    .map((c) => ({ ...c, average: covered.length ? round(c.total / covered.length) : null }))
    .sort((a, b) => b.total - a.total)

  const total = (name: string) => [...categories.values()].find((c) => c.name === name)?.total ?? 0
  const tax = TAX_CATEGORIES.map((name) => ({ name, total: total(name) })).filter((t) => t.total !== 0)
  const giving = db.prepare(`
    SELECT l.date, COALESCE(l.merchant, l.name) AS description, l.amount, l.notes, a.name AS account
    FROM ledger l JOIN categories c ON c.id = l.category_id LEFT JOIN accounts a ON a.id = l.account_id
    WHERE c.name = 'Taxes & Giving' AND l.pending = 0 AND substr(l.date, 1, 4) = ? ORDER BY l.date`).all(year)

  return {
    year,
    years: years(),
    months,
    partial: lastMonth !== '12',
    coveredMonths: covered.length,
    priorYear: hasPrior ? prior : null,
    figures: {
      income,
      spending,
      saved: figure('savings'),
      leftOver: { total: round(income.total - spending.total), prior: hasPrior ? round((income.prior ?? 0) - (spending.prior ?? 0)) : null },
    },
    spending: spendingRows,
    tax,
    giving,
    loanInterest: loanInterest(year, months),
  }
}

// Interest on loans with a rate, estimated month by month from the month-end
// balance (or the current balance for months with no snapshot) times APR / 12.
// The lender's statement (a 1098 for a mortgage) has the real figure.
function loanInterest(year: string, months: string[]) {
  const loans = db.prepare(`SELECT id, name, balance, apr FROM accounts WHERE type = 'loan' AND apr > 0 ORDER BY name`).all() as { id: string; name: string; balance: number | null; apr: number }[]
  const monthEnd = db.prepare(`SELECT balance FROM balance_snapshots WHERE account_id = ? AND substr(date, 1, 7) = ? ORDER BY date DESC LIMIT 1`)
  return loans.map((l) => {
    let interest = 0
    for (const m of months) {
      const snap = monthEnd.get(l.id, `${year}-${m}`) as { balance: number | null } | undefined
      const owed = Math.max(0, -(snap?.balance ?? l.balance ?? 0))
      interest += (owed * l.apr) / 100 / 12
    }
    return { id: l.id, name: l.name, apr: l.apr, estimate: round(interest) }
  }).filter((l) => l.estimate > 0)
}

// The year's ledger (or every year's) as CSV. Splits come out as their parts.
// amount is bank style: money out negative, money in positive (the app itself
// stores money out as positive).
export function exportCsv(year: string): string {
  const all = year === 'all'
  if (!all && !/^\d{4}$/.test(year)) throw new Error('Pick a year')
  const rows = db.prepare(`
    SELECT l.date, a.name AS account, l.name AS description, l.merchant, c.name AS category, c.kind, l.amount, l.notes,
      CASE WHEN l.id != l.transaction_id THEN 'yes' ELSE 'no' END AS split, l.transaction_id, l.pending
    FROM ledger l LEFT JOIN accounts a ON a.id = l.account_id LEFT JOIN categories c ON c.id = l.category_id
    ${all ? '' : 'WHERE substr(l.date, 1, 4) = ?'}
    ORDER BY l.date, l.transaction_id, l.id`).all(...(all ? [] : [year])) as Record<string, unknown>[]
  const cell = (v: unknown) => {
    const s = v == null ? '' : String(v)
    return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  const header = ['date', 'account', 'description', 'merchant', 'category', 'kind', 'amount', 'notes', 'split', 'pending', 'transaction_id']
  const lines = rows.map((r) => [
    r.date, r.account, r.description, r.merchant, r.category, r.kind, (-(r.amount as number)).toFixed(2), r.notes, r.split, r.pending ? 'yes' : 'no', r.transaction_id,
  ].map(cell).join(','))
  return [header.join(','), ...lines].join('\r\n') + '\r\n'
}
