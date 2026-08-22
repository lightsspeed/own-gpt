import { useState, useRef, useCallback, useEffect } from 'react';
import { pdfjs, Document, Page } from 'react-pdf';
import 'react-pdf/dist/Page/TextLayer.css';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import {
  ZoomIn, ZoomOut, ChevronLeft, ChevronRight,
  Loader2, Search, X, AlertCircle,
} from 'lucide-react';

pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const API_BASE = 'http://localhost:8000/api/v1';

interface PdfViewerProps {
  filename: string;
  onPageChange?: (page: number) => void;
  onLoad?: (numPages: number) => void;
  highlight?: { page: number; text: string; ts: number } | null;
}

export function PdfViewer({ filename, onPageChange, onLoad, highlight }: PdfViewerProps) {
  const [numPages, setNumPages] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.0);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [showFallback, setShowFallback] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});

  const fileUrl = `${API_BASE}/documents/${encodeURIComponent(filename)}/file`;

  function onDocumentLoadSuccess({ numPages: pages }: { numPages: number }) {
    setNumPages(pages);
    setShowFallback(false);
    onLoad?.(pages);
  }

  function onDocumentLoadError() {
    setShowFallback(true);
  }

  const scrollToPage = useCallback((page: number) => {
    const p = Math.max(1, Math.min(page, numPages || page));
    setPageNumber(p);
    onPageChange?.(p);
    pageRefs.current[p]?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [numPages, onPageChange]);

  // Track which page is most visible while scrolling
  useEffect(() => {
    if (numPages === 0) return;
    const observer = new IntersectionObserver(
      entries => {
        const visible = entries
          .filter(e => e.isIntersecting)
          .sort((a, b) => (b.intersectionRatio - a.intersectionRatio))[0];
        if (visible) {
          const page = Number((visible.target as HTMLElement).dataset.page);
          if (page !== pageNumber) {
            setPageNumber(page);
            onPageChange?.(page);
          }
        }
      },
      { root: containerRef.current, rootMargin: '0px 0px -20% 0px', threshold: [0, 0.1, 0.25, 0.5] },
    );
    Object.values(pageRefs.current).forEach(el => { if (el) observer.observe(el); });
    return () => observer.disconnect();
  }, [numPages, pageNumber, onPageChange]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') scrollToPage(pageNumber - 1);
      if (e.key === 'ArrowRight') scrollToPage(pageNumber + 1);
      if ((e.metaKey || e.ctrlKey) && e.key === 'f') { e.preventDefault(); setShowSearch(s => !s); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [pageNumber, scrollToPage]);

  // Locate and flash-highlight a cited passage in the document
  useEffect(() => {
    if (!highlight) return;
    const { page, text } = highlight;
    scrollToPage(page);
    const pageEl = pageRefs.current[page];
    if (!pageEl) return;
    pageEl.classList.add('ring-2', 'ring-amber-400/60', 'rounded-sm');

    const timer = window.setTimeout(() => {
      const spans = Array.from(pageEl.querySelectorAll('.textLayer span'));
      const needle = (text || '').trim().toLowerCase().replace(/\s+/g, ' ');
      if (!needle) return;
      let acc = '';
      let accStart: Element | null = null;
      let hit: Element | null = null;
      for (const span of spans) {
        const t = span.textContent ?? '';
        if (!t.trim()) continue;
        if (!accStart) accStart = span;
        acc += t;
        const idx = acc.indexOf(needle.slice(0, 60));
        if (idx >= 0) {
          hit = accStart;
          break;
        }
        if (acc.length > 140) {
          acc = acc.slice(40);
          accStart = null;
        }
      }
      if (hit) {
        hit.classList.add('citation-highlight');
        hit.scrollIntoView({ behavior: 'smooth', block: 'center' });
        window.setTimeout(() => hit?.classList.remove('citation-highlight'), 4000);
      }
    }, 300);

    const clearRing = window.setTimeout(() => {
      pageEl.classList.remove('ring-2', 'ring-amber-400/60', 'rounded-sm');
    }, 4300);

    return () => {
      window.clearTimeout(timer);
      window.clearTimeout(clearRing);
    };
  }, [highlight, scrollToPage]);

  if (showFallback) {
    return <TextViewerFallback filename={filename} />;
  }

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="shrink-0 flex items-center justify-between px-4 py-2 border-b border-border/40 bg-elevated/30">
        <div className="flex items-center gap-2">
          <button
            onClick={() => scrollToPage(pageNumber - 1)}
            disabled={pageNumber <= 1}
            className="p-1.5 rounded-lg text-muted-foreground/50 hover:text-foreground hover:bg-hover transition-colors disabled:opacity-30"
          >
            <ChevronLeft size={16} />
          </button>
          <span className="text-small text-muted-foreground tabular-nums">
            <input
              type="number"
              value={pageNumber}
              onChange={e => scrollToPage(Number(e.target.value))}
              className="w-8 bg-transparent text-center text-foreground outline-none border-b border-border/30 mx-0.5"
              min={1}
              max={numPages}
            />
            <span className="text-muted-foreground/40"> / {numPages}</span>
          </span>
          <button
            onClick={() => scrollToPage(pageNumber + 1)}
            disabled={pageNumber >= numPages}
            className="p-1.5 rounded-lg text-muted-foreground/50 hover:text-foreground hover:bg-hover transition-colors disabled:opacity-30"
          >
            <ChevronRight size={16} />
          </button>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowSearch(s => !s)}
            className={`p-1.5 rounded-lg transition-colors ${showSearch ? 'bg-primary/10 text-primary' : 'text-muted-foreground/50 hover:text-foreground hover:bg-hover'}`}
          >
            <Search size={15} />
          </button>
          <button
            onClick={() => setScale(s => Math.max(0.5, s - 0.15))}
            className="p-1.5 rounded-lg text-muted-foreground/50 hover:text-foreground hover:bg-hover transition-colors"
          >
            <ZoomOut size={15} />
          </button>
          <span className="text-caption text-muted-foreground/50 w-10 text-center tabular-nums">{Math.round(scale * 100)}%</span>
          <button
            onClick={() => setScale(s => Math.min(3, s + 0.15))}
            className="p-1.5 rounded-lg text-muted-foreground/50 hover:text-foreground hover:bg-hover transition-colors"
          >
            <ZoomIn size={15} />
          </button>
        </div>
      </div>

      {/* Search bar */}
      {showSearch && (
        <div className="shrink-0 px-4 py-2 border-b border-border/40 bg-elevated/20">
          <div className="relative max-w-xs">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/30" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search in document..."
              className="w-full rounded-lg bg-background/30 py-1.5 pl-8 pr-8 text-small text-foreground placeholder:text-muted-foreground/30 outline-none"
              autoFocus
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground/30 hover:text-foreground">
                <X size={13} />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Scrollable pages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar bg-canvas" ref={containerRef}>
        <Document
          file={fileUrl}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={onDocumentLoadError}
          loading={<div className="flex items-center justify-center h-full"><Loader2 size={24} className="animate-spin text-primary/60" /></div>}
        >
          <div className="flex flex-col items-center gap-5 py-4">
            {numPages > 0 && Array.from({ length: numPages }, (_, i) => i + 1).map(page => (
              <div
                key={`${page}-${scale}`}
                data-page={page}
                ref={el => { pageRefs.current[page] = el; }}
                className={`scroll-mt-4 transition-shadow duration-150 ${
                  page === pageNumber ? 'ring-2 ring-primary/40 rounded-sm' : ''
                }`}
              >
                <Page
                  pageNumber={page}
                  scale={scale}
                  renderTextLayer
                  renderAnnotationLayer
                  className="shadow-xl rounded-sm bg-white"
                  width={containerRef.current?.clientWidth ? containerRef.current.clientWidth * 0.85 : undefined}
                />
              </div>
            ))}
          </div>
        </Document>
      </div>
    </div>
  );
}

function TextViewerFallback({ filename }: { filename: string }) {
  const [fullText, setFullText] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}/content`)
      .then(res => res.ok ? res.json() : Promise.reject())
      .then(data => {
        const joined = (data.chunks as { chunk_index: number; content: string }[])
          .sort((a: any, b: any) => a.chunk_index - b.chunk_index)
          .map(c => c.content)
          .join('\n\n');
        setFullText(joined);
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, [filename]);

  if (isLoading) {
    return <div className="flex items-center justify-center h-full"><Loader2 size={24} className="animate-spin text-primary/60" /></div>;
  }

  return (
    <div className="h-full flex flex-col">
      <div className="shrink-0 px-4 py-2 bg-warning/5 border-b border-border/20">
        <p className="text-caption text-warning flex items-center gap-1.5">
          <AlertCircle size={12} />
          Original file unavailable — showing extracted text content.
        </p>
      </div>
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        <pre className="px-6 py-5 text-[14px] leading-relaxed text-foreground/85 whitespace-pre-wrap break-words font-mono m-0">
          {fullText}
        </pre>
      </div>
    </div>
  );
}
