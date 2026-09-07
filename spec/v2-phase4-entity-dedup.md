# Phase 4 leftover — entity-overlap dedup

Dedup stays cosine-first. Entity overlap is a *second* merge path for near
neighbors so rephrased facts about the same entity do not insert a second row.

## Rules

1. Embed the candidate and take the closest session neighbor (`repo.similar`, limit 1).
2. If cosine ≥ `0.92` (`DEDUP_THRESHOLD`): merge (bump importance +0.05, `access_count += 1`, skip insert). Unchanged.
3. Else if cosine ≥ `0.80` (`ENTITY_OVERLAP_THRESHOLD`) **and** the candidate shares a normalized entity with that neighbor: merge the same way.
4. Otherwise insert.

## Shared entity

Candidate tokens: `kv_triples[].entity`, `graph_triples[].subject`, `graph_triples[].object`, via `normalize_kv_token` / `normalize_graph_token` (strip + lower). Empty tokens ignored.

Neighbor tokens: alphanumeric words (length ≥ 2) from `memory.content`, lowercased, plus substring match when the entity is length ≥ 3 (`entity in content.lower()`).

No extra columns. No KV/graph store round-trip. Empty triples → cosine-only.

## Non-goals

- Changing the 0.92 hard threshold
- Org-wide (not session) dedup
- Rewriting loser content into the winner (consolidation already merges text)
