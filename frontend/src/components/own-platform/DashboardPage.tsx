import { useState, useEffect, useCallback } from 'react'
import { cn } from '@/lib/utils'
import {
  MessageSquare, Activity, AlertTriangle, Clock, RefreshCw,
  Zap, Monitor, BookOpen, Beaker, BarChart3, GitBranch, Archive, Cog,
  TrendingUp, TrendingDown, Minus, Sparkles, ChevronRight,
  Lightbulb, FlaskConical, Brain,
} from 'lucide-react'
import { dashboardApi, type DailyBriefData } from '@/features/dashboard/services/dashboardApi'

/* ── Section wrapper ── */
function Section({ title, icon: Icon, children, className }: {
  title: string
  icon?: React.ElementType
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('bg-elevated border border-border/60 rounded-xl p-5', className)}>
      {title && (
        <div className="flex items-center gap-2 mb-4">
          {Icon && <Icon size={16} className="text-muted-foreground" />}
          <h2 className="text-small font-semibold text-foreground uppercase tracking-wider">{title}</h2>
        </div>
      )}
      {children}
    </div>
  )
}

/* ── Status badge ── */
function StatusBadge({ status }: { status: string }) {
  const color = status === 'healthy' || status === 'completed' ? 'text-success' :
                status === 'degraded' || status === 'running' || status === 'medium' ? 'text-warning' :
                status === 'down' || status === 'failed' || status === 'high' ? 'text-danger' : 'text-info'
  return <span className={cn('text-caption font-medium', color)}>{status}</span>
}

function Dot({ status }: { status: string }) {
  const color = status === 'healthy' || status === 'completed' ? 'bg-success' :
                status === 'degraded' || status === 'running' ? 'bg-warning' :
                status === 'down' || status === 'failed' ? 'bg-danger' : 'bg-info'
  return <span className={cn('w-2 h-2 rounded-full shrink-0', color)} />
}

export function DashboardPage() {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [brief, setBrief] = useState<DailyBriefData | null>(null)

  const fetchAll = useCallback(async () => {
    try {
      const b = await dashboardApi.getDailyBrief()
      setBrief(b)
    } catch {
      // keep state
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    fetchAll().finally(() => setLoading(false))
  }, [fetchAll])

  const handleRefresh = () => {
    setRefreshing(true)
    fetchAll().finally(() => setRefreshing(false))
  }

  const trendIcon = brief?.trend === 'up' ? TrendingUp : brief?.trend === 'down' ? TrendingDown : Minus
  const trendColor = brief?.trend === 'up' ? 'text-success' : brief?.trend === 'down' ? 'text-danger' : 'text-muted-foreground'

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-[1320px] mx-auto p-6 space-y-5">
        {/* ── Header ── */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <h1 className="text-h2 text-foreground">Dashboard</h1>
              <p className="text-caption text-muted-foreground mt-0.5">What needs your attention today?</p>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-hover transition-all disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw size={18} className={cn(refreshing && 'animate-spin')} />
          </button>
        </div>

        {/* ── 1. Daily Brief ── */}
        <div className="bg-gradient-to-br from-primary/5 to-transparent border border-primary/10 rounded-xl p-6">
          {loading ? (
            <div className="h-24 bg-muted/20 rounded-lg animate-pulse" />
          ) : (
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-body text-muted-foreground">Good morning</span>
                  <span className="text-body font-medium text-foreground">Akhilesh</span>
                </div>
                <div className="flex items-center gap-2">
                  {trendIcon && (
                    <trendIcon size={18} className={trendColor} />
                  )}
                  <span className="text-title font-semibold text-foreground">
                    {brief?.overall_health != null ? `${brief.overall_health.toFixed(0)}% healthy` : 'Platform status unavailable'}
                  </span>
                </div>
                <div className="flex flex-wrap gap-3 pt-1">
                  {brief && (
                    <>
                      {brief.recommendation_count > 0 && (
                        <span className="flex items-center gap-1.5 text-small text-warning">
                          <AlertTriangle size={14} /> {brief.recommendation_count} recommendation{brief.recommendation_count > 1 ? 's' : ''}
                        </span>
                      )}
                      {brief.degraded_services > 0 && (
                        <span className="flex items-center gap-1.5 text-small text-danger">
                          <AlertTriangle size={14} /> {brief.degraded_services} degraded service{brief.degraded_services > 1 ? 's' : ''}
                        </span>
                      )}
                      {brief.automations_completed > 0 && (
                        <span className="flex items-center gap-1.5 text-small text-info">
                          <GitBranch size={14} /> {brief.automations_completed} automation{brief.automations_completed > 1 ? 's' : ''} completed
                        </span>
                      )}
                    </>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-small font-medium hover:brightness-110 transition-all">
                  Open OwnGPT
                </button>
                <button className="px-4 py-2 rounded-lg bg-elevated border border-border text-foreground text-small font-medium hover:bg-hover transition-all">
                  View Report
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ── 2. KPIs ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {loading ? [1,2,3,4].map(i => (
            <div key={i} className="bg-elevated border border-border/60 rounded-xl p-5 animate-pulse">
              <div className="h-8 w-16 bg-muted/50 rounded" />
              <div className="h-4 w-20 bg-muted/30 rounded mt-2" />
              <div className="h-3 w-12 bg-muted/20 rounded mt-2" />
            </div>
          )) : (
            <>
              <KpiCard icon={MessageSquare} value={brief ? String(brief.recommendation_count + brief.automations_completed + (brief.degraded_services > 0 ? 1 : 0)) : '—'} label="Action Items" trend="Today" status={brief && (brief.recommendation_count > 0 || brief.degraded_services > 0) ? 'Attention needed' : 'Clear'} danger={brief ? brief.recommendation_count > 0 || brief.degraded_services > 0 : false} />
              <KpiCard icon={Activity} value={brief?.overall_health != null ? `${brief.overall_health.toFixed(0)}%` : '—'} label="System Health" trend={brief?.trend ?? '—'} status={brief?.overall_health != null && brief.overall_health >= 80 ? 'Healthy' : brief?.overall_health != null && brief.overall_health >= 50 ? 'Degraded' : 'Critical'} danger={brief?.overall_health != null && brief.overall_health < 50} />
              <KpiCard icon={FlaskConical} value={String(brief?.running_experiments_list?.length ?? 0)} label="Active Experiments" trend="Running" status="See OwnLab" />
              <KpiCard icon={Brain} value={String(brief?.knowledge_docs ?? 0)} label="Knowledge Docs" trend={brief?.knowledge_updated ?? '—'} status="Indexed" />
            </>
          )}
        </div>

        {/* ── 3+4. Service Health + AI Insights ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Service Health */}
          <Section title="Service Health" icon={Monitor}>
            {loading ? (
              <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="h-12 bg-muted/20 rounded-lg animate-pulse" />)}</div>
            ) : (
              <div className="space-y-1">
                <ServiceRow name="API Server" status="healthy" uptime="99.97%" latency="45ms" detail="Last incident: 7 days ago" />
                <ServiceRow name="Pipeline Engine" status="healthy" uptime="99.89%" latency="120ms" detail="Last incident: 2 days ago" />
                <ServiceRow name="Vector Database" status="healthy" uptime="99.95%" latency="32ms" detail="Last incident: 14 days ago" />
                <ServiceRow name="Model Provider" status="degraded" uptime="98.21%" latency="890ms" detail="Provider X — monitoring" />
                <ServiceRow name="Learning Engine" status="healthy" uptime="99.99%" latency="60ms" detail="Last incident: 30 days ago" />
              </div>
            )}
          </Section>

          {/* AI Insights */}
          <Section title="AI Insights" icon={Lightbulb}>
            {loading ? (
              <div className="space-y-3">{[1,2].map(i => <div key={i} className="h-20 bg-muted/20 rounded-lg animate-pulse" />)}</div>
            ) : (
              <div className="space-y-3">
                <InsightCard
                  icon={<BarChart3 size={14} />}
                  title="Model latency increased 18%"
                  description="caused by Provider X"
                  recommendation="Switch traffic to Anthropic"
                  confidence="High"
                  color="text-warning"
                />
                <InsightCard
                  icon={<BookOpen size={14} />}
                  title="Knowledge gap detected"
                  description="3 queries with low confidence in retrieval"
                  recommendation="Add documents on deployment workflows"
                  confidence="Medium"
                  color="text-info"
                />
              </div>
            )}
          </Section>
        </div>

        {/* ── 5+9. Recent Activity + Recommendations ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <Section title="Recent Activity" icon={Activity}>
            {loading ? (
              <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="h-10 bg-muted/20 rounded-lg animate-pulse" />)}</div>
            ) : (
              <div className="space-y-1">
                <ActivityRow icon={<Zap size={14} />} text="Nightly evaluation completed" time="12 min ago" type="evaluation" />
                <ActivityRow icon={<Lightbulb size={14} />} text="Recommendation: upgrade embedding model" time="1h ago" type="recommendation" />
                <ActivityRow icon={<AlertTriangle size={14} />} text="Model provider latency spike detected" time="2h ago" type="incident" />
                <ActivityRow icon={<FlaskConical size={14} />} text="Experiment 'Prompt v2' finished" time="4h ago" type="experiment" />
                <ActivityRow icon={<GitBranch size={14} />} text="Knowledge sync completed" time="6h ago" type="automation" />
              </div>
            )}
          </Section>

          <Section title="Recommendations" icon={Lightbulb}>
            {loading ? (
              <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="h-12 bg-muted/20 rounded-lg animate-pulse" />)}</div>
            ) : (
              <div className="space-y-1">
                <RecRow priority="high" title="Upgrade reranker model" desc="Improves retrieval accuracy by 12%" />
                <RecRow priority="medium" title="Increase chunk size" desc="Better context coverage for technical docs" />
                <RecRow priority="low" title="Remove stale embeddings" desc="Clean up 1,240 unused vectors" />
                {brief?.recommendations_list?.length > 0 && brief.recommendations_list.slice(0, 3).map(r => (
                  <RecRow key={r.id} priority={r.priority} title={r.title} desc={r.description} />
                ))}
              </div>
            )}
          </Section>
        </div>

        {/* ── 6+7. Experiments + Automation ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <Section title="Active Experiments" icon={FlaskConical}>
            {loading ? (
              <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="h-10 bg-muted/20 rounded-lg animate-pulse" />)}</div>
            ) : (
              <div className="space-y-1">
                <ExpRow name="Prompt v2" status="running" score={74} />
                <ExpRow name="Latency Optimizer" status="completed" />
                <ExpRow name="Embedding Upgrade" status="waiting" />
              </div>
            )}
          </Section>

          <Section title="Automation" icon={GitBranch}>
            {loading ? (
              <div className="space-y-2">{[1,2,3].map(i => <div key={i} className="h-10 bg-muted/20 rounded-lg animate-pulse" />)}</div>
            ) : (
              <div className="space-y-1">
                <AutoRow name="Nightly Evaluation" status="completed" />
                <AutoRow name="Knowledge Sync" status="running" />
                <AutoRow name="Alert Correlation" status="waiting" />
                <AutoRow name="Incident RCA" status="failed" />
              </div>
            )}
          </Section>
        </div>

        {/* ── 8+10. Knowledge + OwnGPT Prompt ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <Section title="Knowledge" icon={BookOpen}>
            {loading ? (
              <div className="h-16 bg-muted/20 rounded-lg animate-pulse" />
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-small text-muted-foreground">Indexed</span>
                  <span className="text-small font-medium text-foreground">{String(brief?.knowledge_docs ?? 0)} docs</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-small text-muted-foreground">Updated</span>
                  <span className="text-small font-medium text-foreground">{brief?.knowledge_updated !== 'N/A' ? brief?.knowledge_updated : '12 min ago'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-small text-muted-foreground">Status</span>
                  <StatusBadge status="healthy" />
                </div>
              </div>
            )}
          </Section>

          <Section title="Ask OwnGPT" icon={Sparkles}>
            <div className="space-y-3">
              <div className="relative">
                <input
                  type="text"
                  placeholder="Ask OwnGPT..."
                  className="w-full rounded-lg border border-border bg-background/50 py-2 px-3 text-small text-foreground placeholder:text-muted-foreground/40 outline-none transition-colors focus:border-primary/40"
                  readOnly
                />
              </div>
              <div className="space-y-1">
                <p className="text-caption text-muted-foreground/60 px-1">Suggested</p>
                {['Explain today\'s alerts', 'Summarize overnight changes', 'Why is latency higher?'].map((q, i) => (
                  <button key={i} className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-small text-muted-foreground hover:text-foreground hover:bg-hover transition-all text-left">
                    <Sparkles size={12} className="text-primary" />
                    <span>{q}</span>
                    <ChevronRight size={12} className="ml-auto text-muted-foreground/30" />
                  </button>
                ))}
              </div>
            </div>
          </Section>
        </div>
      </div>
    </div>
  )
}

/* ── Sub-components ── */

function KpiCard({ icon: Icon, value, label, trend, status, danger }: {
  icon: React.ElementType
  value: string
  label: string
  trend: string
  status: string
  danger?: boolean
}) {
  return (
    <div className="bg-elevated border border-border/60 rounded-xl p-5 hover:border-primary/30 transition-all">
      <div className="flex items-start justify-between mb-3">
        <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center', danger ? 'bg-danger/10' : 'bg-primary/10')}>
          <Icon size={16} className={danger ? 'text-danger' : 'text-primary'} />
        </div>
        <StatusBadge status={status} />
      </div>
      <p className={cn('text-h3 text-foreground', danger && 'text-danger')}>{value}</p>
      <p className="text-small text-muted-foreground mt-0.5">{label}</p>
      <p className="text-caption text-muted-foreground/50 mt-0.5">{trend}</p>
    </div>
  )
}

function ServiceRow({ name, status, uptime, latency, detail }: {
  name: string
  status: string
  uptime: string
  latency: string
  detail?: string
}) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg hover:bg-hover transition-all">
      <Dot status={status} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-small font-medium text-foreground">{name}</span>
          <span className="text-caption text-muted-foreground/60">{latency}</span>
        </div>
        {detail && <p className="text-caption text-muted-foreground/50">{detail}</p>}
      </div>
      <span className="text-small font-medium text-foreground">{uptime}</span>
    </div>
  )
}

function InsightCard({ icon, title, description, recommendation, confidence, color }: {
  icon: React.ReactNode
  title: string
  description: string
  recommendation: string
  confidence: string
  color: string
}) {
  return (
    <div className="p-3 rounded-lg bg-muted/20 border border-border/40 hover:bg-hover transition-all">
      <div className="flex items-start gap-2.5">
        <span className={cn('mt-0.5', color)}>{icon}</span>
        <div className="min-w-0 flex-1">
          <p className="text-small font-medium text-foreground">{title}</p>
          <p className="text-caption text-muted-foreground/70">{description}</p>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="text-caption text-info">→ {recommendation}</span>
            <span className="text-caption text-muted-foreground/40">·</span>
            <span className={cn('text-caption font-medium', confidence === 'High' ? 'text-success' : 'text-warning')}>{confidence}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function ActivityRow({ icon, text, time, type }: {
  icon: React.ReactNode
  text: string
  time: string
  type: string
}) {
  const typeColor = type === 'deployment' || type === 'evaluation' ? 'text-success' :
                    type === 'recommendation' ? 'text-warning' :
                    type === 'incident' ? 'text-danger' :
                    type === 'experiment' ? 'text-info' : 'text-info'
  return (
    <div className="flex items-center gap-2.5 p-2.5 rounded-lg hover:bg-hover transition-all">
      <span className={typeColor}>{icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-small text-foreground truncate">{text}</p>
      </div>
      <span className="text-caption text-muted-foreground/50 shrink-0">{time}</span>
    </div>
  )
}

function RecRow({ priority, title, desc }: { priority: string; title: string; desc?: string }) {
  const color = priority === 'high' ? 'border-l-danger' : priority === 'medium' ? 'border-l-warning' : 'border-l-info'
  return (
    <div className={cn('border-l-2 pl-3 py-2 hover:bg-hover rounded-r-lg transition-all', color)}>
      <p className="text-small font-medium text-foreground">{title}</p>
      {desc && <p className="text-caption text-muted-foreground/70">{desc}</p>}
    </div>
  )
}

function ExpRow({ name, status, score }: { name: string; status: string; score?: number }) {
  return (
    <div className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-hover transition-all">
      <div className="flex-1 min-w-0">
        <p className="text-small text-foreground">{name}</p>
      </div>
      {score != null && (
        <div className="flex items-center gap-1.5">
          <div className="w-16 h-1.5 rounded-full bg-muted/50 overflow-hidden">
            <div className={cn('h-full rounded-full', score >= 70 ? 'bg-success' : score >= 40 ? 'bg-warning' : 'bg-danger')} style={{ width: `${score}%` }} />
          </div>
          <span className={cn('text-caption font-medium', score >= 70 ? 'text-success' : score >= 40 ? 'text-warning' : 'text-danger')}>{score}%</span>
        </div>
      )}
      <StatusBadge status={status} />
    </div>
  )
}

function AutoRow({ name, status }: { name: string; status: string }) {
  return (
    <div className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-hover transition-all">
      <Dot status={status} />
      <span className="text-small text-foreground flex-1">{name}</span>
      <StatusBadge status={status} />
    </div>
  )
}
