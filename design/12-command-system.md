# Universal Command System

> The command system is how users express intent.
>
> Not "where is this feature?" — "what do I want to do?"
>
> The platform decides how to fulfill that intent.

---

## Purpose

### Why Command Systems Exist

Every great engineering tool converges on a command interface because commands respect how engineers think. Engineers do not think in terms of screen hierarchies or navigation menus. They think in terms of actions:

- "Compare these two experiments."
- "Show me what changed yesterday."
- "Explain why health dropped."
- "Create a recommendation from this finding."

A command system translates intent into action. It routes the user's goal to the appropriate platform capability without requiring the user to know which screen, module, or tool serves that capability.

### Why Intent-Based Interaction Is Superior

| Navigation-Based | Intent-Based (Command System) |
|---|---|
| "I need to go to Findings, then filter by severity, then scroll to find the one from last night." | "Show me critical findings from last night." |
| "Open Experiments, find AB-47, open its detail page, scroll to the comparison section." | "Compare experiment AB-47 with the baseline." |
| "Go to Configuration, find the pending snapshot, open the diff view." | "Show me the pending config change and what it affects." |

The command system collapses multi-step navigation into single-intent expression. It does not eliminate navigation — it delegates navigation decisions to the platform.

---

## Command Philosophy

### Intent before location

Users express what they want to accomplish, not where they want to go. The command system resolves intent to the appropriate platform capability. If the user says "Show me critical findings," the system decides whether to open the Findings list, generate a summary in the conversation, or display results inline.

Users should never need to know which module owns a capability to invoke that capability.

### Action before navigation

Commands default to producing results in the current context — inline in a conversation, as a side panel, or as a temporary overlay. Navigation to a full page happens only when the user explicitly requests depth or when the command's output requires a full-page view.

The command system prefers action over navigation. Navigation is a fallback, not the default.

### One entry point

Every command is reachable through a single entry point: the command palette (⌘K). The command palette is universal, omnipresent, and consistent. There is no secondary command interface for power users and a different one for casual users.

The command palette is augmented by natural language (assistant) and contextual actions (right-click menus, widget buttons), but the command palette is the canonical command interface.

### Universal availability

The command palette is available from every screen in the platform. It is not a feature of the assistant — it is a feature of the platform. The user never encounters a screen where ⌘K does nothing.

### Context awareness

Commands adapt to what the user is currently doing. The same command may behave differently depending on the current conversation, selected artifact, active module, and user role.

"Explain this" in a finding detail context explains the finding. "Explain this" in an experiment context explains the experiment. The user does not need to specify the subject — the system infers it from context.

### Progressive assistance

The command system scales from novice to expert:

- **Novice:** Types natural language. The system interprets intent and routes appropriately.
- **Intermediate:** Types partial commands. Autocomplete suggests completions.
- **Expert:** Types concise command syntax. The system executes directly.

All three approaches reach the same result. The user's proficiency determines the input style, not the outcome.

### Conversation integration

Commands invoked from the command palette are recorded in the current conversation (if one is active) or create a new conversation entry. Commands are not siloed in the command palette — they become part of the user's engineering history.

### Predictability

Similar inputs produce similar results. "Show findings" and "list findings" and "find findings" all resolve to the same command. The command system normalizes input variation without surprising the user.

### Explainability

If the command system cannot resolve intent with high confidence, it explains what it understood and asks for clarification. It never silently executes the wrong command.

### Non-destructive by default

Commands default to read-only or preview mode. Mutation requires explicit confirmation. The command system never assumes the user wants to change state unless the user explicitly indicates mutation intent.

---

## Command Lifecycle

### Full Lifecycle

```
INVOCATION
    │
    ▼
INTENT DETECTION
    │
    ├── Clear Intent ──────► COMMAND RESOLUTION
    │                              │
    └── Ambiguous Intent ──► CLARIFICATION
                                    │
                                    ▼
                            REFINED INTENT
                                    │
                                    ▼
                          COMMAND RESOLUTION
                                    │
                                    ▼
                         CONTEXT DETECTION
                                    │
                                    ▼
                         EXECUTION PLAN
                                    │
                        ┌───────────┼───────────┐
                        │           │           │
                        ▼           ▼           ▼
                   IMMEDIATE    PREVIEW     APPROVAL
                   EXECUTION    REQUIRED    REQUIRED
                        │           │           │
                        ▼           ▼           ▼
                   EXECUTION    REVIEW ──►  APPROVAL
                                    │           │
                                    ▼           ▼
                              CONFIRM      EXECUTION
                                    │
                                    ▼
                              EXECUTION
                                    │
                                    ▼
                         RESULTS
                                    │
                                    ▼
                         CONVERSATION UPDATE
                                    │
                                    ▼
                         ARTIFACT CREATION
                                    │
                                    ▼
                         SUGGESTED NEXT COMMANDS
```

### Stage Descriptions

#### 1. Invocation

The user invokes the command system. Primary method: ⌘K / Ctrl+K. Alternate methods: typing in the assistant input, clicking a command button, selecting from a context menu, triggering a notification action.

**User sees:** The command palette opens with the input field focused.

#### 2. Intent Detection

The system processes the user's input. Intent detection considers: the input text, the current context (active screen, selected artifact, conversation history), the user's role and permissions, and recent activity.

**User sees:** As the user types, suggestions appear. The system may show a prefix that indicates the detected category: "Navigate to...", "Search for...", "Explain...", "Compare...".

#### 3. Clarification (if needed)

If intent is ambiguous, the system asks clarifying questions. Clarification is minimal — the system presents options rather than asking open-ended questions.

**User sees:** "Did you mean: (a) Show findings from last night, (b) Show findings related to health, (c) Show all critical findings?"

#### 4. Command Resolution

The resolved command is identified. The system knows which platform capability to invoke.

**User sees:** The resolved command is displayed in the palette: "Explain Finding #1024" or "Compare Experiments: AB-47 vs Baseline."

#### 5. Context Detection

The system gathers relevant context: current conversation, selected artifact, time window, filters, user role.

**User sees:** Context is detected automatically. No user action needed.

#### 6. Execution Plan

The system determines execution mode:
- **Immediate:** Read-only commands with deterministic results execute immediately.
- **Preview:** Commands that create or modify show a preview first.
- **Approval:** Commands with production impact require approval before execution.

**User sees:** For preview commands, the preview is shown. For approval commands, the approval prompt appears.

#### 7-9. Execution

The command executes. Execution follows the tool invocation lifecycle defined in 11-tool-invocation.md (progress streaming, intermediate results, completion).

**User sees:** Progress indicator, streaming results, completion confirmation.

#### 10. Results

Results are displayed. Format depends on command type: inline text, structured data, artifact card, navigation to a page.

**User sees:** Results appropriate to the command.

#### 11. Conversation Update

The command and its results are recorded in the current conversation or create a new conversation entry.

**User sees:** The command appears in the conversation history as a structured entry.

#### 12. Artifact Creation

If the command produced a new artifact, it is created with lineage to the conversation and source context.

**User sees:** Artifact card with link to the new artifact.

#### 13. Suggested Next Commands

Based on the results, the system suggests 2-4 follow-up commands.

**User sees:** Action chips or buttons in the palette or conversation.

---

## Command Categories

### Category Definitions

| Category | Purpose | Typical Inputs | Expected Outputs | Safety |
|---|---|---|---|---|
| **Navigate** | Go to a screen or artifact | "go to findings", "open experiment AB-47", "show configuration" | Navigation to target | Immediate. No side effects. |
| **Search** | Find artifacts across the platform | "find critical findings", "search for retrieval experiments", "show recent decisions" | List of matching artifacts | Immediate. No side effects. |
| **Explain** | Get a natural language explanation | "explain finding #1024", "why did health drop?", "what does this mean?" | Natural language explanation with evidence | Immediate. No side effects. |
| **Investigate** | Multi-step root cause analysis | "investigate health degradation", "trace finding #1024", "why is latency high?" | Investigation report with evidence chain | Immediate. May take time. |
| **Compare** | Side-by-side comparison | "compare experiments AB-47 and AB-48", "diff config v142 and v143", "compare health today vs yesterday" | Structured comparison view | Immediate. No side effects. |
| **Generate** | Create artifacts | "generate report for last week", "create recommendation from finding #1024", "draft experiment plan" | New artifact with preview | Preview required. User confirms. |
| **Evaluate** | Compute metrics or assessments | "evaluate retrieval accuracy", "run health check", "assess config risk" | Evaluation results with confidence | Immediate (read-only evaluation). |
| **Experiment** | Design and launch experiments | "create experiment for recommendation #512", "launch experiment AB-49" | Experiment artifact | Approval required. |
| **Configure** | View or modify configuration | "show current config", "diff with v140", "create config snapshot" | Config data or new snapshot | Read: immediate. Write: approval required. |
| **Automate** | Run or manage automation | "run daily evaluation", "show automation status", "create schedule" | Automation run artifact | Confirmation required. |
| **Report** | Generate structured reports | "generate weekly report", "export findings", "compile evaluation summary" | Report artifact | Preview required. |
| **Learn** | Understand platform concepts | "how does the evidence engine work?", "what is a finding?", "teach me about experiments" | Educational content with references | Immediate. No side effects. |
| **Help** | Get assistance with the platform | "help", "what can I do?", "show commands" | Command list, shortcuts, documentation | Immediate. No side effects. |
| **Review** | Structured review of pending items | "review pending findings", "show my approval queue", "what needs my attention?" | Prioritized list with summaries | Immediate. No side effects. |
| **Summarize** | Condense information | "summarize last 24 hours", "brief me on platform health", "summary of experiment results" | Natural language summary with key points | Immediate. No side effects. |
| **Plan** | Create multi-step plans | "plan rollout for config v143", "create investigation plan for finding #1024" | Structured plan with steps and dependencies | Preview required. |
| **Teach** | Educational walkthrough | "walk me through the experiment workflow", "show me how to review findings" | Step-by-step guide with platform context | Immediate. No side effects. |

### Category Rules

1. Navigate and Search commands are the only categories that produce navigation as their primary output. All other categories prefer inline results.
2. Generate, Experiment, and Configure (write) commands always require preview before execution.
3. Automate commands always require explicit confirmation.
4. Explain, Investigate, Compare, Evaluate, Learn, Help, Review, Summarize, and Teach commands execute immediately without confirmation.
5. Plan commands show the plan as a preview. Execution of the plan follows the individual command rules for each step.

---

## Context Awareness

### Context Dimensions

| Dimension | Source | Effect on Commands |
|---|---|---|
| **Current conversation** | Active conversation ID | Commands reference recent artifacts, conversation subject, and previous questions. |
| **Selected artifact** | Currently viewed or selected artifact | "Explain this" resolves to the selected artifact. Commands can operate on it directly. |
| **Active module** | Current screen or module | "Show findings" in the Experiments module may filter to experiment-related findings. |
| **Current filters** | Active time window, capability filter, status filter | Commands respect active filters. "Show critical findings" uses the active time window. |
| **Pinned context** | Artifacts pinned to the current conversation | Commands can reference pinned artifacts without full ID specification. |
| **User role** | Authenticated user's permissions | Commands may be limited or expanded based on role. Approval requirements respect role. |
| **Current investigation** | Active investigation subject | Commands that relate to the ongoing investigation automatically reference the investigation subject. |
| **Recent activity** | Last 10 user actions | Command suggestions prioritize recently used commands. |
| **Workspace state** | Dashboard time window, expanded sections, open panels | Commands inherit workspace state. "Show health" uses the same time window as the dashboard. |

### Context Rules

1. Context is detected automatically. Users do not specify context explicitly.
2. Context is displayed in the command palette: "In context of: Finding #1024" appears above the results.
3. Users can override context explicitly: "Show findings for capability: evidence-engine" overrides the current module context.
4. When context cannot be detected, the command uses defaults (last 24 hours, all capabilities, user's role scope).
5. Context is shown to the user so they can verify the system understood their working context.

### Context Examples

| User Types | Context Detected | Resolved Command |
|---|---|---|
| "explain this" | Active: Finding Detail (#1024) | "Explain Finding #1024" |
| "compare" | Active: Experiments List (AB-47 selected) | "Compare Experiment AB-47 with..." (asks for second) |
| "show findings" | Active: Dashboard (time window: last 24h) | "Show findings from last 24 hours" |
| "create recommendation" | Active: Finding Detail (#1024) | "Create recommendation from Finding #1024" |
| "diff" | Active: Config Snapshot Detail (v143) | "Diff Config v143 with current" |

---

## Ambiguity Resolution

### When Intent Is Unclear

| Situation | Resolution | User Experience |
|---|---|---|
| Multiple commands match | Show options ranked by relevance | "Did you mean: (a) Show findings, (b) Explain findings, (c) Compare findings?" |
| Input is too vague | Ask for specific clarification | "Which time period?" or "Which capability?" |
| Input matches multiple artifacts | Show artifact selector | "Multiple findings match 'latency'. Which one?" with a short list. |
| Input could be navigate or action | Default to action (preview), offer navigation | "Show Finding #1024" shows the finding summary. "Open in console" is a secondary action. |
| Input requires parameter | Ask for the parameter | "Compare which experiments?" or "Generate report for which time period?" |
| Input is out of scope | Explain scope and offer alternatives | "I can search findings, experiments, and configs. I cannot search external documentation." |

### Ambiguity Rules

1. The system never guesses destructive intent. If there is any ambiguity about whether the user wants to read or mutate, the system defaults to read.
2. Clarification is presented as options, not open-ended questions. Users select from suggestions rather than retyping.
3. Clarification preserves what the system already understood. The user does not restate their entire intent.
4. If the system cannot resolve intent after two clarification rounds, it escalates to the assistant for natural language disambiguation.

---

## Command Preview

### When Previews Are Required

| Command Type | Preview Behavior |
|---|---|
| **Navigate** | No preview. Navigation is immediate. |
| **Search** | No preview. Results stream as they are found. |
| **Explain** | No preview. Response streams. |
| **Investigate** | No preview for the investigation itself. Steps within may preview. |
| **Compare** | Brief loading indicator. No full preview needed. |
| **Generate** | Preview shows the generated artifact before creation. User reviews and confirms. |
| **Evaluate** | No preview. Results stream. |
| **Experiment** | Preview shows the experiment definition. User reviews parameters. |
| **Configure (read)** | No preview. Results displayed. |
| **Configure (write)** | Preview shows the change diff. User reviews before committing. |
| **Automate** | Preview shows the job definition and expected impact. |
| **Report** | Preview shows the report structure. User confirms before full generation. |
| **Learn** | No preview. Content delivered. |
| **Help** | No preview. Content delivered. |
| **Review** | No preview. Results listed. |
| **Summarize** | No preview. Summary streams. |
| **Plan** | Preview shows the full plan. User reviews and approves before execution. |
| **Teach** | No preview. Content delivered. |

### Preview Principles

1. Previews show what will happen without executing it.
2. Previews are interactive. Users can modify parameters before confirming.
3. Previews show the scope of the action: "This will create a recommendation from Finding #1024 with the following content..."
4. Previews for destructive actions include consequences: "This will archive 15 findings. This action can be undone within 30 days."
5. Previews expire after 5 minutes. Users must re-preview if they take longer to decide.

---

## Conversation Integration

### How Commands Integrate

Commands and conversations are deeply integrated:

| Aspect | Behavior |
|---|---|
| **Recording** | Every command executed from the command palette is recorded in the current conversation. If no conversation is active, a new conversation entry is created. |
| **History** | Past commands are searchable in conversation history. Users can review what commands they executed and what results they produced. |
| **References** | Commands that reference artifacts create clickable artifact links in the conversation. |
| **Follow-up** | After a command executes, suggested next commands appear as clickable chips in both the palette and the conversation. |
| **Continuation** | Commands executed from the palette continue the existing conversation thread. The assistant is aware of the command and its results. |
| **Assistant commands** | Commands typed in the assistant input follow the same lifecycle. The assistant may augment the command with additional context. |

### Integration Rules

1. The command palette and the assistant input share the same command resolution system.
2. A command executed in the palette is visible in the conversation as: "User ran command: Compare Experiments AB-47 and AB-48 [results]."
3. A command typed in the assistant input is resolved through the same intent detection pipeline.
4. The assistant can suggest commands to the user: "You might want to: [Compare results] [Create recommendation]."
5. Commands that produce artifacts are linked in the conversation.

---

## Artifact Integration

### How Commands Interact with Artifacts

Commands create, update, compare, explain, and reference artifacts consistently:

| Command Action | Artifact Behavior |
|---|---|
| **Create** (Generate, Experiment, Configure write) | New artifact created with lineage to conversation and source context |
| **Update** (Configure write) | New version of artifact created. Previous version preserved. |
| **Compare** (Compare) | No artifacts created. Comparison result is ephemeral unless saved. |
| **Explain** (Explain, Investigate) | No artifacts created. Explanation is part of conversation history. |
| **Reference** (all commands) | Artifacts referenced by commands are linked in the conversation. |
| **Search** (Search) | No artifacts created. Search results are ephemeral. |
| **Delete** (via Configure or Automation) | Artifact archived with lineage. Requires multi-step confirmation. |

### Integration Rules

1. Artifacts created by commands include a `command_id` and `conversation_id` in their lineage.
2. Artifacts referenced by commands appear in the artifact's "Referenced in conversations" section.
3. Commands that produce artifact comparisons (Compare, Diff) can optionally save the comparison as a new artifact.
4. Commands that search across artifacts (Search, Review) display results as artifact cards with clickable links.

---

## Discovery

### How Users Discover Commands

| Discovery Method | Behavior | User Experience |
|---|---|---|
| **Natural language** | Type what you want in plain English | "show me critical findings" resolves to the Show Findings command with severity filter |
| **Autocomplete** | Suggestions appear as you type | Type "sh" → "Show Findings", "Show Config", "Show Health" |
| **Category browsing** | Browse commands by category | Type "?" or click "Browse commands" to see categories |
| **Recent commands** | Previously used commands appear first | Top section: "Recent" with last 5 commands |
| **Favorites** | User can favorite commands | "Favorites" section with pinned commands |
| **Related commands** | Context-dependent suggestions | "After comparing experiments: Related: Diff config, Create recommendation" |
| **Contextual recommendations** | Palette suggests commands based on current screen | "Working in Findings: Common commands: Explain, Search, Compare" |
| **Learning mode** | Guided command exploration | "Show me what I can do here" → contextual command tour |
| **Keyboard shortcut hints** | Shortcuts shown next to commands | "Show Findings (⌘⇧F)" |
| **Help command** | Explicit help | "help" or "?" shows command reference |

### Discovery Rules

1. The command palette always opens with the input field focused and suggestions visible.
2. Empty state shows: recent commands, favorites, and a "Browse all commands" link.
3. Users can search commands by keyword, category, or artifact type.
4. The palette shows shortcuts for frequently used commands.
5. New commands (introduced in platform updates) are highlighted with a "New" badge for the first 7 days.

---

## Safety Model

### Command Safety Levels

| Safety Level | Behavior | Examples |
|---|---|---|
| **Immediate** | Executes without confirmation. Read-only, no side effects. | Navigate, Search, Explain, Investigate, Compare, Evaluate (read), Learn, Help, Review, Summarize, Teach |
| **Preview** | Shows what will happen. User confirms before execution. | Generate, Report, Plan |
| **Confirm** | User must explicitly confirm. Preview is shown. | Automate, Experiment (launch), Configure (write) |
| **Multi-step confirm** | Multiple distinct confirmations required. | Configure (production), Delete, Rollback |
| **Role-gated** | Requires specific user role. Approval may be from a different user. | Production config apply, Governance policy modification |
| **Emergency override** | Available only to authorized users. Requires post-action audit. | Incident response, Emergency rollback |

### Safety Rules

1. Safety level is determined by the command category and specific action, never by the UI context.
2. Commands with Preview or higher safety levels show a safety indicator in the palette: a shield icon with the safety level.
3. The safety level is communicated to the user before execution: "This command requires approval."
4. Users can cancel any command at any point before execution completes.
5. Commands that require approval show the approval history in the command result.

### Commands That Should Be Disabled

Commands are disabled (with explanation) when:

- The user lacks the required role or permissions
- The required tool or capability is unavailable
- The required artifact does not exist or is inaccessible
- The current context does not support the command (e.g., "Compare" with only one experiment)

Disabled commands show a tooltip explaining why: "Requires Experimenter role" or "No experiments available to compare."

---

## Cross-Experience Behavior

### Consistency Rules

The command system behaves identically regardless of where it is invoked:

| Invocation Point | Behavior |
|---|---|
| **Assistant** | Commands typed in the assistant input go through the full command lifecycle. The assistant augments results with conversation context. |
| **Dashboard** | Command palette (⌘K) works exactly as in any other screen. Context is the dashboard time window and filters. |
| **Findings List** | Command palette works as normal. Context includes the current findings list filters. |
| **Finding Detail** | Commands that accept an artifact default to the current finding. "Explain" explains this finding. |
| **Experiments** | Commands default to the current experiment when applicable. "Compare" selects the current experiment as the first item. |
| **Configuration** | Commands default to the current or most recently viewed snapshot. "Diff" selects current snapshot. |
| **Search** | Command palette opens from search. Search results are preserved when command runs. |
| **Notifications** | Notification actions execute commands with the notification's artifact as context. |
| **Timeline / Activity** | Commands default to the selected timeline item. |
| **Artifact Detail** | Commands default to the viewed artifact. "Share", "Explain", "Compare" all operate on this artifact. |

### Cross-Experience Invariance

1. The same keyboard shortcut (⌘K) opens the command palette from every screen.
2. The same command produces the same result regardless of how it was invoked (palette, assistant, context menu, notification).
3. The same safety level applies to the same command regardless of invocation point.
4. The same artifact integration rules apply regardless of where the command was invoked.
5. The same conversation recording behavior applies regardless of invocation point.

---

## AI Responsibilities

### The Assistant SHOULD

| Responsibility | Behavior |
|---|---|
| **Interpret intent** | Translate natural language into resolved commands with high accuracy. |
| **Suggest commands** | Proactively suggest relevant commands based on context. "You might want to: Compare experiments, Review findings." |
| **Chain commands** | Execute multi-command workflows where one command's output feeds into the next. |
| **Explain commands** | When a user asks about a command, explain what it does, what safety level it has, and what it produces. |
| **Recover from failures** | When a command fails, offer alternatives, retry options, or workarounds. |
| **Teach users** | When a user types something that could be a command but is not recognized, suggest the closest matching command. |
| **Resolve ambiguity** | When intent is unclear, ask clarifying questions with options. |
| **Confirm before mutation** | Before any command that creates, modifies, or deletes state, confirm with the user. |
| **Show previews** | For commands that require preview, generate and display the preview before proceeding. |
| **Record in conversation** | Ensure every command and its results are recorded in the conversation history. |
| **Surface evidence** | For commands that produce conclusions, surface the supporting evidence. |

### The Assistant MUST NOT

| Prohibition | Example Violation |
|---|---|
| **Execute dangerous commands silently** | Running "Delete experiment" without the user knowing. |
| **Invent command results** | Reporting a command succeeded when it failed. |
| **Hide command failures** | A command fails silently and the assistant continues as if nothing happened. |
| **Ignore user confirmation** | Executing a command that requires approval without waiting for it. |
| **Skip preview** | Generating an artifact without showing the user what will be created. |
| **Assume destructive intent** | Interpreting ambiguous input as a delete or modification command. |
| **Mutate without lineage** | Changing configuration without recording the change as an artifact. |
| **Bypass safety levels** | Executing a "Confirm" command without confirmation because it was invoked from the assistant. |
| **Confuse commands and conversation** | Treating every user message as a command. The assistant distinguishes between "chat" and "command" intent. |
| **Override user context** | Ignoring the user's current context and executing a command in the wrong scope. |

---

## Anti-Patterns

### Forbidden Command System Behaviors

1. **Feature-specific commands.** Commands that only work in one module. All commands work everywhere. Context adapts the behavior, but the command is always available.

2. **Hidden commands.** Commands that exist but are not discoverable through the palette, autocomplete, or help. Every command is discoverable.

3. **Inconsistent syntax.** "Show findings" in one context but "display findings" in another. The command system normalizes synonyms to canonical commands.

4. **Navigation-first thinking.** Commands that default to navigating to a page rather than producing inline results. Navigation is offered as an option, not the default.

5. **Silent execution.** Commands that execute without any user-visible feedback. Every command produces a visible result.

6. **Dead-end commands.** Commands that produce results but offer no follow-up actions. Every command suggests next steps.

7. **Context loss.** Executing a command that navigates away from the user's current context without preserving it.

8. **Duplicate command paths.** Multiple ways to do the same thing that behave differently. "Create recommendation from finding" should work the same whether initiated from the palette, the assistant, or the finding detail page.

9. **No escape.** Commands that cannot be cancelled once started. Every command is cancellable.

10. **Over-suggestion.** The palette suggests too many commands, overwhelming the user. Suggestions are ranked by relevance, limited to 5-7 items.

11. **Silent context switching.** The command resolves to a different context than the user expected without explanation. Context changes are communicated.

12. **Command overload.** Every possible action is available as a command, including trivial ones. Commands represent meaningful intents, not every possible API call.

13. **No feedback loop.** The user executes a command and receives no indication of whether it succeeded or failed.

14. **Inconsistent safety.** The same command sometimes requires approval and sometimes does not, depending on where it is invoked.

15. **Relying on the assistant for everything.** The command palette works independently of the assistant. Users who prefer keyboard navigation should not be forced into conversation.

16. **Ignoring permissions.** Commands that the user cannot execute are shown but disabled (with explanation). They are not hidden.

17. **No command memory.** The palette does not remember recently used commands, requiring the user to rediscover them each session.

18. **Text-only commands.** Commands that can only be typed. The palette supports selection, clicking, and keyboard navigation through results.

19. **One-shot only.** Commands that execute and disappear without recording in history. Every command is recorded.

20. **Platform-only commands.** Commands that only work within the platform but not in the assistant. The assistant and palette share the same command system.

---

## Future Evolution

### Voice Commands

As voice interfaces mature:

1. Commands can be spoken: "Show critical findings" spoken triggers the same command as typed.
2. Voice commands go through the same intent detection pipeline.
3. Clarification for voice commands uses natural language rather than option lists.
4. Voice commands for destructive actions require explicit typed confirmation.
5. Voice is treated as an input modality, not a separate command system.

### Multi-Agent Command Planning

As multiple AI agents become available:

1. Complex commands can be planned and delegated to specialized agents.
2. The command system shows which agent will execute which part: "Agent: Evidence Engine will retrieve findings. Agent: Analytics will compute trends."
3. Users can direct commands to specific agents: "Ask the Experimentation Agent to design an experiment."
4. Multi-agent command results are merged into a unified response.

### Collaborative Commands

As teams collaborate:

1. Commands can be executed in shared conversations visible to all participants.
2. Command results are shared with the conversation participants.
3. Commands that require approval can be approved by any authorized participant.
4. Command execution shows who initiated it: "Priya ran: Compare Experiments AB-47 and AB-48."

### Background Execution

Commands that take time can run in the background:

1. Users can invoke a command and choose "Run in background."
2. Background commands notify the user on completion.
3. Background commands are visible in a "Running commands" section of the palette.
4. Users can check the status of background commands at any time.

### Scheduled Commands

Commands can be scheduled:

1. "Run this report every Monday at 9 AM."
2. Scheduled commands appear in the Automation module.
3. Scheduled command results are delivered to the user's notification feed.
4. Users can pause, modify, or cancel scheduled commands.

### Natural Language Workflows

Full workflows expressed as natural language:

1. "Every morning at 8 AM, check last night's evaluation, summarize critical findings, and notify me."
2. The command system parses the workflow, creates the automation schedule, and links it to the appropriate tools.
3. Natural language workflows are translatable to command sequences.
4. Users can review and modify the generated workflow before activation.

### Predictive Command Suggestions

The system anticipates commands before the user types:

1. Based on context, time of day, and user patterns, the palette pre-populates likely commands.
2. Predictive suggestions are shown below the input field as the palette opens.
3. Users can accept, modify, or ignore predictive suggestions.
4. The system learns from user behavior to improve predictions over time.

### Engineering Copilots

The command system becomes the interface for an AI engineering copilot:

1. "Analyze this finding and suggest next steps."
2. "Create an investigation plan and execute it."
3. "Monitor this experiment and alert me when results are ready."
4. "Review my pending approvals and recommend which to prioritize."
5. The copilot uses the command system as its action interface — any action the copilot can take is available as a command the user could have typed.
