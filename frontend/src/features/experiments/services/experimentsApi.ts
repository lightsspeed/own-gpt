const API_BASE = 'http://localhost:8000/api/v1'

export interface ParameterChange {
  domain: string
  parameter: string
  baseline: string | number | null
  candidate: string | number | null
  description: string
}

export interface ExperimentDefinition {
  id?: string
  name: string
  hypothesis: string
  parameter_changes: ParameterChange[]
  dataset_size?: number
  dataset_description?: string
  metrics?: string[]
  status?: string
  recommendation_id?: string | null
}

export interface ExperimentResult {
  experiment_id: string
  baseline_metrics: Record<string, number>
  candidate_metrics: Record<string, number>
  deltas: Record<string, { baseline?: number; candidate?: number; absolute?: number; percent?: number }>
  summary: string
  records_processed: number
  duration_ms: number
  completed_at: string
}

export interface ComparisonReport {
  experiment_id: string
  metrics: Record<string, { baseline?: number; candidate?: number; absolute?: number; percent?: number }>
  wins: string[]
  losses: string[]
  unchanged: string[]
  overall_verdict: string
}

export interface DecisionCandidate {
  id: string
  experiment_id: string
  recommendation_id: string | null
  decision: string
  rationale: string
  supporting_metrics: Record<string, number>
  risks: string[]
  status: string
  created_at: string
}

export interface EvaluateResponse {
  experiment: Record<string, unknown>
  result: ExperimentResult
  comparison: ComparisonReport
  decision_candidate: DecisionCandidate
}

async function postJson<T>(url: string, body: unknown, params?: string): Promise<T> {
  const res = await fetch(`${url}${params ?? ''}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => null)
    throw new Error(err?.detail || `${res.status} ${url}`)
  }
  return await res.json()
}

export const experimentsApi = {
  async run(experiment: ExperimentDefinition, limit = 200): Promise<ExperimentResult> {
    return postJson<ExperimentResult>(`${API_BASE}/experiments/run`, experiment, `?limit=${limit}`)
  },

  async compare(experiment: ExperimentDefinition, limit = 200): Promise<ComparisonReport> {
    return postJson<ComparisonReport>(`${API_BASE}/experiments/compare`, experiment, `?limit=${limit}`)
  },

  async evaluate(experiment: ExperimentDefinition, limit = 200): Promise<EvaluateResponse> {
    return postJson<EvaluateResponse>(`${API_BASE}/experiments/evaluate`, experiment, `?limit=${limit}`)
  },
}

export const PARAMETER_DOMAINS = [
  'chunk_size',
  'retriever_top_k',
  'bm25_weight',
  'reranker_model',
  'embedding_model',
  'prompt_version',
  'confidence_threshold',
  'reranker_threshold',
  'custom',
] as const
