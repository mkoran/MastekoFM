import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'

interface ProjectSummary {
  id: string
  name: string
  code_name: string
  template_id: string
  template_name: string
  status: string
  scenario_count: number
  created_at: string
}

interface ModelSummary {
  id: string
  name: string
  code_name: string
}

export default function ExcelProjectsPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([])
  const [templates, setTemplates] = useState<ModelSummary[]>([])
  const [name, setName] = useState('')
  const [codeName, setCodeName] = useState('')
  const [templateId, setTemplateId] = useState('')
  const [description, setDescription] = useState('')
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [creating, setCreating] = useState(false)

  const load = () => {
    api.get<ProjectSummary[]>('/projects').then(setProjects).catch(() => setProjects([]))
    api.get<ModelSummary[]>('/models').then(setTemplates).catch(() => setTemplates([]))
  }
  useEffect(load, [])

  const handleCreate = async () => {
    if (!name) {
      setMessage({ text: 'Name is required', type: 'error' })
      return
    }
    if (!templateId) {
      setMessage({ text: 'Pick a template', type: 'error' })
      return
    }
    setCreating(true)
    try {
      await api.post('/projects', { name, code_name: codeName, template_id: templateId, description })
      setName('')
      setCodeName('')
      setDescription('')
      setTemplateId('')
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
    if (!confirm(`Archive "${n}"?`)) return
    try {
      await api.post(`/projects/${id}/archive`, {})
      load()
    } catch {
      setMessage({ text: 'Archive failed', type: 'error' })
    }
  }

  return (
    <div className="p-6">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Excel Projects</h1>
          <p className="mt-1 text-sm text-gray-600">A Project pairs one Excel Template with multiple Scenarios (inputs-only .xlsx files).</p>
        </div>
        <Link to="/models" className="rounded border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50">
          Manage Templates →
        </Link>
      </div>

      {message && (
        <div className={`mb-4 rounded px-4 py-2 ${message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          {message.text}
        </div>
      )}

      <div className="mb-6 rounded border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">Create a new Excel Project</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="block text-xs text-gray-600">
            Name
            <input className="mt-1 w-full rounded border px-2 py-1 text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="Campus Adele" />
          </label>
          <label className="block text-xs text-gray-600">
            Code name
            <input className="mt-1 w-full rounded border px-2 py-1 text-sm" value={codeName} onChange={(e) => setCodeName(e.target.value)} placeholder="campus_adele" />
          </label>
          <label className="col-span-full block text-xs text-gray-600">
            Template
            <select className="mt-1 w-full rounded border px-2 py-1 text-sm" value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
              <option value="">— pick a template —</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
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
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Template</th>
              <th className="px-3 py-2">Scenarios</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.id} className="border-t">
                <td className="px-3 py-2 font-medium">
                  <Link to={`/projects/${p.id}`} className="text-blue-600 hover:underline">{p.name}</Link>
                  <div className="text-xs text-gray-500">{p.code_name}</div>
                </td>
                <td className="px-3 py-2">{p.template_name}</td>
                <td className="px-3 py-2">{p.scenario_count}</td>
                <td className="px-3 py-2">
                  <span className={`rounded px-2 py-0.5 text-xs ${p.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {p.status}
                  </span>
                </td>
                <td className="px-3 py-2 text-right">
                  {p.status !== 'archived' && (
                    <button onClick={() => handleArchive(p.id, p.name)} className="text-xs text-red-500 hover:underline">
                      Archive
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {projects.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-sm text-gray-500">
                  No Excel Projects yet. Upload a Template first, then create a Project.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

