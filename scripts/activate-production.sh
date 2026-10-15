#!/usr/bin/env bash
# Current deployment uses isolated Docker services and its own Cloudflare tunnel.
set -euo pipefail
cd "$(dirname "$0")/.."
test -f data/agenda.db
test -f secrets/master.key
test -f secrets/cloudflared.json
docker compose -f compose.production.yaml config --quiet
docker compose -f compose.production.yaml up -d web worker tunnel
