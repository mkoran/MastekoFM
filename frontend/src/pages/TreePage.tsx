/**
 * Sprint A.5 — Tree Navigator.
 *
 * Hierarchical browser:
 *   Project → AssumptionPack → (Inputs | Outputs | Runs) → individual cells / runs
 *
 * Left: tree (lazy-loaded, expand/collapse, filter).
 * Right: detail pane that changes based on which node is selected.
 */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

// ── Types ────────────────────────────────────────────────────────────────────

interface Project {
  id: string
  name: string
  code_name: string
  default_model_id?: string | null
  default_model_name?: string | null
  status: string
}

interface Pack {
  id: string
  name: string
  code_name: string
  status: string
  version: number
  last_run_at?: string | null
  last_run_status?: string | null
  created_at: string
}

interface PackDetail extends Pack {
  description: string
  storage_kind: 'gcs' | 'drive_xlsx'
  drive_file_id: string | null
  edit_url: string | null
  size_bytes: number
  created_by: string
}

interface Run {
  id: string
  status: string
  started_at: string
  duration_ms: number | null
  model_id: string
  output_template_id: string
  output_download_url: string | null
}

interface Cell {
  tab: string
  cell_ref: string
  row: number
  column: number
  label: string | null
  value: number | string | boolean | null
  type: string
}

interface InputsResponse {
  pack_id: string
  tab_count: number
  cells: Cell[]
}

interface OutputsResponse {
  pack_id: string
  run_id: string | null
  run_started_at?: string
  model_id?: string
  model_version?: number
  output_template_id?: string
  output_template_version?: number
  tab_count?: number
  cells: Cell[]
  hint?: string
}

// ── Selection ────────────────────────────────────────────────────────────────

type Selection =
  | { kind: 'project'; projectId: string }
  | { kind: 'pack'; projectId: string; packId: string }
  | { kind: 'inputs'; projectId: string; packId: string }
  | { kind: 'outputs'; projectId: string; packId: string }
  | { kind: 'runs'; projectId: string; packId: string }
  | { kind: 'inputCell'; projectId: string; packId: string; tab: string; cellRef: string }
  | { kind: 'outputCell'; projectId: string; packId: string; tab: string; cellRef: string }
  | { kind: 'run'; runId: string }

const STATUS_COLOR: Record<string, string> = {
  active: 'text-gray-200',
  archived: 'text-gray-500',
  pending: 'bg-yellow-100 text-yellow-800',
  running: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
}

// ── Component ────────────────────────────────────────────────────────────────

export default function TreePage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const params = useParams<{ projectId?: string; packId?: string; nodeKind?: string; tab?: string; cellRef?: string }>()

  const [projects, setProjects] = useState<Project[]>([])
  const [packsByProject, setPacksByProject] = useState<Record<string, Pack[]>>({})
  const [expanded, setExpanded] = useState<Set<string>>(new Set())  // node keys
  const [filter, setFilter] = useState('')

  // Derive selection from URL
  const selection: Selection | null = useMemo(() => {
    if (params.cellRef && params.tab && params.packId && params.projectId) {
      const kind = params.nodeKind === 'outputs' ? 'outputCell' : 'inputCell'
      return { kind, projectId: params.projectId, packId: params.packId, tab: params.tab, cellRef: params.cellRef }
    }
    if (params.nodeKind && params.packId && params.projectId) {
      const k = params.nodeKind
      if (k === 'inputs' || k === 'outputs' || k === 'runs') {
        return { kind: k, projectId: params.projectId, packId: params.packId }
      }
    }
    if (params.packId && params.projectId) {
      return { kind: 'pack', projectId: params.projectId, packId: params.packId }
    }
    if (params.projectId) {
      return { kind: 'project', projectId: params.projectId }
    }
    return null
  }, [params])

  // Load projects
  useEffect(() => {
    if (!token) return
    api.get<Project[]>('/projects').then(setProjects).catch(() => setProjects([]))
  }, [token])

  // Auto-expand current project + lazy-load its packs
  useEffect(() => {
    if (!selection) return
    if ('projectId' in selection) {
      setExpanded((prev) => new Set([...prev, `proj:${selection.projectId}`]))
      if (!packsByProject[selection.projectId]) {
        api.get<Pack[]>(`/projects/${selection.projectId}/assumption-packs`)
          .then((p) => setPacksByProject((prev) => ({ ...prev, [selection.projectId]: p })))
          .catch(() => {})
      }
    }
    if ('packId' in selection && (selection.kind === 'inputs' || selection.kind === 'outputs' || selection.kind === 'runs' || selection.kind === 'inputCell' || selection.kind === 'outputCell')) {
      setExpanded((prev) => new Set([...prev, `pack:${selection.packId}`]))
    }
  }, [selection, packsByProject])

  const toggle = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const expandProject = (pid: string) => {
    if (!expanded.has(`proj:${pid}`) && !packsByProject[pid]) {
      api.get<Pack[]>(`/projects/${pid}/assumption-packs`)
        .then((p) => setPacksByProject((prev) => ({ ...prev, [pid]: p })))
        .catch(() => {})
    }
    toggle(`proj:${pid}`)
  }

  const goto = (sel: Selection) => {
    const path = selectionToPath(sel)
    navigate(path)
  }

  // Filter
  const matchesFilter = (s: string) => {
    if (!filter) return true
    return s.toLowerCase().includes(filter.toLowerCase())
  }

  return (
    <div className="flex h-screen">
      {/* ── Tree (left) ──────────────────────────────────────────────── */}
      <aside className="w-72 flex-shrink-0 overflow-y-auto border-r bg-gray-900 text-white">
        <div className="border-b border-gray-700 px-3 py-3">
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="🔍 filter…"
            className="w-full rounded bg-gray-800 px-2 py-1 text-xs text-white placeholder-gray-500"
          />
        </div>
        <nav className="px-2 py-2 text-sm">
          {projects.filter(p => matchesFilter(p.name) || matchesFilter(p.code_name)).map((p) => {
            const isExpanded = expanded.has(`proj:${p.id}`)
            const packs = packsByProject[p.id] || []
            return (
              <div key={p.id} className="mb-0.5">
                <div className="flex items-center gap-1">
                  <button onClick={() => expandProject(p.id)} className="px-1 text-xs text-gray-500 hover:text-white">
                    {isExpanded ? '▼' : '▶'}
                  </button>
                  <button
                    onClick={() => goto({ kind: 'project', projectId: p.id })}
                    className={`flex-1 truncate text-left text-xs px-1 py-1 rounded hover:bg-gray-800 ${selection?.kind === 'project' && selection.projectId === p.id ? 'bg-gray-700 text-white' : 'text-gray-300'}`}
                  >
                    📁 {p.name}
                  </button>
                </div>
                {isExpanded && packs.map((s) => {
                  const packExpanded = expanded.has(`pack:${s.id}`)
                  return (
                    <div key={s.id} className="ml-4 border-l border-gray-700 pl-2">
                      <div className="flex items-center gap-1">
                        <button onClick={() => toggle(`pack:${s.id}`)} className="px-1 text-xs text-gray-500 hover:text-white">
                          {packExpanded ? '▼' : '▶'}
                        </button>
                        <button
                          onClick={() => goto({ kind: 'pack', projectId: p.id, packId: s.id })}
                          className={`flex-1 truncate text-left text-xs px-1 py-1 rounded hover:bg-gray-800 ${selection?.kind === 'pack' && selection.packId === s.id ? 'bg-gray-700 text-white' : 'text-gray-300'}`}
                        >
                          📄 {s.name}
                        </button>
                      </div>
                      {packExpanded && (
                        <div className="ml-4 border-l border-gray-700 pl-2">
                          <button
                            onClick={() => goto({ kind: 'inputs', projectId: p.id, packId: s.id })}
                            className={`block w-full truncate text-left text-xs px-1 py-1 rounded hover:bg-gray-800 ${selection?.kind === 'inputs' && selection.packId === s.id ? 'bg-gray-700 text-white' : 'text-gray-300'}`}
                          >
                            📥 Inputs
                          </button>
                          <button
                            onClick={() => goto({ kind: 'outputs', projectId: p.id, packId: s.id })}
                            className={`block w-full truncate text-left text-xs px-1 py-1 rounded hover:bg-gray-800 ${selection?.kind === 'outputs' && selection.packId === s.id ? 'bg-gray-700 text-white' : 'text-gray-300'}`}
                          >
                            📤 Outputs
                          </button>
                          <button
                            onClick={() => goto({ kind: 'runs', projectId: p.id, packId: s.id })}
                            className={`block w-full truncate text-left text-xs px-1 py-1 rounded hover:bg-gray-800 ${selection?.kind === 'runs' && selection.packId === s.id ? 'bg-gray-700 text-white' : 'text-gray-300'}`}
                          >
                            ⚡ Runs
                          </button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )
          })}
        </nav>
      </aside>

      {/* ── Detail (right) ───────────────────────────────────────────── */}
      <main className="flex-1 overflow-y-auto bg-gray-50 p-6">
        <Breadcrumb selection={selection} projects={projects} packsByProject={packsByProject} navigate={navigate} />
        <DetailPane selection={selection} projects={projects} navigate={navigate} />
      </main>
    </div>
  )
}

// ── URL helpers ──────────────────────────────────────────────────────────────

function selectionToPath(sel: Selection): string {
  switch (sel.kind) {
    case 'project': return `/tree/projects/${sel.projectId}`
    case 'pack':    return `/tree/projects/${sel.projectId}/packs/${sel.packId}`
    case 'inputs':  return `/tree/projects/${sel.projectId}/packs/${sel.packId}/inputs`
    case 'outputs': return `/tree/projects/${sel.projectId}/packs/${sel.packId}/outputs`
    case 'runs':    return `/tree/projects/${sel.projectId}/packs/${sel.packId}/runs`
    case 'inputCell':  return `/tree/projects/${sel.projectId}/packs/${sel.packId}/inputs/${encodeURIComponent(sel.tab)}/${sel.cellRef}`
    case 'outputCell': return `/tree/projects/${sel.projectId}/packs/${sel.packId}/outputs/${encodeURIComponent(sel.tab)}/${sel.cellRef}`
    case 'run':     return `/runs/${sel.runId}`
  }
}

// ── Breadcrumb ───────────────────────────────────────────────────────────────

function Breadcrumb({
  selection, projects, packsByProject, navigate,
}: { selection: Selection | null; projects: Project[]; packsByProject: Record<string, Pack[]>; navigate: (path: string) => void }) {
  if (!selection) return <p className="mb-4 text-sm text-gray-500">Pick something on the left.</p>
  const parts: { label: string; sel: Selection }[] = []
  if ('projectId' in selection) {
    const p = projects.find(x => x.id === selection.projectId)
    parts.push({ label: p?.name || selection.projectId, sel: { kind: 'project', projectId: selection.projectId } })
  }
  if ('packId' in selection) {
    const pid = selection.projectId
    const s = (packsByProject[pid] || []).find(x => x.id === selection.packId)
    parts.push({ label: s?.name || selection.packId, sel: { kind: 'pack', projectId: pid, packId: selection.packId } })
  }
  if (selection.kind === 'inputs' || selection.kind === 'inputCell') {
    parts.push({ label: 'Inputs', sel: { kind: 'inputs', projectId: selection.projectId, packId: selection.packId } })
  }
  if (selection.kind === 'outputs' || selection.kind === 'outputCell') {
    parts.push({ label: 'Outputs', sel: { kind: 'outputs', projectId: selection.projectId, packId: selection.packId } })
  }
  if (selection.kind === 'runs') {
    parts.push({ label: 'Runs', sel: selection })
  }
  if (selection.kind === 'inputCell' || selection.kind === 'outputCell') {
    parts.push({ label: `${selection.tab}!${selection.cellRef}`, sel: selection })
  }
  return (
    <nav className="mb-4 text-xs text-gray-500">
      {parts.map((p, i) => (
        <span key={i}>
          {i > 0 && ' › '}
          <button className="hover:text-gray-900 hover:underline" onClick={() => navigate(selectionToPath(p.sel))}>
            {p.label}
          </button>
        </span>
      ))}
    </nav>
  )
}

// ── Detail Pane Router ───────────────────────────────────────────────────────

function DetailPane({
  selection, projects, navigate,
}: { selection: Selection | null; projects: Project[]; navigate: (path: string) => void }) {
  if (!selection) {
    return <div className="rounded border bg-white p-6 text-center text-sm text-gray-500">Browse the tree on the left.</div>
  }
  if (selection.kind === 'project') {
    const p = projects.find(x => x.id === selection.projectId)
    return <ProjectDetail project={p} />
  }
  if (selection.kind === 'pack') {
    return <PackDetail projectId={selection.projectId} packId={selection.packId} navigate={navigate} />
  }
  if (selection.kind === 'inputs') {
    return <InputsTable projectId={selection.projectId} packId={selection.packId} navigate={navigate} />
  }
  if (selection.kind === 'outputs') {
    return <OutputsTable projectId={selection.projectId} packId={selection.packId} navigate={navigate} />
  }
  if (selection.kind === 'runs') {
    return <RunsTable projectId={selection.projectId} packId={selection.packId} navigate={navigate} />
  }
  if (selection.kind === 'inputCell') {
    return <CellDetail kind="input" projectId={selection.projectId} packId={selection.packId} tab={selection.tab} cellRef={selection.cellRef} />
  }
  if (selection.kind === 'outputCell') {
    return <CellDetail kind="output" projectId={selection.projectId} packId={selection.packId} tab={selection.tab} cellRef={selection.cellRef} />
  }
  return null
}

function ProjectDetail({ project }: { project?: Project }) {
  if (!project) return <div className="text-sm text-gray-500">Loading project…</div>
  return (
    <div className="rounded border bg-white p-6">
      <h1 className="mb-1 text-2xl font-semibold">{project.name}</h1>
      <p className="text-xs text-gray-500">{project.code_name}</p>
      <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div><dt className="font-semibold text-gray-600">Status</dt><dd>{project.status}</dd></div>
        <div><dt className="font-semibold text-gray-600">Default Model</dt><dd>{project.default_model_name || '—'}</dd></div>
      </dl>
    </div>
  )
}

function PackDetail({ projectId, packId, navigate }: { projectId: string; packId: string; navigate: (path: string) => void }) {
  const [pack, setPack] = useState<PackDetail | null>(null)
  useEffect(() => {
    api.get<PackDetail>(`/projects/${projectId}/assumption-packs/${packId}`).then(setPack).catch(() => setPack(null))
  }, [projectId, packId])
  if (!pack) return <div className="text-sm text-gray-500">Loading pack…</div>
  return (
    <div className="rounded border bg-white p-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{pack.name}</h1>
          <p className="text-xs text-gray-500">{pack.code_name} · v{pack.version} · {Math.round(pack.size_bytes / 1024)} KB</p>
        </div>
        <div className="flex gap-2">
          {pack.edit_url && (
            <a href={pack.edit_url} target="_blank" rel="noreferrer" className="rounded bg-green-600 px-3 py-1.5 text-sm text-white hover:bg-green-700">
              Edit in Sheets ↗
            </a>
          )}
        </div>
      </div>
      {pack.description && <p className="mt-3 text-sm text-gray-700">{pack.description}</p>}
      <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div><dt className="font-semibold text-gray-600">Storage</dt><dd>{pack.storage_kind}</dd></div>
        <div><dt className="font-semibold text-gray-600">Created by</dt><dd>{pack.created_by}</dd></div>
        <div><dt className="font-semibold text-gray-600">Created</dt><dd>{new Date(pack.created_at).toLocaleString()}</dd></div>
        <div><dt className="font-semibold text-gray-600">Last run</dt><dd>{pack.last_run_at ? new Date(pack.last_run_at).toLocaleString() : '—'}</dd></div>
      </dl>
      <div className="mt-6 flex gap-2">
        <button className="rounded border border-gray-300 px-3 py-1.5 text-xs hover:bg-gray-50" onClick={() => navigate(`/tree/projects/${projectId}/packs/${packId}/inputs`)}>📥 Inputs</button>
        <button className="rounded border border-gray-300 px-3 py-1.5 text-xs hover:bg-gray-50" onClick={() => navigate(`/tree/projects/${projectId}/packs/${packId}/outputs`)}>📤 Outputs</button>
        <button className="rounded border border-gray-300 px-3 py-1.5 text-xs hover:bg-gray-50" onClick={() => navigate(`/tree/projects/${projectId}/packs/${packId}/runs`)}>⚡ Runs</button>
      </div>
    </div>
  )
}

function InputsTable({ projectId, packId, navigate }: { projectId: string; packId: string; navigate: (path: string) => void }) {
  const [data, setData] = useState<InputsResponse | null>(null)
  useEffect(() => {
    api.get<InputsResponse>(`/projects/${projectId}/assumption-packs/${packId}/inputs`).then(setData).catch(() => setData({ pack_id: packId, tab_count: 0, cells: [] }))
  }, [projectId, packId])
  if (!data) return <div className="text-sm text-gray-500">Loading inputs…</div>

  // Group by tab
  const byTab: Record<string, Cell[]> = {}
  for (const c of data.cells) (byTab[c.tab] = byTab[c.tab] || []).push(c)
  return (
    <div className="rounded border bg-white p-4">
      <h2 className="mb-3 text-lg font-semibold">📥 Inputs ({data.cells.length} cells across {data.tab_count} tabs)</h2>
      {Object.entries(byTab).map(([tab, cells]) => (
        <div key={tab} className="mb-6">
          <h3 className="mb-2 text-sm font-semibold text-gray-700">{tab}</h3>
          <table className="w-full text-xs">
            <thead className="bg-gray-50 text-left text-gray-600">
              <tr><th className="px-2 py-1">Cell</th><th className="px-2 py-1">Label</th><th className="px-2 py-1">Value</th><th className="px-2 py-1">Type</th></tr>
            </thead>
            <tbody>
              {cells.map((c, i) => (
                <tr key={i} className="border-t hover:bg-blue-50">
                  <td className="px-2 py-1 font-mono">
                    <button className="text-blue-600 hover:underline" onClick={() => navigate(`/tree/projects/${projectId}/packs/${packId}/inputs/${encodeURIComponent(c.tab)}/${c.cell_ref}`)}>
                      {c.cell_ref}
                    </button>
                  </td>
                  <td className="px-2 py-1">{c.label || <span className="text-gray-400">—</span>}</td>
                  <td className="px-2 py-1">{String(c.value)}</td>
                  <td className="px-2 py-1 text-gray-500">{c.type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}

function OutputsTable({ projectId, packId, navigate }: { projectId: string; packId: string; navigate: (path: string) => void }) {
  const [data, setData] = useState<OutputsResponse | null>(null)
  useEffect(() => {
    api.get<OutputsResponse>(`/projects/${projectId}/assumption-packs/${packId}/outputs`).then(setData).catch(() => setData({ pack_id: packId, run_id: null, cells: [] }))
  }, [projectId, packId])
  if (!data) return <div className="text-sm text-gray-500">Loading outputs…</div>
  if (data.hint || data.cells.length === 0) {
    return <div className="rounded border bg-yellow-50 p-4 text-sm text-yellow-800">{data.hint || 'No outputs yet.'}</div>
  }
  const byTab: Record<string, Cell[]> = {}
  for (const c of data.cells) (byTab[c.tab] = byTab[c.tab] || []).push(c)
  return (
    <div className="rounded border bg-white p-4">
      <h2 className="mb-3 text-lg font-semibold">📤 Outputs from latest Run</h2>
      <p className="mb-4 text-xs text-gray-500">
        Run <code>{data.run_id?.slice(0, 8)}…</code>{' '}
        · Model v{data.model_version} · OutputTemplate v{data.output_template_version}
        {data.run_started_at ? ` · ${new Date(data.run_started_at).toLocaleString()}` : ''}
      </p>
      {Object.entries(byTab).map(([tab, cells]) => (
        <div key={tab} className="mb-6">
          <h3 className="mb-2 text-sm font-semibold text-gray-700">{tab}</h3>
          <table className="w-full text-xs">
            <thead className="bg-gray-50 text-left text-gray-600">
              <tr><th className="px-2 py-1">Cell</th><th className="px-2 py-1">Label</th><th className="px-2 py-1">Value</th><th className="px-2 py-1">Type</th></tr>
            </thead>
            <tbody>
              {cells.map((c, i) => (
                <tr key={i} className="border-t hover:bg-green-50">
                  <td className="px-2 py-1 font-mono">
                    <button className="text-blue-600 hover:underline" onClick={() => navigate(`/tree/projects/${projectId}/packs/${packId}/outputs/${encodeURIComponent(c.tab)}/${c.cell_ref}`)}>
                      {c.cell_ref}
                    </button>
                  </td>
                  <td className="px-2 py-1">{c.label || <span className="text-gray-400">—</span>}</td>
                  <td className="px-2 py-1">{String(c.value)}</td>
                  <td className="px-2 py-1 text-gray-500">{c.type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  )
}

function RunsTable({ projectId, packId, navigate }: { projectId: string; packId: string; navigate: (path: string) => void }) {
  const [runs, setRuns] = useState<Run[]>([])
  useEffect(() => {
    api.get<Run[]>(`/runs?project_id=${projectId}&limit=50`).then(setRuns).catch(() => setRuns([]))
  }, [projectId, packId])
  // The API doesn't filter by pack_id directly; filter client-side
  const packRuns = runs.filter(r => (r as unknown as { assumption_pack_id?: string }).assumption_pack_id === packId)
  return (
    <div className="rounded border bg-white p-4">
      <h2 className="mb-3 text-lg font-semibold">⚡ Runs ({packRuns.length})</h2>
      <table className="w-full text-xs">
        <thead className="bg-gray-50 text-left text-gray-600">
          <tr>
            <th className="px-2 py-1">Started</th><th className="px-2 py-1">Status</th>
            <th className="px-2 py-1">Duration</th><th className="px-2 py-1">Output</th>
          </tr>
        </thead>
        <tbody>
          {packRuns.map((r) => (
            <tr key={r.id} className="border-t hover:bg-gray-50">
              <td className="px-2 py-1">
                <button className="text-blue-600 hover:underline" onClick={() => navigate(`/runs/${r.id}`)}>
                  {new Date(r.started_at).toLocaleString()}
                </button>
              </td>
              <td className="px-2 py-1">
                <span className={`rounded px-2 py-0.5 ${STATUS_COLOR[r.status] || 'bg-gray-100'}`}>{r.status}</span>
              </td>
              <td className="px-2 py-1">{r.duration_ms ?? '—'}ms</td>
              <td className="px-2 py-1">
                {r.output_download_url
                  ? <a className="text-blue-600 hover:underline" href={r.output_download_url} target="_blank" rel="noreferrer">.xlsx</a>
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {packRuns.length === 0 && <p className="text-sm text-gray-500">No runs yet for this pack.</p>}
    </div>
  )
}

function CellDetail({ kind, projectId, packId, tab, cellRef }: { kind: 'input' | 'output'; projectId: string; packId: string; tab: string; cellRef: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null)
  const [history, setHistory] = useState<{ run_id: string; started_at: string; value: unknown }[]>([])
  useEffect(() => {
    if (kind === 'input') {
      api.get<Record<string, unknown>>(`/projects/${projectId}/assumption-packs/${packId}/inputs/${encodeURIComponent(tab)}/${cellRef}`).then(setData).catch(() => setData(null))
    } else {
      api.get<{ history: typeof history }>(`/projects/${projectId}/assumption-packs/${packId}/outputs/${encodeURIComponent(tab)}/${cellRef}/history`).then((r) => {
        setHistory(r.history)
        setData({ tab, cell_ref: cellRef, latest: r.history[r.history.length - 1] })
      }).catch(() => setData(null))
    }
  }, [kind, projectId, packId, tab, cellRef])
  if (!data) return <div className="text-sm text-gray-500">Loading cell…</div>
  return (
    <div className="rounded border bg-white p-6">
      <h2 className="mb-3 text-lg font-semibold">
        {kind === 'input' ? '📥' : '📤'} {tab}!{cellRef}
      </h2>
      {kind === 'input' && (
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div><dt className="font-semibold text-gray-600">Value</dt><dd>{String(data.value)}</dd></div>
          <div><dt className="font-semibold text-gray-600">Type</dt><dd>{String(data.type)}</dd></div>
          <div><dt className="font-semibold text-gray-600">Label</dt><dd>{String(data.label || '—')}</dd></div>
          <div><dt className="font-semibold text-gray-600">Pack</dt><dd>{String(data.pack_name)} v{String(data.pack_version)}</dd></div>
        </dl>
      )}
      {kind === 'output' && (
        <div>
          <p className="mb-3 text-sm">Latest value: <strong>{history.length > 0 ? String(history[history.length - 1]?.value) : '—'}</strong></p>
          <h3 className="mt-4 mb-2 text-sm font-semibold text-gray-700">History across runs</h3>
          {history.length === 0 ? (
            <p className="text-sm text-gray-500">No history.</p>
          ) : (
            <table className="w-full text-xs">
              <thead className="bg-gray-50 text-left text-gray-600">
                <tr><th className="px-2 py-1">Run</th><th className="px-2 py-1">Started</th><th className="px-2 py-1">Value</th></tr>
              </thead>
              <tbody>
                {history.map((h, i) => (
                  <tr key={i} className="border-t">
                    <td className="px-2 py-1 font-mono text-gray-500">{h.run_id.slice(0, 8)}…</td>
                    <td className="px-2 py-1">{new Date(h.started_at).toLocaleString()}</td>
                    <td className="px-2 py-1">{String(h.value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}
