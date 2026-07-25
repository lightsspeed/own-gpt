import { useNavigate, useLocation, Outlet } from 'react-router-dom'
import { NavigationShell } from '@/components/own-platform/NavigationShell'

export function OwnPlatformLayout() {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <NavigationShell
      currentPath={location.pathname}
      onNavigate={(path: string) => navigate(path)}
    >
      <Outlet />
    </NavigationShell>
  )
}
