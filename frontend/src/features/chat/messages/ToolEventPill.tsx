import { cn } from '@/lib/utils';

export interface ToolEventPillProps {
  name: string;
  status: 'calling' | 'done';
  className?: string;
}

const TOOL_CONFIG: Record<string, { label: string; accent: string }> = {
  search_knowledge_base: { label: 'Knowledge Base', accent: 'text-accent border-accent/30 bg-accent/8' },
  search_web:            { label: 'Web Search',     accent: 'text-success border-success/30 bg-success/8' },
  remember_user_fact:    { label: 'Saving Memory',   accent: 'text-info border-info/30 bg-info/8' },
};

export function ToolEventPill({ name, status, className }: ToolEventPillProps) {
  const cfg = TOOL_CONFIG[name] || {
    label: name.replace(/_/g, ' '),
    accent: 'text-text-secondary border-border bg-elevated',
  };

  return (
    <div className={cn('flex justify-center my-1.5', className)}>
      <div className={cn(
        'flex items-center gap-1.5 rounded-full border px-3 py-1 text-small font-medium',
        cfg.accent,
        'animate-fade-in',
      )}>
        {/* Tool icon */}
        {name === 'search_knowledge_base' && (
          <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          </svg>
        )}
        {name === 'search_web' && (
          <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
          </svg>
        )}
        {!['search_knowledge_base', 'search_web', 'remember_user_fact'].includes(name) && (
          <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        )}

        <span>{cfg.label}</span>

        {/* Status indicator */}
        {status === 'calling' && (
          <span className="flex gap-0.5 ml-1">
            <span className="h-1 w-1 rounded-full bg-current animate-bounce" />
            <span className="h-1 w-1 rounded-full bg-current animate-bounce" style={{ animationDelay: '0.15s' }} />
            <span className="h-1 w-1 rounded-full bg-current animate-bounce" style={{ animationDelay: '0.3s' }} />
          </span>
        )}
        {status === 'done' && (
          <svg className="h-3 w-3 ml-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        )}
      </div>
    </div>
  );
}
