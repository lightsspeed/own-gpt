import { useEffect, useMemo, useState } from 'react'
import { cn } from '@/lib/utils'
import {
  ShieldCheck, RefreshCw, ChevronDown, CheckCircle2, XCircle,
  AlertTriangle, FileText, Clock, Loader2,
} from 'lucide-react'
import { qualityApi, type QualityReport } from '@/features/quality/services/qualityApi'

const REFRESH_MS = 30000

function formatTime(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso.replace(' ', 'T'))
  return d.toLocaleString()
}

function VerdictBadge({ valid }: { valid: boolean }) {
  return valid
    ? <span className="inline-flex items-center gap-1.5 rounded-lg border border-success/20 bg-success/10 px-2.5 py-1 text-small font-medium text-success"><CheckCircle2 size={13} /> Valid</span>
    : <span className="inline-flex items-center gap-1.5 rounded-lg border border-danger/20 bg-danger/10 px-2.5 py-1 text-small font-medium text-danger"><AlertTriangle size={13} /> Invalid</span>
}

function ReportCard({ report, expanded, onToggle }: {
  report: QualityReport
  expanded: boolean
  onToggle: () => void
}) {
  const groundedPct = report.claims_total > 0
    ? Math.round((report.claims_supported / report.claims_total) * 100)
    : null
  const citationOk = report.citation_valid
  const shownClaims = expanded ? report.claims : report.claims.slice(0, 4)

  return (
    <div className="rounded-xl border border-border/60 bg-elevated overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full text-left px-4 py-3.5 flex items-start gap-3 hover:bg-hover/60 transition-colors"
      >
        <div className={cn(
          'mt-0.5 shrink-0 rounded-lg border p-1.5',
          citationOk ? 'border-success/20 bg-success/10 text-success' : 'border-warning/20 bg-warning/10 text-warning',
        )}>
          <ShieldCheck size={14} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-small font-medium text-foreground leading-snug line-clamp-2">{report.question}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-caption text-muted-foreground/70">
            <span className="inline-flex items-center gap-1"><Clock size={11} /> {formatTime(report.created_at)}</span>
            <span className="rounded-md bg-muted/30 px-1.5 py-0.5 uppercase tracking-wide">{report.answer_mode}</span>
            <span>{report.session_id}</span>
            {report.claims_unsupported > 0 && (
              <span className="text-danger">{report.claims_unsupported} unsupported</span>
            )}
          </div>
        </div>
        <div className="shrink-0 flex items-center gap-2.5">
          <div className="text-right">
            {groundedPct !== null && (
              <>
                <p className={cn('text-small font-semibold', groundedPct === 100 ? 'text-success' : 'text-warning')}>{groundedPct}%</p>
                <p className="text-caption text-muted-foreground/50">{report.claims_supported}/{report.claims_total} grounded</p>
              </>
            )}
          </div>
          <VerdictBadge valid={citationOk} />
          <ChevronDown size={14} className={cn('text-muted-foreground/50 transition-transform', expanded && 'rotate-180')} />
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 pt-1 space-y-2 border-t border-border/40">
          <div className="pt-3 flex flex-wrap gap-x-6 gap-y-1.5 text-caption text-muted-foreground/70">
            <span>Cited <b className="text-foreground/80">{report.cited}/{report.required}</b></span>
            <span>Unique chunks <b className="text-foreground/80">{report.unique_chunks}</b></span>
            <span>Total uses <b className="text-foreground/80">{report.total_uses}</b></span>
            {report.warnings.length > 0 && (
              <span className="text-warning">{report.warnings.length} warning{report.warnings.length > 1 ? 's' : ''}: {report.warnings.join('; ')}</span>
            )}
            {report.reason && <span>{report.reason}</span>}
          </div>

          {report.claims.length > 0 && (
            <div className="space-y-1.5">
              {shownClaims.map(c => (
                <div key={c.id} className="flex items-start gap-2.5 rounded-lg border border-border/40 bg-background/40 px-3 py-2">
                  {c.supported
                    ? <CheckCircle2 size={14} className="text-success mt-0.5 shrink-0" />
                    : <XCircle size={14} className="text-danger mt-0.5 shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <p className={cn('text-caption leading-snug', c.supported ? 'text-foreground/80' : 'text-foreground')}>{c.text}</p>
                    <div className="mt-1 flex items-center gap-2">
                      <div className="h-1 flex-1 rounded-full bg-muted/40 overflow-hidden">
                        <div
                          className={cn('h-full rounded-full', c.supported ? 'bg-success/60' : 'bg-danger/60')}
                          style={{ width: `${Math.min(100, ((c.best_score ?? 0) / c.threshold) * 100)}%` }}
                        />
                      </div>
                      <span className={cn('text-caption font-medium shrink-0', c.supported ? 'text-success/80' : 'text-danger')}>
                        {(c.best_score ?? 0).toFixed(2)}/{c.threshold.toFixed(2)}
                      </span>
                    </div>
                    {c.document && (
                      <p className="mt-1 inline-flex items-center gap-1 text-caption text-muted-foreground/50">
                        <FileText size={10} /> {c.document}
                      </p>
                    )}
                  </div>
                </div>
              ))}
              {!expanded && report.claims.length > 4 && (
                <p className="text-caption text-muted-foreground/50 px-1">+{report.claims.length - 4} more claims…</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function OwnLearnQualityPage() {
  const [reports, setReports] = useState<QualityReport[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const load = async () => {
    setError(null)
    try {
      const data = await qualityApi.listReports(100)
      setReports(data)
    } catch (e: any) {
      setError(e?.message || 'Failed to load reports')
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

  const stats = useMemo(() => {
    const total = reports.length
    const withClaims = reports.filter(r => r.claims_total > 0)
    const grounded = withClaims.reduce((acc, r) => acc + r.claims_supported, 0)
    const unsupported = withClaims.reduce((acc, r) => acc + r.claims_unsupported, 0)
    const citationPass = reports.filter(r => r.citation_valid).length
    return {
      total,
      groundedPct: withClaims.length ? Math.round((grounded / (grounded + unsupported)) * 100) : null,
      unsupported,
      citationPass,
    }
  }, [reports])

  return (
    <div className="h-full overflow-y-auto custom-scrollbar flex flex-col gap-4 p-4 md:p-6 max-w-4xl mx-auto w-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-title font-semibold text-foreground">Answer Quality</h1>
          <p className="text-caption text-muted-foreground/60 mt-0.5">
            Citation and grounding validation per answer. Admin-only view.
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
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Reports" value={stats.total} />
        <StatCard label="Grounded" value={stats.groundedPct !== null ? `${stats.groundedPct}%` : '—'} tone="success" />
        <StatCard label="Unsupported claims" value={stats.unsupported} tone={stats.unsupported > 0 ? 'danger' : 'default'} />
        <StatCard label="Citation valid" value={`${stats.citationPass}/${stats.total}`} tone="default" />
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground/60">
          <Loader2 size={16} className="animate-spin" /> Loading reports…
        </div>
      ) : error ? (
        <div className="rounded-xl border border-danger/30 bg-danger/10 p-6 text-center">
          <AlertTriangle size={24} className="mx-auto text-danger mb-3" />
          <p className="text-small text-danger font-medium">Failed to load quality reports</p>
          <p className="text-caption text-muted-foreground/70 mt-1">{error}</p>
          <button
            onClick={load}
            className="mt-4 rounded-lg border border-border/60 px-3 py-2 text-small text-foreground hover:bg-hover transition-colors inline-flex items-center gap-1.5"
          >
            <RefreshCw size={13} /> Retry
          </button>
        </div>
      ) : reports.length === 0 ? (
        <div className="rounded-xl border border-border/60 bg-elevated/50 p-10 text-center">
          <ShieldCheck size={28} className="mx-auto text-muted-foreground/40 mb-3" />
          <p className="text-small text-muted-foreground/70">No quality reports yet.</p>
          <p className="text-caption text-muted-foreground/50 mt-1">Ask the assistant a question with the knowledge base enabled — citation and grounding checks are recorded automatically.</p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {reports.map(r => (
            <ReportCard
              key={r.record_id}
              report={r}
              expanded={expandedId === r.record_id}
              onToggle={() => setExpandedId(prev => prev === r.record_id ? null : r.record_id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, tone = 'default' }: { label: string; value: string | number; tone?: 'default' | 'success' | 'danger' }) {
  return (
    <div className="rounded-xl border border-border/60 bg-elevated p-4">
      <p className="text-caption text-muted-foreground/60">{label}</p>
      <p className={cn(
        'mt-1 text-title font-semibold',
        tone === 'success' ? 'text-success' : tone === 'danger' ? 'text-danger' : 'text-foreground',
      )}>
        {value}
      </p>
    </div>
  )
}

export default OwnLearnQualityPage
