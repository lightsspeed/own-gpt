# Colors

## Surface Hierarchy

| Token      | HSL                 | Usage                         |
|------------|---------------------|-------------------------------|
| `--canvas` | `0 0% 0%`          | Page background               |
| `--surface`| `0 0% 2%`          | Sidebar, elevated containers  |
| `--elevated`| `0 0% 6%`         | Cards, dropdowns, popovers    |
| `--overlay` | `0 0% 2%`         | Modal backdrops               |
| `--hover`   | `0 0% 10%`        | Hover state backgrounds       |

## Text Hierarchy

| Token                | Opacity/Value        | Usage                    |
|----------------------|----------------------|--------------------------|
| `--text-primary`     | `210 60% 97%`       | Primary text (near-white)|
| `--text-secondary`   | `215 25% 58%`       | Secondary text           |
| `--text-disabled`    | `215 25% 58% / 0.5` | Disabled text            |

## Functional

| Token         | HSL                | Usage                        |
|---------------|--------------------|------------------------------|
| `--primary`   | `221 90% 55%`     | Accent, links, active states |
| `--success`   | `152 60% 40%`     | Success, healthy, up         |
| `--warning`   | `38 90% 50%`      | Warning, degraded, running   |
| `--danger`    | `0 68% 50%`       | Error, down, failed          |
| `--info`      | `270 60% 50%`     | Info, neutral status         |

## Opacity Tokens

Use opacity modifiers for text hierarchy:

- Foreground (primary text): `text-foreground`
- Secondary text: `text-muted-foreground`
- Tertiary text: `text-muted-foreground/60`
- Quaternary text: `text-muted-foreground/40`
- Faint text: `text-muted-foreground/25`

## Borders

- Default: `border-border`
- Subtle: `border-border/60`
- Very subtle: `border-border/40`
- Faint: `border-border/30`
