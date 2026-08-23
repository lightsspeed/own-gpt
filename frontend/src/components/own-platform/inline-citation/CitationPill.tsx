import React, { useState } from 'react'
import { cn } from '@/lib/utils'
import { Globe, BookOpen, ExternalLink } from 'lucide-react'
import type { ResourceItem } from '@/features/chat/types'

interface CitationPillProps {
  label: string
  resource?: ResourceItem
  className?: string
}

export const CitationPill = React.memo(function CitationPill({
  label,
  resource,
  className,
}: CitationPillProps) {
  const [imgFailed, setImgFailed] = useState(false)
  const parts = label.split(/(\s\+\d+$)/)
  const text = parts[0] ?? label
  const extra = parts[1]

  const url = resource?.url
  let domain = ''
  if (url) {
    try {
      domain = new URL(url).hostname.replace(/^www\./, '')
    } catch { /* ignore */ }
  }

  const faviconUrl = domain ? `https://www.google.com/s2/favicons?domain=${domain}&sz=32` : null
  const safeUrl = url && (url.startsWith('http://') || url.startsWith('https://')) ? url : undefined

  return (
    <span className="group/pill relative inline-block align-baseline mx-0.5 my-0">
      {/* Interactive Link Pill */}
      <a
        href={safeUrl || '#'}
        target={safeUrl ? '_blank' : undefined}
        rel="noopener noreferrer"
        onClick={(e) => {
          if (!safeUrl) e.preventDefault()
        }}
        aria-label={`Citation: ${label}`}
        className={cn(
          'inline-flex items-center gap-1.5 align-baseline',
          'rounded-full border px-2 py-0.5',
          'text-micro font-medium leading-none whitespace-nowrap',
          'transition-all select-none cursor-pointer shadow-xs',
          'bg-surface/80 dark:bg-elevated/80 text-foreground/80 border-border/70 group-hover/pill:bg-primary/15 group-hover/pill:text-primary group-hover/pill:border-primary/40',
          className,
        )}
      >
        {faviconUrl && !imgFailed ? (
          <img
            src={faviconUrl}
            onError={() => setImgFailed(true)}
            className="w-3 h-3 rounded-xs shrink-0 object-contain"
            alt=""
          />
        ) : safeUrl ? (
          <Globe size={11} className="shrink-0 opacity-70 text-primary" />
        ) : (
          <BookOpen size={11} className="shrink-0 opacity-70 text-primary" />
        )}
        <span>{text}</span>
        {extra && (
          <span className="text-[0.82em] font-semibold text-primary ml-0.5">
            {extra}
          </span>
        )}
      </a>

      {/* Pure CSS Hover Popover Card — Appears ONLY on hovering THIS pill */}
      {resource && (
        <div
          className={cn(
            'pointer-events-none opacity-0 invisible group-hover/pill:opacity-100 group-hover/pill:visible group-hover/pill:pointer-events-auto',
            'transition-all duration-160 ease-out transform group-hover/pill:translate-y-0 translate-y-1',
            'absolute left-1/2 -translate-x-1/2 bottom-full mb-2 z-50 w-64 p-3 rounded-xl border border-border/80 bg-surface/95 dark:bg-elevated/95 backdrop-blur-xl shadow-2xl origin-bottom',
          )}
        >
          <div className="flex items-center justify-between gap-2 border-b border-border/40 pb-1.5 mb-1.5">
            <div className="flex items-center gap-1.5 min-w-0">
              {faviconUrl && !imgFailed ? (
                <img src={faviconUrl} className="w-3.5 h-3.5 rounded-xs shrink-0 object-contain" alt="" />
              ) : (
                <BookOpen size={12} className="text-primary shrink-0" />
              )}
              <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase truncate">
                {domain || 'Knowledge Base'}
              </span>
            </div>
            {safeUrl && <ExternalLink size={10} className="text-muted-foreground/60 shrink-0" />}
          </div>

          <p className="text-xs font-semibold text-foreground leading-snug line-clamp-2">
            {resource.title || label}
          </p>

          {resource.snippet && (
            <p className="mt-1 text-[11px] text-muted-foreground leading-relaxed line-clamp-2">
              {resource.snippet}
            </p>
          )}

          {safeUrl && (
            <div className="mt-2 pt-1.5 border-t border-border/40 flex items-center justify-between">
              <span className="text-[10px] font-medium text-primary flex items-center gap-1">
                <span>Click pill to visit source</span>
                <ExternalLink size={9} />
              </span>
            </div>
          )}
        </div>
      )}
    </span>
  )
})