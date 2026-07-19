import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Card } from "@/components/ui/card";
import { Globe, BookOpen, Zap, FileText, Copy, Check, ExternalLink } from 'lucide-react';

interface ToolCall {
  name: string;
  status: 'calling' | 'done';
}

export interface ResourceItem {
  type: 'web' | 'file';
  title: string;
  url?: string;
  snippet?: string;
}

export interface MessageData {
  id: string;
  role: 'user' | 'assistant' | 'tool_event';
  content: string;
  tool?: ToolCall;
  timestamp?: Date;
  resources?: ResourceItem[];
  images?: string[]; // preview data URLs for display
}

const TOOL_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  search_knowledge_base: {
    label: 'Knowledge Base',
    icon: <BookOpen size={12} />,
    color: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  },
  search_web: {
    label: 'Web Search',
    icon: <Globe size={12} />,
    color: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
  },
  remember_user_fact: {
    label: 'Saving Memory',
    icon: <Zap size={12} />,
    color: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
  },
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={copy}
      className="absolute top-2 right-2 p-1.5 rounded-md bg-blue-500/10 hover:bg-blue-500/25 text-white/50 hover:text-blue-300 transition-all"
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
    </button>
  );
}

function SourceCard({ res, index }: { res: ResourceItem; index: number }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const isWeb = res.type === 'web';
  const shortTitle = isWeb
    ? (res.url ? new URL(res.url).hostname.replace('www.', '') : res.title)
    : res.title;

  const inner = (
    <div
      className="relative"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium cursor-pointer transition-all select-none max-w-[220px]
        ${ isWeb
          ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300 hover:bg-emerald-500/20 hover:border-emerald-500/40'
          : 'bg-blue-500/10 border-blue-500/20 text-blue-300 hover:bg-blue-500/20 hover:border-blue-500/40'
        }`}
      >
        {isWeb
          ? <Globe size={11} className="flex-shrink-0" />
          : <FileText size={11} className="flex-shrink-0" />
        }
        <span className="truncate">{shortTitle}</span>
        {isWeb && <ExternalLink size={10} className="flex-shrink-0 opacity-50" />}
      </div>

      {/* Hover Tooltip Preview */}
      {showTooltip && res.snippet && (
        <div className="absolute bottom-full left-0 mb-2 z-50 w-64 pointer-events-none animate-in fade-in slide-in-from-bottom-1 duration-150">
          <div className="bg-[#1a1b1e] border border-white/10 rounded-xl shadow-2xl overflow-hidden">
            {/* Header */}
            <div className={`flex items-center gap-2 px-3 py-2 border-b border-white/5
              ${ isWeb ? 'bg-emerald-500/10' : 'bg-blue-500/10' }`}
            >
              {isWeb
                ? <Globe size={12} className="text-emerald-400 flex-shrink-0" />
                : <FileText size={12} className="text-blue-400 flex-shrink-0" />
              }
              <span className="text-xs font-semibold text-white/80 truncate">{shortTitle}</span>
            </div>
            {/* Snippet */}
            <div className="px-3 py-2.5">
              <p className="text-[11px] text-white/60 leading-relaxed line-clamp-4">{res.snippet}</p>
            </div>
          </div>
          {/* Arrow */}
          <div className="absolute left-4 bottom-[-5px] w-2.5 h-2.5 bg-[#1a1b1e] border-r border-b border-white/10 rotate-45" />
        </div>
      )}
    </div>
  );

  if (isWeb && res.url) {
    return <a key={index} href={res.url} target="_blank" rel="noopener noreferrer">{inner}</a>;
  }
  return <div key={index}>{inner}</div>;
}

export function ChatMessage({ role, content, tool, timestamp, resources, images }: MessageData) {
  // Tool event pill – shown inline between messages
  if (role === 'tool_event' && tool) {
    const meta = TOOL_META[tool.name] || {
      label: tool.name.replace(/_/g, ' '),
      icon: <Zap size={12} />,
      color: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    };
    return (
      <div className="flex justify-center my-1.5">
        <div className={`flex items-center gap-1.5 text-xs px-3 py-1 rounded-full border ${meta.color} animate-in fade-in duration-300`}>
          {meta.icon}
          <span className="font-medium">{meta.label}</span>
          {tool.status === 'calling' && (
            <span className="ml-1 flex gap-0.5">
              <span className="w-1 h-1 bg-current rounded-full animate-bounce" />
              <span className="w-1 h-1 bg-current rounded-full animate-bounce" style={{ animationDelay: '0.15s' }} />
              <span className="w-1 h-1 bg-current rounded-full animate-bounce" style={{ animationDelay: '0.3s' }} />
            </span>
          )}
          {tool.status === 'done' && <span className="ml-1 opacity-60">✓</span>}
        </div>
      </div>
    );
  }

  const isUser = role === 'user';

  return (
    <div className={`flex w-full group ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`w-full max-w-[95%] space-y-2 flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        {isUser ? (
          <div className="flex flex-col items-end gap-2 max-w-[85%]">
            {/* Image previews */}
            {images && images.length > 0 && (
              <div className="flex flex-wrap gap-2 justify-end">
                {images.map((src, i) => (
                  <img
                    key={i}
                    src={src}
                    alt={`attachment-${i}`}
                    className="max-w-[200px] max-h-[200px] rounded-2xl object-cover border border-white/10 shadow-lg"
                  />
                ))}
              </div>
            )}
            {content && (
              <div className="bg-[#1e1f20] px-5 py-3 rounded-3xl text-[15px] text-gray-200 shadow-sm leading-relaxed border border-white/5">
                {content}
              </div>
            )}
          </div>
        ) : (
          <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 w-full">
            <div className="
              prose prose-invert prose-sm max-w-[95%]
              prose-p:my-3 prose-p:leading-relaxed prose-p:text-gray-300 prose-p:text-[15px]
              prose-headings:text-gray-100 prose-headings:font-semibold
              prose-h1:text-xl prose-h1:mt-5 prose-h1:mb-3
              prose-h2:text-lg prose-h2:mt-5 prose-h2:mb-2
              prose-h3:text-[16px] prose-h3:mt-4 prose-h3:mb-2
              prose-strong:text-gray-100 prose-strong:font-semibold
              prose-em:text-gray-300/80
              prose-ul:my-3 prose-ul:pl-6 prose-ul:space-y-2 prose-ul:list-[circle]
              prose-ol:my-3 prose-ol:pl-6 prose-ol:space-y-2
              prose-li:text-gray-300 prose-li:text-[15px] prose-li:marker:text-gray-400
              prose-blockquote:border-l-gray-600 prose-blockquote:text-gray-400 prose-blockquote:not-italic
              prose-code:text-blue-300 prose-code:bg-blue-950/60 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[13px] prose-code:font-mono prose-code:before:content-none prose-code:after:content-none
              prose-pre:bg-transparent prose-pre:p-0 prose-pre:m-0 prose-pre:my-4
              prose-hr:border-white/10 prose-hr:my-5
              prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline
              prose-table:text-[15px] prose-th:text-gray-200 prose-td:text-gray-300/80
            ">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ node, className, children, ...props }: any) {
                    const match = /language-(\w+)/.exec(className || '');
                    const codeString = String(children).replace(/\n$/, '');
                    const isBlock = match || codeString.includes('\n');
                    if (isBlock) {
                      return (
                        <div className="relative my-3 rounded-xl overflow-hidden border border-blue-500/20">
                          <div className="flex items-center justify-between px-4 py-1.5 bg-blue-950/60 border-b border-blue-500/10">
                            <span className="text-xs text-blue-300/60 font-mono">{match ? match[1] : 'code'}</span>
                            <CopyButton text={codeString} />
                          </div>
                          <SyntaxHighlighter
                            style={oneDark}
                            language={match ? match[1] : 'text'}
                            PreTag="div"
                            customStyle={{
                              margin: 0,
                              padding: '1rem',
                              background: 'rgba(0,0,0,0.4)',
                              fontSize: '0.8rem',
                              lineHeight: '1.6',
                            }}
                            {...props}
                          >
                            {codeString}
                          </SyntaxHighlighter>
                        </div>
                      );
                    }
                    return (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                  // Render horizontal rules as proper dividers
                  hr: () => <hr className="border-white/10 my-4" />,
                  // Open links in new tab
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

            {/* Resources Section */}
            {resources && resources.length > 0 && (
              <div className="mt-4 pt-3 border-t border-white/5">
                <span className="text-xs text-muted-foreground/60 mb-2 font-medium flex items-center gap-1.5">
                  <BookOpen size={11} /> Sources
                </span>
                <div className="flex flex-wrap gap-2 mt-1">
                  {resources.map((res, i) => (
                    <SourceCard key={i} res={res} index={i} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {timestamp && (
          <span className="text-xs text-muted-foreground opacity-0 group-hover:opacity-60 transition-opacity px-1">
            {timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>
    </div>
  );
}
