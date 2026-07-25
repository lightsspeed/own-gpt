import { forwardRef, type HTMLAttributes } from 'react';

export interface HeaderProps extends HTMLAttributes<HTMLElement> {
  height?: 'sm' | 'md' | 'lg';
}

const heightClasses: Record<string, string> = {
  sm: 'h-12',
  md: 'h-14',
  lg: 'h-16',
};

export const Header = forwardRef<HTMLDivElement, HeaderProps>(
  ({ height = 'md', className = '', children, ...props }, ref) => {
    return (
      <header
        ref={ref}
        className={`flex items-center gap-3 bg-canvas px-4 ${heightClasses[height]} ${className}`.trim()}
        {...props}
      >
        {children}
      </header>
    );
  }
);
Header.displayName = 'Header';
