# api/services/serializers.py — B3. The only place a DB row becomes JSON.
#
# Every Numeric becomes a float rounded to 2 decimals here. Every Date becomes an ISO
# string here. Every optional field is emitted as null, never omitted — the contract
# says the frontend must not have to check `undefined`.


def money(v) -> float:
    return round(float(v), 2)


def iso(d) -> str | None:
    return d.isoformat() if d else None


def supplier_out(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "criticality": float(row.criticality),
        "liquidity_stress": float(row.liquidity_stress),
        "supplier_finance_eligible": bool(row.supplier_finance_eligible),
    }


def customer_out(row) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "mean_delay_days": float(row.mean_delay_days),
        "std_delay_days": float(row.std_delay_days),
        "on_time_probability": float(row.on_time_probability),
        "historical_delays": [float(x) for x in row.historical_delays],
    }


def invoice_out(row) -> dict:
    return {
        "id": row.id,
        "supplier_id": row.supplier_id,
        "amount": money(row.amount),
        "issue_date": iso(row.issue_date),
        "due_date": iso(row.due_date),
        "discount_pct": float(row.discount_pct)
        if row.discount_pct is not None
        else None,
        "discount_until": iso(row.discount_until),
        "penalty_bps_per_day": float(row.penalty_bps_per_day),
        "max_delay_days": int(row.max_delay_days),
        "status": row.status,
    }


def receivable_out(row) -> dict:
    return {
        "id": row.id,
        "customer_id": row.customer_id,
        "amount": money(row.amount),
        "expected_date": iso(row.expected_date),
        "status": row.status,
    }


def obligation_out(row) -> dict:
    return {
        "id": row.id,
        "label": row.label,
        "category": row.category,
        "amount": money(row.amount),
        "due_date": iso(row.due_date),
        "hard": bool(row.hard),
    }


def facility_out(row) -> dict:
    # DB column is `limit_amount` (reserved word); the contract field is `limit`.
    # The rename happens here and nowhere else.
    return {
        "id": row.id,
        "type": row.type,
        "limit": money(row.limit_amount),
        "drawn": money(row.drawn),
        "apr_pct": float(row.apr_pct),
        "min_draw": money(row.min_draw),
        "repayment_days": int(row.repayment_days),
        "eligible_supplier_ids": row.eligible_supplier_ids,
    }


def event_out(row) -> dict:
    return {
        "event_id": row.event_id,
        "sim_day": int(row.sim_day),
        "date": iso(row.date),
        "type": row.type,
        "source": row.source,
        "payload": row.payload,
        "materiality_score": (
            float(row.materiality_score) if row.materiality_score is not None else None
        ),
        "triggered_reoptimization": bool(row.triggered_reoptimization),
        "triggered_decision_id": row.triggered_decision_id,
    }
