# OAuth / Login Page

Minimal by necessity — this page has one job (get the user through Google OAuth
into the dashboard) so the aesthetic shows up in restrained, quiet details
rather than dense content, closer to how rig.ai treats its waitlist panel than
its content-heavy sections.

## Layout
- Centered card (`--bg-raised`, 1px `--border-subtle` border) on the
  `--bg-base` background, subtle dotted-grid texture behind it (same treatment
  as the landing page hero/final-CTA, low opacity so it doesn't compete with
  the card)
- Wordmark above the card, small and centered
- Card contents:
  - Eyebrow (mono, small): `Sign in`
  - Heading: short, e.g. "Access your memory dashboard"
  - Single primary button: **Sign in with Google** (Google's standard branded
    button, not reskinned — don't fight Google's own brand guidelines here)
  - Small mono microcopy below the button, status-pill style: `● Secure via
    Google OAuth` (reuses the status-pill motif, signals trust without heavy
    copy)
- Footer of the card (small, muted): link to Terms/Privacy

## States
- **Loading (during OAuth redirect):** simple centered spinner or a short mono
  status line (`> Authenticating...`) — a light nod to the terminal-boot motif
  from the reference, but brief, not a full ASCII sequence
- **Error (OAuth failed/denied):** inline message inside the same card,
  `--danger` colored small text below the button, button remains to retry —
  never redirect to a separate error page for this
- **Already signed in:** redirect straight to dashboard, no intermediate screen

## What NOT to do here
- No terminal panel, no ANSI bars, no numbered sections — this page should take
  under 3 seconds to parse. Save the fuller aesthetic for landing/docs/dashboard.
