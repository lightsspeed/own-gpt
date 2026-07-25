import { useState } from 'react'
import { cn } from '@/lib/utils'
import { X, Sparkles, Palette, Globe, Shield, Bell, Sliders, ChevronRight } from 'lucide-react'

interface SettingsPanelProps {
  open: boolean
  onClose: () => void
}

const SETTINGS_SECTIONS = [
  {
    id: 'appearance',
    label: 'Appearance',
    icon: <Palette size={18} />,
    desc: 'Theme, font size, density',
    content: (
      <div className="space-y-3">
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border">
          <span className="text-small text-foreground">Theme</span>
          <span className="text-small text-muted-foreground">Dark (default)</span>
        </div>
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border">
          <span className="text-small text-foreground">Font size</span>
          <span className="text-small text-muted-foreground">Medium</span>
        </div>
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border">
          <span className="text-small text-foreground">Density</span>
          <span className="text-small text-muted-foreground">Comfortable</span>
        </div>
      </div>
    ),
  },
  {
    id: 'model',
    label: 'Model Configuration',
    icon: <Sliders size={18} />,
    desc: 'Default model, temperature, tokens',
    content: (
      <div className="space-y-3">
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border">
          <span className="text-small text-foreground">Default model</span>
          <span className="text-small text-muted-foreground">GPT-4o Mini</span>
        </div>
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border">
          <span className="text-small text-foreground">Temperature</span>
          <span className="text-small text-muted-foreground">0.7</span>
        </div>
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border">
          <span className="text-small text-foreground">Max tokens</span>
          <span className="text-small text-muted-foreground">4,096</span>
        </div>
      </div>
    ),
  },
  {
    id: 'kb',
    label: 'Knowledge Base',
    icon: <Globe size={18} />,
    desc: 'Connected corpora, auto-search',
    content: (
      <div className="space-y-3">
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border">
          <span className="text-small text-foreground">Auto-search KB</span>
          <span className="text-small text-success">On</span>
        </div>
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border">
          <span className="text-small text-foreground">Connected corpora</span>
          <span className="text-small text-muted-foreground">3 sources</span>
        </div>
      </div>
    ),
  },
  {
    id: 'privacy',
    label: 'Privacy & Security',
    icon: <Shield size={18} />,
    desc: 'Data retention, PII masking',
    content: (
      <div className="space-y-3">
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border">
          <span className="text-small text-foreground">PII masking</span>
          <span className="text-small text-success">Enabled</span>
        </div>
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border">
          <span className="text-small text-foreground">Data retention</span>
          <span className="text-small text-muted-foreground">30 days</span>
        </div>
      </div>
    ),
  },
  {
    id: 'notifications',
    label: 'Notifications',
    icon: <Bell size={18} />,
    desc: 'Alert preferences, digest frequency',
    content: (
      <div className="space-y-3">
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border">
          <span className="text-small text-foreground">Push alerts</span>
          <span className="text-small text-success">On</span>
        </div>
        <div className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border border-border">
          <span className="text-small text-foreground">Digest frequency</span>
          <span className="text-small text-muted-foreground">Daily</span>
        </div>
      </div>
    ),
  },
]

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const [activeSection, setActiveSection] = useState<string | null>(null)

  const section = SETTINGS_SECTIONS.find(s => s.id === activeSection)

  return (
    <>
      {open && <div className="fixed inset-0 z-50 bg-black/40" onClick={onClose} />}
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
            <span className="text-small font-bold text-foreground">Settings</span>
          </div>
          <button onClick={onClose} className="p-2 text-muted-foreground hover:text-foreground transition-colors rounded-lg">
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {activeSection && section ? (
            <div className="p-5 space-y-4">
              <button onClick={() => setActiveSection(null)} className="flex items-center gap-1.5 text-small text-muted-foreground hover:text-foreground transition-colors">
                <ChevronRight size={14} className="rotate-180" />
                Back
              </button>
              <h3 className="text-title font-semibold text-foreground">{section.label}</h3>
              <p className="text-caption text-muted-foreground">{section.desc}</p>
              {section.content}
            </div>
          ) : (
            <div className="p-4 space-y-1">
              {SETTINGS_SECTIONS.map(s => (
                <button
                  key={s.id}
                  onClick={() => setActiveSection(s.id)}
                  className="w-full flex items-center gap-3 p-3 rounded-xl hover:bg-hover transition-all text-left"
                >
                  <div className="w-9 h-9 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
                    {s.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-small font-medium text-foreground">{s.label}</p>
                    <p className="text-caption text-muted-foreground truncate">{s.desc}</p>
                  </div>
                  <ChevronRight size={16} className="text-muted-foreground/40 shrink-0" />
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
