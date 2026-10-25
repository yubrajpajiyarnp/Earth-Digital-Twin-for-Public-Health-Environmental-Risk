"""Builds one Mistral-generated executive summary across both monitored Nepal regions
(Kathmandu Valley floods, Mugling–Narayangadh landslides). Every fact fed to the model is
already computed by the local ML engine (app/models/simulation/disaster_ml.py) — this only
synthesizes and phrases them, it never computes a new number or a new forecast itself.

Per-region narratives are skipped (include_narrative=False) while gathering facts, since
this endpoint writes its own combined summary — avoiding two redundant LLM calls.
"""

import re

from app.models.llm.narrative import _strip_ai_tells
from app.models.llm.ollama_client import generate
from app.models.simulation.disaster_ml import predict_kathmandu_flood, predict_mugling_landslide

_SUMMARY_SYSTEM_PROMPT = (
    "You are writing a short executive summary for a disaster early-warning dashboard. You "
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
        flood = predict_kathmandu_flood(include_narrative=False)
        worst = max(flood["rivers"], key=lambda r: r["peak_m3s"] / r["thresholds_m3s"]["p90"])
        indicators.append(
            {
                "name": "Kathmandu Valley flood",
                "risk_level": flood["risk_tier"],
                "headline": f"{worst['river']} peak {worst['peak_m3s']:.1f} m³/s on {worst['peak_date']}",
                "detail": (
                    f"{worst['river']} forecast peak {worst['peak_m3s']:.1f} m³/s on {worst['peak_date']} "
                    f"(its P90 is {worst['thresholds_m3s']['p90']:.1f} m³/s)"
                    + ("; unexpected surge flagged" if flood["surge_warning"] else "")
                ),
            }
        )
    except RuntimeError as exc:
        unavailable.append(f"Kathmandu flood: {exc}")

    try:
        slide = predict_mugling_landslide(include_narrative=False)
        peak = slide["peak"]
        indicators.append(
            {
                "name": "Mugling corridor landslide",
                "risk_level": slide["risk_tier"],
                "headline": f"peak {peak['failure_probability']:.1%} on {peak['date']}",
                "detail": (
                    f"highest daily failure probability {peak['failure_probability']:.1%} (z {peak['failure_z']:+.1f}) on "
                    f"{peak['date']}; slope stability index {peak['slope_stability_index']:.2f}"
                ),
            }
        )
    except RuntimeError as exc:
        unavailable.append(f"Mugling landslide: {exc}")

    if not indicators:
        raise RuntimeError("Could not assess any region for the dashboard summary: " + "; ".join(unavailable))

    fallback = _build_fallback_summary(indicators, unavailable)
    return {
        "indicators": indicators,
        "unavailable": unavailable,
        "summary": _generate_summary(indicators, unavailable, fallback),
    }


def _build_fallback_summary(indicators: list[dict], unavailable: list[str]) -> str:
    text = " ".join(f"{i['name']}: {i['risk_level']} — {i['detail']}." for i in indicators)
    if unavailable:
        text += f" {len(unavailable)} region(s) could not be assessed this run."
    return text


def _generate_summary(indicators: list[dict], unavailable: list[str], fallback: str) -> str:
    lines = "\n".join(f"- {i['name']}: {i['risk_level']} — {i['detail']}" for i in indicators)
    prompt = (
        "Nepal hydro-geological disaster outlook for the next two weeks, from local ML models "
        "(tiers: typical / elevated / severe):\n"
        f"{lines}\n\n"
        + (f"Not available this run: {'; '.join(unavailable)}\n\n" if unavailable else "")
        + "Write two short paragraphs, separated by a blank line. Do not number them or "
        "prefix them with any label — write them as plain prose.\n"
        "First paragraph: an overall summary of the flood and landslide outlook in plain language.\n"
        "Second paragraph: what people living or travelling in these areas should watch for, "
        "based only on the figures above."
    )
    text = generate(prompt, system=_SUMMARY_SYSTEM_PROMPT, timeout=_SUMMARY_TIMEOUT_SECONDS)
    return _clean_summary(text) if text else fallback


def _clean_summary(text: str) -> str:
    text = _strip_ai_tells(text)
    # The model sometimes numbers the two paragraphs despite being told not to — strip a
    # leading "1. " / "2. " at the very start or right after a paragraph break.
    return re.sub(r"(^|\n\s*\n)\s*\d\.\s+", r"\1", text).strip()
