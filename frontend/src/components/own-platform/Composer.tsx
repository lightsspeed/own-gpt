import { useRef, useState, useEffect, useCallback } from 'react'
import { Paperclip, Mic, X, Upload, Wrench, Download, ChevronDown, FileText, FileCode, FileSpreadsheet, Plus, List } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { FilePreview } from './FilePreview'
import { ToolPicker } from './ToolPicker'
import { SlashCommands, type SlashCommand } from './SlashCommands'
import { uploadService } from '@/features/chat/services/uploadService'
import {
  hasExportableContent,
  exportConversationAsMarkdown,
  exportConversationAsTxt,
} from '@/features/chat/services/conversationExport'
import { ConversationOutline, type NavigatorAnchor } from './ConversationNavigator'
import type { AttachmentFile, ToolInfo, ToolMode, ContextItem, ContextCategory, MessageData } from '@/features/chat/types'

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
  messages?: MessageData[]
  onExportPdf?: () => void
  title?: string
  chapters?: NavigatorAnchor[]
  streamingId?: string | null
  onChapterClick?: (anchorId: string, targetMsgId: string) => void
}

function DownloadDropdown({
  messages = [],
  onExportPdf,
  title = 'OwnGPT Conversation',
  disabled = false,
}: {
  messages?: MessageData[]
  onExportPdf?: () => void
  title?: string
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const hasMessages = hasExportableContent(messages)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div ref={dropdownRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen(prev => !prev)}
        disabled={disabled || !hasMessages}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1.5 rounded-full border transition-all duration-200 text-xs font-medium',
          open
            ? 'border-primary/50 bg-primary/10 text-primary shadow-sm'
            : 'border-border/60 bg-surface/80 hover:bg-hover text-foreground/80 hover:text-foreground shadow-xs',
          'disabled:opacity-40 disabled:pointer-events-none cursor-pointer'
        )}
        title={hasMessages ? 'Download complete conversation' : 'No messages to download'}
      >
        <Download size={14} className="text-primary" />
        <span className="hidden sm:inline">Download</span>
        <ChevronDown size={12} className={cn('transition-transform duration-200', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 bottom-full mb-2 w-52 rounded-xl border border-border/80 bg-surface/95 backdrop-blur-md p-1 shadow-xl z-50 animate-in fade-in zoom-in-95">
          <div className="px-2.5 py-1.5 text-[10px] font-bold text-muted-foreground uppercase tracking-wider border-b border-border/40 mb-1">
            Download Full Chat
          </div>
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              if (onExportPdf) onExportPdf()
            }}
            className="flex items-center gap-2 w-full px-2.5 py-1.5 rounded-lg text-xs text-foreground hover:bg-hover transition-colors font-medium text-left"
          >
            <FileText size={14} className="text-red-500 shrink-0" />
            <span>Download as PDF</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              exportConversationAsMarkdown(messages, title)
            }}
            className="flex items-center gap-2 w-full px-2.5 py-1.5 rounded-lg text-xs text-foreground hover:bg-hover transition-colors font-medium text-left"
          >
            <FileCode size={14} className="text-blue-500 shrink-0" />
            <span>Download as Markdown</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              exportConversationAsTxt(messages, title)
            }}
            className="flex items-center gap-2 w-full px-2.5 py-1.5 rounded-lg text-xs text-foreground hover:bg-hover transition-colors font-medium text-left"
          >
            <FileSpreadsheet size={14} className="text-emerald-500 shrink-0" />
            <span>Download as TXT</span>
          </button>
        </div>
      )}
    </div>
  )
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
  messages = [],
  onExportPdf,
  title,
  chapters = [],
  streamingId,
  onChapterClick,
}: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const [files, setFiles] = useState<AttachmentFile[]>([])
  const [focused, setFocused] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [plusMenuOpen, setPlusMenuOpen] = useState(false)
  const plusMenuRef = useRef<HTMLDivElement>(null)

  const [exportMenuOpen, setExportMenuOpen] = useState(false)
  const exportMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!plusMenuOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (plusMenuRef.current && !plusMenuRef.current.contains(e.target as Node)) {
        setPlusMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [plusMenuOpen])

  const [topicsMenuOpen, setTopicsMenuOpen] = useState(false)
  const topicsMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!exportMenuOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setExportMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [exportMenuOpen])

  useEffect(() => {
    if (!topicsMenuOpen) return
    const handleClickOutside = (e: MouseEvent) => {
      if (topicsMenuRef.current && !topicsMenuRef.current.contains(e.target as Node)) {
        setTopicsMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [topicsMenuOpen])
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
        <div className="absolute inset-0 z-50 rounded-[28px] border-2 border-dashed border-primary/50 bg-primary/5 backdrop-blur-sm flex items-center justify-center pointer-events-none">
          <div className="text-center space-y-2">
            <Upload size={32} className="mx-auto text-primary/60" />
            <p className="text-small text-foreground font-medium">Drop files to attach</p>
          </div>
        </div>
      )}

      <div
        className={cn(
          'relative flex flex-col rounded-[28px] border transition-all duration-200 bg-surface/95 dark:bg-elevated/95 backdrop-blur-xl shadow-xl',
          focused
            ? 'border-primary/80 ring-2 ring-primary/20 shadow-[0_4px_30px_rgba(59,130,246,0.15)]'
            : 'border-border/70 hover:border-border/90 shadow-[0_4px_24px_rgba(0,0,0,0.06)]',
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
          <div className="flex flex-wrap gap-1.5 pt-3.5 px-5">
            {files.map(f => (
              <div key={f.id} className="flex-1 min-w-[200px]">
                <FilePreview file={f} onRemove={removeFile} />
              </div>
            ))}
          </div>
        )}

        {/* Inline context chips */}
        {hasContext && (
          <div className="flex items-center gap-1.5 pt-3 px-5 overflow-x-auto">
            {contextItems.map(item => {
              const meta = CATEGORY_META[item.category]
              return (
                <div
                  key={item.id}
                  className={cn(
                    'group flex items-center gap-1.5 shrink-0 px-2.5 py-1 rounded-full border text-[11px] font-medium transition-all',
                    meta.color,
                  )}
                >
                  <span className="max-w-[100px] truncate">{item.label}</span>
                  <button
                    onClick={() => onContextRemove?.(item.id)}
                    className="ml-0.5 p-0.5 rounded-full text-current/40 hover:text-current opacity-0 group-hover:opacity-100 transition-all duration-160"
                  >
                    <X size={10} />
                  </button>
                </div>
              )
            })}
          </div>
        )}

        {/* Main row: toolbar + textarea + actions */}
        <div className="flex items-end px-4 py-3 gap-2">
          {/* Left toolbar — single + action button */}
          <div className="flex items-center gap-1 shrink-0 pb-0.5" ref={plusMenuRef}>
            <div className="relative">
              <button
                type="button"
                onClick={() => setPlusMenuOpen(!plusMenuOpen)}
                className={cn(
                  'flex items-center justify-center w-9 h-9 rounded-full transition-all duration-200 relative',
                  plusMenuOpen
                    ? 'bg-primary text-primary-foreground rotate-45 shadow-md scale-105'
                    : 'text-muted-foreground/80 hover:text-foreground hover:bg-hover bg-muted/30 border border-border/40',
                )}
                title="Add content, tools, or outline"
              >
                <Plus size={18} className="transition-transform duration-200" />
                {activeToolCount > 0 && !plusMenuOpen && (
                  <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-primary text-[9px] font-bold text-white flex items-center justify-center">
                    {activeToolCount}
                  </span>
                )}
              </button>

              {plusMenuOpen && (
                <div
                  className="absolute left-0 bottom-full mb-2.5 w-64 py-2 rounded-2xl border border-border/60 bg-surface/95 dark:bg-elevated/95 backdrop-blur-xl shadow-2xl z-50 animate-scale-in origin-bottom-left"
                  onClick={e => e.stopPropagation()}
                >
                  {/* Attach Files */}
                  <button
                    onClick={() => {
                      setPlusMenuOpen(false)
                      fileInputRef.current?.click()
                    }}
                    className="flex items-center gap-3 w-full px-3.5 py-2.5 text-left hover:bg-hover/80 transition-colors group"
                  >
                    <Paperclip size={17} className="text-primary shrink-0 group-hover:scale-110 transition-transform" />
                    <div className="flex flex-col min-w-0">
                      <span className="text-small font-medium text-foreground">Attach Files</span>
                      <span className="text-[11px] text-muted-foreground/70">Upload documents, code, or images</span>
                    </div>
                  </button>

                  {/* Active AI Tools */}
                  {tools && onToggleTool && (
                    <button
                      onClick={() => {
                        setPlusMenuOpen(false)
                        setToolsOpen(true)
                      }}
                      className="flex items-center justify-between w-full px-3.5 py-2.5 text-left hover:bg-hover/80 transition-colors group"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <Wrench size={17} className="text-primary shrink-0 group-hover:scale-110 transition-transform" />
                        <div className="flex flex-col min-w-0">
                          <span className="text-small font-medium text-foreground">Active AI Tools</span>
                          <span className="text-[11px] text-muted-foreground/70">Web Search, KB, Python Sandbox</span>
                        </div>
                      </div>
                      <span className="px-2 py-0.5 rounded-full bg-primary/15 text-primary text-[10px] font-bold shrink-0">
                        {activeToolCount} Active
                      </span>
                    </button>
                  )}

                  {/* Export Conversation */}
                  <button
                    onClick={() => {
                      setPlusMenuOpen(false)
                      setExportMenuOpen(true)
                    }}
                    className="flex items-center justify-between w-full px-3.5 py-2.5 text-left hover:bg-hover/80 transition-colors group"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <Download size={17} className="text-primary shrink-0 group-hover:scale-110 transition-transform" />
                      <div className="flex flex-col min-w-0">
                        <span className="text-small font-medium text-foreground">Export Conversation</span>
                        <span className="text-[11px] text-muted-foreground/70">Save as PDF, Markdown, or Text</span>
                      </div>
                    </div>
                  </button>

                  {/* Topics */}
                  {chapters && chapters.length > 0 && onChapterClick && (
                    <button
                      onClick={() => {
                        setPlusMenuOpen(false)
                        setTopicsMenuOpen(true)
                      }}
                      className="flex items-center justify-between w-full px-3.5 py-2.5 text-left hover:bg-hover/80 transition-colors group"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <List size={17} className="text-primary shrink-0 group-hover:scale-110 transition-transform" />
                        <div className="flex flex-col min-w-0">
                          <span className="text-small font-medium text-foreground">Topics</span>
                          <span className="text-[11px] text-muted-foreground/70">Scroll to any question in this chat</span>
                        </div>
                      </div>
                      <span className="px-1.5 py-0.5 rounded-full bg-primary/10 text-primary text-[10px] font-bold shrink-0">{chapters.length}</span>
                    </button>
                  )}
                </div>
              )}

              {/* Export sub-menu popover */}
              {exportMenuOpen && (
                <div
                  ref={exportMenuRef}
                  className="absolute left-0 bottom-full mb-2.5 w-60 py-2 rounded-2xl border border-border/60 bg-surface/95 dark:bg-elevated/95 backdrop-blur-xl shadow-2xl z-50 animate-scale-in origin-bottom-left"
                  onClick={e => e.stopPropagation()}
                >
                  <div className="px-3.5 py-1 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider border-b border-border/40 mb-1">
                    Export Format
                  </div>

                  {onExportPdf && (
                    <button
                      onClick={() => {
                        setExportMenuOpen(false)
                        onExportPdf()
                      }}
                      className="flex items-center gap-3 w-full px-3.5 py-2 text-left text-small text-foreground hover:bg-hover/80 transition-colors"
                    >
                      <FileText size={16} className="text-primary shrink-0" />
                      <div className="flex flex-col min-w-0">
                        <span className="font-medium">PDF Document</span>
                        <span className="text-[10px] text-muted-foreground">Printable formatted document</span>
                      </div>
                    </button>
                  )}

                  <button
                    onClick={() => {
                      setExportMenuOpen(false)
                      exportConversationAsMarkdown(messages, title)
                    }}
                    className="flex items-center gap-3 w-full px-3.5 py-2 text-left text-small text-foreground hover:bg-hover/80 transition-colors"
                  >
                    <FileCode size={16} className="text-primary shrink-0" />
                    <div className="flex flex-col min-w-0">
                      <span className="font-medium">Markdown (.md)</span>
                      <span className="text-[10px] text-muted-foreground">Raw markdown text file</span>
                    </div>
                  </button>

                  <button
                    onClick={() => {
                      setExportMenuOpen(false)
                      exportConversationAsTxt(messages, title)
                    }}
                    className="flex items-center gap-3 w-full px-3.5 py-2 text-left text-small text-foreground hover:bg-hover/80 transition-colors"
                  >
                    <FileSpreadsheet size={16} className="text-primary shrink-0" />
                    <div className="flex flex-col min-w-0">
                      <span className="font-medium">Plain Text (.txt)</span>
                      <span className="text-[10px] text-muted-foreground">Unformatted text file</span>
                    </div>
                  </button>
                </div>
              )}

              {/* Topics upward popover */}
              {topicsMenuOpen && chapters && chapters.length > 0 && onChapterClick && (
                <div
                  ref={topicsMenuRef}
                  className="absolute left-0 bottom-full mb-2.5 w-72 py-2 rounded-2xl border border-border/60 bg-surface/95 dark:bg-elevated/95 backdrop-blur-xl shadow-2xl z-50 animate-scale-in origin-bottom-left"
                  onClick={e => e.stopPropagation()}
                >
                  <div className="px-3.5 py-1.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider border-b border-border/40 mb-1 flex items-center justify-between">
                    <span>Topics ({chapters.length})</span>
                    <button onClick={() => setTopicsMenuOpen(false)} className="text-muted-foreground/50 hover:text-foreground transition-colors">
                      <X size={13} />
                    </button>
                  </div>
                  <div className="max-h-64 overflow-y-auto custom-scrollbar py-1">
                    {chapters.map((c, i) => (
                      <button
                        key={c.id}
                        onClick={() => {
                          setTopicsMenuOpen(false)
                          onChapterClick(c.id, c.targetMsgId)
                        }}
                        className="flex items-start gap-3 w-full px-3.5 py-2 text-left hover:bg-hover/80 transition-colors group"
                      >
                        <span className="text-[11px] font-bold text-primary/60 group-hover:text-primary pt-0.5 w-4 shrink-0">{i + 1}</span>
                        <span className="text-sm text-foreground/80 group-hover:text-foreground leading-snug">{c.label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Textarea */}
          <div className="relative flex-1 min-w-0 px-1">
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
              className="w-full resize-none bg-transparent outline-none text-[15px] text-foreground placeholder:text-muted-foreground/60 placeholder:font-normal leading-relaxed"
              style={{ minHeight: '1.75rem', maxHeight: '10rem', paddingTop: '3px' }}
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
                  'flex items-center justify-center w-9 h-9 rounded-full transition-all duration-160 relative',
                  isListening
                    ? 'bg-red-500/15 text-red-500 border border-red-500/30 animate-pulse'
                    : 'text-muted-foreground/70 hover:text-foreground hover:bg-hover',
                )}
                title={isListening ? 'Listening... (Click to stop)' : 'Voice input (Click to speak)'}
              >
                <Mic size={18} className={isListening ? 'text-red-500' : ''} />
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

            <div className="w-px h-5 bg-border/60 mx-0.5" />

            {isLoading ? (
              <button
                onClick={onStop}
                className="flex items-center justify-center w-9 h-9 rounded-full bg-destructive text-destructive-foreground hover:brightness-110 transition-all duration-160 shrink-0 shadow-sm"
                title="Stop generation"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
              </button>
            ) : (
              <button
                onClick={onSend}
                disabled={disabled || !canSend}
                className={cn(
                  'flex items-center justify-center w-9 h-9 rounded-full transition-all duration-200 shrink-0',
                  canSend
                    ? 'bg-primary text-primary-foreground hover:brightness-110 hover:scale-105 active:scale-[0.95] shadow-[0_2px_12px_rgba(59,130,246,0.4)]'
                    : 'bg-muted/20 text-muted-foreground/30 cursor-not-allowed',
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
