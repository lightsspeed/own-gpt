import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import {
  AlertTriangle, Lightbulb, FileText, FlaskConical, BarChart3, Settings,
  ExternalLink, Copy, Check, ShieldAlert, Shield, Info, ArrowUpRight,
} from 'lucide-react'
import type { Artifact } from '@/features/chat/types'

const TYPE_CONFIG: Record<string, { icon: React.ReactNode; label: string; color: string; route?: string }> = {
  finding: {
    icon: <AlertTriangle size={16} />,
    label: 'Finding',
    color: 'text-danger border-l-danger',
    route: '/operations',
  },
  recommendation: {
    icon: <Lightbulb size={16} />,
    label: 'Recommendation',
    color: 'text-amber-400 border-l-amber-400',
    route: '/recommendations',
  },
  evidence: {
    icon: <FileText size={16} />,
    label: 'Evidence',
    color: 'text-sky-400 border-l-sky-400',
    route: '/findings',
  },
  experiment: {
    icon: <FlaskConical size={16} />,
    label: 'Experiment',
    color: 'text-purple-400 border-l-purple-400',
    route: '/experiments',
  },
  report: {
    icon: <BarChart3 size={16} />,
    label: 'Report',
    color: 'text-emerald-400 border-l-emerald-400',
    route: '/analytics',
  },
  configuration: {
    icon: <Settings size={16} />,
    label: 'Configuration',
    color: 'text-blue-400 border-l-blue-400',
    route: '/config/snapshots',
  },
}

const SEVERITY_STYLES: Record<string, string> = {
  critical: 'bg-danger/15 text-danger border-danger/20',
  high: 'bg-orange-500/15 text-orange-400 border-orange-500/20',
  medium: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  low: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
}

const STATUS_STYLES: Record<string, string> = {
  open: 'bg-blue-500/15 text-blue-400 border-blue-500/20',
  running: 'bg-purple-500/15 text-purple-400 border-purple-500/20',
  completed: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  failed: 'bg-danger/15 text-danger border-danger/20',
  approved: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  rejected: 'bg-muted/30 text-muted-foreground border-muted/30',
  active: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20',
  pending: 'bg-amber-500/15 text-amber-400 border-amber-500/20',
  draft: 'bg-muted/30 text-muted-foreground border-muted/30',
  archived: 'bg-muted/30 text-muted-foreground border-muted/30',
}

interface ArtifactCardProps {
  artifact: Artifact
  onAction?: (action: { label: string; href?: string }) => void
}

export const ArtifactCard = React.memo(function ArtifactCard({ artifact, onAction }: ArtifactCardProps) {
  const cfg = TYPE_CONFIG[artifact.type] || TYPE_CONFIG.finding
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(`${artifact.title}: ${artifact.description}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  const handleDeepLink = (href?: string) => {
    if (href) onAction?.({ label: 'Navigate', href })
  }

  return (
    <div
      className={cn(
        'group relative rounded-xl border border-border bg-elevated/50 hover:bg-elevated transition-all cursor-pointer overflow-hidden',
        artifact.severity && artifact.type === 'finding' ? 'border-l-[3px]' : '',
      )}
      style={
        artifact.severity && artifact.type === 'finding'
          ? { borderLeftColor: 'var(--border-color, currentColor)' }
          : undefined
      }
      onClick={() => handleDeepLink(cfg.route ? `${cfg.route}/${artifact.id}` : undefined)}
    >
      {/* Top section: icon + title + badges */}
      <div className="flex items-start gap-3 p-3.5">
        <div className={cn(
          'w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border',
          artifact.type === 'finding' ? 'bg-danger/10 border-danger/20 text-danger' :
          artifact.type === 'recommendation' ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' :
          artifact.type === 'evidence' ? 'bg-sky-500/10 border-sky-500/20 text-sky-400' :
          artifact.type === 'experiment' ? 'bg-purple-500/10 border-purple-500/20 text-purple-400' :
          artifact.type === 'report' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' :
          'bg-blue-500/10 border-blue-500/20 text-blue-400',
        )}>
          {cfg.icon}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-caption font-semibold text-muted-foreground uppercase tracking-wider">
              {cfg.label}
            </span>
            {artifact.severity && (
              <span className={cn(
                'text-[10px] font-medium px-1.5 py-0.5 rounded border',
                SEVERITY_STYLES[artifact.severity] || 'bg-muted/30 text-muted-foreground',
              )}>
                {artifact.severity}
              </span>
            )}
            {artifact.confidence != null && (
              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                {artifact.confidence}%
              </span>
            )}
            {artifact.status && (
              <span className={cn(
                'text-[10px] font-medium px-1.5 py-0.5 rounded border',
                STATUS_STYLES[artifact.status] || 'bg-muted/30 text-muted-foreground border-muted/30',
              )}>
                {artifact.status}
              </span>
            )}
          </div>

          <h4 className="text-small font-semibold text-foreground mt-1 leading-snug">{artifact.title}</h4>

          {artifact.description && (
            <p className="text-caption text-muted-foreground mt-0.5 line-clamp-2">{artifact.description}</p>
          )}

          {/* Metadata row */}
          <div className="flex items-center gap-3 mt-1.5 flex-wrap">
            {artifact.source && (
              <span className="text-caption text-muted-foreground/50">{artifact.source}</span>
            )}
            <span className="text-caption text-muted-foreground/40">{timeAgo(artifact.createdAt)}</span>
          </div>
        </div>

        <ArrowUpRight size={14} className="text-muted-foreground/30 group-hover:text-muted-foreground/60 transition-colors shrink-0 mt-1" />
      </div>

      {/* Actions bar */}
      <div className="flex items-center gap-1 px-3.5 pb-3 pt-0">
        <button
          onClick={e => { e.stopPropagation(); handleCopy() }}
          className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium text-muted-foreground/50 hover:text-muted-foreground hover:bg-hover transition-all"
        >
          {copied ? <Check size={11} className="text-success" /> : <Copy size={11} />}
          {copied ? 'Copied' : 'Copy'}
        </button>

        {artifact.actions.map((action, i) => (
          <button
            key={i}
            onClick={e => {
              e.stopPropagation()
              if (action.href) handleDeepLink(action.href)
            }}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium text-muted-foreground/50 hover:text-muted-foreground hover:bg-hover transition-all"
          >
            <ExternalLink size={11} />
            {action.label}
          </button>
        ))}

        {cfg.route && (
          <button
            onClick={e => {
              e.stopPropagation()
              handleDeepLink(`${cfg.route}/${artifact.id}`)
            }}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium text-primary/60 hover:text-primary hover:bg-primary/10 transition-all ml-auto"
          >
            Open {cfg.label}
            <ArrowUpRight size={11} />
          </button>
        )}
      </div>
    </div>
  )
})

function timeAgo(dateStr: string): string {
  const now = Date.now()
  const d = new Date(dateStr).getTime()
  const diff = now - d
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString()
}
