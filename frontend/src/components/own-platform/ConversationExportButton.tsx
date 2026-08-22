import { FileDown, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface ConversationExportButtonProps {
  hasContent: boolean
  loading?: boolean
  onExport: () => void
}

export function ConversationExportButton({ hasContent, loading, onExport }: ConversationExportButtonProps) {
  if (!hasContent) return null
  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-7 w-7"
      onClick={onExport}
      disabled={loading}
      title={loading ? 'Preparing PDF…' : 'Download PDF'}
      aria-label="Download PDF"
    >
      {loading ? <Loader2 size={14} className="animate-spin" /> : <FileDown size={14} />}
    </Button>
  )
}