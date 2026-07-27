import React, { useState, useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'
import { Copy, Check, ThumbsUp, ThumbsDown, Edit3, Ellipsis, ExternalLink, RefreshCw } from 'lucide-react'
import type { ResourceItem } from '@/features/chat/types'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { MarkdownRenderer } from './MarkdownRenderer'

interface MessageBubbleProps {
  role: 'user' | 'assistant' | 'system'
  content: string
  isStreaming?: boolean
  resources?: ResourceItem[]
  answerMode?: string
  onEdit?: (content: string) => void
  onRegenerate?: () => void
}

export const MessageBubble = React.memo(function MessageBubble({ role, content, isStreaming, resources, answerMode, onEdit, onRegenerate }: MessageBubbleProps) {
  const isUser = role === 'user'
  const [showActions, setShowActions] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()

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
        <MarkdownRenderer content={content} />
      </div>

      {/* Actions */}
      {showActions && (
        <div className={cn('flex items-center gap-1 pt-1 opacity-0 group-hover:opacity-100 transition-opacity', isUser ? 'flex-row-reverse' : 'flex-row')}>
          {isUser ? (
            <UserActions content={content} onEdit={onEdit} />
          ) : (
            <AssistantActions content={content} onRegenerate={onRegenerate} />
          )}
        </div>
      )}
    </div>
  )
})

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

function AssistantActions({ content, onRegenerate }: { content: string; onRegenerate?: () => void }) {
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
          <DropdownMenuItem className="flex items-center gap-2.5 rounded-lg p-2 text-small cursor-pointer">
            <ExternalLink size={14} /> Share
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  )
}
