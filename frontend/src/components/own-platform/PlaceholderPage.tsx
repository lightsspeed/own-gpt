import { Construction } from 'lucide-react'

interface PlaceholderPageProps {
  title: string
  description?: string
}

export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div className="flex-1 flex items-center justify-center px-6">
      <div className="max-w-md text-center space-y-4">
        <div className="inline-flex items-center justify-center p-4 rounded-2xl bg-muted border border-border">
          <Construction size={32} className="text-primary" />
        </div>
        <h2 className="text-h3 text-foreground font-semibold">{title}</h2>
        {description && (
          <p className="text-body text-muted-foreground">{description}</p>
        )}
        <p className="text-small text-muted-foreground/60 italic">
          This module will be implemented in a future sprint.
        </p>
      </div>
    </div>
  )
}
