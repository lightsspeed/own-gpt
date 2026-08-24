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

  // 1. Match by exact canonical index (0-based chunk + 1 -> citation_index)
  let found = resources.find(r => r.citation_index === target)
  if (found) return found

  // 2. Match by direct token number (1-based index match or chunk_index)
  found = resources.find(r => r.citation_index === token.number || r.chunk_index === token.number)
  if (found) return found

  // 3. Match by array offset (0-based or 1-based)
  if (token.number >= 0 && token.number < resources.length) {
    return resources[token.number]
  }
  if (token.number - 1 >= 0 && token.number - 1 < resources.length) {
    return resources[token.number - 1]
  }

  // 4. Fallback to first resource available
  return resources[0]
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
  let title = resource.title || 'Knowledge Base'
  // Strip any internal chunk markers like "(Chunk 1)" or "[Chunk 1]" from display labels
  title = title.replace(/\s*[\(\[]Chunk\s*\d+[\)\]]/gi, '').trim()
  return title.replace(/\.[A-Za-z0-9]{1,6}$/, '') || 'Knowledge Base'
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

/**
 * Normalizes markdown content that contains raw URLs inside brackets, e.g.:
 * `[https://www.dota2.com/hero/io, https://dota2.fandom.com/wiki/Io]`
 *
 * Converts raw URL brackets into standard `[1]`, `[2]` citation tokens
 * and synthesizes corresponding `ResourceItem` entries with domain favicons.
 */
export function normalizeContentAndResources(
  content: string,
  existingResources?: ResourceItem[],
): { normalizedContent: string; resources: ResourceItem[] } {
  if (!content) return { normalizedContent: '', resources: existingResources || [] }

  const resources: ResourceItem[] = [...(existingResources || [])]

  // Ensure every resource has a valid 1-based citation_index
  resources.forEach((r, idx) => {
    if (!r.citation_index) {
      r.citation_index = idx + 1
    }
  })

  let nextIndex = resources.reduce((max, r) => Math.max(max, r.citation_index || 0), 0) + 1

  const urlMap = new Map<string, number>()
  for (const r of resources) {
    if (r.url && r.citation_index) {
      urlMap.set(r.url.trim().toLowerCase(), r.citation_index)
    }
  }

  let workingContent = content

  // 1. Extract and strip trailing Sources / References section from markdown body
  const SOURCES_SECTION_RE = /(?:\n|^)\s*(?:---|___|\*\*\*)*\s*(?:\*|_|#|\*\*)*\s*(?:Sources|References|Citations):?\s*(?:\*|_|#|\*\*)*\s*\n([\s\S]*)$/i
  const sourcesMatch = SOURCES_SECTION_RE.exec(workingContent)

  if (sourcesMatch) {
    const sourcesText = sourcesMatch[1]
    // Strip trailing sources block from text body so it doesn't leak as raw text at the bottom
    workingContent = workingContent.slice(0, sourcesMatch.index).trimEnd()

    // Parse list items `- [Title](URL)`
    const LINK_ITEM_RE = /[-*+]\s*\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/gi
    let linkMatch: RegExpExecArray | null
    while ((linkMatch = LINK_ITEM_RE.exec(sourcesText)) !== null) {
      const linkTitle = linkMatch[1].trim()
      const linkUrl = linkMatch[2].trim()
      const lowerUrl = linkUrl.toLowerCase()

      if (!urlMap.has(lowerUrl)) {
        const index = nextIndex++
        urlMap.set(lowerUrl, index)

        let domain = 'web'
        try { domain = new URL(linkUrl).hostname.replace(/^www\./, '') } catch {}

        resources.push({
          citation_index: index,
          type: 'web',
          title: linkTitle,
          url: linkUrl,
          snippet: `Source from ${domain}`,
        })
      }
    }
  }

  // 2. Matches `[https://...]` or `[http://..., http://...]`
  const BRACKETED_URLS_RE = /\[(https?:\/\/[^\]\)\s]+(?:,\s*https?:\/\/[^\]\)\s]+)*)\]/gi

  workingContent = workingContent.replace(BRACKETED_URLS_RE, (fullMatch, rawUrlsGroup) => {
    const rawUrls = rawUrlsGroup.split(/,\s*/).map((u: string) => u.trim()).filter(Boolean)
    const tokenIndexes: number[] = []

    for (const urlStr of rawUrls) {
      const lowerUrl = urlStr.toLowerCase()
      if (urlMap.has(lowerUrl)) {
        tokenIndexes.push(urlMap.get(lowerUrl)!)
      } else {
        const index = nextIndex++
        urlMap.set(lowerUrl, index)

        let domain = 'web'
        try { domain = new URL(urlStr).hostname.replace(/^www\./, '') } catch {}

        resources.push({
          citation_index: index,
          type: 'web',
          title: domain,
          url: urlStr,
          snippet: `Source from ${domain}`,
        })
        tokenIndexes.push(index)
      }
    }

    return ' ' + tokenIndexes.map(idx => `[${idx}]`).join(' ') + ' '
  })

  // 3. Replace named bracket citations like `[Mayo Clinic]`, `[Cleveland Clinic]` with standard `[N]` tokens
  if (resources.length > 0) {
    const NAMED_BRACKET_RE = /\[(?!Chunk\b|\d+\])([^\]]+)\](?!\()/gi
    workingContent = workingContent.replace(NAMED_BRACKET_RE, (fullMatch, rawName) => {
      const cleanName = rawName.trim().toLowerCase()
      if (!cleanName || cleanName.startsWith('http')) return fullMatch

      // Find matching resource by title or domain
      const matchRes = resources.find(r => {
        const titleLower = (r.title || '').toLowerCase()
        const urlLower = (r.url || '').toLowerCase()
        return titleLower.includes(cleanName) || cleanName.includes(titleLower) || urlLower.includes(cleanName)
      })

      if (matchRes && matchRes.citation_index) {
        return ` [${matchRes.citation_index}]`
      }

      // If no exact resource match, synthesize a web resource for the named site
      const index = nextIndex++
      resources.push({
        citation_index: index,
        type: 'web',
        title: rawName.trim(),
        snippet: `Source: ${rawName.trim()}`,
      })
      return ` [${index}]`
    })
  }

  // 4. Synthesize fallback resource entries for any [Chunk N] markers if unmapped
  const UNMAPPED_CHUNK_RE = /\[Chunk\s+(\d+)\]/gi
  let chunkMatch: RegExpExecArray | null
  while ((chunkMatch = UNMAPPED_CHUNK_RE.exec(workingContent)) !== null) {
    const chunkNum = parseInt(chunkMatch[1], 10)
    const targetIdx = chunkNum + 1
    if (!resources.some(r => r.citation_index === targetIdx || r.citation_index === chunkNum)) {
      resources.push({
        citation_index: targetIdx,
        type: 'kb',
        title: 'Knowledge Base Source',
        snippet: 'Knowledge Base Document Reference',
      })
    }
  }

  const deduplicatedContent = deduplicateInlineCitations(workingContent)

  return { normalizedContent: deduplicatedContent, resources }
}

/**
 * Paragraph-level citation deduplication:
 * Within a single paragraph, if the same citation index appears multiple times
 * across consecutive sentences, keeps only the final citation marker to prevent visual clutter.
 */
export function deduplicateInlineCitations(content: string): string {
  if (!content) return ''
  const paragraphs = content.split(/\n{2,}/)

  const deduplicatedParagraphs = paragraphs.map(para => {
    const CITE_REGEX = /\[(Chunk\s+\d+|\d+)\]/g
    const matches = Array.from(para.matchAll(CITE_REGEX))

    if (matches.length <= 1) return para

    const lastOccurrence = new Map<string, number>()
    for (const match of matches) {
      if (match.index !== undefined) {
        lastOccurrence.set(match[0], match.index)
      }
    }

    let result = para
    let offset = 0
    for (const match of matches) {
      const token = match[0]
      const pos = match.index!
      const lastPos = lastOccurrence.get(token)!
      if (pos < lastPos) {
        const currentPos = pos + offset
        result = result.slice(0, currentPos) + result.slice(currentPos + token.length)
        offset -= token.length
      }
    }

    return result.replace(/[ \t]{2,}/g, ' ')
  })

  return deduplicatedParagraphs.join('\n\n')
}