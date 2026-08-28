# Design Language

Aesthetic inspiration: [rig.ai](https://rig.ai/?ref=minimal.gallery) — a dark,
terminal/hacker-developer aesthetic (monospace labels, ANSI-style bar charts,
numbered sections, status pills with a live dot, terminal panel mockups, dotted
grid backgrounds). We're taking the **visual language**, not the copy or the
"local AI" positioning — our product is a hosted memory layer, not a local-only
tool, so CTAs/status language are adapted accordingly (see per-page specs).

**Note:** additional screenshots will be added under `/screenshots` in the repo.
Treat the tokens below as a starting point — once screenshots land, cross-check
exact colors/spacing against them and adjust this file before implementation.

## Color tokens
Dark-first, single accent color, high contrast. Exact hex to be confirmed against
screenshots — placeholders below follow the terminal-green convention rig.ai uses.

| Token | Value (placeholder) | Usage |
|---|---|---|
| `--bg-base` | `#0A0A0B` | page background |
| `--bg-raised` | `#121214` | cards, panels |
| `--bg-terminal` | `#000000` | terminal/code panel background |
| `--border-subtle` | `#232326` | 1px hairline borders on cards/panels |
| `--text-primary` | `#F2F2F0` | headings, primary body |
| `--text-secondary` | `#8B8B90` | subheads, captions, muted labels |
| `--accent` | `#00E08F` | status dots, links, chart bars, active states |
| `--accent-dim` | `#00E08F` at 15% opacity | accent backgrounds, badge fills |
| `--danger` | `#FF5C5C` | error states, revoked keys |
| `--warning` | `#FFB020` | warning callouts |

## Typography
Two-font system, matching the reference's mix of clean headline type and
monospace technical detail.

- **Sans (headings, body):** Inter or Geist — used for H1-H3, paragraph copy, nav
- **Mono (labels, stats, code, badges):** JetBrains Mono or IBM Plex Mono — used
  for eyebrow labels, numbered section markers (`01`, `02`), stat numbers, API
  keys, code blocks, status pills, terminal panels

Scale: keep it restrained — one very large hero size (56-72px), one section
heading size (32-40px), one card heading size (18-20px), one body size (15-16px),
one small/mono label size (12-13px, often uppercase + letter-spacing).

## Core visual motifs (reusable across pages)

1. **Eyebrow + numbered labels** — small mono uppercase text above headings,
   often with a leading number (`[ 01 ]`) or a category tag (`The problem`,
   `Our Approach`). Use consistently as a section-identity pattern.
2. **Status pill with live dot** — a small pill badge, colored dot (accent green
   = healthy/active, red = error/revoked) + mono text (`Operational`, `Active`,
   `Revoked`). Used in nav bars, dashboard headers, key lists.
3. **ANSI-style bar** — inline text/CSS bar built from filled/empty block
   characters or a styled `<div>` bar, used for quick comparative stats (e.g.
   "our recall latency vs. naive vector search").
4. **Terminal panel** — a dark, bordered panel styled like a terminal window
   (subtle top bar with dots, mono content, blinking cursor optional) used to
   show live `remember()`/`recall()` calls or a boot-style sequence.
5. **Stat grid** — 3-4 column grid of large mono numbers with a small label
   underneath (e.g. `<100ms` / `p95 recall latency`).
6. **Numbered capability list** — `[01]`–`[0N]` items in a grid, each with a
   short mono number, bold short title, and one-line description.
7. **Dotted/grid background texture** — very subtle, low-opacity dot or line
   grid behind hero/CTA sections, never behind dense text content (readability).
8. **Scrolling ticker** (optional, hero only) — a slow horizontal marquee of
   short feature tags separated by `·`, used sparingly since it can feel busy on
   a docs-heavy product.

## What we deliberately do NOT carry over
- The "us vs. cloud/big AI" adversarial framing — not our positioning
- Fully offline/local claims — we're a hosted service, so status language should
  say "Operational" / "Connected", not "100% offline"
- Terminal ASCII art as a primary hero visual — fine as a supporting element on
  the landing page, too heavy for docs/dashboard/oauth surfaces
