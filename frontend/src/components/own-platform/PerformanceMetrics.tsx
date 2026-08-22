import { useState, useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'

interface Metric {
  label: string
  value: string
  color?: string
}

export function PerformanceMetrics() {
  const [visible, setVisible] = useState(false)
  const [metrics, setMetrics] = useState<Metric[]>([])
  const fpsRef = useRef({ frames: 0, lastTime: performance.now(), fps: 0 })
  const rafRef = useRef<number>()

  // Toggle with Ctrl+Shift+M
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === 'M') {
        setVisible(v => !v)
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [])

  // FPS counter
  useEffect(() => {
    if (!visible) return
    const tick = () => {
      const now = performance.now()
      fpsRef.current.frames++
      if (now - fpsRef.current.lastTime >= 1000) {
        fpsRef.current.fps = fpsRef.current.frames
        fpsRef.current.frames = 0
        fpsRef.current.lastTime = now
      }
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [visible])

  // Collect metrics every 500ms
  useEffect(() => {
    if (!visible) return
    const interval = setInterval(() => {
      const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined
      const mem = (performance as any).memory
      const entries: Metric[] = [
        { label: 'FPS', value: String(fpsRef.current.fps), color: fpsRef.current.fps >= 50 ? 'text-success' : fpsRef.current.fps >= 30 ? 'text-warning' : 'text-danger' },
      ]
      if (nav) {
        entries.push({ label: 'TTI', value: `${Math.round(nav.domInteractive)}ms` })
        entries.push({ label: 'LCP', value: nav.domContentLoadedEventEnd ? `${Math.round(nav.domContentLoadedEventEnd)}ms` : '—' })
      }
      if (mem) {
        entries.push({ label: 'JS Heap', value: `${Math.round(mem.usedJSHeapSize / 1048576)}MB` })
      }
      setMetrics(entries)
    }, 500)
    return () => clearInterval(interval)
  }, [visible])

  if (!visible) return null

  return (
    <div className="fixed bottom-4 right-4 z-[200] bg-elevated/90 backdrop-blur-md border border-border/30 rounded-xl p-3 shadow-2xl font-mono text-[10px] space-y-1 min-w-[140px]">
      <div className="text-caption text-muted-foreground/40 uppercase tracking-wider mb-1.5">Performance</div>
      {metrics.map(m => (
        <div key={m.label} className="flex items-center justify-between gap-4">
          <span className="text-muted-foreground/60">{m.label}</span>
          <span className={cn('font-semibold', m.color || 'text-foreground/80')}>{m.value}</span>
        </div>
      ))}
      <div className="text-caption text-muted-foreground/30 pt-1 border-t border-border/10 mt-1">Ctrl+Shift+M to hide</div>
    </div>
  )
}
