import { useMemo, useRef, useEffect, useState } from 'react';
import { PanelRightClose, ArrowUp, Square, FileText, Globe, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useChat } from '@/features/chat/hooks/useChat';
import { MessageBubble } from '@/components/own-platform/MessageBubble';
import { GenerationSpinner } from '@/components/own-platform/GenerationSpinner';
import type { ResourceItem } from '@/features/chat/types';

interface DocumentChatProps {
  filename: string;
  currentPage: number;
  onClose?: () => void;
}

export function DocumentChat({ filename, currentPage, onClose }: DocumentChatProps) {
  const {
    messages,
    input,
    setInput,
    isLoading,
    streamingId,
    pipelineStages,
    loadingHistory,
    send,
    stop,
  } = useChat({
    sessionId: `doc-chat-${filename}`,
    model: 'gpt-4o-mini',
    temperature: 0.7,
    document: filename,
    systemPrompt: `You are a helpful assistant reading the document "${filename}" in the Knowledge Base. Today's date is ${new Date().toISOString().split('T')[0]}.`,
  });

  const [expandedSources, setExpandedSources] = useState<ResourceItem[] | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const isNearBottom = useRef(true);

  const visibleMessages = useMemo(() => messages.filter(m => m.role !== 'tool_event'), [messages]);
  const hasMessages = visibleMessages.length > 0;

  const streamingMsg = messages.find(m => m.id === streamingId);
  const showSpinner = isLoading && streamingId !== null && streamingMsg && !streamingMsg.content;

  /* Scroll to bottom when a new message starts, then stay pinned while streaming */
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
      isNearBottom.current = true;
    }
  }, [visibleMessages.length]);

  const lastMessageContent = visibleMessages[visibleMessages.length - 1]?.content || '';
  useEffect(() => {
    if (!isLoading || !isNearBottom.current) return;
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [lastMessageContent, isLoading]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    isNearBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  const handleSend = () => {
    if (isLoading) {
      stop();
      return;
    }
    send();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading) send();
    }
  };

  const handleEdit = (content: string) => {
    setInput(content);
  };

  const handleShowSources = (sources: ResourceItem[]) => {
    setExpandedSources(sources);
  };

  return (
    <div className="h-full flex flex-col bg-elevated/30">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-border/40 shrink-0">
        <span className="text-caption text-muted-foreground font-medium">Ask about document</span>
        {onClose && (
          <button onClick={onClose} className="p-1 rounded text-muted-foreground/40 hover:text-foreground hover:bg-hover transition-colors">
            <PanelRightClose size={14} />
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto custom-scrollbar min-h-0">
        <div className="px-3 py-3">
          {loadingHistory && (
            <div className="flex items-center justify-center h-32">
              <div className="w-5 h-5 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
            </div>
          )}

          {!hasMessages && !loadingHistory && (
            <div className="flex flex-col items-center text-center px-4 pt-10 space-y-2.5">
              <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/25">
                <FileText size={16} className="text-primary" />
              </div>
              <h3 className="text-small font-semibold text-foreground leading-snug">Ask about this document</h3>
              <p className="text-caption text-muted-foreground/60 leading-relaxed">
                Explain sections, summarize content, or find specific information. Answers will only use this document.
              </p>
            </div>
          )}

          <div className="space-y-4">
            {visibleMessages.map(msg => (
              <div key={msg.id} className="animate-message-in">
                <MessageBubble
                  role={msg.role}
                  content={msg.content}
                  isStreaming={msg.id === streamingId}
                  resources={msg.resources}
                  answerMode={msg.answerMode}
                  answerModeMetadata={msg.answerModeMetadata}
                  onEdit={msg.role === 'user' ? handleEdit : undefined}
                  onShowSources={handleShowSources}
                />
              </div>
            ))}
          </div>

          {showSpinner && (
            <div className="animate-fade-in mt-3 mb-3" style={{ animationDuration: '0.3s' }}>
              <GenerationSpinner stages={pipelineStages} />
            </div>
          )}

          {/* Inline sources */}
          {expandedSources && (
            <div className="mt-4 rounded-xl border border-border/40 bg-background/30 animate-fade-in">
              <div className="flex items-center justify-between px-3 py-2 border-b border-border/40">
                <span className="text-caption font-medium text-muted-foreground">Sources</span>
                <button onClick={() => setExpandedSources(null)} className="p-1 rounded text-muted-foreground/40 hover:text-foreground hover:bg-hover transition-colors">
                  <X size={12} />
                </button>
              </div>
              <div className="p-2 space-y-1">
                {expandedSources.map((s, i) => (
                  <a
                    key={i}
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-2 rounded-lg px-2 py-1.5 text-small text-foreground/80 hover:bg-hover transition-colors"
                  >
                    {s.type === 'web' ? (
                      <Globe size={12} className="mt-0.5 shrink-0 text-sky-400" />
                    ) : (
                      <FileText size={12} className="mt-0.5 shrink-0 text-primary" />
                    )}
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{s.title}</span>
                      {s.snippet && <span className="block text-caption text-muted-foreground/60 line-clamp-2">{s.snippet}</span>}
                    </span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Composer */}
      <div className="shrink-0 px-3 py-2.5 border-t border-border/40">
        <div className="flex items-end gap-2 rounded-xl border border-border/60 bg-background/60 px-3 py-2 focus-within:border-primary/40 transition-colors">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about this document..."
            rows={Math.min(4, Math.max(1, input.split('\n').length))}
            className="flex-1 resize-none bg-transparent text-small text-foreground placeholder:text-muted-foreground/30 outline-none leading-relaxed custom-scrollbar"
          />
          <button
            onClick={handleSend}
            disabled={isLoading ? false : !input.trim()}
            className={cn(
              'p-1.5 rounded-lg transition-all shrink-0',
              isLoading
                ? 'bg-muted/30 text-muted-foreground hover:bg-hover'
                : input.trim()
                  ? 'bg-primary/15 text-primary hover:bg-primary/25'
                  : 'bg-muted/10 text-muted-foreground/30',
            )}
          >
            {isLoading ? <Square size={13} /> : <ArrowUp size={13} />}
          </button>
        </div>
      </div>
    </div>
  );
}
