#!/bin/bash
# Quality gate for CI / pre-commit: verifies formatting and lint cleanliness
# WITHOUT modifying any files. Exits non-zero if either check fails.
# Run from the repo root. Use scripts/format.sh to fix issues locally.
set -e

cd "$(dirname "$0")/.."

echo "Checking black formatting..."
uv run black --check --diff backend main.py

echo "Running ruff check..."
uv run ruff check backend main.py

echo "All quality checks passed."
