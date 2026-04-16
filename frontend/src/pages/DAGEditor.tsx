import { useEffect, useState, useRef } from 'react'
import { api } from '../services/api'

interface ModelStatus {
  has_model: boolean
  model_filename: string | null
  calculation_status: string
  last_calculated_at: string | null
  has_drive_folder: boolean
  output_drive_link: string | null
  output_filename: string | null
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
  const [driveLink, setDriveLink] = useState<string | null>(null)
  const [calculating, setCalculating] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [showMappings, setShowMappings] = useState(false)
  const [mappings, setMappings] = useState<Record<string, string>>({})
  const [driveFolderId, setDriveFolderId] = useState('')
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
        const out = result.outputs as Record<string, unknown>
        setDriveLink(out.drive_link as string | null)
        setOutputs(out)
        const hasDrive = !!out.drive_link
        setMessage({ text: hasDrive ? 'Calculation complete! File saved to Google Drive.' : 'Calculation complete! Download your Excel file below.', type: 'success' })
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
              <li>Configure input mappings: which assumption keys map to which Excel cells</li>
              <li>Click "Calculate" — assumptions are injected into the Excel, LibreOffice recalculates all formulas</li>
              <li>The completed Excel file is saved to Google Drive with all inputs, calculations, and outputs</li>
              <li>Open the file in Drive/Excel to see the full model with updated numbers</li>
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

      {/* Google Drive Output */}
      <div className="mb-6 rounded border bg-white p-4">
        <h3 className="mb-2 font-medium">Google Drive Output</h3>
        {status?.has_drive_folder ? (
          <p className="text-sm text-green-700">Drive folder configured. Calculated files will be saved to Google Drive.</p>
        ) : (
          <div>
            <p className="mb-2 text-xs text-gray-500">
              Paste a Google Drive folder URL or ID. Calculated Excel files will be saved here.
              Make sure the folder is shared with <code className="bg-gray-100 px-1">560873149926-compute@developer.gserviceaccount.com</code> (Editor).
            </p>
            <div className="flex gap-2">
              <input
                placeholder="Folder ID or URL (e.g. 1z4lyWMMI1LQPicg2h05v9y0RRKTcfn5A)"
                value={driveFolderId}
                onChange={(e) => {
                  let val = e.target.value.trim()
                  const match = val.match(/folders\/([a-zA-Z0-9_-]+)/)
                  if (match) val = match[1] ?? val
                  setDriveFolderId(val)
                }}
                className="flex-1 rounded border px-3 py-1.5 text-sm font-mono"
              />
              <button
                onClick={async () => {
                  if (!driveFolderId) return
                  await api.post(`${modelBase}/drive-folder`, { folder_id: driveFolderId })
                  setMessage({ text: 'Drive folder saved.', type: 'success' })
                  api.get<ModelStatus>(`${modelBase}/status`).then(setStatus)
                  setTimeout(() => setMessage(null), 3000)
                }}
                className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
              >
                Save
              </button>
            </div>
          </div>
        )}
        {status?.output_drive_link && (
          <a href={status.output_drive_link as string} target="_blank" rel="noopener noreferrer"
            className="mt-2 inline-block text-sm text-blue-600 hover:underline">
            Last output: {status.output_filename ?? 'Open in Drive'}
          </a>
        )}
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

      {/* Results — Drive link + summary */}
      {(driveLink || Object.keys(outputs).length > 0) && (
        <div>
          <h3 className="mb-3 text-lg font-semibold text-gray-900">Results</h3>

          <div className="mb-4 rounded border border-green-200 bg-green-50 p-4">
            <h4 className="mb-2 font-medium text-green-900">Excel File Ready</h4>
            <p className="mb-3 text-sm text-green-800">
              Your model has been calculated with {String((outputs as Record<string, unknown>).assumptions_injected ?? 0)} assumptions injected.
              {(outputs as Record<string, unknown>).libreoffice_used ? ' LibreOffice recalculated all formulas.' : ' Formulas preserved (LibreOffice not available).'}
              {' '}Download the complete Excel workbook to see all inputs, calculations, and outputs.
            </p>
            <div className="flex gap-3">
              <button
                onClick={async () => {
                  const token = localStorage.getItem('masteko_dev_user')
                    ? `dev-${JSON.parse(localStorage.getItem('masteko_dev_user')!).email}`
                    : ''
                  const resp = await fetch(`/api/projects/${projectId}/model/download`, {
                    headers: { 'Authorization': `Bearer ${token}` },
                  })
                  if (!resp.ok) { setMessage({ text: 'Download failed', type: 'error' }); return }
                  const blob = await resp.blob()
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = (outputs as Record<string, unknown>).filename as string || 'model.xlsx'
                  a.click()
                  URL.revokeObjectURL(url)
                }}
                className="inline-flex items-center gap-2 rounded bg-green-700 px-4 py-2.5 text-sm font-medium text-white hover:bg-green-800"
              >
                Download Excel File
              </button>
              {driveLink && (
                <a href={driveLink} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded border border-green-700 px-4 py-2.5 text-sm font-medium text-green-700 hover:bg-green-100">
                  Open in Google Drive
                </a>
              )}
            </div>
          </div>

          {Object.keys(outputs).length > 0 && (
            <div className="rounded border bg-white p-4">
              <h4 className="mb-2 font-medium">Calculation Summary</h4>
              <div className="grid grid-cols-2 gap-2 text-sm">
                {Object.entries(outputs).filter(([, v]) => v != null && typeof v !== 'object').map(([k, v]) => (
                  <div key={k} className="flex justify-between border-b py-1">
                    <span className="capitalize text-gray-500">{k.replace(/_/g, ' ')}</span>
                    <span className="font-medium">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default DAGEditor
