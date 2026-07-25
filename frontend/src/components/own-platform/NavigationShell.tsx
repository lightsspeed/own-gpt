import { useState } from 'react'
import { cn } from '@/lib/utils'
import {
  Sparkles, History, Settings, HelpCircle, LogOut,
  Menu, Activity, Search, PanelLeftClose, Zap, Monitor,
  BookOpen, Beaker, BarChart3, GitBranch, Archive, Cog,
} from 'lucide-react'

export interface NavItem {
  id: string
  label: string
  icon: React.ReactNode
  path: string
  children?: NavItem[]
}

const DEFAULT_NAV_ITEMS: NavItem[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: <Activity size={20} />,
    path: '/dashboard',
  },
  {
    id: 'owngpt',
    label: 'OwnGPT',
    icon: <Sparkles size={20} />,
    path: '/',
  },
  {
    id: 'ownops',
    label: 'OwnOps',
    icon: <Zap size={20} />,
    path: '/operations',
    children: [
      { id: 'findings', label: 'Findings', icon: null, path: '/findings' },
      { id: 'evaluation', label: 'Evaluation', icon: null, path: '/evaluation' },
    ],
  },
  {
    id: 'ownmonitor',
    label: 'OwnMonitor',
    icon: <Monitor size={20} />,
    path: '/monitor',
    children: [
      { id: 'recommendations', label: 'Recommendations', icon: null, path: '/recommendations' },
      { id: 'decisions', label: 'Decisions', icon: null, path: '/decisions' },
    ],
  },
  {
    id: 'ownlearn',
    label: 'OwnLearn',
    icon: <BookOpen size={20} />,
    path: '/learn',
    children: [
      { id: 'capabilities', label: 'Capabilities', icon: null, path: '/capabilities' },
    ],
  },
  {
    id: 'ownlab',
    label: 'OwnLab',
    icon: <Beaker size={20} />,
    path: '/experiments',
  },
  {
    id: 'ownanalytics',
    label: 'OwnAnalytics',
    icon: <BarChart3 size={20} />,
    path: '/analytics',
  },
  {
    id: 'ownflow',
    label: 'OwnFlow',
    icon: <GitBranch size={20} />,
    path: '/automation',
  },
  {
    id: 'ownartifacts',
    label: 'OwnArtifacts',
    icon: <Archive size={20} />,
    path: '/artifacts',
  },
  {
    id: 'ownconfig',
    label: 'OwnConfig',
    icon: <Cog size={20} />,
    path: '/config/snapshots',
  },
]

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
  const [searchQuery, setSearchQuery] = useState('')

  const toggleSection = (id: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
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
          'h-[calc(100vh-16px)] w-[280px]',
          sidebarOpen ? 'left-2' : '-left-[296px]',
        )}
      >
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
              <span className="text-small font-bold text-foreground">Own Platform</span>
              <span className="text-caption text-muted-foreground">AI Engineering</span>
            </div>
          </div>
          <button onClick={() => setSidebarOpen(false)} className="p-2 hover:bg-hover transition-colors rounded-lg text-muted-foreground hover:text-foreground active:scale-95" title="Close sidebar">
            <PanelLeftClose size={18} />
          </button>
        </div>

        <div className="px-4 mb-2 shrink-0">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/60" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search..."
              className="w-full rounded-lg border border-border bg-background/50 py-1.5 pl-8 pr-3 text-small text-foreground placeholder:text-muted-foreground/40 outline-none transition-colors focus:border-primary/40"
            />
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 custom-scrollbar">
          <div className="space-y-0.5">
            {filteredItems.map(item => (
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
                    'group relative flex items-center gap-3 w-full rounded-lg px-3 py-2.5 transition-all text-left',
                    isActive(item.path)
                      ? 'bg-elevated text-foreground font-semibold'
                      : 'text-muted-foreground hover:text-foreground hover:bg-hover',
                  )}
                >
                  {item.id === currentPath.split('/')[1] && (
                    <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary" />
                  )}
                  {item.icon && <span className="shrink-0">{item.icon}</span>}
                  <span className="text-small flex-1">{item.label}</span>
                  {item.children && (
                    <span className={cn(
                      'text-muted-foreground transition-transform',
                      expandedSections.has(item.id) && 'rotate-180',
                    )}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="m6 9 6 6 6-6" />
                      </svg>
                    </span>
                  )}
                </button>
                {item.children && expandedSections.has(item.id) && (
                  <div className="ml-3 space-y-0.5 mt-0.5">
                    {item.children.map(child => (
                      <button
                        key={child.id}
                        onClick={() => onNavigate?.(child.path)}
                        className={cn(
                          'flex items-center gap-3 w-full rounded-lg py-2 px-3 transition-all text-left text-small',
                          isActive(child.path)
                            ? 'text-foreground bg-elevated font-semibold'
                            : 'text-muted-foreground hover:text-foreground hover:bg-hover',
                        )}
                      >
                        {child.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </nav>

        <div className="shrink-0 border-t border-border px-3 py-3 mt-2">
          <button
            onClick={() => onNavigate?.('/history')}
            className="flex items-center gap-3 w-full p-2.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-hover transition-colors text-small"
          >
            <History size={16} />
            History
          </button>
          <button
            onClick={() => onNavigate?.('/settings')}
            className="flex items-center gap-3 w-full p-2.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-hover transition-colors text-small"
          >
            <Settings size={16} />
            Settings
          </button>
          <button
            onClick={() => window.open('https://opencode.ai/docs', '_blank')}
            className="flex items-center gap-3 w-full p-2.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-hover transition-colors text-small"
          >
            <HelpCircle size={16} />
            Help
          </button>
          <button
            onClick={() => { localStorage.clear(); window.location.href = '/' }}
            className="flex items-center gap-3 w-full p-2.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-hover transition-colors text-small"
          >
            <LogOut size={16} />
            Logout
          </button>
          <div className="flex items-center gap-3 p-2.5 mt-2 border-t border-border pt-4">
            <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-white text-[10px] font-bold shrink-0">
              JD
            </div>
            <div className="flex flex-col min-w-0">
              <span className="text-small font-medium text-foreground truncate">Jane Doe</span>
              <span className="text-caption text-muted-foreground">Engineering Lead</span>
            </div>
          </div>
        </div>
      </aside>

      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="fixed top-4 left-4 z-[60] p-2 hover:bg-hover transition-colors rounded-lg text-muted-foreground hover:text-foreground active:scale-95"
        >
          <Menu size={20} />
        </button>
      )}

      <main
        className={cn(
          'flex-1 flex flex-col h-full transition-all duration-300 bg-canvas',
          sidebarOpen ? 'ml-[296px]' : 'ml-0',
        )}
      >
        {children}
      </main>
    </div>
  )
}