import { forwardRef, type HTMLAttributes } from 'react';
import { gap as gapTokens, type SpacingToken } from '@/design-system';

type Gap = keyof typeof gapTokens | SpacingToken;

export interface StackProps extends HTMLAttributes<HTMLDivElement> {
  gap?: Gap;
  align?: 'start' | 'center' | 'end' | 'stretch';
  as?: 'div' | 'section' | 'article' | 'aside' | 'nav' | 'main' | 'header' | 'footer';
}

const alignMap: Record<string, string> = {
  start: 'items-start',
  center: 'items-center',
  end: 'items-end',
  stretch: 'items-stretch',
};

const gapClass = (g: Gap): string => {
  const v = typeof g === 'number' ? g : (gapTokens[g as keyof typeof gapTokens] ?? g);
  if (typeof v === 'number') return `gap-${v}`;
  return `gap-${v}`;
};

export const Stack = forwardRef<HTMLDivElement, StackProps>(
  ({ gap = 'md', align = 'stretch', className = '', as: Tag = 'div', children, ...props }, ref) => {
    return (
      <Tag
        ref={ref}
        className={`flex flex-col ${alignMap[align]} ${gapClass(gap)} ${className}`.trim()}
        {...props}
      >
        {children}
      </Tag>
    );
  }
);
Stack.displayName = 'Stack';
