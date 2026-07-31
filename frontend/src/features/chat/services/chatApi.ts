import type { ChatSession, MessageData, ContextItem } from '../types';

const API_BASE = 'http://localhost:8000/api/v1';

export const api = {
  baseUrl: API_BASE,

  async fetchSessions(): Promise<ChatSession[]> {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions`);
      if (res.ok) {
        const data = await res.json();
        return data.sessions || [];
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
  }): Promise<Response> {
    const { sessionId, message, model, temperature, systemPrompt, uploadedFiles, activeTools, context, document } = params;
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
      body: JSON.stringify({
        session_id: sessionId,
        message,
        model,
        temperature,
        system_prompt: prompt,
        active_tools: activeTools ? {
          web: activeTools.web_search === 'auto' || activeTools.web_search === 'manual',
          kb: activeTools.knowledge_base === 'auto' || activeTools.knowledge_base === 'manual',
        } : undefined,
        context: context?.map(c => ({ category: c.category, label: c.label, value: c.value })),
        document,
      }),
    });
  },

  async deleteSession(sessionId: string): Promise<boolean> {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}`, { method: 'DELETE' });
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
