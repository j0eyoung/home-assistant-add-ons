import { categoryIdByName, db, reimbursableId } from './db.ts'

// "Paid back later": charges in the Reimbursable category are money someone
// owes the user (work travel, a shared bill). The category's kind counts as
// nothing, so they never show as spending. Each charge stays "owed" until it's
// matched to the deposit that paid it back (that deposit goes in Reimbursable
// too, so it doesn't count as income) or marked paid back by hand.

const DEPOSIT_DAYS = 120
const PAID_SHOWN_DAYS = 90

type Row = { id: string; transaction_id: string; date: string; description: string; amount: number; account: string | null; notes: string | null; repaid_by: string | null }

// Reimbursable charges by ledger row, so the Reimbursable part of a split counts on its own.
const CHARGES = `
  SELECT l.id, l.transaction_id, l.date, COALESCE(l.merchant, l.name) AS description, l.amount, a.name AS account, l.notes, t.repaid_by
  FROM ledger l JOIN transactions t ON t.id = l.transaction_id LEFT JOIN accounts a ON a.id = l.account_id
  WHERE l.category_id = ? AND l.amount > 0`

const round = (n: number) => Math.round(n * 100) / 100

export function owed(): Row[] {
  const id = reimbursableId()
  if (id == null) return []
  return db.prepare(`${CHARGES} AND t.repaid_by IS NULL ORDER BY l.date, l.id`).all(id) as Row[]
}

export function owedBrief() {
  const rows = owed()
  return { total: round(rows.reduce((s, r) => s + r.amount, 0)), count: rows.length, oldest: rows[0]?.date ?? null }
}

export function reimbursements() {
  const id = reimbursableId()
  const open = owed()
  const paid = id == null ? [] : (db.prepare(`${CHARGES} AND t.repaid_by IS NOT NULL AND l.date >= date('now', '-${PAID_SHOWN_DAYS} days')
    ORDER BY l.date DESC, l.id`).all(id) as Row[])
  const depositIds = [...new Set(paid.map((p) => p.repaid_by).filter((d): d is string => Boolean(d) && d !== 'manual'))]
  const deposit = db.prepare(`SELECT t.id, t.date, COALESCE(t.merchant, t.name) AS description, -t.amount AS amount, a.name AS account
    FROM transactions t LEFT JOIN accounts a ON a.id = t.account_id WHERE t.id = ?`)
  const deposits = new Map(depositIds.map((d) => [d, deposit.get(d) ?? null]))
  return {
    categoryId: id,
    total: round(open.reduce((s, r) => s + r.amount, 0)),
    open,
    paid: paid.map((p) => ({ ...p, deposit: p.repaid_by && p.repaid_by !== 'manual' ? deposits.get(p.repaid_by) ?? null : null })),
    deposits: candidateDeposits(),
  }
}

// Money that came into a bank account recently and could be a repayment (Zelle
// and Venmo usually land as transfers, so those count too), not already in
// Reimbursable. Card accounts are left out: what arrives there is card payments.
// Amounts are positive here.
function candidateDeposits() {
  const id = reimbursableId()
  const oldest = owed()[0]?.date
  if (!oldest || id == null) return []
  return db.prepare(`
    SELECT t.id, t.date, COALESCE(t.merchant, t.name) AS description, -t.amount AS amount, a.name AS account, c.name AS category
    FROM transactions t LEFT JOIN accounts a ON a.id = t.account_id LEFT JOIN categories c ON c.id = t.category_id
    WHERE t.amount < 0 AND t.pending = 0 AND t.date >= ? AND t.date >= date('now', '-${DEPOSIT_DAYS} days')
      AND (t.category_id IS NULL OR t.category_id != ?)
      AND NOT EXISTS (SELECT 1 FROM splits s WHERE s.transaction_id = t.id)
      AND a.type = 'depository'
    ORDER BY t.date DESC LIMIT 200`).all(oldest, id) as { id: string; date: string; description: string; amount: number; account: string | null; category: string | null }[]
}

// A deposit paid back these charges: the deposit goes in Reimbursable (so it
// isn't income) and each charge is marked paid back by it.
export function matchDeposit(depositId: string, chargeIds: string[]) {
  const id = reimbursableId()
  if (id == null) throw new Error('The Reimbursable category is missing.')
  const deposit = db.prepare('SELECT amount FROM transactions WHERE id = ?').get(depositId) as { amount: number } | undefined
  if (!deposit || deposit.amount >= 0) throw new Error('Pick a deposit (money coming in).')
  const ids = chargeIds.map(String).filter(Boolean)
  if (!ids.length) throw new Error('Tick at least one charge it paid back.')
  const open = new Set(owed().map((r) => r.transaction_id))
  if (ids.some((c) => !open.has(c))) throw new Error('One of those charges is no longer waiting to be paid back.')
  db.exec('BEGIN')
  try {
    db.prepare(`UPDATE transactions SET category_id = ?, category_source = 'user', reviewed = 1 WHERE id = ?
      AND NOT EXISTS (SELECT 1 FROM splits s WHERE s.transaction_id = transactions.id)`).run(id, depositId)
    const mark = db.prepare('UPDATE transactions SET repaid_by = ? WHERE id = ?')
    for (const c of ids) mark.run(depositId, c)
    db.exec('COMMIT')
  } catch (err) {
    db.exec('ROLLBACK')
    throw err
  }
}

export function markPaidBack(transactionId: string) {
  const open = new Set(owed().map((r) => r.transaction_id))
  if (!open.has(transactionId)) throw new Error('That charge is not waiting to be paid back.')
  db.prepare(`UPDATE transactions SET repaid_by = 'manual' WHERE id = ?`).run(transactionId)
}

// Puts a charge back on the owed list. A deposit no other charge points to any
// more goes back to waiting for a category (Other, picked up by rules or the AI).
export function undoPaidBack(transactionId: string) {
  const row = db.prepare('SELECT repaid_by FROM transactions WHERE id = ?').get(transactionId) as { repaid_by: string | null } | undefined
  if (!row?.repaid_by) return
  db.exec('BEGIN')
  try {
    db.prepare('UPDATE transactions SET repaid_by = NULL WHERE id = ?').run(transactionId)
    const depositId = row.repaid_by
    if (depositId !== 'manual' && !db.prepare('SELECT 1 FROM transactions WHERE repaid_by = ?').get(depositId)) {
      db.prepare(`UPDATE transactions SET category_id = ?, category_source = 'none', reviewed = 0 WHERE id = ? AND category_id = ?`)
        .run(categoryIdByName('Other'), depositId, reimbursableId())
    }
    db.exec('COMMIT')
  } catch (err) {
    db.exec('ROLLBACK')
    throw err
  }
}
