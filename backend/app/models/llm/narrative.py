"""Turns already-computed numbers into natural-language explanations via a local Mistral
model (through Ollama). Every function here is given the exact figures the rest of the app
already calculated (z-scores, percentages, mechanism/citation text) and is instructed to
phrase them, not recompute or invent them. If the local model is unreachable or returns
nothing usable, callers fall back to the existing template-generated sentence — the API
response shape and its numeric fields never depend on the LLM being available.
"""

import re

from app.models.llm.ollama_client import generate

_NARRATIVE_SYSTEM_PROMPT = (
    "You are writing a short explanation for an disaster early-warning dashboard. You are given "
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


def enrich_disaster_outlook(*, region_label: str, facts: list[str], fallback: str) -> str:
    """Phrase an already-computed regional flood/landslide outlook for the dashboard.
    `facts` are complete sentences/lines of computed figures; the model may only restate
    them."""
    lines = "\n".join(f"- {f}" for f in facts)
    prompt = (
        f"Region: {region_label}, Nepal\n\n"
        f"Computed disaster outlook from the local forecasting models:\n{lines}\n\n"
        "Write a short, plain-language paragraph (2-4 sentences) for a public early-warning "
        "dashboard summarizing this outlook and what it means for people in the area. Use only "
        "the numbers and dates given — do not invent a probability, date, or figure."
    )
    text = generate(prompt, system=_NARRATIVE_SYSTEM_PROMPT)
    return _strip_ai_tells(text) if text else fallback
