/* ------------------------------------------------------------------ */
/*  Semantic tokens — meaning-mapped color references                  */
/*  Components MUST use semantic tokens, never raw colors.             */
/*  They give purpose to a color, not its appearance.                  */
/*  Theming: only semantic.ts maps change between themes.              */
/* ------------------------------------------------------------------ */

import { colors } from './colors';

export const semantic = {
  /* Surface hierarchy */
  canvas:   colors.canvas,
  surface:  colors.surface,
  elevated: colors.elevated,
  overlay:  colors.overlay,
  hover:    colors.hover,

  /* Text hierarchy */
  text: {
    primary:   colors.text.primary,
    secondary: colors.text.secondary,
    disabled:  colors.text.disabled,
    inverse:   colors.text.inverse,
  },

  /* Borders */
  border: colors.border,
  input:  colors.input,

  /* Interactive */
  ring:  colors.ring,
  focus: colors.focus,

  /* Functional colors */
  accent:      colors.raw.blue,
  accentSoft:  '221 90% 55% / 0.1',
  success:     colors.raw.green,
  successSoft: '152 60% 40% / 0.12',
  warning:     colors.raw.amber,
  warningSoft: '38 90% 50% / 0.12',
  danger:      colors.raw.red,
  dangerSoft:  '0 68% 50% / 0.12',
  info:        colors.raw.purple,
  infoSoft:    '270 60% 50% / 0.12',

  /* Answer mode colors */
  answerMode: {
    grounded:    colors.raw.green,
    hybrid:      colors.raw.purple,
    synthesis:   colors.raw.amber,
    web:         colors.raw.blue,
    noEvidence:  colors.text.disabled,
  } as const,

  /* Answer mode background tints */
  answerModeBg: {
    grounded:   '152 60% 40% / 0.08',
    hybrid:     '270 60% 50% / 0.08',
    synthesis:  '38 90% 50% / 0.08',
    web:        '221 90% 55% / 0.08',
    noEvidence: '215 25% 58% / 0.05',
  } as const,
} as const;

export type SemanticColor = keyof typeof semantic;

/* Helper: convert a semantic color string "hue sat% light%" to CSS hsl() */
export function hsl(cssVar: string): string {
  if (cssVar.includes('hsl')) return cssVar;
  return `hsl(${cssVar})`;
}

/** Get Tailwind bg class for a semantic token */
export function bg(token: keyof typeof semantic): string {
  /* Map known semantic tokens to their custom CSS variable names */
  const map: Record<string, string> = {
    canvas:  'canvas',
    surface: 'surface',
    elevated:'elevated',
    overlay: 'overlay',
    hover:   'hover',
  };
  return map[token] ? `bg-${map[token]}` : '';
}
