import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import {
  AlertTriangle, Archive, GitBranch, History, Loader2, Network, RefreshCw,
} from 'lucide-react'
import { operationsApi, type ArtifactTrace } from '@/features/operations/services/operationsApi'
import { automationApi } from '@/features/automation/services/automationApi'

interface ArtifactEntry {
  id: string
  type: string
  stage: string
  title: string
  detail: string
  created_at: string | null
}

function stageFor(type: string): string {
  if (type === 'evaluation_snapshot') return 'measure'
  if (type === 'configuration_snapshot') return 'apply'
  if (type === 'decision') return 'apply'
  if (type === 'finding') return 'explain'
  if (type === 'recommendation') return 'propose'
  if (type === 'experiment') return 'validate'
  if (type === 'evidence') return 'explain'
  return 'observe'
}

const TRACE_STEP_COLORS: Record<string, string> = {
  configuration_snapshot: 'text-info bg-info/10 border-info/25',
  decision: 'text-success bg-success/10 border-success/25',
  decision_candidate: 'text-warning bg-warning/10 border-warning/25',
  experiment: 'text-primary bg-primary/10 border-primary/25',
  recommendation: 'text-info bg-info/10 border-info/25',
  finding: 'text-warning bg-warning/10 border-warning/25',
  evidence: 'text-success bg-success/10 border-success/25',
  analytics_report: 'text-primary bg-primary/10 border-primary/25',
  unknown: 'text-muted-foreground bg-muted/20 border-border/40',
}

export function OwnArtifactsPage() {
  const [entries, setEntries] = useState<ArtifactEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [trace, setTrace] = useState<{ id: string; data: ArtifactTrace | null; loading: boolean } | null>(null)
  const [collapsed, setCollapsed] = useState(false)

  const fetchAll = async () => {
    setLoading(true)
    setError(null)
    const list: ArtifactEntry[] = []
    try {
      try {
        const snaps = await automationApi.getSnapshots(20)
        for (const s of snaps) {
          list.push({
            id: s.id,
            type: 'evaluation_snapshot',
            stage: stageFor('evaluation_snapshot'),
            title: `Evaluation snapshot · ${s.timestamp ? new Date(s.timestamp).toLocaleDateString() : ''}`,
            detail: `${s.record_count} records · health ${(s.health_scores?.overall ?? 0).toFixed(0)} · ${s.findings_count} findings`,
            created_at: s.timestamp ?? null,
          })
        }
      } catch { /* skip */ }

      try {
        const cfg = await operationsApi.getConfigSnapshots(20)
        for (const s of cfg) {
          list.push({
            id: s.id,
            type: 'configuration_snapshot',
            stage: stageFor('configuration_snapshot'),
            title: s.name || `Config snapshot v${s.version}`,
            detail: `${Object.keys(s.parameters ?? {}).length} parameters${s.is_current ? ' · current' : ''}`,
            created_at: s.created_at ?? null,
          })
        }
      } catch { /* skip */ }

      try {
        const fw = await operationsApi.getFindings({ limit: 50 })
        for (const f of fw.findings) {
          list.push({
            id: f.id,
            type: 'finding',
            stage: stageFor('finding'),
            title: f.title,
            detail: `${f.severity} · ${f.category.replace(/_/g, ' ')} · priority ${f.priority}`,
            created_at: f.created_at ?? null,
          })
        }
      } catch { /* skip */ }

      try {
        const rw = await operationsApi.getRecommendations({ limit: 50 })
        for (const r of rw.recommendations) {
          list.push({
            id: r.id,
            type: 'recommendation',
            stage: stageFor('recommendation'),
            title: r.title,
            detail: `${r.type.replace(/_/g, ' ')} · severity ${r.severity}`,
            created_at: r.lineage?.created_at ?? null,
          })
        }
      } catch { /* skip */ }

      setEntries(list)
    } catch (e: any) {
      setError(e.message || 'Failed to load artifacts')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const filtered = filter ? entries.filter(e => e.type === filter) : entries

  const openTrace = async (id: string) => {
    if (trace?.id === id) {
      setTrace(null)
      return
    }
    setTrace({ id, data: null, loading: true })
    try {
      const traceData = await operationsApi.exploreArtifact(id)
      setTrace({ id, data: traceData, loading: false })
    } catch {
      setTrace({ id, data: null, loading: false })
    }
  }

  const types = Array.from(new Set(entries.map(e => e.type)))
  const stages = Array.from(new Set(entries.map(e => e.stage)))

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-[1100px] mx-auto p-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-h2 text-foreground">Artifact Explorer</h1>
            <p className="text-caption text-muted-foreground mt-0.5">
              Every immutable artifact in the platform, with lineage links back to its parent. Nothing is ever mutated or overwritten.
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

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-elevated border border-border/60 rounded-xl p-4">
            <p className="text-caption text-muted-foreground uppercase tracking-wider">Artifacts</p>
            <p className="text-h3 text-foreground font-semibold mt-1">{loading ? '—' : entries.length}</p>
          </div>
          <div className="bg-elevated border border-border/60 rounded-xl p-4">
            <p className="text-caption text-muted-foreground uppercase tracking-wider">Types</p>
            <p className="text-h3 text-primary font-semibold mt-1">{loading ? '—' : types.length}</p>
          </div>
          <div className="bg-elevated border border-border/60 rounded-xl p-4">
            <p className="text-caption text-muted-foreground uppercase tracking-wider">Stages</p>
            <p className="text-h3 text-success font-semibold mt-1">{loading ? '—' : stages.length}</p>
          </div>
          <div className="bg-elevated border border-border/60 rounded-xl p-4">
            <p className="text-caption text-muted-foreground uppercase tracking-wider">Traced</p>
            <p className="text-h3 text-info font-semibold mt-1">{trace ? 1 : 0}</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-caption text-muted-foreground/70">Type</span>
          <button
            onClick={() => setFilter('')}
            className={cn(
              'px-3 py-1 rounded-lg border text-small transition-all',
              filter === '' ? 'bg-primary/10 border-primary/30 text-foreground' : 'border-border/50 text-muted-foreground/70 hover:bg-hover hover:text-foreground',
            )}
          >
            All
          </button>
          {types.map(t => (
            <button
              key={t}
              onClick={() => setFilter(t)}
              className={cn(
                'px-3 py-1 rounded-lg border text-small transition-all',
                filter === t ? 'bg-primary/10 border-primary/30 text-foreground' : 'border-border/50 text-muted-foreground/70 hover:bg-hover hover:text-foreground',
              )}
            >
              {t.replace(/_/g, ' ')}
            </button>
          ))}
        </div>

        <div className="bg-elevated border border-border/60 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Network size={16} className="text-muted-foreground" />
              <h2 className="text-small font-semibold text-foreground uppercase tracking-wider">Artifact ledger</h2>
            </div>
            <button
              onClick={() => setCollapsed(c => !c)}
              className="text-caption text-muted-foreground/60 hover:text-foreground transition-all"
            >
              {collapsed ? 'Expand' : 'Collapse'}
            </button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground">
              <Loader2 size={18} className="animate-spin" /> Loading artifacts…
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              <Archive size={24} className="mx-auto mb-2 text-muted-foreground/40" />
              <p className="text-small">No artifacts found.</p>
              <p className="text-caption text-muted-foreground/60 mt-1">Artifacts appear once evaluation runs, recommendations surface, and configurations are snapshotted.</p>
            </div>
          ) : (
            <div className={cn('space-y-2', collapsed && 'max-h-[420px] overflow-y-auto custom-scrollbar pr-1')}>
              {filtered.map((e) => (
                <div key={e.id} className="border border-border/60 rounded-lg overflow-hidden">
                  <button
                    onClick={() => openTrace(e.id)}
                    className="w-full flex items-start gap-3 p-3 text-left hover:bg-hover/40 transition-all group"
                  >
                    <span className={cn(
                      'mt-0.5 shrink-0 inline-block text-caption uppercase rounded-md border px-2 py-0.5 font-medium',
                      e.stage === 'apply' ? 'text-danger bg-danger/10 border-danger/25' : 'text-info bg-info/10 border-info/25',
                    )}>
                      {e.stage}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-small font-medium text-foreground">{e.title}</span>
                        <span className="text-caption text-muted-foreground/50 font-mono">{e.id}</span>
                      </div>
                      <p className="text-caption text-muted-foreground/70 mt-0.5">{e.detail}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {e.created_at && <span className="text-caption text-muted-foreground/40 hidden sm:inline">{new Date(e.created_at).toLocaleString()}</span>}
                      <span className={cn('flex items-center gap-1 text-caption text-muted-foreground/50 group-hover:text-primary transition-all', trace?.id === e.id && 'text-primary')}>
                        <GitBranch size={13} /> {trace?.id === e.id ? 'traced' : 'trace'}
                      </span>
                    </div>
                  </button>
                  {trace?.id === e.id && (
                    <div className="px-4 pb-4 pt-1 border-t border-border/50 bg-background/20">
                      <div className="flex items-center gap-2 mb-2">
                        <History size={13} className="text-muted-foreground" />
                        <span className="text-caption uppercase tracking-wider text-muted-foreground">Lineage chain</span>
                      </div>
                      {trace.loading ? (
                        <div className="flex items-center gap-2 py-3 text-caption text-muted-foreground">
                          <Loader2 size={14} className="animate-spin" /> Tracing lineage…
                        </div>
                      ) : !trace.data || trace.data.chain.length === 0 ? (
                        <p className="text-caption text-muted-foreground/60">No lineage back-links resolved for this artifact.</p>
                      ) : (
                        <div className="space-y-1.5">
                          {trace.data.chain.map((step, j) => (
                            <div key={j} className="flex items-center gap-2">
                              {j > 0 && <span className="text-muted-foreground/30 w-5 text-right shrink-0">↑</span>}
                              <span className={cn('inline-block text-caption capitalize rounded-md border px-2 py-0.5', TRACE_STEP_COLORS[step.type] ?? 'text-muted-foreground bg-muted/20 border-border/40')}>
                                {step.type.replace(/_/g, ' ')}
                              </span>
                              <span className="text-caption text-muted-foreground/60 font-mono truncate">
                                {step.data?.id ?? step.data?.name ?? step.type}
                              </span>
                            </div>
                          ))}
                          <div className="flex items-center gap-2 pt-1">
                            <span className="w-5 shrink-0" />
                            <span className="text-caption text-muted-foreground/60">→ root: {trace.data.root_artifact_id} · depth {trace.data.depth}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default OwnArtifactsPage