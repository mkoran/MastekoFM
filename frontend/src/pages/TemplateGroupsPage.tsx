import { useEffect, useState } from 'react'
import { api } from '../services/api'

interface Template { id: string; name: string }
interface TemplateGroup { id: string; name: string; description: string; code_name: string; template_ids: string[] }

function TemplateGroupsPage() {
  const [groups, setGroups] = useState<TemplateGroup[]>([])
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', code_name: '', template_ids: [] as string[] })
  const [editId, setEditId] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      api.get<TemplateGroup[]>('/template-groups'),
      api.get<Template[]>('/templates'),
    ]).then(([g, t]) => { setGroups(g); setTemplates(t) }).finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    if (!form.name.trim()) return
    if (editId) {
      await api.put(`/template-groups/${editId}`, form)
    } else {
      await api.post('/template-groups', form)
    }
    const updated = await api.get<TemplateGroup[]>('/template-groups')
    setGroups(updated)
    setShowCreate(false)
    setEditId(null)
    setForm({ name: '', description: '', code_name: '', template_ids: [] })
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this template group?')) return
    await api.delete(`/template-groups/${id}`)
    setGroups((prev) => prev.filter((g) => g.id !== id))
  }

  const startEdit = (g: TemplateGroup) => {
    setForm({ name: g.name, description: g.description, code_name: g.code_name, template_ids: g.template_ids })
    setEditId(g.id)
    setShowCreate(true)
  }

  if (loading) return <div className="p-8"><p>Loading...</p></div>

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Template Groups</h1>
        <button onClick={() => { setShowCreate(true); setEditId(null); setForm({ name: '', description: '', code_name: '', template_ids: [] }) }}
          className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">New Group</button>
      </div>

      {showCreate && (
        <div className="mb-6 rounded border bg-white p-4">
          <h3 className="mb-3 font-medium">{editId ? 'Edit' : 'New'} Template Group</h3>
          <div className="mb-3 grid grid-cols-3 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">Code Name</label>
              <input value={form.code_name} onChange={(e) => setForm({ ...form, code_name: e.target.value })} placeholder="auto-generated" className="w-full rounded border px-3 py-2 text-sm font-mono" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">Description</label>
              <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full rounded border px-3 py-2 text-sm" />
            </div>
          </div>
          <div className="mb-3">
            <label className="mb-1 block text-xs font-medium text-gray-600">Templates in Group</label>
            <div className="flex flex-wrap gap-2">
              {templates.map((t) => (
                <label key={t.id} className="flex items-center gap-1 rounded border px-2 py-1 text-xs">
                  <input type="checkbox" checked={form.template_ids.includes(t.id)}
                    onChange={(e) => {
                      if (e.target.checked) setForm({ ...form, template_ids: [...form.template_ids, t.id] })
                      else setForm({ ...form, template_ids: form.template_ids.filter((id) => id !== t.id) })
                    }} />
                  {t.name}
                </label>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={handleSave} className="rounded bg-blue-600 px-4 py-2 text-sm text-white">Save</button>
            <button onClick={() => { setShowCreate(false); setEditId(null) }} className="text-sm text-gray-500">Cancel</button>
          </div>
        </div>
      )}

      {groups.length === 0 ? (
        <div className="rounded border-2 border-dashed border-gray-300 p-12 text-center text-gray-500">
          No template groups yet. Create one to bundle templates together.
        </div>
      ) : (
        <table className="w-full rounded border bg-white text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Code</th>
              <th className="px-4 py-3">Description</th>
              <th className="px-4 py-3">Templates</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <tr key={g.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{g.name}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-500">{g.code_name}</td>
                <td className="px-4 py-3 text-gray-500">{g.description}</td>
                <td className="px-4 py-3 text-center">{g.template_ids.length}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <button onClick={() => startEdit(g)} className="text-xs text-blue-600 hover:underline">Edit</button>
                    <button onClick={() => handleDelete(g.id)} className="text-xs text-red-500 hover:underline">Delete</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default TemplateGroupsPage
