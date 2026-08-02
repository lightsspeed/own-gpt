const API_BASE = 'http://localhost:8000/api/v1'

export interface BriefTrigger {
  id: string
  title: string
  description: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  domain: string
  metric_name: string
  metric_value: number
  threshold: number
  direction: string
  snapshot_id: string
  created_at: string
}

export interface BriefDomain {
  domain: string
  score: number
  previous_score: number | null
  trend: string
  finding_count: number
  weight: number
}

export interface DailyBrief {
  date: string
  overall_health: number | null
  health_change: number | null
  health_domains: BriefDomain[]
  new_critical_findings: number
  new_high_findings: number
  total_findings: number
  findings_delta: number
  triggers: BriefTrigger[]
  top_finding: string
  calibration_note: string
  retrieval_note: string
  routing_note: string
  recommendations_generated: number
  experiments_awaiting: number
  snapshot_id: string | null
  generated_at: string
  note?: string
}

export interface SnapshotLineage {
  artifact_id: string
  created_at: string
  parent_type: string
}

export interface EvaluationSnapshot {
  id: string
  previous_snapshot_id: string | null
  timestamp: string
  record_count: number
  event_count: number
  avg_confidence: number | null
  accept_rate: number | null
  ece: number | null
  ece_change_pct: number | null
  findings_count: number
  critical_findings: number
  high_findings: number
  medium_findings: number
  low_findings: number
  knowledge_gap_count: number
  weak_chunk_count: number
  calibration_drift_count: number
  health_scores: Record<string, number>
  intent_distribution: Record<string, number>
  change_summary: Record<string, any>
  findings_delta: number
  confidence_delta: number | null
  lineage: SnapshotLineage | null
}

export interface AutomationRun {
  id: string
  job_type: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | string
  started_at: string
  completed_at: string
  duration_ms: number
  records_processed: number
  findings_generated: number
  error: string | null
  snapshot_id: string | null
  lineage: SnapshotLineage | null
}

export interface AutomationSchedule {
  job_type: string
  cadence: string
  enabled: boolean
  description: string
  timeout_minutes: number
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`HTTP ${res.status} — ${path}`)
  return res.json() as Promise<T>
}

export const automationApi = {
  async getBriefLatest(): Promise<DailyBrief> {
    return get<DailyBrief>('/automation/brief/latest')
  },

  async getSnapshots(limit: number = 10): Promise<EvaluationSnapshot[]> {
    return get<EvaluationSnapshot[]>(`/automation/snapshots?limit=${limit}`)
  },

  async getSnapshot(snapshotId: string): Promise<EvaluationSnapshot> {
    return get<EvaluationSnapshot>(`/automation/snapshots/${encodeURIComponent(snapshotId)}`)
  },

  async getDiff(snapshotId: string): Promise<EvaluationSnapshot> {
    return get<EvaluationSnapshot>(`/automation/snapshots/${encodeURIComponent(snapshotId)}/diff`)
  },

  async getHistory(limit: number = 25): Promise<AutomationRun[]> {
    return get<AutomationRun[]>(`/automation/history?limit=${limit}`)
  },

  async getSchedules(): Promise<AutomationSchedule[]> {
    return get<AutomationSchedule[]>('/automation/schedules')
  },

  async runDailyEvaluation(): Promise<AutomationRun> {
    const res = await fetch(`${API_BASE}/automation/run/daily-evaluation`, { method: 'POST' })
    if (!res.ok) throw new Error(`HTTP ${res.status} — /automation/run/daily-evaluation`)
    return res.json() as Promise<AutomationRun>
  },
}
