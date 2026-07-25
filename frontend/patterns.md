# UX Patterns & Interaction Playbook

> Standardized responses to common user scenarios.
> Every pattern has a rule, a rationale, and a concrete implementation.

---

## Principles

1. **Never leave the user wondering what happened.** Every action produces a visible result within 300ms.
2. **Errors are conversations, not dead ends.** Every error message includes what went wrong and what to do next.
3. **Progress is always visible.** Loading, streaming, uploading — the user always knows where they stand.
4. **Empty states are opportunities.** Every empty screen explains what belongs there and how to fill it.
5. **The AI is transparent.** The user can always see what the system is doing (thinking, retrieving, reasoning, answering).

---

## Loading patterns

### Rule

Never freeze the UI. Always show a progress indicator that communicates:
- **What** is happening (in human terms)
- **How long** it might take (relative, not absolute)
- **When** it's done

### Behaviors

| Context               | Indicator                    | Duration          |
|-----------------------|------------------------------|-------------------|
| Initial chat load     | Skeleton lines (2–3)          | Until loaded      |
| Sending message       | Streaming text immediately    | Instant           |
| Tool execution        | Event pill with bounce dots   | Until tool returns|
| File upload           | Progress banner with stages   | Until completed   |
| Knowledge Base list   | Skeleton cards (3)            | Until loaded      |
| Search (KB)           | Debounce 300ms + spinner      | Until results     |

### What to avoid

- ❌ Full-page spinners
- ❌ Indeterminate progress bars for known-length operations
- ❌ Frozen UI during streaming (messages should appear as they arrive)
- ❌ "Loading..." text without context

---

## Error patterns

### Rule

Every error message must answer three questions:

1. **What happened?** (human-readable, not technical)
2. **Why did it happen?** (one sentence cause)
3. **What can I do?** (actionable recovery)

### Hierarchy

| Severity | Style     | Placement      | Persistence      |
|----------|-----------|----------------|------------------|
| Fatal    | `danger`  | Inline banner  | Until dismissed  |
| Transient| `warning` | Toast           | Auto-dismiss 5s  |
| Recoverable | `warning` | Inline below control | Until fixed |
| Informational | `info` | Toast        | Auto-dismiss 3s  |

### Templates

```
API error:
  ⚠️ Connection lost
     We couldn't reach the server. Check your connection and try again.
     [Try Again] [Dismiss]

Upload error:
  ⚠️ Upload failed
     "terraform.pdf" couldn't be processed. The file might be corrupted.
     [Try Again] [Remove]

Validation error:
  ⚠️ Invalid file type
     Only PDF, DOCX, PPTX, CSV, XLSX, and HTML files are supported.
     [Choose Different File]
```

### What to avoid

- ❌ Technical error codes shown to users
- ❌ "An error occurred" without explanation
- ❌ Stack traces in the UI
- ❌ Errors that dismiss themselves without user action

---

## Success patterns

### Rule

Success feedback should be **proportional** to the action's significance.

| Action          | Feedback                      | Duration |
|-----------------|-------------------------------|----------|
| Copy message    | Icon swap (copy → checkmark) | 2s       |
| Like/dislike    | Icon fills + pulse           | 1s       |
| Upload file     | Progress reaches "Done"      | Persistent until dismissed |
| Save settings   | "Saved" toast                | 3s       |
| Delete session  | Item fades out + toast       | 3s       |
| New chat        | Focus moves to input         | Instant  |

### What to avoid

- ❌ Confetti / celebratory animations for routine actions
- ❌ Modal dialogs for success confirmation
- ❌ Success messages that block further action

---

## Empty patterns

### Rule

Every empty screen must answer:

1. **What is this place?** (title)
2. **Why is it empty?** (explanation)
3. **What should I do?** (action)

### Templates

```
Chat (no history):
  ┌──────────────────────────────┐
  │                              │
  │  Welcome to Own GPT          │
  │                              │
  │  Your personal AI assistant  │
  │  with persistent memory,     │
  │  knowledge base, and web     │
  │  search.                     │
  │                              │
  │  [Ask me anything...]        │
  │                              │
  │  "What is AWS CDK?"          │
  │  "Compare Kubernetes tools"  │
  │  "Summarize this document"   │
  │                              │
  └──────────────────────────────┘

Knowledge Base (no documents):
  ┌──────────────────────────────┐
  │                              │
  │  📄 No documents yet         │
  │                              │
  │  Upload PDFs, Word docs,     │
  │  spreadsheets, or HTML files │
  │  to build your knowledge     │
  │  base.                       │
  │                              │
  │  [Upload Document]           │
  │                              │
  └──────────────────────────────┘

Sidebar (no chat history):
  ┌──────────────────────────────┐
  │                              │
  │  No saved chats              │
  │                              │
  │  Your conversations will     │
  │  appear here automatically.  │
  │                              │
  └──────────────────────────────┘
```

### What to avoid

- ❌ Blank white/dark screens with no context
- ❌ "No data" without explanation
- ❌ Empty screens that don't offer an action

---

## AI interaction patterns

### Streaming response

```
User sends message
  → Input clears (instant)
  → Assistant message appears with blinking cursor (200ms)
  → Text streams in, chunk by chunk (fade-in-up 100ms)
  → When stream ends: cursor fades (500ms)
  → Mode badge fades in (200ms)
  → Sources fade in (200ms)
  → Action buttons appear on hover
```

### Tool execution

```
User asks a question requiring a tool
  → Assistant message placeholder appears
  → Tool event pill slides in: "🔍 Knowledge Base" with bounce dots
  → Tool completes: dots → checkmark
  → Multiple tools: pills stack vertically
  → After all tools: streaming response begins
```

### Clarification / no evidence

```
User asks something beyond corpus knowledge
  → Streaming response begins immediately
  → Mode badge: "LLM Synthesis · No supporting documents used"
  → Debug panel shows: retrieved = 0, confidence = N/A
  → No sources section
```

### Knowledge Base query

```
User references uploaded documents
  → Router detects RAG intent
  → Knowledge Base tool pill appears
  → Chunks retrieved (shown in debug panel)
  → FlashRank reranks (shown in debug panel)
  → Answer streams with Grounded or Hybrid badge
  → Sources show document chips
```

### Web search

```
User asks for current information
  → Router detects web intent
  → Web Search tool pill appears with globe icon
  → Tool returns results
  → Answer streams with synthesis badge
  → Sources show URL chips (clickable)
```

---

## Confirmation patterns

### Destructive actions

| Action         | Confirmation                   |
|----------------|--------------------------------|
| Delete session | Inline: "Delete?" [Yes] [No]  |
| Clear history  | Modal: "Clear all history? This cannot be undone." [Cancel] [Clear] |
| Delete document| Modal: "Delete terraform.pdf?" [Cancel] [Delete] |

### Principles

- Inline confirmation is preferred (less disruptive)
- Modals only for irreversible actions
- Destructive button is `danger` color, never primary
- Always provide an escape (Cancel, Escape key)

---

## Notification patterns

| Type      | Component    | Placement     | Duration    |
|-----------|-------------|---------------|-------------|
| Success   | Toast       | Bottom-right  | 3s auto     |
| Error     | Banner      | Top of context| Manual      |
| Warning   | Toast       | Bottom-right  | 5s auto     |
| Info      | Toast       | Bottom-right  | 3s auto     |
| Progress  | Banner      | Above input   | Until done  |

### What to avoid

- ❌ Notifications that cover content
- ❌ Multiple simultaneous toasts
- ❌ Toasts for actions the user already sees a result for (e.g., sending a message)

---

## Transition patterns

| Transition     | When                          | Animation       |
|----------------|-------------------------------|-----------------|
| New chat       | User clicks "New Chat"        | Messages fade out → empty state fades in (200ms) |
| Switch session | User clicks another session   | Messages fade out → loaded messages fade in (200ms) |
| Open modal     | User triggers settings/KB     | Backdrop fades in → modal scales in (200ms total) |
| Close modal    | User dismisses                | Modal scales out → backdrop fades out (150ms) |
| Sidebar open   | Overlay variant               | Panel slides in (200ms) |
| Sidebar close  | Overlay variant               | Panel slides out (200ms) |

---

## Form patterns

### Input validation

| Scenario                | Behavior                              |
|-------------------------|---------------------------------------|
| Required field empty    | Show error on blur: "This is required"|
| Invalid format          | Show error inline: "Enter a valid URL"|
| Too long                | Character counter, show at 90%        |
| File type unsupported   | Show error banner, dismiss on re-upload|
| Network failure         | Show inline message, keep form state  |

### Save patterns

| Context               | Behavior                              |
|-----------------------|---------------------------------------|
| Settings form         | Save button → "Saved" toast → keep form populated |
| Session rename        | Inline edit → blur or Enter saves → focus returns |
| Pin session           | Instant toggle, no confirmation       |

---

## Responsive patterns

| Breakpoint | Layout changes                                    |
|------------|---------------------------------------------------|
| ≥ 1024px   | Sidebar visible, chat centered at 800px           |
| 768–1023px | Sidebar overlay (toggle), chat 90vw              |
| < 768px    | Sidebar overlay (full-width), chat 95vw, reduced header |

### Mobile-specific behaviors

- Input bar is at the bottom (no floating attachment)
- Sources and debug panel collapse to save space
- Action buttons (copy, like, dislike) shown always (not hover)
- Header shows only logo + menu button
- Sidebar toggle is prominent (left of input or top-left corner)

---

## AI Activity Timeline

### Description

An optional expanded view of the AI's reasoning process. Hidden by default. Replaces or augments the simple Debug Panel.

### States

| State       | Visual                                           |
|-------------|--------------------------------------------------|
| Thinking    | Pulsing dot + "Thinking…"                        |
| Routing     | Icon + intent label + route decision             |
| Retrieving  | Animated search icon + "Searching knowledge base"|
| Reranking   | Progress bar (20 → 5) or animated filter icon    |
| LLM         | Pulsing AI icon + "Generating response"           |
| Complete    | Checkmark + answer mode badge                     |

### Layout

```
┌──────────────────────────────────────────┐
│ ▼ AI Activity (expandable)              │
│                                          │
│  🔍 Intent Classifier                  │
│     general · 0.90                      │
│                                          │
│  📡 Router                              │
│     retrieval                            │
│                                          │
│  📚 Knowledge Search                    │
│     Hybrid · 20 retrieved                │
│                                          │
│  ⚡ FlashRank                            │
│     5 reranked                            │
│                                          │
│  🧠 Generating                           │
│     Grounded Retrieval                   │
│     5 chunks · 2 documents               │
│     73% confidence                       │
└──────────────────────────────────────────┘
```

### Implementation notes

- Each stage is a row: icon + label (left) + value (right)
- Stages appear sequentially with 100ms fade-in as they complete
- Current stage pulses gently
- Completed stages show a checkmark
- Collapsed by default, remembers expanded/collapsed state in localStorage
- Accessible: `aria-live="polite"` announces stage transitions

---

## Reference: State matrix

| Context     | Loading     | Empty       | Error       | Success     |
|-------------|-------------|-------------|-------------|-------------|
| Chat        | Skeletons   | Welcome     | Inline banner| Messages   |
| Sidebar     | Skeletons   | "No chats"  | —           | Sessions   |
| Input       | Disabled    | Placeholder | Error banner| Cleared    |
| KB list     | Skeleton cards | Empty state | Retry banner | Doc cards |
| Upload      | Progress bar | File picker | Error + retry| Done + dismiss|
| Settings    | —           | —           | Inline validation | Toast  |
| Sources     | —           | —           | —           | Pill chips |
| Debug panel | —           | —           | —           | Key-value grid |
