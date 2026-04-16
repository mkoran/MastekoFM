import { useEffect, useState } from 'react'
import { api } from '../services/api'

function SettingsPage() {
  const [driveFolderId, setDriveFolderId] = useState('')
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success: boolean; message?: string; error?: string } | null>(null)

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
    setTestResult(null)
    setTimeout(() => setSaved(false), 3000)
  }

  const handleTestGCS = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await api.post<{ success: boolean; message?: string; error?: string }>('/settings/test-storage', {})
      setTestResult(result)
    } catch (e) {
      setTestResult({ success: false, error: String(e) })
    } finally {
      setTesting(false)
    }
  }

  if (loading) return <div className="p-8"><p>Loading...</p></div>

  return (
    <div className="p-8">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Settings</h1>

      {/* Output Storage */}
      <div className="mb-6 max-w-2xl rounded border bg-white p-6">
        <h2 className="mb-4 text-lg font-medium">Output File Storage</h2>
        <p className="mb-4 text-sm text-gray-600">
          When you calculate a model, the output Excel file is saved to cloud storage
          and available via the "Download Excel File" button.
        </p>

        <div className="mb-4">
          <button
            onClick={handleTestGCS}
            disabled={testing}
            className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {testing ? 'Testing...' : 'Test Storage Connection'}
          </button>
        </div>

        {testResult && (
          <div className={`mb-4 rounded p-3 text-sm ${testResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
            {testResult.success ? (
              <div>
                <p className="font-medium">Storage connection OK!</p>
                <p className="mt-1">{testResult.message}</p>
              </div>
            ) : (
              <div>
                <p className="font-medium">Storage test failed</p>
                <p className="mt-1 break-all">{testResult.error}</p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Google Drive (future) */}
      <div className="max-w-2xl rounded border bg-white p-6">
        <h2 className="mb-4 text-lg font-medium">Google Drive Integration <span className="rounded bg-yellow-100 px-2 py-0.5 text-xs text-yellow-700">Coming Soon</span></h2>
        <p className="mb-3 text-sm text-gray-600">
          Save output files directly to your Google Drive folder. This requires Google Sign-In
          (not DEV login) so the system can use your credentials to write to your Drive.
        </p>
        <div className="mb-3 flex gap-2">
          <input
            value={driveFolderId}
            onChange={(e) => setDriveFolderId(e.target.value)}
            placeholder="Drive folder ID or URL (for when Google Sign-In is enabled)"
            className="flex-1 rounded border px-3 py-2 font-mono text-sm"
          />
          <button onClick={handleSave} className="rounded bg-gray-600 px-4 py-2 text-sm text-white hover:bg-gray-700">
            Save
          </button>
        </div>
        {saved && <p className="mb-3 text-sm text-green-600">Drive folder ID saved.</p>}

        <div className="rounded bg-gray-50 p-3 text-xs text-gray-600">
          <p className="font-medium">Why it doesn't work with DEV Login:</p>
          <p className="mt-1">
            Google Drive requires your personal OAuth credentials to upload files to your folder.
            The service account on Cloud Run doesn't have Drive storage quota for personal Gmail accounts.
            Once Google Sign-In is enabled in Firebase Auth, the system will use your Google token to
            upload directly to your Drive.
          </p>
        </div>
      </div>
    </div>
  )
}

export default SettingsPage
