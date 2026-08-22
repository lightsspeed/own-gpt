# Interaction Principles — Frontend Architecture Root

> This document defines HOW PEOPLE INTERACT WITH THE PLATFORM.
>
> Every screen, component, animation, AI response, workflow, and interaction must follow these principles.
>
> This document should remain valid even if the UI is completely redesigned in five years.

---

## Purpose

Interaction Architecture defines the rules governing how users and the platform exchange information, make decisions, and take action. It sits between Information Architecture (what exists) and Visual Design (how it looks).

| Layer | Answers |
|---|---|
| Information Architecture | What screens exist? What data belongs on each? |
| **Interaction Architecture** | **How do users navigate, inspect, decide, and act? When do we confirm? How do we reveal complexity?** |
| Visual Design | What colors, typography, spacing, and motion are used? |

Interaction Architecture is the frontend equivalent of backend architecture. Just as backend architecture defines service boundaries, data flow, and dependency rules, Interaction Architecture defines interaction boundaries, information flow, and behavioral rules.

---

## Core Philosophy

### Interaction over decoration
Every visual element must serve an interaction purpose. Decorative elements that do not inform, guide, or provide feedback are eliminated. If an element cannot justify its existence in terms of user behavior, it does not belong.

### Context over navigation
Users should not need to navigate to a new page to answer a simple question. Context should flow with the user. Side panels, inline expansions, and conversational responses should handle the majority of information needs. Full page navigation is reserved for deep work.

### Conversation over search
The default path to information is asking, not searching. The assistant should handle the first 80% of information needs. Search and browse are fallbacks for when the user does not know how to ask or wants to explore broadly.

### Evidence over assumptions
Every statement from the platform must be grounded in evidence. Assumptions, guesses, and probabilistic statements that cannot cite sources are forbidden. The platform never says "probably" without showing its work.

### Actions over dashboards
Dashboards exist to surface what needs action, not to display data. Every widget must drive a decision or a navigation. If a widget does not change behavior, it does not belong on a dashboard.

### Progressive disclosure
Information is revealed in layers. Summary first. Detail on request. Raw data on explicit demand. The platform never dumps full complexity on the user unless asked.

### Minimal cognitive load
Every screen should be scannable in under 10 seconds. Information is chunked, prioritized, and visually weighted by importance. Operators should not need to read to understand — they should be able to scan.

### Trust through transparency
Every platform output must be verifiable. Sources are cited. Confidence is communicated. Uncertainty is explicit. Trust is earned through repeated verification, not through persuasive design.

### Consistency over cleverness
Users should be able to predict how an unfamiliar screen behaves based on their experience with familiar ones. Novel interactions are only justified when they meaningfully reduce complexity. Familiar patterns are never sacrificed for visual novelty.

### Predictability over surprise
The platform should behave consistently across sessions. Navigation does not reorganize. Buttons do not move. Actions have consistent consequences. Surprise is reserved for critical alerts, never for layout or behavior.

### Human control over automation
Automation handles repetitive work. Humans make decisions. The assistant may recommend, draft, and propose — but every production change requires human approval. The platform never acts autonomously in a way that affects production behavior.

---

## Universal Interaction Principles

### Navigation & Context

1. **One primary action per screen.** Every screen has exactly one primary action. Secondary actions exist but are visually subordinate. If a screen has multiple primary actions, split it into multiple screens.

2. **Every page is reachable in three clicks.** Maximum navigation depth from the home screen to any detail screen is three clicks. Beyond that, the architecture needs restructuring.

3. **Never interrupt without value.** Modals, dialogs, and overlays are only justified when the user must make a decision or acknowledge critical information before proceeding. "Nice to know" information never uses interruption.

4. **Never hide critical information.** Warnings, errors, and security-relevant information are always visible without interaction. They cannot be in collapsed sections, tooltips, or hover states.

5. **Never remove user context.** Navigating to a detail screen preserves the list position, filters, and scroll state. Returning from detail restores the previous view exactly. Context is never discarded.

6. **Always preserve navigation history.** The back button and browser history always work correctly. Deep links are stable and shareable. State is encoded in the URL where appropriate (filters, selected item, view mode).

7. **State is preserved per session.** Scroll position, expanded sections, selected filters, and open panels persist across navigation within a session. On return to the platform, the last-used state is restored.

8. **Navigation never reorganizes.** The sidebar, top bar, and navigation structure remain stable within a session. Items do not appear, disappear, or reorder based on context. The only exception is badges and counts.

9. **Side panels are for context, not primary actions.** Side panels show supplementary information. Primary actions live on full pages or modals. A side panel never contains the primary action for a workflow.

10. **Every link is navigable.** All artifact references, user mentions, and module names in any content area are clickable links. Engineers should never need to copy-paste an ID to navigate somewhere.

### AI Interaction

11. **AI explains before recommending.** Before suggesting an action, the AI explains the situation. A recommendation without context is not trustworthy. Explanation always precedes proposal.

12. **Recommendations before automation.** The AI may recommend an action. Automation of that action requires explicit human approval. The assistant drafts; the operator approves.

13. **Automation before manual repetition.** If the platform observes a user performing a repetitive action, it should offer to automate it. But it must ask first.

14. **Every generated artifact has lineage.** Any artifact created by the AI (recommendation, experiment definition, config snapshot) must reference its parent artifacts. Orphan artifacts are not permitted.

15. **Every answer exposes evidence.** All factual claims in AI responses include citations. Citations are clickable and navigate to the source artifact. No claim stands without a source.

16. **Never fabricate certainty.** If the AI is uncertain, it says so explicitly. Confidence scores are displayed alongside conclusions. False precision is never presented.

17. **Surface uncertainty explicitly.** When evidence is conflicting, incomplete, or low-confidence, the AI surfaces this before presenting its conclusion. Uncertainty is not hidden in footnotes or tooltips.

18. **Streaming indicates progress.** During AI response generation, the streaming cursor or progress indicator is always visible. Users should never wonder whether the system is working.

19. **AI interruptions are contextual.** The AI may proactively interrupt only for critical findings, completed experiments, or pending approvals that match the user's current context. It never interrupts for informational messages.

### Actions & Feedback

20. **Every important action is reversible or reviewable.** Destructive actions have an undo window or a review step before final execution. Permanent actions require confirmation. Nothing irreversible happens without explicit user intent.

21. **No action without feedback.** Every user action produces a visible response within 100ms. If the response takes longer, a progress indicator appears within 200ms.

22. **Loading preserves layout stability.** Skeletons match the final layout dimensions. Content does not jump or resize as it loads. Layout shift during loading is a defect.

23. **Users should never lose work.** Form input is auto-saved. Drafts are persisted. Closing a page with unsaved changes triggers a warning. Unsaved work recovery is automatic on return.

24. **Confirmation scales with consequence.** Read-only operations are immediate. Destructive operations require confirmation. Irreversible operations require multi-step confirmation. The higher the risk, the higher the friction.

25. **Errors teach, not just notify.** Error messages explain what went wrong, why it happened, and how to fix it. "Something went wrong" is not acceptable. Every error includes a suggested corrective action.

26. **Partial failure is not silent.** If a page loads 8 of 10 widgets successfully, the 2 failures are shown inline with error states. Successful content remains visible. The user is not blocked by partial failures.

27. **Background actions show status.** Long-running operations (experiments, evaluations, config rollouts) show current status, elapsed time, and estimated completion. Users can navigate away and return to see updated status.

### Information Display

28. **One layer of expansion at a time.** Progressive disclosure reveals one additional layer of detail at a time. A single click or tap never reveals more than one level of hidden information.

29. **Empty states are not silent.** Every list, table, and data area has a purposeful empty state. Empty states explain why the area is empty and what action the user can take to populate it.

30. **Counts precede lists.** Before showing a list, show a count. Engineers scan counts to decide whether to engage with a list. Every list header includes a count badge.

31. **Timestamps are absolute by default.** All timestamps default to absolute format ("Mar 24, 10:23 AM") with relative tooltip ("2 hours ago"). Operators need precise time references for investigations.

32. **Status is always color-independent.** Status indicators use shape, icon, and text in addition to color. Red/green color coding is never the sole differentiator.

33. **List density is user-controllable.** Lists default to a compact view with expandable rows. Users can switch between compact and detailed list views. Default is compact.

34. **Charts summarize; tables substantiate.** Charts show patterns. Tables show precise values. Every interactive chart point is explorable to see the underlying data.

### Trust & Safety

35. **Trust is earned through verifiability.** Every platform claim must be verifiable in one click. If a user cannot verify a claim within one click, the interaction model is broken.

36. **Never hide AI reasoning.** The AI's reasoning process, source selection, and confidence calculation are always accessible. "Show your work" is available on every AI response.

37. **Human approval is never skippable.** No production configuration change, experiment launch, or destructive action can bypass the approval workflow. Automation may simplify approval but never eliminate it.

38. **Anonymous data is never assumed.** If the platform cannot authenticate a user, it operates in read-only mode. No actions, no approvals, no configuration changes.

39. **Every change is attributed.** All actions are logged with user identity and timestamp. The audit trail is complete, immutable, and accessible.

40. **Rate-limited interactions for safety.** Automated or rapid repeated actions (batch approve, bulk dismiss) require explicit confirmation of scope before execution.

---

## Interaction Hierarchy

Every feature should support this hierarchy. Users move through these stages naturally. The platform should facilitate movement down the hierarchy without forcing it.

```
1. READ
   └─ Scan the current state. What is happening right now?

2. UNDERSTAND
   └─ Interpret the state. Why is this happening? What does it mean?

3. INVESTIGATE
   └─ Explore details. What evidence supports this? What is the lineage?

4. COMPARE
   └─ Evaluate alternatives. How does this compare to the previous state? What are the options?

5. DECIDE
   └─ Choose a course of action. What should we do about this?

6. ACT
   └─ Execute the decision. Apply the change, launch the experiment, approve the config.

7. REVIEW
   └─ Verify the outcome. Did the action produce the expected result? What changed?
```

### How the hierarchy maps to interactions

| Stage | Interaction Pattern | Navigation Method |
|---|---|---|
| Read | Dashboard, summary cards, count badges | Default landing |
| Understand | AI explanation, daily brief, finding summary | Assistant query or brief section |
| Investigate | Evidence timeline, lineage graph, artifact panel | Click drill-down, side panel |
| Compare | Side-by-side comparison, diff view, experiment results | Compare mode in console |
| Decide | Recommendation review, decision panel | Modal or full-page review |
| Act | Confirm, approve, launch, apply | Modal with appropriate confirmation level |
| Review | Post-action summary, change log, audit trail | Auto-navigate to result or timeline |

Features that skip stages risk pushing users into decisions they do not understand. The platform should facilitate movement through the hierarchy but never force advancement.

---

## Context Preservation

Context is the user's current mental model of the platform state. Preserving it across interactions is critical for engineering velocity.

### Context Types

| Context | Scope | Preserved Where |
|---|---|---|
| Current conversation | Session | Conversation history, pinned artifacts |
| Selected artifact | Session | Side panel, breadcrumb, URL |
| Search filters | Session | URL params, filter bar state |
| Time window | Session | Global time selector, URL param |
| Active experiment | Session | Dashboard widget, sidebar indicator |
| Health view | Per-page | URL, page state |
| Pinned items | Cross-session | User preferences, API |
| Navigation history | Session | Browser history, back stack |

### Context Rules

1. **URL encodes navigable state.** Filters, selected items, time windows, and view modes are encoded in URL parameters for deep linking and back navigation.

2. **Side panel context is independent of main content.** Opening a finding detail in a side panel does not change the main list context. Closing the panel restores the previous view.

3. **Assistant conversations preserve artifact context.** When an assistant response references an artifact, clicking the artifact opens it in context — not in a new session. The user can return to the conversation.

4. **Cross-module transitions preserve source.** Navigating from a finding to its source evidence preserves the finding context. The evidence view shows "You came from finding #1024" and offers a return path.

5. **Time window is global.** Changing the time window in the dashboard updates it for all widgets and propagates to detail views when navigated from the dashboard. Detail views opened independently use their own time defaults.

### Back Navigation Rules

1. Back always returns to the previous logical screen, not the browser's last URL.
2. Closing a side panel returns focus to the element that opened it.
3. The browser back button respects application state, not just URL history.
4. Deep links from external sources (notifications, shared links) set a breadcrumb trail showing "External link" as the entry point.

### Deep Linking Rules

1. Every artifact has a stable, shareable URL.
2. Deep links restore the full context: the artifact detail, its parent list, and relevant filters.
3. Deep links from the assistant include the conversation context as a URL parameter.

---

## Navigation Philosophy

### When to Use Each Navigation Pattern

| Pattern | Used When | Examples |
|---|---|---|
| **Full page navigation** | The user's primary focus changes to a different module or entity. Preserves full context for deep work. | Findings List → Finding Detail, Config List → Config Detail |
| **Side panel** | The user needs supplementary context without leaving the current page. Quick inspection, not deep work. | Finding references from assistant, artifact lineage from any list |
| **Bottom sheet** | Mobile or narrow viewport alternative to side panel. Also used for quick selections with limited options. | Pick a variant, select a time range |
| **Popover** | Instant context for a single element. Dismisses on click outside. No critical actions in popovers. | Status explanation, user avatar detail, metric tooltip |
| **Context menu** | Secondary actions on a list item without navigating. | Right-click on finding: "Acknowledge, Dismiss, Escalate" |
| **Modal** | The user must make a decision or acknowledge information before proceeding. Blocks interaction with the background. | Approve config, confirm destructive action, launch experiment review |
| **Inline expansion** | Revealing additional detail within the current context without navigation. | Expand finding summary to see evidence, expand experiment row to see metrics |
| **Tabs** | Switching between related views of the same entity. Never used for navigation between different entities. | Finding Detail: Evidence | Timeline | Lineage |
| **Accordion** | Hiding optional detail that most users do not need. Never used to hide critical information. | Advanced experiment parameters, raw artifact payload |
| **Breadcrumb** | Showing position within the navigation hierarchy and enabling upward navigation. | Home > Observe > Findings > #1024 |
| **Command palette** | Power users who want to navigate or act without using the mouse. | ⌘K: "Go to findings", "Create experiment", "Search artifact #1024" |

### Navigation Rules

1. **Full pages are for focus.** If a task requires more than 30 seconds of concentrated work, it deserves a full page.
2. **Side panels are for glanceability.** If the user needs to see something briefly before returning to their primary task, use a side panel.
3. **Modals are for decisions.** If the user must make a choice before proceeding, use a modal. Nothing else belongs in a modal.
4. **Inline expansion is for progressive disclosure.** If the user might want more detail but does not always need it, use inline expansion.
5. **Context menus are for power users.** Secondary actions that most users do not need daily belong in context menus. Primary actions are never in context menus.
6. **Tabs categorize, not navigate.** Tabs switch views within a single entity. They do not navigate between different modules.

---

## Confirmation Philosophy

### Interaction Levels

| Level | Behavior | Examples |
|---|---|---|
| **Immediate** | Action executes without confirmation. Reserved for zero-consequence operations. | Open finding, expand section, apply filter, dismiss toast |
| **Undo** | Action executes immediately but can be undone within a time window (5-30 seconds). | Dismiss finding, delete draft, archive artifact |
| **Preview** | Action shows a preview of the result before the user commits. | View config diff before approving, preview experiment definition before launching |
| **Review** | Action collects all changes into a review screen where the user confirms the full scope before execution. | Batch acknowledge findings, launch experiment, generate config snapshot |
| **Approve** | Action requires a separate approval step, possibly by a different user (Engineering Manager). | Apply config snapshot, approve recommendation for production |
| **Multi-step approval** | Action requires multiple distinct confirmations. Used for irreversible or high-risk operations. | Rollback configuration, delete experiment with active data, modify governance policy |
| **Risk acknowledgment** | Action displays a risk summary and requires the user to explicitly acknowledge each risk before proceeding. | Deploy unverified config, force-stop running experiment |

### Action-to-Level Mapping

| Action Type | Confirmation Level |
|---|---|
| Navigate to a page | Immediate |
| Apply a filter | Immediate |
| Acknowledge a finding | Undo (30s) |
| Dismiss a single finding | Undo (15s) |
| Batch dismiss findings | Review |
| Open an artifact | Immediate |
| Share an artifact | Immediate |
| Export data | Immediate (or Preview for large exports) |
| Approve a recommendation | Approve |
| Reject a recommendation | Review (requires reason) |
| Launch an experiment | Review |
| Declare experiment winner | Review |
| Create a config snapshot | Review |
| Apply a config snapshot | Approve |
| Rollback configuration | Multi-step approval |
| Delete a document | Undo (30s) or Review for batch |
| Run automation job | Review |
| Modify a schedule | Preview + Confirm |
| Modify governance policy | Multi-step approval |
| Delete an experiment | Multi-step approval |
| Modify user permissions | Approve (requires Engineering Manager) |

### Confirmation Design Rules

1. The confirmation level is determined by the action's consequence, never by the UI context.
2. Actions of the same type always use the same confirmation level regardless of where they appear.
3. Confirmation dialogs always explain the consequence: "This will apply configuration snapshot v143 to production. Rollback plan: [link]."
4. Undo actions always show a visible undo button with a countdown timer.
5. Multi-step approvals show a progress indicator ("Step 2 of 3").

---

## Progressive Disclosure

### Layered Information Model

```
Layer 1: SUMMARY
  └─ What the user needs at a glance.
     └─ Title, status, key metric, severity, timestamp
     └─ Always visible. No interaction required.

Layer 2: KEY EVIDENCE
  └─ What supports the summary.
     └─ Primary evidence, supporting metrics, brief explanation
     └─ Visible on click or inline expand. One interaction away.

Layer 3: DETAILED EVIDENCE
  └─ The full evidence set.
     └─ All evidence items, methodology, confidence scores
     └─ Side panel or expanded section. Two interactions away.

Layer 4: RAW ARTIFACTS
  └─ The unprocessed data.
     └─ Full artifact payload, raw metrics, complete lineage
     └─ Full page or artifact explorer. Three interactions away.

Layer 5: LOGS / TRACE
  └─ The source-level detail.
     └─ System logs, trace spans, raw telemetry
     └─ External link or dedicated trace viewer. Four interactions away.
```

### Application

| Entity | Layer 1 | Layer 2 | Layer 3 | Layer 4 |
|---|---|---|---|---|
| Finding | Title, severity, status, affected capability | Evidence timeline summary, key metric | Full evidence list, methodology, raw metric chart | Artifact payload |
| Recommendation | Title, confidence score, status, source finding | Evidence summary, proposed change | Full evidence, risk assessment, config diff | Artifact payload |
| Experiment | Name, status, duration, variants | Metric summary, leader indicator | Full metric comparison, statistical analysis | Raw experiment data |
| Config snapshot | Version, status, timestamp, author | Change summary, diff overview | Full diff, risk assessment, rollback plan | Raw config payload |
| Artifact | ID, type, timestamp, capability | Summary, lineage parents | Full metadata, lineage graph | Raw JSON payload |

### Disclosure Rules

1. Layer 1 is always visible without interaction. Engineers scan Layer 1 to decide whether to engage.
2. Each layer is exactly one interaction away from the previous layer.
3. Layers are never skipped. The user does not jump from summary to raw payload without seeing the evidence.
4. The "expand" affordance is consistent: chevron icon, "+" badge, or "Show more" link. Never a different affordance per entity type.
5. Raw payload viewers offer syntax-highlighted JSON and search within the payload.

---

## Trust Model

### Interaction Patterns That Build Trust

| Pattern | Description | Implementation |
|---|---|---|
| **Confidence indicators** | Every AI-generated conclusion shows a confidence score. | Badge or progress bar on recommendation cards, evidence items |
| **Evidence cards** | Every claim is accompanied by a compact evidence card showing the source, value, and timestamp. | Collapsible card below AI response claims |
| **Source links** | Every artifact reference is a clickable link to its detail page. | Inline hyperlink on artifact IDs |
| **Reasoning summary** | AI responses include a brief summary of how the conclusion was reached. | Expandable "Show reasoning" section |
| **Retrieval metadata** | The AI shows which sources were searched, which were found, and which were used. | Expandable "Sources" section |
| **Known limitations** | The AI explicitly states when information is missing, outdated, or incomplete. | Inline callout at the top of the response |
| **Missing evidence** | When evidence was expected but not found, the AI explains why. | "I searched the Evidence Engine and Learning Ledger but found no records matching this query." |
| **Timestamp visibility** | Every data point shows when it was last updated. | Badge or text: "Updated 2 hours ago" |
| **Contradiction handling** | When evidence sources conflict, the AI presents both sides. | Side-by-side comparison with explanation of discrepancy |
| **Human verification prompt** | Before high-consequence conclusions, the AI prompts the user to verify key evidence. | "Please verify this evidence before making a decision: [link]" |

### Trust Rules

1. The first time a user sees a type of AI-generated conclusion, the platform should show the evidence verification path explicitly. ("You can verify this by clicking the evidence link.")
2. Confidence scores below 70% should always include an explanation of what would increase confidence.
3. Evidence cards are collapsed by default but visually indicate they contain sources. They expand on click.
4. When the AI is uncertain, the uncertainty is communicated before the conclusion, not after.

---

## Error Interaction

### Error Type Behaviors

| Error Type | User Experience | Recovery |
|---|---|---|
| **Validation error** | Inline error below the field. Red border. Error message explains the constraint. | User corrects input. Error clears on valid input. |
| **Network failure** | Inline banner at the top of the affected area. "Connection lost. Retrying..." Shows last-known data if available. | Auto-retry with exponential backoff. Manual retry button. |
| **Tool failure** | The AI explains which tool failed and why. "I was unable to retrieve experiment results because the Experimentation service returned an error." | Suggest alternative approach or retry. |
| **Partial failure** | Successful widgets render. Failed widgets show inline error. Layout is not disrupted. | Retry per widget or refresh page. |
| **Permission error** | The action button is disabled with a tooltip: "You need X role to perform this action." | Contact admin or switch account. |
| **Unavailable data** | Empty state with explanation. "No data is available for the selected time window. The Continuous Evaluation pipeline may not have run yet." | Expand time window, check pipeline status. |
| **Conflicting evidence** | The AI presents both sources with the discrepancy highlighted. "Source A says X, Source B says Y. The difference may be due to..." | User investigates both sources. |
| **Timeout** | "The request timed out. Partial results may be available." Shows partial data if any. | Retry with longer timeout or narrower scope. |
| **Long-running job** | Progress bar with elapsed time and estimated completion. "Experiment AB-47 is 60% complete. Estimated 2 hours remaining." | User can navigate away and return. Notification on completion. |
| **Cancelled operation** | The UI returns to the previous state with a brief message. "Experiment launch was cancelled. No changes were made." | User can restart the flow. |

### Error Communication Principles

1. **Errors are contextual.** An error message explains what the user was doing, what went wrong, and what to do next. "Failed to load findings. The Evidence Engine is experiencing high latency. Try again in a few seconds."
2. **Errors preserve user work.** Form data, filter selections, and view state survive error conditions. A network failure during form submission does not clear the form.
3. **Errors are not silent.** All errors produce visible feedback. Errors that happen in the background (auto-refresh, polling) are silently retried but surfaced if they persist beyond the retry limit.
4. **Error severity determines visibility.** Toast for recoverable errors. Inline banner for partial failures. Full-page error for critical failures. Modal for blocking errors.
5. **Error messages are human-readable.** No error codes unless the user explicitly requests them. Error codes, when shown, are secondary text below the human-readable message.

---

## AI Interaction Principles

### Streaming

1. AI responses always stream. The user sees tokens appearing progressively. Streaming starts within 500ms of query submission.
2. The streaming cursor (animated indicator) is always visible during generation.
3. The user can interrupt streaming at any point. Interrupting stops generation and shows the partial response.
4. Streaming preserves the response structure. Headers, lists, and citations appear in their final positions as they stream.
5. When tool execution is required, a progress indicator replaces the streaming cursor with the tool name and status.

### Interruptions

1. The AI may proactively interrupt the user only for: critical findings on the user's monitored capabilities, completed experiments the user launched, pending approvals the user is waiting for.
2. Proactive interruptions are contextual. The AI does not interrupt with information unrelated to the user's current session or role.
3. Interruptions are delivered as suggestions, not demands. "I noticed a critical finding has been generated. Would you like me to summarize it?"

### Tool Execution

1. Tool calls are visible to the user. The AI shows which tool it is calling and why.
2. Long-running tool calls show progress. The user sees "Retrieving experiment results..." with an animated indicator.
3. Failed tool calls include the error and a retry option.
4. Tool calls that produce visualizable results (charts, diffs, comparisons) render inline in the conversation.

### Reasoning Summaries

1. Every AI response includes an expandable "Show reasoning" section.
2. The reasoning summary shows: which tools were called, what evidence was retrieved, how the conclusion was reached.
3. Reasoning summaries are LLM-generated (not raw chain-of-thought) for readability.

### Suggested Actions

1. After each response, the AI suggests 2-4 follow-up actions relevant to the current context.
2. Suggested actions are buttons or quick-reply chips, not plain text.
3. Example: After explaining a finding: "Investigate further — View evidence — Dismiss finding — Create recommendation"

### Follow-Up Questions

1. The AI generates 2-3 follow-up questions that anticipate the user's likely next information need.
2. Follow-up questions appear as clickable chips below the response.
3. Follow-up questions are context-aware. They reference artifacts mentioned in the current conversation.

### Context Carry-Over

1. The AI retains the full conversation history within a session.
2. The AI remembers the current "subject" (investigation target, experiment, finding).
3. When the user switches subjects, the AI acknowledges the shift: "Switching from finding #1024 to experiment AB-47."
4. The AI can reference artifacts from earlier in the conversation without re-retrieval.

### Response Citations

1. Every factual claim includes inline citations.
2. Citations are rendered as superscript numbers or bracketed references: "Retrieval accuracy dropped to 87% [1]."
3. Hovering over a citation shows a tooltip with the source summary.
4. Clicking a citation opens the source artifact in a side panel.
5. The full citation list appears at the end of the response.

### Artifact References

1. Artifact references in AI responses are rendered as rich links: icon + type + ID + title.
2. Example: "Based on [Finding #1024 — Retrieval Accuracy Degradation], I recommend..."
3. Artifact links are clickable and navigate to the artifact detail screen.
4. The artifact reference color is distinct from regular links.

---

## Accessibility Principles

### Keyboard-First

1. Every interactive element is reachable via keyboard.
2. Tab order follows the visual hierarchy (top-to-bottom, left-to-right).
3. Focus indicators are always visible and high-contrast.
4. Custom keyboard shortcuts are documented and avoid conflicting with browser shortcuts.
5. The command palette (⌘K) provides keyboard access to every action.
6. All modals trap focus and close on Escape.
7. Arrow keys navigate lists, tables, and tab panels.

### Screen Readers

1. All interactive elements have accessible names.
2. Dynamic content updates use `aria-live` regions.
3. Status changes (loading, error, success) are announced.
4. Charts have text alternatives or data tables.
5. AI streaming responses announce when generation starts and completes.
6. Custom components use appropriate ARIA roles.

### Focus Management

1. Focus moves predictably: Tab moves forward, Shift+Tab moves backward.
2. Opening a modal moves focus to the first interactive element in the modal.
3. Closing a modal returns focus to the element that triggered it.
4. Navigating between pages sets focus to the page title or main content area.
5. Side panel opening moves focus to the panel content.
6. Side panel closing moves focus to the trigger element.

### Reduced Motion

1. All animations respect `prefers-reduced-motion`.
2. Reduced motion mode: fade transitions replace slide transitions. No scale or bounce animations. Streaming cursor becomes a simpler indicator.
3. Auto-refresh polling does not animate when reduced motion is enabled.

### Color Independence

1. No information is conveyed through color alone.
2. Status indicators use shape, icon, and text in addition to color.
3. Links are underlined (not just colored).
4. All charts use patterns or labels in addition to color coding.
5. Focus indicators are not color-dependent.

### Touch Targets

1. All interactive elements are at least 44x44px.
2. Sufficient spacing between touch targets to prevent mis-taps.
3. Swipe gestures are accessible via alternative button controls.

### High Contrast

1. All text meets WCAG AA contrast ratios (4.5:1 normal, 3:1 large).
2. UI controls and focus indicators meet 3:1 contrast against adjacent colors.
3. High-contrast mode is supported and tested.

---

## Performance Perception

The platform should *feel* fast even when operations take time.

### Perception Rules

1. **Skeletons are the default loading state.** Every page, list, and widget has a skeleton that matches the final layout dimensions. Content does not jump on load.

2. **Streaming is preferred over blocking.** AI responses, search results, and large list loads should stream or progressively load rather than blocking the UI.

3. **Optimistic updates for predictable actions.** Actions with predictable outcomes update the UI immediately and revert on failure (with a visible error and retry).

4. **Background refresh for stale data.** Widgets and lists auto-refresh in the background. The user sees a subtle "Updated" indicator rather than a loading spinner.

5. **Progress indicators show expected duration.** Operations under 1 second show a brief spinner. Operations over 1 second show a progress bar. Operations over 10 seconds show estimated time remaining.

6. **Prefetching for anticipated navigation.** Hovering over a link or viewing an item triggers prefetch of the target page data.

7. **State preservation prevents reloads.** Navigating back to a previously visited page restores the cached state without a network request. Cache is invalidated on explicit refresh or after a time threshold.

### Load Times

| Interaction | Target | Degradation Threshold |
|---|---|---|
| Page navigation (full) | < 1s skeleton visible, < 2s content ready | > 3s shows loading state |
| AI response start | < 500ms first token | > 2s shows "still working" message |
| List load (50 items) | < 500ms | > 2s shows progressive load |
| Search results | < 200ms first result | > 1s shows "searching" indicator |
| Side panel open | < 300ms | > 1s shows skeleton in panel |
| Command palette | < 100ms | > 300ms shows loading state |

---

## Anti-Patterns

### Forbidden Interaction Behaviors

1. **Surprising navigation.** Navigating the user to a different page without their explicit intent. Example: clicking a filter option navigates to a different module.

2. **Hidden destructive actions.** Destructive actions (delete, rollback, dismiss in bulk) without visible, clear confirmation. Example: an icon button with no label that deletes an artifact without confirmation.

3. **Modal overload.** Requiring the user to dismiss multiple sequential modals before returning to their work. Exception: multi-step approval workflows that show a progress indicator.

4. **Infinite confirmations.** Asking the user to confirm the same type of action repeatedly within a session without offering "Don't ask again for this session" or "Apply to all."

5. **Blocking without explanation.** Showing a loading spinner without indicating what is happening or how long it might take. Example: "Loading..." without context for more than 2 seconds.

6. **Loading spinners without progress.** Using an indeterminate spinner for operations that take more than 5 seconds. Long operations require progress bars or status messages.

7. **Silent failures.** An action appears to succeed but fails without any user-visible feedback. Example: clicking "Save" shows no error but the data is not persisted.

8. **Hidden AI reasoning.** AI responses that present conclusions without any way for the user to inspect the reasoning or source evidence.

9. **Fake confidence.** AI responses that present low-confidence conclusions with the same certainty as high-confidence ones. Example: "This is definitely the issue" when confidence is below 70%.

10. **Inconsistent interactions.** The same action behaves differently in different contexts. Example: "Approve" is a single click on the findings page but requires a multi-step modal on the recommendations page.

11. **Orphaned artifacts.** Features that create artifacts (recommendations, snapshots, experiments) without establishing lineage to the parent artifact.

12. **Context reset.** Navigating away from a page and returning to find filters, scroll position, or selected items cleared.

13. **Auto-play or auto-advance.** Content that advances without user interaction (carousels, auto-rotating tabs, auto-advancing lists).

14. **Animation without purpose.** Motion that does not communicate state change, progress, or system status. Decorative animation is forbidden.

15. **Undo without visibility.** Undo actions that do not show an undo button with a countdown timer.

16. **Denying user control.** Preventing the user from interrupting a long-running operation, changing their mind after initiating an action, or correcting a mistake.

17. **Assumed identity.** Performing actions or showing data without confirming the user's identity and permissions.

18. **Infinite scroll without context.** Infinite scroll lists that do not show item counts, search within the list, or allow the user to return to a previously viewed item.

---

## Future Evolution

### As the Assistant Becomes More Agentic

1. The interaction principles remain valid: human approval before execution, evidence before recommendations, context preservation.
2. Agentic workflows introduce a new interaction pattern: "Managed workflow" where the user delegates a bounded task and monitors progress.
3. Managed workflows require: clear scope definition, progress reporting, pause/resume capability, and result review before any production effect.
4. The confirmation philosophy extends: agentic actions at the workflow level require approval; individual tool calls within a managed workflow do not require per-call approval.

### As Multiple AI Agents Collaborate

1. Multi-agent interactions introduce "agent attribution" — the user can see which agent performed which action.
2. Cross-agent handoffs are visible. The user sees "Agent A handed off to Agent B for experiment analysis."
3. The trust model extends: each agent has its own confidence score, and the platform shows a combined confidence.
4. The conversation model extends: multi-agent discussions are shown as parallel threads.

### As Automation Increases

1. Automation introduces "supervised autonomy" — the platform can execute bounded workflows within explicit guardrails.
2. The human approval principle remains: the guardrails are set by humans. The automation operates within them.
3. Automation introduces a new interaction pattern: "Approval policy" — users pre-approve categories of actions so routine operations do not require per-action approval.
4. Automation events are always visible in the activity timeline. Silent automation is not permitted.

### As Natural Language Becomes Primary

1. The command palette and AI assistant merge into a unified natural language interface.
2. Navigation remains available for power users but becomes secondary to conversational interaction.
3. The progressive disclosure model extends: the AI handles Layer 1-2 (summary, key evidence) in conversation; the console handles Layer 3-5 (detailed, raw, trace).
4. The interaction hierarchy adapts: the AI assists with Read, Understand, Investigate, and Compare; the user focuses on Decide, Act, and Review.

### As New Modules Are Added

1. New modules inherit all interaction principles. They do not define their own interaction patterns.
2. New modules are added to the sidebar and navigation hierarchy following the existing positioning rules.
3. New modules register their artifact types with the Artifact Explorer and global search.
4. New modules specify their place in the progressive disclosure model — what belongs in Layer 1, 2, 3 for the new entity type.
5. The confirmation philosophy is reviewed: where does the new module's actions fall in the action-to-level mapping?

---

## Appendix: Principle Summary

### The 40 Interaction Principles

| # | Principle | Category |
|---|---|---|
| 1 | One primary action per screen | Navigation & Context |
| 2 | Every page is reachable in three clicks | Navigation & Context |
| 3 | Never interrupt without value | Navigation & Context |
| 4 | Never hide critical information | Navigation & Context |
| 5 | Never remove user context | Navigation & Context |
| 6 | Always preserve navigation history | Navigation & Context |
| 7 | State is preserved per session | Navigation & Context |
| 8 | Navigation never reorganizes | Navigation & Context |
| 9 | Side panels are for context, not primary actions | Navigation & Context |
| 10 | Every link is navigable | Navigation & Context |
| 11 | AI explains before recommending | AI Interaction |
| 12 | Recommendations before automation | AI Interaction |
| 13 | Automation before manual repetition | AI Interaction |
| 14 | Every generated artifact has lineage | AI Interaction |
| 15 | Every answer exposes evidence | AI Interaction |
| 16 | Never fabricate certainty | AI Interaction |
| 17 | Surface uncertainty explicitly | AI Interaction |
| 18 | Streaming indicates progress | AI Interaction |
| 19 | AI interruptions are contextual | AI Interaction |
| 20 | Every important action is reversible or reviewable | Actions & Feedback |
| 21 | No action without feedback | Actions & Feedback |
| 22 | Loading preserves layout stability | Actions & Feedback |
| 23 | Users should never lose work | Actions & Feedback |
| 24 | Confirmation scales with consequence | Actions & Feedback |
| 25 | Errors teach, not just notify | Actions & Feedback |
| 26 | Partial failure is not silent | Actions & Feedback |
| 27 | Background actions show status | Actions & Feedback |
| 28 | One layer of expansion at a time | Information Display |
| 29 | Empty states are not silent | Information Display |
| 30 | Counts precede lists | Information Display |
| 31 | Timestamps are absolute by default | Information Display |
| 32 | Status is always color-independent | Information Display |
| 33 | List density is user-controllable | Information Display |
| 34 | Charts summarize; tables substantiate | Information Display |
| 35 | Trust is earned through verifiability | Trust & Safety |
| 36 | Never hide AI reasoning | Trust & Safety |
| 37 | Human approval is never skippable | Trust & Safety |
| 38 | Anonymous data is never assumed | Trust & Safety |
| 39 | Every change is attributed | Trust & Safety |
| 40 | Rate-limited interactions for safety | Trust & Safety |
