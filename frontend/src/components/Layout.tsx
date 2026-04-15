import { Link, useLocation, useParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const globalNav = [
  { path: '/', label: 'Projects', icon: '\u{1F4C1}' },
  { path: '/templates', label: 'Templates', icon: '\u{1F4CB}' },
]

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

  const isProjectView = !!projectId

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 flex-shrink-0 flex-col border-r bg-gray-900 text-white">
        <div className="border-b border-gray-700 px-4 py-4">
          <Link to="/" className="text-lg font-bold">MastekoFM</Link>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-4">
          {/* Global nav */}
          {globalNav.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`mb-1 flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                location.pathname === item.path
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-white'
              }`}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          ))}

          {/* Project-scoped nav */}
          {isProjectView && (
            <>
              <div className="my-3 border-t border-gray-700" />
              <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-gray-500">Project</p>
              {projectNav.map((item) => {
                const path = `/projects/${projectId}${item.suffix}`
                const isActive = location.pathname === path
                return (
                  <Link
                    key={item.suffix}
                    to={path}
                    className={`mb-1 flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                      isActive ? 'bg-gray-700 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                    }`}
                  >
                    <span>{item.icon}</span>
                    {item.label}
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
