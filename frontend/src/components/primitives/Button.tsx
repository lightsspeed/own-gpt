import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cn } from '@/lib/utils';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  asChild?: boolean;
  loading?: boolean;
  icon?: ReactNode;
}

const variantClasses: Record<string, string> = {
  primary:   'bg-accent text-white hover:brightness-110',
  secondary: 'border border-border bg-transparent text-text-primary hover:bg-hover',
  ghost:     'bg-transparent text-text-secondary hover:text-text-primary hover:bg-hover',
  danger:    'bg-danger text-white hover:brightness-110',
};

const sizeClasses: Record<string, string> = {
  sm: 'h-8 px-3 text-small rounded-lg',
  md: 'h-10 px-4 text-body rounded-lg',
  lg: 'h-12 px-6 text-body rounded-lg',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', asChild = false, loading = false, icon, className = '', children, disabled, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    const classes = cn(
      'inline-flex items-center justify-center gap-2 font-medium',
      'active:scale-[0.98] transition-all duration-150',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
      'disabled:pointer-events-none disabled:opacity-50',
      variantClasses[variant],
      sizeClasses[size],
      className,
    );

    return (
      <Comp
        ref={ref}
        className={classes}
        disabled={disabled || loading}
        {...props}
      >
        {loading ? (
          <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        ) : icon ? (
          <span className="shrink-0">{icon}</span>
        ) : null}
        {children && <span>{children}</span>}
      </Comp>
    );
  }
);
Button.displayName = 'Button';
