import { useState, useEffect } from 'react';
import { FileText, FileCode, Loader2, AlertCircle, X } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api/v1';

interface DocumentInfo {
  filename: string;
  chunks: number;
}

interface DocumentViewerModalProps {
  document: DocumentInfo;
  onClose: () => void;
}

function getFileExt(filename: string): string {
  const i = filename.lastIndexOf('.');
  return i >= 0 ? filename.substring(i).toLowerCase() : '';
}

export function DocumentViewerModal({ document: doc, onClose }: DocumentViewerModalProps) {
  const ext = getFileExt(doc.filename);
  const isPdf = ext === '.pdf';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 w-[90vw] max-w-5xl h-[90vh] rounded-2xl border border-border/60 bg-overlay shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between px-6 py-3 border-b border-border/60 bg-elevated/50">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl bg-muted/30 border border-border/40 flex items-center justify-center shrink-0">
              {isPdf ? <FileText size={16} className="text-rose-400" /> : <FileCode size={16} className="text-emerald-400" />}
            </div>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-foreground truncate">{doc.filename}</h2>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg text-muted-foreground/40 hover:text-foreground hover:bg-hover transition-colors">
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 bg-canvas overflow-hidden">
          <FileViewer filename={doc.filename} isPdf={isPdf} />
        </div>
      </div>
    </div>
  );
}

function FileViewer({ filename, isPdf }: { filename: string; isPdf: boolean }) {
  const fileUrl = `${API_BASE}/documents/${encodeURIComponent(filename)}/file`;
  const [useChunks, setUseChunks] = useState(false);

  if (isPdf) {
    return useChunks ? (
      <ChunkViewer filename={filename} />
    ) : (
      <PdfIframe url={fileUrl} filename={filename} onNotFound={() => setUseChunks(true)} />
    );
  }

  return useChunks ? (
    <ChunkViewer filename={filename} />
  ) : (
    <RawFileViewer url={fileUrl} onNotFound={() => setUseChunks(true)} />
  );
}

function PdfIframe({ url, filename, onNotFound }: { url: string; filename: string; onNotFound: () => void }) {
  const [status, setStatus] = useState<'loading' | 'error' | 'loaded'>('loading');

  return (
    <div className="h-full relative">
      {status === 'loading' && (
        <div className="absolute inset-0 flex items-center justify-center bg-canvas z-10">
          <Loader2 size={24} className="animate-spin text-primary/60" />
        </div>
      )}
      {status === 'error' ? (
        <div className="flex items-center justify-center h-full">
          <div className="flex flex-col items-center gap-3 max-w-sm text-center">
            <AlertCircle size={24} className="text-danger" />
            <p className="text-small text-muted-foreground">Could not load file. Showing reconstructed content instead.</p>
            <button onClick={onNotFound} className="px-4 py-2 rounded-xl bg-primary/10 text-primary text-small font-medium hover:bg-primary/20 transition-colors">
              Show text version
            </button>
          </div>
        </div>
      ) : (
        <iframe
          src={`${url}#view=FitH`}
          className="w-full h-full border-0"
          title={filename}
          onLoad={() => setStatus('loaded')}
          onError={() => setStatus('error')}
        />
      )}
    </div>
  );
}

function RawFileViewer({ url, onNotFound }: { url: string; onNotFound: () => void }) {
  const [text, setText] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch(url);
        if (cancelled) return;
        if (res.status === 404) { onNotFound(); return; }
        if (!res.ok) throw new Error(`Failed to load (${res.status})`);
        setText(await res.text());
      } catch (err: any) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [url, onNotFound]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={24} className="animate-spin text-primary/60" />
      </div>
    );
  }

  if (error || !text) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3 max-w-sm text-center">
          <AlertCircle size={24} className="text-danger" />
          <p className="text-small text-muted-foreground">Could not load file. Showing reconstructed content instead.</p>
          <button onClick={onNotFound} className="px-4 py-2 rounded-xl bg-primary/10 text-primary text-small font-medium hover:bg-primary/20 transition-colors">
            Show text version
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <pre className="px-6 py-5 text-[14px] leading-relaxed text-foreground/85 whitespace-pre-wrap break-words font-mono m-0">{text}</pre>
    </div>
  );
}

function ChunkViewer({ filename }: { filename: string }) {
  const [fullText, setFullText] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}/content`);
        if (cancelled) return;
        if (!res.ok) throw new Error(`Failed to load (${res.status})`);
        const data = await res.json();
        const joined = (data.chunks as { chunk_index: number; content: string }[])
          .sort((a, b) => a.chunk_index - b.chunk_index)
          .map(c => c.content)
          .join('\n\n');
        setFullText(joined);
      } catch (err: any) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [filename]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={24} className="animate-spin text-primary/60" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3 max-w-sm text-center">
          <AlertCircle size={24} className="text-danger" />
          <p className="text-small text-muted-foreground">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto custom-scrollbar">
      <div className="px-6 py-2 bg-warning/5 border-b border-border/20">
        <p className="text-caption text-warning flex items-center gap-1.5">
          <AlertCircle size={12} />
          Original file unavailable — showing reconstructed content from database.
        </p>
      </div>
      <pre className="px-6 py-5 text-[14px] leading-relaxed text-foreground/85 whitespace-pre-wrap break-words font-mono m-0">{fullText}</pre>
    </div>
  );
}

export default DocumentViewerModal;
