#!/bin/sh
set -eu
curl --fail --silent --show-error "${APP_BASE_URL:-http://127.0.0.1:8765}/health/ready"
