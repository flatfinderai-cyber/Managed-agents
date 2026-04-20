#!/bin/bash
# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
# FlatFinder™ — Agent System Startup Script
# ─────────────────────────────────────────────────────────────────
# Usage:
#   bash agents/start.sh                        # full pipeline, Toronto, $72k
#   bash agents/start.sh affordability          # affordability agent only
#   bash agents/start.sh scraper Edinburgh      # scraper agent, Edinburgh
#   bash agents/start.sh db                     # database architect only
# ─────────────────────────────────────────────────────────────────

set -e

# ── Locate project root (the flatfinder/ folder) ──────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# ── Load .env.local ───────────────────────────────────────────────
ENV_FILE="$PROJECT_ROOT/.env.local"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

# ── Check API key ─────────────────────────────────────────────────
if [ -z "$ANTHROPIC_API_KEY" ] || [ "$ANTHROPIC_API_KEY" = "FILL_IN_YOUR_ANTHROPIC_KEY" ]; then
  echo ""
  echo "  ✗ ANTHROPIC_API_KEY is not set."
  echo ""
  echo "  Open this file and add your key:"
  echo "    $ENV_FILE"
  echo ""
  echo "  Line to edit:"
  echo "    ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE"
  echo ""
  echo "  Get your key at: https://console.anthropic.com/settings/keys"
  echo ""
  exit 1
fi

# ── Install Python deps if needed ────────────────────────────────
python3 -c "import anthropic" 2>/dev/null || {
  echo "  Installing dependencies…"
  pip install anthropic python-dotenv --break-system-packages -q
}

# ── Run ───────────────────────────────────────────────────────────
AGENT="${1:-all}"
CITY="${2:-Toronto}"
INCOME="${3:-72000}"

case "$AGENT" in
  affordability)
    echo "  Running Affordability Agent (income: \$$INCOME/yr)…"
    python3 -m agents.run --agent affordability --income "$INCOME"
    ;;
  scraper)
    echo "  Running Scraper Agent (city: $CITY)…"
    python3 -m agents.run --agent scraper --city "$CITY"
    ;;
  db)
    echo "  Running Database Architect Agent…"
    python3 -m agents.run --agent db
    ;;
  all)
    echo "  Running full pipeline (city: $CITY, income: \$$INCOME/yr)…"
    python3 -m agents.run --city "$CITY" --income "$INCOME" --save agents/last_run.json
    ;;
  *)
    echo "  Unknown agent: $AGENT"
    echo "  Options: all | affordability | scraper | db"
    exit 1
    ;;
esac
