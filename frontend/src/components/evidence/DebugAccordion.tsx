import { useState } from 'react';
import { cn } from '@/lib/utils';
import { answerModeText } from '@/design-system/ai';
import type { AnswerMode } from '@/design-system/ai';

export interface DebugAccordionProps {
  answerMode: AnswerMode;
  retrievalMethod?: string;
  chunkCount?: number;
  docCount?: number;
  confidence?: number;
  retrievedCount?: number;
  className?: string;
}

const methodLabels: Record<string, string> = {
  hybrid: 'Hybrid (Vector + BM25)',
  vector: 'Vector (Semantic)',
  bm25:   'BM25 (Keyword)',
};

export function DebugAccordion({ answerMode, retrievalMethod, chunkCount, docCount, confidence, retrievedCount, className }: DebugAccordionProps) {
  const [open, setOpen] = useState(false);

  const showPipeline = chunkCount != null && docCount != null;

  return (
    <div className={cn('', className)}>
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-micro font-medium text-text-disabled hover:text-text-secondary hover:bg-hover transition-colors"
      >
        <svg
          className={cn('h-3 w-3 transition-transform duration-200', open && 'rotate-90')}
          viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
        Why this answer?
      </button>

      {open && (
        <div className="ml-5 mt-1 space-y-1.5 rounded-lg border border-border bg-elevated px-3 py-2.5 animate-fade-in">
          {/* Retriever */}
          {retrievalMethod && (
            <Row label="Retriever" value={methodLabels[retrievalMethod] || retrievalMethod} />
          )}

          {/* Pipeline */}
          {showPipeline && (
            <Row
              label="Pipeline"
              value={
                <span className="flex items-center gap-1">
                  {retrievedCount != null && <>{retrievedCount} retrieved</>}
                  {retrievedCount != null && chunkCount != null && (
                    <svg className="h-2.5 w-2.5 text-text-disabled" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  )}
                  {chunkCount != null && <>{chunkCount} reranked</>}
                  {chunkCount != null && docCount != null && (
                    <svg className="h-2.5 w-2.5 text-text-disabled" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  )}
                  {docCount != null && <>{docCount} doc{docCount !== 1 ? 's' : ''}</>}
                </span>
              }
            />
          )}

          {/* Answer mode */}
          <Row
            label="Answer mode"
            value={<span className={answerModeText(answerMode)}>{answerMode}</span>}
          />

          {/* Confidence */}
          {confidence != null && (
            <Row label="Confidence" value={`${Math.round(confidence * 100)}%`} />
          )}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-micro text-text-secondary">{label}</span>
      <span className="text-micro font-medium text-text-primary">{value}</span>
    </div>
  );
}
