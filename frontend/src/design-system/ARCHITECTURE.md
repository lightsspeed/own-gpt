# Frontend Architecture Rule

> A page may compose components. A component may compose primitives. A primitive may consume design tokens. Only the design system may know about raw colors, spacing, typography, or animation values.

## Enforcement

```
npm run lint
```

Runs `oxlint` (static analysis) + `scripts/check-design-tokens.mjs` (arbitrary value ban).

## Allowed

```tsx
<Surface variant="surface">
  <Stack gap="lg">
    <Heading>Knowledge Base</Heading>
    <Button variant="primary">Upload</Button>
  </Stack>
</Surface>
```

## Forbidden

```tsx
<div className="rounded-xl border border-zinc-800 bg-zinc-900 p-6 shadow-lg">
  <div className="flex flex-col gap-4">
    <h2 className="text-[18px] font-semibold">Knowledge Base</h2>
    <button className="bg-[#2563eb] rounded-[8px] px-[16px]">Upload</button>
  </div>
</div>
```

## Token hierarchy

```
Theme
  → Semantic Tokens (semantic.ts)
    → Components (layout/ + primitives/)
      → Screens / Pages
```

Components **never** reference `colors.raw.blue` directly — they use `semantic.accent`.

## Checking compliance

```bash
node scripts/check-design-tokens.mjs
```

Fails on: `rounded-[...]`, `p-[...]`, `m-[...]`, `gap-[...]`, `text-[...]`, `shadow-[...]`, `inset-[...]`, `space-[xy]-[...]` in any file outside `components/ui/`.
