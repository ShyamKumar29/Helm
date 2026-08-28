# api/enums.py — thin re-export from contracts/enums.py, plus API-only constants.
#
# Never redefine an enum value locally. If contracts.enums does not import cleanly,
# that is a contract problem to raise out loud, not to route around — see
# docs/backend/04-PHASE-B1-db-and-models.md step 4.
from contracts.enums import (  # noqa: F401
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

POLICY_AGENT = "AGENT"
POLICY_BASELINE = "BASELINE"
POLICIES = (POLICY_AGENT, POLICY_BASELINE)
