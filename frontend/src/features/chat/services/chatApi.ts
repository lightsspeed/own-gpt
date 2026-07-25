import type { ChatSession, MessageData } from '../types';

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
  }): Promise<Response> {
    const { sessionId, message, model, temperature, systemPrompt, uploadedFiles } = params;
    const prompt = (uploadedFiles?.length ?? 0) > 0
      ? `${systemPrompt}\n\nIMPORTANT: The user has uploaded custom files. You MUST call the 'search_knowledge_base' tool to query and retrieve facts from these documents to construct your answer. Do not answer from your pre-trained memory. Always provide citations (Sources) in your answer referencing the exact filename.`
      : systemPrompt;

    return fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        model,
        temperature,
        system_prompt: prompt,
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
