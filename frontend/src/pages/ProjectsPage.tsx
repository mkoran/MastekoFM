import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'

/**
 * Sprint UX-01: Projects list with the columns Marc requested:
 *   Name · Created By · Created On · Default Model · Last Run · Drive URL · Runs · Status
 * Plus per-column filter inputs (UX-01-10), an archived toggle (UX-01-11),
 * and an inline Archive/Unarchive action (UX-01-13).
 */

interface ProjectSummary {
  id: string
  name: string
  code_name: string
  default_model_id: string | null
  default_model_name: string | null
  status: string
  archived: boolean
  drive_folder_url: string | null
  pack_count: number
  run_count: number
  last_run_at: string | null
  last_run_status: string | null
  created_by: string
  created_by_email: string | null
  created_at: string
}

interface ModelSummary {
  id: string
  name: string
  code_name: string
}

type SortKey = 'name' | 'created_at' | 'last_run_at' | 'run_count' | 'created_by_email'

export default function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [models, setModels] = useState<ModelSummary[]>([])
  const [name, setName] = useState('')
  const [codeName, setCodeName] = useState('')
  const [defaultModelId, setDefaultModelId] = useState('')
  const [description, setDescription] = useState('')
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [creating, setCreating] = useState(false)
  const [showArchived, setShowArchived] = useState(false)

  // Per-column filters (UX-01-10)
  const [fName, setFName] = useState('')
  const [fCreatedBy, setFCreatedBy] = useState('')
  const [fModel, setFModel] = useState('')
  const [fStatus, setFStatus] = useState('')

  const [sortKey, setSortKey] = useState<SortKey>('created_at')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const load = () => {
    const qs = showArchived ? '?include_archived=true' : ''
    api.get<ProjectSummary[]>(`/projects${qs}`).then(setProjects).catch(() => setProjects([]))
    api.get<ModelSummary[]>('/models').then(setModels).catch(() => setModels([]))
  }
  useEffect(load, [showArchived])

  const handleCreate = async () => {
    if (!name) {
      setMessage({ text: 'Name is required', type: 'error' })
      return
    }
    setCreating(true)
    try {
      await api.post('/projects', {
        name,
        code_name: codeName,
        default_model_id: defaultModelId || undefined,
        description,
      })
      setName(''); setCodeName(''); setDescription(''); setDefaultModelId('')
      setMessage({ text: 'Project created', type: 'success' })
      load()
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'Failed to create', type: 'error' })
    } finally {
      setCreating(false)
      setTimeout(() => setMessage(null), 5000)
    }
  }

  const handleArchive = async (id: string, n: string) => {
    if (!confirm(`Archive "${n}"? It will be hidden from the Tree and from the default Projects view.`)) return
    try { await api.post(`/projects/${id}/archive`, {}); load() }
    catch { setMessage({ text: 'Archive failed', type: 'error' }) }
  }
  const handleUnarchive = async (id: string) => {
    try { await api.post(`/projects/${id}/unarchive`, {}); load() }
    catch { setMessage({ text: 'Unarchive failed', type: 'error' }) }
  }

  const filtered = useMemo(() => {
    const lc = (s: string | null | undefined) => (s ?? '').toLowerCase()
    let rows = projects.filter((p) => {
      if (fName && !lc(p.name).includes(fName.toLowerCase()) && !lc(p.code_name).includes(fName.toLowerCase())) return false
      if (fCreatedBy && !lc(p.created_by_email).includes(fCreatedBy.toLowerCase())) return false
      if (fModel && !lc(p.default_model_name).includes(fModel.toLowerCase())) return false
      if (fStatus && p.status !== fStatus) return false
      return true
    })
    rows = [...rows].sort((a, b) => {
      const av = (a[sortKey] ?? '') as string | number
      const bv = (b[sortKey] ?? '') as string | number
      const cmp = av < bv ? -1 : av > bv ? 1 : 0
      return sortDir === 'asc' ? cmp : -cmp
    })
    return rows
  }, [projects, fName, fCreatedBy, fModel, fStatus, sortKey, sortDir])

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    else { setSortKey(k); setSortDir('desc') }
  }

  const SortHeader = ({ k, label }: { k: SortKey; label: string }) => (
    <button onClick={() => toggleSort(k)} className="flex items-center gap-1 hover:text-gray-900">
      {label}
      {sortKey === k && <span className="text-[10px]">{sortDir === 'asc' ? '▲' : '▼'}</span>}
    </button>
  )

  return (
    <div className="p-6">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Projects</h1>
          <p className="mt-1 text-sm text-gray-600">An organizational scope. AssumptionPacks live inside; Runs reference Project + Model + Pack + OutputTemplate.</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-gray-600">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
            Show archived
          </label>
          <Link to="/models" className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50">Manage Models →</Link>
        </div>
      </div>

      {message && (
        <div className={`mb-4 rounded px-4 py-2 ${message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          {message.text}
        </div>
      )}

      <div className="mb-6 rounded border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">Create a new Project</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="block text-xs text-gray-600">
            Name
            <input className="mt-1 w-full rounded border px-2 py-1 text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="Campus Adele" />
          </label>
          <label className="block text-xs text-gray-600">
            Code name (optional)
            <input className="mt-1 w-full rounded border px-2 py-1 text-sm" value={codeName} onChange={(e) => setCodeName(e.target.value)} placeholder="campus_adele" />
          </label>
          <label className="col-span-full block text-xs text-gray-600">
            Default Model (optional)
            <select className="mt-1 w-full rounded border px-2 py-1 text-sm" value={defaultModelId} onChange={(e) => setDefaultModelId(e.target.value)}>
              <option value="">— none (pick a Model in New Run) —</option>
              {models.map((t) => (<option key={t.id} value={t.id}>{t.name}</option>))}
            </select>
          </label>
          <label className="col-span-full block text-xs text-gray-600">
            Description
            <input className="mt-1 w-full rounded border px-2 py-1 text-sm" value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
        </div>
        <button onClick={handleCreate} disabled={creating} className="mt-3 rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50">
          {creating ? 'Creating…' : 'Create Project'}
        </button>
      </div>

      <div className="overflow-x-auto rounded border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs text-gray-600">
            <tr>
              <th className="px-3 py-2"><SortHeader k="name" label="Name" /></th>
              <th className="px-3 py-2"><SortHeader k="created_by_email" label="Created By" /></th>
              <th className="px-3 py-2"><SortHeader k="created_at" label="Created On" /></th>
              <th className="px-3 py-2">Default Model</th>
              <th className="px-3 py-2"><SortHeader k="last_run_at" label="Last Run" /></th>
              <th className="px-3 py-2">Drive URL</th>
              <th className="px-3 py-2"><SortHeader k="run_count" label="Runs" /></th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2"></th>
            </tr>
            {/* Per-column filters (UX-01-10) */}
            <tr className="bg-white">
              <th className="px-3 pb-2"><input className="w-full rounded border px-1 py-0.5 text-xs" placeholder="filter…" value={fName} onChange={(e) => setFName(e.target.value)} /></th>
              <th className="px-3 pb-2"><input className="w-full rounded border px-1 py-0.5 text-xs" placeholder="email…" value={fCreatedBy} onChange={(e) => setFCreatedBy(e.target.value)} /></th>
              <th className="px-3 pb-2"></th>
              <th className="px-3 pb-2"><input className="w-full rounded border px-1 py-0.5 text-xs" placeholder="model…" value={fModel} onChange={(e) => setFModel(e.target.value)} /></th>
              <th className="px-3 pb-2"></th>
              <th className="px-3 pb-2"></th>
              <th className="px-3 pb-2"></th>
              <th className="px-3 pb-2">
                <select className="w-full rounded border px-1 py-0.5 text-xs" value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
                  <option value="">all</option>
                  <option value="active">active</option>
                  <option value="archived">archived</option>
                </select>
              </th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => (
              <tr key={p.id} className={`border-t ${p.archived ? 'text-gray-400 italic' : ''}`}>
                <td className="px-3 py-2 font-medium">
                  <Link to={`/projects/${p.id}`} className="text-blue-600 hover:underline">{p.name}</Link>
                  <div className="text-xs text-gray-500">{p.code_name}</div>
                </td>
                <td className="px-3 py-2 text-xs">{p.created_by_email ?? '—'}</td>
                <td className="px-3 py-2 text-xs">{p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}</td>
                <td className="px-3 py-2 text-xs">{p.default_model_name ?? <span className="italic text-gray-400">none</span>}</td>
                <td className="px-3 py-2 text-xs">
                  {p.last_run_at ? (
                    <>
                      {new Date(p.last_run_at).toLocaleString()}
                      {p.last_run_status && <span className={`ml-1 rounded px-1 ${p.last_run_status === 'completed' ? 'bg-green-100 text-green-700' : p.last_run_status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'}`}>{p.last_run_status}</span>}
                    </>
                  ) : '—'}
                </td>
                <td className="px-3 py-2 text-xs">
                  {p.drive_folder_url ? (
                    <a href={p.drive_folder_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">📁 Drive</a>
                  ) : '—'}
                </td>
                <td className="px-3 py-2 text-xs">
                  {p.run_count > 0 ? (
                    <Link to={`/runs?project_id=${p.id}`} className="text-blue-600 hover:underline">{p.run_count}</Link>
                  ) : '0'}
                </td>
                <td className="px-3 py-2">
                  <span className={`rounded px-2 py-0.5 text-xs ${p.archived ? 'bg-gray-100 text-gray-500' : 'bg-green-100 text-green-700'}`}>
                    {p.archived ? 'archived' : 'active'}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  {p.archived ? (
                    <button onClick={() => handleUnarchive(p.id)} className="text-xs text-blue-500 hover:underline">Unarchive</button>
                  ) : (
                    <button onClick={() => handleArchive(p.id, p.name)} className="text-xs text-red-500 hover:underline">Archive</button>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={9} className="px-3 py-6 text-center text-sm text-gray-500">
                  {projects.length === 0 ? 'No Projects yet — create one above.' : 'No Projects match your filters.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
