import { useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

/**
 * Sprint UX-01-15 + UX-01-16: Models page now shows the Model's URL with an
 * "Open in Sheets" button (UX-01-15), and supports inline editing of the
 * underlying Drive file id (UX-01-16). Archive/Unarchive added too.
 */

interface ModelSummary {
  id: string
  name: string
  code_name: string
  version: number
  input_tab_count: number
  output_tab_count: number
  calc_tab_count: number
  archived: boolean
  drive_url: string | null
  created_by_email: string | null
  created_at: string
  updated_at: string
}

interface ModelDetail extends ModelSummary {
  drive_file_id: string | null
}

export default function ModelsPage() {
  const { token } = useAuth()
  const [models, setModels] = useState<ModelSummary[]>([])
  const [editing, setEditing] = useState<{ id: string; drive_file_id: string } | null>(null)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [uploading, setUploading] = useState(false)
  const [name, setName] = useState('')
  const [codeName, setCodeName] = useState('')
  const [description, setDescription] = useState('')
  const [showArchived, setShowArchived] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => {
    const qs = showArchived ? '?include_archived=true' : ''
    api.get<ModelSummary[]>(`/models${qs}`).then(setModels).catch(() => setModels([]))
  }
  useEffect(load, [showArchived])

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0]
    if (!file) { setMessage({ text: 'Pick an .xlsx file first', type: 'error' }); return }
    if (!name) { setMessage({ text: 'Name is required', type: 'error' }); return }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file); fd.append('name', name)
      fd.append('code_name', codeName); fd.append('description', description)
      const resp = await fetch('/api/models', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({ detail: resp.statusText }))
        throw new Error(body.detail || 'Upload failed')
      }
      const created = await resp.json()
      setMessage({
        text: `Uploaded: ${created.name} (${created.input_tabs.length} I_ tabs, ${created.output_tabs.length} O_ tabs, ${created.calc_tabs.length} calc tabs)`,
        type: 'success',
      })
      setName(''); setCodeName(''); setDescription('')
      if (fileRef.current) fileRef.current.value = ''
      load()
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'Upload failed', type: 'error' })
    } finally {
      setUploading(false)
      setTimeout(() => setMessage(null), 6000)
    }
  }

  const handleDelete = async (id: string, n: string) => {
    if (!confirm(`Delete Model "${n}"? Projects pinned to it will still reference the deleted id.`)) return
    try { await api.delete(`/models/${id}`); load() }
    catch { setMessage({ text: 'Delete failed', type: 'error' }) }
  }

  const handleArchive = async (id: string, n: string) => {
    if (!confirm(`Archive Model "${n}"?`)) return
    try { await api.post(`/models/${id}/archive`, {}); load() }
    catch { setMessage({ text: 'Archive failed', type: 'error' }) }
  }
  const handleUnarchive = async (id: string) => {
    try { await api.post(`/models/${id}/unarchive`, {}); load() }
    catch { setMessage({ text: 'Unarchive failed', type: 'error' }) }
  }

  const startEdit = async (m: ModelSummary) => {
    // Need full doc to know current drive_file_id
    const detail = await api.get<ModelDetail>(`/models/${m.id}`)
    setEditing({ id: m.id, drive_file_id: detail.drive_file_id ?? '' })
  }
  const saveEdit = async () => {
    if (!editing) return
    try {
      await api.put(`/models/${editing.id}`, { drive_file_id: editing.drive_file_id })
      setMessage({ text: 'Drive file id updated', type: 'success' })
      setEditing(null)
      load()
    } catch (err) {
      setMessage({ text: err instanceof Error ? err.message : 'Update failed', type: 'error' })
    }
  }

  return (
    <div className="p-6">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="mb-1 text-2xl font-semibold text-gray-900">Models</h1>
          <p className="text-sm text-gray-600">
            Upload a .xlsx with tabs prefixed <code className="rounded bg-gray-100 px-1">I_</code> (inputs), <code className="rounded bg-gray-100 px-1">O_</code> (outputs), and any other name (calc). Case-sensitive.
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs text-gray-600">
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
          Show archived
        </label>
      </div>

      {message && (
        <div className={`mb-4 rounded px-4 py-2 ${message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          {message.text}
        </div>
      )}

      <div className="mb-6 rounded border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">Upload a new Model</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="block text-xs text-gray-600">
            Name
            <input className="mt-1 w-full rounded border px-2 py-1 text-sm" value={name} onChange={(e) => setName(e.target.value)} placeholder="Construction-to-Perm v1" />
          </label>
          <label className="block text-xs text-gray-600">
            Code name (optional)
            <input className="mt-1 w-full rounded border px-2 py-1 text-sm" value={codeName} onChange={(e) => setCodeName(e.target.value)} placeholder="cons_to_perm_v1" />
          </label>
          <label className="col-span-full block text-xs text-gray-600">
            Description
            <input className="mt-1 w-full rounded border px-2 py-1 text-sm" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Short description" />
          </label>
          <label className="col-span-full block text-xs text-gray-600">
            .xlsx file
            <input ref={fileRef} type="file" accept=".xlsx" className="mt-1 block w-full text-sm" />
          </label>
        </div>
        <button
          onClick={handleUpload}
          disabled={uploading}
          className="mt-3 rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {uploading ? 'Uploading…' : 'Upload Model'}
        </button>
      </div>

      <div className="overflow-x-auto rounded border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs text-gray-600">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Code</th>
              <th className="px-3 py-2">v</th>
              <th className="px-3 py-2">I_</th>
              <th className="px-3 py-2">O_</th>
              <th className="px-3 py-2">calc</th>
              <th className="px-3 py-2">URL</th>
              <th className="px-3 py-2">Created By</th>
              <th className="px-3 py-2">Updated</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {models.map((t) => (
              <tr key={t.id} className={`border-t ${t.archived ? 'text-gray-400 italic' : ''}`}>
                <td className="px-3 py-2 font-medium">{t.name}</td>
                <td className="px-3 py-2 text-gray-500">{t.code_name}</td>
                <td className="px-3 py-2">v{t.version}</td>
                <td className="px-3 py-2">{t.input_tab_count}</td>
                <td className="px-3 py-2">{t.output_tab_count}</td>
                <td className="px-3 py-2">{t.calc_tab_count}</td>
                <td className="px-3 py-2">
                  {editing?.id === t.id ? (
                    <div className="flex items-center gap-1">
                      <input
                        className="w-44 rounded border px-1 py-0.5 text-xs"
                        placeholder="drive file id"
                        value={editing.drive_file_id}
                        onChange={(e) => setEditing({ ...editing, drive_file_id: e.target.value })}
                      />
                      <button onClick={saveEdit} className="rounded bg-blue-600 px-2 py-0.5 text-xs text-white">Save</button>
                      <button onClick={() => setEditing(null)} className="text-xs text-gray-500">×</button>
                    </div>
                  ) : t.drive_url ? (
                    <div className="flex items-center gap-2">
                      <a href={t.drive_url} target="_blank" rel="noreferrer" className="rounded bg-green-600 px-2 py-0.5 text-xs text-white hover:bg-green-700">
                        Open in Sheets
                      </a>
                      <button onClick={() => startEdit(t)} className="text-xs text-blue-600 hover:underline">edit</button>
                    </div>
                  ) : (
                    <button onClick={() => startEdit(t)} className="text-xs text-blue-600 hover:underline">+ set Drive id</button>
                  )}
                </td>
                <td className="px-3 py-2 text-xs">{t.created_by_email ?? '—'}</td>
                <td className="px-3 py-2 text-xs text-gray-500">{new Date(t.updated_at).toLocaleString()}</td>
                <td className="px-3 py-2">
                  <span className={`rounded px-2 py-0.5 text-xs ${t.archived ? 'bg-gray-100 text-gray-500' : 'bg-green-100 text-green-700'}`}>
                    {t.archived ? 'archived' : 'active'}
                  </span>
                </td>
                <td className="px-3 py-2 text-right space-x-2">
                  {t.archived ? (
                    <button onClick={() => handleUnarchive(t.id)} className="text-xs text-blue-500 hover:underline">Unarchive</button>
                  ) : (
                    <button onClick={() => handleArchive(t.id, t.name)} className="text-xs text-yellow-600 hover:underline">Archive</button>
                  )}
                  <button onClick={() => handleDelete(t.id, t.name)} className="text-xs text-red-500 hover:underline">Delete</button>
                </td>
              </tr>
            ))}
            {models.length === 0 && (
              <tr>
                <td colSpan={11} className="px-3 py-6 text-center text-sm text-gray-500">
                  No Models yet. Upload one above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
