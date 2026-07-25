# Baseline UI Audit — Scores

> Scored against `ui-checklist.md` criteria before any redesign work begins.
> Target for all pages: **≥ 9.0** after redesign.

---

## Summary

| Screen         | Typography | Spacing | Hierarchy | A11y  | Animation | Consistency | **Overall** |
|----------------|-----------|---------|-----------|-------|-----------|-------------|-------------|
| Chat           | 6         | 7       | 5         | 8     | 4         | 6           | **6.0**     |
| Sidebar        | 7         | 6       | 6         | 7     | 5         | 7           | **6.3**     |
| Input bar      | 7         | 7       | 7         | 8     | 6         | 7           | **7.0**     |
| Header         | 7         | 7       | 7         | 8     | 6         | 7           | **7.0**     |
| Knowledge Base | 6         | 7       | 6         | 7     | 5         | 6           | **6.2**     |
| Settings       | 7         | 7       | 7         | 8     | 5         | 7           | **6.8**     |
| Upload dialog  | 7         | 6       | 6         | 7     | 6         | 7           | **6.5**     |
| Empty states   | 5         | 5       | 5         | 5     | 3         | 4           | **4.5**     |
| Loading states | 5         | 6       | 5         | 6     | 4         | 5           | **5.2**     |
| Error states   | 6         | 6       | 6         | 6     | 4         | 5           | **5.5**     |
| **Average**    | **6.3**   | **6.4** | **6.0**   | **7.0**| **4.8**  | **6.1**     | **6.1**     |

---

## Detailed scores

### Chat (6.0)

| Dimension      | Score | Evidence |
|----------------|-------|----------|
| Typography     | 6     | Message body ~14px (no scale applied). Prose styles override content but not consistently. No visible type hierarchy. |
| Spacing        | 7     | Gap between messages ~20px (reasonable). `max-w-3xl` is 768px — slightly below target 800px. Padding 16px on sides is tight. |
| Hierarchy      | 5     | Everything has equal visual weight. Mode badge, sources, and actions compete. No clear focal point. |
| Accessibility  | 8     | Semantic HTML (markdown), focusable action buttons. No `aria-live` on streaming. No `aria-label` on icon buttons. |
| Animations     | 4     | Streaming text appears instantly (no fade). Mode badge and sources appear instantly. No transition on message appear. |
| Consistency    | 6     | Source pills, badges, and mode card all use different radii and padding. Border styles vary. |

**Key fixes:** Apply type scale. Add animation to streaming messages. Reduce visual noise (fewer borders). Widen container to 800px.

---

### Sidebar (6.3)

| Dimension      | Score | Evidence |
|----------------|-------|----------|
| Typography     | 7     | Session titles readable. No hierarchy between sections. |
| Spacing        | 6     | Items feel packed. 4px stack gap is tight. Padding inside items < 8px. |
| Hierarchy      | 6     | Active session distinguishable via bg. Sections not visually separated except by tight grouping. |
| Accessibility  | 7     | Navigation landmark present. Keyboard navigable. Focus indicator visible. |
| Animations     | 5     | No hover animation on items. No transition on session switch. No sidebar open/close animation. |
| Consistency    | 7     | All items same style. New Chat button different (correct). |

**Key fixes:** Increase spacing (8px stack gap, 12px item padding). Add hover lift. Add sidebar slide animation. Add section labels.

---

### Input bar (7.0)

| Dimension      | Score | Evidence |
|----------------|-------|----------|
| Typography     | 7     | Input text ~15px (good). Placeholder readable. |
| Spacing        | 7     | 12px vertical padding adequate. 4px side padding tight. Could be wider. |
| Hierarchy      | 7     | Send button visually dominant (correct). Attachment buttons secondary. |
| Accessibility  | 8     | Text input focusable. Send button has label. Enter sends. |
| Animations     | 6     | Focus glow transitions. No send button scale animation. No progress banner animation. |
| Consistency    | 7     | Matches other text inputs in the app. |

**Key fixes:** Wider padding (12px 16px). Glass effect polish. Add send button press animation. Add attachment button visual feedback.

---

### Header (7.0)

| Dimension      | Score | Evidence |
|----------------|-------|----------|
| Typography     | 7     | Logo and model badge sized well. No overflow issues. |
| Spacing        | 7     | 48px height adequate. Padding 16px works. |
| Hierarchy      | 7     | Logo is focal point (correct). Icons secondary. |
| Accessibility  | 8     | Banner landmark. Buttons focusable with aria-labels. |
| Animations     | 6     | No hover animations on action icons. Sticky positioning works but no transition. |
| Consistency    | 7     | Consistent with sidebar styling. |

**Key fixes:** Add hover animation on action icons. Ensure glass panel renders correctly on all breakpoints.

---

### Knowledge Base (6.2)

| Dimension      | Score | Evidence |
|----------------|-------|----------|
| Typography     | 6     | Filename truncated but readable. No metadata size hierarchy. |
| Spacing        | 7     | Card padding adequate. List spacing consistent. |
| Hierarchy      | 6     | All documents same weight. No search bar prominence. Delete button hidden in hover. |
| Accessibility  | 7     | Focusable items. Delete has confirmation. |
| Animations     | 5     | No hover lift on cards. No transition on delete. No search debounce. |
| Consistency    | 6     | Card style differs from other cards in the app. |

**Key fixes:** Redesign cards with proper structure. Add search bar + filter. Add hover lift. Add delete animation.

---

### Settings (6.8)

| Dimension      | Score | Evidence |
|----------------|-------|----------|
| Typography     | 7     | Section labels clear. Input labels visible. |
| Spacing        | 7     | Form spacing consistent. Tabs use adequate gap. |
| Hierarchy      | 7     | Tabs are primary navigation (correct). Save is primary action. |
| Accessibility  | 8     | Tab list with aria roles. Focus management works. |
| Animations     | 5     | No tab transition animation. No save confirmation animation. |
| Consistency    | 7     | Matches shadcn/ui defaults. Inputs consistent with rest of app. |

**Key fixes:** Add tab slide animation. Add save confirmation toast. Increase vertical spacing between sections.

---

### Upload dialog (6.5)

| Dimension      | Score | Evidence |
|----------------|-------|----------|
| Typography     | 7     | Status text clear. Filename readable. |
| Spacing        | 6     | Progress bar padding could be larger. Banner feels cramped. |
| Hierarchy      | 6     | Progress stages equal weight. Current stage not emphasized. |
| Accessibility  | 7     | Status announced via `aria-live`. Dismissible. |
| Animations     | 6     | Stage transitions exist but not smooth. Done animation simple. |
| Consistency    | 7     | Banner style differs from other banners. |

**Key fixes:** Redesign progress as stage list with visual connectors. Animate stage transitions. Improve done state.

---

### Empty states (4.5) ⚠️ Lowest

| Dimension      | Score | Evidence |
|----------------|-------|----------|
| Typography     | 5     | Welcome screen uses 14–16px text. No display-size heading. |
| Spacing        | 5     | Suggestion chips close together. Content not centered properly. |
| Hierarchy      | 5     | No clear focal point. Everything at once. |
| Accessibility  | 5     | No semantic headings. Empty states not labeled. |
| Animations     | 3     | No fade-in. No suggestion chip hover. Static. |
| Consistency    | 4     | Welcome screen style doesn't match rest of app. Inherits some boilerplate styles. |

**Key fixes:** Complete rebuild. Apply `display` type (32px). Add suggestion chips as pills. Add fade-in animation. Add clear CTA.

---

### Loading states (5.2)

| Dimension      | Score | Evidence |
|----------------|-------|----------|
| Typography     | 5     | Skeleton sizes approximate but don't match final content. |
| Spacing        | 6     | Skeleton positioning matches layout. |
| Hierarchy      | 5     | Multiple skeletons at once — no indication of which is primary. |
| Accessibility  | 6     | `aria-busy` not consistently applied. Screen readers hear nothing during load. |
| Animations     | 4     | Shimmer animation exists (pulse) but CSS-based shimmer is preferred. |
| Consistency    | 5     | Skeleton style differs by component. |

**Key fixes:** Standardized skeleton component with shimmer animation. `aria-busy="true"` on loading containers. Match skeleton dimensions to real content.

---

### Error states (5.5)

| Dimension      | Score | Evidence |
|----------------|-------|----------|
| Typography     | 6     | Error text readable. But no hierarchy between title and detail. |
| Spacing        | 6     | Inline banners have adequate padding. |
| Hierarchy      | 6     | Error color draws attention. Recovery action could be more prominent. |
| Accessibility  | 6     | Errors visible but not announced via `aria-live`. |
| Animations     | 4     | No error appear animation. No dismiss animation. |
| Consistency    | 5     | Different error styles across components. No standard error component. |

**Key fixes:** Create standard `InlineBanner` and `Toast` components for errors. Add `aria-live="assertive"`. Add slide-in animation. Standardize across all components.
