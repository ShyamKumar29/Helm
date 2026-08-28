# api/services/clock.py — B5. sim_day / as_of arithmetic: the only date math in api/
# services (docs/backend/08-PHASE-B5-sim-loop.md section 2). api/seed/generate.py does its
# own pre-existing date math building the seed world and is out of scope here; every date
# delta the *sim loop* needs from here on routes through this module.
from __future__ import annotations

from datetime import date, timedelta


def advance(as_of: date) -> date:
    """One simulated day forward."""
    return as_of + timedelta(days=1)


def add_days(d: date, n: int) -> date:
    return d + timedelta(days=int(n))


def days_between(later: date, earlier: date) -> int:
    """`later` - `earlier`, in whole days. Negative if `later` is before `earlier`."""
    return (later - earlier).days
