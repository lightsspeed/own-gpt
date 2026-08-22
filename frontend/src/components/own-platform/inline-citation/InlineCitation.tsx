import React from 'react'
import { CitationPill } from './CitationPill'
import { CitationPopover } from './CitationPopover'
import {
  splitCitationMarkers,
  pillowLabel,
  type CiteGroup,
  type CitationToken,
} from './CitationMarker'

export interface CitationOpen {
  key: string
  /** Carousel position inside the open group's sources. */
  index: number
}

/** Stable identity for a cite group across render passes. */
export function groupKey(group: CiteGroup): string {
  return group.sources.map(s => `${s.token.kind}:${s.token.number}`).join('|')
}

interface InlineCitationTextProps {
  text: string
  groups: CiteGroup[]
  open: CitationOpen | null
  onActivateKey: (key: string) => void
  onHoverEnterKey: (key: string) => void
  onHoverLeaveKey: (key: string) => void
  onNavigate: (delta: number) => void
  onClose: () => void
  variant: 'card' | 'sheet'
}

function matchesGroup(token: CitationToken, group: CiteGroup): boolean {
  return group.sources.some(s => s.token.kind === token.kind && s.token.number === token.number)
}

export function InlineCitationText({
  text,
  groups,
  open,
  onActivateKey,
  onHoverEnterKey,
  onHoverLeaveKey,
  onNavigate,
  onClose,
  variant,
}: InlineCitationTextProps) {
  if (groups.length === 0) return <>{text}</>

  const segments = splitCitationMarkers(text)
  const out: React.ReactNode[] = []
  let groupCursor = 0
  let keyCounter = 0

  let i = 0
  while (i < segments.length) {
    const segment = segments[i]
    if (segment.type === 'text') {
      out.push(<React.Fragment key={`t-${keyCounter++}`}>{segment.text}</React.Fragment>)
      i++
      continue
    }

    const group = groups[groupCursor]
    if (!group || !matchesGroup(segment.token, group)) {
      // Marker without a resolved source — never leak internal tokens.
      i++
      continue
    }

    const key = groupKey(group)
    const isActive = open?.key === key
    const activeIndex = isActive ? Math.min(open!.index, group.sources.length - 1) : 0

    out.push(
      <span key={`c-${keyCounter++}`} className="relative inline-block align-baseline">
        <CitationPill
          label={pillowLabel(group)}
          active={isActive}
          onActivate={() => onActivateKey(key)}
          onHoverEnter={() => onHoverEnterKey(key)}
          onHoverLeave={() => onHoverLeaveKey(key)}
        />
        {isActive && (
          <CitationPopover
            sources={group.sources}
            activeIndex={activeIndex}
            onNavigate={onNavigate}
            onClose={onClose}
            variant={variant}
          />
        )}
      </span>,
    )
    i++
    groupCursor++

    // Consume the remaining markers of this group (whitespace-separated).
    while (i < segments.length) {
      const s = segments[i]
      if (s.type === 'citation' && matchesGroup(s.token, group)) {
        i++
        continue
      }
      const next = segments[i + 1]
      if (s.type === 'text' && next && next.type === 'citation' && matchesGroup(next.token, group) && /^\s*$/.test(s.text)) {
        i++
        continue
      }
      break
    }
  }

  return <>{out}</>
}