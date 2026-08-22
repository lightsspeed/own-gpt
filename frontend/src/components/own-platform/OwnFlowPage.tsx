import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import {
  Activity, RefreshCw, ChevronDown, AlertTriangle, Loader2, Play,
  TrendingDown, TrendingUp, Minus, ShieldCheck, History, Clock, FileText,
  X, ArrowRight, ChevronRight, FlaskConical,
} from 'lucide-react'
import {
  automationApi, type DailyBrief, type EvaluationSnapshot, type AutomationRun, type BriefTrigger,
} from '@/features/automation/services/automationApi'
import { useCountUp } from '@/lib/useCountUp'

const REFRESH_MS = 30000

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso.replace(' ', 'T'))
  return d.toLocaleString()
}

function TrendIcon({ trend }: { trend: string }) {
  if (trend === 'declining') return <TrendingDown size={13} className="text-danger" />
  if (trend === 'improving') return <TrendingUp size={13} className="text-success" />
  return <Minus size={13} className="text-muted-foreground/40" />
}

const SEVERITY_CLASS: Record<string, string> = {
  critical: 'border-danger/30 bg-danger/10 text-danger',
  high: 'border-warning/30 bg-warning/10 text-warning',
  medium: 'border-border/60 bg-muted/30 text-foreground/80',
  low: 'border-border/60 bg-muted/30 text-muted-foreground',
}

function TriggerRow({ trigger, onClick }: { trigger: BriefTrigger; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn('w-full text-left flex items-start gap-3 rounded-lg border border-border/40 bg-background/40 px-3 py-2.5 transition-colors', onClick && 'hover:bg-hover/60 cursor-pointer')}
    >
      <span className={cn('mt-0.5 inline-flex shrink-0 rounded-md border px-1.5 py-0.5 text-caption font-medium uppercase tracking-wide', SEVERITY_CLASS[trigger.severity] ?? SEVERITY_CLASS.medium)}>
        {trigger.severity}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-small font-medium text-foreground">{trigger.title}</p>
        <p className="text-caption text-muted-foreground/70 mt-0.5">{trigger.description}</p>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-caption text-muted-foreground/50">
          <span className="rounded-md bg-muted/30 px-1.5 py-0.5">{trigger.domain}</span>
          <span>{trigger.metric_name} {trigger.metric_value} {trigger.direction} {trigger.threshold}</span>
        </div>
      </div>
      {onClick && <ChevronRight size={14} className="text-muted-foreground/40 shrink-0 mt-1.5" />}
    </button>
  )
}

function ChangeRow({ field, change }: { field: string; change: any }) {
  const prev = change?.previous
  const current = change?.current
  const delta = change?.delta
  const deltaPct = change?.delta_pct
  return (
    <div className="flex items-center gap-2.5 text-caption">
      <span className="w-40 shrink-0 text-muted-foreground/70 font-medium">{field}</span>
      <span className="text-muted-foreground/60">{formatNum(prev)}</span>
      <span className="text-muted-foreground/40">→</span>
      <span className="text-foreground/90 font-medium">{formatNum(current)}</span>
      <span className={cn('ml-auto font-medium shrink-0', (delta ?? 0) > 0 ? 'text-danger' : (delta ?? 0) < 0 ? 'text-success' : 'text-muted-foreground/40')}>
        {delta !== undefined && delta !== null ? `${delta > 0 ? '+' : ''}${formatNum(delta)}${deltaPct !== undefined && deltaPct !== null ? ` (${deltaPct > 0 ? '+' : ''}${deltaPct}%)` : ''}` : ''}
      </span>
    </div>
  )
}

function formatNum(v: any): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2)
  return String(v)
}

function SnapshotRow({ snap, diff, expanded, onToggle, diffLoading }: {
  snap: EvaluationSnapshot
  diff: EvaluationSnapshot | null
  expanded: boolean
  onToggle: () => void
  diffLoading: boolean
}) {
  const overall = snap.health_scores?.overall
  const changes = Object.entries(diff?.change_summary ?? {})
  return (
    <div className="rounded-xl border border-border/60 bg-elevated overflow-hidden">
      <button onClick={onToggle} className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-hover/60 transition-colors">
        <div className={cn(
          'shrink-0 rounded-lg border p-1.5',
          overall !== undefined && overall < 70
            ? 'border-danger/20 bg-danger/10 text-danger'
            : overall !== undefined && overall < 90
              ? 'border-warning/20 bg-warning/10 text-warning'
              : 'border-success/20 bg-success/10 text-success',
        )}>
          <Activity size={14} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-small font-medium text-foreground">{formatTime(snap.timestamp)}</p>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-caption text-muted-foreground/70">
            <span>{snap.id}</span>
            {snap.previous_snapshot_id && <span>prev {snap.previous_snapshot_id}</span>}
            <span className="inline-flex items-center gap-1"><FileText size={10} /> {snap.findings_count} findings</span>
            <span className="inline-flex items-center gap-1"><Clock size={10} /> {snap.record_count} records</span>
          </div>
        </div>
        <div className="shrink-0 text-right">
          <p className={cn('text-small font-semibold', overall !== undefined && overall < 70 ? 'text-danger' : overall !== undefined && overall < 90 ? 'text-warning' : 'text-foreground')}>
            {overall !== undefined ? `${overall}%` : '—'}
          </p>
          <p className="text-caption text-muted-foreground/50">health</p>
        </div>
        <ChevronDown size={14} className={cn('text-muted-foreground/50 transition-transform', expanded && 'rotate-180')} />
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-1 space-y-2 border-t border-border/40">
          <div className="pt-3 grid grid-cols-2 md:grid-cols-4 gap-2">
            <div className="rounded-lg border border-border/40 bg-background/40 px-3 py-2">
              <p className="text-caption text-muted-foreground/60">Confidence</p>
              <p className="text-small font-semibold text-foreground">{snap.avg_confidence ?? '—'}</p>
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 px-3 py-2">
              <p className="text-caption text-muted-foreground/60">ECE</p>
              <p className="text-small font-semibold text-foreground">{snap.ece ?? '—'}{snap.ece_change_pct ? ` (${snap.ece_change_pct > 0 ? '+' : ''}${snap.ece_change_pct}%)` : ''}</p>
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 px-3 py-2">
              <p className="text-caption text-muted-foreground/60">Findings</p>
              <p className="text-small font-semibold text-foreground">{snap.critical_findings} crit / {snap.high_findings} high</p>
            </div>
            <div className="rounded-lg border border-border/40 bg-background/40 px-3 py-2">
              <p className="text-caption text-muted-foreground/60">Knowledge gaps</p>
              <p className="text-small font-semibold text-foreground">{snap.knowledge_gap_count}</p>
            </div>
          </div>

          {diffLoading ? (
            <div className="flex items-center justify-center gap-2 py-4 text-caption text-muted-foreground/60">
              <Loader2 size={13} className="animate-spin" /> Computing diff…
            </div>
          ) : changes.length > 0 ? (
            <div className="space-y-1.5 rounded-lg border border-border/40 bg-background/40 px-3 py-2.5">
              <p className="text-caption font-medium text-muted-foreground/70 mb-1.5">Change summary vs {snap.previous_snapshot_id}</p>
              {changes.map(([k, v]) => <ChangeRow key={k} field={k} change={v} />)}
            </div>
          ) : (
            <p className="text-caption text-muted-foreground/50">No meaningful changes vs previous snapshot.</p>
          )}
        </div>
      )}
    </div>
  )
}

function FindingDrawer({ trigger, diff, domain, onClose, onRunExperiment }: {
  trigger: BriefTrigger
  diff: EvaluationSnapshot | null
  domain: { domain: string; score: number; previous_score: number | null; trend: string } | null
  onClose: () => void
  onRunExperiment: () => void
}) {
  const changes = Object.entries(diff?.change_summary ?? {})
  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/50 animate-in fade-in-0 duration-200" onClick={onClose} />
      <aside className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-md bg-elevated border-l border-border shadow-2xl flex flex-col animate-in slide-in-from-right-4 duration-300">
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-border/60">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={cn('inline-flex shrink-0 rounded-md border px-1.5 py-0.5 text-caption font-medium uppercase tracking-wide', SEVERITY_CLASS[trigger.severity] ?? SEVERITY_CLASS.medium)}>
                {trigger.severity}
              </span>
              <span className="rounded-md bg-muted/30 px-1.5 py-0.5 text-caption">{trigger.domain}</span>
            </div>
            <h3 className="text-small font-semibold text-foreground mt-2 leading-snug">{trigger.title}</h3>
            <p className="text-caption text-muted-foreground/70 mt-1">{trigger.description}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-muted-foreground/50 hover:text-foreground hover:bg-hover transition-colors shrink-0">
            <X size={16} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar px-5 py-4 space-y-4">
          <div>
            <p className="text-caption font-medium uppercase tracking-wider text-muted-foreground/60 mb-2">Metric</p>
            <div className="rounded-lg border border-border/40 bg-background/40 px-3 py-2.5">
              <p className="text-small font-medium text-foreground">{trigger.metric_name}</p>
              <p className="text-caption text-muted-foreground/70 mt-0.5">
                {trigger.metric_value} {trigger.direction} threshold {trigger.threshold}
              </p>
            </div>
          </div>

          {domain && (
            <div>
              <p className="text-caption font-medium uppercase tracking-wider text-muted-foreground/60 mb-2">Domain health</p>
              <div className="rounded-lg border border-border/40 bg-background/40 px-3 py-2.5 flex items-center justify-between">
                <p className="text-small font-medium text-foreground capitalize">{domain.domain}</p>
                <p className="flex items-center gap-1.5 text-small">
                  <span className="text-muted-foreground/60">{domain.previous_score?.toFixed(1)} → </span>
                  <span className={cn('font-semibold', domain.score < 70 ? 'text-danger' : domain.score < 90 ? 'text-warning' : 'text-success')}>{domain.score.toFixed(1)}</span>
                  <TrendIcon trend={domain.trend} />
                </p>
              </div>
            </div>
          )}

          <div>
            <p className="text-caption font-medium uppercase tracking-wider text-muted-foreground/60 mb-2">
              Snapshot {trigger.snapshot_id}
            </p>
            {changes.length > 0 ? (
              <div className="space-y-1.5 rounded-lg border border-border/40 bg-background/40 px-3 py-2.5">
                {changes.map(([k, v]) => <ChangeRow key={k} field={k} change={v} />)}
              </div>
            ) : (
              <p className="text-caption text-muted-foreground/50">No change summary loaded for this snapshot.</p>
            )}
          </div>

          {trigger.created_at && (
            <p className="text-caption text-muted-foreground/50">Detected {formatTime(trigger.created_at)}</p>
          )}
        </div>

        <div className="border-t border-border/60 px-5 py-3.5 flex items-center gap-2">
          <button
            onClick={onRunExperiment}
            className="flex-1 rounded-lg bg-primary text-primary-foreground px-3 py-2 text-small font-medium hover:brightness-110 transition-all inline-flex items-center justify-center gap-1.5"
          >
            <FlaskConical size={13} /> Run experiment
          </button>
          <button
            onClick={onClose}
            className="flex-1 rounded-lg bg-elevated border border-border px-3 py-2 text-small text-muted-foreground hover:text-foreground hover:bg-hover transition-colors"
          >
            Close
          </button>
        </div>
      </aside>
    </>
  )
}

export function OwnFlowPage() {
  const navigate = useNavigate()
  const [brief, setBrief] = useState<DailyBrief | null>(null)
  const [snapshots, setSnapshots] = useState<EvaluationSnapshot[]>([])
  const [history, setHistory] = useState<AutomationRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [diffs, setDiffs] = useState<Record<string, EvaluationSnapshot>>({})
  const [diffLoading, setDiffLoading] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [selectedTrigger, setSelectedTrigger] = useState<BriefTrigger | null>(null)

  const load = async () => {
    setError(null)
    try {
      const [briefData, snapData, historyData] = await Promise.all([
        automationApi.getBriefLatest(),
        automationApi.getSnapshots(10),
        automationApi.getHistory(25),
      ])
      setBrief(briefData)
      setSnapshots(snapData)
      setHistory(historyData)
    } catch (e: any) {
      setError(e?.message || 'Failed to load evaluation data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    if (!autoRefresh) return
    const t = setInterval(load, REFRESH_MS)
    return () => clearInterval(t)
  }, [autoRefresh])

  const toggleExpand = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null)
      return
    }
    setExpandedId(id)
    if (!diffs[id]) {
      setDiffLoading(id)
      try {
        const d = await automationApi.getDiff(id)
        setDiffs(prev => ({ ...prev, [id]: d }))
      } catch {
        setDiffs(prev => ({ ...prev, [id]: null as any }))
      } finally {
        setDiffLoading(null)
      }
    }
  }

  const openTrigger = async (t: BriefTrigger) => {
    setSelectedTrigger(t)
    if (t.snapshot_id && !diffs[t.snapshot_id]) {
      try {
        const d = await automationApi.getDiff(t.snapshot_id)
        setDiffs(prev => ({ ...prev, [t.snapshot_id]: d }))
      } catch {
        // drawer still opens without diff data
      }
    }
  }

  const topTrigger = useMemo(() => {
    if (!brief) return null
    const sev: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }
    const triggers = brief.triggers ?? []
    if (triggers.length === 0) return null
    return [...triggers].sort((a, b) => (sev[a.severity] ?? 9) - (sev[b.severity] ?? 9))[0]
  }, [brief])

  const runNow = async () => {
    setRunning(true)
    try {
      await automationApi.runDailyEvaluation()
      await load()
    } catch (e: any) {
      setError(e?.message || 'Failed to run evaluation')
    } finally {
      setRunning(false)
    }
  }

  const domains = useMemo(() => brief?.health_domains ?? [], [brief])
  const lastRun = history[0]

  const healthAnim = useCountUp(brief?.overall_health ?? 0)
  const findingsAnim = useCountUp(brief?.total_findings ?? 0)
  const triggersAnim = useCountUp(brief?.triggers.length ?? 0)

  const hasData = !!brief && !brief.note && !!brief.generated_at

  return (
    <div className="h-full overflow-y-auto custom-scrollbar flex flex-col gap-4 p-4 md:p-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-title font-semibold text-foreground">Continuous Evaluation</h1>
          <p className="text-caption text-muted-foreground/60 mt-0.5">
            Daily health brief, triggers, and evaluation snapshots. Admin-only view.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh(v => !v)}
            className={cn(
              'rounded-lg border px-3 py-2 text-small transition-colors',
              autoRefresh
                ? 'border-primary/30 bg-primary/10 text-primary'
                : 'border-border/60 text-muted-foreground/60 hover:text-foreground',
            )}
          >
            Auto {autoRefresh ? 'on' : 'off'}
          </button>
          <button
            onClick={load}
            className="rounded-lg border border-border/60 px-3 py-2 text-small text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5"
          >
            <RefreshCw size={13} className={cn(loading && 'animate-spin')} /> Refresh
          </button>
          <button
            onClick={runNow}
            disabled={running}
            className="rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-small text-primary hover:bg-primary/20 transition-colors inline-flex items-center gap-1.5 disabled:opacity-50"
          >
            {running ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
            {running ? 'Evaluating…' : 'Run evaluation now'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-danger/30 bg-danger/10 p-4 text-center">
          <p className="text-small text-danger font-medium">Failed to load evaluation data</p>
          <p className="text-caption text-muted-foreground/70 mt-1">{error}</p>
          <button
            onClick={load}
            className="mt-3 rounded-lg border border-border/60 px-3 py-2 text-small text-foreground hover:bg-hover transition-colors inline-flex items-center gap-1.5"
          >
            <RefreshCw size={13} /> Retry
          </button>
        </div>
      )}

      {!error && loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground/60">
          <Loader2 size={16} className="animate-spin" /> Loading evaluation data…
        </div>
      ) : !error && !hasData ? (
        <div className="rounded-xl border border-border/60 bg-elevated/50 p-10 text-center">
          <ShieldCheck size={28} className="mx-auto text-muted-foreground/40 mb-3" />
          <p className="text-small text-muted-foreground/70">No evaluation data available yet.</p>
          <p className="text-caption text-muted-foreground/50 mt-1">Run the daily evaluation to generate the first health snapshot.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="rounded-xl border border-border/60 bg-elevated p-4">
              <p className="text-caption text-muted-foreground/60">Overall health</p>
              <p className={cn('mt-1 text-title font-semibold', brief.overall_health !== null && brief.overall_health < 70 ? 'text-danger' : brief.overall_health !== null && brief.overall_health < 90 ? 'text-warning' : 'text-foreground')}>
                {brief.overall_health !== null ? `${Math.round(healthAnim)}%` : '—'}
              </p>
            </div>
            <div className="rounded-xl border border-border/60 bg-elevated p-4">
              <p className="text-caption text-muted-foreground/60">Findings</p>
              <p className="mt-1 text-title font-semibold text-foreground">{Math.round(findingsAnim)} <span className="text-caption font-normal text-muted-foreground/60">({brief.findings_delta > 0 ? '+' : ''}{brief.findings_delta})</span></p>
            </div>
            <div className="rounded-xl border border-border/60 bg-elevated p-4">
              <p className="text-caption text-muted-foreground/60">New triggers</p>
              <p className={cn('mt-1 text-title font-semibold', brief.triggers.length > 0 ? 'text-warning' : 'text-foreground')}>{Math.round(triggersAnim)}</p>
            </div>
            <div className="rounded-xl border border-border/60 bg-elevated p-4">
              <p className="text-caption text-muted-foreground/60">Last run</p>
              <p className="mt-1 text-small font-semibold text-foreground">{lastRun ? formatTime(lastRun.started_at) : '—'}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {domains.filter(d => d.domain !== 'overall').map(d => (
              <div key={d.domain} className="rounded-xl border border-border/60 bg-elevated p-4">
                <div className="flex items-center justify-between">
                  <p className="text-caption text-muted-foreground/60 capitalize">{d.domain}</p>
                  <TrendIcon trend={d.trend} />
                </div>
                <p className={cn('mt-1 text-title font-semibold', d.score < 70 ? 'text-danger' : d.score < 90 ? 'text-warning' : 'text-foreground')}>
                  {d.score}%
                </p>
                <p className="text-caption text-muted-foreground/50 mt-0.5">
                  prev {d.previous_score ?? '—'}%
                </p>
              </div>
            ))}
          </div>

          {brief.top_finding && (
            <button
              onClick={() => topTrigger && openTrigger(topTrigger)}
              disabled={!topTrigger}
              className={cn('w-full text-left rounded-xl border border-warning/30 bg-warning/5 p-4 transition-colors', topTrigger && 'hover:bg-warning/10 cursor-pointer')}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-caption font-medium text-warning mb-1">Top finding</p>
                {topTrigger && <ChevronRight size={14} className="text-warning/60 shrink-0" />}
              </div>
              <p className="text-small text-foreground">{brief.top_finding}</p>
              <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-caption text-muted-foreground/70">
                {brief.calibration_note && <span>Calibration: {brief.calibration_note}</span>}
                {brief.retrieval_note && <span>Retrieval: {brief.retrieval_note}</span>}
                {brief.routing_note && <span>Routing: {brief.routing_note}</span>}
              </div>
              {topTrigger && (
                <div className="mt-2 flex items-center gap-1.5 text-caption text-info">
                  <ArrowRight size={12} /> View evidence, metrics and next steps
                </div>
              )}
            </button>
          )}

          <section className="space-y-2.5">
            <h2 className="text-small font-semibold text-foreground flex items-center gap-2"><AlertTriangle size={14} className="text-warning" /> Active triggers</h2>
            {brief.triggers.length === 0 ? (
              <p className="text-caption text-muted-foreground/50 rounded-xl border border-border/60 bg-elevated/50 p-6 text-center">No active triggers.</p>
            ) : (
              brief.triggers.map(t => <TriggerRow key={t.id} trigger={t} onClick={() => openTrigger(t)} />)
            )}
          </section>

          <section className="space-y-2.5">
            <h2 className="text-small font-semibold text-foreground flex items-center gap-2"><Activity size={14} className="text-primary" /> Snapshots</h2>
            {snapshots.length === 0 ? (
              <p className="text-caption text-muted-foreground/50 rounded-xl border border-border/60 bg-elevated/50 p-6 text-center">No snapshots yet.</p>
            ) : (
              snapshots.map(s => (
                <SnapshotRow
                  key={s.id}
                  snap={s}
                  diff={diffs[s.id]}
                  expanded={expandedId === s.id}
                  onToggle={() => toggleExpand(s.id)}
                  diffLoading={diffLoading === s.id}
                />
              ))
            )}
          </section>

          <section className="space-y-2.5">
            <h2 className="text-small font-semibold text-foreground flex items-center gap-2"><History size={14} className="text-primary" /> Run history</h2>
            {history.length === 0 ? (
              <p className="text-caption text-muted-foreground/50 rounded-xl border border-border/60 bg-elevated/50 p-6 text-center">No runs recorded yet.</p>
            ) : (
              <div className="rounded-xl border border-border/60 bg-elevated overflow-hidden">
                {history.map((r, i) => (
                  <div key={r.id} className={cn('flex items-center gap-3 px-4 py-2.5', i > 0 && 'border-t border-border/40')}>
                    <span className={cn(
                      'shrink-0 rounded-md border px-1.5 py-0.5 text-caption font-medium uppercase tracking-wide',
                      r.status === 'completed' ? 'border-success/30 bg-success/10 text-success'
                        : r.status === 'failed' ? 'border-danger/30 bg-danger/10 text-danger'
                          : r.status === 'running' ? 'border-warning/30 bg-warning/10 text-warning'
                            : 'border-border/60 bg-muted/30 text-muted-foreground',
                    )}>
                      {r.status}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-small font-medium text-foreground">{r.job_type}</p>
                      <p className="text-caption text-muted-foreground/60">{formatTime(r.started_at)}{r.snapshot_id ? ` · ${r.snapshot_id}` : ''}</p>
                    </div>
                    <div className="shrink-0 text-right text-caption text-muted-foreground/70">
                      <p>{r.duration_ms ? `${(r.duration_ms / 1000).toFixed(1)}s` : '—'}</p>
                      <p>{r.records_processed} records · {r.findings_generated} findings</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}

      {selectedTrigger && (
        <FindingDrawer
          trigger={selectedTrigger}
          diff={selectedTrigger.snapshot_id ? diffs[selectedTrigger.snapshot_id] ?? null : null}
          domain={brief?.health_domains?.find(d => d.domain === selectedTrigger.domain) ?? null}
          onClose={() => setSelectedTrigger(null)}
          onRunExperiment={() => { setSelectedTrigger(null); navigate('/experiments') }}
        />
      )}
    </div>
  )
}

export default OwnFlowPage
