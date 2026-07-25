# Notifications

> How the platform communicates asynchronous state changes to operators.
>
> Every notification is a traceable artifact.
>
> **State Transition → Notification → Navigation → Conversation → Artifact**

---

## Purpose

Notifications inform operators about events that occurred outside their current context. They bridge the gap between platform automation and human awareness.

The notification system follows a simple chain:

1. **State Transition** — Something changed in the platform state model.
2. **Notification** — The change is recorded as a notification artifact.
3. **Navigation** — The notification links to the relevant screen.
4. **Conversation** — The notification can be discussed in conversation context.
5. **Artifact** — The notification is itself an immutable artifact with lineage.

This chain ensures every notification is predictable, traceable, and actionable.

---

## Notification Philosophy

### State transitions drive notifications
Every notification is triggered by a state transition in the platform's state model (13). If no state transition occurred, no notification should be generated. This prevents notification noise and ensures every alert has a verifiable cause.

### Actionable by default
Every notification must enable a clear action: navigate to the relevant screen, acknowledge, dismiss, or escalate. Notifications that say "something happened" without enabling action are noise. Noise erodes trust.

### Context-preserving
A notification carries enough context to understand what happened without requiring immediate navigation. Title, summary, severity, timestamp, and source are always included. "Click to find out" is not acceptable.

### Aggregated, not multiplied
Related notifications are grouped. Ten findings from the same evaluation cycle become one notification with a count, not ten individual alerts. Aggregation respects the operator's attention budget.

### Rate-limited
Notification volume is bounded. If the same event type triggers more than N notifications in a time window, they consolidate into a summary notification. Operators are never flooded.

### User-controllable
Users control which notification types they receive, at what threshold, and through which channel. Notification preferences are stored as user settings artifacts (Recipe J).

---

## Notification Lifecycle

```
Event Occurs
    ↓
State Transition
    ↓
Notification Created (id, timestamp, lineage)
    ↓
Delivery (in-app panel, toast, conversation)
    ↓
User Interaction (navigate, acknowledge, dismiss, escalate)
    ↓
Notification Archived or Resolved
    ↓
Audit Trail (immutable record)
```

### Lifecycle states

| State | Description |
|---|---|
| Created | Notification artifact generated and stored |
| Delivered | Sent to the delivery channel |
| Read | User has seen the notification (viewed in panel) |
| Acknowledged | User has explicitly acknowledged receipt |
| Navigated | User clicked through to the related screen |
| Dismissed | User dismissed without action |
| Resolved | The underlying state transition has been resolved |
| Archived | Moved to historical storage |
| Aggregated | Grouped into a parent notification |
| Expired | Auto-dismissed after time-to-live |

---

## Notification Types

### By source

| Type | Trigger | Example |
|---|---|---|
| Finding | New finding created (severity ≥ threshold) | "High query latency detected in Evidence Engine" |
| Recommendation | New recommendation created | "Recommendation R-42: Increase temperature to 0.8" |
| Experiment | Experiment status change | "Experiment AB-47 completed — results ready for review" |
| Decision | Decision required or made | "Config v143 pending approval" |
| Config | Configuration change | "Config v142 applied to production" |
| Automation | Job status change | "Daily evaluation job failed" |
| Health | Health status change | "Evidence Engine health degraded" |
| Approval | Approval required or granted | "Temperature increase approved by @alice" |

### By severity

| Level | Visual | Behavior |
|---|---|---|
| Critical | Red, icon, persistent banner | Requires acknowledgment; cannot be dismissed without action |
| High | Orange/amber, icon, persistent in panel | Stays in panel until acknowledged or resolved |
| Medium | Blue/info, icon, standard | Normal priority; auto-archived after time-to-live |
| Low | No icon, subtle | Silent; grouped into daily summary |
| System | Gray, no notification | Logged to audit; no user-facing notification |

### By delivery mode

| Mode | Description | Use |
|---|---|---|
| Toast | Temporary popup, auto-dismisses | Medium urgency, non-critical updates |
| Banner | Persistent bar at top of screen | Critical alerts, system-wide announcements |
| Panel | Notification list in slide-over | All notifications, organized by recency |
| Badge | Count on bell icon | Unread count — always visible |
| Conversation | Notification appears in conversation | When user is actively working in conversation |
| Daily brief | Aggregate notification in daily summary | Low-priority events, end-of-day review |

---

## Notification Structure

Every notification is an artifact with the following structure:

```
{
  id: UUID,
  type: "finding" | "recommendation" | "experiment" | "decision" | "config" | "automation" | "health" | "approval",
  severity: "critical" | "high" | "medium" | "low" | "system",
  state: "created" | "delivered" | "read" | "acknowledged" | "navigated" | "dismissed" | "resolved" | "archived",
  title: string,
  summary: string,
  source: { type: string, id: UUID },
  lineage: { parent?: UUID, children?: UUID[], related?: UUID[] },
  timestamp: ISO8601,
  ttl: duration,
  actions: ["navigate", "acknowledge", "dismiss", "escalate"],
  metadata: { ... }
}
```

### Required fields
- **id** — Unique identifier (immutable)
- **type** — Notification category
- **severity** — Urgency level
- **state** — Current lifecycle state
- **title** — Human-readable title (max 80 chars)
- **summary** — One-line explanation (max 200 chars)
- **source** — Reference to the state transition that triggered it
- **lineage** — Parent notification (if aggregated) and related notifications
- **timestamp** — When the state transition occurred
- **ttl** — Time after which the notification auto-archives

---

## Notification Panel

The Notification Panel is the primary interface for reviewing notifications. It is a slide-over panel (Recipe I — Search + Explore variant) triggered by the bell icon in the global command bar.

### Panel layout

```
┌──────────────────────────────────┐
│  Notifications  [Mark all read]  │
├──────────────────────────────────┤
│  [All] [Unread] [Critical]       │
├──────────────────────────────────┤
│                                  │
│  Today                           │
│  ┌────────────────────────────┐ │
│  │ 🔴 Finding: High latency   │ │
│  │ Evidence Engine · 2m ago   │ │
│  │ Query latency p95 > 2s     │ │
│  └────────────────────────────┘ │
│  ┌────────────────────────────┐ │
│  │ 🟡 Exp: AB-47 complete     │ │
│  │ Results ready for review   │ │
│  │ · 15m ago                  │ │
│  └────────────────────────────┘ │
│                                  │
│  Yesterday                       │
│  ┌────────────────────────────┐ │
│  │ ✅ Config v142 applied     │ │
│  │ 2 changes · 1d ago         │ │
│  └────────────────────────────┘ │
│                                  │
│  [View all notifications →]     │
└──────────────────────────────────┘
```

### Interaction model
- Click notification → navigate to the relevant screen (deep link)
- Click "Mark all read" → sets all visible notifications to "read"
- Filter tabs: All, Unread, Critical
- Grouped by date (Today, Yesterday, This Week, Earlier)
- Swipe (mobile) or hover action (desktop) to dismiss individual notifications
- Empty state: "No notifications. All clear."

---

## Notification Behavior

### Toast notifications

| Property | Value |
|---|---|
| Position | Top-right (LTR), top-left (RTL) |
| Max visible | 3 simultaneous |
| Auto-dismiss | Medium/Low: 5s; High: persistent; Critical: persistent |
| Stack | New toasts push existing ones down |
| Interaction | Click → navigate; hover → pause auto-dismiss |
| Exit | Slide out right, 200ms |

### Banner notifications

| Property | Value |
|---|---|
| Position | Below global command bar, full width |
| Count | 1 at a time (stacking: latest replaces previous) |
| Auto-dismiss | Never (requires explicit dismiss) |
| Interaction | Click → navigate; dismiss → archive |
| Animation | Slide down from top, 300ms |

### Badge updates

| Property | Value |
|---|---|
| Position | Bell icon in global command bar |
| Count | Unread notification count |
| Max display | 99+ (count capped) |
| Update | Animated count change (scale, 100ms) |
| Clear | Marking all as read in panel clears badge |

---

## Aggregation Rules

| Condition | Behavior |
|---|---|
| Same type, same source, within 5 minutes | Group into single notification: "3 new findings from Evidence Engine" |
| Same severity, any type, within 1 minute | Group into summary: "5 high-severity events in the last minute" |
| More than 10 notifications of same type in 1 hour | Group into digest: "12 findings today — 3 critical, 7 high, 2 medium" |
| Same notification sent to multiple channels | Only one delivery record (deduplication by notification ID) |

**Aggregation respects:** Each aggregated notification links to the individual events. The operator can expand an aggregated notification to see individual items.

---

## Notification → Navigation

Every notification maps to exactly one navigation target.

| Notification type | Navigation target | Deep link |
|---|---|---|
| Finding | Finding Detail | `/findings/:id` |
| Recommendation | Recommendation Detail | `/recommendations/:id` |
| Experiment completed | Experiment Detail | `/experiments/:id` |
| Experiment needs review | Experiment Detail (results panel) | `/experiments/:id?panel=results` |
| Decision required | Decision Detail or Config Snapshot Detail | `/decisions/:id` or `/configuration/:id` |
| Config applied | Config Snapshot Detail | `/configuration/:id` |
| Job failed | Job Detail (logs panel) | `/automation/jobs/:id?panel=logs` |
| Health degraded | Capability Health Detail | `/operations/:capabilityId` |
| Approval granted | Decision Detail | `/decisions/:id` |

### Navigation behavior
- Clicking a notification navigates to the target screen.
- The notification is marked as "read" on navigation.
- Back navigation returns to the previous screen (not the notification panel).
- If the notification panel was open when clicking, it closes on navigation.

---

## Notification → Conversation

Notifications integrate with the conversation workspace:

| Interaction | Behavior |
|---|---|
| Share notification to conversation | Click "Share" → notification summary appears as a message in conversation |
| Conversation triggers notification | State transition from a command or tool invocation generates a notification |
| Context from notification | Navigating from notification preserves notification context in conversation |
| Discuss notification | "About the finding from 2 minutes ago..." references the notification ID |

### Conversation notification delivery
When the user is actively in a conversation, notifications may appear in the conversation thread instead of (or in addition to) the notification panel. This respects the principle that conversation is the primary interaction surface.

- **Low urgency:** Silent — appears as a notification artifact in the conversation thread
- **Medium urgency:** Inline — appears as a non-disruptive card
- **High urgency:** Prompt — appears as an interrupt with acknowledgment required

---

## Notification → Artifact

Every notification is an artifact. This means:

- Notifications have IDs, timestamps, version, and lineage.
- Notifications are immutable once created.
- Notifications are stored in the learning ledger.
- Notifications can be referenced by other artifacts.
- Notifications appear in the Artifact Explorer.

### Lineage
```
State Transition (event)
    ↓
Notification (artifact)
    ↓
User Action (navigate, acknowledge, dismiss)
    ↓
Audit Log Entry (artifact)
```

This lineage ensures every notification is traceable to its cause and its outcome.

---

## Notification Preferences

Users control notification behavior through settings (Recipe J).

| Preference | Options | Default |
|---|---|---|
| Types | Per-type toggle (finding, recommendation, experiment, etc.) | All enabled |
| Severity thresholds | Minimum severity for notification (all, ≥high, ≥medium, ≥low) | ≥medium |
| Delivery channels | In-app, conversation, email, slack (future) | In-app only |
| Quiet hours | Start/end time, timezone | None |
| Digest frequency | Real-time, hourly, daily, never | Real-time for ≥high, daily for ≤medium |
| Aggregation preference | Aggregated or individual | Aggregated |

Preferences are stored as User Settings artifacts and are user-specific.

---

## Notification Anti-Patterns

| Anti-pattern | Problem | Remedy |
|---|---|---|
| Notification for every state change | Noise; operators disable notifications | Only notify on meaningful state transitions (configured by type) |
| Missing navigation target | "Something happened — figure out where" | Every notification must have a navigation target |
| No aggregation | "10 new findings" × 10 cycles = 100 notifications | Group same-type events; use severity-based aggregation |
| No user control | All notifications on or all off | Granular per-type, per-severity controls |
| Notifications without lineage | No traceability to the state transition that triggered it | Every notification records its source state transition |
| Auto-dismiss for critical alerts | Operator misses critical information | Critical notifications require explicit acknowledgment |
| Notification as the only channel | Operator may not be looking at the platform | Use additional channels for critical alerts (future) |
| Duplicate notifications | Same event generates multiple notifications | Deduplicate by notification ID |
| Notification without context | "Error occurred" (what error? where?) | Every notification includes title, summary, severity, timestamp, and source |
| Notification panel is hard to find | Bell icon is small; panel is undiscoverable | Bell icon is prominent in global command bar; badge shows unread count |

---

## State Model for Notifications

Notifications follow the platform's universal state model (13):

```
Created → Delivered → Read → Acknowledged → Archived
                              ↓
                         Navigated → Resolved → Archived
                              ↓
                         Dismissed → Archived
                              ↓
                         Expired → Archived
```

| Transition | Trigger | Behavior |
|---|---|---|
| Created → Delivered | State transition event processed | Notification artifact created and queued for delivery |
| Delivered → Read | User opens notification panel | Marked as read; badge count decreases |
| Read → Acknowledged | User clicks "Acknowledge" | Explicit acknowledgment recorded |
| Read → Navigated | User clicks notification | Opens target screen; marks as navigated |
| Navigated → Resolved | Underlying state resolved | Notification marked as resolved |
| Read → Dismissed | User dismisses | Notification archived without action |
| Any → Expired | TTL exceeded | Auto-archived; removed from active panel |
| Any → Archived | Manual archive or TTL expiry | Moved to historical storage |

---

## Relationship to Other Documents

| Document | Relationship |
|---|---|
| 13-state-model.md | Notifications are triggered by state transitions |
| 09-conversation-lifecycle.md | Notifications integrate with conversation thread |
| 10-artifact-interactions.md | Notifications are artifacts with lineage and lifecycle |
| 14-navigation-behavior.md | Every notification maps to a navigation target |
| 17-design-system-architecture.md | Notification primitives (toast, badge, banner, panel) |
| 18-visual-language.md | Notification severity colors and iconography |
| 19-motion-feedback.md | Notification entrance, attention, and exit animations |
| 16-screen-recipes.md | Notification panel follows Recipe I (Search + Explore) |

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-07-25 | Architecture | Initial notification architecture |
