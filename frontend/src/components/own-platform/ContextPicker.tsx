import { useState, useRef, useEffect } from 'react'
import { cn } from '@/lib/utils'
import {
  Globe, Cloud, FileText, FlaskConical, BookOpen, Clock, Hash, Plus, Search
} from 'lucide-react'
import type { ContextItem, ContextCategory } from '@/features/chat/types'

const CATEGORIES: { category: ContextCategory; icon: React.ReactNode; label: string; color: string }[] = [
  { category: 'environment', icon: <Globe size={14} />, label: 'Environment', color: 'text-emerald-400' },
  { category: 'service', icon: <Cloud size={14} />, label: 'Service', color: 'text-sky-400' },
  { category: 'artifact', icon: <FileText size={14} />, label: 'Artifact', color: 'text-orange-400' },
  { category: 'experiment', icon: <FlaskConical size={14} />, label: 'Experiment', color: 'text-purple-400' },
  { category: 'knowledge', icon: <BookOpen size={14} />, label: 'Knowledge', color: 'text-blue-400' },
  { category: 'timeframe', icon: <Clock size={14} />, label: 'Time Range', color: 'text-amber-400' },
  { category: 'custom', icon: <Hash size={14} />, label: 'Custom', color: 'text-muted-foreground' },
]

const PRESETS: Record<ContextCategory, string[]> = {
  environment: ['Production', 'Staging', 'Development', 'Local'],
  service: ['API Gateway', 'Auth Service', 'Vector DB', 'Embedding', 'Reranker', 'Retrieval'],
  artifact: [],
  experiment: [],
  knowledge: ['Terraform', 'Kubernetes', 'AWS', 'FastAPI', 'Architecture', 'Runbooks'],
  timeframe: ['Today', 'Last 24h', 'Last 7d', 'Last 30d', 'Since last deployment'],
  custom: [],
}

interface ContextPickerProps {
  onAdd: (item: ContextItem) => void
  onClose: () => void
  existingLabels: string[]
}

export function ContextPicker({ onAdd, onClose, existingLabels }: ContextPickerProps) {
  const [query, setQuery] = useState('')
  const [selectedCat, setSelectedCat] = useState<ContextCategory | 'all'>('all')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  const filtered = (() => {
    const cats = selectedCat === 'all'
      ? CATEGORIES
      : CATEGORIES.filter(c => c.category === selectedCat)

    const results: { category: ContextCategory; label: string }[] = []

    for (const cat of cats) {
      if (cat.category === 'custom' && query.trim()) {
        results.push({ category: 'custom', label: query.trim() })
        continue
      }
      const presets = PRESETS[cat.category] || []
      for (const p of presets) {
        if (existingLabels.includes(p)) continue
        if (!query || p.toLowerCase().includes(query.toLowerCase())) {
          results.push({ category: cat.category, label: p })
        }
      }
    }

    return results
  })()

  return (
    <div
      ref={ref}
      className="absolute bottom-full left-0 right-0 mb-2 bg-elevated border border-border rounded-xl shadow-2xl overflow-hidden z-50"
      style={{ maxHeight: 'min(400px, 60vh)' }}
    >
      {/* Search */}
      <div className="relative px-3 pt-3 pb-2">
        <Search size={14} className="absolute left-5 top-[22px] text-muted-foreground/40" />
        <input
          autoFocus
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search context..."
          className="w-full rounded-lg border border-border bg-background/50 py-1.5 pl-8 pr-3 text-small text-foreground placeholder:text-muted-foreground/40 outline-none focus:border-primary/40 transition-colors"
        />
      </div>

      {/* Category filter */}
      <div className="flex gap-1 px-3 pb-2 overflow-x-auto">
        <button
          onClick={() => setSelectedCat('all')}
          className={cn(
            'shrink-0 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all',
            selectedCat === 'all' ? 'bg-primary/15 text-primary' : 'text-muted-foreground/50 hover:text-muted-foreground hover:bg-hover',
          )}
        >
          All
        </button>
        {CATEGORIES.map(cat => (
          <button
            key={cat.category}
            onClick={() => setSelectedCat(cat.category)}
            className={cn(
              'shrink-0 flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all',
              selectedCat === cat.category ? 'bg-primary/15 text-primary' : 'text-muted-foreground/50 hover:text-muted-foreground hover:bg-hover',
            )}
          >
            {cat.icon}
            {cat.label}
          </button>
        ))}
      </div>

      {/* Results */}
      <div className="overflow-y-auto max-h-[250px] px-1 pb-2 space-y-0.5">
        {filtered.length === 0 ? (
          <p className="px-3 py-6 text-center text-caption text-muted-foreground/40">
            {query ? 'No results' : 'Select a category above'}
          </p>
        ) : (
          filtered.map((item, i) => {
            const cat = CATEGORIES.find(c => c.category === item.category)
            return (
              <button
                key={`${item.category}-${item.label}-${i}`}
                onClick={() => {
                  onAdd({
                    id: `${item.category}-${Date.now()}`,
                    category: item.category,
                    label: item.label,
                    value: item.label.toLowerCase().replace(/\s+/g, '-'),
                  })
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-small text-foreground hover:bg-hover transition-all text-left"
              >
                <span className={cn('shrink-0', cat?.color)}>{cat?.icon}</span>
                <span className="flex-1 truncate">{item.label}</span>
                <span className="text-caption text-muted-foreground/40 shrink-0">{cat?.label}</span>
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}
