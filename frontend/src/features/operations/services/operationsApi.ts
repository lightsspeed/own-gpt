const API_BASE = 'http://localhost:8000/api/v1'

export interface FindingRow {
  priority: number
  id: string
  category: string
  severity: string
  title: string
  description: string
  evidence_strength: string
  evidence_confidence: number
  sample_size: number
  trend: string
  root_cause: string
  recommendation_text: string
  created_at: string
  lineage: Record<string, string> | null
}

export interface FindingsWorkspace {
  workspace: string
  total: number
  priority_filters: { severity: string[]; strength: string[] }
  findings: FindingRow[]
}

export interface RecommendationRow {
  id: string
  type: string
  severity: string
  title: string
  description: string
  status: string
  review_notes?: string
  reviewed_at?: string
  finding_id: string
  evidence: Record<string, any>
  lineage: Record<string, string> | null
}

export interface ReviewDecision {
  id: string
  recommendation_id: string
  recommendation_type?: string
  recommendation_title?: string
  decision: string
  reviewer_notes?: string
  created_at?: string
}

export interface RecommendationsWorkspace {
  workspace: string
  total: number
  decisions: ReviewDecision[]
  recommendations: RecommendationRow[]
}

export interface DecisionRow {
  id: string
  experiment_id: string | null
  config_snapshot_id: string | null
  config_version: number | null
  status: string
  name: string
  description: string
  applied_at: string | null
  source: string
  recommendation_type?: string | null
  lineage: Record<string, string> | null
}

export interface DecisionsWorkspace {
  workspace: string
  total: number
  decisions: DecisionRow[]
}

export interface ConfigSnapshot {
  id: string
  version: number
  parent_id: string | null
  name: string
  description: string
  parameters: Record<string, any>
  domains: string[]
  git_commit: string
  created_from_decision_id: string | null
  created_from_experiment_id: string | null
  is_current: boolean
  created_at: string
  lineage: Record<string, string> | null
}

export interface ConfigWorkspace {
  workspace: string
  current: ConfigSnapshot | null
  snapshots: ConfigSnapshot[]
  actions: string[]
}

export interface ConfigDiff {
  snapshot_a_id: string
  snapshot_b_id: string
  a_name: string
  b_name: string
  added: Record<string, any>
  removed: Record<string, any>
  changed: Record<string, { from: any; to: any }>
  unchanged_count: number
}

export interface LineageStep {
  type: string
  data: Record<string, any>
}

export interface ArtifactTrace {
  root_artifact_id: string
  chain: LineageStep[]
  depth: number
}

export interface MemoryEventRow {
  status: string
  at: string
  note: string
}

export interface MemoryFactRow {
  id: string
  fact: string
  scope: string
  source: string
  created_at: string
  status: string
  version: number
  supersedes: string[]
  events: MemoryEventRow[]
}

export interface MemoriesWorkspace {
  workspace: string
  total: number
  active_count: number
  scopes: string[]
  facts: MemoryFactRow[]
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`HTTP ${res.status} — ${path}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status} — ${path}`)
  return res.json() as Promise<T>
}

export const operationsApi = {
  async getFindings(params: { category?: string; severity?: string; min_priority?: number; limit?: number } = {}): Promise<FindingsWorkspace> {
    const qs = new URLSearchParams()
    if (params.category) qs.set('category', params.category)
    if (params.severity) qs.set('severity', params.severity)
    if (params.min_priority) qs.set('min_priority', String(params.min_priority))
    if (params.limit) qs.set('limit', String(params.limit))
    const q = qs.toString()
    return get<FindingsWorkspace>(`/operations/findings${q ? `?${q}` : ''}`)
  },

  async getRecommendations(params: { status?: string; limit?: number } = {}): Promise<RecommendationsWorkspace> {
    const qs = new URLSearchParams()
    if (params.status) qs.set('status', params.status)
    if (params.limit) qs.set('limit', String(params.limit))
    const q = qs.toString()
    return get<RecommendationsWorkspace>(`/operations/recommendations${q ? `?${q}` : ''}`)
  },

  async approveRecommendation(recId: string, notes: string = ''): Promise<any> {
    const qs = new URLSearchParams()
    if (notes) qs.set('reviewer_notes', notes)
    const q = qs.toString()
    return post(`/operations/recommendations/${encodeURIComponent(recId)}/approve${q ? `?${q}` : ''}`)
  },

  async dismissRecommendation(recId: string, notes: string = ''): Promise<any> {
    const qs = new URLSearchParams()
    if (notes) qs.set('reviewer_notes', notes)
    const q = qs.toString()
    return post(`/operations/recommendations/${encodeURIComponent(recId)}/dismiss${q ? `?${q}` : ''}`)
  },

  async getRecommendation(id: string): Promise<{ recommendation: RecommendationRow; finding: FindingRow | null; actions: string[] }> {
    return get(`/operations/recommendations/${encodeURIComponent(id)}`)
  },

  async applyDecision(decisionId: string): Promise<any> {
    const qs = new URLSearchParams()
    qs.set('decision_id', decisionId)
    return post(`/operations/decisions/apply?${qs.toString()}`)
  },

  async getDecisions(params: { status?: string; limit?: number } = {}): Promise<DecisionsWorkspace> {
    const qs = new URLSearchParams()
    if (params.status) qs.set('status', params.status)
    if (params.limit) qs.set('limit', String(params.limit))
    const q = qs.toString()
    return get<DecisionsWorkspace>(`/operations/decisions${q ? `?${q}` : ''}`)
  },

  async getConfigurations(limit: number = 50): Promise<ConfigWorkspace> {
    return get<ConfigWorkspace>(`/operations/configurations?limit=${limit}`)
  },

  async getConfigSnapshots(limit: number = 50): Promise<ConfigSnapshot[]> {
    return get<ConfigSnapshot[]>(`/config/snapshots?limit=${limit}`)
  },

  async createConfigSnapshot(params: { name?: string; description?: string } = {}): Promise<ConfigSnapshot> {
    const qs = new URLSearchParams()
    if (params.name) qs.set('name', params.name)
    if (params.description) qs.set('description', params.description)
    const q = qs.toString()
    return post<ConfigSnapshot>(`/config/snapshots${q ? `?${q}` : ''}`)
  },

  async setCurrentConfig(snapshotId: string): Promise<ConfigSnapshot> {
    return post<ConfigSnapshot>(`/config/current/${encodeURIComponent(snapshotId)}`)
  },

  async rollbackConfig(snapshotId: string): Promise<ConfigSnapshot> {
    return post<ConfigSnapshot>(`/config/rollback/${encodeURIComponent(snapshotId)}`)
  },

  async diffAgainstCurrent(snapshotId: string): Promise<ConfigDiff> {
    return get<ConfigDiff>(`/config/diff/current/${encodeURIComponent(snapshotId)}`)
  },

  async exploreArtifact(artifactId: string): Promise<ArtifactTrace> {
    return get<ArtifactTrace>(`/operations/explore/${encodeURIComponent(artifactId)}`)
  },

  async getMemories(params: { scope?: string; includeSuperseded?: boolean; limit?: number } = {}): Promise<MemoriesWorkspace> {
    const qs = new URLSearchParams()
    if (params.scope) qs.set('scope', params.scope)
    if (params.includeSuperseded) qs.set('include_superseded', 'true')
    if (params.limit) qs.set('limit', String(params.limit))
    const q = qs.toString()
    return get<MemoriesWorkspace>(`/operations/memories${q ? `?${q}` : ''}`)
  },

  async getMemory(factId: string): Promise<MemoryFactRow> {
    return get<MemoryFactRow>(`/operations/memories/${encodeURIComponent(factId)}`)
  },

  async forgetMemory(factId: string, note: string = ''): Promise<{ status: string; fact: MemoryFactRow }> {
    const qs = new URLSearchParams()
    if (note) qs.set('note', note)
    const q = qs.toString()
    return post(`/operations/memories/${encodeURIComponent(factId)}/forget${q ? `?${q}` : ''}`)
  },
}