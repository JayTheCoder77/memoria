# Frontend Folder Structure (apps/web)

This complements `spec/02-folder-structure.md`, which covers monorepo/routing
layout. This file is scoped to how `apps/web`'s components and styles are
organized internally — separated by concern so the design system stays
reusable and page code stays thin.

## Separation of concerns

| Layer | Contains | Knows about business logic? | Knows about design tokens? |
|---|---|---|---|
| `styles/tokens` | Colors, type scale, spacing — from `spec/design/01-design-language.md` | No | Is the source of them |
| `components/ui` | Primitives: Button, Badge, StatusPill, StatGrid, TerminalPanel, Card | No | Yes, consumes tokens only |
| `components/layout` | Sidebar, Navbar, Footer, PageShell | No | Yes, via ui primitives |
| `components/features` | MemoriesTable, ApiKeysList, ActivityLog — composed, page-specific | Yes — data fetching, state | Indirectly, via ui/layout |
| `app/*` (routes) | Page composition only — assembles feature components | Minimal — delegates to features | No — never hardcodes a color/spacing value |

Rule of thumb: if a component would make sense in a completely different product
(a button, a badge, a stat grid), it belongs in `ui/`. If it's specific to what
*this* product does (a table of memories, an API key list), it belongs in
`features/`. Route files should mostly just arrange feature components on a page.

## Structure

```
apps/web/
├── app/
│   ├── (marketing)/
│   │   └── page.tsx                # landing page — composes marketing/* features
│   ├── (auth)/
│   │   └── login/
│   │       └── page.tsx            # composes features/auth/LoginCard
│   ├── dashboard/
│   │   ├── page.tsx                # overview — composes features/dashboard/*
│   │   ├── memories/page.tsx
│   │   ├── keys/page.tsx
│   │   └── settings/page.tsx
│   └── docs/
│       └── [...slug]/page.tsx
│
├── components/
│   ├── ui/                         # dumb, reusable, no business logic
│   │   ├── Button.tsx
│   │   ├── Badge.tsx
│   │   ├── StatusPill.tsx
│   │   ├── StatGrid.tsx
│   │   ├── TerminalPanel.tsx
│   │   ├── AnsiBar.tsx
│   │   ├── Card.tsx
│   │   └── CodeBlock.tsx
│   │
│   ├── layout/                     # structural, no business logic
│   │   ├── Sidebar.tsx
│   │   ├── Navbar.tsx
│   │   ├── Footer.tsx
│   │   └── PageShell.tsx
│   │
│   └── features/                   # product-specific, composed from ui + layout
│       ├── marketing/
│       │   ├── Hero.tsx
│       │   ├── ProblemSection.tsx
│       │   ├── CapabilitiesGrid.tsx
│       │   └── Faq.tsx
│       ├── auth/
│       │   └── LoginCard.tsx
│       └── dashboard/
│           ├── MemoriesTable.tsx
│           ├── ApiKeysList.tsx
│           └── ActivityLog.tsx
│
├── styles/
│   ├── tokens.css                  # design tokens — single source of truth,
│   │                                # mirrors spec/design/01-design-language.md
│   └── globals.css
│
├── lib/
│   ├── auth.ts                     # Auth.js Google provider config
│   └── api-client.ts               # typed client for Memory API
│
└── package.json
```

## Why this matters here specifically
- `01-design-language.md` defines the tokens; `tokens.css` is the *only* place
  they're declared in code — no component should hardcode a hex value or a
  spacing number
- `ui/` components (StatusPill, StatGrid, TerminalPanel, AnsiBar) are the same
  components reused across the landing page, docs, and dashboard per
  `01-design-language.md`'s "core visual motifs" — building them once in `ui/`
  is what makes that reuse actually happen instead of getting redrawn per page
- Keeping `features/` separate from `ui/` means a change to, say, the
  `MemoriesTable`'s data logic can't accidentally break the `Badge` component
  used on three other pages
