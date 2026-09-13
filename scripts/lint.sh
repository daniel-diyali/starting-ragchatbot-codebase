#!/bin/bash
# Lint the codebase with ruff without modifying any files.
# Exits non-zero if issues are found. Run from the repo root.
set -e

cd "$(dirname "$0")/.."

echo "Running ruff check..."
uv run ruff check backend main.py
