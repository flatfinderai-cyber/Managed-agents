#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install -q -r requirements-copilot.txt

if ! command -v copilot >/dev/null 2>&1; then
  npm install -g @github/copilot@1.0.32 >/dev/null
fi

python tools/copilot_pr_analysis.py "$@"
