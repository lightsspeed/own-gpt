# Navigation Behavior Architecture

> Navigation is movement through engineering knowledge.
>
> Users should never feel lost. Users should never lose context.
>
> This document defines HOW NAVIGATION SHOULD BEHAVE — not where it goes, but how movement feels.

---

## Purpose

### Why Navigation Is Movement Through Knowledge

Traditional applications organize pages in a hierarchy. Users navigate "down" into details and "up" to summaries. Navigation is a tree.

This platform organizes engineering knowledge as a connected graph. Navigation is traversal through relationships — from a finding to its evidence, from evidence to the experiment that validated it, from the experiment to the decision that approved it, from the decision to the configuration that changed.

Users do not navigate between pages. They navigate between related pieces of engineering knowledge. The page is just the container for that knowledge.

### Why Conversations, Artifacts, Commands, and Tools Redefine Navigation

Traditional navigation assumes the user starts at a menu and clicks through pages. This platform offers multiple entry points that bypass traditional navigation:

- **Conversations**: Users ask the assistant and the assistant navigates on their behalf. The user does not click a menu — they express intent.
- **Artifacts**: Users navigate through relationships and lineage. They do not go "back to the list" — they go "to the parent artifact."
- **Commands**: Users type what they want and the platform navigates for them. The command palette replaces menu browsing.
- **Tools**: Tool results contain navigable artifact links. The user navigates from within a response, not from a navigation bar.

Navigation in this platform is nonlinear, relationship-driven, and intent-initiated. The behavioral architecture must support all paths equally.

---

## Navigation Philosophy

### Context over hierarchy

Users should not need to know where they are in a page hierarchy to navigate effectively. Knowing their current context — active artifact, active conversation, current filters — is sufficient for all navigation decisions.

### Intent over menus

Navigation should be initiated by intent (what do I want to see?) rather than by menu selection (which page do I open?). The command palette, assistant, and relationship links are the primary navigation methods. The sidebar is a fallback.

### Relationships over folders

Artifacts are not organized into folders. They are connected through relationships. Navigation follows relationships, not directory trees. A finding's "parent" is its evidence, not a folder name.

### Continuity over page changes

Navigation should feel like a shift in focus, not a disruption. The sidebar, top bar, and global state remain stable. Only the content area changes. The user should never feel like they have entered a different application.

### Progressive exploration

Navigation should invite exploration. Every artifact shows related artifacts. Every result suggests next destinations. Users discover the platform's depth through navigation, not through documentation.

### Minimal disorientation

Users should always be able to answer: where am I, how did I get here, where can I go next. Breadcrumbs, context indicators, and navigation history are always accessible.

### Multiple valid paths

There is no single "correct" path to any destination. Users may reach the same finding through the dashboard, the assistant, the command palette, a notification, a relationship link, or a conversation reference. All paths are equally valid.

### Recoverable navigation

Every navigation action is reversible. Back returns the user to their previous context. Navigation history is complete and browsable. Users can never navigate somewhere they cannot return from.

### Navigation should preserve work

Navigating to a different screen does not discard unsaved work, clear filters, reset scroll position, or lose the conversation thread. Work in progress persists across all navigation.

### Navigation should preserve thinking

Navigating should not force the user to rebuild their mental model. The breadcrumb shows the path. The context indicator shows the current focus. The navigation history shows the exploration trail. Users carry their thinking with them.

---

## Navigation Principles

### Context & Orientation

1. **Every screen has a clear identity.** The user can immediately identify where they are, what module they are in, and what entity they are viewing.

2. **Every screen shows how you got there.** Breadcrumbs, navigation history, or context indicators show the path taken to reach the current view.

3. **Every screen shows where you can go next.** Related artifacts, suggested actions, and navigable links are always present.

4. **Context is never lost on navigation.** The active conversation, selected artifact, pinned items, filters, time window, and workspace state survive all navigation.

5. **Navigation preserves state per entity.** Navigating away from a finding and back returns to the same scroll position, expanded sections, and active tab.

6. **The navigation structure is stable.** The sidebar, top-level modules, and primary navigation paths do not change within a session.

### Navigation Initiation

7. **Navigation can be initiated from anywhere.** The command palette, assistant, search, relationship links, notifications, and breadcrumbs all initiate navigation.

8. **Navigation always shows the target context.** When navigation is initiated from a link, the user sees both the destination and the context: "Opened from Finding #1024."

9. **Navigation has a single preferred form.** The same destination reached through different paths shows the same view. Context differences are communicated through breadcrumbs.

10. **Navigation never happens without user intent.** The platform does not navigate the user to a different page unless the user explicitly initiates navigation.

### Navigation Types

11. **Full page navigation is for focus.** Full page navigation is for deep work: inspecting an artifact, comparing experiments, reviewing configuration. It is not the default navigation mode.

12. **Side panel navigation is for glanceability.** Side panels show supplementary context without leaving the current page. They are for quick inspection, not primary workflows.

13. **Inline navigation is for progressive disclosure.** Expanding a summary to see evidence, unfolding a finding to see its lineage — these are navigations within the current view.

14. **Conversational navigation is for exploration.** Asking the assistant a question and clicking the resulting artifact links is a primary navigation path.

### History & Recovery

15. **Back always returns to the previous logical context.** Back does not simply navigate to the previous URL. It returns to the previous user context.

16. **Navigation history is browsable.** Users can see and jump to any point in their navigation history within the current session.

17. **Navigation is fully reversible.** Every navigation action can be undone. Side panels close. Full pages return to the previous view. Inline expansions collapse.

18. **Users can always return to a known anchor.** The Dashboard, the active conversation, and the command palette are always one action away.

### Deep Links & Sharing

19. **Every significant view has a stable URL.** Conversations, artifacts, findings, experiments, reports, and investigation states are all shareable.

20. **Deep links restore full context.** Opening a deep link restores the artifact, its filters, its time window, and any relevant conversation context.

21. **Deep links are human-readable.** URLs follow a predictable pattern: `/conversations/:id`, `/artifacts/:type/:id`.

### Cross-Experience

22. **Navigation behavior is consistent across all experiences.** The same navigation rules apply in the assistant, dashboard, operations console, and search.

23. **Navigation between experiences preserves cross-cutting context.** Moving from Dashboard to a Finding preserves the time window. Moving from a Conversation to an Artifact preserves the conversation reference.

24. **The assistant and the command palette share the same navigation destinations.** Any destination in the sidebar can be reached by typing in the palette or asking the assistant.

### Performance

25. **Navigation is instant or shows progress.** Target content appears within 500ms or a loading indicator is shown. Skeleton screens preserve layout stability.

26. **Navigation state is cached.** Revisiting a recently viewed screen does not require reloading. State is preserved for the session duration.

27. **Navigation never blocks.** Users can initiate navigation at any time. Ongoing operations continue in the background.

### Safety

28. **Navigation never discards work.** Unsaved work, active conversations, and in-progress investigations survive all navigation.

29. **Navigation never executes actions.** Navigating does not submit forms, approve requests, or change state. Navigation is read-only.

30. **Navigation preserves destructive confirmation.** If the user had a destructive confirmation dialog open, navigating away cancels the confirmation (not the action).

31. **Navigation to external resources is warned.** Links that leave the platform show a confirmation: "You are leaving the AI Engineering Platform."

### Accessibility

32. **Navigation is keyboard-accessible.** All navigation actions are reachable via keyboard. Tab order follows visual hierarchy.

33. **Screen readers announce navigation.** When navigation occurs, screen readers announce the new location and context.

34. **Focus management is predictable.** After navigation, focus moves to the main content area. After side panel open, focus moves to the panel.

35. **Navigation respects reduced motion.** Navigation transitions are simple and do not trigger motion sickness.

---

## Navigation Model

### Conceptual Relationships

```
                         ┌──────────────┐
                         │  DASHBOARD   │
                         │  (Home / /)  │
                         └──────┬───────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
     ┌──────────┐      ┌──────────────┐     ┌────────────┐
     │ASSISTANT │      │  OPERATIONS  │     │  SEARCH    │
     │  (/)     │      │  CONSOLE     │     │  (⌘K)     │
     └────┬─────┘      │  (/ops/*)    │     └─────┬──────┘
          │            └──────┬───────┘           │
          │                   │                   │
          │            ┌──────┴──────┐            │
          │            │             │            │
          ▼            ▼             ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
    │CONVERS-  │ │ FINDINGS │ │ EXPERIM- │ │ NOTIFIC- │
    │ATION     │ │ /ops/find│ │ ENTS     │ │ ATIONS   │
    │ /conv/:id│ │          │ │ /ops/exp │ │ /notif   │
    └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
         │            │            │            │
         └────────────┼────────────┼────────────┘
                      │            │
                      ▼            ▼
                ┌──────────┐ ┌──────────┐
                │ ARTIFACT │ │ DECISION │
                │ DET      │ │ /dec/:id │
                │ /art/:id │ └──────────┘
                └──────────┘
                      │
                      ▼
                ┌──────────┐
                │ LINEAGE  │
                │ (graph)  │
                └──────────┘
```

### Navigation Entry Points and Their Behaviors

| Entry Point | Navigation Behavior | Context Carried |
|---|---|---|
| **Dashboard** | Primary navigation hub. Click widgets to drill into modules. | Time window, health context |
| **Assistant** | Conversational navigation. User asks, assistant responds with artifact links. | Conversation history, pinned artifacts |
| **Command Palette** | Intent-based navigation. User types destination, platform navigates. | Current workspace context |
| **Search** | Discovery navigation. User searches, selects result. | Search query, filters |
| **Notifications** | Alert-driven navigation. User clicks notification, navigates to relevant artifact. | Notification context |
| **Relationship Links** | Graph navigation. User clicks related artifact link. | Source artifact context |
| **Breadcrumbs** | Hierarchical navigation. User clicks parent level. | Current location context |
| **Sidebar** | Module navigation. User clicks module name. | None (module root) |

### Navigation Model Rules

1. All entry points lead to the same destination views. The finding detail view looks the same whether reached from Dashboard, Assistant, Search, or Notifications.
2. All entry points preserve the user's active conversation. Navigating from a conversation to an artifact does not end the conversation — the user can return.
3. All entry points carry relevant context. The destination view shows "Opened from [source]" when navigation crosses contexts.
4. The only exception to rule 1 is the Assistant's inline artifact cards, which show a summary rather than a full detail view. Full detail is one click away.

---

## Context Preservation

### What Must Survive Navigation

| Context Element | Survival Rule | Restoration Behavior |
|---|---|---|
| **Active conversation** | Always preserved. Navigates to a side panel or new tab. Conversation remains active. | Return via "Return to conversation" link in breadcrumb or navigation history. |
| **Selection state** | Preserved within the same module. List view remembers which item was selected. | Navigating back to the list restores the selection highlight. |
| **Filters and time window** | Preserved within the same module. Navigating to a detail and back restores filters. | Filters are encoded in URL parameters. Back button restores them. |
| **Pinned artifacts** | Always preserved. Pins are conversation- or session-scoped. | Visible in the conversation side panel or workspace pin area. |
| **Workspace layout** | Preserved per session. Customized widget layouts, panel widths, and sidebar state survive. | Restored on page load within the same session. |
| **Navigation history** | Always preserved. Full session navigation history is maintained. | Accessible via back button, history panel, or breadcrumb dropdown. |
| **Open investigations** | Always preserved. Multi-turn investigations in the assistant are not discarded by navigation. | Return to the assistant conversation to continue. |
| **Command history** | Preserved per session. Recently executed commands are available in the palette. | Shown in the "Recent" section of the command palette. |
| **Drafts** | Always preserved. Unsaved drafts, partial forms, and composed messages survive navigation. | Restored on return to the relevant screen. Auto-save prevents loss. |
| **Search state** | Preserved within the search session. Search query, filters, and results page survive. | Back button returns to search results. URL encodes query state. |
| **Side panel state** | Only one side panel at a time. Opening a new panel replaces the current one. | Previous panel state is cached. Closing the new panel restores the previous. |
| **Scroll position** | Preserved within list views and long documents. | Restored exactly on return. |

### Context Preservation Rules

1. Context is never discarded unless the user explicitly clears it (e.g., "Clear filters", "Close conversation").
2. Context that cannot be preserved is communicated before navigation: "Navigating away will discard your current filter selection."
3. Session context is persisted to localStorage or equivalent. A page refresh does not clear context.
4. Cross-session context (pinned artifacts, saved filters) is persisted to the user's platform preferences.

---

## Navigation History

### Conceptual History Model

Navigation history is not a URL stack. It is a tree of user context transitions:

```
Initial: Dashboard
  │
  ├── Dashboard → Findings List (filter: critical)
  │     │
  │     ├── Findings List → Finding Detail (#1024)
  │     │     │
  │     │     ├── Finding Detail → Evidence Detail (#512)
  │     │     │     │
  │     │     │     └── Evidence Detail → Finding Detail (back)
  │     │     │
  │     │     └── Finding Detail → Recommendation Detail (#89)
  │     │           │
  │     │           └── Recommendation Detail → Finding Detail (back)
  │     │
  │     └── Findings List → Dashboard (back)
  │
  ├── Dashboard → Assistant Conversation
  │     │
  │     └── Conversation → Artifact Explorer
  │
  └── Dashboard → Notifications → Finding Detail (#1030)
```

### History Operations

| Operation | Behavior | User Action |
|---|---|---|
| **Back** | Returns to the previous context in the history stack. Restores full context (scroll, filters, selection). | Back button, browser back, swipe gesture |
| **Forward** | Re-advances to the context that was backed from. Only available after back. | Forward button, browser forward |
| **Jump** | Navigates to any point in the history tree. Does not replay intermediate steps. | History panel dropdown |
| **Recent** | Shows the last 10 unique locations. Quick access to frequently revisited places. | "Recent" section in command palette or history panel |
| **Reopen** | Reopens a previously closed conversation or artifact. | "Reopen" action on archived items |
| **Return to investigation** | Navigates from any location back to the current active investigation. | "Return to investigation" link in breadcrumb or history |
| **Saved locations** | User-bookmarked locations. Persistent across sessions. | Bookmarks/favorites section |
| **Pinned locations** | User-pinned locations for the current session. | Pinned section in sidebar or history |

### History Rules

1. History is preserved for the session duration (until logout or session timeout).
2. History is not preserved across different user sessions.
3. History includes: screen location, filter state, scroll position, time window, and selection state.
4. History entries are labeled with human-readable titles: "Finding #1024 — Retrieval Accuracy Degradation."
5. Users can clear history at any time. Clearing history does not affect pinned or saved locations.

---

## Relationship Navigation

### How Users Navigate Through Relationships

Navigation through relationships is the primary method for deep exploration:

```
Finding #1024: "Retrieval accuracy degraded"
    │
    ├── Evidence (what supports this)
    │   ├── Evidence #512: Accuracy metrics
    │   │   └── Analytics Report: Metric trend
    │   └── Evidence #513: Config change log
    │       └── Config Snapshot v141: Parallel retrieval increase
    │
    ├── Recommendations (what was proposed)
    │   └── Recommendation #89: Increase temperature
    │       └── Experiment AB-47: Temperature variant test
    │           ├── Decision #12: Winner declared (temperature increase)
    │           │   └── Config Snapshot v143: Temperature updated
    │           └── Decision #13: Rollback (latency impact)
    │               └── Config Snapshot v144: Reverted temperature
    │
    └── Conversations (what was discussed)
        ├── "Health degradation investigation" (Mar 24)
        └── "Experiment AB-47 review" (Mar 25)
```

### Relationship Navigation Rules

1. Every artifact detail view includes a "Related" panel showing navigable relationships.
2. Relationships are grouped by type: Evidence, Recommendations, Experiments, Decisions, Conversations.
3. Each relationship link includes the artifact type, ID, title, and status.
4. Clicking a relationship navigates to that artifact. The source artifact's context is preserved in breadcrumbs.
5. Lineage navigation follows the full parent-child chain. Users can traverse forward and backward through the artifact graph.
6. Conversations are first-class relationship targets. Every artifact shows which conversations referenced it.
7. Dependency navigation allows users to see what an artifact depends on and what depends on it (for config snapshots, capabilities, and experiments).

### Branching Navigation

When the user navigates through a relationship, they are creating a branch in their navigation path:

```
Main path: Finding #1024
    │
    ├── Branch: Navigated to Evidence #512
    │   └── Returned to Finding #1024
    │
    └── Branch: Navigated to Recommendation #89
        ├── Navigated to Experiment AB-47
        │   └── Returned to Recommendation #89
        └── Returned to Finding #1024
```

Users can see their navigation branches in the history view. Branching is natural and does not require explicit user action.

---

## Cross-Experience Navigation

### Movement Rules

| Transition | Behavior | Context Preserved |
|---|---|---|
| **Assistant → Dashboard** | Dashboard opens in the same tab. Assistant conversation remains active. | Conversation ID, pinned artifacts |
| **Assistant → Artifact** | Artifact opens in a side panel (if quick inspection) or full page (if deep work). | Conversation reference ("Opened from conversation") |
| **Assistant → Command Palette** | Command palette opens over the assistant. No navigation occurs. | Conversation context |
| **Dashboard → Artifact** | Artifact opens in the module's list or detail view. | Dashboard time window, navigation source |
| **Dashboard → Conversation** | Conversation opens in the assistant workspace. | None (new conversation context) |
| **Artifact → Conversation** | Conversation opens in the assistant. Artifact is pinned as context. | Artifact ID, artifact evidence |
| **Artifact → Related Artifact** | Related artifact opens. Navigation source is shown in breadcrumbs. | Source artifact context |
| **Notification → Destination** | Destination opens in the appropriate view. | Notification context, source notification ID |
| **Search → Result** | Search result opens in the appropriate view. | Search query, search filters |
| **Timeline → Artifact** | Timeline event's artifact opens. | Timeline context, timestamp |
| **Command → Destination** | Command executes. Destination may be a page, inline result, or artifact. | Current workspace context |
| **Sidebar → Module** | Module root opens. | None (fresh module context) |

### Cross-Experience Rules

1. All cross-experience transitions preserve the user's active conversation.
2. Cross-experience transitions show a "Return to [source]" link in the destination's breadcrumb or navigation header.
3. Cross-experience transitions that lose context (e.g., starting a new conversation from an artifact) communicate the context change.
4. Cross-experience transitions are reversible. Back from a destination returns to the exact source state.
5. Cross-experience transitions within the same tool or module are preferred over cross-tool transitions. Users stay in their current workspace when possible.

---

## Search as Navigation

### Why Search Is Navigation

Search is not a separate activity from navigation. Search is navigation for users who know what they want but not where it is. The search bar and command palette are navigation interfaces.

### Search Navigation Types

| Type | Behavior | Example |
|---|---|---|
| **Natural language search** | User types a question or description. Search returns relevant artifacts with summaries. | "findings about latency last night" |
| **Structured search** | User filters by type, status, time, capability. | "type:finding severity:critical time:24h" |
| **Recent search** | User selects from recently viewed artifacts. | Recent artifacts list |
| **Saved search** | User selects from saved search configurations. | "My saved search: Critical findings daily" |
| **Semantic search** | User searches by meaning. Platform returns conceptually related artifacts. | "experiments related to retrieval optimization" |
| **Related objects** | User navigates to a search result and then to its related artifacts. | Finding → Evidence → Analytics |
| **Graph traversal** | User expands search results through lineage. | Finding → parent Evidence → sibling Artifacts |
| **Conversation search** | User searches within conversation history. | "find the conversation about experiment AB-47" |
| **Artifact search** | User searches for specific artifact types. | "config snapshot v143" |

### Search Navigation Rules

1. Search results are navigable. Each result is a link to the artifact's detail view.
2. Search results preserve the search context. The search query and filters are maintained.
3. Navigating from a search result shows "Back to search results" as a navigation option.
4. Search within a module affects that module's scope. Search from the command palette spans all modules.
5. Search is available from every screen. It is not a separate module — it is a navigation tool.

---

## Deep Linking

### Deep Link Philosophy

Every significant view in the platform is a stable, shareable destination. Deep links are permanent — they do not expire. They are context-aware — they restore the relevant state when opened.

### What Can Be Deep Linked

| Entity | URL Pattern | Restored State |
|---|---|---|
| **Conversation** | `/conversations/:id` | Full conversation history, pinned artifacts, last message |
| **Artifact** | `/artifacts/:type/:id` | Full artifact detail, evidence, lineage |
| **Finding** | `/findings/:id` | Finding detail, evidence timeline, related artifacts |
| **Recommendation** | `/recommendations/:id` | Recommendation detail, evidence, experiments |
| **Experiment** | `/experiments/:id` | Experiment detail, results, comparison state |
| **Decision** | `/decisions/:id` | Decision detail, approval chain, lineage |
| **Config Snapshot** | `/configuration/:id` | Snapshot detail, diff state, rollback info |
| **Report** | `/reports/:id` | Full report content |
| **Dashboard state** | `/?time=24h&capability=evidence` | Dashboard with filters applied |
| **Search state** | `/search?q=latency&type=finding` | Search results with query and filters |
| **Notification** | `/notifications/:id` | Notification detail, source artifact |
| **Timeline moment** | `/timeline?time=2024-03-24T02:00:00Z` | Timeline at the specified moment |

### Deep Link Rules

1. Deep links are stable across platform versions. A link created today still works in five years.
2. Deep links that point to deleted or archived content show a "Content not found" page with relevant alternatives.
3. Deep links from external sources (shared links, notifications, email) include a source parameter: `?source=notification`.
4. Deep links open in the platform's standard navigation frame (sidebar, top bar, breadcrumbs are visible).
5. Deep links for authenticated content redirect to login if the user is not authenticated, then continue to the destination.

---

## Navigation Recovery

### When Users Become Lost

| Situation | Recovery Path | User Action |
|---|---|---|
| **Where am I?** | Breadcrumb shows current location. Context indicator shows active module and entity. | Look at breadcrumb or page title. |
| **How did I get here?** | Navigation history shows the path taken. | Open history panel. |
| **How do I get back?** | Back button returns to previous context. "Return to [source]" link is in the breadcrumb. | Click Back or "Return to" link. |
| **I was investigating something — where did it go?** | Active conversation is preserved. Open conversations list shows active investigations. | Open assistant or conversations list. |
| **I can't find what I'm looking for.** | Search and command palette are available from every screen. | Type ⌘K and search. |
| **I opened a deep link and it's not what I expected.** | Breadcrumb shows "External link" entry point. Context is noted. | Use Back or navigate to related content. |
| **I closed something accidentally.** | Recently closed items are available in history. | Open recent list and reopen. |
| **I refreshed and lost my place.** | Session state is restored on page load. Active conversation, filters, and workspace are preserved. | Wait for restore. Brief loading indicator. |

### Recovery Rules

1. Recovery is passive — users do not need to take action unless they choose to.
2. Recovery information (breadcrumbs, history, context indicators) is always visible but never intrusive.
3. Users can actively recover by: using Back, opening history, searching, or asking the assistant.
4. Session recovery after refresh is automatic. The user returns to their previous state within 2 seconds.
5. When recovery is not possible (e.g., session expired), the platform explains what was lost and offers to restore what it can.

---

## AI Responsibilities

### The Assistant SHOULD

| Responsibility | Behavior |
|---|---|
| **Guide navigation** | When the user asks a question that implies navigation, the assistant provides a direct link: "Let me take you there: [Finding #1024]". |
| **Recommend destinations** | After a response, the assistant suggests related artifacts the user might want to navigate to. |
| **Preserve context** | When the assistant provides artifact links, it preserves the conversation context. Navigating to an artifact from an assistant response does not end the conversation. |
| **Open related artifacts** | When explaining an artifact, the assistant links to related artifacts: "This finding is related to Experiment AB-47. [Open experiment]". |
| **Resume investigations** | When the user returns to a conversation, the assistant summarizes the investigation state and offers to continue. |
| **Suggest next exploration** | After completing an investigation, the assistant suggests related areas: "Would you like to explore related findings, or review the experiments that followed?" |
| **Explain navigation context** | When the user navigates through the assistant, it clarifies what will happen: "I'll open the finding detail page. You can return to our conversation from there." |
| **Recover from navigation** | If the user returns to the assistant after navigating away, the assistant acknowledges the return and offers to continue. |

### The Assistant MUST NOT

| Prohibition | Behavior |
|---|---|
| **Teleport users without explanation** | Navigating the user to a different page without explaining why or where they are going. |
| **Lose context** | Providing a link that navigates the user away without a way to return. |
| **Break investigations** | Linking to an artifact that has no relationship to the current investigation without noting the context switch. |
| **Hide relationships** | Presenting an artifact without showing its relationships to the current context. |
| **Assume navigation intent** | Navigating the user to a detail view when they only wanted a summary. Default to inline summaries with "Open detail" as an action. |
| **Over-navigate** | Providing so many links that the user cannot decide where to go. Limit to 3-5 related navigation suggestions. |
| **Navigate without consent** | Automatically redirecting the user to a different page unless they explicitly click a link or confirm navigation. |
| **Discard conversation** | Navigating away from the assistant in a way that closes the conversation without warning. |

---

## Anti-Patterns

### Forbidden Navigation Behaviors

1. **Dead ends.** A page with no navigable links, no related artifacts, no suggested next steps, and no breadcrumbs. Every view has a way forward and a way back.

2. **Context loss.** Navigating to a new page and finding that the conversation is gone, filters are cleared, scroll position is reset, and the user must reconstruct their state.

3. **Page-first navigation.** Defaulting to full-page navigation for every action. Side panels, inline expansions, and conversation results should handle the majority of navigation.

4. **Broken history.** The back button does not return to the expected previous context. It returns to a different page or loses state.

5. **Unexpected redirects.** The user clicks a link expecting to go to one place but is redirected to another without explanation.

6. **Modal traps.** Navigation is blocked by an open modal that cannot be dismissed without completing an unrelated action.

7. **Lost investigations.** The user was in the middle of a multi-step investigation and navigated away, but there is no way to resume.

8. **Reset filters.** Navigating to a detail view and back clears all applied filters in the list view.

9. **Duplicate paths.** The same destination is reachable through 10 different paths that all behave differently, and the user cannot predict which path leads to which experience.

10. **No sense of place.** The user cannot tell where they are in the platform. The page title is generic. There is no breadcrumb. The sidebar does not highlight the current module.

11. **Infinite scroll without anchors.** A list view that loads infinitely but provides no way to save a position, share a position, or return to a previously viewed item.

12. **Navigation without feedback.** Clicking a link shows no loading state. The user wonders if anything happened.

13. **Side panel overuse.** Content that should be a full page is loaded in a side panel, giving the user insufficient room to work.

14. **Full page overuse.** Content that should be a quick side panel inspection opens as a full page, disrupting the user's flow.

15. **No breadcrumb.** The user has navigated three levels deep and cannot see how they got there or how to go up.

16. **Broken deep links.** Shared links that expire, break after platform updates, or do not restore the expected context.

17. **Cross-context navigation without warning.** Navigating from a conversation to an artifact in a different module without noting the context switch.

18. **Navigation that discards work.** Navigating away from a page causes unsaved form data, in-progress compositions, or active tool executions to be discarded.

19. **Silent navigation targets.** Links that look like they navigate within the platform but actually open external resources without warning.

20. **Non-deterministic navigation.** The same link sometimes navigates to a detail view and sometimes to a list view, depending on state the user cannot see.

21. **Navigation that requires reorientation.** After navigation, the sidebar, top bar, or layout changes significantly, requiring the user to reorient.

22. **History blindness.** No indication of how many steps back are available, no ability to jump to a specific history entry.

23. **Ignoring user role.** Navigation shows destinations the user cannot access without explanation.

24. **Overwhelming choices.** A page with 20+ navigable links, no prioritization, and no grouping. Related and suggested navigations are limited to 5-7 items.

25. **No escape from full-screen.** A full-screen view (experiment comparison, config diff) that offers no way to return to the standard navigation frame.

---

## Future Evolution

### Knowledge Graph Navigation

As the artifact graph grows:

1. Navigation becomes graph-native. Users navigate by exploring the artifact graph rather than by selecting from lists.
2. A graph explorer view allows users to pan, zoom, and traverse the full artifact relationship network.
3. The platform surfaces "paths" through the graph: common investigation routes that other users have taken.
4. Graph navigation is interactive — users can filter by relationship type, artifact type, time range, and status.

### Collaborative Workspaces

As teams collaborate:

1. Navigation includes presence indicators: which team members are viewing which artifacts.
2. Shared navigation history allows teams to retrace a colleague's investigation path.
3. Navigation to a shared workspace shows the team's current focus: "3 team members are investigating Finding #1024."
4. Collaborative navigation merges individual histories into shared investigation timelines.

### Spatial Navigation

As the platform evolves:

1. Three-panel navigation becomes available: primary content, related context, and investigation thread.
2. Users can "pin" navigation locations to spatial workspace regions.
3. Spatial memory (where things are on screen) becomes a navigation aid.
4. Users can define custom workspace layouts that persist across sessions.

### Voice Navigation

As voice interfaces mature:

1. Navigation via voice: "Go to finding #1024", "Show me the experiment results", "Go back to the conversation."
2. Voice navigation follows the same navigation principles. Commands are normalized and clarified.
3. Voice is treated as an input modality for the existing navigation system, not a separate navigation interface.
4. Voice navigation includes confirmation for high-cost actions: "Navigating to configuration. Continue?"

### Multi-Agent Exploration

As multiple AI agents operate:

1. Users can delegate navigation to agents: "Find all findings related to this experiment and summarize them."
2. Agents navigate the artifact graph on the user's behalf, returning curated paths.
3. Multi-agent navigation results include the navigation path taken: "Agent navigated: Finding #1024 → Evidence #512 → Experiment AB-47."
4. Users can review and modify agent navigation paths before following them.

### Predictive Navigation

As the platform learns from user behavior:

1. The platform predicts the user's likely next navigation destination and prefetches it.
2. The sidebar and command palette prioritize predicted destinations.
3. Predictive navigation is subtle — it never navigates without user intent, but it prepares the next view.
4. Users can disable predictive navigation if they prefer deterministic behavior.

### Engineering Memory

As the platform accumulates collective knowledge:

1. Navigation preserves institutional memory: "This is the same investigation path taken by Priya last month for a similar finding."
2. Users can navigate through "investigation patterns" — common navigation paths for specific artifact types.
3. The platform suggests navigation paths based on the current artifact and historical patterns.
4. Navigation becomes a form of organizational learning: the more the platform is used, the better it navigates.
