/* Mirrors legacy ChatMessage types for compatibility */
interface ToolCall {
  name: string;
  status: 'calling' | 'done';
}

export interface ResourceItem {
  type: 'web' | 'file';
  title: string;
  url?: string;
  snippet?: string;
}

export interface ArtifactAction {
  label: string;
  href?: string;
}

export type ArtifactType = 'finding' | 'recommendation' | 'evidence' | 'experiment' | 'report' | 'configuration';

export interface Artifact {
  id: string;
  type: ArtifactType;
  title: string;
  description: string;
  severity?: 'low' | 'medium' | 'high' | 'critical';
  confidence?: number;
  status?: string;
  source?: string;
  createdAt: string;
  metadata?: Record<string, string>;
  actions: ArtifactAction[];
}

export interface MessageData {
  id: string;
  role: 'user' | 'assistant' | 'tool_event';
  content: string;
  tool?: ToolCall;
  timestamp?: Date;
  resources?: ResourceItem[];
  artifacts?: Artifact[];
  images?: string[];
  feedback?: 'liked' | 'disliked' | null;
  usedTools?: string[];
  answerMode?: 'grounded' | 'hybrid' | 'synthesis' | 'web' | 'no_evidence';
  answerModeMetadata?: {
    chunk_count: number;
    doc_count: number;
    confidence: number;
    retrieval_method: string;
  };
}

export type ContextCategory = 'environment' | 'service' | 'artifact' | 'experiment' | 'knowledge' | 'custom' | 'timeframe';

export interface ContextItem {
  id: string;
  category: ContextCategory;
  label: string;
  value: string;
  color?: string;
}

export interface ConversationContext {
  items: ContextItem[];
}

export interface AttachmentFile {
  id: string;
  name: string;
  size: number;
  type: string;
  url?: string;
  preview?: string;
  status: 'pending' | 'uploading' | 'uploaded' | 'error';
  progress: number;
  error?: string;
}

export interface UploadedFile {
  name: string;
  chunks: number;
  type: string;
}

export interface ChatSession {
  id: string;
  title: string;
  is_pinned?: boolean;
  created_at?: string;
  updated_at?: string;
  message_count?: number;
  last_answer_mode?: 'grounded' | 'hybrid' | 'synthesis' | 'web' | 'no_evidence';
}

export type ToolMode = 'auto' | 'manual' | 'disabled';

export interface ToolInfo {
  name: string;
  label: string;
  icon: React.ReactNode;
  color: string;
  desc: string;
  category: 'knowledge' | 'analysis' | 'generation' | 'external';
  enabled: boolean;
  mode: ToolMode;
}

export const DEFAULT_TOOLS: ToolInfo[] = [
  { name: 'web_search', label: 'Web Search', icon: '🌐', color: 'text-sky-400', desc: 'Search the web for real-time information', category: 'knowledge', enabled: true, mode: 'auto' },
  { name: 'knowledge_base', label: 'Knowledge Base', icon: '📚', color: 'text-blue-400', desc: 'Retrieve information from connected corpora', category: 'knowledge', enabled: true, mode: 'auto' },
  { name: 'calculator', label: 'Calculator', icon: '🧮', color: 'text-emerald-400', desc: 'Perform mathematical calculations', category: 'analysis', enabled: false, mode: 'manual' },
  { name: 'code_interpreter', label: 'Code Interpreter', icon: '💻', color: 'text-purple-400', desc: 'Execute code snippets for analysis', category: 'analysis', enabled: false, mode: 'manual' },
  { name: 'image_analysis', label: 'Image Analysis', icon: '📷', color: 'text-amber-400', desc: 'Analyze uploaded images', category: 'analysis', enabled: false, mode: 'manual' },
  { name: 'memory', label: 'Memory', icon: '🧠', color: 'text-rose-400', desc: 'Recall information from past conversations', category: 'knowledge', enabled: false, mode: 'auto' },
]

export type PipelineStageStatus = 'waiting' | 'active' | 'done';

export interface PipelineStage {
  id: string;
  label: string;
  status: PipelineStageStatus;
  startedAt?: number;
  elapsedMs?: number;
}
