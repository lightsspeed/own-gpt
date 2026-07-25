import { memo } from 'react';
import { EvidencePanel } from '@/components/evidence';
import { ToolEventPill } from './ToolEventPill';
import { MessageAvatar } from './MessageAvatar';
import { MessageContent } from './MessageContent';
import { MessageActions } from './MessageActions';
import { cn } from '@/lib/utils';

export interface ToolCall {
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
  images?: string[];
  feedback?: 'liked' | 'disliked' | null;
  answerMode?: 'grounded' | 'hybrid' | 'synthesis' | 'web' | 'no_evidence';
  answerModeMetadata?: {
    chunk_count: number;
    doc_count: number;
    confidence: number;
    retrieval_method: string;
  };
}

export interface ChatMessageProps extends MessageData {
  onEdit?: (content: string) => void;
  onFeedback?: (id: string, feedback: 'liked' | 'disliked' | null) => void;
  isStreaming?: boolean;
}

export const ChatMessage = memo(function ChatMessage({
  id,
  role,
  content,
  tool,
  timestamp,
  resources,
  images,
  feedback,
  answerMode,
  answerModeMetadata,
  onEdit,
  onFeedback,
  isStreaming,
}: ChatMessageProps) {
  /* ── Tool event pill ── */
  if (role === 'tool_event' && tool) {
    return <ToolEventPill name={tool.name} status={tool.status} />;
  }

  const isUser = role === 'user';

  return (
    <div className={cn('flex w-full group', isUser ? 'justify-end' : 'justify-start')}>
      <div className={cn(
        'w-full max-w-[95%] space-y-2',
        isUser ? 'flex flex-col items-end' : 'flex flex-col items-start',
      )}>
        {/* ── Header + Avatar row ── */}
        <div className={cn(
          'flex items-center gap-2 w-full',
          isUser ? 'flex-row-reverse' : 'flex-row',
        )}>
          <MessageAvatar role={role} />
          <span className="text-small font-medium text-text-primary">
            {isUser ? 'You' : 'Assistant'}
          </span>
          {!isUser && !isStreaming && (
            <span className="rounded-md bg-elevated px-1.5 py-0.5 text-micro text-text-secondary">
              GPT-4o Mini
            </span>
          )}
          {timestamp && (
            <span className="text-micro text-text-disabled">
              {timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
        </div>

        {/* ── Message body ── */}
        <MessageContent
          role={role}
          content={content}
          images={images}
        />

        {/* ── Evidence panel (assistant only) ── */}
        {!isUser && (
          <EvidencePanel
            answerMode={answerMode}
            retrievalMethod={answerModeMetadata?.retrieval_method}
            chunkCount={answerModeMetadata?.chunk_count}
            docCount={answerModeMetadata?.doc_count}
            confidence={answerModeMetadata?.confidence}
            resources={resources}
            isStreaming={isStreaming}
          />
        )}

        {/* ── Actions ── */}
        {content && !isStreaming && (
          <MessageActions
            role={role}
            content={content}
            feedback={feedback}
            onCopy={() => {}}
            onEdit={onEdit ? () => onEdit(content) : undefined}
            onFeedback={onFeedback ? (type) => onFeedback(id, feedback === type ? null : type) : undefined}
            className={cn(
              'transition-opacity',
              isUser ? 'opacity-0 group-hover:opacity-100' : 'opacity-0 group-hover:opacity-100',
            )}
          />
        )}
      </div>
    </div>
  );
});
