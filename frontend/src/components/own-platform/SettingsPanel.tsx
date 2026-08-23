import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { X, Sparkles, Palette, Globe, Shield, Sliders, ChevronRight, Check, Sun, Moon, RefreshCw, Save } from 'lucide-react'
import { api } from '@/features/chat/services/chatApi'

interface SettingsPanelProps {
  open: boolean
  onClose: () => void
}

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const [activeSection, setActiveSection] = useState<string | null>(null)
  const [isDark, setIsDark] = useState<boolean>(() => {
    if (typeof document === 'undefined') return true
    return document.documentElement.classList.contains('dark')
  })
  const [supportedModels, setSupportedModels] = useState<string[]>([])
  const [providerName, setProviderName] = useState<string>('')
  const [selectedModel, setSelectedModel] = useState<string>(() => localStorage.getItem('own_gpt_model') || 'gemini-3.6-flash')

  useEffect(() => {
    api.fetchModels().then(data => {
      if (data && data.models && data.models.length > 0) {
        setSupportedModels(data.models)
        setProviderName(data.provider)
        const saved = localStorage.getItem('own_gpt_model')
        if (!saved || !data.models.includes(saved)) {
          setSelectedModel(data.default_model || data.models[0])
        }
      }
    })
  }, [])
  const [temperature, setTemperature] = useState<number>(() => parseFloat(localStorage.getItem('own_gpt_temp') || '0.7'))
  const [maxTokens, setMaxTokens] = useState<number>(() => parseInt(localStorage.getItem('own_gpt_max_tokens') || '4096', 10))
  const [autoKbSearch, setAutoKbSearch] = useState<boolean>(() => localStorage.getItem('own_gpt_auto_kb') !== 'false')
  const [piiMasking, setPiiMasking] = useState<boolean>(() => localStorage.getItem('own_gpt_pii') !== 'false')
  const [savedNotice, setSavedNotice] = useState<boolean>(false)
  const [cacheCleared, setCacheCleared] = useState<boolean>(false)
  const [isDirty, setIsDirty] = useState<boolean>(false)

  // Track initial values to detect changes
  const [savedModel, setSavedModel] = useState(selectedModel)
  const [savedTemp, setSavedTemp] = useState(temperature)
  const [savedMaxTokens, setSavedMaxTokens] = useState(maxTokens)
  const [savedAutoKb, setSavedAutoKb] = useState(autoKbSearch)
  const [savedPii, setSavedPii] = useState(piiMasking)

  useEffect(() => {
    if (typeof document === 'undefined') return
    if (isDark) {
      document.documentElement.classList.add('dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.classList.remove('dark')
      localStorage.setItem('theme', 'light')
    }
  }, [isDark])

  // Detect dirty state whenever any setting changes
  useEffect(() => {
    const dirty =
      selectedModel !== savedModel ||
      temperature !== savedTemp ||
      maxTokens !== savedMaxTokens ||
      autoKbSearch !== savedAutoKb ||
      piiMasking !== savedPii
    setIsDirty(dirty)
  }, [selectedModel, temperature, maxTokens, autoKbSearch, piiMasking, savedModel, savedTemp, savedMaxTokens, savedAutoKb, savedPii])

  const handleSave = () => {
    localStorage.setItem('own_gpt_model', selectedModel)
    localStorage.setItem('own_gpt_temp', temperature.toString())
    localStorage.setItem('own_gpt_max_tokens', maxTokens.toString())
    localStorage.setItem('own_gpt_auto_kb', autoKbSearch ? 'true' : 'false')
    localStorage.setItem('own_gpt_pii', piiMasking ? 'true' : 'false')
    // Commit saved baseline
    setSavedModel(selectedModel)
    setSavedTemp(temperature)
    setSavedMaxTokens(maxTokens)
    setSavedAutoKb(autoKbSearch)
    setSavedPii(piiMasking)
    setIsDirty(false)
    setSavedNotice(true)
    setTimeout(() => setSavedNotice(false), 2500)
  }

  const handleClearCache = () => {
    sessionStorage.clear()
    setCacheCleared(true)
    setTimeout(() => setCacheCleared(false), 2500)
  }

  const SETTINGS_SECTIONS = [
    {
      id: 'appearance',
      label: 'Appearance',
      icon: <Palette size={18} />,
      desc: 'Theme, color mode, and UI layout',
      content: (
        <div className="space-y-4">
          <div className="p-3.5 rounded-xl bg-muted/30 border border-border/60 space-y-2.5">
            <span className="text-small font-medium text-foreground block">Color Theme</span>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setIsDark(false)}
                className={cn(
                  'flex items-center justify-center gap-2 p-2.5 rounded-lg border text-small transition-all',
                  !isDark
                    ? 'border-primary bg-primary/10 text-primary font-semibold shadow-sm'
                    : 'border-border/60 bg-surface/50 text-muted-foreground hover:text-foreground hover:bg-hover',
                )}
              >
                <Sun size={15} /> Light
              </button>
              <button
                onClick={() => setIsDark(true)}
                className={cn(
                  'flex items-center justify-center gap-2 p-2.5 rounded-lg border text-small transition-all',
                  isDark
                    ? 'border-primary bg-primary/10 text-primary font-semibold shadow-sm'
                    : 'border-border/60 bg-surface/50 text-muted-foreground hover:text-foreground hover:bg-hover',
                )}
              >
                <Moon size={15} /> Dark
              </button>
            </div>
          </div>
        </div>
      ),
    },
    {
      id: 'model',
      label: 'Model & Generation',
      icon: <Sliders size={18} />,
      desc: 'Default model, temperature, max tokens',
      content: (
        <div className="space-y-4">
          <div className="p-3.5 rounded-xl bg-muted/30 border border-border/60 space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-small font-medium text-foreground block">Active Model</label>
              {providerName && <span className="text-xs uppercase font-mono text-muted-foreground/60 font-semibold">{providerName}</span>}
            </div>
            <select
              value={selectedModel}
              onChange={e => setSelectedModel(e.target.value)}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-small text-foreground outline-none focus:border-primary font-mono"
            >
              {supportedModels.length > 0 ? (
                supportedModels.map(m => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))
              ) : (
                <option value={selectedModel}>{selectedModel}</option>
              )}
            </select>
          </div>

          <div className="p-3.5 rounded-xl bg-muted/30 border border-border/60 space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-small font-medium text-foreground">Temperature</label>
              <span className="text-small font-mono text-primary font-semibold">{temperature}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={temperature}
              onChange={e => setTemperature(parseFloat(e.target.value))}
              className="w-full accent-primary cursor-pointer"
            />
            <p className="text-[11px] text-muted-foreground">Lower values are more precise; higher values are more creative.</p>
          </div>

          <div className="p-3.5 rounded-xl bg-muted/30 border border-border/60 space-y-2">
            <label className="text-small font-medium text-foreground block">Max Response Tokens</label>
            <select
              value={maxTokens}
              onChange={e => setMaxTokens(parseInt(e.target.value, 10))}
              className="w-full bg-background border border-border rounded-lg px-3 py-2 text-small text-foreground outline-none focus:border-primary"
            >
              <option value={2048}>2,048 tokens</option>
              <option value={4096}>4,096 tokens (Default)</option>
              <option value={8192}>8,192 tokens</option>
            </select>
          </div>
        </div>
      ),
    },
    {
      id: 'kb',
      label: 'Knowledge Base & Search',
      icon: <Globe size={18} />,
      desc: 'Retrieval settings and source grounding',
      content: (
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-muted/30 border border-border/60">
            <div>
              <p className="text-small font-medium text-foreground">Auto-search Knowledge Base</p>
              <p className="text-[11px] text-muted-foreground">Automatically query connected corpora when relevant</p>
            </div>
            <button
              onClick={() => setAutoKbSearch(!autoKbSearch)}
              className={cn(
                'w-11 h-6 rounded-full transition-colors relative shrink-0 p-0.5',
                autoKbSearch ? 'bg-primary' : 'bg-muted-foreground/30',
              )}
            >
              <div className={cn('w-5 h-5 rounded-full bg-white transition-transform shadow-md', autoKbSearch ? 'translate-x-5' : 'translate-x-0')} />
            </button>
          </div>
        </div>
      ),
    },
    {
      id: 'privacy',
      label: 'Privacy & Storage',
      icon: <Shield size={18} />,
      desc: 'PII masking and local browser cache',
      content: (
        <div className="space-y-4">
          <div className="flex items-center justify-between p-3.5 rounded-xl bg-muted/30 border border-border/60">
            <div>
              <p className="text-small font-medium text-foreground">PII Masking</p>
              <p className="text-[11px] text-muted-foreground">Mask sensitive tokens before sending to LLMs</p>
            </div>
            <button
              onClick={() => setPiiMasking(!piiMasking)}
              className={cn(
                'w-11 h-6 rounded-full transition-colors relative shrink-0 p-0.5',
                piiMasking ? 'bg-primary' : 'bg-muted-foreground/30',
              )}
            >
              <div className={cn('w-5 h-5 rounded-full bg-white transition-transform shadow-md', piiMasking ? 'translate-x-5' : 'translate-x-0')} />
            </button>
          </div>

          <div className="p-3.5 rounded-xl bg-muted/30 border border-border/60 space-y-2">
            <p className="text-small font-medium text-foreground">Local Cache</p>
            <p className="text-[11px] text-muted-foreground">Clear transient state cached in your browser session.</p>
            <button
              onClick={handleClearCache}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border/60 bg-hover/50 text-small text-muted-foreground hover:text-foreground transition-all"
            >
              <RefreshCw size={13} /> {cacheCleared ? 'Cache Cleared!' : 'Clear Local Cache'}
            </button>
          </div>
        </div>
      ),
    },
  ]

  const section = SETTINGS_SECTIONS.find(s => s.id === activeSection)

  return (
    <>
      {open && <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs" onClick={onClose} />}
      <div
        className={cn(
          'fixed right-0 top-0 h-full w-[420px] bg-surface border-l border-border z-[60] shadow-2xl transition-transform duration-300 flex flex-col',
          open ? 'translate-x-0' : 'translate-x-full',
        )}
      >
        {/* Header */}
        <div className="h-16 flex items-center justify-between px-5 border-b border-border shrink-0">
          <div className="flex items-center gap-3">
            <Sparkles size={18} className="text-primary" />
            <span className="text-small font-bold text-foreground">Platform Settings</span>
          </div>
          <button onClick={onClose} className="p-2 text-muted-foreground hover:text-foreground transition-colors rounded-lg">
            <X size={18} />
          </button>
        </div>

        {savedNotice && (
          <div className="bg-emerald-500/15 border-b border-emerald-500/30 px-5 py-2 flex items-center gap-2 text-emerald-500 text-xs font-medium animate-in fade-in">
            <Check size={14} /> Settings saved successfully!
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
          {activeSection && section ? (
            <div className="space-y-4">
              <button onClick={() => setActiveSection(null)} className="flex items-center gap-1.5 text-small text-muted-foreground hover:text-foreground transition-colors">
                <ChevronRight size={14} className="rotate-180" />
                Back to all settings
              </button>
              <div>
                <h3 className="text-title font-semibold text-foreground">{section.label}</h3>
                <p className="text-caption text-muted-foreground">{section.desc}</p>
              </div>
              {section.content}
            </div>
          ) : (
            <div className="space-y-1.5">
              {SETTINGS_SECTIONS.map(s => (
                <button
                  key={s.id}
                  onClick={() => setActiveSection(s.id)}
                  className="w-full flex items-center gap-3 p-3 rounded-xl hover:bg-hover transition-all text-left group border border-transparent hover:border-border/40"
                >
                  <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
                    {s.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-small font-medium text-foreground group-hover:text-primary transition-colors">{s.label}</p>
                    <p className="text-caption text-muted-foreground truncate">{s.desc}</p>
                  </div>
                  <ChevronRight size={16} className="text-muted-foreground/40 shrink-0 group-hover:translate-x-0.5 transition-transform" />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer with Save Action */}
        <div className="p-4 border-t border-border bg-surface shrink-0 flex items-center justify-between">
          <span className="text-caption text-muted-foreground">OwnGPT Platform v3.3</span>
          {isDirty && (
            <button
              onClick={handleSave}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-small font-medium hover:brightness-110 active:scale-95 transition-all shadow-md animate-in fade-in"
            >
              <Save size={14} /> Save Changes
            </button>
          )}
        </div>
      </div>
    </>
  )
}
