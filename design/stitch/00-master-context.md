# Stitch Master Context

> Single source of truth for all Own Platform Stitch prompts.
>
> **Every prompt in this kit imports this context conceptually. Do not restate it.**
>
> Last updated: 2026-07-25 | Architecture v1.0 (Frozen)

---

## 1. Product Identity

**Own Platform** is an evidence-driven AI engineering platform. It continuously improves AI systems through observation, evaluation, experimentation, governance, and human approval.

### Product Family

| Module | Role |
|---|---|
| **OwnGPT** | Conversational AI assistant — primary interface |
| **OwnOps** | Operations Console — power user workspace |
| **OwnMonitor** | Observability & health monitoring |
| **OwnLearn** | Knowledge & continuous learning |
| **OwnLab** | Experiments & evaluation |
| **OwnAnalytics** | Dashboards & reports |
| **OwnArtifacts** | Engineering knowledge repository |
| **OwnConfig** | Configuration management |
| **OwnFlow** | Workflow automation |
| **OwnAgent** | Autonomous AI agents |

### Design Goals
- Conversation is the primary interaction surface. OwnGPT handles 80% of understanding; OwnOps handles 20% of deep work.
- Every claim is grounded in evidence. All AI outputs include inline citations.
- Human approval is never skippable for production changes.
- The platform is designed for long-term evolution. Optimize for maintainability, traceability, and correctness over speed.

---

## 2. Core Interaction Principles

1. **One primary action per screen.** If a screen has multiple primary actions, split it.
2. **Every page reachable in three clicks.** Maximum depth: 2 levels below root.
3. **Never interrupt without value.** Modals only for decisions and critical information.
4. **Never hide critical information.** Warnings and errors are always visible without interaction.
5. **Never remove user context.** List position, filters, and scroll state are preserved on navigation.
6. **Evidence before recommendations.** AI explains the situation before suggesting an action.
7. **Surface uncertainty.** Confidence scores accompany all conclusions. No false precision.
8. **No action without feedback.** Every user action produces a visible response within 100ms.
9. **Loading preserves layout stability.** Skeletons match final dimensions. No layout shift.
10. **Users should never lose work.** Form input is auto-saved. Drafts are persisted.
11. **Errors teach, not just notify.** Every error explains what went wrong and how to fix it.
12. **Status is always color-independent.** Shape + icon + text + color for all indicators.

---

## 3. Screen Recipes

37 screens are built from **10 reusable recipes**. No screen uses a unique behavioral model.

| Recipe | Purpose | Screens |
|---|---|---|
| **A — Overview + Actions** | Dashboard-style aggregate status with drill-down | 5 |
| **B — Collection + Inspector** | Browse, filter, search, and inspect items | 18 |
| **C — Conversation + Context** | AI interaction surface with context panels | 1 |
| **D — Timeline + Detail** | Chronological events with item inspection | 2 |
| **E — Compare + Analysis** | Side-by-side or unified comparison | 1 |
| **F — Editor + Preview** | Form with live preview and validation | 1 |
| **G — Review + Approval** | Evidence review with approve/reject decisions | 2 |
| **H — Monitoring + Status** | Real-time health and metrics | 2 |
| **I — Search + Explore** | Faceted search across artifact types | 2 |
| **J — Settings + Configuration** | Preference and configuration forms | 2 |

### Layout rules per recipe

- **Recipe A:** Two-column (65/35) with sticky command bar. Widgets load independently.
- **Recipe B:** Filter bar + collection + pagination. Detail via side panel or full page.
- **Recipe C:** Full-width message thread + optional right context panel (toggle).
- **Recipe D:** Vertical timeline with inline expandable detail.
- **Recipe E:** Side-by-side or unified diff with synchronized scroll.
- **Recipe F:** Form (left) + live preview (right). Sticky save/cancel footer.
- **Recipe G:** Evidence panel (left) + sticky decision panel (right).
- **Recipe H:** Health grid cards + detail panel on selection.
- **Recipe I:** Prominent search bar + collapsible filters + grouped results.
- **Recipe J:** Section sidebar/tabs + content area + sticky save.

---

## 4. Design System Philosophy

### Layers
```
Foundation → Design Tokens → Primitives → Compositions → Patterns → Recipes → Experiences
```

### Foundations
- **Typography:** Single sans-serif typeface + monospace for code. Roles (heading h1–h6, body, secondary, caption, code, label), not sizes.
- **Spacing:** Geometric or linear scale. Semantic spacing (inset, stack, inline, gutter). Density-aware (default + compact + relaxed).
- **Grid:** Column system with defined breakpoints. Content drives layout, not the reverse.
- **Elevation:** 5 levels (surface, raised, overlay, modal, notification). Never decorative.
- **Shape:** Square for structural, rounded for interactive, circular for avatars.

### Primitives (26 total)
Surface, Container, Panel, Card, Section, Divider, Heading, Text, Action, Input, Selection, Status, Indicator, Badge, Avatar, Navigation Item, Toolbar, Inspector, Timeline Entry, Conversation Message, Artifact Reference, Command Entry, Tool Result, Evidence Block, Approval Block, Progress Block.

Each primitive has a defined behavioral contract and state model (idle, loading, empty, error, success, disabled, selected, focused).

---

## 5. Visual Language Constraints

### Color
- **Neutral:** Multi-step gray scale for backgrounds, text, borders.
- **Accent:** Single accent color for interactive elements and links. Must meet WCAG AA.
- **Status:** Green (success), yellow (warning), red (error), blue (info), gray (neutral).
- **Severity:** Red (critical), orange (high), yellow (medium), blue (low), gray (none).
- **Charts:** Colorblind-safe palette (Okabe-Ito or similar).
- **Dark mode:** First-class, not inverted. Different neutral scale. Shadows become background shifts.

### Typography
- One body typeface. One monospace for code.
- Max 3 font weights per face (regular, medium, semibold or equivalent).
- Line length: 45–75 characters for body text.
- Tabular figures for data; proportional for prose.

### Elevation
- Surface (0): flat background.
- Raised (1): cards, panels, dropdowns — subtle shadow + background shift.
- Overlay (2): side panels, dialogs — noticeable shadow.
- Modal (3): modals — pronounced shadow + scrim backdrop.
- Notification (4): toasts, popovers — closest to user.

### Motion
- Functional transitions: 200–300ms. Feedback: <100ms. Entrance: 200–300ms.
- Use opacity + transform only (GPU-accelerated). Never animate layout properties.
- Respect `prefers-reduced-motion`: disable decorative animations, reduce essential to 50–100ms.
- Skeletons pulse at 1.5s cycle. No spinners for initial load.

### Icons
- Line icons with consistent stroke weight. Filled variants for active/selected only.
- Sizes: small (16px), medium (20px), large (24px). No scaling.
- Rounded caps and joins. Consistent bounding box.

### Borders
- Three weight levels: subtle (dividers), default (containers), strong (focus).
- Cards use borders OR elevation — never both.
- Focus indicators use offset ring, not border change.

---

## 6. Navigation Architecture

- **Sidebar:** Stable, does not reorganize. Sections: Home, Observe, Analyze, Govern, Operate, System.
- **Top bar:** Global command bar (search, time controls, notifications, user menu).
- **Breadcrumbs:** On detail screens. Clickable segments with dropdown alternatives.
- **Maximum depth:** 2 levels below root (3 total). Never deeper.
- **Context preservation:** List position, filters, scroll state preserved on navigation and return.
- **Deep links:** Stable URLs for all entities (findings, recommendations, experiments, etc.).
- **Keyboard shortcuts:** Global (`⌘K` search, `⌘,` settings), Navigation (`g h` dashboard, `g f` findings), Conversation (`⌘Enter` send, `⌘N` new), Operations (`⌘⇧N` create).

### Route hierarchy
```
/                           Dashboard
/conversation               OwnGPT
/findings                   Findings List
/findings/:id               Finding Detail
/recommendations            Recommendations List
/recommendations/:id        Recommendation Detail
/experiments                Experiments List
/experiments/new            Experiment Designer
/experiments/:id            Experiment Detail
/decisions                  Decisions List
/decisions/:id              Decision Detail
/configuration              Config Snapshots List
/configuration/:id          Config Snapshot Detail
/configuration/diff         Config Diff
/evaluation                 CE Dashboard
/evaluation/:id             Evaluation Detail
/operations                 OwnOps (Control Plane)
/operations/:capabilityId   Capability Health Detail
/automation                 Automation Dashboard
/automation/jobs/:id        Job Detail
/automation/schedules       Schedule Editor
/automation/triggers        Trigger Config
/capabilities               Capabilities Registry
/capabilities/:id           Capability Detail
/ledger                     Learning Ledger Browser
/ledger/:id                 Ledger Record Detail
/artifacts                  Artifact Explorer
/artifacts/:id              Artifact Detail
/analytics                  Analytics Overview
/analytics/:category        Analytics Category Detail
/knowledge                  Knowledge Base
/governance                 Governance Dashboard
/governance/audit           Audit Log
/settings                   Profile & Preferences
/help                       Help & Documentation
```

---

## 7. OwnGPT Design Constraints

OwnGPT must replicate the interaction philosophy of ChatGPT while integrating into Own Platform.

### Layout
- Conversation-first layout. Message thread is the primary content area.
- Minimal left sidebar (conversation list, settings). Hidden by default on desktop.
- Composer fixed at the bottom of the viewport. Multi-line textarea, auto-grows.
- Tool launcher beside the composer (icon button). Not permanently visible in sidebar.
- Right context panel (optional, toggleable). Shows artifact previews, tool output, evidence.

### What to hide by default
- NO confidence scores in the normal chat experience.
- NO grounding method, analysis pipeline, execution timer, or engineering telemetry.
- NO model selector visible in the default view (accessible via settings or developer mode).
- NO raw JSON or technical details in message responses.
- Advanced engineering details available ONLY through:
  - The optional right inspector panel.
  - Developer mode (`⌘⇧D`).
  - Navigating to OwnOps.

### What to show
- User and AI messages with clear visual distinction (alignment + avatar + background).
- Streaming response: text appears incrementally with blinking cursor.
- Citations: inline links to source artifacts (subtle, non-disruptive).
- Artifact cards: compact type icon + title + status + summary when AI references an artifact.
- Tool results: structured output in the message thread. Collapsible if large.
- Approval requests: inline decision card (approve/reject/request changes).
- Follow-up suggestions: 2–4 clickable chips below each AI response.
- Conversations listed in sidebar with search.

### Split view
- OwnGPT can split the view with OwnOps (50/50 or 60/40).
- Activate via drag, shortcut (`⌘⇧S`), or "Open in split" action.
- Adjustable divider between panels.
- Selection in OwnOps can inject context into OwnGPT.

---

## 8. Non-Negotiable UX Constraints

| Constraint | Rationale |
|---|---|
| No full-page loading spinners | Use skeletons matching content layout |
| No auto-playing animations | Respects prefers-reduced-motion |
| No decorative motion | Every animation has a communication purpose |
| No color-only information | Status/severity always use shape + icon + text + color |
| No orphan artifacts | Every created item has lineage to its parent |
| No hidden AI reasoning | "Show your work" always accessible |
| No skippable human approval | Production changes require explicit approval |
| No context loss on navigation | List position, filters, scroll preserved |
| No infinite scroll without count | Show total results before loading more |
| No empty screens without guidance | Every empty state explains what to do next |
| No modal for complex forms | Editors deserve full page or side panel |
| No destructive action without confirmation | Scale confirmation with consequence |

---

## 9. What Stitch Must Never Do

1. **Expose internal AI telemetry** (confidence scores, model names, latency, tokens) in the default chat experience. These belong in developer mode or OwnOps.
2. **Clutter the sidebar.** Sidebar contains navigation items, conversation list, and settings. No tool panels, configuration options, or status indicators in the sidebar.
3. **Invent new interaction patterns.** Use the 10 defined screen recipes. If a screen doesn't fit a recipe, challenge the screen definition.
4. **Create unique component variants.** Use the 26 defined primitives. Any new visual element should be a composition of existing primitives, not a new primitive.
5. **Design without dark mode.** Every screen must work in light and dark modes. Dark mode is not inverted light mode.
6. **Add decorative elements.** Gradients, patterns, illustrations that don't serve a communication purpose are forbidden.
7. **Separate OwnGPT from the platform.** OwnGPT is embedded in Own Platform. It shares the sidebar, top bar, navigation, and design system. It is not a separate app.
8. **Auto-approve or auto-execute actions.** Every production change requires human approval. Automation may recommend; humans apply.
9. **Use modals for primary navigation.** Modals are for transient decisions. Full-page navigation is for deep work.
10. **Ignore mobile.** All screens must degrade gracefully to mobile viewports. OwnGPT is the highest mobile priority.

---

## 10. Technology Stack (for reference)

| Layer | Technology |
|---|---|
| Framework | React 19 |
| Language | TypeScript |
| Build | Vite |
| Styling | Tailwind CSS |
| Components | shadcn/ui primitives |
| Animation | Motion (framer-motion) |
| Data fetching | TanStack Query |
| Routing | TanStack Router |
| Forms | React Hook Form + Zod |
| Icons | Lucide |
| Charts | Recharts |

---

## 11. Repository Structure

```
apps/web/src/
  app/                    Route definitions, layouts
  features/
    owngpt/               OwnGPT conversational workspace
    ownops/               Operations Console
    ownmonitor/           Monitoring & health
    ownlearn/             Knowledge base
    ownlab/               Experiments & evaluation
    ownanalytics/         Analytics & reports
    ownartifacts/         Artifact repository
    ownconfig/            Configuration management
  components/
    ui/                   shadcn/ui primitives
    primitives/           Custom platform primitives
    compositions/         Reusable compositions
    recipes/              Screen recipe layouts
  layouts/                Shared layout components
  hooks/                  Shared React hooks
  lib/                    Utility functions
  services/               API service layer
  types/                  TypeScript type definitions
  styles/                 Global styles, tokens
```

---

## 12. Prompt Execution Order

Use this order to generate screens. Each pass builds on the previous.

**Pass 1: Core experience**
1. Navigation shell (sidebar + top bar + layouts)
2. OwnGPT (conversation workspace)
3. OwnOps dashboard
4. Operator Dashboard

**Pass 2: Engineering modules**
5. OwnLearn (knowledge base)
6. OwnLab (experiments + evaluation)
7. OwnMonitor (operations + health)
8. OwnAnalytics (analytics + reports)
9. OwnArtifacts (artifact explorer)

**Pass 3: Configuration and polish**
10. OwnConfig (configuration management)
11. Settings + Help
12. Mobile adaptation
13. Dark mode
14. Final consistency review

---

## References

- Full architecture: `design/` directory (22 documents + 1 appendix)
- Screen recipes: `design/16-screen-recipes.md`
- Design system: `design/17-design-system-architecture.md`
- Visual language: `design/18-visual-language.md`
- Motion: `design/19-motion-feedback.md`
- Notifications: `design/20-notifications.md`
- OwnGPT: `design/21-owngpt-experience.md`
- Keyboard shortcuts: `design/appendix-keyboard-shortcuts.md`
