# api/seed/__init__.py — public entry point for B2.
#
# `seed_world(session, seed, start_date)` is the only function anything outside this
# package should call. It builds a deterministic WorldSpec (api.seed.generate.build_world),
# overwrites the demo-critical records (api.seed.planted.apply), and inserts everything
# through the B1 SQLAlchemy session — both policies, in the order the FK constraints require.
from api.seed.generate import build_world  # noqa: F401
from api.seed.seed import seed_world  # noqa: F401
