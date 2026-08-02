const API_BASE = 'http://localhost:8000/api/v1'

/* ── Telemetry counters ── */
export interface TelemetryDashboard {
  learning_records: number
  user_events: number
  thumbs_up: number
  thumbs_down: number
  thumb_approval_rate: number
  copies: number
  regenerations: number
  events_by_type: Record<string, number>
  records_by_intent: Record<string, number>
}

/* ── Query intelligence ── */
export interface QueryRow {
  question_hash?: string
  sample?: string
  count?: number
  total?: number
  avg_confidence?: number
  accept_rate?: number
  answer_mode?: string
  last_seen?: string
  failures?: number
  fail_rate?: number
  common_reason?: string
  regens?: number
  copies?: number
  copy_rate?: number
  synthesis_rate?: number
  thumbs_down?: number
}

export interface QueryReport {
  top_queries: QueryRow[]
  lowest_confidence: QueryRow[]
  most_failed: QueryRow[]
  most_regenerated: QueryRow[]
  highest_copy_rate: QueryRow[]
  knowledge_gaps: QueryRow[]
}

/* ── Retrieval ── */
export interface DocRow {
  document?: string
  retrieved_count?: number
  avg_confidence?: number
  accept_rate?: number
}

export interface RetrievalReport {
  per_document: DocRow[]
  per_chunk: DocRow[]
  chunk_quality: { excellent?: number; good?: number; weak?: number; dead?: number }
  top_documents: DocRow[]
  weakest_documents: DocRow[]
}

/* ── Routing ── */
export interface RoutingReport {
  intent_distribution: Record<string, number>
  rule_distribution: Record<string, number>
  confidence_by_intent: { intent?: string; total?: number; avg_confidence?: number; accept_rate?: number; rule_diversity?: number }[]
  rule_vs_llm_rate: Record<string, number>
}

/* ── Behavior ── */
export interface BehaviorReport {
  summary: Record<string, number>
  event_counts: Record<string, number>
  by_intent: { intent?: string; records?: number; thumbs?: number; copies?: number; regens?: number }[]
}

/* ── Trends ── */
export interface TrendsReport {
  daily_volume: { day?: string; queries?: number; unique_questions?: number; novelty_rate?: number }[]
  daily_confidence: { day?: string; avg_confidence?: number; avg_accept?: number; queries?: number }[]
  weekly_growth: Record<string, number | string>
  top_days: { day?: string; queries?: number; avg_confidence?: number }[]
}

/* ── Recommendations ── */
export interface Recommendation {
  id: string
  type?: string
  severity?: string
  confidence?: number
  title: string
  description?: string
  status?: string
  created_at?: string
}

export interface RecommendationsReport {
  knowledge_gaps: Recommendation[]
  weak_chunks: Recommendation[]
  dead_chunks: Recommendation[]
  routing_issues: Recommendation[]
  benchmark_candidates: Recommendation[]
}

/* ── Composite overview ── */
export interface OverviewReport {
  generated_at?: string
  total_records?: number
  total_events?: number
  query?: QueryReport
  retrieval?: RetrievalReport
  routing?: RoutingReport
  behavior?: BehaviorReport
  trends?: TrendsReport
  recommendations?: RecommendationsReport
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`${res.status} ${url}`)
  return await res.json()
}

export const analyticsApi = {
  async getOverview(): Promise<OverviewReport> {
    return fetchJson<OverviewReport>(`${API_BASE}/analytics/overview`)
  },

  async getTelemetryDashboard(): Promise<TelemetryDashboard> {
    return fetchJson<TelemetryDashboard>(`${API_BASE}/telemetry/dashboard`)
  },

  async getAll(): Promise<{ overview: OverviewReport; telemetry: TelemetryDashboard }> {
    const [overview, telemetry] = await Promise.all([this.getOverview(), this.getTelemetryDashboard()])
    return { overview, telemetry }
  },
}
