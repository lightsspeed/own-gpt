import { useState, useCallback, useRef, useEffect } from 'react';
import { ArrowLeft, PanelRight, BookOpen } from 'lucide-react';
import { PdfViewer } from './PdfViewer';
import { DocumentChat } from './DocumentChat';

const CHAT_DEFAULT_WIDTH = 320;
const CHAT_MIN_WIDTH = 280;
const CHAT_MAX_WIDTH = 520;

interface DocumentWorkspaceProps {
  filename: string;
  onBack: () => void;
}

export function DocumentWorkspace({ filename, onBack }: DocumentWorkspaceProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [showChat, setShowChat] = useState(true);
  const [chatWidth, setChatWidth] = useState(CHAT_DEFAULT_WIDTH);
  const dragRef = useRef<{ startX: number; startW: number } | null>(null);

  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  const onResizeMove = useCallback((e: PointerEvent) => {
    if (!dragRef.current) return;
    const delta = dragRef.current.startX - e.clientX;
    const next = Math.min(CHAT_MAX_WIDTH, Math.max(CHAT_MIN_WIDTH, dragRef.current.startW + delta));
    setChatWidth(next);
  }, []);

  const onResizeEnd = useCallback(() => {
    dragRef.current = null;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    window.removeEventListener('pointermove', onResizeMove);
    window.removeEventListener('pointerup', onResizeEnd);
  }, [onResizeMove]);

  useEffect(() => onResizeEnd, [onResizeEnd]);

  const startResize = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    dragRef.current = { startX: e.clientX, startW: chatWidth };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', onResizeMove);
    window.addEventListener('pointerup', onResizeEnd);
  }, [chatWidth, onResizeMove, onResizeEnd]);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-canvas">
      {/* Top bar */}
      <div className="shrink-0 flex items-center justify-between px-4 py-2.5 border-b border-border/60 bg-elevated/40">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-small text-muted-foreground/60 hover:text-foreground transition-colors px-2 py-1 rounded-lg hover:bg-hover"
          >
            <ArrowLeft size={14} />
            Back to Knowledge Base
          </button>
          <div className="w-px h-4 bg-border/40" />
          <div className="flex items-center gap-2 min-w-0">
            <BookOpen size={15} className="text-primary shrink-0" />
            <span className="text-small text-foreground font-medium truncate max-w-[300px]">{filename}</span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setShowChat(s => !s)}
            className={`p-1.5 rounded-lg transition-colors ${showChat ? 'bg-primary/10 text-primary' : 'text-muted-foreground/40 hover:text-foreground hover:bg-hover'}`}
            title="Toggle AI chat"
          >
            <PanelRight size={15} />
          </button>
        </div>
      </div>

      {/* 2-panel body */}
      <div className="flex-1 flex overflow-hidden">
        {/* PDF viewer */}
        <div className="flex-1 min-w-0 overflow-hidden">
          <PdfViewer
            filename={filename}
            onPageChange={handlePageChange}
          />
        </div>

        {/* AI chat (resizable) */}
        {showChat && (
          <>
            <div
              onPointerDown={startResize}
              className="w-[3px] shrink-0 cursor-col-resize hover:bg-primary/30 active:bg-primary/50 transition-colors bg-border/20"
              title="Drag to resize chat"
            />
            <div style={{ width: chatWidth }} className="shrink-0 overflow-hidden">
              <DocumentChat
                filename={filename}
                currentPage={currentPage}
                onClose={() => setShowChat(false)}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
