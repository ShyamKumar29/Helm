# engine/actions/candidates.py — FINAL.md §12 build order step 3: "enumerates every legal
# action per open invoice with its execution date, funding source options and full
# score_breakdown." One `Candidate` per economically-distinct (action, funding_source) pair;
# `optimizer/greedy_fallback.py` and `optimizer/milp.py` both consume the same list and just
# differ in how they pick one per invoice.
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from contracts.schemas import Facility, Invoice, ObjectiveWeights, Supplier
from engine.optimizer.scoring import (
    financing_cost,
    late_penalty,
    liquidity_risk_cost,
    supplier_stress_delta,
    weighted_score,
)

REASON_FOR_ACTION = {
    "PAY_NOW": "OBLIGATION_PRIORITY",
    "PAY_AT_MATURITY": "PENALTY_AVOIDED",
    "DELAY": "PENALTY_ACCEPTED",
    "FINANCE_BANK": "INSUFFICIENT_CASH",
    "HOLD": "OBLIGATION_PRIORITY",
}


@dataclass
class Candidate:
    invoice: Invoice
    supplier: Supplier | None
    action: str  # ActionType
    funding_source: str  # FundingSource
    facility: Facility | None
    amount: float
    execute_on: date | None
    days_late: int
    discount_captured: float
    penalty_incurred: float
    financing_cost: float
    liquidity_risk_cost: float
    supplier_stress_delta: float
    net_value: float
    score: float  # weighted — ranking only, never shown directly
    primary_reason_code: str
    binding_constraints: list[str]


def _has_discount(invoice: Invoice, as_of: date) -> bool:
    return (
        invoice.discount_pct is not None
        and invoice.discount_until is not None
        and invoice.discount_until >= as_of
    )


def _make(
    invoice: Invoice,
    supplier: Supplier | None,
    action: str,
    funding_source: str,
    facility: Facility | None,
    amount: float,
    execute_on: date | None,
    days_late: int,
    weights: ObjectiveWeights,
    shortfall_prob_at_binding: float,
) -> Candidate:
    discount_captured = invoice.amount * (invoice.discount_pct or 0) / 100.0 if action == "PAY_EARLY_DISCOUNT" else 0.0
    penalty_incurred = late_penalty(invoice, days_late) if action == "DELAY" else 0.0
    fin_cost = (
        financing_cost(amount, facility.apr_pct, facility.repayment_days)
        if facility is not None and funding_source in ("BANK_LINE", "SUPPLIER_FINANCE")
        else 0.0
    )
    liq_cost = liquidity_risk_cost(amount, shortfall_prob_at_binding) if funding_source == "CASH" else 0.0
    stress = supplier_stress_delta(action, supplier)
    net_value = discount_captured - penalty_incurred - fin_cost - liq_cost
    score = weighted_score(weights, discount_captured, penalty_incurred, fin_cost, liq_cost, stress, invoice.amount)

    if action == "PAY_EARLY_DISCOUNT":
        reason = "CHEAPER_FINANCING" if funding_source == "BANK_LINE" else "DISCOUNT_CAPTURED"
    elif action == "PAY_AT_MATURITY" and invoice.penalty_bps_per_day <= 0:
        reason = "NO_BETTER_ALTERNATIVE"
    elif action == "FINANCE_SUPPLIER":
        reason = "SUPPLIER_DISTRESS" if supplier and supplier.liquidity_stress >= supplier.criticality else "SUPPLIER_CRITICAL"
    else:
        reason = REASON_FOR_ACTION.get(action, "NO_BETTER_ALTERNATIVE")

    binding: list[str] = []
    if funding_source == "CASH" and liq_cost > 0:
        binding.append("BUFFER_FLOOR")
    if funding_source in ("BANK_LINE", "SUPPLIER_FINANCE"):
        binding.append("FACILITY_LIMIT")

    return Candidate(
        invoice=invoice,
        supplier=supplier,
        action=action,
        funding_source=funding_source,
        facility=facility,
        amount=round(amount, 2),
        execute_on=execute_on,
        days_late=days_late,
        discount_captured=round(discount_captured, 2),
        penalty_incurred=round(penalty_incurred, 2),
        financing_cost=round(fin_cost, 2),
        liquidity_risk_cost=round(liq_cost, 2),
        supplier_stress_delta=round(stress, 4),
        net_value=round(net_value, 2),
        score=score,
        primary_reason_code=reason,
        binding_constraints=binding,
    )


def rejection_reason(candidate: Candidate, chosen: Candidate) -> str:
    """Why this *non-chosen* candidate lost, for its entry in `rejected_alternatives`
    (FINAL.md §8.4 / PS requirement 7) — a different question from `primary_reason_code`,
    which answers why the chosen one won."""
    if candidate.action == "PAY_AT_MATURITY" and chosen.action == "PAY_EARLY_DISCOUNT":
        return "DISCOUNT_FORGONE"
    if candidate.funding_source == "CASH" and candidate.liquidity_risk_cost > 0:
        return "BUFFER_BREACH"
    if candidate.funding_source in ("BANK_LINE", "SUPPLIER_FINANCE"):
        return "FACILITY_LIMIT" if candidate.net_value < chosen.net_value else "CHEAPER_FINANCING"
    if candidate.action == "DELAY":
        return "PENALTY_ACCEPTED"
    if candidate.action == "HOLD" and chosen.action != "HOLD":
        return "OBLIGATION_PRIORITY"
    return "NO_BETTER_ALTERNATIVE"


def generate(
    invoice: Invoice,
    supplier: Supplier | None,
    as_of: date,
    weights: ObjectiveWeights,
    bank_facility: Facility | None,
    supplier_facility: Facility | None,
    shortfall_prob_at_binding: float,
) -> list[Candidate]:
    """Every legal (action, funding_source) pair for one open invoice. Always non-empty —
    HOLD is unconditional, which is what lets `actions[]` cover every invoice explicitly
    (FINAL.md §8.4) even on an invoice with no live option at all."""
    out: list[Candidate] = []

    out.append(_make(invoice, supplier, "HOLD", "CASH", None, 0.0, None, 0, weights, shortfall_prob_at_binding))
    out.append(
        _make(invoice, supplier, "PAY_AT_MATURITY", "CASH", None, invoice.amount, invoice.due_date, 0, weights, shortfall_prob_at_binding)
    )
    out.append(_make(invoice, supplier, "PAY_NOW", "CASH", None, invoice.amount, as_of, 0, weights, shortfall_prob_at_binding))

    if _has_discount(invoice, as_of):
        discounted = invoice.amount * (1 - (invoice.discount_pct or 0) / 100.0)
        out.append(
            _make(invoice, supplier, "PAY_EARLY_DISCOUNT", "CASH", None, discounted, invoice.discount_until, 0, weights, shortfall_prob_at_binding)
        )
        if bank_facility is not None:
            out.append(
                _make(
                    invoice, supplier, "PAY_EARLY_DISCOUNT", "BANK_LINE", bank_facility,
                    discounted, invoice.discount_until, 0, weights, shortfall_prob_at_binding,
                )
            )

    if invoice.max_delay_days > 0:
        out.append(
            _make(
                invoice, supplier, "DELAY", "CASH", None, invoice.amount,
                invoice.due_date + timedelta(days=invoice.max_delay_days),
                invoice.max_delay_days, weights, shortfall_prob_at_binding,
            )
        )

    if bank_facility is not None:
        headroom = bank_facility.limit - bank_facility.drawn
        if headroom >= max(invoice.amount, bank_facility.min_draw):
            out.append(
                _make(invoice, supplier, "FINANCE_BANK", "BANK_LINE", bank_facility, invoice.amount, as_of, 0, weights, shortfall_prob_at_binding)
            )

    if (
        supplier is not None
        and supplier.supplier_finance_eligible
        and supplier_facility is not None
        and supplier_facility.eligible_supplier_ids is not None
        and supplier.id in supplier_facility.eligible_supplier_ids
    ):
        headroom = supplier_facility.limit - supplier_facility.drawn
        if headroom >= max(invoice.amount, supplier_facility.min_draw):
            out.append(
                _make(
                    invoice, supplier, "FINANCE_SUPPLIER", "SUPPLIER_FINANCE", supplier_facility,
                    invoice.amount, as_of, 0, weights, shortfall_prob_at_binding,
                )
            )

    return out
