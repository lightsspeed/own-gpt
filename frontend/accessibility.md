# Accessibility Specification

> Target: **WCAG 2.2 Level AA** compliance across all screens.
> Every component in `components.md` has accessibility requirements. This document defines shared rules.

---

## Standards

| Standard | Target | Notes |
|----------|--------|-------|
| WCAG 2.2 | AA     | All new and redesigned content |
| EN 301 549 | Compliant | EU public procurement standard |
| ARIA 1.3 | Authoring practices | Follow APG patterns |

---

## Color contrast

| Token pair                              | Required ratio | Measured |
|-----------------------------------------|----------------|----------|
| Foreground on background                | 4.5:1          | AA       |
| Muted-foreground on background          | 3:1            | AA large |
| Primary text on primary bg              | 4.5:1          | AA       |
| Border on background                    | 3:1            | AA       |
| Disabled text on background             | 3:1            | AA       |
| Error text on background                | 4.5:1          | AA       |

All HSL values in `index.css` have been designed to meet these ratios on the `--background` surface (#0a0e1a equivalent). Verify with a contrast checker before shipping.

### What to check
- [ ] All text meets 4.5:1 (normal text) or 3:1 (large text ≥18px bold or ≥24px)
- [ ] Placeholder text meets 4.5:1 (not just 3:1)
- [ ] Focus ring meets 3:1 against adjacent background
- [ ] Disabled controls meet 3:1 but are distinguishable from enabled
- [ ] Icons conveying information meet 3:1

---

## Keyboard navigation

### Global

| Key       | Action                              |
|-----------|-------------------------------------|
| Tab       | Move focus forward through controls |
| Shift+Tab | Move focus backward                 |
| Enter     | Activate focused control            |
| Space     | Activate focused button / toggle    |
| Escape    | Close modal / dropdown / panel      |
| Ctrl+B    | Toggle sidebar                      |
| Ctrl+Enter | Send message (from input)          |

### Focus order

Focus follows visual order (left to right, top to bottom). The expected tab order:

```
Sidebar toggle → Header actions → Message area → Message actions → Input bar → Send
```

### Focus indicator

```css
/* Default (matches tailwind.config ring token) */
:focus-visible {
  outline: 2px solid hsl(var(--ring));
  outline-offset: 2px;
  border-radius: 6px;
}

/* Custom shadcn/ui compatible */
.ring-ring {
  --tw-ring-color: hsl(var(--ring));
}
```

- [ ] All interactive elements have visible focus indicator
- [ ] Focus indicator contrast is ≥ 3:1 against adjacent background
- [ ] `:focus-visible` is used (not `:focus`) to avoid mouse-users seeing focus rings
- [ ] Custom components use `tabindex` appropriately

---

## ARIA patterns

### Landmarks

| Region          | Role                | aria-label            |
|-----------------|---------------------|-----------------------|
| Header          | `banner`            | –                     |
| Sidebar         | `navigation`        | "Chat history"        |
| Main content    | `main`              | –                     |
| Input area      | –                   | –                     |
| Chat messages   | `log`               | "Conversation"        |
| Knowledge Base  | `region`            | "Knowledge base"      |

### Interactive elements

| Element                | Pattern                           |
|------------------------|-----------------------------------|
| Sidebar toggle         | `aria-controls="sidebar"`, `aria-expanded` |
| Message actions (copy, like, dislike) | `aria-label`, `aria-pressed` on feedback |
| Collapsible (why this answer) | `aria-expanded`, `aria-controls` |
| Tabs (settings)        | `role="tablist"`, `role="tab"`, `aria-selected` |
| Modal                  | `role="dialog"`, `aria-modal="true"` |
| Tooltip                | `role="tooltip"`, `aria-describedby` |
| Upload progress        | `role="status"`, `aria-live="polite"` |
| Streaming content      | `aria-live="polite"`, `aria-atomic="false"` |

### Live regions

| Context                | aria-live | aria-atomic | Notes                         |
|------------------------|-----------|-------------|-------------------------------|
| Streaming answer text  | `polite`  | `false`     | Only new tokens are announced |
| Upload progress        | `polite`  | `true`      | Whole status is announced     |
| Error banner           | `assertive`| `true`     | Must interrupt                |
| Tool event pill        | `polite`  | `true`      | "Searching knowledge base…"   |

---

## Screen reader annotations

### ChatMessage

```html
<div role="log" aria-label="Conversation" aria-live="polite" aria-atomic="false">
  <div aria-label="Assistant message: What is AWS CDK? The AWS Cloud Development Kit…">
    <p>Answer content…</p>
    <div aria-label="Answer mode: grounded. 5 chunks from 2 documents.">…</div>
    <div aria-label="Sources: AWS CDK.pdf, aws_well_architected_framework.pdf">…</div>
  </div>
</div>
```

### DebugPanel

```html
<button aria-expanded="false" aria-controls="debug-panel-content">
  ▶ Why this answer?
</button>
<div id="debug-panel-content" role="region" aria-label="Pipeline details" hidden>
  …
</div>
```

### Toolbar

```html
<div aria-label="Message actions">
  <button aria-label="Copy message">…</button>
  <button aria-label="Like" aria-pressed="false">…</button>
  <button aria-label="Dislike" aria-pressed="false">…</button>
</div>
```

---

## Focus management

| Action                          | Focus moves to                         |
|---------------------------------|----------------------------------------|
| Open modal                      | First focusable input                  |
| Close modal                     | Element that triggered the modal       |
| Open sidebar (overlay)          | First sidebar item                     |
| Close sidebar (overlay)         | Sidebar toggle button                  |
| New message appears             | No focus change (stays in input)       |
| Upload completes                | No focus change                        |
| Error appears                   | Error banner (if assertive)            |
| After send                      | Input (for next message)               |

### Implementation pattern

```tsx
// useFocusTrap for modals
const FocusTrap = ({ children }: { children: React.ReactNode }) => {
  const ref = useRef<HTMLDivElement>(null);
  // Tab/Shift+Tab cycle within ref
  // Escape closes
};

// useRestoreFocus for returning focus on close
const useRestoreFocus = (open: boolean) => {
  const previous = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (open) previous.current = document.activeElement as HTMLElement;
    if (!open) previous.current?.focus();
  }, [open]);
};
```

---

## Semantic HTML guidelines

- Use native `<button>` for actions — never `div` with `onClick`
- Use native `<a>` for links — never `button` with `onClick` navigation
- Use `<input>` / `<textarea>` for text entry
- Use `<nav>` for navigation regions
- Use `<main>` for primary content
- Use `<h1>`–`<h6>` for headings — never styled spans
- Use `<ul>` / `<ol>` for lists
- Use `<table>` for tabular data
- Use `<form>` with `<label>` for form controls

---

## Testing checklist

### Automated (run before every PR)

- [ ] `axe-core` scan on all pages — 0 violations
- [ ] Lighthouse a11y audit — score ≥ 95
- [ ] Color contrast checked with `@axe-core/cli` or similar

### Manual (quarterly or before major releases)

- [ ] Full keyboard navigation: Tab through every interactive element
- [ ] Screen reader test: NVDA (Windows) + VoiceOver (macOS)
- [ ] Zoom to 200% — no content loss or overlap
- [ ] `prefers-reduced-motion: reduce` — no animations, all content visible
- [ ] High contrast mode (Windows) — all content distinguishable

### Per-component

Each component in `components.md` has a checklist item:

```markdown
- [ ] Keyboard: [expected behavior]
- [ ] Focus: [expected behavior]
- [ ] Screen reader: [expected announcement]
- [ ] Contrast: [expected ratio]
```

---

## Design tokens

Add these CSS custom properties for accessibility-aware styling:

```css
:root {
  --focus-ring-color: hsl(var(--ring));
  --focus-ring-width: 2px;
  --focus-ring-offset: 2px;
  --text-disabled: hsl(215 25% 58% / 0.5);
  --surface-disabled: hsl(220 40% 14% / 0.5);
  --stroke-icons: hsl(215 25% 58%);
}
```

---

## Edge cases

| Case                                    | Handling                                    |
|-----------------------------------------|---------------------------------------------|
| Streaming content with screen reader    | `aria-live="polite"` + `aria-atomic="false"` |
| Long message (>1000 words)              | No truncation. Reader reads all on focus.   |
| Code block in message                   | `<code>` or `<pre>` with `aria-label="Code block"` |
| Image in message                        | `alt` text from user or "User attached image" |
| Empty chat history                      | "No saved chats" readable by screen reader  |
| Upload progress with screen reader      | `role="status"` announces stage changes     |
| 20+ sources in a single answer          | "20 sources" aria-label, no individual announcements |
| Network error                           | `role="alert"` interrupts                  |
