import { forwardRef, type HTMLAttributes } from 'react';

export interface InlineProps extends HTMLAttributes<HTMLDivElement> {
  gap?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  align?: 'start' | 'center' | 'end' | 'stretch' | 'baseline';
  wrap?: boolean;
  as?: 'div' | 'span' | 'nav';
}

const gapMap: Record<string, string> = {
  xs: 'gap-1',
  sm: 'gap-2',
  md: 'gap-3',
  lg: 'gap-4',
  xl: 'gap-6',
};

const alignMap: Record<string, string> = {
  start: 'items-start',
  center: 'items-center',
  end: 'items-end',
  stretch: 'items-stretch',
  baseline: 'items-baseline',
};

export const Inline = forwardRef<HTMLDivElement, InlineProps>(
  ({ gap = 'sm', align = 'center', wrap = false, className = '', as: Tag = 'div', children, ...props }, ref) => {
    const classes = [
      'flex flex-row',
      alignMap[align],
      gapMap[gap],
      wrap && 'flex-wrap',
      className,
    ].filter(Boolean).join(' ');

    return (
      <Tag ref={ref} className={classes} {...props}>
        {children}
      </Tag>
    );
  }
);
Inline.displayName = 'Inline';
