# Dashboard

The dashboard is where the aesthetic earns its keep functionally — status
pills, stat grids, and mono type aren't just decoration here, they're the right
tool for showing live system state (key status, latency, memory counts).

## Layout
- **Left sidebar** — wordmark, nav items (`Memories`, `API Keys`, `Settings`),
  org switcher at top if multi-org is ever needed (not MVP), user avatar/menu
  at bottom
- **Top bar** — page title, status pill (`● Operational`) top-right, matches
  the nav-bar treatment from the landing page

## Overview / home
- **Stat grid** (reused component from landing page, same visual weight):
  - Total memories stored
  - p95 recall latency (last 24h)
  - Active API keys
  - Requests today
- **Recent activity panel** — styled as a terminal-log panel (dark, mono,
  timestamped lines), showing recent `remember`/`recall`/`forget` calls —
  this is a direct, functional reuse of the reference's terminal-panel motif,
  and it's genuinely useful here (not just aesthetic)

## API Keys page
- Table: key prefix (`mem_live_...`, masked after prefix), created date, last
  used, status pill (`● Active` accent green / `● Revoked` danger red)
- `Create new key` button — on creation, show the full key **once** in a
  terminal-styled panel with a `Copy` button and a clear "won't be shown again"
  warning (danger/warning color)
- Revoke action per row, confirmation modal before revoking

## Memories page
- List/table view: content preview (truncated), memory type as a small colored
  badge (episodic / semantic / procedural — three distinct muted colors, not
  full-saturation, so they don't compete with the single accent color used for
  status), session_id, created date, last accessed
- Filter bar: by memory type, by session_id, search by content
- Row click → detail panel (side sheet): full content, source_metadata (raw
  JSON in a mono code block), access_count, importance score

## Settings page
- Org name, org ID (mono, copyable)
- Connected Google account (email, avatar)
- Danger zone (delete org) — `--danger` colored section, clearly separated

## Component reuse notes
- Status pills, stat grid, terminal panel, and mono/sans type pairing are the
  same components defined in `01-design-language.md` — the dashboard should
  feel like the same product as the landing page and docs, not a different
  visual system bolted on
- Unlike the landing page, no dotted-grid decorative backgrounds here — this is
  a working surface, keep backgrounds flat and quiet
