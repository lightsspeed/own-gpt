import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
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
import type { ResourceItem } from '@/features/chat/types'
import type { NavigatorAnchor } from './ConversationNavigator'

interface OwnGPTPageProps {
  sessionId: string
}

export function OwnGPTPage({ sessionId }: OwnGPTPageProps) {
  const navigate = useNavigate()
  const [contextPanelOpen, setContextPanelOpen] = useState(false)
  const [sourcesData, setSourcesData] = useState<ResourceItem[]>([])

  const {
    messages,
    input,
    setInput,
    isLoading,
    streamingId,
    pipelineStages,
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
    model: 'gpt-4o-mini',
    temperature: 0.7,
    systemPrompt: 'You are a helpful AI engineering assistant on the Own Platform.',
  })

  const scrollRef = useRef<HTMLDivElement>(null)
  const visibleMessages = messages.filter(m => m.role !== 'tool_event')
  const hasMessages = visibleMessages.length > 0

  const isNearBottom = useRef(true)
  const [showScrollBtn, setShowScrollBtn] = useState(false)
  const [newMsgCount, setNewMsgCount] = useState(0)
  const prevMsgLen = useRef(visibleMessages.length)

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    setNewMsgCount(0)
  }, [bottomRef])

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    isNearBottom.current = distFromBottom < 120
    setShowScrollBtn(distFromBottom > 150)
  }, [])

  useEffect(() => {
    if (isNearBottom.current) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
      setNewMsgCount(0)
    } else if (isLoading && visibleMessages.length > prevMsgLen.current) {
      setNewMsgCount(c => c + 1)
    }
    prevMsgLen.current = visibleMessages.length
  }, [messages, isLoading, bottomRef, visibleMessages.length])

  const streamingMsg = messages.find(m => m.id === streamingId)
  const showSpinner = isLoading && streamingId !== null && streamingMsg && !streamingMsg.content

  const handleOpenSources = (resources: ResourceItem[]) => {
    setSourcesData(resources)
    setContextPanelOpen(true)
  }

  const lastUserMsg = messages.filter(m => m.role === 'user').pop()

  const handleRegenerate = () => {
    if (lastUserMsg) {
      setInput(lastUserMsg.content)
    }
  }

  const handleEdit = (content: string) => {
    setInput(content)
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }

  const handleArtifactAction = (action: { label: string; href?: string }) => {
    if (action.href) {
      navigate(action.href)
    }
  }

  const [highlightedMsgId, setHighlightedMsgId] = useState<string | null>(null)
  const highlightTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const handleChapterClick = useCallback((_anchorId: string, targetMsgId: string) => {
    setHighlightedMsgId(targetMsgId)
    if (highlightTimer.current) clearTimeout(highlightTimer.current)
    highlightTimer.current = setTimeout(() => setHighlightedMsgId(null), 2000)
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
      let responseCount = 0
      let artifactCount = 0
      let toolCount = 0
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
        responseCount,
        artifactCount,
        toolCount,
      }
    })
  }, [messages])

    return (
    <div className="flex flex-col h-full">
      <ScrollToBottom
        show={showScrollBtn}
        onClick={scrollToBottom}
        newMessages={newMsgCount || undefined}
        isLoading={isLoading}
      />
      <div className="relative flex-1 min-h-0">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="overflow-y-auto custom-scrollbar h-full"
        >
          <div className="pt-6 pb-4 px-6">
            <div className="max-w-[920px] mx-auto space-y-6">
            {hasMessages && (
              <div className="flex items-center gap-3 pb-2 border-b border-border/10">
                <ConversationOutline
                  chapters={chapters}
                  streamingId={streamingId}
                  onAnchorClick={handleChapterClick}
                />
              </div>
            )}

            {messages.map((msg, idx) => {
              if (msg.role === 'tool_event') return null
              return (
                <div key={msg.id} className={cn('animate-message-in space-y-3', highlightedMsgId === msg.id && 'animate-highlight-fade')}>
                  <MessageBubble
                    role={msg.role}
                    content={msg.content}
                    isStreaming={msg.id === streamingId}
                    resources={msg.resources}
                    answerMode={msg.answerMode}
                    onOpenSources={handleOpenSources}
                    onEdit={msg.role === 'user' ? handleEdit : undefined}
                    onRegenerate={msg.role === 'assistant' && idx === visibleMessages.length - 1 && !isLoading ? handleRegenerate : undefined}
                  />
                  {msg.role === 'assistant' && msg.usedTools && msg.usedTools.length > 0 && msg.id !== streamingId && (
                    <ToolChips tools={msg.usedTools} />
                  )}
                  {msg.id !== streamingId && msg.artifacts && msg.artifacts.length > 0 && (
                    <div className="space-y-2">
                      {msg.artifacts.map(artifact => (
                        <ArtifactCard
                          key={artifact.id}
                          artifact={artifact}
                          onAction={handleArtifactAction}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )
            })}

            {showSpinner && (
              <div className="animate-fade-in" style={{ animationDuration: '0.3s' }}>
                <GenerationSpinner stages={pipelineStages} />
              </div>
            )}

            {!hasMessages && (
              <div
                className="transition-all duration-500 ease-in-out overflow-hidden"
                style={{
                  maxHeight: '500px',
                  opacity: 1,
                  paddingBottom: '32px',
                }}
              >
                <div className="flex items-end justify-center">
                  <div className="max-w-[600px] mx-auto text-center space-y-5 px-6">
                    <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/25 mb-2">
                      <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                        <path d="M16 2L20 10L28 12L20 14L16 22L12 14L4 12L12 10L16 2Z" fill="currentColor" className="text-primary" />
                        <circle cx="16" cy="22" r="3" fill="currentColor" className="text-primary/60" />
                        <path d="M16 28L18 26H14L16 28Z" fill="currentColor" className="text-primary/40" />
                      </svg>
                    </div>
                    <div className="prose prose-invert max-w-none prose-headings:text-foreground prose-p:text-muted-foreground">
                      <h2 className="text-2xl font-semibold">Welcome to <span className="text-primary">OwnGPT</span></h2>
                      <p className="text-muted-foreground/80">Your intelligent engineering co-pilot. Ask me anything about your platform.</p>
                    </div>

                    <div className="flex flex-wrap justify-center gap-2 max-w-[480px] mx-auto">
                      {[
                        'Summarize platform health',
                        'Investigate retrieval quality',
                        'Run an evaluation',
                        'Compare experiments',
                        'Search knowledge base',
                        'Analyze recent findings',
                      ].map(q => (
                        <button
                          key={q}
                          onClick={() => setInput(q)}
                          className="px-3.5 py-2 rounded-xl border border-border/60 bg-elevated/40 text-small text-muted-foreground hover:text-foreground hover:border-primary/30 hover:bg-primary/5 transition-all"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
            </div>
          </div>
        </div>
      </div>

      <div className="pb-4">
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
        />
      </div>

      <ContextPanel
        open={contextPanelOpen}
        onClose={() => setContextPanelOpen(false)}
        sources={sourcesData}
      />
    </div>
  )
}
