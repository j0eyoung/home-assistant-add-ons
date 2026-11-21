import { config } from './config.ts'
import { categoryIdByName, db, meta, secret } from './db.ts'

// SimpleFIN Bridge: https://beta-bridge.simplefin.org/info/developers
// A one-time setup token is base64 of a claim URL; POSTing to it returns the
// access URL (with embedded credentials) used for all later /accounts calls.

const ACCESS_KEY = 'simplefin_access_url'
const LOOKBACK_FIRST_SYNC_DAYS = 365
const LOOKBACK_RESYNC_DAYS = 7

export function isConnected(): boolean {
  return Boolean(secret.get(ACCESS_KEY) || config.simplefinAccessUrl)
}

export async function claimSetupToken(setupToken: string): Promise<void> {
  const claimUrl = Buffer.from(setupToken.trim(), 'base64').toString('utf8')
  if (!/^https:\/\/|^http:\/\/127\.0\.0\.1/.test(claimUrl)) throw new Error('That does not look like a SimpleFIN setup token')
  const res = await fetch(claimUrl, { method: 'POST', headers: { 'Content-Length': '0' } })
  if (!res.ok) throw new Error(`SimpleFIN claim failed (${res.status}). Setup tokens are single-use; create a new one.`)
  secret.set(ACCESS_KEY, (await res.text()).trim())
}

export function disconnect(): void {
  secret.delete(ACCESS_KEY)
}

// Node's fetch rejects URLs with embedded credentials, so split them out.
function accessRequest(): { base: string; headers: Record<string, string> } {
  const raw = secret.get(ACCESS_KEY) || config.simplefinAccessUrl
  if (!raw) throw new Error('SimpleFIN is not connected yet')
  const url = new URL(raw)
  const auth = Buffer.from(`${decodeURIComponent(url.username)}:${decodeURIComponent(url.password)}`).toString('base64')
  url.username = ''
  url.password = ''
  return { base: url.toString().replace(/\/$/, ''), headers: { Authorization: `Basic ${auth}` } }
}

type SfTransaction = { id: string; posted: number; transacted_at?: number; amount: string; description?: string; payee?: string; memo?: string; pending?: boolean }
type SfAccount = {
  id: string
  org: { name?: string; domain?: string }
  name: string
  currency: string
  balance: string
  'available-balance'?: string
  'balance-date': number
  transactions: SfTransaction[]
}

// SimpleFIN doesn't say what kind of account it is; guess from the name and
// sign, and let the user correct it in the Accounts tab.
function guessType(a: SfAccount): string {
  const text = `${a.org.name ?? ''} ${a.name}`.toLowerCase()
  if (/mortgage|loan|lightstream/.test(text)) return 'loan'
  if (/card|credit|visa|mastercard|discover|amex|blue cash/.test(text)) return 'credit'
  if (/brokerage|invest|401|ira|roth/.test(text)) return 'investment'
  return Number(a.balance) < 0 ? 'credit' : 'depository'
}

const dateOf = (unix: number) => new Date(unix * 1000).toISOString().slice(0, 10)
// Pending transactions arrive with posted = 0; use when they happened, or today.
const txDate = (t: SfTransaction) => dateOf(t.posted > 0 ? t.posted : t.transacted_at || Date.now() / 1000)

// How far back to fetch a SimpleFIN account that first shows up on a later
// sync: SimpleFIN Bridge keeps about 90 days.
export const BACKFILL_DAYS = 90
// Accounts merged into their replacement (old id -> new id) in the Accounts
// tab. A reconnected bank can keep returning the old ids; their data is stale.
export const MERGED_KEY = 'merged_accounts'
export const mergedAccounts = (): Record<string, string> => JSON.parse(meta.get(MERGED_KEY) || '{}')

// One /accounts request. accountIds limits it to those accounts (the
// protocol's `account` parameter); callers still filter the reply.
async function fetchAccounts(days: number, accountIds: string[] = []): Promise<{ errors: string[]; accounts: SfAccount[] }> {
  const { base, headers } = accessRequest()
  const params = new URLSearchParams({ 'start-date': String(Math.floor(Date.now() / 1000) - days * 86400), pending: '1' })
  for (const id of accountIds) params.append('account', id)
  const res = await fetch(`${base}/accounts?${params}`, { headers })
  if (res.status === 403) throw new Error('SimpleFIN rejected the access URL. Reconnect with a new setup token.')
  if (!res.ok) throw new Error(`SimpleFIN request failed (${res.status})`)
  return (await res.json()) as { errors: string[]; accounts: SfAccount[] }
}

// Inserts or updates one account's transactions; returns how many posted ones are new.
// New transactions start as 'Other' until a rule, the AI or the user relabels them.
function storeTransactions(accountId: string, transactions: SfTransaction[]): number {
  const rule = db.prepare('SELECT category_id FROM rules WHERE pattern = ?')
  const txExists = db.prepare('SELECT 1 FROM transactions WHERE id = ?')
  const insertTx = db.prepare(`
    INSERT INTO transactions (id, account_id, date, name, merchant, amount, pending, category_id, category_source)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET date = excluded.date, name = excluded.name, merchant = excluded.merchant,
      amount = excluded.amount, pending = excluded.pending`)
  const fallback = categoryIdByName('Other')
  let added = 0
  for (const t of transactions) {
    const label = t.payee || t.description || ''
    const ruleHit = rule.get(label.toLowerCase()) as { category_id: number } | undefined
    const isNew = !txExists.get(t.id)
    insertTx.run(t.id, accountId, txDate(t), t.description ?? label, t.payee ?? null,
      -Number(t.amount), t.pending ? 1 : 0, ruleHit?.category_id ?? fallback, ruleHit ? 'rule' : 'none')
    if (isNew && !t.pending) added++
  }
  return added
}

// Fetches the last BACKFILL_DAYS of transactions for these accounts (one request).
export async function backfillAccounts(accountIds: string[]): Promise<number> {
  if (!accountIds.length) return 0
  const data = await fetchAccounts(BACKFILL_DAYS, accountIds)
  let added = 0
  db.exec('BEGIN')
  try {
    for (const a of data.accounts) if (accountIds.includes(a.id)) added += storeTransactions(a.id, a.transactions ?? [])
    db.exec('COMMIT')
  } catch (err) {
    db.exec('ROLLBACK')
    throw err
  }
  return added
}

export async function syncSimpleFin(): Promise<{ added: number; errors: string[] }> {
  const lastSync = meta.get('last_sync')
  const data = await fetchAccounts(lastSync ? LOOKBACK_RESYNC_DAYS : LOOKBACK_FIRST_SYNC_DAYS)

  const now = new Date().toISOString()
  const today = now.slice(0, 10)
  const existingAccount = db.prepare('SELECT type FROM accounts WHERE id = ?')
  const upsertAccount = db.prepare(`
    INSERT INTO accounts (id, source, org_name, name, type, balance, available, currency, balance_date, updated_at)
    VALUES (?, 'simplefin', ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET org_name = excluded.org_name, name = excluded.name, balance = excluded.balance,
      available = excluded.available, currency = excluded.currency, balance_date = excluded.balance_date, updated_at = excluded.updated_at`)
  const snapshot = db.prepare('INSERT OR REPLACE INTO balance_snapshots (date, account_id, balance) VALUES (?, ?, ?)')
  const clearPending = db.prepare('DELETE FROM transactions WHERE account_id = ? AND pending = 1')

  const merged = mergedAccounts()
  const fresh: string[] = []
  let added = 0
  db.exec('BEGIN')
  try {
    for (const a of data.accounts) {
      if (merged[a.id]) continue
      const known = existingAccount.get(a.id) as { type: string } | undefined
      if (!known && lastSync) fresh.push(a.id)
      upsertAccount.run(a.id, a.org.name ?? a.org.domain ?? null, a.name, known?.type ?? guessType(a), Number(a.balance),
        a['available-balance'] != null ? Number(a['available-balance']) : null, a.currency, dateOf(a['balance-date']), now)
      snapshot.run(today, a.id, Number(a.balance))
      clearPending.run(a.id)
      added += storeTransactions(a.id, a.transactions ?? [])
    }
    meta.set('last_sync', now)
    meta.set('last_sync_errors', JSON.stringify(data.errors ?? []))
    db.exec('COMMIT')
  } catch (err) {
    db.exec('ROLLBACK')
    throw err
  }
  // An account that first appears on a later sync (often a bank reconnected at
  // bridge.simplefin.org, which gives its accounts new ids) only got the short
  // resync window; fetch its history too.
  if (fresh.length) {
    try {
      added += await backfillAccounts(fresh)
    } catch (err: any) {
      console.error('Fetching history for new accounts failed:', err.message)
    }
  }
  return { added, errors: data.errors ?? [] }
}
