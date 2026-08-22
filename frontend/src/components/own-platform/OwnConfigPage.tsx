import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import {
  AlertTriangle, CheckCheck, ChevronDown, Cog, FilePlus2, History, Loader2, RefreshCw, RotateCcw, GitBranch,
} from 'lucide-react'
import {
  operationsApi, type ConfigDiff, type ConfigSnapshot,
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

export function OwnConfigPage() {
  const [snapshots, setSnapshots] = useState<ConfigSnapshot[]>([])
  const [current, setCurrent] = useState<ConfigSnapshot | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notify, setNotify] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [diff, setDiff] = useState<{ id: string; data: ConfigDiff | null } | null>(null)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [showCreate, setShowCreate] = useState(false)

  const fetchAll = async () => {
    setLoading(true)
    setError(null)
    try {
      const cfg = await operationsApi.getConfigurations(100)
      setSnapshots(cfg.snapshots)
      setCurrent(cfg.current)
    } catch (e: any) {
      setError(e.message || 'Failed to load configuration')
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

  const loadDiff = async (id: string) => {
    if (diff?.id === id) {
      setDiff(null)
      return
    }
    setDiff({ id, diff: null })
    try {
      const d = await operationsApi.diffAgainstCurrent(id)
      setDiff({ id, diff: d })
    } catch {
      setDiff({ id, diff: null })
    }
  }

  const handleCreate = async () => {
    setBusy(true)
    setError(null)
    setNotify(null)
    try {
      await operationsApi.createConfigSnapshot({ name: newName, description: newDesc })
      setNewName('')
      setNewDesc('')
      setShowCreate(false)
      setNotify('Snapshot created.')
      await fetchAll()
    } catch (e: any) {
      setError(e.message || 'Failed to create snapshot')
    } finally {
      setBusy(false)
    }
  }

  const handleRollback = async (id: string) => {
    setBusy(true)
    setError(null)
    setNotify(null)
    try {
      await operationsApi.rollbackConfig(id)
      setNotify(`Rolled back to ${id}.`)
      await fetchAll()
    } catch (e: any) {
      setError(e.message || 'Rollback failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-[1100px] mx-auto p-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-h2 text-foreground">Own Config</h1>
            <p className="text-caption text-muted-foreground mt-0.5">
              Configuration is an artifact — never mutated. Each change creates a new snapshot. Rollback only moves the pointer.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={fetchAll}
              disabled={loading || busy}
              className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-hover transition-all disabled:opacity-50"
              title="Refresh"
            >
              <RefreshCw size={18} className={cn(loading && 'animate-spin')} />
            </button>
            <button
              onClick={() => setShowCreate(s => !s)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-primary text-primary-foreground text-small font-medium hover:brightness-110 transition-all"
            >
              <FilePlus2 size={14} /> New snapshot
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-xs text-destructive bg-danger/10 border border-danger/20 rounded-lg p-2.5">
            <AlertTriangle size={13} />
            <span>{error}</span>
          </div>
        )}
        {notify && (
          <div className="flex items-center gap-2 text-xs text-success bg-success/10 border border-success/20 rounded-lg p-2.5">
            <CheckCheck size={13} />
            <span>{notify}</span>
          </div>
        )}

        {showCreate && (
          <Section title="Create configuration snapshot" icon={Cog}>
            <div className="space-y-3">
              <input
                className={inputCls}
                placeholder="Snapshot name"
                value={newName}
                onChange={e => setNewName(e.target.value)}
              />
              <input
                className={inputCls}
                placeholder="Description (optional)"
                value={newDesc}
                onChange={e => setNewDesc(e.target.value)}
              />
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleCreate}
                  disabled={busy}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-small font-medium hover:brightness-110 transition-all disabled:opacity-50"
                >
                  {busy ? <Loader2 size={14} className="animate-spin" /> : <FilePlus2 size={14} />} Create
                </button>
                <button
                  onClick={() => setShowCreate(false)}
                  className="px-4 py-2 rounded-lg bg-elevated border border-border text-foreground text-small font-medium hover:bg-hover transition-all"
                >
                  Cancel
                </button>
              </div>
            </div>
          </Section>
        )}

        {/* ── Current ── */}
        <Section title="Current configuration" icon={CheckCheck}>
          {loading ? (
            <div className="flex items-center gap-2 py-6 text-muted-foreground text-small">
              <Loader2 size={16} className="animate-spin" /> Loading…
            </div>
          ) : current ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 rounded-md border border-success/25 bg-success/10 px-2 py-0.5 text-caption text-success font-medium">
                  <CheckCheck size={11} /> current
                </span>
                <span className="text-small font-medium text-foreground">{current.name || `Config v${current.version}`}</span>
                <span className="text-caption text-muted-foreground/50 font-mono">{current.id}</span>
                <span className="text-caption text-muted-foreground/60">v{current.version}</span>
              </div>
              <table className="w-full text-small">
                <thead>
                  <tr className="text-caption text-muted-foreground/60 uppercase tracking-wider">
                    <th className="text-left py-2 pr-3 font-medium w-1/2">Parameter</th>
                    <th className="text-left py-2 font-medium">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(current.parameters ?? {}).map(([k, v]) => (
                    <tr key={k} className="border-t border-border/40">
                      <td className="py-1.5 pr-3 text-muted-foreground font-mono">{k}</td>
                      <td className="py-1.5 text-foreground font-mono">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-small text-muted-foreground/70 py-2">
              No current configuration set. Create your first snapshot to establish the baseline.
            </p>
          )}
        </Section>

        {/* ── History ── */}
        <Section title={`Configuration history (${snapshots.length})`} icon={History}>
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground">
              <Loader2 size={18} className="animate-spin" /> Loading snapshots…
            </div>
          ) : snapshots.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              <Cog size={24} className="mx-auto mb-2 text-muted-foreground/40" />
              <p className="text-small">No configuration snapshots yet.</p>
              <p className="text-caption text-muted-foreground/60 mt-1">Use "New snapshot" to capture the production configuration baseline.</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {snapshots.map((s) => {
                const open = expanded.has(s.id)
                return (
                  <div key={s.id} className="border border-border/60 rounded-lg overflow-hidden">
                    <button
                      onClick={() => toggle(s.id)}
                      className="w-full flex items-start gap-3 p-3 text-left hover:bg-hover/40 transition-all group"
                    >
                      <span className="mt-0.5 bg-primary/10 border border-primary/25 text-primary text-caption font-medium rounded-md px-2 py-0.5 shrink-0">
                        v{s.version}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="text-small font-medium text-foreground">{s.name || `Config v${s.version}`}</span>
                          {s.is_current && (
                            <span className="inline-flex items-center gap-1 rounded-md border border-success/25 bg-success/10 px-2 py-0.5 text-caption text-success">
                              <CheckCheck size={11} /> current
                            </span>
                          )}
                          <span className="text-caption text-muted-foreground/50 font-mono">{s.id}</span>
                        </div>
                        <p className="text-caption text-muted-foreground/70 mt-0.5">
                          {Object.keys(s.parameters ?? {}).length} parameters{ s.description ? ` · ${s.description}` : ''}{ s.created_at ? ` · ${new Date(s.created_at).toLocaleString()}` : ''}
                        </p>
                      </div>
                      <ChevronDown size={16} className={cn('text-muted-foreground/40 mt-1 shrink-0 transition-transform duration-200', open && 'rotate-180')} />
                    </button>
                    {open && (
                      <div className="px-4 pb-4 pt-1 border-t border-border/50 bg-background/20 space-y-3 text-small">
                        <div className="flex flex-wrap gap-2">
                          {!s.is_current && (
                            <button
                              onClick={() => handleRollback(s.id)}
                              disabled={busy}
                              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-elevated border border-border text-foreground text-caption font-medium hover:bg-hover transition-all disabled:opacity-50"
                            >
                              <RotateCcw size={13} /> Rollback to here
                            </button>
                          )}
                          <button
                            onClick={() => loadDiff(s.id)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-elevated border border-border text-foreground text-caption font-medium hover:bg-hover transition-all"
                          >
                            <GitBranch size={13} /> {diff?.id === s.id ? 'Hide diff' : 'Diff vs current'}
                          </button>
                          {s.parent_id && (
                            <span className="flex items-center gap-1 text-caption text-muted-foreground/60">
                              <GitBranch size={12} /> parent {s.parent_id}
                            </span>
                          )}
                          {s.created_from_decision_id && (
                            <span className="text-caption text-muted-foreground/60 font-mono">decision {s.created_from_decision_id}</span>
                          )}
                        </div>

                        {diff?.id === s.id && (
                          <div className="border border-border/40 rounded-lg p-3 bg-background/30">
                            {diff.diff ? (
                              <div className="space-y-2">
                                {Object.keys(diff.diff.added ?? {}).length > 0 && (
                                  <div>
                                    <p className="text-caption text-success uppercase tracking-wider mb-1">Added</p>
                                    <div className="flex flex-wrap gap-1.5">
                                      {Object.entries(diff.diff.added).map(([k, v]) => (
                                        <span key={k} className="text-caption text-success bg-success/5 border border-success/20 rounded-md px-2 py-0.5 font-mono">{k}: {String(v)}</span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {Object.keys(diff.diff.changed ?? {}).length > 0 && (
                                  <div>
                                    <p className="text-caption text-warning uppercase tracking-wider mb-1">Changed</p>
                                    <div className="space-y-1">
                                      {Object.entries(diff.diff.changed).map(([k, c]) => (
                                        <p key={k} className="text-caption text-foreground/80 font-mono">
                                          <span className="text-muted-foreground">{k}:</span> {c.from} → <span className="text-warning">{c.to}</span>
                                        </p>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {Object.keys(diff.diff.removed ?? {}).length > 0 && (
                                  <div>
                                    <p className="text-caption text-danger uppercase tracking-wider mb-1">Removed</p>
                                    <div className="flex flex-wrap gap-1.5">
                                      {Object.entries(diff.diff.removed).map(([k, v]) => (
                                        <span key={k} className="text-caption text-danger bg-mono/20 border border-danger/20 rounded-md px-2 py-0.5 font-mono">{k}: {String(v)}</span>
                                      ))}
                                    </div>
                                  </div>
                                )}
                                {Object.keys(diff.diff.added ?? {}).length + Object.keys(diff.diff.changed ?? {}).length + Object.keys(diff.diff.removed ?? {}).length === 0 && (
                                  <p className="text-caption text-muted-foreground/70">No differences ({diff.diff.unchanged_count} unchanged parameters).</p>
                                )}
                              </div>
                            ) : (
                              <p className="text-caption text-muted-foreground/60">Diff unavailable — no current configuration set.</p>
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

const inputCls = 'w-full rounded-lg border border-border bg-background/50 px-3 py-2 text-small text-foreground placeholder:text-muted-foreground/40 outline-none transition-colors focus:border-primary/40'

export default OwnConfigPage