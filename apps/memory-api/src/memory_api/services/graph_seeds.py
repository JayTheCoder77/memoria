from __future__ import annotations

import re

from memory_api.stores.graph import normalize_graph_token

_TOKEN = re.compile(r"[a-z0-9]{3,}")
_CAP = 12

_LIVES_IN = re.compile(r"\blives in\s+(\w+)", re.IGNORECASE)
_PREFER = re.compile(r"\bprefer\s+(\w+)", re.IGNORECASE)
_WORKS_ON = re.compile(r"\bworks on\s+(\w+)", re.IGNORECASE)


def _add_seed(results: list[str], seen: set[str], entity: str) -> None:
    if len(results) >= _CAP:
        return
    normalized = normalize_graph_token(entity)
    if not normalized or normalized in seen:
        return
    seen.add(normalized)
    results.append(normalized)


def _rules_seeds(query: str) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()

    for pattern in (_LIVES_IN, _PREFER, _WORKS_ON):
        for match in pattern.finditer(query):
            _add_seed(results, seen, match.group(1))

    for token in _TOKEN.findall(query.lower()):
        _add_seed(results, seen, token)
        if len(results) >= _CAP:
            break

    return results


def derive_graph_seeds(query: str) -> list[str]:
    return _rules_seeds(query)
