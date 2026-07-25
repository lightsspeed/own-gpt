import { Outlet, Link, useLocation } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/', label: 'Workspace' },
  { to: '/chat', label: 'Legacy Chat' },
  { to: '/ui-lab', label: 'UI Lab' },
];

/**
 * RootLayout — dev navigation + route content.
 * The AppShell layout is handled per-route:
 *   /          → AppShellDemo (owns sidebar/header/workspace)
 *   /chat      → Legacy ChatLayout (owns its own layout)
 *   /ui-lab    → PageContainer (design system reference)
 */
export function RootLayout() {
  const location = useLocation();

  return (
    <div className="flex h-screen w-full flex-col bg-canvas">
      {/* Dev navigation bar — removed post-Wave 1 */}
      <nav className="flex items-center gap-4 border-b border-border px-4 py-2 shrink-0">
        <span className="text-small text-text-secondary font-medium mr-2">Wave 1:</span>
        {NAV_ITEMS.map(item => (
          <Link
            key={item.to}
            to={item.to}
            className={`text-small px-3 py-1 rounded-md transition-colors ${
              location.pathname === item.to
                ? 'bg-elevated text-text-primary'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}
