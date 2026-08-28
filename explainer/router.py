# explainer/router.py — must always export a module-level `router = APIRouter()` (FINAL.md
# line 1706: "Person B's mount line depends on that exact name"). Mounted by api/main.py
# inside a try/except; if this file is broken or missing, the API still boots (already
# verified this session — no changes needed on that side).
from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from contracts.schemas import State
from explainer import config, llm as llm_mod, templates, whatif as whatif_mod

log = logging.getLogger(__name__)

router = APIRouter()


class ExplainBody(BaseModel):
    mode: str = "template"


class WhatIfBody(BaseModel):
    overrides: list[dict[str, Any]] = []
    weights: dict[str, float] | None = None


def _fetch_json(path: str) -> dict[str, Any]:
    """explainer/ never imports api/ or touches the database (FINAL.md line 1705) — it reads
    what it needs back over HTTP from the same running API, exactly like api/'s own internal
    calls into this package (api/routers/decisions.py's `_try_attach_explanation`)."""
    try:
        resp = httpx.get(f"{config.API_BASE_URL}{path}", timeout=5.0)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"could not reach the api: {exc}") from exc
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"not found: {path}")
    resp.raise_for_status()
    return resp.json()


@router.post("/explain/{decision_id}")
def explain(decision_id: str, body: ExplainBody) -> dict[str, Any]:
    decision = _fetch_json(f"/decisions/{decision_id}")
    if body.mode == "llm":
        try:
            return llm_mod.build_explanation(decision)
        except Exception:
            # Never allowed to fail the request over this — templates.py is the required
            # floor (FINAL.md §17 cut #1) and must always produce a valid Explanation.
            log.warning("llm explainer unavailable for %s, falling back to template", decision_id, exc_info=True)
    return templates.build_explanation(decision)


@router.post("/whatif")
def whatif(body: WhatIfBody) -> dict[str, Any]:
    state = State.model_validate(_fetch_json("/state?policy=AGENT"))
    result = whatif_mod.run(state, body.overrides, body.weights)
    result["explanation"] = templates.build_explanation(result["whatif_decision"])
    return result
