# Component Specifications

> Every UI component has a contract: purpose, props, states, behavior, and accessibility requirements.
> Rebuild order: **AppShell → Page layout → Interactive elements → Content components**.

---

## Template

Every component below follows this structure:

```
## ComponentName

**Purpose:** One sentence.

**Props:** TypeScript interface.

**States:** [loading | empty | error | hover | focus | active | disabled | streaming]

**Keyboard:** Tab order, Enter/Space activation, Escape close.

**Animation:** Enter, exit, hover, focus, state transitions.

**Accessibility:** ARIA roles, labels, live regions, focus management.

**Spacing:** Padding, margin, gap values from design tokens (never magic numbers).

**Variants:** Desktop | Tablet | Mobile differences.
```

---

## P0 components

### AppShell

**Purpose:** Root layout composing Header, Sidebar, and routed content area.

**Props:**
```ts
interface AppShellProps {
  children: React.ReactNode;
  defaultSidebarOpen?: boolean;
}
```

**States:** None (structural).

**Keyboard:** `Ctrl+B` toggles sidebar. Escape closes overlay sidebar.

**Animation:** Sidebar open/close slides 200ms. Content area adjusts width without animation.

**Accessibility:** `aria-controls` on sidebar toggle. Main content is `role="main"`.

**Spacing:** No padding at this level (delegates to children).

**Variants:**
- Desktop: sidebar always visible, 260px width
- Tablet: sidebar overlay, backdrop blur on overlay
- Mobile: sidebar overlay, full-width

---

### Sidebar

**Purpose:** Navigation hub — new chat, history list, bottom links.

**Props:**
```ts
interface SidebarProps {
  sessions: Session[];
  activeSessionId: string | null;
  onNewChat: () => void;
  onSelectSession: (id: string) => void;
  onDeleteSession: (id: string) => void;
  onRenameSession: (id: string, title: string) => void;
  onTogglePin: (id: string) => void;
  onOpenKnowledgeBase: () => void;
  onOpenSettings: () => void;
  isOpen: boolean;
  onClose?: () => void;
}
```

**States:**
- Normal: session list with items
- Empty: "No saved chats" message (caption, italic, muted)
- Loading: skeleton lines (pulse animation)
- Editing: inline text input replacing session title

**Keyboard:**
- Arrow keys navigate session list
- Enter on session selects it
- Delete key with confirmation deletes session
- Escape cancels inline edit

**Animation:** None for desktop sidebar. Slide 200ms for overlay variant.

**Accessibility:**
- `role="navigation"` with `aria-label="Chat history"`
- Session list is `role="listbox"` with `aria-activedescendant`
- New Chat button has `aria-label="Start new chat"`

**Spacing:**
- Section gap: 8px
- Item stack gap: 4px
- Item padding: 8px 12px
- Active item bg: `--accent`
- Width: 260px

**Variants:**
- Desktop: static, no border, same bg as page
- Tablet/Mobile: overlay with backdrop, close button

---

### Header

**Purpose:** Top bar with app identity, model badge, and status.

**Props:**
```ts
interface HeaderProps {
  modelName: string;
  messageCount: number;
  onToggleSidebar: () => void;
  onOpenSettings: () => void;
  onExportChat?: () => void;
}
```

**States:** None (static).

**Keyboard:** Sidebar toggle is first tab stop.

**Animation:** None.

**Accessibility:**
- `role="banner"`
- Sidebar toggle has `aria-label="Toggle sidebar"`
- Settings button has `aria-label="Open settings"`
- Live indicator uses `aria-live="polite"` (updates rarely)

**Spacing:**
- Height: 48px
- Padding: 0 16px
- Glass panel: `glass-panel` class

**Variants:** None (consistent across breakpoints).

---

### ChatLayout

**Purpose:** Scrollable message list with auto-scroll, loading state, and empty state.

**Props:**
```ts
interface ChatLayoutProps {
  messages: MessageData[];
  isLoading: boolean;
  isStreaming: boolean;
  streamingMessageId: string | null;
  onEdit: (id: string) => void;
  onFeedback: (id: string, feedback: 'liked' | 'disliked' | null) => void;
  emptyState?: React.ReactNode;
}
```

**States:**
- Loading: skeleton placeholder lines
- Empty: welcome screen (display text + suggestion chips)
- Messages: chat message list
- Streaming: last message shows fade-in animation

**Keyboard:** Focus trap not needed (no modal behavior).

**Animation:**
- New messages fade in 200ms
- Streaming text fades in 100ms per chunk
- Auto-scroll is smooth (`scroll-behavior: smooth` or manual scrollIntoView)

**Accessibility:**
- `role="log"` with `aria-live="polite"` for streaming content
- `aria-atomic="false"` so only new text is announced
- Each message has `aria-label="[role] message: [preview]"`

**Spacing:**
- Max-width: 800px, centered
- Padding top: 80px (to clear header)
- Padding bottom: 200px (to clear input bar)
- Message stack gap: 24px

**Variants:**
- Mobile: max-width 95vw, reduced padding

---

### InputBar

**Purpose:** Message composer with attachments, voice, and send.

**Props:**
```ts
interface InputBarProps {
  onSend: (text: string, images: ImageAttachment[]) => void;
  onFileUpload: (file: File) => void;
  onImageAttach: (files: File[]) => void;
  disabled?: boolean;
  placeholder?: string;
}
```

**States:**
- Normal: empty input, ghost icons visible
- Typing: input has text, send button becomes primary active
- Disabled: loading state, all inputs grayed
- Uploading: progress banner shown above input

**Keyboard:**
- Enter sends (without Shift)
- Shift+Enter inserts newline
- Escape clears input
- Tab moves to send button

**Animation:**
- Send button scales 0.98 on click, 150ms
- Progress banner slides down 200ms
- Focus glow on entire bar: 150ms

**Accessibility:**
- Text input has `role="textbox"` with `aria-multiline="true"`
- Send button has `aria-label="Send message"`
- Attachment button has `aria-label="Attach file"`
- `aria-disabled` on all controls when disabled

**Spacing:**
- Max-width: 800px, centered, fixed bottom
- Padding: 12px 16px
- Border radius: 16px
- Glass panel with backdrop blur

**Variants:** Mobile: reduce horizontal padding to 12px.

---

## P1 components

### ChatMessage

**Purpose:** Renders a single chat message (user or assistant) with metadata.

**Props:**
```ts
interface ChatMessageProps {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  resources?: ResourceItem[];
  answerMode?: AnswerMode;
  answerModeMetadata?: AnswerModeMetadata;
  timestamp?: Date;
  feedback?: 'liked' | 'disliked' | null;
  isStreaming?: boolean;
  onEdit?: (content: string) => void;
  onFeedback?: (id: string, feedback: 'liked' | 'disliked' | null) => void;
}
```

**States:**
- User message: right-aligned, secondary bg, no border
- Assistant message: left-aligned, no bg, no border
- Streaming: last assistant message with fade-in animation
- With metadata: mode badge + sources shown below content

**Keyboard:** Action buttons are tab-focusable.

**Animation:**
- New message: fade-in 200ms
- Streaming chunk: fade-in-up 100ms
- Mode badge appears after streaming: fade-in 200ms

**Accessibility:**
- `aria-label` includes role and first 80 chars of content
- Streaming uses `aria-live="polite"` on parent ChatLayout
- Action buttons have `aria-label` (no visible labels)

**Spacing:**
- Message gap: 24px
- Answer → metadata gap: 16px
- Sources section → mode badge gap: 12px
- User message max-width: 75%

**Variants:** None.

---

### AnswerModeBadge

**Purpose:** Displays how the answer was produced (grounded / hybrid / synthesis).

**Props:**
```ts
interface AnswerModeBadgeProps {
  mode: 'grounded' | 'hybrid' | 'synthesis' | 'no_evidence';
  metadata: {
    chunk_count: number;
    doc_count: number;
    confidence: number;
    retrieval_method: string;
  };
}
```

**States:**
- Grounded: blue, BookOpen icon
- Hybrid: purple, Puzzle icon
- Synthesis: amber, Lightbulb icon
- No evidence: hidden

**Keyboard:** Not interactive.

**Animation:** Fade-in 200ms after streaming completes.

**Accessibility:** `aria-label="Answer mode: [mode]. [chunks] chunks from [docs] documents."`

**Spacing:** `px-3 py-2`, `gap-1` between rows.

**Variants:** None.

---

### SourceCard

**Purpose:** A pill chip representing one source document or URL.

**Props:**
```ts
interface SourceCardProps {
  resource: ResourceItem;
}
```

**States:**
- Normal: pill chip with icon + truncated title
- Hover: slight lift + tooltip with content preview
- Web source: clickable (opens URL)

**Keyboard:** If web source, focusable and Enter opens URL.

**Animation:**
- Hover: 150ms `translateY(-1px)` + shadow
- Tooltip: fade in 150ms, 300ms delay before show

**Accessibility:**
- `aria-label="Source: [title]"` with optional "opens in new tab"
- Tooltip is not keyboard-trapping

**Spacing:**
- `px-2.5 py-1.5`, `gap-1.5` icon to text
- `rounded-full`, `max-w-[220px]` with truncation
- Font: `small` (13px)

---

### Toolbar (action buttons)

**Purpose:** Copy, like, dislike actions on assistant messages.

**Props:**
```ts
interface ToolbarProps {
  content: string;
  feedback?: 'liked' | 'disliked' | null;
  onFeedback?: (fb: 'liked' | 'disliked' | null) => void;
}
```

**States:**
- Hidden: not visible until message hover
- Visible: subtle opacity, icons + labels
- Liked: thumb up filled, blue
- Disliked: thumb down filled, blue

**Keyboard:** All buttons focusable, Tab order: Copy → Like → Dislike.

**Animation:**
- Appear: 150ms fade on parent hover
- Click: 100ms scale pulse
- Feedback toggle: 150ms icon color transition

**Accessibility:** Each button has `aria-label="Copy message"`, `"Like"`, `"Dislike"`. `aria-pressed` for feedback buttons.

**Spacing:** `gap-1` between buttons, `p-1.5` per button.

---

### DebugPanel

**Purpose:** Collapsible pipeline trace for developer transparency.

**Props:**
```ts
interface DebugPanelProps {
  metadata: AnswerModeMetadata;
  answerMode: string;
}
```

**States:**
- Collapsed: shows `▶ Why this answer?` toggle
- Expanded: key-value grid with retriever, chunks, documents, mode, confidence

**Keyboard:** Toggle is focusable, Enter/Space toggles, Escape collapses.

**Animation:**
- Expand: slide-down 200ms `ease-in-out`
- Chevron: rotate 90° 200ms
- Collapse: reverse

**Accessibility:**
- Toggle has `aria-expanded` and `aria-controls`
- Panel content has `role="region"` and `aria-label="Pipeline details"`
- `aria-hidden` on collapsed content

**Spacing:**
- Toggle: `caption` (12px), `gap-1`, `py-0.5`
- Expanded panel: `px-3 py-2`, `gap-1` between rows, `rounded-lg`

---

## P2 components

### KnowledgeBaseCard

**Purpose:** Document card in the Knowledge Base list.

**Props:**
```ts
interface KnowledgeBaseCardProps {
  filename: string;
  chunks: number;
  updatedAt: string;
  size: string;
  onDelete: () => void;
}
```

**States:** Normal, Hover (lift + shadow), Deleted (fade out).

**Keyboard:** Delete button focusable.

**Animation:** Hover: 150ms lift. Delete: 200ms fade-out.

**Spacing:** `rounded-xl`, `p-4`, `gap-3` icon to text.

---

### SettingsDialog

**Purpose:** Modal for app settings with tabbed sections.

**Props:**
```ts
interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
  settings: AppSettings;
  onSave: (settings: AppSettings) => void;
}
```

**States:** Open (scale-in), Closed.

**Keyboard:** Focus trap, Tab cycles within dialog, Escape closes.

**Animation:** Open: 200ms scale-in + fade. Close: 150ms fade-out.

**Accessibility:** `role="dialog"`, `aria-modal="true"`, focus first input on open.

---

### UploadProgress

**Purpose:** Animated progress banner for file upload stages.

**Props:**
```ts
interface UploadProgressProps {
  filename: string;
  stage: 'reading' | 'parsing' | 'chunking' | 'embedding' | 'done' | 'error';
  chunks?: number;
  onDismiss?: () => void;
}
```

**States:** Each stage shows a different icon (spinner → checkmark → error).

**Animation:** Stage transitions: 300ms fade. Done: 200ms checkmark scale. Auto-dismiss after 2.5s.

**Accessibility:** `aria-live="polite"`, `role="status"`.

---

## Component dependency graph

```
AppShell
├── Header
├── Sidebar
└── ChatLayout
    ├── ChatMessage
    │   ├── AnswerModeBadge
    │   ├── DebugPanel
    │   ├── SourceCard
    │   └── Toolbar
    └── InputBar

KnowledgeBase
└── KnowledgeBaseCard
    └── UploadProgress

SettingsDialog
```

- **P0** must be rebuilt first: AppShell → Header + Sidebar + ChatLayout + InputBar
- **P1** depends on P0 layout being correct: ChatMessage + AnswerModeBadge + SourceCard + Toolbar + DebugPanel
- **P2** can be rebuilt in parallel: KnowledgeBase, Settings, UploadProgress
- **P3** polished last: empty states, skeletons, toasts
