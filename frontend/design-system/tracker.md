# Conversation Minimap

A fixed-position scroll progress indicator on the right edge of the viewport.

## Position

- `position: fixed`
- `right: 20px`
- `top: 50%; transform: translateY(-50%)`
- z-index: 40

## Dimensions

| Property | Value  |
|----------|--------|
| Container height | 460px  |
| Container width  | 8px    |
| Track width (default) | 2px |
| Track width (hover)   | 5px |
| Thumb width    | 8px    |
| Thumb height   | 32px   |
| Thumb radius   | 999px  |

## Track

- Background: `bg-border/15`
- Border radius: `rounded-full`
- Centered: `left-1/2 -translate-x-1/2`
- Transition: 180ms ease for width change

## Tick Marks

- Horizontal lines along the track
- Width: 10px, Height: 1px
- Spacing: every 12px
- Opacity (default): 0.35
- Opacity (hover/drag): 0.70
- Color: currentColor (inherits text color)
- Centered: `left-1/2 -translate-x-1/2`

## Thumb

- Width: 8px, Height: 32px
- Border radius: 999px (fully rounded pill)
- Color: primary (default opacity 0.70)
- Hover/drag: primary at full opacity
- Glow (drag): `box-shadow: 0 0 12px rgba(59,130,246,0.55)`
- Glow (idle): `box-shadow: 0 0 8px rgba(59,130,246,0.3)`
- Transition: 150ms

## Interaction

### Click to Jump
```
scrollTop = (clickY / trackerHeight) * scrollHeight
```
Smooth scrolling.

### Drag to Scrub
- `mousedown` starts drag
- `mousemove` updates position
- `mouseup` ends drag
- Feels like an IDE minimap

## Visibility

- Hide when conversation height <= viewport height
- Opacity 0 + pointer-events: none when inactive
- 300ms grace period before hiding (prevents flicker)
- Only opacity, scale, translate, width transitions (never height/top/left)
