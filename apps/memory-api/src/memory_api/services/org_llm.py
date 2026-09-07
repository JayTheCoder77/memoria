from __future__ import annotations

import logging

from memory_api.db.models import Org
from memory_api.services.llm_json import LlmProvider

logger = logging.getLogger(__name__)


def org_chat_providers(org: Org | None, *, timeout: float) -> list[LlmProvider]:
    from memory_api.config import settings
    from memory_api.services.secrets import decrypt_secret

    providers: list[LlmProvider] = []
    if org is None:
        return providers
    if org.openrouter_key_ciphertext:
        try:
            key = decrypt_secret(org.openrouter_key_ciphertext)
        except Exception:
            logger.exception("Failed to decrypt OpenRouter key")
        else:
            providers.append(
                LlmProvider(
                    api_key=key,
                    base_url=settings.llm_base_url,
                    model=org.openrouter_model or settings.llm_model,
                    timeout=timeout,
                    extra_headers={
                        "HTTP-Referer": settings.openrouter_http_referer,
                        "X-Title": settings.openrouter_app_title,
                    },
                )
            )
    if org.groq_key_ciphertext:
        try:
            key = decrypt_secret(org.groq_key_ciphertext)
        except Exception:
            logger.exception("Failed to decrypt Groq key")
        else:
            providers.append(
                LlmProvider(
                    api_key=key,
                    base_url=settings.groq_base_url,
                    model=settings.groq_model,
                    timeout=timeout,
                )
            )
    return providers
