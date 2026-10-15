#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
: "${1:?Indicar archivo de destino fuera del disco de datos}"
exec .venv/bin/python -m agenda_radar.cli backup "$1"
