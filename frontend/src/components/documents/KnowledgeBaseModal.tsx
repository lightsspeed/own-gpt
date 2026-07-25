import { useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { FileText, Loader2, Trash2 } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

const API_BASE = 'http://localhost:8000/api/v1';

interface KnowledgeBaseModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface DocumentInfo {
  filename: string;
  chunks: number;
}

export function KnowledgeBaseModal({ open, onOpenChange }: KnowledgeBaseModalProps) {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [deletingFile, setDeletingFile] = useState<string | null>(null);

  const fetchDocuments = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/documents/`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchDocuments();
    }
  }, [open]);

  const handleDelete = async (filename: string) => {
    setDeletingFile(filename);
    try {
      const res = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        // Remove from UI immediately
        setDocuments(prev => prev.filter(d => d.filename !== filename));
      } else {
        console.error('Failed to delete document');
      }
    } catch (error) {
      console.error('Failed to delete document:', error);
    } finally {
      setDeletingFile(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px] bg-[#12141a] text-white border-white/10 shadow-2xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-medium tracking-wide text-white">Knowledge Base</DialogTitle>
          <DialogDescription className="text-gray-400">
            Manage files uploaded for Retrieval-Augmented Generation (RAG).
          </DialogDescription>
        </DialogHeader>

        <div className="py-4">
          {isLoading ? (
            <div className="flex items-center justify-center h-[200px] text-gray-500">
              <Loader2 size={24} className="animate-spin" />
            </div>
          ) : documents.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-[200px] text-gray-500 gap-3">
              <FileText size={40} className="text-white/10" />
              <p className="text-sm">No documents in the knowledge base.</p>
              <p className="text-xs text-white/40">Upload files via the chat input to see them here.</p>
            </div>
          ) : (
            <ScrollArea className="h-[300px] pr-4">
              <div className="flex flex-col gap-2">
                {documents.map((doc, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3 rounded-xl border border-white/5 bg-white/5 hover:bg-white/10 transition-colors group"
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0 overflow-hidden">
                      <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                        <FileText size={18} className="text-blue-400" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span className="text-sm text-gray-200 truncate font-medium">{doc.filename}</span>
                        <span className="text-xs text-gray-500">{doc.chunks} chunks stored</span>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                      onClick={() => handleDelete(doc.filename)}
                      disabled={deletingFile === doc.filename}
                    >
                      {deletingFile === doc.filename ? (
                        <Loader2 size={16} className="animate-spin text-red-400" />
                      ) : (
                        <Trash2 size={16} />
                      )}
                    </Button>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
