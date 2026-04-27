import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { setTokenGetter, setGoogleTokenGetter } from './services/api'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Login from './pages/Login'
import SettingsPage from './pages/SettingsPage'
import ModelsPage from './pages/ModelsPage'
import ModelDetailPage from './pages/ModelDetailPage'
import WorkspaceSettingsPage from './pages/WorkspaceSettingsPage'
import HelpPage from './pages/HelpPage'
import ProjectsPage from './pages/ProjectsPage'
import ProjectView from './pages/ProjectView'
import OutputTemplatesPage from './pages/OutputTemplatesPage'
import RunsPage from './pages/RunsPage'
import RunDetailPage from './pages/RunDetailPage'
import TreePage from './pages/TreePage'

function P({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute><Layout>{children}</Layout></ProtectedRoute>
}

function AppRoutes() {
  const { token, googleAccessToken } = useAuth()

  useEffect(() => {
    setTokenGetter(() => token)
  }, [token])

  useEffect(() => {
    setGoogleTokenGetter(() => googleAccessToken)
  }, [googleAccessToken])

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route path="/projects" element={<P><ProjectsPage /></P>} />
      <Route path="/projects/:projectId" element={<P><ProjectView /></P>} />
      <Route path="/models" element={<P><ModelsPage /></P>} />
      <Route path="/models/:modelId" element={<P><ModelDetailPage /></P>} />
      <Route path="/output-templates" element={<P><OutputTemplatesPage /></P>} />
      <Route path="/runs" element={<P><RunsPage /></P>} />
      <Route path="/runs/:runId" element={<P><RunDetailPage /></P>} />
      {/* Sprint A.5 — Tree Navigator */}
      <Route path="/tree" element={<ProtectedRoute><TreePage /></ProtectedRoute>} />
      <Route path="/tree/projects/:projectId" element={<ProtectedRoute><TreePage /></ProtectedRoute>} />
      <Route path="/tree/projects/:projectId/packs/:packId" element={<ProtectedRoute><TreePage /></ProtectedRoute>} />
      <Route path="/tree/projects/:projectId/packs/:packId/:nodeKind" element={<ProtectedRoute><TreePage /></ProtectedRoute>} />
      <Route path="/tree/projects/:projectId/packs/:packId/:nodeKind/:tab/:cellRef" element={<ProtectedRoute><TreePage /></ProtectedRoute>} />
      <Route path="/workspaces/:workspaceId" element={<P><WorkspaceSettingsPage /></P>} />
      <Route path="/settings" element={<P><SettingsPage /></P>} />
      <Route path="/help" element={<P><HelpPage /></P>} />
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
