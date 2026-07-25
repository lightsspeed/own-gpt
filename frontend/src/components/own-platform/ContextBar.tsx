import { useState } from 'react'
import { cn } from '@/lib/utils'
import {
  Globe, Cloud, FileText, FlaskConical, BookOpen, Clock, Hash, X, Plus, ChevronDown
} from 'lucide-react'
import type { ContextItem, ContextCategory } from '@/features/chat/types'
import { ContextPicker } from './ContextPicker'

const CATEGORY_META: Record<ContextCategory, { icon: React.ReactNode; color: string }> = {
  environment: { icon: <Globe size={12} />, color: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' },
  service: { icon: <Cloud size={12} />, color: 'bg-sky-500/15 text-sky-400 border-sky-500/20' },
  artifact: { icon: <FileText size={12} />, color: 'bg-orange-500/15 text-orange-400 border-orange-500/20' },
  experiment: { icon: <FlaskConical size={12} />, color: 'bg-purple-500/15 text-purple-400 border-purple-500/20' },
  knowledge: { icon: <BookOpen size={12} />, color: 'bg-blue-500/15 text-blue-400 border-blue-500/20' },
  timeframe: { icon: <Clock size={12} />, color: 'bg-amber-500/15 text-amber-400 border-amber-500/20' },
  custom: { icon: <Hash size={12} />, color: 'bg-muted/30 text-muted-foreground border-muted/30' },
}

interface ContextBarProps {
  items: ContextItem[]
  onAdd: (item: ContextItem) => void
  onRemove: (id: string) => void
  onClear: () => void
}

export function ContextBar({ items, onAdd, onRemove, onClear }: ContextBarProps) {
  const [pickerOpen, setPickerOpen] = useState(false)

  if (items.length === 0 && !pickerOpen) return null

  return (
    <div className="w-full max-w-[860px] mx-auto relative">
      <div className="flex items-center gap-1.5 px-1 pb-1.5 overflow-x-auto">
        {/* Label */}
        {items.length > 0 && (
          <span className="shrink-0 text-caption font-medium text-muted-foreground/50 uppercase tracking-wider mr-1">
            Context
          </span>
        )}

        {/* Chips */}
        {items.map(item => {
          const meta = CATEGORY_META[item.category]
          return (
            <div
              key={item.id}
              className={cn(
                'group flex items-center gap-1.5 shrink-0 px-2 py-1 rounded-lg border text-[11px] font-medium transition-all',
                meta.color,
              )}
            >
              {meta.icon}
              <span className="max-w-[120px] truncate">{item.label}</span>
              <button
                onClick={() => onRemove(item.id)}
                className="ml-0.5 p-0.5 rounded text-current/40 hover:text-current opacity-0 group-hover:opacity-100 transition-all"
              >
                <X size={10} />
              </button>
            </div>
          )
        })}

        {/* Add button */}
        <button
          onClick={() => setPickerOpen(!pickerOpen)}
          className={cn(
            'shrink-0 flex items-center gap-1 px-2.5 py-1 rounded-lg border border-dashed text-[11px] font-medium transition-all',
            pickerOpen
              ? 'border-primary/40 text-primary bg-primary/10'
              : 'border-border/60 text-muted-foreground/50 hover:text-muted-foreground hover:border-muted-foreground/30 hover:bg-hover',
          )}
        >
          {pickerOpen ? <ChevronDown size={12} /> : <Plus size={12} />}
          {pickerOpen ? 'Close' : 'Add'}
        </button>

        {/* Clear all */}
        {items.length > 1 && (
          <button
            onClick={onClear}
            className="shrink-0 px-2 py-1 rounded-lg text-[11px] text-muted-foreground/40 hover:text-muted-foreground hover:bg-hover transition-all"
          >
            Clear
          </button>
        )}
      </div>

      {/* Picker dropdown */}
      {pickerOpen && (
        <ContextPicker
          onAdd={item => { onAdd(item); setPickerOpen(false) }}
          onClose={() => setPickerOpen(false)}
          existingLabels={items.map(i => i.label)}
        />
      )}
    </div>
  )
}
