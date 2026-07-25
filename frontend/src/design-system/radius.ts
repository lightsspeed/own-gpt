/* ------------------------------------------------------------------ */
/*  Border radius tokens                                                */
/* ------------------------------------------------------------------ */

export const radius = {
  xs:    6,
  sm:    8,
  md:    12,       /* default — matches --radius in index.css */
  lg:    16,
  xl:    20,
  full:  9999,
} as const;

export type RadiusToken = keyof typeof radius;

/** Map radius token to Tailwind class. */
export function radiusClass(token: RadiusToken): string {
  const map: Record<RadiusToken, string> = {
    xs:   'rounded-xs',
    sm:   'rounded-sm',
    md:   'rounded-md',
    lg:   'rounded-lg',
    xl:   'rounded-xl',
    full: 'rounded-full',
  };
  return map[token];
}
