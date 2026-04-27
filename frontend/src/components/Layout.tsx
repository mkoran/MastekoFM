import { Link, useLocation, useParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useEffect, useState } from 'react'
import { api } from '../services/api'

interface NavProject { id: string; name: string; code_name: string }
interface NavPack { id: string; name: string }
interface NavWorkspace {
  id: string
  name: string
  code_name: string
  member_count: number
  drive_folder_url: string | null
}

/**
 * Sprint B Layout — clean nav. Legacy TGV nav removed.
 * Sprint A.5 will replace this sidebar with the Tree Navigator.
 */
function Layout({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth()
  const location = useLocation()
  const { projectId } = useParams<{ projectId: string }>()

  const [projects, setProjects] = useState<NavProject[]>([])
  const [packs, setPacks] = useState<Record<string, NavPack[]>>({})
  const [expanded, setExpanded] = useState<string | null>(null)
  const [workspace, setWorkspace] = useState<NavWorkspace | null>(null)

  const isActive = (path: string) => location.pathname === path

  useEffect(() => {
    // Sprint G1: load default workspace (auto-creates if user has none)
    api.get<NavWorkspace>('/workspaces/me/default')
      .then(setWorkspace)
      .catch(() => setWorkspace(null))
    api.get<NavProject[]>('/projects').then(setProjects).catch(() => {})
  }, [])

  useEffect(() => {
    if (projectId) {
      setExpanded(projectId)
      api.get<NavPack[]>(`/projects/${projectId}/assumption-packs`)
        .then((p) => setPacks((prev) => ({ ...prev, [projectId]: p })))
        .catch(() => {})
    }
  }, [projectId])

  const toggleProject = (pid: string) => {
    if (expanded === pid) {
      setExpanded(null)
    } else {
      setExpanded(pid)
      api.get<NavPack[]>(`/projects/${pid}/assumption-packs`)
        .then((p) => setPacks((prev) => ({ ...prev, [pid]: p })))
        .catch(() => {})
    }
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 flex-shrink-0 flex-col border-r bg-gray-900 text-white">
        <div className="border-b border-gray-700 px-4 py-4">
          <Link to="/projects" className="text-lg font-bold">MastekoFM</Link>
          {/* Sprint G1: workspace context */}
          {workspace && (
            <div className="mt-2 rounded bg-gray-800 px-2 py-1.5 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-gray-300" title={workspace.name}>
                  🏢 {workspace.name}
                </span>
                <span className="text-[10px] text-gray-500">
                  {workspace.member_count}👤
                </span>
              </div>
              {workspace.drive_folder_url && (
                <a
                  href={workspace.drive_folder_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 block text-[10px] text-gray-500 hover:text-gray-300"
                >
                  📁 Open in Drive
                </a>
              )}
            </div>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-3 text-sm">
          <Link
            to="/tree"
            className={`mb-1 flex items-center gap-2 rounded-lg px-3 py-2 ${location.pathname.startsWith('/tree') ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}
          >
            <span className="text-xs">🌳</span> Tree Navigator
          </Link>
          <Link
            to="/projects"
            className={`mb-1 flex items-center gap-2 rounded-lg px-3 py-2 ${isActive('/projects') ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}
          >
            <span className="text-xs">&#9632;</span> Projects
          </Link>
          {projects.map((p) => (
            <div key={p.id}>
              <div className="flex items-center">
                <button onClick={() => toggleProject(p.id)} className="px-2 py-0.5 text-xs text-gray-500 hover:text-white">
                  {expanded === p.id ? '\u25BC' : '\u25B6'}
                </button>
                <Link
                  to={`/projects/${p.id}`}
                  className={`flex-1 truncate rounded px-1 py-1 text-xs ${isActive(`/projects/${p.id}`) ? 'text-white' : 'text-gray-400 hover:text-white'}`}
                >
                  {p.name}
                </Link>
              </div>
              {expanded === p.id && (
                <div className="ml-6 border-l border-gray-700 pl-2">
                  {(packs[p.id] || []).map((s) => (
                    <Link
                      key={s.id}
                      to={`/projects/${p.id}`}
                      className="mb-0.5 block truncate rounded px-2 py-0.5 text-xs text-gray-500 hover:text-gray-300"
                    >
                      {s.name}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}

          <Link to="/models" className={`mt-2 mb-1 flex items-center gap-2 rounded-lg px-3 py-2 ${isActive('/models') ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}>
            <span className="text-xs">&#9632;</span> Models
          </Link>

          <Link to="/output-templates" className={`mb-1 flex items-center gap-2 rounded-lg px-3 py-2 ${isActive('/output-templates') ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}>
            <span className="text-xs">&#9632;</span> Output Templates
          </Link>

          <Link to="/runs" className={`mb-1 flex items-center gap-2 rounded-lg px-3 py-2 ${isActive('/runs') ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}>
            <span className="text-xs">&#9632;</span> Runs
          </Link>

          <div className="my-3 border-t border-gray-700" />

          <Link to="/settings" className={`mb-1 flex items-center gap-2 rounded-lg px-3 py-2 ${isActive('/settings') ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'}`}>
            <span className="text-xs">&#9881;</span> Settings
          </Link>
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
