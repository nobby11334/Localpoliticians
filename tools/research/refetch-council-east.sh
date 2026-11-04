#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd -- "$(dirname -- "$0")" && pwd)"
EAST_PYTHON="${CODEX_PRIMARY_RUNTIME_PYTHON:-python3}"
"$EAST_PYTHON" "$BASE/fetch-east.py"
"$EAST_PYTHON" "$BASE/fetch-east-more.py"
"$EAST_PYTHON" "$BASE/parse-east.py"
