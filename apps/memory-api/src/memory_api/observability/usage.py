from __future__ import annotations

from uuid import UUID

from memory_api.db.models import LlmUsage
from memory_api.db.session import SessionLocal
from memory_api.observability.metrics import record_llm_tokens


def record_llm_usage(
    *,
    org_id: UUID,
    user_id: str | None,
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float,
    trace_id: str | None,
) -> None:
    session = SessionLocal()
    try:
        session.add(
            LlmUsage(
                org_id=org_id,
                user_id=user_id,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
                trace_id=trace_id,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    record_llm_tokens(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
