import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ScrollToBottomProps {
  visible: boolean
  onClick: () => void
  newMessages?: number
}

export function ScrollToBottom({ visible, onClick, newMessages }: ScrollToBottomProps) {
  if (!visible) return null

  return (
    <div className="flex justify-center">
      <button
        onClick={onClick}
        className={cn(
          'flex items-center gap-2 px-4 py-2 rounded-full border border-border/60 bg-elevated/90 backdrop-blur-sm shadow-lg text-small font-medium transition-all hover:bg-elevated active:scale-[0.97]',
          newMessages ? 'text-primary border-primary/30' : 'text-muted-foreground',
        )}
      >
        <ChevronDown size={16} />
        {newMessages ? `${newMessages} new message${newMessages > 1 ? 's' : ''}` : 'Scroll to bottom'}
      </button>
    </div>
  )
}
