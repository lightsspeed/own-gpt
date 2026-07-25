import { forwardRef, type HTMLAttributes } from 'react';
import { Stack } from './Stack';

export interface SectionProps extends HTMLAttributes<HTMLElement> {
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  as?: 'section' | 'article' | 'div';
}

export const Section = forwardRef<HTMLElement, SectionProps>(
  ({ title, description, action, as: Tag = 'section', className = '', children, ...props }, ref) => {
    return (
      <Tag ref={ref} className={className} {...props}>
        {(title || description || action) && (
          <div className="flex items-start justify-between mb-4">
            <Stack gap="xs">
              {title && (
                <h2 className="text-title text-text-primary">{title}</h2>
              )}
              {description && (
                <p className="text-small text-text-secondary">{description}</p>
              )}
            </Stack>
            {action && (
              <div className="shrink-0 ml-4">{action}</div>
            )}
          </div>
        )}
        {children}
      </Tag>
    );
  }
);
Section.displayName = 'Section';
