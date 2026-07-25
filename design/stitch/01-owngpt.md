# Stitch Prompt: OwnGPT

> Generate the OwnGPT conversational workspace.
>
> **Context:** This prompt assumes `stitch/00-master-context.md` as the foundation. Read it first.
>
> **Priority:** Sprint 1 — must be generated before Dashboard and OwnOps.

---

## Design Goal

Generate the OwnGPT conversational AI assistant screen for Own Platform.

The goal is to **replicate the interaction philosophy of ChatGPT as closely as possible** while integrating into the Own Platform design system.

This is not "inspired by ChatGPT." It should feel familiar to anyone who has used ChatGPT, while adding platform-specific capabilities (artifact cards, tool results, evidence blocks, split view) in a way that does not clutter the core chat experience.

---

## Screen Information

| Property | Value |
|---|---|
| **Recipe** | C — Conversation + Context |
| **Route** | `/conversation` (can also be default landing at `/`) |
| **Primary users** | All authenticated users |
| **Primary goal** | Ask questions, issue commands, review AI responses, invoke tools, make decisions |
| **Layout** | Full-width message thread + optional right context panel |

---

## Layout Structure

```
┌──────────────────────────────────────────────────────────────┐
│  Top Bar: [☰ Sidebar] OwnGPT · [Model] · [Share] · [⋮]     │
├────────────────────────────────┬─────────────────────────────┤
│                                │                             │
│  Conversation Thread           │  Context Panel (optional)   │
│                                │                             │
│  (messages fill available      │  - Artifact preview         │
│   height, scrollable)          │  - Tool output              │
│                                │  - Evidence panel           │
│                                │  - Lineage graph            │
│                                │                             │
│                                │                             │
│                                │                             │
├────────────────────────────────┴─────────────────────────────┤
│  [Attach] [Tools] [Type a message...] [Send]                 │
└──────────────────────────────────────────────────────────────┘
```

### Left sidebar (collapsible)

- Hidden by default. Toggle via ☰ hamburger or `⌘\`.
- Contains: conversation list (searchable, grouped by date), "New conversation" button at top.
- Width: 280px. Overlays content on mobile; pushes content on desktop.
- Each conversation item shows: title, message count, timestamp, last message preview.

### Top bar

- Left: ☰ hamburger (toggle sidebar) + "OwnGPT" label.
- Center or right: Model indicator (subtle, clickable for menu — hidden in default view, shown in developer mode).
- Right: Share conversation button, overflow menu (export, settings, developer mode toggle).

### Message thread

- Full remaining height. Scrollable. Newest messages at bottom.
- Messages are left-aligned (AI) and right-aligned (user) with avatars.
- Streaming response appears as text incrementally with blinking cursor at end.
- Suggested follow-ups appear as chips below each AI response (max 4).

### Composer (fixed at bottom)

- Multi-line textarea. Auto-grows to max 8 lines. Placeholder: "Type a message, or use / for commands..."
- Buttons beside composer (left to right):
  - 📎 Attach (opens file picker)
  - 🔧 Tools (opens tool picker)
  - Send button (becomes ■ Stop button during streaming)
- Composer is always visible. Does not scroll with messages.

### Context panel (right, optional)

- Hidden by default. Toggle via `⌘⇧C` or clicking an artifact reference.
- Width: 400px. Slides in from right, overlays conversation.
- Content changes based on what user clicked:
  - Artifact preview: metadata + payload + lineage
  - Tool output: full result with details
  - Evidence: source artifacts and citations
- Close via Escape or close button.

---

## Visual Design Constraints

### Colors
- **Sidebar:** Surface background (`bg.secondary`). Selected conversation: accent background.
- **Thread:** Page background (`bg.primary`).
- **AI messages:** Subtle background (`bg.secondary`), rounded corners.
- **User messages:** No background or accent background (like ChatGPT — user messages are plain or subtle).
- **Composer:** Surface background, subtle border.
- **Links/citations:** Accent color, underlined.
- **Status indicators:** Green/blue/yellow/red per severity.
- **Dark mode:** Must work as first-class theme. Dark sidebar, dark thread, adjusted message backgrounds.

### Typography
- Body text: 15–16px base. Comfortable line height (1.5–1.6).
- Code blocks: Monospace, slightly smaller, with background.
- Message headers (name): Small, secondary text color.
- Timestamps: Smaller, secondary text color.
- Follow-up suggestions: Body size, clickable, subtle background on hover.

### Spacing
- Message gap: 16–24px between messages.
- Composer padding: 16px around textarea.
- Sidebar items: 8–12px vertical padding.
- Context panel padding: 20px.
- Generous whitespace throughout. ChatGPT-like breathing room.

### Elevation
- Sidebar: Raised (elevation 1) when overlaying content.
- Context panel: Overlay (elevation 2) with scrim.
- Composer: Surface (elevation 0) — attached to bottom of viewport.
- Dropdowns/tooltips: Notification (elevation 4).

### Borders
- Sidebar: Right border (subtle).
- Context panel: Left border (subtle).
- Composer: Top border (subtle).
- Input textarea: Border on focus (accent color).
- Cards within messages: Border OR elevation (not both).

### Motion
- Sidebar open/close: 250ms, slide from left.
- Context panel open/close: 250ms, slide from right.
- Streaming: Text appears incrementally. Blinking cursor (1s interval).
- Message entrance: Fade in (150ms) when not streaming.
- Follow-up chips: Fade in (100ms) after response completes.
- Composer: No animation (persistent).

---

## States to Design

### Empty state (new conversation, first-time user)

Show a welcome message centered in the thread:

> **Welcome to OwnGPT**
>
> I'm your AI engineering assistant. I can help you monitor your platform, investigate findings, run experiments, and manage configurations.
>
> Try asking:
> - "How is the platform doing?"
> - "Show me recent findings"
> - "What experiments are running?"
>
> [Start with a suggestion →]

Suggested prompts appear as clickable chips below the welcome message.

### Empty state (returning user)

Show the last conversation summary or a prompt input ready with recent conversations listed in sidebar.

### Loading state (initial load)

Skeleton: 2–3 message placeholders with avatar circles + text line blocks. No spinner.

### Loading state (AI thinking)

AI avatar shows brief pulse animation. "Thinking..." appears for < 2 seconds before first token arrives.

### Streaming state

Text appears incrementally. Blinking cursor at end of current text. Stop button replaces send button.

### Error state (response failed)

Error message inline in thread:

> "I encountered an error generating a response. [Retry]"

Original user message remains. Retry sends the same message again.

### Error state (network lost)

Banner at top: "Connection lost. Your messages will be sent when connectivity is restored."

No message is lost. Queued messages send on reconnect.

### Loading state (file upload)

Attachment chip below composer with progress bar. File name + size + upload percentage.

### Empty state (no conversation history in sidebar)

> "No conversations yet. Start a new conversation to see history here."

### Developer mode

Toggled via `⌘⇧D`. Adds subtle "Dev" badge to top bar. Context panel shows debug info (token count, latency, prompt preview, tool calls). Not visible in normal mode.

---

## Key Interactions to Design

### Sending a message
1. User types in composer.
2. Enter sends (Shift+Enter = newline).
3. Message appears in thread as "sending" (gray, pending).
4. AI response begins streaming.

### Stopping a response
1. During streaming, send button becomes stop button (■).
2. Clicking stop halts streaming. Partial response remains.
3. "Response stopped" indicator appears below partial response.

### Editing a message
1. Press ↑ in empty composer to edit the last user message.
2. Original message appears in composer for editing.
3. Re-sending replaces the original and removes its response.

### Opening the tool picker
1. Click 🔧 button beside composer.
2. Overlay panel appears above composer with tool list.
3. Each tool shows: icon, name, description.
4. Selecting a tool adds a tool card to the input area.
5. User configures parameters inline, then sends.

### Opening the context panel
1. Click an artifact reference, citation, or tool result in the message thread.
2. Context panel slides in from right with relevant content.
3. Escape or close button dismisses.
4. Pin button keeps current content while navigating thread.

### Switching conversations
1. Open sidebar (☰ or `⌘\`).
2. Click a conversation in the list.
3. Current conversation is preserved in history.
4. Selected conversation loads in thread.

### Using split view
1. Click "Open in split" or use `⌘⇧S`.
2. Conversation shifts to left 60%; OwnOps opens in right 40%.
3. Adjustable divider between panes.
4. Click "Close split" or use `⌘⇧S` again to restore full conversation.

---

## Message Types (Visual Variants)

### User message
- Right-aligned. User avatar + name + timestamp above.
- Plain text with optional formatting (code, lists).
- No background (like ChatGPT) or subtle background.

### AI text response
- Left-aligned. AI avatar + "OwnGPT" + timestamp above.
- Rich text: paragraphs, lists, code blocks, tables.
- Inline citations: clickable, accent-colored links.
- Streaming: text fills in left-to-right with cursor.

### Artifact card (inline)
- Compact card within the AI response: type icon + title + status + 1-line summary.
- Clickable — opens artifact preview in context panel.
- Examples: finding card, experiment card, config snapshot card.

### Tool result
- Structured card below AI response: tool name + status + duration.
- Content: table, code output, chart, or structured data.
- Collapsible if content is large. Collapsed by default for large outputs.

### Evidence block
- Collapsible section: "Sources" header with count badge.
- Each source: artifact type icon + title + excerpt + confidence.
- Click to open source artifact in context panel.

### Approval request
- Inline decision card: context summary + evidence.
- Two buttons: Approve (primary), Reject (secondary).
- Optional rationale text area for rejection.
- After decision: card updates to show "Approved" or "Rejected" with timestamp.

### System message
- Centered, subtle text. No avatar.
- Used for: status updates, errors, informational messages.
- Examples: "Finding R-42 was approved.", "Connection restored."

---

## Accessibility Requirements

- All text meets WCAG AA contrast.
- Messages announced via `aria-live="polite"` as they appear.
- Streaming content announced in chunks (not character by character).
- All interactive elements keyboard accessible (Tab, Enter, Escape, Arrow keys).
- Focus management: after sending, focus returns to composer. After opening panel, focus moves to panel.
- Respects `prefers-reduced-motion`: no streaming cursor blink, no slide animations, opacity-only transitions.
- Skip navigation link: "Skip to latest message" at top of thread.
- Touch targets: minimum 44x44px on mobile (send button, attachment button, tool button).

---

## Mobile Adaptations

- **Layout:** Full-width conversation. No persistent sidebar or context panel.
- **Sidebar:** Full-screen overlay, triggered by ☰ or swipe from left.
- **Context panel:** Bottom sheet (pull up) or full-screen push.
- **Composer:** Fixed above keyboard. Textarea auto-focuses on tap.
- **Split view:** Not available on mobile.
- **Message density:** Slightly more compact. Avatars smaller (32px vs 40px).
- **Send button:** Larger touch target. Prominent.
- **Attachments:** Accessible via + button beside composer (instead of inline icon).

---

## Review Checklist

Before finalizing, verify:

- [ ] Does it feel like ChatGPT? (clean, centered, minimal, fast)
- [ ] Is engineering telemetry hidden by default?
- [ ] Are artifact cards and tool results non-disruptive?
- [ ] Does the composer feel fixed and natural?
- [ ] Does the sidebar feel like a navigation tool, not a control panel?
- [ ] Does streaming feel responsive and cancellable?
- [ ] Are all states (empty, loading, streaming, error) handled?
- [ ] Does the context panel complement rather than compete with the thread?
- [ ] Does dark mode work without looking inverted?
- [ ] Can a user start their first conversation without instruction?

---

## Deliverables

Generate:
1. **OwnGPT conversation view** — full thread with one AI response (streaming or complete), composer, sidebar closed
2. **OwnGPT with sidebar open** — conversation list visible, one conversation selected
3. **OwnGPT with context panel** — artifact preview visible in right panel
4. **OwnGPT split view** — conversation on left, OwnOps on right (60/40)
5. **OwnGPT mobile** — single column, composer at bottom, sidebar as overlay
6. **OwnGPT empty state** — welcome screen with suggested prompts
7. **OwnGPT developer mode** — debug info visible in context panel
8. **OwnGPT error state** — failed response with retry option
9. **Dark mode variants** for each of the above
