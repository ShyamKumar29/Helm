#!/usr/bin/env bash
# scripts/reset.sh — stub, B0. Real reset (DB rebuild + seed) lands in B2/B5.
set -euo pipefail

SEED="${1:-42}"
START_DATE="${2:-2026-03-01}"

curl -s -X POST localhost:8000/api/sim/reset \
  -H 'content-type: application/json' \
  -d "{\"seed\": ${SEED}, \"start_date\": \"${START_DATE}\"}"
echo
