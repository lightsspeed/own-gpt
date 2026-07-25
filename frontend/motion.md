# Motion & Interaction System

> Every animation has a purpose: communicate state change, guide attention, or provide feedback.
> All values are in milliseconds. All easings are CSS `cubic-bezier()` or Tailwind defaults.

---

## Principles

1. **Fast** — no animation exceeds 300ms. Users never wait for the UI.
2. **Subtle** — animations support understanding, not decoration.
3. **Purposeful** — every animation communicates a state change or affordance.
4. **Accessible** — `prefers-reduced-motion` disables all decorative animation.

---

## Timing chart

| Token              | Duration | Easing                              | Usage                           |
|--------------------|----------|--------------------------------------|---------------------------------|
| `instant`          | 0ms      | –                                    | Theme switch, color-only changes |
| `micro`            | 100ms    | `ease-out`                           | Button press, icon toggle       |
| `fast`             | 150ms    | `ease-out`                           | Hover, focus, tooltip show      |
| `normal`           | 200ms    | `cubic-bezier(0.4, 0, 0.2, 1)`      | Panel expand, modal open, fade  |
| `slow`             | 250ms    | `ease-in-out`                        | Accordion, sidebar slide        |
| `reveal`           | 300ms    | `ease-out`                           | Page transition, skeleton pulse |

### Tailwind config

```js
transitionDuration: {
  'micro': '100ms',
  'fast':  '150ms',
  'normal':'200ms',
  'slow':  '250ms',
  'reveal':'300ms',
},
transitionTimingFunction: {
  'in-expo':    'cubic-bezier(0.4, 0, 0.2, 1)',
  'out-expo':   'cubic-bezier(0, 0, 0.2, 1)',
  'in-out-expo':'cubic-bezier(0.4, 0, 0.2, 1)',
  'bounce':     'cubic-bezier(0.34, 1.56, 0.64, 1)',
},
```

---

## Keyframe library

```css
@keyframes fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}

@keyframes fade-in-up {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes slide-down {
  from { opacity: 0; transform: translateY(-4px); max-height: 0; }
  to   { opacity: 1; transform: translateY(0); max-height: 300px; }
}

@keyframes scale-in {
  from { opacity: 0; transform: scale(0.95); }
  to   { opacity: 1; transform: scale(1); }
}

@keyframes scale-pulse {
  0%   { transform: scale(1); }
  50%  { transform: scale(0.95); }
  100% { transform: scale(1); }
}

@keyframes bounce-dot {
  0%, 80%, 100% { transform: scale(0); }
  40%           { transform: scale(1); }
}

@keyframes shimmer {
  0%   { background-position: -200% center; }
  100% { background-position: 200% center; }
}

@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0; }
}

@keyframes checkmark-draw {
  to { stroke-dashoffset: 0; }
}
```

---

## Interaction specifications

### Hover

| Element       | Transform            | Shadow        | Duration |
|---------------|----------------------|---------------|----------|
| Source pill   | `translateY(-1px)`   | `shadow-sm`   | 150ms    |
| KB card       | `translateY(-2px)`   | `shadow-md`   | 150ms    |
| Button (ghost)| bg → accent          | none          | 150ms    |
| Sidebar item  | bg → secondary       | none          | 150ms    |
| Session item  | bg → secondary       | none          | 150ms    |

### Click / press

| Element      | Transform            | Duration |
|--------------|----------------------|----------|
| Button       | `scale(0.97)`        | 100ms    |
| Icon button  | `scale(0.9)`         | 100ms    |
| Source pill  | `scale(0.97)`        | 100ms    |
| Send button  | `scale(0.95)`        | 100ms    |

### Enter transitions

| Element           | Animation       | Duration | Delay     |
|-------------------|-----------------|----------|-----------|
| New message       | `fade-in-up`    | 200ms    | 0         |
| Streaming chunk   | `fade-in-up`    | 100ms    | staggered |
| Mode badge        | `fade-in`       | 200ms    | 100ms     |
| Tool event pill   | `fade-in`       | 200ms    | 0         |
| Modal backdrop    | `fade-in`       | 200ms    | 0         |
| Modal content     | `scale-in`      | 200ms    | 50ms      |
| Tooltip           | `fade-in`       | 150ms    | 300ms     |
| Upload progress   | `slide-down`    | 200ms    | 0         |

### Exit transitions

| Element     | Animation    | Duration |
|-------------|--------------|----------|
| Modal       | `fade-out`   | 150ms    |
| Tooltip     | `fade-out`   | 100ms    |
| Upload prog | `slide-up`   | 200ms    |
| Toast       | `slide-out`  | 200ms    |

### State change transitions

| Change                    | Animation           | Duration |
|---------------------------|---------------------|----------|
| Sidebar open (overlay)    | slide from left     | 200ms    |
| Sidebar close (overlay)   | slide to left       | 200ms    |
| Debug panel expand        | `slide-down`        | 200ms    |
| Debug panel collapse      | slide-up            | 200ms    |
| Feedback toggle           | `scale-pulse`       | 100ms    |
| Copy confirmed            | icon swap + fade    | 150ms    |
| Page transition           | `fade-in`           | 200ms    |
| Skeleton pulse            | `shimmer`           | 1.5s     |

---

## Streaming text behavior

1. Each SSE `content` chunk appends to a buffer
2. On animation frame, accumulated text flushes to the DOM
3. Text appears with `fade-in-up` (100ms)
4. A blinking cursor (`|` character, `cursor-blink` 1s) appears at the end
5. When streaming ends, cursor disappears after 500ms fade
6. Mode badge and sources fade in after streaming completes

```
Input buffer ──→ requestAnimationFrame ──→ DOM updates with fade-in-up
                                                    │
                                              cursor blinks at end
                                                    │
                                          stream ends → cursor fades
                                                    │
                                          mode badge + sources appear
```

---

## Reduced motion

When `prefers-reduced-motion: reduce` is active:

- All `fade-in-up` becomes instant (opacity + translate both set to final)
- All `scale-in` becomes instant
- `shimmer` skeleton animation stops (solid bg color)
- `cursor-blink` becomes static
- Streaming text appears instantly
- Hover lifts are disabled (color change only)
- Sidebar slide is instant

Implement via:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

And in React, use a `usePrefersReducedMotion()` hook to conditionally disable animation classNames on interactive elements.

---

## Interaction checklist

- [ ] All hover states communicate affordance (lift, color, or both)
- [ ] All press states provide tactile feedback (scale)
- [ ] All state changes are animated (not instant)
- [ ] All transitions are under 300ms
- [ ] Enter animations are staggered when multiple elements appear
- [ ] Exit animations are faster than enter animations
- [ ] Default text is `body` with `transition: colors 150ms` for theme changes
- [ ] Reduced motion is fully supported
- [ ] Animations never block interaction
- [ ] No animation plays on initial page load (user has not asked for it)
