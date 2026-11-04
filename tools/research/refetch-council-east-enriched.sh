#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd -- "$(dirname -- "$0")" && pwd)"
EAST_PYTHON="${CODEX_PRIMARY_RUNTIME_PYTHON:-python3}"
# Re-download official rosters and extract linked member sites (at most 6 requests).
"$BASE/refetch-council-east.sh"
"$EAST_PYTHON" "$BASE/enrich-east.py"
# Reapply only the frozen, manually reviewed 2026-11-04 biography observations.
# Newly discovered biography candidates require review before import.
"$EAST_PYTHON" "$BASE/import-east-biographies.py"
