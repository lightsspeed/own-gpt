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

export interface MessageData {
  id: string;
  role: 'user' | 'assistant' | 'tool_event';
  content: string;
  tool?: ToolCall;
  timestamp?: Date;
  resources?: ResourceItem[];
  images?: string[];
  feedback?: 'liked' | 'disliked' | null;
  answerMode?: 'grounded' | 'hybrid' | 'synthesis' | 'web' | 'no_evidence';
  answerModeMetadata?: {
    chunk_count: number;
    doc_count: number;
    confidence: number;
    retrieval_method: string;
  };
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

export interface ToolInfo {
  name: string;
  label: string;
  icon: React.ReactNode;
  color: string;
  desc: string;
}

export type PipelineStageStatus = 'waiting' | 'active' | 'done';

export interface PipelineStage {
  id: string;
  label: string;
  status: PipelineStageStatus;
  startedAt?: number;
  elapsedMs?: number;
}
