import { cn } from '@/lib/utils';
import type { AnswerMode } from '@/design-system/ai';
import { answerModeText, answerModeBg } from '@/design-system/ai';
import { ModeCard } from './ModeCard';
import { SourceCard } from './SourceCard';
import { ConfidenceMeter } from './ConfidenceMeter';
import { PipelineSummary } from './PipelineSummary';
import { DebugAccordion } from './DebugAccordion';

export interface EvidenceResource {
  type: 'web' | 'file';
  title: string;
  url?: string;
  snippet?: string;
}

export interface EvidencePanelProps {
  answerMode?: AnswerMode;
  retrievalMethod?: string;
  chunkCount?: number;
  docCount?: number;
  confidence?: number;
  resources?: EvidenceResource[];
  retrievedCount?: number;
  isStreaming?: boolean;
  className?: string;
}

export function EvidencePanel({
  answerMode,
  retrievalMethod,
  chunkCount,
  docCount,
  confidence,
  resources,
  retrievedCount,
  isStreaming,
  className,
}: EvidencePanelProps) {
  const hasEvidence = answerMode && answerMode !== 'no_evidence' && !isStreaming;
  const hasResources = resources && resources.length > 0;

  if (!hasEvidence && !hasResources) return null;

  return (
    <div className={cn('mt-4 space-y-3', className)}>
      {/* Mode card */}
      {hasEvidence && answerMode && (
        <ModeCard
          answerMode={answerMode}
          retrievalMethod={retrievalMethod}
          chunkCount={chunkCount}
          docCount={docCount}
        />
      )}

      {/* Pipeline summary + Confidence (side by side on wide messages) */}
      {(confidence != null || (retrievedCount != null && chunkCount != null)) && hasEvidence && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {retrievedCount != null && chunkCount != null && (
            <PipelineSummary
              retrievedCount={retrievedCount}
              rerankedCount={chunkCount}
              docCount={docCount}
              method={retrievalMethod}
            />
          )}
          {confidence != null && (
            <ConfidenceMeter confidence={confidence} />
          )}
        </div>
      )}

      {/* Resources */}
      {hasResources && (
        <div className="space-y-2">
          <span className={cn(
            'flex items-center gap-1.5 text-micro font-medium uppercase tracking-[0.1em]',
            answerMode ? answerModeText(answerMode) : 'text-text-disabled',
          )}>
            {answerMode === 'web' ? (
              <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
            ) : (
              <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
            )}
            {answerMode === 'web' ? 'Web Sources' : 'Reference Material'}
          </span>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {resources.map((res, i) => (
              <SourceCard
                key={i}
                title={res.title}
                type={res.type}
                url={res.url}
                snippet={res.snippet}
                grounding={confidence != null && confidence >= 0.9 ? 'high' : confidence != null && confidence >= 0.7 ? 'medium' : 'low'}
              />
            ))}
          </div>
        </div>
      )}

      {/* Debug accordion */}
      {hasEvidence && answerMode && (
        <DebugAccordion
          answerMode={answerMode}
          retrievalMethod={retrievalMethod}
          chunkCount={chunkCount}
          docCount={docCount}
          confidence={confidence}
          retrievedCount={retrievedCount}
        />
      )}
    </div>
  );
}
