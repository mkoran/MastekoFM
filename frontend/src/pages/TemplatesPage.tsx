import { useEffect, useState } from 'react'
import { api } from '../services/api'

interface Column { name: string; type: string }
interface KeyValue { key: string; display_name: string; category: string; type: string; default_value: unknown }
interface TableDef { key: string; display_name: string; category: string; columns: Column[] }
interface Template { id: string; name: string; description: string; key_values: KeyValue[]; tables: TableDef[] }

function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Template | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  useEffect(() => {
    loadTemplates()
  }, [])

  const loadTemplates = () => {
    api.get<Template[]>('/templates').then(setTemplates).finally(() => setLoading(false))
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this template? This cannot be undone.')) return
    await api.delete(`/templates/${id}`)
    setTemplates((prev) => prev.filter((t) => t.id !== id))
  }

  const handleSeed = async () => {
    await api.post('/templates/seed', {})
    loadTemplates()
  }

  if (loading) return <div className="p-8"><p className="text-gray-500">Loading templates...</p></div>

  return (
    <div className="p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Assumption Templates</h1>
        <div className="flex gap-2">
          <button onClick={handleSeed} className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50">
            Seed Defaults
          </button>
          <button onClick={() => { setShowCreate(true); setEditing(null) }}
            className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700">
            New Template
          </button>
        </div>
      </div>

      {(showCreate || editing) && (
        <TemplateEditor
          template={editing}
          onSave={() => { setShowCreate(false); setEditing(null); loadTemplates() }}
          onCancel={() => { setShowCreate(false); setEditing(null) }}
        />
      )}

      {templates.length === 0 ? (
        <div className="rounded border-2 border-dashed border-gray-300 p-12 text-center">
          <p className="text-gray-500">No templates yet. Click "Seed Defaults" for pre-built templates or create your own.</p>
        </div>
      ) : (
        <table className="w-full rounded border bg-white text-sm">
          <thead>
            <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Description</th>
              <th className="px-4 py-3">Key-Values</th>
              <th className="px-4 py-3">Tables</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((t) => (
              <tr key={t.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{t.name}</td>
                <td className="px-4 py-3 text-gray-500">{t.description}</td>
                <td className="px-4 py-3 text-center">{t.key_values.length}</td>
                <td className="px-4 py-3 text-center">{t.tables.length}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <button onClick={() => { setEditing(t); setShowCreate(false) }} className="text-xs text-blue-600 hover:underline">Edit</button>
                    <button onClick={() => handleDelete(t.id)} className="text-xs text-red-500 hover:underline">Delete</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Template details accordion */}
      {templates.map((t) => (
        <details key={t.id} className="mt-4 rounded border bg-white">
          <summary className="cursor-pointer px-4 py-3 font-medium hover:bg-gray-50">{t.name} — Details</summary>
          <div className="border-t px-4 py-3">
            {t.key_values.length > 0 && (
              <div className="mb-4">
                <h4 className="mb-2 text-xs font-semibold uppercase text-gray-500">Key-Value Assumptions</h4>
                <table className="w-full text-xs">
                  <thead><tr className="border-b text-left text-gray-400"><th className="py-1">Key</th><th>Name</th><th>Category</th><th>Type</th><th>Default</th></tr></thead>
                  <tbody>
                    {t.key_values.map((kv) => (
                      <tr key={kv.key} className="border-b last:border-0">
                        <td className="py-1 font-mono">{kv.key}</td><td>{kv.display_name}</td>
                        <td>{kv.category}</td><td>{kv.type}</td><td>{String(kv.default_value ?? '—')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {t.tables.length > 0 && (
              <div>
                <h4 className="mb-2 text-xs font-semibold uppercase text-gray-500">Table Assumptions</h4>
                {t.tables.map((tbl) => (
                  <div key={tbl.key} className="mb-2 rounded bg-gray-50 p-2">
                    <span className="font-medium">{tbl.display_name}</span>
                    <span className="ml-2 text-xs text-gray-400">({tbl.category})</span>
                    <span className="ml-2 text-xs text-gray-400">
                      Columns: {tbl.columns.map((c) => `${c.name}(${c.type})`).join(', ')}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </details>
      ))}
    </div>
  )
}

function TemplateEditor({ template, onSave, onCancel }: {
  template: Template | null; onSave: () => void; onCancel: () => void
}) {
  const [name, setName] = useState(template?.name ?? '')
  const [description, setDescription] = useState(template?.description ?? '')
  const [keyValues, setKeyValues] = useState<KeyValue[]>(template?.key_values ?? [])
  const [tables, setTables] = useState<TableDef[]>(template?.tables ?? [])
  const [saving, setSaving] = useState(false)

  const addKeyValue = () => setKeyValues([...keyValues, { key: '', display_name: '', category: '', type: 'number', default_value: null }])
  const addTable = () => setTables([...tables, { key: '', display_name: '', category: '', columns: [{ name: '', type: 'text' }] }])

  const handleSave = async () => {
    if (!name.trim()) return
    setSaving(true)
    try {
      const payload = { name, description, key_values: keyValues, tables }
      if (template) {
        await api.put(`/templates/${template.id}`, payload)
      } else {
        await api.post('/templates', payload)
      }
      onSave()
    } finally { setSaving(false) }
  }

  return (
    <div className="mb-6 rounded border bg-white p-4">
      <h3 className="mb-4 text-lg font-medium">{template ? 'Edit Template' : 'New Template'}</h3>

      <div className="mb-4 grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-600">Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded border px-3 py-2 text-sm" placeholder="Multifamily Acquisition" />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-600">Description</label>
          <input value={description} onChange={(e) => setDescription(e.target.value)} className="w-full rounded border px-3 py-2 text-sm" placeholder="Standard multifamily model..." />
        </div>
      </div>

      {/* Key-Values */}
      <div className="mb-4">
        <div className="mb-2 flex items-center justify-between">
          <h4 className="text-sm font-medium text-gray-700">Key-Value Assumptions</h4>
          <button onClick={addKeyValue} className="text-xs text-blue-600 hover:underline">+ Add</button>
        </div>
        {keyValues.map((kv, i) => (
          <div key={i} className="mb-1 flex gap-2">
            <input placeholder="key" value={kv.key} onChange={(e) => { const n = [...keyValues]; n[i] = { ...kv, key: e.target.value }; setKeyValues(n) }} className="rounded border px-2 py-1 text-xs font-mono" />
            <input placeholder="Display Name" value={kv.display_name} onChange={(e) => { const n = [...keyValues]; n[i] = { ...kv, display_name: e.target.value }; setKeyValues(n) }} className="rounded border px-2 py-1 text-xs" />
            <input placeholder="Category" value={kv.category} onChange={(e) => { const n = [...keyValues]; n[i] = { ...kv, category: e.target.value }; setKeyValues(n) }} className="rounded border px-2 py-1 text-xs" />
            <select value={kv.type} onChange={(e) => { const n = [...keyValues]; n[i] = { ...kv, type: e.target.value }; setKeyValues(n) }} className="rounded border px-2 py-1 text-xs">
              <option value="number">Number</option><option value="currency">Currency</option>
              <option value="percentage">Percentage</option><option value="text">Text</option>
              <option value="boolean">Boolean</option><option value="date">Date</option>
            </select>
            <button onClick={() => setKeyValues(keyValues.filter((_, j) => j !== i))} className="text-xs text-red-500">x</button>
          </div>
        ))}
      </div>

      {/* Tables */}
      <div className="mb-4">
        <div className="mb-2 flex items-center justify-between">
          <h4 className="text-sm font-medium text-gray-700">Table Assumptions</h4>
          <button onClick={addTable} className="text-xs text-blue-600 hover:underline">+ Add</button>
        </div>
        {tables.map((tbl, i) => (
          <div key={i} className="mb-3 rounded bg-gray-50 p-3">
            <div className="mb-2 flex gap-2">
              <input placeholder="key" value={tbl.key} onChange={(e) => { const n = [...tables]; n[i] = { ...tbl, key: e.target.value }; setTables(n) }} className="rounded border px-2 py-1 text-xs font-mono" />
              <input placeholder="Display Name" value={tbl.display_name} onChange={(e) => { const n = [...tables]; n[i] = { ...tbl, display_name: e.target.value }; setTables(n) }} className="rounded border px-2 py-1 text-xs" />
              <input placeholder="Category" value={tbl.category} onChange={(e) => { const n = [...tables]; n[i] = { ...tbl, category: e.target.value }; setTables(n) }} className="rounded border px-2 py-1 text-xs" />
              <button onClick={() => setTables(tables.filter((_, j) => j !== i))} className="text-xs text-red-500">x</button>
            </div>
            <p className="mb-1 text-xs text-gray-500">Columns:</p>
            {tbl.columns.map((col, ci) => (
              <div key={ci} className="mb-1 ml-4 flex gap-2">
                <input placeholder="column name" value={col.name} onChange={(e) => {
                  const n = [...tables]; const cols = [...tbl.columns]; cols[ci] = { ...col, name: e.target.value }; n[i] = { ...tbl, columns: cols }; setTables(n)
                }} className="rounded border px-2 py-0.5 text-xs font-mono" />
                <select value={col.type} onChange={(e) => {
                  const n = [...tables]; const cols = [...tbl.columns]; cols[ci] = { ...col, type: e.target.value }; n[i] = { ...tbl, columns: cols }; setTables(n)
                }} className="rounded border px-1 py-0.5 text-xs">
                  <option value="text">Text</option><option value="number">Number</option>
                  <option value="currency">Currency</option><option value="percentage">%</option><option value="date">Date</option>
                </select>
                <button onClick={() => {
                  const n = [...tables]; n[i] = { ...tbl, columns: tbl.columns.filter((_, j) => j !== ci) }; setTables(n)
                }} className="text-xs text-red-500">x</button>
              </div>
            ))}
            <button onClick={() => {
              const n = [...tables]; n[i] = { ...tbl, columns: [...tbl.columns, { name: '', type: 'text' }] }; setTables(n)
            }} className="ml-4 text-xs text-blue-600 hover:underline">+ column</button>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <button onClick={handleSave} disabled={saving} className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50">
          {saving ? 'Saving...' : 'Save Template'}
        </button>
        <button onClick={onCancel} className="rounded border px-4 py-2 text-sm text-gray-600">Cancel</button>
      </div>
    </div>
  )
}

export default TemplatesPage
