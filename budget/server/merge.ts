import fs from 'node:fs'
import path from 'node:path'
import { config } from './config.ts'
import { db, meta } from './db.ts'
import { MERGED_KEY, backfillAccounts, isConnected, mergedAccounts } from './simplefin.ts'

type Account = { id: string; source: string; org_name: string | null; name: string; type: string; balance_date: string | null }
type Tx = {
  id: string
  date: string
  amount: number
  pending: number
  category_id: number | null
  category_source: string
  reviewed: number
  notes: string | null
  splits: number
}

const sameAccount = (a: Account) => `${(a.org_name ?? '').trim().toLowerCase()}|${a.name.trim().toLowerCase()}`

// Reconnecting a bank at bridge.simplefin.org gives its accounts new ids, so
// each one shows twice: the old copy stops updating and the new one starts
// with a short history. Old id -> the newest account with the same institution
// and name that has updated more recently.
export function replacements(): Map<string, string> {
  const accounts = db.prepare(`SELECT id, source, org_name, name, type, balance_date FROM accounts WHERE source = 'simplefin'`).all() as Account[]
  const out = new Map<string, string>()
  for (const a of accounts) {
    const newer = accounts
      .filter((b) => b.id !== a.id && sameAccount(b) === sameAccount(a) && (b.balance_date ?? '') > (a.balance_date ?? ''))
      .sort((x, y) => (y.balance_date ?? '').localeCompare(x.balance_date ?? ''))
    if (newer.length) out.set(a.id, newer[0].id)
  }
  return out
}

const dayNumber = (date: string) => Date.parse(`${date}T00:00:00Z`) / 86400000
// Someone's own decision about a category, as opposed to the AI's or the default.
const decided = (t: Tx) => t.category_source === 'user' || t.category_source === 'rule' || t.splits > 0 || t.reviewed > 0
const MATCH_DAYS = 3

// Folds account `fromId` into `intoId`: fetches the new account's full history
// first (when it's a SimpleFIN account), then moves each old transaction over
// unless the new account already has it (same amount within MATCH_DAYS days),
// in which case the user's category, split, note and review carry over to the
// new copy. Balance history, debt settings and plan goals move too, and the old
// account is removed and skipped by later syncs. A copy of the database is
// saved first as before-merge.db in the backups folder.
export async function mergeAccount(fromId: string, intoId: string) {
  const get = db.prepare('SELECT id, source, org_name, name, type, balance_date FROM accounts WHERE id = ?')
  const from = get.get(fromId) as Account | undefined
  const into = get.get(intoId) as Account | undefined
  if (!from || !into) throw new Error('No such account')
  if (from.id === into.id) throw new Error("An account can't be merged into itself")

  let backfilled = 0
  let warning: string | null = null
  if (into.source === 'simplefin' && isConnected()) {
    try {
      backfilled = await backfillAccounts([into.id])
    } catch (err: any) {
      warning = `Couldn't fetch the new account's older history from SimpleFIN (${err.message}); merged what's here.`
    }
  }

  fs.mkdirSync(config.backupDir, { recursive: true })
  const safety = path.join(config.backupDir, 'before-merge.db')
  fs.rmSync(safety, { force: true })
  db.exec(`VACUUM INTO '${safety.replace(/'/g, "''")}'`)

  const rows = db.prepare(`
    SELECT t.id, t.date, t.amount, t.pending, t.category_id, t.category_source, t.reviewed, t.notes,
      (SELECT COUNT(*) FROM splits s WHERE s.transaction_id = t.id) AS splits
    FROM transactions t WHERE t.account_id = ? ORDER BY t.date, t.id`)
  const intoRows = (rows.all(into.id) as Tx[]).filter((t) => !t.pending)
  const firstInto = intoRows[0]?.date ?? null
  const used = new Set<string>()
  const counts = { moved: 0, matched: 0, backfilled, warning }

  db.exec('BEGIN')
  try {
    const dropSplits = db.prepare('DELETE FROM splits WHERE transaction_id = ?')
    const drop = db.prepare('DELETE FROM transactions WHERE id = ?')
    const move = db.prepare('UPDATE transactions SET account_id = ? WHERE id = ?')
    for (const t of rows.all(from.id) as Tx[]) {
      // Pending rows are replaced on every sync anyway.
      if (t.pending) {
        dropSplits.run(t.id)
        drop.run(t.id)
        continue
      }
      const near = firstInto && dayNumber(t.date) >= dayNumber(firstInto) - MATCH_DAYS
      const twin = near
        ? intoRows
          .filter((n) => !used.has(n.id) && Math.abs(n.amount - t.amount) < 0.005 && Math.abs(dayNumber(n.date) - dayNumber(t.date)) <= MATCH_DAYS)
          .sort((a, b) => Math.abs(dayNumber(a.date) - dayNumber(t.date)) - Math.abs(dayNumber(b.date) - dayNumber(t.date)))[0]
        : undefined
      if (!twin) {
        move.run(into.id, t.id)
        counts.moved++
        continue
      }
      used.add(twin.id)
      if (decided(t) && !decided(twin)) {
        db.prepare('UPDATE transactions SET category_id = ?, category_source = ?, reviewed = ? WHERE id = ?')
          .run(t.category_id, t.splits ? 'user' : t.category_source, 1, twin.id)
        if (t.splits) db.prepare('UPDATE splits SET transaction_id = ? WHERE transaction_id = ?').run(twin.id, t.id)
      }
      if (t.notes) db.prepare('UPDATE transactions SET notes = COALESCE(notes, ?) WHERE id = ?').run(t.notes, twin.id)
      dropSplits.run(t.id)
      drop.run(t.id)
      counts.matched++
    }

    db.prepare('INSERT OR IGNORE INTO balance_snapshots (date, account_id, balance) SELECT date, ?, balance FROM balance_snapshots WHERE account_id = ?')
      .run(into.id, from.id)
    db.prepare('DELETE FROM balance_snapshots WHERE account_id = ?').run(from.id)
    // The old account's type and debt terms are the ones the user set up.
    db.prepare(`UPDATE accounts SET type = ?, apr = COALESCE(apr, ?), min_payment = COALESCE(min_payment, ?),
      promo_apr = COALESCE(promo_apr, ?), promo_end = COALESCE(promo_end, ?), in_plan = ? WHERE id = ?`)
      .run(...(() => {
        const o = db.prepare('SELECT type, apr, min_payment, promo_apr, promo_end, in_plan FROM accounts WHERE id = ?').get(from.id) as any
        return [o.type, o.apr, o.min_payment, o.promo_apr, o.promo_end, o.in_plan, into.id] as const
      })())

    const plan = meta.get('plan')
    if (plan) {
      const p = JSON.parse(plan)
      for (const g of p.goals ?? []) if (g.accountId === from.id) g.accountId = into.id
      meta.set('plan', JSON.stringify(p))
    }
    const merged = mergedAccounts()
    for (const [old, target] of Object.entries(merged)) if (target === from.id) merged[old] = into.id
    merged[from.id] = into.id
    meta.set(MERGED_KEY, JSON.stringify(merged))
    db.prepare('DELETE FROM accounts WHERE id = ?').run(from.id)
    db.exec('COMMIT')
  } catch (err) {
    db.exec('ROLLBACK')
    throw err
  }
  return counts
}
