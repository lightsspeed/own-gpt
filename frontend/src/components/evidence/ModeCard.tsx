import { cn } from '@/lib/utils';
import type { AnswerMode } from '@/design-system/ai';
import { answerModes, answerModeText, answerModeBg } from '@/design-system/ai';

export interface ModeCardProps {
  answerMode: AnswerMode;
  retrievalMethod?: string;
  chunkCount?: number;
  docCount?: number;
  className?: string;
}

const retrievalLabel: Record<string, string> = {
  hybrid: 'Hybrid Search',
  vector: 'Vector Search',
  bm25:   'BM25 Search',
};

const modeIcons: Record<AnswerMode, React.ReactNode> = {
  grounded: (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  ),
  hybrid: (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
    </svg>
  ),
  synthesis: (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v18M3 12h18" /><path d="m8 8 8 8M16 8l-8 8" />
    </svg>
  ),
  no_evidence: (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><path d="m15 9-6 6M9 9l6 6" />
    </svg>
  ),
  web: (
    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  ),
};

export function ModeCard({ answerMode, retrievalMethod, chunkCount, docCount, className }: ModeCardProps) {
  const mode = answerModes[answerMode];
  if (!mode) return null;

  const showStats = (answerMode === 'grounded' || answerMode === 'hybrid') && chunkCount != null;

  return (
    <div className={cn('rounded-xl border border-border bg-surface p-3', className)}>
      <div className="flex items-start gap-3">
        <div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-lg', answerModeBg(answerMode))}>
          <span className={answerModeText(answerMode)}>
            {modeIcons[answerMode]}
          </span>
        </div>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-center gap-2">
            <span className={cn('text-small font-semibold', answerModeText(answerMode))}>
              {mode.label}
            </span>
            {retrievalMethod && (
              <>
                <span className="text-text-disabled">·</span>
                <span className="text-small text-text-secondary">{retrievalLabel[retrievalMethod] || retrievalMethod}</span>
              </>
            )}
          </div>
          <p className="text-micro text-text-secondary">{mode.description}</p>
          {showStats && (
            <div className="flex items-center gap-3 pt-1">
              <span className={cn('text-small font-medium tabular-nums', answerModeText(answerMode))}>
                {chunkCount} supporting chunk{chunkCount !== 1 ? 's' : ''}
              </span>
              {docCount != null && (
                <>
                  <span className="text-text-disabled">·</span>
                  <span className="text-small text-text-secondary">{docCount} document{docCount !== 1 ? 's' : ''}</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
