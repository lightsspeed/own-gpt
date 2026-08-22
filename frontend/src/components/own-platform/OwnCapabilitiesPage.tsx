import { useEffect, useMemo, useState } from 'react'
import { cn } from '@/lib/utils'
import { Boxes, RefreshCw, Search, AlertTriangle, Loader2, GitBranch, FileJson } from 'lucide-react'
import { capabilitiesApi, type Capability } from '@/features/capabilities/services/capabilitiesApi'

const STAGES = ['observe', 'measure', 'explain', 'propose', 'validate', 'apply', 'operate']

const MATURITY_COLORS: Record<string, string> = {
  mature: 'text-success bg-success/10 border-success/20',
  implemented: 'text-primary bg-primary/10 border-primary/25',
  experimental: 'text-warning bg-warning/10 border-warning/20',
}

function MaturityBadge({ maturity }: { maturity: string }) {
  return (
    <span className={cn(
      'inline-flex items-center rounded-lg border px-2 py-0.5 text-caption font-medium capitalize',
      MATURITY_COLORS[maturity] ?? 'text-muted-foreground bg-muted/20 border-border/40',
    )}>
      {maturity}
    </span>
  )
}

function Chip({ label, title }: { label: string; title?: string }) {
  return (
    <span
      title={title ?? label}
      className="inline-flex items-center rounded-md border border-border/40 bg-background/50 px-1.5 py-0.5 text-[11px] text-muted-foreground/80 max-w-full truncate"
    >
      {label}
    </span>
  )
}

function CapabilityCard({ id, cap }: { id: string; cap: Capability }) {
  return (
    <div className="rounded-xl border border-border/60 bg-elevated p-4 flex flex-col gap-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-small font-semibold text-foreground truncate">{cap.name}</p>
          <p className="text-[11px] font-mono text-muted-foreground/50 mt-0.5 truncate">{id}</p>
        </div>
        <MaturityBadge maturity={cap.maturity} />
      </div>

      <div className="text-caption text-muted-foreground/70">
        <span className="text-muted-foreground/50">Owner</span> <span className="font-mono">{cap.owner}</span>
      </div>

      {cap.dependencies.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <GitBranch size={11} className="text-muted-foreground/40 shrink-0" />
          {cap.dependencies.map(d => <Chip key={d} label={d} title={`Depends on ${d}`} />)}
        </div>
      )}

      {cap.artifacts.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          <FileJson size={11} className="text-muted-foreground/40 shrink-0" />
          {cap.artifacts.map(a => <Chip key={a} label={a} />)}
        </div>
      )}

      {cap.api_prefix && (
        <div className="text-[11px] font-mono text-muted-foreground/50 bg-background/40 border border-border/30 rounded-md px-2 py-1 truncate">
          {cap.api_prefix}
        </div>
      )}
    </div>
  )
}

export function OwnCapabilitiesPage() {
  const [data, setData] = useState<Record<string, Capability>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [stage, setStage] = useState<string | null>(null)
  const [maturity, setMaturity] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const res = await capabilitiesApi.list()
      setData(res.capabilities)
    } catch (e: any) {
      setError(e?.message || 'Failed to load capabilities')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return Object.entries(data).filter(([id, cap]) => {
      if (stage && cap.lifecycle_stage !== stage) return false
      if (maturity && cap.maturity !== maturity) return false
      if (q) {
        const hay = `${id} ${cap.name} ${cap.owner} ${cap.dependencies.join(' ')}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })
  }, [data, query, stage, maturity])

  const grouped = useMemo(() => {
    const groups: { stage: string; items: [string, Capability][] }[] = []
    for (const s of STAGES) {
      const items = filtered.filter(([, cap]) => cap.lifecycle_stage === s)
      if (items.length > 0) groups.push({ stage: s, items })
    }
    const other = filtered.filter(([, cap]) => !STAGES.includes(cap.lifecycle_stage))
    if (other.length > 0) groups.push({ stage: 'other', items: other })
    return groups
  }, [filtered])

  const maturities = useMemo(() => Array.from(new Set(Object.values(data).map(c => c.maturity))), [data])

  return (
    <div className="h-full overflow-y-auto custom-scrollbar flex flex-col gap-4 p-4 md:p-6 max-w-5xl mx-auto w-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-title font-semibold text-foreground">Capability Registry</h1>
          <p className="text-caption text-muted-foreground/60 mt-0.5">
            Every subsystem registered on the platform — owner, lifecycle stage, maturity, and artifacts.
          </p>
        </div>
        <button
          onClick={load}
          className="rounded-lg border border-border/60 px-3 py-2 text-small text-muted-foreground hover:text-foreground transition-colors inline-flex items-center gap-1.5"
        >
          <RefreshCw size={13} className={cn(loading && 'animate-spin')} /> Refresh
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search name, id, owner, dependency…"
            className="w-full rounded-lg border border-border bg-background/50 px-8 py-2 text-small text-foreground placeholder:text-muted-foreground/40 outline-none transition-colors focus:border-primary/40"
          />
        </div>
        <select
          value={maturity ?? ''}
          onChange={e => setMaturity(e.target.value || null)}
          className="rounded-lg border border-border bg-background/50 px-3 py-2 text-small text-foreground outline-none focus:border-primary/40"
        >
          <option value="">All maturities</option>
          {maturities.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => setStage(null)}
          className={cn(
            'rounded-lg border px-3 py-1.5 text-caption transition-colors',
            stage === null
              ? 'border-primary/30 bg-primary/10 text-primary font-medium'
              : 'border-border/50 text-muted-foreground/60 hover:text-foreground',
          )}
        >
          All ({Object.keys(data).length})
        </button>
        {STAGES.map(s => (
          <button
            key={s}
            onClick={() => setStage(stage === s ? null : s)}
            className={cn(
              'rounded-lg border px-3 py-1.5 text-caption capitalize transition-colors',
              stage === s
                ? 'border-primary/30 bg-primary/10 text-primary font-medium'
                : 'border-border/50 text-muted-foreground/60 hover:text-foreground',
            )}
          >
            {s}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground/60">
          <Loader2 size={16} className="animate-spin" /> Loading registry…
        </div>
      ) : error ? (
        <div className="rounded-xl border border-danger/30 bg-danger/10 p-6 text-center">
          <AlertTriangle size={24} className="mx-auto text-danger mb-3" />
          <p className="text-small text-danger font-medium">Failed to load capabilities</p>
          <p className="text-caption text-muted-foreground/70 mt-1">{error}</p>
          <button
            onClick={load}
            className="mt-4 rounded-lg border border-border/60 px-3 py-2 text-small text-foreground hover:bg-hover transition-colors inline-flex items-center gap-1.5"
          >
            <RefreshCw size={13} /> Retry
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-border/60 bg-elevated/50 p-10 text-center">
          <Boxes size={28} className="mx-auto text-muted-foreground/40 mb-3" />
          <p className="text-small text-muted-foreground/70">No capabilities match the current filters.</p>
        </div>
      ) : (
        <div className="space-y-5">
          {grouped.map(group => (
            <div key={group.stage}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground/50">
                  {group.stage}
                </span>
                <span className="text-caption text-muted-foreground/30">({group.items.length})</span>
                <div className="flex-1 h-px bg-border/50" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {group.items.map(([id, cap]) => <CapabilityCard key={id} id={id} cap={cap} />)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default OwnCapabilitiesPage
