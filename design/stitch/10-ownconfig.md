# Stitch Prompt: OwnConfig

> Generate the configuration management module for Own Platform.
>
> **Context:** This prompt assumes `stitch/00-master-context.md` as the foundation. Read it first.
>
> **Priority:** Sprint 3

---

## Design Goal

Generate OwnConfig — the configuration management interface where operators view, create, diff, and roll back configuration snapshots.

Configuration is immutable. Changes always create a new ConfigurationSnapshot. Rollback changes pointers. Never modify historical snapshots.

OwnConfig should feel like:

- **Terraform Cloud** — snapshot-based configs, version history, diff viewer
- **Datadog** — config health indicators, status badges
- **Sentry** — clean metadata sidebar, JSON preview

---

## Screen Information

| Property | Value |
|---|---|
| **Recipe** | B — Collection + Inspector (list + inspector) |
| **Routes** | `/config/snapshots`, `/config/snapshots/:id` |
| **Primary users** | AI Engineer, Operator |
| **Primary goal** | Browse snapshots, inspect config diff, rollback (with human approval) |

---

## Layout Structure

### Snapshot List (`/config/snapshots`)

```
┌──────────────────────────────────────────────────────────────┐
│  Header: Configuration · [Compare] [Filter ▼]                │
├──────────────────────────────────────────────────────────────┤
│  Applied Snapshot Indicator                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ ✅ Currently applied: Snapshot #203 · v140             │ │
│  │ Applied 2h ago by alice@own                            │ │
│  └────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────┤
│  Snapshot Timeline (reversed, newest first)                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ ⚡ #203  v140  Applied ✅    2h ago  by alice   [View] │ │
│  │ #202  v139  Rolled back ⏪  5h ago  by bob     [View] │ │
│  │ #201  v138  Applied ✅    1d ago  by alice   [View] │ │
│  │ #200  v137  Rejected ❌   1d ago  by ci       [View] │ │
│  │ #199  v136  Applied ✅    2d ago  by bob     [View] │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Snapshot Detail (`/config/snapshots/:id`)

```
┌──────────────────────────────────────────────────────────────┐
│  Breadcrumbs: Config > Snapshots > #203                      │
│  Header: Snapshot #203 · v140 · Applied · [Rollback to here] │
├──────────────────────────────────────────────────────────────┤
│  Metadata Panel                                              │
│  ┌─────────────┬────────────────────────────────────────┐   │
│  │ ID          | snap_203                               │   │
│  │ Version     | 140                                    │   │
│  │ Status      | Applied                                 │   │
│  │ Applied by  | alice@own                               │   │
│  │ Applied at  | Mar 24, 2026 · 10:00 UTC               │   │
│  │ Previous    | #202 (v139)                             │   │
│  │ Lineage     | → recommendation_56 → decision_32      │   │
│  └─────────────┴────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────┤
│  Entries Table                                               │
│  ┌──────────────┬────────────┬────────────┬──────────┐      │
│  │ Key          │ Value      │ Changed    │ Previous │      │
│  ├──────────────┼────────────┼────────────┼──────────┤      │
│  │ model.temp   │ 0.7        │ ✓ Changed  │ 0.8      │      │
│  │ model.top_k  │ 50         │ ✓ Changed  │ 100      │      │
│  │ retrieval.l  │ 0.6        │ ✓ Changed  │ 0.5      │      │
│  │ runtime.max  │ 30s        │ —          │ —        │      │
│  └──────────────┴────────────┴────────────┴──────────┘      │
├──────────────────────────────────────────────────────────────┤
│  Diff View (togglable)                                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Diff: Snapshot #203 vs #202 (v139)                     │ │
│  │ ──────────────────────────────────────────────────     │ │
│  │ - model.temp: 0.8                                     │ │
│  │ + model.temp: 0.7                                     │ │
│  │ - model.top_k: 100                                    │ │
│  │ + model.top_k: 50                                     │ │
│  │ + retrieval.threshold: 0.6                            │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## Sections Detail

### Applied Snapshot Indicator
- **Content:** Green banner/bar showing currently applied snapshot. Version number, applied timestamp, actor.
- **Interaction:** "View" link to that snapshot. "Rollback" CTA (needs approval).

### Snapshot Timeline
- **Content:** Vertical timeline. Each entry: icon (⚡ new, ⏪ rollback, ❌ rejected), version, status badge, timestamp, actor.
- **Interaction:** Click row → snapshot detail. Compare checkbox for side-by-side diff.
- **Empty:** "No snapshots yet. Configurations are recorded when changes are applied."

### Metadata Panel (Detail)
- **Content:** Key-value: ID, version, status, applied by/at, previous snapshot, lineage.
- **Interaction:** Copy fields. Click previous/lineage links.

### Entries Table (Detail)
- **Content:** All config entries in this snapshot. Columns: key, value, changed indicator, previous value.
- **Interaction:** Sort by key or changed. Filter by changed/unchanged. Search by key.
- **Empty:** "No configuration entries in this snapshot."

### Diff View
- **Content:** Unified or split diff between this snapshot and previous. Added lines green, removed red, unchanged dimmed.
- **Interaction:** Toggle between table view and diff view. Copy diff. Download as patch.

---

## States

### Loading (list)
- Timeline skeleton (5 entries). Applied indicator skeleton.

### Loading (detail)
- Metadata skeleton. Entries table skeleton (5 rows). Diff skeleton.

### Empty (no snapshots)
- "No configuration snapshots yet. Snapshots are created automatically when configuration changes are applied."

### Rollback in progress
- Snapshot timeline shows pending rollback badge with spinner.
- Rollback confirmation modal visible (requires human approval).

### Error (list)
- "Failed to load snapshots. [Retry]"

### Error (detail)
- "Failed to load snapshot. [Retry]"

---

## Deliverables

Generate:
1. **Snapshot List** — timeline with applied indicator
2. **Snapshot Detail** — metadata panel, entries table, diff view
3. **Snapshot Diff** — side-by-side diff view toggled on
4. **Rollback Confirmation** — modal or panel with approval step
5. **Dark mode variants** for each
