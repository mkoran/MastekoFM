import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'

interface Project {
  id: string
  name: string
  status: string
  created_at: string
  updated_at: string
}

function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    api.get<Project[]>('/projects').then(setProjects).finally(() => setLoading(false))
  }, [])

  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    try {
      const project = await api.post<Project>('/projects', { name: newName.trim() })
      setProjects((prev) => [...prev, project])
      setNewName('')
      setShowCreate(false)
    } finally { setCreating(false) }
  }

  const handleRename = async (id: string) => {
    if (!editName.trim()) return
    const updated = await api.put<Project>(`/projects/${id}`, { name: editName.trim() })
    setProjects((prev) => prev.map((p) => (p.id === id ? updated : p)))
    setEditingId(null)
  }

  const handleArchive = async (id: string) => {
    if (!confirm('Archive this project?')) return
    await api.post(`/projects/${id}/archive`, {})
    setProjects((prev) => prev.filter((p) => p.id !== id))
  }

  if (loading) return <div className="p-8"><p className="text-gray-500">Loading projects...</p></div>

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
        <button onClick={() => setShowCreate(true)} className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          New Project
        </button>
      </div>

      {showCreate && (
        <div className="mb-4 flex gap-3 rounded border bg-white p-4">
          <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)}
            placeholder="Project name" className="flex-1 rounded border px-3 py-2 text-sm" autoFocus
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()} />
          <button onClick={handleCreate} disabled={creating}
            className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50">
            {creating ? 'Creating...' : 'Create'}
          </button>
          <button onClick={() => setShowCreate(false)} className="text-sm text-gray-500">Cancel</button>
        </div>
      )}

      {projects.length === 0 ? (
        <div className="rounded border-2 border-dashed border-gray-300 p-12 text-center">
          <p className="text-gray-500">No projects yet. Create your first project to get started.</p>
        </div>
      ) : (
        <table className="w-full rounded border bg-white text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Created</th>
              <th className="px-4 py-3">Updated</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((p) => (
              <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="px-4 py-3">
                  {editingId === p.id ? (
                    <input value={editName} onChange={(e) => setEditName(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleRename(p.id)}
                      onBlur={() => handleRename(p.id)}
                      className="rounded border px-2 py-1 text-sm" autoFocus />
                  ) : (
                    <button onClick={() => navigate(`/projects/${p.id}`)} className="font-medium text-blue-600 hover:underline">
                      {p.name}
                    </button>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs ${p.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {p.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500">{new Date(p.created_at).toLocaleDateString()}</td>
                <td className="px-4 py-3 text-gray-500">{new Date(p.updated_at).toLocaleDateString()}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-3">
                    <button onClick={() => navigate(`/projects/${p.id}`)} className="text-xs text-blue-600 hover:underline">Open</button>
                    <button onClick={() => { setEditingId(p.id); setEditName(p.name) }} className="text-xs text-gray-600 hover:underline">Rename</button>
                    <button onClick={() => handleArchive(p.id)} className="text-xs text-red-500 hover:underline">Archive</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default Dashboard
