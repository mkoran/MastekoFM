import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

/**
 * Sprint UX-01-14: Run history filterable by Project, by User (email), and by Status.
 * Sorted descending by started_at (default). Project filter syncs to ?project_id=
 * in the URL so the Projects-list "Runs" link can deep-link straight here.
 */

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
  output_drive_file_id: string | null   // Sprint G3 — for Open in Sheets
  output_folder_url: string | null      // Sprint G3 — for Drive folder link
  output_filename: string | null        // Sprint G3 — {ts}_{model}_V{v}_AP{NN}.xlsx
  output_pdf_drive_file_id: string | null  // Sprint D-1 — PDF rendered from xlsx
  output_pdf_filename: string | null       // Sprint D-1 — {ts}_{model}_V{v}_AP{NN}.pdf
  output_narrative_pdf_drive_file_id: string | null  // Sprint D-2 — narrative PDF (from Google Doc)
  output_narrative_pdf_filename: string | null       // Sprint D-2
  triggered_by: string
  triggered_by_email: string | null
}

interface ProjectSummary { id: string; name: string }

const STATUS_COLOR: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-700',
}

export default function RunsPage() {
  const { token } = useAuth()
  const [params, setParams] = useSearchParams()
  const projectIdFilter = params.get('project_id') || ''
  const userFilter = params.get('triggered_by_email') || ''
  const statusFilter = params.get('status') || ''

  const [runs, setRuns] = useState<RunSummary[]>([])
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.get<ProjectSummary[]>('/projects').then(setProjects).catch(() => setProjects([]))
  }, [])

  const load = () => {
    if (!token) return
    setLoading(true)
    const qs: string[] = []
    if (projectIdFilter) qs.push(`project_id=${encodeURIComponent(projectIdFilter)}`)
    if (userFilter) qs.push(`triggered_by_email=${encodeURIComponent(userFilter)}`)
    if (statusFilter) qs.push(`status=${encodeURIComponent(statusFilter)}`)
    qs.push('limit=200')
    api.get<RunSummary[]>(`/runs?${qs.join('&')}`)
      .then(setRuns)
      .catch(() => setRuns([]))
      .finally(() => setLoading(false))
  }

  useEffect(load, [token, projectIdFilter, userFilter, statusFilter])

  const userOptions = useMemo(() => {
    const set = new Set<string>()
    runs.forEach((r) => { if (r.triggered_by_email) set.add(r.triggered_by_email) })
    return Array.from(set).sort()
  }, [runs])

  const setParam = (k: string, v: string) => {
    const next = new URLSearchParams(params)
    if (v) next.set(k, v); else next.delete(k)
    setParams(next, { replace: true })
  }

  const projectName = (id: string) => projects.find((p) => p.id === id)?.name ?? id.slice(0, 8) + '…'

  return (
    <div className="p-6">
      <div className="mb-4 flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Runs</h1>
          <p className="mt-1 text-sm text-gray-600">
            Every three-way composition execution. Each Run is immutable. Sorted newest first.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-gray-600">
            Project
            <select className="ml-1 rounded border px-2 py-1 text-xs" value={projectIdFilter} onChange={(e) => setParam('project_id', e.target.value)}>
              <option value="">all</option>
              {projects.map((p) => (<option key={p.id} value={p.id}>{p.name}</option>))}
            </select>
          </label>
          <label className="text-xs text-gray-600">
            User
            <select className="ml-1 rounded border px-2 py-1 text-xs" value={userFilter} onChange={(e) => setParam('triggered_by_email', e.target.value)}>
              <option value="">all</option>
              {userOptions.map((u) => (<option key={u} value={u}>{u}</option>))}
            </select>
          </label>
          <label className="text-xs text-gray-600">
            Status
            <select className="ml-1 rounded border px-2 py-1 text-xs" value={statusFilter} onChange={(e) => setParam('status', e.target.value)}>
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
              <th className="px-3 py-2">Started ▼</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Duration</th>
              <th className="px-3 py-2">Project</th>
              <th className="px-3 py-2">Model</th>
              <th className="px-3 py-2">AssumptionPack</th>
              <th className="px-3 py-2">OutputTemplate</th>
              <th className="px-3 py-2">By</th>
              <th className="px-3 py-2">Open in Sheets</th>
              <th className="px-3 py-2">📄 PDF</th>
              <th className="px-3 py-2">📜 Narrative</th>
              <th className="px-3 py-2">📁 Folder</th>
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
                <td className="px-3 py-2 text-xs">{r.project_name ?? projectName(r.project_id)}</td>
                <td className="px-3 py-2 text-xs">{r.model_name ?? r.model_id.slice(0, 8) + '…'}</td>
                <td className="px-3 py-2 text-xs">{r.assumption_pack_name ?? r.assumption_pack_id.slice(0, 8) + '…'}</td>
                <td className="px-3 py-2 text-xs">{r.output_template_name ?? r.output_template_id.slice(0, 8) + '…'}</td>
                <td className="px-3 py-2 text-xs text-gray-600">{r.triggered_by_email ?? r.triggered_by}</td>
                <td className="px-3 py-2">
                  {r.output_drive_file_id ? (
                    <a
                      href={`https://docs.google.com/spreadsheets/d/${r.output_drive_file_id}/edit`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-600 hover:underline"
                      title={r.output_filename ?? undefined}
                    >
                      📊 {r.output_filename ?? 'Open'}
                    </a>
                  ) : r.output_download_url ? (
                    <a href={r.output_download_url} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline">
                      .xlsx
                    </a>
                  ) : '—'}
                </td>
                <td className="px-3 py-2">
                  {r.output_pdf_drive_file_id ? (
                    <a
                      href={`https://drive.google.com/file/d/${r.output_pdf_drive_file_id}/view`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-600 hover:underline"
                      title={r.output_pdf_filename ?? 'Open PDF'}
                    >
                      📄 {r.output_pdf_filename ?? 'PDF'}
                    </a>
                  ) : '—'}
                </td>
                <td className="px-3 py-2">
                  {r.output_narrative_pdf_drive_file_id ? (
                    <a
                      href={`https://drive.google.com/file/d/${r.output_narrative_pdf_drive_file_id}/view`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-600 hover:underline"
                      title={r.output_narrative_pdf_filename ?? 'Open narrative PDF'}
                    >
                      📜 Narrative
                    </a>
                  ) : '—'}
                </td>
                <td className="px-3 py-2">
                  {r.output_folder_url ? (
                    <a
                      href={r.output_folder_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-blue-600 hover:underline"
                      title="Open Drive folder for this run"
                    >
                      📁 Folder
                    </a>
                  ) : '—'}
                </td>
              </tr>
            ))}
            {!loading && runs.length === 0 && (
              <tr><td colSpan={12} className="px-3 py-6 text-center text-sm text-gray-500">No runs match the current filters.</td></tr>
            )}
            {loading && (
              <tr><td colSpan={12} className="px-3 py-6 text-center text-sm text-gray-500">Loading…</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
