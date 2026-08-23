import { useChat, type UseChatOptions } from '../hooks/useChat';
import { MessageList } from './MessageList';
import { Composer } from './Composer';
import { StreamingOverlay } from './StreamingOverlay';
import { ChatMessage } from '@/features/chat/messages';
import { DaySeparator, isDifferentDay } from '@/components/chat/DaySeparator';
import React from 'react';

/**
 * ChatWorkspace — pure conversation container.
 *
 * Knows nothing about:
 * - Sidebar
 * - Header
 * - Settings
 * - Sessions
 *
 * Its world: messages ↔ input ↔ streaming.
 */
export interface ChatWorkspaceProps extends UseChatOptions {}

export function ChatWorkspace(props: ChatWorkspaceProps) {
  const {
    messages,
    input,
    setInput,
    isLoading,
    streamingId,
    pipelineStages,
    send,
    stop,
    bottomRef,
  } = useChat(props);

  return (
    <div className="flex h-full flex-col">
      {/* Messages — renders legacy ChatMessage unchanged */}
      <MessageList bottomRef={bottomRef}>
        {messages.map((msg, idx) => {
          const prev = messages[idx - 1];
          const showSeparator =
            msg.timestamp &&
            (idx === 0 || isDifferentDay(prev?.timestamp, msg.timestamp));
          return (
            <React.Fragment key={msg.id}>
              {showSeparator && <DaySeparator date={msg.timestamp!} />}
              <div className="mb-4 last:mb-0">
                <ChatMessage
                  id={msg.id}
                  role={msg.role}
                  content={msg.content}
                  timestamp={msg.timestamp}
                  tool={msg.tool}
                  resources={msg.resources}
                  images={msg.images}
                  answerMode={msg.answerMode}
                  answerModeMetadata={msg.answerModeMetadata}
                  feedback={msg.feedback}
                  isStreaming={msg.id === streamingId}
                  onEdit={() => {}}
                  onFeedback={() => {}}
                />
              </div>
            </React.Fragment>
          );
        })}
      </MessageList>

      {/* Pipeline stage indicator (appears during loading) */}
      <StreamingOverlay visible={isLoading} stages={pipelineStages} />

      {/* Input */}
      <Composer
        input={input}
        setInput={setInput}
        onSend={send}
        onStop={stop}
        isLoading={isLoading}
      />
    </div>
  );
}
