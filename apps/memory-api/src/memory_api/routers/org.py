from __future__ import annotations

from fastapi import APIRouter, Depends

from memory_api.auth import get_session_user
from memory_api.db.deps import get_identity_repository
from memory_api.db.identity import IdentityRepository
from memory_api.db.models import Org, User
from memory_api.schemas.auth import ExtractionPolicyOut, ExtractionPolicyUpdate

router = APIRouter()


def _normalize_instructions(instructions: str | None) -> str | None:
    if instructions is None:
        return None
    text = instructions.strip()
    return text or None


def _normalize_categories(categories: list[str]) -> list[str]:
    kept: list[str] = []
    for item in categories:
        label = item.strip()
        if label and label not in kept:
            kept.append(label)
    return kept


def _policy_out(org: Org) -> ExtractionPolicyOut:
    raw = org.categories if isinstance(org.categories, list) else []
    categories = [item for item in raw if isinstance(item, str) and item.strip()]
    return ExtractionPolicyOut(
        instructions=org.extraction_instructions,
        categories=categories,
    )


@router.get("/org/extraction-policy", response_model=ExtractionPolicyOut)
def get_extraction_policy(user: User = Depends(get_session_user)) -> ExtractionPolicyOut:
    return _policy_out(user.org)


@router.put("/org/extraction-policy", response_model=ExtractionPolicyOut)
def update_extraction_policy(
    body: ExtractionPolicyUpdate,
    user: User = Depends(get_session_user),
    identities: IdentityRepository = Depends(get_identity_repository),
) -> ExtractionPolicyOut:
    updated = identities.update_org_extraction_policy(
        user.org,
        instructions=_normalize_instructions(body.instructions),
        categories=_normalize_categories(body.categories),
    )
    return _policy_out(updated)
