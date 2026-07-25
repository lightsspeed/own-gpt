import { forwardRef, type HTMLAttributes, type ReactNode } from 'react';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'grounded' | 'hybrid' | 'synthesis' | 'web' | 'no_evidence';
  dot?: boolean;
  icon?: ReactNode;
}

const variantClasses: Record<string, string> = {
  default:    'bg-elevated text-text-secondary',
  success:    'bg-successSoft text-success',
  warning:    'bg-warningSoft text-warning',
  danger:     'bg-dangerSoft text-danger',
  info:       'bg-infoSoft text-info',
  grounded:   'bg-successSoft text-success',
  hybrid:     'bg-infoSoft text-info',
  synthesis:  'bg-warningSoft text-warning',
  noEvidence: 'bg-elevated text-text-disabled',
};

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant = 'default', dot = false, icon, className = '', children, ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-micro font-medium ${variantClasses[variant]} ${className}`.trim()}
        {...props}
      >
        {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
        {icon && <span className="shrink-0">{icon}</span>}
        {children}
      </span>
    );
  }
);
Badge.displayName = 'Badge';
