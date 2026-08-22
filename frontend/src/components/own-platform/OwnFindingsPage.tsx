import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import {
  AlertTriangle, ChevronRight, Loader, RefreshCw, Search, ShieldAlert,
} from 'lucide-react'
import {
  operationsApi, type FindingRow, type FindingsWorkspace,
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

function SeverityBadge({ severity }: { severity: string }) {
  const color = severity === 'critical' ? 'text-danger bg-danger/10 border-danger/25'
    : severity === 'high' ? 'text-warning bg-warning/10 border-warning/25'
    : severity === 'medium' ? 'text-info bg-info/10 border-info/25'
    : 'text-muted-foreground bg-muted/20 border-border/40'
  return (
    <span className={cn('inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-caption font-medium capitalize', color)}>
      {severity === 'critical' && <AlertTriangle size={11} />}
      {severity}
    </span>
  )
}

function StrengthBadge({ label }: { label: string }) {
  const color = label === 'high' ? 'text-success bg-success/10 border-success/20'
    : label === 'medium' ? 'text-info bg-info/10 border-info/20'
    : label === 'low' ? 'text-warning bg-warning/10 border-warning/20'
    : 'text-muted-foreground bg-muted/20 border-border/40'
  return (
    <span className={cn('text-caption rounded-md border px-2 py-0.5', color)}>evidence: {label}</span>
  )
}

export function OwnFindingsPage() {
  const [data, setData] = useState<FindingsWorkspace | null>(null)
  const [severity, setSeverity] = useState('')
  const [category, setCategory] = useState('')
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchAll = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await operationsApi.getFindings({ severity: severity || undefined, category: category || undefined, limit: 100 })
      setData(res)
    } catch (e: any) {
      setError(e.message || 'Failed to load findings')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [severity, category])

  const categories = Array.from(new Set(data?.findings.map(f => f.category) ?? []))
  const counts = {
    critical: data?.findings.filter(f => f.severity === 'critical').length ?? 0,
    high: data?.findings.filter(f => f.severity === 'high').length ?? 0,
    total: data?.total ?? 0,
  }

  const toggle = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-[1100px] mx-auto p-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-h2 text-foreground">Findings</h1>
            <p className="text-caption text-muted-foreground mt-0.5">
              Evidence-backed issues surfaced from the learning ledger. Prioritized by severity × evidence strength × frequency × trend.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={fetchAll}
              disabled={loading}
              className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-hover transition-all disabled:opacity-50"
              title="Refresh"
            >
              <RefreshCw size={18} className={cn(loading && 'animate-spin')} />
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-xs text-destructive bg-danger/10 border border-danger/20 rounded-lg p-2.5">
            <AlertTriangle size={13} />
            <span>{error}</span>
          </div>
        )}

        {/* ── Summary cards ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-elevated border border-border/60 rounded-xl p-4">
            <p className="text-caption text-muted-foreground uppercase tracking-wider">Total</p>
            <p className="text-h3 text-foreground font-semibold mt-1">{loading ? '—' : counts.total}</p>
          </div>
          <div className="bg-elevated border border-danger/20 rounded-xl p-4">
            <p className="text-caption text-danger/70 uppercase tracking-wider">Critical</p>
            <p className="text-h3 text-danger font-semibold mt-1">{loading ? '—' : counts.critical}</p>
          </div>
          <div className="bg-elevated border border-warning/20 rounded-xl p-4">
            <p className="text-caption text-warning/70 uppercase tracking-wider">High</p>
            <p className="text-h3 text-warning font-semibold mt-1">{loading ? '—' : counts.high}</p>
          </div>
          <div className="bg-elevated border border-border/60 rounded-xl p-4">
            <p className="text-caption text-muted-foreground uppercase tracking-wider">Categories</p>
            <p className="text-h3 text-foreground font-semibold mt-1">{loading ? '—' : categories.length}</p>
          </div>
        </div>

        {/* ── Filters ── */}
        <Section title="Filters" icon={Search}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-caption text-muted-foreground/70">Severity</span>
            {[{ v: '', l: 'All' }, { v: 'critical', l: 'Critical' }, { v: 'high', l: 'High' }, { v: 'medium', l: 'Medium' }, { v: 'low', l: 'Low' }].map(s => (
              <button
                key={s.v}
                onClick={() => setSeverity(s.v)}
                className={cn(
                  'px-3 py-1 rounded-lg border text-small transition-all',
                  severity === s.v ? 'bg-primary/10 border-primary/30 text-foreground' : 'border-border/50 text-muted-foreground/70 hover:bg-hover hover:text-foreground',
                )}
              >
                {s.l}
              </button>
            ))}
            {categories.length > 1 && (
              <>
                <span className="text-caption text-muted-foreground/70 ml-3">Category</span>
                <select
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                  className="rounded-lg border border-border bg-background/50 px-2.5 py-1 text-small text-foreground outline-none focus:border-primary/40"
                >
                  <option value="">All categories</option>
                  {categories.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
                </select>
              </>
            )}
          </div>
        </Section>

        {/* ── Findings list ── */}
        <Section title={`Findings (${data?.findings.length ?? 0})`} icon={ShieldAlert}>
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground">
              <Loader size={18} className="animate-spin" /> Loading findings…
            </div>
          ) : !data || data.findings.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              <AlertTriangle size={24} className="mx-auto mb-2 text-muted-foreground/40" />
              <p className="text-small">No findings match the current filters.</p>
              <p className="text-caption text-muted-foreground/60 mt-1">Findings appear after evaluation runs surface degrading signals.</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {data.findings.map((f: FindingRow) => {
                const open = expanded.has(f.id)
                return (
                  <div key={f.id} className="border border-border/60 rounded-lg overflow-hidden">
                    <button
                      onClick={() => toggle(f.id)}
                      className="w-full flex items-start gap-3 p-3.5 text-left hover:bg-hover/40 transition-all"
                    >
                      <div className="flex flex-col items-center gap-2 shrink-0">
                        <span className={cn(
                          'text-h4 font-bold w-12 text-center rounded-lg py-1 border',
                          f.priority >= 75 ? 'text-danger border-danger/30 bg-danger/5' : f.priority >= 40 ? 'text-warning border-warning/30 bg-warning/5' : 'text-muted-foreground border-border/30 bg-muted/10',
                        )}>
                          {f.priority}
                        </span>
                        <span className="text-[10px] text-muted-foreground/50 uppercase tracking-wider">priority</span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-small font-medium text-foreground">{f.title}</span>
                          <SeverityBadge severity={f.severity} />
                          <StrengthBadge label={f.evidence_strength} />
                        </div>
                        <p className="text-caption text-muted-foreground/80 mt-1 line-clamp-2">{f.description}</p>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5 text-caption text-muted-foreground/60">
                          <span>{f.category.replace(/_/g, ' ')}</span>
                          <span>root cause: {f.root_cause.replace(/_/g, ' ')}</span>
                          <span>{f.sample_size} samples</span>
                          <span>confidence {(f.evidence_confidence * 100).toFixed(0)}%</span>
                          {f.created_at && <span>{new Date(f.created_at).toLocaleString()}</span>}
                        </div>
                      </div>
                      <ChevronRight size={16} className={cn('text-muted-foreground/40 mt-1 shrink-0 transition-transform duration-200', open && 'rotate-90')} />
                    </button>
                    {open && (
                      <div className="px-4 pb-4 pt-1 border-t border-border/50 bg-background/20 space-y-2.5 text-small">
                        <div>
                          <p className="text-caption text-muted-foreground uppercase tracking-wider mb-1">Recommended action</p>
                          <p className="text-foreground/85">{f.recommendation_text || 'No recommendation attached.'}</p>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div>
                            <p className="text-caption text-muted-foreground uppercase tracking-wider mb-1">Evidence</p>
                            <p className="text-caption text-muted-foreground/80">
                              Strength {f.evidence_strength} · confidence {(f.evidence_confidence * 100).toFixed(0)}% · {f.sample_size} records · trend {f.trend}
                            </p>
                          </div>
                          <div>
                            <p className="text-caption text-muted-foreground uppercase tracking-wider mb-1">Lineage</p>
                            <p className="text-caption text-muted-foreground/80 font-mono">
                              {f.id} → {f.lineage?.parent_type ?? 'root'}
                            </p>
                          </div>
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

export default OwnFindingsPage