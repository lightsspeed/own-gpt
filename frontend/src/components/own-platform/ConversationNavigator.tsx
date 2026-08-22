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
}

const CHAPTER_ICONS: Record<string, string> = {
  user: '\u25B6',
  artifact: '\u25C6',
  summary: '\u25A0',
}

function ChapterIcon({ type }: { type: NavigatorAnchor['type'] }) {
  const icon = CHAPTER_ICONS[type] || CHAPTER_ICONS.user
  return <span className="shrink-0 leading-none text-[11px]">{icon}</span>
}

export function ConversationOutline({ chapters, streamingId, onAnchorClick }: ConversationOutlineProps) {
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
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-1.5 text-[12px] font-medium px-2.5 py-1.5 rounded-lg transition-all',
          open
            ? 'text-primary bg-primary/[0.08]'
            : 'text-muted-foreground/50 hover:text-foreground hover:bg-hover/50',
        )}
      >
        <List size={14} />
        Outline
      </button>

      {open && (
        <div
          className={cn(
            'absolute left-0 top-full mt-1 z-50 w-[260px] rounded-xl border border-border/40 bg-elevated/95 backdrop-blur-lg shadow-xl overflow-hidden animate-scale-in origin-top-left',
          )}
          style={{ transformOrigin: 'top left' }}
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
