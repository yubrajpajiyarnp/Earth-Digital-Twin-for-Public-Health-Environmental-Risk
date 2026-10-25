import hashlib
import logging
import threading
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 20.0
_DEFAULT_MAX_TOKENS = 300

# Every narrative call in this app is a pure function of the exact numbers embedded in its
# prompt (see narrative.py/dashboard_summary.py docstrings) — so the same prompt+system pair
# always deserves the same answer, and re-running the model on it is pure waste. The
# frontend polls several of these endpoints on a timer and mounts more than one component
# that requests the same figures (e.g. ConditionsBar and AqiPanel both read AQI risk), so
# without this cache a local 7B-parameter model would be re-generating identical text every
# few minutes indefinitely — the main source of sustained CPU/GPU load (and heat) this
# module was contributing. TTL is just a safety net for cache growth / eventual refresh, not
# how staleness is actually avoided: staleness is avoided because a real change in the
# underlying numbers changes the prompt text, which changes the cache key automatically.
_CACHE_TTL_SECONDS = 30 * 60
# Cache keys are content-addressed on the formatted prompt text, and every distinct
# reading eventually produces a distinct key — without a cap this dict (and its matching
# inflight-lock map) would grow for as long as the process runs. Sweep expired entries
# once the cache crosses this size rather than tracking a per-entry timer.
_CACHE_SWEEP_THRESHOLD = 200
_cache: dict[str, tuple[float, str]] = {}
_cache_lock = threading.Lock()

# Concurrent requests for the exact same facts (e.g. ConditionsBar and AqiPanel both
# firing on initial page load, before either has populated the cache) would otherwise both
# hit Ollama at once, doubling the momentary compute/heat spike for zero benefit — one of
# them is guaranteed to produce a response the other could have reused. A per-key lock makes
# the second caller wait for the first's result instead of duplicating the work.
_inflight_locks: dict[str, threading.Lock] = {}
_inflight_locks_guard = threading.Lock()


def _cache_key(prompt: str, system: str | None) -> str:
    digest = hashlib.sha256()
    digest.update((system or "").encode("utf-8"))
    digest.update(b"\x00")
    digest.update(prompt.encode("utf-8"))
    return digest.hexdigest()


def _sweep_expired_locked(now: float) -> None:
    """Caller must hold _cache_lock. Drops expired cache entries and their matching
    inflight locks so both maps stay bounded across a long-running process."""
    expired = [k for k, (ts, _) in _cache.items() if now - ts >= _CACHE_TTL_SECONDS]
    for k in expired:
        _cache.pop(k, None)
    if expired:
        with _inflight_locks_guard:
            for k in expired:
                _inflight_locks.pop(k, None)


def _get_inflight_lock(key: str) -> threading.Lock:
    with _inflight_locks_guard:
        lock = _inflight_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _inflight_locks[key] = lock
        return lock


def generate(
    prompt: str,
    system: str | None = None,
    timeout: float = _TIMEOUT_SECONDS,
    max_tokens: int = _DEFAULT_MAX_TOKENS,
) -> str | None:
    """Calls the local Ollama server for a single non-streaming completion, cached by the
    exact (system, prompt) text so repeated requests for the same already-computed facts
    don't re-run the model — see module docstring above for why that's the main lever here.

    This is best-effort narrative enrichment, not a required data path: any failure (Ollama
    not running, model not pulled, request timeout) is caught and logged, returning None so
    callers fall back to their existing template-generated text instead of breaking the API
    response. Never used for numeric predictions — only for phrasing numbers already computed
    elsewhere. `timeout` defaults to the usual short one-liner budget; pass a larger value for
    longer, multi-paragraph generations (e.g. the cross-indicator dashboard summary).
    `max_tokens` bounds the worst-case generation length (and so the worst-case compute/heat
    per call) regardless of how verbose the model tries to be.
    """
    if not settings.llm_narrative_enabled:
        return None

    key = _cache_key(prompt, system)
    now = time.monotonic()

    with _cache_lock:
        cached = _cache.get(key)
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    lock = _get_inflight_lock(key)
    with lock:
        # Re-check after acquiring the lock: whoever held it first may have just populated
        # the cache while this call was waiting.
        with _cache_lock:
            cached = _cache.get(key)
        if cached is not None and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": max_tokens},
            # Keep the model loaded well past this app's own refresh cadence so periodic
            # calls don't each pay Ollama's cold-load cost on top of generation itself.
            "keep_alive": "30m",
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
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Ollama narrative generation failed, using template fallback: %s", exc)
            return None

        if not text:
            return None

        with _cache_lock:
            if len(_cache) >= _CACHE_SWEEP_THRESHOLD:
                _sweep_expired_locked(time.monotonic())
            _cache[key] = (time.monotonic(), text)
        return text
