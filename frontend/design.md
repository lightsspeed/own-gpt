# Design System & UI Specification

> **Version:** 1.0
> **Stack:** React 19 + Tailwind CSS 3 + shadcn/ui + Lucide + Inter
> **Theme:** Dark-only, deep navy base

---

## Design Principles

1. **Calm** — every element has its place. No competing focal points.
2. **Spacious** — whitespace is the primary layout tool, not borders.
3. **Consistent** — one spacing scale, one type scale, one radius set. No exceptions.
4. **Honest** — the UI reveals how the answer was produced (mode badge, debug panel).
5. **Fast** — micro-interactions are 150–250 ms. Nothing feels sluggish.

---

## Color System

### Base palette (CSS variables in `index.css`)

| Token               | HSL                              | Usage                          |
|---------------------|----------------------------------|--------------------------------|
| `--background`      | `222 50% 7%`                     | Page background                |
| `--foreground`      | `210 60% 97%`                    | Primary text                   |
| `--card`            | `222 48% 9%`                     | Card / elevated surfaces       |
| `--card-foreground` | `210 60% 97%`                    | Text on card                   |
| `--primary`         | `221 90% 55%`                    | Buttons, links, active states  |
| `--primary-foreground` | `0 0% 100%`                   | Text on primary                |
| `--secondary`       | `220 40% 14%`                    | Subtle surfaces (hover, nav)   |
| `--secondary-foreground` | `210 60% 97%`               | Text on secondary              |
| `--muted`           | `220 40% 14%`                    | Background for muted elements  |
| `--muted-foreground`| `215 25% 58%`                    | Secondary text, metadata       |
| `--accent`          | `220 40% 18%`                    | Hover states, subtle highlights|
| `--accent-foreground` | `210 60% 97%`                 | Text on accent                 |
| `--border`          | `220 35% 16%`                    | Borders, dividers              |
| `--ring`            | `221 90% 55%`                    | Focus rings                    |
| `--radius`          | `0.75rem` (12px)                 | Default border radius          |

### Semantic colors (add to Tailwind extend)

Add these as Tailwind colors for badges, alerts, and state indicators:

```js
colors: {
  success: {
    DEFAULT: 'hsl(152 60% 40%)',
    bg:    'hsl(152 60% 40% / 0.15)',
    text:  'hsl(152 60% 70%)',
    border:'hsl(152 60% 40% / 0.25)',
  },
  warning: {
    DEFAULT: 'hsl(38 90% 50%)',
    bg:    'hsl(38 90% 50% / 0.15)',
    text:  'hsl(38 90% 75%)',
    border:'hsl(38 90% 50% / 0.25)',
  },
  danger: {
    DEFAULT: 'hsl(0 68% 50%)',
    bg:    'hsl(0 68% 50% / 0.15)',
    text:  'hsl(0 68% 75%)',
    border:'hsl(0 68% 50% / 0.25)',
  },
  info: {
    DEFAULT: 'hsl(221 90% 55%)',
    bg:    'hsl(221 90% 55% / 0.15)',
    text:  'hsl(221 90% 75%)',
    border:'hsl(221 90% 55% / 0.25)',
  },
  grounded: {   // BookOpen blue
    bg:    'hsl(221 90% 55% / 0.15)',
    text:  'hsl(221 90% 75%)',
    border:'hsl(221 90% 55% / 0.25)',
  },
  hybrid: {    // Puzzle purple
    bg:    'hsl(270 60% 50% / 0.15)',
    text:  'hsl(270 60% 75%)',
    border:'hsl(270 60% 50% / 0.25)',
  },
  synthesis: {  // Lightbulb amber
    bg:    'hsl(38 90% 50% / 0.15)',
    text:  'hsl(38 90% 75%)',
    border:'hsl(38 90% 50% / 0.25)',
  },
}
```

### Usage rules

- Never use opaque borders on cards — use `border-white/5` or `border-white/10`
- Surface hierarchy is expressed through brightness, not shadows
- Glass effect (`glass-panel`) only on floating elements (header, input bar, modals)

---

## Typography

Font: **Inter** (300–700 weight range, already loaded via Google Fonts).

| Token         | Size  | Weight | Line Height | Usage                              |
|---------------|-------|--------|-------------|------------------------------------|
| `display`     | 32px  | 600    | 1.2         | Welcome screen, empty states       |
| `h1`          | 28px  | 600    | 1.25        | Page titles (settings, KB)         |
| `h2`          | 24px  | 600    | 1.3         | Section headers                    |
| `h3`          | 20px  | 600    | 1.35        | Card titles, modal headers         |
| `title`       | 18px  | 600    | 1.4         | Chat history item titles           |
| `body`        | 15px  | 400    | 1.6         | Message content, input text        |
| `small`       | 13px  | 500    | 1.4         | Labels, mode badges, source cards  |
| `caption`     | 12px  | 400    | 1.4         | Metadata, timestamps, debug panel  |
| `micro`       | 11px  | 500    | 1.3         | Badge metadata, tooltips           |

Add these as Tailwind utilities:

```js
fontSize: {
  'display': ['32px', { lineHeight: '1.2', fontWeight: '600' }],
  'h1':      ['28px', { lineHeight: '1.25', fontWeight: '600' }],
  'h2':      ['24px', { lineHeight: '1.3', fontWeight: '600' }],
  'h3':      ['20px', { lineHeight: '1.35', fontWeight: '600' }],
  'title':   ['18px', { lineHeight: '1.4', fontWeight: '600' }],
  'body':    ['15px', { lineHeight: '1.6', fontWeight: '400' }],
  'small':   ['13px', { lineHeight: '1.4', fontWeight: '500' }],
  'caption': ['12px', { lineHeight: '1.4', fontWeight: '400' }],
  'micro':   ['11px', { lineHeight: '1.3', fontWeight: '500' }],
},
```

---

## Spacing

Only these values. No exceptions.

```
4   8   12   16   20   24   32   40   48   64
```

**8px rhythm:** all vertical spacing should be a multiple of 8 (8, 16, 24, 32, 40…).  
Inner padding can use 4px granularity (4, 12, 20).

### Common patterns

| Context                                | Value |
|----------------------------------------|-------|
| Padding inside cards / panels          | 16px  |
| Gap between message groups             | 24px  |
| Gap between answer and metadata        | 16px  |
| Gap between paragraphs in answer       | 16px  |
| Gap between resources section and mode | 12px  |
| Stack gap (sidebar items, chat list)   | 4px   |
| Icon gap in inline badges              | 6px   |
| Container max-width (chat content)     | 800px |
| Input bar horizontal padding           | 16px  |
| Input bar vertical padding             | 12px  |

---

## Border Radius

| Token  | Value  | Usage                              |
|--------|--------|------------------------------------|
| `xs`   | 6px    | Inputs, small badges               |
| `sm`   | 8px    | Buttons, source chips              |
| `md`   | 12px   | Cards, panels, modals (base)       |
| `lg`   | 16px   | Message bubbles, large cards       |
| `xl`   | 20px   | User message bubble                |
| `full` | 9999px | Pills, avatars, rounded badges     |

---

## Shadows

Only three levels:

```js
boxShadow: {
  'sm':    '0 1px 3px 0 rgb(0 0 0 / 0.3)',
  'md':    '0 4px 12px 0 rgb(0 0 0 / 0.4)',
  'lg':    '0 8px 32px 0 rgb(0 0 0 / 0.5)',
  'glow':  '0 0 20px hsl(221 90% 55% / 0.35), 0 0 60px hsl(221 90% 55% / 0.1)',
  'inner': 'inset 0 1px 0 0 rgb(255 255 255 / 0.05)',
}
```

- `sm` — subtle elevation for interactive hover
- `md` — floating elements (input bar, tooltips, dropdowns)
- `lg` — modals, side panels
- `glow` — primary button, active/focused state (sparingly)
- `inner` — inset highlight on cards for depth

---

## Animations

### Timing

| Context              | Duration | Easing                   |
|----------------------|----------|--------------------------|
| Hover transitions    | 150ms    | `ease-out`               |
| UI state changes     | 200ms    | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Panel expand/collapse| 250ms    | `ease-in-out`            |
| Page transitions     | 300ms    | `ease-in-out`            |
| Micro-interactions   | 100–150ms| `ease-out`               |

### Keyframes to add

```js
keyframes: {
  'fade-in': {
    from: { opacity: 0 },
    to:   { opacity: 1 },
  },
  'fade-in-up': {
    from: { opacity: 0, transform: 'translateY(8px)' },
    to:   { opacity: 1, transform: 'translateY(0)' },
  },
  'slide-down': {
    from: { opacity: 0, transform: 'translateY(-4px)' },
    to:   { opacity: 1, transform: 'translateY(0)' },
  },
  'scale-in': {
    from: { opacity: 0, transform: 'scale(0.95)' },
    to:   { opacity: 1, transform: 'scale(1)' },
  },
}
```

### When to use

| Animation    | Element                                                 |
|-------------|----------------------------------------------------------|
| `fade-in`   | New messages appearing in chat                           |
| `fade-in-up`| Streaming text chunks, tool event pills                  |
| `slide-down`| Debug panel, dropdowns, tooltips                         |
| `scale-in`  | Modals, dialogs                                          |
| `hover:lift`| Cards on hover (`transform: translateY(-2px)`)           |

---

## Layout

### Page structure

```
┌──────────────────────────────────────────────────┐
│  Header (48px)                                   │
│  ┌────────────┬────────────────────────────────┐ │
│  │            │                                │ │
│  │  Sidebar   │   Main Content                 │ │
│  │  (260px)   │   (max-width: 800px)           │ │
│  │            │                                │ │
│  │            │   ┌────────────────────┐       │ │
│  │            │   │  Messages           │       │ │
│  │            │   │                     │       │ │
│  │            │   │  ↓ scroll           │       │ │
│  │            │   │                     │       │ │
│  │            │   └────────────────────┘       │ │
│  │            │   ┌────────────────────┐       │ │
│  │            │   │  Input Bar (fixed) │       │ │
│  │            │   └────────────────────┘       │ │
│  └────────────┴────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

### Header
- Height: 48px
- Background: `glass-panel` (no bottom border)
- Elements: sidebar toggle, logo + model badge, right: live indicator + buttons
- Sticky top, highest z-index among content layer

### Sidebar
- Width: 260px
- Background: `--background` (same as page, no border)
- Sections: New Chat button, Chat History list, bottom: Knowledge Base + Settings
- Each section separated by 8px of whitespace, not a line

### Chat content area
- Max-width: 800px (Tailwind `max-w-3xl` is 768px — bump to custom `max-w-[800px]`)
- Centered with auto margins
- Padding top: 80px (to clear header)
- Padding bottom: 200px (to clear input bar)

### Input bar
- Fixed to bottom, floating above content
- Max-width matches chat content (800px)
- `glass-panel` effect with backdrop blur
- Border radius: 16px (lg)
- Padding: 12px 16px

---

## Component Design

### ChatMessage (Assistant)

```
┌────────────────────────────────────┐
│                                    │
│  Answer text (body, 15px)         │
│                                    │
│  ┌──────────────────────────────┐  │
│  │ 📖 Grounded · Hybrid Search  │  │
│  │ 5 chunks · 2 documents       │  │
│  │ ▶ Why this answer?           │  │
│  └──────────────────────────────┘  │
│                                    │
│  Sources                           │
│  [📄 AWS CDK.pdf] [📄 Well-Arch…] │
│                                    │
│  [Copy] [Like] [Dislike]           │
│                                    │
└────────────────────────────────────┘
```

- No border, no background on the message container
- Whitespace between answer and metadata: 20px
- Metadata section is a compact card (bordered, subtle bg)
- Source chips are pills with `small` font size
- Action buttons appear on hover, subtle fade

### ChatMessage (User)

```
                    ┌────────────────────┐
                    │  Question text     │
                    │  (body, 15px)      │
                    └────────────────────┘
```

- Right-aligned, max-width 75%
- Background: `--secondary` (not a bright bubble — subtle)
- Border radius: 20px top-right, 12px rest
- No shadow, no border

### SourceCard (pill chip)

```
[📄 filename.pdf]
```

- Icon: `FileText` (file) or `Globe` (web)
- Font: `small` (13px)
- Border radius: `full` (pill shape)
- Background: tonal 10% opacity
- Hover: slight lift + tooltip with snippet preview
- Max-width: 220px with truncation

### AnswerMode badge

```
┌──────────────────────────────┐
│ 📖 Grounded · Hybrid Search  │  ← one row
│ 5 chunks · 2 documents       │  ← subtitle row
└──────────────────────────────┘
```

- Compact card: `rounded-xl`, `px-3 py-2`
- Icon + label row: `small` (13px) semibold
- Metadata row: `micro` (11px) 70% opacity
- No hover effect (informational, not interactive)

### DebugPanel (collapsible)

```
▶ Why this answer?               ← toggle (caption, 12px)

┌──────────────────────────────┐  ← expanded content
│ Retriever    Hybrid (V+BM25) │
│ Chunks       20 → 5          │
│ Documents   2                │
│ Mode        hybrid            │
│ Confidence  73%               │
└──────────────────────────────┘
```

- Toggle: `caption` size, low opacity, hover brightens
- Expanded panel: `rounded-lg`, `bg-black/20`, `border-white/5`
- Key-value rows: `caption` size, monospace values
- Expand/collapse animation: 200ms `slide-down`

### KnowledgeBase card (future)

```
┌────────────────────────────────────┐
│ 📄  →  terraform.pdf               │
│   126 chunks · Updated yesterday   │
│   2.4 MB                           │
│   [Delete]                         │
└────────────────────────────────────┘
```

- Each document is a bordered card (`rounded-xl`)
- Icon: `FileText` with file type color
- Metadata: `caption` size
- Hover: subtle `sm` shadow + `translateY(-1px)`
- Search bar above with filter toggle

---

## Interaction Patterns

| Pattern              | Behavior                                              |
|----------------------|-------------------------------------------------------|
| Hover on sources     | Pill lifts 1px, tooltip shows snippet after 300ms    |
| Click on web source  | Opens URL in new tab                                  |
| Toggle debug panel   | 200ms slide-down animation, chevron rotates           |
| Copy button          | 150ms scale + fade feedback, resets after 2s          |
| Like/dislike         | 100ms scale pulse, icon fills                          |
| Edit message         | Click populates input bar, scrolls to top             |
| Streaming text       | Fade-in-up 100ms per chunk, shows blinking cursor    |
| Tool event pills     | Appear with fade-in, bounce dots during call          |
| Sidebar hover        | Item bg brightens 150ms                               |
| New chat             | Fade out current messages, slide in empty state       |

---

## Accessibility

- All interactive elements focusable via keyboard
- Visible focus ring (`ring-2 ring-ring ring-offset-2`) on all controls
- Color contrast: all text meets WCAG AA (4.5:1 ratio minimum)
- Semantic color tokens are never the only differentiator — always pair with icon or label
- `aria-expanded` on collapsible panels
- `aria-label` on icon-only buttons
- Reduce motion: respect `prefers-reduced-motion` by disabling decorative animations

---

## Responsive behavior

| Breakpoint | Sidebar | Chat width | Input bar       |
|------------|---------|------------|-----------------|
| ≥ 1024px   | Visible | 800px      | 800px centered  |
| 768-1023px | Overlay | 90vw       | 90vw centered   |
| < 768px    | Overlay | 95vw       | 95vw centered   |

- Sidebar collapses to overlay on mobile with backdrop blur
- Header shrinks to 40px on mobile
- Action buttons move below answer on very narrow screens

---

## Component inventory (current + planned)

| Component        | Status     | Priority |
|------------------|------------|----------|
| ChatMessage      | Redesign   | P0       |
| SourceCard       | Polish     | P0       |
| AnswerMode badge | New        | P0       |
| DebugPanel       | New        | P0       |
| Header           | Redesign   | P1       |
| Sidebar          | Redesign   | P1       |
| InputBar         | Redesign   | P1       |
| KnowledgeCard    | Redesign   | P1       |
| SettingsDialog   | Redesign   | P1       |
| WelcomeScreen    | Redesign   | P1       |
| SkeletonLoader   | New        | P2       |
| EmptyState       | New        | P2       |
| Toast            | New        | P2       |
| Onboarding       | New        | P3       |

---

## Implementation order

**Milestone 1 — Foundation (2–3 days)**
1. Update `tailwind.config.js` with new tokens (colors, font sizes, spacing, shadows, radii, animations)
2. Update `index.css` with new semantic color variables
3. Remove `App.css` (old boilerplate)
4. Audit all existing components and replace magic numbers with tokens
5. Verify the new tokens produce a cohesive page

**Milestone 2 — Chat Experience (3–5 days)**
1. Redesign `ChatMessage` — remove borders, use whitespace, apply type scale
2. Redesign `SourceCard` — pill chips with tooltip preview
3. Refine `AnswerMode` badge — compact card layout
4. Polish `DebugPanel` — smooth slide-down, proper toggle
5. Widen chat container to 800px
6. Refine `InputBar` — glass effect, proper padding
7. Redesign `Header` — 48px, clean layout
8. Redesign `Sidebar` — spacing, typography, no unnecessary icons

**Milestone 3 — Knowledge Base + Settings (2–3 days)**
1. Redesign KB list as document cards with search
2. Redesign Settings dialog with proper sections
3. Add skeleton loaders for history, KB list
4. Add streaming cursor animation
5. Add message fade-in animation

**Milestone 4 — Polish (2–3 days)**
1. Hover animations on all interactive elements
2. Focus states and keyboard navigation audit
3. Empty states for sidebar (no chats), KB (no docs)
4. Responsive sidebar overlay behavior
5. `prefers-reduced-motion` support
6. Final contrast and spacing audit
