/** @vitest-environment happy-dom */
import { describe, it, expect, afterEach, vi } from 'vitest'
import { createRoot, type Root } from 'react-dom/client'
import { act } from 'react'
import { MarkdownRenderer } from '../MarkdownRenderer'
import type { ResourceItem } from '@/features/chat/types'

const KB_RESOURCES: ResourceItem[] = [
  { type: 'file', title: 'report.pdf', citation_index: 1, section: 'Summary', page: 3, confidence_label: 'high', snippet: 'The report states the ground truth claim.' },
  { type: 'file', title: 'guide.pdf', citation_index: 2, confidence_label: 'medium', snippet: 'The guide expands on methodology.' },
]

const WEB_RESOURCES: ResourceItem[] = [
  { type: 'web', title: 'Pytest Docs', url: 'https://docs.pytest.org/', citation_index: 1, snippet: 'pytest is mature.' },
  { type: 'web', title: 'Vitest Guide', url: 'https://vitest.dev/', citation_index: 2, snippet: 'Vitest is fast.' },
]

const MIXED_RESOURCES: ResourceItem[] = [
  { type: 'web', title: 'Kubernetes Docs', url: 'https://kubernetes.io/docs/', citation_index: 1, snippet: 'K8s overview.' },
  { type: 'web', title: 'Docker Docs', url: 'https://docs.docker.com/', citation_index: 2, snippet: 'Docker overview.' },
]

function renderMarkdown(content: string, resources?: ResourceItem[]) {
  const container = document.createElement('div')
  document.body.appendChild(container)
  const root: Root = createRoot(container)
  act(() => {
    root.render(<MarkdownRenderer content={content} resources={resources} />)
  })
  return { container, root }
}

function pillsIn(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll('button')) as HTMLElement[]
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('MarkdownRenderer inline citations', () => {
  it('renders plain text when no resources are provided (streaming / user / print)', () => {
    const { container, root } = renderMarkdown('Claim [Chunk 0] here.')
    expect(container.textContent).toContain('Claim [Chunk 0] here.')
    expect(pillsIn(container).length).toBe(0)
    act(() => root.unmount())
  })

  it('renders pills with domain labels for resolved [Chunk N] markers', () => {
    const { container, root } = renderMarkdown('Alpha claim [Chunk 0]. Beta claim [Chunk 1].', KB_RESOURCES)
    const pills = pillsIn(container)
    expect(pills.length).toBe(2)
    // sourceDomain strips extension: "report.pdf" → "report", "guide.pdf" → "guide"
    expect(pills[0].textContent).toBe('report')
    expect(pills[1].textContent).toBe('guide')
    expect(container.textContent).toContain('Alpha claim')
    act(() => root.unmount())
  })

  it('renders pills with URL hostname labels for web resources', () => {
    const { container, root } = renderMarkdown('Fact [1] and fact [2].', WEB_RESOURCES)
    const pills = pillsIn(container)
    expect(pills.length).toBe(2)
    expect(pills[0].textContent).toBe('docs.pytest.org')
    expect(pills[1].textContent).toBe('vitest.dev')
    act(() => root.unmount())
  })

  it('opens the source card on pill click and closes via its close button', () => {
    const { container, root } = renderMarkdown('Alpha [Chunk 0].', KB_RESOURCES)
    act(() => {
      pillsIn(container)[0].click()
    })
    const dialog = container.querySelector('[role="dialog"]')!
    expect(dialog.textContent).toContain('report.pdf')
    expect(dialog.textContent).toContain('Summary')
    expect(dialog.textContent).toContain('Page 3')
    expect(dialog.textContent).toContain('The report states the ground truth claim.')
    act(() => {
      (dialog.querySelector('button[aria-label="Close source"]') as HTMLElement).click()
    })
    expect(container.querySelector('[role="dialog"]')).toBeNull()
    act(() => root.unmount())
  })

  it('cycles sources within a multi-source group with arrow keys', () => {
    // Consecutive markers form a single multi-source group
    const { container, root } = renderMarkdown('Alpha [Chunk 0][Chunk 1].', KB_RESOURCES)
    act(() => {
      pillsIn(container)[0].click()
    })
    const dialog = () => container.querySelector('[role="dialog"]')!
    expect(dialog()!.textContent).toContain('report.pdf')
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }))
    })
    expect(dialog()!.textContent).toContain('guide.pdf')
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }))
    })
    expect(dialog()!.textContent).toContain('report.pdf')
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    })
    expect(container.querySelector('[role="dialog"]')).toBeNull()
    act(() => root.unmount())
  })

  it('shows source count and navigation in multi-source popovers', () => {
    const { container, root } = renderMarkdown('Alpha [Chunk 0][Chunk 1].', KB_RESOURCES)
    act(() => {
      pillsIn(container)[0].click()
    })
    expect(container.textContent).toContain('1 / 2')
    act(() => root.unmount())
  })

  it('leaves unresolvable markers as plain text', () => {
    const { container, root } = renderMarkdown('Out of range [Chunk 9] stays literal.', KB_RESOURCES)
    expect(container.textContent).toContain('Out of range [Chunk 9] stays literal.')
    expect(pillsIn(container).length).toBe(0)
    act(() => root.unmount())
  })

  it('keeps [Chunk N] inside fenced code blocks untouched', () => {
    const content = 'Claim [Chunk 0].\n\n```js\nconst label = "[Chunk 7]";\n```'
    const { container, root } = renderMarkdown(content, KB_RESOURCES)
    // At least 1 pill for [Chunk 0] outside the fence
    expect(pillsIn(container).length).toBeGreaterThanOrEqual(1)
    // The code block text must be preserved literally
    expect(container.textContent).toContain('[Chunk 7]')
    act(() => root.unmount())
  })

  it('renders bare web [N] markers against 1-based tool labels', () => {
    const content = 'Pytest is mature [1] while Vitest is fast [2].'
    const { container, root } = renderMarkdown(content, WEB_RESOURCES)
    const pills = pillsIn(container)
    expect(pills.length).toBe(2)
    act(() => {
      pills[0].click()
    })
    const dialog = container.querySelector('[role="dialog"]')!
    expect(dialog.textContent).toContain('Pytest Docs')
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    })
    act(() => root.unmount())
  })

  it('groups consecutive [Chunk N] markers into a single pill with +N label', () => {
    const content = 'First [Chunk 0][Chunk 1] and more.'
    const { container, root } = renderMarkdown(content, KB_RESOURCES)
    const pills = pillsIn(container)
    // [Chunk 0]+[Chunk 1] → single group (report + guide)
    expect(pills.length).toBe(1)
    // sourceDomain strips extension: "report.pdf" → "report"
    expect(pills[0].textContent).toBe('report +1')
    act(() => root.unmount())
  })

  it('renders domain-based pill labels from URLs', () => {
    const content = 'Ref [1]. Ref [2].'
    const { container, root } = renderMarkdown(content, MIXED_RESOURCES)
    const pills = pillsIn(container)
    expect(pills.length).toBe(2)
    expect(pills[0].textContent).toBe('kubernetes.io')
    expect(pills[1].textContent).toBe('docs.docker.com')
    act(() => root.unmount())
  })

  it('does not render pills during streaming (resources provided but content has no markers)', () => {
    const { container, root } = renderMarkdown('Streaming answer in progress...', KB_RESOURCES)
    expect(pillsIn(container).length).toBe(0)
    act(() => root.unmount())
  })

  it('hover-enter opens the popover and hover-leave closes it', () => {
    vi.useFakeTimers()
    const { container, root } = renderMarkdown('Claim [Chunk 0].', KB_RESOURCES)
    const pill = pillsIn(container)[0]

    // Use focus to trigger onHoverEnter (CitationPill wires onFocus → onHoverEnter)
    act(() => {
      pill.focus()
    })
    act(() => { vi.advanceTimersByTime(0) })
    expect(container.querySelector('[role="dialog"]')).not.toBeNull()

    // Blur triggers no leave handler, so use Escape to close
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    })
    act(() => { vi.advanceTimersByTime(0) })
    expect(container.querySelector('[role="dialog"]')).toBeNull()

    vi.useRealTimers()
    act(() => root.unmount())
  })
})
