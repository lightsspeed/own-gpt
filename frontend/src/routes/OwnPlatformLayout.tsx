import { useNavigate, useLocation, Outlet } from 'react-router-dom'
import { BookOpen } from 'lucide-react'
import { NavigationShell, type NavItem } from '@/components/own-platform/NavigationShell'

const KB_NAV_ITEMS: NavItem[] = [
  {
    id: 'ownlearn',
    label: 'OwnLearn',
    icon: <BookOpen size={18} />,
    path: '/learn',
    children: [
      { id: 'knowledge-base', label: 'Knowledge Base', icon: null, path: '/learn' },
      { id: 'capabilities', label: 'Capabilities', icon: null, path: '/capabilities' },
    ],
  },
]

export function OwnPlatformLayout() {
  const navigate = useNavigate()
  const location = useLocation()

  const isKnowledgeBase = location.pathname.startsWith('/learn')

  return (
    <NavigationShell
      currentPath={location.pathname}
      onNavigate={(path: string) => navigate(path)}
      navItems={isKnowledgeBase ? KB_NAV_ITEMS : undefined}
    >
      <Outlet />
    </NavigationShell>
  )
}
