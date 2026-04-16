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

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await api.post<{ success: boolean; message?: string; error?: string }>('/settings/test-drive', {})
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

      <div className="max-w-2xl rounded border bg-white p-6">
        <h2 className="mb-4 text-lg font-medium">Google Drive Output Folder</h2>
        <p className="mb-3 text-sm text-gray-600">
          Set the root Google Drive folder where all project outputs will be saved.
          Each project gets a subfolder, and each scenario gets a sub-subfolder.
        </p>
        <div className="mb-3 rounded bg-blue-50 p-3 text-xs text-blue-800">
          <p className="font-medium">Setup:</p>
          <ol className="mt-1 ml-4 list-decimal space-y-0.5">
            <li>Create a folder in Google Drive (e.g. "MastekoFM Outputs")</li>
            <li>Share it with <code className="bg-blue-100 px-1">560873149926-compute@developer.gserviceaccount.com</code> as <strong>Editor</strong></li>
            <li>Paste the folder URL or ID below</li>
            <li>Click Save, then Test Connection</li>
          </ol>
        </div>
        <div className="mb-3 flex gap-2">
          <input
            value={driveFolderId}
            onChange={(e) => setDriveFolderId(e.target.value)}
            placeholder="Folder ID or Drive URL"
            className="flex-1 rounded border px-3 py-2 font-mono text-sm"
          />
          <button onClick={handleSave} className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">
            Save
          </button>
        </div>
        {saved && <p className="mb-3 text-sm text-green-600">Settings saved.</p>}

        <button
          onClick={handleTest}
          disabled={testing || !driveFolderId}
          className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {testing ? 'Testing...' : 'Test Connection'}
        </button>

        {testResult && (
          <div className={`mt-3 rounded p-3 text-sm ${testResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
            {testResult.success ? (
              <div>
                <p className="font-medium">Connection successful!</p>
                <p className="mt-1">{testResult.message}</p>
              </div>
            ) : (
              <div>
                <p className="font-medium">Connection failed</p>
                <p className="mt-1 break-all">{testResult.error}</p>
                <p className="mt-2 text-xs">Make sure the folder is shared with the service account as Editor.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default SettingsPage
