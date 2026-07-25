import React, { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Check, Copy } from 'lucide-react'
import { useCopy } from '@/hooks/useCopy'

interface MarkdownRendererProps {
  content: string
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  const { copied, copy } = useCopy()

  return (
    <div className="relative my-3 rounded-xl overflow-hidden border border-border">
      <div className="flex items-center justify-between bg-elevated px-4 py-1.5 border-b border-border">
        <span className="text-caption font-mono text-muted-foreground">{language}</span>
        <button
          onClick={() => copy(code)}
          className={`flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-all ${
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

export const MarkdownRenderer = React.memo(function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const rendered = useMemo(() => (
    <div className="prose prose-invert max-w-none prose-headings:text-foreground prose-headings:font-semibold prose-p:text-foreground/90 prose-p:leading-relaxed prose-a:text-primary prose-a:no-underline hover:prose-a:underline prose-strong:text-foreground prose-code:text-primary prose-code:bg-muted/50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-small prose-pre:bg-transparent prose-pre:p-0 prose-pre:m-0 prose-pre:my-4 prose-pre:border-none prose-li:text-foreground/90 prose-hr:border-border prose-blockquote:border-l-primary prose-blockquote:text-muted-foreground prose-table:text-body prose-th:text-foreground prose-td:text-muted-foreground">
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
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  ), [content])

  return rendered
})
