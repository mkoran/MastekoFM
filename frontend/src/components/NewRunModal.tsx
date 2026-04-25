/**
 * NewRunModal — the centerpiece of three-way composition.
 *
 * User picks (AssumptionPack, Model, OutputTemplate); the modal validates
 * compatibility live as they pick. On Run, POSTs /api/runs and (for now,
 * sync) navigates to the new RunDetail page with the result.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'

interface AssumptionPackOption {
  id: string
  name: string
  code_name: string
  status: string
}

interface ModelOption {
  id: string
  name: string
  code_name: string
  version: number
  input_tab_count: number
  output_tab_count: number
}

interface OutputTemplateOption {
  id: string
  name: string
  code_name: string
  format: string
  version: number
  m_tab_count: number
  output_tab_count: number
}

interface ValidateResponse {
  compatible: boolean
  errors: string[]
}

interface RunResponse {
  id: string
  status: string
  duration_ms: number | null
  output_download_url: string | null
  warnings: string[]
}

interface Props {
  projectId: string
  onClose: () => void
  onRunComplete?: (runId: string) => void
}

export default function NewRunModal({ projectId, onClose, onRunComplete }: Props) {
  const navigate = useNavigate()
  const [packs, setPacks] = useState<AssumptionPackOption[]>([])
  const [models, setModels] = useState<ModelOption[]>([])
  const [templates, setTemplates] = useState<OutputTemplateOption[]>([])
  const [packId, setPackId] = useState('')
  const [modelId, setModelId] = useState('')
  const [tplId, setTplId] = useState('')
  const [validation, setValidation] = useState<ValidateResponse | null>(null)
  const [validating, setValidating] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load all three lists on mount
  useEffect(() => {
    api.get<AssumptionPackOption[]>(`/projects/${projectId}/assumption-packs`)
      .then((s) => setPacks(s.filter((p) => p.status === 'active')))
      .catch(() => setPacks([]))
    api.get<ModelOption[]>('/models')
      .then(setModels)
      .catch(() => setModels([]))
    api.get<OutputTemplateOption[]>('/output-templates')
      .then(setTemplates)
      .catch(() => setTemplates([]))
  }, [projectId])

  // Re-validate any time the composition changes
  useEffect(() => {
    if (!packId || !modelId || !tplId) {
      setValidation(null)
      return
    }
    setValidating(true)
    setError(null)
    api.post<ValidateResponse>('/runs/validate', {
      assumption_pack_id: packId,
      model_id: modelId,
      output_template_id: tplId,
    })
      .then(setValidation)
      .catch((e) => setError(e instanceof Error ? e.message : 'validation failed'))
      .finally(() => setValidating(false))
  }, [packId, modelId, tplId])

  const handleRun = async () => {
    if (!packId || !modelId || !tplId) return
    setRunning(true)
    setError(null)
    try {
      const run = await api.post<RunResponse>('/runs', {
        project_id: projectId,
        assumption_pack_id: packId,
        model_id: modelId,
        output_template_id: tplId,
      })
      onRunComplete?.(run.id)
      navigate(`/runs/${run.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Run failed to launch')
    } finally {
      setRunning(false)
    }
  }

  const compatible = validation?.compatible === true
  const canRun = packId && modelId && tplId && compatible && !running

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl rounded-lg bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b px-6 py-4">
          <h2 className="text-lg font-semibold text-gray-900">+ New Run</h2>
          <p className="mt-1 text-xs text-gray-500">
            Pick one of each. The platform validates that they're compatible before letting you run.
          </p>
        </div>

        <div className="space-y-4 px-6 py-5">
          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-700">
              <span className="rounded bg-yellow-100 px-1.5 py-0.5 text-yellow-800">Inputs</span>{' '}
              <span className="text-gray-500">(AssumptionPack — the numbers)</span>
            </label>
            <select
              className="w-full rounded border px-3 py-2 text-sm"
              value={packId}
              onChange={(e) => setPackId(e.target.value)}
            >
              <option value="">— pick an AssumptionPack —</option>
              {packs.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            {packs.length === 0 && (
              <p className="mt-1 text-xs text-gray-500">No AssumptionPacks in this project. Create one first.</p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-700">
              <span className="rounded bg-blue-100 px-1.5 py-0.5 text-blue-800">Model</span>{' '}
              <span className="text-gray-500">(the calc engine)</span>
            </label>
            <select
              className="w-full rounded border px-3 py-2 text-sm"
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
            >
              <option value="">— pick a Model —</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name} (v{m.version}, {m.input_tab_count} I_ / {m.output_tab_count} O_)
                </option>
              ))}
            </select>
            {models.length === 0 && (
              <p className="mt-1 text-xs text-gray-500">No Models uploaded. Go to Models page to upload one.</p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold text-gray-700">
              <span className="rounded bg-green-100 px-1.5 py-0.5 text-green-800">Output Template</span>{' '}
              <span className="text-gray-500">(the report shape)</span>
            </label>
            <select
              className="w-full rounded border px-3 py-2 text-sm"
              value={tplId}
              onChange={(e) => setTplId(e.target.value)}
            >
              <option value="">— pick an OutputTemplate —</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.format}, v{t.version}, {t.m_tab_count} M_ / {t.output_tab_count} O_)
                </option>
              ))}
            </select>
            {templates.length === 0 && (
              <p className="mt-1 text-xs text-gray-500">No OutputTemplates uploaded.</p>
            )}
          </div>

          {/* Compatibility status */}
          {validating && (
            <div className="rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
              Validating composition…
            </div>
          )}
          {validation && validation.compatible && (
            <div className="rounded border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-800">
              ✅ Compatible — ready to run
            </div>
          )}
          {validation && !validation.compatible && (
            <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">
              ❌ Not compatible:
              <ul className="mt-1 list-inside list-disc">
                {validation.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </div>
          )}
          {error && (
            <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800">
              {error}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t px-6 py-3">
          <button
            onClick={onClose}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
            disabled={running}
          >
            Cancel
          </button>
          <button
            onClick={handleRun}
            disabled={!canRun}
            className="rounded bg-green-600 px-4 py-1.5 text-sm text-white hover:bg-green-700 disabled:opacity-40"
          >
            {running ? 'Launching…' : '▶ Run'}
          </button>
        </div>
      </div>
    </div>
  )
}
