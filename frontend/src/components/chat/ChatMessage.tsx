import React, { useState, memo } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark, oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Globe, BookOpen, Zap, Copy, Check, ThumbsUp, ThumbsDown, Edit2 } from 'lucide-react';
import { EvidencePanel } from '@/components/evidence';
import { Streamdown } from '@/components/streamdown';

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
  evidence?: any[];  // EvidenceItem[] from V3 Phase 5
  images?: string[];
  feedback?: 'liked' | 'disliked' | null;
  answerMode?: 'grounded' | 'hybrid' | 'synthesis' | 'web' | 'no_evidence';
  answerModeMetadata?: {
    chunk_count: number;
    doc_count: number;
    confidence: number;
    retrieval_method: string;
    retrieved_count?: number;
  };
}

export interface ChatMessageProps extends MessageData {
  onEdit?: (content: string) => void;
  onFeedback?: (id: string, feedback: 'liked' | 'disliked' | null) => void;
  isStreaming?: boolean;
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

  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
        copied
          ? 'bg-emerald-500/15 text-emerald-500 border border-emerald-500/30'
          : 'bg-hover/80 hover:bg-hover text-muted-foreground hover:text-foreground border border-border/50'
      }`}
      title="Copy code"
    >
      {copied ? (
        <>
          <Check size={12} className="text-emerald-500" />
          <span className="text-emerald-500">Copied!</span>
        </>
      ) : (
        <>
          <Copy size={12} />
          <span>Copy</span>
        </>
      )}
    </button>
  );
}

function MessageActionButton({ icon, label, active, onClick }: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  const [clicked, setClicked] = useState(false);

  return (
    <button
      onClick={() => {
        onClick?.();
        setClicked(true);
        setTimeout(() => setClicked(false), 600);
      }}
      title={label}
      className={`p-1.5 rounded-md transition-all active:scale-90 ${
        active
          ? 'bg-blue-500/20 text-blue-400'
          : clicked
            ? 'bg-white/10 text-white/70'
            : 'text-white/30 hover:text-white/70 hover:bg-white/5'
      }`}
    >
      {icon}
    </button>
  );
}

export const ChatMessage = memo(function ChatMessage({ id, role, content, tool, timestamp, resources, evidence, images, feedback, answerMode, answerModeMetadata, onEdit, onFeedback, isStreaming }: ChatMessageProps) {
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
      <div className={`w-full max-w-full space-y-2 flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
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
              <div className="bg-elevated px-5 py-3 rounded-3xl text-[15px] text-foreground shadow-sm leading-relaxed border border-border">
                {content}
              </div>
            )}
            {/* Question actions */}
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <MessageActionButton icon={<Copy size={12} />} label="Copy" onClick={() => navigator.clipboard.writeText(content)} />
              {onEdit && (
                <MessageActionButton icon={<Edit2 size={12} />} label="Edit" onClick={() => onEdit(content)} />
              )}
            </div>
          </div>
        ) : (
          <div className="w-full">
            {/* Streamdown per-word blurIn animation during streaming, zero DOM overhead when finished */}
            <div className="
              w-full max-w-full prose dark:prose-invert prose-sm text-foreground
              prose-p:my-2.5 prose-p:leading-relaxed prose-p:text-[15px] prose-p:text-foreground
              prose-headings:font-semibold prose-headings:text-foreground
              prose-h1:text-xl prose-h1:mt-5 prose-h1:mb-2.5 prose-h1:border-b prose-h1:border-border/40 prose-h1:pb-1.5
              prose-h2:text-lg prose-h2:mt-4 prose-h2:mb-2
              prose-h3:text-[15px] prose-h3:mt-3.5 prose-h3:mb-1.5
              prose-strong:font-semibold prose-strong:text-foreground
              prose-em:opacity-90 prose-em:text-foreground
              prose-ul:my-2.5 prose-ul:pl-5 prose-ul:space-y-1 prose-ul:list-disc
              prose-ol:my-2.5 prose-ol:pl-5 prose-ol:space-y-1 prose-ol:list-decimal
              prose-li:text-[15px] prose-li:leading-relaxed prose-li:text-foreground
              prose-blockquote:border-l-4 prose-blockquote:border-primary/60 prose-blockquote:pl-3.5 prose-blockquote:py-1 prose-blockquote:my-2.5 prose-blockquote:italic prose-blockquote:bg-elevated/40 prose-blockquote:rounded-r-md prose-blockquote:text-foreground/90
              prose-pre:bg-transparent prose-pre:p-0 prose-pre:m-0 prose-pre:my-3
              prose-hr:border-border prose-hr:my-4
              prose-a:text-primary prose-a:font-medium prose-a:no-underline hover:prose-a:underline
              prose-table:text-[15px] prose-th:text-foreground prose-td:text-foreground/90
            ">
              <Streamdown
                animated={{
                  animation: 'blurIn',
                  duration: 250,
                  easing: 'ease-out',
                  sep: 'word',
                }}
                isAnimating={isStreaming}
                components={{
                  code({ node: _node, className, children }: any) {
                    const match = /language-(\w+)/.exec(className || '');
                    const codeString = String(children).replace(/\n$/, '');
                    const isBlock = match || codeString.includes('\n');
                    const isDark = typeof document !== 'undefined' ? document.documentElement.classList.contains('dark') : true;

                    if (isBlock) {
                      return (
                        <div className="code-block-wrapper relative my-4 rounded-xl overflow-hidden border border-border shadow-sm bg-elevated">
                          <div className="flex items-center justify-between px-4 py-2 bg-muted/60 border-b border-border/60">
                            <span className="text-xs font-mono text-muted-foreground font-medium">{match ? match[1] : 'code'}</span>
                            <CopyButton text={codeString} />
                          </div>
                          <div className="code-block-content p-4 overflow-x-auto text-xs sm:text-sm font-mono leading-relaxed">
                            <SyntaxHighlighter
                              style={isDark ? oneDark : oneLight}
                              language={match ? match[1] : 'text'}
                              PreTag="div"
                              customStyle={{
                                margin: 0,
                                padding: 0,
                                background: 'transparent',
                                fontSize: '0.85rem',
                                lineHeight: '1.6',
                              }}
                            >
                              {codeString}
                            </SyntaxHighlighter>
                          </div>
                        </div>
                      );
                    }
                    return (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                  hr: () => <hr className="border-border my-5" />,
                  a: ({ href, children, ...props }: any) => (
                    <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
                      {children}
                    </a>
                  ),
                }}
              >
                {content}
              </Streamdown>
            </div>

            {/* Evidence Panel — unified answer mode, sources, confidence, pipeline, debug */}
            <EvidencePanel
              answerMode={answerMode}
              retrievalMethod={answerModeMetadata?.retrieval_method}
              chunkCount={answerModeMetadata?.chunk_count}
              docCount={answerModeMetadata?.doc_count}
              confidence={answerModeMetadata?.confidence}
              retrievedCount={answerModeMetadata?.retrieved_count}
              resources={resources}
              evidence={evidence}
              isStreaming={isStreaming}
            />
            {/* Answer actions — only after streaming completes */}
            {content && !isStreaming && (
              <div className="flex items-center gap-1 mt-2">
                <MessageActionButton icon={<Copy size={12} />} label="Copy" onClick={() => navigator.clipboard.writeText(content)} />
                <MessageActionButton
                  icon={<ThumbsUp size={12} />}
                  label="Like"
                  active={feedback === 'liked'}
                  onClick={() => onFeedback?.(id, feedback === 'liked' ? null : 'liked')}
                />
                <MessageActionButton
                  icon={<ThumbsDown size={12} />}
                  label="Dislike"
                  active={feedback === 'disliked'}
                  onClick={() => onFeedback?.(id, feedback === 'disliked' ? null : 'disliked')}
                />
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
});
