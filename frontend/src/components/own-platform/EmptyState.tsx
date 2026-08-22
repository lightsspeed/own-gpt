import { Sparkles, BarChart3, Search, FlaskConical } from 'lucide-react'

const SUGGESTIONS = [
  {
    id: '1',
    icon: <BarChart3 size={24} />,
    title: 'How is the platform doing?',
    description: 'Analyze real-time health metrics and uptime.',
    action: 'how is the platform doing?',
  },
  {
    id: '2',
    icon: <Search size={24} />,
    title: 'Show me recent findings',
    description: 'Review recent anomalies and log exceptions.',
    action: 'show me recent findings',
  },
  {
    id: '3',
    icon: <FlaskConical size={24} />,
    title: 'What experiments are running?',
    description: 'Check active A/B tests and rollout status.',
    action: 'what experiments are running?',
  },
]

interface EmptyStateProps {
  onSuggestionClick?: (text: string) => void
}

export function EmptyState({ onSuggestionClick }: EmptyStateProps) {
  return (
    <div className="w-full max-w-[800px] mx-auto text-center space-y-10 px-6">
      {/* Welcome Branding */}
      <div className="space-y-5 animate-fade-in">
        <div className="inline-flex items-center justify-center p-4 rounded-2xl bg-elevated border border-border">
          <Sparkles size={36} className="text-primary" />
        </div>
        <h1 className="text-display text-foreground tracking-tight">
          Welcome to OwnGPT
        </h1>
        <p className="text-body text-muted-foreground leading-relaxed max-w-2xl mx-auto">
          I'm your AI engineering assistant. I can help you monitor your platform,
          investigate findings, run experiments, and manage configurations.
        </p>
      </div>

      {/* Suggestion Chips */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-fade-in-up">
        {SUGGESTIONS.map(s => (
          <button
            key={s.id}
            onClick={() => onSuggestionClick?.(s.action)}
            className="group p-5 rounded-xl border border-border bg-surface hover:bg-elevated hover:border-primary transition-all text-left flex flex-col gap-3"
          >
            <span className="text-primary group-hover:scale-110 transition-transform">
              {s.icon}
            </span>
            <span className="text-body text-foreground font-medium">
              {s.title}
            </span>
            <span className="text-caption text-muted-foreground">
              {s.description}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
