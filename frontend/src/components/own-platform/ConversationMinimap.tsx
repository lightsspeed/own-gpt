import { useRef, useCallback, useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

interface ConversationMinimapProps {
  scrollRef: React.RefObject<HTMLDivElement | null>
  progress: number
  visible: boolean
}

const TRACK_HEIGHT = 460
const VISIBILITY_GRACE_MS = 300

export function ConversationMinimap({ scrollRef, progress, visible }: ConversationMinimapProps) {
  const railRef = useRef<HTMLDivElement>(null)
  const [dragging, setDragging] = useState(false)
  const [hovered, setHovered] = useState(false)
  const [show, setShow] = useState(false)
  const hideTimer = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (hideTimer.current) clearTimeout(hideTimer.current)
    if (visible) {
      setShow(true)
    } else {
      hideTimer.current = setTimeout(() => setShow(false), VISIBILITY_GRACE_MS)
    }
    return () => { if (hideTimer.current) clearTimeout(hideTimer.current) }
  }, [visible])

  const jumpTo = useCallback((clientY: number) => {
    const el = scrollRef.current
    const rail = railRef.current
    if (!el || !rail) return
    const rect = rail.getBoundingClientRect()
    const frac = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height))
    el.scrollTo({ top: frac * (el.scrollHeight - el.clientHeight), behavior: 'smooth' })
  }, [scrollRef])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setDragging(true)
    jumpTo(e.clientY)
  }, [jumpTo])

  useEffect(() => {
    if (!dragging) return
    const handleMove = (e: MouseEvent) => { e.preventDefault(); jumpTo(e.clientY) }
    const handleUp = () => setDragging(false)
    window.addEventListener('mousemove', handleMove)
    window.addEventListener('mouseup', handleUp)
    return () => {
      window.removeEventListener('mousemove', handleMove)
      window.removeEventListener('mouseup', handleUp)
    }
  }, [dragging, jumpTo])

  const ticks: number[] = []
  for (let i = 0; i < Math.floor(TRACK_HEIGHT / 12); i++) {
    ticks.push(i * 12)
  }

  return (
    <div
      className={cn(
        'fixed z-40 select-none transition-all duration-200',
        show || dragging || hovered ? 'opacity-100' : 'opacity-0 pointer-events-none',
      )}
      style={{
        right: '20px',
        top: '50%',
        transform: 'translateY(-50%)',
        height: `${TRACK_HEIGHT}px`,
        width: '8px',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { if (!dragging) setHovered(false) }}
    >
      <div
        ref={railRef}
        onMouseDown={handleMouseDown}
        className="relative w-full h-full cursor-pointer"
      >
        {/* Track */}
        <div
          className={cn(
            'absolute left-1/2 top-0 bottom-0 -translate-x-1/2 rounded-full bg-border/15 transition-all duration-180',
            hovered || dragging ? 'w-[5px]' : 'w-[2px]',
          )}
        />

        {/* Tick marks */}
        {ticks.map((t, i) => (
          <div
            key={i}
            className={cn(
              'absolute left-1/2 -translate-x-1/2 h-[1px] transition-all duration-180',
              hovered || dragging ? 'opacity-70' : 'opacity-35',
            )}
            style={{
              width: '10px',
              top: `${t}px`,
              background: 'currentColor',
            }}
          />
        ))}

        {/* Progress thumb */}
        <div
          className={cn(
            'absolute left-1/2 -translate-x-1/2 w-2 h-8 rounded-full transition-all duration-150',
            dragging ? 'bg-primary shadow-[0_0_12px_rgba(59,130,246,0.55)]' : 'bg-primary/70 shadow-[0_0_8px_rgba(59,130,246,0.3)]',
          )}
          style={{
            top: `${Math.max(0, Math.min(100, progress * 100))}%`,
            transform: `translate(-50%, -${Math.max(0, Math.min(100, progress * 100))}%)`,
          }}
        />
      </div>
    </div>
  )
}
