# Conversation Lifecycle Architecture

> Conversations are first-class engineering workspaces.
>
> Everything in the platform — findings, evidence, experiments, configs, decisions, artifacts — can attach to a conversation.
>
> This document defines the complete lifecycle of a conversation from creation to archival.

---

## Purpose

### Why Conversations Are First-Class Entities

A conversation is not a transient chat exchange. It is a persistent, stateful engineering workspace that accumulates context, artifacts, decisions, and lineage over time.

In a traditional application, the user navigates through screens to gather context, correlate data, and make decisions. Each screen transition risks losing the thread of investigation. The user must hold the context in their head.

In this platform, the conversation holds the context. The user asks questions, the assistant retrieves evidence, the user investigates, the assistant proposes actions, the user decides — and everything is preserved in the conversation record.

### Why Conversations Replace Navigation

Navigation is the traditional way to move between information silos. A conversation is the natural way to move between related ideas. Engineers do not think in terms of screen hierarchies; they think in terms of investigation threads.

The conversation becomes the workspace because:

- **Context accumulates.** Every question, every retrieved artifact, every decision builds on what came before.
- **Intent is preserved.** The platform knows *why* the user is looking at a finding — they are investigating a health degradation — not just *that* they are looking at it.
- **Reasoning is recorded.** The chain of investigation is a first-class artifact, not something the user must reconstruct from browser history.
- **Work is resumable.** An interrupted investigation can be resumed hours or days later without losing the thread.
- **Collaboration is natural.** Conversations can be shared, forked, and merged — just like code branches.

---

## Conversation Lifecycle

### Full Lifecycle

```
CREATE
  │
  ▼
INTENT RECOGNITION
  │
  ▼
CONTEXT RETRIEVAL
  │
  ▼
REASONING
  │
  ▼
RESPONSE GENERATION
  │
  ▼
TOOL INVOCATION ───────► TOOL EXECUTION ───────► RESULT INTEGRATION
  │                                                   │
  │                                                   ▼
  └─────────────────────────────────────────── ARTIFACT GENERATION
                                                         │
                                                         ▼
                                              FOLLOW-UP / ITERATION
                                                         │
                                              ┌──────────┼──────────┐
                                              │          │          │
                                              ▼          ▼          ▼
                                     INVESTIGATION  DECISION   COMPLETION
                                                         │
                                                         ▼
                                                APPROVAL CHECKPOINT
                                                         │
                                              ┌──────────┴──────────┐
                                              │                     │
                                              ▼                     ▼
                                        ACTION EXECUTED      REJECTED / DEFERRED
                                              │
                                              ▼
                                        REVIEW OUTCOME
                                              │
                                              ▼
                                        CONTINUE or COMPLETE
                                              │
                                              ▼
                                          ARCHIVE
```

### Stage Descriptions

#### 1. Create

A conversation is created when:
- The user types a message in the assistant
- The user clicks a quick action that initiates a conversation ("Investigate finding", "Compare experiments")
- The user opens a deep link that creates a new session
- The user forks an existing conversation
- A notification triggers a new investigation session

Creation metadata includes: timestamp, creator, entry point (assistant, dashboard, notification, deep link), and initial intent if available.

#### 2. Intent Recognition

The platform classifies the user's intent before retrieving any data. This determines the conversation mode (explain, investigate, compare, search, generate, plan, review, teach) and guides context retrieval.

Intent recognition is explicit: the system may show a brief "I understand you want to investigate a finding" acknowledgment before proceeding. If intent is ambiguous, the assistant asks a clarifying question before retrieving data.

#### 3. Context Retrieval

Based on the recognized intent, the platform retrieves relevant context from:
- The current conversation history (what has been discussed so far)
- Pinned artifacts (findings, experiments, configs attached to this conversation)
- The user's session state (selected time window, active filters)
- Platform data (Evidence Engine, Analytics, Learning Ledger, etc.)

Context retrieval may involve multiple tool calls. Each call is visible in the conversation as a progress indicator.

#### 4. Reasoning

The platform synthesizes the retrieved context into a coherent understanding. This stage is not visible to the user as a separate step — it produces the response content. However, the reasoning process is always accessible via an expandable "Show reasoning" section.

#### 5. Response Generation

The response is generated and streamed to the user. The response includes:
- Natural language explanation
- Evidence citations (linked to source artifacts)
- Suggested follow-up actions (as clickable chips)
- Drill-down links to the Operations Console

#### 6. Tool Invocation

When the user asks a question that requires data beyond the current context, or when they accept a suggested action, the assistant invokes platform tools. Tool invocation is always visible to the user.

#### 7. Artifact Generation

When tools produce results, those results may become new artifacts (recommendations, experiment definitions, config snapshots). Artifact generation is recorded in the conversation lineage with parent references.

#### 8. Follow-Up / Iteration

The user continues the investigation. Each turn adds to the conversation context. The assistant maintains awareness of the full thread.

#### 9. Decision Support

When the investigation reaches a decision point, the assistant presents options with evidence, trade-offs, and recommendations. The user decides.

#### 10. Approval Checkpoint

If the decision requires a production change, an approval checkpoint is inserted. The conversation pauses until approval is granted or denied.

#### 11. Review Outcome

After action is taken, the assistant summarizes what changed and offers to verify the outcome.

#### 12. Complete / Archive

The conversation reaches a natural end state (see Conversation Ending section).

---

## Conversation States

### State Diagram

```
                        ┌──────────────┐
                        │     NEW      │
                        └──────┬───────┘
                               │
                               ▼
                   ┌───────────────────────┐
          ┌───────│      ACTIVE            │◄────────┐
          │       │ (awaiting user input)  │         │
          │       └───────┬───────────────┘         │
          │               │                         │
          │               ▼                         │
          │       ┌───────────────────────┐         │
          │       │   PROCESSING          │         │
          │       │ (AI generating /      │         │
          │       │  streaming response)  │         │
          │       └───────┬───────────────┘         │
          │               │                         │
          │       ┌───────┴───────────────┐         │
          │       │                       │         │
          │       ▼                       ▼         │
          │  ┌──────────┐          ┌──────────┐     │
          │  │ WAITING  │          │ WAITING  │     │
          │  │ FOR TOOL │          │ FOR USER │     │
          │  └────┬─────┘          └────┬─────┘     │
          │       │                     │           │
          │       ▼                     │           │
          │  ┌──────────┐              │           │
          │  │ STREAMING│              │           │
          │  │ RESULT   │              │           │
          │  └────┬─────┘              │           │
          │       │                    │           │
          │       ▼                    ▼           │
          │  ┌──────────────────────────────┐      │
          │  │     AWAITING APPROVAL         │      │
          │  └──────┬───────────────────────┘      │
          │         │                              │
          │         ▼                              │
          │  ┌──────────────────────────────┐      │
          │  │     ACTION / DECISION         │──────┘
          │  └──────────────────────────────┘
          │
          │         ┌──────────────┐
          │         │   PAUSED     │ (user explicitly pauses)
          │         └──────┬───────┘
          │                │
          └────────────────┘

          ┌────────────────────┐
          │    BACKGROUND      │ (long-running tool, user
          │    PROCESSING      │  navigated away)
          └─────────┬──────────┘
                    │
                    ▼
          ┌────────────────────┐
          │    COMPLETED       │
          └─────────┬──────────┘
                    │
          ┌────────┴────────┐
          │                 │
          ▼                 ▼
   ┌──────────┐     ┌──────────┐
   │ ARCHIVED │     │  FAILED  │
   └──────────┘     └────┬─────┘
                         │
                         ▼
                  ┌──────────────┐
                  │  RECOVERED   │
                  └──────────────┘
```

### State Definitions

| State | Description | Transitions To |
|---|---|---|
| **New** | Just created, no messages yet | Active |
| **Active** | Awaiting user input. The conversation is ready for the next message. | Processing, Paused, Completed |
| **Processing** | AI is generating a response. User cannot send new messages until streaming completes (or they interrupt). | Streaming, Waiting for Tool |
| **Streaming** | Response tokens are being delivered to the user. The user can read partial output. | Active (when complete), Waiting for User |
| **Waiting for Tool** | The AI has invoked a platform tool and is waiting for results. User sees a progress indicator. | Streaming, Waiting for User, Failed |
| **Waiting for User** | The AI has asked a clarifying question or presented options. User must respond. | Active |
| **Streaming Result** | Tool results are being streamed into the conversation (long lists, charts, artifact summaries). | Active |
| **Awaiting Approval** | A decision checkpoint requires human approval. Conversation is blocked until approval or rejection. | Active (approved), Completed (rejected) |
| **Action / Decision** | A decision has been made. The conversation records the decision artifact. | Active (continue), Completed |
| **Paused** | User explicitly pauses the investigation. The conversation state is frozen. | Active (resume) |
| **Background Processing** | A long-running operation (experiment, evaluation) continues after the user has navigated away. | Active (notification on completion) |
| **Completed** | Investigation reached a natural end. No pending actions. | Archived |
| **Archived** | Actively closed. Searchable but not in the active conversation list. | Active (reopen) |
| **Failed** | An unrecoverable error occurred during processing. | Recovered, Archived |
| **Recovered** | A failed conversation was restored from a checkpoint. | Active |

---

## Conversation Context

### Context Categories

| Category | Contents | Lifetime |
|---|---|---|
| **User input** | Current message text, intent classification, attached files | Current turn |
| **Conversation history** | All previous messages, responses, and tool results in this conversation | Conversation |
| **Pinned artifacts** | Artifacts the user has explicitly pinned to this conversation | Conversation (explicit) |
| **Active artifact** | The artifact currently being discussed (finding, experiment, config) | Current investigation thread |
| **Retrieved evidence** | Evidence, analytics, and ledger records retrieved during the conversation | Conversation (auto-managed) |
| **Tool outputs** | Results of tool invocations (structured data, charts, summaries) | Conversation |
| **Generated artifacts** | Recommendations, experiment definitions, config snapshots created during this conversation | Persistent (platform artifacts) |
| **Session metadata** | User identity, role, permissions, platform version | Session |
| **Time window** | The current evaluation time window | Session (global) |
| **User preferences** | Display preferences, notification settings, default time window | Persistent (cross-session) |
| **Temporary notes** | User's inline notes attached to specific messages | Conversation |
| **Decision records** | Approvals, rejections, deferrals made during this conversation | Persistent (platform artifacts) |

### Context Size Management

Conversation context has practical limits. The platform manages context through:

1. **Summarization.** When the conversation exceeds a context threshold, older turns are summarized into a condensed representation. The summary is available for review but does not consume full context capacity.

2. **Eviction priority.** Tool outputs and retrieved evidence are evicted before user messages and pinned artifacts. The assistant can re-retrieve evidence if needed.

3. **Explicit pinning.** Users can pin critical artifacts to prevent eviction. Pinned artifacts persist in context regardless of conversation length.

4. **Context budget display.** When the conversation approaches context limits, the assistant may suggest archiving and starting a fresh continuation thread.

---

## Context Evolution

### How Context Grows

Each turn in a conversation expands the context:

```
Turn 1: "Why did health decrease last night?"
    Context: Question + Intent("investigate_health")
    Retrieval: Health report, recent findings, evaluation scores
    Context now: Question + Intent + HealthData + Findings

Turn 2: "Show me the evidence for finding #1024"
    Context now: [previous] + Reference to Finding #1024
    Retrieval: Evidence timeline for #1024, related metrics
    Context now: [previous] + EvidenceData

Turn 3: "What recommendations exist for this?"
    Context now: [previous] + Recommendation intent
    Retrieval: Recommendations linked to finding #1024
    Context now: [previous] + RecommendationData

Turn 4: "Create an experiment for the top recommendation"
    Context now: [previous] + Experiment creation intent
    Action: Draft experiment definition created
    Context now: [previous] + DraftExperiment(v1)
```

### Context Reset Rules

Context is never silently reset. The following are explicit context transitions:

| Transition | Trigger | Behavior |
|---|---|---|
| **Context switch** | User explicitly changes topic: "Let me look at something else" | Assistant acknowledges switch. Previous context remains in history. |
| **Branch** | User forks the conversation | New branch inherits parent context up to the fork point |
| **Summarize** | Context exceeds budget | Older turns are summarized. Summary is visible and expandable. |
| **Archive** | User archives conversation | Context is preserved in the artifact store. No longer active. |
| **Resume** | User reopens an archived conversation | Full context is restored (or summarized if budget exceeded) |

---

## Conversation Memory

### Memory Scopes

```
┌─────────────────────────────────────────────────────────────┐
│                    PLATFORM MEMORY                            │
│  (cross-user, cross-session: learned patterns, tuning data)  │
│  Lifetime: permanent                                         │
│  Scope: all users                                            │
│  Not directly visible to individual users                    │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              PERSISTENT USER PREFERENCES                │ │
│  │  (theme, default time window, notification settings)    │ │
│  │  Lifetime: permanent                                    │ │
│  │  Scope: per user, cross-session                         │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  WORKSPACE MEMORY                        │ │
│  │  (pinned artifacts, saved investigations, bookmarks)    │ │
│  │  Lifetime: explicit (until unpinned or deleted)          │ │
│  │  Scope: per user, cross-session                         │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                SESSION MEMORY                            │ │
│  │  (time window, active filters, navigation history)      │ │
│  │  Lifetime: session (until logout or timeout)             │ │
│  │  Scope: per user session                                │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              CONVERSATION MEMORY                         │ │
│  │  (full message history, pinned artifacts, tool outputs) │ │
│  │  Lifetime: until archived or deleted                     │ │
│  │  Scope: per conversation                                │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  ┌─────────────────────────────────────────────────────┐│ │
│  │  │            CURRENT TASK MEMORY                       ││ │
│  │  │  (active artifact, current investigation subject)   ││ │
│  │  │  Lifetime: until subject explicitly changes         ││ │
│  │  │  Scope: current investigation thread                ││ │
│  │  └─────────────────────────────────────────────────────┘│ │
│  │  ┌─────────────────────────────────────────────────────┐│ │
│  │  │              CURRENT MESSAGE                         ││ │
│  │  │  (user input currently being composed)              ││ │
│  │  │  Lifetime: until sent or discarded                  ││ │
│  │  └─────────────────────────────────────────────────────┘│ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Memory Rules

1. **Conversation memory never expires for active conversations.** All turns, tool outputs, and artifacts remain accessible throughout the conversation lifecycle.
2. **Session memory resets on logout.** Active filters, expanded sections, and navigation history do not persist across sessions.
3. **Workspace memory requires explicit user action.** Pinning an artifact, saving an investigation, or bookmarking a conversation is always an explicit user action.
4. **Platform memory is aggregate and anonymous.** Individual conversations are never used for platform learning without explicit opt-in.
5. **Memory boundaries are visible.** Users can see what is in each memory scope and clear session or workspace memory explicitly.

---

## Multi-Turn Investigation

### Investigation Pattern

A multi-turn investigation follows a predictable pattern:

1. **Initial question.** The user starts with a broad question or observation.
2. **Scoping.** The assistant clarifies scope: time window, capabilities, specific artifacts.
3. **Evidence gathering.** The assistant retrieves relevant data across multiple tools.
4. **Synthesis.** The assistant presents a structured overview.
5. **Drill-down.** The user asks follow-up questions on specific aspects.
6. **Hypothesis.** The assistant proposes potential root causes or explanations.
7. **Validation.** The user requests evidence for specific hypotheses.
8. **Conclusion.** The investigation reaches a conclusion or identifies the need for an experiment.
9. **Action.** The user decides on a course of action (create recommendation, launch experiment, dismiss).
10. **Review.** The assistant summarizes what was learned and offers to monitor the outcome.

### Example: Platform Health Investigation

```
USER: "Why did platform health decrease last night?"

ASSISTANT: "I'll investigate. Let me check the health report, recent
findings, and evaluation data."

[Retrieving: Health scores, recent findings, evaluation reports]

"The platform health score dropped from 96 to 84 between 02:00 and 03:00 UTC.
The decrease is primarily in the Evidence Engine capability.

Key findings during this period:
1. Finding #1021: Evidence Engine latency increased by 340ms (p95)
2. Finding #1022: Retrieval accuracy dropped from 91% to 84%
3. Finding #1023: Confidence scoring pipeline timeout rate increased

Would you like me to investigate any of these findings in detail?"

USER: "What caused the latency increase?"

ASSISTANT: "Let me trace the Evidence Engine latency finding."

[Retrieving: Evidence timeline for Finding #1021, Learning Ledger records]

"The latency increase correlates with a configuration change at 01:45 UTC:
- Snapshot v141 increased the parallel retrieval factor from 4 to 8
- This change was intended to improve throughput but appears to have
  caused resource contention under peak load

The latency increase started 15 minutes after the config change was applied
and persisted for the remainder of the evaluation window.

Would you like to:
1. Create a recommendation to revert the change?
2. Design an experiment with a moderate parallel factor (6)?
3. View the full evidence timeline?"
```

### Example: Experiment Comparison

```
USER: "Compare experiments AB-47 and AB-48"

ASSISTANT: "Let me retrieve the results for both experiments."

[Retrieving: Experiment definitions, results, metric comparisons]

"Here is the comparison:

Metric            | AB-47 (baseline) | AB-48 (candidate) | Delta  | p-value
──────────────────┼──────────────────┼───────────────────┼────────┼────────
Retrieval Accuracy| 87.2%            | 91.4%             | +4.2%  | 0.03
Latency p95       | 210ms            | 245ms             | +35ms  | 0.08
User Satisfaction | 4.2/5.0          | 4.5/5.0           | +0.3   | 0.04

AB-48 shows statistically significant improvement in accuracy and satisfaction
with a modest (not statistically significant) latency increase.

Recommendation: Consider promoting AB-48 to production with latency monitoring.

Would you like to:
1. View the detailed metric breakdown?
2. Declare AB-48 as the winner?
3. Design a follow-up experiment targeting latency?"
```

---

## Branching

### Why Branching Matters

Engineering investigations are nonlinear. An engineer investigating a question will naturally encounter sub-questions, alternative explanations, and competing hypotheses. Branching allows the engineer to explore multiple paths without losing the main thread.

### Branch Model

```
Main investigation: "Why did health decrease?"
    │
    ├── Branch A: "Investigate latency finding"
    │   ├── Sub-branch A1: "Check if related to config change"
    │   └── Sub-branch A2: "Check if related to data volume"
    │
    ├── Branch B: "Investigate accuracy finding"
    │   └── Sub-branch B1: "Compare to last week's accuracy"
    │
    └── Branch C: "Check automation logs for anomalies"
```

### Branch Operations

| Operation | Description | Behavior |
|---|---|---|
| **Fork** | Create a new branch from any message in the conversation | Branch inherits all context up to the fork point. Branch has independent state. |
| **Switch** | Move between branches | Context switches to the selected branch. Previous branch position is preserved. |
| **Merge** | Combine findings from a branch back into the parent | Key findings from the branch are summarized and inserted into the parent conversation. |
| **Compare branches** | View differences between two branches | Side-by-side view of conclusions, decisions, and artifacts from each branch. |
| **Close branch** | End a branch without merging | Branch is archived with its findings preserved and linked to the parent conversation. |
| **Reference branch** | Reference findings from another branch in the current branch | Cross-branch references are visible as links. |

### Branching Rules

1. Branches are visible in a branch explorer within the conversation.
2. The current branch is always indicated in the conversation header.
3. Merging a branch is a reviewable action — the user reviews the branch summary before merging.
4. Branches inherit the parent conversation's pinned artifacts and time window.
5. A branch can itself be forked (sub-branches), creating a tree structure.
6. Deep branches (more than 3 levels) suggest that the investigation should become a separate conversation.

---

## Artifact Attachment Model

### How Conversations Attach to Platform Entities

Conversations and platform entities have a bidirectional attachment relationship:

```
Conversation ◄────► Finding
Conversation ◄────► Evidence
Conversation ◄────► Experiment
Conversation ◄────► Configuration Snapshot
Conversation ◄────► Decision Record
Conversation ◄────► Recommendation
Conversation ◄────► Analytics Report
Conversation ◄────► Automation Run
Conversation ◄────► Capability
Conversation ◄────► Dashboard
```

### Attachment Semantics

| Direction | Behavior |
|---|---|
| **Conversation → Artifact** | The conversation references an artifact. The artifact appears in the conversation's context. The artifact's detail page shows a list of conversations that reference it. |
| **Artifact → Conversation** | An artifact was created during a conversation. The artifact's detail page links back to the conversation where it was created. |
| **Manual pinning** | User explicitly pins an artifact to a conversation. The artifact is preserved in context regardless of conversation length. |
| **Auto-attachment** | When the assistant retrieves an artifact during a conversation, a soft reference is created. Soft references are evictable during context management. Auto-attachment is not visible in the artifact's conversation list unless the user explicitly interacts with the artifact. |

### Attachment Rules

1. Every artifact created during a conversation (recommendation, experiment definition, config snapshot) includes a `conversation_id` in its lineage.
2. Every artifact detail page shows a "Referenced in conversations" section with links to relevant conversations.
3. Artifacts can be detached from conversations without affecting the artifact itself.
4. Deleting a conversation does not delete its artifacts. Artifacts are independent platform entities.
5. Read-only artifacts (evidence, analytics reports) can be attached but never modified through conversations.

---

## Tool Interaction Lifecycle

### How Tools Appear Inside Conversations

Tool invocations are first-class conversation events, not hidden implementation details.

```
USER: "What findings were generated last night?"

VISIBLE IN CONVERSATION:

[Assistant is retrieving findings...]
  ├── Searching Evidence Engine...
  │   └── ✓ 12 findings found
  ├── Filtering by time window (last 24h)...
  │   └── ✓ 8 findings in time window
  └── Retrieving evidence summaries...
      └── ✓ 8 summaries retrieved

"Here are the findings from last night:"
[...response content...]
```

### Tool Lifecycle States

```
PLANNING ──► EXECUTING ──► STREAMING ──► COMPLETE
                │                          │
                ▼                          ▼
             FAILED                    CANCELLED
```

| State | Visible to User | User Can |
|---|---|---|
| **Planning** | Indicator: "Planning investigation..." | Cancel |
| **Executing** | Progress: "Retrieving experiment results... (45%)" | Cancel, view progress |
| **Streaming** | Partial results arriving in conversation | Read, continue |
| **Complete** | Results integrated into response | Interact with results |
| **Failed** | Error message with explanation | Retry, cancel, proceed without |
| **Cancelled** | "Search cancelled." | Proceed without |

### Long-Running Tools

For tools that take more than 5 seconds (experiments, evaluations, large searches):

1. The conversation enters Background Processing state.
2. A progress notification appears: "Evaluating experiment results... This may take a few minutes."
3. The user can navigate away. The conversation continues in the background.
4. On completion, the conversation is updated and a notification is sent.
5. Returning to the conversation shows the completed results.

### Tool Result Rendering

Tool results are rendered inline in the conversation as structured content:

- **Data tables:** Formatted tables with sortable columns
- **Charts:** Inline chart visualizations (sparklines, bar charts, comparison charts)
- **Artifact cards:** Compact artifact summaries with clickable links
- **Diffs:** Side-by-side or inline diff views
- **Timelines:** Sequential event displays

Tool results are interactive. Users can sort, filter, expand, and drill into results without leaving the conversation.

---

## Human Approval

### Approval Checkpoints

Certain actions within a conversation require explicit human approval before execution:

| Action | Approval Level | Behavior |
|---|---|---|
| **Launch experiment** | Review | Show experiment definition, variants, metrics. User reviews and confirms. |
| **Apply configuration** | Approve | Show config diff, rollback plan, risk assessment. User approves or rejects. |
| **Delete artifact** | Confirm | Show artifact summary and consequences. User confirms. |
| **Run automation** | Confirm | Show job type, parameters, expected duration. User confirms. |
| **Batch action (5+ items)** | Review | Show full list of affected items. User reviews scope. |
| **Rollback configuration** | Multi-step | Step 1: Show rollback target. Step 2: Show rollback plan. Step 3: Confirm. |
| **Dismiss finding** | Undo | Action executes immediately with undo window. |
| **Acknowledge finding** | Immediate | No confirmation needed. |

### Approval Interaction in Conversations

When an action requires approval, the conversation transitions to the Awaiting Approval state:

```
ASSISTANT: "Based on this investigation, I recommend creating
experiment AB-49 to test increasing the temperature parameter
from 0.7 to 0.8.

Experiment summary:
- Baseline: temperature 0.7 (current config)
- Candidate: temperature 0.8
- Duration: 48 hours
- Metrics: accuracy, latency, user satisfaction
- Rollback: automatic if accuracy drops below 85%

Would you like to launch this experiment?

[Approve] [Modify] [Reject]
```

- **Approve:** The action executes. The conversation records the decision.
- **Modify:** The user provides modifications. The assistant updates the proposal.
- **Reject:** The action is not executed. The conversation records the rejection with the user's reason.

### Approval Rules

1. The conversation cannot proceed past an approval checkpoint until a decision is made.
2. Approval checkpoints are skippable only if the user explicitly declines the action.
3. All approval decisions are recorded as Decision artifacts with full lineage.
4. The approval UI is rendered inline in the conversation, never in a separate modal or page.
5. Approvals that require a different user (Engineering Manager) are sent as notifications to that user. The conversation remains in Awaiting Approval until the approving user responds.

---

## Conversation Ending

### End States

| State | Description | Triggers |
|---|---|---|
| **Completed** | The investigation reached a natural conclusion. All actions have been taken or explicitly declined. | User marks as complete, assistant suggests completion after final action |
| **Dormant** | The conversation has been inactive for a configurable period (default: 7 days). Automatically moves to Archived after notification. | No user activity for 7 days |
| **Archived** | Actively closed. The conversation is searchable but removed from the active conversations list. | User archives, dormant timeout expires |
| **Superseded** | A newer conversation contains more up-to-date investigation results. The old conversation is linked to the new one. | User creates a continuation, newer investigation covers the same scope |
| **Merged** | A branch was merged into its parent conversation. The branch remains accessible from the parent. | User executes merge operation |
| **Deleted** | Permanently removed. Only available for conversations with no attached artifacts or decisions. | User deletes (with confirmation, only if no persistent artifacts) |

### Completion Detection

The assistant can suggest completion when:

1. A decision was made and action was executed.
2. The user explicitly states the investigation is done.
3. A recommendation was rejected and the user has no further questions.
4. The conversation has been idle for 5 minutes after the last action.

### Reopening

Archived conversations can be reopened:

1. The full conversation history is restored.
2. The conversation state returns to Active.
3. A new entry is added to the conversation indicating it was reopened.
4. The assistant acknowledges the return: "Welcome back. We were investigating finding #1024. Would you like to continue?"
5. Context from the original conversation is preserved (summarized if necessary).

---

## Searchability

### Finding Archived Conversations

Conversations are searchable through multiple dimensions:

| Dimension | Search Method | Example |
|---|---|---|
| **Text content** | Full-text search across all messages and responses | "retrieval accuracy experiment" |
| **Attached artifacts** | Search by artifact ID, type, or title | "finding #1024" |
| **Time** | Filter by creation date, last activity, or time range | "conversations from last week" |
| **Participants** | Filter by user | "conversations by @priya" |
| **Intent** | Filter by conversation mode (investigate, compare, etc.) | "mode:compare" |
| **Outcome** | Filter by end state (completed, archived, has decisions) | "has:decision" |
| **Tags** | User-defined tags on conversations | "tag:incident" |
| **Capabilities** | Filter by capabilities referenced | "capability:evidence-engine" |

### Organization

Active conversations are organized by recency in the conversation list. Users can:

- **Pin** important conversations to the top of the list
- **Tag** conversations for categorization
- **Group** conversations by investigation topic
- **Bookmark** specific messages within conversations
- **Share** conversations (read-only or with comment permission)
- **Export** conversations as markdown or JSON

### Search Rules

1. All conversations are searchable by default. Users cannot hide conversations from search.
2. Deleted conversations are removed from search results.
3. Search respects permissions. A user cannot search conversations they do not have access to.
4. Search results show: conversation title (auto-generated or user-defined), first message preview, last activity timestamp, artifact count, outcome summary.

---

## Cross-Experience Navigation

### Movement Between Conversation and Console

Users can move between the assistant conversation and the Operations Console fluidly:

```
Conversation                              Operations Console
─────────────────────────────             ─────────────────────────
[Assistant response references          Finding Detail (#1024)
 finding #1024]                          • Full evidence timeline
                                         • Interactive lineage graph
                                         • Action panel
  ┌─────────────────────────┐
  │ 🔗 Open in Console      │──────►   (All filters preserved
  └─────────────────────────┘           from conversation context)
              │
              │ (User clicks
              │  "Return to
              │  conversation")
              ◄──────────────────────
```

### Navigation Rules

1. **Conversation → Console:** Clicking an artifact link in a conversation opens the artifact in the Operations Console. The conversation remains open in the background. The user can return to the conversation via a "Return to conversation" breadcrumb or the conversation list.

2. **Console → Conversation:** Opening an artifact that was created during a conversation shows a "View in conversation" link. Clicking it opens the conversation scrolled to the message where the artifact was created.

3. **Dashboard → Conversation:** Dashboard widgets that show pending items offer an "Investigate in Assistant" action that creates a new conversation or continues an existing one with that item as context.

4. **Notification → Conversation:** Notifications about findings, completed experiments, or pending approvals open the relevant conversation (or create one if none exists for that item).

5. **Command Palette → Conversation:** The command palette can search conversations, create new conversations, and navigate to specific messages within conversations.

6. **Search → Conversation:** Global search results include conversations. Selecting a conversation navigates to it with the matching message highlighted.

### Context Preservation on Transition

When moving between conversation and console:

1. The active artifact, time window, and any pinned context are carried over.
2. The destination page acknowledges the source: "Opened from conversation: Health Investigation"
3. The user can return to the source conversation in one click.
4. Changes made in the console (dismissing a finding, approving a recommendation) are reflected in the conversation on return.

---

## Future Evolution

### Multi-Agent Conversations

When multiple AI agents participate in a conversation:

1. Each agent has a distinct identity visible in the conversation.
2. Agent handoffs are explicit: "Transferring to Experimentation Specialist."
3. Multi-agent discussions are presented as parallel or sequential threads.
4. The user can address specific agents: "Ask the Evidence Agent to verify this."
5. Agent attribution is recorded for every tool invocation and response.

### Collaborative Investigations

When multiple human users participate in a conversation:

1. Each user has a distinct identity and color.
2. Users can see each other's messages in real time.
3. Decisions show who made them: "Approved by @marcus"
4. Users can @-mention other users within conversations.
5. Conversation branches can be assigned to different users.
6. Read receipts and typing indicators exist for human participants.

### Live Incident Response

During active incidents:

1. Conversations can be designated as "incident" mode.
2. Incident conversations get priority notification routing.
3. Incident conversations are automatically pinned and tagged.
4. The assistant switches to a more direct, action-oriented tone.
5. Approval workflows are streamlined for incident response (with post-incident audit).
6. A post-incident review conversation is automatically generated.

### Background Agents

Persistent monitoring agents can run alongside user conversations:

1. Background agents have their own conversation threads that the user can inspect.
2. Agents can notify the user when conditions are met: "I've been monitoring the latency trend and it has stabilized."
3. Agent conversations are distinguishable from user-initiated conversations.
4. Users can configure which agents run in their workspace.

### Autonomous Planning

Future conversations may include autonomous planning phases:

1. The assistant creates an investigation plan before executing.
2. The user reviews and approves the plan (or modifies it).
3. The assistant executes the plan, reporting progress at each step.
4. The user can intervene, redirect, or cancel at any point.
5. Completed plans are saved as reusable investigation templates.

---

## Appendix: Conversation Artifact Schema

Every conversation produces at least the following metadata as an artifact:

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Unique conversation identifier |
| `title` | String | Auto-generated or user-defined title |
| `created_at` | Timestamp | When the conversation was created |
| `updated_at` | Timestamp | Last activity timestamp |
| `status` | Enum | Current conversation state |
| `creator` | User ID | Who created the conversation |
| `participants` | User ID[] | All human participants |
| `entry_point` | Enum | How the conversation started (assistant, dashboard, notification, deep link, branch) |
| `mode` | Enum | Primary conversation mode |
| `pinned_artifacts` | Artifact ID[] | Explicitly pinned artifacts |
| `generated_artifacts` | Artifact ID[] | Artifacts created during this conversation |
| `decision_ids` | Decision ID[] | Decisions made during this conversation |
| `tags` | String[] | User-defined tags |
| `parent_conversation` | Conversation ID | If this is a branch, the parent conversation |
| `branches` | Conversation ID[] | Branches forked from this conversation |
| `message_count` | Integer | Total messages |
| `summary` | String | Auto-generated conversation summary |
| `lineage` | Lineage Parent | Parent reference for artifact lineage |
