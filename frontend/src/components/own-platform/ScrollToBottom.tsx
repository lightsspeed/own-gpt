import { useState, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ScrollToBottomProps {
  visible: boolean
  onClick: () => void
  newMessages?: number
  isLoading?: boolean
}

export function ScrollToBottom({ visible, onClick, newMessages, isLoading }: ScrollToBottomProps) {
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    if (visible) setMounted(true)
    else {
      const timer = setTimeout(() => setMounted(false), 200)
      return () => clearTimeout(timer)
    }
  }, [visible])

  if (!mounted) return null

  const label = newMessages
    ? isLoading
      ? 'Continue ↓'
      : 'New response ↓'
    : null

  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center justify-center gap-1.5 h-10 rounded-full border bg-elevated/90 backdrop-blur-sm shadow-lg transition-all duration-200',
        newMessages
          ? 'border-primary/30 text-primary hover:border-primary/50 shadow-primary/10'
          : 'border-border/50 text-muted-foreground hover:border-border/80 hover:text-foreground',
        visible
          ? 'opacity-100 translate-y-0 scale-100'
          : 'opacity-0 translate-y-2 scale-95 pointer-events-none',
        label ? 'px-4' : 'w-10',
      )}
      style={{ transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)' }}
    >
      <ChevronDown size={16} className="shrink-0" />
      {label && (
        <span className="text-[13px] font-medium whitespace-nowrap">{label}</span>
      )}
    </button>
  )
}
