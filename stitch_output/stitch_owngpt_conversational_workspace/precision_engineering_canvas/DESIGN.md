---
name: Precision Engineering Canvas
colors:
  surface: '#13131b'
  surface-dim: '#13131b'
  surface-bright: '#393841'
  surface-container-lowest: '#0d0d15'
  surface-container-low: '#1b1b23'
  surface-container: '#1f1f27'
  surface-container-high: '#292932'
  surface-container-highest: '#34343d'
  on-surface: '#e4e1ed'
  on-surface-variant: '#c7c4d7'
  inverse-surface: '#e4e1ed'
  inverse-on-surface: '#303038'
  outline: '#908fa0'
  outline-variant: '#464554'
  surface-tint: '#c0c1ff'
  primary: '#c0c1ff'
  on-primary: '#1000a9'
  primary-container: '#8083ff'
  on-primary-container: '#0d0096'
  inverse-primary: '#494bd6'
  secondary: '#4fdbc8'
  on-secondary: '#003731'
  secondary-container: '#04b4a2'
  on-secondary-container: '#003f38'
  tertiary: '#ffb783'
  on-tertiary: '#4f2500'
  tertiary-container: '#d97721'
  on-tertiary-container: '#452000'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#07006c'
  on-primary-fixed-variant: '#2f2ebe'
  secondary-fixed: '#71f8e4'
  secondary-fixed-dim: '#4fdbc8'
  on-secondary-fixed: '#00201c'
  on-secondary-fixed-variant: '#005048'
  tertiary-fixed: '#ffdcc5'
  tertiary-fixed-dim: '#ffb783'
  on-tertiary-fixed: '#301400'
  on-tertiary-fixed-variant: '#703700'
  background: '#13131b'
  on-background: '#e4e1ed'
  surface-variant: '#34343d'
  bg-primary: '#0A0A0A'
  bg-secondary: '#171717'
  bg-tertiary: '#262626'
  slate-gray: '#404040'
  border-subtle: '#262626'
  text-primary: '#F5F5F5'
  text-secondary: '#A3A3A3'
  ai-presence: '#6366F1'
  success-teal: '#14B8A6'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.01em
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  sidebar-width: 280px
  context-panel-width: 400px
  max-content-width: 800px
  gutter: 24px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 24px
  inset-md: 16px
---

## Brand & Style

The design system is engineered for high-stakes enterprise environments where clarity, evidence, and precision are paramount. It adopts a **Minimalist / Corporate Modern** aesthetic that prioritizes content density and functional breathing room, mirroring the focused experience of sophisticated developer tools.

The interface should evoke a sense of **quiet authority and technical reliability**. It avoids decorative flourishes, using whitespace as a structural element to separate intent from execution. The emotional response is one of "calm control"—user-led interactions supported by background AI intelligence.

**Key Stylistic Pillars:**
- **Clarity over Decoration:** No gradients or unnecessary textures. High-quality typography and consistent line-weights drive the visual language.
- **Contextual Intelligence:** Deep engineering telemetry is layered, appearing only when requested via developer modes or inspector panels.
- **High Utility:** Interaction patterns are optimized for speed, utilizing keyboard-first navigation and clear functional zones.

## Colors

The palette is anchored in a **Dark Mode first** philosophy to reduce eye strain during long engineering sessions. 

- **Primary (Electric Indigo):** Reserved for primary actions, the AI streaming cursor, and interactive citations. It signifies "active intelligence."
- **Secondary (Technical Teal):** Used for successful deployments, healthy system statuses, and validated evidence.
- **Neutrals (Deep Charcoal & Slate):** Provide the structural foundation. We use a tiered neutral system to create depth without relying on heavy shadows.
- **Backgrounds:** `bg-primary` is the infinite canvas for chat threads; `bg-secondary` is used for sidebars and AI message bubbles to create a subtle containerized feel.

## Typography

This design system uses **Inter** for all UI elements and prose to ensure maximum legibility and a neutral, professional tone. **JetBrains Mono** is employed for code blocks, terminal outputs, and technical identifiers to provide the necessary character distinction required for engineering tasks.

**Usage Guidelines:**
- **Body Text:** Use `body-md` (15px) for the main conversation thread to achieve a "ChatGPT" feel that balances information density and readability.
- **Code Blocks:** Should always use `code-md` with a background container to separate logic from conversation.
- **Headings:** Keep headings concise. Use `headline-md` for artifact titles within cards.
- **Tabular Data:** Use `jetbrainsMono` for numerical data in tables to ensure alignment.

## Layout & Spacing

The layout follows a **Fixed-Fluid Hybrid** model. The conversation thread is centered with a max-width of 800px to maintain an optimal line length (45-75 characters), while the surrounding sidebar and context panels are fixed-width.

**Grid & Alignment:**
- **Desktop:** 12-column grid is used for "OwnOps" screens, but "OwnGPT" utilizes a centered single-column thread for focus.
- **Sidebars:** The left navigation sidebar (280px) is collapsible to maximize the canvas.
- **Context Panel:** The right panel (400px) slides over content or pushes it depending on the "Split View" state.
- **Spacing Rhythm:** An 8px linear scale is used. Use `stack-lg` (24px) for gaps between different message turns and `stack-sm` (8px) for internal message elements (name to bubble).

## Elevation & Depth

Hierarchy is established through **Tonal Layering** rather than heavy shadows, maintaining a flat, modern engineering aesthetic.

- **Level 0 (Surface):** The main canvas background (`bg-primary`).
- **Level 1 (Raised):** Sidebars and cards use a slightly lighter background (`bg-secondary`) and a 1px border (`border-subtle`). 
- **Level 2 (Overlay):** Context panels and dropdowns use Level 1 styling but add a subtle ambient shadow (0px 4px 12px rgba(0,0,0,0.5)) to indicate they are floating above the thread.
- **Scrim:** Used only for mobile overlays to focus user attention on the active drawer or modal.

## Shapes

The design system utilizes **Rounded** (8px-12px) geometry for all interactive and container elements. This softens the technical aesthetic, making the platform feel approachable and modern.

- **Standard Buttons/Inputs:** 8px radius.
- **Message Bubbles & Cards:** 12px radius.
- **Avatars:** Circular (100% radius) to distinguish human/AI entities from UI components.
- **Code Blocks:** 8px radius to match the container logic.

## Components

### Buttons & Interactive
- **Primary:** Solid `ai-presence` (Indigo) with white text. 8px radius.
- **Secondary:** Transparent with `border-subtle`.
- **Ghost:** No border, text-only until hover. Used for toolbar icons.

### Message Bubbles
- **User:** Right-aligned, plain text, no background. Emphasizes user intent as a "command."
- **AI:** Left-aligned, `bg-secondary` background. 12px radius. Top-left corner is sharp (0px) when adjacent to the avatar to create a directional pointer effect.

### Composer
- **Fixed Position:** Always pinned to the bottom of the viewport with a subtle top border.
- **Multi-line:** Auto-expands up to 8 lines before internal scrolling kicks in.
- **Tools/Attach:** Icon buttons flanking the text area. 

### Artifact Cards
- **Inline:** Reside within AI responses. Feature a 1px border, a type-specific icon, and a "Success Teal" status indicator if applicable.
- **Interaction:** Entire card is a trigger for the Right Context Panel.

### Input Fields
- **Focus State:** 2px solid `ai-presence` ring with a 2px offset to ensure visibility in dark mode.
- **Placeholder:** `text-secondary` color, providing clear guidance without competing with user input.