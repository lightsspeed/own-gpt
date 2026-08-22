import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, FileCode, File, Upload, Search,
  Loader2, Trash2, AlertCircle, BookOpen,
  X, ChevronDown, Filter,
} from 'lucide-react';
import { DocumentUpload } from './DocumentUpload';
import { DocumentWorkspace } from './DocumentWorkspace';

const API_BASE = 'http://localhost:8000/api/v1';

interface DocumentInfo {
  filename: string;
  chunks: number;
}

type ViewMode = 'list' | 'grid';

const FILE_TYPE_ICONS: Record<string, React.ReactNode> = {
  '.pdf': <FileText size={16} className="text-rose-400" />,
  '.txt': <FileCode size={16} className="text-blue-400" />,
  '.md': <FileCode size={16} className="text-emerald-400" />,
};

const FILE_TYPE_COLORS: Record<string, string> = {
  '.pdf': 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  '.txt': 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  '.md': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
};

function getFileExt(filename: string): string {
  const i = filename.lastIndexOf('.');
  return i >= 0 ? filename.substring(i).toLowerCase() : '';
}

function FileTypeBadge({ ext }: { ext: string }) {
  const label = ext.toUpperCase().replace('.', '') || 'FILE';
  const colorClass = FILE_TYPE_COLORS[ext] || 'bg-muted/20 text-muted-foreground border-border/30';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider border ${colorClass}`}>
      {label}
    </span>
  );
}

export function KnowledgeBasePage() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const [viewMode] = useState<ViewMode>('list');
  const [showUpload, setShowUpload] = useState(false);
  const [showFilter, setShowFilter] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<{ name: string; chunks: number; type: string }[]>([]);
  const [workspaceDoc, setWorkspaceDoc] = useState<DocumentInfo | null>(null);

  const fetchDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/documents/`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      } else {
        throw new Error(`Failed to load (${res.status})`);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load documents');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const handleDelete = async (filename: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletingFile(filename);
    try {
      const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        setDocuments(prev => prev.filter(d => d.filename !== filename));
      }
    } catch (err) {
      console.error('Delete failed:', err);
    } finally {
      setDeletingFile(null);
    }
  };

  const handleFileUploaded = (file: { name: string; chunks: number; type: string }) => {
    setUploadedFiles(prev => [...prev, file]);
    fetchDocuments();
  };

  const fileExtSet = new Set(documents.map(d => getFileExt(d.filename)));
  const availableTypes = ['all', ...Array.from(fileExtSet)].sort();

  const filtered = documents.filter(d => {
    const matchSearch = d.filename.toLowerCase().includes(searchQuery.toLowerCase());
    const matchType = typeFilter === 'all' || getFileExt(d.filename) === typeFilter;
    return matchSearch && matchType;
  });

  const totalChunks = documents.reduce((sum, d) => sum + d.chunks, 0);
  const extCounts = documents.reduce<Record<string, number>>((acc, d) => {
    const ext = getFileExt(d.filename);
    acc[ext] = (acc[ext] || 0) + 1;
    return acc;
  }, {});

  if (workspaceDoc) {
    return (
      <DocumentWorkspace
        filename={workspaceDoc.filename}
        onBack={() => setWorkspaceDoc(null)}
      />
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-canvas">
      {/* Header */}
      <div className="shrink-0 border-b border-border/60 px-6 py-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h1 className="text-xl font-semibold text-foreground">Knowledge Base</h1>
            <p className="text-small text-muted-foreground mt-0.5">
              {documents.length} document{documents.length !== 1 ? 's' : ''} · {totalChunks} chunks stored
            </p>
          </div>
          <button
            onClick={() => setShowUpload(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-white text-small font-medium hover:bg-primary/90 transition-colors"
          >
            <Upload size={15} />
            Upload
          </button>
        </div>

        {/* Search + filter bar */}
        <div className="flex items-center gap-2">
          <div className="relative flex-1 max-w-md">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/40" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search documents..."
              className="w-full rounded-xl border border-border/60 bg-elevated/50 py-2 pl-9 pr-4 text-small text-foreground placeholder:text-muted-foreground/30 outline-none transition-colors focus:border-primary/40 focus:bg-elevated"
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground/30 hover:text-foreground">
                <X size={14} />
              </button>
            )}
          </div>
          <div className="relative">
            <button
              onClick={() => setShowFilter(!showFilter)}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl border transition-colors text-small ${
                typeFilter !== 'all'
                  ? 'border-primary/40 bg-primary/10 text-primary'
                  : 'border-border/60 bg-elevated/50 text-muted-foreground hover:text-foreground'
              }`}
            >
              <Filter size={14} />
              {typeFilter !== 'all' ? typeFilter.toUpperCase().replace('.', '') : 'All types'}
              <ChevronDown size={12} className={`transition-transform ${showFilter ? 'rotate-180' : ''}`} />
            </button>
            {showFilter && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowFilter(false)} />
                <div className="absolute right-0 top-full mt-1 z-20 w-40 rounded-xl border border-border/60 bg-overlay shadow-2xl p-1.5">
                  {availableTypes.map(type => (
                    <button
                      key={type}
                      onClick={() => { setTypeFilter(type); setShowFilter(false); }}
                      className={`flex items-center gap-2 w-full px-3 py-1.5 rounded-lg text-small transition-colors ${
                        typeFilter === type
                          ? 'text-foreground bg-hover'
                          : 'text-muted-foreground hover:text-foreground hover:bg-hover/50'
                      }`}
                    >
                      {type === 'all' ? (
                        <BookOpen size={14} />
                      ) : (
                        FILE_TYPE_ICONS[type] || <File size={14} />
                      )}
                      <span className="flex-1 text-left">
                        {type === 'all' ? 'All Types' : type.toUpperCase().replace('.', '')}
                      </span>
                      {type !== 'all' && (
                        <span className="text-caption text-muted-foreground/40">{extCounts[type] || 0}</span>
                      )}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {isLoading ? (
          <div className="flex items-center justify-center h-[400px]">
            <div className="flex flex-col items-center gap-3">
              <Loader2 size={24} className="animate-spin text-primary/60" />
              <p className="text-small text-muted-foreground/50">Loading documents...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-[400px]">
            <div className="flex flex-col items-center gap-3 max-w-sm text-center">
              <div className="w-12 h-12 rounded-xl bg-danger/10 flex items-center justify-center">
                <AlertCircle size={24} className="text-danger" />
              </div>
              <p className="text-small text-muted-foreground">{error}</p>
              <button
                onClick={fetchDocuments}
                className="px-4 py-2 rounded-xl bg-primary/10 text-primary text-small font-medium hover:bg-primary/20 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex items-center justify-center h-[400px]">
            <div className="flex flex-col items-center gap-4 max-w-sm text-center">
              <div className="w-16 h-16 rounded-2xl bg-muted/30 border border-border/40 flex items-center justify-center">
                <BookOpen size={32} className="text-muted-foreground/30" />
              </div>
              {searchQuery || typeFilter !== 'all' ? (
                <>
                  <p className="text-small text-muted-foreground">No documents match your filters.</p>
                  <button
                    onClick={() => { setSearchQuery(''); setTypeFilter('all'); }}
                    className="text-small text-primary hover:text-primary/80 transition-colors"
                  >
                    Clear filters
                  </button>
                </>
              ) : (
                <>
                  <p className="text-small text-muted-foreground">
                    No documents uploaded yet. Upload PDF, TXT, or MD files to build your knowledge base.
                  </p>
                  <button
                    onClick={() => setShowUpload(true)}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-small font-medium hover:bg-primary/90 transition-colors"
                  >
                    <Upload size={16} />
                    Upload your first document
                  </button>
                </>
              )}
            </div>
          </div>
        ) : viewMode === 'list' ? (
          <div className="p-4">
            <div className="max-w-4xl mx-auto space-y-1">
              {filtered.map((doc, i) => {
                const ext = getFileExt(doc.filename);
                return (
                  <button
                    key={i}
                    onClick={() => setWorkspaceDoc(doc)}
                    className="w-full flex items-center gap-4 px-4 py-3 rounded-xl hover:bg-hover/60 transition-colors group text-left border border-transparent hover:border-border/40"
                  >
                    {/* Icon */}
                    <div className="w-10 h-10 rounded-xl bg-muted/30 border border-border/40 flex items-center justify-center shrink-0">
                      {FILE_TYPE_ICONS[ext] || <File size={16} className="text-muted-foreground" />}
                    </div>

                    {/* Name */}
                    <div className="flex-1 min-w-0">
                      <p className="text-small text-foreground font-medium truncate">{doc.filename}</p>
                      <p className="text-caption text-muted-foreground/50 mt-0.5">{doc.chunks} chunks</p>
                    </div>

                    {/* Type badge */}
                    <FileTypeBadge ext={ext} />

                    {/* Delete */}
                    <button
                      onClick={(e) => handleDelete(doc.filename, e)}
                      disabled={deletingFile === doc.filename}
                      className="p-2 rounded-lg text-muted-foreground/30 hover:text-danger hover:bg-danger/10 transition-all opacity-0 group-hover:opacity-100 shrink-0"
                    >
                      {deletingFile === doc.filename ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Trash2 size={14} />
                      )}
                    </button>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>

      {/* Upload modal */}
      {showUpload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowUpload(false)} />
          <div className="relative z-10 w-full max-w-lg mx-4 rounded-2xl border border-border/60 bg-overlay shadow-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-foreground">Upload Document</h2>
              <button onClick={() => setShowUpload(false)} className="p-1.5 rounded-lg text-muted-foreground/40 hover:text-foreground hover:bg-hover transition-colors">
                <X size={16} />
              </button>
            </div>
            <DocumentUpload
              uploadedFiles={uploadedFiles}
              onFileUploaded={handleFileUploaded}
            />
            <p className="text-caption text-muted-foreground/40 mt-3">
              Supported: PDF, TXT, Markdown. Files are parsed, chunked, and embedded for RAG retrieval.
            </p>
          </div>
        </div>
      )}

    </div>
  );
}



export default KnowledgeBasePage;
