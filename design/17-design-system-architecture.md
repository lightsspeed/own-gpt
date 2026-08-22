# Design System Architecture

> The conceptual building blocks from which every interface in the AI Engineering Platform is constructed.
>
> **Not a component library. Not a Figma file. Not Tailwind. Not React.**
>
> This document defines the architecture *above* any implementation framework.
>
> Implementation technologies may change. This architecture should not.

---

## Purpose

A design system is often mistaken for a UI toolkit — a collection of buttons, inputs, and cards that teams assemble into screens.

This document rejects that definition.

A design system is an **architectural asset**. It translates interaction architecture into consistent, predictable interfaces. It encodes the behavioral rules defined in Phases 5 and 6 into reusable primitives that guarantee every screen feels like part of the same product.

The architecture serves three purposes:

1. **Consistency enforcement** — Every screen built from the same primitives behaves predictably, regardless of which team or engineer builds it.
2. **Complexity containment** — Primitives encapsulate behavioral complexity. Screens compose primitives; they do not reinvent interaction patterns.
3. **Technology independence** — The architecture survives framework migrations, visual redesigns, and platform changes because it defines *what* exists, not *how* it is rendered.

---

## Design System Philosophy

### Consistency before creativity
Every interface decision must first be questioned: "Does an existing primitive or pattern handle this?" Novelty is permitted only when no existing construct can express the required behavior. Consistency is the default; creativity requires justification.

### Composition over customization
Interfaces are assembled from primitives, not custom-built for each screen. Customization happens through composition rules, spacing, and token selection — never through one-off components that duplicate existing primitives.

### Semantics over appearance
Primitives are defined by what they **mean** and **do**, not by how they look. A "Status Indicator" is defined by its behavioral contract (conveys state at a glance, uses shape+color+text, supports live updates), not by its pixel representation.

### Behavior before visuals
Visual properties serve behavioral intent. A surface has elevation because it establishes visual hierarchy, not because shadows are decorative. A button has padding because it needs a minimum touch target, not because it "looks balanced."

### Accessibility by default
Accessibility is not a layer applied after design. Every primitive must work for keyboard-only users, screen reader users, and users with motion sensitivity by default. Primitives that cannot meet accessibility requirements are not added to the system.

### Predictability
Users should be able to predict how an unfamiliar screen behaves based on their experience with the same primitives on familiar screens. A Card is a Card is a Card — whether it appears on the dashboard or in an experiment list.

### Progressive disclosure
Primitives support layering. A summary is shown by default. Detail is revealed on interaction. Raw data is shown on explicit request. No primitive dumps full complexity on the user.

### State-driven presentation
Every primitive renders according to its current state (idle, loading, empty, error, success, disabled, selected, focused). Visual properties are derived from state + semantics, never from arbitrary decisions.

### Reusable primitives
The primitive set is finite and deliberately small. New primitives are added only when existing ones cannot express the required semantics. Primitive count is a metric to be minimized, not maximized.

### Minimal cognitive load
Primitives communicate their purpose at a glance. A Surface is for containing. An Action is for triggering. A Status is for indicating. Users should never need to read to understand what a primitive does.

### Long-term maintainability
Every primitive, composition, and pattern is documented with its purpose, behavioral contract, state model, and relationship to other primitives. Undocumented primitives are deleted. Undocumented patterns are not valid.

---

## Design System Layers

```
Foundation
    ↓
Design Tokens
    ↓
Primitives
    ↓
Compositions
    ↓
Patterns
    ↓
Screen Recipes
    ↓
Experiences
```

### Foundation
The deepest layer. Defines the sensory constants of the platform: typography rhythm, spatial system, grid logic, density spectrum, elevation philosophy, shape language, and contrast principles. Foundations define *what* each dimension means, not *what value* it has.

**Owns:** Typography system, spacing scale principles, grid logic, density definitions, elevation meaning, shape semantics, contrast requirements.

**Does not own:** Specific numeric values, color palettes, font choices.

### Design Tokens
The semantic translation layer. Maps foundational concepts to named tokens that represent design decisions. Tokens are the interface between foundation and implementation.

**Owns:** Color tokens (semantic, not literal), spacing tokens, typography tokens, elevation tokens, radius tokens, opacity tokens, motion tokens, duration tokens, z-order tokens, icon tokens.

**Does not own:** Component-specific styling, page layout decisions.

### Primitives
The atomic building blocks. Every interface element that carries semantic meaning belongs to exactly one primitive category. Primitives are defined by their behavioral contract, state model, and token interface.

**Owns:** Surface, Container, Panel, Card, Section, Divider, Heading, Text, Action, Input, Selection, Status, Indicator, Badge, Avatar, Navigation Item, Toolbar, Inspector, Timeline Entry, Conversation Message, Artifact Reference, Command Entry, Tool Result, Evidence Block, Approval Block, Progress Block.

**Does not own:** Screen-specific layouts, business logic, page-level behavior.

### Compositions
Named groupings of primitives that form reusable mid-level structures. Compositions are the vocabulary of page construction.

**Owns:** Panels, Inspectors, Dashboards, Editors, Collections, Comparisons, Workspaces, Conversations, Monitoring views, Review experiences.

**Does not own:** Full page layouts, recipe-level behavior.

### Patterns
Reusable interaction sequences that span multiple compositions. Patterns define how compositions interact — how a Collection feeds into an Inspector, how a Conversation spawns an Editor, how a Review composition commits a Decision.

**Owns:** List→Detail, Conversation→Action, Search→Explore, Timeline→Inspect, Compare→Decide.

**Does not own:** Page-level flow, cross-screen navigation (owned by recipes).

### Screen Recipes
Complete page blueprints that combine compositions and patterns into full-screen experiences. Recipes are the bridge between design system and product.

**Owns:** Overview+Actions, Collection+Inspector, Conversation+Context, Timeline+Detail, Compare+Analysis, Editor+Preview, Review+Approval, Monitoring+Status, Search+Explore, Settings+Configuration.

**Does not own:** Product-specific content, API integration.

### Experiences
The top layer. Product-specific screens that instantiate recipes with real data and business logic. Experiences are the only layer that should contain product-specific behavior.

**Owns:** Operator Dashboard, Findings List, Experiment Designer, etc.

**Owns nothing shared** — any reusable behavior discovered at this layer must be pushed down to the appropriate lower layer.

### Layer rules
- Dependencies flow downward. No layer depends on a higher layer.
- A layer may only use primitives, compositions, and patterns from its own or lower layers.
- Violation: A Screen Recipe referencing a product-specific API endpoint.
- Violation: A Primitive referencing a Screen Recipe.
- Violation: A Composition containing product-specific business logic.

---

## Foundations

### Typography
Typography is defined by role, not by size.

- **Heading roles:** Page title, section title, card title, widget header. Each role has a defined hierarchy position (h1–h6).
- **Text roles:** Body (primary content), secondary (supporting content), caption (metadata), code (technical content), label (form labels).
- **Semantic properties:** Role, weight, line-height ratio, tracking (letter-spacing), case convention.
- **Rhythm:** Vertical rhythm follows spacing scale. Headers have defined margin relationships to following content.

**Principles:**
- One typeface family. A second is permitted for code/content display only.
- No font weights below 400 (regular) for body text.
- Line length bounded by readability (45–75 characters optimal).
- Hierarchical contrast achieved through weight + size + spacing, never color alone.

### Spacing
Spacing follows a geometric or linear scale. The scale defines spatial relationships, not pixel values.

- **Scale type:** Linear or geometric with defined base and ratio.
- **Semantic spacing:** Inset (internal padding), stack (vertical gap between elements), inline (horizontal gap), gutter (between columns).
- **Context-aware spacing:** Dense mode (compact), default mode (comfortable), relaxed mode (spacious).

**Principles:**
- Spacing values are never arbitrary. Every gap maps to a scale value.
- Related elements use tighter spacing than unrelated elements.
- Spacing communicates hierarchy: more space between sections than within sections.

### Grid
The grid is a conceptual framework for horizontal layout. It defines column logic, breakpoints, and responsiveness.

- **Column system:** A defined number of columns at each breakpoint.
- **Gutter:** The gap between columns, derived from spacing scale.
- **Margin:** The outer padding of the grid, derived from spacing scale.
- **Breakpoints:** Device-agnostic width thresholds that trigger layout changes.

**Principles:**
- Grid is a guideline, not a cage. Content can span fractional columns.
- Grid adapts to content density, not the reverse.
- Breakpoints are defined by content needs, not device categories.

### Density
Density defines how tightly packed interface elements appear.

- **Density levels:** Compact, default, comfortable, spacious.
- **Density applies to:** Spacing scale, typography scale, touch target sizes, component internal padding.
- **Density is not:** A visual style. It is a spatial efficiency preference.

**Principles:**
- Default density targets information-dense professional work.
- Users may switch density modes (user preference).
- Accessibility overrides density at extreme compact levels (minimum touch targets).

### Sizing
Sizing defines the fundamental measurement units.

- **Base unit:** A single number from which all measurements derive.
- **Element sizing:** Content-determined (shrinkwrapped), container-determined (filled), or proportional (relative to parent).
- **Touch targets:** Minimum interactive area regardless of visual size.

**Principles:**
- No element has a size without reason. Size follows role, content, or container.
- Interactive elements meet minimum touch target size.
- Sizing is relative, not absolute — scales with typography and spacing.

### Elevation
Elevation communicates vertical hierarchy in a flat interface. It is not decorative.

- **Elevation levels:** Surface (0), raised (1), overlay (2), modal (3), notification (4).
- **Elevation communicates:** Containment relationship, interaction priority, temporal relevance.
- **Elevation uses:** Shadow, background color, or border — never more than one at a time.

**Principles:**
- Higher elevation = higher priority or closer temporal relevance.
- Elevation is meaningful, not decorative. No element has elevation without a hierarchy reason.
- Elevation model is consistent across the platform — a modal is always at the same level.

### Shape
Shape defines the corner treatment of surfaces and containers.

- **Shape levels:** None (square), soft (rounded), rounder (pill), circular.
- **Shape is semantic:** Square for structural containers, rounded for interactive elements, circular for avatars and badges.
- **Shape consistency:** Similar elements share the same shape treatment.

### Borders
- Borders define separation, not decoration.
- Border use cases: Container outline, divider between sections, focus indicator, error state.
- Border weight is minimal — the lightest visible weight is preferred.

### Contrast
- Text contrast meets WCAG AA (4.5:1 for body, 3:1 for large text).
- Interactive element contrast meets WCAG AA.
- Non-text content (icons, charts) meets WCAG AA (3:1).
- Contrast is never sacrificed for visual style.

---

## Design Tokens

### Token philosophy
Tokens are **semantic** abstractions, not direct value assignments.

Good: `color.text.primary`, `color.status.error`, `spacing.stack.section`

Bad: `color.blue.500`, `spacing.16px`, `color.primary`

Semantic tokens allow the visual identity to change without changing the architecture. A re-theme changes token values, not token names.

### Token categories

#### Color tokens

- **Text:** `text.primary`, `text.secondary`, `text.disabled`, `text.inverse`, `text.link`, `text.code`
- **Background:** `bg.primary`, `bg.secondary`, `bg.tertiary`, `bg.surface`, `bg.overlay`, `bg.modal`
- **Border:** `border.default`, `border.subtle`, `border.focus`, `border.error`, `border.success`
- **Interactive:** `interactive.primary`, `interactive.secondary`, `interactive.neutral`, `interactive.danger`
- **Status:** `status.success`, `status.warning`, `status.error`, `status.info`, `status.neutral`
- **Severity:** `severity.critical`, `severity.high`, `severity.medium`, `severity.low`, `severity.none`
- **Chart:** `chart.1` through `chart.N` (data visualization series)

Semantic naming ensures that changing a brand color updates every consumer without renaming.

#### Spacing tokens

- **Scale:** `spacing.0`, `spacing.1`, `spacing.2`, ..., `spacing.N`
- **Semantic:** `spacing.inset.small`, `spacing.stack.default`, `spacing.inline.large`
- **Density-aware:** Tokens adjust value based on density mode while keeping the same name.

#### Typography tokens

- **Font family:** `font.family.body`, `font.family.code`
- **Font weight:** `font.weight.regular`, `font.weight.medium`, `font.weight.semibold`, `font.weight.bold`
- **Font size:** `font.size.body`, `font.size.small`, `font.size.large`, `font.size.h1`–`h6`
- **Line height:** `line.height.body`, `line.height.heading`, `line.height.code`
- **Letter spacing:** `tracking.default`, `tracking.heading`, `tracking.code`

#### Elevation tokens

- `elevation.surface` (base level)
- `elevation.raised` (cards, dropdowns)
- `elevation.overlay` (side panels, dialogs)
- `elevation.modal` (modal dialogs)
- `elevation.notification` (toasts, popovers)

#### Radius tokens

- `radius.none` (square)
- `radius.small` (subtle rounding)
- `radius.medium` (moderate rounding)
- `radius.large` (significant rounding)
- `radius.full` (pill/circular)

#### Opacity tokens

- `opacity.disabled`
- `opacity.subtle`
- `opacity.overlay`

#### Motion tokens

- `motion.duration.instant` (< 100ms)
- `motion.duration.fast` (100–200ms)
- `motion.duration.normal` (200–300ms)
- `motion.duration.slow` (300–500ms)
- `motion.easing.linear`
- `motion.easing.standard`
- `motion.easing.accelerate`
- `motion.easing.decelerate`
- `motion.easing.spring`

#### Duration tokens

- `duration.instant`, `duration.short`, `duration.medium`, `duration.long`
- Used for transitions, animations, and auto-dismiss timing.

#### Z-order tokens

- `z.base`, `z.sticky`, `z.dropdown`, `z.overlay`, `z.modal`, `z.notification`, `z.max`

#### Icon tokens

- `icon.size.small`, `icon.size.medium`, `icon.size.large`
- Icon categories: Action, Status, Navigation, File type, Severity

#### Illustration tokens

- `illustration.size.inline`, `illustration.size.card`, `illustration.size.section`, `illustration.size.page`

#### Chart tokens

- `chart.color.primary` through `chart.color.quaternary`
- `chart.grid`, `chart.axis`, `chart.label`

---

## Primitive Building Blocks

Every interface element carries semantic meaning and belongs to exactly one primitive category.

### Surface

**Purpose:** The backdrop for content. Provides visual container context.

**Behavioral contract:**
- Surfaces contain content but do not interact.
- Surfaces have elevation (one of the defined levels).
- Surfaces have no padding of their own — they rely on children or Container for spacing.
- Surfaces communicate their role through elevation + background color.

**States:** Default only (surfaces do not have loading/error states).

**Relationships:** Is the lowest-level container. Panels and Cards are Surfaces with additional semantics.

### Container

**Purpose:** A bounded content area with optional padding, background, and borders.

**Behavioral contract:**
- Containers hold content with defined spacing.
- Containers may be scrollable.
- Containers may have a header (using Heading primitive).
- Containers adapt to available width.

**States:** Default, loading (skeleton), empty (empty state message), error (error state).

**Composition:** May contain any other primitive.

### Panel

**Purpose:** A side-mounted container for supplementary or detail content.

**Behavioral contract:**
- Panels slide in from the right or bottom.
- Panels have a close/dismiss action.
- Panels preserve their content state when toggled.
- Panels are not modal — they overlay without blocking.

**States:** Open, closed, loading, empty, error.

**Composition:** Contains Headings, Text, Lists, Status, Actions.

### Card

**Purpose:** A self-contained content unit with visual boundaries.

**Behavioral contract:**
- Cards are clickable (navigates to detail).
- Cards contain a summary of the item they represent.
- Cards have consistent internal structure: optional header → content → optional footer.
- Cards may have status indicators or badges.

**States:** Default, hovered, focused, pressed, selected, disabled, loading (skeleton), empty (no content in card).

**Composition:** Badge, Status, Heading, Text, Actions, Artifact Reference.

### Section

**Purpose:** A named grouping of related content within a larger layout.

**Behavioral contract:**
- Sections have a heading (stage 1 heading or lower).
- Sections may be collapsible.
- Sections have consistent vertical spacing (stack token).
- Sections are not interactive themselves (their children are).

**States:** Expanded, collapsed, loading, empty.

**Composition:** Heading, any content primitives.

### Divider

**Purpose:** Visual separation between content groups.

**Behavioral contract:**
- Dividers have no interactive behavior.
- Dividers may be horizontal or vertical.
- Dividers are semantic — they communicate grouping, not decoration.

**States:** Default only.

### Heading

**Purpose:** Establish content hierarchy and enable screen reader navigation.

**Behavioral contract:**
- Headings map to semantic levels h1–h6.
- Each screen has exactly one h1 (page title).
- Headings are not styled text — they are structural.
- Headings have consistent typography tokens based on level.

**States:** Default only.

### Text

**Purpose:** Display readable content.

**Behavioral contract:**
- Text has defined roles: body, secondary, caption, code, label.
- Text supports inline emphasis (strong, code, link).
- Text truncation is explicit (ellipsis with optional tooltip).
- Text is never interactive on its own (use within Action for clickable text).

**States:** Default, disabled (grayed out).

### Action

**Purpose:** Trigger an operation or navigate to a destination.

**Behavioral contract:**
- Actions have a defined weight: primary, secondary, tertiary, ghost, danger.
- Actions have a defined size: small, medium, large.
- Actions show loading state during execution.
- Actions show disabled state when unavailable.
- Actions support keyboard activation (Enter/Space).

**States:** Default, hovered, focused, pressed, loading, disabled, hidden.

**Variants:** Button, Link, Icon button, Split button, Menu item.

### Input

**Purpose:** Capture user input for a single field.

**Behavioral contract:**
- Inputs have a label (using Text label role).
- Inputs show placeholder text when empty.
- Inputs show validation state: valid, invalid, warning.
- Inputs show character count when bounded.
- Inputs support keyboard navigation and focus.

**States:** Default, focused, filled, invalid, warning, disabled, loading (async validation).

**Variants:** Text input, textarea, number input, email, password, search input.

### Selection

**Purpose:** Choose from predefined options.

**Behavioral contract:**
- Selection primitives communicate single vs. multi-select.
- Selection shows current value clearly.
- Selection expands to reveal options.
- Selection supports keyboard navigation (arrow keys, type-ahead).

**States:** Default, focused, open, selected, disabled, loading, empty (no options).

**Variants:** Dropdown, Select, Combo box, Radio group, Checkbox group, Toggle (binary).

### Status

**Purpose:** Communicate the state of a system, process, or item.

**Behavioral contract:**
- Status uses shape + color + text label (never color alone).
- Status updates via live region for screen reader announcements.
- Status has defined levels: success, warning, error, info, neutral, pending.
- Status may include an animated indicator (pulse for active, spinner for loading).

**States:** Each status level is a state. Visual properties change with status, not with interaction.

**Variants:** Status dot, status badge, status bar, status pill.

### Indicator

**Purpose:** Show presence, activity, or count.

**Behavioral contract:**
- Indicators are compact — they do not contain text longer than a few characters.
- Indicators show unread counts, active presence, or attention signals.
- Indicators update in real time using live regions.

**States:** Visible with count, visible without count (zero hidden), hidden.

**Variants:** Badge count, presence dot, attention indicator.

### Badge

**Purpose:** Label an item with a category, severity, or attribute.

**Behavioral contract:**
- Badges are compact, non-interactive labels.
- Badges have semantic color mapping (severity, status, lifecycle stage).
- Badges may include an icon.

**States:** Each badge variant is a state. No interactive states.

**Variants:** Severity badge, status badge, lifecycle badge, maturity badge, type badge.

### Avatar

**Purpose:** Represent a user or system entity.

**Behavioral contract:**
- Avatars show initials when no image is available.
- Avatars have defined sizes (small, medium, large).
- Avatars may show online/offline presence.
- Avatars may be grouped (overlap cluster).

**States:** Default, with image, without image (initials), online, offline, busy.

### Navigation Item

**Purpose:** Navigate to another screen or section.

**Behavioral contract:**
- Navigation items show their current state (active/inactive).
- Navigation items may have nested children.
- Navigation items may show count badges or status indicators.
- Navigation items activate on click or keyboard Enter.

**States:** Default, hovered, active (current route), focused, disabled.

**Variants:** Sidebar item, top nav item, breadcrumb, tab, pagination item.

### Toolbar

**Purpose:** Group actions and filters for the current context.

**Behavioral contract:**
- Toolbar contains Actions, Selection, and Search primitives.
- Toolbar is sticky or scrolls with content based on recipe.
- Toolbar collapses overflow items into a "More" menu on smaller viewports.
- Toolbar never contains content — only controls.

**States:** Default, with overflow (some items in overflow menu).

### Inspector

**Purpose:** Display detailed information about a selected item.

**Behavioral contract:**
- Inspector shows metadata, content, and actions for one item.
- Inspector updates when selection changes.
- Inspector may be a side panel or inline section.
- Inspector preserves scroll position when switching items.

**States:** No selection (empty), loading, populated, error.

**Composition:** Heading, Text, Status, Badge, Action, Artifact Reference, Timeline Entry.

### Timeline Entry

**Purpose:** Represent a single event in a chronological sequence.

**Behavioral contract:**
- Timeline entries show time, event type, title, and summary.
- Timeline entries are clickable for detail.
- Timeline entries visually connect to adjacent entries.
- Timeline entries may show status or severity.

**States:** Default, expanded (detail visible), loading (streaming event).

### Conversation Message

**Purpose:** Represent a single turn in a conversation thread.

**Behavioral contract:**
- Messages are authored by user or AI.
- Messages may contain text, artifacts, tool results, or approval requests.
- AI messages stream content incrementally.
- Messages have citations linked to artifacts.
- Messages support branching (fork from this point).

**States:** Sending (pending), streaming (incremental), complete, error (failed to send).

### Artifact Reference

**Purpose:** Inline link to an artifact with preview context.

**Behavioral contract:**
- Artifact references show type icon, title, and optional summary.
- Artifact references are clickable (navigate to artifact detail).
- Artifact references may show status or severity.
- Artifact references inline in text are distinguished from surrounding content.

**States:** Default, hovered (preview tooltip).

### Command Entry

**Purpose:** Display a command and its result in a structured format.

**Behavioral contract:**
- Command entries show the command text, timestamp, and status.
- Command entries show the result in a structured view.
- Command entries support undo where applicable.
- Command entries may be collapsed to show summary only.

**States:** Pending, running, succeeded, failed, cancelled.

### Tool Result

**Purpose:** Display the output of a tool execution.

**Behavioral contract:**
- Tool results show tool name, execution time, status, and output.
- Tool results render output in appropriate format (table, code, text, chart).
- Tool results support streaming for long-running tools.
- Tool results are collapsed by default for large outputs.

**States:** Running, streaming, succeeded, failed, cancelled.

### Evidence Block

**Purpose:** Present supporting evidence for a claim, finding, or recommendation.

**Behavioral contract:**
- Evidence blocks show source artifact, timestamp, confidence, and excerpt.
- Evidence blocks are collapsible (summary expanded by default).
- Evidence blocks link to the full source artifact.
- Evidence blocks may be aggregated (multiple sources for one claim).

**States:** Loading, populated, error (source unavailable).

### Approval Block

**Purpose:** Present an approval decision point requiring human action.

**Behavioral contract:**
- Approval blocks show the decision to be made, context summary, and decision actions.
- Approval blocks require explicit action (approve, reject, request changes).
- Approval blocks collect rationale text for rejection.
- Approval blocks show decision history.

**States:** Pending (awaiting action), approved, rejected, changes-requested, approved-with-warning.

### Progress Block

**Purpose:** Show progress of a long-running operation.

**Behavioral contract:**
- Progress blocks show determinate or indeterminate progress.
- Progress blocks show elapsed time and estimated remaining time.
- Progress blocks show current step description.
- Progress blocks support cancellation.

**States:** Running (determinate), running (indeterminate), paused, completed, failed, cancelled.

---

## Composition Rules

Primitives combine into compositions. Compositions are named, reusable mid-level structures.

### Panel composition

```
Panel = Surface + Container semantics
  → Header: Heading + close Action
  → Body: any primitives (structured content)
  → Footer (optional): Action(s) for panel-level operations
```

### Inspector composition

```
Inspector = Panel composition
  → Selection-aware: content updates when parent list selection changes
  → Content sections: metadata, status, timeline, lineage, actions
  → State: no-selection (placeholder message)
```

### Dashboard composition

```
Dashboard = Grid layout
  → Widgets: Card compositions arranged in grid
  → Widget types: summary, list, chart, timeline, status
  → Behavior: independent loading, per-widget refresh, widget-level error handling
  → Command bar: Toolbar composition fixed at top
```

### Editor composition

```
Editor = Split layout (form + preview)
  → Form: Input + Selection + Action primitives in structured layout
  → Preview: live rendering of current form state
  → Validation: inline field validation, summary error banner
  → Actions: Save Draft, Submit, Cancel
```

### Collection composition

```
Collection = Filter + List + Detail
  → Toolbar: Search Input + Selection filters + Actions
  → List: Collection of Card primitives
  → Detail (optional): Inspector composition or full-page navigation
  → Pagination: Page controls or infinite scroll
  → Selection: Checkbox or row selection for batch actions
```

### Comparison composition

```
Comparison = Split view (two items side by side)
  → Item A: any primitive set
  → Item B: any primitive set
  → Diff highlights: visual indicators on changed/added/removed content
  → Unified view toggle: switch between side-by-side and unified
  → Sync behavior: synchronized scroll, synchronized expansion
```

### Workspace composition

```
Workspace = Full-height layout with persistent context
  → Main area: primary content (Conversation, Canvas, etc.)
  → Context panel: Inspector composition (togglable)
  → Header: Title, status, metadata
  → Toolbar: Context-specific actions
```

### Conversation composition

```
Conversation = Message thread + Input + Context
  → Thread: vertical list of Conversation Message primitives
  → Input: textarea + send Action + attachment controls
  → Context panel (optional): Inspector or artifact reference
  → Streaming: new messages appear incrementally with cursor animation
  → Branching: messages fork into parallel threads
```

### Monitoring composition

```
Monitoring = Status grid + Detail panel
  → Grid: Card primitives with Status indicators
  → Detail panel: Inspector showing metrics and events
  → Auto-refresh: configurable polling per card
  → Time controls: window selector for historical data
```

### Review composition

```
Review = Evidence + Decision panel
  → Evidence: Evidence Block primitives arranged in hierarchy
  → Comparison (optional): Comparison composition for before/after
  → Decision panel: sticky panel with Approval Block
  → Comments: thread for discussion
```

---

## State Representation

Every primitive communicates its state visually. The design system defines a consistent visual language for each state category.

| State | Visual Communication |
|---|---|
| **Idle** | Normal appearance. No special indicators. |
| **Loading** | Skeleton placeholder matching content dimensions. No spinner for initial load. Spinner for refresh. |
| **Streaming** | Animated cursor or progress bar. Content appears incrementally. "Stop" action available. |
| **Waiting** | Subtle progress indicator (pulsing dot, thin bar). No blocking overlay for brief waits. |
| **Needs approval** | Prominent attention indicator (badge, color, border). Decision actions visible. |
| **Success** | Green/mint status indicator. Confirmation icon. Brief duration animation (auto-dismiss). |
| **Warning** | Yellow/amber status indicator. Warning icon. Persistent until acknowledged. |
| **Error** | Red status indicator. Error icon. Error message with recovery action. Persistent. |
| **Recovering** | Fading from error state to normal. Subtle success indicator on recovery. |
| **Archived** | Reduced opacity. Gray styling. "Archived" badge. |
| **Disabled** | Reduced opacity (60%). No interaction possible. Cursor not-allowed. |
| **Selected** | Highlighted background or border. Selection indicator (checkbox, radio). Persists across interactions. |
| **Focused** | Visible focus ring. Keyboard navigation indicator. Never removed by design (determined by interaction). |

### State transition principles
- Transitions between states are **smooth and meaningful**, never abrupt.
- Loading → Content uses fade-in (not flash).
- Error → Recovery uses gradual reintroduction (not sudden replacement).
- State transitions respect `prefers-reduced-motion`.
- Every state communicates why the user is seeing it and what to do next.

---

## Responsive Philosophy

### Desktop-first
- Primary design target: 1280–1920px width.
- All recipes are designed for desktop first.
- Responsive behavior is adaptation, not redesign.

### Tablet (768–1024px)
- Two-column layouts collapse to single column.
- Side panels become slide-over overlays.
- Action bars condense (labels hide, icons remain).
- Grid reduces column count proportionally.

### Mobile (< 768px)
- Single column, full-width content.
- Side panels become bottom sheets or full-screen push.
- Filters collapse to expandable sections or modals.
- Complex interactions (edit, compare) use full-screen modes.
- Touch targets remain at minimum size (44x44px).

### Large displays (> 1920px)
- Content width is bounded (max-width constraint). White space fills margins.
- Grid may add columns for additional context.
- Side panels can be wider.

### Content adaptation
- Content informs layout, not the reverse.
- Data-dense screens (collections, monitoring) use available space.
- Content-light screens (settings, editor) use centered or constrained layouts.
- Text content respects line-length limits on any viewport.

### Interaction adaptation
- Hover states become tap states on touch devices.
- Drag-and-drop falls back to click-to-select + move.
- Complex gestures are never the only path to an action.
- Tooltips become expandable labels on touch.

---

## Accessibility Philosophy

### Visual
- All text meets WCAG AA contrast (4.5:1 body, 3:1 large text).
- Non-text content meets 3:1 contrast ratio.
- Information is never conveyed by color alone.
- Focus indicators are visible (minimum 2px offset ring).

### Motor
- All interactive elements have minimum 44x44px touch targets.
- All actions are reachable via keyboard.
- No time-limited interactions without ability to extend.
- Drag operations have a single-click alternative.

### Keyboard
- All functionality is operable through keyboard.
- Tab order follows visual layout (top-to-bottom, left-to-right).
- Focus is managed predictably — modals trap focus, side panels return focus on close.
- Arrow keys navigate within grouped elements (lists, grids, tabs).
- Escape closes overlays, panels, and modals.

### Screen readers
- All primitives have appropriate ARIA roles and labels.
- Dynamic content updates use `aria-live` regions.
- Status changes are announced (not just visually displayed).
- Headings form a logical document outline (h1–h6, no skips).
- Images and icons have meaningful alt text or `aria-hidden`.

### Cognitive
- Consistent layout and interaction patterns reduce cognitive load.
- Errors are explained in plain language with recovery actions.
- Complex operations are broken into steps with progress indication.
- No unexpected behavior or surprising navigation.

### Motion sensitivity
- All animations respect `prefers-reduced-motion`.
- Essential motion (progress, status change) uses minimal animation.
- Non-essential motion (decorative, parallax, entrance) is removed.
- No auto-playing animations or auto-scrolling carousels.

### Color independence
- Status uses shape + text + color (never color alone).
- Severity uses icon + text + color.
- Links use underline + color (never color alone).
- Charts use pattern + label + color.

---

## Extensibility

### Adding new primitives
New primitives are added only when existing primitives cannot express the required semantics.

**Approval criteria:**
1. Does an existing primitive already express this semantics? (reject — duplicate)
2. Can a composition of existing primitives express it? (reject — composition is sufficient)
3. Is this primitive used by at least 3 distinct screens? (reject — too narrow; defer)
4. Does the primitive have a clear behavioral contract? (required)
5. Does the primitive have a defined state model? (required)
6. Can the primitive be implemented without framework-specific dependencies? (required)

### Naming
- Primitive names are nouns (Surface, Card, Action, Status).
- Composition names are descriptive nouns (Inspector, Collection, Dashboard).
- Token names use dot-notation categories (`color.text.primary`).
- No framework-specific naming (`Button` is `Action`; no `VueButton` or `ReactButton`).

### Versioning philosophy
- The design system architecture has semantic versioning: MAJOR.MINOR.PATCH.
- MAJOR: Breaking change to primitive contracts or layer structure.
- MINOR: New primitive, composition, or pattern addition.
- PATCH: Clarification, correction, or non-breaking refinement.
- Version is applied to the architecture document, not to implementation artifacts.

### Deprecation
- Primitives and compositions are deprecated, not removed.
- Deprecated items remain in the architecture but are flagged as "do not use in new screens."
- Migration path is documented for each deprecated item.
- Removal occurs after two MAJOR versions have passed.

### Evolution
- The architecture is expected to evolve incrementally.
- New patterns emerge from product needs and are pushed down from Experiences.
- Evolution happens through documented RFCs, not through ad-hoc decisions.
- Every evolutionary step preserves backward compatibility for existing screens.

---

## Governance

### Ownership
- The design system architecture is owned by Platform Architecture (not by a single team).
- Changes require review by: Architecture group + at least two consuming teams.
- Day-to-day stewardship is assigned to a rotating Design System Architect role.

### Review process
1. **RFC** — Document describing the proposed change (problem, solution, impact, migration)
2. **Review** — Architecture group evaluates against criteria (extensibility section)
3. **Decision** — Accept, reject, or request revisions
4. **Document** — Update the architecture document with the change
5. **Communicate** — Announce to all consuming teams with migration guidance

### Contribution guidelines
- Contributions must be motivated by a real product need.
- Contributions must include documentation (purpose, contract, state model, relationships).
- Contributions must demonstrate cross-screen reuse (minimum 3 screens).
- Contributions must be framework-agnostic.

### Breaking changes
- Breaking changes require a MAJOR version bump.
- Breaking changes must include a migration guide.
- Breaking changes must be communicated at least one version cycle in advance.
- Breaking changes must have an architect-level approval.

### Documentation expectations
- Every primitive has: purpose, behavioral contract, state model, composition rules, variants, token interface, relationships, accessibility requirements, anti-patterns.
- Every composition has: purpose, participating primitives, layout rules, behavior rules, example recipes.
- Every token has: semantic name, category, expected value type, usage guidelines.
- Documentation is stored alongside the architecture (in the `design/` directory).

### Quality gates
- New primitive: demonstrated in 3 screens + accessibility audit + state model coverage.
- New composition: demonstrated in 2 recipes + responsive validation + keyboard navigation.
- Token change: verified against all token consumers + contrast audit.
- Breaking change: migration verified for all known consumers.

---

## Anti-Patterns

### Visual inconsistency
Elements with the same semantics appear differently across screens. Caused by allowing per-screen customization of primitives.

**Remedy:** Audit consistency quarterly. Any divergence is either a bug or a valid reason for a new primitive variant.

### Component explosion
The primitive set grows without bound. Every new screen adds new components instead of composing existing ones.

**Remedy:** Track primitive count as a quality metric. Adding a primitive requires documented justification against the approval criteria.

### Primitive duplication
Multiple primitives with overlapping responsibilities (e.g., Card vs. Tile vs. Block vs. Panel).

**Remedy:** Merge overlapping primitives. No two primitives should have overlapping behavioral contracts.

### Semantic drift
A primitive's visual appearance changes over time while its semantics remain the same, or its semantics change while its visual appearance stays the same.

**Remedy:** Semantic audits per release. Any drift is corrected or the primitive is formally redefined.

### Over-customization
Individual screens override token values or primitive behavior to achieve specific visual effects.

**Remedy:** Overrides are forbidden unless approved as a new token variant. If a screen needs different visual treatment, the token set expands, not the override count.

### Magic components
Components that handle too many concerns — rendering, state, business logic, data fetching — becoming impossible to reuse or test.

**Remedy:** Primitives handle presentation and behavior only. Business logic and data fetching live at the Screen Recipe layer.

### Token misuse
Using a token for a purpose other than its semantic meaning (e.g., `status.error` for a decorative border).

**Remedy:** Token usage audits. Any token used outside its semantic domain must switch to the correct token.

### Hidden state
State changes that are not visually communicated (e.g., a button that does nothing but gives no feedback).

**Remedy:** Every primitive must have a defined state model. Missing state representations are bugs.

### Accessibility as an afterthought
Accessibility is addressed after design is complete, leading to retrofits that are more expensive and less effective.

**Remedy:** Accessibility requirements are part of the primitive definition, not a separate review step. Primitives are not accepted without accessibility documentation.

### Framework-specific thinking
Designing primitives that mirror framework concepts (React components, Vue directives, CSS classes) rather than conceptual building blocks.

**Remedy:** Primitives are defined in behavioral terms. Implementation details are an entirely separate concern.

### Over-engineering for edge cases
Primitives that handle every possible variant and configuration, becoming complex and hard to understand.

**Remedy:** 80/20 rule — primitives handle the 80% common case. Edge cases use escape hatches or composition of simpler primitives.

### Design by committee
Every stakeholder adds requirements to primitives, leading to bloated combinatorial explosions.

**Remedy:** Primitives are owned by architecture, not by stakeholders. Stakeholder needs are met through composition, not primitive expansion.

### Ignoring motion
Motion is treated as decorative rather than communicative. Transitions are inconsistent or absent.

**Remedy:** Motion is defined at the Foundation layer. Every state transition has defined motion properties.

---

## Future Evolution

### AI-generated interfaces
As AI generates more interface elements, the design system architecture must constrain AI output to valid primitives and compositions. AI should not invent new interface patterns — it should assemble from the existing vocabulary.

**Implications:**
- Primitives and compositions must be machine-readable (structured definitions).
- AI prompt engineering should reference primitive contracts.
- Validation gates must reject AI output that violates the architecture.

### Adaptive layouts
Future interfaces may adapt to user role, current task, device capability, and context in real time.

**Implications:**
- Responsive philosophy must extend beyond viewport to context adaptation.
- Compositions must define adaptable slot structures (content fills available space).
- Layout logic must be rule-based, not position-based.

### Voice
Voice interactions introduce new input modalities while preserving existing visual primitives.

**Implications:**
- Primitives must have voice interaction contracts (what can be spoken, what is spoken back).
- Conversational primitives (Conversation Message, Command Entry) are the primary voice interface.
- Visual primitives must support being "spoken" (accessibility already provides foundation).

### Spatial computing
3D and mixed reality interfaces introduce spatial arrangement of primitives.

**Implications:**
- Elevation model extends to physical z-space.
- Primitives remain valid but render in 3D space.
- Composition rules become spatial arrangement rules.
- The architecture is already partially compatible (elevation, responsive layers).

### Multi-agent workspaces
Interfaces where multiple AI agents and multiple humans collaborate in shared workspaces.

**Implications:**
- Workspace composition becomes primary (Canvas with multiple participants).
- Agent avatars and presence indicators become important primitives.
- Timeline composition tracks agent actions alongside human actions.

### Personalization
Users may customize their interface over time.

**Implications:**
- Personalization operates on token values (theme, density) and composition arrangement (widget layout), never on primitive contracts.
- Personalization is stored as user settings artifacts.
- The architecture must distinguish between customization (allowed) and customization that breaks consistency (forbidden).

### Self-evolving design systems
Future systems may automatically suggest new primitives or compositions based on usage patterns.

**Implications:**
- The architecture must define what constitutes a valid new primitive (approval criteria).
- Usage data feeds into the governance process.
- Machine-assisted evolution is guided by the architecture, not autonomous.

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-07-25 | Architecture | Initial design system architecture |
