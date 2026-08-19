/* Mirrors legacy ChatMessage types for compatibility */
interface ToolCall {
  name: string;
  status: 'calling' | 'done';
}

export interface ResourceItem {
  type: 'web' | 'file' | 'knowledge';
  title: string;
  url?: string;
  snippet?: string;
  // V3 Phase 5: citation transparency fields
  document_id?: string | null;
  chunk_index?: number | null;
  page?: number | null;
  section?: string | null;
  confidence_label?: 'high' | 'medium' | 'low' | 'no_evidence' | null;
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

export interface CitationCheck {
  valid: boolean
  cited: number
  required: number
  unique_chunks: number
  total_uses: number
  warnings: string[]
  reason: string
}

export interface ClaimItem {
  id: string
  text: string
  supported: boolean
  best_score: number
  threshold: number
  best_chunk_idx?: number
  document?: string
}

export interface ClaimValidation {
  valid: boolean
  total: number
  unsupported: number
  claims: ClaimItem[]
}

export interface MessageData {
  id: string;
  role: 'user' | 'assistant' | 'tool_event';
  content: string;
  status?: string;
  tool?: ToolCall;
  timestamp?: Date;
  resources?: ResourceItem[];
  evidence?: EvidenceItem[];
  artifacts?: Artifact[];
  images?: string[];
  feedback?: 'liked' | 'disliked' | null;
  usedTools?: string[];
  recordId?: string;
  answerMode?: 'grounded' | 'hybrid' | 'synthesis' | 'web' | 'no_evidence';
  answerModeMetadata?: {
    chunk_count: number;
    doc_count: number;
    confidence: number;
    retrieval_method: string;
    retrieved_count?: number;  // V3 Phase 5: how many chunks were retrieved before reranking
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
  project_id?: string | null;
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
]

export type ConfidenceLabel = 'high' | 'medium' | 'low' | 'no_evidence';

export type RetrievalMethod = 'vector' | 'bm25' | 'hybrid' | 'web' | 'memory' | 'none';

export interface EvidenceItem {
  id: string;
  title: string;
  source_type: 'knowledge' | 'web' | 'memory' | 'file';
  url?: string | null;
  chunk?: string | null;
  confidence_label: ConfidenceLabel;
  retrieval_method: RetrievalMethod;
  chunk_index?: number | null;
  total_chunks?: number | null;
  document_id?: string | null;
  metadata?: Record<string, unknown>;
  raw_score?: number | null;
  reranker_score?: number | null;
}

export interface EvidenceBundle {
  items: EvidenceItem[];
  answer_mode: string;
}

export const CONFIDENCE_LABELS: Record<ConfidenceLabel, { label: string; color: string }> = {
  high: { label: 'High Confidence', color: 'text-success' },
  medium: { label: 'Strong Match', color: 'text-primary' },
  low: { label: 'Low Confidence', color: 'text-warning' },
  no_evidence: { label: 'No Evidence', color: 'text-muted-foreground/50' },
};

export const RETRIEVAL_LABELS: Record<RetrievalMethod, { label: string; color: string }> = {
  hybrid: { label: 'Hybrid', color: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  vector: { label: 'Vector', color: 'bg-purple-500/10 text-purple-400 border-purple-500/20' },
  bm25: { label: 'BM25', color: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
  web: { label: 'Web', color: 'bg-sky-500/10 text-sky-400 border-sky-500/20' },
  memory: { label: 'Memory', color: 'bg-rose-500/10 text-rose-400 border-rose-500/20' },
  none: { label: 'None', color: 'bg-muted/10 text-muted-foreground/50 border-border/30' },
};

export type PipelineStageStatus = 'waiting' | 'active' | 'done';

export interface PipelineStage {
  id: string;
  label: string;
  status: PipelineStageStatus;
  startedAt?: number;
  elapsedMs?: number;
}
