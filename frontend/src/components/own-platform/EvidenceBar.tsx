import { useState } from 'react'
import { ChevronDown, ChevronRight, FileText, Globe, Brain, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { EvidenceItem, ConfidenceLabel, RetrievalMethod } from '@/features/chat/types'

interface EvidenceBarProps {
  items: EvidenceItem[]
  onSelect: (item: EvidenceItem) => void
}

const SOURCE_ICONS: Record<string, React.ReactNode> = {
  knowledge: <FileText size={13} />,
  web: <Globe size={13} />,
  memory: <Brain size={13} />,
  file: <FileText size={13} />,
}

const CONFIDENCE_COLORS: Record<ConfidenceLabel, string> = {
  high: 'text-success',
  medium: 'text-primary',
  low: 'text-warning',
  no_evidence: 'text-muted-foreground/50',
}

const RETRIEVAL_STYLES: Record<RetrievalMethod, string> = {
  hybrid: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  vector: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  bm25: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  web: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  memory: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  none: 'bg-muted/10 text-muted-foreground/50 border-border/30',
}

const CONFIDENCE_LABELS: Record<ConfidenceLabel, string> = {
  high: 'High Confidence',
  medium: 'Strong Match',
  low: 'Low Confidence',
  no_evidence: 'No Evidence',
}

export function EvidenceBar({ items, onSelect }: EvidenceBarProps) {
  const [expanded, setExpanded] = useState(false)

  if (!items || items.length === 0) return null

  return (
    <div className="mt-3 border-t border-border/10 pt-2">
      {/* Collapsed header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-[12px] font-medium text-muted-foreground/60 hover:text-foreground/80 transition-colors"
      >
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        Sources ({items.length})
      </button>

      {/* Expanded list */}
      {expanded && (
        <div className="mt-2 space-y-1.5">
          {items.map((item, i) => (
            <button
              key={item.id || i}
              onClick={() => onSelect(item)}
              className="w-full flex items-center gap-2.5 p-2 rounded-lg bg-white/[0.03] hover:bg-white/[0.06] border border-transparent hover:border-border/20 transition-all text-left group"
            >
              <span className="shrink-0 text-muted-foreground/40">
                {SOURCE_ICONS[item.source_type] || <FileText size={13} />}
              </span>

              <div className="flex-1 min-w-0">
                <span className="text-[12px] font-medium text-foreground/80 truncate block">
                  {item.title}
                </span>
                <span className={cn('text-[11px] font-medium', CONFIDENCE_COLORS[item.confidence_label])}>
                  {CONFIDENCE_LABELS[item.confidence_label]}
                </span>
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                <span className={cn(
                  'text-[9px] font-semibold px-1.5 py-0.5 rounded border uppercase tracking-wide',
                  RETRIEVAL_STYLES[item.retrieval_method],
                )}>
                  {item.retrieval_method}
                </span>
                <ExternalLink size={12} className="text-muted-foreground/20 group-hover:text-muted-foreground/50 transition-colors" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
