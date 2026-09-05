import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 20.0


def generate(prompt: str, system: str | None = None, timeout: float = _TIMEOUT_SECONDS) -> str | None:
    """Calls the local Ollama server for a single non-streaming completion.

    This is best-effort narrative enrichment, not a required data path: any failure (Ollama
    not running, model not pulled, request timeout) is caught and logged, returning None so
    callers fall back to their existing template-generated text instead of breaking the API
    response. Never used for numeric predictions — only for phrasing numbers already computed
    elsewhere. `timeout` defaults to the usual short one-liner budget; pass a larger value for
    longer, multi-paragraph generations (e.g. the cross-indicator dashboard summary).
    """
    if not settings.llm_narrative_enabled:
        return None

    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3},
    }
    if system:
        payload["system"] = system

    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/generate",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        text = response.json().get("response", "").strip()
        return text or None
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Ollama narrative generation failed, using template fallback: %s", exc)
        return None
