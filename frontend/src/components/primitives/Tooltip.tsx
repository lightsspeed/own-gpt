import { type ReactNode } from 'react';
import {
  Tooltip as ShadcnTooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

export interface TooltipProps {
  content: ReactNode;
  side?: 'top' | 'bottom' | 'left' | 'right';
  delay?: number;
  children: ReactNode;
}

export function Tooltip({ content, side = 'top', delay = 400, children }: TooltipProps) {
  return (
    <TooltipProvider delayDuration={delay}>
      <ShadcnTooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent side={side} className="text-small bg-elevated text-text-primary border border-border shadow-md">
          {content}
        </TooltipContent>
      </ShadcnTooltip>
    </TooltipProvider>
  );
}
