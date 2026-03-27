#!/bin/bash
# SQL Optimizer - Pre-commit Lint Hook
# Runs appropriate linter based on staged files
# Exit non-zero on lint failure (strict mode)

set -e

echo "Running lint checks..."

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

if [ -z "$STAGED_FILES" ]; then
    echo "No staged files"
    exit 0
fi

HAS_PYTHON=false
HAS_JS=false
HAS_GO=false

while IFS= read -r file; do
    case "$file" in
        *.py)
            HAS_PYTHON=true
            ;;
        *.js|*.jsx|*.ts|*.tsx)
            HAS_JS=true
            ;;
        *.go)
            HAS_GO=true
            ;;
    esac
done <<< "$STAGED_FILES"

if [ "$HAS_PYTHON" = true ]; then
    echo "Running ruff on Python files..."
    ruff check $STAGED_FILES || { echo "ruff failed"; exit 1; }

    echo "Checking method order (CLASS-003)..."
    PY_FILES=$(echo "$STAGED_FILES" | grep "\.py$" | tr '\n' ' ')
    python3 "$(dirname "$0")/check_method_order.py" $PY_FILES || { echo "Method order check failed"; exit 1; }
fi

if [ "$HAS_JS" = true ]; then
    echo "Running eslint on JS/TS files..."
    eslint $STAGED_FILES || { echo "eslint failed"; exit 1; }
fi

if [ "$HAS_GO" = true ]; then
    echo "Running golangci-lint on Go files..."
    golangci-lint run $STAGED_FILES || { echo "golangci-lint failed"; exit 1; }
fi

echo "Lint checks passed"
exit 0
