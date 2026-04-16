import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../services/api'

interface Scenario {
  id: string; name: string; code_name: string; version: number
  values: Record<string, unknown>
  table_data: Record<string, Record<string, unknown>[]>
}

interface ScenarioSummary { id: string; name: string; code_name: string; version: number }

function ScenarioEditor() {
  const { projectId, scenarioId } = useParams<{ projectId: string; scenarioId: string }>()
  const navigate = useNavigate()
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [scenarios, setScenarios] = useState<ScenarioSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editValues, setEditValues] = useState<Record<string, string>>({})
  const [showNewScenario, setShowNewScenario] = useState(false)
  const [newName, setNewName] = useState('')
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  useEffect(() => {
    if (projectId) {
      api.get<ScenarioSummary[]>(`/projects/${projectId}/scenarios`).then(setScenarios).catch(() => {})
    }
  }, [projectId])

  useEffect(() => {
    if (projectId && scenarioId) {
      api.get<Scenario>(`/projects/${projectId}/scenarios/${scenarioId}`)
        .then((s) => {
          setScenario(s)
          const ev: Record<string, string> = {}
          for (const [k, v] of Object.entries(s.values)) { ev[k] = String(v ?? '') }
          setEditValues(ev)
        })
        .finally(() => setLoading(false))
    }
  }, [projectId, scenarioId])

  const handleSave = async () => {
    if (!projectId || !scenarioId) return
    setSaving(true)
    try {
      // Convert string values back to proper types
      const values: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(editValues)) {
        const num = Number(v)
        values[k] = v === '' ? null : isNaN(num) ? v : num
      }
      await api.put(`/projects/${projectId}/scenarios/${scenarioId}`, { values })
      setMessage({ text: 'Scenario saved.', type: 'success' })
      // Refresh
      const updated = await api.get<Scenario>(`/projects/${projectId}/scenarios/${scenarioId}`)
      setScenario(updated)
    } catch {
      setMessage({ text: 'Save failed.', type: 'error' })
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(null), 3000)
    }
  }

  const handleCreateScenario = async () => {
    if (!projectId || !newName.trim()) return
    const result = await api.post<{ id: string }>(`/projects/${projectId}/scenarios`, {
      name: newName,
      clone_from_id: scenarioId,
    })
    setShowNewScenario(false)
    setNewName('')
    navigate(`/projects/${projectId}/scenarios/${result.id}`)
  }

  const handleCalculate = async () => {
    if (!projectId || !scenarioId) return
    setMessage({ text: 'Calculating...', type: 'success' })
    try {
      const result = await api.post<{ success: boolean; outputs: Record<string, unknown> }>(
        `/projects/${projectId}/calculate?scenario_id=${scenarioId}`, {}
      )
      if (result.success) {
        const dl = (result.outputs as Record<string, unknown>).download_url as string | null
        if (dl && dl.startsWith('http')) {
          window.open(dl, '_blank')
        }
        setMessage({ text: 'Calculation complete! File downloaded.', type: 'success' })
      } else {
        setMessage({ text: 'Calculation failed.', type: 'error' })
      }
    } catch {
      setMessage({ text: 'Calculation error.', type: 'error' })
    }
    setTimeout(() => setMessage(null), 5000)
  }

  if (loading) return <div className="p-8"><p>Loading scenario...</p></div>
  if (!scenario) return <div className="p-8"><p>Scenario not found.</p></div>

  // Group values by prefix
  const groups: Record<string, string[]> = {}
  for (const key of Object.keys(editValues)) {
    const category = key.includes('_') ? key.split('_').slice(0, -1).join(' ') : 'General'
    const cat = category.charAt(0).toUpperCase() + category.slice(1)
    groups[cat] = groups[cat] ?? []
    groups[cat]!.push(key)
  }

  return (
    <div className="p-8">
      {message && (
        <div className={`mb-4 rounded p-3 text-sm ${message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
          {message.text}
        </div>
      )}

      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{scenario.name}</h1>
          <p className="text-sm text-gray-500">Version {scenario.version} | Code: {scenario.code_name}</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowNewScenario(true)} className="rounded border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50">
            Clone Scenario
          </button>
          <button onClick={handleSave} disabled={saving}
            className="rounded bg-blue-600 px-4 py-2 text-sm text-white hover:bg-blue-700 disabled:opacity-50">
            {saving ? 'Saving...' : 'Save Values'}
          </button>
          <button onClick={handleCalculate}
            className="rounded bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700">
            Calculate
          </button>
        </div>
      </div>

      {showNewScenario && (
        <div className="mb-4 flex gap-2 rounded border bg-white p-3">
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="New scenario name (e.g. Optimistic)"
            className="flex-1 rounded border px-3 py-2 text-sm" onKeyDown={(e) => e.key === 'Enter' && handleCreateScenario()} />
          <button onClick={handleCreateScenario} className="rounded bg-blue-600 px-4 py-2 text-sm text-white">Create</button>
          <button onClick={() => setShowNewScenario(false)} className="text-sm text-gray-500">Cancel</button>
        </div>
      )}

      {/* Scenario tabs */}
      <div className="mb-6 flex gap-2 border-b pb-2">
        {scenarios.map((s) => (
          <button key={s.id} onClick={() => navigate(`/projects/${projectId}/scenarios/${s.id}`)}
            className={`rounded-t px-3 py-1.5 text-sm ${s.id === scenarioId ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            {s.name} <span className="text-xs opacity-60">v{s.version}</span>
          </button>
        ))}
      </div>

      {/* Values editor */}
      {Object.keys(editValues).length === 0 ? (
        <div className="rounded border-2 border-dashed border-gray-300 p-12 text-center text-gray-500">
          No values in this scenario. Apply a template group to populate it.
        </div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groups).sort().map(([category, keys]) => (
            <div key={category}>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-gray-500">{category}</h3>
              <div className="rounded border bg-white">
                {keys.sort().map((key) => (
                  <div key={key} className="flex items-center border-b px-4 py-2 last:border-0">
                    <span className="w-1/2 font-mono text-xs text-gray-600">{key}</span>
                    <input
                      value={editValues[key] ?? ''}
                      onChange={(e) => setEditValues({ ...editValues, [key]: e.target.value })}
                      className="w-1/2 rounded border px-2 py-1 text-sm"
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Table data */}
      {Object.keys(scenario.table_data).length > 0 && (
        <div className="mt-8">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">Tables</h3>
          {Object.entries(scenario.table_data).map(([key, rows]) => (
            <div key={key} className="mb-4 rounded border bg-white">
              <div className="border-b px-4 py-2 font-medium">{key} ({rows.length} rows)</div>
              {rows.length > 0 && (
                <div className="overflow-x-auto p-2">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b text-left text-gray-500">
                        {Object.keys(rows[0] ?? {}).map((col) => <th key={col} className="px-2 py-1">{col}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.slice(0, 20).map((row, i) => (
                        <tr key={i} className="border-b last:border-0">
                          {Object.values(row).map((v, j) => <td key={j} className="px-2 py-1">{String(v ?? '')}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {rows.length > 20 && <p className="px-2 py-1 text-xs text-gray-400">...and {rows.length - 20} more rows</p>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ScenarioEditor
