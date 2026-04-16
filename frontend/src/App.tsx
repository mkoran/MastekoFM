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
import TemplateGroupsPage from './pages/TemplateGroupsPage'
import ScenarioEditor from './pages/ScenarioEditor'
import SettingsPage from './pages/SettingsPage'

function P({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute><Layout>{children}</Layout></ProtectedRoute>
}

function AppRoutes() {
  const { token } = useAuth()

  useEffect(() => {
    setTokenGetter(() => token)
  }, [token])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<P><Dashboard /></P>} />
      <Route path="/templates" element={<P><TemplatesPage /></P>} />
      <Route path="/template-groups" element={<P><TemplateGroupsPage /></P>} />
      <Route path="/template-groups/:groupId" element={<P><TemplateGroupsPage /></P>} />
      <Route path="/settings" element={<P><SettingsPage /></P>} />
      <Route path="/projects/:projectId" element={<P><ProjectView /></P>} />
      <Route path="/projects/:projectId/datasources" element={<P><ProjectView section="datasources" /></P>} />
      <Route path="/projects/:projectId/dag" element={<P><ProjectView section="dag" /></P>} />
      <Route path="/projects/:projectId/reports" element={<P><ProjectView section="reports" /></P>} />
      <Route path="/projects/:projectId/scenarios/:scenarioId" element={<P><ScenarioEditor /></P>} />
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
