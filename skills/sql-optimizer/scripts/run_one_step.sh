#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_PATH="${1:-sqlopt.yml}"
TO_STAGE="${2:-patch_generate}"
RUN_ID="${3:-}"
MAX_STEPS="${4:-200}"
MAX_SECONDS="${5:-95}"
if [[ -x "$SKILL_ROOT/runtime/.venv/bin/python" ]]; then
  PY="$SKILL_ROOT/runtime/.venv/bin/python"
  SCRIPT="$SKILL_ROOT/runtime/scripts/run_until_budget.py"
  if [[ -n "$RUN_ID" ]]; then
    "$PY" "$SCRIPT" --config "$CONFIG_PATH" --to-stage "$TO_STAGE" --run-id "$RUN_ID" --max-steps "$MAX_STEPS" --max-seconds "$MAX_SECONDS"
  else
    "$PY" "$SCRIPT" --config "$CONFIG_PATH" --to-stage "$TO_STAGE" --max-steps "$MAX_STEPS" --max-seconds "$MAX_SECONDS"
  fi
else
  REPO_ROOT="$(cd "$SKILL_ROOT/../.." && pwd)"
  export PYTHONPATH="$REPO_ROOT/python"
  if [[ -n "$RUN_ID" ]]; then
    python3 "$REPO_ROOT/scripts/run_until_budget.py" --config "$CONFIG_PATH" --to-stage "$TO_STAGE" --run-id "$RUN_ID" --max-steps "$MAX_STEPS" --max-seconds "$MAX_SECONDS"
  else
    python3 "$REPO_ROOT/scripts/run_until_budget.py" --config "$CONFIG_PATH" --to-stage "$TO_STAGE" --max-steps "$MAX_STEPS" --max-seconds "$MAX_SECONDS"
  fi
fi
