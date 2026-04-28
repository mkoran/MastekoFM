import { useEffect, useRef, useState } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import NewRunModal from '../components/NewRunModal'

interface ProjectResponse {
  id: string
  name: string
  code_name: string
  description: string
  default_model_id: string | null
  default_model_name: string | null
  default_model_version: number | null
  status: string
  archived: boolean
  drive_folder_url: string | null
}

interface AssumptionPackSummary {
  id: string
  name: string
  code_name: string
  status: string
  version: number
  pack_kind?: 'xlsx' | 'json' | 'pull'   // Sprint I-1
  last_run_at: string | null
  last_run_status: string | null
  created_at: string
}

interface AssumptionPackDetail extends AssumptionPackSummary {
  description: string
  storage_kind: 'gcs' | 'drive_xlsx'
  storage_path: string | null
  drive_folder_id: string | null    // Sprint G1
  drive_folder_url: string | null   // Sprint G1
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

interface PackRevision {
  version: number
  file_id: string
  name: string
  ext: string
  size_bytes: number | null
  modified_time: string
  edit_url: string | null
  download_url: string | null
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

export default function ProjectView() {
  const { projectId } = useParams<{ projectId: string }>()
  const { token } = useAuth()
  const navigate = useNavigate()
  const [project, setProject] = useState<ProjectResponse | null>(null)
  const [packs, setPacks] = useState<AssumptionPackSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selected, setSelected] = useState<AssumptionPackDetail | null>(null)
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [revisions, setRevisions] = useState<PackRevision[]>([])
  const [showRevisions, setShowRevisions] = useState(false)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [calculating, setCalculating] = useState(false)
  const [newName, setNewName] = useState('')
  const [cloneFromId, setCloneFromId] = useState('')
  // Sprint UX-01: drop GCS option per CLAUDE.md doctrine — packs live in Drive only.
  const uploadFileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [showRunModal, setShowRunModal] = useState(false)

  const loadProject = () => {
    if (!projectId || !token) return  // wait until auth token is ready
    api.get<ProjectResponse>(`/projects/${projectId}`).then(setProject).catch(() => setProject(null))
    api.get<AssumptionPackSummary[]>(`/projects/${projectId}/assumption-packs`).then((s) => {
      setPacks(s)
      if (s.length > 0 && !selectedId && s[0]) setSelectedId(s[0].id)
    }).catch(() => setPacks([]))
  }
  useEffect(loadProject, [projectId, token])

  const loadSelected = () => {
    if (!projectId || !selectedId || !token) return
    api.get<AssumptionPackDetail>(`/projects/${projectId}/assumption-packs/${selectedId}`).then(setSelected).catch(() => setSelected(null))
    api.get<RunRecord[]>(`/projects/${projectId}/assumption-packs/${selectedId}/runs`).then(setRuns).catch(() => setRuns([]))
    // Sprint G2: pack revision history (versioned files in Drive folder)
    api.get<{ revisions: PackRevision[] }>(`/projects/${projectId}/assumption-packs/${selectedId}/revisions`)
      .then((r) => setRevisions(r.revisions || []))
      .catch(() => setRevisions([]))
  }
  useEffect(loadSelected, [projectId, selectedId, token])

  const handleCreatePack = async () => {
    if (!newName) {
      setMessage({ text: 'Name is required', type: 'error' })
      return
    }
    try {
      const body: { name: string; clone_from_id?: string } = { name: newName }
      if (cloneFromId) body.clone_from_id = cloneFromId
      await api.post(`/projects/${projectId}/assumption-packs`, body)
      setNewName('')
      setCloneFromId('')
      setMessage({ text: 'AssumptionPack created', type: 'success' })
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
            Default Model:{' '}
            {project.default_model_id ? (
              <>
                <span className="font-medium">{project.default_model_name ?? '—'}</span>
                {project.default_model_version != null && (
                  <span className="text-gray-500"> (pinned to v{project.default_model_version})</span>
                )}
              </>
            ) : (
              <span className="italic text-gray-500">none — pick one in New Run, or set via PUT /api/projects</span>
            )}
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
          {project.drive_folder_url && (
            <a href={project.drive_folder_url} target="_blank" rel="noreferrer" className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50">
              📁 Drive
            </a>
          )}
          {project.archived ? (
            <button
              onClick={async () => {
                await api.post(`/projects/${projectId}/unarchive`, {})
                loadProject()
              }}
              className="rounded border border-blue-300 px-3 py-2 text-sm text-blue-700 hover:bg-blue-50"
            >
              Unarchive
            </button>
          ) : (
            <button
              onClick={async () => {
                if (!confirm(`Archive "${project.name}"? It will be hidden from the Tree and the default Projects list.`)) return
                await api.post(`/projects/${projectId}/archive`, {})
                navigate('/projects')
              }}
              className="rounded border border-yellow-300 px-3 py-2 text-sm text-yellow-700 hover:bg-yellow-50"
            >
              Archive
            </button>
          )}
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

      <div className="space-y-6">
        {/* AssumptionPack list — Sprint G3: full-width above the detail panel for better real estate */}
        <div className="rounded border bg-white">
          <div className="border-b px-3 py-2 text-sm font-semibold text-gray-700">Assumption Packs</div>
          <div className="flex flex-wrap gap-2 p-3">
            {packs.map((s) => (
              <button
                key={s.id}
                onClick={() => setSelectedId(s.id)}
                className={`rounded border px-3 py-2 text-left text-sm hover:bg-gray-50 ${
                  selectedId === s.id
                    ? 'border-blue-400 bg-blue-50 font-semibold'
                    : 'border-gray-200 bg-white'
                }`}
              >
                <div className="flex items-center gap-1">
                  <span>{s.name}</span>
                  {s.pack_kind === 'pull' && (
                    <span
                      className="rounded bg-purple-100 px-1.5 py-0.5 text-[10px] font-medium text-purple-700"
                      title="This pack's values are pulled from external sources at Run time"
                    >
                      🔗 pull
                    </span>
                  )}
                  {s.pack_kind === 'json' && (
                    <span
                      className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-700"
                      title="This pack's values come from a JSON dict (no underlying xlsx)"
                    >
                      json
                    </span>
                  )}
                </div>
                <div className="text-xs text-gray-500">
                  v{s.version}{s.last_run_status ? ` · last ${s.last_run_status}` : ''}
                </div>
              </button>
            ))}
            {packs.length === 0 && <div className="px-1 py-1 text-xs text-gray-500">No packs yet.</div>}
          </div>
          <div className="border-t p-3">
            <div className="mb-2 text-xs font-semibold text-gray-600">New AssumptionPack</div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                className="rounded border px-2 py-1 text-xs"
                placeholder="Name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <select className="rounded border px-2 py-1 text-xs" value={cloneFromId} onChange={(e) => setCloneFromId(e.target.value)}>
                <option value="">Seed from default Model</option>
                {packs.map((s) => (
                  <option key={s.id} value={s.id}>Clone from: {s.name}</option>
                ))}
              </select>
              <button onClick={handleCreatePack} className="rounded bg-blue-600 px-3 py-1.5 text-xs text-white hover:bg-blue-700">
                Create
              </button>
              <p className="text-[10px] text-gray-500">Stored in Drive (.xlsx). Edit in Sheets after creation.</p>
            </div>
          </div>
        </div>

        {/* Scenario detail + actions — full width below the pack list */}
        <div className="rounded border bg-white">
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

              {/* Sprint G2: AssumptionPack revision history (versioned files in Drive) */}
              <div className="mb-4 rounded border bg-white">
                <button
                  onClick={() => setShowRevisions((v) => !v)}
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-semibold text-gray-700 hover:bg-gray-50"
                >
                  <span>📜 Version history ({revisions.length} version{revisions.length === 1 ? '' : 's'} in Drive)</span>
                  <span className="text-xs text-gray-400">{showRevisions ? '▼' : '▶'}</span>
                </button>
                {showRevisions && (
                  <div className="border-t px-3 py-2">
                    {revisions.length === 0 ? (
                      <p className="text-xs text-gray-500">
                        No versioned files found. {selected?.drive_folder_id ? 'Drive may not be reachable from this session.' : 'Legacy pack without per-pack folder.'}
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
                )}
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
            <div className="p-6 text-sm text-gray-500">Pick an AssumptionPack on the left or create one.</div>
          )}
        </div>
      </div>
    </div>
  )
}
