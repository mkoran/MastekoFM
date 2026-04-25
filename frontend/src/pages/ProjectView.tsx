import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import NewRunModal from '../components/NewRunModal'

interface ExcelProject {
  id: string
  name: string
  code_name: string
  description: string
  template_id: string
  template_name: string
  template_version_pinned: number
  status: string
}

interface AssumptionPackSummary {
  id: string
  name: string
  code_name: string
  status: string
  version: number
  last_run_at: string | null
  last_run_status: string | null
  created_at: string
}

interface ScenarioDetail extends AssumptionPackSummary {
  description: string
  storage_kind: 'gcs' | 'drive_xlsx'
  storage_path: string | null
  drive_file_id: string | null
  edit_url: string | null
  size_bytes: number
  last_run: {
    run_id: string
    started_at: string
    completed_at: string
    status: string
    output_storage_path: string
    output_download_url: string
    duration_ms: number
  } | null
}

interface RunRecord {
  id: string
  status: string
  started_at: string
  completed_at: string | null
  duration_ms: number | null
  template_version_used?: number
  scenario_version_used?: number
  input_storage_kind?: string | null
  input_download_url?: string | null
  output_download_url: string | null
  warnings: string[]
  error: string | null
}

export default function ExcelProjectView() {
  const { projectId } = useParams<{ projectId: string }>()
  const { token } = useAuth()
  const [project, setProject] = useState<ExcelProject | null>(null)
  const [scenarios, setScenarios] = useState<AssumptionPackSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selected, setSelected] = useState<ScenarioDetail | null>(null)
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [calculating, setCalculating] = useState(false)
  const [newName, setNewName] = useState('')
  const [cloneFromId, setCloneFromId] = useState('')
  const [newStorageKind, setNewStorageKind] = useState<'' | 'gcs' | 'drive_xlsx'>('')
  const uploadFileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [showRunModal, setShowRunModal] = useState(false)

  const loadProject = () => {
    if (!projectId || !token) return  // wait until auth token is ready
    api.get<ExcelProject>(`/projects/${projectId}`).then(setProject).catch(() => setProject(null))
    api.get<AssumptionPackSummary[]>(`/projects/${projectId}/assumption-packs`).then((s) => {
      setScenarios(s)
      if (s.length > 0 && !selectedId && s[0]) setSelectedId(s[0].id)
    }).catch(() => setScenarios([]))
  }
  useEffect(loadProject, [projectId, token])

  const loadSelected = () => {
    if (!projectId || !selectedId || !token) return
    api.get<ScenarioDetail>(`/projects/${projectId}/assumption-packs/${selectedId}`).then(setSelected).catch(() => setSelected(null))
    api.get<RunRecord[]>(`/projects/${projectId}/assumption-packs/${selectedId}/runs`).then(setRuns).catch(() => setRuns([]))
  }
  useEffect(loadSelected, [projectId, selectedId, token])

  const handleCreateScenario = async () => {
    if (!newName) {
      setMessage({ text: 'Name is required', type: 'error' })
      return
    }
    try {
      const body: { name: string; clone_from_id?: string; storage_kind?: string } = { name: newName }
      if (cloneFromId) body.clone_from_id = cloneFromId
      if (newStorageKind) body.storage_kind = newStorageKind
      await api.post(`/projects/${projectId}/assumption-packs`, body)
      setNewName('')
      setCloneFromId('')
      setNewStorageKind('')
      setMessage({ text: 'Scenario created', type: 'success' })
      loadProject()
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'Failed', type: 'error' })
    } finally {
      setTimeout(() => setMessage(null), 4000)
    }
  }

  const handleCalculate = async () => {
    if (!projectId || !selectedId) return
    setCalculating(true)
    setMessage(null)
    try {
      const run = await api.post<RunRecord>(`/projects/${projectId}/assumption-packs/${selectedId}/calculate`, {})
      setMessage({
        text: `Calculated in ${run.duration_ms}ms. ${run.warnings.length ? `Warnings: ${run.warnings.join('; ')}` : 'No warnings.'}`,
        type: 'success',
      })
      loadSelected()
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'Calc failed', type: 'error' })
    } finally {
      setCalculating(false)
      setTimeout(() => setMessage(null), 8000)
    }
  }

  const handleUploadNewVersion = async () => {
    if (!projectId || !selectedId) return
    const file = uploadFileRef.current?.files?.[0]
    if (!file) {
      setMessage({ text: 'Pick an .xlsx file', type: 'error' })
      return
    }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const resp = await fetch(`/api/projects/${projectId}/assumption-packs/${selectedId}/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({ detail: resp.statusText }))
        throw new Error(body.detail || 'Upload failed')
      }
      setMessage({ text: 'New inputs version uploaded', type: 'success' })
      if (uploadFileRef.current) uploadFileRef.current.value = ''
      loadSelected()
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'Upload failed', type: 'error' })
    } finally {
      setUploading(false)
      setTimeout(() => setMessage(null), 6000)
    }
  }

  const inputsEditUrl = selected?.edit_url ?? null
  const isDriveScenario = selected?.storage_kind === 'drive_xlsx'
  const downloadOutputUrl = selected?.last_run?.output_download_url

  if (!project) {
    return <div className="p-6 text-gray-500">Loading project…</div>
  }

  return (
    <div className="p-6">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">{project.name}</h1>
          <p className="mt-1 text-sm text-gray-600">
            Default Model: <span className="font-medium">{project.template_name}</span> (pinned to v{project.template_version_pinned})
          </p>
          {project.description && <p className="mt-1 text-xs text-gray-500">{project.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowRunModal(true)}
            className="rounded bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700"
          >
            + New Run
          </button>
          <Link to="/projects" className="text-sm text-blue-600 hover:underline">← All Projects</Link>
        </div>
      </div>

      {showRunModal && projectId && (
        <NewRunModal projectId={projectId} onClose={() => setShowRunModal(false)} />
      )}

      {message && (
        <div className={`mb-4 rounded px-4 py-2 ${message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Scenario list */}
        <div className="rounded border bg-white">
          <div className="border-b px-3 py-2 text-sm font-semibold text-gray-700">Scenarios</div>
          <ul>
            {scenarios.map((s) => (
              <li key={s.id}>
                <button
                  onClick={() => setSelectedId(s.id)}
                  className={`block w-full px-3 py-2 text-left text-sm hover:bg-gray-50 ${selectedId === s.id ? 'bg-blue-50 font-semibold' : ''}`}
                >
                  <div>{s.name}</div>
                  <div className="text-xs text-gray-500">
                    v{s.version}{s.last_run_status ? ` · last ${s.last_run_status}` : ''}
                  </div>
                </button>
              </li>
            ))}
            {scenarios.length === 0 && <li className="px-3 py-3 text-xs text-gray-500">No scenarios yet.</li>}
          </ul>
          <div className="border-t p-3">
            <div className="mb-2 text-xs font-semibold text-gray-600">New Scenario</div>
            <input
              className="mb-1 w-full rounded border px-2 py-1 text-xs"
              placeholder="Name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <select className="mb-1 w-full rounded border px-2 py-1 text-xs" value={cloneFromId} onChange={(e) => setCloneFromId(e.target.value)}>
              <option value="">Seed from Template</option>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>Clone from: {s.name}</option>
              ))}
            </select>
            <select
              className="mb-1 w-full rounded border px-2 py-1 text-xs"
              value={newStorageKind}
              onChange={(e) => setNewStorageKind(e.target.value as '' | 'gcs' | 'drive_xlsx')}
            >
              <option value="">Storage: use default</option>
              <option value="gcs">Cloud Storage (GCS)</option>
              <option value="drive_xlsx">Google Drive (.xlsx)</option>
            </select>
            <button onClick={handleCreateScenario} className="w-full rounded bg-blue-600 px-3 py-1.5 text-xs text-white hover:bg-blue-700">
              Create
            </button>
          </div>
        </div>

        {/* Scenario detail + actions */}
        <div className="rounded border bg-white lg:col-span-2">
          {selected ? (
            <div className="p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold">{selected.name}</h2>
                  <div className="text-xs text-gray-500">
                    v{selected.version} · {Math.round(selected.size_bytes / 1024)} KB
                  </div>
                </div>
                <button
                  onClick={handleCalculate}
                  disabled={calculating}
                  className="rounded bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700 disabled:opacity-50"
                >
                  {calculating ? 'Calculating…' : '▶ Calculate'}
                </button>
              </div>
              {selected.description && <p className="mb-3 text-sm text-gray-600">{selected.description}</p>}

              <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="rounded border bg-gray-50 p-3">
                  <div className="mb-1 flex items-center justify-between">
                    <div className="text-xs font-semibold text-gray-600">Inputs file (I_ tabs only)</div>
                    <span className={`rounded px-2 py-0.5 text-[10px] ${isDriveScenario ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'}`}>
                      {isDriveScenario ? 'Drive' : 'GCS'}
                    </span>
                  </div>
                  {isDriveScenario ? (
                    <>
                      {inputsEditUrl ? (
                        <a href={inputsEditUrl} target="_blank" rel="noreferrer" className="inline-block rounded bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700">
                          Edit in Google Sheets →
                        </a>
                      ) : (
                        <p className="text-xs text-gray-500">Drive file not available.</p>
                      )}
                      <div className="mt-2 text-xs text-gray-500">Opens in Sheets (Office mode). Save in Sheets → Calculate → new output.</div>
                    </>
                  ) : (
                    <>
                      {inputsEditUrl ? (
                        <a href={inputsEditUrl} target="_blank" rel="noreferrer" className="block text-sm text-blue-600 hover:underline">
                          Download current inputs .xlsx
                        </a>
                      ) : (
                        <p className="text-xs text-gray-500">No inputs file available.</p>
                      )}
                      <div className="mt-2 text-xs text-gray-500">To edit: download, open in Excel / Sheets, modify the I_ tabs, then upload below.</div>
                    </>
                  )}
                  <div className="mt-2 flex items-center gap-2">
                    <input ref={uploadFileRef} type="file" accept=".xlsx" className="text-xs" />
                    <button
                      onClick={handleUploadNewVersion}
                      disabled={uploading}
                      className="rounded border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                    >
                      {uploading ? 'Uploading…' : 'Upload new version'}
                    </button>
                  </div>
                </div>

                <div className="rounded border bg-gray-50 p-3">
                  <div className="mb-1 text-xs font-semibold text-gray-600">Latest output</div>
                  {downloadOutputUrl ? (
                    <>
                      <a href={downloadOutputUrl} target="_blank" rel="noreferrer" className="block text-sm text-blue-600 hover:underline">
                        Download latest output .xlsx
                      </a>
                      <div className="mt-1 text-xs text-gray-500">
                        {selected.last_run?.status} · {selected.last_run?.duration_ms}ms · {selected.last_run?.completed_at && new Date(selected.last_run.completed_at).toLocaleString()}
                      </div>
                    </>
                  ) : (
                    <div className="text-sm text-gray-500">No calculation yet — click Calculate.</div>
                  )}
                </div>
              </div>

              {runs.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-gray-700">Run history</h3>
                  <table className="w-full text-xs">
                    <thead className="bg-gray-50 text-left text-gray-600">
                      <tr>
                        <th className="px-2 py-1">Started</th>
                        <th className="px-2 py-1">Status</th>
                        <th className="px-2 py-1">Duration</th>
                        <th className="px-2 py-1">Tpl v</th>
                        <th className="px-2 py-1">Scn v</th>
                        <th className="px-2 py-1">Inputs used</th>
                        <th className="px-2 py-1">Output</th>
                        <th className="px-2 py-1">Warnings</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runs.map((r) => (
                        <tr key={r.id} className="border-t">
                          <td className="px-2 py-1">{new Date(r.started_at).toLocaleString()}</td>
                          <td className="px-2 py-1">{r.status}{r.error && ` · ${r.error}`}</td>
                          <td className="px-2 py-1">{r.duration_ms ?? '—'}ms</td>
                          <td className="px-2 py-1">{r.template_version_used ?? '—'}</td>
                          <td className="px-2 py-1">{r.scenario_version_used ?? '—'}</td>
                          <td className="px-2 py-1">
                            {r.input_download_url ? (
                              <a href={r.input_download_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                                {r.input_storage_kind === 'drive_xlsx' ? 'Sheets' : '.xlsx'}
                              </a>
                            ) : '—'}
                          </td>
                          <td className="px-2 py-1">
                            {r.output_download_url && (
                              <a href={r.output_download_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                                .xlsx
                              </a>
                            )}
                          </td>
                          <td className="px-2 py-1 text-gray-500">
                            {r.warnings && r.warnings.length > 0 ? r.warnings.join('; ') : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <div className="p-6 text-sm text-gray-500">Pick a scenario on the left or create one.</div>
          )}
        </div>
      </div>
    </div>
  )
}
