import { MessageMarkdown } from './MessageMarkdown';
import { cn } from '@/lib/utils';

export interface MessageContentProps {
  role: 'user' | 'assistant';
  content: string;
  images?: string[];
  className?: string;
}

export function MessageContent({ role, content, images, className }: MessageContentProps) {
  const isUser = role === 'user';

  return (
    <div className={cn('space-y-3', className)}>
      {/* Image attachments */}
      {images && images.length > 0 && (
        <div className={cn('flex flex-wrap gap-2', isUser && 'justify-end')}>
          {images.map((src, i) => (
            <img
              key={i}
              src={src}
              alt={`attachment-${i}`}
              className="max-w-[200px] max-h-[200px] rounded-2xl object-cover border border-border shadow-sm"
            />
          ))}
        </div>
      )}

      {/* Text content */}
      {content && (
        isUser ? (
          <div className="inline-block max-w-[85%] rounded-2xl bg-elevated px-5 py-3 text-body text-text-primary leading-relaxed border border-border shadow-sm">
            {content}
          </div>
        ) : (
          <MessageMarkdown content={content} />
        )
      )}
    </div>
  );
}
