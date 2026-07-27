import { useState, useMemo, useRef, useEffect } from 'react'
import { cn } from '@/lib/utils'
import {
  Search, Pin, Trash2, Edit2, Check, X, LogOut, Settings, PanelLeftClose, Plus,
  MoreHorizontal, Copy, Share2, Archive,
} from 'lucide-react'
import type { ChatSession } from '@/features/chat/types'

interface ConversationSidebarProps {
  sessions: ChatSession[]
  activeId: string | null
  loading?: boolean
  searchQuery?: string
  onSearchChange?: (q: string) => void
  onSearchFocus?: () => void
  onSelect: (id: string) => void
  onNewChat: () => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
  onTogglePin?: (id: string) => void
  sidebarOpen: boolean
  onToggleSidebar: () => void
  onOpenSettings: () => void
}

function dateGroup(dateStr?: string): string {
  if (!dateStr) return 'Previous 30 Days'
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  if (days < 7) return 'Previous 7 Days'
  if (days < 30) return 'Previous 30 Days'
  return 'Older'
}

export function ConversationSidebar({
  sessions,
  activeId,
  loading,
  searchQuery = '',
  onSearchChange,
  onSearchFocus,
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
  const [openMenuId, setOpenMenuId] = useState<string | null>(null)

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
    const order = ['Today', 'Yesterday', 'Previous 7 Days', 'Previous 30 Days', 'Older']
    return order.filter(g => groups[g]?.length > 0).map(g => ({ label: g, items: groups[g] }))
  }, [unpinned])

  // Close menu on outside click
  useEffect(() => {
    if (!openMenuId) return
    const close = () => setOpenMenuId(null)
    window.addEventListener('click', close)
    return () => window.removeEventListener('click', close)
  }, [openMenuId])

  return (
    <aside
      className={cn(
        'sidebar-transition z-50 fixed top-2 flex flex-col',
        'rounded-2xl shadow-xl border border-border bg-surface',
        'h-[calc(100vh-16px)] w-[315px]',
        sidebarOpen ? 'left-2' : '-left-[361px]',
      )}
    >
      {/* Logo + collapse */}
      <div className="flex items-center justify-between px-4 pt-4 pb-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary/25 to-primary/5 flex items-center justify-center border border-primary/25">
            <svg width="16" height="16" viewBox="0 0 32 32" fill="none">
              <path d="M16 2L20 10L28 12L20 14L16 22L12 14L4 12L12 10L16 2Z" fill="currentColor" className="text-primary" />
              <circle cx="16" cy="22" r="3" fill="currentColor" className="text-primary/60" />
              <path d="M16 28L18 26H14L16 28Z" fill="currentColor" className="text-primary/40" />
            </svg>
          </div>
          <span className="text-small font-bold text-foreground">OwnGPT</span>
        </div>
        <button onClick={onToggleSidebar} className="p-1.5 hover:bg-hover transition-colors rounded-lg text-muted-foreground hover:text-foreground" title="Close sidebar">
          <PanelLeftClose size={16} />
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
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => onSearchChange?.(e.target.value)}
            onFocus={() => onSearchFocus?.()}
            onKeyDown={e => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); onSearchFocus?.() }
            }}
            placeholder="Search conversations..."
            className="w-full rounded-lg border border-border/50 bg-background/30 py-1.5 pl-8 pr-10 text-small text-foreground placeholder:text-muted-foreground/30 outline-none transition-colors focus:border-primary/30 focus:bg-background/50"
          />
          <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] font-medium text-muted-foreground/25 bg-muted/20 px-1.5 py-0.5 rounded border border-border/30 pointer-events-none">⌘K</kbd>
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
          <p className="px-5 py-8 text-center text-small text-muted-foreground/50 italic">
            {searchQuery ? 'No matching conversations' : 'No conversations yet'}
          </p>
        ) : (
          <div className="space-y-1 px-1 py-1">
            {pinned.length > 0 && !searchQuery && (
              <>
                <div className="px-2 py-1.5 text-[11px] font-semibold text-muted-foreground/55 uppercase tracking-[.12em] flex items-center gap-2">
                  <Pin size={10} className="text-muted-foreground/30" />
                  Pinned
                </div>
                {pinned.map(session => (
                  <SessionRow
                    key={session.id}
                    session={session}
                    activeId={activeId}
                    editingId={editingId}
                    editTitle={editTitle}
                    openMenuId={openMenuId}
                    onSelect={onSelect}
                    onStartRename={(id, title) => { setEditTitle(title); setEditingId(id); setOpenMenuId(null) }}
                    onConfirmRename={(id) => { onRename(id, editTitle); setEditingId(null) }}
                    onCancelRename={() => setEditingId(null)}
                    onEditTitleChange={setEditTitle}
                    onDelete={onDelete}
                    onTogglePin={onTogglePin}
                    onOpenMenu={setOpenMenuId}
                  />
                ))}
                <div className="my-2 mx-2 border-t border-border/30" />
              </>
            )}

            {grouped.map(group => (
              <div key={group.label}>
                <div className="px-2 py-1.5 text-[11px] font-semibold text-muted-foreground/55 uppercase tracking-[.12em]">
                  {group.label}
                </div>
                {group.items.map(session => (
                  <SessionRow
                    key={session.id}
                    session={session}
                    activeId={activeId}
                    editingId={editingId}
                    editTitle={editTitle}
                    openMenuId={openMenuId}
                    onSelect={onSelect}
                    onStartRename={(id, title) => { setEditTitle(title); setEditingId(id); setOpenMenuId(null) }}
                    onConfirmRename={(id) => { onRename(id, editTitle); setEditingId(null) }}
                    onCancelRename={() => setEditingId(null)}
                    onEditTitleChange={setEditTitle}
                    onDelete={onDelete}
                    onTogglePin={onTogglePin}
                    onOpenMenu={setOpenMenuId}
                  />
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="shrink-0 border-t border-border/60 px-3 py-2.5 mt-1">
        <button onClick={onOpenSettings} className="flex items-center gap-2.5 w-full p-2 rounded-lg text-muted-foreground/60 hover:text-foreground hover:bg-hover/60 transition-all duration-150 text-small">
          <Settings size={16} className="text-muted-foreground/40" />
          Settings
        </button>
        <div className="flex items-center gap-2.5 p-2 mt-1.5 border-t border-border/40 pt-3">
          <div className="w-7 h-7 rounded-full bg-primary/15 flex items-center justify-center text-primary text-[10px] font-bold shrink-0 ring-1 ring-primary/20">
            JD
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-small font-medium text-foreground truncate">Jane Doe</span>
            <span className="text-caption text-muted-foreground/50 truncate">Engineering Lead</span>
            <span className="text-caption text-muted-foreground/40 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-success" />
              Online
            </span>
          </div>
          <LogOut size={14} className="ml-auto text-muted-foreground/25" />
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
  openMenuId,
  onSelect,
  onStartRename,
  onConfirmRename,
  onCancelRename,
  onEditTitleChange,
  onDelete,
  onTogglePin,
  onOpenMenu,
}: {
  session: ChatSession
  activeId: string | null
  editingId: string | null
  editTitle: string
  openMenuId: string | null
  onSelect: (id: string) => void
  onStartRename: (id: string, title: string) => void
  onConfirmRename: (id: string) => void
  onCancelRename: () => void
  onEditTitleChange: (val: string) => void
  onDelete: (id: string) => void
  onTogglePin?: (id: string) => void
  onOpenMenu: (id: string | null) => void
}) {
  const isActive = session.id === activeId
  const isEditing = editingId === session.id
  const menuOpen = openMenuId === session.id
  const menuRef = useRef<HTMLDivElement>(null)

  // Close menu on Escape
  useEffect(() => {
    if (!menuOpen) return
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenMenu(null)
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [menuOpen, onOpenMenu])

  return (
    <div
      className={cn(
        'group relative flex items-center gap-2 rounded-md px-2.5 py-[9px] transition-all duration-160 cursor-pointer',
        isActive ? 'bg-primary/[0.08]' : 'hover:bg-white/[0.05]',
      )}
      onClick={() => { onSelect(session.id); onOpenMenu(null) }}
    >
      {/* Active accent */}
      {isActive && (
        <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary" />
      )}

      {isEditing ? (
        <div className="flex items-center gap-1 w-full pl-1">
          <input
            autoFocus
            className="flex-1 bg-background text-foreground border border-border/60 rounded px-1.5 py-1 outline-none min-w-0 text-small"
            value={editTitle}
            onChange={e => onEditTitleChange(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') onConfirmRename(session.id)
              if (e.key === 'Escape') onCancelRename()
            }}
            onClick={e => e.stopPropagation()}
          />
          <button onClick={e => { e.stopPropagation(); onConfirmRename(session.id) }} className="text-success hover:text-success/80 p-0.5"><Check size={12} /></button>
          <button onClick={e => { e.stopPropagation(); onCancelRename() }} className="text-muted-foreground hover:text-foreground p-0.5"><X size={12} /></button>
        </div>
      ) : (
        <>
          <div className={cn('flex-1 min-w-0', isActive && 'pl-1')}>
            <div className="flex items-center gap-1.5">
              {session.is_pinned && <Pin size={10} className="shrink-0 text-primary/50" />}
              <span className={cn('truncate text-small', isActive ? 'font-semibold text-foreground' : 'text-muted-foreground/80 group-hover:text-foreground')}>
                {session.title}
              </span>
            </div>

          </div>

          {/* Hover ⋯ menu */}
          <div className="relative shrink-0" ref={menuRef}>
            <button
              onClick={e => { e.stopPropagation(); onOpenMenu(menuOpen ? null : session.id) }}
              className={cn(
                'p-1 rounded-md transition-all opacity-0 group-hover:opacity-100',
                menuOpen ? 'opacity-100 bg-hover text-foreground' : 'text-muted-foreground/50 hover:text-foreground hover:bg-hover',
              )}
            >
              <MoreHorizontal size={14} />
            </button>

            {menuOpen && (
              <div
                className="absolute right-0 bottom-full mb-1 w-44 py-1 rounded-xl border border-border/60 bg-surface shadow-2xl z-50 animate-fade-in"
                onClick={e => e.stopPropagation()}
              >
                <MenuButton icon={<Edit2 size={13} />} label="Rename" onClick={() => onStartRename(session.id, session.title)} />
                <MenuButton icon={<Pin size={13} />} label={session.is_pinned ? 'Unpin' : 'Pin'} onClick={() => onTogglePin?.(session.id)} />
                <MenuButton icon={<Copy size={13} />} label="Duplicate" onClick={() => {}} />
                <MenuButton icon={<Share2 size={13} />} label="Share" onClick={() => {}} />
                <div className="my-1 mx-2 border-t border-border/40" />
                <MenuButton icon={<Archive size={13} />} label="Archive" onClick={() => {}} />
                <MenuButton icon={<Trash2 size={13} />} label="Delete" danger onClick={() => onDelete(session.id)} />
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function MenuButton({ icon, label, danger, onClick }: { icon: React.ReactNode; label: string; danger?: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2.5 w-full px-3 py-1.5 text-left text-small transition-colors',
        danger ? 'text-danger/80 hover:text-danger hover:bg-danger/5' : 'text-muted-foreground/80 hover:text-foreground hover:bg-hover/60',
      )}
    >
      <span className="shrink-0">{icon}</span>
      {label}
    </button>
  )
}


