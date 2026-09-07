#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PYTHON_BIN="${CLAUDER_WORKBENCH_PYTHON:-}"

if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "Python 3.10+ was not found." >&2
    exit 1
  fi
fi

export PYTHONPATH="$SCRIPT_DIR/skills/clauder-rstudio-workbench${PYTHONPATH:+:$PYTHONPATH}"
if "$PYTHON_BIN" -c 'import tomlkit' >/dev/null 2>&1; then
  exec "$PYTHON_BIN" -m clauder_workbench.installer --repo-root "$SCRIPT_DIR" "$@"
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to provision the installer dependencies (tomlkit)." >&2
  exit 1
fi
exec uv run --no-project --with 'tomlkit>=0.13,<1' --with "tomli>=2; python_version < '3.11'" \
  --python "$PYTHON_BIN" python -m clauder_workbench.installer --repo-root "$SCRIPT_DIR" "$@"
