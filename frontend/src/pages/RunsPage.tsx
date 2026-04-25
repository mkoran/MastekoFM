import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

interface RunSummary {
  id: string
  project_id: string
  project_name?: string | null
  model_id: string
  model_name?: string | null
  assumption_pack_id: string
  assumption_pack_name?: string | null
  output_template_id: string
  output_template_name?: string | null
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  output_download_url: string | null
  triggered_by: string
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-700',
}

export default function RunsPage() {
  const { token } = useAuth()
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [loading, setLoading] = useState(false)

  const load = () => {
    if (!token) return
    setLoading(true)
    const q = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : ''
    api.get<RunSummary[]>(`/runs${q}`)
      .then(setRuns)
      .catch(() => setRuns([]))
      .finally(() => setLoading(false))
  }

  useEffect(load, [token, statusFilter])

  return (
    <div className="p-6">
      <div className="mb-4 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Runs</h1>
          <p className="mt-1 text-sm text-gray-600">
            Every three-way composition execution. Each Run is immutable.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-600">
            Status:{' '}
            <select className="rounded border px-2 py-1 text-xs" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">all</option>
              <option value="pending">pending</option>
              <option value="running">running</option>
              <option value="completed">completed</option>
              <option value="failed">failed</option>
              <option value="cancelled">cancelled</option>
            </select>
          </label>
          <button onClick={load} className="rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50">
            Refresh
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs text-gray-600">
            <tr>
              <th className="px-3 py-2">Started</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Duration</th>
              <th className="px-3 py-2">Project</th>
              <th className="px-3 py-2">Model</th>
              <th className="px-3 py-2">Inputs</th>
              <th className="px-3 py-2">OutputTemplate</th>
              <th className="px-3 py-2">By</th>
              <th className="px-3 py-2">Output</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id} className="border-t">
                <td className="px-3 py-2 text-xs">
                  <Link to={`/runs/${r.id}`} className="text-blue-600 hover:underline">
                    {new Date(r.started_at).toLocaleString()}
                  </Link>
                </td>
                <td className="px-3 py-2">
                  <span className={`rounded px-2 py-0.5 text-xs ${STATUS_COLOR[r.status] || 'bg-gray-100'}`}>
                    {r.status}
                  </span>
                </td>
                <td className="px-3 py-2 text-xs">{r.duration_ms != null ? `${r.duration_ms}ms` : '—'}</td>
                <td className="px-3 py-2 text-xs text-gray-500">{r.project_id.slice(0, 8)}…</td>
                <td className="px-3 py-2 text-xs text-gray-500">{r.model_id.slice(0, 8)}…</td>
                <td className="px-3 py-2 text-xs text-gray-500">{r.assumption_pack_id.slice(0, 8)}…</td>
                <td className="px-3 py-2 text-xs text-gray-500">{r.output_template_id.slice(0, 8)}…</td>
                <td className="px-3 py-2 text-xs text-gray-500">{r.triggered_by}</td>
                <td className="px-3 py-2">
                  {r.output_download_url ? (
                    <a href={r.output_download_url} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline">
                      .xlsx
                    </a>
                  ) : '—'}
                </td>
              </tr>
            ))}
            {!loading && runs.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center text-sm text-gray-500">
                  No runs yet. Open a project and click "+ New Run".
                </td>
              </tr>
            )}
            {loading && (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center text-sm text-gray-500">Loading…</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
