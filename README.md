# Managed-agents

## Copilot Stack

This repository is wired to use:

- GitHub Copilot CLI (`@github/copilot`)
- GitHub Copilot SDK (`github-copilot-sdk`)
- Copilot Skill for PR analysis
- GitHub Actions workflow for automated PR analysis comments

## Local Run

Run PR analysis with one command:

```bash
./scripts/run-copilot-pr-analysis.sh
```

Output file:

- `artifacts/copilot-pr-analysis.md`

## CI Run

Workflow file:

- `.github/workflows/copilot-pr-analysis.yml`

On each pull request, CI:

1. Installs Copilot CLI + SDK
2. Runs PR analysis script
3. Uploads analysis artifact
4. Posts analysis comment on the PR
