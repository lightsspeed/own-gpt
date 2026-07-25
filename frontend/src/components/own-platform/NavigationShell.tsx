import { useState } from 'react'
import { cn } from '@/lib/utils'
import {
  Sparkles, History, Settings, HelpCircle, LogOut,
  Menu, Activity, Search, PanelLeftClose, Zap, Monitor,
  BookOpen, Beaker, BarChart3, GitBranch, Archive, Cog,
  ChevronDown,
} from 'lucide-react'

export interface NavItem {
  id: string
  label: string
  icon: React.ReactNode
  path: string
  children?: NavItem[]
}

interface NavGroup {
  label: string
  defaultOpen?: boolean
  items: NavItem[]
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Core',
    defaultOpen: true,
    items: [
      {
        id: 'owngpt',
        label: 'OwnGPT',
        icon: <Sparkles size={18} />,
        path: '/',
      },
      {
        id: 'dashboard',
        label: 'Dashboard',
        icon: <Activity size={18} />,
        path: '/dashboard',
      },
      {
        id: 'ownops',
        label: 'OwnOps',
        icon: <Zap size={18} />,
        path: '/operations',
        children: [
          { id: 'findings', label: 'Findings', icon: null, path: '/findings' },
          { id: 'evaluation', label: 'Evaluation', icon: null, path: '/evaluation' },
        ],
      },
    ],
  },
  {
    label: 'Observability',
    defaultOpen: true,
    items: [
      {
        id: 'ownmonitor',
        label: 'OwnMonitor',
        icon: <Monitor size={18} />,
        path: '/monitor',
        children: [
          { id: 'recommendations', label: 'Recommendations', icon: null, path: '/recommendations' },
          { id: 'decisions', label: 'Decisions', icon: null, path: '/decisions' },
        ],
      },
      {
        id: 'ownanalytics',
        label: 'OwnAnalytics',
        icon: <BarChart3 size={18} />,
        path: '/analytics',
      },
    ],
  },
  {
    label: 'Development',
    defaultOpen: false,
    items: [
      {
        id: 'ownlab',
        label: 'OwnLab',
        icon: <Beaker size={18} />,
        path: '/experiments',
      },
      {
        id: 'ownflow',
        label: 'OwnFlow',
        icon: <GitBranch size={18} />,
        path: '/automation',
      },
    ],
  },
  {
    label: 'Configuration',
    defaultOpen: false,
    items: [
      {
        id: 'ownlearn',
        label: 'OwnLearn',
        icon: <BookOpen size={18} />,
        path: '/learn',
        children: [
          { id: 'capabilities', label: 'Capabilities', icon: null, path: '/capabilities' },
        ],
      },
      {
        id: 'ownartifacts',
        label: 'OwnArtifacts',
        icon: <Archive size={18} />,
        path: '/artifacts',
      },
      {
        id: 'ownconfig',
        label: 'OwnConfig',
        icon: <Cog size={18} />,
        path: '/config/snapshots',
      },
    ],
  },
]

const DEFAULT_NAV_ITEMS = NAV_GROUPS.flatMap(g => g.items)

interface NavigationShellProps {
  children: React.ReactNode
  currentPath?: string
  onNavigate?: (path: string) => void
  navItems?: NavItem[]
}

export function NavigationShell({
  children,
  currentPath = '/',
  onNavigate,
  navItems = DEFAULT_NAV_ITEMS,
}: NavigationShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set())
  const [collapsedGroups, setCollapsedGroups] = useState<Set<number>>(new Set(
    NAV_GROUPS.map((g, i) => g.defaultOpen === false ? i : -1).filter(i => i >= 0)
  ))
  const [searchQuery, setSearchQuery] = useState('')

  const toggleSection = (id: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleGroup = (gi: number) => {
    setCollapsedGroups(prev => {
      const next = new Set(prev)
      if (next.has(gi)) next.delete(gi)
      else next.add(gi)
      return next
    })
  }

  const isActive = (path: string) => currentPath === path || currentPath.startsWith(path)

  const filteredItems = searchQuery
    ? navItems.filter(item => {
        const labelMatch = item.label.toLowerCase().includes(searchQuery.toLowerCase())
        const childMatch = item.children?.some(c => c.label.toLowerCase().includes(searchQuery.toLowerCase()))
        return labelMatch || childMatch
      })
    : navItems

  return (
    <div className="flex h-screen w-full overflow-hidden bg-canvas">
      <aside
        className={cn(
          'sidebar-transition z-50 fixed top-2 flex flex-col overflow-y-auto',
          'rounded-2xl shadow-xl border border-border bg-surface',
          'h-[calc(100vh-16px)] w-[250px]',
          sidebarOpen ? 'left-2' : '-left-[296px]',
        )}
      >
        {/* Logo header */}
        <div className="flex items-center justify-between px-4 pt-4 pb-3 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary/25 to-primary/5 flex items-center justify-center border border-primary/25">
              <svg width="16" height="16" viewBox="0 0 32 32" fill="none">
                <path d="M16 2L20 10L28 12L20 14L16 22L12 14L4 12L12 10L16 2Z" fill="currentColor" className="text-primary" />
                <circle cx="16" cy="22" r="3" fill="currentColor" className="text-primary/60" />
                <path d="M16 28L18 26H14L16 28Z" fill="currentColor" className="text-primary/40" />
              </svg>
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-small font-bold text-foreground">Own Platform</span>
              <span className="text-caption text-muted-foreground">AI Engineering</span>
            </div>
          </div>
          <button onClick={() => setSidebarOpen(false)} className="p-1.5 hover:bg-hover transition-colors rounded-lg text-muted-foreground hover:text-foreground" title="Close sidebar">
            <PanelLeftClose size={16} />
          </button>
        </div>

        {/* ⌘K Search */}
        <div className="px-4 mb-2 shrink-0">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search..."
              className="w-full rounded-lg border border-border/50 bg-background/30 py-1.5 pl-8 pr-10 text-small text-foreground placeholder:text-muted-foreground/30 outline-none transition-colors focus:border-primary/30 focus:bg-background/50"
            />
            <kbd className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] font-medium text-muted-foreground/25 bg-muted/20 px-1.5 py-0.5 rounded border border-border/30 pointer-events-none">⌘K</kbd>
          </div>
        </div>

        {/* Nav groups */}
        <nav className="flex-1 overflow-y-auto px-2 custom-scrollbar">
          <div className="space-y-1">
            {NAV_GROUPS.map((group, gi) => {
              const groupCollapsed = collapsedGroups.has(gi)
              const groupItems = searchQuery
                ? filteredItems.filter(fi => group.items.some(i => i.id === fi.id))
                : group.items
              if (groupItems.length === 0) return null

              return (
                <div key={gi}>
                  {/* Group header (collapsible) */}
                  {!searchQuery && (
                    <button
                      onClick={() => toggleGroup(gi)}
                      className="flex items-center gap-1.5 w-full px-3 py-1.5 group/gh"
                    >
                      <ChevronDown
                        size={10}
                        className={cn(
                          'text-muted-foreground/25 transition-transform duration-200',
                          groupCollapsed && '-rotate-90',
                        )}
                      />
                      <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground/25">
                        {group.label}
                      </span>
                    </button>
                  )}

                  {/* Group items */}
                  <div className={cn(
                    'space-y-0.5 overflow-hidden',
                    groupCollapsed && !searchQuery ? 'hidden' : '',
                  )}>
                    {groupItems.map(item => {
                      const active = isActive(item.path)
                      const expanded = expandedSections.has(item.id)
                      return (
                        <div key={item.id}>
                          <button
                            onClick={() => {
                              if (item.children) {
                                toggleSection(item.id)
                              } else {
                                onNavigate?.(item.path)
                              }
                            }}
                            className={cn(
                              'group relative flex items-center gap-2.5 w-full rounded-lg px-3 py-2 text-left transition-all duration-150',
                              active
                                ? 'bg-primary/[0.08] text-foreground'
                                : 'text-muted-foreground/70 hover:text-foreground hover:bg-hover/60',
                            )}
                          >
                            {/* Left accent bar — Linear style */}
                            <span className={cn(
                              'absolute left-0 top-1/2 -translate-y-1/2 w-[3px] rounded-full transition-all duration-150',
                              active
                                ? 'h-5 bg-primary opacity-100'
                                : 'h-0 bg-transparent opacity-0 group-hover:h-4 group-hover:bg-border/20 group-hover:opacity-100',
                            )} />

                            {/* Icon with lift effect */}
                            <span className={cn(
                              'shrink-0 transition-all duration-150',
                              active
                                ? 'text-primary'
                                : 'text-muted-foreground/50 group-hover:text-muted-foreground/80 group-hover:translate-x-[1px]',
                            )}>
                              {item.icon}
                            </span>

                            <span className="text-small flex-1 truncate">{item.label}</span>

                            {item.children && (
                              <ChevronDown
                                size={12}
                                className={cn(
                                  'text-muted-foreground/30 transition-transform duration-200',
                                  expanded && 'rotate-180',
                                )}
                              />
                            )}
                          </button>

                          {/* Children */}
                          {item.children && expanded && (
                            <div className="ml-4 space-y-0.5 mt-0.5 overflow-hidden animate-slide-down">
                              {item.children.map(child => (
                                <button
                                  key={child.id}
                                  onClick={() => onNavigate?.(child.path)}
                                  className={cn(
                                    'flex items-center gap-2.5 w-full rounded-lg py-1.5 px-3 transition-all text-left text-small',
                                    isActive(child.path)
                                      ? 'text-foreground font-medium'
                                      : 'text-muted-foreground/60 hover:text-foreground hover:bg-hover/40',
                                  )}
                                >
                                  <span className="w-1 h-1 rounded-full bg-border/30 shrink-0" />
                                  {child.label}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        </nav>

        {/* Footer */}
        <div className="shrink-0 border-t border-border/60 px-3 py-2.5 mt-1">
          <button
            onClick={() => onNavigate?.('/history')}
            className="flex items-center gap-2.5 w-full p-2 rounded-lg text-muted-foreground/60 hover:text-foreground hover:bg-hover/60 transition-all duration-150 text-small"
          >
            <History size={16} className="text-muted-foreground/40" />
            History
          </button>
          <button
            onClick={() => onNavigate?.('/settings')}
            className="flex items-center gap-2.5 w-full p-2 rounded-lg text-muted-foreground/60 hover:text-foreground hover:bg-hover/60 transition-all duration-150 text-small"
          >
            <Settings size={16} className="text-muted-foreground/40" />
            Settings
          </button>
          <button
            onClick={() => window.open('https://opencode.ai/docs', '_blank')}
            className="flex items-center gap-2.5 w-full p-2 rounded-lg text-muted-foreground/60 hover:text-foreground hover:bg-hover/60 transition-all duration-150 text-small"
          >
            <HelpCircle size={16} className="text-muted-foreground/40" />
            Help
          </button>
          <button
            onClick={() => { localStorage.clear(); window.location.href = '/' }}
            className="flex items-center gap-2.5 w-full p-2 rounded-lg text-muted-foreground/60 hover:text-foreground hover:bg-hover/60 transition-all duration-150 text-small"
          >
            <LogOut size={16} className="text-muted-foreground/40" />
            Logout
          </button>
          <div className="flex items-center gap-2.5 p-2 mt-1.5 border-t border-border/40 pt-3">
            <div className="w-7 h-7 rounded-full bg-primary/15 flex items-center justify-center text-primary text-[10px] font-bold shrink-0 ring-1 ring-primary/20">
              JD
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-small font-medium text-foreground truncate">Jane Doe</span>
              <span className="text-caption text-muted-foreground/50 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-success" />
                Online
              </span>
            </div>
          </div>
        </div>
      </aside>

      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="fixed top-4 left-4 z-[60] p-2 hover:bg-hover transition-colors rounded-lg text-muted-foreground hover:text-foreground"
        >
          <Menu size={20} />
        </button>
      )}

      <main
        className={cn(
          'flex-1 flex flex-col h-full transition-all duration-300 bg-canvas',
          sidebarOpen ? 'ml-[266px]' : 'ml-0',
        )}
      >
        {children}
      </main>
    </div>
  )
}
