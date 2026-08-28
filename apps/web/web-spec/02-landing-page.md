# Landing Page

Applies the motifs from `01-design-language.md` to the marketing site, adapted
from rig.ai's "local AI coding agent" framing to our "memory infrastructure for
agent harnesses" positioning.

## Structure (top to bottom)

**1. Nav**
- Wordmark left, mono-style links right (`Docs`, `Pricing`, `Sign in`), primary
  CTA button (`Get API Key` / `Start Building`)
- Status pill in nav or just below it: `● Operational` — subtle, not the focus

**2. Hero**
- Eyebrow (mono, uppercase): e.g. `MEMORY INFRASTRUCTURE FOR AI AGENTS`
- Headline (large sans): problem-forward, short — e.g. "Your agent forgets
  everything. We fixed that."
- Subhead: one line on speed + persistence
- Two CTAs: primary (`Get API Key`), secondary (`Read the docs`)
- Optional scrolling ticker beneath: short tags separated by `·` — e.g.
  `Sub-100ms recall · Stateless MCP · Multi-tenant · Episodic · Semantic · Procedural`
- Subtle dotted-grid background texture behind the hero only

**3. Problem section**
- Eyebrow: `The problem`
- Numbered cards (001-00N, mono numerals) — each: short bold title + 1-2 line
  body. Adapt rig.ai's "monitoring/telemetry" cards into our domain, e.g.:
  - `001` — "Every session starts from zero" (context lost between runs)
  - `002` — "Context windows blow up" (re-reading the same files every time)
  - `003` — "Fixes get forgotten" (same bug solved twice)

**4. Solution section**
- Eyebrow: `Introducing [product name]`
- Large heading + short body
- **Terminal panel visual** (reused component) showing a live-feeling sequence:
  connect → `remember()` call → `recall()` call → response, styled exactly like
  rig.ai's terminal mockup (dark panel, mono text, checkmarks, timing in ms)
- Below/beside it: a simple flow diagram (harness → MCP → API → cache/DB),
  using the same visual weight as rig.ai's "your machine / cloud" diagram, but
  representing our actual architecture instead of a local-vs-cloud split

**5. Speed section (stat grid)**
- 3-4 column stat grid, mono numbers, e.g.:
  - `<100ms` — p95 cached recall latency
  - `Stateless` — MCP server, horizontally scalable
  - `3` — memory types (episodic / semantic / procedural)
  - `100%` — tenant-isolated by default
- Optional ANSI-style comparison bar: "cached recall" vs "uncached vector search"
  latency, same visual pattern as rig.ai's model-size/latency bars

**6. Capabilities grid**
- `[01]`–`[06]` numbered items, 2-3 column grid, each: mono number, bold short
  title, 1-2 line description. Pull from actual features: hybrid retrieval,
  dedup/consolidation, multi-tenant isolation, MCP-native, async extraction,
  Google OAuth + API key auth.

**7. Integrations strip**
- Row of harness logos/badges: Claude Code, Cursor, LangGraph, "any MCP client" —
  this replaces rig.ai's "engineered intelligence" grid, serves the same
  credibility-signal purpose

**8. FAQ**
- Numbered accordion (`01`–`0N`), mono numerals, plain sans body text on expand —
  same pattern as rig.ai, content specific to our product (pricing, self-host vs
  hosted, supported harnesses, data retention, auth model)

**9. Final CTA**
- Large centered heading, subtle background texture (dotted grid or soft glow,
  not a heavy graphic), single primary CTA, small reassurance microcopy
  (`No credit card required` — keep this, it works regardless of positioning)

**10. Footer**
- Wordmark + one-line tagline, link columns (`Product`, `Docs`, `Company`,
  `Legal`), status pill (`● All systems operational`), copyright line
