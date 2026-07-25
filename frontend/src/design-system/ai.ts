/* ------------------------------------------------------------------ */
/*  AI Language Token System                                           */
/*  Single source of truth for AI-specific visual language.             */
/*  Every answer mode, pipeline stage, tool status, and retrieval       */
/*  method is defined here, not sprinkled across components.           */
/* ------------------------------------------------------------------ */

import { semantic } from './semantic';

/* ── Answer Modes ───────────────────────────────────── */
export const answerModes = {
  grounded: {
    label: 'Grounded',
    color: semantic.answerMode.grounded,
    bg:    semantic.answerModeBg.grounded,
    icon:  'FileText',
    description: 'Answer is directly supported by source documents.',
    order: 0,
  },
  hybrid: {
    label: 'Hybrid',
    color: semantic.answerMode.hybrid,
    bg:    semantic.answerModeBg.hybrid,
    icon:  'Puzzle',
    description: 'Answer combines retrieved knowledge with model reasoning.',
    order: 1,
  },
  synthesis: {
    label: 'Synthesis',
    color: semantic.answerMode.synthesis,
    bg:    semantic.answerModeBg.synthesis,
    icon:  'Sparkles',
    description: 'Answer is synthesized across multiple sources without direct evidence.',
    order: 2,
  },
  no_evidence: {
    label: 'No Evidence',
    color: semantic.answerMode.noEvidence,
    bg:    semantic.answerModeBg.noEvidence,
    icon:  'Lightbulb',
    description: 'Answer has no retrievable evidence — based on model knowledge.',
    order: 3,
  },
  web: {
    label: 'Web',
    color: semantic.answerMode.web,
    bg:    semantic.answerModeBg.web,
    icon:  'Globe',
    description: 'Answer generated from live web search results.',
    order: 2,
  },
} as const;

export type AnswerMode = keyof typeof answerModes;

/* ── Pipeline Stages ───────────────────────────────── */
export const pipelineStages = {
  thinking:   { label: 'Thinking',   icon: 'Loader2',  color: semantic.text.secondary },
  routing:    { label: 'Routed',     icon: 'GitFork',  color: semantic.accent },
  retrieving: { label: 'Retrieving', icon: 'Search',   color: semantic.info },
  reranking:  { label: 'Reranking',  icon: 'ArrowUpDown', color: semantic.warning },
  generating: { label: 'Generating', icon: 'Pen',      color: semantic.success },
  complete:   { label: 'Complete',   icon: 'Check',    color: semantic.success },
  failed:     { label: 'Failed',     icon: 'X',        color: semantic.danger },
} as const;

export type PipelineStage = keyof typeof pipelineStages;

/* ── Tool / Agent Status ───────────────────────────── */
export const toolStatuses = {
  idle:     { label: 'Idle',     icon: 'Circle',          color: semantic.text.disabled },
  running:  { label: 'Running',  icon: 'Loader2',         color: semantic.accent },
  success:  { label: 'Success',  icon: 'CheckCircle2',    color: semantic.success },
  failed:   { label: 'Failed',   icon: 'XCircle',         color: semantic.danger },
  waiting:  { label: 'Waiting',  icon: 'Clock',           color: semantic.warning },
} as const;

export type ToolStatus = keyof typeof toolStatuses;

/* ── Retrieval Methods ─────────────────────────────── */
export const retrievalMethods = {
  none:   { label: 'None',    short: '—' },
  vector: { label: 'Vector',  short: 'VS' },
  bm25:   { label: 'BM25',   short: 'BM' },
  hybrid: { label: 'Hybrid',  short: 'HB' },
} as const;

export type RetrievalMethod = keyof typeof retrievalMethods;

/* ── Evidence family metadata ──────────────────────── */
export const evidenceFamily = {
  answerMode: 'answer-mode',
  sources:    'sources',
  debug:      'debug',
  timeline:   'activity-timeline',
} as const;

export type EvidenceFamily = keyof typeof evidenceFamily;

/* ── Visual helpers ────────────────────────────────── */
/** Get Tailwind text color class for an answer mode */
export function answerModeText(mode: AnswerMode): string {
  const map: Record<AnswerMode, string> = {
    grounded:    'text-success',
    hybrid:      'text-info',
    synthesis:   'text-warning',
    web:         'text-accent',
    no_evidence: 'text-text-disabled',
  };
  return map[mode];
}

/** Get Tailwind background class for an answer mode */
export function answerModeBg(mode: AnswerMode): string {
  const map: Record<AnswerMode, string> = {
    grounded:    'bg-successSoft',
    hybrid:      'bg-infoSoft',
    synthesis:   'bg-warningSoft',
    web:         'bg-accent/10',
    no_evidence: 'bg-elevated',
  };
  return map[mode];
}
