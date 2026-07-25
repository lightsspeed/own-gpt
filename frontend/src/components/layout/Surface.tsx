import { forwardRef, type HTMLAttributes } from 'react';

export interface SurfaceProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'canvas' | 'surface' | 'elevated' | 'overlay' | 'hover' | 'glass' | 'transparent';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  as?: 'div' | 'section' | 'article' | 'aside' | 'main';
}

const variantClasses: Record<string, string> = {
  canvas:      'bg-canvas',
  surface:     'bg-surface border border-border',
  elevated:    'bg-elevated border border-border shadow-sm',
  overlay:     'bg-overlay border border-border shadow-md',
  hover:       'bg-hover',
  glass:       'glass-panel',
  transparent: 'bg-transparent',
};

const paddingClasses: Record<string, string> = {
  none: '',
  sm:   'p-2',
  md:   'p-3',
  lg:   'p-4',
};

export const Surface = forwardRef<HTMLDivElement, SurfaceProps>(
  ({ variant = 'surface', padding = 'lg', className = '', as: Tag = 'div', children, ...props }, ref) => {
    const classes = [
      'rounded-xl',
      variantClasses[variant] || variantClasses.surface,
      paddingClasses[padding] || paddingClasses.lg,
      className,
    ].join(' ');

    return (
      <Tag ref={ref} className={classes} {...props}>
        {children}
      </Tag>
    );
  }
);
Surface.displayName = 'Surface';
