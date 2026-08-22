import React from 'react'
import { ChevronLeft, ChevronRight, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { CiteSource } from './CitationMarker'
import { safeSourceUrl, sourceDomain } from './CitationMarker'

interface CitationPopoverProps {
  sources: CiteSource[]
  activeIndex: number
  onNavigate: (delta: number) => void
  onClose: () => void
  variant: 'card' | 'sheet'
}

const CONFIDENCE_STYLES: Record<string, string> = {
  high: 'text-success',
  medium: 'text-warning',
  low: 'text-danger',
  no_evidence: 'text-muted-foreground',
}

function SourceBody({ sources, activeIndex, onNavigate }: Pick<CitationPopoverProps, 'sources' | 'activeIndex' | 'onNavigate'>) {
  const source = sources[activeIndex]
  const resource = source.resource
  const safeUrl = safeSourceUrl(resource.url)

  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <span className="text-micro font-semibold uppercase tracking-wide text-muted-foreground">Source</span>
        {resource.confidence_label && (
          <span className={`text-micro font-medium ${CONFIDENCE_STYLES[resource.confidence_label] ?? 'text-muted-foreground'}`}>
            {resource.confidence_label}
          </span>
        )}
      </div>

      <p className="mt-1.5 text-small font-semibold text-foreground leading-snug">{resource.title}</p>

      {(resource.section || resource.page !== undefined) && (
        <p className="mt-0.5 text-micro text-muted-foreground">
          {resource.section && <span>{resource.section}</span>}
          {resource.section && resource.page !== undefined && <span> · </span>}
          {resource.page !== undefined && <span>Page {resource.page}</span>}
        </p>
      )}

      {resource.snippet && (
        <p className="mt-2 text-micro text-foreground/75 leading-relaxed line-clamp-4">{resource.snippet}</p>
      )}

      {safeUrl && (
        <a
          href={safeUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="mt-2 inline-flex items-center gap-1 text-micro font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
        >
          <ExternalLink size={11} /> {sourceDomain(resource).replace(/\+\d+$/, '')}
        </a>
      )}

      {sources.length > 1 && (
        <div className="mt-2 flex items-center justify-between border-t border-border pt-1.5">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onNavigate(-1)
            }}
            aria-label="Previous source"
            className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-hover focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
          >
            <ChevronLeft size={14} />
          </button>
          <span className="text-micro text-muted-foreground">
            {activeIndex + 1} / {sources.length}
          </span>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onNavigate(1)
            }}
            aria-label="Next source"
            className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-hover focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      )}
    </>
  )
}

export function CitationPopover({ sources, activeIndex, onNavigate, onClose, variant }: CitationPopoverProps) {
  if (variant === 'sheet') {
    return (
      <div className="fixed inset-x-0 bottom-0 z-50" role="dialog" aria-label="Citation source">
        <div
          className="absolute inset-0 bg-black/40"
          onClick={(e) => {
            e.stopPropagation()
            onClose()
          }}
          aria-hidden
        />
        <div className="relative rounded-t-2xl border-t border-border bg-popover px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 shadow-2xl animate-in fade-in slide-in-from-bottom-4">
          <div className="mx-auto mb-2 h-1 w-10 rounded-full bg-foreground/15" />
          <div className="flex items-center justify-between pr-1">
            <button
              type="button"
              onClick={onClose}
              aria-label="Close source"
              className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-hover"
            >
              <span className="text-caption font-semibold">×</span>
            </button>
          </div>
          <SourceBody sources={sources} activeIndex={activeIndex} onNavigate={onNavigate} />
        </div>
      </div>
    )
  }

  return (
    <div
      role="dialog"
      aria-label="Citation source"
      className={cn(
        'absolute left-0 top-full z-40 mt-1.5 w-[19rem] rounded-2xl border border-border bg-popover p-3 shadow-2xl',
        'animate-in fade-in zoom-in-95',
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <span />
        <button
          type="button"
          onClick={onClose}
          aria-label="Close source"
          className="rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-hover"
        >
          <span className="text-caption font-semibold">×</span>
        </button>
      </div>
      <SourceBody sources={sources} activeIndex={activeIndex} onNavigate={onNavigate} />
    </div>
  )
}