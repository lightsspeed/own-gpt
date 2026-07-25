import { useState, useMemo } from 'react'
import { cn } from '@/lib/utils'
import {
  Search, Pin, Trash2, Edit2, Check, X, LogOut, Settings, PanelLeftClose, Plus, MessageSquare, Clock
} from 'lucide-react'
import type { ChatSession } from '@/features/chat/types'

interface ConversationSidebarProps {
  sessions: ChatSession[]
  activeId: string | null
  loading?: boolean
  searchQuery?: string
  onSearchChange?: (q: string) => void
  onSelect: (id: string) => void
  onNewChat: () => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
  onTogglePin?: (id: string) => void
  sidebarOpen: boolean
  onToggleSidebar: () => void
  onOpenSettings: () => void
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return 'Unknown'
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  if (days === 1) return 'Yesterday'
  if (days < 7) return `${days} days ago`
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
}

function dateGroup(dateStr?: string): string {
  if (!dateStr) return 'Older'
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return 'This Week'
  if (days < 30) return 'This Month'
  return 'Older'
}

export function ConversationSidebar({
  sessions,
  activeId,
  loading,
  searchQuery = '',
  onSearchChange,
  onSelect,
  onNewChat,
  onRename,
  onDelete,
  onTogglePin,
  sidebarOpen,
  onToggleSidebar,
  onOpenSettings,
}: ConversationSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')

  const filtered = searchQuery
    ? sessions.filter(s => s.title.toLowerCase().includes(searchQuery.toLowerCase()))
    : sessions

  const { pinned, unpinned } = useMemo(() => {
    const ordered = [...filtered].sort((a, b) => {
      return (b.updated_at ?? '').localeCompare(a.updated_at ?? '')
    })
    return {
      pinned: ordered.filter(s => s.is_pinned),
      unpinned: ordered.filter(s => !s.is_pinned),
    }
  }, [filtered])

  const grouped = useMemo(() => {
    const groups: Record<string, ChatSession[]> = {}
    for (const s of unpinned) {
      const g = dateGroup(s.updated_at)
      if (!groups[g]) groups[g] = []
      groups[g].push(s)
    }
    const order = ['Today', 'Yesterday', 'This Week', 'This Month', 'Older']
    return order.filter(g => groups[g]?.length > 0).map(g => ({ label: g, items: groups[g] }))
  }, [unpinned])

  return (
    <aside
      className={cn(
        'sidebar-transition z-50 fixed top-2 flex flex-col',
        'rounded-2xl shadow-xl border border-border bg-surface',
        'h-[calc(100vh-16px)] w-[250px]',
        sidebarOpen ? 'left-2' : '-left-[296px]',
      )}
    >
      {/* Logo + collapse */}
      <div className="flex items-center justify-between px-4 pt-4 pb-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary/25 to-primary/5 flex items-center justify-center border border-primary/25">
            <svg width="18" height="18" viewBox="0 0 32 32" fill="none">
              <path d="M16 2L20 10L28 12L20 14L16 22L12 14L4 12L12 10L16 2Z" fill="currentColor" className="text-primary" />
              <circle cx="16" cy="22" r="3" fill="currentColor" className="text-primary/60" />
              <path d="M16 28L18 26H14L16 28Z" fill="currentColor" className="text-primary/40" />
            </svg>
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-small font-bold text-foreground">OwnGPT</span>
            <span className="text-caption text-muted-foreground">Conversations</span>
          </div>
        </div>
        <button onClick={onToggleSidebar} className="p-2 hover:bg-hover transition-colors rounded-lg text-muted-foreground hover:text-foreground active:scale-95" title="Close sidebar">
          <PanelLeftClose size={18} />
        </button>
      </div>

      {/* New Chat */}
      <div className="px-4 mb-3 shrink-0">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-primary text-primary-foreground text-small font-semibold hover:brightness-110 transition-all active:scale-[0.98] shadow-lg shadow-primary/20"
        >
          <Plus size={18} />
          <span>New Chat</span>
        </button>
      </div>

      {/* Search */}
      <div className="px-4 mb-2 shrink-0">
        <div className="relative">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/60" />
            <input
            type="text"
            value={searchQuery}
            onChange={e => onSearchChange?.(e.target.value)}
            placeholder="Search..."
            className="w-full rounded-lg border border-border bg-background/50 py-1.5 pl-8 pr-10 text-small text-foreground placeholder:text-muted-foreground/40 outline-none transition-colors focus:border-primary/40"
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] font-medium text-muted-foreground/30 bg-muted/30 px-1.5 py-0.5 rounded border border-border/40 pointer-events-none">⌘K</kbd>
        </div>
      </div>

      {/* Sessions */}
      <div className="flex-1 overflow-y-auto px-2 custom-scrollbar">
        {loading ? (
          <div className="space-y-2 px-3 py-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="flex items-center gap-3 p-2">
                <div className="w-8 h-8 rounded-lg animate-pulse bg-muted" />
                <div className="flex-1 space-y-1">
                  <div className="h-3 w-3/4 rounded animate-pulse bg-muted" />
                  <div className="h-2 w-1/4 rounded animate-pulse bg-muted/60" />
                </div>
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <p className="px-5 py-8 text-center text-small text-muted-foreground/60 italic">
            {searchQuery ? 'No matching conversations' : 'No conversations yet'}
          </p>
        ) : (
          <div className="space-y-1 px-1 py-1">
            {/* Pinned section */}
            {pinned.length > 0 && !searchQuery && (
              <>
                <div className="px-2 py-1.5 text-caption font-medium text-muted-foreground/60 uppercase tracking-wider">Pinned</div>
                {pinned.map(session => (
                  <SessionRow
                    key={session.id}
                    session={session}
                    activeId={activeId}
                    editingId={editingId}
                    editTitle={editTitle}
                    onSelect={onSelect}
                    onStartRename={(id, title) => { setEditTitle(title); setEditingId(id) }}
                    onConfirmRename={(id) => { onRename(id, editTitle); setEditingId(null) }}
                    onCancelRename={() => setEditingId(null)}
                    onEditTitleChange={setEditTitle}
                    onDelete={onDelete}
                    onTogglePin={onTogglePin}
                  />
                ))}
                <div className="my-2 mx-2 border-t border-border/40" />
              </>
            )}

            {/* Grouped sessions */}
            {grouped.map(group => (
              <div key={group.label}>
                <div className="px-2 py-1.5 text-caption font-medium text-muted-foreground/60 uppercase tracking-wider">
                  {group.label}
                </div>
                {group.items.map(session => (
                  <SessionRow
                    key={session.id}
                    session={session}
                    activeId={activeId}
                    editingId={editingId}
                    editTitle={editTitle}
                    onSelect={onSelect}
                    onStartRename={(id, title) => { setEditTitle(title); setEditingId(id) }}
                    onConfirmRename={(id) => { onRename(id, editTitle); setEditingId(null) }}
                    onCancelRename={() => setEditingId(null)}
                    onEditTitleChange={setEditTitle}
                    onDelete={onDelete}
                    onTogglePin={onTogglePin}
                  />
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="shrink-0 border-t border-border px-3 py-3 mt-2">
        <button onClick={onOpenSettings} className="flex items-center gap-3 w-full p-2.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-hover transition-colors text-small">
          <Settings size={16} />
          Settings
        </button>
        <div className="flex items-center gap-3 p-2.5 mt-2 border-t border-border pt-4">
          <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-white text-[10px] font-bold shrink-0">JD</div>
          <div className="flex flex-col min-w-0">
            <span className="text-small font-medium text-foreground truncate">Jane Doe</span>
            <span className="text-caption text-muted-foreground">Engineering Lead</span>
          </div>
          <LogOut size={14} className="ml-auto text-muted-foreground/40" />
        </div>
      </div>
    </aside>
  )
}

function SessionRow({
  session,
  activeId,
  editingId,
  editTitle,
  onSelect,
  onStartRename,
  onConfirmRename,
  onCancelRename,
  onEditTitleChange,
  onDelete,
  onTogglePin,
}: {
  session: ChatSession
  activeId: string | null
  editingId: string | null
  editTitle: string
  onSelect: (id: string) => void
  onStartRename: (id: string, title: string) => void
  onConfirmRename: (id: string) => void
  onCancelRename: () => void
  onEditTitleChange: (val: string) => void
  onDelete: (id: string) => void
  onTogglePin?: (id: string) => void
}) {
  const isActive = session.id === activeId
  const isEditing = editingId === session.id

  return (
    <div
      className={cn(
        'group relative flex items-center gap-2 rounded-lg px-3 py-2.5 transition-all cursor-pointer',
        isActive ? 'bg-elevated' : 'hover:bg-hover',
      )}
      onClick={() => onSelect(session.id)}
    >
      {isActive && <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary" />}

      {isEditing ? (
        <div className="flex items-center gap-1 w-full">
          <input
            autoFocus
            className="flex-1 bg-background text-foreground border border-border rounded px-1.5 py-1 outline-none min-w-0 text-small"
            value={editTitle}
            onChange={e => onEditTitleChange(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') onConfirmRename(session.id)
              if (e.key === 'Escape') onCancelRename()
            }}
            onClick={e => e.stopPropagation()}
          />
          <button onClick={e => { e.stopPropagation(); onConfirmRename(session.id) }} className="text-success p-0.5"><Check size={12} /></button>
          <button onClick={e => { e.stopPropagation(); onCancelRename() }} className="text-muted-foreground p-0.5"><X size={12} /></button>
        </div>
      ) : (
        <>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              {session.is_pinned && <Pin size={10} className="shrink-0 text-primary/60" />}
              <span className={cn('truncate text-small', isActive ? 'font-semibold text-foreground' : 'text-muted-foreground group-hover:text-foreground')}>
                {session.title}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-caption text-muted-foreground/40">{formatDate(session.updated_at)}</span>
              {session.message_count != null && (
                <span className="text-caption text-muted-foreground/40 flex items-center gap-1">
                  <MessageSquare size={10} />
                  {session.message_count}
                </span>
              )}
            </div>
          </div>
          {isActive && (
            <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" onClick={e => e.stopPropagation()}>
              {onTogglePin && (
                <button onClick={() => onTogglePin(session.id)} className="p-1 text-muted-foreground hover:text-primary rounded">
                  <Pin size={12} />
                </button>
              )}
              <button onClick={() => onStartRename(session.id, session.title)} className="p-1 text-muted-foreground hover:text-foreground rounded">
                <Edit2 size={12} />
              </button>
              <button onClick={() => onDelete(session.id)} className="p-1 text-muted-foreground hover:text-danger rounded">
                <Trash2 size={12} />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
