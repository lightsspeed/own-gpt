import { useState } from 'react'
import { ConversationSidebar } from './ConversationSidebar'
import { Menu, Sparkles, Download, Share2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ChatSession } from '@/features/chat/types'

interface OwnGPTLayoutProps {
  children: React.ReactNode
  sessions: ChatSession[]
  activeId: string | null
  loading?: boolean
  onSelect: (id: string) => void
  onNewChat: () => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
  onTogglePin?: (id: string) => void
}

export function OwnGPTLayout({
  children,
  sessions,
  activeId,
  loading,
  onSelect,
  onNewChat,
  onRename,
  onDelete,
  onTogglePin,
}: OwnGPTLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* Conversation sidebar */}
      <ConversationSidebar
        sessions={sessions}
        activeId={activeId}
        loading={loading}
        onSelect={onSelect}
        onNewChat={onNewChat}
        onRename={onRename}
        onDelete={onDelete}
        onTogglePin={onTogglePin}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(false)}
      />

      {/* Hamburger when sidebar closed */}
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="fixed top-4 left-4 z-50 p-2 bg-surface border border-border rounded-lg text-muted-foreground hover:text-foreground hover:bg-hover transition-all shadow-md"
        >
          <Menu size={18} />
        </button>
      )}

      {/* Main area */}
      <main
        className={cn(
          'flex-1 flex flex-col h-full transition-all duration-300 relative bg-background',
          sidebarOpen ? 'ml-[280px]' : 'ml-0',
        )}
      >
        {/* Top bar */}
        <header className={cn(
          'fixed top-0 right-0 h-14 glass-panel z-40 px-6 flex items-center justify-between transition-all duration-300',
          sidebarOpen ? 'w-[calc(100%-280px)]' : 'w-full',
        )}>
          <div className="flex items-center gap-4">
            {!sidebarOpen && (
              <button
                onClick={() => setSidebarOpen(true)}
                className="p-1.5 text-muted-foreground hover:text-foreground transition-all rounded-lg"
              >
                <Menu size={18} />
              </button>
            )}
            <div className="flex items-center gap-2">
              <Sparkles size={18} className="text-primary" />
              <span className="text-title font-bold text-foreground">OwnGPT</span>
            </div>
            <span className="px-2 py-0.5 rounded bg-elevated text-[10px] font-bold text-primary uppercase tracking-widest border border-border hidden sm:inline">
              Enterprise
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border text-small text-muted-foreground hover:text-foreground transition-all">
              <Share2 size={16} />
              <span className="hidden sm:inline">Share</span>
            </button>
            <button className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-small hover:brightness-110 transition-all">
              <Download size={16} />
              <span className="hidden sm:inline">Export</span>
            </button>
          </div>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-y-auto pt-14 custom-scrollbar">
          {children}
        </div>
      </main>
    </div>
  )
}
