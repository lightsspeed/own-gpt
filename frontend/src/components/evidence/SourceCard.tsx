import { useState } from 'react';
import { cn } from '@/lib/utils';
import { SourceInspectorModal } from './SourceInspectorModal';
import { DocumentViewerModal } from '@/components/documents/DocumentViewerModal';

export interface SourceCardProps {
  title: string;
  type: 'web' | 'file' | 'knowledge';
  url?: string;
  snippet?: string;
  pages?: string;
  chunks?: number;
  grounding?: 'high' | 'medium' | 'low';
  className?: string;
  // V3 Phase 5: citation transparency
  documentId?: string | null;
  chunkIndex?: number | null;
  page?: number | null;
  section?: string | null;
  confidenceLabel?: 'high' | 'medium' | 'low' | 'no_evidence' | null;
}

const groundingConfig = {
  high:   { label: 'High',   class: 'text-success bg-success/10' },
  medium: { label: 'Medium', class: 'text-warning bg-warning/10' },
  low:    { label: 'Low',    class: 'text-danger bg-danger/10' },
} as const;

export function SourceCard({
  title, type, url, snippet, pages, chunks, grounding = 'medium', className,
  documentId, chunkIndex, page, section, confidenceLabel,
}: SourceCardProps) {
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [docViewerOpen, setDocViewerOpen] = useState(false);

  const isWeb = type === 'web';
  const hostname = isWeb && url ? (() => { try { return new URL(url).hostname.replace('www.', ''); } catch { return ''; } })() : '';

  // Resolve effective grounding badge from confidence_label when available
  const effectiveGrounding: 'high' | 'medium' | 'low' =
    confidenceLabel === 'high' ? 'high'
    : confidenceLabel === 'low' || confidenceLabel === 'no_evidence' ? 'low'
    : grounding;

  return (
    <>
      <div className={cn(
        'group relative rounded-xl border border-border bg-surface p-3 transition-all',
        'hover:border-accent/20 hover:bg-elevated',
        className,
      )}>
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div className={cn(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
            isWeb ? 'bg-success/10' : 'bg-accent/10',
          )}>
            {isWeb ? (
              <svg className="h-4 w-4 text-success" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
            ) : (
              <svg className="h-4 w-4 text-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
            )}
          </div>

          {/* Body */}
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-small font-medium text-text-primary">{title}</span>
              {isWeb && hostname && (
                <span className="shrink-0 text-micro text-text-disabled">{hostname}</span>
              )}
            </div>

            {/* Metadata */}
            <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
              {pages && <span className="text-micro text-text-secondary">Pages {pages}</span>}
              {/* V3 Phase 5: page + section from chunk metadata */}
              {page != null && !pages && <span className="text-micro text-text-secondary">Page {page}</span>}
              {section && <span className="text-micro text-text-secondary truncate max-w-[120px]" title={section}>{section}</span>}
              {chunks != null && <span className="text-micro text-text-secondary">{chunks} chunk{chunks !== 1 ? 's' : ''}</span>}
              <span className={cn('rounded-full px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wider', groundingConfig[effectiveGrounding].class)}>
                {groundingConfig[effectiveGrounding].label}
              </span>
            </div>

            {/* Snippet preview */}
            {snippet && (
              <p className="text-micro text-text-secondary line-clamp-2 leading-relaxed">{snippet}</p>
            )}
          </div>
        </div>

        {/* Action buttons — appear on hover */}
        <div className="mt-2 flex items-center gap-2 border-t border-border/50 pt-2 opacity-0 group-hover:opacity-100 transition-opacity">
          {isWeb && url && (
            <a href={url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-text-secondary hover:text-text-primary hover:bg-hover transition-colors">
              <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
              </svg>
              Open
            </a>
          )}
          {/* V3 Phase 5: functional Preview button */}
          <button
            onClick={() => setInspectorOpen(true)}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium text-text-secondary hover:text-text-primary hover:bg-hover transition-colors"
          >
            <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
            </svg>
            Preview
          </button>
        </div>
      </div>

      {/* Source Inspector Modal */}
      {inspectorOpen && (
        <SourceInspectorModal
          title={title}
          type={type}
          url={url}
          documentId={documentId}
          chunkIndex={chunkIndex}
          page={page}
          section={section}
          snippet={snippet}
          confidenceLabel={confidenceLabel}
          onClose={() => setInspectorOpen(false)}
          onOpenDocument={(filename) => {
            setInspectorOpen(false);
            setDocViewerOpen(true);
          }}
        />
      )}

      {/* Full Document Viewer */}
      {docViewerOpen && (
        <DocumentViewerModal
          document={{ filename: documentId || title, chunks: chunks || 0 }}
          onClose={() => setDocViewerOpen(false)}
        />
      )}
    </>
  );
}
