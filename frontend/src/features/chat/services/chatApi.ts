import type { ChatSession, MessageData, ContextItem } from '../types';

const API_BASE = 'http://localhost:8000/api/v1';

export interface ChatRequestBodyParams {
  sessionId: string;
  message: string;
  model?: string;
  temperature?: number;
  systemPrompt: string;
  activeTools?: Record<string, string>;
  context?: ContextItem[];
  document?: string;
  projectId?: string | null;
  signal?: AbortSignal;
}

export function buildChatRequestBody(p: ChatRequestBodyParams): Record<string, unknown> {
  const body: Record<string, unknown> = {
    session_id: p.sessionId,
    message: p.message,
  };
  if (p.model) body.model = p.model;
  if (p.temperature != null) body.temperature = p.temperature;
  if (p.systemPrompt) body.system_prompt = p.systemPrompt;
  if (p.activeTools) {
    body.active_tools = {
      web: p.activeTools.web_search === 'auto' || p.activeTools.web_search === 'manual',
      kb: p.activeTools.knowledge_base === 'auto' || p.activeTools.knowledge_base === 'manual',
    };
  }
  if (p.context && p.context.length > 0) {
    body.context = p.context.map(c => ({ category: c.category, label: c.label, value: c.value }));
  }
  if (p.document) body.document = p.document;
  if (p.projectId) body.project_id = p.projectId;
  return body;
}

export async function responseError(res: Response): Promise<Error> {
  let message = 'Server error';
  try {
    const data = await res.json();
    const err = data?.error;
    if (err?.message) {
      message = typeof err.message === 'string' ? err.message : 'Server error';
    } else if (typeof data?.detail === 'string') {
      message = data.detail;
    }
  } catch {
    /* non-JSON error body — keep fallback */
  }
  return new Error(message);
}

export const api = {
  baseUrl: API_BASE,

  async fetchSessions(): Promise<ChatSession[]> {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions`);
      if (res.ok) {
        const data = await res.json();
        return (data.sessions || []).map((s: any) => ({
          id: s.id,
          title: s.title,
          is_pinned: s.is_pinned,
          project_id: s.project_id ?? null,
          created_at: s.created_at,
          updated_at: s.updated_at,
          message_count: s.message_count,
          last_answer_mode: s.last_answer_mode,
        }));
      }
    } catch { /* ignore */ }
    return [];
  },

  async search(query: string, type: string = 'all', limit: number = 20): Promise<{ results: any[]; total: number }> {
    try {
      const res = await fetch(`${API_BASE}/chat/search?q=${encodeURIComponent(query)}&type=${type}&limit=${limit}`);
      if (res.ok) return await res.json();
    } catch { /* ignore */ }
    return { results: [], total: 0 };
  },

  async fetchHistory(sessionId: string): Promise<MessageData[]> {
    try {
      const res = await fetch(`${API_BASE}/chat/${sessionId}/history`);
      if (res.ok) {
        const data = await res.json();
        if (data.messages?.length > 0) {
          return data.messages.map((m: any, i: number) => ({
            id: `history-${i}`,
            role: m.role as 'user' | 'assistant',
            content: m.content,
            status: m.status,
            timestamp: new Date(),
            resources: m.resources,
          }));
        }
      }
    } catch { /* ignore */ }
    return [];
  },

  async sendMessage(params: {
    sessionId: string;
    message: string;
    model?: string;
    temperature?: number;
    systemPrompt?: string;
    uploadedFiles?: { name: string; chunks: number; type: string }[];
    activeTools?: Record<string, string>;
    context?: ContextItem[];
    document?: string;
    projectId?: string | null;
    signal?: AbortSignal;
  }): Promise<Response> {
    const { sessionId, message, model, temperature, systemPrompt, uploadedFiles, activeTools, context, document, projectId, signal } = params;
    let prompt = systemPrompt || '';

    const toolInstructions: string[] = [];
    const webOn = activeTools?.web_search === 'auto' || activeTools?.web_search === 'manual';
    const kbOn = activeTools?.knowledge_base === 'auto' || activeTools?.knowledge_base === 'manual';

    if (webOn && !kbOn) {
      toolInstructions.push('CRITICAL: You MUST use the web search tool to find real-time information. Do NOT answer from your pre-trained knowledge or memory. Do NOT search the knowledge base. Every factual claim MUST be backed by a web search result with a URL citation. If you cannot find information via web search, state that clearly.');
    } else if (!webOn && kbOn) {
      toolInstructions.push('CRITICAL: You MUST use the knowledge base tool to retrieve information. Do NOT search the web. Always cite the source filename. Do NOT answer from your pre-trained memory.');
    } else if (!webOn && !kbOn) {
      toolInstructions.push('Do not search the knowledge base or the web. Answer from your own knowledge only.');
    } else if (webOn && kbOn) {
      toolInstructions.push('You have access to both web search and knowledge base. Use web search for real-time information and the knowledge base for internal documents. Always cite your sources.');
    }

    if (uploadedFiles?.length) {
      toolInstructions.push('The user has uploaded custom files. You MUST call the \'search_knowledge_base\' tool to query and retrieve facts from these documents to construct your answer. Do not answer from your pre-trained memory. Always provide citations (Sources) in your answer referencing the exact filename.');
    }

    if (toolInstructions.length > 0) {
      prompt = `${prompt}\n\n${toolInstructions.join('\n')}`.trim();
    }

    return fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildChatRequestBody({
        sessionId,
        message,
        model,
        temperature,
        systemPrompt: prompt,
        activeTools,
        context,
        document,
        projectId,
      })),
      signal,
    }).then(async res => {
      if (!res.ok) {
        throw await responseError(res);
      }
      return res;
    });
  },

  async deleteSession(sessionId: string): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}`, { method: 'DELETE' });
      return res.ok;
    } catch { return false; }
  },

  async sendThumb(recordId: string, thumb: 'up' | 'down'): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/telemetry/thumb`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ record_id: recordId, thumb }),
      });
      return res.ok;
    } catch { return false; }
  },

  async sendEvent(type: string, recordId: string, sessionId?: string, metadata?: Record<string, unknown>): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/telemetry/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, record_id: recordId, session_id: sessionId, metadata }),
      });
      return res.ok;
    } catch { return false; }
  },

  async updateSession(sessionId: string, updates: { title?: string; is_pinned?: boolean }): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      return res.ok;
    } catch { return false; }
  },
};
