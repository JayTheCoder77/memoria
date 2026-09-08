# Memoria Cloud Node.js SDK

Typed `fetch` client for the Memoria Memory API. Machine auth is a `mem_...` Bearer key.

```bash
npm install memoria-cloud-sdk
# or: bun add memoria-cloud-sdk
```

```ts
import { Memoria } from "memoria-cloud-sdk";

const client = new Memoria();
// q is a plain-language search question, not a filter expression
await client.recall({ q: "what test runner do we use?" });
```

Defaults to `https://memoria-api-jw5g.onrender.com` when `MEMORY_API_URL` is unset.

`session_id` is a label you choose. Required on `remember`. Omit it on `recall` to
search the whole org. Full field list: website `/docs/sdk`.
