# Universal State Model

> State is the foundation of user experience.
>
> Every interaction is fundamentally a state transition.
>
> This document defines the conceptual state model for the entire platform.

---

## Purpose

### Why State Is the Foundation

Users experience platforms through state. Every visual indicator, every loading spinner, every notification, every enabled or disabled button communicates state. When state is clear, users understand what is happening, why, and what they can do next. When state is unclear, users feel lost, frustrated, or distrustful.

A platform without an explicit state model inevitably produces inconsistent behavior: some loading states show spinners, others show nothing; some errors are visible, others are silent; some background work is communicated, some is hidden. Each inconsistency erodes trust.

An explicit state model ensures that every state is defined, every transition is understood, and every state change is communicated to the user consistently.

### Why Every Interaction Is a State Transition

| User Action | State Transition |
|---|---|
| Types a question | Idle → Processing |
| Receives a response | Processing → Streaming → Completed |
| Clicks "Approve" | Awaiting Approval → Approving → Completed |
| Opens a finding | Navigation: Idle → Loading → Displayed |
| Runs an experiment | Idle → Running → Completed (Exp) |
| Refreshes the dashboard | Dashboard: Idle → Refreshing → Updated |
| Receives a notification | Notification: Created → Delivered → Read |

Every action the user takes, and every action the platform takes in response, is a state transition. The state model defines which transitions are valid, how they are communicated, and what the user can do during each state.

---

## Universal State Philosophy

### State before animation

Animation does not define behavior — behavior defines animation. Every animation should be a visible expression of a state transition. The state model determines what animates; the animation system determines how.

### State before notification

Notifications are triggered by state transitions, not by arbitrary events. A user is notified when a high-value state transition occurs: an artifact changes status, a long-running operation completes, a decision requires attention.

### State before rendering

Every UI component should derive its visual presentation from an explicit state. A button is not "disabled" because of a CSS class — it is disabled because the underlying state machine says the action is unavailable.

### State before navigation

Navigation decisions depend on state. A finding that is in "Archived" state may navigate to a read-only view. A finding in "Pending" state may show approval options. Navigation is state-dependent.

### State should always be observable

Users should never wonder what the platform is doing. Every processing state, waiting state, and background state must be visible. States do not exist unless the user can perceive them.

### State transitions should always be explainable

When the platform transitions between states, users should understand why. "The findings list is loading because we are retrieving data from the Evidence Engine." Every transition has a reason that can be communicated.

### Users should understand what the platform is doing

The platform should never be in an ambiguous state. If it is loading, the user knows what is loading. If it is waiting, the user knows what it is waiting for. If it is processing, the user knows what is being processed.

### Never hide background work

Work that happens in the background is still visible. A background task has a state, a progress indicator, and a completion notification. Users can inspect background work at any time.

---

## Global State Categories

### User State

The user's authentication, role, preferences, and session status.

| State | Description |
|---|---|
| Unauthenticated | No user session. Read-only access. |
| Authenticated | Valid session. Full access based on role. |
| Session Expired | Previous session expired. Re-authentication required. |
| Permission Limited | Authenticated but with restricted capabilities. |

### Conversation State

The state of an engineering conversation. Defined in detail in 09-conversation-lifecycle.md.

| State | Description |
|---|---|
| New | Created, no messages yet |
| Active | Awaiting user input |
| Processing | AI generating or tool executing |
| Streaming | Response tokens arriving |
| Waiting for Tool | Tool execution in progress |
| Waiting for User | AI has asked a question |
| Awaiting Approval | Blocked on human approval |
| Paused | User explicitly paused |
| Background Processing | Long-running operation active |
| Completed | Investigation reached natural end |
| Archived | Actively closed |
| Failed | Unrecoverable error |
| Recovered | Restored from failure |

### Assistant State

The AI assistant's current operational state.

| State | Description |
|---|---|
| Idle | Awaiting user input |
| Thinking | Processing user input, planning |
| Retrieving | Gathering context from tools |
| Generating | Producing response content |
| Streaming | Delivering response incrementally |
| Executing Tool | Running a platform tool |
| Waiting | Waiting for external dependency |
| Error | Encountered an error |
| Interrupted | User cancelled generation |

### Tool State

The execution state of a platform tool. Defined in detail in 11-tool-invocation.md.

| State | Description |
|---|---|
| Queued | Awaiting execution slot |
| Starting | Initializing |
| Running | Actively executing |
| Waiting | Waiting for dependency |
| Retrying | Recovering from transient failure |
| Streaming | Returning incremental results |
| Completed | Execution finished successfully |
| Failed | Execution finished with error |
| Cancelled | User cancelled execution |
| Partial Success | Completed with some errors |

### Artifact State

The lifecycle state of any platform artifact. Defined in detail in 10-artifact-interactions.md.

| State | Description |
|---|---|
| Created | Generated, not yet observed |
| Observed | Seen by a user |
| Reviewed | Examined in detail |
| Validated | Claims verified against evidence |
| Acted | Decision made based on this artifact |
| Completed | Purpose fulfilled |
| Referenced | Cited by another artifact |
| Compared | Used in a comparison |
| Updated / Revised | Content changed after creation |
| Archived | No longer actively relevant |
| Restored | Brought back from archive |
| Deprecated | Superseded, should not be used |

### Notification State

The delivery and acknowledgment state of notifications.

| State | Description |
|---|---|
| Created | Generated but not yet delivered |
| Queued | Waiting in delivery queue |
| Delivered | Sent to user's notification feed |
| Read | User has seen the notification |
| Actioned | User took action from the notification |
| Dismissed | User dismissed without action |
| Expired | Notification is no longer relevant |

### Navigation State

The current screen and navigation context state.

| State | Description |
|---|---|
| Idle | Current screen displayed, no transitions |
| Navigating | Transitioning to a new screen |
| Loading | Target screen data loading |
| Displayed | Target screen fully rendered |
| Error | Navigation failed |
| Side Panel Open | Secondary context panel active |
| Modal Open | Decision modal active |

### Workspace State

The user's workspace configuration.

| State | Description |
|---|---|
| Default | Standard layout, no modifications |
| Customized | User has modified layout (widgets, filters) |
| Focused | Single module or task in focus mode |
| Split | Side panel or comparison view active |

### Search State

The global search and command palette state.

| State | Description |
|---|---|
| Closed | Not visible |
| Open | Visible, awaiting input |
| Typing | User is entering text |
| Searching | Results being retrieved |
| Results Displayed | Search results shown |
| No Results | Search completed with no matches |
| Error | Search failed |

### Selection State

What the user currently has selected.

| State | Description |
|---|---|
| Nothing Selected | No active selection |
| Artifact Selected | Single artifact in focus |
| Multiple Selected | Batch selection active |
| Range Selected | Time range or list range active |

### Background Task State

Long-running tasks that continue after the user navigates away.

| State | Description |
|---|---|
| Queued | Waiting to start |
| Running | Actively executing |
| Completed | Finished successfully |
| Failed | Finished with error |
| Needs Attention | Requires user action |
| Cancelled | Stopped by user |

### Automation State

The state of automated jobs, schedules, and triggers.

| State | Description |
|---|---|
| Idle | No automation running |
| Scheduled | Next run scheduled |
| Running | Actively executing |
| Completed | Last run successful |
| Failed | Last run failed |
| Paused | Schedule paused |
| Disabled | Automation disabled |

### Health State

Platform and capability health states.

| State | Description |
|---|---|
| Healthy | Operating within parameters |
| Degraded | Performance below threshold |
| Critical | Significant impairment |
| Down | Capability unavailable |
| Unknown | Health data unavailable |
| Recovering | Returning to healthy state |

---

## Universal State Lifecycle

### Generic Lifecycle

Every entity in the platform follows a variant of this generic lifecycle:

```
CREATED
   │
   ▼
  IDLE
   │
   ▼
ACTIVE ──────────► PROCESSING ──────────► STREAMING
   │                     │                      │
   │                     ▼                      │
   │                WAITING ────────────────────┘
   │                     │
   │                     ▼
   │               NEEDS APPROVAL ────► APPROVING
   │                                          │
   └──────────────────────────────────────────┘
                      │
                      ▼
                 COMPLETED
                      │
               ┌──────┴──────┐
               │             │
               ▼             ▼
           ARCHIVED       FAILED
               │             │
               │             ▼
               │         RECOVERED ────► ACTIVE
               │
               ▼
         DEPRECATED
```

### Lifecycle Stage Meanings

| Stage | Meaning | Observable |
|---|---|---|
| **Created** | Entity has been instantiated. May not be ready for interaction. | Brief initialization state |
| **Idle** | Entity exists and is ready. No active work. | Waiting state, stable |
| **Active** | Entity is engaged in its primary function. | Active state, user may interact |
| **Processing** | Work is being performed. No streaming yet. | Active work state, brief or long |
| **Streaming** | Work results are being delivered incrementally. | Visible progress, partial results |
| **Waiting** | Blocked on an external dependency (tool, user, approval). | Waiting indicator visible |
| **Needs Approval** | Action cannot proceed without human decision. | Approval prompt displayed |
| **Approving** | Approval is being processed. | Brief transition |
| **Completed** | Work has finished successfully. | Terminal success state |
| **Archived** | Actively closed. Preserved for history. | Terminal, reversible |
| **Deprecated** | Superseded. Should not be used for new decisions. | Terminal, irreversible |
| **Failed** | Work finished with an error. | Terminal, may recover |
| **Recovered** | Restored from a failed state. | Transient, leads back to Active |

### Lifecycle Rules

1. Every entity in the platform exists in exactly one state at any time.
2. Not every entity passes through every state in the generic lifecycle. A read-only artifact may go Created → Idle → Archived without ever Processing.
3. The lifecycle is directional. Entities move forward through states. Recovery is the only backward transition.
4. States at the same horizontal level in the lifecycle diagram are mutually exclusive. An entity cannot be both Processing and Waiting simultaneously.
5. Terminal states (Completed, Archived, Deprecated, Failed) cannot transition to states earlier in the lifecycle except through explicit Recovery.

---

## State Visibility

### Visibility Levels

| Level | Description | Examples |
|---|---|---|
| **Prominent** | Always visible. Cannot be missed. | Error state, critical finding, waiting for approval |
| **Visible** | Visible but not prominent. User can see it without searching. | Loading spinner, streaming indicator, health status |
| **Subtle** | Visible on demand. User must look for it. | Background task progress, tool execution details |
| **Implicit** | Not directly visible but inferable from UI state. | Navigation state (user knows they navigated), selection state (highlighted item) |
| **Logged** | Not visible but recorded. Available for audit. | Past tool execution details, state transition history |

### Visibility Rules

| State Type | Minimum Visibility | Rationale |
|---|---|---|
| Error | Prominent | Users must know something went wrong |
| Waiting for user | Prominent | User must respond |
| Needs Approval | Prominent | Decision required |
| Processing (expected < 2s) | Subtle | Brief enough to not demand attention |
| Processing (expected 2-30s) | Visible | User should know work is happening |
| Processing (expected 30s+) | Prominent | User may want to navigate away |
| Streaming | Visible | User reads partial results |
| Background processing | Subtle | User chose to navigate away |
| Completed | Visible (brief) | Transition indicator |
| Archived | Implicit | Only relevant when browsing archives |
| Deprecated | Visible | Users should not use this |
| Idle | Implicit | Default state, no indication needed |

### Notification Triggers

| State Transition | Notification? | When |
|---|---|---|
| Created → Idle (new finding, critical) | Yes | Immediately |
| Completed (long-running task) | Yes | On completion |
| Failed (user-initiated task) | Yes | On failure |
| Needs Approval | Yes | When assigned to user |
| Archived (by another user) | No | Implicit |
| Updated | If subscribed | On update |
| Referenced | If mentioned | On reference |

### State Logging

All state transitions are logged for audit and history purposes. Logged transitions are accessible through the artifact history view and the audit log. Users can review the state history of any entity.

---

## State Transitions

### Valid Transitions

Valid transitions follow the lifecycle model. Each entity type defines which transitions are valid for its specific lifecycle. Examples:

| Entity | Valid Transition | Meaning |
|---|---|---|
| Conversation | Processing → Streaming | AI response is being delivered |
| Tool | Running → Completed | Tool execution finished |
| Artifact | Created → Observed | User has seen the artifact |
| Notification | Delivered → Read | User opened the notification |

### Invalid Transitions

Transitions that are not permitted by the lifecycle model. The platform prevents invalid transitions.

| Entity | Invalid Transition | Why |
|---|---|---|
| Artifact | Created → Archived | Must be observed first |
| Conversation | New → Completed | Must be active first |
| Tool | Queued → Completed | Must run first |
| Notification | Created → Read | Must be delivered first |

### Interrupted Transitions

Users can interrupt certain transitions:

| Interruptible Transition | Behavior |
|---|---|
| Streaming → Interrupted | Stop AI generation. Show partial response. |
| Processing → Cancelled | Cancel tool execution. Return partial results. |
| Waiting → Cancelled | Cancel the wait. Return to previous state. |
| Long-running → Cancelled | Stop background task. Discard incomplete results. |

Non-interruptible transitions:

- Approval (once submitted, cannot be recalled)
- Navigation (once navigated, previous screen is cached but navigation itself is not cancellable)
- State persistence (state writes are atomic)

### Concurrent Transitions

Multiple state transitions can occur simultaneously when they affect different entities:

- A Conversation can be in Streaming state while a Tool is in Running state.
- A Dashboard can be in Refreshing state while a Notification is in Delivered state.
- A Background Task can be in Running state while the user navigates to a different screen.

Concurrent transitions are independent. They do not block each other.

### Recovery Transitions

Recovery transitions return an entity from a failed or interrupted state to a functional state:

| Recovery Path | Behavior |
|---|---|
| Failed → Recovered → Active | Error resolved. Entity resumes. |
| Failed → Recovered → Idle | Error resolved. Entity returns to ready state. |
| Failed → Archived | Error is permanent. Entity archived as-is. |

Recovery may involve data loss. Partial results may be available. The user is informed of what was preserved and what was lost.

### Rollback Transitions

Rollback transitions revert an entity to a previous state:

| Rollback Path | Behavior |
|---|---|
| Applied → Rolled Back | Configuration reverted. New snapshot created. |
| Approved → Rejected | Decision reversed. Audit trail preserved. |

Rollbacks create new artifacts (rollback snapshots, reversal decisions). They do not erase history.

### Timeout Transitions

When an operation exceeds its expected duration:

| Timeout Path | Behavior |
|---|---|
| Processing → Failed | Operation timed out. User informed. |
| Waiting → Failed | Dependency did not respond. User informed. |
| Processing → Partial Success | Some results available. Timeout noted. |

Timeout thresholds are defined per operation type. Users are warned before timeout if the operation is approaching the threshold.

### Background Transitions

Transitions that occur when the user is not actively watching:

1. Background transitions update the entity's state in the state store.
2. The user is notified only if the transition is to a state that requires attention.
3. When the user returns to the entity, they see the current state and a brief transition history.
4. Background transitions that result in failure are always surfaced.

---

## Long-Running State

### How Users Experience Long-Running Operations

| Operation | Typical Duration | State Path | User Experience |
|---|---|---|---|
| **AI reasoning** | 1-5s | Processing → Streaming → Completed | Streaming cursor, partial response visible |
| **Tool execution (fast)** | 0.5-3s | Running → Completed | Brief spinner, then results |
| **Tool execution (medium)** | 3-30s | Running → (progress) → Completed | Progress bar with status message |
| **Tool execution (slow)** | 30s-5m | Running → (progress with ETA) → Completed | Progress bar, ETA, intermediate results |
| **Experiment run** | 1-48h | Running (experiment) → Completed | Background task. User navigates away. Notification on completion. |
| **Evaluation** | 1-30m | Running → (progress) → Completed | Progress bar. Intermediate results. Completion notification. |
| **Automation job** | 1-60m | Queued → Running → Completed | Background task. Status in automation dashboard. |
| **Config rollout** | 1-10m | Approving → Applying → Completed | Multi-step progress. Rollback available during rollout. |
| **Continuous evaluation** | Ongoing | Running (continuous) | Health scores update periodically. Dashboard reflects current state. |

### Long-Running State Rules

1. Every long-running operation has a known state path. Users can see where in the path the operation is.
2. Operations longer than 5 seconds show: progress bar, status message, elapsed time, and (where possible) estimated time remaining.
3. Operations longer than 30 seconds are cancellable.
4. Operations longer than 5 minutes can run in the background. Users are notified on completion.
5. Users can check the status of any running operation from the command palette: "show running tasks."
6. Long-running state is persisted across page refreshes. Refreshing the page during a long-running operation shows the operation's current state.

---

## State Synchronization

### Synchronization Principles

1. **State is consistent within a user's session.** All views the user sees reflect the same state. The assistant, dashboard, artifact views, and command palette all show the same conversation state, artifact states, and tool states.

2. **State changes propagate without manual refresh.** When a finding's status changes from "New" to "Acknowledged," the change is reflected in the dashboard widget, the findings list, the conversation where it was referenced, and any open artifact detail views — without the user refreshing.

3. **State is source-of-truth per user session.** Each user session maintains its own state representation. State conflicts between sessions are resolved by the backend (last-write-wins or explicit conflict resolution).

4. **State updates are non-disruptive.** A background state update does not interrupt the user's current activity. Updated elements show a subtle "Updated" indicator rather than a disruptive refresh.

5. **State synchronization is observable.** Users can see when state was last synchronized: "Updated 10 seconds ago" appears on synchronized elements.

### Cross-View Consistency

| View | Consistent With |
|---|---|
| Assistant | Current conversation state, pinned artifacts, active tool executions |
| Dashboard | All module states, health state, pending item counts |
| List view (findings, experiments, etc.) | Artifact states, filter state, selection state |
| Detail view | Single artifact state, lineage, history |
| Command palette | Workspace state, active conversation, recent commands |
| Notifications | Notification state, artifact states that triggered notifications |
| Search | Search state, artifact states in results |

### Synchronization Rules

1. Opening a new view always shows the current state. No view displays stale data without indicating it.
2. When a view is in the background and its data changes, the view shows a "New data available" indicator when the user returns to it.
3. Manual refresh is always available but never required. Users can refresh explicitly if they want to verify state.
4. State synchronization failures are communicated: "Some data may be outdated. Last updated: 5 minutes ago."

---

## State Recovery

### Recovery Patterns

| Scenario | Recovery Behavior | User Experience |
|---|---|---|
| **Browser refresh** | Session state is restored. Active conversations, open views, and navigation history are preserved. | Page reloads to the same state. Brief loading indicator. |
| **Connection lost** | Platform enters reduced-functionality mode. Previously loaded data remains visible. New actions are queued. | Banner: "Connection lost. Retrying...". Data remains readable. |
| **Reconnect** | Queued actions are submitted. State is resynchronized. | Banner: "Reconnected. Syncing...". Brief sync indicator. |
| **Session timeout** | User is prompted to re-authenticate. State is preserved until re-authentication completes. | Auth modal. On success, state is restored. |
| **Tool failure** | Tool state transitions to Failed. Recovery options are presented. | Error message with retry, alternative, or cancel options. |
| **Task cancellation** | Task state transitions to Cancelled. Partial results may be available. | "Task cancelled." Optional: "View partial results." |
| **Conflict detection** | User is notified of the conflict. Both versions are presented for comparison. | Conflict resolution UI: "A change was made while you were viewing. Review the update." |
| **Partial recovery** | Available data is restored. Unavailable data is noted. | "Some data could not be recovered. [details]" |

### Recovery Rules

1. Recovery is automatic for transient failures (connection loss, brief tool failure). The user is informed but does not need to act.
2. Recovery requires user action for persistent failures (session timeout, tool failure, conflict).
3. Recovery never loses user work. Composed but unsubmitted messages, modified but unsaved filters, and in-progress selections are always preserved.
4. Recovery preserves context. After recovery, the user's active conversation, selected artifact, and workspace state are restored.

---

## Error State Philosophy

### State Types vs. User Expectations

| State Type | User Expectation | Example |
|---|---|---|
| **Error** | Something is definitely wrong. User cannot proceed until resolved. | Tool execution failed, data cannot be loaded |
| **Warning** | Something may be wrong or suboptimal. User can proceed with caution. | Partial results, outdated data, low confidence |
| **Pending** | Something is expected but not yet available. User must wait. | Tool running, data loading, approval awaiting |
| **Unknown** | State cannot be determined. User should not assume anything. | Health data unavailable, capability status unknown |
| **Unavailable** | Something is known to be inaccessible. User cannot use it. | Tool disabled, feature not in user's scope |
| **Outdated** | Data was valid but may no longer be current. User should refresh. | Dashboard not updated, last sync was 10 minutes ago |
| **Recovering** | Something failed and is being restored. User should wait briefly. | Reconnecting, retrying tool execution |

### Error Visual Distinction

Each error state type is visually distinct:

- **Error**: Red. Icon: X-circle. Urgent, requires attention.
- **Warning**: Yellow/amber. Icon: triangle-exclamation. Cautionary, does not block.
- **Pending**: Blue. Icon: spinner or clock. Informational, requires patience.
- **Unknown**: Gray. Icon: question-mark. Neutral, requires investigation.
- **Unavailable**: Gray with icon. Neutral, requires alternative action.
- **Outdated**: Yellow with clock icon. Informational, requires refresh.
- **Recovering**: Blue with rotating arrows. Informational, progressing.

### Error State Rules

1. Error states are visible immediately when they occur. No delay.
2. Error states include an explanation: "The Evidence Engine is unavailable because..." not just "Error."
3. Error states include recovery guidance: "Try refreshing, or check the Operations Control Plane for service status."
4. Warning states include what the user should be aware of: "Results are based on data from 2 hours ago. Some findings may have been updated since."
5. Pending states include what is happening and why: "Evaluating experiment results... this typically takes 30 seconds."
6. Unknown states include what is needed to resolve: "Connect to the platform to check health status."
7. States that persist beyond expected duration escalate: Pending → Warning → Error.

---

## Human Expectations

### What Users Should Always Know

| Question | How the Platform Answers |
|---|---|
| **What is happening?** | Current state is always visible. State labels, progress indicators, and status messages communicate current activity. |
| **Why?** | State transitions include explanations. "Evaluating experiment results because you launched experiment AB-47." |
| **How long?** | Expected duration is communicated for operations over 2 seconds. ETA for operations over 30 seconds. |
| **What changed?** | State changes are highlighted. New results, updated status, and completed operations are visually marked. |
| **What can I do next?** | Available actions are determined by current state. Disabled actions explain why. Suggested next actions are offered. |
| **Can I interrupt?** | Interruptible states show a cancel button. Non-interruptible states explain why. "Cannot cancel once approval is submitted." |
| **Can I undo?** | Reversible actions show an undo option and its time window. Irreversible actions are clearly warned. |
| **Where am I?** | Breadcrumbs, navigation state, and context indicators show the user's location in the platform. |
| **What was the previous state?** | History and audit trails are accessible. Users can review past states and transitions. |
| **Is my data safe?** | Persistent states are clearly distinguished from ephemeral states. Auto-save indicators confirm data persistence. |

---

## Anti-Patterns

### Forbidden State Behaviors

1. **Invisible state.** The platform is in a state the user cannot perceive. Example: background processing that the user cannot see, tool execution with no indicator.

2. **Stuck loading.** A loading state that never resolves. No timeout, no error, no recovery. The user waits indefinitely.

3. **Conflicting indicators.** Two UI elements showing different states for the same entity. Example: a widget says "3 pending findings" while the findings list shows 0.

4. **Duplicate state.** The same entity exists in two different states in different parts of the UI. Example: a finding is "Acknowledged" in the detail view but still shows as "New" in the dashboard.

5. **State desynchronization.** The UI shows a state that has already changed. No indicator that the data may be stale.

6. **Impossible transitions.** The platform transitions to a state that cannot logically follow from the current state. Example: an artifact goes from "Created" directly to "Archived" without being observed.

7. **Silent background work.** Work happens without the user knowing. The platform executes tools, creates artifacts, or modifies state while the user is unaware.

8. **No exit from error.** An error state with no recovery path. The user cannot retry, cancel, or proceed.

9. **False completion.** An operation appears to complete successfully but failed silently. The UI shows "Completed" but the underlying operation failed.

10. **State reset.** Navigating away from a screen and returning resets the state. Filters are cleared, scroll position is lost, expanded sections are collapsed.

11. **Black box processing.** A processing state that shows no information about what is happening or how long it will take. Users stare at an empty spinner.

12. **State without context.** A state is displayed without explaining why. "Loading..." without "Loading findings from the Evidence Engine."

13. **Inconsistent state terminology.** Different parts of the platform use different terms for the same state. "Processing" in one place, "Running" in another, "In Progress" in a third — all meaning the same thing.

14. **State overload.** Too many states for a single entity, making it impossible for users to understand what is happening. Each entity type has a clearly bounded set of states.

15. **State dependence on UI.** An entity's state is tied to the UI component displaying it rather than being a property of the entity itself. Closing a panel should not change an artifact's state.

16. **Non-deterministic state.** The same action sometimes leads to one state and sometimes to another, without explanation. State transitions should be predictable.

17. **State without ownership.** No clear entity owns the state. The conversation, tool, and artifact all claim to control the same state, leading to conflicts.

18. **Hidden error states.** Errors that occur but do not produce an error state visible to the user. Example: a background sync fails silently.

19. **Premature completion.** An operation transitions to "Completed" while work is still happening in the background. Users think their task is done when it is not.

20. **State without escape.** A state that the user cannot leave. Example: "Awaiting Approval" with no way to cancel the approval request.

---

## Future Evolution

### Multiple Agents

As multiple AI agents operate concurrently:

1. Each agent has its own state lifecycle: Idle → Thinking → Executing → Waiting → Completed.
2. Agent states are visible to users. A multi-agent dashboard shows the state of each active agent.
3. Agent-to-agent handoffs are visible state transitions: "Agent A (completed) → Agent B (starting)."
4. Conflicting agent states are surfaced: "Agent A believes this is resolved. Agent B is still investigating."

### Collaborative Workspaces

As multiple users collaborate:

1. Each user's session maintains its own state. Shared state (artifact status, conversation content) is synchronized.
2. Presence state is visible: "Priya is viewing this finding. Marcus is editing the experiment definition."
3. Concurrent state transitions from different users are merged or flagged as conflicts.
4. Shared state has explicit ownership: "Priya is the reviewer. Marcus is the approver."

### Offline Operation

As the platform supports offline work:

1. Offline state is explicitly communicated: "You are offline. Changes will sync when connected."
2. Queued actions in offline state are visible as a pending action list.
3. State synchronization on reconnection is visible: "Syncing changes... 3 of 5 complete."
4. Conflicts detected during synchronization are surfaced for resolution.

### Distributed Execution

As platform capabilities are distributed across regions or clusters:

1. Regional state is labeled: "US East — Healthy. EU West — Degraded."
2. Cross-region state synchronization latency is visible: "Last sync: 2 seconds ago."
3. Users can filter state views by region.
4. Capability state reflects the worst state across all regions.

### Continuous Background Learning

As the platform learns continuously:

1. A persistent "Learning" state is visible for the learning subsystem.
2. Users can inspect what the platform is currently learning: "Analyzing 1,000 recent interactions for trend detection."
3. Learning state transitions are logged for audit.
4. Users can pause or configure background learning.

### Autonomous Systems

As automation becomes more autonomous:

1. Autonomous agents have state lifecycles with explicit permission boundaries.
2. "Needs Approval" states include the scope of autonomy: "This action is within your pre-approved automation policy."
3. Autonomous state transitions beyond pre-approved scope require explicit approval.
4. A global "Autonomy Level" state indicates the current degree of platform autonomy.
