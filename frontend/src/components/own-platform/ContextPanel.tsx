import { cn } from '@/lib/utils'
import { X, Globe, FileText, ExternalLink } from 'lucide-react'
import type { ResourceItem } from '@/features/chat/types'

interface ContextPanelProps {
  open: boolean
  onClose: () => void
  sources?: ResourceItem[]
}

function SourceLogo({ type, title }: { type: string; title: string }) {
  if (type === 'web') {
    try {
      const hostname = new URL(title).hostname
      return (
        <div className="w-8 h-8 rounded-lg bg-surface border border-border flex items-center justify-center overflow-hidden shrink-0">
          <img
            src={`https://www.google.com/s2/favicons?domain=${hostname}&sz=32`}
            alt=""
            className="w-5 h-5"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
        </div>
      )
    } catch {
      return (
        <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center shrink-0">
          <Globe size={16} className="text-sky-400" />
        </div>
      )
    }
  }
  return (
    <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0">
      <FileText size={16} className="text-blue-400" />
    </div>
  )
}

export function ContextPanel({ open, onClose, sources }: ContextPanelProps) {
  const hasSources = sources && sources.length > 0

  return (
    <>
      {open && (
        <div className="fixed inset-0 z-50 bg-black/40" onClick={onClose} />
      )}
      <div
        className={cn(
          'fixed right-0 top-0 h-full w-[400px] bg-surface border-l border-border z-[60] shadow-2xl transition-transform duration-300',
          open ? 'translate-x-0' : 'translate-x-full',
        )}
      >
        <div className="h-full flex flex-col">
          {/* Header */}
          <div className="h-16 flex items-center justify-between px-5 border-b border-border shrink-0">
            <div className="flex items-center gap-3">
              <FileText size={18} className="text-primary" />
              <span className="text-small font-bold text-foreground">
                {hasSources ? `Sources (${sources.length})` : 'Sources'}
              </span>
            </div>
            <button onClick={onClose} className="p-2 text-muted-foreground hover:text-foreground transition-colors rounded-lg">
              <X size={18} />
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
            {hasSources ? (
              <div className="space-y-2">
                {sources.map((r, i) => (
                  <div
                    key={i}
                    onClick={() => r.url && window.open(r.url, '_blank')}
                    className="flex items-center gap-3 p-3 rounded-xl bg-muted/50 border border-border/50 hover:bg-hover hover:border-primary/30 transition-all cursor-pointer group"
                  >
                    <SourceLogo type={r.type} title={r.title} />
                    <div className="flex-1 min-w-0">
                      <p className="text-small text-foreground truncate group-hover:text-primary transition-colors">{r.title}</p>
                      {r.snippet && (
                        <p className="text-caption text-muted-foreground/60 mt-0.5 line-clamp-2">{r.snippet}</p>
                      )}
                    </div>
                    <ExternalLink size={14} className="text-muted-foreground/30 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center">
                <p className="text-small text-muted-foreground/40">No sources available</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
