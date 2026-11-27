#!/usr/bin/env bash
# Current deployment uses isolated Docker services and its own Cloudflare tunnel.
set -euo pipefail
cd "$(dirname "$0")/.."
test -f data/agenda.db
test -f secrets/master.key
test -f secrets/cloudflared-aradar.json
docker compose -f compose.production.yaml config --quiet
docker compose -f compose.production.yaml run --rm --no-deps web python -m agenda_radar.cli backup "/app/backups/pre-release-$(date -u +%Y%m%dT%H%M%S).db"
docker compose -f compose.production.yaml run --rm --no-deps web python -m agenda_radar.cli init
docker compose -f compose.production.yaml up -d web worker collaboration tunnel
