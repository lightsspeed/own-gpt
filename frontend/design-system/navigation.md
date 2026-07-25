# Navigation Shell

## Layout

- Fixed sidebar, floating, detached from viewport edge
- `position: fixed; top: 8px; left: 8px`
- Width: 250px
- Height: `calc(100vh - 16px)`
- Border radius: `rounded-2xl` (16px)
- Shadow: `shadow-xl`
- Border: `border border-border`
- Background: `bg-surface`

## Collapse

- Slides off-screen to `left: -296px`
- Transition: `transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)`
- When closed: hamburger button at `fixed top-4 left-4 z-[60]`
- Main content margin: `ml-[266px]` when open, `ml-0` when closed

## Logo Header

- Icon container: `w-8 h-8 rounded-xl`, gradient primary border
- SVG icon: 16×16px
- Title: `text-small font-bold text-foreground`
- Subtitle: `text-caption text-muted-foreground`
- Close button: `p-1.5`, icon 16px

## Search

- `⌘K` keyboard hint badge
- Search icon: 13px, left inset
- Input: `rounded-lg border border-border/50 bg-background/30`
- Padding: `py-1.5 pl-8 pr-10`
- Text: `text-small`
- Placeholder: `text-muted-foreground/30`
- Focus: `border-primary/30 bg-background/50`
- ⌘K badge: `text-[10px] text-muted-foreground/25 bg-muted/20 border border-border/30`

## Nav Groups

### Group Header
- Chevron icon: 10px, rotates when collapsed
- Label: `text-[11px] font-semibold uppercase tracking-[0.08em]`
- Opacity: `text-muted-foreground/25`
- Padding: `px-3 py-1.5`

### Nav Item
- Height: 44px (`py-2`)
- Horizontal padding: `px-3`
- Gap between icon and text: `gap-2.5`
- Border radius: `rounded-lg` (8px)
- Transition: `duration-150`

### Active State
- Background: `bg-primary/[0.08]`
- Left bar: `w-[3px] h-5 bg-primary rounded-full`
- Icon color: `text-primary`
- Text weight: `font-semibold`

### Hover State
- Background: `bg-hover/60`
- Icon lift: `translate-x-[1px]`
- Left bar appears: `h-4 bg-border/20`
- Transition: 150ms

## Children Sub-items

- Indent: `ml-4`
- Left dot: `w-1 h-1 rounded-full bg-border/30`
- Expand animation: `animate-slide-down` (180ms)

## Footer

- Divider: `border-t border-border/60`
- Buttons: 16px icon, `text-muted-foreground/60`, `hover:text-foreground hover:bg-hover/60`
- Profile: avatar `w-7 h-7 bg-primary/15 ring-1 ring-primary/20`
- Online indicator: `w-1.5 h-1.5 rounded-full bg-success`
- Status text: `text-caption text-muted-foreground/50`
