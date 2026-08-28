# contracts/enums.py — frozen enums. FINAL.md section 8.1, verbatim.
#
# OWNER: SHARED. Adding a new value here is a contract change: announce it out loud,
# get agreement, log it in contracts/CHANGELOG.md, tell everyone to pull.
# Do not reformat this file when editing it.
from typing import Literal

ActionType = Literal[
    "PAY_NOW",  # pay today from cash
    "PAY_EARLY_DISCOUNT",  # pay on/before discount_until to capture discount
    "PAY_AT_MATURITY",  # pay exactly on due_date
    "DELAY",  # pay after due_date, within max_delay_days, accepting penalty
    "FINANCE_BANK",  # pay supplier now, funded by drawing the bank line
    "FINANCE_SUPPLIER",  # supplier paid early by financier, we settle at maturity
    "HOLD",  # no action this cycle, revisit next run
]

FundingSource = Literal["CASH", "BANK_LINE", "SUPPLIER_FINANCE"]

EventType = Literal[
    "DAY_ADVANCED",
    "RECEIVABLE_DELAYED",
    "RECEIVABLE_COLLECTED",
    "NEW_INVOICE",
    "INVOICE_PAID",
    "RATE_CHANGE",
    "NEW_OBLIGATION",
    "SUPPLIER_DISTRESS",
    "CASH_INJECTION",
]

EventSource = Literal["SIM", "JUDGE_INJECTED", "SYSTEM"]

TriggerType = Literal["SCHEDULED", "EVENT", "MANUAL", "WHATIF"]

ActionStatus = Literal["PROPOSED", "EXECUTED", "SUPERSEDED", "ESCALATED"]

InvoiceStatus = Literal["OPEN", "SCHEDULED", "PAID", "FINANCED"]

ReceivableStatus = Literal["OPEN", "COLLECTED", "WRITTEN_OFF"]

FacilityType = Literal["BANK_LINE", "SUPPLIER_FINANCE"]

ObligationCategory = Literal["PAYROLL", "TAX", "RENT", "LOAN_EMI", "UTILITY"]

SolverMethod = Literal["MILP_SCENARIO", "GREEDY_FALLBACK"]
SolverStatus = Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "TIMEOUT"]

ReasonCode = Literal[
    "BUFFER_BREACH",  # paying would push P5 cash below zero
    "DISCOUNT_CAPTURED",
    "DISCOUNT_FORGONE",
    "PENALTY_AVOIDED",
    "PENALTY_ACCEPTED",
    "FACILITY_LIMIT",  # facility headroom exhausted
    "OBLIGATION_PRIORITY",  # cash reserved for a hard obligation
    "SUPPLIER_CRITICAL",  # supplier criticality forced earlier payment
    "SUPPLIER_DISTRESS",  # supplier liquidity stress forced earlier payment
    "CHEAPER_FINANCING",  # borrowing was cheaper than forgoing the discount
    "INSUFFICIENT_CASH",
    "NO_BETTER_ALTERNATIVE",
]
