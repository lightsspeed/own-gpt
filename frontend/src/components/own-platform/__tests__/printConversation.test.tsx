/** @vitest-environment happy-dom */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createRoot, type Root } from 'react-dom/client'
import { act } from 'react'
import { PrintConversation } from '../PrintConversation'
import type { ExportMessage } from '@/features/chat/services/conversationExport'

function messages(): ExportMessage[] {
  return [
    { id: 'u1', role: 'user', content: 'Question one', timestamp: new Date(2026, 7, 20, 10, 0) },
    {
      id: 'a1',
      role: 'assistant',
      content: 'Answer with a **bold** statement and `code`.\n\n```js\nconst x = 1\n```',
      status: 'completed',
      resources: [{ type: 'web', title: 'Example Source', url: 'https://example.test/doc' }],
    },
    { id: 'u2', role: 'user', content: 'Follow-up', timestamp: new Date(2026, 7, 20, 10, 5) },
    { id: 'a2', role: 'assistant', content: 'Failed answer', status: 'failed' },
  ]
}

let container: HTMLDivElement
let root: Root
let printSpy: ReturnType<typeof vi.fn>

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
  printSpy = vi.fn()
  vi.stubGlobal('print', printSpy)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
  document.title = 'Test Page'
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

function render(props: Partial<Parameters<typeof PrintConversation>[0]>) {
  act(() => {
    root.render(
      <PrintConversation
        title="My Conversation"
        messages={messages()}
        exporting={false}
        onExportComplete={() => {}}
        {...props}
      />,
    )
  })
}

describe('PrintConversation', () => {
  it('is hidden until exporting is triggered', () => {
    render({ exporting: false })
    const el = container.querySelector('#print-conversation')!
    expect(el).not.toBeNull()
  })

  it('invokes window.print when exporting and sets a sensible document title', () => {
    vi.useFakeTimers()
    render({ exporting: true })
    act(() => {
      vi.advanceTimersByTime(60)
    })
    expect(printSpy).toHaveBeenCalledTimes(1)
    expect(document.title).toMatch(/^OwnGPT_My_Conversation_\d{4}-\d{2}-\d{2}$/)
  })

  it('renders all messages with user/assistant labels in order', () => {
    render({ exporting: true })
    const html = container.innerHTML
    const roles = Array.from(container.querySelectorAll('.pc-role')).map(el => el.textContent)
    expect(roles[0]).toContain('You')
    expect(roles[1]).toContain('OwnGPT')
    expect(roles[2]).toContain('You')
    expect(roles[3]).toContain('OwnGPT')
    expect(html).toContain('Question one')
    expect(html).toContain('Answer with a')
    expect(html).toContain('Follow-up')
    expect(html).toContain('Failed answer')
  })

  it('renders resources and failure status for the assistant message', () => {
    render({ exporting: true })
    expect(container.textContent).toContain('Sources:')
    expect(container.textContent).toContain('Example Source')
    expect(container.textContent).toContain('Generation failed')
  })

  it('numbers sources by citation_index and never leaks raw [Chunk N] markers', () => {
    const md: ExportMessage[] = [{
      id: 'a-cite',
      role: 'assistant',
      content: 'Grounded claim [Chunk 0] and another claim [Chunk 2].',
      resources: [
        { type: 'file', title: 'First Doc', citation_index: 1 },
        { type: 'web', title: 'Second Doc', url: 'https://web.test/doc', citation_index: 3 },
      ],
    }]
    act(() => {
      root.render(
        <PrintConversation title="Cite" messages={md} exporting={false} onExportComplete={() => {}} />,
      )
    })
    const text = container.textContent || ''
    expect(text).toContain('Grounded claim [1] and another claim [3]')
    expect(text).not.toContain('Chunk')
    const sources = container.querySelectorAll('.pc-sources li')
    expect(sources.length).toBe(2)
    expect(sources[0].textContent).toContain('[1]')
    expect(sources[0].textContent).toContain('First Doc')
    expect(sources[1].textContent).toContain('[3]')
    expect(sources[1].textContent).toContain('Second Doc')
  })

  it('restores the original document title after the print dialog closes', () => {
    render({ exporting: true })
    expect(document.title).toMatch(/^OwnGPT_.*_\d{4}-\d{2}-\d{2}$/)
    act(() => {
      window.dispatchEvent(new Event('afterprint'))
    })
    expect(document.title).toBe('Test Page')
  })

  it('renders an empty conversation safely', () => {
    act(() => {
      root.render(
        <PrintConversation title="Empty" messages={[]} exporting={true} onExportComplete={() => {}} />,
      )
    })
    expect(container.textContent).toContain('Empty')
    expect(container.textContent).toContain('0 messages')
  })

  it('renders markdown headings and horizontal rules without leaking raw tokens', () => {
    const md: ExportMessage[] = [{
      id: 'a-md',
      role: 'assistant',
      content: [
        '###3. Platform Engineering & Internal Developer Platforms',
        '',
        'Body with **bold** and *italic* text.',
        '',
        '---',
        '',
        '---### 5. Advanced GitOps & Ephemeral Environments',
      ].join('\n'),
    }]
    act(() => {
      root.render(
        <PrintConversation title="MD" messages={md} exporting={false} onExportComplete={() => {}} />,
      )
    })
    const text = container.textContent || ''
    expect(text).toContain('Platform Engineering & Internal Developer Platforms')
    expect(text).toContain('Advanced GitOps & Ephemeral Environments')
    expect(text).toContain('bold')
    expect(text).toContain('italic')
    expect(text).not.toContain('###')
    expect(text).not.toContain('---')
  })

  it('passes unicode and emoji through unchanged', () => {
    const unicode: ExportMessage[] = [{
      id: 'a-uni',
      role: 'assistant',
      content: 'Launch 🚀 cost ₹1,500 → estimated ≥ 3× today.',
    }]
    act(() => {
      root.render(
        <PrintConversation title="Unicode" messages={unicode} exporting={false} onExportComplete={() => {}} />,
      )
    })
    expect(container.textContent).toContain('🚀')
    expect(container.textContent).toContain('₹1,500')
    expect(container.textContent).toContain('≥ 3×')
  })

  it('does not invoke print when not exporting', () => {
    render({ exporting: false })
    expect(printSpy).not.toHaveBeenCalled()
  })
})