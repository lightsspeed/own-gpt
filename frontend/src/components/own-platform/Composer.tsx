import { useRef, useState, useEffect, useCallback } from 'react'
import { ArrowUp, Paperclip, Mic, X, Upload, Wrench } from 'lucide-react'
import { cn } from '@/lib/utils'
import { FilePreview } from './FilePreview'
import { ToolPicker } from './ToolPicker'
import { uploadService } from '@/features/chat/services/uploadService'
import type { AttachmentFile, ToolInfo, ToolMode } from '@/features/chat/types'

interface ComposerProps {
  input: string
  setInput: (val: string) => void
  onSend: () => void
  onStop?: () => void
  isLoading?: boolean
  disabled?: boolean
  placeholder?: string
  tools?: ToolInfo[]
  onToggleTool?: (name: string) => void
  onToolModeChange?: (name: string, mode: ToolMode) => void
}

export function Composer({
  input,
  setInput,
  onSend,
  onStop,
  isLoading = false,
  disabled = false,
  placeholder = 'Ask anything...',
  tools,
  onToggleTool,
  onToolModeChange,
}: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const dropRef = useRef<HTMLDivElement>(null)
  const [files, setFiles] = useState<AttachmentFile[]>([])
  const [focused, setFocused] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)

  const autoResize = () => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }

  useEffect(() => { autoResize() }, [input])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!isLoading) onSend()
    }
  }

  const processFiles = useCallback(async (fileList: FileList | File[]) => {
    const newFiles: AttachmentFile[] = []
    for (const f of Array.from(fileList)) {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase()
      if (!uploadService.ALLOWED_TYPES.includes(ext)) {
        newFiles.push({
          id: `file-${Date.now()}-${Math.random().toString(36).slice(2)}`,
          name: f.name,
          size: f.size,
          type: f.type || 'application/octet-stream',
          status: 'error',
          progress: 0,
          error: `Unsupported file type`,
        })
        continue
      }
      if (f.size > uploadService.MAX_SIZE) {
        newFiles.push({
          id: `file-${Date.now()}-${Math.random().toString(36).slice(2)}`,
          name: f.name,
          size: f.size,
          type: f.type || 'application/octet-stream',
          status: 'error',
          progress: 0,
          error: `File too large (max ${uploadService.formatSize(uploadService.MAX_SIZE)})`,
        })
        continue
      }

      const id = `file-${Date.now()}-${Math.random().toString(36).slice(2)}`
      const preview = uploadService.canPreview(f.type) ? await uploadService.readAsDataURL(f).catch(() => undefined) : undefined

      const fileEntry: AttachmentFile = {
        id,
        name: f.name,
        size: f.size,
        type: f.type || 'application/octet-stream',
        status: 'uploading',
        progress: 0,
        preview,
      }
      newFiles.push(fileEntry)

      uploadService.uploadFile(f, (progress) => {
        setFiles(prev => prev.map(pf => pf.id === id ? { ...pf, progress } : pf))
      }).then(result => {
        setFiles(prev => prev.map(pf => pf.id === id ? { ...pf, status: 'uploaded', url: result.url, progress: 100 } : pf))
      }).catch(err => {
        setFiles(prev => prev.map(pf => pf.id === id ? { ...pf, status: 'error', error: err.message } : pf))
      })
    }
    setFiles(prev => [...prev, ...newFiles])
  }, [])

  // Drag & drop handlers
  useEffect(() => {
    const el = dropRef.current
    if (!el) return

    const onDragOver = (e: DragEvent) => { e.preventDefault(); setIsDragging(true) }
    const onDragLeave = () => setIsDragging(false)
    const onDrop = (e: DragEvent) => {
      e.preventDefault()
      setIsDragging(false)
      if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) {
        processFiles(e.dataTransfer.files)
      }
    }

    el.addEventListener('dragover', onDragOver)
    el.addEventListener('dragleave', onDragLeave)
    el.addEventListener('drop', onDrop)
    return () => {
      el.removeEventListener('dragover', onDragOver)
      el.removeEventListener('dragleave', onDragLeave)
      el.removeEventListener('drop', onDrop)
    }
  }, [processFiles])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processFiles(e.target.files)
    }
    e.target.value = ''
  }

  const removeFile = (id: string) => {
    setFiles(prev => prev.filter(f => f.id !== id))
  }

  const hasUploading = files.some(f => f.status === 'uploading')
  const canSend = input.trim() && !isLoading && !hasUploading

  return (
    <div ref={dropRef} className="w-full max-w-[860px] mx-auto relative">
      {/* Drag overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-50 rounded-2xl border-2 border-dashed border-primary/50 bg-primary/5 backdrop-blur-sm flex items-center justify-center pointer-events-none">
          <div className="text-center space-y-2">
            <Upload size={32} className="mx-auto text-primary/60" />
            <p className="text-small text-foreground font-medium">Drop files to attach</p>
          </div>
        </div>
      )}

      {/* File previews */}
      {files.length > 0 && (
        <div className="flex flex-wrap gap-2 pb-2">
          {files.map(f => (
            <div key={f.id} className="w-full sm:w-[calc(50%-4px)]">
              <FilePreview file={f} onRemove={removeFile} />
            </div>
          ))}
        </div>
      )}

      <div
        className={cn(
          'relative bg-elevated/80 backdrop-blur-sm border rounded-2xl shadow-2xl transition-all duration-200',
          focused ? 'border-primary/40 shadow-[0_0_0_1px_rgba(59,130,246,0.15)]' : 'border-border/60',
        )}
      >
        <div className="flex items-end px-2 py-1.5">
          {tools && onToggleTool && (
            <div className="relative">
              <button
                onClick={() => setToolsOpen(!toolsOpen)}
                className={cn(
                  'p-2 mb-[3px] rounded-lg transition-all shrink-0',
                  toolsOpen || tools.some(t => t.enabled)
                    ? 'text-primary hover:bg-primary/10'
                    : 'text-muted-foreground hover:text-foreground',
                )}
                title="Toggle tools"
              >
                <Wrench size={18} />
              </button>
              {toolsOpen && (
                <ToolPicker
                  tools={tools}
                  onToggle={onToggleTool}
                  onModeChange={onToolModeChange || (() => {})}
                  onClose={() => setToolsOpen(false)}
                />
              )}
            </div>
          )}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2 mb-[3px] text-muted-foreground hover:text-foreground rounded-lg transition-all shrink-0"
            title="Attach files"
          >
            <Paperclip size={20} />
          </button>

          <div className="relative flex-1">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder={isDragging ? 'Drop files here...' : placeholder}
              disabled={disabled || isLoading}
              rows={1}
              className="flex-1 w-full resize-none bg-transparent text-body text-foreground placeholder:text-muted-foreground/40 outline-none py-2.5 px-2 leading-relaxed"
              style={{ minHeight: '1.75rem', maxHeight: '10rem' }}
            />
            {input && !isLoading && (
              <button
                onClick={() => setInput('')}
                className="absolute bottom-2.5 right-1 p-1 text-muted-foreground/40 hover:text-foreground transition-colors"
              >
                <X size={14} />
              </button>
            )}
          </div>

          <button
            disabled={disabled || isLoading}
            className="p-2 mb-[3px] text-muted-foreground hover:text-foreground rounded-lg transition-all shrink-0"
            title="Voice input"
          >
            <Mic size={20} />
          </button>

          <div className="w-px h-6 bg-border/60 mx-1 mb-[3px]" />

          {isLoading ? (
            <button
              onClick={onStop}
              className="mb-[3px] bg-destructive text-destructive-foreground p-2 rounded-lg shrink-0 hover:brightness-110 transition-all"
              title="Stop generation"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
            </button>
          ) : (
            <button
              onClick={onSend}
              disabled={disabled || !canSend}
              className={cn(
                'mb-[3px] p-2 rounded-lg shrink-0 transition-all',
                canSend ? 'bg-primary text-primary-foreground hover:opacity-90' : 'text-muted-foreground',
              )}
              title="Send"
            >
              <ArrowUp size={20} />
            </button>
          )}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={uploadService.ALLOWED_TYPES.join(',')}
          className="hidden"
          onChange={handleFileChange}
        />
      </div>
    </div>
  )
}
