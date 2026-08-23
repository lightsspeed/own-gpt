import React, { useMemo, useState, useEffect, useRef, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Check, Copy } from 'lucide-react'
import { useCopy } from '@/hooks/useCopy'
import type { ResourceItem } from '@/features/chat/types'
import { InlineCitationText, groupKey, type CitationOpen } from './inline-citation/InlineCitation'
import { buildCiteGroups, normalizeContentAndResources, type CiteGroup, type CitationToken } from './inline-citation/CitationMarker'
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
  const isDark = typeof document !== 'undefined' ? document.documentElement.classList.contains('dark') : true

  return (
    <div className="code-block-wrapper relative my-3 rounded-xl overflow-hidden border border-border bg-elevated shadow-sm">
      <div className="flex items-center justify-between bg-muted/60 px-4 py-2 border-b border-border">
        <span className="text-xs font-mono text-muted-foreground uppercase font-semibold tracking-wider">{language || 'code'}</span>
        <button
          onClick={() => copy(code)}
          className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all ${
            copied
              ? 'bg-emerald-500/15 text-emerald-500 border border-emerald-500/30'
              : 'bg-hover/80 hover:bg-hover text-muted-foreground hover:text-foreground border border-border/50'
          }`}
        >
          {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <div className="code-block-content p-3.5 sm:p-4 overflow-x-auto text-xs sm:text-sm font-mono leading-relaxed">
        <SyntaxHighlighter
          style={isDark ? oneDark : oneLight}
          language={language || 'text'}
          PreTag="div"
          customStyle={{
            margin: 0,
            padding: 0,
            background: 'transparent',
            fontSize: '0.85rem',
            lineHeight: '1.6',
          }}
          showLineNumbers={code.split('\n').length > 3}
        >
          {code}
        </SyntaxHighlighter>
      </div>
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

  const { normalizedContent, effectiveResources } = useMemo(() => {
    const res = normalizeContentAndResources(content, resources)
    return { normalizedContent: res.normalizedContent, effectiveResources: res.resources }
  }, [content, resources])

  const groups = useMemo<CiteGroup[]>(() => buildCiteGroups(normalizedContent, effectiveResources), [normalizedContent, effectiveResources])
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
        className="w-full max-w-full markdown-body text-foreground"
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
                <code className="inline-code" {...props}>
                  {children}
                </code>
              )
            },
            a: ({ href, children, ...props }: any) => (
              <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                {children}
              </a>
            ),
            h1: ({ children, ...props }: any) => (
              <h1 className="md-h1" {...props}>
                <CitationAware>{children}</CitationAware>
              </h1>
            ),
            h2: ({ children, ...props }: any) => (
              <h2 className="md-h2" {...props}>
                <CitationAware>{children}</CitationAware>
              </h2>
            ),
            h3: ({ children, ...props }: any) => (
              <h3 className="md-h3" {...props}>
                <CitationAware>{children}</CitationAware>
              </h3>
            ),
            h4: ({ children, ...props }: any) => (
              <h4 className="md-h4" {...props}>
                <CitationAware>{children}</CitationAware>
              </h4>
            ),
            h5: ({ children, ...props }: any) => (
              <h5 className="font-semibold text-sm text-foreground my-2" {...props}>
                <CitationAware>{children}</CitationAware>
              </h5>
            ),
            h6: ({ children, ...props }: any) => (
              <h6 className="font-semibold text-xs text-muted-foreground uppercase tracking-wider my-2" {...props}>
                <CitationAware>{children}</CitationAware>
              </h6>
            ),
            p: ({ children, ...props }: any) => (
              <p className="my-2.5 leading-relaxed text-foreground" {...props}>
                <CitationAware>{children}</CitationAware>
              </p>
            ),
            ul: ({ children, ...props }: any) => (
              <ul className="my-3 space-y-1.5 pl-5 list-disc text-foreground" {...props}>
                {children}
              </ul>
            ),
            ol: ({ children, ...props }: any) => (
              <ol className="my-3 space-y-1.5 pl-5 list-decimal text-foreground" {...props}>
                {children}
              </ol>
            ),
            li: ({ children, ...props }: any) => (
              <li className="leading-relaxed my-1" {...props}>
                <CitationAware>{children}</CitationAware>
              </li>
            ),
            table: ({ children, ...props }: any) => (
              <div className="my-4 overflow-x-auto rounded-xl border border-border/60 bg-surface/40 dark:bg-elevated/40 shadow-xs">
                <table className="w-full border-collapse text-left text-sm" {...props}>
                  {children}
                </table>
              </div>
            ),
            thead: ({ children, ...props }: any) => (
              <thead className="bg-muted/50 text-xs font-semibold uppercase text-muted-foreground border-b border-border/60" {...props}>
                {children}
              </thead>
            ),
            tbody: ({ children, ...props }: any) => (
              <tbody className="divide-y divide-border/40" {...props}>
                {children}
              </tbody>
            ),
            tr: ({ children, ...props }: any) => (
              <tr className="hover:bg-hover/40 transition-colors" {...props}>
                {children}
              </tr>
            ),
            th: ({ children, ...props }: any) => (
              <th className="px-4 py-2.5 font-semibold text-xs text-muted-foreground uppercase tracking-wider text-left border-b border-border/60" {...props}>
                <CitationAware>{children}</CitationAware>
              </th>
            ),
            td: ({ children, ...props }: any) => (
              <td className="px-4 py-3 text-sm text-foreground/90 align-top border-b border-border/30" {...props}>
                <CitationAware>{children}</CitationAware>
              </td>
            ),
          }}
        >
          {normalizedContent}
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