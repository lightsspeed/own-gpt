import { forwardRef, type HTMLAttributes } from 'react';

export interface ScrollAreaProps extends HTMLAttributes<HTMLDivElement> {
  hideScrollbar?: boolean;
}

export const ScrollArea = forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ hideScrollbar = false, className = '', children, ...props }, ref) => {
    const classes = [
      'overflow-y-auto',
      hideScrollbar ? 'scrollbar-none' : '',
      className,
    ].filter(Boolean).join(' ');

    return (
      <div ref={ref} className={classes} {...props}>
        {children}
      </div>
    );
  }
);
ScrollArea.displayName = 'ScrollArea';
