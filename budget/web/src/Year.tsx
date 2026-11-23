import { Fragment, useEffect, useState } from 'react'
import { api, dollars, money, monthLabel, shortDate, thisMonth, useNarrow } from './api.ts'

type Figure = { total: number; prior: number | null }
type Row = { id: number; name: string; total: number; prior: number | null; average: number | null; months: Record<string, number> }
type YearData = {
  year: string
  years: string[]
  months: string[]
  partial: boolean
  coveredMonths: number
  priorYear: string | null
  figures: { income: Figure; spending: Figure; saved: Figure; leftOver: Figure }
  spending: Row[]
  tax: { name: string; total: number }[]
  giving: { date: string; description: string; amount: number; notes: string | null; account: string | null }[]
  loanInterest: { id: string; name: string; apr: number; estimate: number }[]
}

const monthName = (year: string, m: string) => monthLabel(`${year}-${m}`, false)

// The Year tab: the year's totals against last year, spending by category,
// what's needed at tax time, and the year's transactions as a CSV.
export function YearPage({ onError }: { onError: (m: string) => void }) {
  const [year, setYear] = useState(thisMonth().slice(0, 4))
  const [data, setData] = useState<YearData | null>(null)
  const [showMonths, setShowMonths] = useState(false)
  const narrow = useNarrow()
  useEffect(() => {
    setData(null)
    api<YearData>(`year?year=${year}`).then(setData).catch((e) => onError(e.message))
  }, [year, onError])

  const years = data?.years.length ? data.years : [year]
  const range = data && data.partial ? `${monthName(year, '01')} to ${monthName(year, data.months.at(-1)!)}` : null
  const compare = (f: Figure, better: 'up' | 'down') => {
    if (f.prior == null) return null
    const diff = f.total - f.prior
    const good = better === 'up' ? diff >= 0 : diff <= 0
    return <small>{data?.priorYear}: {dollars(f.prior)} <span className={`nowrap ${good ? '' : 'over'}`}>({diff >= 0 ? '+' : '−'}{dollars(Math.abs(diff))})</span></small>
  }

  return (
    <>
      <section>
        <div className="chart-head">
          <h2>{year}{range ? <span className="muted">{range}</span> : null}</h2>
          <div className="toolbar tight">
            <select value={year} aria-label="Year" onChange={(e) => setYear(e.target.value)}>
              {years.map((y) => <option key={y}>{y}</option>)}
            </select>
            <a className="button" href={`api/export.csv?year=${year}`} download>Download {year}</a>
            <a className="button" href="api/export.csv?year=all" download>Download all years</a>
          </div>
        </div>
        {data && (
          <>
            <dl className="figures">
              <div><dt>Income</dt><dd>{dollars(data.figures.income.total)}{compare(data.figures.income, 'up')}</dd></div>
              <div><dt>Spending</dt><dd>{dollars(data.figures.spending.total)}{compare(data.figures.spending, 'down')}</dd></div>
              <div><dt>Left over</dt><dd className={data.figures.leftOver.total < 0 ? 'over' : ''}>{data.figures.leftOver.total < 0 ? '−' : ''}{dollars(Math.abs(data.figures.leftOver.total))}{compare(data.figures.leftOver, 'up')}</dd></div>
              <div><dt>Pre-tax savings</dt><dd>{dollars(data.figures.saved.total)}{compare(data.figures.saved, 'up')}</dd></div>
            </dl>
            <p className="muted">
              {data.priorYear ? `Compared with the same months of ${data.priorYear}. ` : ''}
              The CSV has every transaction (splits as their parts) with money out as negative amounts, the way banks write it.
            </p>
          </>
        )}
      </section>

      {data && (
        <section>
          <div className="chart-head">
            <h2>Spending by category</h2>
            {data.spending.length > 0 && (
              <button className="toggle" onClick={() => setShowMonths(!showMonths)}>{showMonths ? 'Hide months' : 'Show months'}</button>
            )}
          </div>
          {!data.spending.length ? <p className="muted">No spending in {year}.</p> : showMonths && !narrow ? (
            <div className="table-wrap">
              <table className="year-months">
                <thead>
                  <tr><th>Category</th>{data.months.map((m) => <th key={m} className="num">{monthName(year, m)}</th>)}<th className="num">Total</th></tr>
                </thead>
                <tbody>
                  {data.spending.map((r) => (
                    <tr key={r.id}>
                      <td>{r.name}</td>
                      {data.months.map((m) => <td key={m} className="num">{r.months[m] ? dollars(r.months[m]) : ''}</td>)}
                      <td className="num"><strong>{dollars(r.total)}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="year-table">
                <thead>
                  <tr>
                    <th>Category</th><th className="num">{year}</th>
                    <th className="num" title={`Over the ${data.coveredMonths} months your history covers`}>A month</th>
                    {data.priorYear && <th className="num">{data.priorYear}</th>}
                  </tr>
                </thead>
                <tbody>
                  {data.spending.map((r) => (
                    <Fragment key={r.id}>
                      <tr>
                        <td>{r.name}</td>
                        <td className="num">{dollars(r.total)}</td>
                        <td className="num muted">{r.average != null ? dollars(r.average) : '—'}</td>
                        {data.priorYear && <td className="num muted">{r.prior ? dollars(r.prior) : '—'}</td>}
                      </tr>
                      {showMonths && (
                        <tr className="month-list-row">
                          <td colSpan={data.priorYear ? 4 : 3}>
                            <span className="month-list">
                              {data.months.filter((m) => r.months[m]).map((m) => <span key={m}>{monthName(year, m)} {dollars(r.months[m])}</span>)}
                            </span>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td>Total</td><td className="num">{dollars(data.figures.spending.total)}</td>
                    <td className="num">{data.coveredMonths ? dollars(data.figures.spending.total / data.coveredMonths) : '—'}</td>
                    {data.priorYear && <td className="num">{dollars(data.figures.spending.prior ?? 0)}</td>}
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </section>
      )}

      {data && (
        <section>
          <h2>Tax time</h2>
          {!data.tax.length && !data.loanInterest.length && <p className="muted">Nothing in the tax-time categories for {year}.</p>}
          {data.tax.map((t) => (
            <div className="line" key={t.name}><span>{t.name}</span><span>{money(t.total)}</span></div>
          ))}
          {data.loanInterest.map((l) => (
            <div className="line" key={l.id}>
              <span>{l.name} interest <span className="muted">(estimate at {l.apr}%)</span></span><span>{money(l.estimate)}</span>
            </div>
          ))}
          {data.loanInterest.length > 0 && <p className="muted small">Loan interest is estimated from each month's balance and the rate. Your lender's year-end statement (a 1098 for a mortgage) has the real figure.</p>}
          {data.giving.length > 0 && (
            <details>
              <summary>Taxes & Giving, {data.giving.length} {data.giving.length === 1 ? 'transaction' : 'transactions'}</summary>
              {data.giving.map((g, i) => (
                <div className="line" key={i}>
                  <span>{g.description}<span className="small muted"> · {shortDate(g.date)}{g.account ? ` · ${g.account}` : ''}{g.notes ? ` · ${g.notes}` : ''}</span></span>
                  <span>{money(g.amount)}</span>
                </div>
              ))}
            </details>
          )}
        </section>
      )}
    </>
  )
}
