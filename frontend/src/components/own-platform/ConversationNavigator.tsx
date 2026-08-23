import { useRef, useCallback, useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import { List } from 'lucide-react'

export interface NavigatorAnchor {
  id: string
  targetMsgId: string
  type: 'user' | 'artifact' | 'summary'
  label: string
  responseCount?: number
  artifactCount?: number
  toolCount?: number
}

interface ConversationOutlineProps {
  chapters: NavigatorAnchor[]
  streamingId?: string | null
  onAnchorClick: (anchorId: string, targetMsgId: string) => void
  direction?: 'up' | 'down'
}

const CHAPTER_ICONS: Record<string, string> = {
  user: '▶',
  artifact: '◆',
  summary: '■',
}

function ChapterIcon({ type }: { type: NavigatorAnchor['type'] }) {
  const icon = CHAPTER_ICONS[type] || CHAPTER_ICONS.user
  return <span className="shrink-0 leading-none text-[11px]">{icon}</span>
}

export function ConversationOutline({ chapters, streamingId, onAnchorClick, direction = 'up' }: ConversationOutlineProps) {
  const [open, setOpen] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handleClickOutside = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  if (chapters.length === 0) return null

  return (
    <div ref={panelRef} className="relative">
      <button
        id="composer-outline-trigger"
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-1.5 text-[12px] font-medium px-2.5 py-1.5 rounded-full transition-all',
          open
            ? 'text-primary bg-primary/[0.08]'
            : 'text-muted-foreground/50 hover:text-foreground hover:bg-hover/50',
        )}
        title="Conversation Outline"
      >
        <List size={14} />
        <span className="hidden sm:inline">Outline</span>
      </button>

      {open && (
        <div
          className={cn(
            'absolute left-0 z-50 w-[260px] rounded-xl border border-border/40 bg-elevated/95 backdrop-blur-lg shadow-xl overflow-hidden animate-scale-in',
            direction === 'up' ? 'bottom-full mb-2 origin-bottom-left' : 'top-full mt-1 origin-top-left',
          )}
        >
          <div className="px-4 py-2.5 border-b border-border/10">
            <p className="text-[13px] font-medium text-foreground">Conversation Outline</p>
          </div>

          <div className="py-1 max-h-[360px] overflow-y-auto">
            {chapters.map((chapter) => {
              const isStreamingNow = streamingId === chapter.targetMsgId

              return (
                <button
                  key={chapter.id}
                  onClick={() => { onAnchorClick(chapter.id, chapter.targetMsgId); setOpen(false) }}
                  className="group relative w-full flex items-start gap-2.5 px-4 py-2 text-left hover:bg-hover/60 transition-colors"
                >
                  <span className={cn(
                    'mt-0.5 shrink-0',
                    isStreamingNow ? 'text-primary' : 'text-muted-foreground/40 group-hover:text-muted-foreground/60',
                  )}>
                    <ChapterIcon type={chapter.type} />
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className={cn(
                      'text-[13px] leading-snug truncate',
                      isStreamingNow ? 'text-primary' : 'text-foreground/80 group-hover:text-foreground',
                    )}>
                      {chapter.label}
                    </p>
                    <div className="flex flex-wrap gap-x-2.5 gap-y-0.5 mt-0.5">
                      {chapter.responseCount !== undefined && (
                        <span className="text-[10px] text-muted-foreground/50">
                          {chapter.responseCount} response{chapter.responseCount !== 1 ? 's' : ''}
                        </span>
                      )}
                      {chapter.artifactCount !== undefined && chapter.artifactCount > 0 && (
                        <span className="text-[10px] text-muted-foreground/50">
                          {chapter.artifactCount} artifact{chapter.artifactCount !== 1 ? 's' : ''}
                        </span>
                      )}
                      {chapter.toolCount !== undefined && chapter.toolCount > 0 && (
                        <span className="text-[10px] text-muted-foreground/50">
                          {chapter.toolCount} tool{chapter.toolCount !== 1 ? 's' : ''}
                        </span>
                      )}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>

          <div className="px-4 py-2 border-t border-border/10">
            <p className="text-[10px] text-muted-foreground/40">{chapters.length} chapter{chapters.length !== 1 ? 's' : ''}</p>
          </div>
        </div>
      )}
    </div>
  )
}
