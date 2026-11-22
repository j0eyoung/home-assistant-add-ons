import { useState } from 'react'
import { addMonths, dollars, monthLabel, thisMonth } from './api.ts'
import type { BudgetRow } from './api.ts'
import { Icon } from './Icon.tsx'

// Where the month is, for the pace marker on each rule; null for other months.
function monthProgress(month: string): { day: number; days: number } | null {
  if (month !== thisMonth()) return null
  const now = new Date()
  return { day: now.getDate(), days: new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate() }
}

const pct = (n: number) => `${Math.max(0, Math.min(100, n * 100))}%`

function PaceRule({ used, at }: { used: number; at: number | null }) {
  return (
    <div className="pace-rule" aria-hidden="true">
      <i style={{ width: pct(used) }} />
      {at != null && <u style={{ left: pct(at) }} />}
    </div>
  )
}

// The dashboard's sign: the month's total and each category with what's
// left, set right like mileage, closest to running out first. Over-budget
// lines turn sign yellow, untouched ones print grey, and categories with no
// budget follow under their own rule.
export function Sign({ month, rows, onOpenBudget }: { month: string; rows: BudgetRow[] | null; onOpenBudget: () => void }) {
  const [showQuiet, setShowQuiet] = useState(false)
  const progress = monthProgress(month)
  const at = progress ? progress.day / progress.days : null
  const prev = monthLabel(addMonths(month, -1), false)

  if (!rows) {
    return (
      <section className="sign" aria-busy="true">
        <h2>{monthLabel(month)}{progress && <span>Day {progress.day} of {progress.days}</span>}</h2>
        <div className="sign-loading" aria-hidden="true"><i /><i /><i /><i /></div>
      </section>
    )
  }
  const expenses = rows.filter((r) => r.kind === 'expense')
  const budgeted = expenses.filter((r) => r.budget > 0).sort((a, b) => {
    if ((a.spent > 0) !== (b.spent > 0)) return a.spent > 0 ? -1 : 1
    return a.budget - a.spent - (b.budget - b.spent)
  })
  const unbudgeted = expenses.filter((r) => r.budget <= 0 && r.spent > 0).sort((a, b) => b.spent - a.spent)
  const quiet = expenses.filter((r) => r.budget <= 0 && r.spent <= 0 && r.prev > 0)

  const total = budgeted.reduce((s, r) => s + r.budget, 0)
  const spentIn = budgeted.reduce((s, r) => s + r.spent, 0)
  const spentAll = expenses.reduce((s, r) => s + r.spent, 0)
  const prevAll = expenses.reduce((s, r) => s + r.prev, 0)
  const left = total - spentIn

  const trend = (r: BudgetRow) =>
    r.prev > 0 ? (
      <span>
        <Icon name={r.spent > r.prev + 0.5 ? 'up' : r.spent < r.prev - 0.5 ? 'down' : 'equal'} size={14} /> {dollars(r.prev)} in {prev}
      </span>
    ) : null

  return (
    <section className="sign" aria-label={`${monthLabel(month)} against the budget`}>
      <h2>
        {monthLabel(month)}
        {progress && <span>Day {progress.day} of {progress.days}</span>}
      </h2>
      {total > 0 ? (
        <>
          <div className={`sign-total ${left < 0 ? 'over' : ''}`}>
            <strong>{dollars(Math.abs(left))}</strong>
            <span>{left < 0 ? 'over' : 'left'} of {dollars(total)}</span>
          </div>
          <PaceRule used={total ? spentIn / total : 0} at={at} />
          <p className="sign-sub">{dollars(spentAll)} spent in all · {dollars(prevAll)} in {prev}</p>
        </>
      ) : (
        <>
          <div className="sign-total"><strong>{dollars(spentAll)}</strong><span>spent</span></div>
          <p className="empty-sign">Set monthly targets and this shows what's left in each category.</p>
          <button onClick={onOpenBudget}>Set targets</button>
        </>
      )}

      {budgeted.length > 0 && (
        <div className="sign-rows">
          {budgeted.map((r) => {
            const over = r.spent > r.budget
            return (
              <div key={r.id} className={`sign-row ${over ? 'over' : ''} ${r.spent <= 0 ? 'idle' : ''}`}>
                <div className="sign-line">
                  <b>{over && <span className="diamond" aria-hidden="true" />}{r.name}</b>
                  <strong>{over ? `${dollars(r.spent - r.budget)} over` : dollars(r.budget - r.spent)}</strong>
                </div>
                <div className="sign-meta"><span>{dollars(r.spent)} of {dollars(r.budget)}</span>{trend(r)}</div>
                <PaceRule used={r.spent / r.budget} at={at} />
              </div>
            )
          })}
        </div>
      )}

      {unbudgeted.length > 0 && (
        <div className="sign-group">
          <h3>No budget set</h3>
          {unbudgeted.map((r) => (
            <div key={r.id} className="sign-row">
              <div className="sign-line"><b>{r.name}</b><strong>{dollars(r.spent)}</strong></div>
              <div className="sign-meta"><span>spent</span>{trend(r)}</div>
            </div>
          ))}
        </div>
      )}

      {quiet.length > 0 && (
        <>
          {showQuiet && (
            <div className="sign-group">
              <h3>Spent on in {prev}, not yet this month</h3>
              {quiet.map((r) => (
                <div key={r.id} className="sign-row idle">
                  <div className="sign-line"><b>{r.name}</b><strong>{dollars(r.prev)}</strong></div>
                </div>
              ))}
            </div>
          )}
          <button className="link left" onClick={() => setShowQuiet(!showQuiet)}>
            {showQuiet ? `Hide ${prev}'s other categories` : `Show ${quiet.length} more from ${prev}`}
          </button>
        </>
      )}
    </section>
  )
}
