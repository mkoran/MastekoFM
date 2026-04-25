import { useEffect, useRef, useState } from 'react'
import { api } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

interface ModelSummary {
  id: string
  name: string
  code_name: string
  version: number
  input_tab_count: number
  output_tab_count: number
  calc_tab_count: number
  created_at: string
  updated_at: string
}

export default function ExcelTemplatesPage() {
  const { token } = useAuth()
  const [templates, setTemplates] = useState<ModelSummary[]>([])
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)
  const [uploading, setUploading] = useState(false)
  const [name, setName] = useState('')
  const [codeName, setCodeName] = useState('')
  const [description, setDescription] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => {
    api.get<ModelSummary[]>('/models').then(setTemplates).catch(() => setTemplates([]))
  }

  useEffect(load, [])

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0]
    if (!file) {
      setMessage({ text: 'Pick an .xlsx file first', type: 'error' })
      return
    }
    if (!name) {
      setMessage({ text: 'Name is required', type: 'error' })
      return
    }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('name', name)
      fd.append('code_name', codeName)
      fd.append('description', description)
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
      setName('')
      setCodeName('')
      setDescription('')
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
    if (!confirm(`Delete Excel Template "${n}"? Projects pinned to it will still reference the deleted template_id.`)) return
    try {
      await api.delete(`/models/${id}`)
      load()
    } catch {
      setMessage({ text: 'Delete failed', type: 'error' })
    }
  }

  return (
    <div className="p-6">
      <h1 className="mb-1 text-2xl font-semibold text-gray-900">Excel Templates</h1>
      <p className="mb-4 text-sm text-gray-600">
        Upload a .xlsx with tabs prefixed <code className="rounded bg-gray-100 px-1">I_</code> (inputs), <code className="rounded bg-gray-100 px-1">O_</code> (outputs), and any other name (calc tabs). Case-sensitive.
      </p>

      {message && (
        <div className={`mb-4 rounded px-4 py-2 ${message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          {message.text}
        </div>
      )}

      <div className="mb-6 rounded border bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-gray-700">Upload a new Template</h2>
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
          {uploading ? 'Uploading…' : 'Upload Template'}
        </button>
      </div>

      <div className="overflow-x-auto rounded border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs text-gray-600">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Code</th>
              <th className="px-3 py-2">Version</th>
              <th className="px-3 py-2">I_ tabs</th>
              <th className="px-3 py-2">O_ tabs</th>
              <th className="px-3 py-2">Calc tabs</th>
              <th className="px-3 py-2">Updated</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {templates.map((t) => (
              <tr key={t.id} className="border-t">
                <td className="px-3 py-2 font-medium">{t.name}</td>
                <td className="px-3 py-2 text-gray-500">{t.code_name}</td>
                <td className="px-3 py-2">v{t.version}</td>
                <td className="px-3 py-2">{t.input_tab_count}</td>
                <td className="px-3 py-2">{t.output_tab_count}</td>
                <td className="px-3 py-2">{t.calc_tab_count}</td>
                <td className="px-3 py-2 text-xs text-gray-500">{new Date(t.updated_at).toLocaleString()}</td>
                <td className="px-3 py-2 text-right">
                  <button onClick={() => handleDelete(t.id, t.name)} className="text-xs text-red-500 hover:underline">
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {templates.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-6 text-center text-sm text-gray-500">
                  No Excel Templates yet. Upload one above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
