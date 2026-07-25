import { cn } from '@/lib/utils';

export interface PipelineSummaryProps {
  retrievedCount?: number;
  rerankedCount?: number;
  docCount?: number;
  method?: string;
  className?: string;
}

export function PipelineSummary({ retrievedCount, rerankedCount, docCount, method, className }: PipelineSummaryProps) {
  const stages: { label: string; value: string; color: string }[] = [];

  if (retrievedCount != null) {
    stages.push({ label: 'Retrieved', value: String(retrievedCount), color: 'text-accent' });
  }
  if (rerankedCount != null) {
    stages.push({ label: 'FlashRank', value: String(rerankedCount), color: 'text-warning' });
  }
  if (docCount != null) {
    stages.push({ label: 'Context', value: `${docCount} doc${docCount !== 1 ? 's' : ''}`, color: 'text-success' });
  }

  if (stages.length === 0) return null;

  return (
    <div className={cn('space-y-1.5', className)}>
      <span className="text-micro font-medium uppercase tracking-[0.1em] text-text-disabled">Retrieval Pipeline</span>
      <div className="flex items-center gap-2">
        {stages.map((stage, i) => (
          <div key={stage.label} className="flex items-center gap-2">
            {i > 0 && (
              <svg className="h-3 w-3 shrink-0 text-text-disabled" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            )}
            <div className="flex flex-col items-center rounded-lg border border-border bg-elevated px-2.5 py-1.5 min-w-[56px]">
              <span className={cn('text-small font-semibold tabular-nums', stage.color)}>{stage.value}</span>
              <span className="text-micro text-text-disabled">{stage.label}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
