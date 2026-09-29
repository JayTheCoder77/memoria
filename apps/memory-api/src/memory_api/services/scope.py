from __future__ import annotations


def normalize_scope_id(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > 128:
        raise ValueError("must be at most 128 characters")
    return text


def stored_scope_id(value: str | None) -> str:
    return value or ""


def exposed_scope_id(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return value


def scope_matches(
    row_user: str | None,
    row_agent: str | None,
    *,
    user_id: str | None,
    agent_id: str | None,
) -> bool:
    if user_id is not None and row_user != user_id:
        return False
    if agent_id is not None and row_agent != agent_id:
        return False
    return True
