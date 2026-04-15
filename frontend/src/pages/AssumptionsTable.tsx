import { useEffect, useState } from 'react'
import { api } from '../services/api'

interface Assumption {
  id: string
  key: string
  display_name: string
  category: string
  type: string
  value: unknown
  version: number
}

interface Props {
  projectId: string
}

function AssumptionsTable({ projectId }: Props) {
  const [assumptions, setAssumptions] = useState<Assumption[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [newRow, setNewRow] = useState({ key: '', display_name: '', category: '', type: 'number', value: '' })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  useEffect(() => {
    api.get<Assumption[]>(`/projects/${projectId}/assumptions`)
      .then(setAssumptions)
      .finally(() => setLoading(false))
  }, [projectId])

  const handleAdd = async () => {
    if (!newRow.key.trim()) return
    const assumption = await api.post<Assumption>(`/projects/${projectId}/assumptions`, {
      ...newRow,
      value: newRow.type === 'boolean' ? newRow.value === 'true' : newRow.value,
    })
    setAssumptions((prev) => [...prev, assumption])
    setNewRow({ key: '', display_name: '', category: '', type: 'number', value: '' })
    setShowAdd(false)
  }

  const handleSaveEdit = async (id: string) => {
    const updated = await api.put<Assumption>(`/projects/${projectId}/assumptions/${id}`, { value: editValue })
    setAssumptions((prev) => prev.map((a) => (a.id === id ? updated : a)))
    setEditingId(null)
  }

  const handleDelete = async (id: string) => {
    await api.delete(`/projects/${projectId}/assumptions/${id}`)
    setAssumptions((prev) => prev.filter((a) => a.id !== id))
  }

  const formatValue = (a: Assumption) => {
    if (a.type === 'percentage') return `${(Number(a.value) * 100).toFixed(1)}%`
    if (a.type === 'currency') return `$${Number(a.value).toLocaleString()}`
    if (a.type === 'boolean') return a.value ? 'Yes' : 'No'
    return String(a.value ?? '')
  }

  // Group by category
  const categories = [...new Set(assumptions.map((a) => a.category))].sort()

  if (loading) return <p className="text-gray-500">Loading assumptions...</p>

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Assumptions</h2>
        <button
          onClick={() => setShowAdd(true)}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
        >
          Add Assumption
        </button>
      </div>

      {showAdd && (
        <div className="mb-4 flex gap-2 rounded border bg-white p-3">
          <input placeholder="Key" value={newRow.key} onChange={(e) => setNewRow({ ...newRow, key: e.target.value })} className="rounded border px-2 py-1 text-sm" />
          <input placeholder="Name" value={newRow.display_name} onChange={(e) => setNewRow({ ...newRow, display_name: e.target.value })} className="rounded border px-2 py-1 text-sm" />
          <input placeholder="Category" value={newRow.category} onChange={(e) => setNewRow({ ...newRow, category: e.target.value })} className="rounded border px-2 py-1 text-sm" />
          <select value={newRow.type} onChange={(e) => setNewRow({ ...newRow, type: e.target.value })} className="rounded border px-2 py-1 text-sm">
            <option value="number">Number</option>
            <option value="currency">Currency</option>
            <option value="percentage">Percentage</option>
            <option value="text">Text</option>
            <option value="boolean">Boolean</option>
            <option value="date">Date</option>
          </select>
          <input placeholder="Value" value={newRow.value} onChange={(e) => setNewRow({ ...newRow, value: e.target.value })} className="rounded border px-2 py-1 text-sm" />
          <button onClick={handleAdd} className="rounded bg-green-600 px-3 py-1 text-sm text-white">Save</button>
          <button onClick={() => setShowAdd(false)} className="text-sm text-gray-500">Cancel</button>
        </div>
      )}

      {categories.length === 0 ? (
        <div className="rounded border-2 border-dashed border-gray-300 p-8 text-center text-gray-500">
          No assumptions yet. Click "Add Assumption" to start.
        </div>
      ) : (
        categories.map((cat) => (
          <div key={cat} className="mb-6">
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">{cat}</h3>
            <table className="w-full rounded border bg-white text-sm">
              <thead>
                <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                  <th className="px-4 py-2">Key</th>
                  <th className="px-4 py-2">Name</th>
                  <th className="px-4 py-2">Type</th>
                  <th className="px-4 py-2">Value</th>
                  <th className="px-4 py-2">v</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {assumptions.filter((a) => a.category === cat).map((a) => (
                  <tr key={a.id} className="border-b last:border-0">
                    <td className="px-4 py-2 font-mono text-xs">{a.key}</td>
                    <td className="px-4 py-2">{a.display_name}</td>
                    <td className="px-4 py-2 text-xs text-gray-500">{a.type}</td>
                    <td className="px-4 py-2">
                      {editingId === a.id ? (
                        <input
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && handleSaveEdit(a.id)}
                          onBlur={() => handleSaveEdit(a.id)}
                          className="w-full rounded border px-2 py-0.5 text-sm"
                          autoFocus
                        />
                      ) : (
                        <span
                          onClick={() => { setEditingId(a.id); setEditValue(String(a.value ?? '')) }}
                          className="cursor-pointer rounded px-1 hover:bg-blue-50"
                        >
                          {formatValue(a)}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-400">{a.version}</td>
                    <td className="px-4 py-2">
                      <button onClick={() => handleDelete(a.id)} className="text-xs text-red-500 hover:text-red-700">Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))
      )}
    </div>
  )
}

export default AssumptionsTable
