import { cn } from '@/lib/utils';

export interface MessageAvatarProps {
  role: 'user' | 'assistant';
  className?: string;
}

export function MessageAvatar({ role, className }: MessageAvatarProps) {
  return (
    <div className={cn('flex items-center gap-2', className)}>
      {role === 'assistant' ? (
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/15">
          <svg className="h-3.5 w-3.5 text-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3v18M3 12h18" />
            <path d="m8 8 8 8M16 8l-8 8" />
          </svg>
        </div>
      ) : (
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-elevated">
          <svg className="h-3.5 w-3.5 text-text-secondary" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
      )}
    </div>
  );
}
