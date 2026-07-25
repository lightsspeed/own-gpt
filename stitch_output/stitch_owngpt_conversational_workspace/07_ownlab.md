# Stitch Prompt: OwnLab

> Generate the experiments and evaluation module for Own Platform.
>
> **Context:** This prompt assumes `stitch/00-master-context.md` as the foundation. Read it first.
>
> **Priority:** Sprint 3

---

## Design Goal

Generate OwnLab — the experiments workspace where engineers design, run, and analyze A/B tests and configuration experiments.

OwnLab should feel like a combination of:

- **Vercel** — clean experiment overview, clear status indicators
- **Optimizely** — variant comparison, metric tracking, winner declaration
- **Linear** — task-like experiment cards, filterable lists

---

## Screen Information

| Property | Value |
|---|---|
| **Recipe** | B — Collection + Inspector (list + detail) + F — Editor + Preview (designer) |
| **Routes** | `/experiments`, `/experiments/:id`, `/experiments/new` |
| **Primary users** | AI Engineer, ML Engineer |
| **Primary goal** | Design experiments, monitor runs, compare variants, declare winners |

---

## Layout Structure

### Experiments List (`/experiments`)

```
┌──────────────────────────────────────────────────────────────┐
│  Header: Experiments · [New Experiment] [Filter ▼] [Search]  │
├──────────────────────────────────────────────────────────────┤
│  Experiment Cards (grid or list)                             │
│  ┌──────────────────────┐ ┌──────────────────────┐          │
│  │ 🔄 AB-47             │ │ ✅ CD-12             │          │
│  │ Temperature increase  │ │ Top-k reduction      │          │
│  │ Running · 2h elapsed  │ │ Completed · 30m ago  │          │
│  │ Variants: 2           │ │ Winner: Variant B    │          │
│  └──────────────────────┘ └──────────────────────┘          │
│  ┌──────────────────────┐ ┌──────────────────────┐          │
│  │ ⏳ EF-89             │ │ ❌ GH-34             │          │
│  │ Prompt optimization  │ │ Model swap            │          │
│  │ Draft · Not started  │ │ Failed · 1h ago      │          │
│  └──────────────────────┘ └──────────────────────┘          │
└──────────────────────────────────────────────────────────────┘
```

### Experiment Detail (`/experiments/:id`)

```
┌──────────────────────────────────────────────────────────────┐
│  Breadcrumbs: Experiments > AB-47                            │
│  Header: AB-47 · Running · [Stop] [Declare Winner] [Share]   │
├──────────────────────────────────────────────────────────────┤
│  Summary Cards                                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Duration │ │ Variants │ │ Metrics  │ │ Status   │       │
│  │ 2h 15m   │ │ 2        │ │ 3        │ │ Running  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
├──────────────────────────────────────────────────────────────┤
│  Metric Comparison Table                                      │
│  ┌──────────┬───────────┬───────────┬───────┬────────┐     │
│  │ Metric   │ Baseline  │ Variant B │ Delta │ p-value│     │
│  ├──────────┼───────────┼───────────┼───────┼────────┤     │
│  │ Accuracy │ 87.2%     │ 89.1%     │ +1.9% │ 0.03   │     │
│  │ Latency  │ 245ms     │ 267ms     │ +9%   │ 0.12   │     │
│  └──────────┴───────────┴───────────┴───────┴────────┘     │
├──────────────────────────────────────────────────────────────┤
│  Timeline Chart (metrics over experiment duration)           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░    │ │
│  │  Baseline ──  Variant B ──                             │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Experiment Designer (`/experiments/new`)

```
┌──────────────────────────────────────────────────────────────┐
│  Header: New Experiment · [Save Draft] [Review & Launch]     │
├────────────────────────────┬─────────────────────────────────┤
│  Form (left)               │  Preview (right)                │
│                            │                                 │
│  Name: [_______________]   │  Experiment Summary             │
│  Description: [________]   │  Name: AB-47                   │
│                            │  Baseline: config v140         │
│  Baseline Config: [v140]   │  Variant B: config v141        │
│                            │  Metrics: accuracy, latency    │
│  Variants:                  │  Duration: 24h                 │
│  ┌────────────────────┐   │                                 │
│  │ + Add Variant      │   │                                 │
│  └────────────────────┘   │                                 │
│                            │                                 │
│  Metrics:                   │                                 │
│  [x] Accuracy               │                                 │
│  [x] Latency p95            │                                 │
│  [ ] Throughput             │                                 │
│                            │                                 │
│  Duration: [24h] [▼]      │                                 │
│  Traffic: [50%]           │                                 │
│                            │                                 │
│  Rollback Conditions:      │                                 │
│  [____________________]    │                                 │
└────────────────────────────┴─────────────────────────────────┘
```

---

## States

### Loading (list)
- Card skeleton grid (4 placeholder cards).

### Empty (no experiments)
- "No experiments yet. Approve a recommendation or design a new experiment to get started."
- "New Experiment" CTA.

### Running
- Card shows spinner/progress. Duration elapsed updating.
- Detail shows live metric comparison with auto-refresh indicator.

### Completed (ready for review)
- Card shows "Results ready" badge. CTA to review.
- Detail shows winner suggestion with confidence.

### Failed
- Card shows red "Failed" badge. Error summary on hover.
- Detail shows failure reason and logs.

### Draft
- Card shows "Draft" badge. "Continue editing" CTA.
- Designer pre-fills last saved state.

---

## Deliverables

Generate:
1. **Experiments List** — grid of experiment cards with status badges
2. **Experiment Detail** — metric comparison table, timeline chart, decision panel
3. **Experiment Designer** — form with live preview, validation
4. **Experiments List empty** — no experiments yet
5. **Dark mode variants** for each
