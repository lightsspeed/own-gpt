# Motion & Feedback

> How the platform communicates change, state, and progress through motion.
>
> **Not CSS animations. Not JavaScript libraries. Not implementation.**
>
> This document defines the principles governing motion as a communication medium.
>
> Every animation must communicate meaning. If it doesn't, it doesn't belong.

---

## Purpose

Motion is not decoration. In the AI Engineering Platform, motion serves three purposes:

1. **Communicate state change** — Something happened. The interface acknowledges it.
2. **Guide attention** — Look here. Something needs you.
3. **Maintain orientation** — Where you were is still here. Where you arrived makes sense.

The state model (13) defines *what* state exists. Motion defines *how* the user perceives state transitions.

Feedback is the sensory confirmation of action. Every user action must produce a perceivable response within 100ms. Silence is not a valid feedback state.

---

## Motion Philosophy

### Communicate, don't decorate
Every animation has a purpose. Entrance animations orient. Transition animations connect. Status animations inform. If you can remove an animation and nothing breaks, it was decorative — and decorative animations are forbidden.

### Predictable, not surprising
Motion follows consistent patterns. The same transition behaves the same way every time. Surprise motion (unexpected elements flying in, unpredictable delays) erodes trust.

### Fast, not flashy
Animations complete in 200–300ms for functional transitions. Users are never forced to wait for an animation to finish before interacting. Speed is a feature.

### Progressive enhancement
Motion enhances the experience but never blocks it. If motion is disabled (accessibility), the experience remains complete. Content does not depend on animation timing.

### Reduced motion is the default respect
The platform respects `prefers-reduced-motion` at the system and user level. When reduced motion is detected:
- All non-essential animations are removed.
- Essential animations (loading, progress, status change) use minimal duration (50–100ms).
- No parallax, entrance, or decorative animations play.
- Opacity transitions remain (they communicate state); transform transitions are removed.

---

## Motion Categories

| Category | Purpose | Examples |
|----------|---------|----------|
| **Transition** | Navigate between views or states | Page transitions, panel slide-in, tab switch |
| **Feedback** | Confirm user action | Button press, toggle switch, submit success |
| **Status** | Communicate system state | Loading spinner, progress bar, streaming cursor |
| **Attention** | Guide user focus | New notification, error highlight, alert pulse |
| **Entrance** | Reveal content on mount | Card fade-in, list item stagger, skeleton→content |
| **Exit** | Remove content from view | Dialog close, toast dismiss, item removal |

---

## Transition Motion

### Page transitions
Page transitions orient the user to a new context. They are subtle and fast.

| Transition | When | Duration | Behavior |
|---|---|---|---|
| Slide (right→left) | Drill forward (list→detail) | 250ms | New content slides over from right; previous content stays in history |
| Slide (left→right) | Navigate back (detail→list) | 200ms | Previous content slides back into view |
| Fade through | Same-level navigation (tab switch) | 150ms | Content cross-fades; no directional bias |
| Instant | Command palette, notifications | 0ms | No transition needed for overlay patterns |

**Principles:**
- Page transitions are never full-page — the sidebar and top bar remain static.
- Transition direction is consistent with navigation semantics (forward = right, back = left).
- Content appears before chrome (data arrives → content fades in → chrome is already there).

### Panel transitions
Panels (sidebars, inspectors, dialogs) slide in from a predictable direction.

| Panel type | Origin | Duration | Behavior |
|---|---|---|---|
| Side panel (inspector) | Right edge | 250ms | Slides in; push or overlay depending on recipe |
| Bottom sheet | Bottom edge | 300ms | Slides up; overlay with scrim |
| Modal | Center (scale) | 200ms | Scales in from center; overlay with scrim |
| Toast | Top-right / bottom-right | 300ms | Slides in; auto-dismiss after duration |

**Principles:**
- Panels that overlay content use a scrim (semi-transparent backdrop).
- Scrim fades in over 150ms (no slide).
- Panel entrance and scrim fade are simultaneous.
- Panel exit reverses the entrance animation (same duration).

---

## Feedback Motion

### Action feedback
Every interactive action produces immediate feedback.

| Action | Feedback | Timing |
|---|---|---|
| Button click | Subtle scale (98%) on press, return on release | 50ms press, 100ms release |
| Toggle | Thumb slides; background color transitions | 200ms |
| Card click | Subtle lift (elevation increase) | 100ms |
| Link click | Underline appears or color transition | 100ms |
| Menu item | Background highlight on hover | 100ms |
| Drag | Element follows cursor with slight elevation increase | Real-time |

**Principles:**
- Feedback is visible within 50ms of the action (perception threshold).
- Feedback duration is shorter than transition duration.
- Feedback does not block subsequent interactions.

### Result feedback
After an action completes, the result is communicated.

| Result | Feedback | Duration |
|---|---|---|
| Success | Brief green flash or checkmark animation | 1–2s, then auto-dismiss |
| Error | Red highlight on the error source; error message appears | Persistent |
| Async started | Progress indicator replaces action button | Until complete |

---

## Status Motion

### Loading
Loading communicates that the system is working.

| Context | Indicator | Behavior |
|---|---|---|
| Page/section load | Skeleton (pulsing placeholder) | Pulse animation (opacity 0.3→0.6) until content arrives |
| Action execution | Spinner or button progress | Indeterminate spinner for unknown duration; determinate bar for known duration |
| Background refresh | Subtle progress bar at top of content area | Thin bar (2px), slides in from left, fills on completion |
| Polling | No visible indicator (silent) | Content updates in place; no loading spinner |

**Principles:**
- Initial load uses skeletons (content-shaped placeholders), not spinners.
- Skeleton pulses gently (1.5s cycle) to indicate activity without urgency.
- Subsequent loads (refresh, pagination) use smaller indicators.
- Loading never blocks the entire interface — only the loading section.

### Streaming
Streaming is used when content appears incrementally (AI responses, log output).

| Context | Indicator | Behavior |
|---|---|---|
| AI message | Animated cursor (blinking vertical bar) | Blinks at 1s interval while content streams |
| AI message (start) | Fade-in of message container | 100ms fade as first token arrives |
| Log output | Content appears line by line | No animation — lines appear as received |
| File upload | Progress bar with file name | Determinate bar with percentage |

**Principles:**
- Streaming shows content as it arrives — never buffer and reveal.
- The streaming cursor is the primary affordance that "more is coming."
- Streaming can be stopped by the user (stop button replaces send button).

### Progress
Progress communicates advancement through a multi-step process.

| Context | Indicator | Behavior |
|---|---|---|
| Form wizard | Step indicator (filled/completed/current/upcoming) | Step fills on completion with brief checkmark animation |
| Multi-step tool execution | Progress bar with step labels | Bar fills proportionally; step label highlights current |
| File processing | Progress bar + elapsed time | Determinate bar; time updates every second |
| Indeterminate (unknown steps) | Indeterminate bar | Bar oscillates until completion |

**Principles:**
- Determinate progress is always preferred over indeterminate.
- Progress indicators show estimated time remaining when available.
- Progress indicators can be cancelled when the operation supports it.

---

## Attention Motion

### Alerts and notifications
Motion draws attention to new items without disrupting workflow.

| Context | Indicator | Behavior |
|---|---|---|
| New notification (existing panel) | Badge count increments with bounce | Brief scale animation on badge (100ms) |
| New notification (user elsewhere) | Toast slides in | Slides from top-right (300ms) |
| Critical alert | Persistent banner with attention color | Slides down from top (300ms); persists until dismissed |
| Attention queue update | Badge pulse (if count increases) | Two pulse cycles (opacity 0.6→1, 1s total) |

**Principles:**
- Attention motion is subtle — enough to notice, not enough to alarm.
- Critical alerts use color and position (top banner), not aggressive animation.
- Motion stops after the initial notification (no looping attention animations).

### Focus guidance
Motion guides the user to relevant content after a state change.

| Context | Indicator | Behavior |
|---|---|---|
| Validation error | Error field scrolls into view; border highlights | Scroll (instant), border highlight (200ms) |
| New content loaded | "N new items" banner at top of list | Slides down (200ms); dismisses on scroll |
| Search results | Results appear with brief stagger | 50ms stagger per result group (not per item) |

---

## Entrance Motion

### Content reveal
Content appears in a predictable, non-distracting manner.

| Context | Animation | Duration |
|---|---|---|
| Card grid | Cards fade in with 50ms stagger per row | 200ms per card |
| List items | Items fade in with 30ms stagger | 150ms per item |
| Chart | Chart fades in (no axis animation) | 300ms |
| Skeleton → content | Content cross-fades over skeleton | 150ms |
| Image | Image fades in on load | 200ms |

**Principles:**
- Stagger reveals are used only for the initial load of a collection.
- Stagger delay per item is minimal (30–50ms) — not a sequential parade.
- Content that appears above the fold is not animated (user sees it immediately).
- Content below the fold may animate as it scrolls into view (lazy entrance).

---

## Exit Motion

### Content removal
Elements leaving the viewport exit with purpose.

| Context | Animation | Duration |
|---|---|---|
| Toast dismiss | Slide out to right | 200ms |
| Dialog close | Scale out slightly | 150ms |
| Panel close | Slide out to right | 200ms |
| Item removal from list | Fade out + height collapse | 200ms + 150ms collapse |
| Notification dismiss | Fade out | 150ms |

**Principles:**
- Exit animations match the reverse of entrance animations where applicable.
- Exit animations are faster than entrance animations.
- An item being removed is never hidden before the removal animation completes (no "poof" behavior).

---

## Duration & Easing

### Duration tokens

| Token | Value Range | Use |
|-------|-------------|-----|
| instant | 0–50ms | Feedback, hover states |
| fast | 100–150ms | Status changes, focus transitions |
| normal | 200–300ms | Panel slides, page transitions, entrance |
| slow | 300–500ms | Complex transitions, full-page reveals |
| deliberate | 500–800ms | Celebratory or completion animations (rare) |

### Easing tokens

| Token | Curve | Use |
|-------|-------|-----|
| linear | Linear | Progress bars, opacity transitions |
| standard | Ease-in-out | Most UI transitions |
| accelerate | Ease-in | Elements leaving the screen |
| decelerate | Ease-out | Elements entering the screen |
| spring | Overshoot curve | Celebratory, attention-grabbing (rare) |

**Principles:**
- Spring easing is reserved for moments of celebration or completion (experiment concluded, config approved).
- Linear easing is used for continuous motion (progress bars, spinners).
- Standard easing is the default for all transitions.
- Duration and easing values are tokens (defined in the design system), not inline magic numbers.

---

## Feedback Principles

### Action confirmation
Every user action must produce a perceivable response.

| Action type | Feedback type | Timing |
|---|---|---|
| Tap/click | Visual (scale, color, elevation) | < 50ms |
| Key press | Visual (focus ring, cursor change) | Instant |
| Navigation | Visual (page transition) | < 300ms |
| Submit | Visual (processing indicator) | < 100ms |
| Error | Visual (error indicator) | < 100ms |
| Success | Visual (success indicator) | < 100ms |
| Long operation | Visual (progress indicator) | < 100ms then continuous |

**The 100ms rule:** If an action takes longer than 100ms to complete, show a progress indicator. Any action that completes in under 100ms shows a result indicator, not a progress indicator.

### Feedback hierarchy
- **Highest priority:** Error and failure feedback. Immediately visible, clearly distinguishable.
- **Medium priority:** Success and completion feedback. Visible but not attention-demanding.
- **Lowest priority:** Neutral status updates. Visible but subtle.

### Feedback zones
- **Inline:** Feedback appears at the point of action (input validation, button state).
- **Context-area:** Feedback appears within the relevant content area (section-level error).
- **Global:** Feedback appears in a dedicated space (toast, banner, notification center).

---

## Loading Sequence Architecture

### Phase 1: Instant (0–50ms)
- Navigation intent acknowledged
- Cursor changes to indicate processing
- UI remains fully interactive

### Phase 2: Perceived (50–300ms)
- Skeleton or loading indicator appears
- Non-blocking — user can cancel or navigate away
- No spinner for perceived-duration loads (skeleton only)

### Phase 3: Active (300ms–5s)
- Progress indicator (determinate preferred)
- "Cancel" or "Stop" action available for cancellable operations
- Estimated time shown when available

### Phase 4: Extended (> 5s)
- User can navigate away without losing operation (background processing)
- Notification on completion
- Operation continues even if user leaves the screen

### Phase 5: Stalled (> 30s)
- "This is taking longer than expected" message
- Option to continue waiting or receive notification
- No indefinite spinner without communication

---

## State-Driven Motion Map

Every state transition defined in the state model (13) has a corresponding motion behavior.

| State Transition | Motion | Duration | Feedback |
|---|---|---|---|
| Idle → Loading | Skeleton appears | 0ms (instant) | — |
| Loading → Populated | Skeleton → content cross-fade | 150ms | — |
| Loading → Error | Skeleton → error state fade | 150ms | Error indicator |
| Idle → Streaming | Streaming cursor appears | 100ms | "More is coming" |
| Streaming → Complete | Cursor disappears; message complete | 100ms | — |
| Idle → Needs Approval | Badge/pulse appears | 300ms | "Action needed" |
| Needs Approval → Approved | Success animation | 300ms | Success indicator |
| Needs Approval → Rejected | Transition to rejected state | 200ms | — |
| Populated → Updated | Subtle highlight on changed content | 200ms | "Content changed" |
| Hidden → Visible | Entrance animation | 200–300ms | — |
| Visible → Hidden | Exit animation | 150–200ms | — |

---

## Accessibility & Motion

### prefers-reduced-motion
The platform fully respects `prefers-reduced-motion`.

**When reduced motion is detected:**
- All entrance, exit, and decorative animations are disabled.
- Transition animations are reduced to opacity-only (no transform).
- Duration is reduced to 50–100ms for essential motion.
- Progress indicators remain (they communicate essential state).
- Streaming cursor remains (it communicates essential state).
- Skeleton pulses are disabled (static placeholder shown).
- Stagger reveals are disabled (all content appears simultaneously).

### Motion sensitivity guidelines
- No auto-playing animations.
- No parallax effects.
- No continuous looping animations (except spinners, which stop after 30s).
- No animations that cover more than 25% of the viewport.
- All animations can be paused by the user (system-level or platform setting).

### Vestibular considerations
- No rapid scaling animations (can trigger dizziness).
- No large-scale parallax or perspective shifts.
- Minimal use of horizontal movement (most likely to cause discomfort).
- All motion respects the system-level motion sensitivity setting.

---

## Implementation Principles

### Declarative motion
Motion is defined by what it should do, not how it should do it. Implementation details (CSS transitions, JS animations, canvas rendering) are a separate concern. The architecture defines the contract; implementation satisfies it.

### Consistent timing
All durations and easings are defined as tokens. No inline duration or easing values exist in implementation. A single source of truth for all motion properties.

### Performance
- Motion targets 60fps. Use GPU-accelerated properties (opacity, transform) exclusively.
- Avoid animating layout properties (width, height, top, left).
- Animations on non-visible elements are suspended.
- Heavy animations (charts, graphs) use canvas or WebGL, not DOM manipulation.

### Orchestration
Sequential or parallel animations are defined declaratively. A panel entrance may involve:
- Scrim fade-in (parallel, 150ms)
- Panel slide-in (parallel, 250ms, starts 50ms after scrim)
- Content fade-in (sequential, 100ms, starts after panel settles)

Orchestration is defined at the composition level, not the primitive level.

---

## Motion Anti-Patterns

| Anti-pattern | Problem | Remedy |
|---|---|---|
| Decorative animation | Animation that serves no communication purpose | Remove |
| Over-animated entrance | Every element flies, fades, or bounces in | Only animate the first meaningful element below the fold |
| Slow transitions | User waits for animation to complete | Keep functional transitions under 300ms |
| Inconsistent easing | Different animations use different curves | Use the defined easing token for each category |
| Motion without feedback | Action produces no perceivable response | Every action must produce feedback within 100ms |
| Continuous animation | Spinner or pulse that never stops | Stop after 30s; show "taking longer than expected" message |
| Sequential overload | Items animate one by one (50 items × 100ms each) | Stagger in groups, not individually |
| Accessibility neglect | Animations that violate reduced motion | Test all animations with prefers-reduced-motion enabled |
| Layout animation | Animating width, height, or position (causes layout shift) | Use opacity and transform only |
| Motion dependency | Content is unreachable without animation | Progressive enhancement: content is always accessible without animation |

---

## Relationship to Other Documents

| Document | Relationship |
|---|---|
| 08-interaction-principles.md | Motion implements interaction principles (feedback, state communication) |
| 13-state-model.md | Every state transition has a corresponding motion behavior |
| 17-design-system-architecture.md | Motion tokens (duration, easing) are part of the token system |
| 18-visual-language.md | Motion brings visual properties to life |
| 20-notifications.md | Notification appearance and dismiss use motion patterns |

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-07-25 | Architecture | Initial motion and feedback definition |
