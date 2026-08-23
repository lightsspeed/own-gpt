import React from 'react'
import { ExternalLink, BookOpen, X, ChevronLeft, ChevronRight } from 'lucide-react'
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

export function CitationPopover({ sources, activeIndex, onNavigate, onClose, variant }: CitationPopoverProps) {
  const source = sources[activeIndex]
  if (!source) return null
  const resource = source.resource
  const safeUrl = safeSourceUrl(resource.url)
  const domain = safeUrl ? sourceDomain(resource).replace(/\+\d+$/, '') : 'Knowledge Base'

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
          <div className="flex items-center justify-between gap-2 border-b border-border/40 pb-2 mb-2">
            <div className="flex items-center gap-1.5 min-w-0">
              {safeUrl ? (
                <img
                  src={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
                  className="w-3.5 h-3.5 rounded-xs shrink-0 object-contain"
                  alt=""
                />
              ) : (
                <BookOpen size={13} className="text-primary shrink-0" />
              )}
              <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase truncate">
                {domain}
              </span>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-hover"
            >
              <X size={14} />
            </button>
          </div>
          <p className="text-sm font-semibold text-foreground leading-snug line-clamp-2">{resource.title}</p>
          {resource.snippet && (
            <p className="mt-1 text-xs text-muted-foreground leading-relaxed line-clamp-3">{resource.snippet}</p>
          )}
          {safeUrl && (
            <a
              href={safeUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
            >
              <span>Visit website</span>
              <ExternalLink size={11} />
            </a>
          )}
        </div>
      </div>
    )
  }

  return (
    <div
      role="dialog"
      aria-label="Citation source"
      className={cn(
        'absolute left-1/2 -translate-x-1/2 bottom-full mb-2.5 z-50 w-64 p-3.5 rounded-2xl border border-border/80 bg-surface/95 dark:bg-elevated/95 backdrop-blur-xl shadow-2xl origin-bottom animate-scale-in',
      )}
    >
      <div className="flex items-center justify-between gap-2 border-b border-border/40 pb-2 mb-2">
        <div className="flex items-center gap-1.5 min-w-0">
          {safeUrl ? (
            <img
              src={`https://www.google.com/s2/favicons?domain=${domain}&sz=32`}
              className="w-3.5 h-3.5 rounded-xs shrink-0 object-contain"
              alt=""
            />
          ) : (
            <BookOpen size={12} className="text-primary shrink-0" />
          )}
          <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase truncate">
            {domain}
          </span>
        </div>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onClose()
          }}
          className="text-muted-foreground/60 hover:text-foreground p-0.5 rounded transition-colors"
        >
          <X size={12} />
        </button>
      </div>

      <p className="text-xs font-semibold text-foreground leading-snug line-clamp-2">
        {resource.title}
      </p>

      {resource.snippet && (
        <p className="mt-1 text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
          {resource.snippet}
        </p>
      )}

      {safeUrl && (
        <div className="mt-2.5 pt-2 border-t border-border/40 flex items-center justify-between">
          <a
            href={safeUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
          >
            <span>Visit website</span>
            <ExternalLink size={10} />
          </a>
          {sources.length > 1 && (
            <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
              <button onClick={() => onNavigate(-1)} className="p-0.5 hover:text-foreground">
                <ChevronLeft size={12} />
              </button>
              <span>{activeIndex + 1}/{sources.length}</span>
              <button onClick={() => onNavigate(1)} className="p-0.5 hover:text-foreground">
                <ChevronRight size={12} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}