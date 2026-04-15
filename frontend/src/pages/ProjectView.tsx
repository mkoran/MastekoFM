import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../services/api'
import AssumptionsTable from './AssumptionsTable'
import DataSourceConfig from './DataSourceConfig'

interface Project {
  id: string
  name: string
  status: string
  checkout: {
    user_uid: string | null
    user_name: string | null
    checked_out_at: string | null
    expires_at: string | null
  }
}

function ProjectView() {
  const { projectId } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'assumptions' | 'datasources' | 'dag' | 'reports'>('assumptions')

  useEffect(() => {
    if (projectId) {
      api.get<Project>(`/projects/${projectId}`)
        .then(setProject)
        .finally(() => setLoading(false))
    }
  }, [projectId])

  if (loading) return <div className="flex min-h-screen items-center justify-center"><p>Loading...</p></div>
  if (!project) return <div className="p-8"><p>Project not found.</p></div>

  const tabs = ['assumptions', 'datasources', 'dag', 'reports'] as const

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white px-8 py-4">
        <div className="flex items-center gap-4">
          <Link to="/" className="text-sm text-blue-600 hover:underline">&larr; Projects</Link>
          <h1 className="text-xl font-bold text-gray-900">{project.name}</h1>
        </div>
      </header>

      {project.checkout.user_uid && (
        <div className="border-b bg-yellow-50 px-8 py-2 text-sm text-yellow-800">
          Checked out by {project.checkout.user_name ?? 'someone'}
          {project.checkout.expires_at && ` — expires ${new Date(project.checkout.expires_at).toLocaleTimeString()}`}
        </div>
      )}

      <nav className="border-b bg-white px-8">
        <div className="flex gap-6">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`border-b-2 px-1 py-3 text-sm font-medium capitalize ${
                activeTab === tab ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </nav>

      <main className="mx-auto max-w-6xl px-8 py-6">
        {activeTab === 'assumptions' && projectId && <AssumptionsTable projectId={projectId} />}
        {activeTab === 'datasources' && projectId && <DataSourceConfig projectId={projectId} />}
        {activeTab === 'dag' && <p className="text-gray-500">DAG editor — coming in Sprint 3.</p>}
        {activeTab === 'reports' && <p className="text-gray-500">Reports — coming in Sprint 5.</p>}
      </main>
    </div>
  )
}

export default ProjectView
