import { useCallback, useEffect, useState } from 'react'
import { api } from './api.ts'

type Backup = { name: string; date: string; size: number; accounts?: number; transactions?: number; lastDate?: string | null }

// Nightly backups, and restoring one: after a reinstall, or to bring data over
// from another install by copying its budget-YYYY-MM-DD.db into the folder shown.
export function Backups({ onError, onDone }: { onError: (m: string) => void; onDone: () => void }) {
  const [data, setData] = useState<{ folder: string; backups: Backup[] } | null>(null)
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const load = useCallback(() => {
    api('backups').then(setData).catch((e) => onError(e.message))
  }, [onError])
  useEffect(load, [load])

  const run = async (label: string, fn: () => Promise<string>) => {
    setBusy(label)
    try {
      setMessage(await fn())
      load()
      onDone()
    } catch (e: any) {
      onError(e.message)
    }
    setBusy('')
  }
  const backupNow = () => run('backup', async () => ((await api('backups', 'POST')).file ? 'Backed up.' : 'Nothing to back up yet: no accounts.'))
  const restore = (b: Backup) => {
    if (!window.confirm(`Replace everything in the app with the backup from ${b.date} (${b.accounts ?? '?'} accounts, ${b.transactions ?? '?'} transactions)?\n\nWhat's here now is saved as before-restore.db first. Your SimpleFIN and Claude connections stay as they are.`)) return
    run(b.name, async () => {
      await api('backups/restore', 'POST', { name: b.name })
      return `Restored the ${b.date} backup. Click Sync now (above) to pull in anything newer.`
    })
  }

  return (
    <section>
      <div className="chart-head">
        <h2>Backups</h2>
        <button onClick={backupNow} disabled={Boolean(busy)}>{busy === 'backup' ? 'Backing up…' : 'Back up now'}</button>
      </div>
      <p className="muted">
        A copy of your data is saved every night (the last 7 are kept) in <code className="inline">{data?.folder ?? '…'}</code>. To bring data over from another install
        of this add-on, copy its newest budget-YYYY-MM-DD.db file into that folder (Samba share or the SSH add-on), then restore it here.
      </p>
      {data && !data.backups.length && <p className="muted">No backups yet.</p>}
      {data?.backups.map((b) => (
        <div className="account" key={b.name}>
          <div>
            {b.date}
            <div className="muted">
              {b.accounts != null ? `${b.accounts} accounts · ${b.transactions} transactions${b.lastDate ? ` through ${b.lastDate}` : ''}` : "couldn't read this file"}
            </div>
          </div>
          <button onClick={() => restore(b)} disabled={Boolean(busy) || !b.accounts}>{busy === b.name ? 'Restoring…' : 'Restore'}</button>
        </div>
      ))}
      {message && <p className="notice good">{message}</p>}
    </section>
  )
}
