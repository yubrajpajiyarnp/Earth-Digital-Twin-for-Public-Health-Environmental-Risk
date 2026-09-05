"""Builds one Mistral-generated executive summary spanning all four live risk indicators
(air quality, vegetation, rainfall, wildlife), plus a plain-language read of what continuing
the current trend would mean. Every fact fed to the model is already computed by the same
risk-assessment modules used elsewhere (risk_level, pct_change_vs_baseline) — this only
synthesizes and phrases them, it never computes a new number or a new forecast itself.

Per-outcome LLM explanations are skipped (include_llm_explanations=False) when gathering
these facts, since this only needs each indicator's top-level numbers, not the individual
health/ecological outcome explanations those functions also generate — skipping them avoids
4-6 redundant LLM calls this endpoint doesn't need.
"""

import re

from app.core.config import settings
from app.services.knowledge_graph.fauna_risk_assessment import assess_fauna_disruption
from app.services.knowledge_graph.flood_risk_assessment import assess_flood_risk
from app.services.knowledge_graph.risk_assessment import assess_no2_health_risk
from app.services.knowledge_graph.vegetation_risk_assessment import assess_vegetation_risk
from app.services.llm.narrative import _strip_ai_tells
from app.services.llm.ollama_client import generate

_SUMMARY_SYSTEM_PROMPT = (
    "You are writing a short executive summary for an environmental risk dashboard. You "
    "are given exact numbers and facts that have already been computed — use only those "
    "numbers, do not invent, recalculate, or add new percentages, dates, or data points "
    "beyond what is given. Write in a neutral, factual, direct tone, like a person "
    "explaining this to a colleague — avoid hedging phrases like 'however', 'it's "
    "important to note', or 'this suggests that'. Do not end with a generic disclaimer "
    "sentence like 'this is subject to various factors' or 'conditions may vary' — if you "
    "have nothing more specific to say, just stop. No headers, no bullet points, no "
    "markdown, no preamble — just the two paragraphs of text themselves, separated by a "
    "blank line."
)

_SUMMARY_TIMEOUT_SECONDS = 45.0


def build_dashboard_summary() -> dict:
    indicators = []
    unavailable = []

    try:
        no2 = assess_no2_health_risk(include_llm_explanations=False)
        indicators.append(
            {
                "name": "Air quality (NO2)",
                "risk_level": no2["risk_level"],
                "pct_change_vs_baseline": no2["pct_change_vs_baseline"],
                "detail": "7-day forecast vs. its own recent baseline",
            }
        )
    except RuntimeError as exc:
        unavailable.append(f"Air quality: {exc}")

    try:
        veg = assess_vegetation_risk(include_llm_explanations=False)
        indicators.append(
            {
                "name": "Vegetation (NDVI)",
                "risk_level": veg["risk_level"],
                "pct_change_vs_baseline": veg["pct_change_vs_baseline"],
                "detail": f"Last {veg['recent_window_days']} days vs. its own baseline",
            }
        )
    except RuntimeError as exc:
        unavailable.append(f"Vegetation: {exc}")

    try:
        flood = assess_flood_risk(include_llm_explanations=False)
        indicators.append(
            {
                "name": "Rainfall / flood risk",
                "risk_level": flood["risk_level"],
                "pct_change_vs_baseline": flood["pct_change_vs_baseline"],
                "detail": f"Last {flood['recent_window_days']}-day total vs. typical",
            }
        )
    except RuntimeError as exc:
        unavailable.append(f"Rainfall: {exc}")

    try:
        fauna = assess_fauna_disruption(include_llm_explanations=False)
        indicators.append(
            {
                "name": "Wildlife activity",
                "risk_level": fauna["risk_level"],
                "pct_change_vs_baseline": fauna["pct_change_vs_baseline"],
                "detail": "Recent GBIF observation count vs. typical (publishing-lag caveat applies)",
            }
        )
    except RuntimeError as exc:
        unavailable.append(f"Wildlife: {exc}")

    if not indicators:
        raise RuntimeError(
            "Could not assess any indicator for the dashboard summary: " + "; ".join(unavailable)
        )

    fallback = _build_fallback_summary(indicators, unavailable)
    summary = _generate_summary(indicators, unavailable, fallback)

    return {
        "city": settings.pilot_city,
        "indicators": indicators,
        "unavailable": unavailable,
        "summary": summary,
    }


def _build_fallback_summary(indicators: list[dict], unavailable: list[str]) -> str:
    elevated = [i["name"] for i in indicators if i["risk_level"] == "elevated"]
    reduced = [i["name"] for i in indicators if i["risk_level"] == "reduced"]
    parts = []
    if elevated:
        verb = "is" if len(elevated) == 1 else "are"
        parts.append(f"{', '.join(elevated)} {verb} elevated relative to baseline")
    if reduced:
        verb = "is" if len(reduced) == 1 else "are"
        parts.append(f"{', '.join(reduced)} {verb} better than baseline")
    if not elevated and not reduced:
        parts.append("all tracked indicators are within their typical range")
    text = f"{settings.pilot_city}: " + "; ".join(parts) + "."
    if unavailable:
        text += f" {len(unavailable)} indicator(s) could not be assessed this run."
    return text


def _generate_summary(indicators: list[dict], unavailable: list[str], fallback: str) -> str:
    lines = "\n".join(
        f"- {i['name']}: {i['risk_level']} ({i['pct_change_vs_baseline']:+.1f}% vs baseline) — {i['detail']}"
        for i in indicators
    )
    prompt = (
        f"Location: {settings.pilot_city}\n\n"
        "Current status of each tracked environmental indicator (relative to this "
        "location's own recent baseline, not an absolute threshold):\n"
        f"{lines}\n\n"
        + (f"Not available this run: {'; '.join(unavailable)}\n\n" if unavailable else "")
        + "Write two short paragraphs, separated by a blank line. Do not number them or "
        "prefix them with '1.'/'2.' or any label — write them as plain prose.\n"
        "First paragraph: an overall summary of current conditions across these "
        "indicators — what's notable, what's normal, in plain language.\n"
        "Second paragraph: a plain-language read of what continuing the CURRENT "
        "direction and rough size of change (the same numbers given above) would mean "
        "over the coming weeks for whichever indicator is furthest from its baseline — "
        "describe the direction, not a new invented number."
    )
    text = generate(prompt, system=_SUMMARY_SYSTEM_PROMPT, timeout=_SUMMARY_TIMEOUT_SECONDS)
    return _clean_summary(text) if text else fallback


def _clean_summary(text: str) -> str:
    text = _strip_ai_tells(text)
    # The model sometimes numbers the two paragraphs despite being told not to — strip a
    # leading "1. " / "2. " at the very start or right after a paragraph break.
    return re.sub(r"(^|\n\s*\n)\s*\d\.\s+", r"\1", text).strip()
