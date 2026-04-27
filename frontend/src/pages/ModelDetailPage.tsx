import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

/**
 * Sprint G2: per-Model dashboard.
 *   - Hero: Drive folder URL + Open in Sheets + I_/O_/calc tab counts
 *   - Version history: every {code}_v{NNN}.xlsx in the Model folder, with
 *     timestamps + open/download links
 *   - Calculations (query view): runs filtered to this Model
 */

interface ModelDetail {
  id: string
  name: string
  code_name: string
  description: string
  workspace_id: string | null
  version: number
  input_tabs: string[]
  output_tabs: string[]
  calc_tabs: string[]
  drive_folder_id: string | null
  drive_folder_url: string | null
  drive_file_id: string | null
  drive_url: string | null
  size_bytes: number
  archived: boolean
  uploaded_by_email: string | null
  created_at: string
  updated_at: string
}

interface Revision {
  version: number
  file_id: string
  name: string
  ext: string
  size_bytes: number | null
  modified_time: string
  edit_url: string | null
  download_url: string | null
}

interface RunSummary {
  id: string
  project_id: string
  project_name: string | null
  assumption_pack_id: string
  assumption_pack_name: string | null
  output_template_id: string
  output_template_name: string | null
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string
  duration_ms: number | null
  output_download_url: string | null
  triggered_by_email: string | null
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-700',
}

export default function ModelDetailPage() {
  const { modelId } = useParams<{ modelId: string }>()
  const { token } = useAuth()
  const [model, setModel] = useState<ModelDetail | null>(null)
  const [revisions, setRevisions] = useState<Revision[]>([])
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!modelId || !token) return
    api.get<ModelDetail>(`/models/${modelId}`).then(setModel).catch((e) => setError(String(e)))
    api.get<{ revisions: Revision[] }>(`/models/${modelId}/revisions`)
      .then((r) => setRevisions(r.revisions || []))
      .catch(() => setRevisions([]))
    api.get<RunSummary[]>(`/runs?model_id=${modelId}&limit=50`)
      .then(setRuns)
      .catch(() => setRuns([]))
  }, [modelId, token])

  if (!model) {
    return (
      <div className="p-6 text-sm text-gray-500">
        {error ? <p className="text-red-600">{error}</p> : 'Loading model…'}
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold text-gray-900">{model.name}</h1>
            <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">v{model.version}</span>
            {model.archived && (
              <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500 italic">archived</span>
            )}
          </div>
          <p className="mt-1 text-xs text-gray-500">{model.code_name}</p>
          {model.description && <p className="mt-1 text-sm text-gray-700">{model.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          {model.drive_folder_url && (
            <a
              href={model.drive_folder_url}
              target="_blank" rel="noreferrer"
              className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
            >
              📁 Drive folder
            </a>
          )}
          {model.drive_url && (
            <a
              href={model.drive_url}
              target="_blank" rel="noreferrer"
              className="rounded bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700"
            >
              Open latest in Sheets ↗
            </a>
          )}
          <Link to="/models" className="text-sm text-blue-600 hover:underline">← All Models</Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Tab structure */}
        <div className="rounded border bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">Tab structure</h2>
          <dl className="space-y-2 text-sm">
            <div>
              <dt className="text-xs font-semibold text-yellow-800">I_ inputs ({model.input_tabs.length})</dt>
              <dd className="text-xs text-gray-700">{model.input_tabs.join(', ') || '—'}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-blue-800">Calc ({model.calc_tabs.length})</dt>
              <dd className="text-xs text-gray-700">{model.calc_tabs.join(', ') || '—'}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold text-green-800">O_ outputs ({model.output_tabs.length})</dt>
              <dd className="text-xs text-gray-700">{model.output_tabs.join(', ') || '—'}</dd>
            </div>
          </dl>
        </div>

        {/* Version history */}
        <div className="rounded border bg-white p-4 lg:col-span-2">
          <h2 className="mb-3 flex items-center justify-between text-sm font-semibold text-gray-700">
            <span>Version history</span>
            <span className="text-xs font-normal text-gray-500">{revisions.length} version(s) in Drive</span>
          </h2>
          {revisions.length === 0 ? (
            <p className="text-xs text-gray-500">
              No versions found. {model.drive_folder_id ? 'Drive may not be reachable from this session.' : 'Legacy GCS Model — no Drive folder.'}
            </p>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-gray-50 text-left text-gray-600">
                <tr>
                  <th className="px-2 py-1">Version</th>
                  <th className="px-2 py-1">Filename</th>
                  <th className="px-2 py-1">Modified</th>
                  <th className="px-2 py-1">Size</th>
                  <th className="px-2 py-1"></th>
                </tr>
              </thead>
              <tbody>
                {revisions.map((r) => (
                  <tr key={r.file_id} className="border-t">
                    <td className="px-2 py-1 font-mono">v{String(r.version).padStart(3, '0')}</td>
                    <td className="px-2 py-1 font-mono text-gray-600">{r.name}</td>
                    <td className="px-2 py-1 text-gray-500">{new Date(r.modified_time).toLocaleString()}</td>
                    <td className="px-2 py-1 text-gray-500">{r.size_bytes != null ? `${Math.round(r.size_bytes / 1024)} KB` : '—'}</td>
                    <td className="px-2 py-1 space-x-2">
                      {r.edit_url && <a href={r.edit_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">Open</a>}
                      {r.download_url && <a href={r.download_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">↓</a>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Calculations (query view: Runs that used this Model) */}
      <div className="mt-4 rounded border bg-white p-4">
        <h2 className="mb-3 flex items-center justify-between text-sm font-semibold text-gray-700">
          <span>Calculations (Runs using this Model)</span>
          <Link to={`/runs?model_id=${model.id}`} className="text-xs font-normal text-blue-600 hover:underline">
            All in /runs →
          </Link>
        </h2>
        {runs.length === 0 ? (
          <p className="text-xs text-gray-500">No Runs have used this Model yet.</p>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-gray-50 text-left text-gray-600">
              <tr>
                <th className="px-2 py-1">Started</th>
                <th className="px-2 py-1">Status</th>
                <th className="px-2 py-1">Duration</th>
                <th className="px-2 py-1">Project</th>
                <th className="px-2 py-1">Pack</th>
                <th className="px-2 py-1">OutputTemplate</th>
                <th className="px-2 py-1">By</th>
                <th className="px-2 py-1">Output</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="px-2 py-1">
                    <Link to={`/runs/${r.id}`} className="text-blue-600 hover:underline">
                      {new Date(r.started_at).toLocaleString()}
                    </Link>
                  </td>
                  <td className="px-2 py-1">
                    <span className={`rounded px-1.5 py-0.5 ${STATUS_COLOR[r.status] ?? 'bg-gray-100'}`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="px-2 py-1">{r.duration_ms != null ? `${r.duration_ms}ms` : '—'}</td>
                  <td className="px-2 py-1">{r.project_name ?? r.project_id.slice(0, 8) + '…'}</td>
                  <td className="px-2 py-1">{r.assumption_pack_name ?? r.assumption_pack_id.slice(0, 8) + '…'}</td>
                  <td className="px-2 py-1">{r.output_template_name ?? r.output_template_id.slice(0, 8) + '…'}</td>
                  <td className="px-2 py-1">{r.triggered_by_email ?? '—'}</td>
                  <td className="px-2 py-1">
                    {r.output_download_url ? (
                      <a href={r.output_download_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">↓</a>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
