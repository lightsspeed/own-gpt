# Stitch Prompt: Navigation Shell

> Generate the navigation shell for Own Platform.
>
> **Context:** This prompt assumes `stitch/00-master-context.md` as the foundation. Read it first.
>
> **Priority:** Sprint 1 — must be generated before or alongside OwnGPT and Dashboard.

---

## Design Goal

Generate the persistent navigation shell that wraps every screen in Own Platform: sidebar, top bar, breadcrumbs, and global command palette.

The navigation must feel stable, predictable, and professional. It never reorganizes. Items do not appear, disappear, or reorder based on context. The only dynamic elements are badges and counts.

---

## Layout Structure

```
┌──────────────┬───────────────────────────────────────────────┐
│              │  Global Command Bar                           │
│              │  [🔍 Search... (⌘K)]  [24h ▼]  [+]  [🔔][👤] │
│  Sidebar     ├───────────────────────────────────────────────┤
│  (240px)     │                                               │
│              │  Content Area                                 │
│  Home        │                                               │
│  ► OwnGPT    │  (screen content fills remaining space)       │
│               │                                               │
│  Observe     │                                               │
│    Findings  │                                               │
│    Evaluation│                                               │
│              │                                               │
│  Analyze     │                                               │
│    Recs      │                                               │
│    Exps      │                                               │
│    Analytics │                                               │
│              │                                               │
│  Govern      │                                               │
│    Config    │                                               │
│    Decisions │                                               │
│    Governance│                                               │
│              │                                               │
│  Operate     │                                               │
│    OwnOps    │                                               │
│    Automation│                                               │
│              │                                               │
│  System      │                                               │
│    Caps      │                                               │
│    Ledger    │                                               │
│    Artifacts │                                               │
│              │                                               │
│  🕐 History  │                                               │
│  ⚙ Settings  │                                               │
│  ❓ Help     │                                               │
└──────────────┴───────────────────────────────────────────────┘
```

---

## Section Specifications

### Sidebar
- **Width:** 240px desktop. Collapsible to icon-only (64px) or hidden.
- **Background:** Surface color (`bg.secondary`). Right border (subtle).
- **Sections:** Home, Observe, Analyze, Govern, Operate, System — plus bottom-anchored items.
- **Items per section:** Section header (uppercase, small, secondary text) + clickable navigation items.
- **Navigation items:** Icon (20px, line style) + label. Active item: accent color + subtle background highlight.
- **Count badges:** Optional — shown on items with pending counts (e.g., "Findings" with badge for unread count).
- **Collapse:** Toggle via ☰ in top bar or `⌘\`. Collapsed state shows icons only with tooltips.
- **Bottom section:** History, Settings, Help — visually separated by divider.

### Sidebar sections

```
Home
  ► OwnGPT                    Badge: unread conversation count (optional)
  Dashboard

Observe
  Findings                    Badge: unread findings count
  Continuous Evaluation

Analyze
  Recommendations             Badge: pending count
  Experiments                 Badge: running count
  Analytics

Govern
  Configuration               Badge: pending approval count
  Decisions
  Governance

Operate
  OwnOps (Operations)
  Automation

System
  Capabilities
  Learning Ledger
  Artifact Explorer
```

### Global Command Bar
- **Height:** 56px. Sticky top. Full width.
- **Background:** Surface color (`bg.primary` or `bg.secondary`). Bottom border (subtle).
- **Elements** (left to right):
  - ☰ hamburger (toggle sidebar collapse)
  - Breadcrumbs (on detail screens)
  - Search input (⌘K) — prominent, centered or slightly right
  - Time window dropdown
  - "+" quick action button
  - Notification bell with unread count badge
  - User avatar + dropdown (settings, sign out)

### Breadcrumbs
- **Visibility:** Only on detail screens (Level 2). Not shown on Level 0 or Level 1.
- **Format:** `Home > Findings > Finding Detail` — clickable segments with chevron separators.
- **Behavior:** Click segment → navigate to that level. Last segment is current page (not clickable).
- **Dropdown:** Each segment (except last) shows dropdown on hover with sibling pages.

### Mobile top bar
- Condensed: hamburger + page title + search icon + notification bell + user avatar.
- Search opens full-screen overlay.
- Time window and quick action hidden in overflow menu.

---

## Global Command Palette (⌘K)

- **Trigger:** ⌘K / Ctrl+K from any screen. Clicking search bar.
- **Layout:** Centered overlay. Width: 600px max. Dark scrim behind.
- **Content:**
  - Search input (auto-focused) with placeholder "Search artifacts, capabilities, configs, or type a command..."
  - Results grouped by type: Findings, Recommendations, Experiments, Config, Artifacts, Capabilities
  - Recent searches (below input, before query)
  - Keyboard shortcut hints (right side of results)
- **Navigation:** Arrow keys through results. Enter to navigate. Escape to close.
- **Empty:** "Type to search across the platform."
- **Error:** "Search failed. Try again." — inline within palette.

### Type prefixes
Users can scope searches:
- `f:` → Findings
- `r:` → Recommendations
- `e:` → Experiments
- `c:` → Configuration
- `a:` → Artifacts

---

## States to Design

### Sidebar states
- **Default:** Expanded (240px). All sections visible. Active item highlighted.
- **Collapsed:** Icons only (64px). Tooltips on hover. Active item indicated.
- **Hidden:** Not visible. Content area full width. Toggle via ☰.
- **Loading:** Skeleton sidebar — icon placeholders + text line placeholders.
- **Badge updates:** Count badges animate on change (scale bounce, 100ms).

### Command palette states
- **Closed:** Not visible.
- **Open (no query):** Overlay open. Input focused. Recent searches shown.
- **Open (typing):** Results appear asynchronously with loading indicator in palette.
- **Open (results):** Grouped results. Type prefix filter active if applicable.
- **Open (no results):** "No results matching your query" with suggestions.
- **Error:** "Search failed. Try again." — inline.

### Breadcrumb states
- **Not shown:** On root and Level 1 screens.
- **Shown:** On detail screens (Level 2). Full breadcrumb trail visible.
- **Hover:** Segment background highlight. Dropdown on clickable segments.

---

## Visual Design Constraints

### Colors
- **Sidebar:** `bg.secondary`. Active item: accent background (subtle, 10–15% opacity). Text: `text.primary`.
- **Sidebar icons:** `text.secondary`. Active icon: accent color.
- **Section headers:** Uppercase, 11px, `text.secondary` (60% opacity).
- **Command bar:** `bg.primary` or `bg.secondary`. Bottom border: `border.subtle`.
- **Command palette:** Overlay background with scrim. Results: alternating or with hover highlight.
- **Breadcrumbs:** `text.secondary`. Active segment: `text.primary`. Separators: `text.disabled`.

### Typography
- **Sidebar items:** 14px, regular.
- **Section headers:** 11px, semibold, uppercase, tracking 0.5px.
- **Command bar:** 14px for search placeholder. 13px for time window.
- **Command palette results:** 14px item title, 12px description.

### Spacing
- **Sidebar padding:** 16px horizontal. 8px between sections.
- **Sidebar items:** 8–10px vertical padding. 12px gap between icon and label.
- **Section headers:** 16px top padding, 8px bottom padding.
- **Command bar:** 0–16px horizontal padding. Items centered vertically.
- **Command palette:** 20px internal padding. 8px between results.

### Icons
- **Sidebar:** 20px line icons. Consistent stroke width.
- **Command bar:** 16px icons. Search icon prominent.
- **Notification bell:** 20px. Badge overlaid top-right.

---

## Accessibility Requirements

- All interactive elements keyboard navigable (Tab through sidebar, Enter to activate).
- Sidebar uses `role="navigation"` with `aria-label`.
- Active item uses `aria-current="page"`.
- Collapsed sidebar uses tooltips for icon-only items.
- Command palette uses `role="listbox"` with `aria-activedescendant`.
- Breadcrumbs use `aria-label="Breadcrumb"` with `aria-current="page"` on last item.
- Focus management: command palette traps focus while open. Escape returns focus to trigger element.

---

## Mobile Adaptations

- **Sidebar:** Becomes full-screen overlay. Triggered by hamburger or swipe from left edge.
- **Command bar:** Condensed. Search becomes icon. Time window and quick action in overflow.
- **Command palette:** Full-screen overlay (not centered). Wider results for touch.
- **Breadcrumbs:** Truncated with "..." for long paths. First + last segment visible.
- **Bottom navigation:** On mobile, primary navigation may use bottom tab bar instead of sidebar.

---

## Review Checklist

- [ ] Does the sidebar feel stable and predictable?
- [ ] Can every screen be reached in 3 clicks from the dashboard?
- [ ] Is the active navigation item clearly indicated?
- [ ] Is the command palette fast and discoverable?
- [ ] Do breadcrumbs make navigation context clear?
- [ ] Does the command bar provide value on every screen?
- [ ] Does the navigation work identically with keyboard and mouse?
- [ ] Does mobile navigation feel native, not desktop-adapted?

---

## Deliverables

Generate:
1. **Full navigation shell** — sidebar expanded, command bar, empty content area
2. **Sidebar collapsed** — icon-only mode with tooltip on hover
3. **Breadcrumbs visible** — on a detail screen (e.g., Finding Detail)
4. **Command palette open** — overlay with search results
5. **Navigation mobile** — sidebar as overlay, condensed top bar
6. **Navigation with badges** — counts visible on sidebar items
7. **Dark mode variants** for each of the above
