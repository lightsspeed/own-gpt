import { useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import { FileText, FileImage, FileCode, File, X, AlertCircle } from 'lucide-react'
import { uploadService } from '@/features/chat/services/uploadService'
import type { AttachmentFile } from '@/features/chat/types'

interface FilePreviewProps {
  file: AttachmentFile
  onRemove: (id: string) => void
}

function FileIcon({ type }: { type: string }) {
  if (type.startsWith('image/')) return <FileImage size={16} className="text-sky-400" />
  if (type.startsWith('text/') || type.includes('json') || type.includes('yaml') || type.includes('toml')) return <FileCode size={16} className="text-emerald-400" />
  if (type === 'application/pdf') return <FileText size={16} className="text-rose-400" />
  return <File size={16} className="text-muted-foreground" />
}

export function FilePreview({ file, onRemove }: FilePreviewProps) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewError, setPreviewError] = useState(false)

  useEffect(() => {
    if (file.preview && !previewUrl) {
      setPreviewUrl(file.preview)
    }
  }, [file.preview, previewUrl])

  const showPreview = file.type.startsWith('image/') && previewUrl && !previewError

  return (
    <div
      className={cn(
        'group relative flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-all',
        file.status === 'error'
          ? 'bg-danger/10 border-danger/30'
          : 'bg-elevated/60 border-border/60 hover:border-primary/30',
      )}
    >
      {/* Preview thumbnail */}
      {showPreview ? (
        <div className="w-10 h-10 rounded-lg overflow-hidden shrink-0 bg-muted/50">
          <img
            src={previewUrl}
            alt={file.name}
            className="w-full h-full object-cover"
            onError={() => setPreviewError(true)}
          />
        </div>
      ) : (
        <div className="w-10 h-10 rounded-lg bg-muted/30 border border-border/50 flex items-center justify-center shrink-0">
          <FileIcon type={file.type} />
        </div>
      )}

      {/* Details */}
      <div className="flex-1 min-w-0">
        <p className="text-small text-foreground truncate font-medium">{file.name}</p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-caption text-muted-foreground/50">{uploadService.formatSize(file.size)}</span>
          {file.status === 'uploading' && (
            <span className="text-caption text-primary/60">{file.progress}%</span>
          )}
          {file.status === 'error' && (
            <span className="text-caption text-danger flex items-center gap-1">
              <AlertCircle size={10} /> {file.error || 'Upload failed'}
            </span>
          )}
          {file.status === 'uploaded' && (
            <span className="text-caption text-emerald-400/60">Ready</span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {file.status === 'uploading' && (
        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-muted/30 rounded-full overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-300 rounded-full"
            style={{ width: `${file.progress}%` }}
          />
        </div>
      )}

      {/* Remove */}
      <button
        onClick={() => onRemove(file.id)}
        className="p-1 rounded-md text-muted-foreground/30 hover:text-foreground hover:bg-hover transition-all opacity-0 group-hover:opacity-100 shrink-0"
      >
        <X size={14} />
      </button>
    </div>
  )
}
