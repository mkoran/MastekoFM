import { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { api } from '../services/api'

function SettingsPage() {
  const { user, googleAccessToken, signInWithGoogle } = useAuth()
  const [driveFolderId, setDriveFolderId] = useState('')
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [testingGCS, setTestingGCS] = useState(false)
  const [testingDrive, setTestingDrive] = useState(false)
  const [gcsResult, setGcsResult] = useState<{ success: boolean; message?: string; error?: string } | null>(null)
  const [driveResult, setDriveResult] = useState<{ success: boolean; message?: string; error?: string } | null>(null)

  useEffect(() => {
    api.get<{ drive_root_folder_id: string }>('/settings')
      .then((s) => setDriveFolderId(s.drive_root_folder_id || ''))
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    let folderId = driveFolderId.trim()
    const match = folderId.match(/folders\/([a-zA-Z0-9_-]+)/)
    if (match) folderId = match[1] ?? folderId
    setDriveFolderId(folderId)

    await api.put('/settings', { drive_root_folder_id: folderId })
    setSaved(true)
    setDriveResult(null)
    setGcsResult(null)
    setTimeout(() => setSaved(false), 3000)
  }

  const handleTestGCS = async () => {
    setTestingGCS(true)
    setGcsResult(null)
    try {
      const r = await api.post<{ success: boolean; message?: string; error?: string }>('/settings/test-storage', {})
      setGcsResult(r)
    } catch (e) { setGcsResult({ success: false, error: String(e) }) }
    finally { setTestingGCS(false) }
  }

  const handleTestDrive = async () => {
    if (!googleAccessToken) {
      setDriveResult({ success: false, error: 'Sign in with Google first (click the button above).' })
      return
    }
    setTestingDrive(true)
    setDriveResult(null)
    try {
      const r = await api.post<{ success: boolean; message?: string; error?: string }>('/settings/test-drive', {})
      setDriveResult(r)
    } catch (e) { setDriveResult({ success: false, error: String(e) }) }
    finally { setTestingDrive(false) }
  }

  if (loading) return <div className="p-8"><p>Loading...</p></div>

  const isGoogleAuth = !!googleAccessToken

  return (
    <div className="p-8">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Settings</h1>

      {/* Google Auth status */}
      <div className="mb-6 max-w-2xl rounded border bg-white p-6">
        <h2 className="mb-3 text-lg font-medium">Google Authentication</h2>
        {isGoogleAuth ? (
          <div className="rounded bg-green-50 p-3 text-sm text-green-800">
            Signed in with Google as <strong>{user?.email}</strong>. Drive access enabled.
          </div>
        ) : (
          <div>
            <p className="mb-3 text-sm text-gray-600">
              Sign in with Google to enable Drive uploads. Your Google token is used to write files to your personal Drive.
            </p>
            <button onClick={signInWithGoogle} className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">
              Sign in with Google
            </button>
          </div>
        )}
      </div>

      {/* Google Drive folder */}
      <div className="mb-6 max-w-2xl rounded border bg-white p-6">
        <h2 className="mb-3 text-lg font-medium">Google Drive Output Folder</h2>
        <p className="mb-3 text-sm text-gray-600">
          Calculated Excel files will be saved to this Drive folder, organized by project and scenario.
        </p>
        <div className="mb-3 flex gap-2">
          <input
            value={driveFolderId}
            onChange={(e) => setDriveFolderId(e.target.value)}
            placeholder="Paste Drive folder URL or ID"
            className="flex-1 rounded border px-3 py-2 font-mono text-sm"
          />
          <button onClick={handleSave} className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">Save</button>
        </div>
        {saved && <p className="mb-3 text-sm text-green-600">Saved.</p>}

        <div className="flex gap-2">
          <button onClick={handleTestDrive} disabled={testingDrive}
            className="rounded border border-blue-600 px-4 py-2 text-sm text-blue-600 hover:bg-blue-50 disabled:opacity-50">
            {testingDrive ? 'Testing...' : 'Test Drive Connection'}
          </button>
          <button onClick={handleTestGCS} disabled={testingGCS}
            className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50">
            {testingGCS ? 'Testing...' : 'Test Cloud Storage'}
          </button>
        </div>

        {driveResult && (
          <div className={`mt-3 rounded p-3 text-sm ${driveResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
            <p className="font-medium">{driveResult.success ? 'Drive connection OK!' : 'Drive test failed'}</p>
            <p className="mt-1">{driveResult.message || driveResult.error}</p>
          </div>
        )}

        {gcsResult && (
          <div className={`mt-3 rounded p-3 text-sm ${gcsResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
            <p className="font-medium">{gcsResult.success ? 'Cloud Storage OK!' : 'Storage test failed'}</p>
            <p className="mt-1">{gcsResult.message || gcsResult.error}</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default SettingsPage
