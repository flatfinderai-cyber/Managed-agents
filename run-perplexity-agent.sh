#!/usr/bin/env bash
set -euo pipefail

# Load PERPLEXITY_API_KEY from .env if not already exported.
if [[ -z "${PERPLEXITY_API_KEY:-}" && -f .env ]]; then
  PERPLEXITY_API_KEY="$({
    awk -F '=' '
      /^[[:space:]]*PERPLEXITY_API_KEY[[:space:]]*=/ {
        value=$0
        sub(/^[^=]*=/, "", value)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
        gsub(/^"|"$/, "", value)
        gsub(/^\047|\047$/, "", value)
        last=value
      }
      END { if (last != "") print last }
    ' .env
  })"
  export PERPLEXITY_API_KEY
fi

if [[ -z "${PERPLEXITY_API_KEY:-}" ]]; then
  echo "Error: PERPLEXITY_API_KEY is not set." >&2
  echo "Set it in .env or export it first, for example:" >&2
  echo "  cp .env.example .env" >&2
  echo "  # then edit .env and set PERPLEXITY_API_KEY" >&2
  exit 1
fi

curl https://api.perplexity.ai/chat/completions \
  -H "Authorization: Bearer $PERPLEXITY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"sonar-pro","messages":[{"role":"user","content":"Hello"}]}'
