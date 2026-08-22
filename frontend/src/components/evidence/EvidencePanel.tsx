import { cn } from '@/lib/utils';
import type { AnswerMode } from '@/design-system/ai';
import { answerModeText } from '@/design-system/ai';
import { ModeCard } from './ModeCard';
import { SourceCard } from './SourceCard';
import { ConfidenceMeter } from './ConfidenceMeter';
import { PipelineSummary } from './PipelineSummary';
import { DebugAccordion } from './DebugAccordion';

export interface EvidenceResource {
  type: 'web' | 'file' | 'knowledge';
  title: string;
  url?: string;
  snippet?: string;
  // V3 Phase 5: rich citation fields
  document_id?: string | null;
  chunk_index?: number | null;
  page?: number | null;
  section?: string | null;
  confidence_label?: 'high' | 'medium' | 'low' | 'no_evidence' | null;
}

/** Full EvidenceItem from the backend (mirrors app/models/evidence.py) */
export interface EvidenceItem {
  id: string;
  title: string;
  source_type: 'knowledge' | 'web' | 'memory' | 'file';
  url?: string | null;
  chunk?: string | null;
  confidence_label: 'high' | 'medium' | 'low' | 'no_evidence';
  retrieval_method: string;
  chunk_index?: number | null;
  total_chunks?: number | null;
  document_id?: string | null;
  page?: number | null;
  section?: string | null;
  metadata?: Record<string, unknown>;
}

export interface EvidencePanelProps {
  answerMode?: AnswerMode;
  retrievalMethod?: string;
  chunkCount?: number;
  docCount?: number;
  confidence?: number;
  resources?: EvidenceResource[];
  /** Full EvidenceItem[] from the `evidence` SSE event — preferred over resources when present */
  evidence?: EvidenceItem[];
  retrievedCount?: number;
  isStreaming?: boolean;
  className?: string;
}

/** Derive grounding badge from confidence_label */
function toGrounding(label?: 'high' | 'medium' | 'low' | 'no_evidence' | null): 'high' | 'medium' | 'low' {
  if (label === 'high') return 'high';
  if (label === 'low' || label === 'no_evidence') return 'low';
  return 'medium';
}

export function EvidencePanel({
  answerMode,
  retrievalMethod,
  chunkCount,
  docCount,
  confidence,
  resources,
  evidence,
  retrievedCount,
  isStreaming,
  className,
}: EvidencePanelProps) {
  const hasEvidence = answerMode && answerMode !== 'no_evidence' && !isStreaming;

  // Prefer full EvidenceItem[] when available, fall back to resources
  const hasRichEvidence = evidence && evidence.length > 0;
  const hasResources = resources && resources.length > 0;
  const showSources = hasRichEvidence || hasResources;

  if (!hasEvidence && !showSources) return null;

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

      {/* Sources */}
      {showSources && (
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
            {/* Prefer rich EvidenceItem[] */}
            {hasRichEvidence
              ? evidence!.map((ev, i) => (
                  <SourceCard
                    key={ev.id || i}
                    title={ev.title}
                    type={ev.source_type === 'web' ? 'web' : 'knowledge'}
                    url={ev.url ?? undefined}
                    snippet={ev.chunk ?? undefined}
                    grounding={toGrounding(ev.confidence_label)}
                    // V3 Phase 5: citation transparency
                    documentId={ev.document_id}
                    chunkIndex={ev.chunk_index}
                    page={ev.page}
                    section={ev.section}
                    confidenceLabel={ev.confidence_label}
                  />
                ))
              : resources!.map((res, i) => (
                  <SourceCard
                    key={i}
                    title={res.title}
                    type={res.type === 'knowledge' ? 'knowledge' : res.type}
                    url={res.url}
                    snippet={res.snippet}
                    grounding={toGrounding(res.confidence_label)}
                    // V3 Phase 5: rich fields from enriched resources event
                    documentId={res.document_id}
                    chunkIndex={res.chunk_index}
                    page={res.page}
                    section={res.section}
                    confidenceLabel={res.confidence_label}
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
