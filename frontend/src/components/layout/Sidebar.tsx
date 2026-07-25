import { forwardRef, type HTMLAttributes } from 'react';
import { Stack } from './Stack';

export interface SidebarProps extends HTMLAttributes<HTMLDivElement> {
  header?: React.ReactNode;
  footer?: React.ReactNode;
}

export const Sidebar = forwardRef<HTMLDivElement, SidebarProps>(
  ({ header, footer, className = '', children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`flex h-full flex-col bg-canvas ${className}`.trim()}
        {...props}
      >
        {header && (
          <div className="shrink-0 px-4 py-3">{header}</div>
        )}
        <div className="flex-1 overflow-y-auto px-2 py-2">
          <Stack gap="xs">
            {children}
          </Stack>
        </div>
        {footer && (
          <div className="shrink-0 border-t border-border px-4 py-3">{footer}</div>
        )}
      </div>
    );
  }
);
Sidebar.displayName = 'Sidebar';
