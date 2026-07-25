import { useRef, useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import {
  HelpCircle, BookOpen, BarChart3, FlaskConical, RefreshCw, Wrench, AlertTriangle,
  Cloud, Globe, Search, MessageSquare, Plus, Settings, Hash
} from 'lucide-react'
import type { ChatSession } from '@/features/chat/types'

export interface SlashAction {
  type: 'fill' | 'navigate'
  value: string
}

export interface SlashCommand {
  command: string
  label: string
  description: string
  icon: React.ReactNode
  category: string
  action: SlashAction
}

const COMMANDS: SlashCommand[] = [
  { command: 'help', label: 'Help', description: 'Show available commands and how to use OwnGPT', icon: <HelpCircle size={15} />, category: 'General', action: { type: 'fill', value: 'What can you help me with?' } },
  { command: 'knowledge', label: 'Search Knowledge', description: 'Search the connected knowledge base', icon: <BookOpen size={15} />, category: 'Knowledge', action: { type: 'fill', value: 'Search knowledge base for ' } },
  { command: 'kb', label: 'Knowledge Base', description: 'Query documents in the knowledge base', icon: <BookOpen size={15} />, category: 'Knowledge', action: { type: 'fill', value: 'Search knowledge base for ' } },
  { command: 'monitor', label: 'Monitor', description: 'Check system health and metrics', icon: <BarChart3 size={15} />, category: 'Operations', action: { type: 'fill', value: 'Show me the current system health status' } },
  { command: 'evaluate', label: 'Evaluate', description: 'Run or review evaluations', icon: <FlaskConical size={15} />, category: 'Operations', action: { type: 'fill', value: 'Run an evaluation on ' } },
  { command: 'experiment', label: 'Experiment', description: 'Design or compare experiments', icon: <RefreshCw size={15} />, category: 'Operations', action: { type: 'fill', value: 'Compare experiments for ' } },
  { command: 'findings', label: 'Findings', description: 'Browse recent findings and alerts', icon: <AlertTriangle size={15} />, category: 'Operations', action: { type: 'navigate', value: '/findings' } },
  { command: 'deploy', label: 'Deploy', description: 'View deployment status and history', icon: <Cloud size={15} />, category: 'Operations', action: { type: 'navigate', value: '/operations' } },
  { command: 'context', label: 'Context', description: 'Manage current session context', icon: <Globe size={15} />, category: 'Session', action: { type: 'fill', value: 'Set context to ' } },
  { command: 'clear', label: 'Clear', description: 'Clear the conversation', icon: <RefreshCw size={15} />, category: 'Session', action: { type: 'fill', value: '/clear' } },
  { command: 'search', label: 'Search Web', description: 'Search the web for real-time information', icon: <Globe size={15} />, category: 'Knowledge', action: { type: 'fill', value: 'Search the web for ' } },
  { command: 'tools', label: 'Tools', description: 'Configure which tools are active', icon: <Wrench size={15} />, category: 'Session', action: { type: 'fill', value: '/tools' } },
  { command: 'settings', label: 'Settings', description: 'Open settings panel', icon: <Settings size={15} />, category: 'Session', action: { type: 'navigate', value: '/settings' } },
  { command: 'summary', label: 'Summarize', description: 'Summarize the current conversation', icon: <MessageSquare size={15} />, category: 'General', action: { type: 'fill', value: 'Summarize this conversation so far' } },
  { command: 'new', label: 'New Chat', description: 'Start a new conversation', icon: <Plus size={15} />, category: 'Session', action: { type: 'fill', value: '/new' } },
]

interface SlashCommandsProps {
  query: string
  onSelect: (command: SlashCommand) => void
  onClose: () => void
  sessions?: ChatSession[]
}

export function SlashCommands({ query, onSelect, onClose, sessions }: SlashCommandsProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [selectedIdx, setSelectedIdx] = useState(0)

  const exact = query.startsWith('/') ? query.slice(1).toLowerCase() : query.toLowerCase()

  const filtered = COMMANDS.filter(c => {
    if (!exact) return true
    return c.command.includes(exact) || c.label.toLowerCase().includes(exact) || c.description.toLowerCase().includes(exact)
  })

  // Reset selection when list changes
  useEffect(() => { setSelectedIdx(0) }, [query])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIdx(i => Math.min(i + 1, filtered.length - 1))
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIdx(i => Math.max(i - 1, 0))
      }
      if (e.key === 'Enter' && filtered[selectedIdx]) {
        e.preventDefault()
        onSelect(filtered[selectedIdx])
      }
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [filtered, selectedIdx, onSelect, onClose])

  if (filtered.length === 0) return null

  const grouped: Record<string, SlashCommand[]> = {}
  for (const cmd of filtered) {
    if (!grouped[cmd.category]) grouped[cmd.category] = []
    grouped[cmd.category].push(cmd)
  }

  return (
    <div
      ref={ref}
      className="absolute bottom-full left-0 right-0 mb-2 bg-elevated border border-border rounded-xl shadow-2xl overflow-hidden z-50"
      style={{ maxHeight: 'min(360px, 60vh)' }}
    >
      <div className="px-3.5 py-2 border-b border-border/50">
        <p className="text-caption font-medium text-muted-foreground/50">
          Commands {query ? `matching "${query}"` : ''}
        </p>
      </div>
      <div className="overflow-y-auto max-h-[300px] px-1 py-1">
        {Object.entries(grouped).map(([category, cmds]) => (
          <div key={category}>
            <div className="px-2.5 py-1.5 text-caption font-medium text-muted-foreground/40 uppercase tracking-wider">
              {category}
            </div>
            {cmds.map((cmd, i) => {
              const globalIdx = filtered.indexOf(cmd)
              return (
                <button
                  key={cmd.command}
                  onClick={() => onSelect(cmd)}
                  onMouseEnter={() => setSelectedIdx(globalIdx)}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left',
                    globalIdx === selectedIdx ? 'bg-primary/10' : 'hover:bg-hover',
                  )}
                >
                  <div className={cn(
                    'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border',
                    globalIdx === selectedIdx ? 'bg-primary/15 border-primary/25 text-primary' : 'bg-muted/20 border-border/50 text-muted-foreground',
                  )}>
                    {cmd.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-small font-semibold text-foreground">
                        /{cmd.command}
                      </span>
                      <span className="text-caption text-muted-foreground/50">
                        {cmd.label}
                      </span>
                    </div>
                    <p className="text-caption text-muted-foreground/50 truncate">{cmd.description}</p>
                  </div>
                  <span className="text-caption text-muted-foreground/30 shrink-0">
                    {cmd.action.type === 'navigate' ? '→' : '⏎'}
                  </span>
                </button>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
