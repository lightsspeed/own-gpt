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

  const hasNewMessages = !!newMessages && newMessages > 0

  return (
    <button
      onClick={onClick}
      className={cn(
        'fixed z-30 flex items-center justify-center w-9 h-9 rounded-full transition-all duration-200 ease-out',
        hasNewMessages
          ? 'bg-primary text-white shadow-[0_8px_20px_rgba(0,0,0,0.28)]'
          : 'bg-[rgba(32,32,34,0.95)] backdrop-blur-[12px] text-muted-foreground border border-white/[0.08] shadow-[0_8px_20px_rgba(0,0,0,0.28)]',
        show
          ? 'opacity-100 scale-100 translate-y-0'
          : 'opacity-0 scale-[0.96] translate-y-2 pointer-events-none',
        !hasNewMessages && 'hover:translate-y-[-2px] hover:scale-105',
      )}
      style={{
        left: '50%',
        bottom: '96px',
        transform: `translateX(-50%) ${show ? 'translateY(0)' : 'translateY(8px)'}`,
        transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)',
      }}
    >
      {hasNewMessages ? (
        <span className="text-[13px] font-bold leading-none">{newMessages}</span>
      ) : (
        <ChevronDown
          size={18}
          strokeWidth={2}
          className={cn(isLoading && 'animate-bounce-subtle')}
        />
      )}
    </button>
  )
}
