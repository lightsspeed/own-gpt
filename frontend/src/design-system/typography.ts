/* ------------------------------------------------------------------ */
/*  Typography tokens                                                  */
/*  Single source of truth for font size, weight, and line-height.     */
/* ------------------------------------------------------------------ */

export const typography = {
  /* Font family */
  fontFamily: "'Inter', system-ui, sans-serif",
  fontMono: "'JetBrains Mono', 'Fira Code', monospace",

  /* Type scale — name → { size, lineHeight, fontWeight } */
  scale: {
    display:  { size: 32,  lineHeight: 1.2,  weight: 600 } as const,
    h1:       { size: 28,  lineHeight: 1.25, weight: 600 } as const,
    h2:       { size: 24,  lineHeight: 1.3,  weight: 600 } as const,
    h3:       { size: 20,  lineHeight: 1.35, weight: 600 } as const,
    title:    { size: 18,  lineHeight: 1.4,  weight: 600 } as const,
    body:     { size: 15,  lineHeight: 1.6,  weight: 400 } as const,
    small:    { size: 13,  lineHeight: 1.4,  weight: 500 } as const,
    caption:  { size: 12,  lineHeight: 1.4,  weight: 400 } as const,
    micro:    { size: 11,  lineHeight: 1.3,  weight: 500 } as const,
  } as const,

  /* Utility — px values for direct use */
  px: {
    display: 32,
    h1: 28,
    h2: 24,
    h3: 20,
    title: 18,
    body: 15,
    small: 13,
    caption: 12,
    micro: 11,
  } as const,
} as const;

export type TypeScaleName = keyof typeof typography.scale;

/** Get Tailwind-compatible `text-*` class for a scale name. */
export function textClass(name: TypeScaleName): string {
  return `text-${name}`;
}
