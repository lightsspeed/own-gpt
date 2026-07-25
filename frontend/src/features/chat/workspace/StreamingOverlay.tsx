import { useState, useEffect } from 'react';
import type { PipelineStage } from '../types';
import { cn } from '@/lib/utils';

export interface StreamingOverlayProps {
  visible: boolean;
  stages?: PipelineStage[];
}

const stageIcons: Record<string, React.ReactNode> = {
  thinking: (
    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <path d="M12 17h.01" />
    </svg>
  ),
  routing: (
    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </svg>
  ),
  retrieving: (
    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  ),
  reranking: (
    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 6h18M9 12h6M5 18h14" />
    </svg>
  ),
  generating: (
    <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v18M3 12h18" />
      <path d="m8 8 8 8M16 8l-8 8" />
    </svg>
  ),
};

/** Format ms to a short human string */
function fmt(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function StreamingOverlay({ visible, stages }: StreamingOverlayProps) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!visible) return;
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [visible]);

  if (!visible || !stages) return null;

  const activeIdx = stages.findIndex(s => s.status === 'active');

  return (
    <div className="flex items-center justify-center gap-1.5 px-4 py-2 animate-fade-in">
      <div className="flex items-center gap-2 text-small text-text-secondary">
        {stages.map((stage, i) => (
          <div key={stage.id} className="flex items-center gap-1.5">
            {i > 0 && (
              <span className={cn(
                'text-text-disabled select-none',
                i <= activeIdx && 'text-accent/40',
              )}>—</span>
            )}
            <div
              className={cn(
                'flex items-center gap-1 rounded-full px-2 py-0.5 transition-all duration-300',
                stage.status === 'active' && 'bg-accent/10',
                stage.status === 'done' && 'bg-success/10',
              )}
            >
              {/* Icon or checkmark */}
              <span className={cn(
                'shrink-0',
                stage.status === 'waiting' && 'text-text-disabled',
                stage.status === 'active' && 'text-accent',
                stage.status === 'done' && 'text-success',
              )}>
                {stage.status === 'done' ? (
                  <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  stageIcons[stage.id] || null
                )}
              </span>

              {/* Label */}
              <span className={cn(
                'whitespace-nowrap text-[11px] font-medium tracking-wide uppercase',
                stage.status === 'waiting' && 'text-text-disabled',
                stage.status === 'active' && 'text-accent',
                stage.status === 'done' && 'text-success',
              )}>
                {stage.label}
              </span>

              {/* Timing */}
              {(stage.status === 'active' || stage.status === 'done') && (
                <span className={cn(
                  'text-[10px] tabular-nums',
                  stage.status === 'active' && 'text-accent/60',
                  stage.status === 'done' && 'text-success/60',
                )}>
                  {stage.status === 'active' && stage.startedAt
                    ? fmt(now - stage.startedAt)
                    : stage.status === 'done' && stage.elapsedMs != null
                      ? fmt(stage.elapsedMs)
                      : null}
                </span>
              )}

              {/* Active pulsing dot */}
              {stage.status === 'active' && (
                <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
