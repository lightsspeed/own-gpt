import { forwardRef, type HTMLAttributes } from 'react';

export interface PageContainerProps extends HTMLAttributes<HTMLDivElement> {
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl';
}

const maxWidthClasses: Record<string, string> = {
  sm: 'max-w-screen-sm',
  md: 'max-w-screen-md',
  lg: 'max-w-screen-lg',
  xl: 'max-w-[800px]', /* design system content width */
};

export const PageContainer = forwardRef<HTMLDivElement, PageContainerProps>(
  ({ maxWidth = 'xl', className = '', children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`mx-auto w-full px-4 sm:px-6 ${maxWidthClasses[maxWidth]} ${className}`.trim()}
        {...props}
      >
        {children}
      </div>
    );
  }
);
PageContainer.displayName = 'PageContainer';
