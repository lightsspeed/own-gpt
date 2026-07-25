# OwnGPT Experience

> The conversational AI workspace — the primary interface of the AI Engineering Platform.
>
> **Not a ChatGPT clone. Not a chatbot.**
>
> This is a complete product within the platform: a conversational workspace designed for engineering work.
>
> Every design decision traces back to the platform's interaction architecture (Phases 5–6).

---

## Purpose

OwnGPT is the primary interface for human-AI interaction in the AI Engineering Platform. It is where operators ask questions, issue commands, review artifacts, make decisions, and manage their relationship with the platform's AI capabilities.

The Operations Console (the broader platform UI) is the "power mode" workspace for deep inspection and management. OwnGPT is the conversational layer that makes the platform accessible, responsive, and intelligent.

### Design goals

1. **Conversation as a first-class workspace** — Not a transient chat window, but a persistent workspace with state, history, and tools.
2. **Evidence-driven responses** — Every AI answer is grounded, cited, and verifiable.
3. **Progressive complexity** — Simple questions get simple answers. Deep investigation is always one click away.
4. **Context-preserving** — The conversation carries context across turns, sessions, and navigation.
5. **Tool-augmented** — The AI can invoke platform tools, and the results appear seamlessly in the conversation.

---

## Workspace Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Top Bar: Title + Status + Model Selector + Share + Close       │
├──────────────────────────────┬──────────────────────────────────┤
│                              │                                  │
│  Conversation Thread         │  Context Panel (optional)        │
│                              │                                  │
│  ┌────────────────────────┐  │  ┌────────────────────────────┐ │
│  │ Welcome / Context       │  │  │ Artifact Preview           │ │
│  └────────────────────────┘  │  │  Tool Output                │ │
│  ┌────────────────────────┐  │  │  Evidence Panel             │ │
│  │ User Message            │  │  │  Comparison View           │ │
│  ├────────────────────────┤  │  │  Lineage Graph             │ │
│  │ AI Response             │  │  └────────────────────────────┘ │
│  │  ┌──────────────────┐   │  │                                  │
│  │  │ Streamed content  │   │  │                                  │
│  │  │ Citations         │   │  │                                  │
│  │  │ Artifact cards    │   │  │                                  │
│  │  │ Tool results      │   │  │                                  │
│  │  │ Approval buttons  │   │  │                                  │
│  │  └──────────────────┘   │  │                                  │
│  ├────────────────────────┤  │                                  │
│  │ Suggested follow-ups   │  │                                  │
│  └────────────────────────┘  │                                  │
│                              │                                  │
│  ──────────────────────────  │                                  │
│  [Input area] [🔗] [🔧] [↩]  │                                  │
│                              │                                  │
├──────────────────────────────┴──────────────────────────────────┤
│  Status bar: Context tokens · Model info · Actions               │
└─────────────────────────────────────────────────────────────────┘
```

### Layout zones

| Zone | Default | Purpose |
|---|---|---|
| Top bar | Always visible | Title, status, model selector, share, close |
| Conversation thread | Full width | Primary interaction surface |
| Context panel | Hidden (toggle) | Artifact preview, tool output, evidence, lineage |
| Input area | Always visible | Message composition, attachments, tool picker |
| Status bar | Always visible | Context usage, model info, actions |

### Layout variants

| Mode | Thread width | Panel | When |
|---|---|---|---|
| Focus | Full width (constrained) | Hidden | Default writing/review mode |
| Inspect | 60% | Visible (40%) | Reviewing artifacts or tool output |
| Compare | 50% | 50% (split) | Comparing artifacts side by side |
| Minimal | Full width (no chrome) | Hidden | Embedded in Operations Console |

---

## Conversation Thread

### Message types

| Message type | Visual | Behavior |
|---|---|---|
| **User message** | User avatar + name + timestamp | Plain text or structured command; right-aligned in thread |
| **AI response** | AI avatar + name + timestamp | Streamed text with embedded elements; left-aligned |
| **Tool result** | Structured card with tool icon | Collapsible; shows progress → result |
| **Artifact card** | Compact artifact reference | Type icon + title + status + summary; clickable |
| **Evidence block** | Cited source with excerpt | Collapsible; links to source artifact |
| **Approval request** | Decision card with actions | Sticky within thread; approve/reject/request changes |
| **System message** | Centered, subtle | Status updates, errors, informational |
| **Error message** | Red/amber inline | Error description + retry or alternative |

### Message structure

Each message follows a consistent structure:

```
┌──────────────────────────────────────┐
│  [Avatar] [Name] · [Timestamp]       │
│                                      │
│  Content (text, markdown, elements)  │
│                                      │
│  ┌────────────────────────────────┐  │
│  │ Embedded artifacts / tool      │  │
│  │ results / evidence / approvals │  │
│  └────────────────────────────────┘  │
│                                      │
│  Actions: Copy · Share · Fork · Cite │
└──────────────────────────────────────┘
```

### Streaming response

AI responses appear incrementally, character by character or token by token.

| State | Visual | Behavior |
|---|---|---|
| Waiting | AI avatar with pulse animation | "Thinking..." — visible for < 2s before first token |
| Streaming | Text appears character by character | Cursor blinks at end of current text |
| Complete | Full response rendered; cursor disappears | Final formatting applied |
| Interrupted | "Response stopped" indicator | User clicked stop; partial response remains |
| Error | Error message replaces response | "Failed to generate response" with retry |

**Streaming rules:**
- First token appears within 2 seconds of submission (or "thinking" indicator).
- Text is progressively rendered — no buffering.
- Citations appear inline as the source text is written.
- Embedded elements (artifacts, tables) render after their text context is complete.
- Streaming can be stopped at any time via stop button (replaces send button during streaming).

---

## Input Area

```
┌─────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────┐    │
│  │  Type a message, or use / for commands...  │    │
│  │                                             │    │
│  └─────────────────────────────────────────────┘    │
│  [🔗 Attach] [🔧 Tools] [📋 / Commands] [↩ Send]   │
└─────────────────────────────────────────────────────┘
```

### Input features

| Feature | Behavior |
|---|---|
| **Message input** | Multi-line textarea; auto-grows to 8 lines; Enter to send (Shift+Enter for newline) |
| **Tool picker** | Opens tool selector panel; select tool → tool card appears in input area with config |
| **Attachments** | Opens file picker; supports drag-and-drop; shows attachment chips in input area |
| **Command menu** | Opens command palette filtered to conversation commands (`/find`, `/compare`, `/explain`, etc.) |
| **Send button** | Submits message; becomes stop button during streaming |
| **Voice input** | (Future) Microphone icon; speech-to-text |

### Attachment handling

| Attachment type | Behavior | Preview |
|---|---|---|
| File (PDF, TXT, MD) | Uploaded and added to conversation context | File name, size, type badge |
| Image | Displayed inline | Thumbnail; expandable |
| Artifact reference | Linked as artifact card | Type icon, title, summary |
| Multiple files | Stacked as attachment chips | Count badge on attach button |

### Command integration

Commands are accessible via:
- `/` prefix in the input area
- Command button (🔧) above input
- Keyboard shortcut (⌘/)

Commands in the conversation workspace include:

| Command | Action |
|---|---|
| `/find` | Search artifacts |
| `/compare` | Compare two items |
| `/explain` | Explain a concept or result |
| `/approve` | Approve pending item |
| `/reject` | Reject with rationale |
| `/summarize` | Summarize current context |
| `/export` | Export conversation |
| `/settings` | Open conversation settings |

---

## Context Panel

The Context Panel provides supplementary information without navigating away from the conversation.

### Panel modes

| Mode | Content | Trigger |
|---|---|---|
| **Artifact preview** | Artifact metadata, payload, lineage | Click artifact card in conversation |
| **Tool output** | Full tool result with details | Click tool result in conversation |
| **Evidence** | Source artifacts and citations | Click citation in conversation |
| **Comparison** | Side-by-side comparison | `/compare` command |
| **Lineage** | Full lineage graph | "View lineage" action on any artifact |
| **Search** | Search results | Inline search from conversation |

### Panel behavior

| Aspect | Behavior |
|---|---|
| Open | Toggle via button, click artifact, or `⌘.` |
| Close | Escape, click outside, or close button |
| Width | 40% of viewport (desktop); full-width slide-over (tablet/mobile) |
| Multiple | Stacked — new replaces current unless pinned |
| Pin | Pin button keeps panel content fixed while navigating in thread |
| State | Panel state (open/closed, pinned, content) preserved per session |

---

## Tool Picker

The Tool Picker lets users invoke platform tools within the conversation.

### Access points
- Tool button (🔧) above input area
- `/tool` or `/run` command
- AI may suggest tools and ask for confirmation

### Tool picker interface

```
┌──────────────────────────────────────────────┐
│  Select a tool              [Search...]      │
├──────────────────────────────────────────────┤
│  ┌────────────────────────────────────────┐ │
│  │ 🔬 Evaluate     Run evaluation         │ │
│  │   on a capability                       │ │
│  ├────────────────────────────────────────┤ │
│  │ 📊 Analyze      Analyze metrics         │ │
│  │   and generate report                   │ │
│  ├────────────────────────────────────────┤ │
│  │ 🔍 Compare      Compare two             │ │
│  │   configurations                        │ │
│  ├────────────────────────────────────────┤ │
│  │ 📄 Export       Export data or          │ │
│  │   artifacts                             │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  [Recently used] [All tools]                 │
└──────────────────────────────────────────────┘
```

### Tool invocation flow

1. User selects tool (or AI suggests)
2. Tool parameters appear in conversation
3. User configures parameters inline
4. User confirms execution
5. Tool runs; progress shown in conversation
6. Result appears as structured output
7. User can iteratively refine

---

## Conversation History

### History panel

Access via sidebar "History" section or `/history` command.

```
┌──────────────────────────────────────────────┐
│  Search conversations          [⌘K search]   │
├──────────────────────────────────────────────┤
│  Today                                       │
│  ┌────────────────────────────────────────┐ │
│  │ Review findings from last eval         │ │
│  │ 12 messages · 2 artifacts              │ │
│  └────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────┐ │
│  │ Debug retrieval pipeline               │ │
│  │ 8 messages · 1 tool run                │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  Yesterday                                   │
│  ┌────────────────────────────────────────┐ │
│  │ Configure experiment AB-47             │ │
│  │ 24 messages · 1 approval · 2 artifacts │ │
│  └────────────────────────────────────────┘ │
│  ...                                        │
│                                              │
│  [Load more]  [Clear history]                │
└──────────────────────────────────────────────┘
```

### History features

| Feature | Behavior |
|---|---|
| Search | Full-text search across all conversations |
| Filter | By date, tags, artifacts, tools used |
| Group | By date (Today, Yesterday, This Week, Older) |
| Summary | Each conversation shows: title, message count, artifact count, last message preview |
| Delete | Soft delete (archived, not removed from ledger) |
| Export | Export conversation as JSON, Markdown, or PDF |
| Share | Generate shareable link with read-only view |

### Conversation metadata

Each conversation in history shows:
- Title (auto-generated from first message or user-defined)
- Timestamp of first and last message
- Message count
- Artifact count (with type breakdown)
- Tool run count
- Approval count
- Tags (auto or user-assigned)
- Participants (user + AI instance)

---

## Follow-up Suggestions

After each AI response, the system suggests follow-up questions or actions.

### Suggestion types

| Type | Example |
|---|---|
| **Explore deeper** | "Show me the evidence for this finding" |
| **Take action** | "Create an experiment to test this change" |
| **Related topic** | "How did this compare to last week's evaluation?" |
| **Refine** | "Narrow this to the last 24 hours" |
| **Explain** | "Explain why this metric dropped" |

### Presentation

Suggestions appear below the AI response as compact, clickable chips:

```
┌──────────────────────────────────────────────┐
│  AI Response text...                          │
│                                              │
│  ┌──────────────┐ ┌──────────────────┐      │
│  │ Show evidence │ │ Create experiment │      │
│  └──────────────┘ └──────────────────┘      │
│  ┌──────────────────┐ ┌─────────────────┐   │
│  │ Compare with last│ │ Explain metric  │   │
│  └──────────────────┘ └─────────────────┘   │
└──────────────────────────────────────────────┘
```

### Generation rules
- Maximum 4 suggestions per response.
- Suggestions are context-aware (based on the current conversation and platform state).
- Suggestions never repeat verbatim within the same conversation.
- Clicking a suggestion sends it as the next message.
- Suggestions can be dismissed (hide this set).

---

## Conversation States

The conversation workspace follows the platform's state model (13).

| State | Visual | Behavior |
|---|---|---|
| **Idle** | Normal view; input enabled | Ready for user input |
| **User typing** | Input area active | No change to thread |
| **AI thinking** | AI avatar with pulse; "Thinking..." | Brief (< 2s) before streaming; cannot send |
| **AI streaming** | Text appearing incrementally; stop button visible | Response in progress; user can stop |
| **AI complete** | Full response rendered; suggestions shown | User can send next message |
| **AI interrupted** | Partial response with "Stopped" indicator | User stopped streaming; partial response remains |
| **Tool running** | Progress indicator in thread | Tool executing; user can cancel and send other messages |
| **Tool complete** | Tool result rendered | Result viewable; conversation continues |
| **Needs approval** | Approval card with actions | Awaiting user decision; conversation blocked for this item |
| **Error** | Error message in thread | Retry or continue |
| **Branching** | Fork indicator on message | New branch started from this point |
| **Searching** | Search results in context panel | User can select result to reference |

---

## Split View with Operations Console

OwnGPT can operate in split view alongside the Operations Console, enabling conversation-powered investigation.

### Split view modes

```
Full Conversation              Split 60/40                 Split 50/50
┌──────────────────────┐      ┌──────────┬──────────┐      ┌────────┬─────────┐
│                      │      │          │          │      │        │         │
│     OwnGPT           │      │  OwnGPT  │ Console  │      │ Console│ OwnGPT  │
│                      │      │          │          │      │        │         │
│                      │      │          │          │      │        │         │
│                      │      │          │          │      │        │         │
└──────────────────────┘      └──────────┴──────────┘      └────────┴─────────┘
Default                  Inspect mode               Reference mode
```

### Split view behaviors

| Aspect | Behavior |
|---|---|
| Activation | Drag conversation to side, click "Open in split", or use keyboard shortcut |
| Sizing | Adjustable divider between panels |
| Sync | Actions in one panel may affect the other (console selection → conversation context) |
| Context injection | Selecting an item in the console pre-fills conversation context |
| Navigation | Navigating in the console does not change the conversation thread |
| Session | Split state (position, content, sizing) preserved across navigation |
| Close | Drag divider to edge, click "Close split", or use shortcut |

---

## Keyboard Shortcuts

OwnGPT is designed for keyboard-first interaction.

| Shortcut | Action |
|---|---|
| `⌘K` | Open command palette |
| `⌘⇧K` | Open tool picker |
| `⌘N` | New conversation |
| `⌘⇧F` | Search conversations |
| `⌘⇧C` | Toggle context panel |
| `⌘⇧S` | Toggle split view |
| `⌘.` | Focus context panel |
| `⌘Enter` | Send message |
| `⌘⇧Enter` | Send without streaming (full response at once) |
| `↑` (in empty input) | Edit last message |
| `Escape` | Stop streaming / close panel / clear selection |
| `⌘C` (during streaming) | Stop streaming |
| `⌘⌫` | Clear conversation |
| `⌘⇧E` | Export conversation |
| `⌘⇧D` | Toggle developer mode |
| `⌘[` | Navigate to previous conversation |
| `⌘]` | Navigate to next conversation |

---

## Developer Mode

Developer mode adds debugging and introspection capabilities to OwnGPT.

### Activation
- Keyboard shortcut: `⌘⇧D`
- Toggle from user menu
- Per-session setting (not persisted)

### Developer mode features

| Feature | Purpose |
|---|---|
| **Raw response viewer** | See the full JSON response from the AI engine |
| **Token usage** | Token count, cost estimate, model used |
| **Latency breakdown** | Time to first token, total response time, tool execution time |
| **Prompt preview** | View the full prompt sent to the model (including system prompt and context) |
| **Knowledge base references** | See which documents/chunks were used in retrieval |
| **Tool call log** | Each tool invocation with input, output, duration |
| **Confidence scores** | Per-claim confidence from the evidence engine |
| **State inspector** | Current conversation state, context size, cached data |

### Developer mode presentation
Developer information appears in the context panel (when in developer mode) or as an expandable section below each message.

---

## Empty States

| State | Visual | Message |
|---|---|---|
| **New conversation (first time)** | Welcome card with platform logo | "Welcome to OwnGPT. Ask me anything about your AI Engineering Platform. Try: 'How is the platform doing?' or 'Show me recent findings.'" |
| **New conversation (returning)** | Input area focused; history shown | Empty thread; last conversation shown in history panel |
| **No search results (within conversation)** | Search results area with empty state | "No messages matching your search" |
| **No conversation history** | History panel with empty state | "No conversations yet. Start your first conversation to see history here." |
| **No tool results** | Tool picker with empty state | "This tool requires parameters. Configure options above." |
| **No attachments** | Attachment area with upload prompt | "Drop files here or click to browse supported file types." |
| **Network disconnected** | Banner at top of conversation | "You're offline. Your messages will be sent when connectivity is restored." with reconnect button |

---

## Loading States

| Load context | Indicator | Description |
|---|---|---|
| **Initial conversation load** | Thread skeleton with 3 placeholder message blocks | Shows avatar + text line placeholders at realistic spacing |
| **Message sending** | Message appears as "sending" (gray, pending icon) | Transitions to complete state on delivery |
| **AI thinking** | AI avatar pulse animation | "Thinking..." — appears for < 2s |
| **AI streaming** | Text appears incrementally | Cursor blinks at end of current text |
| **Tool execution** | Tool card with progress bar | Tool name, elapsed time, step description |
| **File upload** | Attachment chip with progress | File name, size, upload progress |
| **History search** | Search results skeleton | Search bar active; results appear progressively |
| **Context panel load** | Panel skeleton | Content-specific skeleton (artifact card, chart placeholder) |

---

## Error States

| Error | Behavior | Recovery |
|---|---|---|
| **AI response failed** | Error message in thread; "Failed to generate response" | Retry button; suggest rephrasing |
| **Tool execution failed** | Tool result shows error with details | Retry; suggest alternative tool |
| **Network lost** | Banner: "Connection lost" | Auto-reconnect; queued messages sent on reconnect |
| **Rate limited** | Inline message: "Too many requests. Please wait." | Countdown to retry |
| **Invalid input** | Input area shows validation error | Correct the input |
| **Attachment failed** | Attachment chip shows error | Retry upload; remove attachment |
| **Session expired** | Full-screen overlay: "Session expired" | Re-authenticate; conversation preserved |
| **Unknown error** | Error message with correlation ID | "Something unexpected happened. Reference ID: XXX" |

### Error recovery principles
- Errors never lose conversation history.
- Errors allow retry without re-typing the message.
- Recoverable errors show recovery action; unrecoverable errors show explanation.
- Conversation continues after error (error message stays; user can send new message).

---

## Mobile Experience

### Layout adaptation

| Element | Mobile behavior |
|---|---|
| **Conversation thread** | Full width; no context panel |
| **Input area** | Fixed at bottom; above keyboard; auto-grows |
| **Tool picker** | Full-screen modal |
| **Context panel** | Bottom sheet or full-screen push |
| **History panel** | Full-screen overlay |
| **Split view** | Not available (mobile is single-focus) |
| **Top bar** | Condensed: title + back + actions overflow |

### Touch interactions

| Gesture | Action |
|---|---|
| Swipe left (on message) | Reveal action: Reply, Copy, Share |
| Long press (on message) | Context menu: Copy, Share, Fork, Report |
| Swipe down (on thread) | Refresh conversation |
| Tap (on input area) | Focus input and open keyboard |
| Tap (on attachment) | Preview attachment |
| Swipe right (from left edge) | Open history panel |

### Mobile-specific states
- **Keyboard open:** Input area moves to top of keyboard; thread scrolls to latest message.
- **Orientation change:** Landscape shows slightly wider input area; portrait is default.
- **Offline:** Messages queued; banner shows offline status; conversation remains readable.

---

## Accessibility

### Visual
- All text meets WCAG AA contrast.
- Message bubbles have clear visual separation.
- AI vs. user messages distinguishable by alignment + color + label.
- Streaming cursor is high contrast.

### Keyboard
- Full keyboard navigation of all interactive elements.
- Tab order: Input → messages (most recent first) → tool bar → context panel.
- Messages are reachable via arrow keys.
- All actions available via keyboard shortcut.

### Screen reader
- New messages announced via `aria-live="polite"`.
- Message roles: user = "You said:", AI = "Assistant said:".
- Streaming content announced as it arrives (chunked).
- Attachments announced with file name and type.
- Tool results announced with status.

### Motor
- Minimum 44x44px touch targets.
- All interactions available without drag or long-press.
- Send button is large; easy to tap on mobile.
- Stop button is prominent during streaming.

### Cognitive
- Consistent message layout throughout conversation.
- Suggestions reduce cognitive load (no need to formulate queries).
- Error messages are plain language with clear recovery.
- Undo available for supported actions.

### Reduced motion
- All animations respect `prefers-reduced-motion`.
- Streaming: opacity changes only (no cursor blink).
- Panel transitions: opacity only (no slide).
- Skeleton: static (no pulse).

---

## Implementation Boundaries

### OwnGPT owns:
- Conversation thread rendering and behavior
- Message input and submission
- Streaming response rendering
- Context panel
- Tool picker and tool integration
- Conversation history management
- Follow-up suggestion generation
- Split view integration
- Developer mode
- Keyboard shortcut handling

### Operations Console owns:
- All list/detail screens (Findings, Experiments, etc.)
- Dashboards
- Monitoring
- Configuration management
- Settings

### Platform owns:
- AI engine (model, prompt management, context orchestration)
- Tool execution engine
- Artifact storage and retrieval
- Notification system
- Authentication and session management

---

## Anti-Patterns

| Anti-pattern | Problem | Remedy |
|---|---|---|
| Chatbot-style single-turn interaction | Each message is a disconnected query | Conversation is a persistent workspace with context across turns |
| No evidence citation | AI makes claims without sources | Every factual claim must have an inline citation |
| Blocking tool execution | User cannot send other messages while tool runs | Tools run asynchronously; user can continue conversation |
| Notification spam in conversation | Every state change interrupts the conversation | Only critical notifications appear in conversation; others go to panel |
| Forgetting context on navigation | Conversation loses references to previous artifacts | Context is preserved across navigation and sessions |
| Mobile as an afterthought | Mobile experience is broken or missing | Mobile is designed as part of the workspace, not adapted later |
| Streaming as a spinner | User waits for full response before seeing anything | First token within 2s; progressive rendering throughout |
| No undo | User cannot recover from mistakes | Undo for message send, dismiss, and delete operations |
| Hidden developer mode | Debug information is inaccessible | Developer mode is discoverable via shortcut and menu |
| Over-engineered suggestions | Suggestions are irrelevant or repetitive | Context-aware, max 4, never repeat verbatim |

---

## Relationship to Other Documents

| Document | Relationship |
|---|---|
| 07-assistant-philosophy.md | OwnGPT embodies the assistant constitution and responsibilities |
| 09-conversation-lifecycle.md | OwnGPT implements the full conversation lifecycle |
| 10-artifact-interactions.md | Artifacts appear inline, in context panel, and in lineage views |
| 11-tool-invocation.md | Tool picker and tool execution follow the tool lifecycle |
| 12-command-system.md | Commands are accessible via `/` and keyboard shortcuts |
| 13-state-model.md | Conversation states follow the universal state model |
| 16-screen-recipes.md | OwnGPT is Recipe C — Conversation + Context |
| 17-design-system-architecture.md | Uses all primitives (Message, Action, Input, Status, etc.) |
| 18-visual-language.md | Applies visual language tokens consistently |
| 19-motion-feedback.md | Streaming, transitions, and feedback follow motion principles |
| 20-notifications.md | Notifications integrate into conversation thread |

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-07-25 | Architecture | Initial OwnGPT experience definition |
