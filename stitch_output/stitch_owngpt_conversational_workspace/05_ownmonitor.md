# Stitch Prompt: OwnMonitor

> Generate the observability and health monitoring module for Own Platform.
>
> **Context:** This prompt assumes `stitch/00-master-context.md` as the foundation. Read it first.
>
> **Priority:** Sprint 2

---

## Design Goal

Generate OwnMonitor — the continuous evaluation dashboard and evaluation detail screens.

OwnMonitor answers:

> **"How is my AI system performing?"**

It shows evaluation scores over time, per-capability breakdowns, trends, and generated findings. It is read-only — insights here drive action in OwnOps and OwnLab.

---

## Screen Information

| Property | Value |
|---|---|
| **Recipe** | A — Overview + Actions (CE Dashboard) + D — Timeline + Detail (Evaluation Detail) |
| **Route** | `/evaluation` and `/evaluation/:id` |
| **Primary users** | AI Engineer, ML Engineer, Engineering Manager |
| **Primary goal** | View evaluation scores, trends, and drill into per-capability detail |

---

## Layout Structure

### CE Dashboard (`/evaluation`)

```
┌──────────────────────────────────────────────────────────────┐
│  Header: Continuous Evaluation · [Time window] [Compare]     │
├──────────────────────────────────────────────────────────────┤
│  Score Gauge (prominent)                                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │          Overall Score: 87/100                          │ │
│  │          ╭──────────────────╮                           │ │
│  │          │     87           │                           │ │
│  │          │    Score        │                           │ │
│  │          ╰──────────────────╯                           │ │
│  │          ▲ 2 pts vs last window                         │ │
│  └────────────────────────────────────────────────────────┘ │
├──────────────────────────────────┬───────────────────────────┤
│  Score Trend                     │  Latest Report Summary    │
│  (line chart, last N windows)   │  Report #847             │
│                                  │  Generated: 2h ago       │
│                                  │  15 capabilities scored  │
│                                  │                           │
├──────────────────────────────────┴───────────────────────────┤
│  Capability Breakdown Table                                  │
│  ┌─────────┬───────┬──────────┬──────────┬──────────┐       │
│  │ Capability│ Score│ Change   │ Trend    │ Findings │       │
│  ├─────────┼───────┼──────────┼──────────┼──────────┤       │
│  │ Runtime │ 92    │ +1      │ ▲        │ 0        │       │
│  │ Ledger  │ 88    │ -3      │ ▼        │ 2        │       │
│  │ Evidence│ 74    │ -12     │ ▼▼       │ 5        │       │
│  │ ...     │ ...   │ ...     │ ...      │ ...      │       │
│  └─────────┴───────┴──────────┴──────────┴──────────┘       │
└──────────────────────────────────────────────────────────────┘
```

### Evaluation Detail (`/evaluation/:id`)

```
┌──────────────────────────────────────────────────────────────┐
│  Breadcrumbs: Evaluation > Report #847                       │
│  Header: Evaluation Report · Window: Mar 24 10:00 UTC        │
├──────────────────────────────────────────────────────────────┤
│  Capability Metrics (full detail for selected capability)    │
│  ┌─────────────┐  ┌─────────────┐                            │
│  │ Score: 74    │  │ Change: -12 │                            │
│  │ (gauge)      │  │ (indicator) │                            │
│  └─────────────┘  └─────────────┘                            │
│  ┌─────────────┐  ┌─────────────┐                            │
│  │ Trend (7d)  │  │ Metric      │                            │
│  │ (sparkline) │  │ breakdown   │                            │
│  └─────────────┘  └─────────────┘                            │
├──────────────────────────────────────────────────────────────┤
│  Findings Generated in This Window                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 🔴 High query latency · Evidence Engine · 20m ago     │ │
│  │ 🟡 Retrieval accuracy dropped · Ledger · 20m ago      │ │
│  └────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│  Raw Report Link                                             │
│  [View full report artifact →]                               │
└──────────────────────────────────────────────────────────────┘
```

---

## Sections Detail

### Score Gauge
- **Position:** Top, prominent. Centered or left-aligned.
- **Content:** Large score number (e.g., 87/100), change indicator (▲ +2), color-coded by score range (green ≥80, yellow ≥60, red <60).
- **Interaction:** None (display only). Hover for exact timestamp.

### Score Trend Chart
- **Content:** Line chart of overall score over last N evaluation windows. X-axis: time. Y-axis: score (0–100).
- **Interaction:** Hover for data point values. Click point → jump to that evaluation's detail. Brush to zoom time range.

### Capability Breakdown Table
- **Content:** Table with columns: capability name, score, change vs prior window, trend indicator (▲/▼/—), findings count.
- **Interaction:** Click row → navigate to evaluation detail for that capability. Sort by any column. Filter by score range.
- **Empty:** "No evaluation data yet. The first evaluation will run automatically."
- **Loading:** Table skeleton with 8 rows.

### Evaluation Detail Sections
- **Metric cards:** Key metrics for the capability (score, change, trend).
- **Findings list:** Findings generated during this evaluation window. Click to navigate to Finding Detail.
- **Raw report:** Link to the full evaluation report artifact.

---

## States

### Loading (dashboard)
- Score gauge: circle skeleton with number placeholder.
- Trend chart: line chart skeleton.
- Table: skeleton rows (8).

### Empty (no evaluations)
- "No evaluation data yet. The first evaluation will run automatically."
- Estimated time until first evaluation shown.
- Dashboard framework visible — sections show empty state messages.

### Error
- Per-widget inline error with retry.
- Score gauge: "Score unavailable."
- Trend chart: "Trend data unavailable."
- Table: "Failed to load capability data. [Retry]"

### Partial data
- Some capabilities scored, others pending.
- Pending capabilities show "Pending" badge.
- Score gauge shows score for completed capabilities only.

---

## Visual Design Constraints

- **Gauge:** Circular or semi-circular. Color fills by score range. Score number centered, large (48px).
- **Table:** Clean, minimal borders. Row hover highlight. Trend indicators: ▲ green, ▼ red, — gray.
- **Charts:** Line chart (score trend). No grid lines. Smooth curves. Data point dots on hover.
- **Colors:** Score colors: green ≥80, amber 60–79, red <60. Trend: green positive, red negative, gray flat.
- **Typography:** Score number: 48px bold. Capability name: 14px medium. Score value: 14px tabular.
- **Spacing:** Gauge section: 32px padding. Table: 12px row height.

---

## Deliverables

Generate:
1. **CE Dashboard** — score gauge, trend chart, breakdown table populated
2. **CE Dashboard empty** — no evaluations yet
3. **Evaluation Detail** — capability metrics, findings list, raw report link
4. **CE Dashboard with degraded score** — yellow/red gauge, downward trend
5. **Dark mode variants** for each
