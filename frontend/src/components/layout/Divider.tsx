import { forwardRef, type HTMLAttributes } from 'react';

export interface DividerProps extends HTMLAttributes<HTMLHRElement> {
  orientation?: 'horizontal' | 'vertical';
  spacing?: 'sm' | 'md' | 'lg';
}

const spacingClasses: Record<string, string> = {
  sm: 'my-2',
  md: 'my-4',
  lg: 'my-6',
};

export const Divider = forwardRef<HTMLHRElement, DividerProps>(
  ({ orientation = 'horizontal', spacing = 'md', className = '', ...props }, ref) => {
    if (orientation === 'vertical') {
      return (
        <div
          ref={ref as any}
          className={`inline-block w-px self-stretch bg-border ${className}`.trim()}
          {...(props as any)}
        />
      );
    }

    return (
      <hr
        ref={ref}
        className={`border-t border-border ${spacingClasses[spacing] || spacingClasses.md} ${className}`.trim()}
        {...props}
      />
    );
  }
);
Divider.displayName = 'Divider';
