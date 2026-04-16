import { Link, useLocation, useParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useEffect, useState } from 'react'
import { api } from '../services/api'

interface NavProject { id: string; name: string }
interface NavTG { id: string; name: string }
interface NavTGV { id: string; name: string }

const projectNav = [
  { suffix: '', label: 'Assumptions', icon: '\u{1F4CA}' },
  { suffix: '/datasources', label: 'Data Sources', icon: '\u{1F517}' },
  { suffix: '/dag', label: 'DAG', icon: '\u{1F501}' },
  { suffix: '/reports', label: 'Reports', icon: '\u{1F4C4}' },
]

function Layout({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth()
  const location = useLocation()
  const { projectId } = useParams<{ projectId: string }>()

  const [projects, setProjects] = useState<NavProject[]>([])
  const [templateGroups, setTemplateGroups] = useState<NavTG[]>([])
  const [scenarios, setScenarios] = useState<NavTGV[]>([])
  const [expandedProject, setExpandedProject] = useState<string | null>(null)

  const isProjectView = !!projectId
  const isActive = (path: string) => location.pathname === path

  useEffect(() => {
    api.get<NavProject[]>('/projects').then(setProjects).catch(() => {})
    api.get<NavTG[]>('/template-groups').then(setTemplateGroups).catch(() => {})
  }, [])

  useEffect(() => {
    if (projectId) {
      setExpandedProject(projectId)
      api.get<NavTGV[]>(`/projects/${projectId}/scenarios`).then(setScenarios).catch(() => {})
    }
  }, [projectId])

  const toggleProject = (pid: string) => {
    if (expandedProject === pid) {
      setExpandedProject(null)
    } else {
      setExpandedProject(pid)
      api.get<NavTGV[]>(`/projects/${pid}/scenarios`).then(setScenarios).catch(() => {})
    }
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 flex-shrink-0 flex-col border-r bg-gray-900 text-white">
        <div className="border-b border-gray-700 px-4 py-4">
          <Link to="/" className="text-lg font-bold">MastekoFM</Link>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-3 text-sm">
          {/* Projects */}
          <Link to="/" className={`mb-1 flex items-center gap-2 rounded-lg px-3 py-2 ${isActive('/') ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}>
            <span className="text-xs">&#9632;</span> Projects
          </Link>
          {projects.map((p) => (
            <div key={p.id}>
              <div className="flex items-center">
                <button onClick={() => toggleProject(p.id)} className="px-2 py-0.5 text-xs text-gray-500 hover:text-white">
                  {expandedProject === p.id ? '\u25BC' : '\u25B6'}
                </button>
                <Link to={`/projects/${p.id}`}
                  className={`flex-1 truncate rounded px-1 py-1 text-xs ${isActive(`/projects/${p.id}`) ? 'text-white' : 'text-gray-400 hover:text-white'}`}>
                  {p.name}
                </Link>
              </div>
              {expandedProject === p.id && (
                <div className="ml-6 border-l border-gray-700 pl-2">
                  {scenarios.map((s) => (
                    <Link key={s.id} to={`/projects/${p.id}/scenarios/${s.id}`}
                      className={`mb-0.5 block truncate rounded px-2 py-0.5 text-xs ${isActive(`/projects/${p.id}/scenarios/${s.id}`) ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'}`}>
                      {s.name}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}

          <div className="my-3 border-t border-gray-700" />

          {/* Templates */}
          <Link to="/templates" className={`mb-1 flex items-center gap-2 rounded-lg px-3 py-2 ${isActive('/templates') ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}>
            <span className="text-xs">&#9632;</span> Templates
          </Link>

          {/* Template Groups */}
          <Link to="/template-groups" className={`mb-1 flex items-center gap-2 rounded-lg px-3 py-2 ${isActive('/template-groups') ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}>
            <span className="text-xs">&#9632;</span> Template Groups
          </Link>
          {templateGroups.map((tg) => (
            <Link key={tg.id} to={`/template-groups/${tg.id}`}
              className={`mb-0.5 ml-4 block truncate rounded px-2 py-0.5 text-xs ${isActive(`/template-groups/${tg.id}`) ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'}`}>
              {tg.name}
            </Link>
          ))}

          <div className="my-3 border-t border-gray-700" />

          {/* Settings */}
          <Link to="/settings" className={`mb-1 flex items-center gap-2 rounded-lg px-3 py-2 ${isActive('/settings') ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}>
            <span className="text-xs">&#9881;</span> Settings
          </Link>

          {/* Project-scoped nav */}
          {isProjectView && (
            <>
              <div className="my-3 border-t border-gray-700" />
              <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-gray-500">Project</p>
              {projectNav.map((item) => {
                const path = `/projects/${projectId}${item.suffix}`
                return (
                  <Link key={item.suffix} to={path}
                    className={`mb-1 flex items-center gap-3 rounded-lg px-3 py-2 ${isActive(path) ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}>
                    <span>{item.icon}</span> {item.label}
                  </Link>
                )
              })}
            </>
          )}
        </nav>

        <div className="border-t border-gray-700 px-4 py-3">
          <p className="truncate text-xs text-gray-400">{user?.email}</p>
          <button onClick={signOut} className="mt-2 text-xs text-gray-500 hover:text-white">Sign out</button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto bg-gray-50">
        {children}
      </main>
    </div>
  )
}

export default Layout
