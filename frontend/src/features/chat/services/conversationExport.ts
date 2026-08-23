import type { MessageData } from '@/features/chat/types'

export interface ExportResource {
  type: string
  title: string
  url?: string
  /** 1-based citation_index — matches the canonical numbering used by the UI and Sources section. */
  citation_index?: number
}

export interface ExportMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  status?: string
  timestamp?: Date
  resources?: ExportResource[]
}

const EXPORTABLE_ROLES: ReadonlySet<string> = new Set(['user', 'assistant'])

export function exportFilename(date: Date = new Date()): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  // Filename-safe: letters, digits, dashes, underscores only.
  return `OwnGPT-Conversation-${y}-${m}-${d}`.replace(/[^A-Za-z0-9-_]/g, '-')
}

// Preferred: OwnGPT_<conversation-title>_<YYYY-MM-DD>.pdf
// Fallback:  OwnGPT_Conversation_<YYYY-MM-DD_HH-mm>.pdf
export function exportDocumentTitle(title: string | undefined, date: Date = new Date()): string {
  const y = date.getFullYear()
  const mo = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const h = String(date.getHours()).padStart(2, '0')
  const mi = String(date.getMinutes()).padStart(2, '0')
  const safeTitle = (title || '').trim().replace(/[^A-Za-z0-9 _-]/g, '').trim()
  if (safeTitle) {
    return `OwnGPT_${safeTitle.replace(/\s+/g, '_')}_${y}-${mo}-${d}`
  }
  return `OwnGPT_Conversation_${y}-${mo}-${d}_${h}-${mi}`
}

// Export-only, presentation-level markdown normalization. Never touches the
// stored conversation: it only repairs render-only tokens so the browser can
// produce proper document elements instead of leaking raw markdown syntax.
//
//   1. ATX headings missing the required space: `###3. Foo` -> `### 3. Foo`
//   2. Thematic break glued to a heading:      `---### 5. Bar` -> `---\n### 5. Bar`
//   3. Inline citation markers `[Chunk N]` -> `[N+1]` (PDF never leaks the raw
//      `[Chunk N]` token; the numbered Sources section carries the canonical
//      1-based citation_index).
const CITATION_MARKER_RE = /\[Chunk\s+(\d+)\]/gi

export function normalizeMarkdownForExport(content: string): string {
  if (!content) return content
  const lines = content.split('\n')
  const out: string[] = []
  let inFence = false
  for (const line of lines) {
    // Code fences keep their literal content byte-for-byte.
    const fenceMatch = /^\s*(```|~~~)/.exec(line)
    if (fenceMatch) inFence = !inFence
    if (inFence) {
      out.push(line)
      continue
    }
    const repaired = /^---(?=#{1,6})/.test(line)
      ? `---\n${fixHeadingSeparator(line.slice(3))}`
      : fixHeadingSeparator(line)
    out.push(repaired.replace(CITATION_MARKER_RE, (_, n) => `[${Number(n) + 1}]`))
  }
  return out.join('\n')
}

function fixHeadingSeparator(line: string): string {
  const m = /^(#{1,6})(?=[^#\s])/.exec(line)
  if (m) return `${m[1]} ${line.slice(m[1].length)}`
  return line
}

function toExportResource(resource: { type?: string; title?: string; url?: string; citation_index?: number | null }): ExportResource | null {
  if (!resource.title) return null
  return {
    type: resource.type || 'file',
    title: resource.title,
    url: resource.url,
    ...(resource.citation_index !== undefined && resource.citation_index !== null
      ? { citation_index: resource.citation_index }
      : {}),
  }
}

export function selectExportMessages(messages: MessageData[]): ExportMessage[] {
  const out: ExportMessage[] = []
  for (const m of messages) {
    if (!EXPORTABLE_ROLES.has(m.role)) continue
    const resources: ExportResource[] | undefined = m.resources
      ?.map(toExportResource)
      .filter((r): r is ExportResource => r !== null)
    out.push({
      id: m.id,
      role: m.role as 'user' | 'assistant',
      content: m.content ?? '',
      status: m.status,
      timestamp: m.timestamp,
      resources: resources && resources.length > 0 ? resources : undefined,
    })
  }
  return out
}

export function hasExportableContent(messages: MessageData[]): boolean {
  return selectExportMessages(messages).length > 0
}

export function exportConversationAsMarkdown(messages: MessageData[], title?: string) {
  const exportMsgs = selectExportMessages(messages)
  if (exportMsgs.length === 0) return

  const docTitle = title || 'OwnGPT Conversation'
  const dateStr = new Date().toLocaleDateString()
  let mdContent = `# ${docTitle}\n*Exported on ${dateStr}*\n\n---\n\n`

  for (const msg of exportMsgs) {
    const roleName = msg.role === 'user' ? '👤 **User**' : '🤖 **OwnGPT**'
    mdContent += `### ${roleName}\n\n${normalizeMarkdownForExport(msg.content)}\n\n`

    if (msg.resources && msg.resources.length > 0) {
      mdContent += `**Sources:**\n`
      for (const res of msg.resources) {
        mdContent += `- [${res.citation_index || '1'}] ${res.title}${res.url ? ` (${res.url})` : ''}\n`
      }
      mdContent += `\n`
    }
    mdContent += `---\n\n`
  }

  const filename = `${exportDocumentTitle(docTitle)}.md`
  const blob = new Blob([mdContent], { type: 'text/markdown;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function exportConversationAsTxt(messages: MessageData[], title?: string) {
  const exportMsgs = selectExportMessages(messages)
  if (exportMsgs.length === 0) return

  const docTitle = title || 'OwnGPT Conversation'
  const dateStr = new Date().toLocaleDateString()
  let txtContent = `${docTitle.toUpperCase()}\nExported on ${dateStr}\n${'='.repeat(40)}\n\n`

  for (const msg of exportMsgs) {
    const roleName = msg.role === 'user' ? 'USER' : 'OWNGPT'
    txtContent += `[${roleName}]\n${msg.content}\n\n`

    if (msg.resources && msg.resources.length > 0) {
      txtContent += `Sources:\n`
      for (const res of msg.resources) {
        txtContent += `- [${res.citation_index || '1'}] ${res.title}${res.url ? ` (${res.url})` : ''}\n`
      }
      txtContent += `\n`
    }
    txtContent += `${'-'.repeat(30)}\n\n`
  }

  const filename = `${exportDocumentTitle(docTitle)}.txt`
  const blob = new Blob([txtContent], { type: 'text/plain;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}