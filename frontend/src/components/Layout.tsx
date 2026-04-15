import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const navItems = [
  { path: '/', label: 'Projects', icon: '□' },
]

function Layout({ children }: { children: React.ReactNode }) {
  const { user, signOut } = useAuth()
  const location = useLocation()

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="flex w-56 flex-col border-r bg-gray-900 text-white">
        <div className="border-b border-gray-700 px-4 py-4">
          <Link to="/" className="text-lg font-bold">MastekoFM</Link>
        </div>
        <nav className="flex-1 px-2 py-4">
          {navItems.map((item) => (
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
        </nav>
        <div className="border-t border-gray-700 px-4 py-3">
          <p className="truncate text-xs text-gray-400">{user?.email}</p>
          <button
            onClick={signOut}
            className="mt-2 text-xs text-gray-500 hover:text-white"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 bg-gray-50">
        {children}
      </main>
    </div>
  )
}

export default Layout
