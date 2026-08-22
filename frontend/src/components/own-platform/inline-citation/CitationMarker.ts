import type { ResourceItem } from '@/features/chat/types'

export type CitationKind = 'chunk' | 'bare'

export interface CitationToken {
  kind: CitationKind
  number: number
}

export interface CiteSource {
  token: CitationToken
  resource: ResourceItem
}

export interface CiteGroup {
  /** Resolved sources cited by this marker group, in marker order. */
  sources: CiteSource[]
}

export type CitationSegment =
  | { type: 'text'; text: string }
  | { type: 'citation'; token: CitationToken }

// Matches `[Chunk 3]` (0-based KB markers) or `[1]` (bare web-tool labels).
// The bare alternative excludes markdown links like `[1](https://...)`.
const CITATION_TOKEN_RE = /\[Chunk\s+(\d+)\]|\[(\d+)\](?!\()/gi

// ---------------------------------------------------------------------------
// Tokenization
// ---------------------------------------------------------------------------

export function splitCitationMarkers(text: string): CitationSegment[] {
  const segments: CitationSegment[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null
  CITATION_TOKEN_RE.lastIndex = 0
  while ((match = CITATION_TOKEN_RE.exec(text)) !== null) {
    const before = text.slice(lastIndex, match.index)
    if (before) segments.push({ type: 'text', text: before })
    const chunkNumber = match[1]
    const bareNumber = match[2]
    if (chunkNumber !== undefined) {
      segments.push({
        type: 'citation',
        token: { kind: 'chunk', number: parseInt(chunkNumber, 10) },
      })
    } else if (bareNumber !== undefined) {
      segments.push({
        type: 'citation',
        token: { kind: 'bare', number: parseInt(bareNumber, 10) },
      })
    }
    lastIndex = match.index + match[0].length
  }
  const tail = text.slice(lastIndex)
  if (tail) segments.push({ type: 'text', text: tail })
  return segments
}

// ---------------------------------------------------------------------------
// Canonical numbering — the single authoritative citation index.
//
//   [Chunk N]  →  N + 1        (0-based KB markers → 1-based canonical index)
//   [N]        →  N            (bare web labels are already 1-based)
//
// This is the ONLY place marker numbers are converted; every layer (pill,
// hover card, resource list, PDF sources) consumes the canonical index.
// ---------------------------------------------------------------------------

export function citationIndex(token: CitationToken): number {
  return token.kind === 'chunk' ? token.number + 1 : token.number
}

export function resolveCitationResource(
  resources: ResourceItem[] | undefined,
  token: CitationToken,
): ResourceItem | undefined {
  if (!resources || resources.length === 0) return undefined
  const target = citationIndex(token)
  return resources.find(r => r.citation_index === target)
}

// ---------------------------------------------------------------------------
// Grouping — consecutive markers separated only by whitespace form ONE pill.
//   "claim. [Chunk 1] [Chunk 2]" → one pill whose popover lists both sources.
// ---------------------------------------------------------------------------

export function buildCiteGroups(text: string, resources: ResourceItem[] | undefined): CiteGroup[] {
  const groups: CiteGroup[] = []
  let pending: CitationToken[] = []
  let hasPending = false

  const flush = () => {
    if (!hasPending) return
    const sources: CiteSource[] = []
    for (const token of pending) {
      const resource = resolveCitationResource(resources, token)
      if (resource) sources.push({ token, resource })
    }
    if (sources.length > 0) groups.push({ sources })
    pending = []
    hasPending = false
  }

  for (const segment of splitCitationMarkers(text)) {
    if (segment.type === 'citation') {
      pending.push(segment.token)
      hasPending = true
      continue
    }
    // Whitespace-only text between citations keeps the group open.
    if (hasPending && /^\s*$/.test(segment.text)) continue
    flush()
  }
  flush()
  return groups
}

// ---------------------------------------------------------------------------
// Presentation helpers
// ---------------------------------------------------------------------------

/** Short display label: URL hostname for web sources, title otherwise. */
export function sourceDomain(resource: ResourceItem): string {
  if (resource.url) {
    try {
      return new URL(resource.url).hostname.replace(/^www\./, '')
    } catch {
      /* fall through to title */
    }
  }
  return (resource.title || 'source').replace(/\.[A-Za-z0-9]{1,6}$/, '')
}

/** Pill content: `kubernetes.io`, `kubernetes.io +2` (two additional sources). */
export function pillowLabel(group: CiteGroup): string {
  const primary = group.sources[0]
  if (!primary) return 'source'
  const label = sourceDomain(primary.resource)
  const extra = group.sources.length - 1
  return extra > 0 ? `${label} +${extra}` : label
}

/** Only http(s) links are interactive; everything else renders as plain text. */
export function safeSourceUrl(url: string | undefined): string | undefined {
  if (!url) return undefined
  try {
    const parsed = new URL(url)
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') return parsed.href
  } catch {
    /* not a URL */
  }
  return undefined
}