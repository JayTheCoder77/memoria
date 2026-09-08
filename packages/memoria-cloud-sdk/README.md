# Memoria Cloud Python SDK

Typed HTTP client for the Memoria Memory API. Machine auth is a `mem_...` Bearer key.

```bash
pip install memoria-cloud-sdk
```

```python
from memoria_cloud import Memoria

client = Memoria()  # MEMORY_API_URL / MEMORY_API_KEY
client.remember(content="We prefer pytest", session_id="s1")
hits = client.recall(q="pytest")
```

Defaults to `https://memoria-api-jw5g.onrender.com` when `MEMORY_API_URL` is unset.
