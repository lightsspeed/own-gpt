import React, { useMemo, useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Check, Copy } from 'lucide-react'
import { useCopy } from '@/hooks/useCopy'
import type { ResourceItem } from '@/features/chat/types'
import { InlineCitationText, groupKey, type CitationOpen } from './inline-citation/InlineCitation'
import { buildCiteGroups, type CiteGroup, type CitationToken } from './inline-citation/CitationMarker'
import { useCoarsePointer } from './inline-citation/useCoarsePointer'

interface MarkdownRendererProps {
  content: string
  /** Sources available for inline `[Chunk N]` / `[N]` citation pills.
   *  Omit (or pass empty) to render markers as plain text — always the case
   *  for user messages, live streaming content, and PDF/print exports. */
  resources?: ResourceItem[]
}

const HOVER_OPEN_DELAY_MS = 0
const HOVER_CLOSE_DELAY_MS = 150

function CodeBlock({ language, code }: { language: string; code: string }) {
  const { copied, copy } = useCopy()

  return (
    <div className="relative my-3 rounded-xl overflow-hidden border border-border">
      <div className="flex items-center justify-between bg-elevated px-4 py-1.5 border-b border-border">
        <span className="text-caption font-mono text-muted-foreground">{language}</span>
        <button
          onClick={() => copy(code)}
          className={`flex items-center gap-1 rounded-md px-2 py-1 text-caption font-medium transition-all ${
            copied ? 'text-success' : 'text-muted-foreground hover:text-foreground hover:bg-hover'
          }`}
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <SyntaxHighlighter
        style={oneDark}
        language={language}
        PreTag="div"
        customStyle={{
          margin: 0,
          padding: '1rem',
          background: 'rgba(0,0,0,0.3)',
          fontSize: '0.8rem',
          lineHeight: '1.6',
        }}
        showLineNumbers={code.split('\n').length > 3}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}

const MemoCodeBlock = React.memo(CodeBlock)

// Inline elements whose text content must stay byte-for-byte literal.
const LITERAL_INLINE_TAGS = new Set(['code', 'a', 'img', 'br', 'kbd', 'samp', 'var', 'sup', 'sub'])

export const MarkdownRenderer = React.memo(function MarkdownRenderer({ content, resources }: MarkdownRendererProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [open, setOpen] = useState<CitationOpen | null>(null)
  const coarse = useCoarsePointer()
  const variant: 'card' | 'sheet' = coarse ? 'sheet' : 'card'

  const groups = useMemo<CiteGroup[]>(() => buildCiteGroups(content, resources), [content, resources])
  const groupByKey = useMemo(() => {
    const map = new Map<string, CiteGroup>()
    for (const g of groups) map.set(groupKey(g), g)
    return map
  }, [groups])

  const clearHoverTimer = useCallback(() => {
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current)
      hoverTimerRef.current = null
    }
  }, [])

  const close = useCallback(() => setOpen(null), [])

  useEffect(() => () => clearHoverTimer(), [clearHoverTimer])

  const handleActivateKey = useCallback((key: string) => {
    clearHoverTimer()
    setOpen(prev => (prev?.key === key ? null : { key, index: 0 }))
  }, [clearHoverTimer])

  const handleHoverEnterKey = useCallback((key: string) => {
    clearHoverTimer()
    setOpen(prev => (prev?.key === key ? prev : { key, index: 0 }))
  }, [clearHoverTimer])

  const handleHoverLeaveKey = useCallback((key: string) => {
    clearHoverTimer()
    hoverTimerRef.current = setTimeout(() => {
      setOpen(prev => (prev?.key === key ? null : prev))
    }, HOVER_CLOSE_DELAY_MS)
  }, [clearHoverTimer])

  const handleNavigate = useCallback((delta: number) => {
    setOpen(prev => {
      if (!prev) return prev
      const size = groupByKey.get(prev.key)?.sources.length ?? 1
      return { key: prev.key, index: (prev.index + delta + size) % size }
    })
  }, [groupByKey])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        setOpen(null)
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        handleNavigate(-1)
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        handleNavigate(1)
      }
    }
    const onPointerDown = (e: PointerEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(null)
      }
    }
    window.addEventListener('keydown', onKey, true)
    window.addEventListener('pointerdown', onPointerDown, true)
    return () => {
      window.removeEventListener('keydown', onKey, true)
      window.removeEventListener('pointerdown', onPointerDown, true)
    }
  }, [open, handleNavigate])

  const rendered = useMemo(() => {
    const hoverEnabled = variant === 'card'
    const CitationAware = ({ children }: { children?: React.ReactNode }) => {
      if (groups.length === 0) return <>{children}</>
      return enhanceChildren(children, {
        groups,
        open,
        onActivateKey: handleActivateKey,
        onHoverEnterKey: hoverEnabled ? handleHoverEnterKey : () => {},
        onHoverLeaveKey: hoverEnabled ? handleHoverLeaveKey : () => {},
        onNavigate: handleNavigate,
        onClose: close,
        variant,
      })
    }

    return (
      <div
        ref={containerRef}
        className="prose prose-invert max-w-none prose-headings:text-foreground prose-headings:font-semibold prose-p:text-foreground/90 prose-p:leading-relaxed prose-a:text-primary prose-a:no-underline hover:prose-a:underline prose-strong:text-foreground prose-code:text-primary prose-code:bg-muted/50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-small prose-pre:bg-transparent prose-pre:p-0 prose-pre:m-0 prose-pre:my-4 prose-pre:border-none prose-li:text-foreground/90 prose-hr:border-border prose-blockquote:border-l-primary prose-blockquote:text-muted-foreground prose-table:text-body prose-th:text-foreground prose-td:text-muted-foreground"
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({ className, children, ...props }: any) {
              const match = /language-(\w+)/.exec(className || '')
              const code = String(children).replace(/\n$/, '')
              const isBlock = match || code.includes('\n')
              if (isBlock) {
                return <MemoCodeBlock language={match?.[1] || 'text'} code={code} />
              }
              return (
                <code className={className} {...props}>
                  {children}
                </code>
              )
            },
            a: ({ href, children, ...props }: any) => (
              <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                {children}
              </a>
            ),
            p: CitationAware,
            li: CitationAware,
            h1: CitationAware,
            h2: CitationAware,
            h3: CitationAware,
            h4: CitationAware,
            h5: CitationAware,
            h6: CitationAware,
            blockquote: CitationAware,
            td: CitationAware,
            th: CitationAware,
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    )
  }, [content, groups, open, variant, handleActivateKey, handleHoverEnterKey, handleHoverLeaveKey, handleNavigate, close])

  return rendered
})

interface EnhanceContext {
  groups: CiteGroup[]
  open: CitationOpen | null
  onActivateKey: (key: string) => void
  onHoverEnterKey: (key: string) => void
  onHoverLeaveKey: (key: string) => void
  onNavigate: (delta: number) => void
  onClose: () => void
  variant: 'card' | 'sheet'
}

function enhanceChildren(children: React.ReactNode, ctx: EnhanceContext): React.ReactNode {
  if (typeof children === 'string') {
    if (ctx.groups.length === 0) return children
    return (
      <InlineCitationText
        text={children}
        groups={ctx.groups}
        open={ctx.open}
        onActivateKey={ctx.onActivateKey}
        onHoverEnterKey={ctx.onHoverEnterKey}
        onHoverLeaveKey={ctx.onHoverLeaveKey}
        onNavigate={ctx.onNavigate}
        onClose={ctx.onClose}
        variant={ctx.variant}
      />
    )
  }
  if (Array.isArray(children)) {
    return children.map((child, i) => (
      <React.Fragment key={i}>{enhanceChildren(child, ctx)}</React.Fragment>
    ))
  }
  if (React.isValidElement(children)) {
    const el = children as React.ReactElement<{ children?: React.ReactNode }>
    const tag = typeof el.type === 'string' ? el.type : ''
    if (tag && LITERAL_INLINE_TAGS.has(tag)) return el
    return React.cloneElement(el, undefined, enhanceChildren(el.props.children, ctx))
  }
  return children
}