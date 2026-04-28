import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

/**
 * Sprint G2: Workspace settings page. Minimal MVP — name/description/archive
 * + members list with add/remove. Permissions are NOT enforced yet (members
 * is recorded only). Roles + permissions are a separate sprint.
 */

interface WorkspaceDetail {
  id: string
  name: string
  code_name: string
  description: string
  members: string[]
  member_count: number
  drive_folder_id: string | null
  drive_folder_url: string | null
  archived: boolean
  created_by: string
  created_by_email: string | null
  created_at: string
  updated_at: string
}

// Sprint I-2 — Airtable connections
interface ConnectionSummary {
  id: string
  name: string
  kind: 'airtable'
  metadata: Record<string, string>
}

export default function WorkspaceSettingsPage() {
  const { workspaceId } = useParams<{ workspaceId: string }>()
  const { token } = useAuth()
  const [ws, setWs] = useState<WorkspaceDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [newMember, setNewMember] = useState('')
  const [saving, setSaving] = useState(false)
  // Sprint I-2 — Airtable connections
  const [connections, setConnections] = useState<ConnectionSummary[]>([])
  const [connName, setConnName] = useState('')
  const [connSecret, setConnSecret] = useState('')
  const [connBaseId, setConnBaseId] = useState('')
  const [savingConn, setSavingConn] = useState(false)

  const load = () => {
    if (!workspaceId || !token) return
    api.get<WorkspaceDetail>(`/workspaces/${workspaceId}`)
      .then((d) => {
        setWs(d)
        setName(d.name)
        setDescription(d.description)
      })
      .catch((e) => setError(String(e)))
    // Sprint I-2 — load connections in parallel
    api.get<ConnectionSummary[]>(`/workspaces/${workspaceId}/connections`)
      .then(setConnections)
      .catch(() => setConnections([]))
  }
  useEffect(load, [workspaceId, token])

  // Sprint I-2 ── Airtable connection handlers
  const handleAddAirtableConnection = async () => {
    if (!workspaceId) return
    if (!connName.trim() || !connSecret.trim() || !connBaseId.trim()) {
      setError('Name, API key, and Base ID are all required')
      return
    }
    setSavingConn(true)
    try {
      await api.post(`/workspaces/${workspaceId}/connections`, {
        name: connName.trim(),
        kind: 'airtable',
        secret: connSecret.trim(),
        metadata: { base_id: connBaseId.trim() },
      })
      setConnName('')
      setConnSecret('')
      setConnBaseId('')
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'add connection failed')
    } finally {
      setSavingConn(false)
    }
  }

  const handleDeleteConnection = async (connId: string, name: string) => {
    if (!workspaceId) return
    if (!confirm(`Delete connection "${name}"? Packs that reference it will fail to pull.`)) return
    try {
      await api.delete(`/workspaces/${workspaceId}/connections/${connId}`)
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'delete connection failed')
    }
  }

  const handleSaveMeta = async () => {
    if (!workspaceId) return
    setSaving(true)
    try {
      await api.put(`/workspaces/${workspaceId}`, { name, description })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleAddMember = async () => {
    if (!workspaceId || !newMember.trim()) return
    try {
      await api.put(`/workspaces/${workspaceId}`, { members_add: [newMember.trim()] })
      setNewMember('')
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'add member failed')
    }
  }

  const handleRemoveMember = async (uid: string) => {
    if (!workspaceId) return
    if (!confirm(`Remove ${uid} from this workspace?`)) return
    try {
      await api.put(`/workspaces/${workspaceId}`, { members_remove: [uid] })
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'remove member failed')
    }
  }

  const handleArchive = async () => {
    if (!workspaceId || !ws) return
    if (!confirm(`Archive workspace "${ws.name}"?`)) return
    try {
      await api.post(`/workspaces/${workspaceId}/archive`, {})
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'archive failed')
    }
  }

  const handleUnarchive = async () => {
    if (!workspaceId) return
    try {
      await api.post(`/workspaces/${workspaceId}/unarchive`, {})
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'unarchive failed')
    }
  }

  if (!ws) {
    return (
      <div className="p-6 text-sm text-gray-500">
        {error ? <p className="text-red-600">{error}</p> : 'Loading workspace…'}
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold text-gray-900">🏢 {ws.name}</h1>
            {ws.archived && (
              <span className="rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-500 italic">archived</span>
            )}
          </div>
          <p className="mt-1 text-xs text-gray-500">
            <code className="rounded bg-gray-100 px-1">{ws.code_name}</code> · created by {ws.created_by_email ?? ws.created_by} on {new Date(ws.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {ws.drive_folder_url && (
            <a href={ws.drive_folder_url} target="_blank" rel="noreferrer" className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50">
              📁 Drive folder
            </a>
          )}
          {ws.archived ? (
            <button onClick={handleUnarchive} className="rounded border border-blue-300 px-3 py-1.5 text-sm text-blue-700 hover:bg-blue-50">
              Unarchive
            </button>
          ) : (
            <button onClick={handleArchive} className="rounded border border-yellow-300 px-3 py-1.5 text-sm text-yellow-700 hover:bg-yellow-50">
              Archive
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Metadata */}
        <div className="rounded border bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">Workspace metadata</h2>
          <label className="mb-2 block text-xs text-gray-600">
            Name
            <input className="mt-1 w-full rounded border px-2 py-1 text-sm" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="mb-3 block text-xs text-gray-600">
            Description
            <textarea
              className="mt-1 w-full rounded border px-2 py-1 text-sm"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </label>
          <button
            onClick={handleSaveMeta}
            disabled={saving || (name === ws.name && description === ws.description)}
            className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>

        {/* Members */}
        <div className="rounded border bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-gray-700">
            Members ({ws.member_count})
            <span className="ml-2 text-xs font-normal text-gray-500">
              (permissions not enforced yet — view-only)
            </span>
          </h2>
          <ul className="mb-3 space-y-1 text-sm">
            {ws.members.map((uid) => (
              <li key={uid} className="flex items-center justify-between rounded border px-2 py-1">
                <span className="font-mono text-xs">{uid}</span>
                {ws.members.length > 1 && (
                  <button onClick={() => handleRemoveMember(uid)} className="text-xs text-red-500 hover:underline">
                    Remove
                  </button>
                )}
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-2">
            <input
              className="flex-1 rounded border px-2 py-1 text-sm"
              placeholder="user uid (Firebase auth uid)"
              value={newMember}
              onChange={(e) => setNewMember(e.target.value)}
            />
            <button
              onClick={handleAddMember}
              disabled={!newMember.trim()}
              className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              Add
            </button>
          </div>
        </div>
      </div>

      {/* Sprint I-2 — Airtable connections */}
      <div className="mt-6 rounded border bg-white p-4">
        <h2 className="mb-1 text-sm font-semibold text-gray-700">
          🔌 Connections
          <span className="ml-2 text-xs font-normal text-gray-500">
            (used by AssumptionPacks with Source = Pull)
          </span>
        </h2>
        <p className="mb-3 text-xs text-gray-500">
          Add an Airtable connection to pull pack values directly from a base.
          Get a Personal Access Token at{' '}
          <a
            href="https://airtable.com/create/tokens"
            target="_blank"
            rel="noreferrer"
            className="text-blue-600 hover:underline"
          >
            airtable.com/create/tokens
          </a>{' '}
          (scopes: <code>data.records:read</code>; access: the bases you want
          to pull from). Your API key is encrypted at rest with KMS and never
          returned by any endpoint.
        </p>

        <ul className="mb-4 space-y-1 text-sm">
          {connections.length === 0 && (
            <li className="rounded border border-dashed px-3 py-2 text-xs text-gray-400">
              No connections yet.
            </li>
          )}
          {connections.map((c) => (
            <li
              key={c.id}
              className="flex items-center justify-between rounded border px-3 py-2"
            >
              <div>
                <div className="font-medium">{c.name}</div>
                <div className="text-xs text-gray-500">
                  {c.kind} · base{' '}
                  <code className="rounded bg-gray-100 px-1">
                    {c.metadata?.base_id ?? '—'}
                  </code>{' '}
                  · id <code className="rounded bg-gray-100 px-1">{c.id}</code>
                </div>
              </div>
              <button
                onClick={() => handleDeleteConnection(c.id, c.name)}
                className="text-xs text-red-500 hover:underline"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>

        <div className="rounded border bg-gray-50 p-3">
          <h3 className="mb-2 text-xs font-semibold text-gray-700">
            + Add Airtable connection
          </h3>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
            <label className="text-xs text-gray-600">
              Name
              <input
                className="mt-1 w-full rounded border px-2 py-1 text-sm"
                placeholder="My CRE Pipeline"
                value={connName}
                onChange={(e) => setConnName(e.target.value)}
              />
            </label>
            <label className="text-xs text-gray-600">
              Base ID
              <input
                className="mt-1 w-full rounded border px-2 py-1 text-sm font-mono"
                placeholder="appXXXXXXXXXXXXXX"
                value={connBaseId}
                onChange={(e) => setConnBaseId(e.target.value)}
              />
            </label>
            <label className="text-xs text-gray-600">
              API key (PAT)
              <input
                className="mt-1 w-full rounded border px-2 py-1 text-sm font-mono"
                type="password"
                placeholder="patXXXXXXXXXXXXXXXX..."
                value={connSecret}
                onChange={(e) => setConnSecret(e.target.value)}
              />
            </label>
          </div>
          <div className="mt-3 flex justify-end">
            <button
              onClick={handleAddAirtableConnection}
              disabled={
                savingConn ||
                !connName.trim() ||
                !connSecret.trim() ||
                !connBaseId.trim()
              }
              className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {savingConn ? 'Saving…' : 'Add connection'}
            </button>
          </div>
        </div>
      </div>

      <p className="mt-4 text-xs text-gray-500">
        <Link to="/projects" className="text-blue-600 hover:underline">← Back to Projects</Link>
      </p>
    </div>
  )
}
