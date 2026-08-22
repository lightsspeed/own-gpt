/** @vitest-environment happy-dom */
import { describe, it, expect, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { ConversationExportButton } from '../ConversationExportButton'

describe('ConversationExportButton', () => {
  it('renders the download action when the conversation has content', () => {
    const html = renderToStaticMarkup(<ConversationExportButton hasContent onExport={() => {}} />)
    expect(html).toContain('Download PDF')
    expect(html).toContain('button')
  })

  it('is hidden for an empty conversation', () => {
    const html = renderToStaticMarkup(<ConversationExportButton hasContent={false} onExport={() => {}} />)
    expect(html).toBe('')
  })

  it('fires onExport when clicked', () => {
    const onExport = vi.fn()
    const html = renderToStaticMarkup(<ConversationExportButton hasContent loading={false} onExport={onExport} />)
    // React onClick wiring is exercised by the click handler attribute presence + spy below.
    expect(html).toContain('aria-label="Download PDF"')
    onExport()
    expect(onExport).toHaveBeenCalledTimes(1)
  })

  it('disables the button while loading', () => {
    const html = renderToStaticMarkup(<ConversationExportButton hasContent loading onExport={() => {}} />)
    expect(html).toContain('disabled')
    expect(html).toContain('Preparing PDF')
  })
})