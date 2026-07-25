import { useState, useEffect, useCallback } from 'react';
import type { ChatSession } from '../types';
import { api } from '../services/chatApi';

let sessionCounter = 0;

function generateSessionId(): string {
  return `session-${Date.now()}-${++sessionCounter}`;
}

export function useConversations() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const list = await api.fetchSessions();
    setSessions(list);
    if (!activeId && list.length > 0) {
      setActiveId(list[0].id);
    }
    setLoading(false);
  }, [activeId]);

  useEffect(() => { refresh(); }, [refresh]);

  const create = useCallback(() => {
    const id = generateSessionId();
    const newSession: ChatSession = {
      id,
      title: 'New Chat',
      is_pinned: false,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    setSessions(prev => [newSession, ...prev]);
    setActiveId(id);
    return id;
  }, []);

  const remove = useCallback(async (id: string) => {
    await api.deleteSession(id);
    setSessions(prev => prev.filter(s => s.id !== id));
    if (activeId === id) {
      setActiveId(prev => {
        const remaining = sessions.filter(s => s.id !== id);
        return remaining.length > 0 ? remaining[0].id : null;
      });
    }
  }, [activeId, sessions]);

  const rename = useCallback(async (id: string, title: string) => {
    await api.updateSession(id, { title });
    setSessions(prev => prev.map(s => s.id === id ? { ...s, title } : s));
  }, []);

  const togglePin = useCallback(async (id: string) => {
    const session = sessions.find(s => s.id === id);
    if (!session) return;
    const is_pinned = !session.is_pinned;
    await api.updateSession(id, { is_pinned });
    setSessions(prev => prev.map(s => s.id === id ? { ...s, is_pinned } : s));
  }, [sessions]);

  const switchTo = useCallback((id: string) => {
    setActiveId(id);
  }, []);

  const activeSession = sessions.find(s => s.id === activeId) ?? null;

  return {
    sessions,
    activeId,
    activeSession,
    loading,
    create,
    remove,
    rename,
    togglePin,
    switchTo,
    refresh,
  };
}
