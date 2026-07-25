import { useState, useRef, useEffect } from 'react';
import type { ChatSession } from '../types';

export interface ConversationToolbarProps {
  session: ChatSession | null;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  onTogglePin: (id: string) => void;
}

export function ConversationToolbar({ session, onRename, onDelete, onTogglePin }: ConversationToolbarProps) {
  const [editing, setEditing] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editing]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [menuOpen]);

  if (!session) return null;

  const handleStartRename = () => {
    setTitleDraft(session.title);
    setEditing(true);
    setMenuOpen(false);
  };

  const handleSubmitRename = () => {
    const trimmed = titleDraft.trim();
    if (trimmed && trimmed !== session.title) {
      onRename(session.id, trimmed);
    }
    setEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSubmitRename();
    if (e.key === 'Escape') setEditing(false);
  };

  return (
    <div className="flex items-center justify-between w-full px-4">
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-body text-text-primary font-medium whitespace-nowrap">ownGPT</span>
        <span className="text-caption text-text-secondary bg-elevated px-2 py-0.5 rounded-md shrink-0">GPT-4o Mini</span>

        {editing ? (
          <input
            ref={inputRef}
            value={titleDraft}
            onChange={e => setTitleDraft(e.target.value)}
            onBlur={handleSubmitRename}
            onKeyDown={handleKeyDown}
            className="ml-2 rounded border border-accent/40 bg-canvas px-2 py-0.5 text-small text-text-primary outline-none max-w-[200px]"
          />
        ) : (
          <span className="ml-2 truncate text-small text-text-secondary max-w-[200px]">{session.title}</span>
        )}
      </div>

      <div className="flex items-center gap-1">
        {session.is_pinned && (
          <svg className="h-3.5 w-3.5 text-accent" viewBox="0 0 24 24" fill="currentColor">
            <path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z" />
          </svg>
        )}

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="rounded-md p-1.5 text-text-secondary hover:text-text-primary hover:bg-hover transition-colors"
            title="Conversation actions"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="5" r="1" />
              <circle cx="12" cy="12" r="1" />
              <circle cx="12" cy="19" r="1" />
            </svg>
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 min-w-[160px] rounded-lg border border-border bg-surface py-1 shadow-lg z-50">
              <MenuBtn onClick={handleStartRename} label="Rename" />
              <MenuBtn onClick={() => { onTogglePin(session.id); setMenuOpen(false); }} label={session.is_pinned ? 'Unpin' : 'Pin'} />
              <MenuBtn onClick={() => { onDelete(session.id); setMenuOpen(false); }} label="Delete" danger />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MenuBtn({ onClick, label, danger }: { onClick: () => void; label: string; danger?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={`w-full px-3 py-1.5 text-left text-small transition-colors ${
        danger ? 'text-danger hover:bg-danger/10' : 'text-text-secondary hover:text-text-primary hover:bg-hover'
      }`}
    >
      {label}
    </button>
  );
}
