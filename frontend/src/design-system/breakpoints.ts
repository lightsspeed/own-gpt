/* ------------------------------------------------------------------ */
/*  Breakpoint tokens — responsive design thresholds                   */
/* ------------------------------------------------------------------ */

export const breakpoints = {
  sm:   640,
  md:   768,
  lg:   1024,
  xl:   1280,
  '2xl': 1400,
} as const;

export type Breakpoint = keyof typeof breakpoints;

export function mediaMin(bp: Breakpoint): string {
  return `@media (min-width: ${breakpoints[bp]}px)`;
}

export function mediaMax(bp: Breakpoint): string {
  return `@media (max-width: ${breakpoints[bp] - 1}px)`;
}
