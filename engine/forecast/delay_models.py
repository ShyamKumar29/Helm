# engine/forecast/delay_models.py — FINAL.md §11.4, receivable delay model.
#
# Per customer, a mixture: with probability `on_time_probability` the delay is 0; otherwise
# draw from bootstrap (>=5 historical samples) or a floored Normal. Vectorized so
# monte_carlo.py can draw all `n_paths` samples for one customer in a single call — a Python
# loop over 2000 paths x every receivable would be the thing that blows the 400ms budget
# (FINAL.md §12 build order, H+4-H+8).
from __future__ import annotations

import numpy as np

from contracts.schemas import Customer

MIN_BOOTSTRAP_SAMPLES = 5


def sample_delays(rng: np.random.Generator, customer: Customer | None, n: int) -> np.ndarray:
    """n delay-day samples (float, >= 0) for one customer. `customer=None` (an orphaned
    customer_id reference) degrades to "always on time" rather than crashing the forecast —
    the same bulletproofing principle CLAUDE.md rule 9 asks of the frontend applies here."""
    if customer is None or n == 0:
        return np.zeros(n)

    on_time = rng.random(n) < customer.on_time_probability
    late_mask = ~on_time
    n_late = int(late_mask.sum())
    delays = np.zeros(n)
    if n_late == 0:
        return delays

    hist = np.asarray(customer.historical_delays, dtype=float)
    if hist.size >= MIN_BOOTSTRAP_SAMPLES:
        sampled = rng.choice(hist, size=n_late, replace=True)
    else:
        std = max(customer.std_delay_days, 1e-6)  # a zero std would make every draw identical
        sampled = rng.normal(customer.mean_delay_days, std, size=n_late)

    delays[late_mask] = np.maximum(0.0, np.round(sampled))
    return delays
