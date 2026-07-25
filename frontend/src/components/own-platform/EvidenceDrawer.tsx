import { useState } from 'react'
import { X, FileText, Globe, Brain, ExternalLink, ChevronDown, ChevronUp, BarChart3 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { EvidenceItem, ConfidenceLabel, RetrievalMethod } from '@/features/chat/types'
import { useHotkeys } from '@/hooks/useHotkeys'

interface EvidenceDrawerProps {
  item: EvidenceItem | null
  onClose: () => void
  onNavigate?: (direction: 'prev' | 'next') => void
  hasPrev?: boolean
  hasNext?: boolean
}

const CONFIDENCE_COLORS: Record<ConfidenceLabel, string> = {
  high: 'text-success',
  medium: 'text-primary',
  low: 'text-warning',
  no_evidence: 'text-muted-foreground/50',
}

const CONFIDENCE_LABELS: Record<ConfidenceLabel, string> = {
  high: 'High Confidence',
  medium: 'Strong Match',
  low: 'Low Confidence',
  no_evidence: 'No Evidence',
}

const RETRIEVAL_LABELS: Record<RetrievalMethod, string> = {
  hybrid: 'Hybrid',
  vector: 'Vector Search',
  bm25: 'BM25 Keyword',
  web: 'Web Search',
  memory: 'Memory Recall',
  none: 'None',
}

const SOURCE_ICONS: Record<string, React.ReactNode> = {
  knowledge: <FileText size={16} />,
  web: <Globe size={16} />,
  memory: <Brain size={16} />,
  file: <FileText size={16} />,
}

function HighlightSnippet({ text, query }: { text: string; query?: string }) {
  if (!query || !text) return <>{text}</>
  const normalizedText = text.toLowerCase()
  const normalizedQuery = query.toLowerCase()
  const idx = normalizedText.indexOf(normalizedQuery)
  if (idx === -1) return <>{text}</>
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-primary/20 text-foreground rounded-sm px-0.5">{text.slice(idx, idx + query.length)}</mark>
      {text.slice(idx + query.length)}
    </>
  )
}

export function EvidenceDrawer({ item, onClose, onNavigate, hasPrev, hasNext }: EvidenceDrawerProps) {
  const [showDeveloper, setShowDeveloper] = useState(false)
  const [highlightQuery, setHighlightQuery] = useState('')

  useHotkeys([
    { key: 'Escape', handler: onClose, deps: [onClose] },
    { key: 'ArrowLeft', handler: () => hasPrev && onNavigate?.('prev'), deps: [hasPrev, onNavigate] },
    { key: 'ArrowRight', handler: () => hasNext && onNavigate?.('next'), deps: [hasNext, onNavigate] },
  ])

  if (!item) return null

  const hasDeveloperFields = item.raw_score != null || item.reranker_score != null

  return (
    <div className="fixed inset-0 z-[90] flex" onClick={onClose}>
      <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" />

      <div
        className="relative ml-auto w-full max-w-[420px] h-full bg-elevated/98 backdrop-blur-xl border-l border-border/30 shadow-2xl overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 bg-elevated/95 backdrop-blur-md border-b border-border/10">
          <div className="flex items-center justify-between px-5 py-4">
            <div className="flex items-center gap-3">
              <span className="text-muted-foreground/50">{SOURCE_ICONS[item.source_type] || <FileText size={16} />}</span>
              <h3 className="text-small font-semibold text-foreground">Evidence</h3>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-hover text-muted-foreground hover:text-foreground transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* Navigation */}
          {(hasPrev || hasNext) && (
            <div className="flex items-center gap-1 px-5 pb-3">
              <button
                disabled={!hasPrev}
                onClick={() => onNavigate?.('prev')}
                className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-white/[0.04] text-muted-foreground/60 hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              >
                ← Prev
              </button>
              <button
                disabled={!hasNext}
                onClick={() => onNavigate?.('next')}
                className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-white/[0.04] text-muted-foreground/60 hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              >
                Next →
              </button>
            </div>
          )}
        </div>

        {/* Content */}
        <div className="px-5 py-4 space-y-5">
          {/* Title */}
          <div>
            <span className="text-caption text-muted-foreground/40 uppercase tracking-[.08em]">Document</span>
            <p className="text-body font-medium text-foreground mt-0.5">{item.title}</p>
          </div>

          {/* Divider */}
          <div className="border-t border-border/10" />

          {/* Chunk */}
          {item.chunk && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-caption text-muted-foreground/40 uppercase tracking-[.08em]">Chunk</span>
                {item.chunk_index != null && item.total_chunks != null && (
                  <span className="text-caption text-muted-foreground/30">
                    Chunk {item.chunk_index + 1} / {item.total_chunks}
                  </span>
                )}
              </div>
              <div className="relative">
                <div
                  className="text-small text-foreground/80 leading-relaxed bg-background/50 rounded-lg p-3 border border-border/20 max-h-[200px] overflow-y-auto custom-scrollbar"
                >
                  <HighlightSnippet text={item.chunk} query={highlightQuery || undefined} />
                </div>
              </div>
            </div>
          )}

          {/* Divider */}
          <div className="border-t border-border/10" />

          {/* Confidence */}
          <div>
            <span className="text-caption text-muted-foreground/40 uppercase tracking-[.08em]">Confidence</span>
            <p className={cn('text-body font-semibold mt-0.5', CONFIDENCE_COLORS[item.confidence_label])}>
              {CONFIDENCE_LABELS[item.confidence_label]}
            </p>
          </div>

          {/* Retrieval method */}
          <div>
            <span className="text-caption text-muted-foreground/40 uppercase tracking-[.08em]">Retrieved By</span>
            <div className="flex items-center gap-2 mt-1">
              <span className={cn(
                'text-[11px] font-semibold px-2 py-0.5 rounded border',
                item.retrieval_method === 'hybrid' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                item.retrieval_method === 'vector' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' :
                item.retrieval_method === 'bm25' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                item.retrieval_method === 'web' ? 'bg-sky-500/10 text-sky-400 border-sky-500/20' :
                'bg-muted/10 text-muted-foreground/50 border-border/30',
              )}>
                {RETRIEVAL_LABELS[item.retrieval_method]}
              </span>
            </div>
          </div>

          {/* URL */}
          {item.url && (
            <div>
              <span className="text-caption text-muted-foreground/40 uppercase tracking-[.08em]">Source URL</span>
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-small text-primary hover:text-primary/80 mt-0.5 break-all"
              >
                {item.url}
                <ExternalLink size={12} />
              </a>
            </div>
          )}

          {/* Developer mode */}
          {hasDeveloperFields && (
            <div>
              <button
                onClick={() => setShowDeveloper(!showDeveloper)}
                className="flex items-center gap-2 text-caption text-muted-foreground/40 hover:text-muted-foreground/60 transition-colors"
              >
                <BarChart3 size={12} />
                {showDeveloper ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                Developer Details
              </button>

              {showDeveloper && (
                <div className="mt-2 space-y-2 bg-background/50 rounded-lg p-3 border border-border/20">
                  {item.raw_score != null && (
                    <div className="flex items-center justify-between py-1">
                      <span className="text-caption text-muted-foreground/50">Retrieval Score</span>
                      <span className="text-caption font-mono text-foreground/70">{item.raw_score.toFixed(4)}</span>
                    </div>
                  )}
                  {item.reranker_score != null && (
                    <div className="flex items-center justify-between py-1">
                      <span className="text-caption text-muted-foreground/50">Reranker Score</span>
                      <span className="text-caption font-mono text-foreground/70">{item.reranker_score.toFixed(4)}</span>
                    </div>
                  )}
                  {item.chunk_index != null && (
                    <div className="flex items-center justify-between py-1">
                      <span className="text-caption text-muted-foreground/50">Chunk ID</span>
                      <span className="text-caption font-mono text-foreground/70">{item.id}</span>
                    </div>
                  )}
                  {item.document_id && (
                    <div className="flex items-center justify-between py-1">
                      <span className="text-caption text-muted-foreground/50">Document ID</span>
                      <span className="text-caption font-mono text-foreground/70 truncate max-w-[200px]">{item.document_id}</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
