import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { setTokenGetter } from './services/api'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import ProjectView from './pages/ProjectView'
import TemplatesPage from './pages/TemplatesPage'

function AppRoutes() {
  const { token } = useAuth()

  useEffect(() => {
    setTokenGetter(() => token)
  }, [token])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<ProtectedRoute><Layout><Dashboard /></Layout></ProtectedRoute>} />
      <Route path="/templates" element={<ProtectedRoute><Layout><TemplatesPage /></Layout></ProtectedRoute>} />
      <Route path="/projects/:projectId" element={<ProtectedRoute><Layout><ProjectView /></Layout></ProtectedRoute>} />
      <Route path="/projects/:projectId/datasources" element={<ProtectedRoute><Layout><ProjectView section="datasources" /></Layout></ProtectedRoute>} />
      <Route path="/projects/:projectId/dag" element={<ProtectedRoute><Layout><ProjectView section="dag" /></Layout></ProtectedRoute>} />
      <Route path="/projects/:projectId/reports" element={<ProtectedRoute><Layout><ProjectView section="reports" /></Layout></ProtectedRoute>} />
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
