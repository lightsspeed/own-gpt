import { useState } from 'react';
import { AppShell, Header } from '@/components/layout';
import { Badge, IconButton } from '@/components/primitives';
import { WorkspaceSidebar } from '@/components/sidebar/WorkspaceSidebar';
import { ChatWorkspace, ConversationToolbar } from '@/features/chat';
import { useConversations } from '@/features/chat/hooks/useConversations';

const DEFAULT_SYSTEM_PROMPT =
  'You are a helpful, knowledgeable AI assistant with access to tools including web search and a knowledge base of uploaded documents. Be concise, accurate, and friendly.';

export function AppShellDemo() {
  const conv = useConversations();
  const [searchQuery, setSearchQuery] = useState('');

  const activeSessionId = conv.activeId ?? undefined;

  return (
    <AppShell
      sidebarWidth="wide"
      sidebar={
        <WorkspaceSidebar
          sessions={conv.sessions}
          activeId={conv.activeId}
          loading={conv.loading}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          onSelect={conv.switchTo}
          onNewChat={conv.create}
          onRename={conv.rename}
          onDelete={conv.remove}
        />
      }
      header={
        <Header height="md">
          <ConversationToolbar
            session={conv.activeSession}
            onRename={conv.rename}
            onDelete={conv.remove}
            onTogglePin={conv.togglePin}
          />
        </Header>
      }
    >
      <ChatWorkspace
        key={activeSessionId}
        sessionId={activeSessionId ?? ''}
        systemPrompt={DEFAULT_SYSTEM_PROMPT}
      />
    </AppShell>
  );
}
