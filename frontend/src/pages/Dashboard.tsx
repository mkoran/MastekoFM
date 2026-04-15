import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { api } from '../services/api'

interface Project {
  id: string
  name: string
  status: string
  created_at: string
  updated_at: string
}

function Dashboard() {
  const { user, loading: authLoading, signOut } = useAuth()
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    if (!authLoading && user) {
      api.get<Project[]>('/projects').then(setProjects).finally(() => setLoading(false))
    }
  }, [authLoading, user])

  const handleCreate = async () => {
    if (!newName.trim()) return
    setCreating(true)
    try {
      const project = await api.post<Project>('/projects', { name: newName.trim() })
      setProjects((prev) => [...prev, project])
      setNewName('')
      setShowCreate(false)
    } finally {
      setCreating(false)
    }
  }

  if (authLoading) return <div className="flex min-h-screen items-center justify-center"><p>Loading...</p></div>

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white px-8 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">MastekoFM</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">{user?.email}</span>
            <button onClick={signOut} className="text-sm text-gray-500 hover:text-gray-700">Sign out</button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-8 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900">Projects</h2>
          <button
            onClick={() => setShowCreate(true)}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            New Project
          </button>
        </div>

        {showCreate && (
          <div className="mb-6 flex gap-3 rounded-lg border bg-white p-4">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Project name"
              className="flex-1 rounded border px-3 py-2 text-sm"
              autoFocus
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
            />
            <button
              onClick={handleCreate}
              disabled={creating}
              className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {creating ? 'Creating...' : 'Create'}
            </button>
            <button onClick={() => setShowCreate(false)} className="rounded px-3 py-2 text-sm text-gray-500 hover:bg-gray-100">
              Cancel
            </button>
          </div>
        )}

        {loading ? (
          <p className="text-gray-500">Loading projects...</p>
        ) : projects.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
            <p className="text-gray-500">No projects yet. Create your first project to get started.</p>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <Link
                key={project.id}
                to={`/projects/${project.id}`}
                className="rounded-lg border bg-white p-5 shadow-sm hover:shadow-md transition-shadow"
              >
                <h3 className="font-semibold text-gray-900">{project.name}</h3>
                <p className="mt-1 text-xs text-gray-500">
                  Updated {new Date(project.updated_at).toLocaleDateString()}
                </p>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

export default Dashboard
