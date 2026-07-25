# Stitch Prompt: OwnAnalytics

> Generate the analytics and reporting module for Own Platform.
>
> **Context:** This prompt assumes `stitch/00-master-context.md` as the foundation. Read it first.
>
> **Priority:** Sprint 3

---

## Design Goal

Generate OwnAnalytics — the analytics dashboard showing query patterns, retrieval effectiveness, routing accuracy, user behavior, and trends.

OwnAnalytics answers:

> **"How is the system being used and how well is it performing?"**

It is a read-only investigation surface. Insights here drive configuration changes in OwnConfig and experiments in OwnLab.

---

## Screen Information

| Property | Value |
|---|---|
| **Recipe** | A — Overview + Actions (overview) + B — Collection + Inspector (category detail) |
| **Routes** | `/analytics` and `/analytics/:category` |
| **Primary users** | AI Engineer, ML Engineer |
| **Primary goal** | View aggregate analytics across platform dimensions |

---

## Layout Structure

### Analytics Overview (`/analytics`)

```
┌──────────────────────────────────────────────────────────────┐
│  Header: Analytics · [Time window] [Export]                  │
├──────────────────────────────────────────────────────────────┤
│  Summary Cards (2×N grid)                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Query        │ │ Retrieval    │ │ Routing      │        │
│  │ Analytics    │ │ Analytics    │ │ Analytics    │        │
│  │ 12.4K total  │ │ 94.2% hit   │ │ 97.1% acc.  │        │
│  │ ▲ 8% vs prev │ │ ▼ 2% vs prev│ │ — 0% vs prev│        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│  ┌──────────────┐ ┌──────────────┐                          │
│  │ Behavior     │ │ Trends       │                          │
│  │ Analytics    │ │ Overview     │                          │
│  │ 342 users    │ │ +12% growth  │                          │
│  │ ▲ 5% vs prev│ │ ▲ 3% vs prev│                          │
│  └──────────────┘ └──────────────┘                          │
├──────────────────────────────────────────────────────────────┤
│  KPI Sparklines (below summary cards)                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Total Queries · Avg Latency · Error Rate · Active Users│ │
│  │ (sparklines across time window)                        │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Analytics Category Detail (`/analytics/:category`)

```
┌──────────────────────────────────────────────────────────────┐
│  Breadcrumbs: Analytics > Query Analytics                    │
│  Header: Query Analytics · [Time window] [Compare period]    │
├──────────────────────────────────────────────────────────────┤
│  Filter Bar                                                  │
│  [Metric ▼] [Segment ▼] [Chart type ▼]                      │
├──────────────────────────────────────────────────────────────┤
│  Main Chart (prominent)                                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Bar/Line chart of selected metric over time           │ │
│  │  (interactive: hover, zoom, brush)                     │ │
│  └────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│  Data Table (below chart)                                    │
│  ┌──────────┬────────┬────────┬────────┬──────────┐        │
│  │ Segment  │ Queries│ Avg    │ P95    │ Error    │        │
│  │          │        │ Latency│ Latency│ Rate     │        │
│  ├──────────┼────────┼────────┼────────┼──────────┤        │
│  │ OwnGPT   │ 8,234  │ 1.2s   │ 2.8s   │ 1.2%     │        │
│  │ API      │ 3,102  │ 340ms  │ 890ms  │ 0.4%     │        │
│  │ Batch    │ 1,024  │ 4.5s   │ 12s    │ 2.1%     │        │
│  └──────────┴────────┴────────┴────────┴──────────┘        │
└──────────────────────────────────────────────────────────────┘
```

---

## Sections Detail

### Summary Cards (Overview)
- **Content:** 5 category cards (Query, Retrieval, Routing, Behavior, Trends). Each shows: category name, key metric, change indicator (▲/▼/—) vs prior period.
- **Interaction:** Click card → navigate to category detail. Hover for sparkline preview.

### KPI Sparklines
- **Content:** Row of compact sparklines: total queries, avg latency, error rate, active users.
- **Interaction:** Hover for exact values.

### Category Detail — Filter Bar
- **Content:** Metric selector, segment filter, chart type toggle, time window.
- **Behavior:** All controls update the main chart and data table. Preserved in URL.

### Category Detail — Main Chart
- **Types:** Line (trends), bar (comparison), stacked (composition), area (volume).
- **Interaction:** Hover for tooltip. Click legend to toggle series. Brush to zoom. Download as PNG.

### Category Detail — Data Table
- **Content:** Tabular data backing the chart. Sortable columns. Paginated.
- **Interaction:** Click row to drill into segment detail. Export as CSV.

---

## States

### Loading (overview)
- Summary card skeleton grid (5 cards).
- Sparkline skeleton row.

### Loading (detail)
- Chart skeleton with axis labels.
- Table skeleton with 5 rows.

### Empty (no data)
- "Analytics data will appear once the system processes user interactions."
- Estimated time until first data point.

### Error
- Per-card/chart inline error with retry.
- "Failed to load analytics data. [Retry]"

---

## Deliverables

Generate:
1. **Analytics Overview** — summary cards with sparklines
2. **Analytics Category Detail** — main chart with filter bar and data table
3. **Analytics Overview empty** — no data yet
4. **Analytics on mobile** — stacked cards, full-width charts
5. **Dark mode variants** for each
