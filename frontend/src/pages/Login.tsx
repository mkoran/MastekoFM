import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { Navigate } from 'react-router-dom'

function Login() {
  const { user, loading, signInWithGoogle, signInDev } = useAuth()
  const [devEmail, setDevEmail] = useState('marc.koran@gmail.com')
  const [googleError, setGoogleError] = useState<string | null>(null)

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"></div>
          <p className="text-gray-500">Loading...</p>
        </div>
      </div>
    )
  }

  if (user) {
    return <Navigate to="/" replace />
  }

  const handleGoogle = async () => {
    try {
      setGoogleError(null)
      await signInWithGoogle()
    } catch (err) {
      setGoogleError('Google Sign-In not available yet. Use Dev Login below.')
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md rounded-lg bg-white p-8 shadow-md">
        <h1 className="mb-2 text-center text-3xl font-bold text-gray-900">MastekoFM</h1>
        <p className="mb-8 text-center text-gray-600">Financial Modelling Platform</p>

        <button
          onClick={handleGoogle}
          className="mb-4 flex w-full items-center justify-center gap-3 rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
        >
          Sign in with Google
        </button>

        {googleError && (
          <p className="mb-4 text-center text-xs text-amber-600">{googleError}</p>
        )}

        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-gray-200"></div></div>
          <div className="relative flex justify-center text-xs"><span className="bg-white px-2 text-gray-400">or</span></div>
        </div>

        <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4">
          <p className="mb-3 text-center text-xs font-medium text-gray-500">DEV Login</p>
          <div className="flex gap-2">
            <input
              type="email"
              value={devEmail}
              onChange={(e) => setDevEmail(e.target.value)}
              placeholder="your@email.com"
              className="flex-1 rounded border px-3 py-2 text-sm"
              onKeyDown={(e) => e.key === 'Enter' && signInDev(devEmail)}
            />
            <button
              onClick={() => signInDev(devEmail)}
              className="rounded bg-gray-800 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700"
            >
              Dev Login
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Login
