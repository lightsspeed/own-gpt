import { useRef, useState, useEffect, useCallback } from 'react'
import { Paperclip, Mic, X, Upload, Wrench } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { FilePreview } from './FilePreview'
import { ToolPicker } from './ToolPicker'
import { SlashCommands, type SlashCommand } from './SlashCommands'
import { uploadService } from '@/features/chat/services/uploadService'
import type { AttachmentFile, ToolInfo, ToolMode, ContextItem, ContextCategory } from '@/features/chat/types'

declare global {
  interface Window {
    SpeechRecognition: any
    webkitSpeechRecognition: any
  }
}

const CATEGORY_META: Record<ContextCategory, { color: string }> = {
  environment: { color: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' },
  service: { color: 'bg-sky-500/15 text-sky-400 border-sky-500/20' },
  artifact: { color: 'bg-orange-500/15 text-orange-400 border-orange-500/20' },
  experiment: { color: 'bg-purple-500/15 text-purple-400 border-purple-500/20' },
  knowledge: { color: 'bg-blue-500/15 text-blue-400 border-blue-500/20' },
  timeframe: { color: 'bg-amber-500/15 text-amber-400 border-amber-500/20' },
  custom: { color: 'bg-muted/30 text-muted-foreground border-muted/30' },
}

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
  contextItems?: ContextItem[]
  onContextRemove?: (id: string) => void
  projectId?: string | null
}

export function Composer({
  input,
  setInput,
  onSend,
  onStop,
  isLoading = false,
  disabled = false,
  placeholder = 'Message OwnGPT...',
  tools,
  onToggleTool,
  onToolModeChange,
  contextItems,
  onContextRemove,
  projectId,
}: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const [files, setFiles] = useState<AttachmentFile[]>([])
  const [focused, setFocused] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)
  const [slashOpen, setSlashOpen] = useState(false)
  const [slashQuery, setSlashQuery] = useState('')
  const [isListening, setIsListening] = useState(false)
  const [speechError, setSpeechError] = useState<string | null>(null)
  const recognitionRef = useRef<any>(null)
  const baseInputRef = useRef<string>('')

  const toggleListening = useCallback(() => {
    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop()
      }
      setIsListening(false)
      return
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setSpeechError('Voice input is not supported in this browser.')
      setTimeout(() => setSpeechError(null), 3500)
      return
    }

    try {
      const recognition = new SpeechRecognition()
      recognition.continuous = true
      recognition.interimResults = true
      recognition.lang = navigator.language || 'en-US'

      baseInputRef.current = input

      recognition.onresult = (event: any) => {
        let transcript = ''
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript
        }
        if (transcript) {
          const base = baseInputRef.current
          const prefix = base ? (base.endsWith(' ') ? base : base + ' ') : ''
          setInput(prefix + transcript)
        }
      }

      recognition.onerror = (event: any) => {
        setIsListening(false)
        if (event.error === 'not-allowed') {
          setSpeechError('Microphone access denied by browser.')
        } else if (event.error !== 'no-speech') {
          setSpeechError(`Voice recognition error: ${event.error}`)
        }
        setTimeout(() => setSpeechError(null), 3500)
      }

      recognition.onend = () => {
        setIsListening(false)
      }

      recognition.start()
      recognitionRef.current = recognition
      setIsListening(true)
      setSpeechError(null)
    } catch (err: any) {
      setIsListening(false)
      setSpeechError('Could not start voice recognition.')
      setTimeout(() => setSpeechError(null), 3500)
    }
  }, [input, isListening, setInput])

  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.stop()
      }
    }
  }, [])

  const autoResize = () => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
  }

  useEffect(() => { autoResize() }, [input])

  const handleInputChange = (val: string) => {
    setInput(val)
    const trimmed = val.trimStart()
    if (trimmed.startsWith('/') && !trimmed.includes(' ')) {
      const q = trimmed.slice(1)
      setSlashQuery(q)
      setSlashOpen(true)
    } else if (slashOpen && (trimmed === '' || trimmed.includes(' '))) {
      setSlashOpen(false)
    }
  }

  const handleSlashSelect = (cmd: SlashCommand) => {
    setSlashOpen(false)
    if (cmd.action.type === 'fill') {
      setInput(cmd.action.value)
    } else if (cmd.action.type === 'navigate') {
      navigate(cmd.action.value)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (slashOpen) return
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
          name: f.name, size: f.size, type: f.type || 'application/octet-stream',
          status: 'error', progress: 0, error: `Unsupported file type`,
        })
        continue
      }
      if (f.size > uploadService.MAX_SIZE) {
        newFiles.push({
          id: `file-${Date.now()}-${Math.random().toString(36).slice(2)}`,
          name: f.name, size: f.size, type: f.type || 'application/octet-stream',
          status: 'error', progress: 0, error: `File too large (max ${uploadService.formatSize(uploadService.MAX_SIZE)})`,
        })
        continue
      }
      const id = `file-${Date.now()}-${Math.random().toString(36).slice(2)}`
      const preview = uploadService.canPreview(f.type) ? await uploadService.readAsDataURL(f).catch(() => undefined) : undefined
      newFiles.push({ id, name: f.name, size: f.size, type: f.type || 'application/octet-stream', status: 'uploading', progress: 0, preview })
      uploadService.uploadFile(f, (p) => {
        setFiles(prev => prev.map(pf => pf.id === id ? { ...pf, progress: p } : pf))
      }, projectId).then(result => {
        setFiles(prev => prev.map(pf => pf.id === id ? { ...pf, status: 'uploaded', url: result.url, progress: 100 } : pf))
      }).catch(err => {
        setFiles(prev => prev.map(pf => pf.id === id ? { ...pf, status: 'error', error: err.message } : pf))
      })
    }
    setFiles(prev => [...prev, ...newFiles])
  }, [projectId])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const onDragOver = (e: DragEvent) => { e.preventDefault(); setIsDragging(true) }
    const onDragLeave = () => setIsDragging(false)
    const onDrop = (e: DragEvent) => {
      e.preventDefault(); setIsDragging(false)
      if (e.dataTransfer?.files && e.dataTransfer.files.length > 0) processFiles(e.dataTransfer.files)
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
    if (e.target.files && e.target.files.length > 0) processFiles(e.target.files)
    e.target.value = ''
  }

  const removeFile = (id: string) => setFiles(prev => prev.filter(f => f.id !== id))

  const hasUploading = files.some(f => f.status === 'uploading')
  const canSend = input.trim() && !isLoading && !hasUploading
  const activeToolCount = tools?.filter(t => t.enabled).length || 0
  const hasContext = contextItems && contextItems.length > 0
  const hasAttachments = files.length > 0

  return (
    <div ref={containerRef} className="w-full max-w-[920px] mx-auto relative">
      {isDragging && (
        <div className="absolute inset-0 z-50 rounded-[18px] border-2 border-dashed border-primary/50 bg-primary/5 backdrop-blur-sm flex items-center justify-center pointer-events-none">
          <div className="text-center space-y-2">
            <Upload size={32} className="mx-auto text-primary/60" />
            <p className="text-small text-foreground font-medium">Drop files to attach</p>
          </div>
        </div>
      )}

      <div
        className={cn(
          'relative flex flex-col rounded-[18px] border shadow-2xl transition-all duration-160 bg-elevated/90 backdrop-blur-sm',
          focused
            ? 'border-primary shadow-[0_0_0_3px_rgba(59,130,246,0.12)]'
            : 'border-border/60',
        )}
      >
        {/* Slash commands (positioned above) */}
        {slashOpen && (
          <div className="absolute bottom-full left-0 right-0 mb-2 z-50">
            <SlashCommands
              query={slashQuery}
              onSelect={handleSlashSelect}
              onClose={() => setSlashOpen(false)}
            />
          </div>
        )}

        {/* Inline attachments */}
        {hasAttachments && (
          <div className="flex flex-wrap gap-1.5 pt-3 px-[18px]">
            {files.map(f => (
              <div key={f.id} className="flex-1 min-w-[200px]">
                <FilePreview file={f} onRemove={removeFile} />
              </div>
            ))}
          </div>
        )}

        {/* Inline context chips */}
        {hasContext && (
          <div className="flex items-center gap-1.5 pt-2.5 px-[18px] overflow-x-auto">
            {contextItems.map(item => {
              const meta = CATEGORY_META[item.category]
              return (
                <div
                  key={item.id}
                  className={cn(
                    'group flex items-center gap-1.5 shrink-0 px-2 py-1 rounded-lg border text-[11px] font-medium transition-all',
                    meta.color,
                  )}
                >
                  <span className="max-w-[100px] truncate">{item.label}</span>
                  <button
                    onClick={() => onContextRemove?.(item.id)}
                    className="ml-0.5 p-0.5 rounded text-current/40 hover:text-current opacity-0 group-hover:opacity-100 transition-all duration-160"
                  >
                    <X size={10} />
                  </button>
                </div>
              )
            })}
          </div>
        )}

        {/* Main row: toolbar + textarea + actions */}
        <div className="flex items-end px-[18px] py-[14px] gap-2">
          {/* Left toolbar */}
          <div className="flex items-center gap-1.5 shrink-0 pb-0.5">
            {tools && onToggleTool && (
              <div className="relative">
                <button
                  onClick={() => setToolsOpen(!toolsOpen)}
                    className={cn(
                      'flex items-center justify-center w-9 h-9 rounded-[10px] transition-all duration-160',
                      toolsOpen || activeToolCount > 0
                        ? 'bg-primary/[0.08] text-primary hover:bg-primary/[0.12]'
                        : 'text-muted-foreground/60 hover:text-foreground hover:bg-white/[0.05]',
                  )}
                  title="Toggle tools"
                >
                  <Wrench size={17} />
                  {activeToolCount > 0 && (
                    <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-primary text-[9px] font-bold text-white flex items-center justify-center">
                      {activeToolCount}
                    </span>
                  )}
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
              className="flex items-center justify-center w-9 h-9 rounded-[10px] transition-all duration-160 text-muted-foreground/60 hover:text-foreground hover:bg-white/[0.05]"
              title="Attach files"
            >
              <Paperclip size={18} />
            </button>
          </div>

          {/* Textarea */}
          <div className="relative flex-1 min-w-0">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={e => handleInputChange(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder={isDragging ? 'Drop files here...' : placeholder}
              disabled={disabled || isLoading}
              rows={1}
              className="w-full resize-none bg-transparent outline-none text-[16px] text-foreground placeholder:text-foreground/55 placeholder:font-normal leading-relaxed"
              style={{ minHeight: '1.75rem', maxHeight: '10rem', paddingTop: '2px' }}
            />
          </div>

          {/* Right actions */}
          <div className="flex items-center gap-1.5 shrink-0 pb-0.5">
            <div className="relative">
              <button
                type="button"
                onClick={toggleListening}
                disabled={disabled || isLoading}
                className={cn(
                  'flex items-center justify-center w-9 h-9 rounded-[10px] transition-all duration-160 relative',
                  isListening
                    ? 'bg-red-500/15 text-red-400 border border-red-500/30 animate-pulse'
                    : 'text-muted-foreground/60 hover:text-foreground hover:bg-white/[0.05]',
                )}
                title={isListening ? 'Listening... (Click to stop)' : 'Voice input (Click to speak)'}
              >
                <Mic size={18} className={isListening ? 'text-red-400' : ''} />
                {isListening && (
                  <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-red-500 animate-ping" />
                )}
              </button>
              {speechError && (
                <div className="absolute bottom-full right-0 mb-2 whitespace-nowrap text-xs bg-red-950/90 text-red-200 border border-red-800/50 px-2.5 py-1 rounded-md shadow-lg z-50 animate-in fade-in">
                  {speechError}
                </div>
              )}
            </div>

            <div className="w-px h-6 bg-foreground/[0.18] mx-0.5" />

            {isLoading ? (
              <button
                onClick={onStop}
                className="flex items-center justify-center w-9 h-9 rounded-full bg-destructive text-destructive-foreground hover:brightness-110 transition-all duration-160 shrink-0"
                title="Stop generation"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
              </button>
            ) : (
              <button
                onClick={onSend}
                disabled={disabled || !canSend}
                className={cn(
                  'flex items-center justify-center w-9 h-9 rounded-full transition-all duration-160 shrink-0',
                  canSend
                    ? 'bg-primary text-primary-foreground hover:scale-105 active:scale-[0.96] shadow-md'
                    : 'bg-muted/10 text-muted-foreground/35',
                )}
                title="Send"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 19V5" />
                  <path d="M5 12l7-7 7 7" />
                </svg>
              </button>
            )}
          </div>
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
