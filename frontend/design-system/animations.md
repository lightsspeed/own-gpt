# Animations

## Duration Tokens

| Token   | Milliseconds |
|---------|--------------|
| Instant | 100ms        |
| Fast    | 150ms        |
| Normal  | 200ms        |
| Slow    | 300ms        |
| Reveal  | 500ms        |

## Easing Curves

- Default: `cubic-bezier(0.4, 0, 0.2, 1)` (ease-out)
- Spring-like: `cubic-bezier(0.16, 1, 0.3, 1)`
- Bounce: `cubic-bezier(0.34, 1.56, 0.64, 1)`

## Component Animations

### Message Entry
- Keyframes: `message-in`
- From: `opacity: 0, translateY(16px)`
- To: `opacity: 1, translateY(0)`
- Duration: 400ms
- Easing: ease-out
- Applied via: `animate-message-in`

### Fade In
- Keyframes: `fade-in`
- Duration: 200ms
- Usage: dropdowns, popovers, spinners

### Fade In Up
- Keyframes: `fade-in-up`
- From: `opacity: 0, translateY(8px)`
- Duration: 250ms
- Usage: tooltips, toasts

### Scale In
- Keyframes: `scale-in`
- From: `opacity: 0, scale(0.95)`
- Duration: 150ms
- Usage: modals, menus

### Slide Down (Expand)
- Keyframes: `slide-down`
- From: `opacity: 0, maxHeight: 0`
- To: `opacity: 1, maxHeight: var(--slide-height, 500px)`
- Duration: 250ms
- Usage: collapsible sections, nav children

### Cursor Blink
- Keyframes: `cursor-blink`
- 0%, 100%: `opacity: 1`
- 50%: `opacity: 0`
- Duration: 1s, step-end
- Usage: streaming cursor

### Shimmer
- Keyframes: `shimmer`
- Background-position: -200% → 200%
- Duration: 2s, linear, infinite
- Usage: loading skeletons

## Scroll-To-Bottom FAB

- Entry: `opacity: 0, scale: 0.96, translateY(8px)` → `opacity: 1, scale: 1, translateY(0)`
- Duration: 200ms
- Easing: `cubic-bezier(0.16, 1, 0.3, 1)` (spring-like)
- Exit: reverse, 200ms

## Minimap

- Track width: 2px → 5px on hover, 180ms ease
- Thumb opacity/glow: 150ms
- Container opacity: 200ms
- Never animate height, top, or left properties
