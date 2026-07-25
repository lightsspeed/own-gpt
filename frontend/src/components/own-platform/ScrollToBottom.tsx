import { useState, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ScrollToBottomProps {
  show: boolean
  onClick: () => void
  newMessages?: number
  isLoading?: boolean
}

export function ScrollToBottom({ show, onClick, newMessages, isLoading }: ScrollToBottomProps) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    if (show) setMounted(true)
    else {
      const timer = setTimeout(() => setMounted(false), 220)
      return () => clearTimeout(timer)
    }
  }, [show])

  if (!mounted) return null

  const isStreaming = isLoading

  return (
    <button
      onClick={onClick}
      className={cn(
        'fixed z-30 flex items-center justify-center rounded-full border shadow-lg transition-all duration-200',
        newMessages
          ? 'border-primary/30 bg-elevated/95 text-primary hover:border-primary/50 hover:bg-elevated shadow-primary/10'
          : 'border-border/40 bg-elevated/90 text-muted-foreground hover:border-border/70 hover:text-foreground',
        show
          ? 'opacity-100 scale-100'
          : 'opacity-0 scale-[0.96] pointer-events-none',
        newMessages ? 'gap-1.5 px-4 h-10' : 'w-10 h-10',
      )}
      style={{
        left: '50%',
        bottom: '84px',
        transform: `translateX(-50%) ${show ? 'translateY(0)' : 'translateY(2px)'}`,
        boxShadow: newMessages
          ? '0 8px 24px rgba(0,0,0,0.4)'
          : '0 8px 24px rgba(0,0,0,0.3)',
        transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      <ChevronDown size={18} className="shrink-0" />
      {newMessages ? (
        <span className="text-[13px] font-medium whitespace-nowrap">
          {isStreaming ? 'Continue generating' : `${newMessages} new message${newMessages > 1 ? 's' : ''}`}
        </span>
      ) : null}
    </button>
  )
}
