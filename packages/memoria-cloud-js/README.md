# Memoria Cloud Node.js SDK

Typed `fetch` client for the Memoria Memory API. Machine auth is a `mem_...` Bearer key.

```bash
npm install memoria-cloud-sdk
```

```ts
import { Memoria } from "memoria-cloud-sdk";

const client = new Memoria();
await client.recall({ q: "pytest" });
```

Defaults to `https://memoria-api-jw5g.onrender.com` when `MEMORY_API_URL` is unset.
