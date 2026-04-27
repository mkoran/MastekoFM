import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { api } from '../services/api'

type StorageKind = 'gcs' | 'drive_xlsx'

interface SeedResult {
  workspace_id?: string
  workspace_code?: string
  project_id?: string
  model_id?: string
  output_template_id?: string
  assumption_pack_id?: string
  created?: string[]
  existing?: string[]
}

function SettingsPage() {
  const { user, googleAccessToken, signInWithGoogle } = useAuth()
  const [driveFolderId, setDriveFolderId] = useState('')
  const [defaultStorageKind, setDefaultStorageKind] = useState<StorageKind>('gcs')
  const [saved, setSaved] = useState(false)
  const [loading, setLoading] = useState(true)
  const [testingGCS, setTestingGCS] = useState(false)
  const [testingDrive, setTestingDrive] = useState(false)
  const [gcsResult, setGcsResult] = useState<{ success: boolean; message?: string; error?: string } | null>(null)
  const [driveResult, setDriveResult] = useState<{ success: boolean; message?: string; error?: string } | null>(null)
  const [seeding, setSeeding] = useState(false)
  const [seedResult, setSeedResult] = useState<SeedResult | null>(null)
  const [seedError, setSeedError] = useState<string | null>(null)

  useEffect(() => {
    api.get<{ drive_root_folder_id: string; default_scenario_storage_kind: StorageKind }>('/settings')
      .then((s) => {
        setDriveFolderId(s.drive_root_folder_id || '')
        setDefaultStorageKind(s.default_scenario_storage_kind || 'gcs')
      })
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    let folderId = driveFolderId.trim()
    const match = folderId.match(/folders\/([a-zA-Z0-9_-]+)/)
    if (match) folderId = match[1] ?? folderId
    setDriveFolderId(folderId)

    await api.put('/settings', {
      drive_root_folder_id: folderId,
      default_scenario_storage_kind: defaultStorageKind,
    })
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

  const handleSeedHelloWorld = async () => {
    if (!googleAccessToken) {
      setSeedError('Sign in with Google first — Hello World needs Drive access to upload the seed files.')
      return
    }
    setSeeding(true)
    setSeedResult(null)
    setSeedError(null)
    try {
      const result = await api.post<SeedResult>('/seed/helloworld', {})
      setSeedResult(result)
    } catch (e) {
      setSeedError(e instanceof Error ? e.message : String(e))
    } finally {
      setSeeding(false)
    }
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

      {/* Sprint G2: One-click Hello World seed */}
      <div className="mb-6 max-w-2xl rounded border bg-white p-6">
        <h2 className="mb-2 text-lg font-medium">Quickstart — seed Hello World</h2>
        <p className="mb-3 text-sm text-gray-600">
          Creates a complete demo: a Project + Model + AssumptionPack + OutputTemplate that
          verify the engine end-to-end. Idempotent — re-running returns the existing record IDs
          rather than duplicating. New to the system?{' '}
          <Link to="/help" className="text-blue-600 hover:underline">Read the manual</Link>.
        </p>
        <button
          onClick={handleSeedHelloWorld}
          disabled={seeding || !googleAccessToken}
          className="rounded bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700 disabled:opacity-50"
        >
          {seeding ? 'Seeding… (Drive uploads ~10–20s)' : '🌱 Seed Hello World'}
        </button>
        {!googleAccessToken && (
          <p className="mt-2 text-xs text-amber-700">
            Sign in with Google first (section below) — the seed needs your Drive access token.
          </p>
        )}
        {seedError && (
          <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
            <strong>Seed failed.</strong> {seedError}
          </div>
        )}
        {seedResult && (
          <div className="mt-3 rounded border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-800">
            <p className="font-medium mb-1">
              {(seedResult.created?.length ?? 0) > 0 ? 'Hello World seeded ✓' : 'Hello World already existed ✓'}
            </p>
            {seedResult.created && seedResult.created.length > 0 && (
              <p className="mb-1">Created: <code className="text-[10px]">{seedResult.created.join(', ')}</code></p>
            )}
            {seedResult.existing && seedResult.existing.length > 0 && (
              <p className="mb-1">Existing: <code className="text-[10px]">{seedResult.existing.join(', ')}</code></p>
            )}
            {seedResult.project_id && (
              <p className="mt-2">
                <Link to={`/projects/${seedResult.project_id}`} className="underline font-medium">
                  → Open the Hello World project
                </Link>
              </p>
            )}
          </div>
        )}
      </div>

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

      {/* Default Scenario storage */}
      <div className="mb-6 max-w-2xl rounded border bg-white p-6">
        <h2 className="mb-3 text-lg font-medium">Where should new Scenarios live?</h2>
        <p className="mb-3 text-sm text-gray-600">
          Each Scenario is a .xlsx containing only the Template's <code className="rounded bg-gray-100 px-1">I_</code> tabs.
          Drive-backed scenarios open in Google Sheets (Office mode) via one click — recommended once Google Sign-In is configured.
          GCS is the simpler fallback that works without any Google credentials.
        </p>
        <label className="flex items-center gap-2 text-sm mb-2">
          <input type="radio" name="storage-kind" value="gcs" checked={defaultStorageKind === 'gcs'}
            onChange={() => setDefaultStorageKind('gcs')} />
          <span><strong>Cloud Storage (GCS)</strong> — Scenario files stored in masteko-fm-outputs bucket. Edit via download/upload.</span>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="radio" name="storage-kind" value="drive_xlsx" checked={defaultStorageKind === 'drive_xlsx'}
            onChange={() => setDefaultStorageKind('drive_xlsx')} />
          <span><strong>Google Drive (.xlsx)</strong> — Scenario files stored in Drive. Click "Edit in Sheets" to open in your browser; saves go back to the same file. Requires Google Sign-In + a Drive root folder below.</span>
        </label>
      </div>

      {/* Google Drive folder */}
      <div className="mb-6 max-w-2xl rounded border bg-white p-6">
        <h2 className="mb-3 text-lg font-medium">Google Drive Root Folder</h2>
        <p className="mb-3 text-sm text-gray-600">
          Scenario files (Drive mode) and calculated output files live under <code className="rounded bg-gray-100 px-1">&lt;root&gt;/MastekoFM/&lt;project&gt;/Inputs/</code> and <code className="rounded bg-gray-100 px-1">.../Outputs/</code>.
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

        {driveFolderId && (
          <div className="mb-3 rounded bg-gray-50 p-3 text-sm">
            <div className="mb-1 text-xs font-semibold text-gray-600">Quick links</div>
            <a
              href={`https://drive.google.com/drive/folders/${driveFolderId}`}
              target="_blank"
              rel="noreferrer"
              className="block text-blue-600 hover:underline"
            >
              Open Root folder in Drive ↗
            </a>
          </div>
        )}

        <div className="flex gap-2">
          <button onClick={handleTestDrive} disabled={testingDrive}
            className="rounded border border-blue-600 px-4 py-2 text-sm text-blue-600 hover:bg-blue-50 disabled:opacity-50">
            {testingDrive ? 'Testing...' : 'Test Drive Connection'}
          </button>
          <button onClick={handleTestGCS} disabled={testingGCS}
            className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50">
            {testingGCS ? 'Testing...' : 'Test Cloud Storage'}
          </button>
          <button
            onClick={signInWithGoogle}
            className="rounded border border-gray-300 px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
            title="Re-sign-in if your Google access token has expired (happens ~every hour)"
          >
            Refresh Google sign-in
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
