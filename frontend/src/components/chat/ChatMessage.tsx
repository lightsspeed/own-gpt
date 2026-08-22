import React, { useState, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Card } from "@/components/ui/card";
import { Globe, BookOpen, Zap, FileText, Copy, Check, ThumbsUp, ThumbsDown, Edit2 } from 'lucide-react';
import { EvidencePanel } from '@/components/evidence';

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
      className={`p-1.5 rounded-md transition-all ${
        copied
          ? 'bg-green-500/20 text-green-400'
          : 'bg-blue-500/10 hover:bg-blue-500/25 text-white/50 hover:text-blue-300'
      }`}
    >
      {copied ? <Check size={12} /> : <Copy size={12} />}
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
                hr: () => <hr className="border-white/10 my-4" />,
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
