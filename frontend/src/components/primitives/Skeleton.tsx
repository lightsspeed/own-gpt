import { forwardRef, type HTMLAttributes } from 'react';

export interface SkeletonProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'text' | 'circular' | 'rectangular';
  width?: string | number;
  height?: string | number;
}

export const Skeleton = forwardRef<HTMLDivElement, SkeletonProps>(
  ({ variant = 'text', width, height, className = '', style, ...props }, ref) => {
    const sizeStyles: Record<string, string> = {
      text:        'h-4 w-full rounded-md',
      circular:    'h-10 w-10 rounded-full',
      rectangular: 'rounded-lg',
    };

    const classes = [
      'animate-pulse bg-elevated',
      sizeStyles[variant],
      className,
    ].filter(Boolean).join(' ');

    return (
      <div
        ref={ref}
        className={classes}
        style={{ width, height, ...style }}
        aria-hidden="true"
        {...props}
      />
    );
  }
);
Skeleton.displayName = 'Skeleton';
