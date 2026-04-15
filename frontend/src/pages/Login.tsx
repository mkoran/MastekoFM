import { useAuth } from '../contexts/AuthContext'
import { Navigate } from 'react-router-dom'

function Login() {
  const { user, loading, signInWithGoogle } = useAuth()

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <p className="text-gray-500">Loading...</p>
      </div>
    )
  }

  if (user) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md rounded-lg bg-white p-8 shadow-md">
        <h1 className="mb-2 text-center text-3xl font-bold text-gray-900">MastekoFM</h1>
        <p className="mb-8 text-center text-gray-600">Financial Modelling Platform</p>
        <button
          onClick={signInWithGoogle}
          className="flex w-full items-center justify-center gap-3 rounded-lg border border-gray-300 bg-white px-4 py-3 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
        >
          Sign in with Google
        </button>
      </div>
    </div>
  )
}

export default Login
