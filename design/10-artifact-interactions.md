# Artifact Interaction Architecture

> Artifacts are the primary units of engineering knowledge.
>
> Every engineering activity creates, references, compares, or consumes artifacts.
>
> This document defines HOW USERS INTERACT WITH ARTIFACTS — a universal interaction model that applies to every artifact type in the platform.

---

## Purpose

### Why Artifacts Are First-Class Objects

In most platforms, records exist in a database and are surfaced through screens designed specifically for that record type. A finding has a finding page. An experiment has an experiment page. Each page has its own navigation, actions, and layout. Users must learn each page individually.

This platform rejects that model. Artifacts are not "records in a database" — they are **living engineering objects** with consistent behavior regardless of type. A finding, an experiment, a decision, and a capability should all support the same fundamental interactions: inspect, compare, reference, explain, share, trace lineage.

### How This Differs from Traditional CRUD

| Traditional CRUD | Artifact Interaction Model |
|---|---|
| Each type has its own page with unique behavior | All artifacts share a universal interaction model |
| Relationships are implicit in database foreign keys | Relationships are explicit, navigable, and visual |
| Lineage is reconstructed from query logs | Lineage is a first-class property of every artifact |
| History is tracked in audit tables | History is visible, navigable, and comparable |
| Users navigate between pages | Users navigate between artifacts regardless of type |
| Conversations and artifacts are separate | Conversations and artifacts are deeply linked |

### Why Engineering Knowledge Revolves Around Artifacts

An engineer's understanding of the platform is built from artifacts: findings reveal behavior, evidence explains causes, recommendations propose changes, experiments validate hypotheses, decisions record choices, configurations encode state. Each artifact type captures a specific kind of engineering knowledge, and together they form a connected knowledge graph.

The platform's job is to make this knowledge graph navigable, explainable, and actionable — regardless of which artifact type the user starts from.

---

## Universal Artifact Model

Every artifact, regardless of type, supports the following interaction dimensions. These are not database fields — they are interaction expectations.

| Dimension | Description | User Expectation |
|---|---|---|
| **Identity** | Every artifact has a unique, stable identifier. | Users can reference, share, and search by ID. IDs are human-recognizable (Finding #1024, Exp AB-47). |
| **Type** | Every artifact has a type that determines its role in the platform. | Users can identify the type at a glance. Type determines available actions. |
| **Status** | Every artifact has a current status within its lifecycle. | Users can see status immediately and understand what it means. |
| **Owner** | Every artifact has a creator or responsible party. | Users can see who created it and contact them. |
| **Creation context** | Every artifact knows how it was created (manual, automated, AI-generated, derived from another artifact). | Users can understand the artifact's origin and trust implications. |
| **Conversation references** | Every artifact tracks which conversations reference it. | Users can see the engineering discussion that produced or used this artifact. |
| **Evidence** | Every artifact that makes a claim can reference supporting evidence. | Users can verify any claim by inspecting its evidence. |
| **Lineage** | Every artifact knows its parents (what created it) and children (what depends on it). | Users can navigate forward and backward through the artifact graph. |
| **Relationships** | Every artifact can be related to other artifacts beyond lineage (references, dependencies, alternatives). | Users can discover related artifacts that may be relevant. |
| **History** | Every artifact tracks its state changes over time. | Users can see what changed, when, and by whom. |
| **Approvals** | Every artifact that requires authorization records its approval chain. | Users can see who approved what and when. |
| **Confidence** | Every AI-generated or AI-synthesized artifact carries a confidence score. | Users can assess reliability before acting on the artifact. |
| **Tags** | Every artifact supports user-defined tags for organization. | Users can categorize, filter, and find artifacts by tag. |
| **Permissions** | Every artifact has access controls. | Users can see what they can do with an artifact (view, edit, approve, delete). |
| **Metadata** | Every artifact has creation and modification timestamps. | Users can assess freshness and recency. |

---

## Artifact Lifecycle

### Universal Lifecycle

Not every artifact type passes through every stage, but every artifact follows the same lifecycle concept:

```
CREATED
  │
  ▼
OBSERVED ─────► REVIEWED ─────► VALIDATED ─────► ACTED ─────► COMPLETED
  │                                                    │
  │              ┌──────────────┐                       │
  │              │  REFERENCED  │ ◄─────────────────────┘
  │              │  (recurring) │
  │              └──────────────┘
  │
  ▼
COMPARED (may occur at any point after OBSERVED)
  │
  ▼
UPDATED / REVISED (may occur at any point before COMPLETED)
  │
  ▼
ARCHIVED ─────► RESTORED ─────► DEPRECATED
```

### Stage Descriptions

| Stage | Description | User Interaction |
|---|---|---|
| **Created** | The artifact is generated. May be manual, automated, or AI-generated. | User sees the new artifact in context (conversation, dashboard, notification). |
| **Observed** | The artifact has been seen by a user. Not necessarily reviewed — just acknowledged as existing. | Artifact appears in attention queue. User may scan it without deep inspection. |
| **Reviewed** | A user has examined the artifact's content and evidence. | User has opened the artifact and inspected its detail. Status changes from "new" to "reviewed." |
| **Validated** | The artifact's claims have been verified against evidence. | User (or AI) has confirmed the artifact's assertions. Validation is recorded. |
| **Acted** | A decision has been made based on this artifact. | User has taken action: acknowledged, dismissed, approved, rejected, escalated. |
| **Completed** | The artifact's purpose has been fulfilled. No further action is expected. | Artifact reaches terminal state for its type. |
| **Referenced** | The artifact has been cited by another artifact or conversation. | Cross-references are recorded. User can see where this artifact is used. |
| **Compared** | The artifact has been compared with another artifact of the same type. | Comparison results are recorded. User can revisit comparisons. |
| **Updated / Revised** | The artifact's content has changed after creation. | Previous version is preserved. Diff is available. |
| **Archived** | The artifact is no longer actively relevant but is preserved for history. | Artifact is removed from active views. Still searchable. |
| **Restored** | An archived artifact has been brought back to active status. | Artifact reappears in active views. Restoration is recorded in history. |
| **Deprecated** | The artifact is superseded and should not be used for new decisions. | Artifact is clearly marked as deprecated. Active references are flagged. |

### Lifecycle Rules

1. Artifacts cannot skip from Created to Archived without passing through at least Observed.
2. Comparisons are non-destructive. Comparing two artifacts does not change either artifact's state.
3. Updates always create a new version. Previous versions remain accessible.
4. Archival is reversible. Deprecation is permanent (but the artifact remains accessible).
5. Lifecycle transitions are recorded as history entries with timestamps and actors.

---

## Universal Artifact Actions

The following actions should behave consistently across all artifact types. The presentation may vary by context, but the behavior is universal.

### Navigation Actions

| Action | Behavior | Applicable Types |
|---|---|---|
| **Open** | Navigate to the artifact's detail view. | All |
| **Open in Console** | Open the artifact in the Operations Console detail screen. | All |
| **Open in Conversation** | Open the conversation where this artifact was created or referenced. | All |
| **Open Related** | Navigate to a related artifact (determined by relationship type). | All |
| **Previous / Next** | Navigate to the previous or next artifact in the current list context. | All (when viewed in a list) |
| **Back to List** | Return to the list from which this artifact was opened. | All |

### Inspection Actions

| Action | Behavior | Applicable Types |
|---|---|---|
| **Inspect** | Show the artifact's full detail view. | All |
| **Summarize** | Generate or show a concise summary of the artifact. | All |
| **Explain** | AI explains the artifact's meaning, evidence, and context. | All |
| **Show Lineage** | Display the artifact's lineage graph (parents and children). | All |
| **Show History** | Display the artifact's version history. | All |
| **Show Evidence** | Display the evidence supporting this artifact's claims. | Findings, Recommendations, Experiments |
| **Show Raw** | Display the artifact's raw payload. | All (power user feature) |

### Organization Actions

| Action | Behavior | Applicable Types |
|---|---|---|
| **Pin** | Pin the artifact to the current conversation. | All |
| **Bookmark** | Save the artifact to the user's bookmarks. | All |
| **Tag** | Add or remove user-defined tags. | All |
| **Watch / Subscribe** | Subscribe to notifications for changes to this artifact. | All |
| **Favorite** | Mark the artifact as a favorite for quick access. | All |

### Sharing Actions

| Action | Behavior | Applicable Types |
|---|---|---|
| **Share** | Generate a shareable link to the artifact. | All |
| **Copy Link** | Copy the artifact's URL to the clipboard. | All |
| **Copy ID** | Copy the artifact's ID to the clipboard. | All |
| **Export** | Export the artifact in a structured format (JSON, Markdown). | All |
| **Duplicate** | Create a copy of the artifact (with lineage to the original). | Experiments, Config Snapshots |

### Analytical Actions

| Action | Behavior | Applicable Types |
|---|---|---|
| **Compare** | Compare this artifact with another of the same type. | Experiments, Config Snapshots, Findings, Health Snapshots |
| **Diff** | Show the difference between this artifact and another version. | Config Snapshots, Recommendations |
| **Trace** | Follow the artifact's lineage backward to root causes or forward to impacts. | All |
| **Trend** | Show how this artifact's metrics have changed over time. | Findings, Health Snapshots, Evaluation Results |
| **Generate Report** | Create a report based on this artifact and its related artifacts. | All |

### Action Actions

| Action | Behavior | Applicable Types |
|---|---|---|
| **Acknowledge** | Mark the artifact as seen. | Findings, Recommendations |
| **Dismiss** | Mark the artifact as not actionable. | Findings |
| **Approve** | Approve the artifact for next steps. | Recommendations, Config Snapshots, Decisions |
| **Reject** | Reject the artifact with a reason. | Recommendations, Config Snapshots |
| **Escalate** | Create a follow-up artifact (finding → recommendation, recommendation → experiment). | Findings, Recommendations |
| **Comment** | Add a human-readable comment to the artifact. | All |
| **Assign** | Assign the artifact to a user for action. | Findings, Recommendations |
| **Delete** | Delete the artifact (with confirmation and lineage preservation). | All (subject to permissions) |

### AI Actions

| Action | Behavior | Applicable Types |
|---|---|---|
| **Explain** | AI generates a natural language explanation of the artifact. | All |
| **Summarize** | AI generates a concise summary. | All |
| **Analyze** | AI performs deeper analysis on the artifact's data. | Findings, Experiments, Health Snapshots |
| **Suggest Related** | AI suggests related artifacts the user might want to see. | All |
| **Draft Follow-up** | AI drafts a follow-up artifact (recommendation from finding, experiment from recommendation). | Findings, Recommendations |
| **Answer Questions** | User can ask questions about the artifact and the AI answers with evidence. | All |

### Action Consistency Rules

1. Every action that is applicable to an artifact type must behave the same way regardless of where the user triggers it (conversation, list, detail page, side panel, command palette).
2. Actions that are not applicable to a type are hidden (not disabled).
3. The names and icons for actions are consistent across the platform. "Compare" always means the same thing and uses the same icon.
4. Actions that produce a new artifact (escalate, duplicate, draft follow-up) always establish lineage to the source artifact.

---

## Artifact Relationships

### Relationship Types

Artifacts exist in a connected graph. The platform makes these relationships navigable.

```
RELATIONSHIP TYPE        MEANING                                    EXAMPLE
────────────────────     ──────────────────────────────────────     ─────────────────────
PARENT                   The source that created this artifact      Evidence → Finding
CHILD                    An artifact created from this one           Finding → Recommendation
DERIVED FROM             This artifact was derived from another      Recommendation → Experiment
SUPERSEDES               This artifact replaces another              New config snapshot supersedes old
SUPERSEDED BY            This artifact was replaced                  Old config snapshot superseded by new
REFERENCES               This artifact references another            Conversation references Finding
REFERENCED BY            Another artifact references this            Finding referenced by Conversation
SUPPORTS                 This artifact supports another              Evidence supports Finding
CONTRADICTS              This artifact contradicts another           Conflicting evidence
Depends On               This artifact depends on another            Experiment depends on Config Snapshot
DEPENDENT                Another artifact depends on this            Config Snapshot depended on by Experiment
RELATED                  General association (AI-suggested)          Finding related to Experiment
CONVERSATION             The conversation where this was discussed   All artifacts
```

### Relationship Graph Example

```
Learning Record
    │
    ▼
Evidence ───► Finding ───► Recommendation ───► Experiment ───► Decision ───► Config Snapshot
    │                       │                       │               │
    │                       └── Conversation 1       │               └── Conversation 2
    │                                               │
    ▼                                               ▼
Analytics Report                             Automation Run
    │                                               │
    ▼                                               ▼
Health Snapshot ◄────────────────────────────── Evaluation Result
```

### Relationship Navigation

1. Every artifact detail view shows its relationships in a relationship panel.
2. Relationships are grouped by type (parents, children, references, related).
3. Each relationship shows the artifact type, ID, title, and status.
4. Clicking a relationship navigates to that artifact.
5. The relationship graph is interactive — users can expand, collapse, and pan.

---

## Lineage Philosophy

### What Lineage Must Answer

For any artifact, the user should always be able to answer:

| Question | Example |
|---|---|
| Where did this come from? | "This recommendation was generated from Finding #1024." |
| What created it? | "It was created by the Recommendation Engine on March 24 at 02:00 UTC." |
| What evidence supports it? | "It is supported by Evidence #512, #513, and #514." |
| What depends on it? | "Experiment AB-48 was designed based on this recommendation." |
| What conversations referenced it? | "This was discussed in 3 conversations." |
| What decisions used it? | "Decision #89 approved the config change derived from this." |
| What changed over time? | "This finding was updated twice. Version history shows the changes." |

### Lineage Experience

Lineage is not a database query — it is a first-class visual experience.

1. **Lineage is always accessible.** Every artifact has a "Show lineage" action. Lineage is one click away from any artifact view.

2. **Lineage is directional.** Users can trace "upstream" (what created this) and "downstream" (what depends on this). The direction is always clear.

3. **Lineage is interactive.** Users can click any node in the lineage graph to navigate to that artifact. The graph expands, collapses, and re-centers on selection.

4. **Lineage is contextual.** The lineage view defaults to the immediate parents and children. Users can expand to show more distant ancestors and descendants.

5. **Lineage is filtered.** Users can filter the lineage view by relationship type, artifact type, time range, or status.

6. **Lineage is time-aware.** If an artifact was superseded, the lineage shows both the old and new versions, with the supersession relationship clearly marked.

### Lineage Rules

1. All artifacts must have lineage. Orphan artifacts (no parents) are permitted only for manually created artifacts.
2. Lineage is immutable. Once established, a lineage relationship cannot be broken.
3. Lineage relationships are typed. "Parent" and "referenced by" are different relationships.
4. Lineage is cross-type. A finding's lineage may include evidence, analytics reports, conversations, and recommendations.
5. Lineage export is available. Users can export the lineage graph as a structured format (JSON, DOT, Mermaid).

---

## Comparison Model

### Comparison Principles

1. **Compare is universal.** Any artifact type that can have multiple instances supports comparison.
2. **Compare is side-by-side.** Comparisons are always presented in a side-by-side layout showing both artifacts simultaneously.
3. **Compare highlights differences.** The comparison view highlights what changed, what stayed the same, and what is unique to each artifact.
4. **Compare is structured.** Comparison results are organized by the artifact's structure (metadata, metrics, evidence, lineage).
5. **Compare is recordable.** Comparison results can be saved as a new artifact with lineage to both compared artifacts.

### Comparison Examples

| Artifact Type | Comparison View |
|---|---|
| **Experiments** | Side-by-side metric table (baseline vs candidate), metric charts overlaid, statistical significance indicators, variant configuration diff |
| **Config Snapshots** | Side-by-side or unified diff view, key-by-key comparison, rollback path comparison |
| **Findings** | Side-by-side evidence timeline, metric comparison, severity changes, scope changes |
| **Health Snapshots** | Overlay health scores, per-capability status changes, trend comparison |
| **Recommendations** | Side-by-side proposal, evidence comparison, confidence comparison, risk comparison |

### Comparison Rules

1. The first artifact in a comparison is always the "reference" — the baseline.
2. Differences are ordered by significance (most impactful change first).
3. Statistical significance is displayed for metric comparisons.
4. Users can switch between side-by-side and unified views.
5. Comparisons are shareable via a unique URL.

---

## Artifact Navigation

### Movement Patterns

Users move between artifacts through multiple paths:

| Path | Initiated By | Behavior |
|---|---|---|
| **Relationship navigation** | User clicks a relationship link | Opens the related artifact, replacing or adding to the current context |
| **Lineage navigation** | User clicks a node in the lineage graph | Opens the selected artifact |
| **Suggested artifacts** | AI suggests related artifacts | User clicks a suggestion to navigate |
| **Conversation references** | User clicks an artifact reference in a conversation | Opens the artifact (side panel or full page, depending on context) |
| **Search results** | User selects a search result | Opens the artifact |
| **List navigation** | User clicks an item in a list | Opens the artifact detail |
| **Previous / Next** | User clicks previous/next in a list context | Navigates through the list without returning to the list |
| **Breadcrumb** | User clicks a breadcrumb segment | Navigates up the hierarchy |
| **Deep link** | User opens a shared URL | Opens the artifact directly |

### Navigation State

When navigating between artifacts:

1. **Context is preserved.** The previous artifact's state (scroll position, expanded sections) is cached.
2. **Navigation history is maintained.** Back navigates through the artifact navigation stack, not just the URL history.
3. **Side panel navigation stays in context.** Opening an artifact in a side panel from a conversation does not navigate away from the conversation.
4. **Full page navigation is for focus.** Opening an artifact in a full page is an explicit "I want to focus on this" action.

### Breadcrumb Strategy

Artifact breadcrumbs follow this pattern:

```
[Source Context] > [Artifact Type] > [Artifact Title]

Examples:
Conversation: Health Investigation > Finding #1024 > Evidence #512
Dashboard > Experiments > Experiment AB-47
```

---

## Evidence Integration

### How Evidence Attaches to Artifacts

Evidence is not a separate page — it is a property of any artifact that makes claims.

| Evidence Aspect | Description | User Experience |
|---|---|---|
| **Evidence visibility** | Evidence is always accessible but never required to be visible. | Collapsed by default. One click to expand. |
| **Confidence** | AI-generated artifacts include a confidence score. | Badge or indicator showing 0-100%. |
| **Supporting evidence** | Evidence that supports the artifact's claims. | Listed with source links, timestamps, and summaries. |
| **Contradicting evidence** | Evidence that conflicts with the artifact's claims. | Shown alongside supporting evidence with a "contradiction" indicator. |
| **Missing evidence** | Expected evidence that was not found. | The AI explicitly states when expected evidence is missing. |
| **Evidence freshness** | How recent the evidence is. | Timestamp with relative indicator ("2 hours ago"). |
| **Evidence quality** | Quality assessment of the evidence source. | Quality indicator (high, medium, low) based on source reliability. |

### Evidence Display

1. Evidence is rendered as cards within the artifact detail view.
2. Each evidence card shows: source type, source ID, timestamp, summary, confidence, and a clickable link to the source.
3. Evidence cards are sorted by relevance (most directly supporting first).
4. Contradicting evidence is visually distinct (different color, icon).
5. Users can filter evidence by type, time range, or quality.

### Evidence Rules

1. Every claim in an AI-generated artifact must cite at least one piece of evidence.
2. Evidence citations that no longer exist (deleted or expired evidence) are flagged as "stale."
3. Users can manually add evidence to any artifact.
4. Evidence cannot be removed from an artifact — only superseded by newer evidence.

---

## Collaboration

### Collaborative Interactions

| Interaction | Description | Applies To |
|---|---|---|
| **Comments** | Human-readable notes attached to an artifact. Threaded replies supported. | All |
| **Reviews** | Formal review request with required approvers. | Recommendations, Config Snapshots, Experiments |
| **Approvals** | Explicit sign-off on an action. | Decisions, Config Snapshots |
| **Assignments** | Assigning an artifact to a specific user for action. | Findings, Recommendations |
| **Mentions** | @-mentioning a user in comments or artifact descriptions. | All |
| **Subscriptions** | Users subscribe to artifact changes. Notifications on updates. | All |
| **Watchers** | Explicit list of users monitoring an artifact. Visible to all. | All |
| **Shared investigations** | Conversations that multiple users participate in. | Conversations (see 09-conversation-lifecycle.md) |
| **Bookmarks** | User-specific saved references. | All |

### Collaboration Rules

1. All collaborative interactions are recorded in the artifact's history.
2. Comments are not editable after 5 minutes (to preserve audit integrity).
3. Approvals are irrevocable by the approver (but can be overridden by a higher authority with audit trail).
4. Assignment notifications include the artifact summary and context.
5. Users can see who else is watching or subscribed to an artifact.

---

## Search & Discovery

### Discovery Dimensions

| Dimension | Method | Example |
|---|---|---|
| **Natural language** | Ask the assistant | "Show me findings from last night" |
| **Structured filters** | Filter panels in list views | Type: Finding, Status: Critical, Time: Last 24h |
| **Tags** | Filter by user-defined tags | tag:incident |
| **Relationships** | Navigate related artifacts | Finding → Evidence → Analytics Report |
| **Timeline** | Browse by time | All artifacts from last week |
| **Capability** | Filter by capability | capability:evidence-engine |
| **Health** | Filter by health impact | Severity: Critical |
| **Owner** | Filter by creator | created-by:@priya |
| **Conversation** | Find artifacts referenced in a conversation | conversation:id:abc123 |
| **Similarity** | AI-suggested similar artifacts | "Show me similar findings" |
| **Recent** | Browse recently viewed | Recent artifacts list |
| **Favorites** | Browse bookmarked | Favorites list |
| **Saved searches** | Reusable search configurations | Saved: "Critical findings - last 24h" |

### Search Behavior

1. Search spans all artifact types. Results are grouped by type.
2. Search results show: artifact type icon, ID, title, status, timestamp, summary preview.
3. Users can filter search results by type, status, time, capability, and owner.
4. Search respects permissions. Users only see artifacts they have access to.
5. Natural language search (via assistant) interprets intent and retrieves relevant artifacts before the user finishes typing.

---

## Notifications

### Notification Triggers

| Event | Notification Type | Applies To |
|---|---|---|
| **Created** | New artifact alert | Findings (critical only), Recommendations |
| **Updated** | Artifact content changed | All (subscribed/watching) |
| **Approved** | Approval granted | Decisions, Config Snapshots |
| **Rejected** | Approval denied | Recommendations, Config Snapshots |
| **Referenced** | Another artifact references this one | All |
| **Compared** | Artifact was used in a comparison | Experiments, Config Snapshots |
| **Linked to conversation** | Artifact was attached to a conversation | All |
| **Archived** | Artifact was archived | All (watching) |
| **Mentioned** | User was @-mentioned | All |
| **Assigned** | Artifact assigned to user | Findings, Recommendations |
| **Superseded** | New version supersedes this one | Config Snapshots, Recommendations |
| **Status changed** | Artifact lifecycle transition | All (subscribed/watching) |

### Notification Rules

1. Users receive notifications for artifacts they created, subscribed to, or were mentioned in.
2. Notification frequency: critical findings are immediate. Other notifications are batched (configurable: immediately, hourly, daily).
3. Notifications include artifact type, ID, title, summary, and a direct link.
4. Notifications in the platform are mirrored to the user's configured external channel (email, Slack) if enabled.

---

## AI Interaction

### How the Assistant Interacts with Artifacts

| AI Action | Behavior | Example |
|---|---|---|
| **Explain** | AI generates a natural language explanation of the artifact, its evidence, and its significance. | "Finding #1024 shows that retrieval accuracy dropped from 92% to 87% between 02:00 and 03:00 UTC. The evidence points to a configuration change..." |
| **Summarize** | AI generates a concise 1-2 sentence summary. | "Finding #1024: Retrieval accuracy degraded by 5% following config change v141." |
| **Compare** | AI performs a structured comparison between two artifacts. | Side-by-side table with metrics, differences highlighted, statistical significance. |
| **Navigate** | AI provides a clickable link to the artifact. | "Let me take you there: [Finding #1024]" |
| **Generate** | AI creates a new artifact based on context (recommendation from finding, experiment from recommendation). | "Based on this finding, I've drafted a recommendation. Would you like to review it?" |
| **Recommend** | AI suggests actions on the artifact. | "I recommend acknowledging this finding and creating a recommendation to investigate further." |
| **Review** | AI reviews the artifact and provides assessment. | "This finding appears to be a true positive. Confidence: 87%. The supporting evidence is strong." |
| **Teach** | AI explains what the artifact type means and how it fits in the platform. | "A finding represents an observed deviation from expected behavior. It is generated by the Evidence Engine..." |
| **Trace lineage** | AI follows the artifact's lineage and reports the chain. | "This recommendation traces back to Finding #1024, which was generated from Evidence #512, which was derived from..." |
| **Surface related** | AI suggests related artifacts the user may want to examine. | "You might also want to look at these related findings..." |
| **Answer questions** | User asks questions about the artifact; AI answers with evidence. | "User: What caused this finding? AI: The primary cause appears to be..." |

### AI Interaction Rules

1. The AI never fabricates artifact state. If an artifact does not exist, the AI does not pretend it does.
2. The AI always cites specific artifact IDs when referencing platform data.
3. AI-generated explanations include confidence scores and evidence sources.
4. The AI can suggest actions on artifacts (approve, dismiss, escalate) but never executes them without user confirmation.
5. AI-generated artifacts (recommendations, experiment drafts) are clearly labeled as AI-generated.

---

## Anti-Patterns

### Forbidden Artifact Interaction Behaviors

1. **Hidden lineage.** Artifacts that do not show their parents or children. Users should never encounter an artifact and wonder where it came from.

2. **Dead-end artifacts.** Artifacts that have no navigable relationships or references. Every artifact should connect to something else.

3. **Unexplained relationships.** Artifacts that are related but the nature of the relationship is unclear. All relationship types must be labeled and explained.

4. **Orphan artifacts.** Artifacts created without establishing lineage to their parent. Manual creation requires explicit parent specification.

5. **Hidden history.** Artifacts that change without any visible version history or diff. Every change is tracked and accessible.

6. **No comparison.** Artifacts that cannot be compared with other instances of the same type. Every type supports comparison.

7. **Broken references.** Links to artifacts that no longer exist or are inaccessible. References are validated and broken links are flagged.

8. **Lost conversation links.** Artifacts discussed in conversations without any record of the discussion. Artifact detail views must show conversation references.

9. **Inconsistent actions.** The same action behaving differently for different artifact types. Compare, Explain, Share, Pin, and Lineage must work identically across all types.

10. **Type-specific navigation patterns.** Users should not need to learn different navigation rules for findings vs experiments vs decisions.

11. **Silent supersession.** An artifact being superseded without notifying users who referenced or subscribed to the original.

12. **Context-less sharing.** Sharing an artifact link without preserving the context (conversation, investigation, filter state).

13. **Non-diffable updates.** Updates to artifacts that cannot be compared with the previous version. Every update produces a diff.

14. **Unsubscribe difficulty.** Making it hard for users to stop watching or subscribing to an artifact.

15. **Evidence hiding.** Presenting conclusions without showing the evidence that supports them.

16. **Relationship overload.** Showing every possible relationship without filtering by relevance. Relationship views should prioritize immediate lineage.

17. **Mutable evidence.** Allowing evidence to be modified after it has been cited by an artifact. Evidence is append-only.

18. **Conversation-orphaned artifacts.** Artifacts created during a conversation that do not link back to that conversation.

19. **Cross-user isolation.** Artifacts that are only visible to their creator when they should be visible to the team.

20. **No bulk operations.** Requiring users to perform the same action on multiple artifacts one at a time. Lists support batch actions.

---

## Future Evolution

### Knowledge Graphs

As the artifact graph grows, the platform evolves from a navigable graph to an explorable knowledge graph:

1. **Semantic relationships.** AI discovers and suggests relationships between artifacts that are not explicitly linked.
2. **Graph visualization.** The full artifact graph becomes explorable as an interactive network visualization.
3. **Community detection.** The platform identifies clusters of related artifacts and surfaces them as investigation topics.
4. **Pathfinding.** Users can ask "What is the path from this finding to this configuration change?" and the platform traces the full chain.

### Autonomous Agents

As agents become more capable:

1. **Agent-generated artifacts.** Agents create artifacts independently within bounded permissions.
2. **Agent review.** Agents can review artifacts and provide assessments before human review.
3. **Automated lineage.** Agents automatically establish lineage relationships that humans would miss.
4. **Proactive artifact surfacing.** Agents surface relevant artifacts before the user asks.

### Collaborative Engineering

As teams grow:

1. **Shared artifact spaces.** Teams have shared artifact collections with their own permissions.
2. **Cross-user investigations.** Multiple engineers collaborate on the same artifact investigation.
3. **Artifact reviews.** Formal review workflows with required approvers, due dates, and escalation.
4. **Artifact annotations.** Users can annotate artifacts with private or shared notes.

### Continuous Learning

As the platform matures:

1. **Artifact quality scoring.** The platform learns which artifact types and sources produce the most reliable conclusions.
2. **Predictive relationships.** The platform predicts likely relationships between new artifacts based on patterns from existing ones.
3. **Knowledge gaps.** The platform identifies areas where artifacts are missing or incomplete and suggests creation.
4. **Engineering memory.** The artifact graph becomes the organization's collective engineering memory, retaining context even as team members change.

### Cross-Project Intelligence

As the platform serves multiple projects:

1. **Cross-project artifact search.** Users can search across all projects they have access to.
2. **Shared patterns.** The platform identifies patterns that repeat across projects and suggests reusable solutions.
3. **Global lineage.** Artifacts in one project can reference artifacts in another project with explicit cross-project lineage.
4. **Federated knowledge.** Each project maintains its own artifact graph, but the platform provides unified search and cross-reference capabilities.
