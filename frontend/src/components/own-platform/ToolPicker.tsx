import { useRef, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { Search, Wrench } from 'lucide-react'
import type { ToolInfo, ToolMode } from '@/features/chat/types'

interface ToolPickerProps {
  tools: ToolInfo[]
  onToggle: (name: string) => void
  onModeChange: (name: string, mode: ToolMode) => void
  onClose: () => void
}

const MODE_OPTIONS: { value: ToolMode; label: string; desc: string }[] = [
  { value: 'auto', label: 'Auto', desc: 'Run when needed' },
  { value: 'manual', label: 'Manual', desc: 'Ask before running' },
  { value: 'disabled', label: 'Off', desc: 'Never use' },
]

export function ToolPicker({ tools, onToggle, onModeChange, onClose }: ToolPickerProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const byCategory = (cat: string) => tools.filter(t => t.category === cat)

  return (
    <div
      ref={ref}
      className="absolute bottom-full left-0 mb-2 w-[340px] bg-elevated border border-border rounded-xl shadow-2xl overflow-hidden z-50"
      style={{ maxHeight: 'min(420px, 70vh)' }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-4 pt-3.5 pb-2 border-b border-border/50">
        <Wrench size={14} className="text-muted-foreground" />
        <span className="text-small font-semibold text-foreground">Tools</span>
        <span className="text-caption text-muted-foreground/40 ml-auto">
          {tools.filter(t => t.enabled).length} active
        </span>
      </div>

      {/* Tool list */}
      <div className="overflow-y-auto max-h-[340px] px-1.5 py-1.5 space-y-0.5">
        {(['knowledge', 'analysis', 'generation', 'external'] as const).map(cat => {
          const items = byCategory(cat)
          if (items.length === 0) return null
          return (
            <div key={cat}>
              <div className="px-2.5 py-1.5 text-caption font-medium text-muted-foreground/50 uppercase tracking-wider">
                {cat}
              </div>
              {items.map(tool => (
                <div
                  key={tool.name}
                  className={cn(
                    'rounded-lg border transition-all',
                    tool.enabled
                      ? 'border-primary/20 bg-primary/[0.03]'
                      : 'border-transparent',
                  )}
                >
                  {/* Toggle row */}
                  <div className="flex items-center gap-2.5 px-2.5 py-2">
                    <button
                      onClick={() => onToggle(tool.name)}
                      className={cn(
                        'w-9 h-9 rounded-lg flex items-center justify-center border transition-all shrink-0',
                        tool.enabled
                          ? 'bg-primary/15 border-primary/25 text-primary'
                          : 'bg-muted/20 border-border/50 text-muted-foreground/40',
                      )}
                    >
                      <span className="text-base">{tool.icon}</span>
                    </button>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={cn('text-small font-medium', tool.enabled ? 'text-foreground' : 'text-muted-foreground/50')}>
                          {tool.label}
                        </span>
                      </div>
                      <p className="text-caption text-muted-foreground/50 truncate">{tool.desc}</p>
                    </div>

                    {/* Toggle switch */}
                    <button
                      onClick={() => onToggle(tool.name)}
                      className={cn(
                        'relative w-8 h-4 rounded-full transition-all shrink-0',
                        tool.enabled ? 'bg-primary' : 'bg-muted/40',
                      )}
                    >
                      <div className={cn(
                        'absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-all',
                        tool.enabled ? 'left-[18px]' : 'left-0.5',
                      )} />
                    </button>
                  </div>

                  {/* Mode selection */}
                  {tool.enabled && (
                    <div className="flex gap-1 px-2.5 pb-2.5 pt-0">
                      {MODE_OPTIONS.map(opt => (
                        <button
                          key={opt.value}
                          onClick={() => onModeChange(tool.name, opt.value)}
                          className={cn(
                            'flex-1 px-2 py-1 rounded-md text-[10px] font-medium transition-all',
                            tool.mode === opt.value
                              ? 'bg-primary/15 text-primary'
                              : 'text-muted-foreground/40 hover:text-muted-foreground hover:bg-hover',
                          )}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
