# engine/optimizer/scoring.py — FINAL.md §11.1-§11.3 and §11.6, exactly.
#
# `net_value` (the rupee figure shown on screen) is discount_captured - penalty_incurred -
# financing_cost - liquidity_risk_cost — matches decision.sample.json's own worked example
# (17000 - 0 - 4100 - 1200 = 11700). `supplier_stress_delta` is reported separately: it's a
# dimensionless relationship-health indicator, not a rupee cost, and only enters the weighted
# `score` used to rank candidates (via STRESS_TO_RUPEE below), never `net_value` itself.
from __future__ import annotations

from contracts.schemas import Invoice, ObjectiveWeights, Supplier

EMERGENCY_RATE = 0.30  # §11.6 — annualised cost of emergency funding if the buffer is breached
STRESS_TO_RUPEE_PCT = 0.05  # calibration note in §11.6: "~10-20% of typical financing cost";
# 5% of the invoice amount lands comfortably inside that band for a typical mid-size invoice.


def effective_apr_of_discount(discount_pct: float, discount_days: int, net_days: int) -> float:
    """§11.1 — the annualised cost of *forgoing* a d/D net N discount."""
    if net_days <= discount_days:
        return float("inf")
    d = discount_pct / 100.0
    if d >= 1.0:
        return float("inf")
    return (d / (1 - d)) * (365.0 / (net_days - discount_days))


def financing_cost(amount: float, apr_pct: float, days_outstanding: int) -> float:
    """§11.2."""
    return amount * (apr_pct / 100.0) * (days_outstanding / 365.0)


def late_penalty(invoice: Invoice, days_late: int) -> float:
    """§11.3. Caller is responsible for clamping `days_late` to `invoice.max_delay_days`."""
    return invoice.amount * (invoice.penalty_bps_per_day / 10000.0) * days_late


def supplier_stress_delta(action: str, supplier: Supplier | None) -> float:
    """Dimensionless, roughly in [-0.3, 1.0]. Positive = relationship gets worse (a delay on
    a critical, cash-stressed supplier); negative = it improves (paid promptly or early)."""
    if supplier is None:
        return 0.0
    base = supplier.criticality * supplier.liquidity_stress
    if action == "DELAY":
        return base
    if action in ("PAY_NOW", "PAY_EARLY_DISCOUNT", "FINANCE_BANK", "FINANCE_SUPPLIER"):
        return -0.3 * base
    if action == "HOLD":
        return 0.1 * base
    return 0.0  # PAY_AT_MATURITY — the contractual baseline, no relationship signal either way


def liquidity_risk_cost(amount_from_cash: float, shortfall_prob_at_binding: float) -> float:
    """§11.6's `expected_shortfall_cost`, collapsed to a single per-candidate estimate: the
    rupees drawn from today's own cash, weighted by how likely the forecast already says the
    buffer breaks, priced at the emergency-funding rate. Zero for anything funded by a
    facility instead of cash — that risk is priced by `financing_cost`, not this term."""
    if amount_from_cash <= 0:
        return 0.0
    return amount_from_cash * shortfall_prob_at_binding * EMERGENCY_RATE


def weighted_score(
    weights: ObjectiveWeights,
    discount_captured: float,
    penalty_incurred: float,
    fin_cost: float,
    liq_risk_cost: float,
    stress_delta: float,
    invoice_amount: float,
) -> float:
    """§11.6's objective — used only to rank/select candidates. `net_value` (the number shown
    to a human) is a separate, simpler rupee figure computed by the caller."""
    stress_rupees = stress_delta * invoice_amount * STRESS_TO_RUPEE_PCT
    return (
        weights.discount * discount_captured
        - weights.financing_cost * fin_cost
        - weights.penalty * penalty_incurred
        - weights.liquidity_risk * liq_risk_cost
        - weights.supplier_stress * stress_rupees
    )
