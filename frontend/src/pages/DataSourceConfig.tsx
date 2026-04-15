import { useEffect, useState } from 'react'
import { api } from '../services/api'

interface DataSource {
  id: string
  name: string
  type: string
  sync_status: string
  last_synced_at: string | null
  sync_error: string | null
  field_mappings: { source_field: string; assumption_key: string }[]
}

interface DiscoveredField {
  name: string
  inferred_type: string
  sample_value: unknown
}

interface Props {
  projectId: string
}

function DataSourceConfig({ projectId }: Props) {
  const [sources, setSources] = useState<DataSource[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [newSource, setNewSource] = useState({ name: '', type: 'csv' })
  const [airtableConfig, setAirtableConfig] = useState({ base_id: '', table_name: '', api_key: '' })
  const [csvFile, setCsvFile] = useState<File | null>(null)
  const [discoveredFields, setDiscoveredFields] = useState<DiscoveredField[]>([])
  const [mappings, setMappings] = useState<Record<string, string>>({})
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null)
  const [syncing, setSyncing] = useState<string | null>(null)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const base = `/projects/${projectId}/datasources`

  useEffect(() => {
    api.get<DataSource[]>(base).then(setSources).finally(() => setLoading(false))
  }, [projectId])

  const handleCreate = async () => {
    if (!newSource.name.trim()) return
    const config: Record<string, string> = {}

    if (newSource.type === 'airtable') {
      Object.assign(config, airtableConfig)
    } else if (csvFile) {
      const buf = await csvFile.arrayBuffer()
      config.file_content_b64 = btoa(String.fromCharCode(...new Uint8Array(buf)))
    }

    const ds = await api.post<DataSource>(base, { name: newSource.name, type: newSource.type, config })
    setSources((prev) => [...prev, ds])
    setActiveSourceId(ds.id)
    setShowAdd(false)
    setNewSource({ name: '', type: 'csv' })
    setCsvFile(null)

    // Auto-discover fields
    try {
      const fields = await api.post<DiscoveredField[]>(`${base}/${ds.id}/discover`, {})
      setDiscoveredFields(fields)
    } catch {
      setMessage({ text: 'Field discovery failed. Check config.', type: 'error' })
    }
  }

  const handleSaveMappings = async (sourceId: string) => {
    const fieldMappings = Object.entries(mappings)
      .filter(([, key]) => key.trim())
      .map(([source_field, assumption_key]) => ({ source_field, assumption_key }))

    await api.put(`${base}/${sourceId}`, { field_mappings: fieldMappings })
    setMessage({ text: 'Mappings saved.', type: 'success' })
    setTimeout(() => setMessage(null), 3000)
  }

  const handleSync = async (sourceId: string) => {
    setSyncing(sourceId)
    try {
      const result = await api.post<{ success: boolean; synced_count: number; errors: string[] }>(
        `${base}/${sourceId}/sync`, {}
      )
      if (result.success) {
        setMessage({ text: `Synced ${result.synced_count} fields.`, type: 'success' })
      } else {
        setMessage({ text: `Synced ${result.synced_count} fields with errors: ${result.errors.join(', ')}`, type: 'error' })
      }
      // Refresh sources
      const updated = await api.get<DataSource[]>(base)
      setSources(updated)
    } catch {
      setMessage({ text: 'Sync failed.', type: 'error' })
    } finally {
      setSyncing(null)
      setTimeout(() => setMessage(null), 5000)
    }
  }

  const handleDelete = async (sourceId: string) => {
    await api.delete(`${base}/${sourceId}`)
    setSources((prev) => prev.filter((s) => s.id !== sourceId))
    if (activeSourceId === sourceId) {
      setActiveSourceId(null)
      setDiscoveredFields([])
    }
  }

  if (loading) return <p className="text-gray-500">Loading data sources...</p>

  return (
    <div>
      {message && (
        <div className={`mb-4 rounded p-3 text-sm ${message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          {message.text}
        </div>
      )}

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Data Sources</h2>
        <button onClick={() => setShowAdd(true)} className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700">
          Add Data Source
        </button>
      </div>

      {showAdd && (
        <div className="mb-6 rounded border bg-white p-4">
          <div className="mb-3 flex gap-3">
            <input placeholder="Name" value={newSource.name} onChange={(e) => setNewSource({ ...newSource, name: e.target.value })}
              className="rounded border px-3 py-2 text-sm" />
            <select value={newSource.type} onChange={(e) => setNewSource({ ...newSource, type: e.target.value })}
              className="rounded border px-3 py-2 text-sm">
              <option value="csv">CSV</option>
              <option value="excel">Excel</option>
              <option value="airtable">Airtable</option>
            </select>
          </div>

          {(newSource.type === 'csv' || newSource.type === 'excel') && (
            <div className="mb-3">
              <input type="file" accept={newSource.type === 'csv' ? '.csv' : '.xlsx,.xls'}
                onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)} className="text-sm" />
            </div>
          )}

          {newSource.type === 'airtable' && (
            <div className="mb-3 flex gap-2">
              <input placeholder="Base ID" value={airtableConfig.base_id}
                onChange={(e) => setAirtableConfig({ ...airtableConfig, base_id: e.target.value })}
                className="rounded border px-2 py-1 text-sm" />
              <input placeholder="Table Name" value={airtableConfig.table_name}
                onChange={(e) => setAirtableConfig({ ...airtableConfig, table_name: e.target.value })}
                className="rounded border px-2 py-1 text-sm" />
              <input placeholder="API Key" type="password" value={airtableConfig.api_key}
                onChange={(e) => setAirtableConfig({ ...airtableConfig, api_key: e.target.value })}
                className="rounded border px-2 py-1 text-sm" />
            </div>
          )}

          <div className="flex gap-2">
            <button onClick={handleCreate} className="rounded bg-blue-600 px-4 py-2 text-sm text-white">Create & Discover</button>
            <button onClick={() => setShowAdd(false)} className="text-sm text-gray-500">Cancel</button>
          </div>
        </div>
      )}

      {/* Source list */}
      {sources.length === 0 && !showAdd ? (
        <div className="rounded border-2 border-dashed border-gray-300 p-8 text-center text-gray-500">
          No data sources yet.
        </div>
      ) : (
        <div className="space-y-3">
          {sources.map((ds) => (
            <div key={ds.id} className="rounded border bg-white p-4">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium">{ds.name}</span>
                  <span className="ml-2 rounded bg-gray-100 px-2 py-0.5 text-xs text-gray-600">{ds.type}</span>
                  <span className={`ml-2 text-xs ${ds.sync_status === 'error' ? 'text-red-600' : ds.sync_status === 'syncing' ? 'text-blue-600' : 'text-gray-400'}`}>
                    {ds.sync_status}
                  </span>
                  {ds.last_synced_at && (
                    <span className="ml-2 text-xs text-gray-400">
                      Last sync: {new Date(ds.last_synced_at).toLocaleString()}
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => { setActiveSourceId(ds.id); setDiscoveredFields([]) }}
                    className="text-xs text-blue-600 hover:underline">Map Fields</button>
                  <button onClick={() => handleSync(ds.id)} disabled={syncing === ds.id}
                    className="rounded bg-green-600 px-3 py-1 text-xs text-white hover:bg-green-700 disabled:opacity-50">
                    {syncing === ds.id ? 'Syncing...' : 'Sync'}
                  </button>
                  <button onClick={() => handleDelete(ds.id)} className="text-xs text-red-500 hover:text-red-700">Delete</button>
                </div>
              </div>
              {ds.sync_error && <p className="mt-1 text-xs text-red-600">{ds.sync_error}</p>}
              {ds.field_mappings.length > 0 && (
                <div className="mt-2 text-xs text-gray-500">
                  Mappings: {ds.field_mappings.map((m) => `${m.source_field} → ${m.assumption_key}`).join(', ')}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Field mapping panel */}
      {activeSourceId && (
        <div className="mt-6 rounded border bg-white p-4">
          <h3 className="mb-3 font-medium">Field Mapping</h3>
          {discoveredFields.length === 0 ? (
            <p className="text-sm text-gray-500">Click "Map Fields" on a source, then discover fields.</p>
          ) : (
            <>
              <table className="mb-3 w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs font-medium uppercase text-gray-500">
                    <th className="py-2">Source Field</th>
                    <th className="py-2">Type</th>
                    <th className="py-2">Sample</th>
                    <th className="py-2">Map to Assumption Key</th>
                  </tr>
                </thead>
                <tbody>
                  {discoveredFields.map((f) => (
                    <tr key={f.name} className="border-b">
                      <td className="py-2 font-mono text-xs">{f.name}</td>
                      <td className="py-2 text-xs text-gray-500">{f.inferred_type}</td>
                      <td className="py-2 text-xs text-gray-400">{String(f.sample_value ?? '')}</td>
                      <td className="py-2">
                        <input
                          placeholder="assumption_key"
                          value={mappings[f.name] ?? ''}
                          onChange={(e) => setMappings({ ...mappings, [f.name]: e.target.value })}
                          className="w-full rounded border px-2 py-1 text-xs"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <button onClick={() => handleSaveMappings(activeSourceId)}
                className="rounded bg-blue-600 px-4 py-2 text-sm text-white">
                Save Mappings
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default DataSourceConfig
