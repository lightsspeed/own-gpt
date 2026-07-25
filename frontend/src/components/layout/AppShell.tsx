import { forwardRef, type HTMLAttributes } from 'react';

export interface AppShellProps extends HTMLAttributes<HTMLDivElement> {
  sidebar?: React.ReactNode;
  header?: React.ReactNode;
  sidebarWidth?: 'narrow' | 'normal' | 'wide';
}

const sidebarWidthClasses: Record<string, string> = {
  narrow: 'w-[240px]',
  normal: 'w-[280px]',
  wide:   'w-[320px]',
};

export const AppShell = forwardRef<HTMLDivElement, AppShellProps>(
  ({ sidebar, header, sidebarWidth = 'normal', className = '', children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`flex h-screen w-full overflow-hidden bg-canvas ${className}`.trim()}
        {...props}
      >
        {sidebar && (
          <aside className={`hidden lg:flex flex-col border-r border-border ${sidebarWidthClasses[sidebarWidth]} shrink-0`}>
            {sidebar}
          </aside>
        )}

        <div className="flex flex-1 flex-col min-w-0">
          {header && (
            <header className="shrink-0 border-b border-border">
              {header}
            </header>
          )}
          <main className="flex-1 overflow-y-auto">
            {children}
          </main>
        </div>
      </div>
    );
  }
);
AppShell.displayName = 'AppShell';
