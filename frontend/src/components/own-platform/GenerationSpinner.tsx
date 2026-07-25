import type { PipelineStage } from '@/features/chat/types'
import { TextShimmer } from '@/components/ui/text-shimmer'
import Spinner4 from '@/components/spinner4'

interface GenerationSpinnerProps {
  stages: PipelineStage[]
}

const STAGE_LABELS: Record<string, string> = {
  thinking: 'Analyzing your request...',
  routing: 'Routing to best model...',
  retrieving: 'Searching knowledge base...',
  reranking: 'Ranking results...',
  generating: 'Generating response...',
}

export function GenerationSpinner({ stages }: GenerationSpinnerProps) {
  const activeStage = stages.find(s => s.status === 'active')
  const label = activeStage ? STAGE_LABELS[activeStage.id] || 'Processing...' : 'Processing...'

  return (
    <div className="flex items-center gap-3 animate-fade-in">
      <Spinner4 />
      <TextShimmer className="text-small" duration={2}>
        {label}
      </TextShimmer>
    </div>
  )
}