# api/services/rng.py — B5. Seeded, reproducible sampling. This is the only module that
# calls `np.random`/`random` inside the sim loop (docs/backend/08-PHASE-B5-sim-loop.md
# section 3 step 2; 14-TESTING-AND-VERIFICATION.md drill 5 greps for stragglers).
from __future__ import annotations

import hashlib

import numpy as np


def gen(seed: int, *parts) -> np.random.Generator:
    """A generator seeded from `seed` plus an arbitrary key (e.g. a receivable id). Two calls
    with identical arguments always produce the same first draw — this is what makes a
    receivable's realised delay reproducible across resets (FINAL.md section 8, CLAUDE.md
    rule 6), without needing `sim_day` in the key so the delay is decided once per receivable
    and stays decided.
    """
    key = ":".join(str(p) for p in parts).encode()
    h = int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")
    return np.random.default_rng((seed ^ h) % (2**63))


def sample_delay(
    rng: np.random.Generator,
    *,
    mean_delay_days: float,
    std_delay_days: float,
    on_time_probability: float,
    historical_delays: list[float],
) -> int:
    """FINAL.md section 11.4. Bootstrap from `historical_delays` when there are 5+ samples,
    otherwise a floor-at-zero normal — always wrapped in the on-time mixture (a plain normal
    without it is unrealistic; see 11.4).

    Exactly one draw is consumed per branch, so calling this once against a generator seeded
    by `gen(seed, receivable_id)` always reproduces the same delay. That means the caller can
    recompute a receivable's realised arrival on every simulated day instead of caching it on
    the row — cheaper than a schema change and just as deterministic.
    """
    if rng.random() < on_time_probability:
        return 0
    if len(historical_delays) >= 5:
        delay = rng.choice(historical_delays)
    else:
        delay = max(0.0, rng.normal(mean_delay_days, std_delay_days))
    return round(float(delay))
