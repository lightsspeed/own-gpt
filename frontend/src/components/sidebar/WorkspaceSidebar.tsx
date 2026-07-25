import { useState, type ReactNode } from 'react';
import { Stack, Divider } from '@/components/layout';
import { cn } from '@/lib/utils';
import type { ChatSession } from '@/features/chat/types';

interface WorkspaceSidebarProps {
  sessions: ChatSession[];
  activeId: string | null;
  loading: boolean;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}

export function WorkspaceSidebar({
  sessions,
  activeId,
  loading,
  searchQuery,
  onSearchChange,
  onSelect,
  onNewChat,
  onRename,
  onDelete,
}: WorkspaceSidebarProps) {
  const filtered = searchQuery
    ? sessions.filter(s => s.title.toLowerCase().includes(searchQuery.toLowerCase()))
    : sessions;

  const displaySessions = filtered.sort((a, b) => {
    if (a.is_pinned && !b.is_pinned) return -1;
    if (!a.is_pinned && b.is_pinned) return 1;
    return (b.updated_at ?? '').localeCompare(a.updated_at ?? '');
  });

  return (
    <aside className="flex h-full w-[280px] flex-col border-r border-border bg-canvas">
      <div className="flex-1 overflow-y-auto px-3 py-4">

        {/* ═══════════ Section 1 — Workspace ═══════════ */}
        <Stack gap="sm" className="px-1">
          <button
            onClick={onNewChat}
            className="flex w-full items-center gap-3 rounded-xl bg-accent px-4 py-3 text-small font-medium text-white hover:brightness-110 active:scale-[0.98] transition-all"
          >
            <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
            New Chat
          </button>

          <div className="flex items-center gap-3 px-2 py-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/15">
              <span className="text-[13px] font-bold text-accent">OG</span>
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-small font-semibold text-text-primary">Own GPT</span>
              <span className="text-micro text-text-secondary">GPT-4o Mini</span>
            </div>
          </div>
        </Stack>

        <Divider spacing="md" />

        {/* ═══════════ Section 2 — AI Tools ═══════════ */}
        <div className="px-1">
          <SectionLabel>AI Tools</SectionLabel>
          <Stack gap="xs">
            <ToolItem icon={<BookIcon />} label="Knowledge Base" tooltip="Search uploaded documents" />
            <ToolItem icon={<GlobeIcon />} label="Web Search" tooltip="Search the internet" />
            <ToolItem icon={<HashtagIcon />} label="Social Media" tooltip="Monitor social channels" />

            <div className="my-1 border-t border-border/50" />

            <ToolItem icon={<FutureIcon />} label="Evaluation" muted tooltip="Coming soon" />
            <ToolItem icon={<FutureIcon />} label="Benchmarks" muted tooltip="Coming soon" />
          </Stack>
        </div>

        <Divider spacing="md" />

        {/* ═══════════ Section 3 — Recent Conversations ═══════════ */}
        <div className="px-1">
          <SectionLabel>Conversations</SectionLabel>

          <div className="relative mb-2">
            <svg className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-disabled pointer-events-none" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
            <input
              type="text"
              value={searchQuery}
              onChange={e => onSearchChange(e.target.value)}
              placeholder="Search conversations…"
              className="w-full rounded-lg border border-border bg-transparent py-1.5 pl-8 pr-3 text-small text-text-primary placeholder:text-text-disabled outline-none transition-colors focus:border-accent/40"
            />
          </div>

          {loading ? (
            <div className="space-y-2 px-3 py-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-8 animate-pulse rounded-lg bg-elevated" />
              ))}
            </div>
          ) : displaySessions.length === 0 ? (
            <p className="px-3 py-4 text-center text-small text-text-disabled">
              {searchQuery ? 'No matching conversations' : 'No conversations yet'}
            </p>
          ) : (
            <Stack gap="xs">
              {displaySessions.map(conv => (
                <ConversationItem
                  key={conv.id}
                  session={conv}
                  isActive={conv.id === activeId}
                  onSelect={() => onSelect(conv.id)}
                  onRename={onRename}
                  onDelete={onDelete}
                />
              ))}
            </Stack>
          )}
        </div>

        <Divider spacing="md" />

        {/* ═══════════ Section 4 — Workspace Status ═══════════ */}
        <div className="px-1">
          <SectionLabel>Knowledge Base</SectionLabel>
          <div className="rounded-lg border border-border bg-surface px-3 py-2.5 space-y-1">
            <div className="flex items-center gap-2 text-small text-text-secondary flex-wrap">
              <span className="font-medium text-text-primary tabular-nums">6,436</span> chunks
              <span className="text-text-disabled">·</span>
              <span className="font-medium text-text-primary">9</span> documents
            </div>
            <div className="flex items-center gap-2 text-small text-text-secondary flex-wrap">
              <span>Hybrid</span>
              <span className="text-text-disabled">·</span>
              <span className="truncate">text-embedding-3-small</span>
            </div>
            <div className="flex items-center gap-1.5 text-small">
              <span className="h-1.5 w-1.5 rounded-full bg-success" />
              <span className="text-success font-medium">Healthy</span>
            </div>
          </div>
        </div>
      </div>

      {/* ═══════════ Section 5 — Footer ═══════════ */}
      <div className="shrink-0 border-t border-border px-4 py-3">
        <div className="flex items-center justify-between">
          <FooterBtn label="Storage" />
          <FooterBtn label="Settings" />
          <FooterBtn label="About" />
        </div>
      </div>
    </aside>
  );
}

/* ────────────────────────────────────────────── */
/*  Sub-components                                */
/* ────────────────────────────────────────────── */

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <span className="mb-2 block px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-text-disabled">
      {children}
    </span>
  );
}

function ToolItem({ icon, label, muted, tooltip }: { icon: ReactNode; label: string; muted?: boolean; tooltip?: string }) {
  return (
    <button
      title={tooltip}
      className={cn(
        'group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-body transition-all',
        muted
          ? 'cursor-not-allowed text-text-disabled'
          : 'text-text-secondary hover:text-text-primary hover:bg-hover hover:translate-x-0.5',
      )}
    >
      <span className={cn('shrink-0', muted ? 'opacity-40' : '')}>{icon}</span>
      <span className={cn('truncate', muted ? 'text-text-disabled' : '')}>{label}</span>
      {muted && <span className="ml-auto text-micro text-text-disabled">Soon</span>}
    </button>
  );
}

function ConversationItem({
  session,
  isActive,
  onSelect,
}: {
  session: ChatSession;
  isActive: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        'group relative flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left transition-all',
        isActive ? 'bg-elevated' : 'hover:bg-hover hover:translate-x-0.5',
      )}
    >
      {isActive && (
        <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-accent" />
      )}

      <div className="flex-1 min-w-0 flex items-center gap-2">
        {session.is_pinned && (
          <svg className="h-3 w-3 shrink-0 text-accent/60" viewBox="0 0 24 24" fill="currentColor">
            <path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z" />
          </svg>
        )}
        <span className={cn(
          'truncate text-small',
          isActive ? 'font-semibold text-text-primary' : 'text-text-secondary group-hover:text-text-primary',
        )}>
          {session.title}
        </span>
      </div>
    </button>
  );
}

function FooterBtn({ label }: { label: string }) {
  return (
    <button className="rounded-md px-3 py-1.5 text-small text-text-secondary hover:text-text-primary hover:bg-hover hover:translate-x-0.5 transition-all">
      {label}
    </button>
  );
}

/* ── Inline SVG icons ── */
function BookIcon() { return (<svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" /><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></svg>); }
function GlobeIcon() { return (<svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" /></svg>); }
function HashtagIcon() { return (<svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 9h16M4 15h16M10 3L8 21M16 3l-2 18" /></svg>); }
function FutureIcon() { return (<svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" /></svg>); }
