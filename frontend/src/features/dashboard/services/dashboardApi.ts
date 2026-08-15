const API_BASE = 'http://localhost:8000/api/v1'

export interface SystemService {
  status: string
  version?: string
  chunk_count?: number
  doc_count?: number
  index_exists?: boolean
  detail?: string
}

export interface SystemStatus {
  status: string
  services: Record<string, SystemService>
}

export interface HealthScores {
  overall_health: number | null
  domains: Record<string, number>
  snapshot_id?: string
  timestamp?: string
  note?: string
}

export interface AutomationRun {
  id: string
  job_type: string
  status: string
  started_at: string
  completed_at?: string
  summary?: string
}

export interface Recommendation {
  id: string
  title: string
  priority: string
  description?: string
}

export interface UsageData {
  records: number
  tokens_in: number
  tokens_out: number
  total_tokens: number
  estimated_cost_usd: number
  cost_per_1k_input: number
  cost_per_1k_output: number
}

export interface DashboardCounters {
  user_events: number
  thumbs_up: number
  thumbs_down: number
  thumb_approval_rate: number
  copies: number
  regenerations: number
  usage?: UsageData
}

export interface DailyBriefData {
  overall_health: number | null
  recommendation_count: number
  degraded_services: number
  running_experiments: number
  automations_completed: number
  knowledge_docs: number
  knowledge_updated: string
  trend: 'up' | 'down' | 'stable'
  recent_events: { time: string; text: string; type: string }[]
  ai_insights: { title: string; description: string; recommendation: string; confidence: string }[]
  running_experiments_list: { name: string; status: string; score?: number }[]
  automations_list: { name: string; status: string }[]
  recommendations_list: Recommendation[]
  health_change?: number | null
  health_domains?: { domain: string; score: number; previous_score: number | null; trend: string }[]
  triggers?: { id: string; title: string; description: string; severity: string; domain: string }[]
  top_finding?: string
}

async function fetchJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 5000)
    const res = await fetch(url, { signal: controller.signal })
    clearTimeout(timer)
    if (!res.ok) return fallback
    return await res.json()
  } catch {
    return fallback
  }
}

export const dashboardApi = {
  async getSystemStatus(): Promise<SystemStatus> {
    return fetchJson<SystemStatus>(`${API_BASE}/system/status`, { status: 'error', services: {} })
  },

  async getHealthScores(): Promise<HealthScores> {
    return fetchJson<HealthScores>(`${API_BASE}/automation/health`, { overall_health: null, domains: {}, note: 'Unavailable' })
  },

  async getSessionCount(): Promise<number> {
    const data = await fetchJson<any[]>(`${API_BASE}/chat/sessions`, [])
    return data?.length ?? 0
  },

  async getCounters(): Promise<DashboardCounters> {
    const data = await fetchJson<any>(`${API_BASE}/telemetry/dashboard`, { user_events: 0, thumbs_up: 0, thumbs_down: 0, thumb_approval_rate: 0, copies: 0, regenerations: 0 })
    return {
      ...data,
      usage: data?.usage ?? { records: 0, tokens_in: 0, tokens_out: 0, total_tokens: 0, estimated_cost_usd: 0, cost_per_1k_input: 0, cost_per_1k_output: 0 },
    }
  },

  async getAutomationHistory(): Promise<AutomationRun[]> {
    return fetchJson<AutomationRun[]>(`${API_BASE}/automation/history`, [])
  },

  async getRecommendations(): Promise<Recommendation[]> {
    return fetchJson<Recommendation[]>(`${API_BASE}/operations/recommendations`, [])
  },

  async getDailyBrief(): Promise<DailyBriefData> {
    const data = await fetchJson<any>(`${API_BASE}/automation/brief`, null)

    // Ensure all fields exist regardless of what the backend returns
    const defaults: DailyBriefData = {
      overall_health: null,
      recommendation_count: 0,
      degraded_services: 0,
      running_experiments: 0,
      automations_completed: 0,
      knowledge_docs: 0,
      knowledge_updated: 'N/A',
      trend: 'stable',
      recent_events: [],
      ai_insights: [],
      running_experiments_list: [],
      automations_list: [],
      recommendations_list: [],
    }

    if (data && data.overall_health != null) {
      return { ...defaults, ...data, recommendations_list: data.recommendations_list ?? [] }
    }

    // Build daily brief from individual endpoints
    const [sys, health, , telem, autoHistory, recs] = await Promise.all([
      this.getSystemStatus(),
      this.getHealthScores(),
      this.getSessionCount(),
      this.getCounters(),
      this.getAutomationHistory(),
      this.getRecommendations(),
    ])

    const brief: DailyBriefData = {
      ...defaults,
      overall_health: health?.overall_health ?? null,
      recommendation_count: recs?.length ?? 0,
      degraded_services: Object.values(sys?.services ?? {}).filter(s => s?.status === 'degraded' || s?.status === 'error').length,
      automations_completed: autoHistory?.filter(a => a?.status === 'completed').length ?? 0,
      knowledge_docs: Object.values(sys?.services ?? {}).reduce((sum, s) => sum + (s?.doc_count ?? s?.chunk_count ?? 0), 0),
      trend: (health?.overall_health ?? 100) >= 80 ? 'up' : (health?.overall_health ?? 100) >= 50 ? 'stable' : 'down',
      recommendations_list: recs ?? [],
    }

    // Build events
    const errorCount = Object.values(sys?.services ?? {}).filter(s => s?.status === 'error').length
    if (errorCount > 0) {
      brief.recent_events.push({ time: 'Now', text: `${errorCount} service(s) reporting errors`, type: 'warning' })
    }
    if ((telem?.thumbs_up ?? 0) > 0) {
      brief.recent_events.push({ time: 'Lifetime', text: `${telem?.thumb_approval_rate ?? 0}% approval rate`, type: 'success' })
    }
    if (health?.overall_health != null) {
      brief.ai_insights.push({
        title: 'System Health',
        description: `Overall health is ${health.overall_health.toFixed(0)}%`,
        recommendation: health.overall_health < 70 ? 'Review degraded services and check recent findings.' : 'No action needed.',
        confidence: 'High',
      })
    }

    return brief
  },
}
