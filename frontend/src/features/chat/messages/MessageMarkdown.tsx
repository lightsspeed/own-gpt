import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CodeBlock } from './CodeBlock';
import { cn } from '@/lib/utils';

export interface MessageMarkdownProps {
  content: string;
  className?: string;
}

export function MessageMarkdown({ content, className }: MessageMarkdownProps) {
  return (
    <div className={cn(
      'prose prose-invert prose-sm max-w-none',
      'prose-p:my-3 prose-p:leading-relaxed prose-p:text-text-primary prose-p:text-body',
      'prose-headings:text-text-primary prose-headings:font-semibold',
      'prose-h1:text-h1 prose-h1:mt-6 prose-h1:mb-4',
      'prose-h2:text-h2 prose-h2:mt-6 prose-h2:mb-3',
      'prose-h3:text-h3 prose-h3:mt-5 prose-h3:mb-2',
      'prose-strong:text-text-primary prose-strong:font-semibold',
      'prose-em:text-text-primary/80',
      'prose-ul:my-3 prose-ul:pl-6 prose-ul:space-y-1.5',
      'prose-ol:my-3 prose-ol:pl-6 prose-ol:space-y-1.5',
      'prose-li:text-text-primary prose-li:text-body',
      'prose-blockquote:border-l-text-disabled prose-blockquote:text-text-secondary prose-blockquote:not-italic',
      'prose-code:text-accent prose-code:bg-accent/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-small prose-code:font-mono prose-code:before:content-none prose-code:after:content-none',
      'prose-pre:bg-transparent prose-pre:p-0 prose-pre:m-0 prose-pre:my-4',
      'prose-hr:border-border prose-hr:my-6',
      'prose-a:text-accent prose-a:no-underline hover:prose-a:underline',
      'prose-table:text-body prose-th:text-text-primary prose-td:text-text-secondary',
      className,
    )}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className: cName, children, ...props }: any) {
            const match = /language-(\w+)/.exec(cName || '');
            const code = String(children).replace(/\n$/, '');
            const isBlock = match || code.includes('\n');
            if (isBlock) {
              return <CodeBlock language={match?.[1] || 'text'} code={code} />;
            }
            return (
              <code className={cName} {...props}>
                {children}
              </code>
            );
          },
          hr: () => <hr className="border-border my-6" />,
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
  );
}
