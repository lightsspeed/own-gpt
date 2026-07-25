import { useState, useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'
import { Copy, Check, ThumbsUp, ThumbsDown, Edit3, Ellipsis, Globe, ExternalLink, RefreshCw, ChevronDown } from 'lucide-react'
import type { ResourceItem, EvidenceItem } from '@/features/chat/types'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { MarkdownRenderer } from './MarkdownRenderer'
import { EvidenceBar } from './EvidenceBar'
import { EvidenceDrawer } from './EvidenceDrawer'

const COLLAPSE_THRESHOLD = 600

interface MessageBubbleProps {
  role: 'user' | 'assistant' | 'system'
  content: string
  isStreaming?: boolean
  resources?: ResourceItem[]
  evidence?: EvidenceItem[]
  answerMode?: string
  onOpenSources?: (resources: ResourceItem[]) => void
  onEdit?: (content: string) => void
  onRegenerate?: () => void
}

export function MessageBubble({ role, content, isStreaming, resources, evidence, answerMode, onOpenSources, onEdit, onRegenerate }: MessageBubbleProps) {
  const isUser = role === 'user'
  const [showActions, setShowActions] = useState(false)
  const [collapsed, setCollapsed] = useState(true)
  const [drawerItem, setDrawerItem] = useState<EvidenceItem | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

  const evidenceItems = evidence || []
  const drawerIndex = drawerItem ? evidenceItems.indexOf(drawerItem) : -1

  useEffect(() => {
    if (isUser) {
      setShowActions(true)
      return
    }
    if (isStreaming || !content) {
      setShowActions(false)
      if (timerRef.current) clearTimeout(timerRef.current)
    } else {
      timerRef.current = setTimeout(() => setShowActions(true), 1000)
    }
    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [isStreaming, content, isUser])

  if (role === 'system') {
    return (
      <div className="flex justify-center py-3">
        <p className="text-small text-muted-foreground/50 italic">{content}</p>
      </div>
    )
  }

  return (
    <div className={cn('flex flex-col group', isUser ? 'items-end' : 'items-start')}>
      {/* Answer mode badge */}
      {!isUser && answerMode && !isStreaming && (
        <div className="flex items-center gap-2 px-1 mb-2">
          <span className={cn(
            'inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium uppercase tracking-wider',
            answerMode === 'web' && 'bg-info/10 text-info/80',
            answerMode === 'grounded' && 'bg-success/10 text-success/80',
            answerMode === 'hybrid' && 'bg-warning/10 text-warning/80',
            answerMode === 'synthesis' && 'bg-primary/10 text-primary/80',
            !['web', 'grounded', 'hybrid', 'synthesis'].includes(answerMode) && 'bg-muted/10 text-muted-foreground/60',
          )}>
            {answerMode === 'web' && '🌐'}
            {answerMode === 'grounded' && '📚'}
            {answerMode === 'hybrid' && '🔀'}
            {answerMode === 'synthesis' && '✨'}
            {answerMode === 'web' ? 'Web Search' : answerMode === 'grounded' ? 'Grounded' : answerMode === 'hybrid' ? 'Hybrid' : answerMode === 'synthesis' ? 'Synthesis' : answerMode}
          </span>
        </div>
      )}

      {/* Message content */}
      <div
        className={cn(
          'px-4 py-2.5 max-w-[85%] text-body text-foreground',
          isUser
            ? 'bg-primary/15 rounded-2xl rounded-br-md'
            : 'px-1',
        )}
      >
        <div className={cn('relative overflow-hidden transition-all duration-300', isLong && collapsed ? 'max-h-[300px]' : 'max-h-[99999px]')}>
          <MarkdownRenderer content={content} />

          {isLong && collapsed && (
            <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-[#000] to-transparent pointer-events-none" />
          )}
        </div>
        {isLong && (
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="flex items-center gap-1 text-caption text-muted-foreground/50 hover:text-muted-foreground transition-colors mt-1"
          >
            <ChevronDown size={12} className={cn('transition-transform', !collapsed && 'rotate-180')} />
            {collapsed ? 'Show more' : 'Show less'}
          </button>
        )}

        {/* Evidence sources - only for non-streaming non-user messages */}
        {!isUser && !isStreaming && evidenceItems.length > 0 && (
          <EvidenceBar items={evidenceItems} onSelect={setDrawerItem} />
        )}
      </div>

      {/* Actions */}
      {showActions && (
        <div className={cn('flex items-center gap-1 pt-1 opacity-0 group-hover:opacity-100 transition-opacity', isUser ? 'flex-row-reverse' : 'flex-row')}>
          {isUser ? (
            <UserActions content={content} onEdit={onEdit} />
          ) : (
            <AssistantActions content={content} resources={resources} onOpenSources={onOpenSources} onRegenerate={onRegenerate} />
          )}
        </div>
      )}

      {/* Evidence Drawer */}
      <EvidenceDrawer
        item={drawerItem}
        onClose={() => setDrawerItem(null)}
        onNavigate={(dir) => {
          const idx = evidenceItems.indexOf(drawerItem!)
          const next = dir === 'next' ? idx + 1 : idx - 1
          if (next >= 0 && next < evidenceItems.length) {
            setDrawerItem(evidenceItems[next])
          }
        }}
        hasPrev={drawerIndex > 0}
        hasNext={drawerIndex < evidenceItems.length - 1}
      />
    </div>
  )
}

function UserActions({ content, onEdit }: { content: string; onEdit?: (content: string) => void }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <>
      {onEdit && (
        <button onClick={() => onEdit(content)} className="p-1.5 rounded-lg text-muted-foreground/40 hover:text-foreground hover:bg-hover transition-all" title="Edit">
          <Edit3 size={14} />
        </button>
      )}
      <button onClick={handleCopy} className="p-1.5 rounded-lg text-muted-foreground/40 hover:text-foreground hover:bg-hover transition-all" title="Copy">
        {copied ? <Check size={14} className="text-success" /> : <Copy size={14} />}
      </button>
    </>
  )
}

function AssistantActions({ content, resources, onOpenSources, onRegenerate }: {
  content: string
  resources?: ResourceItem[]
  onOpenSources?: (resources: ResourceItem[]) => void
  onRegenerate?: () => void
}) {
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <>
      {onRegenerate && (
        <button onClick={onRegenerate} className="p-1.5 rounded-lg text-muted-foreground/40 hover:text-foreground hover:bg-hover transition-all" title="Regenerate">
          <RefreshCw size={14} />
        </button>
      )}
      <button onClick={handleCopy} className="p-1.5 rounded-lg text-muted-foreground/40 hover:text-foreground hover:bg-hover transition-all" title="Copy">
        {copied ? <Check size={14} className="text-success" /> : <Copy size={14} />}
      </button>
      <button
        onClick={() => setFeedback(feedback === 'up' ? null : 'up')}
        className={cn('p-1.5 rounded-lg transition-all', feedback === 'up' ? 'text-success' : 'text-muted-foreground/40 hover:text-foreground hover:bg-hover')}
        title="Good response"
      >
        <ThumbsUp size={14} />
      </button>
      <button
        onClick={() => setFeedback(feedback === 'down' ? null : 'down')}
        className={cn('p-1.5 rounded-lg transition-all', feedback === 'down' ? 'text-danger' : 'text-muted-foreground/40 hover:text-foreground hover:bg-hover')}
        title="Bad response"
      >
        <ThumbsDown size={14} />
      </button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button className="p-1.5 rounded-lg text-muted-foreground/40 hover:text-foreground hover:bg-hover transition-all" title="More">
            <Ellipsis size={14} />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" side="top" className="bg-popover w-[180px] rounded-xl border p-1.5 shadow-xl">
          {resources && resources.length > 0 && (
            <DropdownMenuItem className="flex items-center gap-2.5 rounded-lg p-2 text-small cursor-pointer" onSelect={() => onOpenSources?.(resources)}>
              <Globe size={14} /> Sources
            </DropdownMenuItem>
          )}
          <DropdownMenuItem className="flex items-center gap-2.5 rounded-lg p-2 text-small cursor-pointer">
            <ExternalLink size={14} /> Share
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  )
}