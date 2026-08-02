import { useState, useEffect, useCallback } from 'react'
import { cn } from '@/lib/utils'
import {
  BarChart3, RefreshCw, Activity, MessageSquare, ThumbsUp, ThumbsDown,
  Copy, RotateCcw, Search, Lightbulb, FileText, GitBranch, AlertTriangle, Inbox,
} from 'lucide-react'
import { analyticsApi, type OverviewReport, type TelemetryDashboard, type QueryRow } from '@/features/analytics/services/analyticsApi'
import { useCountUp } from '@/lib/useCountUp'

const POLL_MS = 30_000

function Section({ title, icon: Icon, children, className }: {
  title: string
  icon?: React.ElementType
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('bg-elevated border border-border/60 rounded-xl p-5', className)}>
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon size={16} className="text-muted-foreground" />}
        <h2 className="text-small font-semibold text-foreground uppercase tracking-wider">{title}</h2>
      </div>
      {children}
    </div>
  )
}

function PctBar({ value, max = 1, color }: { value: number; max?: number; color?: string }) {
  const width = max > 0 ? Math.max(2, Math.min(100, (value / max) * 100)) : 0
  return (
    <div className="w-full h-1.5 rounded-full bg-muted/50 overflow-hidden">
      <div className={cn('h-full rounded-full transition-[width] duration-500 ease-out', color ?? 'bg-primary')} style={{ width: `${width}%` }} />
    </div>
  )
}

function ConfidenceBar({ value }: { value?: number }) {
  const v = value ?? 0
  const color = v >= 0.7 ? 'bg-success' : v >= 0.45 ? 'bg-warning' : 'bg-danger'
  return <PctBar value={v} color={color} />
}

function MiniBars({ items, barClass }: {
  items: { label: string; value: number; display?: string }[]
  barClass: (v: number) => string
}) {
  if (!items.length) {
    return <p className="text-caption text-muted-foreground/60 py-4 text-center">No data yet</p>
  }
  const max = Math.max(...items.map(i => i.value), 1)
  return (
    <div className="flex items-end gap-1.5 h-32">
      {items.map((it, i) => (
        <div key={i} className="flex-1 flex flex-col items-center gap-1 min-w-0" title={`${it.label}: ${it.display ?? it.value}`}>
          <span className="text-caption text-muted-foreground/60">{it.display ?? it.value}</span>
          <div
            className={cn('w-full rounded-t-md', barClass(it.value))}
            style={{ height: `${Math.max(4, (it.value / max) * 72)}px` }}
          />
          <span className="text-caption text-muted-foreground/40 truncate w-full text-center">{it.label}</span>
        </div>
      ))}
    </div>
  )
}

function EmptyRow({ text = 'No data yet' }: { text?: string }) {
  return (
    <div className="flex items-center gap-2 justify-center py-6 text-caption text-muted-foreground/60">
      <Inbox size={13} />
      <span>{text}</span>
    </div>
  )
}

function WhyNote({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-2 rounded-lg border border-info/25 bg-info/5 px-3 py-2 text-caption text-info/90 flex items-start gap-2">
      <Lightbulb size={12} className="shrink-0 mt-0.5" />
      <div>{children}</div>
    </div>
  )
}

export function OwnAnalyticsPage() {
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [overview, setOverview] = useState<OverviewReport | null>(null)
  const [telemetry, setTelemetry] = useState<TelemetryDashboard | null>(null)

  const fetchAll = useCallback(async (silent = false) => {
    if (!silent) setRefreshing(true)
    try {
      const d = await analyticsApi.getAll()
      setOverview(d.overview)
      setTelemetry(d.telemetry)
      setError(null)
      setLastUpdated(new Date())
    } catch (e: any) {
      setError(e.message || 'Failed to load analytics')
    } finally {
      setRefreshing(false)
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    fetchAll(true).finally(() => setLoading(false))
  }, [fetchAll])

  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(() => fetchAll(true), POLL_MS)
    return () => clearInterval(id)
  }, [autoRefresh, fetchAll])

  const totalRecords = overview?.total_records ?? telemetry?.learning_records ?? 0
  const hasData = totalRecords > 0

  const recordsAnim = useCountUp(totalRecords)
  const eventsAnim = useCountUp(telemetry?.user_events ?? overview?.total_events ?? 0)

  const volume = (overview?.trends?.daily_volume ?? []).slice(-14).map(d => ({
    label: (d.day ?? '').slice(5),
    value: d.queries ?? 0,
  }))
  const confidence = (overview?.trends?.daily_confidence ?? []).slice(-14).map(d => ({
    label: (d.day ?? '').slice(5),
    value: Math.round((d.avg_confidence ?? 0) * 100),
  }))
  const avgConfidence = confidence.length
    ? confidence[confidence.length - 1].value
    : overview?.trends?.weekly_growth?.current_avg_confidence != null
      ? Math.round((overview.trends.weekly_growth.current_avg_confidence as number) * 100)
      : null

  const growth = overview?.trends?.weekly_growth
  const growthPct = growth?.query_growth_pct as number | undefined
  const currentQueries = growth?.current_queries as number | undefined
  const previousQueries = growth?.previous_queries as number | undefined
  const confDeltaPct = growth?.confidence_change_pct as number | undefined

  const recordsContext = growthPct != null
    ? `+${currentQueries ?? 0} this week · ${growthPct > 0 ? '+' : ''}${growthPct}%`
    : 'Total answers recorded'
  const confidenceContext = confDeltaPct != null
    ? `${confDeltaPct > 0 ? '+' : ''}${confDeltaPct}% vs prev week (${previousQueries ?? 0} → ${currentQueries ?? 0})`
    : 'Latest day'

  const confidenceAnim = useCountUp(avgConfidence ?? 0)

  const intentDist = Object.entries(overview?.routing?.intent_distribution ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
  const ruleVsLlm = overview?.routing?.rule_vs_llm_rate ?? {}
  const chunkQuality = overview?.retrieval?.chunk_quality ?? {}

  const recGroups: { key: string; label: string; items: any[]; icon: React.ElementType }[] = [
    { key: 'knowledge_gaps', label: 'Knowledge Gaps', items: overview?.recommendations?.knowledge_gaps ?? [], icon: Search },
    { key: 'weak_chunks', label: 'Weak Chunks', items: overview?.recommendations?.weak_chunks ?? [], icon: FileText },
    { key: 'dead_chunks', label: 'Dead Chunks', items: overview?.recommendations?.dead_chunks ?? [], icon: Inbox },
    { key: 'routing_issues', label: 'Routing Issues', items: overview?.recommendations?.routing_issues ?? [], icon: GitBranch },
    { key: 'benchmark_candidates', label: 'Benchmark Candidates', items: overview?.recommendations?.benchmark_candidates ?? [], icon: BarChart3 },
  ]
  const recTotal = recGroups.reduce((s, g) => s + g.items.length, 0)

  const gaps = overview?.query?.knowledge_gaps ?? []
  const weakChunks = overview?.recommendations?.weak_chunks ?? []
  const deadChunks = overview?.recommendations?.dead_chunks ?? []
  const routingIssues = overview?.recommendations?.routing_issues ?? []
  const lowConfQueries = (overview?.query?.top_queries ?? []).filter(q => (q.avg_confidence ?? 1) < 0.6)
  const worstDoc = [...(overview?.retrieval?.per_document ?? [])].sort((a, b) => (a.avg_confidence ?? 1) - (b.avg_confidence ?? 1))[0]
  const gapSample = gaps[0]?.sample ? ` e.g. “${gaps[0].sample}”` : ''

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-[1320px] mx-auto p-6 space-y-5">
        {/* ── Header ── */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-h2 text-foreground">OwnAnalytics</h1>
            <p className="text-caption text-muted-foreground mt-0.5">
              Query patterns, retrieval effectiveness, routing, and user behavior
              {lastUpdated && ` — updated ${lastUpdated.toLocaleTimeString()}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setAutoRefresh(v => !v)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-small font-medium border transition-all',
                autoRefresh
                  ? 'bg-primary/10 border-primary/30 text-primary'
                  : 'bg-elevated border-border text-muted-foreground hover:text-foreground',
              )}
              title="Toggle auto-refresh"
            >
              Auto {autoRefresh ? 'on' : 'off'}
            </button>
            <button
              onClick={() => fetchAll()}
              disabled={refreshing}
              className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-hover transition-all disabled:opacity-50"
              title="Refresh"
            >
              <RefreshCw size={18} className={cn(refreshing && 'animate-spin')} />
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-xs text-destructive bg-danger/10 border border-danger/20 rounded-lg p-2.5">
            <AlertTriangle size={13} />
            <span>Failed to load analytics: {error}</span>
          </div>
        )}

        {/* ── KPIs ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {loading ? [1, 2, 3, 4].map(i => (
            <div key={i} className="bg-elevated border border-border/60 rounded-xl p-5 animate-pulse">
              <div className="h-8 w-14 bg-muted/50 rounded" />
              <div className="h-4 w-24 bg-muted/30 rounded mt-2" />
            </div>
          )) : (
            <>
              <KpiCard icon={MessageSquare} value={String(Math.round(recordsAnim))} label="Learning Records" sub={recordsContext} />
              <KpiCard icon={Activity} value={String(Math.round(eventsAnim))} label="User Events" sub="Thumbs, copies, regenerations" />
              <KpiCard icon={ThumbsUp} value={telemetry?.thumb_approval_rate != null ? `${telemetry.thumb_approval_rate}%` : '—'} label="Approval Rate" sub={`${telemetry?.thumbs_up ?? 0} up / ${telemetry?.thumbs_down ?? 0} down`} />
              <KpiCard icon={BarChart3} value={avgConfidence != null ? `${Math.round(confidenceAnim)}%` : '—'} label="Avg Confidence" sub={confidenceContext} />
            </>
          )}
        </div>

        {!hasData && !loading && (
          <div className="flex flex-col items-center gap-2 py-10 bg-elevated border border-border/60 rounded-xl text-center">
            <Inbox size={28} className="text-muted-foreground/40" />
            <p className="text-small text-muted-foreground">No learning data yet</p>
            <p className="text-caption text-muted-foreground/60 max-w-md">
              Ask OwnGPT a few questions and rate the answers — analytics surface here automatically.
            </p>
          </div>
        )}

        {/* ── Trends ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <Section title="Daily Volume (14d)" icon={Activity}>
            <MiniBars items={volume} barClass={() => 'bg-primary'} />
          </Section>
          <Section title="Daily Confidence (14d)" icon={BarChart3}>
            <MiniBars
              items={confidence}
              barClass={v => (v >= 70 ? 'bg-success' : v >= 45 ? 'bg-warning' : 'bg-danger')}
            />
            {avgConfidence != null && avgConfidence < 70 && gaps.length > 0 && (
              <WhyNote>
                <b>Why:</b> {gaps.length} knowledge gap{gaps.length > 1 ? 's' : ''} keep confidence below 70%{gapSample}.{' '}
                <b>Fix:</b> add documents covering these topics and re-sync the knowledge base.
              </WhyNote>
            )}
          </Section>
        </div>

        {/* ── Query intelligence ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <Section title="Top Queries" icon={Search}>
            {(overview?.query?.top_queries ?? []).length === 0 ? (
              <EmptyRow text="Ask OwnGPT to see top queries" />
            ) : (
              <>
                <div className="space-y-1.5">
                {(overview?.query?.top_queries ?? []).slice(0, 10).map((q: QueryRow, i) => (
                  <div key={i} className="flex items-center gap-2.5 p-2 rounded-lg hover:bg-hover transition-all">
                    <span className="text-caption text-muted-foreground/50 w-4 text-right shrink-0">{i + 1}</span>
                    <div className="flex-1 min-w-0 space-y-1">
                      <p className="text-small text-foreground truncate">{q.sample || '(no sample)'}</p>
                      <div className="flex items-center gap-2">
                        <ConfidenceBar value={q.avg_confidence} />
                        <span className="text-caption text-muted-foreground/60 shrink-0">{(q.avg_confidence ?? 0).toFixed(2)}</span>
                      </div>
                    </div>
                    <span className="text-small font-medium text-foreground shrink-0">{q.count}</span>
                  </div>
                ))}
                </div>
                {lowConfQueries.length > 0 && (
                  <WhyNote>
                    <b>Why:</b> {lowConfQueries.length} frequent quer{lowConfQueries.length > 1 ? 'ies' : 'y'} score below 0.60 confidence.{' '}
                    <b>Fix:</b> strengthen knowledge coverage for those topics.
                  </WhyNote>
                )}
              </>
            )}
          </Section>

          <Section title="Knowledge Gaps" icon={Lightbulb}>
            {(overview?.query?.knowledge_gaps ?? []).length === 0 ? (
              <EmptyRow text="No knowledge gaps detected" />
            ) : (
              <div className="space-y-1.5">
                {(overview?.query?.knowledge_gaps ?? []).slice(0, 10).map((g: QueryRow, i) => (
                  <div key={i} className="flex items-center gap-2.5 p-2 rounded-lg hover:bg-hover transition-all">
                    <div className="flex-1 min-w-0 space-y-1">
                      <p className="text-small text-foreground truncate">{g.sample || '(no sample)'}</p>
                      <div className="flex items-center gap-2">
                        <ConfidenceBar value={g.avg_confidence} />
                        <span className="text-caption text-muted-foreground/60 shrink-0">
                          {g.count}× · {(g.avg_confidence ?? 0).toFixed(2)} conf
                        </span>
                      </div>
                    </div>
                    {(g.thumbs_down ?? 0) > 0 && (
                      <span className="text-caption text-danger flex items-center gap-1 shrink-0">
                        <ThumbsDown size={11} /> {g.thumbs_down}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Section>
        </div>

        {/* ── Retrieval ── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <Section title="Chunk Quality" icon={FileText} className="lg:col-span-1">
            {(overview?.retrieval?.per_chunk ?? []).length === 0 ? (
              <EmptyRow text="No retrieval data yet" />
            ) : (
              <div className="space-y-3">
                  {(['excellent', 'good', 'weak', 'dead'] as const).map(k => {
                    const v = chunkQuality[k] ?? 0
                    const color = k === 'excellent' ? 'bg-success' : k === 'good' ? 'bg-info' : k === 'weak' ? 'bg-warning' : 'bg-danger'
                    return (
                      <div key={k} className="space-y-1">
                        <div className="flex items-center justify-between text-small">
                          <span className="capitalize text-foreground">{k}</span>
                          <span className="text-muted-foreground">{v}</span>
                        </div>
                        <PctBar value={v} max={Math.max(...Object.values(chunkQuality), 1)} color={color} />
                      </div>
                    )
                  })}
                  {(weakChunks.length + deadChunks.length) > 0 && (
                    <WhyNote>
                      <b>Why:</b> {weakChunks.length} weak and {deadChunks.length} dead chunk{(weakChunks.length + deadChunks.length) > 1 ? 's' : ''} reduce retrieval quality.{' '}
                      <b>Fix:</b> re-split or re-index the affected documents.
                    </WhyNote>
                  )}
                </div>
            )}
          </Section>

          <Section title="Document Effectiveness" icon={BarChart3} className="lg:col-span-2">
            {(overview?.retrieval?.per_document ?? []).length === 0 ? (
              <EmptyRow text="No per-document retrieval data yet" />
            ) : (
              <div className="space-y-1.5">
                {(overview?.retrieval?.per_document ?? []).slice(0, 8).map((d, i) => (
                  <div key={i} className="flex items-center gap-3 p-2 rounded-lg hover:bg-hover transition-all">
                    <FileText size={13} className="text-muted-foreground shrink-0" />
                    <span className="text-small text-foreground truncate flex-1">{d.document}</span>
                    <div className="w-24 shrink-0 space-y-0.5">
                      <ConfidenceBar value={d.avg_confidence} />
                    </div>
                    <span className="text-caption text-muted-foreground/70 shrink-0 w-16 text-right">
                      {(d.avg_confidence ?? 0).toFixed(2)}
                    </span>
                    <span className="text-caption text-muted-foreground/50 shrink-0 w-14 text-right">{d.retrieved_count}×</span>
                  </div>
                ))}
                {worstDoc && (worstDoc.avg_confidence ?? 1) < 0.6 && (
                  <WhyNote>
                    <b>Weakest document:</b> {worstDoc.document} at {(worstDoc.avg_confidence ?? 0).toFixed(2)} confidence.{' '}
                    <b>Fix:</b> re-index it or check its chunking strategy.
                  </WhyNote>
                )}
              </div>
            )}
          </Section>
        </div>

        {/* ── Routing ── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <Section title="Intent Distribution" icon={GitBranch}>
            {intentDist.length === 0 ? (
              <EmptyRow text="No routing data yet" />
            ) : (
              <div className="space-y-3">
                {intentDist.map(([intent, count]) => (
                  <div key={intent} className="space-y-1">
                    <div className="flex items-center justify-between text-small">
                      <span className="text-foreground truncate">{intent || '(unknown)'}</span>
                      <span className="text-muted-foreground shrink-0">{count}</span>
                    </div>
                    <PctBar value={count} max={intentDist[0][1]} color="bg-info" />
                  </div>
                ))}
              </div>
            )}
          </Section>

          <Section title="Rule vs LLM Routing" icon={GitBranch}>
            {(ruleVsLlm.rule_pct != null || ruleVsLlm.llm_pct != null) ? (
              <div className="space-y-4 pt-2">
                <div className="flex h-4 rounded-full overflow-hidden bg-muted/50">
                  <div className="bg-info" style={{ width: `${ruleVsLlm.rule_pct ?? 0}%` }} title={`Rule: ${ruleVsLlm.rule_pct ?? 0}%`} />
                  <div className="bg-primary" style={{ width: `${ruleVsLlm.llm_pct ?? 0}%` }} title={`LLM: ${ruleVsLlm.llm_pct ?? 0}%`} />
                </div>
                <div className="flex gap-6 text-small">
                  <span className="flex items-center gap-1.5 text-foreground"><span className="w-2.5 h-2.5 rounded-sm bg-info" /> Rule — {ruleVsLlm.rule_pct ?? 0}%</span>
                  <span className="flex items-center gap-1.5 text-foreground"><span className="w-2.5 h-2.5 rounded-sm bg-primary" /> LLM — {ruleVsLlm.llm_pct ?? 0}%</span>
                </div>
                {(overview?.routing?.confidence_by_intent ?? []).length > 0 && (
                  <div className="space-y-1.5 pt-2 border-t border-border/50">
                    {(overview?.routing?.confidence_by_intent ?? []).slice(0, 6).map((r, i) => (
                      <div key={i} className="flex items-center gap-3 text-small">
                        <span className="text-foreground truncate flex-1">{r.intent || '(unknown)'}</span>
                        <span className="text-muted-foreground/60 w-12 text-right">{r.total}</span>
                        <div className="w-20 shrink-0"><ConfidenceBar value={r.avg_confidence} /></div>
                        <span className="text-caption text-muted-foreground/70 w-10 text-right">{(r.avg_confidence ?? 0).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <EmptyRow text="No routing data yet" />
            )}
            {routingIssues.length > 0 && (
              <WhyNote>
                <b>Why:</b> {routingIssues.length} routing issue{routingIssues.length > 1 ? 's' : ''} detected.{' '}
                <b>Fix:</b> review routing rules for misdirected queries.
              </WhyNote>
            )}
          </Section>
        </div>

        {/* ── Behavior ── */}
        <Section title="User Behavior" icon={ThumbsUp}>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
            <BehaviorChip icon={ThumbsUp} color="text-success" label="Thumbs Up" value={telemetry?.thumbs_up ?? 0} />
            <BehaviorChip icon={ThumbsDown} color="text-danger" label="Thumbs Down" value={telemetry?.thumbs_down ?? 0} />
            <BehaviorChip icon={Copy} color="text-info" label="Copies" value={telemetry?.copies ?? 0} />
            <BehaviorChip icon={RotateCcw} color="text-warning" label="Regenerations" value={telemetry?.regenerations ?? 0} />
          </div>
          {(overview?.behavior?.by_intent ?? []).length === 0 ? (
            <EmptyRow text="No behavior data yet" />
          ) : (
            <div className="space-y-1">
              {(overview?.behavior?.by_intent ?? []).slice(0, 8).map((b, i) => (
                <div key={i} className="flex items-center gap-3 p-2 rounded-lg hover:bg-hover transition-all text-small">
                  <span className="text-foreground truncate flex-1">{b.intent || '(unknown)'}</span>
                  <span className="text-muted-foreground/60 w-14 text-right">{b.records} rec</span>
                  <span className="text-success/80 w-12 text-right">{b.thumbs ?? 0} 👍</span>
                  <span className="text-info/80 w-12 text-right">{b.copies ?? 0} cp</span>
                  <span className="text-warning/80 w-12 text-right">{b.regens ?? 0} rg</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* ── Recommendations ── */}
        <Section title="Recommendations" icon={Lightbulb}>
          {recTotal === 0 ? (
            <EmptyRow text="No recommendations yet — they appear as evidence accumulates" />
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {recGroups.filter(g => g.items.length > 0).map(group => (
                <div key={group.key} className="space-y-1.5">
                  <p className="text-caption text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                    <group.icon size={12} /> {group.label} <span className="text-muted-foreground/40">({group.items.length})</span>
                  </p>
                  {group.items.slice(0, 6).map((r: any) => (
                    <div key={r.id} className={cn('border-l-2 pl-3 py-2 rounded-r-lg', r.severity === 'high' ? 'border-l-danger' : r.severity === 'low' ? 'border-l-info' : 'border-l-warning')}>
                      <p className="text-small font-medium text-foreground">{r.title}</p>
                      {r.description && <p className="text-caption text-muted-foreground/70 line-clamp-2">{r.description}</p>}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>
    </div>
  )
}

function KpiCard({ icon: Icon, value, label, sub }: {
  icon: React.ElementType
  value: string
  label: string
  sub: string
}) {
  return (
    <div className="bg-elevated border border-border/60 rounded-xl p-5 hover:border-primary/30 hover:-translate-y-0.5 transition-all">
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
          <Icon size={16} className="text-primary" />
        </div>
      </div>
      <p className="text-h3 text-foreground">{value}</p>
      <p className="text-small text-muted-foreground mt-0.5">{label}</p>
      <p className="text-caption text-muted-foreground/50 mt-0.5">{sub}</p>
    </div>
  )
}

function BehaviorChip({ icon: Icon, color, label, value }: {
  icon: React.ElementType
  color: string
  label: string
  value: number
}) {
  return (
    <div className="flex items-center gap-2.5 bg-muted/20 border border-border/40 rounded-lg px-3 py-2.5">
      <Icon size={15} className={color} />
      <div>
        <p className="text-title font-semibold text-foreground leading-tight">{value}</p>
        <p className="text-caption text-muted-foreground/60">{label}</p>
      </div>
    </div>
  )
}

export default OwnAnalyticsPage
