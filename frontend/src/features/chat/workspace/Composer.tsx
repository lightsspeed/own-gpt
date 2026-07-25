import { forwardRef, type KeyboardEvent, useState } from 'react';
import { cn } from '@/lib/utils';

export interface ComposerProps {
  input: string;
  setInput: (value: string) => void;
  onSend: () => void;
  onStop?: () => void;
  isLoading?: boolean;
  disabled?: boolean;
  placeholder?: string;
  kbEnabled?: boolean;
  webEnabled?: boolean;
  onToggleKb?: () => void;
  onToggleWeb?: () => void;
}

export const Composer = forwardRef<HTMLDivElement, ComposerProps>(
  (
    {
      input,
      setInput,
      onSend,
      onStop,
      isLoading,
      disabled,
      placeholder = 'Ask anything…',
      kbEnabled = true,
      webEnabled = true,
      onToggleKb,
      onToggleWeb,
    },
    ref,
  ) => {
    const [focused, setFocused] = useState(false);

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!isLoading) onSend();
      }
      if (e.key === 'Enter' && e.shiftKey) {
      }
    };

    return (
      <div ref={ref} className="border-t border-border bg-canvas px-4 pb-3 pt-3">
        <div className="mx-auto max-w-[800px]">
          <div
            className={cn(
              'relative flex items-end gap-2 rounded-[16px] border bg-surface px-4 py-3 transition-all duration-200',
              focused
                ? 'border-accent/40 shadow-[0_0_0_1px_rgba(59,130,246,0.15),0_4px_20px_rgba(0,0,0,0.3)]'
                : 'border-border shadow-sm',
            )}
          >
            {/* Left side — tool menu trigger */}
            <button
              type="button"
              disabled={disabled || isLoading}
              className="mb-[3px] flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-text-secondary hover:bg-hover hover:text-text-primary disabled:opacity-30 disabled:pointer-events-none transition-colors"
              title="Add tools"
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>

            {/* Input area */}
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder={placeholder}
              disabled={disabled || isLoading}
              rows={1}
              className="flex-1 resize-none bg-transparent text-body leading-6 text-text-primary placeholder:text-text-disabled outline-none py-0"
              style={{ minHeight: '1.5rem', maxHeight: '6rem' }}
            />

            {/* Right side — grouped controls */}
            <div className="flex shrink-0 items-center gap-1">
              {/* Tool toggles as pills */}
              <ToolToggle
                icon={
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" />
                  </svg>
                }
                label="KB"
                active={kbEnabled}
                onClick={onToggleKb}
                disabled={disabled || isLoading}
              />
              <ToolToggle
                icon={
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                  </svg>
                }
                label="Web"
                active={webEnabled}
                onClick={onToggleWeb}
                disabled={disabled || isLoading}
              />

              {/* Send / Stop button */}
              <div className="ml-1">
                {isLoading ? (
                  <button
                    onClick={onStop}
                    disabled={disabled}
                    className="flex h-9 w-9 items-center justify-center rounded-lg bg-danger text-white hover:brightness-110 active:scale-[0.95] transition-all"
                    title="Stop"
                  >
                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                      <rect x="6" y="6" width="12" height="12" rx="2" />
                    </svg>
                  </button>
                ) : (
                  <button
                    onClick={onSend}
                    disabled={disabled || !input.trim()}
                    className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-white hover:brightness-110 active:scale-[0.95] disabled:opacity-30 disabled:pointer-events-none transition-all"
                    title="Send"
                  >
                    <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 12h14M12 5l7 7-7 7" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  },
);
Composer.displayName = 'Composer';

/* ── small pill toggle ───────────────────────────────────── */
function ToolToggle({
  icon,
  label,
  active,
  onClick,
  disabled,
}: {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick?: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'flex h-7 items-center gap-1 rounded-full px-2.5 text-[12px] font-medium transition-all',
        'disabled:pointer-events-none disabled:opacity-30',
        active
          ? 'bg-accent/12 text-accent hover:bg-accent/20'
          : 'text-text-secondary hover:bg-hover hover:text-text-primary',
      )}
      title={label}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}
