import React, { useState, useRef } from 'react';
import { UploadCloud, CheckCircle2, Loader2, FileText, AlertCircle, X } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api/v1';
const SUPPORTED_EXTS = ['.pdf', '.txt', '.md'];

interface UploadedFile {
  name: string;
  chunks: number;
  type: string;
}

interface DocumentUploadProps {
  uploadedFiles: UploadedFile[];
  onFileUploaded: (file: UploadedFile) => void;
}

export function DocumentUpload({ uploadedFiles, onFileUploaded }: DocumentUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!SUPPORTED_EXTS.includes(ext)) {
      setError(`Unsupported format. Use: ${SUPPORTED_EXTS.join(', ')}`);
      return;
    }

    setIsUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/documents/upload`, { method: 'POST', body: formData });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }
      const data = await res.json();
      onFileUploaded({ name: data.filename, chunks: data.chunks, type: ext });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-2">
      {/* Drop zone */}
      <div
        className={`border-2 border-dashed rounded-xl p-4 text-center transition-all duration-200 cursor-pointer flex flex-col items-center gap-2 min-h-[100px] justify-center
          ${isDragging ? 'border-primary bg-primary/10' : 'border-border hover:border-primary/50 hover:bg-card/50'}
          ${isUploading ? 'pointer-events-none opacity-60' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => { e.preventDefault(); setIsDragging(false); if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); }}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          type="file"
          accept=".pdf,.txt,.md"
          className="hidden"
          ref={fileInputRef}
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />

        {isUploading ? (
          <>
            <Loader2 className="w-7 h-7 text-primary animate-spin" />
            <p className="text-xs text-muted-foreground">Embedding document…</p>
          </>
        ) : (
          <>
            <UploadCloud className={`w-7 h-7 ${isDragging ? 'text-primary' : 'text-muted-foreground'}`} />
            <div>
              <p className="text-xs font-medium">Upload Document</p>
              <p className="text-xs text-muted-foreground">PDF · TXT · MD</p>
            </div>
          </>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2 text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-lg p-2">
          <AlertCircle size={12} className="mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Uploaded files list */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-1 mt-1">
          {uploadedFiles.map((f, i) => (
            <div key={i} className="flex items-center gap-2 text-xs bg-secondary/20 rounded-lg px-2 py-1.5">
              <FileText size={11} className="text-primary flex-shrink-0" />
              <span className="truncate text-foreground flex-1">{f.name}</span>
              <span className="text-muted-foreground flex-shrink-0">{f.chunks}c</span>
              <CheckCircle2 size={11} className="text-green-500 flex-shrink-0" />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
