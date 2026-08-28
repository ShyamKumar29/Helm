#!/usr/bin/env bash
# scripts/reset.sh — B8. One command, no arguments to remember
# (docs/backend/11-PHASE-B8-hardening-and-demo.md section 4). Run this before every
# rehearsal and possibly in front of a judge.
set -euo pipefail

docker compose up -d db
until docker compose exec -T db pg_isready -U helm >/dev/null 2>&1; do sleep 0.5; done

curl -fsS -X POST localhost:8000/api/sim/reset \
  -H 'content-type: application/json' \
  -d '{"seed":42,"start_date":"2026-03-01"}'

echo
curl -fsS localhost:8000/api/sim/status
echo
