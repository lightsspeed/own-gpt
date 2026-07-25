import { cn } from '@/lib/utils';

export interface ConfidenceMeterProps {
  confidence: number;
  className?: string;
}

function confidenceColor(value: number): string {
  if (value >= 0.9) return 'bg-success';
  if (value >= 0.7) return 'bg-warning';
  return 'bg-danger';
}

function confidenceTrackColor(value: number): string {
  if (value >= 0.9) return 'bg-success/15';
  if (value >= 0.7) return 'bg-warning/15';
  return 'bg-danger/15';
}

export function ConfidenceMeter({ confidence, className }: ConfidenceMeterProps) {
  const pct = Math.round(confidence * 100);

  return (
    <div className={cn('space-y-1.5', className)}>
      <div className="flex items-center justify-between">
        <span className="text-small text-text-secondary">Confidence</span>
        <span className="text-small font-semibold text-text-primary tabular-nums">{pct}%</span>
      </div>
      <div className={cn('h-1.5 w-full rounded-full overflow-hidden', confidenceTrackColor(confidence))}>
        <div
          className={cn('h-full rounded-full transition-all duration-500', confidenceColor(confidence))}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
