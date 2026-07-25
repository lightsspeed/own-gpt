import { type ReactNode } from 'react';
import { Stack } from '@/components/layout/Stack';
import { Button } from './Button';

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ icon, title, description, action, secondaryAction }: EmptyStateProps) {
  return (
    <Stack gap="md" align="center" className="py-16 px-4 text-center">
      {icon && (
        <div className="text-text-disabled mb-2">
          {icon}
        </div>
      )}
      <h3 className="text-title text-text-primary">{title}</h3>
      {description && (
        <p className="text-body text-text-secondary max-w-sm">{description}</p>
      )}
      {action && (
        <div className="mt-2">
          <Button variant="primary" size="md" onClick={action.onClick}>
            {action.label}
          </Button>
        </div>
      )}
      {secondaryAction && (
        <Button variant="ghost" size="sm" onClick={secondaryAction.onClick}>
          {secondaryAction.label}
        </Button>
      )}
    </Stack>
  );
}
