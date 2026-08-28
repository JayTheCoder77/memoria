# Docs Page

Docs are content-dense, so the aesthetic gets toned down from the landing page —
motifs are used for wayfinding and code, not decoration. No dotted-grid
backgrounds or terminal panels-as-decoration here; the terminal styling is
reserved for actual code blocks.

## Layout
- **Left sidebar** — mono-font nav tree (matches rig.ai's mono link style),
  collapsible sections, active item marked with the accent color + left border
  tick, not a filled background (keeps it quiet against dense content)
- **Top bar** — search (`⌘K`), version/status pill (`v0 · MVP`), link to
  dashboard/sign-in
- **Main content column** — sans-serif body text, generous line-height for
  readability, max content width (~720px) so lines don't run too long
- **Right-side "on this page" mini-nav** (optional, if pages get long) — small
  mono links to headings

## Components specific to docs

**Code blocks**
- Styled as a compact terminal panel: dark background (`--bg-terminal`), thin
  border, mono text, subtle top bar with a language label (e.g. `python`,
  `bash`) and a `Copy` button (top-right, icon + text)
- Syntax highlighting uses the accent green sparingly (strings/keywords), avoid
  a full rainbow theme — keep it close to the reference's restrained palette

**Callouts**
- Left-border colored block (accent green for tips, warning amber for cautions,
  danger red for breaking-change notices), mono label (`NOTE`, `WARNING`) +
  sans body text

**API reference blocks**
- Method + endpoint in mono with a colored HTTP-verb badge (`GET` accent,
  `POST` a secondary tone, `DELETE` danger) — matches the status-pill pattern
  from the design language spec
- Parameter tables: mono for parameter names/types, sans for descriptions

**MCP quickstart block**
- A terminal-panel component (same as landing page's, reused) showing the exact
  MCP config snippet a developer pastes into their harness — this is one of the
  highest-value pieces of the whole docs site, give it visual prominence on the
  quickstart page specifically

## Pages to design first (MVP)
1. Quickstart (MCP config + first `remember`/`recall` call)
2. Authentication (API keys, Google OAuth for dashboard access)
3. API reference (`/memories`, `/auth/google`, key management endpoints)
4. Memory types (episodic/semantic/procedural explained)
5. Self-host vs hosted (if applicable at MVP)
