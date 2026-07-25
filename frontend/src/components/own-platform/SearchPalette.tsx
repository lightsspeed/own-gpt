import { useState, useRef, useEffect, useCallback } from 'react'
import { Search, MessageSquare, FileText, Code, Wrench, Hash, Command } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/features/chat/services/chatApi'

const searchCache = new Map<string, { results: SearchResult[]; total: number }>()
const MAX_CACHE = 50

interface SearchResult {
  session_id: string
  session_title: string
  match_type: 'title' | 'message'
  preview: string
  timestamp: string
}

interface SearchPaletteProps {
  open: boolean
  onClose: () => void
  onSelect: (sessionId: string) => void
  onNewChat: () => void
}

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'title', label: 'Conversations' },
  { key: 'message', label: 'Messages' },
]

function highlightText(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx === -1) return text
  return (
    <>
      {text.slice(0, idx)}
      <mark className="bg-primary/20 text-foreground rounded-sm px-0.5">{text.slice(idx, idx + query.length)}</mark>
      {text.slice(idx + query.length)}
    </>
  )
}

export function SearchPalette({ open, onClose, onSelect, onNewChat }: SearchPaletteProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [filter, setFilter] = useState('all')
  const [loading, setLoading] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  const doSearch = useCallback(async (q: string, f: string) => {
    if (!q.trim()) { setResults([]); return }
    const key = `${q}:${f}`
    const cached = searchCache.get(key)
    if (cached) { setResults(cached.results); return }
    setLoading(true)
    const data = await api.search(q, f, 20)
    const results = data.results || []
    if (searchCache.size >= MAX_CACHE) {
      const firstKey = searchCache.keys().next().value
      if (firstKey) searchCache.delete(firstKey)
    }
    searchCache.set(key, { results, total: data.total })
    setResults(results)
    setLoading(false)
    setSelectedIdx(0)
  }, [])

  useEffect(() => {
    if (!open) { setQuery(''); setResults([]); return }
    inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSearch(query, filter), 200)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [query, filter, doSearch])

  useEffect(() => {
    if (!open) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIdx(i => Math.min(i + 1, results.length - 1)) }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSelectedIdx(i => Math.max(i - 1, 0)) }
      if (e.key === 'Enter' && results[selectedIdx]) {
        onSelect(results[selectedIdx].session_id)
        onClose()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [open, results, selectedIdx, onClose, onSelect])

  useEffect(() => {
    if (!open) return
    const handleGlobal = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', handleGlobal)
    return () => window.removeEventListener('keydown', handleGlobal)
  }, [open, onClose])

  if (!open) return null

  const showEmpty = query.trim() && !loading && results.length === 0
  const showInitial = !query.trim()

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]" onClick={onClose}>
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />

      <div
        className="relative w-full max-w-[600px] rounded-2xl border border-border/40 bg-elevated/95 backdrop-blur-xl shadow-2xl overflow-hidden animate-scale-in"
        onClick={e => e.stopPropagation()}
        style={{ transformOrigin: 'top center' }}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border/10">
          <Search size={16} className="shrink-0 text-muted-foreground/50" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search conversations, messages, code..."
            className="flex-1 bg-transparent text-[15px] text-foreground placeholder:text-muted-foreground/35 outline-none"
          />
          <kbd className="text-[10px] font-medium text-muted-foreground/30 bg-muted/10 px-1.5 py-0.5 rounded border border-border/30 shrink-0">
            <Command size={10} className="inline -mt-0.5" />K
          </kbd>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-1 px-4 py-2 border-b border-border/5">
          {FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={cn(
                'px-2.5 py-1 rounded-md text-[11px] font-medium transition-all',
                filter === f.key
                  ? 'bg-primary/[0.1] text-primary'
                  : 'text-muted-foreground/50 hover:text-foreground hover:bg-white/[0.04]',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Results */}
        <div className="max-h-[360px] overflow-y-auto">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <div className="w-5 h-5 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
            </div>
          )}

          {showEmpty && (
            <div className="py-8 text-center">
              <Search size={28} className="mx-auto text-muted-foreground/20 mb-2" />
              <p className="text-small text-muted-foreground/50">No results for "<span className="text-foreground/60">{query}</span>"</p>
              <div className="flex flex-wrap justify-center gap-1.5 mt-3">
                {['Terraform', 'Kubernetes', 'Docker', 'RAG', 'API'].map(s => (
                  <button key={s} onClick={() => setQuery(s)} className="px-2 py-1 rounded-md text-[11px] bg-white/[0.04] text-muted-foreground/60 hover:text-foreground hover:bg-white/[0.07] transition-all">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {showInitial && (
            <div className="py-8 text-center">
              <Command size={32} className="mx-auto text-muted-foreground/15 mb-2" />
              <p className="text-small text-muted-foreground/40">Search across all conversations</p>
              <div className="flex items-center justify-center gap-4 mt-3 text-[10px] text-muted-foreground/30">
                <span className="flex items-center gap-1"><MessageSquare size={12} /> Conversations</span>
                <span className="flex items-center gap-1"><FileText size={12} /> Messages</span>
                <span className="flex items-center gap-1"><Code size={12} /> Code</span>
                <span className="flex items-center gap-1"><Wrench size={12} /> Tools</span>
              </div>
            </div>
          )}

          {results.map((r, i) => (
            <button
              key={`${r.session_id}-${r.match_type}-${i}`}
              onClick={() => { onSelect(r.session_id); onClose() }}
              onMouseEnter={() => setSelectedIdx(i)}
              className={cn(
                'w-full flex items-start gap-3 px-4 py-2.5 text-left transition-colors',
                i === selectedIdx ? 'bg-primary/[0.06]' : 'hover:bg-white/[0.03]',
              )}
            >
              <span className={cn(
                'mt-0.5 shrink-0',
                r.match_type === 'title' ? 'text-muted-foreground/40' : 'text-primary/60',
              )}>
                {r.match_type === 'title' ? <MessageSquare size={14} /> : <Hash size={14} />}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-medium text-foreground/80 truncate">{r.session_title}</span>
                  <span className={cn(
                    'text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0',
                    r.match_type === 'title' ? 'bg-primary/[0.06] text-primary/60' : 'bg-muted/10 text-muted-foreground/50',
                  )}>
                    {r.match_type === 'title' ? 'Conversation' : 'Message'}
                  </span>
                </div>
                <p className="text-[12px] text-muted-foreground/60 mt-0.5 line-clamp-2">
                  {highlightText(r.preview, query)}
                </p>
              </div>
            </button>
          ))}
        </div>

        {/* Footer */}
        {results.length > 0 && (
          <div className="px-4 py-2 border-t border-border/10 flex items-center justify-between text-[10px] text-muted-foreground/30">
            <span>{results.length} result{results.length !== 1 ? 's' : ''}</span>
            <span>↑↓ navigate · enter open · esc close</span>
          </div>
        )}
      </div>
    </div>
  )
}
