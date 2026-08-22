# Stitch Prompt: OwnOps

> Generate the Operations Console for Own Platform.
>
> **Context:** This prompt assumes `stitch/00-master-context.md` as the foundation. Read it first.
>
> **Priority:** Sprint 2

---

## Design Goal

Generate OwnOps — the power user workspace for engineering investigation.

OwnOps is where engineers go when they need **depth**. It should feel like a fusion of:

- **Grafana** — health grids, metric charts, time controls
- **Linear** — clean list/detail, fast filters, keyboard-first
- **GitHub** — lineage graphs, diff views, audit trails
- **Cursor Inspector** — developer telemetry, raw data inspection

OwnOps complements OwnGPT. The assistant handles 80% of understanding; OwnOps handles the remaining 20% of deep work. All engineering telemetry hidden in OwnGPT belongs here.

---

## Screen Information

| Property | Value |
|---|---|
| **Recipe** | H — Monitoring + Status (primary) + B — Collection + Inspector (detail) |
| **Route** | `/operations` and `/operations/:capabilityId` |
| **Primary users** | Platform Engineer, DevOps Engineer |
| **Primary goal** | Monitor health, inspect metrics, investigate issues, view telemetry |

---

## Layout Structure

### OwnOps Control Plane (`/operations`)

```
┌──────────────────────────────────────────────────────────────┐
│  Header: [← Back] OwnOps · [Capability filter] [Time window]│
├──────────────────────────────────────────────────────────────┤
│  Status Bar (sticky)                                         │
│  ● 12 healthy  ◯ 2 degraded  ◆ 1 down                       │
├──────────────────────────────────┬───────────────────────────┤
│                                  │                           │
│  Health Grid                     │  Detail Panel             │
│  (4 columns desktop)             │  (selected capability)    │
│                                  │                           │
│  ┌──────┐ ┌──────┐ ┌──────┐    │  — Metric charts          │
│  │ ●●   │ │ ●●   │ │ ◯    │    │  — Latency p50/p95/p99    │
│  │Runtime│ │Ledger │ │Evidence│  │  — Error rate             │
│  └──────┘ └──────┘ └──────┘    │  — Throughput              │
│  ┌──────┐ ┌──────┐             │  — Recent events           │
│  │ ◆    │ │ ●●   │             │  — Related findings        │
│  │Analytics│ │Propose│         │  — Dependency graph        │
│  └──────┘ └──────┘             │                           │
│                                  │                           │
├──────────────────────────────────┴───────────────────────────┤
│  Telemetry section (full width, below fold)                  │
│  — Raw metrics table                                         │
│  — Recent logs                                               │
│  — Active alerts                                             │
└──────────────────────────────────────────────────────────────┘
```

### Capability Health Detail (`/operations/:capabilityId`)

```
┌──────────────────────────────────────────────────────────────┐
│  Breadcrumbs: OwnOps > Capability Name                       │
│  Header: Capability Name · Status badge · [Back] [Settings] │
├──────────────────────────────────────────────────────────────┤
│  Metric charts (2×2 grid)                                    │
│  ┌─────────────┐  ┌─────────────┐                            │
│  │ Latency p95 │  │ Error Rate  │                            │
│  │ (line chart)│  │ (line chart)│                            │
│  └─────────────┘  └─────────────┘                            │
│  ┌─────────────┐  ┌─────────────┐                            │
│  │ Throughput  │  │ Health Score│                            │
│  │ (bar chart) │  │ (gauge)     │                            │
│  └─────────────┘  └─────────────┘                            │
├──────────────────────────────────────────────────────────────┤
│  Activity Timeline                                            │
│  10:23 ● Health degraded — latency spike                     │
│  09:15 ● Config updated — v142 deployed                     │
│  08:44 ● Finding created — high query latency               │
├──────────────────────────────────────────────────────────────┤
│  Related Artifacts                                            │
│  — Findings (3) · Recommendations (1) · Config changes (2)   │
└──────────────────────────────────────────────────────────────┘
```

---

## Where Engineering Telemetry Lives

OwnOps is where all the details **hidden** in OwnGPT become visible:

| Hidden in OwnGPT | Visible in OwnOps |
|---|---|
| Confidence scores | Per-claim confidence with breakdown |
| Grounding method | Source documents, retrieval strategy |
| Analysis pipeline | Full chain of tool invocations |
| Execution timer | Duration per step, total latency |
| Token counts | Prompt size, response size, cost |
| Internal reasoning | Raw AI response, prompt preview |
| Model info | Model name, version, parameters |
| Tool internals | Full input/output per tool call |

---

## Sections Detail

### Health Grid
- **Content:** Grid of capability cards. Each card: name + health dot (green/yellow/red/down) + key metric + lifecycle stage badge.
- **Filter:** By status (all/healthy/degraded/down) or lifecycle stage.
- **Interaction:** Click card → select and show detail panel. Double-click or "Open" → navigate to detail page.
- **Loading:** Skeleton grid (12 placeholder cards in 4×3 layout).

### Detail Panel
- **Content (context-dependent):** Metric sparklines, recent events (last 24h), related artifacts, dependency links.
- **Behavior:** Updates when selection changes. Preserves scroll position between selections. Pin-able.

### Metric Charts
- **Chart types:** Line (trends), bar (comparison), gauge (single target), sparkline (compact).
- **Time controls:** 1h, 6h, 24h, 7d, 30d, custom range. Brush range selection.
- **Interaction:** Hover for exact values. Click point to see related events. Drag to zoom.
- **Loading:** Chart skeleton with axis placeholders. No spinner.

### Activity Timeline
- **Content:** Chronological feed of events for the capability. Each event: time + icon + title + summary.
- **Filter:** By event type (config, finding, health, deployment).
- **Interaction:** Click event → navigate to relevant detail or show inline expansion.
- **Loading:** Timeline skeleton with event lines at realistic spacing.

---

## States

### Loading
- Health grid: skeleton cards with status placeholder shapes.
- Detail panel: metric chart skeletons + timeline placeholders.
- Charts: skeleton with axis labels (no data line).

### Empty (no capabilities)
- "No capabilities registered. The platform is running but no capabilities have been configured."
- Onboarding guidance for registering the first capability.

### Empty (no data for time range)
- "No data available for the selected time window. Try a different range."
- Time range selector remains active.

### Error (per-capability)
- Individual card shows gray/unknown status. "Data unavailable."
- Other cards unaffected.
- Detail panel shows "Failed to load metrics" with retry.

### Degraded
- Card shows yellow status with degraded indicator.
- Detail panel highlights relevant metrics and related findings.
- Timeline shows recent degradation events.

---

## Visual Design Constraints

- **Colors:** Status dots use platform palette (green/yellow/red/gray). Charts use chart color tokens (colorblind-safe).
- **Typography:** Chart labels: 12px secondary. Metric values: 20–24px bold for key metrics. Card titles: 14px semibold.
- **Spacing:** Card grid: 16px gap. Chart panels: 20px internal padding. Timeline: 12px between events.
- **Charts:** Minimal grid lines. Left-aligned y-axis labels. Time-based x-axis. Consistent height across charts in same row.
- **Cards:** No border (use elevation 1). Status dot top-right or left of name.

---

## Deliverables

Generate:
1. **OwnOps Control Plane** — health grid with detail panel, one capability selected
2. **OwnOps with degraded capability** — yellow status card, detail panel shows alerts
3. **Capability Health Detail** — full metric charts, timeline, related artifacts
4. **OwnOps empty state** — no capabilities registered
5. **OwnOps mobile** — single column, stacked cards
6. **Dark mode variants** for each
