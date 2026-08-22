# Screen Recipes

> Reusable architectural blueprints for every screen in the Own Platform.
>
> **Not about pixels. Not about React. Not about components. Not about visual styling.**
>
> This document defines **how classes of screens behave**.

---

## Why Screen Recipes?

The screen inventory (Phase 5) defines 37 screens.

37 unique behavioral models would be impossible to maintain, impossible to learn, and impossible to build consistently.

Screen recipes reduce 37 screens to **10 reusable archetypes**.

Every screen in the product is built from exactly one recipe.

No screen requires a unique behavioral model.

---

## Recipe Overview

| # | Recipe | Screens Served | Complexity |
|---|--------|---------------|------------|
| A | Overview + Actions | 5 | High |
| B | Collection + Inspector | 13 | Medium |
| C | Conversation + Context | 1 | High |
| D | Timeline + Detail | 2 | Medium |
| E | Compare + Analysis | 2 | Medium |
| F | Editor + Preview | 3 | High |
| G | Review + Approval | 2 | Medium |
| H | Monitoring + Status | 2 | Medium |
| I | Search + Explore | 2 | Medium |
| J | Settings + Configuration | 2 | Low |

---

## Recipe A — Overview + Actions

### Purpose
Provide an at-a-glance summary of aggregate platform state, surface items needing attention, and enable one-click navigation to detail screens.

### When to use
Use when the primary user goal is "What needs my attention right now?" and the screen aggregates data from multiple downstream sources.

**Used by:** Operator Dashboard, CE Dashboard, Automation Dashboard, Governance Dashboard, Analytics Overview

### Information hierarchy
```
┌─────────────────────────────────────────┐
│  Global Command Bar (sticky)            │
├──────────────────┬──────────────────────┤
│  Zone A (65%)    │  Zone B (35%)        │
│                  │                      │
│  Health Summary  │  Summary Card        │
│  Attention Queue │  Context Card        │
│  Priority Items  │  Activity Feed       │
│  Trends          │  Status Cards        │
│                  │                      │
├──────────────────┴──────────────────────┤
│  Full-width reference section (below)   │
└─────────────────────────────────────────┘
```

### User goals
- Assess overall platform/system health in under 30 seconds
- Identify items requiring immediate action
- Navigate to detail screens for investigation
- Understand trends and direction of travel

### Primary interactions
- Scan — visual hierarchy communicates urgency without reading
- Click — any item navigates to its detail screen
- Filter — time window selector adjusts all widgets
- Customize — widget visibility and arrangement (optional, per-user)

### Navigation behavior
- Recipe A is always a navigation root (depth 0 or depth 1)
- All items are one-click drill-downs to Recipe B or Recipe G screens
- Global time window is preserved when navigating away and returning
- Scroll position and expanded sections persist per session

### Conversation integration
- "What's on my dashboard?" returns a summary of attention items
- "What changed since yesterday?" updates the daily brief widget
- Conversation can pin items to the attention queue

### Artifact integration
- Dashboard does not display full artifacts — only counts, badges, and summaries
- Each artifact reference is a clickable link to its detail screen
- Artifact lineage is not shown on dashboard (refer to Recipe B)

### Command integration
- Global search (⌘K) is the primary command entry point
- Quick action menu ("+") for rapid creation (new finding, experiment, etc.)
- Keyboard shortcuts for focusing specific widgets (⌘1–⌘6)

### Tool integration
- Tools do not run from the dashboard
- Dashboard reflects tool output indirectly through artifact counts and health status

### State expectations
- **Loading:** Skeleton grid matching widget layout; widgets load independently (parallel)
- **Empty:** Onboarding message with next-step guidance
- **Error:** Widget-level inline error with retry; never full-page error unless all widgets fail
- **Stale:** Last-known data persists with "Data may be stale" indicator
- **Refresh:** Configurable polling (15–60s per widget); manual refresh via ⌘R

### Loading behavior
- Skeleton placeholders match final widget dimensions
- Widgets render independently — fast widgets appear before slow ones
- No global loading spinner
- Content appears progressively as each endpoint resolves

### Empty state philosophy
- Never show empty dashboard as blank space
- Provide actionable next step: "No data yet. Complete your first evaluation to populate the dashboard."
- Use empty state as onboarding opportunity

### Error handling philosophy
- Widget-level errors never block other widgets
- Last known good data persists with stale indicator
- Retry is per-widget, not global
- Full-page error only if critical path endpoints all fail

### Responsive behavior
- Desktop: Two-column (65/35) with full-width bottom section
- Tablet: Single column stacked; widgets become expandable cards
- Mobile: Minimal — counts only, expandable sections, full-width

### Accessibility considerations
- Widget headers are `<h2>` elements
- Count badges use `aria-label`
- Status indicators use `aria-live="polite"`
- Tab order follows visual hierarchy (top-to-bottom, left-to-right)
- All interactions reachable via keyboard

### Anti-patterns
- Do not show raw data on the dashboard
- Do not make dashboard items require scrolling to see attention items
- Do not use carousels or auto-playing content
- Do not show more than 7 items in a single widget
- Do not mix P0 and P3 content above the fold

---

## Recipe B — Collection + Inspector

### Purpose
Browse a collection of items, filter/search, and inspect individual items in detail.

### When to use
Use when users need to browse a homogeneous collection, filter by criteria, and examine individual items.

**Used by:** Findings List, Finding Detail, Recommendations List, Recommendation Detail, Experiments List, Experiment Detail, Decisions List, Decision Detail, Config Snapshots List, Config Snapshot Detail, Capabilities Registry, Capability Detail, Learning Ledger Browser, Ledger Record Detail, Audit Log, Schedule Editor, Trigger Config, Knowledge Base

### Information hierarchy
```
┌──────────────────────────────────────────────┐
│  Filter Bar + Search + Action Bar (sticky)   │
├──────────────────────────────────────────────┤
│                                              │
│  Collection (table / cards / list)           │
│                                              │
│  with pagination or infinite scroll          │
│                                              │
├──────────────────────────────────────────────┤
│  Inspector panel (optional, slide-over)      │
└──────────────────────────────────────────────┘
```

Two variants:
- **B1 — List + Detail (drill-down):** Full-page list navigates to full-page detail. Used when detail requires full screen.
- **B2 — List + Inspector (split):** Persistent list with slide-over or side-panel detail. Used when detail is compact and quick inspection is common.

### User goals
- Find a specific item by searching or filtering
- Scan collection for items matching criteria
- Inspect an item's full detail without losing list context
- Perform batch actions on selected items
- Navigate lineage to related items

### Primary interactions
- Filter by metadata fields (status, severity, date, type, owner)
- Search by keyword or ID
- Sort by column headers
- Select items for batch actions
- Click item to inspect (full page or side panel)
- Paginate or infinite scroll through results

### Navigation behavior
- List position, filters, scroll state preserved when returning from detail
- URL encodes active filters and pagination state
- Detail screen has stable URL for sharing
- Back navigation restores exact list state

### Conversation integration
- "Show me findings from the last 24 hours" opens the filtered list
- "What happened with experiment AB-47?" opens the detail
- Conversation can apply filters to the collection
- Collection can be exported to conversation as context

### Artifact integration
- Each item in the collection represents an artifact
- Detail view shows artifact metadata, payload, and lineage
- Batch actions create new artifacts (e.g., batch dismiss creates audit entries)
- Collection is the primary surface for artifact discovery

### Command integration
- Filter by prefix in search bar (e.g., `type:finding severity:critical`)
- Quick filters as command suggestions
- `/edit` command from detail to enter edit mode
- `/export` command to export collection

### Tool integration
- Tools generate items that appear in collections (findings, recommendations)
- Detail view shows the tool that produced the artifact
- Rerun tool from artifact detail (if applicable)

### State expectations
- **Loading:** Table skeleton matching row count; filter bar skeleton
- **Empty:** "No items matching your criteria" with suggested filter removal
- **Error:** Inline error with retry; partial data shown if error is scoped
- **Not found (detail):** "Item not found" with back button and lineage suggestion

### Loading behavior
- Collection: skeleton rows with realistic proportions
- Detail: content skeleton matching layout (text blocks, metadata placeholders)
- Concurrent loading: list loads first, detail loads on navigation
- Pagination uses cursor-based or offset-based loading with page size indicator

### Empty state philosophy
- Differentiate "no items exist" from "no items match filters"
- Provide obvious filter removal action
- Offer creation action when applicable ("No experiments yet. Start one.")
- Use empty state as teaching moment for the feature

### Error handling philosophy
- Collection errors show inline banner with retry
- Detail errors for missing items offer navigation to parent collection or related items
- Network errors in detail show cached data if available
- Partial errors (one field fails) show error badge on the field, not full-page error

### Responsive behavior
- Desktop: Full-width collection; side-panel detail (B2) or full-page detail (B1)
- Tablet: Collection stacks above detail on navigation
- Mobile: Collection is full-width list; detail is full-page push navigation
- Filter bar collapses to icon-driven overlay on narrow viewports

### Accessibility considerations
- Collection uses `<table>` or `role="grid"` with proper headers
- Sortable columns announce sort direction
- Selection state announced via `aria-selected`
- Pagination controls are reachable landmarks
- Detail panels use `aria-label` for close/back actions

### Anti-patterns
- Do not show detail as a modal over the full list (loses context)
- Do not force pagination when infinite scroll is expected
- Do not clear filters when navigating to detail and back
- Do not use cards when a table is more scannable (structured data)
- Do not hide the filter bar behind interaction

---

## Recipe C — Conversation + Context

### Purpose
Primary AI interaction surface — conversational interface with supporting context panels for artifacts, lineage, and tools.

### When to use
Use when the primary user goal is to ask questions, give instructions, or explore through conversation.

**Used by:** Conversation Workspace (primary AI interaction)

### Information hierarchy
```
┌──────────────────────────────────────────────┐
│  Header: Conversation Title + Status + Meta  │
├──────────────────┬───────────────────────────┤
│                  │                           │
│  Message Thread  │  Context Panel (optional) │
│                  │                           │
│  ┌──────────┐   │  - Artifact preview       │
│  │ User msg  │   │  - Tool output            │
│  ├──────────┤   │  - Lineage view           │
│  │ AI resp   │   │  - Evidence panel         │
│  ├──────────┤   │  - Command results         │
│  │ ...      │   │                           │
│  └──────────┘   │                           │
│                  │                           │
│  ─────────────  │                           │
│  Input area      │                           │
│  [Type...] [↩]   │                           │
│                  │                           │
├──────────────────┴───────────────────────────┤
│  Footer: Context tokens, model info, actions │
└──────────────────────────────────────────────┘
```

### User goals
- Ask questions about platform state, artifacts, or history
- Issue commands to inspect, compare, or investigate
- Review AI responses with supporting evidence
- Iterate on ideas through conversation
- Execute workflows through natural language
- Review tool outputs and their results

### Primary interactions
- Type message — send query or instruction to AI
- Review response — read AI output with embedded artifacts and citations
- Click citation — navigate to source artifact
- Expand context — open artifact preview or tool output in side panel
- Branch — fork conversation at any point
- Approve — approve recommendation or action from conversation
- Command — use slash commands for structured actions

### Navigation behavior
- Conversation is a persistent workspace (not a transient page)
- Navigating within the platform can inject context into the conversation
- Conversation state preserved when navigating to other screens
- Deep links to specific messages or branches
- Artifact navigation from conversation opens in Recipe B or Recipe E

### Conversation integration
- This is the conversation hub — all other screens integrate with it
- Conversations can reference artifacts from any recipe
- Conversations can spawn commands (Recipe F)
- Conversations can trigger tool invocations

### Artifact integration
- Artifacts appear inline or as referenced cards in message thread
- Artifacts are clickable — open in context panel or navigate to detail
- Conversation produces artifacts (recommendations, experiment definitions)
- Artifact lineage visible through conversation history

### Command integration
- Slash commands (`/find`, `/compare`, `/edit`, `/approve`, `/explain`)
- Natural language interpreted as commands
- Command results appear as structured responses
- Command preview before execution

### Tool integration
- Tools invoked via conversation
- Tool progress shown in message thread
- Tool output rendered inline (tables, charts, structured data)
- Approval requests rendered as interactive prompts

### State expectations
- **Loading:** Message appears with streaming indicator (cursor animation)
- **Empty:** Welcome message with suggested starting points
- **Error:** Error message with retry option; conversation continues
- **Streaming:** Progressive rendering of AI response with stop button
- **Idle:** Input area focused, ready for next message
- **Waiting:** Pending tool execution or approval

### Loading behavior
- Streaming response renders incrementally — never a spinner for AI responses
- Tool execution shows progress indicator (not a generic loader)
- Attachments and artifacts load asynchronously in context panel
- Message thread never shows a full-page loader

### Empty state philosophy
- First-time user gets a welcome message explaining capabilities
- Returning user sees last conversation restored
- Empty state teaches interaction model through examples
- Suggested prompts for common tasks

### Error handling philosophy
- AI errors are shown in the message thread (not a toast or modal)
- Tool errors are shown inline in the tool output
- Network errors show reconnection status
- Conversation never loses history on error

### Responsive behavior
- Desktop: Full conversation thread with optional context panel
- Tablet: Full-width conversation; context panel as slide-over
- Mobile: Full-width conversation; context panel as bottom sheet or full-screen overlay
- Input area moves to bottom of viewport on mobile keyboard

### Accessibility considerations
- Live regions for streaming responses (`aria-live="polite"`)
- Message role for each turn
- Keyboard shortcuts for common actions (`⌘Enter` to send, `↑` to edit)
- Focus management on input area
- Skip navigation link to message thread

### Anti-patterns
- Do not use a generic loading spinner while AI is responding — stream the response
- Do not hide tool execution progress — show what is happening
- Do not make the conversation feel like a search engine
- Do not clear context on page refresh
- Do not force the user to type — offer suggestions and shortcuts

---

## Recipe D — Timeline + Detail

### Purpose
Display a chronological feed of events with the ability to inspect individual events in detail.

### When to use
Use when the primary user need is understanding "what happened when" and inspecting individual events.

**Used by:** Job Detail, Automation History (within Automation Dashboard), Evaluation Detail
**(Note: Some timeline views are embedded within Recipe A screens)**

### Information hierarchy
```
┌──────────────────────────────────────────────┐
│  Header: Title + Status + Time Range         │
├──────────────────────────────────────────────┤
│  Timeline (vertical)                         │
│                                              │
│  Today                                       │
│  ┌─────────────────────────────────────┐    │
│  │ 10:23  ● Event type  — Title        │    │
│  │        Summary line                  │    │
│  ├─────────────────────────────────────┤    │
│  │ 09:15  ● Event type  — Title        │    │
│  │        Summary line                  │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  Yesterday                                   │
│  ┌─────────────────────────────────────┐    │
│  │ 15:30  ● Event type  — Title        │    │
│  │        Summary line                  │    │
│  └─────────────────────────────────────┘    │
│                                              │
├──────────────────────────────────────────────┤
│  Detail Area (expandable or side panel)      │
└──────────────────────────────────────────────┘
```

### User goals
- See what happened in chronological order
- Understand sequence and causality of events
- Inspect details of a specific event
- Identify patterns or anomalies in event stream

### Primary interactions
- Scroll through timeline
- Click event to expand detail inline or open in panel
- Filter events by type
- Toggle between compact and detailed timeline view
- Navigate to artifact associated with event

### Navigation behavior
- Timeline position preserved when navigating to detail
- Detail opens inline or as slide-over (not full-page replace)
- Individual events are deep-linkable
- Timeline maintains scroll anchor — new events at top don't shift view

### Conversation integration
- "What happened in the last hour?" opens filtered timeline
- "Show me errors from the evaluation run" filters to error events
- Conversation can pin timeline events for reference

### Artifact integration
- Each timeline event references an artifact
- Event detail shows artifact preview
- Clicking event navigates to artifact detail (Recipe B)
- Timeline is itself an artifact lineage view

### Command integration
- `/timeline` with time range filter
- `/events` filtered by type
- `/export` timeline as log

### Tool integration
- Timeline shows tool executions as events
- Tool progress visible through timeline
- Failed tool executions are timeline events

### State expectations
- **Loading:** Timeline skeleton with event placeholders at realistic spacing
- **Empty:** "No events in this time range" with time range adjustment
- **Error:** Error banner with retry; last-known events preserved
- **Streaming:** New events appear at top (most recent first)
- **Stale:** "Data may be delayed" indicator

### Loading behavior
- Timeline loads oldest-to-newest or newest-to-oldest based on context
- Infinite scroll for long timelines
- Skeleton shows event lines at proportional spacing
- Detail loads on interaction, not pre-loaded

### Empty state philosophy
- No events means either "nothing happened" or "time range too narrow"
- Offer to expand time range
- If system is new, explain when events will appear

### Error handling philosophy
- Timeline errors preserve any loaded events
- New event polling fails silently (badge indicator)
- Detail errors show inline within the expanded event
- Individual event load failure doesn't block timeline

### Responsive behavior
- Desktop: Full timeline with inline or side-panel detail
- Tablet: Timeline full-width; detail inline (accordion)
- Mobile: Timeline full-width; detail inline (accordion)

### Accessibility considerations
- Timeline uses `aria-label` for event grouping by date
- Each event is a focusable element
- Timeline navigation with arrow keys
- Events announce time and type on focus

### Anti-patterns
- Do not auto-scroll the timeline on new events if user has scrolled up
- Do not collapse all events — keep most recent expanded
- Do not use a horizontal timeline (dates are harder to scan)
- Do not show raw timestamps without relative time ("2m ago")

---

## Recipe E — Compare + Analysis

### Purpose
Side-by-side or unified comparison of two or more items to identify differences, evaluate changes, and support decision-making.

### When to use
Use when the primary user goal is understanding "what changed" or "which is better."

**Used by:** Config Diff, Experiment Detail (variant comparison), Recommendation Detail (before/after config)

### Information hierarchy
```
┌──────────────────────────────────────────────┐
│  Compare Header: Title + Metadata            │
├──────────────────────┬───────────────────────┤
│                      │                       │
│  Item A              │  Item B               │
│                      │                       │
│  ┌────────────────┐  │  ┌────────────────┐  │
│  │ Metadata        │  │  │ Metadata        │  │
│  └────────────────┘  │  └────────────────┘  │
│  ┌────────────────┐  │  ┌────────────────┐  │
│  │ Content/Diff    │  │  │ Content/Diff    │  │
│  └────────────────┘  │  └────────────────┘  │
│                      │                       │
├──────────────────────┴───────────────────────┤
│  Unified diff view (toggle option)           │
├──────────────────────────────────────────────┤
│  Analysis panel: summary, stats, delta       │
└──────────────────────────────────────────────┘
```

Three variants:
- **E1 — Side-by-side diff:** Two items displayed in parallel with visual diff highlighting
- **E2 — Unified diff:** Single scroll showing differences inline
- **E3 — Comparison table:** Structured data comparison with delta columns

### User goals
- Understand what changed between two versions
- Identify specific differences in configuration, code, or data
- Evaluate which variant performs better (experiments)
- Support approval decisions with diff evidence

### Primary interactions
- Toggle between side-by-side and unified view
- Scroll through diff synchronously (both sides scroll together)
- Click diff line to see additional context
- Expand/collapse unchanged sections
- Navigate to either item's detail screen
- View delta summary (added, removed, changed counts)

### Navigation behavior
- Diff is a transient view — users arrive from a parent (Config List or Experiment Detail)
- Navigate to either item's detail from the diff header
- URL encodes the two items being compared (deep-linkable)
- Diff does not appear in navigation history independently (treated as detail)

### Conversation integration
- "Compare config v140 and v141" opens this recipe
- "What changed in this experiment?" summarizes diff in conversation
- Diff results can be referenced in conversation context

### Artifact integration
- Both items being compared are artifacts
- Diff is itself an artifact (the delta)
- Lineage shows the relationship between the two items

### Command integration
- `/compare` with two item references
- `/diff` with version identifiers
- `/delta` for numerical comparison

### Tool integration
- Diff computed by a compare tool
- Tool output is the diff view
- Tool progress shown during diff computation

### State expectations
- **Loading:** Two-column skeleton with file/line placeholders
- **No diff:** "No differences found" with identical indicator
- **Error:** Diff computation error with retry
- **Large diff:** Truncated with "X more differences" expand

### Loading behavior
- Diff computation may be async — show progress during computation
- Large diffs load incrementally (chunked)
- Skeleton shows two columns with line placeholders
- Synchronous scroll setup after load

### Empty state philosophy
- "No differences" is a valid and useful state — treat as success
- Offer to compare different items if identical

### Error handling philosophy
- One item not found: show partial diff with error badge
- Computation timeout: offer simplified text diff
- Large file: offer chunked or summarized diff

### Responsive behavior
- Desktop: Side-by-side (preferred) or unified diff
- Tablet: Unified diff by default; side-by-side on landscape
- Mobile: Unified diff only; scroll horizontally for long lines

### Accessibility considerations
- Diff regions use `aria-label="added"`, "removed", "unchanged"
- Color is not the only indicator of change type
- Synchronized scroll announced via `aria-live`
- Keyboard navigation between diff chunks

### Anti-patterns
- Do not show only unified diff — offer side-by-side as option
- Do not break synchronize scroll on line height differences
- Do not show full files when only a few lines changed
- Do not make the diff read-only — allow copy of specific lines

---

## Recipe F — Editor + Preview

### Purpose
Create or modify an artifact with real-time preview, validation, and structured input.

### When to use
Use when the user needs to create or edit a defined artifact type with structured fields and validation.

**Used by:** Experiment Designer, Schedule Editor (create/edit mode), Trigger Config (create/edit mode)

### Information hierarchy
```
┌──────────────────────────────────────────────┐
│  Editor Header: Title + Status + Actions     │
├──────────────────────┬───────────────────────┤
│                      │                       │
│  Form / Editor       │  Preview Panel        │
│  (primary input)     │  (live output)        │
│                      │                       │
│  ┌────────────────┐  │  ┌────────────────┐  │
│  │ Field 1         │  │  │ Summary        │  │
│  │ [__________]    │  │  │ Config preview │  │
│  ├────────────────┤  │  │ Diff preview   │  │
│  │ Field 2         │  │  │ Metric forecast│  │
│  │ [__________]    │  │  └────────────────┘  │
│  ├────────────────┤  │                       │
│  │ Field 3         │  │                       │
│  │ [__________]    │  │                       │
│  └────────────────┘  │                       │
│                      │                       │
│  Validation summary  │                       │
│  ─────────────────   │                       │
│  Save Draft | Launch  │                       │
│                      │                       │
├──────────────────────┴───────────────────────┤
│  Advanced / collapsed sections               │
└──────────────────────────────────────────────┘
```

### User goals
- Define or modify an artifact with confidence
- See the impact of changes before committing
- Validate inputs against business rules
- Save progress as draft
- Complete the creation workflow efficiently

### Primary interactions
- Fill form fields with structured input
- See live preview update as fields change
- Validate inputs with inline validation
- Toggle between edit and review mode
- Save draft / discard
- Submit for review or directly create

### Navigation behavior
- Editor is typically a dialog state — navigating away discards or prompts save
- Returning to editor from a validation error restores unsaved state
- Successful creation navigates to the new artifact's detail (Recipe B)
- Draft saves preserve URL for later return

### Conversation integration
- "Create a new experiment with variant A as control and variant B with temperature 0.8" pre-fills the editor
- Conversation can suggest editor values
- Editor state can be shared to conversation for review

### Artifact integration
- Editor creates a new artifact or modifies an existing one
- Preview shows the artifact as it will appear after creation
- Draft is a saved artifact state
- After creation, artifact follows its standard lifecycle

### Command integration
- `/new` with type prefix to open editor for specific artifact type
- `/edit` on an existing artifact opens it in editor
- `/validate` to check current inputs
- `/preview` to refresh preview panel

### Tool integration
- Tools may pre-fill editor fields (e.g., "load baseline config")
- Validation may invoke a tool (e.g., "check if metric is valid")
- Preview may invoke a tool (e.g., "estimate experiment duration")

### State expectations
- **Loading:** Form skeleton with field placeholders; preview skeleton
- **Dirty:** Unsaved changes indicator in header
- **Validating:** Inline validation on field blur; async validation with spinner
- **Saving:** Save button shows progress; fields disabled during save
- **Error:** Field-level errors highlighted; summary error banner
- **Draft:** "Saved as draft" confirmation; draft metadata in header

### Loading behavior
- Form loads as a skeleton with field shapes
- Preview loads asynchronously with loading indicator in preview panel
- Async validations show inline spinner on the field
- Draft auto-save is silent (no interruption)

### Empty state philosophy
- Editor is never "empty" — it always has default values or placeholders
- First-time users see field hints and help text
- Validation errors guide correction

### Error handling philosophy
- Field-level validation on blur (not on every keystroke for async validators)
- Summary error banner for global validation failures
- Draft saves on network error are queued for retry
- Session recovery restores unsaved editor state

### Responsive behavior
- Desktop: Side-by-side editor + preview
- Tablet: Editor full-width; preview as toggleable bottom panel
- Mobile: Editor full-width; preview accessible via tab or inline sections

### Accessibility considerations
- Form fields have proper `<label>` elements
- Validation messages use `aria-describedby`
- Preview panel is a live region for screen readers
- Keyboard navigation follows logical field order
- Error summary is focusable on validation

### Anti-patterns
- Do not auto-save on every keystroke if validation is expensive
- Do not hide the preview — it is a primary feature
- Do not allow navigation away without confirming discard of unsaved changes
- Do not use modals for complex editors — they deserve full page or side panel
- Do not disable the save button without explanation

---

## Recipe G — Review + Approval

### Purpose
Review an item's full context, evidence, and implications before making a decision (approve, reject, request changes).

### When to use
Use when a human decision is required before proceeding with a change, recommendation, or action.

**Used by:** Recommendation Detail (approve/reject), Config Snapshot Detail (approve/reject/rollback)

### Information hierarchy
```
┌──────────────────────────────────────────────┐
│  Review Header: Title + Status + Metadata    │
├──────────────────┬───────────────────────────┤
│                  │                           │
│  Evidence Panel  │  Decision Panel           │
│  (primary)       │  (sticky)                 │
│                  │                           │
│  ┌────────────┐  │  ┌─────────────────────┐ │
│  │ Summary     │  │  │ Approve (✓)        │ │
│  ├────────────┤  │  │ Reject (✗)         │ │
│  │ Evidence    │  │  │ Request Changes     │ │
│  │ timeline    │  │  │                     │ │
│  ├────────────┤  │  │ Rationale input     │ │
│  │ Risk        │  │  │ [________________] │ │
│  │ assessment  │  │  └─────────────────────┘ │
│  ├────────────┤  │                           │
│  │ Before/after│  │                           │
│  │ comparison  │  │                           │
│  ├────────────┤  │                           │
│  │ Lineage     │  │                           │
│  └────────────┘  │                           │
│                  │                           │
├──────────────────┴───────────────────────────┤
│  Thread / Comments (collapsible)             │
└──────────────────────────────────────────────┘
```

### User goals
- Understand what is being decided
- Review all supporting evidence
- Assess risk and impact
- Make an informed decision
- Document the rationale for the decision
- Complete the approval workflow efficiently

### Primary interactions
- Review evidence summary (expand for detail)
- View before/after comparison (link to Recipe E)
- Assess risk indicators
- Select decision action (approve/reject/request changes)
- Enter decision rationale
- Submit decision
- View decision history and audit trail

### Navigation behavior
- Review screen is typically reached from a list (Recipe B) or dashboard (Recipe A)
- After decision, navigate back to list or to next pending item
- Decision is an immutable artifact — navigating away returns to the decision's read-only view
- Approval flow may chain to next item ("Approve and go to next")

### Conversation integration
- "Review recommendation R-42" opens this recipe
- Conversation can pre-fill the rationale
- Decision result is broadcast to conversation
- "What happens if I approve this?" triggers analysis in conversation

### Artifact integration
- The item under review is an artifact (recommendation, config snapshot)
- Evidence section shows parent artifacts (finding → recommendation)
- Decision creates a DecisionCandidate artifact
- Lineage connects decision to all related artifacts

### Command integration
- `/approve` with optional rationale
- `/reject` with required rationale
- `/request-changes` with required feedback
- `/compare` to open diff view (Recipe E)
- `/audit` to view decision history

### Tool integration
- Risk assessment may invoke an evaluation tool
- Before/after comparison may invoke a diff tool
- Impact analysis may invoke a simulation tool

### State expectations
- **Loading:** Three-panel skeleton (evidence, decision, comments)
- **Decision pending:** All decision actions enabled
- **Decision submitted:** Confirmation state with action badge
- **Error:** Submission failure with retry; rationale preserved

### Loading behavior
- Evidence loads first (primary content)
- Decision panel is always visible and sticky
- Comments thread loads asynchronously
- Risk assessment may load after initial render

### Empty state philosophy
- N/A — review always has a source item
- If evidence is missing, show warning: "Limited evidence available"

### Error handling philosophy
- Submission errors preserve the rationale text
- Evidence load failures show inline error within evidence panel
- Decision panel is never blocked by evidence load failure
- Confirmation timeout shows "Decision recorded but confirmation delayed"

### Responsive behavior
- Desktop: Two-column (evidence + decision); decision panel sticky
- Tablet: Evidence full-width; decision panel as sticky bottom bar
- Mobile: Evidence full-width; decision panel as fixed bottom bar

### Accessibility considerations
- Decision buttons have clear, distinct labels (not just icons)
- Rationale textarea has character count and required indicator
- Evidence panel uses proper heading hierarchy
- Risk indicators use text + icon (not color alone)
- Focus management: auto-focus rationale field after decision selection

### Anti-patterns
- Do not allow approval without rationale for rejections
- Do not hide the decision panel below the fold
- Do not make the approval button green before rationale is entered
- Do not require page reload to see updated decision state
- Do not allow changing a decision after submission

---

## Recipe H — Monitoring + Status

### Purpose
Real-time and historical monitoring of system health, metrics, and component status.

### When to use
Use when the primary user goal is continuous observation of system health, not action.

**Used by:** Operations Control Plane, Capability Health Detail

### Information hierarchy
```
┌──────────────────────────────────────────────┐
│  Header: Overall Status + Time Controls      │
├──────────────────────────────────────────────┤
│  Summary Bar (sticky)                        │
│  ● 12 healthy  ◯ 2 degraded  ◆ 1 down       │
├──────────────────┬───────────────────────────┤
│                  │                           │
│  Health Grid     │  Detail Panel             │
│  (capability     │  (selected capability)    │
│   cards)         │                           │
│                  │  - Metric charts          │
│  ┌────┐┌────┐   │  - Recent events          │
│  │ ●  ││ ◯  │   │  - Related artifacts      │
│  └────┘└────┘   │                           │
│  ┌────┐┌────┐   │                           │
│  │ ◆  ││ ●  │   │                           │
│  └────┘└────┘   │                           │
│                  │                           │
├──────────────────┴───────────────────────────┤
│  Full-width metric charts (optional)         │
└──────────────────────────────────────────────┘
```

### User goals
- Assess overall platform health at a glance
- Identify degraded or failing components
- Inspect metrics for a specific component
- Understand trends over time
- Navigate to related findings or artifacts

### Primary interactions
- Scan health grid — color/icon-coded status per capability
- Click capability card — select and show detail panel
- Filter by status or lifecycle stage
- Toggle time window for metrics
- Navigate to capability detail or findings

### Navigation behavior
- Monitoring screen is a navigation root (depth 0 or 1)
- Clicking capability navigates to its detail (Recipe B or Recipe H detail mode)
- Time window and selected capability persist in URL
- Auto-refresh preserves scroll position

### Conversation integration
- "How is the platform doing?" returns current health summary
- "What happened to the Evidence Engine?" opens its health detail
- Health alerts appear in conversation as notifications

### Artifact integration
- Each monitored component produces artifacts
- Artifact count is shown on capability card
- Related findings link to artifact detail (Recipe B)
- Health metrics are derived from artifact analysis

### Command integration
- `/health` returns status summary
- `/metrics` with capability filter
- `/alerts` to view recent alerts
- `/refresh` to trigger manual health check

### Tool integration
- Health checks are tool executions
- Metric collection tools run on schedule
- Alert condition evaluation is a tool function

### State expectations
- **Loading:** Grid of skeleton cards with status placeholder shapes
- **Empty:** "No capabilities registered" with onboarding guidance
- **Error:** Per-card error with retry; overall status shows "Unknown"
- **Degraded:** Yellow status with degraded indicator and partial data
- **Down:** Red status with failure indicator and last-known data

### Loading behavior
- Health grid loads cards independently — fast components appear first
- Metric charts load after grid (async fetch)
- Detail panel loads on selection
- Auto-refresh updates individual cards without full page flash
- Skeleton cards have realistic proportions matching final layout

### Empty state philosophy
- No capabilities means the platform hasn't been configured
- Provide clear next steps for registering the first capability
- Until then, show the monitoring UI framework with placeholders

### Error handling philosophy
- Individual capability failure doesn't block others
- Stale data persists with "last known" badge
- Polling failures are silent (no toast) — status indicator grays out
- Full API failure shows inline banner with retry

### Responsive behavior
- Desktop: Grid (4 columns) + side detail panel
- Tablet: Grid (2 columns) + detail panel as slide-over
- Mobile: Single column cards; detail as full-screen push

### Accessibility considerations
- Status uses shape + color + text label
- Health grid cards are focusable with arrow key navigation
- Metric charts use accessible data tables as fallback
- Auto-refresh announcements respect `prefers-reduced-motion`
- Status changes use `aria-live="polite"`

### Anti-patterns
- Do not require clicking to see status — make status visible on the card
- Do not use only color to indicate health
- Do not auto-refresh aggressively on mobile connections
- Do not show raw metric values on the grid — use visual indicators
- Do not put monitoring behind an interaction — it should be glanceable

---

## Recipe I — Search + Explore

### Purpose
Search across all artifact types with faceted filtering, results exploration, and rapid navigation.

### When to use
Use when the primary user goal is finding specific items across heterogeneous artifact types.

**Used by:** Artifact Explorer, Global Search (Command Palette)

### Information hierarchy
```
┌──────────────────────────────────────────────┐
│  Search Bar (prominent, auto-focused)        │
├──────────────────────────────────────────────┤
│  Filter Panel (collapsible)                  │
│  Type | Capability | Date | Status           │
├──────────────────────────────────────────────┤
│                                              │
│  Results (grouped by type)                   │
│                                              │
│  Findings (3)                                │
│  ┌─────────────────────────────────────┐    │
│  │ Result 1 — summary line             │    │
│  │ Result 2 — summary line             │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  Recommendations (2)                         │
│  ┌─────────────────────────────────────┐    │
│  │ Result 1 — summary line             │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  Result count: "X results in Y types"        │
└──────────────────────────────────────────────┘
```

Two variants:
- **I1 — Full page:** Artifact Explorer with advanced filters, pagination, and type grouping
- **I2 — Overlay:** Global Command Palette with keyboard-first interaction, type prefixes, and recent items

### User goals
- Find a specific artifact by keyword, ID, or criteria
- Explore available artifacts by type or category
- Navigate quickly to known items (Command Palette)
- Discover items related to search terms

### Primary interactions
- Type to search — results appear asynchronously
- Filter by type, capability, date range, status
- Group results by type
- Click result to navigate to detail
- Command Palette: type-prefix filtering (`f:`, `r:`, `e:`, `c:`)

### Navigation behavior
- Search results are transient — URL encodes query and filters
- Clicking result navigates to artifact detail (Recipe B)
- Back from detail restores search results
- Command Palette closes on navigation (Escape to dismiss)

### Conversation integration
- Conversation can run searches and present results inline
- "Find all findings related to retrieval quality" triggers search
- Search context can be shared to conversation

### Artifact integration
- Every search result is an artifact
- Results show artifact type, ID, title, summary, and timestamp
- Lineage search: "show artifacts related to X"

### Command integration
- Command Palette is the primary command interface
- `/search` with query for full page
- Type prefixes (`f:`, `r:`, `e:`) for scoped search
- `/recent` for recent items

### Tool integration
- Search may invoke a search/index tool
- Search results may include tool-generated previews

### State expectations
- **Loading:** Spinner in search bar (I2) or results skeleton (I1)
- **Empty (no query):** "Type to search artifacts, capabilities, and configs"
- **Empty (no results):** "No results matching your query" with suggestions
- **Error:** "Search failed" with retry in search bar
- **Recent (I2):** Recent searches and artifacts shown before query

### Loading behavior
- Search-as-you-type with debounce (300ms)
- Results appear progressively as each type resolves
- Skeleton shows grouped result placeholders
- Full page search shows skeleton after initial query submission

### Empty state philosophy
- Pre-query: Show recent items and suggested searches
- Post-query: "No results" with alternative search suggestions
- Never show a blank white page for search

### Error handling philosophy
- Search errors allow retry without losing query
- Partial results shown if some types fail
- Network offline shows cached recent results
- Command Palette gracefully degrades to simple text search

### Responsive behavior
- Desktop: Full page (I1) or centered overlay (I2)
- Tablet: Same behavior as desktop
- Mobile: Full-screen overlay (I2); full page with sticky search (I1)
- Filters collapse to bottom sheet on mobile

### Accessibility considerations
- Search results use `role="listbox"` with `aria-activedescendant`
- Live region for result count updates
- Command Palette announces active result
- Keyboard navigation: arrow keys through results, Enter to select
- Escape to close overlay or clear search

### Anti-patterns
- Do not search only in titles — search full content
- Do not require exact matches — support fuzzy search
- Do not show results without type grouping
- Do not hide the filter panel behind interaction on full page
- Do not make the Command Palette feel slow — it should be instant

---

## Recipe J — Settings + Configuration

### Purpose
Manage user or system preferences through structured forms with clear save/confirmation patterns.

### When to use
Use when the user needs to configure preferences, profile settings, or system-level options.

**Used by:** Profile & Preferences, Help & Documentation

### Information hierarchy
```
┌──────────────────────────────────────────────┐
│  Header: Title + Navigation (sections)       │
├──────────────────────────────────────────────┤
│                                              │
│  Section navigation (sidebar or tabs)        │
│                                              │
│  ┌──────────────────────────────────────┐   │
│  │ Section 1                             │   │
│  │ ┌────────────────────────────────┐   │   │
│  │ │ Setting A    [value]           │   │   │
│  │ ├────────────────────────────────┤   │   │
│  │ │ Setting B    [____]           │   │   │
│  │ ├────────────────────────────────┤   │   │
│  │ │ Setting C    [toggle]          │   │   │
│  │ └────────────────────────────────┘   │   │
│  │                                       │   │
│  │ Section 2                             │   │
│  │ ┌────────────────────────────────┐   │   │
│  │ │ Setting D    [value]           │   │   │
│  │ └────────────────────────────────┘   │   │
│  └──────────────────────────────────────┘   │
│                                              │
│  Save / Cancel (sticky bottom)              │
└──────────────────────────────────────────────┘
```

### User goals
- View and modify personal or system preferences
- Understand the impact of each setting
- Find specific settings quickly
- Save changes with confidence

### Primary interactions
- Navigate between sections (sidebar or tabs)
- Toggle boolean settings
- Edit text/numeric fields
- Select from predefined options
- Save or discard changes

### Navigation behavior
- Settings is a self-contained section — navigation is internal
- Unsaved changes prompt confirmation on navigation away
- Saved changes are immediate (no approval workflow for personal settings)
- Deep-link to specific settings section

### Conversation integration
- "Change my notification preferences" opens settings at the correct section
- Conversation can change settings on behalf of user (with confirmation)
- "Show me my current settings" returns summary in conversation

### Artifact integration
- User settings are artifacts (configuration snapshots)
- System-wide settings are ConfigSnapshot artifacts
- Settings changes produce audit trail entries

### Command integration
- `/settings` opens settings at specified section
- `/theme dark` toggles theme without opening settings
- `/shortcuts` shows keyboard shortcut reference

### Tool integration
- N/A — settings are direct mutations, not tool invocations

### State expectations
- **Loading:** Form skeleton with section navigation placeholders
- **Dirty:** Unsaved indicator in header and save button
- **Saving:** Save button shows progress
- **Saved:** "Changes saved" confirmation with optional undo
- **Error:** Field-level errors; save error with retry

### Loading behavior
- Sections load independently (lazy)
- Skeleton shows field shapes matching expected content
- Theme toggle is instant (no API call)
- API tokens load asynchronously with mask/unmask

### Empty state philosophy
- Settings are never empty — defaults always exist
- First-time users see defaults with explanation text
- Empty sections show "No options to configure"

### Error handling philosophy
- Save error preserves all unsaved changes
- Field validation on change + on save
- Network error during save shows inline banner
- Conflicting settings show explanation and recommended fix

### Responsive behavior
- Desktop: Sidebar navigation + content area
- Tablet: Tab navigation + full-width content
- Mobile: Single column, sections as expandable accordions

### Accessibility considerations
- Section navigation uses proper heading hierarchy
- All form controls have labels
- Theme toggle respects system preference as default
- Keyboard shortcut reference is keyboard-navigable
- Color contrast for all themes

### Anti-patterns
- Do not auto-save without confirmation for complex settings
- Do not hide settings behind multiple clicks — they should be 2 clicks max from anywhere
- Do not show settings as modals — they deserve a full page
- Do not require save for toggle-only sections (auto-save toggles)
- Do not mix user settings with system-wide settings without clear separation

---

## Screen-to-Recipe Mapping

All 37 platform screens mapped to exactly one recipe. No screen requires a unique behavioral model.

| # | Screen | Route | Recipe | Rationale |
|---|--------|-------|--------|-----------|
| 1 | Operator Dashboard | `/` | A — Overview + Actions | Aggregate status with drill-down; multi-source attention queue |
| 2 | Conversation Workspace | `/conversation` | C — Conversation + Context | Primary AI interaction surface with context panels |
| 3 | Findings List | `/findings` | B — Collection + Inspector | Standard list + drill-down detail |
| 4 | Finding Detail | `/findings/:id` | B — Collection + Inspector | Detail view of a collection item |
| 5 | Recommendations List | `/recommendations` | B — Collection + Inspector | Standard list + drill-down detail |
| 6 | Recommendation Detail | `/recommendations/:id` | G — Review + Approval | Decision-focused review with approve/reject |
| 7 | Experiments List | `/experiments` | B — Collection + Inspector | Standard list + drill-down detail |
| 8 | Experiment Designer | `/experiments/new` | F — Editor + Preview | Form with live preview before launch |
| 9 | Experiment Detail | `/experiments/:id` | B — Collection + Inspector | Detail view with variant comparison (Recipe E embedded) |
| 10 | Decisions List | `/decisions` | B — Collection + Inspector | Standard list + drill-down detail |
| 11 | Decision Detail | `/decisions/:id` | B — Collection + Inspector | Read-only detail with audit and lineage |
| 12 | Config Snapshots List | `/configuration` | B — Collection + Inspector | Standard list + drill-down; active config banner |
| 13 | Config Snapshot Detail | `/configuration/:id` | G — Review + Approval | Decision-focused review with approve/reject/rollback |
| 14 | Config Diff | `/configuration/diff` | E — Compare + Analysis | Side-by-side or unified diff |
| 15 | CE Dashboard | `/evaluation` | A — Overview + Actions | Scores, trends, and drill-down by capability |
| 16 | Evaluation Detail | `/evaluation/:id` | D — Timeline + Detail | Window metrics with event timeline |
| 17 | Operations Control Plane | `/operations` | H — Monitoring + Status | Health grid with capability status |
| 18 | Capability Health Detail | `/operations/:capabilityId` | H — Monitoring + Status | Deep-dive metrics for one capability |
| 19 | Automation Dashboard | `/automation` | A — Overview + Actions | Job history, schedules, triggers overview |
| 20 | Job Detail | `/automation/jobs/:id` | D — Timeline + Detail | Execution timeline with logs |
| 21 | Schedule Editor | `/automation/schedules` | B — Collection + Inspector | List + create/edit (Recipe F embedded for forms) |
| 22 | Trigger Config | `/automation/triggers` | B — Collection + Inspector | List + create/edit (Recipe F embedded for forms) |
| 23 | Capabilities Registry | `/capabilities` | B — Collection + Inspector | Card grid + drill-down detail |
| 24 | Capability Detail | `/capabilities/:id` | B — Collection + Inspector | Metadata, dependencies, links to health |
| 25 | Learning Ledger Browser | `/ledger` | B — Collection + Inspector | Table + drill-down record detail |
| 26 | Ledger Record Detail | `/ledger/:id` | B — Collection + Inspector | Raw payload and lineage view |
| 27 | Artifact Explorer | `/artifacts` | I — Search + Explore | Faceted search across all artifact types |
| 28 | Artifact Detail | `/artifacts/:id` | B — Collection + Inspector | Metadata, payload, lineage graph |
| 29 | Analytics Overview | `/analytics` | A — Overview + Actions | Category summary cards with drill-down |
| 30 | Analytics Category Detail | `/analytics/:category` | B — Collection + Inspector | Charts and tables for one category |
| 31 | Knowledge Base | `/knowledge` | B — Collection + Inspector | Document list with file operations |
| 32 | Governance Dashboard | `/governance` | A — Overview + Actions | Policy compliance and audit overview |
| 33 | Audit Log | `/governance/audit` | B — Collection + Inspector | Chronological table with filters |
| 34 | Profile & Preferences | `/settings` | J — Settings + Configuration | User preferences and profile |
| 35 | Help & Documentation | `/help` | J — Settings + Configuration | Searchable docs and reference |
| 36 | Notification Panel | (slide-over) | I — Search + Explore | Filtered notification list with navigation |
| 37 | Global Search | (overlay) | I — Search + Explore | Command palette with type-prefixed search |

### Mapping summary

| Recipe | Count | Screens |
|--------|-------|---------|
| A — Overview + Actions | 5 | Operator Dashboard, CE Dashboard, Automation Dashboard, Analytics Overview, Governance Dashboard |
| B — Collection + Inspector | 18 | Findings List, Finding Detail, Recommendations List, Experiments List, Experiment Detail, Decisions List, Decision Detail, Config Snapshots List, Schedule Editor, Trigger Config, Capabilities Registry, Capability Detail, Learning Ledger Browser, Ledger Record Detail, Artifact Detail, Analytics Category Detail, Knowledge Base, Audit Log |
| C — Conversation + Context | 1 | Conversation Workspace |
| D — Timeline + Detail | 2 | Evaluation Detail, Job Detail |
| E — Compare + Analysis | 1 | Config Diff |
| F — Editor + Preview | 1 | Experiment Designer |
| G — Review + Approval | 2 | Recommendation Detail, Config Snapshot Detail |
| H — Monitoring + Status | 2 | Operations Control Plane, Capability Health Detail |
| I — Search + Explore | 2 | Artifact Explorer, Notification Panel, Global Search |
| J — Settings + Configuration | 2 | Profile & Preferences, Help & Documentation |
| **Total** | **37** | |
| J — Settings + Configuration | 2 | Profile & Preferences, Help & Documentation |

---

## Recipe Composition Rules

### Recipes can embed other recipes
- Recipe B (detail) can embed Recipe E (compare) for variant comparison
- Recipe B (list) can embed Recipe F (editor) via "New" action
- Recipe G (review) can embed Recipe E (diff) for before/after comparison
- Recipe A (dashboard) embeds previews of Recipe B (list snippets)

### Recipes can transition to other recipes
- A → B: "View all" or click item to list/detail
- A → G: Click pending approval item to review
- B → F: Click "New" or "Edit" to open editor
- B → G: Escalate finding to recommendation
- C → B: Click artifact reference to navigate
- C → F: "Create experiment" from conversation
- C → G: "Approve recommendation" from conversation
- E → B: Navigate to either compared item

### Recipes that are not navigation roots
- Recipe E (Compare) — always reached from B, F, or G
- Recipe G (Review) — always reached from B or A
- Recipe F (Editor) — always reached from B or C

### Recipes that are navigation roots
- Recipe A (Overview) — root
- Recipe B (Collection) — root
- Recipe C (Conversation) — root (persistent workspace)
- Recipe H (Monitoring) — root
- Recipe I (Search) — root (full page) or overlay
- Recipe J (Settings) — root

---

## Recipe Decision Tree

When designing a new screen, follow this decision tree to determine which recipe to use:

```
Is the primary goal to get an overview / assess status?
  ├─ Yes → Does it aggregate data from multiple sources? → Recipe A
  └─ No  → Continue

Is the primary goal to find and inspect items?
  ├─ Yes → Are items homogeneous in type? → Recipe B
  └─ No  → Continue

Is the primary goal to converse / ask questions?
  ├─ Yes → Recipe C
  └─ No  → Continue

Is the primary goal to understand what happened over time?
  ├─ Yes → Recipe D
  └─ No  → Continue

Is the primary goal to compare two or more items?
  ├─ Yes → Recipe E
  └─ No  → Continue

Is the primary goal to create or modify something?
  ├─ Yes → Recipe F
  └─ No  → Continue

Is the primary goal to make a decision (approve/reject)?
  ├─ Yes → Recipe G
  └─ No  → Continue

Is the primary goal to monitor health and status?
  ├─ Yes → Recipe H
  └─ No  → Continue

Is the primary goal to search for something specific?
  ├─ Yes → Recipe I
  └─ No  → Continue

Is the primary goal to configure preferences?
  ├─ Yes → Recipe J
  └─ No  → Recipe is wrong — challenge the assumption
```

---

## Implementation Guidance

### Each recipe maps to:
1. **A layout component** (the skeleton structure)
2. **Slot components** (content areas populated by screen-specific data)
3. **Behavior hooks** (loading, empty, error, state management)
4. **Navigation patterns** (URL structure, context preservation)
5. **Integration points** (conversation, artifacts, commands, tools)

### Recipe documentation in code
Each recipe should be documented as:
```
recipes/
  overview-actions/      # Recipe A
    layout.tsx
    behaviors.ts
    slots.ts
    README.md
  collection-inspector/  # Recipe B
    ...
```

### Screen implementation
Implementing a screen means:
1. Choose the recipe
2. Configure the slots with screen-specific components
3. Wire the data sources (API endpoints)
4. Configure navigation patterns
5. Set behavior configuration (loading, empty, error states)

---

## Anti-Pattern Catalog

### Recipe-level anti-patterns

| Anti-pattern | Violates | Instead |
|---|---|---|
| Using Recipe A for single-source data | Recipe A purpose | Use Recipe B with summary widget |
| Using Recipe B for approval workflows | Recipe B purpose | Use Recipe G with Recipe B as parent |
| Building a screen that doesn't fit any recipe | Recipe reduction goal | Challenge: is this a valid screen? |
| Creating a unique screen "because it's special" | Consistency principle | Every screen can be expressed as a recipe variant |
| Modifying a recipe for one screen | Reusability | Create a variant within the recipe |

### Cross-recipe anti-patterns

| Anti-pattern | Problem |
|---|---|
| Recipe B detail opens as modal over list | Loses list context; prefer side panel or full page |
| Recipe A showing raw artifact data | Recipe A shows summaries only; click for detail |
| Recipe G without Recipe E integration | Approval without diff is blind approval |
| Recipe G decision panel below the fold | Decision panel must always be visible |
| Recipe F without preview | Editor without preview forces guesswork |
| Recipe H with real-time auto-refresh on mobile | Battery and data usage; respect connection |

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-07-25 | Architecture | Initial recipe definitions and mapping |
