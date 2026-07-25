import { useState } from 'react';
import { cn } from '@/lib/utils';

export interface MessageActionsProps {
  role: 'user' | 'assistant';
  content: string;
  feedback?: 'liked' | 'disliked' | null;
  onCopy?: () => void;
  onEdit?: () => void;
  onFeedback?: (type: 'liked' | 'disliked') => void;
  className?: string;
}

export function MessageActions({ role, content, feedback, onCopy, onEdit, onFeedback, className }: MessageActionsProps) {
  const [copied, setCopied] = useState(false);
  const [justLiked, setJustLiked] = useState<'liked' | 'disliked' | null>(null);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    onCopy?.();
  };

  const handleFeedback = (type: 'liked' | 'disliked') => {
    onFeedback?.(type);
  };

  return (
    <div className={cn(
      'flex items-center gap-0.5',
      className,
    )}>
      {/* Copy */}
      <ActionBtn
        icon={
          copied ? (
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          )
        }
        label={copied ? 'Copied' : 'Copy'}
        active={copied}
        onClick={handleCopy}
      />

      {/* Edit — user only */}
      {role === 'user' && onEdit && (
        <ActionBtn
          icon={
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
            </svg>
          }
          label="Edit"
          onClick={onEdit}
        />
      )}

      {/* Feedback — assistant only */}
      {role === 'assistant' && onFeedback && (
        <>
          <div className="mx-1 h-4 w-px bg-border" />
          <ActionBtn
            icon={
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M7 10v12" /><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z" />
              </svg>
            }
            label="Like"
            active={feedback === 'liked'}
            onClick={() => handleFeedback('liked')}
          />
          <ActionBtn
            icon={
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 14V2" /><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22h0a3.13 3.13 0 0 1-3-3.88Z" />
              </svg>
            }
            label="Dislike"
            active={feedback === 'disliked'}
            onClick={() => handleFeedback('disliked')}
          />
        </>
      )}
    </div>
  );
}

/* ── Small icon action button ── */
function ActionBtn({
  icon,
  label,
  active,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick: () => void;
}) {
  const [clicked, setClicked] = useState(false);

  return (
    <button
      onClick={() => {
        onClick();
        setClicked(true);
        setTimeout(() => setClicked(false), 600);
      }}
      title={label}
      className={cn(
        'flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] font-medium transition-all',
        active
          ? 'text-accent'
          : clicked
            ? 'text-text-secondary'
            : 'text-text-disabled hover:text-text-secondary hover:bg-hover',
      )}
    >
      {icon}
    </button>
  );
}
