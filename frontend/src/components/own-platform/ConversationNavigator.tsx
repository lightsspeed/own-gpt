import { useRef, useCallback, useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

export interface NavigatorAnchor {
  id: string
  targetMsgId: string
  type: 'user' | 'section' | 'artifact' | 'summary'
  label: string
  responseCount?: number
  artifactCount?: number
  toolCount?: number
}

interface ConversationNavigatorProps {
  scrollRef: React.RefObject<HTMLDivElement | null>
  progress: number
  visible: boolean
  anchors: NavigatorAnchor[]
  streamingId?: string | null
  onAnchorClick?: (anchorId: string, targetMsgId: string) => void
}

const TRACK_HEIGHT = 460
const PANEL_WIDTH = 260
const VISIBILITY_GRACE_MS = 300

const sectionIcons: Record<string, string> = {
  user: '\u25CF',
  section: '\u25CF',
  artifact: '\u25C6',
  summary: '\u25A0',
}

function SectionIcon({ type }: { type: NavigatorAnchor['type'] }) {
  const icon = sectionIcons[type] || '\u25CF'
  return <span className={cn(
    'shrink-0 leading-none',
    type === 'user' && 'text-[11px]',
    type === 'section' && 'text-[10px] opacity-70',
    type === 'artifact' && 'text-[13px]',
    type === 'summary' && 'text-[11px]',
  )}>{icon}</span>
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
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const hideTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  useEffect(() => {
    if (hideTimer.current) clearTimeout(hideTimer.current)
    if (visible) setShow(true)
    else {
      hideTimer.current = setTimeout(() => setShow(false), VISIBILITY_GRACE_MS)
    }
    return () => { if (hideTimer.current) clearTimeout(hideTimer.current) }
  }, [visible])

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
    const target = anchors.length > 1 ? idx / (anchors.length - 1) : 0
    el.scrollTo({ top: target * (el.scrollHeight - el.clientHeight), behavior: 'smooth' })
    onAnchorClick?.(anchor.id, anchor.targetMsgId)
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

  const panelOpen = hovered || dragging

  return (
    <div
      className={cn(
        'fixed z-40 select-none transition-all duration-180 ease-out',
        show || dragging || hovered ? 'opacity-100' : 'opacity-0 pointer-events-none',
      )}
      style={{
        right: '20px',
        top: '50%',
        transform: 'translateY(-50%)',
        height: `${TRACK_HEIGHT}px`,
        width: panelOpen ? `${PANEL_WIDTH}px` : '8px',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { if (!dragging) { setHovered(false); setHoveredIndex(null) } }}
    >
      <div
        ref={railRef}
        onMouseDown={handleMouseDown}
        className="relative w-full h-full cursor-pointer"
      >
        {/* Rail track */}
        <div
          className={cn(
            'absolute left-0 top-0 bottom-0 rounded-full transition-all duration-180',
            panelOpen ? 'w-[2px]' : 'w-[2px]',
          )}
          style={{
            background: panelOpen
              ? 'linear-gradient(to bottom, rgba(255,255,255,0.08), rgba(255,255,255,0.04))'
              : 'rgba(255,255,255,0.06)',
          }}
        />

        {/* Section dots (always visible) + labels (on hover) */}
        {anchors.map((anchor, i) => {
          const pos = anchors.length > 1 ? (i / (anchors.length - 1)) * 100 : 50
          const isActive = i === activeIndex
          const isHovered = i === hoveredIndex
          const isStreamingNow = streamingId === anchor.targetMsgId
          const isArtifact = anchor.type === 'artifact'

          return (
            <div
              key={anchor.id}
              className="absolute left-0 right-0"
              style={{ top: `${pos}%`, transform: 'translateY(-50%)' }}
            >
              {/* Rail dot */}
              <div
                className={cn(
                  'absolute left-0 rounded-full transition-all duration-150',
                  isActive
                    ? 'bg-primary w-[7px] h-[7px] shadow-[0_0_8px_rgba(59,130,246,0.5)]'
                    : 'bg-foreground/25 w-[5px] h-[5px]',
                  isStreamingNow && 'animate-pulse',
                  isArtifact && !isActive && 'bg-foreground/35 w-[6px] h-[6px]',
                )}
                style={{ top: '50%', transform: 'translate(-50%, -50%)', left: '1px' }}
              />

              {/* Panel labels */}
              {panelOpen && (
                <button
                  onClick={(e) => { e.stopPropagation(); jumpToAnchor(anchor) }}
                  onMouseEnter={() => setHoveredIndex(i)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  className={cn(
                    'absolute left-4 right-0 flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-all duration-120',
                    isActive
                      ? 'bg-primary/[0.08] text-foreground'
                      : 'text-muted-foreground/60 hover:bg-hover/50 hover:text-foreground',
                  )}
                  style={{ top: '50%', transform: 'translateY(-50%)' }}
                >
                  <span className={cn(
                    'shrink-0',
                    isActive ? 'text-primary' : 'text-muted-foreground/40',
                  )}>
                    <SectionIcon type={anchor.type} />
                  </span>
                  <span className="text-[12px] leading-tight truncate flex-1">{anchor.label}</span>

                  {/* Hover tooltip card */}
                  {isHovered && !isActive && (
                    <div className="fixed z-50 pointer-events-none" style={{
                      left: 'calc(100% + 8px)',
                      top: '50%',
                      transform: 'translateY(-50%)',
                    }}>
                      <div className="bg-popover border border-border/40 rounded-xl px-3.5 py-2.5 shadow-xl min-w-[160px]">
                        <p className="text-[13px] font-medium text-foreground truncate max-w-[180px]">{anchor.label}</p>
                        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground/60">
                          {anchor.responseCount !== undefined && (
                            <span>{anchor.responseCount} response{anchor.responseCount !== 1 ? 's' : ''}</span>
                          )}
                          {anchor.artifactCount !== undefined && anchor.artifactCount > 0 && (
                            <span>{anchor.artifactCount} artifact{anchor.artifactCount !== 1 ? 's' : ''}</span>
                          )}
                          {anchor.toolCount !== undefined && anchor.toolCount > 0 && (
                            <span>{anchor.toolCount} tool{anchor.toolCount !== 1 ? 's' : ''}</span>
                          )}
                        </div>
                        <p className="mt-1 text-[10px] text-muted-foreground/40">Click to jump</p>
                      </div>
                    </div>
                  )}
                </button>
              )}

              {/* Separator line between entries (only in panel mode, between non-consecutive sections) */}
              {panelOpen && i > 0 && (
                <div
                  className="absolute left-4 right-3 border-t border-border/10 pointer-events-none"
                  style={{ top: '-50%' }}
                />
              )}
            </div>
          )
        })}

        {/* Ghost drag zone when collapsed */}
        {!panelOpen && (
          <div className="absolute inset-0" />
        )}
      </div>
    </div>
  )
}
