#!/bin/bash
# Auto-format the codebase with black and apply safe ruff lint fixes
# (import sorting, unused imports, etc.). Run from the repo root.
set -e

cd "$(dirname "$0")/.."

echo "Running black..."
uv run black backend main.py

echo "Running ruff --fix..."
uv run ruff check --fix backend main.py

echo "Done."
