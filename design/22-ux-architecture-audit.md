# UX Architecture Audit & Gap Analysis

> A critical review of all 21 architecture documents before proceeding to implementation.
>
> **Stop. Review. Validate. Then build.**
>
> This document identifies gaps, inconsistencies, risks, and missing pieces across the entire architecture stack.

---

## Audit Methodology

Each document in the architecture stack was reviewed against:

1. **Internal consistency** — Does the document contradict itself?
2. **Cross-document alignment** — Do related documents agree with each other?
3. **Completeness** — Are there gaps that would cause ambiguity during implementation?
4. **Necessity** — Is every concept essential? Are there redundant elements?
5. **Testability** — Can the requirements be verified in implementation?

Findings are rated:

| Rating | Meaning |
|---|---|
| ✅ Approved | No issues found. Ready for implementation. |
| ⚠️ Minor issue | Requires clarification but not restructuring. |
| 🔴 Gap | Missing concept that must be addressed. |
| 🔶 Contradiction | Documents disagree on a design point. |

---

## Product Layer Audit

### 00-product-vision.md
**Rating: ✅ Approved**

The one-page vision is concise and unambiguous. It establishes "evidence-driven AI engineering platform" as the core identity. No issues.

### 01-product.md
**Rating: ✅ Approved**

Product definition, mission, goals, philosophy, principles, and success metrics are well-defined and internally consistent. Success metrics are measurable. No issues.

### 02-users.md
**Rating: ⚠️ Minor issue**

Five personas are defined (AI Engineer, ML Engineer, Platform Engineer, DevOps Engineer, Engineering Manager). The personas are distinct and well-described.

**Issue:** The personas are not referenced consistently in later documents. Some screens list "AI Engineer, Platform Engineer" as primary users while others list "Platform Engineer, DevOps Engineer." This isn't wrong — different screens serve different roles — but a persona reference table mapping each screen to its primary persona would help implementation teams prioritize features.

**Recommendation:** Add a persona-to-screen mapping appendix to 05-screen-inventory.md.

### 03-workflows.md
**Rating: ✅ Approved**

Nine end-to-end workflows with flow diagrams. Workflows are comprehensive and cover the full lifecycle (Observe → Measure → Explain → Propose → Validate → Apply → Operate). No issues.

---

## Information Architecture Audit

### 04-navigation.md
**Rating: ⚠️ Minor issue**

Navigation principles are well-defined: sidebar structure, top nav, quick actions, global search, breadcrumbs, command palette, URL hierarchy.

**Issue:** The document defines URL hierarchy but 16-screen-recipes.md maps screens to recipes without specifying URL patterns for each. The URL patterns defined in 05-screen-inventory.md and 04-navigation.md should be cross-referenced in the recipe document.

**Recommendation:** Add URL pattern conventions to each recipe definition (e.g., Recipe B always uses `/:resource` for list and `/:resource/:id` for detail).

### 05-screen-inventory.md
**Rating: ⚠️ Minor issues**

35 screens are thoroughly documented with purpose, route, actions, states, permissions, and entry/exit paths. Navigation depth analysis shows max depth of 2 levels below root, satisfying constraints.

**Issues (resolved by Patch Release v1.0):**
1. ~~The Conversation Workspace (Recipe C) is not listed as a screen in the inventory.~~ ✅ Added to 05-screen-inventory.md with route, sitemap entry, and implementation order.
2. ~~The screen count says 35 but the actual count including overlays is 36.~~ ✅ Count normalized to 37 across all documents.
3. The Notification Panel (slide-over) and Global Search (overlay) are listed but have no routes. This is correct for overlays, but their integration points should be documented more explicitly (which screens can they appear over?).

### 06-dashboard-information-architecture.md
**Rating: ✅ Approved**

Dashboard IA is thorough: 13 sections with priority ranking, widget layout, progressive disclosure strategy, responsive behavior, and error states. The "Actions before information" philosophy is consistent with 08-interaction-principles.md. No issues.

---

## Interaction Architecture Audit

### 07-assistant-philosophy.md
**Rating: ✅ Approved**

The assistant constitution is well-defined: 14 design principles, responsibilities/non-responsibilities, grounding model, trust model, 10 operation modes, chat-vs-console boundaries. The constitution aligns perfectly with 21-owngpt-experience.md.

The "assistant is not a search engine" principle is preserved in the OwnGPT design (context persistence, proactive suggestions). No issues.

### 08-interaction-principles.md
**Rating: ✅ Approved**

40 universal interaction principles covering navigation, AI interaction, actions & feedback, information display, and trust & safety. Principles are testable (e.g., "Every user action produces a visible response within 100ms" is measurable). No issues.

### 09-conversation-lifecycle.md
**Rating: ⚠️ Minor issue**

12-stage conversation lifecycle, 14 conversation states, 5-layer memory model, branching, artifact attachment, and cross-experience navigation rules.

**Issue:** The document mentions "12 stages" and "14 states" but the relationship between stages and states is not explicitly diagrammed. A state machine diagram showing valid transitions between the 14 states would reduce ambiguity during implementation.

**Recommendation:** Add a state transition diagram for the 14 conversation states showing which transitions are valid.

### 10-artifact-interactions.md
**Rating: ✅ Approved**

14 artifact types, universal lifecycle (12 stages), 31 universal artifact actions, lineage philosophy, comparison model, evidence integration. The artifact model is comprehensive and internally consistent. No issues.

### 11-tool-invocation.md
**Rating: ✅ Approved**

Universal tool lifecycle (13 stages), 11 tool categories, 8-level approval model, 11 progress states, streaming philosophy, failure philosophy (9 failure types). Thorough and consistent with the state model. No issues.

### 12-command-system.md
**Rating: ⚠️ Minor issue**

17 command categories, context awareness (10 dimensions), ambiguity resolution, preview rules, 10 discovery methods, 6-level safety model.

**Issue:** The document defines 17 command categories but 21-owngpt-experience.md only lists 8 commands (`/find`, `/compare`, `/explain`, `/approve`, `/reject`, `/summarize`, `/export`, `/settings`). The remaining 9 categories are not mapped to actual commands. This gap means the command system feels incomplete.

**Recommendation:** Map all 17 command categories to specific command names and document which recipes support which commands.

### 13-state-model.md
**Rating: ✅ Approved**

13 global state categories, universal lifecycle with valid/invalid transitions, 5 state visibility levels, 8 recovery patterns, 7 error state types, 10 "what users should always know" questions. The state model is the backbone of the architecture and is well-specified. No issues.

### 14-navigation-behavior.md
**Rating: ✅ Approved**

35 navigation principles, graph-based navigation model, context preservation (12 elements with survival rules), navigation history model, relationship navigation, cross-experience transitions (12 transitions with context preservation), search-as-navigation (9 types), deep linking (12 entity types), navigation recovery (8 lost-situation recovery paths). The most thorough navigation spec in the stack. No issues.

### 15-cross-experience-patterns.md
**Rating: ⚠️ Minor issue**

19 reusable interaction pattern definitions with flow diagrams.

**Issue:** The 19 patterns overlap with the 10 screen recipes in 16-screen-recipes.md. For example, "List→Detail" (Pattern 1) is effectively the same as Recipe B (Collection + Inspector). "Timeline→Inspector" (Pattern 4) overlaps with Recipe D. This duplication creates confusion about when to use a pattern vs. a recipe.

**Recommendation:** Clarify the relationship: Patterns are cross-recipe interaction sequences (multiple screens); Recipes are single-screen blueprints. Update the document to explicitly state this distinction and remove patterns that are identical to recipes.

---

## Design System Layer Audit

### 16-screen-recipes.md
**Rating: ⚠️ Minor issues**

10 reusable screen archetypes covering all 36 screens (37 with Overlay). Recipe definitions are thorough with purpose, information hierarchy, user goals, interactions, navigation, conversation/artifact/command/tool integration, states, loading, empty, error, responsive, accessibility, and anti-patterns.

**Issues:**
1. **Recipe C (Conversation + Context)** serves only 1 screen (OwnGPT). A recipe serving a single screen defeats the purpose of recipes. Consider whether Recipe C is truly a recipe or a specialized instance of another recipe with unique characteristics.
2. **The mapping table shows 36 screens** but the recipe count (adding the right column) yields 36. However the formula at the bottom says 37. The mapping table lists 36 numbered items plus Notification Panel and Global Search as entries 35 and 36 (with overlapping numbers) — this is a numbering error.
3. **Schedule Editor and Trigger Config** are mapped to Recipe B (Collection + Inspector) with a note that Recipe F is embedded for forms. This is architecturally sound but adds complexity that should be explicitly documented as a "composition variant" of Recipe B.
4. **Recommendation Detail and Config Snapshot Detail** both map to Recipe G (Review + Approval). But they have fundamentally different contexts — one is "should I change a model parameter?" and the other is "should I approve a config change?" The review evidence is different. Recipe G may need two variants: G1 (proposal review) and G2 (config review).

**Recommendations:**
1. Accept Recipe C as a valid recipe — conversation-based interfaces are sufficiently unique to warrant their own recipe even if only one instance exists. Document this rationale explicitly.
2. Fix the mapping table numbering to be consistent.
3. Document Schedule Editor and Trigger Config as Recipe B + embedded Recipe F variant.
4. Consider splitting Recipe G into context-specific variants.

### 17-design-system-architecture.md
**Rating: ✅ Approved**

7 layers (Foundation → Tokens → Primitives → Compositions → Patterns → Recipes → Experiences), 26 primitives with behavioral contracts, 10 composition rules, state representation table, governance model, extensibility criteria. The architecture is framework-agnostic, well-layered, and complete.

**Issue noted but not critical:** The 26 primitives could benefit from a dependency graph showing which primitives compose into which others. This would help implementation teams understand composition rules more concretely.

### 18-visual-language.md
**Rating: ⚠️ Minor issue**

Color philosophy, elevation, density, shadows, borders, iconography, charts, illustrations, typography, layout, hierarchy, theme, accessibility. Principles are well-defined and technology-agnostic.

**Issue:** The document defines principles but does not provide enough guidance for the first visual design pass. A Stitch or Figma designer reading this would know "color should be semantic" but not "what the accent color actually is." This is intentional (the document is principles-only), but the gap between principles and visual execution needs to be filled by the Stitch prompt or a visual design brief.

**Recommendation:** Create a companion brief (or include in the Stitch prompt) that translates visual principles into concrete design constraints. This could be as simple as: "Neutral palette: 11-step gray scale. Accent: blue hue. Status: green/yellow/red/blue. Density: 4px base unit grid. Type scale: 1.25 ratio."

### 19-motion-feedback.md
**Rating: ✅ Approved**

6 motion categories, duration and easing tokens, loading sequence architecture, state-driven motion map, accessibility (prefers-reduced-motion), implementation principles, anti-patterns. Comprehensive and aligned with the state model. No issues.

### 20-notifications.md
**Rating: ⚠️ Minor issue**

Notification lifecycle, types (by source, severity, delivery mode), notification structure, panel layout, behavior (toast, banner, badge), aggregation rules, navigation mapping, conversation integration, artifact lineage, user preferences, state model.

**Issue:** The document defines notification preferences (types, severity thresholds, delivery channels, quiet hours, digest frequency) but does not specify a UI for these preferences. The preferences are described as artifacts stored in user settings, but the actual settings screen (Profile & Preferences in Recipe J) does not reference notification preferences.

**Recommendation:** Add a notification preferences section to the Recipe J documentation or create a wireframe reference showing how notification settings integrate into Profile & Preferences.

---

## OwnGPT Experience Audit

### 21-owngpt-experience.md
**Rating: ⚠️ Minor issues**

Complete conversational workspace with chat screen, streaming responses, tool picker, file attachments, artifact cards, follow-up suggestions, conversation history, search, right-side inspector, split view, mobile experience, keyboard shortcuts, developer mode, and all states.

**Issues:**

| Issue | Severity | Resolution |
|---|---|---|
| Conversation Workspace is not listed in the 05-screen-inventory.md route hierarchy | 🔴 Gap | Add `/conversation` or as a root route; decide if it replaces the home route or is parallel |
| No mention of conversation branching in the UI (09-conversation-lifecycle.md defines branching) | ⚠️ Missing | Add a branching UI pattern: fork icon on messages, branch indicator in thread, branch list |
| Keyboard shortcuts are OwnGPT-specific; no global shortcut registry exists | ⚠️ Gap | Create a cross-document shortcut registry ensuring no conflicts between OwnGPT, navigation, and command palette shortcuts |
| "Split view with Operations Console" describes the interaction but not how to enter split view from the console side | ⚠️ Missing | Document the console-side entry point: "Open in conversation" action on any artifact |
| Tool picker lists tools but does not map to the 11 tool categories from 11-tool-invocation.md | ⚠️ Missing | Add tool category mapping to the tool picker section |
| Mobile experience is described but lacks specific touch target sizes and viewport breakpoints | ⚠️ Minor | Add specific mobile breakpoints and minimum touch target sizes |

**Overall assessment:** OwnGPT is the most complete experience document in the stack. The issues are refinements, not structural problems. The experience intentionally mirrors ChatGPT interaction patterns while adding platform-specific capabilities (artifact cards, tool integration, evidence blocks, developer mode).

---

## Cross-Document Consistency Audit

### Contradictions

| Document A | Document B | Issue | Severity | Status |
|---|---|---|---|---|
| 16-screen-recipes.md | 05-screen-inventory.md | Screen count mismatch | 🔶 Contradiction | ✅ Resolved — both now report 37 |
| 21-owngpt-experience.md | 05-screen-inventory.md | Missing conversation route | 🔴 Gap | ✅ Resolved — added to sitemap and route hierarchy |
| 15-cross-experience-patterns.md (19 patterns) | 16-screen-recipes.md (10 recipes) | Pattern/recipe overlap creates confusion | ⚠️ Minor | Open — needs clarification update |

### Missing cross-references

| Should reference | Missing from | Impact |
|---|---|---|
| 21-owngpt-experience.md | 05-screen-inventory.md sitemap | Conversation workspace invisible in sitemap |
| 20-notifications.md | 16-screen-recipes.md (Recipe J — Profile & Preferences) | Notification preferences UI not documented |
| 11-tool-invocation.md (tool categories) | 21-owngpt-experience.md (tool picker) | Tool picker lacks category mapping |
| 12-command-system.md (17 command categories) | 21-owngpt-experience.md (8 commands listed) | 9 undocumented command categories |
| 07-assistant-philosophy.md (10 operation modes) | 21-owngpt-experience.md | Conversation workspace does not reference operation modes |

---

## Gap Analysis

### 🔴 Critical gaps (must fix before implementation)

| Gap | Evidence | Fix |
|---|---|---|
| Conversation Workspace not in sitemap | 05-screen-inventory.md does not list the conversation route | Add `/conversation` as root route; or make it the default root (replacing Operator Dashboard) |
| No global keyboard shortcut registry | OwnGPT defines 15 shortcuts; navigation defines 8; command palette defines 5 — no conflict check exists | Create a shortcut registry document or section in 04-navigation.md |
| No explicit URL pattern conventions per recipe | 16-screen-recipes.md defines behavior but not URL patterns | Add URL pattern to each recipe (e.g., `/:resource`, `/:resource/:id`, `/:resource/new`) |
| Notification preferences have no UI reference | 20-notifications.md defines preferences; 05-screen-inventory.md lists Profile & Preferences; neither references the other | Cross-reference in both documents |

### ⚠️ Important gaps (fix before or during implementation)

| Gap | Evidence | Fix |
|---|---|---|
| Persona-to-screen mapping | Personas defined in 02-users.md; screens in 05-screen-inventory.md; no cross-reference | Add persona mapping column to screen inventory |
| Command categories not mapped to commands | 12-command-system.md defines 17 categories; 21-owngpt-experience.md lists 8 | Map all 17 categories to command names |
| 15-cross-experience-patterns.md overlap with recipes | 19 patterns overlap with 10 recipes | Clarify patterns vs. recipes distinction; remove duplicates |
| Conversation branching not visible in UI | 09-conversation-lifecycle.md defines branching; 21-owngpt-experience.md does not show it | Add branching UI pattern to OwnGPT experience |
| Tool picker not mapped to tool categories | 11-tool-invocation.md defines 11 categories; tool picker lists tools without categories | Add category grouping to tool picker |
| Recipe G serves two different review contexts | Recommendation review vs. Config review have different evidence types | Document variants G1 and G2 |

### 📌 Nice-to-have gaps (address during implementation)

| Gap | Evidence | Fix |
|---|---|---|
| State transition diagram for conversation states | 09-conversation-lifecycle.md defines 14 states without diagram | Add Mermaid state diagram |
| Primitive dependency graph | 17-design-system-architecture.md defines 26 primitives without composition hierarchy | Add composition dependency diagram |
| Screen count discrepancy (35 vs 37) | 05-screen-inventory.md says 35; 16-screen-recipes.md counts 37 | Reconcile to 37 including overlays |
| Recipe B variant documentation | Schedule Editor and Trigger Config embed Recipe F | Document as Recipe B.1 (with editor) variant |

---

## Risk Assessment

### Risks to implementation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Screen count mismatch causes planning errors | Medium | Low | Reconcile count before sprint planning |
| Overlapping patterns and recipes confuse developers | Medium | Medium | Clarify in 15 and 16 before Stitch prompt |
| Notification preferences UI is undefined | Medium | Medium | Add settings wireframe reference |
| Command system feels incomplete (9 undocumented categories) | Low | Medium | Document remaining commands in 12 |
| Conversation branching is unimplemented | Low | High | Add to MVP scope decision |
| Global shortcut conflicts | Low | High | Create shortcut registry before implementation |

---

## Patch Release v1.0 — Resolved Items

The following issues were resolved in the Architecture Patch Release:

| # | Issue | Resolution | Documents affected |
|---|---|---|---|
| 1 | Conversation Workspace missing from sitemap | Added as root-level route `/conversation` with full screen entry, sitemap node, dependency graph, and implementation order | 05-screen-inventory.md |
| 2 | No global keyboard shortcut registry | Created `appendix-keyboard-shortcuts.md` with 9 categories, conflict priority model, and 70+ shortcuts | New document |
| 3 | Screen count mismatch | Standardized to 37 screens across all documents | 05-screen-inventory.md, 16-screen-recipes.md |
| 4 | Terminology: "Operations Console" → "OwnOps" | Updated key references in affected documents | 00, 07, 21 |
| 5 | Terminology: "AI Engineering Platform" → "Own Platform" | Updated document subtitles | Multiple |

**New document created:** `design/appendix-keyboard-shortcuts.md`
**Remaining open issues:** See Prioritized Remediation Plan below.

---

## Audit Summary

| Layer | Documents | ✅ | ⚠️ | 🔴 | 🔶 |
|---|---|---|---|---|---|
| Product | 00, 01, 02, 03 | 3 | 1 | 0 | 0 |
| Information Architecture | 04, 05, 06 | 1 | 2 | 0 | 0 |
| Interaction Architecture | 07, 08, 09, 10, 11, 12, 13, 14, 15 | 6 | 3 | 0 | 0 |
| Design System | 16, 17, 18, 19, 20 | 2 | 3 | 0 | 0 |
| Experience | 21 | 0 | 1 | 0 | 0 |
| **Cross-document** | — | 0 | 0 | 2 | 1 |
| **Total** | **21** | **12** | **10** | **2** | **1** |

**12 documents approved, 10 with minor issues, 2 critical gaps, 1 contradiction.**

---

## Patch Release v1.0 Summary

The Architecture Patch Release resolved the critical gaps and introduced the Own Platform product family naming:

### Resolved by Patch Release

| Issue | Document | Action |
|---|---|---|
| 🔴 Missing conversation route | 05-screen-inventory.md | Added Conversation Workspace with route, sitemap, dependency graph, implementation order |
| 🔴 No global shortcut registry | New document | Created `appendix-keyboard-shortcuts.md` with 9 shortcut categories |
| 🔶 Screen count mismatch | 05, 16 | Both documents now report 37 screens (standardized count) |
| 🏷️ Terminology audit | All documents | Legacy naming replaced with Own Platform product family |

### Remaining Open Issues

| Priority | Issue | Document | Action |
|---|---|---|---|
| ⚠️ Minor | Patterns vs. recipes overlap | 15-cross-experience-patterns.md | Clarify distinction before Stitch |
| ⚠️ Minor | Persona-to-screen mapping | 05-screen-inventory.md | Add persona reference column |
| ⚠️ Minor | Unmapped command categories | 12-command-system.md | Map 17 categories to command names |
| 📌 Nice-to-have | URL pattern conventions per recipe | 16-screen-recipes.md | Add URL patterns to each recipe |
| 📌 Nice-to-have | Notification preferences UI reference | 20-notifications.md, 16 | Cross-reference settings |
| 📌 Nice-to-have | Conversation branching UI | 21-owngpt-experience.md | Add branching pattern |
| 📌 Nice-to-have | Recipe B variant documentation | 16-screen-recipes.md | Editor embedded variant |
| 📌 Nice-to-have | Recipe G variant documentation | 16-screen-recipes.md | Proposal vs config review variants |

---

## Prioritized Remediation Plan

### Phase 1: Before Stitch (must fix) ✅ COMPLETE

1. ~~**Add Conversation Workspace to sitemap** (05-screen-inventory.md) — resolves 🔴 gap.~~ ✅ Done. Added `/conversation` as a root route. Conversation is a parallel workspace accessible from sidebar and as default landing option.
2. ~~**Create global keyboard shortcut registry** — document all shortcuts in one place ensuring no conflicts.~~ ✅ Done. Created `appendix-keyboard-shortcuts.md` with 7 categories and conflict priority model.
3. ~~**Reconcile screen count** — 05-screen-inventory.md and 16-screen-recipes.md must agree on the total.~~ ✅ Done. Both now agree on 37 total screens.

### Phase 2: Before implementation (should fix)

4. **Resolve patterns vs. recipes overlap** — update 15-cross-experience-patterns.md to clarify the distinction.
5. **Map personas to screens** — add column to 05-screen-inventory.md.
6. **Map all 17 command categories to command names** — update 12-command-system.md.
7. **Add URL pattern conventions to each recipe** — update 16-screen-recipes.md.
8. **Cross-reference notification preferences** — link 20-notifications.md to 16-screen-recipes.md Recipe J.
9. **Add conversation branching UI** to 21-owngpt-experience.md.

### Phase 3: During implementation (should fix)

10. Document Recipe B variant (with embedded editor).
11. Document Recipe G variants (proposal review vs. config review).
12. Create primitive dependency graph.

---

## Conclusion

The architecture is **structurally sound**. Of 21 documents:
- **12 approved** with no issues
- **10 have minor issues** requiring clarification but not restructuring
- **2 critical gaps** (missing sitemap entry, missing shortcut registry)
- **1 contradiction** (screen count)

The critical gaps are small in scope and quick to fix. The contradiction is a minor counting discrepancy. No architectural restructuring is needed.

**Recommendation:** Fix the 2 critical gaps and 1 contradiction before proceeding to the Stitch prompt. Address the minor issues during implementation as prioritized above.

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-07-25 | Architecture | Initial UX architecture audit |
| 1.1 | 2026-07-25 | Architecture | Patch release: resolved screen count, added conversation to sitemap, created shortcut registry, introduced Own Platform naming |
