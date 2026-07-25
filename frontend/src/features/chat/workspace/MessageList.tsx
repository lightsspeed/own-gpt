import { forwardRef, type ReactNode } from 'react';

export interface MessageListProps {
  children: ReactNode;
  bottomRef: React.RefObject<HTMLDivElement | null>;
}

export const MessageList = forwardRef<HTMLDivElement, MessageListProps>(
  ({ children, bottomRef }, ref) => {
    return (
      <div
        ref={ref}
        className="flex-1 overflow-y-auto px-4 py-6"
      >
        <div className="mx-auto max-w-[800px]">
          {children}
        </div>
        <div ref={bottomRef} />
      </div>
    );
  }
);
MessageList.displayName = 'MessageList';
