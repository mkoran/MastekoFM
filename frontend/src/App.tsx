import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { setTokenGetter } from './services/api'
import ProtectedRoute from './components/ProtectedRoute'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import ProjectView from './pages/ProjectView'

function AppRoutes() {
  const { token } = useAuth()

  useEffect(() => {
    setTokenGetter(() => token)
  }, [token])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/projects/:projectId" element={<ProtectedRoute><ProjectView /></ProtectedRoute>} />
    </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
