/* ------------------------------------------------------------------ */
/*  Color tokens — single source of truth for all UI color values    */
/*  Based on CSS custom properties defined in index.css              */
/*  All values are HSL strings or raw hue/saturation/lightness.      */
/* ------------------------------------------------------------------ */

export const colors = {
  /* Brand */
  primary: {
    hue: 221, sat: 90, light: 55,
    hsl: '221 90% 55%',
  },

  /* Surfaces */
  canvas:   '222 50% 7%',    /* page background */
  surface:  '222 48% 9%',    /* card / elevated surface */
  overlay:  '222 48% 9%',    /* modal / popover */
  elevated: '220 40% 14%',   /* secondary surface */
  hover:    '220 40% 18%',   /* accent / hover */

  /* Text */
  text: {
    primary:   '210 60% 97%',
    secondary: '215 25% 58%',
    disabled:  '215 25% 58% / 0.5',
    inverse:   '0 0% 0%',
  },

  /* Borders */
  border: '220 35% 16%',
  input:  '220 35% 16%',

  /* Interactive */
  ring:   '221 90% 55%',
  focus:  '221 90% 55%',

  /* Semantic — mapped in semantic.ts */
  raw: {
    white:      '0 0% 100%',
    black:      '0 0% 0%',
    transparent:'0 0% 0% / 0',
    blue:       '221 90% 55%',
    green:      '152 60% 40%',
    amber:      '38 90% 50%',
    red:        '0 68% 50%',
    purple:     '270 60% 50%',
    gray:       '220 40% 14%',
  },
} as const;

export type ColorKey = keyof typeof colors;
