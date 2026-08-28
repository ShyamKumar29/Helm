# api/services/ids.py — one helper module, one format, used everywhere.
# IDs are contract surface (FINAL.md section 8, "Universal conventions").
# Counters come from `SELECT count(*)` on the relevant table inside the caller's
# transaction, not from a Python global — that is the caller's job (B2 onward).


def event_id(n: int) -> str:
    return f"EVT-{n:04d}"


def decision_id(n: int) -> str:
    return f"DEC-{n:06d}"


def action_id(n: int) -> str:
    return f"ACT-{n:04d}"


def invoice_id(n: int) -> str:
    return f"INV-{n:04d}"


def rcv_id(n: int) -> str:
    return f"RCV-{n:04d}"


def sup_id(n: int) -> str:
    return f"SUP-{n:03d}"


def cus_id(n: int) -> str:
    return f"CUS-{n:03d}"


def obl_id(n: int) -> str:
    return f"OBL-{n:03d}"


def fac_id(n: int) -> str:
    return f"FAC-{n:03d}"
