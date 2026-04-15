import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../services/api'
import AssumptionsTable from './AssumptionsTable'
import DataSourceConfig from './DataSourceConfig'
import DAGEditor from './DAGEditor'
import ReportBuilder from './ReportBuilder'

interface Project {
  id: string
  name: string
  status: string
  checkout: {
    user_uid: string | null
    user_name: string | null
    expires_at: string | null
  }
}

function ProjectView({ section }: { section?: string }) {
  const { projectId } = useParams<{ projectId: string }>()
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (projectId) {
      api.get<Project>(`/projects/${projectId}`)
        .then(setProject)
        .finally(() => setLoading(false))
    }
  }, [projectId])

  if (loading) return <div className="flex h-full items-center justify-center p-8"><p>Loading...</p></div>
  if (!project) return <div className="p-8"><p>Project not found.</p></div>

  const activeSection = section ?? 'assumptions'

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
        {project.checkout.user_uid && (
          <div className="mt-2 rounded bg-yellow-50 px-4 py-2 text-sm text-yellow-800">
            Checked out by {project.checkout.user_name ?? 'someone'}
            {project.checkout.expires_at && ` — expires ${new Date(project.checkout.expires_at).toLocaleTimeString()}`}
          </div>
        )}
      </div>

      {activeSection === 'assumptions' && projectId && <AssumptionsTable projectId={projectId} />}
      {activeSection === 'datasources' && projectId && <DataSourceConfig projectId={projectId} />}
      {activeSection === 'dag' && projectId && <DAGEditor projectId={projectId} />}
      {activeSection === 'reports' && projectId && <ReportBuilder projectId={projectId} />}
    </div>
  )
}

export default ProjectView
