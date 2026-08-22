import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import {
  Brain, ChevronRight, Globe, History, Loader, RefreshCw, Trash2, MessageSquare, AlertTriangle,
} from 'lucide-react'
import {
  operationsApi, type MemoryFactRow, type MemoriesWorkspace,
} from '@/features/operations/services/operationsApi'

function Section({ title, icon: Icon, children }: {
  title: string
  icon?: React.ElementType
  children: React.ReactNode
}) {
  return (
    <div className="bg-elevated border border-border/60 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon size={16} className="text-muted-foreground" />}
        <h2 className="text-small font-semibold text-foreground uppercase tracking-wider">{title}</h2>
      </div>
      {children}
    </div>
  )
}

function ScopeBadge({ scope }: { scope: string }) {
  const isSession = scope.startsWith('session:')
  const Icon = isSession ? MessageSquare : Globe
  return (
    <span className={cn(
      'inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-caption font-medium',
      isSession ? 'text-info bg-info/10 border-info/20' : 'text-success bg-success/10 border-success/20',
    )}>
      <Icon size={11} />
      {isSession ? 'conversation' : 'global'}
    </span>
  )
}

export function OwnMemoriesPage() {
  const [data, setData] = useState<MemoriesWorkspace | null>(null)
  const [scope, setScope] = useState('')
  const [showSuperseded, setShowSuperseded] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [forgetting, setForgetting] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchAll = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await operationsApi.getMemories({
        scope: scope || undefined,
        includeSuperseded: showSuperseded,
        limit: 200,
      })
      setData(res)
    } catch (e: any) {
      setError(e.message || 'Failed to load memories')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, showSuperseded])

  const toggle = (id: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const forget = async (fact: MemoryFactRow) => {
    if (!window.confirm(`Forget memory: "${fact.fact}"? This marks the fact as superseded (history is preserved).`)) return
    setForgetting(fact.id)
    setError(null)
    try {
      await operationsApi.forgetMemory(fact.id)
      await fetchAll()
    } catch (e: any) {
      setError(e.message || 'Failed to forget memory')
    } finally {
      setForgetting(null)
    }
  }

  const facts = data?.facts ?? []
  const activeCount = data?.active_count ?? 0
  const superseded = facts.filter(f => f.status === 'superseded').length

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-[1100px] mx-auto p-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-h2 text-foreground">Agent Memory</h1>
            <p className="text-caption text-muted-foreground mt-0.5">
              Facts the agent has learned about the user and conversations — immutable artifacts with lineage.
              Forgetting marks a fact as superseded; history is never rewritten.
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

        {!data && !loading && !error && (
          <div className="text-center py-10 bg-elevated border border-border/60 rounded-xl">
            <p className="text-small text-muted-foreground">Memory API unavailable. Is the backend running?</p>
          </div>
        )}

        {/* ── Summary cards ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-elevated border border-border/60 rounded-xl p-4">
            <p className="text-caption text-muted-foreground uppercase tracking-wider">Active facts</p>
            <p className="text-h3 text-foreground font-semibold mt-1">{loading ? '—' : activeCount}</p>
          </div>
          <div className="bg-elevated border border-success/20 rounded-xl p-4">
            <p className="text-caption text-success/70 uppercase tracking-wider">Global</p>
            <p className="text-h3 text-success font-semibold mt-1">{loading ? '—' : facts.filter(f => f.scope === 'global').length}</p>
          </div>
          <div className="bg-elevated border border-info/20 rounded-xl p-4">
            <p className="text-caption text-info/70 uppercase tracking-wider">Conversation</p>
            <p className="text-h3 text-info font-semibold mt-1">{loading ? '—' : facts.filter(f => f.scope.startsWith('session:')).length}</p>
          </div>
          <div className="bg-elevated border border-border/60 rounded-xl p-4">
            <p className="text-caption text-muted-foreground uppercase tracking-wider">Superseded</p>
            <p className="text-h3 text-muted-foreground font-semibold mt-1">{loading ? '—' : superseded}</p>
          </div>
        </div>

        {/* ── Filters ── */}
        <Section title="Filters" icon={Brain}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-caption text-muted-foreground/70">Scope</span>
            {[{ v: '', l: 'All' }, { v: 'global', l: 'Global' }, { v: 'session', l: 'Conversation' }].map(s => (
              <button
                key={s.v}
                onClick={() => setScope(s.v)}
                className={cn(
                  'px-3 py-1 rounded-lg border text-small transition-all',
                  scope === s.v ? 'bg-primary/10 border-primary/30 text-foreground' : 'border-border/50 text-muted-foreground/70 hover:bg-hover hover:text-foreground',
                )}
              >
                {s.l}
              </button>
            ))}
            <span className="text-caption text-muted-foreground/70 ml-3">Status</span>
            <button
              onClick={() => setShowSuperseded(v => !v)}
              className={cn(
                'px-3 py-1 rounded-lg border text-small transition-all',
                showSuperseded ? 'bg-primary/10 border-primary/30 text-foreground' : 'border-border/50 text-muted-foreground/70 hover:bg-hover hover:text-foreground',
              )}
            >
              Include superseded
            </button>
          </div>
        </Section>

        {/* ── Memory list ── */}
        <Section title={`Memories (${facts.length})`} icon={History}>
          {loading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground">
              <Loader size={18} className="animate-spin" /> Loading memories…
            </div>
          ) : facts.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              <Brain size={24} className="mx-auto mb-2 text-muted-foreground/40" />
              <p className="text-small">No memories match the current filters.</p>
              <p className="text-caption text-muted-foreground/60 mt-1">
                Ask the agent to remember something (e.g. &quot;remember my name is Alice&quot;) in a conversation, then approve the tool call in Tool Executions.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {facts.map((f: MemoryFactRow) => {
                const open = expanded.has(f.id)
                const isSuperseded = f.status === 'superseded'
                return (
                  <div key={f.id} className={cn('border rounded-lg overflow-hidden', isSuperseded ? 'border-border/30 opacity-60' : 'border-border/60')}>
                    <button
                      onClick={() => toggle(f.id)}
                      className="w-full flex items-start gap-3 p-3.5 text-left hover:bg-hover/40 transition-all"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={cn('text-small font-medium', isSuperseded ? 'text-muted-foreground line-through' : 'text-foreground')}>{f.fact}</span>
                          <ScopeBadge scope={f.scope} />
                          {isSuperseded && (
                            <span className="text-caption rounded-md border border-border/40 px-2 py-0.5 text-muted-foreground">superseded</span>
                          )}
                        </div>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1.5 text-caption text-muted-foreground/60">
                          <span className="font-mono">{f.id}</span>
                          <span>source: {f.source}</span>
                          <span>{new Date(f.created_at).toLocaleString()}</span>
                        </div>
                      </div>
                      <ChevronRight size={16} className={cn('text-muted-foreground/40 mt-1 shrink-0 transition-transform duration-200', open && 'rotate-90')} />
                    </button>
                    {open && (
                      <div className="px-4 pb-4 pt-1 border-t border-border/50 bg-background/20 space-y-3 text-small">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                          <div>
                            <p className="text-caption text-muted-foreground uppercase tracking-wider mb-1">Record</p>
                            <p className="text-caption text-muted-foreground/80 font-mono">
                              {f.id} · v{f.version} · {f.scope}
                            </p>
                          </div>
                          <div>
                            <p className="text-caption text-muted-foreground uppercase tracking-wider mb-1">Lineage</p>
                            <p className="text-caption text-muted-foreground/80 font-mono">
                              {f.supersedes.length > 0 ? `supersedes: ${f.supersedes.join(', ')}` : 'root fact'}
                            </p>
                          </div>
                        </div>
                        <div>
                          <p className="text-caption text-muted-foreground uppercase tracking-wider mb-1">Lifecycle events</p>
                          <ul className="space-y-1">
                            {f.events.map((e, i) => (
                              <li key={i} className="text-caption text-muted-foreground/80">
                                <span className="font-medium text-foreground/80">{e.status}</span>
                                <span className="text-muted-foreground/50"> · {new Date(e.at).toLocaleString()}</span>
                                {e.note && <span className="text-muted-foreground/60"> · {e.note}</span>}
                              </li>
                            ))}
                          </ul>
                        </div>
                        {!isSuperseded && (
                          <div className="flex justify-end">
                            <button
                              onClick={() => forget(f)}
                              disabled={forgetting === f.id}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-danger/30 text-danger/90 text-small hover:bg-danger/10 transition-all disabled:opacity-50"
                            >
                              <Trash2 size={13} />
                              {forgetting === f.id ? 'Forgetting…' : 'Forget'}
                            </button>
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

export default OwnMemoriesPage