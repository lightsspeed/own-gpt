import { useChat, type UseChatOptions } from '../hooks/useChat';
import { MessageList } from './MessageList';
import { Composer } from './Composer';
import { StreamingOverlay } from './StreamingOverlay';
import { ChatMessage } from '@/features/chat/messages';

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
        {messages.map(msg => (
          <div key={msg.id} className="mb-4 last:mb-0">
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
        ))}
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
