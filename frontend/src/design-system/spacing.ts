/* ------------------------------------------------------------------ */
/*  Spacing tokens — 8px grid, no exceptions                          */
/*  Usage: spacing[4] → 4px pixel value, Tailwind p-1 for 4px        */
/* ------------------------------------------------------------------ */

const _BASE = 4; /* 1 Tailwind unit = 4px */

export const spacing = {
  0:  0,
  1:  _BASE * 1,      /* 4px  */
  2:  _BASE * 2,      /* 8px  */
  3:  _BASE * 3,      /* 12px */
  4:  _BASE * 4,      /* 16px */
  5:  _BASE * 5,      /* 20px */
  6:  _BASE * 6,      /* 24px */
  8:  _BASE * 8,      /* 32px */
  10: _BASE * 10,     /* 40px */
  12: _BASE * 12,     /* 48px */
  16: _BASE * 16,     /* 64px */
} as const;

export type SpacingToken = keyof typeof spacing;

/* Semantic spacing references */
export const gap = {
  xs:   spacing[1],    /* 4px  — icon to icon, tight stack */
  sm:   spacing[2],    /* 8px  — badge gap, inline elements */
  md:   spacing[3],    /* 12px — section-to-metadata */
  lg:   spacing[4],    /* 16px — paragraph gap, card padding */
  xl:   spacing[6],    /* 24px — message gap, section spacing */
  '2xl': spacing[8],   /* 32px — page section spacing */
  '3xl': spacing[10],  /* 40px — layout margins */
} as const;

export const padding = {
  inset: {
    sm: spacing[2],    /* 8px  — tight chip */
    md: spacing[3],    /* 12px — input bar */
    lg: spacing[4],    /* 16px — card default */
  },
  stack: {
    xs: spacing[1],
    sm: spacing[2],
    md: spacing[3],
    lg: spacing[4],
  },
} as const;
