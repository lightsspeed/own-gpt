# Component Acceptance Criteria

Before merging any new or redesigned component, the following checks must pass.

---

## Architecture

- [ ] Uses only design tokens (from `design-system/`)
- [ ] Uses only primitives (from `components/primitives/` or `components/layout/`)
- [ ] No arbitrary Tailwind values (`text-[15px]`, `rounded-[17px]`, `p-[22px]`, etc.)
- [ ] No duplicate styling — every visual concern lives in exactly one place
- [ ] `scripts/check-design-tokens.mjs` passes
- [ ] Barrel export added to the appropriate `index.ts`

---

## Accessibility

- [ ] Keyboard navigation works (Tab, Enter, Escape, Arrow keys as appropriate)
- [ ] All interactive elements have visible focus rings
- [ ] Screen reader tested: labels, roles, live regions, aria-expanded set correctly
- [ ] Color contrast meets WCAG 2.2 AA (4.5:1 text, 3:1 large text)
- [ ] Semantic HTML elements used (`<button>`, `<nav>`, `<main>`, etc.)
- [ ] `aria-label` provided for icon-only controls

---

## Motion

- [ ] Uses motion duration tokens from `design-system/motion.ts`
- [ ] Uses motion easing tokens from `design-system/motion.ts`
- [ ] `prefers-reduced-motion` respected — animations degrade gracefully
- [ ] No layout shift during animation
- [ ] Streaming text: no reflow, characters appear in place

---

## Performance

- [ ] Component doesn't cause unnecessary re-renders
- [ ] `React.memo` applied if renders > 5 times on typical interaction
- [ ] No `useEffect` chains causing cascading renders
- [ ] Streaming data doesn't block main thread
- [ ] Bundle impact assessed (no large library added without review)

---

## Documentation

- [ ] Props match types defined in `.types.ts` or inline interface
- [ ] `displayName` set for all forwardRef components
- [ ] Behavior matches `components.md` contract
- [ ] Visual appearance matches `design.md`
- [ ] Accessibility patterns match `accessibility.md`
- [ ] Loading, empty, error, and hover states are documented

---

## UX states checklist

- [ ] Default / idle
- [ ] Hover
- [ ] Focus (keyboard visible)
- [ ] Active / pressed
- [ ] Loading / busy
- [ ] Empty / no data
- [ ] Error / failure
- [ ] Disabled
- [ ] Streaming (for AI components)
- [ ] Dark mode (only dark mode supported currently — verify no light-mode breakage)

---

## Evidence family (AI-specific)

For components related to Answer Mode, Sources, Debug, or Activity Timeline:

- [ ] Uses `design-system/ai.ts` tokens
- [ ] Consistent visual language across the evidence family
- [ ] Collapsed state fits within message width (800px)
- [ ] Expanded state doesn't overflow or clip
