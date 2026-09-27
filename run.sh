#!/usr/bin/env bash
# Start the Invoice Generator on http://127.0.0.1:8100 (set INVOICEGEN_PORT to change).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi

exec .venv/bin/python -m invoicegen
