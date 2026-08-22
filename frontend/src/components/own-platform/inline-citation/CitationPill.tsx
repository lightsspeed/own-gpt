import React from 'react'
import { cn } from '@/lib/utils'

interface CitationPillProps {
  label: string
  active?: boolean
  onActivate: () => void
  /** Hover navigation (desktop). Timer management lives in the renderer. */
  onHoverEnter: () => void
  onHoverLeave: () => void
  className?: string
}

export const CitationPill = React.forwardRef<HTMLButtonElement, CitationPillProps>(function CitationPill(
  { label, active, onActivate, onHoverEnter, onHoverLeave, className },
  ref,
) {
  const parts = label.split(/(\s\+\d+$)/)
  const text = parts[0] ?? label
  const extra = parts[1]

  return (
    <button
      ref={ref}
      type="button"
      onClick={onActivate}
      onMouseEnter={onHoverEnter}
      onMouseLeave={onHoverLeave}
      onFocus={onHoverEnter}
      aria-label={`Citation: ${label}`}
      aria-expanded={active || undefined}
      className={cn(
        'inline-flex items-center gap-0.5 align-baseline',
        'mx-0.5 my-0 rounded-full border px-1.5 py-px',
        'text-micro font-medium leading-[1.4] whitespace-nowrap',
        'transition-all select-none cursor-pointer',
        active
          ? 'bg-primary/15 text-primary border-primary/40'
          : 'bg-elevated/70 text-foreground/70 border-border/60 hover:bg-primary/10 hover:text-primary hover:border-primary/30',
        className,
      )}
    >
      {text}
      {extra && (
        <span className={cn('text-[0.82em] font-semibold', active ? 'text-primary' : 'text-primary/80')}>
          {extra}
        </span>
      )}
    </button>
  )
})