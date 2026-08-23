import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useVirtualizer } from '@tanstack/react-virtual'
import { cn } from '@/lib/utils'
import { useChat } from '@/features/chat/hooks/useChat'
import { Composer } from './Composer'
import { MessageBubble } from './MessageBubble'
import { GenerationSpinner } from './GenerationSpinner'
import { ContextPanel } from './ContextPanel'
import { ArtifactCard } from './ArtifactCard'
import { ToolChips } from './ToolChips'
import { ScrollToBottom } from './ScrollToBottom'
import { ConversationOutline } from './ConversationNavigator'
import { PrintConversation } from './PrintConversation'
import { ConversationExportButton } from './ConversationExportButton'
import { selectExportMessages } from '@/features/chat/services/conversationExport'
import type { ResourceItem, MessageData } from '@/features/chat/types'
import type { NavigatorAnchor } from './ConversationNavigator'

interface OwnGPTPageProps {
  sessionId: string
  projectId?: string | null
  title?: string
  onFirstUserMessage?: (content: string) => void
}

export function OwnGPTPage({ sessionId, projectId, title = 'OwnGPT Conversation', onFirstUserMessage }: OwnGPTPageProps) {
  const navigate = useNavigate()
  const [contextPanelOpen, setContextPanelOpen] = useState(false)
  const [sourcesData, setSourcesData] = useState<ResourceItem[]>([])
  const [exporting, setExporting] = useState(false)

  const {
    messages,
    input,
    setInput,
    isLoading,
    streamingId,
    pipelineStages,
    loadingHistory,
    send,
    stop,
    bottomRef,
    context,
    addContextItem,
    removeContextItem,
    clearContext,
    tools,
    toggleTool,
    setToolMode,
  } = useChat({
    sessionId,
    projectId,
    model: import.meta.env.VITE_DEFAULT_MODEL || '',
    temperature: 0.7,
    systemPrompt: `You are a helpful AI engineering assistant on the Own Platform. Today's date is ${new Date().toISOString().split('T')[0]}.`,
    onFirstUserMessage,
  })

  const scrollRef = useRef<HTMLDivElement>(null)
  const visibleMessages = useMemo(
    () => messages.filter((m): m is MessageData & { role: 'user' | 'assistant' } => m.role !== 'tool_event'),
    [messages],
  )
  const hasMessages = visibleMessages.length > 0
  const [highlightedMsgId, setHighlightedMsgId] = useState<string | null>(null)
  const highlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const lastUserMsg = useMemo(() => messages.filter(m => m.role === 'user').pop(), [messages])

  const exportMessages = useMemo(() => selectExportMessages(messages), [messages])

  const handleRegenerate = useCallback(() => {
    if (lastUserMsg) setInput(lastUserMsg.content)
  }, [lastUserMsg, setInput])

  const handleEdit = useCallback((content: string) => {
    setInput(content)
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [setInput])

  const handleArtifactAction = useCallback((action: { label: string; href?: string }) => {
    if (action.href) navigate(action.href)
  }, [navigate])

  const handleShowSources = useCallback((sources: ResourceItem[]) => {
    setSourcesData(sources)
    setContextPanelOpen(true)
  }, [])

  const chapters: NavigatorAnchor[] = useMemo(() => {
    const userMessages = messages.filter(m => m.role === 'user')
    if (userMessages.length === 0) return []
    const MAX_CHAPTERS = 15
    let selectedUsers: typeof userMessages
    if (userMessages.length > MAX_CHAPTERS) {
      const step = (userMessages.length - 1) / (MAX_CHAPTERS - 1)
      selectedUsers = []
      for (let i = 0; i < MAX_CHAPTERS; i++) {
        selectedUsers.push(userMessages[Math.round(i * step)])
      }
    } else {
      selectedUsers = userMessages
    }
    return selectedUsers.map((msg) => {
      const msgIdx = messages.indexOf(msg)
      let responseCount = 0, artifactCount = 0, toolCount = 0
      if (msgIdx >= 0) {
        for (let j = msgIdx + 1; j < messages.length; j++) {
          const m = messages[j]
          if (!m || m.role === 'user') break
          if (m.role === 'assistant') {
            responseCount++
            if (m.usedTools) toolCount += m.usedTools.length
            if (m.artifacts) artifactCount += m.artifacts.length
          }
        }
      }
      return {
        id: `chapter-${msg.id}`,
        targetMsgId: msg.id,
        type: 'user' as const,
        label: msg.content.length > 50 ? msg.content.slice(0, 50).replace(/\s+\S*$/, '') + '…' : msg.content,
        responseCount, artifactCount, toolCount,
      }
    })
  }, [messages])

  // ── Virtualizer ──────────────────────────────────────────────────────────
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const [newMsgCount, setNewMsgCount] = useState(0)
  const prevMsgLen = useRef(visibleMessages.length)
  const isNearBottom = useRef(true)

  const rowVirtualizer = useVirtualizer({
    count: visibleMessages.length + 1,
    getScrollElement: () => scrollRef.current,
    estimateSize: (index) => {
      if (index === visibleMessages.length) return 1
      const msg = visibleMessages[index]
      if (!msg) return 120
      const len = msg.content?.length || 0
      const lines = Math.max(1, Math.ceil(len / 80))
      const textH = lines * 24
      const toolsH = (msg.usedTools?.length || 0) * 28
      const artH = (msg.artifacts?.length || 0) * 80
      const extra = msg.role === 'user' ? 40 : 60
      return Math.min(textH + toolsH + artH + extra, 5000)
    },
    getItemKey: (index) => visibleMessages[index]?.id ?? `anchor-${index}`,
    overscan: 10,
  })

  const streamingMsg = messages.find(m => m.id === streamingId)
  const showSpinner = isLoading && streamingId !== null && streamingMsg && !streamingMsg.content

  const scrollToBottom = useCallback(() => {
    rowVirtualizer.scrollToIndex(visibleMessages.length, { align: 'end', behavior: 'smooth' })
    setNewMsgCount(0)
    setTimeout(() => {
      const ta = document.querySelector('textarea')
      if (ta) ta.focus()
    }, 300)
  }, [rowVirtualizer, visibleMessages.length])

  const handleChapterClick = useCallback((_anchorId: string, targetMsgId: string) => {
    const targetIndex = visibleMessages.findIndex(m => m.id === targetMsgId)
    if (targetIndex !== -1) {
      rowVirtualizer.scrollToIndex(targetIndex, { align: 'start', behavior: 'smooth' })
    }
    setHighlightedMsgId(targetMsgId)
    if (highlightTimer.current) clearTimeout(highlightTimer.current)
    highlightTimer.current = setTimeout(() => setHighlightedMsgId(null), 2500)
  }, [visibleMessages, rowVirtualizer])

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    isNearBottom.current = distFromBottom < 80
    setShowScrollBtn(distFromBottom > 140)
  }, [])

  const msgCount = visibleMessages.length

  useEffect(() => {
    handleScroll()
  }, [msgCount, handleScroll])

  useEffect(() => {
    const len = msgCount
    const prevLen = prevMsgLen.current
    prevMsgLen.current = len

    if (len <= prevLen) return

    // React 18 batches both the user AND assistant setMessages calls into a single
    // render, so lastMsg.role is always 'assistant' by the time this runs.
    // The fix: always scroll to bottom when new messages arrive.
    setNewMsgCount(0)
    setTimeout(() => {
      const el = scrollRef.current
      if (el) {
        el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
      }
    }, 30)
  }, [msgCount])

  const lastMessageContent = visibleMessages[visibleMessages.length - 1]?.content || ''

  // While streaming: keep the view pinned to the bottom as new tokens arrive
  useEffect(() => {
    if (!isLoading || !isNearBottom.current) return
    const el = scrollRef.current
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: 'auto' })
    }
  }, [lastMessageContent, isLoading])

  // ── Render ───────────────────────────────────────────────────────────────
  const totalSize = rowVirtualizer.getTotalSize()
  const virtualRows = rowVirtualizer.getVirtualItems()

  return (
    <div className="flex flex-col h-full">
      <div className="relative flex-1 min-h-0">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="overflow-y-auto custom-scrollbar h-full"
          style={{ overflowAnchor: 'none' }}
        >
          <div className="pt-16 pb-20 px-6">
            <div className="max-w-[860px] mx-auto">
              {/* Virtual message list */}
              <div style={{ height: totalSize, position: 'relative' }}>
                {virtualRows.map(virtualRow => {
                  const isAnchor = virtualRow.index === visibleMessages.length
                  if (isAnchor) {
                    return (
                      <div key="bottom-anchor" ref={bottomRef} style={{ height: 1, width: '100%' }} />
                    )
                  }
                  const msg = visibleMessages[virtualRow.index]
                  if (!msg) return null
                  const isStreamingMsg = msg.id === streamingId
                  return (
                    <div
                      key={msg.id}
                      ref={rowVirtualizer.measureElement}
                      data-index={virtualRow.index}
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                    >
                      <div
                        className={cn(
                          'animate-message-in',
                          msg.role === 'user' && virtualRow.index > 0 && 'mt-8 sm:mt-10 pt-4 border-t border-border/25',
                          highlightedMsgId === msg.id && 'animate-highlight-fade',
                        )}
                      >
                      <MessageBubble
                        role={msg.role}
                        content={msg.content}
                        isStreaming={isStreamingMsg}
                        status={msg.status}
                        resources={msg.resources}
                        recordId={msg.recordId}
                        sessionId={sessionId}
                        onEdit={msg.role === 'user' ? handleEdit : undefined}
                        onShowSources={handleShowSources}
                      />
                      {msg.role === 'assistant' && msg.usedTools && msg.usedTools.length > 0 && !isStreamingMsg && (
                        <ToolChips tools={msg.usedTools} />
                      )}
                      {!isStreamingMsg && msg.artifacts && msg.artifacts.length > 0 && (
                        <div className="space-y-2">
                          {msg.artifacts.map(artifact => (
                            <ArtifactCard key={artifact.id} artifact={artifact} onAction={handleArtifactAction} />
                          ))}
                        </div>
                      )}
                    </div>
                    </div>
                  )
                })}
              </div>

              {showSpinner && (
                <div className="animate-fade-in mt-5 mb-6" style={{ animationDuration: '0.3s' }}>
                  <GenerationSpinner stages={pipelineStages} />
                </div>
              )}

              {loadingHistory && !hasMessages && (
                <div className="flex items-center justify-center h-48">
                  <div className="w-5 h-5 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
                </div>
              )}

              {!hasMessages && !loadingHistory && (
                <div className="flex flex-col items-center justify-center min-h-[50vh] text-center px-4 animate-fade-in">
                  <div className="relative mb-6 group cursor-pointer">
                    <div className="absolute -inset-4 rounded-full bg-primary/20 blur-xl opacity-75 group-hover:opacity-100 transition-opacity" />
                    <img
                      src="/OwnGPT_brand_assets_clean/OwnGPT-logo-symbol-blood-orange-tight.png"
                      alt="OwnGPT"
                      className="relative w-20 h-20 sm:w-24 sm:h-24 object-contain drop-shadow-[0_10px_25px_rgba(255,77,0,0.3)] transition-transform duration-300 group-hover:scale-105"
                    />
                  </div>
                  <h1 className="text-3xl font-extrabold text-foreground tracking-tight sm:text-4xl mb-3">
                    What can I help with today?
                  </h1>
                  <p className="text-muted-foreground/70 text-base max-w-md font-normal leading-relaxed">
                    OwnGPT AI Engineering Co-Pilot. Ask anything about your platform, code, or knowledge base.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="px-4 pb-5 pt-2">
        <div className="max-w-[860px] mx-auto relative">
          <ScrollToBottom show={showScrollBtn} onClick={scrollToBottom} newMessages={newMsgCount || undefined} isLoading={isLoading} />
          <Composer
            input={input}
            setInput={setInput}
            onSend={send}
            onStop={stop}
            isLoading={isLoading}
            tools={tools}
            onToggleTool={toggleTool}
            onToolModeChange={setToolMode}
            contextItems={context.items}
            onContextRemove={removeContextItem}
            projectId={projectId}
            messages={messages}
            onExportPdf={() => setExporting(true)}
            title={title}
            chapters={chapters}
            streamingId={streamingId}
            onChapterClick={handleChapterClick}
          />
        </div>
      </div>

      <ContextPanel open={contextPanelOpen} onClose={() => setContextPanelOpen(false)} sources={sourcesData} />

      <PrintConversation
        title={title}
        messages={exportMessages}
        exporting={exporting}
        onExportComplete={() => setExporting(false)}
      />
    </div>
  )
}
