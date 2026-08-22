# Visual Language

> The sensory identity of the AI Engineering Platform.
>
> **Not pixel values. Not CSS. Not Figma.**
>
> This document defines the principles governing how the platform looks.
>
> Visual styling may evolve. These principles should not.

---

## Purpose

The Design System Architecture (17) defines the conceptual building blocks of the interface. This document defines how those building blocks are **seen** — the visual principles that give the platform a coherent sensory identity.

Where the Design System Architecture answers "what exists and how does it behave?", the Visual Language answers "what does it look like and why?"

The visual language is a direct expression of the Interaction Principles (08). Every visual decision traces back to a behavioral intention. Nothing is decorative.

---

## Visual Language Philosophy

### Function over decoration
Every visual choice serves a purpose. Color communicates meaning. Elevation communicates hierarchy. Density communicates efficiency. If a visual property does not inform, guide, or provide feedback, it does not belong.

### Consistency over novelty
The visual language is consistent across all screens, recipes, and compositions. Visual novelty is reserved for communicating exceptional states (errors, alerts, completions), not for differentiating screens.

### Clarity over style
Readability, scannability, and comprehension come before aesthetic preferences. A visually appealing interface that slows down an operator is a failed design.

### Accessibility as identity
The visual language is designed for accessibility from the foundation, not as a compliance layer. High contrast, color independence, and readability are defining characteristics — not constraints.

### Restraint over richness
The platform uses a deliberately constrained visual vocabulary. Fewer colors, fewer elevations, fewer icon styles. Richness comes from composition and information density, not from visual embellishment.

---

## Color

### Color philosophy
Color in this platform is **semantic**, not decorative. Every color choice communicates meaning. No color is used purely for visual variety.

### Color categories

#### Neutral palette
The foundation of the interface. Neutrals define the background, surface, text, and border hierarchy.

**Principles:**
- Neutrals provide the backdrop for all content. They should recede visually.
- Text contrast is the primary driver of neutral values.
- Surface differentiation is achieved through subtle neutral shifts, not color.
- Dark mode is a first-class concern, not an afterthought.

**Roles:**
- `bg.primary` — Main page background
- `bg.secondary` — Surface background (cards, panels)
- `bg.tertiary` — Raised surface background (dropdowns, tooltips)
- `text.primary` — Primary content
- `text.secondary` — Supporting content
- `text.disabled` — Disabled or inactive content
- `border.default` — Standard container borders
- `border.subtle` — Minimal separation (dividers)

#### Accent / Brand palette
The primary interactive color. Used for primary actions, active states, links, and focused elements.

**Principles:**
- One accent color. Not a palette.
- Accent is used sparingly — only for interactive and active elements.
- Accent signals "this is something you can interact with."
- Accent must meet WCAG AA contrast on all surfaces.

**Roles:**
- `interactive.primary` — Primary action buttons, active navigation
- `interactive.primary.hover` — Hover state
- `interactive.primary.active` — Pressed state
- `text.link` — Inline links (may be same as interactive.primary)
- `focus.ring` — Focus indicator

#### Status palette
Communicates system and process state. Used for status indicators, badges, alerts, and progress indicators.

**Principles:**
- Status colors are universally recognizable: green = good, yellow = caution, red = error, blue = information.
- These colors are never used for decorative purposes.
- Status colors appear in context — a red badge means "error," not "brand accent."
- Each status color has a text variant, background variant, and border variant.

**Roles:**
- `status.success` — Healthy, complete, confirmed
- `status.warning` — Degraded, pending, needs attention
- `status.error` — Failed, critical, blocked
- `status.info` — Informational, neutral update
- `status.neutral` — Inactive, paused, idle

#### Severity palette
Communicates the urgency or impact level of findings, alerts, and recommendations. Partially overlaps with status but is distinct — a finding can be severity=low with status=open.

**Roles:**
- `severity.critical` — Immediate attention required
- `severity.high` — High impact, needs review
- `severity.medium` — Moderate impact, monitor
- `severity.low` — Minor, informational
- `severity.none` — No severity classification

#### Data visualization palette
Used for charts, graphs, and data-driven visualizations.

**Principles:**
- Chart colors are perceptually distinct (not relying on hue alone).
- Chart colors are colorblind-safe (Okabe-Ito or similar palette).
- Chart colors work on both light and dark backgrounds.
- Chart colors are ordered by usage frequency (series 1 is most common).

### Color independence
- No information is conveyed by color alone.
- Status combines shape + icon + text + color.
- Severity combines icon + text + color.
- Links combine underline + color.
- Charts combine pattern + label + color.

### Dark mode philosophy
- Dark mode is not an inverted light mode.
- Dark mode uses a different neutral scale optimized for dark adaptation.
- Accent colors may be slightly brighter in dark mode to maintain perceived contrast.
- Status colors maintain their semantic meaning but may shift in saturation.
- Shadows invert or disappear (elevation uses background color instead).

---

## Elevation

### Elevation philosophy
Elevation visualizes the conceptual hierarchy of interface layers. Higher elevation elements appear closer to the user. Elevation is never decorative — it always communicates a structural relationship.

### Elevation levels

| Level | Name | Purpose | Visual cues |
|-------|------|---------|-------------|
| 0 | Surface | Base content layer | No shadow; flat background |
| 1 | Raised | Cards, panels, dropdowns | Subtle shadow; slight background shift |
| 2 | Overlay | Side panels, dialogs | Noticeable shadow; distinct background |
| 3 | Modal | Modal dialogs | Pronounced shadow; scrim backdrop |
| 4 | Notification | Toasts, popovers, tooltips | Most prominent; closest to user |

### Elevation principles
- Elements at the same elevation level never overlap.
- A child at a higher elevation implies a temporary or focused relationship.
- Elevation changes are animated (consistent with motion tokens).
- Dark mode: elevation is communicated through background color shifts rather than shadows.
- Scrim (backdrop overlay) is used for modal elevation only.

---

## Density

### Density philosophy
Density defines how tightly interface elements are packed. The platform supports multiple density modes to accommodate different user preferences and task contexts.

### Density spectrum

| Mode | Use case | Characteristics |
|------|----------|-----------------|
| Compact | Data-dense screens, monitoring, lists | Reduced padding, smaller typography, tighter spacing |
| Default | Most screens, balanced reading | Standard padding, base typography, comfortable spacing |
| Relaxed | Review screens, settings, onboarding | Generous padding, larger touch targets, ample whitespace |
| Spacious | Presentations, demos, focus mode | Maximum breathing room, reduced content density |

### Density principles
- Density changes spacing token values, not primitive structure.
- All density modes maintain minimum touch target sizes (44x44px).
- Density is user-selectable (persisted in user preferences).
- Default density is the designed baseline — compact and relaxed are adaptations.
- Density mode does not affect content legibility (contrast, typography remain constant).

---

## Shadows

### Shadow philosophy
Shadows communicate elevation. They are not decorative. The platform uses a minimal shadow vocabulary.

### Shadow characteristics
- Soft, not sharp — shadows diffuse rather than outline.
- Directional: light source from above (consistent with reading direction).
- Multi-layer: a component shadow + a contact shadow for realism.
- Duration: elevation changes animate over motion tokens.

### Shadow rules
- Same elevation = same shadow. No custom shadows per component.
- Text never has shadows.
- Interactive elements do not cast shadows on hover (elevation is for hierarchy, not feedback).
- Dark mode: shadows are reduced or eliminated; elevation communicated via background color.

---

## Borders

### Border philosophy
Borders define separation, containment, and hierarchy. They are minimal and functional.

### Border hierarchy

| Level | Purpose | Visual weight |
|-------|---------|---------------|
| Subtle | Dividers, separators between sections | Lightest weight, low contrast |
| Default | Container boundaries, card outlines | Medium weight, moderate contrast |
| Strong | Focus indicators, active selections | Heavier weight, high contrast |
| Accent | Interactive element boundaries, active state | Accent color, medium weight |

### Border principles
- Borders are secondary to spacing as a separation mechanism. Spacing should separate before borders.
- Borders always use rounded corners (radius tokens).
- Cards use borders OR elevation — never both.
- Focus indicators use a focus ring (offset from element), not a border change.

---

## Iconography

### Icon philosophy
Icons communicate meaning at a glance. They are simple, consistent, and semantically clear.

### Icon characteristics
- **Style:** Line icons with consistent stroke weight. Filled variants for active/selected states only.
- **Size:** Small (16px), medium (20px), large (24px). All icons render at their defined size — no scaling.
- **Weight:** Consistent stroke width across all icons.
- **Corners:** Rounded caps and joins throughout.
- **Grid:** All icons sit on a consistent bounding box with consistent internal padding.

### Icon roles

| Role | Usage | Size |
|------|-------|------|
| Navigation | Sidebar, top nav items | Medium (20px) |
| Action | Buttons, toolbar items | Small (16px) |
| Status | Status indicators, badges | Small (16px) |
| Severity | Severity indicators | Small (16px) |
| Inline | In text, messages | Matches text line height |
| Section | Section headers, empty states | Large (24px) |
| Illustration | Full empty states, onboarding | Custom (not a standard icon) |

### Icon principles
- Every icon has a text label nearby or available via tooltip.
- Icons are never the sole communication of meaning.
- Icon set is curated — no duplicate or near-duplicate icons.
- New icons must match the established style (stroke, weight, corner treatment).
- Animated icons are reserved for progress/loading states only.

---

## Charts

### Chart philosophy
Charts present data for analysis, not decoration. Every chart must enable the viewer to extract accurate information quickly.

### Chart types

| Type | Use when | Example |
|------|----------|---------|
| Line chart | Showing trends over time | Health score over evaluation windows |
| Bar chart | Comparing discrete values | Capability scores side by side |
| Gauge | Showing a single value against a target | Overall evaluation score |
| Sparkline | Compact trend in limited space | Metric trend in a card |
| Scatter plot | Showing distribution or correlation | Latency vs throughput |
| Heat map | Showing density or concentration | Error distribution across time/capability |
| Table | Showing exact values for comparison | Metric comparison with deltas |

### Chart principles
- Charts always have labels — never assume the viewer understands the axes without reading.
- Charts support hover/tap for exact values.
- Charts have consistent color assignment (data palette).
- Charts are colorblind-safe (pattern + color).
- Time-series charts support range selection.
- Charts respect reduced motion (no animated entrance).
- Sparklines have the same height-to-width ratio throughout the platform.

### Chart layout
- Chart height is determined by data density, not container size.
- Charts have consistent padding and axis styling.
- Grid lines are minimal (light weight, low contrast).
- Legends are placed above or to the right of the chart.

---

## Illustrations

### Illustration philosophy
Illustrations are used sparingly — primarily for empty states, onboarding, and error pages. They provide context and reduce anxiety in uncertain situations.

### Illustration roles

| Role | Usage | Style |
|------|-------|-------|
| Empty state | "No data yet" screens | Simplified scene with platform elements |
| Onboarding | First-time user guidance | Step-by-step visual explanations |
| Error | "Something went wrong" | Reassuring, not alarming |
| Success | "All clear" confirmation | Positive affirmation |

### Illustration principles
- Illustrations are used only when they serve a communication purpose.
- Illustrations are never purely decorative.
- Illustration style is consistent: flat, geometric, limited color palette (neutral + one accent).
- Illustrations include an accessible text alternative.
- Illustrations do not animate.
- New illustrations must match the established style guide.

---

## Typography (Visual)

### Typography philosophy
Typography is the primary communication medium. It must be readable, scannable, and hierarchically clear at all sizes and densities.

### Typeface
- **Body:** A single, widely-available sans-serif typeface with multiple weights.
- **Code:** A single monospace typeface for code and technical content.
- Both typefaces are chosen for readability at small sizes and on screens.

### Type scale
A modular scale defines the relationship between type sizes. The scale is limited — size is determined by role, not by arbitrary choice.

| Role | Weight | Relative size |
|------|--------|---------------|
| Page title (h1) | Bold | Largest |
| Section title (h2) | Bold | Large |
| Card title (h3) | Semibold | Medium-large |
| Widget header (h4) | Semibold | Medium |
| Body | Regular | Base |
| Secondary | Regular | Slightly smaller |
| Caption | Regular | Small |
| Code | Regular | Monospace |

### Typography principles
- Line length: 45–75 characters for body text.
- Line height: proportional to role (headings tighter, body more open).
- Font weight is used for hierarchy, not emphasis. Emphasis uses italic or color.
- All caps is reserved for labels and badges only (never for body or headings).
- Number alignment: tabular figures in data contexts, proportional figures in prose.
- Text is never compressed or stretched.

---

## Layout (Visual)

### Layout philosophy
Layout is the spatial organization of primitives and compositions. It follows the grid and spacing foundations.

### Visual rhythm
- Content is organized into clear vertical and horizontal rhythm.
- Related elements share alignment edges.
- White space is active — it communicates grouping and separation.
- Left alignment is the default for text-heavy interfaces.

### Visual balance
- Asymmetric layouts are preferred (information is rarely symmetrical).
- Weight is balanced by visual mass, not mathematical symmetry.
- Action areas (toolbars, decision panels) are placed at predictable locations.

### Visual flow
- Reading order follows the natural flow (left-to-right, top-to-bottom for LTR locales).
- The most important content is at the top-left.
- The primary action is at the end of the content flow (bottom-right).
- Scanning is supported by consistent alignment and spacing.

---

## Visual Hierarchy Principles

### What creates hierarchy
1. **Size** — Larger elements are perceived as more important.
2. **Weight** — Heavier typography draws attention.
3. **Color** — Higher contrast elements are more prominent.
4. **Position** — Top-left is the primary zone.
5. **Spacing** — More space around an element makes it stand out.
6. **Elevation** — Higher elevation elements appear more important.

### What does NOT create hierarchy
- Decorative backgrounds
- Unnecessary borders
- Excessive whitespace
- Animation (reserved for state changes)

### Hierarchy rules
- No more than 3 levels of visual hierarchy on any screen.
- The primary action is always the most visually prominent interactive element.
- Informational elements never compete with actionable elements.
- Hierarchy is consistent across screens — the same element type has the same visual weight everywhere.

---

## Theme Philosophy

### Light mode
The default and primary mode. Optimized for well-lit environments typical of professional workspaces.

### Dark mode
A first-class theme, not an afterthought. Optimized for low-light environments and extended screen time.

### Theme principles
- Theme changes are implemented through token value swaps only — no structural changes.
- All primitives and compositions work in both themes without modification.
- Theme is user-selectable (light, dark, system) and persisted.
- Theme transition is animated (consistent with motion tokens).
- New visual elements must be designed for both themes simultaneously.

---

## Visual Anti-Patterns

| Anti-pattern | Problem | Remedy |
|---|---|---|
| Decorative color | Color used without semantic meaning | Remove color or assign a semantic role |
| Shadow overload | Every element casts a shadow | Only elevated elements cast shadows |
| Border overuse | Every section uses borders | Replace with spacing first, borders second |
| Icon inconsistency | Icons with different stroke weights | Audit against icon style guide |
| Chart complexity | Charts with too many series or dimensions | Simplify to the minimum needed for the decision |
| Typography explosion | More than 2 typefaces or 6 sizes | Consolidate to the modular scale |
| Visual noise | Gradients, patterns, backgrounds competing with content | Remove; content is the hero |
| Theme neglect | Only designed for light mode | Every visual decision must account for both themes |
| Density ignoring | One density for all screens | Default density is the baseline; adapt |
| Color-only information | Status or severity conveyed by color alone | Always pair with icon, text, or shape |

---

## Accessibility Integration

The visual language embeds accessibility at every level:

- **Color:** All combinations meet WCAG AA. Color is never the sole information channel.
- **Typography:** Readable sizes, sufficient line height, adequate contrast.
- **Focus:** Visible focus indicators on all interactive elements.
- **Motion:** All animations respect `prefers-reduced-motion`.
- **Touch:** Minimum 44x44px touch targets in all density modes.
- **Screen reader:** Visual hierarchy mirrors document structure (h1–h6).
- **Dark mode:** Same contrast and readability as light mode.

---

## Visual Language Evolution

### Adding a new visual concept
1. **Identify the gap** — What behavioral intent is not expressed visually?
2. **Verify necessity** — Can an existing visual property express it?
3. **Define semantics** — What does the new concept mean?
4. **Define behavior** — How does it change across states, themes, and contexts?
5. **Document** — Add to this document with principles, not values.
6. **Prototype** — Test in both themes, all densities, and accessibility constraints.

### Deprecating a visual concept
1. **Mark deprecated** — Note in this document; do not use in new screens.
2. **Migration path** — Document what replaces it.
3. **Remove** — After the migration period, remove from the visual language.

---

## Relationship to Other Documents

| Document | Relationship |
|---|---|
| 08-interaction-principles.md | Visual language is a direct expression of interaction principles |
| 13-state-model.md | State transitions determine the visual state representation |
| 17-design-system-architecture.md | Primitives and compositions consume visual tokens |
| 19-motion-feedback.md | Motion brings visual properties to life |
| 20-notifications.md | Notification appearance follows visual language |

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-07-25 | Architecture | Initial visual language definition |
