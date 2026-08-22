import { describe, it, expect } from 'vitest'
import {
  exportFilename,
  exportDocumentTitle,
  normalizeMarkdownForExport,
  selectExportMessages,
  hasExportableContent,
} from '../conversationExport'
import type { MessageData } from '@/features/chat/types'

function message(over: Partial<MessageData> & { role: MessageData['role']; content: string }): MessageData {
  return { id: over.id || `m-${Math.random()}`, ...over }
}

const baseMsgs: MessageData[] = [
  message({ id: 'u1', role: 'user', content: 'What is RAG?' }),
  message({
    id: 'a1',
    role: 'assistant',
    content: 'RAG is **retrieval augmented generation**.',
    status: 'completed',
    resources: [
      { type: 'file', title: 'source.pdf', url: 'https://example.test/source.pdf', document_id: 'doc-1', chunk_index: 3, confidence_label: 'high' },
    ],
    evidence: [{ id: 'e1', title: 'internal evidence', source_type: 'knowledge', url: null, chunk: 'secret chunk', confidence_label: 'high', retrieval_method: 'hybrid' } as any],
    artifacts: [{ id: 'art-1', type: 'finding', title: 'internal artifact', description: 'x', actions: [] } as any],
    usedTools: ['web_search'],
    recordId: 'rec-1',
    answerMode: 'grounded',
    feedback: 'liked',
    answerModeMetadata: { chunk_count: 5, doc_count: 1, confidence: 0.9, retrieval_method: 'hybrid' },
  }),
  message({ id: 't1', role: 'tool_event', content: '', tool: { name: 'web_search', status: 'done' } }),
  message({ id: 'u2', role: 'user', content: 'Give an example.' }),
  message({ id: 'a2', role: 'assistant', content: '```python\nprint("hi")\n```', status: 'failed' }),
]

describe('selectExportMessages', () => {
  it('includes every user and assistant message in order', () => {
    const out = selectExportMessages(baseMsgs)
    expect(out.map(m => m.id)).toEqual(['u1', 'a1', 'u2', 'a2'])
  })

  it('preserves user and assistant roles', () => {
    const out = selectExportMessages(baseMsgs)
    expect(out.map(m => m.role)).toEqual(['user', 'assistant', 'user', 'assistant'])
  })

  it('drops tool_event messages and internal fields', () => {
    const out = selectExportMessages(baseMsgs)
    const a1 = out.find(m => m.id === 'a1')!
    expect(out.some(m => m.id === 't1')).toBe(false)
    expect(a1).not.toHaveProperty('evidence')
    expect(a1).not.toHaveProperty('artifacts')
    expect(a1).not.toHaveProperty('usedTools')
    expect(a1).not.toHaveProperty('recordId')
    expect(a1).not.toHaveProperty('answerMode')
    expect(a1).not.toHaveProperty('answerModeMetadata')
    expect(a1).not.toHaveProperty('feedback')
  })

  it('exports only displayable resource metadata (type/title/url)', () => {
    const a1 = selectExportMessages(baseMsgs).find(m => m.id === 'a1')!
    expect(a1.resources).toEqual([
      { type: 'file', title: 'source.pdf', url: 'https://example.test/source.pdf' },
    ])
    expect(a1.resources![0]).not.toHaveProperty('document_id')
    expect(a1.resources![0]).not.toHaveProperty('chunk_index')
    expect(a1.resources![0]).not.toHaveProperty('confidence_label')
  })

  it('preserves citation_index so the Sources section can be numbered', () => {
    const withCite = message({
      id: 'a-cite',
      role: 'assistant',
      content: 'Answer [Chunk 2]',
      resources: [
        { type: 'web', title: 'Web Source', url: 'https://web.test', citation_index: 3 },
        { type: 'file', title: 'KB Doc', citation_index: 1 },
      ],
    })
    const out = selectExportMessages([withCite]).find(m => m.id === 'a-cite')!
    expect(out.resources).toEqual([
      { type: 'web', title: 'Web Source', url: 'https://web.test', citation_index: 3 },
      { type: 'file', title: 'KB Doc', citation_index: 1 },
    ])
  })

  it('keeps status for failed messages', () => {
    const a2 = selectExportMessages(baseMsgs).find(m => m.id === 'a2')!
    expect(a2.status).toBe('failed')
    expect(a2.content).toContain('```python')
  })

  it('does not truncate long conversations (500 messages)', () => {
    const many: MessageData[] = Array.from({ length: 250 }, (_, i) => [
      message({ id: `u-${i}`, role: 'user', content: `question ${i}` }),
      message({ id: `a-${i}`, role: 'assistant', content: `answer ${i}` }),
    ]).flat()
    const out = selectExportMessages(many)
    expect(out).toHaveLength(500)
    expect(out[0].content).toBe('question 0')
    expect(out[499].content).toBe('answer 249')
    expect(new Set(out.map(m => m.id)).size).toBe(500)
  })

  it('handles empty conversation safely', () => {
    expect(selectExportMessages([])).toEqual([])
    expect(hasExportableContent([])).toBe(false)
  })
})

describe('exportFilename', () => {
  it('uses the provided date deterministically', () => {
    expect(exportFilename(new Date(2026, 7, 20))).toBe('OwnGPT-Conversation-2026-08-20')
  })

  it('zero-pads month and day', () => {
    expect(exportFilename(new Date(2026, 0, 5))).toBe('OwnGPT-Conversation-2026-01-05')
  })

  it('is filename-safe on every platform', () => {
    const name = exportFilename(new Date(2026, 11, 31))
    expect(/^[A-Za-z0-9-_]+$/.test(name)).toBe(true)
  })
})

describe('exportDocumentTitle', () => {
  it('uses the preferred OwnGPT_<title>_<date> form with a title', () => {
    expect(exportDocumentTitle('Lifecycle Testing', new Date(2026, 7, 20))).toBe(
      'OwnGPT_Lifecycle_Testing_2026-08-20',
    )
  })

  it('strips filesystem-illegal characters and collapses spaces', () => {
    expect(exportDocumentTitle('Book: 10 Books 🚀 / Part 1', new Date(2026, 7, 20))).toBe(
      'OwnGPT_Book_10_Books_Part_1_2026-08-20',
    )
  })

  it('falls back to OwnGPT_Conversation_<date>_<time> without a title', () => {
    expect(exportDocumentTitle('', new Date(2026, 7, 20, 23, 5))).toBe(
      'OwnGPT_Conversation_2026-08-20_23-05',
    )
    expect(exportDocumentTitle(undefined, new Date(2026, 7, 20, 9, 0))).toBe(
      'OwnGPT_Conversation_2026-08-20_09-00',
    )
  })
})

describe('normalizeMarkdownForExport', () => {
  it('adds the missing space to a heading without one', () => {
    expect(normalizeMarkdownForExport('###3. Platform Engineering & Internal Developer Platforms'))
      .toBe('### 3. Platform Engineering & Internal Developer Platforms')
  })

  it('splits a thematic break glued to a heading', () => {
    expect(normalizeMarkdownForExport('---### 5. Advanced GitOps & Ephemeral Environments'))
      .toBe('---\n### 5. Advanced GitOps & Ephemeral Environments')
  })

  it('fixes top-level headings too', () => {
    expect(normalizeMarkdownForExport('#Title without space')).toBe('# Title without space')
    expect(normalizeMarkdownForExport('##Second level')).toBe('## Second level')
  })

  it('leaves well-formed markdown untouched', () => {
    const ok = '### 3. Heading\n\n---\n\nParagraph with **bold**.'
    expect(normalizeMarkdownForExport(ok)).toBe(ok)
  })

  it('never touches inline content or mid-line tokens', () => {
    expect(normalizeMarkdownForExport('It takes ~3 hours with 2# tags and 100% effort.')).toBe(
      'It takes ~3 hours with 2# tags and 100% effort.',
    )
  })

  it('handles empty input', () => {
    expect(normalizeMarkdownForExport('')).toBe('')
  })

  it('converts [Chunk N] citation markers to canonical [N+1]', () => {
    expect(normalizeMarkdownForExport('Ground truth claim [Chunk 0] and more [Chunk 3].'))
      .toBe('Ground truth claim [1] and more [4].')
    expect(normalizeMarkdownForExport('Lowercase [chunk 1] marker')).toBe('Lowercase [2] marker')
  })

  it('never leaks [Chunk N] inside fenced code blocks', () => {
    const md = 'Claim [Chunk 0].\n\n```js\nconst cite = "[Chunk 7]";\n```\n\nAfter [Chunk 1].'
    expect(normalizeMarkdownForExport(md)).toBe('Claim [1].\n\n```js\nconst cite = "[Chunk 7]";\n```\n\nAfter [2].')
  })

  it('leaves bare [N] markers and markdown links untouched', () => {
    expect(normalizeMarkdownForExport('Web claim [1] and link [1](https://x.test)')).toBe(
      'Web claim [1] and link [1](https://x.test)',
    )
  })
})