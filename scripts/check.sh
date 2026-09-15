#!/usr/bin/env sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
project_root=$(dirname "$script_dir")
cd "$project_root"

# Let uv choose the locked environment when it is available. The fallback is
# useful on machines that already have the dependencies in their active venv.
if command -v uv >/dev/null 2>&1; then
  exec uv run python scripts/check.py
fi

PYTHONPATH="$project_root/src${PYTHONPATH:+:$PYTHONPATH}" \
  exec "${PYTHON:-python3}" scripts/check.py
