import { useState, useEffect, useCallback } from 'react'
import { ConversationSidebar } from './ConversationSidebar'
import { OwnGPTPage } from './OwnGPTPage'
import { SearchPalette } from './SearchPalette'
import { SettingsPanel } from './SettingsPanel'
import { Menu, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import { api } from '@/features/chat/services/chatApi'
import type { ChatSession } from '@/features/chat/types'

export function OwnGPTContainer() {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)

  const refresh = useCallback(async () => {
    const list = await api.fetchSessions()
    setSessions(list)
    if (!activeId && list.length > 0) {
      setActiveId(list[0].id)
    }
    setLoading(false)
  }, [activeId])

  useEffect(() => { refresh() }, [refresh])

  const handleNewChat = useCallback(() => {
    const id = crypto.randomUUID()
    setSessions(prev => [{
      id,
      title: 'New Chat',
      is_pinned: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }, ...prev])
    setActiveId(id)
  }, [])

  const handleDelete = useCallback(async (id: string) => {
    await api.deleteSession(id)
    setSessions(prev => prev.filter(s => s.id !== id))
    if (activeId === id) {
      const remaining = sessions.filter(s => s.id !== id)
      setActiveId(remaining.length > 0 ? remaining[0].id : null)
    }
  }, [activeId, sessions])

  const handleRename = useCallback(async (id: string, title: string) => {
    await api.updateSession(id, { title })
    setSessions(prev => prev.map(s => s.id === id ? { ...s, title } : s))
  }, [])

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setSearchOpen(prev => !prev)
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [])

  const handleSearchSelect = useCallback((sessionId: string) => {
    setActiveId(sessionId)
  }, [])

  const handleTogglePin = useCallback(async (id: string) => {
    const session = sessions.find(s => s.id === id)
    if (!session) return
    const is_pinned = !session.is_pinned
    await api.updateSession(id, { is_pinned })
    setSessions(prev => prev.map(s => s.id === id ? { ...s, is_pinned } : s))
  }, [sessions])

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <SearchPalette
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onSelect={handleSearchSelect}
        onNewChat={handleNewChat}
      />

      <ConversationSidebar
        sessions={sessions}
        activeId={activeId}
        loading={loading}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onSearchFocus={() => setSearchOpen(true)}
        onSelect={handleSearchSelect}
        onNewChat={handleNewChat}
        onRename={handleRename}
        onDelete={handleDelete}
        onTogglePin={handleTogglePin}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(false)}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="fixed top-4 left-4 z-50 p-2.5 bg-surface border border-border rounded-xl text-muted-foreground hover:text-foreground hover:bg-hover transition-all shadow-lg"
        >
          <Menu size={18} />
        </button>
      )}

      <main className={cn(
        'flex-1 flex flex-col h-full transition-all duration-300 min-w-0',
        sidebarOpen ? 'ml-[266px]' : 'ml-0',
      )}>
        <div className="flex-1 min-h-0">
          {activeId ? (
            <OwnGPTPage key={activeId} sessionId={activeId} />
          ) : (
            <div className="h-full flex items-center justify-center">
              <div className="text-center space-y-4">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/25 flex items-center justify-center mx-auto">
                  <Sparkles size={28} className="text-primary" />
                </div>
                <h2 className="text-title font-semibold text-foreground">Welcome to OwnGPT</h2>
                <p className="text-body text-muted-foreground max-w-md">Your intelligent engineering co-pilot</p>
                <button onClick={handleNewChat} className="px-6 py-2.5 rounded-xl bg-primary text-primary-foreground text-small font-medium hover:brightness-110 transition-all">
                  Start a conversation
                </button>
              </div>
            </div>
          )}
        </div>
      </main>

      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
