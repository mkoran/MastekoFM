import { useEffect, useState } from 'react'
import { api } from '../services/api'

interface Column { name: string; type: string }
interface Assumption {
  id: string; key: string; display_name: string; category: string
  type: string; value: unknown; format: string; columns: Column[] | null; version: number
}
interface TableRowData { id: string; row_index: number; data: Record<string, unknown> }
interface Template { id: string; name: string; description: string; key_values: unknown[]; tables: unknown[] }

interface Props { projectId: string }

function AssumptionsTable({ projectId }: Props) {
  const [assumptions, setAssumptions] = useState<Assumption[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [newRow, setNewRow] = useState({ key: '', display_name: '', category: '', type: 'number', value: '', format: 'key_value' })
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [expandedTables, setExpandedTables] = useState<Record<string, TableRowData[]>>({})
  const [templates, setTemplates] = useState<Template[]>([])
  const [showTemplates, setShowTemplates] = useState(false)
  const [applying, setApplying] = useState(false)

  const base = `/projects/${projectId}/assumptions`

  useEffect(() => {
    api.get<Assumption[]>(base).then(setAssumptions).finally(() => setLoading(false))
    api.get<Template[]>('/templates').then(setTemplates).catch(() => {})
  }, [projectId])

  const handleAdd = async () => {
    if (!newRow.key.trim()) return
    const payload: Record<string, unknown> = { ...newRow }
    if (newRow.format === 'key_value') {
      payload.value = newRow.type === 'boolean' ? newRow.value === 'true' : newRow.value
    }
    const assumption = await api.post<Assumption>(base, payload)
    setAssumptions((prev) => [...prev, assumption])
    setNewRow({ key: '', display_name: '', category: '', type: 'number', value: '', format: 'key_value' })
    setShowAdd(false)
  }

  const handleSaveEdit = async (id: string) => {
    const updated = await api.put<Assumption>(`${base}/${id}`, { value: editValue })
    setAssumptions((prev) => prev.map((a) => (a.id === id ? updated : a)))
    setEditingId(null)
  }

  const handleDelete = async (id: string) => {
    await api.delete(`${base}/${id}`)
    setAssumptions((prev) => prev.filter((a) => a.id !== id))
  }

  const handleApplyTemplate = async (templateId: string) => {
    setApplying(true)
    try {
      await api.post(`/projects/${projectId}/apply-template/${templateId}`, {})
      const updated = await api.get<Assumption[]>(base)
      setAssumptions(updated)
      setShowTemplates(false)
    } finally { setApplying(false) }
  }

  // Table row operations
  const loadRows = async (assumptionId: string) => {
    const rows = await api.get<TableRowData[]>(`${base}/${assumptionId}/rows`)
    setExpandedTables((prev) => ({ ...prev, [assumptionId]: rows }))
  }

  const toggleTable = (id: string) => {
    if (expandedTables[id]) {
      setExpandedTables((prev) => { const n = { ...prev }; delete n[id]; return n })
    } else {
      loadRows(id)
    }
  }

  const addTableRow = async (assumptionId: string, columns: Column[]) => {
    const emptyRow: Record<string, unknown> = {}
    columns.forEach((c) => { emptyRow[c.name] = c.type === 'number' || c.type === 'currency' ? 0 : '' })
    const rows = await api.post<TableRowData[]>(`${base}/${assumptionId}/rows`, { rows: [emptyRow] })
    setExpandedTables((prev) => ({ ...prev, [assumptionId]: [...(prev[assumptionId] ?? []), ...rows] }))
  }

  const updateTableCell = async (assumptionId: string, rowId: string, data: Record<string, unknown>) => {
    const updated = await api.put<TableRowData>(`${base}/${assumptionId}/rows/${rowId}`, { data })
    setExpandedTables((prev) => ({
      ...prev,
      [assumptionId]: (prev[assumptionId] ?? []).map((r) => (r.id === rowId ? updated : r)),
    }))
  }

  const deleteTableRow = async (assumptionId: string, rowId: string) => {
    await api.delete(`${base}/${assumptionId}/rows/${rowId}`)
    setExpandedTables((prev) => ({
      ...prev,
      [assumptionId]: (prev[assumptionId] ?? []).filter((r) => r.id !== rowId),
    }))
  }

  const formatValue = (a: Assumption) => {
    if (a.format === 'table') return `[Table: ${a.columns?.length ?? 0} columns]`
    if (a.type === 'percentage') return `${(Number(a.value) * 100).toFixed(1)}%`
    if (a.type === 'currency') return `$${Number(a.value).toLocaleString()}`
    if (a.type === 'boolean') return a.value ? 'Yes' : 'No'
    return String(a.value ?? '')
  }

  const kvAssumptions = assumptions.filter((a) => a.format !== 'table')
  const tableAssumptions = assumptions.filter((a) => a.format === 'table')
  const categories = [...new Set(kvAssumptions.map((a) => a.category))].sort()

  if (loading) return <p className="text-gray-500">Loading assumptions...</p>

  return (
    <div>
      {/* Header with actions */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Assumptions</h2>
        <div className="flex gap-2">
          {templates.length > 0 && (
            <button onClick={() => setShowTemplates(!showTemplates)}
              className="rounded border border-blue-600 px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50">
              Apply Template
            </button>
          )}
          <button onClick={() => setShowAdd(true)} className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700">
            Add Assumption
          </button>
        </div>
      </div>

      {/* Template selector */}
      {showTemplates && (
        <div className="mb-4 rounded border bg-white p-4">
          <h3 className="mb-3 font-medium">Choose a Template</h3>
          <p className="mb-3 text-xs text-gray-500">Applying a template creates key-value assumptions and table structures for your project.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {templates.map((t) => (
              <div key={t.id} className="rounded border p-3">
                <h4 className="font-medium">{t.name}</h4>
                <p className="mt-1 text-xs text-gray-500">{t.description}</p>
                <p className="mt-1 text-xs text-gray-400">{t.key_values.length} values + {t.tables.length} tables</p>
                <button onClick={() => handleApplyTemplate(t.id)} disabled={applying}
                  className="mt-2 rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700 disabled:opacity-50">
                  {applying ? 'Applying...' : 'Apply'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Add assumption form */}
      {showAdd && (
        <div className="mb-4 rounded border bg-white p-3">
          <div className="mb-2 flex gap-2">
            <select value={newRow.format} onChange={(e) => setNewRow({ ...newRow, format: e.target.value })} className="rounded border px-2 py-1 text-sm">
              <option value="key_value">Key-Value</option>
              <option value="table">Table</option>
            </select>
            <input placeholder="Key" value={newRow.key} onChange={(e) => setNewRow({ ...newRow, key: e.target.value })} className="rounded border px-2 py-1 text-sm" />
            <input placeholder="Name" value={newRow.display_name} onChange={(e) => setNewRow({ ...newRow, display_name: e.target.value })} className="rounded border px-2 py-1 text-sm" />
            <input placeholder="Category" value={newRow.category} onChange={(e) => setNewRow({ ...newRow, category: e.target.value })} className="rounded border px-2 py-1 text-sm" />
          </div>
          {newRow.format === 'key_value' && (
            <div className="mb-2 flex gap-2">
              <select value={newRow.type} onChange={(e) => setNewRow({ ...newRow, type: e.target.value })} className="rounded border px-2 py-1 text-sm">
                <option value="number">Number</option><option value="currency">Currency</option>
                <option value="percentage">Percentage</option><option value="text">Text</option>
                <option value="boolean">Boolean</option><option value="date">Date</option>
              </select>
              <input placeholder="Value" value={newRow.value} onChange={(e) => setNewRow({ ...newRow, value: e.target.value })} className="rounded border px-2 py-1 text-sm" />
            </div>
          )}
          <div className="flex gap-2">
            <button onClick={handleAdd} className="rounded bg-green-600 px-3 py-1 text-sm text-white">Save</button>
            <button onClick={() => setShowAdd(false)} className="text-sm text-gray-500">Cancel</button>
          </div>
        </div>
      )}

      {assumptions.length === 0 ? (
        <div className="rounded border-2 border-dashed border-gray-300 p-8 text-center text-gray-500">
          No assumptions yet. Apply a template or add assumptions manually.
        </div>
      ) : (
        <>
          {/* Key-value assumptions grouped by category */}
          {categories.map((cat) => (
            <div key={cat} className="mb-6">
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">{cat}</h3>
              <table className="w-full rounded border bg-white text-sm">
                <thead>
                  <tr className="border-b bg-gray-50 text-left text-xs font-medium uppercase text-gray-500">
                    <th className="px-4 py-2">Key</th><th className="px-4 py-2">Name</th>
                    <th className="px-4 py-2">Type</th><th className="px-4 py-2">Value</th>
                    <th className="px-4 py-2">v</th><th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {kvAssumptions.filter((a) => a.category === cat).map((a) => (
                    <tr key={a.id} className="border-b last:border-0">
                      <td className="px-4 py-2 font-mono text-xs">{a.key}</td>
                      <td className="px-4 py-2">{a.display_name}</td>
                      <td className="px-4 py-2 text-xs text-gray-500">{a.type}</td>
                      <td className="px-4 py-2">
                        {editingId === a.id ? (
                          <input value={editValue} onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSaveEdit(a.id)}
                            onBlur={() => handleSaveEdit(a.id)} className="w-full rounded border px-2 py-0.5 text-sm" autoFocus />
                        ) : (
                          <span onClick={() => { setEditingId(a.id); setEditValue(String(a.value ?? '')) }}
                            className="cursor-pointer rounded px-1 hover:bg-blue-50">{formatValue(a)}</span>
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
          ))}

          {/* Table assumptions */}
          {tableAssumptions.length > 0 && (
            <div className="mt-8">
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Tables</h3>
              {tableAssumptions.map((a) => (
                <div key={a.id} className="mb-4 rounded border bg-white">
                  <div className="flex cursor-pointer items-center justify-between border-b px-4 py-3" onClick={() => toggleTable(a.id)}>
                    <div>
                      <span className="font-medium">{a.display_name}</span>
                      <span className="ml-2 text-xs text-gray-400">{a.category}</span>
                      <span className="ml-2 text-xs text-gray-400">{a.columns?.length ?? 0} columns</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400">v{a.version}</span>
                      <span className="text-gray-400">{expandedTables[a.id] ? '\u25B2' : '\u25BC'}</span>
                    </div>
                  </div>

                  {expandedTables[a.id] && (
                    <div className="p-4">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b text-left text-xs font-medium uppercase text-gray-500">
                            <th className="py-2 pr-2">#</th>
                            {a.columns?.map((col) => (
                              <th key={col.name} className="px-2 py-2">{col.name}<span className="ml-1 text-gray-300">({col.type})</span></th>
                            ))}
                            <th className="py-2"></th>
                          </tr>
                        </thead>
                        <tbody>
                          {(expandedTables[a.id] ?? []).map((row) => (
                            <TableRowEditor
                              key={row.id}
                              row={row}
                              columns={a.columns ?? []}
                              onSave={(data) => updateTableCell(a.id, row.id, data)}
                              onDelete={() => deleteTableRow(a.id, row.id)}
                            />
                          ))}
                        </tbody>
                      </table>
                      <button onClick={() => addTableRow(a.id, a.columns ?? [])}
                        className="mt-2 rounded border border-dashed border-gray-300 px-3 py-1.5 text-xs text-gray-500 hover:border-blue-400 hover:text-blue-600">
                        + Add Row
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function TableRowEditor({ row, columns, onSave, onDelete }: {
  row: TableRowData; columns: Column[]
  onSave: (data: Record<string, unknown>) => void; onDelete: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [data, setData] = useState<Record<string, unknown>>(row.data)

  const handleBlur = () => {
    if (JSON.stringify(data) !== JSON.stringify(row.data)) {
      onSave(data)
    }
    setEditing(false)
  }

  return (
    <tr className="border-b last:border-0" onClick={() => !editing && setEditing(true)}>
      <td className="py-1.5 pr-2 text-xs text-gray-400">{row.row_index}</td>
      {columns.map((col) => (
        <td key={col.name} className="px-2 py-1.5">
          {editing ? (
            <input
              value={String(data[col.name] ?? '')}
              onChange={(e) => setData({ ...data, [col.name]: e.target.value })}
              onBlur={handleBlur}
              onKeyDown={(e) => e.key === 'Enter' && handleBlur()}
              className="w-full rounded border px-1 py-0.5 text-sm"
            />
          ) : (
            <span className="cursor-pointer rounded px-1 text-sm hover:bg-blue-50">
              {col.type === 'currency' ? `$${Number(data[col.name] ?? 0).toLocaleString()}` : String(data[col.name] ?? '')}
            </span>
          )}
        </td>
      ))}
      <td className="py-1.5">
        <button onClick={(e) => { e.stopPropagation(); onDelete() }} className="text-xs text-red-500 hover:text-red-700">x</button>
      </td>
    </tr>
  )
}

export default AssumptionsTable
