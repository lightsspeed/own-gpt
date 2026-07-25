# Tool Invocation Architecture

> Tools are how the assistant interacts with the platform.
>
> Every tool invocation is a first-class interaction — visible, explainable, auditable.
>
> This document defines HOW TOOL EXECUTION SHOULD FEEL TO USERS.

---

## Purpose

### Why Tools Exist

The assistant's LLM reasoning alone cannot access live platform data, query the Evidence Engine, launch experiments, or modify configuration. Tools bridge the gap between natural language understanding and platform capabilities.

Tools transform the assistant from a conversational interface into an engineering collaborator. The assistant does not just answer questions — it *does* things: retrieves evidence, compares experiments, drafts recommendations, generates reports.

### Why LLM Reasoning Alone Is Insufficient

LLM reasoning is stateless, training-data-bound, and incapable of platform interaction. Without tools:

- The assistant cannot access live metrics or findings
- The assistant cannot verify its claims against current platform state
- The assistant cannot execute actions on the user's behalf
- The assistant cannot produce artifacts with lineage

Tools make the assistant trustworthy because every claim can be verified against live platform data, every action is recorded with lineage, and every result is grounded in evidence.

### Why Tool Invocation Builds Trust

Tool invocation is transparent by design. Users see:

- **What** tool is being called
- **Why** it is needed (the reasoning that led to the invocation)
- **What** it returned (the raw or summarized results)
- **What** evidence it used (source artifacts)
- **What** happens next (suggested actions based on results)

This transparency turns tool invocation from a hidden implementation detail into a trust-building interaction.

---

## Tool Invocation Philosophy

### Reason before action

The assistant explains *why* a tool is needed before invoking it. The user should never wonder why a search started or a recommendation was generated.

**Example:** "To understand why health decreased, I need to retrieve the latest evaluation report and recent findings. Let me search for those."

### Plan before execution

For multi-tool workflows, the assistant presents the plan before executing. The user sees the sequence of tool calls and can approve, modify, or cancel.

**Example:** "I'll investigate this finding by: (1) retrieving the evidence timeline, (2) checking related metrics in Analytics, (3) searching for similar historical findings. Shall I proceed?"

### Preview before mutation

Tools that create, update, or delete platform state show a preview of the change before execution. Users verify before committing.

**Example:** Before creating a recommendation: "Here is the draft recommendation based on my analysis. Please review before I submit it."

### Evidence before recommendation

Tools that produce recommendations always surface the supporting evidence alongside the recommendation. Users evaluate the evidence, not just the conclusion.

### Human approval before production impact

Any tool invocation that could affect production behavior requires explicit human approval before execution. Read-only tools do not require approval.

### Transparency over hidden execution

Tool invocations are always visible in the conversation. The user sees when a tool starts, what progress it makes, and what results it returns. Background execution is reserved only for long-running tools that the user explicitly delegates.

### Progress over waiting

Users should never see an indeterminate spinner for tool execution. Every tool invocation communicates: what stage it is in, how long it might take, and what it has produced so far.

### Recovery over failure

Tool failures are not dead ends. Every failure offers recovery options: retry, fallback to alternative tools, proceed with partial results, or cancel.

---

## Universal Tool Lifecycle

### Full Lifecycle

```
INTENT RECOGNITION
    │
    ▼
PLANNING
    │
    ▼
TOOL SELECTION
    │
    ▼
EXECUTION PREVIEW  ───► APPROVAL (if required)
    │                              │
    │                    ┌─────────┴─────────┐
    │                    ▼                   ▼
    │               APPROVED             REJECTED
    │                    │                   │
    └────────────────────┘                   │
         │                                   │
         ▼                                   ▼
    EXECUTION                          CONVERSATION UPDATE
         │                          (with rejection reason)
         ▼
    PROGRESS STREAMING
         │
         ▼
    RESULT INTEGRATION
         │
         ▼
    EVIDENCE ATTACHMENT
         │
         ▼
    SUGGESTED NEXT ACTIONS
         │
         ▼
    CONVERSATION UPDATE
         │
         ▼
    ARTIFACT CREATION (if applicable)
         │
         ▼
    COMPLETION
```

### Stage Descriptions

#### 1. Intent Recognition

The assistant determines that answering the user's question or fulfilling their request requires platform data or action beyond what conversation context provides.

**User sees:** The assistant may acknowledge the need: "Let me look that up."

#### 2. Planning

For simple tools, planning is immediate — the assistant knows which tool to call. For complex multi-tool workflows, the assistant creates a plan.

**User sees:** For multi-tool workflows, the plan is presented: "I'll search findings, check analytics, and review the last evaluation. Shall I proceed?"

#### 3. Tool Selection

The assistant selects the specific platform capability to invoke. Selection is based on intent, available tools, and user permissions.

**User sees:** The tool name is displayed: "Searching the Evidence Engine..."

#### 4. Execution Preview

For mutation tools (create, update, delete), the assistant shows a preview of what will happen before executing.

**User sees:** A preview card showing the proposed action, parameters, and expected outcome.

#### 5. Approval

If the tool requires approval, the assistant presents the preview and asks for confirmation. Approval levels are defined in the Approval Model section.

**User sees:** An approval prompt within the conversation. Options vary by approval level.

#### 6. Execution

The tool executes. The assistant communicates that execution has started.

**User sees:** "Running..." or "Processing..." with the tool name.

#### 7. Progress Streaming

For long-running tools, progress is streamed. The user sees intermediate states, partial results, and estimated completion.

**User sees:** Progress bar, status messages, intermediate results as they become available.

#### 8. Result Integration

The tool's output is integrated into the conversation. Results are formatted based on their type (table, chart, list, artifact card, natural language summary).

**User sees:** Formatted results inline in the conversation.

#### 9. Evidence Attachment

The tool's results are linked to their source evidence. Every claim in the results is traceable.

**User sees:** Source citations, timestamps, and evidence links attached to results.

#### 10. Suggested Next Actions

Based on the tool's results, the assistant suggests what the user can do next.

**User sees:** Action chips or buttons: "View the finding", "Compare with previous", "Create recommendation", "Ask a follow-up question."

#### 11. Conversation Update

The tool execution is recorded in the conversation history as a structured event. The user can review it later.

**User sees:** The tool execution appears as an expandable entry in the conversation timeline.

#### 12. Artifact Creation

If the tool produced a new artifact (recommendation, experiment definition, config snapshot, report), the artifact is created and linked to the conversation.

**User sees:** An artifact card with a link to the new artifact.

#### 13. Completion

The tool lifecycle ends. The conversation returns to Active state, awaiting user input.

---

## Tool Categories

### Category Definitions

| Category | Examples | Interaction Expectation |
|---|---|---|
| **Read** | Retrieve finding, get config, view health | Immediate execution. No approval. Results stream inline. |
| **Search** | Full-text search, artifact search, filter | Immediate execution. Results stream as they are found. |
| **Analyze** | Compute trend, aggregate metrics, detect anomaly | May take 2-10 seconds. Progress indicator shown. Results include confidence. |
| **Compare** | Experiment A vs B, config diff, health period comparison | May involve multiple read tools. Results are structured comparison views. |
| **Generate** | Create report, draft recommendation, generate summary | May take 5-30 seconds. Preview is shown before finalization. Results are artifacts. |
| **Recommend** | Suggest action, propose config change, recommend experiment | Requires evidence attachment. Includes confidence score. May require approval. |
| **Evaluate** | Run evaluation, compute metrics, assess health | Long-running (30s-5min). Progress streamed. Results are artifacts. |
| **Experiment** | Define experiment, launch run, compare variants | Multi-step. Requires approval. Long-running. Results produce decisions. |
| **Configuration** | View config, create snapshot, diff, rollback | Read: immediate. Mutation: requires approval. Diffs are previewed. |
| **Automation** | Run job, trigger evaluation, execute schedule | Requires confirmation. Long-running. Progress streamed. Results are artifacts. |
| **Reporting** | Generate daily brief, export report, compile summary | May take 10-60s. Streams intermediate results. Final output is an artifact. |

### Category Interaction Rules

1. **Read and Search** tools never require approval. They are the default path for information retrieval.
2. **Generate and Recommend** tools show a preview before creating artifacts. The preview is dismissable.
3. **Experiment, Configuration (mutation), and Automation** tools require explicit approval.
4. **Evaluate** tools show intermediate progress but do not require approval to start (they are read-only with respect to production state).
5. **Compare** tools are read-only but may take time to gather data. They show progress for each data source.

---

## Approval Model

### Approval Levels

| Level | Behavior | User Experience | Tool Categories |
|---|---|---|---|
| **No approval** | Tool executes immediately. No user interruption. | Tool execution appears in conversation with results. | Read, Search, Compare, Analyze |
| **Notification only** | Tool executes immediately. User is notified after completion. | Brief notification: "Report generated." No interruption. | Reporting, Evaluate (if user initiated) |
| **Soft confirmation** | Tool shows a brief confirmation prompt. Single click to proceed. | Inline chip: "Show results?" or "Proceed?" Default action proceeds after 5 seconds. | Generate (drafts) |
| **Review required** | Tool shows a preview of what will happen. User reviews and explicitly confirms. | Preview card with details. "Approve" or "Modify" buttons. | Recommend, Generate (final artifacts) |
| **Explicit approval** | Tool requires explicit user approval. Preview includes full scope and consequences. | Approval prompt with scope summary, risk assessment, and undo information. | Experiment (launch), Config (create/modify) |
| **Multi-step approval** | Tool requires multiple distinct confirmations. Each step shows different information. | Step 1: Scope review. Step 2: Consequence acknowledgment. Step 3: Final confirmation. | Config (production rollout), Automation (destructive) |
| **Production approval** | Tool requires approval from a user with production permissions (may be different from the requesting user). | Approval request sent to authorized user. Original user is notified when approved or rejected. | Config (production apply), Experiment (production rollout) |
| **Emergency override** | Authorized users can bypass normal approval for urgent situations. Requires post-action audit. | Override requires explicit risk acknowledgment and post-action report. | Rollback, incident response |

### Approval Rules

1. The approval level is determined by the tool category and the specific action, never by the UI context.
2. Approval prompts include: what will happen, what evidence supports the action, what the consequences are, and what the rollback plan is (if applicable).
3. Users can provide a reason when rejecting, which is recorded in the conversation and artifact lineage.
4. Approval decisions are recorded as Decision artifacts with full lineage.
5. Emergency overrides are logged with the override reason and user identity for audit.
6. The same tool invoked from different entry points (assistant, console, command palette) uses the same approval level.

---

## Progress Model

### Progress States

```
QUEUED ──► STARTING ──► RUNNING ──► COMPLETED
              │             │
              │             ├──► WAITING (for external dependency)
              │             │        │
              │             │        ▼
              │             │     RESUMED ──► COMPLETED
              │             │
              │             ├──► RETRYING ──► RUNNING
              │             │        │
              │             │        ▼
              │             │     FAILED ──► RECOVERED ──► COMPLETED
              │             │
              │             └──► CANCELLED
              │
              └──► FAILED ──► RECOVERED ──► COMPLETED
```

### State Descriptions

| State | User Sees | Duration |
|---|---|---|
| **Queued** | "Waiting to start..." with position in queue | Brief (< 2s) |
| **Starting** | "Starting..." with tool name | Brief (< 1s) |
| **Running** | Progress bar or spinner with status message and elapsed time | Variable |
| **Waiting** | "Waiting for [dependency]..." with estimated wait time | Variable (external dependencies) |
| **Retrying** | "Retrying... attempt 2 of 3" with progress indicator | Brief per attempt |
| **Completed** | Results displayed inline | Terminal |
| **Failed** | Error message with failure reason and recovery options | Terminal |
| **Recovered** | "Recovered from failure. Results may be partial." with results | Terminal |
| **Cancelled** | "Cancelled." with note about what was done before cancellation | Terminal |
| **Partial Success** | Results displayed with a warning banner: "Some data may be incomplete." | Terminal |

### Progress Display Rules

1. Tools expected to complete in under 2 seconds show a brief spinner. No progress bar needed.
2. Tools expected to take 2-30 seconds show a progress bar with status message.
3. Tools expected to take 30+ seconds show: progress bar, estimated time remaining, intermediate results as they become available, and a "Notify me" option.
4. Progress is always cancellable by the user. Cancellation returns partial results if available.
5. Progress messages are human-readable: "Retrieving findings from the Evidence Engine..." not "Executing tool_id=42."

---

## Streaming Philosophy

### What Should Stream

| Content | Stream? | Why |
|---|---|---|
| **Planning steps** | Yes | Users see the assistant's plan as it forms. Builds trust through transparency. |
| **Progress updates** | Yes | Users see tool execution progress in real time. Reduces uncertainty. |
| **Intermediate findings** | Yes | Partial results are displayed as they become available. Users can start reading before the tool completes. |
| **Generated artifacts** | Yes | Artifact cards appear progressively as content is generated. |
| **Warnings** | Yes | Warnings are displayed immediately when detected, not batched with final results. |
| **Evidence** | Yes | Evidence citations appear as they are retrieved. Users can inspect evidence while the tool continues. |
| **Final summary** | Yes | The summary is the last thing to arrive, after all supporting content is already visible. |
| **Suggested actions** | Yes | Action suggestions appear after the summary. |

### Why Streaming Matters

Streaming transforms tool invocation from a blocking operation into a transparent collaboration. Users do not wait for a black box to finish — they watch the assistant work, see intermediate results, and can form an understanding before the final response arrives.

Streaming also enables partial interaction. If a user sees early evidence that answers their question, they can interrupt the tool and move on without waiting for full completion.

### Streaming Rules

1. Streaming always starts within 500ms of tool invocation.
2. The user can interrupt streaming at any point. Interrupting stops the tool and shows partial results.
3. Streaming content is progressively stable. Text does not reflow once rendered. New content appends.
4. Streaming works consistently across all tool categories.
5. When the user scrolls away from streaming content, a "New content available" indicator appears.

---

## Tool Results

### Every Tool Result Should Define

| Component | Description | User Experience |
|---|---|---|
| **Summary** | A concise natural language summary of what the tool produced. | First thing the user reads. 1-3 sentences. |
| **Evidence** | The source data or artifacts that support the results. | Citation links, evidence cards. Collapsible. |
| **Confidence** | How confident the assistant is in the results (for AI-mediated results). | Badge or indicator. Shown near the summary. |
| **Generated artifacts** | Any new artifacts created by the tool. | Artifact cards with type, ID, title, and link. |
| **Warnings** | Any caveats, limitations, or known issues with the results. | Warning banner with icon. Visually distinct. |
| **Limitations** | What the tool could not do or what data it could not access. | Brief note below results. Honest about gaps. |
| **Related conversations** | Other conversations that referenced similar artifacts. | Links to related conversations. |
| **Next actions** | Suggested actions the user can take based on the results. | Action chips or buttons. 2-4 suggestions. |

### Result Formatting

Tool results are formatted for readability:

- **Tables** are rendered as structured tables with sortable columns
- **Lists** are rendered as bulleted or numbered lists with expandable items
- **Charts** are rendered as inline visualizations
- **Diffs** are rendered as side-by-side or unified diff views
- **Artifact cards** are rendered as compact cards with type icon, ID, title, status, and link
- **Timelines** are rendered as sequential event displays

### Result Rules

1. Results are always summarized in natural language before any structured data.
2. Evidence citations are always included with every result that makes factual claims.
3. Warnings and limitations are displayed before the detailed results.
4. Results that span more than 20 lines are collapsible by default with a "Show more" toggle.
5. Results are persistent in the conversation history. They do not disappear or expire.

---

## Failure Philosophy

### Failure Types and Responses

| Failure Type | User Sees | Recovery Options |
|---|---|---|
| **Tool unavailable** | "The [tool name] is currently unavailable. This may be due to a platform issue." | Retry, use alternative tool, proceed without |
| **Timeout** | "The request timed out after [duration]. Partial results may be available." | View partial results, retry with longer timeout, narrow the scope |
| **Permission denied** | "You don't have permission to access this tool or data." | Request access, contact admin, use an alternative approach |
| **Invalid input** | "The request couldn't be processed. [Specific error message]" | Correct the input, ask the assistant for guidance |
| **Partial results** | Results displayed with a banner: "Some results could not be retrieved. [Specific reason]" | Use available results, retry the failed portion |
| **Cancelled** | "Tool execution was cancelled." with partial results if available | Use partial results, restart the tool |
| **Conflicting evidence** | Results show conflicting data with both sources presented: "Source A claims X, Source B claims Y." | Investigate both sources, request additional evidence |
| **Platform unavailable** | "The platform is experiencing connectivity issues. I cannot access [affected tools]." | Retry, check platform status, work with available context |
| **Recovered failure** | "An error occurred, but I was able to recover. Results may be partial." | Review results, check for completeness, retry if needed |

### Failure Rules

1. Every failure is communicated to the user within 2 seconds.
2. Failures include a clear explanation of what went wrong, not just an error code.
3. Failures that occur during streaming show the partial results received before the failure.
4. Recovery options are always offered. "It failed" is never the final message.
5. Silent failures are forbidden. If a tool fails, the user always knows.
6. Repeated failures of the same tool within a conversation trigger a suggestion to use an alternative approach.

---

## Conversation Integration

### How Tool Execution Appears in Conversation

Tool execution is a visible, structured part of the conversation:

```
USER: "Why did health decrease last night?"

ASSISTANT: Let me investigate that.

┌─ Tool: Search Evidence Engine ──────────────────────────┐
│  Searching for findings from last 24 hours...            │
│  ✓ 12 findings found                                    │
│  Filtering by health-related...                         │
│  ✓ 3 health-related findings identified                 │
└─────────────────────────────────────────────────────────┘

┌─ Tool: Retrieve Health Report ──────────────────────────┐
│  Retrieving latest health snapshot...                    │
│  ✓ Health snapshot from 03:00 UTC loaded                 │
└─────────────────────────────────────────────────────────┘

Here's what I found:

Platform health decreased from 96 to 84 between 02:00 and 03:00 UTC.
The primary contributor was the Evidence Engine capability, which
experienced increased latency.

[Evidence: Health Snapshot #HS-2024-03-24]
[Evidence: Finding #1021, #1022, #1023]

Would you like me to investigate any of these findings in detail?
```

### Conversation History

Tool executions are recorded in the conversation history as structured entries:

- Tool name and type
- Input parameters (summarized)
- Execution duration
- Results summary
- Evidence references
- Approval decisions (if applicable)
- Generated artifacts

Users can expand past tool executions to review details. Tool entries are visually distinct from user messages and AI responses.

### Conversation Integration Rules

1. Tool executions are always rendered inline in the conversation — never in a separate window or modal.
2. Multiple tool executions in a workflow are shown sequentially with clear separation.
3. The user can scroll back to review past tool executions at any time.
4. Long-running tool executions that complete after the user has navigated away update the conversation asynchronously with a notification.
5. Tool executions are included in conversation search and export.

---

## Artifact Integration

### Artifact Creation by Tools

When a tool creates or updates an artifact, the following happens:

| Action | Artifact Behavior | Lineage |
|---|---|---|
| **Generate report** | New report artifact created | Parent: conversation. Evidence: tool inputs. |
| **Launch experiment** | New experiment definition artifact created | Parent: conversation, source recommendation (if applicable). |
| **Create recommendation** | New recommendation artifact created | Parent: conversation, source finding(s). |
| **Propose config snapshot** | New config snapshot artifact created (draft) | Parent: conversation, source experiment/decision. |
| **Run evaluation** | New evaluation result artifact created | Parent: conversation. Evidence: tool outputs. |
| **Create learning record** | New learning record artifact created | Parent: conversation. Evidence: tool interaction. |
| **Execute automation** | New automation run artifact created | Parent: conversation. Evidence: job results. |
| **Record decision** | New decision artifact created | Parent: conversation, source recommendation/experiment. |

### Attachment Rules

1. Every artifact created by a tool during a conversation includes a `conversation_id` in its lineage.
2. The artifact detail page shows "Created in conversation: [link]" linking back to the conversation.
3. The conversation shows "Artifact created: [link]" as part of the tool result.
4. Artifacts persist independently of the conversation. Deleting the conversation does not delete the artifacts.
5. Artifacts created by tools are labeled with both the tool name and "AI-generated" or "AI-assisted" as appropriate.

---

## Trust Model

### How Users Should Trust Tool Execution

| Trust Factor | Implementation | User Experience |
|---|---|---|
| **Execution logs** | Every tool invocation records: tool name, inputs, outputs, duration, errors. | Available in tool execution details. Expandable. |
| **Evidence** | Every result cites its source artifacts. | Citations are clickable links to source artifacts. |
| **Timing** | Start time, end time, and duration are recorded. | Displayed in tool execution details. |
| **Inputs** | The parameters passed to the tool are recorded. | Visible in expanded tool details. |
| **Outputs** | The full output of the tool is recorded. | Visible in the conversation. Expandable for large outputs. |
| **Confidence** | AI-mediated results include confidence scores. | Badge or indicator near results. |
| **Approval history** | Approval decisions are recorded with user identity and timestamp. | Visible in artifact lineage and decision records. |
| **Lineage** | Every tool execution links to its parent conversation and produces artifacts with lineage. | Navigable lineage graph from any artifact. |
| **Explainability** | The assistant can explain why a tool was selected and how it produced its results. | "Show reasoning" section on tool execution. |

### Trust Rules

1. Tool execution details are always accessible. No invisible tool calls.
2. Users can inspect the full input and output of any past tool execution.
3. Approval decisions are immutable and auditable.
4. If a tool produces unexpected results, the assistant acknowledges the discrepancy and offers to investigate.

---

## Multi-Tool Workflows

### Orchestration Principles

1. **Plan before execution.** For workflows involving 3+ tools, the assistant presents the plan before starting.
2. **Sequential by default.** Tools execute sequentially to maintain clarity. Parallel execution is used only when tools are independent and the user has been informed.
3. **Each step is visible.** Every tool in a multi-tool workflow is shown as a separate step with its own progress and results.
4. **Early results can skip steps.** If the first tool in a workflow produces sufficient information, the assistant offers to skip remaining steps.
5. **Failure in one step does not block the entire workflow.** Independent steps can still execute. Dependent steps offer alternatives.

### Example Multi-Tool Workflow

```
USER: "Should I approve the pending config change?"

ASSISTANT: Let me evaluate that by reviewing the change and its impact.

Plan:
1. Retrieve the pending config snapshot
2. Diff it against the current configuration
3. Check if any experiments were run with similar parameters
4. Review the experiment results
5. Summarize the risk assessment

Shall I proceed?

USER: "Yes."

[Step 1/5: Retrieving config snapshot... ✓]
[Step 2/5: Computing diff... ✓]
[Step 3/5: Searching for related experiments... ✓]
[Step 4/5: Retrieving experiment results... ✓]
[Step 5/5: Generating risk assessment... ✓]

Here is my assessment of config snapshot v143:

[Summary, evidence, risk assessment, recommendation]

Would you like to approve this change?
```

### Workflow Rules

1. Multi-tool workflows are interruptible. The user can approve, modify, or cancel the plan at any point.
2. Workflows that take more than 30 seconds offer a "Notify me when complete" option.
3. Completed workflows are saved as conversation history and can be replayed.
4. Frequently used workflows can be saved as templates for one-click execution.

---

## AI Responsibilities

### The Assistant SHOULD

| Responsibility | Behavior |
|---|---|
| **Plan** | Present a plan before executing multi-tool workflows. |
| **Explain** | Explain why each tool is needed before invoking it. |
| **Recommend** | Recommend actions based on tool results, with evidence and confidence. |
| **Summarize** | Summarize tool results in natural language before showing structured data. |
| **Warn** | Warn the user when tool results are incomplete, conflicting, or low-confidence. |
| **Request approval** | Request explicit approval before any mutation tool or production-impacting action. |
| **Interpret results** | Explain what the tool's results mean in the context of the user's question. |
| **Guide next actions** | Suggest what the user can do next based on the results. |
| **Offer alternatives** | When a tool fails, offer alternative tools or approaches. |
| **Admit limitations** | When a tool cannot answer the question, say so clearly. |

### The Assistant MUST NOT

| Prohibition | Example Violation |
|---|---|
| **Execute destructive operations silently** | Deleting an artifact without telling the user. |
| **Hide failures** | A tool fails but the assistant pretends it succeeded. |
| **Invent tool outputs** | Fabricating results that a tool did not produce. |
| **Skip approval** | Executing a production-impacting action without confirmation. |
| **Suppress uncertainty** | Presenting low-confidence results with high certainty. |
| **Execute without context** | Running a tool without explaining why it is needed. |
| **Ignore user preferences** | Executing a tool the user has previously asked to avoid. |
| **Modify configuration without lineage** | Changing a setting without recording the change as an artifact. |
| **Assume intent** | Running tools based on assumptions without confirming with the user. |
| **Persist without consent** | Saving tool results as permanent artifacts without user awareness. |

---

## Anti-Patterns

### Forbidden Tool Invocation Behaviors

1. **Invisible execution.** Running tools without the user knowing. Every tool invocation must be visible in the conversation.

2. **Silent failures.** A tool fails and the assistant continues as if nothing happened. Failures are always communicated.

3. **Endless spinners.** Tools that show progress without communicating what stage they are in or how long they might take.

4. **No progress updates.** Tools that take more than 5 seconds without showing any progress indicator.

5. **Skipping approval.** Executing production-impacting tools without requesting and receiving explicit approval.

6. **Hidden evidence.** Presenting tool results without showing the evidence that supports them.

7. **Unexplained recommendations.** Recommending actions without explaining why, based on what evidence.

8. **Duplicate tool execution.** Running the same tool twice for the same data within a conversation without acknowledging the cache.

9. **Inconsistent confirmations.** The same tool sometimes requires approval and sometimes does not, depending on where it is invoked.

10. **Blocking the user unnecessarily.** Waiting for a tool to complete when the user could proceed with partial results.

11. **No cancellation.** Tools that cannot be cancelled once started.

12. **Tool without context.** Running a tool without establishing why the user needs the information.

13. **Scope mismatch.** Running a broad search when a targeted query would suffice, or vice versa.

14. **Over-automation.** Executing a full multi-tool workflow without checking with the user at each decision point.

15. **False recovery.** Claiming recovery from a failure when the results are incomplete or incorrect.

16. **Unattributed results.** Presenting tool results without indicating which tool produced them.

17. **No fallback.** A tool fails and the assistant offers no alternative approach.

18. **Orphaned artifact generation.** Creating artifacts during tool execution that are not linked to the conversation.

19. **Approval fatigue.** Requiring approval for every minor action, causing users to approve without reading.

20. **Ignoring partial results.** Discarding partial results when a later step in a multi-tool workflow fails.

---

## Future Evolution

### Multiple Concurrent Tools

As the platform evolves, the assistant may invoke multiple tools simultaneously:

1. **Parallel execution** is visible as concurrent progress indicators.
2. **Dependency graphs** show which tools depend on which.
3. **Result merging** combines results from parallel tools into a unified view.
4. **Conflict resolution** identifies and surfaces conflicting results from parallel tools.

### Background Agents

Persistent agents may invoke tools independently:

1. Agent tool invocations are recorded in dedicated agent conversation threads.
2. Users can review, approve, or reject agent-initiated actions asynchronously.
3. Agent tool usage is bounded by explicit permissions and scope definitions.
4. Agent-invoked tools follow the same lifecycle, approval, and artifact rules.

### Scheduled Workflows

Tools may be invoked on a schedule:

1. Scheduled invocations create automation run artifacts.
2. Results are delivered to the user's notification feed.
3. Failed scheduled invocations trigger escalation workflows.
4. Scheduled workflows can be paused, modified, or cancelled.

### Autonomous Planning

The assistant may plan and execute bounded workflows autonomously:

1. Autonomous execution is limited to pre-approved scope and tool categories.
2. Autonomous plans are reviewed by the user before execution begins.
3. The user can revoke autonomy at any point during execution.
4. Autonomous execution logs are available for audit.

### Collaborative Execution

Multiple users interacting with the same tool workflow:

1. Tool invocations in shared conversations are visible to all participants.
2. Approval can be delegated to any authorized participant.
3. Tool results are shared across the conversation.
4. Collaborative tool usage is recorded with attribution.

### Long-Running Investigations

Some tool workflows may run for hours or days:

1. Long-running investigations are managed as persistent conversation sessions.
2. Progress is delivered as periodic updates in the conversation.
3. Users can add new instructions to an ongoing investigation.
4. Completed investigations produce comprehensive summary artifacts.

### Continuous Evaluation Integration

Tools become part of the continuous evaluation loop:

1. Tool effectiveness is measured and fed back into the platform.
2. Frequently failing tools trigger automated diagnostics.
3. Tool usage patterns inform capability improvements.
4. The platform learns which tools produce the most reliable results for which types of questions.
