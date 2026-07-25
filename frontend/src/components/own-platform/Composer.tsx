import { useRef, useState, useEffect } from 'react'
import { ArrowUp, Paperclip, Mic, X } from 'lucide-react'

interface ComposerProps {
  input: string
  setInput: (val: string) => void
  onSend: () => void
  onStop?: () => void
  isLoading?: boolean
  disabled?: boolean
  placeholder?: string
}

export function Composer({
  input,
  setInput,
  onSend,
  onStop,
  isLoading = false,
  disabled = false,
  placeholder = 'Ask anything...',
}: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [files, setFiles] = useState<{ name: string; size: number }[]>([])
  const [focused, setFocused] = useState(false)

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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newFiles = Array.from(e.target.files || [])
    setFiles(prev => [...prev, ...newFiles.map(f => ({ name: f.name, size: f.size }))])
    e.target.value = ''
  }

  return (
    <div className="w-full max-w-[860px] mx-auto">
      <div
        className={`relative bg-elevated/80 backdrop-blur-sm border rounded-2xl shadow-2xl transition-all duration-200 ${
          focused ? 'border-primary/40 shadow-[0_0_0_1px_rgba(59,130,246,0.15)]' : 'border-border/60'
        }`}
      >
        {files.length > 0 && (
          <div className="flex flex-wrap gap-2 px-3 pt-3">
            {files.map(f => (
              <div key={f.name} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-primary/10 border border-primary/20 text-small text-primary">
                <Paperclip size={12} />
                <span className="max-w-[140px] truncate">{f.name}</span>
                <button onClick={() => setFiles(prev => prev.filter(x => x.name !== f.name))} className="ml-0.5 text-muted-foreground hover:text-foreground">
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-end px-2 py-1.5">
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
              placeholder={placeholder}
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
              disabled={disabled || !input.trim()}
              className={`mb-[3px] p-2 rounded-lg shrink-0 transition-all ${
                input.trim()
                  ? 'bg-primary text-primary-foreground hover:opacity-90'
                  : 'text-muted-foreground'
              }`}
              title="Send"
            >
              <ArrowUp size={20} />
            </button>
          )}
        </div>

        <input ref={fileInputRef} type="file" multiple accept=".pdf,.txt,.md,.csv,.json" className="hidden" onChange={handleFileChange} />
      </div>
    </div>
  )
}
