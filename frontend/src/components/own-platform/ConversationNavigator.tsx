import { useRef, useCallback, useEffect, useState, useMemo } from 'react'
import { cn } from '@/lib/utils'
import type { MessageData } from '@/features/chat/types'

export interface NavigatorAnchor {
  id: string
  type: 'user' | 'artifact' | 'summary'
  label: string
  timestamp?: Date
  detail?: string
}

interface ConversationNavigatorProps {
  scrollRef: React.RefObject<HTMLDivElement | null>
  progress: number
  visible: boolean
  anchors: NavigatorAnchor[]
  streamingId?: string | null
  onAnchorClick?: (anchorId: string) => void
}

const TRACK_HEIGHT = 460
const PANEL_WIDTH = 260
const VISIBILITY_GRACE_MS = 300

const ANCHOR_ICONS: Record<string, React.ReactNode> = {
  user: <span className="text-[10px]">●</span>,
  artifact: <span className="text-[12px] leading-none">◆</span>,
  summary: <span className="text-[11px] leading-none">■</span>,
}

function getAnchorIcon(type: NavigatorAnchor['type']) {
  return ANCHOR_ICONS[type] || ANCHOR_ICONS.user
}

export function ConversationNavigator({
  scrollRef,
  progress,
  visible,
  anchors,
  streamingId,
  onAnchorClick,
}: ConversationNavigatorProps) {
  const railRef = useRef<HTMLDivElement>(null)
  const [dragging, setDragging] = useState(false)
  const [hovered, setHovered] = useState(false)
  const [show, setShow] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const hideTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => {
    if (hideTimer.current) clearTimeout(hideTimer.current)
    if (visible) setShow(true)
    else {
      hideTimer.current = setTimeout(() => setShow(false), VISIBILITY_GRACE_MS)
    }
    return () => { if (hideTimer.current) clearTimeout(hideTimer.current) }
  }, [visible])

  // Determine active anchor from scroll progress
  useEffect(() => {
    if (anchors.length === 0) { setActiveIndex(-1); return }
    const idx = Math.round(progress * (anchors.length - 1))
    setActiveIndex(Math.max(0, Math.min(anchors.length - 1, idx)))
  }, [progress, anchors.length])

  const jumpToAnchor = useCallback((anchor: NavigatorAnchor) => {
    const el = scrollRef.current
    if (!el || anchors.length === 0) return
    const idx = anchors.indexOf(anchor)
    if (idx < 0) return
    const target = idx / (anchors.length - 1)
    el.scrollTo({ top: target * (el.scrollHeight - el.clientHeight), behavior: 'smooth' })
    onAnchorClick?.(anchor.id)
  }, [scrollRef, anchors, onAnchorClick])

  const jumpToPosition = useCallback((clientY: number) => {
    const el = scrollRef.current
    const rail = railRef.current
    if (!el || !rail) return
    const rect = rail.getBoundingClientRect()
    const frac = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height))
    el.scrollTo({ top: frac * (el.scrollHeight - el.clientHeight), behavior: 'smooth' })
  }, [scrollRef])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setDragging(true)
    jumpToPosition(e.clientY)
  }, [jumpToPosition])

  useEffect(() => {
    if (!dragging) return
    const handleMove = (e: MouseEvent) => { e.preventDefault(); jumpToPosition(e.clientY) }
    const handleUp = () => setDragging(false)
    window.addEventListener('mousemove', handleMove)
    window.addEventListener('mouseup', handleUp)
    return () => {
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', handleUp)
    }
  }, [dragging, jumpToPosition])

  if (!show) return null

  return (
    <div
      className={cn(
        'fixed z-40 select-none transition-all duration-180',
        show || dragging || hovered ? 'opacity-100' : 'opacity-0 pointer-events-none',
      )}
      style={{
        right: '20px',
        top: '50%',
        transform: 'translateY(-50%)',
        height: `${TRACK_HEIGHT}px`,
        width: hovered || dragging ? `${PANEL_WIDTH}px` : '8px',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { if (!dragging) setHovered(false) }}
    >
      <div
        ref={railRef}
        onMouseDown={handleMouseDown}
        className="relative w-full h-full cursor-pointer"
      >
        {/* Rail track */}
        <div
          className={cn(
            'absolute left-0 top-0 bottom-0 rounded-full bg-border/10 transition-all duration-180',
            hovered || dragging ? 'w-[3px]' : 'w-[2px]',
          )}
        />

        {/* Anchor dots + hover labels */}
        {anchors.map((anchor, i) => {
          const pos = anchors.length > 1 ? (i / (anchors.length - 1)) * 100 : 50
          const isActive = i === activeIndex
          const isStreamingNow = streamingId === anchor.id

          return (
            <div
              key={anchor.id}
              className="absolute left-0 right-0"
              style={{ top: `${pos}%`, transform: 'translateY(-50%)' }}
            >
              {/* Rail dot */}
              <div
                className={cn(
                  'absolute left-0 rounded-full transition-all duration-150 -translate-y-1/2',
                  isActive
                    ? 'bg-primary w-[6px] h-[6px] shadow-[0_0_6px_rgba(59,130,246,0.4)]'
                    : 'bg-foreground/30 w-[5px] h-[5px]',
                  isStreamingNow && 'animate-pulse',
                )}
                style={{ top: '50%' }}
              />

              {/* Hover label panel */}
              {(hovered || dragging) && (
                <button
                  onClick={(e) => { e.stopPropagation(); jumpToAnchor(anchor) }}
                  className={cn(
                    'absolute left-4 right-0 flex items-center gap-2 px-3 py-1.5 rounded-lg text-left transition-all duration-160',
                    isActive
                      ? 'bg-primary/[0.08] text-foreground'
                      : 'text-muted-foreground/70 hover:bg-hover/50 hover:text-foreground',
                  )}
                  style={{ top: '50%', transform: 'translateY(-50%)' }}
                >
                  <span className={cn(
                    'shrink-0',
                    isActive ? 'text-primary' : 'text-muted-foreground/50',
                  )}>
                    {getAnchorIcon(anchor.type)}
                  </span>
                  <span className="text-[12px] truncate flex-1">{anchor.label}</span>
                </button>
              )}
            </div>
          )
        })}

        {/* Ghost click area when not hovered — full height drag zone */}
        {!hovered && !dragging && (
          <div className="absolute inset-0" />
        )}
      </div>
    </div>
  )
}
