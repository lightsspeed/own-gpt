# Appendix: Keyboard Shortcuts

> Authoritative global keyboard shortcut registry for the Own Platform.
>
> All shortcuts defined in individual documents (navigation, conversation, command system, etc.) are consolidated here.
>
> Individual documents reference this appendix instead of redefining shortcuts.

---

## Conventions

| Notation | Meaning |
|---|---|
| `⌘` | Command key (macOS) / Ctrl key (Windows, Linux) |
| `⌥` | Option (macOS) / Alt (Windows, Linux) |
| `⇧` | Shift |
| `⌫` | Backspace / Delete |
| `Space` | Spacebar |
| `↑ ↓ ← →` | Arrow keys |

Shortcut conflicts are resolved by priority: Global > Navigation > Conversation > Contextual.

---

## Global

| Shortcut | Action | Scope | Defined in |
|---|---|---|---|
| `⌘K` | Open command palette / search | Always active | 04-navigation.md |
| `⌘,` | Open settings | Always active | 04-navigation.md |
| `⌘⇧?` | Show keyboard shortcuts reference | Always active | — |
| `⌘⇧D` | Toggle developer mode | Always active | 21-owngpt-experience.md |
| `⌘R` | Refresh current view | Always active | 06-dashboard-ia.md |
| `Escape` | Close overlay / panel / modal / cancel | Always active | 04-navigation.md |
| `⌘⇧M` | Toggle dark/light mode | Always active | — |
| `⌘Q` | Sign out confirmation | Always active | — |

---

## Navigation

| Shortcut | Action | Scope | Defined in |
|---|---|---|---|
| `g h` | Go to Dashboard | Any screen | 06-dashboard-ia.md |
| `g f` | Go to Findings List | Any screen | — |
| `g r` | Go to Recommendations List | Any screen | — |
| `g e` | Go to Experiments List | Any screen | — |
| `g c` | Go to Configuration | Any screen | — |
| `g d` | Go to Decisions List | Any screen | — |
| `g o` | Go to Operations (OwnOps) | Any screen | — |
| `g a` | Go to Automation | Any screen | — |
| `g s` | Go to Settings | Any screen | — |
| `g /` | Go to Artifact Explorer | Any screen | — |
| `⌘[` | Navigate back in history | Any screen | 14-navigation-behavior.md |
| `⌘]` | Navigate forward in history | Any screen | 14-navigation-behavior.md |
| `⌘⇧H` | Go to conversation history | Any screen | 21-owngpt-experience.md |
| `⌘1`–`⌘6` | Focus dashboard widget (1–6) | Dashboard only | 06-dashboard-ia.md |

---

## Conversation (OwnGPT)

| Shortcut | Action | Scope | Defined in |
|---|---|---|---|
| `⌘Enter` | Send message | Conversation only | 21-owngpt-experience.md |
| `⌘⇧Enter` | Send without streaming (full response) | Conversation only | 21-owngpt-experience.md |
| `↑` (empty input) | Edit last message | Conversation only | 21-owngpt-experience.md |
| `Escape` | Stop streaming / clear input | Conversation only | 21-owngpt-experience.md |
| `⌘C` | Stop streaming (during response) | Conversation only | 21-owngpt-experience.md |
| `⌘N` | New conversation | Conversation only | 21-owngpt-experience.md |
| `⌘⇧C` | Toggle context panel | Conversation only | 21-owngpt-experience.md |
| `⌘.` | Focus context panel | Conversation only | 21-owngpt-experience.md |
| `⌘⇧S` | Toggle split view | Conversation only | 21-owngpt-experience.md |
| `⌘⌫` | Clear current conversation | Conversation only | 21-owngpt-experience.md |
| `⌘⇧E` | Export conversation | Conversation only | 21-owngpt-experience.md |
| `⌘⇧K` | Open tool picker | Conversation only | 21-owngpt-experience.md |
| `⌘[` | Previous conversation in history | Conversation only | 21-owngpt-experience.md |
| `⌘]` | Next conversation in history | Conversation only | 21-owngpt-experience.md |
| `⌘⇧F` | Search conversations | Conversation only | 21-owngpt-experience.md |
| `/` (input start) | Open command suggestions | Conversation only | 12-command-system.md |

---

## Command System

| Shortcut | Action | Scope | Defined in |
|---|---|---|---|
| `/` | Type command prefix in input | Any input field | 12-command-system.md |
| `Tab` | Autocomplete command | Command input active | 12-command-system.md |
| `↑ ↓` | Navigate command history | Command input active | 12-command-system.md |
| `Enter` | Execute command | Command preview active | 12-command-system.md |
| `Escape` | Cancel command | Command preview active | 12-command-system.md |

---

## Artifacts

| Shortcut | Action | Scope | Defined in |
|---|---|---|---|
| `Enter` | Open selected artifact detail | List/collection active | 16-screen-recipes.md |
| `Space` | Preview selected artifact (quick peek) | List/collection active | — |
| `⌘A` | Select all items in list | List/collection active | — |
| `Escape` | Close artifact detail / preview | Detail/preview active | 16-screen-recipes.md |
| `⌘⇧E` | Export selected artifact(s) | Selection active | 10-artifact-interactions.md |
| `⌘C` | Copy artifact ID or link | Detail active | — |
| `⌘⇧V` | View lineage graph | Detail active | 10-artifact-interactions.md |

---

## Operations (OwnOps)

| Shortcut | Action | Scope | Defined in |
|---|---|---|---|
| `⌘⇧N` | Create new item (finding, experiment, etc.) | Context-dependent | 16-screen-recipes.md |
| `⌘S` | Save current form / editor | Editor active | 16-screen-recipes.md |
| `⌘⇧P` | Preview current editor state | Editor active | 16-screen-recipes.md |
| `⌘⌫` | Delete selected item | Selection active | — |
| `⌘Z` | Undo last action | Action-dependent | 14-navigation-behavior.md |
| `⌘⇧Z` | Redo last action | Action-dependent | 14-navigation-behavior.md |
| `⌘F` | Find / search within current view | Any list | — |

---

## Accessibility

| Shortcut | Action | Scope | Defined in |
|---|---|---|---|
| `Tab` | Move focus to next interactive element | Always active | 08-interaction-principles.md |
| `⇧Tab` | Move focus to previous interactive element | Always active | 08-interaction-principles.md |
| `Enter` / `Space` | Activate focused element | Focus active | 08-interaction-principles.md |
| `Escape` | Return from detail to list, close panel | Context-dependent | 14-navigation-behavior.md |
| `⌘⇧A` | Toggle accessibility mode (high contrast, larger text) | Always active | — |

---

## Developer Mode

| Shortcut | Action | Scope | Defined in |
|---|---|---|---|
| `⌘⇧D` | Toggle developer mode | Always active | 21-owngpt-experience.md |
| `⌘⇧I` | Open raw response viewer | Developer mode active | 21-owngpt-experience.md |
| `⌘⇧P` | Open prompt preview | Developer mode active | 21-owngpt-experience.md |
| `⌘⇧L` | Open latency breakdown | Developer mode active | 21-owngpt-experience.md |
| `⌘⇧T` | Open token usage panel | Developer mode active | 21-owngpt-experience.md |

---

## Future Reserved

| Shortcut | Purpose |
|---|---|
| `⌥1`–`⌥9` | Reserved for workspace switching |
| `⌃↑` | Reserved for OwnAgent panel |
| `⌃Space` | Reserved for voice input |
| `⌘⇧R` | Reserved for recording macros |

---

## Shortcut Conflict Priority

When a key combination is bound in multiple contexts, the most specific context wins:

```
1. Modal / Dialog (highest priority — active only while modal is open)
2. Developer Mode (active only when dev mode is on)
3. Conversation (active only in conversation workspace)
4. Editor (active only in editor/forms)
5. Navigation (active on any screen)
6. Global (lowest priority — fallback when nothing else matches)
```

---

## Defining New Shortcuts

New shortcuts must:
1. Not conflict with existing shortcuts at the same or higher priority level.
2. Be registered in this appendix before implementation.
3. Follow the naming conventions.
4. Include a discoverable path (menu item, tooltip, or shortcut reference screen).

---

## Related

- All shortcuts are also accessible via the Help & Documentation screen.
- The command palette (`⌘K`) provides a discoverable alternative for all shortcuts.
- Shortcut preferences (customization) is a future feature (post-v1).
