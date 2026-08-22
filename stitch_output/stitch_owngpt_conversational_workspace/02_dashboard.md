# Stitch Prompt: Dashboard

> Generate the Operator Dashboard for Own Platform.
>
> **Context:** This prompt assumes `stitch/00-master-context.md` as the foundation. Read it first.
>
> **Priority:** Sprint 1

---

## Design Goal

Generate the Home dashboard for Own Platform.

The dashboard answers one question in under 30 seconds:

> **"What needs my attention right now?"**

It is **not** a chart gallery. Every widget drives an action or a navigation. If a widget does not change operator behavior, it does not belong on the dashboard.

---

## Screen Information

| Property | Value |
|---|---|
| **Recipe** | A — Overview + Actions |
| **Route** | `/` |
| **Primary users** | AI Engineer, Platform Engineer, Engineering Manager |
| **Primary goal** | Assess platform health, see pending items, navigate to detail screens |
| **Layout** | Two-column (65/35) + full-width bottom section |

---

## Layout Structure

```
┌──────────────────────────────────────────────────────────────┐
│  Global Command Bar (sticky, full width)                     │
│  [🔍 Search... (⌘K)]  [24h ▼]  [+]  [🔔 3]  [👤]           │
├───────────────────────────────┬──────────────────────────────┤
│  Zone A (65%)                 │  Zone B (35%)                │
│                               │                              │
│  Platform Health Summary      │  Daily Brief                 │
│  ● ● ● ● ● ● ● ● ● ● ●     │  "3 findings, 2 experiments   │
│  12 of 12 healthy             │   completed, 1 config change"│
│                               │                              │
│  Attention Queue  (5)        │  Recent Config Changes       │
│  🔴 Finding: High latency     │  v142 — 2h ago ✅           │
│  🟡 Rec: Increase temperature │  v141 — 8h ago ✅           │
│  🟢 Exp: AB-47 complete      │                              │
│  ⏳ Config: v143 pending     │  Automation Status           │
│                               │  Last run: ✅ 12m ago       │
│  Critical Findings  (3)      │  Next: Daily eval in 4h     │
│  🔴 High query latency        │                              │
│  🔴 Retrieval failure        │  Recent Activity             │
│  🔴 Confidence < 60%         │  10:23 Config v142 applied  │
│                               │  09:15 Exp AB-47 done      │
│  Pending Recommendations (2) │                              │
│  92% · Increase temperature  │                              │
│  74% · Reduce top-k          │                              │
│                               │                              │
│  Running Experiments (2)     │                              │
│  🔄 AB-47 · 2h elapsed       │                              │
│  🔄 CD-12 · 30m elapsed     │                              │
│                               │                              │
├───────────────────────────────┴──────────────────────────────┤
│  All Capabilities (full-width, below fold)                   │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                       │
│  │Observe│ │Measure│ │Explain│ │Propose│                     │
│  │ ● ● ●│ │ ● ● ●│ │ ● ●  │ │ ●    │                     │
│  └──────┘ └──────┘ └──────┘ └──────┘                       │
└──────────────────────────────────────────────────────────────┘
```

---

## Section Specifications

### Global Command Bar
- **Position:** Sticky top. Full width. Always visible.
- **Elements** (left to right):
  - Search input with placeholder "Search artifacts, capabilities, configs... (⌘K)"
  - Time window dropdown (24h / 7d / 30d / custom)
  - "+" quick action button (opens create menu)
  - Notification bell with unread count badge
  - User avatar + dropdown menu

### Platform Health Summary
- **Position:** Top of Zone A.
- **Content:** Row of capability health pills. Each pill shows: capability name + status dot (green/yellow/red). Total: "X of Y healthy" indicator.
- **Interaction:** Click any pill → navigate to capability detail. Click "X of Y healthy" → navigate to OwnOps.
- **Empty:** "No capabilities registered."
- **Loading:** Row of skeleton pills (12 placeholders).
- **Error:** All pills show gray/unknown with retry.

### Attention Queue
- **Position:** Below health summary.
- **Content:** Unified list of actionable items (max 7). Each shows: type icon, title, severity badge, timestamp, 1-line summary. Sorted by severity then recency.
- **Interaction:** Click item → navigate to detail. "View all" → relevant list screen.
- **Empty:** "All clear. No items require your attention." with checkmark icon.
- **Loading:** Skeleton list with 5 rows.

### Daily Brief
- **Position:** Top of Zone B.
- **Content:** AI-generated summary. Date header. 3–5 bullet points. "Generated at" timestamp. Expandable.
- **Interaction:** Click bullet → navigate to relevant screen. Expand for full brief.
- **Empty:** "No daily brief yet. Complete an evaluation cycle to generate one."

### Critical Findings / Pending Recommendations / Running Experiments
- **Position:** Zone A, below Attention Queue (stacked vertically).
- **Content:** Each section shows header with count badge + list of items (max 5 per section).
- **Interaction:** Click item → navigate to detail. Click "View all" → filtered list screen. Quick-acknowledge inline.
- **Empty:** Contextual message per section.

### Recent Config Changes / Automation Status / Recent Activity
- **Position:** Zone B, below Daily Brief (stacked vertically).
- **Content:** Compact lists. Config: version + timestamp + changed by. Automation: last run + next run. Activity: chronological feed.
- **Interaction:** Click item → navigate to detail.

### All Capabilities
- **Position:** Full-width, below both columns. Below the fold.
- **Content:** Grid of capability cards (4 columns desktop, 2 tablet, 1 mobile). Each card: name, lifecycle stage badge, maturity badge, health dot, key metric.
- **Interaction:** Click card → navigate to capability detail.
- **Loading:** Skeleton grid (12 cards in 4×3 layout).

---

## Visual Design Constraints

### Colors
- **Zone A:** Slightly wider left column for attention-driving content.
- **Badges:** Severity-colored (red/orange/yellow/blue) with text label.
- **Health dots:** Green (healthy), yellow (degraded), red (down), gray (unknown).
- **Widget headers:** Medium weight text, secondary color.
- **Cards:** Surface background (`bg.secondary`). No border (use subtle shadow / elevation 1).
- **Command bar:** Surface background (`bg.primary` or secondary). Bottom border.

### Typography
- Widget headers: 14–15px, semibold.
- Item titles: 14px, regular, primary text.
- Item metadata: 12px, secondary text.
- Count badges: 12px, bold.
- Daily brief: 14px body, 12px secondary for metadata.

### Spacing
- Widget internal padding: 16–20px.
- Gap between widgets: 16px.
- Column gap: 24px.
- Item spacing within widget: 8–12px.
- Command bar height: 56px.

### Widget cards
- Each widget is a card with rounded corners (8px radius).
- No border. Use shadow/elevation 1.
- Header: title left + count badge right + optional "View all" link right.
- Content: list of items.
- Footer: optional "View all" link (if not in header).

---

## States to Design

### Loading state (initial)
- Command bar: static (always visible).
- Zone A: skeleton pills for health, skeleton list (5 rows) for attention queue, skeleton cards for sections.
- Zone B: skeleton text (4 lines) for brief, skeleton lists for config/auto/activity.
- Capability grid: skeleton grid (12 cards).

### Empty state (fresh platform)
- Health summary: "No capabilities registered. Configure your first capability to populate health data."
- Attention queue: "All clear. No items require your attention."
- All widgets show onboarding-friendly empty messages with next steps.

### Error state (widget-level)
- Failed widget shows inline error within card: icon + message + "Retry" link.
- Other widgets unaffected.
- Health summary: all pills gray. "Unable to reach health endpoint."
- Global failure: full-page error with "Check API connectivity" and retry.

### Single-capability degradation
- Health pill for that capability shows yellow/degraded.
- Attention queue includes related findings.
- Critical findings section shows relevant items.

---

## Responsive Adaptations

### Tablet (768–1024px)
- Single column stacked layout.
- Zone A widgets stack above Zone B widgets.
- Health summary becomes scrollable row.
- Daily brief collapses to expandable card.
- Capability grid: 2 columns.

### Mobile (< 768px)
- Single column, full-width cards.
- Health summary collapses to single line with expand.
- Attention queue shows top 3 items + "View X more."
- P1 widgets (findings, recs, experiments) show only counts as tappable cards.
- P2 widgets (config, automation, activity) hidden behind "More" accordion.
- Capability grid: 1 column.
- Command bar condenses: search becomes icon, time window hidden in overflow.

---

## Review Checklist

- [ ] Can an operator understand platform status within 30 seconds?
- [ ] Are actionable items above informational widgets?
- [ ] Does every widget have a clear drill-down destination?
- [ ] Are charts supporting decisions rather than dominating?
- [ ] Do empty states guide the user toward next steps?
- [ ] Does the dashboard feel like a command center, not a report?
- [ ] Would the user know what to do first?

---

## Deliverables

Generate:
1. **Dashboard default** — all widgets populated, above the fold visible
2. **Dashboard scrolled** — All Capabilities section below the fold
3. **Dashboard empty** — fresh platform with no data
4. **Dashboard error** — widget-level failures with retry
5. **Dashboard mobile** — single column, condensed widgets
6. **Dark mode variants** for each of the above
