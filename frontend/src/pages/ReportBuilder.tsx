import { useEffect, useState } from 'react'
import { api } from '../services/api'

interface Props { projectId: string }

function ReportBuilder({ projectId }: Props) {
  const [outputs, setOutputs] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get<{ outputs: Record<string, unknown> }>(`/projects/${projectId}/model/outputs`)
      .then((r) => setOutputs(r.outputs ?? {}))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [projectId])

  if (loading) return <p className="text-gray-500">Loading outputs...</p>

  const hasOutputs = Object.keys(outputs).length > 0

  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold text-gray-900">Reports</h2>

      {!hasOutputs ? (
        <div className="rounded border-2 border-dashed border-gray-300 p-12 text-center">
          <p className="text-gray-500">No calculated outputs yet.</p>
          <p className="mt-1 text-sm text-gray-400">Go to the DAG tab, upload your model, and run a calculation first.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Executive Summary */}
          <div className="rounded border bg-white p-6">
            <h3 className="mb-4 text-lg font-bold text-gray-900">Executive Summary</h3>
            <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
              {'construction_loan' in outputs && (() => {
                const cl = outputs.construction_loan as Record<string, unknown>
                return <>
                  <SummaryCard label="Total Project Cost" value={fmtCurrency(cl.total_project_cost)} />
                  <SummaryCard label="Max Loan Amount" value={fmtCurrency(cl.max_loan_amount)} />
                  <SummaryCard label="LTC" value={fmtPct(cl.ltc)} />
                </>
              })()}
              {'permanent_loan' in outputs && (() => {
                const pl = outputs.permanent_loan as Record<string, unknown>
                return <>
                  <SummaryCard label="Permanent Loan" value={fmtCurrency(pl.loan_amount)} />
                  <SummaryCard label="Interest Rate" value={fmtPct(pl.interest_rate)} />
                  <SummaryCard label="Monthly Payment" value={fmtCurrency(pl.monthly_payment)} />
                  <SummaryCard label="Amortization" value={`${pl.amortization_years} yrs`} />
                </>
              })()}
            </div>
          </div>

          {/* Budget Summary */}
          {'budget_summary' in outputs && (
            <ReportTable title="Construction Budget Summary" rows={outputs.budget_summary as Record<string, unknown>[]} />
          )}

          {/* Sources & Uses */}
          {'sources_and_uses' in outputs && (
            <ReportTable title="Sources & Uses — Construction Period" rows={outputs.sources_and_uses as Record<string, unknown>[]} />
          )}

          {/* Annual Summary */}
          {'annual_summary' in outputs && (
            <ReportTable title="Annual Operating Summary (5-Year)" rows={outputs.annual_summary as Record<string, unknown>[]} />
          )}

          {/* Print button */}
          <div className="text-center">
            <button onClick={() => window.print()} className="rounded bg-gray-800 px-6 py-2.5 text-sm font-medium text-white hover:bg-gray-700">
              Print Report
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-gray-50 p-4">
      <p className="text-xs font-medium uppercase text-gray-500">{label}</p>
      <p className="mt-1 text-xl font-bold text-gray-900">{value}</p>
    </div>
  )
}

function ReportTable({ title, rows }: { title: string; rows: Record<string, unknown>[] }) {
  if (!rows || rows.length === 0) return null
  const cols = Object.keys(rows[0] ?? {})
  const filtered = rows.filter((r) => Object.values(r).some((v) => v !== null))
  if (filtered.length === 0) return null

  return (
    <div className="rounded border bg-white">
      <h3 className="border-b px-4 py-3 font-bold">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
              {cols.map((c) => <th key={c} className="whitespace-nowrap px-3 py-2">{c.replace(/_/g, ' ')}</th>)}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, i) => {
              const isHeader = typeof row[cols[0]!] === 'string' && (row[cols[0]!] as string).toUpperCase() === row[cols[0]!]
              return (
                <tr key={i} className={`border-b last:border-0 ${isHeader ? 'bg-gray-50 font-semibold' : 'hover:bg-gray-50'}`}>
                  {cols.map((c) => (
                    <td key={c} className="whitespace-nowrap px-3 py-1.5 tabular-nums">
                      {typeof row[c] === 'number'
                        ? Math.abs(Number(row[c])) >= 100
                          ? Number(row[c]).toLocaleString(undefined, { maximumFractionDigits: 0 })
                          : Number(row[c]).toLocaleString(undefined, { maximumFractionDigits: 4 })
                        : String(row[c] ?? '')}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function fmtCurrency(v: unknown): string {
  if (v == null) return '—'
  return `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function fmtPct(v: unknown): string {
  if (v == null) return '—'
  return `${(Number(v) * 100).toFixed(2)}%`
}

export default ReportBuilder
