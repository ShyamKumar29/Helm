# explainer/llm.py — the enhancement layer (FINAL.md §17 cut #1: optional on top of
# templates.py, which must always work without this). Groq-backed (OpenAI-compatible chat
# completions endpoint, plain HTTP — no SDK dependency beyond httpx, which api/ already
# needs anyway).
#
# CLAUDE.md rule 4, taken literally: the model is shown ONLY a trimmed decision (the numbers
# it's allowed to talk about), instructed to invent nothing, and its numeric claims are
# checked against that same trimmed payload before being trusted. Anything that fails —
# network, bad JSON, an ungrounded number — raises, and router.py falls back to
# templates.py. This module never returns a number it can't trace.
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

from explainer import config, templates

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "rationale.txt"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Numbers under this are day-counts, percentages, action counts — not the rupee figures rule
# 4 is actually worried about. Grounding only the ones that matter keeps the check honest
# without breaking on every "3 invoices" or "21 days late" in the prose.
GROUNDING_FLOOR = 100
GROUNDING_TOLERANCE = 2


def _trimmed_decision(decision: dict[str, Any]) -> dict[str, Any]:
    """Only the fields the model is allowed to narrate — it never sees anything it could
    invent a number from that isn't already grounded."""
    top = templates._top_actions(decision, n=4)
    return {
        "decision_id": decision.get("decision_id"),
        "cash_before": decision.get("cash_before"),
        "buffer_required": decision.get("buffer_required"),
        "deployable_cash": decision.get("deployable_cash"),
        "trigger": decision.get("trigger"),
        "diff_from_previous": decision.get("diff_from_previous"),
        "actions": [decision["actions"][i] for i, _ in top],
    }


def _grounded_numbers(payload: dict[str, Any]) -> set[int]:
    nums = re.findall(r"\d+(?:\.\d+)?", json.dumps(payload))
    return {round(float(n)) for n in nums if float(n) >= GROUNDING_FLOOR}


def _claimed_numbers(text: str) -> set[int]:
    nums = re.findall(r"\d[\d,]*(?:\.\d+)?", text)
    out = set()
    for n in nums:
        try:
            out.add(round(float(n.replace(",", ""))))
        except ValueError:
            continue
    return {n for n in out if n >= GROUNDING_FLOOR}


def build_explanation(decision: dict[str, Any]) -> dict[str, Any]:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")

    trimmed = _trimmed_decision(decision)
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    resp = httpx.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}", "content-type": "application/json"},
        json={
            "model": config.GROQ_MODEL,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(trimmed)},
            ],
        },
        timeout=config.GROQ_TIMEOUT_S,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    parsed = json.loads(content)

    narrative = str(parsed.get("narrative", "")).strip()
    if not narrative:
        raise ValueError("llm returned an empty narrative")

    allowed = _grounded_numbers(trimmed)
    claimed = _claimed_numbers(narrative)
    ungrounded = {c for c in claimed if not any(abs(c - a) <= GROUNDING_TOLERANCE for a in allowed)}
    if ungrounded:
        log.warning("llm explanation cited ungrounded number(s) %s, discarding", ungrounded)
        raise ValueError(f"llm explanation not grounded: {ungrounded}")

    fallback_headline = templates.build_explanation(decision)["headline"]

    return {
        "decision_id": decision.get("decision_id", ""),
        "headline": str(parsed.get("headline", "")).strip() or fallback_headline,
        "narrative": narrative,
        "key_assumptions": [str(x) for x in (parsed.get("key_assumptions") or [])],
        "tradeoffs": [str(x) for x in (parsed.get("tradeoffs") or [])],
        "would_change_if": [str(x) for x in (parsed.get("would_change_if") or [])],
        "generated_by": f"groq-{config.GROQ_MODEL}",
        "grounded_fields": ["cash_before", "buffer_required", "deployable_cash", "actions"],
    }
