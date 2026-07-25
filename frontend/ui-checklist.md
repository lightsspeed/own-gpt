# UI Audit Checklist

> Audit every screen against the design system **before** writing code.
> Score each dimension 1–10. Overall = average. A score below 7 means the page needs a full rebuild.

---

## Scoring rubric

| Score | Meaning |
|-------|---------|
| 10    | Matches spec perfectly. No changes needed. |
| 8–9   | Minor deviations. Touch-up only. |
| 6–7   | Functional but inconsistent. Needs redesign. |
| 4–5   | Multiple violations. Full rebuild. |
| 1–3   | Not implemented. |

---

## Pages

| Page | Priority | Current score |
|------|----------|---------------|
| Chat (messages) | P0 | |
| Sidebar | P0 | |
| Input bar | P0 | |
| Header | P1 | |
| Knowledge Base | P1 | |
| Settings | P1 | |
| Upload dialog | P2 | |
| Welcome / empty state | P2 | |
| Loading states | P1 | |
| Error states | P2 | |

---

## Dimensions per page

### Typography

- [ ] Every text node uses a token from the type scale (no ad-hoc sizes)
- [ ] Message body is 15px (`body`)
- [ ] Source labels are 13px (`small`)
- [ ] Metadata / timestamps are 12px (`caption`)
- [ ] Badges / mode pills are 13px (`small`)
- [ ] Sidebar items are 14px (`small`)
- [ ] Headers / section titles use `small` or `title`
- [ ] No text is below 11px (`micro` minimum)
- [ ] Line heights match spec (body: 1.6, small: 1.4, caption: 1.4)
- [ ] Prose content inside markdown respects the scale

### Spacing

- [ ] All values come from the set {4, 8, 12, 16, 20, 24, 32, 40, 48, 64}
- [ ] No magic numbers (no `p-5`, `gap-3`, `m-7`, etc.)
- [ ] Message-to-message gap is 24px
- [ ] Answer-to-metadata gap is 16px
- [ ] Paragraphs inside answer are 16px apart
- [ ] Sidebar item stack gap is 4px
- [ ] Source chip gap is 8px
- [ ] Icon-to-label gap is 6px
- [ ] Card / panel padding is 16px
- [ ] Chat container max-width is 800px

### Hierarchy

- [ ] Page has exactly one focal point
- [ ] Primary action is visually dominant (filled button)
- [ ] Secondary actions are ghost or text buttons
- [ ] No two elements compete for attention
- [ ] Mode badge is present but subordinate to answer text
- [ ] Debug panel is collapsed by default
- [ ] Sources are visually distinct from answer content
- [ ] The streaming message is clearly "in progress" (cursor or fade)

### Accessibility

- [ ] All interactive elements are keyboard-focusable
- [ ] Visible focus ring on all controls (`ring-2 ring-ring ring-offset-2`)
- [ ] Icon-only buttons have `aria-label`
- [ ] Collapsible panels have `aria-expanded`
- [ ] Color is never the sole differentiator (pair with icon or text)
- [ ] All text meets WCAG AA 4.5:1 contrast ratio
- [ ] `prefers-reduced-motion` respected

### Animations

- [ ] Hover transitions are 150ms ease-out
- [ ] UI state changes are 200ms
- [ ] Panel expand/collapse is 250ms with slide-down
- [ ] Streaming text fades in (100ms per chunk)
- [ ] New messages fade in (200ms)
- [ ] Modals scale in (200ms)
- [ ] Tooltips fade in (150ms)
- [ ] No animation exceeds 300ms

### Consistency

- [ ] Same component uses same tokens everywhere
- [ ] All buttons use the same height / padding / radius
- [ ] All cards use the same radius (`rounded-xl` = 12px)
- [ ] All pills / badges use `rounded-full`
- [ ] All inputs share same height / border / focus style
- [ ] All links share same color / hover behavior
- [ ] All dividers use `border-white/5` or `border-white/10`
- [ ] All hover effects use same transition timing

---

## Per-page checklists

### 1. Chat (messages view)

- [ ] Message container has no border or background (pure whitespace separation)
- [ ] Assistant answer uses `body` (15px) with 1.6 line height
- [ ] User message uses `--secondary` background, rounded-xl (20px top-right)
- [ ] Mode badge appears after streaming completes
- [ ] Mode badge shows: icon + label + retrieval method + chunk/doc count
- [ ] Debug panel toggle: `▶ Why this answer?` (12px, low opacity)
- [ ] Sources section uses pill chips (13px)
- [ ] Action buttons (copy, like, dislike) visible on hover
- [ ] Streaming shows animated cursor or fade-in
- [ ] Tool event pills centered, fade in with bounce animation
- [ ] No nested cards or unnecessary borders

### 2. Sidebar

- [ ] Width: 260px
- [ ] Background matches page (`--background`)
- [ ] No border-right — use whitespace gap instead
- [ ] "New Chat" button at top (secondary or primary ghost)
- [ ] Chat history: each item is one line, `small` (13px), 4px stack gap
- [ ] Active chat has accent background (`--accent`)
- [ ] Pinned chats indicated visually (pin icon, subtle)
- [ ] Bottom section: Knowledge Base + Settings links
- [ ] Sections separated by 8px whitespace, not lines
- [ ] Scrollbar matches design system

### 3. Input bar

- [ ] Fixed to bottom, centered, max-width 800px
- [ ] Glass effect: `glass-panel` with backdrop blur
- [ ] Border radius: 16px (`rounded-xl`)
- [ ] Padding: 12px 16px
- [ ] Text input: `body` (15px), no border, transparent bg
- [ ] Attachment button (left): ghost icon, 18px
- [ ] Voice button (left of send): ghost icon
- [ ] Send button: primary filled, circular (32px)
- [ ] Focus state: glow ring on the entire bar
- [ ] File upload progress banner above input

### 4. Header

- [ ] Height: 48px
- [ ] Glass effect: `glass-panel`
- [ ] No bottom border
- [ ] Left: sidebar toggle (icon button)
- [ ] Center-left: "Own GPT" logo + model badge (13px pill)
- [ ] Right: Live indicator (green pulse dot + text) + action icons
- [ ] Sticky top, highest z-index in content layer

### 5. Knowledge Base

- [ ] Each document is a card: `rounded-xl`, 16px padding
- [ ] Card shows: icon + filename + chunk count + date + size
- [ ] Hover: `sm` shadow + slight lift (`-translateY(1px)`)
- [ ] Search bar at top with filter toggle
- [ ] Delete button appears on card hover
- [ ] Empty state: illustration + message + upload CTA
- [ ] Upload progress shown as animated banner

### 6. Settings

- [ ] Tabs: General / Models / Knowledge / Prompts / Advanced
- [ ] Clean form layout, consistent input spacing
- [ ] Each section separated by 24px
- [ ] Save button at bottom, primary filled
- [ ] Danger zone (clear history) at bottom, separated by divider

### 7. Upload dialog

- [ ] Drag-and-drop zone with dashed border
- [ ] File type indicators (supported: .pdf .docx .pptx .csv .xlsx .html)
- [ ] Animated progress stages (reading → parsing → chunking → embedding → done)
- [ ] Completion animation (checkmark + green)
- [ ] Error state with retry button

### 8. Welcome / empty state

- [ ] Centered display text (32px, `display`)
- [ ] Subtitle explaining capabilities (Memory, RAG, Web Search, Tools)
- [ ] Suggested prompt chips (3–4 examples)
- [ ] Fade-in on first load

### 9. Loading states

- [ ] Chat history: skeleton lines (pulse animation, `--muted` bg)
- [ ] KB list: skeleton cards (same layout as real cards)
- [ ] Streaming message: blinking cursor at end of text
- [ ] Tool call: animated bounce dots in pill

### 10. Error states

- [ ] API error: inline banner, `danger` colors, dismissible
- [ ] Upload error: red banner, retry button
- [ ] Network offline: persistent top bar
- [ ] All errors have human-readable message + action

---

## Scoring template

```markdown
## Page: [name]

| Dimension      | Score | Notes |
|----------------|-------|-------|
| Typography     | /10   |       |
| Spacing        | /10   |       |
| Hierarchy      | /10   |       |
| Accessibility  | /10   |       |
| Animations     | /10   |       |
| Consistency    | /10   |       |
| **Overall**    | **/10** |     |
```
