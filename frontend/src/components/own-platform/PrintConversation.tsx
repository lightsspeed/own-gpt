import { useEffect } from 'react'
import { MarkdownRenderer } from '@/components/own-platform/MarkdownRenderer'
import {
  exportDocumentTitle,
  normalizeMarkdownForExport,
  type ExportMessage,
} from '@/features/chat/services/conversationExport'

interface PrintConversationProps {
  title: string
  messages: ExportMessage[]
  exporting: boolean
  onExportComplete: () => void
}

const PRINT_STYLES = `
#print-conversation { display: none; }

@media print {
  @page { margin: 12mm 15mm 15mm 15mm; size: auto; }

  body { background: #ffffff !important; overflow: visible !important; }
  body * { visibility: hidden !important; }
  #print-conversation, #print-conversation * { visibility: visible !important; }

  #print-conversation {
    display: block !important;
    position: static !important;
    width: 100% !important;
    height: auto !important;
    overflow: visible !important;
    background: #ffffff !important;
    color: #1F2937 !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif !important;
    font-size: 11pt !important;
    line-height: 1.45 !important;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }

  #print-conversation .pc-page {
    padding: 16mm 16mm 20mm 16mm !important;
  }

  /* ── Brand / header block ─────────────────────────────────────────── */
  #print-conversation .pc-brand {
    font-size: 9pt !important;
    font-weight: 700 !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    color: #4B5563 !important;
    margin: 0 0 6pt !important;
  }
  #print-conversation .pc-title {
    font-size: 19pt !important;
    font-weight: 700 !important;
    color: #111827 !important;
    margin: 0 0 5pt !important;
    line-height: 1.25 !important;
  }
  #print-conversation .pc-meta {
    font-size: 9pt !important;
    color: #6B7280 !important;
    margin: 0 !important;
  }
  #print-conversation .pc-divider {
    border: 0 !important;
    border-top: 1.5pt solid #111827 !important;
    margin: 12pt 0 0 !important;
  }

  /* ── Messages ─────────────────────────────────────────────────────── */
  #print-conversation .pc-msg {
    margin: 0 0 10pt !important;
    padding: 7pt 9pt !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 5pt !important;
  }
  /* Short user messages stay intact; long assistant answers flow */
  #print-conversation .pc-msg.user { break-inside: avoid-page !important; background: #F9FAFB !important; }
  #print-conversation .pc-msg.assistant { break-inside: auto !important; }

  #print-conversation .pc-role {
    font-size: 8.5pt !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: #4B5563 !important;
    margin: 0 0 3pt !important;
  }
  #print-conversation .pc-role.user { color: #1F2937 !important; }
  #print-conversation .pc-status { color: #B91C1C !important; font-style: italic !important; }
  #print-conversation .pc-time {
    font-size: 8.5pt !important;
    color: #6B7280 !important;
    font-weight: 400 !important;
    letter-spacing: 0 !important;
    text-transform: none !important;
  }

  /* ── Typography palette (overrides app dark-theme utilities) ──────── */
  #print-conversation p { color: #1F2937 !important; margin: 0 0 6pt !important; }
  #print-conversation h1, #print-conversation h2,
  #print-conversation h3, #print-conversation h4 { color: #111827 !important; margin: 11pt 0 4pt !important; break-after: avoid-page !important; }
  #print-conversation h1 { font-size: 16pt !important; }
  #print-conversation h2 { font-size: 14pt !important; }
  #print-conversation h3 { font-size: 12.5pt !important; }
  #print-conversation h4 { font-size: 11.5pt !important; }
  #print-conversation strong { color: #111827 !important; }
  #print-conversation em { color: #1F2937 !important; }
  #print-conversation ul, #print-conversation ol { margin: 0 0 6pt !important; padding-left: 18pt !important; }
  #print-conversation li { color: #1F2937 !important; margin: 0 0 2pt !important; break-inside: avoid-page !important; }
  #print-conversation hr { border: 0 !important; border-top: 1px solid #E5E7EB !important; margin: 10pt 0 !important; }
  #print-conversation blockquote {
    color: #4B5563 !important;
    border-left: 3pt solid #E5E7EB !important;
    margin: 6pt 0 !important;
    padding: 2pt 10pt !important;
  }
  #print-conversation a { color: #1D4ED8 !important; text-decoration: underline !important; }
  #print-conversation table { border-collapse: collapse !important; width: 100% !important; margin: 0 0 8pt !important; }
  #print-conversation th, #print-conversation td { border: 1px solid #D1D5DB !important; padding: 3pt 5pt !important; font-size: 9.5pt !important; color: #1F2937 !important; }
  #print-conversation th { background: #F3F4F6 !important; }

  /* ── Code ─────────────────────────────────────────────────────────── */
  #print-conversation code, #print-conversation pre {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace !important;
  }
  #print-conversation pre {
    background: #F3F4F6 !important;
    border: 1px solid #E5E7EB !important;
    color: #1F2937 !important;
    padding: 8pt !important;
    border-radius: 4pt !important;
    font-size: 9pt !important;
    line-height: 1.45 !important;
    white-space: pre-wrap !important;
    overflow-wrap: anywhere !important;
    margin: 6pt 0 !important;
    break-inside: auto !important;
  }
  #print-conversation pre code { background: transparent !important; border: 0 !important; padding: 0 !important; color: inherit !important; }
  #print-conversation :not(pre) > code {
    background: #F3F4F6 !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 3pt !important;
    padding: 0.5pt 3pt !important;
    font-size: 9pt !important;
    color: #1F2937 !important;
  }

  /* ── Sources / citations ──────────────────────────────────────────── */
  #print-conversation .pc-sources {
    margin-top: 6pt !important;
    padding-top: 5pt !important;
    border-top: 1px solid #E5E7EB !important;
    font-size: 9pt !important;
    color: #4B5563 !important;
    break-inside: avoid-page !important;
  }
  #print-conversation .pc-sources ul { margin: 2pt 0 0 14pt !important; padding: 0 !important; }
  #print-conversation .pc-sources li { color: #4B5563 !important; }
  #print-conversation .pc-sources .pc-cite { font-weight: 600 !important; color: #1D4ED8 !important; }

  /* ── Running footer with dynamic page numbers ─────────────────────── */
  #print-conversation .pc-footer {
    position: fixed !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    display: flex !important;
    justify-content: space-between !important;
    align-items: center !important;
    padding: 4mm 16mm 5mm 16mm !important;
    border-top: 1px solid #E5E7EB !important;
    font-size: 8.5pt !important;
    color: #6B7280 !important;
    background: #ffffff !important;
  }
  #print-conversation .pc-page-num::after {
    content: counter(page);
  }
}
`

const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MONTHS_LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

function formatTime(ts?: Date): string {
  if (!ts || !(ts instanceof Date) || Number.isNaN(ts.getTime())) return ''
  let h = ts.getHours()
  const ampm = h >= 12 ? 'PM' : 'AM'
  if (h === 0) h = 12
  else if (h > 12) h -= 12
  const mm = String(ts.getMinutes()).padStart(2, '0')
  return `${ts.getDate()} ${MONTHS_SHORT[ts.getMonth()]} ${ts.getFullYear()} · ${h}:${mm} ${ampm}`
}

function formatExported(ts: Date): string {
  return `${ts.getDate()} ${MONTHS_LONG[ts.getMonth()]} ${ts.getFullYear()}`
}

export function PrintConversation({ title, messages, exporting, onExportComplete }: PrintConversationProps) {
  const exportedAt = new Date()
  const fullTitle = title || 'OwnGPT Conversation'

  useEffect(() => {
    if (!exporting) return
    const prevTitle = document.title
    document.title = exportDocumentTitle(fullTitle, new Date())

    const printTimer = setTimeout(() => {
      if (typeof window.print === 'function') window.print()
    }, 350)

    const finish = () => {
      document.title = prevTitle
      onExportComplete()
    }
    window.addEventListener('afterprint', finish)
    const fallbackTimer = setTimeout(finish, 15000)

    return () => {
      clearTimeout(printTimer)
      clearTimeout(fallbackTimer)
      window.removeEventListener('afterprint', finish)
      document.title = prevTitle
    }
  }, [exporting, onExportComplete, fullTitle])

  return (
    <div id="print-conversation" aria-hidden="true">
      <style>{PRINT_STYLES}</style>
      <div className="pc-page">
        <div className="pc-header">
          <p className="pc-brand">OwnGPT</p>
          <h1 className="pc-title">{fullTitle}</h1>
          <p className="pc-meta">
            Exported: {formatExported(exportedAt)} · {messages.length} message{messages.length === 1 ? '' : 's'}
          </p>
          <hr className="pc-divider" />
        </div>

        {messages.map((m) => (
          <div key={m.id} className={`pc-msg ${m.role === 'user' ? 'user' : 'assistant'}`}>
            <p className={`pc-role ${m.role === 'user' ? 'user' : ''}`}>
              {m.role === 'user' ? 'You' : 'OwnGPT'}
              {m.status === 'failed' && <span className="pc-status"> · Generation failed</span>}
              {formatTime(m.timestamp) && <span className="pc-time"> · {formatTime(m.timestamp)}</span>}
            </p>
            <MarkdownRenderer content={normalizeMarkdownForExport(m.content)} />
            {m.resources && m.resources.length > 0 && (
              <div className="pc-sources">
                <strong>Sources:</strong>
                <ul>
                  {m.resources.map((r, i) => (
                    <li key={`${m.id}-src-${i}`}>
                      <span className="pc-cite">[{r.citation_index ?? i + 1}]</span>{' '}
                      {r.url ? <a href={r.url}>{r.title}</a> : r.title}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}

        <div className="pc-footer">
          <span>OwnGPT · Conversation Export</span>
          <span className="pc-page-num" />
        </div>
      </div>
    </div>
  )
}