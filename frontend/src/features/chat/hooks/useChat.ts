import { useState, useEffect, useRef, useCallback } from 'react';
import type { MessageData, UploadedFile, PipelineStage, ContextItem, ConversationContext, ToolInfo, ToolMode } from '../types';
import { DEFAULT_TOOLS } from '../types';
import { api } from '../services/chatApi';

export interface UseChatOptions {
  sessionId: string;
  model?: string;
  temperature?: number;
  systemPrompt?: string;
  uploadedFiles?: UploadedFile[];
}

export interface UseChatReturn {
  messages: MessageData[];
  setMessages: React.Dispatch<React.SetStateAction<MessageData[]>>;
  input: string;
  setInput: React.Dispatch<React.SetStateAction<string>>;
  isLoading: boolean;
  streamingId: string | null;
  pipelineStages: PipelineStage[];
  error: string | null;
  send: () => Promise<void>;
  stop: () => void;
  clear: () => void;
  bottomRef: React.RefObject<HTMLDivElement | null>;
  context: ConversationContext;
  addContextItem: (item: ContextItem) => void;
  removeContextItem: (id: string) => void;
  clearContext: () => void;
  tools: ToolInfo[];
  toggleTool: (name: string) => void;
  setToolMode: (name: string, mode: ToolMode) => void;
  loadingHistory: boolean;
}

const INITIAL_STAGES: PipelineStage[] = [
  { id: 'thinking',   label: 'Thinking',    status: 'waiting' },
  { id: 'routing',    label: 'Routing',     status: 'waiting' },
  { id: 'retrieving', label: 'Retrieving',  status: 'waiting' },
  { id: 'reranking',  label: 'Reranking',   status: 'waiting' },
  { id: 'generating', label: 'Generating',  status: 'waiting' },
];

function stageAfter(id: string): number {
  const order = ['thinking', 'routing', 'retrieving', 'reranking', 'generating'];
  return order.indexOf(id) + 1;
}

function advanceTo(stages: PipelineStage[], targetId: string, now: number = Date.now()): PipelineStage[] {
  const order = ['thinking', 'routing', 'retrieving', 'reranking', 'generating'];
  const idx = order.indexOf(targetId);
  if (idx === -1) return stages;
  return stages.map((s, i) => {
    if (i < idx) return { ...s, status: 'done' as const, elapsedMs: s.startedAt ? now - s.startedAt : undefined };
    if (i === idx) return { ...s, status: 'active' as const, startedAt: s.startedAt ?? now };
    return s;
  });
}

function completeAll(stages: PipelineStage[], now: number = Date.now()): PipelineStage[] {
  return stages.map(s => {
    if (s.status === 'active') {
      return { ...s, status: 'done' as const, elapsedMs: s.startedAt ? now - s.startedAt : undefined };
    }
    return { ...s, status: 'done' as const };
  });
}

export function useChat(options: UseChatOptions): UseChatReturn {
  const { sessionId, model, temperature, systemPrompt, uploadedFiles } = options;

  const [messages, setMessages] = useState<MessageData[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [pipelineStages, setPipelineStages] = useState<PipelineStage[]>(INITIAL_STAGES);
  const [error, setError] = useState<string | null>(null);
  const [context, setContext] = useState<ConversationContext>({ items: [] });
  const [tools, setTools] = useState<ToolInfo[]>(DEFAULT_TOOLS);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const initialLoadDone = useRef(false);

  const toggleTool = useCallback((name: string) => {
    setTools(prev => prev.map(t => t.name === name ? { ...t, enabled: !t.enabled } : t));
  }, []);

  const setToolMode = useCallback((name: string, mode: ToolMode) => {
    setTools(prev => prev.map(t => t.name === name ? { ...t, mode } : t));
  }, []);

  const addContextItem = useCallback((item: ContextItem) => {
    setContext(prev => ({
      items: [...prev.items.filter(i => !(i.category === item.category && i.value === item.value)), item],
    }));
  }, []);

  const removeContextItem = useCallback((id: string) => {
    setContext(prev => ({ items: prev.items.filter(i => i.id !== id) }));
  }, []);

  const clearContext = useCallback(() => {
    setContext({ items: [] });
  }, []);

  const contentBuffer = useRef('');
  const rafPending = useRef(false);
  const assistantIdRef = useRef('');
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const hasContent = useRef(false);
  const contextRef = useRef(context);
  contextRef.current = context;
  const toolsRef = useRef(tools);
  toolsRef.current = tools;

  /* Load history on mount / session change */
  useEffect(() => {
    let cancelled = false;
    setLoadingHistory(true);
    initialLoadDone.current = false;
    const load = async () => {
      const history = await api.fetchHistory(sessionId);
      if (cancelled) return;
      if (history.length > 0) {
        setMessages(history);
      } else {
        setMessages([]);
      }
      if (!cancelled) {
        setLoadingHistory(false);
        initialLoadDone.current = true;
      }
    };
    load();
    return () => { cancelled = true; };
  }, [sessionId]);

  /* Scroll is managed by the virtualizer in OwnGPTPage */

  const send = useCallback(async () => {
    if (!input.trim() || isLoading) return;

    const userMsg: MessageData = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);
    setError(null);
    hasContent.current = false;
    setPipelineStages(advanceTo(INITIAL_STAGES, 'thinking'));

    const assistantMessageId = (Date.now() + 1).toString();
    assistantIdRef.current = assistantMessageId;
    setStreamingId(assistantMessageId);
    setMessages(prev => [...prev, {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      resources: [],
    }]);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const ctx = contextRef.current.items;
      const contextStr = ctx.length > 0
        ? `\n\nCurrent context:\n${ctx.map(i => `- ${i.label} (${i.category})`).join('\n')}`
        : '';

      const enabledTools = toolsRef.current
        .filter(t => t.enabled)
        .reduce((acc, t) => ({ ...acc, [t.name]: t.mode }), {} as Record<string, string>);

      const response = await api.sendMessage({
        sessionId,
        message: userMsg.content,
        model,
        temperature,
        systemPrompt: systemPrompt ? systemPrompt + contextStr : contextStr,
        uploadedFiles,
        context: ctx,
        activeTools: enabledTools,
      });

      if (!response.ok) {
        throw new Error('Server error');
      }

      setPipelineStages(prev => advanceTo(prev, 'routing'));

      const reader = response.body?.getReader();
      if (!reader) throw new Error('ReadableStream not supported');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.slice(6).trim();
          if (dataStr === '[DONE]') continue;

          try {
            const payload = JSON.parse(dataStr);
            if (payload.type === 'content') {
              if (!hasContent.current) {
                hasContent.current = true;
                setPipelineStages(prev => advanceTo(prev, 'generating'));
              }
              contentBuffer.current += payload.content;
              if (!rafPending.current) {
                rafPending.current = true;
                requestAnimationFrame(() => {
                  const chunk = contentBuffer.current;
                  contentBuffer.current = '';
                  rafPending.current = false;
                  if (!chunk) return;
                  setMessages(prev => prev.map(m => {
                    if (m.id === assistantIdRef.current) {
                      return { ...m, content: m.content + chunk };
                    }
                    return m;
                  }));
                });
              }
            } else if (payload.type === 'tool_start') {
              if (payload.tool === 'search_knowledge_base' || payload.tool === 'search_web') {
                setPipelineStages(prev => advanceTo(prev, 'retrieving'));
              }
              setMessages(prev => {
                const idx = prev.findIndex(m => m.id === assistantMessageId);
                if (idx !== -1) {
                  const copy = [...prev];
                  copy.splice(idx, 0, {
                    id: `tool-${Date.now()}-${Math.random()}`,
                    role: 'tool_event',
                    content: '',
                    tool: { name: payload.tool, status: 'calling' },
                  });
                  return copy;
                }
                return prev;
              });
            } else if (payload.type === 'tool_end') {
              if (payload.tool === 'search_knowledge_base' || payload.tool === 'search_web') {
                setPipelineStages(prev => advanceTo(prev, 'reranking'));
              }
              setMessages(prev => prev.map(m => {
                if (m.role === 'tool_event' && m.tool?.name === payload.tool && m.tool?.status === 'calling') {
                  return { ...m, tool: { ...m.tool, status: 'done' } };
                }
                return m;
              }));
            } else if (payload.type === 'tool_used') {
              setMessages(prev => prev.map(m => {
                if (m.id === assistantMessageId) {
                  const existing = m.usedTools || [];
                  return { ...m, usedTools: existing.includes(payload.tool) ? existing : [...existing, payload.tool] };
                }
                return m;
              }));
            } else if (payload.type === 'evidence') {
              setMessages(prev => prev.map(m => {
                if (m.id === assistantMessageId) {
                  return { ...m, evidence: payload.evidence, answerMode: payload.answer_mode };
                }
                return m;
              }));
            } else if (payload.type === 'resources') {
              setMessages(prev => prev.map(m => {
                if (m.id === assistantMessageId) {
                  return { ...m, resources: payload.resources, answerMode: payload.answer_mode, answerModeMetadata: payload.answer_mode_metadata };
                }
                return m;
              }));
            } else if (payload.type === 'artifacts') {
              setMessages(prev => prev.map(m => {
                if (m.id === assistantMessageId) {
                  return { ...m, artifacts: payload.artifacts };
                }
                return m;
              }));
            } else if (payload.type === 'error') {
              throw new Error(payload.message);
            }
          } catch (err) {
            console.error('Error parsing SSE line', err);
          }
        }
      }

      setPipelineStages(prev => completeAll(prev));
    } catch (e: any) {
      if (e.name !== 'AbortError') {
        setError(e.message);
        setMessages(prev => prev.map(m => {
          if (m.id === assistantMessageId) {
            return { ...m, content: m.content + `\n\n⚠️ **Error:** ${e.message}` };
          }
          return m;
        }));
      }
    } finally {
      setIsLoading(false);
      setStreamingId(null);
      abortRef.current = null;
    }
  }, [input, isLoading, sessionId, model, temperature, systemPrompt, uploadedFiles]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setPipelineStages(prev => completeAll(prev));
  }, []);

  const clear = useCallback(() => {
    setMessages([]);
    setInput('');
    setError(null);
    setPipelineStages(INITIAL_STAGES);
  }, []);

  return {
    messages,
    setMessages,
    input,
    setInput,
    isLoading,
    streamingId,
    pipelineStages,
    error,
    send,
    stop,
    clear,
    bottomRef,
    context,
    addContextItem,
    removeContextItem,
    clearContext,
    tools,
    toggleTool,
    setToolMode,
    loadingHistory,
  };
}
