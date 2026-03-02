#!/usr/bin/env bash
set -euo pipefail
RUN_ID="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="${2:-.}"
if [[ -x "$SKILL_ROOT/runtime/.venv/bin/python" ]]; then
  PY="$SKILL_ROOT/runtime/.venv/bin/python"
  ROOT="$SKILL_ROOT/runtime"
  if [[ -z "$RUN_ID" ]]; then
    RUN_ID="$("$PY" "$ROOT/scripts/resolve_run_id.py" --project "$PROJECT_DIR")"
  fi
  run_status() { "$PY" "$ROOT/scripts/sqlopt_cli.py" status --run-id "$RUN_ID"; }
  run_resume() { "$PY" "$ROOT/scripts/sqlopt_cli.py" resume --run-id "$RUN_ID"; }
else
  REPO_ROOT="$(cd "$SKILL_ROOT/../.." && pwd)"
  export PYTHONPATH="$REPO_ROOT/python"
  if [[ -z "$RUN_ID" ]]; then
    RUN_ID="$(python3 "$REPO_ROOT/scripts/resolve_run_id.py" --project "$PROJECT_DIR")"
  fi
  run_status() { python3 "$REPO_ROOT/scripts/sqlopt_cli.py" status --run-id "$RUN_ID"; }
  run_resume() { python3 "$REPO_ROOT/scripts/sqlopt_cli.py" resume --run-id "$RUN_ID"; }
fi

for _ in $(seq 1 200); do
  OUT="$(run_status)"
  echo "$OUT"
  if echo "$OUT" | rg -q '"complete": True|"complete": true'; then
    exit 0
  fi
  run_resume
done
echo "resume loop exhausted" >&2
exit 1
