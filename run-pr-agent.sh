#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if ! python -c "import anthropic" >/dev/null 2>&1; then
  python -m pip install anthropic
fi

if [[ $# -eq 0 ]]; then
  echo "Usage: ./run-pr-agent.sh '<task description>'" >&2
  echo "   or: ./run-pr-agent.sh --task-file path/to/task.txt" >&2
  exit 1
fi

python -m pr_agent.run "$@"
