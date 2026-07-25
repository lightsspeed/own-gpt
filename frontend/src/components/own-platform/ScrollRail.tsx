import { useRef, useCallback, useEffect, useState } from 'react'
import { cn } from '@/lib/utils'

interface ScrollRailProps {
  scrollRef: React.RefObject<HTMLDivElement | null>
  progress: number
}

export function ScrollRail({ scrollRef, progress }: ScrollRailProps) {
  const railRef = useRef<HTMLDivElement>(null)
  const [dragging, setDragging] = useState(false)
  const [hovered, setHovered] = useState(false)

  const jumpTo = useCallback((clientY: number) => {
    const el = scrollRef.current
    const rail = railRef.current
    if (!el || !rail) return
    const rect = rail.getBoundingClientRect()
    const frac = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height))
    el.scrollTop = frac * (el.scrollHeight - el.clientHeight)
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

  return (
    <div
      ref={railRef}
      onMouseDown={handleMouseDown}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { if (!dragging) setHovered(false) }}
      className={cn(
        'absolute right-1.5 top-0 bottom-0 z-20 cursor-pointer select-none transition-all duration-150',
        hovered || dragging ? 'w-[5px]' : 'w-[3px]',
      )}
      style={{ paddingBlock: '12px' }}
    >
      {/* Rail track */}
      <div className="relative w-full h-full rounded-full bg-border/8">
        {/* Top dot */}
        <div className="absolute left-1/2 top-0 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-border/20" />

        {/* Thumb */}
        <div
          className={cn(
            'absolute left-1/2 -translate-x-1/2 w-2 h-8 rounded-full transition-all duration-150',
            dragging ? 'bg-primary shadow-[0_0_12px_rgba(59,130,246,0.5)]' : 'bg-primary/60',
          )}
          style={{ top: `${progress * 100}%`, transform: `translate(-50%, -${progress * 100}%)` }}
        />

        {/* Bottom dot */}
        <div className="absolute left-1/2 bottom-0 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-border/20" />
      </div>
    </div>
  )
}
