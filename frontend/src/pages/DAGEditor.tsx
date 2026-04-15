import { useEffect, useState, useRef } from 'react'
import { api } from '../services/api'

interface ModelStatus {
  has_model: boolean
  model_filename: string | null
  calculation_status: string
  last_calculated_at: string | null
}

interface CalcResult {
  success: boolean
  nodes_calculated: number
  errors: string[]
  outputs: Record<string, unknown>
}

interface Props { projectId: string }

function DAGEditor({ projectId }: Props) {
  const [status, setStatus] = useState<ModelStatus | null>(null)
  const [outputs, setOutputs] = useState<Record<string, unknown>>({})
  const [calculating, setCalculating] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [showMappings, setShowMappings] = useState(false)
  const [mappings, setMappings] = useState<Record<string, string>>({})
  const fileRef = useRef<HTMLInputElement>(null)

  const modelBase = `/projects/${projectId}/model`

  useEffect(() => {
    api.get<ModelStatus>(`${modelBase}/status`).then(setStatus).catch(() => {})
    api.get<{ outputs: Record<string, unknown> }>(`${modelBase}/outputs`).then((r) => setOutputs(r.outputs ?? {})).catch(() => {})
    api.get<Record<string, string>>(`${modelBase}/input-mappings`).then(setMappings).catch(() => {})
  }, [projectId])

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const token = localStorage.getItem('masteko_dev_user')
        ? `dev-${JSON.parse(localStorage.getItem('masteko_dev_user')!).email}`
        : ''
      const formData = new FormData()
      formData.append('file', file)
      const resp = await fetch(`/api/projects/${projectId}/model/upload`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      })
      if (!resp.ok) throw new Error('Upload failed')
      setMessage({ text: `Model uploaded: ${file.name}`, type: 'success' })
      api.get<ModelStatus>(`${modelBase}/status`).then(setStatus)
    } catch {
      setMessage({ text: 'Upload failed', type: 'error' })
    } finally {
      setUploading(false)
      setTimeout(() => setMessage(null), 5000)
    }
  }

  const handleCalculate = async () => {
    setCalculating(true)
    setMessage(null)
    try {
      const result = await api.post<CalcResult>(`/projects/${projectId}/calculate`, {})
      if (result.success) {
        setMessage({ text: `Calculation complete.`, type: 'success' })
        setOutputs(result.outputs)
        api.get<ModelStatus>(`${modelBase}/status`).then(setStatus)
      } else {
        setMessage({ text: `Calculation failed: ${result.errors.join(', ')}`, type: 'error' })
      }
    } catch (e) {
      setMessage({ text: `Error: ${e}`, type: 'error' })
    } finally {
      setCalculating(false)
      setTimeout(() => setMessage(null), 10000)
    }
  }

  const handleSaveMappings = async () => {
    await api.post(`${modelBase}/input-mappings`, mappings)
    setMessage({ text: 'Input mappings saved.', type: 'success' })
    setTimeout(() => setMessage(null), 3000)
  }

  return (
    <div>
      {message && (
        <div className={`mb-4 rounded p-3 text-sm ${message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          {message.text}
        </div>
      )}

      <h2 className="mb-4 text-lg font-semibold text-gray-900">Calculation Engine</h2>

      {/* Model upload */}
      <div className="mb-6 rounded border bg-white p-4">
        <h3 className="mb-2 font-medium">Excel Model</h3>
        {status?.has_model ? (
          <p className="mb-2 text-sm text-green-700">Model loaded: <strong>{status.model_filename}</strong></p>
        ) : (
          <div className="mb-2 rounded bg-blue-50 p-3 text-xs text-blue-800">
            <p className="font-medium">How it works:</p>
            <ol className="mt-1 ml-4 list-decimal space-y-0.5">
              <li>Upload your .xlsx financial model (the one with all the formulas)</li>
              <li>Configure input mappings: which assumptions map to which Excel cells</li>
              <li>Click "Calculate" — your assumptions are injected, LibreOffice recalculates all formulas</li>
              <li>Outputs (Annual Summary, Sources & Uses, etc.) are extracted and displayed below</li>
              <li>Change any assumption, recalculate, and see updated results instantly</li>
            </ol>
          </div>
        )}
        <div className="flex gap-2">
          <input ref={fileRef} type="file" accept=".xlsx" className="text-sm" />
          <button onClick={handleUpload} disabled={uploading}
            className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50">
            {uploading ? 'Uploading...' : 'Upload Model'}
          </button>
        </div>
      </div>

      {/* Input Mappings */}
      <div className="mb-6 rounded border bg-white p-4">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="font-medium">Input Mappings <span className="text-xs text-gray-400">({Object.keys(mappings).length} configured)</span></h3>
          <button onClick={() => setShowMappings(!showMappings)} className="text-xs text-blue-600">{showMappings ? 'Hide' : 'Configure'}</button>
        </div>
        {showMappings && (
          <div className="mt-3">
            <p className="mb-2 text-xs text-gray-500">Map assumption keys → Excel cell references. Format: <code>key = SheetName!CellRef</code> or just <code>key = CellRef</code> (defaults to Inputs & Assumptions sheet).</p>
            <textarea
              className="mb-2 w-full rounded border p-2 font-mono text-xs"
              rows={12}
              value={Object.entries(mappings).map(([k, v]) => `${k} = ${v}`).join('\n')}
              onChange={(e) => {
                const m: Record<string, string> = {}
                e.target.value.split('\n').forEach((line) => {
                  const eq = line.indexOf('=')
                  if (eq > 0) {
                    const key = line.slice(0, eq).trim()
                    const val = line.slice(eq + 1).trim()
                    if (key && val) m[key] = val
                  }
                })
                setMappings(m)
              }}
            />
            <button onClick={handleSaveMappings} className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white">Save Mappings</button>
          </div>
        )}
      </div>

      {/* Calculate button */}
      <div className="mb-6 rounded border bg-white p-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium">Run Calculation</h3>
            <p className="text-xs text-gray-500">
              Status: <span className={status?.calculation_status === 'done' ? 'font-medium text-green-600' : status?.calculation_status === 'error' ? 'font-medium text-red-600' : 'text-gray-500'}>
                {status?.calculation_status ?? 'idle'}
              </span>
              {status?.last_calculated_at && ` — Last run: ${new Date(status.last_calculated_at).toLocaleString()}`}
            </p>
          </div>
          <button onClick={handleCalculate} disabled={calculating || !status?.has_model}
            className="rounded bg-green-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50">
            {calculating ? 'Calculating...' : 'Calculate'}
          </button>
        </div>
      </div>

      {/* Outputs */}
      {Object.keys(outputs).length > 0 && (
        <div>
          <h3 className="mb-3 text-lg font-semibold text-gray-900">Results</h3>

          {'construction_loan' in outputs && (
            <OutputCard title="Construction Loan Parameters" data={outputs.construction_loan as Record<string, unknown>} />
          )}
          {'permanent_loan' in outputs && (
            <OutputCard title="Permanent Financing" data={outputs.permanent_loan as Record<string, unknown>} />
          )}
          {'budget_summary' in outputs && (
            <OutputTable title="Budget Summary" rows={outputs.budget_summary as Record<string, unknown>[]} />
          )}
          {'sources_and_uses' in outputs && (
            <OutputTable title="Sources & Uses — Construction" rows={outputs.sources_and_uses as Record<string, unknown>[]} />
          )}
          {'annual_summary' in outputs && (
            <OutputTable title="Annual Operating Summary" rows={outputs.annual_summary as Record<string, unknown>[]} />
          )}
        </div>
      )}
    </div>
  )
}

function OutputCard({ title, data }: { title: string; data: Record<string, unknown> }) {
  return (
    <div className="mb-4 rounded border bg-white p-4">
      <h4 className="mb-2 font-medium">{title}</h4>
      <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
        {Object.entries(data).filter(([, v]) => v != null).map(([k, v]) => (
          <div key={k} className="flex justify-between border-b py-1.5">
            <span className="capitalize text-gray-500">{k.replace(/_/g, ' ')}</span>
            <span className="font-medium tabular-nums">
              {typeof v === 'number' ? (Math.abs(v) >= 1000 ? `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : v.toLocaleString(undefined, { maximumFractionDigits: 4 })) : String(v)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function OutputTable({ title, rows }: { title: string; rows: Record<string, unknown>[] }) {
  if (!rows || rows.length === 0) return null
  const cols = Object.keys(rows[0] ?? {})
  const filtered = rows.filter((r) => Object.values(r).some((v) => v !== null))
  if (filtered.length === 0) return null

  return (
    <details className="mb-4 rounded border bg-white" open>
      <summary className="cursor-pointer border-b px-4 py-3 font-medium hover:bg-gray-50">{title} ({filtered.length} rows)</summary>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
              {cols.map((c) => <th key={c} className="whitespace-nowrap px-3 py-2">{c.replace(/_/g, ' ')}</th>)}
            </tr>
          </thead>
          <tbody>
            {filtered.map((row, i) => (
              <tr key={i} className="border-b last:border-0 hover:bg-gray-50">
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
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

export default DAGEditor
