# contracts/schemas.py — Pydantic models, the source of truth. FINAL.md section 8.
#
# OWNER: SHARED. Any shape change here is a contract change: announce it out loud,
# get agreement from both others, log it in contracts/CHANGELOG.md, tell everyone to pull.
# Do not reformat this file when editing it.
#
# Universal conventions (FINAL.md section 8):
#   - money: plain float, rounded to 2 decimals at the API boundary
#   - dates: ISO "YYYY-MM-DD", no timezones — `date` fields accept and re-emit that string
#   - optional fields are present with `null`, never omitted
#   - all keys snake_case
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from contracts.enums import (
    ActionStatus,
    ActionType,
    EventSource,
    EventType,
    FacilityType,
    FundingSource,
    InvoiceStatus,
    ObligationCategory,
    ReasonCode,
    ReceivableStatus,
    SolverMethod,
    SolverStatus,
    TriggerType,
)


class Contract(BaseModel):
    """Base for every contract model: unknown keys are a shape drift, not silently dropped."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --------------------------------------------------------------------------------------
# 8.2 State
# --------------------------------------------------------------------------------------


class Supplier(Contract):
    id: str
    name: str
    criticality: float = Field(ge=0, le=1)
    liquidity_stress: float = Field(ge=0, le=1)
    supplier_finance_eligible: bool


class Customer(Contract):
    id: str
    name: str
    mean_delay_days: float
    std_delay_days: float
    on_time_probability: float = Field(ge=0, le=1)
    historical_delays: list[float]


class Invoice(Contract):
    id: str
    supplier_id: str
    amount: float
    issue_date: date
    due_date: date
    discount_pct: float | None
    discount_until: date | None
    penalty_bps_per_day: float
    max_delay_days: int
    status: InvoiceStatus


class Receivable(Contract):
    id: str
    customer_id: str
    amount: float
    expected_date: date
    status: ReceivableStatus


class Obligation(Contract):
    id: str
    label: str
    category: ObligationCategory
    amount: float
    due_date: date
    hard: bool


class Facility(Contract):
    id: str
    type: FacilityType
    limit: float
    drawn: float
    apr_pct: float
    min_draw: float
    repayment_days: int
    eligible_supplier_ids: list[str] | None


class State(Contract):
    as_of: date
    sim_day: int
    cash_available: float
    suppliers: list[Supplier]
    customers: list[Customer]
    invoices: list[Invoice]
    receivables: list[Receivable]
    obligations: list[Obligation]
    facilities: list[Facility]


# --------------------------------------------------------------------------------------
# 8.3 Forecast
# --------------------------------------------------------------------------------------


class ForecastBucket(Contract):
    date: date
    day_offset: int
    p10: float
    p50: float
    p90: float
    shortfall_prob: float = Field(ge=0, le=1)
    committed_outflow: float
    expected_inflow: float


class Forecast(Contract):
    generated_at: date
    sim_day: int
    horizon_days: int
    n_paths: int
    risk_alpha: float
    buckets: list[ForecastBucket]
    deployable_cash: float = Field(ge=0)
    buffer_required: float
    binding_date: date | None
    binding_reason: str | None
    worst_case_min_cash: float


# --------------------------------------------------------------------------------------
# 8.4 DecisionObject
# --------------------------------------------------------------------------------------


class ObjectiveWeights(Contract):
    discount: float
    financing_cost: float
    penalty: float
    liquidity_risk: float
    supplier_stress: float


class Trigger(Contract):
    type: TriggerType
    event_id: str | None
    materiality_score: float | None
    description: str | None


class ScoreBreakdown(Contract):
    discount_captured: float
    penalty_incurred: float
    financing_cost: float
    liquidity_risk_cost: float
    supplier_stress_delta: float
    net_value: float


class RejectedAlternative(Contract):
    action: ActionType
    net_value: float
    delta: float = Field(le=0)  # PS req 7: never a better rejected alternative
    reason_code: ReasonCode


class Action(Contract):
    action_id: str
    target_type: str
    target_id: str
    supplier_id: str | None
    action: ActionType
    amount: float
    execute_on: date | None
    funding_source: FundingSource
    facility_id: str | None
    confidence: float = Field(ge=0, le=1)
    score_breakdown: ScoreBreakdown
    binding_constraints: list[str]
    primary_reason_code: ReasonCode
    rejected_alternatives: list[RejectedAlternative] = Field(min_length=1)  # PS req 7
    status: ActionStatus


class FacilityAction(Contract):
    facility_id: str
    action: str
    amount: float
    expected_repay_date: date | None
    interest_cost: float


class SolverInfo(Contract):
    method: SolverMethod
    status: SolverStatus
    solve_ms: int
    n_scenarios: int
    fallback_used: bool


class DiffFlip(Contract):
    target_id: str
    from_: ActionType = Field(alias="from")
    to: ActionType
    reason_code: ReasonCode


class DiffFromPrevious(Contract):
    previous_decision_id: str | None
    flipped: list[DiffFlip]
    added: list[dict] = Field(default_factory=list)
    removed: list[dict] = Field(default_factory=list)


class Explanation(Contract):
    decision_id: str
    headline: str
    narrative: str
    key_assumptions: list[str]
    tradeoffs: list[str]
    would_change_if: list[str]
    generated_by: str
    grounded_fields: list[str]


class DecisionObject(Contract):
    decision_id: str
    run_at: date
    sim_day: int
    policy: str  # "AGENT" | "BASELINE" — FINAL.md section 8.4
    trigger: Trigger
    cash_before: float
    buffer_required: float
    deployable_cash: float
    objective_weights: ObjectiveWeights
    objective_value: float
    actions: list[Action]
    facility_actions: list[FacilityAction]
    solver: SolverInfo
    diff_from_previous: DiffFromPrevious | None
    explanation: Explanation | None


# --------------------------------------------------------------------------------------
# 8.6 Event
# --------------------------------------------------------------------------------------


class Event(Contract):
    event_id: str
    sim_day: int
    date: date
    type: EventType
    source: EventSource
    payload: dict
    materiality_score: float | None
    triggered_reoptimization: bool
    triggered_decision_id: str | None


# --------------------------------------------------------------------------------------
# 8.7 ComparisonMetrics
# --------------------------------------------------------------------------------------


class PolicyMetrics(Contract):
    discounts_captured: float
    financing_cost: float
    penalties_paid: float
    net_working_capital_cost: float
    shortfall_days: int
    min_cash_seen: float
    obligations_missed: int
    avg_supplier_stress: float
    decisions_made: int
    reoptimizations_triggered: int
    health_score: int = Field(ge=0, le=100)
    savings_per_day: float


class MetricsDelta(Contract):
    net_working_capital_cost: float
    shortfall_days: int
    obligations_missed: int
    health_score: int


class ComparisonMetrics(Contract):
    sim_day: int
    as_of: date
    agent: PolicyMetrics
    baseline: PolicyMetrics
    delta: MetricsDelta
