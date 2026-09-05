"""Turns already-computed numbers into natural-language explanations via a local Mistral
model (through Ollama). Every function here is given the exact figures the rest of the app
already calculated (z-scores, percentages, mechanism/citation text) and is instructed to
phrase them, not recompute or invent them. If the local model is unreachable or returns
nothing usable, callers fall back to the existing template-generated sentence — the API
response shape and its numeric fields never depend on the LLM being available.
"""

import re

from app.services.llm.ollama_client import generate

_NARRATIVE_SYSTEM_PROMPT = (
    "You are writing a short explanation for an environmental risk dashboard. You are given "
    "exact numbers and facts that have already been computed — use only those numbers, do not "
    "invent, recalculate, or round them differently than given. Do not add citations, sources, "
    "or facts beyond what is provided. Write 2-3 plain, direct sentences, no bullet points, no "
    "headers, no markdown, no preamble like 'Sure, here is...' — just the explanation text "
    "itself, in a neutral, factual tone. State the numbers and what they mean plainly, without "
    "hedging phrases like 'however', 'it's important to note', or 'this suggests that'."
)

# The system prompt alone doesn't reliably stop a small local model from reaching for
# stock AI-report phrasing, so this is a deterministic backstop: strip the usual hedge/
# transition fillers when they open a sentence, then re-capitalize what's left. Only
# matches at a sentence boundary so it won't mangle the phrase if it's used mid-sentence.
_LEADING_TELLS = [
    r"however,?\s*",
    r"it'?s important to (?:note|consider|remember) that\s*",
    r"it is important to (?:note|consider|remember) that\s*",
    r"note that\s*",
    r"keep in mind that\s*",
    r"overall,\s*",
    r"in summary,\s*",
    r"additionally,\s*",
    r"furthermore,\s*",
    r"this suggests that\s*",
    r"this may indicate that\s*",
    r"hey( there)?[,!]\s*",
]
_LEADING_TELL_RE = re.compile(
    r"(^|(?<=[.!?]\s))(" + "|".join(_LEADING_TELLS) + r")", re.IGNORECASE
)
_TRAILING_TELLS_RE = re.compile(
    r"\s*(stay tuned[^.!?]*[.!?]|keep an eye out[^.!?]*[.!?])\s*$", re.IGNORECASE
)

# Whole throwaway sentences the model adds that carry no actual information beyond what's
# already been said — generic "conditions may vary" hand-waving. These are removed as
# entire sentences (not just the trigger phrase), wherever they appear, since trimming just
# the phrase would leave a broken sentence fragment behind.
_VAGUE_DISCLAIMER_SENTENCE_RE = re.compile(
    r"(?:(?<=^)|(?<=[.!?]\s))[^.!?]*\b("
    r"subject to (?:various|many|numerous|several) factors"
    r"|various factors (?:could|may|might) (?:influence|affect|impact)"
    r"|many factors (?:could|may|might) (?:come into play|be at work|influence)"
    r"|unforeseen (?:events|circumstances|factors)"
    r"|(?:this|the) (?:analysis|assessment) is ongoing"
    r"|conditions (?:may|could|might) vary"
    r")\b[^.!?]*[.!?]\s*",
    re.IGNORECASE,
)


def _strip_ai_tells(text: str) -> str:
    text = _TRAILING_TELLS_RE.sub("", text)
    text = _VAGUE_DISCLAIMER_SENTENCE_RE.sub("", text)
    # Chained hedges ("However, it's important to note that...") only become eligible one
    # at a time: re.sub scans the ORIGINAL string once, so after stripping "However, " the
    # newly-exposed sentence start isn't re-checked in that same pass. Loop until stable.
    prev = None
    while prev != text:
        prev = text
        text = _LEADING_TELL_RE.sub("", text)
    text = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)
    return re.sub(r"\s{2,}", " ", text).strip()


def enrich_forecast_summary(
    contributions: list[dict],
    base_value: float,
    predicted: float,
    actual: float,
    fallback: str,
) -> str:
    top = contributions[:3]
    driver_lines = "\n".join(
        f"- {c['label']}: contribution {c['contribution']:+.3e} "
        f"({'pushes prediction up' if c['contribution'] > 0 else 'pushes prediction down'})"
        for c in top
    )
    prompt = (
        "Explain what is driving a NO2 (air pollution proxy) forecast for one location.\n\n"
        f"Baseline expectation (SHAP base value): {base_value:.3e}\n"
        f"Model's predicted value for the latest date: {predicted:.3e}\n"
        f"Actual observed value for that date: {actual:.3e}\n"
        f"Top contributing features (SHAP values):\n{driver_lines}\n\n"
        "Write a short, natural explanation of why the prediction landed where it did, "
        "naming the top drivers and whether each pushed the prediction up or down."
    )
    text = generate(prompt, system=_NARRATIVE_SYSTEM_PROMPT)
    return _strip_ai_tells(text) if text else fallback


def enrich_optimizer_explanation(
    *,
    city: str,
    budget: float,
    traffic_budget: float,
    reduction_pct: float,
    afforest_budget: float,
    area_pct: float,
    projected_no2: float,
    projected_ndvi: float,
    projected_risk_score: float,
    carbon_value_usd: float | None,
    fallback: str,
) -> str:
    no_spend = reduction_pct < 0.1 and area_pct < 0.1
    prompt = (
        f"Location: {city}\n"
        f"A reinforcement-learning policy (PPO) was trained to split a ₹{budget:.0f} "
        "mitigation budget between two interventions — cutting traffic (which lowers NO2 "
        "pollution) and afforestation (which raises NDVI vegetation cover) — to minimize "
        "combined projected risk.\n\n"
        f"Recommended traffic-reduction spend: ₹{traffic_budget:.1f} "
        f"({reduction_pct:.1f}% traffic reduction)\n"
        f"Recommended afforestation spend: ₹{afforest_budget:.1f} "
        f"({area_pct:.1f}% of the buffer area reforested)\n"
        f"Projected NO2 after this allocation: {projected_no2:.3e} mol/m²\n"
        f"Projected NDVI after this allocation: {projected_ndvi:.3f}\n"
        f"Projected residual risk score (0 = no elevated risk left): "
        f"{projected_risk_score:.3f}\n"
        + (
            f"Estimated value of CO2 avoided: ${carbon_value_usd:.0f}\n"
            if carbon_value_usd is not None
            else ""
        )
        + (
            "\nNote: both recommended amounts are near zero — this means the model found "
            "no meaningful elevated risk to spend the budget reducing, not that the "
            "calculation failed.\n"
            if no_spend
            else ""
        )
        + "\nWrite a short, natural explanation of this recommendation for a dashboard "
        "reader: what split it recommends and why that's a reasonable way to spend the "
        "budget given the projected outcome."
    )
    text = generate(prompt, system=_NARRATIVE_SYSTEM_PROMPT)
    return _strip_ai_tells(text) if text else fallback


def enrich_risk_explanation(
    *,
    city: str,
    indicator_label: str,
    risk_level: str,
    pct_change: float,
    mechanism: str,
    outcome: str,
    extra_context: str = "",
    fallback: str,
) -> str:
    prompt = (
        f"Location: {city}\n"
        f"Indicator: {indicator_label}\n"
        f"Risk level (already classified, relative to this location's own historical "
        f"baseline — not an absolute threshold): {risk_level}\n"
        f"Percent change vs. baseline: {pct_change:+.1f}%\n"
        f"Linked outcome: {outcome}\n"
        f"Mechanism linking the indicator to this outcome: {mechanism}\n"
        + (f"Additional context: {extra_context}\n" if extra_context else "")
        + "\nWrite a short, natural explanation of this risk finding for a dashboard reader, "
        "stating the risk level and percent change, and explaining the mechanism in plain "
        "language."
    )
    text = generate(prompt, system=_NARRATIVE_SYSTEM_PROMPT)
    return _strip_ai_tells(text) if text else fallback
