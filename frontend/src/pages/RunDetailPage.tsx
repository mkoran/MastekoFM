import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

interface RunDetail {
  id: string
  project_id: string
  assumption_pack_id: string
  assumption_pack_version: number
  model_id: string
  model_version: number
  output_template_id: string
  output_template_version: number
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  output_storage_path: string | null
  output_download_url: string | null
  output_drive_file_id: string | null
  warnings: string[]
  error: string | null
  triggered_by: string
  retry_of: string | null
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-700',
}

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>()
  const { token } = useAuth()
  const [run, setRun] = useState<RunDetail | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = () => {
    if (!token || !runId) return
    api.get<RunDetail>(`/runs/${runId}`).then(setRun).catch((e) => setError(String(e)))
  }
  useEffect(load, [token, runId])

  const handleRetry = async () => {
    if (!runId) return
    setRetrying(true)
    setError(null)
    try {
      const newRun = await api.post<RunDetail>(`/runs/${runId}/retry`, {})
      window.location.href = `/runs/${newRun.id}`
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Retry failed')
    } finally {
      setRetrying(false)
    }
  }

  if (!run) {
    return (
      <div className="p-6 text-sm text-gray-500">
        {error ? <p className="text-red-600">{error}</p> : 'Loading run…'}
      </div>
    )
  }

  const driveOutputUrl = run.output_drive_file_id
    ? `https://docs.google.com/spreadsheets/d/${run.output_drive_file_id}/edit`
    : null

  return (
    <div className="p-6">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <h1 className="text-xl font-semibold text-gray-900">Run {run.id.slice(0, 8)}…</h1>
            <span className={`rounded px-2 py-0.5 text-xs ${STATUS_COLOR[run.status] || 'bg-gray-100'}`}>
              {run.status}
            </span>
          </div>
          <p className="text-xs text-gray-500">
            Started {new Date(run.started_at).toLocaleString()}{' '}
            {run.completed_at ? `· completed in ${run.duration_ms}ms` : ''}
            {run.retry_of ? <> · retry of <Link to={`/runs/${run.retry_of}`} className="text-blue-600 hover:underline">{run.retry_of.slice(0, 8)}…</Link></> : null}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {(run.status === 'failed' || run.status === 'completed') && (
            <button
              onClick={handleRetry}
              disabled={retrying}
              className="rounded border border-blue-600 px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 disabled:opacity-50"
            >
              {retrying ? 'Retrying…' : 'Retry with same composition'}
            </button>
          )}
          <Link to="/runs" className="text-sm text-blue-600 hover:underline">← All runs</Link>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Composition */}
        <div className="rounded border bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">Composition</h2>
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-xs font-semibold text-gray-500">
                <span className="rounded bg-yellow-100 px-1.5 py-0.5 text-yellow-800">Inputs</span>
              </dt>
              <dd className="mt-1 text-gray-700">{run.assumption_pack_id} <span className="text-xs text-gray-500">v{run.assumption_pack_version}</span></dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-gray-500">
                <span className="rounded bg-blue-100 px-1.5 py-0.5 text-blue-800">Model</span>
              </dt>
              <dd className="mt-1 text-gray-700">{run.model_id} <span className="text-xs text-gray-500">v{run.model_version}</span></dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-gray-500">
                <span className="rounded bg-green-100 px-1.5 py-0.5 text-green-800">OutputTemplate</span>
              </dt>
              <dd className="mt-1 text-gray-700">{run.output_template_id} <span className="text-xs text-gray-500">v{run.output_template_version}</span></dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-gray-500">Project</dt>
              <dd className="mt-1"><Link to={`/excel-projects/${run.project_id}`} className="text-sm text-blue-600 hover:underline">{run.project_id}</Link></dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-gray-500">Triggered by</dt>
              <dd className="mt-1 text-sm text-gray-700">{run.triggered_by}</dd>
            </div>
          </dl>
        </div>

        {/* Output */}
        <div className="rounded border bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">Output artifact</h2>
          {run.status === 'completed' && run.output_download_url ? (
            <div className="space-y-3">
              <a
                href={run.output_download_url}
                target="_blank" rel="noreferrer"
                className="inline-block rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
              >
                Download .xlsx ↓
              </a>
              {driveOutputUrl && (
                <div>
                  <a href={driveOutputUrl} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline">
                    Open in Google Sheets ↗
                  </a>
                </div>
              )}
              <p className="text-xs text-gray-500">{run.output_storage_path}</p>
            </div>
          ) : run.status === 'failed' ? (
            <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
              <p className="font-semibold">Run failed</p>
              <p className="mt-1">{run.error || 'unknown error'}</p>
            </div>
          ) : (
            <p className="text-sm text-gray-500">No output yet.</p>
          )}

          {run.warnings.length > 0 && (
            <div className="mt-4 rounded border border-yellow-200 bg-yellow-50 px-3 py-2 text-xs text-yellow-800">
              <p className="font-semibold">Warnings:</p>
              <ul className="mt-1 list-inside list-disc">
                {run.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
