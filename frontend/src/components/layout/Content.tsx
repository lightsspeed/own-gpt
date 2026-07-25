import { forwardRef, type HTMLAttributes } from 'react';

export interface ContentProps extends HTMLAttributes<HTMLDivElement> {
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl';
}

const maxWidthClasses: Record<string, string> = {
  sm: 'max-w-screen-sm',
  md: 'max-w-screen-md',
  lg: 'max-w-screen-lg',
  xl: 'max-w-[800px]',
};

export const Content = forwardRef<HTMLDivElement, ContentProps>(
  ({ maxWidth = 'xl', className = '', children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`mx-auto w-full px-4 py-6 ${maxWidthClasses[maxWidth]} ${className}`.trim()}
        {...props}
      >
        {children}
      </div>
    );
  }
);
Content.displayName = 'Content';
