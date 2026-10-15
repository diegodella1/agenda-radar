#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
python_bin="${PYTHON_BIN:-python3.12}"
"$python_bin" -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m agenda_radar.cli init
printf '%s\n' 'Instalado. Crear administrador: .venv/bin/python -m agenda_radar.cli create-admin --email TU_CORREO' 'Iniciar web y worker por separado; consultar README.md.'
