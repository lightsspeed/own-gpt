import React, { useState, useEffect, useRef } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Send, Settings, History, FileText, Plus, Loader2,
  Globe, BookOpen, Zap, PanelLeftClose, PanelLeft, Mic, Trash2, MessageSquare,
  Pin, Edit2, Check, X, MoreHorizontal, ImagePlus
} from 'lucide-react';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarTrigger,
  SidebarMenuAction,
  SidebarInset
} from "@/components/ui/sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ChatMessage } from './ChatMessage';
import type { MessageData } from './ChatMessage';
import { DocumentUpload } from '../documents/DocumentUpload';
import { SettingsModal } from '../settings/SettingsModal';
import type { AppSettings } from '../settings/SettingsModal';
import { ToolPicker } from './ToolPicker';

const API_BASE = 'http://localhost:8000/api/v1';

function getOrCreateSessionId(): string {
  let sid = localStorage.getItem('chat_session_id');
  if (!sid) {
    sid = crypto.randomUUID();
    localStorage.setItem('chat_session_id', sid);
  }
  return sid;
}

const TOOLS_INFO = [
  { name: 'search_knowledge_base', label: 'Knowledge Base', icon: <BookOpen size={13} />, color: 'text-blue-400', desc: 'Searches your uploaded documents using semantic similarity.' },
  { name: 'search_web', label: 'Web Search', icon: <Globe size={13} />, color: 'text-sky-400', desc: 'Searches the internet for real-time information via Tavily.' },
  { name: 'sm_integration', label: 'Social Media', icon: <Zap size={13} />, color: 'text-indigo-400', desc: 'Post, read, or analyze social media content.' },
];

export function ChatLayout() {
  const [messages, setMessages] = useState<MessageData[]>([]);
  const [input, setInput] = useState('');
  const [isSidebarOpen, setSidebarOpen] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const [isSettingsOpen, setSettingsOpen] = useState(false);
  const [isToolPickerOpen, setToolPickerOpen] = useState(false);
  const [activeTools, setActiveTools] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string>(getOrCreateSessionId);
  const [sessions, setSessions] = useState<{ id: string; title: string; is_pinned?: boolean }[]>([]);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<{ name: string; chunks: number; type: string }[]>([]);
  const [imageAttachments, setImageAttachments] = useState<{ name: string; base64: string; mimeType: string; preview: string }[]>([]);
  const [uploadProgress, setUploadProgress] = useState<{
    filename: string;
    stage: 'reading' | 'uploading' | 'chunking' | 'embedding' | 'done' | 'error';
    chunks?: number;
  } | null>(null);
  const hiddenFileInputRef = useRef<HTMLInputElement>(null);
  const hiddenImageInputRef = useRef<HTMLInputElement>(null);
  const inputBarRef = useRef<HTMLDivElement>(null);
  const [appSettings, setAppSettings] = useState<AppSettings>({
    model: 'gpt-4o-mini',
    temperature: 0.7,
    systemPrompt: 'You are a helpful, knowledgeable AI assistant with access to tools including web search and a knowledge base of uploaded documents. Be concise, accurate, and friendly.',
  });
  const bottomRef = useRef<HTMLDivElement>(null);

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch {}
  };

  useEffect(() => {
    fetchSessions();
  }, [sessionId]);

  // Load history on mount
  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch(`${API_BASE}/chat/${sessionId}/history`);
        if (res.ok) {
          const data = await res.json();
          if (data.messages?.length > 0) {
            setMessages(data.messages.map((m: any, i: number) => ({
              id: `history-${i}`,
              role: m.role as 'user' | 'assistant',
              content: m.content,
              timestamp: new Date(),
              resources: m.resources
            })));
          } else {
            setMessages([{
              id: 'welcome',
              role: 'assistant',
              content: `## Welcome to **Own GPT** 👋\n\nI'm your personal AI assistant with:\n- 🧠 **Persistent memory** — I remember our full conversation\n- 📚 **Knowledge Base** — Upload documents and ask me about them\n- 🌐 **Web Search** — I can look up real-time information\n- 🔧 **Tool Calling** — Watch me use tools in real-time\n\nTry asking me anything, or upload a document to get started!`,
              timestamp: new Date(),
            }]);
          }
        }
      } catch { /* ignore */ }
      finally { setIsLoadingHistory(false); }
    };
    load();
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = async () => {
    if ((!input.trim() && imageAttachments.length === 0) || isLoading) return;
    const userContent = input.trim() || (imageAttachments.length > 0 ? 'Analyze this image' : '');
    const userMsg: MessageData = { 
      id: Date.now().toString(), 
      role: 'user', 
      content: userContent,
      images: imageAttachments.map(img => img.preview),
      timestamp: new Date() 
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    const imagesToSend = [...imageAttachments];
    setImageAttachments([]);
    setIsLoading(true);

    const assistantMessageId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      resources: [],
    }]);

    try {
      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: userMsg.content,
          model: appSettings.model,
          temperature: appSettings.temperature,
          system_prompt: uploadedFiles.length > 0
            ? `${appSettings.systemPrompt}\n\nIMPORTANT: The user has uploaded custom files. You MUST call the 'search_knowledge_base' tool to query and retrieve facts from these documents to construct your answer. Do not answer from your pre-trained memory. Always provide citations (Sources) in your answer referencing the exact filename.`
            : appSettings.systemPrompt,
          images: imagesToSend.length > 0 ? imagesToSend.map(img => ({
            base64: img.base64,
            mimeType: img.mimeType,
            name: img.name,
          })) : undefined,
        }),
      });

      if (!response.ok) {
        throw new Error('Server error');
      }

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
            console.log("SSE payload:", payload);
            if (payload.type === 'content') {
              setMessages(prev => prev.map(m => {
                if (m.id === assistantMessageId) {
                  return { ...m, content: m.content + payload.content };
                }
                return m;
              }));
            } else if (payload.type === 'tool_start') {
              setMessages(prev => {
                const idx = prev.findIndex(m => m.id === assistantMessageId);
                if (idx !== -1) {
                  const copy = [...prev];
                  copy.splice(idx, 0, {
                    id: `tool-${Date.now()}-${Math.random()}`,
                    role: 'tool_event',
                    content: '',
                    tool: { name: payload.tool, status: 'calling' }
                  });
                  return copy;
                }
                return prev;
              });
            } else if (payload.type === 'tool_end') {
              setMessages(prev => prev.map(m => {
                if (m.role === 'tool_event' && m.tool?.name === payload.tool && m.tool?.status === 'calling') {
                  return { ...m, tool: { ...m.tool, status: 'done' } };
                }
                return m;
              }));
            } else if (payload.type === 'resources') {
              setMessages(prev => prev.map(m => {
                if (m.id === assistantMessageId) {
                  return { ...m, resources: payload.resources };
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
      fetchSessions();
    } catch (e: any) {
      setMessages(prev => prev.map(m => {
        if (m.id === assistantMessageId) {
          return { ...m, content: m.content + `\n\n⚠️ **Error:** ${e.message}` };
        }
        return m;
      }));
    } finally {
      setIsLoading(false);
    }
  };

  const handleToolSelect = (toolId: string) => {
    setActiveTools(prev =>
      prev.includes(toolId) ? prev.filter(t => t !== toolId) : [...prev, toolId]
    );
    // Append tool hint to message input
    const toolHints: Record<string, string> = {
      search_web: '[Use web search] ',
      search_knowledge_base: '[Search knowledge base] ',
      deep_research: '[Deep research] ',
      create_image: '[Create an image of] ',
      sm_integration: '[Social media] ',
    };
    if (toolHints[toolId]) {
      setInput(prev => (prev.startsWith(toolHints[toolId]) ? prev.slice(toolHints[toolId].length) : toolHints[toolId] + prev));
    }
  };

  const handleNewChat = () => {
    const newId = crypto.randomUUID();
    localStorage.setItem('chat_session_id', newId);
    setSessionId(newId);
  };

  const handleDeleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.id !== id));
        if (id === sessionId) handleNewChat();
      }
    } catch (err) {
      console.error('Failed to delete session', err);
    }
  };

  const handleUpdateSession = async (id: string, updates: { title?: string; is_pinned?: boolean }, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
      if (res.ok) {
        setSessions(prev => prev.map(s => s.id === id ? { ...s, ...updates } : s).sort((a, b) => {
          if (a.is_pinned && !b.is_pinned) return -1;
          if (!a.is_pinned && b.is_pinned) return 1;
          return 0; // maintain relative order for simple optimistic update
        }));
        setEditingSessionId(null);
      }
    } catch (err) {
      console.error('Failed to update session', err);
    }
  };

  const handleClearHistory = () => {
    handleDeleteSession(sessionId, { stopPropagation: () => {} } as any);
  };

  return (
    <SidebarProvider>
      {/* ─── Shadcn Sidebar ─── */}
      <Sidebar variant="inset" className="border-r border-border/50">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" className="hover:bg-transparent cursor-default">
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-blue-600 text-white font-bold text-xs shadow-md">
                  AI
                </div>
                <div className="flex flex-col gap-0.5 leading-none">
                  <span className="font-semibold tracking-tight">Own GPT</span>
                  <span className="text-xs text-muted-foreground">Beta Version</span>
                </div>
              </SidebarMenuButton>
            </SidebarMenuItem>
            
            <SidebarMenuItem className="mt-2">
              <SidebarMenuButton onClick={handleNewChat} className="border border-blue-500/20 text-blue-400 hover:bg-blue-500/10 justify-start">
                <Plus /> <span>New Chat</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel className="text-xs uppercase font-semibold">Available Tools</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {TOOLS_INFO.map(t => (
                  <SidebarMenuItem key={t.name}>
                    <SidebarMenuButton className="h-auto py-2 px-3">
                      <span className={`mt-0.5 ${t.color}`}>{t.icon}</span>
                      <div className="flex flex-col gap-0.5">
                        <span className="text-xs font-medium">{t.label}</span>
                        <span className="text-[10px] text-muted-foreground leading-tight whitespace-normal">{t.desc}</span>
                      </div>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>

          <SidebarGroup>
            <SidebarGroupLabel className="text-xs uppercase font-semibold">Chat History</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {sessions.map(s => (
                  <SidebarMenuItem key={s.id}>
                    {editingSessionId === s.id ? (
                      <div className="flex items-center gap-1 w-full px-2 py-1">
                        <input
                          autoFocus
                          className="flex-1 bg-background text-foreground border border-border rounded px-1.5 py-0.5 outline-none min-w-0 text-xs"
                          value={editTitle}
                          onChange={e => setEditTitle(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') handleUpdateSession(s.id, { title: editTitle });
                            if (e.key === 'Escape') setEditingSessionId(null);
                          }}
                        />
                        <button onClick={() => handleUpdateSession(s.id, { title: editTitle })} className="text-green-500 p-0.5"><Check size={12} /></button>
                        <button onClick={() => setEditingSessionId(null)} className="text-muted-foreground p-0.5"><X size={12} /></button>
                      </div>
                    ) : (
                      <>
                        <SidebarMenuButton 
                          isActive={s.id === sessionId}
                          onClick={() => {
                            localStorage.setItem('chat_session_id', s.id);
                            setSessionId(s.id);
                          }}
                        >
                          {s.is_pinned ? <Pin className="fill-current" /> : <MessageSquare />}
                          <span>{s.title}</span>
                        </SidebarMenuButton>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <SidebarMenuAction>
                              <MoreHorizontal />
                            </SidebarMenuAction>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent side="right" align="start">
                            <DropdownMenuItem onClick={(e) => handleUpdateSession(s.id, { is_pinned: !s.is_pinned }, e as any)}>
                              <Pin className="mr-2 h-4 w-4" />
                              {s.is_pinned ? "Unpin" : "Pin"}
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => { setEditTitle(s.title); setEditingSessionId(s.id); }}>
                              <Edit2 className="mr-2 h-4 w-4" />
                              Rename
                            </DropdownMenuItem>
                            <DropdownMenuItem className="text-red-500 hover:text-red-600" onClick={(e) => handleDeleteSession(s.id, e as any)}>
                              <Trash2 className="mr-2 h-4 w-4" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </>
                    )}
                  </SidebarMenuItem>
                ))}
                {sessions.length === 0 && (
                  <div className="px-3 py-2 text-xs text-muted-foreground/60 italic">No saved chats</div>
                )}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>

        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={() => setSettingsOpen(true)}>
                <Settings /> <span>Settings</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>

      {/* ─── Main Content ─── */}
      <SidebarInset className="flex flex-col min-w-0 relative h-screen bg-background">
        {/* Header */}
        <header className="h-14 border-b border-border/40 flex items-center px-4 gap-3 glass-panel flex-shrink-0 absolute top-0 left-0 right-0 z-20">
          <SidebarTrigger className="-ml-1" />

          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm">Own GPT</span>
            <Badge className="bg-primary/20 text-primary border-primary/30 text-xs">{appSettings.model}</Badge>
          </div>

          <div className="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              Live
            </span>
            <span>{messages.filter(m => m.role === 'user').length} msgs</span>
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setSettingsOpen(true)}>
              <Settings size={14} />
            </Button>
          </div>
        </header>

        {/* Messages */}
        <ScrollArea className="flex-1 h-full w-full">
          <div className="max-w-3xl mx-auto px-4 pt-20 pb-40 space-y-5">
            {isLoadingHistory ? (
              <div className="flex justify-center items-center h-40 gap-3 text-muted-foreground">
                <Loader2 className="animate-spin" size={18} />
                <span className="text-sm">Restoring conversation…</span>
              </div>
            ) : (
              messages.map(msg => <ChatMessage key={msg.id} {...msg} />)
            )}

            {/* Typing indicator */}
            {isLoading && (
              <div className="flex gap-3 opacity-70">
                <div className="w-8 h-8 rounded-full bg-primary/20 flex-shrink-0 flex items-center justify-center">
                  <div className="w-3 h-3 rounded-full bg-primary animate-pulse" />
                </div>
                <div className="bg-card/50 border border-white/5 rounded-2xl rounded-tl-sm px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0.15s' }} />
                    <div className="w-2 h-2 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0.3s' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        {/* True Floating Input Area */}
        <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-background via-background/95 to-transparent z-10 pointer-events-none">
          <div className="max-w-3xl mx-auto relative pointer-events-auto">
            {/* Uploaded File Chips */}
            {uploadedFiles.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2 justify-start items-center">
                {uploadedFiles.map((file, i) => (
                  <div key={i} className="flex items-center gap-1.5 bg-blue-500/10 border border-blue-500/20 text-blue-300 text-xs px-2.5 py-1 rounded-full animate-in fade-in slide-in-from-bottom-1 duration-200">
                    <FileText size={12} className="text-blue-400" />
                    <span className="max-w-[120px] truncate">{file.name}</span>
                    <button
                      onClick={() => setUploadedFiles(prev => prev.filter((_, idx) => idx !== i))}
                      className="text-blue-400 hover:text-blue-200 transition-colors p-0.5 rounded-full hover:bg-white/5"
                    >
                      <X size={10} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Image Attachment Thumbnails */}
            {imageAttachments.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-2">
                {imageAttachments.map((img, i) => (
                  <div key={i} className="relative group animate-in fade-in zoom-in-75 duration-200">
                    <img
                      src={img.preview}
                      alt={img.name}
                      className="w-16 h-16 rounded-xl object-cover border border-white/10 shadow-lg"
                    />
                    <button
                      onClick={() => setImageAttachments(prev => prev.filter((_, idx) => idx !== i))}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 hover:bg-red-400 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity shadow-lg"
                    >
                      <X size={10} className="text-white" />
                    </button>
                    <div className="absolute inset-0 rounded-xl bg-black/0 group-hover:bg-black/20 transition-colors" />
                  </div>
                ))}
              </div>
            )}

            <input
              type="file"
              accept=".pdf,.txt,.md"
              ref={hiddenFileInputRef}
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;

                // Stage 1: Reading
                setUploadProgress({ filename: file.name, stage: 'reading' });
                await new Promise(r => setTimeout(r, 400));

                // Stage 2: Uploading
                setUploadProgress({ filename: file.name, stage: 'uploading' });
                const fd = new FormData();
                fd.append('file', file);

                try {
                  const res = await fetch(`${API_BASE}/documents/upload`, { method: 'POST', body: fd });

                  // Stage 3: Chunking (simulated during parse)
                  setUploadProgress({ filename: file.name, stage: 'chunking' });
                  await new Promise(r => setTimeout(r, 350));

                  if (res.ok) {
                    const data = await res.json();

                    // Stage 4: Embedding
                    setUploadProgress({ filename: file.name, stage: 'embedding', chunks: data.chunks });
                    await new Promise(r => setTimeout(r, 400));

                    // Stage 5: Done
                    setUploadProgress({ filename: file.name, stage: 'done', chunks: data.chunks });
                    setUploadedFiles(prev => [...prev, { name: data.filename, chunks: data.chunks, type: '.' + file.name.split('.').pop() }]);

                    // Auto-dismiss after 2.5s
                    setTimeout(() => setUploadProgress(null), 2500);
                  } else {
                    setUploadProgress({ filename: file.name, stage: 'error' });
                    setTimeout(() => setUploadProgress(null), 3000);
                  }
                } catch {
                  setUploadProgress({ filename: file.name, stage: 'error' });
                  setTimeout(() => setUploadProgress(null), 3000);
                }
                e.target.value = '';
              }}
            />

            {/* Hidden Image Picker */}
            <input
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif"
              multiple
              ref={hiddenImageInputRef}
              className="hidden"
              onChange={async (e) => {
                const files = Array.from(e.target.files || []);
                const results = await Promise.all(files.map(file => new Promise<{ name: string; base64: string; mimeType: string; preview: string }>((resolve) => {
                  const reader = new FileReader();
                  reader.onload = () => {
                    const dataUrl = reader.result as string;
                    const base64 = dataUrl.split(',')[1];
                    resolve({ name: file.name, base64, mimeType: file.type, preview: dataUrl });
                  };
                  reader.readAsDataURL(file);
                })));
                setImageAttachments(prev => [...prev, ...results]);
                e.target.value = '';
              }}
            />

            {/* Upload Progress Banner */}
            {uploadProgress && (
              <div className={`mb-2 flex items-center gap-3 px-4 py-2.5 rounded-xl border text-xs font-medium animate-in fade-in slide-in-from-bottom-2 duration-200
                ${ uploadProgress.stage === 'error'
                    ? 'bg-red-500/10 border-red-500/20 text-red-300'
                    : uploadProgress.stage === 'done'
                    ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                    : 'bg-blue-500/10 border-blue-500/20 text-blue-300'
                }`}
              >
                {uploadProgress.stage === 'done' ? (
                  <div className="w-4 h-4 rounded-full bg-emerald-500 flex items-center justify-center flex-shrink-0">
                    <Check size={10} className="text-white" />
                  </div>
                ) : uploadProgress.stage === 'error' ? (
                  <div className="w-4 h-4 rounded-full bg-red-500 flex items-center justify-center flex-shrink-0">
                    <X size={10} className="text-white" />
                  </div>
                ) : (
                  <Loader2 size={14} className="animate-spin flex-shrink-0" />
                )}

                <div className="flex flex-col gap-0.5 min-w-0">
                  <span className="truncate text-white/80">{uploadProgress.filename}</span>
                  <span className="text-[10px] opacity-70">
                    {uploadProgress.stage === 'reading' && 'Reading file...'}
                    {uploadProgress.stage === 'uploading' && 'Uploading to server...'}
                    {uploadProgress.stage === 'chunking' && 'Splitting into chunks...'}
                    {uploadProgress.stage === 'embedding' && `Generating embeddings${uploadProgress.chunks ? ` for ${uploadProgress.chunks} chunks` : ''}...`}
                    {uploadProgress.stage === 'done' && `Done! ${uploadProgress.chunks} chunks embedded into knowledge base.`}
                    {uploadProgress.stage === 'error' && 'Upload failed. Please try again.'}
                  </span>
                </div>

                {/* Animated step dots */}
                {!['done', 'error'].includes(uploadProgress.stage) && (
                  <div className="ml-auto flex items-center gap-1.5 flex-shrink-0">
                    {(['reading', 'uploading', 'chunking', 'embedding'] as const).map((s, i) => (
                      <div key={s} className={`w-1.5 h-1.5 rounded-full transition-all duration-300
                        ${ (['reading', 'uploading', 'chunking', 'embedding'] as const).indexOf(uploadProgress.stage) >= i
                            ? 'bg-blue-400 scale-125'
                            : 'bg-blue-400/20'
                        }`}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* The Gemini-style Floating Pill Input */}
            <div className="relative">
              {/* Glow layer */}
              <div className="absolute inset-0 rounded-full blur-xl opacity-30 bg-gradient-to-r from-blue-600 via-indigo-500 to-blue-400 animate-pulse pointer-events-none" />
              <div ref={inputBarRef} className="relative flex items-center gap-2 bg-[#12141a] rounded-full px-4 py-3 shadow-2xl border border-blue-500/20 focus-within:border-blue-400/60 focus-within:shadow-[0_0_30px_rgba(59,130,246,0.35)] transition-all duration-300">
              {/* + Tool picker button */}
              <Button
                id="tool-picker-btn"
                variant="ghost"
                size="icon"
                className="h-10 w-10 rounded-full flex-shrink-0 text-muted-foreground hover:text-foreground hover:bg-white/10 transition-colors"
                onClick={() => setToolPickerOpen(v => !v)}
                disabled={isLoadingHistory}
              >
                <Plus size={20} />
              </Button>

              {/* Tool Picker Popup */}
              <ToolPicker
                open={isToolPickerOpen}
                onClose={() => setToolPickerOpen(false)}
                onFileUploadClick={() => hiddenFileInputRef.current?.click()}
                onToolSelect={handleToolSelect}
                activeTools={activeTools}
              />

              {/* Input */}
              <input
                id="chat-input"
                placeholder="Ask anything…"
                className="flex-1 bg-transparent text-[15px] outline-none text-white placeholder:text-gray-400 py-2"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                disabled={isLoadingHistory}
              />

              {/* Image Attach button */}
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-10 w-10 rounded-full flex-shrink-0 text-muted-foreground hover:text-foreground hover:bg-white/10 transition-colors"
                onClick={() => hiddenImageInputRef.current?.click()}
              >
                <ImagePlus size={18} />
              </Button>

              {/* Mic button */}
              <Button variant="ghost" size="icon" className="h-10 w-10 rounded-full flex-shrink-0 text-muted-foreground hover:text-foreground hover:bg-white/10 transition-colors">
                <Mic size={20} />
              </Button>

              {/* Send */}
              <Button
                id="chat-send-btn"
                size="icon"
                className="h-10 w-10 rounded-full bg-white hover:bg-gray-200 text-black shadow-lg transition-transform hover:scale-105 active:scale-95 flex-shrink-0"
                onClick={handleSend}
                disabled={isLoading || isLoadingHistory || (!input.trim() && imageAttachments.length === 0)}
              >
                <Send size={18} />
              </Button>
              </div>
            </div>
            
            <p className="text-center text-xs text-muted-foreground mt-3 opacity-60 font-medium pb-2">
              Memory · RAG · Web Search · Tool Calling
            </p>
          </div>
        </div>
      </SidebarInset>

      {/* Settings Modal */}
      <SettingsModal
        open={isSettingsOpen}
        onClose={() => setSettingsOpen(false)}
        onClearHistory={handleClearHistory}
        settings={appSettings}
        onSettingsChange={setAppSettings}
      />
    </SidebarProvider>
  );
}
