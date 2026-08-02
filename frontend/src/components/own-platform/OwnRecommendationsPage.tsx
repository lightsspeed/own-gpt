import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import {
  AlertTriangle, CheckCircle2, ChevronDown, FlaskConical, GitBranch, Lightbulb, Loader2, RefreshCw,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import {
  operationsApi, type RecommendationRow, type RecommendationsWorkspace,
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

function SeverityDot({ severity }: { severity: string }) {
  const color = severity === 'critical' ? 'bg-danger' : severity === 'high' ? 'bg-warning' : severity === 'medium' ? 'bg-info' : 'bg-muted'
  return <span className={cn('inline-block w-1.5 h-1.5 rounded-full', color)} />
}

export function OwnRecommendationsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<RecommendationsWorkspace | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchAll = async () => {
    setLoading(true)
    setError(null)
    try {
      setData(await operationsApi.getRecommendations({ limit: 100 }))
    } catch (e: any) {
      setError(e.message || 'Failed to load recommendations')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const toggle = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const types = Array.from(new Set(data?.recommendations.map(r => r.type) ?? []))

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-[1100px] mx-auto p-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-h2 text-foreground">Recommendations</h1>
            <p className="text-caption text-muted-foreground mt-0.5">
              Machine proposals grounded in findings. Humans review, then approve or dismiss — nothing is applied automatically.
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

        {/* ── Summary ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-elevated border border-border/60 rounded-xl p-4">
            <p className="text-caption text-muted-foreground uppercase tracking-wider">Open</p>
            <p className="text-h3 text-foreground font-semibold mt-1">{loading ? '—' : data?.total ?? 0}</p>
          </div>
          <div className="bg-elevated border border-border/60 rounded-xl p-4">
            <p className="text-caption text-muted-foreground uppercase tracking-wider">For review</p>
            <p className="text-h3 text-warning font-semibold mt-1">{loading ? '—' : (data?.recommendations ?? []).filter(r => r.status === 'high').length}</p>
          </div>
          <div className="bg-elevated border border-border/60 rounded-xl p-4">
            <p className="text-caption text-muted-foreground uppercase tracking-wider">Types</p>
            <p className="text-h3 text-foreground font-semibold mt-1">{loading ? '—' : types.length}</p>
          </div>
          <div className="bg-elevated border border-border/60 rounded-xl p-4">
            <p className="text-caption text-muted-foreground uppercase tracking-wider">Approved</p>
            <p className="text-h3 text-success font-semibold mt-1">0</p>
          </div>
        </div>

        {/* ── List ── */}
        <Section title="Recommendation inbox" icon={Lightbulb}>
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground">
              <Loader2 size={18} className="animate-spin" /> Loading recommendations…
            </div>
          ) : !data || data.recommendations.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              <CheckCircle2 size={24} className="mx-auto mb-2 text-success/50" />
              <p className="text-small">No recommendations at this time.</p>
              <p className="text-caption text-muted-foreground/60 mt-1">Recommendations surface when the evidence engine finds actionable issues.</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {data.recommendations.map((r: RecommendationRow) => {
                const open = expanded.has(r.id)
                const observations = (r.evidence?.observations as string[] | undefined) ?? []
                return (
                  <div key={r.id} className="border border-border/60 rounded-lg overflow-hidden">
                    <button
                      onClick={() => toggle(r.id)}
                      className="w-full flex items-start gap-3 p-3.5 text-left hover:bg-hover/40 transition-all"
                    >
                      <div className="mt-1 shrink-0">
                        <SeverityDot severity={r.severity} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-small font-medium text-foreground">{r.title}</span>
                          <span className="text-caption capitalize bg-muted/20 border border-border/40 rounded-md px-2 py-0.5 text-muted-foreground">{r.type.replace(/_/g, ' ')}</span>
                          <span className="text-caption text-muted-foreground/50 font-mono">{r.id}</span>
                        </div>
                        <p className="text-caption text-muted-foreground/80 mt-1">{r.description}</p>
                      </div>
                      <ChevronDown size={16} className={cn('text-muted-foreground/40 mt-1 shrink-0 transition-transform duration-200', open && 'rotate-180')} />
                    </button>
                    {open && (
                      <div className="px-4 pb-4 pt-1 border-t border-border/50 bg-background/20 space-y-3 text-small">
                        {observations.length > 0 && (
                          <div>
                            <p className="text-caption text-muted-foreground uppercase tracking-wider mb-1.5">Evidence & observations</p>
                            <ul className="space-y-1">
                              {observations.map((o, i) => (
                                <li key={i} className="text-caption text-foreground/80 flex items-start gap-2">
                                  <span className="text-primary/60 mt-1">•</span> {o}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {(r.evidence?.root_cause_explanation || r.evidence?.root_cause) && (
                          <div>
                            <p className="text-caption text-muted-foreground uppercase tracking-wider mb-1">Diagnosis</p>
                            <p className="text-foreground/85">
                              {typeof r.evidence.root_cause_explanation === 'string'
                                ? r.evidence.root_cause_explanation
                                : `Root cause: ${String(r.evidence.root_cause)}`}
                            </p>
                          </div>
                        )}
                        <div className="flex flex-wrap gap-2 pt-1">
                          <button
                            onClick={() => navigate('/experiments')}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-caption font-medium hover:brightness-110 transition-all"
                            title="Experiment will measure this recommendation's impact"
                          >
                            <FlaskConical size={13} /> Run experiment
                          </button>
                          <span className="flex items-center gap-1.5 text-caption text-muted-foreground/60">
                            <GitBranch size={13} /> finding {r.finding_id}
                          </span>
                        </div>
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

export default OwnRecommendationsPage