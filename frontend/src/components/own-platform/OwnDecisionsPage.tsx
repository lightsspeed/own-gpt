import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import {
  AlertTriangle, CheckCircle2, ChevronRight, GitBranch, Loader2, RefreshCw, Scale,
} from 'lucide-react'
import {
  operationsApi, type ArtifactTrace, type DecisionRow, type DecisionsWorkspace,
} from '@/features/operations/services/operationsApi'

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

const TRACE_COLORS: Record<string, string> = {
  configuration_snapshot: 'text-info bg-info/10 border-info/25',
  decision: 'text-success bg-success/10 border-success/25',
  decision_candidate: 'text-warning bg-warning/10 border-warning/25',
  experiment: 'text-primary bg-primary/10 border-primary/25',
  recommendation: 'text-info bg-info/10 border-info/25',
  finding: 'text-warning bg-warning/10 border-warning/25',
  evidence: 'text-success bg-success/10 border-success/25',
}

export function OwnDecisionsPage() {
  const [data, setData] = useState<DecisionsWorkspace | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [trace, setTrace] = useState<{ id: string; data: ArtifactTrace } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchAll = async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await operationsApi.getDecisions({ status: statusFilter || undefined, limit: 100 }))
    } catch (e: any) {
      setError(e.message || 'Failed to load decisions')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter])

  const toggle = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const openTrace = async (id: string) => {
    if (trace?.id === id) {
      setTrace(null)
      return
    }
    try {
      const data = await operationsApi.exploreArtifact(id)
      setTrace({ id, data })
    } catch {
      setTrace({ id, data: { root_artifact_id: id, chain: [], depth: 0 } })
    }
  }

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-[1100px] mx-auto p-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-h2 text-foreground">Decisions</h1>
            <p className="text-caption text-muted-foreground mt-0.5">
              Human decisions that change production configuration. Every decision carries full lineage back to evidence.
            </p>
          </div>
          <button
            onClick={fetchAll}
            disabled={loading}
            className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-hover transition-all disabled:opacity-50 shrink-0"
            title="Refresh"
          >
            <RefreshCw size={18} className={cn(loading && 'animate-spin')} />
          </button>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-xs text-destructive bg-danger/10 border border-danger/20 rounded-lg p-2.5">
            <AlertTriangle size={13} />
            <span>{error}</span>
          </div>
        )}

        {/* ── Status filter ── */}
        <Section title="Filters" icon={Scale}>
          <div className="flex flex-wrap items-center gap-2">
            {[{ v: '', l: 'All' }, { v: 'approved', l: 'Approved' }, { v: 'archived', l: 'Archived' }].map(s => (
              <button
                key={s.v}
                onClick={() => setStatusFilter(s.v)}
                className={cn(
                  'px-3 py-1 rounded-lg border text-small transition-all',
                  statusFilter === s.v ? 'bg-primary/10 border-primary/30 text-foreground' : 'border-border/50 text-muted-foreground/70 hover:bg-hover hover:text-foreground',
                )}
              >
                {s.l}
              </button>
            ))}
          </div>
        </Section>

        {/* ── Decision list ── */}
        <Section title={`Decisions (${data?.total ?? 0})`} icon={CheckCircle2}>
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground">
              <Loader2 size={18} className="animate-spin" /> Loading decisions…
            </div>
          ) : !data || data.decisions.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              <Scale size={24} className="mx-auto mb-2 text-muted-foreground/40" />
              <p className="text-small">No decisions recorded yet.</p>
              <p className="text-caption text-muted-foreground/60 mt-1">
                Decisions are created when an experiment candidate is approved and its configuration snapshot is applied.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {data.decisions.map((d: DecisionRow) => {
                const open = expanded.has(d.id)
                return (
                  <div key={d.id} className="border border-border/60 rounded-lg overflow-hidden">
                    <button
                      onClick={() => toggle(d.id)}
                      className="w-full flex items-start gap-3 p-3.5 text-left hover:bg-hover/40 transition-all"
                    >
                      <div className="mt-0.5 shrink-0">
                        <span className={cn(
                          'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-caption capitalize',
                          d.status === 'approved' ? 'text-success bg-success/10 border-success/25' : 'text-muted-foreground bg-muted/20 border-border/40',
                        )}>
                          {d.status === 'approved' && <CheckCircle2 size={11} />}
                          {d.status}
                        </span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-small font-medium text-foreground">{d.name || 'Untitled decision'}</span>
                          <span className="text-caption text-muted-foreground/50 font-mono">{d.id}</span>
                        </div>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1 text-caption text-muted-foreground/60">
                          {d.description && <span>{d.description}</span>}
                          <span>config v{d.config_version}</span>
                          {d.config_snapshot_id && <span>{d.config_snapshot_id}</span>}
                          {d.applied_at && <span>{new Date(d.applied_at).toLocaleString()}</span>}
                        </div>
                      </div>
                      <ChevronRight size={16} className={cn('text-muted-foreground/40 mt-1 shrink-0 transition-transform duration-200', open && 'rotate-90')} />
                    </button>
                    {open && (
                      <div className="px-4 pb-4 pt-1 border-t border-border/50 bg-background/20 space-y-3 text-small">
                        <div className="flex flex-wrap gap-2">
                          {d.experiment_id && (
                            <span className="text-caption bg-muted/20 border border-border/40 rounded-md px-2 py-0.5">
                              experiment <span className="font-mono text-foreground/80">{d.experiment_id}</span>
                            </span>
                          )}
                          {d.config_snapshot_id && (
                            <span className="text-caption bg-muted/20 border border-border/40 rounded-md px-2 py-0.5">
                              config <span className="font-mono text-foreground/80">{d.config_snapshot_id}</span>
                            </span>
                          )}
                          {d.lineage?.parent_type && (
                            <span className="flex items-center gap-1 text-caption text-muted-foreground/60">
                              <GitBranch size={12} /> parent: {d.lineage.parent_type}
                            </span>
                          )}
                        </div>
                        <button
                          onClick={() => openTrace(d.id)}
                          className="flex items-center gap-1.5 text-caption text-primary hover:brightness-110 transition-all"
                        >
                          <GitBranch size={13} /> {trace?.id === d.id ? 'Hide lineage trace' : 'Trace full lineage'}
                        </button>
                        {trace?.id === d.id && (
                          <div className="space-y-1.5 pt-1">
                            {trace.data.chain.length === 0 ? (
                              <p className="text-caption text-muted-foreground/60">No lineage steps resolved for this artifact.</p>
                            ) : (
                              trace.data.chain.map((step, i) => (
                                <div key={i} className="flex items-center gap-2">
                                  {i > 0 && <span className="text-muted-foreground/30 w-5 text-right">↓</span>}
                                  <span className={cn('inline-block text-caption rounded-md border px-2 py-0.5 capitalize', TRACE_COLORS[step.type] ?? 'text-muted-foreground bg-muted/20 border-border/40')}>
                                    {step.type.replace(/_/g, ' ')}
                                  </span>
                                  <span className="text-caption text-muted-foreground/60 font-mono">
                                    {step.data?.id ?? step.data?.name ?? step.type}
                                  </span>
                                </div>
                              ))
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </Section>
      </div>
    </div>
  )
}

export default OwnDecisionsPage