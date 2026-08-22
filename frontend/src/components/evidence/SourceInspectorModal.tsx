/**
 * SourceInspectorModal — V3 Phase 5: Citation Transparency
 *
 * Shows the exact supporting chunk for a citation, with graceful handling
 * for deleted/missing documents. Opens DocumentViewerModal for the full file.
 */
import { useState, useEffect } from 'react';
import { X, FileText, Globe, AlertCircle, Loader2, ExternalLink, BookOpen, Hash, FileCode } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api/v1';

export interface SourceInspectorProps {
  title: string;
  type: 'web' | 'file' | 'knowledge';
  url?: string | null;
  documentId?: string | null;
  chunkIndex?: number | null;
  page?: number | null;
  section?: string | null;
  snippet?: string | null;
  confidenceLabel?: 'high' | 'medium' | 'low' | 'no_evidence' | null;
  onClose: () => void;
  onOpenDocument?: (filename: string) => void;
}

const CONFIDENCE_CONFIG = {
  high:        { label: 'High',   cls: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25' },
  medium:      { label: 'Strong', cls: 'bg-blue-500/15 text-blue-400 border border-blue-500/25' },
  low:         { label: 'Low',    cls: 'bg-amber-500/15 text-amber-400 border border-amber-500/25' },
  no_evidence: { label: 'None',   cls: 'bg-white/5 text-white/30 border border-white/10' },
} as const;

interface ChunkData {
  filename: string;
  chunk_index: number;
  content: string;
  page: number | null;
  section: string | null;
  total_chunks: number;
}

export function SourceInspectorModal({
  title,
  type,
  url,
  documentId,
  chunkIndex,
  page,
  section,
  snippet,
  confidenceLabel,
  onClose,
  onOpenDocument,
}: SourceInspectorProps) {
  const [chunkData, setChunkData] = useState<ChunkData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [documentMissing, setDocumentMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isWeb = type === 'web';
  const filename = documentId || title;
  const conf = CONFIDENCE_CONFIG[(confidenceLabel ?? 'medium') as keyof typeof CONFIDENCE_CONFIG]
    ?? CONFIDENCE_CONFIG.medium;

  useEffect(() => {
    if (isWeb) return;

    // For KB sources: fetch the specific chunk if we have a chunk_index
    const loadChunk = async () => {
      setIsLoading(true);
      setError(null);

      // First check if document still exists
      try {
        const existsRes = await fetch(
          `${API_BASE}/documents/${encodeURIComponent(filename)}/exists`
        );
        if (existsRes.ok) {
          const exists = await existsRes.json();
          if (!exists.exists) {
            setDocumentMissing(true);
            setIsLoading(false);
            return;
          }
        }
      } catch {/* ignore — existence check is best-effort */}

      if (chunkIndex != null) {
        try {
          const res = await fetch(
            `${API_BASE}/documents/${encodeURIComponent(filename)}/chunks/${chunkIndex}`
          );
          if (res.status === 404) {
            // Chunk gone but doc exists — fall back to snippet
            setChunkData(null);
          } else if (!res.ok) {
            setError(`Could not load chunk (${res.status})`);
          } else {
            setChunkData(await res.json());
          }
        } catch (err: any) {
          setError(err.message);
        }
      }
      setIsLoading(false);
    };

    loadChunk();
  }, [filename, chunkIndex, isWeb]);

  const displayContent = chunkData?.content ?? snippet ?? '';
  const displayPage = chunkData?.page ?? page;
  const displaySection = chunkData?.section ?? section;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/75 backdrop-blur-sm" onClick={onClose} />

      {/* Panel */}
      <div className="relative z-10 w-[90vw] max-w-2xl max-h-[80vh] flex flex-col rounded-2xl border border-white/10 bg-[#1a1b1c] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/8 bg-white/[0.02] shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            {/* Icon */}
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${isWeb ? 'bg-sky-500/15' : 'bg-blue-500/15'}`}>
              {isWeb
                ? <Globe size={15} className="text-sky-400" />
                : <BookOpen size={15} className="text-blue-400" />}
            </div>

            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-white truncate leading-tight">{title}</h2>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-[11px] text-white/40">
                  {isWeb ? 'Web Source' : 'Knowledge Base'}
                </span>
                {confidenceLabel && confidenceLabel !== 'no_evidence' && (
                  <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${conf.cls}`}>
                    {conf.label} relevance
                  </span>
                )}
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-white/30 hover:text-white/70 hover:bg-white/5 transition-colors shrink-0"
          >
            <X size={16} />
          </button>
        </div>

        {/* Metadata row */}
        {!isWeb && (displayPage != null || displaySection || chunkIndex != null) && !documentMissing && (
          <div className="flex items-center gap-3 px-5 py-2 border-b border-white/5 bg-white/[0.015] shrink-0">
            {displayPage != null && (
              <span className="flex items-center gap-1 text-[11px] text-white/50">
                <FileText size={11} className="text-white/30" />
                Page {displayPage}
              </span>
            )}
            {displaySection && (
              <span className="flex items-center gap-1 text-[11px] text-white/50">
                <Hash size={11} className="text-white/30" />
                {displaySection}
              </span>
            )}
            {chunkIndex != null && (
              <span className="flex items-center gap-1 text-[11px] text-white/30">
                <FileCode size={11} className="text-white/20" />
                Chunk {chunkIndex}
                {chunkData?.total_chunks != null ? ` of ${chunkData.total_chunks}` : ''}
              </span>
            )}
          </div>
        )}

        {/* Body */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {isWeb ? (
            /* Web source: show snippet + open link */
            <div className="px-5 py-4 space-y-4">
              {snippet && (
                <p className="text-[14px] leading-relaxed text-white/70 whitespace-pre-wrap">{snippet}</p>
              )}
              {url && (
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sky-400 text-[13px] hover:text-sky-300 underline underline-offset-2 transition-colors"
                >
                  <ExternalLink size={13} />
                  {url}
                </a>
              )}
            </div>
          ) : isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={22} className="animate-spin text-white/30" />
            </div>
          ) : documentMissing ? (
            /* Deleted document */
            <div className="flex flex-col items-center justify-center gap-3 py-12 px-5 text-center">
              <AlertCircle size={24} className="text-amber-400/70" />
              <div>
                <p className="text-[14px] font-medium text-white/70">Document no longer available</p>
                <p className="text-[12px] text-white/40 mt-1">
                  <span className="font-mono text-white/50">{filename}</span> has been removed from the knowledge base.
                  The citation was grounded at the time of the answer.
                </p>
              </div>
              {snippet && (
                <div className="mt-4 w-full rounded-xl border border-white/8 bg-white/[0.03] px-4 py-3 text-left">
                  <p className="text-[11px] text-white/30 mb-1.5 uppercase tracking-wider font-medium">Cached snippet</p>
                  <p className="text-[13px] leading-relaxed text-white/60 italic">{snippet}</p>
                </div>
              )}
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center gap-2 py-12 px-5 text-center">
              <AlertCircle size={20} className="text-red-400/70" />
              <p className="text-[13px] text-white/50">{error}</p>
              {snippet && <p className="text-[13px] leading-relaxed text-white/60 italic px-4">{snippet}</p>}
            </div>
          ) : (
            /* Chunk content */
            <div className="px-5 py-4">
              {displayContent ? (
                <pre className="text-[13.5px] leading-relaxed text-white/75 whitespace-pre-wrap break-words font-sans">
                  {displayContent}
                </pre>
              ) : (
                <p className="text-[13px] text-white/40 italic">No content preview available.</p>
              )}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-white/8 bg-white/[0.02] shrink-0">
          <div className="text-[11px] text-white/30">
            {isWeb ? 'External source' : `Source: ${filename}`}
          </div>
          <div className="flex items-center gap-2">
            {!isWeb && !documentMissing && onOpenDocument && (
              <button
                onClick={() => { onOpenDocument(filename); onClose(); }}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 transition-colors border border-blue-500/20 hover:border-blue-500/30"
              >
                <FileText size={12} />
                Open full document
              </button>
            )}
            {isWeb && url && (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium text-sky-400 hover:text-sky-300 hover:bg-sky-500/10 transition-colors border border-sky-500/20 hover:border-sky-500/30"
              >
                <ExternalLink size={12} />
                Open source
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
