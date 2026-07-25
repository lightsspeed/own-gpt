/* ------------------------------------------------------------------ */
/*  Reusable Tailwind class strings                                    */
/*  Centralize common utility-class combinations here.                 */
/*  Components reference these by name, never raw classes.             */
/* ------------------------------------------------------------------ */

/* ── Surfaces ─────────────────────────────────────────── */
export const card =
  'rounded-xl border border-border bg-surface text-text-primary shadow-sm';

export const surfaceElevated =
  'rounded-lg bg-elevated text-text-primary';

export const panel =
  'rounded-lg border border-border bg-surface';

export const dialog =
  'rounded-xl border border-border bg-overlay shadow-lg';

export const badge =
  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-micro font-medium';

/* ── Buttons ─────────────────────────────────────────── */
export const buttonPrimary =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-accent text-white px-4 py-2 text-body font-medium hover:brightness-110 active:scale-[0.98] transition-all duration-150';

export const buttonSecondary =
  'inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-transparent text-text-primary px-4 py-2 text-body font-medium hover:bg-hover active:scale-[0.98] transition-all duration-150';

export const buttonGhost =
  'inline-flex items-center justify-center gap-2 rounded-lg bg-transparent text-text-secondary hover:text-text-primary hover:bg-hover active:scale-[0.98] transition-all duration-150 px-2 py-1 text-body';

export const buttonIcon =
  'inline-flex items-center justify-center rounded-lg bg-transparent text-text-secondary hover:text-text-primary hover:bg-hover active:scale-[0.98] transition-all duration-150';

/* ── Input ─────────────────────────────────────────── */
export const input =
  'w-full rounded-lg border border-input bg-transparent px-4 py-2 text-body text-text-primary placeholder:text-text-disabled focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all duration-150';

/* ── Badge variants ─────────────────────────────────── */
export const badgeSuccess =
  badge + ' bg-successSoft text-success';

export const badgeWarning =
  badge + ' bg-warningSoft text-warning';

export const badgeDanger =
  badge + ' bg-dangerSoft text-danger';

export const badgeInfo =
  badge + ' bg-infoSoft text-info';
