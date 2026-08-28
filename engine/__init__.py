# engine/ — OWNER: Shyam. Nobody else opens this folder (CLAUDE.md rule 1).
#
# Pure function of State. No database, no env vars, no network, no stdout in production
# paths (CLAUDE.md rule 3). Public contract is exactly two functions in engine/decide.py —
# forecast() and decide() — frozen per FINAL.md §12. Everything under this package is free
# to change; that boundary is not.
