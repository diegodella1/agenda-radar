#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
: "${1:?Indicar backup}"
: "${2:?Indicar nueva base de destino}"
exec .venv/bin/python -m agenda_radar.cli restore "$1" "$2"
