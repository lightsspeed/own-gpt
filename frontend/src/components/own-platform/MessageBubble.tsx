import React, { useState, useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'
import { Copy, Check, ThumbsUp, ThumbsDown, Edit3, Ellipsis, ExternalLink, FileText } from 'lucide-react'
import type { ResourceItem } from '@/features/chat/types'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { MarkdownRenderer } from './MarkdownRenderer'
import { api } from '@/features/chat/services/chatApi'

interface MessageBubbleProps {
  role: 'user' | 'assistant' | 'system'
  content: string
  isStreaming?: boolean
  resources?: ResourceItem[]
  recordId?: string
  sessionId?: string
  onEdit?: (content: string) => void
  onShowSources?: (sources: ResourceItem[]) => void
}

export const MessageBubble = React.memo(function MessageBubble({ role, content, isStreaming, resources, recordId, sessionId, onEdit, onShowSources }: MessageBubbleProps) {
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
      // Show immediately when streaming ends
      setShowActions(true)
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
            <AssistantActions
              content={content}
              resources={resources}
              recordId={recordId}
              sessionId={sessionId}
              onShowSources={onShowSources}
            />
          )}
        </div>
      )}
    </div>
  )
})

function UserActions({ content, onEdit }: { content: string; onEdit?: (content: string) => void }) {  const [copied, setCopied] = useState(false)

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

function AssistantActions({ content, resources, recordId, sessionId, onShowSources }: AssistantActionsProps) {
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
    if (recordId) api.sendEvent('copy', recordId, sessionId)
  }

  const handleFeedback = (thumb: 'up' | 'down') => {
    if (!recordId) return
    const next = feedback === thumb ? null : thumb
    setFeedback(next)
    api.sendThumb(recordId, next || 'none')
  }

  const hasResources = resources && resources.length > 0

  return (
    <>
      <button onClick={handleCopy} className="p-1.5 rounded-lg text-muted-foreground/40 hover:text-foreground hover:bg-hover transition-all" title="Copy">
        {copied ? <Check size={14} className="text-success" /> : <Copy size={14} />}
      </button>
      <button
        onClick={() => handleFeedback('up')}
        className={cn('p-1.5 rounded-lg transition-all', feedback === 'up' ? 'text-success' : 'text-muted-foreground/40 hover:text-foreground hover:bg-hover')}
        title="Good response"
      >
        <ThumbsUp size={14} />
      </button>
      <button
        onClick={() => handleFeedback('down')}
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
          {hasResources && onShowSources && (
            <DropdownMenuItem onClick={() => onShowSources(resources)} className="flex items-center gap-2.5 rounded-lg p-2 text-small cursor-pointer">
              <FileText size={14} /> Sources
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
