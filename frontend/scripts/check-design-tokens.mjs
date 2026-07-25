/**
 * Design Token Lint Script
 *
 * Forbids arbitrary Tailwind values (rounded-[17px], p-[22px], text-[15px], etc.)
 * in src/ files. All values must come from design-system tokens.
 *
 * Usage: node scripts/check-design-tokens.mjs
 * Exit code: 0 = clean, 1 = violations found
 */

import { readFileSync, readdirSync, statSync } from 'fs';
import { join, relative, extname, resolve } from 'path';

const ROOT = resolve(import.meta.dirname, '..');
const SRC = join(ROOT, 'src');

/* ── Patterns with arbitrary values ── */
const FORBIDDEN_PATTERNS = [
  // Forbid arbitrary values in spacing, typography, radius, shadows
  { pattern: /(?:^|[^-\w])rounded-\[[^\]]+\]/g,      hint: 'Use rounded-{xs|sm|md|lg|xl|full} from radius.ts' },
  { pattern: /(?:^|[^-\w])p-\[[^\]]+\]/g,            hint: 'Use p-{1|2|3|4|5|6|8|10|12|16} from spacing.ts' },
  { pattern: /(?:^|[^-\w])px-\[[^\]]+\]/g,           hint: 'Use px-{n} from spacing.ts' },
  { pattern: /(?:^|[^-\w])py-\[[^\]]+\]/g,           hint: 'Use py-{n} from spacing.ts' },
  { pattern: /(?:^|[^-\w])m-\[[^\]]+\]/g,            hint: 'Use m-{n} from spacing.ts' },
  { pattern: /(?:^|[^-\w])mx-\[[^\]]+\]/g,           hint: 'Use mx-{n} from spacing.ts' },
  { pattern: /(?:^|[^-\w])my-\[[^\]]+\]/g,           hint: 'Use my-{n} from spacing.ts' },
  { pattern: /(?:^|[^-\w])gap-\[[^\]]+\]/g,          hint: 'Use gap-{1|2|3|4|5|6|8|10|12|16} from spacing.ts' },
  { pattern: /(?:^|[^-\w])text-\[[^\]]+\]/g,         hint: 'Use text-{display|h1|h2|h3|title|body|small|caption|micro} from typography.ts' },
  { pattern: /(?:^|[^-\w])shadow-\[[^\]]+\]/g,       hint: 'Use shadow-{sm|md|lg|glow|inner} from shadows.ts' },
  { pattern: /(?:^|[^-\w])inset-\[[^\]]+\]/g,        hint: 'Use spacing tokens' },
  { pattern: /(?:^|[^-\w])space-[xy]-\[[^\]]+\]/g,   hint: 'Use Stack/Inline with gap prop' },
];

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (entry === 'node_modules') continue;
      yield* walk(full);
    } else {
      yield full;
    }
  }
}

let exitCode = 0;

for (const file of walk(SRC)) {
  const ext = extname(file);
  if (ext !== '.tsx' && ext !== '.ts') continue;

  /* Skip shadcn-generated UI components */
  if (file.includes('components\\ui\\') || file.includes('components/ui/')) continue;

  const content = readFileSync(file, 'utf-8');
  const rel = relative(ROOT, file);

  for (const { pattern, hint } of FORBIDDEN_PATTERNS) {
    let match;
    pattern.lastIndex = 0;
    while ((match = pattern.exec(content)) !== null) {
      const line = content.substring(0, match.index).split('\n').length;
      console.error(`  ${rel}:${line}  ${match[0]}  — ${hint}`);
      exitCode = 1;
    }
  }
}

if (exitCode === 0) {
  console.log('✅ No arbitrary Tailwind values — all design tokens respected.');
} else {
  console.error('\n❌ Replace arbitrary values with design system tokens.');
}

process.exit(exitCode);
