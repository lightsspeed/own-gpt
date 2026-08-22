# Sidebar

## Design Tokens

| Token              | Value                   |
|--------------------|-------------------------|
| Width              | 250px                   |
| Border radius      | 16px (rounded-2xl)      |
| Item height        | 44px                    |
| Icon size          | 18px                    |
| Horizontal padding | 14px (px-3.5) / 16px (px-4) |
| Vertical gap       | 6px (space-y-1.5)       |
| Group spacing      | 18px                    |

## Section Headers

| Property       | Value    |
|----------------|----------|
| Font size      | 11px     |
| Font weight    | 600      |
| Letter spacing | 0.08em   |
| Opacity        | 25%      |
| Text transform | uppercase |
| Padding        | px-3 py-1.5 |

## Nav Items

| State   | Background | Left Bar     | Icon           | Text          |
|---------|------------|--------------|----------------|---------------|
| Default | transparent| none         | 50% opacity    | 70% opacity   |
| Hover   | hover/60   | h-4 border/20| 80% opacity + translateX(1px) | foreground |
| Active  | primary/8% | 3px primary h-5 | primary     | foreground, semibold |

## Items with Children

- Chevron icon: 12px, 30% opacity
- Rotates 180° when expanded
- Children indent: `ml-4`
- Child height: 32px (py-1.5)
- Child left dot: 4px circle at 30% border opacity

## Footer

- 60% opacity border-top divider
- 16px icons at 40% opacity
- Button text: 60% → hover foreground
- Hover background: hover/60
- User avatar: 28px, primary/15 background, ring-1 ring-primary/20

## Collapse Animation

- Expand: `animate-slide-down` — opacity 0→1, maxHeight 0→500px
- Duration: 180ms
- Easing: ease-out
