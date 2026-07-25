import React from 'react'
import { cn } from '@/lib/utils'

const TOOL_MAP: Record<string, { icon: string; label: string; color: string }> = {
  web_search: { icon: '🌐', label: 'Web Search', color: 'text-sky-400' },
  knowledge_base: { icon: '📚', label: 'Knowledge Base', color: 'text-blue-400' },
  calculator: { icon: '🧮', label: 'Calculator', color: 'text-emerald-400' },
  code_interpreter: { icon: '💻', label: 'Code Interpreter', color: 'text-purple-400' },
  image_analysis: { icon: '📷', label: 'Image Analysis', color: 'text-amber-400' },
  memory: { icon: '🧠', label: 'Memory', color: 'text-rose-400' },
}

interface ToolChipsProps {
  tools: string[]
  className?: string
}

function ToolChipsInner({ tools, className }: ToolChipsProps) {
  if (!tools || tools.length === 0) return null

  return (
    <div className={cn('flex items-center gap-1.5 flex-wrap', className)}>
      <span className="text-caption text-muted-foreground/40 mr-0.5">Used</span>
      {tools.map(name => {
        const meta = TOOL_MAP[name] || { icon: '⚒', label: name, color: 'text-muted-foreground' }
        return (
          <span
            key={name}
            className={cn(
              'inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-muted/20 border border-border/40',
              meta.color,
            )}
          >
            <span>{meta.icon}</span>
            {meta.label}
          </span>
        )
      })}
    </div>
  )
}

export const ToolChips = React.memo(ToolChipsInner)
