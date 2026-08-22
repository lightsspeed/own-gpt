# Conversation Layout

## Message Column

- Max width: 920px
- Centered: `mx-auto`
- Padding: `px-6`
- Spacing between messages: `space-y-6`

## Message Bubble

- User messages: right-aligned, primary background
- Assistant messages: left-aligned, elevated background
- Streaming: blinking cursor via `animate-cursor-blink`
- Collapsible: messages >600 chars show expand/collapse

## Composer

- Container: `bg-elevated/80 backdrop-blur-sm border rounded-2xl`
- Focus: `border-primary/40` with glow shadow
- Textarea: auto-resizing, `min-h-[44px] max-h-[200px]`
- Shift+Enter: newline
- Enter (without Shift): send
- Tool trigger wrench: left side
- Drag-and-drop zone: entire composer area

## Context Bar

- Color-coded chips per category (red=code, blue=knowledge, etc.)
- Each chip: hover-to-remove X button
- Add button: opens ContextPicker dropdown
- Clear button: removes all context

## Welcome State

- Star icon in gradient container
- Title: `text-2xl font-semibold`
- Subtitle: `text-muted-foreground/80`
- 6 suggestion chips in flex-wrap grid
- Chips: `rounded-xl border border-border/60 bg-elevated/40`

## Generation Spinner

- Pipeline stage indicators
- Animated dots for current stage
- Fade-in animation: 300ms
