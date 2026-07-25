/* ------------------------------------------------------------------ */
/*  Shadow tokens — only 5 levels, no custom shadows                   */
/* ------------------------------------------------------------------ */

export const shadows = {
  sm:    '0 1px 3px 0 rgb(0 0 0 / 0.3)',
  md:    '0 4px 12px 0 rgb(0 0 0 / 0.4)',
  lg:    '0 8px 32px 0 rgb(0 0 0 / 0.5)',
  glow:  '0 0 20px hsl(221 90% 55% / 0.35), 0 0 60px hsl(221 90% 55% / 0.1)',
  inner: 'inset 0 1px 0 0 rgb(255 255 255 / 0.05)',
} as const;

export type ShadowToken = keyof typeof shadows;

export function shadowClass(token: ShadowToken): string {
  return `shadow-${token}`;
}
