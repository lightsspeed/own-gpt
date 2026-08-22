# Cross-Experience Interaction Patterns

> Interaction patterns are reusable behavioral recipes.
>
> The same pattern should work identically whether it appears in the Assistant, Dashboard, Operations Console, Search, Notifications, or Timeline.
>
> Screens do not define behavior — patterns do.

---

## Purpose

### Why Interaction Patterns Are More Valuable Than Screen-Specific Behavior

Every screen-specific behavior is a liability. It must be learned, documented, tested, and maintained independently. As the platform grows, screen-specific behaviors multiply, consistency degrades, and the user must relearn interaction patterns for each module.

Interaction patterns invert this. A small set of reusable patterns (20-25) covers the vast majority of user interactions across the entire platform. New screens compose from existing patterns rather than inventing new behavior. Users learn the patterns once and apply them everywhere.

### How Patterns Create Consistency Across Experiences

| Experience | Pattern | Example |
|---|---|---|
| Assistant | Conversation + Context | AI response with artifact side panel |
| Dashboard | Overview → Drill Down | Widget click → Module detail |
| Operations Console | List → Detail | Findings list → Finding detail |
| Search | Search → Explore | Query → Result → Related artifact |
| Notifications | Alert → Investigation | Notification click → Investigation |
| Timeline | Timeline → Inspector | Event click → Event detail |

The same pattern — List → Detail — behaves identically whether the list contains findings, experiments, decisions, or config snapshots. The content differs; the interaction does not.

---

## Pattern Philosophy

### One pattern, many contexts

A pattern is defined once and applied everywhere. "List → Detail" is the same pattern for findings, experiments, recommendations, decisions, and config snapshots. The pattern defines how the list filters, how selection works, and how the detail opens — the content is the only variable.

### Behavior before layout

Patterns define behavior first. They specify what happens, in what order, and what the user experiences. Layout (side panel vs full page, left vs right) is a presentation decision that can vary by context without changing the pattern's behavioral contract.

### Composition over specialization

Complex workflows should be compositions of simple patterns, not special-case implementations. An investigation workflow composes Alert → Investigation + Evidence → Explanation + Compare + Recommendation → Decision. Each sub-pattern is independently reusable.

### Patterns are predictable

Users should be able to predict what will happen when they encounter a familiar pattern in a new context. If they know "List → Detail" from the findings module, they should know exactly how it works in the experiments module.

### Patterns reduce cognitive load

Users do not need to learn 35 screen-specific interaction models. They learn 20 patterns and can navigate any screen by recognizing which pattern is in use.

### Patterns preserve context

Patterns define what context is carried between stages. "Overview → Drill Down" carries the time window and filters. "List → Detail" carries the list state. Context preservation is part of the pattern contract.

### Patterns should be reusable

A pattern is only added to the catalog if it can be used in at least two different contexts. Single-use patterns are not patterns — they are screen-specific behavior and should be documented as such.

### Patterns should evolve slowly

Patterns represent stable interaction knowledge. They should not change frequently. When a pattern needs to evolve, the change must be validated across all contexts where the pattern is used.

---

## Pattern Catalog

---

### Pattern 1: List → Detail

**Purpose:** Browse a collection of items, select one, and inspect its details. Return to the list with context preserved.

**When to use:** Any collection of homogeneous artifacts where the user needs to browse, select, and inspect individual items.

**Expected behavior:**
1. User sees a paginated list of items with summary information.
2. User can filter, sort, and search the list.
3. User clicks an item to open its detail view.
4. Detail view replaces or overlays the list (depending on context).
5. User returns to the list at the exact position, filter, and scroll state they left it.

**State expectations:**
- List: Idle → Filtering (reactive) → Item Selected → Detail Open
- Detail: Loading → Displayed → (actions)
- Return to list restores previous list state

**Navigation expectations:**
- List → Detail: Side panel (quick inspection) or full page (deep work)
- Detail → List: Back, close panel, breadcrumb
- Navigation preserves list filters, scroll position, and selection

**Conversation integration:**
- Selecting an item from the list can be recorded in the active conversation
- "Open in Assistant" action on any list item starts a conversation about that item

**Artifact integration:**
- Each list item is an artifact card (type icon, ID, title, status, summary)
- Click navigates to the artifact's universal detail view

**Command integration:**
- "Show [type] list" opens the list
- "Open [artifact ID]" navigates directly to the detail (skipping the list)
- List supports batch commands: "Acknowledge selected", "Export selected"

**Tool integration:**
- List data is retrieved via Read or Search tools
- Actions on list items (acknowledge, dismiss) may invoke mutation tools
- Long lists may stream results

**Anti-patterns:**
- List that resets on return from detail
- Detail that opens in a new window/tab without context
- List that does not show item count
- List that hides available filters

---

### Pattern 2: Conversation + Context

**Purpose:** The user converses with the AI assistant while contextual information (artifacts, evidence, timelines) is displayed alongside the conversation.

**When to use:** Any interaction where the user asks questions, investigates, or makes decisions with the assistant's help.

**Expected behavior:**
1. User asks a question or issues a command in the conversation input.
2. Assistant processes and responds. Response includes artifact references.
3. Context panel updates to show relevant artifacts, evidence, or timelines.
4. User can click artifact references to inspect in the context panel.
5. Context panel content changes as the conversation evolves.
6. User can pin artifacts to keep them in the context panel.

**State expectations:**
- Conversation: Active → Processing → Streaming → Active
- Context Panel: Idle → Loading → Displayed → Updated
- Pinned items remain in context across conversation turns

**Navigation expectations:**
- Clicking an artifact reference in a response opens it in the context panel
- "Open in Console" action on a context panel item navigates to the full Operations Console
- Back from console returns to the conversation

**Conversation integration:**
- This pattern defines the primary assistant interface
- The context panel is conversation-scoped — it shows artifacts relevant to the current conversation

**Artifact integration:**
- Artifact references are rendered as inline links in conversation responses
- Clicking an artifact link opens it in the context panel
- The context panel shows artifact summary, key evidence, and actions

**Command integration:**
- Typing in the conversation input is a command — the assistant resolves intent
- Commands from the palette can continue the current conversation
- Suggested next actions appear as clickable chips

**Tool integration:**
- Assistant tool invocations appear inline in the conversation
- Tool results populate the context panel when relevant

**Anti-patterns:**
- Context panel that does not update as the conversation progresses
- Artifact references in responses that are not clickable
- Context that resets when the conversation moves to a new subject
- Context panel that shows no information (empty state should be helpful)

---

### Pattern 3: Overview → Drill Down

**Purpose:** Present a summarized view of platform state (dashboard, health, summary) and allow the user to drill into specific areas for detail.

**When to use:** Dashboards, health summaries, evaluation overviews, daily briefs — any screen where the primary purpose is situational awareness and the secondary purpose is action.

**Expected behavior:**
1. User sees a summary of key metrics, statuses, and pending items.
2. Summary items are clickable — each drives to a specific detail view.
3. User clicks a summary item (widget, card, metric).
4. Platform navigates to the relevant module or detail view with context.
5. User can return to the overview, which preserves its previous state.

**State expectations:**
- Overview: Idle → (no loading — summaries are lightweight) → Displayed
- Drill-down: Destination loads with context from overview

**Navigation expectations:**
- Summary items navigate to full detail views
- Each widget has exactly one primary navigation target
- Filters applied in the overview carry to the detail

**Conversation integration:**
- "Explain this" action on any summary item starts an assistant conversation
- Overview summaries can be discussed in the assistant

**Artifact integration:**
- Summary items may represent artifact counts (findings, experiments, decisions)
- Clicking a count navigates to the filtered artifact list

**Command integration:**
- "Show overview" or "Show dashboard" opens this pattern
- Commands that change filters update the overview

**Tool integration:**
- Overview data is retrieved via Read tools (health, counts, summaries)
- Overview is not the place for long-running tool invocations

**Anti-patterns:**
- Summary items that are not clickable
- Overview that takes too long to load (target: < 500ms)
- Widgets that navigate to different destinations depending on context
- Overview that shows data without indicating its freshness

---

### Pattern 4: Timeline → Inspector

**Purpose:** Display a chronological sequence of events and allow the user to inspect individual events in detail.

**When to use:** Activity history, audit logs, learning ledger, evaluation timelines, automation run history.

**Expected behavior:**
1. User sees a chronological list of events.
2. Events are grouped by time (Today, Yesterday, This Week, Earlier).
3. User clicks an event to inspect its details.
4. Inspector panel shows the event's metadata, context, and related artifacts.
5. User can navigate to related events backward and forward.

**State expectations:**
- Timeline: Loading → Displayed → (filtered/scrolled)
- Inspector: Closed → Loading → Displayed
- Timeline preserves scroll position and filter

**Navigation expectations:**
- Event click opens inspector (side panel or inline expansion)
- Inspector may contain links to full detail views of related artifacts
- Timeline events support deep linking to specific moments

**Conversation integration:**
- "What happened at this time?" can be answered from the timeline
- Timeline events can be attached to conversations as context

**Artifact integration:**
- Each timeline event represents or references an artifact
- Clicking an event shows its artifact's summary

**Command integration:**
- "Show timeline" opens the timeline view
- "Show events from last 24 hours" filters the timeline

**Tool integration:**
- Timeline data is retrieved via Read or Search tools
- Long timelines may stream or paginate

**Anti-patterns:**
- Timeline that shows raw timestamps without grouping
- Events that are not inspectable
- Timeline that does not indicate when new events are available
- Timeline that resets scroll on data refresh

---

### Pattern 5: Search → Explore

**Purpose:** User searches for artifacts or information and explores the results through relationships.

**When to use:** Global search, module-specific search, artifact discovery.

**Expected behavior:**
1. User types a search query.
2. Results appear grouped by artifact type.
3. User selects a result to see its summary.
4. User can explore related artifacts from the result.
5. Search history and recent searches are available.

**State expectations:**
- Search: Closed → Open → Typing → Searching → Results Displayed
- Result Inspection: Summary → Detail (optional)
- Search state is preserved (query, filters, results page)

**Navigation expectations:**
- Selecting a result navigates to its detail view (or opens summary inline)
- Exploring related artifacts from a result creates a navigation chain
- "Back to search results" returns to the search state

**Conversation integration:**
- Search can be initiated from the assistant: "Search for latency findings"
- Search results can be attached to conversations
- The assistant can perform searches on the user's behalf

**Artifact integration:**
- All artifact types are searchable
- Search results show artifact type icon, ID, title, status, and timestamp

**Command integration:**
- Any text typed in the command palette that is not a recognized command falls through to search
- "/search" prefix forces search mode

**Tool integration:**
- Search invokes the Search tool
- Results may stream as they are found

**Anti-patterns:**
- Search that does not group results by type
- Search that requires exact keyword matching (support natural language and fuzzy)
- Search results that are not navigable
- Search that clears on navigation

---

### Pattern 6: Alert → Investigation

**Purpose:** An alert (notification, critical finding, health degradation) triggers an investigation workflow.

**When to use:** Incoming notifications, critical findings, health status changes, automation failures.

**Expected behavior:**
1. User receives an alert (notification, badge, dashboard indicator).
2. User clicks the alert.
3. Platform opens an investigation context: a new conversation or an existing one related to the alert's subject.
4. Assistant pre-populates context with the alert's artifact and evidence.
5. User investigates with the assistant, following the natural investigation workflow.
6. Investigation concludes with a decision (acknowledge, escalate, dismiss).

**State expectations:**
- Alert: Created → Delivered → Read → Actioned
- Investigation: New → Active → (investigation lifecycle)
- The alert is marked as Actioned when the investigation concludes

**Navigation expectations:**
- Alert click navigates to the investigation context
- If the user is already in an active conversation, the alert may create a branch
- Investigation may navigate to artifact details as needed

**Conversation integration:**
- The investigation IS a conversation
- The alert becomes the first message in the conversation context

**Artifact integration:**
- The alert references a source artifact (finding, health report, automation run)
- The artifact is pinned in the investigation context

**Command integration:**
- Notifications and alerts can be managed through commands
- "Acknowledge all" batch command for non-critical alerts

**Tool integration:**
- Investigation may invoke Read, Search, Analyze, and Compare tools
- Conclusions may invoke Generate or Recommend tools

**Anti-patterns:**
- Alert that navigates to a static detail page instead of an investigation
- Alert that does not carry context to the investigation
- Investigation that starts without acknowledging the alert
- Alert that requires action but provides no investigation path

---

### Pattern 7: Notification → Conversation

**Purpose:** A notification triggers or resumes a conversation about the notified event.

**When to use:** Any notification that warrants discussion: experiment completed, approval requested, finding generated, config change applied.

**Expected behavior:**
1. User receives a notification.
2. User clicks the notification.
3. Platform opens the relevant conversation (existing or new).
4. If new, the notification's context becomes the conversation seed.
5. If existing, the conversation scrolls to the relevant point.
6. User can discuss the notification with the assistant.

**State expectations:**
- Notification: Created → Delivered → Read → Actioned
- Conversation: Active or Resumed
- Notification marked as Actioned when conversation reaches a conclusion

**Navigation expectations:**
- Notification → relevant conversation or new conversation
- Conversation may reference the notification artifact
- User can return to the notification list from the conversation

**Conversation integration:**
- The notification becomes part of the conversation context
- The assistant is aware of the notification and can discuss it

**Artifact integration:**
- The notification references an artifact that becomes conversation context

**Command integration:**
- Notifications can be actioned via commands
- "Show notifications" opens the notification list

**Tool integration:**
- The assistant may invoke tools to gather context about the notification's subject

**Anti-patterns:**
- Notification that opens a blank conversation with no context
- Notification that cannot be discussed with the assistant
- Notification that is dismissed by clicking but not actioned

---

### Pattern 8: Dashboard → Action

**Purpose:** A dashboard widget surfaces a pending action item, and the user acts on it from the dashboard without navigating away.

**When to use:** Dashboard widgets that show pending items (approvals, acknowledgments, reviews).

**Expected behavior:**
1. User sees a pending action item in a dashboard widget.
2. User can perform quick actions directly on the widget: acknowledge, approve, dismiss.
3. Actions update the widget state immediately (optimistic).
4. For complex actions, the widget provides a single-click path to the full action workflow.
5. Widget refreshes after the action to show updated state.

**State expectations:**
- Action item: Pending → (quick action executed) → Updated
- Widget: Displayed → (action in progress) → Updated
- Optimistic update shows immediate feedback

**Navigation expectations:**
- Quick actions do not navigate
- "View all" or "Full review" navigates to the relevant list
- Complex actions (approve config) navigate to the full workflow

**Conversation integration:**
- "Investigate in Assistant" action opens a conversation about the item

**Artifact integration:**
- Each action item represents or references an artifact
- Quick actions may change artifact state

**Command integration:**
- Quick actions are available from the command palette
- "Acknowledge latest finding" can be a command

**Tool integration:**
- Quick actions invoke lightweight tools
- Complex actions defer to full tool workflows

**Anti-patterns:**
- Dashboard widget that shows items but provides no actions
- Dashboard that requires navigation for every action
- Dashboard that does not update after an action
- Widget that shows stale action items

---

### Pattern 9: Artifact → Lineage

**Purpose:** From any artifact, the user can view and navigate the artifact's lineage — its parents, children, and relationships.

**When to use:** Any artifact detail view where understanding origin and impact is relevant.

**Expected behavior:**
1. User is viewing an artifact detail.
2. User opens the lineage view (tab, panel, or action).
3. Lineage graph shows the artifact's parents (what created it) and children (what depends on it).
4. Graph is interactive — user can click nodes to navigate.
5. User can expand/collapse lineage depth.
6. User can filter lineage by relationship type.

**State expectations:**
- Lineage: Closed → Loading → Displayed → (interaction)
- Node click: navigates to the selected artifact
- Lineage state is independent of the main artifact view

**Navigation expectations:**
- Lineage node click navigates to the selected artifact
- Navigation preserves the lineage view's position
- Breadcrumb shows lineage navigation path

**Conversation integration:**
- "Show me the lineage" assistant command opens the lineage view
- Lineage path can be attached to a conversation as context

**Artifact integration:**
- Lineage IS artifact relationship navigation
- The current artifact is the center of the graph

**Command integration:**
- "Show lineage for [artifact]" opens lineage
- "Trace [artifact] to root" expands the full upstream lineage

**Tool integration:**
- Lineage data is retrieved via a Read tool (artifact relationships API)

**Anti-patterns:**
- Lineage that shows only one level (no expandability)
- Lineage that does not differentiate relationship types
- Lineage that is not interactive
- Lineage that does not show the current artifact as the center

---

### Pattern 10: Evidence → Explanation

**Purpose:** The user encounters evidence (a metric, a finding, a data point) and the AI explains its meaning, context, and significance.

**When to use:** Any evidence, finding, metric, or data point in any context — conversation, list, detail, dashboard, timeline.

**Expected behavior:**
1. User encounters an evidence item.
2. User triggers "Explain" action (click, hover, command).
3. AI generates a natural language explanation of the evidence.
4. Explanation includes: what the evidence means, why it matters, how it relates to the current context, and what actions might be relevant.
5. Explanation is grounded in the evidence's source artifact.

**State expectations:**
- Explanation: Hidden → Generating → Streaming → Displayed
- Evidence: unchanged

**Navigation expectations:**
- Explanation is inline — no navigation
- Explanation may contain artifact links that the user can click

**Conversation integration:**
- Explanation can be added to the active conversation
- User can ask follow-up questions about the explanation

**Artifact integration:**
- The evidence is an artifact or is attached to an artifact
- Explanation references the source artifact

**Command integration:**
- "Explain" is a universal artifact action
- Available from any artifact context menu

**Tool integration:**
- Explanation may invoke the Explain AI capability
- The assistant may retrieve additional context to provide a thorough explanation

**Anti-patterns:**
- Explanation that is too long and not collapsible
- Explanation that does not reference the evidence
- Explanation that fabricates context
- Explanation that is not available for evidence

---

### Pattern 11: Tool → Progress

**Purpose:** A tool is executing and the user can observe progress, intermediate results, and completion.

**When to use:** Any tool invocation that takes more than 2 seconds.

**Expected behavior:**
1. Tool execution begins.
2. Progress indicator appears with: tool name, current stage, elapsed time.
3. For long-running tools (> 10s): estimated time remaining, intermediate results.
4. User can cancel the tool execution.
5. On completion: results appear. On failure: error with recovery options.

**State expectations:**
- Tool: Starting → Running → (progress updates) → Completed / Failed / Cancelled
- Progress: Hidden → Visible → Result / Error

**Navigation expectations:**
- Progress is inline in the current context
- User can navigate away during long-running tools (background execution)
- Returning shows current progress or completion

**Conversation integration:**
- Tool progress appears inline in the conversation
- Completion updates the conversation with results

**Artifact integration:**
- Tool may produce artifacts on completion

**Command integration:**
- "Show running tasks" lists active tool executions
- "Cancel [task]" cancels a running tool

**Tool integration:**
- This pattern defines the tool execution UX

**Anti-patterns:**
- Indeterminate spinner for operations > 5 seconds
- No progress information for operations > 2 seconds
- No cancellation option for operations > 10 seconds
- Progress that disappears and reappears

---

### Pattern 12: Command → Result

**Purpose:** User issues a command (from palette, assistant, or shortcut) and receives the result inline.

**When to use:** Any command execution.

**Expected behavior:**
1. User invokes a command (⌘K, assistant, shortcut).
2. Command resolves and executes.
3. Result appears inline — in the command palette, the conversation, or a temporary overlay.
4. Result may be: information, navigation, artifact, or confirmation.
5. User can act on the result or dismiss it.

**State expectations:**
- Command: Invoked → Resolving → Executing → Completed / Failed
- Result: Hidden → Displayed → (user acts or dismisses)

**Navigation expectations:**
- Results that are information: stay inline
- Results that are navigation: navigate to destination
- Results that are artifacts: show artifact card with link

**Conversation integration:**
- Commands are recorded in the active conversation
- Results are part of the conversation history

**Artifact integration:**
- Commands that produce artifacts show artifact cards

**Command integration:**
- This pattern IS the command system's primary UX

**Tool integration:**
- Commands may invoke tools. Tool progress follows the Tool → Progress pattern.

**Anti-patterns:**
- Command that executes silently
- Command that navigates without showing a result
- Command that does not show progress
- Command that cannot be cancelled

---

### Pattern 13: Recommendation → Decision

**Purpose:** The assistant presents a recommendation, and the user evaluates and decides.

**When to use:** Any recommendation (config change, experiment launch, finding escalation, automation trigger).

**Expected behavior:**
1. Recommendation is presented with: summary, evidence, confidence, expected impact, alternatives.
2. User reviews the recommendation and supporting evidence.
3. User approves, rejects, or requests modifications.
4. Decision is recorded as an artifact with lineage to the recommendation.
5. If approved, the recommended action enters the execution workflow.

**State expectations:**
- Recommendation: Presented → Under Review → Decided (Approved / Rejected / Modified)
- Decision: Created → Recorded

**Navigation expectations:**
- Recommendation is inline (conversation, detail view)
- Reviewing evidence may open related artifacts
- Decision is recorded without navigation

**Conversation integration:**
- Recommendations appear in conversations
- Decisions become part of the conversation history

**Artifact integration:**
- Recommendation is an artifact
- Decision is an artifact with lineage to the recommendation
- Evidence artifacts are linked

**Command integration:**
- "Approve", "Reject", "Modify" are available as commands on recommendation artifacts

**Tool integration:**
- Recommendation may have been generated by a Recommend tool
- Decision may trigger subsequent tool invocations

**Anti-patterns:**
- Recommendation without evidence
- Recommendation without confidence
- Approval that does not record the decision
- Rejection that does not capture the reason

---

### Pattern 14: Experiment → Evaluation

**Purpose:** An experiment is launched, runs for a duration, produces results, and is evaluated.

**When to use:** Experiment lifecycle.

**Expected behavior:**
1. Experiment is defined and launched.
2. Experiment runs for its configured duration.
3. User can monitor progress during the run.
4. On completion, results are available for comparison.
5. Results include: metric comparison, statistical significance, winner declaration.
6. User evaluates results and decides next steps.

**State expectations:**
- Experiment: Draft → Running → Completed / Failed → (evaluated)
- Evaluation: Pending → Available → Reviewed

**Navigation expectations:**
- Experiment detail is a full-page view (deep work)
- Monitoring during run may be inline or notification-based

**Conversation integration:**
- Experiment results are discussed in conversations
- "Compare" action opens the comparison view
- Winner declaration creates a decision artifact

**Artifact integration:**
- Experiment, results, and decisions are artifacts
- Lineage: Recommendation → Experiment → Decision

**Command integration:**
- "Launch experiment", "Compare results", "Declare winner" are commands

**Tool integration:**
- Experiment execution uses the Experiment tool
- Evaluation uses the Evaluate tool

**Anti-patterns:**
- Experiment that does not show progress during run
- Results that do not include statistical significance
- Comparison that does not highlight differences
- No clear winner declaration path

---

### Pattern 15: Configuration → Preview

**Purpose:** A configuration change is proposed and the user previews the diff before approving.

**When to use:** Any configuration change — snapshot creation, parameter update, rollback.

**Expected behavior:**
1. Configuration change is proposed (by assistant, automation, or manual).
2. Preview shows the diff: what changed, what stayed the same.
3. Diff is presented as side-by-side or unified view.
4. User reviews the diff and associated risk assessment.
5. User approves, rejects, or requests changes.
6. On approval, the configuration is applied.
7. Rollback plan is available before and after application.

**State expectations:**
- Change: Proposed → Previewing → Approved / Rejected → Applied / Reverted
- Preview: Hidden → Displayed → (decision)

**Navigation expectations:**
- Preview is inline or full-page (preference for inline for simple changes)
- Full-page preview for complex changes

**Conversation integration:**
- Configuration changes are discussed in conversations
- Preview can be attached to a conversation

**Artifact integration:**
- Configuration snapshots are artifacts
- Diff is a comparison of two snapshot artifacts

**Command integration:**
- "Show diff", "Approve config", "Rollback" are commands

**Tool integration:**
- Configuration management tools handle the diff and application

**Anti-patterns:**
- Config change proposed without a preview
- Diff that is not human-readable (raw JSON only)
- No risk assessment with the preview
- Approval that does not require review

---

### Pattern 16: History → Restore

**Purpose:** User browses the history of an artifact, conversation, or workspace and restores a previous state.

**When to use:** Artifact version history, conversation history, config snapshot history, workspace state recovery.

**Expected behavior:**
1. User opens the history view for an entity.
2. History shows all state transitions with timestamps and actors.
3. User selects a historical state to preview.
4. Preview shows what the state looked like at that point.
5. User can restore the previous state (if applicable).
6. Restore creates a new artifact (rollback snapshot, restored version).

**State expectations:**
- History: Loading → Displayed → (select) → Preview → (restore decision)
- Restore: Confirmed → Executed → New artifact created

**Navigation expectations:**
- History is accessible from any artifact detail
- Selecting a historical state shows a preview inline or in a panel

**Conversation integration:**
- History can be discussed in conversations
- Restoration decisions are recorded in conversation history

**Artifact integration:**
- History is a view of an artifact's state transitions
- Restoration creates a new artifact with lineage to the restored state

**Command integration:**
- "Show history", "Restore to [version]" are commands

**Tool integration:**
- History retrieval uses Read tools
- Restoration uses Config or mutation tools

**Anti-patterns:**
- History that shows timestamps without context
- History that cannot be browsed (only shows latest)
- Restoration that overwrites history (restore creates a new artifact, does not delete old)
- Restoration without confirmation

---

### Pattern 17: Collection → Filter → Refine

**Purpose:** User starts with a broad collection of artifacts and progressively narrows to a specific subset.

**When to use:** Any list view where users need to find specific items: findings, experiments, decisions, configs, artifacts.

**Expected behavior:**
1. User sees a collection with default filters (time window, status).
2. User can add filters by type, status, capability, owner, severity, etc.
3. Collection updates reactively as filters are applied.
4. User can see active filters and remove individual filters.
5. Refined collection can be saved as a view or exported.

**State expectations:**
- Collection: Loading → Displayed → (filtering) → Refined
- Filters reflect in URL for shareability

**Navigation expectations:**
- Filtering does not navigate — collection updates in place
- Saved views are navigable

**Conversation integration:**
- "Show me findings from last 24 hours with critical severity" translates to a filtered collection
- Filtered collections can be attached to conversations

**Artifact integration:**
- The collection contains artifacts of the selected type

**Command integration:**
- "Show findings", "filter by severity:critical" are commands

**Tool integration:**
- Collections are populated via Read or Search tools
- Filtering may be client-side or server-side depending on collection size

**Anti-patterns:**
- Filters that reset on navigation
- Filters that are not reflected in the URL
- No way to see active filters
- Filtering that requires page reload

---

### Pattern 18: Review → Approve

**Purpose:** A user reviews pending items in a structured workflow and makes approval decisions.

**When to use:** Approval queues, review workflows, batch operations.

**Expected behavior:**
1. User opens a review queue (pending approvals, pending reviews).
2. Queue shows items grouped by type and priority.
3. User reviews each item: sees summary, evidence, impact.
4. User approves or rejects each item.
5. Batch operations available for similar items.
6. Decisions are recorded with lineage and timestamp.

**State expectations:**
- Queue: Loading → Displayed → (reviewing) → (decisions made)
- Each item: Pending → Reviewed → Approved / Rejected

**Navigation expectations:**
- Review is inline (no navigation per item)
- Complex items may open detail for full review
- Returning to the queue shows updated state

**Conversation integration:**
- Review items can be discussed in conversations
- Approval decisions are recorded in conversation history

**Artifact integration:**
- Each review item is an artifact
- Approval decisions are decision artifacts

**Command integration:**
- "Show approval queue", "Approve", "Reject" are commands
- Batch commands for bulk operations

**Tool integration:**
- Queue data from Read tools
- Approvals invoke decision tools

**Anti-patterns:**
- Review queue that requires per-item navigation
- No batch operations for similar items
- Approval that does not show the item being approved
- No way to reject with a reason

---

### Pattern 19: Observe → Investigate → Decide → Act → Verify

**Purpose:** End-to-end decision workflow: observe a condition, investigate its causes, decide on action, execute, and verify the outcome.

**When to use:** Any significant platform workflow: health degradation response, finding remediation, experiment evaluation.

**Expected behavior:**
1. **Observe:** User notices a condition (dashboard widget, notification, finding).
2. **Investigate:** User investigates with the assistant — gathers evidence, traces lineage, explores related artifacts.
3. **Decide:** User evaluates options and makes a decision (acknowledge, escalate, recommend, approve).
4. **Act:** Decision is executed (config change, experiment launch, finding dismissal).
5. **Verify:** Outcome is checked. Did the action produce the expected result?

**State expectations:**
- Observe: Condition detected → User aware
- Investigate: Conversation Active → Evidence Gathered → Hypothesis Formed
- Decide: Options Presented → Decision Made
- Act: Action Executed
- Verify: Outcome Checked → Confirmed or Flagged

**Navigation expectations:**
- Each stage may involve different views
- The assistant is the consistent thread across all stages
- Users can move between stages without losing progress

**Conversation integration:**
- The entire workflow can happen within a single conversation
- Each stage is recorded in the conversation history
- The assistant guides the transition between stages

**Artifact integration:**
- Each stage produces or references artifacts
- Observe: finding or health report
- Investigate: evidence artifacts
- Decide: decision artifact
- Act: config snapshot, experiment run
- Verify: evaluation result

**Command integration:**
- Each stage has corresponding commands
- "Investigate this", "Create recommendation", "Approve", "Verify outcome"

**Tool integration:**
- Each stage may invoke different tools
- Observe: Read tools
- Investigate: Search, Read, Analyze tools
- Decide: Recommend tools
- Act: Config, Experiment, or Automation tools
- Verify: Evaluate tools

**Anti-patterns:**
- Stages that are not connected by a conversation
- Investigation that does not lead to a decision
- Action that skips verification
- Workflow that cannot be resumed if interrupted

---

## Pattern Composition

### How Patterns Compose into Workflows

Complex workflows are compositions of multiple patterns. Each pattern handles one phase of the workflow, and the phases are connected by the conversation.

**Example: Responding to a Health Degradation**

```
Stage 1: Dashboard → Action (or Alert → Investigation)
    └─ User notices health degradation on the dashboard widget.
    └─ User clicks "Investigate" → opens assistant conversation.

Stage 2: Conversation + Context
    └─ User asks: "Why did health decrease?"
    └─ Assistant retrieves evidence (Tool → Progress).
    └─ Context panel shows relevant findings.

Stage 3: List → Detail (via relationship links)
    └─ Assistant references Finding #1024.
    └─ User clicks finding → opens in context panel or console.
    └─ User reviews evidence (Evidence → Explanation).

Stage 4: Artifact → Lineage
    └─ User traces finding to its root cause (config change v141).
    └─ User reviews the config diff (Configuration → Preview).

Stage 5: Recommendation → Decision
    └─ Assistant recommends reverting the config change.
    └─ User approves (Review → Approve).

Stage 6: Configuration → Preview → Apply
    └─ Config change is applied.
    └─ System verifies health improvement (Observe → Investigate → Decide → Act → Verify).
```

### Composition Rules

1. Patterns compose sequentially. The output of one pattern becomes the input context for the next.
2. The conversation is the glue that connects patterns. Each pattern may produce artifacts and conversation entries.
3. Not every workflow uses every pattern. Compose only the patterns needed.
4. Patterns can nest. A pattern's detail view may contain another pattern internally.
5. Composed workflows are themselves reusable. Common compositions become templates (see Screen Recipes).

---

## Pattern Consistency Rules

1. The same pattern must behave identically regardless of which experience invokes it (Assistant, Dashboard, Console, Search, Notifications, Timeline).
2. Patterns are context-adaptive but behavior-invariant. The content may change; the interaction sequence does not.
3. A pattern's actions (commands, buttons, gestures) are the same wherever the pattern appears.
4. A pattern's state behavior is the same wherever the pattern appears.
5. A pattern's navigation behavior is the same wherever the pattern appears.
6. Patterns cannot be overridden by specific screens. If a screen needs different behavior, it should use a different pattern.
7. All patterns are documented in this catalog. No undocumented pattern variations exist.

---

## AI Responsibilities

| Pattern | Assistant Role |
|---|---|
| List → Detail | Can navigate lists, open details, summarize items. |
| Conversation + Context | This IS the assistant's primary interface. |
| Overview → Drill Down | Can explain overview items, suggest drill-down targets. |
| Timeline → Inspector | Can explain timeline events, summarize time periods. |
| Search → Explore | Can perform searches, suggest search refinements. |
| Alert → Investigation | Initiates investigations, guides the process. |
| Notification → Conversation | Opens conversation with notification context. |
| Dashboard → Action | Can suggest actions based on dashboard state. |
| Artifact → Lineage | Can trace lineage, explain relationships. |
| Evidence → Explanation | Provides explanations for evidence. |
| Tool → Progress | Reports progress, handles interruptions. |
| Command → Result | Interprets commands, presents results. |
| Recommendation → Decision | Presents recommendations, facilitates decisions. |
| Experiment → Evaluation | Monitors progress, presents results. |
| Configuration → Preview | Generates previews, explains diffs. |
| History → Restore | Explains history, guides restoration. |
| Collection → Filter → Refine | Translates natural language to filters. |
| Review → Approve | Prepares review context, suggests priorities. |
| Observe → Investigate → Decide → Act → Verify | Guides the full end-to-end workflow. |

### Assistant Participation Rules

1. The assistant can participate in any pattern but never overrides the pattern's behavioral contract.
2. The assistant's role in a pattern is to augment, not replace, the pattern's core interaction.
3. Users can choose to use the assistant within any pattern or interact directly with the pattern's UI.
4. The assistant adds value by explaining, suggesting, and connecting patterns — it does not change how patterns behave.

---

## Anti-Patterns

### Forbidden Pattern Behaviors

1. **Inventing new patterns unnecessarily.** Before creating a new pattern, verify that existing patterns cannot compose to produce the desired behavior. New patterns require strong justification.

2. **Context switching without reason.** A pattern should not switch between experiences (Assistant ↔ Console) unless the user explicitly requests it or the task's complexity demands it.

3. **Breaking composition.** Patterns that cannot be composed with other patterns. Every pattern should have clear input and output interfaces for composition.

4. **Special-case behavior.** A pattern that behaves differently for different artifact types. The pattern's behavior is invariant; the content varies.

5. **Pattern duplication.** Two patterns that serve the same purpose. If two patterns seem similar, consolidate them into one with context-adaptive features.

6. **Pattern with no reuse.** A pattern that is only used in one context. Document it as a screen-specific behavior, not a pattern.

7. **Pattern that requires specific implementation.** A pattern that cannot be implemented in different frontend frameworks. Patterns are behavioral, not technological.

8. **Over-composed patterns.** A pattern that tries to do everything. A pattern should do one thing well. Complex workflows should compose multiple simple patterns.

9. **Pattern without state definition.** A pattern that does not define its state expectations. State is part of the pattern contract.

10. **Pattern without navigation definition.** A pattern that does not define how users enter and exit it. Entry and exit are part of the pattern contract.

11. **Pattern that ignores conversation.** A pattern that does not integrate with the assistant or conversation history.

12. **Pattern that ignores artifacts.** A pattern that operates on data without producing or referencing artifacts.

13. **Pattern with silent failure.** A pattern that fails without communicating the failure to the user.

14. **Pattern with invisible state.** A pattern that has internal state the user cannot perceive.

15. **Pattern that assumes non-interrupted workflow.** A pattern that breaks if the user navigates away and returns.

---

## Future Evolution

### Spatial Interfaces

As the platform evolves toward spatial interfaces:
1. Patterns adapt to spatial layout (e.g., List → Detail becomes a spatial proximity relationship).
2. Pattern composition becomes spatial arrangement (multiple patterns visible simultaneously in 3D space).
3. The pattern catalog remains valid — spatial interfaces are a new presentation layer, not a new behavioral model.

### Voice

As voice interaction matures:
1. Each pattern gains a voice interaction transcript. The user can speak their way through any pattern.
2. Voice follows the same pattern state machines. Voice is an input modality, not a new pattern.
3. Patterns with high interactivity (List → Detail → Filter) may offer voice shortcuts for frequent actions.

### Collaborative Investigations

As teams collaborate:
1. Patterns gain multi-user awareness. Multiple users can participate in the same pattern instance.
2. Pattern state is shared. All participants see the same state transitions.
3. Pattern actions may require multi-user approval.
4. The conversation within a pattern is shared.

### Multiple Agents

As multiple AI agents operate:
1. Different agents may handle different patterns in a composed workflow.
2. Agents are associated with patterns based on their capability.
3. The user sees which agent is handling which pattern step.
4. Pattern handoffs between agents are visible state transitions.

### Engineering Knowledge Graphs

As the platform accumulates collective knowledge:
1. Patterns become navigable paths through the knowledge graph.
2. Common pattern compositions become "investigation templates" that new users can follow.
3. The platform can recommend patterns based on the current context and historical usage.
4. Pattern usage data feeds back into the platform's understanding of effective workflows.
