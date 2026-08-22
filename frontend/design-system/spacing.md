# Spacing

## Base Unit

4px grid. All spacing values are multiples of 4.

| Token | Pixels | Usage                     |
|-------|--------|---------------------------|
| 1     | 4px    | Compact inner padding     |
| 1.5   | 6px    | Tight gaps                |
| 2     | 8px    | Element gaps              |
| 2.5   | 10px   | Icon-to-text gaps         |
| 3     | 12px   | Section inner padding     |
| 3.5   | 14px   | Horizontal padding        |
| 4     | 16px   | Card padding, gaps        |
| 5     | 20px   | Section spacing           |
| 6     | 24px   | Page margins              |
| 8     | 32px   | Large section spacing     |
| 10    | 40px   | Page section gaps         |
| 12    | 48px   | Major layout separation   |

## Sidebar

- Horizontal padding: `px-3` (12px) or `px-4` (16px)
- Item padding: `py-2` (8px) vertical, `px-3` (12px) horizontal
- Group spacing: `space-y-1` (4px) between items
- Section header: `py-1.5` (6px) vertical padding

## Cards

- Card padding: `p-5` (20px)
- Card gap: `space-y-3` (12px)
- Inner element gap: `gap-3` (12px)

## Rules

- Never use odd pixel values.
- Never use margin to simulate padding.
- Use Tailwind spacing utilities (`p-*`, `m-*`, `gap-*`, `space-y-*`).
