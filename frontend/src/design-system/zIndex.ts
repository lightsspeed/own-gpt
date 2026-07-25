/* ------------------------------------------------------------------ */
/*  Z-index tokens — layered stacking system                           */
/* ------------------------------------------------------------------ */

export const zIndex = {
  base:      0,
  dropdown:  100,
  sticky:    200,
  overlay:   300,
  modal:     400,
  toast:     500,
  tooltip:   600,
} as const;

export type ZIndexLayer = keyof typeof zIndex;

export function zIndexClass(layer: ZIndexLayer): string {
  return `z-${zIndex[layer]}`;
}
