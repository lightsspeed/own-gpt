import { useState } from 'react'
import { cn } from '@/lib/utils'
import {
  FlaskConical, Play, GitCompare, Scale, Loader2, Plus, Trash2,
  CheckCircle2, XCircle, Minus, AlertTriangle, FileText,
} from 'lucide-react'
import {
  experimentsApi, PARAMETER_DOMAINS,
  type ExperimentDefinition, type ParameterChange,
  type ExperimentResult, type ComparisonReport, type DecisionCandidate,
} from '@/features/experiments/services/experimentsApi'

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

const inputCls = 'w-full rounded-lg border border-border bg-background/50 px-3 py-2 text-small text-foreground placeholder:text-muted-foreground/40 outline-none transition-colors focus:border-primary/40'

function VerdictBadge({ verdict }: { verdict: string }) {
  const color = verdict === 'improvement' ? 'text-success bg-success/10 border-success/20'
    : verdict === 'regression' ? 'text-danger bg-danger/10 border-danger/20'
    : verdict === 'mixed' ? 'text-warning bg-warning/10 border-warning/20'
    : 'text-muted-foreground bg-muted/20 border-border/40'
  return (
    <span className={cn('inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-small font-medium capitalize', color)}>
      {verdict === 'improvement' ? <CheckCircle2 size={13} /> : verdict === 'regression' ? <XCircle size={13} /> : <Minus size={13} />}
      {verdict}
    </span>
  )
}

function DeltaCell({ delta }: { delta?: { baseline?: number; candidate?: number; absolute?: number; percent?: number } }) {
  if (!delta) return <span className="text-caption text-muted-foreground/50">—</span>
  const abs = delta.absolute
  const improved = (abs ?? 0) > 0
  const regressed = (abs ?? 0) < 0
  return (
    <span className={cn('text-caption font-medium', improved ? 'text-success' : regressed ? 'text-danger' : 'text-muted-foreground/60')}>
      {abs != null && abs > 0 ? '+' : ''}{abs?.toFixed(3) ?? '—'}
      {delta.percent != null && ` (${delta.percent > 0 ? '+' : ''}${delta.percent.toFixed(1)}%)`}
    </span>
  )
}

export function OwnExperimentsPage() {
  const [name, setName] = useState('')
  const [hypothesis, setHypothesis] = useState('')
  const [datasetSize, setDatasetSize] = useState(200)
  const [datasetDesc, setDatasetDesc] = useState('')
  const [changes, setChanges] = useState<ParameterChange[]>([{ domain: 'custom', parameter: '', baseline: '', candidate: '', description: '' }])
  const [running, setRunning] = useState<'run' | 'compare' | 'evaluate' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ExperimentResult | null>(null)
  const [comparison, setComparison] = useState<ComparisonReport | null>(null)
  const [candidate, setCandidate] = useState<DecisionCandidate | null>(null)

  const setChange = (i: number, patch: Partial<ParameterChange>) => {
    setChanges(prev => prev.map((c, idx) => idx === i ? { ...c, ...patch } : c))
  }

  const buildDefinition = (): ExperimentDefinition => ({
    name: name.trim() || 'Untitled experiment',
    hypothesis: hypothesis.trim(),
    parameter_changes: changes.filter(c => c.parameter.trim()),
    dataset_size: datasetSize,
    dataset_description: datasetDesc.trim(),
  })

  const valid = changes.some(c => c.parameter.trim())

  const runAction = async (action: 'run' | 'compare' | 'evaluate') => {
    setError(null)
    setRunning(action)
    try {
      const def = buildDefinition()
      if (action === 'run') {
        setResult(await experimentsApi.run(def, datasetSize))
      } else if (action === 'compare') {
        setComparison(await experimentsApi.compare(def, datasetSize))
      } else {
        const r = await experimentsApi.evaluate(def, datasetSize)
        setResult(r.result)
        setComparison(r.comparison)
        setCandidate(r.decision_candidate)
      }
    } catch (e: any) {
      setError(e.message || 'Experiment failed')
    } finally {
      setRunning(null)
    }
  }

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="max-w-[1100px] mx-auto p-6 space-y-5">
        <div>
          <h1 className="text-h2 text-foreground">Experiments</h1>
          <p className="text-caption text-muted-foreground mt-0.5">
            Design parameter experiments, replay them over the learning ledger, and produce decision candidates. Humans decide — experiments only measure.
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-xs text-destructive bg-danger/10 border border-danger/20 rounded-lg p-2.5">
            <AlertTriangle size={13} />
            <span>{error}</span>
          </div>
        )}

        {/* ── Define experiment ── */}
        <Section title="1 · Define Experiment" icon={FlaskConical}>
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input className={inputCls} placeholder="Experiment name" value={name} onChange={e => setName(e.target.value)} />
              <input className={inputCls} type="number" placeholder="Dataset size (learning records)" value={datasetSize} onChange={e => setDatasetSize(Number(e.target.value) || 0)} />
            </div>
            <textarea className={cn(inputCls, 'min-h-[70px] resize-y')} placeholder="Hypothesis — what do you expect to change and why?" value={hypothesis} onChange={e => setHypothesis(e.target.value)} />
            <input className={inputCls} placeholder="Dataset description (optional)" value={datasetDesc} onChange={e => setDatasetDesc(e.target.value)} />

            {/* Parameter changes */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-caption text-muted-foreground uppercase tracking-wider">Parameter Changes</span>
                <button
                  onClick={() => setChanges(prev => [...prev, { domain: 'custom', parameter: '', baseline: '', candidate: '', description: '' }])}
                  className="flex items-center gap-1 text-caption text-primary hover:brightness-110 transition-all"
                >
                  <Plus size={12} /> Add
                </button>
              </div>
              {changes.map((c, i) => (
                <div key={i} className="grid grid-cols-2 sm:grid-cols-6 gap-2 items-center">
                  <select
                    className={cn(inputCls, 'col-span-2 sm:col-span-1')}
                    value={c.domain}
                    onChange={e => setChange(i, { domain: e.target.value })}
                  >
                    {PARAMETER_DOMAINS.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                  <input className={cn(inputCls, 'col-span-2')} placeholder="parameter (e.g. top_k)" value={c.parameter} onChange={e => setChange(i, { parameter: e.target.value })} />
                  <input className={inputCls} placeholder="baseline" value={c.baseline as string} onChange={e => setChange(i, { baseline: e.target.value })} />
                  <input className={inputCls} placeholder="candidate" value={c.candidate as string} onChange={e => setChange(i, { candidate: e.target.value })} />
                  <button
                    onClick={() => setChanges(prev => prev.filter((_, idx) => idx !== i))}
                    disabled={changes.length === 1}
                    className="p-2 rounded-lg text-muted-foreground/40 hover:text-danger hover:bg-hover transition-all disabled:opacity-30 justify-self-end"
                    title="Remove"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>

            {/* Actions */}
            <div className="flex flex-wrap gap-2 pt-1">
              <button
                onClick={() => runAction('run')}
                disabled={!valid || running !== null}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-small font-medium hover:brightness-110 transition-all disabled:opacity-50"
              >
                {running === 'run' ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} Run
              </button>
              <button
                onClick={() => runAction('compare')}
                disabled={!valid || running !== null}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-elevated border border-border text-foreground text-small font-medium hover:bg-hover transition-all disabled:opacity-50"
              >
                {running === 'compare' ? <Loader2 size={14} className="animate-spin" /> : <GitCompare size={14} />} Compare
              </button>
              <button
                onClick={() => runAction('evaluate')}
                disabled={!valid || running !== null}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-elevated border border-border text-foreground text-small font-medium hover:bg-hover transition-all disabled:opacity-50"
              >
                {running === 'evaluate' ? <Loader2 size={14} className="animate-spin" /> : <Scale size={14} />} Evaluate → Candidate
              </button>
            </div>
          </div>
        </Section>

        {/* ── Result ── */}
        {result && (
          <Section title="2 · Results" icon={FileText}>
            <div className="space-y-4">
              <p className="text-small text-foreground/80">{result.summary || 'Experiment completed.'}</p>
              <div className="flex gap-5 text-caption text-muted-foreground/70">
                <span>Records: {result.records_processed}</span>
                <span>Duration: {result.duration_ms} ms</span>
                <span>Completed: {result.completed_at ? new Date(result.completed_at).toLocaleString() : '—'}</span>
              </div>
              <div className="overflow-x-auto custom-scrollbar">
                <table className="w-full text-small">
                  <thead>
                    <tr className="text-caption text-muted-foreground/60 uppercase tracking-wider">
                      <th className="text-left py-2 pr-3 font-medium">Metric</th>
                      <th className="text-right py-2 pr-3 font-medium">Baseline</th>
                      <th className="text-right py-2 pr-3 font-medium">Candidate</th>
                      <th className="text-right py-2 font-medium">Delta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(result.deltas).map(([metric, delta]) => (
                      <tr key={metric} className="border-t border-border/40">
                        <td className="py-2 pr-3 text-foreground">{metric}</td>
                        <td className="py-2 pr-3 text-right text-muted-foreground">{(delta?.baseline ?? 0).toFixed(3)}</td>
                        <td className="py-2 pr-3 text-right text-muted-foreground">{(delta?.candidate ?? 0).toFixed(3)}</td>
                        <td className="py-2 text-right"><DeltaCell delta={delta} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </Section>
        )}

        {/* ── Comparison ── */}
        {comparison && (
          <Section title="3 · Comparison" icon={GitCompare}>
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <VerdictBadge verdict={comparison.overall_verdict} />
                <div className="flex gap-2 text-caption">
                  {comparison.wins.length > 0 && <span className="text-success">{comparison.wins.length} wins</span>}
                  {comparison.losses.length > 0 && <span className="text-danger">{comparison.losses.length} losses</span>}
                  {comparison.unchanged.length > 0 && <span className="text-muted-foreground/60">{comparison.unchanged.length} unchanged</span>}
                </div>
              </div>
              {comparison.wins.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {comparison.wins.map(m => <span key={m} className="text-caption text-success bg-success/10 border border-success/20 rounded-md px-2 py-0.5">{m}</span>)}
                </div>
              )}
              {comparison.losses.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {comparison.losses.map(m => <span key={m} className="text-caption text-danger bg-danger/10 border border-danger/20 rounded-md px-2 py-0.5">{m}</span>)}
                </div>
              )}
            </div>
          </Section>
        )}

        {/* ── Decision candidate ── */}
        {candidate && (
          <Section title="4 · Decision Candidate" icon={Scale}>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className={cn(
                  'inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-small font-medium capitalize',
                  candidate.decision === 'adopt' ? 'text-success bg-success/10 border-success/20'
                    : candidate.decision === 'reject' ? 'text-danger bg-danger/10 border-danger/20'
                    : 'text-warning bg-warning/10 border-warning/20',
                )}>
                  {candidate.decision === 'adopt' ? <CheckCircle2 size={13} /> : candidate.decision === 'reject' ? <XCircle size={13} /> : <AlertTriangle size={13} />}
                  {candidate.decision}
                </span>
                <span className="text-caption text-muted-foreground/60">{candidate.status} · {candidate.id}</span>
              </div>
              <p className="text-small text-foreground/85">{candidate.rationale}</p>
              {candidate.risks.length > 0 && (
                <div className="space-y-1">
                  <p className="text-caption text-muted-foreground uppercase tracking-wider">Risks</p>
                  {candidate.risks.map((r, i) => (
                    <p key={i} className="text-caption text-muted-foreground/80 flex items-start gap-1.5">
                      <AlertTriangle size={11} className="text-warning mt-0.5 shrink-0" /> {r}
                    </p>
                  ))}
                </div>
              )}
              {Object.keys(candidate.supporting_metrics).length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(candidate.supporting_metrics).map(([k, v]) => (
                    <span key={k} className="text-caption bg-muted/20 border border-border/40 rounded-md px-2 py-0.5">
                      {k}: <span className="font-medium text-foreground">{typeof v === 'number' ? v.toFixed(3) : v}</span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </Section>
        )}
      </div>
    </div>
  )
}

export default OwnExperimentsPage
