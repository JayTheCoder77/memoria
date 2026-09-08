# Memoria Cloud Python SDK

Typed HTTP client for the Memoria Memory API. Machine auth is a `mem_...` Bearer key.

```bash
pip install memoria-cloud-sdk
```

```python
from memoria_cloud import Memoria

client = Memoria()  # MEMORY_API_URL / MEMORY_API_KEY
client.remember(content="We prefer pytest", session_id="s1")
# q is a plain-language search question, not a filter expression
hits = client.recall(q="what test runner do we use?")
```

Defaults to `https://memoria-api-jw5g.onrender.com` when `MEMORY_API_URL` is unset.

`session_id` is a label you choose (chat, ticket, project). Required on `remember`.
Omit it on `recall` to search the whole org. `memory_type` is `semantic` (default),
`episodic`, or `procedural`. Full field list: website `/docs/sdk`.
