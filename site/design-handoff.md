# Design handoff — ASX research site (`docs/index.html`)

Hand this file (plus `docs/index.html` itself) to any future Claude session or
collaborator working on the site. It records the design system, the rules the
page was built under, and how to extend it without breaking either.

## What this page is

A single-file, dependency-free research dossier for the ASX announcement alpha
study, aimed at a LinkedIn/quant/hiring audience. Its job: demonstrate rigor.
The honest-nulls framing is the product — never redesign it into a pitch.

- One self-contained HTML file: inline CSS, inline JS, hand-built SVG charts,
  system fonts only. No CDNs, no build step, no external requests (must work
  under a strict CSP and on GitHub Pages).
- Also published as a Claude Artifact (same content minus the outer
  `<html>/<head>/<body>` skeleton): the artifact-format source of truth is the
  **committed** `site/src/research-src.html`; the local `scripts/_wrap_site.py`
  wraps it into `docs/index.html`.
- Artifact URL (preview): https://claude.ai/code/artifact/b0833637-f29d-4bac-a75d-43d3820fc9a0
  (favicon 📉 — keep it stable across updates).

## Voice

- Findings stated plainly, caveats stated proudly. "REFUTED" is a result, not
  an apology. Never hype: no "game-changing", no rocket emoji.
- Numbers always carry their honesty markers (n, t, "in-sample",
  "exploratory"). If a claim's t-stat is optimistic, the page says so.
- Section eyebrows are numbered `01 · the interrogation` … they encode the
  study's actual narrative sequence, not decoration.

## Design tokens

Defined as CSS custom properties on `:root`, redefined under
`@media (prefers-color-scheme: dark)`, then AGAIN under
`:root[data-theme="light"]` and `:root[data-theme="dark"]` (the artifact
viewer's theme toggle stamps `data-theme` and must win in both directions).
Never style a component with raw hex — always through tokens.

| Token | Light | Dark | Role |
|---|---|---|---|
| `--page` | `#f9f9f7` | `#0d0d0d` | page ground |
| `--surface` | `#fcfcfb` | `#1a1a19` | cards, chart surface |
| `--ink` | `#0b0b0b` | `#ffffff` | primary text |
| `--ink-2` | `#52514e` | `#c3c2b7` | secondary text |
| `--muted` | `#898781` | `#898781` | axis labels, captions |
| `--grid` | `#e1e0d9` | `#2c2c2a` | hairline gridlines |
| `--baseline` | `#c3c2b7` | `#383835` | zero lines / axes |
| `--ring` | `rgba(11,11,11,.10)` | `rgba(255,255,255,.10)` | card borders |
| `--pos` / `--s1` | `#2a78d6` | `#3987e5` | series blue; positive pole |
| `--neg` | `#e34948` | `#e66767` | series red; negative pole |
| `--s2` / `--seq-mid` | `#1baf7a` | `#199e70` | series aqua (2nd series / middle stack segment) |
| `--s-unflag` | `#eb6834` | `#d95926` | orange: "not flagged" category |
| `--good`/`--warn`/`--crit` | `#0ca30c`/`#fab219`/`#d03b3b` | same | STATUS ONLY — verdict chips, never a data series |

Palette provenance: the validated reference palette from the dataviz method
(colorblind-safe ordering; the 3-slot combos used here were re-validated with
its `validate_palette.js`, both modes). If you add a series color, validate
before shipping; do not invent hues. Dark mode is a *selected* palette, not an
inversion — add dark values deliberately.

## Type

- Everything is system sans: `system-ui, -apple-system, "Segoe UI", sans-serif`.
- ALL numbers, verdict chips, eyebrows, axis text, stat values, tooltips:
  `ui-monospace, "Cascadia Code", Consolas, Menlo, monospace` (`.mono` or the
  `svg text` rule). The mono-for-data / sans-for-prose split IS the visual
  identity — do not soften it.
- Scale: h1 `clamp(30px, 5.4vw, 46px)/750`; h2 27px/700; h3 18px/650; body
  16px/1.65; captions 13px; axis 11px. Eyebrows 12px mono, `0.14em`
  letter-spacing, uppercase.
- `text-wrap: balance` on h1/h2; `font-variant-numeric: tabular-nums` wherever
  digits align (tables, axes).

## Layout

- `.wrap` = 900px max; `.prose` = 720px max (reading measure). Charts sit in
  `figure.viz` cards (surface bg, 1px `--ring` border, 12px radius) that span
  the full 900px.
- Every chart lives inside `<div class="chart-scroll">` (`overflow-x: auto`) —
  the page body never scrolls horizontally.
- Sections: eyebrow → h2 → prose → figure(s). Grids of cards
  (`.verdicts`, `.lessons`): `repeat(auto-fit, minmax(255px, 1fr))`, 14px gap.
- Spacing comes from flex/grid `gap`, not stacked margins.

## Chart conventions (all hand-built SVG, no libraries)

- ViewBox width 860, `width="100%"`. Left margin ~46–52 for y labels.
- Marks: bars `rx:3-4` with a 2px surface gap between adjacent/stacked
  segments; lines 2px; dots r 4–5 with a 2px `--surface` ring.
- Grid: 1px `--grid`; the zero line uses `--baseline`. Axis text 11px `--muted`.
- Direct value labels on bars/points: 11–12px, weight 700, `--ink` (text NEVER
  wears the series color).
- A `.legend` row above any chart with ≥2 series; none for single-series.
- Color rules: polarity (under/over) = `--neg`/`--pos` diverging. Series
  identity = `--s1` then `--s2` in fixed order. Status hues never encode data.
- Every mark is hoverable: shared `#tip` fixed-position tooltip (ink bg, page
  ink text, mono). Helpers in the IIFE: `el()`, `hover(node, html)`,
  `showTip/hideTip`. Line charts get a nearest-point crosshair (see chart 6).
- Charts with dense data include a `<details class="tbl">` table fallback, and
  each `<svg>` carries a one-sentence `aria-label`.
- Data is embedded inline in each chart's IIFE — real numbers from the study
  only. NEVER invent or extrapolate a data point for visual effect. Sources:
  BUILD_LOG.md entries + the gitignored `scripts/_*.py` outputs.

## Page inventory (order matters — it's the argument)

1. Hero: thesis headline, dek, stat band (6 tiles), pipeline strip.
2. `01 the interrogation` — decay line chart (8 robustness stages).
3. `02 the survivor` — 31-event diverging bars + sector dots; CYL case-study
   line chart (CYL vs gold peers, sale/result markers).
4. `03 the graveyard` — 6 verdict cards (chips: REFUTED/INCONCLUSIVE/NULL);
   PEAD quintiles; dividend actions; dip-buy scatter (50 points + control
   reference line).
5. `04 market plumbing` — flag-divergence bars (flagged blue vs unflagged
   orange; the $1M+ sales row is the bolded protagonist).
6. `05 the LLM under the microscope` — cross-doc stacked bars; eval-progression
   small multiples (earnings v1→v7, director trades v2→v3); three lesson cards.
7. `06 what would make this real` — forward-test framing + the caveats box
   ("Read the fine print — it's the point"). Never delete or bury this box.
8. Footer: pipeline one-liner, repo link, not-investment-advice.

## Updating workflow

1. Edit `site/src/research-src.html` (artifact format: starts at `<title>`, no
   doctype/html/head/body) — this is the single source of truth, committed.
2. Republish the Artifact from that file (same URL, new `label`).
3. Run `scripts/_wrap_site.py` to regenerate `docs/index.html`, commit both.
4. GitHub Pages serves from `main` `/docs` → site URL is
   `https://taylor-hobbs.github.io/asx/` once Pages is enabled.
5. When numbers change (new analysis runs), update BOTH the chart data arrays
   and any prose that quotes the number, and re-check the table fallbacks —
   they duplicate the data on purpose.

## Do / don't

- DO add new findings as new figures following the existing chart recipes.
- DO keep verdict chips honest — if a result is exploratory, say EXPLORATORY.
- DON'T add webfonts, CDN scripts, chart libraries, or external images.
- DON'T use emoji in body copy; the favicon is the only emoji.
- DON'T repaint series when a filter/edit changes counts (color follows entity).
- DON'T center body text, add gradient heroes, or round every corner further —
  the restraint is the brand.
