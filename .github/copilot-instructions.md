# Managed-agents Workspace Guidelines

## Scope
These instructions apply to the whole repository and are intended to bootstrap coding agents quickly.

## Primary References
- Managed Agents policy and required execution order: `managed-agents-policy.md`
- Anthropic managed-agents onboarding doc used in this repo: `managed-agents.doc`
- Perplexity agent API notes used in this repo: `agents-run.doc`

Link to these files for details instead of copying long documentation into responses or code comments.

## Architecture
- `pr_agent/` contains the Anthropic Managed Agents flow.
  - `pr_agent/setup.py`: one-time provisioning of vault, environment, and agent.
  - `pr_agent/run.py`: per-task session creation and streaming event loop.
- `example/` contains a minimal Perplexity API example (`example/main.py`).
- `run-perplexity-agent.sh` is a shell quickstart for Perplexity API calls.

## Build And Run
- Python version: `>=3.12`.
- Create env and install dependencies:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install anthropic perplexityai`
- Quick checks:
  - `python pr_agent/setup.py` (one-time provisioning)
  - `python pr_agent/run.py "<task description>"` (run one managed-agent task)
  - `./run-pr-agent.sh "<task description>"` (one-command auto-bootstrap + run)
  - `python example/main.py` (Perplexity SDK smoke test)
  - `./run-perplexity-agent.sh` (Perplexity curl smoke test)

## Required Conventions
- Follow `managed-agents-policy.md` exactly for managed-agent workflows.
- Never hardcode secrets. Read from environment variables only.
- Validate required env vars before API calls and fail with clear errors.
- Keep the object lifecycle explicit and ordered: agent -> environment -> session -> streamed events.
- Treat `session.status_idle` as completion; do not claim success before it.

## Environment And Secrets
- Use `.env.example` as the template.
- Required variables vary by flow:
  - Anthropic flow: `ANTHROPIC_API_KEY`, `GITHUB_TOKEN`, and managed-agent IDs produced by setup.
  - Perplexity flow: `PERPLEXITY_API_KEY`.
- Never commit `.env` or credentials.

## Coding Expectations
- Keep changes small and task-focused.
- Preserve existing event handling behavior in `pr_agent/run.py` unless requested.
- If adding managed-agent API calls, use beta managed-agent endpoints/features already used in repo.
